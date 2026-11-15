"""Der bearbeitete Kontext ist Text vom Besucher und geht durch dasselbe Tor.

Bis zum 2026-08-29 tat er das nicht. Auf drei Wegen kam ein `context_prompt`
am Sicherheitstor vorbei, und auf zweien davon war er vorher schon bei einem
Modell gewesen: `execute_stage2` und `interception_pipeline` schickten ihn zum
Uebersetzen an ein lokales Modell und prueften erst danach — und dann
`input_text`, nie den Kontext. Der Strom-Weg hielt die Reihenfolge ein, pruefte
aber ebenfalls nur den einen der beiden Texte.

Zwei Arten von Pruefung stehen hier, weil zwei Dinge schiefgehen koennen:

1. Das Tor muss BEIDE Texte sehen (`test_beide_texte`) — das prueft, was der
   Helfer tut.
2. Das Tor muss VOR der Uebersetzung stehen (`test_reihenfolge`) — das prueft,
   wo es steht. Diese zweite ist eine Lesepruefung am Quelltext, und das mit
   Absicht: der urspruengliche Fehler war eine Reihenfolge, kein falscher
   Rueckgabewert. Ein Test, der nur den Helfer aufruft, haette ihn nicht
   gefunden.

Das Tor ist auf allen drei Wegen der Eingang, seit dem 2026-11-01 auch auf der
Vorpruefung. Er haelt Namen lebender Privatpersonen und Adressen an, kein
Kennzeichen; der Reiz ist deshalb ein Name in einem beschreibenden Satz.
Namenserkennung und Namensfrage stehen hier fest, so dass kein Modell gefragt
wird. Was der Eingang selbst entscheidet, prueft test_safety_gate.py.
"""

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

ROUTES = REPO / "my_app" / "routes" / "schema_pipeline_routes.py"

HARMLOS = "Ein Haus steht in einer Landschaft."
NAME = "Max Mustermann"
BLOCKT = "Ein Bild von Max Mustermann vor seinem Haus."


# --------------------------------------------------------------- 1. beide Texte

@pytest.fixture
def namenspruefung(monkeypatch):
    """Namenserkennung und Namensfrage, festgelegt: erkannt wird NAME, und die
    Namensfrage bejaht ihn. Gibt die Texte zurueck, die die Erkennung gesehen
    hat."""
    from my_app.services import safety_gate
    from schemas.engine import stage_orchestrator
    gesehen = []

    def erkennung(text):
        gesehen.append(text)
        return (NAME in text, [NAME] if NAME in text else [], True)

    monkeypatch.setattr(stage_orchestrator, "fast_dsgvo_check", erkennung)
    monkeypatch.setattr(stage_orchestrator, "llm_personal_data_check",
                        lambda text, names=None: NAME in text)
    # Der Eingang merkt sich, was er durchgelassen hat; ein Text aus einem
    # anderen Test soll hier nicht als bekannt gelten.
    safety_gate._RELEASED.clear()
    yield gesehen
    safety_gate._RELEASED.clear()


def _check(fields, level="kids"):
    from my_app.routes.schema_pipeline_routes import check_intake_texts
    return check_intake_texts(fields, level=level)


class TestBeideTexte:
    def test_harmlos_geht_durch(self, namenspruefung):
        verdict = _check({"input_text": HARMLOS, "context_prompt": HARMLOS})
        assert verdict.passed, verdict

    def test_reiz_im_input_text_blockt(self, namenspruefung):
        verdict = _check({"input_text": BLOCKT, "context_prompt": HARMLOS})
        assert not verdict.passed
        assert verdict.field == "input_text"

    def test_reiz_im_context_prompt_blockt(self, namenspruefung):
        """Der Fall, der bis zum 2026-08-29 durchlief."""
        verdict = _check({"input_text": HARMLOS, "context_prompt": BLOCKT})
        assert not verdict.passed
        assert verdict.field == "context_prompt"

    def test_leerer_kontext_kostet_nichts(self, namenspruefung):
        verdict = _check({"input_text": HARMLOS, "context_prompt": ""})
        assert verdict.passed
        assert namenspruefung == [HARMLOS]

    def test_research_hebt_das_tor_auf(self, namenspruefung):
        """Unveraendertes Verhalten: auf research prueft der Eingang nichts."""
        verdict = _check({"input_text": BLOCKT}, level="research")
        assert verdict.passed
        assert namenspruefung == []


# ------------------------------------------------------------- 2. Reihenfolge

def _funktion(name):
    """Der Quelltext einer Funktion aus der Routen-Datei."""
    src = ROUTES.read_text(encoding="utf-8")
    lines = src.split("\n")
    start = next(i for i, ln in enumerate(lines)
                 if re.match(r"^(async )?def %s\(" % re.escape(name), ln))
    for i in range(start + 1, len(lines)):
        if re.match(r"^(@|async def |def )", lines[i]):
            return "\n".join(lines[start:i])
    return "\n".join(lines[start:])


class TestReihenfolge:
    def test_execute_stage2_prueft_vor_dem_uebersetzen(self):
        # The run is called `_run_stage2` since 2026-09-04. The route was put on
        # the platform's SSE transport so that a long interception survives the
        # edge's 100-second cut, and the body moved out of the view function to
        # get there. Same path, same order, a different function to read it in.
        # Since 2026-10-10 the translation itself stands in `_translate_context`;
        # what this reads is the order of the two calls in the run. Since
        # 2026-10-31 the check there is the intake, and since 2026-11-01 on the
        # pre-check too.
        body = _funktion("_run_stage2")
        tor = body.index("check_intake_texts(")
        uebersetzung = body.index("_translate_context(")
        assert tor < uebersetzung, (
            "Der Eingang steht wieder HINTER der Kontext-Uebersetzung. "
            "Damit war der bearbeitete Kontext bei einem Modell, bevor ihn "
            "irgendetwas geprueft hat.")

    def test_interception_pipeline_prueft_vor_dem_uebersetzen(self):
        # Der Lauf heisst seit dem 2026-09-04 `_run_interception_pipeline`: die
        # Route bekam an dem Tag den SSE-Transport der Plattform, damit ein
        # langer Lauf den 100-Sekunden-Schnitt der Kante ueberlebt, und der
        # Rumpf zog dafuer aus der View-Funktion aus. Gleicher Weg, gleiche
        # Reihenfolge, eine andere Funktion zum Nachlesen.
        # Since 2026-10-31 the check there is the intake.
        body = _funktion("_run_interception_pipeline")
        tor = body.index("check_intake_texts(")
        uebersetzung = body.index("_translate_context(")
        assert tor < uebersetzung, (
            "Dieselbe Reihenfolge wie in execute_stage2, und derselbe Grund.")

    def test_jeder_weg_reicht_den_kontext_an_das_tor(self):
        """Wer `context_prompt` liest und an die Pipeline gibt, prueft ihn auch.

        Gelesen wird er an sieben Stellen; die Abgrenzung ist am 2026-08-29
        einzeln nachgesehen worden:

        - Die drei hier geprueften geben ihn in die Pipeline-Config bzw. an das
          Uebersetzungsmodell. Sie muessen das Tor rufen.
        - `optimize_pipeline` und `execute_optimization_streaming` trugen in
          der Sicherheits-Landkarte `unchecked-proxy` (Werkzeuge HINTER
          Stage 2, Eingabe bereits geprueft); beide sind seit 2026-10-10 weg.
        - `execute_generation_streaming` und `generation_endpoint` reichen ihn
          nur bis Stage 4 durch, wo er ins Protokoll geschrieben und an kein
          Modell gegeben wird.
        """
        # `_run_stage2` is the body of /pipeline/stage2 — see the note above;
        # the view function `execute_stage2` has been the branch between a
        # stream and one JSON body since 2026-09-04.
        # `_run_interception_pipeline` ist der Rumpf von /pipeline/interception
        # — siehe die Notiz oben; die View-Funktion `interception_pipeline` ist
        # seit dem 2026-09-04 die Weiche zwischen zwei Stroemen und einem
        # JSON-Body.
        for name in ("_run_stage2", "_run_interception_pipeline",
                     "execute_pipeline_streaming"):
            body = _funktion(name)
            assert "context_prompt" in body, name
            assert "check_intake_texts(" in body, (
                "%s liest einen context_prompt, reicht ihn aber nicht an das "
                "Tor" % name)
            assert "'context_prompt': context_prompt" in body, (
                "%s ruft das Tor, gibt ihm aber den Kontext nicht mit" % name)
