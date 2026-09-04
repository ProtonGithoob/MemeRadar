#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() {
  printf '[MemeRadar-Shadow] %s\n' "$*"
}

fail() {
  printf '[MemeRadar-Shadow] ERROR: %s\n' "$*" >&2
  python3 "${ROOT_DIR}/scripts/shadow_status.py" --update-run-state START_FAILED 2>/dev/null || true
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

# 3. Initialize Shadow Run Identity in PENDING State
SHADOW_ARTIFACT_DIR="${ROOT_DIR}/artifacts/research/live-shadow"
mkdir -p "${SHADOW_ARTIFACT_DIR}"

log "Initializing shadow run identity in PENDING state..."
python3 "${ROOT_DIR}/scripts/shadow_status.py" --init-run

# 4. Launch MemeRadar Services via start.sh
log "Launching MemeRadar services via scripts/start.sh..."
if ! bash "${ROOT_DIR}/scripts/start.sh"; then
  fail "Stack startup via scripts/start.sh failed."
fi

# 5. Evaluate Readiness & Output Verdict via Shared Canonical Python Service
log "Evaluating stack & provider readiness..."
python3 "${ROOT_DIR}/scripts/shadow_status.py" --evaluate-readiness
