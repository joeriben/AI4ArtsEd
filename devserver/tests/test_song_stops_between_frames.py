"""A stop ends the song between two frames.

The frame loop is heartlib's (HeartMuLaGenPipeline._forward) and asks nobody
between frames, and ComfyUI asks for its interrupt only before a node runs.
Until 2026-10-01 the HeartMuLa node asked once, before the loop: a stop
reached a song that was still loading and none that was being made, and the
card made the whole song for nobody. Since then the node asks at every frame
(_heartmula.generate).

ComfyUI is stubbed (the fixture of test_local_llm_finite.py); the pipeline is
a stand-in whose loop calls mula.generate_frame once per frame, as heartlib's
does.

Run: cd devserver && python3 -m pytest tests/test_song_stops_between_frames.py -q
"""
import sys
import threading
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from file_modules import load_module
from test_local_llm_finite import PACKAGE, llm  # noqa: F401  (the fixture)

FRAMES = 3000 // 80      # what a 3 s song asks of heartlib's loop


class Stopped(Exception):
    pass


@pytest.fixture
def song(llm, monkeypatch):
    _mod, torch = llm
    load_module("ai4artsed_comfyui._whole", PACKAGE / "_whole.py", register=True)
    node = load_module("ai4artsed_comfyui._heartmula", PACKAGE / "_heartmula.py", register=True)

    class Mula:
        made = 0

        def generate_frame(self, **kwargs):
            Mula.made += 1
            return torch.zeros(1, 9, dtype=torch.long)

    class Codec:
        def detokenize(self, frames):
            return torch.zeros(2, 480)

    class Pipe:
        def __init__(self):
            self.mula = Mula()
            self.codec = Codec()

        def preprocess(self, inputs, cfg_scale):
            return {}

        def _forward(self, inputs, max_audio_length_ms, **kwargs):
            frames = [self.mula.generate_frame(tokens=None)
                      for _ in range(max_audio_length_ms // 80)]
            return {"frames": torch.stack(frames)}

    pipe = Pipe()
    held = types.SimpleNamespace(lock=threading.Lock(), extra={"pipe": pipe}, key="heartmula/3B")
    monkeypatch.setattr(node, "get_built", lambda *a, **k: held)
    monkeypatch.setattr(node._card, "on_card", lambda *a, **k: torch.device("cpu"))
    return node, pipe, Mula


def _stop_after(monkeypatch, asks):
    """ComfyUI's interrupt, raised from the asks-th question on."""
    seen = {"asks": 0}

    def ask():
        seen["asks"] += 1
        if seen["asks"] >= asks:
            raise Stopped()

    monkeypatch.setattr(sys.modules["comfy.model_management"],
                        "throw_exception_if_processing_interrupted", ask)


def test_a_stop_ends_the_song_between_two_frames(song, monkeypatch):
    node, pipe, Mula = song
    _stop_after(monkeypatch, 5)          # once before the loop, then per frame
    with pytest.raises(Stopped):
        node.generate("dir", "lyrics", "tags", max_audio_length_ms=3000)
    assert Mula.made == 3
    assert "generate_frame" not in vars(pipe.mula)


def test_without_a_stop_the_song_is_made_whole(song):
    node, pipe, Mula = song
    result = node.generate("dir", "lyrics", "tags", max_audio_length_ms=3000)
    assert Mula.made == FRAMES
    assert result["audio"].shape[0] == 2
    assert "generate_frame" not in vars(pipe.mula)
