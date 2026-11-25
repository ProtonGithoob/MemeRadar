"""M1: bounded launch inventory, coverage ledger and reproducible cohort manifest.

The research cohort must be the *all-observed-launch* population of a bounded,
finalized slot window: every verified Pump.fun create, including tokens that
never trade, never graduate or die immediately.  Selecting only tokens that
later appeared on a DEX or pumped is survivorship bias and makes any recall or
base rate meaningless.

Two inventories of the same window are reconciled:

* ``primary`` -- the canonical path (finalized block scan through the same
  decoder used by live ingestion and backfill);
* ``independent`` -- a different retrieval path (an address index), so that a
  block-fetch or decoder-routing loss shows up as a disagreement.

Nothing here talks to a provider.  Inputs are plain records; outputs are a
coverage ledger and a manifest whose logical digest is identical for identical
inputs (run timestamps are excluded from the digest).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from memeradar_domain.common import ensure_utc, require_text
from memeradar_domain.identities import require_solana_address

LAUNCH_INVENTORY_VERSION = "launch-inventory-v1"
# Frozen before any labelling (plan M1): the eligible population is every
# successful, finalized create/create_v2 of the verified Pump.fun program in the
# window.  No trading, liquidity, DEX or outcome condition participates.
LAUNCH_ELIGIBILITY_VERSION = "pumpfun-all-observed-launch-v1"
LAUNCH_ELIGIBILITY_DEFINITION = (
    "chain=solana; program=6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P; "
    "instruction in {create, create_v2} routed by verified program+discriminator; "
    "transaction succeeded (meta.err is null); commitment=finalized; "
    "slot within the declared window; no trade, liquidity, listing or outcome filter"
)
PUMP_FUN_TOKEN_DECIMALS = 6
_LAUNCH_INSTRUCTIONS = frozenset({"create", "create_v2"})


class SlotState(str, Enum):
    SCANNED = "SCANNED"  # produced block, fully scanned
    SKIPPED = "SKIPPED"  # slot not produced (leader skipped)
    UNRESOLVED = "UNRESOLVED"  # could not be scanned; coverage unknown


class DataRights(str, Enum):
    OWN_COLLECTION = "OWN_COLLECTION"
    PERMITTED = "PERMITTED"
    UNKNOWN = "UNKNOWN"
    RESTRICTED = "RESTRICTED"


class InventoryRejection(ValueError):
    """An input record cannot enter any inventory (bad identity, time or unit)."""


@dataclass(frozen=True, slots=True)
class InventoryLaunch:
    mint: str
    signature: str
    slot: int
    block_time: datetime
    instruction: str
    source: str
    creator: str | None = None
    decimals: int | None = None
    transaction_failed: bool = False

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "mint", require_solana_address(self.mint, "mint"))
        except (TypeError, ValueError):
            raise InventoryRejection(f"ambiguous mint identity: {self.mint!r}") from None
        object.__setattr__(
            self, "signature", require_text(self.signature, "signature", max_length=128)
        )
        if isinstance(self.slot, bool) or not isinstance(self.slot, int) or self.slot < 0:
            raise InventoryRejection("slot must be a non-negative integer")
        try:
            object.__setattr__(self, "block_time", ensure_utc(self.block_time, "block_time"))
        except (AttributeError, TypeError, ValueError):
            raise InventoryRejection("block_time must be a timezone-aware timestamp") from None
        if self.instruction not in _LAUNCH_INSTRUCTIONS:
            raise InventoryRejection(f"not a launch instruction: {self.instruction!r}")
        if self.decimals is not None and self.decimals != PUMP_FUN_TOKEN_DECIMALS:
            raise InventoryRejection(
                f"decimals {self.decimals} differ from verified Pump.fun decimals"
            )

    def canonical(self) -> dict[str, object]:
        return {
            "mint": self.mint,
            "signature": self.signature,
            "slot": self.slot,
            "block_time": self.block_time.isoformat(),
            "instruction": self.instruction,
            "creator": self.creator,
            "transaction_failed": self.transaction_failed,
        }


@dataclass(frozen=True, slots=True)
class InventoryWindow:
    """One source's view of ``[from_slot, to_slot]`` at finalized commitment."""

    source: str
    from_slot: int
    to_slot: int
    cutoff: datetime
    slot_states: Mapping[int, SlotState]
    launches: tuple[InventoryLaunch, ...]
    unresolved_reasons: Mapping[int, str] = field(default_factory=dict)
    source_revision: str = "unversioned"
    data_rights: DataRights = DataRights.OWN_COLLECTION
    rejected: tuple[tuple[str, str], ...] = ()  # (record id, reason)

    def __post_init__(self) -> None:
        if self.from_slot > self.to_slot:
            raise ValueError("from_slot must not exceed to_slot")
        object.__setattr__(self, "cutoff", ensure_utc(self.cutoff, "cutoff"))
        object.__setattr__(self, "data_rights", DataRights(self.data_rights))
        expected = set(range(self.from_slot, self.to_slot + 1))
        states = {int(slot): SlotState(state) for slot, state in self.slot_states.items()}
        if set(states) != expected:
            raise ValueError("slot_states must cover every slot in the window exactly once")
        object.__setattr__(self, "slot_states", states)
        kept: list[InventoryLaunch] = []
        rejected = list(self.rejected)
        for launch in self.launches:
            if not self.from_slot <= launch.slot <= self.to_slot:
                rejected.append((launch.signature, "SLOT_OUTSIDE_WINDOW"))
            elif launch.block_time > self.cutoff:
                rejected.append((launch.signature, "FUTURE_DATED_OBSERVATION"))
            elif states[launch.slot] is not SlotState.SCANNED:
                rejected.append((launch.signature, "LAUNCH_IN_UNSCANNED_SLOT"))
            else:
                kept.append(launch)
        object.__setattr__(self, "launches", tuple(kept))
        object.__setattr__(self, "rejected", tuple(sorted(rejected)))

    @property
    def resolved_slots(self) -> frozenset[int]:
        return frozenset(
            slot for slot, state in self.slot_states.items() if state is not SlotState.UNRESOLVED
        )

    def digest(self) -> str:
        return _digest(
            {
                "source": self.source,
                "window": [self.from_slot, self.to_slot],
                "slots": {str(k): v.value for k, v in sorted(self.slot_states.items())},
                "launches": [
                    launch.canonical()
                    for launch in sorted(
                        self.launches,
                        key=lambda launch: (launch.slot, launch.signature, launch.mint),
                    )
                ],
                "rejected": [list(item) for item in self.rejected],
            }
        )


@dataclass(frozen=True, slots=True)
class CohortEntry:
    mint: str
    slot: int
    signature: str
    instruction: str
    creator: str | None
    sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CoverageLedger:
    from_slot: int
    to_slot: int
    jointly_resolved_slots: int
    unresolved_slots: Mapping[str, tuple[int, ...]]
    matched: tuple[str, ...]
    primary_only: tuple[str, ...]
    independent_only: tuple[str, ...]
    duplicate_mints: tuple[str, ...]
    failed_transactions: tuple[str, ...]
    reason_codes: tuple[str, ...]

    @property
    def primary_recall(self) -> float | None:
        """Share of independently seen launches the canonical path also saw.

        Defined only over jointly resolved slots; UNRESOLVED slots are outside
        the denominator and reported separately, never counted as misses.
        """

        denominator = len(self.matched) + len(self.independent_only)
        return None if denominator == 0 else len(self.matched) / denominator

    def to_payload(self) -> dict[str, object]:
        return {
            "window": [self.from_slot, self.to_slot],
            "jointly_resolved_slots": self.jointly_resolved_slots,
            "unresolved_slots": {k: list(v) for k, v in self.unresolved_slots.items()},
            "matched_count": len(self.matched),
            "primary_only": list(self.primary_only),
            "independent_only": list(self.independent_only),
            "duplicate_mints": list(self.duplicate_mints),
            "failed_transactions": list(self.failed_transactions),
            "primary_recall": self.primary_recall,
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class CohortManifest:
    eligibility_version: str
    eligibility_definition: str
    window: tuple[int, int]
    inputs: tuple[Mapping[str, object], ...]
    entries: tuple[CohortEntry, ...]
    exclusions: tuple[Mapping[str, object], ...]
    ledger: CoverageLedger
    status: str
    version: str = LAUNCH_INVENTORY_VERSION

    def logical_payload(self) -> dict[str, object]:
        return {
            "version": self.version,
            "eligibility_version": self.eligibility_version,
            "eligibility_definition": self.eligibility_definition,
            "window": list(self.window),
            "inputs": [dict(item) for item in self.inputs],
            "entries": [
                {
                    "mint": e.mint,
                    "slot": e.slot,
                    "signature": e.signature,
                    "instruction": e.instruction,
                    "creator": e.creator,
                    "sources": list(e.sources),
                }
                for e in self.entries
            ],
            "exclusions": [dict(item) for item in self.exclusions],
            "ledger": self.ledger.to_payload(),
            "status": self.status,
        }

    @property
    def digest(self) -> str:
        return _digest(self.logical_payload())


def reconcile(primary: InventoryWindow, independent: InventoryWindow) -> CoverageLedger:
    if (primary.from_slot, primary.to_slot) != (independent.from_slot, independent.to_slot):
        raise ValueError("inventories must describe the same slot window")
    joint = primary.resolved_slots & independent.resolved_slots

    def by_mint(window: InventoryWindow) -> dict[str, list[InventoryLaunch]]:
        grouped: dict[str, list[InventoryLaunch]] = {}
        for launch in window.launches:
            if launch.slot in joint and not launch.transaction_failed:
                grouped.setdefault(launch.mint, []).append(launch)
        return grouped

    left, right = by_mint(primary), by_mint(independent)
    duplicates = sorted(
        mint
        for mint in set(left) | set(right)
        if len({item.signature for item in left.get(mint, [])}) > 1
        or len({r.signature for r in right.get(mint, [])}) > 1
    )
    failed = sorted(
        {
            launch.signature
            for window in (primary, independent)
            for launch in window.launches
            if launch.transaction_failed
        }
    )
    unresolved = {
        window.source: tuple(
            sorted(s for s, st in window.slot_states.items() if st is SlotState.UNRESOLVED)
        )
        for window in (primary, independent)
    }
    matched = tuple(sorted(set(left) & set(right)))
    primary_only = tuple(sorted(set(left) - set(right)))
    independent_only = tuple(sorted(set(right) - set(left)))
    reasons: list[str] = []
    if any(unresolved.values()):
        reasons.append("INVENTORY_UNRESOLVED_SLOTS")
    if primary_only or independent_only:
        reasons.append("INVENTORY_SOURCE_DISAGREEMENT")
    if duplicates:
        reasons.append("INVENTORY_DUPLICATE_MINT")
    if not reasons:
        reasons.append("INVENTORY_SOURCES_AGREE")
    return CoverageLedger(
        from_slot=primary.from_slot,
        to_slot=primary.to_slot,
        jointly_resolved_slots=len(joint),
        unresolved_slots=unresolved,
        matched=matched,
        primary_only=primary_only,
        independent_only=independent_only,
        duplicate_mints=tuple(duplicates),
        failed_transactions=tuple(failed),
        reason_codes=tuple(reasons),
    )


def build_cohort(
    primary: InventoryWindow,
    independent: InventoryWindow,
    *,
    extra_inputs: Iterable[InventoryWindow] = (),
) -> CohortManifest:
    """All-observed-launch cohort for the jointly resolved part of the window.

    A launch seen by either source in a jointly resolved slot is eligible
    (union): disagreement is recorded in the ledger, not resolved by dropping
    tokens.  Overlapping sources add source references, never extra rows.
    Inputs with unknown or restricted data rights block approval.
    """

    ledger = reconcile(primary, independent)
    windows = (primary, independent, *tuple(extra_inputs))
    joint = primary.resolved_slots & independent.resolved_slots
    grouped: dict[str, list[InventoryLaunch]] = {}
    for window in windows:
        for launch in window.launches:
            if launch.slot in joint and not launch.transaction_failed:
                grouped.setdefault(launch.mint, []).append(launch)
    entries: list[CohortEntry] = []
    exclusions: list[dict[str, object]] = []
    for mint, launches in sorted(grouped.items()):
        signatures = {launch.signature for launch in launches}
        if len(signatures) > 1:
            exclusions.append(
                {"mint": mint, "reason": "DUPLICATE_MINT_MULTIPLE_CREATES",
                 "signatures": sorted(signatures)}
            )
            continue
        first = min(launches, key=lambda launch: (launch.slot, launch.source))
        entries.append(
            CohortEntry(
                mint=mint,
                slot=first.slot,
                signature=first.signature,
                instruction=first.instruction,
                creator=next((item.creator for item in launches if item.creator), None),
                sources=tuple(sorted({launch.source for launch in launches})),
            )
        )
    for window in windows:
        for record_id, reason in window.rejected:
            exclusions.append({"source": window.source, "record": record_id, "reason": reason})
        for launch in window.launches:
            if launch.transaction_failed:
                exclusions.append(
                    {"source": window.source, "record": launch.signature,
                     "reason": "TRANSACTION_FAILED"}
                )
        for slot in sorted(s for s, st in window.slot_states.items()
                           if st is SlotState.UNRESOLVED):
            exclusions.append(
                {"source": window.source, "slot": slot, "reason": "SLOT_UNRESOLVED",
                 "detail": window.unresolved_reasons.get(slot, "UNKNOWN")}
            )
    rights_ok = all(
        window.data_rights in {DataRights.OWN_COLLECTION, DataRights.PERMITTED}
        for window in windows
    )
    if not rights_ok:
        status = "REJECTED_DATA_RIGHTS"
    elif ledger.jointly_resolved_slots == 0:
        status = "NO_RESOLVED_COVERAGE"
    elif "INVENTORY_SOURCES_AGREE" in ledger.reason_codes:
        status = "APPROVED"
    else:
        status = "APPROVED_WITH_COVERAGE_GAPS"
    return CohortManifest(
        eligibility_version=LAUNCH_ELIGIBILITY_VERSION,
        eligibility_definition=LAUNCH_ELIGIBILITY_DEFINITION,
        window=(primary.from_slot, primary.to_slot),
        inputs=tuple(
            {
                "source": window.source,
                "source_revision": window.source_revision,
                "data_rights": window.data_rights.value,
                "inventory_digest": window.digest(),
                "launch_count": len(window.launches),
                "resolved_slots": len(window.resolved_slots),
            }
            for window in windows
        ),
        entries=tuple(entries) if rights_ok else (),
        exclusions=tuple(
            sorted(exclusions, key=lambda item: json.dumps(item, sort_keys=True, default=str))
        ),
        ledger=ledger,
        status=status,
    )


def window_from_records(
    *,
    source: str,
    from_slot: int,
    to_slot: int,
    cutoff: datetime,
    scanned: Iterable[int],
    skipped: Iterable[int] = (),
    unresolved: Mapping[int, str] | None = None,
    records: Sequence[Mapping[str, object]] = (),
    source_revision: str = "unversioned",
    data_rights: DataRights | str = DataRights.OWN_COLLECTION,
) -> InventoryWindow:
    """Build a window from loose records, rejecting invalid ones with reasons."""

    states: dict[int, SlotState] = {}
    for slot in scanned:
        states[int(slot)] = SlotState.SCANNED
    for slot in skipped:
        states[int(slot)] = SlotState.SKIPPED
    unresolved = dict(unresolved or {})
    for slot in range(from_slot, to_slot + 1):
        if slot not in states:
            states[slot] = SlotState.UNRESOLVED
            unresolved.setdefault(slot, "NOT_REPORTED_BY_SOURCE")
    for slot in unresolved:
        states[int(slot)] = SlotState.UNRESOLVED
    launches: list[InventoryLaunch] = []
    rejected: list[tuple[str, str]] = []
    for record in records:
        record_id = str(record.get("signature") or record.get("mint") or "<unidentified>")
        try:
            launches.append(
                InventoryLaunch(
                    mint=str(record.get("mint")),
                    signature=str(record.get("signature")),
                    slot=record.get("slot"),  # type: ignore[arg-type]
                    block_time=record.get("block_time"),  # type: ignore[arg-type]
                    instruction=str(record.get("instruction")),
                    source=source,
                    creator=_optional_text(record.get("creator")),
                    decimals=record.get("decimals")  # type: ignore[arg-type]
                    if isinstance(record.get("decimals"), int) else None,
                    transaction_failed=bool(record.get("transaction_failed", False)),
                )
            )
        except InventoryRejection as error:
            rejected.append((record_id, f"REJECTED: {error}"[:200]))
    return InventoryWindow(
        source=source,
        from_slot=from_slot,
        to_slot=to_slot,
        cutoff=cutoff,
        slot_states=states,
        launches=tuple(launches),
        unresolved_reasons=unresolved,
        source_revision=source_revision,
        data_rights=DataRights(data_rights),
        rejected=tuple(rejected),
    )


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _digest(material: object) -> str:
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "LAUNCH_ELIGIBILITY_DEFINITION",
    "LAUNCH_ELIGIBILITY_VERSION",
    "LAUNCH_INVENTORY_VERSION",
    "PUMP_FUN_TOKEN_DECIMALS",
    "CohortEntry",
    "CohortManifest",
    "CoverageLedger",
    "DataRights",
    "InventoryLaunch",
    "InventoryRejection",
    "InventoryWindow",
    "SlotState",
    "build_cohort",
    "reconcile",
    "window_from_records",
]
