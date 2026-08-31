"""Durable exit-evaluation timeline over the existing domain-event log."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from memeradar_application.exit_engine import (
    ExitAction,
    ExitEvaluation,
    ExitEvaluationStore,
    ExitRiskScore,
    ExitTimelineConflict,
)
from memeradar_domain import AlertSeverity, ExitSignal, QualityState
from memeradar_domain.common import to_decimal

from .models import DomainEventRow
from .serialization import json_safe, reason_codes_from_json, reason_codes_to_json


def _payload_for(evaluation: ExitEvaluation) -> dict[str, Any]:
    signal = evaluation.signal
    payload: dict[str, object] = {
        "position_id": str(evaluation.position_id),
        "occurred_at": evaluation.occurred_at.isoformat(),
        "evaluated_at": evaluation.evaluated_at.isoformat(),
        "action": evaluation.action.value,
        "exit_fraction": str(evaluation.exit_fraction),
        "triggered_rules": list(evaluation.triggered_rules),
        "before_evidence_refs": list(evaluation.before_evidence_refs),
        "after_evidence_refs": list(evaluation.after_evidence_refs),
        "policy_version": evaluation.policy_version,
        "config_hash": evaluation.config_hash,
        "risk_score": {
            "score": str(evaluation.risk_score.score),
            "confidence": str(evaluation.risk_score.confidence),
            "quality_state": evaluation.risk_score.quality_state.value,
            "components": {
                key: str(value) for key, value in evaluation.risk_score.components.items()
            },
            "reason_codes": reason_codes_to_json(evaluation.risk_score.reason_codes),
            "evidence_refs": list(evaluation.risk_score.evidence_refs),
            "policy_version": evaluation.risk_score.policy_version,
            "config_hash": evaluation.risk_score.config_hash,
            "action": evaluation.risk_score.action.value,
            "exit_fraction": str(evaluation.risk_score.exit_fraction),
        },
        "signal": None,
    }
    if signal is not None:
        payload["signal"] = {
            "id": str(signal.id),
            "position_id": str(signal.position_id),
            "occurred_at": signal.occurred_at.isoformat(),
            "severity": signal.severity.value,
            "action": signal.action,
            "reason_codes": reason_codes_to_json(signal.reason_codes),
            "evidence_refs": list(signal.evidence_refs),
            "version": signal.version,
            "score_before": None if signal.score_before is None else str(signal.score_before),
            "score_after": None if signal.score_after is None else str(signal.score_after),
        }
    return cast(dict[str, Any], json_safe(payload))


def _required_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"exit event payload field {field_name} must be an object")
    return value


def _required_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"exit event payload field {field_name} must be a string")
    return value


def _required_list(value: object, field_name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"exit event payload field {field_name} must be a list")
    return value


def _required_decimal(value: object, field_name: str) -> Decimal:
    return to_decimal(_required_string(value, field_name), field_name)


def _parse_datetime(value: object, field_name: str) -> datetime:
    return datetime.fromisoformat(_required_string(value, field_name))


def evaluation_from_row(row: DomainEventRow) -> ExitEvaluation:
    """Rehydrate one persisted evaluation through the canonical exit contract."""

    if not isinstance(row, DomainEventRow):
        raise TypeError("row must be a DomainEventRow")
    payload = _required_mapping(row.payload, "payload")
    position_id = UUID(_required_string(payload.get("position_id"), "position_id"))
    risk_payload = _required_mapping(payload.get("risk_score"), "risk_score")
    components_payload = _required_mapping(risk_payload.get("components"), "components")
    components = {
        str(key): _required_decimal(value, f"components.{key}")
        for key, value in components_payload.items()
    }
    risk_reasons = reason_codes_from_json(risk_payload.get("reason_codes"))
    risk_score = ExitRiskScore(
        score=_required_decimal(risk_payload.get("score"), "risk_score.score"),
        confidence=_required_decimal(risk_payload.get("confidence"), "risk_score.confidence"),
        quality_state=QualityState(
            _required_string(risk_payload.get("quality_state"), "risk_score.quality_state")
        ),
        components=components,
        reason_codes=risk_reasons,
        evidence_refs=tuple(
            _required_string(value, "risk_score.evidence_refs")
            for value in _required_list(
                risk_payload.get("evidence_refs"), "risk_score.evidence_refs"
            )
        ),
        policy_version=_required_string(
            risk_payload.get("policy_version"), "risk_score.policy_version"
        ),
        config_hash=_required_string(risk_payload.get("config_hash"), "risk_score.config_hash"),
        action=ExitAction(_required_string(risk_payload.get("action"), "risk_score.action")),
        exit_fraction=_required_decimal(
            risk_payload.get("exit_fraction"), "risk_score.exit_fraction"
        ),
    )
    signal_payload = payload.get("signal")
    signal: ExitSignal | None = None
    if signal_payload is not None:
        signal_values = _required_mapping(signal_payload, "signal")
        score_before = signal_values.get("score_before")
        score_after = signal_values.get("score_after")
        signal = ExitSignal(
            id=UUID(_required_string(signal_values.get("id"), "signal.id")),
            position_id=UUID(
                _required_string(signal_values.get("position_id"), "signal.position_id")
            ),
            occurred_at=_parse_datetime(signal_values.get("occurred_at"), "signal.occurred_at"),
            severity=AlertSeverity(
                _required_string(signal_values.get("severity"), "signal.severity")
            ),
            action=_required_string(signal_values.get("action"), "signal.action"),
            reason_codes=reason_codes_from_json(signal_values.get("reason_codes")),
            evidence_refs=tuple(
                _required_string(value, "signal.evidence_refs")
                for value in _required_list(
                    signal_values.get("evidence_refs"), "signal.evidence_refs"
                )
            ),
            version=_required_string(signal_values.get("version"), "signal.version"),
            score_before=(
                None
                if score_before is None
                else _required_decimal(score_before, "signal.score_before")
            ),
            score_after=(
                None
                if score_after is None
                else _required_decimal(score_after, "signal.score_after")
            ),
        )
    return ExitEvaluation(
        id=row.id,
        position_id=position_id,
        occurred_at=_parse_datetime(payload.get("occurred_at"), "occurred_at"),
        evaluated_at=_parse_datetime(payload.get("evaluated_at"), "evaluated_at"),
        risk_score=risk_score,
        action=ExitAction(_required_string(payload.get("action"), "action")),
        exit_fraction=_required_decimal(payload.get("exit_fraction"), "exit_fraction"),
        triggered_rules=tuple(
            _required_string(value, "triggered_rules")
            for value in _required_list(payload.get("triggered_rules"), "triggered_rules")
        ),
        before_evidence_refs=tuple(
            _required_string(value, "before_evidence_refs")
            for value in _required_list(
                payload.get("before_evidence_refs"), "before_evidence_refs"
            )
        ),
        after_evidence_refs=tuple(
            _required_string(value, "after_evidence_refs")
            for value in _required_list(
                payload.get("after_evidence_refs"), "after_evidence_refs"
            )
        ),
        policy_version=_required_string(payload.get("policy_version"), "policy_version"),
        config_hash=_required_string(payload.get("config_hash"), "config_hash"),
        signal=signal,
    )


class SqlAlchemyExitEvaluationStore:
    """Persist exit evaluations as immutable ``ExitEvaluation`` domain events."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._session_factory = session_factory or async_sessionmaker(
            engine,
            expire_on_commit=False,
            autoflush=True,
        )

    async def append(self, evaluation: ExitEvaluation) -> None:
        if not isinstance(evaluation, ExitEvaluation):
            raise TypeError("evaluation must be an ExitEvaluation")
        payload = _payload_for(evaluation)
        idempotency_key = f"exit-evaluation:{evaluation.id}"
        reason_codes = reason_codes_to_json(evaluation.risk_score.reason_codes)
        async with self._session_factory() as session, session.begin():
            existing = await session.get(DomainEventRow, evaluation.id)
            if existing is not None:
                if (
                    existing.kind != "ExitEvaluation"
                    or existing.idempotency_key != idempotency_key
                    or existing.payload != payload
                ):
                    raise ExitTimelineConflict("exit evaluation identity has conflicting input")
                return
            existing = await session.scalar(
                select(DomainEventRow).where(DomainEventRow.idempotency_key == idempotency_key)
            )
            if existing is not None:
                if existing.payload != payload:
                    raise ExitTimelineConflict(
                        "exit evaluation idempotency key has conflicting input"
                    )
                return
            session.add(
                DomainEventRow(
                    id=evaluation.id,
                    kind="ExitEvaluation",
                    schema_version=1,
                    aggregate_type="Position",
                    aggregate_id=str(evaluation.position_id),
                    occurred_at=evaluation.occurred_at,
                    observed_at=evaluation.evaluated_at,
                    ingested_at=evaluation.evaluated_at,
                    correlation_id=f"exit:{evaluation.id}",
                    producer="exit-engine",
                    payload=payload,
                    idempotency_key=idempotency_key,
                    reason_codes=reason_codes,
                )
            )

    async def list(self, position_id: UUID) -> Sequence[ExitEvaluation]:
        if not isinstance(position_id, UUID):
            raise TypeError("position_id must be a UUID")
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(DomainEventRow)
                    .where(
                        DomainEventRow.kind == "ExitEvaluation",
                        DomainEventRow.aggregate_type == "Position",
                        DomainEventRow.aggregate_id == str(position_id),
                    )
                    .order_by(DomainEventRow.occurred_at, DomainEventRow.id)
                )
            ).all()
            return tuple(_evaluation_from_row(row) for row in rows)


# Kept as a compatibility alias for the existing persistence contract tests and
# callers that used the original private helper before the read projection was
# added.  New adapters should use the public canonical rehydrator above.
_evaluation_from_row = evaluation_from_row


def assert_exit_evaluation_store_contract(store: object) -> ExitEvaluationStore:
    """Type-checking helper for callers composing the durable timeline port."""

    if not isinstance(store, SqlAlchemyExitEvaluationStore):
        raise TypeError("store must be a SqlAlchemyExitEvaluationStore")
    return store


__all__ = [
    "SqlAlchemyExitEvaluationStore",
    "assert_exit_evaluation_store_contract",
    "evaluation_from_row",
]
