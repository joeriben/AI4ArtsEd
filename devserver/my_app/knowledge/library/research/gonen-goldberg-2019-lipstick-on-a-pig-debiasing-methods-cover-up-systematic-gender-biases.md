---
id: gonen-goldberg-2019-lipstick-on-a-pig-debiasing-methods-cover-up-systematic-gender-biases
titel: "Lipstick on a Pig: Debiasing Methods Cover up Systematic Gender Biases in Word Embeddings But do not Remove Them"
autor: "Hila Gonen, Yoav Goldberg"
jahr: 2019
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, bias]
lizenz: CC BY 4.0 (ACL Anthology) - original not redistributed; this file is a condensation produced on this platform
url: "https://doi.org/10.18653/v1/N19-1061"
status: published
analyzed_at: "2026-07-31T12:08:39.265792+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Lipstick on a Pig: Debiasing Methods Cover up Systematic Gender Biases in Word Embeddings But do not Remove Them

## PROFIL

Hila Gonen and Yoav Goldberg argue that existing debiasing methods for word embeddings, such as HARD-DEBIASED and GN-GLOVE, merely hide systematic gender biases rather than removing them, as these biases persist in the spatial geometry of "gender-neutralized" words and remain recoverable. The text sets itself against the assumption, established by Bolukbasi et al. and Zhao et al., that reducing a word's projection on the "gender direction" (he - she) is sufficient to achieve gender-neutral modeling. By demonstrating that stereotypical associations survive post-debiasing through proximity to socially-marked words, the authors expose the superficiality of targeting only explicit gender markers. For arts education, this indicates that computational language tools marketed as unbiased may still perpetuate implicit social stereotypes, requiring critical scrutiny when integrated into pedagogical or curricular technologies.

## WISSEN

### Problem Framing and Thesis

Word embeddings trained on text corpora reflect pervasive gender bias. Existing debiasing methods target bias defined as projection on the *gender direction* (→he − →she), substantially reducing it. We argue this removal is superficial: bias is hidden, not eliminated. Gender-bias information persists in the geometry of "gender-neutralized" words and remains recoverable. Experiments on two debiasing methods support this, indicating current techniques are insufficient for gender-neutral modeling.

<!-- quelle: Problem Framing and Thesis -->

### Gender Bias Definitions and Existing Debiasing Methods

Bolukbasi et al. (2016b) define gender bias as a word's projection on the **gender direction** (he − she), and debias by zeroing this projection for non-gendered words, plus equalizing neutral words' distance to gendered pairs. Zhao et al. (2018) debias during training by concentrating gender information in one vector coordinate. Both rely on the same definition, which the authors argue is an indicator but not the complete manifestation of bias.

<!-- quelle: Conceptual Clarification: Gender Bias Definitions and Existing Debiasing Methods -->

### Remaining Bias After Debiasing

Existing debiasing methods reduce projection on a *gender direction* without harming standard task performance, but rely on a narrow bias definition. The authors argue bias is more systematic: reducing gender-direction projection merely hides it, as stereotypical associations persist among gender-neutral words. Since most word pairs retain their similarity, the embeddings' spatial geometry stays largely unchanged, leaving bias intact.

<!-- quelle: Thesis Elaboration: Remaining Bias After Debiasing -->

### Experimental Setup

To quantify hidden bias, HARD-DEBIASED and GN-GLOVE embeddings are compared against biased counterparts. Using a reduced vocabulary of the 50,000 most frequent words/phrases, we remove words with upper-case letters, digits, punctuation, words longer than 20 characters, and inherently gendered words (e.g. mother, father, queen). Bias is computed via projection on the gender direction (he - she). Association is measured using WEAT.

<!-- quelle: Experimental Setup -->

### Biased Words Cluster Together After Debiasing

The 1,000 most gender-biased words (500 male, 500 female) were clustered via k-means into two clusters. Post-debiasing, clusters still align with gender: HARD-DEBIASED accuracy drops only from 99.9% to 92.5%; GN-GLOVE from 100% to 85.6%. tSNE projections confirm the persistent separation, indicating much bias information remains embedded after debiasing.

<!-- quelle: Experiment 1: Biased Words Cluster Together After Debiasing -->

### Bias-by-Neighbours Correlation and Professions Analysis

Bias persists post-debiasing not through explicit gender markers but through proximity to socially-marked words (e.g., 'nurse' near 'receptionist', 'caregiver'). This motivates a new measure: the percentage of male/female socially-biased words among the k nearest neighbors of a target word. This bias-by-neighbours measure correlates significantly with original bias (Pearson 0.686 for HARD-DEBIASED, 0.736 for GN-GLOVE; professions: 0.606 and 0.792 respectively; all p-values ≈ 0).

<!-- quelle: Experiment 2: Bias-by-Neighbours Correlation and Professions Analysis -->

### Association Tests and Classification of Debiased Words

Three gender-association experiments (Caliskan et al. 2017) are replicated using full vocabulary and female/male names instead of inherently gendered words. All p-values remain significant for both HARD-DEBIASED (0, 0.00016, 0.0467) and GN-GLOVE (7.7×10⁻⁵, 0.00031, 0.0064), indicating residual bias. An SVM classifier trained on the 5,000 most biased words still predicts gender at 88.88% (HARD-DEBIASED) and 96.53% (GN-GLOVE), versus ~98% non-debiased—debiasing reduces but does not eliminate classifiable gender information.

<!-- quelle: Experiments 3 and 4: Association Tests and Classification of Debiased Words -->

### Superficiality of Gender-Direction Debiasing

Debiasing methods targeting the *gender direction* are superficial, leaving deeper stereotype bias intact. Algorithmic discrimination (e.g., resume classifiers) exploits these implicit associations. The *gender-direction* measures but does not determine gender-association; popular bias-removal definitions are insufficient. Specifically:
- Words with strong previous gender bias (with the same direction) are easy to cluster together.
- Words that receive implicit gender from social stereotypes (e.g. receptionist, hairdresser, captain) still tend to group with other implicit-gender words of the same gender, similar as for non-debiased word embeddings.
- The implicit gender of words with prevalent previous bias is easy to predict based on their vectors alone.

<!-- quelle: Discussion and Conclusion -->

## GLOSSAR

- **gender direction** — A vector estimated by averaging differences between female and male word pairs in a predefined set, used to identify and reduce gender bias in embeddings.
- **gender-neutralized** — Words whose embeddings have been post-processed to reduce or eliminate their projection onto the gender direction, yet which still retain recoverable gender-bias information in their relative geometry.
- **indirect bias** — Bias persisting in word embeddings through similarities between gender-neutral words that carry stereotypical gender associations, remaining after direct gender-direction debiasing.
- **HARD-DEBIASED** — Word embeddings from Bolukbasi et al. (2016b) used as a baseline for comparison against their pre-debiased state.
- **GN-GLOVE** — Gender-neutral GloVe embeddings from Zhao et al. (2018) compared against standard GloVe trained on the same corpus.
- **WEAT** — Word Embedding Association Test, a permutation test estimating the probability that target words produce equal or greater similarities to attribute sets.
- **bias-by-neighbours** — A bias measure defined as the percentage of male/female socially-biased words among the k nearest neighbors of a target word in the embedding space.
- **implicit gender** — Gender association derived from social stereotypes rather than explicit gender terms.
