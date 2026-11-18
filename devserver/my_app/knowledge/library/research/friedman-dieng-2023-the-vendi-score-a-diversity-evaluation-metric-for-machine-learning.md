---
id: friedman-dieng-2023-the-vendi-score-a-diversity-evaluation-metric-for-machine-learning
titel: The Vendi Score. A Diversity Evaluation Metric for Machine Learning
autor: "Dan Friedman, Adji Bousso Dieng"
jahr: 2023
quelle: "Transactions on Machine Learning Research (TMLR), 07/2023"
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2210.02410"
status: published
checks: passed
review: passed
analyzed_at: "2026-11-15T11:25:29.773778+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: gedruckt
---

# The Vendi Score. A Diversity Evaluation Metric for Machine Learning

## PROFIL

Written by Dan Friedman and Adji Bousso Dieng (Princeton University) and published in Transactions on Machine Learning Research (July 2023), the article addresses researchers in machine learning who need to measure diversity in models, algorithms, and datasets. Its subject is diversity evaluation, and its claim is that existing metrics—reference-based ones such as FID and precision/recall, classifier-based ones such as the Inception Score and Number of Modes, discrete-feature and average pairwise similarity metrics—are domain-specific, inflexible, or dependent on reference datasets, classifiers, or labels. The authors propose the Vendi Score, a general, reference-free metric defined as the exponential of the Shannon entropy of the eigenvalues of a similarity matrix induced by a user-defined similarity function, interpretable as the effective number of unique elements in a sample; they connect it to Hill numbers and entropy-based diversity in ecology (Hill, Jost, Leinster), to effective rank (Roy and Vetterli), and to von Neumann entropy in quantum statistical mechanics. The paper first critiques existing metrics category by category, then defines the score, proves four properties (effective number, identical elements, partitioning, symmetry), discusses computation and relations to Determinantal Point Processes and spectral clustering, and reports experiments on synthetic mixtures, molecular generative models on the MOSES benchmark, mode collapse in GANs on Stacked MNIST, image generative models on CIFAR-10, ImageNet 64×64, and LSUN, text decoding algorithms on MS COCO captioning, and dataset diagnosis on CIFAR-100, GoodScents, MultiNLI, Amazon reviews, Fashion MNIST, and CelebA. It closes with three limitations—internal diversity only, dependence on the similarity function, computational cost—and a prospect of diversity-informed data augmentation. It is usable in any discipline or situation of machine-learning practice where a similarity function can be defined, including generative-model evaluation, decoding-algorithm comparison, and dataset auditing. Code is available at the repository given in the paper.

## WISSEN

### Purpose and Thesis (p. 1–2)

This paper, published in *Transactions on Machine Learning Research* (July 2023) by Dan Friedman and Adji Bousso Dieng (Princeton University), addresses the problem of measuring diversity in machine learning (ML). The authors argue that existing diversity metrics are often domain-specific, inflexible, and dependent on reference datasets, pretrained classifiers, or discrete features. They propose the **Vendi Score (VS)**, a general, reference-free metric that connects ideas from ecology and quantum statistical mechanics to ML. The Vendi Score is defined as the exponential of the Shannon entropy of the eigenvalues of a similarity matrix induced by a user-defined similarity function applied to the sample being evaluated. Because it takes a similarity function as input, the metric lets users specify any desired form of diversity, and it requires no reference dataset, distribution over samples, or labels—making it applicable to any generative model, decoding algorithm, or dataset in any domain where similarity can be defined. Code is available at https://github.com/vertaix/Vendi-Score.

### Critique of Existing Diversity Metrics (p. 2–5)

The authors organize existing metrics into categories and describe their limitations:

- **Reference-based metrics** define diversity as coverage of a reference distribution. Examples include Fréchet Inception Distance (FID; Heusel et al., 2017), which measures the Wasserstein-2 distance between Gaussians fit to embeddings of a reference sample and the evaluated sample, and the precision/recall paradigm (Sajjadi et al., 2018), where recall measures diversity as coverage. Variations include Kynkäänniemi et al. (2019), Simon et al. (2019), and Naeem et al. (2020). The Vendi Score, by contrast, measures intrinsic diversity of a set and should be used alongside a quality metric.
- **Classifier-based metrics** require labeled datasets: the Inception Score (IS; Salimans et al., 2016) uses the entropy of the marginal distribution of predicted class labels; Number of Modes (NOM; Srivastava et al., 2017) counts unique labels predicted for GAN samples.
- **Discrete-feature metrics** such as n-gram diversity in NLP (Li et al., 2016) require explicit discrete representations.
- **Average pairwise similarity metrics** include pairwise-BLEU (Shen et al., 2019), d-lex-sim (Fomicheva et al., 2020), and IntDiv in molecular generation (Benhenda, 2017, using Jaccard/Tanimoto fingerprint similarity). The authors show these become less sensitive as diversity increases and do not account for correlations between features. The similarity-sensitive metric of Leinster and Cobbold (2012), introduced to ML by Posada et al. (2020), also fails to account for feature correlations.
- **Other metrics**: the Birthday Paradox Test (Arora and Zhang, 2018) requires manual inspection; GILBO (Alemi and Fischer, 2018) applies only to latent variable models; Kviman et al. (2022) use Jensen-Shannon divergence only for sets of distributions; Mitchell et al. (2020) define diversity via socially relevant attributes (the authors use "diversity" in the sense of Mitchell et al.'s "heterogeneity"—variety in arbitrary user-specified attributes); Xie et al. (2022) require a similarity threshold; quality diversity (QD) algorithms (Pugh et al., 2015) require choosing a bin size.

### Definition of the Vendi Score (p. 5–6)

Drawing on ecology, where diversity is defined as the exponential of the entropy of the species distribution (Hill, 1973; Jost, 2006; Leinster, 2021), the authors define: given samples x₁,…,xₙ, a positive semidefinite similarity function k with k(x,x)=1, and the kernel matrix K with entries Kᵢⱼ = k(xᵢ,xⱼ), the Vendi Score is the exponential of the Shannon entropy of the eigenvalues λ₁,…,λₙ of K/n (with the convention 0·log 0 = 0). The eigenvalues of K/n are nonnegative and sum to one, so the entropy is well-defined. The score can also be seen as the **effective rank** of K (Roy and Vetterli, 2007), used in ML by Torregrossa et al. (2020) and Arora et al. (2019). Lemma 3.1 shows the score equals the exponential of the **von Neumann entropy** of K/n—hence the name "Vendi," for "von Neumann diversity"—with K/n playing the role of a density matrix in quantum statistical mechanics (Bengtsson and Życzkowski, 2017; Bach, 2022). A probability-weighted generalization is given in Definition 7.1 (p. 21).

### Properties of the Vendi Score (p. 6–8)

Theorem 3.1 states four properties:

1. **Effective number**: if all pairwise similarities are 0, VS is maximized at n; if all are 1, VS is minimized at 1. A score of m means the sample is as diverse as m completely dissimilar elements.
2. **Identical elements**: combining two identical elements (merging their probabilities) leaves the score unchanged.
3. **Partitioning**: if samples are partitioned into groups whose cross-group similarities are 0, the score of the union is the geometric mean of the groups' scores weighted by relative sizes, analogous to the partitioning property of Shannon entropy.
4. **Symmetry**: the score is invariant to permutation of the samples.

The score also accounts for correlations between features: combining distinct similarity functions (e.g., ½k + ½k′) can yield a score greater than the average of the individual scores when the functions capture distinct dimensions of variation.

### Computation and Connections (p. 8)

Computing VS requires eigenvalues of an n×n matrix, O(n³). When d-dimensional embeddings (d ≪ n) are available, K = X⊤X and the score can be computed exactly in O(d²n + d³) = O(d²n), the same complexity as FID. Without embeddings, Nyström column-sampling (Williams and Seeger, 2000) can approximate it. The empirical estimator of the kernel entropy has convergence rate proportional to 1/√n (Bach, 2022). The authors also relate VS to Determinantal Point Processes (Kulesza et al., 2012)—noting the DPP likelihood is zero for samples with duplicates and less interpretable—and to spectral clustering (Von Luxburg, 2007), noting VS is more general than counting connected components because it captures within-component diversity.

### Experiments (p. 9–15)

**Synthetic data (p. 9–10)**: On mixtures of univariate normals with an RBF kernel, VS behaves as the effective number of modes, whereas IntDiv is insensitive to within-mode variance and shows diminishing returns for additional modes. Appendix experiments on MNIST and MultiNLI confirm VS correlates more strongly with the true number of classes than IntDiv (p. 24–25).

**Molecular generative models (p. 10–11)**: On the MOSES benchmark (Polykovskiy et al., 2020), using Morgan fingerprint similarity (radius 2, RDKit) on the first 2,500 valid molecules per model, IntDiv ranks the HMM among the most diverse models while VS ranks it least diverse (VS 250.9 vs. IntDiv 0.871; original dataset: IntDiv 0.855, VS 403.9). The HMM produces clusters of exact or near-duplicates that average similarity misses.

**Mode collapse in GANs (p. 11)**: On Stacked MNIST (1000 modes), using the probability product kernel (Jebara et al., 2004) with an MNIST classifier, both PresGAN (Dieng et al., 2019) and Self-conditioned GAN (Liu et al., 2020) capture all 1000 modes (NOM = 1000), but VS reveals finer distinctions: Self-cond. GAN 746.7, PresGAN 866.6, original dataset 943.7. A "Mode Diversity" measure (exponential entropy of the predicted mode distribution: 921.0, 948.7, 950.8) shows the gap is not solely due to mode-imbalance.

**Image generative models (p. 11–13)**: Evaluating VDVAE (Child, 2020), DenseFlow (Grčić et al., 2021), IDDPM (Nichol and Dhariwal, 2021), ADM (Dhariwal and Nichol, 2021), StyleGAN2 (Karras et al., 2019, 2020), and RQ-VT (Lee et al., 2022) on CIFAR-10, ImageNet 64×64, and LSUN Cat/Bedroom 256×256, using cosine similarity between Inception embeddings: VS generally agrees with IS, FID, Precision, and Recall on low-resolution datasets (diffusion models best). On LSUN, ADM has the best quality scores but lower VS; e.g., on LSUN Cat, ADM has precision 0.63 and recall 0.52 but VS 13.09 vs. StyleGAN2's 13.55 and the original's 15.12—suggesting the model generates near-duplicates. No model matches the diversity of its training dataset. Dataset diversity ranks: ImageNet 64×64 (43.93) > CIFAR-10 (19.50) > LSUN Cat (15.12) > LSUN Bedroom (8.99).

**Text decoding algorithms (p. 13–14)**: On MS COCO image captioning (Lin et al., 2014) with a GPT-2-based model, comparing human captions, beam search, and diverse beam search (Vijayakumar et al., 2018) with diversity penalties γ = 0.2–0.8, using an n-gram overlap kernel (average of k₁,…,k₄): all metrics rank human captions highest (VS 4.88, i.e., five human captions are nearly completely dissimilar), beam search lowest (VS 2.44, effectively only three distinct responses per five), with DBS increasing with γ. Appendix analysis (p. 26–28) shows VS correlates highly with n-gram diversity but diverges when n-gram diversity conflates within-sentence repetition or is inflated by one long sentence.

**Dataset diagnosis (p. 14–15)**: On CIFAR-100 categories, pixel-based diversity is highest for categories like "aquarium fish" and lowest for "cockroach"; Inception-based diversity may be lower for classes like "castle" and higher for "clock" and "keyboard." Appendix examples (p. 26–32) cover GoodScents perfume molecules (molecular and odor-descriptor diversity correlate: "green"/"woody" descriptors mark diverse molecules, "waxy"/"fatty" mark similar ones), MultiNLI genres and Amazon review star ratings (using n-gram and SimCSE similarity; 5-star reviews have highest n-gram but lowest SimCSE diversity, 3-star reviews highest SimCSE diversity), Fashion MNIST, and CelebA (where nearly all similarity functions show the dataset is more diverse for men than for women).

### Limitations (p. 15)

Three caveats: (1) VS is reference-free and measures internal diversity only, so random noise can score highly—it should be used alongside a quality metric (as with IntDiv and n-gram diversity); (2) VS depends on the choice of similarity function—too sensitive a function makes everything look diverse, too insensitive makes everything look uniform, and a wrong choice can introduce bias; (3) computation can be expensive when the similarity function lacks low-dimensional embeddings.

### Discussion and Conclusion (p. 15)

The Vendi Score is an interpretable, general, unsupervised metric—the effective number of unique elements in a sample—applicable wherever similarity can be defined, computable efficiently and exactly, and allowing users to specify the form of diversity they want via the similarity function. Future work will leverage VS for diversity-informed data augmentation.

### Figures (p. 2–32)

*Image 2 (p. 2):* — The image is a scientific diagram displaying nine square similarity matrices arranged in a 3×3 grid with rows labeled (a), (b), and (c). Each heatmap uses a color scale from black (0.0) to yellow (1.0), indicated by vertical color bars labeled "Similarity" on the right side of each row, to represent values between items marked by colored symbols (hearts, spades, clubs, diamonds, squares) along the axes. Each panel is titled with text such as "VS = 2.00", "VS = 3.00", "VS = 4.00", "VS = 3.78", "VS = 4.66" and "IntDiv = 0.50", "IntDiv = 0.67", "IntDiv = 0.75", and the matrices show patterns ranging from block-diagonal yellow squares to scattered red and yellow cells.

*Image 3 (p. 9):* — The image is a scientific figure containing bar charts on the left and line graphs on the right. The left side displays three rows of bar charts titled "Number of components", "Mixture proportions", and "Per-component variance", with each row containing five panels labeled S₁, S₂, S₃, S₄, and S₅. The right side shows six line graphs arranged in two columns labeled "VS" and "IntDiv", with horizontal axes marked S₁ through S₅ and vertical axes displaying numerical scales.

*Fig. 3 (p. 10):* The kernel matrices for 250 molecules sampled from the hmm, aae, and the original dataset, sorted lexicographically by smiles string representation. The samples have similar IntDiv scores, but the hmm samples score much lower on vs. The figure shows that the hmm generates a number of exact duplicates. vs is able to capture the hmm's lack of diversity while IntDiv cannot. — The image is a scientific figure showing three square heatmaps side by side, labeled “HMM”, “AAE”, and “Real”, each with the lines “VS: 55.8” / “IntDiv: 0.853”, “VS: 142.1” / “IntDiv: 0.849”, and “VS: 127.7” / “IntDiv: 0.847” respectively. A vertical colorbar at the right is labeled “Similarity” and runs from “0.0” to “1.0”. The HMM heatmap has a bright diagonal plus several bright off-diagonal square blocks, whereas the AAE and Real heatmaps are mostly dark purple with a thin bright diagonal line.

*Fig. 4 (p. 14):* The categories in cifar-100 with the lowest and highest vs, defining similarity as the cosine similarity between either Inception embeddings or pixel vectors. We show 100 examples from each category, in decreasing order of average similarity , with the image at the top left having the highest average similarity scores according to the corresponding kernel. — This is a figure made up of eight grids, each containing 100 small thumbnail photographs arranged in 10 rows and 10 columns. The top row is labeled "Inception" and the bottom row "Pixels," and the headings "Least diverse" and "Most diverse" sit above the category labels "plain," "castle," "clock," "keyboard" in the top row and "cockroach," "plain," "man," "aquarium_fish" in the bottom row. Each grid shows many small photographs of the category named above it, such as landscapes under "plain," buildings under "castle," clocks under "clock," keyboards under "keyboard," insects under "cockroach," faces under "man," and fish under "aquarium_fish."

*Fig. 5 (p. 25):* Detecting mode dropping in image and text datasets. We evaluate vs and IntDiv on datasets containing 500 examples drawn uniformly from between one and ten classes: digits in mnist and sentences genres in Multinli. Compared to IntDiv, vs increases more consistently with the number of classes. — The picture is a four-panel line-chart figure arranged in a 2×2 grid. The left column is headed “MNIST” and the right column “MultiNLI”; the upper panels plot a red line with the legend “VS,” and the lower panels plot a blue line with the legend “IntDiv.” Each panel has an x-axis labeled “Number of classes” running from 1 to 10. In the MNIST panels, VS climbs from below 10 to above 20 and then flattens, whereas IntDiv jumps from below 0.45 to near 0.60 and stays roughly flat; in the MultiNLI panels, VS rises from around 360 to above 400, and IntDiv rises from below 0.925 to about 0.940.

*Fig. 6 (p. 27):* The choice of similarity function provides a way of specifying the notion of diversity that is relevant for a given application. We project lsun Cat images along the top eigenvectors of the kernel matrix, using either Inception features or pixels to define similarity . Inception similarity provides a form of semantic similarity , with components corresponding to particular cat breeds, while the pixel kernel captures visual similarity. For each eigenvector u , we show the four images with the highest and lowest entries in u . For both kernels, every similarity score is positive, so all entries in the top eigenvector have the same sign; the images with the highest weights in this component have the highest expected similarity scores. The remaining eigenvectors partition the images along different dimensions of variation. — This is a figure made of two side-by-side grids of small cat photographs. The left grid is headed “Inception kernel” and the right grid is headed “Pixel kernel,” and each grid has two columns labeled “Least positive” and “Most positive.” Along the left edge, rows are numbered 1 through 8 beside the vertical label “Kernel principal components,” and each cell contains several small thumbnail images of cats.

*Fig. 7 (p. 28):* VS is correlated with N-gram diversity. Each point represents a group of five captions for a particular image. — This is a scatter plot chart. The horizontal axis is labeled “N-gram diversity” and the vertical axis is labeled “N-gram VS.” A legend identifies three series: red circles for “Beam search,” blue squares for “Diverse beam search,” and green triangles for “Human.” The points rise from the lower left toward the upper right, with red circles mostly at lower values, blue squares in the middle, and green triangles at higher values.

*Fig. 9 (p. 29):* The Vendi Scores of samples containing 500 molecules with different scent labels, calculating diversity using two similarity functions: Morgan molecular fingerprint similarity, and the similarity between odor descriptors. Each molecule is associated with one or more human-written tags (e.g. 'floral, fruity , green, sweet'), and the odor-descriptor similarity is the cosine similarity between binary tag indicator vectors. — It is a scatter plot with the x-axis labeled “Molecular fingerprints” and the y-axis labeled “Odor descriptors.” Blue points are labeled “waxy,” “fatty,” “fruity,” “spicy,” “floral,” “sweet,” “green,” “woody,” and “herbal.” The points span roughly from 60 to 180 on the x-axis and from 30 to 44 on the y-axis, with “waxy” and “fatty” at the lower left and “sweet,” “green,” and “woody” near the top.

*Fig. 11 (p. 29):* The Vendi Scores of samples containing 500 MultiNLI sentences with different genres (left) or Amazon reviews with different star ratings (right), defining similarity using either n-gram overlap or SimCSE (Gao et al., 2021). — The image displays two scatter plots side by side. The left plot, titled "MultiNLI genres", shows five data points labeled "Fiction", "Travel", "Telephone", "Government", and "Slate" plotted with "N-grams" on the horizontal axis and "SimCSE" on the vertical axis. The right plot, titled "Amazon reviews", shows five data points labeled "1 stars", "2 stars", "3 stars", "4 stars", and "5 stars" plotted with "N-grams" on the horizontal axis and "SimCSE" on the vertical axis.

*Fig. 10 (p. 30):* The scent categories in Goodscents dataset with the highest (top) and lowest (bottom) vendi score (vs), using the molecular fingerprint similarity. We show 100 examples from each category, in decreasing order of average similarity, with the image at the top left having the highest average similarity scores. — This is a printed scientific figure (a diagram) consisting of four rectangular panels arranged in two rows, each panel filled with many small skeletal chemical-structure drawings. The upper row is headed by the italic text “Most diverse,” with the left panel labeled “Woody” and the right panel labeled “Herbal”; the lower row is headed by “Least diverse,” with the left panel labeled “Waxy” and the right panel labeled “Fatty.” The top two panels contain a wide variety of ring-shaped, branched, and heteroatom-containing molecular structures, while the bottom two panels are dominated by long, mostly linear chain-like structures with only occasional rings, branches, or colored atoms.

*Fig. 12 (p. 31):* The categories in Fashion MNIST with the lowest (left) and highest (right) Vendi Scores, defining similarity as the cosine similarity between either Inception embeddings (top) or pixel vectors (bottom). We show 100 examples from each category, in decreasing order of average similarity, with the image at the top left having the highest average similarity scores according to the corresponding kernel. — This is a figure made of eight square grids of small grayscale thumbnail images, arranged in two rows of four. The left edge of the top row is labeled “Inception” and of the bottom row “Pixels”; above the grids the headings read “Least diverse” over the first two columns and “Most diverse” over the last two columns in both rows. Each grid has a category label—“Sneaker”, “Ankle boot”, “Bag”, “Shirt” in the top row and “Trouser”, “Coat”, “Bag”, “Sandal” in the bottom row—and contains 100 tiny black-and-white images of that clothing or footwear type on a dark background.

*Fig. 13 (p. 32):* The attributes in celeba with the lowest (left) and highest (right) vs, defining similarity as the cosine similarity between either Inception embeddings (top), pixel vectors (middle), or binary attribute vectors (bottom). We show 100 examples from each category, in decreasing order of average similarity, with the image at the top left having the highest average similarity scores according to the corresponding kernel. These examples illustrate the importance of the choice of similarity function for defining the notion of diversity that is relevant for a given application. However, almost all choices of similarity functions show that the celeba dataset is more diverse for men than for women. — The picture is a document figure made of twelve 10-by-10 grids of small color face-portrait thumbnails, arranged in three rows labeled vertically on the left as “Inception,” “Pixels,” and “Attributes.” Each row has two grids beneath the header “Least diverse” and two beneath “Most diverse,” with attribute labels above them such as “Rosy_Cheeks,” “Blurry,” “Wearing_Hat,” “Blond_Hair,” “Mustache,” “Heavy_Makeup,” “Big_Nose,” and “Male.” The individual cells are tiny photographs of faces.

<!-- quelle: The Vendi Score. A Diversity Evaluation Metric for Machine Learning (p. 1–32) -->

## LITERATUR

<!-- quelle: References (p. 16–20) -->

- Adelman, M. A. (1969). Comment on the "H" concentration measure as a numbersequivalent. The Review of economics and statistics , pages 99-101.
- Alemi, A. A. and Fischer, I. (2018). GILBO: one metric to measure them all. In Proceedings of the 32nd International Conference on Neural Information Processing Systems , pages 7037-7046.
- Arora, S., Cohen, N., Hu, W ., and Luo, Y. (2019). Implicit regularization in deep matrix factorization. In Advances in Neural Information Processing Systems .
- Arora, S. and Zhang, Y. (2018). Do GANs actually learn the distribution? some theory and empirics. In International Conference on Learning Representations .
- Bach, F . (2022). Information theory with kernel methods. arXiv preprint arXiv:2202.08545 .
- Bengtsson, I. and ˙ Zyczkowski, K. (2017). Geometry of quantum states: an introduction to quantum entanglement . Cambridge university press.
- Benhenda, M. (2017). ChemGAN challenge for drug discovery: can AI reproduce natural chemical diversity? arXiv preprint arXiv:1708.08227 .
- Bird, S. (2006). Nltk: The natural language toolkit. In Proceedings of the COLING / ACL 2006 Interactive Presentation Sessions , pages 69-72.
- Child, R. (2020). Very deep VAEs generalize autoregressive models and can outperform them on images. arXiv preprint arXiv:2011.10650 .
- Cífka, O., Severyn, A., Alfonseca, E., and Filippova, K. (2018). Eval all, trust a few, do wrong to none: Comparing sentence generation models. arXiv preprint arXiv:1804.07972 .
- Devlin, J., Chang, M.-W ., Lee, K., and Toutanova, K. (2019). BERT: Pre-training of deep bidirectional transformers for language understanding. In Proceedings of the 2019 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies .
- Dhariwal, P . and Nichol, A. (2021). Diffusion models beat GANs on image synthesis. Advances in Neural Information Processing Systems , 34:8780-8794.
- Dieng, A. B., Ruiz, F . J., Blei, D. M., and Titsias, M. K. (2019). Prescribed generative adversarial networks. arXiv preprint arXiv:1910.04302 .
- Fomicheva, M., Sun, S., Yankovskaya, L., Blain, F ., Guzmán, F ., Fishel, M., Aletras, N., Chaudhary, V ., and Specia, L. (2020). Unsupervised quality estimation for neural machine translation. Transactions of the Association for Computational Linguistics , 8:539-555.
- Gao, T., Yao, X., and Chen, D. (2021). SimCSE: Simple contrastive learning of sentence embeddings. In Proceedings of the 2021 Conference on Empirical Methods in Natural Language Processing , pages 6894-6910.
- Grci´ c, M., Grubiši´ c, I., and Šegvi´ c, S. (2021). Densely connected normalizing flows. Advances in Neural Information Processing Systems , 34:23968-23982.
- Heusel, M., Ramsauer, H., Unterthiner, T., Nessler, B., and Hochreiter, S. (2017). Gans trained by a two time-scale update rule converge to a local nash equilibrium. Advances in neural information processing systems , 30.
- Hill, M. O. (1973). Diversity and Evenness: A Unifying Notation and Its Consequences. Ecology , 54(2):427-432.
- Jebara, T., Kondor, R., and Howard, A. (2004). Probability product kernels. The Journal of Machine Learning Research , 5:819-844.
- Jost, L. (2006). Entropy and Diversity. Oikos , 113(2):363-375.
- Karras, T ., Laine, S., and Aila, T . (2019). A style-based generator architecture for generative adversarial networks. In Proceedings of the IEEE / CVF conference on computer vision and pattern recognition , pages 4401-4410.
- Karras, T., Laine, S., Aittala, M., Hellsten, J., Lehtinen, J., and Aila, T . (2020). Analyzing and improving the image quality of StyleGAN. In Proceedings of the IEEE / CVF conference on computer vision and pattern recognition , pages 8110-8119.
- Keung, P ., Lu, Y., Szarvas, G., and Smith, N. A. (2020). The multilingual Amazon reviews corpus. In Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing .
- Krizhevsky, A. (2009). Learning multiple layers of features from tiny images. Technical report.
- Kulesza, A., Taskar, B., et al. (2012). Determinantal point processes for machine learning. Foundations and Trends® in Machine Learning , 5(2-3):123-286.
- Kviman, O., Melin, H., Koptagel, H., Elvira, V ., and Lagergren, J. (2022). Multiple importance sampling elbo and deep ensembles of variational approximations. In International Conference on Artificial Intelligence and Statistics , pages 1068710702. PMLR.
- Kynkäänniemi, T., Karras, T ., Laine, S., Lehtinen, J., and Aila, T . (2019). Improved precision and recall metric for assessing generative models. In Proceedings of the 33rd International Conference on Neural Information Processing Systems , pages 3927-3936.
- Lee, D., Kim, C., Kim, S., Cho, M., and Han, W .-S. (2022). Autoregressive Image Generation using Residual Quantization. In Proceedings of the IEEE / CVF Conference on Computer Vision and Pattern Recognition , pages 11523-11532.
- Leinster, T . (2021). Entropy and Diversity: The Axiomatic Approach . Cambridge University Press.
- Leinster, T . and Cobbold, C. A. (2012). Measuring Diversity: The Importance of Species Similarity. Ecology , 93(3):477-489.
- Li, J., Galley , M., Brockett, C., Gao, J., and Dolan, W . B. (2016). A diversity-promoting objective function for neural conversation models. In Proceedings of the 2016 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies , pages 110-119.
- Lin, T .-Y ., Maire, M., Belongie, S., Hays, J., Perona, P ., Ramanan, D., Dollár, P ., and Zitnick, C. L. (2014). Microsoft COCO: Common objects in context. In European conference on computer vision , pages 740-755. Springer.
- Liu, S., Wang, T., Bau, D., Zhu, J.-Y., and Torralba, A. (2020). Diverse image generation via self-conditioned gans. In Proceedings of the IEEE / CVF Conference on Computer Vision and Pattern Recognition (CVPR) .
- Liu, Z., Luo, P ., Wang, X., and Tang, X. (2015). Deep learning face attributes in the wild. In International Conference on Computer Vision .
- Metz, L., Poole, B., Pfau, D., and Sohl-Dickstein, J. (2017). Unrolled generative adversarial networks. In International Conference on Learning Representations .
- Mitchell, M., Baker, D., Moorosi, N., Denton, E., Hutchinson, B., Hanna, A., Gebru, T ., and Morgenstern, J. (2020). Diversity and inclusion metrics in subset selection. In Proceedings of the AAAI / ACM Conference on AI, Ethics, and Society , pages 117-123.
- Naeem, M. F ., Oh, S. J., Uh, Y., Choi, Y., and Yoo, J. (2020). Reliable fidelity and diversity metrics for generative models. In International Conference on Machine Learning , pages 7176-7185. PMLR.
- Nichol, A. Q. and Dhariwal, P . (2021). Improved denoising diffusion probabilistic models. In International Conference on Machine Learning , pages 8162-8171. PMLR.
- Papineni, K., Roukos, S., Ward, T., and Zhu, W .-J. (2002). BLEU: A method for automatic evaluation of machine translation. In Proceedings of the 40th annual meeting of the Association for Computational Linguistics , pages 311-318.
- Parmar, G., Zhang, R., and Zhu, J.-Y. (2022). On aliased resizing and surprising subtleties in gan evaluation. In Proceedings of the IEEE / CVF Conference on Computer Vision and Pattern Recognition , pages 11410-11420.
- Patil, G. and Taillie, C. (1982). Diversity as a Concept and Its Measurement. Journal of the American Statistical Association , 77(379):548-561.
- Polykovskiy, D., Zhebrak, A., Sanchez-Lengeling, B., Golovanov, S., Tatanov, O., Belyaev, S., Kurbanov, R., Artamonov, A., Aladinskiy, V ., Veselov, M., Kadurin, A., Johansson, S., Chen, H., Nikolenko, S., Aspuru-Guzik, A., and Zhavoronkov, A. (2020). Molecular Sets (MOSES): A Benchmarking Platform for Molecular Generation Models. Frontiers in Pharmacology .
- Posada, J. G., Vani, A., Schwarzer, M., and Lacoste-Julien, S. (2020). Gait: A geometric approach to information theory. In International Conference on Artificial Intelligence and Statistics , pages 2601-2611. PMLR.
- Preuer, K., Renz, P ., Unterthiner, T ., Hochreiter, S., and Klambauer, G. (2018). Fréchet ChemNet distance: a metric for generative models for molecules in drug discovery. Journal of chemical information and modeling , 58(9):1736-1741.
- Pugh, J. K., Soros, L. B., Szerlip, P . A., and Stanley , K. O. (2015). Confronting the challenge of quality diversity. In Proceedings of the 2015 Annual Conference on Genetic and Evolutionary Computation , pages 967-974.
- Radford, A., Metz, L., and Chintala, S. (2015). Unsupervised representation learning with deep convolutional generative adversarial networks. In arXiv:1511.06434 .
- Roy, O. and Vetterli, M. (2007). The effective rank: A measure of effective dimensionality. In 2007 15th European signal processing conference , pages 606-610. IEEE.
- Russakovsky, O., Deng, J., Su, H., Krause, J., Satheesh, S., Ma, S., Huang, Z., Karpathy, A., Khosla, A., Bernstein, M., et al. (2015). ImageNet large scale visual recognition challenge. International journal of computer vision , 115(3):211-252.
- Sajjadi, M. S., Bachem, O., Lucic, M., Bousquet, O., and Gelly, S. (2018). Assessing generative models via precision and recall. In Proceedings of the 32nd International Conference on Neural Information Processing Systems , pages 5234-5243.
- Salimans, T., Goodfellow, I., Zaremba, W ., Cheung, V ., Radford, A., Chen, X., and Chen, X. (2016). Improved Techniques for Training GANs. In Lee, D. D., Sugiyama, M., Luxburg, U. V ., Guyon, I., and Garnett, R., editors, Advances in Neural Information Processing Systems 29 , pages 2234-2242. Curran Associates, Inc.
- Sanchez-Lengeling, B., Wei, J. N., Lee, B. K., Gerkin, R. C., Aspuru-Guzik, A., and Wiltschko, A. B. (2019). Machine learning for scent: Learning generalizable perceptual representations of small molecules. arXiv preprint arXiv:1910.10685 .
- Shen, T., Ott, M., Auli, M., and Ranzato, M. (2019). Mixture models for diverse machine translation: Tricks of the trade. In International conference on machine learning , pages 5719-5728. PMLR.
- Simon, L., Webster, R., and Rabin, J. (2019). Revisiting precision and recall definition for generative model evaluation. In International Conference on Machine Learning (ICML) .
- Song, J., Meng, C., and Ermon, S. (2021). Denoising diffusion implicit models. In International Conference on Learning Representations .
- Srivastava, A., Valkov, L., Russell, C., Gutmann, M. U., and Sutton, C. (2017). VEEGAN: reducing mode collapse in GANs using implicit variational learning. In Advances in Neural Information Processing Systems .
- Szegedy, C., Vanhoucke, V ., Ioffe, S., Shlens, J., and Wojna, Z. (2016). Rethinking the Inception architecture for computer vision. In Proceedings of the IEEE conference on computer vision and pattern recognition , pages 2818-2826.
- Torregrossa, F ., Claveau, V ., Kooli, N., Gravier, G., and Allesiardo, R. (2020). On the correlation of word embedding evaluation metrics. In Proceedings of the 12th Conference on Language Resources and Evaluation (LREC 2020) , pages 4789-4797.
- Vijayakumar, A., Cogswell, M., Selvaraju, R., Sun, Q., Lee, S., Crandall, D., and Batra, D. (2018). Diverse beam search for improved description of complex scenes. In Proceedings of the AAAI Conference on Artificial Intelligence .
- Von Luxburg, U. (2007). A tutorial on spectral clustering. Statistics and computing , 17(4):395-416.
- Wilde, M. M. (2013). Quantum information theory . Cambridge University Press.
- Williams, A., Nangia, N., and Bowman, S. (2018). A broad-coverage challenge corpus for sentence understanding through inference. In Proceedings of the 2018 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies, Volume 1 (Long Papers) , pages 11121122.
- Williams, C. and Seeger, M. (2000). Using the nyström method to speed up kernel machines. Advances in Neural Information Processing Systems , 13.
- Wolf, T ., Debut, L., Sanh, V ., Chaumond, J., Delangue, C., Moi, A., Cistac, P ., Rault, T ., Louf, R., Funtowicz, M., et al. (2019). Huggingface's transformers: State-of-the-art natural language processing. arXiv preprint arXiv:1910.03771 .
- Xiao, H., Rasul, K., and Vollgraf, R. (2017). Fashion-MNIST: A novel image dataset for benchmarking machine learning algorithms. In arXiv:1708.07747 .
- Xie, Y., Xu, Z., Ma, J., and Mei, Q. (2022). How much of the chemical space has been explored? selecting the right exploration measure for drug discovery. In ICML 2022 2nd AI for Science Workshop .
- Yu, F ., Seff, A., Zhang, Y., Song, S., Funkhouser, T ., and Xiao, J. (2015). LSUN: Construction of a large-scale image dataset using deep learning with humans in the loop. arXiv preprint arXiv:1506.03365 .

## GLOSSAR

- **Vendi Score (VS)** — The exponential of the Shannon entropy of the eigenvalues of the normalized similarity matrix K/n; interpretable as the effective number of dissimilar elements in a sample; named for "von Neumann diversity."
- **Probability-weighted Vendi Score** — A generalization using the probability-weighted kernel matrix K̃p = diag(√p)K diag(√p), for settings with an explicit distribution over samples.
- **Effective number** — The interpretation of a diversity score as the size of an equally-weighted set of completely dissimilar elements that would have the same score.
- **Effective rank** — The exponential of the entropy of normalized singular values of a matrix (Roy and Vetterli, 2007); the Vendi Score is the effective rank of the kernel matrix.
- **von Neumann entropy** — The entropy of the eigenvalues of a density matrix from quantum statistical mechanics; the Vendi Score is its exponential for K/n.
- **Mode Diversity** — A measure introduced in the paper—the exponential entropy of the predicted mode distribution, exp H(p̂(y))—used to separate mode-imbalance effects from overall diversity.
- **IntDiv** — The standard molecular diversity metric, the average pairwise dissimilarity (complement of average Jaccard/Tanimoto fingerprint similarity); shown to miss clusters of duplicates.
- **Number of Modes (NOM)** — A classifier-based GAN mode-collapse metric counting unique predicted classes; limited to labeled datasets and coarser than VS.
- **n-gram diversity** — The proportion of unique n-grams out of total n-grams; a standard NLP diversity metric requiring discrete features.
- **Similarity function (kernel)** — A user-specified positive semidefinite function k with k(x,x)=1 that defines the notion of diversity the Vendi Score measures.
- **Diverse N-Best List** — In text decoding, a list of sentences with high likelihood under the model that are mutually distinct.
- **Heterogeneity** — Mitchell et al.'s term for variety in arbitrary attributes; the paper uses "diversity" in this same sense.
