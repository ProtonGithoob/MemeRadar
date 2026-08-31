"""Provider-free control-plane contracts and safe mutation behavior."""

import asyncio
from datetime import UTC, datetime

import pytest

from memeradar_application.control import (
    DEFAULT_CONTROL_CONFIG,
    ControlAction,
    ControlAuthorizationError,
    ControlConfigError,
    ControlPrincipal,
    ControlRole,
    ControlSafetyError,
    InMemoryControlPlane,
    authorize,
    canonical_config_hash,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


def principal(role: ControlRole) -> ControlPrincipal:
    return ControlPrincipal(subject=role.value.lower(), role=role)


def test_role_matrix_keeps_permissions_separate() -> None:
    assert authorize(principal(ControlRole.VIEWER), ControlAction.READ_STATE) is None
    assert authorize(principal(ControlRole.OPERATOR), ControlAction.PAUSE_ANALYSIS) is None
    assert authorize(
        principal(ControlRole.EXECUTION), ControlAction.ACTIVATE_EXECUTION_KILL_SWITCH
    ) is None
    assert authorize(principal(ControlRole.ADMIN), ControlAction.MUTATE_CONFIG) is None

    with pytest.raises(ControlAuthorizationError):
        authorize(principal(ControlRole.VIEWER), ControlAction.PAUSE_ANALYSIS)
    with pytest.raises(ControlAuthorizationError):
        authorize(principal(ControlRole.OPERATOR), ControlAction.MUTATE_CONFIG)
    with pytest.raises(ControlAuthorizationError):
        authorize(principal(ControlRole.EXECUTION), ControlAction.MUTATE_CONFIG)


def test_control_plane_defaults_to_safe_state_and_initial_config() -> None:
    control = InMemoryControlPlane(clock=lambda: NOW)

    state = asyncio.run(control.get_state())
    config = asyncio.run(control.get_config())

    assert state.analysis_paused is False
    assert state.execution_kill_switch is True
    assert state.version == 0
    assert config.version == "control-config-v0"
    assert dict(config.config) == dict(DEFAULT_CONTROL_CONFIG)
    assert config.decision_affecting is True
    assert control.audit_events == ()


def test_analysis_pause_and_execution_kill_switch_activation_are_audited() -> None:
    control = InMemoryControlPlane(clock=lambda: NOW)
    operator = principal(ControlRole.OPERATOR)

    paused = asyncio.run(
        control.set_analysis_paused(
            operator,
            active=True,
            reason="pause ingestion",
            correlation_id="corr-analysis",
        )
    )
    killed = asyncio.run(
        control.set_execution_kill_switch(
            operator,
            active=True,
            reason="stop execution",
            correlation_id="corr-execution",
        )
    )

    assert paused.analysis_paused is True
    assert paused.version == 1
    assert killed.execution_kill_switch is True
    assert killed.version == 1
    assert len(control.audit_events) == 1
    event = control.audit_events[0]
    assert event.actor == "operator"
    assert event.action == ControlAction.PAUSE_ANALYSIS.value
    assert event.target == "analysis"
    assert event.correlation_id == "corr-analysis"
    assert event.before["analysis_paused"] is False
    assert event.after["analysis_paused"] is True


def test_repeated_safe_kill_activation_is_idempotent_without_duplicate_audit() -> None:
    control = InMemoryControlPlane(clock=lambda: NOW)
    operator = principal(ControlRole.OPERATOR)

    first = asyncio.run(
        control.set_execution_kill_switch(
            operator,
            active=True,
            reason="stop execution",
            correlation_id="corr-1",
        )
    )
    second = asyncio.run(
        control.set_execution_kill_switch(
            operator,
            active=True,
            reason="stop execution again",
            correlation_id="corr-2",
        )
    )

    assert first == second
    assert control.audit_events == ()


def test_execution_kill_switch_cannot_be_cleared_in_protected_modes() -> None:
    control = InMemoryControlPlane(clock=lambda: NOW)

    with pytest.raises(ControlSafetyError, match="protected operating modes"):
        asyncio.run(
            control.set_execution_kill_switch(
                principal(ControlRole.ADMIN),
                active=False,
                reason="attempt clear",
                correlation_id="corr-clear",
            )
        )


def test_config_mutation_is_validated_hashed_versioned_and_audited() -> None:
    control = InMemoryControlPlane(clock=lambda: NOW)
    admin = principal(ControlRole.ADMIN)

    result = asyncio.run(
        control.mutate_config(
            admin,
            changes={
                "decision_entry_ready_threshold": 90,
                "alert_max_messages_per_window": 25,
            },
            reason="calibrate thresholds",
            correlation_id="corr-config",
        )
    )

    assert result.version == "control-config-v1"
    assert result.config["decision_entry_ready_threshold"] == 90.0
    assert result.config["alert_max_messages_per_window"] == 25
    assert result.decision_affecting is True
    assert result.config_hash == canonical_config_hash(result.config)
    assert len(control.audit_events) == 1
    assert control.audit_events[0].action == ControlAction.MUTATE_CONFIG.value
    assert control.audit_events[0].after["config_hash"] == result.config_hash


def test_noop_config_mutation_returns_existing_snapshot_without_audit() -> None:
    control = InMemoryControlPlane(clock=lambda: NOW)
    admin = principal(ControlRole.ADMIN)
    current = asyncio.run(control.get_config())

    result = asyncio.run(
        control.mutate_config(
            admin,
            changes={"alert_max_messages_per_window": 20},
            reason="same setting",
            correlation_id="corr-noop",
        )
    )

    assert result == current
    assert control.audit_events == ()


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({}, "must not be empty"),
        ({"unknown": 1}, "unknown config field"),
        ({"AUTO_EXECUTION": True}, "protected operating mode"),
        ({"alert_max_messages_per_window": True}, "must be an integer"),
        ({"alert_max_messages_per_window": 0}, "must be between"),
        ({"decision_minimum_confidence": 2}, "must be between"),
        ({"decision_watch_threshold": 90, "decision_strong_setup_threshold": 80}, "ordered"),
    ],
)
def test_invalid_config_mutations_fail_without_audit(
    changes: dict[str, object], message: str
) -> None:
    control = InMemoryControlPlane(clock=lambda: NOW)

    with pytest.raises(ControlConfigError, match=message):
        asyncio.run(
            control.mutate_config(
                principal(ControlRole.ADMIN),
                changes=changes,
                reason="bad change",
                correlation_id="corr-invalid",
            )
        )

    assert control.audit_events == ()


def test_audit_reason_and_correlation_are_bounded() -> None:
    control = InMemoryControlPlane(clock=lambda: NOW)

    with pytest.raises(ValueError):
        asyncio.run(
            control.set_analysis_paused(
                principal(ControlRole.OPERATOR),
                active=True,
                reason=" ",
                correlation_id="corr",
            )
        )
    with pytest.raises(ValueError):
        asyncio.run(
            control.set_analysis_paused(
                principal(ControlRole.OPERATOR),
                active=True,
                reason="pause",
                correlation_id=" ",
            )
        )
