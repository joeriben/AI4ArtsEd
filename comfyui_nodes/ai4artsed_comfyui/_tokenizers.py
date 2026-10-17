"""
Tokenizers — the cut, and nothing that needs a card.

The Latent Lab's language-comparison instrument shows one sentence cut into
tokens by several tokenizers at once. That needs no weights and no GPU: a
tokenizer is a vocabulary and a merge table, a few megabytes of JSON, and it
answers in milliseconds. Loading a model for it would take a VRAM slot and
several seconds to say what the JSON already knows. So this is answered on
ComfyUI's own HTTP server (`_tokenizer_routes.py`), off the queue: a prompt in
the queue would wait behind every picture being made.

Two things live here, kept apart:

  * the cut and the facts of a tokenizer the DevServer names (`tokenize`,
    `facts`): read from the Hugging Face cache of this machine, never from the
    network. WHICH tokenizers the instrument offers is the DevServer's table
    (devserver/config/tokenizer_catalogue.json); this package names no model;
  * the window count a run asks before it starts (`count_tokens`): how many
    tokens a text costs one of the encoders a picture graph reads with. Those
    tokenizers are ComfyUI's own — the vocabulary files it ships and its
    graphs cut with — so the count is the count of the graph that runs;
  * the rows of the conditioning table (`encoder_rows`): which piece of a
    text stands in which row at CLIP and at T5, for the Encoder Fusion
    surface, laid by instances of the tokenizer classes the graphs cut with
    (the graph's CLIP-G side pads with 0 where CLIP-L pads with its end
    token; the rows and their pieces are the same).

Every number this module reports is read from files on this machine: the
size of the vocabulary from the tokenizer, the width of the window and the
size of the embedding matrix from the model's config. Nothing is written down
here that could go stale when a model is updated.
"""

import logging
import os
import threading
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_tokenizers: Dict[str, Any] = {}
_facts: Dict[str, Dict[str, Any]] = {}


def _snapshot(repo_id: str) -> Optional[str]:
    """The directory this repository's files sit in on this machine, or None.

    Asked without reaching the network, and the DIRECTORY is what gets loaded
    from below: given a repository id, transformers asks the hub for the
    model's metadata even under `local_files_only` (and sends the account
    token with it); given a directory, it reads the files and stays here.
    """
    try:
        from huggingface_hub import try_to_load_from_cache
    except Exception:
        return None
    for name in ("tokenizer_config.json", "tokenizer.json", "vocab.json"):
        try:
            hit = try_to_load_from_cache(repo_id, name)
        except Exception:
            hit = None
        if isinstance(hit, str):
            return os.path.dirname(hit)
    return None


def _load(repo_id: str, snapshot: str):
    """The tokenizer, loaded once from its snapshot directory and kept."""
    with _lock:
        if repo_id in _tokenizers:
            return _tokenizers[repo_id]
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
    with _lock:
        _tokenizers[repo_id] = tok
    return tok


def _model_facts(repo_id: str, snapshot: str) -> Dict[str, Optional[int]]:
    """How wide the window is, and how many rows the embedding matrix has.

    Both come out of the model's `config.json`, which is a few kilobytes — no
    weights are touched. They are two different numbers and they are reported
    as two: a matrix is commonly padded to a multiple the kernels like, by a
    few hundred rows beyond what the tokenizer addresses, and no text ever
    produces one of them.
    """
    with _lock:
        if repo_id in _facts:
            return _facts[repo_id]
    window: Optional[int] = None
    matrix: Optional[int] = None
    try:
        from transformers import AutoConfig
        cfg = AutoConfig.from_pretrained(snapshot, local_files_only=True)
        # A picture model keeps the text side in a sub-config, and that is the
        # side whose window this instrument is about.
        text_cfg = getattr(cfg, "text_config", None) or cfg
        window = getattr(text_cfg, "max_position_embeddings", None)
        matrix = getattr(text_cfg, "vocab_size", None)
    except Exception as e:
        logger.info(f"[AI4ArtsEd tokenizers] no config for {repo_id}: {e}")
    facts = {"window": window, "matrix": matrix}
    with _lock:
        _facts[repo_id] = facts
    return facts


def facts(model_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """Which of these tokenizers this machine has, and their numbers.

    Presence is answered from the cache directory, not by loading: a list call
    that loads six tokenizers to say they exist takes seconds and warms nothing
    that the next call needs.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for repo_id in model_ids:
        snapshot = _snapshot(repo_id)
        row: Dict[str, Any] = {"available": snapshot is not None}
        if snapshot is not None:
            row.update(_model_facts(repo_id, snapshot))
        out[repo_id] = row
    return out


def tokenize(text: str, model_id: str) -> Dict[str, Any]:
    """One text, one tokenizer, the pieces it falls into.

    Without the chat template's control tokens: this is the cut of the sentence
    itself, and the count is the one the overview card's language comparison
    was measured with.

    Each piece is reported twice, because neither form is readable on its own
    for every tokenizer. `s` is the decoded text — what the piece says. `raw`
    is the literal entry in the vocabulary, with whatever the family marks a
    word boundary with (`Ġ` for byte-level BPE, `▁` for SentencePiece). The
    surface shows `s` and falls back to `raw`. `part` says that this piece
    shares its stretch of text with the one before it — it is the second (or
    third) piece of ONE character.

    An answer that carries `http_status` is a refusal, with the status the
    route is to answer with.
    """
    snapshot = _snapshot(model_id)
    if snapshot is None:
        return {"error": f"{model_id} is not on this machine.", "http_status": 404}

    try:
        tok = _load(model_id, snapshot)
    except Exception as e:
        logger.error(f"[AI4ArtsEd tokenizers] {model_id} did not load: {e}")
        return {"error": f"{model_id} did not load: {e}", "http_status": 500}

    try:
        ids = tok.encode(text, add_special_tokens=False)
        tokens = token_surfaces(tok, text, ids)
    except Exception as e:
        # A lone surrogate in the text, for one: the tokenizer refuses it with
        # a TypeError, and the refusal travels as JSON with its cause.
        logger.error(f"[AI4ArtsEd tokenizers] {model_id} could not cut the text: {e}")
        return {"error": f"{model_id} could not cut this text: {e}", "http_status": 500}

    model_facts = _model_facts(model_id, snapshot)
    return {
        "model_id": model_id,
        "tokens": tokens,
        "count": len(tokens),
        # The vocabulary the tokenizer can actually produce, added special
        # tokens included — not the number of rows in the embedding matrix.
        "vocab": len(tok),
        "matrix": model_facts.get("matrix"),
        "window": model_facts.get("window"),
    }


def token_surfaces(tok, text: str, ids, spans=None) -> List[Dict[str, Any]]:
    """The pieces behind `ids`, each in the two forms a surface needs.

    Decoding a single piece fails wherever a piece is HALF of a letter, and
    that is the normal case for Cyrillic, Hebrew, Arabic and Korean in a
    tokenizer built for English: CLIP needs two pieces for „Б" and returns
    nothing readable for either. The fast tokenizers say which stretch of the
    original text a piece covers, so where the decoding gives nothing or a
    replacement character, the piece is shown as that stretch — both halves of
    „Б" then read „Б", which is exactly what happened.

    `tok` is a tokenizer OBJECT, not a catalogue id. `spans` may be passed in
    where the caller has already asked for them.
    """
    raws = tok.convert_ids_to_tokens(ids)

    if spans is None:
        spans = []
        if getattr(tok, "is_fast", False):
            try:
                spans = tok(text, add_special_tokens=False,
                            return_offsets_mapping=True)["offset_mapping"]
            except Exception:
                spans = []

    tokens = []
    for i, tid in enumerate(ids):
        try:
            s = tok.decode([tid])
        except Exception:
            s = ""
        if (not s or "\ufffd" in s) and i < len(spans):
            a, b = spans[i]
            if b > a:
                s = text[a:b]
        # Two tokens that cover the same stretch of the text are two pieces of
        # ONE character, not the same character twice. Without this mark the
        # chip row reads „집 집 한 한" like repeated text, and the finding
        # itself (CLIP needs two tokens for a Korean character, for some
        # three) is lost in the repetition.
        part = bool(i > 0 and i < len(spans) and spans[i][0] < spans[i - 1][1])
        tokens.append({"s": s, "raw": raws[i] if i < len(raws) else "",
                       "id": int(tid), "part": part})

    return tokens


# ---------------------------------------------------------------------------
# The window count.

# The encoders a picture graph reads its prompt with, by the role a config
# declares (`prompt_window_tokenizer`), each answered by the tokenizer ComfyUI
# ships for it. CLIP-L and CLIP-G cut with the same vocabulary and merges: the
# two encoders differ in what they make of the pieces, not in the pieces.
_ENCODERS = ("clip_l", "clip_g", "t5")
_encoder_tokenizers: Dict[str, Any] = {}


def _encoder_tokenizer(encoder: str):
    with _lock:
        tok = _encoder_tokenizers.get(encoder)
    if tok is not None:
        return tok
    if encoder in ("clip_l", "clip_g"):
        from comfy import sd1_clip
        tok = sd1_clip.SDTokenizer().tokenizer
    elif encoder == "t5":
        from comfy.text_encoders import sd3_clip
        tok = sd3_clip.T5XXLTokenizer().tokenizer
    else:
        raise ValueError(f"encoder {encoder!r}: one of {', '.join(_ENCODERS)}")
    with _lock:
        _encoder_tokenizers[encoder] = tok
    return tok


def count_tokens(text: str, encoder: str) -> Dict[str, Any]:
    """How many tokens one text costs one encoder, start and end marks included.

    Measured with the tokenizer ComfyUI ships for the encoder, over the text
    as one piece: weight syntax such as `(word:1.3)` counts here as typed,
    where a graph strips it. Asked by the DevServer before a run of a config
    that declares a window (`prompt_window_tokens`); what a graph makes of a
    text beyond that window is the graph's own matter (CLIPTextEncode reads
    the text in stretches of 77 and drops nothing), and what the DevServer
    does with the count is decided there, per config.
    """
    try:
        tok = _encoder_tokenizer(encoder)
    except ValueError as e:
        return {"error": str(e), "http_status": 400}
    except Exception as e:
        logger.error(f"[AI4ArtsEd tokenizers] the {encoder} tokenizer did not load: {e}")
        return {"error": f"the {encoder} tokenizer did not load: {e}", "http_status": 500}
    try:
        ids = tok(text, padding=False, truncation=False)["input_ids"]
    except Exception as e:
        return {"error": f"{encoder} could not cut this text: {e}", "http_status": 500}
    return {"count": len(ids), "encoder": encoder}


# ---------------------------------------------------------------------------
# The rows of the conditioning table.

# The T5 block's length in the picture graphs, the default where a request
# names none; the DevServer sends its own (schemas/engine/comfyui_chunk_support
# T5_LENGTH), which is the one its graphs put on the T5TokenizerOptions node.
T5_ROWS_DEFAULT = 512

_row_tokenizers: Dict[str, Any] = {}


def _row_tokenizer(encoder: str):
    """ComfyUI's own tokenizer OBJECT for one encoder, the one its graphs cut
    with: `tokenize_with_weights` lays the rows the encoder reads, start and
    end marks, the window cut where ComfyUI cuts it, padding included. The HF
    tokenizer inside it (`_encoder_tokenizer`) knows the pieces and none of
    that."""
    with _lock:
        tok = _row_tokenizers.get(encoder)
    if tok is not None:
        return tok
    if encoder == "clip":
        from comfy import sd1_clip
        tok = sd1_clip.SDTokenizer()
    elif encoder == "t5":
        from comfy.text_encoders import sd3_clip
        tok = sd3_clip.T5XXLTokenizer()
    else:
        raise ValueError(f"encoder {encoder!r}: one of clip, t5")
    with _lock:
        _row_tokenizers[encoder] = tok
    return tok


def _unreadable(s: str) -> bool:
    return not s or "\ufffd" in s


def _rows_of(sd_tok, text: str, word_end: str = "", word_start: str = "",
             **options) -> Dict[str, Any]:
    """The rows one encoder fills with `text`, up to and including its end
    mark; what follows is padding to `block`. `cut` counts the pieces the
    window left out (CLIP's second chunk and on; T5 has no window).

    `part` says that a piece continues the word of the piece before it, read
    off the vocabulary's own boundary marks: CLIP closes a word with
    `word_end` (`</w>`), SentencePiece opens one with `word_start` (`▁`). The
    word ids `tokenize_with_weights` returns are no help here: they number the
    weighted segments of the prompt, and a plain prompt is one segment.

    A piece that decodes to nothing readable is part of a character (CLIP
    needs two for „Б"); a run of such pieces inside one word is decoded from
    its start, piece by piece: the pieces up to the first readable prefix make
    one character (or two, where a piece straddles them) and each of them reads
    as it, then the next pieces the same way, so that a word of seven letters
    in ten pieces shows its letters and not the word ten times. Where even that
    gives nothing, the vocabulary entry stands (`▁`, `<unk>`).
    """
    chunks = sd_tok.tokenize_with_weights(text, return_word_ids=True, **options)
    first = chunks[0] if chunks else []
    hf = sd_tok.tokenizer
    marks = {t for t in (sd_tok.start_token, sd_tok.end_token,
                         getattr(sd_tok, "pad_token", None)) if t is not None}
    rows: List[Dict[str, Any]] = []
    for index, (token, _weight, word) in enumerate(first):
        if sd_tok.start_token is not None and index == 0 and token == sd_tok.start_token:
            kind = "start"
        elif sd_tok.end_token is not None and token == sd_tok.end_token and word == 0:
            kind = "end"
        else:
            kind = "piece"
        raw = sd_tok.inv_vocab.get(token, "")
        if kind == "piece":
            try:
                s = hf.decode([token])
            except Exception:
                s = ""
        else:
            s = raw
        prev = rows[-1] if rows else None
        # A control mark written into the text (`<|endoftext|>` in the middle
        # of a prompt) is a piece here, and it carries no word-end mark: the
        # piece after it begins a word all the same.
        part = bool(
            kind == "piece" and prev is not None and prev["kind"] == "piece"
            and prev["id"] not in marks
            and ((word_end and not prev["raw"].endswith(word_end))
                 or (word_start and not raw.startswith(word_start)))
        )
        rows.append({"row": index, "kind": kind, "s": s, "raw": raw, "id": int(token),
                     "part": part})
        if kind == "end":
            break
    # runs of half characters, decoded together
    i = 0
    while i < len(rows):
        if rows[i]["kind"] == "piece" and rows[i]["id"] >= 0 and _unreadable(rows[i]["s"]):
            j = i
            # ... within one word: a run never crosses a word boundary, or
            # three Korean syllables would all read as the whole phrase.
            while (j + 1 < len(rows) and rows[j + 1]["kind"] == "piece"
                   and rows[j + 1]["id"] >= 0 and rows[j + 1]["part"]
                   and _unreadable(rows[j + 1]["s"])):
                j += 1
            start = i
            while start <= j:
                end, joint = start, ""
                while end <= j:
                    try:
                        joint = hf.decode([r["id"] for r in rows[start:end + 1]])
                    except Exception:
                        joint = ""
                    if not _unreadable(joint):
                        break
                    end += 1
                if end > j:
                    # nothing readable up to the end of the run
                    for r in rows[start:j + 1]:
                        r["s"] = r["raw"]
                    break
                for r in rows[start:end + 1]:
                    r["s"] = joint
                start = end + 1
            i = j + 1
        else:
            i += 1
    cut = sum(1 for chunk in chunks[1:] for _t, _w, word in chunk if word > 0)
    return {"rows": rows, "filled": len(rows), "block": len(first), "cut": cut}


def encoder_rows(text: str, t5_min_length: int = T5_ROWS_DEFAULT) -> Dict[str, Any]:
    """The rows of SD 3.5's conditioning table one text fills, per encoder.

    CLIP: row 0 is the start mark, then the pieces, then the end mark, then
    padding to 77; what does not fit the window is cut where ComfyUI cuts it
    and counted. CLIP-L and CLIP-G cut with the same vocabulary and merges, so
    one column stands for both. T5: the pieces, then `</s>`, then padding to
    the block's length, or longer where the text is. The length goes in as the
    tokenizer option the graph's T5TokenizerOptions node sets
    (`t5xxl_min_length`), which every ComfyUI since the option exists reads;
    the `min_length` keyword is younger (0.15.0) and older ones drop it. Weight syntax such as `(word:1.3)` is read the way the
    graph reads it. Asked by the Encoder Fusion surface on every change of the
    prompt, off the queue.
    """
    try:
        clip, t5 = _row_tokenizer("clip"), _row_tokenizer("t5")
    except Exception as e:
        logger.error(f"[AI4ArtsEd tokenizers] the encoder tokenizers did not load: {e}")
        return {"error": f"the encoder tokenizers did not load: {e}", "http_status": 500}
    try:
        return {
            "clip": _rows_of(clip, text, word_end="</w>"),
            "t5": _rows_of(t5, text, word_start="\u2581",
                           tokenizer_options={f"{t5.embedding_key}_min_length": int(t5_min_length)}),
        }
    except Exception as e:
        return {"error": f"the encoders could not cut this text: {e}", "http_status": 500}
