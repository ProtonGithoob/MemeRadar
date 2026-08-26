"""Test import paths for the repository's source-layout packages."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    ROOT / "packages" / "application" / "src",
    ROOT / "packages" / "domain" / "src",
    ROOT / "apps" / "api" / "src",
    ROOT / "apps" / "worker" / "src",
):
    sys.path.insert(0, str(source_root))
