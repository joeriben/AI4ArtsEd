# Attribution & License Apparatus — Tier F (UNESCO)

This directory (`library/unesco/`) holds **derivative Markdown editions** of UNESCO
publications, prepared for the AI4ArtsEd knowledge library (structured Markdown +
condensed cards + glossary, produced by `devserver/scripts/knowledge_ingest.py`).

**These files are NOT official UNESCO publications.** They are reformatted,
excerpted, and machine-assisted condensations, provided here as a study and
citation apparatus for a pedagogical tool. For the authoritative text, always
consult the original publication at the `url` given in each document's
front-matter (its UNESCO Digital Library record, https://unesdoc.unesco.org).

## Standard license: CC BY-SA 3.0 IGO

Most UNESCO publications are released under the **Creative Commons
Attribution-ShareAlike 3.0 IGO license (CC BY-SA 3.0 IGO)**:
https://creativecommons.org/licenses/by-sa/3.0/igo/

Under this license, derivative editions may be redistributed provided that:

1. **Attribution** — the original UNESCO source is credited (see the per-title
   attribution muster below and the `lizenz` / `url` / `titel` / `jahr` fields in
   each Markdown file's YAML front-matter).
2. **ShareAlike** — derivatives carry the same CC BY-SA 3.0 IGO license.
3. **Disclaimer** — it is stated that the derivative is *not* an official UNESCO
   publication and that UNESCO is not responsible for its content (this file, and
   the note above).
4. **No endorsement / no logo** — the UNESCO name and logo are **not** used in any
   way that implies endorsement of the derivative. No UNESCO logo appears here.

The designations employed and the presentation of material in the original
publications do not imply the expression of any opinion whatsoever on the part of
UNESCO concerning the legal status of any country, territory, city or area or of
its authorities, or concerning the delimitation of its frontiers or boundaries.
The same reservation applies, unchanged, to these derivatives.

### ⚠ Per-title license verification (required)

CC BY-SA 3.0 IGO is the UNESCO **standard**, but individual titles — especially
**co-publications** with other bodies — may carry a different license (e.g.
**CC BY-NC-SA**, or all-rights-reserved). The license actually printed on each
title (usually on the copyright page, verso of the title page) is authoritative
and MUST be transcribed into that document's `lizenz` front-matter field during
ingest. `knowledge_ingest.py` refuses to write a document without a `lizenz`
value. Where a title's license could not be verified without disproportionate
effort, the front-matter carries `lizenz: "TODO — verify per title"` and the
document is withheld (`status: draft`) until confirmed.

## Attribution muster (per title)

Each derivative Markdown file records, in its YAML front-matter, the fields needed
to build a citation. The canonical attribution string for a title is:

> UNESCO ({jahr}). *{titel}*. Paris: UNESCO. Licensed under CC BY-SA 3.0 IGO.
> {url} — Derivative edition prepared for AI4ArtsEd; not an official UNESCO
> publication.

Adjust the license clause per title where the verified `lizenz` differs from the
standard.

## Original PDFs

The source PDFs are **not** committed to the repository. They are fetched by
`download_knowledge.sh` into `resources/knowledge_originals/unesco/` (gitignored).
The manifest of titles, UNESCO Digital Library IDs, and source URLs lives in that
script.
