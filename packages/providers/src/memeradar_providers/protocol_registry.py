"""Versioned Solana protocol identity registry and canonical decoder.

The registry is the only routing table for protocol instructions.  A
discriminator/tag is never sufficient by itself; program identity is always
part of the lookup key.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Protocol, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_application.stream_integrity import RawChainTransaction
from memeradar_domain import (
    NormalizedChainEvent,
    Provenance,
    RecoveryState,
)
from memeradar_domain.common import ensure_utc, freeze_mapping, require_text
from memeradar_domain.identities import require_solana_address

from .launchpad_dex import (
    MeteoraAdapter,
    ParsedProtocolEvent,
    ProtocolEventType,
    PumpFunAdapter,
    PumpSwapAdapter,
    RaydiumAdapter,
)
from .pump_fun_idl import (
    PUMP_FUN_CREATION_DOC_SOURCE,
    PUMP_FUN_IDL_REVISION,
    PUMP_FUN_IDL_SHA256,
    PUMP_FUN_IDL_SOURCE,
    PUMP_FUN_LOCAL_SCHEMA_VERSION,
    PUMP_FUN_PROTOCOL_DRIFT_DETECTED,
    pump_fun_protocol_pin_status,
)
from .solana_raw_stream import (
    PUMP_FUN_BUY_EXACT_QUOTE_IN_V2_TAG,
    PUMP_FUN_BUY_TAG,
    PUMP_FUN_BUY_V2_TAG,
    PUMP_FUN_CREATE_TAG,
    PUMP_FUN_CREATE_V2_TAG,
    PUMP_FUN_MIGRATE_TAG,
    PUMP_FUN_PROGRAM_ID,
    PUMP_FUN_SELL_TAG,
    PUMP_FUN_SELL_V2_TAG,
)
from .transport import ProviderSchemaError

PROTOCOL_REGISTRY_VERSION = "protocol-registry-v1"


class ProgramKind(str, Enum):
    ANCHOR = "ANCHOR"
    NATIVE = "NATIVE"


class ProtocolVerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    TODO_VERIFY = "TODO_VERIFY"
    UNVERIFIED = "UNVERIFIED"
    CONFLICTED = "CONFLICTED"


class ProtocolSupportStatus(str, Enum):
    SUPPORTED_VERIFIED = "SUPPORTED_VERIFIED"
    SUPPORTED_NEEDS_REVERIFY = "SUPPORTED_NEEDS_REVERIFY"
    NOT_SUPPORTED_PLANNED = "NOT_SUPPORTED_PLANNED"
    NOT_SUPPORTED_OUT_OF_SCOPE = "NOT_SUPPORTED_OUT_OF_SCOPE"


class ProtocolCertificationStatus(str, Enum):
    """Deployment certification state; stronger than decoder identity pinning."""

    UNVERIFIED = "UNVERIFIED"
    TODO_VERIFY = "TODO_VERIFY"
    VERIFIED_READ_ONLY = "VERIFIED_READ_ONLY"
    VERIFIED_QUOTE = "VERIFIED_QUOTE"
    VERIFIED_PAPER = "VERIFIED_PAPER"
    DEPRECATED = "DEPRECATED"
    PROTOCOL_DRIFT = "PROTOCOL_DRIFT"


class UnsupportedProtocolInput(ValueError):
    """Base fail-closed error for unknown or non-authoritative routing."""

    reason_code = "UNSUPPORTED_PROTOCOL_INPUT"


class UnknownProtocolInput(UnsupportedProtocolInput):
    reason_code = "UNKNOWN_PROTOCOL_INPUT"


class UnverifiedProtocolInput(UnsupportedProtocolInput):
    reason_code = "UNVERIFIED_PROTOCOL_INPUT"


class ProtocolDriftDetected(UnverifiedProtocolInput):
    reason_code = PUMP_FUN_PROTOCOL_DRIFT_DETECTED


def _tag(value: str | bytes | int) -> str:
    if isinstance(value, bytes):
        if not value:
            raise ValueError("discriminator_or_tag must not be empty")
        return value.hex()
    if isinstance(value, bool) or not isinstance(value, str | int):
        raise TypeError("discriminator_or_tag must be text, bytes or an integer")
    if isinstance(value, int):
        if value < 0:
            raise ValueError("native tag must not be negative")
        return str(value)
    return require_text(value, "discriminator_or_tag", max_length=128).lower()


def anchor_discriminator(instruction_name: str) -> bytes:
    """Derive Anchor's first eight ``global:<name>`` SHA-256 bytes."""

    name = require_text(instruction_name, "instruction_name", max_length=128)
    return hashlib.sha256(f"global:{name}".encode()).digest()[:8]


def account_discriminator(account_name: str) -> bytes:
    """Derive Anchor's first eight ``account:<name>`` SHA-256 bytes."""

    name = require_text(account_name, "account_name", max_length=128)
    return hashlib.sha256(f"account:{name}".encode()).digest()[:8]


def native_tag(value: int | str) -> str:
    """Normalize an explicit native opcode without pretending it is Anchor."""

    if isinstance(value, bool) or not isinstance(value, int | str):
        raise TypeError("native tag must be an integer or text")
    return _tag(value)


@dataclass(frozen=True, slots=True)
class ProtocolRegistryEntry:
    """One immutable, versioned program/instruction identity definition."""

    protocol: str
    program_id: str
    program_kind: ProgramKind | str
    instruction_name: str
    discriminator_or_tag: str | bytes | int
    supported_event_types: Sequence[str] = ()
    verification_status: ProtocolVerificationStatus | str = ProtocolVerificationStatus.TODO_VERIFY
    support_status: ProtocolSupportStatus | str = ProtocolSupportStatus.SUPPORTED_NEEDS_REVERIFY
    sources: Sequence[str] = ()
    decoder_version: str = "unknown"
    registry_version: str = PROTOCOL_REGISTRY_VERSION
    verified_at: datetime | None = None
    account_discriminators: Sequence[str | bytes] = ()
    upstream_source: str | None = None
    upstream_revision: str | None = None
    idl_sha256: str | None = None
    local_schema_version: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "protocol", require_text(self.protocol, "protocol", max_length=128)
        )
        try:
            object.__setattr__(
                self, "program_id", require_solana_address(self.program_id, "program_id")
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("program_id must be a canonical Solana address") from exc
        object.__setattr__(self, "program_kind", ProgramKind(self.program_kind))
        object.__setattr__(
            self,
            "instruction_name",
            require_text(self.instruction_name, "instruction_name", max_length=128),
        )
        object.__setattr__(
            self,
            "discriminator_or_tag",
            _tag(self.discriminator_or_tag),
        )
        normalized_events: list[str] = []
        for event_type in self.supported_event_types:
            value = require_text(event_type, "supported_event_type", max_length=128).lower()
            if value not in normalized_events:
                normalized_events.append(value)
        object.__setattr__(self, "supported_event_types", tuple(normalized_events))
        object.__setattr__(
            self,
            "verification_status",
            ProtocolVerificationStatus(self.verification_status),
        )
        object.__setattr__(self, "support_status", ProtocolSupportStatus(self.support_status))
        object.__setattr__(self, "sources", _text_tuple(self.sources, "sources", 512))
        object.__setattr__(
            self,
            "decoder_version",
            require_text(self.decoder_version, "decoder_version", max_length=128),
        )
        object.__setattr__(
            self,
            "registry_version",
            require_text(self.registry_version, "registry_version", max_length=128),
        )
        if self.verified_at is not None:
            object.__setattr__(self, "verified_at", ensure_utc(self.verified_at, "verified_at"))
        if self.verification_status is ProtocolVerificationStatus.VERIFIED:
            if self.verified_at is None:
                raise ValueError("verified protocol identities require verified_at")
            if not self.sources:
                raise ValueError("verified protocol identities require sources")
            if self.support_status is not ProtocolSupportStatus.SUPPORTED_VERIFIED:
                raise ValueError("verified protocol identities require supported verification")
        for field_name in (
            "upstream_source",
            "upstream_revision",
            "idl_sha256",
            "local_schema_version",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_text(value, field_name, max_length=512),
                )
        normalized_accounts: list[str] = []
        for discriminator in self.account_discriminators:
            value = _tag(discriminator)
            if value not in normalized_accounts:
                normalized_accounts.append(value)
        object.__setattr__(self, "account_discriminators", tuple(normalized_accounts))

    @property
    def key(self) -> tuple[str, str]:
        return self.program_id, cast(str, self.discriminator_or_tag)

    @property
    def verification_sources(self) -> tuple[str, ...]:
        return tuple(self.sources)

    @property
    def authoritative(self) -> bool:
        return (
            self.verification_status is ProtocolVerificationStatus.VERIFIED
            and self.support_status is ProtocolSupportStatus.SUPPORTED_VERIFIED
        )

    @property
    def protocol_pin_status(self) -> str:
        if self.protocol != "pump.fun":
            return "OK"
        if any(
            value is None
            for value in (
                self.upstream_revision,
                self.idl_sha256,
                self.local_schema_version,
            )
        ):
            return PUMP_FUN_PROTOCOL_DRIFT_DETECTED
        return pump_fun_protocol_pin_status(
            upstream_revision=cast(str, self.upstream_revision),
            idl_sha256=cast(str, self.idl_sha256),
            local_schema_version=cast(str, self.local_schema_version),
        )


@dataclass(frozen=True, slots=True)
class ProtocolCertificationRecord:
    """Machine-readable evidence record for one protocol deployment."""

    provider: str
    protocol: str
    chain_id: str | int
    contract_address: str | None = None
    runtime_bytecode_hash: str | None = None
    contract_interface_identity: str | None = None
    event_signatures: Sequence[str] = ()
    known_block: int | None = None
    known_transaction: str | None = None
    decoded_sample_event: Mapping[str, object] | None = None
    provider_timestamp: datetime | None = None
    normalized_output: Mapping[str, object] | None = None
    protocol_version: str | None = None
    last_verified_at: datetime | None = None
    status: ProtocolCertificationStatus | str = ProtocolCertificationStatus.TODO_VERIFY
    evidence_sources: Sequence[str] = ()
    contract_applicable: bool = True
    registry_version: str = "protocol-certification-v1"

    def __post_init__(self) -> None:
        for field_name in ("provider", "protocol"):
            object.__setattr__(
                self,
                field_name,
                require_text(getattr(self, field_name), field_name, max_length=128),
            )
        if isinstance(self.chain_id, bool) or not isinstance(self.chain_id, str | int):
            raise TypeError("chain_id must be text or an integer")
        if isinstance(self.chain_id, int) and self.chain_id < 0:
            raise ValueError("chain_id must not be negative")
        if isinstance(self.chain_id, str):
            object.__setattr__(
                self,
                "chain_id",
                require_text(self.chain_id, "chain_id", max_length=128),
            )
        if self.contract_address is not None:
            object.__setattr__(
                self,
                "contract_address",
                require_text(self.contract_address, "contract_address", max_length=128),
            )
        for field_name in ("runtime_bytecode_hash", "contract_interface_identity"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_text(value, field_name, max_length=512),
                )
        object.__setattr__(
            self,
            "event_signatures",
            _text_tuple(self.event_signatures, "event_signatures", 512),
        )
        if self.known_block is not None:
            if isinstance(self.known_block, bool) or not isinstance(self.known_block, int):
                raise TypeError("known_block must be an integer")
            if self.known_block < 0:
                raise ValueError("known_block must not be negative")
        for field_name in ("known_transaction", "protocol_version", "registry_version"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_text(value, field_name, max_length=512),
                )
        for field_name in ("decoded_sample_event", "normalized_output"):
            value = getattr(self, field_name)
            if value is not None:
                if not isinstance(value, Mapping):
                    raise TypeError(f"{field_name} must be a mapping")
                object.__setattr__(self, field_name, freeze_mapping(value, field_name))
        for field_name in ("provider_timestamp", "last_verified_at"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, ensure_utc(value, field_name))
        object.__setattr__(self, "status", ProtocolCertificationStatus(self.status))
        object.__setattr__(
            self,
            "evidence_sources",
            _text_tuple(self.evidence_sources, "evidence_sources", 512),
        )
        if not isinstance(self.contract_applicable, bool):
            raise TypeError("contract_applicable must be boolean")
        if self.status in {
            ProtocolCertificationStatus.VERIFIED_READ_ONLY,
            ProtocolCertificationStatus.VERIFIED_QUOTE,
            ProtocolCertificationStatus.VERIFIED_PAPER,
        }:
            missing = self.missing_evidence
            if missing:
                raise ValueError("verified certificate requires " + ", ".join(missing))

    @property
    def missing_evidence(self) -> tuple[str, ...]:
        required = [
            "contract_interface_identity",
            "event_signatures",
            "known_block",
            "known_transaction",
            "decoded_sample_event",
            "provider_timestamp",
            "normalized_output",
            "protocol_version",
            "last_verified_at",
        ]
        if self.contract_applicable:
            required[0:0] = ["contract_address", "runtime_bytecode_hash"]
        return tuple(
            field_name
            for field_name in required
            if (
                getattr(self, field_name) is None
                or getattr(self, field_name) == ()
                or getattr(self, field_name) == {}
            )
        )

    @property
    def complete(self) -> bool:
        return not self.missing_evidence

    def to_mapping(self) -> Mapping[str, object]:
        """Return JSON-compatible evidence without exposing mutable internals."""

        def plain(value: object) -> object:
            if isinstance(value, Mapping):
                return {str(key): plain(item) for key, item in value.items()}
            if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
                return [plain(item) for item in value]
            if isinstance(value, datetime):
                return value.isoformat()
            return value

        return {
            "provider": self.provider,
            "protocol": self.protocol,
            "chain_id": self.chain_id,
            "contract_address": self.contract_address,
            "runtime_bytecode_hash": self.runtime_bytecode_hash,
            "contract_interface_identity": self.contract_interface_identity,
            "event_signatures": list(self.event_signatures),
            "known_block": self.known_block,
            "known_transaction": self.known_transaction,
            "decoded_sample_event": plain(self.decoded_sample_event),
            "provider_timestamp": plain(self.provider_timestamp),
            "normalized_output": plain(self.normalized_output),
            "protocol_version": self.protocol_version,
            "last_verified_at": plain(self.last_verified_at),
            "status": cast(ProtocolCertificationStatus, self.status).value,
            "evidence_sources": list(self.evidence_sources),
            "contract_applicable": self.contract_applicable,
            "registry_version": self.registry_version,
        }


def _text_tuple(values: Sequence[str], field_name: str, max_length: int) -> tuple[str, ...]:
    if isinstance(values, str | bytes | bytearray):
        raise TypeError(f"{field_name} must be a sequence")
    result: list[str] = []
    for value in values:
        normalized = require_text(value, field_name, max_length=max_length)
        if normalized not in result:
            result.append(normalized)
    return tuple(result)


class ProtocolIdentityRegistry:
    """Immutable full-key routing registry."""

    def __init__(
        self,
        entries: Sequence[ProtocolRegistryEntry] = (),
        *,
        version: str | None = None,
    ) -> None:
        normalized = tuple(entries)
        if any(not isinstance(entry, ProtocolRegistryEntry) for entry in normalized):
            raise TypeError("entries must contain ProtocolRegistryEntry values")
        mapping: dict[tuple[str, str], ProtocolRegistryEntry] = {}
        for entry in normalized:
            if entry.key in mapping:
                raise ValueError(f"duplicate protocol identity: {entry.key}")
            mapping[entry.key] = entry
        versions = {entry.registry_version for entry in normalized}
        if version is not None:
            normalized_version = require_text(version, "version", max_length=128)
        elif len(versions) == 1:
            normalized_version = next(iter(versions))
        else:
            normalized_version = PROTOCOL_REGISTRY_VERSION
        if versions and any(item != normalized_version for item in versions):
            raise ValueError("all protocol entries must use one registry version")
        self._entries = tuple(sorted(normalized, key=lambda entry: entry.key))
        self._mapping = mapping
        self.version = normalized_version

    @property
    def entries(self) -> tuple[ProtocolRegistryEntry, ...]:
        return self._entries

    def route(
        self,
        program_id: str,
        discriminator_or_tag: str | bytes | int,
    ) -> ProtocolRegistryEntry:
        """Resolve only a complete program-ID plus discriminator/tag key."""

        try:
            normalized_program = require_solana_address(program_id, "program_id")
        except (TypeError, ValueError) as exc:
            raise UnknownProtocolInput("program identity is invalid") from exc
        key = (normalized_program, _tag(discriminator_or_tag))
        entry = self._mapping.get(key)
        if entry is None:
            raise UnknownProtocolInput("program/discriminator identity is not registered")
        if (
            entry.verification_status is not ProtocolVerificationStatus.VERIFIED
            or entry.support_status is not ProtocolSupportStatus.SUPPORTED_VERIFIED
        ):
            raise UnverifiedProtocolInput(
                "protocol identity is not authoritative: "
                f"{cast(ProtocolVerificationStatus, entry.verification_status).value}"
            )
        if entry.protocol_pin_status != "OK":
            raise ProtocolDriftDetected(PUMP_FUN_PROTOCOL_DRIFT_DETECTED)
        return entry

    def find(
        self, program_id: str, discriminator_or_tag: str | bytes | int
    ) -> ProtocolRegistryEntry | None:
        """Return a definition without treating it as authoritative."""

        try:
            key = (require_solana_address(program_id, "program_id"), _tag(discriminator_or_tag))
        except (TypeError, ValueError):
            return None
        return self._mapping.get(key)

    def route_by_discriminator(
        self, discriminator_or_tag: str | bytes | int
    ) -> ProtocolRegistryEntry:
        """Reject the unsafe discriminator-only routing shape explicitly."""

        del discriminator_or_tag
        raise UnknownProtocolInput("program_id is required for protocol routing")


@dataclass(frozen=True, slots=True)
class ProtocolCoverageAudit:
    name: str
    status: ProtocolSupportStatus
    registered: bool
    decoder_available: bool
    notes: str


_AUDIT_TARGETS: tuple[tuple[str, str, bool, ProtocolSupportStatus, str], ...] = (
    (
        "Pump.fun",
        "pump.fun",
        True,
        ProtocolSupportStatus.SUPPORTED_NEEDS_REVERIFY,
        (
            "Existing PumpFunAdapter is preserved; program identity requires "
            "authoritative re-verification."
        ),
    ),
    (
        "PumpSwap",
        "pumpswap",
        True,
        ProtocolSupportStatus.SUPPORTED_NEEDS_REVERIFY,
        (
            "Existing PumpSwapAdapter is preserved; program identity requires "
            "authoritative re-verification."
        ),
    ),
    (
        "Raydium AMM v4",
        "raydium",
        True,
        ProtocolSupportStatus.SUPPORTED_NEEDS_REVERIFY,
        (
            "Existing RaydiumAdapter covers normalized lifecycle aliases; AMM-v4 "
            "identity is TODO_VERIFY."
        ),
    ),
    (
        "Raydium CPMM",
        "raydium",
        True,
        ProtocolSupportStatus.SUPPORTED_NEEDS_REVERIFY,
        "Existing RaydiumAdapter is shared; CPMM instruction identity is TODO_VERIFY.",
    ),
    (
        "Raydium CLMM",
        "raydium",
        True,
        ProtocolSupportStatus.SUPPORTED_NEEDS_REVERIFY,
        "Existing RaydiumAdapter is shared; CLMM instruction identity is TODO_VERIFY.",
    ),
    (
        "Raydium LaunchLab / LetsBonk",
        "raydium-launchlab",
        False,
        ProtocolSupportStatus.NOT_SUPPORTED_PLANNED,
        "No dedicated verified decoder is added by E8.4.",
    ),
    (
        "Meteora DLMM",
        "meteora",
        True,
        ProtocolSupportStatus.SUPPORTED_NEEDS_REVERIFY,
        (
            "Existing MeteoraAdapter covers normalized lifecycle aliases; DLMM "
            "identity is TODO_VERIFY."
        ),
    ),
    (
        "Meteora DAMM v2",
        "meteora",
        True,
        ProtocolSupportStatus.SUPPORTED_NEEDS_REVERIFY,
        "Existing MeteoraAdapter is shared; DAMM v2 identity is TODO_VERIFY.",
    ),
    (
        "Meteora DBC / Believe",
        "meteora-dbc",
        False,
        ProtocolSupportStatus.NOT_SUPPORTED_PLANNED,
        "Migration path is audited only; no unverified decoder is claimed.",
    ),
    (
        "Orca Whirlpools",
        "orca-whirlpools",
        False,
        ProtocolSupportStatus.NOT_SUPPORTED_PLANNED,
        "No dedicated decoder is in the approved current roadmap slice.",
    ),
    (
        "Moonshot",
        "moonshot",
        False,
        ProtocolSupportStatus.NOT_SUPPORTED_OUT_OF_SCOPE,
        "No dedicated decoder is required for current MemeRadar acceptance.",
    ),
)


def protocol_registry_audit(
    registry: ProtocolIdentityRegistry | None = None,
) -> tuple[ProtocolCoverageAudit, ...]:
    """Classify required protocol coverage without auto-claiming support."""

    active = registry or DEFAULT_PROTOCOL_REGISTRY
    registered_protocols = {entry.protocol for entry in active.entries}
    return tuple(
        ProtocolCoverageAudit(
            name=name,
            status=status,
            registered=protocol in registered_protocols,
            decoder_available=decoder_available,
            notes=notes,
        )
        for name, protocol, decoder_available, status, notes in _AUDIT_TARGETS
    )


def _production_entry(
    *,
    protocol: str,
    program_id: str,
    kind: ProgramKind,
    instruction_name: str,
    tag: str | bytes | int,
    source: str,
) -> ProtocolRegistryEntry:
    return ProtocolRegistryEntry(
        protocol=protocol,
        program_id=program_id,
        program_kind=kind,
        instruction_name=instruction_name,
        discriminator_or_tag=tag,
        supported_event_types=(instruction_name,),
        verification_status=ProtocolVerificationStatus.TODO_VERIFY,
        support_status=ProtocolSupportStatus.SUPPORTED_NEEDS_REVERIFY,
        sources=(source,),
        decoder_version="launchpad-dex-v2",
        registry_version=PROTOCOL_REGISTRY_VERSION,
    )


def _verified_production_entry(
    *,
    protocol: str,
    program_id: str,
    kind: ProgramKind,
    instruction_name: str,
    tag: str | bytes | int,
    sources: Sequence[str],
    verified_at: datetime,
    upstream_source: str | None = None,
    upstream_revision: str | None = None,
    idl_sha256: str | None = None,
    local_schema_version: str | None = None,
) -> ProtocolRegistryEntry:
    return ProtocolRegistryEntry(
        protocol=protocol,
        program_id=program_id,
        program_kind=kind,
        instruction_name=instruction_name,
        discriminator_or_tag=tag,
        supported_event_types=(instruction_name,),
        verification_status=ProtocolVerificationStatus.VERIFIED,
        support_status=ProtocolSupportStatus.SUPPORTED_VERIFIED,
        sources=sources,
        decoder_version="pumpfun-idl-v1" if protocol == "pump.fun" else "launchpad-dex-v2",
        registry_version=PROTOCOL_REGISTRY_VERSION,
        verified_at=verified_at,
        upstream_source=upstream_source,
        upstream_revision=upstream_revision,
        idl_sha256=idl_sha256,
        local_schema_version=local_schema_version,
    )


def _verified_pump_fun_entry(
    *, instruction_name: str, tag: str | bytes | int
) -> ProtocolRegistryEntry:
    return _verified_production_entry(
        protocol="pump.fun",
        program_id=PUMP_FUN_PROGRAM_ID,
        kind=ProgramKind.ANCHOR,
        instruction_name=instruction_name,
        tag=tag,
        sources=(PUMP_FUN_IDL_SOURCE, PUMP_FUN_CREATION_DOC_SOURCE),
        verified_at=datetime(2026, 9, 20, tzinfo=UTC),
        upstream_source=PUMP_FUN_IDL_SOURCE,
        upstream_revision=PUMP_FUN_IDL_REVISION,
        idl_sha256=PUMP_FUN_IDL_SHA256,
        local_schema_version=PUMP_FUN_LOCAL_SCHEMA_VERSION,
    )


# Verified entries below have current primary documentation, derived tags,
# keyless decoder fixtures and a live program-identity cross-check. Remaining
# entries stay provisional and cannot route authoritative production evidence.
DEFAULT_PROTOCOL_REGISTRY = ProtocolIdentityRegistry(
    (
        _verified_pump_fun_entry(instruction_name="create", tag=PUMP_FUN_CREATE_TAG),
        _verified_pump_fun_entry(instruction_name="create_v2", tag=PUMP_FUN_CREATE_V2_TAG),
        _verified_pump_fun_entry(instruction_name="buy", tag=PUMP_FUN_BUY_TAG),
        _verified_pump_fun_entry(instruction_name="buy_v2", tag=PUMP_FUN_BUY_V2_TAG),
        _verified_pump_fun_entry(
            instruction_name="buy_exact_quote_in_v2", tag=PUMP_FUN_BUY_EXACT_QUOTE_IN_V2_TAG
        ),
        _verified_pump_fun_entry(instruction_name="sell", tag=PUMP_FUN_SELL_TAG),
        _verified_pump_fun_entry(instruction_name="sell_v2", tag=PUMP_FUN_SELL_V2_TAG),
        _verified_pump_fun_entry(instruction_name="migrate", tag=PUMP_FUN_MIGRATE_TAG),
        _production_entry(
            protocol="pump.fun",
            # Current Pump public docs publish ...hRvf...; retain TODO_VERIFY
            # until the instruction/event payload decoder is independently checked.
            program_id=PUMP_FUN_PROGRAM_ID,
            kind=ProgramKind.ANCHOR,
            instruction_name="trade",
            tag=anchor_discriminator("trade"),
            source=(
                "https://github.com/pump-fun/pump-public-docs/blob/main/"
                "docs/PUMP_PROGRAM_README.md"
            ),
        ),
        _production_entry(
            protocol="pumpswap",
            program_id="pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",
            kind=ProgramKind.ANCHOR,
            instruction_name="swap",
            tag=anchor_discriminator("swap"),
            source="independent-public-pumpswap-program-reference",
        ),
        _production_entry(
            protocol="raydium",
            program_id="675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
            kind=ProgramKind.NATIVE,
            instruction_name="initialize",
            tag=native_tag(0),
            source="official-public-raydium-program-reference",
        ),
        _production_entry(
            protocol="raydium-cpmm",
            program_id="CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C",
            kind=ProgramKind.ANCHOR,
            instruction_name="swap",
            tag=anchor_discriminator("swap"),
            source="official-public-raydium-program-reference",
        ),
        _production_entry(
            protocol="raydium-clmm",
            program_id="CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",
            kind=ProgramKind.ANCHOR,
            instruction_name="swap",
            tag=anchor_discriminator("swap"),
            source="official-public-raydium-program-reference",
        ),
    )
)


def protocol_certification_registry(
    registry: ProtocolIdentityRegistry | None = None,
) -> tuple[ProtocolCertificationRecord, ...]:
    """Project registered identities and EVM candidates into strict certificates.

    Decoder identity and fixture coverage are deliberately insufficient for a
    deployment certificate.  Until live bytecode, a known transaction, a
    decoded sample and normalized output are supplied, the projection remains
    ``TODO_VERIFY`` even when the canonical decoder can route the identity.
    """

    active = registry or DEFAULT_PROTOCOL_REGISTRY
    grouped: dict[tuple[str, str], list[ProtocolRegistryEntry]] = {}
    for entry in active.entries:
        grouped.setdefault((entry.protocol, entry.program_id), []).append(entry)
    records: list[ProtocolCertificationRecord] = []
    for (protocol, program_id), entries in sorted(grouped.items()):
        first = entries[0]
        records.append(
            ProtocolCertificationRecord(
                provider="solana-rpc",
                protocol=protocol,
                chain_id="solana:mainnet-beta",
                contract_address=program_id,
                contract_interface_identity=ProgramKind(first.program_kind).value,
                event_signatures=tuple(
                    sorted({cast(str, entry.discriminator_or_tag) for entry in entries})
                ),
                protocol_version=first.decoder_version,
                last_verified_at=max(
                    (entry.verified_at for entry in entries if entry.verified_at is not None),
                    default=None,
                ),
                status=ProtocolCertificationStatus.TODO_VERIFY,
                evidence_sources=tuple(
                    sorted({source for entry in entries for source in entry.sources})
                ),
            )
        )

    # EVM candidates are intentionally imported lazily to keep the Solana
    # identity module independent of the EVM parser module at import time.
    from .evm_protocols import EVM_PROTOCOL_CANDIDATES

    for deployment in EVM_PROTOCOL_CANDIDATES:
        records.append(
            ProtocolCertificationRecord(
                provider="evm-rpc",
                protocol=deployment.protocol,
                chain_id=str(deployment.chain_id),
                contract_address=deployment.contract_address,
                runtime_bytecode_hash=deployment.runtime_code_hash,
                event_signatures=tuple(deployment.event_topics.values()),
                known_transaction=deployment.sample_transaction,
                status=ProtocolCertificationStatus.TODO_VERIFY,
                evidence_sources=(deployment.verification_source,)
                if deployment.verification_source is not None
                else (),
            )
        )
    return tuple(records)


DEFAULT_PROTOCOL_CERTIFICATION_REGISTRY = protocol_certification_registry()


class CanonicalProtocolDecoder:
    """Decode one raw transaction path for live, backfill and replay modes."""

    def __init__(
        self,
        registry: ProtocolIdentityRegistry,
        *,
        adapters: Mapping[str, object] | None = None,
    ) -> None:
        if not isinstance(registry, ProtocolIdentityRegistry):
            raise TypeError("registry must be a ProtocolIdentityRegistry")
        self.registry = registry
        self.decode_invocations = 0
        self._adapters = dict(
            adapters
            or {
                "pump.fun": PumpFunAdapter(),
                "pumpswap": PumpSwapAdapter(),
                "raydium": RaydiumAdapter(),
                "meteora": MeteoraAdapter(),
            }
        )

    def decode(
        self,
        transaction: RawChainTransaction,
        *,
        recovery_state: RecoveryState = RecoveryState.LIVE_OBSERVED,
        backfill_source: str | None = None,
        recovery_at: datetime | None = None,
    ) -> NormalizedChainEvent:
        if not isinstance(transaction, RawChainTransaction):
            raise TypeError("transaction must be a RawChainTransaction")
        entry = self.registry.route(transaction.program_id, transaction.discriminator_or_tag)
        self.decode_invocations += 1
        payload = dict(transaction.payload)
        # ``route`` only returns full-key, authoritatively verified identities.
        # Preserve that fact beside the normalized event so downstream early
        # detection can distinguish canonical chain evidence from an untrusted
        # protocol-shaped payload without importing this provider package.
        payload["protocol_identity_verified"] = True
        payload["protocol_registry_version"] = entry.registry_version
        if entry.upstream_source is not None:
            payload["upstream_source"] = entry.upstream_source
        if entry.upstream_revision is not None:
            payload["upstream_revision"] = entry.upstream_revision
        if entry.idl_sha256 is not None:
            payload["idl_sha256"] = entry.idl_sha256
        if entry.local_schema_version is not None:
            payload["local_schema_version"] = entry.local_schema_version
        adapter = self._adapters.get(entry.protocol)
        normalized_event_type = entry.instruction_name
        if adapter is not None:
            if not hasattr(adapter, "parse"):
                raise ProviderSchemaError("configured protocol decoder is invalid")
            parser = cast(_LaunchpadAdapter, adapter)
            requested_at = transaction.observed_at
            context = ProviderRequestContext(
                correlation_id=f"chain:{transaction.signature}",
                requested_at=requested_at,
                deadline_at=max(transaction.ingested_at, requested_at + timedelta(seconds=1)),
            )
            message = {
                "event_type": entry.instruction_name,
                "source_id": transaction.signature,
                "occurred_at": transaction.occurred_at,
                "schema_version": 2 if transaction.event_schema_version >= 2 else 1,
                "data": payload,
            }
            parsed = parser.parse(message, context)
            normalized_event_type = (
                cast(ProtocolEventType, parsed.protocol_event_type).value
                if parsed.protocol_event_type is not None
                else parsed.event_type
            )
            payload = dict(parsed.to_observation().normalized_payload)
        token_id = _token_id_from_payload(payload)
        return NormalizedChainEvent(
            chain=transaction.chain,
            slot=transaction.slot,
            signature=transaction.signature,
            event_index=transaction.event_index,
            program_id=entry.program_id,
            discriminator_or_tag=entry.discriminator_or_tag,
            protocol=entry.protocol,
            event_type=normalized_event_type,
            source_transport=transaction.transport,
            occurred_at=transaction.occurred_at,
            observed_at=transaction.observed_at,
            ingested_at=transaction.ingested_at,
            commitment=transaction.commitment,
            recovery_state=recovery_state,
            provenance=Provenance(
                provider=transaction.transport,
                source_id=transaction.signature,
                observed_at=transaction.observed_at,
                parser_version=entry.decoder_version,
            ),
            normalized_payload=freeze_mapping(payload, "normalized_payload"),
            parser_version=entry.decoder_version,
            registry_version=entry.registry_version,
            event_schema_version=transaction.event_schema_version,
            token_id=token_id,
            backfill_source=backfill_source,
            recovery_at=recovery_at,
        )

    def decode_live(self, transaction: RawChainTransaction) -> NormalizedChainEvent:
        return self.decode(transaction, recovery_state=RecoveryState.LIVE_OBSERVED)

    def decode_backfill(
        self,
        transaction: RawChainTransaction,
        *,
        backfill_source: str,
        recovery_at: datetime,
    ) -> NormalizedChainEvent:
        return self.decode(
            transaction,
            recovery_state=RecoveryState.RECOVERED_UNVERIFIED,
            backfill_source=backfill_source,
            recovery_at=recovery_at,
        )

    def decode_replay(self, transaction: RawChainTransaction) -> NormalizedChainEvent:
        return self.decode(transaction, recovery_state=RecoveryState.LIVE_OBSERVED)


class _LaunchpadAdapter(Protocol):
    def parse(self, message: object, context: ProviderRequestContext) -> ParsedProtocolEvent:
        """Parse one transport-neutral protocol message."""


def _token_id_from_payload(payload: Mapping[str, object]) -> UUID | None:
    """Derive a token UUID only when a valid normalized mint is present."""

    for key in ("mint_address", "mint", "token_mint", "base_mint"):
        value = payload.get(key)
        if isinstance(value, str):
            try:
                require_solana_address(value, "mint")
            except (TypeError, ValueError):
                continue
            return uuid5(NAMESPACE_URL, f"memeradar:chain-token:{value}")
    return None


__all__ = [
    "CanonicalProtocolDecoder",
    "DEFAULT_PROTOCOL_CERTIFICATION_REGISTRY",
    "DEFAULT_PROTOCOL_REGISTRY",
    "ProtocolCertificationRecord",
    "ProtocolCertificationStatus",
    "ProgramKind",
    "ProtocolCoverageAudit",
    "ProtocolIdentityRegistry",
    "ProtocolDriftDetected",
    "ProtocolRegistryEntry",
    "ProtocolSupportStatus",
    "ProtocolVerificationStatus",
    "PROTOCOL_REGISTRY_VERSION",
    "UnknownProtocolInput",
    "UnverifiedProtocolInput",
    "UnsupportedProtocolInput",
    "account_discriminator",
    "anchor_discriminator",
    "native_tag",
    "protocol_certification_registry",
    "protocol_registry_audit",
]
