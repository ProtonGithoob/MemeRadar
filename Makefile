SHELL := /bin/bash

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
WEB_DIR ?= apps/web
COMPOSE_FILE ?= infra/compose/docker-compose.yml
COMPOSE ?= docker compose -f $(COMPOSE_FILE)

.PHONY: bootstrap lint typecheck test frontend-lint frontend-typecheck frontend-test \
	frontend-build compose-config secret-scan verify up down migrate doctor

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
	npm --prefix $(WEB_DIR) run lint

frontend-typecheck:
	npm --prefix $(WEB_DIR) run typecheck

frontend-test:
	npm --prefix $(WEB_DIR) run test

frontend-build:
	npm --prefix $(WEB_DIR) run build

compose-config:
	$(COMPOSE) config --quiet

secret-scan:
	$(PYTHON) scripts/secret_scan.py

verify: lint typecheck test frontend-lint frontend-typecheck frontend-test compose-config secret-scan

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

migrate:
	@if [[ -f alembic.ini ]]; then \
		$(PYTHON) -m alembic upgrade head; \
	else \
		echo "No migrations configured; persistence begins in Phase 1."; \
	fi

doctor:
	$(PYTHON) scripts/doctor.py
