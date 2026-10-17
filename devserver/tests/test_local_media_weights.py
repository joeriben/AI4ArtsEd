#!/usr/bin/env python3
"""The table of the media stations' weights carries what its readers read.

Stage 6 of the move to ComfyUI: config/local_media_weights.json
is the one place that names a media model (its repository, its folder under
<ComfyUI>/models/<station>/, the files a whole copy holds, what the readers
of the media-reading station are and what they are told, and the Stable
Audio tier policy). services/local_media_weights reads it for the DevServer;
the node package reads the folders. Held here: every entry carries the fields
its kind needs, the readers and the tier policy name entries the table holds,
a folder is whole by the entry's own list and never with an '.incomplete'
part among the model's files, and the listing has the settings page's shape.

The twin of test_local_llm_weights.py for the language models.

Run: pytest devserver/tests/test_local_media_weights.py -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from my_app.services import local_llm_weights
from my_app.services import local_media_weights as w
from media_layouts import LAYOUTS, files_of, write_file, write_whole

KINDS = {"snapshot": ("repo",), "parts": ("parts",), "files": ("repo", "files"), "url": ("url", "file")}


def test_every_entry_carries_what_the_readers_read():
    stations = w.stations()
    assert stations, "the table names its stations"
    for name, s in stations.items():
        assert s["folder"] and s["display_name"] and s["library"], name
    for alias, e in w.models().items():
        assert e["station"] in stations, f"{alias}: station {e['station']!r} is not in the table"
        assert e["kind"] in KINDS, f"{alias}: kind {e['kind']!r}"
        for field in KINDS[e["kind"]]:
            assert e.get(field), f"{alias}: a {e['kind']} entry needs {field!r}"
        assert e["dir"] and "/" not in e["dir"], f"{alias}: the folder is one name under the station"
        assert float(e["size_gb"]) > 0, alias
        assert all(isinstance(r, str) and r.strip() for r in e.get("cached", [])), \
            f"{alias}: cached repositories are repository ids (a canonical one has no namespace)"
        assert e.get("display_name"), alias


def test_no_two_entries_of_a_station_share_a_folder():
    for station in w.stations():
        dirs = [w.entry(a)["dir"] for a in w.aliases_of_station(station)]
        assert len(dirs) == len(set(dirs)), station
        for alias in w.aliases_of_station(station):
            assert w.alias_of_dir(station, w.entry(alias)["dir"]) == alias
    assert w.alias_of_dir(next(iter(w.stations())), "nothing-at-all") is None


def test_no_two_entries_of_the_table_share_a_folder():
    """alias_of_folder answers without a station, so a folder has to name
    one model across the whole table."""
    dirs = [e["dir"] for e in w.models().values()]
    assert len(dirs) == len(set(dirs))
    for alias, e in w.models().items():
        assert w.alias_of_folder(e["dir"]) == alias
    assert w.alias_of_folder("nothing-at-all") is None


def test_the_bar_names_a_media_run_by_the_models_alias():
    """The dispatch the ComfyUI client announces for the bar is read off
    the workflow (comfyui_ws_client._checkpoint_of), and a node of the
    platform's package is handed the weights FOLDER under model_name; the
    bar shows the alias the route announced, not the folder. A folder the
    table does not know, and a model_name of a node outside the package,
    stay what they are."""
    from my_app.services.comfyui_ws_client import _checkpoint_of
    for alias, e in w.models().items():
        workflow = {"1": {"class_type": f"ai4artsed_{e['station']}",
                          "inputs": {"model_name": e["dir"], "prompt": "x"}}}
        assert _checkpoint_of(workflow) == alias
    assert _checkpoint_of({"1": {"class_type": "ai4artsed_audio_synth",
                                 "inputs": {"model_name": "copied-in-by-hand"}}}) == "copied-in-by-hand"
    some = next(iter(w.models().values()))["dir"]
    assert _checkpoint_of({"1": {"class_type": "UpscaleModelLoader",
                                 "inputs": {"model_name": some}}}) == some


def test_a_reader_handed_a_language_model_is_keyed_as_that_model():
    """ai4artsed_media_reading lists the readers and the language models in
    one model_name list (image and video are read by a language model). Keyed
    off the folder alone, the same model had two keys in the gate: the raw
    folder here, `local/<alias>` when ai4artsed_local_llm loaded it. The
    language-model table is asked first, the media table second."""
    from my_app.services import local_llm_weights as llm
    from my_app.services.comfyui_ws_client import _checkpoint_of
    alias, e = next(iter(llm.models().items()))
    assert _checkpoint_of({"1": {"class_type": "ai4artsed_media_reading",
                                 "inputs": {"task": "image", "model_name": e["dir"]}}}
                          ) == f"{llm.LOCAL_PREFIX}{alias}"
    reader_alias, reader = next(iter(w.models().items()))
    assert _checkpoint_of({"1": {"class_type": "ai4artsed_media_reading",
                                 "inputs": {"task": "audio", "model_name": reader["dir"]}}}
                          ) == reader_alias


def test_the_readers_and_their_prompts_are_in_the_table():
    readers = w.reading()["readers"]
    assert {"audio", "video", "image", "lyrics", "music_tags"} <= set(readers)
    for task in readers:
        alias, folder = w.reader_dir(task)
        assert alias == readers[task] and folder
        if alias.startswith(local_llm_weights.LOCAL_PREFIX):
            assert local_llm_weights.entry(alias) is not None, f"{task}: {alias} is in neither table"
        else:
            assert w.entry(alias) is not None, f"{task}: {alias} is not in the table"
            assert w.entry(alias)["station"] == "media_reading", task
    with pytest.raises(KeyError):
        w.reader_alias("smell")
    for kind in ("audio_system", "audio", "video", "image"):
        assert w.prompt(kind).strip()
    assert w.music_tag_vocabulary()
    assert isinstance(w.reader_trusts_remote_code("audio"), bool)


def test_the_stable_audio_tiers_name_entries_of_the_stable_audio_station():
    policy = w.stable_audio_policy()
    assert float(policy["medium_min_vram_gb"]) > 0
    for alias in (policy["medium"], policy["small"]["music"], policy["small"]["sfx"]):
        assert w.entry(alias) is not None and w.entry(alias)["station"] == "stable_audio", alias


def test_the_wholeness_test_is_the_node_packages_own():
    assert w.WHOLE_CHECK.is_file()
    assert w.WHOLE_CHECK.parent == local_llm_weights.SNAPSHOT_CHECK.parent
    assert set(w._whole().CHECKS) == set(w.stations()), "one check per station of the table"
    with pytest.raises(KeyError, match="no media station 'nothing'"):
        w.folder_missing("nothing", "/nowhere")


@pytest.mark.parametrize("station", sorted(LAYOUTS))
def test_a_folder_is_whole_with_every_file_the_station_reads(tmp_path, station):
    folder = tmp_path / "m"
    assert w.folder_missing(station, folder) == "the folder is absent"
    folder.mkdir()
    for left_out in files_of(station):
        write_whole(station, folder)
        (folder / left_out).unlink()
        why = w.folder_missing(station, folder)
        named = Path(left_out).name in (why or "") or Path(left_out).parent.name in (why or "")
        assert why is not None and named, f"{station} without {left_out}: {why!r}"
    write_whole(station, folder)
    assert w.folder_missing(station, folder) is None and w.folder_is_whole(station, folder)


# The stations whose folder holds one model: read whole, a part anywhere
# under it counts, the hub's own staging folder .cache/ included, as
# services/local_llm_weights holds for the language models. The other three
# are roots with sibling models beside the ones read (heartlib's checkpoint
# root, the Hunyuan3D snapshot with its variants) and are held to what they
# read.
READ_WHOLE = {"imagebind", "mmaudio", "media_reading"}
A_SIBLING = {"stable_audio": "t5gemma-other", "heartmula": "HeartMuLa-RL-oss-3B-20260123",
             "hunyuan3d": "hunyuan3d-dit-v2-0-turbo"}


@pytest.mark.parametrize("station", sorted(LAYOUTS))
def test_a_part_in_flight_under_what_is_read_is_not_whole(tmp_path, station):
    folder = tmp_path / "m"
    write_whole(station, folder)
    part = folder / files_of(station)[-1].rsplit("/", 1)[0] / "x.safetensors.incomplete" \
        if "/" in files_of(station)[-1] else folder / "x.safetensors.incomplete"
    part.write_bytes(b"\0")
    why = w.folder_missing(station, folder)
    assert why is not None and "in flight" in why and "x.safetensors.incomplete" in why, why
    part.unlink()
    (folder / "y.pth.incomplete").write_bytes(b"\0")
    assert "y.pth.incomplete" in (w.folder_missing(station, folder) or ""), "a part among the root's own files"
    (folder / "y.pth.incomplete").unlink()
    assert w.folder_is_whole(station, folder)
    staged = folder / ".cache" / "huggingface" / "download"
    staged.mkdir(parents=True)
    (staged / "x.incomplete").write_bytes(b"\0")
    if station in READ_WHOLE:
        assert not w.folder_is_whole(station, folder), "a part under the hub's own staging"
    else:
        assert w.folder_is_whole(station, folder), "the root's dot-folder is nobody's model"
        sibling = folder / A_SIBLING[station] / ".cache" / "huggingface" / "download"
        sibling.mkdir(parents=True)
        (sibling / "z.incomplete").write_bytes(b"\0")
        assert w.folder_is_whole(station, folder), "a download broken off in a sibling folder"


def test_the_readers_accept_the_bin_weights_they_are_published_with(tmp_path):
    folder = tmp_path / "m"
    write_file(folder, "config.json", {})
    assert w.folder_missing("media_reading", folder) == "no weights file (.safetensors or .bin) is there"
    write_file(folder, "pytorch_model.bin")
    assert w.folder_is_whole("media_reading", folder)
    write_file(folder, "model.safetensors.index.json", {"weight_map": {"a": "model-00001-of-00002.safetensors"}})
    assert w.folder_missing("media_reading", folder) == "model-00001-of-00002.safetensors is missing", \
        "an index names the shards, and a .bin beside it is not them"


def test_heartmula_offers_the_whole_versions_only(tmp_path):
    folder = tmp_path / "m"
    write_whole("heartmula", folder)
    write_file(folder, "HeartMuLa-oss-7B/config.json", {})
    write_file(folder, "HeartMuLa-oss-7B/model.safetensors.index.json",
               {"weight_map": {"a": "model-00001-of-00003.safetensors"}})
    assert w._whole().heartmula_versions(str(folder)) == ["3B"], "a version without its shards is not offered"
    assert w.folder_is_whole("heartmula", folder), "and it does not stand in the way of the whole one"
    (folder / "HeartMuLa-oss-3B" / "model.safetensors").unlink()
    assert w.folder_missing("heartmula", folder) == "HeartMuLa-oss-3B: no weights file (.safetensors) is there"


def test_installed_means_a_whole_folder_under_the_station(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "models_root", lambda: tmp_path)
    alias = next(iter(w.models()))
    e = w.entry(alias)
    assert w.weights_dir(alias) == tmp_path / w.stations()[e["station"]]["folder"] / e["dir"]
    assert w.is_installed(alias) is False and w.installed_aliases() == []
    write_whole(e["station"], w.weights_dir(alias))
    assert w.is_installed(alias) is True and w.installed_aliases() == [alias]
    assert w.is_installed("nothing-at-all") is False
    assert w.weights_dir("nothing-at-all") is None and w.dir_name("nothing-at-all") is None


def test_the_listing_has_the_settings_pages_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "models_root", lambda: tmp_path)
    rows = w.listing()
    assert [r["id"] for r in rows] == list(w.models())
    for r in rows:
        e = w.entry(r["id"])
        assert set(r) == {"id", "display_name", "available", "installable", "approx_download_mb",
                          "backend", "station", "gated", "repo"}
        assert r["backend"] == r["station"] == e["station"]
        assert r["available"] is False and r["installable"] is True
        assert r["approx_download_mb"] == int(round(float(e["size_gb"]) * 1024))
        assert r["gated"] is bool(e.get("gated"))
