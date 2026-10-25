#!/usr/bin/env python3
"""
The provider table (config/llm_providers.json, read through
my_app/services/llm_providers.py) is the ONE place that says what an external
LLM provider is. Written on 2026-09-12, when that knowledge stood in nine
places -- six credential loaders, the pipeline engine's own table, the key-path
constants and the key-present check -- and two of them disagreed about where
'anthropic/' goes.

Three things are held here. That the table agrees with the register the
operator edits (hardware_matrix.defaults.json names a preset per provider, and
a provider on one side but not the other is a provider half the platform does
not know). That no other file carries a provider's address as a literal, which
is how a second table starts. And that the one reader of keys reads them the
way the six did: variable first, then the file, then nothing, with the key
shape respected where the provider has one.

Run: python3 -m pytest devserver/tests/test_llm_providers.py -q
"""
import json
import re
import sys

import pytest

from file_modules import DEVSERVER

sys.path.insert(0, str(DEVSERVER))

from my_app.services import llm_providers as lp  # noqa: E402
from my_app.services import openai_style_stream as oss  # noqa: E402

DIALECTS = {lp.CHAT_COMPLETIONS, lp.MESSAGES, lp.BEDROCK}


def test_every_entry_is_complete():
    for name, p in lp.providers().items():
        assert p.get("dialect") in DIALECTS, f"{name}: dialect"
        assert p.get("label"), f"{name}: label"
        if p.get("dialect") == lp.BEDROCK:
            assert "key_file" not in p and "env_var" not in p, f"{name}: bedrock keeps no key file"
            continue
        assert p.get("api_url", "").startswith("https://"), f"{name}: api_url"
        assert p.get("key_file", "").endswith(".key"), f"{name}: key_file"
        assert p.get("env_var", "").endswith("_API_KEY"), f"{name}: env_var"
        assert "key_prefix" in p, f"{name}: key_prefix (may be empty, must be stated)"


def test_the_optional_fields_have_the_shape_their_readers_test_for():
    """floor_for tests `is False` and the engine calls dict() on the payload:
    a string "false" is silently no floor, a string payload a ValueError on
    the first request."""
    for name, p in lp.providers().items():
        if "image_input" in p:
            assert isinstance(p["image_input"], bool), f"{name}: image_input"
        if "thinking_off_payload" in p:
            assert isinstance(p["thinking_off_payload"], dict) and p["thinking_off_payload"], \
                f"{name}: thinking_off_payload"
            # The reader writes these after the payload, so a table entry
            # cannot take them over; and a cap or a timeout has no place in
            # a table entry at all (rule 5).
            reserved = {"model", "messages", "system", "stream", "stream_options", "tools",
                        "temperature", "max_tokens", "max_completion_tokens",
                        "max_output_tokens", "timeout"}
            assert reserved.isdisjoint(p["thinking_off_payload"]), \
                f"{name}: thinking_off_payload carries a reserved field"


def test_table_and_register_name_the_same_providers():
    """A provider the operator can record a data path for is one the platform
    can reach, and the other way round."""
    shipped = json.loads((DEVSERVER / "hardware_matrix.defaults.json").read_text())
    in_register = set(shipped.get("llm_presets", {}))
    in_table = set(lp.names())
    assert in_register == in_table, (
        f"only in register: {sorted(in_register - in_table)}; "
        f"only in table: {sorted(in_table - in_register)}")


def test_dialect_tables_are_derived_from_the_one_table():
    assert tuple(oss._OPENAI_STYLE_PROVIDERS) == lp.names(lp.CHAT_COMPLETIONS)
    assert tuple(oss._ANTHROPIC_STYLE_PROVIDERS) == lp.names(lp.MESSAGES)
    assert "anthropic" not in oss._OPENAI_STYLE_PROVIDERS
    assert set(oss._OPENAI_STYLE_PROVIDERS).isdisjoint(oss._ANTHROPIC_STYLE_PROVIDERS)


def test_no_second_table_anywhere():
    """A provider's address written into a .py file is the seed of a second
    table. The one exception is the module that serves the table."""
    urls = [p[k] for p in lp.providers().values() for k in ("api_url", "credits_url", "key_url")
            if p.get(k)]
    hosts = sorted({re.match(r"https://([^/]+)", u).group(1) for u in urls})
    # Not the platform: the five runners are research scripts (2026-03 and
    # 2026-08), frozen with the runs they produced.
    exempt = {
        "scripts/stage2_model_comparison.py",
        "scripts/stage2_gemini_full_comparison.py",
        "scripts/h7_pilot_runner.py",
        "scripts/abc_form_comparison.py",
        "scripts/substance_pilot_runner.py",
    }
    offenders = []
    for py in DEVSERVER.rglob("*.py"):
        rel = py.relative_to(DEVSERVER).as_posix()
        if rel.startswith(("venv/", "tests/", "testfiles/", "archive/")) or rel in exempt:
            continue
        text = py.read_text(errors="ignore")
        for host in hosts:
            if host in text:
                offenders.append(f"{rel}: {host}")
    assert not offenders, "provider addresses outside the table:\n  " + "\n  ".join(offenders)


def test_openrouter_is_reached_on_its_eu_host():
    """The key's workspace permits requests only on eu.openrouter.ai
    (OpenRouter's refusal, 2026-09-10); the global host answers such a key
    with that sentence. All three of its addresses in the table stand on the EU host, and
    no .py under devserver spells the global one -- the ComfyUI nodes read the
    table too, so this is the one place the host is written."""
    p = lp.provider("openrouter")
    assert p["api_url"].startswith("https://eu.openrouter.ai/"), p["api_url"]
    assert p["credits_url"].startswith("https://eu.openrouter.ai/"), p["credits_url"]
    assert p["key_url"].startswith("https://eu.openrouter.ai/"), p["key_url"]
    offenders = []
    for py in DEVSERVER.rglob("*.py"):
        rel = py.relative_to(DEVSERVER).as_posix()
        if rel.startswith(("venv/", "tests/", "testfiles/", "archive/")):
            continue
        if "https://openrouter.ai/" in py.read_text(errors="ignore"):
            offenders.append(rel)
    assert not offenders, "the global OpenRouter host outside the table:\n  " + "\n  ".join(offenders)


def test_provider_of_reads_the_first_segment_only():
    assert lp.provider_of("mammouth/glm-5.3") == "mammouth"
    assert lp.provider_of("openrouter/anthropic/claude-sonnet-5") == "openrouter"
    assert lp.provider_of("anthropic/claude-sonnet-5") == "anthropic"
    assert lp.provider_of("local/qwen3.5:27b") is None
    assert lp.provider_of("qwen3.5:27b") is None
    assert lp.provider_of("") is None


def test_provider_of_takes_the_id_exactly_as_written():
    """The dispatchers cut the path off behind the provider's name. A head
    that is lower-cased or stripped first names a provider while the slice
    stands somewhere else; a bare provider name is not an id at all."""
    assert lp.provider_of("Mammouth/glm-5.3") is None
    assert lp.provider_of(" mammouth/glm-5.3") is None
    assert lp.provider_of("mammouth") is None
    assert lp.provider_of("mammouth/") == "mammouth"


def test_split_provider_hands_back_the_path_as_the_provider_publishes_it():
    assert lp.split_provider("mammouth/glm-5.3") == ("mammouth", "glm-5.3")
    assert lp.split_provider("openrouter/anthropic/claude-sonnet-5") == \
        ("openrouter", "anthropic/claude-sonnet-5")
    assert lp.split_provider("local/qwen3.5:27b") == (None, "local/qwen3.5:27b")
    assert lp.split_provider("qwen3.5:27b") == (None, "qwen3.5:27b")
    assert lp.split_provider("mammouth") == (None, "mammouth")


@pytest.fixture
def scratch_root(tmp_path, monkeypatch):
    """A devserver/ of its own for the key files, and no key in the environment."""
    monkeypatch.setattr(lp, "DEVSERVER_ROOT", tmp_path)
    for p in lp.providers().values():
        if p.get("env_var"):
            monkeypatch.delenv(p["env_var"], raising=False)
    return tmp_path


def test_credentials_prefer_the_environment(scratch_root, monkeypatch):
    (scratch_root / "mammouth.key").write_text("from-file\n")
    monkeypatch.setenv("MAMMOUTH_API_KEY", "from-env")
    assert lp.credentials("mammouth") == (lp.provider("mammouth")["api_url"], "from-env")


def test_credentials_read_the_file_past_comments(scratch_root):
    (scratch_root / "mistral.key").write_text("# my key\n\n// note\nthe-key\nsecond\n")
    assert lp.credentials("mistral")[1] == "the-key"


def test_credentials_respect_the_key_shape(scratch_root):
    """A line that does not have the provider's key shape is a note somebody
    left in the file, not a key -- the six loaders read it that way too."""
    (scratch_root / "openrouter.key").write_text("note without shape\nsk-or-real\n")
    assert lp.credentials("openrouter")[1] == "sk-or-real"
    (scratch_root / "anthropic.key").write_text("just a note\n")
    assert lp.credentials("anthropic")[1] == ""


def test_credentials_of_a_missing_file_are_empty_and_keep_the_address(scratch_root):
    url, key = lp.credentials("ionos")
    assert key == "" and url == lp.provider("ionos")["api_url"]
    assert lp.credentials("nope") == ("", "")


def test_has_key_is_presence_not_validity(scratch_root):
    assert lp.has_key("mammouth") is False
    (scratch_root / "mammouth.key").write_text("anything\n")
    assert lp.has_key("mammouth") is True
    # Anthropic's presence is Anthropic's file, never OpenRouter's -- the
    # confusion this table replaced.
    (scratch_root / "openrouter.key").write_text("sk-or-x\n")
    assert lp.has_key("openrouter") is True
    assert lp.has_key("anthropic") is False
    (scratch_root / "anthropic.key").write_text("sk-ant-x\n")
    assert lp.has_key("anthropic") is True
    # No key file at all: the credentials live elsewhere, so present.
    assert lp.has_key("bedrock") is True
    assert lp.has_key("local") is True
    assert lp.has_key("nope") is False


def test_key_in_file_is_the_file_alone(scratch_root, monkeypatch):
    """What the settings page shows masked and overwrites on save is the FILE,
    read with the platform's own reader; the environment is not a file."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-from-env")
    assert lp.key_in_file("openrouter") == ""
    (scratch_root / "openrouter.key").write_text("# note\nnot a key\nsk-or-file\n")
    assert lp.key_in_file("openrouter") == "sk-or-file"
    assert lp.key_in_file("bedrock") == ""
    assert lp.key_in_file("nope") == ""



def test_every_provider_is_a_backend_type():
    """The backend router builds BackendType(provider) from the table, so a
    provider without a member there is a ValueError on the first request."""
    from schemas.engine.backend_router import BackendType
    for name in lp.names():
        BackendType(name)


def test_no_prefix_ladder_anywhere():
    """A chain of startswith('<provider>/') is the dispatch ladder this table
    replaced: three of them sent 'anthropic/' to three different places. The
    provider is read from the id by provider_of() and the path by
    split_provider(); a new ladder is a defect."""
    pattern = re.compile(
        r"""startswith\(\s*f?["'](?:%s)/["']|\[\s*len\(\s*["'](?:%s)/["']\s*\)|["'](?:%s)/["']\s*:"""
        % ((r"|".join(map(re.escape, lp.names())),) * 3))
    # model_selector maps OpenRouter ids to local ones by a table of its own
    # (the eco mode of the legacy workflow route carried the twin until the
    # route went on 2026-10-10). That is about the one aggregator, not a
    # dispatch, and is not extended.
    exempt = {
        "schemas/engine/model_selector.py",
    }
    offenders = []
    for py in DEVSERVER.rglob("*.py"):
        rel = py.relative_to(DEVSERVER).as_posix()
        if rel.startswith(("venv/", "tests/", "testfiles/", "archive/")) or rel in exempt:
            continue
        for i, line in enumerate(py.read_text(errors="ignore").split("\n"), 1):
            if pattern.search(line):
                offenders.append(f"{rel}:{i}: {line.strip()}")
    assert not offenders, "prefix ladders outside the table:\n  " + "\n  ".join(offenders)

