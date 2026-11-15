#!/usr/bin/env python3
"""The progress of a generation belongs to its run.

Generations queue for the card (`_locked_generate`). Until 2026-10-31 their
progress was one dict for the whole service, and a run waiting behind another
read that run's steps and its preview, which the DevServer streamed to its own
surface. Each run's progress is now filed under the label its request carries
(`run_label`), and the polling names the run it asks about.

  cd gpu_service && ../venv/bin/python -m pytest tests/test_progress_per_run.py
"""

import asyncio
import contextvars
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from flask import Flask  # noqa: E402

from services import diffusers_backend as backend  # noqa: E402
from services.gpu_admission import CURRENT_RUN_LABEL  # noqa: E402

IDLE = {"step": 0, "total_steps": 0, "active": False}


@pytest.fixture(autouse=True)
def empty_card():
    backend._progress_by_run.clear()
    yield
    backend._progress_by_run.clear()


def as_run(label, fn, *args):
    """Call `fn` the way a generation thread of the run `label` calls it."""
    def call():
        CURRENT_RUN_LABEL.set(label)
        return fn(*args)
    return contextvars.copy_context().run(call)


def test_a_run_reads_its_own_steps_and_picture():
    as_run("run_a", backend._progress_begin, 25)
    as_run("run_a", backend._progress_step, 3, 25)
    as_run("run_a", backend._progress_preview, "AAAA")
    assert backend.get_generation_progress("run_a") == {
        "step": 3, "total_steps": 25, "active": True, "preview": "AAAA"}


def test_a_run_waiting_for_the_card_reads_nothing_of_the_one_on_it():
    as_run("run_a", backend._progress_begin, 25)
    as_run("run_a", backend._progress_preview, "AAAA")
    assert backend.get_generation_progress("run_b") == IDLE
    assert backend.get_generation_progress("") == IDLE


def test_two_runs_keep_apart():
    as_run("run_a", backend._progress_begin, 25)
    as_run("run_b", backend._progress_begin, 30)
    as_run("run_a", backend._progress_step, 5, 25)
    as_run("run_b", backend._progress_step, 9, 30)
    assert (backend.get_generation_progress("run_a")["step"],
            backend.get_generation_progress("run_b")["step"]) == (5, 9)


def test_a_run_that_left_the_card_reads_idle_and_a_late_callback_does_not_bring_it_back():
    as_run("run_a", backend._progress_begin, 25)
    as_run("run_a", backend._progress_done)
    as_run("run_a", backend._progress_step, 25, 25)
    as_run("run_a", backend._progress_preview, "AAAA")
    assert backend.get_generation_progress("run_a") == IDLE
    assert backend._progress_by_run == {}


def test_the_generation_thread_files_under_the_run_of_its_request():
    """Every generation path runs its work through asyncio.to_thread, which
    copies the context the request's mark was set in."""
    async def generate():
        CURRENT_RUN_LABEL.set("run_a")
        await asyncio.to_thread(backend._progress_begin, 25)
        await asyncio.to_thread(backend._progress_step, 7, 25)

    asyncio.run(generate())
    assert backend.get_generation_progress("run_a")["step"] == 7


def test_the_route_answers_for_the_run_it_is_asked_about():
    from routes.diffusers_routes import diffusers_bp

    app = Flask(__name__)
    app.register_blueprint(diffusers_bp)
    client = app.test_client()
    as_run("run_a", backend._progress_begin, 25)
    as_run("run_a", backend._progress_preview, "AAAA")
    assert client.get("/api/diffusers/progress?run_label=run_a").get_json()["preview"] == "AAAA"
    assert client.get("/api/diffusers/progress?run_label=run_b").get_json() == IDLE
    assert client.get("/api/diffusers/progress").get_json() == IDLE


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-v']))
