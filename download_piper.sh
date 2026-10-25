#!/bin/bash
# AI4ArtsEd DevServer - Piper Voice Setup
#
# Installs Piper and one or more voices for EVERY platform language
# (output config `piper_standard`, chunk `output_speech_piper`).
#
# Nothing here is committed to this repository. Piper, like ComfyUI and like
# every model on this platform, is a downloaded technology: the code lives in
# its own virtual environment, the weights live outside the working tree, and
# both are fetched by this script. The separate environment is also what keeps
# its onnxruntime and espeak-ng data from colliding with the platform's.
#
# WHY ALL TEN LANGUAGES, AND WHY MORE THAN ONE VOICE FOR SOME
#
# Piper is the only synthesiser on this platform that covers every platform
# language. Supertonic has nine of ten and no Hebrew; VoxCPM2 has eight.
# Hebrew and Ukrainian exist nowhere else here — and Ukrainian, which the other
# two answer in English, has three high-quality voices in this catalogue.
# Downloading only German would have made a property of one afternoon's file
# copying look like a property of the model.
#
# Where a language has several regional voices, several are fetched. One voice
# per language would make this platform decide, silently and once, that Spanish
# is Spain and English is the United States. Three Spanish voices from Spain,
# Mexico and Argentina put that choice in front of whoever is listening instead.
# Where the catalogue offers only one, that is itself worth hearing: "Arabic"
# here is one man from Jordan.
#
# Dataset and licence per voice are quoted from each voice's own MODEL_CARD,
# read 2026-08-10. See docs/installation/MODELS_REQUIRED.md for the table.
#
# Idempotent: safe to re-run.

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PIPER_HOME="${PIPER_HOME:-$HOME/ai/piper}"
VENV="$PIPER_HOME/venv"
MODELS="$PIPER_HOME/models"
BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main"

# path under rhasspy/piper-voices  |  what it is, from its MODEL_CARD
VOICES=(
    # Arabic — the only Arabic voice in the catalogue. Jordan.
    "ar/ar_JO/kareem/medium/ar_JO-kareem-medium"
    # Bulgarian — the only one. OHF-Voice datasets, CC0.
    "bg/bg_BG/dimitar/medium/bg_BG-dimitar-medium"
    # German — Multilingual LibriSpeech (openslr 94), CC BY 4.0. The only
    # German voice in this catalogue above 16 kHz; the rest are x_low/low and
    # would make Piper sound worse for reasons that have nothing to do with
    # what is being compared.
    "de/de_DE/mls/medium/de_DE-mls-medium"
    # German, second voice — PAVOQUE. The only German voice in this catalogue
    # whose speaker is documented as a professional: Stefan Röttig, trained
    # actor and baritone, recorded for the DFKI project of the same name. Two
    # things come with it and are not defects to be hidden. It is "low", i.e.
    # 16 kHz, and its MODEL_CARD says it was "finetuned from U.S. English Ryan
    # voice" — so this German is an American voice bent towards German. It is
    # here because the comparison is about articulation, and an amateur
    # reading at 22 kHz answers a question nobody asked. CC BY-NC-SA 4.0.
    "de/de_DE/pavoque/low/de_DE-pavoque-low"
    # English — lessac is the Blizzard 2013 voice many other Piper voices were
    # retrained from, so it is the lineage as much as a voice. cori is a
    # LibriVox reader, public domain.
    "en/en_US/lessac/high/en_US-lessac-high"
    "en/en_GB/cori/high/en_GB-cori-high"
    # Spanish — Spain (CC0), Mexico (Apache-2.0), Argentina (openslr 61,
    # CC BY-SA 4.0). Three, so that "Spanish" is not quietly Spain.
    "es/es_ES/davefx/medium/es_ES-davefx-medium"
    "es/es_MX/claude/high/es_MX-claude-high"
    "es/es_AR/daniela/high/es_AR-daniela-high"
    # French — SIWIS, University of Edinburgh datashare, CC BY 4.0.
    "fr/fr_FR/siwis/medium/fr_FR-siwis-medium"
    # Hebrew — SASPEECH gold standard (openslr 134). The ONLY Hebrew voice on
    # this platform: neither of the other two synthesisers has one.
    "he/he_IL/saspeech/medium/he_IL-saspeech-medium"
    # Korean — KSS, single speaker, CC BY-NC-SA 4.0.
    "ko/ko_KR/kss/medium/ko_KR-kss-medium"
    # Turkish — DFKI ot-data, CC BY-NC-SA 4.0.
    "tr/tr_TR/dfki/medium/tr_TR-dfki-medium"
    # Ukrainian — two of the three high-quality voices, Apache-2.0. The other
    # two synthesisers have no Ukrainian at all and answer it in English;
    # Russian is never offered in its place.
    "uk/uk_UA/tetiana/high/uk_UA-tetiana-high"
    "uk/uk_UA/mykyta/high/uk_UA-mykyta-high"
)

echo -e "${GREEN}=== Piper Setup ===${NC}"
echo "Home:   $PIPER_HOME"

# Nothing downloaded here may become committable (global rule 6). The paths
# are configurable, so a pattern in .gitignore cannot know where they point
# and this check does: a model directory inside a git working tree is
# refused, whatever it is called. It stands before the first thing is
# written, the environment included.
PROBE="$MODELS"
while [ ! -d "$PROBE" ] && [ "$PROBE" != "/" ] && [ "$PROBE" != "." ]; do
    PROBE="$(dirname "$PROBE")"
done
if TREE="$(git -C "$PROBE" rev-parse --show-toplevel 2>/dev/null)"; then
    echo -e "${RED}$MODELS lies inside the git working tree $TREE.${NC}"
    echo "Piper's weights and the corpus files are downloaded technology and"
    echo "never go into a repository. Set PIPER_HOME to a path outside it."
    exit 1
fi

if [ ! -x "$VENV/bin/piper" ]; then
    echo "Creating the Piper environment (separate from the platform's)..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" -q install --upgrade pip
    "$VENV/bin/pip" -q install piper-tts
else
    echo "Environment present."
fi

"$VENV/bin/pip" show piper-tts | sed -n '1,2p'

mkdir -p "$MODELS"
for voice in "${VOICES[@]}"; do
    stem="$(basename "$voice")"
    for suffix in ".onnx" ".onnx.json"; do
        target="$MODELS/$stem$suffix"
        if [ -s "$target" ]; then
            continue
        fi
        echo "  fetching $stem$suffix"
        curl -fSL --progress-bar -o "$target" "$BASE_URL/$voice$suffix"
    done
done

# What a corpus documents about the speakers of a multi-speaker voice, read
# by the backend from `<stem>.metainfo.txt` beside the model
# (piper_backend.py, PiperVoiceModel). Multilingual LibriSpeech lists, one
# row per chapter, the speaker's number, gender and minutes; the backend sums
# the minutes per speaker, and the comparison column names gender and amount
# in its speaker list. The file is the corpus's own (CC BY 4.0), fetched from
# the dataset's repository; without it the speakers stand by number alone, as
# the model names them. The corpus's terms: "You agree to not attempt to
# determine the identity of speakers in this dataset" - the number is shown,
# nothing is resolved from it.
#
# Fetched only for a voice that is actually installed, written to a .part
# file and moved into place on success: a download cut short would otherwise
# stay, be taken for the corpus, and put plausible wrong amounts under the
# speakers it reached. A failure here is not fatal — the voices work without
# it, and their speakers then stand by their numbers.
SPEAKER_INFO=(
    "de_DE-mls-medium|https://huggingface.co/datasets/facebook/multilingual_librispeech/resolve/main/data/mls_german/metainfo.txt"
)
for entry in "${SPEAKER_INFO[@]}"; do
    stem="${entry%%|*}"
    url="${entry#*|}"
    target="$MODELS/$stem.metainfo.txt"
    if [ ! -s "$MODELS/$stem.onnx" ] || [ -s "$target" ]; then
        continue
    fi
    echo "  fetching $stem.metainfo.txt"
    if curl -fSL --progress-bar -o "$target.part" "$url"; then
        mv "$target.part" "$target"
    else
        rm -f "$target.part"
        echo -e "${YELLOW}  $stem.metainfo.txt could not be fetched; its"
        echo -e "  speakers will stand by their numbers.${NC}"
    fi
done

echo
echo "Installed voices:"
for f in "$MODELS"/*.onnx; do
    [ -e "$f" ] || continue
    echo "  $(basename "$f" .onnx)"
done

if [ ! -x "$VENV/bin/piper" ]; then
    echo -e "${RED}piper binary missing at $VENV/bin/piper${NC}"
    exit 1
fi

echo
echo -e "${GREEN}Done.${NC}"
echo -e "${YELLOW}The DevServer finds this via PIPER_BIN and PIPER_MODEL_DIR"
echo -e "(devserver/config.py). Both default to exactly these paths.${NC}"
