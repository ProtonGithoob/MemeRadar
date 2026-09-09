"""Backend-owned universal search resolution contracts."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from memeradar_api.main import create_app
from memeradar_application.config import Settings
from memeradar_application.read_api import InMemoryReadQueryService, TokenView, WalletView

TOKEN_ID = uuid4()
MINT = "So11111111111111111111111111111111111111112"
WALLET = "Vote111111111111111111111111111111111111111"
EVM_WALLET = "0x1111111111111111111111111111111111111111"
NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)


def test_search_resolver_returns_typed_token_wallet_and_not_found_targets() -> None:
    service = InMemoryReadQueryService(
        tokens=(
            TokenView(
                id=TOKEN_ID,
                chain="solana",
                mint_address=MINT,
                token_program="spl-token",
                first_seen_at=NOW,
            ),
        ),
        wallets=(
            WalletView(
                address=WALLET,
                label="fixture wallet",
                registry_tier="TIER_A",
                recommended_tier="TIER_A",
                as_of=NOW,
                expires_at=NOW + timedelta(minutes=5),
            ),
            WalletView(
                address=EVM_WALLET,
                chain="bnb",
                label="evm fixture wallet",
                registry_tier="TIER_A",
                recommended_tier="TIER_A",
                as_of=NOW,
                expires_at=NOW + timedelta(minutes=5),
            ),
        ),
    )
    client = TestClient(
        create_app(
            Settings.from_env({"VIEWER_API_TOKEN": "viewer-search-secret"}),
            read_service=service,
        )
    )
    headers = {"Authorization": "Bearer viewer-search-secret"}

    token = client.get("/v1/search/resolve", params={"q": str(TOKEN_ID)}, headers=headers)
    wallet = client.get("/v1/search/resolve", params={"q": WALLET}, headers=headers)
    evm_wallet = client.get(
        "/v1/search/resolve", params={"q": f"bnb:{EVM_WALLET}"}, headers=headers
    )
    missing = client.get(
        "/v1/search/resolve",
        params={"q": "0x0000000000000000000000000000000000000000"},
        headers=headers,
    )

    assert token.status_code == 200
    assert token.json()["kind"] == "TOKEN"
    assert token.json()["route"] == f"/tokens/{TOKEN_ID}"
    assert wallet.status_code == 200
    assert wallet.json()["kind"] == "WALLET"
    assert wallet.json()["route"] == f"/wallets/{WALLET}"
    assert evm_wallet.status_code == 200
    assert evm_wallet.json()["kind"] == "WALLET"
    assert evm_wallet.json()["route"] == f"/wallets/bnb:{EVM_WALLET}"
    assert missing.status_code == 200
    assert missing.json()["kind"] == "NOT_FOUND"
