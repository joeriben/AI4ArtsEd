"""A save from the settings page keeps the settings in user_settings.json that
the page does not send and config declares (settings_routes._file_after_save,
2026-10-01).

The page sends back the fields of GET's `current`. RESONA_VIEW_VLM_MODEL, a
WATERMARK block and KNOWLEDGE_QUERY_TRANSLATION_MODEL are set in the file by
hand, and every save deleted them, because the route wrote the request over
the file. Any other key still goes with the save.

Run: pytest devserver/tests/test_settings_save_keeps_the_file.py -q
"""
import json
import sys
from pathlib import Path

DEVSERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEVSERVER))

import config  # noqa: E402
from my_app.routes import settings_routes as sr  # noqa: E402

UNDECLARED = "A_SETTING_CONFIG_DOES_NOT_DECLARE"


def _a_key_variable():
    """The env-var name of one provider key, whichever the table holds."""
    for name in sr.provider_names():
        var = (sr.provider_entry(name) or {}).get("env_var")
        if var:
            return var
    raise AssertionError("the provider table names no key variable")


def test_a_key_the_page_does_not_send_stays_in_the_file():
    previous = {
        "STAGE1_TEXT_MODEL": "before",
        "RESONA_VIEW_VLM_MODEL": "qwen3-vl:8b",
        "WATERMARK": {"visible_image": True},
    }
    after = sr._file_after_save(previous, {"STAGE1_TEXT_MODEL": "after"})
    assert after == {
        "STAGE1_TEXT_MODEL": "after",
        "RESONA_VIEW_VLM_MODEL": "qwen3-vl:8b",
        "WATERMARK": {"visible_image": True},
    }


def test_what_the_save_sends_is_written_even_when_empty():
    after = sr._file_after_save({"SAFETY_MODEL": "shieldstral:3b"}, {"SAFETY_MODEL": ""})
    assert after == {"SAFETY_MODEL": ""}


def test_a_provider_key_in_an_old_file_is_not_carried_over(monkeypatch):
    """Not even one config declares as a setting. None does today, and the
    key would go anyway, so the declaration is made here: without it, this
    would only test the other filter."""
    var = _a_key_variable()
    monkeypatch.setitem(config._SETTINGS_DEFAULTS, var, "")
    after = sr._file_after_save({var: "x", "UI_MODE": "kids"}, {"UI_MODE": "youth"})
    assert after == {"UI_MODE": "youth"}


def test_the_previous_file_is_not_changed_in_place():
    previous = {"UI_MODE": "kids", "WATERMARK": {}}
    sr._file_after_save(previous, {"UI_MODE": "youth"})
    assert previous == {"UI_MODE": "kids", "WATERMARK": {}}


def test_a_file_that_could_not_be_read_leaves_the_save_alone():
    # _read_settings_file answers {} for a missing or unreadable file.
    assert sr._file_after_save({}, {"UI_MODE": "kids"}) == {"UI_MODE": "kids"}


def test_the_keys_set_by_hand_are_declared_settings():
    """The merge keeps the settings config declares, so a key set by hand
    survives a save only while _SETTINGS_DEFAULTS holds it."""
    for key in ("RESONA_VIEW_VLM_MODEL", "WATERMARK", "KNOWLEDGE_QUERY_TRANSLATION_MODEL"):
        assert key in config._SETTINGS_DEFAULTS, f"config does not declare {key}; a save would drop it"


def test_static_configuration_goes_with_the_save():
    """PORT, HOST and THREADS left the settings on 2025-12-18 for production
    safety (a3599ecb). The load still applies PORT from an old file; the save
    drops it, as it did before, instead of keeping it for good."""
    assert hasattr(config, "PORT") and "PORT" not in config._SETTINGS_DEFAULTS
    after = sr._file_after_save({"PORT": 1, "UI_MODE": "kids"}, {"UI_MODE": "youth"})
    assert after == {"UI_MODE": "youth"}


def test_a_key_the_load_passes_over_goes_with_the_save():
    """VLM_SAFETY_MODEL and DSGVO_VERIFY_MODEL left the page's source and
    config on 2026-10-01; a file that still holds one would keep it for good,
    with a warning at every load, since the page no longer sends it."""
    assert not hasattr(config, UNDECLARED)
    after = sr._file_after_save({UNDECLARED: "x", "UI_MODE": "kids"}, {"UI_MODE": "youth"})
    assert after == {"UI_MODE": "youth"}


def test_the_save_names_what_it_leaves_out(caplog):
    """A key the save drops goes by name into the log, the provider key as
    well; its value does not."""
    var = _a_key_variable()
    previous = {UNDECLARED: "x", "PORT": 1, var: "secret-value", "UI_MODE": "kids"}
    with caplog.at_level("WARNING", logger=sr.logger.name):
        sr._log_left_out(previous, sr._file_after_save(previous, {"UI_MODE": "youth"}))
    assert UNDECLARED in caplog.text and "PORT" in caplog.text and var in caplog.text
    assert "secret-value" not in caplog.text and "UI_MODE" not in caplog.text


def test_a_save_that_drops_nothing_says_nothing(caplog):
    previous = {"UI_MODE": "kids", "WATERMARK": {}}
    with caplog.at_level("WARNING", logger=sr.logger.name):
        sr._log_left_out(previous, sr._file_after_save(previous, {"UI_MODE": "youth"}))
    assert "left out" not in caplog.text


def test_the_filter_reads_only_the_old_file():
    """The page decides what it writes; what config declares narrows only
    what is carried over."""
    after = sr._file_after_save({}, {UNDECLARED: "x"})
    assert after == {UNDECLARED: "x"}


def _app(monkeypatch):
    """The settings blueprint on its own. The record of the user's own models
    is stubbed: the save would otherwise read and write the installation's
    last_user_setting.json."""
    from flask import Flask
    monkeypatch.setattr(sr, "_read_last_user_setting", lambda: {})
    monkeypatch.setattr(sr, "_write_last_user_setting", lambda record: None)
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(sr.settings_bp)
    return app


def test_the_save_route_writes_the_merge(tmp_path, monkeypatch, caplog):
    """POST /api/settings/ writes what _file_after_save returns, and then
    names in the log what it left out."""
    settings_file = tmp_path / "user_settings.json"
    settings_file.write_text(json.dumps({
        "UI_MODE": "kids",
        "WATERMARK": {"visible_image": True},
        UNDECLARED: "x",
    }))
    monkeypatch.setattr(sr, "SETTINGS_FILE", settings_file)
    with caplog.at_level("WARNING", logger=sr.logger.name):
        response = _app(monkeypatch).test_client().post("/api/settings/", json={"UI_MODE": "youth"})
    assert response.status_code == 200, response.get_json()
    assert json.loads(settings_file.read_text()) == {
        "UI_MODE": "youth",
        "WATERMARK": {"visible_image": True},
    }
    assert UNDECLARED in caplog.text


def test_a_save_that_fails_names_nothing(tmp_path, monkeypatch, caplog):
    """The log said the save had left PORT out before the write, so a save
    that failed claimed it as well."""
    blocker = tmp_path / "not_a_folder"
    blocker.write_text("")
    monkeypatch.setattr(sr, "SETTINGS_FILE", blocker / "user_settings.json")
    monkeypatch.setattr(sr, "_read_settings_file", lambda: {"PORT": 1, "UI_MODE": "kids"})
    with caplog.at_level("WARNING", logger=sr.logger.name):
        response = _app(monkeypatch).test_client().post("/api/settings/", json={"UI_MODE": "youth"})
    assert response.status_code == 500, response.get_json()
    assert "PORT" not in caplog.text
