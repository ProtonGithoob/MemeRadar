"""Versioned Solana protocol identity registry and canonical decoder.

The registry is the only routing table for protocol instructions.  A
discriminator/tag is never sufficient by itself; program identity is always
part of the lookup key.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
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


class UnsupportedProtocolInput(ValueError):
    """Base fail-closed error for unknown or non-authoritative routing."""

    reason_code = "UNSUPPORTED_PROTOCOL_INPUT"


class UnknownProtocolInput(UnsupportedProtocolInput):
    reason_code = "UNKNOWN_PROTOCOL_INPUT"


class UnverifiedProtocolInput(UnsupportedProtocolInput):
    reason_code = "UNVERIFIED_PROTOCOL_INPUT"


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


# These definitions are intentionally non-authoritative until the verification
# workflow in the extension has independently checked the current chain
# identity and instruction layout.  They provide an auditable place for the
# known program references without allowing them to route production evidence.
DEFAULT_PROTOCOL_REGISTRY = ProtocolIdentityRegistry(
    (
        _production_entry(
            protocol="pump.fun",
            program_id="6EF8rrecthR5Dkzon8Nwu78gNvfCKubJ14M5uBEwF6P",
            kind=ProgramKind.ANCHOR,
            instruction_name="trade",
            tag=anchor_discriminator("trade"),
            source="official-public-pump-program-reference",
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
    "DEFAULT_PROTOCOL_REGISTRY",
    "ProgramKind",
    "ProtocolCoverageAudit",
    "ProtocolIdentityRegistry",
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
    "protocol_registry_audit",
]
