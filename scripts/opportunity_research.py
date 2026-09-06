#!/usr/bin/env python3
"""Run measurement-only opportunity ablation on a canonical case-study bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    ROOT / "packages" / "application" / "src",
    ROOT / "packages" / "domain" / "src",
):
    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)

from memeradar_application.opportunity_case_studies import (  # noqa: E402
    load_opportunity_case_studies,
)
from memeradar_application.opportunity_research import (  # noqa: E402
    OpportunityResearchAnalyzer,
    samples_from_case_studies,
)
from memeradar_application.replay_harness import ReplayHarness  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run keyless event-time opportunity ablation without production promotion."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("fixtures/research/opportunity_case_studies.json"),
        help="bounded opportunity case-study bundle",
    )
    parser.add_argument(
        "--output", type=Path, help="optional report JSON path"
    )
    return parser


def load_report(input_path: Path):
    bundle = load_opportunity_case_studies(input_path)
    replay = ReplayHarness().replay(bundle.dataset, manifest=bundle.manifest)
    return OpportunityResearchAnalyzer().analyze(samples_from_case_studies(bundle, replay))


def main() -> int:
    arguments = _parser().parse_args()
    try:
        report = load_report(arguments.input)
        artifact = f"{json.dumps(report.to_json_dict(), indent=2, sort_keys=True)}\n"
        if arguments.output is None:
            print(artifact, end="")
        else:
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_text(artifact, encoding="utf-8")
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        del exc
        print("opportunity research failed: INVALID_INPUT_OR_CONTRACT", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
