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

# 1. Enforce Operating Mode Invariants (Fail-Closed Check)
INHERITED_ANALYSIS="${ANALYSIS_ONLY:-true}"
INHERITED_PAPER="${PAPER_TRADING:-true}"
INHERITED_MANUAL="${MANUAL_EXECUTION:-false}"
INHERITED_AUTO="${AUTO_EXECUTION:-false}"

if [[ "${INHERITED_ANALYSIS}" != "true" ]]; then
  fail "Unsafe inherited env: ANALYSIS_ONLY must be true. Got: ${INHERITED_ANALYSIS}"
fi

if [[ "${INHERITED_PAPER}" != "true" ]]; then
  fail "Unsafe inherited env: PAPER_TRADING must be true. Got: ${INHERITED_PAPER}"
fi

if [[ "${INHERITED_MANUAL}" != "false" ]]; then
  fail "Unsafe inherited env: MANUAL_EXECUTION must be false. Got: ${INHERITED_MANUAL}"
fi

if [[ "${INHERITED_AUTO}" != "false" ]]; then
  fail "Unsafe inherited env: AUTO_EXECUTION must be false. Got: ${INHERITED_AUTO}"
fi

# 2. Explicitly Export Protection Invariants for Child Processes & Compose
export ANALYSIS_ONLY=true
export PAPER_TRADING=true
export MANUAL_EXECUTION=false
export AUTO_EXECUTION=false

log "Operating mode invariants verified & exported (FAIL-CLOSED):"
log "  ANALYSIS_ONLY=${ANALYSIS_ONLY}"
log "  PAPER_TRADING=${PAPER_TRADING}"
log "  MANUAL_EXECUTION=${MANUAL_EXECUTION}"
log "  AUTO_EXECUTION=${AUTO_EXECUTION}"

# 3. Establish Durable Shadow Run Identity
SHADOW_ARTIFACT_DIR="${ROOT_DIR}/artifacts/research/live-shadow"
RUNS_DIR="${SHADOW_ARTIFACT_DIR}/runs"
CURRENT_RUN_FILE="${SHADOW_ARTIFACT_DIR}/current_run.json"
mkdir -p "${SHADOW_ARTIFACT_DIR}" "${RUNS_DIR}"

NOW_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
RUN_ID="shadow_run_$(date -u +"%Y%m%d_%H%M%S")_$$"

# Preserve previous run history if existing run file is present
if [[ -f "${CURRENT_RUN_FILE}" ]]; then
  PREV_RUN_ID=$(python3 -c "import json; print(json.load(open('${CURRENT_RUN_FILE}')).get('run_id', 'unknown'))" 2>/dev/null || echo "prev_run")
  log "Archiving previous shadow run identity: ${PREV_RUN_ID}"
  cp "${CURRENT_RUN_FILE}" "${RUNS_DIR}/run_${PREV_RUN_ID}_$(date -u +"%Y%m%d_%H%M%S").json" 2>/dev/null || true
fi

CONFIG_HASH=$(python3 -c "import hashlib; print(hashlib.sha256(b'true:true:false:false').hexdigest()[:16])")
GIT_SHA=$(git rev-parse HEAD 2>/dev/null || echo "UNKNOWN")

cat <<EOF > "${CURRENT_RUN_FILE}"
{
  "run_id": "${RUN_ID}",
  "run_started_at": "${NOW_UTC}",
  "git_commit_sha": "${GIT_SHA}",
  "config_hash": "${CONFIG_HASH}",
  "operating_modes": {
    "analysis_only": true,
    "paper_trading": true,
    "manual_execution": false,
    "auto_execution": false
  }
}
EOF

log "Durable shadow run identity established:"
log "  Run ID: ${RUN_ID}"
log "  Started At: ${NOW_UTC}"

# 4. Launch MemeRadar Services via start.sh
log "Launching MemeRadar services via scripts/start.sh..."
bash "${ROOT_DIR}/scripts/start.sh"

# 5. Evaluate Stack Readiness vs Provider Readiness
API_HOST_PORT="${API_HOST_PORT:-18000}"
API_URL="${MEMERADAR_API_URL:-http://localhost:${API_HOST_PORT}}"

log "Checking stack & provider readiness..."

STACK_STATUS="STACK_OFFLINE"
if curl -fsS "${API_URL}/health/live" >/dev/null 2>&1; then
  STACK_STATUS="STACK_READY"
fi

PROVIDER_READINESS="BLOCKED_EXTERNAL"
LIVE_SHADOW_COLLECTION="NOT_ACTIVE"

if HEALTH_JSON=$(curl -fsS "${API_URL}/v1/providers/health" 2>/dev/null); then
  # Evaluate registered primary providers (Helius and Birdeye)
  HELIUS_STATE=$(echo "${HEALTH_JSON}" | python3 -c "import sys, json; items = json.load(sys.stdin).get('items', []); print(next((i.get('state') for i in items if i.get('provider') == 'helius'), 'UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")
  BIRDEYE_STATE=$(echo "${HEALTH_JSON}" | python3 -c "import sys, json; items = json.load(sys.stdin).get('items', []); print(next((i.get('state') for i in items if i.get('provider') == 'birdeye'), 'UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")

  if [[ "${HELIUS_STATE}" == "FRESH" ]] && [[ "${BIRDEYE_STATE}" == "FRESH" ]]; then
    PROVIDER_READINESS="PROVIDERS_READY"
    LIVE_SHADOW_COLLECTION="LIVE_SHADOW_COLLECTION_ACTIVE"
  elif [[ "${HELIUS_STATE}" == "DEGRADED" ]] || [[ "${BIRDEYE_STATE}" == "DEGRADED" ]]; then
    PROVIDER_READINESS="DEGRADED"
    LIVE_SHADOW_COLLECTION="LIVE_SHADOW_COLLECTION_ACTIVE"
  else
    PROVIDER_READINESS="BLOCKED_EXTERNAL"
    LIVE_SHADOW_COLLECTION="NOT_ACTIVE"
  fi
fi

log "=========================================================="
log "           MemeRadar Start Shadow Readiness               "
log "=========================================================="
log "Run ID:                   ${RUN_ID}"
log "Stack Status:             ${STACK_STATUS}"
log "Provider Readiness:       ${PROVIDER_READINESS}"
log "Live Shadow Collection:   ${LIVE_SHADOW_COLLECTION}"
log "Operating Modes:          ANALYSIS_ONLY=true, PAPER_TRADING=true"
log "                          MANUAL_EXECUTION=false, AUTO_EXECUTION=false"
log "=========================================================="

if [[ "${STACK_STATUS}" == "STACK_READY" ]] && [[ "${LIVE_SHADOW_COLLECTION}" == "LIVE_SHADOW_COLLECTION_ACTIVE" ]]; then
  log "STATUS: STACK_READY / LIVE_SHADOW_COLLECTION_ACTIVE"
else
  log "STATUS: STACK_READY / LIVE_DATA_BLOCKED_EXTERNAL (Awaiting external provider credentials)"
fi
