"""Deterministic Phase 11.3 security-review contracts."""

from __future__ import annotations

import shutil
from pathlib import Path

import scripts.security_review as security_review
from scripts.security_review import (
    CheckStatus,
    check_container_contracts,
    check_dependency_locks,
    check_deployment_security,
    check_secret_boundaries,
    run_review,
)

ROOT = Path(__file__).resolve().parents[2]


def test_keyless_review_reports_each_local_boundary_and_does_not_claim_external_scans() -> None:
    report = run_review(ROOT)

    assert report.schema_version == "security-review-v1"
    assert report.status is CheckStatus.PASS
    assert report.external_scans == {
        "pip_audit": CheckStatus.NOT_RUN,
        "npm_audit": CheckStatus.NOT_RUN,
        "container_scan": CheckStatus.NOT_RUN,
    }
    assert {check.name for check in report.checks} == {
        "dependency_lock_metadata",
        "container_runtime_contracts",
        "secret_boundary_scan",
        "rbac_auth_session_contracts",
        "llm_prompt_data_contracts",
        "deployment_security_contracts",
        "protected_operating_modes",
    }
    assert report.to_dict()["modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }


def test_dependency_lock_review_rejects_unpinned_python_requirement(tmp_path: Path) -> None:
    (tmp_path / "apps" / "web").mkdir(parents=True)
    for relative in (
        "pyproject.toml",
        "apps/web/package.json",
        "apps/web/package-lock.json",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    requirements = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    (tmp_path / "requirements.lock").write_text(
        requirements + "\nrequests>=2.0\n",
        encoding="utf-8",
    )

    check = check_dependency_locks(tmp_path)

    assert check.status is CheckStatus.FAIL
    assert "exact" in check.detail.lower()


def test_container_review_rejects_latest_or_root_only_images(tmp_path: Path) -> None:
    docker_dir = tmp_path / "infra" / "docker"
    docker_dir.mkdir(parents=True)
    (docker_dir / "api.Dockerfile").write_text(
        'FROM python:latest\nCMD ["python", "-m", "example"]\n',
        encoding="utf-8",
    )
    (docker_dir / "worker.Dockerfile").write_text(
        'FROM python:3.12-slim\nCMD ["python", "-m", "example"]\n',
        encoding="utf-8",
    )
    (docker_dir / "web.Dockerfile").write_text(
        'FROM node:22-alpine\nUSER root\nCMD ["npm", "run", "dev"]\n',
        encoding="utf-8",
    )

    check = check_container_contracts(tmp_path)

    assert check.status is CheckStatus.FAIL
    assert "non-root" in check.detail.lower() or "unversioned" in check.detail.lower()


def test_external_scans_without_installed_tools_are_blocked_not_passed(monkeypatch) -> None:
    monkeypatch.setattr(security_review.shutil, "which", lambda _: None)

    report = run_review(ROOT, external=True)

    assert report.status is CheckStatus.BLOCKED_EXTERNAL
    assert all(status is CheckStatus.BLOCKED_EXTERNAL for status in report.external_scans.values())
    assert report.external_acceptance is CheckStatus.BLOCKED_EXTERNAL


def test_protected_mode_override_fails_closed() -> None:
    report = run_review(ROOT, environ={"AUTO_EXECUTION": "true"})

    assert report.status is CheckStatus.FAIL
    assert report.checks[-1].name == "protected_operating_modes"
    assert report.checks[-1].status is CheckStatus.FAIL


def test_secret_boundary_review_includes_history_and_artifacts(tmp_path: Path) -> None:
    check = check_secret_boundaries(tmp_path)

    assert check.status is CheckStatus.PASS
    assert "history" in check.detail.lower()
    assert "artifact" in check.detail.lower()


def test_deployment_review_rejects_publicly_bound_compose_port(tmp_path: Path) -> None:
    compose_dir = tmp_path / "infra" / "compose"
    compose_dir.mkdir(parents=True)
    (compose_dir / "docker-compose.yml").write_text(
        "services:\n  api:\n    ports:\n      - '0.0.0.0:18000:8000'\n",
        encoding="utf-8",
    )
    (tmp_path / "apps" / "api" / "src" / "memeradar_api").mkdir(parents=True)
    (tmp_path / "apps" / "api" / "src" / "memeradar_api" / "main.py").write_text(
        "from fastapi.middleware.cors import CORSMiddleware\n"
        "allow_origins=['*']\n",
        encoding="utf-8",
    )
    for relative in (
        "apps/api/src/memeradar_api/control.py",
        "packages/application/src/memeradar_application/config.py",
        "packages/telemetry/src/memeradar_telemetry/logging.py",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)

    check = check_deployment_security(tmp_path)

    assert check.status is CheckStatus.FAIL
    assert "port" in check.detail.lower() or "cors" in check.detail.lower()
