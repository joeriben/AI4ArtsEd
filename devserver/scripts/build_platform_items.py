#!/usr/bin/env python3
"""Carry the on-page explanations of the labs into one machine-readable place.

Why this exists: the Latent Lab instruments and the comparison modes explain
themselves ON the page, in the i18n catalogue, and nowhere else. Help never
sees any of it — the handbook knew eleven pages by name and not one of these
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

The names are the labels the items carry on the page (NAME_KEY), read from
every catalogue the frontend ships: the `messages` object in
public/ai4artsed-frontend/src/i18n/index.ts, read the way en.ts is read. Each
item carries them as `names: {<language>: <label>}`; `name` stays the handle
the tools find an item by. Where a catalogue holds no string of its own for a
label, the frontend shows the one of its `fallbackLocale`, and `names` carries
that one for the language. No label is written here.

Run: python3 devserver/scripts/build_platform_items.py
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EN_TS = REPO / "public/ai4artsed-frontend/src/i18n/en.ts"
# Which catalogues the frontend ships, under which language code, and which
# one it falls back to.
I18N_INDEX = EN_TS.parent / "index.ts"
OUT = REPO / "devserver/my_app/knowledge/platform_items.json"
# Read only to check that every route of the use reports reaches Help.
USE_REPORTS = REPO / "devserver/my_app/knowledge/use_reports.json"

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
    # In Cultural Knowledge & Stereotypes, where the column shows it
    # (latent_lab.vue, GROUPS: `mean` under `compare`). The id stays, per the
    # note at the top of this list.
    ("latent_lab.image.mean",         "compare",           "Mean Images",            "/latent-lab/mean-images", "latentLab.meanImages"),
    ("latent_lab.image.attention",    "latent_lab.image",  "Attention Cartography",  "/latent-lab/attention-cartography", "latentLab.attention"),
    ("latent_lab.image.fusion",       "latent_lab.image",  "Encoder Fusion",         "/latent-lab/encoder-fusion", "surrealizer"),
    ("latent_lab.image.probing",      "latent_lab.image",  "Dimension Explorer",     "/latent-lab/dimension-explorer", "latentLab.probing"),
    ("latent_lab.image.algebra",      "latent_lab.image",  "Concept Algebra",        "/latent-lab/concept-algebra", "latentLab.algebra"),
    ("latent_lab.image.composable",   "latent_lab.image",  "Composable Diffusion",   "/latent-lab/composable-diffusion", "latentLab.composable"),
    ("latent_lab.image.workbench",    "latent_lab.image",  "Encoder Fusion Workbench", "/latent-lab/fusion-workbench", "latentLab.workbench"),
    ("latent_lab.text",               "latent_lab",        "Transformers Lab",       None, "latentLab.textLab"),
    ("latent_lab.text.repeng",        "latent_lab.text",   "Representation Engineering", "/latent-lab/representation-engineering", "latentLab.textLab.repeng"),
    # Moved to the comparison category on 2026-11-06: the column shows them under
    # Cultural Knowledge & Stereotypes. The ids stay, per the note at the top.
    ("latent_lab.text.bias",          "compare",           "Bias Research 1",          "/latent-lab/bias-archaeology", "latentLab.textLab.bias"),
    ("latent_lab.text.coref",         "compare",           "Bias Research 2",          "/latent-lab/coreference-test", None),
    # Moved here from Comparison Modes on 2026-08-22. The id keeps its old
    # prefix on purpose — chat_routes.py and the lookup_place tool address an
    # item by id, and only the parent moved.
    ("compare.systemprompt",          "latent_lab.text",   "System Prompts",         "/latent-lab/system-prompts", None),
    # The two entries under System Prompts in the column (views/latent_lab.vue,
    # GROUPS: textlab), in its order. The first carries the name of the image
    # models' Model Comparison (`compare.tabs.model`).
    ("latent_lab.text.systemprompt_models", "latent_lab.text", "Model Comparison", "/latent-lab/system-prompt-across-models", "latentLab.textLab.systempromptModels"),
    ("latent_lab.text.tokens",        "latent_lab.text",   "Tokenizer",              "/latent-lab/tokenization", "latentLab.textLab.tokens"),
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

# id -> the i18n key of the label the item carries where a visitor sees it:
# its entry in the Latent Lab column (views/latent_lab.vue: the per-item key in
# GROUPS, otherwise I18N_ROOT + ".<entry>.label"), the category heading over a
# group (latentLab.tabs), and the Latent Lab tile of the start page.
NAME_KEY = {
    "latent_lab": "landing.features.latentLab.title",
    "compare": "latentLab.tabs.compare",
    "compare.model": "compare.tabs.model",
    "compare.language": "compare.tabs.language",
    "compare.vlm_analysis": "compare.tabs.vlm-analysis",
    "compare.voice": "compare.tabs.voice",
    "latent_lab.image.census": "compare.tabs.census",
    "interception": "latentLab.tabs.interception",
    "interception.models": "latentLab.interception.tabs.interception-models.label",
    "interception.template": "latentLab.interception.tabs.interception-template.label",
    "interception.poles": "latentLab.interception.tabs.interception-poles.label",
    "latent_lab.image": "latentLab.tabs.image",
    "latent_lab.image.archaeology": "latentLab.imageLab.tabs.archaeology.label",
    "latent_lab.image.mean": "latentLab.imageLab.tabs.mean.label",
    "latent_lab.image.attention": "latentLab.imageLab.tabs.attention.label",
    "latent_lab.image.fusion": "latentLab.imageLab.tabs.fusion.label",
    "latent_lab.image.probing": "latentLab.imageLab.tabs.probing.label",
    "latent_lab.image.algebra": "latentLab.imageLab.tabs.algebra.label",
    "latent_lab.image.composable": "latentLab.imageLab.tabs.composable.label",
    "latent_lab.image.workbench": "latentLab.imageLab.tabs.workbench.label",
    "latent_lab.text": "latentLab.tabs.textlab",
    "latent_lab.text.repeng": "latentLab.textLab.tabs.repeng.label",
    "latent_lab.text.bias": "latentLab.textLab.tabs.bias.label",
    "latent_lab.text.coref": "latentLab.textLab.tabs.coref.label",
    "compare.systemprompt": "latentLab.textLab.tabs.systemprompt.label",
    "latent_lab.text.systemprompt_models": "compare.tabs.model",
    "latent_lab.text.tokens": "latentLab.textLab.tabs.tokens.label",
    "latent_lab.crossmodal": "latentLab.tabs.crossmodal",
    "latent_lab.crossmodal.synth": "latentLab.crossmodal.tabs.synth.label",
    "latent_lab.crossmodal.mmaudio": "latentLab.crossmodal.tabs.mmaudio.label",
    "latent_lab.crossmodal.guidance": "latentLab.crossmodal.tabs.guidance.label",
    "latent_lab.crossmodal.reenactment": "coverBand.modeTitle",
    "training": "latentLab.loraLab.tabs.lora.label",
    "latent_lab.lora.reach": "latentLab.loraLab.tabs.reach.label",
}

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
    # These three comparison pages have no block prefix; their address stands
    # outside their block, under compare.address.<name>.
    "compare.model": (
        ("what", ("compare.address.model.story",)),
        ("how", ("compare.address.model.purpose",)),
    ),
    "compare.language": (
        ("what", ("compare.address.language.story",)),
        ("how", ("compare.address.language.purpose",)),
    ),
    "compare.vlm_analysis": (
        ("what", ("compare.address.vlm-analysis.story",)),
        ("how", ("compare.address.vlm-analysis.purpose",)),
    ),
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
    # The Latent Lab instruments written since 2026-09 name these two blocks
    # `story` and `purpose`; without them their pages explain themselves to a
    # visitor and say nothing at all to Help. Where a block carries both, the
    # address wins: it is what the page says about itself on arrival, and the
    # explain* texts are the older in-page copy.
    ("story", "what"),
    ("purpose", "how"),
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


def load_catalogue(path: Path, export: str) -> dict:
    """A catalogue is a plain object literal behind a TS export — node reads it
    as it is written, which no regex over the file would do safely."""
    src = path.read_text(encoding="utf-8").replace(f"export const {export} =", "module.exports =", 1)
    with tempfile.NamedTemporaryFile("w", suffix=".cjs", delete=False, encoding="utf-8") as f:
        f.write(src)
        tmp = f.name
    out = subprocess.run(
        ["node", "-e", f"process.stdout.write(JSON.stringify(require({json.dumps(tmp)})))"],
        capture_output=True, text=True, check=True,
    )
    Path(tmp).unlink(missing_ok=True)
    return json.loads(out.stdout)


def load_en() -> dict:
    return load_catalogue(EN_TS, "en")


def shipped_catalogues() -> tuple:
    """(code -> (file, export name), fallback code), read from i18n/index.ts:
    the `messages` object handed to createI18n, the imports that fill it, and
    its `fallbackLocale`. Raises ValueError when index.ts no longer has that
    shape."""
    src = I18N_INDEX.read_text(encoding="utf-8")
    files = dict(re.findall(r"import \{ (\w+) \} from '\./(\w+)'", src))
    messages = re.search(r"const messages = \{([^}]*)\}", src)
    fallback = re.search(r"fallbackLocale: '([\w-]+)'", src)
    if not messages or not fallback:
        raise ValueError(f"{I18N_INDEX.relative_to(REPO)}: no `messages` object or no fallbackLocale")
    out = {}
    for entry in messages.group(1).split(","):
        code, _, export = entry.strip().partition(":")
        code = code.strip().strip("'\"")
        export = export.strip() or code
        if not code:
            continue
        if export not in files:
            raise ValueError(f"{I18N_INDEX.relative_to(REPO)}: `{export}` is not imported")
        out[code] = (I18N_INDEX.parent / f"{files[export]}.ts", export)
    if fallback.group(1) not in out:
        raise ValueError(f"{I18N_INDEX.relative_to(REPO)}: fallbackLocale is not a shipped catalogue")
    return out, fallback.group(1)


def names_for(key: str, catalogues: dict, fallback: str):
    """The label at `key` in every catalogue, as the frontend resolves it: a
    string a catalogue holds is shown as it is, and where the key is missing
    the fallback catalogue's string is shown. None when the fallback catalogue
    has no string there either."""
    base = at(catalogues[fallback], key)
    if not isinstance(base, str):
        return None
    out = {}
    for code, cat in catalogues.items():
        value = at(cat, key)
        out[code] = value if isinstance(value, str) else base
    return out


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


def check_use_reports(routed: set) -> bool:
    """Every route of the use reports reaches Help: by its catalogue item, or
    as one of the record's `places` (platform_items.place_for_view /
    place_for_route). Prints the routes that do neither. A missing record is
    reported and passes; an unreadable or malformed one fails."""
    if not USE_REPORTS.exists():
        print(f"{USE_REPORTS.relative_to(REPO)} is missing; build it with devserver/scripts/build_use_reports.py")
        return True
    try:
        reports = json.loads(USE_REPORTS.read_text(encoding="utf-8"))
        placed = {p.get("route") for p in reports.get("places") or []}
        stray = [r.get("route") for r in reports.get("instruments") or []
                 if r.get("route") not in routed and r.get("route") not in placed]
    except (ValueError, AttributeError, TypeError) as e:
        print(f"{USE_REPORTS.relative_to(REPO)} cannot be read: {e}; nothing written")
        return False
    if stray:
        print("use-report routes with neither an item nor a place: " + ", ".join(stray))
    return True


def main() -> int:
    en = load_en()
    try:
        shipped, fallback = shipped_catalogues()
    except ValueError as e:
        print(f"{e}; nothing written")
        return 1
    catalogues = {code: en if path == EN_TS else load_catalogue(path, export)
                  for code, (path, export) in shipped.items()}
    kept_before = previous()
    items = []
    empty = []
    kept = []
    unnamed = []
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
        names = names_for(NAME_KEY[item_id], catalogues, fallback) if item_id in NAME_KEY else None
        if names is None:
            unnamed.append(item_id)
        else:
            entry["names"] = names
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
        items.append(entry)
        if not technical:
            empty.append(item_id)

    if unnamed:
        print("no label in the fallback catalogue for: " + ", ".join(unnamed) + "; nothing written")
        return 1
    if not check_use_reports({i.get("route") for i in items}):
        return 1
    OUT.write_text(json.dumps({
        "_source": [
            "Wording: public/ai4artsed-frontend/src/i18n/en.ts, moved unchanged. Nothing here is rewritten.",
            "Where a page carries no authored text, the wording stands here and only here; the build keeps it, field by field.",
            "Item list: the tab arrays actually rendered in image_lab.vue, latent_text_lab.vue, crossmodal_lab.vue, compare_hub.vue.",
            "names: the label each item carries on the page, from every catalogue in public/ai4artsed-frontend/src/i18n/index.ts; where a catalogue has no string of its own, the string of the frontend's fallbackLocale, as the frontend shows it. name: the handle the tools find an item by.",
            "Built by devserver/scripts/build_platform_items.py. Re-run it after the catalogue changes.",
            "The per-page annotations (what a page is about and what is learned on it) are not in here yet.",
            "Teaching scenarios and the AI-literacy mapping per route: devserver/my_app/knowledge/use_reports.json (the versioned use reports), joined by route at runtime in platform_items.py; not carried in this file since 2026-11-06.",
        ],
        "items": items,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    filled = len(items) - len(empty)
    print(f"{OUT.relative_to(REPO)}: {len(items)} items, {filled} carry text")
    if kept:
        print("kept the existing wording for: " + ", ".join(kept))
    if empty:
        print("no text found for: " + ", ".join(empty))
    return 0


if __name__ == "__main__":
    sys.exit(main())
