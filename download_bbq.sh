#!/bin/bash
# AI4ArtsEd DevServer - BBQ downloader (Bias Archaeology)
#
# Fetches the Bias Benchmark for QA: Parrish, Chen, Nangia, Padmakumar, Phang,
# Thompson, Htut and Bowman, "BBQ: A Hand-Built Bias Benchmark for Question
# Answering", Findings of ACL 2022, pages 2086-2105. Released under CC BY 4.0 at
# https://github.com/nyu-mll/BBQ.
#
# 58,492 questions in eleven categories, plus the per-example metadata file that
# says WHICH of the three answers reflects the bias (target_loc). Both are needed:
# without the metadata the instrument would have to decide for itself what counts
# as a stereotype, which is exactly what it must not do.
#
# Target: resources/bbq/  (gitignored; the resources/ idiom of this repo). The
# dataset is downloadable material and does not belong in the repository - the
# loader reads it from here and says so plainly when it is missing.
#
# Idempotent: re-running skips what is already there. Pass --force to refetch.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${BBQ_DIR:-${SCRIPT_DIR}/resources/bbq}"
REPO="https://github.com/nyu-mll/BBQ.git"

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

FILES=(
  "data/Age.jsonl"
  "data/Disability_status.jsonl"
  "data/Gender_identity.jsonl"
  "data/Nationality.jsonl"
  "data/Physical_appearance.jsonl"
  "data/Race_ethnicity.jsonl"
  "data/Race_x_gender.jsonl"
  "data/Race_x_SES.jsonl"
  "data/Religion.jsonl"
  "data/SES.jsonl"
  "data/Sexual_orientation.jsonl"
  "analysis_scripts/additional_metadata.csv"
  "LICENSE"
)

have_all() {
  for f in "${FILES[@]}"; do
    [ -s "${TARGET}/${f}" ] || return 1
  done
  return 0
}

if [ "$FORCE" -eq 0 ] && have_all; then
  echo "BBQ already present in ${TARGET} - nothing to do (--force to refetch)."
  exit 0
fi

echo "Fetching BBQ into ${TARGET}"
mkdir -p "${TARGET}"

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

git clone --depth 1 --quiet "${REPO}" "${TMP}/BBQ"

for f in "${FILES[@]}"; do
  mkdir -p "${TARGET}/$(dirname "${f}")"
  cp "${TMP}/BBQ/${f}" "${TARGET}/${f}"
  printf '  %-46s %s\n' "${f}" "$(wc -l < "${TARGET}/${f}") lines"
done

cat > "${TARGET}/PROVENANCE.txt" <<'EOF'
BBQ - Bias Benchmark for Question Answering

Parrish, Chen, Nangia, Padmakumar, Phang, Thompson, Htut, Bowman:
"BBQ: A Hand-Built Bias Benchmark for Question Answering",
Findings of the Association for Computational Linguistics: ACL 2022, 2086-2105.
https://aclanthology.org/2022.findings-acl.165/
Data: https://github.com/nyu-mll/BBQ, licence CC BY 4.0 (see LICENSE).

Two parts are used here:
  data/*.jsonl                          the questions
  analysis_scripts/additional_metadata.csv   target_loc per example - which of the
                                        three answers reflects the bias. It is
                                        polarity-specific: for "who was the
                                        secretary?" it points at the stereotyped
                                        group, for "who was the board chair?" at
                                        the other one.

Nothing in here is edited by this platform. Every selection this platform makes
is recorded in the instrument, not in this directory.
EOF

echo
echo "Done. ${TARGET}"
echo "The instrument reads it through devserver/my_app/services/bbq_corpus.py."
