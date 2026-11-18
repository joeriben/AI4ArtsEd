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
checks: passed
review: passed
analyzed_at: "2026-11-15T11:59:46.434157+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: gedruckt
---

# Improved Precision and Recall Metric for Assessing Generative Models

## PROFIL

The paper "Improved Precision and Recall Metric for Assessing Generative Models" was written by Tuomas Kynkäänniemi, Jaakko Lehtinen, Tero Karras, Samuli Laine, and Timo Aila, and is addressed to researchers working on generative image models and their evaluation. Its subject is an evaluation metric that measures precision (sample quality/fidelity) and recall (coverage of the training data's variation) separately, against the authors' claim that single-number metrics such as FID, IS, and KID conflate quality and variety and make diagnosis of model performance difficult. The work builds on Sajjadi et al.'s earlier precision-and-recall metric, which it criticizes for relying on relative probability densities and failing when samples are densely packed (e.g., under truncation or mode collapse); it instead forms explicit, non-parametric manifold estimates by embedding equal numbers of real and generated samples (50,000, via VGG-16 features) and surrounding each feature vector with a hypersphere reaching its k-th nearest neighbor (k = 3). The paper validates the metric on StyleGAN with FFHQ and BigGAN with ImageNet, uses it to analyze StyleGAN training configurations along a Pareto frontier of precision/recall tradeoffs, and extends the binary membership function to a continuous realism score for individual samples. Appendices provide pseudocode, a synthetic mode-dropping/invention experiment replicating Sajjadi et al.'s setup, an analysis of truncation strategies in StyleGAN's latent spaces, and additional sample examples; the authors also engage with Brock et al.'s feature-space choice and Zhang et al.'s perceptual metric, and reference Karras et al.'s StyleGAN work. The metric is usable in machine-learning and computer-vision education concerned with generative model assessment, and the authors suggest precision quantification may extend to image-to-image translation; source code is made available.

## WISSEN

### Purpose and Background (pp. 1–3)

This paper by Tuomas Kynkäänniemi, Jaakko Lehtinen, Tero Karras, Samuli Laine, and Timo Aila presents an improved evaluation metric for generative models that separately measures two aspects of generated images: **precision** (sample quality/fidelity) and **recall** (coverage of the training data's variation). The authors argue that widely used single-number metrics such as Fréchet Inception Distance (FID), Inception Score (IS), and Kernel Inception Distance (KID) conflate quality and variety into one value, making diagnosis of model performance difficult. They note the paradox that although state-of-the-art methods claim to optimize FID, published results are almost always produced with a truncated model that sacrifices variation (and often FID) for higher quality.

The work builds on Sajjadi et al.'s earlier precision-and-recall metric, which the authors criticize for relying on relative probability densities. That approach cannot correctly handle situations where many samples are packed together (e.g., from mode collapse or truncation), and it cannot reliably estimate the classic extreme values of precision and recall. The authors argue the classic definitions suffice: precision is the fraction of generated images that are realistic; recall is the fraction of the training data manifold covered by the generator. Their primary contribution is a metric forming explicit, non-parametric representations of the real and generated manifolds. Source code is available at https://github.com/kynkaat/improved-precision-and-recall-metric.

### The Improved Precision and Recall Metric (pp. 3–4)

The method draws equal numbers of samples from the real distribution P_r and generated distribution P_g, embeds them into a high-dimensional feature space using a pre-trained classifier (VGG-16, extracting activations after the second fully connected layer), and estimates each manifold as follows: for each feature vector, compute pairwise Euclidean distances and form a hypersphere whose radius equals the distance to its k-th nearest neighbor. Together these hyperspheres define a volume approximating the true manifold. A binary membership function f(φ, Φ) answers whether a sample lies within this estimated volume.

- **Precision** is quantified by querying, for each generated image, whether it falls within the estimated manifold of real images.
- **Recall** is calculated symmetrically by querying, for each real image, whether it falls within the estimated manifold of generated images.

Design choices: the metric is weakly affected by sample count (like FID); the authors use 50,000 samples, matching FID convention. The size of the neighborhood, k, is a compromise between covering the entire manifold (large values) and overestimating its volume as little as possible (small values); k = 3 was found robust and used in all experiments. Inception-v3 features yield substantially similar results to VGG-16. The authors chose the VGG-16 feature space (as used by Brock et al.) over Zhang et al.'s perceptual metric because it places less emphasis on exact spatial arrangement.

### Validation on State-of-the-Art Models (pp. 4–6)

**StyleGAN (FFHQ dataset):** Four setups illustrate the metric's behavior. Setup A (heavily truncated) shows high precision and low recall; setup B (more variation) improves recall at some cost to precision; setup C (the FID-optimized configuration) improves recall further but reduces precision due to distorted faces; setup D preserves variation but nearly all images are broken, yielding much lower precision. In contrast, Sajjadi et al.'s method rates B, C, and D as essentially perfect and incorrectly assigns A the lowest precision; FID ranks B and D as almost equally good and C as clearly best despite visible artifacts. A truncation experiment (ψ from 0 to 1) shows the expected behavior for the new metric—precision drops and recall rises as truncation is removed—whereas Sajjadi et al.'s method reports both precision and recall increasing, contrary to expectation. The authors hypothesize the failure stems from truncation packing generated images densely, creating clusters without real images.

**BigGAN (ImageNet):** The metric is applied to classes Brock et al. identified as easy or difficult. Precision is invariably high for easy classes (textural, common in the dataset, including cats and dogs, which have disproportionate training data) and lower for difficult ones (precise global structure, unaligned faces, underrepresented). Recall is very low for classes like "Lemon" or "Broccoli" despite good FID—because FID corresponds to a Wasserstein-2 distance, low intrinsic variation yields low FID even when much variation is missed. Difficult classes show higher recall, indicating BigGAN successfully modeled their intra-class variation.

### Using the Metric to Analyze and Improve StyleGAN (pp. 6–7)

Because FID can vary up to ±14% between consecutive training iterations, and snapshots represent different precision/recall tradeoffs, the authors identify the **Pareto frontier**—the minimal subset of snapshots guaranteed to contain the optimal choice for any given tradeoff. Findings on StyleGAN variants trained with FFHQ at 1024×1024:

- Baseline (A) includes a minibatch standard deviation layer; removing it (B) shifts the tradeoff toward precision over recall, confirming the layer increases variation.
- Reducing the R_1 regularization parameter γ by 100× (C) shifts the balance further toward precision.
- Disabling progressive growing (D) reduces both quality and variation, confirming Karras et al.'s claims.
- Randomly translating discriminator inputs by −16…16 pixels (E) improves precision.
- Disabling instance normalization in the AdaIN operation (F) unexpectedly improves recall; configuration F yields a new state-of-the-art FID for the dataset.

FID is shown to favor high-recall configurations (A, F) over high-precision ones (B, C); random translation (E) is exceptional in improving precision while slightly improving FID.

### Estimating the Quality of Individual Samples (pp. 7–9)

The binary membership function is extended to a continuous **realism score** R: the score increases the closer a generated image's feature vector is to the real manifold, with f(φ_g, Φ_r) = 1 iff R ≥ 1. Because k-NN hyperspheres become large in sparsely sampled regions, single images landing in fringe hyperspheres could get wildly inaccurate scores; the authors therefore discard the half of hyperspheres with the largest radii (keeping only those smaller than the median). This yields an overconservative but more consistent estimate, used only for R, not f.

Examples from BigGAN's eight classes show high-realism images contain a clear class object while low-realism images are distorted or unrecognizable. Applied to StyleGAN latent-space interpolations (linear interpolation in W), realism scores correlate well with perceived quality. Sampling 1M latent vectors with R ≥ 1 without truncation gave 500k interpolation paths; only 2.4% of paths had more than 25% of intermediate images with R < 0.9, suggesting the realistic subset of W is highly convex.

### Conclusion (p. 9)

The authors argue separate precision/recall assessment reveals insights about generative models and can improve them; precision quantification may also be useful for image-to-image translation. The training-configuration effects identified raise the question of whether truncation is necessary if similar tradeoffs can be achieved by modifying training. Since density models can fail to assess whether an example belongs to the training distribution, explicitly modeling the real manifold may offer an alternative.

### Implementation, Synthetic Validation, and Truncation Analysis (pp. 10–13)

**Pseudocode (Appendix A):** The main function PRECISION-RECALL embeds real and generated images via feature network F, then calls MANIFOLD-ESTIMATE twice (Φ_r, Φ_g for precision; Φ_g, Φ_r for recall). MANIFOLD-ESTIMATE computes pairwise distances within Φ_a, sets each radius to the (k+1)-th smallest distance (excluding the point itself), and returns the fraction of Φ_b points within any hypersphere. On an NVIDIA Tesla V100, a 50k-image estimate takes ~8 minutes (vs. ~4 minutes for FID and ~14 minutes to generate 50k 1024×1024 StyleGAN images).

**Synthetic data (Appendix B):** Replicating Sajjadi et al.'s mode-dropping/invention experiment with a 10-class 2D Gaussian mixture (real data covering five modes), the metric yields correct precision and recall in all cases; Sajjadi et al.'s method performs similarly except for k-means clustering artifacts.

**Truncation methods (Appendix C):** Four primary strategies for StyleGAN's intermediate latent space W: A) rejecting random latents too far from their mean; B) rejecting low-density latents under a multivariate Gaussian approximation; C) clamping low-density latents to the boundary hyperellipsoid; D) linear interpolation of all latents toward the mean. Three secondary strategies: E) interpolating in Z instead of W; F) truncating the Z distribution along coordinate axes; G) replacing a random subset of latents with the distribution mean. Applying truncation to only some layers had no meaningful impact. Findings: strategies in Z (E, F) yield clearly inferior tradeoffs; density-based rejection (B) beats distance-based rejection (A); clamping (C) beats rejection; interpolation (D) is competitive because it affects all latents equally, inflating precision; random replacement (G) increases average quality without reducing support (and even slightly increases recall—an artifact of the k-NN approximation becoming conservative at lower sample density). When recall is replaced by FID, interpolation and random replacement become less desirable, and clamping (C) emerges as the clear winner because it minimizes the Wasserstein-2 distance between truncated and original distributions in W; visual inspection confirms clamping yields the best tradeoff.

**Additional examples (Appendix D):** BigGAN high-realism samples contain clear class objects; low-realism samples lack or distort them. StyleGAN high-quality samples lose some background/accessory variation (hats, microphones, occlusions), which the generator could not realistically recreate; low-quality interpolations are significantly distorted with incoherent backgrounds.

### Figures (p. 2–16)

*Fig. 1 (p. 2):* Definition of precision and recall for distributions [25]. (a) Denote the distribution of real images with P r (blue) and the distribution of generated images with P g (red). (b) Precision is the probability that a random image from P g falls within the support of P r . (c) Recall is the probability that a random image from P r falls within the support of P g . — It is a three-panel scientific diagram rather than a photograph. Panel (a), labeled “Example distributions,” shows overlapping red and blue contour-line distributions marked “P_g” and “P_r.” Panel (b), labeled “Precision,” shows a solid blue shaded region with many filled red dots concentrated in the overlap and additional open red circles near a dashed outline. Panel (c), labeled “Recall,” shows a solid red shaded region with many filled blue dots in the overlap and open blue circles near a dashed outline. _(Lettering in the image, read by the image model, not confirmed: “P_g”, “P_r.”)_

*Fig. 2 (p. 3):* (a) An example manifold in a feature space. (b) Estimate of the manifold obtained by sampling a set of points and surrounding each with a hypersphere that reaches its k th nearest neighbor. — The picture is a two-panel scientific diagram on a white background. Panel (a) shows a single smooth, light-blue, irregular amoeba-like shape, with the legible caption “(a) True manifold”. Panel (b) shows many overlapping semi-transparent blue circles of different sizes packed into a similar elongated wavy shape, with the legible caption “(b) Approx. manifold”.

*Fig. 3 (p. 4):* (a) Our metric behaves similarly to FID in terms of varying sample count. (b) Precision (blue) and recall (orange) for several neighborhood sizes k . Larger k increases both numbers. Here a trained model ( ψ = 1 ) was expanded to a family of models by artificially limiting the variation in the results. We would expect the precision and recall to reach 1.0 and 0.0, respectively, when ψ → 0 . (c) Using Inception-v3 features instead of VGG-16 yields a substantially similar result. — The image is a scientific figure made of three side-by-side line charts labeled (a), (b), and (c). Chart (a), titled “Varying |Φ|, VGG-16,” plots “Precision,” “Recall,” and “FID” against “Number of images,” with Precision/Recall on the left axis and FID on a right-hand axis. Charts (b) and (c), titled “Varying k, VGG-16” and “Varying k, Inception-v3,” plot several curves against “Truncation ψ,” with blue curves near the top and orange curves rising from near zero. The legends show “k=2,” “k=3,” “k=5,” “k=7,” and “k=10,” and the axis labels “Precision / Recall,” “FID,” and “Truncation ψ” are legible. _(Lettering in the image, read by the image model, not confirmed: “Truncation ψ,”, “Truncation ψ”)_

*Fig. 4 (p. 5):* Comparison of our method (black dots), Sajjadi et al.'s method [25] (red triangles), and FID for 4 StyleGAN setups. We recommend zooming in to better assess the quality of images. — The picture is a composite figure: on the left is a scatter plot with a vertical axis labeled “Precision” and a horizontal axis labeled “Recall,” showing black dots and red triangles marked with the letters A, B, C, and D. On the right are four groups of six face photographs each. Beneath the photo groups are the labels “A (FID = 91.7)”, “B (FID = 16.9)”, “C (FID = 4.5)”, and “D (FID = 16.7)”.

*Fig. 5 (p. 5):* (a) Example images produced by StyleGAN [13] trained using the FFHQ dataset. It is generally agreed [18, 4, 14, 13] that truncation provides a tradeoff between perceptual quality and variation. (b) With our method, the maximally truncated setup ( ψ = 0 ) has zero recall but high precision. As truncation is gradually removed, precision drops and recall increases as expected. The final recall value approximates the fraction of training set the generator can reproduce (generally well below 100%). (c) The method of Sajjadi et al. reports both precision and recall increasing as truncation is removed, contrary to the expected behavior, and the final numerical values of both precision and recall seem excessively high. — The figure consists of three panels labeled (a), (b), and (c). Panel (a) is a grid of twelve photographic face images in three rows and four columns, with the labels "ψ = 0.0", "ψ = 0.3", "ψ = 0.7", and "ψ = 1.0" under the columns. Panels (b) and (c) are line charts whose x-axis is labeled "Truncation ψ" and whose y-axis runs from 0.0 to 1.0, each plotting a blue "Precision" line and an orange "Recall" line; panel (b) is captioned "Our method" and panel (c) is captioned "Sajjadi et al. [25]". _(Lettering in the image, read by the image model, not confirmed: "Truncation ψ")_

*Image 6 (p. 6):* — The picture combines a line chart on the left with eight photographs on the right. The chart plots "Precision" on the vertical axis against "Recall" on the horizontal axis, with colored lines identified in a legend as "Great Pyrenees", "Broccoli", "Egyptian cat", "Lemon", "Baseball player", "Bubble", "Trumpet", "Park bench", and "Entire dataset". The photographs are arranged in two rows marked (a) and (b), each with a caption giving the object name and an FID value, such as "Great Pyrenees (FID = 30.0)", "Broccoli (FID = 40.2)", "Egyptian cat (FID = 39.2)", "Lemon (FID = 46.4)", "Bubble (FID = 63.5)", "Baseball player (FID = 49.2)", "Trumpet (FID = 100.4)", and "Park bench (FID = 80.3)".

*Fig. 7 (p. 7):* (a) Precision and recall for different snapshots of StyleGAN taken during the training, along with their corresponding Pareto frontier. We use the standard training configuration by Karras et al. [13] with FFHQ and ψ = 1 . (b) Different training configurations lead to vastly different tradeoffs between precision and recall. (c) Best FID obtained for each configuration (lower is better). — The image is a technical figure containing three side-by-side panels labeled (a), (b), and (c). Panels (a) and (b) are scatter plots with “Recall” on the horizontal axis and “Precision” on the vertical axis; panel (a) shows blue “Training snapshots” points, one black “Lowest FID” point, and a “Pareto frontier” line, while panel (b) shows colored point clusters and lines for the legend entries “A) StyleGAN”, “B) No mb. std.”, “C) B + low γ”, “D) No growing”, “E) Rand. trans.”, and “F) No inst. norm.”. Panel (c) is a two-column table headed “Configuration” and “FID” listing “A) StyleGAN” 4.43, “B) No mb. std.” 8.58, “C) B + low γ” 10.34, “D) No growing” 6.14, “E) Rand. trans.” 4.27, and “F) No inst. norm.” 4.16, with 4.16 in bold.

*Fig. 8 (p. 8):* Quality of individual samples of BigGAN from eight classes. Top: Images with high realism. Bottom: Images with low realism. We show two images with the highest and lowest realism score selected from 1000 non-truncated images. — It is a grid of 32 small color photographs arranged in four rows and eight columns. Across the top, the columns are labeled "Red wine", "Alp", "Golden Retriever", "Ladybug", "Lighthouse", "Tabby cat", "Monarch butterfly", and "Cocker Spaniel"; the left side marks the upper two rows "Best-2" and the lower two rows "Worst-2". The "Best-2" rows show sharp, recognizable photographs of the labeled subject in each column, while the "Worst-2" rows show blurry, distorted, or hard-to-recognize photographs under the same labels.

*Fig. 9 (p. 9):* Realism score for four interpolation paths as function of linear interpolation parameter t and corresponding images from paths A-D. We did not use truncation when generating the images. — The image is a composite figure: on the left, a line chart plots “Realism score R” on the vertical axis (0.0 to 2.0) against “Interpolation parameter t” on the horizontal axis (0.0 to 1.0), with four colored curves labeled A, B, C, and D in a legend. On the right are four horizontal rows of face photographs labeled A, B, C, and D, each row showing seven images in sequence. Row A shows a sequence of similar young women’s faces, row B shows a helmeted person followed by different women, row C shows a blonde woman followed by gray-haired and costumed figures, and row D shows a capped person followed by colorful faces. Gridlines and numeric tick labels are visible on the chart.

*Fig. 10 (p. 11):* (a) Real data covers five modes (1-5) and the generated data is expanded, one mode at a time, to cover the real modes (1-5) and five extraneous modes (6-10). Both metrics were evaluated using 20k real and generated samples. (b) Results from our metric with k = 3 . (c) Results from the method of Sajjadi et al. [25]. — The picture shows a three-panel figure labeled (a), (b), and (c). Panel (a) is a 2D scatter plot of ten colored point clusters, each marked with a number from 1 to 10. Panels (b) and (c) are line charts with the x-axis labeled "Covered modes" (values 1 to 10) and a y-axis from 0.0 to 1.0; panel (b) plots two lines with the legend "Precision" and "Recall", and panel (c) plots two lines with the legend "F_{1,k}" and "F_k". In both charts, the orange line rises from 0.2 at covered mode 1 to 1.0 at covered mode 5 and then stays flat, while the blue line reaches 1.0 at covered mode 5 and then decreases to about 0.5 at covered mode 10. _(Lettering in the image, read by the image model, not confirmed: "F_{1,k}", "F_k")_

*Fig. 11 (p. 12):* (a) Our primary truncation strategies avoid sampling the extremal regions of StyleGAN's intermediate latent space. (b) Precision and recall for different amounts of truncation with FFHQ. (c) Using FID instead of recall to measure distribution quality. Note that the x -axis is flipped. — This is a scientific figure made up of three panels labeled (a), (b), and (c). Panel (a) shows four schematic diagrams labeled “A) Reject by distance”, “B) Reject by density”, “C) Clamp by density”, and “D) Interpolate to mean”, each with an ellipse containing black dots; A and B also show red dots outside the ellipse, while C and D show blue arrows. Panels (b) and (c) are line charts with “Precision” on the vertical axis; panel (b) plots Precision against “Recall”, and panel (c) plots Precision against “FID” with the x-axis values running from 80 down to 0, and both charts have a legend reading “A) Reject dist.”, “B) Reject dens.”, “C) Clamp dens.”, “D) Interp. mean”, “E) Interp. Z”, “F) Trunc. Z”, and “G) Replace”.

*Image 12 (p. 14):* — This image shows a grid of 48 color photographs arranged in six rows and eight columns, with category labels written vertically on the left side of each row. The labels read "Border Collie", "Lakeside", "Norwich Terrier", "Persian cat", "Panda", and "Siamese cat" from top to bottom. Each row displays eight photographs corresponding to its label: Border Collie dogs, lakeside water scenery, Norwich Terrier dogs, Persian cats, pandas, and Siamese cats.

*Image 13 (p. 14):* — The picture is a grid of color photographs arranged in six rows and eight columns. Along the left side of each row, vertical text labels read "Border Collie", "Lakeside", "Norwich Terrier", "Persian cat", "Panda", and "Siamese cat". Each row contains eight photographs depicting subjects corresponding to its label, including dogs, lakeside scenes, cats, and pandas.

*Image 14 (p. 15):* — The image is a collage of 48 portrait photographs arranged in a grid of 6 rows and 8 columns. Each cell contains a headshot of a different person showing their face and shoulders against various backgrounds, including outdoor scenes and plain indoor settings. The individuals appear to be adults of varying ages, with most facing the camera and smiling. No text is visible in the image.

*Image 15 (p. 15):* — The picture is a collage made of many small portrait photographs arranged in a rectangular grid. It shows head-and-shoulders portraits of many different people of varying ages and backgrounds, including babies, children, adults, and older adults, some smiling and some with neutral expressions, with a few wearing hats, headscarves, or costume pieces. Small lettering appears on some caps and hats, but it is not legible.

*Image 16 (p. 16):* — The picture is a grid of portrait photographs arranged in seven rows and ten columns. Each row displays a sequence of ten headshots of the same individual, with visible variations in facial expression, hairstyle, or appearance progressing from left to right. The subjects are men and women of various ages and ethnicities, some wearing eyeglasses, photographed against diverse indoor and outdoor backgrounds. No text is visible in the image.

*Image 17 (p. 16):* — The image is a grid of color portrait photographs arranged in seven rows and ten columns. Each row contains multiple photographs of the same individual's face, showing variations in facial expression, pose, and headwear such as beanies, caps, goggles, and glasses. The grid includes photographs of men, women, and a child. No text is visible in the picture.

<!-- quelle: Improved Precision and Recall Metric for Assessing Generative Models (p. 1–16) -->

## LITERATUR

<!-- quelle: References (p. 9–10) -->

- S. Arora and Y. Zhang. Do GANs actually learn the distribution? An empirical study. CoRR , abs/1706.08224, 2017.
- M. Bi´ nkowski, D. J. Sutherland, M. Arbel, and A. Gretton. Demystifying MMD GANs. CoRR , abs/1801.01401, 2018.
- J. Branke, J. Branke, K. Deb, K. Miettinen, and R. Slowi´ nski. Multiobjective optimization: Interactive and evolutionary approaches , volume 5252. Springer Science & Business Media, 2008.
- A. Brock, J. Donahue, and K. Simonyan. Large scale GAN training for high fidelity natural image synthesis. In Proc. ICLR , 2019.
- J. Deng, W. Dong, R. Socher, L.-J. Li, K. Li, and L. Fei-Fei. ImageNet: A Large-Scale Hierarchical Image Database. In Proc. CVPR , 2009.
- L. Dinh, J. Sohl-Dickstein, and S. Bengio. Density estimation using Real NVP. CoRR , abs/1605.08803, 2016.
- D. Eberly. Distance from a point to an ellipse, an ellipsoid, or a hyperellipsoid. Geometric Tools, LLC , 2011.
- I. Goodfellow, J. Pouget-Abadie, M. Mirza, B. Xu, D. Warde-Farley, S. Ozair, A. Courville, and Y. Bengio. Generative Adversarial Networks. In NIPS , 2014.
- A. Grover, M. Dhar, and S. Ermon. Flow-GAN: Combining maximum likelihood and adversarial learning in generative models. In Proc. AAAI , 2018.
- M. Heusel, H. Ramsauer, T. Unterthiner, B. Nessler, and S. Hochreiter. GANs trained by a two time-scale update rule converge to a local Nash equilibrium. In NIPS , pages 6626-6637, 2017.
- X. Huang and S. J. Belongie. Arbitrary style transfer in real-time with adaptive instance normalization. CoRR , abs/1703.06868, 2017.
- T. Karras, T. Aila, S. Laine, and J. Lehtinen. Progressive growing of GANs for improved quality, stability, and variation. CoRR , abs/1710.10196, 2017.
- T. Karras, S. Laine, and T. Aila. A style-based generator architecture for generative adversarial networks. In Proc. CVPR , 2019.
- D. P. Kingma and P. Dhariwal. Glow: Generative flow with invertible 1x1 convolutions. CoRR , abs/1807.03039, 2018.
- D. P. Kingma, D. J. Rezende, S. Mohamed, and M. Welling. Semi-supervised learning with deep generative models. In Proc. NIPS , 2014.
- Z. Lin, A. Khetan, G. Fanti, and S. Oh. PacGAN: The power of two samples in generative adversarial networks. CoRR , abs/1712.04086, 2017.
- D. Lopez-Paz and M. Oquab. Revisiting classifier two-sample tests. In Proc. ICLR , 2017.
- M. Marchesi. Megapixel size image creation using generative adversarial networks. CoRR , abs/1706.00082, 2017.
- L. Mescheder, A. Geiger, and S. Nowozin. Which training methods for GANs do actually converge? CoRR , abs/1801.04406, 2018.
- L. Metz, B. Poole, D. Pfau, and J. Sohl-Dickstein. Unrolled generative adversarial networks. CoRR , abs/1611.02163, 2016.
- T. Miyato, T. Kataoka, M. Koyama, and Y. Yoshida. Spectral normalization for generative adversarial networks. CoRR , abs/1802.05957, 2018.
- T. Miyato and M. Koyama. cGANs with projection discriminator. CoRR , abs/1802.05637, 2018.
- E. Nalisnick, A. Matsukawa, Y. W. Teh, D. Gorur, and B. Lakshminarayanan. Do deep generative models know what they don't know? In Proc. ICLR , 2019.
- A. Odena, C. Olah, and J. Shlens. Conditional image synthesis with auxiliary classifier GANs. In ICML , 2017.
- M. S. M. Sajjadi, O. Bachem, M. Lucic, O. Bousquet, and S. Gelly. Assessing generative models via precision and recall. CoRR , abs/1806.00035, 2018.
- T. Salimans, I. J. Goodfellow, W. Zaremba, V. Cheung, A. Radford, and X. Chen. Improved techniques for training GANs. In NIPS , 2016.
- L. Simon, R. Webster, and J. Rabin. Revisiting precision and recall definition for generative model evaluation. CoRR , abs/1905.05441, 2019.
- K. Simonyan and A. Zisserman. Very deep convolutional networks for large-scale image recognition. CoRR , abs/1409.1556, 2014.
- I. Tolstikhin, O. Bousquet, S. Gelly, and B. Schoelkopf. Wasserstein auto-encoders. In Proc. ICLR , 2018.
- A. van den Oord, N. Kalchbrenner, and K. Kavukcuoglu. Pixel recurrent neural networks. In ICML , pages 1747-1756, 2016.
- A. van den Oord, N. Kalchbrenner, O. Vinyals, L. Espeholt, A. Graves, and K. Kavukcuoglu. Conditional image generation with PixelCNN decoders. CoRR , abs/1606.05328, 2016.
- H. Zhang, I. Goodfellow, D. Metaxas, and A. Odena. Self-attention generative adversarial networks. CoRR , abs/1805.08318, 2018.
- R. Zhang, P. Isola, A. A. Efros, E. Shechtman, and O. Wang. The unreasonable effectiveness of deep features as a perceptual metric. In Proc. CVPR , 2018.
- J. Zhu, T. Park, P. Isola, and A. A. Efros. Unpaired image-to-image translation using cycle-consistent adversarial networks. CoRR , abs/1703.10593, 2017.

## GLOSSAR

- **Precision** — the probability that a random generated image falls within the support (estimated manifold) of the real distribution; corresponds to average sample quality.
- **Recall** — the probability that a random real image falls within the support (estimated manifold) of the generated distribution; corresponds to coverage of the training data's variation.
- **Improved precision and recall metric** — the paper's method estimating both quantities via explicit, non-parametric k-NN manifold approximations in a feature space.
- **Manifold estimate** — the volume in feature space defined by hyperspheres centered on feature vectors, each with radius equal to the distance to its k-th nearest neighbor.
- **Membership function f(φ, Φ)** — binary function determining whether sample φ lies within the estimated manifold of feature set Φ.
- **Realism score R** — a continuous extension of f measuring how close a generated image's feature vector is to the manifold of real images; f = 1 iff R ≥ 1.
- **Pareto frontier** — the minimal subset of training snapshots guaranteed to contain the optimal precision/recall tradeoff for any given preference.
- **Truncation** — post-training techniques that trade variation for sample quality by limiting sampling to a high-quality subset of the latent space.
- **k (neighborhood size)** — the number of nearest neighbors defining hypersphere radii; k = 3 chosen as a robust compromise.
- **Hypersphere pruning** — for the realism score only, discarding the half of hyperspheres with the largest radii to avoid wildly inaccurate scores in sparsely sampled regions.
