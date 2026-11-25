"""Opt-in daily reverse wallet research over recent launches (read-only).

Every ``interval`` the worker:

1. picks launches 24-48 h old from the canonical chain rows (winners and
   non-winners alike -- no outcome filter), skipping ones already researched;
2. collects each token's finalized history and stores its classified wallet
   events (failed transactions are counted, not stored) as one
   ``wallet.token_history`` observation;
3. rebuilds registry records and point-in-time profiles from all histories
   within the lookback, persists ``wallet.registry`` and ``wallet.profile``
   rows, and
4. enqueues one ``WALLET_RESEARCH`` Telegram digest (research only, no
   entry or copy instruction).

Disabled by default (``WALLET_RESEARCH_ENABLED=false``).  Nothing here can
change modes, size positions or sign anything.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from memeradar_application.onchain_wallet_events import (
    REGISTRY_VERSION,
    ActivityKind,
    OnChainWalletEvent,
    RegistryRecord,
    build_registry_record,
    decode_event,
    deduplicate,
    encode_event,
)
from memeradar_application.wallet_intelligence import (
    ProfilePolicy,
    WalletCategory,
    WalletProfile,
    build_profiles,
    co_buy_clusters,
)
from memeradar_domain import EventEnvelope, Observation, Provenance, QualityState
from memeradar_persistence import ObservationRow, SqlAlchemyUnitOfWork
from memeradar_providers.pump_fun_idl import PUMP_FUN_PROGRAM_ID
from memeradar_providers.token_history_collector import TokenHistory, collect_token_history
from memeradar_providers.wallet_funding import earliest_funding, shared_funder_clusters

from .operations_jobs import sleep_until_stopped
from .wallet_profile_store import profile_observation

LOGGER = logging.getLogger(__name__)
HISTORY_KIND = "wallet.token_history"
REGISTRY_KIND = "wallet.registry"
FUNDING_KIND = "wallet.funding"
_EARLY_BUYERS_PER_TOKEN = 10
_STORED_KINDS = frozenset(ActivityKind) - {ActivityKind.FAILED}
Sleep = Callable[[float], Awaitable[None]]


class HistoryCollector:
    """Seam over the RPC collector so tests can inject recorded histories."""

    def __init__(self, rpc: object) -> None:
        self.rpc = rpc

    async def collect(self, mint: str, launch_signature: str | None, max_tx: int) -> TokenHistory:
        return await collect_token_history(
            self.rpc, mint, launch_signature=launch_signature, max_tx=max_tx  # type: ignore[arg-type]
        )

    async def funding(self, wallet: str) -> dict[str, object]:
        return await earliest_funding(self.rpc, wallet)  # type: ignore[arg-type]


def _text_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _observation(
    kind: str, source_id: str, at: datetime, payload: dict[str, object]
) -> Observation:
    return Observation(
        id=uuid5(NAMESPACE_URL, f"memeradar:{kind}:{source_id}"),
        kind=kind,
        provenance=Provenance(
            provider="memeradar.wallet-research", source_id=source_id, observed_at=at,
            parser_version=REGISTRY_VERSION,
        ),
        occurred_at=at,
        observed_at=at,
        ingested_at=at,
        quality_state=QualityState.FRESH,
        normalized_payload=payload,
    )


def digest_lines(
    registry: Sequence[RegistryRecord],
    profiles: dict[str, WalletProfile],
    researched_now: int,
    complete_now: int,
) -> list[str]:
    outcomes: Counter[str] = Counter()
    for record in registry:
        for outcome in record.outcomes:
            if outcome.horizon == "24h":
                outcomes[outcome.outcome.value] += 1
    categories: Counter[str] = Counter(
        category.value for profile in profiles.values() for category in profile.categories
    )
    candidates = sorted(
        (p for p in profiles.values()
         if WalletCategory.EARLY_SMART_MONEY_CANDIDATE in p.categories),
        key=lambda p: (-p.early_5x_tokens, p.wallet),
    )[:3]
    lines = [
        f"Researched {researched_now} new launches ({complete_now} with complete history)",
        f"Tokens in lookback: {len(registry)}; 24h outcomes: "
        + ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items())),
        f"Wallets profiled: {len(profiles)}",
        "Risk categories: "
        + ", ".join(
            f"{name} {categories[name]}"
            for name in ("CREATOR_LINKED", "POTENTIAL_INSIDER", "POTENTIAL_WASH_TRADER",
                         "POTENTIAL_MANIPULATION_CLUSTER")
            if categories[name]
        ),
        f"Early smart-money candidates: {categories['EARLY_SMART_MONEY_CANDIDATE']}"
        " (heuristic, not validated)",
    ]
    lines.extend(f"  {p.wallet} early>=5x {p.early_5x_tokens}, win {p.win_rate}"
                 for p in candidates)
    lines.append("Research only: not an entry, copy or exit instruction")
    return lines


class WalletResearchWorker:
    def __init__(
        self,
        engine: AsyncEngine,
        collector: HistoryCollector,
        *,
        clock: Callable[[], datetime] | None = None,
        max_tokens_per_run: int = 30,
        max_tx_per_token: int = 800,
        max_funding_lookups_per_run: int = 100,
        lookback: timedelta = timedelta(days=30),
        policy: ProfilePolicy | None = None,
    ) -> None:
        self.engine = engine
        self.collector = collector
        self.clock = clock or (lambda: datetime.now(UTC))
        self.max_tokens = max_tokens_per_run
        self.max_tx = max_tx_per_token
        self.max_funding = max_funding_lookups_per_run
        self.lookback = lookback
        self.policy = policy or ProfilePolicy()
        self._factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _due_launches(self, now: datetime) -> list[tuple[str, str | None, datetime]]:
        async with self._factory() as session:
            researched = set(
                (
                    await session.scalars(
                        select(ObservationRow.normalized_payload["mint"].as_string()).where(
                            ObservationRow.kind == HISTORY_KIND
                        )
                    )
                ).all()
            )
            rows = (
                await session.scalars(
                    select(ObservationRow)
                    .where(
                        ObservationRow.kind == "chain.event",
                        ObservationRow.program_id == PUMP_FUN_PROGRAM_ID,
                        ObservationRow.occurred_at >= now - timedelta(hours=48),
                        ObservationRow.occurred_at <= now - timedelta(hours=24),
                    )
                    .order_by(ObservationRow.occurred_at)
                    .limit(5000)
                )
            ).all()
        due: list[tuple[str, str | None, datetime]] = []
        for row in rows:
            payload = row.normalized_payload
            if str(payload.get("instruction_type", "")).lower() not in {"create", "create_v2"}:
                continue
            mint = payload.get("mint_address") or payload.get("mint")
            if isinstance(mint, str) and mint not in researched:
                researched.add(mint)
                occurred = row.occurred_at or row.observed_at
                due.append((mint, row.signature, occurred))
            if len(due) >= self.max_tokens:
                break
        return due

    async def _funding_rows(self, now: datetime) -> list[dict[str, object]]:
        async with self._factory() as session:
            rows = (
                await session.scalars(
                    select(ObservationRow).where(
                        ObservationRow.kind == FUNDING_KIND,
                        ObservationRow.observed_at >= now - self.lookback,
                    )
                )
            ).all()
        return [dict(row.normalized_payload) for row in rows]

    async def _stored_histories(self, now: datetime) -> list[dict[str, object]]:
        async with self._factory() as session:
            rows = (
                await session.scalars(
                    select(ObservationRow).where(
                        ObservationRow.kind == HISTORY_KIND,
                        ObservationRow.observed_at >= now - self.lookback,
                    )
                )
            ).all()
        return [dict(row.normalized_payload) for row in rows]

    async def run_once(self) -> dict[str, object]:
        now = self.clock()
        due = await self._due_launches(now)
        new_histories: list[Observation] = []
        complete = 0
        for mint, signature, launched_at in due:
            history = await self.collector.collect(mint, signature, self.max_tx)
            complete += history.history_complete
            kept = [encode_event(e) for e in history.events if e.kind in _STORED_KINDS]
            new_histories.append(
                _observation(
                    HISTORY_KIND,
                    f"wallet:history:{mint}",
                    now,
                    {
                        "mint": mint,
                        "launch_signature": signature,
                        "launch_at": launched_at.isoformat(),
                        **history.meta(),
                        "failed_transactions": sum(
                            1 for e in history.events if e.kind is ActivityKind.FAILED
                        ),
                        "events": kept,
                    },
                )
            )
        if new_histories:
            async with SqlAlchemyUnitOfWork(self.engine) as unit_of_work:
                for observation in new_histories:
                    await unit_of_work.observations.add(observation)
                await unit_of_work.commit()
        funded = await self._funding_rows(now)
        known = {str(f.get("to_address")) for f in funded}
        lookups: list[str] = []
        for observation in new_histories:
            payload = observation.normalized_payload
            raw = payload.get("events")
            token_events = [decode_event(r) for r in raw if isinstance(r, dict)] if isinstance(
                raw, list
            ) else []
            creator = next((e.wallet for e in token_events if e.kind is ActivityKind.CREATE), None)
            early = [
                e.wallet for e in sorted(token_events, key=lambda e: (e.slot, e.event_index))
                if e.kind is ActivityKind.SWAP_BUY and e.wallet != creator
            ]
            for wallet in list(dict.fromkeys(early))[:_EARLY_BUYERS_PER_TOKEN]:
                if wallet not in known and wallet not in lookups:
                    lookups.append(wallet)
        funding_rows: list[Observation] = []
        for wallet in lookups[: self.max_funding]:
            try:
                funding = await self.collector.funding(wallet)
            except Exception as error:  # noqa: BLE001 - coverage stays explicit
                LOGGER.info("wallet_funding_failed", extra={"error_class": type(error).__name__})
                continue
            funding_rows.append(
                _observation(FUNDING_KIND, f"wallet:funding:{wallet}", now, funding)
            )
        if funding_rows:
            async with SqlAlchemyUnitOfWork(self.engine) as unit_of_work:
                for observation in funding_rows:
                    await unit_of_work.observations.add(observation)
                await unit_of_work.commit()
        funded = [*funded, *(dict(o.normalized_payload) for o in funding_rows)]
        stored = await self._stored_histories(now)
        events: list[OnChainWalletEvent] = []
        records: list[RegistryRecord] = []
        for stored_history in stored:
            raw_events = stored_history.get("events")
            token_events = [
                decode_event(row) for row in raw_events if isinstance(row, dict)
            ] if isinstance(raw_events, list) else []
            events.extend(token_events)
            migrated = next(
                (e.block_time for e in token_events if e.kind is ActivityKind.LIQUIDITY_MIGRATION),
                None,
            )
            creator = next((e.wallet for e in token_events if e.kind is ActivityKind.CREATE), None)
            records.append(
                build_registry_record(
                    mint=str(stored_history["mint"]),
                    launch_at=datetime.fromisoformat(str(stored_history["launch_at"])),
                    activities=token_events,
                    now=now,
                    creator=creator,
                    launch_signature=_text_or_none(stored_history.get("launch_signature")),
                    migrated_at=migrated,
                    history_complete=bool(stored_history.get("history_complete")),
                )
            )
        events = list(deduplicate(events))
        creators = {r.creator for r in records if r.creator}
        clusters = co_buy_clusters(events, as_of=now, exclude=creators)
        for wallet, cluster_id in shared_funder_clusters(funded).items():
            clusters.setdefault(wallet, cluster_id)
        profiles = build_profiles(
            events, {r.mint: r for r in records}, as_of=now, policy=self.policy,
            cluster_members=clusters,
        )
        bucket = int(now.timestamp() // 3600)
        lines = digest_lines(records, profiles, len(due), complete)
        async with SqlAlchemyUnitOfWork(self.engine) as unit_of_work:
            for record in records:
                await unit_of_work.observations.add(
                    _observation(REGISTRY_KIND, f"wallet:registry:{record.mint}:{bucket}", now,
                                 record.to_payload())
                )
            for profile in profiles.values():
                await unit_of_work.observations.add(profile_observation(profile))
            if due:
                await unit_of_work.outbox.enqueue(
                    EventEnvelope(
                        id=uuid5(NAMESPACE_URL, f"memeradar:wallet-research:{bucket}"),
                        kind="AlertRequested",
                        aggregate_type="research",
                        aggregate_id=uuid5(NAMESPACE_URL, "memeradar:wallet-research"),
                        occurred_at=now, observed_at=now, ingested_at=now,
                        correlation_id=f"wallet-research:{bucket}",
                        producer="memeradar.wallet-research",
                        payload={
                            "type": "WALLET_RESEARCH",
                            "severity": "INFO",
                            "dedupe_key": f"wallet-research:{bucket}",
                            "payload": {
                                "state": "WALLET_RESEARCH",
                                "symbol": "Wallet research digest",
                                "advisory_lines": lines,
                            },
                        },
                        idempotency_key=f"wallet-research:{bucket}",
                    ),
                    side_effect_kind="notification",
                )
            await unit_of_work.commit()
        report: dict[str, object] = {
            "researched": len(due),
            "complete": complete,
            "tokens_in_lookback": len(records),
            "wallets_profiled": len(profiles),
            "cluster_wallets": len(clusters),
            "funding_lookups": len(funding_rows),
        }
        LOGGER.info("wallet_research_cycle", extra=report)
        return report

    async def run(
        self, stop_event: asyncio.Event, *, interval_seconds: float, sleeper: Sleep
    ) -> None:
        while not stop_event.is_set():
            try:
                await self.run_once()
            except Exception as error:  # noqa: BLE001 - research must not stop the worker
                LOGGER.warning(
                    "wallet_research_failed", extra={"error_class": type(error).__name__}
                )
            await sleep_until_stopped(stop_event, interval_seconds, sleeper)


__all__ = [
    "HISTORY_KIND",
    "REGISTRY_KIND",
    "HistoryCollector",
    "WalletResearchWorker",
    "digest_lines",
]
