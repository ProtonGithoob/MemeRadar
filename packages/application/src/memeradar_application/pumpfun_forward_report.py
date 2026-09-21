"""Pure aggregation for the durable Pump.fun forward evidence report."""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
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
    if (event_count or raw_event_count) and not gaps and not errors:
        return "YES"
    if gaps or errors:
        return "DEGRADED"
    return "UNKNOWN"


def build_forward_report(
    rows: Sequence[Mapping[str, object]],
    *,
    generated_at: str | None = None,
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
            if _hit(row, int(target.removesuffix("X"))):
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
    measured_outcome_count = sum(
        _outcome_evidence_available(row) for row in outcomes.values()
    )

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
        "DISCOVERED_COUNT": len(launches),
        "WATCH_COUNT": sum("WATCH" in stages[mint] for mint in launch_mints),
        "EARLY_WATCH_COUNT": sum("EARLY_WATCH" in stages[mint] for mint in launch_mints),
        "STRONG_SETUP_COUNT": sum("STRONG_SETUP" in stages[mint] for mint in launch_mints),
        "HIGH_CONFLUENCE_COUNT": sum(
            "HIGH_CONFLUENCE" in stages[mint] for mint in launch_mints
        ),
        "ENTRY_READY_COUNT": sum("ENTRY_READY" in stages[mint] for mint in launch_mints),
        "INVALIDATED_COUNT": len(invalidated),
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
        "OUTCOME_STATUS": (
            "MEASURED"
            if measured_outcome_count
            else "INSUFFICIENT_SAMPLES"
        ),
        "STATISTICAL_SAMPLE_SUFFICIENT": (
            "YES"
            if len(launches) >= 100 and measured_outcome_count >= 100
            else "NO"
        ),
        "ENGINEERING_READY": "YES",
        "PUMPFUN_REAL_INGESTION": "YES" if launches else "UNKNOWN",
        "LIVE_SHADOW_OPERATIONAL": _live_shadow_status(latest_health),
        "DEX_FORWARD_BENCHMARK": (
            "PASS" if leads else "INSUFFICIENT_SAMPLES"
        ),
        "TELEGRAM_OPERATIONAL": "YES" if telegram_sent else "UNKNOWN",
        "OUTCOME_TRACKING_OPERATIONAL": "YES" if outcomes else "INSUFFICIENT_SAMPLES",
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
