#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# MemeRadar — Codex Autonomous Validation Runner
#
# Features:
#   - LOCAL ONLY
#   - RESUMABLE CODEX SESSION
#   - PERSISTENT STATE
#   - SAFE AFTER REBOOT / SESSION DROP
#   - USAGE LIMIT DETECTION
#   - CHECKPOINT RECOVERY
#   - SINGLE INSTANCE LOCK
#   - TELEGRAM NOTIFICATION
# ============================================================

REPO="/home/ubra/codex/MemeRadar"
PROMPT_FILE="$REPO/prompts/MemeRadar.md"

CODEX_DIR="$REPO/.codex"
LOG_DIR="$CODEX_DIR/logs"
RUNTIME_DIR="$CODEX_DIR/runtime"

TELEGRAM_ENV="$CODEX_DIR/telegram.env"

SESSION_FILE="$RUNTIME_DIR/session_id"
STATE_FILE="$RUNTIME_DIR/runner.state"
LOCK_FILE="$RUNTIME_DIR/runner.lock"
LAST_LOG_LINK="$RUNTIME_DIR/latest.log"
LAST_JSON_LINK="$RUNTIME_DIR/latest.jsonl"

CURRENT_TASK_FILE="$CODEX_DIR/CURRENT_TASK.md"
VERIFICATION_FILE="$CODEX_DIR/VERIFICATION.md"

mkdir -p "$LOG_DIR" "$RUNTIME_DIR"

cd "$REPO"

# ============================================================
# Single-run protection
# ============================================================

exec 9>"$LOCK_FILE"

if ! flock -n 9; then
    echo "ERROR: Another MemeRadar Codex runner is already active."
    echo "Lock: $LOCK_FILE"
    exit 75
fi

# ============================================================
# Run metadata
# ============================================================

TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"

LOG_FILE="$LOG_DIR/codex_validation_${TIMESTAMP}.log"
JSON_FILE="$LOG_DIR/codex_validation_${TIMESTAMP}.jsonl"

START_EPOCH="$(date +%s)"
START_TIME="$(date -Is)"

CODEX_EXIT=0
FINAL_STATUS="RUNNING"
RESUME_MODE="NEW"
SESSION_ID=""
FINALIZED=0

ln -sfn "$LOG_FILE" "$LAST_LOG_LINK"
ln -sfn "$JSON_FILE" "$LAST_JSON_LINK"

# ============================================================
# Persistent state
# ============================================================

write_state() {
    local status="$1"

    cat > "${STATE_FILE}.tmp" <<EOF
STATUS=${status}
START_TIME=${START_TIME}
UPDATED_AT=$(date -Is)
PID=$$
SESSION_ID=${SESSION_ID:-}
RESUME_MODE=${RESUME_MODE}
LOG_FILE=${LOG_FILE}
JSON_FILE=${JSON_FILE}
BRANCH=$(git branch --show-current 2>/dev/null || echo UNKNOWN)
HEAD=$(git rev-parse HEAD 2>/dev/null || echo UNKNOWN)
EOF

    mv "${STATE_FILE}.tmp" "$STATE_FILE"
}

# ============================================================
# Telegram
# ============================================================

if [[ -f "$TELEGRAM_ENV" ]]; then
    # shellcheck disable=SC1090
    source "$TELEGRAM_ENV"
fi

send_telegram() {
    local message="$1"

    if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]] ||
       [[ -z "${TELEGRAM_CHAT_ID:-}" ]]; then
        echo "WARNING: Telegram configuration missing." >&2
        return 0
    fi

    curl \
        --silent \
        --show-error \
        --max-time 20 \
        --retry 2 \
        --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
        --data-urlencode "text=${message}" \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        >/dev/null || true
}

# ============================================================
# Detect likely interruption reason
# ============================================================

detect_status() {
    local exit_code="$1"

    if [[ "$exit_code" -eq 0 ]]; then
        echo "SUCCESS"
        return
    fi

    if grep -Eiq \
        'usage limit|rate.?limit|quota|token budget exhausted|rollout token budget exhausted|too many requests|429|limit reached|you have.*weighted tokens left' \
        "$LOG_FILE" "$JSON_FILE" 2>/dev/null; then

        echo "PAUSED_LIMIT"
        return
    fi

    if grep -Eiq \
        'connection reset|connection closed|broken pipe|transport.*closed|network.*error|timed out|timeout' \
        "$LOG_FILE" "$JSON_FILE" 2>/dev/null; then

        echo "PAUSED_CONNECTION"
        return
    fi

    echo "FAILED"
}

# ============================================================
# Finalization
# ============================================================

notify_finished() {
    local trap_exit_code=$?

    if [[ "$FINALIZED" -eq 1 ]]; then
        return
    fi

    FINALIZED=1

    local effective_exit="$CODEX_EXIT"

    if [[ "$effective_exit" -eq 0 && "$trap_exit_code" -ne 0 ]]; then
        effective_exit="$trap_exit_code"
    fi

    local end_epoch
    local duration
    local end_time
    local head
    local branch
    local hours
    local minutes
    local seconds

    end_epoch="$(date +%s)"
    duration=$((end_epoch - START_EPOCH))
    end_time="$(date -Is)"

    head="$(git rev-parse --short HEAD 2>/dev/null || echo UNKNOWN)"
    branch="$(git branch --show-current 2>/dev/null || echo UNKNOWN)"

    FINAL_STATUS="$(detect_status "$effective_exit")"

    write_state "$FINAL_STATUS"

    hours=$((duration / 3600))
    minutes=$(((duration % 3600) / 60))
    seconds=$((duration % 60))

    local message

    message="MemeRadar Codex runner

Status: ${FINAL_STATUS}
Exit code: ${effective_exit}

Mode: ${RESUME_MODE}
Session: ${SESSION_ID:-UNKNOWN}

Branch: ${branch}
HEAD: ${head}

Started: ${START_TIME}
Finished: ${end_time}
Duration: ${hours}h ${minutes}m ${seconds}s

Log:
${LOG_FILE}

Checkpoint:
${CURRENT_TASK_FILE}"

    send_telegram "$message"
}

trap notify_finished EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

# ============================================================
# Pre-flight
# ============================================================

for cmd in codex curl flock tee grep git awk sed; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd"
        exit 127
    fi
done

if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "ERROR: Prompt file not found:"
    echo "$PROMPT_FILE"
    exit 1
fi

# ============================================================
# Determine whether this is NEW or RESUME
# ============================================================

if [[ -s "$SESSION_FILE" ]]; then
    SESSION_ID="$(tr -d '[:space:]' < "$SESSION_FILE")"

    if [[ -n "$SESSION_ID" ]]; then
        RESUME_MODE="RESUME"
    fi
fi

write_state "STARTING"

# ============================================================
# Build continuation instruction
# ============================================================

build_resume_prompt() {

cat <<'SYSTEM_INSTRUCTIONS'

============================================================
AUTONOMOUS EXECUTION / RECOVERY INSTRUCTIONS
============================================================

You are operating as an autonomous engineering agent inside the
LOCAL MemeRadar repository.

THIS RUN MAY BE A RESUMED RUN AFTER:

- Codex usage/rate limit exhaustion
- terminal/SSH/session loss
- computer shutdown or reboot
- network interruption
- Codex process termination
- previous runner failure

The LOCAL repository and durable checkpoint files are authoritative.

DO NOT ask the user for confirmation between phases.

DO NOT stop merely because a phase is large.

DO NOT use GitHub or any remote Git operations.

NEVER run:

git push
git pull
git fetch
git remote update

============================================================
MANDATORY RECOVERY PROCEDURE
============================================================

Before doing ANY implementation work:

1. inspect:
   git status --short

2. inspect:
   git branch --show-current

3. inspect:
   git rev-parse HEAD

4. inspect recent local history:
   git log --oneline --decorate -20

5. read completely if present:
   .codex/CURRENT_TASK.md

6. read completely if present:
   .codex/VERIFICATION.md

7. read completely if present:
   docs/STRATEGY_VALIDATION_LAB.md

8. inspect relevant existing implementation and tests

9. determine exactly:
   - what was already completed
   - what was partially completed
   - what remains unresolved
   - what was verified
   - what has NOT yet been verified

10. resume from the FIRST unresolved acceptance gate.

DO NOT restart the project from Phase 0.

DO NOT redo already completed work unless:

- regression verification fails
- existing implementation is incomplete
- checkpoint evidence conflicts with repository state

The filesystem and git repository override stale conversational memory.

============================================================
DURABLE CHECKPOINT REQUIREMENT
============================================================

Update:

.codex/CURRENT_TASK.md

frequently, especially:

- before starting a major phase
- after completing a major phase
- before long test suites
- after long test suites
- before risky changes
- after important commits
- when a blocker is discovered

It must contain at least:

CURRENT_PHASE
CURRENT_TASK
STATUS
LAST_COMPLETED_STEP
NEXT_STEP
LAST_VERIFIED_HEAD
TEST_STATUS
BLOCKERS
UPDATED_AT

Also maintain:

.codex/VERIFICATION.md

with actual verification evidence.

Checkpoint files must describe REAL repository state.
Never fabricate verification.

============================================================
INTERRUPTION SAFETY
============================================================

Assume this process can terminate at ANY moment.

Therefore:

- make changes incrementally
- avoid leaving destructive half-completed migrations
- persist checkpoint state frequently
- make focused LOCAL commits when a coherent unit is complete
- do not wait until the very end to record progress

Before executing a potentially long validation/test command,
update CURRENT_TASK.md with:

STATUS=IN_PROGRESS
NEXT_STEP=<exact command or gate being executed>

After it finishes, immediately persist the result.

============================================================
EXTERNAL BLOCKERS
============================================================

If an external dependency blocks one task:

1. record the exact blocker
2. record available evidence
3. mark only that gate BLOCKED
4. continue every independent locally executable task

Do not stop the entire run because one external dependency failed.

============================================================
COMPLETION CONDITION
============================================================

Continue autonomously until either:

A. all locally executable acceptance criteria are complete

OR

B. every remaining task genuinely requires:
   - external authority
   - external provider access
   - unavailable external data
   - unavailable credentials
   - elapsed runtime evidence

Do not fabricate evidence.

At completion, update CURRENT_TASK.md and VERIFICATION.md before exiting.

============================================================
PRIMARY TASK / PROJECT SPECIFICATION
============================================================

SYSTEM_INSTRUCTIONS

cat "$PROMPT_FILE"

}

# ============================================================
# Display run information
# ============================================================

echo "============================================================"
echo "MemeRadar Codex autonomous runner"
echo
echo "Repository : $REPO"
echo "Prompt     : $PROMPT_FILE"
echo "Mode       : $RESUME_MODE"
echo "Session    : ${SESSION_ID:-NEW}"
echo "Log        : $LOG_FILE"
echo "JSON       : $JSON_FILE"
echo "Started    : $START_TIME"
echo "============================================================"

send_telegram "MemeRadar Codex started

Mode: ${RESUME_MODE}
Session: ${SESSION_ID:-NEW}

Branch: $(git branch --show-current 2>/dev/null || echo UNKNOWN)
HEAD: $(git rev-parse --short HEAD 2>/dev/null || echo UNKNOWN)

Started: ${START_TIME}"

write_state "RUNNING"

# ============================================================
# Temporary prompt file
# ============================================================

RUN_PROMPT_FILE="$RUNTIME_DIR/prompt_${TIMESTAMP}.txt"

build_resume_prompt > "$RUN_PROMPT_FILE"

# ============================================================
# Run Codex
# ============================================================
#
# IMPORTANT:
# set +e here intentionally.
#
# With:
#
#   set -e
#   set -o pipefail
#
# a non-zero Codex exit could terminate the shell BEFORE we
# capture PIPESTATUS.
# ============================================================

set +e

if [[ "$RESUME_MODE" == "RESUME" ]]; then

    echo
    echo "Resuming Codex session:"
    echo "$SESSION_ID"
    echo

    codex exec \
        -C "$REPO" \
        --json \
        resume "$SESSION_ID" \
        - < "$RUN_PROMPT_FILE" \
        > >(tee "$JSON_FILE" | tee -a "$LOG_FILE") \
        2> >(tee -a "$LOG_FILE" >&2)

    CODEX_EXIT=$?

else

    echo
    echo "Starting NEW Codex session..."
    echo

    codex exec \
        -C "$REPO" \
        --json \
        - < "$RUN_PROMPT_FILE" \
        > >(tee "$JSON_FILE" | tee -a "$LOG_FILE") \
        2> >(tee -a "$LOG_FILE" >&2)

    CODEX_EXIT=$?

fi

set -e

# ============================================================
# Capture / verify Codex thread ID
# ============================================================

DISCOVERED_SESSION_ID="$(
    grep -m1 '"type"[[:space:]]*:[[:space:]]*"thread.started"' \
        "$JSON_FILE" 2>/dev/null |
    sed -n 's/.*"thread_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p'
)"

if [[ -n "$DISCOVERED_SESSION_ID" ]]; then

    if [[ "$RESUME_MODE" == "NEW" ]]; then

        SESSION_ID="$DISCOVERED_SESSION_ID"

        printf '%s\n' "$SESSION_ID" > "${SESSION_FILE}.tmp"
        mv "${SESSION_FILE}.tmp" "$SESSION_FILE"

        echo
        echo "Saved Codex session ID:"
        echo "$SESSION_ID"

    else

        # Normally a resumed exec should remain associated with
        # the requested thread. Warn loudly if Codex reports a
        # different thread ID.
        if [[ "$DISCOVERED_SESSION_ID" != "$SESSION_ID" ]]; then
            echo
            echo "WARNING:"
            echo "Requested resume session : $SESSION_ID"
            echo "Codex reported session   : $DISCOVERED_SESSION_ID"
            echo
            echo "Possible resume fallback/new-thread condition."

            send_telegram "WARNING: MemeRadar Codex resume session mismatch

Requested:
${SESSION_ID}

Reported:
${DISCOVERED_SESSION_ID}

Check:
${LOG_FILE}"
        fi
    fi
fi

# ============================================================
# Remove transient prompt copy
# ============================================================

rm -f "$RUN_PROMPT_FILE"

# ============================================================
# Final state
# ============================================================

FINAL_STATUS="$(detect_status "$CODEX_EXIT")"

write_state "$FINAL_STATUS"

echo
echo "============================================================"
echo "MemeRadar Codex run finished"
echo
echo "Status     : $FINAL_STATUS"
echo "Exit code  : $CODEX_EXIT"
echo "Mode       : $RESUME_MODE"
echo "Session    : ${SESSION_ID:-UNKNOWN}"
echo "Finished   : $(date -Is)"
echo
echo "Log        : $LOG_FILE"
echo "JSON       : $JSON_FILE"
echo "State      : $STATE_FILE"
echo "Checkpoint : $CURRENT_TASK_FILE"
echo "============================================================"

exit "$CODEX_EXIT"
