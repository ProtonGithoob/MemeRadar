SHELL := /bin/bash

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
WEB_DIR ?= apps/web
COMPOSE_FILE ?= infra/compose/docker-compose.yml
COMPOSE ?= docker compose -f $(COMPOSE_FILE)
REPLAY_INPUT ?= fixtures/research/replay_dataset.json
REPLAY_OUTPUT ?=
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
EARLY_DETECTION_ITERATIONS ?= 100
EARLY_DETECTION_OUTPUT ?=
SBOM_OUTPUT ?=

.PHONY: bootstrap lint typecheck test replay-dataset profile-replay frontend-lint frontend-typecheck frontend-test frontend-e2e \
	frontend-build compose-config secret-scan migration-check integration-test verify up down migrate doctor \
	start stop status \
	provider-doctor helius-doctor solana-rpc-doctor dexscreener-doctor free-provider-doctor \
	birdeye-doctor rugcheck-doctor social-doctor narrative-doctor ollama-doctor \
	external-wallet-doctor telegram-doctor stream-integrity-doctor paper-trading-doctor \
	backtest-replay calibrate-score winner-vs-rug-optimizer reliability-benchmark early-detection-benchmark early-live-doctor reliability-doctor \
	security-review security-review-external sbom shadow-start shadow-status


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

replay-dataset:
	$(PYTHON) scripts/replay_dataset.py --input $(REPLAY_INPUT) $(if $(REPLAY_OUTPUT),--output $(REPLAY_OUTPUT),)

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

early-detection-benchmark:
	$(PYTHON) scripts/early_detection_benchmark.py --iterations $(EARLY_DETECTION_ITERATIONS) \
		$(if $(EARLY_DETECTION_OUTPUT),--output $(EARLY_DETECTION_OUTPUT),)

frontend-lint:
	cd $(WEB_DIR) && npm run lint

frontend-typecheck:
	cd $(WEB_DIR) && npm run typecheck

frontend-test:
	cd $(WEB_DIR) && npm run test

frontend-e2e:
	cd $(WEB_DIR) && npm run test:e2e

frontend-build:
	cd $(WEB_DIR) && npm run build

compose-config:
	$(COMPOSE) config --quiet

secret-scan:
	$(PYTHON) scripts/secret_scan.py

security-review:
	$(PYTHON) scripts/security_review.py

security-review-external:
	$(PYTHON) scripts/security_review.py --external

sbom:
	$(PYTHON) scripts/sbom.py --check $(if $(SBOM_OUTPUT),--output $(SBOM_OUTPUT),)

migration-check:
	$(PYTHON) scripts/check_migrations.py

integration-test:
	@if [[ -n "$${MEMERADAR_TEST_DATABASE_URL:-}" ]]; then \
		$(PYTHON) -m pytest tests/integration -q; \
	else \
		echo "MEMERADAR_TEST_DATABASE_URL not configured; integration tests skipped."; \
	fi

verify: lint typecheck test frontend-lint frontend-typecheck frontend-test compose-config secret-scan migration-check security-review sbom

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
	$(PYTHON) scripts/provider_doctor.py

helius-doctor:
	$(PYTHON) scripts/provider_doctor.py

solana-rpc-doctor:
	$(PYTHON) scripts/solana_rpc_doctor.py

dexscreener-doctor:
	$(PYTHON) scripts/dexscreener_doctor.py

free-provider-doctor:
	$(PYTHON) scripts/free_provider_doctor.py

birdeye-doctor:
	$(PYTHON) scripts/birdeye_doctor.py

rugcheck-doctor:
	$(PYTHON) scripts/rugcheck_doctor.py

social-doctor:
	$(PYTHON) scripts/social_doctor.py

narrative-doctor:
	$(PYTHON) scripts/narrative_doctor.py

ollama-doctor:
	$(PYTHON) scripts/ollama_doctor.py

external-wallet-doctor:
	$(PYTHON) scripts/external_wallet_doctor.py

telegram-doctor:
	$(PYTHON) scripts/telegram_doctor.py

stream-integrity-doctor:
	$(PYTHON) scripts/stream_integrity_doctor.py

paper-trading-doctor:
	$(PYTHON) scripts/paper_trading_doctor.py

early-live-doctor:
	$(PYTHON) scripts/early_live_doctor.py

reliability-doctor:
	$(PYTHON) scripts/reliability_doctor.py

shadow-start:
	bash scripts/start-shadow.sh

shadow-status:
	$(PYTHON) scripts/shadow_status.py
