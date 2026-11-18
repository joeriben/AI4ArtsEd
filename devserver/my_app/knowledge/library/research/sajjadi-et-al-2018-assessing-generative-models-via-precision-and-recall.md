---
id: sajjadi-et-al-2018-assessing-generative-models-via-precision-and-recall
titel: Assessing Generative Models via Precision and Recall
autor: "Mehdi S. M. Sajjadi, Olivier Bousquet, Olivier Bachem, Mario Lucic, Sylvain Gelly"
jahr: 2018
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/1806.00035"
status: published
checks: passed
review: passed
analyzed_at: "2026-11-15T11:43:53.815388+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: gedruckt
---

# Assessing Generative Models via Precision and Recall

## PROFIL

- Written by Mehdi S. M. Sajjadi (MPI for Intelligent Systems / Max Planck ETH Center for Learning Systems, work done during an internship at Google Brain) with Olivier Bousquet, Olivier Bachem, Mario Lucic and Sylvain Gelly (all Google Brain), the paper addresses researchers evaluating deep generative models, for whom one-dimensional metrics such as the Inception Score (IS) and Fréchet Inception Distance (FID) cannot distinguish failure modes: two models may share nearly identical FID while one drops modes and the other produces low-quality samples across the whole distribution.
- Its central claim is that a single-value summary is inadequate, and it proposes a novel, theoretically sound definition of precision and recall for distributions (PRD) that disentangles the divergence between a learned distribution Q and a reference distribution P into precision (quality of samples from Q) and recall (proportion of P covered by Q), with a trade-off curve when the distributions differ on their shared support.
- The paper states five contributions: the definition itself, an efficient algorithm to compute it, connections to total variation distance, IS and FID, a demonstration that mode dropping and mode inventing can be quantified on real-world image and text data, and a comparison of generative model types.
- After reviewing and setting itself against log-likelihood comparison, IS, FID (and the unbiased KID alternative) and classifier-based evaluation — all one-dimensional — it derives the definition via mixture decompositions on the intersection of supports, states six properties of PRD (equality, disjoint supports, maximum precision and recall, monotonicity, duality), and gives an equivalent characterization (Theorem 2) yielding an algorithm over an equiangular grid of λ values; for λ = 1 the construction recovers 1 − total variation distance.
- In practice, samples are embedded with a pre-trained Inception network (Pool3 layer) and clustered with mini-batch k-means, reducing the comparison to cluster-assignment histograms; only a meaningful embedding is required, so the method extends to other modalities, including text.
- Experiments on MNIST, Fashion-MNIST, CIFAR-10 and CelebA, plus MultiNLI sentences embedded with a BiLSTM, show that PRD curves separate mode dropping from mode inventing where FID cannot, distinguish GANs with identical FID but opposite failure modes, and — reportedly the first metric to do so — empirically confirm the folklore that GANs yield high precision at the risk of mode collapse while VAEs yield higher recall with blurrier samples; the appendix contains the proofs.
- The paper is usable in machine-learning and computational-arts education wherever generative image or text models are trained and evaluated, particularly in situations requiring diagnosis of failure modes rather than model ranking by a single score.

## WISSEN

### Purpose and Thesis (p. 1–2)

This paper by Mehdi S. M. Sajjadi (MPI for Intelligent Systems / Max Planck ETH Center for Learning Systems, work done during an internship at Google Brain) with Olivier Bousquet, Olivier Bachem, Mario Lucic and Sylvain Gelly (all Google Brain) addresses a central problem in evaluating deep generative models: commonly used metrics such as the Inception Score (IS) and Fréchet Inception Distance (FID) produce only a single one-dimensional score and therefore cannot distinguish between different failure modes. Two models may obtain nearly identical FID scores while failing in opposite ways — one producing realistic samples that cover only part of the target distribution (mode dropping), the other producing low-quality samples that cover the whole distribution. The authors propose a novel definition of **precision and recall for distributions** that disentangles the divergence between a learned distribution Q and a reference distribution P into two separate dimensions: precision measures the quality of samples from Q, recall measures the proportion of P covered by Q. They argue that a single-value summary is inadequate for comparing generative models.

The paper's stated contributions are fivefold: (1) a novel, theoretically sound definition of precision and recall for distributions; (2) an efficient algorithm to compute these quantities; (3) a connection of the notions to total variation distance, IS and FID; (4) a demonstration that mode dropping and mode inventing can be quantified on real-world image and text data; and (5) a comparison of generative model types — reportedly the first metric to experimentally confirm the "folklore" that GANs produce sharper images but suffer from mode collapse (high precision, low recall), while VAEs produce blurrier images but cover more modes (low precision, high recall).

### Background and Related Work (p. 2–3)

The authors review existing evaluation approaches for deep generative models on image and text data:

- **Log-likelihood comparison**: criticized because high likelihood can coexist with low image quality and vice versa; kernel density estimation in high-dimensional spaces is extremely challenging.
- **Inception Score (IS)**: based on the intuition that the conditional label distribution p(y|x) of meaningful samples should have low entropy while the overall label distribution p(y) should have high entropy; formally IS(G) = exp(E_x∼G[d_KL(p(y|x), p(y))]). It requires a labeled data set and an Inception classifier trained on ImageNet, and has been found weak for model comparison.
- **FID**: embeds samples in a feature space (a layer of the Inception network), fits a multivariate Gaussian, and computes a distance from means and covariances. It requires no labels, is robust to image corruption, and is sensitive both to spurious modes and mode dropping — but yields one number. The Kernel Inception Distance (KID) is an unbiased alternative that correlates extremely strongly with FID.
- **Classifier-based evaluation**: training a classifier to distinguish real from fake samples; impractical (a classifier per model) and risky, since the classifier may detect a single artifact dimension and unfairly favor a worse model.

A previous notion of precision and recall (by the authors of the model comparison study cited as [18]) computed distance to the manifold of the true data, but only on a synthetic data set. All commonly used metrics are one-dimensional; the proposed approach breaks with this.

### PRD: Precision and Recall for Distributions — Derivation and Definition (p. 3–5)

The key intuition: precision measures how much of Q can be generated by a "part" of P; recall measures how much of P can be generated by a "part" of Q. Four toy examples motivate the definition: (a) P bimodal, Q capturing one mode → perfect precision, limited recall; (b) the opposite → perfect recall, limited precision; (c) Q = P → perfect precision and recall; (d) disjoint supports → zero precision and recall.

The derivation proceeds in two steps:

1. Let S = supp(P) ∩ supp(Q), the intersection of the supports. Both P and Q are decomposed into two-component mixtures: components P_S and Q_S on S, and components P_S̄ and Q_S̄ on the complement. The mixture weights give natural losses: the part of P that cannot be generated by Q (weight 1 − β̄) is a **recall loss**; the part of Q that cannot be generated by P (weight 1 − ᾱ) is a **precision loss**. If P_S = Q_S (the distributions agree on S up to scaling), ᾱ and β̄ give a simple two-number summary.

2. If P_S ≠ Q_S, the authors — inspired by PR curves in binary classification — resolve the ambiguity of whether differences should count as precision or recall losses by offering a **trade-off curve** rather than two numbers. A distribution μ on S is considered a "true" common component of P_S and Q_S; the parts of P_S and Q_S not captured by μ are respectively recall loss and precision loss (noise). Varying μ traces out the trade-off. Unlike PR curves in classification, the trade-off here does not correspond to different models — the curve only describes the characteristics of one model relative to the target distribution.

**Definition 1**: For α, β ∈ (0, 1], Q has precision α at recall β w.r.t. P if there exist distributions μ, ν_P and ν_Q such that P = βμ + ν_P and Q = αμ + ν_Q (with ν_P the part of P "missed" by Q and ν_Q the noise part of Q).

**Definition 2**: PRD(Q, P) is the set of all attainable (α, β) pairs plus the pair (0, 0).

**Theorem 1** establishes desirable properties of PRD(Q, P), proved in the appendix:
- (i) (1, 1) ∈ PRD(Q, P) ⇔ Q = P (equality)
- (ii) PRD(Q, P) = {(0, 0)} ⇔ supp(Q) ∩ supp(P) = ∅ (disjoint supports)
- (iii) Q(supp(P)) = ᾱ = max α over PRD(Q, P) (maximum precision)
- (iv) P(supp(Q)) = β̄ = max β over PRD(Q, P) (maximum recall)
- (v) monotonicity: if (α, β) ∈ PRD(Q, P), so does any (α′, β′) with α′ ∈ (0, α], β′ ∈ (0, β]
- (vi) duality: (α, β) ∈ PRD(Q, P) ⇔ (β, α) ∈ PRD(P, Q) — the precision of Q w.r.t. P equals the recall of P w.r.t. Q.

Further toy examples (e) and (f), where P and Q share the same support but differ on it, show the value of the trade-off: these behave like noisy versions of cases (a) and (b), and the PRD sets capture the high-precision/low-recall versus low-precision/high-recall character.

### Algorithm and Connection to Total Variation (p. 5)

Computing PRD(Q, P) directly from the definitions is non-trivial. **Theorem 2** gives an equivalent characterization: for λ > 0, define functions α(λ) and β(λ) (based on sums over ω of min(P(ω), Q(ω)/λ) and related quantities); then PRD(Q, P) equals the union over all λ ∈ (0, ∞) and θ ∈ [0, 1] of the points (θα(λ), θβ(λ)). Geometrically, the set is a union of line segments α = λβ, each starting at the origin and ending at the maximal achievable (α(λ), β(λ)). This yields a simple algorithm: compute pairs (α(λ), β(λ)) on an equiangular grid of λ values for a chosen angular resolution m ∈ ℕ, plot the resulting PRD curve, and interpolate toward the origin to approximate the full set. An implementation is available at https://github.com/msmsajjadi/precision-recall-distributions.

For λ = 1, the construction recovers 1 − δ(P, Q), where δ is the total variation distance — so the proposed notion generalizes total variation.

### Application to Deep Generative Models (p. 5–6)

In practice, P and Q are accessible only through samples P̂ and Q̂. Since the distributions are continuous, direct comparison of sample points fails, and comparing in image space risks favoring worse models. Following common practice, the authors embed samples with a pre-trained Inception network (Pool3 layer), then cluster the union of P̂ and Q̂ in feature space using mini-batch k-means with k = 20. This reduces the problem to comparing histograms of cluster assignments: failing to produce samples in clusters with many real samples hurts recall; producing samples in clusters with few real samples hurts precision. Because clustering is randomized, the procedure is run several times and the PRD curves averaged. Only a meaningful embedding is required, so the method applies to other modalities, including text.

### Experiments: Adding and Dropping Modes (p. 6–7)

To demonstrate sensitivity to mode dropping and mode inventing, the authors use three labeled, balanced 10-class data sets: MNIST, Fashion-MNIST and CIFAR-10. They fix P̂ to contain samples from the first 5 classes of the test set, and construct Q̂_i from the first i classes of the training set, for i = 1, …, 10. As i grows toward 5, recall should increase; beyond 5, added spurious classes should reduce precision without affecting recall; Q̂_5 should have both high precision and high recall.

Results on CIFAR-10 (others in the appendix): IS only increases as classes are added (it is not computed against a reference distribution). FID decreases until Q̂_5 and then increases — but critically cannot distinguish mode dropping from mode inventing: Q̂_4 and Q̂_6 have similar FIDs yet strikingly different PRD curves. The PRD curves correctly show recall gains from adding correct modes and precision losses from adding fake modes.

The method is also applied to text: sentences from the MultiNLI corpus (crowd-sourced sentence pairs annotated with topic and textual entailment; the entailment label is discarded) are embedded using a BiLSTM with 2048 cells in each direction and max pooling, giving 4096-dimensional embeddings. With 5 classes and P̂ containing all classes, the PRD curves demonstrate recall's sensitivity to mode dropping.

### Experiments: Class Imbalance in GANs (p. 7)

Two GANs trained on MNIST with virtually identical FID show very different PRD curves: the left model generates a high-quality subset of digits; the right model generates all digits at low quality. For desired recall below ~0.6, the left model has higher precision; above ~0.6, the right model does. A classifier trained on the embedding of P̂ confirms this: the left model's predicted-class histogram shows missing classes (recall loss), while the right model's is balanced (high recall); average classifier confidence is 96.7% for the left model versus 88.6% for the right, indicating higher sample quality on the left.

This analysis connects to IS (low-entropy p(y|x), high-entropy p(y)): plotting p(y|x) against precision and p(y) against recall over many GANs and VAEs yields Spearman rank correlations of −0.83 and 0.89 respectively. Two key differences are stressed: IS needs a classifier and labeled data, whereas PRD works on unlabeled data; and IS only captures recall losses at the class level, while PRD measures more fine-grained recall losses (an appendix example shows two GANs both collapsed to producing 1's — a classifier analysis treats them identically, but the PRD curve reveals the right model has slightly higher recall because it produces more varied shapes such as tilted 1's).

### Experiments: Comparing GANs and VAEs (p. 8)

The authors evaluate 7 GAN types and the VAE with 100 hyperparameter settings each (as provided by a prior comparison study). To summarize PRD curves, they reject the symmetric maximum F_1 score (harmonic mean of precision and recall) as fundamentally flawed, and instead use its generalization F_β = (1 + β²)p·r / ((β²p) + r), where β > 1 weighs recall higher and β < 1 weighs precision higher. Each PRD curve is distilled into a pair of values: F_β and F_(1/β).

Using β = 8 on Fashion-MNIST, they plot maximum F_8 (recall-weighted) against maximum F_(1/8) (precision-weighted). Models with higher recall than precision lie below the diagonal; models with higher precision lie above. This provides the first empirical metric confirmation of the folklore that VAEs are biased toward higher recall but may suffer precision issues (e.g., blurring), while GANs tend toward higher precision at the risk of mode collapse. Sample images from four models illustrate the four combinations: (A) high precision, low recall; (B) high precision, high recall; (C) low precision, low recall; (D) low precision, high recall. Similar plots for MNIST, CIFAR-10 and CelebA appear in the appendix.

### Conclusion (p. 8)

One-dimensional scores are insufficient to capture the distinct failure cases of state-of-the-art generative models. The proposed precision-and-recall notion for distributions is theoretically sound, connects to total variation distance, FID and IS, and yields an efficient sample-based algorithm. Experiments on real-world image and text data show it captures precision and recall of generative models, and it provides empirical evidence that VAEs produce lower-quality samples while being less prone to mode collapse than GANs.

### Appendix: Proofs (p. 11–12)

The appendix proves the theory. **Lemma 1** states that (α, β) ∈ PRD(Q, P) if and only if there exists a distribution μ such that for all ω, βμ(ω) ≤ P(ω) and αμ(ω) ≤ Q(ω). Theorem 1's six properties are proved individually: equality (from Definition 1 with μ = ν_P = ν_Q = P); disjoint support (by contraposition, constructing μ concentrated on a single shared support point); maximum precision (showing α ≤ Q(supp(P)) for all attainable pairs and exhibiting an attainable pair achieving equality via a μ proportional to Q on the intersection S); maximum recall (by duality from maximum precision); monotonicity (weakening the inequalities of Lemma 1); and duality (switching α with β, P with Q, ν_P with ν_Q in Definition 1). Theorem 2 is proved by two inclusions: every attainable pair lies on some segment θα(λ), θβ(λ) (choosing λ = α′/β′ and θ = β′/β(λ), and showing θ ∈ [0, 1] via Lemma 1), and conversely every point on such a segment is attainable (constructing μ(ω) = min(P(ω), Q(ω)/λ)/β(λ) and applying Lemma 1).

### Figures (p. 2–15)

*Fig. 1 (p. 2):* Comparison of GANs trained on MNIST and CelebA. Although the models obtain a similar FID on each data set (32/29 for MNIST and 65/62 for CelebA), their samples look very different. For example, the model on the left produces reasonably looking faces on CelebA, but too many dark images. In contrast, the model on the right produces more artifacts, but more varied images. By the proposed metric (middle), the models on the left achieve higher precision and lower recall than the models on the right, which suffices to successfully distinguishing between the failure cases. — This is a screenshot of a three-panel figure. The left and right panels each contain a grid of images: several rows of handwritten digits on top and several rows of small face images below. The center panel is a line chart whose vertical axis is labeled “Precision” and horizontal axis “Recall,” with four curves and a legend reading “MNIST left,” “MNIST right,” “CelebA left,” and “CelebA right.”

*Fig. 3 (p. 3):* PRD( Q,P ) for the examples above. — The image is a composite scientific diagram made of bar charts and 2D plots. At the upper left, six pairs of horizontal bar charts labeled (a)–(f) have rows marked “P” and “Q,” with the caption line “Figure 2: Intuitive examples of P and Q.” Below them are six square plots labeled (a)–(f), each with vertical axis “α” and horizontal axis “β” marked 0 and 1, containing different colored filled or empty regions. At the right is a plot with y-axis “Precision α” and x-axis “Recall β,” both scaled from 0.0 to 1.0, showing a blue shaded region, a black boundary with three marked points, and dotted diagonal lines labeled “λ = 2,” “λ = 1,” and “λ = 0.5.”

*Fig. 5 (p. 6):* Left: IS and FID as we remove and add classes of CIFAR-10. IS generally only increases, while FID is sensitive to both the addition and removal of classes. However, it cannot distinguish between the two failure cases of inventing or dropping modes. Middle: Resulting PRD curves for the same experiment. As expected, adding modes leads to a loss in precision ( Q 6 -Q 10 ), while dropping modes leads to a loss in recall ( Q 1 -Q 4 ). As an example consider Q 4 and Q 6 which have similar FID, but strikingly different PRD curves. The same behavior can be observed for the task of text generation, as displayed on the plot on the right. For this experiment, we set P to contain samples from all classes so the PRD curves demonstrate the increase in recall as we increase the number of classes in Q . — The image contains three charts arranged horizontally. The left chart is a line graph plotting "Inception score" (left y-axis, scale 4–11) and "FID" (right y-axis, scale 0–100) against "Number of classes in Q" (x-axis, 1–10), with a blue line marked "Inception score" and a green line marked "FID". The middle chart shows precision-recall curves with "Precision" on the y-axis and "Recall" on the x-axis, both ranging from 0.0 to 1.0, and a legend listing Q from 1 to 10. The right chart is a similar precision-recall plot with axes labeled "Precision" and "Recall" (both 0.0–1.0) and a legend showing Q values 1 through 5.

*Image 4 (p. 7):* — This is a screenshot of a document page containing five panels arranged around a central chart. The center panel is a line chart plotting "Precision" on the vertical axis against "Recall" on the horizontal axis, with two curves labeled "left" and "right". The upper-left and upper-right panels show grids of handwritten digits on black backgrounds, while the lower-left and lower-right panels are bar charts with the horizontal axis labeled "Class label".

*Fig. 7 (p. 8):* F 1 / 8 vs F 8 scores for a large number of GANs and VAEs on the Fashion-MNIST data set. For each model, we plot the maximum F 1 / 8 and F 8 scores to show the trade-off between precision and recall. VAEs generally achieve lower precision and/or higher recall than GANs which matches the folklore that VAEs often produce samples of lower quality while being less prone to mode collapse. On the right we show samples from four models which correspond to various success/failure modes: (A) high precision, low recall, (B) high precision, high recall, (C) low precision, low recall, and (D) low precision, high recall. — This is a scientific figure made of a scatter plot on the left and four grids of sample images on the right. The plot has an x-axis labeled “F8 (Recall)” and a y-axis labeled “F1/8 (Precision)”, both scaled from 0.0 to 1.0, with blue points labeled “GAN” and green points labeled “VAE”, and four points marked A, B, C, and D. To the right, panels A, B, C, and D each show a grid of small grayscale images of clothing items such as shoes, shirts, dresses, and bags.

*Fig. 8 (p. 12):* Comparing a pair of GANs on MNIST which have both collapsed to producing 1's. An analysis with a trained classifier as in Section 4.2 comes to the same conclusion for both models, namely, that they have collapsed to producing 1's only. However, the PRD curve shows that the model on the right has a slightly higher recall. This is indeed correct: while the model on the left is producing straight 1's only, the model on the right is producing some more varied shapes such as tilted 1's. — This is a composite figure made of image grids and charts. On the left and right are grids of white digit-like strokes on a black background, each placed above a bar chart whose horizontal axis is labeled "Class label" and whose vertical axis is marked up to "10k", with a single tall bar at class 1; the left grid shows mostly straight vertical strokes, while the right grid shows more slanted and varied strokes. In the middle is a line chart with vertical axis "Precision" and horizontal axis "Recall", containing two curves labeled "left" and "right", where the "right" curve stays above the "left" curve before both drop to "0.0".

*Fig. 9 (p. 13):* Clustering the real and generated samples from a GAN in feature space (10 cluster centers for visualization) yields the clusters above for the data sets MNIST, Fashion-MNIST, CIFAR-10 and CelebA. Although the GAN samples are not perfect, they are clustered in a meaningful way. — This is a screenshot of a figure with two column headings, “Real images” on the left and “Generated images” on the right. Below the headings are four rows of image grids: black-background grids of white handwritten digits, grids of grayscale garments, grids of small color pictures of animals and vehicles, and grids of color portrait photographs of faces. Each row places a grid of real images beside a grid of generated images of the same kind.

*Fig. 10 (p. 14):* Comparing our unsupervised F 1 / 8 and F 8 measures with the supervised measures P ( y | x ) and P ( y ) similar to the IS (for a definition of F β , see Section 4.3). Each circle represents a trained generative model (GAN or VAE) on the MNIST data set. The values show a fairly high correlation with a Spearman rank correlation coefficient of -0.83 on the left and 0.89 on the right. — The image shows a scientific figure containing two side-by-side scatter plots with light gridlines and many small blue-gray circular points. In the left plot, the horizontal axis is labeled “F₁/₈ (Precision)” from 0.0 to 1.0 and the vertical axis is labeled “P(y|x)” from 0.0 to 0.6; the points are broadly scattered but trend downward and become densely clustered near the right edge at low P(y|x) values. In the right plot, the horizontal axis is labeled “F₈ (Recall)” from 0.0 to 1.0 and the vertical axis is labeled “P(y)” from 0.0 to 2.5; the points are broadly scattered but trend upward and cluster near the upper right at high recall and P(y) around 2.2–2.3.

*Fig. 11 (p. 14):* Corresponding plots as in Figure 5 for the data sets MNIST (top) and Fashion-MNIST (bottom). — It is a figure made of four line charts arranged in a 2×2 grid. The two charts on the left plot “Inception score” (blue) and “FID” (green) against “Number of classes in Q” from 1 to 10, with “Inception score” on the left y-axis and “FID” on the right y-axis. The two charts on the right plot “Precision” versus “Recall” with multiple colored curves whose legend is labeled “Q” with entries 1 through 10. Visible text includes the axis labels “Inception score”, “FID”, “Number of classes in Q”, “Precision”, “Recall”, and the legend labels “Inception score”, “FID”, and “Q”.

*Fig. 12 (p. 15):* Corresponding plots as in Figure 7 for the data sets MNIST (top), CIFAR-10 (middle) and CelebA (bottom). — The picture is a scientific figure with three rows, each row pairing a scatter plot on the left with four image grids labeled A, B, C and D on the right. Each scatter plot has a horizontal axis labeled “F_8 (Recall)” and a vertical axis labeled “F_{1/8} (Precision)”, with many small light-blue points, a legend reading “GAN” and “VAE”, and four darker points marked A, B, C and D. The top row’s grids contain black-and-white handwritten digit images, the middle row’s grids contain small color photographs of animals and vehicles, and the bottom row’s grids contain color photographs of human faces. _(Lettering in the image, read by the image model, not confirmed: “F_8 (Recall)”)_

<!-- quelle: Assessing Generative Models via Precision and Recall (p. 1–15) -->

## LITERATUR

<!-- quelle: References (p. 9–10) -->

- Olivier Bachem, Mario Lucic, Hamed Hassani, and Andreas Krause. Fast and provably good seedings for k-means. In Advances in Neural Information Processing Systems (NIPS) , 2016.
- Olivier Bachem, Mario Lucic, S Hamed Hassani, and Andreas Krause. Approximate k-means++ in sublinear time. In AAAI , 2016.
- Shane Barratt and Rishi Sharma. A Note on the Inception Score. arXiv preprint arXiv:1801.01973 , 2018.
- Mikołaj Bi´ nkowski, Dougal J. Sutherland, Michael Arbel, and Arthur Gretton. Demystifying MMD GANs. In International Conference on Learning Representations (ICLR) , 2018.
- Ali Borji. Pros and Cons of GAN Evaluation Measures. arXiv preprint arXiv:1802.03446 , 2018.
- Ondˇ rej Cífka, Aliaksei Severyn, Enrique Alfonseca, and Katja Filippova. Eval all, trust a few, do wrong to none: Comparing sentence generation models. arXiv preprint arXiv:1804.07972 , 2018.
- Alexis Conneau, Douwe Kiela, Holger Schwenk, Loic Barrault, and Antoine Bordes. Supervised Learning of Universal Sentence Representations from Natural Language Inference Data. arXiv preprint arXiv:1705.02364 , 2017.
- Ian Goodfellow, Jean Pouget-Abadie, Mehdi Mirza, Bing Xu, David Warde-Farley, Sherjil Ozair, Aaron Courville, and Yoshua Bengio. Generative Adversarial Networks. In Advances in Neural Information Processing Systems (NIPS) , 2014.
- Martin Heusel, Hubert Ramsauer, Thomas Unterthiner, Bernhard Nessler, Günter Klambauer, and Sepp Hochreiter. GANs trained by a two time-scale update rule converge to a Nash equilibrium. In Advances in Neural Information Processing Systems (NIPS) , 2017.
- Ferenc Huszár. How (not) to Train your Generative Model: Scheduled Sampling, Likelihood, Adversary? arXiv preprint arXiv:1511.05101 , 2015.
- Daniel Jiwoong Im, He Ma, Graham Taylor, and Kristin Branson. Quantitatively evaluating GANs with divergences proposed for training. In International Conference on Learning Representations (ICLR) , 2018.
- Diederik P Kingma and Max Welling. Auto-encoding Variational Bayes. In International Conference on Learning Representations (ICLR) , 2014.
- Alex Krizhevsky and Geoffrey Hinton. Learning multiple layers of features from tiny images, 2009.
- Karol Kurach, Mario Lucic, Xiaohua Zhai, Marcin Michalski, and Sylvain Gelly. The GAN Landscape: Losses, architectures, regularization, and normalization. arXiv preprint arXiv:1807.04720 , 2018.
- Yann LeCun, Léon Bottou, Yoshua Bengio, and Patrick Haffner. Gradient-based learning applied to document recognition. In IEEE , 1998.
- Ziwei Liu, Ping Luo, Xiaogang Wang, and Xiaoou Tang. Deep learning face attributes in the wild. In Proceedings of International Conference on Computer Vision (ICCV) , 2015.
- David Lopez-Paz and Maxime Oquab. Revisiting Classifier Two-Sample Tests. In International Conference on Learning Representations (ICLR) , 2016.
- Mario Lucic, Karol Kurach, Marcin Michalski, Sylvain Gelly, and Olivier Bousquet. Are GANs Created Equal? A Large-Scale Study. In Advances in Neural Information Processing Systems (NIPS) , 2018.
- Augustus Odena, Vincent Dumoulin, and Chris Olah. Deconvolution and checkerboard artifacts. Distill , 2016.
- Tim Salimans, Ian Goodfellow, Wojciech Zaremba, Vicki Cheung, Alec Radford, and Xi Chen. Improved Techniques for Training GANs. In Advances in Neural Information Processing Systems (NIPS) , 2016.
- David Sculley. Web-scale k-means clustering. In International Conference on World Wide Web (WWW) , 2010.
- Lucas Theis, Aäron van den Oord, and Matthias Bethge. A note on the evaluation of generative models. In International Conference on Learning Representations (ICLR) , 2016.
- Adina Williams, Nikita Nangia, and Samuel R Bowman. A broad-coverage challenge corpus for sentence understanding through inference. arXiv preprint arXiv:1704.05426 , 2017.
- Yuhuai Wu, Yuri Burda, Ruslan Salakhutdinov, and Roger Grosse. On the quantitative analysis of decoder-based generative models. In International Conference on Learning Representations (ICLR) , 2017.
- Han Xiao, Kashif Rasul, and Roland Vollgraf. Fashion-MNIST: A Novel Image Dataset for Benchmarking Machine Learning Algorithms. arXiv preprint arXiv:1708.07747 , 2017.

## GLOSSAR

- **PRD (Precision and Recall for Distributions)** — the set PRD(Q, P) of all attainable pairs (α, β) such that Q has precision α at recall β with respect to P, plus the pair (0, 0).
- **Precision (of a distribution)** — how much of Q can be generated by a "part" of P; intuitively the quality of samples from Q.
- **Recall (of a distribution)** — how much of P can be generated by a "part" of Q; intuitively the proportion of the target distribution covered by Q.
- **Precision α at recall β (Definition 1)** — Q has precision α at recall β w.r.t. P if there exist distributions μ, ν_P and ν_Q with P = βμ + ν_P and Q = αμ + ν_Q.
- **Recall loss** — the part of P that is "missed" by Q (the component ν_P).
- **Precision loss** — the "noise" part of Q that cannot be generated by P (the component ν_Q).
- **PRD curve** — a practical plot of the pairs (α(λ), β(λ)) computed on an equiangular grid of λ values, analogous to PR curves in binary classification.
- **F_β summary** — the generalization F_β = (1 + β²)p·r / ((β²p) + r) used to distill a PRD curve into a pair of values F_β and F_(1/β); β > 1 weighs recall higher, β < 1 weighs precision higher.
- **Mode dropping / mode collapse** — the failure case where a generative model produces only a subset of the modes of the target distribution, visible as a loss in recall.
- **Mode inventing** — the failure case where a generative model produces spurious modes not present in the target distribution, visible as a loss in precision.
