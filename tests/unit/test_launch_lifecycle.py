"""Deterministic launch lifecycle and route-state contracts."""

from datetime import UTC, datetime, timedelta

from memeradar_application.launch_lifecycle import (
    GraduationAwareRouteAnalyzer,
    LaunchLifecycleState,
    RouteState,
)
from memeradar_domain import Chain, Observation, Provenance, QualityState, TokenIdentity

NOW = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)
TOKEN = "0x" + "ab" * 20
POOL = "0x" + "cd" * 20


def _observation(
    source_id: str,
    occurred_at: datetime,
    payload: dict[str, object],
    *,
    quality_state: QualityState = QualityState.FRESH,
) -> Observation:
    return Observation(
        kind=str(payload.pop("kind", "protocol.lifecycle")),
        provenance=Provenance(
            provider=str(payload.pop("provider", "fixture")),
            source_id=source_id,
            observed_at=occurred_at,
            parser_version="fixture-v1",
        ),
        occurred_at=occurred_at,
        observed_at=occurred_at,
        ingested_at=occurred_at,
        quality_state=quality_state,
        normalized_payload=payload,
    )


def _token() -> TokenIdentity:
    return TokenIdentity(TOKEN, chain=Chain.ROBINHOOD, token_program="erc20")


def test_bonding_token_is_not_classified_as_no_route_and_graduation_finds_pool() -> None:
    token = _token()
    analyzer = GraduationAwareRouteAnalyzer()
    bonding_at = NOW
    bonding = _observation(
        "launch:bonding",
        bonding_at,
        {
            "chain": "robinhood",
            "token_address": TOKEN,
            "event_type": "bonding_curve_progress",
            "bonding_curve_progress_bps": 4200,
        },
    )
    bonding_snapshot = analyzer.snapshot(
        token,
        (bonding,),
        now=bonding_at + timedelta(seconds=1),
        config_hash="launch-route-test-v1",
    )
    assert bonding_snapshot.lifecycle_state is LaunchLifecycleState.BONDING
    assert bonding_snapshot.route_state is RouteState.BONDING
    assert bonding_snapshot.route_available is None

    graduated_at = NOW + timedelta(minutes=1)
    graduation = _observation(
        "launch:graduation",
        graduated_at,
        {
            "chain": "robinhood",
            "token_address": TOKEN,
            "event_type": "graduation",
        },
    )
    market = _observation(
        "market:pool",
        graduated_at,
        {
            "kind": "market.snapshot",
            "provider": "dexscreener",
            "chain": "robinhood",
            "token_address": TOKEN,
            "pair_address": POOL,
            "dex_id": "robinhood-dex",
            "coverage_state": "FOUND",
        },
    )
    graduated_snapshot = analyzer.snapshot(
        token,
        (bonding, graduation, market),
        now=graduated_at + timedelta(seconds=1),
        config_hash="launch-route-test-v1",
    )
    assert graduated_snapshot.lifecycle_state is LaunchLifecycleState.GRADUATED
    assert graduated_snapshot.route_state is RouteState.FOUND
    assert graduated_snapshot.route_available is True
    assert graduated_snapshot.pool_address == POOL
    assert graduated_snapshot.provenance


def test_graduation_without_completed_discovery_remains_unknown() -> None:
    token = _token()
    at = NOW + timedelta(minutes=1)
    snapshot = GraduationAwareRouteAnalyzer().snapshot(
        token,
        (
            _observation(
                "launch:graduation",
                at,
                {
                    "chain": "robinhood",
                    "token_address": TOKEN,
                    "event_type": "graduation",
                },
            ),
        ),
        now=at + timedelta(seconds=1),
        config_hash="launch-route-test-v1",
    )
    assert snapshot.lifecycle_state is LaunchLifecycleState.GRADUATED
    assert snapshot.route_state is RouteState.UNKNOWN
    assert snapshot.route_available is None
    assert snapshot.quality_state is QualityState.FRESH

    no_route = GraduationAwareRouteAnalyzer().snapshot(
        token,
        (
            _observation(
                "route:complete",
                at,
                {
                    "kind": "market.snapshot",
                    "provider": "dexscreener",
                    "chain": "robinhood",
                    "token_address": TOKEN,
                    "route_state": "NO_ROUTE",
                    "route_discovery_complete": True,
                },
            ),
        ),
        now=at + timedelta(seconds=1),
        config_hash="launch-route-test-v1",
    )
    assert no_route.route_state is RouteState.NO_ROUTE
    assert no_route.route_available is False


def test_conflicting_latest_providers_are_conflicted_and_future_route_is_ignored() -> None:
    token = _token()
    at = NOW + timedelta(minutes=1)
    snapshot = GraduationAwareRouteAnalyzer().snapshot(
        token,
        (
            _observation(
                "provider-a:event",
                at,
                {
                    "chain": "robinhood",
                    "token_address": TOKEN,
                    "event_type": "graduation",
                    "provider": "provider-a",
                },
            ),
            _observation(
                "provider-b:event",
                at,
                {
                    "chain": "robinhood",
                    "token_address": TOKEN,
                    "event_type": "bonding_curve_progress",
                    "provider": "provider-b",
                },
            ),
            _observation(
                "future:pool",
                at + timedelta(minutes=1),
                {
                    "kind": "market.snapshot",
                    "provider": "dexscreener",
                    "chain": "robinhood",
                    "token_address": TOKEN,
                    "pair_address": POOL,
                    "coverage_state": "FOUND",
                },
            ),
        ),
        now=at + timedelta(seconds=1),
        config_hash="launch-route-test-v1",
    )
    assert snapshot.quality_state is QualityState.CONFLICTED
    assert snapshot.route_state is RouteState.UNKNOWN
    assert snapshot.pool_address is None
    assert "PROVIDER_DISAGREEMENT" in {reason.code for reason in snapshot.reason_codes}
