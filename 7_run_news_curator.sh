#!/bin/bash
# 7 — Run News Curator Agent
# Extracts user-relevant changes from DEVELOPMENT_LOG.md → devserver/news.json
# Runs without permission prompts — safe for AFK / cron usage
#
# Usage:
#   ./7_run_news_curator.sh              # foreground (interactive terminal)
#   ./7_run_news_curator.sh --unattended # tmux session + log file (cron/AFK)

cd "$(dirname "$0")"

# Allow running from within a Claude Code session (unset nesting guard)
unset CLAUDECODE

LOGDIR="logs/news"
mkdir -p "$LOGDIR"
LOGFILE="$LOGDIR/$(date +%Y%m%d_%H%M%S).log"

PROMPT="You are the news curator agent. Follow .claude/agents/news-curator.md EXACTLY — it defines item count, writing style, and verification rules. Execute its Workflow section step by step. Pay special attention to step 3 (VERIFY EVERY ITEM): always verify the current state of code/configs, not just dev log entries."

CLAUDE_OPTS=(
    -p
    --permission-mode bypassPermissions
    --model haiku
    --allowedTools "Read" "Write" "Bash" "Glob" "Grep"
)

if [[ "$1" == "--unattended" ]]; then
    echo "=== News Curator (unattended) ==="
    echo "Log: $LOGFILE"
    echo "tmux session: news-curator"

    WORKDIR="$(pwd)"
    tmux new-session -d -s news-curator \
        "cd $WORKDIR && echo '$PROMPT' | claude ${CLAUDE_OPTS[*]} 2>&1 | tee $LOGFILE; echo; echo '=== Done ==='; sleep 86400" \
    && echo "Started. Attach with: tmux attach -t news-curator" \
    || echo "Failed to start tmux session (already running?)"
else
    echo "=== News Curator (interactive) ==="
    echo "Log: $LOGFILE"

    echo "$PROMPT" | claude "${CLAUDE_OPTS[@]}" 2>&1 | tee "$LOGFILE"
fi
