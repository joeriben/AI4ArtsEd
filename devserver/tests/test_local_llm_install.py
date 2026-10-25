#!/usr/bin/env python3
"""The installer of local language models writes whole snapshots, or none.

Stage 3 of the move to ComfyUI: services/local_llm_install
downloads a repository of config/local_llm_weights.json into a staging folder
under <ComfyUI>/models/llm/ and renames it into place once it is whole. What
this file holds it to, with the download itself stood in for: the events the
surface reads (start/progress/done/error), a snapshot that is not whole stays
in staging and the destination stays absent, a destination that exists and is
not whole is refused by name and never deleted, one install at a time, and
the install runs to its end when the reader of its events has left.

Run: pytest devserver/tests/test_local_llm_install.py -q
"""

import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.services import local_llm_install as inst
from my_app.services import local_llm_weights as w

ALIAS = min((a for a, e in w.models().items() if not e.get("gated")),
            key=lambda a: w.entry(a)["size_gb"])
ENTRY = w.entry(ALIAS)


@pytest.fixture()
def root(tmp_path, monkeypatch):
    r = tmp_path / "models" / "llm"
    monkeypatch.setattr(w, "models_root", lambda: r)
    # The disk under tmp_path is whatever the host has; the precheck's
    # arithmetic is its own test below, and here it is given room.
    monkeypatch.setattr(inst, "_free_bytes_under", lambda path: 10**15)
    return r


def _whole_snapshot(folder):
    os.makedirs(folder, exist_ok=True)
    Path(folder, "config.json").write_text(json.dumps({"model_type": "stand-in"}))
    Path(folder, "model.safetensors").write_bytes(b"\0" * 64)


def _cut_off_snapshot(folder):
    os.makedirs(folder, exist_ok=True)
    Path(folder, "config.json").write_text(json.dumps({"model_type": "stand-in"}))
    Path(folder, "model.safetensors.incomplete").write_bytes(b"\0" * 8)


def _fetching(writer, gate=None):
    def fetch(e, staging):
        if gate is not None:
            assert gate.wait(10.0)
        writer(staging)
    return staticmethod(fetch)


def test_a_whole_download_is_renamed_into_place(root, monkeypatch):
    monkeypatch.setattr(inst.LocalLLMInstaller, "_fetch", _fetching(_whole_snapshot))
    installer = inst.LocalLLMInstaller()
    events = list(installer.install(ALIAS))
    assert events[0] == {"type": "start", "alias": ALIAS, "file": ENTRY["dir"],
                         "total_mb": int(round(ENTRY["size_gb"] * 1024))}
    assert events[-1]["type"] == "done" and events[-1]["alias"] == ALIAS
    assert all(ev["type"] in ("start", "progress", "done") for ev in events)
    assert w.is_installed(ALIAS)
    assert not (root / f".incoming-{ENTRY['dir']}").exists()
    assert not installer.is_busy()


def test_a_download_that_is_not_whole_stays_in_staging(root, monkeypatch):
    monkeypatch.setattr(inst.LocalLLMInstaller, "_fetch", _fetching(_cut_off_snapshot))
    installer = inst.LocalLLMInstaller()
    events = list(installer.install(ALIAS))
    assert events[-1]["type"] == "error" and "not whole" in events[-1]["message"]
    assert (root / f".incoming-{ENTRY['dir']}").is_dir(), "the staging folder is what the next install takes up"
    assert not (root / ENTRY["dir"]).exists()
    assert not w.is_installed(ALIAS)
    assert not installer.is_busy()


def test_a_destination_that_exists_and_is_not_whole_is_refused_by_name(root, monkeypatch):
    fetched = []
    monkeypatch.setattr(inst.LocalLLMInstaller, "_fetch",
                        _fetching(lambda staging: fetched.append(staging)))
    final = root / ENTRY["dir"]
    final.mkdir(parents=True)
    Path(final, "config.json").write_text("{}")
    installer = inst.LocalLLMInstaller()
    check = installer.precheck(ALIAS)
    assert check["ok"] is False and str(final) in check["reason"] and "no whole snapshot" in check["reason"]
    events = list(installer.install(ALIAS))
    assert events == [{"type": "error", "alias": ALIAS, "message": check["reason"]}]
    assert fetched == []
    assert Path(final, "config.json").exists(), "nothing here deletes a folder it did not write"


def test_one_install_at_a_time_and_the_lock_goes_with_the_download(root, monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(inst.LocalLLMInstaller, "_fetch", _fetching(_whole_snapshot, gate))
    installer = inst.LocalLLMInstaller()
    first = installer.install(ALIAS)
    assert next(first)["type"] == "start"
    assert installer.is_busy() and installer.active_alias() == ALIAS
    second = list(installer.install(ALIAS))
    assert second[0]["type"] == "error" and "already running" in second[0]["message"]
    assert installer.precheck(ALIAS)["ok"] is False
    # The reader of the first install leaves; the download runs to its end.
    first.close()
    assert installer.is_busy()
    gate.set()
    deadline = time.time() + 10
    while installer.is_busy() and time.time() < deadline:
        time.sleep(0.02)
    assert not installer.is_busy()
    assert w.is_installed(ALIAS)


def test_the_precheck_creates_nothing_and_credits_finished_files_only(root, monkeypatch):
    installer = inst.LocalLLMInstaller()
    check = installer.precheck(ALIAS)
    assert check["ok"] is True, check
    assert not root.exists(), "a precheck is a question, not a side effect"
    staging = root / f".incoming-{ENTRY['dir']}"
    _cut_off_snapshot(staging)
    assert inst._bytes_on_disk(str(staging), in_flight=False) == len(json.dumps({"model_type": "stand-in"}))
    assert inst._bytes_on_disk(str(staging)) > inst._bytes_on_disk(str(staging), in_flight=False)


def test_an_unknown_alias_is_refused():
    installer = inst.LocalLLMInstaller()
    assert installer.precheck("nothing:1b")["ok"] is False
    assert list(installer.install("nothing:1b"))[0]["type"] == "error"
