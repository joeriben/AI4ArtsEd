"""The video reader's yes/no answer, without a model.

The check at the result asks the video reader one question about a video
(safety_gate.check_result_video): the classifier takes no video. The answer is
a task of the platform's node (comfyui_nodes/ai4artsed_comfyui/_media_reading.py,
score_video), and the DevServer takes it back through its media client
(services/media_analysis_client.score_video). These tests stand the model in
and show:

  * the answer is the share of yes in the mass of yes and no at the position
    after the prompt, each side summed over the spellings the vocabulary
    writes as one token;
  * a reader that would begin with anything but yes or no has not answered,
    and neither has one where neither side carries any mass;
  * the question goes to the reader as a system line, then the question, then
    the video, in one forward pass that keeps no cache; nothing is generated,
    so nothing is sampled;
  * the node hands the number back, and the client takes back a probability
    and nothing else.
"""
import math
import sys
import threading
import types
from types import SimpleNamespace

import pytest
from comfy_stubs import ModelPatcher

from file_modules import REPO, load_module

sys.path.insert(0, str(REPO / "devserver"))
PACKAGE = REPO / "comfyui_nodes" / "ai4artsed_comfyui"


# ---------------------------------------------------------------------------
# Package side

@pytest.fixture
def package(monkeypatch, tmp_path):
    """_media_reading and the node, with ComfyUI's modules stood in for.

    Every module is loaded afresh and taken out of sys.modules again after
    the test, so that no other test file finds these stand-ins."""
    torch = pytest.importorskip("torch")
    pytest.importorskip("transformers")
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
    monkeypatch.setenv("FORCE_QWENVL_VIDEO_READER", "torchvision")

    def load(name):
        monkeypatch.setitem(sys.modules, f"ai4artsed_comfyui.{name}", None)
        return load_module(f"ai4artsed_comfyui.{name}", PACKAGE / f"{name}.py", register=True)

    for name in ("_repetition_guard", "_snapshot", "_card", "_local_llm", "_whole", "_media_files"):
        load(name)
    reading = load("_media_reading")
    node = load("ai4artsed_media_reading")
    return SimpleNamespace(reading=reading, node=node, torch=torch)


# The spellings as a tokenizer might write them: the bare and the spaced word
# in lower and title case as one token, the capitals as two.
_ONE_TOKEN = {"yes": 5, "Yes": 6, " yes": 7, " Yes": 10,
              "no": 20, "No": 21, " no": 22, " No": 24}
VOCABULARY = 32
YES_IDS = [5, 6, 7, 10]
NO_IDS = [20, 21, 22, 24]


class _Tokenizer:
    def __init__(self, one_token=None):
        self.one_token = _ONE_TOKEN if one_token is None else one_token

    def __call__(self, text, add_special_tokens=False):
        if text in self.one_token:
            return SimpleNamespace(input_ids=[self.one_token[text]])
        return SimpleNamespace(input_ids=[30, 31])

    def decode(self, ids):
        names = {v: k for k, v in self.one_token.items()}
        return "".join(names.get(i, f"<{i}>") for i in ids)


def _logits(torch, **at):
    """A row of logits: -10 everywhere, and the values given by id."""
    row = torch.full((VOCABULARY,), -10.0)
    for key, value in at.items():
        row[int(key.lstrip("t"))] = value
    return row


def test_the_ids_of_the_spellings_that_are_one_token(package):
    read = package.reading
    assert read.answer_token_ids(_Tokenizer(), read.YES_SPELLINGS) == YES_IDS
    assert read.answer_token_ids(_Tokenizer(), read.NO_SPELLINGS) == NO_IDS


def test_the_share_of_yes_summed_over_its_spellings(package):
    torch = package.torch
    logits = _logits(torch, t5=2.0, t7=1.0, t20=1.5, t22=0.5)
    probs = torch.softmax(logits, dim=-1)
    yes = float(probs[5] + probs[7] + probs[6] + probs[10])
    no = float(probs[20] + probs[22] + probs[21] + probs[24])
    share = package.reading.yes_share(logits, YES_IDS, NO_IDS)
    assert share == pytest.approx(yes / (yes + no))
    # Taken at the larger spelling alone, the yes side would count less.
    assert share > float(probs[5]) / float(probs[5] + probs[20] + probs[22])


def test_a_no_reads_low(package):
    logits = _logits(package.torch, t5=0.0, t20=4.0)
    assert package.reading.yes_share(logits, YES_IDS, NO_IDS) < 0.05


def test_a_reader_that_would_begin_with_anything_else_has_not_answered(package):
    logits = _logits(package.torch, t5=1.0, t20=1.0, t3=6.0)
    with pytest.raises(ValueError, match="neither yes nor no"):
        package.reading.yes_share(logits, YES_IDS, NO_IDS, decode=_Tokenizer().decode)


def test_no_mass_on_either_side_is_no_answer(package):
    torch = package.torch
    logits = torch.full((VOCABULARY,), float("-inf"))
    with pytest.raises(ValueError, match="no answer"):
        package.reading.yes_share(logits, [0], [1])


class _Reader:
    """The video reader's model as score_video touches it: one call, logits
    over [batch, positions, vocabulary]. It must never generate."""

    def __init__(self, torch, last, keeps=True):
        self.torch = torch
        self.last = last
        self.calls = []
        if keeps:
            self.forward = self._forward_keeping
        else:
            self.forward = self._forward

    def _forward_keeping(self, input_ids=None, attention_mask=None, use_cache=None,
                         logits_to_keep=0, **kwargs):
        pass

    def _forward(self, input_ids=None, attention_mask=None, use_cache=None, **kwargs):
        pass

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        positions = 1 if kwargs.get("logits_to_keep") == 1 else 4
        logits = self.torch.zeros((1, positions, VOCABULARY))
        logits[0, -1] = self.last
        return SimpleNamespace(logits=logits)

    def generate(self, **kwargs):
        raise AssertionError("a yes/no question is read off one pass, never generated")


class _Inputs(dict):
    def to(self, device):
        self["moved_to"] = str(device)
        return self


@pytest.fixture
def reader(package, monkeypatch):
    """A built video reader and the preparation of its inputs, stood in."""
    torch, read = package.torch, package.reading
    seen = SimpleNamespace(messages=None, video=None, reserve=None, reader=None)
    built = SimpleNamespace(lock=threading.Lock(), tokenizer=_Tokenizer(),
                            config=SimpleNamespace(), module=SimpleNamespace(hf=None))

    def visual_inputs(b, messages, video):
        seen.messages, seen.video = messages, video
        return _Inputs(input_ids=torch.zeros((1, 9), dtype=torch.long),
                       attention_mask=torch.ones((1, 9), dtype=torch.long))

    def on_card(b, reserve):
        seen.reserve = reserve
        return torch.device("cpu")

    monkeypatch.setattr(read._local_llm, "get_built", lambda name: built)
    monkeypatch.setattr(read._local_llm, "_on_card", on_card)
    monkeypatch.setattr(read._local_llm, "_kv_cache_bytes", lambda config, tokens: tokens)
    monkeypatch.setattr(read, "_visual_inputs", visual_inputs)

    def with_model(model, tokenizer=None):
        built.module.hf = model
        if tokenizer is not None:
            built.tokenizer = tokenizer
        seen.reader = model
        return seen

    return with_model


def test_the_question_is_asked_in_one_pass(package, reader):
    torch, read = package.torch, package.reading
    last = _logits(torch, t6=3.0, t21=1.0)
    seen = reader(_Reader(torch, last))
    score = read.score_video("Qwen--Qwen3-VL-8B-Instruct", "/in/clip.mp4", "SYSTEM", "QUESTION")
    assert score == pytest.approx(read.yes_share(last, YES_IDS, NO_IDS))
    assert seen.messages == [
        {"role": "system", "content": [{"type": "text", "text": "SYSTEM"}]},
        {"role": "user", "content": [{"type": "text", "text": "QUESTION"},
                                     {"type": "video", "video": "file:///in/clip.mp4"}]},
    ]
    assert seen.video is True
    [call] = seen.reader.calls
    assert call["use_cache"] is False and call["logits_to_keep"] == 1
    assert call["moved_to"] == "cpu"
    # The room for the cache is the prompt's, since nothing follows the pass.
    assert seen.reserve == read.VIDEO_RESERVE_BYTES + 9


def test_the_same_video_gives_the_same_score(package, reader):
    torch, read = package.torch, package.reading
    reader(_Reader(torch, _logits(torch, t5=1.2, t20=1.0)))
    first = read.score_video("reader", "/in/clip.mp4", "SYSTEM", "QUESTION")
    assert read.score_video("reader", "/in/clip.mp4", "SYSTEM", "QUESTION") == first


def test_a_reader_without_logits_to_keep_is_read_at_its_last_position(package, reader):
    torch, read = package.torch, package.reading
    last = _logits(torch, t20=2.0, t5=0.0)
    seen = reader(_Reader(torch, last, keeps=False))
    score = read.score_video("reader", "/in/clip.mp4", "SYSTEM", "QUESTION")
    assert score == pytest.approx(read.yes_share(last, YES_IDS, NO_IDS))
    assert "logits_to_keep" not in seen.reader.calls[0]


def test_a_reader_that_does_not_answer_gives_no_score(package, reader):
    torch, read = package.torch, package.reading
    reader(_Reader(torch, _logits(torch, t3=5.0, t5=1.0, t20=1.0)))
    with pytest.raises(ValueError, match="neither yes nor no"):
        read.score_video("reader", "/in/clip.mp4", "SYSTEM", "QUESTION")


def test_a_reader_that_writes_no_answer_as_one_token_is_not_asked(package, reader):
    torch, read = package.torch, package.reading
    seen = reader(_Reader(torch, _logits(torch, t5=1.0)),
                  tokenizer=_Tokenizer({"no": 20, " no": 22}))
    with pytest.raises(ValueError, match="cannot answer"):
        read.score_video("reader", "/in/clip.mp4", "SYSTEM", "QUESTION")
    assert seen.reader.calls == [] and seen.messages is None


def test_the_node_hands_back_the_score(package, monkeypatch, tmp_path):
    clip = tmp_path / "ai4artsed_read_x.mp4"
    clip.write_bytes(b"a video")
    asked = []

    def score_video(model_name, path, system_prompt, prompt):
        asked.append((model_name, path, system_prompt, prompt))
        return 0.25

    monkeypatch.setattr(package.node._media_files, "input_path", lambda name: str(clip))
    monkeypatch.setattr(package.node._media_reading, "score_video", score_video)
    out = package.node.ai4artsed_media_reading().run(
        "video_check", "Qwen--Qwen3-VL-8B-Instruct", clip.name,
        prompt="QUESTION", system_prompt="SYSTEM")
    assert asked == [("Qwen--Qwen3-VL-8B-Instruct", str(clip), "SYSTEM", "QUESTION")]
    assert out["ui"]["score"] == [0.25]
    assert out["result"] == ("0.25",)
    assert "video_check" in package.node.TASKS


# ---------------------------------------------------------------------------
# DevServer side

@pytest.fixture
def client(monkeypatch):
    """The media client with its one way to the node stood in."""
    from my_app.services import media_analysis_client as mac
    reads = []
    answer = SimpleNamespace(out={"score": 0.0})

    def read(self, task, path, reader=None, **inputs):
        reads.append((task, path, reader, inputs))
        return answer.out

    monkeypatch.setattr(mac.MediaAnalysisClient, "_read", read)
    return SimpleNamespace(module=mac, reads=reads, answer=answer)


def test_the_question_goes_to_the_video_reader(client):
    client.answer.out = {"score": 0.125}
    score = client.module.MediaAnalysisClient().score_video("/runs/clip.mp4", "SYSTEM", "QUESTION")
    assert score == 0.125
    assert client.reads == [("video_check", "/runs/clip.mp4", "video",
                             {"system_prompt": "SYSTEM", "prompt": "QUESTION"})]


@pytest.mark.parametrize("value", [0, 0.0, 0.5, 1, 1.0])
def test_a_probability_comes_back(client, value):
    client.answer.out = {"score": value}
    score = client.module.MediaAnalysisClient().score_video("/runs/clip.mp4", "S", "Q")
    assert score == float(value) and isinstance(score, float)


@pytest.mark.parametrize("value", [True, False, "0.4", None, [0.4], -0.01, 1.01,
                                   math.nan, math.inf, 10 ** 400])
def test_anything_but_a_probability_is_no_verdict(client, value):
    client.answer.out = {"score": value}
    assert client.module.MediaAnalysisClient().score_video("/runs/clip.mp4", "S", "Q") is None
    assert client.module.last_reason() == "The video check sent back no probability."


def test_a_reading_that_failed_is_no_verdict(client):
    client.answer.out = None
    assert client.module.MediaAnalysisClient().score_video("/runs/clip.mp4", "S", "Q") is None


def test_the_reader_is_the_tables_video_reader(monkeypatch, tmp_path):
    """The client's own way: the table's reader for "video" answers the
    video_check task, and the file goes up and comes down again."""
    from my_app.services import llm_client, local_media_weights
    from my_app.services import media_analysis_client as mac
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"a video")
    asked, ran = [], []

    def reader_dir(task):
        asked.append(task)
        return "video_reader", "Qwen--Qwen3-VL-8B-Instruct"

    def run_node(cls, class_type, inputs, workload=None):
        ran.append((class_type, inputs))
        return {"score": 0.75}

    monkeypatch.setattr(local_media_weights, "reader_dir", reader_dir)
    monkeypatch.setattr(llm_client, "upload_input", lambda data, name: name)
    monkeypatch.setattr(llm_client.LLMClient, "run_node", classmethod(run_node))
    assert mac.MediaAnalysisClient().score_video(str(clip), "SYSTEM", "QUESTION") == 0.75
    assert asked == ["video"]
    [(class_type, inputs)] = ran
    assert class_type == mac.NODE_CLASS
    assert inputs["task"] == "video_check"
    assert inputs["model_name"] == "Qwen--Qwen3-VL-8B-Instruct"
    assert inputs["system_prompt"] == "SYSTEM" and inputs["prompt"] == "QUESTION"
    assert inputs["file"].startswith("ai4artsed_read_") and inputs["file"].endswith(".mp4")
