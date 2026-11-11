from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_coverage_is_branch_enabled_and_scoped_to_application_sources():
    with (ROOT / "pyproject.toml").open("rb") as stream:
        config = tomllib.load(stream)

    coverage = config["tool"]["coverage"]
    assert coverage["run"] == {
        "branch": True,
        "source": ["apps", "packages"],
        "omit": ["tests/*", "scripts/*"],
    }
    assert coverage["report"]["show_missing"] is True


def test_make_and_ci_use_the_same_coverage_command():
    makefile = (ROOT / "Makefile").read_text()
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()

    expected_make_test = (
        '$(PYTHON) -m pytest -q -m "not integration" '
        "--cov=apps --cov=packages --cov-report=term-missing"
    )
    assert expected_make_test in makefile
    assert "run: make test PYTHON=python" in workflow
    assert workflow.index("name: Migration upgrade") < workflow.index(
        "name: PostgreSQL integration acceptance"
    )


def test_integration_runbooks_keep_test_database_separate_from_runtime_database():
    for name in ("RELIABILITY.md", "RELEASE.md"):
        runbook = (ROOT / "docs" / "RUNBOOKS" / name).read_text()

        assert 'MEMERADAR_TEST_DATABASE_URL="$MEMERADAR_DATABASE_URL"' not in runbook
        assert "disposable" in runbook.lower()
