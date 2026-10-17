---
id: kynkaanniemi-et-al-2019-improved-precision-and-recall-metric-for-assessing-generative-models
titel: Improved Precision and Recall Metric for Assessing Generative Models
autor: "Tuomas Kynkäänniemi, Jaakko Lehtinen, Tero Karras, Samuli Laine, Timo Aila"
jahr: 2019
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/1904.06991"
status: published
analyzed_at: "2026-07-31T11:54:49.029862+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Improved Precision and Recall Metric for Assessing Generative Models

## PROFIL

The text argues that an improved precision and recall metric, utilizing explicit non-parametric representations of data manifolds, can separately and reliably measure the sample quality and distribution coverage of generative models. It sets itself against widely used single-scalar metrics such as Fréchet Inception Distance (FID), Inception Score (IS), and Kernel Inception Distance (KID), as well as the relative density-based formulation by Sajjadi et al., which fail to expose the tradeoff between quality and variety or misinterpret packed samples. By constructing k-nearest-neighbor hyperspheres in a high-dimensional feature space, the method disentangles fidelity from manifold coverage. For arts education, this metric provides a technical framework to evaluate generative AI tools by independently assessing aesthetic fidelity and stylistic diversity in machine-generated artworks.

## WISSEN

### Problem framing and motivation

Generative modeling aims to learn the manifold of training data to produce novel samples indistinguishable from the training set. Two distinct goals emerge: individual samples must be faithful to examples (quality), and their variation must match the training distribution (coverage). Existing metrics — Fréchet Inception Distance (FID), Inception Score (IS), Kernel Inception Distance (KID) — collapse both into a single scalar without exposing the tradeoff, making diagnosis difficult. Notably, state-of-the-art methods optimize FID yet uncurated results are typically produced via truncation that sacrifices variation for quality. Insufficient coverage remains a GAN challenge; prior variation metrics are subjective, domain-specific, or unreliable. Sajjadi et al. proposed separating quality into precision and recall, but their metric has weaknesses demonstrated later experimentally. The primary contribution is an improved precision and recall metric providing explicit visibility of the quality–variety tradeoff.

<!-- quelle: Problem framing and motivation -->

### Background and critique of existing precision/recall method

Sajjadi et al. introduce precision and recall to generative model evaluation, motivated by FID's inability to disentangle sample quality from manifold coverage. Classic precision = fraction of generated images that are realistic; recall = fraction of the training data manifold covered by the generator. Sajjadi et al. instead formulate these through relative probability densities, producing a continuum whose extrema correspond to classic definitions. This approach has two flaws: ambiguity in choosing a value, and inability to correctly interpret packed samples (e.g., mode collapse, truncation) due to reliance on relative densities. Lopez-Paz et al.'s k-nearest-neighbor test shares this flaw; Simon et al. extend Sajjadi's formulation via a post hoc classifier. The authors argue the classic definition suffices for disentangling quality and coverage, supported by Lin et al.'s analysis where precision and recall correspond to vertical and horizontal extremal cases of mode collapse regions. They construct adaptive-resolution finite approximations to real and generated manifolds answering binary membership queries ('does sample x lie in the support of distribution P?'). Combined with density-based metrics like FID, these scores reveal effects in the 'null space' of FID.

<!-- quelle: Background and critique of existing precision/recall method -->

### Improved k-NN precision and recall metric

The metric forms explicit non-parametric representations of the manifolds of real and generated data, from which precision and recall are estimated. Real and generated samples are embedded into a high-dimensional feature space via a pre-trained classifier; for each feature vector, a hypersphere with radius equal to the distance to its k-th nearest neighbor is formed. Together these hyperspheres define an estimated manifold. Precision is quantified by querying whether each generated image falls within the estimated manifold of real images; recall symmetrically queries whether each real image falls within the generated manifold. The authors tested VGG-16 (activations after the second fully connected layer) against a perceptual metric using intermediate convolutional activations, finding the former works considerably better because it places less emphasis on exact spatial arrangement — sparsely sampled manifolds rarely include near-exact spatial matches. The metric is weakly affected by sample count (like FID); k=3 and |Φ|=50000 are adopted as robust defaults. Inception-v3 features yield substantially similar results, confirming the approach is not architecture-specific.

<!-- quelle: Proposed improved k-NN precision and recall metric -->

### Precision and recall of state-of-the-art generative models

The authors' precision/recall metric is validated against StyleGAN (FFHQ) and BigGAN (ImageNet), contrasted with Sajjadi et al.'s method and FID.

**StyleGAN:** Four setups illustrate a quality–variation tradeoff. Setup A (heavy truncation) yields high precision, low recall; B increases variation (higher recall, slightly lower precision); C adds further variation but introduces artifacts (lower precision); D preserves variation but nearly all images are broken (much lower precision). Sajjadi et al.'s method incorrectly rates B, C, D as near-perfect and assigns A the lowest precision — hypothesized to result from truncation packing generated images densely, creating clusters devoid of real images. FID ranks C best despite visible artifacts and treats B and D as nearly equal, overweighting variation. The authors' method estimates real and generated manifolds separately, avoiding this mixing problem.

**BigGAN:** Easy ImageNet classes (textural, well-represented; dogs/cats have extra training data) show high precision; difficult classes (precise global structure, underrepresented) show lower precision. Recall reveals missed variation invisible to FID: classes like 'Lemon' and 'Broccoli' have low recall yet good FID, because low intrinsic variation yields low FID even when much variation is missed.

<!-- quelle: Evaluation on state-of-the-art generative models -->

### Using precision and recall to analyze and improve StyleGAN

FID as sole metric can hide qualitative differences and favor an unintended precision–recall tradeoff. To compare training runs while accounting for stochastic variation (FID fluctuates ±14% between iterations), the authors identify the Pareto frontier of snapshots—the minimal subset containing the optimal choice for any desired tradeoff—rather than selecting a single best snapshot.

Applied to StyleGAN variants on FFHQ 1024²: removing the minibatch standard deviation layer shifts tradeoff toward precision (B); reducing R1 regularization γ by 100× shifts further toward precision (C); disabling progressive growing reduces both (D); random discriminator-input translation (±16px) improves precision (E); disabling instance normalization in AdaIN unexpectedly improves recall (F).

FID systematically favors high-recall configurations (A, F) over high-precision ones (B, C); configuration F yields state-of-the-art FID. Random translation (E) is exceptional, improving precision at recall's cost yet slightly improving FID—an effect left for future work.

<!-- quelle: Application: analyzing and improving StyleGAN design decisions -->

### Realism score for individual samples and interpolations

The binary precision metric cannot rank individual samples. A continuous *realism score* R extends the classification function f: f=1 iff R≥1, measuring closeness to the manifold of real images. Finite training sets create oversized k-NN hyperspheres in sparse regions; for single images these yield erratic scores. Pruning the largest half of hyperspheres (maximum taken only over φ_r whose radius is below median) gives an overconservative but consistent estimate, applied only to R.

Applied to StyleGAN interpolations in W, R correlates with perceived quality. Sampling 1M latent vectors with R≥1 yields 500k paths; defining a path as straying when >25% of intermediate images have R<0.9, only 2.4% cross unrealistic regions—suggesting the realistic subset of W is highly convex. This invites refined exclusion of unrealistic images beyond truncation.

<!-- quelle: Extension: estimating quality of individual samples and interpolations -->

### Conclusion and outlook

Separate assessment of precision and recall yields insights into generative models and can drive further improvement; the approach extends to image-to-image translation, where per-image quality matters. Applying the metric revealed previously unknown training-configuration effects, prompting the question whether truncation is necessary at all if comparable tradeoffs arise from adjusting training configuration instead — an in-depth study is deferred to future work. Finally, since density models can fail to determine whether an example belongs to the training distribution, explicitly modeling the real manifold offers a potential alternative for such membership estimation.

<!-- quelle: Conclusion and outlook -->

### Implementation, synthetic validation, and truncation analysis

Algorithm 1 implements precision–recall via k-NN manifold estimation: feature vectors are embedded by network *F*, and each point's *k*-th nearest neighbor distance defines the manifold boundary; precision and recall count how many points from one set fall within the other's manifold. A 50k-image evaluation runs in ~8 minutes on a single V100.

Synthetic validation (10-class 2D Gaussian mixture) confirms correct behavior: partial mode coverage yields perfect precision with recall = fraction covered; extraneous modes yield perfect recall with precision = fraction of real modes. The method of Sajjadi et al. performs similarly but exhibits k-means artifacts.

Truncation analysis evaluates seven strategies in StyleGAN's *W* and *Z* spaces. Key findings: *Z*-space strategies (E, F) are inferior, confirming *Z* density does not predict image quality; density-based rejection (B) outperforms distance-based (A); clamping outliers (C) outperforms rejecting them; interpolation toward mean (D) and random replacement (G) appear competitive but artificially inflate precision by increasing average density without reducing support. Replacing recall with FID reveals D and G degrade distribution quality—demonstrating recall alone measures extent, not quality.

<!-- quelle: Appendices: implementation, synthetic validation, truncation analysis, and sample quality examples -->

## GLOSSAR

- **precision** — The probability that a random generated image falls within the support of the real data distribution, corresponding to average sample quality.
- **recall** — The probability that a random real image falls within the support of the generated distribution, corresponding to coverage of the training manifold.
- **manifold** — The underlying structure of the training data that a generative model aims to learn for sampling novel, indistinguishable examples.
- **binary set membership** — Whether a sample drawn from one distribution falls under the support of another distribution, used to compute classic precision and recall as expectations.
- **relative probability densities** — Sajjadi et al.'s formulation of precision and recall through density ratios between real and generated distributions, producing a continuum rather than binary membership.
- **null space of FID** — Aspects of distributional quality and coverage that FID cannot distinguish, made visible by the authors' precision and recall scores.
- **truncation** — A technique trading perceptual quality for variation in generative models; stronger truncation increases image quality but reduces diversity.
- **Pareto frontier** — The minimal subset of training snapshots guaranteed to contain the optimal precision–recall tradeoff for any desired balance, avoiding assumptions about which tradeoff is preferred.
- **R1 regularization** — A regularization technique whose γ parameter controls the precision–recall balance; reducing it shifts the tradeoff toward precision.
- **AdaIN** — Adaptive instance normalization operation in StyleGAN; disabling its instance normalization unexpectedly improves recall.
