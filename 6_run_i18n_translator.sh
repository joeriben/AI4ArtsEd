#!/bin/bash
# 6 — Run i18n Batch Translator (nightly, unattended)
# Processes pending work orders + auto-detects missing keys
# Runs without permission prompts — safe for AFK / cron usage
#
# Usage:
#   ./6_run_i18n_translator.sh           # foreground (interactive terminal)
#   ./6_run_i18n_translator.sh --unattended # tmux session + log file (cron/AFK)

cd "$(dirname "$0")"

LOGDIR="logs/i18n"
mkdir -p "$LOGDIR"
LOGFILE="$LOGDIR/$(date +%Y%m%d_%H%M%S).log"

PROMPT="You are the i18n batch translator. Follow the workflow in .claude/agents/i18n-translator.md exactly: 1) Run the auto-audit (compare en.ts keys vs all 9 target files). 2) Process all pending work orders from WORK_ORDERS.md. 3) Translate any missing keys found by the audit. 4) Run apostrophe validation, type-check, build. 5) Move completed WOs, commit with chore(i18n): prefix. Target languages: de/tr/ko/uk/fr/es/he/ar/bg (9 total)."

CLAUDE_OPTS=(
    -p
    --verbose
    --permission-mode bypassPermissions
    --model sonnet
    --allowedTools "Read,Edit,Write,Bash,Glob,Grep"
)
# Uncomment for debug output (when troubleshooting hangs):
# CLAUDE_OPTS+=(--debug --verbose)

# Allow running from within a Claude Code session
unset CLAUDECODE

if [[ "$1" == "--unattended" ]]; then
    echo "=== i18n Unattended Translator ==="
    echo "Log: $LOGFILE"
    echo "tmux session: i18n-nightly"

    WORKDIR="$(pwd)"
    tmux new-session -d -s i18n-nightly \
        "cd $WORKDIR && echo '$PROMPT' | claude ${CLAUDE_OPTS[*]} 2>&1 | tee $LOGFILE; echo; echo '=== Done ==='; sleep 86400" \
    && echo "Started. Attach with: tmux attach -t i18n-nightly" \
    || echo "Failed to start tmux session (already running?)"
else
    echo "=== i18n Batch Translator (interactive) ==="
    echo "Processing: audit all 8 target languages, translate pending work orders"
    echo "Model: sonnet | Mode: bypassPermissions"
    echo "Log: $LOGFILE"
    echo ""
    echo "Running... (output appears when Claude responds)"
    echo ""

    echo "$PROMPT" | claude "${CLAUDE_OPTS[@]}" 2>&1 | tee "$LOGFILE"
fi
