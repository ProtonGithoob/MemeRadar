#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/infra/compose/docker-compose.yml"
export POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-55432}"
export REDIS_HOST_PORT="${REDIS_HOST_PORT:-56379}"
export API_HOST_PORT="${API_HOST_PORT:-18000}"
export WEB_HOST_PORT="${WEB_HOST_PORT:-13000}"
API_URL="${MEMERADAR_API_URL:-http://localhost:${API_HOST_PORT}}"
START_TIMEOUT_SECONDS="${MEMERADAR_START_TIMEOUT_SECONDS:-120}"
START_POLL_INTERVAL_SECONDS="${MEMERADAR_START_POLL_INTERVAL_SECONDS:-2}"

log() {
  printf '[MemeRadar] %s\n' "$*"
}

fail() {
  printf '[MemeRadar] ERROR: %s\n' "$*" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail "Docker is not installed or not in PATH."
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required."
command -v curl >/dev/null 2>&1 || fail "curl is required for local health checks."
[[ -f "${COMPOSE_FILE}" ]] || fail "Compose file not found: ${COMPOSE_FILE}"
[[ "${START_TIMEOUT_SECONDS}" =~ ^[1-9][0-9]*$ ]] || fail "MEMERADAR_START_TIMEOUT_SECONDS must be a positive integer."
[[ "${START_POLL_INTERVAL_SECONDS}" =~ ^[1-9][0-9]*$ ]] || fail "MEMERADAR_START_POLL_INTERVAL_SECONDS must be a positive integer."

cd "${ROOT_DIR}"

wait_for_health() {
  local endpoint="$1"
  local label="$2"
  local elapsed=0

  while (( elapsed <= START_TIMEOUT_SECONDS )); do
    if curl --fail --silent --show-error --max-time 5 "${endpoint}" >/dev/null 2>&1; then
      log "${label}: healthy"
      return 0
    fi
    if (( elapsed >= START_TIMEOUT_SECONDS )); then
      break
    fi
    sleep "${START_POLL_INTERVAL_SECONDS}"
    elapsed=$((elapsed + START_POLL_INTERVAL_SECONDS))
  done
  return 1
}

log "Starting MemeRadar in protected analysis/paper mode..."
log "ANALYSIS_ONLY=true | PAPER_TRADING=true | MANUAL_EXECUTION=false | AUTO_EXECUTION=false"
log "PostgreSQL host port: ${POSTGRES_HOST_PORT} (container: 5432)"
log "Redis host port: ${REDIS_HOST_PORT} (container: 6379)"
log "API host port: ${API_HOST_PORT} (container: 8000)"
log "Web host port: ${WEB_HOST_PORT} (container: 3000)"

docker compose -f "${COMPOSE_FILE}" up -d --build --remove-orphans

log "Waiting up to ${START_TIMEOUT_SECONDS}s for API liveness and readiness..."
if ! wait_for_health "${API_URL}/health/live" "API liveness" || \
   ! wait_for_health "${API_URL}/health/ready" "API readiness"; then
  docker compose -f "${COMPOSE_FILE}" ps
  fail "API did not become ready. Check: docker compose -f infra/compose/docker-compose.yml logs --tail=200"
fi

log "Service status:"
docker compose -f "${COMPOSE_FILE}" ps

printf '\n'
log "MemeRadar started successfully."
if [[ -n "${MEMERADAR_WEB_URL:-}" ]]; then
  log "Web: configured MEMERADAR_WEB_URL"
else
  log "Web: http://localhost:${WEB_HOST_PORT}"
fi
if [[ -n "${MEMERADAR_API_URL:-}" ]]; then
  log "API: configured MEMERADAR_API_URL"
else
  log "API: http://localhost:${API_HOST_PORT}"
fi
log "API health: local liveness/readiness checks passed"
log "PostgreSQL host: localhost:${POSTGRES_HOST_PORT}"
log "Redis host: localhost:${REDIS_HOST_PORT}"
log "Logs: docker compose -f infra/compose/docker-compose.yml logs -f"
log "Status: bash scripts/status.sh"
log "Stop: bash scripts/stop.sh"
