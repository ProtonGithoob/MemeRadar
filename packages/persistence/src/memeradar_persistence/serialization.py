"""Lossless-enough JSON representations for domain evidence metadata."""

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from memeradar_domain import Provenance, ReasonCode


def reason_codes_to_json(values: Sequence[ReasonCode]) -> list[dict[str, Any]]:
    return [
        {
            "code": value.code,
            "detail": value.detail,
            "evidence_refs": list(value.evidence_refs),
        }
        for value in values
    ]


def reason_codes_from_json(value: object) -> tuple[ReasonCode, ...]:
    if not isinstance(value, list):
        raise TypeError("reason_codes JSON must be a list")
    normalized: list[ReasonCode] = []
    for item in value:
        if not isinstance(item, dict):
            raise TypeError("reason code JSON entries must be objects")
        code = item.get("code")
        detail = item.get("detail")
        evidence_refs = item.get("evidence_refs", [])
        if not isinstance(code, str) or not isinstance(detail, str | type(None)):
            raise TypeError("reason code JSON has invalid code/detail")
        if not isinstance(evidence_refs, list) or not all(
            isinstance(reference, str) for reference in evidence_refs
        ):
            raise TypeError("reason code JSON has invalid evidence references")
        normalized.append(ReasonCode(code=code, detail=detail, evidence_refs=tuple(evidence_refs)))
    return tuple(normalized)


def provenance_to_json(values: Sequence[Provenance]) -> list[dict[str, Any]]:
    return [
        {
            "provider": value.provider,
            "source_id": value.source_id,
            "observed_at": value.observed_at.isoformat(),
            "parser_version": value.parser_version,
            "raw_payload_hash": value.raw_payload_hash,
            "raw_payload_ref": value.raw_payload_ref,
        }
        for value in values
    ]


def json_safe(value: object) -> Any:
    """Convert domain values to JSON-compatible values without logging secrets."""

    if isinstance(value, str | int | float | bool) or value is None:
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | UUID):
        return str(value)
    if isinstance(value, Enum):
        return json_safe(value.value)
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [json_safe(item) for item in value]
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")
