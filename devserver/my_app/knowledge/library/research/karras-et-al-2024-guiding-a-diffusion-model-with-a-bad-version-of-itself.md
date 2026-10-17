---
id: karras-et-al-2024-guiding-a-diffusion-model-with-a-bad-version-of-itself
titel: Guiding a Diffusion Model with a Bad Version of Itself
autor: "Tero Karras, Miika Aittala, Tuomas Kynkäänniemi, Jaakko Lehtinen, Timo Aila, Samuli Laine"
jahr: 2024
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2406.02507"
status: published
analyzed_at: "2026-07-31T10:43:55.374375+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Guiding a Diffusion Model with a Bad Version of Itself

## PROFIL

The text argues that image quality in image-generating diffusion models can be disentangled from prompt alignment and improved without reducing variation by using "autoguidance"—guiding generation with a smaller, less-trained version of the same model—rather than relying on classifier-free guidance (CFG). It sets itself against CFG, which entangles quality and alignment, suffers from task discrepancy between conditional and unconditional denoisers, and limits control over the sampling trajectory. By replacing the unconditional model with a degraded version of the main model, the method eliminates task discrepancy and achieves adaptive truncation along the data manifold. For arts education, this method offers a technical framework for generating high-fidelity, diverse synthetic images that can serve as customized visual references or creative assets in pedagogical settings.

## WISSEN

### Autoguidance: Disentangling Quality from Prompt Alignment

Classifier-free guidance (CFG) improves prompt alignment and image quality by steering a conditional denoiser away from an unconditional one, but these two effects are entangled and cannot be controlled separately. CFG also suffers from a task discrepancy: the conditional and unconditional denoisers solve different tasks, causing the sampling trajectory to overshoot the desired conditional distribution and yield skewed, simplified compositions. The authors observe that image-quality improvement can be disentangled from prompt alignment without reducing variation by guiding generation with a smaller, less-trained version of the same model—autoguidance—rather than an unconditional model. Because the guiding model shares the same conditioning and task as the main model, the task discrepancy problem is eliminated. The method is applicable to both conditional and unconditional diffusion models. It yields record FIDs of 1.01 (64×64) and 1.25 (512×512) on ImageNet using publicly available networks, with improvements confirmed by FID and FDDINOv2 metrics.

<!-- quelle: Abstract and Introduction -->

### Background on Diffusion and Classifier-Free Guidance

Denoising diffusion generates samples from p_data(x) by iteratively denoising white noise via a probability flow ODE that maintains x_σ ~ p(x_σ; σ). This requires evaluating the score function ∇_x log p(x; σ), approximated by a neural network D_θ(x; σ) trained for denoising, where ∇_x log p(x; σ) ≈ (D_θ(x; σ) - x) / σ². For conditional generation with label c, a denoiser D_θ(x; σ, c) is used.

Classifier-free guidance (CFG) addresses the failure of finite-capacity networks to reproduce training image clarity by extrapolating between two denoisers D_0 and D_1 by a factor w. Setting D_0 := D_θ(x; σ, ∅) and D_1 := D_θ(x; σ, c), the extrapolated score becomes ∇_x log p(x|c; σ) + (w-1)∇_x log p(c|x; σ), pushing samples towards higher likelihood of class c. However, p_w(x|c; σ) does not represent a valid heat diffusion of p_w(x|c; 0), so solving the ODE does not follow the density, leading to distorted trajectories, mode dropping, and over-saturation, despite improved image quality.

<!-- quelle: Background on Diffusion and Classifier-Free Guidance -->

### Why CFG Improves Image Quality: Mechanism Analysis

Unguided diffusion produces outliers because **score matching** yields a **conservative fit** — the model covers all training samples to avoid KL penalties, generating unlikely samples from distribution extremities it cannot fit accurately. A 2D toy dataset (low local dimensionality, hierarchical detail emergence) demonstrates this: unguided sampling scatters samples outside the distribution bulk.

CFG eliminates these outliers not merely by boosting class likelihood but by exploiting a quality gap between the conditional denoiser D₁ (focused on one class) and the unconditional D₀ (harder task, worse fit, more spread-out density). Guidance adds a force along ∇ log[p₁(x|c;σ)/p₀(x;σ)]; because p₀ falls off slower than the sharper p₁, this gradient points inward toward the data manifold, concentrating samples at high-probability regions.

This constitutes **adaptive truncation**: CFG identifies under-fit regions where denoiser predictions disagree and pushes samples toward better-fit areas. Naive truncation (uniformly lengthening score vectors, as in GAN truncation tricks) concentrates isotropically, emptying outer branches and reducing diversity — CFG's anisotropic correction follows the manifold's local orientation instead.

<!-- quelle: Why CFG Improves Image Quality: Mechanism Analysis -->

### Autoguidance Method and Synthetic Degradation Study

Autoguidance isolates image quality improvement by guiding a high-quality model D1 with an inferior version of itself, D0, trained on the same task but with additional degradations. Unlike discriminator guidance, the task is implicit and the distinction is between p1 and p0. Under limited capacity, score matching over-emphasizes low-probability regions; a weaker model makes similar errors more strongly. Autoguidance boosts the difference between D1 and D0: agreement yields insignificant perturbation, disagreement indicates direction toward better samples. The technique requires compatible degradations; D0 should exacerbate D1's inherent weaknesses, and the quality gap must outweigh random differences. A synthetic degradation study validates this:

- Base model: EDM2-S trained on ImageNet-512 without dropout (FID = 2.56).
- Dropout: D1 by applying 5% dropout to the base model (FID = 4.98), D0 by applying 10% dropout (FID = 15.00). Autoguidance best result (FID = 2.55) with w = 2.25.
- Input noise: D1 by modifying the base model to add noise to input images so noise level increased by 10% (FID = 3.96). σ conditioning input adjusted accordingly. D0 similarly with 20% increase (FID = 9.73). Autoguidance best result (FID = 2.56) with w = 2.00.
- Mismatched degradations: If corrupt D1 by dropout and D0 by input noise, or vice versa, guidance does not improve; best FID obtained by setting w = 1, i.e., disabling guidance and using less corrupted D1 exclusively.

The authors acknowledge these synthetic corruptions are not practically useful, as realistic models lack these specific degradations and would not achieve consistent truncation towards the data manifold.

<!-- quelle: Autoguidance Method and Synthetic Degradation Study -->

### Quantitative Results on ImageNet

Evaluation on ImageNet at 512×512 (latent diffusion) and 64×64 (RGB pixels), using EDM2 as baseline. Autoguidance employs a guiding model with two degradations: shorter training and reduced capacity relative to the main model. Both enabled together yields best results (e.g., EDM2-S with XS guiding model trained on 1/16th of iterations). Grid search optimizes guidance weight and EMA length per case.

Autoguidance improves FID and FDDINOv2 considerably. On ImageNet-512 with EDM2-S, FID drops from 2.56 to 1.34, beating CFG + Guidance Interval (1.68) and setting the best reported result regardless of model size. EDM2-XXL further lowers FID to 1.25 and FDDINOv2 to 24.18. On ImageNet-64, new records: FID 1.01, FDDINOv2 31.85.

Ablations show both degradations matter: reducing training only gives FID 1.51; reducing capacity only gives 2.13; same EMA for both models gives 1.53. Using different EMA lengths for main and guiding models is beneficial.

Autoguidance applies to unconditional models: EDM2-S unconditional FID drops from 11.67 to 3.86, a substantial improvement in a setting where results remain surprisingly poor.

<!-- quelle: Quantitative Results on ImageNet -->

### Ablation Studies and Parameter Sensitivity

Independent EMA lengths for the main and guiding models improve FID (1.34→1.53 when forced equal on ImageNet-512, EDM2-S). Two degradations—reduced training time and reduced capacity—were tested in isolation: same-capacity guiding model trained shorter yields FID 1.51; reduced-capacity guiding model trained equally long yields FID 2.13. Both degradations are beneficial and orthogonal, with reduced training contributing the majority of improvement. All ablations still outperform standard CFG.

Sensitivity analysis: best result at 1/16th the main model's training; halving further is near-equally good, doubling slowly compromises results. Results are insensitive to guidance weight. One capacity step smaller (XS for EDM2-S) is optimal; two steps smaller (XXS) still beats no reduction but shows excessive guidance-weight sensitivity. EMA length sensitivity persists, addressed via Post-hoc EMA.

Four explored degradations were NOT beneficial: (1) reducing training data for the guiding model; (2) applying guidance interval on top of autoguidance (reducing benefits, suggesting autoguidance helps at all noise levels); (3) deriving the guiding model via synthetic degradations (failed entirely, confirming the guiding model must exhibit the same degradations the main model suffers from); (4) further quantizing an already-quantized main model.

Limitation: a separate guiding model is required, but added cost is modest (+3.6% for EDM2-S/XS; +11% for EDM2-M/XXL).

<!-- quelle: Ablation Studies and Parameter Sensitivity -->

### Qualitative Results and DeepFloyd IF Application

On ImageNet-512, both CFG and the authors' method improve perceptual quality as guidance weight increases, but CFG converges toward a limited set of canonical images per class, while the authors' method maintains a wider gamut of compositions. The Palace example illustrates this: an atypical sample at w=1 is idealized by CFG as w rises. The Castle example, containing incompatible elements of multiple images, causes CFG to struggle, whereas the authors' method first builds the dominant red element into a castle, then focuses on the red foreground object with increased guidance. Greater output variety correlates with lower FID, indicating better training-data coverage.

Applied to DeepFloyd IF (a cascade of base model plus two superresolution stages), the method guides only the base model; superresolution always uses CFG. To combine autoguidance with CFG, the authors extend Equation 3 to multiple guiding models via linear interpolation of total guidance weight. CFG improves quality but simplifies style and layout toward canonical depiction; the authors' method similarly improves quality while better preserving style and visual complexity. Simultaneous use of both guiding methods is proposed as a new artistic control.

<!-- quelle: Qualitative Results and DeepFloyd IF Application -->

### Discussion and Future Work

Classifier-free guidance (CFG) entangles several phenomena; separating them and removing the superfluous connection to conditioning opens a new design space with better results. Future work should formally prove the conditions under which autoguidance is beneficial and derive rules for selecting the guiding model. The suggested guiding model—an early snapshot of a smaller model—is unavailable for current large-scale image generators, and successive training stages with changing data risk distribution shifts that violate assumptions. Whether perturbation-based guidance modifications (attention maps, denoiser inputs) benefit this setup remains open. Autoguidance shares conceptual ground with contrastive decoding in LLMs. Unlike noise-level-dependent CFG schedules, which suppress CFG at high noise levels because the image-quality benefit is overshadowed by reduced variation from large differences in differently conditioned distributions, autoguidance should not suffer this problem since both models target the same distribution. Only the interval method was tested in combination, without benefit. Needed: further combination studies (quantitative and artistic control) and alternative metrics—precision and recall, Human Preference Score, PickScore—to isolate the improvement's origin.

<!-- quelle: Discussion and Future Work -->

### References and Appendices

The appendix provides supplementary results and implementation details for the autoguidance method. Additional DeepFloyd IF results mirror the main paper's Figure 5, with rows at guidance weights w ∈ {1,2,3,4} and columns interpolating between CFG and autoguidance (XL-sized model guided by M-sized one). FID and FDDINOv2 sweeps over w on EDM2-S/ImageNet-512 show autoguidance is less sensitive to the exact choice of w than CFG. Visual grids on Tree frog, Minibus, and Mushroom classes (at exaggerated w = 4) demonstrate that CFG steers toward canonical templates while autoguidance preserves greater variation, though at the cost of saturation and artifacts at extreme guidance. Additional toy-example visualizations track how implied densities evolve during inference under both methods. Implementation used the public EDM2 codebase with NVIDIA A100 GPUs, PyTorch 2.2.0, CUDA 11.8; only one line in the sampling loop was modified to pass the class label to the guiding network alongside the main network. For four cases lacking pre-trained models, the authors trained models themselves. Algorithms 1 and 2 provide reproduction steps for Table 1 results.

<!-- quelle: References and Appendices -->

## GLOSSAR

- **classifier-free guidance (CFG)** — Standard method that steers a conditional denoiser away from an unconditional one to focus generation on well-learned high-probability regions, simultaneously improving prompt alignment and image quality at the cost of variation.
- **autoguidance** — Novel guidance method that uses a smaller or less-trained version of the same conditional model as the guiding signal, disentangling quality control from prompt alignment and avoiding the task discrepancy of CFG.
- **task discrepancy** — Problem arising in CFG because the conditional and unconditional denoisers are trained on different tasks, causing the sampling trajectory to overshoot the desired conditional distribution.
- **probability flow ODE** — An ODE that evolves a sample backward towards low noise levels while maintaining a specific distribution property.
- **score function** — The gradient of the log-density, ∇_x log p(x; σ), approximated by a denoiser network.
- **score matching** — Training objective closely related to maximum likelihood estimation that fits the data distribution's score (log-density gradient).
- **conservative fit** — A model tendency to cover all training samples broadly, including extremities it cannot represent accurately, to avoid high loss penalties.
- **adaptive truncation** — CFG's mechanism of identifying under-fit sample regions via conditional-unconditional denoiser disagreement and pushing samples toward better-fit areas along the manifold.
- **truncation towards the data manifold** — The consistent movement of generated samples toward the true data distribution.
- **guiding model** — A smaller, less-trained model derived from the same architecture as the main model, used to provide guidance signal in place of classifier-free guidance.
