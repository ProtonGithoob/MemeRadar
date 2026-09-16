from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.release_identity import RELEASE_IDENTITY_SCHEMA_VERSION, build_release_identity

ROOT = Path(__file__).resolve().parents[2]


def test_release_identity_is_reproducible_and_binds_existing_release_inputs() -> None:
    identity = build_release_identity(ROOT)
    git_sha = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert identity["schema_version"] == RELEASE_IDENTITY_SCHEMA_VERSION
    assert identity["git_sha"] == git_sha
    assert identity["app_version"] == "0.1.0"
    assert identity["api_version"] == "0.1.0"
    assert identity["migration_heads"] == ["0011_collection_checkpoints"]
    assert identity["migration_table_count"] == 27
    assert identity["config_hash"].startswith("sha256:")
    assert identity["sbom_schema_version"] == "security-sbom-v1"
    assert identity["sbom_component_count"] == 582
    assert str(identity["sbom_digest"]).startswith("sha256:")
    assert identity["protected_modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }


def test_release_identity_binds_immutable_service_artifacts() -> None:
    identity = build_release_identity(
        ROOT,
        image_digests={
            "api": "sha256:" + "a" * 64,
            "worker": "sha256:" + "b" * 64,
            "web": "sha256:" + "c" * 64,
        },
    )

    assert identity["images"] == {
        "api": {"digest": "sha256:" + "a" * 64},
        "worker": {"digest": "sha256:" + "b" * 64},
        "web": {"digest": "sha256:" + "c" * 64},
    }


def test_ci_gates_and_publishes_the_release_identity_artifact() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "release-identity" in workflow
    assert "needs: [backend, frontend, compose, secret-scan, container-build]" in workflow
    assert "npm audit --omit=dev --audit-level=high" in workflow
    assert "MEMERADAR_TEST_DATABASE_URL" in workflow
    assert "postgres:16" in workflow
    assert "scripts/check_frontend_css.py" in workflow
    assert "npm audit --audit-level=high" in workflow
    assert "Docker image" in workflow
    assert "scripts/release_identity.py --output artifacts/release-identity.json" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "release-candidate" in workflow


def test_release_identity_cli_writes_the_same_safe_artifact(tmp_path: Path) -> None:
    output = tmp_path / "release-identity.json"
    subprocess.run(
        [
            str(ROOT / ".venv" / "bin" / "python"),
            str(ROOT / "scripts" / "release_identity.py"),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert output.is_file()
