---
id: friedman-dieng-2023-the-vendi-score-a-diversity-evaluation-metric-for-machine-learning
titel: The Vendi Score. A Diversity Evaluation Metric for Machine Learning
autor: "Dan Friedman, Adji Bousso Dieng"
jahr: 2023
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2210.02410"
status: published
analyzed_at: "2026-07-31T12:02:36.380413+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# The Vendi Score. A Diversity Evaluation Metric for Machine Learning

## PROFIL

The text proposes the "Vendi Score"—the exponential of the Shannon entropy of the eigenvalues of a similarity matrix induced by a user-defined similarity function—as a general, reference-free metric for evaluating diversity in machine learning. It sets itself against existing domain-specific metrics that rely on reference datasets, pretrained classifiers, or discrete features, which limit flexibility and fail to account for feature correlations. Grounded in ecology (Hill, Jost) and quantum statistical mechanics (von Neumann entropy), the metric allows users to specify any desired form of diversity without requiring a reference distribution. For arts education, the Vendi Score provides a framework for assessing the diversity of student portfolios or generated artworks by encoding domain-specific aesthetic or conceptual similarities without relying on external benchmarks.

## WISSEN

### Problem Framing and Thesis

Diversity matters across ML—dataset curation, generative modeling, reinforcement learning, decoding—but existing diversity metrics are domain-specific and inflexible. They depend on a reference dataset, a pretrained classifier, or discrete features such as n-grams, limiting generality. Against this background, the authors propose a **reference-free** metric grounded in ecology, where biological diversity is defined as the exponential of the entropy of the species distribution within a population (Hill, 1973; Jost, 2006), interpretable as the effective number of species.

To adapt this to ML, the diversity of a collection $x_1, \ldots, x_n$ is defined as the exponential of the Shannon entropy of the eigenvalues of the $n \times n$ similarity matrix $K$, whose entries are pairwise similarity scores from a user-defined similarity function. This entropy coincides with the von Neumann entropy of $K$, motivating the name **Vendi Score** (von Neumann diversity).

The metric's sole inputs are the sample itself and a user-chosen similarity function, so it requires no reference dataset or label distribution and applies to any domain where similarity can be defined. The user-specified similarity function lets the evaluator encode any desired notion of diversity.

Figure 1 establishes three advantages over **IntDiv** (expected pairwise dissimilarity): (a) the Vendi Score scales linearly with the number of modes while IntDiv saturates toward 1; (b) combining distinct similarity functions increases the Vendi Score but leaves IntDiv unchanged; (c) the Vendi Score accounts for correlations between features, whereas IntDiv does not—it is highest when items differ across many uncorrelated attributes.

<!-- quelle: Problem Framing and Thesis -->

### Critique of Existing Diversity Metrics

Existing ML diversity metrics fall into several families, each with applicability or measurement shortcomings. **Reference-based metrics** (e.g., FID, precision/recall variants) define diversity as coverage of a reference distribution via an embedding function; they require a reference dataset. **Classifier-based metrics** (Inception Score, Number of Modes) define diversity through predefined labels, requiring labeled data and a separate classifier. **Discrete-feature metrics** (n-gram diversity) require an explicit discrete representation. **Similarity-based metrics** (average pairwise similarity/dissimilarity, including pairwise-BLEU and IntDiv) have two shortcomings demonstrated via similarity matrices over shape and color features: (1) average similarity becomes less sensitive as diversity increases, and (2) it does not account for correlations between features. The Vendi Score, by contrast, accounts for feature correlations and captures increased diversity from composing distinct similarity functions. A related ecology metric based on a similarity profile (Leinster and Cobbold, 2012) likewise fails to account for feature correlations. **Other metrics** face distinct limitations: the Birthday Paradox Test requires manual inspection; GILBO applies only to latent variable models; JSD-based diversity applies only to sets of probability distributions; Xie et al.'s threshold-based metric requires setting a threshold; quality diversity algorithms require picking a bin size. Mitchell et al. (2020) distinguish diversity (socially relevant attributes) from heterogeneity (arbitrary attributes); this paper uses diversity in the sense of heterogeneity. The author's self-positioning: the Vendi Score is reference-free, measuring intrinsic diversity rather than relationship to a reference, and should be used alongside a quality metric. Conclusion: existing metrics are either limited in applicability—requiring references, labels, domain-specificity, or parameter choices—or exhibit measurement shortcomings in capturing diversity.

<!-- quelle: Critique of Existing Diversity Metrics -->

### Defining the Vendi Score

The Vendi Score adapts ecology's diversity index — the exponential of the entropy of a species distribution — to ML. A naive extension using Shannon entropy of a model or dataset probability distribution is rejected because it requires a tractable probability distribution, unavailable in many ML settings. Instead, the metric should rely solely on the samples being evaluated, attain its maximum when all samples are dissimilar and its minimum when all are identical, which necessitates a similarity function over samples.

Given samples x₁,…,xₙ, a positive semidefinite similarity function k with k(x,x)=1, and kernel matrix K with entries K_{i,j}=k(x_i,x_j), the Vendi Score (VS) is the exponential of the Shannon entropy of the eigenvalues λ₁,…,λₙ of K/n:

VS = exp(−Σ λᵢ log λᵢ), with 0 log 0 = 0.

The score is well-defined because the eigenvalues of K/n are nonnegative (k is positive semidefinite) and sum to one (diagonal entries of K/n equal 1/n). It coincides with the effective rank of K (Roy and Vetterli, 2007), defined as the exponential of the entropy of normalized singular values. Lemma 3.1 shows the VS can be expressed directly as a function of K, establishing a connection to quantum statistical mechanics: the VS equals the exponential of the von Neumann entropy of K/n, where K/n plays the role of a density matrix. The formulation assumes independent sampling with p(xᵢ) ≈ 1/n; a generalization to an explicit probability distribution over the sample space exists (Definition 7.1, appendix).

<!-- quelle: Definition of the Vendi Score -->

### Properties of the Vendi Score

- The Vendi Score acts as an *effective number*, quantifying the effective number of dissimilar elements in a sample. This provides a consistent basis for comparing diversity via ratios and percentages; doubling the modes doubles the score.
- It accounts for feature correlations: a combined similarity function of $k$ and $k'$ can yield a score greater than the average of individual scores if they capture distinct variation dimensions, increasing as items differ in more, less correlated attributes.
- Theorem 3.1 defines four properties:
  1. *Effective number*: Maximized ($=n$) when all elements are dissimilar ($k(x_i, x_j)=0$ for $i \neq j$); minimized ($=1$) when all are identical ($k(x_i, x_j)=1$).
  2. *Identical elements*: If $k(x_i, x_j)=1$ for some $i \neq j$, combining them ($p'_i = p_i + p_j$) leaves the score unchanged. This justifies sampling approximations (e.g., 90 blue diamonds and 10 yellow squares equals a probability-weighted score of one blue spade and one yellow square, $p=(0.9, 0.1)$).
  3. *Partitioning*: For completely dissimilar collections ($k(x, x')=0$ across collections), the union's diversity depends only on individual diversities and relative sizes, forming a geometric mean with Shannon entropy.
  4. *Symmetry*: The score is invariant to element permutation, independent of similarity matrix row/column order.

<!-- quelle: Properties of the Vendi Score -->

### Computation and Connections to ML

Calculating the Vendi Score for a sample of n elements naively requires eigenvalue decomposition of an n × n similarity matrix, at O(n³). When embeddings φ(x) ∈ ℝᵈ with d ≪ n are available—as in most ML settings—the similarity matrix K = X⊤X can be used; since eigenvalues of K/n equal those of the covariance matrix XX⊤/n, the score is computed exactly in O(d²n + d³) = O(d²n), matching the complexity of FID. Without embeddings, the Nyström method approximates the score via column-sampling. The Vendi Score is the exponential of the kernel entropy H(K) = −tr K/n log K/n, whose empirical estimator converges at a rate proportional to 1/√n.

The score relates to two ML objects using similarity-matrix eigenvalues. **Determinantal Point Processes (dpps)** define subset likelihood as p(X) ∝ |K_X| = ∏ᵢ λᵢ, interpretable as squared volume in feature space. The dpp likelihood is not used for diversity evaluation: it vanishes with any duplicate and is less straightforward to interpret than the Vendi Score's effective number of dissimilar elements. **Spectral clustering** uses the graph Laplacian L = D − K, where the multiplicity of eigenvalue 0 equals the number of connected components. The Vendi Score is more general: it yields a meaningful measure for fully connected graphs and captures within-component diversity, whereas connected-component counting does not.

<!-- quelle: Computation and Connections to ML -->

### Experiments and Applications of the Vendi Score

VS is validated on synthetic mixture-of-normal data, then applied across molecular generation, GAN mode collapse, and image generation. On synthetic data varying component count, mixture proportions, or per-component variance, VS behaves as the *effective number of modes*, increasing proportionally with diversity; IntDiv is relatively insensitive to within-mode variance and shows diminishing returns for additional modes.

For molecular generative models (moses benchmark, Morgan fingerprint similarity), VS and IntDiv diverge on the HMM: IntDiv ranks it among the most diverse because average pairwise similarity is low, yet VS ranks it least diverse because it generates clusters of exact duplicates — a weakness IntDiv cannot detect.

For GAN mode collapse (StackedMNIST, 1000 modes), VS reveals finer-grained diversity than *number of modes* (nom). PresGAN and Self-conditioned GAN both capture all 1000 modes (nom = 1000), but VS distinguishes them (866.6 vs. 746.7), and both fall below the original dataset (943.7). To test whether low VS merely reflects mode-distribution imbalance, *Mode Diversity* — the exponential entropy of the predicted mode distribution — is computed; models score lower on VS than on Mode Diversity, confirming VS captures diversity aspects beyond distributional imbalance.

For image generative models (CIFAR-10, ImageNet 64×64, LSUN), VS is computed via cosine similarity of Inception embeddings. On low-resolution datasets, VS agrees with IS, FID, Precision, and Recall. On LSUN, the diffusion model (ADM) achieves high precision (0.63) and recall (0.52) yet scores lower on VS, indicating near-duplicates among non-reference-matching images. No model matches the original dataset's VS.

<!-- quelle: Experiments and Applications -->

### Limitations and Discussion of the Vendi Score

Three limitations constrain interpretation of vs. First, vs is a reference-free metric: it measures internal diversity of a set, not relation to a reference distribution. This suits settings lacking a reference but permits high scores on random noise—a property shared with other reference-free metrics such as IntDiv and n-gram diversity. vs should therefore be used alongside a quality metric. Second, vs depends on the choice of similarity function. An overly sensitive function makes all sets appear diverse; an insufficiently sensitive one makes all sets score low. A wrong choice can introduce biases skewing diversity scores, so the similarity function must be appropriate for the specific application. Third, computational cost of vs can be high when the similarity function is not associated with low-dimensional embeddings.

The Vendi Score is defined as a function of the pairwise similarity scores between elements of a sample and is interpretable as the effective number of unique elements in the sample. It is interpretable, general, and applicable to any domain where similarity can be defined. It is unsupervised, requiring no labels or reference probability distribution or dataset. The user specifies the form of diversity to measure via the similarity function. vs can be computed efficiently exactly and was demonstrated across several ml applications, datasets, and domains. Future work will leverage vs to improve data augmentation in limited-data settings.

<!-- quelle: Limitations and Discussion -->

### Acknowledgements and References

Funding: NSF OAC #2118201. Thanks to Sadhika Malladi for directing attention to the effective rank. Paper dedicated to PhD advisors David Blei and John Paisley.

The reference list spans several clusters relevant to the paper's conceptual apparatus: (1) diversity and entropy measurement in ecology and information theory (Hill 1973; Jost 2006; Patil & Taillie 1982; Leinster & Cobbold 2012; Leinster 2021); (2) effective dimensionality and rank (Roy & Vetterli 2007); (3) generative model evaluation, especially fidelity–diversity trade-offs (Sajjadi et al. 2018; Kynkäänniemi et al. 2019; Naeem et al. 2020; Simon et al. 2019); (4) GAN, VAE, and diffusion architectures (Karras et al. 2019, 2020; Dhariwal & Nichol 2021; Nichol & Dhariwal 2021; Child 2020); (5) NLP generation and evaluation including diversity-promoting objectives (Li et al. 2016; Vijayakumar et al. 2018; Papineni et al. 2002); (6) molecular generation benchmarks (Polykovskiy et al. 2020; Preuer et al. 2018); (7) quantum information theory and kernel methods (Bengtsson & Życzkowski 2017; Wilde 2013; Bach 2022; Jebara et al. 2004).

<!-- quelle: Acknowledgements, References, and Proofs -->

## GLOSSAR

- **Vendi Score (VS)** — The exponential of the Shannon entropy of the eigenvalues of a similarity matrix K induced by a user-defined similarity function; interpretable as the effective number of unique elements in a sample.
- **IntDiv** — Average pairwise dissimilarity used in biology, with similarity defined as Jaccard (Tanimoto) similarity between molecular fingerprints; becomes less sensitive as diversity increases and ignores feature correlations.
- **mode collapse** — A known shortcoming of GANs where the model fails to capture the full diversity of the training distribution; the Vendi Score can quantify it even when all labeled modes are nominally captured.
- **similarity profile** — A vector whose entries equal the expected similarity scores of each element, used in an entropy-based diversity metric from ecology that, like IntDiv, does not account for correlations between features.
- **effective rank** — The exponential of the entropy of the normalized singular values of a matrix, introduced in signal processing and here identified with the Vendi Score.
- **von Neumann entropy** — Entropy associated with a density matrix in quantum statistical mechanics; the Vendi Score equals its exponential when K/n is treated as the density matrix.
- **effective number** — The count of completely dissimilar elements that would yield the same diversity score as a given sample.
- **partitioning** — The property that the diversity of a union of completely dissimilar samples depends only on their individual diversities and relative sizes.
- **identical elements** — The property that combining identical elements into a single probability weight leaves the Vendi Score unchanged.
- **kernel entropy** — The quantity H(K) = −tr K/n log K/n, whose exponential gives the Vendi Score.
