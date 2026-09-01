"""Phase 11.3 security review and boundary contracts."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from scripts.security_review import CheckStatus, run_review

from memeradar_api.auth import RoleTokenAuthenticator
from memeradar_application.config import Settings
from memeradar_application.control import ControlAction, ControlRole

ROOT = Path(__file__).resolve().parents[2]


def test_security_review_keyless_gate_is_pass_and_external_acceptance_is_explicit() -> None:
    report = run_review(ROOT)
    serialized = report.to_dict()

    assert serialized["schema_version"] == "security-review-v1"
    assert serialized["status"] == "PASS"
    assert serialized["external_acceptance"] == "BLOCKED_EXTERNAL"
    assert serialized["external_scans"]["pip_audit"] == "NOT_RUN"
    assert serialized["external_scans"]["npm_audit"] == "NOT_RUN"
    assert serialized["external_scans"]["container_scan"] == "NOT_RUN"
    assert all(check.status is CheckStatus.PASS for check in report.checks)


def test_role_tokens_are_bearer_only_constant_time_and_permission_scoped() -> None:
    settings = Settings.from_env(
        {
            "VIEWER_API_TOKEN": "viewer-review-secret",
            "ADMIN_API_TOKEN": "admin-review-secret",
        }
    )
    authenticator = RoleTokenAuthenticator(settings)

    principal = authenticator.authenticate("Bearer viewer-review-secret")

    assert principal.role is ControlRole.VIEWER
    assert "review-secret" not in repr(principal)
    with pytest.raises(HTTPException) as unauthorized:
        authenticator.authenticate("Bearer wrong-review-secret")
    assert unauthorized.value.status_code == 401
    with pytest.raises(HTTPException) as forbidden:
        authenticator.require("Bearer viewer-review-secret", ControlAction.MUTATE_CONFIG)
    assert forbidden.value.status_code == 403


def test_security_review_source_contracts_cover_prompt_injection_and_execution_boundaries() -> None:
    auth_source = (ROOT / "apps/api/src/memeradar_api/auth.py").read_text(encoding="utf-8")
    control_source = (ROOT / "packages/application/src/memeradar_application/control.py").read_text(
        encoding="utf-8"
    )
    narrative_source = (
        ROOT / "packages/application/src/memeradar_application/narrative.py"
    ).read_text(
        encoding="utf-8"
    )
    narrative_contracts = (
        ROOT / "packages/application/src/memeradar_application/provider_contracts.py"
    ).read_text(encoding="utf-8")
    narrative_provider = (
        ROOT / "packages/providers/src/memeradar_providers/narrative.py"
    ).read_text(encoding="utf-8")

    assert "secrets.compare_digest" in auth_source
    assert "authorize(principal, action)" in auth_source
    assert "_PROTECTED_CONFIG_FIELDS" in control_source
    assert "execution_kill_switch" in control_source
    assert "NarrativeAnalyzer" in narrative_source
    assert "execution_eligible" in narrative_contracts
    assert "advisory" in narrative_contracts
    assert "<UNTRUSTED_DATA>" in narrative_provider
    assert "_PROMPT_INSTRUCTION_PATTERN" in narrative_provider
    assert "_PROMPT_TOOL_PATTERN" in narrative_provider
    assert "sign_transaction" not in narrative_source.lower()
    assert "submit_transaction" not in narrative_source.lower()
