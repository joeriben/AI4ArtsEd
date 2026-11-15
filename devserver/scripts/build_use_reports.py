#!/usr/bin/env python3
"""Build the structured record and the matrix page of the use reports.

Reads
  docs/use_reports/v<VERSION>/NN_*.md     the use reports, one per instrument, in
                                          the nine-section format (00_README.md
                                          describes the run and is not parsed)
  docs/ailit/learner_expectations.tsv     the framework's competence statements and
                                          Learner Expectations, with their pages
  docs/ailit/classroom_scenarios.tsv      the framework's "In the Classroom"
                                          examples, with their pages
  docs/ailit/unterstuetzung.tsv           the record of the earlier reading; only
                                          its rows without a part are read: the
                                          measures no part of the platform
                                          supports, with the reason (German)
  devserver/my_app/knowledge/platform_items.json
                                          the catalogue, to know which report
                                          routes have no item of their own

Writes
  devserver/my_app/knowledge/use_reports.json
      every report structured and raw: sections 1-3 and 5-9, the possibilities of
      section 7, the scenarios of section 8 with their parsed setting (form,
      subjects, grades, duration) and their Sequence / Subject link /
      Uncertainty, the mapping of section 9 ((a) hits, (b) mutatis mutandis
      with the modification, Beyond the framework, Non-fits), the framework
      wording with its pages, `places`: the report routes without a
      catalogue item, with the view names their pages send to Help, and
      `unreached`: competence|level -> the German text of the earlier reading
      for the measures no part of the platform supports (lookup_scenarios
      hands it over where a competence has no mapped scenario, 2026-11-08).
  docs/use_reports/v<VERSION>/ailit_matrix.html
      one self-contained page: competences x levels with the density of the
      (a) entries, (b) switchable, instruments x competences, Beyond.

Who reads the JSON: devserver/my_app/services/platform_items.py, which joins a
report to the page by route for Help (chat_routes) and serves it to the
lookup_place, lookup_scenarios and read_scenario tools (tool_registry).

Checks: a quoted expectation that differs from the framework wording, a
scenario reference that section 8 does not carry, a (b) entry without
Modification or Restriction, a bullet of (a) or (b) that does not parse, report
numbers that are not consecutive from 01, and a report route that has neither
a catalogue item nor an entry in PAGE_CONTEXT are printed as WARNING, and the
build exits 1 writing nothing. Lines printed as NOTE (a scenario without a
parsed form, a mapping entry that cites no scenario, a competence and level in
both (a) and (b)) are for reading and do not change the exit code.

Run:  python3 devserver/scripts/build_use_reports.py
"""
import datetime
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VERSION = '1.0'
REPORTS_DIR = REPO / 'docs/use_reports' / f'v{VERSION}'
EXP_TSV = REPO / 'docs/ailit/learner_expectations.tsv'
SCEN_TSV = REPO / 'docs/ailit/classroom_scenarios.tsv'
SUP_TSV = REPO / 'docs/ailit/unterstuetzung.tsv'
ITEMS_JSON = REPO / 'devserver/my_app/knowledge/platform_items.json'
OUT_JSON = REPO / 'devserver/my_app/knowledge/use_reports.json'
OUT_HTML = REPORTS_DIR / 'ailit_matrix.html'

DOMAINS = ['Engage', 'Create', 'Manage', 'Shape']
LEVELS = ['Basic', 'Intermediate', 'Advanced']

# What the pages without a catalogue item send to Help, so the report reaches
# the page somebody stands on. usePageContext.formatPageContextForLLM sends
# "Aktive Ansicht: <activeViewType>" when the page sets a context and
# "[Kontext: Aktive Seite = <route>]" when it sets none. Verified in the
# frontend source (public/ai4artsed-frontend/src):
#   /x2x-flow      router -> views/x2x_flow.vue, activeViewType 'x2x_flow'
#   /together      router -> views/resona.vue, activeViewType 'resona'
#   /contesting    router -> views/ai_persona.vue, activeViewType 'ai_persona'
#   /canvas        router -> views/canvas_workflow.vue, activeViewType 'canvas_workflow'
#   /latent-lab/overview
#                  views/latent_lab.vue sets no context for the overview, so the
#                  route is sent; the IDS table keeps /latent-lab/intro as an
#                  earlier address of the same page
# The Model Comparison of the Transformers Lab and the Tokenizer stood here
# until 2026-11-08: since 3c30e8d1 the catalogue holds an item for each, so
# they are joined by route like the other instruments (chat_routes
# ITEM_FOR_VIEW maps their views to the items).
PAGE_CONTEXT = {
    '/x2x-flow': {'views': ['x2x_flow'], 'aliases': []},
    '/together': {'views': ['resona'], 'aliases': []},
    '/contesting': {'views': ['ai_persona'], 'aliases': []},
    '/canvas': {'views': ['canvas_workflow'], 'aliases': []},
    '/latent-lab/overview': {'views': [], 'aliases': ['/latent-lab/intro']},
}

# German page names as the interface labels them, so lookup_place resolves the name a German-speaking person uses
GERMAN_NAMES: dict[str, str] = {
    '/latent-lab/overview': 'Überblick',
    '/latent-lab/model-comparison': 'Modell-Vergleich',
    '/latent-lab/cultural-un-known': 'Stereotypen-Analyse',
    '/latent-lab/image-understanding': 'Bildverständnis',
    '/latent-lab/language-understanding': 'Sprachverständnis',
    '/latent-lab/voices': 'Stimmen-Vergleich',
    '/latent-lab/interception-across-models': 'Sprachmodell-Vergleich',
    '/latent-lab/perspectives-on-a-template': 'Wirkungsvergleich',
    '/latent-lab/aesthetic-poles': 'Ästhetische Pole',
}


def read_tsv(path, n_fields):
    rows = []
    with path.open(encoding='utf-8', newline='') as f:
        for n, line in enumerate(f, 1):
            line = line.rstrip('\n')
            if n == 1 or not line.strip():
                continue
            fields = [x.strip() for x in line.split('\t')]
            assert len(fields) == n_fields, f'{path.name} line {n}: {len(fields)} fields instead of {n_fields}'
            rows.append(fields)
    return rows


# ---- framework wording -------------------------------------------------------
competences, expectations, classroom = [], {}, {}
expectation_pages, classroom_pages = {}, {}
for competence, _dom, _nr, statement, basic, inter, adv, _ksa, page in read_tsv(EXP_TSV, 9):
    competences.append({'code': competence, 'domain': competence.split()[0], 'title': statement, 'page': page})
    for lv, text in zip(LEVELS, (basic, inter, adv)):
        expectations[f'{competence}|{lv}'] = text
        expectation_pages[f'{competence}|{lv}'] = page
for competence, lv, text, page in read_tsv(SCEN_TSV, 4):
    assert lv in LEVELS, f'{SCEN_TSV.name}: unknown level {lv!r}'
    classroom[f'{competence}|{lv}'] = text
    classroom_pages[f'{competence}|{lv}'] = page
assert len(competences) == 19, len(competences)
assert len(expectations) == 57, len(expectations)
assert len(classroom) == 57, len(classroom)
assert set(classroom) == set(expectations), 'the two TSVs name different competences or levels'

# ---- what no part of the platform carries ------------------------------------
# The record of the earlier reading keeps, in its rows without a part, the
# measures that reading found no part for, each with a German text: the
# framework's measure in one sentence, what the platform does not hold in the
# next. The use reports name such a competence only in a "Non-fits" list,
# without a reason; lookup_scenarios hands this text over when a competence
# has no mapped scenario, so the model has the answer in one round. The
# reports V 1.0 are the source since 2026-11-06: a row of the table that a
# report's scenario reaches at that competence and level is superseded and
# left out below; the mapping of the table (which part supports which
# measure) is not read at all.
unreached = {}
for teil, competence, lv, status, wie_de, _scenario, _source in read_tsv(SUP_TSV, 7):
    if teil:
        continue
    assert status == 'nein', f'{SUP_TSV.name}: {competence} {lv} without a part but status {status!r}'
    assert competence in {c['code'] for c in competences}, f'{SUP_TSV.name}: unknown competence {competence!r}'
    assert lv in LEVELS, f'{SUP_TSV.name}: unknown level {lv!r}'
    assert wie_de, f'{SUP_TSV.name}: {competence} {lv} without a text'
    assert f'{competence}|{lv}' not in unreached, f'{SUP_TSV.name}: {competence} {lv} twice without a part'
    unreached[f'{competence}|{lv}'] = wie_de

# ---- reports -----------------------------------------------------------------
LINE = re.compile(r'^- ((?:Engage|Create|Manage|Shape) \d) (Basic|Intermediate|Advanced) — "([^"]+)"[ \t]*([^\n]*)$', re.M)
SCEN = re.compile(r'\*\*(S\d+)\s*[—–-]\s*([^*]+?)\*\*\.?\s*(\(([^)]*)\))?')
SECTION = re.compile(r'^## (\d)\. (.+?)\s*$', re.M)
SUBFIELD = re.compile(r'(?:(?<=[.;)"] )|^)(Sequence(?: \([^)]*\))?|Subject link|Uncertainty):\s*')
FORMS = {'formal', 'non-formal', 'formal or non-formal', 'non-formal or formal', 'formal/non-formal'}


def parse_setting(raw):
    """The parenthesis after a scenario title, 'formal, art, grades 7–10, 90 min':
    kept raw, and split into form / subjects / grades / duration where a token
    is unmistakable. Anything else stays in subjects."""
    out = {'form': None, 'subjects': None, 'grades': None, 'duration': None}
    if not raw:
        return out
    rest = []
    for tok in [x.strip() for x in re.split(r',\s*', raw) if x.strip()]:
        low = tok.lower()
        if low in FORMS and out['form'] is None:
            out['form'] = low
        elif re.search(r'\b\d+\s*(?:min|h|hours?)\b|\bdays?\b|\bsessions?\b|×|add-on|project of|full day', low) and out['duration'] is None:
            out['duration'] = tok
        elif re.search(r'\bgrades?\b|\bage\b|\badults\b|\bfrom grade\b', low) and out['grades'] is None:
            out['grades'] = tok
        else:
            rest.append(tok)
    out['subjects'] = ', '.join(rest) or None
    return out


def split_body(body):
    """A scenario paragraph with its labelled tail: 'Sequence: …', 'Subject
    link: …', 'Uncertainty: …'. The text before the first label is the
    scenario. A parenthesis in the Sequence label ('Sequence (session 1):')
    is kept at the start of the value."""
    parts = SUBFIELD.split(body)
    out = {'text': parts[0].strip().lstrip('. ').strip(), 'sequence': None, 'subject_link': None, 'uncertainty': None}
    for lab, val in zip(parts[1::2], parts[2::2]):
        key = 'sequence' if lab.startswith('Sequence') else ('subject_link' if lab.startswith('Subject') else 'uncertainty')
        val = val.strip()
        if key == 'sequence' and lab != 'Sequence':
            val = lab[len('Sequence'):].strip() + ' ' + val
        out[key] = (out[key] + ' ' if out[key] else '') + val
    return out


instruments, records, warnings = [], [], []
for f in sorted(REPORTS_DIR.glob('[0-3][0-9]_*.md')):
    t = f.read_text(encoding='utf-8')
    first = t.splitlines()[0]
    h = re.match(r'^# (\d\d) (.+?)(?: — `([^`]+)`)?\s*$', first)
    if not h or h.group(1) == '00':
        continue
    num, name, route = h.group(1), h.group(2).strip(), (h.group(3) or '')
    used = next((ln.strip() for ln in t.splitlines()[1:6] if ln.startswith('Used ')), '')
    # the nine sections, raw
    heads = list(SECTION.finditer(t))
    sections = []
    for k, m in enumerate(heads):
        end = heads[k + 1].start() if k + 1 < len(heads) else len(t)
        sections.append({'number': int(m.group(1)), 'title': m.group(2), 'text': t[m.end():end].strip()})
    sec = {s['number']: s['text'] for s in sections}
    if sorted(sec) != list(range(1, 10)):
        warnings.append(f'{num}: sections {sorted(sec)}')
    s7, s8, s9 = sec.get(7, ''), sec.get(8, ''), sec.get(9, '')
    possibilities = [ln[2:].strip() for ln in s7.splitlines() if ln.startswith('- ')]
    # the paragraphs of section 7 that are not bullets, e.g. a closing remark
    possibilities_note = '\n\n'.join(
        p.strip() for p in re.split(r'\n[ \t]*\n', s7)
        if p.strip() and not p.strip().startswith('- '))
    # scenarios: head line, setting, body with its labelled tail
    heads8 = list(SCEN.finditer(s8))
    intro = s8[:heads8[0].start()].strip() if heads8 else s8.strip()
    scen, scen_list = {}, []
    for k, m in enumerate(heads8):
        end = heads8[k + 1].start() if k + 1 < len(heads8) else len(s8)
        title = m.group(2).strip().rstrip('.')
        setting = (m.group(4) or '').strip()
        body = s8[m.end():end].strip()
        scen[m.group(1)] = {'title': title, 'setting': setting}
        rec = {'id': m.group(1), 'title': title, 'setting': setting}
        rec.update(parse_setting(setting))
        rec.update(split_body(body))
        scen_list.append(rec)
    a_blk = s9.split('**(a)')[1].split('**(b)')[0] if '**(a)' in s9 else ''
    b_blk = s9.split('**(b)')[1] if '**(b)' in s9 else ''
    b_blk = b_blk.split('**Beyond')[0].split('**Non-fits')[0]
    beyond = ''
    if '**Beyond the framework**' in s9:
        beyond = s9.split('**Beyond the framework**')[1].split('**Non-fits')[0].lstrip(': ').strip()
    nonfits = ''
    m = re.search(r'\*\*Non-fits\*\*:\s*(.+)', s9)
    if m:
        nonfits = m.group(1).strip()

    def lines(blk, cat, num=num, scen=scen):
        view, full = [], []
        for ln in blk.splitlines():
            s = ln.strip()
            if s.startswith('- ') and s not in ('- --', '- —') and not LINE.match(s):
                warnings.append(f'{num}: ({cat}) line does not parse: {s[:60]!r}')
        for m in LINE.finditer(blk):
            txt = m.group(4).strip()
            refs = sorted(set(re.findall(r'\bS\d+\b', txt)), key=lambda s: int(s[1:]))
            for r in refs:
                if r not in scen:
                    warnings.append(f'{num}: {cat} {m.group(1)} {m.group(2)} refers to {r}, which section 8 does not carry')
            cell = f'{m.group(1)}|{m.group(2)}'
            if expectations.get(cell) != m.group(3):
                warnings.append(f'{num}: quote of {cell} differs from the framework wording')
            view.append({'cell': cell, 'quote': m.group(3), 'text': txt, 'scen': refs})
            rec = {'competence': m.group(1), 'level': m.group(2), 'expectation': m.group(3), 'text': txt, 'scenarios': refs}
            if cat == 'b':
                mm = re.search(r'(?:Modification|Restriction):\s*(.+)$', txt)
                rec['modification'] = mm.group(1).strip() if mm else None
                if not mm:
                    warnings.append(f'{num}: (b) {cell} names no Modification or Restriction')
            full.append(rec)
        return view, full
    a_view, a_full = lines(a_blk, 'a')
    b_view, b_full = lines(b_blk, 'b')
    instruments.append({'num': num, 'name': name, 'route': route, 'file': f.name,
                        'scenarios': scen, 'a': a_view, 'b': b_view,
                        'beyond': beyond, 'nonfits': nonfits})
    german = GERMAN_NAMES.get(route)
    aliases = ([german] if german and german != name else []) + list((PAGE_CONTEXT.get(route) or {}).get('aliases') or [])
    records.append({'number': num, 'name': name, 'route': route, 'file': f.name,
                    'aliases': aliases,
                    'sections': [s for s in sections if s['number'] != 4],
                    'help_should_say': sec.get(6, '').strip(),
                    'possibilities': possibilities,
                    'possibilities_note': possibilities_note,
                    'scenarios_intro': intro,
                    'scenarios': scen_list,
                    'mapping': {'a': a_full, 'b': b_full, 'beyond': beyond or None, 'non_fits': nonfits or None}})
instruments.sort(key=lambda i: i['num'])
records.sort(key=lambda r: r['number'])
numbers = [r['number'] for r in records]
if numbers != [f'{k:02d}' for k in range(1, len(numbers) + 1)]:
    warnings.append(f'report numbers are not consecutive from 01 without gap or duplicate: {numbers}')
print(f'reports={len(records)}')

# Informational: cases worth a look that do not stop the build.
notes = []
for r in records:
    for s in r['scenarios']:
        if s['form'] is None:
            notes.append(f"{r['number']}: scenario {s['id']} has no parsed setting form")
    for cat in ('a', 'b'):
        for e in r['mapping'][cat]:
            if not e['scenarios']:
                notes.append(f"{r['number']}: ({cat}) {e['competence']} {e['level']} cites no scenario")
    a_cells = {(e['competence'], e['level']) for e in r['mapping']['a']}
    for e in r['mapping']['b']:
        if (e['competence'], e['level']) in a_cells:
            notes.append(f"{r['number']}: {e['competence']} {e['level']} stands in both (a) and (b)")
for n in notes:
    print('NOTE', n)
print(f'notes={len(notes)}')

# ---- the pages without a catalogue item ------------------------------------
item_routes = {i.get('route') for i in json.loads(ITEMS_JSON.read_text(encoding='utf-8')).get('items', [])
               if i.get('route')}
places = []
for r in records:
    if r['route'] in item_routes:
        continue
    ctx = PAGE_CONTEXT.get(r['route'])
    if ctx is None:
        warnings.append(f"{r['number']}: route {r['route']} has no catalogue item and no entry in PAGE_CONTEXT")
        continue
    german = GERMAN_NAMES.get(r['route'])
    places.append({'route': r['route'], 'number': r['number'], 'name': r['name'],
                   'views': list(ctx['views']),
                   'aliases': list(ctx['aliases']) + ([german] if german and german != r['name'] else [])})
for route in PAGE_CONTEXT:
    if route in item_routes:
        warnings.append(f'PAGE_CONTEXT names {route}, which has a catalogue item now')
    if route not in {r['route'] for r in records}:
        warnings.append(f'PAGE_CONTEXT names {route}, which no report carries')

for w in warnings:
    print('WARNING', w)

# ---- the rows of the table the reports supersede --------------------------------
# Where a scenario of V 1.0 is mapped to the competence at that level, the
# reports have the measure; the table's row is superseded and stays out.
mapped_cells = {f"{e['competence']}|{e['level']}" for r in records for cat in ('a', 'b')
                for e in r['mapping'][cat] if e['scenarios']}
superseded = sorted(k for k in unreached if k in mapped_cells)
unreached = {k: v for k, v in unreached.items() if k not in mapped_cells}

# ---- the versioned record: one JSON, every report structured and raw ----------
generated = datetime.date.today().isoformat()
record = {
    'version': VERSION,
    'generated': generated,
    'title': f'Use reports of the {len(records)} instruments and their AI-literacy mapping',
    # Who used the instruments, on which build, when, and who reviewed what
    # stands in the README, in the session line and section 4 of the .md
    # files and in the repository history. The record carries neither: it is
    # read by the agents of the platform, and what an agent reads it can say
    # in the room (2026-11-07). It carries sections 1 to 3 (what was done on
    # the page, what its controls did, what came out) and 5 to 9 with the
    # fields built from them. Sections 1 to 3 joined on 2026-11-14: since
    # then the report is what Help and Together know of what a page is and
    # does, and the handbook keeps no entry for a page that has a report.
    'source': {'folder': f'docs/use_reports/v{VERSION}',
               'readme': '00_README.md'},
    'framework': {'citation': 'OECD / European Union (2026), Empowering learners for the age of AI: An AI literacy framework '
                              'for primary and secondary education, OECD Publishing, Paris, https://doi.org/10.1787/65cd27d4-en',
                  'license': 'CC BY 4.0',
                  'wording': 'The 19 competence statements, 57 Learner Expectations and 57 "In the Classroom" examples are '
                             'read verbatim from docs/ailit/learner_expectations.tsv and docs/ailit/classroom_scenarios.tsv, '
                             'with their pages; the build checks that every quote in the reports is identical.'},
    'categories': {
        'a': '100 % hit: the scenario contains the activity of the framework\'s classroom example for that competence and level.',
        'b': 'Mutatis mutandis: a modification, named in the entry, brings the scenario to the level of the classroom example.',
        'beyond': 'Where the scenarios go beyond every classroom example of the framework; one paragraph per instrument.',
        'non_fits': 'The competences the instrument\'s scenarios do not reach, named by the report.'},
    'domains': DOMAINS, 'levels': LEVELS, 'competences': competences,
    'expectations': expectations, 'classroom': classroom,
    'expectation_pages': expectation_pages, 'classroom_pages': classroom_pages,
    'unreached': unreached,
    'unreached_note': ('The rows without a part of docs/ailit/unterstuetzung.tsv that no teaching '
                       'scenario of the reports reaches, by competence and level: the framework\'s '
                       'measure and what the platform does not hold, in German. The reports V 1.0 '
                       'are the source since 2026-11-06; a row a scenario is mapped to at that '
                       'competence and level is superseded and left out.'),
    'places': places,
    'instruments': records}
if warnings:
    print(f'{len(warnings)} warnings; nothing written')
    sys.exit(1)
OUT_JSON.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
nscen = sum(len(r['scenarios']) for r in records)
nparsed = sum(1 for r in records for s in r['scenarios'] if s['form'] and s['duration'])
print(f'wrote {OUT_JSON.relative_to(REPO)} {OUT_JSON.stat().st_size} bytes; scenarios={nscen}, '
      f'with form and duration parsed={nparsed}, places={len(places)}, unreached={len(unreached)}, superseded={len(superseded)}, warnings={len(warnings)}')

data = {'generated': generated, 'domains': DOMAINS, 'levels': LEVELS,
        'competences': competences, 'expectations': expectations, 'classroom': classroom,
        'instruments': instruments}
na = sum(len(i['a']) for i in instruments)
nb = sum(len(i['b']) for i in instruments)
nbey = sum(1 for i in instruments if i['beyond'])
print(f'instruments={len(instruments)} a-lines={na} b-lines={nb} beyond={nbey} scenarios={sum(len(i["scenarios"]) for i in instruments)}')

PAGE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AILit matrix V __VERSION__</title>
<style>
:root{--ink:#1b1f23;--mute:#5b6570;--line:#d9dee3;--bg:#fbfbfa;--panel:#fff;--acc:#1f5f8b;--hatch:#b86b2a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,"Segoe UI",Roboto,"Source Sans 3",sans-serif}
header{padding:20px 24px 8px}
h1{font-size:22px;margin:0 0 4px;font-weight:600}
.sub{color:var(--mute);margin:0 0 10px;max-width:980px}
.controls{display:flex;flex-wrap:wrap;gap:14px;align-items:center;padding:0 24px 12px;color:var(--mute)}
.controls button{border:1px solid var(--line);background:#fff;color:var(--ink);padding:5px 10px;border-radius:6px;cursor:pointer;font:inherit}
.controls button.on{background:var(--acc);color:#fff;border-color:var(--acc)}
.controls label{display:flex;gap:6px;align-items:center;cursor:pointer}
main{display:grid;grid-template-columns:minmax(0,1fr) 420px;gap:0 20px;padding:0 24px 24px}
@media (max-width:1100px){main{grid-template-columns:1fr}#panel{position:static;max-height:none}}
@media (max-width:700px){td.cell{min-width:52px;width:auto;height:40px}td.comp small{display:block;margin:0;font-size:12px}table{border-spacing:2px}header,.controls,main,footer{padding-left:14px;padding-right:14px}}
table{border-collapse:separate;border-spacing:3px;width:100%}
th{font-weight:500;color:var(--mute);text-align:left;padding:4px 6px;font-size:13px}
th.lvl{text-align:center}
td.cell{height:46px;min-width:70px;width:118px;text-align:center;border-radius:5px;cursor:pointer;position:relative;border:1px solid transparent;font-variant-numeric:tabular-nums}
td.cell:hover,td.cell.sel{outline:2px solid var(--acc);outline-offset:-1px}
td.cell .n{font-size:17px;font-weight:600}
td.cell .nb{font-size:12px;color:var(--hatch);margin-left:3px;font-weight:600}
td.cell.hasb{background-image:repeating-linear-gradient(135deg,rgba(184,107,42,.18) 0 3px,transparent 3px 9px)}
td.comp{padding:4px 8px;font-size:13.5px;max-width:640px}
td.comp small{color:var(--mute);margin-left:6px;font-weight:400}
tr.dom td{padding:14px 8px 4px;color:var(--mute);font-size:12px;letter-spacing:.06em;text-transform:uppercase}
td.beyond{text-align:left;padding:8px 10px;border-radius:5px;background:#efe9df;cursor:pointer}
td.beyond:hover,td.beyond.sel{outline:2px solid var(--acc);outline-offset:-1px}
/* view 2 */
table.inst th.c{writing-mode:vertical-rl;transform:rotate(180deg);text-align:left;padding:6px 2px;font-size:12px;white-space:nowrap}
table.inst td.name{white-space:nowrap;font-size:13.5px;padding:2px 8px}
table.inst td.m{height:28px;min-width:34px;text-align:center;border-radius:4px;cursor:pointer;background:#fff;border:1px solid var(--line);font-size:11px;letter-spacing:1px}
table.inst td.m:hover,table.inst td.m.sel{outline:2px solid var(--acc);outline-offset:-1px}
table.inst td.m b{color:var(--acc)}
table.inst td.m i{color:var(--hatch);font-style:normal}
table.inst td.m.empty{background:transparent;border-color:transparent}
#panel{position:sticky;top:12px;align-self:start;max-height:calc(100vh - 24px);overflow:auto;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px 16px}
#panel h2{font-size:16px;margin:0 0 6px}
#panel .q{color:var(--mute);font-style:italic;margin:0 0 10px}
#panel .cls{font-size:13px;color:var(--mute);margin:0 0 12px}
#panel h3{font-size:14px;margin:14px 0 4px}
#panel .tag{display:inline-block;font-size:11px;padding:1px 6px;border-radius:4px;border:1px solid var(--line);color:var(--mute);margin-right:6px;vertical-align:middle}
#panel .tag.a{border-color:var(--acc);color:var(--acc)}
#panel .tag.b{border-color:var(--hatch);color:var(--hatch)}
#panel p{margin:4px 0 6px;font-size:14px}
#panel ul{margin:2px 0 8px 18px;padding:0;font-size:13.5px}
#panel li{margin:2px 0}
#panel .set{color:var(--mute)}
#panel a{color:var(--acc);text-decoration:none}
#tip{position:fixed;pointer-events:none;background:#1b1f23;color:#fff;padding:8px 10px;border-radius:6px;font-size:12.5px;max-width:340px;display:none;z-index:9;line-height:1.35}
#tip .h{font-weight:600;margin-bottom:3px}
#tip .mute{color:#c9d1d9}
footer{padding:8px 24px 24px;color:var(--mute);font-size:12.5px;max-width:980px}
.legend{display:flex;gap:10px;align-items:center;font-size:12.5px;color:var(--mute)}
.legend span.sw{display:inline-block;width:18px;height:14px;border-radius:3px;border:1px solid var(--line);vertical-align:middle}
</style>
</head>
<body>
<header>
<h1>AI literacy framework × the platform's instruments</h1>
<p class="sub">Built from the __COUNT__ use reports: for every instrument the mapping in section 9, read against the framework's "In the Classroom" examples. <b>(a)</b> = the report's scenario contains the classroom example's activity at its level. <b>(b)</b> = with a modification that reaches the level. A cell's number is the count of instruments, not a measure of quality. Hover lists the instruments, click shows their scenarios.</p>
</header>
<div class="controls">
  <button id="v1" class="on">Competences × levels</button>
  <button id="v2">Instruments × competences</button>
  <label><input type="checkbox" id="showb"> show (b) mutatis mutandis</label>
  <span class="legend"><span class="sw" id="sw0"></span>0 <span class="sw" id="sw1"></span>low <span class="sw" id="sw2"></span>high</span>
</div>
<main>
  <div id="grid"></div>
  <aside id="panel"><h2>Nothing selected</h2><p class="q">Click a cell.</p></aside>
</main>
<div id="tip"></div>
<footer>Framework: OECD / European Union (2026), <i>Empowering learners for the age of AI: An AI literacy framework for primary and secondary education</i>, OECD Publishing, Paris, <a href="https://doi.org/10.1787/65cd27d4-en">https://doi.org/10.1787/65cd27d4-en</a>, CC BY 4.0. Expectation texts are the framework's wording. Reports and mapping: V __VERSION__ of the use reports, generated DATE from the report files in this folder. Since 2026-11-06 this mapping (V __VERSION__) is what the platform's Help and Together read; the earlier table docs/ailit/unterstuetzung.tsv remains as a record.</footer>
<script id="data" type="application/json">DATA</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const grid=document.getElementById('grid'),panel=document.getElementById('panel'),tip=document.getElementById('tip');
let view='v1',showB=false,sel=null;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const label=i=>`${i.num} ${i.name}`;
function byCell(){const m={};for(const i of D.instruments){for(const k of ['a','b'])for(const l of i[k]){(m[l.cell]??={a:[],b:[]})[k].push({i,l});}}return m;}
const CELLS=byCell();
const maxA=Math.max(1,...Object.values(CELLS).map(c=>c.a.length));
function shade(n){if(!n)return '#f3f4f6';const t=Math.min(1,n/maxA);const l=94-t*62;return `hsl(206 60% ${l}%)`;}
function ink(n){return n/maxA>0.55?'#fff':'var(--ink)';}
document.getElementById('sw0').style.background=shade(0);document.getElementById('sw1').style.background=shade(Math.ceil(maxA/4));document.getElementById('sw2').style.background=shade(maxA);
function renderV1(){
  let h='<table><thead><tr><th></th>'+D.levels.map(l=>`<th class="lvl">${l}</th>`).join('')+'</tr></thead><tbody>';
  for(const dom of D.domains){
    h+=`<tr class="dom"><td colspan="4">${dom}</td></tr>`;
    for(const c of D.competences.filter(c=>c.domain===dom)){
      h+=`<tr><td class="comp"><b>${c.code}</b><small>${esc(c.title)}</small></td>`;
      for(const lv of D.levels){const key=`${c.code}|${lv}`;const cell=CELLS[key]||{a:[],b:[]};const na=cell.a.length,nb=cell.b.length;
        const cls='cell'+(showB&&nb?' hasb':'')+(sel===key?' sel':'');
        h+=`<td class="${cls}" data-key="${key}" style="background-color:${shade(na)};color:${ink(na)}"><span class="n">${na||''}</span>${showB&&nb?`<span class="nb">+${nb}</span>`:''}</td>`;}
      h+='</tr>';}
  }
  const bey=D.instruments.filter(i=>i.beyond);
  h+=`<tr class="dom"><td colspan="4">Outside the framework</td></tr><tr><td class="comp"><b>Beyond</b><small>what the reports place outside every competence</small></td><td class="beyond${sel==='beyond'?' sel':''}" colspan="3" data-key="beyond"><b>${bey.length}</b> of ${D.instruments.length} reports carry a "Beyond the framework" paragraph</td></tr>`;
  h+='</tbody></table>';grid.innerHTML=h;
}
function marks(i,c){const out=[];for(const lv of D.levels){const key=`${c.code}|${lv}`;const a=i.a.some(l=>l.cell===key),b=i.b.some(l=>l.cell===key);const ch=lv[0];if(a)out.push(`<b>${ch}</b>`);else if(b&&showB)out.push(`<i>${ch}</i>`);}return out;}
function renderV2(){
  let h='<table class="inst"><thead><tr><th></th>'+D.competences.map(c=>`<th class="c" title="${esc(c.title)}">${c.code}</th>`).join('')+'<th class="c">Beyond</th></tr></thead><tbody>';
  for(const i of D.instruments){
    h+=`<tr><td class="name">${esc(label(i))}</td>`;
    for(const c of D.competences){const m=marks(i,c);const key=`${i.num}|${c.code}`;
      h+=`<td class="m${m.length?'':' empty'}${sel===key?' sel':''}" data-key="${key}">${m.join('')}</td>`;}
    h+=`<td class="m${i.beyond?'':' empty'}${sel===i.num+'|beyond'?' sel':''}" data-key="${i.num}|beyond">${i.beyond?'<b>●</b>':''}</td></tr>`;}
  h+='</tbody></table>';grid.innerHTML=h;
}
function render(){(view==='v1'?renderV1:renderV2)();}
function scenList(i,refs){if(!refs.length)return '';return '<ul>'+refs.map(r=>{const s=i.scenarios[r];return s?`<li><b>${r}</b> ${esc(s.title)}${s.setting?` <span class="set">(${esc(s.setting)})</span>`:''}</li>`:`<li><b>${r}</b></li>`;}).join('')+'</ul>';}
function showCell(key){
  const [code,lv]=key.split('|');const cell=CELLS[key]||{a:[],b:[]};const c=D.competences.find(x=>x.code===code);
  let h=`<h2>${code} ${lv}</h2><p class="q">"${esc(D.expectations[key]||'')}"</p>`;
  if(D.classroom[key])h+=`<p class="cls"><b>In the Classroom:</b> ${esc(D.classroom[key])}</p>`;
  h+=`<p class="cls">${esc(c?c.title:'')}</p>`;
  const groups=[['a',cell.a,'(a) 100 % hits'],['b',cell.b,'(b) mutatis mutandis']];
  for(const [k,arr,title] of groups){if(k==='b'&&!showB)continue;h+=`<h3><span class="tag ${k}">${k}</span>${title}: ${arr.length}</h3>`;
    if(!arr.length)h+='<p class="set">none</p>';
    for(const {i,l} of arr){h+=`<p><b>${esc(label(i))}</b> <a href="${esc(i.file)}" title="report">↗</a><br>${esc(l.text)}</p>${scenList(i,l.scen)}`;}}
  panel.innerHTML=h;
}
function showBeyond(){let h=`<h2>Beyond the framework</h2><p class="q">What the reports place outside every competence of the framework.</p>`;for(const i of D.instruments.filter(i=>i.beyond))h+=`<h3>${esc(label(i))} <a href="${esc(i.file)}">↗</a></h3><p>${esc(i.beyond)}</p>`;panel.innerHTML=h;}
function showInst(num,code){
  const i=D.instruments.find(x=>x.num===num);let h=`<h2>${esc(label(i))}</h2><p class="cls">${esc(i.route)} · <a href="${esc(i.file)}">${esc(i.file)}</a></p>`;
  if(code==='beyond'){h+=`<h3>Beyond the framework</h3><p>${esc(i.beyond||'—')}</p>`;}
  else{const c=D.competences.find(x=>x.code===code);h+=`<p class="q">${esc(c.title)}</p>`;
    for(const k of ['a','b']){if(k==='b'&&!showB)continue;const arr=i[k].filter(l=>l.cell.startsWith(code+'|'));if(!arr.length)continue;
      for(const l of arr){const lv=l.cell.split('|')[1];h+=`<h3><span class="tag ${k}">${k}</span>${code} ${lv}</h3><p class="q">"${esc(l.quote)}"</p><p>${esc(l.text)}</p>${scenList(i,l.scen)}`;}}
    if(i.nonfits)h+=`<p class="cls"><b>Non-fits:</b> ${esc(i.nonfits)}</p>`;}
  const all=Object.entries(i.scenarios);if(all.length){h+=`<h3>All scenarios of this report</h3><ul>`+all.map(([r,s])=>`<li><b>${r}</b> ${esc(s.title)}${s.setting?` <span class="set">(${esc(s.setting)})</span>`:''}</li>`).join('')+'</ul>';}
  panel.innerHTML=h;
}
function tipFor(key){
  if(key==='beyond'){const b=D.instruments.filter(i=>i.beyond);return `<div class="h">Beyond the framework · ${b.length}</div>`+b.map(label).map(esc).join('<br>');}
  if(/^\d\d\|/.test(key)){const [num,code]=key.split('|');const i=D.instruments.find(x=>x.num===num);if(code==='beyond')return `<div class="h">${esc(label(i))}</div><span class="mute">${esc((i.beyond||'').slice(0,220))}…</span>`;
    const ls=[...i.a.map(l=>['a',l]),...(showB?i.b.map(l=>['b',l]):[])].filter(([,l])=>l.cell.startsWith(code+'|'));if(!ls.length)return '';
    return `<div class="h">${esc(label(i))} · ${code}</div>`+ls.map(([k,l])=>`(${k}) ${l.cell.split('|')[1]}${l.scen.length?' · '+l.scen.join(', '):''}`).join('<br>');}
  const cell=CELLS[key]||{a:[],b:[]};let h=`<div class="h">${key.replace('|',' ')} · (a) ${cell.a.length}${showB?` · (b) ${cell.b.length}`:''}</div><span class="mute">${esc((D.expectations[key]||'').slice(0,160))}${(D.expectations[key]||'').length>160?'…':''}</span>`;
  if(cell.a.length)h+='<br><br>'+cell.a.map(({i,l})=>esc(label(i))+(l.scen.length?` <span class="mute">${l.scen.join(', ')}</span>`:'')).join('<br>');
  if(showB&&cell.b.length)h+='<br><br><span class="mute">(b)</span><br>'+cell.b.map(({i})=>esc(label(i))).join('<br>');
  return h;
}
grid.addEventListener('mousemove',e=>{const td=e.target.closest('td[data-key]');if(!td){tip.style.display='none';return;}const h=tipFor(td.dataset.key);if(!h){tip.style.display='none';return;}tip.innerHTML=h;tip.style.display='block';const x=Math.min(e.clientX+14,window.innerWidth-360),y=Math.min(e.clientY+14,window.innerHeight-tip.offsetHeight-10);tip.style.left=x+'px';tip.style.top=y+'px';});
grid.addEventListener('mouseleave',()=>tip.style.display='none');
grid.addEventListener('click',e=>{const td=e.target.closest('td[data-key]');if(!td)return;const key=td.dataset.key;sel=key;render();
  if(key==='beyond')showBeyond();else if(/^\d\d\|/.test(key)){const [num,code]=key.split('|');showInst(num,code);}else showCell(key);});
document.getElementById('showb').addEventListener('change',e=>{showB=e.target.checked;render();if(sel){if(sel==='beyond')showBeyond();else if(/^\d\d\|/.test(sel)){const [n,c]=sel.split('|');showInst(n,c);}else showCell(sel);}});
for(const id of ['v1','v2'])document.getElementById(id).addEventListener('click',()=>{view=id;document.getElementById('v1').classList.toggle('on',id==='v1');document.getElementById('v2').classList.toggle('on',id==='v2');sel=null;render();});
render();
</script>
</body>
</html>
'''
# DATE, __VERSION__ and __COUNT__ before DATA: the inserted data must not be searched for a placeholder.
out = PAGE.replace('DATE', data['generated']).replace('__VERSION__', VERSION).replace(
    '__COUNT__', str(len(instruments))).replace('DATA', json.dumps(data, ensure_ascii=False).replace('</', '<\\/'))
OUT_HTML.write_text(out, encoding='utf-8')
print('wrote', OUT_HTML.relative_to(REPO), len(out), 'bytes')
