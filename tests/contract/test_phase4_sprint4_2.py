"""Keyless replay contract for Phase 4 Sprint 4.2 SmartWalletScore."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import yaml

from memeradar_application.wallet_scoring import (
    SmartWalletScorer,
    SmartWalletScoringPolicy,
)
from memeradar_application.wallet_tracking import (
    WalletRoundTrip,
    WalletTier,
    WalletTrackingSnapshot,
)
from memeradar_domain import Provenance, QualityState, TokenIdentity

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 27, 17, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def load_fixture(name: str) -> dict[str, object]:
    path = ROOT / "fixtures" / "providers" / "wallet_scoring" / name
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
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
    if isinstance(value, dict):
        for key, nested in value.items():
            assert str(key).lower() not in credential_names
            assert_credential_free(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_credential_free(nested)


def build_snapshot(
    token: TokenIdentity,
    row: dict[str, object],
) -> WalletTrackingSnapshot:
    raw_trips = row["round_trips"]
    assert isinstance(raw_trips, list)
    trips: list[WalletRoundTrip] = []
    wallet = str(row["wallet_address"])
    for raw_trip in raw_trips:
        assert isinstance(raw_trip, dict)
        buy_at = datetime.fromisoformat(str(raw_trip["buy_at"]))
        sell_at = datetime.fromisoformat(str(raw_trip["sell_at"]))
        cost_raw = raw_trip["cost_basis"]
        proceeds_raw = raw_trip["proceeds"]
        cost = None if cost_raw is None else Decimal(str(cost_raw))
        proceeds = None if proceeds_raw is None else Decimal(str(proceeds_raw))
        realized = None if cost is None or proceeds is None else proceeds - cost
        source_id = str(raw_trip["source_id"])
        trips.append(
            WalletRoundTrip(
                token=token,
                wallet_address=wallet,
                quantity=Decimal("1"),
                buy_at=buy_at,
                sell_at=sell_at,
                cost_basis=cost,
                proceeds=proceeds,
                realized_pnl=realized,
                hold_seconds=Decimal(str((sell_at - buy_at).total_seconds())),
                token_age_at_entry_seconds=(
                    None
                    if raw_trip["token_age_at_entry_seconds"] is None
                    else Decimal(str(raw_trip["token_age_at_entry_seconds"]))
                ),
                rug_exposure=raw_trip["rug_exposure"],
                provenance=(
                    Provenance(
                        provider="wallet-scoring-fixture",
                        source_id=source_id,
                        observed_at=sell_at,
                        parser_version="wallet-scoring-fixture-v1",
                    ),
                ),
                evidence_refs=(source_id,),
                reason_codes=("FIFO_MATCHED",),
            )
        )
    quality_state = QualityState(str(row["quality_state"]))
    as_of = datetime.fromisoformat(str(row["as_of"]))
    known_pnl = [trip.realized_pnl for trip in trips]
    realized_pnl = (
        None
        if any(value is None for value in known_pnl)
        else sum((value for value in known_pnl if value is not None), Decimal("0"))
    )
    first_entry = min((trip.buy_at for trip in trips), default=None)
    rug_values = {trip.rug_exposure for trip in trips}
    rug_exposure = next(iter(rug_values)) if len(rug_values) == 1 else None
    return WalletTrackingSnapshot(
        token=token,
        wallet_address=wallet,
        label=str(row["label"]),
        tier=WalletTier(str(row["tier"])),
        as_of=as_of,
        expires_at=as_of + timedelta(minutes=5),
        buy_count=len(trips),
        sell_count=len(trips),
        matched_sell_count=len(trips),
        open_quantity=Decimal("0"),
        open_cost_basis=Decimal("0"),
        unmatched_sell_quantity=Decimal("0"),
        realized_pnl=realized_pnl,
        round_trips=tuple(trips),
        first_entry_at=first_entry,
        token_age_at_first_entry_seconds=(trips[0].token_age_at_entry_seconds if trips else None),
        median_hold_seconds=(
            sum((trip.hold_seconds for trip in trips), Decimal("0")) / Decimal(len(trips))
            if trips
            else None
        ),
        rug_exposure=rug_exposure,
        provenance=tuple(value for trip in trips for value in trip.provenance),
        evidence_refs=tuple(value for trip in trips for value in trip.evidence_refs),
        reason_codes=("WALLET_ACTIVITY_RECONSTRUCTED",),
        confidence=Decimal(str(row["confidence"])),
        config_hash="wallet-scoring-fixture",
        quality_state=quality_state,
    )


def test_smart_wallet_score_fixtures_replay_deterministically() -> None:
    snapshots_payload = load_fixture("snapshots.json")
    penalties_payload = load_fixture("penalties.json")
    assert_credential_free(snapshots_payload)
    assert_credential_free(penalties_payload)
    raw_snapshots = snapshots_payload["snapshots"]
    raw_penalties = penalties_payload["manipulation_penalties"]
    assert isinstance(raw_snapshots, list)
    assert isinstance(raw_penalties, dict)
    token = TokenIdentity(mint_address=MINT, id=uuid4())
    snapshots = tuple(build_snapshot(token, row) for row in raw_snapshots if isinstance(row, dict))
    penalties = {str(address): Decimal(str(value)) for address, value in raw_penalties.items()}
    scorer = SmartWalletScorer(
        policy=SmartWalletScoringPolicy(
            minimum_sample_count=3,
            tier_b_minimum_sample_count=3,
            tier_a_minimum_sample_count=3,
            tier_a_minimum_confidence=Decimal("0.6"),
            tier_b_minimum_confidence=Decimal("0.6"),
        ),
    )
    scores = scorer.score(
        snapshots,
        now=NOW,
        config_hash="phase4-sprint4-2-fixture",
        manipulation_penalties=penalties,
    )
    by_wallet = {score.wallet_address: score for score in scores}
    high = by_wallet["11111111111111111111111111111112"]
    tiny = by_wallet["11111111111111111111111111111113"]
    incomplete = by_wallet["11111111111111111111111111111114"]
    boundary = by_wallet["11111111111111111111111111111115"]

    assert len(scores) == 4
    assert high.sample_count == 3
    assert high.known_outcome_count == 3
    assert high.realized_pnl == Decimal("17")
    assert high.win_rate == Decimal("1")
    assert high.median_return == Decimal("0.5")
    assert high.early_entry_rate == Decimal("1")
    assert high.rug_avoidance_rate == Decimal("1")
    assert high.manipulation_penalty == Decimal("3")
    assert high.recommended_tier is WalletTier.TIER_A
    assert "DUPLICATE_OUTCOME_DEDUPED" in {reason.code for reason in high.reason_codes}
    assert tiny.sample_count == 1
    assert tiny.recommended_tier is WalletTier.CANDIDATE
    assert "TIER_A_SAMPLE_GATE" in {reason.code for reason in tiny.reason_codes}
    assert incomplete.quality_state is QualityState.UNKNOWN
    assert incomplete.early_entry_rate is None
    assert incomplete.rug_avoidance_rate is None
    assert incomplete.recommended_tier is WalletTier.CANDIDATE
    assert boundary.sample_count == 1
    assert boundary.quality_state is QualityState.INVALID
    assert boundary.recommended_tier is WalletTier.CANDIDATE
    assert "OUTCOME_OUTSIDE_WINDOW" in {reason.code for reason in boundary.reason_codes}
    assert "FUTURE_OUTCOME_EXCLUDED" in {reason.code for reason in boundary.reason_codes}
    assert all(score.execution_eligible(NOW) is False for score in scores)

    replay = scorer.score(
        snapshots,
        now=NOW,
        config_hash="phase4-sprint4-2-fixture",
        manipulation_penalties=penalties,
    )
    assert replay == scores


def test_smart_wallet_score_fixture_contract_preserves_safe_modes_and_seam() -> None:
    compose = yaml.safe_load(
        (ROOT / "infra" / "compose" / "docker-compose.yml").read_text(encoding="utf-8")
    )
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"
    source = (
        ROOT / "packages" / "application" / "src" / "memeradar_application" / "wallet_scoring.py"
    ).read_text(encoding="utf-8")
    assert "memeradar_providers" not in source
    assert "httpx" not in source
    assert "sign(" not in source.lower()
    assert "submit(" not in source.lower()
    assert (ROOT / "fixtures" / "providers" / "wallet_scoring" / "snapshots.json").is_file()
    assert (ROOT / "fixtures" / "providers" / "wallet_scoring" / "penalties.json").is_file()
