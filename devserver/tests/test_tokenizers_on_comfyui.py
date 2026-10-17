"""The tokenizers of the text side answer on ComfyUI (stage 5 of the move).

Four things read a vocabulary file and no model: the window count a run asks
before it starts, the comparison instrument's catalogue and cut, and the rows
of the conditioning table the Encoder Fusion surface shows. The node package
answers them on ComfyUI's HTTP server, off the queue; the DevServer asks there
and nowhere else.
"""
import inspect
import sys
import types

import pytest

from file_modules import REPO, load_module

sys.path.insert(0, str(REPO / "devserver"))
PACKAGE = REPO / "comfyui_nodes" / "ai4artsed_comfyui"


class _Recorder:
    def __init__(self, body, status=200):
        self.calls = []
        self.body = body
        self.status_code = status
        self.ok = status < 400

    def __call__(self, url, **kw):
        self.calls.append((url, kw))
        return self

    def json(self):
        return self.body


# ---------------------------------------------------------------------------
# The DevServer's side.

def test_the_window_count_is_asked_of_comfyui(monkeypatch):
    import requests
    from config import COMFYUI_PORT
    from my_app.services import prompt_window as pw

    post = _Recorder({"count": 33, "encoder": "clip_l"})
    monkeypatch.setattr(requests, "post", post)
    assert pw.count_tokens("Ein Haus steht in einer Landschaft", "clip_l") == 33
    url, kw = post.calls[0]
    assert url == f"http://127.0.0.1:{COMFYUI_PORT}/ai4artsed/text/token-count"
    assert kw["json"] == {"text": "Ein Haus steht in einer Landschaft", "encoder": "clip_l"}


def test_an_encoder_nobody_declared_is_left_unknown_without_a_call(monkeypatch):
    import requests
    from my_app.services import prompt_window as pw

    post = _Recorder({"count": 1})
    monkeypatch.setattr(requests, "post", post)
    assert pw.count_tokens("text", "bert") is None
    assert pw.count_tokens("", "clip_l") is None
    assert post.calls == []


def test_the_window_fit_names_the_encoder_and_no_repository():
    from my_app.services import prompt_window as pw
    assert list(inspect.signature(pw.fit_to_window).parameters)[:3] == ["text", "limit", "role"]
    assert list(inspect.signature(pw.count_tokens).parameters) == ["text", "role"]


def test_the_comparison_instrument_asks_comfyui(monkeypatch):
    import requests
    import asyncio
    from config import COMFYUI_PORT
    from my_app.services.text_client import TextClient

    post = _Recorder({"count": 2, "tokens": []})
    monkeypatch.setattr(requests, "post", post)
    client = TextClient()
    assert asyncio.run(client.tokenize("Haus", "a/b")) == {"count": 2, "tokens": []}
    assert asyncio.run(client.tokenizer_facts(["a/b", "c"])) == {"count": 2, "tokens": []}
    assert post.calls[0][0] == f"http://127.0.0.1:{COMFYUI_PORT}/ai4artsed/text/tokenize"
    assert post.calls[0][1]["json"] == {"text": "Haus", "model_id": "a/b"}
    assert post.calls[1][0] == f"http://127.0.0.1:{COMFYUI_PORT}/ai4artsed/text/tokenizer-facts"
    assert post.calls[1][1]["json"] == {"model_ids": ["a/b", "c"]}


def test_the_instrument_offers_the_table_and_nothing_else(monkeypatch):
    """The DevServer's table says which tokenizers may be asked; ComfyUI is
    asked for the cut of those alone, and for the facts of all of them at
    once."""
    import asyncio
    from my_app.routes import text_routes
    from my_app.services import text_client as tc

    class _Client:
        def __init__(self):
            self.asked = []

        async def tokenize(self, text, model_id):
            self.asked.append(("tokenize", model_id))
            return {"model_id": model_id, "tokens": [], "count": 0, "vocab": 1, "matrix": 1, "window": 1}

        async def tokenizer_facts(self, model_ids):
            self.asked.append(("facts", tuple(model_ids)))
            return {m: {"available": m == model_ids[0], "window": 7, "matrix": 9} for m in model_ids}

    fake = _Client()
    monkeypatch.setattr(tc, "get_text_client", lambda: fake)
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(text_routes.text_bp)
    catalogue = text_routes._tokenizer_catalogue()
    first = catalogue[0]
    with app.test_client() as web:
        refused = web.post("/api/text/tokenize", json={"text": "Haus", "model_id": "nobody/nothing"})
        assert refused.status_code == 400 and fake.asked == []
        cut = web.post("/api/text/tokenize", json={"text": "Haus", "model_id": first["id"]})
        assert cut.status_code == 200
        assert cut.get_json()["label"] == first["label"] and cut.get_json()["role"] == first["role"]
        rows = web.get("/api/text/tokenizers").get_json()["tokenizers"]
    assert fake.asked[-1] == ("facts", tuple(e["id"] for e in catalogue))
    assert [r["id"] for r in rows] == [e["id"] for e in catalogue]
    assert rows[0]["available"] is True and rows[0]["window"] == 7 and rows[0]["label"] == first["label"]
    assert all(r["available"] is False for r in rows[1:])


def test_a_refusal_of_comfyui_travels_with_its_status(monkeypatch):
    import requests
    import asyncio
    from my_app.services.text_client import TextClient

    monkeypatch.setattr(requests, "post", _Recorder({"error": "Unknown tokenizer: x"}, status=400))
    answer = asyncio.run(TextClient().tokenize("Haus", "x"))
    assert answer == {"error": "Unknown tokenizer: x", "http_status": 400}


# ---------------------------------------------------------------------------
# The package's side, with ComfyUI's tokenizer classes stood in for.

class _Tok:
    """A tokenizer that cuts on spaces and adds two marks, the way CLIP's
    start and end tokens count against the window."""
    def __init__(self, marks):
        self.marks = marks

    def __call__(self, text, **kw):
        return {"input_ids": [0] * self.marks + [1] * len(text.split())}


@pytest.fixture
def package(monkeypatch):
    sd1_clip = types.ModuleType("comfy.sd1_clip")
    sd1_clip.SDTokenizer = lambda: types.SimpleNamespace(tokenizer=_Tok(2))
    sd3_clip = types.ModuleType("comfy.text_encoders.sd3_clip")
    sd3_clip.T5XXLTokenizer = lambda: types.SimpleNamespace(tokenizer=_Tok(1))
    comfy = types.ModuleType("comfy")
    comfy.sd1_clip = sd1_clip
    encoders = types.ModuleType("comfy.text_encoders")
    encoders.sd3_clip = sd3_clip
    for name, mod in (("comfy", comfy), ("comfy.sd1_clip", sd1_clip),
                      ("comfy.text_encoders", encoders), ("comfy.text_encoders.sd3_clip", sd3_clip)):
        monkeypatch.setitem(sys.modules, name, mod)
    parent = types.ModuleType("ai4artsed_comfyui")
    parent.__path__ = [str(PACKAGE)]
    monkeypatch.setitem(sys.modules, "ai4artsed_comfyui", parent)
    tokenizers = load_module("ai4artsed_comfyui._tokenizers", PACKAGE / "_tokenizers.py", register=True)
    routes = load_module("ai4artsed_comfyui._tokenizer_routes", PACKAGE / "_tokenizer_routes.py", register=True)
    return tokenizers, routes


def test_the_count_is_what_the_encoder_receives(package):
    tokenizers, _ = package
    assert tokenizers.count_tokens("ein haus steht", "clip_l") == {"count": 5, "encoder": "clip_l"}
    assert tokenizers.count_tokens("ein haus steht", "clip_g") == {"count": 5, "encoder": "clip_g"}
    assert tokenizers.count_tokens("ein haus steht", "t5") == {"count": 4, "encoder": "t5"}
    refused = tokenizers.count_tokens("ein haus", "bert")
    assert refused["http_status"] == 400 and "bert" in refused["error"]


def test_a_tokenizer_this_machine_lacks_is_refused_with_404(package, monkeypatch):
    tokenizers, _ = package
    monkeypatch.setattr(tokenizers, "_snapshot", lambda repo: None)
    assert tokenizers.tokenize("Haus", "a/b")["http_status"] == 404
    assert tokenizers.facts(["a/b", "c"]) == {"a/b": {"available": False}, "c": {"available": False}}


def test_a_tokenizer_is_loaded_from_its_directory_and_never_by_id(package, monkeypatch):
    """Given a repository id, transformers asks the hub for the model's
    metadata even under `local_files_only`; given the snapshot directory it
    reads the files and stays on this machine."""
    tokenizers, _ = package
    loaded = []

    class _Tok0(_Tok):
        is_fast = False

        def encode(self, text, **kw):
            return [1] * len(text.split())

        def convert_ids_to_tokens(self, ids):
            return ["x"] * len(ids)

        def decode(self, ids):
            return "x"

        def __len__(self):
            return 7

    class _Auto:
        """Stands in for AutoTokenizer and AutoConfig alike; both are asked
        for the same directory."""
        @staticmethod
        def from_pretrained(where, **kw):
            loaded.append((where, kw.get("local_files_only")))
            return _Tok0(0)

    hub = types.ModuleType("huggingface_hub")
    hub.try_to_load_from_cache = lambda repo, name: "/cache/models--a--b/snapshots/abc/" + name
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    transformers = types.ModuleType("transformers")
    transformers.AutoTokenizer = _Auto
    transformers.AutoConfig = _Auto
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setattr(tokenizers, "_tokenizers", {})
    monkeypatch.setattr(tokenizers, "_facts", {})

    answer = tokenizers.tokenize("ein haus", "a/b")
    assert answer["count"] == 2 and answer["vocab"] == 7
    assert loaded and all(where == "/cache/models--a--b/snapshots/abc" and lfo is True for where, lfo in loaded)


def test_a_failure_inside_the_cut_answers_as_json_with_its_cause(package, monkeypatch):
    tokenizers, _ = package

    class _Refusing:
        def encode(self, text, **kw):
            raise TypeError("TextEncodeInput must be str")

    monkeypatch.setattr(tokenizers, "_snapshot", lambda repo: "/somewhere")
    monkeypatch.setattr(tokenizers, "_load", lambda repo, snap: _Refusing())
    answer = tokenizers.tokenize("\ud83d", "a/b")
    assert answer["http_status"] == 500 and "TextEncodeInput" in answer["error"]

    class _Broken:
        def __call__(self, text, **kw):
            raise TypeError("TextEncodeInput must be str")

    monkeypatch.setattr(tokenizers, "_encoder_tokenizers", {"t5": _Broken()})
    answer = tokenizers.count_tokens("\ud83d", "t5")
    assert answer["http_status"] == 500 and "t5" in answer["error"]


def test_the_routes_refuse_a_text_beyond_the_bound_and_a_body_that_is_no_object(package):
    import asyncio
    _, routes = package

    class _Routes:
        def __init__(self):
            self.handlers = {}

        def post(self, path):
            return lambda fn: self.handlers.__setitem__(path, fn) or fn

    class _Request:
        def __init__(self, body):
            self._body = body

        async def json(self):
            if isinstance(self._body, Exception):
                raise self._body
            return self._body

    table = _Routes()
    routes.register(table)
    count = table.handlers["/ai4artsed/text/token-count"]
    too_long = asyncio.run(count(_Request({"text": "x" * (routes.MAX_TEXT_CHARS + 1), "encoder": "t5"})))
    assert too_long.status == 413
    no_object = asyncio.run(count(_Request(["not", "an", "object"])))
    assert no_object.status == 400
    from aiohttp import web
    with pytest.raises(web.HTTPRequestEntityTooLarge):
        asyncio.run(count(_Request(web.HTTPRequestEntityTooLarge(max_size=1, actual_size=2))))
    facts = table.handlers["/ai4artsed/text/tokenizer-facts"]
    assert asyncio.run(facts(_Request({"model_ids": ["a"] * (routes.MAX_MODEL_IDS + 1)}))).status == 413


def test_install_registers_on_the_running_server_and_on_nothing_else(package, monkeypatch):
    """The server is taken from `sys.modules`, where ComfyUI has put it before
    any node package loads; a `server` module of another program, or one whose
    PromptServer is not constructed, registers nothing and raises nothing."""
    _, routes = package

    class _Routes:
        def __init__(self):
            self.seen = []

        def post(self, path):
            return lambda fn: self.seen.append(path) or fn

    monkeypatch.delitem(sys.modules, "server", raising=False)
    assert routes.install() is False

    foreign = types.ModuleType("server")
    monkeypatch.setitem(sys.modules, "server", foreign)
    assert routes.install() is False

    class _PromptServer:
        pass

    foreign.PromptServer = _PromptServer
    assert routes.install() is False

    table = _Routes()
    _PromptServer.instance = types.SimpleNamespace(routes=table)
    assert routes.install() is True
    assert sorted(table.seen) == ["/ai4artsed/text/encoder-rows", "/ai4artsed/text/token-count",
                                  "/ai4artsed/text/tokenize", "/ai4artsed/text/tokenizer-facts"]


def test_the_package_registers_the_four_doors(package):
    _, routes = package

    class _Routes:
        def __init__(self):
            self.seen = []

        def get(self, path):
            return lambda fn: self.seen.append(("GET", path)) or fn

        def post(self, path):
            return lambda fn: self.seen.append(("POST", path)) or fn

    table = _Routes()
    routes.register(table)
    assert sorted(table.seen) == [
        ("POST", "/ai4artsed/text/encoder-rows"),
        ("POST", "/ai4artsed/text/token-count"),
        ("POST", "/ai4artsed/text/tokenize"),
        ("POST", "/ai4artsed/text/tokenizer-facts"),
    ]


# ---------------------------------------------------------------------------
# The rows of the conditioning table (the Encoder Fusion surface's token table).

class _RowTok:
    """A stand-in for ComfyUI's SDTokenizer: one piece per space-separated
    word, a `+` inside a word making two pieces of one word, start and end
    marks and padding laid the way `tokenize_with_weights` lays them, and a
    vocabulary whose entries carry the boundary marks of the family.
    `unreadable` names pieces that decode to nothing on their own."""

    def __init__(self, has_start, max_length, min_length, pad_to_max, word_end="",
                 word_start="", unreadable=()):
        self.start_token = 0 if has_start else None
        self.end_token = 1
        self.pad_token = 1 if has_start else 2
        self.max_length, self.min_length = max_length, min_length
        self.pad_to_max = pad_to_max
        self.word_end, self.word_start = word_end, word_start
        self.unreadable = set(unreadable)
        # the family's key in the graph's tokenizer options
        self.embedding_key = "clip_l" if has_start else "t5xxl"
        self.last_options = None
        self.vocab = {"<s>": 0, "</s>": 1, "<pad>": 2}
        self.inv_vocab = {0: "<s>", 1: "</s>", 2: "<pad>"}
        self.tokenizer = self

    def _id(self, raw):
        if raw not in self.vocab:
            self.vocab[raw] = len(self.vocab)
            self.inv_vocab[self.vocab[raw]] = raw
        return self.vocab[raw]

    def _pieces(self, text):
        out = []
        for word in text.split():
            bits = word.split("+")
            for i, bit in enumerate(bits):
                raw = bit
                if self.word_start and i == 0:
                    raw = self.word_start + raw
                if self.word_end and i == len(bits) - 1:
                    raw = raw + self.word_end
                out.append(self._id(raw))
        return out

    def tokenize_with_weights(self, text, return_word_ids=True, tokenizer_options=None):
        self.last_options = dict(tokenizer_options or {})
        min_length = self.last_options.get(f"{self.embedding_key}_min_length")
        pieces = self._pieces(text)
        chunks, batch = [], []
        if self.start_token is not None:
            batch.append((self.start_token, 1.0, 0))
        for piece in pieces:
            if len(batch) + 1 > self.max_length - 1:
                batch.append((self.end_token, 1.0, 0))
                while self.pad_to_max and len(batch) < self.max_length:
                    batch.append((self.pad_token, 1.0, 0))
                chunks.append(batch)
                batch = [(self.start_token, 1.0, 0)] if self.start_token is not None else []
            batch.append((piece, 1.0, 1))
        batch.append((self.end_token, 1.0, 0))
        floor = min_length if min_length is not None else self.min_length
        if floor is not None:
            while len(batch) < floor:
                batch.append((self.pad_token, 1.0, 0))
        if self.pad_to_max:
            while len(batch) < self.max_length:
                batch.append((self.pad_token, 1.0, 0))
        chunks.append(batch)
        return chunks

    def decode(self, ids):
        raws = [self.inv_vocab[i] for i in ids]
        if any(r in self.unreadable for r in raws):
            # two halves together read; one half alone does not
            return "".join(r.rstrip(self.word_end).lstrip(self.word_start) for r in raws) \
                if len(raws) > 1 else ""
        return "".join(r.replace(self.word_end, "").replace(self.word_start, "") for r in raws)


@pytest.fixture
def rows_package(package, monkeypatch):
    tokenizers, routes = package
    clip = _RowTok(has_start=True, max_length=7, min_length=None, pad_to_max=True,
                   word_end="</w>", unreadable={"Ð", "±", "±</w>", "¾</w>"})
    t5 = _RowTok(has_start=False, max_length=99999, min_length=3, pad_to_max=False,
                 word_start="▁")
    monkeypatch.setattr(tokenizers, "_row_tokenizers", {"clip": clip, "t5": t5})
    return tokenizers, routes


def test_the_rows_are_laid_the_way_the_graph_lays_them(rows_package):
    """CLIP: the start mark on row 0, the pieces, the end mark, padding to the
    window. T5: the pieces, `</s>`, padding to the block's length. Both
    columns stop at the end mark and say how long the block is."""
    tokenizers, _ = rows_package
    out = tokenizers.encoder_rows("ein haus", 512)
    clip, t5 = out["clip"], out["t5"]
    assert [(r["row"], r["kind"], r["s"]) for r in clip["rows"]] == [
        (0, "start", "<s>"), (1, "piece", "ein"), (2, "piece", "haus"), (3, "end", "</s>")]
    assert (clip["filled"], clip["block"], clip["cut"]) == (4, 7, 0)
    assert [(r["row"], r["kind"], r["s"]) for r in t5["rows"]] == [
        (0, "piece", "ein"), (1, "piece", "haus"), (2, "end", "</s>")]
    assert (t5["filled"], t5["block"], t5["cut"]) == (3, 512, 0)
    # the vocabulary entry travels with the piece, boundary mark included
    assert clip["rows"][1]["raw"] == "ein</w>" and t5["rows"][1]["raw"] == "▁haus"


def test_a_piece_that_continues_a_word_says_so(rows_package):
    tokenizers, _ = rows_package
    out = tokenizers.encoder_rows("land+schaft steht", 512)
    assert [(r["s"], r["part"]) for r in out["clip"]["rows"][1:-1]] == [
        ("land", False), ("schaft", True), ("steht", False)]
    assert [(r["s"], r["part"]) for r in out["t5"]["rows"][:-1]] == [
        ("land", False), ("schaft", True), ("steht", False)]


def test_what_the_clip_window_cuts_is_counted_and_t5_keeps_everything(rows_package):
    tokenizers, _ = rows_package
    out = tokenizers.encoder_rows("a b c d e f g h", 4)
    clip = out["clip"]
    # a window of 7: start, five pieces, end; three pieces fall out
    assert [r["kind"] for r in clip["rows"]] == ["start"] + ["piece"] * 5 + ["end"]
    assert clip["cut"] == 3 and clip["block"] == 7
    t5 = out["t5"]
    assert t5["filled"] == 9 and t5["block"] == 9 and t5["cut"] == 0


def test_two_halves_of_one_character_read_as_that_character(rows_package):
    tokenizers, _ = rows_package
    out = tokenizers.encoder_rows("Ð+±", 512)
    # the stand-in joins the two vocabulary entries; ComfyUI's CLIP decodes
    # the two byte halves to „Б" the same way, both rows carrying it
    assert [(r["s"], r["part"]) for r in out["clip"]["rows"][1:-1]] == [("Ð±", False), ("Ð±", True)]


def test_a_run_of_half_characters_reads_letter_by_letter(rows_package):
    """Four pieces making two characters read as two characters, two rows
    each - and not as the whole word on every row."""
    tokenizers, _ = rows_package
    out = tokenizers.encoder_rows("Ð+±+Ð+¾", 512)
    assert [(r["s"], r["part"]) for r in out["clip"]["rows"][1:-1]] == [
        ("Ð±", False), ("Ð±", True), ("Ð¾", True), ("Ð¾", True)]


def test_the_t5_block_is_as_long_as_the_graph_makes_it(rows_package):
    """The length travels as the tokenizer option the graph's
    T5TokenizerOptions node sets, under the family's own key."""
    tokenizers, _ = rows_package
    assert tokenizers.encoder_rows("ein", 512)["t5"]["block"] == 512
    assert tokenizers._row_tokenizers["t5"].last_options == {"t5xxl_min_length": 512}
    assert tokenizers.encoder_rows("ein", 77)["t5"]["block"] == 77


def test_the_rows_route_checks_its_body(rows_package):
    import asyncio
    _, routes = rows_package

    class _Routes:
        def __init__(self):
            self.handlers = {}

        def post(self, path):
            return lambda fn: self.handlers.__setitem__(path, fn) or fn

    class _Request:
        def __init__(self, body):
            self._body = body

        async def json(self):
            return self._body

    table = _Routes()
    routes.register(table)
    rows = table.handlers["/ai4artsed/text/encoder-rows"]
    assert asyncio.run(rows(_Request({"text": ""}))).status == 400
    assert asyncio.run(rows(_Request({"text": "x", "t5_min_length": "512"}))).status == 400
    assert asyncio.run(rows(_Request({"text": "x", "t5_min_length": True}))).status == 400
    assert asyncio.run(rows(_Request({"text": "x", "t5_min_length": 10001}))).status == 400
    assert asyncio.run(rows(_Request({"text": "x" * (routes.MAX_TEXT_CHARS + 1)}))).status == 413
    good = asyncio.run(rows(_Request({"text": "ein haus", "t5_min_length": 512})))
    assert good.status == 200
    import json
    body = json.loads(good.text)
    assert body["clip"]["filled"] == 4 and body["t5"]["block"] == 512


def test_the_devserver_asks_comfyui_for_the_rows_with_the_graphs_t5_length(monkeypatch):
    import asyncio
    from config import COMFYUI_PORT
    from my_app.services.text_client import TextClient
    from schemas.engine.comfyui_chunk_support import T5_LENGTH
    import requests

    post = _Recorder({"clip": {"rows": []}, "t5": {"rows": []}})
    monkeypatch.setattr(requests, "post", post)
    client = TextClient()
    answer = asyncio.run(client.encoder_rows("ein haus", T5_LENGTH))
    assert answer == {"clip": {"rows": []}, "t5": {"rows": []}}
    url, kw = post.calls[0]
    assert url == f"http://127.0.0.1:{COMFYUI_PORT}/ai4artsed/text/encoder-rows"
    assert kw["json"] == {"text": "ein haus", "t5_min_length": T5_LENGTH}
