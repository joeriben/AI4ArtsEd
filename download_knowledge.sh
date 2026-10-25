#!/bin/bash
# AI4ArtsEd DevServer - Knowledge Library (Tier F) source downloader
#
# Downloads the UNESCO source PDFs that the knowledge library's Tier F is built
# from. The PDFs are the RAW SOURCES for the ingest pipeline
# (devserver/scripts/knowledge_ingest.py) — they are NOT committed. Only the
# aufbereitete Markdown editions + cards under
# devserver/my_app/knowledge/library/unesco/ go into git (see that folder's
# ATTRIBUTION.md; UNESCO standard license CC BY-SA 3.0 IGO, per-title verify).
#
# Target: resources/knowledge_originals/unesco/  (gitignored; resources/ idiom)
# Override with KNOWLEDGE_ORIGINALS before running.
#
# ── unesdoc bot protection ────────────────────────────────────────────────
# unesdoc.unesco.org sits behind bot protection: a plain download returns an
# HTML wrapper (or 403), not the PDF. This script sends a browser User-Agent
# and then VALIDATES that each saved file is really a PDF (%PDF magic bytes).
# If a title comes back as HTML instead of a PDF, it is reported as a MANUAL
# download — open the landing URL printed for that title and save the PDF by
# hand into the target directory. This is expected for some titles; the ingest
# step does not care how the PDF arrived, only that it is present.
#
# Idempotent: re-running skips files already present as valid PDFs.
#
# Manifest (verified UNESCO Digital Library IDs unless marked). Each title lists
# its unesdoc ark id, the English multi-PDF URL, the human landing page, and its
# license note. Titles whose canonical PDF is hosted OUTSIDE unesdoc, or whose
# unesdoc id could not be verified, are carried as commented TODO entries — NOT
# guessed (per build policy).

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KNOWLEDGE_ORIGINALS="${KNOWLEDGE_ORIGINALS:-${SCRIPT_DIR}/resources/knowledge_originals/unesco}"

# Browser User-Agent — unesdoc rejects non-browser agents.
UA='Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0'

echo -e "${BLUE}=== AI4ArtsEd Knowledge Library — UNESCO Tier-F Source Downloader ===${NC}"
echo ""
echo "Target directory: $KNOWLEDGE_ORIGINALS"
echo ""

mkdir -p "$KNOWLEDGE_ORIGINALS"

MANUAL_TITLES=()
OK_TITLES=()

# download_pdf <landing_url> <pdf_url> <output_basename> <title>
# Fetches <pdf_url> with a browser UA, then checks the saved file is a real PDF.
# On HTML-instead-of-PDF (bot wall) it removes the bad file and flags the title
# for manual download via <landing_url>.
download_pdf() {
    local landing_url="$1"
    local pdf_url="$2"
    local output="${KNOWLEDGE_ORIGINALS}/$3"
    local title="$4"

    echo -e "${BLUE}•${NC} $title"

    if [ -f "$output" ] && head -c 4 "$output" | grep -q '%PDF'; then
        echo -e "  ${GREEN}✓${NC} Already present: $(basename "$output")"
        OK_TITLES+=("$title")
        echo ""
        return 0
    fi

    # -L follow redirects, -f fail on HTTP error (but we still validate content).
    curl -sL --max-time 180 -A "$UA" -o "$output" "$pdf_url" 2>/dev/null || true

    if [ -f "$output" ] && head -c 4 "$output" | grep -q '%PDF'; then
        local size
        size=$(du -h "$output" | cut -f1)
        echo -e "  ${GREEN}✓${NC} Downloaded: $(basename "$output") ($size)"
        OK_TITLES+=("$title")
    else
        rm -f "$output"
        echo -e "  ${YELLOW}⚠ Automatic download blocked (got HTML, not PDF).${NC}"
        echo -e "  ${YELLOW}  Download manually and save as:${NC} $output"
        echo -e "  ${YELLOW}  Landing page:${NC} $landing_url"
        MANUAL_TITLES+=("$title — $landing_url  →  $output")
    fi
    echo ""
}

# ── VERIFIED unesdoc titles ────────────────────────────────────────────────
# License note per title: UNESCO standard is CC BY-SA 3.0 IGO. ⚠ still verify on
# each title's copyright page during ingest (co-publications may differ);
# knowledge_ingest.py refuses to write a doc without a `lizenz` value.

# A Framework for Culture and Arts Education (2024) — pf0000390135
download_pdf \
    "https://unesdoc.unesco.org/ark:/48223/pf0000390135" \
    "https://unesdoc.unesco.org/ark:/48223/pf0000390135/PDF/390135eng.pdf.multi" \
    "unesco-framework-arts-education-2024.pdf" \
    "Framework for Culture and Arts Education (2024)"

# Guidance for generative AI in education and research (2023) — pf0000386693
download_pdf \
    "https://unesdoc.unesco.org/ark:/48223/pf0000386693" \
    "https://unesdoc.unesco.org/ark:/48223/pf0000386693/PDF/386693eng.pdf.multi" \
    "unesco-genai-guidance-education-2023.pdf" \
    "Guidance for generative AI in education and research (2023)"

# AI competency framework for students (2024) — pf0000391105
download_pdf \
    "https://unesdoc.unesco.org/ark:/48223/pf0000391105" \
    "https://unesdoc.unesco.org/ark:/48223/pf0000391105/PDF/391105eng.pdf.multi" \
    "unesco-ai-competency-students-2024.pdf" \
    "AI competency framework for students (2024)"

# AI competency framework for teachers (2024) — pf0000391104
download_pdf \
    "https://unesdoc.unesco.org/ark:/48223/pf0000391104" \
    "https://unesdoc.unesco.org/ark:/48223/pf0000391104/PDF/391104eng.pdf.multi" \
    "unesco-ai-competency-teachers-2024.pdf" \
    "AI competency framework for teachers (2024)"

# Reimagining our futures together: a new social contract for education (2021)
# — pf0000379707 (verified 2026-07-04)
download_pdf \
    "https://unesdoc.unesco.org/ark:/48223/pf0000379707" \
    "https://unesdoc.unesco.org/ark:/48223/pf0000379707/PDF/379707eng.pdf.multi" \
    "unesco-reimagining-futures-together-2021.pdf" \
    "Reimagining our futures together (2021)"

# NICHT ENTHALTEN: Seoul Agenda 2010 (pf0000190692) und Road Map 2006
# (pf0000384200) sind historische Vorgaenger, aufgegangen im Framework for
# Culture and Arts Education (2024). Die Bibliothek fuehrt keine
# Diskursgeschichte; bei Bedarf in der git-Historie.

# Recommendation on the Ethics of Artificial Intelligence (2021) — pf0000380455
# (verified 2026-07-04)
download_pdf \
    "https://unesdoc.unesco.org/ark:/48223/pf0000380455" \
    "https://unesdoc.unesco.org/ark:/48223/pf0000380455/PDF/380455eng.pdf.multi" \
    "unesco-recommendation-ethics-of-ai-2021.pdf" \
    "Recommendation on the Ethics of Artificial Intelligence (2021)"

# Basic texts of the 2005 Convention on the Protection and Promotion of the
# Diversity of Cultural Expressions — latest basic-texts edition pf0000388847
# (2005 Convention). ⚠ Confirm this is the edition wanted; earlier editions
# pf0000260710 / pf0000225383 also exist.
download_pdf \
    "https://unesdoc.unesco.org/ark:/48223/pf0000388847" \
    "https://unesdoc.unesco.org/ark:/48223/pf0000388847/PDF/388847eng.pdf.multi" \
    "unesco-convention-diversity-cultural-expressions-2005.pdf" \
    "Convention on the Diversity of Cultural Expressions (2005, basic texts)"

# ── Titles whose canonical PDF is NOT on unesdoc (hosted on ich.unesco.org /
#    unesco.org): downloaded directly. These are stable official PDFs.

# Basic Texts of the 2003 Convention for the Safeguarding of the Intangible
# Cultural Heritage — canonical PDF hosted on the ICH portal (ich.unesco.org),
# not under an unesdoc ark id. 2022 edition (verified 2026-07-04).
download_pdf \
    "https://ich.unesco.org/en/basic-texts-00503" \
    "https://ich.unesco.org/doc/src/2003_Convention_Basic_Texts-_2022_version-EN_.pdf" \
    "unesco-convention-intangible-cultural-heritage-2003.pdf" \
    "Convention for the Safeguarding of the Intangible Cultural Heritage (2003, basic texts)"

# MONDIACULT 2022 — Final Declaration. Canonical PDF hosted on unesco.org (not
# under an unesdoc ark id at time of verification, 2026-07-04).
download_pdf \
    "https://www.unesco.org/en/articles/mondiacult-2022-states-adopt-historic-declaration-culture" \
    "https://www.unesco.org/sites/default/files/medias/fichiers/2022/10/6.MONDIACULT_EN_DRAFT%20FINAL%20DECLARATION_FINAL_1.pdf" \
    "unesco-mondiacult-final-declaration-2022.pdf" \
    "MONDIACULT 2022 — Final Declaration"

# ── UNVERIFIED (do NOT guess an id) — enable after confirming the exact record.
# Uncomment and fill the ark id / PDF url once verified on unesdoc.unesco.org.
#
# # World Conference on Arts Education follow-up survey — candidate pf0000190695
# # (report on implementation of the Road Map). Verify before enabling.
# download_pdf \
#     "https://unesdoc.unesco.org/ark:/48223/pf0000190695" \
#     "https://unesdoc.unesco.org/ark:/48223/pf0000190695/PDF/190695eng.pdf.multi" \
#     "unesco-road-map-implementation-survey.pdf" \
#     "Road Map for Arts Education — implementation survey (TODO verify id)"

echo "==================================="
echo -e "${BLUE}Summary${NC}"
echo "==================================="
echo -e "${GREEN}Downloaded / present:${NC} ${#OK_TITLES[@]}"
for t in "${OK_TITLES[@]}"; do echo "  ✓ $t"; done
echo ""
if [ "${#MANUAL_TITLES[@]}" -gt 0 ]; then
    echo -e "${YELLOW}Manual download needed (unesdoc bot wall):${NC} ${#MANUAL_TITLES[@]}"
    for t in "${MANUAL_TITLES[@]}"; do echo "  ⚠ $t"; done
    echo ""
    echo "Open each landing page, download the English PDF, and save it under"
    echo "$KNOWLEDGE_ORIGINALS with the filename shown. Then re-run to verify."
fi
echo ""
echo "Next: run the ingest for the PDFs present —"
echo "  devserver/scripts/knowledge_ingest.py (see its docstring for the venv)."
