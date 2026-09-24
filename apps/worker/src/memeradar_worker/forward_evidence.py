"""Single-loop Pump.fun forward evidence collection.

This is a research projection over the existing canonical launch observations.
It does not consume the chain stream, score candidates, or authorize trades.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from memeradar_application.creator_graph import (
    CreatorOutcomeGraph,
    CreatorReputationAnalyzer,
    EdgeKind,
    GraphEdge,
    GraphNode,
    NodeKind,
)
from memeradar_application.early_failure_analysis import (
    FalsePositiveAnalyzer,
    MissedWinnerAnalyzer,
)
from memeradar_application.early_replay import (
    EXTREME_OUTCOME_HORIZONS,
    OUTCOME_LABEL_VERSION,
    OUTCOME_METHODOLOGY_VERSION,
    ExtremeWinnerOutcomeLabeler,
    ExtremeWinnerOutcomeSnapshot,
    classify_research_outcome,
)
from memeradar_application.provider_contracts import (
    MarketDataPort,
    MarketDataRequest,
    ProviderRequestContext,
)
from memeradar_application.pumpfun_forward import (
    DEX_FIRST_OBSERVATION_OFFSETS_SECONDS,
    MARKET_SNAPSHOT_OFFSETS_SECONDS,
    PUMPFUN_FORWARD_VERSION,
    dex_horizon_source_id,
    forward_observation_source_id,
    lead_seconds,
    offset_label,
    poll_is_due,
)
from memeradar_application.replay_harness import ReplayCheckpoint, ReplayEventRecord
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity
from memeradar_domain.common import ensure_utc
from memeradar_persistence import ObservationRow, SqlAlchemyUnitOfWork
from memeradar_providers.transport import ProviderError, ProviderRateLimitedError

Clock = Callable[[], datetime]
Sleep = Callable[[float], Awaitable[None]]
LOGGER = logging.getLogger(__name__)
_RESEARCH_KINDS = (
    "chain.event",
    "early.stage_snapshot",
    "market.market_snapshot",
    "research.dex_forward",
    "research.outcome",
    "research.creator_history",
    "research.missed_winner",
    "research.false_positive",
    "research.funnel_transition",
    "research.early_reevaluation",
)
_MINT_KEYS = ("mint", "mint_address", "address")
_OUTCOME_TARGETS = (2, 5, 10, 20, 50, 100)
_FORWARD_OUTCOME_HORIZONS = (
    ("1m", timedelta(minutes=1)),
    ("3m", timedelta(minutes=3)),
    ("5m", timedelta(minutes=5)),
    ("15m", timedelta(minutes=15)),
    ("30m", timedelta(minutes=30)),
    ("1h", timedelta(hours=1)),
    ("3h", timedelta(hours=3)),
    ("6h", timedelta(hours=6)),
    ("24h", timedelta(hours=24)),
    *EXTREME_OUTCOME_HORIZONS[3:],
)
_FORWARD_NAMESPACE = "https://memeradar.local/pumpfun-forward/"
_MAX_LAUNCHES_PER_CYCLE = 16


def _payload(row: ObservationRow | Mapping[str, object]) -> Mapping[str, object]:
    if isinstance(row, ObservationRow):
        return row.normalized_payload
    value = row.get("normalized_payload", row.get("payload"))
    return value if isinstance(value, Mapping) else row


def _row_value(row: ObservationRow | Mapping[str, object], name: str) -> object:
    value = _payload(row).get(name)
    if value is not None:
        return value
    return row.get(name) if isinstance(row, Mapping) else None


def _mint(row: ObservationRow | Mapping[str, object]) -> str | None:
    for key in _MINT_KEYS:
        value = _row_value(row, key)
        if isinstance(value, str) and value:
            return value
    return None


def _datetime(value: object, fallback: datetime | None = None) -> datetime | None:
    if isinstance(value, datetime):
        return ensure_utc(value, "timestamp")
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return fallback
        return ensure_utc(parsed, "timestamp")
    return fallback


def _row_time(row: ObservationRow) -> datetime:
    return ensure_utc(row.occurred_at or row.observed_at, "row_time")


def _source_id(row: ObservationRow) -> str:
    return f"{row.provider}:{row.kind}:{row.source_id}"


def _token_id(record: LaunchRecord) -> UUID:
    return record.row.token_id or uuid5(NAMESPACE_URL, f"{_FORWARD_NAMESPACE}token:{record.mint}")


def _candidate_id(record: LaunchRecord) -> UUID:
    return record.row.candidate_id or uuid5(
        NAMESPACE_URL,
        f"{_FORWARD_NAMESPACE}candidate:{record.mint}",
    )


def _json_decimal(value: object) -> str | None:
    if value is None:
        return None
    try:
        return str(Decimal(str(value)))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class LaunchRecord:
    row: ObservationRow
    mint: str
    discovered_at: datetime
    payload: Mapping[str, object]


def is_pumpfun_launch(row: ObservationRow | Mapping[str, object]) -> bool:
    """Recognize only canonical Pump.fun create/create_v2 launch events."""

    payload = _payload(row)
    event_type = str(
        payload.get(
            "instruction_type",
            payload.get("event_type", row.event_type if isinstance(row, ObservationRow) else ""),
        )
    ).lower()
    protocol_type = str(payload.get("protocol_event_type", "")).lower()
    return event_type in {"create", "create_v2"} or protocol_type == "launch"


def _launch_records(rows: Sequence[ObservationRow]) -> tuple[LaunchRecord, ...]:
    discovered_by_mint: dict[str, datetime] = {}
    for row in rows:
        if row.kind != "early.stage_snapshot":
            continue
        payload = row.normalized_payload
        if str(payload.get("state", payload.get("stage", ""))).upper() != "DISCOVERED":
            continue
        mint = _mint(row)
        discovered = _datetime(payload.get("discovered_at", payload.get("first_seen_at")))
        if mint is not None and discovered is not None:
            previous_discovered = discovered_by_mint.get(mint)
            discovered_by_mint[mint] = (
                discovered if previous_discovered is None else min(previous_discovered, discovered)
            )

    records: dict[str, LaunchRecord] = {}
    for row in rows:
        if row.kind != "chain.event" or not is_pumpfun_launch(row):
            continue
        mint = _mint(row)
        if mint is None:
            continue
        discovered = discovered_by_mint.get(mint, ensure_utc(row.observed_at, "observed_at"))
        current = LaunchRecord(row, mint, discovered, dict(row.normalized_payload))
        previous_record = records.get(mint)
        if previous_record is None or _row_time(row) < _row_time(previous_record.row):
            records[mint] = current
    return tuple(sorted(records.values(), key=lambda value: (value.discovered_at, value.mint)))


def _research_observation(
    *,
    kind: str,
    source_id: str,
    query_at: datetime,
    payload: Mapping[str, object],
    quality_state: QualityState,
    record: LaunchRecord,
    occurred_at: datetime | None = None,
) -> Observation:
    return Observation(
        id=uuid5(NAMESPACE_URL, f"{_FORWARD_NAMESPACE}{kind}:{source_id}"),
        kind=kind,
        provenance=Provenance(
            provider="memeradar.forward-research",
            source_id=source_id,
            observed_at=query_at,
            parser_version=PUMPFUN_FORWARD_VERSION,
        ),
        occurred_at=occurred_at or query_at,
        observed_at=query_at,
        ingested_at=query_at,
        quality_state=quality_state,
        normalized_payload=dict(payload),
        candidate_id=record.row.candidate_id,
        token_id=record.row.token_id,
    )


def unknown_market_snapshot(
    record: LaunchRecord,
    *,
    query_at: datetime,
    offset_seconds: int,
) -> Observation:
    """Persist an explicit no-pair/error snapshot without inventing market data."""

    source_id = f"pumpfun-forward:market:{record.mint}:{offset_seconds}"
    return _research_observation(
        kind="market.market_snapshot",
        source_id=source_id,
        query_at=query_at,
        quality_state=QualityState.UNKNOWN,
        record=record,
        payload={
            "chain": "solana",
            "mint_address": record.mint,
            "mint": record.mint,
            "pair_found": False,
            "pair_address": None,
            "pair_created_at": None,
            "price_usd": None,
            "liquidity_usd": None,
            "fdv": None,
            "market_cap": None,
            "volume_24h_usd": None,
            "transactions": None,
            "provider_freshness": QualityState.UNKNOWN.value,
            "snapshot_offset_seconds": offset_seconds,
            "snapshot_label": offset_label(offset_seconds),
            "dex_query_at": query_at.isoformat(),
            "collection_mode": "LIVE_SHADOW",
        },
    )


def _market_source_id(mint: str, offset_seconds: int) -> str:
    return f"pumpfun-forward:market:{mint}:{offset_seconds}"


def _forward_payload(
    record: LaunchRecord,
    *,
    query_at: datetime,
    offset_seconds: int,
    market: Observation | None,
    error: BaseException | None,
    first_observed_at: datetime | None,
) -> dict[str, object]:
    market_payload = {} if market is None else dict(market.normalized_payload)
    pair_found = market is not None and market_payload.get("pair_address") is not None
    if pair_found:
        poll_status = "PAIR_FOUND"
    elif isinstance(error, ProviderRateLimitedError):
        poll_status = "RATE_LIMITED"
    elif error is not None:
        poll_status = "REQUEST_FAILED"
    else:
        poll_status = "NO_PAIR_YET"
    first = first_observed_at or (query_at if pair_found else None)
    payload: dict[str, object] = {
        "mint": record.mint,
        "mint_address": record.mint,
        "signature": record.payload.get("signature"),
        "slot": record.payload.get("slot"),
        "instruction_type": record.payload.get(
            "instruction_type", record.payload.get("event_type")
        ),
        "creator": record.payload.get("creator"),
        "user": record.payload.get("user"),
        "name": record.payload.get("name"),
        "symbol": record.payload.get("symbol"),
        "uri": record.payload.get("uri"),
        "is_mayhem_mode": record.payload.get("is_mayhem_mode"),
        "quote_mint_semantics": record.payload.get("quote_mint_semantics"),
        "is_holder_reward": record.payload.get("is_holder_reward"),
        "memeradar_discovered_at": record.discovered_at.isoformat(),
        "dex_query_at": query_at.isoformat(),
        "dex_query_offset_seconds": offset_seconds,
        "dex_query_label": offset_label(offset_seconds),
        "pair_found": pair_found,
        "poll_status": poll_status,
        "poll_terminal": False,
        "pair_address": market_payload.get("pair_address"),
        "pair_created_at": market_payload.get("pair_created_at"),
        "price": market_payload.get("price_usd", market_payload.get("price")),
        "price_usd": market_payload.get("price_usd"),
        "liquidity": market_payload.get("liquidity_usd", market_payload.get("liquidity")),
        "liquidity_usd": market_payload.get("liquidity_usd"),
        "fdv": market_payload.get("fdv"),
        "market_cap": market_payload.get("market_cap"),
        "volume": market_payload.get("volume_24h_usd", market_payload.get("volume_24h")),
        "volume_24h_usd": market_payload.get("volume_24h_usd"),
        "transactions": market_payload.get("transactions"),
        "provider_freshness": (
            QualityState.UNKNOWN.value if market is None else market.quality_state.value
        ),
        "dex_api_first_observed_at": None if first is None else first.isoformat(),
        "memeradar_to_dex_api_lead_seconds": lead_seconds(record.discovered_at, first),
        "collection_mode": "LIVE_SHADOW",
        "research_version": PUMPFUN_FORWARD_VERSION,
    }
    if error is not None:
        payload["error_class"] = type(error).__name__
        payload["error_message"] = str(error)[:256]
    return payload


def _market_observation(
    market: Observation,
    record: LaunchRecord,
    *,
    query_at: datetime,
    offset_seconds: int,
) -> Observation:
    source_id = _market_source_id(record.mint, offset_seconds)
    payload = dict(market.normalized_payload)
    payload.update(
        {
            "mint": record.mint,
            "mint_address": record.mint,
            "dex_query_at": query_at.isoformat(),
            "snapshot_offset_seconds": offset_seconds,
            "snapshot_label": offset_label(offset_seconds),
            "collection_mode": "LIVE_SHADOW",
            "research_version": PUMPFUN_FORWARD_VERSION,
            "provider_freshness": market.quality_state.value,
        }
    )
    return replace(
        market,
        id=uuid5(NAMESPACE_URL, f"{_FORWARD_NAMESPACE}market:{record.mint}:{offset_seconds}"),
        provenance=replace(
            market.provenance,
            source_id=source_id,
            observed_at=query_at,
            parser_version=PUMPFUN_FORWARD_VERSION,
        ),
        occurred_at=query_at,
        observed_at=query_at,
        ingested_at=query_at,
        normalized_payload=payload,
        candidate_id=record.row.candidate_id,
        token_id=record.row.token_id,
    )


async def _load_rows(engine: AsyncEngine) -> list[ObservationRow]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        result = await session.scalars(
            select(ObservationRow)
            .where(ObservationRow.kind.in_(_RESEARCH_KINDS))
            .order_by(ObservationRow.occurred_at, ObservationRow.id)
        )
        return list(result.all())


def _existing_sources(rows: Sequence[ObservationRow]) -> set[str]:
    return {row.source_id for row in rows}


def _next_due_offset(
    discovered_at: datetime,
    offsets: Sequence[int],
    existing: set[str],
    mint: str,
    source_kind: str,
    now: datetime,
) -> int | None:
    for offset in offsets:
        source_id = (
            forward_observation_source_id(mint, offset)
            if source_kind == "dex"
            else _market_source_id(mint, offset)
        )
        if source_id not in existing and poll_is_due(
            discovered_at, offset, now
        ):
            return offset
    return None


def _pair_first(rows: Sequence[ObservationRow], mint: str) -> datetime | None:
    values = [
        _datetime(row.normalized_payload.get("dex_api_first_observed_at"))
        for row in rows
        if row.kind == "research.dex_forward"
        and _mint(row) == mint
        and row.normalized_payload.get("pair_found") is True
    ]
    valid = [value for value in values if value is not None]
    return min(valid) if valid else None


def _dex_horizon_exhausted(
    discovered_at: datetime,
    existing: set[str],
    mint: str,
    now: datetime,
) -> bool:
    due_offsets = tuple(
        offset
        for offset in DEX_FIRST_OBSERVATION_OFFSETS_SECONDS
        if poll_is_due(discovered_at, offset, now)
    )
    return bool(due_offsets) and all(
        forward_observation_source_id(mint, offset) in existing for offset in due_offsets
    )


async def _query_market(
    market: MarketDataPort,
    record: LaunchRecord,
    *,
    query_at: datetime,
) -> tuple[Observation | None, BaseException | None]:
    token = TokenIdentity(mint_address=record.mint, id=_token_id(record))
    register = getattr(market, "register_token", None)
    if callable(register):
        register(token)
    context = ProviderRequestContext(
        correlation_id=f"pumpfun-forward:{record.mint}:{query_at.timestamp()}",
        requested_at=query_at,
        deadline_at=query_at + timedelta(seconds=15),
    )
    try:
        observations = await market.snapshot(
            MarketDataRequest(context=context, token_ids=(token.id,))
        )
    except (ProviderError, ValueError) as error:
        return None, error
    if not observations:
        return None, RuntimeError("DexScreener returned no normalized observation")
    return observations[0], None


def _creator_outcome_rows(rows: Sequence[ObservationRow]) -> dict[str, list[ObservationRow]]:
    result: dict[str, list[ObservationRow]] = {}
    for row in rows:
        if row.kind != "research.outcome":
            continue
        mint = _mint(row)
        if mint is not None:
            result.setdefault(mint, []).append(row)
    return result


async def _persist(
    engine: AsyncEngine,
    observations: Sequence[Observation],
) -> int:
    if not observations:
        return 0
    async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
        for observation in observations:
            if observation.kind == "research.outcome":
                await unit_of_work.observations.upsert_research_outcome(observation)
            else:
                await unit_of_work.observations.add(observation)
        await unit_of_work.commit()
    return len(observations)


def _creator_history_rows(
    rows: Sequence[ObservationRow],
    record: LaunchRecord,
) -> Observation | None:
    creator = record.payload.get("creator")
    if not isinstance(creator, str) or not creator:
        return None
    prior = [
        value
        for value in _launch_records(rows)
        if value.mint != record.mint
        and value.payload.get("creator") == creator
        and _row_time(value.row) < _row_time(record.row)
    ]
    outcomes = _creator_outcome_rows(rows)
    previous_winner_mints: set[str] = set()
    previous_rug_mints: set[str] = set()
    outcome_by_mint: dict[str, Mapping[str, object]] = {}
    for value in prior:
        for outcome in outcomes.get(value.mint, ()):
            payload = outcome.normalized_payload
            if payload.get("matured") is not True:
                continue
            outcome_by_mint[value.mint] = payload
            if any(payload.get(f"hit_{target}x") is True for target in (10, 20, 50, 100)):
                previous_winner_mints.add(value.mint)
            if payload.get("rug_dead_liquidity_collapse") is True:
                previous_rug_mints.add(value.mint)
    shared_funders = None
    linked_wallets = None
    for value in prior:
        for key in ("shared_funders", "linked_wallets"):
            if value.payload.get(key) is not None:
                if key == "shared_funders":
                    shared_funders = value.payload[key]
                else:
                    linked_wallets = value.payload[key]
    graph = CreatorOutcomeGraph()
    wallet_id = f"wallet:{creator}"
    graph.add_node(GraphNode(id=wallet_id, kind=NodeKind.WALLET, label=creator))
    as_of = _row_time(record.row)
    for value in prior:
        mint = value.mint
        token_id = f"token:{mint}"
        outcome_class = outcome_by_mint.get(mint, {}).get("outcome")
        if outcome_class is None:
            prior_outcome = outcome_by_mint.get(mint, {})
            if any(
                prior_outcome.get(f"hit_{target}x") is True
                for target in (10, 20, 50, 100)
            ):
                outcome_class = "WINNER"
            elif prior_outcome.get("rug_dead_liquidity_collapse") is True:
                outcome_class = "RUG_OR_LIQUIDITY_COLLAPSE"
            else:
                outcome_class = "UNKNOWN"
        graph.add_node(
            GraphNode(
                id=token_id,
                kind=NodeKind.TOKEN,
                label=mint,
                properties={"outcome": outcome_class},
            )
        )
        graph.add_edge(
            GraphEdge(
                id=f"creator-history:{creator}:{mint}",
                from_id=wallet_id,
                to_id=token_id,
                kind=EdgeKind.CREATED,
                occurred_at=_row_time(value.row),
                observed_at=value.row.observed_at,
                ingested_at=value.row.ingested_at,
                token_mint=mint,
            )
        )
    reputation = CreatorReputationAnalyzer(graph).evaluate(creator, as_of=as_of)
    source_id = f"pumpfun-creator-history:{record.mint}"
    return _research_observation(
        kind="research.creator_history",
        source_id=source_id,
        query_at=ensure_utc(record.row.ingested_at, "ingested_at"),
        occurred_at=as_of,
        quality_state=QualityState.UNKNOWN if not prior else QualityState.FRESH,
        record=record,
        payload={
            "mint": record.mint,
            "creator": creator,
            "as_of": as_of.isoformat(),
            "previous_launches": len(prior),
            "previous_rugs": len(previous_rug_mints),
            "previous_winners": len(previous_winner_mints),
            "shared_funders": shared_funders,
            "linked_wallets": linked_wallets,
            "repeated_launch_behavior": bool(prior),
            "history_state": "UNKNOWN" if not prior else "OBSERVED",
            "reputation_class": reputation.reputation_class.value,
            "winner_rate": str(reputation.winner_rate),
            "rug_rate": str(reputation.rug_rate),
            "score": str(reputation.score),
            "confidence": str(reputation.confidence),
            "reason_codes": [reason.code for reason in reputation.reason_codes],
            "collection_mode": "LIVE_SHADOW",
            "creator_graph_version": "creator-graph-v1",
        },
    )


def _funnel_transition_rows(
    rows: Sequence[ObservationRow],
    record: LaunchRecord,
    *,
    query_at: datetime,
) -> tuple[Observation, ...]:
    result: list[Observation] = []
    for row in rows:
        if row.kind != "early.stage_snapshot" or _mint(row) != record.mint:
            continue
        payload = row.normalized_payload
        state = str(payload.get("state", payload.get("stage", ""))).upper()
        if not state:
            continue
        transition_at = _datetime(payload.get("state_at"), _row_time(row)) or _row_time(row)
        source_id = f"pumpfun-funnel:{record.mint}:{state}:{transition_at.isoformat()}"
        result.append(
            _research_observation(
                kind="research.funnel_transition",
                source_id=source_id,
                query_at=query_at,
                occurred_at=transition_at,
                quality_state=QualityState(row.quality_state),
                record=record,
                payload={
                    "mint": record.mint,
                    "stage": state,
                    "state": state,
                    "transition_at": transition_at.isoformat(),
                    "token_age_seconds": payload.get("token_age_seconds"),
                    "market_cap": payload.get("market_cap"),
                    "score": payload.get("early_score"),
                    "confidence": payload.get("confidence"),
                    "safety_status": payload.get("safety_status"),
                    "reason_codes": payload.get("reason_codes", ()),
                    "scoring_version": payload.get("score_version"),
                    "collection_mode": "LIVE_SHADOW",
                    "funnel_version": PUMPFUN_FORWARD_VERSION,
                },
            )
        )
    return tuple(result)


def _observation_from_row(row: ObservationRow, *, token_id: UUID) -> Observation:
    return Observation(
        id=row.id,
        kind=row.kind,
        provenance=Provenance(
            provider=row.provider,
            source_id=row.source_id,
            observed_at=row.observed_at,
            parser_version=row.parser_version,
            raw_payload_hash=row.raw_payload_hash,
            raw_payload_ref=row.raw_payload_ref,
        ),
        occurred_at=row.occurred_at,
        observed_at=row.observed_at,
        ingested_at=row.ingested_at,
        quality_state=QualityState(row.quality_state),
        normalized_payload=row.normalized_payload,
        candidate_id=row.candidate_id,
        token_id=token_id,
    )


def _metric(payload: Mapping[str, object], *names: str) -> Decimal | None:
    for name in names:
        value = payload.get(name)
        if value is not None:
            try:
                parsed = Decimal(str(value))
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                return parsed
    for nested_name in ("values", "metrics", "snapshot", "data"):
        nested = payload.get(nested_name)
        if isinstance(nested, Mapping):
            value = _metric(nested, *names)
            if value is not None:
                return value
    return None


def _market_metrics(record: ReplayEventRecord) -> dict[str, Decimal | None]:
    payload = record.observation.normalized_payload
    return {
        "price": _metric(payload, "price_usd", "market_price", "price"),
        "liquidity": _metric(
            payload,
            "effective_executable_liquidity",
            "executable_liquidity",
            "effective_liquidity",
            "liquidity_usd",
            "liquidity",
            "pool_liquidity",
        ),
        "market_cap": _metric(
            payload,
            "market_cap_usd",
            "market_cap",
            "marketCapUsd",
            "market_capitalization",
            "fdv",
        ),
    }


def _valid_market_record(record: ReplayEventRecord) -> bool:
    if record.observation.kind != "market.market_snapshot":
        return False
    if record.observation.quality_state is not QualityState.FRESH:
        return False
    if record.observation.normalized_payload.get("pair_found") is False:
        return False
    return any(value is not None for value in _market_metrics(record).values())


def _horizon_matured(
    records: Sequence[ReplayEventRecord],
    signal_at: datetime,
    duration: timedelta,
) -> bool:
    target = signal_at + duration
    return any(_valid_market_record(record) and record.event_at >= target for record in records)


def _endpoint_record(
    records: Sequence[ReplayEventRecord],
    signal_at: datetime,
    duration: timedelta,
) -> ReplayEventRecord | None:
    end = signal_at + duration
    bounded = [
        record
        for record in records
        if _valid_market_record(record)
        and signal_at < record.event_at <= end
    ]
    if bounded:
        return max(bounded, key=lambda record: record.event_at)
    after = [
        record
        for record in records
        if _valid_market_record(record) and record.event_at > end
    ]
    return min(after, key=lambda record: record.event_at) if after else None


def _multiple_at_endpoint(
    record: ReplayEventRecord | None,
    *,
    baseline_price: Decimal | None,
    baseline_market_cap: Decimal | None,
) -> Decimal | None:
    if record is None:
        return None
    values = _market_metrics(record)
    if values["price"] is not None and baseline_price is not None and baseline_price > 0:
        return values["price"] / baseline_price
    if (
        values["market_cap"] is not None
        and baseline_market_cap is not None
        and baseline_market_cap > 0
    ):
        return values["market_cap"] / baseline_market_cap
    return None


def _initial_market_values(
    records: Sequence[ReplayEventRecord],
    signal_at: datetime,
    stage_payloads: Sequence[Mapping[str, object]],
) -> dict[str, str | None]:
    candidates = [
        record
        for record in records
        if _valid_market_record(record) and record.event_at >= signal_at
    ]
    first = min(candidates, key=lambda record: record.event_at) if candidates else None
    values = _market_metrics(first) if first is not None else {}
    stage = next(
        (
            payload
            for payload in sorted(
                stage_payloads,
                key=lambda value: str(value.get("occurred_at", value.get("discovered_at", ""))),
            )
            if str(payload.get("state", payload.get("stage", ""))).upper() == "DISCOVERED"
        ),
        {},
    )
    names = {
        "price": ("price_at_detection", "price_usd", "market_price", "price"),
        "liquidity": (
            "liquidity_at_detection",
            "effective_executable_liquidity",
            "executable_liquidity",
            "liquidity_usd",
            "liquidity",
        ),
        "market_cap": (
            "market_cap_at_detection",
            "market_cap_usd",
            "market_cap",
            "fdv",
        ),
    }
    result: dict[str, str | None] = {}
    for key, payload_names in names.items():
        metric = values.get(key)
        if metric is None:
            metric = _metric(stage, *payload_names)
        result[key] = None if metric is None else str(metric)
    return result


def _flag(payload: Mapping[str, object], *names: str) -> bool:
    for name in names:
        value = payload.get(name)
        if isinstance(value, bool):
            if value:
                return True
        elif isinstance(value, str) and value.strip().lower() in {
            "true",
            "yes",
            "1",
            "detected",
            "removed",
            "failed",
            "honeypot",
        }:
            return True
    return False


def _outcome_flags(
    records: Sequence[ReplayEventRecord],
    stage_payloads: Sequence[Mapping[str, object]],
    *,
    signal_at: datetime,
    initial_liquidity: Decimal | None,
) -> dict[str, bool]:
    payloads = [record.observation.normalized_payload for record in records] + list(stage_payloads)
    rug_detected = any(
        record.observation.kind in {"risk.rug_event", "risk.token_outcome", "security.rug"}
        for record in records
    ) or any(_flag(payload, "rug_detected", "rug", "rugged") for payload in payloads)
    honeypot = any(
        _flag(payload, "honeypot_detected", "honeypot", "is_honeypot")
        for payload in payloads
    )
    migration_completed = any(
        _flag(payload, "migration_completed", "graduated", "dex_active", "liquidity_added")
        or str(payload.get("migration_state", payload.get("lifecycle_state", ""))).upper()
        in {"COMPLETED", "GRADUATED", "DEX_ACTIVE", "LIQUIDITY_ADDED"}
        for payload in payloads
    )
    liquidities = [
        _market_metrics(record)["liquidity"]
        for record in records
        if record.event_at > signal_at and _valid_market_record(record)
    ]
    liquidity_removed = any(
        _flag(payload, "liquidity_removed", "liquidity_rug", "liquidity_collapse")
        for payload in payloads
    )
    if initial_liquidity is not None and initial_liquidity > 0:
        liquidity_removed = liquidity_removed or any(
            liquidity is not None and liquidity <= initial_liquidity * Decimal("0.10")
            for liquidity in liquidities
        )
    return {
        "rug_detected": rug_detected,
        "honeypot_detected": honeypot,
        "liquidity_removed": liquidity_removed,
        "migration_completed": migration_completed,
    }


def _stable_payload(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _outcome_payload(
    record: LaunchRecord,
    *,
    label: object,
    horizon: str,
    duration: timedelta,
    stage_payloads: Sequence[Mapping[str, object]],
    matured: bool = True,
    outcome_label: str = "NEUTRAL",
    initial_values: Mapping[str, object] | None = None,
    outcome_series: Mapping[str, Mapping[str, object]] | None = None,
    flags: Mapping[str, bool] | None = None,
    provider_provenance: Sequence[str] = (),
) -> dict[str, object]:
    snapshot = label

    def get(name: str, default: object = None) -> object:
        return getattr(snapshot, name, default)

    initial = dict(initial_values or {})
    series = outcome_series or {}
    outcome_flags = dict(flags or {})
    current_series = dict(series.get(horizon, {}))
    states = {
        str(value.get("state", value.get("stage", ""))).upper()
        for value in stage_payloads
        if value.get("state", value.get("stage")) is not None
    }
    raw_reason_codes = get("reason_codes", ())
    reason_codes = (
        [getattr(reason, "code", str(reason)) for reason in raw_reason_codes]
        if isinstance(raw_reason_codes, Sequence)
        and not isinstance(raw_reason_codes, str | bytes | bytearray)
        else []
    )
    raw_evidence_refs = get("evidence_refs", ())
    evidence_refs = (
        tuple(str(value) for value in raw_evidence_refs)
        if isinstance(raw_evidence_refs, Sequence)
        and not isinstance(raw_evidence_refs, str | bytes | bytearray)
        else ()
    )
    executable_multiple = get("executable_multiple")
    missed_targets = [
        f"{target}X"
        for target in _OUTCOME_TARGETS[2:]
        if getattr(snapshot, f"hit_{target}x", False) and "EARLY_WATCH" not in states
    ]
    fast_safety_rejected = any(
        str(value.get("state", "")).upper() == "RISK_REJECTED"
        or str(value.get("safety_status", "")).upper() in {"BLOCK", "UNKNOWN"}
        for value in stage_payloads
    )
    return {
        "mint": record.mint,
        "mint_address": record.mint,
        "signature": record.payload.get("signature"),
        "slot": record.payload.get("slot"),
        "instruction_type": record.payload.get(
            "instruction_type", record.payload.get("event_type")
        ),
        "creator": record.payload.get("creator"),
        "user": record.payload.get("user"),
        "name": record.payload.get("name"),
        "symbol": record.payload.get("symbol"),
        "horizon": horizon,
        "horizon_seconds": int(duration.total_seconds()),
        "signal_at": record.discovered_at.isoformat(),
        "matured": matured,
        "outcome_status": "MATURED" if matured else "INSUFFICIENT_HORIZON",
        "outcome_label": outcome_label,
        "label_version": OUTCOME_LABEL_VERSION,
        "methodology_version": OUTCOME_METHODOLOGY_VERSION,
        "price_at_detection": initial.get("price"),
        "liquidity_at_detection": initial.get("liquidity"),
        "market_cap_at_detection": initial.get("market_cap"),
        "observed_peak_multiple": _json_decimal(get("mark_multiple")),
        "executable_peak_multiple": _json_decimal(executable_multiple),
        "observed_return": (
            current_series.get("return")
            if current_series.get("return") is not None
            else (
                None
                if get("mark_multiple") is None
                else _json_decimal(Decimal(str(get("mark_multiple"))) - 1)
            )
        ),
        "peak_return": (
            None
            if get("mark_multiple") is None
            else _json_decimal(Decimal(str(get("mark_multiple"))) - 1)
        ),
        "executable_return": (
            None
            if executable_multiple is None
            else _json_decimal(Decimal(str(executable_multiple)) - 1)
        ),
        "max_drawdown": _json_decimal(get("post_peak_drawdown")),
        "time_to_2x": _json_decimal(get("time_to_2x")),
        "time_to_5x": _json_decimal(get("time_to_5x")),
        "time_to_10x": _json_decimal(get("time_to_10x")),
        "time_to_20x": _json_decimal(get("time_to_20x")),
        "time_to_50x": _json_decimal(get("time_to_50x")),
        "time_to_100x": _json_decimal(get("time_to_100x")),
        "hit_2x": bool(get("hit_2x", False)),
        "hit_5x": bool(get("hit_5x", False)),
        "hit_10x": bool(get("hit_10x", False)),
        "hit_20x": bool(get("hit_20x", False)),
        "hit_50x": bool(get("hit_50x", False)),
        "hit_100x": bool(get("hit_100x", False)),
        "rug_dead_liquidity_collapse": bool(
            get("rug_before_multiple", False) or outcome_flags.get("rug_detected", False)
        ),
        "rug_detected": outcome_flags.get("rug_detected", False),
        "honeypot_detected": outcome_flags.get("honeypot_detected", False),
        "liquidity_removed": outcome_flags.get("liquidity_removed", False),
        "dead_token": outcome_flags.get("dead_token", False),
        "migration_completed": outcome_flags.get("migration_completed", False),
        "provider_provenance": tuple(dict.fromkeys(str(value) for value in provider_provenance)),
        "liquidity_survival": get("liquidity_survival"),
        "quality_state": getattr(get("quality_state"), "value", get("quality_state")),
        "executable_quality_state": getattr(
            get("executable_quality_state"), "value", get("executable_quality_state")
        ),
        "reason_codes": tuple(dict.fromkeys(reason_codes)),
        "evidence_refs": evidence_refs,
        "reached_early_watch": "EARLY_WATCH" in states,
        "reached_strong_setup": "STRONG_SETUP" in states,
        "reached_high_confluence": "HIGH_CONFLUENCE" in states,
        "fast_safety_rejected": fast_safety_rejected,
        "missed_winner": bool(missed_targets),
        "missed_targets": missed_targets,
        "missed_rejection_reason_codes": tuple(
            dict.fromkeys(
                [
                    *reason_codes,
                    *(("FAST_SAFETY_REJECTED",) if fast_safety_rejected else ()),
                    *(("MISSED_EARLY_WATCH",) if "EARLY_WATCH" not in states else ()),
                ]
            )
        ),
        "collection_mode": "LIVE_SHADOW",
        "outcome_version": "pumpfun-forward-outcomes-v2",
        **{
            f"return_{name}": value.get("return")
            for name, value in series.items()
        },
        **{
            f"max_return_{name}": value.get("max_return")
            for name, value in series.items()
            if name in {"1h", "6h", "24h"}
        },
        **{
            f"max_drawdown_{name}": value.get("max_drawdown")
            for name, value in series.items()
            if name in {"1h", "6h", "24h"}
        },
    }


def _false_positive_observations(
    record: LaunchRecord,
    outcome_payload: Mapping[str, object],
    stage_payloads: Sequence[Mapping[str, object]],
    *,
    query_at: datetime,
) -> tuple[Observation, ...]:
    findings = FalsePositiveAnalyzer().analyze(
        record.mint,
        outcome_payload,
        stage_snapshots=stage_payloads,
    )
    result: list[Observation] = []
    for finding in findings:
        stage = finding.stage
        source_id = f"pumpfun-false-positive:{record.mint}:{stage}"
        snapshot = next(
            (
                value
                for value in stage_payloads
                if str(value.get("state", value.get("stage", ""))).upper() == stage
            ),
            {},
        )
        payload = {
            "mint": record.mint,
            "stage": stage,
            "score": snapshot.get("early_score"),
            "confidence": snapshot.get("confidence"),
            "creator_evidence": {
                "creator": record.payload.get("creator"),
                "creator_linked_buyer_ratio": snapshot.get("creator_linked_buyer_ratio"),
            },
            "wallet_evidence": {
                "raw_smart_wallet_count": snapshot.get("raw_smart_wallet_count"),
                "independent_smart_wallet_count": snapshot.get("independent_smart_wallet_count"),
            },
            "bundle_evidence": {
                "bundle_risk": snapshot.get("bundle_risk"),
                "sniper_risk": snapshot.get("sniper_risk"),
            },
            "organic_momentum": snapshot.get("organic_momentum_score"),
            "liquidity": snapshot.get("liquidity"),
            "failure_reason": finding.explanation,
            "reason_codes": [reason.code for reason in finding.reason_codes],
            "attribution": finding.attribution.value,
            "historical_score_unchanged": True,
            "outcome_horizon": outcome_payload.get("horizon"),
            "collection_mode": "LIVE_SHADOW",
        }
        result.append(
            _research_observation(
                kind="research.false_positive",
                source_id=source_id,
                query_at=query_at,
                payload=payload,
                quality_state=QualityState.FRESH,
                record=record,
                occurred_at=query_at,
            )
        )
    return tuple(result)


class PumpFunForwardEvidenceCollector:
    """One bounded scheduler for all discovered launches."""

    def __init__(
        self,
        engine: AsyncEngine,
        market: MarketDataPort,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.engine = engine
        self.market = market
        self.clock = clock or (lambda: datetime.now(UTC))

    async def run(
        self,
        stop_event: asyncio.Event,
        *,
        poll_interval_seconds: float,
        sleeper: Sleep = asyncio.sleep,
    ) -> None:
        while not stop_event.is_set():
            try:
                await self.collect_once()
            except Exception as error:  # noqa: BLE001 - research worker must not stop ingestion.
                LOGGER.warning(
                    "pumpfun_forward_collection_failed",
                    extra={"error_class": type(error).__name__},
                )
            if not stop_event.is_set():
                await sleeper(poll_interval_seconds)

    async def collect_once(self, *, now: datetime | None = None) -> int:
        query_now = ensure_utc(now or self.clock(), "now")
        rows = await _load_rows(self.engine)
        # Process the oldest due records first so a live stream cannot starve
        # historical mints while the bounded cycle catches up.
        records = _launch_records(rows)
        existing = _existing_sources(rows)
        persisted = 0
        processed_records = 0
        for record in records:
            if processed_records >= _MAX_LAUNCHES_PER_CYCLE:
                break
            record_observations: list[Observation] = []
            first = _pair_first(rows, record.mint)
            first_offset: int | None = None
            first_market: Observation | None = None
            first_error: BaseException | None = None
            if not first:
                first_offset = _next_due_offset(
                    record.discovered_at,
                    DEX_FIRST_OBSERVATION_OFFSETS_SECONDS,
                    existing,
                    record.mint,
                    "dex",
                    query_now,
                )
                if first_offset is not None:
                    first_market, first_error = await _query_market(
                        self.market,
                        record,
                        query_at=query_now,
                    )
                    snapshot = (
                        unknown_market_snapshot(
                            record,
                            query_at=query_now,
                            offset_seconds=first_offset,
                        )
                        if first_market is None
                        else _market_observation(
                            first_market,
                            record,
                            query_at=query_now,
                            offset_seconds=first_offset,
                        )
                    )
                    record_observations.extend(
                        (
                            snapshot,
                            _research_observation(
                                kind="research.dex_forward",
                                source_id=forward_observation_source_id(
                                    record.mint, first_offset
                                ),
                                query_at=query_now,
                                payload=_forward_payload(
                                    record,
                                    query_at=query_now,
                                    offset_seconds=first_offset,
                                    market=first_market,
                                    error=first_error,
                                    first_observed_at=(
                                        query_now
                                        if (
                                            first_market is not None
                                            and first_market.normalized_payload.get(
                                                "pair_address"
                                            )
                                            is not None
                                        )
                                        else None
                                    ),
                                ),
                                quality_state=(
                                    QualityState.UNKNOWN
                                    if first_market is None
                                    else first_market.quality_state
                                ),
                                record=record,
                            ),
                        )
                    )
                    existing.add(forward_observation_source_id(record.mint, first_offset))
                    existing.add(snapshot.provenance.source_id)
                elif _dex_horizon_exhausted(
                    record.discovered_at,
                    existing,
                    record.mint,
                    query_now,
                ):
                    terminal_source = dex_horizon_source_id(record.mint)
                    if terminal_source not in existing:
                        terminal_payload = _forward_payload(
                            record,
                            query_at=query_now,
                            offset_seconds=DEX_FIRST_OBSERVATION_OFFSETS_SECONDS[-1],
                            market=None,
                            error=None,
                            first_observed_at=None,
                        )
                        terminal_payload.update(
                            {
                                "poll_status": "HORIZON_EXHAUSTED",
                                "poll_terminal": True,
                                "dex_query_offset_seconds": None,
                                "dex_query_label": None,
                                "terminal_at": query_now.isoformat(),
                            }
                        )
                        record_observations.append(
                            _research_observation(
                                kind="research.dex_forward",
                                source_id=terminal_source,
                                query_at=query_now,
                                payload=terminal_payload,
                                quality_state=QualityState.UNKNOWN,
                                record=record,
                            )
                        )
                        existing.add(terminal_source)
            market_offset = _next_due_offset(
                record.discovered_at,
                MARKET_SNAPSHOT_OFFSETS_SECONDS,
                existing,
                record.mint,
                "market",
                query_now,
            )
            if market_offset is not None:
                if market_offset == first_offset:
                    market_observation, market_error = first_market, first_error
                else:
                    market_observation, market_error = await _query_market(
                        self.market,
                        record,
                        query_at=query_now,
                    )
                snapshot = (
                    unknown_market_snapshot(
                        record,
                        query_at=query_now,
                        offset_seconds=market_offset,
                    )
                    if market_observation is None
                    else _market_observation(
                        market_observation,
                        record,
                        query_at=query_now,
                        offset_seconds=market_offset,
                    )
                )
                record_observations.append(snapshot)
                existing.add(_market_source_id(record.mint, market_offset))
            for funnel in _funnel_transition_rows(rows, record, query_at=query_now):
                if funnel.provenance.source_id not in existing:
                    record_observations.append(funnel)
                    existing.add(funnel.provenance.source_id)
            creator_source = f"pumpfun-creator-history:{record.mint}"
            if creator_source not in existing:
                creator = _creator_history_rows(rows, record)
                if creator is not None:
                    record_observations.append(creator)
                    existing.add(creator_source)
            if record_observations:
                processed_records += 1
                persisted += await _persist(self.engine, record_observations)
        rows = await _load_rows(self.engine)
        outcome_observations = await self._outcome_cycle(rows, query_now)
        persisted += await _persist(self.engine, outcome_observations)
        return persisted

    async def _outcome_cycle(
        self,
        rows: Sequence[ObservationRow],
        now: datetime,
    ) -> tuple[Observation, ...]:
        records = _launch_records(rows)
        existing = _existing_sources(rows)
        existing_outcomes = {
            row.source_id: dict(row.normalized_payload)
            for row in rows
            if row.kind == "research.outcome"
        }
        result: list[Observation] = []
        labeler = ExtremeWinnerOutcomeLabeler()
        for record in records:
            token_id = _token_id(record)
            candidate_id = _candidate_id(record)
            market_rows = [
                row
                for row in rows
                if row.kind == "market.market_snapshot"
                and _mint(row) == record.mint
                and row.ingested_at <= now
                and row.occurred_at is not None
            ]
            observations = [_observation_from_row(row, token_id=token_id) for row in market_rows]
            replay_records = tuple(
                ReplayEventRecord(
                    observation=observation,
                    registry_version=PUMPFUN_FORWARD_VERSION,
                )
                for observation in observations
                if observation.occurred_at is not None
            )
            stage_payloads = [
                dict(row.normalized_payload)
                for row in rows
                if row.kind == "early.stage_snapshot" and _mint(row) == record.mint
            ]
            checkpoint = ReplayCheckpoint(
                id=uuid5(NAMESPACE_URL, f"{_FORWARD_NAMESPACE}checkpoint:{record.mint}"),
                token_id=token_id,
                candidate_id=candidate_id,
                as_of=record.discovered_at,
                venue="pump.fun",
            )
            baseline_price = None
            for observation in sorted(replay_records, key=lambda value: value.event_at):
                if (
                    observation.event_at <= record.discovered_at
                    and observation.observation.quality_state is QualityState.FRESH
                ):
                    raw = observation.observation.normalized_payload.get(
                        "price_usd", observation.observation.normalized_payload.get("price")
                    )
                    try:
                        if raw is not None and Decimal(str(raw)) > 0:
                            baseline_price = Decimal(str(raw))
                    except (TypeError, ValueError):
                        pass

            initial_values = _initial_market_values(
                replay_records,
                record.discovered_at,
                stage_payloads,
            )
            if baseline_price is None and initial_values.get("price") is not None:
                baseline_price = Decimal(str(initial_values["price"]))
            baseline_market_cap = (
                Decimal(str(initial_values["market_cap"]))
                if initial_values.get("market_cap") is not None
                else None
            )
            base_flags = _outcome_flags(
                replay_records,
                stage_payloads,
                signal_at=record.discovered_at,
                initial_liquidity=(
                    Decimal(str(initial_values["liquidity"]))
                    if initial_values.get("liquidity") is not None
                    else None
                ),
            )
            provider_provenance = tuple(
                sorted(
                    {
                        observation.observation.provenance.provider
                        for observation in replay_records
                        if observation.observation.provenance.provider
                    }
                )
            )
            evaluations: dict[str, dict[str, object]] = {}
            for horizon, duration in _FORWARD_OUTCOME_HORIZONS:
                if not poll_is_due(record.discovered_at, int(duration.total_seconds()), now):
                    continue
                label = labeler.evaluate(
                    replay_records,
                    checkpoint,
                    baseline_price=baseline_price,
                    baseline_market_cap=baseline_market_cap,
                    horizon=duration,
                )
                matured = _horizon_matured(replay_records, record.discovered_at, duration)
                endpoint = _endpoint_record(replay_records, record.discovered_at, duration)
                endpoint_multiple = _multiple_at_endpoint(
                    endpoint,
                    baseline_price=baseline_price,
                    baseline_market_cap=baseline_market_cap,
                )
                severe_drawdown = (
                    getattr(label, "post_peak_drawdown", None) is not None
                    and Decimal(str(label.post_peak_drawdown)) >= Decimal("0.50")
                )
                dead_token = bool(
                    base_flags.get("dead_token", False)
                    or (matured and endpoint is not None and endpoint_multiple is None)
                )
                outcome_label = classify_research_outcome(
                    matured=matured,
                    hit_2x=bool(getattr(label, "hit_2x", False)),
                    hit_5x=bool(getattr(label, "hit_5x", False)),
                    hit_10x=bool(getattr(label, "hit_10x", False)),
                    hit_20x=bool(getattr(label, "hit_20x", False)),
                    hit_50x=bool(getattr(label, "hit_50x", False)),
                    rug_detected=bool(base_flags.get("rug_detected", False)),
                    honeypot_detected=bool(base_flags.get("honeypot_detected", False)),
                    dead_token=dead_token,
                    severe_drawdown=severe_drawdown,
                    observable=endpoint_multiple is not None,
                )
                evaluations[horizon] = {
                    "label": label,
                    "matured": matured,
                    "outcome_label": outcome_label.value,
                    "return": (
                        None
                        if not matured or endpoint_multiple is None
                        else _json_decimal(endpoint_multiple - 1)
                    ),
                    "max_return": (
                        None
                        if not matured or getattr(label, "mfe", None) is None
                        else _json_decimal(Decimal(str(label.mfe)) - 1)
                    ),
                    "max_drawdown": (
                        None
                        if not matured
                        else _json_decimal(getattr(label, "post_peak_drawdown", None))
                    ),
                    "dead_token": dead_token,
                }
            series = {
                name: {
                    "return": values["return"],
                    "max_return": values["max_return"],
                    "max_drawdown": values["max_drawdown"],
                    "outcome_label": values["outcome_label"],
                }
                for name, values in evaluations.items()
            }
            for horizon, duration in _FORWARD_OUTCOME_HORIZONS:
                source_id = f"pumpfun-outcome:{record.mint}:{horizon}"
                evaluation = evaluations.get(horizon)
                if evaluation is None:
                    continue
                label = cast(ExtremeWinnerOutcomeSnapshot, evaluation["label"])
                matured = bool(evaluation["matured"])
                outcome_flags = {
                    **base_flags,
                    "dead_token": bool(evaluation["dead_token"]),
                }
                payload = _outcome_payload(
                    record,
                    label=label,
                    horizon=horizon,
                    duration=duration,
                    stage_payloads=stage_payloads,
                    matured=matured,
                    outcome_label=str(evaluation["outcome_label"]),
                    initial_values=initial_values,
                    outcome_series=series,
                    flags=outcome_flags,
                    provider_provenance=provider_provenance,
                )
                missed_findings = MissedWinnerAnalyzer().analyze(
                    record.mint,
                    payload,
                    stage_snapshots=stage_payloads,
                )
                if missed_findings:
                    payload["missed_winner"] = True
                    payload["missed_targets"] = tuple(
                        f"{int(finding.threshold_multiple)}X" for finding in missed_findings
                    )
                    payload["missed_rejection_reason_codes"] = tuple(
                        dict.fromkeys(
                            code
                            for finding in missed_findings
                            for code in (reason.code for reason in finding.reason_codes)
                        )
                    )
                    payload["missed_findings"] = [
                        dict(finding.to_mapping()) for finding in missed_findings
                    ]
                previous_payload = existing_outcomes.get(source_id)
                if previous_payload is not None:
                    if _stable_payload(previous_payload) == _stable_payload(payload):
                        continue
                    if (
                        previous_payload.get("matured") is True
                        and payload.get("matured") is not True
                        and previous_payload.get("outcome_version")
                        == payload.get("outcome_version")
                    ):
                        continue
                outcome = _research_observation(
                    kind="research.outcome",
                    source_id=source_id,
                    query_at=now,
                    payload=payload,
                    quality_state=QualityState.FRESH if matured else QualityState.UNKNOWN,
                    record=record,
                )
                result.append(outcome)
                existing.add(source_id)
                existing_outcomes[source_id] = payload
                if payload["missed_winner"] is True:
                    targets = payload["missed_targets"]
                    if not isinstance(targets, Sequence) or isinstance(
                        targets, str | bytes | bytearray
                    ):
                        targets = ()
                    for target in targets:
                        missed_source = f"pumpfun-missed:{record.mint}:{horizon}:{target}"
                        result.append(
                            _research_observation(
                                kind="research.missed_winner",
                                source_id=missed_source,
                                query_at=now,
                                payload={
                                    **payload,
                                    "threshold": target,
                                    "rejection_reason_codes": payload[
                                        "missed_rejection_reason_codes"
                                    ],
                                },
                                quality_state=label.quality_state,
                                record=record,
                            )
                        )
                if horizon == "7d":
                    result.extend(
                        _false_positive_observations(
                            record,
                            payload,
                            stage_payloads,
                            query_at=now,
                        )
                    )
                if payload["rug_dead_liquidity_collapse"] is True:
                    invalidated_source = f"pumpfun-invalidated:{record.mint}"
                    if invalidated_source in existing:
                        continue
                    result.append(
                        _research_observation(
                            kind="research.funnel_transition",
                            source_id=invalidated_source,
                            query_at=now,
                            payload={
                                "mint": record.mint,
                                "stage": "INVALIDATED",
                                "state": "INVALIDATED",
                                "transition_at": now.isoformat(),
                                "reason_codes": payload["reason_codes"],
                                "collection_mode": "LIVE_SHADOW",
                            },
                            quality_state=label.quality_state,
                            record=record,
                        )
                    )
                    existing.add(invalidated_source)
        return tuple(result)


__all__ = [
    "LaunchRecord",
    "PumpFunForwardEvidenceCollector",
    "is_pumpfun_launch",
    "unknown_market_snapshot",
]
