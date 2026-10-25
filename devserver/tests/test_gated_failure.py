"""A run that fails in the slot is not a measurement of how long it takes.

The gate's `failed` mark used to ride on exceptions alone. A view that caught
its own trouble and RETURNED — a 400 for missing parameters, a 500 for a
backend that came back empty, a load reporting `success: false` with a 200 on
it — ended its `with` block normally, and the hold went into the books as a
valid reading. Eighteen such places stood in seven gated views (found
2026-08-18, four adversarial rounds).

Why it matters beyond tidiness: the hold feeds the shared ordering EMA and
overwrites the residency belief under its own key. An unmarked failure
therefore makes the next run of ANOTHER surface count as cold, and that run
files its warm success in the cold bucket — two of those and the spread gate
silences the config for good.

Run: python3 -m pytest devserver/tests/test_gated_failure.py -q
"""

import sys

from file_modules import REPO

# APPENDED, not inserted at the front: gpu_service has a `config.py` of
# its own, and putting it ahead of devserver/ would hand a later test
# the wrong one.
sys.path.append(str(REPO / "gpu_service"))

import contextlib

import pytest
from flask import Flask, jsonify

import services.gpu_admission as GA
from services.gpu_admission import answered_with_failure, gated


class Lease:
    failed = False


@pytest.fixture()
def app():
    return Flask(__name__)


def _antwort(app, bauen):
    """What a view returns, seen the way the decorator sees it."""
    with app.test_request_context():
        return bauen()


class TestWasAlsFehlschlagZaehlt:
    def test_vierhundert(self, app):
        assert answered_with_failure(
            _antwort(app, lambda: (jsonify({"error": "prompt required"}), 400)))

    def test_fuenfhundert(self, app):
        assert answered_with_failure(
            _antwort(app, lambda: (jsonify({"error": "backend empty"}), 500)))

    def test_ergebnis_ist_kein_fehlschlag(self, app):
        assert not answered_with_failure(
            _antwort(app, lambda: jsonify({"success": True, "audio_base64": "..."})))

    def test_zweihundert_mit_erfolg_false(self, app):
        """A load that loaded nothing answers 200 -- and held the card."""
        assert not_ok(app, {"success": False})

    def test_zweihundert_ohne_erfolgsfeld(self, app):
        """Says nothing about failing, so it is taken at its word."""
        assert not not_ok(app, {"axes": ["warm", "cold"]})

    def test_rohes_woerterbuch(self):
        assert answered_with_failure({"success": False})
        assert not answered_with_failure({"success": True})

    def test_text_bleibt_ein_ergebnis(self):
        assert not answered_with_failure("fertig")

    def test_status_als_zeichenkette(self, app):
        assert answered_with_failure(
            _antwort(app, lambda: (jsonify({"error": "x"}), "503 Service Unavailable")))

    def test_gestreute_antwort_wird_nicht_angefasst(self, app):
        """Reading a streamed body would consume it."""
        with app.test_request_context():
            from flask import Response
            r = Response((x for x in ["a", "b"]), mimetype="application/json")
            assert r.is_streamed
            assert not answered_with_failure(r)


def not_ok(app, koerper):
    return answered_with_failure(_antwort(app, lambda: jsonify(koerper)))


class TestDerDekoratorMarkiert:
    """The decorator has to actually set it on the lease."""

    @pytest.fixture(autouse=True)
    def schleuse(self, monkeypatch):
        self.lease = Lease()
        prueflauf = self

        class Schleuse:
            @contextlib.contextmanager
            def slot(self, *a, **kw):
                yield prueflauf.lease

        monkeypatch.setattr(GA, "get_gpu_admission", lambda: Schleuse())

    def test_fehlschlag_wird_markiert(self, app):
        @gated("probe")
        def sicht():
            return jsonify({"error": "prompt required"}), 400
        with app.test_request_context():
            sicht()
        assert self.lease.failed is True

    def test_ergebnis_bleibt_ungemarkt(self, app):
        @gated("probe")
        def sicht():
            return jsonify({"success": True})
        with app.test_request_context():
            sicht()
        assert self.lease.failed is False

    def test_ausnahme_bleibt_ausnahme(self, app):
        """The old path must keep working: slot() marks on the way out."""
        @gated("probe")
        def sicht():
            raise RuntimeError("die Karte")
        with app.test_request_context():
            with pytest.raises(RuntimeError):
                sicht()

    def test_ohne_lease_kein_absturz(self, app, monkeypatch):
        """Reentrant use yields None -- the outer slot owns the mark."""
        class Schleuse:
            @contextlib.contextmanager
            def slot(self, *a, **kw):
                yield None
        monkeypatch.setattr(GA, "get_gpu_admission", lambda: Schleuse())

        @gated("probe")
        def sicht():
            return jsonify({"error": "x"}), 400
        with app.test_request_context():
            assert sicht()[1] == 400
