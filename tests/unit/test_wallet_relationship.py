"""Deterministic wallet funding/bridge relationship evidence contracts."""

import asyncio
from datetime import UTC, datetime, timedelta

from memeradar_application.creator_graph import CreatorOutcomeGraph, EdgeKind
from memeradar_application.event_time import EventTimeQuality
from memeradar_application.read_api import InMemoryReadQueryService, WalletGraphQuery
from memeradar_application.wallet_relationship import (
    WalletRelationshipAnalyzer,
    WalletRelationshipConfidence,
)
from memeradar_domain import Observation, Provenance, QualityState

NOW = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)
TOKEN = "So11111111111111111111111111111111111111112"
WALLET_A = "11111111111111111111111111111112"
WALLET_B = "11111111111111111111111111111113"
FUNDER = "11111111111111111111111111111115"
EXCHANGE = "11111111111111111111111111111116"
BRIDGE_SERVICE = "11111111111111111111111111111117"
ROUTER = "11111111111111111111111111111118"
POOL = "11111111111111111111111111111119"


def _observation(
    source_id: str,
    kind: str,
    payload: dict[str, object],
    at: datetime,
    *,
    provider: str = "fixture",
    quality_state: QualityState = QualityState.FRESH,
) -> Observation:
    return Observation(
        kind=kind,
        provenance=Provenance(
            provider=provider,
            source_id=source_id,
            observed_at=at,
            parser_version="wallet-relationship-fixture-v1",
        ),
        occurred_at=at,
        observed_at=at,
        ingested_at=at,
        quality_state=quality_state,
        normalized_payload=payload,
    )


def _funding(
    source_id: str,
    wallet: str,
    at: datetime,
    *,
    source: str = FUNDER,
    source_role: str | None = None,
) -> Observation:
    payload: dict[str, object] = {
        "from_chain": "solana",
        "from_address": source,
        "to_chain": "solana",
        "to_address": wallet,
        "amount": "1",
    }
    if source_role is not None:
        payload["source_role"] = source_role
    return _observation(
        source_id,
        "wallet.funding",
        payload,
        at,
    )


def _relationship(
    source_id: str,
    state: str,
    at: datetime,
    *,
    provider: str,
) -> Observation:
    return _observation(
        source_id,
        "wallet.relationship",
        {
            "wallet_a_chain": "solana",
            "wallet_a": WALLET_A,
            "wallet_b_chain": "solana",
            "wallet_b": WALLET_B,
            "relationship_state": state,
        },
        at,
        provider=provider,
    )


def _find_pair(values: tuple[object, ...], suffix: str = "") -> object:
    for value in values:
        if (
            getattr(value, "wallet_a", "").endswith(WALLET_A)
            and getattr(value, "wallet_b", "").endswith(WALLET_B)
            and (
                not suffix
                or suffix in {str(item) for item in getattr(value, "dimensions", ())}
            )
        ):
            return value
    raise AssertionError("expected wallet relationship pair")


def test_single_weak_funding_dimension_cannot_become_high_or_ownership() -> None:
    evidence = WalletRelationshipAnalyzer().analyze(
        (
            _funding("fund:a", WALLET_A, NOW),
            _funding("fund:b", WALLET_B, NOW + timedelta(minutes=6)),
        ),
        now=NOW + timedelta(minutes=6, seconds=1),
        config_hash="wallet-relationship-test-v1",
    )
    pair = _find_pair(evidence, "SHARED_FUNDING")
    assert pair.confidence is WalletRelationshipConfidence.WEAK
    assert pair.ownership_asserted is False
    assert "FUNDING_TIME_PROXIMITY" not in pair.dimensions

    graph = CreatorOutcomeGraph()
    graph.add_edge(pair.to_graph_edge())
    edge = next(iter(graph.edges.values()))
    assert edge.kind is EdgeKind.RELATIONSHIP_EVIDENCE
    assert edge.properties["ownership_asserted"] is False

    view = asyncio.run(
        InMemoryReadQueryService(
            creator_graph=graph,
            clock=lambda: NOW + timedelta(minutes=7),
        ).get_wallet_graph(
            WalletGraphQuery(address=WALLET_A),
        )
    )
    assert view.edges[0]["kind"] == "RELATIONSHIP_EVIDENCE"


def test_repeated_funding_plus_same_token_behavior_is_high_candidate_evidence_only() -> None:
    observations = (
        _funding("fund:a1", WALLET_A, NOW),
        _funding("fund:b1", WALLET_B, NOW + timedelta(seconds=1)),
        _funding("fund:a2", WALLET_A, NOW + timedelta(minutes=1)),
        _funding("fund:b2", WALLET_B, NOW + timedelta(minutes=1, seconds=1)),
        _observation(
            "buy:a",
            "wallet.activity",
            {
                "chain": "solana",
                "wallet_address": WALLET_A,
                "token_address": TOKEN,
                "action": "buy",
            },
            NOW + timedelta(minutes=2),
        ),
        _observation(
            "buy:b",
            "wallet.activity",
            {
                "chain": "solana",
                "wallet_address": WALLET_B,
                "token_address": TOKEN,
                "action": "buy",
            },
            NOW + timedelta(minutes=2, seconds=1),
        ),
    )
    pair = _find_pair(
        WalletRelationshipAnalyzer().analyze(
            observations,
            now=NOW + timedelta(minutes=2, seconds=2),
            config_hash="wallet-relationship-test-v1",
        ),
        "SAME_TOKEN_PARTICIPATION",
    )
    assert pair.confidence is WalletRelationshipConfidence.HIGH
    assert pair.ownership_asserted is False
    assert "REPEATED_COMMON_FUNDING" in pair.dimensions


def test_broad_market_activity_does_not_become_same_token_relationship_evidence() -> None:
    observations = (
        _funding("fund:a1", WALLET_A, NOW),
        _funding("fund:b1", WALLET_B, NOW + timedelta(seconds=1)),
        _funding("fund:a2", WALLET_A, NOW + timedelta(minutes=1)),
        _funding("fund:b2", WALLET_B, NOW + timedelta(minutes=1, seconds=1)),
        _observation(
            "market:all",
            "wallet.activity",
            {
                "chain": "solana",
                "wallet_address": WALLET_A,
                "token_address": TOKEN,
                "action": "buy",
                "canonical_event_id": "market:all",
                "market_wide": True,
            },
            NOW + timedelta(minutes=2),
        ),
        _observation(
            "market:all-copy",
            "wallet.activity",
            {
                "chain": "solana",
                "wallet_address": WALLET_B,
                "token_address": TOKEN,
                "action": "buy",
                "canonical_event_id": "market:all",
                "market_wide": True,
            },
            NOW + timedelta(minutes=2, seconds=1),
        ),
    )
    values = WalletRelationshipAnalyzer().analyze(
        observations,
        now=NOW + timedelta(minutes=2, seconds=2),
        config_hash="wallet-relationship-test-v1",
    )
    pair = _find_pair(values, "REPEATED_COMMON_FUNDING")
    assert "SAME_TOKEN_PARTICIPATION" not in pair.dimensions
    assert pair.confidence is WalletRelationshipConfidence.WEAK


def test_bridge_origin_is_evidence_but_exchange_service_does_not_link_wallets() -> None:
    bridge = _observation(
        "bridge:1",
        "wallet.bridge",
        {
            "origin_chain": "solana",
            "origin_address": WALLET_A,
            "destination_chain": "bnb",
            "destination_address": "0x" + "ab" * 20,
            "bridge_origin": "canonical-bridge-origin",
        },
        NOW,
    )
    exchange_funding = (
        _funding(
            "exchange:a",
            WALLET_A,
            NOW + timedelta(seconds=2),
            source=EXCHANGE,
            source_role="exchange",
        ),
        _funding(
            "exchange:b",
            WALLET_B,
            NOW + timedelta(seconds=3),
            source=EXCHANGE,
            source_role="exchange",
        ),
    )
    values = WalletRelationshipAnalyzer().analyze(
        (bridge, *exchange_funding),
        now=NOW + timedelta(seconds=4),
        config_hash="wallet-relationship-test-v1",
    )
    assert any("BRIDGE_ORIGIN" in value.dimensions for value in values)
    assert not any(
        WALLET_A in value.wallet_a and WALLET_B in value.wallet_b for value in values
    )

    target_values = WalletRelationshipAnalyzer(
        service_addresses=(("solana", EXCHANGE),),
    ).analyze(
        (
            _funding("exchange:target", EXCHANGE, NOW, source=FUNDER),
            _funding("wallet:target", WALLET_A, NOW + timedelta(seconds=1)),
        ),
        now=NOW + timedelta(seconds=2),
        config_hash="wallet-relationship-test-v1",
    )
    assert target_values == ()


def test_contradictory_link_evidence_is_conflicted_and_future_evidence_is_ignored() -> None:
    values = WalletRelationshipAnalyzer().analyze(
        (
            _relationship("link:yes", "LINKED", NOW, provider="provider-a"),
            _relationship("link:no", "REJECTED", NOW, provider="provider-b"),
            _funding("future:a", WALLET_A, NOW + timedelta(minutes=1)),
            _funding("future:b", WALLET_B, NOW + timedelta(minutes=1)),
        ),
        now=NOW + timedelta(seconds=1),
        config_hash="wallet-relationship-test-v1",
    )
    pair = _find_pair(values)
    assert pair.quality_state is QualityState.CONFLICTED
    assert pair.confidence is WalletRelationshipConfidence.UNKNOWN
    assert "PROVIDER_DISAGREEMENT" in {reason.code for reason in pair.reason_codes}


def test_duplicate_funding_does_not_count_as_repeated_and_unknown_time_is_not_strong() -> None:
    duplicate_a = _funding("same:event", WALLET_A, NOW)
    duplicate_b = _funding("same:event", WALLET_A, NOW)
    values = WalletRelationshipAnalyzer().analyze(
        (
            duplicate_a,
            duplicate_b,
            _funding("other:event", WALLET_B, NOW),
        ),
        now=NOW + timedelta(seconds=1),
        config_hash="wallet-relationship-test-v1",
    )
    pair = _find_pair(values, "SHARED_FUNDING")
    assert pair.event_count == 2
    assert "REPEATED_COMMON_FUNDING" not in pair.dimensions

    missing_a = _funding("missing:a", WALLET_A, NOW)
    missing_b = _funding("missing:b", WALLET_B, NOW)
    missing_a = Observation(
        kind=missing_a.kind,
        provenance=missing_a.provenance,
        occurred_at=None,
        observed_at=missing_a.observed_at,
        ingested_at=missing_a.ingested_at,
        quality_state=missing_a.quality_state,
        normalized_payload=missing_a.normalized_payload,
    )
    missing = _find_pair(
        WalletRelationshipAnalyzer().analyze(
            (missing_a, missing_b),
            now=NOW + timedelta(seconds=1),
            config_hash="wallet-relationship-test-v1",
        ),
        "SHARED_FUNDING",
    )
    assert missing.time_quality is EventTimeQuality.UNKNOWN
    assert missing.confidence is WalletRelationshipConfidence.UNKNOWN
    assert missing.to_graph_edge().occurred_at is None


def test_all_service_relationship_paths_are_excluded() -> None:
    service_payloads = (
        ("wallet.transfer", {"from_address": EXCHANGE, "to_address": WALLET_A}),
        ("onchain.transfer", {"from_address": ROUTER, "to_address": WALLET_A}),
        ("wallet.bridge", {"origin_address": BRIDGE_SERVICE, "destination_address": WALLET_A}),
        ("wallet.activity", {"wallet_address": POOL, "token_address": TOKEN}),
        (
            "wallet.relationship",
            {"wallet_a": EXCHANGE, "wallet_b": WALLET_A, "relationship_state": "LINKED"},
        ),
        ("wallet.link", {"wallet_a": ROUTER, "wallet_b": WALLET_A, "link_state": "LINKED"}),
    )
    observations = tuple(
        _observation(
            f"service:{index}",
            kind,
            {
                **payload,
                "from_chain": "solana",
                "to_chain": "solana",
                "origin_chain": "solana",
                "destination_chain": "solana",
                "wallet_a_chain": "solana",
                "wallet_b_chain": "solana",
                "chain": "solana",
                "source_role": "exchange" if index == 0 else None,
            },
            NOW + timedelta(seconds=index),
        )
        for index, (kind, payload) in enumerate(service_payloads)
    )
    assert WalletRelationshipAnalyzer(
        service_addresses=(
            ("solana", EXCHANGE),
            ("solana", BRIDGE_SERVICE),
            ("solana", ROUTER),
            ("solana", POOL),
        )
    ).analyze(
        observations,
        now=NOW + timedelta(minutes=1),
        config_hash="wallet-relationship-test-v1",
    ) == ()


def test_classified_service_is_excluded_from_unclassified_sibling_observations() -> None:
    classified = _observation(
        "service:classified",
        "wallet.activity",
        {
            "chain": "solana",
            "wallet_address": EXCHANGE,
            "token_address": TOKEN,
            "classification": "centralized_exchange",
        },
        NOW,
    )
    values = WalletRelationshipAnalyzer().analyze(
        (
            classified,
            _funding("unclassified:a", WALLET_A, NOW + timedelta(seconds=1), source=EXCHANGE),
            _funding("unclassified:b", WALLET_B, NOW + timedelta(seconds=2), source=EXCHANGE),
        ),
        now=NOW + timedelta(seconds=3),
        config_hash="wallet-relationship-test-v1",
    )
    assert not any(
        WALLET_A in value.wallet_a and WALLET_B in value.wallet_b for value in values
    )


def test_changed_duplicate_source_is_provider_conflict_not_overwrite() -> None:
    first = _relationship("provider:source", "LINKED", NOW, provider="provider-a")
    changed = _observation(
        "provider:source",
        "wallet.relationship",
        {
            "wallet_a_chain": "solana",
            "wallet_a": WALLET_A,
            "wallet_b_chain": "solana",
            "wallet_b": WALLET_B,
            "relationship_state": "REJECTED",
        },
        NOW,
        provider="provider-a",
    )
    pair = _find_pair(
        WalletRelationshipAnalyzer().analyze(
            (first, changed),
            now=NOW + timedelta(seconds=1),
            config_hash="wallet-relationship-test-v1",
        )
    )
    assert pair.quality_state is QualityState.CONFLICTED
    assert pair.confidence is WalletRelationshipConfidence.UNKNOWN
