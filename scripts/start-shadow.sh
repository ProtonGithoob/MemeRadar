#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() {
  printf '[MemeRadar-Shadow] %s\n' "$*"
}

fail() {
  printf '[MemeRadar-Shadow] ERROR: %s\n' "$*" >&2
  exit 1
}

# 1. Enforce Operating Mode Invariants
ANALYSIS_ONLY="${ANALYSIS_ONLY:-true}"
PAPER_TRADING="${PAPER_TRADING:-true}"
MANUAL_EXECUTION="${MANUAL_EXECUTION:-false}"
AUTO_EXECUTION="${AUTO_EXECUTION:-false}"

if [[ "${ANALYSIS_ONLY}" != "true" ]]; then
  fail "ANALYSIS_ONLY must be true for live shadow mode. Got: ${ANALYSIS_ONLY}"
fi

if [[ "${PAPER_TRADING}" != "true" ]]; then
  fail "PAPER_TRADING must be true for live shadow mode. Got: ${PAPER_TRADING}"
fi

if [[ "${MANUAL_EXECUTION}" != "false" ]]; then
  fail "MANUAL_EXECUTION must be false. Live execution is locked. Got: ${MANUAL_EXECUTION}"
fi

if [[ "${AUTO_EXECUTION}" != "false" ]]; then
  fail "AUTO_EXECUTION must be false. Live execution is locked. Got: ${AUTO_EXECUTION}"
fi

log "Operating mode invariants verified (FAIL-CLOSED):"
log "  ANALYSIS_ONLY=${ANALYSIS_ONLY}"
log "  PAPER_TRADING=${PAPER_TRADING}"
log "  MANUAL_EXECUTION=${MANUAL_EXECUTION}"
log "  AUTO_EXECUTION=${AUTO_EXECUTION}"

# 2. Ensure artifacts directory exists
SHADOW_ARTIFACT_DIR="${ROOT_DIR}/artifacts/research/live-shadow"
mkdir -p "${SHADOW_ARTIFACT_DIR}"

# 3. Delegate to start.sh for container lifecycle
log "Launching MemeRadar services via scripts/start.sh..."
bash "${ROOT_DIR}/scripts/start.sh"

# 4. Verify Provider Health Endpoint
API_HOST_PORT="${API_HOST_PORT:-18000}"
API_URL="${MEMERADAR_API_URL:-http://localhost:${API_HOST_PORT}}"

log "Checking provider health endpoint (${API_URL}/v1/providers/health)..."
if HEALTH_OUTPUT=$(curl -fsS "${API_URL}/v1/providers/health" 2>/dev/null); then
  log "Provider health check succeeded."
  echo "${HEALTH_OUTPUT}" | head -n 30
else
  log "Provider health check returned non-200 or empty response (service starting up or no credentials configured)."
fi

log "Live read-only shadow validation environment is READY."
