"""Keyless golden replay contracts for external-wallet extension E6.2."""

import asyncio
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from memeradar_application.external_wallet import (
    ExternalWalletIntelligenceRequest,
    ExternalWalletLabel,
    ExternalWalletReconciler,
    ExternalWalletTokenSignal,
)
from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_application.wallet_scoring import SmartWalletScore
from memeradar_application.wallet_tracking import WalletTier
from memeradar_domain import Provenance, QualityState, TokenIdentity
from memeradar_providers.external_wallet import FixtureExternalWalletIntelligenceAdapter

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "fixtures" / "providers" / "external_wallet" / "replay.json"
NOW = datetime(2026, 8, 30, 20, 0, tzinfo=UTC)
WALLET_A = "11111111111111111111111111111112"
WALLET_B = "11111111111111111111111111111113"


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


def token_from_row(row: Mapping[str, object]) -> TokenIdentity:
    mint_address = str(row["mint_address"])
    return TokenIdentity(mint_address=mint_address, id=uuid5(NAMESPACE_URL, mint_address))


def item_provenance(source_id: str, source: str, observed_at: datetime) -> Provenance:
    return Provenance(
        provider=source,
        source_id=source_id,
        observed_at=observed_at,
        parser_version="external-wallet-fixture-v1",
    )


def build_labels(rows: Sequence[object]) -> tuple[ExternalWalletLabel, ...]:
    result: list[ExternalWalletLabel] = []
    for raw in rows:
        assert isinstance(raw, Mapping)
        observed_at = datetime.fromisoformat(str(raw["observed_at"]))
        result.append(
            ExternalWalletLabel(
                wallet_address=str(raw["wallet_address"]),
                label=str(raw["label"]),
                source=str(raw["source"]),
                source_confidence=Decimal(str(raw["source_confidence"])),
                observed_at=observed_at,
                expires_at=datetime.fromisoformat(str(raw["expires_at"])),
                raw_source_id=str(raw["raw_source_id"]),
                provenance=item_provenance(
                    str(raw["raw_source_id"]), str(raw["source"]), observed_at
                ),
                quality_state=QualityState(str(raw.get("quality_state", "FRESH"))),
                evidence_refs=(str(raw["raw_source_id"]),),
            )
        )
    return tuple(result)


def build_signals(
    rows: Sequence[object], token: TokenIdentity
) -> tuple[ExternalWalletTokenSignal, ...]:
    result: list[ExternalWalletTokenSignal] = []
    for raw in rows:
        assert isinstance(raw, Mapping)
        observed_at = datetime.fromisoformat(str(raw["observed_at"]))
        result.append(
            ExternalWalletTokenSignal(
                token=token,
                wallet_address=(
                    None if raw.get("wallet_address") is None else str(raw["wallet_address"])
                ),
                signal_type=str(raw["signal_type"]),
                source=str(raw["source"]),
                source_confidence=Decimal(str(raw["source_confidence"])),
                observed_at=observed_at,
                expires_at=datetime.fromisoformat(str(raw["expires_at"])),
                raw_source_id=str(raw["raw_source_id"]),
                provenance=item_provenance(
                    str(raw["raw_source_id"]), str(raw["source"]), observed_at
                ),
                tracked_supply_pct=(
                    None
                    if raw.get("tracked_supply_pct") is None
                    else Decimal(str(raw["tracked_supply_pct"]))
                ),
                bundle_confidence=(
                    None
                    if raw.get("bundle_confidence") is None
                    else Decimal(str(raw["bundle_confidence"]))
                ),
                side_wallet_cluster_confidence=(
                    None
                    if raw.get("side_wallet_cluster_confidence") is None
                    else Decimal(str(raw["side_wallet_cluster_confidence"]))
                ),
                security_flags=tuple(str(value) for value in raw.get("security_flags", [])),
                quality_state=QualityState(str(raw.get("quality_state", "FRESH"))),
                evidence_refs=(str(raw["raw_source_id"]),),
            )
        )
    return tuple(result)


def score(wallet: str, *, qualified: bool = True) -> SmartWalletScore:
    tier = WalletTier.TIER_B if qualified else WalletTier.CANDIDATE
    return SmartWalletScore(
        wallet_address=wallet,
        label="internal fixture wallet",
        registry_tier=tier,
        recommended_tier=tier,
        as_of=NOW - timedelta(seconds=30),
        expires_at=NOW + timedelta(minutes=4),
        score=Decimal("80") if qualified else Decimal("40"),
        confidence=Decimal("0.9") if qualified else Decimal("0.4"),
        sample_count=10,
        known_outcome_count=10,
        win_rate=Decimal("0.8"),
        realized_pnl=Decimal("10"),
        median_return=Decimal("0.2"),
        early_entry_rate=Decimal("0.8"),
        rug_avoidance_rate=Decimal("1"),
        manipulation_penalty=Decimal("0"),
        components={"win_rate": Decimal("80")},
        penalties={},
        provenance=(
            item_provenance(
                f"internal:{wallet}",
                "internal-fixture",
                NOW - timedelta(seconds=30),
            ),
        ),
        evidence_refs=(f"internal:{wallet}",),
        reason_codes=("SMART_WALLET_SCORE_CALCULATED",),
        config_hash="external-wallet-fixture",
        quality_state=QualityState.FRESH,
    )


def test_external_wallet_fixture_replays_deterministically_and_is_credential_free() -> None:
    payload = load_fixture()
    assert_credential_free(payload)
    tokens = payload["tokens"]
    assert isinstance(tokens, Mapping)
    token = token_from_row(tokens["meme"])
    scenarios = payload["scenarios"]
    assert isinstance(scenarios, Mapping)

    scenario = scenarios["agreement"]
    assert isinstance(scenario, Mapping)
    labels = build_labels(scenario["labels"])
    signals = build_signals(scenario["token_signals"], token)
    reconciler = ExternalWalletReconciler()
    first = reconciler.reconcile(
        token,
        labels=labels,
        token_signals=signals,
        internal_scores=(score(WALLET_A), score(WALLET_B)),
        now=NOW,
        config_hash="external-wallet-fixture",
    )
    reverse = reconciler.reconcile(
        token,
        labels=tuple(reversed(labels)),
        token_signals=tuple(reversed(signals)),
        internal_scores=(score(WALLET_B), score(WALLET_A)),
        now=NOW,
        config_hash="external-wallet-fixture",
    )
    assert first == reverse
    assert first.version == "external-wallet-cross-validation-v1"
    assert first.external_label_confidence > Decimal("0")
    assert first.execution_eligible(NOW) is False


def test_external_wallet_fixture_covers_stale_disagreement_and_provider_removal() -> None:
    payload = load_fixture()
    tokens = payload["tokens"]
    scenarios = payload["scenarios"]
    assert isinstance(tokens, Mapping) and isinstance(scenarios, Mapping)
    token = token_from_row(tokens["meme"])
    reconciler = ExternalWalletReconciler()

    stale = scenarios["stale"]
    assert isinstance(stale, Mapping)
    stale_result = reconciler.reconcile(
        token,
        labels=build_labels(stale["labels"]),
        internal_scores=(score(WALLET_A),),
        now=NOW,
        config_hash="external-wallet-fixture",
    )
    assert stale_result.confidence_bonus == Decimal("0")
    assert "EXTERNAL_LABEL_STALE" in {reason.code for reason in stale_result.reason_codes}

    disagreement = scenarios["disagreement"]
    assert isinstance(disagreement, Mapping)
    disagreement_result = reconciler.reconcile(
        token,
        labels=build_labels(disagreement["labels"]),
        internal_scores=(score(WALLET_A),),
        now=NOW,
        config_hash="external-wallet-fixture",
    )
    assert disagreement_result.quality_state is QualityState.CONFLICTED
    assert disagreement_result.confidence_bonus == Decimal("0")
    assert "CONFLICTED_EXTERNAL_WALLET_LABEL" in {
        reason.code for reason in disagreement_result.reason_codes
    }

    without_external = reconciler.reconcile(
        token,
        internal_scores=(score(WALLET_A),),
        now=NOW,
        config_hash="external-wallet-fixture",
    )
    assert without_external.external_label_confidence == Decimal("0")
    assert without_external.confidence_bonus == Decimal("0")
    assert without_external.internal_score_refs == (f"internal:{WALLET_A}",)


def test_fixture_adapter_implements_request_port_without_network() -> None:
    payload = load_fixture()
    tokens = payload["tokens"]
    scenarios = payload["scenarios"]
    assert isinstance(tokens, Mapping) and isinstance(scenarios, Mapping)
    token = token_from_row(tokens["meme"])
    scenario = scenarios["agreement"]
    assert isinstance(scenario, Mapping)
    adapter = FixtureExternalWalletIntelligenceAdapter(
        labels=build_labels(scenario["labels"]),
        token_signals=build_signals(scenario["token_signals"], token),
    )
    request = ExternalWalletIntelligenceRequest(
        context=ProviderRequestContext(
            correlation_id="external-wallet-fixture",
            requested_at=NOW,
            deadline_at=NOW + timedelta(seconds=5),
        ),
        token=token,
        wallet_addresses=(WALLET_A,),
    )
    result = asyncio.run(adapter.lookup(request))
    assert result.provider == adapter.provider_name
    assert {item.wallet_address for item in result.labels} == {WALLET_A}
    assert result.token_signals
    assert result.execution_eligible(NOW) is False
