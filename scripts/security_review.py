#!/usr/bin/env python3
"""Key-safe Phase 11.3 security review for the analysis-only repository.

The deterministic checks inspect lockfiles, image construction, tracked source
boundaries and protected modes. Optional vulnerability scanners are invoked
only with fixed argument lists; their raw output is never returned or logged.
Missing tools, registries or vulnerability databases remain BLOCKED_EXTERNAL.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
for source_root in (
    ROOT / "packages" / "application" / "src",
    ROOT / "packages" / "domain" / "src",
):
    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)

from memeradar_application.config import Settings  # noqa: E402
from scripts.secret_scan import scan_files, tracked_files  # noqa: E402


class CheckStatus(str, Enum):
    """Bounded result states for local and optional external checks."""

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
    NOT_RUN = "NOT_RUN"


@dataclass(frozen=True, slots=True)
class SecurityCheck:
    """Safe check result; detail never contains command output or secrets."""

    name: str
    status: CheckStatus
    detail: str

    def __post_init__(self) -> None:
        if not self.name or len(self.name) > 96 or not re.fullmatch(r"[a-z0-9_.-]+", self.name):
            raise ValueError("security check name must be a bounded identifier")
        if len(self.detail) > 256:
            raise ValueError("security check detail is too long")
        object.__setattr__(self, "status", CheckStatus(self.status))

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status.value, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class SecurityReviewReport:
    """Versioned security review output with explicit external scan state."""

    checks: tuple[SecurityCheck, ...]
    external_scans: Mapping[str, CheckStatus]
    modes: Mapping[str, bool]
    schema_version: str = "security-review-v1"

    def __post_init__(self) -> None:
        if self.schema_version != "security-review-v1":
            raise ValueError("unsupported security review schema version")
        object.__setattr__(self, "checks", tuple(self.checks))
        normalized_scans = {
            str(name): CheckStatus(status) for name, status in self.external_scans.items()
        }
        object.__setattr__(self, "external_scans", normalized_scans)
        normalized_modes = dict(self.modes)
        if normalized_modes != _SAFE_MODES:
            raise ValueError("security review modes must remain protected")
        object.__setattr__(self, "modes", normalized_modes)

    @property
    def status(self) -> CheckStatus:
        if any(check.status is CheckStatus.FAIL for check in self.checks):
            return CheckStatus.FAIL
        if any(status is CheckStatus.FAIL for status in self.external_scans.values()):
            return CheckStatus.FAIL
        if any(
            status is CheckStatus.BLOCKED_EXTERNAL for status in self.external_scans.values()
        ):
            return CheckStatus.BLOCKED_EXTERNAL
        return CheckStatus.PASS

    @property
    def external_acceptance(self) -> CheckStatus:
        if any(status is CheckStatus.FAIL for status in self.external_scans.values()):
            return CheckStatus.FAIL
        if any(
            status in {CheckStatus.BLOCKED_EXTERNAL, CheckStatus.NOT_RUN}
            for status in self.external_scans.values()
        ):
            return CheckStatus.BLOCKED_EXTERNAL
        return CheckStatus.PASS

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "status": self.status.value,
            "checks": [check.to_dict() for check in self.checks],
            "external_scans": {
                name: status.value for name, status in sorted(self.external_scans.items())
            },
            "external_acceptance": self.external_acceptance.value,
            "modes": dict(self.modes),
        }


_SAFE_MODES = {
    "analysis_only": True,
    "paper_trading": True,
    "manual_execution": False,
    "auto_execution": False,
}
_REQUIREMENT = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*(?:\[[A-Za-z0-9_,.-]+\])?)"
    r"==(?P<version>[0-9][A-Za-z0-9.!+:-]*)$"
)
_SOURCE_CONTRACTS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "apps/api/src/memeradar_api/auth.py",
        (
            "secrets.compare_digest",
            "authorize(principal, action)",
            "WWW-Authenticate",
        ),
        ("print(", "logger.info(authorization"),
    ),
    (
        "apps/api/src/memeradar_api/control.py",
        (
            "ControlAction.READ_STATE",
            "ControlAction.MUTATE_CONFIG",
            "role_authenticator.require",
        ),
        ("sign_transaction", "submit_transaction", "private_key"),
    ),
    (
        "packages/application/src/memeradar_application/control.py",
        ("_PROTECTED_CONFIG_FIELDS", "execution_kill_switch", "ControlRole", "authorize("),
        ("private_key", "sign_transaction", "submit_transaction"),
    ),
    (
        "packages/application/src/memeradar_application/narrative.py",
        ("NarrativeSnapshot", "NARRATIVE_SCHEMA_VERSION"),
        ("sign_transaction", "submit_transaction", "private_key"),
    ),
    (
        "packages/providers/src/memeradar_providers/narrative.py",
        ("<UNTRUSTED_DATA>", "_PROMPT_INSTRUCTION_PATTERN", "_PROMPT_TOOL_PATTERN"),
        ("sign_transaction", "submit_transaction", "private_key"),
    ),
    (
        "packages/application/src/memeradar_application/observability.py",
        ("OperationsProjector", "execution_eligible", "OperationalSloState"),
        ("sign_transaction", "submit_transaction", "private_key"),
    ),
)
_NETWORK_BLOCKERS = (
    "timed out",
    "timeout",
    "connection refused",
    "connection reset",
    "network is unreachable",
    "temporary failure in name resolution",
    "could not resolve",
    "eai_again",
    "unable to fetch",
    "failed to fetch",
    "no route to host",
    "registry unavailable",
    "database unavailable",
)


def _pass(name: str, detail: str) -> SecurityCheck:
    return SecurityCheck(name=name, status=CheckStatus.PASS, detail=detail)


def _fail(name: str, detail: str) -> SecurityCheck:
    return SecurityCheck(name=name, status=CheckStatus.FAIL, detail=detail)


def _read(root: Path, relative: str) -> str | None:
    try:
        return (root / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _normalized_name(value: str) -> str:
    return re.split(r"[\[<>=!~;\s]", value, maxsplit=1)[0].lower().replace("_", "-")


def _requirement_names(text: str) -> tuple[set[str], str | None]:
    names: set[str] = set()
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = _REQUIREMENT.fullmatch(line)
        if match is None:
            return set(), f"requirements.lock line {line_number} is not exact"
        names.add(_normalized_name(match.group("name")))
    return names, None


def _declared_python_names(data: Mapping[str, object]) -> tuple[set[str], str | None]:
    project = data.get("project")
    if not isinstance(project, Mapping):
        return set(), "pyproject.toml project metadata is missing"
    raw_requirements: list[object] = []
    dependencies = project.get("dependencies", [])
    if not isinstance(dependencies, list):
        return set(), "pyproject.toml dependencies are invalid"
    raw_requirements.extend(dependencies)
    optional = project.get("optional-dependencies", {})
    if not isinstance(optional, Mapping):
        return set(), "pyproject.toml optional dependencies are invalid"
    for values in optional.values():
        if not isinstance(values, list):
            return set(), "pyproject.toml optional dependency group is invalid"
        raw_requirements.extend(values)
    names: set[str] = set()
    for value in raw_requirements:
        if not isinstance(value, str) or _REQUIREMENT.fullmatch(value.strip()) is None:
            return set(), "pyproject.toml contains a non-exact dependency"
        names.add(_normalized_name(value.strip()))
    return names, None


def _string_mapping(value: object) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            return None
        result[key] = item
    return result


def check_dependency_locks(root: Path) -> SecurityCheck:
    """Verify exact declared Python/npm versions and lockfile roots."""

    requirements = _read(root, "requirements.lock")
    pyproject = _read(root, "pyproject.toml")
    package_text = _read(root, "apps/web/package.json")
    lock_text = _read(root, "apps/web/package-lock.json")
    if any(value is None for value in (requirements, pyproject, package_text, lock_text)):
        return _fail("dependency_lock_metadata", "required lock metadata is missing or unreadable")
    assert requirements is not None
    assert pyproject is not None
    assert package_text is not None
    assert lock_text is not None
    lock_names, error = _requirement_names(requirements)
    if error is not None:
        return _fail("dependency_lock_metadata", error)
    try:
        pyproject_data = tomllib.loads(pyproject)
        package_data = json.loads(package_text)
        package_lock = json.loads(lock_text)
    except (tomllib.TOMLDecodeError, json.JSONDecodeError):
        return _fail("dependency_lock_metadata", "dependency metadata is not parseable")
    if not isinstance(package_data, Mapping) or not isinstance(package_lock, Mapping):
        return _fail("dependency_lock_metadata", "npm metadata is not an object")
    declared_python, error = _declared_python_names(pyproject_data)
    if error is not None:
        return _fail("dependency_lock_metadata", error)
    if not declared_python.issubset(lock_names):
        return _fail(
            "dependency_lock_metadata",
            "a declared Python dependency is absent from the lock",
        )
    package_dependencies = _string_mapping(package_data.get("dependencies", {}))
    package_dev = _string_mapping(package_data.get("devDependencies", {}))
    packages = package_lock.get("packages")
    if package_dependencies is None or package_dev is None or not isinstance(packages, Mapping):
        return _fail("dependency_lock_metadata", "npm package or lock metadata is invalid")
    if package_lock.get("lockfileVersion") != 3:
        return _fail("dependency_lock_metadata", "npm lockfile version is not 3")
    root_package = packages.get("")
    if not isinstance(root_package, Mapping):
        return _fail("dependency_lock_metadata", "npm lockfile root package is missing")
    for field, declared in (
        ("dependencies", package_dependencies),
        ("devDependencies", package_dev),
    ):
        locked = _string_mapping(root_package.get(field, {}))
        if locked != declared:
            return _fail("dependency_lock_metadata", f"npm root {field} do not match package.json")
        if any(
            not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", value)
            for value in declared.values()
        ):
            return _fail(
                "dependency_lock_metadata",
                "package.json contains a non-exact npm version",
            )
    for package_name, metadata in packages.items():
        if package_name == "":
            continue
        if not isinstance(metadata, Mapping) or not isinstance(metadata.get("version"), str):
            return _fail("dependency_lock_metadata", "npm lock entry has no concrete version")
    return _pass("dependency_lock_metadata", "exact Python and npm lock metadata verified")


def check_container_contracts(root: Path) -> SecurityCheck:
    """Verify versioned base images and non-root runtime users."""

    files = (
        "infra/docker/api.Dockerfile",
        "infra/docker/worker.Dockerfile",
        "infra/docker/web.Dockerfile",
    )
    for relative in files:
        source = _read(root, relative)
        if source is None:
            return _fail("container_runtime_contracts", f"{relative} is missing or unreadable")
        bases = re.findall(r"^\s*FROM\s+([^\s]+)", source, flags=re.IGNORECASE | re.MULTILINE)
        if not bases:
            return _fail("container_runtime_contracts", f"{relative} has no base image")
        if any(
            base.lower().endswith(":latest")
            or (":" not in base and "@sha256:" not in base)
            for base in bases
        ):
            return _fail(
                "container_runtime_contracts",
                f"{relative} uses an unversioned base image",
            )
        users = re.findall(r"^\s*USER\s+([^\s#]+)", source, flags=re.IGNORECASE | re.MULTILINE)
        if not users or users[-1].lower() in {"root", "0", "0:0"}:
            return _fail("container_runtime_contracts", f"{relative} must end with a non-root USER")
    return _pass("container_runtime_contracts", "versioned base images and non-root users verified")


def check_tracked_file_secrets(root: Path) -> SecurityCheck:
    """Run the existing high-confidence scanner without exposing findings."""

    findings = scan_files(tracked_files(root))
    if findings:
        return _fail("tracked_file_secret_scan", "tracked-file secret scan found material")
    return _pass(
        "tracked_file_secret_scan",
        "tracked-file secret scan found no high-confidence material",
    )


def check_source_contracts(root: Path) -> SecurityCheck:
    """Verify source-level auth, advisory-LLM and non-execution markers."""

    for relative, required, forbidden in _SOURCE_CONTRACTS:
        source = _read(root, relative)
        if source is None:
            return _fail("rbac_auth_session_contracts", f"{relative} is missing or unreadable")
        lowered = source.lower()
        if any(marker.lower() not in lowered for marker in required):
            return _fail(
                "rbac_auth_session_contracts",
                f"required boundary marker missing in {relative}",
            )
        if any(marker.lower() in lowered for marker in forbidden):
            return _fail(
                "rbac_auth_session_contracts",
                f"forbidden authority marker found in {relative}",
            )
    return _pass(
        "rbac_auth_session_contracts",
        "RBAC, bearer, narrative and execution boundaries verified",
    )


def check_llm_contracts(root: Path) -> SecurityCheck:
    """Keep prompt/data handling distinct from the authorization check name."""

    provider_source = _read(root, "packages/providers/src/memeradar_providers/narrative.py")
    application_source = _read(root, "packages/application/src/memeradar_application/narrative.py")
    if provider_source is None or application_source is None:
        return _fail(
            "llm_prompt_data_contracts",
            "narrative boundary source is missing or unreadable",
        )
    required_provider = (
        "<UNTRUSTED_DATA>",
        "_PROMPT_SECRET_PATTERN",
        "_PROMPT_INSTRUCTION_PATTERN",
        "_PROMPT_TOOL_PATTERN",
    )
    application_contracts = _read(
        root,
        "packages/application/src/memeradar_application/provider_contracts.py",
    )
    if application_contracts is None:
        return _fail(
            "llm_prompt_data_contracts",
            "narrative contract source is missing or unreadable",
        )
    required_application = ("NarrativeAnalyzer", "config_hash", "schema_version")
    required_contracts = ("execution_eligible", "advisory", "NarrativeSnapshot")
    if any(marker.lower() not in provider_source.lower() for marker in required_provider):
        return _fail(
            "llm_prompt_data_contracts",
            "narrative provider sanitization markers are incomplete",
        )
    if any(marker.lower() not in application_source.lower() for marker in required_application):
        return _fail(
            "llm_prompt_data_contracts",
            "narrative application audit markers are incomplete",
        )
    if any(marker.lower() not in application_contracts.lower() for marker in required_contracts):
        return _fail(
            "llm_prompt_data_contracts",
            "narrative advisory contract markers are incomplete",
        )
    return _pass(
        "llm_prompt_data_contracts",
        "untrusted prompt data and strict advisory output markers verified",
    )


def check_protected_modes(
    environ: Mapping[str, str] | None = None,
) -> tuple[SecurityCheck, dict[str, bool]]:
    """Load settings and fail closed if any protected mode is overridden."""

    values = os.environ if environ is None else environ
    try:
        settings = Settings.from_env(values)
    except ValueError:
        return (
            _fail("protected_operating_modes", "protected operating mode validation failed"),
            dict(_SAFE_MODES),
        )
    modes = {
        "analysis_only": settings.analysis_only,
        "paper_trading": settings.paper_trading,
        "manual_execution": settings.manual_execution,
        "auto_execution": settings.auto_execution,
    }
    if modes != _SAFE_MODES:
        return _fail("protected_operating_modes", "protected operating mode values changed"), modes
    return _pass("protected_operating_modes", "all four protected modes verified"), modes


def _external_command(command: Sequence[str], *, cwd: Path) -> CheckStatus:
    executable = shutil.which(command[0])
    if executable is None:
        return CheckStatus.BLOCKED_EXTERNAL
    try:
        completed = subprocess.run(
            [executable, *command[1:]],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return CheckStatus.BLOCKED_EXTERNAL
    if completed.returncode == 0:
        return CheckStatus.PASS
    combined = f"{completed.stdout}\n{completed.stderr}".lower()
    if any(marker in combined for marker in _NETWORK_BLOCKERS):
        return CheckStatus.BLOCKED_EXTERNAL
    return CheckStatus.FAIL


def _run_external_scans(root: Path) -> dict[str, CheckStatus]:
    return {
        "pip_audit": _external_command(("pip-audit", "-r", "requirements.lock"), cwd=root),
        "npm_audit": _external_command(
            ("npm", "audit", "--audit-level=high", "--omit=dev"),
            cwd=root / "apps" / "web",
        ),
        "container_scan": _external_command(
            (
                "trivy",
                "config",
                "--exit-code",
                "1",
                "--severity",
                "HIGH,CRITICAL",
                "infra/docker",
            ),
            cwd=root,
        ),
    }


def run_review(
    root: Path,
    *,
    external: bool = False,
    environ: Mapping[str, str] | None = None,
) -> SecurityReviewReport:
    """Run the keyless review and optionally installed external scanners."""

    normalized_root = root.resolve()
    mode_check, modes = check_protected_modes(environ)
    checks = (
        check_dependency_locks(normalized_root),
        check_container_contracts(normalized_root),
        check_tracked_file_secrets(normalized_root),
        check_source_contracts(normalized_root),
        check_llm_contracts(normalized_root),
        mode_check,
    )
    external_scans = (
        _run_external_scans(normalized_root)
        if external
        else {
            "pip_audit": CheckStatus.NOT_RUN,
            "npm_audit": CheckStatus.NOT_RUN,
            "container_scan": CheckStatus.NOT_RUN,
        }
    )
    return SecurityReviewReport(checks=checks, external_scans=external_scans, modes=modes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--external",
        action="store_true",
        help="attempt installed vulnerability scanners and classify unavailable access",
    )
    args = parser.parse_args()
    report = run_review(ROOT, external=args.external)
    print(json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":")))
    return {
        CheckStatus.PASS: 0,
        CheckStatus.BLOCKED_EXTERNAL: 2,
        CheckStatus.FAIL: 1,
        CheckStatus.NOT_RUN: 2,
    }[report.status]


if __name__ == "__main__":
    raise SystemExit(main())
