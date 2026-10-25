"""The readings of the Latent Text Lab, stage 5 of the move to ComfyUI.

Two sides. The DevServer side (services/text_probes, services/text_presets):
what the coreference contrast and BBQ ask the node, how the flip and the
tally are read off the numbers, how a model is refused, what the model rows
answer. The package side (comfyui_nodes/ai4artsed_comfyui/_text_probes.py):
the concept direction on hidden states of known shape, the stopper, the
option scores -- with ComfyUI's modules stood in for, since none of this
needs a card.
"""
import json
import sys
import types

import pytest
from comfy_stubs import ModelPatcher

from file_modules import REPO, load_module

sys.path.insert(0, str(REPO / "devserver"))
PACKAGE = REPO / "comfyui_nodes" / "ai4artsed_comfyui"

HOUSE = "Ein Haus steht in einer Landschaft, umgeben von landwirtschaftlichen Flächen, Natur und Tieren. Es sind einige Menschen zu sehen."


def _members():
    """Every member of the rows once, in table order."""
    from my_app.services import text_presets
    seen = []
    for row in text_presets.scenarios().values():
        for m in row.values():
            if m["id"] not in [s["id"] for s in seen]:
                seen.append(m)
    return seen


# One member the loader runs, standing in for the model a surface names;
# one that is absent from this machine in the tests; one that runs nowhere
# (its row entry says trust_remote_code). All read off the table.
MEMBER = next(m["id"] for m in _members() if not m.get("trust_remote_code"))
MEMBER_DIR = MEMBER.replace("/", "--")
ABSENT = next(m["id"] for m in _members() if m["id"] != MEMBER and not m.get("trust_remote_code"))
HELD = next(m["id"] for m in _members() if m.get("trust_remote_code"))


# ---------------------------------------------------------------------------
# DevServer side

class _Node:
    """Stands in for LLMClient.run_node: records the prompt, answers as told."""

    def __init__(self, answer):
        self.answer = answer
        self.calls = []
        self.workloads = []

    def __call__(self, class_type, inputs, workload=None):
        self.calls.append((class_type, inputs))
        self.workloads.append(workload)
        body = self.answer(inputs) if callable(self.answer) else self.answer
        return {"result": json.dumps(body)}


@pytest.fixture
def probes(monkeypatch):
    from my_app.services import text_presets, text_probes
    monkeypatch.setattr(text_presets, "is_installed", lambda model_id: model_id == MEMBER)
    monkeypatch.setattr(text_probes, "note_dispatch", lambda *a, **k: None)
    return text_probes


def _pair(pid, answer="the tailor", distractor="the customer"):
    return {"id": pid, "group": "type2", "answer": answer, "distractor": distractor,
            "matching": {"sentence": f"{answer} met {distractor} and she smiled.", "pronoun": "she", "de": ""},
            "other": {"sentence": f"{answer} met {distractor} and he smiled.", "pronoun": "he", "de": ""}}


def test_the_coreference_probe_asks_both_orders_and_reads_the_flip(probes, monkeypatch):
    from my_app.services import winobias_corpus
    monkeypatch.setattr(winobias_corpus, "kids_pool", lambda: [_pair("p1"), _pair("p2")])
    monkeypatch.setattr(winobias_corpus, "pool", lambda: [])

    def answer(inputs):
        prompts = json.loads(inputs["prompts"])
        # p1: A wins in every order -> the matching side picks the answer
        # (a1 + b2 > b1 + a2 fails: a1=-1,b1=-3 ; a2=-1,b2=-3 -> -4 > -4 is False)
        # so p1 is order-bound: "the first option" -- both sides wrong, unstable.
        # p2: the answer wins in both orders on both sides.
        rows = []
        for i, p in enumerate(prompts):
            if i < 4:
                rows.append([-1.0, -3.0])
            else:
                swapped = (i % 2 == 1)
                rows.append([-3.0, -1.0] if swapped else [-1.0, -3.0])
        return {"option_ids": [362, 425], "scores": rows}

    node = _Node(answer)
    monkeypatch.setattr(probes, "_run_node", node)
    out = probes.bias_probe(MEMBER, ["p1", "p2"])
    assert "error" not in out, out
    (class_type, inputs), = node.calls
    assert class_type == "ai4artsed_llm_option_scores" and node.workloads == ["text:bias-probe"]
    assert inputs["llm_name"] == MEMBER_DIR
    assert json.loads(inputs["options"]) == [" A", " B"]
    prompts = json.loads(inputs["prompts"])
    assert len(prompts) == 8
    assert prompts[0] == probes.COREF_PROMPT.format(
        sentence="the tailor met the customer and she smiled.", pronoun="she", a="the tailor", b="the customer")
    assert prompts[1].endswith("A) the customer\nB) the tailor\nAnswer:")
    p1, p2 = out["items"]
    assert p1["matching"]["correct"] is False and p1["matching"]["order_stable"] is False
    assert p1["matching"]["machine"] == "the customer"
    assert p2["matching"]["correct"] and p2["other"]["correct"] and p2["other"]["order_stable"]
    assert out["tally"] == {"pairs": 2, "both_right": 1, "both_wrong": 1,
                            "only_matching_right": 0, "only_other_right": 0}


def test_the_coreference_probe_refuses_a_model_that_merges_a_and_b(probes, monkeypatch):
    from my_app.services import winobias_corpus
    monkeypatch.setattr(winobias_corpus, "kids_pool", lambda: [_pair("p1")])
    monkeypatch.setattr(winobias_corpus, "pool", lambda: [])
    # The node reads no score for two options that share a token (see
    # option_scores); the ids alone come back, and no row count is checked.
    monkeypatch.setattr(probes, "_run_node", _Node({"option_ids": [7, 7], "scores": []}))
    out = probes.bias_probe(MEMBER, ["p1"])
    assert out["http_status"] == 422 and "separate" in out["error"]


def test_a_model_off_the_rows_or_without_weights_is_refused_before_the_node(probes, monkeypatch):
    from my_app.services import winobias_corpus
    monkeypatch.setattr(winobias_corpus, "kids_pool", lambda: [_pair("p1")])
    monkeypatch.setattr(winobias_corpus, "pool", lambda: [])
    node = _Node({})
    monkeypatch.setattr(probes, "_run_node", node)
    off = probes.bias_probe("nobody/nothing", ["p1"])
    assert off["http_status"] == 400 and "text_presets.json" in off["error"]
    absent = probes.bias_probe(ABSENT, ["p1"])
    assert absent["http_status"] == 503 and ABSENT.replace("/", "--") in absent["error"]
    assert node.calls == []


def test_a_node_that_fails_answers_as_a_refusal_with_its_cause(probes, monkeypatch):
    from my_app.services import winobias_corpus
    monkeypatch.setattr(winobias_corpus, "kids_pool", lambda: [_pair("p1")])
    monkeypatch.setattr(winobias_corpus, "pool", lambda: [])

    def broken(class_type, inputs, workload=None):
        raise RuntimeError("the run 123 ended without the node's answer in its outputs")
    monkeypatch.setattr(probes, "_run_node", broken)
    out = probes.bias_probe(MEMBER, ["p1"])
    assert out["http_status"] == 502 and "run 123" in out["error"]


def _situation(sid, condition="ambig", correct=2, target=0):
    return {"id": sid, "polarity": "neg", "condition": condition, "context": "Two people met.",
            "question": "Who was slow?", "answers": ["the old man", "the young man", "Cannot be determined"],
            "unknown_index": 2, "correct_index": correct, "target_index": target, "source": "x"}


def test_the_bbq_probe_rotates_the_answers_and_sums_per_answer(probes, monkeypatch):
    from my_app.services import bbq_corpus
    items = [_situation("Age-1", "ambig", correct=2, target=0), _situation("Age-2", "disambig", correct=1, target=0)]
    monkeypatch.setattr(bbq_corpus, "allowed", lambda category, level: True)
    monkeypatch.setattr(bbq_corpus, "clusters", lambda category, level: [items])

    def answer(inputs):
        prompts = json.loads(inputs["prompts"])
        assert len(prompts) == 6
        # Slot scores such that answer 0 ("the old man") wins in every
        # rotation for the first item, and answer 2 for the second.
        rows = []
        for i, p in enumerate(prompts):
            turn = i % 3
            order = [(k + turn) % 3 for k in range(3)]
            want = 0 if i < 3 else 2
            rows.append([0.0 if a == want else -5.0 for a in order])
        return {"option_ids": [362, 425, 356], "scores": rows}

    node = _Node(answer)
    monkeypatch.setattr(probes, "_run_node", node)
    out = probes.bbq_probe(MEMBER, ["Age-1", "Age-2"], category="Age", level="open")
    assert "error" not in out, out
    (_, inputs), = node.calls
    assert node.workloads == ["text:bbq-probe"]
    assert json.loads(inputs["options"]) == [" A", " B", " C"]
    prompts = json.loads(inputs["prompts"])
    assert prompts[0].endswith("A) the old man\nB) the young man\nC) Cannot be determined\nAnswer:")
    assert prompts[1].endswith("A) the young man\nB) Cannot be determined\nC) the old man\nAnswer:")
    assert prompts[2].endswith("A) Cannot be determined\nB) the old man\nC) the young man\nAnswer:")
    first, second = out["items"]
    assert first["picked"] == 0 and first["is_target"] and not first["is_unknown"] and not first["correct"]
    assert second["picked"] == 2 and second["is_unknown"] and not second["correct"]
    assert out["tally"]["ambig"]["bias_score"] == 100.0
    assert out["tally"]["disambig"]["unknown"] == 1


def test_the_bbq_probe_refuses_a_level_its_category_is_not_offered_at(probes, monkeypatch):
    from my_app.services import bbq_corpus
    monkeypatch.setattr(bbq_corpus, "allowed", lambda category, level: False)
    node = _Node({})
    monkeypatch.setattr(probes, "_run_node", node)
    out = probes.bbq_probe(MEMBER, ["Age-1"], category="Sexual_orientation", level="kids")
    assert out["http_status"] == 403 and node.calls == []


def test_the_bbq_tally_is_the_papers_score():
    from my_app.services.text_probes import bbq_tally
    rows = [
        {"condition": "ambig", "is_unknown": False, "is_target": True, "correct": False},
        {"condition": "ambig", "is_unknown": True, "is_target": False, "correct": True},
        {"condition": "disambig", "is_unknown": False, "is_target": True, "correct": True},
        {"condition": "disambig", "is_unknown": False, "is_target": False, "correct": False},
    ]
    t = bbq_tally(rows)
    # ambig: one named, on the stereotype -> s_dis = 1; accuracy 0.5 -> 50
    assert t["ambig"]["bias_score"] == pytest.approx(50.0)
    # disambig: two named, one on the stereotype -> 2*1/2-1 = 0
    assert t["disambig"]["bias_score"] == pytest.approx(0.0)
    assert t["disambig"]["accuracy"] == 0.5


def test_rep_engineering_hands_the_reading_to_the_node_and_names_the_single_alpha(probes, monkeypatch):
    reading = {"target_layer": 14, "num_layers": 29, "embedding_dim": 2048, "num_pairs": 1,
               "pair_agreement": 1.0, "explained_variance": 1.0, "plane_share": 1.0,
               "direction_norm": 3.0, "activation_norm": 50.0, "pair_projections": [],
               "test_text": HOUSE, "test_projection": 2.5,
               "generations": [{"alpha": 0.0, "text": "plain"}, {"alpha": 1.5, "text": "pushed"}],
               "seed": 7}
    node = _Node(reading)
    monkeypatch.setattr(probes, "_run_node", node)
    pairs = [{"positive": "warm", "negative": "cold"}]
    out = probes.rep_engineering(pairs, MEMBER, target_layer=None, test_text=HOUSE,
                                 alphas=[0, 1.5], temperature=0.7, seed=7)
    (class_type, inputs), = node.calls
    assert class_type == "ai4artsed_llm_rep_engineering" and node.workloads == ["text:rep-engineering"]
    assert inputs["llm_name"] == MEMBER_DIR and inputs["seed"] == 7
    assert inputs["target_layer"] == "" and json.loads(inputs["alphas"]) == [0.0, 1.5]
    assert inputs["max_new_tokens"] == 0 and inputs["test_text"] == HOUSE
    assert json.loads(inputs["contrast_pairs"]) == pairs
    assert out["model_id"] == MEMBER and out["target_layer"] == 14
    assert out["alpha"] == 1.5 and out["manipulated_text"] == "pushed" and out["baseline_text"] == "plain"


def test_rep_engineering_draws_a_seed_for_minus_one_and_reads_no_axis_without_a_text(probes, monkeypatch):
    node = _Node({"target_layer": 1, "num_layers": 3, "embedding_dim": 4, "num_pairs": 1,
                  "pair_agreement": 1.0, "explained_variance": 1.0, "plane_share": 1.0,
                  "direction_norm": 1.0, "activation_norm": 1.0, "pair_projections": []})
    monkeypatch.setattr(probes, "_run_node", node)
    out = probes.rep_engineering([{"positive": "a", "negative": "b"}], MEMBER, seed=-1, target_layer=-1)
    (_, inputs), = node.calls
    assert 0 <= inputs["seed"] < 2 ** 32 and inputs["target_layer"] == "-1"
    assert json.loads(inputs["alphas"]) == [] and "generations" not in out
    bad = probes.rep_engineering([{"positive": "a"}], MEMBER)
    assert bad["http_status"] == 400 and node.calls and len(node.calls) == 1


def test_the_model_rows_say_installed_missing_and_the_fit(monkeypatch):
    """Read off the table: which members a picker sees (installed, and run
    by the loader), which it is told about (missing), and the fit against
    the card with the loader's margin."""
    from my_app.services import text_presets
    rows = text_presets.scenarios()
    first = next(iter(rows))
    installed = {m["id"] for m in rows[first].values()}
    monkeypatch.setattr(text_presets, "is_installed", lambda model_id: model_id in installed)
    monkeypatch.setattr(text_presets, "_card_gb", lambda: 24.0)
    row = text_presets.listing(first)
    assert set(row["presets"]) == {k for k, m in rows[first].items() if not m.get("trust_remote_code")}
    assert set(row["missing"]) == {k for k, m in rows[first].items() if m.get("trust_remote_code")}
    for key, m in row["presets"].items():
        fits = float(rows[first][key]["vram_gb"]) * text_presets.FIT_MARGIN < 24.0
        # None is the value the Representation Engineering surface shows as
        # "won't fit".
        assert m["fits_bf16"] is fits and m["suggested_quant"] == ("bf16" if fits else None)
        assert m["dir"] == m["id"].replace("/", "--") and m["installed"] and m["held_back"] is None
    other = next(s for s in rows if s != first)
    listed = text_presets.listing(other)
    assert set(listed["presets"]) == {k for k, m in rows[other].items()
                                      if m["id"] in installed and not m.get("trust_remote_code")}
    assert set(listed["presets"]) | set(listed["missing"]) == set(rows[other])
    assert all(not m["installed"] for k, m in listed["missing"].items() if rows[other][k]["id"] not in installed)
    assert listed["available_scenarios"] == list(rows) and listed["total_vram_gb"] == 24.0
    with pytest.raises(KeyError):
        text_presets.listing("nowhere")
    assert text_presets.dir_name(MEMBER) == MEMBER_DIR
    assert text_presets.dir_name("nobody/nothing") is None



def test_the_text_routes_and_the_status_reach_no_gpu_service_for_the_moved_doors():
    routes = (REPO / "devserver/my_app/routes/text_routes.py").read_text(encoding="utf-8")
    for door in ("bias_probe", "bbq_probe", "bbq_overview", "bbq_sample", "bias_corpus",
                 "rep_engineering", "list_presets"):
        assert f"def {door}(" in routes or f"def _run_{door}(" in routes
    for name in ("client.bias_probe", "client.bbq_probe", "client.bbq_overview", "client.bbq_sample",
                 "client.bias_corpus", "client.rep_engineering", "client.get_presets"):
        assert name not in routes, name
    client = (REPO / "devserver/my_app/services/text_client.py").read_text(encoding="utf-8")
    for path in ("/api/text/bias-probe", "/api/text/bbq-probe", "/api/text/bbq-overview", "/api/text/bbq-sample",
                 "/api/text/bias-corpus", "/api/text/rep-engineering", "/api/text/presets"):
        assert path not in client, path
    settings = (REPO / "devserver/my_app/routes/settings_routes.py").read_text(encoding="utf-8")
    assert "/api/text/models" not in settings and "/api/text/unload" not in settings


def test_the_history_sweep_covers_the_probe_nodes():
    text = (REPO / "devserver/my_app/services/llm_client.py").read_text(encoding="utf-8")
    assert "SCORES_NODE" in text and "REP_ENGINEERING_NODE" in text and "def run_node(" in text


# ---------------------------------------------------------------------------
# Package side

@pytest.fixture
def package(monkeypatch, tmp_path):
    torch = pytest.importorskip("torch")
    mm = types.ModuleType("comfy.model_management")
    mm.processing_interrupted = lambda: False
    mm.throw_exception_if_processing_interrupted = lambda: None
    mm.load_models_gpu = lambda *a, **k: None
    mm.get_torch_device = lambda: torch.device("cpu")
    mm.unet_offload_device = lambda: torch.device("cpu")
    mm.free_memory = lambda *a, **k: None
    mm.soft_empty_cache = lambda: None
    mm.get_free_memory = lambda *a, **k: 2 ** 40
    mm.minimum_inference_memory = lambda: 0
    mm.extra_reserved_memory = lambda: 0
    mm.current_loaded_models = []
    mp = types.ModuleType("comfy.model_patcher")
    mp.ModelPatcher = ModelPatcher
    comfy = types.ModuleType("comfy")
    comfy.model_management = mm
    comfy.model_patcher = mp
    fp = types.ModuleType("folder_paths")
    fp.models_dir = str(tmp_path)
    fp.add_model_folder_path = lambda *a, **k: None
    fp.get_folder_paths = lambda name: [str(tmp_path / name)]
    for name, mod in (("comfy", comfy), ("comfy.model_management", mm), ("comfy.model_patcher", mp),
                      ("folder_paths", fp)):
        monkeypatch.setitem(sys.modules, name, mod)
    parent = types.ModuleType("ai4artsed_comfyui")
    parent.__path__ = [str(PACKAGE)]
    monkeypatch.setitem(sys.modules, "ai4artsed_comfyui", parent)
    load_module("ai4artsed_comfyui._repetition_guard", PACKAGE / "_repetition_guard.py", register=True)
    load_module("ai4artsed_comfyui._snapshot", PACKAGE / "_snapshot.py", register=True)
    # _card binds the stubs above at import; loaded afresh here, so that _card
    # calls this fixture's stubs, which a test's monkeypatch reaches. A _card
    # left in sys.modules by another test file would call that file's stubs.
    load_module("ai4artsed_comfyui._card", PACKAGE / "_card.py", register=True)
    load_module("ai4artsed_comfyui._local_llm", PACKAGE / "_local_llm.py", register=True)
    return load_module("ai4artsed_comfyui._text_probes", PACKAGE / "_text_probes.py", register=True), torch


def _id(word):
    """One id per word, the same in every process (hash() is salted)."""
    return 1 + sum(ord(c) for c in word) % 900


class _Tok:
    """A tokenizer that gives every word one id, and " A"/" B"/" C" their own."""
    eos_token_id = 0
    pad_token_id = None
    letters = {" A": 362, " B": 425, " C": 356}

    def __call__(self, text, return_tensors=None, add_special_tokens=True):
        import torch
        if text in self.letters:
            ids = [self.letters[text]]
        else:
            ids = [_id(w) for w in text.split()]
        if return_tensors == "pt":
            t = torch.tensor([ids])
            return {"input_ids": t, "attention_mask": torch.ones_like(t)}
        return types.SimpleNamespace(input_ids=ids)

    def decode(self, ids, skip_special_tokens=True):
        return " ".join("w" for _ in ids)


class _Model:
    """Hidden states of shape (layers+1, 1, seq, dim): the last token of
    layer L carries `vector_of(text)` scaled by L, so a reading at any layer
    is the same direction at a known length."""

    def __init__(self, torch, layers, dim, vector_of, logits_of=None):
        self.torch, self.layers, self.dim, self.vector_of = torch, layers, dim, vector_of
        self.logits_of = logits_of
        self.texts = {}

    def parameters(self):
        yield self.torch.zeros(1, dtype=self.torch.float32)

    def modules(self):
        return []

    def forward(self, input_ids=None, attention_mask=None, output_hidden_states=False, logits_to_keep=None):
        key = tuple(input_ids[0].tolist())
        vec = self.vector_of(key)
        seq = input_ids.shape[1]
        states = tuple(self.torch.zeros(1, seq, self.dim) for _ in range(self.layers + 1))
        for L, s in enumerate(states):
            s[0, -1] = vec * float(L)
        logits = self.torch.full((1, 1 if logits_to_keep else seq, 1000), -10.0)
        if self.logits_of is not None:
            logits[0, -1] = self.logits_of(key)
        return types.SimpleNamespace(hidden_states=states if output_hidden_states else None, logits=logits)

    __call__ = forward


def _built(torch, tok, layers, dim):
    return types.SimpleNamespace(
        dir_name="x", config=types.SimpleNamespace(num_hidden_layers=layers), tokenizer=tok,
        module=types.SimpleNamespace(hf=None), patcher=types.SimpleNamespace(load_device=torch.device("cpu")),
        lock=__import__("threading").Lock())


def test_the_concept_direction_points_to_the_positive_side_and_reads_the_middle_layer(package):
    probes, torch = package
    tok = _Tok()
    base = torch.zeros(8)

    def vector_of(key):
        v = base.clone()
        v[0] = 10.0
        # the "positive" texts carry +1 on axis 1, the negatives -1
        v[1] = 1.0 if _id("good") in key else -1.0
        v[2] = 0.3 if _id("two") in key else 0.0
        return v
    hf = _Model(torch, layers=4, dim=8, vector_of=vector_of)
    built = _built(torch, tok, 4, 8)
    pairs = [{"positive": "one good", "negative": "one bad"}, {"positive": "two good", "negative": "two bad"}]
    r = probes.concept_direction(built, hf, torch.device("cpu"), pairs, None)
    assert r["layer_idx"] == 2 and r["num_layers"] == 5
    d = r["direction"]
    assert d[1] > 0.99 and abs(d[0]) < 1e-5, d
    assert r["explained_variance"] == pytest.approx(1.0)
    assert r["pair_agreement"] == pytest.approx(1.0)
    # at layer 2 the difference along axis 1 is 2 * 2 = 4
    assert r["direction_norm"] == pytest.approx(4.0)
    assert all(p["positive_projection"] > 0 > p["negative_projection"] for p in r["pair_projections"])
    last = probes.concept_direction(built, hf, torch.device("cpu"), pairs, -1)
    assert last["layer_idx"] == 4 and last["direction_norm"] == pytest.approx(8.0)


def test_a_model_that_answers_the_wrong_number_of_states_is_refused(package):
    probes, torch = package
    tok = _Tok()
    hf = _Model(torch, layers=3, dim=4, vector_of=lambda key: torch.ones(4))
    built = _built(torch, tok, 4, 4)     # the config says 4 layers, the model answers 3+1
    with pytest.raises(RuntimeError, match="answered 4 hidden states, its config names 5"):
        probes.concept_direction(built, hf, torch.device("cpu"), [{"positive": "a", "negative": "b"}], None)


def test_the_option_scores_are_log_probabilities_of_the_options_first_tokens(package, monkeypatch):
    probes, torch = package
    tok = _Tok()

    def logits_of(key):
        row = torch.full((1000,), -10.0)
        row[362] = 2.0
        row[425] = 1.0
        return row
    hf = _Model(torch, layers=2, dim=4, vector_of=lambda key: torch.ones(4), logits_of=logits_of)
    built = _built(torch, tok, 2, 4)
    built.module.hf = hf
    monkeypatch.setattr(probes, "get_built", lambda dir_name: built)
    monkeypatch.setattr(probes, "_kv_cache_bytes", lambda config, tokens: 0)
    monkeypatch.setattr(probes, "_on_card", lambda built, reserve: torch.device("cpu"))
    out = probes.option_scores("x", ["p one", "p two"], [" A", " B"])
    assert out["option_ids"] == [362, 425]
    lp = torch.log_softmax(logits_of(None), dim=-1)
    assert out["scores"] == [[pytest.approx(float(lp[362])), pytest.approx(float(lp[425]))]] * 2
    with pytest.raises(ValueError):
        probes.option_scores("x", [], [" A"])


def test_the_stopper_closes_at_a_sentence_end_after_the_soft_count_and_on_a_loop(package):
    probes, torch = package

    class _T:
        def decode(self, ids, skip_special_tokens=True):
            return "".join(chr(int(i)) for i in ids)

    stop = probes._Stopper(_T(), prompt_len=0, soft_tokens=3)
    ids = torch.tensor([[ord("a"), ord("b")]])
    assert not stop(ids, None).item()
    ids = torch.tensor([[ord("a"), ord("b"), ord("c"), ord(".")]])
    assert stop(ids, None).item() and stop.reason == "sentence"
    loop = probes._Stopper(_T(), prompt_len=0, soft_tokens=None)
    text = "The same sentence again. " * 12
    ids = torch.tensor([[ord(c) for c in text]])
    assert loop(ids, None).item() and loop.reason == "repetition"


def test_the_package_names_no_model_and_registers_the_two_nodes():
    init = (PACKAGE / "__init__.py").read_text(encoding="utf-8")
    assert '"ai4artsed_llm_option_scores": ai4artsed_llm_option_scores' in init
    assert '"ai4artsed_llm_rep_engineering": ai4artsed_llm_rep_engineering' in init
    from my_app.services import text_presets
    orgs = {m["id"].split("/")[0].lower() for row in text_presets.scenarios().values() for m in row.values()}
    for f in ("_text_probes.py", "ai4artsed_text_probes.py"):
        text = (PACKAGE / f).read_text(encoding="utf-8").lower()
        for org in orgs:
            assert org not in text, (f, org)


def test_a_member_the_loader_runs_nowhere_is_held_back_and_refused(probes, monkeypatch):
    """The table's trust_remote_code member: on its row with the reason, in
    no picker's `presets` even when its weights are there, and refused with
    a 422 before the node."""
    from my_app.services import text_presets, winobias_corpus
    monkeypatch.setattr(winobias_corpus, "kids_pool", lambda: [_pair("p1")])
    monkeypatch.setattr(winobias_corpus, "pool", lambda: [])
    node = _Node({})
    monkeypatch.setattr(probes, "_run_node", node)
    monkeypatch.setattr(text_presets, "is_installed", lambda model_id: True)
    out = probes.bias_probe(HELD, ["p1"])
    assert out["http_status"] == 422 and "trust_remote_code" in out["error"] and node.calls == []
    monkeypatch.setattr(text_presets, "_card_gb", lambda: 96.0)
    rows = text_presets.scenarios()
    seen = 0
    for scenario, row in rows.items():
        listed = text_presets.listing(scenario)
        for key, member in row.items():
            if member["id"] != HELD:
                continue
            seen += 1
            assert key not in listed["presets"]
            assert listed["missing"][key]["installed"] and "trust_remote_code" in listed["missing"][key]["held_back"]
    assert seen >= 1


def test_a_run_that_does_not_come_back_clears_the_dispatch_note(probes, monkeypatch):
    from my_app.services import winobias_corpus
    monkeypatch.setattr(winobias_corpus, "kids_pool", lambda: [_pair("p1")])
    monkeypatch.setattr(winobias_corpus, "pool", lambda: [])
    said = []
    monkeypatch.setattr(probes, "note_dispatch", lambda model, local=False: said.append(model))

    def broken(class_type, inputs, workload=None):
        raise RuntimeError("gone")
    monkeypatch.setattr(probes, "_run_node", broken)
    assert probes.bias_probe(MEMBER, ["p1"])["http_status"] == 502
    assert said == [MEMBER, None]


def test_a_number_that_cannot_be_read_is_refused_before_the_dispatch(probes, monkeypatch):
    said = []
    monkeypatch.setattr(probes, "note_dispatch", lambda model, local=False: said.append(model))
    node = _Node({})
    monkeypatch.setattr(probes, "_run_node", node)
    out = probes.rep_engineering([{"positive": "a", "negative": "b"}], MEMBER, target_layer="middle")
    assert out["http_status"] == 400 and "could not be read" in out["error"]
    out = probes.rep_engineering([{"positive": "a", "negative": "b"}], MEMBER, test_text="t", alphas=["x"])
    assert out["http_status"] == 400
    assert node.calls == [] and said == []


def test_the_row_is_refused_while_the_card_cannot_be_read(monkeypatch):
    from my_app.services import text_presets
    from my_app.services.gpu_card import CardUnreadable

    def unreadable():
        raise CardUnreadable("ComfyUI answered no system_stats")
    monkeypatch.setattr(text_presets, "_card_gb", unreadable)
    with pytest.raises(CardUnreadable):
        text_presets.listing(next(iter(text_presets.scenarios())))
    from flask import Flask
    from my_app.routes.text_routes import text_bp
    app = Flask(__name__)
    app.register_blueprint(text_bp)
    with app.test_client() as c:
        answer = c.get("/api/text/presets")
    assert answer.status_code == 503 and "system_stats" in answer.get_json()["error"]


def test_two_options_that_share_a_first_token_are_said_before_the_card(package, monkeypatch):
    probes, torch = package

    class _Merged(_Tok):
        letters = {" A": 7, " B": 7}
    built = _built(torch, _Merged(), 2, 4)
    built.module.hf = _Model(torch, layers=2, dim=4, vector_of=lambda key: torch.ones(4))
    monkeypatch.setattr(probes, "get_built", lambda dir_name: built)
    monkeypatch.setattr(probes, "_kv_cache_bytes", lambda config, tokens: 0)

    def never(built, reserve):
        raise AssertionError("the card was asked for a reading that was refused")
    monkeypatch.setattr(probes, "_on_card", never)
    assert probes.option_scores("x", ["p one"], [" A", " B"]) == {"option_ids": [7, 7], "scores": []}
    with pytest.raises(ValueError, match="empty"):
        probes.option_scores("x", ["p one", "   "], [" A", " B"])


def test_the_stopper_is_the_loaders_stop_with_the_surfaces_rules_on_top(package, monkeypatch):
    probes, torch = package
    loader = sys.modules["ai4artsed_comfyui._local_llm"]
    stop = probes._Stopper(_Tok(), prompt_len=1, soft_tokens=None)
    assert isinstance(stop, loader._Stop)
    ids = torch.tensor([[1, 2, 3]])
    assert not stop(ids, None).item() and stop.generated == 2
    monkeypatch.setattr(sys.modules["comfy.model_management"], "processing_interrupted", lambda: True)
    assert stop(ids, None).item() and stop.interrupted and stop.reason is None


def test_steered_runs_every_strength_off_one_seed_and_hangs_no_hook_at_zero(package):
    probes, torch = package
    seen = []

    class _HF(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.p = torch.nn.Parameter(torch.zeros(1))
            self.model = types.SimpleNamespace(layers=torch.nn.ModuleList([torch.nn.Identity() for _ in range(3)]))

        def generate(self, input_ids, attention_mask=None, **kw):
            seen.append({"seed": torch.initial_seed(), "hooks": len(self.model.layers[1]._forward_hooks),
                         "max_new_tokens": kw["max_new_tokens"]})
            new = torch.zeros((1, kw["max_new_tokens"] if len(seen) < 3 else 1), dtype=input_ids.dtype)
            return torch.cat([input_ids, new], dim=1)

    hf = _HF()
    built = _built(torch, _Tok(), 3, 4)
    out = probes.steered(built, hf, torch.device("cpu"), "p one", torch.ones(4), layer_idx=2,
                         alphas=[0.0, 1.5, -1.5], max_new_tokens=2, temperature=0.0, seed=11)
    assert [g["alpha"] for g in out] == [0.0, 1.5, -1.5]
    assert len({s["seed"] for s in seen}) == 1 and [s["max_new_tokens"] for s in seen] == [2, 2, 2]
    assert [s["hooks"] for s in seen] == [0, 1, 1] and not hf.model.layers[1]._forward_hooks
    assert [g["new_tokens"] for g in out] == [2, 2, 1]
    assert [g["stopped_by"] for g in out] == ["length", "length", "end"]
    with pytest.raises(RuntimeError, match="no decoder layer"):
        probes.steered(built, hf, torch.device("cpu"), "p one", torch.ones(4), layer_idx=0,
                       alphas=[0.0], max_new_tokens=2, temperature=0.0, seed=11)


def test_the_nodes_read_their_inputs_and_refuse_what_is_no_list(package, monkeypatch):
    probes, torch = package
    node = load_module("ai4artsed_comfyui.ai4artsed_text_probes", PACKAGE / "ai4artsed_text_probes.py", register=True)
    asked = []
    monkeypatch.setattr(node, "option_scores",
                        lambda d, p, o: asked.append(("scores", d, p, o)) or {"option_ids": [1, 2], "scores": [[0.0, -1.0]]})
    monkeypatch.setattr(node, "rep_engineering",
                        lambda d, pairs, **kw: asked.append(("rep", d, pairs, kw)) or {"target_layer": 1})
    scores = node.ai4artsed_llm_option_scores()
    out = scores.run("x", json.dumps(["p"]), json.dumps([" A", " B"]))
    assert json.loads(out["result"][0]) == {"option_ids": [1, 2], "scores": [[0.0, -1.0]]}
    assert out["ui"]["result"] == [out["result"][0]] and asked[-1] == ("scores", "x", ["p"], [" A", " B"])
    with pytest.raises(ValueError, match="JSON list"):
        scores.run("x", "not json", "[]")
    with pytest.raises(ValueError, match="string"):
        scores.run("x", json.dumps([1]), json.dumps([" A"]))
    rep = node.ai4artsed_llm_rep_engineering()
    rep.run("x", json.dumps([{"positive": "a", "negative": "b"}]), 5, test_text="  ", alphas="",
            target_layer="", temperature=0.5, max_new_tokens=0)
    assert asked[-1] == ("rep", "x", [{"positive": "a", "negative": "b"}],
                         {"target_layer": None, "test_text": None, "alphas": [], "max_new_tokens": None,
                          "temperature": 0.5, "seed": 5})
    rep.run("x", "[]", 0, test_text="t", alphas="[0, 2]", target_layer="-1", temperature=0.7, max_new_tokens=8)
    assert asked[-1][3] == {"target_layer": -1, "test_text": "t", "alphas": [0.0, 2.0], "max_new_tokens": 8,
                            "temperature": 0.7, "seed": 0}
    with pytest.raises(ValueError, match="whole number"):
        rep.run("x", "[]", 0, target_layer="middle")
    with pytest.raises(ValueError, match="number"):
        rep.run("x", "[]", 0, alphas='["x"]')


def test_a_model_that_caps_its_attention_logits_is_built_eager(package, monkeypatch, tmp_path):
    """transformers' sdpa attention drops attn_logit_softcapping; the loader
    asks for the eager one where the config carries the cap."""
    probes, torch = package
    loader = sys.modules["ai4artsed_comfyui._local_llm"]
    from transformers import AutoModelForCausalLM, AutoTokenizer
    asked = []

    def fake_model(path, **kw):
        asked.append(kw)
        return types.SimpleNamespace(generation_config=types.SimpleNamespace(eos_token_id=0),
                                     eval=lambda: None)

    def fake_tokenizer(path):
        return types.SimpleNamespace(eos_token_id=0, decode=lambda ids: "")
    # Patched on the classes themselves: the lazy transformers module hands
    # out its own class again once a sibling name has been imported.
    monkeypatch.setattr(AutoModelForCausalLM, "from_pretrained", staticmethod(fake_model))
    monkeypatch.setattr(AutoTokenizer, "from_pretrained", staticmethod(fake_tokenizer))
    monkeypatch.setattr(loader, "weights_path", lambda d: str(tmp_path))
    monkeypatch.setattr(loader, "_missing_requirements", lambda p: [])
    monkeypatch.setattr(loader, "_weight_bytes", lambda p: 0)
    capped = types.SimpleNamespace(model_type="g", attn_logit_softcapping=50.0)
    plain = types.SimpleNamespace(model_type="q", attn_logit_softcapping=None)
    monkeypatch.setattr(loader, "_read_config", lambda p: capped)
    loader._build("x")
    monkeypatch.setattr(loader, "_read_config", lambda p: plain)
    loader._build("y")
    assert asked[0]["attn_implementation"] == "eager" and "attn_implementation" not in asked[1]
    nested = types.SimpleNamespace(text_config=types.SimpleNamespace(attn_logit_softcapping=30.0))
    assert loader._softcapped(nested) and not loader._softcapped(plain)
