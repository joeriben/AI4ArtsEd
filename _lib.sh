#!/bin/bash
# Shared by the model download scripts (download_models.sh, download_flux2.sh,
# download_flux3.sh, download_qwen.sh). Source it after SCRIPT_DIR is set:
#
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   source "$SCRIPT_DIR/_lib.sh"
#
# Defines the colour variables, download_file and check_model. The functions
# read the sourcing script's DOWNLOADER (aria2c or wget) and set its SIZE and
# MODELS_OK, as they did when every script carried its own copy.

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

download_file() {
    local url="$1"
    local output="$2"
    local part="$output.part"

    if [ -f "$output" ]; then
        echo -e "${GREEN}✓${NC} Already exists, skipping: $(basename "$output")"
        return 0
    fi

    # Into a .part file, resumed where one is left from a run that broke
    # off, and renamed only once the downloader returned success: a file
    # under its final name is a whole file. Until 2026-10-10 the bytes went
    # straight to the final name, and the next run took the fragment for
    # the model and skipped it (S-021).
    # A fragment aria2c left is the one with its control file beside it
    # ("$part.aria2", kept while the download is unfinished). aria2c
    # preallocates the whole length, so wget would take that fragment for a
    # whole file (HTTP 416, "already fully retrieved") and the rename below
    # would hand out zeros under the model's name; a fragment wget left
    # aria2c resumes from its size (-c). The one way round is struck
    # (second review of 2026-10-10).
    if [ "$DOWNLOADER" != "aria2c" ] && [ -f "$part.aria2" ]; then
        echo "Discarding a fragment of another downloader: $(basename "$part")"
        rm -f "$part" "$part.aria2"
    fi
    if [ -f "$part" ]; then
        echo "Resuming: $(basename "$output")"
    else
        echo "Downloading: $(basename "$output")"
    fi

    if [ "$DOWNLOADER" = "aria2c" ]; then
        aria2c -c -x 16 -s 16 -d "$(dirname "$output")" -o "$(basename "$part")" "$url"
    else
        wget -c "$url" -O "$part"
    fi || {
        echo -e "${RED}✗${NC} Failed to download: $(basename "$output") (what arrived stays in $(basename "$part") for the next run)"
        return 1
    }

    if [ -f "$part" ]; then
        mv "$part" "$output"
        SIZE=$(du -h "$output" | cut -f1)
        echo -e "${GREEN}✓${NC} Downloaded: $(basename "$output") ($SIZE)"
    else
        echo -e "${RED}✗${NC} Failed to download: $(basename "$output")"
        return 1
    fi
}

check_model() {
    local path="$1"
    local name="$2"

    if [ -s "$path" ]; then
        SIZE=$(du -hL "$path" | cut -f1)
        echo -e "${GREEN}✓${NC} $name ($SIZE)"
    else
        echo -e "${RED}✗${NC} $name (missing or empty)"
        MODELS_OK=false
    fi
}
