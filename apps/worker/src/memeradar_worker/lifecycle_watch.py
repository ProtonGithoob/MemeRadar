"""Post-launch lifecycle watch and manual-position exit monitor.

One bounded loop that:

1. incrementally discovers Pump.fun launches from the canonical chain rows
   (cursor on ``ingested_at``; never a full-table reload);
2. polls DexScreener in batches of 30 mints with a hard per-cycle request
   budget, spending it on hot mints and open manual positions first;
3. labels outcomes per horizon without lookahead;
4. raises ``REVIVAL_WATCH`` advisories for sustained, buyer-corroborated
   second waves on tokens whose launch safety passed;
5. raises ``MANUAL_EXIT`` advisories for positions the operator bought.

Nothing here scores AlphaScore, changes modes, or executes trades.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from memeradar_application.holder_concentration import (
    ConcentrationRisk,
    HolderConcentration,
    HolderSnapshot,
    assess_concentration,
    unknown_concentration,
)
from memeradar_application.lifecycle_watch import (
    LIFECYCLE_WATCH_VERSION,
    LifecycleOutcome,
    LifecyclePolicy,
    LifecycleSample,
    MintLifecycle,
    RevivalAssessment,
    RevivalSignal,
    Tier,
    apply_sample,
    assess_revival,
    finalize,
    mark_alerted,
    record_migration,
    record_missing,
    schedule_next,
)
from memeradar_application.manual_exit import (
    EntryPriceSemantics,
    ExitAdvice,
    ExitAdvisorState,
    ExitPolicy,
    ManualPosition,
    advise,
)
from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_domain import EventEnvelope, Observation, Provenance, QualityState
from memeradar_persistence import ObservationRow, SqlAlchemyUnitOfWork
from memeradar_providers.pump_fun_idl import PUMP_FUN_PROGRAM_ID
from memeradar_providers.transport import ProviderError, ProviderRateLimitedError

LOGGER = logging.getLogger(__name__)
Clock = Callable[[], datetime]
Sleep = Callable[[float], Awaitable[None]]

BATCH_SIZE = 30
PRODUCER = "memeradar.lifecycle-watch"
MANUAL_POSITION_KIND = "manual.position"
POSITION_MARK_KIND = "manual.position_mark"
EXIT_ADVICE_KIND = "manual.exit_advice"
OUTCOME_KIND = "lifecycle.outcome"
SIGNAL_KIND = "lifecycle.signal"
_LAUNCH_NAMES = frozenset({"create", "create_v2"})
_POSITION_POLL = timedelta(seconds=20)
# Re-armable advisories may legitimately recur; bucket their delivery identity.
_REARMABLE_KEYS = frozenset({"stale", "sell_pressure"})


class HolderSnapshotPort(Protocol):
    async def fetch_holder_snapshot(
        self, mint: str, *, context: ProviderRequestContext
    ) -> HolderSnapshot: ...


class LifecycleMarketPort(Protocol):
    async def lifecycle_samples(
        self, mints: Sequence[str], *, context: ProviderRequestContext
    ) -> Mapping[str, LifecycleSample | None]: ...


@dataclass(slots=True)
class _PositionTrack:
    position: ManualPosition | None
    mint: str
    position_id: str
    opened_at: datetime
    size_usd: Decimal
    symbol: str | None
    entry_price_usd: Decimal | None
    advisor: ExitAdvisorState = field(default_factory=ExitAdvisorState)
    last_polled_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CycleReport:
    tracked: int
    polled: int
    requests: int
    samples: int
    missing: int
    revivals: int
    alerts: int
    advisories: int
    outcomes: int
    retired: int
    rate_limited: bool
    tiers: Mapping[str, int]


def _payload_mint(payload: Mapping[str, object]) -> str | None:
    for key in ("mint", "mint_address", "address"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _observation(
    *,
    kind: str,
    source_id: str,
    at: datetime,
    payload: Mapping[str, object],
    occurred_at: datetime | None = None,
    quality: QualityState = QualityState.FRESH,
) -> Observation:
    return Observation(
        id=uuid5(NAMESPACE_URL, f"memeradar:lifecycle:{kind}:{source_id}"),
        kind=kind,
        provenance=Provenance(
            provider=PRODUCER,
            source_id=source_id,
            observed_at=at,
            parser_version=LIFECYCLE_WATCH_VERSION,
        ),
        occurred_at=occurred_at or at,
        observed_at=at,
        ingested_at=at,
        quality_state=quality,
        normalized_payload=dict(payload),
    )


def _alert_event(
    *,
    alert_type: str,
    severity: str,
    dedupe_key: str,
    mint: str,
    at: datetime,
    payload: Mapping[str, object],
) -> EventEnvelope:
    return EventEnvelope(
        id=uuid5(NAMESPACE_URL, f"memeradar:lifecycle-alert:{dedupe_key}"),
        kind="AlertRequested",
        aggregate_type="token",
        aggregate_id=uuid5(NAMESPACE_URL, f"memeradar:token:{mint}"),
        occurred_at=at,
        observed_at=at,
        ingested_at=at,
        correlation_id=f"lifecycle:{mint}",
        producer=PRODUCER,
        payload={
            "type": alert_type,
            "severity": severity,
            "dedupe_key": dedupe_key,
            "payload": dict(payload),
        },
        idempotency_key=dedupe_key,
    )


def _money(value: object) -> str:
    parsed = _decimal(value)
    if parsed is None:
        return "UNKNOWN"
    if parsed >= 1_000_000:
        return f"${parsed / 1_000_000:.2f}M"
    if parsed >= 1_000:
        return f"${parsed / 1_000:.1f}k"
    return f"${parsed:.2f}"


def _holder_line(concentration: HolderConcentration) -> str:
    if concentration.risk is ConcentrationRisk.UNKNOWN:
        return "Holder concentration: UNKNOWN (" + ", ".join(concentration.reason_codes) + ")"
    return (
        f"Holders ex-pool: top1 {concentration.top1_pct}% / top10 {concentration.top10_pct}%"
        f" [{concentration.risk.value}]"
    )


def revival_alert_lines(
    state: MintLifecycle,
    assessment: RevivalAssessment,
    safety: Mapping[str, object],
    concentration: HolderConcentration | None = None,
) -> list[str]:
    metrics = assessment.metrics
    age_hours = Decimal(str(metrics.get("age_seconds", 0))) / 3600
    lines = [
        f"Second wave on {'PumpSwap/AMM' if metrics.get('graduated') else 'bonding curve'}",
        f"Age since launch: {age_hours:.1f}h",
        f"Market cap: {_money(metrics.get('market_cap_usd'))}"
        f" (observed peak {_money(metrics.get('peak_market_cap_usd'))})",
        f"Liquidity: {_money(metrics.get('liquidity_usd'))}"
        f" [{metrics.get('liquidity_basis')}]",
        f"5m volume: {_money(metrics.get('volume_m5_usd'))},"
        f" acceleration x{metrics.get('volume_acceleration')}",
        f"5m buys/sells: {metrics.get('buys_m5')}/{metrics.get('sells_m5')}",
        f"Price 5m/1h: {metrics.get('price_change_m5_pct')}% / "
        f"{metrics.get('price_change_h1_pct')}%",
        f"Sustained: {metrics.get('sustained_samples')} samples over "
        f"{metrics.get('sustained_seconds')}s",
        f"Launch safety: {safety.get('safety_status')}"
        f" (mint/freeze authority revoked)",
        (
            _holder_line(concentration)
            if concentration is not None
            else "Holder concentration: UNKNOWN (no holder source configured)"
        ),
        "Unknown: insider distribution, deployer exits",
        f"https://dexscreener.com/solana/{state.mint}",
    ]
    return lines


def exit_alert_lines(track: _PositionTrack, advice: ExitAdvice) -> list[str]:
    fraction = advice.sell_fraction_of_remaining
    action = advice.action.value
    lines = [
        f"Action: {action}"
        + (f" {Decimal(fraction) * 100:.0f}% of what you still hold" if fraction else ""),
        f"Mark multiple: x{advice.mark_multiple} (peak x{advice.peak_multiple})",
        f"Reason: {', '.join(advice.reason_codes)}",
        f"Entry: {track.entry_price_usd} USD [{advice.entry_semantics.value}]",
        "Multiple uses market reference price; your fill will be worse after slippage",
        f"https://dexscreener.com/solana/{track.mint}",
    ]
    return lines


class LifecycleWatchWorker:
    def __init__(
        self,
        engine: AsyncEngine,
        market: LifecycleMarketPort,
        *,
        policy: LifecyclePolicy | None = None,
        exit_policy: ExitPolicy | None = None,
        clock: Clock | None = None,
        max_requests_per_cycle: int = 20,
        holders: HolderSnapshotPort | None = None,
    ) -> None:
        if not 1 <= max_requests_per_cycle <= 200:
            raise ValueError("max_requests_per_cycle must be between 1 and 200")
        self.engine = engine
        self.market = market
        self.holders = holders
        self.policy = policy or LifecyclePolicy()
        self.exit_policy = exit_policy or ExitPolicy()
        self.clock = clock or (lambda: datetime.now(UTC))
        self.max_requests = max_requests_per_cycle
        self.states: dict[str, MintLifecycle] = {}
        self.positions: dict[str, _PositionTrack] = {}
        self._launch_cursor: datetime | None = None
        self._recorded_outcomes: set[str] = set()
        self._bootstrapped = False
        self._restored_fired: dict[str, set[str]] = {}
        self._factory = async_sessionmaker(engine, expire_on_commit=False)

    # ------------------------------------------------------------------ loading
    async def _bootstrap(self, now: datetime) -> None:
        since = now - self.policy.horizon - timedelta(hours=1)
        async with self._factory() as session:
            rows = await session.scalars(
                select(ObservationRow.source_id).where(
                    ObservationRow.kind == OUTCOME_KIND,
                    ObservationRow.observed_at >= since,
                )
            )
            self._recorded_outcomes = set(rows.all())
            marks = await session.scalars(
                select(ObservationRow).where(ObservationRow.kind == EXIT_ADVICE_KIND)
            )
            fired: dict[str, set[str]] = {}
            for row in marks.all():
                payload = row.normalized_payload
                position_id = payload.get("position_id")
                key = payload.get("advice_key")
                if (
                    isinstance(position_id, str)
                    and isinstance(key, str)
                    and key not in _REARMABLE_KEYS
                ):
                    fired.setdefault(position_id, set()).add(key)
            self._restored_fired = fired
        self._bootstrapped = True

    async def _load_launches(self, now: datetime) -> int:
        since = now - self.policy.horizon
        event_type = ObservationRow.normalized_payload["event_type"].as_string()
        query = select(ObservationRow).where(
            ObservationRow.kind == "chain.event",
            ObservationRow.program_id == PUMP_FUN_PROGRAM_ID,
            ObservationRow.occurred_at >= since,
            or_(event_type.is_(None), event_type != "trade_event"),
        )
        if self._launch_cursor is not None:
            query = query.where(ObservationRow.ingested_at > self._launch_cursor)
        query = query.order_by(ObservationRow.ingested_at).limit(5000)
        added = 0
        async with self._factory() as session:
            rows = list((await session.scalars(query)).all())
        for row in rows:
            ingested = _utc(row.ingested_at)
            if self._launch_cursor is None or ingested > self._launch_cursor:
                self._launch_cursor = ingested
            payload = row.normalized_payload
            name = str(payload.get("instruction_type", row.event_type or "")).lower()
            mint = _payload_mint(payload)
            if mint is None:
                continue
            occurred = _utc(row.occurred_at or row.observed_at)
            if name in _LAUNCH_NAMES and mint not in self.states:
                state = MintLifecycle(mint=mint, discovered_at=occurred)
                state.symbol = payload.get("symbol") if isinstance(
                    payload.get("symbol"), str
                ) else None
                for label, _duration in self.policy.outcome_horizons:
                    if f"lifecycle:outcome:{mint}:{label}" in self._recorded_outcomes:
                        state.outcomes_recorded.add(label)
                self.states[mint] = state
                added += 1
            elif name == "migrate" and mint in self.states:
                record_migration(self.states[mint], occurred)
        return added

    async def _load_positions(self) -> None:
        async with self._factory() as session:
            rows = list(
                (
                    await session.scalars(
                        select(ObservationRow)
                        .where(ObservationRow.kind == MANUAL_POSITION_KIND)
                        .order_by(ObservationRow.observed_at, ObservationRow.id)
                    )
                ).all()
            )
        open_ids: set[str] = set()
        for row in rows:
            payload = row.normalized_payload
            position_id = payload.get("position_id")
            mint = _payload_mint(payload)
            if not isinstance(position_id, str) or mint is None:
                continue
            event = payload.get("event")
            if event == "CLOSE":
                open_ids.discard(position_id)
                self.positions.pop(position_id, None)
                continue
            if event == "ENTRY_REFERENCED":
                track = self.positions.get(position_id)
                price = _decimal(payload.get("entry_price_usd"))
                if track is not None and track.entry_price_usd is None and price:
                    track.entry_price_usd = price
                    track.position = self._position(
                        track, EntryPriceSemantics.MARKET_REFERENCE_AT_REGISTRATION
                    )
                continue
            if event != "OPEN":
                continue
            open_ids.add(position_id)
            if position_id in self.positions:
                continue
            opened_at = _utc(row.occurred_at or row.observed_at)
            track = _PositionTrack(
                position=None,
                mint=mint,
                position_id=position_id,
                opened_at=opened_at,
                size_usd=_decimal(payload.get("size_usd")) or Decimal("50"),
                symbol=payload.get("symbol") if isinstance(payload.get("symbol"), str) else None,
                entry_price_usd=_decimal(payload.get("entry_price_usd")),
            )
            track.advisor.fired |= self._restored_fired.get(position_id, set())
            if track.entry_price_usd is not None and track.entry_price_usd > 0:
                track.position = self._position(track, EntryPriceSemantics.OPERATOR_EXECUTED)
            self.positions[position_id] = track
        for stale in set(self.positions) - open_ids:
            self.positions.pop(stale, None)

    @staticmethod
    def _position(track: _PositionTrack, semantics: EntryPriceSemantics) -> ManualPosition:
        assert track.entry_price_usd is not None
        return ManualPosition(
            position_id=track.position_id,
            mint=track.mint,
            opened_at=track.opened_at,
            size_usd=track.size_usd,
            entry_price_usd=track.entry_price_usd,
            entry_semantics=semantics,
            symbol=track.symbol,
        )

    async def _launch_safety(self, mint: str) -> Mapping[str, object] | None:
        """Latest evaluated launch safety. Revoked authorities are permanent."""

        async with self._factory() as session:
            rows = list(
                (
                    await session.scalars(
                        select(ObservationRow)
                        .where(
                            ObservationRow.kind == "early.stage_snapshot",
                            ObservationRow.normalized_payload["mint"].as_string() == mint,
                        )
                        .order_by(ObservationRow.observed_at.desc())
                        .limit(50)
                    )
                ).all()
            )
        evaluated = [row.normalized_payload for row in rows
                     if row.normalized_payload.get("safety_status") is not None]
        if not evaluated:
            return None
        if any(payload.get("hard_blocks") for payload in evaluated):
            return {"safety_status": "BLOCK", "hard_blocks": True}
        return evaluated[0]

    # ------------------------------------------------------------------ cycle
    def _due(self, now: datetime) -> list[str]:
        due: list[str] = []
        for track in self.positions.values():
            if track.last_polled_at is None or now - track.last_polled_at >= _POSITION_POLL:
                due.append(track.mint)
        priority = {Tier.HOT: 0, Tier.WARM: 1, Tier.COLD: 2, Tier.RETIRED: 3}
        ready = sorted(
            (
                state
                for state in self.states.values()
                if state.next_due_at is not None and state.next_due_at <= now
            ),
            key=lambda state: (priority[state.tier], state.next_due_at, state.mint),
        )
        due.extend(state.mint for state in ready)
        return list(dict.fromkeys(due))[: self.max_requests * BATCH_SIZE]

    async def collect_once(self, *, now: datetime | None = None) -> CycleReport:
        checked_at = now or self.clock()
        if not self._bootstrapped:
            await self._bootstrap(checked_at)
        await self._load_launches(checked_at)
        await self._load_positions()
        observations: list[Observation] = []
        events: list[EventEnvelope] = []
        counts: Counter[str] = Counter()
        rate_limited = False

        due = self._due(checked_at)
        for start in range(0, len(due), BATCH_SIZE):
            batch = due[start : start + BATCH_SIZE]
            context = ProviderRequestContext(
                correlation_id=f"lifecycle:{int(checked_at.timestamp())}:{start}",
                requested_at=checked_at,
                deadline_at=checked_at + timedelta(seconds=15),
            )
            try:
                samples = await self.market.lifecycle_samples(batch, context=context)
            except ProviderRateLimitedError:
                rate_limited = True
                break
            except (ProviderError, ValueError) as error:
                LOGGER.warning(
                    "lifecycle_batch_failed", extra={"error_class": type(error).__name__}
                )
                continue
            counts["requests"] += 1
            for mint in batch:
                sample = samples.get(mint)
                counts["polled"] += 1
                if sample is None:
                    counts["missing"] += 1
                else:
                    counts["samples"] += 1
                await self._handle_mint(mint, sample, checked_at, observations, events, counts)

        for mint, state in list(self.states.items()):
            if state.tier is Tier.RETIRED or (
                state.next_due_at is not None
                and state.age(checked_at) > self.policy.horizon
            ):
                observations.extend(
                    self._outcome_rows(finalize(state, self.policy, checked_at), checked_at)
                )
                counts["retired"] += 1
                del self.states[mint]
        counts["outcomes"] += sum(1 for o in observations if o.kind == OUTCOME_KIND)
        await self._persist(observations, events)
        tiers = Counter(state.tier.value for state in self.states.values())
        report = CycleReport(
            tracked=len(self.states),
            polled=counts["polled"],
            requests=counts["requests"],
            samples=counts["samples"],
            missing=counts["missing"],
            revivals=counts["revivals"],
            alerts=counts["alerts"],
            advisories=counts["advisories"],
            outcomes=counts["outcomes"],
            retired=counts["retired"],
            rate_limited=rate_limited,
            tiers=dict(tiers),
        )
        LOGGER.info(
            "lifecycle_watch_cycle",
            extra={
                "tracked": report.tracked,
                "polled": report.polled,
                "requests": report.requests,
                "missing": report.missing,
                "revivals": report.revivals,
                "alerts": report.alerts,
                "outcomes": report.outcomes,
                "rate_limited": report.rate_limited,
                "tiers": dict(report.tiers),
            },
        )
        return report

    async def _handle_mint(
        self,
        mint: str,
        sample: LifecycleSample | None,
        now: datetime,
        observations: list[Observation],
        events: list[EventEnvelope],
        counts: Counter[str],
    ) -> None:
        for track in [t for t in self.positions.values() if t.mint == mint]:
            track.last_polled_at = now
            await self._handle_position(track, sample, now, observations, events, counts)
        state = self.states.get(mint)
        if state is None:
            return
        if sample is None:
            record_missing(state, self.policy, now)
        else:
            observations.extend(
                self._outcome_rows(apply_sample(state, sample, self.policy), now)
            )
            assessment = assess_revival(state, sample, self.policy)
            if assessment.signal in {RevivalSignal.REVIVAL, RevivalSignal.PENDING}:
                await self._handle_revival(state, assessment, now, observations, events, counts)
        schedule_next(state, self.policy, now)

    async def _handle_revival(
        self,
        state: MintLifecycle,
        assessment: RevivalAssessment,
        now: datetime,
        observations: list[Observation],
        events: list[EventEnvelope],
        counts: Counter[str],
    ) -> None:
        payload = assessment.to_payload()
        reasons = list(assessment.reason_codes)
        if assessment.signal is RevivalSignal.REVIVAL:
            counts["revivals"] += 1
        alert = assessment.should_alert
        safety: Mapping[str, object] | None = None
        if alert:
            safety = await self._launch_safety(state.mint)
            safe = bool(
                safety
                and safety.get("safety_status") in {"PASS", "CAUTION"}
                and safety.get("mint_authority_safe") is True
                and safety.get("freeze_authority_safe") is True
            )
            payload["launch_safety"] = (
                "UNKNOWN" if safety is None else str(safety.get("safety_status"))
            )
            if not safe:
                alert = False
                reasons.append(
                    "LIFECYCLE_LAUNCH_SAFETY_UNKNOWN"
                    if safety is None
                    else "LIFECYCLE_LAUNCH_SAFETY_NOT_PASSED"
                )
        concentration: HolderConcentration | None = None
        if alert:
            concentration = await self._concentration(state, now)
            payload["holder_concentration"] = concentration.to_payload()
            if concentration.risk is ConcentrationRisk.HIGH:
                alert = False
                reasons.append("LIFECYCLE_HOLDER_CONCENTRATION_HIGH")
        payload["reason_codes"] = reasons
        payload["alert_requested"] = alert
        observations.append(
            _observation(
                kind=SIGNAL_KIND,
                source_id=f"lifecycle:signal:{state.mint}:{int(now.timestamp())}",
                at=now,
                payload=payload,
            )
        )
        if alert and safety is not None:
            mark_alerted(state, now)
            bucket = int(now.timestamp() // self.policy.alert_cooldown.total_seconds())
            events.append(
                _alert_event(
                    alert_type="REVIVAL_WATCH",
                    severity="WARNING",
                    dedupe_key=f"lifecycle:revival:{state.mint}:{bucket}",
                    mint=state.mint,
                    at=now,
                    payload={
                        "mint": state.mint,
                        "symbol": state.symbol,
                        "state": "REVIVAL_WATCH",
                        "advisory_lines": revival_alert_lines(
                            state, assessment, safety, concentration
                        ),
                        "reason_codes": reasons,
                        "config_hash": assessment.config_hash,
                    },
                )
            )
            counts["alerts"] += 1

    async def _concentration(self, state: MintLifecycle, now: datetime) -> HolderConcentration:
        """Holder evidence for an alert candidate; any failure is UNKNOWN."""

        if self.holders is None:
            return unknown_concentration(state.mint, "HOLDER_SOURCE_NOT_CONFIGURED")
        context = ProviderRequestContext(
            correlation_id=f"lifecycle-holders:{state.mint}",
            requested_at=now,
            deadline_at=now + timedelta(seconds=10),
        )
        try:
            snapshot = await self.holders.fetch_holder_snapshot(state.mint, context=context)
        except (ProviderError, ValueError) as error:
            LOGGER.info(
                "lifecycle_holder_snapshot_unavailable",
                extra={"error_class": type(error).__name__},
            )
            return unknown_concentration(state.mint, "HOLDER_SNAPSHOT_UNAVAILABLE")
        pool = None if state.last_sample is None else state.last_sample.pair_address
        return assess_concentration(snapshot, liquidity_owners=() if pool is None else (pool,))

    async def _handle_position(
        self,
        track: _PositionTrack,
        sample: LifecycleSample | None,
        now: datetime,
        observations: list[Observation],
        events: list[EventEnvelope],
        counts: Counter[str],
    ) -> None:
        if track.position is None:
            if sample is None or sample.price_usd is None or sample.price_usd <= 0:
                return
            track.entry_price_usd = sample.price_usd
            track.position = self._position(
                track, EntryPriceSemantics.MARKET_REFERENCE_AT_REGISTRATION
            )
            observations.append(
                _observation(
                    kind=MANUAL_POSITION_KIND,
                    source_id=f"manual:position:{track.position_id}:entry-referenced",
                    at=now,
                    payload={
                        "event": "ENTRY_REFERENCED",
                        "position_id": track.position_id,
                        "mint": track.mint,
                        "entry_price_usd": str(sample.price_usd),
                        "entry_price_semantics": "MARKET_REFERENCE_AT_REGISTRATION",
                        "sample_source_id": sample.source_id,
                    },
                )
            )
        if sample is not None and sample.price_usd is not None:
            observations.append(
                _observation(
                    kind=POSITION_MARK_KIND,
                    source_id=f"manual:mark:{track.position_id}:{int(now.timestamp())}",
                    at=now,
                    occurred_at=sample.observed_at,
                    payload={
                        "position_id": track.position_id,
                        "mint": track.mint,
                        **sample.to_payload(),
                    },
                )
            )
        for advice in advise(
            track.position, track.advisor, sample, now=now, policy=self.exit_policy
        ):
            counts["advisories"] += 1
            payload = advice.to_payload()
            delivery_key = f"manual:exit:{track.position_id}:{advice.key}"
            if advice.key in _REARMABLE_KEYS:
                delivery_key += f":{int(now.timestamp() // 3600)}"
            observations.append(
                _observation(
                    kind=EXIT_ADVICE_KIND,
                    source_id=delivery_key,
                    at=now,
                    payload=payload,
                )
            )
            events.append(
                _alert_event(
                    alert_type="MANUAL_EXIT",
                    severity=advice.severity,
                    dedupe_key=delivery_key,
                    mint=track.mint,
                    at=now,
                    payload={
                        "mint": track.mint,
                        "symbol": track.symbol,
                        "state": advice.action.value,
                        "action": advice.action.value,
                        "position_id": None,
                        "advisory_lines": exit_alert_lines(track, advice),
                        "reason_codes": list(advice.reason_codes),
                    },
                )
            )
            counts["alerts"] += 1

    def _outcome_rows(
        self, outcomes: Sequence[LifecycleOutcome], now: datetime
    ) -> list[Observation]:
        rows: list[Observation] = []
        for outcome in outcomes:
            if outcome.sample_count == 0:
                continue  # never indexed: no evidence, not a zero outcome
            source_id = f"lifecycle:outcome:{outcome.mint}:{outcome.horizon}"
            if source_id in self._recorded_outcomes:
                continue
            self._recorded_outcomes.add(source_id)
            rows.append(
                _observation(
                    kind=OUTCOME_KIND,
                    source_id=source_id,
                    at=now,
                    occurred_at=outcome.horizon_end,
                    payload=outcome.to_payload(),
                    # Sampling resolution travels in the payload ("COARSE"/"FINE").
                    quality=QualityState.FRESH,
                )
            )
        return rows

    async def _persist(
        self, observations: Sequence[Observation], events: Sequence[EventEnvelope]
    ) -> None:
        if not observations and not events:
            return
        async with SqlAlchemyUnitOfWork(self.engine) as unit_of_work:
            for observation in observations:
                await unit_of_work.observations.add(observation)
            for event in events:
                await unit_of_work.outbox.enqueue(event, side_effect_kind="notification")
            await unit_of_work.commit()

    async def run(
        self,
        stop_event: asyncio.Event,
        *,
        poll_interval_seconds: float = 10.0,
        sleeper: Sleep = asyncio.sleep,
    ) -> None:
        while not stop_event.is_set():
            try:
                await self.collect_once()
            except Exception as error:  # noqa: BLE001 - research loop must not stop ingestion.
                LOGGER.warning(
                    "lifecycle_watch_cycle_failed",
                    extra={"error_class": type(error).__name__},
                )
            if not stop_event.is_set():
                await sleeper(poll_interval_seconds)


__all__ = [
    "EXIT_ADVICE_KIND",
    "MANUAL_POSITION_KIND",
    "OUTCOME_KIND",
    "SIGNAL_KIND",
    "CycleReport",
    "LifecycleMarketPort",
    "LifecycleWatchWorker",
]
