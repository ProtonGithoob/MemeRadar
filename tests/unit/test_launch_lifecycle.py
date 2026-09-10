"""Deterministic launch lifecycle and route-state contracts."""

from datetime import UTC, datetime, timedelta

from memeradar_application.event_time import EventTimeQuality
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
    assert bonding_snapshot.route_state is RouteState.BONDING_ROUTE
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
            "kind": "market.market_snapshot",
            "provider": "dexscreener",
            "chain": "robinhood",
            "token_address": TOKEN,
            "pair_address": POOL,
            "dex_id": "robinhood-dex",
            "coverage_state": "FOUND",
            "route_verified": True,
        },
    )
    graduated_snapshot = analyzer.snapshot(
        token,
        (bonding, graduation, market),
        now=graduated_at + timedelta(seconds=1),
        config_hash="launch-route-test-v1",
    )
    assert graduated_snapshot.lifecycle_state is LaunchLifecycleState.DEX_LIVE
    assert graduated_snapshot.route_state is RouteState.DEX_ROUTE
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
    assert snapshot.lifecycle_state is LaunchLifecycleState.GRADUATING
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
                    "route_verified": True,
                },
            ),
        ),
        now=at + timedelta(seconds=1),
        config_hash="launch-route-test-v1",
    )
    assert no_route.route_state is RouteState.NO_ROUTE
    assert no_route.route_available is False


def test_expired_lifecycle_evidence_is_stale_without_becoming_a_route() -> None:
    token = _token()
    snapshot = GraduationAwareRouteAnalyzer().snapshot(
        token,
        (
            _observation(
                "launch:stale-bonding",
                NOW,
                {
                    "chain": "robinhood",
                    "token_address": TOKEN,
                    "event_type": "bonding_curve_progress",
                    "bonding_curve_progress_bps": 4200,
                },
            ),
        ),
        now=NOW + timedelta(minutes=5, seconds=1),
        config_hash="launch-route-test-v1",
    )

    assert snapshot.lifecycle_state is LaunchLifecycleState.BONDING
    assert snapshot.route_state is RouteState.BONDING_ROUTE
    assert snapshot.quality_state is QualityState.STALE
    assert snapshot.confidence == 0


def test_required_lifecycle_states_and_verified_market_fields_are_replayable() -> None:
    token = _token()
    analyzer = GraduationAwareRouteAnalyzer()
    creator = "0x" + "ef" * 20
    created = _observation(
        "launch:created",
        NOW,
        {"chain": "robinhood", "token_address": TOKEN, "event_type": "created"},
    )
    assert analyzer.snapshot(
        token,
        (created,),
        now=NOW + timedelta(seconds=1),
        config_hash="launch-route-test-v1",
    ).lifecycle_state is LaunchLifecycleState.CREATED

    graduating_at = NOW + timedelta(minutes=2)
    graduating = _observation(
        "launch:graduating",
        graduating_at,
        {
            "chain": "robinhood",
            "token_address": TOKEN,
            "event_type": "graduating",
            "launchpad": "verified-launchpad",
            "creator_address": creator,
            "quote_asset": "USDC",
            "graduation_threshold_bps": 10000,
            "canonical_event_id": "graduation:1",
        },
    )
    pending = analyzer.snapshot(
        token,
        (created, graduating),
        now=graduating_at + timedelta(seconds=1),
        config_hash="launch-route-test-v1",
    )
    assert pending.lifecycle_state is LaunchLifecycleState.GRADUATING
    assert pending.route_state is RouteState.UNKNOWN
    assert pending.launchpad == "verified-launchpad"
    assert pending.creator_address == creator
    assert pending.graduation_threshold_bps == 10000

    live_at = graduating_at + timedelta(minutes=1)
    live = _observation(
        "market:verified",
        live_at,
        {
            "kind": "market.snapshot",
            "provider": "dexscreener",
            "chain": "robinhood",
            "token_address": TOKEN,
            "event_type": "first_liquidity",
            "pair_address": POOL,
            "dex_id": "robinhood-dex-v2",
            "route_verified": True,
            "quote_asset": "USDC",
            "liquidity_lock_state": "UNKNOWN",
        },
    )
    first_swap = _observation(
        "market:swap",
        live_at + timedelta(seconds=1),
        {
            "kind": "market.snapshot",
            "provider": "canonical-rpc",
            "chain": "robinhood",
            "token_address": TOKEN,
            "event_type": "first_verified_swap",
            "pair_address": POOL,
            "route_verified": True,
            "canonical_event_id": "swap:1",
        },
    )
    live_snapshot = analyzer.snapshot(
        token,
        (created, graduating, live, first_swap),
        now=live_at + timedelta(seconds=2),
        config_hash="launch-route-test-v1",
    )
    assert live_snapshot.lifecycle_state is LaunchLifecycleState.DEX_LIVE
    assert live_snapshot.route_state is RouteState.DEX_ROUTE
    assert live_snapshot.pool_address == POOL
    assert live_snapshot.venue == "robinhood-dex-v2"
    assert live_snapshot.graduated_at == graduating_at
    assert live_snapshot.first_verified_dex_liquidity_at == live_at
    assert live_snapshot.first_verified_swap_at == live_at + timedelta(seconds=1)


def test_feed_and_rpc_duplicates_with_one_canonical_event_are_deduplicated() -> None:
    token = _token()
    at = NOW + timedelta(minutes=1)
    common = {
        "chain": "robinhood",
        "token_address": TOKEN,
        "event_type": "graduating",
        "canonical_event_id": "tx:graduation-1",
    }
    feed = _observation("feed:graduation-1", at, {**common, "provider": "robinhood-sequencer"})
    rpc = _observation(
        "rpc:graduation-1",
        at,
        {**common, "provider": "canonical-rpc", "rpc_reconciled": True},
    )
    snapshot = GraduationAwareRouteAnalyzer().snapshot(
        token,
        (feed, rpc),
        now=at + timedelta(seconds=1),
        config_hash="launch-route-test-v1",
    )
    assert snapshot.lifecycle_state is LaunchLifecycleState.GRADUATING
    assert snapshot.quality_state is QualityState.FRESH
    assert "DUPLICATE_CANONICAL_EVENT_DEDUPED" in {
        reason.code for reason in snapshot.reason_codes
    }
    assert len(snapshot.evidence_refs) == 1


def test_same_source_payload_mutation_is_conflicted_not_overwritten() -> None:
    token = _token()
    first = _observation(
        "launch:mutable",
        NOW,
        {
            "chain": "robinhood",
            "token_address": TOKEN,
            "event_type": "graduation",
            "creator_address": "0x" + "ef" * 20,
        },
    )
    second = _observation(
        "launch:mutable",
        NOW,
        {
            "chain": "robinhood",
            "token_address": TOKEN,
            "event_type": "graduation",
            "creator_address": "0x" + "12" * 20,
        },
    )

    snapshot = GraduationAwareRouteAnalyzer().snapshot(
        token,
        (first, second),
        now=NOW + timedelta(seconds=1),
        config_hash="launch-route-test-v1",
    )

    assert snapshot.quality_state is QualityState.CONFLICTED
    assert snapshot.lifecycle_state is LaunchLifecycleState.UNKNOWN
    assert snapshot.route_state is RouteState.UNKNOWN


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


def test_missing_event_time_is_unknown_and_delayed_observation_cannot_look_back() -> None:
    token = _token()
    delayed = Observation(
        kind="protocol.lifecycle",
        provenance=Provenance(
            provider="fixture",
            source_id="delayed:event",
            observed_at=NOW + timedelta(minutes=2),
            parser_version="fixture-v1",
        ),
        occurred_at=NOW,
        observed_at=NOW + timedelta(minutes=2),
        ingested_at=NOW + timedelta(minutes=2),
        quality_state=QualityState.FRESH,
        normalized_payload={
            "chain": "robinhood",
            "token_address": TOKEN,
            "event_type": "graduation",
        },
    )
    missing_time = Observation(
        kind="protocol.lifecycle",
        provenance=Provenance(
            provider="fixture",
            source_id="missing:event",
            observed_at=NOW,
            parser_version="fixture-v1",
        ),
        occurred_at=None,
        observed_at=NOW,
        ingested_at=NOW,
        quality_state=QualityState.FRESH,
        normalized_payload={
            "chain": "robinhood",
            "token_address": TOKEN,
            "event_type": "graduation",
        },
    )

    delayed_snapshot = GraduationAwareRouteAnalyzer().snapshot(
        token,
        (delayed,),
        now=NOW + timedelta(minutes=1),
        config_hash="launch-route-test-v1",
    )
    missing_snapshot = GraduationAwareRouteAnalyzer().snapshot(
        token,
        (missing_time,),
        now=NOW + timedelta(seconds=1),
        config_hash="launch-route-test-v1",
    )

    assert delayed_snapshot.lifecycle_state is LaunchLifecycleState.UNKNOWN
    assert missing_snapshot.lifecycle_state is LaunchLifecycleState.GRADUATING
    assert missing_snapshot.graduated_at is None
    assert missing_snapshot.time_quality is EventTimeQuality.UNKNOWN
    assert missing_snapshot.quality_state is QualityState.UNKNOWN


def test_same_transaction_different_logs_remain_distinct_lifecycle_events() -> None:
    token = _token()
    at = NOW + timedelta(minutes=1)
    observations = tuple(
        _observation(
            f"rpc:log:{index}",
            at,
            {
                "chain": "robinhood",
                "token_address": TOKEN,
                "event_type": "graduation",
                "tx_hash": "0x" + "12" * 32,
                "log_index": index,
                "topic0": "0x" + ("aa" if index == 0 else "bb") * 32,
            },
        )
        for index in (0, 1)
    )
    snapshot = GraduationAwareRouteAnalyzer().snapshot(
        token,
        observations,
        now=at + timedelta(seconds=1),
        config_hash="launch-route-test-v1",
    )

    assert len(snapshot.evidence_refs) == 2
    assert "DUPLICATE_CANONICAL_EVENT_DEDUPED" not in {
        reason.code for reason in snapshot.reason_codes
    }
