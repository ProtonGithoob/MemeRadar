SHELL := /bin/bash

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
WEB_DIR ?= apps/web
COMPOSE_FILE ?= infra/compose/docker-compose.yml
COMPOSE ?= docker compose -f $(COMPOSE_FILE)
REPLAY_INPUT ?= fixtures/research/replay_dataset.json
REPLAY_OUTPUT ?=
OPPORTUNITY_RESEARCH_INPUT ?= fixtures/research/opportunity_case_studies.json
OPPORTUNITY_RESEARCH_OUTPUT ?=
HISTORICAL_DATASET_INPUT ?= $(OPPORTUNITY_RESEARCH_INPUT)
HISTORICAL_DATASET_OUTPUT ?=
BACKTEST_INPUT ?= $(REPLAY_INPUT)
BACKTEST_OUTPUT ?=
BACKTEST_ENTRY_SCORE_THRESHOLD ?= 50
BACKTEST_MIN_CONFIDENCE ?= 0.60
BACKTEST_OUTCOME_HORIZON ?= 24h
BACKTEST_FEE_BPS ?= 30
BACKTEST_SLIPPAGE_BPS ?= 25
CALIBRATION_INPUT ?= $(BACKTEST_INPUT)
CALIBRATION_OUTPUT ?=
PROFILE_ITERATIONS ?= 10
WINNER_VS_RUG_INPUT ?= fixtures/providers/winner_vs_rug/replay.json
WINNER_VS_RUG_OUTPUT ?=
RELIABILITY_ITERATIONS ?= 1000
RELIABILITY_OUTPUT ?=
SOAK_ITERATIONS ?= 1000
SOAK_EXPECTED_RATE ?= 100
SOAK_OUTPUT ?=
STACK_SOAK_ITERATIONS ?= 100
STACK_SOAK_INTERVAL_SECONDS ?= 1
STACK_SOAK_STRICT_ACCEPTANCE ?= 0
STACK_SOAK_OUTPUT ?=
STACK_API_BASE_URL ?= http://127.0.0.1:18000
STACK_CONTAINER_NAMES ?=
RELEASE_IMAGE_TAG ?= memeradar-$(shell git rev-parse --short HEAD)
RELEASE_API_IMAGE ?= memeradar-api:$(RELEASE_IMAGE_TAG)
RELEASE_WORKER_IMAGE ?= memeradar-worker:$(RELEASE_IMAGE_TAG)
RELEASE_WEB_IMAGE ?= memeradar-web:$(RELEASE_IMAGE_TAG)
PRODUCTION_COMPOSE_FILE ?= infra/compose/docker-compose.prod.yml
PRODUCTION_COMPOSE ?= docker compose -f $(COMPOSE_FILE) -f $(PRODUCTION_COMPOSE_FILE)
BACKUP_FILE ?= artifacts/memeradar-backup-restore-drill.dump
BACKUP_RESTORE_OUTPUT ?=
EARLY_DETECTION_ITERATIONS ?= 100
EARLY_DETECTION_OUTPUT ?=
SBOM_OUTPUT ?=

.PHONY: bootstrap lint typecheck test mcp replay-dataset profile-replay frontend-css-contract frontend-lint frontend-typecheck frontend-test frontend-e2e \
	frontend-build frontend-security-audit deterministic-release-gates prod-read-only-verify \
	compose-config secret-scan migration-check integration-test verify up down migrate doctor \
	start stop status \
	provider-doctor helius-doctor solana-rpc-doctor dexscreener-doctor free-provider-doctor \
	birdeye-doctor rugcheck-doctor social-doctor narrative-doctor ollama-doctor \
	external-wallet-doctor telegram-doctor stream-integrity-doctor paper-trading-doctor \
	backtest-replay opportunity-research historical-dataset alpha-readiness calibrate-score winner-vs-rug-optimizer reliability-benchmark synthetic-reliability-benchmark production-soak production-stack-smoke production-stack-acceptance early-detection-benchmark early-live-doctor reliability-doctor \
	security-review security-review-external sbom release-identity compose-prod-config production-images production-build-e2e production-dependency-drill backup-restore-drill shadow-start shadow-status


bootstrap:
	python3 -m venv .venv
	$(PIP) install --disable-pip-version-check -r requirements.lock
	npm ci --prefix $(WEB_DIR) --ignore-scripts

lint:
	$(PYTHON) -m ruff check apps packages tests scripts

typecheck:
	$(PYTHON) -m mypy

test:
	$(PYTHON) -m pytest -q --cov=apps --cov=packages --cov-report=term-missing

mcp:
	PYTHONPATH=apps/mcp/src:apps/api/src:packages/application/src:packages/domain/src:packages/persistence/src:packages/providers/src:packages/telemetry/src \
		$(PYTHON) -m memeradar_mcp

replay-dataset:
	$(PYTHON) scripts/replay_dataset.py --input $(REPLAY_INPUT) $(if $(REPLAY_OUTPUT),--output $(REPLAY_OUTPUT),)

opportunity-research:
	$(PYTHON) scripts/opportunity_research.py --input $(OPPORTUNITY_RESEARCH_INPUT) \
		$(if $(OPPORTUNITY_RESEARCH_OUTPUT),--output $(OPPORTUNITY_RESEARCH_OUTPUT),)

historical-dataset:
	$(PYTHON) scripts/historical_dataset.py --input $(HISTORICAL_DATASET_INPUT) \
		$(if $(HISTORICAL_DATASET_OUTPUT),--output $(HISTORICAL_DATASET_OUTPUT),)

alpha-readiness:
	$(PYTHON) scripts/alpha_readiness.py --input $(HISTORICAL_DATASET_INPUT)

profile-replay:
	$(PYTHON) scripts/profile_replay.py --input $(REPLAY_INPUT) --iterations $(PROFILE_ITERATIONS)

backtest-replay:
	$(PYTHON) scripts/backtest_replay.py --input $(BACKTEST_INPUT) \
		--entry-score-threshold $(BACKTEST_ENTRY_SCORE_THRESHOLD) \
		--min-confidence $(BACKTEST_MIN_CONFIDENCE) \
		--outcome-horizon $(BACKTEST_OUTCOME_HORIZON) \
		--fee-bps $(BACKTEST_FEE_BPS) \
		--slippage-bps $(BACKTEST_SLIPPAGE_BPS) \
		$(if $(BACKTEST_OUTPUT),--output $(BACKTEST_OUTPUT),)

calibrate-score:
	$(PYTHON) scripts/calibrate_score.py --input $(CALIBRATION_INPUT) \
		$(if $(CALIBRATION_OUTPUT),--output $(CALIBRATION_OUTPUT),)

winner-vs-rug-optimizer:
	$(PYTHON) scripts/winner_vs_rug_optimizer.py --input $(WINNER_VS_RUG_INPUT) \
		$(if $(WINNER_VS_RUG_OUTPUT),--output $(WINNER_VS_RUG_OUTPUT),)

reliability-benchmark:
	$(PYTHON) scripts/reliability_benchmark.py --iterations $(RELIABILITY_ITERATIONS) \
		$(if $(RELIABILITY_OUTPUT),--output $(RELIABILITY_OUTPUT),)

synthetic-reliability-benchmark:
	$(MAKE) reliability-benchmark

production-soak:
	MEMERADAR_STACK_API_BASE_URL="$(STACK_API_BASE_URL)" \
	MEMERADAR_STACK_CONTAINER_NAMES="$(STACK_CONTAINER_NAMES)" \
		$(PYTHON) scripts/production_stack_soak.py --iterations $(STACK_SOAK_ITERATIONS) \
		--interval-seconds $(STACK_SOAK_INTERVAL_SECONDS) \
		$(if $(filter 1 true yes,$(STACK_SOAK_STRICT_ACCEPTANCE)),--strict-acceptance,) \
		$(if $(STACK_SOAK_OUTPUT),--output $(STACK_SOAK_OUTPUT),)

production-stack-smoke:
	$(MAKE) production-soak STACK_SOAK_ITERATIONS=1 STACK_SOAK_INTERVAL_SECONDS=0 \
		STACK_SOAK_OUTPUT="$(STACK_SOAK_OUTPUT)"

production-stack-acceptance:
	$(MAKE) production-soak STACK_SOAK_STRICT_ACCEPTANCE=1

production-build-e2e:
	@if [[ -z "$${MEMERADAR_E2E_BASE_URL:-}" ]]; then \
		echo "MEMERADAR_E2E_BASE_URL is required for production-build-e2e."; exit 2; \
	fi
	$(MAKE) frontend-e2e

production-dependency-drill:
	@set -euo pipefail; \
	drill_output=$$(mktemp -d); \
	assert_production_recovery_contract() { \
		for service in api worker; do \
			container_id="$$($(PRODUCTION_COMPOSE) ps -q "$$service")"; \
			test -n "$$container_id"; \
			docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$$container_id" | \
				$(PYTHON) -c 'import sys; env = dict(line.rstrip("\n").split("=", 1) for line in sys.stdin if "=" in line); assert env.get("APP_ENV") == "production"; assert env.get("REQUIRE_DATABASE_FOR_READINESS") == "true"; assert env.get("REQUIRE_REDIS_FOR_READINESS") == "true"; assert env.get("ANALYSIS_ONLY") == "true"; assert env.get("PAPER_TRADING") == "true"; assert env.get("MANUAL_EXECUTION") == "false"; assert env.get("AUTO_EXECUTION") == "false"; assert not any(name in env for name in ("VIEWER_API_TOKEN", "OPERATOR_API_TOKEN", "ADMIN_API_TOKEN", "EXECUTION_API_TOKEN")) if "worker" in sys.argv[1].lower() else True' "$$service"; \
		done; \
	}; \
	trap '$(PRODUCTION_COMPOSE) start postgres redis >/dev/null 2>&1 || true; rm -f "$$drill_output"/*.json; rmdir "$$drill_output"' EXIT; \
	$(MAKE) production-stack-smoke; \
	$(PRODUCTION_COMPOSE) stop postgres; \
	set +e; $(MAKE) production-stack-smoke STACK_SOAK_OUTPUT="$$drill_output/postgres-down.json"; postgres_down_status=$$?; set -e; \
	test $$postgres_down_status -ne 0; \
	$(PYTHON) -c 'import json, sys; report = json.load(open(sys.argv[1])); assert report["dependency_readiness"] == {"database": "unreachable", "redis": "reachable"}, report["dependency_readiness"]' "$$drill_output/postgres-down.json"; \
	$(PRODUCTION_COMPOSE) start postgres >/dev/null; \
	$(PRODUCTION_COMPOSE) up -d --wait api worker >/dev/null; \
	assert_production_recovery_contract; \
	$(MAKE) production-stack-smoke; \
	$(PRODUCTION_COMPOSE) stop redis; \
	set +e; $(MAKE) production-stack-smoke STACK_SOAK_OUTPUT="$$drill_output/redis-down.json"; redis_down_status=$$?; set -e; \
	test $$redis_down_status -ne 0; \
	$(PYTHON) -c 'import json, sys; report = json.load(open(sys.argv[1])); assert report["dependency_readiness"] == {"database": "reachable", "redis": "unreachable"}, report["dependency_readiness"]' "$$drill_output/redis-down.json"; \
	$(PRODUCTION_COMPOSE) start redis >/dev/null; \
	$(PRODUCTION_COMPOSE) up -d --wait api worker >/dev/null; \
	assert_production_recovery_contract; \
	$(MAKE) production-stack-smoke

early-detection-benchmark:
	$(PYTHON) scripts/early_detection_benchmark.py --iterations $(EARLY_DETECTION_ITERATIONS) \
		$(if $(EARLY_DETECTION_OUTPUT),--output $(EARLY_DETECTION_OUTPUT),)

frontend-lint:
	cd $(WEB_DIR) && npm run lint

frontend-css-contract:
	$(PYTHON) scripts/check_frontend_css.py

frontend-typecheck:
	cd $(WEB_DIR) && npm run typecheck

frontend-test:
	cd $(WEB_DIR) && npm run test

frontend-e2e:
	cd $(WEB_DIR) && npm run test:e2e

frontend-build:
	cd $(WEB_DIR) && npm run build

frontend-security-audit:
	cd $(WEB_DIR) && npm audit --omit=dev --audit-level=high

compose-config:
	$(COMPOSE) config --quiet

compose-prod-config:
	$(PRODUCTION_COMPOSE) config --quiet

secret-scan:
	$(PYTHON) scripts/secret_scan.py

security-review:
	$(PYTHON) scripts/security_review.py

security-review-external:
	$(PYTHON) scripts/security_review.py --external

sbom:
	$(PYTHON) scripts/sbom.py --check $(if $(SBOM_OUTPUT),--output $(SBOM_OUTPUT),)

release-identity:
	RELEASE_API_IMAGE="$(RELEASE_API_IMAGE)" \
	RELEASE_WORKER_IMAGE="$(RELEASE_WORKER_IMAGE)" \
	RELEASE_WEB_IMAGE="$(RELEASE_WEB_IMAGE)" \
		$(PYTHON) scripts/release_identity.py $(if $(RELEASE_IDENTITY_OUTPUT),--output $(RELEASE_IDENTITY_OUTPUT),)

production-images:
	docker build -q -f infra/docker/api.Dockerfile -t "$(RELEASE_API_IMAGE)" .
	docker build -q -f infra/docker/worker.Dockerfile -t "$(RELEASE_WORKER_IMAGE)" .
	docker build -q -f infra/docker/web.Dockerfile -t "$(RELEASE_WEB_IMAGE)" .

backup-restore-drill:
	MEMERADAR_BACKUP_SOURCE_URL="$${MEMERADAR_BACKUP_SOURCE_URL:?set source URL}" \
	MEMERADAR_BACKUP_RESTORE_URL="$${MEMERADAR_BACKUP_RESTORE_URL:?set disposable restore URL}" \
		$(PYTHON) scripts/backup_restore_drill.py --backup-file "$(BACKUP_FILE)" \
		$(if $(BACKUP_RESTORE_OUTPUT),--output "$(BACKUP_RESTORE_OUTPUT)",)

migration-check:
	$(PYTHON) scripts/check_migrations.py

integration-test:
	@if [[ -n "$${MEMERADAR_TEST_DATABASE_URL:-}" ]]; then \
		$(PYTHON) -m pytest tests/integration -q; \
	else \
		echo "MEMERADAR_TEST_DATABASE_URL not configured; integration tests skipped."; \
	fi

verify: lint typecheck test frontend-css-contract frontend-lint frontend-typecheck frontend-test compose-config secret-scan migration-check security-review sbom

deterministic-release-gates: verify frontend-build frontend-security-audit compose-prod-config production-images release-identity

prod-read-only-verify: deterministic-release-gates
	@if [[ -z "$${MEMERADAR_TEST_DATABASE_URL:-}" ]]; then \
		 echo "BLOCKED_EXTERNAL: MEMERADAR_TEST_DATABASE_URL is required for PostgreSQL acceptance."; \
		exit 2; \
	fi
	@if [[ -z "$${MEMERADAR_E2E_BASE_URL:-}" ]]; then \
		echo "BLOCKED_EXTERNAL: MEMERADAR_E2E_BASE_URL must point to a production build for browser acceptance."; \
		exit 2; \
	fi
	$(MAKE) integration-test
	$(MAKE) production-build-e2e

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

start:
	bash scripts/start.sh

stop:
	bash scripts/stop.sh

status:
	bash scripts/status.sh

migrate:
	@if [[ -f alembic.ini ]]; then \
		if [[ -n "$${MEMERADAR_DATABASE_URL:-}" || -n "$${DATABASE_URL:-}" ]]; then \
			$(PYTHON) -m alembic -c alembic.ini upgrade head; \
		else \
			echo "Migration files present; no database URL configured; runtime migration skipped."; \
		fi; \
	else \
		echo "No migrations configured."; \
	fi

doctor:
	$(PYTHON) scripts/doctor.py

provider-doctor:
	$(PYTHON) -m scripts.provider_doctor

helius-doctor:
	$(PYTHON) -m scripts.provider_doctor

solana-rpc-doctor:
	$(PYTHON) -m scripts.solana_rpc_doctor

dexscreener-doctor:
	$(PYTHON) -m scripts.dexscreener_doctor

free-provider-doctor:
	$(PYTHON) -m scripts.free_provider_doctor

birdeye-doctor:
	$(PYTHON) -m scripts.birdeye_doctor

rugcheck-doctor:
	$(PYTHON) -m scripts.rugcheck_doctor

social-doctor:
	$(PYTHON) -m scripts.social_doctor

narrative-doctor:
	$(PYTHON) -m scripts.narrative_doctor

ollama-doctor:
	$(PYTHON) -m scripts.ollama_doctor

external-wallet-doctor:
	$(PYTHON) -m scripts.external_wallet_doctor

telegram-doctor:
	$(PYTHON) -m scripts.telegram_doctor

stream-integrity-doctor:
	$(PYTHON) -m scripts.stream_integrity_doctor

paper-trading-doctor:
	$(PYTHON) -m scripts.paper_trading_doctor

early-live-doctor:
	$(PYTHON) -m scripts.early_live_doctor

reliability-doctor:
	$(PYTHON) -m scripts.reliability_doctor

shadow-start:
	bash scripts/start-shadow.sh

shadow-status:
	$(PYTHON) scripts/shadow_status.py
