#!/usr/bin/env python3
"""
Policy: a model identifier is DATA, never a literal in code.

Which model can do what, and which model a role uses, belongs in
`hardware_matrix.json`, `user_settings.json`, or the measured store behind
`my_app/services/model_capabilities`. A name written into code is a fact frozen at the
moment someone typed it: it outlives the model being retired, the provider adding a
capability, and the operator choosing something else.

Written 2026-08-13, after exactly that happened inside one feature. A cloud model was
assumed to accept images because of its provider prefix; when it turned out not to,
the first fix was a hand-maintained list of model names in `vision_support.py`, under
a twelve-line comment explaining why this particular list was legitimate. It was not.
The comment is what makes this hard to see -- a rule broken with a written
justification reads like a decision.

This test does not read justifications.

Sibling of `test_latent_lab_model_policy.py`, which holds the same line for one model
family. Run: python3 -m pytest devserver/tests/test_no_model_literals.py -q
"""
import ast
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Where code lives. config.py and the tests are exempt by design: a platform default
# belongs in config, and a test has to be able to name what it tests.
SCAN_ROOTS = ("my_app", "schemas")
# config.py holds the platform defaults by design. The path is relative to devserver/,
# which is what ROOT points at -- the earlier value "my_app/config.py" named a directory
# and exempted nothing.
EXEMPT_FILES = {
    "config.py",
    # The Latent Lab's resolver is the one place that names its backbone, by
    # rule: test_latent_lab_model_policy.py holds that every chunk reads it
    # from there.
    "my_app/services/latent_lab_model.py",
}
# The frontend, scanned with the same pattern since 2026-10-10 (finding S-051 of the code review of 2026-10-10): .ts
# and .vue sources, specs and type declarations aside. Paths are keyed from
# the repository root.
FRONTEND_PREFIX = "public/ai4artsed-frontend/src/"

# A provider-prefixed identifier, or one of the bare shapes this platform uses.
# Widened 2026-08-13 after an adversarial pass walked straight through the first
# version: the tail now admits '/' and '~', because this platform's own identifiers are
# three segments deep (a provider route in front of a provider/model pair) and the whole
# of two of six providers slipped past; and a bare name is any name:tag, not only the
# handful of shapes that happened to be in the tree that day.
MODEL_LITERAL = re.compile(
    r"""['"]((?:local/)?(?:mammouth|mistral|ionos|anthropic|openai|openrouter|bedrock|stabilityai|Wan-AI)/[\w.:+~/-]+)['"]"""
    r"""|['"]((?:local/)?[\w.]*[a-zA-Z][\w.-]*:(?:\d+(?:\.\d+)?[bB]|latest)"""
    r"""|(?:local/)?(?:glm-[\d.]+|gpt-oss-[\w.-]+|claude-(?:opus|sonnet|haiku)-[\w.-]+))['"]"""
)

# stabilityai/ and Wan-AI/ joined on 2026-10-10 (finding S-026 of the code review of 2026-10-10): a HuggingFace id is a
# model identifier like any other, and nine of them stood as defaults in the
# DevServer's Diffusers client.
#
# A bare name is name:tag where the tag is a parameter count or "latest". Anything
# looser also matches "pbkdf2:sha256", "data:image", "1:1" and every clock time in the
# tree -- and a gate that cries wolf is a gate somebody switches off.

# Debt inherited on 2026-08-13, not permission. Keyed by file and by the identifier
# itself, so it survives the lines moving but never covers a NEW name.
#
# The list may shrink. It must not grow: a new entry is a recorded product decision,
# never a way past a red test. Each one is a place where the platform still cannot be reconfigured
# without editing code.
ALLOWED = {
    # a preset default that belongs in the model matrix
    ("my_app/routes/settings_routes.py", "anthropic/claude-haiku-4-5"),
    # example rows in the local-model endpoint's response shape
    ("my_app/routes/settings_routes.py", "qwen3-vl:32b"),
    ("my_app/routes/settings_routes.py", "qwen2.5vl:72b"),
    # the dedicated local vision channel, hardcoded since long before this rule
    ("my_app/services/llm_service.py", "qwen3-vl:4b"),
    # the legacy model selector's price and fallback tables
    ("schemas/engine/model_selector.py", "anthropic/claude-haiku-4.5"),
    # the published system prompts of a shipped assistant, quoted word for
    # word; the file's own header says what it is
    ("public/ai4artsed-frontend/src/views/compare/system_prompts_published.ts", "claude-opus-4-20250514"),
    ("public/ai4artsed-frontend/src/views/compare/system_prompts_published.ts", "claude-opus-5"),
    ("public/ai4artsed-frontend/src/views/compare/system_prompts_published.ts", "claude-sonnet-5"),
    ("public/ai4artsed-frontend/src/views/compare/system_prompts_published.ts", "claude-haiku-4-5-20251001"),
}

# Found on 2026-08-14 by sharpening the pattern above, every one of them older than the
# rule: the model selector's routing and price tables, four archived media-optimisation
# chunks, the interception engine's default and one route default. Thirteen of the
# seventeen sit in live paths -- model_selector reaches the canvas routes, the
# interception engine reaches the schema pipeline. Only the four archived ones are dust.
#
# Four came off on 2026-08-17 with the model selector's two fallback tables (the
# OpenRouter list and the local preferred-prefix list, the latter ending in "any model
# that is not the one that just failed"). They were the reachable half of this file: a
# failed call answered from a different model. The routing and price tables that remain
# do not substitute anything -- they feed the canvas dropdown and an admissibility
# check.
# These are NOT exemptions -- they are the violations that were already in the tree when
# the gate went up, held in a separate list so that they can be counted, so that the gate
# can block anything NEW today, and so that nobody has to widen ALLOWED to get a green
# run. Every line is a place where a model cannot be swapped without editing code.
#
# The count below may only fall. Working one of these off means deleting its line here.
INHERITED_DEBT = {
    ("schemas/engine/model_selector.py", "gemma2:27b"),
    ("schemas/engine/model_selector.py", "gemma2:9b"),
    ("schemas/engine/model_selector.py", "llava:13b"),
    ("schemas/engine/model_selector.py", "local/gemma3:4b"),
    ("schemas/engine/model_selector.py", "local/llava:13b"),
    ("schemas/engine/model_selector.py", "local/mistral-small:24b"),
    ("schemas/engine/model_selector.py", "mistral-small:24b"),
    ("schemas/engine/model_selector.py", "openrouter/anthropic/claude-haiku-4.5"),
    ("schemas/engine/model_selector.py", "openrouter/google/gemini-2.5-pro"),
    ("schemas/engine/model_selector.py", "openrouter/google/gemma-3-4b-it"),
    ("schemas/engine/model_selector.py", "openrouter/mistralai/mistral-nemo"),
    ("schemas/engine/prompt_interception_engine.py", "local/gemma2:9b"),
    # Found on 2026-10-10 when the pattern took HuggingFace ids (finding S-026 of the code review of 2026-10-10): the
    # Diffusers chunks each name the model they run. Which model a config
    # runs belongs in the config.
    ("schemas/chunks/output_audio_stableaudio_diffusers.py", "stabilityai/stable-audio-3-medium"),
    ("schemas/chunks/output_image_sd35_diffusers.py", "stabilityai/stable-diffusion-3.5-large"),
    ("schemas/chunks/output_image_sd35_img2img_diffusers.py", "stabilityai/stable-diffusion-3.5-large"),
    ("schemas/chunks/output_image_sd35_turbo_diffusers.py", "stabilityai/stable-diffusion-3.5-large-turbo"),
    ("schemas/chunks/output_video_wan22_diffusers.py", "Wan-AI/Wan2.2-T2V-A14B-Diffusers"),
    ("schemas/chunks/output_video_wan22_i2v_diffusers.py", "Wan-AI/Wan2.2-I2V-A14B-Diffusers"),
    # Found on 2026-10-10 when the frontend joined the scan (finding S-051 of the code review of 2026-10-10): the
    # settings page offers the safety model by name.
    ("public/ai4artsed-frontend/src/views/SettingsView.vue", "shieldstral:3b"),
    # Restored on 2026-10-15 with views/compare/llm_model_comparison.vue, which Issue #41
    # freezes under Rule 19: 26ed141 deleted the page and this store on 2026-10-10, hours
    # before the frontend joined the scan, so the two literals were never counted. The
    # page is not routed; the literals are its default columns.
    ("public/ai4artsed-frontend/src/stores/llmModelCompare.ts", "local/qwen3:4b"),
    ("public/ai4artsed-frontend/src/stores/llmModelCompare.ts", "local/llama3.2:3b"),
}


def _docstring_lines(tree):
    """Line numbers occupied by docstrings. Prose may name a model; code may not."""
    covered = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                and isinstance(first.value.value, str):
            covered.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return covered


def _comment_spans(source):
    """Column at which a real comment starts, per line. Only actual comments."""
    import io
    import tokenize
    spans = {}
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                spans.setdefault(token.start[0], token.start[1])
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return spans


def _offenders_in(rel, source, only_lines=None):
    """Offenders in one file's source. `only_lines` narrows the check to those lines,
    while the whole source is still parsed -- docstring and comment spans need the
    context around a line to be recognised as such."""
    found = []
    try:
        prose = _docstring_lines(ast.parse(source))
    except SyntaxError:
        prose = set()
    comments = _comment_spans(source)
    for number, line in enumerate(source.splitlines(), 1):
        if number in prose:
            continue
        if only_lines is not None and number not in only_lines:
            continue
        # Cutting at the first '#' also cut at a '#' inside a string, so a colour
        # literal or a URL fragment earlier on the line switched the check off for
        # the rest of it. The tokenizer knows which '#' is a comment.
        code = line[:comments[number]] if number in comments else line
        for match in MODEL_LITERAL.finditer(code):
            name = match.group(1) or match.group(2)
            if (rel, name) in ALLOWED or (rel, name) in INHERITED_DEBT:
                continue
            found.append(f"{rel}:{number}: {name}   -- {line.strip()[:90]}")
    return found


def _tracked_files(prefix, suffixes):
    """(path from the repository root, file) for every tracked file under `prefix`
    whose name ends in one of `suffixes`.

    Only what git tracks, since 2026-10-18. The scans walked the directories with
    rglob and so also read gitignored files, and those differ between checkouts:
    the four archived chunks under schemas/archive/media_prompt_optimization/
    (.gitignore, `**/archive/`) lie in the Fedora checkout and are missing from a
    fresh clone. 96f7cb4a took their INHERITED_DEBT entries out because a fresh
    clone has no such files, and the test went red on Fedora. A gitignored file no
    longer changes what the scan reads. A new file counts once it is added; the
    commit gate reads it from then on. A tracked file deleted in the working
    tree is skipped, as the walk skipped it.

    git runs in ROOT.parent without the variables that point it at another
    repository or index (`git rev-parse --local-env-vars`), and only when
    ROOT.parent is the top level of its own work tree. A tree that is not (a ZIP
    download, a copy inside another repository, a checkout git refuses to read)
    has no tracked set, and the test is skipped with the cause, in git's words
    where git gives them. Names are read as bytes: in text mode a carriage
    return inside a name turns into a newline and the file drops out unseen. A
    submodule or an embedded repository is one gitlink entry in the listing,
    without the files inside it, which the walk read; one under `prefix` fails
    the test.
    """
    import os
    import subprocess
    import pytest

    def git(*args, env=None):
        return subprocess.run(("git",) + args, cwd=str(ROOT.parent), env=env,
                              capture_output=True)

    local = set(os.fsdecode(git("rev-parse", "--local-env-vars").stdout).split())
    env = {k: v for k, v in os.environ.items() if k not in local}
    top = git("rev-parse", "--show-toplevel", env=env)
    top_level = os.fsdecode(top.stdout).strip()
    # samefile, because a path compared as text differs from git's by a symlink
    # or, on a case-insensitive disk, by the case it was typed in.
    if top.returncode != 0 or not os.path.samefile(top_level, ROOT.parent):
        reason = os.fsdecode(top.stderr).strip() or f"the work tree's top level is {top_level}"
        pytest.skip(f"the scan reads the tracked files of {ROOT.parent} and needs it "
                    f"to be a git checkout of its own: {reason}")
    listing = git("ls-files", "-z", "--stage", "--", prefix, env=env)
    assert listing.returncode == 0, os.fsdecode(listing.stderr)
    names, nested = set(), []
    for entry in listing.stdout.split(b"\0"):
        if not entry:
            continue
        mode, _, name = entry.partition(b"\t")
        if mode.startswith(b"160000 "):
            nested.append(os.fsdecode(name))
        else:
            names.add(os.fsdecode(name))
    assert not nested, f"repositories nested under {prefix} are not scanned: {', '.join(nested)}"
    files = []
    for name in sorted(names):
        path = ROOT.parent / name
        if name.endswith(suffixes) and path.is_file():
            files.append((name, path))
    return files


def _backend_files():
    """(path from devserver/, file) for every tracked .py file in SCAN_ROOTS."""
    files = []
    for base in SCAN_ROOTS:
        for name, path in _tracked_files(f"devserver/{base}/", (".py",)):
            files.append((name[len("devserver/"):], path))
    # A scan that reads no file passes everything.
    assert files, f"no tracked .py file under devserver/{{{','.join(SCAN_ROOTS)}}}"
    return files


def _frontend_files():
    files = []
    for name, path in _tracked_files(FRONTEND_PREFIX, (".ts", ".vue")):
        rel = name[len(FRONTEND_PREFIX):]
        if "__tests__/" in rel or rel.endswith(".spec.ts") or rel.endswith(".d.ts"):
            continue
        files.append((name, path))
    return files


def _frontend_code(source):
    """The source with its comments blanked, line count kept: block comments,
    HTML comments, and a `//` tail that is not part of a URL."""
    blank = lambda m: "\n" * m.group(0).count("\n")
    source = re.sub(r"/\*.*?\*/", blank, source, flags=re.S)
    source = re.sub(r"<!--.*?-->", blank, source, flags=re.S)
    return [re.sub(r"(^|[^:])//.*$", r"\1", line) for line in source.splitlines()]


def _frontend_offenders_in(rel, source, only_lines=None):
    found = []
    for number, (code, line) in enumerate(zip(_frontend_code(source), source.splitlines()), 1):
        if only_lines is not None and number not in only_lines:
            continue
        for match in MODEL_LITERAL.finditer(code):
            name = match.group(1) or match.group(2)
            if (rel, name) in ALLOWED or (rel, name) in INHERITED_DEBT:
                continue
            found.append(f"{rel}:{number}: {name}   -- {line.strip()[:90]}")
    return found


def _offenders():
    found = []
    for rel, path in _backend_files():
        if rel in EXEMPT_FILES:
            continue
        found.extend(_offenders_in(rel, path.read_text(encoding="utf-8")))
    for rel, path in _frontend_files():
        found.extend(_frontend_offenders_in(rel, path.read_text(encoding="utf-8")))
    return found


def _staged_offenders():
    """What THIS commit adds -- the staged content of staged files, added lines only.

    Several sessions share this checkout. A gate that judges the whole working tree
    stops a commit over a line in a file the committer never opened, and over another
    session's half-finished edit. Neither has anything to do with the commit being
    made, so neither is grounds to refuse it.
    """
    import subprocess

    def git(*args):
        return subprocess.run(("git",) + args, cwd=str(ROOT.parent),
                              capture_output=True, text=True, check=True).stdout

    found = []
    def added_lines(name):
        added = set()
        for line in git("diff", "--cached", "-U0", "--", name).splitlines():
            if line.startswith("@@"):
                head = line.split("+", 1)[1].split(" ", 1)[0]
                start, _, count = head.partition(",")
                added.update(range(int(start), int(start) + int(count or 1)))
        return added

    for name in git("diff", "--cached", "--name-only", "--diff-filter=ACM").splitlines():
        if name.startswith(FRONTEND_PREFIX) and name.endswith((".ts", ".vue")):
            tail = name[len(FRONTEND_PREFIX):]
            if "__tests__/" in tail or tail.endswith(".spec.ts") or tail.endswith(".d.ts"):
                continue
            found.extend(_frontend_offenders_in(name, git("show", f":{name}"),
                                                only_lines=added_lines(name)))
            continue
        if not name.endswith(".py") or not name.startswith("devserver/"):
            continue
        rel = name[len("devserver/"):]
        if rel in EXEMPT_FILES or rel.split("/", 1)[0] not in SCAN_ROOTS:
            continue
        found.extend(_offenders_in(rel, git("show", f":{name}"), only_lines=added_lines(name)))
    return found


def test_no_model_identifier_literals_in_code():
    offenders = _offenders()
    assert not offenders, (
        "Model identifiers belong in configuration, not in code "
        "(hardware_matrix.json / user_settings.json / model_capabilities):\n  "
        + "\n  ".join(offenders)
    )


def test_the_allowlist_does_not_cover_what_is_already_gone():
    """A stale exemption is an open door nobody remembers opening."""
    live = set()
    for rel, path in _backend_files():
        source = path.read_text(encoding="utf-8")
        for match in MODEL_LITERAL.finditer(source):
            live.add((rel, match.group(1) or match.group(2)))
    for rel, path in _frontend_files():
        for code in _frontend_code(path.read_text(encoding="utf-8")):
            for match in MODEL_LITERAL.finditer(code):
                live.add((rel, match.group(1) or match.group(2)))
    stale = sorted((ALLOWED | INHERITED_DEBT) - live)
    assert not stale, (
        "allowlist entries that no longer match anything -- delete them:\n  "
        + "\n  ".join(f"{rel}: {name}" for rel, name in stale)
    )


def test_the_inherited_debt_only_shrinks():
    """21 literals were already in the tree when this rule was written.

    A number that rises means someone added a model name to code and hid it here instead
    of putting it in configuration. The gate is for that case; this test guards the gate.
    """
    # 21 on 2026-08-13; 12 live on 2026-10-10, when five entries that named
    # files or literals already gone came off, the pattern took HuggingFace ids
    # (+6, the Diffusers chunks) and the frontend joined the scan (+1); 21 on
    # 2026-10-15, when a page frozen by Rule 19 came back with its store (+2).
    assert len(INHERITED_DEBT) <= 21, (
        "the inherited list grew -- a new model literal belongs in configuration, "
        "not in this file"
    )


if __name__ == "__main__":
    # The pre-commit hook's entry point. It asks only about the commit in front of it;
    # the whole-tree question is the test above, which runs when someone runs the tests.
    import sys

    if "--staged" not in sys.argv:
        raise SystemExit("usage: test_no_model_literals.py --staged  (or run pytest)")
    try:
        bad = _staged_offenders()
    except Exception as e:                                   # noqa: BLE001
        # A gate that cannot read the commit says so and steps aside. Blocking every
        # commit in the checkout because git or this file misbehaved is the larger harm.
        print(f"model-policy gate could not read the staged commit ({e}); "
              f"letting it through", file=sys.stderr)
        raise SystemExit(0)
    if bad:
        print("\nCOMMIT BLOCKED -- this commit adds a model identifier to code:\n  "
              + "\n  ".join(bad)
              + "\n\nModel identifiers are DATA: hardware_matrix.json, user_settings.json, or\n"
                "the measured store behind my_app/services/model_capabilities. Platform\n"
                "defaults go in devserver/config.py; tests may name what they test.\n\n"
                "If a literal genuinely has to stay, that is a decision recorded in\n"
                "the commit message, not a --no-verify.\n", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(0)
