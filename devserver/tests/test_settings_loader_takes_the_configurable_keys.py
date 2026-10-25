"""The settings loader takes the runtime-configurable keys and no other.

reload_user_settings applied every key of user_settings.json that config.py
had any attribute for: the static server settings (HOST, PORT, THREADS,
CORS_ALLOWED_ORIGINS) and config's own functions among them. The set of keys
the settings page writes, config._SETTINGS_DEFAULTS, was read nowhere as the
allow-list it was laid out as (finding S-056 of the code review of 2026-10-10).
"""
import json


def test_only_the_configurable_keys_are_taken(tmp_path, monkeypatch):
    import config
    from my_app import reload_user_settings

    assert "DEFAULT_LANGUAGE" in config._SETTINGS_DEFAULTS
    monkeypatch.setattr(config, "DEFAULT_LANGUAGE", "de")
    monkeypatch.setattr(config, "PORT", 17802)
    monkeypatch.setattr(config, "THREADS", 4, raising=False)
    monkeypatch.setattr(config, "_USER_CONFIGURED_KEYS", set(), raising=False)
    settings_file = tmp_path / "user_settings.json"
    settings_file.write_text(json.dumps({
        "DEFAULT_LANGUAGE": "tr",          # configurable: taken
        "PORT": 1,                         # a server setting: dropped
        "THREADS": 99,                     # a server setting: dropped
        "resolve_knowledge_processing_model": "x",   # a function: dropped
        "NOT_A_SETTING_AT_ALL": 1,         # unknown: dropped, as before
    }), encoding="utf-8")

    reload_user_settings(settings_file=settings_file)

    assert config.DEFAULT_LANGUAGE == "tr"
    assert config.PORT == 17802
    assert config.THREADS == 4
    assert callable(config.resolve_knowledge_processing_model)
