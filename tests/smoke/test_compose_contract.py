from pathlib import Path

import yaml
from tests.route_helpers import app_routes

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = ROOT / "infra" / "compose" / "docker-compose.yml"


def test_compose_defines_the_local_runtime_topology():
    compose = yaml.safe_load(COMPOSE_PATH.read_text())

    assert set(compose["services"]) == {"api", "worker", "web", "postgres", "redis"}
    assert compose["services"]["api"]["depends_on"] == {
        "postgres": {"condition": "service_healthy"},
        "redis": {"condition": "service_healthy"},
    }
    assert compose["services"]["worker"]["depends_on"] == {
        "postgres": {"condition": "service_healthy"},
        "redis": {"condition": "service_healthy"},
    }


def test_compose_has_dependency_health_checks_and_safe_modes():
    services = yaml.safe_load(COMPOSE_PATH.read_text())["services"]

    assert services["postgres"]["healthcheck"]["test"][0] == "CMD-SHELL"
    assert services["redis"]["healthcheck"]["test"][0] == "CMD"
    for service_name in ("api", "worker"):
        environment = services[service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_dockerfiles_keep_runtime_entrypoints_explicit():
    api_dockerfile = (ROOT / "infra" / "docker" / "api.Dockerfile").read_text()
    worker_dockerfile = (ROOT / "infra" / "docker" / "worker.Dockerfile").read_text()
    web_dockerfile = (ROOT / "infra" / "docker" / "web.Dockerfile").read_text()

    assert '"uvicorn", "memeradar_api.main:app"' in api_dockerfile
    assert "/app/packages/telemetry/src" in api_dockerfile
    assert "COPY packages/telemetry/src ./packages/telemetry/src" in api_dockerfile
    assert "/app/packages/persistence/src" in api_dockerfile
    assert "COPY packages/persistence/src ./packages/persistence/src" in api_dockerfile
    assert "/app/packages/providers/src" in api_dockerfile
    assert "COPY packages/providers/src ./packages/providers/src" in api_dockerfile
    assert '"python", "-m", "memeradar_worker"' in worker_dockerfile
    assert "/app/packages/persistence/src" in worker_dockerfile
    assert "COPY packages/persistence/src ./packages/persistence/src" in worker_dockerfile
    assert "/app/packages/telemetry/src" in worker_dockerfile
    assert "COPY packages/telemetry/src ./packages/telemetry/src" in worker_dockerfile
    assert "/app/packages/providers/src" in worker_dockerfile
    assert "COPY packages/providers/src ./packages/providers/src" in worker_dockerfile
    assert "RUN npm run build" in web_dockerfile
    assert 'ENV NODE_ENV=production' in web_dockerfile
    assert 'CMD ["node", "server.js"]' in web_dockerfile


def test_helius_read_layer_and_doctor_are_explicit_and_keyless():
    from memeradar_providers.helius import HeliusRpcAdapter
    from memeradar_providers.helius_stream import (
        HeliusObservationNormalizer,
        HeliusStreamConsumer,
    )

    assert HeliusRpcAdapter.provider_name == "helius"
    assert HeliusObservationNormalizer.provider_name == "helius"
    assert HeliusStreamConsumer
    makefile = (ROOT / "Makefile").read_text()
    env_example = (ROOT / ".env.example").read_text()
    assert "provider-doctor:" in makefile
    assert "HELIUS_RPC_URL=" in env_example
    assert "HELIUS_API_KEY=" in env_example
    assert "ANALYSIS_ONLY=true" in env_example
    assert "PAPER_TRADING=true" in env_example
    assert "MANUAL_EXECUTION=false" in env_example
    assert "AUTO_EXECUTION=false" in env_example


def test_token_security_and_rugcheck_seam_are_explicit_and_safe():
    from memeradar_application.token_security import TokenSecurityEvaluator, TokenSecurityPolicy
    from memeradar_providers.rugcheck import RugCheckRestAdapter

    assert TokenSecurityEvaluator
    assert TokenSecurityPolicy().risk_version == "token-security-v1"
    assert RugCheckRestAdapter.provider_name == "rugcheck"
    makefile = (ROOT / "Makefile").read_text()
    env_example = (ROOT / ".env.example").read_text()
    assert "rugcheck-doctor:" in makefile
    assert "RUGCHECK_API_URL=" in env_example
    assert "RUGCHECK_API_KEY=" in env_example
    assert "ANALYSIS_ONLY=true" in env_example
    assert "PAPER_TRADING=true" in env_example
    assert "MANUAL_EXECUTION=false" in env_example
    assert "AUTO_EXECUTION=false" in env_example


def test_holder_graph_replay_seam_is_packaged_and_safe():
    from memeradar_application.holder_graph import HolderGraphAnalyzer, HolderGraphPolicy

    assert HolderGraphAnalyzer
    assert HolderGraphPolicy().max_graph_depth == 1
    assert (ROOT / "fixtures" / "providers" / "wallet_graph" / "holder_data.json").is_file()
    assert (ROOT / "fixtures" / "providers" / "wallet_graph" / "transfers.json").is_file()
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_flow_analysis_replay_seam_is_packaged_and_safe():
    from memeradar_application.flow_analysis import FlowAnalysisPolicy, FlowAnalyzer

    assert FlowAnalyzer
    assert FlowAnalysisPolicy().maximum_price_impact_bps == 100
    flow_fixture_dir = ROOT / "fixtures" / "providers" / "flow_analysis"
    assert (flow_fixture_dir / "market_safe.json").is_file()
    assert (flow_fixture_dir / "market_suspicious.json").is_file()
    assert (flow_fixture_dir / "trades_safe.json").is_file()
    assert (flow_fixture_dir / "trades_suspicious.json").is_file()
    assert (flow_fixture_dir / "quotes.json").is_file()
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_wallet_tracking_replay_seam_is_packaged_and_safe():
    from memeradar_application.wallet_tracking import (
        TrackedWalletRegistry,
        WalletTrackingAnalyzer,
        WalletTrackingPolicy,
    )

    assert WalletTrackingAnalyzer
    assert WalletTrackingPolicy().max_activities == 5000
    assert TrackedWalletRegistry
    wallet_fixture_dir = ROOT / "fixtures" / "providers" / "wallet_tracking"
    assert (wallet_fixture_dir / "registry.json").is_file()
    assert (wallet_fixture_dir / "activities.json").is_file()
    assert (wallet_fixture_dir / "risk.json").is_file()
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_wallet_scoring_replay_seam_is_packaged_and_safe():
    from memeradar_application.wallet_scoring import (
        SmartWalletScore,
        SmartWalletScorer,
        SmartWalletScoringPolicy,
    )

    assert SmartWalletScorer
    assert SmartWalletScore
    assert SmartWalletScoringPolicy().version == "smart-wallet-v1"
    score_fixture_dir = ROOT / "fixtures" / "providers" / "wallet_scoring"
    assert (score_fixture_dir / "snapshots.json").is_file()
    assert (score_fixture_dir / "penalties.json").is_file()
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_external_wallet_intelligence_replay_seam_is_packaged_and_safe():
    from memeradar_application.external_wallet import (
        EXTERNAL_WALLET_VERSION,
        ExternalWalletCrossValidationPolicy,
        ExternalWalletIntelligencePort,
        ExternalWalletReconciler,
    )
    from memeradar_providers.external_wallet import FixtureExternalWalletIntelligenceAdapter

    assert EXTERNAL_WALLET_VERSION == "external-wallet-v1"
    assert ExternalWalletCrossValidationPolicy().version
    assert ExternalWalletIntelligencePort
    assert ExternalWalletReconciler
    assert FixtureExternalWalletIntelligenceAdapter.provider_name == "fixture.external_wallet"
    fixture_dir = ROOT / "fixtures" / "providers" / "external_wallet"
    assert (fixture_dir / "README.md").is_file()
    assert (fixture_dir / "replay.json").is_file()
    makefile = (ROOT / "Makefile").read_text()
    env_example = (ROOT / ".env.example").read_text()
    assert "external-wallet-doctor:" in makefile
    assert "EXTERNAL_WALLET_API_URL=" in env_example
    assert "EXTERNAL_WALLET_API_KEY=" in env_example
    assert "EXTERNAL_WALLET_STREAM_URL=" in env_example
    assert "X_PROVIDER_ENABLED=false" in env_example
    assert "TELEGRAM_BOT_USERNAME=" in env_example
    compose = yaml.safe_load(COMPOSE_PATH.read_text())["services"]
    for service_name in ("api", "worker"):
        environment = compose[service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_confluence_replay_seam_is_packaged_and_safe():
    from memeradar_application.confluence import (
        ConfluenceAnalyzer,
        ConfluencePolicy,
        SmartMoneyEventType,
        TokenSmartMoneyScore,
    )

    assert ConfluenceAnalyzer
    assert ConfluencePolicy().version == "smart-money-confluence-v1"
    assert SmartMoneyEventType.CONFLUENCE.value == "CONFLUENCE"
    assert TokenSmartMoneyScore
    confluence_fixture_dir = ROOT / "fixtures" / "providers" / "confluence"
    assert (confluence_fixture_dir / "README.md").is_file()
    assert (confluence_fixture_dir / "replay.json").is_file()
    assert (confluence_fixture_dir / "graph_stale.json").is_file()
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_social_provider_and_doctor_are_explicit_and_keyless():
    from memeradar_providers.social import (
        SOCIAL_PARSER_VERSION,
        SOCIAL_PROVIDER,
        SocialRestAdapter,
    )

    assert SocialRestAdapter.provider_name == SOCIAL_PROVIDER == "social"
    assert SOCIAL_PARSER_VERSION == "social-search-v1"
    social_fixture_dir = ROOT / "fixtures" / "providers" / "social"
    assert (social_fixture_dir / "README.md").is_file()
    assert (social_fixture_dir / "search.json").is_file()
    assert (social_fixture_dir / "health.json").is_file()
    makefile = (ROOT / "Makefile").read_text()
    env_example = (ROOT / ".env.example").read_text()
    assert "social-doctor:" in makefile
    assert "SOCIAL_API_URL=" in env_example
    assert "SOCIAL_API_KEY=" in env_example
    assert "ANALYSIS_ONLY=true" in env_example
    assert "PAPER_TRADING=true" in env_example
    assert "MANUAL_EXECUTION=false" in env_example
    assert "AUTO_EXECUTION=false" in env_example


def test_social_intelligence_replay_seam_is_packaged_and_safe():
    from memeradar_application.social_intelligence import (
        AuthorTrustScorer,
        SocialAuthorRegistry,
        SocialVelocityScorer,
    )

    assert AuthorTrustScorer
    assert SocialAuthorRegistry
    assert SocialVelocityScorer
    intelligence_fixture_dir = ROOT / "fixtures" / "providers" / "social_intelligence"
    assert (intelligence_fixture_dir / "README.md").is_file()
    assert (intelligence_fixture_dir / "replay.json").is_file()
    assert (intelligence_fixture_dir / "future_stale.json").is_file()
    source = (
        ROOT
        / "packages"
        / "application"
        / "src"
        / "memeradar_application"
        / "social_intelligence.py"
    ).read_text()
    assert "memeradar_providers" not in source
    assert "ANALYSIS_ONLY=true" in (ROOT / ".env.example").read_text()
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_call_performance_replay_seam_is_packaged_and_safe():
    from memeradar_application.call_performance import (
        CallPerformanceAnalyzer,
        CallPerformancePolicy,
        CallPerformanceSnapshot,
        SocialCall,
        SocialCallOutcome,
    )

    assert CallPerformanceAnalyzer
    assert CallPerformancePolicy().version == "call-performance-v1"
    assert CallPerformanceSnapshot
    assert SocialCall
    assert SocialCallOutcome
    performance_fixture_dir = ROOT / "fixtures" / "providers" / "call_performance"
    assert (performance_fixture_dir / "README.md").is_file()
    assert (performance_fixture_dir / "replay.json").is_file()
    source = (
        ROOT / "packages" / "application" / "src" / "memeradar_application" / "call_performance.py"
    ).read_text()
    assert "memeradar_providers" not in source
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_narrative_llm_seam_is_optional_strict_and_safe():
    from memeradar_application.narrative import NarrativeAnalyzer, NarrativeCache, NarrativePolicy
    from memeradar_application.provider_contracts import (
        NarrativeEvidence,
        NarrativeOrganicAssessment,
        NarrativeSentiment,
        NarrativeSnapshot,
    )
    from memeradar_providers.narrative import (
        FixtureNarrativeAdapter,
        NarrativeRestAdapter,
    )

    assert NarrativeAnalyzer
    assert NarrativeCache
    assert NarrativePolicy().version == "narrative-gateway-v1"
    assert NarrativeEvidence
    assert NarrativeOrganicAssessment.UNKNOWN.value == "UNKNOWN"
    assert NarrativeSentiment.UNKNOWN.value == "UNKNOWN"
    assert NarrativeSnapshot
    assert FixtureNarrativeAdapter.provider_name == "fixture-narrative"
    assert NarrativeRestAdapter.provider_name == "narrative"
    narrative_fixture_dir = ROOT / "fixtures" / "providers" / "narrative"
    assert (narrative_fixture_dir / "README.md").is_file()
    assert (narrative_fixture_dir / "valid.json").is_file()
    assert (narrative_fixture_dir / "malformed.json").is_file()
    assert (narrative_fixture_dir / "injection.json").is_file()
    source = (
        ROOT / "packages" / "application" / "src" / "memeradar_application" / "narrative.py"
    ).read_text()
    assert "memeradar_providers" not in source
    makefile = (ROOT / "Makefile").read_text()
    env_example = (ROOT / ".env.example").read_text()
    assert "narrative-doctor:" in makefile
    assert "NARRATIVE_API_URL=" in env_example
    assert "NARRATIVE_API_KEY=" in env_example
    assert "NARRATIVE_MODEL=" in env_example
    assert "ANALYSIS_ONLY=true" in env_example
    assert "PAPER_TRADING=true" in env_example
    assert "MANUAL_EXECUTION=false" in env_example
    assert "AUTO_EXECUTION=false" in env_example
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_birdeye_market_layer_and_doctor_are_explicit_and_keyless():
    from memeradar_providers.birdeye import (
        BIRDEYE_CHAIN,
        BirdeyeObservationResolver,
        BirdeyeRestAdapter,
    )
    from memeradar_providers.birdeye_stream import (
        BirdeyeDiscoveryFallback,
        BirdeyeListingNormalizer,
    )

    assert BIRDEYE_CHAIN == "solana"
    assert BirdeyeRestAdapter.provider_name == "birdeye"
    assert BirdeyeListingNormalizer.provider_name == "birdeye"
    assert BirdeyeDiscoveryFallback
    assert BirdeyeObservationResolver
    makefile = (ROOT / "Makefile").read_text()
    env_example = (ROOT / ".env.example").read_text()
    assert "birdeye-doctor:" in makefile
    assert "BIRDEYE_API_URL=" in env_example
    assert "BIRDEYE_API_KEY=" in env_example
    assert "ANALYSIS_ONLY=true" in env_example
    assert "PAPER_TRADING=true" in env_example
    assert "MANUAL_EXECUTION=false" in env_example
    assert "AUTO_EXECUTION=false" in env_example


def test_launchpad_dex_adapters_and_manual_submission_are_explicit_and_safe():
    from memeradar_api.main import create_app
    from memeradar_application.config import Settings
    from memeradar_providers.launchpad_dex import (
        CanonicalDuplicateDetector,
        MeteoraAdapter,
        PumpFunAdapter,
        PumpSwapAdapter,
        RaydiumAdapter,
    )

    assert PumpFunAdapter().provider_name == "pump.fun"
    assert PumpSwapAdapter().provider_name == "pumpswap"
    assert RaydiumAdapter().provider_name == "raydium"
    assert MeteoraAdapter().provider_name == "meteora"
    assert CanonicalDuplicateDetector
    route_paths = {route.path for route in app_routes(create_app(Settings.from_env({})))}
    assert "/v1/manual/mints" in route_paths
    env_example = (ROOT / ".env.example").read_text()
    assert "OPERATOR_API_TOKEN=" in env_example
    assert "ANALYSIS_ONLY=true" in env_example
    assert "PAPER_TRADING=true" in env_example
    assert "MANUAL_EXECUTION=false" in env_example
    assert "AUTO_EXECUTION=false" in env_example


def test_rich_protocol_lifecycle_replay_seam_is_packaged_and_safe():
    from memeradar_providers.launchpad_dex import (
        PROTOCOL_EVENT_SCHEMA_VERSION,
        RICH_LAUNCHPAD_PARSER_VERSION,
        ProtocolEventOrigin,
        ProtocolEventType,
    )
    from memeradar_providers.protocol_stream import (
        ProtocolEventStreamFallback,
        ProtocolStreamPolicy,
    )

    assert PROTOCOL_EVENT_SCHEMA_VERSION == 2
    assert RICH_LAUNCHPAD_PARSER_VERSION == "launchpad-dex-v2"
    assert ProtocolEventType.WHALE_TRADE.value == "whale_trade"
    assert ProtocolEventOrigin.DERIVED.value == "DERIVED"
    assert ProtocolEventStreamFallback
    assert ProtocolStreamPolicy().max_messages == 1000
    fixture_path = ROOT / "fixtures" / "providers" / "launchpad_dex" / "rich_pumpfun_replay.json"
    readme_path = ROOT / "fixtures" / "providers" / "launchpad_dex" / "README.md"
    assert fixture_path.is_file()
    assert readme_path.is_file()
    assert "schema v2" in readme_path.read_text(encoding="utf-8").lower()
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_correlation_replay_seam_is_packaged_provider_free_and_safe():
    from memeradar_application.correlation import (
        CORRELATION_VERSION,
        DEFAULT_CORRELATION_WINDOWS,
        CorrelationWindowBuilder,
        CorrelationWindowPolicy,
    )

    assert CorrelationWindowBuilder
    assert CorrelationWindowPolicy().version == CORRELATION_VERSION
    assert tuple(name for name, _ in DEFAULT_CORRELATION_WINDOWS) == (
        "5s",
        "15s",
        "30s",
        "60s",
        "1m",
        "5m",
        "15m",
    )
    correlation_fixture_dir = ROOT / "fixtures" / "providers" / "correlation"
    assert (correlation_fixture_dir / "README.md").is_file()
    assert (correlation_fixture_dir / "replay.json").is_file()
    source = (
        ROOT / "packages" / "application" / "src" / "memeradar_application" / "correlation.py"
    ).read_text(encoding="utf-8")
    assert "memeradar_providers" not in source
    assert "httpx" not in source
    assert "sign(" not in source.lower()
    assert "submit(" not in source.lower()
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_alpha_strategy_replay_seam_is_versioned_provider_free_and_safe():
    from memeradar_application.alpha_strategy import (
        ALPHA_SCORE_V1_VERSION,
        ALPHA_SCORE_V1_WEIGHTS,
        AlphaScoreV1Strategy,
        ReferenceStrategy,
        StrategyPolicy,
        StrategySnapshot,
    )

    assert AlphaScoreV1Strategy
    assert ReferenceStrategy
    assert StrategySnapshot
    assert StrategyPolicy().version == ALPHA_SCORE_V1_VERSION
    assert tuple(ALPHA_SCORE_V1_WEIGHTS) == (
        "SmartMoney",
        "OnChainSafety",
        "LiquidityQuality",
        "OrganicFlow",
        "SocialVelocity",
        "HolderQuality",
        "Momentum",
    )
    alpha_fixture_dir = ROOT / "fixtures" / "providers" / "alpha_strategy"
    assert (alpha_fixture_dir / "README.md").is_file()
    assert (alpha_fixture_dir / "replay.json").is_file()
    source = (
        ROOT / "packages" / "application" / "src" / "memeradar_application" / "alpha_strategy.py"
    ).read_text(encoding="utf-8")
    assert "memeradar_providers" not in source
    assert "memeradar_persistence" not in source
    assert "ExecutionPort" not in source
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_feature_window_replay_seam_is_versioned_provider_free_and_safe():
    from memeradar_application.feature_windows import (
        FEATURE_WINDOW_NAMES,
        FEATURE_WINDOWS_VERSION,
        FeatureSnapshotAggregator,
        FeatureWindowAggregator,
        FeatureWindowPolicy,
    )

    assert FeatureWindowAggregator
    assert FeatureSnapshotAggregator is FeatureWindowAggregator
    assert FeatureWindowPolicy().version == FEATURE_WINDOWS_VERSION
    assert FEATURE_WINDOW_NAMES == ("1m", "5m", "15m")
    fixture_dir = ROOT / "fixtures" / "providers" / "feature_windows"
    assert (fixture_dir / "README.md").is_file()
    assert (fixture_dir / "replay.json").is_file()
    source = (
        ROOT / "packages" / "application" / "src" / "memeradar_application" / "feature_windows.py"
    ).read_text(encoding="utf-8")
    assert "memeradar_providers" not in source
    assert "memeradar_persistence" not in source
    assert "sign(" not in source.lower()
    assert "submit(" not in source.lower()
    compose = yaml.safe_load(COMPOSE_PATH.read_text())["services"]
    for service_name in ("api", "worker"):
        environment = compose[service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_alpha_score_recomputation_seam_is_provider_free_and_safe():
    from memeradar_application.score_recomputation import (
        AlphaScoreRecomputer,
        ScoreRecomputationService,
    )

    assert AlphaScoreRecomputer
    assert ScoreRecomputationService
    fixture_dir = ROOT / "fixtures" / "providers" / "alpha_score"
    assert (fixture_dir / "README.md").is_file()
    assert (fixture_dir / "replay.json").is_file()
    source = (
        ROOT
        / "packages"
        / "application"
        / "src"
        / "memeradar_application"
        / "score_recomputation.py"
    ).read_text(encoding="utf-8")
    assert "memeradar_providers" not in source
    assert "memeradar_persistence" not in source
    assert "sign(" not in source.lower()
    assert "submit(" not in source.lower()
    compose = yaml.safe_load(COMPOSE_PATH.read_text())["services"]
    for service_name in ("api", "worker"):
        environment = compose[service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_decision_state_machine_and_timeline_are_provider_free_and_safe():
    from memeradar_application.decision_engine import (
        DECISION_POLICY_VERSION,
        TIMELINE_VERSION,
        DecisionEngine,
        DecisionPolicy,
        EvidenceTimelineProjector,
    )

    assert DecisionEngine
    assert EvidenceTimelineProjector
    assert DecisionPolicy().version == DECISION_POLICY_VERSION
    assert EvidenceTimelineProjector.version == TIMELINE_VERSION
    fixture_dir = ROOT / "fixtures" / "providers" / "decision"
    assert (fixture_dir / "README.md").is_file()
    assert (fixture_dir / "replay.json").is_file()
    source = (
        ROOT / "packages" / "application" / "src" / "memeradar_application" / "decision_engine.py"
    ).read_text(encoding="utf-8")
    assert "memeradar_providers" not in source
    assert "memeradar_persistence" not in source
    assert "sign(" not in source.lower()
    assert "submit(" not in source.lower()
    compose = yaml.safe_load(COMPOSE_PATH.read_text())["services"]
    for service_name in ("api", "worker"):
        environment = compose[service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_alert_pipeline_and_telegram_adapter_are_explicit_and_safe():
    from memeradar_application.alert_pipeline import (
        AlertDeliveryService,
        AlertEventProjector,
        AlertRenderer,
    )
    from memeradar_providers.telegram import (
        FixtureNotificationAdapter,
        TelegramNotificationAdapter,
    )

    assert AlertDeliveryService
    assert AlertEventProjector
    assert AlertRenderer
    assert FixtureNotificationAdapter.provider_name == "fixture-telegram"
    assert TelegramNotificationAdapter.provider_name == "telegram"
    fixture_dir = ROOT / "fixtures" / "providers" / "telegram"
    assert (fixture_dir / "README.md").is_file()
    assert (fixture_dir / "replay.json").is_file()
    makefile = (ROOT / "Makefile").read_text()
    env_example = (ROOT / ".env.example").read_text()
    assert "telegram-doctor:" in makefile
    assert "TELEGRAM_BOT_TOKEN=" in env_example
    assert "TELEGRAM_CHAT_ID=" in env_example
    source = (
        ROOT / "packages" / "application" / "src" / "memeradar_application" / "alert_pipeline.py"
    ).read_text()
    assert "memeradar_providers" not in source
    assert "memeradar_persistence" not in source
    assert "sign(" not in source.lower()
    assert "submit(" not in source.lower()
    compose = yaml.safe_load(COMPOSE_PATH.read_text())["services"]
    for service_name in ("api", "worker"):
        environment = compose[service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_read_api_surface_is_packaged_and_safe():
    from memeradar_api.read import build_read_router
    from memeradar_application.read_api import ReadQueryPort

    assert build_read_router
    assert ReadQueryPort
    read_source = (ROOT / "apps" / "api" / "src" / "memeradar_api" / "read.py").read_text()
    application_source = (
        ROOT / "packages" / "application" / "src" / "memeradar_application" / "read_api.py"
    ).read_text()
    assert "POST" not in read_source
    assert "memeradar_providers" not in application_source
    assert "fastapi" not in application_source
    assert "sqlalchemy" not in application_source
    assert "execution_eligible: bool = False" in read_source
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"


def test_control_api_rbac_and_kill_switch_are_packaged_and_safe():
    from memeradar_api.auth import RoleTokenAuthenticator
    from memeradar_api.control import build_control_router
    from memeradar_api.main import create_app
    from memeradar_application.config import Settings
    from memeradar_application.control import ControlRole, InMemoryControlPlane

    settings = Settings.from_env({})
    app = create_app(settings)
    route_paths = {route.path for route in app_routes(app)}
    assert "/v1/control/state" in route_paths
    assert "/v1/control/config" in route_paths
    assert "/v1/control/analysis-kill-switch" in route_paths
    assert "/v1/control/execution-kill-switch" in route_paths
    assert RoleTokenAuthenticator
    assert build_control_router
    assert ControlRole.EXECUTION.value == "EXECUTION"
    assert InMemoryControlPlane().execution_clear_allowed is False
    env_example = (ROOT / ".env.example").read_text()
    for name in (
        "VIEWER_API_TOKEN=",
        "OPERATOR_API_TOKEN=",
        "ADMIN_API_TOKEN=",
        "EXECUTION_API_TOKEN=",
    ):
        assert name in env_example
    control_source = (ROOT / "apps" / "api" / "src" / "memeradar_api" / "control.py").read_text()
    auth_source = (ROOT / "apps" / "api" / "src" / "memeradar_api" / "auth.py").read_text()
    assert "sign_transaction" not in control_source
    assert "private_key" not in control_source
    assert "compare_digest" in auth_source
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"
