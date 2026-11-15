#!/usr/bin/env python3
"""A check that cannot run does not grant permission.

Four shapes have broken this platform's age and content check since 2025, and
each test below stands at the line where one of them bit:

1. a verdict that fails to arrive read as a pass,
2. dead code in a check path,
3. a check asking a model that cannot answer its question,
4. a verdict read by substring, prefix, suffix or last word.

Run: python3 -m pytest devserver/tests/test_check_cannot_permit.py -q
"""
import builtins
import logging
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from my_app.services import safety_classifier           # noqa: E402
from my_app.services import safety_gate as gate         # noqa: E402
from my_app.utils import vlm_safety                      # noqa: E402
from schemas.engine import stage_orchestrator as so      # noqa: E402
from schemas.engine.pipeline_executor import PipelineExecutor  # noqa: E402


FLAGGED = ("function setup(){ createCanvas(400,400); }\n"
           "function draw(){ eval(atob('YWxlcnQoMSk=')); fetch('http://x/'); }")
CLEAN = ("function setup(){ createCanvas(400,400); }\n"
         "function draw(){ ellipse(200,200,50,50); }")


def _run_code_check(code, level='kids'):
    return gate.check_result_code(code, level=level)


@pytest.fixture()
def verdict(monkeypatch):
    """One scripted answer where the classifier's code question would be. The
    level's text question over the code is answered no beforehand, so that
    what is tested is the code question alone."""
    def script(answer=None, raises=None):
        def fake(policy, document, images=None):
            if raises is not None:
                raise raises
            return answer
        monkeypatch.setattr(gate, 'check_result_text', lambda text, *, level, field='text':
                            gate.Verdict(True, gate.CHECKPOINT_RESULT, level, field))
        monkeypatch.setattr(safety_classifier, 'is_unsafe', fake)
    return script


class TestTheCodeCheckDoesNotPassFlaggedCode:
    """The pattern list flags `eval(`, `fetch(` and their siblings and hands
    the case to a slower question. That question called
    `pipeline_executor.execute_chunk_async` — a method PipelineExecutor has
    never had — from 2025-12-01 to 2026-09-04, and the AttributeError was
    caught and answered with `safe: True` carrying the flagged code.

    Until 2026-11-01 the question went to the cloud verdict model, whose free
    text could also arrive cut off or unreadable. The check at the result asks
    the local classifier, which answers yes, no or nothing; nothing and a call
    that raises are the ways left of not getting an answer."""

    def test_a_verdict_that_never_arrives_is_not_a_pass(self, verdict):
        verdict(answer=None)
        v = _run_code_check(FLAGGED)
        assert not v.passed and v.operational
        assert v.reason == so.SAFETY_CHECK_UNAVAILABLE_MESSAGE

    def test_a_verdict_call_that_raises_is_not_a_pass(self, verdict):
        verdict(raises=RuntimeError('API Error: 524'))
        v = _run_code_check(FLAGGED)
        assert not v.passed and v.operational
        assert v.reason == so.SAFETY_CHECK_UNAVAILABLE_MESSAGE

    def test_an_unsafe_verdict_reads_as_a_rating_and_not_as_a_fault(self, verdict):
        """The two refusals mean different things to the child reading them."""
        verdict(answer=True)
        v = _run_code_check(FLAGGED)
        assert not v.passed and not v.operational
        assert v.reason_key == gate.REASON_CODE
        assert v.reason == so.build_safety_message([])

    def test_a_stated_safe_verdict_is_the_only_way_through(self, verdict):
        """The control. Without a case that passes under the same harness the
        rest of this class would assert nothing."""
        verdict(answer=False)
        assert _run_code_check(FLAGGED).passed

    def test_unflagged_code_never_reaches_the_code_question(self, verdict):
        verdict(raises=AssertionError('the code question was asked of unflagged code'))
        assert _run_code_check(CLEAN).passed

    def test_research_and_adult_ask_no_code_question(self, verdict):
        verdict(raises=AssertionError('these levels run no pattern list'))
        for level in ('research', 'adult'):
            assert _run_code_check(FLAGGED, level).passed

    def test_the_check_calls_no_method_the_executor_does_not_have(self):
        """Pattern 2, at its root. The check asks the classifier directly;
        nothing in it may reach back into the pipeline executor for a method
        that has to exist for the check to run at all."""
        import inspect
        assert not hasattr(PipelineExecutor, 'execute_chunk_async')
        source = inspect.getsource(gate.check_result_code)
        # Comments stripped: prose may name what the check does not call.
        code = '\n'.join(line.split('#', 1)[0] for line in source.splitlines())
        assert '.execute_chunk_async(' not in code
        assert 'pipeline_executor' not in code


class TestAVerdictIsAClaimAndCarriesItsNegation:
    """`_extract_verdict` took the first word, the last word, and failing those
    the last occurrence anywhere."""

    @pytest.mark.parametrize('text', [
        'The description mentions a weapon, so this is not safe',
        'Verdict: not safe',
        'Antwort: nicht safe',
    ])
    def test_a_negated_safe_states_unsafe(self, text):
        assert vlm_safety._extract_verdict(text) == 'unsafe'

    @pytest.mark.parametrize('text,expected', [
        ('SAFE', 'safe'),
        ('UNSAFE', 'unsafe'),
        ('**SAFE**', 'safe'),
        ('The analysis found no violence, gore or nudity. SAFE', 'safe'),
        ('The description does not contain unsafe content. SAFE', 'safe'),
    ])
    def test_a_stated_verdict_still_reads(self, text, expected):
        assert vlm_safety._extract_verdict(text) == expected

    @pytest.mark.parametrize('text', [
        '',
        '   ',
        'Presence of UNSAF',
        'Condition: Dark lighting/shadow',
        'Answer SAFE or UNSAFE',      # the model echoing its own instruction
        'This image is not unsafe.',  # a double negative is not a stated pass
    ])
    def test_what_cannot_be_read_is_no_verdict(self, text):
        assert vlm_safety._extract_verdict(text) is None


class TestTheClassifierCannotReportASafetyItDidNotGet:
    """`safety_classifier.score` is the one reader of the one answer now, so
    every way of not getting one has to come back None. It used to be three
    readers over three prose formats: a category list, a SAFE/UNSAFE word, and
    a reasoning field read by substring."""

    def _post(self, monkeypatch, **kw):
        import requests
        from my_app.services import safety_classifier as sc

        class Resp:
            status_code = kw.get('status', 200)
            text = kw.get('text', '')

            def json(self):
                if 'raises' in kw:
                    raise ValueError('not json')
                return kw.get('body', {})

        if kw.get('unreachable'):
            def post(*a, **k):
                raise requests.RequestException('no route to host')
        else:
            def post(*a, **k):
                return Resp()
        monkeypatch.setattr(requests, 'post', post)
        monkeypatch.setattr(sc, '_model', lambda: 'a-model')
        monkeypatch.setattr(sc, 'model_name', lambda: 'a-model')
        return sc.score('i', 'q', 'd')

    def test_an_unreachable_service_is_no_verdict(self, monkeypatch):
        assert self._post(monkeypatch, unreachable=True) is None

    def test_a_status_other_than_200_is_no_verdict(self, monkeypatch):
        assert self._post(monkeypatch, status=503, body={'error': 'no room'}) is None

    def test_a_body_without_a_score_is_no_verdict(self, monkeypatch):
        assert self._post(monkeypatch, body={'ok': True}) is None

    def test_a_body_that_is_not_json_is_no_verdict(self, monkeypatch):
        assert self._post(monkeypatch, raises=True) is None

    @pytest.mark.parametrize('status', [200, 503])
    @pytest.mark.parametrize('body', [['a list'], 'a string', 7])
    def test_a_body_that_is_json_but_no_object_is_no_verdict(self, monkeypatch, status, body):
        """JSON that is no object (a list, a string, a number) has no `.get`:
        on a status other than 200, the error detail raised AttributeError,
        which left score() instead of its None."""
        assert self._post(monkeypatch, status=status, body=body, text=str(body)) is None

    def _decoded(self, monkeypatch, status, content, encoding='utf-8'):
        """score() on a real requests.Response, which decodes the body itself."""
        import requests
        from my_app.services import safety_classifier as sc
        response = requests.Response()
        response.status_code = status
        response._content = content
        response.encoding = encoding
        monkeypatch.setattr(requests, 'post', lambda *a, **k: response)
        monkeypatch.setattr(sc, '_model', lambda: 'a-model')
        monkeypatch.setattr(sc, 'model_name', lambda: 'a-model')
        return sc.score('i', 'q', 'd')

    @pytest.mark.parametrize('content', [
        b'{"score": false}',
        b'{"score": true}',
        b'{"score": "0"}',
        b'{"score": " 0.0 "}',
        b'{"score": 1' + b'0' * 400 + b'}',
        b'[' * 100000 + b']' * 100000,
    ], ids=['false', 'true', 'a string', 'a string with spaces',
            'an integer too large for a float', 'nested too deep'])
    def test_an_answer_that_holds_no_number_is_no_verdict(self, monkeypatch, content):
        """float() read a JSON false as 0.0, a pass, true as 1.0, a rating,
        and a string as the number written in it; a 401-digit integer raised
        OverflowError, and a body nested deeper than the decoder goes raised
        RecursionError, both out of score() instead of its None."""
        assert self._decoded(monkeypatch, 200, content) is None

    @pytest.mark.parametrize('content,encoding', [
        (b'[' * 100000 + b']' * 100000, 'utf-8'),
        (b'{"error": "no room"}', 'idna'),
        (b'<html><body>' + b'x' * 187 + '\u00fc'.encode() + b'</body></html>', 'utf-8'),
        ('Fehler: kein Platz f\u00fcr das Modell'.encode('latin-1'), 'latin-1'),
        ('Fehler: kein Platz f\u00fcr das Modell'.encode('latin-1'), None),
        (None, 'utf-8'),
    ], ids=['nested too deep', 'a charset whose codec refuses replacement',
            'a character cut at byte 200', 'Latin-1 with its charset',
            'Latin-1 without a charset', 'no raw stream'])
    def test_an_error_body_that_cannot_be_read_is_no_verdict(self, monkeypatch, content, encoding):
        """On a status other than 200 the body is read only for the journal.
        A body nested too deep raised RecursionError there, and a charset
        whose codec takes no replacement at all (idna) raised UnicodeError
        from requests' .text, which it does for every body that is not
        empty, both out of score() instead of its None. The other bodies
        read through .text as before: one that is no UTF-8, with its charset
        or without, one cut inside a character at its 200th byte, and a
        Response without a raw stream, which has None there -- a stand-in;
        requests gives b"" for an empty body."""
        assert self._decoded(monkeypatch, 503, content, encoding) is None

    @pytest.mark.parametrize('content,encoding,detail', [
        (b'<html>' + b'y' * 5000 + b'</html>', 'utf-8', '<html>' + 'y' * 194),
        ('Fehler: kein Platz f\u00fcr das Modell'.encode(), 'utf-8',
         'Fehler: kein Platz f\u00fcr das Modell'),
        ('Fehler: kein Platz f\u00fcr das Modell'.encode('latin-1'), 'latin-1',
         'Fehler: kein Platz f\u00fcr das Modell'),
        ('Fehler: kein Platz f\u00fcr das Modell'.encode('latin-1'), 'utf-8',
         'Fehler: kein Platz f\ufffdr das Modell'),
        (b'{"error": "no room"}', 'idna', '{"error": "no room"}'),
        ('Fehler: kein Platz f\u00fcr das Modell'.encode('latin-1'), 'idna',
         'Fehler: kein Platz f\ufffdr das Modell'),
        (b'x' * 500, 'idna', 'x' * 200),
        (('\u00fc' * 150).encode(), 'idna', '\u00fc' * 100),
        (None, 'utf-8', ''),
        (b'<html>\r\n<body>\x1b[31mno room\x00</body>', 'utf-8',
         '<html>\\r\\n<body>\\x1b[31mno room\\x00</body>'),
        (b'C:\\models\\new', 'utf-8', 'C:\\\\models\\\\new'),
        (b'\x00' * 300, 'utf-8', '\\x00' * 50),
        (b'x' * 199 + b'\x1b', 'utf-8', 'x' * 199),
        (b'a\tb', 'utf-8', 'a\\tb'),
        ('Preis: 5 \u20ac'.encode('cp1252'), 'latin-1', 'Preis: 5 \\x80'),
    ], ids=['a long body', 'UTF-8', 'Latin-1 with its charset', 'Latin-1 sent as UTF-8',
            'a charset whose codec refuses replacement',
            'a charset whose codec refuses replacement, a body that is no UTF-8',
            'a charset whose codec refuses replacement, a long body',
            'a charset whose codec refuses replacement, a long body of two-byte characters', 'no raw stream',
            'line breaks and control characters', 'backslashes',
            'a long body of control characters', 'an escape that does not fit at the end', 'a tab',
            'a character beyond ASCII that is not printable'])
    def test_the_journal_shows_the_start_of_an_error_body_that_is_no_json(
            self, monkeypatch, caplog, content, encoding, detail):
        """What the journal says of an error body that is no JSON: at most 200
        characters of it, as requests decodes it, with U+FFFD for what its
        charset cannot decode; with a charset whose codec takes no
        replacement at all (idna), on which requests fails for every body
        that is not empty, JSON as well, its first 200 bytes as UTF-8, with
        U+FFFD for what is no UTF-8; and nothing for a Response without a
        raw stream. A character that is not printable -- a tab, a line break,
        a terminal's escape, and one beyond ASCII as well (U+0080, the euro
        sign of cp1252 read as Latin-1) -- and the backslash are written as
        Python writes them in a string, so that the record stays one line --
        a line break started an entry of its own in the journal -- and a
        backslash before an n does not read as a line break; and of what is
        written no more than 200 characters, without a character cut in
        half."""
        with caplog.at_level(logging.ERROR, logger='my_app.services.safety_classifier'):
            assert self._decoded(monkeypatch, 503, content, encoding) is None
        said = [r.getMessage() for r in caplog.records if 'answered 503' in r.getMessage()]
        assert said == [f'[SAFETY-CLASSIFIER] a-model answered 503 ({detail}) -- no verdict']

    @pytest.mark.parametrize('content,detail', [
        (b'{"error": "no room"}', 'no room'),
        (b'{"error": "' + b'e' * 500 + b'"}', 'e' * 200),
        (b'{"error": 7}', '7'),
        (b'{}', ''),
        (b'null', 'null'),
        (b'false', 'false'),
        (b'0', '0'),
        (b'[]', '[]'),
        (b'""', '""'),
        (b'{"error": null}', 'null'),
        (b'{"error": true}', 'true'),
        (b'{"error": {"code": 5, "why": "no room"}}', '{"code": 5, "why": "no room"}'),
        (b'{"error": "line one\\nline two"}', 'line one\\nline two'),
        (b'{"error": {"why": "kein Platz f\\u00fcr das Modell"}}', '{"why": "kein Platz f\u00fcr das Modell"}'),
        (b'{"error": "a\\\\nb"}', 'a\\\\nb'),
        (b'{"error": {"why": "' + b'e' * 500 + b'"}}', '{"why": "' + 'e' * 191),
        (b'{"error": {"why": "no room", "code": 5}}', '{"why": "no room", "code": 5}'),
        (b'{"error": "\\u202e\\u0085"}', '\\u202e\\x85'),
    ], ids=['an error', 'a long error', 'an error that is a number', 'an object without an error',
            'null', 'false', 'zero', 'an empty list', 'an empty string', 'an error that is null',
            'an error that is true', 'an error that is an object', 'an error with a line break',
            'an error that is an object, with a character that is no ASCII',
            'an error with a backslash before an n', 'a long error that is an object',
            'an error that is an object, its keys not in order',
            'an error with characters beyond ASCII that are not printable'])
    def test_the_journal_shows_the_error_of_a_json_body(self, monkeypatch, caplog, content, detail):
        """What the journal says of an error body that is JSON: the first 200
        characters of an object's "error", as text, an error that is no text
        as JSON writes it, its keys in their order and a character that is
        no ASCII as it is -- where it is printable -- and nothing for an
        object without one; JSON that is no object has its text shown, as a
        body that is no JSON does. null, false, 0 and an
        empty list or string showed nothing: `or {}` read them as an object
        without an error. An error that was null showed as None, and a line
        break in one began an entry of its own in the journal; a backslash
        before an n is written escaped, so that it does not read as one."""
        with caplog.at_level(logging.ERROR, logger='my_app.services.safety_classifier'):
            assert self._decoded(monkeypatch, 503, content) is None
        said = [r.getMessage() for r in caplog.records if 'answered 503' in r.getMessage()]
        assert said == [f'[SAFETY-CLASSIFIER] a-model answered 503 ({detail}) -- no verdict']

    @pytest.mark.parametrize('bad', [-0.1, 1.5, float('nan')])
    def test_a_score_outside_the_range_is_no_verdict(self, monkeypatch, bad):
        assert self._post(monkeypatch, body={'score': bad}) is None

    def test_an_empty_model_setting_is_no_verdict(self, monkeypatch):
        from my_app.services import safety_classifier as sc
        monkeypatch.setattr(sc, '_model', lambda: '')
        assert sc.score('i', 'q', 'd') is None

    def test_a_real_score_reads_on_both_sides_of_the_threshold(self, monkeypatch):
        from my_app.services import safety_classifier as sc
        monkeypatch.setattr(sc, 'score', lambda *a, **k: 0.51)
        assert sc.is_unsafe(sc.NAME_POLICY, 'x') is True
        monkeypatch.setattr(sc, 'score', lambda *a, **k: 0.49)
        assert sc.is_unsafe(sc.NAME_POLICY, 'x') is False


class TestTheDataProtectionGateCannotPermitWithoutAVerdict:
    """The gate that keeps real people's names away from every model behind it.
    It read a reasoning field by substring until 2026-09, and "SAFE" is a
    substring of "NOT SAFE"; it reads one number now, and no number blocks."""

    def _drive(self, monkeypatch, value):
        so._dsgvo_verify_cache.clear()
        from my_app.services import safety_classifier as sc
        monkeypatch.setattr(sc, 'score', lambda *a, **k: value)
        return so.llm_personal_data_check('some text')

    def test_no_verdict_blocks(self, monkeypatch):
        assert self._drive(monkeypatch, None) is None

    def test_a_yes_blocks(self, monkeypatch):
        assert self._drive(monkeypatch, 0.97) is True

    def test_a_no_passes(self, monkeypatch):
        assert self._drive(monkeypatch, 0.02) is False

    def test_the_cache_does_not_turn_no_verdict_into_one(self, monkeypatch):
        assert self._drive(monkeypatch, None) is None
        # A None was never cached, so the next call asks again rather than
        # serving the absence of an answer as an answer.
        assert self._drive(monkeypatch, 0.97) is True


class TestTheLevelQuestionDoesNotBypassItself:
    """`llm_service.check_safety` (run by `/run_workflow_stream` until that
    route was removed on 2026-10-10) answered a failed safety model with
    `{"is_safe": True, "note": "... bypassing check."}` — the first pattern,
    written out in words. It asked the level's question about the prompt a
    workflow was about to receive, and its cache answered for a prompt it had
    cleared. Since 2026-11-01 the check before the model asks that question,
    and the gate's memory of what passed is the one a check answers from;
    what was held against the old check is held against them here."""

    ORIGINAL = 'ein Haus am Meer'
    PROMPT = 'a house by the sea'

    @pytest.fixture(autouse=True)
    def _forget(self):
        gate._RELEASED.clear()
        yield
        gate._RELEASED.clear()

    def _check(self, level='kids'):
        # The original beside the prompt: the check reads both and translates
        # nothing itself.
        return gate.check_before_model({'prompt': self.PROMPT}, level=level,
                                       originals={'prompt': self.ORIGINAL})

    def _drive(self, monkeypatch, value, level='kids'):
        monkeypatch.setattr(safety_classifier, 'score', lambda *a, **k: value)
        return self._check(level)

    def test_no_verdict_blocks(self, monkeypatch):
        v = self._drive(monkeypatch, None)
        assert not v.passed and v.operational
        assert v.reason == so.SAFETY_CHECK_UNAVAILABLE_MESSAGE

    def test_a_yes_is_a_content_rating_and_not_a_fault(self, monkeypatch):
        v = self._drive(monkeypatch, 0.93)
        assert not v.passed and not v.operational
        assert v.reason != so.SAFETY_CHECK_UNAVAILABLE_MESSAGE

    def test_a_no_passes(self, monkeypatch):
        assert self._drive(monkeypatch, 0.04).passed

    def test_research_never_reaches_the_model(self, monkeypatch):
        def never(*a, **k):
            raise AssertionError('the classifier was asked on research')
        monkeypatch.setattr(safety_classifier, 'score', never)
        assert self._check('research').passed

    def test_adult_is_asked_its_own_question(self, monkeypatch):
        """The old check left adult out as well. Since 2026-11-01 adult is
        asked its own question before the model; research is the one level
        that checks nothing."""
        asked = []

        def score(instruct, query, document, images=None):
            asked.append((instruct, query))
            return 0.04
        monkeypatch.setattr(safety_classifier, 'score', score)
        assert self._check('adult').passed
        adult = (safety_classifier.LEVEL_INSTRUCTS['adult'],
                 safety_classifier.LEVEL_QUERIES['adult']['prompt'])
        assert asked and set(asked) == {adult}

    def test_a_pass_at_a_looser_level_does_not_answer_a_stricter_one(self, monkeypatch):
        """A prompt cleared under research answered the next kids run as safe:
        the old cache's key was the prompt alone, and a cache hit returned
        before the check. The gate remembers a text that passed with the level
        it passed at, and a stricter level asks again."""
        monkeypatch.setattr(safety_classifier, 'score', lambda *a, **k: 0.04)
        for level in ('research', 'adult'):
            assert gate.check_result_text(self.PROMPT, level=level).passed
        monkeypatch.setattr(safety_classifier, 'score', lambda *a, **k: 0.99)
        assert not gate.check_result_text(self.PROMPT, level='kids').passed


class TestTheStatutoryFilterDoesNotReportClearWhenItHasNoList:
    """§86a carries a statutory duty. The loader logged and handed back `{}`,
    and the filter then reported "clear" for every text — an empty list read as
    "nothing objectionable"."""

    def test_a_list_that_cannot_be_loaded_stops_the_run(self, monkeypatch):
        monkeypatch.setattr(so, '_BILINGUAL_86A_CACHE', None, raising=False)
        real_open = builtins.open

        def fake_open(path, *args, **kwargs):
            if 'stage1_86a_critical_bilingual.json' in str(path):
                raise FileNotFoundError(path)
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr(builtins, 'open', fake_open)
        with pytest.raises(RuntimeError, match='86a'):
            so.fast_filter_bilingual_86a('Hakenkreuz', 'de')

    def test_the_healthy_list_still_loads(self, monkeypatch):
        monkeypatch.setattr(so, '_BILINGUAL_86A_CACHE', None, raising=False)
        has_terms, _found = so.fast_filter_bilingual_86a('ein Baum im Garten', 'de')
        assert has_terms is False


def test_the_dead_fail_open_stage1_check_is_gone():
    """It had no caller, and on a pipeline failure it returned `(True, [])`
    under a log line reading "continuing (fail-open)". Dead code in a check
    path reads like a check that runs."""
    assert not hasattr(so, 'execute_stage1_safety')
    route_source = (Path(so.__file__).resolve().parents[2]
                    / 'my_app' / 'routes' / 'schema_pipeline_routes.py')
    assert 'execute_stage1_safety,' not in route_source.read_text(encoding='utf-8')
