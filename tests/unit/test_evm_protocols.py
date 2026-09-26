"""Provider-neutral EVM deployment, lifecycle and sellability contracts."""

from datetime import UTC, datetime, timedelta

import pytest

from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_domain import Chain, QualityState
from memeradar_providers.evm_protocols import (
    DopplerV4LaunchAdapter,
    EvmProtocolDeployment,
    EvmProtocolLogReader,
    EvmProtocolVerificationStatus,
    FourMemeAdapter,
    HoodiePadLaunchAdapter,
    NoxaLaunchAdapter,
    OdysseyLaunchAdapter,
    PancakeSwapAdapter,
    UniswapAdapter,
)
from memeradar_providers.transport import ProviderSchemaError

NOW = datetime(2026, 9, 24, tzinfo=UTC)
ADDRESS = "0x" + "ab" * 20
POOL = "0x" + "cd" * 20
TOPIC = "0x" + "12" * 32


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="evm-protocol-unit",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=5),
    )


def verified(protocol: str, chain: Chain = Chain.BASE) -> EvmProtocolDeployment:
    return EvmProtocolDeployment(
        protocol=protocol,
        chain=chain,
        contract_address=ADDRESS,
        event_topics={"pool_created": TOPIC},
        runtime_code_hash="sha256:" + "1" * 64,
        sample_transaction="0x" + "34" * 32,
        verification_status=EvmProtocolVerificationStatus.VERIFIED,
        verification_source="fixture:verified-deployment",
    )


def test_unverified_four_meme_does_not_become_authoritative() -> None:
    observation = FourMemeAdapter().parse(
        {
            "address": ADDRESS,
            "topics": [TOPIC],
            "event_name": "TokenCreate",
            "token_address": ADDRESS,
            "pool_address": POOL,
            "transaction_hash": "0x" + "34" * 32,
            "block_number": 10,
        },
        context(),
    )
    assert observation.quality_state is QualityState.UNKNOWN
    assert observation.normalized_payload["verification_status"] == "TODO_VERIFY"
    assert observation.normalized_payload["authoritative"] is False


def test_verified_protocol_requires_exact_contract_and_event_identity() -> None:
    adapter = UniswapAdapter(deployments=(verified("uniswap"),))
    observation = adapter.parse(
        {
            "address": ADDRESS,
            "topics": [TOPIC],
            "event_name": "pool_created",
            "token_address": ADDRESS,
            "pool_address": POOL,
            "transaction_hash": "0x" + "34" * 32,
            "block_number": 10,
            "block_timestamp": NOW.timestamp() - 1,
        },
        context(),
    )
    assert observation.quality_state is QualityState.FRESH
    assert observation.normalized_payload["authoritative"] is False
    with pytest.raises(ProviderSchemaError, match="deployment identity"):
        adapter.parse(
            {
                "address": "0x" + "ef" * 20,
                "topics": [TOPIC],
                "event_name": "pool_created",
            },
            context(),
        )


def test_pancake_adapter_normalizes_lifecycle_names_without_implying_graduation() -> None:
    adapter = PancakeSwapAdapter(deployments=(verified("pancakeswap"),))
    observation = adapter.parse(
        {
            "address": ADDRESS,
            "topics": [TOPIC],
            "event_name": "LiquidityAdded",
            "token_address": ADDRESS,
            "pool_address": POOL,
            "transaction_hash": "0x" + "34" * 32,
            "block_number": 10,
        },
        context(),
    )
    assert observation.normalized_payload["event_type"] == "liquidity_added"
    assert observation.normalized_payload["lifecycle_state"] == "LIQUIDITY_ADDED"


def test_par_adapter_preserves_protocol_specific_multi_market_fields() -> None:
    from memeradar_providers.evm_protocols import ParLaunchAdapter

    observation = ParLaunchAdapter(deployments=(verified("par", Chain.ROBINHOOD),)).parse(
        {
            "address": ADDRESS,
            "topics": [TOPIC],
            "event_name": "PoolCreated",
            "token_address": ADDRESS,
            "pool_address": POOL,
            "pool_id": "pool-1",
            "quote_asset": "USDC",
            "multi_market_state": "PRIMARY",
            "transaction_hash": "0x" + "34" * 32,
            "block_number": 10,
        },
        context(),
    )
    assert observation.normalized_payload["pool_id"] == "pool-1"
    assert observation.normalized_payload["multi_market_state"] == "PRIMARY"


def test_robinhood_candidate_adapters_remain_read_only_and_unverified() -> None:
    base = {
        "address": ADDRESS,
        "topics": [TOPIC],
        "event_name": "Launch",
        "token_address": ADDRESS,
        "pool_address": POOL,
        "pool_key": "pool-key",
        "pool_id": "pool-id",
        "hook": "hook-address",
        "holder_count": 12,
        "top10_pct": "0.42",
        "transaction_hash": "0x" + "34" * 32,
    }
    hoodie = HoodiePadLaunchAdapter().parse(base, context())
    doppler = DopplerV4LaunchAdapter().parse(base, context())
    noxa = NoxaLaunchAdapter().parse({**base, "event_name": "Swap"}, context())
    odyssey = OdysseyLaunchAdapter().parse({**base, "event_name": "Graduation"}, context())

    for observation in (hoodie, doppler, noxa, odyssey):
        assert observation.quality_state is QualityState.UNKNOWN
        assert observation.normalized_payload["verification_status"] == "TODO_VERIFY"
        assert observation.normalized_payload["authoritative"] is False
    assert hoodie.normalized_payload["lifecycle_state"] == "DEX_ACTIVE"
    assert noxa.normalized_payload["lifecycle_state"] == "DEX_ACTIVE"
    assert odyssey.normalized_payload["lifecycle_state"] == "GRADUATED"
    assert hoodie.normalized_payload["pool_id"] == "pool-id"


def test_verified_deployment_contract_requires_all_identity_evidence() -> None:
    with pytest.raises(ValueError, match="runtime_code_hash"):
        EvmProtocolDeployment(
            protocol="uniswap",
            chain=Chain.BASE,
            contract_address=ADDRESS,
            event_topics={"pool_created": TOPIC},
            sample_transaction="0x" + "34" * 32,
            verification_status=EvmProtocolVerificationStatus.VERIFIED,
            verification_source="fixture",
        )


def test_verified_log_reader_uses_shared_rpc_logs_and_rejects_unverified_sources() -> None:
    class FakeRpc:
        chain = Chain.BASE
        provider_name = "fixture-base-rpc"

        async def fetch_logs(self, **_kwargs: object) -> tuple[dict[str, object], ...]:
            return (
                {
                    "address": ADDRESS,
                    "topics": [TOPIC],
                    "event_name": "PoolCreated",
                    "token_address": ADDRESS,
                    "pool_address": POOL,
                    "transaction_hash": "0x" + "34" * 32,
                },
            )

    async def scenario() -> None:
        reader = EvmProtocolLogReader(FakeRpc(), UniswapAdapter(deployments=(verified("uniswap"),)))
        observations = await reader.read(from_block=1, to_block=2, context=context())
        assert observations[0].quality_state is QualityState.FRESH

    import asyncio

    asyncio.run(scenario())
