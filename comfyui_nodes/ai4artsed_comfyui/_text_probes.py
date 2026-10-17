"""The readings of the Latent Text Lab, on a local model ComfyUI holds.

Stage 5 of the move to ComfyUI. Two readings of a model
live here:

  * option_scores: after each of a list of prompts, the log-probability of
    the next token being each of a few answer options. The coreference
    contrast (WinoBias) and the BBQ questions are prompts of this kind; the
    DevServer builds them, every order of the options included, and does the
    arithmetic over the numbers this returns.

  * concept_direction and steered: Representation Engineering (Zou et al.
    2023). The axis that contrast pairs share in the activations of one
    layer, read at the last token, and generations with that axis added at
    that layer, one per strength, all off one reading and one seed.

The model is the one _local_llm builds (get_built) and ComfyUI puts on the
card for the call (_on_card), the same way an answer is
generated. Nothing here knows a model name or a corpus: the folder name and
the texts come from the caller.
"""
import inspect
import logging
from typing import Any, Dict, List, Optional

import torch
from transformers import StoppingCriteriaList

import comfy.model_management

from ._local_llm import Built, _Stop, _kv_cache_bytes, _on_card, get_built
from ._repetition_guard import RepetitionGuard

logger = logging.getLogger(__name__)

# The guard that works BEFORE a text turns into a loop: it lowers the odds of
# a token that has just been used. The loop guard below counts finished
# sentences, and a steered model at high strength writes "and the, and the,
# and the" -- no full stop, so nothing is ever counted. 1.1 is the mild
# setting: a factual continuation keeps its repeated phrasing, a fragment
# loop stops being the most probable next thing (measured 2026-08-25 on the
# Text Lab's 4B model at strength 3: capped at 50 tokens the row took 21 s,
# uncapped with the loop guard alone it was still running after ten minutes).
DEFAULT_REPETITION_PENALTY = 1.1

# The Representation Engineering surface is the ONE place on this platform that
# runs a generation under a hard length limit. It is the one exception to the
# platform's ban on hard output limits, and the
# reason is in the first two paragraphs of the paper this surface implements
# (Zou et al. 2023, arXiv:2310.01405): the unit of analysis is the
# representational space - the pattern of activity across a population of
# neurons - and everything below that unit is abstracted away. The text a cell
# shows is the READOUT of a shift in that space. Its length carries none of the
# finding, and the paper's own control examples are a few sentences long.
#
# Two numbers, because a bare cap is what broke this surface once already: the
# run closes at the first sentence end after SOFT, so a cell always holds
# finished sentences instead of a word torn in half, and HARD ends the run that
# writes a single sentence forever.
#
# This exception covers this surface alone. Everywhere else on the platform the
# ban on hard output limits stands unchanged.
REPENG_SOFT_TOKENS = 160
REPENG_HARD_TOKENS = 256

_SENTENCE_END = tuple('.!?。！？')


def _closes_a_sentence(piece: str) -> bool:
    tail = piece.rstrip()
    return bool(tail) and tail.endswith(_SENTENCE_END)


def _encode(built: Built, text: str, device) -> Dict[str, Any]:
    enc = built.tokenizer(text, return_tensors="pt")
    return {k: (v.to(device) if hasattr(v, "to") else v) for k, v in enc.items()}


def _interrupted() -> None:
    """ComfyUI's own way of ending a run, asked between two passes."""
    comfy.model_management.throw_exception_if_processing_interrupted()


def _layers_in(config: Any) -> int:
    """The decoder layers the config announces; a vision model keeps them in
    its text config."""
    for c in (config, getattr(config, "text_config", None)):
        n = getattr(c, "num_hidden_layers", None)
        if isinstance(n, int) and n > 0:
            return n
    raise ValueError(f"{type(config).__name__} names no num_hidden_layers")


def _heal_capture(model: torch.nn.Module) -> int:
    """Put back any `forward` transformers left overwritten.

    `check_model_inputs` (transformers/utils/generic.py) overwrites
    `module.forward` on every recordable module while it collects hidden
    states and puts the original back AFTER the call, outside a `finally`.
    An exception in the forward pass -- an out-of-memory above all -- leaves
    all of them overwritten, and every later call then appends its
    activations into a collection nobody reads (measured at roughly 60 MB
    per call on the Text Lab's 4B model, held until the model is dropped).

    A left-over wrapper is a plain function; a `forward` that was put back is
    a bound method. Dropping the instance attribute uncovers the class
    method, which is what the module carried before anybody touched it.
    """
    healed = 0
    for module in model.modules():
        found = module.__dict__.get("forward")
        if found is not None and not inspect.ismethod(found):
            del module.__dict__["forward"]
            healed += 1
    return healed


# ---------------------------------------------------------------------------
# Option scores

def option_scores(dir_name: str, prompts: List[str], options: List[str]) -> Dict[str, Any]:
    """After each prompt, the log-probability of each option's FIRST token
    as the next token.

    Returns {"option_ids": [id per option], "scores": [[per option] per
    prompt]}. Two options that begin with the same token cannot be told
    apart by this reading: the ids come back alone then, with no score and
    before anything goes on the card, and the caller refuses the model
    (the coreference probe and the BBQ probe both do, with a 422).
    """
    if not prompts:
        raise ValueError("option_scores takes at least one prompt")
    if not options:
        raise ValueError("option_scores takes at least one option")
    for i, prompt in enumerate(prompts):
        if not prompt.strip():
            raise ValueError(f"prompt {i} is empty; every prompt has to carry text")
    built = get_built(dir_name)
    with built.lock:
        ids = []
        for option in options:
            toks = built.tokenizer(option, add_special_tokens=False).input_ids
            if not toks:
                raise ValueError(f"the option {option!r} tokenizes to nothing")
            ids.append(int(toks[0]))
        if len(set(ids)) < len(ids):
            return {"option_ids": ids, "scores": []}
        longest = max(len(built.tokenizer(p).input_ids) for p in prompts)
        reserve = _kv_cache_bytes(built.config, max(longest, 1024))
        device = _on_card(built, reserve)
        hf = built.module.hf
        # Only the last position's logits are read; a model whose forward
        # takes logits_to_keep computes only those (a vocabulary of 150k
        # times the prompt's length otherwise).
        keep = {"logits_to_keep": 1} if "logits_to_keep" in inspect.signature(hf.forward).parameters else {}
        rows = []
        with torch.inference_mode():
            for prompt in prompts:
                _interrupted()
                enc = _encode(built, prompt, device)
                logits = hf(**enc, **keep).logits[0, -1].float()
                lp = torch.log_softmax(logits, dim=-1)
                rows.append([float(lp[i]) for i in ids])
    return {"option_ids": ids, "scores": rows}


# ---------------------------------------------------------------------------
# Representation Engineering (Zou et al. 2023)

def _decoder_layers(model: torch.nn.Module) -> Optional[List[torch.nn.Module]]:
    """The decoder stack, for the architectures the Text Lab runs."""
    inner = getattr(model, "model", None)
    if inner is not None and hasattr(inner, "layers"):
        return list(inner.layers)
    transformer = getattr(model, "transformer", None)
    if transformer is not None and hasattr(transformer, "h"):
        return list(transformer.h)
    if transformer is not None and hasattr(transformer, "layers"):
        return list(transformer.layers)
    return None


def _hidden_states(built: Built, hf: torch.nn.Module, enc: Dict[str, Any]):
    """The hidden states of one forward pass, counted against the config.

    N decoder layers give N+1 states ([0] is the embedding). Any other
    count means the model was not read whole -- on the old service, seven
    concurrent runs once answered 35, 15, 59 states where 37 was the number,
    for six months without an error -- and the reading is refused.
    """
    keep = {"logits_to_keep": 1} if "logits_to_keep" in inspect.signature(hf.forward).parameters else {}
    out = hf(**enc, output_hidden_states=True, **keep)
    states = out.hidden_states
    expected = _layers_in(built.config) + 1
    if states is None or len(states) != expected:
        raise RuntimeError(
            f"{built.dir_name} answered {0 if states is None else len(states)} hidden states, "
            f"its config names {expected}")
    return states


def concept_direction(built: Built, hf: torch.nn.Module, device,
                      contrast_pairs: List[Dict[str, str]],
                      target_layer: Optional[int]) -> Dict[str, Any]:
    """Read a concept as a direction in activation space (Zou et al. 2023).

    The two sides of a contrast pair differ in one respect, so the difference
    of their activations at the last token points along that respect.
    Normalized, so that a long pair does not outweigh a short one, the first
    principal component of those differences is what the pairs have in
    common: the direction.

    target_layer None reads in the middle of the stack, where Zou et al.
    read: the last layer is already committed to the next token. -1 is the
    last layer; other values index the hidden states directly.
    """
    differences, positives, negatives = [], [], []
    num_layers = _layers_in(built.config) + 1
    if target_layer is None:
        layer_idx = num_layers // 2
    else:
        layer_idx = target_layer if target_layer >= 0 else num_layers + target_layer
    layer_idx = max(0, min(layer_idx, num_layers - 1))

    with torch.inference_mode():
        for pair in contrast_pairs:
            _interrupted()
            pos = _hidden_states(built, hf, _encode(built, pair["positive"], device))
            neg = _hidden_states(built, hf, _encode(built, pair["negative"], device))
            # Read at the last token, the LAT position for decoder models
            # (Zou et al. 2023, C.1). Averaging over the whole sequence puts
            # the words the two sides do not share into the difference, and
            # they outweigh what the pairs are about: over ten held-out
            # true/false pairs the averaged axis placed 6-7 correctly, the
            # last-token axis 9 of 10 on a 1.7B model and 10 of 10 from 8B up.
            pos_hidden = pos[layer_idx][:, -1, :].float().squeeze(0)
            neg_hidden = neg[layer_idx][:, -1, :].float().squeeze(0)
            positives.append(pos_hidden)
            negatives.append(neg_hidden)
            differences.append(pos_hidden - neg_hidden)

    diff_matrix = torch.stack(differences)
    origin = (torch.stack(positives).mean(dim=0) + torch.stack(negatives).mean(dim=0)) / 2

    # How large an activation is at this layer of this model. Steering
    # strength is given as a share of it, because the same absolute push is
    # a nudge on one model and demolition on the next.
    activation_norm = float(torch.stack([h.norm() for h in positives + negatives]).mean())

    # The axis as Zou et al. (2023) build it in Appendix C.1: normalize each
    # pair difference, then take the first principal component of those
    # differences. C.1 pairs its stimuli unlabelled and in arbitrary order,
    # so +d and -d enter the cloud with equal right and its mean sits at
    # zero. Here the pairs ARE labelled (positive - negative), so that
    # symmetry is stated rather than drawn: the SVD runs UNCENTERED, which is
    # the same computation as feeding it every difference in both
    # orientations. Centering it instead subtracts exactly what the pairs
    # share and leaves the axis along which they differ from each other.
    eps = 1e-8
    unit_diffs = diff_matrix / diff_matrix.norm(dim=1, keepdim=True).clamp_min(eps)
    _u, S, Vh = torch.linalg.svd(unit_diffs, full_matrices=False)
    energy = float((S ** 2).sum())

    if energy < eps:
        # Both sides of every pair read identically. There is no axis to
        # find, and everything below would divide by zero.
        direction = torch.zeros_like(diff_matrix[0])
        explained_variance = 0.0
    else:
        direction = Vh[0]
        explained_variance = float(S[0] ** 2 / energy)
        # C.1 takes the component's sign from the labels; the SVD's own sign
        # is arbitrary. Positive means: towards the positive side of the pairs.
        if float(torch.dot(unit_diffs.mean(dim=0), direction)) < 0:
            direction = -direction

    # How far the pairs travel along that axis, in this layer's own units.
    # The axis is a unit vector; without this the steering hook would add a
    # push of length 1 to activations two orders of magnitude larger.
    direction_norm = torch.stack([torch.dot(d, direction).abs() for d in differences]).mean()
    direction_raw = direction_norm * direction

    # The plane the reading itself picks out: the first two right singular
    # vectors. The first axis is the steering direction, so a difference's x
    # is exactly what it contributes to the push and its y what stays behind;
    # `plane_share` says how much of the spread the projection keeps.
    if energy < eps or Vh.shape[0] < 2:
        second = torch.zeros_like(direction)
        plane_share = 0.0
    else:
        second = Vh[1]
        # Orthogonal to `direction` by construction, and the sign of a
        # singular vector is arbitrary; laying it on the first pair keeps the
        # picture from mirroring between two runs of the same pairs.
        if float(torch.dot(unit_diffs[0], second)) < 0:
            second = -second
        plane_share = float((S[0] ** 2 + S[1] ** 2) / energy)

    # How far the single pairs agree with that axis: 1.0 = all pull the same
    # way, around 0 = the pairs have no common direction.
    agreements = [torch.nn.functional.cosine_similarity(d, direction, dim=0).item()
                  for d in differences]
    pair_agreement = sum(agreements) / len(agreements)

    pair_projections = []
    for i, pair in enumerate(contrast_pairs):
        pair_projections.append({
            "positive": pair["positive"],
            "negative": pair["negative"],
            "projection": torch.dot(differences[i], direction).item(),
            "agreement": agreements[i],
            # Where this difference sits in the plane, as a unit vector: the
            # drawing wants a direction, and the lengths differ by orders of
            # magnitude between layers.
            "plane_x": float(torch.dot(unit_diffs[i], direction)) if energy >= eps else 0.0,
            "plane_y": float(torch.dot(unit_diffs[i], second)) if energy >= eps else 0.0,
            # Measured from the midpoint of the pairs, so the two sides come
            # out symmetric around zero. This scale belongs to the pairs.
            "positive_projection": torch.dot(positives[i] - origin, direction).item(),
            "negative_projection": torch.dot(negatives[i] - origin, direction).item(),
        })

    return {
        "activation_norm": activation_norm,
        "direction": direction,
        "direction_raw": direction_raw,
        "direction_norm": float(direction_norm),
        "pair_agreement": pair_agreement,
        "explained_variance": explained_variance,
        "plane_share": plane_share,
        "layer_idx": layer_idx,
        "num_layers": num_layers,
        "pair_projections": pair_projections,
    }


class _Stopper(_Stop):
    """The loader's stop (_Stop: ComfyUI was told to interrupt) with the
    surface's two rules on top: the answer began to loop, or it is past SOFT
    tokens and the piece just written closes a sentence."""

    def __init__(self, tokenizer, prompt_len: int, soft_tokens: Optional[int]):
        super().__init__(prompt_len)
        self.tokenizer = tokenizer
        self.soft_tokens = soft_tokens
        self.guard = RepetitionGuard()
        self.seen = 0
        self.reason: Optional[str] = None

    def __call__(self, input_ids, scores, **kwargs):
        done = bool(super().__call__(input_ids, scores, **kwargs)[0])
        fresh = input_ids[0][self.prompt_len + self.seen:]
        if fresh.numel() > 0:
            self.seen += int(fresh.numel())
            piece = self.tokenizer.decode(fresh, skip_special_tokens=True)
            if self.soft_tokens and self.seen >= self.soft_tokens and _closes_a_sentence(piece):
                self.reason = self.reason or "sentence"
                done = True
            if self.guard.feed(piece):
                self.reason = self.reason or "repetition"
                done = True
        return torch.full((input_ids.shape[0],), done, dtype=torch.bool, device=input_ids.device)


def steered(built: Built, hf: torch.nn.Module, device, text: str,
            direction_raw: torch.Tensor, layer_idx: int, alphas: List[float],
            max_new_tokens: Optional[int], temperature: float, seed: int) -> List[Dict[str, Any]]:
    """One generation per strength, all off one reading and one seed.

    The same seed for all of them: two cells side by side then differ in
    the strength and in nothing else -- without that, a difference could
    always have been the draw. Strength 0 hangs no hook and is the untouched
    run.
    """
    enc = _encode(built, text, device)
    prompt_len = int(enc["input_ids"].shape[1])
    model_dtype = next(hf.parameters()).dtype
    dir_vec = direction_raw.to(device=device, dtype=model_dtype).unsqueeze(0).unsqueeze(0)
    decoder_layers = _decoder_layers(hf)
    # hidden_states has N+1 entries ([0] = embedding), decoder_layers has N:
    # hidden_states[layer_idx] is the output of decoder_layers[layer_idx - 1].
    hook_layer_idx = layer_idx - 1
    if not decoder_layers or not (0 <= hook_layer_idx < len(decoder_layers)):
        raise RuntimeError(
            f"{built.dir_name}: no decoder layer for hidden state {layer_idx} "
            f"({'no decoder stack found' if not decoder_layers else f'{len(decoder_layers)} layers'})")
    hard = max_new_tokens if max_new_tokens and max_new_tokens > 0 else REPENG_HARD_TOKENS
    pad = built.tokenizer.pad_token_id if built.tokenizer.pad_token_id is not None else built.tokenizer.eos_token_id

    def make_hook(strength: float):
        def hook_fn(module, module_input, output):
            if isinstance(output, tuple):
                return (output[0] + strength * dir_vec,) + output[1:]
            return output + strength * dir_vec
        return hook_fn

    generations = []
    for strength in alphas:
        _interrupted()
        handle = None
        if strength != 0:
            handle = decoder_layers[hook_layer_idx].register_forward_hook(make_hook(float(strength)))
        stop = _Stopper(built.tokenizer, prompt_len, REPENG_SOFT_TOKENS)
        try:
            gen_kwargs: Dict[str, Any] = dict(
                max_new_tokens=hard,
                do_sample=temperature > 0,
                repetition_penalty=DEFAULT_REPETITION_PENALTY,
                pad_token_id=pad,
                stopping_criteria=StoppingCriteriaList([stop]),
            )
            if temperature > 0:
                gen_kwargs["temperature"] = float(temperature)
            torch.manual_seed(int(seed))
            with torch.inference_mode():
                out = hf.generate(enc["input_ids"], attention_mask=enc.get("attention_mask"),
                                  **gen_kwargs)
        finally:
            if handle is not None:
                handle.remove()
        if stop.interrupted:
            _interrupted()
        generations.append({
            "alpha": float(strength),
            "text": built.tokenizer.decode(out[0], skip_special_tokens=True),
            "new_tokens": int(out.shape[1]) - prompt_len,
            "stopped_by": stop.reason or ("length" if int(out.shape[1]) - prompt_len >= hard else "end"),
        })
    return generations


def rep_engineering(dir_name: str, contrast_pairs: List[Dict[str, str]],
                    target_layer: Optional[int] = None, test_text: Optional[str] = None,
                    alphas: Optional[List[float]] = None, max_new_tokens: Optional[int] = None,
                    temperature: float = 0.7, seed: int = 0) -> Dict[str, Any]:
    """The reading and, with a test text, the projection and the steered
    generations. Returns the numbers the Representation Engineering
    surface reads; the caller adds the model's name."""
    if not contrast_pairs:
        raise ValueError("rep_engineering takes at least one contrast pair")
    for pair in contrast_pairs:
        if not isinstance(pair, dict) or not pair.get("positive") or not pair.get("negative"):
            raise ValueError("every contrast pair carries a positive and a negative text")
    built = get_built(dir_name)
    with built.lock:
        longest = max(len(built.tokenizer(t).input_ids)
                      for pair in contrast_pairs for t in (pair["positive"], pair["negative"]))
        if test_text:
            longest = max(longest, len(built.tokenizer(test_text).input_ids)
                          + (max_new_tokens if max_new_tokens and max_new_tokens > 0 else REPENG_HARD_TOKENS))
        reserve = _kv_cache_bytes(built.config, max(longest, 1024))
        device = _on_card(built, reserve)
        hf = built.module.hf
        try:
            reading = concept_direction(built, hf, device, contrast_pairs, target_layer)
            result: Dict[str, Any] = {
                "target_layer": reading["layer_idx"],
                "num_layers": reading["num_layers"],
                "embedding_dim": int(reading["direction"].shape[0]),
                "num_pairs": len(contrast_pairs),
                "pair_agreement": reading["pair_agreement"],
                "explained_variance": reading["explained_variance"],
                "plane_share": reading["plane_share"],
                "direction_norm": reading["direction_norm"],
                "activation_norm": reading["activation_norm"],
                "pair_projections": reading["pair_projections"],
            }
            if test_text:
                with torch.inference_mode():
                    states = _hidden_states(built, hf, _encode(built, test_text, device))
                # Same reading position as the axis: a mean-pooled state
                # projected onto a last-token axis would be a number from
                # another space.
                test_hidden = states[reading["layer_idx"]][:, -1, :].float().squeeze(0)
                result["test_text"] = test_text
                result["test_projection"] = torch.dot(test_hidden, reading["direction"]).item()
                if alphas:
                    result["generations"] = steered(
                        built, hf, device, test_text, reading["direction_raw"],
                        reading["layer_idx"], [float(a) for a in alphas],
                        max_new_tokens, temperature, seed)
                    result["seed"] = int(seed)
        finally:
            healed = _heal_capture(hf)
            if healed:
                logger.warning(f"[AI4ArtsEd LLM] put back {healed} forward methods left "
                               f"overwritten on {dir_name}")
    return result
