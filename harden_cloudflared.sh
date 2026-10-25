#!/bin/bash
# =============================================================================
# AI4ArtsEd — cloudflared lifeline hardening (ZERO downtime)
# =============================================================================
# cloudflared-ssh-fedora.service is ALREADY systemd-managed + enabled (boot-start)
# + Restart=on-failure. This only TIGHTENS the restart policy via a drop-in:
#   - Restart=always            (also restart on a clean exit 0)
#   - StartLimitIntervalSec=0   (never give up restarting the SSH lifeline)
#
# It does NOT stop, kill, or restart the running tunnel. daemon-reload applies the
# new policy to FUTURE restarts only. The live connection (and your SSH session)
# stays up the entire time. REQUIRES sudo. Idempotent.
# =============================================================================
set -euo pipefail

UNIT="cloudflared-ssh-fedora.service"
DROPDIR="/etc/systemd/system/${UNIT}.d"

if [ "$EUID" -ne 0 ]; then
    echo "[✗] Must run with sudo:  sudo bash $0"
    exit 1
fi

BEFORE_PID=$(systemctl show -p MainPID --value "$UNIT")
echo "Running tunnel MainPID before: $BEFORE_PID (this must NOT change)"

mkdir -p "$DROPDIR"
cat > "$DROPDIR/hardening.conf" <<'EOF'
[Unit]
# Never permanently give up restarting the SSH lifeline / public tunnel.
StartLimitIntervalSec=0

[Service]
# Restart on ANY exit (including a clean exit 0), not just failures.
Restart=always
RestartSec=5s
EOF
echo "[✓] wrote $DROPDIR/hardening.conf"

# Apply unit-definition change WITHOUT restarting the running process.
systemctl daemon-reload
echo "[✓] daemon-reload done (running tunnel untouched)"

AFTER_PID=$(systemctl show -p MainPID --value "$UNIT")
echo "Running tunnel MainPID after:  $AFTER_PID"
if [ "$BEFORE_PID" = "$AFTER_PID" ]; then
    echo "[✓] PID unchanged — no restart happened, lifeline stayed up."
else
    echo "[!] PID CHANGED — investigate (unexpected restart)."
fi

echo ""
echo "=== effective policy now ==="
systemctl show -p Restart -p RestartSec -p StartLimitIntervalSec "$UNIT"
echo ""
echo "[✓] cloudflared lifeline hardened. View logs: journalctl -fu $UNIT"
