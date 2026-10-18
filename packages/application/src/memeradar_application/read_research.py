"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from memeradar_domain import Chain, QualityState, normalize_chain
from memeradar_domain.common import ensure_utc

from .read_common import DEFAULT_PAGE_LIMIT, _bounded_limit, _optional_cursor, _optional_quality


@dataclass(frozen=True, slots=True)
class ChainOpportunityQuery:
    """Bounded filters for raw chain-opportunity evidence."""

    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    chain: Chain | str | None = None
    quality_state: QualityState | str | None = None
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        object.__setattr__(
            self,
            "chain",
            None if self.chain is None else normalize_chain(self.chain),
        )
        object.__setattr__(self, "quality_state", _optional_quality(self.quality_state))
        if self.as_of is not None:
            object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
