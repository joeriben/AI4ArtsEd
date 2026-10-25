---
id: arora-zhang-2017-do-gans-actually-learn-the-distribution-an-empirical-study
titel: Do GANs actually learn the distribution? An empirical study
autor: "Sanjeev Arora, Yi Zhang"
jahr: 2017
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/1706.08224"
status: published
analyzed_at: "2026-07-31T12:00:31.586447+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Do GANs actually learn the distribution? An empirical study

## PROFIL

The text argues that well-known GAN approaches empirically learn distributions of fairly low support and thus fail to capture the target distribution, challenging the foundational assumption—traceable to Goodfellow et al. (2014)—that sufficiently large nets, sample sizes, and computation time guarantee distributional learning. It positions itself against both the standard theoretical guarantee and the surrogate qualitative tests (nearest-neighbor similarity, interpolation, semantic directions, Annealed Importance Sampling) that researchers use in the absence of a perplexity-like distributional-fit measure. The central technical contribution is a birthday-paradox-based test estimating the support size of a generated distribution, supported by collision-probability theorems and experiments on CelebA, CIFAR-10, and Bedroom datasets showing that DCGAN and MIX+DCGAN yield support sizes far below training-set diversity, while ALI/BiGAN's bidirectional structure mitigates mode collapse. For arts education, the text provides a transferable diagnostic framework for critically evaluating the diversity and representational adequacy of generative-image models used in creative and pedagogical contexts.

## WISSEN

### GAN support-size problem framing

GANs lack distributional-fit measures (e.g., perplexity), so researchers rely on surrogate qualitative tests (nearest-neighbor similarity, interpolation, semantic directions, Annealed Importance Sampling). Theoretical analysis [4] shows finite-size discriminators allow training objective near-optimum even when the generated distribution has support of only O(n log n/ε²) images—a failure mode distinct from memorization. This note tests whether such low-support solutions arise empirically, introducing a birthday-paradox-based test to estimate support size of the generated distribution.

<!-- quelle: Problem framing and theoretical background -->

### Birthday paradox test for support size

A sample of size ≈√N from a distribution with support N likely contains a duplicate (birthday paradox). The proposed test for GANs: (a) pick sample size s from the generated distribution; (b) use automated image similarity to flag the 20 most similar pairs; (c) visually inspect flagged pairs for duplicates; (d) repeat. If duplicates appear with good probability at sample size s, suspect support ≈s². The test's only failure mode is nonuniformity — heavy probability on few images — which is itself a GAN training failure. Theorem 1: if mass ≥ρ concentrates on a subset of size N, collision probability among M samples is ≥1−exp(−M²ρ²/N). Theorem 2 (converse): observed collision probability γ bounds the size of a high-mass subset, via the collision time T and uniformity surrogate β=1/∑P(X)².

<!-- quelle: Birthday paradox test: Theoretical framework -->

### Birthday paradox test for GANs: experimental setup

The birthday paradox test seems inapplicable to continuous GAN distributions, where infinite support precludes exact pixel duplicates. Yet it works via near-duplicates: select the 20 closest pairs by a heuristic metric, then visually inspect. CelebA faces suit human judgment; CIFAR-10 uses CNN embeddings. Crude similarity measures only overestimate support size — better measures find more duplicates — so all estimates are upper bounds. Noise-blurred images (VAEs, some GANs) defeat both automated and visual similarity; sharp realistic images work best.

<!-- quelle: Experimental setup and methodology -->

### Empirical results on CelebA and discriminator size

DCGAN and MIX+DCGAN yield duplicates in batches of ~400 (≥50% probability), implying support size <160,000—below training-set diversity yet not pure memorization. ALI/BiGAN show greater diversity (collisions at batch size 1000, support ~1 million), supporting that bidirectional structure mitigates mode collapse. Discriminator size was equalized for fair comparison. Scaling a 5-layer CNN discriminator (dim = 16–128) shows diversity growing near-linearly with discriminator capacity, consistent with Arora et al.'s near-equilibrium analysis, though diversity plateaus.

<!-- quelle: Empirical results on CelebA and discriminator size -->

### Empirical results on CIFAR-10 and Bedroom dataset

Euclidean distance in pixel space is uninformative on CIFAR-10, so pretrained CNN top-layer features serve as embeddings. Noisy training yields blurry blobs as nearest neighbors. Using a class-conditioned Stacked GAN, diversity is measured per class. Detected duplicates differ from their nearest training-set neighbors, indicating low support size rather than memorization. On the Bedroom dataset, Euclidean distance reveals similar pairs share fixed noise patterns; ignoring these, clean pairs remain dissimilar, indicating underfitting with ~5% corrupted samples.

<!-- quelle: Empirical results on CIFAR-10 and Bedroom dataset -->

### Birthday Paradox Test Applied to VAEs

VAEs train generators via approximate perplexity rather than discriminator feedback, so prior diversity analyses do not directly apply; higher diversity is conceivable. However, the birthday paradox test proved difficult to run: VAE samples trained on CelebA were too blurry for humans to definitively identify near-duplicates. In batches of 400, collision candidates showed crucial features (hair, eyes, mouth) insufficiently distinctive compared to GAN samples, preventing reliable judgment.

<!-- quelle: Application to VAEs -->

### Conclusions and outlook

A Birthday Paradox-based test assesses image diversity. Experiments show current GANs, especially higher visual-quality ones, fall significantly short of learning the target distribution: support size is low (mode collapse), consistent with theory that the training objective cannot prevent it. Rough experiments suggest support size scales near-linearly with discriminator capacity, needing further verification. ALI/BiGANs show somewhat better diversity. The open problem is reformulating the training objective; alternatively, GANs' best use may be feature learning, not distribution learning.

<!-- quelle: Conclusions and outlook -->

### Acknowledgements and references

The authors thank Rong Ge, Cyril Zhang, and Ian Goodfellow for discussions and manuscript comments. Research was supported by NSF, ONR, and the Simons Foundation. References span GAN foundations (Goodfellow et al.), quantitative analysis of generative models, improved generator objectives, generalization and equilibrium in GANs, birthday attack bounds, and datasets (CelebA, CIFAR, LSUN), plus related architectures (DCGAN, ALI, BiGAN, StackGAN, VAE).

<!-- quelle: Acknowledgements and references -->

## GLOSSAR

- **birthday paradox** — A probabilistic argument that in a set of roughly √N randomly sampled items from N possibilities, a collision is likely; used here to estimate the support size N of a GAN's generated distribution.
- **mode collapse** — A GAN failure where the generator produces outputs from a low-support subset rather than the full target distribution.
- **birthday paradox test** — A procedure estimating a GAN's support size by checking for duplicate images in samples of size approximately the square root of the suspected support.
- **collision time** — The first time t≥2 at which an i.i.d. sample repeats a previously drawn value, used to bound distribution uniformity.
- **uniformity surrogate β** — The reciprocal of the sum of squared probabilities, serving as a measure of how uniform a discrete distribution is.
- **near-duplicates** — Image pairs that are not pixel-identical but are judged as duplicates by human inspection.
- **support size** — The effective number of distinct images covered by the generated distribution, used as a diversity measure.
- **near-equilibrium** — A theoretical state in which a distribution with small support suffices to fool the best discriminator.
- **low support size** — The phenomenon where a generative model lacks diversity rather than memorizing the training set.
- **underfitting** — A failure mode where the generated distribution puts significant probability on noise patterns instead of clean data structures.
