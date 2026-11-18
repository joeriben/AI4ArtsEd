---
id: belrose-et-al-2023-leace-perfect-linear-concept-erasure-in-closed-form
titel: "LEACE: Perfect linear concept erasure in closed form"
autor: "Nora Belrose, David Schneider-Joseph, Shauli Ravfogel, Ryan Cotterell, Edward Raff, Stella Biderman"
jahr: 2023
quelle: arXiv preprint (EleutherAI; Bar-Ilan University; ETH Zürich; Booz Allen Hamilton)
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2306.03819"
status: published
checks: passed
review: passed
analyzed_at: "2026-11-15T11:17:50.348684+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: gedruckt
---

# LEACE: Perfect linear concept erasure in closed form

## PROFIL

The article "LEACE: Perfect linear concept erasure in closed form" is written by Nora Belrose, David Schneider-Joseph, Shauli Ravfogel, Ryan Cotterell, Edward Raff, and Stella Biderman, and is addressed to a machine-learning research audience working on fairness and interpretability. Its subject is LEACE (LEAst-squares Concept Erasure), a closed-form method for removing a specified concept from data embeddings, motivated by fairness (preventing classifiers from using attributes such as gender or race) and interpretability (measuring a concept's causal importance by removing it). The authors claim that LEACE provably prevents all linear classifiers from detecting a concept while altering the embedding as little as possible, and that a companion procedure, concept scrubbing, can erase a concept from every layer of a deep neural network without destroying the model's outputs. The paper first establishes five equivalent conditions for linear guardedness (Theorems 3.1–3.4), then derives LEACE as the unique minimal affine transformation (Theorems 4.1–4.3), showing that its projection is generally oblique rather than orthogonal. It evaluates the method on gender-bias removal in BERT embeddings against RLACE and INLP, replicates Elazar et al.'s amnesic probing with part-of-speech tags, and applies concept scrubbing to Pythia and LLaMA language models. It positions itself against prior erasure methods—SAL, Mean Projection, Fair PCA, and INLP—showing the first three guarantee guardedness but are not optimal, and that INLP causes collateral damage; it also relates its guardedness definition to the V-information of Ravfogel et al. Appendices supply proofs, a worked example, a regularization heuristic, and an "Oracle LEACE" variant. The document is usable in machine-learning teaching and research on fairness, interpretability, and probing of neural representations.

## WISSEN

### Purpose and Thesis (pp. 1–2)

This paper introduces **LEACE** (LEAst-squares Concept Erasure), a closed-form mathematical method for removing ("erasing") a specified concept from data embeddings—vector representations of data used inside machine learning models. The authors argue that concept erasure matters for two reasons: **fairness** (e.g., preventing a classifier from using gender or race in its predictions) and **interpretability** (e.g., removing a concept to observe how model behavior changes, thereby measuring the concept's causal importance). The central claims are: (1) LEACE provably prevents *all linear classifiers* from detecting a concept while altering the embedding as little as possible, and (2) a novel procedure called **concept scrubbing**, built on LEACE, can erase a concept from every layer of a deep neural network—something that was impossible with INLP, which cannot be applied to multiple layers of a transformer without causing its outputs to collapse into gibberish. The method is demonstrated on two tasks: measuring how much language models rely on part-of-speech information, and reducing gender bias in BERT embeddings.

The key theoretical insight is a previously unnoticed equivalence: a classification task is "linearly guarded" (no linear classifier can beat a constant predictor) *if and only if* every class has exactly the same mean feature vector. LEACE is derived as the unique minimal transformation achieving this condition.

### Preliminaries and Definitions (p. 2)

The paper frames a k-class classification task over jointly defined random vectors: X (input data in R^d) and Z (one-hot labels). A predictor η is chosen from a function class V to minimize expected loss. Two central definitions:

- **Guardedness**: X "(V, L)-guards" Z if its conditional distribution is among the worst possible for predicting Z using predictors in V and losses in L—no predictor can do better than a constant function.
- **Trivially Attainable Loss**: the lowest expected loss achievable by a constant predictor.
- **Linear Guardedness**: guardedness specifically when V is the class of linear predictors η(x) = b + Wx and L is the class of nonnegative convex loss functions.

### Theoretical Results: Five Equivalent Conditions (pp. 2–4)

The paper's primary theoretical result is that the following conditions are all equivalent:

1. The data X linearly guards the labels Z.
2. For all convex losses, the trivially attainable loss is optimal on (X, Z).
3. The class-conditional mean vectors E[X | Z = i] are equal to the unconditional mean E[X].
4. Every component of X has zero covariance with every component of Z.
5. Every linear classifier evaluated on X exhibits statistical parity with respect to Z.

The proofs proceed in stages: Theorem 3.1 shows that equal class centroids imply the trivially attainable loss cannot be improved (via Jensen's inequality—replacing each data point with its class centroid lower-bounds the loss, and if all centroids equal the global mean, W = 0 is optimal). Lemma 3.2 and Theorem 3.3 prove the converse for cross-entropy loss, using first-order optimality conditions. Theorem 3.4 establishes that equal class-conditional means hold if and only if the cross-covariance matrix Σ_XZ is the zero matrix.

### Deriving LEACE (pp. 4–6)

Theorem 4.1 characterizes all affine transformations r(x) = Px + b that produce linearly guarded features: r(X) guards Z **if and only if the columns of the cross-covariance matrix Σ_XZ lie in the null space of P**. This is a weak condition admitting many solutions, so the authors seek the "surgical" one minimizing the mean squared distance E‖r(X) − X‖²_M for any positive-semidefinite inner product M (including Euclidean and Mahalanobis norms). Theorem 4.2 gives the closed-form solution for centered data, and Theorem 4.3 extends it to uncentered data with the optimal bias b* = E[X] − P*E[X].

The resulting LEACE formula intuitively works in three steps (illustrated in Figure 1): (1) de-mean and whiten x, (2) orthogonally project onto the subspace responsible for correlations between X and Z, (3) unwhiten so the covariance structure mimics the original, then subtract this from x.

**Key insight on oblique projections (p. 6)**: Prior work assumed erasure functions should be orthogonal projections. LEACE's projection is generally *oblique* (not symmetric), and the authors show orthogonal projections are generally not least-squares optimal—the guardedness constraint is on the null space of P, not its range, so the range can be freely chosen to minimize edit distance. Appendix F gives a concrete 2-dimensional example where the oblique method achieves smaller mean squared edit distance.

The paper also notes (p. 6) that Theorem 4.1 implies three prior methods—Spectral Attribute Removal (SAL), Mean Projection, and Fair PCA—do guarantee linear guardedness with suitable hyperparameters, though they are not optimal in preserving the embedding. LEACE also extends to continuous (non-categorical) Z under ordinary least squares regression loss (§ 4.3).

### Evaluation: Gender Bias in BERT (pp. 6–8)

**Intrinsic evaluation (pp. 6–7)**: Using the biographies dataset of De-Arteaga et al. (annotated by binary gender and profession), the authors embed biographies with the [CLS] embedding of a frozen BERT model and erase gender information. Compared against RLACE (gradient-based adversarial erasure) and INLP (Iterative Nullspace Projection), LEACE is the only method to achieve random accuracy (perfect erasure) with a small edit, and is roughly two orders of magnitude faster, requiring no gradient-based optimization.

**Downstream fairness (p. 7)**: A profession-prediction classifier achieves 77.3% accuracy on projected embeddings versus 79.3% on originals—minimal damage to the main task. Meanwhile the TPR gap (bias measure from De-Arteaga et al., quantifying true-positive-rate differences between protected groups) drops from 0.198 to 0.084, and the correlation between per-profession TPR gap and the percentage of women in a profession falls from 0.867 to 0.392. Re-fitting the classifier on projected embeddings yields 78.1% accuracy but raises the TPR gap to 0.158.

**Amnesic probing revisited (pp. 8–9)**: Replicating Elazar et al.'s amnesic probing experiments on bert-base-uncased with part-of-speech (POS) tags (18 coarse tags from English Universal Dependencies), the authors erase POS information from single layers. INLP requires 20 iterations and reduces embedding rank by 360; LEACE reduces rank by just 17. LEACE only mildly changes accuracy and loss until layer 8, with the highest drop at layer 11, whereas INLP shows maximum effect at layer 6 (difficult to attribute to concept erasure given its collateral damage). This suggests the causal effect of POS on the language model concentrates in layer 11—in contrast with linear probing results, which peak at earlier layers.

### Concept Scrubbing (pp. 9–10)

Because INLP causes "collateral damage" to useful embedding features, it cannot be applied to multiple layers of a transformer without causing its outputs to collapse into gibberish. LEACE makes **concept scrubbing**—erasing all linear information about a concept at every layer—practical. Algorithm 1 works sequentially: for each layer l, fit LEACE parameters (P, b) on the hidden states H_l and labels Z, scrub those states, then feed the scrubbed embeddings to the next layer. This sequential fitting is necessary because intervening at one layer changes the distribution of hidden states at later layers. The covariance statistics can be computed in a streaming fashion; caching hidden states requires up to 500GB in their experiments, or recomputation raises cost from O(ℓ) to O(ℓ²).

**Experiments (pp. 9–10)**: The authors scrub POS information from autoregressive language models—EleutherAI's Pythia (160M, 1.4B, 6.9B, 12B) and Meta's LLaMA (7B, 13B, 30B)—using 2²² tokens each for fitting and evaluation from the Pile and RedPajama corpora respectively, with SpaCy-generated Universal Dependency tags. Erasure is applied to the input of each transformer block after normalization. Results (Table 1, in bits per UTF-8 byte): random subspace erasure barely affects perplexity (e.g., LLaMA 7B: 0.69 unchanged), while LEACE raises it substantially (LLaMA 7B: 1.73; Pythia 6.9B: 3.57). SAL causes even larger increases (LLaMA 7B: 3.24), which the authors interpret as SAL inflicting more collateral damage—meaning SAL alone would have overestimated the causal effect of POS. The unigram baseline is 2.90 for LLaMA and 2.66 for Pythia. The conclusion: autoregressive language models heavily rely on linearly encoded POS information.

### Limitations and Future Work (p. 10)

The authors call for validation of concept scrubbing with narrower concepts and behavioral metrics, and suggest incorporating scrubbing into pretraining/finetuning to train networks under "conceptual constraints"—though gradient-based optimizers might circumvent such constraints by encoding attributes nonlinearly. They conjecture it is intractable to nondestructively prevent a general nonlinear adversary from recovering Z without detailed knowledge of the data-generating process.

### Appendices (pp. 15–22)

- **Appendix A**: Related work on adversarial (training-time) vs. post-hoc linear erasure methods.
- **Appendices B, C**: Proofs of the equivalence of guardedness with constant-predictor optimality and with statistical parity.
- **Appendix D**: Shows full-rank SAL and Mean Projection guarantee linear guardedness; MP is mathematically equivalent to SAL for binary Z.
- **Appendix E**: Two independent proofs of the LEACE formula (algebraic and covector-based).
- **Appendix F**: Worked example demonstrating oblique projections outperform orthogonal ones.
- **Appendix G**: Equivalence of the paper's guardedness definition with the V-information definition of Ravfogel et al.
- **Appendix H**: A regularization heuristic for concept scrubbing: because LEACE's oblique projection can have singular values greater than 1, embedding norms can diverge (producing NaNs); the authors mix P with SAL's orthogonal projection Q via a convex combination P′ = αP + (1−α)Q chosen so the post-erasure covariance trace equals the original, preserving both guardedness and MSE guarantees.
- **Appendix I**: **Oracle LEACE**—when labels z are available at inference time, the nearest guarded X′ equals the ordinary least squares residuals from regressing X on Z, plus a constant shift preserving the mean.
- **Appendix J**: Notation key.

### Figures (p. 6–22)

*Fig. 1 (p. 6):* LEACE projection in 3 steps. First the data is whitened, ensuring equal variance in all directions. It is then orthogonally projected onto colsp( WΣ XZ ) ⊥ , guaranteeing linear guardedness. Finally, we unwhiten the data so that its covariance structure mimics the original. — It is a four-panel scatter-plot diagram. The panels are titled "Original Data", "Whitening", "Erasure", and "Unwhitening"; each has numbered axes and shows a cloud of blue and orange points, with red and green lines drawn in every panel and a black dashed line also shown in some panels. In the "Erasure" panel the points lie along the green line, whereas in the other panels they form elongated clouds. A legend on the right reads "Concept Subspace", "Orthogonal Subspace", "Output Subspace", "Class 1", and "Class 2".

*Fig. 3 (p. 7):* The correlation between GAP TPR female,y and the relative proportion of women in profession y , for BERT embedding, before (left; R=0.867) and after (right; R=0.392) the projection. — The image shows two side-by-side scatter plots. Each plot has a horizontal axis labeled "% women" with tick marks at 0.2, 0.4, 0.6, and 0.8, and a vertical axis labeled "TPR-Gap" with tick marks at -0.4, -0.2, 0.0, 0.2, and 0.4. Blue circular data points are plotted in each graph, each accompanied by a small red text label naming a profession; legible examples include "surgeon", "nurse", "paralegal", "yoga_teacher", "teacher", and "psychologist". A red straight line passes through the points in each plot, sloping steeply upward in the left plot and only slightly upward in the right plot.

*Fig. 2 (p. 7):* Gender prediction accuracy after bias-removal projection versus the mean squared distance from the original embedding for INLP, RLACE, and LEACE on BERT embeddings. — This is a line chart with "Gender Accuracy" on the vertical axis (ranging from 0.5 to 0.9) and "Mean Squared Error" on the horizontal axis (ranging from 2 to 6). A dashed horizontal line labeled "Majority" runs across the plot at approximately 0.52. The "INLP" series (orange line with error bars) begins near 0.93 at the upper left and slopes downward to about 0.52 at the right edge. The "RLACE" series (blue line with error bars) stays relatively flat around 0.55, and the "Ours" series (red line with error bars) is positioned near the bottom at approximately 0.52.

*Fig. 4 (p. 8):* Amnesic probing results on bert-base-uncased . — The image shows two side-by-side line charts sharing the same x-axis label, "Layer of Intervention," with tick values from 0 to 12. The left chart has a y-axis labeled "MLM Accuracy" (ranging from about 0.2 to above 0.8), and the right chart has a y-axis labeled "MLM Loss" (ranging from 1 to 5). Both charts plot four lines identified in a legend on the left chart: "Ours" (blue line with markers), "Random" (orange line), "INLP (20 iterations)" (green line), and "No Intervention" (black dashed line), which sits near the top of the accuracy chart and near the bottom of the loss chart. In the left chart, the blue "Ours" line stays high until around layer 8, drops sharply to a minimum near layer 11, and rises again at layer 13, while the green "INLP (20 iterations)" line dips around layer 6 and then gradually rises; in the right chart, the blue line peaks above 5 near layer 11 and the green line peaks at 4 near layer 6.

*Fig. 5 (p. 20):* Orthogonal projection of i th component of X , itself a vector in the random variable Hilbert space H , onto the span of the components of Z . The residual X i -proj Z X i is the closest vector to X i orthogonal to, and hence uncorrelated with, Z = span( { Z 1 , Z 2 } ) . — This is a three-dimensional geometric diagram. A green plane labeled "span Z" contains two vectors labeled "Z_1" and "Z_2" emanating from a common origin, while a vector labeled "X_i" extends upward out of the plane. A dashed segment connects the tip of "X_i" to a point in the plane marked "proj_Z X_i", with a small right-angle marker at the plane, and this dashed segment is labeled "X'_i = X_i - proj_Z X_i". _(Lettering in the image, read by the image model, not confirmed: "Z_1", "Z_2", "X_i", "X_i", "proj_Z X_i", "X'_i = X_i - proj_Z X_i")_

*Image 6 (p. 22):* — The image is a diagram containing four scatter plots arranged side by side, titled "Original Data", "Whitening", "Erasure", and "Unwhitening". Each plot displays data points in blue and orange along with three lines intersecting near the center: a red solid line, a black dashed line, and a green solid line. A legend on the right labels the red line "Concept Subspace", the black dashed line "Orthogonal Subspace", the green line "Output Subspace", the blue points "Class 1", and the orange points "Class 2". The plots have grid lines and axes with numerical labels, the vertical axis ranging from -6 to 6 and the horizontal axis from -5 to 5.

*Fig. 2 (p. 22):* Gender prediction accuracy after debiasing against the mean squared distance of the debiased embedding from the original. Ours is the only method to achieve perfect erasure on this dataset (dashed line), and does so with low MSE. For INLP and RLACE, each point corresponds to a different setting of the rank hyperparameter; from left to right the ranks are 1, 4, 8, 16, 32, 50, 64, and 100. Our method is rank 1. — This is a line chart with error bars plotting **Gender Accuracy** on the vertical axis against **Mean Squared Error** on the horizontal axis. The legend in the upper right identifies four series: **Majority** (dashed line), **RLACE** (blue line with plus markers), **INLP** (orange line with x markers), and **Ours** (red marker). The **Majority** series appears as a horizontal dashed line at approximately 0.52. The **INLP** line descends from roughly 0.93 at the left to about 0.53 at the right, the **RLACE** line remains relatively flat near 0.54 across the x-axis range, and **Ours** appears as a single red plus marker near Mean Squared Error 2.2 at the Majority line level.

*Fig. 3 (p. 22):* Corrected version of Figure 3 in our submission, which had erroneously reported that BERT exhibited better masked language modeling accuracy after a random subspace of its activations was ablated. One of our authors had accidentally transposed a digit in the 'No Intervention' MLM accuracy, typing 0.892 in lieu of 0.928. — This is a line chart with the y-axis labeled “MLM Accuracy” and the x-axis labeled “Layer of Intervention.” A legend identifies four plotted series: “Ours,” “Random,” “INLP (20 iterations),” and “No Intervention,” with the last shown as a dashed line. The “Random” and “No Intervention” lines remain near the top across the x-axis range, while “Ours” stays high, drops sharply near layer 11, and rises again by the right edge; “INLP (20 iterations)” dips around layer 6 and then climbs. Visible y-axis tick labels are 0.2, 0.4, 0.6, and 0.8, and visible x-axis tick labels are 0, 2, 4, 6, 8, 10, and 12.

<!-- quelle: LEACE: Perfect linear concept erasure in closed form (p. 1–22) -->

## LITERATUR

<!-- quelle: References (p. 11–14) -->

- UC Berkeley. The Hilbert space of random variables. Lecture Notes Electrical Engineering 126, 2018. URL https://inst.eecs.berkeley.edu/~ee126/sp18/projection.pdf .
- Stella Biderman, Hailey Schoelkopf, Quentin Anthony, Herbie Bradley, Kyle O'Brien, Eric Hallahan, Mohammad Aflah Khan, Shivanshu Purohit, USVSN Sai Prashanth, Edward Raff, et al. Pythia: A suite for analyzing large language models across training and scaling. arXiv preprint arXiv:2304.01373 , 2023.
- Tolga Bolukbasi, Kai-Wei Chang, James Y. Zou, Venkatesh Saligrama, and Adam T. Kalai. Man is to computer programmer as woman is to homemaker? Debiasing word embeddings. Advances in Neural Information Processing Systems , 29:4349-4357, 2016. URL https://proceedings.neurips.cc/paper/2016/file/ a486cd07e4ac3d270571622f4f316ec5-Paper.pdf .
- Xilun Chen, Yu Sun, Ben Athiwaratkun, Claire Cardie, and Kilian Weinberger. Adversarial deep averaging networks for cross-lingual sentiment classification. Transactions of the Association for Computational Linguistics , 6:557-570, 2018. URL https://aclanthology.org/ Q18-1039 .
- Verna Dankers, Christopher Lucas, and Ivan Titov. Can transformer be too compositional? Analysing idiom processing in neural machine translation. In Proceedings of the 60th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers) , pages 3608-3626, 2022.
- Maria De-Arteaga, Alexey Romanov, Hanna Wallach, Jennifer Chayes, Christian Borgs, Alexandra Chouldechova, Sahin Geyik, Krishnaram Kenthapadi, and Adam Tauman Kalai. Bias in bios: A case study of semantic representation bias in a high-stakes setting. In Proceedings of the Conference on Fairness, Accountability, and Transparency , FAT* '19, page 120-128, New York, NY, USA, 2019. Association for Computing Machinery. ISBN 9781450361255. doi: 10.1145/3287560.3287572. URL https://doi.org/10.1145/3287560.3287572 .
- Sunipa Dev, Tao Li, Jeff M. Phillips, and Vivek Srikumar. OSCaR: Orthogonal subspace correction and rectification of biases in word embeddings. In Proceedings of the 2021 Conference on Empirical Methods in Natural Language Processing , pages 5034-5050, Online and Punta Cana, Dominican Republic, November 2021. Association for Computational Linguistics. doi: 10.18653/v1/2021.emnlp-main.411. URL https://aclanthology.org/2021. emnlp-main.411 .
- Harrison Edwards and Amos Storkey. Censoring representations with an adversary. In International Conference in Learning Representations , pages 1-14, May 2016. URL https: //arxiv.org/abs/1511.05897 .
- Yanai Elazar and Yoav Goldberg. Adversarial removal of demographic attributes from text data. In Proceedings of the 2018 Conference on Empirical Methods in Natural Language Processing , pages 11-21, Brussels, Belgium, October-November 2018. Association for Computational Linguistics. doi: 10.18653/v1/D18-1002. URL https://aclanthology.org/D18-1002 .
- Yanai Elazar, Shauli Ravfogel, Alon Jacovi, and Yoav Goldberg. Amnesic probing: Behavioral explanation with amnesic counterfactuals. Transactions of the Association for Computational Linguistics , 9:160-175, 2021. doi: 10.1162/tacl_a_00359. URL https://aclanthology. org/2021.tacl-1.10 .
- Nelson Elhage, Neel Nanda, Catherine Olsson, Tom Henighan, Nicholas Joseph, Ben Mann, Amanda Askell, Yuntao Bai, Anna Chen, Tom Conerly, Nova DasSarma, Dawn Drain, Deep Ganguli, Hatfield Zac Dodds, Danny Hernandez, Andy Jones, Jackson Kernion, Liane Lovitt, Kamal Ndousse, Dario Amodei, Tom Brown, Jack Clark, Jared Kaplan, Sam McCandlish, and Chris Olah. A mathematical framework for transformer circuits. Transformer Circuits Thread , 2021.
- Thomas S. Ferguson. Mathematical Statistics . Academic Press, Cambridge, MA, 1967.
- Leo Gao, Stella Biderman, Sid Black, Laurence Golding, Travis Hoppe, Charles Foster, Jason Phang, Horace He, Anish Thite, Noa Nabeshima, Shawn Presser, and Connor Leahy. The Pile: An 800GB dataset of diverse text for language modeling. arXiv preprint arXiv:2101.00027 , 2020.
- Atticus Geiger, Zhengxuan Wu, Hanson Lu, Josh Rozner, Elisa Kreiss, Thomas Icard, Noah Goodman, and Christopher Potts. Inducing causal structure for interpretable neural networks. In International Conference on Machine Learning , pages 7324-7338. PMLR, 2022.
- Christopher Grimsley, Elijah Mayfield, and Julia R.S. Bursten. Why attention is not explanation: Surgical intervention and causal reasoning about neural models. In Proceedings of the Twelfth Language Resources and Evaluation Conference , pages 1780-1790, Marseille, France, May 2020. European Language Resources Association. URL https://aclanthology.org/2020. lrec-1.220 .
- Pantea Haghighatkhah, Wouter Meulemans, Bettina Speckmann, Jérôme Urhausen, and Kevin Verbeek. Obstructing classification via projection. In Filippo Bonchi and Simon J. Puglisi, editors, 46th International Symposium on Mathematical Foundations of Computer Science , Leibniz International Proceedings in Informatics, LIPIcs. Schloss Dagstuhl - Leibniz-Zentrum für Informatik, 2021.
- Pantea Haghighatkhah, Antske Fokkens, Pia Sommerauer, Bettina Speckmann, and Kevin Verbeek. Better hit the nail on the head than beat around the bush: Removing protected attributes with a single projection. pages 8395-8416, December 2022. doi: 10.18653/v1/2022. emnlp-main.575. URL https://aclanthology.org/2022.emnlp-main.575 .
- Evan Hernandez and Jacob Andreas. The low-dimensional linear geometry of contextualized word representations. In Proceedings of the 25th Conference on Computational Natural Language Learning , pages 82-93, 2021.
- Matthew Honnibal, Ines Montani, Sofie Van Landeghem, and Adriane Boyd. spaCy: Industrialstrength Natural Language Processing in Python, 2020.
- Matthäus Kleindessner, Michele Donini, Chris Russell, and Muhammad Bilal Zafar. Efficient fair PCA for fair representation learning. In International Conference on Artificial Intelligence and Statistics , pages 5250-5270. PMLR, 2023.
- Abhinav Kumar, Chenhao Tan, and Amit Sharma. Probing classifiers are unreliable for concept removal and detection. In S. Koyejo, S. Mohamed, A. Agarwal, D. Belgrave, K. Cho, and A. Oh, editors, Advances in Neural Information Processing Systems , volume 35, pages 17994-18008. Curran Associates, Inc., 2022. URL https://proceedings.neurips.cc/paper_files/ paper/2022/file/725f5e8036cc08adeba4a7c3bcbc6f2c-Paper-Conference.pdf .
- Matt J. Kusner, Joshua Loftus, Chris Russell, and Ricardo Silva. Counterfactual fairness. Advances in Neural Information Processing Systems , 30, 2017.
- Ryan McDonald, Joakim Nivre, Yvonne Quirmbach-Brundage, Yoav Goldberg, Dipanjan Das, Kuzman Ganchev, Keith Hall, Slav Petrov, Hao Zhang, Oscar Täckström, et al. Universal dependency annotation for multilingual parsing. In Proceedings of the 51st Annual Meeting of the Association for Computational Linguistics (Volume 2: Short Papers) , pages 92-97, 2013.
- Neel Nanda. Actually, Othello-GPT has a linear emergent world model, Mar 2023. URL <https://neelnanda.io/mechanistic-interpretability/othello> .
- Vassilina Nikoulina, Maxat Tezekbayev, Nuradil Kozhakhmet, Madina Babazhanova, Matthias Gallé, and Zhenisbek Assylbekov. The rediscovery hypothesis: Language models need to meet linguistics. Journal of Artificial Intelligence Research , 72:1343-1384, 2021.
- Hamed Nilforoshan, Johann D. Gaebler, Ravi Shroff, and Sharad Goel. Causal conceptions of fairness and their consequences. In International Conference on Machine Learning , pages 16848-16887. PMLR, 2022.
- Joakim Nivre, Marie-Catherine de Marneffe, Filip Ginter, Jan Hajic, Christopher D. Manning, Sampo Pyysalo, Sebastian Schuster, Francis Tyers, and Daniel Zeman. Universal Dependencies v2: An evergrowing multilingual treebank collection. In Proceedings of the 12th Language Resources and Evaluation Conference , pages 4034-4043, 2020.
- Judea Pearl. Causality . Cambridge University Press, Cambridge, UK, 2 edition, 2009. ISBN 978-0-521-89560-6. doi: 10.1017/CBO9780511803161.
- Shauli Ravfogel, Yanai Elazar, Hila Gonen, Michael Twiton, and Yoav Goldberg. Null it out: Guarding protected attributes by iterative nullspace projection. In Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics , pages 7237-7256, Online, July 2020. Association for Computational Linguistics. doi: 10.18653/v1/2020.acl-main.647. URL https://aclanthology.org/2020.acl-main.647 .
- Shauli Ravfogel, Grusha Prasad, Tal Linzen, and Yoav Goldberg. Counterfactual interventions reveal the causal effect of relative clause representations on agreement prediction. In Proceedings of the 25th Conference on Computational Natural Language Learning , pages 194-209, 2021.
- Shauli Ravfogel, Michael Twiton, Yoav Goldberg, and Ryan D Cotterell. Linear adversarial concept erasure. In International Conference on Machine Learning , pages 18400-18421. PMLR, 2022.
- Shauli Ravfogel, Francisco Vargas, Yoav Goldberg, and Ryan Cotterell. Adversarial concept erasure in kernel space. In Proceedings of the 2022 Conference on Empirical Methods in Natural Language Processing , pages 6034-6055, 2022.
- Shauli Ravfogel, Yoav Goldberg, and Ryan Cotterell. Log-linear guardedness and its implications. In Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers) , pages 9413-9431, Toronto, Canada, July 2023. Association for Computational Linguistics. doi: 10.18653/v1/2023.acl-long.523. URL https://aclanthology.org/2023.acl-long.523 .
- Bashir Sadeghi and Vishnu Boddeti. On the fundamental trade-offs in learning invariant representations. arXiv preprint arXiv:2109.03386 , 2021. URL https://openreview.net/ pdf?id=KOk7mUGspN9 .
- Bashir Sadeghi, Runyi Yu, and Vishnu Boddeti. On the global optima of kernelized adversarial representation learning. In 2019 IEEE/CVF International Conference on Computer Vision , pages 7970-7978. IEEE, 2019. URL http://hal.cse.msu.edu/assets/pdfs/papers/ 2019-iccv-kernel-adversarial-representation-learning.pdf .
- Shun Shao, Yftah Ziser, and Shay B. Cohen. Gold doesn't always glitter: Spectral removal of linear and nonlinear guarded attribute information. In Proceedings of the 17th Conference of the European Chapter of the Association for Computational Linguistics , pages 1611-1622, Dubrovnik, Croatia, May 2023. Association for Computational Linguistics. URL https: //aclanthology.org/2023.eacl-main.118 .
- Shun Shao, Yftah Ziser, and Shay B. Cohen. Erasure of unaligned attributes from neural representations. Transactions of the Association for Computational Linguistics , 11:488-510, 2023. doi: 10.1162/tacl_a_00558. URL https://aclanthology.org/2023.tacl-1.29 .
- Ian Tenney, Dipanjan Das, and Ellie Pavlick. BERT rediscovers the classical NLP pipeline. In Proceedings of the 57th Annual Meeting of the Association for Computational Linguistics , pages 4593-4601, 2019.
- Hugo Touvron, Thibaut Lavril, Gautier Izacard, Xavier Martinet, Marie-Anne Lachaux, Timothée Lacroix, Baptiste Rozière, Naman Goyal, Eric Hambro, Faisal Azhar, Aurelien Rodriguez, Armand Joulin, Edouard Grave, and Guillaume Lample. LLaMA: Open and efficient foundation language models, 2023. URL http://arxiv.org/abs/2302.13971 .
- James Francis Woodward. Making Things Happen: A Theory of Causal Explanation explanation . Oxford University Press, 2005.
- Zhengxuan Wu, Atticus Geiger, Christopher Potts, and Noah Goodman. Interpretability at scale: Identifying causal mechanisms in Alpaca. 2023.
- Qizhe Xie, Zihang Dai, Yulun Du, Eduard Hovy, and Graham Neubig. Controllable invariance through adversarial feature learning. In Advances in Neural Information Processing Systems , volume 30, pages 585-596, 2017. URL https://dl.acm.org/doi/10.5555/3294771. 3294827 .
- Yilun Xu, Shengjia Zhao, Jiaming Song, Russell Stewart, and Stefano Ermon. A theory of usable information under computational constraints. In 8th International Conference on Learning Representations , 2020. URL https://openreview.net/forum?id=r1eBeyHFDH .
- Brian Hu Zhang, Blake Lemoine, and Margaret Mitchell. Mitigating unwanted biases with adversarial learning. In Proceedings of the 2018 AAAI/ACM Conference on AI, Ethics, and Society , page 335-340, New York, NY, USA, 2018. Association for Computing Machinery. ISBN 9781450360128. URL https://doi.org/10.1145/3278721.3278779 .

## GLOSSAR

- **LEACE (LEAst-squares Concept Erasure)** — A closed-form affine transformation that provably prevents all linear classifiers from detecting a concept while minimally changing the embedding, measured by any norm induced by an inner product.
- **Concept erasure** — Removing a specified feature from an embedding to improve fairness or interpretability, without finetuning or inspecting model parameters.
- **Guardedness** — The property that a data vector X is among the worst possible distributions for predicting labels Z using predictors from a class V and losses from L—no predictor beats a constant function.
- **Linear guardedness** — Guardedness where V is the class of linear predictors and L the class of nonnegative convex losses.
- **Trivially attainable loss** — The lowest expected loss achievable by a constant predictor.
- **Trivial predictor** — The specific constant predictor achieving the trivially attainable loss (e.g., log of class probabilities under cross-entropy).
- **V-information / predictive V-information** — A tractable lower bound on mutual information I(X; Z), measuring how well classifiers from family V can predict Z.
- **Concept scrubbing** — The paper's procedure of sequentially applying LEACE to the activations at every layer of a deep network, fitting parameters layer by layer.
- **Oblique projection** — A non-symmetric idempotent projection; LEACE's projection is generally oblique, and the paper shows oblique projections are least-squares optimal for erasure, unlike orthogonal ones.
- **Whitening transformation** — W = (Σ_XX^{1/2})⁺, used in LEACE to equalize variance in all directions before projection.
- **Cross-covariance matrix (Σ_XZ)** — The matrix whose (i, j)th entry is Cov(X_i, Z_j); linear guardedness holds iff it is zero.
- **Statistical parity** — The fairness condition that a function's expected output is the same regardless of the protected attribute Z.
- **TPR-GAP (GAP_TPR)** — A bias measure from De-Arteaga et al. quantifying the difference in true positive rates between individuals with different protected attributes.
- **Amnesic probing** — A causal intervention (from Elazar et al.) that removes a concept from model activations to test its importance to a main task.
- **Oracle LEACE** — A variant assuming access to labels at inference time; the nearest guarded X′ equals OLS residuals from regressing X on Z, plus a mean-preserving shift.
