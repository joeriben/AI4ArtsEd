"""
The card is asked once, of ComfyUI, and an unreadable card is said so.

Three places used to ask the GPU service how big the card is, each with its own
request and its own direction of failure: the Latent Lab model resolver quietly
chose the smaller model, the capability gate closed, the hardware route answered
an empty dict. The migration moves the question to ComfyUI, and a question asked
in three places moves in three places — so it is asked in one.
"""

import ast
import asyncio
import io
import time

import pytest

from my_app.services import gpu_card
from my_app.services.gpu_card import CardUnreadable

from file_modules import REPO

SERVICES = REPO / "devserver" / "my_app" / "services"


@pytest.fixture(autouse=True)
def _clean():
    gpu_card.reset_cache()
    yield
    gpu_card.reset_cache()


def _answer(payload, status=200, text=""):
    """A stand-in for the aiohttp session gpu_card opens."""
    class _Response:
        def __init__(self):
            self.status = status
        async def json(self):
            if payload is None:
                raise ValueError("no json")
            return payload
        async def text(self):
            return text
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False

    class _Session:
        def get(self, *a, **k):
            return _Response()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False

    return _Session


def _with_session(monkeypatch, session_cls):
    import aiohttp
    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: session_cls())


# ------------------------------------------------------------------ the reading


def test_the_card_is_read_from_comfyuis_own_report(monkeypatch):
    _with_session(monkeypatch, _answer({"devices": [{"vram_total": 101971591168}]}))
    assert asyncio.run(gpu_card.total_vram_gb()) == pytest.approx(94.97, abs=0.01)


def test_the_unit_is_gib_because_every_threshold_is_set_against_it(monkeypatch):
    """24 GiB is the 4090, 32 the 5090, 96 the RTX PRO 6000. Decimal GB would
    read the 4090 as 25.8 and move every threshold the platform has."""
    _with_session(monkeypatch, _answer({"devices": [{"vram_total": 24 * 1024 ** 3}]}))
    assert asyncio.run(gpu_card.total_vram_gb()) == pytest.approx(24.0)


def test_a_reading_that_succeeded_is_kept(monkeypatch):
    calls = []

    class _Counting:
        def get(self, *a, **k):
            calls.append(1)
            return _answer({"devices": [{"vram_total": 8 * 1024 ** 3}]})().get()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False

    _with_session(monkeypatch, _Counting)
    asyncio.run(gpu_card.total_vram_gb())
    asyncio.run(gpu_card.total_vram_gb())
    assert len(calls) == 1


# ------------------------------------------------- what happens when it cannot


@pytest.mark.parametrize("payload,status,text", [
    (None, 200, "<html>502 Bad Gateway</html>"),   # no JSON at all
    ({}, 200, ""),                                  # no devices key
    ({"devices": []}, 200, ""),                     # no device
    ({"devices": [{}]}, 200, ""),                   # device without vram_total
    ({"devices": [{"vram_total": 0}]}, 200, ""),    # a zero is no reading
    ({"devices": [{"vram_total": "lots"}]}, 200, ""),
    (None, 503, "ComfyUI is starting"),
])
def test_an_answer_that_says_nothing_is_no_number(monkeypatch, payload, status, text):
    _with_session(monkeypatch, _answer(payload, status=status, text=text))
    with pytest.raises(CardUnreadable):
        asyncio.run(gpu_card.total_vram_gb())


def test_a_failed_reading_is_held_briefly_and_then_asked_again(monkeypatch):
    _with_session(monkeypatch, _answer({"devices": []}))
    with pytest.raises(CardUnreadable):
        asyncio.run(gpu_card.total_vram_gb())
    with pytest.raises(CardUnreadable):
        asyncio.run(gpu_card.total_vram_gb())          # held, no second request
    gpu_card._failed_until = time.monotonic() - 1       # the minute has passed
    _with_session(monkeypatch, _answer({"devices": [{"vram_total": 2 * 1024 ** 3}]}))
    assert asyncio.run(gpu_card.total_vram_gb()) == pytest.approx(2.0)


# ------------------------------------------- no model is chosen behind our back


def test_the_latent_lab_model_is_large_on_a_32_gb_card(monkeypatch):
    """
    SD 3.5 Large has to fit in 32 GB. Before this rule a card
    under 50 GB was answered SD3.5-Medium, 24 MMDiT blocks against 38, and the
    instrument quietly made a different thing than the surface names.
    """
    from my_app.services import latent_lab_model
    monkeypatch.delenv("AI4ARTSED_LATENT_LAB_MODEL", raising=False)
    _with_session(monkeypatch, _answer({"devices": [{"vram_total": 32 * 1024 ** 3}]}))
    assert asyncio.run(latent_lab_model.get_latent_lab_model_id()) == \
        latent_lab_model.LATENT_LAB_LARGE


def test_the_latent_lab_model_is_decided_without_reading_the_card(monkeypatch):
    """No reading, so no unreadable card and no override can change it."""
    from my_app.services import latent_lab_model

    class _NeverAsked:
        def get(self, *a, **k):
            raise AssertionError("the Latent Lab model is decided without reading the card")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    monkeypatch.setenv("AI4ARTSED_LATENT_LAB_MODEL", "medium")
    _with_session(monkeypatch, _NeverAsked)
    assert asyncio.run(latent_lab_model.get_latent_lab_model_id()) == \
        latent_lab_model.LATENT_LAB_LARGE


def test_the_capability_gate_still_closes_on_an_unreadable_card(monkeypatch):
    """The other direction of the same reading, and it stays fail-closed."""
    from my_app.services import latent_lab_capabilities as caps_mod
    caps_mod.reset_cache()
    monkeypatch.delenv("AI4ARTSED_FORCE_HEAVY_LATENT_LAB", raising=False)
    _with_session(monkeypatch, _answer({"devices": []}))
    caps = asyncio.run(caps_mod.get_latent_lab_capabilities())
    assert caps["attention_cartography"] is False
    assert caps["feature_probing"] is False
    assert caps["total_vram_gb"] is None
    caps_mod.reset_cache()


# ------------------------------------------------------- one asker, not several


def test_the_latent_lab_services_no_longer_ask_the_gpu_service():
    """
    The point of the move: the DevServer stops reaching for the card through
    the GPU service. A second asker would move separately, or stay behind.
    """
    offenders = []
    for name in ("latent_lab_model.py", "latent_lab_capabilities.py"):
        text = io.open(SERVICES / name, encoding="utf-8").read()
        if "get_gpu_info" in text or "get_diffusers_backend" in text:
            offenders.append(name)
    assert not offenders, (
        f"these ask the GPU service for the card again: {offenders}"
    )


def test_the_resolver_reads_no_card_and_no_environment():
    """
    Since 2026-09-18 the Latent Lab model is SD 3.5 Large on every card, so
    the module has no reading to make: a `gpu_card` import or an `os.environ`
    lookup in it would be the threshold or the override coming back.
    """
    text = io.open(SERVICES / "latent_lab_model.py", encoding="utf-8").read()
    tree = ast.parse(text)
    imported = {
        alias.name.split(".")[0]
        for n in ast.walk(tree) if isinstance(n, ast.Import)
        for alias in n.names
    } | {
        (n.module or "").split(".")[-1]
        for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
    }
    assert "gpu_card" not in imported, "latent_lab_model.py reads the card again"
    assert "os" not in imported, "latent_lab_model.py reads the environment again"


# ------------------------------------------------------- the name on the card


def test_the_name_comes_off_the_same_reading(monkeypatch):
    _with_session(monkeypatch, _answer({"devices": [{
        "name": "cuda:0 NVIDIA RTX PRO 6000 Blackwell Workstation Edition : cudaMallocAsync",
        "vram_total": 101971591168}]}))
    card = asyncio.run(gpu_card.read())
    assert card.name == "NVIDIA RTX PRO 6000 Blackwell Workstation Edition"
    assert card.total_vram_gb == pytest.approx(94.97, abs=0.01)


@pytest.mark.parametrize("raw,want", [
    ("cuda:0 NVIDIA RTX PRO 6000 Blackwell Workstation Edition : cudaMallocAsync",
     "NVIDIA RTX PRO 6000 Blackwell Workstation Edition"),
    ("cuda:1 NVIDIA GeForce RTX 5090", "NVIDIA GeForce RTX 5090"),
    ("NVIDIA GeForce RTX 4090", "NVIDIA GeForce RTX 4090"),
    # ComfyUI writes an empty allocator where torch will not name one, and the
    # dangling colon used to stay on the card.
    ("cuda:0 NVIDIA GeForce RTX 4090 : ", "NVIDIA GeForce RTX 4090"),
    # One decoration is stripped, not every " : " group in the name.
    ("cuda:0 CARD A : B : alloc", "CARD A : B"),
    ("", ""),
    (None, ""),
])
def test_comfyuis_decoration_stays_with_comfyui(raw, want):
    """The index it computes on and the allocator it uses belong to ComfyUI,
    not to the card, and every reader that compares the name would otherwise
    have to carry them."""
    assert gpu_card._trim_device_name(raw) == want


def test_a_flask_route_can_ask_without_a_loop(monkeypatch):
    _with_session(monkeypatch, _answer({"devices": [
        {"name": "cuda:0 NVIDIA GeForce RTX 5090 : cudaMallocAsync",
         "vram_total": 34359738368}]}))
    assert gpu_card.read_sync().name == "NVIDIA GeForce RTX 5090"


# --------------------------------------------------- the hardware route's table


def test_the_footprint_table_matches_the_board_to_its_family():
    """The file keys on the family, the driver reports the board. An exact
    lookup missed on the development card and drew a table saying nothing had
    been measured — for a card the file holds a full set of readings for."""
    from my_app.routes.hardware_routes import _footprints_for, _load_footprints
    fp = _load_footprints()
    assert "NVIDIA RTX PRO 6000 Blackwell" in fp.get("footprints", {}), (
        "the fixture this test reads has changed; adjust the names below")
    matched = _footprints_for("NVIDIA RTX PRO 6000 Blackwell Workstation Edition", fp)
    assert matched.get("by_model"), "the board no longer finds its family"


def test_a_board_the_file_does_not_know_matches_nothing():
    from my_app.routes.hardware_routes import _footprints_for
    fp = {"footprints": {"NVIDIA GeForce RTX 4090": {"by_model": {"x": {}}}}}
    assert _footprints_for("NVIDIA H100 PCIe", fp) == {}
    assert _footprints_for("", fp) == {}
    assert _footprints_for(None, fp) == {}


def test_the_longest_family_wins():
    """Where two families both continue into the name, the longer one is it."""
    from my_app.routes.hardware_routes import _footprints_for
    fp = {"footprints": {
        "NVIDIA GeForce RTX 5090": {"total_vram_gb": 32, "by_model": {"a": {}}},
        "NVIDIA GeForce RTX 5090 Ti": {"total_vram_gb": 32, "by_model": {"b": {}}}}}
    got = _footprints_for("NVIDIA GeForce RTX 5090 Ti Founders Edition", fp, 32.0)
    assert got["by_model"] == {"b": {}}


def test_a_laptop_card_does_not_inherit_the_desktop_cards_measurements():
    """"NVIDIA GeForce RTX 4090 Laptop GPU" continues "NVIDIA GeForce RTX 4090"
    and has 16 GB against the family's 24. Taking the family would hand it nine
    measurements from a card with half again as much memory, and tell it that a
    22 GB model fits — beside a `total_vram_gb` of 16, in the same answer."""
    from my_app.routes.hardware_routes import _footprints_for, _load_footprints
    fp = _load_footprints()
    assert _footprints_for("NVIDIA GeForce RTX 4090 Laptop GPU", fp, 16.0) == {}
    assert _footprints_for("NVIDIA GeForce RTX 5090 Laptop GPU", fp, 24.0) == {}
    # The desktop cards themselves keep theirs.
    assert _footprints_for("NVIDIA GeForce RTX 4090", fp, 24.0).get("by_model")
    assert _footprints_for("NVIDIA GeForce RTX 5090 D", fp, 32.0).get("by_model")


def test_a_family_is_continued_at_a_word_and_not_mid_word():
    """"RTX 4090M" is not an "RTX 4090"."""
    from my_app.routes.hardware_routes import _footprints_for, _load_footprints
    fp = _load_footprints()
    assert _footprints_for("NVIDIA GeForce RTX 4090M", fp, 16.0) == {}


def test_a_card_whose_size_could_not_be_read_still_matches_its_family():
    """The size guard refuses a disagreement, not a missing reading."""
    from my_app.routes.hardware_routes import _footprints_for, _load_footprints
    fp = _load_footprints()
    assert _footprints_for(
        "NVIDIA RTX PRO 6000 Blackwell Workstation Edition", fp, 0.0).get("by_model")


def test_a_restarted_comfyui_forgets_the_card():
    """It is the one moment the answer can change while the server runs, which
    is why the reading is otherwise kept for the life of the process."""
    src = (REPO / "devserver" / "my_app" / "services" / "comfyui_manager.py").read_text(
        encoding="utf-8")
    assert "gpu_card.reset_cache()" in src


def test_forgetting_the_card_takes_the_lock():
    """A reading already on its way back would otherwise be written after the
    reset, and the forgotten card would come straight back."""
    src = (SERVICES / "gpu_card.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "reset_cache")
    assert any(isinstance(n, ast.With) for n in ast.walk(fn)), \
        "reset_cache assigns the module globals outside the lock"


def test_the_hardware_route_no_longer_asks_the_gpu_service():
    """Stage 0.6 C. The GPU service is being taken down; a route that still
    asks it draws an empty table the day it goes."""
    src = (REPO / "devserver" / "my_app" / "routes" / "hardware_routes.py").read_text(
        encoding="utf-8")
    assert "gpu_info" not in src
    assert "GPU_SERVICE_URL" not in src
    assert "gpu_card" in src
