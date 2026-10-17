"""
AI4ArtsEd — Composable Diffusion (ComfyUI custom nodes)

ComfyUI port of gpu_service/services/diffusers_backend.py::generate_composable_diffusion,
the instrument's Diffusers original.

Each concept gets its own pass through the transformer at every denoising step, and the
predictions are composed in score space:

    eps = eps_u + sum_i v_i * (eps_i - eps_u)

Liu et al. (2022), "Compositional Visual Generation with Composable Diffusion Models",
Eq. 11; concept negation (Eq. 15) is the same expression with a negative v_i, because
eps_u + w*(eps_a - eps_b) == eps_u + w*(eps_a - eps_u) - w*(eps_b - eps_u).

The two parameterizations of the user-facing weights are the original's, unchanged:

    "mixture"     (normalize_weights, every w >= 0):  v_i = cfg * w_i / sum(w)
                  Total guidance stays at cfg; the weights are shares of it.
    "temperature" (otherwise):                        v_i = cfg * w_i
                  Each concept keeps its own strength; w < 0 means NOT.

A negative weight turns normalization off: a signed mixture has no meaning.

`combine_at` chooses the place the concepts are combined. Under "score" the sum above
runs at every step, one prediction per concept. Under "conditioning" the concepts'
conditionings are interpolated into one table before the run (see
`_combined_conditioning`), and the sampler makes an ordinary CFG run on it: the two
passes a single prompt takes at every step, one for that conditioning and one for the
negative. Seed, sigmas, sampler and scheduler are the same lines for both. What the
weights do differs with the place: under "score" each one scales the guidance of its
prediction, under "conditioning" only their RATIO acts, as the point between the
concepts that the interpolation reaches. NOT is the denoiser's operation alone: a
point between the concepts exists for weights of one sign, so under "conditioning"
a negative weight is refused instead of read as something else.

Why a guider and not `set_model_sampler_cfg_function`: that hook is handed ONE conditional
prediction and one unconditional one (comfy/samplers.py:387), and this instrument needs one
prediction per concept. `calc_cond_batch` (comfy/samplers.py:202) takes an arbitrary list of
conds and returns one output each, and `process_conds` (:784) already iterates over whatever
keys a guider puts in `self.conds` — so a CFGGuider subclass carries N concepts without
touching ComfyUI itself.
"""

import math

import comfy.model_management
import comfy.sample
import comfy.samplers
import comfy.utils
import latent_preview


class AI4ArtsEdConcept:
    """One weighted concept, chained into a list for the composing sampler."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "conditioning": ("CONDITIONING",),
                "weight": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0,
                                     "step": 0.05,
                                     "tooltip": "Share of the guidance under normalization, "
                                                "own strength without it. A negative weight "
                                                "subtracts the concept where combine_at is "
                                                "score (Eq. 15). Where it is conditioning and "
                                                "its sign differs from the others, the share "
                                                "leaves [0, 1] and the interpolation runs PAST "
                                                "the other concepts instead of between them."}),
            },
            "optional": {
                "concepts": ("AI4ARTSED_CONCEPTS",),
            },
        }

    RETURN_TYPES = ("AI4ARTSED_CONCEPTS",)
    FUNCTION = "add"
    CATEGORY = "AI4ArtsEd/latent lab"

    def add(self, conditioning, weight, concepts=None):
        chain = list(concepts or [])
        chain.append((conditioning, float(weight)))
        return (chain,)


def _read_weights(concepts, normalize_weights):
    """The weights as both places read them, and which of the two readings it was.

    A negative weight turns normalization off: a signed mixture has no meaning.
    """
    raw = [float(w) for _cond, w in concepts]
    if normalize_weights and any(w < 0 for w in raw):
        normalize_weights = False
    if normalize_weights:
        total = sum(raw)
        weights = [w / total for w in raw] if total > 0 else list(raw)
        return weights, "mixture"
    return list(raw), "temperature"


_SLERP = None


def _platform_slerp():
    """`slerp_tokens` from ai4artsed_sd3_conditioning.py, the ComfyUI side's
    spherical interpolation of two token tensors, taken rather than written a
    second time (Rule 13). The Diffusers backend holds the same arithmetic under
    the same name for its own path (gpu_service/services/diffusers_backend.py),
    on the other side of the process boundary.

    ComfyUI registers a node file under its own path as the module name
    (nodes.py, load_custom_node), so the sibling cannot be reached by a plain
    import. It is loaded once from the directory this file lies in: through the
    link in custom_nodes, realpath lands in the repository, where both files
    stand next to each other. That module holds constants and functions at
    import and nothing else, so reading it a second time costs its import.
    """
    global _SLERP
    if _SLERP is None:
        import importlib.util
        import os
        path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                            "ai4artsed_sd3_conditioning.py")
        spec = importlib.util.spec_from_file_location(
            "ai4artsed_sd3_conditioning_for_composable", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _SLERP = module.slerp_tokens
    return _SLERP


def _combined_conditioning(concepts, weights):
    """The concepts' conditionings as ONE, interpolated rather than added.

    A weighted sum shortens what it combines: two directions at half weight
    each give a vector shorter than either. It shortens exactly the positions
    the concepts differ in, because a conditioning is one row per token
    position and the encoders fill the positions past the text with padding.
    Two prompts of the same token count then differ in the rows that carry the
    words alone: "an apple" against "a tree" in two rows of 589. The model
    then reads one short, ambiguous row. Measured: either
    concept whole, never a mixture, flipping between them at a weight
    difference of 0.05, and behaving otherwise on a long prompt, where many
    rows differ.

    Encoder Fusion answered this geometry before: `_fusion_weights` holds BOTH
    readings at 1 in the middle of its band instead of halving each, and
    `slerp_tokens` turns the direction while the length runs between the two
    lengths. The same `slerp_tokens` carries every concept here. The result so
    far and the next concept are interpolated at that concept's share of the
    weight carried so far, so two concepts are exactly `slerp_tokens` at
    w2 / (w1 + w2), and each further concept turns the result further. Only the
    RATIO of the weights acts, so halving every weight changes nothing, and the
    length runs between the lengths of the two readings instead of falling
    below both. Three concepts or more depend on the order they are chained in,
    as every running mean on a sphere does, and the pooled vector -- one vector,
    with no shared rows to hold it steady -- moves several times as far under a
    reordering as the table does.

    A share INSIDE [0, 1] -- every weight of one sign -- reaches a point between
    the concepts, which is where Encoder Fusion uses `slerp_tokens`. A share
    outside it, which mixed signs produce, EXTRAPOLATES, and that is an
    operation this instrument offers rather than one it refuses: the result
    leaves the arc between the concepts, stands antiparallel to one of them at a
    share of pi/theta and back ON it at 2*pi/theta, and the length term
    (1-a)|x| + a|y| crosses zero at a different share in every row, so single
    rows are annihilated while their neighbours are stretched. That is the
    estrangement Split & Combine had (`ai4artsed_comfyui/ai4artsed_conditioning_fusion.py`,
    alpha from -5 to +5) and that this instrument brings back; of that node's
    four methods, two were the plain sum and one was this same per-row slerp, so
    the range was what distinguished it. Nothing clamps the result: at the far
    end of the surface's slider a row runs some 30 times the longest input row,
    and the turn per row spreads far enough that the table scatters rather than
    travels.

    Four cases are refused rather than papered over, because each one would
    silently change what the model reads. A weight that is not a finite number:
    NaN passes every comparison and would carry the whole table and the pooled
    vector to NaN without an error anywhere. A concept whose CONDITIONING
    carries more than one entry: everything past the first would be left out.
    Tables of unequal row count: the shorter ones would need rows no encoder
    wrote, and SD 3.5 reads its text stream without an attention mask, so it
    attends to them. A set in which only some concepts carry a pooled vector:
    the result would mix a vector with nothing, and SD3.encode_adm needs one.

    A weight of exactly 0 takes its concept out of the chain rather than
    interpolating 0 towards it, so [0, 0, 5] gives the third concept instead of
    dividing by a share that never left the starting point. Where the weights
    carried so far and the next one cancel exactly there is no share at all, and
    that one set is refused with its two numbers.

    Any other key the first concept's conditioning carries is taken over as it
    stands; through this instrument's graph there is none besides the pooled
    vector.
    """
    weights = [float(w) for w in weights]
    for index, weight in enumerate(weights):
        if not math.isfinite(weight):
            raise ValueError(
                "Concept %d carries the weight %r, which is not a finite "
                "number. Every comparison against it is false, so it would "
                "reach the interpolation and carry the whole conditioning to "
                "NaN." % (index + 1, weight))

    heads = []
    for cond, _weight in concepts:
        if len(cond) != 1:
            raise ValueError(
                "A concept carries %d conditionings where one is expected. "
                "Combining in the conditioning interpolates the tables, and "
                "everything past the first would be left out." % len(cond))
        heads.append(cond[0])

    rows = sorted({tensor.shape[1] for tensor, _meta in heads})
    if len(rows) != 1:
        raise ValueError(
            "The concepts' conditionings carry %s rows. Interpolating them "
            "needs the same count in every one, and padding the shorter ones "
            "would add rows no encoder wrote." % ", ".join(str(r) for r in rows))
    if not all(meta.get("pooled_output") is not None for _tensor, meta in heads):
        raise ValueError(
            "Some concepts carry a pooled vector and some do not, so the "
            "result would mix a vector with nothing.")

    carrying = [(head, weight) for head, weight in zip(heads, weights) if weight != 0]
    if not carrying:
        raise ValueError(
            "Every concept is weighted 0, so there is no reading to "
            "interpolate between. Give at least one concept a weight.")

    slerp = _platform_slerp()
    (table, first_meta), carried = carrying[0]
    pooled = first_meta["pooled_output"]
    for (tensor, meta), weight in carrying[1:]:
        total = carried + weight
        if abs(total) < 1e-6:
            raise ValueError(
                "The weights carried so far (%.2f) and the next concept (%.2f) "
                "cancel, so there is no share to interpolate at -- every point "
                "on the line is equally far. Move one of the two."
                % (carried, weight))
        alpha = weight / total
        table = slerp(table, tensor, alpha)
        pooled = slerp(pooled, meta["pooled_output"], alpha)
        carried = total
    meta = dict(first_meta)
    meta["pooled_output"] = pooled
    return [[table, meta]]


class _ComposableGuider(comfy.samplers.CFGGuider):
    """A guider that predicts once per concept and composes in score space."""

    def set_concepts(self, concepts, negative, cfg, normalize_weights):
        weights, self.composition_mode = _read_weights(concepts, normalize_weights)
        self.guidance = [cfg * w for w in weights]

        conds = {"negative": negative}
        for i, (cond, _w) in enumerate(concepts):
            conds["ai4artsed_concept_%d" % i] = cond
        self.inner_set_conds(conds)
        self.set_cfg(cfg)

    def predict_noise(self, x, timestep, model_options={}, seed=None):
        uncond = self.conds.get("negative", None)
        per_concept = [self.conds.get("ai4artsed_concept_%d" % i)
                       for i in range(len(self.guidance))]
        out = comfy.samplers.calc_cond_batch(
            self.inner_model, per_concept + [uncond], x, timestep, model_options)
        eps_u = out[-1]
        composed = eps_u
        for v, eps in zip(self.guidance, out[:-1]):
            composed = composed + v * (eps - eps_u)
        return composed


class AI4ArtsEdComposableDiffusion:
    """KSampler that combines the concepts in one of two places."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "concepts": ("AI4ARTSED_CONCEPTS",),
                "negative": ("CONDITIONING",),
                "latent_image": ("LATENT",),
                "seed": ("INT", {"default": 123456789, "min": 0,
                                 "max": 0xFFFFFFFFFFFFFFFF}),
                "steps": ("INT", {"default": 25, "min": 1, "max": 200}),
                "cfg": ("FLOAT", {"default": 4.5, "min": 0.0, "max": 100.0,
                                  "step": 0.1}),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS,
                                 {"default": "euler"}),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS,
                              {"default": "normal"}),
                "normalize_weights": ("BOOLEAN", {"default": True}),
                "combine_at": (["score", "conditioning"], {
                    "default": "score",
                    "tooltip": "Where the concepts are combined. score: one "
                               "prediction per concept at every step, added with "
                               "the weights. conditioning: their conditionings "
                               "interpolated into one before the run, where only "
                               "the ratio of the weights acts."}),
            },
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "sample"
    CATEGORY = "AI4ArtsEd/latent lab"

    def sample(self, model, concepts, negative, latent_image, seed, steps, cfg,
               sampler_name, scheduler, normalize_weights, combine_at="score"):
        if not concepts or len(concepts) < 2:
            raise ValueError(
                "Composable Diffusion needs at least two concepts; %d arrived. "
                "Chain AI4ArtsEdConcept nodes into `concepts`."
                % len(concepts or []))

        latent = latent_image["samples"]
        latent = comfy.sample.fix_empty_latent_channels(model, latent)
        noise_mask = latent_image.get("noise_mask", None)
        noise = comfy.sample.prepare_noise(latent, seed,
                                           latent_image.get("batch_index", None))

        if combine_at == "conditioning":
            # Not _read_weights: normalizing divides every weight by their sum,
            # and here only their ratio acts, which that division leaves as it
            # is. The weights go in as they stand.
            weights = [float(w) for _cond, w in concepts]
            guider = comfy.samplers.CFGGuider(model)
            guider.set_conds(_combined_conditioning(concepts, weights), negative)
            guider.set_cfg(float(cfg))
        else:
            guider = _ComposableGuider(model)
            guider.set_concepts(concepts, negative, float(cfg), bool(normalize_weights))

        sampler = comfy.samplers.sampler_object(sampler_name)
        sigmas = comfy.samplers.calculate_sigmas(
            model.get_model_object("model_sampling"), scheduler, steps)
        sigmas = sigmas.to(model.load_device)

        callback = latent_preview.prepare_callback(model, sigmas.shape[-1] - 1)
        disable_pbar = not comfy.utils.PROGRESS_BAR_ENABLED

        samples = guider.sample(noise, latent, sampler, sigmas,
                                denoise_mask=noise_mask, callback=callback,
                                disable_pbar=disable_pbar, seed=seed)
        samples = samples.to(comfy.model_management.intermediate_device())

        out = latent_image.copy()
        out["samples"] = samples
        return (out,)


NODE_CLASS_MAPPINGS = {
    "AI4ArtsEdConcept": AI4ArtsEdConcept,
    "AI4ArtsEdComposableDiffusion": AI4ArtsEdComposableDiffusion,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AI4ArtsEdConcept": "AI4ArtsEd Concept",
    "AI4ArtsEdComposableDiffusion": "AI4ArtsEd Composable Diffusion",
}
