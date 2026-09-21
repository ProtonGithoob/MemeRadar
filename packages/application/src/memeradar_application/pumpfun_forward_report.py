"""Pure aggregation for the durable Pump.fun forward evidence report."""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation


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
        elif kind == "research.telegram_delivery":
            telegram_rows.append(row)
        if kind == "research.false_positive":
            stage = str(_value(row, "stage", "UNKNOWN")).upper()
            false_positive_counts[stage] += 1

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
    lifecycle_feature_counts: dict[str, int] = defaultdict(int)
    for mint in launches:
        candidate_watch_rows = watch_rows_by_mint.get(mint, ())
        if not candidate_watch_rows:
            continue
        codes: set[str] = set()
        for row in candidate_watch_rows:
            codes.update(_reason_codes(row))
            if _value(row, "liquidity") is None:
                lifecycle_feature_counts["NO_LIQUIDITY"] += 1
            if _value(row, "market_cap") is None and _value(row, "liquidity") is None:
                lifecycle_feature_counts["NO_MARKET_DATA"] += 1
            if _value(row, "sellability") is None:
                lifecycle_feature_counts["SELLABILITY_UNKNOWN"] += 1
            if str(_value(row, "safety_status", "UNKNOWN")).upper() == "UNKNOWN":
                lifecycle_feature_counts["CRITICAL_UNKNOWN"] += 1
        for code in codes:
            lifecycle_reason_counts[code] += 1

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

    watch_rows = [row for rows_for_mint in watch_rows_by_mint.values() for row in rows_for_mint]
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
    launch_mints = set(launches)
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
        _timestamp(_value(row, "decision_at")) is not None for row in telegram_rows
    )
    telegram_outbox = sum(
        _timestamp(_value(row, "outbox_at")) is not None for row in telegram_rows
    )
    telegram_sent = sum(
        _timestamp(_value(row, "telegram_sent_at")) is not None for row in telegram_rows
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
            "WATCH_CANDIDATE_COUNT": len(watch_rows_by_mint),
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
        "ELIGIBLE_MATURED_COUNT": eligible_matured_count,
        "OUTCOME_EVIDENCE_AVAILABLE_COUNT": measured_outcome_count,
        "OUTCOME_EVIDENCE_UNKNOWN_COUNT": max(
            0, eligible_matured_count - measured_outcome_count
        ),
        "MISSED_10X": len(missed_mints["10X"]),
        "MISSED_20X": len(missed_mints["20X"]),
        "MISSED_50X": len(missed_mints["50X"]),
        "MISSED_100X": len(missed_mints["100X"]),
        "FALSE_POSITIVE_COUNTS_BY_STAGE": dict(sorted(false_positive_counts.items())),
        "INGESTION_HEALTH": (
            dict(_payload(latest_health))
            if latest_health is not None
            else {"status": "UNKNOWN", "N": 0}
        ),
        "TELEGRAM_DELIVERY": {
            "N": len(telegram_rows),
            "decision_at_count": telegram_decision,
            "outbox_at_count": telegram_outbox,
            "telegram_sent_at_count": telegram_sent,
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
            and not any(
                counts.get("FAILED", 0) > 0 for counts in reeval_by_offset.values()
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
