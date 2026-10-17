---
id: belrose-et-al-2023-leace-perfect-linear-concept-erasure-in-closed-form
titel: "LEACE: Perfect linear concept erasure in closed form"
autor: "Nora Belrose, David Schneider-Joseph, Shauli Ravfogel, Ryan Cotterell, Edward Raff, Stella Biderman"
jahr: 2023
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2306.03819"
status: published
analyzed_at: "2026-07-31T09:32:57.411816+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# LEACE: Perfect linear concept erasure in closed form

## PROFIL

The text argues that LEAst-squares Concept Erasure (LEACE), a closed-form affine transformation, provably achieves linear guardedness—preventing all linear classifiers from detecting a specified concept—while minimally altering the embedding, and that concept scrubbing extends this to deep neural networks by sequentially applying LEACE to every layer. It sets itself against prior concept erasure techniques that rely on orthogonal projections or fundamentally nonlinear methods, demonstrating instead that linear subspace editing is sufficient and surgically optimal. The argument hinges on the equivalence between linear guardedness and equal class-conditional mean vectors, minimizing predictive V-information without inspecting model parameters. For arts education, this methodology provides a rigorous framework for auditing and mitigating bias or measuring the reliance of AI models on specific aesthetic or cultural concepts in generative or analytical tools.

## WISSEN

### LEACE: Linear Concept Erasure via Class-Centroid Equalization

Concept erasure edits a model's hidden states $X$ to minimize predictive $V$-information $I_V(X \to Z)$, preventing model $M$ from using concept $Z$. The necessary condition for $M$ using $Z$ is that $X$ has significant mutual information with $Z$; by the data processing inequality, $M$'s output cannot exceed its inputs' information about $Z$. **Guardedness** formalizes successful erasure: no classifier in family $V$ outperforms a constant function at predicting $Z$.

The central theoretical contribution is a previously unnoticed equivalence: a classification task is linearly guarded if and only if every class has the same mean feature vector. The following conditions are all equivalent:

1. The data $X$ linearly guards the labels $Z$.
2. For all convex losses $L$, the trivially attainable loss is optimal on $(X, Z)$.
3. The class-conditional mean vectors $E[X | Z = i]$ are equal to the unconditional mean $E[X]$.
4. Every component of $X$ has zero covariance with every component of $Z$.
5. Every linear classifier evaluated on $X$ exhibits statistical parity w.r.t. $Z$.

The proof that condition 3 implies condition 2 uses Jensen's inequality: any linear predictor's loss is lower-bounded by the loss at the unconditional mean, which equals a constant predictor's loss. If all class centroids coincide, data points are indistinguishable and $W = 0$ is optimal.

LEACE identifies the unique surgical affine transformation achieving linear guardedness while minimizing mean squared distance under all inner-product-induced norms. **Concept scrubbing** extends this to deep networks by sequentially applying LEACE to each layer's activations.

<!-- quelle: LEACE: Perfect linear concept erasure in closed form … 3.1 Equality of Class Centroids Implies Linear Guardedness -->

### Linear Guardedness, Zero Covariance, and the LEACE Erasure Formula

The argument establishes a chain of equivalences. **Lemma 3.2** proves that if a constant predictor (W*=0) is optimal for losses with bounded, non-vanishing off-category partial derivatives, then each class-conditional mean E[X|Z=i] equals E[X]. **Theorem 3.3** extends this to cross-entropy loss, whose off-category partial derivative exp(η_i)/Σexp(η_j) ∈ (0,1) is nonvanishing and bounded. **Theorem 3.4** shows that equal class-conditional means hold if and only if the cross-covariance matrix Σ_XZ is the zero matrix, completing the equivalence of guardedness with zero covariance.

**Theorem 4.1** then characterizes affine transformations r(x)=Px+b that achieve linear guardedness: the columns of Σ_XZ must lie in the null space of P. This implies that SAL, Mean Projection, and Fair PCA all achieve linear guardedness under suitable hyperparameters.

To derive a *minimal* edit, the objective E‖r(X)−X‖²_M is minimized subject to Cov(r(X),Z)=0. **Theorem 4.2** (centered case) gives P* = I − Σ_XX^{1/2} P_{WΣ_XZ} Σ_XX^{1/2}, where W is the whitening transform and P_{WΣ_XZ} is the orthogonal projection onto colsp(WΣ_XZ). **Theorem 4.3** extends to uncentered data with bias b*=E[X]−P*E[X]. The resulting LEACE formula de-means, whitens, orthogonally projects onto the complement of the subspace responsible for X–Z correlations, unwhitens, and subtracts from x—surgically removing linearly available information about Z.

<!-- quelle: 3.2 Linear Guardedness Implies Equality of Class Centroids … 4.1 Derivation of LEACE -->

### Oblique Optimality, Evaluation, and Concept Scrubbing

Prior work assumes erasure functions should be orthogonal projections, since orthogonal projection yields the nearest point in a subspace. LEACE is not orthogonal in general (the projection matrix is symmetric only when P_WΣ_XZ and W commute), but it is oblique: (P*)² = P*. Orthogonal projections are not least-squares optimal because the guardedness condition PΣ_XZ = 0 constrains the nullspace, not the range; one may freely choose the range to minimize mean squared distance provided colsp(Σ_XZ) is zeroed out. LEACE extends to continuous Z under OLS loss without categorical assumptions, since the equivalence between zero cross-covariance and zero-weight optimality holds in the OLS setting.

On BERT [CLS] embeddings from a biography dataset, LEACE achieves random accuracy (perfect erasure) with a small edit, roughly two orders of magnitude faster than RLACE, without gradient-based optimization. Profession-prediction accuracy drops minimally (79.3% → 77.3%), while TPR gap falls from 0.198 to 0.084 and σ(GAP_TPR, %Women) from 0.867 to 0.392.

Replicating amnesic probing experiments on bert-base-uncased with POS tags: INLP requires 20 iterations, reducing rank by 360, while LEACE reduces rank by 17. INLP's maximum effect at layer 6 is confounded by collateral damage; LEACE's mild changes through layer 8 with the largest drop at layer 11 isolate the causal effect of POS there, contrasting with probing optima at earlier layers. INLP's collateral damage prevents multi-layer application without output collapse.

<!-- quelle: 4.2 Oblique Projections are Least-Squares Optimal … 6 Concept Scrubbing -->

### Concept Scrubbing: Sequential LEACE Across All Layers

The paper introduces **concept scrubbing** — erasing all linear information about a concept at every layer. LEACE makes this practical with minimal collateral damage, low overhead, and streaming covariance statistics.

Because any intervention at layer ℓ changes hidden-state distributions at layers ℓ′ > ℓ, independently fitting LEACE parameters for all layers then applying them simultaneously may fail to fully erase the target. Parameters must instead be fit **sequentially**: after computing (P, b) for a layer, scrub that layer immediately, then feed scrubbed embeddings forward (Algorithm 1). This caching approach requires up to 500GB; recomputing hidden states avoids memory cost but increases total compute from O(ℓ) to O(ℓ²).

Part-of-speech information is scrubbed from Pythia (160M–12B) and LLaMA (7B–30B) models. A **randomized erasure** control — projecting onto a random same-rank subspace — isolates concept erasure from generic degradation. SAL (full-rank) serves as baseline; it lacks a bias term and ignores inter-feature correlations.

Random subspace erasure barely affects perplexity, but POS scrubbing causes large increases across all models. SAL induces significantly larger perplexity increases than LEACE, indicating more collateral damage. LEACE more closely approximates the ideal intervention erasing only the target concept; SAL alone would overestimate POS's causal effect.

The authors flag the need for experiments on narrower concepts with behavioral metrics, and note optimizers might circumvent constraints by encoding attributes nonlinearly. They conjecture nondestructive nonlinear erasure is intractable without detailed knowledge of the data-generating process.

<!-- quelle: Algorithm 1 Concept scrubbing … A Additional Related Work -->

### Equivalences, Prior Work, and LEACE Derivation

**B.** Guardedness ⟺ constant-predictor optimality. B.1: if X (V,L)-guards Z, then L_τ(Z,L) = inf_θ E[L(η(X;θ),Z)] — the null vector X'=0 yields only constant predictors, and guardedness chains the inequality so no predictor in V beats L_τ. B.2: converse — for arbitrary X' with finite first moment, the best loss on (X',Z) ≥ L_τ (constant predictors exist in V), so X maximizes the minimal achievable loss, hence guards Z.

**C.** Linear guardedness ⟺ linear statistical parity. Definition C.1: f exhibits statistical parity w.r.t. Z on X if E[f(X)|Z=z] = E[f(X)] for all z. Theorem C.2: every linear f(x)=b+Wx satisfies this iff E[X|Z=z]=E[X]. Forward: linearity of expectation. Converse: the identity function id(x)=x is itself linear.

**D.** Theorem 4.1 implies full-rank SAL (n=rank(Σ_XZ)) guarantees linear guardedness, since its projection matrix uses an orthonormal basis for Σ_XZ's column space. Mean Projection (MP) guarantees linear guardedness by Theorem 3.1 (equal post-projection centroids); by Theorem 3.4, MP ≡ SAL for binary Z.

**E.** Theorem 4.2 gives the closed-form solution P*=I−W⁺P_{WΣ_XZ}W, where W=(Σ_XX^{1/2})⁺. Algebraic proof: each row P_i is an independent subproblem; in a basis where the first ℓ=rank(Σ_XZ) whitened components of X correlate with Z, the constraint Cov(PX,Z)=0 forces A_ij=0 for j≤ℓ; the minimizer is A=W⁺(I−P_{WΣ_XZ}), yielding P*=I−W⁺P_{WΣ_XZ}W.

<!-- quelle: B Equivalence of Guardedness with the Optimality of Constant Predictors … E.1 Algebraic Proof -->

### LEACE Proofs, Oblique Optimality, Guardedness Equivalence, and Norm Regularization

**E.2 Covector Proof.** Diagonalizing the inner product M lets each row P_i be optimized separately. The objective depends on P_i only through ξ = P_i^T X; all such scalar variables form a vector space U under the covariance inner product. Elements uncorrelated with Z form subspace Z^⊥. The difficulty: orthogonality in U is not equivalent to orthogonality of the corresponding covectors. Changing basis via W^+ aligns the two inner products, so the orthogonal projection of X_i onto Z^⊥ becomes an orthogonal projection of covector (W^+)_i^T onto colsp(WΣ_XZ)^⊥, yielding the final solution that preserves non-varying components.

**F. Oblique Optimality.** Optimal affine erasure need not use orthogonal projection. Example: d=2, k=1, X_2 = X_1 + Z. Orthogonal projection nullifies X_2 entirely; an oblique projection exploits X_1's information about X_2 to partially reconstruct it while fully erasing Z, achieving better MSE.

**G. Guardedness Equivalence.** Xu et al.'s V-entropy H_V(Z|X) is the lowest cross-entropy loss predicting Z from X; unconditional V-entropy H_V(Z) equals the trivially attainable loss L_τ. X guards Z iff H_V(Z|X) = L_τ = H_V(Z), i.e., V-information I_V(X→Z) < ε for all ε > 0.

**H. Norm Constraint.** LEACE's oblique P can have singular values > 1, causing norm divergence (NaN). SAL's orthogonal Q (eigenvalues in {0,1}) never increases norm. Fix: if tr(PΣ_XX P^T) > tr(Σ_XX), find convex combination P' = αP + (1-α)Q preserving tr(Σ_XX). By Theorem 4.1's convexity, P' stays feasible with no worse MSE than Q.

<!-- quelle: E.2 Covector Proof … H Constraining Norm Growth -->

### Oracle LEACE: Closed-Form Concept Erasure

Given oracle access to labels **z** for each **x**, a more surgical erasure is possible: a closed-form formula for the nearest **X′** to **X** such that Cov(**X′**, **Z**) = 0. "Nearest" holds simultaneously for all p.s.d. inner products **a**ᵀ**M****b** on ℝᵈ, because diagonalizing **M** decomposes the problem into *d* independent scalar subproblems, each an orthogonal projection not in ℝᵈ but in a Hilbert space **H** of square-integrable real-valued random variables with inner product ⟨ξ, ζ⟩_H := E[ξζ].

Prior work established that orthogonal projection in such a Hilbert space is equivalent to OLS regression. The theorem extends this: **X′**_LEACE equals the OLS residual from regressing **X** on **Z**, plus a constant shift preserving the mean of **X**.

**Theorem I.1 (Oracle Concept Erasure).** For every p.s.d. inner product on ℝᵈ, the minimizer is the shifted OLS residual: **X′** = **X** − Σ_XZ Σ_ZZ⁺ (**Z** − E[**Z**]).

**Proof sketch.** In a basis diagonalizing **M**, the objective decomposes into independent per-component terms ‖X′ᵢ − Xᵢ‖²_H. Each Xᵢ is orthogonally decomposed along the subspace of constant random variables C = span(1): Xᵢ = X̃ᵢ + μᵢ. The constraint Cov(**X′**, **Z**) = 0 is invariant to constant shifts, so the two terms optimize independently. The constant term is minimized trivially by μ′ᵢ = μᵢ (mean preserved). The zero-mean term requires X̃′ᵢ orthogonal to Z̃ = span({Z̃₁, …, Z̃_k}), which is the orthogonal projection of X̃ᵢ onto Z̃⊥ — equivalently, the OLS residual from regressing X̃ on Z̃. Combining all components yields the closed form.

<!-- quelle: I Oracle LEACE … J Notation Key -->

## GLOSSAR

- **guardedness** — Property of a data vector X that maximizes the minimal achievable loss over a predictor class V and loss family L, preventing any predictor in V from exploiting information about Z.
- **trivially attainable loss** — The lowest expected loss achievable by a constant predictor, serving as the baseline that linearly guarded data cannot improve upon.
- **concept scrubbing** — The procedure of erasing all linear information about a target concept from the activations at every layer of a neural network, applied sequentially from the first layer to the last.
- **linear guardedness** — Property whereby no linear predictor can achieve loss below the trivially attainable baseline for predicting Z from X.
- **off-category partial derivative** — The partial derivative of loss with respect to a logit η_i when the true category differs from i; assumed nonvanishing and category-independent.
- **LEACE** — Closed-form affine erasure that whitens data, projects out the subspace encoding concept–feature correlations, then unwhitens, minimizing perturbation while guaranteeing linear guardedness.
- **oblique projection** — A projection matrix not restricted to orthogonality, allowing singular values greater than 1 and potentially better MSE than orthogonal alternatives.
- **TPR-GAP** — A bias measure quantifying the difference in true positive rate between groups differing in a protected attribute.
- **amnesic probing** — A causal intervention that removes a concept from model activations to test its importance to a main task.
- **randomized erasure** — A control condition in which hidden states are orthogonally projected onto a random linear subspace of the same rank as the cross-covariance matrix, to isolate the effect of concept erasure from generic performance degradation.
