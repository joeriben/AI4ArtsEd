---
id: gonen-goldberg-2019-lipstick-on-a-pig-debiasing-methods-cover-up-systematic-gender-biases
titel: "Lipstick on a Pig: Debiasing Methods Cover up Systematic Gender Biases in Word Embeddings But do not Remove Them"
autor: "Hila Gonen, Yoav Goldberg"
jahr: 2019
quelle: "Proceedings of the 2019 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies, Volume 1 (Long and Short Papers), pages 6096–6106"
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, bias]
lizenz: CC BY 4.0 (ACL Anthology) - original not redistributed; this file is a condensation produced on this platform
url: "https://doi.org/10.18653/v1/N19-1061"
status: published
checks: passed
review: passed
analyzed_at: "2026-11-15T11:27:46.956747+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: gedruckt
---

# Lipstick on a Pig: Debiasing Methods Cover up Systematic Gender Biases in Word Embeddings But do not Remove Them

## PROFIL

This scholarly article by Hila Gonen and Yoav Goldberg, published in the ACL anthology, addresses the NLP research community working on fairness and bias in language technology. Its subject is gender bias in word embeddings and the methods proposed to remove it; its claim is that existing debiasing techniques are superficial—they hide bias rather than eliminate it, because bias information survives in the geometry of the embedding space even after the standard bias metric (projection on the "gender direction," the vector difference between "he" and "she") has been reduced. The paper first reviews prior work showing that embeddings reflect societal stereotypes (Bolukbasi et al., 2016; Caliskan et al., 2017) and examines two debiasing methods: HARD-DEBIASED (Bolukbasi et al., 2016), a post-processing approach the authors credit as foundational but argue rests on an incomplete bias definition, and GN-GLOVE (Zhao et al., 2018), a training-time approach they consider the right strategy but equally insufficient; it also notes related work by Zhang et al. (2018) and the "indirect bias" mentioned in the extended version of Bolukbasi et al. It then reports five experiments comparing debiased embeddings against their biased counterparts: clustering of the most biased words (accuracy 92.5% and 85.6% after debiasing), a proposed bias-by-neighbours measure correlating strongly with original bias, profession-neighbour correlations, WEAT stereotyped-association tests remaining statistically significant after debiasing, and SVM classification predicting a word's implicit gender at 88.88% and 96.53% accuracy from debiased vectors alone. The conclusion argues that the real danger is algorithmic discrimination—e.g., a resume classifier favoring male candidates from stereotypical cues that survive debiasing—and that current bias-removal techniques should not be trusted to provide genuinely gender-neutral modeling. The article is usable in computational linguistics, machine-learning ethics, and data-science education, particularly in teaching situations concerning fairness, bias measurement, and the limits of technical debiasing methods.

## WISSEN

### Purpose and Thesis (p. 609)

This paper, by Hila Gonen and Yoav Goldberg, argues that existing methods for removing gender bias from word embeddings are superficial: they hide the bias rather than eliminate it. Word embeddings (vector representations of words used throughout NLP) are known to reflect societal gender biases. Recent debiasing methods substantially reduce bias according to a specific definition—the projection of a word vector onto a "gender direction" (the vector difference between "he" and "she"). The authors contend that while this metric drops after debiasing, the bias information survives in the geometry of the embedding space, in the distances between supposedly "gender-neutralized" words, and can be recovered from them. They demonstrate this through a series of experiments on two debiasing methods and conclude that current bias-removal techniques should not be trusted to provide genuinely gender-neutral modeling.

### Background: Gender Bias in Word Embeddings and Existing Debiasing Methods (p. 609–610)

The paper situates itself in prior research showing that embeddings reflect social biases. Bolukbasi et al. (2016b), using word2vec trained on Google News, showed that analogies surface stereotypes, e.g. "man is to computer programmer as woman is to x" yields "x = homemaker". Caliskan et al. (2017) demonstrated associations between male/female names and stereotypically gendered word groups (arts vs. science), and correlations between the gender association of occupation words and real labor-force participation data.

Two main debiasing approaches are examined:

1. **HARD-DEBIASED (Bolukbasi et al., 2016b)**: a post-processing method that zeroes the gender projection of each non-inherently-gendered word on a predefined gender direction (chosen as the top principal component of ten gender-pair difference vectors), and additionally ensures neutral words are equidistant to both members of explicitly gendered pairs (e.g. mother, brother, queen). The authors credit this work as rigorous and foundational—it defined the concept of debiasing and established the de facto bias metric—but argue the gender direction is only an indicator of bias, not its complete manifestation.

2. **GN-GLOVE (Zhao et al., 2018)**: trains debiased embeddings from scratch by altering the GloVe loss to concentrate gender information in the last coordinate of each vector, using male/female seed word groups, and encouraging neutral words (excluding that coordinate) to be orthogonal to the gender direction. The authors consider training-time debiasing the right approach, but note it relies on the same insufficient definition.

A related work, Zhang et al. (2018), using adversarial networks and the same bias definition, is expected to show similar results but was not verified. The authors also note that the extended arxiv version of Bolukbasi et al. (2016a) mentions this residual phenomenon as "indirect bias" but treats it as a nuance without quantifying it.

The key observation: most word pairs maintain their previous similarity after debiasing, so previously biased words remain grouped together, and the overall spatial geometry of the embeddings stays largely unchanged.

### Experimental Setup (p. 611)

The authors compare each debiased embedding against its biased counterpart: for HARD-DEBIASED, the embeddings before post-processing; for GN-GLOVE, standard GloVe trained on the same corpus. Following Bolukbasi et al., they use a reduced vocabulary: the most frequent 50,000 words and phrases, removing words with upper-case letters, digits, punctuation, or length over 20 characters, and removing inherently gendered words as predefined in each work. This yields 26,189 words for HARD-DEBIASED and 47,698 for GN-GLOVE. Bias is computed as projection on the gender direction (he − she). To quantify associations between word sets, they use the Word Embedding Association Test (WEAT) from Caliskan et al. (2017), a permutation test comparing target-word sets (e.g. male/female professions) to attribute sets (e.g. male/female names).

### Experiments and Results (p. 611–613)

1. **Clustering of biased words**: The 500 most male-biased and 500 most female-biased words (per the original bias) are clustered into two clusters via k-means. After debiasing, clusters still align with gender: accuracy 92.5% for HARD-DEBIASED (vs. 99.9% before) and 85.6% for GN-GLOVE (vs. 100% before). tSNE projections visualize this before and after debiasing.

2. **Bias-by-neighbours**: Since bias can no longer be observed directly (e.g. "nurse" is no longer closer to explicitly feminine words), the authors propose measuring bias as the percentage of male/female socially-biased words among the k nearest neighbors of a target word. This correlates strongly with the original bias measure: Pearson correlation 0.686 for HARD-DEBIASED (vs. 0.741 for the biased version) and 0.736 for GN-GLOVE (vs. 0.773), all with p-values of 0.

3. **Professions**: Using the profession list from the prior works, the number of male neighbors correlates with original bias: Pearson 0.606 for HARD-DEBIASED (vs. 0.747 biased) and 0.792 for GN-GLOVE (vs. 0.820), all significant with p-values < 1 × 10⁻³⁰.

4. **Stereotyped associations (WEAT)**: Replicating three experiments from Caliskan et al. (2017), using the full vocabulary and substituting female/male names for inherently gendered words: (a) names vs. family/career words; (b) names vs. arts/mathematics words; (c) names vs. arts/science words. For HARD-DEBIASED, p-values are 0, 0.00016, and 0.0467; for GN-GLOVE, 7.7 × 10⁻⁵, 0.00031, and 0.0064—i.e. the stereotyped associations remain statistically significant after debiasing.

5. **Classification**: An RBF-kernel SVM trained on 1,000 of the 5,000 most biased words (2,500 per gender) to predict gender, tested on the remaining 4,000, achieves 88.88% accuracy on HARD-DEBIASED (vs. 98.25% non-debiased) and 96.53% on GN-GLOVE (vs. 98.65% non-debiased). The implicit gender of words is thus easy to predict from the debiased vectors alone.

### Discussion and Conclusion (p. 613)

The experiments reveal a systematic bias independent of the gender direction: (1) words with strong previous same-direction bias cluster together; (2) words with implicit social-stereotype gender (e.g. receptionist, hairdresser, captain) still group with same-gender implicit words; (3) the implicit gender of previously biased words is easy to predict from their vectors alone.

The authors argue the real danger is not "party tricks" like gender-stereotypical analogies, but algorithmic discrimination: systems such as a resume classifier could learn to favor male candidates from stereotypical cues in biased data while remaining "oblivious" to gender, because such cues survive debiasing. The crux: the gender direction provides a way to measure gender association but does not determine it; methods targeting it merely hide the bias. The popular definitions for quantifying and removing bias are insufficient, and other aspects of bias must be considered.

### Figures (p. 611–612)

*Image 1 (p. 611):* — This is a scatter plot labeled "Original" at the top left. It shows two distinct clusters of data points: a purple cluster on the left side and a cyan cluster on the right side. The horizontal axis displays numerical values from -40 to 60, and the vertical axis displays numerical values from -40 to 40.

*Image 2 (p. 612):* — This is a figure containing four scatter plots arranged in a two-by-two grid. The two plots in the top row are labeled "Original" and the two in the bottom row are labeled "Debiased". Each plot shows many small teal dots, with several dots annotated by legible words such as "warrior", "skipper", "captain", "nurse", "nanny", "coach", "colonel", and "inventor". The vertical axes of all four plots are marked from 0 to 100, while the horizontal axes of the left plots run from -0.2 to 0.2 and those of the right plots from -0.15 to 0.15. Caption text along the bottom edge is partially cut off and therefore not legible. _(Lettering in the image, read by the image model, not confirmed: "Debiased", "warrior", "skipper", "captain", "nurse", "nanny", "coach", "colonel", "inventor")_

<!-- quelle: Lipstick on a Pig: Debiasing Methods Cover up Systematic Gender Biases in Word Embeddings But do not Remove Them (p. 609–613) -->

## LITERATUR

<!-- quelle: References (p. 613–614) -->

- Tolga Bolukbasi, Kai-Wei Chang, James Zou, Venkatesh Saligrama, and Adam Kalai. 2016a. Man is to computer programmer as woman is to homemaker? debiasing word embeddings. arXiv:1607.06520 .
- Tolga Bolukbasi, Kai-Wei Chang, James Y Zou, Venkatesh Saligrama, and Adam T Kalai. 2016b. Man is to computer programmer as woman is to homemaker? debiasing word embeddings. In Advances in Neural Information Processing Systems .
- Aylin Caliskan, Joanna J Bryson, and Arvind Narayanan. 2017. Semantics derived automatically from language corpora contain human-like biases. Science , 356(6334):183-186.
- Nikhil Garg, Londa Schiebinger, Dan Jurafsky, and James Zou. 2018. Word embeddings quantify 100 years of gender and ethnic stereotypes. Proceedings of the National Academy of Sciences , 115(16):E3635-E3644.
- Laurens van der Maaten and Geoffrey Hinton. 2008. Visualizing data using t-sne. Journal of machine learning research , 9(Nov):2579-2605.
- Tomas Mikolov, Kai Chen, Greg Corrado, and Jeffrey Dean. 2013. Efficient estimation of word representations in vector space. arXiv preprint arXiv:1301.3781 .
- Jeffrey Pennington, Richard Socher, and Christopher D Manning. 2014. Glove: Global vectors for word representation. In Proceedings of EMNLP .
- Brian Hu Zhang, Blake Lemoine, and Margaret Mitchell. 2018. Mitigating unwanted biases with adversarial learning. In Proceedings of the 2018 AAAI/ACM Conference on AI, Ethics, and Society .
- Jieyu Zhao, Yichao Zhou, Zeyu Li, Wei Wang, and Kai-Wei Chang. 2018. Learning gender-neutral word embeddings. In Proceedings of EMNLP , pages 4847-4853.

## GLOSSAR

- **Gender direction** — the vector difference he − she; the established metric of a word's gender bias, defined as the word's projection on this direction (for HARD-DEBIASED, chosen as the top principal component of ten gender-pair difference vectors).
- **HARD-DEBIASED** — the post-processing debiasing method of Bolukbasi et al. (2016b), which zeroes gender projections of non-gendered words and equalizes their distances to gendered pairs.
- **GN-GLOVE** — the gender-neutral GloVe of Zhao et al. (2018), trained from scratch to concentrate gender information in the last vector coordinate.
- **Bias-by-neighbours** — the authors' new bias measure—the percentage of male/female socially-biased words among the k nearest neighbors of a target word.
- **Indirect bias** — the term used by Bolukbasi et al. (2016a) for residual bias between semantically related words after debiasing, which they treated as a nuance without quantifying it.
- **WEAT (Word Embedding Association Test)** — the permutation test of Caliskan et al. (2017) estimating whether target word sets associate with attribute sets more than chance.
- **Implicit gender** — the social-stereotype gender association of words that are in principle gender-neutral (e.g. nurse, receptionist, captain), which persists in debiased embeddings.
