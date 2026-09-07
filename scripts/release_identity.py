#!/usr/bin/env python3
"""Emit a deterministic, keyless identity for a MemeRadar release candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.sbom import build_sbom, serialize_sbom  # noqa: E402

RELEASE_IDENTITY_SCHEMA_VERSION = "release-identity-v1"
_PROTECTED_MODES = {
    "analysis_only": True,
    "paper_trading": True,
    "manual_execution": False,
    "auto_execution": False,
}


def _git_sha(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("git revision is not a full SHA-1")
    return value


def _migration_report(root: Path) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_migrations.py")],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise ValueError("migration check produced no report")
    report = json.loads(lines[-1])
    if not isinstance(report, dict):
        raise ValueError("migration report is not an object")
    return cast(dict[str, object], report)


def _config_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for relative in (".env.example", "packages/application/src/memeradar_application/config.py"):
        path = root / relative
        if not path.is_file():
            raise ValueError(f"release config input is missing: {relative}")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _versions(root: Path) -> tuple[str, str]:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject.get("project")
    if not isinstance(project, dict) or not isinstance(project.get("version"), str):
        raise ValueError("project version is missing")
    api_source = (root / "apps/api/src/memeradar_api/__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', api_source, re.MULTILINE)
    if match is None:
        raise ValueError("API version is missing")
    return project["version"], match.group(1)


def build_release_identity(root: Path) -> dict[str, object]:
    """Build a stable release record without reading credentials or provider data."""

    normalized_root = root.resolve()
    app_version, api_version = _versions(normalized_root)
    migration = _migration_report(normalized_root)
    sbom = build_sbom(normalized_root)
    sbom_bytes = serialize_sbom(sbom).encode("utf-8")
    components = sbom.get("components")
    if not isinstance(components, list):
        raise ValueError("SBOM components are missing")
    heads = migration.get("heads")
    table_count = migration.get("table_count")
    if not isinstance(heads, list) or not all(isinstance(head, str) for head in heads):
        raise ValueError("migration heads are invalid")
    if not isinstance(table_count, int) or isinstance(table_count, bool):
        raise ValueError("migration table count is invalid")
    return {
        "schema_version": RELEASE_IDENTITY_SCHEMA_VERSION,
        "git_sha": _git_sha(normalized_root),
        "app_version": app_version,
        "api_version": api_version,
        "migration_heads": heads,
        "migration_table_count": table_count,
        "config_hash": _config_hash(normalized_root),
        "sbom_schema_version": sbom.get("schema_version"),
        "sbom_component_count": len(components),
        "sbom_digest": f"sha256:{hashlib.sha256(sbom_bytes).hexdigest()}",
        "protected_modes": dict(_PROTECTED_MODES),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        identity = build_release_identity(args.root)
        encoded = json.dumps(identity, sort_keys=True, indent=2) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
        sys.stdout.write(encoded)
    except (
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as exc:
        del exc
        print("release identity failed: INVALID_INPUT_OR_CONTRACT", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
