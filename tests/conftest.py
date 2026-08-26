"""Test import paths for the repository's source-layout packages."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for source_root in (
    ROOT / "packages" / "application" / "src",
    ROOT / "packages" / "domain" / "src",
    ROOT / "packages" / "persistence" / "src",
    ROOT / "packages" / "telemetry" / "src",
    ROOT / "apps" / "api" / "src",
    ROOT / "apps" / "worker" / "src",
):
    sys.path.insert(0, str(source_root))
