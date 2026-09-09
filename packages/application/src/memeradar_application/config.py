"""Validated runtime configuration with protected operating-mode defaults."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})
SUPPORTED_CHAINS = ("solana", "bnb", "robinhood")


@dataclass(frozen=True, slots=True)
class RuntimeSettingSpec:
    """One canonical, provider-neutral description of an editable setting."""

    key: str
    category: str
    type: str
    mode: str
    attr: str | None = None
    legacy_group: str = "security"
    legacy_key: str | None = None
    default: object = None
    secret: bool = False
    protected: bool = False
    decision_affecting: bool = False
    allowed_values: tuple[str, ...] | None = None
    minimum: int | float | None = None
    maximum: int | float | None = None
    description: str = ""

    @property
    def mutable(self) -> bool:
        return self.mode in {"HOT_APPLY", "RESTART_REQUIRED"}

    @property
    def restart_required(self) -> bool:
        return self.mode == "RESTART_REQUIRED"


class RuntimeSettingValidationError(ValueError):
    """Raised when a runtime setting patch is invalid or unsafe."""


def _spec(
    key: str,
    category: str,
    type_: str,
    mode: str,
    *,
    attr: str | None = None,
    group: str = "security",
    legacy_key: str | None = None,
    default: object = None,
    secret: bool = False,
    protected: bool = False,
    decision_affecting: bool = False,
    allowed: tuple[str, ...] | None = None,
    minimum: int | float | None = None,
    maximum: int | float | None = None,
    description: str = "",
) -> RuntimeSettingSpec:
    return RuntimeSettingSpec(
        key=key,
        category=category,
        type=type_,
        mode=mode,
        attr=attr or key,
        legacy_group=group,
        legacy_key=legacy_key or key,
        default=default,
        secret=secret,
        protected=protected,
        decision_affecting=decision_affecting,
        allowed_values=allowed,
        minimum=minimum,
        maximum=maximum,
        description=description,
    )


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


RUNTIME_SETTING_SPECS: tuple[RuntimeSettingSpec, ...] = (
    _spec(
        "app_env",
        "general/runtime",
        "string",
        "IMMUTABLE",
        description="Application environment name.",
    ),
    _spec(
        "log_level",
        "general/runtime",
        "string",
        "RESTART_REQUIRED",
        allowed=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        description="Application log level.",
    ),
    _spec("api_host", "general/runtime", "string", "IMMUTABLE", description="API bind host."),
    _spec(
        "api_port",
        "general/runtime",
        "integer",
        "IMMUTABLE",
        minimum=1,
        maximum=65535,
        description="API bind port.",
    ),
    _spec(
        "worker_poll_interval_seconds",
        "general/runtime",
        "number",
        "RESTART_REQUIRED",
        minimum=0.1,
        maximum=3600.0,
        description="Worker polling interval in seconds.",
    ),
    _spec(
        "enabled_chains",
        "general/runtime",
        "string_list",
        "RESTART_REQUIRED",
        allowed=SUPPORTED_CHAINS,
        description="Enabled analysis chains.",
    ),
    _spec(
        "early_score_handoff_seconds",
        "decision/research",
        "integer",
        "RESTART_REQUIRED",
        minimum=1,
        maximum=86400,
        decision_affecting=True,
        description="Early-score handoff age in seconds.",
    ),
    _spec(
        "readiness_timeout_seconds",
        "general/runtime",
        "number",
        "RESTART_REQUIRED",
        legacy_key="readiness_timeout_seconds",
        default=0.25,
        minimum=0.01,
        maximum=10.0,
        description="Dependency readiness probe timeout.",
    ),
    _spec(
        "database_url",
        "general/runtime",
        "secret",
        "RESTART_REQUIRED",
        secret=True,
        description="Database connection URL.",
    ),
    _spec(
        "redis_url",
        "general/runtime",
        "secret",
        "RESTART_REQUIRED",
        secret=True,
        description="Redis connection URL.",
    ),
    _spec(
        "require_database_for_readiness",
        "general/runtime",
        "boolean",
        "RESTART_REQUIRED",
        legacy_key="database_required_for_readiness",
        default=False,
        description="Require the database for readiness.",
    ),
    _spec(
        "require_redis_for_readiness",
        "general/runtime",
        "boolean",
        "RESTART_REQUIRED",
        legacy_key="redis_required_for_readiness",
        default=False,
        description="Require Redis for readiness.",
    ),
    _spec(
        "analysis_only",
        "general/runtime",
        "boolean",
        "PROTECTED",
        protected=True,
        description="Analysis-only safety mode.",
    ),
    _spec(
        "paper_trading",
        "general/runtime",
        "boolean",
        "PROTECTED",
        protected=True,
        description="Paper-trading safety mode.",
    ),
    _spec(
        "manual_execution",
        "general/runtime",
        "boolean",
        "PROTECTED",
        protected=True,
        description="Manual execution safety mode.",
    ),
    _spec(
        "auto_execution",
        "general/runtime",
        "boolean",
        "PROTECTED",
        protected=True,
        description="Automatic execution safety mode.",
    ),
    _spec(
        "viewer_api_token",
        "general/runtime",
        "secret",
        "RESTART_REQUIRED",
        legacy_key="viewer_token",
        secret=True,
        description="Viewer control credential.",
    ),
    _spec(
        "operator_api_token",
        "general/runtime",
        "secret",
        "RESTART_REQUIRED",
        legacy_key="operator_token",
        secret=True,
        description="Operator control credential.",
    ),
    _spec(
        "admin_api_token",
        "general/runtime",
        "secret",
        "RESTART_REQUIRED",
        legacy_key="admin_token",
        secret=True,
        description="Admin control credential.",
    ),
    _spec(
        "execution_api_token",
        "general/runtime",
        "secret",
        "PROTECTED",
        legacy_key="execution_token",
        secret=True,
        protected=True,
        description="Execution credential; execution remains locked.",
    ),
    _spec(
        "solana_rpc_url",
        "solana",
        "string",
        "RESTART_REQUIRED",
        group="chains",
        default="https://api.mainnet.solana.com",
        description="Solana JSON-RPC endpoint.",
    ),
    _spec(
        "solana_stream_url",
        "solana",
        "string",
        "RESTART_REQUIRED",
        group="chains",
        description="Solana stream endpoint.",
    ),
    _spec(
        "solana_backfill_url",
        "solana",
        "string",
        "RESTART_REQUIRED",
        group="chains",
        description="Solana backfill endpoint.",
    ),
    _spec(
        "helius_rpc_url",
        "helius",
        "string",
        "RESTART_REQUIRED",
        group="providers",
        description="Helius RPC endpoint.",
    ),
    _spec(
        "helius_api_key",
        "helius",
        "secret",
        "RESTART_REQUIRED",
        group="providers",
        secret=True,
        description="Helius API key.",
    ),
    _spec(
        "helius_stream_url",
        "helius",
        "string",
        "RESTART_REQUIRED",
        group="providers",
        description="Helius stream endpoint.",
    ),
    _spec(
        "dexscreener_api_url",
        "dexscreener",
        "string",
        "RESTART_REQUIRED",
        group="providers",
        default="https://api.dexscreener.com",
        description="DexScreener API endpoint.",
    ),
    _spec(
        "dexscreener_api_key",
        "dexscreener",
        "secret",
        "RESTART_REQUIRED",
        group="providers",
        secret=True,
        description="DexScreener API key.",
    ),
    _spec(
        "market_data_provider",
        "market data",
        "select",
        "RESTART_REQUIRED",
        group="providers",
        default="dexscreener",
        allowed=("birdeye", "dexscreener"),
        description="Primary market-data provider.",
    ),
    _spec(
        "paper_quote_provider",
        "market data",
        "select",
        "RESTART_REQUIRED",
        group="providers",
        default="dexscreener",
        allowed=("custom", "dexscreener", "birdeye"),
        description="Paper quote provider.",
    ),
    _spec(
        "paper_quote_url",
        "market data",
        "string",
        "RESTART_REQUIRED",
        group="providers",
        description="Paper quote endpoint.",
    ),
    _spec(
        "paper_quote_api_key",
        "market data",
        "secret",
        "RESTART_REQUIRED",
        group="providers",
        secret=True,
        description="Paper quote credential.",
    ),
    _spec(
        "birdeye_api_url",
        "birdeye",
        "string",
        "RESTART_REQUIRED",
        group="providers",
        description="Birdeye API endpoint.",
    ),
    _spec(
        "birdeye_api_key",
        "birdeye",
        "secret",
        "RESTART_REQUIRED",
        group="providers",
        secret=True,
        description="Birdeye API key.",
    ),
    _spec(
        "rugcheck_api_url",
        "rugcheck/security",
        "string",
        "RESTART_REQUIRED",
        group="providers",
        description="RugCheck API endpoint.",
    ),
    _spec(
        "rugcheck_api_key",
        "rugcheck/security",
        "secret",
        "RESTART_REQUIRED",
        group="providers",
        secret=True,
        description="RugCheck API key.",
    ),
    _spec(
        "bnb_rpc_url",
        "bnb",
        "string",
        "RESTART_REQUIRED",
        group="chains",
        description="BNB Chain JSON-RPC endpoint.",
    ),
    _spec(
        "bnb_rpc_fallback_url",
        "bnb",
        "string",
        "RESTART_REQUIRED",
        group="chains",
        description="BNB Chain fallback RPC endpoint.",
    ),
    _spec(
        "bnb_chain_id",
        "bnb",
        "integer",
        "IMMUTABLE",
        group="chains",
        default=56,
        minimum=1,
        maximum=2**64 - 1,
        description="BNB Chain ID.",
    ),
    _spec(
        "robinhood_rpc_url",
        "robinhood",
        "string",
        "RESTART_REQUIRED",
        group="chains",
        default="https://rpc.mainnet.chain.robinhood.com",
        description="Robinhood Chain JSON-RPC endpoint.",
    ),
    _spec(
        "robinhood_rpc_fallback_url",
        "robinhood",
        "string",
        "RESTART_REQUIRED",
        group="chains",
        description="Robinhood Chain fallback RPC endpoint.",
    ),
    _spec(
        "robinhood_chain_id",
        "robinhood",
        "integer",
        "IMMUTABLE",
        group="chains",
        default=4663,
        minimum=1,
        maximum=2**64 - 1,
        description="Robinhood Chain ID is fixed at 4663.",
    ),
    _spec(
        "robinhood_sequencer_feed_url",
        "robinhood",
        "string",
        "RESTART_REQUIRED",
        group="chains",
        default="wss://feed.mainnet.chain.robinhood.com",
        description="Robinhood sequencer feed endpoint.",
    ),
    _spec(
        "robinhood_blockscout_api_url",
        "robinhood",
        "string",
        "RESTART_REQUIRED",
        group="chains",
        description="Robinhood Blockscout endpoint.",
    ),
    _spec(
        "wallet_intelligence_provider",
        "external wallet intelligence/stream",
        "select",
        "RESTART_REQUIRED",
        group="wallet",
        legacy_key="intelligence_provider",
        default="local",
        allowed=("external", "local"),
        description="External wallet intelligence provider.",
    ),
    _spec(
        "external_wallet_api_url",
        "external wallet intelligence/stream",
        "string",
        "RESTART_REQUIRED",
        group="wallet",
        legacy_key="external_api_url",
        description="External wallet intelligence endpoint.",
    ),
    _spec(
        "external_wallet_api_key",
        "external wallet intelligence/stream",
        "secret",
        "RESTART_REQUIRED",
        group="wallet",
        legacy_key="external_api_key",
        secret=True,
        description="External wallet intelligence credential.",
    ),
    _spec(
        "external_wallet_stream_url",
        "external wallet intelligence/stream",
        "string",
        "RESTART_REQUIRED",
        group="wallet",
        legacy_key="external_stream_url",
        description="External wallet stream endpoint.",
    ),
    _spec(
        "x_provider_enabled",
        "x",
        "boolean",
        "RESTART_REQUIRED",
        group="x",
        legacy_key="enabled",
        default=False,
        description="Enable configured X/social ingestion.",
    ),
    _spec(
        "x_provider_api_key",
        "x",
        "secret",
        "RESTART_REQUIRED",
        group="x",
        legacy_key="api_key",
        secret=True,
        description="X provider API key.",
    ),
    _spec(
        "x_provider_bearer_token",
        "x",
        "secret",
        "RESTART_REQUIRED",
        group="x",
        legacy_key="bearer_token",
        secret=True,
        description="X provider bearer token.",
    ),
    _spec(
        "telegram_api_url",
        "telegram notification",
        "string",
        "RESTART_REQUIRED",
        group="telegram",
        legacy_key="api_url",
        default="https://api.telegram.org",
        description="Telegram API endpoint.",
    ),
    _spec(
        "telegram_bot_token",
        "telegram notification",
        "secret",
        "RESTART_REQUIRED",
        group="telegram",
        legacy_key="bot_token",
        secret=True,
        description="Telegram bot token.",
    ),
    _spec(
        "telegram_bot_username",
        "telegram notification",
        "string",
        "RESTART_REQUIRED",
        group="telegram",
        legacy_key="bot_username",
        description="Telegram bot username.",
    ),
    _spec(
        "telegram_chat_id",
        "telegram notification",
        "secret",
        "RESTART_REQUIRED",
        group="telegram",
        legacy_key="chat_id",
        secret=True,
        description="Telegram notification chat identifier.",
    ),
    _spec(
        "social_api_url",
        "telegram/social ingestion",
        "string",
        "RESTART_REQUIRED",
        group="social",
        legacy_key="api_url",
        description="Social ingestion endpoint.",
    ),
    _spec(
        "social_api_key",
        "telegram/social ingestion",
        "secret",
        "RESTART_REQUIRED",
        group="social",
        legacy_key="api_key",
        secret=True,
        description="Social ingestion credential.",
    ),
    _spec(
        "social_metadata_provider",
        "social/website metadata",
        "select",
        "RESTART_REQUIRED",
        group="social",
        legacy_key="metadata_provider",
        allowed=("dexscreener", "disabled"),
        description="Social metadata provider.",
    ),
    _spec(
        "website_url",
        "social/website metadata",
        "string",
        "RESTART_REQUIRED",
        group="website",
        legacy_key="url",
        description="Project website URL.",
    ),
    _spec(
        "website_name",
        "social/website metadata",
        "string",
        "RESTART_REQUIRED",
        group="website",
        legacy_key="name",
        description="Project website display name.",
    ),
    _spec(
        "narrative_provider",
        "narrative/LLM",
        "select",
        "RESTART_REQUIRED",
        group="llm",
        legacy_key="provider",
        allowed=("disabled", "external", "ollama"),
        description="Narrative provider.",
    ),
    _spec(
        "narrative_api_url",
        "narrative/LLM",
        "string",
        "RESTART_REQUIRED",
        group="llm",
        legacy_key="api_url",
        description="Narrative provider endpoint.",
    ),
    _spec(
        "narrative_api_key",
        "narrative/LLM",
        "secret",
        "RESTART_REQUIRED",
        group="llm",
        legacy_key="api_key",
        secret=True,
        description="Narrative provider credential.",
    ),
    _spec(
        "narrative_model",
        "narrative/LLM",
        "string",
        "RESTART_REQUIRED",
        group="llm",
        legacy_key="model",
        description="Narrative model name.",
    ),
    _spec(
        "alert_max_messages_per_window",
        "alerts",
        "integer",
        "HOT_APPLY",
        group="telegram",
        attr="alert_max_messages_per_window",
        default=20,
        minimum=1,
        maximum=1000,
        description="Maximum alert messages allowed per rate-limit window.",
    ),
    _spec(
        "alert_rate_limit_window_seconds",
        "alerts",
        "number",
        "HOT_APPLY",
        group="telegram",
        attr="alert_rate_limit_window_seconds",
        default=60.0,
        minimum=1.0,
        maximum=86400.0,
        description="Alert rate-limit window in seconds.",
    ),
    _spec(
        "decision_watch_threshold",
        "decision/research",
        "number",
        "HOT_APPLY",
        default=40.0,
        minimum=0.0,
        maximum=100.0,
        decision_affecting=True,
        description="Minimum score for WATCH.",
    ),
    _spec(
        "decision_strong_setup_threshold",
        "decision/research",
        "number",
        "HOT_APPLY",
        default=75.0,
        minimum=0.0,
        maximum=100.0,
        decision_affecting=True,
        description="Minimum score for STRONG_SETUP.",
    ),
    _spec(
        "decision_entry_ready_threshold",
        "decision/research",
        "number",
        "HOT_APPLY",
        default=85.0,
        minimum=0.0,
        maximum=100.0,
        decision_affecting=True,
        description="Minimum score for ENTRY_READY.",
    ),
    _spec(
        "decision_minimum_confidence",
        "decision/research",
        "number",
        "HOT_APPLY",
        default=0.60,
        minimum=0.0,
        maximum=1.0,
        decision_affecting=True,
        description="Minimum decision confidence.",
    ),
)

RUNTIME_SETTING_SPEC_BY_KEY = {item.key: item for item in RUNTIME_SETTING_SPECS}


def runtime_setting_spec(key: str) -> RuntimeSettingSpec:
    try:
        return RUNTIME_SETTING_SPEC_BY_KEY[key]
    except KeyError as exc:
        raise RuntimeSettingValidationError(f"unknown runtime setting: {key}") from exc


def runtime_setting_value(
    settings: Settings,
    spec: RuntimeSettingSpec,
    *,
    overrides: Mapping[str, object] | None = None,
    control_values: Mapping[str, object] | None = None,
) -> object:
    runtime_overrides = {} if overrides is None else overrides
    configured_values = {} if control_values is None else control_values
    if spec.key in runtime_overrides:
        return runtime_overrides[spec.key]
    if spec.key in configured_values:
        return configured_values[spec.key]
    if spec.attr is None:
        return spec.default
    value = getattr(settings, spec.attr, spec.default)
    return spec.default if value is None and spec.default is not None else value


def validate_runtime_setting(spec: RuntimeSettingSpec, value: object) -> object:
    if spec.protected:
        raise RuntimeSettingValidationError(f"{spec.key} is protected")
    if not spec.mutable:
        raise RuntimeSettingValidationError(f"{spec.key} is immutable")
    if value is None:
        return None
    if spec.type == "boolean":
        if not isinstance(value, bool):
            raise RuntimeSettingValidationError(f"{spec.key} must be a boolean")
        return value
    if spec.type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise RuntimeSettingValidationError(f"{spec.key} must be an integer")
        if (
            spec.minimum is not None
            and value < spec.minimum
            or spec.maximum is not None
            and value > spec.maximum
        ):
            raise RuntimeSettingValidationError(f"{spec.key} is outside its allowed range")
        return value
    if spec.type == "number":
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise RuntimeSettingValidationError(f"{spec.key} must be a number")
        numeric = float(value)
        if (
            not math.isfinite(numeric)
            or spec.minimum is not None
            and numeric < spec.minimum
            or spec.maximum is not None
            and numeric > spec.maximum
        ):
            raise RuntimeSettingValidationError(f"{spec.key} is outside its allowed range")
        return numeric
    if spec.type == "string_list":
        if not isinstance(value, str):
            raise RuntimeSettingValidationError(f"{spec.key} must be a comma-separated list")
        values = tuple(item.strip().lower() for item in value.split(",") if item.strip())
        if (
            not values
            or len(values) != len(set(values))
            or spec.allowed_values is None
            or any(item not in spec.allowed_values for item in values)
        ):
            raise RuntimeSettingValidationError(
                f"{spec.key} contains unsupported or duplicate values"
            )
        return ",".join(values)
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise RuntimeSettingValidationError(f"{spec.key} must be a bounded string")
    normalized = value.strip()
    if spec.allowed_values is None:
        return normalized
    canonical = next(
        (allowed for allowed in spec.allowed_values if allowed.lower() == normalized.lower()),
        None,
    )
    if canonical is None:
        raise RuntimeSettingValidationError(f"{spec.key} has an unsupported value")
    return canonical


def runtime_configured_state(value: object) -> str:
    return "CONFIGURED" if value is not None and value != "" else "NOT_CONFIGURED"


__all__ = [
    "RUNTIME_SETTING_SPECS",
    "RUNTIME_SETTING_SPEC_BY_KEY",
    "RuntimeSettingSpec",
    "RuntimeSettingValidationError",
    "Settings",
    "SUPPORTED_CHAINS",
    "runtime_configured_state",
    "runtime_setting_spec",
    "runtime_setting_value",
    "validate_runtime_setting",
]
