"""The tokenizers of one pipeline are one object, and one thread at a time.

Twice in two days a running generation died with `RuntimeError: Already
borrowed` raised inside `tokenizer_3` — the Rust tokenizer's own borrow check,
tripped because a describing surface was reading the same tokenizer from
another thread while the generation held it. The generation is what was lost;
the describing call went through.

The fake here is that borrow check and nothing else: a tokenizer that refuses
to be entered from a second thread while it is busy. Under the fix every path
in the backend that touches a tokenizer takes the same inference lock, so the
refusal never happens; without it, this file goes red in a second.

No model, no GPU, no diffusers pipeline: a stand-in object with the three
tokenizer attributes SD3.5 has.
"""

import asyncio
import contextlib
import os
import sys
import threading
import time
import types

import pytest

GPU_SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if GPU_SERVICE_DIR not in sys.path:
    sys.path.insert(0, GPU_SERVICE_DIR)

from services.diffusers_backend import DiffusersImageGenerator  # noqa: E402

FAKE_MODEL = "fake/triple-encoder"


class BorrowCheckedTokenizer:
    """A Rust tokenizer's borrow rule, in Python: one thread inside at a time."""

    def __init__(self, dwell_s: float = 0.004):
        self._inside = threading.Lock()
        self.dwell_s = dwell_s
        self.calls = 0
        self.bos_token_id = 1
        self.eos_token_id = 2
        self.pad_token_id = 0
        self.all_special_ids = [0, 1, 2]

    @contextlib.contextmanager
    def _borrow(self):
        if not self._inside.acquire(blocking=False):
            # The real message, and the real shape: it is raised, not returned,
            # and it lands in whichever caller happened to be second.
            raise RuntimeError("Already borrowed")
        try:
            self.calls += 1
            time.sleep(self.dwell_s)          # the window the other thread hits
            yield
        finally:
            self._inside.release()

    def __call__(self, text, **kwargs):
        with self._borrow():
            return {"input_ids": [1, 5, 6, 7, 2]}

    def decode(self, ids, **kwargs):
        with self._borrow():
            return "token"

    def convert_ids_to_tokens(self, tid):
        with self._borrow():
            return "tok</w>"

    def enable_truncation(self, *args, **kwargs):
        with self._borrow():
            return None


class StubGate:
    """The plant-wide slot, reduced to a context manager."""

    @contextlib.contextmanager
    def slot(self, kind, model_id, required_mb, priority, timeout_s=None,
             label="", workload=""):
        yield types.SimpleNamespace(failed=False)


@pytest.fixture
def backend(monkeypatch):
    made = DiffusersImageGenerator()
    pipe = types.SimpleNamespace(
        tokenizer=BorrowCheckedTokenizer(),
        tokenizer_2=BorrowCheckedTokenizer(),
        tokenizer_3=BorrowCheckedTokenizer(),
        tokenizer_max_length=77,
    )
    made._pipelines[FAKE_MODEL] = pipe
    monkeypatch.setattr("services.gpu_admission.get_gpu_admission", lambda: StubGate())
    return made


def _run(fn, seconds=1.5):
    """Run fn in two threads at once for a while; collect what it raised."""
    errors = []
    stop = threading.Event()

    def _loop():
        while not stop.is_set():
            try:
                fn()
            except Exception as e:                          # noqa: BLE001
                errors.append(e)
                return

    threads = [threading.Thread(target=_loop) for _ in range(2)]
    for thread in threads:
        thread.start()
    time.sleep(seconds)
    stop.set()
    for thread in threads:
        thread.join(timeout=10)
    return errors


def test_a_describing_call_never_takes_a_generation_down(backend):
    """One thread describes a prompt, the other generates. Both keep their answer.

    This is the pair that failed in production: `encode_prompt_info` reading the
    tokenizers while a generation held them. Without the lock on the describing
    side, one of the two dies with "Already borrowed" — and which one dies is
    whichever loses the race, which is why it kept being the generation.
    """
    pipe = backend._pipelines[FAKE_MODEL]
    errors = []
    stop = threading.Event()

    def _describe():
        while not stop.is_set():
            try:
                asyncio.run(backend.encode_prompt_info("a red apple", FAKE_MODEL))
            except Exception as e:                          # noqa: BLE001
                errors.append(("describe", e))
                return

    def _generate_one():
        # What a generation does with the tokenizers, from inside the lock the
        # generation paths take.
        pipe.tokenizer("a red apple", padding="max_length", truncation=True)
        pipe.tokenizer_3("a red apple", padding=False, truncation=False)

    def _generate():
        while not stop.is_set():
            try:
                backend._locked_generate(_generate_one)
            except Exception as e:                          # noqa: BLE001
                errors.append(("generate", e))
                return

    threads = [threading.Thread(target=_describe), threading.Thread(target=_generate)]
    for thread in threads:
        thread.start()
    time.sleep(2.0)
    stop.set()
    for thread in threads:
        thread.join(timeout=15)

    assert not errors, f"a borrow collided: {errors}"
    assert pipe.tokenizer_3.calls > 5, "both sides really did run"


def test_the_token_helper_is_safe_from_both_sides(backend):
    """_tokenize_prompt is called from a describing path and from inside a pass.

    So it takes the lock itself, and the lock is re-entrant: a caller that
    already holds it must not deadlock against itself, and a caller that holds
    nothing must still be serialised.
    """
    pipe = backend._pipelines[FAKE_MODEL]

    def _from_outside():
        assert backend._tokenize_prompt(pipe, "a red apple") != []

    def _from_inside():
        backend._locked_generate(lambda: backend._tokenize_prompt(pipe, "a red apple"))

    errors = _run(lambda: (_from_outside(), _from_inside()), seconds=1.5)
    assert not errors, f"a borrow collided, or the lock deadlocked: {errors}"


def test_a_pass_may_take_the_lock_it_already_holds(backend):
    """The re-entrancy itself, said once and plainly."""
    pipe = backend._pipelines[FAKE_MODEL]
    done = []

    def _nested():
        with backend._inference_lock:
            done.append(backend._tokenize_prompt(pipe, "x"))

    worker = threading.Thread(target=lambda: backend._locked_generate(_nested))
    worker.start()
    worker.join(timeout=10)
    assert not worker.is_alive(), "it deadlocked against its own lock"
    assert done and done[0]
