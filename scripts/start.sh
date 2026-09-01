#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/infra/compose/docker-compose.yml"
export POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-55432}"
export REDIS_HOST_PORT="${REDIS_HOST_PORT:-56379}"
export API_HOST_PORT="${API_HOST_PORT:-18000}"
export WEB_HOST_PORT="${WEB_HOST_PORT:-13000}"
API_URL="${MEMERADAR_API_URL:-http://localhost:${API_HOST_PORT}}"
WEB_URL="${MEMERADAR_WEB_URL:-http://localhost:${WEB_HOST_PORT}}"

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
log "PostgreSQL host port: ${POSTGRES_HOST_PORT} (container: 5432)"
log "Redis host port: ${REDIS_HOST_PORT} (container: 6379)"
log "API host port: ${API_HOST_PORT} (container: 8000)"
log "Web host port: ${WEB_HOST_PORT} (container: 3000)"

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
log "PostgreSQL host: localhost:${POSTGRES_HOST_PORT}"
log "Redis host: localhost:${REDIS_HOST_PORT}"
log "Logs: docker compose -f infra/compose/docker-compose.yml logs -f"
log "Stop: make down"
