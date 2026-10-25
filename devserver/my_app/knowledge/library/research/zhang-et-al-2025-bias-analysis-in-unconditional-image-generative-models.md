---
id: zhang-et-al-2025-bias-analysis-in-unconditional-image-generative-models
titel: Bias Analysis in Unconditional Image Generative Models
autor: "Xiaofeng Zhang, Michelle Lin, Simon Lacoste-Julien, Aaron Courville, Yash Goyal"
jahr: 2025
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, bias]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2506.09106"
status: published
analyzed_at: "2026-07-31T10:50:17.747131+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Bias Analysis in Unconditional Image Generative Models

## PROFIL

This text argues that attribute bias shift in unconditional image generative models is primarily driven by the sensitivity of the attribute classifier's decision boundaries, particularly when these boundaries fall in high-density regions of spectrum-based attributes. It sets itself against prior studies that attribute bias shift to caption-prompt discrepancies or fail to isolate the unconditional generator's contribution due to confounding factors like conditional classifier-free guidance (CFG). By training unconditional diffusion models and GANs on labeled datasets, the authors demonstrate that small distributional translations can produce large apparent bias shifts depending on the classifier used. For arts education, the text underscores the necessity of scrutinizing evaluation frameworks and adopting representative labeling practices when analyzing representational harm in AI-generated visual content used in pedagogical settings.

## WISSEN

### Bias Shift in Unconditional Image Generative Models

Existing studies on bias shift between training and generation distributions yield inconclusive results, with some attributing shift to caption-prompt discrepancies. This work isolates the unconditional generator's contribution by excluding conditional classifier-free guidance (CFG), which reduces output diversity and may confound bias measurement. Bias is defined as the difference between the probability of an attribute's presence in the observed distribution and its expected proportion in an ideal reference distribution; bias shift is operationalized as attribute frequency shift from training to generation. Unconditional diffusion models and GANs are trained on CelebA and DeepFashion, with a single classifier labeling both evaluation and generated sets for consistent comparison.

Key findings:
- Attribute bias shift occurs; its magnitude correlates with the spectrum-based (non-binary) nature of the attribute.
- BigGAN models exhibit larger shifts than diffusion models despite comparable FID scores.
- Classifier decision boundary density is a strong predictor of shift sensitivity: when boundaries fall in high-density regions, small distributional translations produce large apparent bias shifts, and vice versa.

This classifier sensitivity is most pronounced for attributes lying on a spectrum rather than exhibiting binary nature, underscoring the need for more representative labeling practices and scrutiny of evaluation frameworks.

<!-- quelle: Introduction and Problem Framing -->

### Related Works: Bias in Image Generation, Train–Generation Shift, and Label Prediction

Prior work on social bias in image generation concludes that T2I models fail to reflect U.S. labor statistics, but studies differ in model selection and benchmarks. Critically, T2I models contain multiple components that may contribute to generative biases; this work isolates the **unconditional image generative model** that directly outputs images without text conditioning or guidance.

Few studies compare bias between generation and training distributions. Existing efforts rely on Stable Diffusion trained on LAION-5B, which lacks explicit attribute labels. One approach subsets LAION-5B via pre-trained image-prompt similarity [15]; another uses caption keywords [16], risking omission of relevant images. To avoid large-scale dataset search and unreliable subset comparison, the authors train generative models on datasets with labeled attributes, ensuring reliable bias estimation across both distributions.

For attribute label prediction on generated images, prior methods infer labels via CLIP representation space, zero-shot VQA with BLIP-2/BLIP, or ViT captioning—yet pre-trained models introduce their own biases, making predicted labels unreliable. Others train classifiers on external supervised datasets. The authors instead train the attribute classifier on the same dataset used for analysis, yielding more accurate predictions and enabling **bias shift evaluation metrics** computed from classifier-predicted labels across training, validation, and generation sets.

<!-- quelle: Related Works -->

### Bias Evaluation Method

Bias is defined as the difference between an attribute's probability in the observed distribution and its expected proportion in an ideal reference distribution. For a set of binary attributes **C**, data bias is measured relative to P_ideal(C), using P_train(C) or P_val(C) as estimation.

The **bias shift evaluation framework** trains unconditional generative models without ground-truth labels, generates 10,000 images per checkpoint, and applies a trained classifier to obtain attribute labels for generated images. The authors acknowledge classifier bias but mitigate it by using the same classifier for both dataset and generation set, and by using P_val(C) rather than P_train(C) to avoid overfitting.

**Attribute bias shift** is defined as the difference between generation bias and training bias; P_ideal(C) cancels out, making the metric independent of ideal reference selection. This equals attribute frequency shift from training to generation; values near 0 indicate equivalent bias levels.

**Average attribute bias shift (ABS)** measures overall magnitude across all attributes as an absolute percentage difference. Averaging is justified because bias shifts are always positive and attributes are non-protected (color, shape, texture).

<!-- quelle: Bias Evaluation Method -->

### Experimental Setup

The framework is applied to two real image datasets: CelebA (200K+ celebrity facial images, 40 binary attributes) and DeepFashion (800K+ fashion images, subset with 26 fine-grained attributes). Official train/validation/test splits are used. The study examines attribute bias shift over fine-grained attributes, clarified as attribute-specific rather than social bias w.r.t. protected attributes.

Backbone models follow the ADM setup, trained at three sizes (tiny/small/large) by adjusting U-Net bottleneck channels (32/64/256). Default results use the large model. 10,000 images per checkpoint are generated with 100 inference steps. Two classifiers are employed: ResNeXt-50 (main paper) and Swin Transformer (appendix). A BigGAN model is trained for GAN comparison.

Evaluation metrics for image generation:
- FID (Fréchet Inception Distance)
- KID (Kernel Inception Distance)
- FLD (Feature Likelihood Divergence): evaluates quality, diversity, and novelty
- Generalization gap: positive values indicate no overfitting

DINOv2 is used as feature extractor for FID, KID, and FLD; a conventional FID implementation provides comparable quality values.

<!-- quelle: Experimental Setup -->

### Backbone Models Performance

Diffusion models trained on CelebA and DeepFashion are evaluated via FID, KID, and FLD. FID and KID converge to small values, indicating good image quality and mode coverage. FLD corroborates conventional metrics, showing no severe memorization. The generalization gap yields positive or slight negative values, indicating no overfitting.

The classifier achieves over 80% validation accuracy on most attributes, with average accuracy of 91.7% for CelebA and 90.5% for DeepFashion.

Pre-sigmoid logit distributions reveal a structural distinction: for **spectrum-based attributes**, the decision boundary consistently falls in a **high-density region** of the logit distribution (Figs. 5a–5b, 6a–6b), whereas for **non-spectrum-based attributes**, it falls in a **low-density region** (Figs. 5c–5d, 6c). This pattern holds across both datasets, suggesting that spectrum-based attributes are harder to separate — the classifier's decision boundary cuts through the most populated part of the logit space — while non-spectrum-based attributes enjoy clearer separation.

<!-- quelle: Backbone Models Performance -->

### Average Attribute Bias Shift Evaluation

ABS remains perceivable even when image generation metrics are small, confirming non-negligible attribute bias shifts between training and generation distributions. Crucially, ABS does not consistently track image generation metrics: models with superior generation metrics are not necessarily less biased. Bias must therefore be treated as an independent issue, distinct from quality and diversity. While diversity metrics assess mode coverage in the generated distribution, bias evaluation should focus on the relative proportions of these modes. On CelebA, ABS fluctuates after 300K steps while generation metrics plateau; on DeepFashion, generation metrics keep improving while ABS stabilizes after ~200K steps. Sampling 10,000 generated images suffices for reliable estimation: ABS between sampled validation subsets and the full validation set is far smaller than ABS between the generation set and full validation set, confirming observed shifts exceed sampling variance. Attributes are categorized into spectrum-based and non-spectrum-based (Table 1). Non-spectrum-based ABS converges to small values (0.71% CelebA, 0.98% DeepFashion), while spectrum-based ABS reaches significantly larger minima (3.25% CelebA, 4.73% DeepFashion).

<!-- quelle: Average Attribute Bias Shift Evaluation -->

### Decision Boundary Density Explains Attribute Bias Shift Magnitude

The classifier is analyzed to explain why some attributes undergo larger *attribute bias shifts* than others. Visualizing pre-sigmoid logit distributions for CelebA and DeepFashion attributes reveals that the decisive factor is **density at the decision boundary**: attributes with large bias shifts have boundaries falling in high-density regions, whereas small-shift attributes have boundaries in low-density regions. Using validation-set density at the boundary, attributes are categorized via a threshold of 0.01: above it, *spectrum-based*; below, non-spectrum-based. Spectrum-based attributes are more sensitive to distribution shifts because moving density mass across a high-density boundary is comparatively easy. Non-spectrum-based attributes' distributions still change between training and generation sets, but their low-density boundaries make cross-boundary transport difficult, yielding small bias shifts. Empirically, training-to-generation distribution shifts exhibit low earth mover's distance (EMD), consistent with the observation that significant reweighting of well-separated modes would require large EMD.

<!-- quelle: Decision Boundary Sensitivity Analysis -->

### Model Comparison and Per-Attribute Bias Shift Analysis

Comparing diffusion models of varying U-Net bottleneck sizes (32/64/256 channels) against BigGAN, the tiny diffusion model is excluded for failing to produce realistic images. Although FLD is similar for the large diffusion model and BigGAN, ABS diverges sharply: BigGAN exhibits considerably larger bias shifts, attributed to GAN mode collapse. The small diffusion model shows larger and more fluctuating bias shifts than the large model, with average ABS increasing after 300K steps despite stable FLD. Generated images from BigGAN and the small model appear more 'washed out,' with fewer variations and details.

Per-attribute analysis distinguishes spectrum-based attributes (e.g., Rosy Cheeks, Smiling, Young on CelebA; Floral, Solid, Cotton on DeepFashion) from non-spectrum-based attributes (e.g., Eyeglasses, Bald, Male on CelebA; Striped, Leather on DeepFashion). Spectrum-based attributes exhibit a gap between generation and validation probabilities and greater fluctuations throughout training (e.g., young, solid), while non-spectrum-based attributes do not, suggesting extra caution is needed for certain spectrum-based attributes. Across three random seeds on CelebA, per-attribute probabilities converge to the same value despite run-to-run randomness.

<!-- quelle: Model Comparison and Per-Attribute Analysis -->

### Conclusion, Limitations, and Broader Impact

The study finds that bias shifts caused by the inductive biases of unconditional image generative models vary by attribute: attributes whose classifier decision boundary falls in a low-density area exhibit small bias shifts. Attributes are categorized into spectrum-based and nonspectrum-based sets. Three observations follow: (1) biases shift between training and generation distributions; (2) selecting a checkpoint with the best image generation metrics does not guarantee the smallest bias shifts; (3) BigGAN and small diffusion models show larger bias shifts than large diffusion models despite similar metric values. The authors hope this enables systematic study of additional bias sources—conditioning, guidance, pretrained modules.

Limitations: the controlled setting uses classifier-predicted labels, which may not reflect real-world attribute ambiguity; binary annotations limit analysis of spectrum-based attributes; findings may not generalize beyond CelebA and DeepFashion.

Broader impact: findings must not be read as evidence that algorithmic bias is unimportant. CelebA abstracts away sociocultural complexity, presenting a curated, stylized representation under a binary gender schema, encoding a simplified worldview. Labels such as 'smiling' or 'attractive' reflect specific cultural and aesthetic norms of curation and may not generalize across contexts or demographics. Over-interpreting these findings risks misleading conclusions about generative model behavior.

<!-- quelle: Conclusion, Limitations, and Broader Impact -->

### References and Appendices

This section is a bibliography. It lists 45 references spanning foundation language models (Llama, GPT-4), text-to-image generation systems (DALL-E, latent diffusion, CLIP), text-to-video and text-to-audio models, and fairness/bias auditing literature for generative models. Key clusters: (1) generative architecture papers — diffusion models, GANs, classifier-free guidance, U-Net, transformers; (2) bias and fairness in text-to-image generation — DALL-EVAL, Stable Bias, bias amplification paradox, fairness fine-tuning; (3) datasets and training — LAION-5B, CelebA, DeepFashion, COYO/CC15M; (4) foundation model surveys and fairness metric reviews. No argumentative content is present; the section functions as scholarly apparatus supporting claims made in earlier chapters.

<!-- quelle: References and Appendices -->

## GLOSSAR

- **bias shift** — The change in distributional bias of attributes between the training data and the generated outputs of a generative model.
- **classifier-free guidance (CFG)** — A conditional generation technique that reduces diversity in outputs, identified as a potential confounding factor in bias analysis.
- **decision boundary density** — Whether a classifier's decision boundary falls in a high- or low-density region of the attribute likelihood distribution, determining sensitivity of measured bias shift.
- **unconditional image generative model** — A generative model that directly outputs images without text conditioning or guidance, isolating generative bias from text-prompt effects.
- **bias shift evaluation metrics** — Metrics computed from classifier-predicted labels across training, validation, and generation sets to quantify bias shift.
- **attribute bias shift (ABS)** — The change in distribution of a specific image attribute between training data and generated samples, distinct from social bias regarding protected attributes.
- **Average attribute bias shift (ABS)** — The average absolute difference between training and generation probabilities across all considered attributes, expressed as a percentage.
- **bias shift evaluation framework** — A protocol training unconditional generative models, generating images per checkpoint, and applying a consistent classifier to both dataset and generated images to measure bias changes.
- **ablated diffusion models (ADMs)** — Unconditional diffusion models trained with U-Net architecture at varying bottleneck channel widths to control model size.
- **generalization gap** — Difference between training and generation performance; positive or slightly negative values indicate absence of overfitting.
