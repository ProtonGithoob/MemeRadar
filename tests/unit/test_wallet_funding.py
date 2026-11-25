"""Funding lookup parsing and shared-funder clustering (no ownership claims)."""

from __future__ import annotations

from memeradar_providers.wallet_funding import (
    SYSTEM_PROGRAM,
    inbound_sol_transfers,
    shared_funder_clusters,
)

WALLET = "Vote111111111111111111111111111111111111111"
FUNDER = "So11111111111111111111111111111111111111112"


def _tx(source: str, destination: str, *, err: object = None, inner: bool = False) -> dict:
    transfer = {
        "programId": SYSTEM_PROGRAM,
        "parsed": {"type": "transfer",
                   "info": {"source": source, "destination": destination, "lamports": 5}},
    }
    meta = {"err": err, "innerInstructions": [{"instructions": [transfer]}] if inner else []}
    return {"meta": meta, "transaction": {"message": {"instructions": [] if inner else [transfer]}}}


def test_only_successful_inbound_system_transfers_count_as_funding() -> None:
    assert inbound_sol_transfers(_tx(FUNDER, WALLET), WALLET) == [
        {"source": FUNDER, "lamports": 5}
    ]
    assert inbound_sol_transfers(_tx(FUNDER, WALLET, inner=True), WALLET)  # CPI transfer
    assert inbound_sol_transfers(_tx(WALLET, FUNDER), WALLET) == []  # outbound
    assert inbound_sol_transfers(_tx(FUNDER, WALLET, err={"x": 1}), WALLET) == []


def test_shared_funder_clusters_need_three_wallets_and_skip_hubs() -> None:
    small = [{"from_address": "F1", "to_address": f"W{i}"} for i in range(3)]
    pair = [{"from_address": "F2", "to_address": f"P{i}"} for i in range(2)]
    hub = [{"from_address": "CEX", "to_address": f"H{i}"} for i in range(60)]
    clusters = shared_funder_clusters([*small, *pair, *hub])
    assert set(clusters) == {"W0", "W1", "W2"}
    assert all(value.startswith("funder:F1") for value in clusters.values())


def test_shared_funder_needs_a_common_early_buy_when_mints_are_known() -> None:
    funded = [{"from_address": "CEXHOT", "to_address": f"W{i}"} for i in range(4)]
    unrelated = {"W0": {"A"}, "W1": {"B"}, "W2": {"C"}, "W3": {"D"}}
    assert shared_funder_clusters(funded, wallet_mints=unrelated) == {}
    together = {"W0": {"A"}, "W1": {"A"}, "W2": {"A", "C"}, "W3": {"D"}}
    assert set(shared_funder_clusters(funded, wallet_mints=together)) == {"W0", "W1", "W2"}
