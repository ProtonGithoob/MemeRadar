"""Runtime scoring must not import future-only research labels."""

from pathlib import Path

APPLICATION = (
    Path(__file__).parents[2]
    / "packages"
    / "application"
    / "src"
    / "memeradar_application"
)


def test_live_early_runtime_modules_have_no_future_outcome_dependencies() -> None:
    forbidden = ("early_replay", "ExtremeWinner", "MissedWinnerAnalyzer", "FalsePositiveAnalyzer")
    runtime_modules = ("early_runtime.py", "early_scoring.py", "early_decision.py")

    for module in runtime_modules:
        source = (APPLICATION / module).read_text(encoding="utf-8")
        assert not any(name in source for name in forbidden), module
