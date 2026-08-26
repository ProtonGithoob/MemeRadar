"""Canonical chain identities used by the MemeRadar domain."""

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4

from .common import require_text

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_VALUES = {character: index for index, character in enumerate(_BASE58_ALPHABET)}


class Chain(str, Enum):
    """Supported blockchain identifiers."""

    SOLANA = "solana"


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


@dataclass(frozen=True, slots=True)
class TokenIdentity:
    """Stable identity for a token independent of any provider payload."""

    mint_address: str
    chain: Chain | str = Chain.SOLANA
    token_program: str = "spl-token"
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        chain = (
            self.chain.value if isinstance(self.chain, Chain) else require_text(self.chain, "chain")
        )
        try:
            normalized_chain = Chain(chain.lower())
        except ValueError as exc:
            raise ValueError(f"unsupported chain: {chain}") from exc
        object.__setattr__(self, "chain", normalized_chain)
        object.__setattr__(
            self,
            "mint_address",
            require_solana_address(self.mint_address, "mint_address"),
        )
        object.__setattr__(self, "token_program", require_text(self.token_program, "token_program"))


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
            require_solana_address(self.pool_address, "pool_address"),
        )
        object.__setattr__(
            self,
            "quote_mint",
            require_solana_address(self.quote_mint, "quote_mint"),
        )

    @property
    def token_id(self) -> UUID:
        """Return the logical token foreign-key value."""

        return self.token.id
