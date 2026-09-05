#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/infra/compose/docker-compose.yml"

log() {
  printf '[MemeRadar] %s\n' "$*"
}

fail() {
  printf '[MemeRadar] ERROR: %s\n' "$*" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail "Docker is not installed or not in PATH."
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required."
[[ -f "${COMPOSE_FILE}" ]] || fail "Compose file not found: ${COMPOSE_FILE}"

cd "${ROOT_DIR}"

log "Stopping MemeRadar services..."
log "Named PostgreSQL and Redis volumes will be preserved."
docker compose -f "${COMPOSE_FILE}" down --remove-orphans
log "MemeRadar stopped."
