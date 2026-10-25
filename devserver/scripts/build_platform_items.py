#!/usr/bin/env python3
"""Carry the on-page explanations of the labs into one machine-readable place.

Why this exists: the Latent Lab instruments and the comparison modes explain
themselves ON the page, in the i18n catalogue, and nowhere else. Help never
sees any of it — the handbook knows eleven pages by name and not one of these
twenty-four. Once those texts are taken off the pages, the descriptions are
gone with them, so they are moved here first and the pages are emptied after.

The item, not the route, is the unit. Since 2026-08-19 every instrument DOES
have an address of its own — /latent-lab/<instrument> — and it stands here, so
an answer can name the door as well as the thing behind it. The five categories
have none: they are groupings in one column and may be regrouped without
breaking a link. The id still carries the nesting, and it is the id the rest of
the platform addresses an item by; the addresses are the changeable side.

Source of the wording: public/ai4artsed-frontend/src/i18n/en.ts, the authored
catalogue — never de.ts, which is derived from it. Nothing is rewritten here;
this is a move, not an edit. What the pages said is what the file says.

Run: python3 devserver/scripts/build_platform_items.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EN_TS = REPO / "public/ai4artsed-frontend/src/i18n/en.ts"
OUT = REPO / "devserver/my_app/knowledge/platform_items.json"
AILIT = REPO / "devserver/my_app/knowledge/ailit_coverage.json"

# id -> (parent, name, route, i18n prefix)
# The instrument lists are the tab arrays actually rendered:
# compare_hub.vue, image_lab.vue, latent_text_lab.vue, crossmodal_lab.vue, and
# TrainingView.vue, which is one instrument and one category at once.
#
# The ids are NOT renamed when a category moves. `compare.*` kept its ids when
# Comparison Modes became the first category of the lab, because chat_routes.py
# and the lookup_place tool address items by id; the parent is what moved.
ITEMS = [
    ("latent_lab",                    None,                "Latent Lab",             "/latent-lab", None),
    ("compare",                       "latent_lab",        "Compare and Analyse",    None, None),
    # The four names below are the labels the tabs carry, verbatim. They read
    # "Model Bias", "Culture Bias", "Image Understanding" and "Voices" until
    # 2026-08-26, so the assistant named places the visitor could not find.
    ("compare.model",                 "compare",           "AI Model Comparison",    "/latent-lab/model-comparison", None),
    ("compare.language",              "compare",           "AI Language Understanding", "/latent-lab/language-understanding", None),
    ("compare.vlm_analysis",          "compare",           "AI Image Understanding", "/latent-lab/image-understanding", None),
    ("compare.voice",                 "compare",           "AI Voice Comparison",    "/latent-lab/voices", None),
    # Built in the Image Lab as Default Census and moved here under its
    # current name. The id keeps its `latent_lab.image.` stem, per the note
    # at the top of this list: a move changes the parent, never the id.
    ("latent_lab.image.census",       "compare",           "AI Cultural Understanding", "/latent-lab/cultural-un-known", "latentLab.census"),
    # The group that puts the platform's own central operation up as a series.
    # It has no explanation block of its own beyond the instrument's; the
    # category is a grouping in one column, like Comparison Modes, so it carries
    # no address.
    ("interception",                  "latent_lab",        "Prompt Interception",    None, None),
    ("interception.models",           "interception",      "Interception across Models", "/latent-lab/interception-across-models", "latentLab.interception.models"),
    ("interception.template",         "interception",      "Perspectives on a Template", "/latent-lab/perspectives-on-a-template", "latentLab.interception.template"),
    ("interception.poles",            "interception",      "Aesthetic Poles",        "/latent-lab/aesthetic-poles", "latentLab.interception.poles"),
    ("latent_lab.image",              "latent_lab",        "Diffusion Lab",          None, "latentLab.imageLab"),
    ("latent_lab.image.archaeology",  "latent_lab.image",  "Denoising Archaeology",  "/latent-lab/denoising-archaeology", "latentLab.archaeology"),
    ("latent_lab.image.mean",         "latent_lab.image",  "Mean Images",            "/latent-lab/mean-images", "latentLab.meanImages"),
    ("latent_lab.image.attention",    "latent_lab.image",  "Attention Cartography",  "/latent-lab/attention-cartography", "latentLab.attention"),
    ("latent_lab.image.fusion",       "latent_lab.image",  "Encoder Fusion",         "/latent-lab/encoder-fusion", "surrealizer"),
    ("latent_lab.image.probing",      "latent_lab.image",  "Dimension Explorer",     "/latent-lab/dimension-explorer", "latentLab.probing"),
    ("latent_lab.image.algebra",      "latent_lab.image",  "Concept Algebra",        "/latent-lab/concept-algebra", "latentLab.algebra"),
    ("latent_lab.image.composable",   "latent_lab.image",  "Composable Diffusion",   "/latent-lab/composable-diffusion", "latentLab.composable"),
    ("latent_lab.image.workbench",    "latent_lab.image",  "Encoder Fusion Workbench", "/latent-lab/fusion-workbench", "latentLab.workbench"),
    ("latent_lab.text",               "latent_lab",        "Transformers Lab",       None, "latentLab.textLab"),
    ("latent_lab.text.repeng",        "latent_lab.text",   "Representation Engineering", "/latent-lab/representation-engineering", "latentLab.textLab.repeng"),
    ("latent_lab.text.bias",          "latent_lab.text",   "Bias Archaeology 1",       "/latent-lab/bias-archaeology", "latentLab.textLab.bias"),
    ("latent_lab.text.coref",         "latent_lab.text",   "Bias Archaeology 2",       "/latent-lab/coreference-test", None),
    # Moved here from Comparison Modes on 2026-08-22. The id keeps its old
    # prefix on purpose — chat_routes.py and the lookup_place tool address an
    # item by id, and only the parent moved.
    ("compare.systemprompt",          "latent_lab.text",   "System Prompts",         "/latent-lab/system-prompts", None),
    ("latent_lab.crossmodal",         "latent_lab",        "Crossmodal Lab",         None, "latentLab.crossmodal"),
    ("latent_lab.crossmodal.synth",   "latent_lab.crossmodal", "Latent Audio Synth", "/latent-lab/audio-synth", "latentLab.crossmodal.synth"),
    ("latent_lab.crossmodal.mmaudio", "latent_lab.crossmodal", "MMAudio",            "/latent-lab/mmaudio", "latentLab.crossmodal.mmaudio"),
    ("latent_lab.crossmodal.guidance","latent_lab.crossmodal", "ImageBind Guidance", "/latent-lab/imagebind-guidance", "latentLab.crossmodal.guidance"),
    ("latent_lab.crossmodal.reenactment", "latent_lab.crossmodal", "Re-enactment",   "/latent-lab/re-enactment", None),
    # The prefix arrived on 2026-09-09. Its block carries `story` and `purpose`
    # — the address a visitor reads on arriving — and without the prefix Help
    # knew this page by one sentence written into the file by hand.
    ("training",                      "latent_lab",        "LoRA Training",          "/latent-lab/lora-sd35", "training"),
    # Under Training, because it needs what Training makes: the four rows put
    # a finished adapter through the with-trigger / without-trigger protocol.
    ("latent_lab.lora.reach",         "training",          "LoRA Explorer",         "/latent-lab/lora-explorer", "latentLab.loraReach"),
]

# The comparison tabs have no explanation block of their own; the single
# sentence each one carries lives in the activation text of its dormant panel.
COMPARE_ACTIVATION = {
    "compare.model": "model",
    "compare.language": "language",
    "compare.vlm_analysis": "vlm-analysis",
    "compare.systemprompt": "systemprompt",
    "compare.voice": "voice",
}

# A page that speaks for itself in its own block, addressed by full key. Voices
# carries three descriptions on the page since 2026-08-26; the single
# activation sentence above is not what it says about itself.
PAGE_TEXT = {
    # What the about box at the head of LoRA Training said about duration and
    # about blocking other runs. The box is gone and its information moves to
    # Help; the two lines stay in en.ts and reach a visitor here.
    "training": (
        ("limits", ("training.info.limitationDuration",
                    "training.info.limitationBlocking")),
    ),
    "compare.voice": (
        ("what", ("compare.voice.about.body",)),
        ("technical", ("compare.voice.kind.espeak",
                       "compare.voice.kind.piper",
                       "compare.voice.kind.supertonic",
                       "compare.voice.kind.voxcpm")),
    ),
}

# i18n key -> field on the item. Left of the arrow is the catalogue, right is
# what the field is FOR, so a later reader does not have to know the catalogue.
FIELDS = [
    ("headerSubtitle", "brief"),
    ("explainWhatText", "what"),
    ("explainHowText", "how"),
    ("explainReadText", "reading"),
    ("techText", "technical"),
    ("description", "brief"),
    # Encoder Fusion is older than the explain* shape and names its blocks
    # differently; only this one instrument has these keys.
    ("infoDescription", "what"),
    ("purposeText", "how"),
    # The Latent Lab instruments written since 2026-09 name these two blocks
    # `story` and `purpose`; without them their pages explain themselves to a
    # visitor and say nothing at all to Help.
    ("story", "what"),
    ("purpose", "how"),
    # A page that states its own limit says it in its own field. Decomposition
    # was the one that did (removed 2026-09-19); the field stays for the next.
    ("infoDisclaimer", "limits"),
]

# The three Crossmodal instruments carry no subtitle in their own block. What
# stands over them on the page is the description on their tab.
TAB_BRIEF = {
    "latent_lab.crossmodal.synth": "latentLab.crossmodal.tabs.synth.description",
    "latent_lab.crossmodal.mmaudio": "latentLab.crossmodal.tabs.mmaudio.description",
    "latent_lab.crossmodal.guidance": "latentLab.crossmodal.tabs.guidance.description",
    # Three instruments whose own block holds control labels and no explanation.
    # What stands for them is the one line each says about itself elsewhere.
    "latent_lab.text.coref": "latentLab.textLab.tabs.coref.short",
    # The line under its entry in the column IS what this instrument says about
    # itself in one sentence; a second wording for the same thing would be a
    # second wording to keep true.
    "interception.models": "latentLab.interception.tabs.interception-models.short",
    "interception.template": "latentLab.interception.tabs.interception-template.short",
    "interception.poles": "latentLab.interception.tabs.interception-poles.short",
    "latent_lab.crossmodal.reenactment": "coverBand.lede",
    # `training` stood here pointing at `training.info.studioDescription`,
    # which en.ts does not have and never had - a row that read as live and
    # resolved to None. Since 2026-09-09 the page has a prefix and says what
    # it is through `story` and `purpose`; its one-line brief is the wording
    # that stands in the JSON and only there.
}


def load_en() -> dict:
    """en.ts is a plain object literal behind a TS export — node reads it as it
    is written, which no regex over the file would do safely."""
    src = EN_TS.read_text(encoding="utf-8").replace("export const en =", "module.exports =", 1)
    with tempfile.NamedTemporaryFile("w", suffix=".cjs", delete=False, encoding="utf-8") as f:
        f.write(src)
        tmp = f.name
    out = subprocess.run(
        ["node", "-e", f"process.stdout.write(JSON.stringify(require({json.dumps(tmp)})))"],
        capture_output=True, text=True, check=True,
    )
    Path(tmp).unlink(missing_ok=True)
    return json.loads(out.stdout)


def at(root: dict, path: str):
    node = root
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def previous() -> dict:
    """What the file already says, per item id. Not every item still explains
    itself on its page: where a page carries no authored text any more, the
    wording for the agent lives HERE and has no other source. Harvesting alone
    would delete it silently, so an empty harvest keeps what stands."""
    if not OUT.exists():
        return {}
    data = json.loads(OUT.read_text(encoding="utf-8"))
    return {i["id"]: i.get("technical") or {} for i in data.get("items", [])}



def load_ailit() -> dict:
    """route -> the measures of the AILit framework this place supports, in
    the framework's own wording.

    Help was asked what a page is FOR in educational terms and had nothing to
    answer with: the AILit assignments lived in two Markdown views and a JSON
    no line of code read. They are joined here by route, so the entry for the
    page somebody stands on carries the measures a course leader can run there
    with this page as the tool: the verbatim Learner Expectation and the
    verbatim "In the Classroom" scenario with their pages in the framework,
    then how this page carries the measure and a practical scenario of this
    platform (both German). Built by devserver/scripts/build_ailit_support.py.
    """
    # A missing or hollow coverage file is an error, not an empty result: the
    # build would otherwise write a catalogue in which every measure is gone,
    # exit 0, and the next commit would carry that loss without a word.
    if not AILIT.exists():
        raise SystemExit(
            f"{AILIT.relative_to(REPO)} is missing; refusing to write a catalogue "
            "without its measures. Build it with devserver/scripts/build_ailit_support.py."
        )
    data = json.loads(AILIT.read_text(encoding="utf-8"))
    by_route = data.get("by_route") or {}
    if not data.get("competences") or not any(by_route.values()):
        raise SystemExit(
            f"{AILIT.relative_to(REPO)} carries no competences or no measures in "
            "by_route; refusing to write a catalogue without its measures."
        )
    # The coverage file already carries the measures per route in the shape
    # platform_items.goals() renders (competence, level, page, expectation,
    # classroom, classroom_page, status, how_de, practice_de); the same dicts
    # serve the pages the catalogue has no entry for (platform_items.place_for_view).
    return {route: list(goals) for route, goals in by_route.items()
            if route.startswith("/") and goals}

def main() -> int:
    en = load_en()
    kept_before = previous()
    ailit = load_ailit()
    items = []
    empty = []
    kept = []
    for item_id, parent, name, route, prefix in ITEMS:
        block = at(en, prefix) if prefix else None
        technical = {}
        if isinstance(block, dict):
            for key, field in FIELDS:
                value = block.get(key)
                if isinstance(value, str) and value.strip() and field not in technical:
                    technical[field] = value
            # What used to stand at the controls. The pages keep one line each
            # now; the full wording lives on in en.ts under <key>Detail and is
            # collected here, so an answer can still be specific.
            details = [v for k, v in block.items()
                       if k.endswith("Detail") and isinstance(v, str) and v.strip()]
            if details:
                technical["hints"] = "\n\n".join(details)
        tab_brief = TAB_BRIEF.get(item_id)
        if tab_brief:
            value = at(en, tab_brief)
            if isinstance(value, str) and value.strip():
                technical["brief"] = value
        act = COMPARE_ACTIVATION.get(item_id)
        if act:
            value = at(en, "compare.activation." + act)
            if isinstance(value, str) and value.strip():
                technical["brief"] = value
        page = PAGE_TEXT.get(item_id)
        if page:
            for field, keys in page:
                parts = [at(en, k) for k in keys]
                parts = [x for x in parts if isinstance(x, str) and x.strip()]
                if parts:
                    technical[field] = "\n\n".join(parts)
            # Harvested field by field, so the file keeps field by field: a
            # brief with no sentence of its own on the page stands here.
            for field, value in (kept_before.get(item_id) or {}).items():
                technical.setdefault(field, value)
        entry = {"id": item_id, "parent": parent, "name": name}
        if route:
            entry["route"] = route
        if prefix:
            entry["i18n"] = prefix
        # Field by field, not all-or-nothing: an item whose page yields ONE
        # harvested line (the comparison tabs yield `brief` and nothing else)
        # would otherwise drop every field written for Help by hand on the next
        # run. The harvest still wins wherever it produces something, so a
        # changed page still changes the file.
        before = kept_before.get(item_id) or {}
        if before:
            missing = [f for f in before if f not in technical]
            for field in missing:
                technical[field] = before[field]
            if missing:
                kept.append(item_id)
        entry["technical"] = technical
        goals = ailit.get(route) if route else None
        if goals:
            entry["ailit"] = {
                "framework": ("AILit — Empowering learners for the age of AI, "
                              "OECD / European Union (2026), "
                              "https://doi.org/10.1787/65cd27d4-en, CC BY 4.0"),
                "goals": goals,
            }
        items.append(entry)
        if not technical:
            empty.append(item_id)

    OUT.write_text(json.dumps({
        "_source": [
            "Wording: public/ai4artsed-frontend/src/i18n/en.ts, moved unchanged. Nothing here is rewritten.",
            "Where a page carries no authored text, the wording stands here and only here; the build keeps it, field by field.",
            "Item list: the tab arrays actually rendered in image_lab.vue, latent_text_lab.vue, crossmodal_lab.vue, compare_hub.vue.",
            "Built by devserver/scripts/build_platform_items.py. Re-run it after the catalogue changes.",
            "The per-page annotations (what a page is about and what is learned on it) are not in here yet.",
            "AI-literacy measures per route: devserver/my_app/knowledge/ailit_coverage.json, joined by route. Verbatim Learner Expectations and 'In the Classroom' scenarios (OECD/EU 2026, CC BY 4.0); which page supports which measure, and how, is this platform's own reading (docs/ailit/QUELLE.md).",
        ],
        "items": items,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    filled = len(items) - len(empty)
    print(f"{OUT.relative_to(REPO)}: {len(items)} items, {filled} carry text")
    with_ailit = sum(1 for i in items if i.get("ailit"))
    print(f"AI-literacy measures attached to {with_ailit} of {len(items)} items")
    # A coverage route with no item is served by the coverage file itself
    # (platform_items.place_for_view / place_for_route: the modes and the two
    # lab pages without an info box). Say which, every time: a renamed route
    # on either side would otherwise drop a page's measures and lower the
    # count above by one, which nobody reads.
    routed = {i.get("route") for i in items}
    unmatched = {r: len(g) for r, g in ailit.items() if r not in routed}
    if unmatched:
        print("coverage routes without an item, served from the coverage file: "
              + ", ".join(f"{r} ({n})" for r, n in sorted(unmatched.items())))
    if kept:
        print("kept the existing wording for: " + ", ".join(kept))
    if empty:
        print("no text found for: " + ", ".join(empty))
    return 0


if __name__ == "__main__":
    sys.exit(main())
