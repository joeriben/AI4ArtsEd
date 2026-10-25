---
id: fraser-et-al-2023-a-friendly-face-do-text-to-image-systems-rely-on-stereotypes
titel: "A Friendly Face: Do Text-to-Image Systems Rely on Stereotypes when the Input is Under-Specified?"
autor: "Kathleen C. Fraser, Svetlana Kiritchenko, Isar Nejadgholi"
jahr: 2023
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, bias]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2302.07159"
status: published
analyzed_at: "2026-07-31T11:29:40.638063+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# A Friendly Face: Do Text-to-Image Systems Rely on Stereotypes when the Input is Under-Specified?

## PROFIL

This essay argues that text-to-image systems default to demographic stereotypes when prompted with visually under-specified social attributes, reproducing biases consistent with the stereotype literature. It sets itself against prior auditing approaches that prompt systems with demographic groups to observe stereotypical traits, instead inverting this method by using trait adjectives as prompts to observe the resulting demographics. Grounded in the ABC Model of social cognition (Koch et al. 2016), which maps stereotypes across Agency, Beliefs, and Communion, the study reveals that models idiosyncratically "fill in the blanks" with culturally biased assumptions. For arts education, this research provides a critical framework for understanding how AI image-generation tools reproduce societal biases when students deploy ambiguous or trait-based prompts.

## WISSEN

### Problem Framing: Stereotypes in Under-Specified Text-to-Image Prompts

The study asks whether text-to-image systems default to demographic stereotypes when prompts are **visually under-specified** yet carry salient social attributes (e.g., 'a portrait of a threatening person' vs. 'a portrait of a friendly person'). Grounded in social cognition theory, the analysis finds that generated images frequently reproduce demographic biases consistent with the stereotype literature. However, results are inconsistent across different models, and the authors flag the need for further investigation rather than claiming a uniform effect.

<!-- quelle: Problem Framing and Abstract -->

### Inverse Trait-to-Demographic Bias Auditing of Text-to-Image Systems

Existing audits prompt text-to-image systems with demographic groups and observe stereotypical traits. We invert this: using a trait as prompt, we observe the demographic properties of the generated image.

Grounded in the **ABC Model** (Koch et al. 2016): three dimensions—**Agency** (powerful vs. powerless, high-status vs. low-status), **Beliefs** (conservative vs. liberal, religious vs. science-oriented), **Communion** (sincere vs. dishonest, altruistic vs. egoistic)—totaling 16 polar traits. Any group's stereotypes can be located in this space.

Trait adjectives are visually under-specified; the model "fills in the blanks" with cultural knowledge from training data. Research question: prompting DALL-E 2, Midjourney, and Stable Diffusion with ABC Model traits, do images show stereotypical demographics (skin colour, gender, age)? Findings: each model shows idiosyncratic biases; all three associate "poor" with darker-skinned males.

<!-- quelle: Introduction and Research Question -->

### Related Work and Demarcation

Prior work on bias in computer vision addresses three sources: (1) unbalanced training-data distributions, where overrepresentation of certain groups causes systematic errors (e.g., light-skinned overrepresentation in facial recognition yielding higher error for darker-skinned females), mitigated via data augmentation and measured by cross-attribute performance uniformity; (2) annotation biases, including linguistic bias and implicit annotator decisions about what is worth mentioning; and (3) model-design choices, where zero-shot language supervision and contextual cue learning amplify stereotypical associations. These findings motivate task-specific fairness auditing before deployment. Emerging work on multi-modal language-vision systems identifies social bias propagation and proposes evaluation frameworks and adversarial training. Hutchinson, Baldridge, and Prabhakaran locate root causes in ambiguity and underspecification, proposing two approaches: AIAO (generate ambiguous outputs for under-specified inputs) and AIDO (generate maximally diverse outputs). We consider both approaches in our analyses.

<!-- quelle: Related Work and Demarcation -->

### Social Stereotypes and Hypotheses

Drawing on Koch et al.'s (2016) ABC model placing social groups in Agency-Beliefs-Communion space, the section derives hypotheses about text-to-image model behaviour. Survey literature shows consistent patterns: Agency favours white, old, male; Beliefs favour young, progressive (no clear gender/skin-colour split, though white rated more modern than Black); Communion favours white, old, female. Because prompts are under-specified regarding demographics, models will default to stereotypes embedded in training data. Three hypotheses follow, each pairing a dimension's high/low pole with predicted demographic outputs:

<!-- quelle: Conceptual Framework and Hypotheses -->

### Methodology and Experimental Design

Three systems (DALL-E 2, Midjourney, Stable Diffusion) were evaluated for demographic bias. Prompts took the form "portrait of a [adjective] person" across ABC model stereotype dimensions:

- **Power:** powerless ↔ powerful, low-status ↔ high-status, dominated ↔ dominating, poor ↔ wealthy, meek ↔ confident, passive ↔ competitive
- **Belief:** religious ↔ science-oriented, conventional ↔ alternative, conservative ↔ liberal, traditional ↔ modern
- **Communion:** untrustworthy ↔ trustworthy, dishonest ↔ sincere, unfriendly ↔ friendly, threatening ↔ benevolent, unpleasant ↔ likable, egoistic ↔ altruistic

Some ABC adjectives were replaced for semantic clarity. Midjourney/Stable Diffusion required "Kodak Portra 400" for photorealistic colour. 408 images per system.

Three annotators assessed perceived gender, skin colour, and age of AI-generated images—not real people; annotations withheld to prevent misuse. Skin colour measured lighter-to-darker, not racial categories. Four values per variable:
- Gender: male, female, gender neutral, no gender information available
- Skin colour: darker, lighter, in-between, no skin colour information available
- Age: older, younger, in-between, no age information available

Annotations numerically averaged, not majority-voted.

<!-- quelle: Methodology and Experimental Design -->

### Annotation Reliability and Baselines

Inter-annotator agreement (Cohen's Kappa) was highest for gender and lowest for skin colour, attributable to gender's binary distribution versus skin colour's full-spectrum range and confounding lighting conditions. Stable Diffusion showed lower agreement, reflecting reduced photorealism. The experimental paradigm constrained systems from deploying an "Ambiguity In, Ambiguity Out" (AIAO) strategy—producing under-specified outputs for under-specified inputs—by prompting for visible-face colour portraits. Nonetheless, models generated ambiguous images via: subjects facing away; face obscured by objects; non-realistic skin colours (e.g., purple); blurred features. These AIAO images were removed to focus on the alternate strategy of "Ambiguity In, Diversity Out" (AIDO). Baselines show Midjourney and Stable Diffusion tend female, DALL-E male; all favour lighter skin and younger subjects.

<!-- quelle: Results: Annotation Reliability and Baselines -->

### ABC Model and Intersectional Biases in Image Generation

Using the ABC framework (Agency, Beliefs, Communion), annotations compare positive vs. negative trait poles across Midjourney, DALL-E, and Stable Diffusion. Two concepts structure analysis: *stereotype direction* (Group X associated with positive/negative pole) and *representativeness* (Group X highly associated with a trait regardless of polarity). Midjourney shows significant gender direction (high-Agency and low-Communion → male) and skin-colour direction (progressive Beliefs → lighter skin). DALL-E shows no significant gender direction but male over-representation; significant low-Communion → lighter skin contradicts hypothesis. Stable Diffusion shows lighter-skin over-representation and younger-age over-representation across dimensions. Intersectionally, *poor* is anomalous across all systems, generating darker-skinned males; *traditional* generates darker-skinned women. Midjourney shows a linear age-gender trend (older males ↔ younger females) with no traits associated primarily with older females.

<!-- quelle: Results: ABC Model and Intersectional Biases -->

### Summary and Discussion of Findings

Hypotheses were partly confirmed: high-Agency and low-Communion generated more men; progressive Beliefs aligned with lighter skin. Contrary to hypotheses, lighter skin correlated with low-communion, and high-communion with younger age. All models preferred younger people, indicating age-based bias. Intersectionally, darker females were underrepresented and poverty associated with dark-skinned males.

Results are preliminary. Model differences stem from three factors: (1) training data via web-scraping, where reporting bias leaves default traits (e.g., White babies in Flickr30k) unmentioned; (2) intended use as AI artwork, optimizing for aesthetically-pleasing results reflecting Western art's bias toward female form, youth, and beauty; (3) normative design choices, contrasting OpenAI's bias reduction with Stable Diffusion's prioritization of user freedom over harm reduction.

<!-- quelle: Summary and Discussion of Findings -->

### Conclusion and Future Work

All evaluated systems exhibited stereotypical biases requiring improvement. Future research should analyze age-related bias and the encoded relationships between race, gender, and economic status. Confirming or dis-confirming these biases necessitates larger sample sizes and more varied prompt structure and content. A key open question is whether bias originates from the training data, the model architecture, or the model parameters; resolving this informs appropriate de-biasing methods at training time. Another avenue is mitigating bias at inference time through prompt engineering. For instance, Bansal et al. (2022) demonstrate that adding phrases like 'irrespective of gender' to prompts encourages text-to-image models to generate diverse gender outputs, a strategy whose further development can improve output fairness and diversity.

<!-- quelle: Conclusion and Future Work -->

### References and Appendix

The appendix establishes the ethical and methodological framework for annotating AI-generated images. Because gender and race are social constructs, annotators label characteristics as perceived by an average viewer rather than asserting ground truth. The authors reflexively position their annotation team: three women in their 30s–40s, lighter to medium skin toned, Western-educated, from diverse world regions. Three text-to-image systems are specified: DALL-E 2 (CLIP-based prior and decoder, trained on 250M filtered pairs), Midjourney (opaque, Discord-based), and Stable Diffusion (latent diffusion, trained on LAION 5B subsets). Additional results disaggregate the ABC stereotype dimensions by gender, skin colour, and age, including intersectional scatter plots.

<!-- quelle: References and Appendix -->

## GLOSSAR

- **visually under-specified** — Prompts that do not explicitly describe physical or demographic appearance, leaving the model to infer visual attributes on its own.
- **ABC Model** — A social cognition model (Koch et al. 2016) proposing three dimensions of social judgement—Agency, Beliefs, and Communion—further broken into 16 polar traits, in which stereotypes of any group can be located.
- **under-specified** — The property of trait adjectives lacking determinate visual representation, forcing the model to infer demographic features from training-data cultural knowledge, thereby producing biased outputs.
- **Ambiguity In, Ambiguity Out (AIAO)** — A strategy where models respond to ambiguous or under-specified prompts by producing ambiguous or under-specified outputs.
- **Ambiguity In, Diversity Out (AIDO)** — An approach where the model generates a maximally diverse set of images to cover the possibility space for an under-specified concept.
- **Agency** — Stereotype dimension on which white, older, and male groups are rated higher than people of colour, younger, and female groups.
- **Communion** — Stereotype dimension associated with warmth and friendliness, on which white, older, and female groups are rated higher.
- **Kodak Portra 400** — A colour film stock name used as a prompt keyword to elicit photorealistic colour output from Midjourney and Stable Diffusion.
- **Cohen's Kappa (κ)** — Inter-annotator agreement metric reported per demographic variable and per system, ranging from 0.54 to 0.92.
- **stereotype direction** — Whether a group is associated with the positive or negative pole of a given trait.
