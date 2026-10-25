"""_translate_query: local utility model, /no_think idiom, fail-safe cache.

Regression for the silent 500: a provider-prefixed cloud model was fed into
the local-only llm_service client, so translation never worked and search ran
without the English query variant.
"""
from my_app.services import knowledge_library as KL


class _FakeLLM:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def _complete(self, model, prompt, **kw):
        self.calls.append((model, prompt))
        return self.reply


def test_translates_via_local_model_and_strips_think(monkeypatch):
    fake = _FakeLLM("<think>\n\n</think>\n\nEcological questions of AI in art courses")
    monkeypatch.setattr(KL, "_QUERY_TRANSLATION_CACHE", {})
    import my_app.services.llm_service as LS
    monkeypatch.setattr(LS, "llm_service", fake)
    import config
    monkeypatch.setattr(config, "KNOWLEDGE_QUERY_TRANSLATION_MODEL", "qwen3:4b", raising=False)

    out = KL._translate_query("ökologische Fragen der KI in Kunstkursen")
    assert out == "Ecological questions of AI in art courses"
    model, prompt = fake.calls[0]
    assert model == "qwen3:4b"
    assert prompt.startswith("/no_think ")

    # second call hits the in-process cache, no new LLM call
    out2 = KL._translate_query("ökologische Fragen der KI in Kunstkursen")
    assert out2 == out
    assert len(fake.calls) == 1


def test_failure_is_failsafe_and_cached(monkeypatch):
    fake = _FakeLLM(None)
    monkeypatch.setattr(KL, "_QUERY_TRANSLATION_CACHE", {})
    import my_app.services.llm_service as LS
    monkeypatch.setattr(LS, "llm_service", fake)

    assert KL._translate_query("noch eine Anfrage") is None
    assert KL._translate_query("noch eine Anfrage") is None
    assert len(fake.calls) == 1  # negative result cached, search proceeds
