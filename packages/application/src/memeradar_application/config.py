"""Validated runtime configuration with protected operating-mode defaults."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def _parse_bool(name: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _parse_int(name: str, value: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _parse_float(name: str, value: str, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _optional_value(environ: Mapping[str, str], name: str) -> str | None:
    value = environ.get(name, "").strip()
    return value or None


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings that can be created without provider credentials."""

    app_env: str
    log_level: str
    api_host: str
    api_port: int
    worker_poll_interval_seconds: float
    database_url: str | None
    redis_url: str | None
    require_database_for_readiness: bool
    require_redis_for_readiness: bool
    readiness_timeout_seconds: float
    analysis_only: bool
    paper_trading: bool
    manual_execution: bool
    auto_execution: bool

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Build settings from an explicit mapping or the process environment.

        The four operating modes are protected until a later roadmap gate. Any
        attempt to override them fails closed instead of silently changing risk.
        """

        values: Mapping[str, str] = os.environ if environ is None else environ
        protected_modes = (
            ("ANALYSIS_ONLY", True),
            ("PAPER_TRADING", True),
            ("MANUAL_EXECUTION", False),
            ("AUTO_EXECUTION", False),
        )
        parsed_modes: dict[str, bool] = {}
        for name, expected in protected_modes:
            actual = _parse_bool(name, values.get(name, str(expected)))
            if actual != expected:
                raise ValueError(f"{name} is a protected operating mode")
            parsed_modes[name] = actual

        api_port = _parse_int("API_PORT", values.get("API_PORT", "8000"), 1, 65535)
        poll_interval = _parse_float(
            "WORKER_POLL_INTERVAL_SECONDS",
            values.get("WORKER_POLL_INTERVAL_SECONDS", "1.0"),
            0.1,
            3600.0,
        )
        readiness_timeout = _parse_float(
            "READINESS_TIMEOUT_SECONDS",
            values.get("READINESS_TIMEOUT_SECONDS", "0.25"),
            0.01,
            10.0,
        )
        return cls(
            app_env=values.get("APP_ENV", "development").strip() or "development",
            log_level=values.get("LOG_LEVEL", "INFO").strip().upper() or "INFO",
            api_host=values.get("API_HOST", "127.0.0.1").strip() or "127.0.0.1",
            api_port=api_port,
            worker_poll_interval_seconds=poll_interval,
            database_url=_optional_value(values, "DATABASE_URL"),
            redis_url=_optional_value(values, "REDIS_URL"),
            require_database_for_readiness=_parse_bool(
                "REQUIRE_DATABASE_FOR_READINESS",
                values.get("REQUIRE_DATABASE_FOR_READINESS", "false"),
            ),
            require_redis_for_readiness=_parse_bool(
                "REQUIRE_REDIS_FOR_READINESS",
                values.get("REQUIRE_REDIS_FOR_READINESS", "false"),
            ),
            readiness_timeout_seconds=readiness_timeout,
            analysis_only=parsed_modes["ANALYSIS_ONLY"],
            paper_trading=parsed_modes["PAPER_TRADING"],
            manual_execution=parsed_modes["MANUAL_EXECUTION"],
            auto_execution=parsed_modes["AUTO_EXECUTION"],
        )
