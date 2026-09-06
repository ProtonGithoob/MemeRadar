"""Bounded opportunity case-study metadata over the canonical replay dataset.

Future targets deliberately live outside ``ReplayDataset``.  Callers pass only
``bundle.dataset`` to ``ReplayHarness`` when reconstructing decision-time
features; the target metadata is for later research comparison.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import cast
from uuid import UUID

from memeradar_domain import Chain, normalize_chain

from .replay_harness import ReplayDataset, ResearchReplayManifest

OPPORTUNITY_CASE_STUDY_SCHEMA_VERSION = 1
OPPORTUNITY_CASE_STUDY_FIXTURE_VERSION = "opportunity-case-studies-v1"
TARGET_MULTIPLE_KEYS: tuple[str, ...] = ("2x", "5x", "10x", "20x", "50x", "100x")
REQUIRED_CASE_STUDY_COHORTS: tuple[str, ...] = (
    "EXTREME_WINNER",
    "ORDINARY_WINNER",
    "HIGH_VIRALITY_NON_WINNER",
    "COPYCAT_FAILURE",
    "RUG_SEVERE_FAILURE",
    "FUNDAMENTAL_NO_REPRICING",
    "WEAK_FUNDAMENTAL_REPRICING",
)
REQUIRED_EVIDENCE_FIELDS: tuple[str, ...] = (
    "deployment",
    "first_liquidity",
    "first_seen",
    "catalyst",
    "pre_token_attention",
    "tracked_wallets",
    "holder_growth",
    "liquidity",
    "volume",
    "copycats",
    "protocol_usage",
    "kol_timeline",
    "executable_quotes",
)
_EVIDENCE_STATES = frozenset({"OBSERVED", "UNKNOWN"})
_FUTURE_TARGET_KEYS = frozenset(
    {"future_outcome_targets", "future_outcome_labels", "future_labels"}
)


@dataclass(frozen=True, slots=True)
class OpportunityCaseStudy:
    """One decision-time cohort member and its research-only future targets."""

    case_id: str
    token_id: UUID
    checkpoint_id: UUID
    cohort: str
    chain: Chain
    archetype: str
    evidence_class: str
    historical_status: str
    evidence_scope: Mapping[str, str]
    unknown_fields: tuple[str, ...]
    future_outcome_targets: Mapping[str, Mapping[str, bool | int | None]]

    def to_json_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "token_id": str(self.token_id),
            "checkpoint_id": str(self.checkpoint_id),
            "cohort": self.cohort,
            "chain": self.chain.value,
            "archetype": self.archetype,
            "evidence_class": self.evidence_class,
            "historical_status": self.historical_status,
            "evidence_scope": dict(self.evidence_scope),
            "unknown_fields": list(self.unknown_fields),
            "future_outcome_targets": {
                key: dict(value) for key, value in self.future_outcome_targets.items()
            },
        }


@dataclass(frozen=True, slots=True)
class OpportunityCaseStudyBundle:
    """Validated metadata plus the existing canonical replay inputs."""

    fixture_version: str
    evidence_class: str
    dataset: ReplayDataset
    manifest: ResearchReplayManifest
    cases: tuple[OpportunityCaseStudy, ...]

    def case(self, case_id: str) -> OpportunityCaseStudy:
        for value in self.cases:
            if value.case_id == case_id:
                return value
        raise KeyError(case_id)


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise TypeError(f"{field_name} keys must be strings")
    return cast(Mapping[str, object], value)


def _text(value: object, field_name: str, *, max_length: int = 128) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise TypeError(f"{field_name} must be a non-empty string")
    return value


def _uuid(value: object, field_name: str) -> UUID:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a UUID string")
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a UUID string") from exc


def _reject_future_targets(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in _FUTURE_TARGET_KEYS:
                raise ValueError("future outcome targets must remain separate from replay evidence")
            _reject_future_targets(child)
    elif isinstance(value, list):
        for child in value:
            _reject_future_targets(child)


def _target_values(value: object, field_name: str) -> Mapping[str, bool | int | None]:
    raw = _mapping(value, field_name)
    if set(raw) != {"hit", "first_crossed_seconds"}:
        raise ValueError(f"{field_name} must contain only hit and first_crossed_seconds")
    hit = raw["hit"]
    seconds = raw["first_crossed_seconds"]
    if hit is not None and not isinstance(hit, bool):
        raise TypeError(f"{field_name}.hit must be boolean or null")
    if seconds is not None and (
        not isinstance(seconds, int) or isinstance(seconds, bool) or seconds < 0
    ):
        raise TypeError(
            f"{field_name}.first_crossed_seconds must be a non-negative integer or null"
        )
    if (hit is True) != (seconds is not None):
        raise ValueError(f"{field_name} must use a crossing time only when hit is true")
    return MappingProxyType({"hit": hit, "first_crossed_seconds": seconds})


def _case(value: object, dataset: ReplayDataset) -> OpportunityCaseStudy:
    raw = _mapping(value, "case study")
    evidence_scope_raw = _mapping(raw.get("evidence_scope"), "case study evidence_scope")
    if set(evidence_scope_raw) != set(REQUIRED_EVIDENCE_FIELDS):
        raise ValueError("case study evidence_scope must cover the required evidence fields")
    evidence_scope = {
        field: _text(evidence_scope_raw[field], f"evidence_scope.{field}", max_length=16).upper()
        for field in REQUIRED_EVIDENCE_FIELDS
    }
    if any(state not in _EVIDENCE_STATES for state in evidence_scope.values()):
        raise ValueError("case study evidence_scope states must be OBSERVED or UNKNOWN")

    unknown_raw = raw.get("unknown_fields")
    if not isinstance(unknown_raw, list) or any(not isinstance(item, str) for item in unknown_raw):
        raise TypeError("case study unknown_fields must be a string list")
    unknown_fields = tuple(unknown_raw)
    if len(set(unknown_fields)) != len(unknown_fields) or any(
        field not in REQUIRED_EVIDENCE_FIELDS for field in unknown_fields
    ):
        raise ValueError("case study unknown_fields contains an invalid or duplicate field")
    if set(unknown_fields) != {
        field for field, state in evidence_scope.items() if state == "UNKNOWN"
    }:
        raise ValueError("case study unknown_fields must match UNKNOWN evidence fields")

    token_id = _uuid(raw.get("token_id"), "case study token_id")
    checkpoint_id = _uuid(raw.get("checkpoint_id"), "case study checkpoint_id")
    token = dataset.token(token_id)
    raw_chain = normalize_chain(_text(raw.get("chain"), "case study chain", max_length=32))
    if token.chain is not raw_chain:
        raise ValueError("case study chain does not match token identity")
    if checkpoint_id not in {value.id for value in dataset.checkpoints}:
        raise ValueError("case study checkpoint_id does not match dataset")

    targets_raw = _mapping(raw.get("future_outcome_targets"), "future_outcome_targets")
    if set(targets_raw) != set(TARGET_MULTIPLE_KEYS):
        raise ValueError("future_outcome_targets must cover 2x, 5x, 10x, 20x, 50x and 100x")
    targets = {
        key: _target_values(targets_raw[key], f"future_outcome_targets.{key}")
        for key in TARGET_MULTIPLE_KEYS
    }
    return OpportunityCaseStudy(
        case_id=_text(raw.get("case_id"), "case study case_id"),
        token_id=token_id,
        checkpoint_id=checkpoint_id,
        cohort=_text(raw.get("cohort"), "case study cohort", max_length=64),
        chain=raw_chain,
        archetype=_text(raw.get("archetype"), "case study archetype", max_length=64).upper(),
        evidence_class=_text(raw.get("evidence_class"), "case study evidence_class", max_length=64),
        historical_status=_text(
            raw.get("historical_status"), "case study historical_status", max_length=32
        ).upper(),
        evidence_scope=MappingProxyType(evidence_scope),
        unknown_fields=unknown_fields,
        future_outcome_targets=MappingProxyType(targets),
    )


def load_opportunity_case_studies(path: Path) -> OpportunityCaseStudyBundle:
    """Load and validate bounded case-study metadata over canonical replay data."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    root = _mapping(raw, "case-study fixture")
    if root.get("schema_version") != OPPORTUNITY_CASE_STUDY_SCHEMA_VERSION:
        raise ValueError("unsupported opportunity case-study schema version")
    fixture_version = _text(root.get("fixture_version"), "fixture_version")
    if fixture_version != OPPORTUNITY_CASE_STUDY_FIXTURE_VERSION:
        raise ValueError("unsupported opportunity case-study fixture version")
    dataset_value = _mapping(root.get("dataset"), "dataset")
    _reject_future_targets(dataset_value)
    dataset = ReplayDataset.from_json_dict(dataset_value)
    manifest = ResearchReplayManifest.from_json_dict(_mapping(root.get("manifest"), "manifest"))
    if (
        manifest.dataset_id != dataset.dataset_id
        or manifest.dataset_version != dataset.dataset_version
    ):
        raise ValueError("case-study manifest identity does not match dataset")
    if any(checkpoint.as_of > manifest.as_of for checkpoint in dataset.checkpoints):
        raise ValueError("case-study checkpoint is outside manifest event-time boundary")
    if manifest.dataset_digest is None:
        manifest = replace(manifest, dataset_digest=dataset.digest)
    elif manifest.dataset_digest != dataset.digest:
        raise ValueError("manifest dataset_digest does not match dataset")

    raw_cases = root.get("case_studies")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise TypeError("case_studies must be a non-empty list")
    cases = tuple(_case(value, dataset) for value in raw_cases)
    if len({value.case_id for value in cases}) != len(cases):
        raise ValueError("case studies contain duplicate case IDs")
    if len({value.token_id for value in cases}) != len(cases):
        raise ValueError("case studies contain duplicate token IDs")
    if {value.cohort for value in cases} != set(REQUIRED_CASE_STUDY_COHORTS):
        raise ValueError("case studies must contain exactly the required cohorts")
    if {value.chain.value for value in cases} != {"solana", "bnb", "robinhood"}:
        raise ValueError("case studies must cover Solana, BNB and Robinhood")
    if {value.checkpoint_id for value in cases} != {value.id for value in dataset.checkpoints}:
        raise ValueError("case studies must map one-to-one to replay checkpoints")
    if any(value.historical_status != "UNKNOWN" for value in cases):
        raise ValueError("unverified historical case studies must use UNKNOWN status")
    evidence_class = _text(root.get("evidence_class"), "evidence_class", max_length=64)
    if any(value.evidence_class != evidence_class for value in cases):
        raise ValueError("case study evidence_class must match fixture evidence_class")
    return OpportunityCaseStudyBundle(
        fixture_version=fixture_version,
        evidence_class=evidence_class,
        dataset=dataset,
        manifest=manifest,
        cases=cases,
    )


__all__ = [
    "OPPORTUNITY_CASE_STUDY_FIXTURE_VERSION",
    "OPPORTUNITY_CASE_STUDY_SCHEMA_VERSION",
    "OpportunityCaseStudy",
    "OpportunityCaseStudyBundle",
    "REQUIRED_CASE_STUDY_COHORTS",
    "REQUIRED_EVIDENCE_FIELDS",
    "TARGET_MULTIPLE_KEYS",
    "load_opportunity_case_studies",
]
