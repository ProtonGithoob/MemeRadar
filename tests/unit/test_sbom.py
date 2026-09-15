"""Deterministic CycloneDX SBOM contracts for the pinned repository inputs."""

import json
from pathlib import Path

from scripts.sbom import SBOM_SCHEMA_VERSION, build_sbom, serialize_sbom

ROOT = Path(__file__).resolve().parents[2]


def test_sbom_is_deterministic_and_contains_pinned_python_npm_and_image_inputs() -> None:
    first = build_sbom(ROOT)
    second = build_sbom(ROOT)

    assert first == second
    assert first["schema_version"] == SBOM_SCHEMA_VERSION
    assert first["bomFormat"] == "CycloneDX"
    assert first["specVersion"] == "1.5"
    assert first["metadata"]["component"] == {
        "type": "application",
        "name": "memeradar",
        "version": "0.1.0",
        "bom-ref": "pkg:generic/memeradar@0.1.0",
    }
    components = first["components"]
    refs = [component["bom-ref"] for component in components]
    assert refs == sorted(refs)
    assert len(refs) == len(set(refs))
    assert "pkg:pypi/fastapi@0.141.1" in refs
    assert "pkg:pypi/starlette@1.3.1" in refs
    assert "pkg:npm/@playwright/test@1.62.1" in refs
    assert "pkg:docker/python@3.12-slim" in refs
    assert "pkg:docker/node@22-alpine" in refs


def test_sbom_serialization_is_stable_and_contains_no_secret_shaped_fields() -> None:
    encoded = serialize_sbom(build_sbom(ROOT))
    parsed = json.loads(encoded)

    assert json.loads(encoded) == parsed
    lowered = encoded.lower()
    assert "private_key" not in lowered
    assert "api_token" not in lowered
    assert "seed_phrase" not in lowered
    assert "secret" not in lowered
