#!/usr/bin/env bash
# Night runner for the workshop replay suite (introduced 2026-08-18).
#
# Why this exists — each point learned the hard way in review:
#   * 260305 defaults to --port 17801 (production). On the dev machine nothing
#     listens there and the script EXITS 0 after a failed health check — the
#     suite would silently lose its only qwen_img2img samples. Every script is
#     started with an explicit --port.
#   * A wedged GPU service (VRAM/CUDA wedge, stays connected, answers nothing)
#     burns each in-flight request to its full client cap. The wall-clock
#     bound per script keeps one wedge from consuming the whole night, and the
#     health gate between scripts stops the suite instead of queueing five
#     scripts against a dead card. The GPU service health route is
#     /api/health (NOT /health — that 404s) and it touches torch.cuda, so a
#     CUDA hang really trips the gate. Two wedge classes still pass it:
#     a ComfyUI execution wedge and the fail-fast VRAM-OOM state — which is
#     why rc=0 in this log is NOT evidence of usable data; the per-script
#     summaries echoed below are.
#   * Client-aborted requests can leave waitress threads parked in gate waits;
#     the health gate RETRIES for up to 10 minutes before giving up, so a
#     recovering server is waited for, not skipped.
#   * A script that cannot reach its backend prints "ERROR: Cannot reach" and
#     exits 0 — the runner greps for that, or a clean rc would also mean
#     "never ran".
#
# Logs go OUTSIDE the repo (they contain course prompts): /var/tmp/ai4artsed/.
set -u
cd "$(dirname "$0")"

PORT=17802
PER_SCRIPT_WALLCLOCK="3h"
LOGDIR=/var/tmp/ai4artsed/replay_$(date +%Y%m%d_%H%M)
mkdir -p "$LOGDIR"
SCRIPTS="260305 260306 260319 260320 260327"

log() { echo "[SUITE] $(date +%H:%M:%S) $*" | tee -a "$LOGDIR/suite.log"; }

health_wait() {
    # All three backends, retried for up to 10 minutes.
    local deadline=$(( $(date +%s) + 600 ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
        if curl -sf -m 5 "http://localhost:${PORT}/health" >/dev/null \
           && curl -sf -m 5 "http://localhost:17803/api/health" >/dev/null \
           && curl -sf -m 5 "http://127.0.0.1:17804/system_stats" >/dev/null; then
            return 0
        fi
        sleep 15
    done
    return 1
}

night_room() {
    # True until 03:30. Evening hours (>= 20:00) always count as room.
    [ "$(date +%H)" -ge 20 ] || [ "$(date +%H%M)" -lt "0330" ]
}

run_pass() {
    local pass="$1"
    for n in $SCRIPTS; do
        if [ "$pass" -ge 2 ] && ! night_room; then
            log "03:30 reached — pass ${pass} stops before ${n}, the morning does not inherit a run"
            return 0
        fi
        if ! health_wait; then
            log "backends not healthy — stopping before ${n} (pass ${pass})"
            return 1
        fi
        log "start ${n} (pass ${pass})"
        timeout "$PER_SCRIPT_WALLCLOCK" python3 "simulate_workshop_${n}.py" --port "$PORT" \
            >"$LOGDIR/${n}_pass${pass}.log" 2>&1
        rc=$?
        log "done  ${n} (pass ${pass}) rc=${rc}"
        if [ "$rc" -eq 124 ]; then
            log "${n} hit the ${PER_SCRIPT_WALLCLOCK} wall clock — server-side work may still be draining"
        fi
        if grep -q "ERROR: Cannot reach" "$LOGDIR/${n}_pass${pass}.log"; then
            log "!! ${n} NEVER RAN (could not reach its backend) despite rc=${rc}"
        fi
        tail -6 "$LOGDIR/${n}_pass${pass}.log" | sed "s/^/[${n}|p${pass}] /" >> "$LOGDIR/suite.log"
    done
    return 0
}

run_pass 1 || exit 1

# Second pass only if the night still has room: it fills the warm buckets the
# first pass left cold. The 03:30 cut is enforced before EVERY pass-2 script.
if night_room; then
    run_pass 2 || exit 1
fi
log "finished — logs in $LOGDIR"
