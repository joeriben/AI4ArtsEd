"""Stop means stop: the card stops computing, not just the page.

Until 2026-08-29 pressing stop on the Diffusers path ended the SSE stream and
nothing else. The generation thread ran on and the card finished the picture —
in the log a `Cancelled during Diffusers generation` and, eight seconds later,
a `STAGE4-GEN Success` for something nobody would ever see. The ComfyUI path
had done it properly all along (`cancel_job`).

Nothing had to be invented: Diffusers leaves the denoising loop as soon as
`pipe._interrupt` is set, and `callback_on_step_end` was already passed on
every generation path — used only for the progress bar. What was missing was
a flag, an endpoint, and the DevServer actually calling it.

Two kinds of test, because two things can go wrong:

1. The registry must behave (TestDieMarke, TestDerHaken) — that is testable
   here, without a card.
2. The paths must be WIRED to it (TestVerdrahtung). Source reads, on purpose:
   the fault was never a wrong return value, it was a hook that nobody had
   connected. A unit test of the registry would have passed on the old code
   just as happily.

Run: python3 -m pytest devserver/tests/test_generation_cancel.py -q
"""

import re
import sys
import time

from file_modules import REPO

# APPENDED, not inserted at the front: gpu_service has a `config.py` of
# its own, and putting it ahead of devserver/ would hand a later test
# the wrong one.
sys.path.append(str(REPO / "gpu_service"))

import pytest

from services.generation_cancel import (GenerationCancelled, clear_cancel,
                                        interrupt_if_cancelled, is_cancelled,
                                        raise_if_cancelled, request_cancel)
import services.generation_cancel as gc
from services.gpu_admission import CURRENT_RUN_LABEL

BACKEND = REPO / "gpu_service" / "services" / "diffusers_backend.py"
GPU_ROUTES = REPO / "gpu_service" / "routes" / "diffusers_routes.py"
DEV_ROUTES = (REPO / "devserver" / "my_app" / "routes"
              / "schema_pipeline_routes.py")

LAUF = "test_run_4711"


class Pipe:
    """As much of a diffusers pipeline as the hook touches."""
    _interrupt = False


@pytest.fixture(autouse=True)
def sauber():
    """No mark and no label may leak from one test into the next."""
    with gc._lock:
        gc._cancelled.clear()
    marke = CURRENT_RUN_LABEL.set("")
    yield
    CURRENT_RUN_LABEL.reset(marke)
    with gc._lock:
        gc._cancelled.clear()


class TestDieMarke:
    def test_setzen_lesen_loeschen(self):
        assert request_cancel(LAUF) is True
        assert is_cancelled(LAUF)
        clear_cancel(LAUF)
        assert not is_cancelled(LAUF)

    def test_ohne_namen_keine_marke(self):
        assert request_cancel("") is False
        assert not is_cancelled("")

    def test_fremder_lauf_bleibt_unberuehrt(self):
        """A stop names one run. It must not end somebody else's."""
        request_cancel(LAUF)
        assert not is_cancelled("ein_anderer_lauf")

    def test_alte_marke_wird_weggekehrt(self):
        """A stop that came a moment too late is read by no run at all."""
        with gc._lock:
            gc._cancelled["uralt"] = time.time() - (gc._TTL + 60)
        request_cancel(LAUF)          # sweeps on the way in
        assert not is_cancelled("uralt")
        assert is_cancelled(LAUF)


class TestDerHaken:
    def test_haelt_die_schleife_an(self):
        CURRENT_RUN_LABEL.set(LAUF)
        request_cancel(LAUF)
        pipe = Pipe()
        assert interrupt_if_cancelled(pipe) is True
        assert pipe._interrupt is True

    def test_ohne_marke_laeuft_es_weiter(self):
        CURRENT_RUN_LABEL.set(LAUF)
        pipe = Pipe()
        assert interrupt_if_cancelled(pipe) is False
        assert pipe._interrupt is False

    def test_ohne_namen_kein_eingriff(self):
        """A run nobody can name cannot be stopped by name either."""
        request_cancel(LAUF)
        pipe = Pipe()                 # CURRENT_RUN_LABEL is empty here
        assert interrupt_if_cancelled(pipe) is False

    def test_der_haken_verbraucht_die_marke_nicht(self):
        """It fires once per step; raise_if_cancelled must still see it."""
        CURRENT_RUN_LABEL.set(LAUF)
        request_cancel(LAUF)
        interrupt_if_cancelled(Pipe())
        interrupt_if_cancelled(Pipe())
        assert is_cancelled(LAUF)

    def test_danach_ist_es_ein_halt_kein_ergebnis(self):
        CURRENT_RUN_LABEL.set(LAUF)
        request_cancel(LAUF)
        with pytest.raises(GenerationCancelled) as e:
            raise_if_cancelled()
        assert e.value.run_label == LAUF

    def test_die_marke_ist_danach_verbraucht(self):
        """Or the next press under the same run id would die at step one."""
        CURRENT_RUN_LABEL.set(LAUF)
        request_cancel(LAUF)
        with pytest.raises(GenerationCancelled):
            raise_if_cancelled()
        raise_if_cancelled()          # must not raise a second time

    def test_ungestoert_faellt_nichts_an(self):
        CURRENT_RUN_LABEL.set(LAUF)
        raise_if_cancelled()


# --------------------------------------------------------------- Verdrahtung

def _methode(text: str, name: str) -> str:
    zeilen = text.split("\n")
    start = next(i for i, ln in enumerate(zeilen)
                 if re.match(r"^    async def %s\(" % re.escape(name), ln))
    for i in range(start + 1, len(zeilen)):
        if re.match(r"^    (async def |def )", zeilen[i]):
            return "\n".join(zeilen[start:i])
    return "\n".join(zeilen[start:])


DREI_WEGE = ("generate_image", "generate_video", "generate_video_from_image")


class TestVerdrahtung:
    @pytest.mark.parametrize("name", DREI_WEGE)
    def test_der_rueckruf_kennt_den_haken(self, name):
        koerper = _methode(BACKEND.read_text(encoding="utf-8"), name)
        assert "interrupt_if_cancelled" in koerper, (
            "%s passes callback_on_step_end for the progress bar but never "
            "asks whether the run was stopped. Then stop only ends the page "
            "and the card computes to the end." % name)

    @pytest.mark.parametrize("name", DREI_WEGE)
    def test_nach_dem_lauf_wird_gefragt(self, name):
        koerper = _methode(BACKEND.read_text(encoding="utf-8"), name)
        assert "raise_if_cancelled" in koerper, (
            "%s does not ask after the pipeline returns. An interrupted "
            "pipeline does not raise -- it hands back half-denoised latents, "
            "and those would be served as the result." % name)

    @pytest.mark.parametrize("name", DREI_WEGE)
    def test_ein_halt_ist_kein_fehlschlag(self, name):
        koerper = _methode(BACKEND.read_text(encoding="utf-8"), name)
        assert "except GenerationCancelled:" in koerper, (
            "%s swallows the stop in its `except Exception -> return None`. "
            "Then a stop is booked as a failed generation." % name)

    def test_der_endpunkt_steht(self):
        quelle = GPU_ROUTES.read_text(encoding="utf-8")
        assert "'/api/diffusers/cancel'" in quelle
        assert "request_cancel(run_label)" in quelle

    def test_beide_abbrueche_reisen_zusammen(self):
        """Wherever the ComfyUI job is cancelled, the Diffusers run is too.

        Which backend a run uses is not recorded in the tracker entry, so both
        are told. If a new cancel site appears for one of them only, the other
        backend keeps the old hole -- exactly the state this fixed.
        """
        quelle = DEV_ROUTES.read_text(encoding="utf-8")
        comfy = quelle.count("_cancel_comfyui_for(device_id)")
        diff = quelle.count("_cancel_diffusers_for(device_id)")
        assert diff >= comfy, (
            "%d ComfyUI cancel sites, %d for Diffusers" % (comfy, diff))
