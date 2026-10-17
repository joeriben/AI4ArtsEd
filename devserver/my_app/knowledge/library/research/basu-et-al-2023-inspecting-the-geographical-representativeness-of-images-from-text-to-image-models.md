---
id: basu-et-al-2023-inspecting-the-geographical-representativeness-of-images-from-text-to-image-models
titel: Inspecting the Geographical Representativeness of Images from Text-to-Image Models
autor: "Abhipsa Basu, R. Venkatesh Babu, Danish Pruthi"
jahr: 2023
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, bias, cultural_diversity]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2305.11080"
status: published
analyzed_at: "2026-07-31T11:40:42.567082+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Inspecting the Geographical Representativeness of Images from Text-to-Image Models

## PROFIL

The text argues that text-to-image models such as DALL·E 2 and Stable Diffusion exhibit poor Geographical Representativeness (GR), predominantly reflecting the surroundings of the United States for underspecified prompts, and that specifying country names yields insufficient improvements. It sets itself against the assumption that large-scale generative models trained on internet-mined data produce globally inclusive images, demonstrating that automated evaluation methods like CLIP text-image similarity are inadequate substitutes for direct user studies. By quantifying these representational and allocational harms through a crowdsourced study across 27 countries, the authors expose the systemic geographical biases embedded in generative technologies. For arts education, this research provides an empirical framework for understanding how generative tools perpetuate geographical biases, necessitating critical media literacy when incorporating these models into creative curricula.

## WISSEN

### Geographical Representativeness of Text-to-Image Models: Problem Framing and Thesis

Text-to-image models (DALL·E 2, Stable Diffusion) generate millions of images daily for art, marketing, and data augmentation. Because training data is mined from an internet that is itself biased and unequally accessible, these models risk amplifying societal biases. Prior bias work addresses race, gender, and occupation; **geographical representativeness** — whether generated images reflect the artifacts and surroundings of different nations rather than overrepresenting certain ones — remains overlooked. Underspecified prompts leave models to fill in details, increasing the risk of demographic overrepresentation. Beyond representational harms, biased generation causes **allocational harms** when generated images augment datasets and propagate existing biases.

The thesis: measure the degree to which text-to-image systems produce images reflecting participants' physical surroundings worldwide. A crowdsourced study (540 participants, 27 countries) presents 80 images of common nouns per user; half specify the participant's country in the prompt, half are deliberately underspecified. Users rate each image on a 5-point Likert scale for geographical representativeness, realism, and whether realism influenced their representativeness scores.

Key findings: underspecified generations most reflect the United States (3.35/5), India (3.23), Canada (2.82); 25 of 27 countries score below 3 for both models. Specifying country names raises average scores (DALL·E 2 +1.44, Stable Diffusion +0.75), yet many countries remain low. DALL·E 2 outperforms Stable Diffusion when country is specified; no significant difference exists in the underspecified case. Realism ratings correlate with representativeness scores.

Finally, two approaches to automating evaluation — CLIP text-image similarity and transferring DALL·E 2 user annotations to Stable Diffusion — prove inadequate, underscoring the necessity of direct user studies.

<!-- quelle: Problem Framing and Thesis -->

### Study Design and Methodology

The study measures **Geographical Representativeness (GR)** of image-generation models by presenting crowdworkers from different countries with model-generated images of common nouns and asking them to rate (1–5) how well the images reflect their surroundings. GR of model *m* for country *c* is the average rating from that country's participants across a noun set *N* using prompt set *P*. **Realism** R(*c,m,p*) is the average realism rating from country *c* for model *m* with prompt *p*. The authors explicitly delimit scope: the focus is solely on *measuring* representativeness for country-specified and unspecified prompts, not on improving prompting or model inclusivity.

Four research questions guide the study:
- **RQ1**: Are DALL·E 2 and Stable Diffusion images geographically representative? Do they over-represent rich or populous nations?
- **RQ2**: To what extent does specifying the country name in the input improve representativeness?
- **RQ3**: Does image realism impact participants' GR ratings?
- **RQ4**: How feasible is automatic assessment of GR?

Countries were sampled via weighted random sampling by population across 88 nations; sufficient responses yielded 27 countries (set *C*): USA, Canada, Mexico, Brazil, Chile, UK, Italy, Spain, Greece, Japan, Korea, India, Israel, Australia, South Africa, Belgium, Poland, Portugal, Germany, France, Latvia, Hungary, Czech Republic, Estonia, New Zealand, Finland, Slovenia.

Ten common nouns (set *N*) were extracted from the Conceptual Captions dataset via NLTK POS-tagging, excluding universal nouns: city, beach, house, festival, road, dress, flag, park, wedding, kitchen.

Two prompt types: country-specified (*p_c*): 'high definition image of a typical [artifact] in [country]'; unspecified (*p*): 'high definition image of a [artifact]'. Each participant rates 80 images (10 nouns × 8 images) on a 5-point Likert scale, then rates photo-realism. Trick questions (mismatched and matched image-label pairs) filter insincere responses. Inter-rater agreement: for 19/27 countries, the most common option was selected by >50% of respondents; highest agreement for flags (81%), lowest for kitchens (41%).

<!-- quelle: Study Design and Methodology -->

### Geographical Representativeness Results

The study defines GR(c, m, n, p) as the geographical representativeness score assigned by participants from country c to images generated for noun n from model m using prompt p. Key metric variants: GR(c, m, ·, p_c) averages ratings across all nouns using a country-specific prompt; GR(c, m, ·, p) uses an unspecified prompt; GR(·, m, n, p_c) averages across all countries with country-specific prompts; GR(·, m, n, p) averages across all countries without country specification.

For RQ1, computing GR(c, ·, ·, p) across 27 countries: 25 score below 3 (scale 1–5), with only the United States (3.35) and India (3.23) exceeding 3. The cross-country average is 2.39; lowest scores are Greece (1.94), Japan (1.95), and Finland (2.03). Against the hypothesis that artifacts represent richer or populous nations more: (1) no correlation with per-capita GDP (Pearson ρ = −0.03); splitting into 'Rich West' countries and others yields no statistically significant difference. The authors acknowledge that broader coverage of developing countries might reveal different trends, but expanding coverage is challenging. (2) GR scores positively correlate with population (ρ = 0.64), suggesting pre-training datasets contain more images from populous countries.

For RQ2, including the country name in the prompt (p_c) increases average GR scores for every nation. A paired sample t-test confirms statistical significance (p < 0.05): country-specific prompts raise scores by 1.44 points for DALL·E 2 and 0.75 for Stable Diffusion. Despite this, 14 of 27 countries still score only 3–3.5, indicating considerable headroom for improvement.

<!-- quelle: Geographical Representativeness Results -->

### Photo-realism and Model Comparison

## 3.4 Photo-realism of Generated Images

The authors hypothesize that photo-realism affects perceived geographical representativeness (RQ3), reasoning that unrealistic images may be hard to interpret and thus judged less geographically appropriate. Participants rated realism (Likert 1–5) for DALL·E 2 and Stable Diffusion images under both under-specified and country-specific prompts, and self-assessed realism's impact on their representativeness scores.

Geographical representativeness and realism correlate: Stable Diffusion Pearson 0.62 (unspecified) and 0.47 (country-specific); DALL·E 2 0.21 (unspecified) and 0.57 (country-specific). Participants self-report moderate influence (avg 3.5/5). Average realism scores are significantly lower (p<0.05) when prompts exclude country names, though for some countries (US, Brazil) realism decreases upon including country names. Qualitative examples show default generations reflect US/Canada artifacts—e.g., DALL·E 2 house images score 3.95 for US/Canada vs 2.09 for remaining countries (unspecified case).

## 3.5 Comparison of DALL·E 2 and Stable Diffusion

Model comparison yields: (i) for country-specific prompts, DALL·E 2 geographical representativeness scores exceed Stable Diffusion by ~0.6 points (statistically significant, paired t-test p<0.05); (ii) for country-agnostic prompts, differences are not statistically significant.

<!-- quelle: Photo-realism and Model Comparison -->

### Feasibility of Automating Evaluation

User studies of geographical representativeness (GR) are labor-intensive and non-reusable, motivating automatic estimation. Two approaches are tested against human ratings from DALL·E 2 and Stable Diffusion (SD).

**CLIP-based similarity.** CLIP similarity between a country-specific prompt and a test image is used as a proxy for GR. High-level findings partially align with human ratings: country-specific prompts yield higher CLIP scores than country-agnostic ones (p<0.001), matching the user study in 98.7% (DALL·E 2) and 96.4% (SD) of cases. However, CLIP contradicts human ratings at finer granularity: it finds no significant difference between DALL·E 2 and SD for country-specific prompts (humans rate DALL·E 2 higher), and rates SD higher for country-agnostic prompts (humans find no difference). Pearson correlation between CLIP and human GR scores is negligible for country-specific images (ρ=0.01) and weak for country-agnostic (ρ=0.34). Pairwise preference agreement is 52.4% versus 50% random chance. CLIP similarity is thus an inadequate proxy for GR.

**k-nearest neighbor estimation.** For a test image, k nearest neighbors among human-annotated images (k=1, given |X_c_n|=4) are found via feature-vector cosine similarity; the predicted GR score is the average of neighbor ratings. DALL·E 2 ratings train; SD ratings test. Correlation is moderate for country-agnostic (ρ=0.46) but absent for country-specific (ρ=0.01). MSE exceeds that of a constant baseline of 3.0 for both prompt types. All tested feature extractors — VGG16, ResNet18, ResNet50, ViT, CLIPVision — yield MSE above the baseline, confirming infeasibility. The authors attribute this partly to the small annotated training corpus and partly to feature extractors not differentiating images along geographical lines.

Both approaches prove inadequate for automatic GR estimation.

<!-- quelle: Feasibility of Automating Evaluation -->

### Limitations, Related Work and Conclusion

## Limitations & Future Directions

Despite outreach to 88 countries, sufficient responses came from only 27. Fourteen countries yielded fewer than 5 responses (Nepal, Bangladesh, Malaysia, Turkey, Singapore, Argentina, Kenya, Venezuela, Pakistan, Indonesia, Nigeria, Romania, Colombia, Namibia); 33 countries yielded zero (Laos, Armenia, Yemen, Thailand, Vietnam, Sri Lanka, Kazakhstan, Ukraine, Sierra Leone, Burkina Faso, Morocco, Senegal, Philippines, Egypt, Peru, Ethiopia, Mozambique, Kyrgyz Republic, Tanzania, Mali, Ecuador, Myanmar, Cambodia, Russia, Andorra, Finland, Tunisia, Gabon, Angola, Algeria, Libya, Botswana, Seychelles). Unequal internet access disproportionately silences marginalized nations; systems trained on internet data risk excluding them, and crowdsourcing platforms' sparse coverage of developing countries exacerbates the challenge of inclusive model development and evaluation.

Evaluation was limited to 10 common nouns (80 images per participant); extending would have reduced participation. The authors will open-source code for replication. Future directions: aggregating images per noun and country to scale evaluation; better documentation of training data sources to understand object and country distributions; collecting more data from under-represented countries; and improving participation from those countries in model development and evaluation.

## Related Work

Text-to-image generation evolved from GANs and generative RNNs to transformer-based and diffusion models. DALL·E 2 and Stable Diffusion were selected because their web-scraped training data raises concerns about amplified societal biases. Prior work measures biases in image classification, captioning, language generation, face recognition, image search, and art creation; recent studies examine DALL·E v1 (gender, racial biases) and Stable Diffusion (gender, class, ethnicity stereotypes). This study shares that critical spirit but addresses geographical representation—an oft-overlooked dimension.

## Conclusion

540 participants across 27 countries assessed how well generated images reflect global surroundings. Without country names in prompts, users in 25 of 27 countries found images less representative (average 2.39); including country names raised the average to 3.49. DALL·E 2 outperformed Stable Diffusion on country-specific inputs; otherwise scores were similar. Explored automation approaches were inadequate.

<!-- quelle: Limitations, Related Work and Conclusion -->

## GLOSSAR

- **Geographical Representativeness (GR)** — The degree to which generated images reflect the objects and surroundings of different nations, rather than overrepresenting certain nations.
- **underspecified** — Input descriptions that omit country names, leaving the model to fill in missing details and risking demographic overrepresentation.
- **allocational harms** — Biases propagated when generated images are used to augment datasets, further entrenching existing inequalities.
- **Realism R(c,m,p)** — Average realism rating assigned by participants from country c to images generated by model m using a specific prompt p.
- **Conceptual Captions dataset** — An image-caption pair dataset used to extract the most common nouns for artifact selection via POS-tagging.
- **GR (c, m, n, p)** — Geographical representativeness score assigned by participants from country c to images generated for noun n from model m using prompt p.
- **country-specific prompt (p_c)** — A textual query that includes the country name, intended to steer the image generation model toward geographically specific output.
- **Rich West** — A country grouping defined per worldpopulationreview.com's western-countries list, used to test whether GR scores differ between Western and non-Western nations.
- **photo-realism** — Participants' Likert-scale rating (1–5) of how realistic a generated image appears.
- **CLIP-based similarity** — An un-normalized score measuring alignment between a textual prompt and an image, used as an automatic proxy for bias evaluation.
