"""Contract checks for the small provider-neutral composition root."""

from __future__ import annotations

import asyncio
from pathlib import Path

from memeradar_application.config import Settings
from memeradar_providers.composition import (
    FreeFirstProviderBundle,
    build_free_first_provider_bundle,
)

ROOT = Path(__file__).resolve().parents[2]


def test_keyless_bundle_uses_free_defaults_and_keeps_optional_adapters_absent() -> None:
    bundle = build_free_first_provider_bundle(Settings.from_env({}))
    try:
        assert isinstance(bundle, FreeFirstProviderBundle)
        assert bundle.chain.provider_name == "solana-public-rpc"
        assert bundle.market.provider_name == "dexscreener"
        assert bundle.quote.provider_name == "dexscreener"
        assert bundle.social_metadata is not None
        assert bundle.social_metadata.provider_name == "dexscreener"
        assert bundle.optional["helius"] == "UNCONFIGURED_OPTIONAL"
        assert bundle.optional["birdeye"] == "UNCONFIGURED_OPTIONAL"
        assert bundle.optional["external_wallet"] == "UNCONFIGURED_OPTIONAL"
    finally:
        asyncio.run(bundle.aclose())


def test_application_routing_stays_provider_import_free() -> None:
    routing_source = (
        ROOT
        / "packages"
        / "application"
        / "src"
        / "memeradar_application"
        / "provider_routing.py"
    ).read_text(encoding="utf-8")

    assert "memeradar_providers" not in routing_source
    assert "sign_transaction" not in routing_source
    assert "submit_transaction" not in routing_source
