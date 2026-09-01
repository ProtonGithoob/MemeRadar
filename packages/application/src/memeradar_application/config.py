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
    viewer_api_token: str | None
    operator_api_token: str | None
    admin_api_token: str | None
    execution_api_token: str | None
    telegram_api_url: str | None
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    alert_max_messages_per_window: int
    alert_rate_limit_window_seconds: float
    analysis_only: bool
    paper_trading: bool
    manual_execution: bool
    auto_execution: bool
    early_score_handoff_seconds: int = 300

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
        early_score_handoff_seconds = _parse_int(
            "EARLY_SCORE_HANDOFF_SECONDS",
            values.get("EARLY_SCORE_HANDOFF_SECONDS", "300"),
            1,
            86_400,
        )
        role_tokens = {
            "VIEWER_API_TOKEN": _optional_value(values, "VIEWER_API_TOKEN"),
            "OPERATOR_API_TOKEN": _optional_value(values, "OPERATOR_API_TOKEN"),
            "ADMIN_API_TOKEN": _optional_value(values, "ADMIN_API_TOKEN"),
            "EXECUTION_API_TOKEN": _optional_value(values, "EXECUTION_API_TOKEN"),
        }
        configured_tokens = [token for token in role_tokens.values() if token is not None]
        if len(configured_tokens) != len(set(configured_tokens)):
            raise ValueError("role tokens must be unique")
        alert_max_messages = _parse_int(
            "ALERT_MAX_MESSAGES_PER_WINDOW",
            values.get("ALERT_MAX_MESSAGES_PER_WINDOW", "20"),
            1,
            1000,
        )
        alert_window = _parse_float(
            "ALERT_RATE_LIMIT_WINDOW_SECONDS",
            values.get("ALERT_RATE_LIMIT_WINDOW_SECONDS", "60"),
            1.0,
            86400.0,
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
            viewer_api_token=role_tokens["VIEWER_API_TOKEN"],
            operator_api_token=role_tokens["OPERATOR_API_TOKEN"],
            admin_api_token=role_tokens["ADMIN_API_TOKEN"],
            execution_api_token=role_tokens["EXECUTION_API_TOKEN"],
            telegram_api_url=_optional_value(values, "TELEGRAM_API_URL"),
            telegram_bot_token=_optional_value(values, "TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_optional_value(values, "TELEGRAM_CHAT_ID"),
            alert_max_messages_per_window=alert_max_messages,
            alert_rate_limit_window_seconds=alert_window,
            analysis_only=parsed_modes["ANALYSIS_ONLY"],
            paper_trading=parsed_modes["PAPER_TRADING"],
            manual_execution=parsed_modes["MANUAL_EXECUTION"],
            auto_execution=parsed_modes["AUTO_EXECUTION"],
            early_score_handoff_seconds=early_score_handoff_seconds,
        )
