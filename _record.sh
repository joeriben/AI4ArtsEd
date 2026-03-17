#!/bin/bash
# Terminal recording helper for AI4ArtsEd services.
# Source this from a startup script AFTER setting RECORD_SERVICE_NAME.
# When RECORD=1, all subsequent stdout/stderr is tee'd to a protocol file.
#
# Usage (in startup script):
#   RECORD_SERVICE_NAME="backend"
#   source "$SCRIPT_DIR/_record.sh"
#
# Environment:
#   RECORD=1              - Enable recording (default: ON for production, OFF for dev)
#   RECORD_MODE=prod|dev  - Force protocol directory (default: auto-detect from SCRIPT_DIR)
#   RECORD_SERVICE_NAME   - Service name for filename (REQUIRED if RECORD=1)

_setup_recording() {
    # Auto-detect default: production records by default, dev is opt-in
    local default="0"
    if [[ "${SCRIPT_DIR:-}" =~ production ]]; then
        default="1"
    fi

    if [[ "${RECORD:-$default}" != "1" ]]; then
        return
    fi

    if [[ -z "${RECORD_SERVICE_NAME:-}" ]]; then
        echo "WARNING: RECORD=1 but RECORD_SERVICE_NAME not set. Recording disabled."
        return
    fi

    # Determine mode (prod/dev)
    local mode="${RECORD_MODE:-}"
    if [[ -z "$mode" ]]; then
        if [[ "${SCRIPT_DIR:-}" =~ production ]]; then
            mode="prod"
        elif [[ "${SCRIPT_DIR:-}" =~ develop ]]; then
            mode="dev"
        else
            mode="prod"
        fi
    fi

    # Map mode to directory
    local base_dir="$HOME/Documents/AI4ArtsEd_technische_Protokolle"
    local proto_dir
    if [[ "$mode" == "prod" ]]; then
        proto_dir="$base_dir/ai4artsed_production"
    else
        proto_dir="$base_dir/ai4artsed_development"
    fi
    mkdir -p "$proto_dir"

    # Build filename: Teilprotokoll {D} {M} {YYYY} {service}.txt (unpadded day/month)
    local logfile="$proto_dir/Teilprotokoll $(date +'%-d %-m %Y') ${RECORD_SERVICE_NAME}.txt"

    # Append restart separator if file already exists and is non-empty
    if [[ -s "$logfile" ]]; then
        echo "" >> "$logfile"
        echo "=== RESTART $(date +%Y-%m-%dT%H:%M:%S) ===" >> "$logfile"
        echo "" >> "$logfile"
    fi

    # Redirect all subsequent stdout+stderr through tee (append mode)
    exec > >(tee -a "$logfile") 2>&1

    echo "[Recording to: $logfile]"
}

_setup_recording
