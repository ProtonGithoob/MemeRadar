from __future__ import annotations

from pathlib import Path
import tomllib


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

    assert "$(PYTHON) -m pytest -q --cov=apps --cov=packages --cov-report=term-missing" in makefile
    assert "python -m pytest -q --cov=apps --cov=packages --cov-report=term-missing" in workflow
