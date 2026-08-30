SHELL := /bin/bash

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
WEB_DIR ?= apps/web
COMPOSE_FILE ?= infra/compose/docker-compose.yml
COMPOSE ?= docker compose -f $(COMPOSE_FILE)

.PHONY: bootstrap lint typecheck test frontend-lint frontend-typecheck frontend-test \
	frontend-build compose-config secret-scan migration-check integration-test verify up down migrate doctor \
	provider-doctor birdeye-doctor rugcheck-doctor social-doctor narrative-doctor

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

frontend-lint:
	cd $(WEB_DIR) && npm run lint

frontend-typecheck:
	cd $(WEB_DIR) && npm run typecheck

frontend-test:
	cd $(WEB_DIR) && npm run test

frontend-build:
	cd $(WEB_DIR) && npm run build

compose-config:
	$(COMPOSE) config --quiet

secret-scan:
	$(PYTHON) scripts/secret_scan.py

migration-check:
	$(PYTHON) scripts/check_migrations.py

integration-test:
	@if [[ -n "$${MEMERADAR_TEST_DATABASE_URL:-}" ]]; then \
		$(PYTHON) -m pytest tests/integration -q; \
	else \
		echo "MEMERADAR_TEST_DATABASE_URL not configured; integration tests skipped."; \
	fi

verify: lint typecheck test frontend-lint frontend-typecheck frontend-test compose-config secret-scan migration-check

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

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

birdeye-doctor:
	$(PYTHON) scripts/birdeye_doctor.py

rugcheck-doctor:
	$(PYTHON) scripts/rugcheck_doctor.py

social-doctor:
	$(PYTHON) scripts/social_doctor.py

narrative-doctor:
	$(PYTHON) scripts/narrative_doctor.py
