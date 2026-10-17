"""Finding S-037 of the code review of 2026-10-10: nineteen files painted
backgrounds and borders with neutral dark literals instead of the surface
tokens of rule 7 (`--bg-base`, `--surface-1..4` and their rgb triplets), so
those surfaces did not follow the tone chosen in the settings. Every
declaration of their style blocks is read here, whatever its form (one-line
rules, a declaration on a rule's opening line, a nested @media, a value over
several lines; the second review of 2026-10-10 named the forms the first
parser missed), and the inline styles of the templates; a shadow and a text
colour are not a surface and are not read.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FE = REPO / "public" / "ai4artsed-frontend" / "src"
FILES = [
    "views/SettingsView.vue", "views/canvas_workflow.vue", "views/cover_band.vue",
    "views/AnimationTestView.vue", "components/KnowledgeLibraryTab.vue",
    "components/ModelMatrixTab.vue", "components/BackendStatusTab.vue",
    "components/ApiManagementTab.vue", "components/PlatformVoice.vue",
    "components/ChatOverlay.vue", "components/AudioRecordWidget.vue",
    "components/MediaInputBox.vue", "components/FooterGallery.vue",
    "components/DokumentationModal.vue", "components/SessionExportView.vue",
    "components/canvas/StageModule.vue", "components/canvas/ConfigSelectorModal.vue",
    "components/canvas/ZoomControls.vue", "components/canvas/OutputDrawer.vue",
]
LITERAL = re.compile(
    r"#(?:333333|333|3a3a3a|444444|444|555555|555|334155|475569|121212|0a0a1a)\b"
    r"|rgba?\(\s*0\s*,\s*0\s*,\s*0\s*[,)]"
    r"|rgb\(\s*0\s+0\s+0\s*/"
    r"|rgba?\(\s*51\s*,\s*65\s*,\s*85\s*[,)]"
    r"|rgb\(\s*51\s+65\s+85\s*/",
    re.I,
)
SURFACE = {
    "border", "border-top", "border-bottom", "border-left", "border-right",
    "border-color", "border-top-color", "border-bottom-color", "border-left-color",
    "border-right-color", "border-inline-end", "border-inline-start",
    "border-inline-end-color", "border-inline-start-color", "border-block-start",
    "border-block-end", "border-block-start-color", "border-block-end-color",
    "outline", "outline-color", "background", "background-color", "background-image",
}


def _blank_comments(css):
    """Comments struck, their line breaks kept, so line numbers stay."""
    return re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), css, flags=re.S)


def _declarations(text):
    """(line, property, value) of every declaration inside the style blocks.
    A declaration starts after `{` or `;` (or at a line start) and runs to
    the next `;` or `}`, over as many lines as it takes; the braces of a
    one-line or nested rule are no obstacle."""
    found = []
    for block in re.finditer(r"<style[^>]*>(.*?)</style>", text, flags=re.S):
        first_line = text[:block.start(1)].count("\n") + 1
        css = _blank_comments(block.group(1))
        for m in re.finditer(r"(?:(?<=[{;])|^)[ \t]*([a-zA-Z-]+)[ \t]*:[ \t]*([^;{}]+)", css, flags=re.M):
            found.append((first_line + css[:m.start(1)].count("\n"), m.group(1).lower(), m.group(2).strip()))
    return found


def _inline_styles(text):
    """(line, value) of every style="…" and :style="…" in the template."""
    return [(text[:m.start()].count("\n") + 1, m.group(1))
            for m in re.finditer(r":?style=\"([^\"]*)\"", text)]


def test_the_named_files_paint_no_neutral_dark_literal_on_a_surface():
    offenders = []
    for rel in FILES:
        text = (FE / rel).read_text(encoding="utf-8")
        for number, prop, value in _declarations(text):
            if prop in SURFACE and LITERAL.search(value):
                offenders.append(f"{rel}:{number}: {prop}: {value}")
        for number, value in _inline_styles(text):
            if LITERAL.search(value) and re.search(r"(background|border|outline)", value):
                offenders.append(f"{rel}:{number}: inline style: {value}")
    assert offenders == [], "\n".join(offenders)


def test_the_parser_reads_the_forms_the_second_review_named():
    css = ("<style scoped>\n.a { background: #333;\n  color: red; }\n"
           "@media (max-width: 480px) { .b { border: 1px solid #444; } }\n"
           ".c {\n  background:\n    linear-gradient(red, rgba(0, 0, 0, 0.8));\n}\n"
           ".d { outline-color: rgb(0 0 0 / 0.5); /* border: #555 */ }\n</style>")
    hits = [(prop, value) for _, prop, value in _declarations(css) if prop in SURFACE and LITERAL.search(value)]
    assert [p for p, _ in hits] == ["background", "border", "background", "outline-color"], hits


def test_the_tokens_the_files_name_exist():
    base = (FE / "assets" / "base.css").read_text(encoding="utf-8")
    defined = set(re.findall(r"^\s*(--(?:bg-base|surface-[1-4])(?:-rgb)?):", base, flags=re.M))
    named = set()
    for rel in FILES:
        named |= set(re.findall(r"var\((--(?:bg-base|surface-[1-4])(?:-rgb)?)\)", (FE / rel).read_text(encoding="utf-8")))
    assert named, "no file names a surface token"
    assert named <= defined, sorted(named - defined)
