"""Werte-Kompass (BIBLIOTHEK.md §7): committed wording, every line anchored.

The compass is the single granted exception to the no-prompt-digest doctrine
(values, not subject knowledge; committed wording). Pinned contract: the
file exists, is prompt-pure (no frontmatter, no comments), and every bullet
carries a source anchor with a year - traceable via read_knowledge.
"""
import re
from pathlib import Path

KOMPASS = (Path(__file__).resolve().parents[1] / "my_app" / "knowledge"
           / "values" / "unesco_kompass.md")


def test_kompass_exists_and_opens_as_compass():
    text = KOMPASS.read_text(encoding="utf-8").strip()
    assert text.startswith("VALUES COMPASS (UNESCO)")


def test_kompass_is_prompt_pure():
    text = KOMPASS.read_text(encoding="utf-8")
    assert not text.lstrip().startswith("---"), "no YAML frontmatter"
    assert "<!--" not in text, "no comments - the file is verbatim prompt payload"


def test_every_bullet_carries_a_source_anchor():
    text = KOMPASS.read_text(encoding="utf-8")
    bullets = [ln for ln in text.splitlines() if ln.startswith("- ")]
    assert len(bullets) >= 8
    for b in bullets:
        assert re.search(r"\(.*\b(19|20)\d{2}.*\)", b), b[:70]
