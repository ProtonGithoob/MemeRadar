"""Versioned protocol identity and canonical decoder contracts."""

from datetime import UTC, datetime, timedelta

import pytest

from memeradar_application.stream_integrity import RawChainTransaction
from memeradar_domain import Chain, RecoveryState
from memeradar_providers.protocol_registry import (
    CanonicalProtocolDecoder,
    ProgramKind,
    ProtocolIdentityRegistry,
    ProtocolRegistryEntry,
    ProtocolSupportStatus,
    ProtocolVerificationStatus,
    UnknownProtocolInput,
    UnverifiedProtocolInput,
    account_discriminator,
    anchor_discriminator,
    protocol_registry_audit,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
PROGRAM_A = "11111111111111111111111111111111"
PROGRAM_B = MINT


def entry(
    *,
    program_id: str = PROGRAM_A,
    protocol: str = "fixture.protocol",
    discriminator: str | bytes | None = None,
    kind: ProgramKind = ProgramKind.ANCHOR,
    verification: ProtocolVerificationStatus = ProtocolVerificationStatus.VERIFIED,
    verified_at: datetime | None = NOW,
) -> ProtocolRegistryEntry:
    return ProtocolRegistryEntry(
        protocol=protocol,
        program_id=program_id,
        program_kind=kind,
        instruction_name="trade",
        discriminator_or_tag=discriminator or anchor_discriminator("trade"),
        supported_event_types=("trade",),
        verification_status=verification,
        support_status=(
            ProtocolSupportStatus.SUPPORTED_VERIFIED
            if verification is ProtocolVerificationStatus.VERIFIED
            else ProtocolSupportStatus.SUPPORTED_NEEDS_REVERIFY
        ),
        sources=("fixture-reference",),
        decoder_version="fixture-decoder-v1",
        registry_version="protocol-registry-v1",
        verified_at=verified_at if verification is ProtocolVerificationStatus.VERIFIED else None,
    )


def transaction(
    *,
    program_id: str = PROGRAM_A,
    discriminator: str | bytes | None = None,
    payload: dict[str, object] | None = None,
) -> RawChainTransaction:
    return RawChainTransaction(
        chain=Chain.SOLANA,
        slot=100,
        signature="registry-signature",
        event_index=0,
        program_id=program_id,
        discriminator_or_tag=discriminator or anchor_discriminator("trade"),
        payload=payload or {"mint": MINT},
        occurred_at=NOW,
        observed_at=NOW + timedelta(seconds=1),
        ingested_at=NOW + timedelta(seconds=2),
        transport="fixture-live",
    )


def test_anchor_and_account_discriminators_are_sha256_prefixes() -> None:
    assert (
        anchor_discriminator("trade") == __import__("hashlib").sha256(b"global:trade").digest()[:8]
    )
    assert (
        account_discriminator("Pool") == __import__("hashlib").sha256(b"account:Pool").digest()[:8]
    )


def test_registry_requires_program_id_and_discriminator_together() -> None:
    registry = ProtocolIdentityRegistry((entry(), entry(program_id=PROGRAM_B)))
    first = registry.route(PROGRAM_A, anchor_discriminator("trade"))
    second = registry.route(PROGRAM_B, anchor_discriminator("trade"))

    assert first.program_id == PROGRAM_A
    assert second.program_id == PROGRAM_B
    with pytest.raises(UnknownProtocolInput):
        registry.route(PROGRAM_A, anchor_discriminator("unknown"))


def test_discriminator_collision_does_not_route_to_wrong_program() -> None:
    registry = ProtocolIdentityRegistry((entry(), entry(program_id=PROGRAM_B, protocol="other")))

    assert registry.route(PROGRAM_A, anchor_discriminator("trade")).protocol == "fixture.protocol"
    assert registry.route(PROGRAM_B, anchor_discriminator("trade")).protocol == "other"


def test_unverified_identity_fails_closed() -> None:
    registry = ProtocolIdentityRegistry(
        (entry(verification=ProtocolVerificationStatus.TODO_VERIFY),)
    )

    with pytest.raises(UnverifiedProtocolInput, match="TODO_VERIFY"):
        registry.route(PROGRAM_A, anchor_discriminator("trade"))


def test_verified_identity_requires_a_date_and_supported_status() -> None:
    with pytest.raises(ValueError, match="verified_at"):
        entry(verified_at=None)


def test_native_tag_is_distinct_from_anchor_discriminator() -> None:
    native = entry(
        protocol="fixture.native",
        kind=ProgramKind.NATIVE,
        discriminator=7,
    )
    assert native.program_kind is ProgramKind.NATIVE
    assert native.discriminator_or_tag == "7"
    assert native.account_discriminators == ()


def test_registry_rejects_duplicate_full_identity() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        ProtocolIdentityRegistry((entry(), entry()))


def test_canonical_decoder_uses_one_path_for_live_backfill_and_replay() -> None:
    registry = ProtocolIdentityRegistry((entry(),))
    decoder = CanonicalProtocolDecoder(registry)
    tx = transaction()

    live = decoder.decode_live(tx)
    backfill = decoder.decode_backfill(
        tx,
        backfill_source="fixture-rpc",
        recovery_at=NOW + timedelta(seconds=3),
    )
    replay = decoder.decode_replay(tx)

    assert live.canonical_identity == backfill.canonical_identity == replay.canonical_identity
    assert live.normalized_payload == backfill.normalized_payload == replay.normalized_payload
    assert live.recovery_state is RecoveryState.LIVE_OBSERVED
    assert backfill.recovery_state is RecoveryState.RECOVERED_UNVERIFIED
    assert replay.recovery_state is RecoveryState.LIVE_OBSERVED
    assert decoder.decode_invocations == 3


def test_unknown_protocol_input_is_explicitly_unsupported() -> None:
    registry = ProtocolIdentityRegistry((entry(),))
    decoder = CanonicalProtocolDecoder(registry)

    with pytest.raises(UnknownProtocolInput):
        decoder.decode_live(transaction(discriminator=anchor_discriminator("unknown")))


def test_protocol_registry_audit_covers_required_targets_without_claiming_all_support() -> None:
    audit = protocol_registry_audit()
    names = {record.name for record in audit}

    assert {
        "Pump.fun",
        "PumpSwap",
        "Raydium AMM v4",
        "Raydium CPMM",
        "Raydium CLMM",
        "Raydium LaunchLab / LetsBonk",
        "Meteora DLMM",
        "Meteora DAMM v2",
        "Meteora DBC / Believe",
        "Orca Whirlpools",
        "Moonshot",
    } <= names
    assert all(
        record.status
        in {
            ProtocolSupportStatus.SUPPORTED_VERIFIED,
            ProtocolSupportStatus.SUPPORTED_NEEDS_REVERIFY,
            ProtocolSupportStatus.NOT_SUPPORTED_PLANNED,
            ProtocolSupportStatus.NOT_SUPPORTED_OUT_OF_SCOPE,
        }
        for record in audit
    )
