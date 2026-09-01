"""Generate a deterministic, keyless CycloneDX SBOM from locked inputs."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path
from uuid import UUID

SBOM_SCHEMA_VERSION = "security-sbom-v1"
_PYTHON_LOCK_LINE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)(?:\[[A-Za-z0-9_,.-]+\])?==(?P<version>[^\s;]+)$"
)
_NODE_MODULES = "node_modules/"


def _required_file(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.is_file():
        raise ValueError(f"required SBOM input is missing: {relative}")
    return path


def _python_component(name: str, version: str) -> dict[str, object]:
    normalized_name = re.sub(r"[-_.]+", "-", name).lower()
    reference = f"pkg:pypi/{normalized_name}@{version}"
    return {
        "type": "library",
        "bom-ref": reference,
        "name": normalized_name,
        "version": version,
        "purl": reference,
        "properties": [
            {"name": "memeradar:source", "value": "requirements.lock"},
        ],
    }


def _python_components(root: Path) -> list[dict[str, object]]:
    lock = _required_file(root, "requirements.lock")
    components: list[dict[str, object]] = []
    for line_number, raw_line in enumerate(lock.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _PYTHON_LOCK_LINE.fullmatch(line)
        if match is None:
            raise ValueError(f"requirements.lock line {line_number} is not exact")
        components.append(_python_component(match["name"], match["version"]))
    if not components:
        raise ValueError("requirements.lock contains no components")
    return components


def _npm_package_name(package_path: str) -> str:
    if not package_path.startswith(_NODE_MODULES):
        raise ValueError("npm package path is not rooted in node_modules")
    return package_path.rsplit(_NODE_MODULES, 1)[-1]


def _npm_component(package_path: str, package: Mapping[str, object]) -> dict[str, object]:
    name = _npm_package_name(package_path)
    version = package.get("version")
    resolved = package.get("resolved")
    integrity = package.get("integrity")
    if not isinstance(version, str) or not version:
        raise ValueError(f"npm package {name} has no concrete version")
    if not isinstance(resolved, str) or not resolved.startswith("https://"):
        raise ValueError(f"npm package {name} has no HTTPS registry resolution")
    if not isinstance(integrity, str) or not integrity.startswith("sha512-"):
        raise ValueError(f"npm package {name} has no SHA-512 integrity")
    reference = f"pkg:npm/{name}@{version}"
    component: dict[str, object] = {
        "type": "library",
        "bom-ref": reference,
        "name": name,
        "version": version,
        "purl": reference,
        "properties": [
            {"name": "memeradar:source", "value": "apps/web/package-lock.json"},
            {"name": "memeradar:resolved", "value": resolved},
        ],
    }
    try:
        digest = base64.b64decode(integrity.removeprefix("sha512-"), validate=True).hex()
    except (ValueError, TypeError) as exc:
        raise ValueError(f"npm package {name} has invalid integrity metadata") from exc
    component["hashes"] = [{"alg": "SHA-512", "content": digest}]
    return component


def _npm_components(root: Path) -> list[dict[str, object]]:
    lock_path = _required_file(root, "apps/web/package-lock.json")
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("package-lock.json is not valid JSON") from exc
    if not isinstance(lock, dict) or lock.get("lockfileVersion") != 3:
        raise ValueError("package-lock.json must use lockfileVersion 3")
    packages = lock.get("packages")
    if not isinstance(packages, dict):
        raise ValueError("package-lock.json packages must be an object")
    by_reference: dict[str, dict[str, object]] = {}
    for package_path, package in sorted(packages.items()):
        if package_path == "":
            continue
        if not isinstance(package_path, str) or not isinstance(package, Mapping):
            raise ValueError("package-lock.json contains an invalid package entry")
        component = _npm_component(package_path, package)
        by_reference.setdefault(str(component["bom-ref"]), component)
    if not by_reference:
        raise ValueError("package-lock.json contains no components")
    return list(by_reference.values())


def _docker_component(image: str, source: str) -> dict[str, object]:
    image_without_digest = image.split("@", 1)[0]
    last_segment = image_without_digest.rsplit("/", 1)[-1]
    if ":" in last_segment:
        name, version = last_segment.rsplit(":", 1)
        image_name = "/".join((*image_without_digest.split("/")[:-1], name))
    else:
        image_name = image_without_digest
        version = "unknown"
    reference = f"pkg:docker/{image_name}@{version}"
    return {
        "type": "container",
        "bom-ref": reference,
        "name": image_name,
        "version": version,
        "purl": reference,
        "properties": [{"name": "memeradar:source", "value": source}],
    }


def _docker_components(root: Path) -> list[dict[str, object]]:
    docker_root = root / "infra" / "docker"
    files = sorted(docker_root.glob("*.Dockerfile"))
    if not files:
        raise ValueError("no Dockerfiles found for SBOM image inputs")
    by_reference: dict[str, dict[str, object]] = {}
    for path in files:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            parts = raw_line.split()
            if len(parts) < 2 or parts[0].upper() != "FROM":
                continue
            image = parts[1]
            if image.upper() == "SCRATCH":
                continue
            component = _docker_component(image, path.relative_to(root).as_posix())
            reference = str(component["bom-ref"])
            existing = by_reference.get(reference)
            if existing is None:
                by_reference[reference] = component
                continue
            properties = existing.setdefault("properties", [])
            if isinstance(properties, list):
                source = component["properties"]
                if isinstance(source, list):
                    for value in source:
                        if value not in properties:
                            properties.append(value)
    if not by_reference:
        raise ValueError("Dockerfiles contain no base images")
    return list(by_reference.values())


def _component_key(component: Mapping[str, object]) -> str:
    reference = component.get("bom-ref")
    if not isinstance(reference, str) or not reference:
        raise ValueError("SBOM component has no bom-ref")
    return reference


def _stable_serial(components: Iterable[Mapping[str, object]]) -> str:
    references = "\n".join(_component_key(component) for component in components)
    digest = hashlib.sha256(references.encode("utf-8")).hexdigest()[:32]
    value = UUID(hex=digest)
    return f"urn:uuid:{value}"


def build_sbom(root: Path) -> dict[str, object]:
    """Build the same SBOM for the same locked repository inputs every time."""

    root = root.resolve()
    pyproject_path = _required_file(root, "pyproject.toml")
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = pyproject.get("project")
    if not isinstance(project, dict):
        raise ValueError("pyproject.toml project metadata is missing")
    project_name = project.get("name")
    project_version = project.get("version")
    if not isinstance(project_name, str) or not isinstance(project_version, str):
        raise ValueError("pyproject.toml project name/version are missing")

    components = [*_python_components(root), *_npm_components(root), *_docker_components(root)]
    by_reference: dict[str, dict[str, object]] = {}
    for component in components:
        by_reference.setdefault(_component_key(component), component)
    ordered = [by_reference[key] for key in sorted(by_reference)]
    application_ref = f"pkg:generic/{project_name}@{project_version}"
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": _stable_serial(ordered),
        "version": 1,
        "schema_version": SBOM_SCHEMA_VERSION,
        "metadata": {
            "component": {
                "type": "application",
                "name": project_name,
                "version": project_version,
                "bom-ref": application_ref,
            },
            "properties": [
                {"name": "memeradar:source", "value": "locked repository inputs"},
            ],
        },
        "components": ordered,
    }


def serialize_sbom(sbom: Mapping[str, object]) -> str:
    """Serialize an SBOM with stable key and component ordering."""

    return json.dumps(sbom, indent=2, sort_keys=True) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        sbom = build_sbom(args.root)
        encoded = serialize_sbom(sbom)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
        if args.check:
            components = sbom.get("components", ())
            count = len(components) if isinstance(components, list) else 0
            digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            print(
                f"SBOM PASS schema={SBOM_SCHEMA_VERSION} "
                f"components={count} digest=sha256:{digest}"
            )
        elif args.output is None:
            sys.stdout.write(encoded)
    except (OSError, TypeError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"SBOM FAIL: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
