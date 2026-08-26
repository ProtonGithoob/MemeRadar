"""Redacted fixture recording and deterministic fake-provider support."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from memeradar_application.provider_contracts import ProviderCapability
from memeradar_domain.common import ensure_utc, freeze_mapping, require_text

from .transport import ProviderUnavailableError

_SENSITIVE_KEY_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "auth",
        "client_secret",
        "cookie",
        "id_token",
        "mnemonic",
        "passphrase",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "seed",
        "seed_phrase",
        "session",
        "session_cookie",
        "set_cookie",
        "x_api_key",
    }
)
_QUERY_SECRET = re.compile(
    r"(?i)((?:[?&])(?:api[_-]?key|access[_-]?token|bot[_-]?token|client[_-]?secret|"
    r"refresh[_-]?token|session[_-]?token)=)[^&#\s]+"
)
_BEARER = re.compile(r"(?i)(\bBearer\s+)[^\s,;]+")
_FIXTURE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


def _normalized_key(value: object) -> str:
    return str(value).strip().lower().replace("-", "_")


def _redact_text(value: str) -> str:
    return _BEARER.sub(r"\1[REDACTED]", _QUERY_SECRET.sub(r"\1[REDACTED]", value))


class FixtureRedactor:
    """Recursively redact credential-shaped mapping keys and URL/header values."""

    def redact(self, value: object) -> Any:
        if isinstance(value, Mapping):
            return {
                str(key): (
                    "[REDACTED]"
                    if _normalized_key(key) in _SENSITIVE_KEY_NAMES
                    or _normalized_key(key).endswith("_token")
                    else self.redact(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list | tuple):
            return [self.redact(item) for item in value]
        if isinstance(value, str):
            return _redact_text(value)
        if value is None or isinstance(value, int | float | bool):
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return self.redact(value.value)
        return str(value)


@dataclass(frozen=True, slots=True)
class FixtureMetadata:
    """Metadata required to replay one safe provider fixture."""

    provider: str
    capability: ProviderCapability | str
    endpoint: str
    captured_at: datetime
    schema_version: str
    parser_version: str
    redacted: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "provider", require_text(self.provider, "provider", max_length=128)
        )
        capability = (
            self.capability.value
            if isinstance(self.capability, ProviderCapability)
            else require_text(self.capability, "capability", max_length=64)
        )
        object.__setattr__(self, "capability", capability)
        object.__setattr__(
            self, "endpoint", require_text(self.endpoint, "endpoint", max_length=512)
        )
        object.__setattr__(self, "captured_at", ensure_utc(self.captured_at, "captured_at"))
        object.__setattr__(
            self,
            "schema_version",
            require_text(self.schema_version, "schema_version", max_length=64),
        )
        object.__setattr__(
            self,
            "parser_version",
            require_text(self.parser_version, "parser_version", max_length=64),
        )
        if self.redacted is not True:
            raise ValueError("fixture metadata must be marked redacted")


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class FixtureRecord:
    """Immutable redacted fixture payload."""

    name: str
    metadata: FixtureMetadata
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        name = require_text(self.name, "fixture name", max_length=128).lower()
        if not _FIXTURE_NAME.fullmatch(name):
            raise ValueError("fixture name must contain only lowercase safe filename characters")
        if not isinstance(self.metadata, FixtureMetadata):
            raise TypeError("metadata must be FixtureMetadata")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "payload", freeze_mapping(self.payload, "fixture payload"))

    def document(self) -> dict[str, object]:
        return {
            "metadata": {
                "provider": self.metadata.provider,
                "capability": self.metadata.capability,
                "endpoint": self.metadata.endpoint,
                "captured_at": self.metadata.captured_at.isoformat(),
                "schema_version": self.metadata.schema_version,
                "parser_version": self.metadata.parser_version,
                "redacted": self.metadata.redacted,
            },
            "name": self.name,
            "payload": _thaw(self.payload),
        }

    def to_json(self) -> str:
        return json.dumps(self.document(), sort_keys=True, separators=(",", ":"))


class FixtureConflict(ValueError):
    """Raised when a fixture name is reused for different safe content."""


class FixtureRecorder:
    """In-memory recorder that stores only recursively redacted fixture data."""

    def __init__(self, redactor: FixtureRedactor | None = None) -> None:
        self._redactor = redactor or FixtureRedactor()
        self._records: dict[str, FixtureRecord] = {}

    def record(
        self,
        name: str,
        metadata: FixtureMetadata,
        payload: Mapping[str, object],
    ) -> FixtureRecord:
        if not isinstance(metadata, FixtureMetadata):
            raise TypeError("metadata must be FixtureMetadata")
        safe_payload = self._redactor.redact(payload)
        if not isinstance(safe_payload, Mapping):
            raise TypeError("fixture payload must be a mapping")
        safe_metadata = replace(metadata, endpoint=_redact_text(metadata.endpoint))
        record = FixtureRecord(name=name, metadata=safe_metadata, payload=safe_payload)
        existing = self._records.get(record.name)
        if existing is not None:
            if existing != record:
                raise FixtureConflict(f"fixture {record.name!r} conflicts with existing content")
            return existing
        self._records[record.name] = record
        return record

    def get(self, name: str) -> FixtureRecord:
        normalized_name = require_text(name, "fixture name", max_length=128).lower()
        return self._records[normalized_name]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._records))

    def export(self, name: str) -> str:
        return self.get(name).to_json()

    def export_all(self) -> str:
        document = {name: self._records[name].document() for name in self.names()}
        return json.dumps(document, sort_keys=True, separators=(",", ":"))

    def write(self, directory: Path) -> tuple[Path, ...]:
        directory.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for name in self.names():
            path = directory / f"{name}.json"
            path.write_text(self.export(name) + "\n", encoding="utf-8")
            paths.append(path)
        return tuple(paths)


class FakeProvider:
    """Network-free provider response/failure source for adapter contract tests."""

    def __init__(
        self,
        provider_name: str,
        *,
        responses: Mapping[ProviderCapability | str, object] | None = None,
    ) -> None:
        self.provider_name = require_text(provider_name, "provider_name", max_length=128)
        self._responses = {
            self._capability_key(capability): response
            for capability, response in (responses or {}).items()
        }
        self._failures: dict[str, list[BaseException]] = {}
        self._calls: list[dict[str, str]] = []

    @staticmethod
    def _capability_key(capability: ProviderCapability | str) -> str:
        return (
            capability.value
            if isinstance(capability, ProviderCapability)
            else require_text(capability, "capability", max_length=64)
        )

    @property
    def calls(self) -> tuple[dict[str, str], ...]:
        return tuple(dict(call) for call in self._calls)

    def queue_failure(
        self,
        capability: ProviderCapability | str,
        error: BaseException,
    ) -> None:
        if not isinstance(error, BaseException):
            raise TypeError("error must be an exception")
        key = self._capability_key(capability)
        self._failures.setdefault(key, []).append(error)

    async def request(
        self,
        capability: ProviderCapability | str,
        *,
        request_type: str,
        correlation_id: str,
    ) -> object:
        key = self._capability_key(capability)
        call = {
            "capability": key,
            "request_type": require_text(request_type, "request_type", max_length=128),
            "correlation_id": require_text(correlation_id, "correlation_id", max_length=128),
        }
        self._calls.append(call)
        failures = self._failures.get(key)
        if failures:
            raise failures.pop(0)
        if key not in self._responses:
            raise ProviderUnavailableError("fake provider response is not configured")
        return self._responses[key]


__all__ = [
    "FakeProvider",
    "FixtureConflict",
    "FixtureMetadata",
    "FixtureRecord",
    "FixtureRecorder",
    "FixtureRedactor",
]
