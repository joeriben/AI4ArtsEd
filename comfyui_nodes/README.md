# AI4ArtsEd ComfyUI Custom Nodes

Node sources kept in this repo alongside the chunks that call them. They do **not**
run from here — ComfyUI only loads what sits in its own `custom_nodes/` directory.

Two kinds of node live here: single `.py` files (CamelCase node names, written for
the move to ComfyUI), and the package `ai4artsed_comfyui/` (lowercase node names),
the fork taken whole on 2026-09-12 of `github.com/joeriben/ai4artsed_comfyui_nodes`.
That repository stays a ComfyUI-only package and is developed apart from this one;
the fork is developed here. The installer cloned it into `custom_nodes/` until that
day. Its LLM nodes call the DevServer (`_devserver.py`: `POST /api/chat/proxy`),
which resolves the model, holds the keys and applies the fallback the settings page
regulates; its two key nodes read the DevServer's key files through
`_platform_credentials.py`, which loads the DevServer's own reader
(`devserver/my_app/services/llm_providers.py`) by path: `OPENROUTER_API_KEY`, else
`devserver/openrouter.key`. The clone read an `openrouter.key` of its own next to its
sources; API keys have one place, and the package carries none
(`devserver/tests/test_own_comfyui_nodes.py` checks that).

## Deploy

`install_comfyui_nodes.sh` links every `.py` and every package directory in this
directory into ComfyUI's `custom_nodes/` (step 3 of 3). A symlink rather than a
copy, so a `git pull` carries the node with it; a real file or directory of the
same name already in `custom_nodes/` is left alone and reported. A clone of the
foreign package from before 2026-09-12 sits at exactly that name and has to be
moved aside.

Until 2026-09-07 there was no such step: these nodes reached the development card
through a symlink set by hand, and a fresh install went without them. ComfyUI
validates `class_type` at submit time, so a workflow using a node that is not
installed is rejected by `/prompt` before anything loads.

```bash
./install_comfyui_nodes.sh
```

Restart ComfyUI after adding a node, then confirm it registered:

```bash
curl -s 127.0.0.1:17804/object_info/AI4ArtsEdDenoisingArchaeology | head -c 200
```

The package's node names are lowercase with underscores
(`ai4artsed_conditioning_fusion`); the single-file nodes are written in CamelCase
(`AI4ArtsEdDenoisingArchaeology`). `devserver/tests/test_own_comfyui_nodes.py`
reads both and checks that every AI4ArtsEd node a chunk calls is here, that the
installer deploys it, and that the package holds no key file and no provider host.

## Nodes

| Node | Used by | Purpose |
|---|---|---|
| `AI4ArtsEdDenoisingArchaeology` | `output_image_denoising_archaeology_comfyui.py` | KSampler that keeps the working latent of every step as a JPEG frame |
| `AI4ArtsEdKeepLatent` | `output_image_sd35_large.json`, `output_image_sd35_turbo.json` | Passes a LATENT through and, when asked, writes the run's final latent as `.npy` in the model's latent space, for Mean Images |
| `AI4ArtsEdLoadKeptLatent` | `devserver/my_app/services/latent_decoder.py` (no chunk) | Reads such a file, or the mean of several, back into a LATENT for the VAE decode |
| `AI4ArtsEdSD3Encode`, `AI4ArtsEdSD3Algebra`, `AI4ArtsEdSD3Probe`, `AI4ArtsEdSD3Fusion`, `AI4ArtsEdSD3Assemble`, `AI4ArtsEdSD3TextEncode` | `output_image_concept_algebra_comfyui.py`, `output_image_feature_probing_comfyui.py`, `output_image_surrealizer_comfyui.py`; `AI4ArtsEdSD3TextEncode` is the negative of every SD 3.5 graph but the Surrealizer's and the Fusion Workbench's scheduled fusion, which fuse their negative the way they fuse the prompt (`schemas/engine/comfyui_chunk_support.py`) | SD 3.5 conditioning addressed per encoder: the parts, arithmetic on one encoder, dimension differences, T5 added onto the CLIP block by a factor past one (the Surrealizer's five strategies), the assembly; the plain encode with the CLIP window |
| `AI4ArtsEdAttentionCapture`, `AI4ArtsEdAttentionMaps` | `output_image_attention_cartography_comfyui.py` | Attention Cartography: a block replacement on the chosen joint blocks reads softmax(QK^T/sqrt(d)) beside ComfyUI's own attention, per step and block, averaged over batch and heads, cut to the word columns; the second node writes maps and tokens to a JSON file after the sampler and announces it under `ai4artsed_attention` |
| `AI4ArtsEdSD3ContextReplace`, `AI4ArtsEdSD3ContextDelta`, `AI4ArtsEdSD3ContextProbe`, `AI4ArtsEdSD3ContextCapture`, `AI4ArtsEdSD3ContextReplay`, `AI4ArtsEdSD3ContextRelease` | `devserver/my_app/services/latent_lab_context_graphs.py` (the Fusion Workbench's `/generate` and its research routes `decomposition`, `position_probe`, `delayed_kickin`, `delayed_kickin_cumulative`) | The text context of SD 3.5's joint blocks, written per block and per step window as a block replacement: replaced whole (the Fusion Workbench's scheduled fusion; the kick-in at block 0), a slice of one encoder's stream moved by alpha times a delta (Decomposition's cells), a slice replaced by a probe's (the position probe), or a block's context recorded over two pre-runs and replayed from a step on (the kick-in past block 0), the recording released after the main run |
| `AI4ArtsEdConcept`, `AI4ArtsEdComposableDiffusion` | `output_image_composable_diffusion_comfyui.py` | Composable Diffusion: a weighted concept, and the sampler cfg function that composes them |
| `ai4artsed_comfyui/` (13 nodes) | `output_vector_fusion_clip_sd35.json`, `dual_encoder_fusion_image.json`, `legacy_surrealization.json` call four of them | The forked package: conditioning and T5-CLIP fusion, Prompt Interception, the safety switch, randomizers, image analysis, the key node. See its `architecture.md`. |

### AI4ArtsEdDenoisingArchaeology

Port of `gpu_service/services/diffusers_backend.py::generate_image_with_archaeology`.

It captures the working latent x_t, the same quantity the Diffusers original
decodes (`callback_kwargs["latents"]`), and not the net's denoised prediction x0 —
ComfyUI's callback carries both, and its own live preview shows x0. Before the VAE
sees a frame it goes through `model_sampling.calculate_input` (the
`1/sqrt(sigma²+1)` divide for SDXL and other eps/v-prediction nets, the identity
for flow matching) and then `process_latent_out`, which already carries the latent
format's scale and shift.

One deliberate difference: the Diffusers original VAE-decodes inside the step
callback, which pins the VAE and the MMDiT on the GPU at the same time. This node
collects the latents on CPU (~1 MB each for SD3.5 at 1024×1024) and decodes them
once sampling has finished, so ComfyUI can release the diffusion model first.

Outputs the final `LATENT` for a downstream `VAEDecode` → `SaveImage`, and announces
the step frames in its `ui` payload as `archaeology[0].frames`
(`{step, sigma, filename, subfolder}`), which the chunk joins against the files the
DevServer's ComfyUI client downloads.
