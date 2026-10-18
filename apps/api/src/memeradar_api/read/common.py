"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from decimal import Decimal
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

from memeradar_application.read_api import Page, ProvenanceView

_RISK_DISPOSITIONS = Literal["PASS", "WARN", "BLOCK", "UNKNOWN"]

ResponseT = TypeVar("ResponseT")

SourceT = TypeVar("SourceT")

BuildT = TypeVar("BuildT")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PageResponse(_StrictModel, Generic[ResponseT]):
    """Stable page envelope shared by every collection endpoint."""

    items: list[ResponseT]
    limit: int
    has_more: bool
    next_cursor: str | None = None


class ProvenanceResponse(_StrictModel):
    provider: str
    source_id: str
    observed_at: datetime
    parser_version: str
    raw_payload_hash: str | None = None


def _materialize(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _materialize(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_materialize(item) for item in value]
    return value


def _mapping(value: Mapping[str, object]) -> dict[str, object]:
    materialized = _materialize(value)
    if not isinstance(materialized, dict):
        raise TypeError("read payload must be a mapping")
    return materialized


def _optional_mapping_decimal(value: Mapping[str, object], field_name: str) -> Decimal | None:
    raw = value.get(field_name)
    if raw is None:
        return None
    try:
        parsed = Decimal(str(raw))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _provenance_response(value: ProvenanceView) -> ProvenanceResponse:
    provenance = value
    return ProvenanceResponse(
        provider=provenance.provider,
        source_id=provenance.source_id,
        observed_at=provenance.observed_at,
        parser_version=provenance.parser_version,
        raw_payload_hash=provenance.raw_payload_hash,
    )


def _page_response(
    page: Page[SourceT], mapper: Callable[[SourceT], ResponseT]
) -> PageResponse[ResponseT]:
    return PageResponse(
        items=[mapper(item) for item in page.items],
        limit=page.limit,
        has_more=page.has_more,
        next_cursor=page.next_cursor,
    )
