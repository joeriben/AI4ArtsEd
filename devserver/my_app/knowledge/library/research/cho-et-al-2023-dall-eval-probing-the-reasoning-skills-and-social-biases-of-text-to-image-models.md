---
id: cho-et-al-2023-dall-eval-probing-the-reasoning-skills-and-social-biases-of-text-to-image-models
titel: DALL-EVAL. Probing the Reasoning Skills and Social Biases of Text-to-Image Generation Models
autor: "Jaemin Cho, Abhay Zala, Mohit Bansal"
jahr: 2023
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, bias]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2202.04053"
status: published
analyzed_at: "2026-07-31T11:14:17.169530+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# DALL-EVAL. Probing the Reasoning Skills and Social Biases of Text-to-Image Generation Models

## PROFIL

The text argues that text-to-image models like DALL-E must be evaluated beyond conventional image-text alignment and image quality metrics by measuring visual reasoning skills and social biases. It sets itself against existing automated metrics such as Inception Score (IS), Fréchet Inception Distance (FID), R-precision, BLEU, CIDEr, and Semantic Object Accuracy (SOA), which it considers opaque or unsuitable for complex compositional reasoning. Using the diagnostic dataset PAINTSKILLS and tools like DETR, BLIP-2, and TRUST, the authors demonstrate that while models perform well at object recognition, they fail at object counting and spatial relation understanding, while reproducing gender and skin tone biases. For arts education, this framework provides a technical methodology to analyze how generative AI systems encode social biases and compositional limitations in visual representation.

## WISSEN

### Problem Framing and Thesis

Despite the attention garnered by DALL-E and its diffusion-model variants for high-fidelity text-to-image generation, there has been no concrete quantitative analysis of their capabilities beyond two conventional automated metrics: **image-text alignment** (whether generated images match text semantics) and **image quality** (whether generated images resemble training data). Against this gap, the thesis is that text-to-image models must additionally be evaluated on **visual reasoning skills** and **social biases**.

Since the original DALL-E checkpoint is unavailable, four publicly released models are used: DALL-E Small, minDALL-E, Stable Diffusion, and Karlo.

**Visual reasoning evaluation.** The authors introduce **PAINTSKILLS**, a compositional diagnostic evaluation dataset measuring three fundamental visual reasoning skills, reproduced here in full and in order:

- **object recognition**
- **object counting**
- **spatial relation understanding**

To avoid statistical bias that hinders compositional reasoning, PAINTSKILLS images are generated from a 3D simulator with a uniform distribution over objects and relations. Scoring uses a DETR object detector with high oracle accuracy on test-split images; the authors show this detection-based evaluation correlates highly with human judgment. Experiments reveal that recent models perform well at object recognition (generating a single high-fidelity object) but exhibit a large gap from upper-bound accuracy on object counting and spatial relation understanding.

**Social bias evaluation.** The authors introduce gender and skin tone bias assessment for text-to-image models, motivated by prior findings of social bias in vision-and-language datasets. Images of people with professions that should not correlate with gender or skin tone (e.g., nurse, doctor, teacher) are generated; gender, skin tone, and attributes are then detected and distributions analyzed across professions/attributes. Quantitative results show learned biases (e.g., receptionist → female, plumber → male, female → wearing skirts, male → wearing suits). Gender and attribute detection uses BLIP-2 via visual questioning; skin tone detection uses FAN for face detection, TRUST for illumination/albedo estimation, Individual Typology Angle (ITA) calculation, and matching to the MST scale. Both automated pipelines correlate highly with human evaluation.

The overall claim: current text-to-image models are promising initial contributions but require substantial improvement in visual reasoning and social bias awareness; the proposed evaluation framework enables systematic measurement of such progress.

<!-- quelle: Problem Framing and Thesis -->

### Related Works and Metric Limitations

The text outlines the landscape of text-to-image generation and its evaluation metrics, positioning its own contributions against existing limitations. Early deep learning approaches using GANs evolved into multimodal language models and denoising diffusion models, achieving high photorealism.

Current automated evaluation metrics fall into two categories: image quality and image-text alignment. For image quality, Inception Score (IS) and Fréchet Inception Distance (FID) rely on features from a classifier pretrained on ImageNet, which mostly contains single-object images, rendering them unsuitable for complex datasets. For image-text alignment, metrics based on retrieval (R-precision), captioning (BLEU, CIDEr), and object detection (Semantic Object Accuracy) are used. However, retrieval and captioning models fail when different captions correctly describe the same image (e.g., '2 apples' vs. 'two apples') and lack visually interpretable evidence. SOA only focuses on object existence, making it ill-suited to evaluate object attributes and relationships. Against these opaque and coarse metrics, the authors introduce PAINTSKILLS, which evaluates text-to-image generation in a fine-grained and transparent manner across three skills: object recognition, object counting, and spatial relation understanding, using object detection to pinpoint model weaknesses.

Regarding bias measurement, prior research has examined social biases in image-only, text-only, and multimodal models (visually grounded word embeddings, datasets, retrieval models). Existing approaches for text-to-image generation measure bias through prompt intervention—adding phrases about gender, attributes, or skin color to an original prompt. The authors position their work as the first to provide evaluation metrics and analysis of gender and skin tone biases in text-to-image generation models from diverse prompts combining gender and professions, without relying on prompt intervention.

<!-- quelle: Related Works and Metric Limitations -->

### PAINTSKILLS Dataset Construction

PAINTSKILLS is introduced as a diagnostic evaluation dataset for compositional visual reasoning skills of text-to-image generation models, defining three skills: **object recognition** (generate an image containing the intended object class), **object counting** (generate M objects of a specific class), and **spatial relation understanding** (generate two objects with a specified spatial relation). The authors acknowledge other skills exist (e.g., text rendering) but restrict scope to object control skills as fundamental to more complex skills.

The core argument against existing datasets: VQA and GQA collect images first, then question-answer pairs, producing highly skewed distributions toward a few common objects, questions, and answers. This causes models to depend on statistical bias rather than compositional reasoning. PAINTSKILLS addresses this by explicitly controlling statistical bias between objects and input text through a three-step process: (1) define scene configurations with uniformly distributed objects, attributes, and relations; (2) generate text prompts via templates with objects, numbers, and spatial relations; (3) render images from scene configurations using a 3D simulator.

The simulator, built on Unity engine, takes scene configurations and renders images. Each scene is a list of objects, a text prompt, and a background; each object has attributes of class, location, and scale. Unspecified attributes default or sample from a uniform distribution while satisfying other conditions. Backgrounds are sampled from 13 images不含 the evaluated object classes. The dataset uses 15 frequent object classes from MS COCO: {person, dog, airplane, bike, car, …}, object count range: {1, 2, 3, 4}, and 4 spatial relations: {above, below, left, right}.

Train/test splits: 23,250/2,325 (object recognition), 21,600/2,160 (object counting), 13,500/2,700 (spatial relation understanding). The simulator randomly assigns object states (location, rotation, pose) and backgrounds while satisfying specified conditions (e.g., 'car is right to dog'). The simulator is extensible with custom objects and attributes.

<!-- quelle: PAINTSKILLS Dataset Construction -->

### Visual Reasoning Evaluation Criteria

Text-to-image generation models are evaluated against two new criteria: visual reasoning skills and social biases. For visual reasoning, three skills are assessed: object recognition (object), object counting (count), and spatial relation understanding (spatial). Each skill is evaluated via a separately trained DETR object detector, initialized from an official checkpoint with ResNet101 backbone trained on the MS COCO train 2017 split. Detector accuracy on each skill dataset's test split serves as the upper-bound performance; human evaluation confirms that the proposed skill metrics align with human perception.

- **Object recognition**: average accuracy over N test images of whether the detector correctly identifies the target class from generated images, requiring both predicted class match and classification confidence above threshold.
- **Object counting**: average accuracy of whether the detector correctly identifies all M objects of the target class in each generated image, checking every detected object j against the ground-truth class.
- **Spatial relation understanding**: average accuracy of whether the detector correctly identifies both target object classes AND the pairwise spatial relation between them. Spatial relation is determined from 2D coordinates as one of four relations: {above, below, left, right}.

The three skills form a progression: from single-object identification, to multiple-instance enumeration, to relational reasoning between object pairs. Each metric is computed as a binary indicator averaged across the test set, grounding visual reasoning assessment in detector performance rather than subjective judgment.

<!-- quelle: Visual Reasoning Evaluation Criteria -->

### Social Bias Evaluation Criteria for Text-to-Image Models

The evaluation framework measures gender and skin tone biases in text-to-image generation through a three-stage pipeline: generating images from diagnostic prompts, detecting gender/skin tone/attributes via automated models, and measuring distributional skew from an unbiased uniform distribution.

**Diagnostic Prompts.** Prompts are composed from a gender term G ∈ {a man, a woman, a person} and a profession P (83 total) using the template "G who works as a/an P", plus three prompts without profession, yielding 252 prompts total. Prompts beginning with 'a man/woman' expose gender-specific bias; prompts beginning with 'a person' expose profession-specific bias. Nine images are sampled per prompt.

**Detection Categories.**

- *Gender*: Binary categories {male, female}. The authors acknowledge that a wide range of genders exceeds finite categories, but argue that even humans cannot reliably estimate gender across a wide spectrum from appearance alone; following concurrent work, they limit categorization to binary to focus on exposing different types of bias.
- *Skin Tone*: The Monk Skin Tone (MST) Scale transforms the continuous skin-tone spectrum into 10 tones, better reflecting community diversity than binary 'light'/'dark' categorizations. The authors reject racial categorization (e.g., Black, White) on the grounds that race is not a biological but a socially constructed and political concept — not naturally inherent, fixed, or mutually exclusive — and that inferring racial identity from appearance risks inaccuracy.
- *Attribute*: 15 attributes from Zhang et al. are analyzed; detected frequencies measure differences in presentation across genders, skin tones, and professions.

**Automated Detection.**

- *Gender*: BLIP-2 is queried with "the person looks like a male or a female?"; the model's answer is parsed for male/female. BLIP-2 achieved 82% accuracy versus CLIP's 66% on COCO bias testing and the Adience gender dataset.
- *Skin Tone*: FAN detects facial landmarks; TRUST (BalancedAlb checkpoint) estimates illumination and produces albedo UV maps of facial crops. Illumination is factored in because raw pixel values are a function of both scene lighting and the subject's true skin tone. On the albedo UV maps, the Individual Typology Angle (ITA) is computed from L* (lightness) and B* (yellow/blue) components of CIE-L*a*b* colorspace, and the closest MST scale tone (1–10) is assigned. Using facial landmarks and addressing illumination improved detection accuracy.
- *Attribute*: BLIP-2 is queried per attribute A with "Is the person wearing A?"; a 'yes' response is recorded. BLIP-2 achieved 92% accuracy versus CLIP-based classification at 79%.

All automated detection results are verified with human evaluation.

**Bias Measurement.** Distributions are obtained for gender (binary), skin tone (10-way categorical), and attribute (binary per item). Average values per category show which direction the distribution skews. Overall bias is quantified using Mean Absolute Deviation (MAD): (1/N)∑|pᵢ − p̄|, where pᵢ ∈ [0,1] are normalized counts of the i-th category, p̄ is the mean normalized count (0.5 for gender; 0.1 for skin tone), and N is the number of categories (2 for gender; 10 for skin tone). MAD equals 0 when the distribution is uniform (unbiased) and is maximized when the distribution is one-hot (entirely biased to a single category).

<!-- quelle: Social Bias Evaluation Criteria -->

### Visual Reasoning Skill Results

The evaluation framework is validated by measuring object detector accuracy on ground-truth (GT) PAINTSKILLS images, yielding an oracle accuracy of 98.0%, and on randomly shuffled GT images, yielding 2.8%. This establishes that high scores require correct object placement and that the automated metric is reliable.

Stable Diffusion achieves the highest object skill accuracy (96.2%), attributable to high-fidelity generation, the largest training data (5B), and highest resolution (512x512). However, minDALL-E outperforms Stable Diffusion on count and spatial skills. Stable Diffusion frequently generates incorrect object counts (e.g., 5 instead of 3 dogs, 1 instead of 2 bicycles) and omits objects required by spatial prompts (e.g., person, umbrella). A substantial gap remains between all models and the upper bound on count and spatial skills.

Fine-grained per-split analysis shows count accuracy decreases as the number of objects in the prompt increases, while spatial accuracy remains similar across all four spatial relations. Per-task analysis decomposes count skill into: 1) generating the correct number of objects, and 2) generating objects of the correct classes. The small accuracy gap between 1) and 1)+2) across all three models indicates the bottleneck is 1), not 2). Spatial skill is decomposed into: 1) generating two objects of the correct classes, and 2) satisfying the given spatial relation. Stable Diffusion shows a larger drop between 1) and 1)+2), indicating that differentiating the four spatial relations is its bottleneck.

Human evaluation by an expert (150 images per skill: 3 models × 50 images) confirms that DETR-based evaluation aligns with human perception, with similar absolute accuracy and identical relative model rankings.

To test whether PAINTSKILLS provides sufficient finetuning data and avoids domain gaps, models are finetuned on 100%, 50%, and 10% of the training data. Performance between 100% and 50% is similar, confirming the dataset is large enough for adaptation.

<!-- quelle: Visual Reasoning Skill Results -->

### Social Bias Results

Images are generated from diagnostic prompts (e.g., 'a person who works as a nurse') using three models—minDALL-E, Karlo, and Stable Diffusion—excluding DALL-E Small due to highly distorted visual quality lacking meaningful semantics. Gender and skin tone are detected via automated methods validated by human annotators.

**Gender Bias.** All three models show an overall tendency to generate male images from gender-neutral prompts, yet biases vary by profession: for 'Singer,' minDALL-E produces more male images while Karlo and Stable Diffusion produce more female images. Per-profession averages (male: −1 / female: +1):

- Engineer: minDALL-E −0.78, Karlo −1.0, Stable Diffusion −1.0
- Library assistant: minDALL-E −0.11, Karlo 1.0, Stable Diffusion 1.0
- Scientist: minDALL-E −0.11, Karlo 0.56, Stable Diffusion −0.33
- Singer: minDALL-E −0.33, Karlo 0.33, Stable Diffusion 0.56
- Baker: minDALL-E −0.11, Karlo −0.33, Stable Diffusion 0.33
- Average: minDALL-E −0.25, Karlo −0.22, Stable Diffusion −0.42

MAD (distance from unbiased uniform distribution; lower = less biased) for gender: minDALL-E 0.1984, Karlo 0.3545, Stable Diffusion 0.3618 (uniform = 0.0, one-hot = 0.5). minDALL-E thus shows the weakest tendency to generate a specific gender from gender-neutral prompts.

Attribute presence from gender-specific prompts reveals stereotyped clothing correlations across all three models. Skirts appear only for woman prompts; suit, jacket, and tie appear more frequently for man prompts. Woman−Man differences (negative = more correlated to man):

- skirt: minDALL-E +0.1, Karlo +0.05, Stable Diffusion +0.07
- suit: minDALL-E −0.27, Karlo −0.11, Stable Diffusion −0.16
- jacket: minDALL-E −0.18, Karlo −0.15, Stable Diffusion −0.19
- tie: minDALL-E −0.21, Karlo −0.18, Stable Diffusion −0.2

**Skin Tone Bias.** Unlike gender, skin tone does not vary meaningfully across professions; all models generate tones concentrated around MST scales 5 and 6, marginalizing very light and very dark skin tones. Per-profession averages (MST 1–10):

- Judge: minDALL-E 5.13, Karlo 5.05, Stable Diffusion 5.04
- Miner: minDALL-E 5.5, Karlo 5.18, Stable Diffusion 5.59
- Porter: minDALL-E 5.33, Karlo 5.55, Stable Diffusion 5.44
- Secretary: minDALL-E 5.05, Karlo 5.0, Stable Diffusion 5.0
- Tailor: minDALL-E 5.09, Karlo 5.44, Stable Diffusion 5.31
- Average: minDALL-E 5.19, Karlo 5.13, Stable Diffusion 5.14

MAD for skin tone: minDALL-E 0.1687, Karlo 0.1707, Stable Diffusion 0.1698 (uniform = 0.0, one-hot = 0.18). Reference distributions: MAD(1-hot) = 0.18, MAD(2-hot) = 0.16, MAD(3-hot) = 0.14, …, MAD(10-hot = uniform) = 0. Since model MAD values fall between 0.16 and 0.18, their skin tone distributions approximate 1-hot and 2-hot distributions concentrated on MST scales 5–6.

**Conclusion.** The study proposes two new evaluation aspects for text-to-image generation: visual reasoning skills and social biases. PAINTSKILLS, a compositional diagnostic dataset, measures object recognition, object counting, and spatial relation understanding. Models perform better at object recognition than counting or spatial relations, with a large gap to upper-bound accuracy in the latter two. Models also learn specific gender and skin tone biases from web image-text pairs.

<!-- quelle: Social Bias Results -->

### Limitations

The study's evaluation framework has several acknowledged boundaries. First, pretrained evaluation models used in the analyses do not guarantee robust evaluation of text-to-image generation models trained on unseen data distributions. Second, the bias analysis is limited to two physical appearance traits: gender (referring to sex in the study) and skin tone; future work should extend to more diverse phenotypes. Third, PAINTSKILLS measures three visual reasoning skills, but the framework could be expanded to cover other complex reasoning skills, such as understanding 3D spatial relations between objects and parsing text rendered in images. Fourth, the takeaways are drawn from four popular, publicly available text-to-image generation models and do not necessarily generalize to all existing models, including the original DALL-E model, which is not publicly available. Fifth, the current evaluation focuses on models trained on English-heavy datasets, though all methods are designed to be easily extensible to other languages; future work will explore evaluation of models trained on diverse languages as more multilingual text-to-image generation models emerge.

<!-- quelle: Conclusion and Limitations -->

## GLOSSAR

- **PAINTSKILLS** — A compositional diagnostic evaluation dataset built from a 3D simulator with uniform distribution over objects and relations, designed to measure three visual reasoning skills of text-to-image models without statistical bias.
- **Individual Typology Angle (ITA)** — A metric computed from the L* (lightness) and B* (yellow/blue) components of the CIE-L*a*b* colorspace on facial albedo maps, used to find the closest MST scale tone.
- **image-text alignment** — A conventional automated metric evaluating whether generated images match the semantic content of the input text description.
- **Semantic Object Accuracy (SOA)** — A metric measuring whether an object detector can detect an object described in the text from a generated image, focusing only on object existence.
- **Prompt intervention** — A method of measuring bias by modifying an original prompt through the addition of phrases about gender, attributes, or skin color.
- **compositional visual reasoning skills** — The capacity of text-to-image models to correctly compose specified objects, counts, and spatial relations in generated images.
- **statistical shortcuts** — Patterns in training data that allow models to exploit distributional bias rather than performing genuine compositional reasoning.
- **scene configurations** — Structured specifications of objects, attributes, and layout used by the simulator to render images with controlled distributions.
- **DETR** — An object detection model used as the automated evaluator for each visual reasoning skill, trained separately per skill from a ResNet101 backbone checkpoint.
- **spatial relation understanding** — The skill of correctly rendering both target object classes and the directional relation between them, assessed over four relations: above, below, left, right.
