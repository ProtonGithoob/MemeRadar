"""Doctor: diff the pinned Pump.fun IDL against an official revision.

Usage:
    python scripts/pump_idl_drift.py [REVISION]   (default: main)

Exit code 0 when every instruction in the target revision is either in the
pinned IDL or classified in ``PUMP_FUN_UNROUTED_INSTRUCTIONS``; 1 when an
unclassified instruction or a changed discriminator appears (new drift that
needs review); 2 when the IDL could not be fetched.  Read-only.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _package in ("domain", "application", "providers", "telemetry"):
    sys.path.insert(0, str(ROOT / "packages" / _package / "src"))

from memeradar_providers.pump_fun_idl import (  # noqa: E402
    PUMP_FUN_IDL_REVISION,
    PUMP_FUN_UNROUTED_INSTRUCTIONS,
)

RAW = "https://raw.githubusercontent.com/pump-fun/pump-public-docs/{rev}/idl/pump.json"


def _fetch(revision: str) -> tuple[dict[str, object], str]:
    request = urllib.request.Request(
        RAW.format(rev=revision), headers={"user-agent": "memeradar-idl-doctor"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed host
        body = response.read()
    return json.loads(body), hashlib.sha256(body).hexdigest()


def _instructions(idl: dict[str, object]) -> dict[str, str]:
    values = idl.get("instructions", [])
    assert isinstance(values, list)
    return {item["name"]: bytes(item["discriminator"]).hex() for item in values}


def main(argv: list[str]) -> int:
    target = argv[1] if len(argv) > 1 else "main"
    try:
        pinned, _ = _fetch(PUMP_FUN_IDL_REVISION)
        latest, digest = _fetch(target)
    except Exception as error:  # noqa: BLE001 - doctor reports, never crashes
        print(f"IDL_FETCH_FAILED {type(error).__name__}")
        return 2
    old, new = _instructions(pinned), _instructions(latest)
    changed = sorted(name for name in old if name in new and old[name] != new[name])
    added = {name: disc for name, disc in new.items() if name not in old}
    unclassified = sorted(
        name
        for name, disc in added.items()
        if PUMP_FUN_UNROUTED_INSTRUCTIONS.get(name, ("", ""))[0] != disc
    )
    print(json.dumps(
        {
            "pinned_revision": PUMP_FUN_IDL_REVISION,
            "target_revision": target,
            "target_sha256": digest,
            "pinned_count": len(old),
            "target_count": len(new),
            "added": sorted(added),
            "removed": sorted(name for name in old if name not in new),
            "changed_discriminators": changed,
            "unclassified_new_instructions": unclassified,
        },
        indent=2,
    ))
    return 1 if unclassified or changed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
