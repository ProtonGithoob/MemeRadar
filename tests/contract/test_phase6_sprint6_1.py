"""Keyless replay contracts for Phase 6 Sprint 6.1 feature windows."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from memeradar_application.correlation import (
    CORRELATION_VERSION,
    CorrelationSnapshot,
    CorrelationWindowFeatures,
)
from memeradar_application.feature_windows import (
    FEATURE_WINDOW_NAMES,
    FEATURE_WINDOWS_VERSION,
    FeatureWindowAggregator,
)
from memeradar_application.holder_graph import HolderConcentrationSnapshot
from memeradar_domain import (
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    TokenIdentity,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "fixtures" / "providers" / "feature_windows" / "replay.json"


def load_fixture() -> dict[str, object]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_feature_window_fixture_is_credential_free_and_has_canonical_windows() -> None:
    payload = load_fixture()
    encoded = json.dumps(payload).lower()
    for forbidden in ("api_key", "access_token", "private_key", "seed_phrase", "session_token"):
        assert forbidden not in encoded
    expected = payload["expected"]
    assert isinstance(expected, dict)
    assert tuple(expected["windows"]) == FEATURE_WINDOW_NAMES
    assert payload["redacted"] is True


def _build_inputs(payload: dict[str, object]) -> tuple[UUID, TokenIdentity, CorrelationSnapshot]:
    candidate_id = UUID(str(payload["candidate_id"]))
    token = TokenIdentity(mint_address=str(payload["token"]["mint_address"]))
    as_of = datetime.fromisoformat(str(payload["as_of"]))
    fixture_config = str(payload["config_hash"])
    source = Provenance(
        provider="feature-fixture",
        source_id="correlation:feature-fixture",
        observed_at=as_of,
        parser_version="feature-fixture-v1",
    )
    windows: dict[str, CorrelationWindowFeatures] = {}
    rows = payload["windows"]
    assert isinstance(rows, dict)
    durations = {
        "1m": timedelta(minutes=1),
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
    }
    for name in FEATURE_WINDOW_NAMES:
        row = rows[name]
        assert isinstance(row, dict)
        values = {
            key: Decimal(value) if isinstance(value, str) else value for key, value in row.items()
        }
        windows[name] = CorrelationWindowFeatures(
            window_name=name,
            start_at=as_of - durations[name],
            end_at=as_of,
            event_count=int(values["event_count"]),
            social_mention_count=int(values["social_mention_count"]),
            market_observation_count=int(values["market_observation_count"]),
            unique_buyers=int(values["unique_buyers"]),
            unique_sellers=int(values["unique_sellers"]),
            unique_makers=int(values["unique_makers"]),
            buyer_arrival_rate=values["buyer_arrival_rate"],
            buy_sell_ratio=values["buy_sell_ratio"],
            net_flow=values["net_flow"],
            net_flow_acceleration=values["net_flow_acceleration"],
            liquidity=values["liquidity"],
            liquidity_delta=values["liquidity_delta"],
            liquidity_acceleration=values["liquidity_acceleration"],
            weighted_entry_quality=values["weighted_entry_quality"],
            independent_entry_clusters=int(values["independent_entry_clusters"]),
            transaction_count=int(values["event_count"]),
            source_independence_count=3,
            source_diversity_confidence=Decimal("1"),
            sample_sufficient=True,
            confidence=Decimal("0.88"),
            quality_state=QualityState.FRESH,
            reason_codes=(ReasonCode("CORRELATION_WINDOW_BUILT"),),
        )
    return (
        candidate_id,
        token,
        CorrelationSnapshot(
            token=token,
            as_of=as_of,
            expires_at=as_of + timedelta(minutes=15),
            windows=windows,
            risk_disposition=RiskDisposition.PASS,
            risk_quality_state=QualityState.FRESH,
            source_independence_count=3,
            source_diversity_confidence=Decimal("1"),
            provenance=(source,),
            evidence_refs=(source.source_id,),
            reason_codes=(ReasonCode("CORRELATION_SNAPSHOT_BUILT"),),
            confidence=Decimal("0.88"),
            config_hash=fixture_config,
            quality_state=QualityState.FRESH,
            version=CORRELATION_VERSION,
        ),
    )


def _risk(candidate_id: UUID, as_of: datetime, config_hash: str) -> RiskAssessment:
    return RiskAssessment(
        candidate_id=candidate_id,
        as_of=as_of - timedelta(seconds=2),
        expires_at=as_of + timedelta(minutes=5),
        risk_version="token-security-v1",
        disposition=RiskDisposition.PASS,
        hard_blocks=(),
        warnings=(),
        penalties={},
        evidence_refs=("risk:feature-fixture",),
        reason_codes=(ReasonCode("RISK_EVIDENCE_FRESH"),),
        confidence=Decimal("0.95"),
        config_hash=config_hash,
        critical_evidence_state=QualityState.FRESH,
    )


def _holder(token: TokenIdentity, as_of: datetime, config_hash: str) -> HolderConcentrationSnapshot:
    return HolderConcentrationSnapshot(
        token=token,
        as_of=as_of - timedelta(seconds=2),
        expires_at=as_of + timedelta(minutes=5),
        total_holder_count=100,
        top1=Decimal("0.12"),
        top5=Decimal("0.30"),
        top10=Decimal("0.42"),
        clustered_top=Decimal("0.48"),
        holders=(),
        excluded_addresses=(),
        provenance=(
            Provenance(
                provider="feature-fixture",
                source_id="holder:feature-fixture",
                observed_at=as_of - timedelta(seconds=2),
                parser_version="feature-fixture-v1",
            ),
        ),
        evidence_refs=("holder:feature-fixture",),
        reason_codes=(ReasonCode("HOLDER_DATA_FRESH"),),
        confidence=Decimal("0.84"),
        config_hash=config_hash,
        quality_state=QualityState.FRESH,
    )


def _projection(values):
    return tuple(
        (
            value.id,
            value.values,
            value.provenance,
            value.quality_state,
            value.completeness,
            value.confidence,
        )
        for value in values
    )


def test_feature_window_fixture_replays_in_reverse_order_deterministically() -> None:
    payload = load_fixture()
    candidate_id, token, correlation = _build_inputs(payload)
    as_of = correlation.as_of
    config_hash = str(payload["config_hash"])
    builder = FeatureWindowAggregator()
    first = builder.build(
        candidate_id,
        correlation,
        risk_assessment=_risk(candidate_id, as_of, config_hash),
        holder_snapshot=_holder(token, as_of, config_hash),
        now=as_of,
        config_hash=config_hash,
    )
    reverse = builder.build(
        candidate_id,
        correlation,
        risk_assessment=_risk(candidate_id, as_of, config_hash),
        holder_snapshot=_holder(token, as_of, config_hash),
        now=as_of,
        config_hash=config_hash,
    )
    expected = payload["expected"]
    assert isinstance(expected, dict)
    assert tuple(value.values["window"] for value in first) == FEATURE_WINDOW_NAMES
    assert _projection(first) == _projection(reverse)
    assert all(value.feature_version == FEATURE_WINDOWS_VERSION for value in first)
    assert all(value.quality_state is QualityState.FRESH for value in first)
    assert all(value.completeness == Decimal(str(expected["completeness"])) for value in first)
    assert all(
        set(value.values["components"]) == set(expected["component_names"]) for value in first
    )
    assert all(value.values["execution_eligible"] is False for value in first)
