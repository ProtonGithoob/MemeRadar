"""Validated runtime configuration with protected operating-mode defaults."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})
SUPPORTED_CHAINS = ("solana", "bnb", "robinhood")


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


def _first_optional_value(environ: Mapping[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = _optional_value(environ, name)
        if value is not None:
            return value
    return None


def _default_value(environ: Mapping[str, str], name: str, default: str) -> str:
    return environ.get(name, "").strip() or default


def _provider_choice(
    environ: Mapping[str, str],
    name: str,
    default: str,
    allowed: frozenset[str],
) -> str:
    value = _default_value(environ, name, default).lower()
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of: {choices}")
    return value


def _chain_list(environ: Mapping[str, str], name: str) -> tuple[str, ...]:
    raw = environ.get(name, ",".join(SUPPORTED_CHAINS))
    values = tuple(item.strip().lower() for item in raw.split(",") if item.strip())
    if not values:
        raise ValueError(f"{name} must contain at least one chain")
    unknown = sorted(set(values) - set(SUPPORTED_CHAINS))
    if unknown:
        raise ValueError(f"{name} contains unsupported chains: {', '.join(unknown)}")
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicate chains")
    return values


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
    telegram_bot_username: str | None
    telegram_chat_id: str | None
    alert_max_messages_per_window: int
    alert_rate_limit_window_seconds: float
    analysis_only: bool
    paper_trading: bool
    manual_execution: bool
    auto_execution: bool
    early_score_handoff_seconds: int = 300
    solana_rpc_url: str = "https://api.mainnet.solana.com"
    helius_rpc_url: str | None = None
    helius_api_key: str | None = None
    helius_stream_url: str | None = None
    solana_stream_url: str | None = None
    solana_backfill_url: str | None = None
    dexscreener_api_url: str = "https://api.dexscreener.com"
    dexscreener_api_key: str | None = None
    market_data_provider: str = "dexscreener"
    birdeye_api_url: str | None = None
    birdeye_api_key: str | None = None
    paper_quote_provider: str = "dexscreener"
    paper_quote_url: str | None = None
    paper_quote_api_key: str | None = None
    rugcheck_api_url: str | None = None
    rugcheck_api_key: str | None = None
    wallet_intelligence_provider: str = "local"
    external_wallet_api_url: str | None = None
    external_wallet_api_key: str | None = None
    external_wallet_stream_url: str | None = None
    social_metadata_provider: str = "dexscreener"
    social_api_url: str | None = None
    social_api_key: str | None = None
    narrative_provider: str = "ollama"
    narrative_api_url: str = "http://host.docker.internal:11434"
    narrative_api_key: str | None = None
    narrative_model: str | None = None
    enabled_chains: tuple[str, ...] = SUPPORTED_CHAINS
    bnb_rpc_url: str | None = None
    bnb_rpc_fallback_url: str | None = None
    bnb_chain_id: int = 56
    robinhood_rpc_url: str = "https://rpc.mainnet.chain.robinhood.com"
    robinhood_rpc_fallback_url: str | None = None
    robinhood_chain_id: int = 4663
    robinhood_sequencer_feed_url: str = "wss://feed.mainnet.chain.robinhood.com"
    robinhood_blockscout_api_url: str | None = None
    x_provider_enabled: bool = False
    x_provider_api_key: str | None = None
    x_provider_bearer_token: str | None = None
    website_url: str | None = None
    website_name: str | None = None

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
        legacy_narrative_url = _optional_value(values, "NARRATIVE_API_URL")
        legacy_narrative_key = _optional_value(values, "NARRATIVE_API_KEY")
        configured_narrative_provider = _optional_value(values, "NARRATIVE_PROVIDER")
        if configured_narrative_provider is None:
            configured_narrative_provider = (
                "external"
                if legacy_narrative_url is not None or legacy_narrative_key is not None
                else "ollama"
            )
        if configured_narrative_provider not in {"ollama", "external", "disabled"}:
            raise ValueError("NARRATIVE_PROVIDER must be one of: disabled, external, ollama")
        dexscreener_url = _default_value(
            values,
            "DEXSCREENER_API_URL",
            _default_value(values, "DEXSCREENER_API_BASE_URL", "https://api.dexscreener.com"),
        )
        stream_url = _first_optional_value(
            values,
            ("MEMERADAR_SOLANA_STREAM_URL", "SOLANA_STREAM_URL", "HELIUS_WEBSOCKET_URL"),
        )
        backfill_url = _first_optional_value(
            values,
            ("MEMERADAR_SOLANA_BACKFILL_URL", "SOLANA_RPC_BACKFILL_URL"),
        )
        enabled_chains = _chain_list(values, "ENABLED_CHAINS")
        bnb_chain_id = _parse_int("BNB_CHAIN_ID", values.get("BNB_CHAIN_ID", "56"), 1, 2**64 - 1)
        robinhood_chain_id = _parse_int(
            "ROBINHOOD_CHAIN_ID",
            values.get("ROBINHOOD_CHAIN_ID", "4663"),
            1,
            2**64 - 1,
        )
        if robinhood_chain_id != 4663:
            raise ValueError("ROBINHOOD_CHAIN_ID is fixed at 4663")
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
            telegram_api_url=_optional_value(values, "TELEGRAM_API_URL")
            or "https://api.telegram.org",
            telegram_bot_token=_optional_value(values, "TELEGRAM_BOT_TOKEN"),
            telegram_bot_username=_optional_value(values, "TELEGRAM_BOT_USERNAME"),
            telegram_chat_id=_optional_value(values, "TELEGRAM_CHAT_ID"),
            alert_max_messages_per_window=alert_max_messages,
            alert_rate_limit_window_seconds=alert_window,
            analysis_only=parsed_modes["ANALYSIS_ONLY"],
            paper_trading=parsed_modes["PAPER_TRADING"],
            manual_execution=parsed_modes["MANUAL_EXECUTION"],
            auto_execution=parsed_modes["AUTO_EXECUTION"],
            early_score_handoff_seconds=early_score_handoff_seconds,
            solana_rpc_url=_default_value(
                values,
                "SOLANA_RPC_URL",
                "https://api.mainnet.solana.com",
            ),
            helius_rpc_url=_optional_value(values, "HELIUS_RPC_URL"),
            helius_api_key=_optional_value(values, "HELIUS_API_KEY"),
            helius_stream_url=_first_optional_value(
                values,
                ("HELIUS_WEBSOCKET_URL", "MEMERADAR_SOLANA_STREAM_URL", "SOLANA_STREAM_URL"),
            ),
            solana_stream_url=stream_url,
            solana_backfill_url=backfill_url,
            dexscreener_api_url=dexscreener_url,
            dexscreener_api_key=_optional_value(values, "DEXSCREENER_API_KEY"),
            market_data_provider=_provider_choice(
                values,
                "MARKET_DATA_PROVIDER",
                "dexscreener",
                frozenset({"birdeye", "dexscreener"}),
            ),
            birdeye_api_url=_optional_value(values, "BIRDEYE_API_URL"),
            birdeye_api_key=_optional_value(values, "BIRDEYE_API_KEY"),
            paper_quote_provider=_provider_choice(
                values,
                "PAPER_QUOTE_PROVIDER",
                "dexscreener",
                frozenset({"custom", "dexscreener", "birdeye"}),
            ),
            paper_quote_url=_first_optional_value(
                values,
                ("MEMERADAR_PAPER_QUOTE_URL", "JUPITER_QUOTE_URL", "JUPITER_API_BASE_URL"),
            ),
            paper_quote_api_key=_first_optional_value(
                values,
                ("MEMERADAR_PAPER_QUOTE_API_KEY", "JUPITER_API_KEY"),
            ),
            rugcheck_api_url=_optional_value(values, "RUGCHECK_API_URL"),
            rugcheck_api_key=_optional_value(values, "RUGCHECK_API_KEY"),
            wallet_intelligence_provider=_provider_choice(
                values,
                "WALLET_INTELLIGENCE_PROVIDER",
                "local",
                frozenset({"external", "local"}),
            ),
            external_wallet_api_url=_optional_value(values, "EXTERNAL_WALLET_API_URL"),
            external_wallet_api_key=_optional_value(values, "EXTERNAL_WALLET_API_KEY"),
            external_wallet_stream_url=_optional_value(values, "EXTERNAL_WALLET_STREAM_URL"),
            social_metadata_provider=_provider_choice(
                values,
                "SOCIAL_METADATA_PROVIDER",
                "dexscreener",
                frozenset({"dexscreener", "disabled"}),
            ),
            social_api_url=_optional_value(values, "SOCIAL_API_URL"),
            social_api_key=_optional_value(values, "SOCIAL_API_KEY"),
            narrative_provider=configured_narrative_provider,
            narrative_api_url=legacy_narrative_url or "http://host.docker.internal:11434",
            narrative_api_key=legacy_narrative_key,
            narrative_model=_optional_value(values, "NARRATIVE_MODEL"),
            enabled_chains=enabled_chains,
            bnb_rpc_url=_optional_value(values, "BNB_RPC_URL"),
            bnb_rpc_fallback_url=_optional_value(values, "BNB_RPC_FALLBACK_URL"),
            bnb_chain_id=bnb_chain_id,
            robinhood_rpc_url=_default_value(
                values,
                "ROBINHOOD_RPC_URL",
                "https://rpc.mainnet.chain.robinhood.com",
            ),
            robinhood_rpc_fallback_url=_optional_value(values, "ROBINHOOD_RPC_FALLBACK_URL"),
            robinhood_chain_id=robinhood_chain_id,
            robinhood_sequencer_feed_url=_default_value(
                values,
                "ROBINHOOD_SEQUENCER_FEED_URL",
                "wss://feed.mainnet.chain.robinhood.com",
            ),
            robinhood_blockscout_api_url=_optional_value(values, "ROBINHOOD_BLOCKSCOUT_API_URL"),
            x_provider_enabled=_parse_bool(
                "X_PROVIDER_ENABLED", values.get("X_PROVIDER_ENABLED", "false")
            ),
            x_provider_api_key=_optional_value(values, "X_PROVIDER_API_KEY"),
            x_provider_bearer_token=_optional_value(values, "X_PROVIDER_BEARER_TOKEN"),
            website_url=_optional_value(values, "WEBSITE_URL"),
            website_name=_optional_value(values, "WEBSITE_NAME"),
        )
