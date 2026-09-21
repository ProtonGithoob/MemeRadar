#!/usr/bin/env python3
"""Read-only check for the pinned Pump.fun IDL revision and digest."""

from __future__ import annotations

# The repository's package roots are intentionally not installed by the bare
# script runner; imports follow the explicit local roots below.
# ruff: noqa: E402
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    ROOT / "packages" / "domain" / "src",
    ROOT / "packages" / "providers" / "src",
):
    sys.path.insert(0, str(source_root))

from memeradar_providers.pump_fun_idl import (
    PUMP_FUN_IDL_RAW_SOURCE,
    PUMP_FUN_IDL_SOURCE,
)
from memeradar_providers.pump_fun_protocol_drift import (
    IDL_SHA256,
    LOCAL_SCHEMA_VERSION,
    PINNED_REVISION,
    compare_upstream,
)

UPSTREAM_REPOSITORY = "https://github.com/pump-fun/pump-public-docs.git"


def _upstream_revision() -> str:
    completed = subprocess.run(
        ["git", "ls-remote", UPSTREAM_REPOSITORY, "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return completed.stdout.split()[0]


def _upstream_sha256() -> str:
    with urlopen(PUMP_FUN_IDL_RAW_SOURCE, timeout=20) as response:  # noqa: S310 - pinned public source.
        return hashlib.sha256(response.read()).hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", help="fixture revision for an offline check")
    parser.add_argument("--sha256", help="fixture IDL digest for an offline check")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        revision = args.revision or _upstream_revision()
        digest = args.sha256 or _upstream_sha256()
        result = dict(compare_upstream(revision, digest))
        result.update(
            {
                "upstream_repository": UPSTREAM_REPOSITORY,
                "checked_source": PUMP_FUN_IDL_SOURCE,
                "checked_raw_source": PUMP_FUN_IDL_RAW_SOURCE,
            }
        )
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "PASS" else 2
    except Exception as error:  # noqa: BLE001 - report external access without changing the pin.
        print(
            json.dumps(
                {
                    "status": "BLOCKED_EXTERNAL",
                    "production_decoder_action": "UNCHANGED",
                    "error_class": type(error).__name__,
                    "error": str(error)[:256],
                    "pinned_revision": PINNED_REVISION,
                    "pinned_idl_sha256": IDL_SHA256,
                    "local_schema_version": LOCAL_SCHEMA_VERSION,
                    "upstream_source": PUMP_FUN_IDL_SOURCE,
                    "upstream_raw_source": PUMP_FUN_IDL_RAW_SOURCE,
                },
                sort_keys=True,
            )
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
