"""Canonical chain and address identities used by the MemeRadar domain."""

import re
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4

from .common import require_text

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_VALUES = {character: index for index, character in enumerate(_BASE58_ALPHABET)}


class Chain(str, Enum):
    """Supported blockchain identifiers."""

    SOLANA = "solana"
    BNB = "bnb"
    ROBINHOOD = "robinhood"

    @property
    def is_evm(self) -> bool:
        """Return whether this chain uses the shared EVM address format."""

        return self in {Chain.BNB, Chain.ROBINHOOD}


# The implementation uses one enum for compatibility with the existing public
# ``Chain`` name; ``ChainId`` is the canonical-network spelling used by the
# multichain extension.
ChainId = Chain


def _is_canonical_solana_address(value: str) -> bool:
    """Validate base58 decoding to exactly one Solana public-key width."""

    if not value or any(character not in _BASE58_VALUES for character in value):
        return False
    number = 0
    for character in value:
        number = number * 58 + _BASE58_VALUES[character]
    significant_length = (number.bit_length() + 7) // 8
    leading_zero_bytes = len(value) - len(value.lstrip("1"))
    return leading_zero_bytes + significant_length == 32


def require_solana_address(value: str, field: str = "address") -> str:
    """Require a canonical base58-encoded 32-byte Solana public key."""

    normalized = require_text(value, field, max_length=64)
    if not _is_canonical_solana_address(normalized):
        raise ValueError(f"{field} must be a canonical Solana base58 address")
    return normalized


_EVM_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")


def require_evm_address(value: str, field: str = "address") -> str:
    """Require and normalize a 20-byte hexadecimal EVM address."""

    normalized = require_text(value, field, max_length=42)
    if not _EVM_ADDRESS.fullmatch(normalized):
        raise ValueError(f"{field} must be a canonical EVM address")
    return normalized.lower()


def normalize_chain(value: Chain | str, field: str = "chain") -> Chain:
    """Normalize a supported chain value without importing provider code."""

    raw = value.value if isinstance(value, Chain) else require_text(value, field)
    try:
        return Chain(raw.lower())
    except ValueError as exc:
        raise ValueError(f"unsupported chain: {raw}") from exc


def require_chain_address(
    value: str,
    chain: Chain | str,
    field: str = "address",
) -> str:
    """Validate an address using the canonical validator for its chain."""

    normalized_chain = normalize_chain(chain)
    if normalized_chain is Chain.SOLANA:
        return require_solana_address(value, field)
    return require_evm_address(value, field)


@dataclass(frozen=True, slots=True)
class TokenIdentity:
    """Stable identity for a token independent of any provider payload."""

    mint_address: str
    chain: Chain | str = Chain.SOLANA
    token_program: str = "spl-token"
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        normalized_chain = normalize_chain(self.chain)
        object.__setattr__(self, "chain", normalized_chain)
        object.__setattr__(
            self,
            "mint_address",
            require_chain_address(self.mint_address, normalized_chain, "mint_address"),
        )
        object.__setattr__(self, "token_program", require_text(self.token_program, "token_program"))

    @property
    def address(self) -> str:
        """Return the generic token address; ``mint_address`` remains compatible."""

        return self.mint_address

    @property
    def token_standard(self) -> str:
        """Return the generic spelling for the existing token-program field."""

        return self.token_program

    @property
    def canonical_id(self) -> str:
        """Return a chain-qualified token identity suitable for joins/deduping."""

        return f"{normalize_chain(self.chain).value}:{self.address}"


@dataclass(frozen=True, slots=True)
class WalletIdentity:
    """Stable chain-qualified wallet identity used by wallet evidence."""

    address: str
    chain: Chain | str = Chain.SOLANA
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        normalized_chain = normalize_chain(self.chain)
        object.__setattr__(self, "chain", normalized_chain)
        object.__setattr__(
            self,
            "address",
            require_chain_address(self.address, normalized_chain, "address"),
        )

    @property
    def canonical_id(self) -> str:
        """Return a chain-qualified wallet identity suitable for joins/deduping."""

        return f"{normalize_chain(self.chain).value}:{self.address}"


@dataclass(frozen=True, slots=True)
class PoolIdentity:
    """Stable identity for a token liquidity pool."""

    token: TokenIdentity
    venue: str
    pool_address: str
    quote_mint: str
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        object.__setattr__(self, "venue", require_text(self.venue, "venue").lower())
        object.__setattr__(
            self,
            "pool_address",
            require_chain_address(self.pool_address, self.token.chain, "pool_address"),
        )
        object.__setattr__(
            self,
            "quote_mint",
            require_chain_address(self.quote_mint, self.token.chain, "quote_mint"),
        )

    @property
    def token_id(self) -> UUID:
        """Return the logical token foreign-key value."""

        return self.token.id

    @property
    def address(self) -> str:
        """Return the generic pool address spelling."""

        return self.pool_address

    @property
    def canonical_id(self) -> str:
        """Return a chain-qualified pool identity suitable for joins/deduping."""

        return f"{normalize_chain(self.token.chain).value}:{self.address}"
