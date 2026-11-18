---
id: naeem-et-al-2020-reliable-fidelity-and-diversity-metrics-for-generative-models
titel: Reliable Fidelity and Diversity Metrics for Generative Models
autor: "Muhammad Ferjad Naeem, Seong Joon Oh, Youngjung Uh, Yunjey Choi, Jaejun Yoo"
jahr: 2020
quelle: "Proceedings of the 37th International Conference on Machine Learning, Vienna, Austria, PMLR 119, 2020"
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2002.09797"
status: published
checks: passed
review: passed
analyzed_at: "2026-11-15T11:00:10.564068+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: pdf
---

# Reliable Fidelity and Diversity Metrics for Generative Models

## PROFIL

The article "Reliable Fidelity and Diversity Metrics for Generative Models" was written by Muhammad Ferjad Naeem, Seong Joon Oh, Youngjung Uh, Yunjey Choi and Jaejun Yoo, researchers at Clova AI Research, Naver Corp., with TU München and EPFL, and presented at ICML 2020. It is addressed to researchers who need to evaluate generative image models, and it argues that the widely used Fréchet Inception Distance (FID) collapses fidelity and diversity into a single number, and that the improved precision and recall (P&R) of Kynkäänniemi et al. (2019) is unreliable: its manifolds overestimate around outliers, it fails to detect certain mode dropping, and it lacks a rationale for hyperparameter choice. The authors propose two replacement metrics, density and coverage (D&C), which count how many real-sample neighbourhood spheres contain each fake sample and build the nearest-neighbour manifold around real samples, and they set out four conditions a useful metric must satisfy (detecting identical distributions, robustness to outliers, responsiveness to mode dropping, ease of hyperparameter selection). The paper first reviews the evaluation pipeline and prior metrics (Parzen window estimates, the Inception Score, FID, and the precision/recall formulations of Sajjadi et al. 2018 and Kynkäänniemi et al. 2019), then demonstrates P&R's failure modes, derives closed-form expected values for D&C that enable systematic hyperparameter selection (M = N = 10000, k = 5), and reports toy and real-world sanity checks on Gaussians, FFHQ, CelebA, LSUN-bedroom and MNIST, including fidelity–diversity trade-off analysis via latent truncation and comparison with negative log likelihood. A further part criticises the reliance on ImageNet pre-trained embeddings and shows that randomly initialised CNN features (R64) are preferable when the target domain, such as MNIST digits or SC09 speech spectrograms, diverges from ImageNet statistics. The work is usable in machine learning and generative-model research wherever stable, interpretable diagnosis of fidelity and diversity is needed, and the authors release code at github.com/clovaai/generative-evaluation-prdc.

## WISSEN

### Purpose and Thesis (p. 1–2)

This paper by Muhammad Ferjad Naeem, Seong Joon Oh, Youngjung Uh, Yunjey Choi and Jaejun Yoo (Clova AI Research, Naver Corp., with TU München and EPFL; ICML 2020) addresses the problem of evaluating generative image models. The widely used Fréchet Inception Distance (FID) collapses quality into a single number and cannot separate two key aspects: **fidelity** (how closely generated samples resemble real ones) and **diversity** (whether generated samples cover the full variability of real samples). Recent "precision and recall" metrics attempt to measure these separately, but the authors show that even the most recent version (Kynkäänniemi et al., 2019) is unreliable. They propose two new metrics, **density and coverage (D&C)**, which are more interpretable, robust, and theoretically analysable. They also criticise the near-universal reliance on ImageNet pre-trained embeddings and propose randomly initialised CNN features as an alternative when the target data differs greatly from ImageNet.

The authors state four necessary conditions for a useful evaluation metric: (1) ability to detect identical real and fake distributions, (2) robustness to outlier samples, (3) responsiveness to mode dropping, and (4) ease of hyperparameter selection. Improved precision and recall (P&R) fails all four; D&C satisfies them.

### Background: Evaluation Pipeline and Prior Metrics (p. 2)

Evaluating generative models P(X) is harder than evaluating discriminative models, because it requires comparing distributions of high-dimensional data. The standard pipeline has three stages: (1) embed real and fake samples into a Euclidean space via a non-linear mapping such as a CNN feature extractor, (2) build real and fake distributions from the embedded samples, and (3) quantify the discrepancy between them.

Existing approaches include: Parzen window estimates (Gaussian kernels around real samples); the Inception Score (IS), which compares class predictions per sample against the marginalised class distribution via KL divergence; and FID, which models embedded real and fake samples as multivariate Gaussians and measures their Fréchet (Wasserstein-2) distance. FID generally agrees with human judgement but conflates fidelity and diversity.

Prior two-value metrics: Sajjadi et al. (2018) defined precision (the portion of Q(Y) generable by P(X)) and recall (the symmetric quantity) from estimated supports, but these rely on initialisation-sensitive k-means and assume uniform embedding density. Kynkäänniemi et al. (2019) proposed **improved precision and recall (P&R)**, which builds a "manifold" for each distribution as the union of spheres B(x, r) around each sample, with radius r set by the k-th nearest neighbour distance NND_k. Precision is the fraction of fake samples falling inside the real manifold; recall is the fraction of real samples inside the fake manifold.

### Problems with Improved Precision and Recall (p. 3–4)

The P&R spheres are not normalised by their radii or local sample density, so the manifold is overestimated around outliers:

- **Precision**: a single real outlier inflates the real manifold; generating many fake samples near that outlier raises precision without real quality (the pathological example yields 100% precision, while density gives 60%).
- **Recall**: the fake manifold is built from fake samples, which tend to include many unrealistic but diverse outputs, so the fake manifold overestimates the true fake distribution and recall gains points for real samples inside the overestimated region. Additionally, the fake manifold must be recomputed per model, costing O(kM log M) per evaluation.

### The Proposed Metrics: Density and Coverage (p. 4)

- **Density** improves precision by counting *how many* real-sample neighbourhood spheres contain each fake sample (rather than a binary in/out decision), forming a manifold by superposition of spheres. This is midway between precision and the Parzen window estimate. It rewards fake samples in densely packed real regions, reducing outlier vulnerability. Unlike precision, density is not upper-bounded by 1.
- **Coverage** improves recall by building the nearest-neighbour manifold around the *real* samples (which have fewer outliers) and measuring the fraction of real samples whose neighbourhoods contain at least one fake sample. The manifold is computed once per dataset rather than per model. Coverage is bounded between 0 and 1.

### Analytic Behaviour and Hyperparameter Selection (p. 4–5)

For identical real and fake distributions, P&R has no simple analytic expression for its expected value because of complex dependencies. In contrast, D&C admits closed forms: E[density] = 1, and E[coverage] is given by a combinatorial formula (the probability that the k−1 smallest of N+M−1 iid distances are all "blue"), which notably does not depend on the distribution type or data dimensionality.

This enables systematic hyperparameter selection with the goal E[coverage] > 1 − ε. The authors set M = N = 10000 and k = 5, giving E[coverage] ≈ 0.969 > 0.95. They note that the rationale behind P&R's choices (k = 3, M = N = 50000) is unknown. Experiments with 64-dimensional Gaussians, 4096-dimensional VGG embeddings of FFHQ faces, and the analytic estimates confirm that D&C values agree across data types, whereas P&R values differ substantially.

### Empirical Results (p. 5–8)

#### Toy sanity checks (p. 5–7)

With X ~ N(0, I) and Y ~ N(µ1, I) in R^64:

- **Distribution match (µ = 0)**: P&R values fall far below 1 (0.68 precision, 0.67 recall), while D&C approach 1 (1.06 density, 0.97 coverage).
- **One outlier at x = +3** added to real or fake samples: P&R are badly affected (precision rises for µ > 0.5; recall rises for µ < −0.4), while D&C largely coincide with the no-outlier case.
- **Mode dropping** on a ten-mode Gaussian mixture, dropped sequentially or simultaneously: recall fails to detect simultaneous dropping until concentration on one mode reaches 90%, then drops suddenly; coverage decreases gradually and reliably in both scenarios.

#### Real-world sanity checks (p. 7–8)

Using fc2 features of ImageNet pre-trained VGG16:

- **Outliers**: on StyleGAN images of CelebA and LSUN-bedroom, with fake samples split 10:1 into inliers/outliers by k-th nearest neighbour distance, adding outliers increases recall by more than 11% (CelebA) and 15% (LSUN bedroom), while coverage increases by less than 2%.
- **Mode dropping on MNIST** (favouring class '0'): recall cannot detect the diversity loss until class '0' exceeds 90%, while coverage drops gradually.
- **Fidelity–diversity trade-off**: truncation analysis on StyleGAN/FFHQ with latent truncation threshold ψ. As ψ increases, fidelity decreases and diversity increases; precision and density decrease while recall and coverage increase, with density giving finer-grained diagnosis than precision.
- **Relation to negative log likelihood (NLL)**: for a convolutional VAE on MNIST, NLL barely distinguishes latent truncation (41.4 vs 40.2), whereas D&C reveal that truncation leaves density nearly unchanged (0.208 → 0.205) but sharply reduces coverage (0.411 → 0.291), i.e., a diversity loss without fidelity gain.

### Random Embeddings (p. 8–9)

The authors examine the embedding stage, noting that ImageNet pre-trained features embed dataset bias. They compare three embeddings: T4096 (fc2 features of ImageNet pre-trained VGG16), R4096 (fc2 of randomly initialised VGG16), and R64 (a randomly initialised VGG16 with the 4096-dimensional fc2 replaced by 64 dimensions).

- On natural images (StyleGAN FFHQ with varying ψ), metrics on R64 closely follow those on T4096, so R64 is usable for ImageNet-like data.
- Beyond natural images — DCGAN on MNIST and WaveGAN spectrograms on the Speech Commands Zero Through Nine (SC09) dataset — T4096 severely underestimates quality. For MNIST, density is 0.02 under T4096 versus 0.53 under R64; for sound, recall (0.03) and coverage (0.02) under T4096 are severe underestimations of actual diversity, whereas R64 gives 0.58 recall and 0.70 coverage. When the target domain differs greatly from ImageNet statistics, random embeddings are the more reasonable choice.

### Conclusion (p. 9)

The paper shows that improved precision and recall overestimate manifolds, underestimate scores for identical distributions, are not robust to outliers, and miss certain mode dropping. Density and coverage remedy these issues and permit systematic hyperparameter selection. The authors recommend that researchers adopt D&C for stable, reliable model diagnosis, and use random embeddings when the target distribution diverges significantly from ImageNet. Code is available at github.com/clovaai/generative-evaluation-prdc.

### Figures (p. 3–8)

*Fig. 1 (p. 3):* Overview of metrics. Two example scenarios for illustrating the advantage of density over precision and coverage over recall. Note that for recall versus coverage figure, the real and fake samples are identical across left and right. — The image is a two-panel schematic diagram. The left panel, captioned “(a) Precision versus density,” shows clustered purple circles labeled “Real manifold” with purple “Real samples” dots, plus a larger purple circle holding green “Fake samples” dots and a single “Real outlier,” marked “k = 2,” with the text “Precision = (1+1+1+1+1)/5 = 100%” and “Density = (2+2+2+2+1)/(2+2+2+2+2) = 60%.” The right panel, captioned “(b) Recall versus coverage,” is divided by a vertical dashed line: the left side shows a large green “Fake manifold” circle with “k = 1” and “Recall = 5/5 = 100%,” while the right side shows purple “Real manifold” circles with “k = 1” and “Coverage = 1/5 = 20%.” _(Lettering in the image, read by the image model, not confirmed: “Precision = (1+1+1+1+1)/5 = 100%”, “Density = (2+2+2+2+1)/(2+2+2+2+2) = 60%.”, “Recall = 5/5 = 100%,”)_

*Fig. 2 (p. 5):* Metrics under identical real and fake distributions. Results with Gaussian and FFHQ data are shown. For density and coverage, the expected values derived in § 3.3 are plotted. In each case, the values are shown with respect to the varying number of samples N = M (assume the same number of real and fake samples) and the nearest neighbours k . — This is a figure made of ten small heatmap charts arranged in two rows, grouped under the headings “Precision” and “Density” on the top row and “Recall” and “Coverage” on the bottom row. Each heatmap is titled “Gaussian”, “FFHQ”, or “Analytic”, with the horizontal axis labeled “k” (1–10) and the vertical axis labeled “Samples” (500 to 32000), plus a vertical color bar beside each plot. The “Precision” and “Recall” plots for “Gaussian” and “FFHQ” show green/yellow at low k changing toward red at higher k, while the “Density” and “Coverage” plots are mostly red/pink with variation near low k and low sample counts.

*Fig. 3 (p. 6):* Robustness to outliers for toy data. Behaviour of the four metrics when the real distribution is fixed X ∼ N (0 , I ) and fake distribution Y ∼ N ( µ, I ) shifts with µ ∈ [ -1 , 1] . We further consider two outlier scenarios where a sample at x = +3 is added either to the set of real or fake samples. — This is a composite diagram: on the left, a 3D-style schematic shows a black curve labeled “Real” and several orange bell curves labeled “Fake” with “μ = -1”, “μ = 0”, and “μ = +1”, plus points marked “Real outliers” and “Fake outliers”; a legend lists “No-outlier case”, “One outlier in real”, and “One outlier in fake”. On the right are four line charts in a 2×2 grid titled “precision”, “recall”, “density”, and “coverage”. Each chart has an x-axis labeled “μ” from -1.0 to 1.0 and a y-axis from 0.0 to 1.0, with several dashed curves. In “precision” and “density”, one dashed curve peaks near μ = 0.0 while another dashed curve rises or stays low toward μ = 1.0; in “recall” and “coverage”, the dashed curves vary across the same μ range.

*Fig. 4 (p. 6):* Sensitivity to mode dropping for toy data. Assuming the mixture-of-Gaussian real distribution X , we simulate two paths in which the perfect fake distribution Y drops to a single mode. Under the sequential dropping , Y drops a mode one at a time; under the simultaneous dropping , Y gradually decreases samples in all but one mode. Corresponding behaviours of the four metrics are shown. — The picture is a scientific figure/diagram, not a photograph: on the left are schematic distribution drawings and on the right are four line charts. The left part shows a “Real distribution” as a black four-peaked curve, and under “Fake distributions” two columns labeled “Sequential dropping” (blue) and “Simultaneous dropping” (magenta) with rows of curves in which peaks are progressively removed. The right part has four plots titled “precision,” “recall,” “density,” and “coverage,” with y-axis ticks 0.0, 0.5, 1.0 and an x-axis labeled “Concentration on the first mode” running from 0.00 to 1.00. In the charts, dashed lines stay high in “precision” (around 0.8) and “density” (near 1.0), while in “recall” and “coverage” the blue dashed line falls toward 0.0 and the magenta dashed line stays higher, with “coverage” for magenta declining mainly near 1.00.

*Fig. 5 (p. 7):* Recall versus coverage against the amount of outliers. Example inliers and the worst outliers are shown below. — The figure is a composite of two line charts across the top, labeled "CelebA" on the left and "LSUN-Bedroom" on the right, each plotting a purple line labeled "recall" that rises and a green line labeled "coverage" that stays nearly flat, with the x-axis labeled "ratio of outliers to inliers (%)" and the y-axis labeled "values relative to the 0% outlier case". Below the left chart are two grids of face photographs, the upper grid labeled "Inliers" and the lower grid labeled "Worst outliers" showing faces with sunglasses and headwear. Below the right chart are two grids of bedroom photographs, the upper grid labeled "Inliers" and the lower grid labeled "Worst outliers" showing colorful and cluttered rooms.

*Fig. 6 (p. 7):* Metrics under mode dropping on MNIST. Behaviour of the metrics under varying degrees of the mode dropping towards a single class on MNIST with R64 . The real distribution has the uniform class distribution while the fake distribution has an increasing ratio of the class '0'. — The image shows two side-by-side line charts with gridlines, labeled "(a) Precision vs density" and "(b) Recall vs coverage". Both charts plot values on a vertical axis from 0.00 to 1.00 against a horizontal axis labeled "Ratio of single-mode samples" ranging from 0 to 1.0. In chart (a), a purple line labeled "Precision" stays nearly flat just below 1.00, while a green line labeled "Density" rises slightly above 1.00 as the ratio increases. In chart (b), a blue line labeled "Recall" remains near 1.00 until the ratio approaches 1.0, where it drops steeply, and a pink line labeled "Coverage" declines steadily from just below 1.00 down to about 0.25 at a ratio of 1.0.

*Fig. 7 (p. 8):* Behaviour of metrics with ψ . The latent truncation threshold ψ is applied over over StyleGAN generated images on FFHQ. Qualitative examples are given. — It is a composite figure with four line charts in a 2×2 grid above a horizontal strip of small face-image grids. The charts have y-axis labels “Precision,” “Recall,” “Density,” and “Coverage,” an x-axis labeled “ψ,” and a legend reading “T4096,” “R4096,” and “R64.” Below the charts are five groups of face thumbnails labeled “ψ = 0.2,” “ψ = 0.4,” “ψ = 0.6,” “ψ = 0.8,” and “ψ = 1.0.”

*Image 8 (p. 8):* Failure of trained embeddings. Evaluation results of generated samples beyond natural images using T4096 , R4096 , and R64 . Corresponding real and fake qualitative samples shown. — The figure displays four grids of grayscale images arranged in two rows above a data table. The top-left grid is labeled "Real MNIST" and contains handwritten digits, the top-right is labeled "Real spectrogram" and contains spectrogram images, the bottom-left is labeled "DCGAN" and contains generated digit images, and the bottom-right is labeled "WaveGAN" and contains generated spectrogram images. The table below has "Methods" in the top-left corner, with column groups labeled "MNIST" and "Sound," each subdivided into "T4096," "R4096," and "R64," and row labels "Precision," "Recall," "Density," and "Coverage" with corresponding numerical values.

<!-- quelle: Reliable Fidelity and Diversity Metrics for Generative Models (p. 1–9) -->

## LITERATUR

<!-- quelle: References (p. 9–10) -->

- Bengio, Y., Mesnil, G., Dauphin, Y., and Rifai, S. Better mixing via deep representations. In Proceedings of the 30th International Conference on Machine Learning , 2013.
- Borji, A. Pros and cons of gan evaluation measures. Computer Vision and Image Understanding , 2019.
- Brock, A., Donahue, J., and Simonyan, K. Large scale gan training for high fidelity natural image synthesis. International Conference on Learning Representations , 2018.
- Deng, J., Dong, W., Socher, R., Li, L.-J., Li, K., and Fei-Fei, L. Imagenet: A large-scale hierarchical image database. In IEEE Conference on Computer Vision and Pattern Recognition , 2009.
- Donahue, C., McAuley, J., and Puckette, M. Adversarial audio synthesis. In International Conference on Learning Representations , 2019.
- Dowson, D. and Landau, B. The fr´ echet distance between multivariate normal distributions. Journal of multivariate analysis , 12(3):450-455, 1982.
- Geirhos, R., Rubisch, P., Michaelis, C., Bethge, M., Wichmann, F. A., and Brendel, W. Imagenet-trained CNNs are biased towards texture; increasing shape bias improves accuracy and robustness. In International Conference on Learning Representations , 2019.
- Heusel, M., Ramsauer, H., Unterthiner, T., Nessler, B., and Hochreiter, S. Gans trained by a two time-scale update rule converge to a local nash equilibrium. In Advances in neural information processing systems , pp. 6626-6637, 2017.
- Karras, T., Laine, S., and Aila, T. A style-based generator architecture for generative adversarial networks. In Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition , 2019.
- Kim, H., Kim, M., Seo, D., Kim, J., Park, H., Park, S., Jo, H., Kim, K., Yang, Y., Kim, Y., et al. Nsml: Meet the mlaas platform with a real-world case study. arXiv preprint arXiv:1810.09957 , 2018.
- Kingma, D. P. and Welling, M. Auto-encoding variational bayes. arXiv preprint arXiv:1312.6114 , 2013.
- Kynk¨ a¨ anniemi, T., Karras, T., Laine, S., Lehtinen, J., and Aila, T. Improved precision and recall metric for assessing generative models. In Advances in Neural Information Processing Systems , pp. 3929-3938, 2019.
- LeCun, Y., Bottou, L., Bengio, Y., and Haffner, P. Gradient-based learning applied to document recognition. Proceedings of the IEEE , 1998.
- Liu, Z., Luo, P., Wang, X., and Tang, X. Deep learning face attributes in the wild. In Proceedings of the IEEE International Conference on Computer Vision , 2015.
- Radford, A., Metz, L., and Chintala, S. Unsupervised representation learning with deep convolutional generative adversarial networks. International Conference on Learning Representations , 2016.
- Sajjadi, M. S., Bachem, O., Lucic, M., Bousquet, O., and Gelly, S. Assessing generative models via precision and recall. In Advances in Neural Information Processing Systems , pp. 52285237, 2018.
- Salimans, T., Goodfellow, I., Zaremba, W., Cheung, V., Radford, A., and Chen, X. Improved techniques for training gans. In Advances in neural information processing systems , pp. 22342242, 2016.
- Simon, L., Webster, R., and Rabin, J. Revisiting precision recall definition for generative modeling. In International Conference on Machine Learning , pp. 5799-5808, 2019.
- Theis, L., van den Oord, A., and Bethge, M. A note on the evaluation of generative models. In International Conference on Learning Representations , pp. 1-10, 2016.
- Torralba, A. and Efros, A. A. Unbiased look at dataset bias. In Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition , 2011.
- Ulyanov, D., Vedaldi, A., and Lempitsky, V. Deep image prior. In Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition , pp. 9446-9454, 2018.
- Vaserstein, L. N. Markov processes over denumerable products of spaces, describing large systems of automata. Problemy Peredachi Informatsii , 1969.
- Yu, F., Zhang, Y., Song, S., Seff, A., and Xiao, J. Lsun: Construction of a large-scale image dataset using deep learning with humans in the loop. arXiv preprint arXiv:1506.03365 , 2015.
- Zhang, R., Isola, P., Efros, A. A., Shechtman, E., and Wang, O. The unreasonable effectiveness of deep features as a perceptual metric. In Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition , pp. 586-595, 2018.

## GLOSSAR

- **Fidelity** — the degree to which generated samples resemble real samples.
- **Diversity** — the degree to which generated samples cover the full variability of the real samples.
- **Precision (Sajjadi et al.)** — the portion of the fake distribution Q(Y) that can be generated by the real distribution P(X); a fidelity measure.
- **Recall (Sajjadi et al.)** — the portion of P(X) that can be generated by Q(Y); a diversity measure.
- **Improved precision and recall (P&R)** — the Kynkäänniemi et al. (2019) metrics that estimate real and fake "manifolds" as unions of k-nearest-neighbour spheres and measure the fraction of samples of one set falling inside the other's manifold.
- **Manifold (in P&R/D&C)** — the union of spheres around each embedded sample, with radius equal to the distance to the sample's k-th nearest neighbour; analogous to a density function that does not sum to 1.
- **Density** — the proposed fidelity metric; counts how many real-sample neighbourhood spheres contain each fake sample, forming a superposition manifold; not upper-bounded by 1.
- **Coverage** — the proposed diversity metric; the fraction of real samples whose neighbourhoods (built on real samples) contain at least one fake sample; bounded between 0 and 1.
- **NND_k(X_i)** — the distance from sample X_i to its k-th nearest neighbour among the other real samples; sets the sphere radius in manifold estimation.
- **Mode dropping** — the failure mode in which a generative model covers only some modes of the real distribution, reducing diversity.
- **Truncation (latent truncation threshold ψ)** — a technique that thresholds the latent noise Z to manipulate the learned distribution; larger ψ lowers fidelity and raises diversity.
- **T4096** — the fc2 features (4096 dimensions) of a VGG16 pre-trained on ImageNet, used as an embedding.
- **R4096** — the fc2 features of a randomly initialised VGG16, used as a bias-free embedding.
- **R64** — the fc2′ features of a randomly initialised VGG16 with the 4096 dimensions replaced by 64 dimensions; recommended for data far from ImageNet statistics.
