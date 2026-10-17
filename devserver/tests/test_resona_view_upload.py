"""
Tests for view_upload (perception grant 2026-07-17): anti-spoof allowlist
binding (_brought_upload_ids via execute()'s context merge), the unconditional
reserved-key strip in ToolRegistry.execute (also closing the pre-existing
context-less _device_id hole), path safety, and scope.

The live vision call is monkeypatched — the VLM path is smoke-tested on the
dev server.

Run: python3 -m pytest devserver/tests/test_resona_view_upload.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import config
from my_app.services.tool_registry import get_tool_registry

UUID_A = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
UUID_B = "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e"


@pytest.fixture()
def registry():
    return get_tool_registry()


@pytest.fixture()
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "UPLOADS_TMP_DIR", tmp_path)
    return tmp_path


@pytest.fixture()
def vlm(monkeypatch):
    from my_app.services.llm_service import llm_service
    monkeypatch.setattr(llm_service, "describe_image_neutral",
                        lambda b64: "a red square on white ground")


def _ctx(allowed):
    return {"device_id": "dev-vu-test", "run_id": None,
            "brought_upload_ids": allowed}


def _write_png(path, size=(8, 8), color=(220, 40, 40)):
    """A real image on disk. The read path decodes and normalises before it
    sends anything, so placeholder bytes no longer stand in for a picture."""
    from PIL import Image
    Image.new("RGB", size, color).save(path, format="PNG")


# ---------------------------------------------------------------------------
# Handler guard paths
# ---------------------------------------------------------------------------

def test_missing_or_malformed_upload_id_refused(registry, uploads_dir):
    for args in ({}, {"upload_id": ""}, {"upload_id": "abc"},
                 {"upload_id": "../" + UUID_A}, {"upload_id": UUID_A + "/x"},
                 {"upload_id": UUID_A.replace("-", "")}):
        result = registry.execute("view_upload", args, context=_ctx([UUID_A]))
        assert result.startswith("Error: a valid upload_id is required"), args


def test_id_not_on_the_table_gets_calm_refusal(registry, uploads_dir):
    result = registry.execute("view_upload", {"upload_id": UUID_B},
                              context=_ctx([UUID_A]))
    # The chat loop's ledger/telemetry guards key on startswith("Error").
    assert result.startswith("Error")
    assert "not among the files the group brought" in result


def test_allowlisted_id_with_no_file_on_disk(registry, uploads_dir):
    result = registry.execute("view_upload", {"upload_id": UUID_A},
                              context=_ctx([UUID_A]))
    assert result.startswith("Error")
    assert "no longer on disk" in result


def test_allowlisted_id_is_viewed_and_normalized(registry, uploads_dir, vlm):
    _write_png(uploads_dir / f"{UUID_A}.png")
    result = registry.execute("view_upload", {"upload_id": UUID_A.upper()},
                              context=_ctx([UUID_A]))
    assert not result.startswith("Error")
    assert "Visual account" in result
    assert UUID_A in result            # lowercase — matches ledger normalization
    assert UUID_A.upper() not in result
    assert "a red square on white ground" in result


def test_vision_channel_silence_is_an_error(registry, uploads_dir, monkeypatch):
    from my_app.services.llm_service import llm_service
    monkeypatch.setattr(llm_service, "describe_image_neutral", lambda b64: None)
    _write_png(uploads_dir / f"{UUID_A}.png")
    result = registry.execute("view_upload", {"upload_id": UUID_A},
                              context=_ctx([UUID_A]))
    assert result.startswith("Error")
    assert "vision channel did not answer" in result


def test_undecodable_file_never_reaches_the_vision_model(registry, uploads_dir, monkeypatch):
    """Bytes that are not an image must fail at the read, not be shipped to the
    VLM as if they were a picture — that confusion is what silently broke every
    Canvas image reading."""
    from my_app.services.llm_service import llm_service
    seen = []
    monkeypatch.setattr(llm_service, "describe_image_neutral",
                        lambda b64: seen.append(b64) or "should not happen")
    (uploads_dir / f"{UUID_A}.png").write_bytes(b"not-really-a-png")
    result = registry.execute("view_upload", {"upload_id": UUID_A},
                              context=_ctx([UUID_A]))
    assert result.startswith("Error reading the image file")
    assert seen == []


# ---------------------------------------------------------------------------
# Reserved-key strip (the blocking finding's regression tests)
# ---------------------------------------------------------------------------

def test_model_cannot_smuggle_allowlist_without_context(registry, uploads_dir, vlm):
    # context=None: the strip removes the key BEFORE any merge would run —
    # no merge happens at all on this path.
    (uploads_dir / f"{UUID_A}.png").write_bytes(b"x")
    result = registry.execute(
        "view_upload",
        {"upload_id": UUID_A, "_brought_upload_ids": [UUID_A]},
        context=None)
    assert result.startswith("Error")
    assert "not among the files the group brought" in result


def test_model_cannot_smuggle_allowlist_past_empty_backend_list(registry, uploads_dir, vlm):
    # Strip + the backend's EMPTY allowlist wins over the model's forged one.
    (uploads_dir / f"{UUID_A}.png").write_bytes(b"x")
    result = registry.execute(
        "view_upload",
        {"upload_id": UUID_A, "_brought_upload_ids": [UUID_A]},
        context={"brought_upload_ids": []})
    assert result.startswith("Error")
    assert "not among the files the group brought" in result


def test_context_less_recall_no_longer_sees_spoofed_device_id(registry):
    # Pre-existing hole closed by the unconditional strip: with context=None a
    # model-supplied _device_id used to pass straight through to the handler.
    result = registry.execute(
        "recall", {"query": "anything", "_device_id": "device_spoofed_ctxless"},
        context=None)
    assert "no device context" in result


# ---------------------------------------------------------------------------
# Scope (NON-INHERITING)
# ---------------------------------------------------------------------------

def test_view_upload_scope_is_resona_only(registry):
    resona = {t["function"]["name"] for t in registry.get_openai_format(scope="resona")}
    universal = {t["function"]["name"] for t in registry.get_openai_format(scope=None)}
    assert "view_upload" in resona
    assert "view_upload" not in universal
