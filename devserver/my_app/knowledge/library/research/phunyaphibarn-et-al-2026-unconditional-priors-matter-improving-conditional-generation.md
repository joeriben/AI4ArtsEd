---
id: phunyaphibarn-et-al-2026-unconditional-priors-matter-improving-conditional-generation
titel: Unconditional Priors Matter!. Improving Conditional Generation of Fine-Tuned Diffusion Models
autor: "Prin Phunyaphibarn, Phillip Y. Lee, Jaihoon Kim, Minhyuk Sung"
jahr: 2026
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2503.20240"
status: published
analyzed_at: "2026-07-31T10:39:36.376994+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Unconditional Priors Matter!. Improving Conditional Generation of Fine-Tuned Diffusion Models

## PROFIL

The text argues that in Classifier-Free Guidance (CFG) for conditional diffusion models, replacing the fine-tuned model's degraded unconditional noise prediction with that of a base model or another pretrained diffusion model significantly improves conditional generation quality. It sets itself against the common practice of jointly learning conditional and unconditional noise within a single network using a small dropout rate, which restricts network capacity and degrades the unconditional prior, thereby harming conditional outputs. By demonstrating that unconditional noise need not be learned jointly during fine-tuning, the authors offer a training-free solution applicable across various architectures and condition modalities. For arts education, this method provides a computationally efficient way to enhance the fidelity of AI-generated visual media used in creative instruction and student projects.

## WISSEN

### Problem Framing and Thesis

Diffusion models are easily adapted into conditional models by fine-tuning a base model, with Classifier-Free Guidance (CFG) as the core mechanism. CFG trains a single network to predict both conditional and unconditional noise, combining them at generation time. However, this joint learning produces poor unconditional priors: network capacity is shared, and the unconditional bandwidth is further restricted by a 5–20% condition drop rate — a problem exacerbated by limited training data or repeated fine-tuning. Critically, degraded unconditional noise prediction directly harms conditional generation quality, since CFG combines both predictions.

The overlooked point is that the base model already possesses superior unconditional generation. The thesis: in CFG-based conditional generation with a fine-tuned model, replacing the fine-tuned model's unconditional noise with that of the base model yields significant quality improvements — a training-free solution requiring no network modification. This demonstrates that unconditional noise need not be learned jointly with conditional noise during fine-tuning.

A further claim extends this: the replacement unconditional noise need not come from the specific base model used for fine-tuning but can originate from other pretrained diffusion models, further eliminating the need for joint learning when a pretrained unconditional model is available.

<!-- quelle: Problem Framing and Thesis -->

### Related Works and Demarcation

Classifier-Free Guidance (CFG) is the de facto technique for conditional diffusion generation, but its dynamics when a model is fine-tuned remain largely unexplored. Existing work either restricts CFG to certain timesteps or extends guidance beyond text conditions for off-the-shelf models. Zhong et al. address fine-tuned DiTs by using unconditional noise from the original model, but only for small class-conditional architectures. The proposed method applies to large-scale diffusion models across different architectures and condition modalities, motivated by empirical observations of unconditional noise degradation during fine-tuning.

Demarcation from Autoguidance: Autoguidance uses an under-trained version of the same model under the same condition to isolate quality from condition-alignment. The proposed method instead combines models whose conditions differ in modality, correcting degradation in the unconditional prior within CFG. Autoguidance stresses that degradations must match the conditional model's; a key contribution here is showing that fine-tuned unconditional degradation hurts rather than helps conditional generation quality.

On merging diffusion models: prior work merges weights (Diffusion Soup), LoRA adapters (Mix-of-Show), intermediate features (MaxFusion), or noise estimates from the same or different models for condition composition. This work extends noise-estimate merging to enhance generation quality when applying CFG to fine-tuned models.

<!-- quelle: Related Works and Demarcation -->

### Diffusion Models and Classifier-Free Guidance

Diffusion models generate data via iterative denoising: a forward process adds Gaussian noise to clean data x₀, and a reverse process denoises x_t by modeling transitions as Gaussian distributions. The posterior mean μ_θ(x_t, t) is reparameterized as a noise prediction task using Tweedie's formula, yielding a predicted clean observation x_{0|t} = g(x_t, ε_θ(x_t)). DDIM enables efficient sampling through a deterministic, non-Markovian transition conditioned on x₀.

Classifier-Free Guidance (CFG) enables conditional generation without a separate classifier. During training, the model learns both conditional ε_θ(x_t, c) and unconditional ε_θ(x_t, ∅) noise prediction by randomly replacing c with null condition ∅. At sampling, CFG replaces the standard noise prediction with ε_θ^(γ)(x_t, c) = ε_θ(x_t, ∅) + γ(ε_θ(x_t, c) − ε_θ(x_t, ∅)), where γ is a guidance scale. Interpreted via score-based models, CFG approximates the score of a gamma-powered distribution p_γ(x_t|c) := p(x_t)(p(x_t|c)/p(x_t))^γ, which can be rewritten as p(x_t)·p(c|x_t)^γ. Thus CFG guides samples through an implicit classifier p(c|x_t)^γ; γ > 1 sharpens the mode corresponding to c, improving conditional alignment and image quality.

<!-- quelle: Conceptual Background -->

### Unconditional Priors Matter

Fine-tuned diffusion models using CFG training suffer conditional generation quality degradation because their unconditional noise estimates deteriorate. This occurs because (1) the unconditional distribution is inherently more complex than the conditional one, and (2) the low CFG dropping probability (5–20%) means only a small data fraction serves unconditional learning per iteration. Through the CFG formulation—sampling from p_γ(x_t|c) ∝ p(x_t) p(c|x_t)^γ—poor unconditional priors introduce approximation errors to p(x_t), which propagate to both p(x_t) and p(c|x_t) ∝ p(x_t|c)/p(x_t). The fine-tuned model thus loses the base model's rich unconditional prior.

The proposed fix replaces the fine-tuned model's unconditional noise prediction with that of a pretrained model possessing better unconditional priors, combining it with the fine-tuned model's conditional prediction in the CFG noise and DDIM sampling step. The source need not be the true base model—any diffusion model with good unconditional priors suffices (e.g., using SD2.1 or PixArt-α unconditional predictions for models fine-tuned on SD1.x). Via the EBM–diffusion connection, this is equivalent to sampling from the time-annealed distribution p_ψ(x_t)^{1−γ} p_θ(x_t|c)^γ, where p_ψ and p_θ are distributions modeled by the base and fine-tuned models respectively.

<!-- quelle: Method Formulation -->

### Empirical Validation Across Single- and Dual-Condition CFG Formulations

The method is validated on five conditional diffusion models. The central claim: replacing a fine-tuned model's degraded unconditional noise prediction with that of a base model improves output quality while preserving condition alignment.

**Single-condition CFG** (one unconditional term replaced):
- **Zero-1-to-3** (novel view synthesis, fine-tuned from SD-IV←SD1.4): Using base-model unconditional noise improves LPIPS, PSNR, SSIM across all base models tested; SD2.1 performs best. Corrects lighting, color saturation, and shape distortions.
- **Versatile Diffusion** (image variations, progressively fine-tuned from SD1.4): Cascaded fine-tuning yields worst unconditional generation quality. Base-model substitution improves FID and FD-DINOv2 while retaining CLIP-I and DINOv2 similarity—quality gain without condition-alignment loss. Corrects saturation and object distortion.
- **DiT** (class-conditional, fine-tuned on SUN397, Food101, Caltech101): Method generalizes beyond UNet to DiT architecture. Larger benefits on larger datasets (Food101, SUN397), corroborating that unconditional-prior degradation is amplified by limited computational budget. No improvement on Caltech101 (10× smaller), as the model sufficiently fits despite low CFG dropout.

**Dual-condition CFG** (only the fully-unconditional term ϵθ(xt,∅,∅) is replaced; ϵθ(xt,c1,∅) remains):
- **DynamiCrafter** (text-and-image-to-video, fine-tuned from VideoCrafterT2V): Outperforms baseline in 7/9 VBench-I2V metrics; more temporally consistent, less distorted.
- **InstructPix2Pix** (instruction-based editing, fine-tuned from SD1.5): Better prompt alignment and identity preservation; improvements in Image Reward and PickScore (human-preference-aligned metrics), slight CLIP-T underperformance with SD1.5/SD2.1.

Notably, improvements hold even when the substitute base model uses a different architecture (PixArtα, a DiT, substituting for UNet-based fine-tuned models).

<!-- quelle: Empirical Validation -->

### Conclusion and Outlook

The proposed training-free approach improves generation quality of CFG-based fine-tuned conditional diffusion models by replacing low-quality unconditional noise with richer unconditional noise drawn from a separate pretrained base diffusion model. Validation spans image variation, image editing, novel view synthesis, and video generation. Notably, the separate pretrained model may differ in both weights and architecture from the original base model.

Limitations: although training-free, the method requires loading a second model, increasing memory cost; parallelization as in CFG is no longer possible, introducing slight inference overhead. The method is less effective for adapter-based fine-tuning approaches such as ControlNet and GLIGEN, which exhibit less degradation in unconditional priors. Identifying unconditional priors for these advanced fine-tuning techniques remains a valuable future direction.

<!-- quelle: Conclusion and Outlook -->

### Supplementary Material and References

This section contains funding acknowledgements (IITP grants, Industrial Technology Innovation Program, DRB-KAIST SketchTheFuture Research Center) and a bibliography of 55 references spanning diffusion models, video generation, image editing, compositional generation, multi-modal synthesis, evaluation metrics, and datasets. No argumentative content is present.

<!-- quelle: Supplementary Material and References -->

## GLOSSAR

- **Classifier-Free Guidance (CFG)** — A training and sampling modification enabling conditional generation without a separate classifier, by learning both conditional and unconditional noise predictions and extrapolating between them at inference.
- **unconditional noise** — The noise prediction corresponding to the unconditional case in CFG, generated by dropping the conditioning input during training.
- **base model** — A pretrained unconditional or lightly conditioned diffusion model from which conditional models are fine-tuned using CFG.
- **Autoguidance** — A guidance method using noise estimates from an under-trained version of the same model under the same condition to improve image quality.
- **unconditional noise degradation** — The observed deterioration of unconditional noise prediction quality that occurs when a diffusion model is fine-tuned for a specific task.
- **Tweedie's formula** — A statistical result used to reparameterize the posterior mean prediction in diffusion models as a noise prediction task, yielding a predicted clean observation x_{0|t}.
- **gamma-powered distribution** — The implicit distribution p_γ(x_t|c) := p(x_t)(p(x_t|c)/p(x_t))^γ whose score CFG approximates, equivalent to p(x_t)·p(c|x_t)^γ, where γ > 1 sharpens the conditional mode.
- **CFG (Classifier-Free Guidance)** — A training and sampling technique combining conditional and unconditional noise predictions to sample from a gamma-powered distribution p_γ(x_t|c) ∝ p(x_t) p(c|x_t)^γ.
- **unconditional prior** — The model's estimate of the marginal data distribution p(x_t), which modulates conditional generation in CFG and degrades under fine-tuning on narrow task-specific data.
- **time-annealed distribution** — The distribution p_ψ(x_t)^{1−γ} p_θ(x_t|c)^γ obtained by combining noise predictions from different models at each timestep, grounded in the energy-based model connection to diffusion.
