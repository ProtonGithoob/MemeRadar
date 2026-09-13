"""Fail when static classes in the frontend lack CSS definitions."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/web/src/app"
STYLESHEET = ROOT / "apps/web/src/app/globals.css"


def css_classes(css: str) -> set[str]:
    values: set[str] = set()
    for match in re.finditer(r"\.((?:\\.|[A-Za-z0-9_-])+)", css):
        values.add(match.group(1).replace("\\", ""))
    return values


def static_classes(source: str) -> set[str]:
    values: set[str] = set()
    for match in re.finditer(r'className="([^"]+)"', source):
        values.update(match.group(1).split())
    return {value for value in values if "{" not in value and "}" not in value}


def main() -> int:
    defined = css_classes(STYLESHEET.read_text(encoding="utf-8"))
    referenced: set[str] = set()
    sources = sorted(APP.rglob("*.tsx"))
    for source in sources:
        referenced.update(static_classes(source.read_text(encoding="utf-8")))
    missing = sorted(referenced - defined)
    if missing:
        print("Missing static CSS classes:")
        print("\n".join(missing))
        return 1
    print(
        f"CSS contract OK: {len(referenced)} static frontend classes checked "
        f"across {len(sources)} files"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
