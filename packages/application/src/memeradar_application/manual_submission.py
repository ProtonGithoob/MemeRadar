"""Provider-independent, analysis-only manual mint submission service."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from memeradar_domain import Provenance, TokenIdentity
from memeradar_domain.common import require_text
from memeradar_domain.identities import require_solana_address

from .provider_contracts import DiscoveryCandidate, ProviderRequestContext

MANUAL_PARSER_VERSION = "manual-submission-v1"


@dataclass(frozen=True, slots=True)
class ManualMintRequest:
    """Validated request to observe a mint without invoking any provider or execution path."""

    context: ProviderRequestContext
    mint_address: str
    token_program: str = "spl-token"

    def __post_init__(self) -> None:
        if not isinstance(self.context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        object.__setattr__(
            self,
            "mint_address",
            require_solana_address(self.mint_address, "mint_address"),
        )
        object.__setattr__(
            self,
            "token_program",
            require_text(self.token_program, "token_program", max_length=128),
        )


@dataclass(frozen=True, slots=True)
class ManualMintResult:
    """Manual candidate plus duplicate status for the current service lifetime."""

    candidate: DiscoveryCandidate
    duplicate: bool

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, DiscoveryCandidate):
            raise TypeError("candidate must be a DiscoveryCandidate")
        if not isinstance(self.duplicate, bool):
            raise TypeError("duplicate must be a boolean")


class ManualMintSubmissionService:
    """Create deterministic manual candidates and retain duplicate evidence in memory."""

    def __init__(self) -> None:
        self._submitted_mints: set[str] = set()

    @staticmethod
    def _token(request: ManualMintRequest) -> TokenIdentity:
        return TokenIdentity(
            mint_address=request.mint_address,
            token_program=request.token_program,
            id=uuid5(NAMESPACE_URL, f"memeradar:manual:token:{request.mint_address}"),
        )

    def submit(self, request: ManualMintRequest) -> ManualMintResult:
        if not isinstance(request, ManualMintRequest):
            raise TypeError("request must be a ManualMintRequest")
        token = self._token(request)
        source_id = f"manual:{request.mint_address}"
        duplicate = request.mint_address in self._submitted_mints
        self._submitted_mints.add(request.mint_address)
        candidate = DiscoveryCandidate(
            token=token,
            source_id=source_id,
            occurred_at=request.context.requested_at,
            observed_at=request.context.requested_at,
            ingested_at=request.context.requested_at,
            provenance=Provenance(
                provider="manual",
                source_id=source_id,
                observed_at=request.context.requested_at,
                parser_version=MANUAL_PARSER_VERSION,
            ),
        )
        return ManualMintResult(candidate=candidate, duplicate=duplicate)


__all__ = [
    "MANUAL_PARSER_VERSION",
    "ManualMintRequest",
    "ManualMintResult",
    "ManualMintSubmissionService",
]
