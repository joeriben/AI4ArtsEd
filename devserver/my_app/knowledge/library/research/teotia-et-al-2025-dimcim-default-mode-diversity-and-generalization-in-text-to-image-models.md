---
id: teotia-et-al-2025-dimcim-default-mode-diversity-and-generalization-in-text-to-image-models
titel: "DIMCIM: A Quantitative Evaluation Framework for Default-mode Diversity and Generalization in Text-to-Image Generative Models"
autor: "Revant Teotia, Candace Ross, Karen Ullrich, Sumit Chopra, Adriana Romero-Soriano, Melissa Hall, Matthew Muckley"
jahr: 2025
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, bias]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2506.05108"
status: published
analyzed_at: "2026-07-31T11:46:45.265361+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# DIMCIM: A Quantitative Evaluation Framework for Default-mode Diversity and Generalization in Text-to-Image Generative Models

## PROFIL

The text argues that text-to-image (T2I) generative models optimized for human preference suffer from limited representation diversity, necessitating a new reference-free benchmarking framework called DIMCIM. It positions itself against existing diversity metrics—both reference-based metrics like FID and reference-free metrics like Vendi Score—which either lack flexibility or fail to capture real-world diversity, as well as against prior bias-focused work that ignores generalization capacity. The framework introduces two measurements: the Does-it Metric (DIM) for default-mode diversity without explicit prompting, and the Can-it Metric (CIM) for generalization capacity when explicitly prompted. By evaluating whether models generate expected attribute variations autonomously or through prompt adjustments, the method exposes a trade-off between scaling parameters and default-mode diversity. For arts education, DIMCIM provides a quantitative tool to critically evaluate generative AI tools, ensuring students and educators select models capable of producing diverse visual representations across various concepts and attributes.

## WISSEN

### Problem Framing and Thesis

T2I models optimized for human preference achieve photorealism and prompt-image consistency but suffer limited representation diversity. Existing diversity metrics are either reference-based (FID, Recall, Coverage), requiring curated datasets for every new category and thus inflexible, or reference-free (Vendi Score), lacking specificity about what kind of diversity is measured. Prior bias-focused work (D'Incà et al., 2024) examines default settings but ignores generalization capacity—whether models can produce diverse images through prompt adjustments.

DIMCIM addresses this gap with two reference-free measurements: the **Does-it Metric (DIM)**—whether a model generates images with expected attribute variation without explicit prompting (default-mode diversity)—and the **Can-it Metric (CIM)**—whether a model generates diverse attributes when explicitly prompted (generalization capacity). Prompts are constructed hierarchically from concepts and paired attributes, using an LLM to produce under-specified coarse prompts and dense prompts with explicit attributes.

Contributions:
- DIMCIM, a quantitative assessment for default-mode diversity (DIM) and generalization capacity (CIM)
- COCO-DIMCIM benchmark, seeded with COCO concepts/captions, augmented by Llama3.1 for real-world diversity
- Analysis revealing a trade-off: scaling from 1.5B to 8.1B parameters improves generalization at the cost of default-mode diversity
- Fine-grained failure identification, including expected failures (e.g., negation) and unexpected failures (e.g., 'closed refrigerator')
- Correlation of 0.85 between training-data image diversity and default-mode diversity, plus detection of anomalies where increased training representation does not improve generated diversity

<!-- quelle: Problem Framing and Thesis -->

### Related Work and Demarcation

Existing image-diversity metrics divide into **reference-free metrics** (e.g., Vendi Score), which compute pairwise similarity within a sample batch but fail to capture real-world diversity, and **reference-based metrics** (e.g., FID, recall, coverage), which depend on large comparison datasets for each diversity axis. GRADE measures attribute distribution per concept, addressing **default mode bias** but not **generalization capacity**. Existing prompt datasets for attribute-object composition are either template-based (Winoground-T2I, T2I-Compbench, ABC-6K) or free-form via LLM (ConceptMix), but test few combinations; the authors extensively generate prompts and attributes per concept. Consistency metrics evaluate image-text faithfulness; some generate questions for VQA evaluation, requiring multiple systems and susceptible to linguistic biases and poor question quality. VQAScore avoids external LM but evaluates the entire prompt. The authors use a modification of VQAScore considering only the specific attribute-object pair at hand.

<!-- quelle: Related Work and Demarcation -->

### DIMCIM Framework and Metrics

DIMCIM is a quantitative benchmarking method for T2I model diversity across two objectives: **Default-mode Diversity** (measured by the **Does-It Metric**) — whether models generate visually diverse images without explicit diversity instructions — and **Model Generalization** (measured by the **Can-It Metric**) — whether models can generate diverse attributes when explicitly prompted.

A **coarse prompt** p_{c,-} contains a single concept without visual attributes (e.g., 'The dog plays in the grass'); a **dense prompt** p_{c,a} augments the coarse prompt with a specified attribute (e.g., 'The brown dog plays in the grass'). Each concept c has attribute types T_c (e.g., color, breed) and each type has attributes A_{c,t} (e.g., black, white, golden).

The **attribute-concept score** S(p_c, a) quantifies how much attribute a is preferred over other attributes in A_{c,t}. For n generated images, each image i receives an **image-attribute score** s(i, a_j) via VQAScore — using truncated text (concept + attribute only) to minimize background influence. S(p_c, a) = mean s(i, a) − mean s(i, a_j) for all a_j ≠ a.

**Does-It Metric**: Uses coarse prompts. S(p_{c,-}, a) at attribute level indicates default bias; summary metric = 1 − mean|S(p_{c,-}, a)| across all concepts and attributes. High score = balanced, diverse generation; low = imbalanced.

**Can-It Metric**: Uses dense prompts. S(p_{c,a}, a) at attribute level indicates whether requested attribute a is actually generated. Summary metric = mean of S(p_{c,a}, a) across all dense prompts.

<!-- quelle: DIMCIM Framework and Metrics -->

### COCO-DIMCIM Dataset Construction

The COCO-DIMCIM Dataset is a benchmark derived from COCO using the DIMCIM framework to evaluate visual attribute diversity in generated images of everyday objects. Human-related captions are excluded to avoid normative diversity issues regarding people. 30 object classes are selected as concepts, with 31 COCO captions serving as seed prompts per concept. An LLM (Llama3.1) extracts visual descriptions from seed prompts and generates plausible additional attributes, which are then grouped by attribute type (e.g., color, material). Visually ambiguous or mutually non-exclusive attributes are manually filtered out. Coarse prompts are created by removing existing visual attributes from seed prompts while preserving environmental context. Dense prompts are generated by injecting single attributes into coarse prompts, skipping unnatural combinations. The final benchmark comprises 30 concepts, 494 attributes, 930 coarse prompts, and 14,641 dense prompts.

<!-- quelle: COCO-DIMCIM Dataset Construction -->

### DIMCIM Experiments and the Diversity–Generalization Trade-off

The study applies DIMCIM to four T2I models spanning 1.5B–12B parameters: LDM2.1, Flow-Int, LDM3.5L, and FLUX.1-dev. For each model, 30 images are generated per dense prompt and per corresponding coarse prompt. Coarse prompts yield the Does-It Metric (DIM); dense prompts yield the Can-It Metric (CIM), both computed via VQAScore with InstructBLIP-Flan-T5-XXL at CFG scale 7.5.

Results reveal a trade-off: as model size increases, DIM decreases while CIM increases. Smaller models (LDM2.1: DIM 0.815, CIM 0.299; Flow-Int: DIM 0.802, CIM 0.315) depict more balanced attribute distributions in default mode. Larger models (LDM3.5L: DIM 0.799, CIM 0.374; FLUX.1-dev: DIM 0.785, CIM 0.326) generalize better when explicitly prompted. Increasing CFG amplifies this trade-off: higher guidance improves prompt-image consistency (raising CIM) but worsens default-mode bias (lowering DIM). Findings hold across VQAScore model variants.

<!-- quelle: Experimental Setup and Overall Results -->

### Fine-grained Failure Mode Analysis

DIMCIM enables interpretable failure-mode identification by plotting the **Does-It Metric** (attribute frequency under coarse prompts) and **Can-It Metric** (attribute generation under dense prompts) for concept-attribute pairs.

**Default-mode bias (Does-It Metric):** High/low scores reveal over/under-representation. For *airplane*–purpose, 'passenger' scores high across all models while 'military' scores low; for *table*–material, 'wooden' dominates over 'glass'. Critically, under-represented attributes retain *high* Can-It scores—models generate them when explicitly prompted, so the bias is default-mode, not a capability deficit. Conversely, 'perched' dominates *bird*–state despite 'flying' being equally common.

**Generalization failures (Can-It Metric):** A negative score means the model fails to generate a specified attribute even under dense prompting. Findings:
- Strong generalization for color, material, pattern across COCO-DIMCIM concepts.
- Larger models generalize better for pairs like 'digital' clock, 'convertible' car, 'freight' train; smaller models (e.g., Flow-Int) fail.
- All models struggle with negation ('without blanket', 'without pillows'), confirming established failure modes.
- **New failure mode:** low Can-It but high Does-It—models generate attributes in default mode yet fail when explicitly asked (e.g., 'closed'-wings birds, 'full' refrigerators).

<!-- quelle: Fine-grained Failure Mode Analysis -->

### Training Data Investigation

To trace sources of default-mode diversity, the authors compute Does-It Metric scores for CC12M training images using VQAScore (threshold 0.8) to retrieve concept-matching images, then compare these scores to those of images generated by a Flow-Int model trained on CC12M. The two score sets are highly correlated (Pearson 0.85 across COCO-DIMCIM concept-attribute pairs): e.g., 'ceramic' bowl scores high in both generated and training images, 'wooden' bowl low in both. This indicates default-mode diversity closely mirrors training-data attribute skew. DIMCIM also flags anomalous cases where an attribute is prevalent in training data yet absent in coarse-prompt generation (e.g., 'flying' bird), suggesting that simply increasing training representation may be insufficient for such cases.

<!-- quelle: Training Data Investigation -->

### Discussion and Limitations of DIMCIM

DIMCIM, a reference dataset-free benchmarking framework, assesses default-mode diversity and generalization capacity of T2I models. Key findings: (1) a trade-off between generalization and default-mode diversity emerges with increasing model size; (2) T2I models generate uncommon attributes when explicitly prompted but not in default behavior; (3) default-mode diversity correlates with training-data attribute distributions (e.g., bowl and bird attributes in Flow-Int trained on CC12M); (4) DIMCIM reveals failure cases where attributes like 'open' or 'closed' appear under generic prompts but fail under explicit requests.

Limitations: DIMCIM depends on external models for dataset construction and metric calculation. Mitigations include realistic captions to reduce hallucinations, filtering for mutually exclusive and imageable attributes, and adapting VQAScore for reliability. Open-source models avoid uncontrolled API variations. The method does not distinguish multiple valid concept definitions, supporting breadth of depictions instead. Generalization is studied via explicit prompting only; models may generate attributes through other methods such as external guidance.

<!-- quelle: Discussion and Limitations -->

### References and Supplementary Materials

The appendix details training and evaluation methodology. **Flow-Int** (Appendix A) was trained using flow matching, control conditions, and latent perceptual loss on image-caption pairs from ImageNet, CC12M, YFCC, and an internally licensed dataset; the version in Section 5.3 used only CC12M. Appendix B presents **COCO-DIMCIM** generalization analyses: (1) failure modes where larger models sometimes underperform smaller ones on specific attributes (e.g., 'broken' umbrella, 'foal', 'on land' boat, 'curly' dog), while all models struggle with 'inverted' bowls; LDM2.1 uniquely fails on 'empty' refrigerators. (2) Negations are difficult across all models—when prompted NOT to generate an attribute, models frequently generate it anyway. (3) Attribute types such as material, patterns, and dog breeds are easy for all models, yielding high Can-It Metric scores.

<!-- quelle: References and Supplementary Materials -->

## GLOSSAR

- **default-mode diversity** — The range of attributes a model generates when prompted coarsely, without explicit attribute specification.
- **generalization capacity** — A model's ability to generate images matching specified non-default attributes when explicitly prompted.
- **DIMCIM** — An evaluation protocol pairing a Does-It Metric (default-mode diversity) with a Can-It Metric (generalization capability) for text-to-image models.
- **reference-free metrics** — Diversity metrics computing pairwise similarity within a sample batch without relying on any external dataset.
- **default mode bias** — The tendency of a model to generate default attribute distributions for a given concept regardless of prompt specifications.
- **coarse prompt** — A prompt containing a single target concept without mention of visual attributes, used to test default-mode diversity.
- **dense prompt** — A coarse prompt augmented with an explicit attribute specification, used to test whether the model can generate requested diversity.
- **attribute-concept score** — The difference between the mean image-attribute score of a target attribute and the mean of all other attributes of the same type, measuring attribute preference in generated images.
- **seed prompts** — Initial COCO captions selected for each concept to generate attributes and prompts.
- **coarse prompts** — Prompts derived from seed prompts by removing visual attributes while preserving context.
