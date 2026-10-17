"""The reach list keeps what it cannot ask (scripts/build_model_providers.py,
2026-09-12).

No machine holds every provider's key. A run that could not ask a provider
keeps that provider's entries from the last run that could, and says from
which day; before this, such a run emptied the file for every provider it
could not reach.
"""
import json
import sys

from file_modules import DEVSERVER, load_module

sys.path.insert(0, str(DEVSERVER))

bmp = load_module("build_model_providers",
                  DEVSERVER / "scripts" / "build_model_providers.py")


def _run(monkeypatch, tmp_path, register, previous, answers):
    monkeypatch.setattr(bmp, "REGISTER", tmp_path / "register.json")
    monkeypatch.setattr(bmp, "TARGET", tmp_path / "reach.json")
    monkeypatch.setattr(bmp, "PROVIDERS", list(answers))
    monkeypatch.setattr(bmp, "catalogue", lambda p: answers[p])
    bmp.REGISTER.write_text(json.dumps({"models": {n: {} for n in register}}))
    if previous is not None:
        bmp.TARGET.write_text(json.dumps(previous))
    assert bmp.main() == 0
    return json.loads(bmp.TARGET.read_text())


def test_a_provider_that_did_not_answer_keeps_its_last_reach(monkeypatch, tmp_path):
    previous = {
        "generated": "2026-09-10",
        "providers": {"mistral": {"answered": True, "catalogue_size": 50}},
        "reach": {"glm-5.3": {"mistral": "glm-5.3-at-mistral"}, "gone": {"mistral": "gone"}},
        "declared": {"kept": {"_source": "x", "mistral": "y"}},
    }
    out = _run(monkeypatch, tmp_path, ["glm-5.3", "kimi-k3"], previous, {
        "mistral": (None, "no credential on this machine"),
        "mammouth": (["glm-5.3", "kimi-k3", "other"], ""),
    })
    assert out["reach"] == {
        "glm-5.3": {"mistral": "glm-5.3-at-mistral", "mammouth": "glm-5.3"},
        "kimi-k3": {"mammouth": "kimi-k3"},
    }
    assert out["providers"]["mistral"] == {
        "answered": False, "reason": "no credential on this machine",
        "kept": 1, "kept_from": "2026-09-10",
    }
    assert out["providers"]["mammouth"] == {"answered": True, "catalogue_size": 3}
    # The hand-kept half is untouched, and a model out of the register is out.
    assert out["declared"] == previous["declared"]
    assert "gone" not in out["reach"]


def test_the_kept_date_survives_a_second_run_that_could_not_ask_either(monkeypatch, tmp_path):
    previous = {
        "generated": "2026-09-11",
        "providers": {"mistral": {"answered": False, "reason": "x", "kept": 1, "kept_from": "2026-09-10"}},
        "reach": {"glm-5.3": {"mistral": "glm-5.3"}},
    }
    out = _run(monkeypatch, tmp_path, ["glm-5.3"], previous, {
        "mistral": (None, "no credential on this machine"),
    })
    assert out["providers"]["mistral"]["kept_from"] == "2026-09-10"
    assert out["reach"] == {"glm-5.3": {"mistral": "glm-5.3"}}


def test_a_first_run_without_a_file_keeps_nothing(monkeypatch, tmp_path):
    out = _run(monkeypatch, tmp_path, ["glm-5.3"], None, {
        "mistral": (None, "no credential on this machine"),
    })
    assert out["providers"]["mistral"] == {"answered": False, "reason": "no credential on this machine"}
    assert out["reach"] == {}
