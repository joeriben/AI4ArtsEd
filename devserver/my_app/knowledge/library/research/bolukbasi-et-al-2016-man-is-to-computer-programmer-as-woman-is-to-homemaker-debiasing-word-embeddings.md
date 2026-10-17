---
id: bolukbasi-et-al-2016-man-is-to-computer-programmer-as-woman-is-to-homemaker-debiasing-word-embeddings
titel: Man is to Computer Programmer as Woman is to Homemaker? Debiasing Word Embeddings
autor: "Tolga Bolukbasi, Kai-Wei Chang, James Zou, Venkatesh Saligrama, Adam Kalai"
jahr: 2016
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, bias]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/1607.06520"
status: published
analyzed_at: "2026-07-31T09:30:18.754429+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Man is to Computer Programmer as Woman is to Homemaker? Debiasing Word Embeddings

## PROFIL

The text argues that word embedding frameworks quantitatively encode and amplify gender stereotypes present in training data, setting itself against the blind application of machine learning that ignores these embedded biases. By demonstrating that gender neutral words are linearly separable from gender definition words within a specific gender subspace, the authors develop algorithms to debias embeddings by quantifying and mitigating both direct and indirect gender biases. This geometric intervention preserves the embedding's utility for analogy tasks while neutralizing stereotypical associations, offering arts education a critical framework for analyzing and correcting algorithmic representation in digital media practices.

## WISSEN

### Problem Framing and Thesis: Gender Bias in Word Embeddings

Blind application of machine learning risks amplifying biases already present in training data. Word embedding—a framework representing text as vectors used across NLP tasks—exemplifies this danger: embeddings trained on Google News articles exhibit female/male gender stereotypes to a disturbing extent, and their widespread use tends to amplify rather than mitigate these biases.

The argument proceeds in two geometric steps. First, gender bias is captured by a specific direction in the word embedding. Second, gender neutral words are linearly separable from gender definition words. These two properties ground a methodology for modifying embeddings to remove gender stereotypes (e.g., the association between *receptionist* and *female*) while preserving desired associations (e.g., between *queen* and *female*).

The authors define metrics to quantify both **direct** and **indirect** gender biases in embeddings, and develop algorithms to debias them. Validation uses both crowd-worker evaluation and standard benchmarks, demonstrating that the algorithms significantly reduce gender bias while preserving useful properties such as clustering related concepts and solving analogy tasks. The resulting embeddings can be deployed in applications without amplifying gender bias.

<!-- quelle: Problem Framing and Thesis -->

### Bias in Word Embeddings and Amplification Risk

Word embeddings represent words as vectors where semantic similarity and relational analogies emerge from co-occurrence in text corpora. The same vector arithmetic that solves *man:king::woman:queen* also produces *man:computer programmer::woman:homemaker*, revealing gender stereotypes embedded in training data. The primary object of study is **w2vNEWS**, trained on Google News; biases persist across other publicly available embeddings.

The central thesis: embeddings quantitatively encode gender stereotypes and, because they serve as features in downstream applications, risk *amplifying* bias. A web-search example illustrates amplification: given identical student pages differing only in names, embeddings rank *John* higher than *Mary* for a CS query, widening the gender gap.

Naïve word-count approaches fail due to **reporting bias** (e.g., *male nurse* outnumbers *female nurse*), but embeddings use second-order methods that can circumvent this.

To quantify bias, a distinction is drawn between *gender specific words* (associated by definition, e.g., *brother*) and *gender neutral words*. Gender-specific words define a **gender subspace**; debiasing removes bias only from neutral words while respecting definitions.

**Direct bias** = association between a gender-neutral word and a gender pair. **Indirect bias** = associations between gender-neutral words arising from gender (e.g., *receptionist* closer to *softball* than *football*). Geometry can determine how much of an association is gender-based versus legitimate.

Crowd workers confirmed biases align with social stereotypes. Debiasing leverages a low-dimensional gender subspace to reduce bias while preserving embedding utility.

Extreme she occupations: homemaker, nurse, receptionist, librarian, socialite, hairdresser, nanny, bookkeeper, stylist, housekeeper, interior designer, guidance counselor.

Extreme he occupations: maestro, skipper, protege, philosopher, captain, architect, financier, warrior, broadcaster, magician, fighter pilot, boss.

Gender stereotype she-he analogies: sewing-carpentry, register_nurse-physician, housewife-shopkeeper, nurse-surgeon, interior_designer-architect, softball-baseball, blond-burly, feminism-conservatism, cosmetics-pharmaceuticals, giggle-chuckle, vocalist-guitarist, petite-lanky, sassy-snappy, diva-superstar, charming-affable, volleyball-football, cupcakes-pizzas, hairdresser-barber.

Gender appropriate she-he analogies: queen-king, sister-brother, mother-father, waitress-waiter, ovarian_cancer-prostate_cancer, convent-monastery.

<!-- quelle: Introduction: Bias in Word Embeddings and Amplification Risk -->

### Related Work on Bias in Language and Algorithms

Related work splits into bias in language and bias in algorithms. The distinction between **direct** and **indirect bias** (Pedreshi et al.) is foundational: direct discrimination uses sensitive features explicitly; indirect discrimination uses non-sensitive correlates that nonetheless produce disproportionate treatment.

Gender bias in English manifests in implicit associations (IATs) linking female terms to liberal arts/family and male terms to science/careers; in word morphology where default forms (actor) encode the dominant class and female forms (actress) are marked; and in lexical imbalance—fewer words for males but far more words sexualizing females. **Benevolent sexism** (Glick & Fiske) shows that even positive associations (helpful, attractive) harm women by reducing their association with words like professional. Stereotypes, being consistent, are easier to study; **complimentary stereotypes** assign each gender offsetting strengths, and compensatory stereotypes justify the status quo. Online contexts confirm these patterns: Wikipedia articles about women disproportionately emphasize gender, husbands, and husbands' jobs; words like husband predict female subjects, baseball predicts male.

Algorithmic bias appears in ad delivery, repeat-offender prediction, and dialect-based exclusion from NLP tools trained on standard datasets. Schmidt independently identified gender bias in word embeddings, proposing debiasing by removing one gender dimension per pair—similar but simpler than our approach. Fair-classification work (Feldman et al.) distinguishes modifying data from modifying the algorithm; our approach resembles the former. However, prior fairness work assumes supervised classification with identifiable individuals and a distinguished sensitive feature. Word embeddings lack clear individuals or a predefined classification task, yet direct and indirect bias still arise, making existing fairness frameworks difficult to apply.

<!-- quelle: Related Work on Bias in Language and Algorithms -->

### Preliminaries and Experimental Setup

An embedding assigns a unit vector w⃗ ∈ R^d (‖w⃗‖ = 1) to each word w ∈ W. Two subsets are assumed given: **gender neutral words** N ⊂ W (e.g., *flight attendant*, *shoes*), not specific to any gender, and **F-M gender pairs** P ⊂ W × W (e.g., *she-he*, *mother-father*), whose definitions differ mainly in gender. Section 7 addresses discovering N and P within the embedding; until then they are taken as given. Similarity is measured by inner product; since words are unit-normalized, cos(w⃗₁, w⃗₂) = w⃗₁ · w⃗₂. The authors note they "abuse terminology" by using "word" and "embedding of a word" interchangeably.

The default embedding is w2vNEWS: a d = 300-dimensional word2vec embedding pre-trained on Google News, normalized to unit length. From the 50,000 most frequent words, only lower-case words and phrases with fewer than 20 lower-case characters were retained; words with upper-case letters, digits, or punctuation were discarded. After filtering, 26,377 words remained. Gender stereotypes are later shown to persist in other embedding datasets.

Crowd experiments ran on Amazon Mechanical Turk, restricted to U.S.-based workers for homogeneity and reproducibility. Two experiment types mirror information-retrieval precision/recall evaluation: (1) soliciting words from the crowd to test whether embedding biases contain crowd biases, and (2) soliciting ratings on embedding-generated words or analogies to test whether crowd biases contain embedding biases. "Majority of 10 crowd judgments" means annotations by 5 or more independent workers.

The authors deliberately solicit ratings of **stereotypes** rather than bias: gender associations vary by culture and person, stereotypes possess greater consistency than biases, and people may feel more comfortable rating cultural stereotypes than discussing personal gender biases.

<!-- quelle: Preliminaries and Experimental Setup -->

### Gender Stereotypes in Word Embeddings

Two methods assess embedding bias: (1) occupation-word proximity to gender terms and (2) generated analogies judged by humans. Projecting occupation words onto the *she-he* direction in w2vNEWS correlates with crowdworker stereotypicality ratings (Spearman ρ = 0.51). The same projection across a GloVe web-crawl embedding yields highly consistent results (ρ = 0.81), establishing that gender stereotypes are prevalent across embeddings and not an artifact of a particular corpus or methodology. Occupation words were chosen for interpretability; *she* and *he* were chosen over *woman*/*man* for frequency and fewer alternative senses.

The analogy task is modified: given a seed pair (a, b) = (she, he), generate word pairs (x, y) scored by parallelism to the seed direction plus semantic coherence (threshold δ = 1). U.S.-based crowdworkers judged each analogy on whether it makes sense and whether it reflects a gender stereotype. Of 150 analogies, 72 were rated gender-appropriate and 29 stereotypical by five or more workers.

Beyond direct bias, *indirect gender bias* is tested by projecting occupation words onto directions defined by gender-neutral word pairs (e.g., softball–football). Bookkeeper and receptionist cluster near softball, plausibly reflecting indirect female associations. However, some male-biased word pairs have legitimate non-gender associations (footballer–football), motivating the rigorous metric developed in Section 5.

<!-- quelle: Empirical Demonstration of Gender Stereotypes in Embeddings -->

### Geometry of Gender: Identifying Gender Subspace and Bias Metrics

Because individual word pairs are noisy due to polysemy (e.g., *man* as exclamation, verb, or gendered noun), bias is estimated by aggregating across multiple paired comparisons. Ten gender pair difference vectors are subjected to PCA; the first principal component explains significantly more variance than expected from random sampling, and is hypothesized as the **gender subspace** (unit vector *g*). Crowd-sourced validation on Amazon Mechanical Turk confirms these pairs capture intuitive gender: definitional and stereotypical word lists (50 male, 50 female each) are classified at 80–93% accuracy by individual pairs.

**DirectBias** measures how far gender-neutral words *N* project onto *g*: DirectBias = (1/|N|) Σ |cos(w, g)|^c, where *c* controls strictness (c=0 is binary, c=1 gradual). For 327 occupations in w2vNEWS, DirectBias₁ = 0.08, confirming substantial gender alignment.

**Indirect bias** persists even after removing explicit gender words. Each vector *w* is decomposed as *w = w_g + w_⊥*, where *w_g = (w·g)g*. The metric β(w,v) = (w·v − w_⊥·v_⊥ / (‖w_⊥‖₂‖v_⊥‖₂)) / (w·v) quantifies the fractional change in similarity when the gender subspace is projected out. Case study: *receptionist*, *waitress*, *homemaker* are closer to *softball* than *football*, with β values of 67%, 35%, 38% respectively, indicating their similarity to *softball* is largely explained by gender. Similarly, *businessman* (β=31%) and *maestro* (β=42%) align with *football* via indirect gender bias.

<!-- quelle: Geometry of Gender: Identifying Gender Subspace and Bias Metrics -->

### Debiasing Algorithms and Gender-Neutral Word Classification

Debiasing is defined over sets of words (not just pairs) for generality across bias types. A set of words to neutralize is assumed, either from a list or from the embedding; in practice it is easier to enumerate the smaller set of gender-specific words and take the complement.

**Step 1 — Identify gender subspace:** A subspace *B* (spanned by *k* orthogonal unit vectors) capturing the bias is extracted via SVD of the covariance of defining-set means.

**Step 2a — Hard de-biasing (Neutralize and Equalize):** Neutralize projects gender-neutral words to zero in *B*. Equalize forces each equality set's vectors to share the same orthogonal-to-*B* component (their average) and a centered, unit-length component within *B*. Centering is essential: without it, *male* and *female* would collapse to identical embeddings, losing analogies like *father:male :: mother:female*. The motivation for centering is that both *male* and *female* project positively onto the gender direction (female more so), plausibly due to corpus frequencies such as "male nurse" or "she was assaulted by the male."

Equalize's disadvantage: it erases distinctions valuable for certain applications — e.g., *to grandfather a regulation* should retain higher probability than *to grandmother a regulation*.

**Observation 1:** After Steps 1 and 2a, any neutral word is equidistant to all words within each equality set, and PairBias = 0.

**Step 2b — Soft bias correction:** A linear transformation *T* preserves pairwise inner products while minimizing projection of neutral words onto *B*, balanced by parameter λ (λ large recovers Step 2a exactly; experiment uses λ = 0.2). Solved as a semi-definite program.

**Determining gender-neutral words (Section 7):** A base list *S₀* of 218 gender-specific words is derived from dictionary definitions (subjective; ideally application-customized). A linear SVM (C = 1.0) generalizes this to the full 3-million-word embedding, yielding *S* of 6,449 gender-specific words. Stratified 10-fold cross-validation gives F-score .627 ± .102; balanced accuracy 95.12% ± 1.46% with 95% confidence.

<!-- quelle: Debiasing Algorithms and Gender-Neutral Word Classification -->

### Debiasing Results and Evaluation

The evaluation tests whether debiasing algorithms preserve embedding utility while reducing both direct and indirect gender biases.

**Utility preservation.** Standard benchmarks (RG, WS, MSR-analogy) show no degradation after debiasing: hard-debiased and soft-debiased embeddings score nearly identically to the original w2vNEWS on coherence and analogy-solving (Table 1).

**Direct bias.** Using the she–he analogy generation task with crowd-worker evaluation, stereotypical analogies dropped from 19% (top 150) in the original embedding to 6% after hard-debiasing. The example *he:doctor :: she:X* yields X=nurse in the original but X=physician after hard-debiasing, while gender-appropriate analogies such as *she:ovarian cancer :: he:prostate cancer* are preserved. The count of appropriate analogies remains similar, confirming quality is retained. Soft-debiasing was less effective.

**Indirect bias.** Without ground truth for indirect effects, evaluation is qualitative. In the softball–football direction, after strict debiasing the most extreme words near softball become *infielder*, *major leaguer*, and *pitcher*—semantically relevant and non-gendered—while stereotypic associations (*receptionist*, *waitress*, *homemaker*) and male-biased words (*businessman*) drop in rank. Words whose similarity stems from actual function (*pitcher*–softball, *footballer*–football) remain essentially unchanged, confirming the algorithm targets gender contribution rather than semantic content.

<!-- quelle: Debiasing Results and Evaluation -->

### Discussion: Debiasing Efficacy, Counter-Arguments, and Future Directions

A single gender direction *g* largely captures gender in word embeddings, enabling quantification of both direct associations between gender-neutral words and gender, and *indirect inequality*. Projecting gender-neutral words onto *g* measures their degree of female- or male-bias.

The **hard-debiasing** algorithm removes gender associations from gender-neutral words (e.g., *nurse* becomes equally male and female along *g*), while retaining the gender component for gender-specific words to preserve analogies such as *she:grandmother :: he:grandfather*. Gender-specific words carry biases beyond *g*: *grandmother* and *grandfather* are both closer to *wisdom* than *gal* and *guy* — not a gender difference — yet *babysit* is disproportionately closer to *grandmother*, a bias specific to that pair. Equating the pair outside gender and stripping *g* from *babysit* resolves this. Empirical evaluation shows significant reduction of both direct and indirect gender bias while preserving embedding utility. A **soft-debiasing** variant balances bias reduction against preserving original distances.

Against the view that embeddings merely reflect societal bias and should not be altered, the authors hold that debiased embeddings prevent machine-learning systems from amplifying stereotypes and may contribute, however modestly, to reducing societal bias. Against the claim that biased embeddings capture useful statistics in specific applications, they recommend erring toward neutrality.

Future work: the same corpus (*w2vNEWS*) exhibits strong racial stereotypes (e.g., occupations clustering toward *whites* vs. *minorities*); quantifying and removing racial, ethnic, and cultural biases remains open. Extending the approach to languages with grammatical gender is also proposed.

<!-- quelle: Discussion, Outlook, and References -->

## GLOSSAR

- **word embedding** — A framework representing text data as vectors, widely used in machine learning and NLP tasks.
- **direct gender bias** — Gender bias explicitly captured along a direction in the word embedding space.
- **indirect gender bias** — Bias affecting the relative geometry between gender-neutral words themselves, where associations between neutral words may indirectly reflect gender stereotypes.
- **direct bias** — Association between a gender-neutral word and a clear gender pair in the embedding geometry.
- **indirect bias** — Discrimination arising from non-sensitive correlates that nonetheless produce disproportionate treatment, as distinguished from direct use of sensitive features.
- **gender subspace** — The principal component direction g, learned from PCA on gender pair difference vectors, hypothesized to capture the gender dimension of the embedding.
- **benevolent sexism** — Perception of women through subjectively positive traits that nonetheless causes discrimination by reducing their association with other desirable attributes.
- **complimentary stereotypes** — Stereotypes assigning each gender perceived strengths that offset its weaknesses and complement the other gender, used to justify the status quo.
- **gender neutral words** — Subset N ⊂ W of words not specific to any gender, such as 'flight attendant' or 'shoes'.
- **F-M gender pairs** — Subset P ⊂ W × W of word pairs whose definitions differ mainly in gender, such as she-he or mother-father.
