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
checks: passed
review: passed
analyzed_at: "2026-11-15T11:42:23.690093+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: gedruckt
---

# Guiding a Diffusion Model with a Bad Version of Itself

## PROFIL

The paper "Guiding a Diffusion Model with a Bad Version of Itself" was written by Tero Karras, Miika Aittala, Tuomas Kynkäänniemi, Jaakko Lehtinen, Timo Aila, and Samuli Laine, affiliated with NVIDIA and Aalto University, as a research contribution on image-generating diffusion models. Its subject is the widely used classifier-free guidance (CFG) technique, and its central claim is that CFG entangles two separate effects — improved prompt alignment and improved image quality — which can be disentangled. The authors' "surprising" observation is that image quality can be improved without sacrificing variation by guiding generation not with an unconditional model but with a smaller, less-trained version of the model itself, a method they call "autoguidance"; they report record FID scores on ImageNet (1.01 at 64×64, 1.25 at 512×512) and note that the method also works for unconditional diffusion models, where CFG is inapplicable. The paper first reviews denoising diffusion and CFG, following the EDM framework of Karras et al., and identifies three drawbacks of CFG: it applies only to conditional generation, it produces skewed and overly simplified compositions due to task discrepancy between conditional and unconditional denoisers, and it cannot control prompt alignment and quality separately. Using a 2D toy example with a fractal-like synthetic distribution, the authors argue that CFG's quality improvement stems from pulling samples toward the core of the manifold — a form of "adaptive truncation" — while naive truncation fails by concentrating samples isotropically. The method section presents autoguidance, validated with synthetic corruptions (dropout, input noise) on EDM2-S trained on ImageNet-512, showing that mismatched degradations yield no benefit. Results on ImageNet-512 and ImageNet-64 with EDM2 models are followed by ablations on EMA lengths, training time, and model capacity, and by qualitative comparisons showing that CFG tends toward canonical images per class while autoguidance preserves a wider gamut of compositions. An application to the text-conditional DeepFloyd IF model extends the guidance equation to multiple guiding models, following Liu et al., and proposes combining CFG and autoguidance as a new artistic control. The discussion situates the method conceptually near contrastive decoding in large language models and outlines future work; implementation details, the toy example's setup, societal impact, and licenses close the paper. The work is usable in arts education contexts concerning generative AI, image synthesis, and the technical and artistic control of diffusion-based image generation.

## WISSEN

### Purpose and Thesis (p. 1–2)

This paper, authored by Tero Karras, Miika Aittala, Tuomas Kynkäänniemi, Jaakko Lehtinen, Timo Aila, and Samuli Laine (NVIDIA and Aalto University), argues that the popular classifier-free guidance (CFG) technique in image-generating diffusion models entangles two separate effects — improved prompt alignment and improved image quality — and that these can be disentangled. The authors' central, "surprising" observation is that image quality can be improved without sacrificing variation in the outputs by guiding generation not with an unconditional model (as CFG does) but with a smaller, less-trained version of the model itself. They call this method "autoguidance." The paper reports record FID scores on ImageNet generation: 1.01 for 64×64 and 1.25 for 512×512, using publicly available networks. A further advantage is that autoguidance also works for unconditional diffusion models, where CFG is inapplicable.

### Background: Denoising Diffusion and Classifier-Free Guidance (p. 2–3)

Denoising diffusion models generate images by reversing a stochastic corruption process: an image is revealed from pure noise by iterative denoising. Mathematically, the data distribution is viewed as undergoing heat diffusion into increasingly smoothed densities; sampling reverses this via a probability flow ODE. Solving the ODE requires evaluating the score function, approximated by a neural denoiser network D_θ(x; σ) trained for the denoising task. The authors follow the recommendations of Karras et al. (the EDM framework), including the schedule σ(t) = t. Conditioning inputs (class labels, text prompts) allow control over the output.

The training objective aims to cover the entire data distribution, which causes problems in low-probability regions: the model is penalized for not representing them but lacks the data to learn them well. CFG addresses this by "lowering the sampling temperature" — training a denoiser to operate both conditionally and unconditionally, then extrapolating between the two denoising results by a factor w. Setting w = 0 or w = 1 recovers either network's output; w > 1 over-emphasizes D_1. Guidance grants access to the score of an implied density p_w, which can be interpreted as increasing the likelihood a hypothetical classifier would assign to the sample coming from density p_1 rather than p_0.

The authors note three drawbacks of CFG: (1) it applies only to conditional generation; (2) because the unconditional and conditional denoisers solve different tasks, sampling trajectories can overshoot, producing skewed and overly simplified compositions; (3) prompt alignment and quality improvement cannot be controlled separately. They also stress that solving the ODE with the guided score does not produce samples from the implied distribution p_w, because it does not represent a valid heat diffusion — samples are "blindly pushed" toward higher implied density, causing distorted trajectories, exaggerated truncation, mode dropping, and color over-saturation.

### Why Does CFG Improve Image Quality? (p. 3–5)

The authors identify the mechanism behind CFG's quality improvement using a 2D toy example: a small denoiser network trained on a fractal-like synthetic distribution with two classes, exhibiting low local dimensionality and hierarchical emergence of detail — properties expected of the manifold of realistic images.

- **Score matching leads to outliers.** Unguided diffusion produces many extremely unlikely samples outside the bulk of the distribution (corresponding to unrealistic, broken images). The authors attribute this to the limited capability of the score network combined with the score matching objective, which — like maximum likelihood estimation — yields a "conservative" fit covering all training samples, including extremities that are not learned accurately. A weaker model's implied density is more spread out than a stronger model's.
- **CFG eliminates outliers.** In the toy example, CFG (w = 4) removes outliers but also drops entire branches of the distribution (reduced diversity). Crucially, samples are also pulled toward the core of the manifold. The authors attribute the quality improvement to this second phenomenon, arguing it stems from a quality difference between the conditional denoiser D_1 (which can focus on a single class) and the unconditional denoiser D_0 (which must generate from all classes at once with a small slice of the training budget, attaining a worse fit). Guidance adds a force pulling samples toward higher values of log[p_1(x|c;σ)/p_0(x|c;σ)]; because the weaker model's density falls off more slowly with distance from the manifold, the gradients point inward toward the data. The authors describe CFG as a form of "adaptive truncation" that identifies under-fit samples and pushes them toward better samples.
- **Naive truncation fails.** Uniformly lengthening score vectors by a factor w > 1 (analogous to the GAN truncation trick or lowering temperature in language models) concentrates samples isotropically, emptying outer branches and producing reduced variation, oversimplified details, and monotone texture.

### The Method: Autoguidance (p. 5–6)

The proposed method isolates the quality-improvement effect by guiding a high-quality model D_1 with a poor model D_0 trained on the same task, with the same conditioning and data distribution, but suffering from additional degradations such as low capacity and/or under-training. Because the guiding model is an inferior version of the main model itself, the method avoids CFG's task discrepancy problem. The rationale: a weaker version of the same model makes broadly similar errors in the same regions, only stronger. The difference between the two models' predictions indicates the direction toward better samples; where they agree, the perturbation is insignificant. Autoguidance requires that the two models' degradations be "compatible" — the quality gap must be large enough that systematic spreading-out of the density outweighs random effects (initialization, data shuffling).

A controlled experiment with synthetic corruptions applied to EDM2-S trained on ImageNet-512 (base FID = 2.56) validates the hypothesis:

- **Dropout:** D_1 with 5% dropout (FID = 4.98), D_0 with 10% dropout (FID = 15.00); autoguidance reaches FID = 2.55 at w = 2.25, matching the base model.
- **Input noise:** D_1 with 10% noise level increase (FID = 3.96), D_0 with 20% (FID = 9.73); autoguidance reaches FID = 2.56 at w = 2.00.
- **Mismatched degradations:** If D_1 is corrupted by dropout and D_0 by input noise (or vice versa), guidance does not help at all; the best FID is at w = 1 (guidance disabled).

The authors caution that these synthetic degradations are for validation only — real models do not suffer from them, so they would not yield consistent truncation in practice.

### Results on ImageNet (p. 6–7)

Evaluation uses ImageNet (ILSVRC2012) at 512×512 (latent diffusion) and 64×64 (RGB pixels), with EDM2 as the baseline (EDM2-S and EDM2-XXL models, 32 deterministic steps, 2nd-order Heun sampler). The guiding model uses two degradations — shorter training time and reduced capacity — with both enabled giving the best results. For EDM2-S, the guiding model is XS-sized and receives 1/16th of the main model's training iterations. Optimal guidance weight and EMA lengths were found by grid search.

Key quantitative results (Table 1):

- **ImageNet-512, EDM2-S:** baseline FID 2.56; CFG 2.23; CFG + Guidance Interval 1.68; autoguidance (XS, T/16) 1.34 — the best result for this dataset regardless of model size. FD_DINOv2 improves from 68.64 to 36.67 (vs. 46.25 for guidance interval).
- **ImageNet-512, EDM2-XXL:** autoguidance (M, T/3.5) reaches FID 1.25 and FD_DINOv2 24.18 (previous record 29.16).
- **ImageNet-64, EDM2-S:** autoguidance (XS, T/8) sets records of FID 1.01 and FD_DINOv2 31.85 (baseline 1.58; CFG 1.48; prior RIN 1.23).
- **Unconditional ImageNet-512, EDM2-S:** baseline FID 11.67 (practically no presentable images); autoguidance (XS, T/16) lowers it to 3.86, with FD_DINOv2 improving from 209.53 to 90.39.

### Ablations and Sensitivity (p. 7–8)

- **Independent EMA lengths** for main and guiding models are beneficial: forcing the same EMA worsens FID from 1.34 to 1.53 (ImageNet-512, EDM2-S).
- **Degradations in isolation:** reducing training only worsens FID to 1.51; reducing capacity only worsens it to 2.13. Both degradations are beneficial and orthogonal, but most of the improvement comes from reduced training of the guiding model. All ablations still outperform standard CFG.
- **Sensitivity:** training the guiding model 1/16th as much as the main model is optimal; halving that budget is almost as good, while doubling it slowly compromises results. Results are quite insensitive to guidance weight. One capacity step smaller (XS for EDM2-S) is best; two steps smaller (XXS) still beats no reduction but shows excessive sensitivity to w. Results are sensitive to EMA length; post-hoc EMA makes searching optimal parameters feasible.
- **Unsuccessful degradations:** reducing the guiding model's training data did not help; applying guidance interval on top of autoguidance reduced its benefits (suggesting autoguidance helps at all noise levels); synthetic degradations did not work at all; further quantizing an already-quantized main model did not yield a useful guiding model.
- **Cost:** the additional training cost is modest — about +11% for the EDM2-XXL/M pair (EDM2-M trains ~2.7× faster per iteration, trained for 1/3.5 of iterations) and only +3.6% for the EDM2-S/XS pair.

### Qualitative Results and DeepFloyd IF (p. 9–10)

On ImageNet-512 examples (Tree frog, Palace, Mushroom, Castle classes), both CFG and autoguidance improve perceptual quality, but CFG tends toward a limited number of canonical images per class, while autoguidance produces a wider gamut of compositions. For example, an atypical Palace image is idealized by CFG as guidance increases; a Castle image mixing incompatible elements is resolved differently by the two methods.

For large-scale text-conditional generation, the authors apply autoguidance to DeepFloyd IF (chosen because multiple differently-sized models are publicly available), specifically to its base model, while the two superresolution stages always use CFG. To combine autoguidance with CFG, they extend the guidance equation to multiple guiding models (following Liu et al.) and distribute the total guidance weight via linear interpolation between a CFG weight w_u and an autoguidance weight w_c. CFG improves quality but simplifies style and layout toward canonical depictions; autoguidance improves quality while better preserving style and visual complexity. The authors suggest using both simultaneously as a new artistic control.

### Discussion and Future Work (p. 10)

The authors conclude that CFG entangles several phenomena and that their perspective opens a new design space. Future directions include: formally proving the conditions under which autoguidance is beneficial; deriving rules of thumb for selecting the guiding model (an early snapshot of a smaller model is easy in principle but such snapshots are unavailable for current large-scale generators, and staged training with changing data could cause distribution shifts violating the assumptions); exploring whether attention-perturbation guidance methods could combine with autoguidance; and noting conceptual similarity to contrastive decoding in large language models. They also observe that noise-level-dependent guidance schedules in recent studies suppress CFG at high noise levels, where its quality benefit is outweighed by reduced variation — a problem autoguidance is not expected to suffer since both models target the same distribution. Further study with alternative metrics (precision and recall, Human Preference Score, PickScore) is suggested.

### Implementation Details (p. 14–16)

Experiments were built on the public EDM2 codebase (NVIDIA A100 GPUs, Python 3.11.7, PyTorch 2.2.0, CUDA 11.8, CuDNN 8.9.7). Only one line of the sampling loop had to be modified to pass class labels to the guiding network. Hyperparameters were optimized by automated grid search over five parameters: model capacity (all EDM2 sizes up to the main model), training time (powers of two, sweet spot always within {2^26, 2^27, 2^28, 2^29} images), guidance weight ([1.00, 3.50] at 0.05 intervals), and two separate EMA lengths ([0.010, 0.250] at 0.005 intervals). The search used local pruning around the best results, with each reported result being the best of three evaluations. In total, roughly 30,000 metric evaluations were performed; each generates 50,000 images (30–60 minutes on eight A100 GPUs, ~2–5 kWh), with the project's overall energy consumption in the ballpark of 60–150 MWh. For DeepFloyd IF, the Stochastic DDPM sampler was used with 100/75/50 steps for the three cascade stages and dynamic thresholding throughout.

### The 2D Toy Example (p. 16–19)

The toy dataset models each of two classes as a mixture of Gaussians forming a thin tree-like fractal structure: starting from one main branch, recursively subdividing six times into two sub-branches, each branch represented by 8 anisotropic Gaussian components — yielding 127 × 8 = 1016 components per class and 2032 in total. Ground truth scores and densities are analytically computable. The denoisers are multi-layer perceptrons (one input layer, four hidden layers, SiLU activations, magnitude-preserving design from EDM2), designed to output the logarithm of an unnormalized probability density, from which scores are derived via automatic differentiation; alternative formulations (direct score or denoised output) gave qualitatively identical results. D_1 has n = 64 hidden features, D_0 has n = 32. Models are trained with exact score matching (denoising score matching showed no noticeable differences): D_1 for 4096 iterations, D_0 for 512, batch size 4096. Sampling uses the standard EDM sampler with N = 32 Heun steps (NFE = 63), σ_min = 0.002, σ_max = 5, ρ = 7. In Figure 1, w = 4 for CFG, w = 3 for autoguidance, and score vectors multiplied by 1.40 for naive truncation.

### Societal Impact and Licenses (p. 19)

The authors acknowledge that generative modeling has significant misuse potential, including disinformation and amplification of stereotypes and unwanted biases, and that improved sample quality can make results more believable even when used for disinformation — though the method does not unlock novel uses of the technology. Licenses: EDM2 models under Creative Commons BY-NC-SA 4.0; DeepFloyd IF under a modified MIT license; Stable Diffusion VAE under CreativeML Open RAIL++-M; InceptionV3 and DINOv2 under Apache 2.0; ImageNet under a custom non-commercial license.

### Figures (p. 4–15)

*Fig. 1 (p. 4):* A fractal-like 2D distribution with two classes indicated with gray and orange regions. Approximately 99% of the probability mass is inside the shown contours. (a) Ground truth samples drawn directly from the orange class distribution. (b) Conditional sampling using a small denoising diffusion model generates outliers. (c) Classifier-free guidance ( w = 4 ) eliminates outliers but reduces diversity by over-emphasizing the class. (d) Naive truncation via lengthening the score vectors. (e) Our method concentrates samples on high-probability regions without reducing diversity. — The image is a figure made of five square panels arranged in one horizontal row, each showing a dark branching, tree-like pattern over a faint gray background. Beneath the panels are the legible labels “(a) Ground truth”, “(b) No guidance”, “(c) Classifier-free guidance”, “(d) Naive truncation”, and “(e) Autoguidance (ours)”. Panel (b) has many small scattered gray points around the branches, panels (c) and (d) show orange outer branches with darker central branches and panel (c) includes a small green rectangular outline near the top, while panel (e) shows mostly dark branches with only sparse orange tips.

*Fig. 2 (p. 4):* Closeup of the region highlighted in Figure 1c. (a) The implied learned density p 1 ( x | c ; σ mid ) (green) at an intermediate noise level σ mid and its score vectors (log-gradients), plotted at representative sample points. The learned density approximates the underlying ground truth p ( x | c ; σ mid ) (orange) but fails to replicate its sharper details. (b) The weaker unconditional model learns a further spread-out density p 0 ( x ; σ mid ) (red) with a looser fit to the data. (c) Guidance moves the points according to the gradient of the (log) ratio of the two learned densities (blue). As the higher-quality model is more sharply concentrated at the data, this field tends inward towards the data distribution. The corresponding gradient is simply the difference of respective gradients in (a) and (b), illustrated at selected points. (d) Sampling trajectories taken by standard unguided diffusion following the learned score ∇ x log p 1 ( x | c ; σ ) , from noise level σ mid to 0 . The contours (orange) represent the ground truth noise-free density. (e) Guidance introduces an additional force shown in (c), causing the points to concentrate at the core of the data density during sampling. — The image is a five-panel scientific diagram arranged left to right as (a)–(e). Panels (a), (b), and (c) are contour plots with black sample points and small arrows—green in (a), red in (b), and blue in (c)—over shaded regions, with the legible subcaptions “(a) p₁(x|c; σ_mid)”, “(b) p₀(x; σ_mid)”, and “(c) Ratio p₁/p₀”. Panels (d) and (e) show beige branching, tree-like structures dotted with black points and short line segments, labeled “(d) No guidance” and “(e) CFG with w = 4”; panel (e) also contains a small green mark near the upper branches. _(Lettering in the image, read by the image model, not confirmed: “(a) p₁(x|c; σ_mid)”, “(b) p₀(x; σ_mid)”)_

*Fig. 3 (p. 7):* Sensitivity w.r.t. autoguidance parameters, using EDM2-S on ImageNet-512. The shaded regions indicate the min/max FID over 3 evaluations. (a) Sweep over guidance weight w while keeping all other parameters unchanged. The curves correspond to how much the guiding model was trained relative to the number of images shown to the main model. (b) Sweep over guidance weight for different guiding model capacities. (c) Sweep over the two EMA length parameters for our best configuration, denoted with ⋆ in (a) and (b). — The image is a three-panel line-chart figure with a vertical “FID” axis on each panel. Panel (a), captioned “(a) Guidance weight & training,” plots three U-shaped curves labeled “T/32,” “T/16*,” and “T/8” against an x-axis marked “w=1.0” to “3.0,” with the numeric labels “1.47,” “1.40,” and “1.34” near the minima. Panel (b), captioned “(b) Guidance weight & capacity,” plots curves labeled “XXS,” “XS*,” and “S” over the same “w” axis, with labels “1.41,” “1.34,” and “1.51.” Panel (c), captioned “(c) EMA length parameters,” plots two curves labeled “EMA_m” and “EMA_g” against an x-axis marked “EMA = 0.05,” “0.10,” and “0.15,” each with a “1.34” label near its minimum. _(Lettering in the image, read by the image model, not confirmed: “EMA_m”, “EMA_g”)_

*Fig. 4 (p. 8):* Example results for the Tree frog, Palace, Mushroom, Castle classes of ImageNet-512 using EDM2-S. Guidance weight increases to the right; rows are classifier-free guidance and our method. — The picture is a figure panel made of a grid of photorealistic images arranged in four rows and six columns. The rows are labeled on the left as “CFG”, “Ours”, “CFG”, and “Ours”, and the columns are labeled at the top as “w = 1”, “w = 2”, and “w = 3” over each group of three images. The top-left group shows green tree frogs on leaves, the top-right group shows a large palace-like building and courtyard, the bottom-left group shows mushrooms, and the bottom-right group shows castle-like red buildings.

*Image 5 (p. 9):* — The picture is a grid of twenty computer-generated images arranged in four rows and five columns, each showing a blue jay bird with colorful macarons. Vertical text on the left side reads "Increasing CFG weight" with a downward arrow, and vertical text on the right side reads "Increasing guidance weight for our method" with a downward arrow. The images display the bird perched on stacks of macarons, in glass jars, baskets, bowls, or on scattered piles, with backgrounds ranging from plain colored backdrops to outdoor greenery.

*Image 6 (p. 13):* — This is a figure made of a 4-by-6 grid of rendered images, each showing a multi-masted sailing ship on calm water among clouds. Across each row the pictures change from bright, lightly colored ships under a blue sky on the left to dark silhouetted ships against an orange-purple sunset on the right. Above the grid, the legible text reads “Interpolation between CFG and our method,” and there is vertical text along the left and right edges that is not fully legible.

*Image 7 (p. 13):* — The picture is a grid of twenty-four images arranged in four rows and six columns, each showing a castle scene. The scenes vary from realistic castle views on the left to increasingly stylized, fantastical castles integrated with trees on the right. Vertical text on the left side reads "Increasing CFG weight" with a downward arrow, and vertical text on the right side reads "Increasing guidance weight for our method" with a downward arrow.

*Fig. 7 (p. 14):* Sweep over guidance weight w using EDM2-S on ImageNet-512. The optimal EMA length was searched separately for the three methods and two metrics (FID and FDDINOv2). — The image is a two-panel line chart. Panel (a), labeled “(a) FID,” plots three curves identified in a legend as “Classifier-free guidance,” “Guidance interval,” and “Autoguidance (ours)” over guidance weight w, with the x-axis marked “w=1.0” and annotated values “2.23,” “1.68,” and “1.34.” Panel (b), labeled “(b) FD” with “DINOv2” in subscript, shows the same three curves over w with annotated values “52.32,” “36.67,” and “46.25.” _(Lettering in the image, read by the image model, not confirmed: “(b) FD”, “DINOv2”)_

*Fig. 8 (p. 14):* Resulting variation for CFG and our method in Tree frog, Minibus, Mushroom classes of ImageNet-512 using EDM2-S (FDDINOv2-optimized). In this image, we have exaggerated the amount of guidance ( w = 4 ) to make its effect on variation more clearly visible. This causes excessive saturation and other image artifacts, but clearly shows that CFG steers towards canonical templates, while our method preserves much greater variation. — It is a grid of small color photographs arranged in two labeled rows, “CFG” and “Ours”, and three columns of object classes. The left column shows tree frogs, the middle column shows minibuses/vans, and the right column shows mushrooms. In the “CFG” row the frogs, vans, and mushrooms repeat very similar poses, colors, and compositions, whereas in the “Ours” row the same classes show visibly more varied poses, colors, vehicle types, and mushroom forms. Only the two row labels “CFG” and “Ours” are legible text.

*Fig. 9 (p. 15):* Progression of implied learned densities during sampling over various σ in a setup similar to Figure 2. Contours of the corresponding ground truth distributions are also shown. (a) Main model density p 1 ( x | c ; σ ) . (b) Unconditional guiding model density p 0 ( x ; σ ) in CFG. (c) Conditional guiding model density p 0 ( x | c ; σ ) in autoguidance. (d) With CFG, guidance towards higher ratio p 1 /p 0 pushes samples towards top right, especially at high σ (top rows). (e) With autoguidance, this anomalous effect does not occur and samples cover the entire class c . — This is a scientific diagram: a 5-by-5 grid of plots with columns headed (a) through (e) and rows labeled “σ = 0.5,” “σ = 0.25,” “σ = 0.08,” “σ = 0.03,” and “σ = 0.01.” The first three columns show filled contour plots in green and orange tones, while the last two columns show blue contour backgrounds with gray regions and black scattered points. Moving down the rows, the contours change from smooth concentric blobs at the top to increasingly branched, tree-like shapes at the bottom. Legible column headers include “(b) CFG,” “(c) Autoguidance,” “(d) CFG ratio p₁/p₀,” and “(e) Autoguidance ratio p₁/p₀.”

<!-- quelle: Guiding a Diffusion Model with a Bad Version of Itself (p. 1–19) -->

## LITERATUR

<!-- quelle: References (p. 10–12) -->

- D. Ahn, H. Cho, J. Min, W. Jang, J. Kim, S. Kim, H. H. Park, K. H. Jin, and S. Kim. Self-rectifying diffusion sampling with perturbed-attention guidance. In Proc. ECCV , 2024.
- F. Bao, S. Nie, K. Xue, Y. Cao, C. Li, H. Su, and J. Zhu. All are worth words: A ViT backbone for diffusion models. In Proc. CVPR , 2023.
- C. M. Bishop. Neural networks for pattern recognition . Oxford University Press, USA, 1995.
- A. Brock, J. Donahue, and K. Simonyan. Large scale GAN training for high fidelity natural image synthesis. In Proc. ICLR , 2019.
- B. C. A. Brown, A. L. Caterini, B. L. Ross, J. C. Cresswell, and G. Loaiza-Ganem. Verifying the union of manifolds hypothesis for image data. In Proc. ICLR , 2023.
- H. Chang, H. Zhang, J. Barber, A. Maschinot, J. Lezama, L. Jiang, M.-H. Yang, K. Murphy, W. T. Freeman, M. Rubinstein, Y. Li, and D. Krishnan. Muse: Text-to-image generation via masked generative transformers. In Proc. ICML , 2023.
- K. Crowson, S. A. Baumann, A. Birch, T. M. Abraham, D. Z. Kaplan, and E. Shippole. Scalable high-resolution pixel-space image synthesis with hourglass diffusion transformers. In Proc. ICML , 2024.
- J. Deng, W. Dong, R. Socher, L.-J. Li, K. Li, and L. Fei-Fei. ImageNet: A large-scale hierarchical image database. In Proc. CVPR , 2009.
- P. Dhariwal and A. Nichol. Diffusion models beat GANs on image synthesis. In Proc. NeurIPS , 2021.
- S. Dieleman. Guidance: A cheat code for diffusion models. Blog post. https://sander.ai/2022/05/ 26/guidance.html , 2022.
- S. Gao, P. Zhou, M.-M. Cheng, and S. Yan. MDTv2: Masked diffusion transformer is a strong image synthesizer. In Proc. ICCV , 2023.
- D. Hendrycks and K. Gimpel. Gaussian error linear units (GELUs). CoRR , abs/1606.08415, 2016.
- M. Heusel, H. Ramsauer, T. Unterthiner, B. Nessler, and S. Hochreiter. GANs trained by a two time-scale update rule converge to a local Nash equilibrium. In Proc. NIPS , 2017.
- J. Ho, W. Chan, C. Saharia, J. Whang, R. Gao, A. Gritsenko, D. P. Kingma, B. Poole, M. Norouzi, D. J. Fleet, and T. Salimans. Imagen Video: High definition video generation with diffusion models. CoRR , abs/2210.02303, 2022.
- J. Ho, A. Jain, and P. Abbeel. Denoising diffusion probabilistic models. In Proc. NeurIPS , 2020.
- J. Ho and T. Salimans. Classifier-free diffusion guidance. In Proc. NeurIPS 2021 Workshop on Deep Generative Models and Downstream Applications , 2021.
- S. Hong. Smoothed energy guidance: Guiding diffusion models with reduced energy curvature of attention. In Proc. NeurIPS , 2024.
- S. Hong, G. Lee, W. Jang, and S. Kim. Improving sample quality of diffusion models using self-attention guidance. In Proc. ICCV , 2023.
- E. Hoogeboom, J. Heek, and T. Salimans. Simple diffusion: End-to-end diffusion for high resolution images. In Proc. ICML , 2023.
- A. Hyvärinen. Estimation of non-normalized statistical models by score matching. JMLR , 6(24):695-709, 2005.
- A. Jabri, D. J. Fleet, and T. Chen. Scalable adaptive computation for iterative generation. In Proc. ICML , 2023.
- A. Jolicoeur-Martineau, K. Li, R. Piché-Taillefer, T. Kachman, and I. Mitliagkas. Gotta go fast when generating data with score-based models. CoRR , abs/2105.14080, 2021.
- T. Karras, M. Aittala, T. Aila, and S. Laine. Elucidating the design space of diffusion-based generative models. In Proc. NeurIPS , 2022.
- T. Karras, M. Aittala, J. Lehtinen, J. Hellsten, T. Aila, and S. Laine. Analyzing and improving the training dynamics of diffusion models. In Proc. CVPR , 2024.
- D. Kim, Y. Kim, S. J. Kwon, W. Kang, and I.-C. Moon. Refining generative process with discriminator guidance in score-based diffusion models. In Proc. ICML , 2023.
- Y. Kirstain, A. Polyak, U. Singer, S. Matiana, J. Penna, and O. Levy. Pick-a-Pic: An open dataset of user preferences for text-to-image generation. In Proc. NeurIPS , 2023.
- T. Kynkäänniemi, M. Aittala, T. Karras, S. Laine, T. Aila, and J. Lehtinen. Applying guidance in a limited interval improves sample and distribution quality in diffusion models. In Proc. NeurIPS , 2024.
- T. Kynkäänniemi, T. Karras, S. Laine, J. Lehtinen, and T. Aila. Improved precision and recall metric for assessing generative models. In Proc. NeurIPS , 2019.
- X. L. Li, A. Holtzman, D. Fried, P. Liang, J. Eisner, T. Hashimoto, L. Zettlemoyer, and M. Lewis. Contrastive decoding: Open-ended text generation as optimization. In Proc. ACL , 2023.
- L. Liu, Y. Ren, Z. Lin, and Z. Zhao. Pseudo numerical methods for diffusion models on manifolds. In Proc. ICLR , 2022.
- N. Liu, S. Li, Y . Du, A. Torralba, and J. B. Tenenbaum. Compositional visual generation with composable diffusion models. In Proc. ECCV , 2022.
- S. Lyu. Interpretation and generalization of score matching. In Proc. UAI , 2009.
- M. Marchesi. Megapixel size image creation using generative adversarial networks. CoRR , abs/1706.00082, 2017.
- P. Mishkin, L. Ahmad, M. Brundage, G. Krueger, and G. Sastry. DALL · E 2 preview - risks and limitations. OpenAI , 2022.
- A. Nichol and P. Dhariwal. Improved denoising diffusion probabilistic models. In Proc. ICML , 2021.
- A. Nichol, P. Dhariwal, A. Ramesh, P. Shyam, P. Mishkin, B. McGrew, I. Sutskever, and M. Chen. GLIDE: Towards photorealistic image generation and editing with text-guided diffusion models. In Proc. ICML , 2022.
- M. Oquab, T. Darcet, T. Moutakanni, H. V. Vo, M. Szafraniec, V. Khalidov, P. Fernandez, D. Haziza, F. Massa, A. El-Nouby, M. Assran, N. Ballas, W. Galuba, R. Howes, P.-Y. Huang, S.-W. Li, I. Misra, M. Rabbat, V. Sharma, G. Synnaeve, H. Xu, H. Jegou, J. Mairal, P. Labatut, A. Joulin, and P. Bojanowski. DINOv2: Learning robust visual features without supervision. TMLR , 2024.
- W. Peebles and S. Xie. Scalable diffusion models with transformers. In Proc. ICCV , 2023.
- B. Poole, A. Jain, J. T. Barron, and B. Mildenhall. DreamFusion: Text-to-3D using 2D diffusion. In Proc. ICLR , 2023.
- P. Pope, C. Zhu, A. Abdelkader, M. Goldblum, and T. Goldstein. The intrinsic dimension of images and its impact on learning. In Proc. ICLR , 2021.
- A. Ramesh, P. Dhariwal, A. Nichol, C. Chu, and M. Chen. Hierarchical text-conditional image generation with CLIP latents. CoRR , abs/2204.06125, 2022.
- R. Rombach, A. Blattmann, D. Lorenz, P. Esser, and B. Ommer. High-resolution image synthesis with latent diffusion models. In Proc. CVPR , 2022.
- A. Sabour, S. Fidler, and K. Kreis. Align your steps: Optimizing sampling schedules in diffusion models. In Proc. ICML , 2024.
- S. Sadat, J. Buhmann, D. Bradley, O. Hilliges, and R. M. Weber. CADS: Unleashing the diversity of diffusion models through condition-annealed sampling. In Proc. ICLR , 2024.
- C. Saharia, W. Chan, S. Saxena, L. Li, J. Whang, E. Denton, S. K. S. Ghasemipour, B. K. Ayan, S. S. Mahdavi, R. G. Lopes, T. Salimans, J. Ho, D. J. Fleet, and M. Norouzi. Photorealistic text-to-image diffusion models with deep language understanding. In Proc. NeurIPS , 2022.
- J. Sohl-Dickstein, E. Weiss, N. Maheswaranathan, and S. Ganguli. Deep unsupervised learning using nonequilibrium thermodynamics. In Proc. ICML , 2015.
- J. Song, C. Meng, and S. Ermon. Denoising diffusion implicit models. In Proc. ICLR , 2021.
- Y. Song and S. Ermon. Generative modeling by estimating gradients of the data distribution. In Proc. NeurIPS , 2019.
- Y. Song, J. Sohl-Dickstein, D. P. Kingma, A. Kumar, S. Ermon, and B. Poole. Score-based generative modeling through stochastic differential equations. In Proc. ICLR , 2021.
- Stability AI. DeepFloyd IF. GitHub repository. https://github.com/deep-floyd/IF , 2023.
- G. Stein, J. C. Cresswell, R. Hosseinzadeh, Y. Sui, B. L. Ross, V. Villecroze, Z. Liu, A. L. Caterini, J. E. T. Taylor, and G. Loaiza-Ganem. Exposing flaws of generative model evaluation metrics and their unfair treatment of diffusion models. In Proc. NeurIPS , 2023.
- C. Szegedy, V. Vanhoucke, S. Ioffe, J. Shlens, and Z. Wojna. Rethinking the Inception architecture for computer vision. In Proc. CVPR , 2016.
- P. Vincent. A connection between score matching and denoising autoencoders. Neural Computation , 23(7):1661-1674, 2011.
- X. Wang, N. Dufour, N. Andreou, M.-P. Cani, V. F. Abrevaya, D. Picard, and V. Kalogeiton. Analysis of classifier-free guidance weight schedulers. TMLR , 2024.
- X. Wu, Y. Hao, K. Sun, Y. Chen, F. Zhu, R. Zhao, and H. Li. Human Preference Score v2: A solid benchmark for evaluating human preferences of text-to-image synthesis. CoRR , abs/2306.09341, 2023.
- L. Zhang, A. Rao, and M. Agrawala. Adding conditional control to text-to-image diffusion models. In Proc. ICCV , 2023.
- Q. Zhang and Y. Chen. Fast sampling of diffusion models with exponential integrator. In Proc. ICLR , 2023.
- C. Zheng and Y. Lan. Characteristic guidance: Non-linear correction for diffusion model at large guidance scale. In Proc. ICML , 2024.

## GLOSSAR

- **Autoguidance** — The paper's proposed method of guiding a high-quality diffusion model with an inferior version of itself (smaller capacity and/or less-trained, with unchanged conditioning), isolating image-quality improvement from prompt alignment and preserving variation.
- **Classifier-free guidance (CFG)** — The standard technique of using an unconditional model to guide a conditional model, improving prompt alignment and quality at the cost of reduced variation; the paper analyzes and critiques it.
- **Guidance interval** — A concurrently proposed method (by other authors) that restricts CFG to a subset of noise levels; the paper compares against it and finds it unhelpful in combination with autoguidance.
- **Score function** — The gradient of the log-probability density, ∇_x log p(x; σ), approximated by a trained denoiser network; the quantity evaluated at each ODE step.
- **Probability flow ODE** — The ordinary differential equation whose solution evolves a noise sample backward toward the data distribution while maintaining the property that the sample follows the smoothed density at each noise level.
- **Implied density p_w** — The density whose score guidance grants access to via extrapolation between two denoisers; notably not a valid heat diffusion of p_w(x|c; 0), so guided sampling does not truly sample from it.
- **Adaptive truncation** — The paper's interpretation of CFG as identifying likely under-fit samples (where the two denoisers disagree) and pushing them toward better samples.
- **Conservative fit** — The tendency of maximum-likelihood-style objectives (and score matching) to cover all training samples, including unlikely extremities the model cannot learn accurately.
- **Post-hoc EMA** — A technique from EDM2 allowing the exponential moving average length of a trained model to be adjusted after training, enabling feasible hyperparameter search over EMA lengths.
- **FD_DINOv2** — A distribution-distance metric (Fréchet distance computed with DINOv2 features) used alongside FID to evaluate generated image quality.
- **FID** — Fréchet Inception Distance, the standard metric for evaluating the quality and diversity of generated image distributions.
- **Naive truncation** — Uniformly lengthening score vectors by a factor w > 1 (analogous to the GAN truncation trick), which concentrates samples isotropically and reduces variation.
- **Compatible degradations** — The requirement that the guiding model suffer from the same kinds of degradations (e.g., limited capacity, under-training) as the main model, only stronger, for autoguidance to work.
