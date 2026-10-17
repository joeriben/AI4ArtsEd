#!/usr/bin/env python3
"""The installer of the media stations' weights writes whole folders, or none.

Stage 6 of the move to ComfyUI: services/local_media_install
downloads an entry of config/local_media_weights.json into a staging folder
under <ComfyUI>/models/<station>/ and renames it into place once it is whole
(the node package's own test, comfyui_nodes/ai4artsed_comfyui/_whole.py). What this
file holds it to, with the download itself stood in for: the events the
surface reads (start/progress/done/error), a folder that is not whole stays
in staging and the destination stays absent, a destination that exists and is
not whole is refused by name and never deleted, one install at a time, the
install runs to its end when the reader of its events has left, a gated
repository needs a token, the repositories an entry lists as `cached` are
fetched after the wholeness test and before the rename, and the command line
takes an alias, a station or nothing.

The twin of test_local_llm_install.py for the language models.

Run: pytest devserver/tests/test_local_media_install.py -q
"""

import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.services import local_media_install as inst
from my_app.services import local_media_weights as w
from media_layouts import LAYOUTS, files_of, write_file, write_whole

ALIAS = min((a for a, e in w.models().items() if not e.get("gated") and not e.get("cached")),
            key=lambda a: w.entry(a)["size_gb"])
ENTRY = w.entry(ALIAS)


@pytest.fixture()
def root(tmp_path, monkeypatch):
    r = tmp_path / "models"
    monkeypatch.setattr(w, "models_root", lambda: r)
    # The disk under tmp_path is whatever the host has; the precheck's
    # arithmetic is its own test below, and here it is given room. The
    # cached repositories go to the HF cache of the machine: stood in for.
    monkeypatch.setattr(inst, "_free_bytes_under", lambda path: 10**15)
    monkeypatch.setattr(inst.LocalMediaInstaller, "_fetch_cached", staticmethod(lambda e, state: None))
    return r / w.stations()[ENTRY["station"]]["folder"]


FILES = files_of(ENTRY["station"])


def _whole_folder(folder, station=ENTRY["station"]):
    write_whole(station, folder)


def _cut_off_folder(folder):
    write_whole(ENTRY["station"], folder, leave_out=[FILES[-1]])
    write_file(folder, FILES[-1] + ".incomplete", size=8)


def _fetching(writer, gate=None):
    def fetch(e, staging):
        if gate is not None:
            assert gate.wait(10.0)
        writer(staging)
    return staticmethod(fetch)


def test_a_whole_download_is_renamed_into_place(root, monkeypatch):
    monkeypatch.setattr(inst.LocalMediaInstaller, "_fetch", _fetching(_whole_folder))
    installer = inst.LocalMediaInstaller()
    events = list(installer.install(ALIAS))
    assert events[0] == {"type": "start", "alias": ALIAS, "file": ENTRY["dir"],
                         "total_mb": int(round(ENTRY["size_gb"] * 1024))}
    assert events[-1]["type"] == "done" and events[-1]["alias"] == ALIAS
    assert all(ev["type"] in ("start", "progress", "done") for ev in events)
    assert w.is_installed(ALIAS)
    assert not (root / f".incoming-{ENTRY['dir']}").exists()
    assert not installer.is_busy()


def test_a_download_that_is_not_whole_stays_in_staging(root, monkeypatch):
    monkeypatch.setattr(inst.LocalMediaInstaller, "_fetch", _fetching(_cut_off_folder))
    installer = inst.LocalMediaInstaller()
    events = list(installer.install(ALIAS))
    assert events[-1]["type"] == "error" and "not whole" in events[-1]["message"]
    assert FILES[-1] + ".incomplete" in events[-1]["message"], "the message names what the folder lacks"
    assert (root / f".incoming-{ENTRY['dir']}").is_dir(), "the staging folder is what the next install takes up"
    assert not (root / ENTRY["dir"]).exists()
    assert not w.is_installed(ALIAS)
    assert not installer.is_busy()


def test_a_destination_that_exists_and_is_not_whole_is_refused_by_name(root, monkeypatch):
    fetched = []
    monkeypatch.setattr(inst.LocalMediaInstaller, "_fetch",
                        _fetching(lambda staging: fetched.append(staging)))
    final = root / ENTRY["dir"]
    final.mkdir(parents=True)
    write_file(final, FILES[0], dict(LAYOUTS[ENTRY["station"]])[FILES[0]])
    installer = inst.LocalMediaInstaller()
    check = installer.precheck(ALIAS)
    assert check["ok"] is False and str(final) in check["reason"] and "no whole copy" in check["reason"]
    assert w.folder_missing(ENTRY["station"], final) in check["reason"], "the reason says what it lacks"
    events = list(installer.install(ALIAS))
    assert events == [{"type": "error", "alias": ALIAS, "message": check["reason"]}]
    assert fetched == []
    assert Path(final, FILES[0]).exists(), "nothing here deletes a folder it did not write"


def test_one_install_at_a_time_and_the_lock_goes_with_the_download(root, monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(inst.LocalMediaInstaller, "_fetch", _fetching(_whole_folder, gate))
    installer = inst.LocalMediaInstaller()
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
    installer = inst.LocalMediaInstaller()
    check = installer.precheck(ALIAS)
    assert check["ok"] is True, check
    assert not root.exists(), "a precheck is a question, not a side effect"
    staging = root / f".incoming-{ENTRY['dir']}"
    _cut_off_folder(staging)
    finished = sum(Path(staging, rel).stat().st_size for rel in FILES[:-1])
    assert inst._bytes_on_disk(str(staging), in_flight=False) == finished
    assert inst._bytes_on_disk(str(staging)) == finished + 8


def test_an_unknown_alias_is_refused():
    installer = inst.LocalMediaInstaller()
    assert installer.precheck("nothing-at-all")["ok"] is False
    assert list(installer.install("nothing-at-all"))[0]["type"] == "error"


def test_a_gated_repository_needs_a_token(root, monkeypatch):
    gated = [a for a, e in w.models().items() if e.get("gated")]
    if not gated:
        pytest.skip("the table holds no gated repository")
    import huggingface_hub
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)
    installer = inst.LocalMediaInstaller()
    check = installer.precheck(gated[0])
    assert check["ok"] is False and "gated" in check["reason"] and "HF_TOKEN" in check["reason"]
    assert w.entry(gated[0])["repo"] in check["reason"]
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: "a-token")
    assert installer.precheck(gated[0])["ok"] is True


def test_the_cached_repositories_come_after_the_wholeness_test_and_before_the_rename(root, monkeypatch):
    with_cache = [a for a, e in w.models().items() if e.get("cached") and not e.get("gated")]
    if not with_cache:
        pytest.skip("the table holds no entry with cached repositories")
    alias = with_cache[0]
    e = w.entry(alias)
    station = root.parent / w.stations()[e["station"]]["folder"]
    seen = {}

    def fetch(entry, staging):
        _whole_folder(staging, entry["station"])

    def fetch_cached(entry, state):
        seen["staging_there"] = os.path.isdir(station / f".incoming-{e['dir']}")
        seen["final_there"] = os.path.isdir(station / e["dir"])
        seen["repos"] = list(entry["cached"])

    monkeypatch.setattr(inst.LocalMediaInstaller, "_fetch", staticmethod(fetch))
    monkeypatch.setattr(inst.LocalMediaInstaller, "_fetch_cached", staticmethod(fetch_cached))
    events = list(inst.LocalMediaInstaller().install(alias))
    assert events[-1]["type"] == "done", events[-1]
    assert seen == {"staging_there": True, "final_there": False, "repos": list(e["cached"])}
    assert w.is_installed(alias)


def test_the_command_line_takes_an_alias_a_station_or_nothing():
    assert inst._aliases_of([]) == list(w.models())
    station = ENTRY["station"]
    assert inst._aliases_of([station]) == w.aliases_of_station(station)
    assert inst._aliases_of([ALIAS]) == [ALIAS]
    # An unknown word is kept, so that the run reports it as unknown.
    assert inst._aliases_of(["nothing-at-all"]) == ["nothing-at-all"]


def test_the_cache_leaves_out_what_the_platform_never_loads():
    # The formats huggingface_hub would fetch alongside the safetensors of a
    # cached repository and no loader here reads: left out, so a cached
    # repository costs its weights once. '*.bin' is not among them: two
    # repositories of the table ship their weights in that form alone.
    assert "*.bin" not in inst._CACHE_IGNORE
    assert {"*.msgpack", "*.h5", "*.onnx", "*.ckpt"} <= set(inst._CACHE_IGNORE)


# ---------------------------------------------------------------------------
# _fetch_url, with the server stood in for.

class _Reply:
    def __init__(self, status, body=b"", headers=None):
        self.status_code = status
        self.headers = headers or {}
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"{self.status_code}")

    def iter_content(self, chunk_size):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]


def _serving(reply, seen):
    def get(url, headers=None, stream=False, timeout=None):
        seen.append(headers or {})
        return reply
    return get


def test_a_url_download_is_a_part_until_the_body_ended_where_the_server_said(tmp_path, monkeypatch):
    import requests
    target = tmp_path / "w.pth"
    seen = []
    monkeypatch.setattr(requests, "get", _serving(_Reply(200, b"x" * 10, {"Content-Length": "12"}), seen))
    with pytest.raises(RuntimeError, match="ended after 10 of 12 bytes; the part is kept"):
        inst._fetch_url("http://h/w.pth", str(target))
    assert (tmp_path / "w.pth.incomplete").read_bytes() == b"x" * 10 and not target.exists()
    monkeypatch.setattr(requests, "get", _serving(_Reply(206, b"yy", {"Content-Length": "2"}), seen))
    inst._fetch_url("http://h/w.pth", str(target))
    assert seen[-1] == {"Range": "bytes=10-"}, "the part is continued from its end"
    assert target.read_bytes() == b"x" * 10 + b"yy" and not (tmp_path / "w.pth.incomplete").exists()


def test_a_416_is_read_by_its_content_range(tmp_path, monkeypatch):
    import requests
    target = tmp_path / "w.pth"
    (tmp_path / "w.pth.incomplete").write_bytes(b"x" * 12)
    seen = []
    monkeypatch.setattr(requests, "get", _serving(_Reply(416, headers={"Content-Range": "bytes */12"}), seen))
    inst._fetch_url("http://h/w.pth", str(target))
    assert target.read_bytes() == b"x" * 12, "the part reached the file's end"
    (tmp_path / "v.pth.incomplete").write_bytes(b"x" * 20)
    monkeypatch.setattr(requests, "get", _serving(_Reply(416, headers={"Content-Range": "bytes */12"}), seen))
    with pytest.raises(RuntimeError, match="held 20 bytes and the file has 12"):
        inst._fetch_url("http://h/v.pth", str(tmp_path / "v.pth"))
    assert not (tmp_path / "v.pth.incomplete").exists(), "a part longer than the file is taken away"
    assert not (tmp_path / "v.pth").exists()


def test_a_body_smaller_than_the_file_weighs_is_not_the_file(tmp_path, monkeypatch):
    import requests
    target = tmp_path / "w.pth"
    monkeypatch.setattr(requests, "get", _serving(_Reply(200, b"<html>no</html>", {"Content-Length": "15"}), []))
    with pytest.raises(RuntimeError, match="ended after 15 bytes where the file weighs at least 1000"):
        inst._fetch_url("http://h/w.pth", str(target), at_least=1000)
    assert not (tmp_path / "w.pth.incomplete").exists() and not target.exists()
