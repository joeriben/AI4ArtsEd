---
id: gandikota-et-al-2023-erasing-concepts-from-diffusion-models-esd
titel: Erasing Concepts from Diffusion Models
autor: ""
jahr: 2023
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2303.07345"
status: published
analyzed_at: "2026-07-31T09:56:03.276725+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Erasing Concepts from Diffusion Models

## PROFIL

The text argues that Erased Stable Diffusion (ESD), a fine-tuning method utilizing negative guidance as a teacher, can permanently erase targeted visual concepts—such as copyrighted artistic styles or explicit content—from pre-trained diffusion model weights using only a textual description. It positions itself against dataset filtering, post-generation filtering, and inference guiding approaches like Safe Latent Diffusion, which are either computationally prohibitive or easily circumvented by users with access to model weights. For arts education, this provides a technical framework for understanding how generative AI systems can be structurally modified to enforce copyright and ethical boundaries without relying on external content filters.

## WISSEN

### Problem Framing and Thesis

Large-scale diffusion models produce undesirable output—sexually explicit content and copyrighted artistic styles. Prior remedies fall into three categories, each insufficient: **dataset filtering** requires prohibitive retraining (SD 2.0 consumed 150,000 GPU-hours over 5 billion images, yet still yields 417 nudity-flagged images on the I2P benchmark vs. 796 for SD 1.4); **post-generation filtering** (e.g., the NSFW filter bundled with SD 1.4) is trivially disabled since weights and code are public; **inference guiding** (e.g., Safe Latent Diffusion) steers output but can be circumvented. Existing artist-protection methods (adversarial perturbation of source images) cannot remove an already-learned style from a pretrained model.

Thesis: a fine-tuning method, **Erased Stable Diffusion (ESD)**, permanently erases a targeted visual concept from model weights using only a short text description of the undesired concept and **negative guidance as a teacher**, with no additional training data. Erasure is weight-level, so it cannot be circumvented even with parameter access. The method is benchmarked against Safe Latent Diffusion and censored training for NSFW removal, tested on erasing five modern artists with a user study, and applied to whole object-class erasure.

<!-- quelle: Problem Framing and Thesis -->

### Related Work and Demarcation

The work demarcates itself from five existing approaches. Against undesirable image removal via dataset censorship (costly, unintended effects) and post-hoc modification (efficient but circumventable), it proposes a third approach: tuning model parameters via guidance-based model-editing, which is fast and difficult to circumvent. Unlike image cloaking, where artists add adversarial perturbations to self-censor content from AI training, this work asks how a model creator can erase a visual concept without active self-censorship by content providers. Unlike model editing methods that add or modify object appearances, the goal is to erase a targeted visual concept using only a single textual description. Unlike machine unlearning, which removes identifiable training data points, this method erases a high-level visual concept learned from an unknown subset of training data. Finally, unlike energy-based composition applied at inference time to reduce undesirable output, this work uses score composition as unsupervised training data to fine-tune model weights to erase a concept.

<!-- quelle: Related Work and Demarcation -->

### Denoising and Latent Diffusion Models

Diffusion models learn a distribution space through gradual denoising: from sampled Gaussian noise, the model predicts noise ϵ_t at each timestep t across T steps, producing intermediate denoised images x_t, where x_T is initial noise and x_0 the final image. This process is modeled as a Markov transition probability.

Latent diffusion models (LDM) improve efficiency by operating in a lower-dimensional latent space z of a pretrained variational autoencoder (encoder E, decoder D). During training, noise is added to the encoded latent z = E(x), yielding z_t with noise level increasing with t. A sequence of denoising models with shared parameters θ learns to predict noise ϵ_θ(z_t, c, t) conditioned on timestep t and text condition c.

Classifier-free guidance regulates generation by redirecting the probability distribution toward data highly probable under an implicit classifier p(c|z_t). The model is jointly trained on conditional and unconditional denoising; at inference, the final score ϵ̃_θ(z_t, c, t) is steered toward the conditioned and away from the unconditioned score via guidance scale α > 1. Inference proceeds sequentially from Gaussian noise z_T through denoising to z_0, then decoded to image space: x_0 ← D(z_0).

<!-- quelle: Conceptual Background -->

### Erased Stable Diffusion: Method and Parameter Choice

The method erases concepts from a pretrained Stable Diffusion U-Net using only the model's own knowledge—no external data. It fine-tunes new parameters θ while keeping the original θ* frozen. Using Tweedie's formula and the reparametrization trick, the score function is rewritten as a denoising prediction; the objective guides θ away from the concept c by combining the frozen model's conditioned and unconditioned noise predictions with negative guidance scaled by η. Training samples are synthesized by the model itself conditioned on c, eliminating data collection.

The effect of erasure depends on which parameters are fine-tuned. Cross-attention parameters depend directly on the prompt text; non-cross-attention parameters contribute to a visual concept even when it is unmentioned. Thus two configurations are proposed:

- **ESD-x** (cross-attention-only fine-tuning): erasure is controlled and prompt-specific—e.g., removing a named artistic style such as Van Gogh's only when his name appears, with minimal interference with other styles.
- **ESD-u** (non-cross-attention fine-tuning): erasure is global and prompt-independent—e.g., removing nudity even when NSFW terms are absent from the prompt.

Van Gogh-style removal illustrates the distinction: ESD-u globally degrades stylistic features across unrelated artists, while ESD-x confines erasure to prompts naming Van Gogh. For NSFW removal, ESD-u performs best because the visual concept must be suppressed regardless of prompt wording.

<!-- quelle: Method and Parameter Choice -->

### Artistic Style Removal: Experiments and User Study

ESD-x fine-tunes cross-attention; ESD-u fine-tunes unconditional U-Net weights. Baselines: SD (pretrained), SLD (Safe Latent Diffusion, adapted by substituting target concept for original safety concepts), SD-Neg-Prompt (artist name as negative prompt).

Five modern artists reported imitated by Stable Diffusion are studied: Kelly McKernan, Thomas Kinkade, Tyler Edlin, Kilian Eng, and the series 'Ajin: Demi-Human.' No direct copies were observed, but styles were captured. Qualitative results (Fig 5) and a user study measure human perception of removal effectiveness.

User study: 40 real images per artist, 40 generic prompts per artist, 4 seeds each, yielding 1000 images. Similar artists paired: (Kelly McKernan, Kirbi Fagan), (Thomas Kinkade, Nicky Boehme), (Ajin: Demi Human, Tokyo Ghoul), (Tyler Edlin, Feng Zhu), (Kilian Eng, Jean Giraud). 13 participants rated confidence (1–5 Likert) that an experimental image matched the reference artist.

Results: original images averaged 3.85; similar artists 3.16; AI-generated art 3.21 (higher than similar genuine artwork, confirming style capture). All removal techniques reduced perceived style: ESD-x 1.12, SLD 2.00, SD-Neg-Prompt 2.22. ESD-x showed minimal interference on untargeted styles. Unlike baselines, ESD-x permanently modifies the model.

<!-- quelle: Application: Artistic Style Removal -->

### Explicit Content Removal via ESD-u

Existing NSFW restriction approaches—inference modification (SLD), post-production classification, and retraining on filtered data (SD V2.0)—are inadequate: inference and post-production methods are circumventable when models are open-sourced, and retraining is expensive yet still produces nudity. Because nudity erasure must be global and independent of text embeddings, the authors apply ESD-u to erase "nudity." Using 4703 images generated from I2P prompts and classified via Nudenet, ESD-u (weak erasure, η = 1) reduces nudity-classified samples from 796 to 134, outperforming SLD and SD V2.0 across all nudity classes. To verify safe-content generation is preserved, fidelity (FID) and CLIP scores are measured on COCO 30K. ESD-u achieves FID 13.68—better than SD's 14.50—possibly because COCO is curated without nudity; stronger erasure (ESD-u-3, η = 3) yields FID 17.27. All methods maintain similar CLIP scores to SD, indicating minimal effect on text-conditioning specificity.

<!-- quelle: Application: Explicit Content Removal -->

### Object Removal and Interference

ESD-u models were tested for erasing entire object classes from Stable Diffusion. Ten models, each targeting one Imagenette class, were evaluated by generating 500 images per class and measuring top-1 ResNet-50 classification accuracy. Targeted class accuracy dropped sharply (average 78.2% → 12.6%), confirming effective erasure, though some classes resisted removal (e.g., 'church': 73.8% → 54.2%). Untargeted classes retained relatively high accuracy (78.2% → 63.2% average), but interference occurred: erasing 'French horn' reduced other-class accuracy to 49.4%, and 'garbage truck' to 51.5%. The parameter η governs a trade-off between erasure strength and collateral interference. For nudity erasure, η = 10 removed 92% of cases but reduced 1000-way object classification by 34%; η = 3 removed 88% with 14% impact; η = 1 removed 83% with 7% impact. Lower η also improves image quality. The appropriate η thus depends on the application's tolerance for residual targeted content versus interference on unrelated concepts.

<!-- quelle: Application: Object Removal and Interference -->

### Limitations and Conclusion

The method outperforms baselines in erasing targeted visual concepts, but erasing large-scale concepts—entire object classes or particular styles—imposes a trade-off between complete erasure and interference with non-targeted concepts. When erasing entire object classes, the method sometimes removes only distinctive attributes (crosses from churches, ribs from parachutes) while leaving the larger concept intact; interference with other classes is quantified in Section 5.3. Artistic style erasure occasionally interferes with other styles, as reflected in the user study (Section 5.1.2).

The paper proposes eliminating specific concepts from text-to-image generation models by directly editing model weights, bypassing the traditional need for extensive dataset filtering and expensive retraining. The method requires only the concept name, eliminates post-inference filters, and enables safe parameter distribution. Efficacy is demonstrated across three applications: (1) removing explicit content, with results comparable to the Safe Latent Diffusion method; (2) removing artistic styles, validated through a human study; (3) removing concrete object classes, illustrating the method's versatility.

<!-- quelle: Limitations and Conclusion -->

### References and Appendix: Visual Motivation and Implementation Details

Source code, datasets, and fine-tuned weights are publicly available. The appendix provides visual motivation for the training objective and implementation details.

**A. Visual Motivation.** The objective is a reconstruction loss between the edited model's conditioned noise and the negatively guided noise from a frozen model. This teaches the model to erase the *residual noise* — the difference between conditional and unconditional scores — that corresponds to a target concept. Visualized at t=10 and amplified 10× through the VAE decoder, the residual noise captures styles and attributes of concepts; negating it from unconditional noise yields a distribution without the concept.

**B. Implementation Details — Artist Style Erasure.** Method: ESD-x with negative guidance 1, fine-tuned 1000 iterations at learning rate 1e-5, using the artist name as the conditioning prompt. Baselines: SLD-Medium (with artist name replacing the default safety concept), Stable Diffusion v1.4, and SD with negative prompt (artist name as negative prompt). Dataset: 1000 images generated using prompts like "art in the style of [artist]" for both erased and similar artists.

<!-- quelle: References and Appendix -->

## GLOSSAR

- **Erased Stable Diffusion (ESD)** — The proposed fine-tuning method that removes a visual concept from a pretrained diffusion model's weights using only a concept description and negative guidance as a teacher.
- **negative guidance as a teacher** — A training signal that steers model weights away from the undesired concept during fine-tuning, serving as the supervisory mechanism for erasure.
- **I2P benchmark** — The Inappropriate Image Prompts benchmark, a set of 4,703 prompts used to evaluate generation of unsafe images by diffusion models.
- **Image cloaking** — Artists adding adversarial perturbations to images before posting them online to hide the work from machine-learned models during training or inference.
- **Machine unlearning** — Modifying a model to behave as if particular, identifiable training data points had not been present.
- **Energy-based composition** — Performing set-like composition on energy-based models and diffusion counterparts via arithmetic on the score or noise predictions.
- **classifier-free guidance** — A technique that steers generation toward conditioned data by combining conditional and unconditional scores at inference using a guidance scale α > 1.
- **latent diffusion models (LDM)** — Diffusion models operating in a lower-dimensional latent space of a pretrained variational autoencoder for improved efficiency.
- **Markov transition probability** — The probabilistic framework modeling the stepwise denoising process from noise to final image.
- **ESD-x** — A variant of the Erasing Stable Diffusion method that fine-tunes cross-attention layers with negative guidance to remove a target concept.
