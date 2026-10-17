---
id: truncated-vendi-2024-do-vendi-scores-converge-with-finite-samples
titel: Do Vendi Scores Converge with Finite Samples?. Truncated Vendi Score for Finite-Sample Convergence Guarantees
autor: "Azim Ospanov, Farzan Farnia"
jahr: 2024
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2410.21719"
status: published
analyzed_at: "2026-07-31T12:05:33.219960+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Do Vendi Scores Converge with Finite Samples?. Truncated Vendi Score for Finite-Sample Convergence Guarantees

## PROFIL

The text argues that the standard Vendi score [Friedman and Dieng, 2023], a reference-free diversity metric based on the Von Neumann entropy of a kernel similarity matrix, generally fails to converge to its population limit when computed with the practically constrained sample sizes (n ≤ 20,000) necessitated by O(n³) eigendecomposition costs—particularly for infinite-dimensional kernels such as the Gaussian RBF. It positions itself against the implicit assumption in prior literature that such restricted-sample Vendi estimates are reliable asymptotic proxies, and proposes the t-truncated Vendi score, which retains only the top t eigenvalues and is provably guaranteed to converge with n = O(t) samples regardless of kernel dimension. In contrast, the RKE score [Jalali et al., 2023], defined via order-2 Rényi entropy, is shown to enjoy universal convergence guarantees across all kernel functions without any truncation. The authors further demonstrate that existing approximation methods (Nyström, FKEA) converge to the truncated Vendi's asymptotic limit. For arts education, the text provides a methodological foundation for rigorously evaluating the diversity of AI-generated artistic outputs—images, text, video—without requiring reference datasets, though its utility is primarily technical rather than pedagogical.

## WISSEN

### Problem Framing and Motivation

Reference-free diversity scores enable evaluation of generative models without reference data. The **Vendi score** [Friedman and Dieng, 2023] quantifies diversity via the exponential of the Von Neumann entropy of the trace-normalized kernel matrix; the **RKE score** [Jalali et al., 2023] applies order-2 Rényi entropy to the same matrix, reducing to the inverse-squared Frobenius norm. Both avoid reference samples but require eigendecomposition of an n × n kernel matrix at O(n³) cost, practically limiting n to ≤ 20,000. This raises a convergence question: does the Vendi score estimated from such restricted sample sizes converge to its **population Vendi** — the asymptotic value under infinite sampling? The literature has not investigated this. The paper addresses the statistical convergence of both scores under finite-sample constraints, demonstrating numerically that the standard Vendi score with sample sizes below 20,000 may fail to converge (e.g., with an infinite-dimensional Gaussian kernel on ImageNet), while the RKE score enjoys universal convergence guarantees across all kernel functions.

<!-- quelle: Problem Framing and Motivation -->

### Vendi Convergence and the Truncated Vendi Score

We examine Vendi convergence for finite versus infinite feature dimension kernels. For finite dimension $d$, a sample size $n = O(d)$ suffices for convergence to the population Vendi; e.g., cosine similarity on ImageNet ($d=768$) converges near $n=5000$. Conversely, infinite feature maps like Gaussian kernels require significantly larger samples; on ImageNet, the score still grows at $n=20,000$.

To address this, we introduce the $t$-truncated Vendi score, computed from the top $t$ eigenvalues $\lambda_1 \ge \cdots \ge \lambda_t$, shifted by $c = (1 - \sum_{i=1}^t \lambda_i)/t$ to sum to 1. If $d \le t$, this matches the original score. We theoretically prove that $n = O(t)$ always estimates the $t$-truncated population Vendi, regardless of kernel dimension finiteness. Finally, we show existing efficient methods (Nyström, FKEA) approximate this truncated score.

<!-- quelle: Vendi Convergence Results and Truncated Vendi Score -->

### RKE Convergence Results and Contributions Summary

A universal convergence guarantee is proven for the RKE score: every order-α entropy score with α ≥ 2 converges to its population value within O(1/√n) error for n samples, across all kernel functions. This guarantee extends to the truncated RKE score, though truncation of the eigenspectrum is unnecessary for RKE since it already enjoys universal convergence. Figure 1 confirms near-convergence with fewer than 10,000 samples using cosine-similarity and Gaussian kernels.

Numerical experiments on image, text, and video datasets validate convergence behavior: with finite-dimension kernel maps, the Vendi score converges to its asymptotic limit and becomes identical to the truncated Vendi; with infinite-dimension Gaussian kernels, the Vendi score grows beyond n = 10,000, indicating non-convergence. The Nyström method and FKEA method yield tight estimations of the population truncated Vendi.

Contributions:
- Analyzing the statistical convergence of Vendi and RKE diversity scores under restricted sample sizes n ⪅ 2 × 10⁴,
- Providing numerical evidence on the Vendi score's lack of convergence for infinite-dimensional kernel functions, e.g. the Gaussian (RBF) kernel,
- Introducing the truncated Vendi score as a statistically converging extension of the Vendi score from finite to infinite dimension kernel functions,
- Demonstrating the universal convergence of the RKE diversity score across all kernel functions.

<!-- quelle: RKE Convergence Results and Contributions Summary -->

### Related Work and Literature Context

Diversity evaluation for generative models divides into **reference-based** methods (FID, KID, Recall, Coverage, MAUVE—measuring distance to or mode-capture of a predefined dataset) and **reference-free** methods (Vendi, RKE—scoring diversity via eigenvalues of a kernel similarity matrix, interpreted as mode identification and entropy of frequencies). This work focuses specifically on the statistical convergence of the vanilla Vendi and RKE scores.

Prior convergence analyses of kernel-matrix eigenvalues are insufficient for this purpose. Shawe-Taylor et al. provide concentration bounds centered on the *expectation* of eigenvalues for a fixed-size random dataset, but this center does not match the eigenvalues of the asymptotic kernel matrix as sample size approaches infinity. Bach proves non-asymptotic convergence of Von-Neumann entropy, but the bound may not guarantee convergence at practical sample sizes (<10000). This work targets convergence guarantees for finite-dimension and **t-truncated Vendi scores** with restricted sample sizes.

For efficient computation, the work adopts Nyström method (O(nm²)) and Random Fourier Features (O(n)), focusing on the population quantities these methods estimate.

Image experiments use DinoV2 embeddings (shown to align with human evaluation); the kernel function extends to InceptionV3 and CLIP embeddings.

<!-- quelle: Related Work and Literature Context -->

### Preliminaries: Kernel Functions, Vendi Score, and Population Limits

A reference-free evaluation of generative model G estimates diversity from n independent samples drawn from P_X. A kernel function k: X×X→R yields a PSD similarity matrix K; by Aronszajn's Theorem this is equivalent to a feature map ϕ with k(x,x')=⟨ϕ(x),ϕ(x')⟩. Both finite-dimension (e.g., cosine similarity) and infinite-dimension (e.g., Gaussian RBF) kernels are studied. Normalized kernels require k(x,x)=1, so the eigenvalues of (1/n)K sum to 1, forming a probability model.

Matrix-based Rényi entropy of a unit-trace PSD matrix is defined via its eigenvalues. The RKE diversity score (Jalali et al., 2023) applies order-α=2 entropy to (1/n)K; the general order-α Vendi score (Friedman and Dieng, 2023; Pasarkar and Dieng, 2024) applies order-α entropy to (1/n)K, reducing to the standard Vendi score at α=1.

Since (1/n)K = (1/n)ΦΦ⊤ shares non-zero eigenvalues with the empirical kernel covariance matrix Ĉ_X = (1/n)Φ⊤Φ, their entropies coincide: H_α((1/n)K) = H_α(Ĉ_X). The population Vendi score is defined via the population kernel covariance matrix C̃_X = E[ϕ(x)ϕ(x)⊤]; population RKE equals population Vendi₂.

<!-- quelle: Preliminaries and Definitions -->

### Statistical Convergence of Vendi and RKE Scores

The section asks how many samples suffice to estimate the population Vendi via the Vendi score. It first establishes (Theorem 1) a concentration bound on the sorted eigenvalues of the normalized kernel matrix for a normalized kernel (k(x,x)=1), relating empirical eigenvalues to those of the underlying covariance matrix, valid for n ≥ 2 + 8 log(1/δ) at probability ≥ 1−δ.

From this, Corollary 1 derives a **dimension-free** convergence guarantee for every Vendi_α with α ≥ 2, including the RKE score (Vendi_2): the bound holds regardless of kernel feature-map dimension, giving RKE a universal convergence guarantee across all kernel functions.

Corollary 2 addresses 1 ≤ α < 2 (including the standard order-1 Vendi score) under a **finite-dimensional** kernel map (dim(ϕ)=d<∞): (a) for α=1, a bound holds given n ≥ 32e² log(2/δ); (b) for 1<α<2, the Theorem 1 sample condition applies. The result indicates convergence of the Vendi score to population Vendi with n = O(d^{2−α}) samples, consistent with numerical observations using the finite-dimension cosine similarity kernel (Figure 1).

<!-- quelle: Theoretical Convergence Analysis of Vendi and RKE Scores -->

### Truncated Vendi Score and Proxy Kernel Estimation

Corollaries 1, 2 establish that the Vendi score converges to the population Vendi with n = O(d) samples when the order α > 2 or the kernel feature map dimension d is finite. However, for order 1 ≤ α < 2 with infinite kernel dimension (e.g., the original order-1 Vendi score with a Gaussian kernel), these results do not apply; numerical observations indicate sample sizes below 20000 may be insufficient for convergence. To address this gap, the **truncated Vendi score** is defined by truncating the eigenspectrum of the normalized kernel matrix to its top t eigenvalues, forming a truncated probability sequence and applying order-α entropy. The corresponding **t-truncated population Vendi** is a deterministic characteristic of the population distribution, whereas the truncated Vendi score is a sample-dependent statistic. Theorem 2 shows the t-truncated population Vendi is estimable with O(t) samples for every kernel function, with t playing the role of a bounded dimension. Theorem 3 establishes that the Nyström method and the FKEA method (using t random Fourier features) for reducing computational costs both have a bounded difference from the truncated population Vendi under specified conditions.

<!-- quelle: Truncated Vendi Score and Proxy Kernel Estimation -->

### Numerical Experiments and Empirical Validation

Experiments evaluate convergence of the Vendi score, the t-truncated Vendi score, and proxy Vendi scores (Nyström method, FKEA) across image (ImageNet, FFHQ), text (synthetic GPT-4 paragraphs), and video (Kinetics) data, using cosine similarity (finite-dimension) and Gaussian/RBF (infinite-dimension) kernels, with 20k samples per computation. The truncation parameter t is matched to the Nyström row-selection count and FKEA's random Fourier features count for comparability.

For the finite-dimension cosine kernel, the Vendi score converges rapidly and proxy versions are nearly identical. For the infinite-dimension Gaussian kernel, the original Vendi score does not converge at 20k samples and keeps growing, whereas the t-truncated Vendi score (t=10000) converges shortly after 10k samples; Nyström and FKEA with matched rank converge to the same limit. This empirically confirms the theoretical convergence results and links the truncated score to existing kernel-approximation methods.

To test correlation with ground-truth diversity, truncation is applied to StyleGAN3 (FFHQ) and StyleGAN-XL (ImageNet) with varying truncation coefficient ψ. The estimated t-truncated Vendi score (Gaussian kernel, t=10000) correlates with underlying diversity for order-α scores (α=1, 1.5, 2); Nyström and FKEA proxies remain close, confirming both computational efficiency and validity for evaluating generated-data diversity.

<!-- quelle: Numerical Experiments and Empirical Validation -->

### Statistical Convergence of Vendi Diversity Scores: Conclusion

The study investigates the statistical convergence behavior of Vendi diversity scores estimated from empirical samples. Because computational complexity limits score calculation to sample sizes below 10,000 for large datasets, the central question is whether such restricted samples suffice for convergence. The argument proceeds in three steps: (1) when the kernel feature dimension is bounded, small sample sizes do not impede statistical convergence; (2) numerical results demonstrate that an infinite-dimensional kernel map, such as the Gaussian kernel, fails to converge to the population Vendi; (3) to address this gap, the authors introduce the *truncated population Vendi* as an alternative target quantity for diversity evaluation. Existing Nyström and FKEA approximation methods are shown to concentrate around this truncated target. Future directions include exploring relationships between other kernel approximation techniques and the truncated population Vendi, and a comprehensive analysis of computational-statistical trade-offs in Vendi score estimation.

<!-- quelle: Conclusion, Acknowledgements, and References -->

### Proofs of Theoretical Results

**Theorem 1** applies the Vector Bernstein Inequality to zero-mean vectors v_i = φ(x_i)⊗φ(x_i) − E[φ(x)⊗φ(x)], bounding ∥Ĉ_X − C̃_X∥_HS, then uses the Hoffman-Wielandt inequality to convert this to eigenvalue concentration: ∥λ̂_n − λ̃∥_2 ≤ √(32 log(2/δ)/n) with probability 1−δ.

**Corollary 2 (α=1)** converts eigenvalue concentration to a bound on von-Neumann entropy difference H_1(Ĉ_n) − H_1(C_X) via two lemmas: Lemma 2 bounds |g(α)−g(β)| ≤ c log(1/c) for g(z)=z log(1/z) when |β−α|≤1/e (proved by cases around the maximum at 1/e); Lemma 3 bounds entropy gap via KKT-verified maximization, yielding u*=ε/√d·1 as global optimum. The sample assumption n ≥ 32e² log(2/δ) ensures the bound ≤ 1/e. For 1<α<2, the norm inequality ∥v∥_α ≤ d^{(2−α)/2}∥v∥_2 extends the result.

**Corollary 1 (α≥2)** uses the triangle inequality on the α-norm Vendi definition directly.

**Theorem 2** proves via Lemma 4 (KKT-verified projection onto the t-simplex) that t-truncated eigenvalues are ℓ₂-projections, so their distance is bounded by the original eigenvalue distance; Corollary 2's proof then applies in t-dimensional space.

**Theorem 3** analyzes FKEA, which approximates k(x,x') = E_ω[cos(ω⊤(x−x'))] via 1/t Σ cos(ω_i⊤(x−x')).

<!-- quelle: Appendix: Proofs of Theoretical Results -->

## GLOSSAR

- **Vendi score** — A reference-free diversity metric computed from the eigenvalues of a kernel similarity matrix of generated data, interpretable as mode identification and entropy of mode frequencies.
- **RKE score** — A reference-free diversity score, like Vendi, based on eigenvalues of a kernel similarity matrix, assigning diversity via entropy calculation over identified modes and their frequencies.
- **population Vendi** — The theoretical diversity value computed from eigenvalues of the underlying covariance matrix, which the Vendi score estimates.
- **t-truncated Vendi score** — A variant of the Vendi score where the kernel eigenspectrum is truncated and the mass of the tail (excluding the top-t eigenvalues) is uniformly redistributed among the top-t eigenvalues.
- **kernel feature dimension** — The dimensionality of the feature space induced by the kernel function, which can be finite or infinite.
- **truncated Vendi score** — A modified Vendi score computed by truncating the eigenspectrum of the normalized kernel matrix to its top t eigenvalues and applying order-α entropy to the resulting truncated probability sequence.
- **RKE diversity score** — The order-2 (Rényi) matrix-based entropy of the normalized kernel matrix, also called RKE mode count.
- **population kernel covariance matrix** — The expectation C̃_X = E[ϕ(x)ϕ(x)⊤] over the data distribution, whose entropy defines the population Vendi score under infinite sampling.
- **t-truncated population Vendi** — The deterministic population-level analogue of the truncated Vendi score, obtained by applying the same truncation process to the eigenspectrum of the population kernel covariance matrix.
- **proxy Vendi scores** — Approximations of the Vendi score computed via the Nyström method or FKEA (random Fourier features), reducing computational cost.
