"""Test import paths and deterministic async test-runtime behavior."""

import asyncio
import sys
from pathlib import Path

try:
    import uvloop
except ImportError:  # pragma: no cover - the project test extra normally includes it
    uvloop = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for source_root in (
    ROOT / "packages" / "application" / "src",
    ROOT / "packages" / "domain" / "src",
    ROOT / "packages" / "providers" / "src",
    ROOT / "packages" / "persistence" / "src",
    ROOT / "packages" / "telemetry" / "src",
    ROOT / "apps" / "api" / "src",
    ROOT / "apps" / "worker" / "src",
):
    sys.path.insert(0, str(source_root))

# The managed Python runtime's default selector loop does not wake a loop from a
# sibling thread reliably.  Starlette's TestClient uses that cross-thread portal;
# uvloop is already provided by uvicorn[standard] and keeps the existing API tests
# deterministic without changing production event-loop configuration.
if uvloop is not None:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
