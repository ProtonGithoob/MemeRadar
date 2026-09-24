"""Provider-neutral eth_call sellability evidence."""

import asyncio
from datetime import UTC, datetime, timedelta

from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_domain import Chain, QualityState
from memeradar_providers.evm_sellability import EvmSellabilityAdapter, EvmSellSimulationRequest
from memeradar_providers.transport import ProviderTimeoutError

NOW = datetime(2026, 9, 24, tzinfo=UTC)
ADDRESS = "0x" + "ab" * 20


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="sellability-unit",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=5),
    )


class FakeRpc:
    chain = Chain.BASE
    provider_name = "fixture-base-rpc"

    def __init__(self, result: object) -> None:
        self.result = result

    async def call_contract(
        self,
        address: str,
        data: str,
        *,
        context: ProviderRequestContext,
    ) -> object:
        assert address == ADDRESS
        assert data == "0x1234"
        assert context.correlation_id == "sellability-unit"
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def request() -> EvmSellSimulationRequest:
    return EvmSellSimulationRequest(
        chain=Chain.BASE,
        token_address=ADDRESS,
        target_address=ADDRESS,
        sell_call_data="0x1234",
        context=context(),
    )


def test_eth_call_success_is_sellable_but_has_no_unearned_tax_claim() -> None:
    async def scenario() -> None:
        result = await EvmSellabilityAdapter(FakeRpc("0x01")).simulate(request())
        assert result.quality_state is QualityState.FRESH
        assert result.sellable is True
        assert result.route_available is True
        assert result.sell_tax_bps is None
        assert result.reason_codes == ("ETH_CALL_SUCCEEDED",)

    asyncio.run(scenario())


def test_rpc_timeout_remains_unknown_and_fail_closed() -> None:
    async def scenario() -> None:
        result = await EvmSellabilityAdapter(
            FakeRpc(ProviderTimeoutError("timeout"))
        ).simulate(request())
        assert result.quality_state is QualityState.UNKNOWN
        assert result.sellable is None
        assert result.route_available is None
        assert result.reason_codes == ("SELL_SIMULATION_UNAVAILABLE",)

    asyncio.run(scenario())
