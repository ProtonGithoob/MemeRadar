"""Keyless golden replay contracts for correlation extension E6.0."""

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import yaml

from memeradar_application.confluence import (
    SmartMoneyEvent,
    SmartMoneyEventType,
    TokenSmartMoneyScore,
)
from memeradar_application.correlation import (
    CORRELATION_VERSION,
    CorrelationWindowBuilder,
)
from memeradar_application.provider_contracts import SocialMention
from memeradar_application.wallet_tracking import WalletAction, WalletActivity
from memeradar_domain import (
    Observation,
    Provenance,
    QualityState,
    RiskAssessment,
    RiskDisposition,
    TokenIdentity,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "fixtures" / "providers" / "correlation" / "replay.json"
COMPOSE_PATH = ROOT / "infra" / "compose" / "docker-compose.yml"
NOW = datetime(2026, 8, 30, 20, 0, tzinfo=UTC)


def load_fixture() -> Mapping[str, object]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, Mapping)
    return payload


def assert_credential_free(value: object) -> None:
    credential_names = {
        "api_key",
        "access_token",
        "authorization",
        "cookie",
        "private_key",
        "seed_phrase",
        "session_token",
    }
    if isinstance(value, Mapping):
        for key, nested in value.items():
            assert str(key).lower() not in credential_names
            assert_credential_free(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_credential_free(nested)


def build_tokens(payload: Mapping[str, object]) -> dict[str, TokenIdentity]:
    raw_tokens = payload["tokens"]
    assert isinstance(raw_tokens, Mapping)
    return {
        key: TokenIdentity(
            mint_address=str(row["mint_address"]),
            id=uuid5(NAMESPACE_URL, str(row["mint_address"])),
        )
        for key, row in raw_tokens.items()
        if isinstance(row, Mapping)
    }


def provenance(source_id: str, provider: str, observed_at: datetime) -> Provenance:
    return Provenance(
        provider=provider,
        source_id=source_id,
        observed_at=observed_at,
        parser_version="correlation-fixture-v1",
    )


def observations(
    rows: Sequence[Mapping[str, object]],
    token: TokenIdentity,
) -> tuple[Observation, ...]:
    result: list[Observation] = []
    for row in rows:
        occurred_at = datetime.fromisoformat(str(row["occurred_at"]))
        observed_at = datetime.fromisoformat(str(row.get("observed_at", NOW)))
        ingested_at = datetime.fromisoformat(str(row.get("ingested_at", observed_at)))
        provider = str(row.get("provider", "fixture"))
        payload = {"mint_address": token.mint_address}
        raw_payload = row.get("payload", {})
        assert isinstance(raw_payload, Mapping)
        payload.update(raw_payload)
        result.append(
            Observation(
                kind=str(row["kind"]),
                provenance=provenance(str(row["source_id"]), provider, observed_at),
                occurred_at=occurred_at,
                observed_at=observed_at,
                ingested_at=ingested_at,
                quality_state=QualityState(str(row.get("quality_state", "FRESH"))),
                normalized_payload=payload,
                token_id=token.id,
            )
        )
    return tuple(result)


def mentions(
    rows: Sequence[Mapping[str, object]],
    token: TokenIdentity,
) -> tuple[SocialMention, ...]:
    result: list[SocialMention] = []
    for row in rows:
        posted_at = datetime.fromisoformat(str(row["posted_at"]))
        observed_at = datetime.fromisoformat(str(row.get("observed_at", NOW)))
        metrics = row.get("metrics", {})
        assert isinstance(metrics, Mapping)
        result.append(
            SocialMention(
                provenance=provenance(str(row["source_id"]), "social-fixture", observed_at),
                author_id=str(row["author_id"]),
                posted_at=posted_at,
                observed_at=observed_at,
                ingested_at=datetime.fromisoformat(str(row.get("ingested_at", observed_at))),
                text_fingerprint=str(row["text_fingerprint"]),
                metrics=metrics,
                token_id=token.id,
                referenced_mint=token.mint_address,
            )
        )
    return tuple(result)


def wallet_activities(
    rows: Sequence[Mapping[str, object]],
    token: TokenIdentity,
) -> tuple[WalletActivity, ...]:
    result: list[WalletActivity] = []
    for row in rows:
        occurred_at = datetime.fromisoformat(str(row["occurred_at"]))
        observed_at = datetime.fromisoformat(str(row.get("observed_at", NOW)))
        result.append(
            WalletActivity(
                token=token,
                wallet_address=str(row["wallet_address"]),
                action=WalletAction(str(row["action"])),
                quantity=Decimal(str(row["quantity"])),
                occurred_at=occurred_at,
                observed_at=observed_at,
                ingested_at=datetime.fromisoformat(str(row.get("ingested_at", observed_at))),
                provenance=provenance(str(row["source_id"]), "wallet-fixture", observed_at),
                quote_amount=Decimal(str(row["quote_amount"]))
                if row.get("quote_amount") is not None
                else None,
            )
        )
    return tuple(result)


def smart_money_score(
    rows: Sequence[Mapping[str, object]],
    token: TokenIdentity,
) -> TokenSmartMoneyScore:
    events: list[SmartMoneyEvent] = []
    clusters: set[str] = set()
    for row in rows:
        occurred_at = datetime.fromisoformat(str(row["occurred_at"]))
        cluster_id = str(row["cluster_id"])
        clusters.add(cluster_id)
        source_id = str(row["source_id"])
        events.append(
            SmartMoneyEvent(
                token=token,
                event_type=SmartMoneyEventType(str(row["event_type"])),
                cluster_id=cluster_id,
                wallet_addresses=(str(row["wallet_address"]),),
                occurred_at=occurred_at,
                observed_at=NOW,
                ingested_at=NOW,
                quantity=None,
                score_contribution=Decimal(str(row["score_contribution"])),
                provenance=(provenance(source_id, "smart-money-fixture", NOW),),
                evidence_refs=(source_id,),
                reason_codes=("SMART_MONEY_ENTRY",),
                quality_state=QualityState.FRESH,
            )
        )
    return TokenSmartMoneyScore(
        token=token,
        as_of=NOW - timedelta(seconds=1),
        expires_at=NOW + timedelta(minutes=5),
        score=Decimal("70"),
        confidence=Decimal("0.8"),
        components={"entry_quality": Decimal("70")},
        penalties={},
        qualified_wallet_count=len(events),
        independent_cluster_count=len(clusters),
        entry_wallet_count=len(events),
        exit_wallet_count=0,
        entry_cluster_count=len(clusters),
        exit_cluster_count=0,
        confluence_event_count=0,
        distribution_event_count=0,
        confluence_detected=False,
        events=tuple(events),
        provenance=(provenance("smart-score", "smart-money-fixture", NOW),),
        evidence_refs=("smart-score",),
        reason_codes=("SMART_MONEY_SCORE",),
        config_hash="e6-0-fixture",
        quality_state=QualityState.FRESH,
    )


def risk(row: Mapping[str, object], scenario_name: str) -> RiskAssessment:
    disposition = RiskDisposition(str(row["disposition"]))
    return RiskAssessment(
        candidate_id=uuid5(NAMESPACE_URL, f"correlation:{scenario_name}"),
        as_of=NOW - timedelta(seconds=1),
        expires_at=NOW + timedelta(minutes=5),
        risk_version="correlation-fixture-risk-v1",
        disposition=disposition,
        hard_blocks=(),
        warnings=("CREATOR_RELATED_SELL_PRESSURE",) if disposition is RiskDisposition.WARN else (),
        penalties={},
        evidence_refs=(str(row["source_id"]),),
        reason_codes=("RISK_EVIDENCE_FRESH",),
        confidence=Decimal("0.9"),
        config_hash="e6-0-fixture",
        critical_evidence_state=QualityState.FRESH,
    )


def build_snapshot(
    payload: Mapping[str, object],
    tokens: Mapping[str, TokenIdentity],
    scenario_name: str,
    *,
    reverse: bool = False,
    extra_observations: Sequence[Observation] = (),
):
    scenarios = payload["scenarios"]
    assert isinstance(scenarios, Mapping)
    scenario = scenarios[scenario_name]
    assert isinstance(scenario, Mapping)
    token = tokens[str(scenario["token"])]
    raw_observations = scenario.get("observations", [])
    raw_mentions = scenario.get("mentions", [])
    raw_wallets = scenario.get("wallet_activities", [])
    raw_smart = scenario.get("smart_money", [])
    assert isinstance(raw_observations, Sequence) and not isinstance(raw_observations, str)
    assert isinstance(raw_mentions, Sequence) and not isinstance(raw_mentions, str)
    assert isinstance(raw_wallets, Sequence) and not isinstance(raw_wallets, str)
    assert isinstance(raw_smart, Sequence) and not isinstance(raw_smart, str)
    observation_rows = tuple(row for row in raw_observations if isinstance(row, Mapping))
    mention_rows = tuple(row for row in raw_mentions if isinstance(row, Mapping))
    wallet_rows = tuple(row for row in raw_wallets if isinstance(row, Mapping))
    smart_rows = tuple(row for row in raw_smart if isinstance(row, Mapping))
    built_observations = list(observations(observation_rows, token))
    duplicate_source_id = scenario.get("duplicate_observation_source_id")
    if isinstance(duplicate_source_id, str):
        duplicate = next(
            item for item in built_observations if item.provenance.source_id == duplicate_source_id
        )
        built_observations.append(duplicate)
    built_observations.extend(extra_observations)
    built_mentions = mentions(mention_rows, token)
    built_wallets = wallet_activities(wallet_rows, token)
    scores = (
        (smart_money_score(smart_rows, token),)
        if smart_rows
        else ()
    )
    raw_risk = scenario["risk"]
    assert isinstance(raw_risk, Mapping)
    creator_wallets = tuple(str(value) for value in scenario.get("creator_wallets", ()))
    related_wallets = tuple(str(value) for value in scenario.get("related_wallets", ()))
    builder = CorrelationWindowBuilder()
    if reverse:
        built_observations.reverse()
        built_mentions = tuple(reversed(built_mentions))
        built_wallets = tuple(reversed(built_wallets))
        scores = tuple(reversed(scores))
    return builder.build(
        token,
        observations=tuple(built_observations),
        mentions=built_mentions,
        wallet_activities=built_wallets,
        smart_money_scores=scores,
        risk_assessment=risk(raw_risk, scenario_name),
        creator_wallets=creator_wallets,
        related_wallets=related_wallets,
        now=NOW,
        config_hash="e6-0-fixture",
    )


def test_golden_scenarios_replay_in_event_time_and_remain_advisory() -> None:
    payload = load_fixture()
    assert_credential_free(payload)
    tokens = build_tokens(payload)
    assert set(tokens) == {
        "organic",
        "wash",
        "smart",
        "social",
        "creator",
    }

    organic = build_snapshot(payload, tokens, "organic_acceleration")
    organic_replay = build_snapshot(
        payload,
        tokens,
        "organic_acceleration",
        reverse=True,
    )
    assert organic == organic_replay
    assert organic.version == CORRELATION_VERSION
    assert organic.windows["15s"].net_flow_acceleration == Decimal("3")
    assert organic.windows["15s"].source_independence_count >= 3
    assert organic.windows["15s"].protocol_event_counts["bonding_curve_progress"] == 1
    assert organic.execution_eligible(NOW) is False

    wash = build_snapshot(payload, tokens, "wash_burst")
    wash_features = wash.windows["15s"]
    assert wash_features.repeated_size_ratio == Decimal("1")
    assert wash_features.circular_flow_ratio == Decimal("1")
    assert wash_features.rapid_round_trip_ratio > Decimal("0")
    assert wash.execution_eligible(NOW) is False

    smart = build_snapshot(payload, tokens, "smart_wallet_only_burst")
    smart_features = smart.windows["15s"]
    assert smart_features.independent_entry_clusters == 2
    assert smart_features.weighted_entry_quality == Decimal("70")
    assert smart_features.source_independence_count == 1
    assert smart_features.quality_state is QualityState.UNKNOWN
    assert smart.execution_eligible(NOW) is False

    social = build_snapshot(payload, tokens, "social_only_burst")
    social_features = social.windows["5s"]
    assert social_features.social_mention_count == 2
    assert social_features.sample_sufficient is False
    assert social_features.source_independence_count == 1
    assert social_features.confidence < Decimal("0.5")
    assert social.quality_state is QualityState.UNKNOWN

    creator = build_snapshot(payload, tokens, "creator_dump")
    creator_features = creator.windows["15s"]
    assert creator_features.creator_related_sell_pressure == Decimal("0.6")
    assert creator.risk_disposition is RiskDisposition.WARN
    assert creator.execution_eligible(NOW) is False


def test_future_fixture_evidence_is_excluded_and_invalidates_confidence() -> None:
    payload = load_fixture()
    tokens = build_tokens(payload)
    baseline = build_snapshot(payload, tokens, "social_only_burst")
    future_row = payload["future_observation"]
    assert isinstance(future_row, Mapping)
    future = observations((future_row,), tokens["social"])[0]
    with_future = build_snapshot(
        payload,
        tokens,
        "social_only_burst",
        extra_observations=(future,),
    )

    assert (
        with_future.windows["5s"].social_mention_count
        == baseline.windows["5s"].social_mention_count
    )
    assert with_future.windows["5s"].transaction_count == 0
    assert with_future.quality_state is QualityState.INVALID
    assert with_future.confidence == Decimal("0")
    assert "CORRELATION_FUTURE_EVIDENCE" in {
        reason.code for reason in with_future.reason_codes
    }


def test_fixture_contract_is_provider_free_and_preserves_safe_modes() -> None:
    source = (
        ROOT
        / "packages"
        / "application"
        / "src"
        / "memeradar_application"
        / "correlation.py"
    ).read_text(encoding="utf-8")
    assert "memeradar_providers" not in source
    assert "httpx" not in source
    assert "sign(" not in source.lower()
    assert "submit(" not in source.lower()
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_fixture_has_no_network_or_credential_material() -> None:
    raw = FIXTURE_PATH.read_text(encoding="utf-8")
    assert "https://" not in raw.lower()
    assert "authorization" not in raw.lower()
    assert "private_key" not in raw.lower()
