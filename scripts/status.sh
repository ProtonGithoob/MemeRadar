#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/infra/compose/docker-compose.yml"
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
command -v curl >/dev/null 2>&1 || fail "curl is required for local health checks."
[[ -f "${COMPOSE_FILE}" ]] || fail "Compose file not found: ${COMPOSE_FILE}"

cd "${ROOT_DIR}"

log "MemeRadar Compose status:"
docker compose -f "${COMPOSE_FILE}" ps

running_services="$(docker compose -f "${COMPOSE_FILE}" ps --services --filter status=running 2>/dev/null || true)"
missing_services=()
for service in postgres redis api worker web; do
  if ! printf '%s\n' "${running_services}" | grep -Fxq "${service}"; then
    missing_services+=("${service}")
  fi
done

overall_status=0
if ((${#missing_services[@]} == 0)); then
  log "Services: PASS (postgres, redis, api, worker, web running)"
else
  log "Services: DEGRADED (not running: ${missing_services[*]})"
  overall_status=1
fi

probe_http() {
  local endpoint="$1"
  local http_code

  if http_code="$(curl --silent --show-error --max-time 5 -o /dev/null -w '%{http_code}' "${endpoint}" 2>/dev/null)"; then
    [[ "${http_code}" =~ ^[23][0-9]{2}$ ]]
    return
  fi
  return 1
}

if probe_http "${API_URL}/health/live"; then
  log "API liveness: PASS"
else
  log "API liveness: FAIL or UNAVAILABLE"
  overall_status=1
fi

if probe_http "${API_URL}/health/ready"; then
  log "API readiness: PASS"
else
  log "API readiness: FAIL or DEGRADED"
  overall_status=1
fi

if probe_http "${WEB_URL}"; then
  log "Web endpoint: PASS"
else
  web_http_code="$(curl --silent --show-error --max-time 5 -o /dev/null -w '%{http_code}' "${WEB_URL}" 2>/dev/null || true)"
  if [[ -z "${web_http_code}" || "${web_http_code}" == "000" ]]; then
    log "Web endpoint: UNAVAILABLE"
  else
    log "Web endpoint: FAIL (HTTP ${web_http_code})"
  fi
  overall_status=1
fi

log "Protected modes: ANALYSIS_ONLY=true | PAPER_TRADING=true | MANUAL_EXECUTION=false | AUTO_EXECUTION=false"
if ((overall_status == 0)); then
  log "Overall status: PASS"
else
  log "Overall status: DEGRADED or STOPPED"
fi

exit "${overall_status}"
