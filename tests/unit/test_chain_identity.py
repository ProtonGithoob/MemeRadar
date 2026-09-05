"""Canonical multi-chain identity contracts."""

import pytest

from memeradar_domain import (
    Chain,
    ChainId,
    PoolIdentity,
    TokenIdentity,
    WalletIdentity,
    require_chain_address,
    require_evm_address,
)

EVM_ADDRESS = "0x" + "AB" * 20
EVM_ADDRESS_NORMALIZED = EVM_ADDRESS.lower()


def test_robinhood_identity_is_chain_qualified_and_distinct_from_bnb() -> None:
    robinhood_token = TokenIdentity(
        mint_address=EVM_ADDRESS,
        chain=Chain.ROBINHOOD,
        token_program="erc20",
    )
    bnb_token = TokenIdentity(
        mint_address=EVM_ADDRESS,
        chain=Chain.BNB,
        token_program="bep20",
    )
    robinhood_wallet = WalletIdentity(address=EVM_ADDRESS, chain=Chain.ROBINHOOD)

    assert ChainId.ROBINHOOD is Chain.ROBINHOOD
    assert robinhood_token.address == EVM_ADDRESS_NORMALIZED
    assert robinhood_token.canonical_id == f"robinhood:{EVM_ADDRESS_NORMALIZED}"
    assert robinhood_wallet.canonical_id == f"robinhood:{EVM_ADDRESS_NORMALIZED}"
    assert robinhood_token.canonical_id != bnb_token.canonical_id


def test_generic_evm_address_validation_is_shared_by_bnb_and_robinhood() -> None:
    assert require_evm_address(EVM_ADDRESS) == EVM_ADDRESS_NORMALIZED
    assert require_chain_address(EVM_ADDRESS, Chain.BNB) == EVM_ADDRESS_NORMALIZED
    assert require_chain_address(EVM_ADDRESS, Chain.ROBINHOOD) == EVM_ADDRESS_NORMALIZED

    for value in ("0x1234", "0x" + "g0" * 20, "1" * 40):
        with pytest.raises(ValueError, match="EVM"):
            require_evm_address(value)


def test_evm_pool_identity_reuses_the_same_chain_address_validator() -> None:
    token = TokenIdentity(mint_address=EVM_ADDRESS, chain=Chain.ROBINHOOD)
    pool = PoolIdentity(
        token=token,
        venue="uniswap",
        pool_address="0x" + "CD" * 20,
        quote_mint="0x" + "EF" * 20,
    )

    assert pool.pool_address == ("0x" + "cd" * 20)
    assert pool.quote_mint == ("0x" + "ef" * 20)
    assert pool.canonical_id == f"robinhood:{pool.pool_address}"


def test_solana_identity_still_rejects_evm_addresses() -> None:
    with pytest.raises(ValueError, match="base58"):
        TokenIdentity(mint_address=EVM_ADDRESS, chain=Chain.SOLANA)
