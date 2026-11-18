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
checks: passed
review: passed
analyzed_at: "2026-11-15T11:06:54.815058+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: gedruckt
---

# Man is to Computer Programmer as Woman is to Homemaker? Debiasing Word Embeddings

## PROFIL

The article "Man is to Computer Programmer as Woman is to Homemaker? Debiasing Word Embeddings" was written by Tolga Bolukbasi, Kai-Wei Chang, James Zou, Venkatesh Saligrama and Adam Kalai, affiliated with Boston University and Microsoft Research New England, and is addressed to the machine learning and natural language processing community. Its subject is the pronounced female/male gender stereotypes contained in word embeddings—vector representations of words used as basic features in applications such as web search, document ranking, sentiment analysis and question retrieval—and its claim is that these stereotypes can be quantified and removed while preserving the embeddings' useful properties, so that computer systems at least do not amplify societal bias. The paper first demonstrates the bias in the w2vNEWS word2vec embedding trained on Google News (occupational stereotypes, stereotyped analogies, indirect bias between gender-neutral words), then identifies a gender subspace through principal component analysis of gender-pair difference vectors, defines metrics of direct and indirect bias, and proposes two debiasing algorithms: hard debiasing (Neutralize and Equalize) and soft bias correction via a semidefinite program. It further describes how gender-neutral words are determined (a Wordnet-derived base set extended by a linear SVM), reports debiasing results with crowd judgments from Amazon Mechanical Turk and standard benchmarks showing no utility degradation, and closes with a discussion recommending erring "on the side of neutrality," notes on racial stereotypes in the same embedding, and appendices covering analogy-generation methods, the SDP solution, questionnaires and full-embedding results. It situates itself against two literatures—studies of gender bias and stereotype in English (implicit associations, marked morphology, Glick and Fiske's "benevolent sexism," Wikipedia studies) and work on algorithmic bias and fair classification (Barocas and Selbst; Feldman et al.; Pedreshi et al.)—and distinguishes its approach from Schmidt's simpler proposal of removing multiple gender dimensions entirely. For arts education, the article is usable in media literacy, digital culture and interdisciplinary teaching on representation and stereotype, wherever the analysis of implicit gender associations in language and the ethics of algorithmic systems are at issue.

## WISSEN

### Purpose and Thesis (pp. 1–4)

This paper by Tolga Bolukbasi, Kai-Wei Chang, James Zou, Venkatesh Saligrama and Adam Kalai (Boston University and Microsoft Research New England) demonstrates that word embeddings—vector representations of words used widely in machine learning and natural language processing—contain pronounced female/male gender stereotypes, and proposes methods to quantify and remove ("debias") these stereotypes while preserving the embeddings' useful properties. The authors show that even the popular word2vec embedding trained on Google News articles (w2vNEWS, 3 million English words/terms in 300 dimensions) exhibits disturbing gender bias: it answers the analogy "man is to computer programmer as woman is to x" with x = homemaker, and outputs that a father is to a doctor as a mother is to a nurse. Because embeddings are used as basic features in applications such as web search, document ranking, sentiment analysis and question retrieval, they risk not only reflecting but amplifying societal bias. The authors illustrate amplification with a hypothetical web search: for the query "cmu computer science phd student," among 127 nearly identical student pages differing only in names, the embedding would rank John's page above Mary's. The paper focuses on Female-Male (F-M) gender bias, though the approach may apply to other biases (pp. 1–4).

The authors note that simple word co-occurrence counting is misleading due to reporting bias (e.g., "male nurse" is more frequent than "female nurse"), whereas embeddings, trained with second-order methods on large data, can circumvent this: the vector for nurse is in fact closer to female than male. Embeddings may thus serve as a means of extracting implicit gender associations from text, analogous to Implicit Association Tests for people (p. 3).

### Related Work (pp. 4–6)

The paper situates itself in two literatures: (1) gender bias and stereotype in English—studies of implicit associations linking female terms with liberal arts and family and male terms with science and careers; marked vs. unmarked word morphology (actor/actress); Glick and Fiske's "benevolent sexism"; complementary and compensatory stereotypes; and Wikipedia studies showing articles about women emphasize husbands and gender; and (2) bias within algorithms—racial and gender bias in online ads, repeat-offender prediction, dialect differences in social media, and prior work on "fair" classification (Barocas and Selbst; Feldman et al.; Pedreshi et al.'s direct vs. indirect discrimination). The authors note independent work by Schmidt, who proposed removing multiple gender dimensions entirely, a simpler approach than theirs. Unlike supervised fair classification, embeddings present no clear individuals or classification task (pp. 4–6).

### Preliminaries (p. 6)

An embedding assigns each word w a unit vector in R^d; similarity is measured by inner product (equivalently cosine, since vectors are normalized). The paper assumes a set of gender-neutral words N (e.g., flight attendant, shoes) and a set of F-M gender pairs P (e.g., she-he, mother-father). The primary embedding studied is w2vNEWS: the pre-trained Google News word2vec embedding, filtered to 26,377 lower-case words/phrases under 20 characters from the 50,000 most frequent words. Human experiments were run on Amazon Mechanical Turk with U.S.-based workers; "majority of 10 crowd judgments" means 5 or more independent workers. Because gender associations vary by culture and person, the authors ask about stereotypes rather than personal biases (p. 6).

### Gender Stereotypes in Word Embeddings (pp. 6–8)

Two exploratory methods are used:

1. **Occupational stereotypes.** The occupations closest to she in w2vNEWS include homemaker, nurse, receptionist, librarian, socialite, hairdresser, nanny, bookkeeper, stylist, housekeeper, interior designer, guidance counselor; closest to he are maestro, skipper, protege, philosopher, captain, architect, financier, warrior, broadcaster, magician, fighter pilot, boss (occupations like businesswoman, where gender is suggested by spelling, were excluded). Ten crowd-workers rated each occupation's stereotypicality on a 0–10 scale; the projection of occupations onto the she-he axis correlates strongly with these ratings (Spearman ρ = 0.51). Projecting occupations onto the she-he direction in both w2vNEWS and a GloVe web-crawl embedding gives highly consistent results (Spearman ρ = 0.81), showing the bias is not an artifact of one corpus or algorithm (pp. 6–7).

2. **Stereotyped analogies.** The authors modify the standard analogy task: given a seed pair (a, b) = (she, he), generate word pairs (x, y) such that "he is to x as she is to y" is a good analogy, scoring pairs by parallelism to the seed direction with a semantic-similarity threshold δ = 1 (angle ≤ π/3). Of 150 generated analogies, 72 were rated gender-appropriate by five or more of 10 workers, and 29 were rated as reflecting gender stereotypes. Stereotypic examples include sewing-carpentry, nurse-surgeon, interior designer-architect, blond-burly, feminism-conservatism, giggle-chuckle, sassy-snappy, volleyball-football, cupcakes-pizzas, hairdresser-barber; gender-appropriate examples include queen-king, sister-brother, mother-father, waitress-waiter, ovarian cancer-prostate cancer, convent-monastery (pp. 7–8).

3. **Indirect gender bias.** Projecting occupations onto the softball-football direction (both gender-neutral words) shows bookkeeper and receptionist much closer to softball, plausibly due to female associations with both—bias acting indirectly between gender-neutral words (p. 8).

### Geometry of Gender and Bias (pp. 8–11)

**Identifying the gender subspace.** Because language use is "messy" (polysemy, e.g., man as exclamation or verb), individual gender-pair difference vectors are not parallel. Ten gender pairs (she-he, her-his, woman-man, Mary-John, herself-himself, daughter-son, mother-father, gal-guy, girl-boy, female-male) were validated against crowd-solicited lists of definitionally gendered and stereotypically gendered words, achieving roughly 80–93% classification accuracy (e.g., she-he: 92% definitional, 89% stereotypical). Principal component analysis of the ten pair-difference vectors reveals a single direction explaining most variance (the first eigenvalue is significantly larger than the rest, unlike the gradual decrease seen with random unit vectors); the top principal component g is taken as the gender direction, though the methods generalize to higher-dimensional subspaces (pp. 8–9).

**Direct bias.** For gender-neutral words N and gender direction g, DirectBias is defined as the mean of |cos(w, g)|^c over N, where parameter c controls strictness (c = 0 is strict, c = 1 gradual). For the 327 occupation words in w2vNEWS, DirectBias₁ = 0.08, confirming substantial gender components in occupation words (pp. 9–10).

**Indirect bias.** Each word vector is decomposed as w = w_g + w_⊥, where w_g = (w·g)g is the gender contribution. The indirect bias metric β(w, v) measures how much the similarity between two words changes (as a fraction of the original inner product) when the gender subspace is projected out and vectors renormalized. Case study on the softball-football axis: receptionist's similarity to softball is 67% gender-explained, waitress 35%, homemaker 38%; businessman's similarity to football is 31% and maestro's 42% gender-explained, while pitcher (softball) and footballer (football) have only 2% and -1% gender contribution—their similarity is functional (pp. 10–11).

### Debiasing Algorithms (pp. 11–13)

The algorithms operate on sets of words for generality (applicable to racial or religious bias). Step 1, **Identify gender subspace**: given defining sets D₁,…,D_n, compute their means, and take the bias subspace B as the first k rows of the SVD of the matrix of centered means (pp. 11–12).

Step 2a, **Hard debiasing (Neutralize and Equalize)**: Neutralize re-embeds each gender-neutral word by zeroing its component in B and renormalizing to unit length. Equalize operates on equality sets (e.g., {grandmother, grandfather}, {guy, gal}): outside B, all words in a set are equated to their average; within B, they are centered (moved to mean 0) and scaled so each vector is unit length. Centering matters: both male and female happen to be positive in the gender direction (female more so), and centering balances them symmetrically—without it, the two would receive identical embeddings, losing analogies like father:male :: mother:female. After Steps 1 and 2a, any neutral word is equidistant to all words in each equality set, and PairBias = 0. The drawback of Equalize is that it removes valuable distinctions, e.g., a language model should prefer "grandfather a regulation" over "grandmother a regulation" (pp. 11–12).

Step 2b, **Soft bias correction**: a linear transformation T ∈ R^(d×d) is learned that preserves pairwise inner products of all word vectors while minimizing the projection of gender-neutral words onto the gender subspace, formalized as a semidefinite program with tuning parameter λ balancing the two objectives (λ = 0.2 in experiments; large λ corresponds to hard debiasing). The output is renormalized to unit length (pp. 12–13).

### Determining Gender-Neutral Words (p. 13)

Since gender-specific words are fewer, the authors enumerate those and take the complement. From dictionary (Wordnet) definitions, a base set S₀ of 218 gender-specific words was derived from w2vNEWS (e.g., he, she, mother, father, king, queen, waitress, businesswoman; words like beard, estrogen, rabbi were debated; clothing words were classified as neutral under a strict definition). A linear SVM (C = 1.0) trained on this set generalized to the full 3-million-word embedding, yielding S of 6,449 gender-specific words. Evaluation: F-score of .627 ± .102 (stratified 10-fold cross-validation); binary accuracy over 99% due to class imbalance; class-balanced accuracy 95.12% ± 1.46% with 95% confidence (p. 13).

### Debiasing Results (pp. 13–14)

**Direct bias.** On the original w2vNEWS, 19% of the top 150 she-he analogies were judged stereotypical by a majority of ten workers; after hard debiasing, only 6%. For "he to doctor is as she to X," the original embedding returns X = nurse, the hard-debiased embedding returns X = physician, while gender-appropriate analogies (she:ovarian cancer :: he:prostate cancer) are preserved. Soft debiasing was less effective. Standard benchmarks show no degradation: RG 62.3→62.4, WS 54.5→54.1, MSR analogy 57.0→57.0 (hard); 62.4/54.2/56.8 (soft) on the filtered vocabulary (pp. 13–14).

**Indirect bias.** After hard debiasing, the most extreme softball-end words become pitcher, infielder, major leaguer, bookkeeper, investigator—words relevant to softball without gender bias—while receptionist, waitress, homemaker, businessman and maestro drop off the extremes; pitcher and footballer are essentially unchanged because their similarity is functional (p. 14).

### Discussion (pp. 14–15)

A single direction largely captures gender, enabling quantification of both direct bias and indirect inequality. Debiasing changes gender-neutral words by removing their gender associations while retaining the gender component of gender-specific words, maintaining analogies like she:grandmother :: he:grandfather. The authors respond to the view that one should debias society rather than embeddings: since computer systems increasingly rely on embeddings, debiased embeddings can in a small way help reduce societal bias, and machine learning should at least not amplify bias. They recommend erring "on the side of neutrality" and using debiased embeddings wherever possible, while acknowledging that in specific applications biased statistics might be useful. The same w2vNEWS also exhibits racial stereotypes: projecting occupations onto the minorities-whites direction, the most extreme white-end occupations are parliamentarian, advocate, deputy, chancellor, legislator, lawyer; the minorities-end extremes are butler, footballer, socialite, crooner. Future work includes other bias types, other languages (especially those with grammatical gender), and the full-embedding results (Appendix H) confirm no utility degradation: RG 76.1→76.5, WS 70.0→69.7, analogy 71.2→71.2 (pp. 14–15, 24–25).

### Appendices (pp. 18–25)

Appendix A discusses analogy-generation methods: the parallelogram approach (equivalent to cosAdd) tends to return trivial or symmetric pairs; the authors' metric requires the pair direction to be parallel to the seed direction while keeping the two words semantically close (‖x−y‖ ≤ δ). Appendix B derives the SDP solution for soft debiasing via singular value decomposition of W, reducing the problem to an efficiently solvable 300×300 matrix. Appendix C details the 218-word gender-specific base list. Appendices D–F reproduce the Mechanical Turk questionnaires (soliciting gendered/stereotypical words and analogies; rating analogies as stereotypes, appropriate, or nonsensical). Appendix G lists the generated analogies with crowd ratings before and after hard debiasing (e.g., before: midwife:doctor 1 appropriate/10 biased, sewing:carpentry 2/9, nurse:surgeon 1/9; after: hostess:bartender 1/8, ballerina:dancer 0/7, with definitional pairs like mother:father 10/1 and queen:king 10/0). Appendix H reports debiasing results on the full w2vNEWS embedding (pp. 18–25).

### Figures (p. 7–15)

*Fig. 4 (p. 7):* Comparing the bias of two different embeddings-the w2vNEWS and the GloVe web-crawl embedding. In each embedding, the occupation words are projected onto the she -he direction. Each dot corresponds to one occupation word; the gender bias of occupations is highly consistent across embeddings (Spearman ρ = 0 . 81 ). — This is a scatter plot titled "Gender bias in occupation words across embeddings." The horizontal axis is labeled "she-he axis of w2vNEWS embedding" and the vertical axis is labeled "she-he axis of GloVe webcrawl embedding." The plot shows many small blue dots forming an upward-sloping distribution from the lower left to the upper right, with both axes marked with values ranging from -0.2 to 0.4. _(Lettering in the image, read by the image model, not confirmed: "Gender bias in occupation words across embeddings.", "she-he axis of w2vNEWS embedding", "she-he axis of GloVe webcrawl embedding.")_

*Fig. 6 (p. 10):* Left: the percentage of variance explained in the PCA of these vector differences (each difference normalized to be a unit vector). The top component explains significantly more variance than any other. Right: for comparison, the corresponding percentages for random unit vectors (figure created by averaging over 1,000 draws of ten random unit vectors in 300 dimensions). — The picture contains two side-by-side bar charts with solid blue bars on white backgrounds. In the left chart, the vertical axis is marked from 0 to 0.7 and the horizontal axis from 0 to 10; the first bar reaches about 0.6, and the later bars fall rapidly toward zero. In the right chart, the vertical axis is marked from 0.00 to 0.14 and the horizontal axis from 0 to 10; its ten bars decrease only gradually, from about 0.13 down to about 0.07. No words or titles are legible in the charts beyond the numeric axis tick labels.

*Fig. 8 (p. 15):* Number of stereotypical (Left) and appropriate (Right) analogies generated by wordembeddings before and after debiasing. — The image contains two side-by-side line charts. Both charts share the x-axis label "number of generated analogies"; the left chart's y-axis reads "number of stereotypic analogies" and the right chart's y-axis reads "number of appropriate analogies". A legend in the upper-left of each chart identifies three data series: "before" (blue dots), "hard-debiased" (green line), and "soft-debiased" (red triangles). _(Lettering in the image, read by the image model, not confirmed: "number of generated analogies", "number of stereotypic analogies", "number of appropriate analogies")_

<!-- quelle: Man is to Computer Programmer as Woman is to Homemaker? Debiasing Word Embeddings (p. 1–25) -->

## LITERATUR

<!-- quelle: References (p. 16–17) -->

- J. Angwin, J. Larson, S. Mattu, and L. Kirchner. Machine bias: There's software used across the country to predict future criminals. and it's biased against blacks., 2016.
- C. Aschwanden. The finkbeiner test: What matters in stories about women scientists? DoubleXScience , 2013.
- S. Barocas and A. D. Selbst. Big data's disparate impact. Available at SSRN 2477899 , 2014.
- E. Beigman and B. B. Klebanov. Learning with annotation noise. In ACL , 2009.
- A. J. Cuddy, E. B. Wolf, P. Glick, S. Crotty, J. Chong, and M. I. Norton. Men as cultural ideals: Cultural values moderate gender stereotype content. Journal of personality and social psychology , 109(4):622, 2015.
- A. Datta, M. C. Tschantz, and A. Datta. Automated experiments on ad privacy settings. Proceedings on Privacy Enhancing Technologies , 2015.
- C. Dwork, M. Hardt, T. Pitassi, O. Reingold, and R. Zemel. Fairness through awareness. In Innovations in Theoretical Computer Science Conference , 2012.
- J. Eisenstein, B. O'Connor, N. A. Smith, and E. P. Xing. Diffusion of lexical change in social media. PLoS ONE , pages 1-13, 2014.
- M. Faruqui, J. Dodge, S. K. Jauhar, C. Dyer, E. Hovy, and N. A. Smith. Retrofitting word vectors to semantic lexicons. In NAACL , 2015.
- M. Feldman, S. A. Friedler, J. Moeller, C. Scheidegger, and S. Venkatasubramanian. Certifying and removing disparate impact. In KDD , 2015.
- C. Fellbaum, editor. Wordnet: An Electronic Lexical Database . The MIT Press, Cambridge, MA, 1998.
- L. Finkelstein, E. Gabrilovich, Y. Matias, E. Rivlin, Z. Solan, G. Wolfman, and E. Ruppin. Placing search in context: The concept revisited. In WWW . ACM, 2001.
- P. Glick and S. T. Fiske. The ambivalent sexism inventory: Differentiating hostile and benevolent sexism. Journal of personality and social psychology , 70(3):491, 1996.
- J. Gordon and B. Van Durme. Reporting bias and knowledge extraction. Automated Knowledge Base Construction (AKBC) , 2013.
- A. G. Greenwald, D. E. McGhee, and J. L. Schwartz. Measuring individual differences in implicit cognition: the implicit association test. Journal of personality and social psychology , 74(6):1464, 1998.
- C. Hansen, M. Tosik, G. Goossen, C. Li, L. Bayeva, F. Berbain, and M. Rotaru. How to get the best word vectors for resume parsing. In SNN Adaptive Intelligence / Symposium: Machine Learning 2015, Nijmegen.
- J. Holmes and M. Meyerhoff. The handbook of language and gender , volume 25. John Wiley & Sons, 2008.
- O. İrsoy and C. Cardie. Deep recursive neural networks for compositionality in language. In NIPS . 2014.
- R. Jakobson, L. R. Waugh, and M. Monville-Burston. On language . Harvard Univ Pr, 1990.
- J. T. Jost and A. C. Kay. Exposure to benevolent sexism and complementary gender stereotypes: consequences for specific and diffuse forms of system justification. Journal of personality and social psychology , 88(3):498, 2005.
- M. Kay, C. Matuszek, and S. A. Munson. Unequal representation and gender stereotypes in image search results for occupations. In Human Factors in Computing Systems . ACM, 2015.
- T. Lei, H. Joshi, R. Barzilay, T. Jaakkola, A. M. Katerina Tymoshenko, and L. Marquez. Semi-supervised question retrieval with gated convolutions. In NAACL . 2016.
- O. Levy and Y. Goldberg. Linguistic regularities in sparse and explicit word representations. In CoNLL , 2014.
- T. Mikolov, K. Chen, G. Corrado, and J. Dean. Efficient estimation of word representations in vector space. In ICLR , 2013.
- T. Mikolov, I. Sutskever, K. Chen, G. S. Corrado, and J. Dean. Distributed representations of words and phrases and their compositionality. In NIPS .
- T. Mikolov, W.-t. Yih, and G. Zweig. Linguistic regularities in continuous space word representations. In HLT-NAACL , pages 746-751, 2013.
- E. Nalisnick, B. Mitra, N. Craswell, and R. Caruana. Improving document ranking with dual word embeddings. In www , April 2016.
- B. A. Nosek, M. Banaji, and A. G. Greenwald. Harvesting implicit group attitudes and beliefs from a demonstration web site. Group Dynamics: Theory, Research, and Practice , 6(1):101, 2002.
- D. Pedreshi, S. Ruggieri, and F. Turini. Discrimination-aware data mining. In Proceedings of the 14th ACM SIGKDD international conference on Knowledge discovery and data mining , pages 560-568. ACM, 2008.
- J. Pennington, R. Socher, and C. D. Manning. Glove: Global vectors for word representation. In EMNLP , 2014.
- K. Ross and C. Carter. Women and news: A long and winding road. Media, Culture & Society , 33(8):1148-1165, 2011.
- H. Rubenstein and J. B. Goodenough. Contextual correlates of synonymy. Communications of the ACM , 8(10):627-633, 1965.
- E. Sapir. Selected writings of Edward Sapir in language, culture and personality , volume 342. Univ of California Press, 1985.
- B. Schmidt. Rejecting the gender binary: a vector-space operation. http://bookworm.benschmidt. org/posts/2015-10-30-rejecting-the-gender-binary.html , 2015.
- J. P. Stanley. Paradigmatic woman: The prostitute. Papers in language variation , pages 303-321, 1977.
- L. Sweeney. Discrimination in online ad delivery. Queue , 11(3):10, 2013.
- A. Torralba and A. Efros. Unbiased look at dataset bias. In CVPR , 2012.
- P. D. Turney. Domain and function: A dual-space model of semantic relations and compositions. Journal of Artificial Intelligence Research , pages 533-585, 2012.
- C. Wagner, D. Garcia, M. Jadidi, and M. Strohmaier. It's a man's wikipedia? assessing gender inequality in an online encyclopedia. In Ninth International AAAI Conference on Web and Social Media , 2015.
- D. Yogatama, M. Faruqui, C. Dyer, and N. A. Smith. Learning word representations with hierarchical sparse coding. In ICML , 2015.
- I. Zliobaite. A survey on measuring indirect discrimination in machine learning. arXiv preprint arXiv:1511.00148 , 2015.

## GLOSSAR

- **Word embedding** — a framework representing each word (or phrase) as a d-dimensional unit vector, where semantically similar words have close vectors and vector differences capture relationships.
- **w2vNEWS** — the publicly available 300-dimensional word2vec embedding trained on Google News (3 million words/terms), the paper's primary object of study.
- **Gender-specific words** — words associated with a gender by definition (e.g., brother, businesswoman), as opposed to gender-neutral words.
- **Gender-neutral words** — words not specific to any gender by definition (e.g., flight attendant, nurse), the set N.
- **Direct bias** — the association between a gender-neutral word and a clear gender pair, measured as the mean of |cos(w, g)|^c over neutral words.
- **Indirect bias** — associations between gender-neutral words that arise through gender (e.g., receptionist closer to softball than football), measured by the metric β.
- **Gender subspace / gender direction g** — the low-dimensional subspace (top principal component of gender-pair difference vectors) that captures gender in the embedding.
- **β (indirect bias metric)** — the fraction of the similarity between two words attributable to gender, computed by projecting out the gender subspace and renormalizing.
- **Neutralize** — the debiasing step that zeroes gender-neutral words' components in the bias subspace.
- **Equalize** — the step that makes all words in an equality set (e.g., {grandmother, grandfather}) equidistant from any neutral word, by averaging outside the subspace and centering within it.
- **Soften (soft debiasing)** — an alternative that reduces differences between equality-set words while preserving original distances as much as possible, via a semidefinite program with parameter λ.
- **Hard debiasing** — the combined Neutralize-and-Equalize procedure that completely removes pair bias.
- **Equality set** — a set of words (typically a gender pair) that should be equidistant from all neutral words after debiasing.
- **Reporting bias** — the phenomenon (Gordon and Van Durme) that common assumptions are left unsaid in text, making raw co-occurrence counts misleading for extracting associations.
