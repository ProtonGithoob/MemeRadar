"""Read-only comparison for the pinned Pump.fun decoder inputs."""

from __future__ import annotations

from collections.abc import Mapping

from .pump_fun_idl import (
    PUMP_FUN_IDL_REVISION as PINNED_REVISION,
)
from .pump_fun_idl import (
    PUMP_FUN_IDL_SHA256 as IDL_SHA256,
)
from .pump_fun_idl import (
    PUMP_FUN_IDL_SOURCE,
)
from .pump_fun_idl import (
    PUMP_FUN_LOCAL_SCHEMA_VERSION as LOCAL_SCHEMA_VERSION,
)


def compare_upstream(
    observed_revision: str | None,
    observed_sha256: str | None,
    *,
    observed_schema_version: str = LOCAL_SCHEMA_VERSION,
) -> Mapping[str, object]:
    """Compare observed upstream metadata without changing production state."""

    drift = (
        observed_revision != PINNED_REVISION
        or observed_sha256 != IDL_SHA256
        or observed_schema_version != LOCAL_SCHEMA_VERSION
    )
    return {
        "status": "PROTOCOL_DRIFT_DETECTED" if drift else "PASS",
        "production_decoder_action": "UNCHANGED",
        "upstream_source": PUMP_FUN_IDL_SOURCE,
        "pinned_revision": PINNED_REVISION,
        "pinned_idl_sha256": IDL_SHA256,
        "local_schema_version": LOCAL_SCHEMA_VERSION,
        "observed_revision": observed_revision,
        "observed_idl_sha256": observed_sha256,
        "observed_schema_version": observed_schema_version,
    }


__all__ = ["IDL_SHA256", "LOCAL_SCHEMA_VERSION", "PINNED_REVISION", "compare_upstream"]
