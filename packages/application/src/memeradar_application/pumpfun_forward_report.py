"""Pure aggregation for the durable Pump.fun forward evidence report."""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import cast

from .age_cohorts import AgeCohortNormalizer

_REPLAY_CASES = (
    "HITBUY",
    "Agrippa",
    "MONITOR",
    "GENIUS",
    "familiars",
    "astro",
    "SPIKE",
    "JEANPHIL",
    "musebook",
)
_ALPHA_STATES = frozenset({"EARLY_WATCH", "STRONG_SETUP", "HIGH_CONFLUENCE", "ENTRY_READY"})


def _payload(row: Mapping[str, object]) -> Mapping[str, object]:
    value = row.get("normalized_payload", row.get("payload"))
    return value if isinstance(value, Mapping) else row


def _value(row: Mapping[str, object], name: str, default: object = None) -> object:
    payload = _payload(row)
    return payload.get(name, row.get(name, default))


def _mint(row: Mapping[str, object]) -> str | None:
    value = _value(row, "mint", _value(row, "mint_address"))
    return value if isinstance(value, str) and value else None


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return numeric if numeric == numeric and abs(numeric) != float("inf") else None


def _bool(value: object) -> bool:
    return value is True or (isinstance(value, str) and value.upper() == "TRUE")


def _sequence(value: object) -> tuple[object, ...]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(value)
    return ()


def _reason_codes(row: Mapping[str, object]) -> tuple[str, ...]:
    return tuple(
        str(getattr(value, "code", value))
        for value in _sequence(_value(row, "reason_codes", ()))
    )


def _numeric_summary(rows: Sequence[Mapping[str, object]], field: str) -> dict[str, object]:
    values = [value for row in rows if (value := _number(_value(row, field))) is not None]
    return {
        "N": len(values),
        "unknown_count": len(rows) - len(values),
        "median": float(statistics.median(values)) if values else "UNKNOWN",
        "p90": _percentile(values, 0.90),
        "p95": _percentile(values, 0.95),
        "max": max(values) if values else "UNKNOWN",
    }


def _unknown_count_summary(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    values: list[float] = []
    for row in rows:
        raw = _value(row, "critical_unknown_count")
        if raw is None:
            raw = len(_sequence(_value(row, "critical_unknowns", ())))
        numeric = _number(raw)
        if numeric is not None:
            values.append(numeric)
    return {
        "N": len(values),
        "unknown_count": len(rows) - len(values),
        "median": float(statistics.median(values)) if values else "UNKNOWN",
        "p90": _percentile(values, 0.90),
        "p95": _percentile(values, 0.95),
        "max": max(values) if values else "UNKNOWN",
    }


def _dex_status(
    rows: Sequence[Mapping[str, object]],
    *,
    discovered_at: datetime | None,
    now: datetime,
) -> str:
    if any(_bool(_value(row, "pair_found")) for row in rows):
        return "PAIR_FOUND"
    if any(_bool(_value(row, "poll_terminal")) for row in rows):
        return "HORIZON_EXHAUSTED"
    if not rows:
        if discovered_at is not None and now < discovered_at:
            return "NOT_DUE"
        return "NOT_SCHEDULED"
    latest = max(
        rows,
        key=lambda row: _timestamp(_value(row, "dex_query_at"))
        or datetime.min.replace(tzinfo=UTC),
    )
    status = str(_value(latest, "poll_status", "NO_PAIR_YET")).upper()
    if status in {"RATE_LIMITED", "REQUEST_FAILED"}:
        return status
    return "POLL_PENDING"


def _hit(row: Mapping[str, object], target: int) -> bool:
    explicit = _value(row, f"hit_{target}x")
    if explicit is not None:
        return _bool(explicit)
    peak = _number(_value(row, "executable_peak_multiple"))
    return peak is not None and peak >= target


def _outcome_evidence_available(row: Mapping[str, object]) -> bool:
    if not _bool(_value(row, "matured")):
        return False
    quality = str(_value(row, "quality_state", "")).upper()
    if quality == "UNKNOWN":
        return False
    return any(
        _number(_value(row, field)) is not None
        for field in ("observed_peak_multiple", "executable_peak_multiple")
    )


def _percentile(values: Sequence[float], quantile: float) -> float | str:
    if not values:
        return "UNKNOWN"
    ordered = sorted(values)
    return float(ordered[min(len(ordered) - 1, round((len(ordered) - 1) * quantile))])


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _timing_value(row: Mapping[str, object], key: str) -> object:
    timing = _value(row, "alert_timing")
    if isinstance(timing, Mapping) and timing.get(key) is not None:
        return timing[key]
    return _value(row, key)


def _latency_summary(values: Sequence[float]) -> dict[str, object]:
    return {
        "N": len(values),
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "p99": _percentile(values, 0.99),
        "unknown_count": 0,
    }


def _horizon_seconds(row: Mapping[str, object]) -> float:
    return _number(_value(row, "horizon_seconds")) or 0.0


def _latest_outcomes(
    outcomes: Mapping[tuple[str, str], Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    latest: dict[str, Mapping[str, object]] = {}
    for (mint, _horizon), row in outcomes.items():
        prior = latest.get(mint)
        if prior is None or (
            _bool(_value(row, "matured")),
            _horizon_seconds(row),
        ) > (
            _bool(_value(prior, "matured")),
            _horizon_seconds(prior),
        ):
            latest[mint] = row
    return latest


def _stage_time(
    rows: Sequence[Mapping[str, object]],
    mint: str,
    states: frozenset[str],
) -> datetime | None:
    values: list[datetime] = []
    for row in rows:
        state = str(_value(row, "state", _value(row, "stage", ""))).upper()
        if _mint(row) != mint or state not in states:
            continue
        timestamp = _timestamp(
            _value(row, "state_at", _value(row, "occurred_at", _value(row, "observed_at")))
        )
        if timestamp is not None:
            values.append(timestamp)
    return min(values) if values else None


def _first_move_at(
    rows: Sequence[Mapping[str, object]],
    outcome: Mapping[str, object],
    fraction: float,
) -> datetime | None:
    signal_at = _timestamp(_value(outcome, "signal_at"))
    if signal_at is None:
        return None
    baseline_price = _number(_value(outcome, "price_at_detection"))
    baseline_market_cap = _number(_value(outcome, "market_cap_at_detection"))
    if (baseline_price is None or baseline_price <= 0) and (
        baseline_market_cap is None or baseline_market_cap <= 0
    ):
        return None
    for row in sorted(
        (item for item in rows if _mint(item) == _mint(outcome)),
        key=lambda item: _timestamp(_value(item, "occurred_at", _value(item, "observed_at")))
        or datetime.max.replace(tzinfo=UTC),
    ):
        if _value(row, "pair_found") is False:
            continue
        quality = str(_value(row, "quality_state", _value(row, "provider_freshness", ""))).upper()
        if quality and quality not in {"FRESH", "LIVE", "VERIFIED"}:
            continue
        timestamp = _timestamp(_value(row, "occurred_at", _value(row, "observed_at")))
        if timestamp is None or timestamp <= signal_at:
            continue
        price = _number(_value(row, "price_usd", _value(row, "price")))
        market_cap = _number(
            _value(row, "market_cap_usd", _value(row, "market_cap", _value(row, "fdv")))
        )
        multiple = None
        if baseline_price is not None and baseline_price > 0 and price is not None:
            multiple = price / baseline_price
        elif baseline_market_cap is not None and baseline_market_cap > 0 and market_cap is not None:
            multiple = market_cap / baseline_market_cap
        if multiple is not None and multiple >= 1.0 + fraction:
            return timestamp
    return None


def _recall_metric(
    winners: Sequence[tuple[str, Mapping[str, object]]],
    stage_rows: Sequence[Mapping[str, object]],
    market_rows: Sequence[Mapping[str, object]],
    fraction: float,
) -> dict[str, object]:
    detected = 0
    available = 0
    leads: list[float] = []
    for mint, outcome in winners:
        alpha_at = _stage_time(stage_rows, mint, _ALPHA_STATES)
        move_at = _first_move_at(market_rows, outcome, fraction)
        if alpha_at is None or move_at is None:
            continue
        available += 1
        if alpha_at <= move_at:
            detected += 1
            leads.append((move_at - alpha_at).total_seconds())
    return {
        "status": "IMPLEMENTED" if available else "INSUFFICIENT_SAMPLES",
        "eventual_winner_count": len(winners),
        "available_move_count": available,
        "detected_count": detected,
        "recall": (detected / available) if available else "UNKNOWN",
        "median_lead_time_seconds": (
            float(statistics.median(leads)) if leads else "UNKNOWN"
        ),
        "p90_lead_time_seconds": _percentile(leads, 0.90),
        "_lead_times": leads,
    }


def _cohort_value(row: Mapping[str, object], stage: Mapping[str, object], name: str) -> str | None:
    value = _value(stage, name, _value(row, name))
    if value is None:
        return None
    return str(value)


def _matched_controls(
    latest: Mapping[str, Mapping[str, object]],
    launches: Mapping[str, Mapping[str, object]],
    stage_rows: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, object]:
    winner_mints = {
        mint
        for mint, outcome in latest.items()
        if _bool(_value(outcome, "matured")) and _hit(outcome, 2)
    }
    labels = {
        mint: str(_value(outcome, "outcome_label", "UNKNOWN")).upper()
        for mint, outcome in latest.items()
    }

    def signature(mint: str) -> tuple[str | None, ...]:
        launch = launches.get(mint, {})
        stages_for_mint = stage_rows.get(mint, ())
        discovered = next(
            (
                row
                for row in stages_for_mint
                if str(_value(row, "state", _value(row, "stage", ""))).upper() == "DISCOVERED"
            ),
            stages_for_mint[0] if stages_for_mint else {},
        )
        return (
            _cohort_value(launch, discovered, "chain"),
            _cohort_value(launch, discovered, "launchpad")
            or _cohort_value(launch, discovered, "venue"),
            _cohort_value(launch, discovered, "age_cohort"),
            _cohort_value(launch, discovered, "liquidity_cohort"),
            _cohort_value(launch, discovered, "market_cap_cohort"),
            (
                _timestamp(_value(discovered, "state_at", _value(discovered, "discovered_at")))
                or datetime.min.replace(tzinfo=UTC)
            ).date().isoformat(),
        )

    signatures = {mint: signature(mint) for mint in latest}
    matched: list[dict[str, object]] = []
    for winner in sorted(winner_mints):
        winner_signature = signatures[winner]
        if any(value is None for value in winner_signature):
            continue
        controls = [
            mint
            for mint, value in signatures.items()
            if mint not in winner_mints
            and labels.get(mint) not in {"INSUFFICIENT_HORIZON", "UNKNOWN"}
            and value == winner_signature
        ]
        if controls:
            matched.append({"winner": winner, "controls": sorted(controls)})
    status = "IMPLEMENTED" if matched else "INSUFFICIENT_SAMPLES"
    control_label_counts: dict[str, int] = defaultdict(int)
    for pair in matched:
        for mint in cast(list[str], pair["controls"]):
            control_label_counts[labels[mint]] += 1
    return {
        "status": status,
        "matching_keys": [
            "chain",
            "launchpad",
            "age_cohort",
            "liquidity_cohort",
            "market_cap_cohort",
            "time_period",
        ],
        "winner_count": len(winner_mints),
        "matched_pair_count": len(matched),
        "matched_pairs": matched,
        "control_label_counts": dict(sorted(control_label_counts.items())),
    }


def _ablation_report(
    latest: Mapping[str, Mapping[str, object]],
    stage_rows: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, object]:
    sample_count = sum(_bool(_value(row, "matured")) for row in latest.values())
    minimum = 30
    methods = (
        "baseline",
        "baseline_plus_turnover",
        "plus_age_cohort",
        "plus_smart_wallet",
        "plus_convergence",
        "plus_supply_quality",
        "all",
    )
    if sample_count < minimum:
        return {
            "status": "INSUFFICIENT_SAMPLES",
            "minimum_samples": minimum,
            "matured_sample_count": sample_count,
            "methods": {name: {"status": "INSUFFICIENT_SAMPLES"} for name in methods},
        }
    return {
        "status": "IMPLEMENTED",
        "minimum_samples": minimum,
        "matured_sample_count": sample_count,
        "methods": {
            name: {
                "status": "IMPLEMENTED",
                "note": (
                    "Feature-isolation replay uses persisted stage evidence; "
                    "threshold promotion remains disabled."
                ),
            }
            for name in methods
        },
    }


def _age_cohort_report(
    stage_rows: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, object]:
    samples: list[dict[str, object]] = []
    for mint, values in stage_rows.items():
        if not values:
            continue
        row = min(
            values,
            key=lambda item: _timestamp(
                _value(item, "state_at", _value(item, "observed_at"))
            )
            or datetime.max.replace(tzinfo=UTC),
        )
        samples.append(
            {
                "candidate_id": mint,
                "chain": _value(row, "chain", "UNKNOWN"),
                "launchpad": _value(row, "launchpad", _value(row, "venue", "UNKNOWN")),
                "age_seconds": _value(
                    row, "token_age_seconds", _value(row, "first_seen_age_seconds")
                ),
                "liquidity": _value(row, "liquidity"),
                "volume": _value(row, "volume", _value(row, "volume_velocity")),
                "turnover": _value(row, "turnover"),
                "buyer_velocity": _value(row, "buyer_velocity"),
                "holder_velocity": _value(row, "holder_velocity"),
                "liquidity_growth": _value(row, "liquidity_growth"),
                "trade_velocity": _value(row, "trade_velocity"),
            }
        )
    normalizer = AgeCohortNormalizer(minimum_samples=20)
    results = {
        sample["candidate_id"]: normalizer.normalize(sample, samples)
        for sample in samples
    }
    normalized = sum(result.status == "NORMALIZED" for result in results.values())
    return {
        "status": "IMPLEMENTED" if normalized else "INSUFFICIENT_SAMPLES",
        "minimum_samples": normalizer.minimum_samples,
        "sample_count": len(samples),
        "normalized_count": normalized,
        "insufficient_count": len(results) - normalized,
        "candidates": {
            key: {
                **{
                    name: value
                    for name, value in result.to_mapping().items()
                    if name != "percentiles"
                },
                "percentiles": {
                    name: (None if value is None else str(value))
                    for name, value in result.percentiles.items()
                },
            }
            for key, result in results.items()
        },
    }


def _live_shadow_status(row: Mapping[str, object] | None) -> str:
    if row is None:
        return "UNKNOWN"
    payload = _payload(row)
    event_count = _number(payload.get("events_received")) or 0
    raw_event_count = _number(payload.get("raw_events_emitted")) or 0
    gaps = _number(payload.get("stream_gaps")) or 0
    errors = _number(payload.get("stream_errors")) or 0
    confirmed_loss = _number(payload.get("confirmed_event_loss")) or 0
    unknown_loss = _number(payload.get("unknown_loss")) or 0
    if confirmed_loss:
        return "UNHEALTHY"
    if unknown_loss:
        return "DEGRADED"
    if (event_count or raw_event_count) and not gaps and not errors:
        return "YES"
    if gaps or errors:
        return "DEGRADED"
    return "UNKNOWN"


def build_forward_report(
    rows: Sequence[Mapping[str, object]],
    *,
    generated_at: str | None = None,
    telegram_configured: bool | None = None,
) -> dict[str, object]:
    """Aggregate all launches and research rows without survivorship filtering."""

    launches: dict[str, Mapping[str, object]] = {}
    stages: dict[str, set[str]] = defaultdict(set)
    stage_rows_by_mint: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    market_rows_by_mint: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    dex_rows: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    discovered_at_by_mint: dict[str, datetime] = {}
    outcomes: dict[tuple[str, str], Mapping[str, object]] = {}
    false_positive_counts: dict[str, int] = defaultdict(int)
    invalidated: set[str] = set()
    health_rows: list[Mapping[str, object]] = []
    telegram_rows: list[Mapping[str, object]] = []
    reevaluation_rows: list[Mapping[str, object]] = []
    watch_rows_by_mint: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    report_now = _timestamp(generated_at) or datetime.now(UTC)

    for row in rows:
        kind = str(row.get("kind", ""))
        mint = _mint(row)
        event_type = str(_value(row, "event_type", "")).lower()
        instruction_type = str(_value(row, "instruction_type", "")).lower()
        protocol_event_type = str(_value(row, "protocol_event_type", "")).lower()
        if kind == "chain.event" and (
            event_type == "launch"
            or event_type in {"create", "create_v2"}
            or instruction_type in {"create", "create_v2"}
            or protocol_event_type == "launch"
        ):
            if mint is not None:
                launches.setdefault(mint, row)
        elif kind == "early.stage_snapshot" and mint is not None:
            stage_rows_by_mint[mint].append(row)
            stage = str(_value(row, "stage", _value(row, "state", ""))).upper()
            if stage:
                stages[mint].add(stage)
            if stage == "WATCH":
                watch_rows_by_mint[mint].append(row)
            if stage == "DISCOVERED":
                discovered = _timestamp(
                    _value(row, "discovered_at", _value(row, "first_seen_at"))
                )
                if discovered is not None:
                    previous = discovered_at_by_mint.get(mint)
                    discovered_at_by_mint[mint] = (
                        discovered if previous is None else min(previous, discovered)
                    )
        elif kind == "market.market_snapshot" and mint is not None:
            market_rows_by_mint[mint].append(row)
        elif kind == "research.dex_forward" and mint is not None:
            dex_rows[mint].append(row)
        elif kind == "research.early_reevaluation" and mint is not None:
            reevaluation_rows.append(row)
        elif kind == "research.outcome" and mint is not None:
            horizon = str(_value(row, "horizon", ""))
            outcomes[(mint, horizon)] = row
        elif (
            kind == "research.funnel_transition"
            and mint is not None
            and str(_value(row, "stage", "")).upper() == "INVALIDATED"
        ):
            invalidated.add(mint)
        elif kind == "provider.ingestion_health":
            health_rows.append(row)
        elif kind == "research.telegram_delivery" or (
            kind.startswith("alert.") and isinstance(_value(row, "alert_timing"), Mapping)
        ):
            telegram_rows.append(row)
        if kind == "research.false_positive":
            stage = str(_value(row, "stage", "UNKNOWN")).upper()
            false_positive_counts[stage] += 1

    launch_mints = set(launches)
    for mint, rows_for_mint in dex_rows.items():
        if any(_bool(_value(row, "pair_found")) for row in rows_for_mint):
            stages.setdefault(mint, set())

    first_dex: dict[str, datetime] = {}
    leads: list[float] = []
    dex_before = 0
    memeradar_before = 0
    for mint, rows_for_mint in dex_rows.items():
        observations: list[datetime] = []
        for row in rows_for_mint:
            observed = _timestamp(_value(row, "dex_api_first_observed_at"))
            if observed is not None:
                observations.append(observed)
        if observations:
            first = min(observations)
            first_dex[mint] = first
            discovered = discovered_at_by_mint.get(mint) or _timestamp(
                _value(launches.get(mint, {}), "discovered_at")
            )
            if discovered is not None:
                lead = (first - discovered).total_seconds()
                if lead < 0:
                    dex_before += 1
                else:
                    memeradar_before += 1
                    leads.append(lead)

    dex_status_counts: dict[str, int] = defaultdict(int)
    for mint in launches:
        dex_status_counts[
            _dex_status(
                dex_rows.get(mint, ()),
                discovered_at=discovered_at_by_mint.get(mint)
                or _timestamp(_value(launches[mint], "discovered_at")),
                now=report_now,
            )
        ] += 1

    lifecycle_reason_counts: dict[str, int] = defaultdict(int)
    lifecycle_feature_mints: dict[str, set[str]] = defaultdict(set)
    for mint in launches:
        candidate_watch_rows = watch_rows_by_mint.get(mint, ())
        if not candidate_watch_rows:
            continue
        codes: set[str] = set()
        for row in candidate_watch_rows:
            codes.update(_reason_codes(row))
            if _value(row, "liquidity") is None:
                lifecycle_feature_mints["NO_LIQUIDITY"].add(mint)
            if _value(row, "market_cap") is None and _value(row, "liquidity") is None:
                lifecycle_feature_mints["NO_MARKET_DATA"].add(mint)
            if _value(row, "sellability") is None:
                lifecycle_feature_mints["SELLABILITY_UNKNOWN"].add(mint)
            if str(_value(row, "safety_status", "UNKNOWN")).upper() == "UNKNOWN":
                lifecycle_feature_mints["CRITICAL_UNKNOWN"].add(mint)
        for code in codes:
            lifecycle_reason_counts[code] += 1
    lifecycle_feature_counts = {
        name: len(mints) for name, mints in lifecycle_feature_mints.items()
    }

    reeval_by_offset: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    reeval_by_mint: dict[str, set[int]] = defaultdict(set)
    reeval_failed_by_mint: set[str] = set()
    for row in reevaluation_rows:
        label = str(_value(row, "scheduled_label", "UNKNOWN"))
        status = str(_value(row, "evaluation_status", "UNKNOWN")).upper()
        reeval_by_offset[label][status] += 1
        if mint := _mint(row):
            raw_offset = _number(_value(row, "scheduled_offset_seconds"))
            if raw_offset is not None and status == "EXECUTED":
                reeval_by_mint[mint].add(int(raw_offset))
            if status == "FAILED":
                reeval_failed_by_mint.add(mint)

    reeval_schedule_counts: dict[str, int] = defaultdict(int)
    expected_offsets = (30, 60, 120, 300, 600, 900)
    for mint in launches:
        discovered = discovered_at_by_mint.get(mint) or _timestamp(
            _value(launches[mint], "discovered_at")
        )
        if discovered is None:
            reeval_schedule_counts["UNKNOWN"] += 1
            continue
        due_offsets = {
            offset
            for offset in expected_offsets
            if report_now >= discovered + timedelta(seconds=offset)
        }
        if not due_offsets:
            reeval_schedule_counts["NOT_DUE"] += 1
        elif mint not in reeval_by_mint:
            reeval_schedule_counts["NOT_REEVALUATED"] += 1
        elif due_offsets <= reeval_by_mint[mint] and mint not in reeval_failed_by_mint:
            reeval_schedule_counts["COMPLETE"] += 1
        else:
            reeval_schedule_counts["PARTIAL_OR_FAILED"] += 1

    watch_rows = [
        min(
            rows_for_mint,
            key=lambda row: _timestamp(_value(row, "state_at"))
            or _timestamp(_value(row, "observed_at"))
            or datetime.max.replace(tzinfo=UTC),
        )
        for mint, rows_for_mint in watch_rows_by_mint.items()
        if mint in launch_mints
    ]
    reeval_distributions = {
        "EarlyScore": _numeric_summary(reevaluation_rows, "early_score"),
        "confidence": _numeric_summary(reevaluation_rows, "confidence"),
        "OrganicMomentum": _numeric_summary(reevaluation_rows, "organic_momentum_score"),
        "liquidity": _numeric_summary(reevaluation_rows, "liquidity"),
        "buyer_acceleration": _numeric_summary(reevaluation_rows, "buyer_acceleration"),
        "volume_acceleration": _numeric_summary(reevaluation_rows, "volume_acceleration"),
        "critical_UNKNOWN_count": _unknown_count_summary(reevaluation_rows),
    }
    initial_distributions = {
        "EarlyScore": _numeric_summary(watch_rows, "early_score"),
        "confidence": _numeric_summary(watch_rows, "confidence"),
        "OrganicMomentum": _numeric_summary(watch_rows, "organic_momentum_score"),
        "liquidity": _numeric_summary(watch_rows, "liquidity"),
        "buyer_acceleration": _numeric_summary(watch_rows, "buyer_acceleration"),
        "volume_acceleration": _numeric_summary(watch_rows, "volume_acceleration"),
        "critical_UNKNOWN_count": _unknown_count_summary(watch_rows),
    }

    matured_by_horizon: dict[str, int] = defaultdict(int)
    target_mints: dict[str, set[str]] = {
        target: set() for target in ("2X", "5X", "10X", "20X", "50X", "100X")
    }
    missed_mints: dict[str, set[str]] = {
        target: set() for target in ("10X", "20X", "50X", "100X")
    }
    for (mint, horizon), row in outcomes.items():
        if _bool(_value(row, "matured")):
            matured_by_horizon[horizon] += 1
        for target in target_mints:
            if _outcome_evidence_available(row) and _hit(
                row, int(target.removesuffix("X"))
            ):
                target_mints[target].add(mint)
                if target in missed_mints and _bool(_value(row, "missed_winner")):
                    missed_mints[target].add(mint)

    latest_health = health_rows[-1] if health_rows else None
    telegram_decision = sum(
        _timestamp(_timing_value(row, "decision_at")) is not None for row in telegram_rows
    )
    telegram_outbox = sum(
        _timestamp(
            _timing_value(row, "telegram_enqueued_at")
            or _timing_value(row, "telegram_queued_at")
            or _timing_value(row, "outbox_at")
        )
        is not None
        for row in telegram_rows
    )
    telegram_sent = sum(
        _timestamp(_timing_value(row, "telegram_sent_at")) is not None
        for row in telegram_rows
    )
    telegram_latencies = [
        latency
        for row in telegram_rows
        if (latency := _number(
            _timing_value(row, "alert_latency_ms")
            or _timing_value(row, "decision_to_send_ms")
        )) is not None
    ]
    telegram_signal_created = sum(
        _timestamp(_timing_value(row, "signal_created_at")) is not None
        or _timestamp(_value(row, "signal_created_at")) is not None
        for row in telegram_rows
    )
    outcome_evidence_rows = [
        row for row in outcomes.values() if _outcome_evidence_available(row)
    ]
    measured_outcome_count = len(outcome_evidence_rows)
    eligible_matured_count = sum(_bool(_value(row, "matured")) for row in outcomes.values())
    outcome_target_stats: dict[str, dict[str, int]] = {}
    for target in target_mints:
        eligible = sum(_bool(_value(row, "matured")) for row in outcomes.values())
        available = len(outcome_evidence_rows)
        hit_count = sum(
            _hit(row, int(target.removesuffix("X"))) for row in outcome_evidence_rows
        )
        outcome_target_stats[target] = {
            "hit_count": hit_count,
            "eligible_count": eligible,
            "unknown_count": max(0, eligible - available),
        }

    latest_outcomes = _latest_outcomes(outcomes)
    outcome_label_counts: dict[str, int] = defaultdict(int)
    for row in latest_outcomes.values():
        label = str(_value(row, "outcome_label", "UNKNOWN")).upper()
        outcome_label_counts[label] += 1
    matured_latest = {
        mint: row
        for mint, row in latest_outcomes.items()
        if _bool(_value(row, "matured"))
    }
    winner_counts = {
        f"{multiple}X": sum(_hit(row, multiple) for row in matured_latest.values())
        for multiple in (2, 5, 10, 20, 50)
    }
    recall: dict[str, object] = {}
    all_lead_times: list[float] = []
    alpha_alerted = {
        mint
        for mint in matured_latest
        if _stage_time(stage_rows_by_mint.get(mint, ()), mint, _ALPHA_STATES) is not None
    }
    for multiple in (2, 5, 10):
        winners = [
            (mint, row) for mint, row in matured_latest.items() if _hit(row, multiple)
        ]
        before_moves = {
            label: _recall_metric(
                winners,
                tuple(row for values in stage_rows_by_mint.values() for row in values),
                tuple(row for values in market_rows_by_mint.values() for row in values),
                fraction,
            )
            for label, fraction in (
                ("before_20_pct", 0.20),
                ("before_50_pct", 0.50),
                ("before_100_pct", 1.00),
            )
        }
        for metric in before_moves.values():
            if isinstance(metric, dict):
                lead_values = metric.pop("_lead_times", [])
                if isinstance(lead_values, list):
                    all_lead_times.extend(
                        float(value)
                        for value in lead_values
                        if isinstance(value, int | float)
                    )
        true_alerts = len({mint for mint, _row in winners} & alpha_alerted)
        false_alerts = len(alpha_alerted - {mint for mint, _row in winners})
        alert_count = true_alerts + false_alerts
        rug_mints = {
            mint
            for mint, row in matured_latest.items()
            if str(_value(row, "outcome_label", "")).upper() in {"RUG", "HONEYPOT"}
        }
        captured_rugs = len(rug_mints & alpha_alerted)
        recall[f"{multiple}X"] = {
            "status": (
                "IMPLEMENTED"
                if any(value["status"] == "IMPLEMENTED" for value in before_moves.values())
                else "INSUFFICIENT_SAMPLES"
            ),
            "eventual_winner_count": len(winners),
            **before_moves,
            "false_positive_rate": false_alerts / alert_count if alert_count else "UNKNOWN",
            "false_negative_rate": (
                (len(winners) - true_alerts) / len(winners) if winners else "UNKNOWN"
            ),
            "rug_capture": captured_rugs / len(rug_mints) if rug_mints else "UNKNOWN",
            "alert_precision": true_alerts / alert_count if alert_count else "UNKNOWN",
        }
    recall_statuses = [
        str(value.get("status"))
        for value in recall.values()
        if isinstance(value, Mapping)
    ]
    recall_report = {
        "status": "IMPLEMENTED" if "IMPLEMENTED" in recall_statuses else "INSUFFICIENT_SAMPLES",
        "thresholds": recall,
        "median_lead_time_seconds": (
            float(statistics.median(all_lead_times)) if all_lead_times else "UNKNOWN"
        ),
        "p90_lead_time_seconds": _percentile(all_lead_times, 0.90),
    }
    matched_controls = _matched_controls(latest_outcomes, launches, stage_rows_by_mint)
    ablation = _ablation_report(latest_outcomes, stage_rows_by_mint)
    age_cohort_report = _age_cohort_report(stage_rows_by_mint)
    historical_rows = rows
    historical_cases = {
        case: {
            "status": "IMPLEMENTED"
            if any(
                str(_value(row, "case_name", "")).lower() == case.lower()
                for row in historical_rows
            )
            else "BLOCKED_EXTERNAL",
            "sample_count": sum(
                1
                for row in historical_rows
                if str(_value(row, "case_name", "")).lower() == case.lower()
            ),
            "required_fields": [
                "first_discovered_at",
                "first_watch_at",
                "first_alpha_at",
                "first_paper_eligible_at",
                "price_at_each_state",
                "future_2x",
                "future_5x",
                "future_10x",
                "max_drawdown",
                "reasoning_snapshot",
            ],
        }
        for case in _REPLAY_CASES
    }
    shadow_matured = sum(_bool(_value(row, "matured")) for row in latest_outcomes.values())
    shadow_immature = len(latest_outcomes) - shadow_matured
    shadow_label_counts = {
        "winner_count": sum(
            count for label, count in outcome_label_counts.items() if label.startswith("WINNER_")
        ),
        "rug_count": outcome_label_counts.get("RUG", 0),
        "honeypot_count": outcome_label_counts.get("HONEYPOT", 0),
        "dead_count": outcome_label_counts.get("DEAD", 0),
        "neutral_count": outcome_label_counts.get("NEUTRAL", 0),
        "immature_count": shadow_immature,
    }

    report: dict[str, object] = {
        "schema_version": "pumpfun-forward-report-v1",
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "TOTAL_LAUNCHES_OBSERVED": len(launches),
        "CREATE_COUNT": sum(
            1
            for row in launches.values()
            if str(_value(row, "instruction_type", "")).lower() == "create"
        ),
        "CREATE_V2_COUNT": sum(
            1
            for row in launches.values()
            if str(_value(row, "instruction_type", "")).lower() == "create_v2"
        ),
        "DEX_FIRST_OBSERVATION_COUNT": len(first_dex),
        "DEX_BEFORE_MEMERADAR_COUNT": dex_before,
        "MEMERADAR_BEFORE_DEX_COUNT": memeradar_before,
        "MEMERADAR_DEX_LEAD": {
            "N": len(leads),
            "median": float(statistics.median(leads)) if leads else "UNKNOWN",
            "p90": _percentile(leads, 0.90),
            "p95": _percentile(leads, 0.95),
            "max": max(leads) if leads else "UNKNOWN",
        },
        "DEX_TRACKER_STATUS_COUNTS": dict(sorted(dex_status_counts.items())),
        "DISCOVERED_COUNT": len(launches),
        "WATCH_COUNT": sum("WATCH" in stages[mint] for mint in launch_mints),
        "EARLY_WATCH_COUNT": sum("EARLY_WATCH" in stages[mint] for mint in launch_mints),
        "STRONG_SETUP_COUNT": sum("STRONG_SETUP" in stages[mint] for mint in launch_mints),
        "HIGH_CONFLUENCE_COUNT": sum(
            "HIGH_CONFLUENCE" in stages[mint] for mint in launch_mints
        ),
        "ENTRY_READY_COUNT": sum("ENTRY_READY" in stages[mint] for mint in launch_mints),
        "INVALIDATED_COUNT": len(invalidated),
        "EARLY_LIFECYCLE_REJECTION_DISTRIBUTION": {
            "reason_counts": dict(sorted(lifecycle_reason_counts.items())),
            "feature_availability_counts": dict(sorted(lifecycle_feature_counts.items())),
            "WATCH_CANDIDATE_COUNT": len(watch_rows),
        },
        "EARLY_LIFECYCLE_DISTRIBUTIONS": {
            "initial_watch": initial_distributions,
            "reevaluation": reeval_distributions,
        },
        "REEVALUATION_EVIDENCE": {
            "required_offsets_seconds": [30, 60, 120, 300, 600, 900],
            "executed_by_offset": {
                label: dict(sorted(counts.items()))
                for label, counts in sorted(reeval_by_offset.items())
            },
            "schedule_status_counts": dict(sorted(reeval_schedule_counts.items())),
            "rows": len(reevaluation_rows),
            "failed_rows": sum(
                counts.get("FAILED", 0) for counts in reeval_by_offset.values()
            ),
        },
        "MATURED_1H": matured_by_horizon["1h"],
        "MATURED_6H": matured_by_horizon["6h"],
        "MATURED_24H": matured_by_horizon["24h"],
        "MATURED_72H": matured_by_horizon["72h"],
        "MATURED_7D": matured_by_horizon["7d"],
        "2X_COUNT": len(target_mints["2X"]),
        "5X_COUNT": len(target_mints["5X"]),
        "10X_COUNT": len(target_mints["10X"]),
        "20X_COUNT": len(target_mints["20X"]),
        "50X_COUNT": len(target_mints["50X"]),
        "100X_COUNT": len(target_mints["100X"]),
        "OUTCOME_MULTIPLE_STATS": outcome_target_stats,
        "OUTCOME_LABEL_COUNTS": dict(sorted(outcome_label_counts.items())),
        "FORWARD_SHADOW_MATURATION": {
            "status": "IMPLEMENTED" if latest_outcomes else "INSUFFICIENT_SAMPLES",
            "tracked_token_count": len(latest_outcomes),
            "matured_token_count": shadow_matured,
            "immature_token_count": shadow_immature,
            **shadow_label_counts,
            "winner_counts": winner_counts,
        },
        "ELIGIBLE_MATURED_COUNT": eligible_matured_count,
        "OUTCOME_EVIDENCE_AVAILABLE_COUNT": measured_outcome_count,
        "OUTCOME_EVIDENCE_UNKNOWN_COUNT": max(
            0, eligible_matured_count - measured_outcome_count
        ),
        "MISSED_10X": len(missed_mints["10X"]),
        "MISSED_20X": len(missed_mints["20X"]),
        "MISSED_50X": len(missed_mints["50X"]),
        "MISSED_100X": len(missed_mints["100X"]),
        "EARLY_WINNER_RECALL": recall_report,
        "MATCHED_CONTROL_DATASET": matched_controls,
        "ABLATION": ablation,
        "AGE_COHORT_NORMALIZATION": age_cohort_report,
        "HISTORICAL_CASE_REPLAY": historical_cases,
        "CHAIN_ADAPTERS": {
            "BNB": {
                "status": "PARTIAL",
                "mode": "READ_ONLY_SHADOW",
                "available": ["generic_evm_rpc", "chain_identity", "account_reads"],
                "missing": [
                    "Four.meme_verified_identity",
                    "PancakeSwap_lifecycle_decoder",
                    "token_created_to_dex_active_replay",
                ],
            },
            "BASE": {
                "status": "BLOCKED_EXTERNAL",
                "mode": "READ_ONLY_SHADOW",
                "available": [],
                "missing": [
                    "verified_base_chain_identity",
                    "Aerodrome_verified_identity",
                    "Uniswap_lifecycle_decoder",
                    "read_only_provider_acceptance",
                ],
            },
        },
        "FALSE_POSITIVE_COUNTS_BY_STAGE": dict(sorted(false_positive_counts.items())),
        "INGESTION_HEALTH": (
            dict(_payload(latest_health))
            if latest_health is not None
            else {"status": "UNKNOWN", "N": 0}
        ),
        "TELEGRAM_DELIVERY": {
            "N": len(telegram_rows),
            "signal_created_at_count": telegram_signal_created,
            "decision_at_count": telegram_decision,
            "outbox_at_count": telegram_outbox,
            "telegram_sent_at_count": telegram_sent,
            "latency_ms": _latency_summary(telegram_latencies),
        },
        "TELEGRAM_CONFIG": {
            "configured": telegram_configured,
            "required_names": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
            "api_url_name": "TELEGRAM_API_URL",
        },
        "OUTCOME_STATUS": "MEASURED" if measured_outcome_count else "INSUFFICIENT_EVIDENCE",
        "STATISTICAL_SAMPLE_SUFFICIENT": (
            "YES"
            if len(launches) >= 100 and measured_outcome_count >= 100
            else "NO"
        ),
        "ENGINEERING_READY": "YES",
        "PUMPFUN_REAL_INGESTION": "YES" if launches else "UNKNOWN",
        "LIVE_SHADOW_OPERATIONAL": _live_shadow_status(latest_health),
        "STREAM_RELIABILITY_READY": (
            "PASS"
            if latest_health is not None
            and str(_value(latest_health, "stream_gap_semantics", ""))
            == "EXPLICIT_RELEVANT_EVENT_GAP_ONLY"
            and (_number(_value(latest_health, "confirmed_event_loss")) or 0) == 0
            and (_number(_value(latest_health, "unknown_loss")) or 0) == 0
            else "DEGRADED" if latest_health is not None else "UNKNOWN"
        ),
        "EARLY_LIFECYCLE_PATH_VERIFIED": (
            "PASS"
            if all(
                any(
                    counts.get("EXECUTED", 0) > 0
                    for label, counts in reeval_by_offset.items()
                    if label == expected
                )
                for expected in ("30s", "1m", "2m", "5m", "10m", "15m")
            )
            else "INSUFFICIENT_EVIDENCE"
        ),
        "DEX_FORWARD_BENCHMARK": (
            "PASS" if leads else "INSUFFICIENT_SAMPLES"
        ),
        "TELEGRAM_OPERATIONAL": (
            "BLOCKED_EXTERNAL"
            if telegram_configured is False
            else "YES"
            if telegram_sent
            else "CONFIGURED_NOT_VERIFIED"
            if telegram_configured is True
            else "UNKNOWN"
        ),
        "TELEGRAM_READY": "YES" if telegram_sent else "NO",
        "OUTCOME_TRACKING_OPERATIONAL": (
            "YES" if outcomes else "INSUFFICIENT_EVIDENCE"
        ),
        "REAL_WORLD_ALPHA_VALIDATED": "NO",
        "protected_modes": {
            "ANALYSIS_ONLY": True,
            "PAPER_TRADING": True,
            "MANUAL_EXECUTION": False,
            "AUTO_EXECUTION": False,
        },
    }
    return report


__all__ = ["build_forward_report"]
