#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/infra/compose/docker-compose.yml"
API_URL="${MEMERADAR_API_URL:-http://localhost:8000}"
WEB_URL="${MEMERADAR_WEB_URL:-http://localhost:3000}"
export REDIS_HOST_PORT="${REDIS_HOST_PORT:-6380}"

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

log "Starting MemeRadar in protected analysis/paper mode..."
log "ANALYSIS_ONLY=true | PAPER_TRADING=true | MANUAL_EXECUTION=false | AUTO_EXECUTION=false"
log "Redis host port: ${REDIS_HOST_PORT} (container port remains 6379)"

docker compose -f "${COMPOSE_FILE}" up -d --build

log "Waiting for services to become healthy..."
for _ in $(seq 1 60); do
  if curl -fsS "${API_URL}/health/live" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! curl -fsS "${API_URL}/health/live" >/dev/null 2>&1; then
  docker compose -f "${COMPOSE_FILE}" ps
  fail "API did not become healthy. Check: docker compose -f infra/compose/docker-compose.yml logs --tail=200"
fi

log "Service status:"
docker compose -f "${COMPOSE_FILE}" ps

printf '\n'
log "MemeRadar started successfully."
log "Web: ${WEB_URL}"
log "API: ${API_URL}"
log "API health: ${API_URL}/health/live"
log "Redis host: localhost:${REDIS_HOST_PORT}"
log "Logs: docker compose -f infra/compose/docker-compose.yml logs -f"
log "Stop: make down"
