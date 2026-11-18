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
checks: passed
review: passed
analyzed_at: "2026-11-15T11:13:31.525966+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: gedruckt
---

# Do GANs actually learn the distribution? An empirical study

## PROFIL

- Written by Sanjeev Arora and Yi Zhang (July 4, 2017), this scholarly article is addressed to the machine-learning research community and investigates empirically whether Generative Adversarial Networks (GANs) actually learn the target distribution they are trained on, as claimed in the original GAN paper (Goodfellow et al. 2014). It responds to a theoretical analysis by Arora et al. (ICML 2017) showing that a finite discriminator of size n allows the training objective to be nearly optimized by a distribution supported on only O(n log n/ε²) images, so that the objective cannot prevent mode collapse.
- Its main technical contribution is a new test for estimating the support size of a generated distribution, based on the birthday paradox: samples of size about √N should contain duplicates if the support is N; the test flags the 20 most similar pairs by an automated similarity measure, checks them visually, and repeats. Two theorems (using collision time and a uniformity surrogate, applying Theorem 3 of [5]) formalize the inference from observed collisions to support size.
- The paper positions itself against the qualitative surrogate tests researchers rely on (nearest-neighbor checks, latent interpolation, Annealed Importance Sampling [2], a sample quality/diversity trade-off [3]), since GANs provide no quantitative measure of distributional fit; it also distinguishes low support from mere memorization of training data.
- Experiments on CelebA (DCGAN, MIX+DCGAN, ALI [10]/BiGAN [11]) find duplicate pairs in batches of about 400 samples, suggesting support below roughly 160,000; ALI/BiGANs are somewhat more diverse, supporting the suggestion in [10] and [11] that bidirectional structure prevents some mode collapse. Varying discriminator size suggests diversity grows near-linearly with discriminator capacity, though it plateaus. On CIFAR-10, a class-conditioned Stacked GAN shows class-specific duplicate rates implying low support, with nearest-neighbor checks confirming lack of diversity rather than memorization. Exploratory results on LSUN Bedroom reveal a fixed noise pattern carrying about 5% probability (underfitting), and the test proves difficult to apply to Variational Auto-Encoders [13], whose samples are too blurry to judge.
- The conclusion is that current GAN approaches producing higher visual quality fall significantly short of learning the target distribution, with rather low support size, as anticipated by the theory of [4]; the authors raise the open problem of modifying the GAN training objective to avoid mode collapse and suggest that GANs may be better suited to feature learning than distribution learning.
- The article is usable in arts education wherever generative image models and their evaluation are taught — for instance in digital and media arts curricula addressing machine learning for image synthesis — as a source on the empirical limits of GAN diversity and on a concrete, teachable test for it.

## WISSEN

### Purpose and Thesis (p. 1–2)

This paper by Sanjeev Arora and Yi Zhang (July 4, 2017) investigates whether Generative Adversarial Networks (GANs) actually learn the target distribution they are trained on. The original GAN paper (Goodfellow et al. 2014) claimed they do, given "sufficiently large" deep nets, sample size, and computation time. However, a theoretical analysis by Arora et al. (appearing at ICML 2017) showed that when the discriminator has finite size n, the training objective can come within ε of its optimum even if the generated distribution is supported on only O(n log n/ε²) images — meaning the objective cannot prevent mode collapse. This paper provides empirical evidence that such low-support distributions do occur in practice in well-known GAN approaches. Its main technical contribution is a new test, based on the birthday paradox, for estimating the support size of a generated distribution.

The authors note that GANs, unlike earlier distribution-learning methods, provide no quantitative measure of distributional fit (e.g., a perplexity score), so researchers rely on qualitative surrogate tests: checking similarity of generated images to nearest training images, interpolating between seeds, looking for semantically meaningful directions in latent space, Annealed Importance Sampling for log-likelihoods (proposed by [2]), and a sample quality/diversity trade-off method by [3] that lacks a quantitative diversity metric. The theoretical failure mode identified by Arora et al. is distinct from mere memorization of training data: the trained distribution may have small support while its samples are completely disjoint from the training set. The paper also notes that empirically estimating support size is hard — humans cannot inspect hundreds of thousands of images, and automated similarity tests can be fooled by small changes in lighting or pose.

### The Birthday Paradox Test for Support Size (p. 2–4)

The test rests on the birthday paradox: if a distribution has support N, a sample of size about √N is quite likely to contain a duplicate (analogously, only 23 people are needed for a >50% chance of two sharing a birthday among 366 possible days). The proposed test for GANs:

(a) Pick a sample of size s from the generated distribution.
(b) Use an automated measure of image similarity to flag the 20 most similar pairs in the sample.
(c) Visually inspect the flagged pairs and check for duplicates.
(d) Repeat.

If samples of size s contain duplicates with good probability, the distribution's support size is suspected to be about s².

The test is not definitive: a distribution could assign, say, 10% probability to a single image while being uniform on a huge number of other images, producing duplicates with small samples despite huge true support. But such nonuniformity would itself be a GAN failure mode. Two theorems formalize this:

- **Theorem 1**: If a subset S of size N carries probability mass at least ρ, then the probability of at least one collision among M i.i.d. samples is at least 1 − exp(−m²ρ²/N) (assuming M << N; worst case is uniform mass on S).
- **Theorem 2**: If the probability of at least one collision among M i.i.d. samples is γ, then for ρ = 1 − o(1), there exists a subset with probability mass ≥ ρ of size at most 2Mρ²(−3 + √(9 + 24M ln(1/(1−γ)))) − 2M(1−ρ)². The proof uses the collision time T and β = 1/∑ P(X)² as a surrogate for the uniformity of P, applying Theorem 3 of [5] (valid when β > 1000 and M ≤ 2√(β ln β)).

### Experimental Setup (p. 4)

GAN distributions are continuous, so exact pixel-identical duplicates should not occur when support is infinite; surprisingly, the test still works when searching for near-duplicates: select the 20 closest pairs by a heuristic metric, then visually judge whether humans would call them duplicates. Two datasets are used: CelebA (over 200K celebrity images of 11K distinct individuals, with 40 attribute annotations, large pose variation and background clutter) and CIFAR-10 (60K 32×32 color images in 10 classes — airplane, automobile, bird, cat, deer, dog, frog, horse, ship, truck — with 6K per class). For faces, Euclidean distance in pixel space works well because samples are centered and aligned; for CIFAR-10, a pre-trained discriminative CNN's top-layer representation serves as an embedding, with Euclidean distance in that space. Since better similarity measures can only find more duplicates, the reported support-size estimates are upper bounds. Preliminary, inconclusive results are also reported on 3,033,042 bedroom images from LSUN (64×64 center crops). The test works poorly on GANs that add noise to training/generated images (e.g., some GANs and variational autoencoders), since noised images are blurry and hard to judge for similarity.

### Results on CelebA (p. 5–6)

Methods tested: DCGAN (unconditional, JSD objective), MIX+ GAN (specifically MIX+DCGAN with 3 mixture components), and Adversarially Learned Inference (ALI) [10], equivalent to BiGANs [11] (only ALI was tested, since the architectures are equivalent).

Findings: with probability ≥50%, a batch of about 400 samples contains at least one duplicate pair for both DCGAN and MIX+DCGAN, suggesting support size below 400² ≈ 160,000 — lower than the training set's diversity, yet not mere memorization of training data. ALI/BiGANs are somewhat more diverse: collisions appear with 50% probability only at a batch size of 1000, implying support of about a million — 5× the training set, but still far smaller than the expected diversity of human faces (the authors remark that most people know several thousand people yet the only doppelgangers among acquaintances are twins). For fairness, ALI's discriminator was set roughly the same size as DCGAN's, since discriminator size strongly affects diversity. These tests support the suggestion in [10] and [11] that bidirectional structure prevents some mode collapse.

### Diversity vs. Discriminator Size (p. 5–6)

Since Arora et al.'s analysis suggested support size could be near-linear in discriminator capacity, the authors built DCGANs with increasingly larger discriminators while fixing other hyperparameters. The discriminator is a 5-layer CNN whose output channels per layer are 1×, 2×, 4×, 8× of dim, with dim ∈ {16, 32, 48, 64, 80, 96, 112, 128}, so discriminator size is proportional to dim². Results suggest the diversity of the learned distribution grows near-linearly with discriminator size, though it plateaus — possibly because other parameters like depth must change to add meaningful capacity.

### Results on CIFAR-10 (p. 6–8)

Pixel-space Euclidean distance is uninformative here, so a classifying CNN (3 convolutional layers, 2 fully-connected layers, 10-class softmax, pretrained on multi-class classification) provides top-layer feature embeddings. Results are affected by sample quality: with noised training samples, the most similar generated samples tend to be blurry blobs — even the best DCGAN variant (Inception Score 7.16) yields mostly blobs. The authors therefore used a Stacked GAN, the best generative model on CIFAR-10 (Inception Score 8.59), which generates the most real-looking images and is class-conditioned, so diversity is measured per class. Class-specific batch sizes needed for duplicates with >50% probability: Aeroplane 500, Auto-Mobile 50, Bird 500, Cat 100, Deer 500, Dog 300, Frog 50, Horse 200, Ship 500, Truck 100. Checking nearest neighbors in the training set shows the closest training image is quite different from the detected duplicate, confirming the issue is lack of diversity (low support size) rather than memorization.

### Exploratory Results on the Bedroom Dataset (p. 7–9)

For DCGANs trained on LSUN Bedroom, Euclidean distance was used to extract collision candidates (no CNN classifier can be trained on a single-category dataset). The most similar pairs tend to be corrupted samples sharing a fixed noise pattern (the top-5 collision candidates all contain such patterns); ignoring these, the most similar "clean" pairs are not even similar to human eyes. This means the distribution puts significant probability on noise patterns — a form of underfitting also reported in the DCGAN paper. Among 900 i.i.d. generated samples, 43 showed the fixed noise pattern, implying about 43/900 ≈ 5% probability.

### Birthday Paradox Test for VAEs (p. 8–9)

It is natural to ask whether Variational Auto-Encoders (VAEs) [13], which train the generator via approximate perplexity feedback rather than discriminator feedback (so the Arora et al. analysis does not directly apply), achieve higher diversity. However, the test was difficult to run: VAE samples from CelebA were not realistic or sharp enough for a human to definitively judge near-duplicates. Collision candidates in batches of 400 samples were frequently blurry, since crucial features (eyes, hair, mouth) are less distinctive than in GAN samples.

### Conclusions (p. 9–10)

The birthday-paradox test suggests that current GAN approaches — specifically those producing higher visual quality — fall significantly short of learning the target distribution, with rather low support size (mode collapse), as anticipated by the theoretical analysis of [4], which showed the GAN training objective cannot prevent mode collapse. Rough experiments also suggest, in line with theory, that support size scales near-linearly with discriminator capacity, though this needs rechecking with more extensive experiments. This raises the open problem of modifying the GAN training objective to avoid mode collapse; possibly ALI/BiGANs point in the right direction, as they exhibit somewhat better diversity. Finally, the authors suggest the best use of GANs and related techniques might be feature learning or some other goal rather than distribution learning, which needs further theoretical and empirical exploration.

### Figures (p. 6–9)

*Image 1 (p. 6):* — The picture displays three side-by-side panels, each containing a grid of small square face images arranged in eight rows and three columns. In each panel, the rightmost column of faces is enclosed by a dashed rectangular border. Below the left panel is the text DCGAN, below the middle panel is MIX+DCGAN, and below the right panel is ALI.

*Fig. 2 (p. 7):* Diversity's dependence on discriminator size. The diversity is measured as the square of the batch size needed to encounter collision w.p. ≥ 50% v.s. size of discriminator. The discriminator size is explained in the main article. — This is a line chart. The horizontal axis is labeled "size of discriminator" and ranges from 0 to 18000, while the vertical axis is labeled "diversity" with a "×10^6" scale ranging from 0 to 6. The plotted line starts at the origin, rises steeply to approximately 1.5 × 10^6, stays flat for a short interval, then increases steadily to about 5.9 × 10^6 at a discriminator size of roughly 12500, after which it plateaus and remains nearly constant through the final data point near 16500. _(Lettering in the image, read by the image model, not confirmed: "×10^6")_

*Fig. 3 (p. 8):* Duplicate pairs found in a batch of 1000 generated CIFAR-10 samples from a Stacked GAN.a)-b):pairs of duplicate samples; c): nearest neighbor of b) in the training set. The batch size 1000 was not the batch size with 50% duplicate detection probability. The number 1000 is chosen for the convenience of selecting pairs for visualization. — The picture is a figure made of many small color thumbnail images arranged in horizontal rows, with text labels at the left and right reading airplane, auto-mobile, bird, cat, deer, dog, frog, horse, ship, and truck. Under airplane there are three rows marked a), b), and c); rows a) and b) show blurry bluish airplane thumbnails, while row c) shows sharper airplanes in sky or on a runway. Each remaining label heads two or three rows of highly similar thumbnails of the named category, such as cars, birds, cats, deer, dogs, frogs, horses, ships on water, and trucks.

*Fig. 4 (p. 9):* Randomly generated samples from a DCGAN trained on Bedroom dataset. Note that there are corrupted images with a fixed noise pattern (emphasized in red boxes). — The picture is a grid of small, blurry thumbnail images that appear to be computer-generated bedroom interiors, showing furniture such as beds, dressers, and windows in muted colors. Four of the thumbnails are outlined with red rectangular boxes, and each of these four displays the same colorful, repeating patterned texture rather than a recognizable room. No text is legible anywhere in the picture.

*Fig. 5 (p. 9):* Collision candidates found in Variation Auto-Encoder samples. The duplicated samples are frequently blurry ones because the crucial features (eyes, hair, mouth) of VAE samples are not as distinctive as those of GANs'. — The picture is a grid of twenty small, blurry color photographs of human faces arranged in two horizontal rows of ten. Each portrait is low-resolution and pixelated, with facial features such as eyes, hair, and mouths appearing indistinct.

<!-- quelle: Do GANs actually learn the distribution? An empirical study (p. 1–10) -->

## LITERATUR

<!-- quelle: References (p. 10–11) -->

- Ian Goodfellow, Jean Pouget-Abadie, Mehdi Mirza, Bing Xu, David Warde-Farley, Sherjil Ozair, Aaron Courville, and Yoshua Bengio. Generative adversarial nets. In Advances in neural information processing systems , pages 2672-2680, 2014.
- Yuhuai Wu, Yuri Burda, Ruslan Salakhutdinov, and Roger Grosse. On the quantitative analysis of decoder-based generative models. arXiv preprint arXiv:1611.04273 , 2016.
- Ben Poole, Alexander A Alemi, Jascha Sohl-Dickstein, and Anelia Angelova. Improved generator objectives for gans. arXiv preprint arXiv:1612.02780 , 2016.
- Sanjeev Arora, Rong Ge, Yingyu Liang, Tengyu Ma, and Yi Zhang. Generalization and equilibrium in generative adversarial nets (gans). arXiv preprint arXiv:1703.00573 , 2017.
- Michael J Wiener. Bounds on birthday attack times. IACR Cryptology ePrint Archive 2005: 318 (2005) , 2005.
- Ziwei Liu, Ping Luo, Xiaogang Wang, and Xiaoou Tang. Deep learning face attributes in the wild. In Proceedings of International Conference on Computer Vision (ICCV) , 2015.
- Alex Krizhevsky. Learning multiple layers of features from tiny images. Citeseer , 2009.
- Fisher Yu, Ari Seff, Yinda Zhang, Shuran Song, Thomas Funkhouser, and Jianxiong Xiao. Lsun: Construction of a large-scale image dataset using deep learning with humans in the loop. arXiv preprint arXiv:1506.03365 , 2015.
- Alec Radford, Luke Metz, and Soumith Chintala. Unsupervised representation learning with deep convolutional generative adversarial networks. arXiv preprint arXiv:1511.06434 , 2015.
- Vincent Dumoulin, Ishmael Belghazi, Ben Poole, Alex Lamb, Martin Arjovsky, Olivier Mastropietro, and Aaron Courville. Adversarially learned inference. In International Conference on Learning Features (ICLR) , 2017.
- Jeff Donahue, Philipp Kr¨ ahenb¨ uhl, and Trevor Darrell. Adversarial feature learning. In International Conference on Learning Features (ICLR) , 2017.
- Xun Huang, Yixuan Li, Omid Poursaeed, John Hopcroft, and Serge Belongie. Stacked generative adversarial networks. arXiv preprint arXiv:1612.04357 , 2016.
- Diederik P Kingma and Max Welling. Auto-encoding variational bayes. In International Conference on Learning Representations (ICLR) , 2014.

## GLOSSAR

- **Birthday paradox test** — A test for the support size of a generated distribution: sample s images, flag the 20 most similar pairs by an automated similarity measure, visually inspect for duplicates, and repeat; frequent duplicates in samples of size s suggest support of about s².
- **Mode collapse** — The failure mode in which the GAN's generated distribution has very low support (few distinct images) and thus does not match the target distribution.
- **Target distribution** — The real distribution of images on which the GAN is trained, which the generator is supposed to learn.
- **Support size** — The number of distinct images (elements) on which the generated distribution places its probability mass.
- **Collision** — The occurrence of at least one duplicate (identical or near-identical image) among a set of i.i.d. samples from a distribution.
- **Collision time (T)** — Defined as inf{t ≥ 2, X_t ∈ {X_1, ..., X_{t−1}}, the first time an i.i.d. sample repeats a previous sample; used in proving Theorem 2.
- **β (surrogate for uniformity)** — β = 1/∑_X P(X)², used as a surrogate for the uniformity of distribution P in the proof of Theorem 2.
- **Doppelgangers** — Term used informally for near-identical faces among acquaintances (usually only twins), illustrating that the true diversity of human faces is enormous.
