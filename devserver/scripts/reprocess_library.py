#!/usr/bin/env python3
"""Re-run the Verdichtung for the Tier-F (UNESCO) library documents.

The nine committed Tier-F files were condensed on 2026-07-04, BEFORE ed20938f
(2026-07-10) removed the max_tokens caps from the reduce/map calls and made the
analysis language a parameter instead of a hardcoded German. They therefore
carry two defects the 29 Tier-O documents do not:

  * eight English UNESCO sources were analysed into German;
  * every PROFIL was produced under a 400-token ceiling that the reasoning
    tokens were drawn from (ed20938f: "truncated the PROFIL mid-word").

This calls the CURRENT engine. It modifies no platform code.
"""
import argparse
import os
import sys
from pathlib import Path

DEV = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEV))
os.chdir(DEV)

import config                                                      # noqa: E402
from my_app.services import knowledge_processing as kp             # noqa: E402
from my_app.services.knowledge_library import _admin_parse_front_matter  # noqa: E402

LIB = Path(config.KNOWLEDGE_LIBRARY_DIR) / "unesco"
RAW = Path(config.KNOWLEDGE_ORIGINALS_DIR) / "unesco"

# process_document's docstring: "A legal instrument is never auto-detected --
# pass 'normtext' explicitly for those." These three are normative instruments.
NORMTEXT = {
    "unesco-basic-texts-of-the-2003-convention-for-the-safeguarding-of-the-intangible-cultural-heritage-2024-edition-2003",
    "unesco-uebereinkommen-ueber-den-schutz-und-die-foerderung-der-vielfalt-kultureller-ausdrucksformen-2005-deutsche-uebersetzung-2005",
    "unesco-recommendation-on-the-ethics-of-artificial-intelligence-2021",
}


def run(doc_id: str, out_dir: Path, target_lang: str) -> int:
    lib_file = LIB / (doc_id + ".md")
    raw_file = RAW / (doc_id + ".raw.md")
    if not raw_file.exists():
        print("MISSING RAW: " + str(raw_file))
        return 1
    fm = _admin_parse_front_matter(lib_file.read_text(encoding="utf-8"))
    # Never carry a previous run's provenance into a new one.
    for k in ("analyzed_at", "analysis_lang", "analysis_model"):
        fm.pop(k, None)
    raw_md = raw_file.read_text(encoding="utf-8")
    mode = "normtext" if doc_id in NORMTEXT else "standard"

    print("=" * 78)
    print(doc_id)
    print("  mode=%s  target_lang=%s  raw=%d chars  alt=%d chars"
          % (mode, target_lang, len(raw_md), len(lib_file.read_text(encoding="utf-8"))))
    print("=" * 78, flush=True)

    llm = kp.default_llm_fn()
    res = kp.process_document(
        raw_md, fm, llm=llm, mode=mode, target_lang=target_lang,
        progress=lambda m: print("   " + m, flush=True),
    )
    if res.fatal:
        print("FATAL (nothing written): " + "; ".join(res.fatal))
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (doc_id + ".md")
    out.write_text(res.markdown, encoding="utf-8")
    print("")
    print("  -> %s" % out)
    print("  ratio=%.3f  sections %d/%d emitted  glossar=%d"
          % (res.ratio, res.n_emitted_sections, res.n_content_sections, res.n_glossary))
    print("  model=%s  lang=%s  at=%s" % (res.analysis_model, res.analysis_lang, res.analyzed_at))
    for w in res.warnings:
        print("  WARN: " + w)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("doc_ids", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--lang", default="en")
    a = ap.parse_args()
    rc = 0
    for d in a.doc_ids:
        rc |= run(d, Path(a.out), a.lang)
    return rc


if __name__ == "__main__":
    sys.exit(main())
