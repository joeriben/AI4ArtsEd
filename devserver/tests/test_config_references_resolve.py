"""Every config name the served code sends or reads resolves to a config of the right kind.

The names are strings. Nothing tied `schema: 'heartmula'` in the Flow's song path
(views/x2x_flow.vue) to the file that answered it, so when
schemas/configs/interception/heartmula.json was deleted as an orphaned
perspective on 2026-08-07 (58280833) the song path answered every press with
404 "Config "heartmula" nicht gefunden" until it was restored on 2026-10-01.
Its frontend test (x2x_flow.streamed.spec.ts) asserted the dangling name
against a mocked reply from its creation on 2026-09-05. On 2026-10-06 the song
left that name for /pipeline/generation, and the file went with it.

The same class, found by this file on 2026-10-01: the Canvas lens "De-Kitsch"
was registered as `clichefilter_v2` (types/canvas.ts) for the file
`clichéfilter_v2.json`; the lens fetch answered 404 and the node ran with an
empty context, with no word about it.

What is read, in the served code (frontend src/, devserver my_app/ and
schemas/; the scripts at the devserver root are manual tools and are not read):

1. Frontend: the names given to `schema` and `interception_config`, which
   must be interception configs, and to `configId`, which must be some config:
   as an object key, bare or quoted, across line breaks; as a query parameter;
   through `params.set(...)`; as either side of `||`, `??` or `?:`; as a
   string or a template without `${`; or through a constant of any case
   (`const SONG = '...'`). Not read: a name passed as a positional argument or
   kept in an array and handed on from there. The output slots are
   test_output_config_carry_list.py's.
2. Frontend: the Canvas lens registry (types/canvas.ts), whose ids the lens
   fetch puts into /api/interception/<id>, and whose lenses the executor has
   to run; and the lenses Resona's canvas graphs may name, which are the
   executor's own list.
3. Frontend: any literal that is a config name spelled without its accents.
4. Backend: a literal handed to `config_loader.get_config`,
   `_resolve_interception_config` or `execute_pipeline`, across line breaks; a
   chunk named as `'chunk': '...'`.
5. The interception, pre_interception and pre_output configs: the pipeline
   each names and the output configs it points at.

The output configs themselves -- their pipelines, their chunks, the defaults
per medium and the surfaces that name one -- are test_output_config_carry_list.py's.

The resolver is the real one (`config_loader` after `init_schema_engine`).

Run: cd devserver && python3 -m pytest tests/test_config_references_resolve.py -q
"""
import json
import re
import sys
import unicodedata

from file_modules import DEVSERVER

REPO = DEVSERVER.parent
SCHEMAS = DEVSERVER / "schemas"
FRONTEND = REPO / "public" / "ai4artsed-frontend" / "src"
CANVAS_TYPES = FRONTEND / "types" / "canvas.ts"
sys.path.insert(0, str(DEVSERVER))

# Words a config's media_preferences.default_output may carry that name a
# medium, which `lookup_output_config` maps to a config, not a config itself.
MEDIA_WORDS = {"image", "audio", "music", "video", "text", "code", "3d", "sound"}

# A name is everything between its quotes, so that a spelling the server does
# not hold (an accent written as a combining mark) is read whole and fails.
ID = r"""[^'"`\s$]+"""
# The kind each slot takes; None: any config.
SLOTS = {"schema": "interception", "interception_config": "interception", "configId": None}
_KEYS = "|".join(SLOTS)
# The key, bare or quoted, and what it is given, up to the next comma, brace,
# semicolon or line end: `schema: 'x'`, `'schema': X`, `schema: v || 'x'`.
SLOT = re.compile(r"""(?<![\w.?])['"]?(%s)['"]?\s*:\s*([^,}\n;]+)""" % _KEYS)
SLOT_SET = re.compile(r"""\.set\(\s*['"](%s)['"]\s*,\s*([^)\n]+)\)""" % _KEYS)
SLOT_QUERY = re.compile(r"""[?&](%s)=([^'"`\s$&#)]+)""" % _KEYS)
ALTERNATIVES = re.compile(r"\|\||\?\?|\?|:")
WHOLE_LITERAL = re.compile(r"""^(['"`])(%s)\1$""" % ID)
CONSTANT = re.compile(r"""\bconst\s+([A-Za-z_]\w*)\s*(?::\s*\w+\s*)?=\s*['"](%s)['"]""" % ID)
SNAKE_LITERAL = re.compile(r"""['"]([a-z]\w*_\w*)['"]""")
BACKEND_PATTERNS = (
    # backend_registry and course_prompt_resolver have get_config methods of their own
    re.compile(r"""\bconfig_loader\.get_config\(\s*['"](%s)['"]""" % ID),
    re.compile(r"""_resolve_interception_config\(\s*['"](%s)['"]""" % ID),
    re.compile(r"""execute_pipeline\(\s*(?:config_name\s*=\s*)?['"](%s)['"]""" % ID),
)
BACKEND_CHUNK = re.compile(r"""['"]chunk['"]\s*:\s*['"]([\w]+)['"]""")


def _loader():
    from my_app.routes.schema_pipeline_routes import init_schema_engine
    init_schema_engine()
    from schemas.engine.config_loader import config_loader
    names = set(config_loader.list_configs())
    assert names, "config_loader resolved no config at all"
    return config_loader, names


def _stage(loader, name):
    config = loader.get_config(name)
    return (config.meta or {}).get("stage") if config is not None else None


def _fold(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(c)).lower()


def _frontend_files():
    files = [p for p in sorted(list(FRONTEND.rglob("*.ts")) + list(FRONTEND.rglob("*.vue")))
             if "__tests__" not in p.parts and "i18n" not in p.parts]
    assert files, f"no frontend source under {FRONTEND}"
    return files


def _where(path, text, offset):
    return f"{path.relative_to(REPO)}:{text.count(chr(10), 0, offset) + 1}"


def _names_in(expression, constants):
    """The names an expression given to a slot can come to: each side of
    `||`, `??` and `?:` that is a whole literal or a known constant. A call or
    a property is no name and is passed over."""
    names = []
    for side in ALTERNATIVES.split(expression):
        side = side.strip().rstrip(")").strip()
        literal = WHOLE_LITERAL.match(side)
        if literal:
            names.append(literal.group(2))
        elif side in constants:
            names.append(constants[side])
    return names


def _slots_in(text, constants):
    """(offset, slot, name) for every name this source gives to a slot."""
    found = []
    for pattern in (SLOT, SLOT_SET):
        for m in pattern.finditer(text):
            for name in _names_in(m.group(2), constants):
                found.append((m.start(), m.group(1), name))
    for m in SLOT_QUERY.finditer(text):
        found.append((m.start(), m.group(1), m.group(2)))
    return found


def _frontend_slots():
    """(where, slot, name) for every config name the frontend gives to a slot."""
    found = []
    for path in _frontend_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        constants = dict(CONSTANT.findall(text))
        for offset, slot, name in _slots_in(text, constants):
            found.append((_where(path, text, offset), slot, name))
    return found


def test_frontend_slots_name_configs_of_their_kind():
    loader, names = _loader()
    found = _frontend_slots()
    assert found, "the scan found no config slot at all"
    problems = []
    for where, slot, name in found:
        if name not in names:
            problems.append(f"{where}  {slot}: {name!r} names no config (the server answers 404)")
        elif SLOTS[slot] and _stage(loader, name) != SLOTS[slot]:
            problems.append(f"{where}  {slot}: {name!r} is a {_stage(loader, name)} config, "
                            f"not an {SLOTS[slot]} config")
    assert not problems, "\n" + "\n".join(problems)


def _canvas_lens_ids():
    text = CANVAS_TYPES.read_text(encoding="utf-8")
    union = re.search(r"export type InterceptionPreset\s*=(.*?)\n\n", text, re.S)
    record = re.search(r"INTERCEPTION_PRESETS[^=]*=\s*\{(.*?)\n\}", text, re.S)
    assert union and record, f"the lens registry in {CANVAS_TYPES} has another shape now"
    in_union = re.findall(r"\|\s*'([^'\s]+)'", union.group(1))
    in_record = re.findall(r"^\s*'?([^'\s:]+)'?\s*:\s*\{", record.group(1), re.M)
    return in_union, in_record


def test_canvas_lenses_are_interception_configs():
    in_union, in_record = _canvas_lens_ids()
    assert in_union and sorted(in_union) == sorted(in_record), (in_union, in_record)
    lens_dir = SCHEMAS / "configs" / "interception"
    problems = [name for name in in_union
                if not (lens_dir / f"{name}.json").is_file()]
    assert not problems, ("Canvas lenses with no interception config behind them; the "
                          f"lens fetch answers 404 and the node runs without context: {problems}")


def _offered_to_resona():
    from my_app.services import canvas_graph_authoring
    canvas_graph_authoring._INTERCEPTION_IDS_CACHE = None
    return canvas_graph_authoring._interception_config_ids()


def test_resonas_canvas_lenses_are_the_ones_the_executor_runs():
    """Guards the derivation: the list a graph is checked against is read
    through the executor's loader (until 2026-10-01 it was a list of its own,
    and the executor refused the accented lens it offered)."""
    from my_app.services.canvas_executor import _load_interception_context
    offered = _offered_to_resona()
    assert offered
    refused = {}
    for name in sorted(offered):
        context, error = _load_interception_context(name, "en")
        if error or not context:
            refused[name] = error
    assert not refused, refused


def test_every_lens_the_canvas_offers_runs():
    """A lens picked in the Canvas fetches its context and runs as a text
    model call; one the executor refuses (no context, no text pipeline) would
    run without its instruction. user_defined is the one the reader writes."""
    in_union, _record = _canvas_lens_ids()
    offered = _offered_to_resona()
    refused = [name for name in in_union if name != "user_defined" and name not in offered]
    assert not refused, refused


def test_no_literal_is_a_config_name_without_its_accents():
    _loader_, names = _loader()
    by_fold = {}
    for name in names:
        by_fold.setdefault(_fold(name), set()).add(name)
    problems = []
    for path in _frontend_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in SNAKE_LITERAL.finditer(text):
            name = m.group(1)
            if name not in names and _fold(name) in by_fold:
                problems.append(f"{_where(path, text, m.start())}  {name!r} is "
                                f"{sorted(by_fold[_fold(name)])} spelled otherwise")
    assert not problems, "\n" + "\n".join(problems)


def test_backend_literals_resolve():
    _loader_, names = _loader()
    chunks = {p.stem for p in (SCHEMAS / "chunks").iterdir() if p.suffix in (".json", ".py")}
    files = [p for root in (DEVSERVER / "my_app", SCHEMAS)
             for p in sorted(root.rglob("*.py")) if "__pycache__" not in p.parts]
    hits, problems = 0, []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in BACKEND_PATTERNS:
            for m in pattern.finditer(text):
                hits += 1
                if m.group(1) not in names:
                    problems.append(f"{_where(path, text, m.start())}  {m.group(1)!r}")
        for m in BACKEND_CHUNK.finditer(text):
            hits += 1
            if m.group(1) not in chunks:
                problems.append(f"{_where(path, text, m.start())}  chunk {m.group(1)!r}")
    assert hits, "the backend scan found no reference at all"
    assert not problems, "The backend names configs or chunks that are not there:\n" + "\n".join(problems)


def _non_output_configs():
    """The configs test_output_config_carry_list.py does not read: interception,
    pre_interception, pre_output (user_configs are the users' own)."""
    for folder in ("interception", "pre_interception", "pre_output"):
        for path in sorted((SCHEMAS / "configs" / folder).glob("*.json")):
            yield path, json.loads(path.read_text(encoding="utf-8"))


def test_configs_name_what_exists():
    _loader_, names = _loader()
    pipelines = {p.stem for p in (SCHEMAS / "pipelines").glob("*.json")}
    problems = []
    for path, data in _non_output_configs():
        where = path.relative_to(REPO)
        pipeline = data.get("pipeline")
        if pipeline and pipeline not in pipelines:
            problems.append(f"{where}: pipeline {pipeline!r}")
        meta = data.get("meta") or {}
        if meta.get("output_config") and meta["output_config"] not in names:
            problems.append(f"{where}: meta.output_config {meta['output_config']!r}")
        prefs = data.get("media_preferences") or {}
        default = prefs.get("default_output")
        if default and default not in MEDIA_WORDS and default not in names:
            problems.append(f"{where}: media_preferences.default_output {default!r}")
        for name in prefs.get("output_configs") or []:
            if name not in names:
                problems.append(f"{where}: media_preferences.output_configs {name!r}")
    assert not problems, "Config files name things that do not exist:\n  " + "\n  ".join(problems)


def _names(source):
    return [name for _o, _s, name in _slots_in(source, dict(CONSTANT.findall(source)))]


def test_the_check_sees_the_cases_that_broke():
    """The slot scan sees the line that dangled for eight weeks and the forms
    a name takes on its way to a slot; the accent check sees the lens."""
    assert _names("      schema: 'heartmula',") == ["heartmula"]
    assert _names("const SONG = 'heartmula'\n  schema:\n    SONG,") == ["heartmula"]
    assert _names("const song = 'heartmula'\n  { 'schema': song }") == ["heartmula"]
    assert _names("  configId: chosen || 'user_defined',") == ["user_defined"]
    assert _names("  schema: wide ? `bauhaus` : 'overdrive'\n") == ["bauhaus", "overdrive"]
    assert _names("  params.set('schema', 'bauhaus')") == ["bauhaus"]
    assert _names("  fetch(`/x?schema=bauhaus&y=1`)") == ["bauhaus"]
    assert _names("  schema: t('flow.schema'),") == []
    assert _names("  schema: string") == []
    nfd = "cliche\u0301filter_v2"
    assert _names(f"  configId: '{nfd}',") == [nfd]
    assert _fold("clichefilter_v2") == _fold("clichéfilter_v2")
