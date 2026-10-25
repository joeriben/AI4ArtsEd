---
id: luccioni-et-al-2023-stable-bias-evaluating-societal-representations-in-diffusion-models
titel: "Stable Bias: Evaluating Societal Representations in Diffusion Models"
autor: "Alexandra Sasha Luccioni, Margaret Mitchell, Christopher Akiki, Yacine Jernite"
jahr: 2023
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, bias]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2303.11408"
status: published
analyzed_at: "2026-07-31T10:59:24.222690+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Stable Bias: Evaluating Societal Representations in Diffusion Models

## PROFIL

Luccioni, Mitchell, Akiki, and Jernite argue that social biases in Text-to-Image (TTI) Systems—understood as assemblages of diffusion models, CLIP-guided training, safety filters, and embeddings whose individual contributions to downstream bias cannot be disentangled—can be audited by systematically varying gender and ethnicity markers in prompts and comparing the resulting image variation against variation produced by spanning different professions. The method sets itself against the prevailing practice of documenting bias only in broad terms within model cards and against the assumption that synthetic depictions of fictive humans, lacking inherent gender or ethnicity, are resistant to diversity evaluation. Applied to Dall·E 2 and Stable Diffusion v.1.4 and v.2, the approach reveals that outputs correlate with US labor demographics while consistently under-representing marginalized identities, and the authors release datasets and low-code interactive platforms to lower barriers to further bias exploration. For arts education, the method and accompanying tools offer a practical framework for students and educators to critically interrogate representation and diversity in AI-generated visual content.

## WISSEN

### Problem Framing and Introduction

As ML-enabled Text-to-Image (TTI) systems gain commercial adoption, characterizing their social biases is a necessary first step toward reducing discriminatory outcomes. This evaluation is complicated by the synthetic nature of outputs: conventional diversity definitions are grounded in social categories of real people, whereas AI-generated depictions of fictive humans carry no inherent gender or ethnicity.

The proposed method addresses this by characterizing variation in generated images triggered by enumerating gender and ethnicity markers in prompts, then comparing it to variation engendered by spanning different professions. This yields three capabilities: (1) identifying specific bias trends, (2) providing targeted scores to directly compare models on diversity and representation, and (3) jointly modeling interdependent social variables for multidimensional analysis. Applied to three popular TTI systems (Dall·E 2, Stable Diffusion v.1.4 and v.2), all outputs correlate with US labor demographics but consistently under-represent marginalized identities to different extents.

A key demarcation: the authors refer to these artifacts as **Text-to-Image (TTI) Systems** rather than models, because training and inference rely on additional processing phases (safety filters, embeddings, CLIP-guided training) whose individual contributions to downstream bias cannot be disentangled. Biases are baked in across this assemblage of components and modules.

Diffusion models are trained to reverse the gradual addition of noise layered onto an image. Their likelihood-based loss function has a **mode-covering characteristic** that produces more diverse outputs than other generative model classes, but the iterative approach makes the latent space particularly difficult to directly access and analyze.

Current bias documentation is sparse: biases are described only in broad terms in model cards and in papers introducing new models. The authors introduce tools and approaches for auditing social biases by comparing model outputs across targeted prompts — specifically, professions and explicit gender/ethnicity terms — and release datasets, low-code interactive exploration platforms, and tools for evaluating additional TTI systems, lowering the barrier to entry for bias exploration.

<!-- quelle: Problem Framing and Introduction -->

### Background and Related Work: Bias in Multimodal and Text-to-Image Systems

Bias in ML encompasses disparate model performance across categories, propagated social stereotypes, and dataset (mis-)representations encoded by models. While text and image models independently encode problematic biases, the rapid rise of multimodal models has outpaced understanding of their specific biases. A central gap: it remains unestablished whether biases in each modality amplify or compound one another. The project addresses this gap.

A *compounded outcome* is illustrated thus: if a multimodal model represents visual concepts of 'people' and 'White people' in a different space than 'Black people,' while representing the linguistic concept of 'people' with higher positive sentiment than 'Black people,' the result can be model output where Black people are depicted more negatively than other identity groups.

Past work supports this concern. Biases regarding race, gender, and appearance propagate to downstream outputs in image captioning (e.g., associating women with shopping and men with snowboarding; producing lower-quality captions for images of people with darker skin) and image search (algorithmic curation reinforcing biases, negatively affecting sense of belonging). State-of-the-art multimodal models learn such biases. Widespread deployment of image generation systems translates these biases into negative impacts on minority groups who feel under- or mis-represented.

For TTI systems specifically, recent work examines safety filters, semantic space structure, stereotypical representations, and memorization of training examples. CLIP, used to guide the diffusion process, encodes societal biases between race and cultural identity. Initial debiasing approaches exist—exploring latent space and guiding generation along different axes—but their generalizability remains unclear.

Multiple sources of bias in TTI systems:
- Training data scraped from the Web contains harmful, pornographic, mislabeled, and corrupted content
- Dataset filters for 'aesthetic' or 'safe for work' subsets rely on classification models trained on other datasets, producing unintended consequences
- Dall·E 2's creators found that filtering 'explicit' content contributed to *bias amplification*, necessitating additional post-hoc mitigation
- CLIP's biases guide training and generation, with unclear impact on image generation
- Safety filters and prompt enhancement techniques are poorly understood and largely undocumented; keyword-based approaches have shown *disparate impact* on already marginalized groups, raising concerns about their use in prompt-level safety filtering

<!-- quelle: Background and Related Work -->

### Methodology: Auditing Social Biases in TTI Systems

The approach is motivated by the need to audit social dynamics in multimodal ML. The core intuition: images generated by TTI systems lack inherent social attributes, yet display visual features in their depiction of human figures that viewers interpret as social markers. These markers cannot be defined a priori because identity characteristics such as race or gender are multidimensional notions spanning a spectrum along which people choose to associate themselves, not discrete external quantities determinable by appearance. Prior ML work has adopted binary gender and fixed prior ethnicity categorizations for convenience; the downstream impact of these choices propagates from labeled datasets to trained models, contributing to algorithmic harms and unfairness. The approach therefore uses flexible proxy representations of visual features in generated images to identify regions of the representation space that viewers may associate with social variation, and uses those to audit TTI diversity in an application setting.

The methodology proceeds in the following steps:

- First, define a set of identity characteristics for which to evaluate diversity and representativity; in this work, both gender and ethnicity are considered.
- Second, generate a set of images with TTI systems by controlling the variation of markers of these social attributes in the systems' input prompts — i.e. by spanning different ways of referring to a person's gender or ethnicity in the prompt.
- Third, generate sets of images for prompts with different social attributes to audit; here, the profession attribute is focused on, and images are generated for a set of 146 professions.
- Finally, given the multimodal nature of TTI systems, carry out two sets of analyses: a text-based analysis leveraging Visual Question Answering (VQA) models in the text modality, and a clustering-based evaluation to characterize correlations between social attributes and identity characteristics directly in the image modality.

The footnote acknowledges that criteria used to establish which images are esthetically-pleasing and safe for work are also unclear and merit further investigation.

<!-- quelle: Methodology Overview -->

### Dataset Generation

Two supporting datasets are constructed to evaluate social biases across three TTI systems: Stable Diffusion v.1.4, v.2, and DALL·E 2. These systems are selected as state-of-the-art as of early 2023, enabling comparison both between two versions of the same system (Stable Diffusion v.1.4 vs. v.2) and between open- and closed-source systems (Stable Diffusion vs. DALL·E 2).

Prompt generation uses the pattern 'Photo portrait of a [ X ] [ Y ]', where X and Y span identity characteristics (ethnicity and gender) and the professional attribute (occupation name). For identity characteristics, the pattern becomes 'Photo portrait of a [ ethnicity ] [ gender ] at work' — the 'at work' suffix ensures comparability with profession-generated images, which are typically set in workplace settings.

- **Professions**: 146 occupations sourced from the U.S. Bureau of Labor Statistics (BLS), which also supplies demographic and salary data per profession for downstream analysis.
- **Gender**: four values — 'man', 'woman', 'non-binary person', and the unspecified 'person'. The authors acknowledge this is far from a complete exploration of gender variation, specifically noting the absence of gender terms relevant to trans* experiences and to gender experiences outside the US context.
- **Ethnicity**: grounded in the North American context, starting from the US census ethnicity list and expanding with synonyms per group (full list in Appendix A).

Enumerating all gender and ethnicity marker combinations yields 68 prompts.

Two datasets are generated:
- **'Identities' dataset**: one set of images per model per gender–ethnicity combination, totaling 68 prompts and 2040 images across the three systems. This dataset grounds the analysis.
- **'Professions' dataset**: one set of images per model per profession (146 professions), used to evaluate social diversity without explicit gender or ethnicity label assignment, including via a novel non-parametric method that compares profession images to the 'Identities' dataset.

<!-- quelle: Dataset Generation -->

### Analytical Approaches for Generated Images

To audit text-to-image (TTI) systems for social biases, two analytical methods are proposed: one using text representations of images, and one using direct comparisons in the image space.

**Text Features Analysis: Image-to-Text Systems**
Text-based representations of depicted figures are obtained using two ML systems: the ViT GPT-2 Model for image captioning and the BLIP VQA base model for Visual Question Answering (VQA). The captioning model generates multi-word captions, while the VQA system answers "What word best describes this person's appearance?" with a single word or short phrase. Both models are open-ended, avoiding constraints to labels reflecting the researchers' own biases. The researchers acknowledge that both models contain confounding factors and biases; thus, captions are not treated as ground truth but as one feature among others. (Before converging on the prefix "Photo portrait of", the researchers experimented with "Photo of", "Photograph of", "Portrait of", and "Close up of", finding the former gave the most realistic results.)

**Visual Features Analysis: Clustering-Based Approach**
Text descriptions are tractable but carry limited information. Dense embedding techniques project images into a multidimensional vector space as a middle ground. The BLIP VQA system is used to obtain image embeddings (normalized average of question token embeddings), chosen to focus on the depicted person, yielding a better structure than the CLIP image encoder. To evaluate social biases, regions of the embedding space corresponding to visual features of gender or ethnicity are identified using the 'Identities' dataset. The embeddings of 2040 data points are clustered into 24 sets using a Ward linkage criterion for the dot product. Trends in TTI outputs (e.g., the 'Professions' dataset) are quantified by over- or under-representation in these 24 regions. Assigning an example to a region differs from assigning a predefined identity characteristic; regions span different gender and identity phrases. Although 24 regions cannot cover the 68 identity phrase combinations, clustering on a space whose variation derives from these phrases ensures the regions encode visual features associated with them, including intersectional phenomena.

**Interactive Exploration**
Interactive tools support story-based examination of biases. Their primary goal is not quantitative insight but ad-hoc, in-depth exploration of aspects difficult to analyze automatically (e.g., specific visual elements), observed from user-defined angles.

<!-- quelle: Analytical Approaches -->

### Gender Bias Analysis via Text Markers

The analysis aims to make text-to-image (TTI) system biases tractable by converting generated images into discrete textual representations via captioning and Visual Question Answering (VQA), then measuring the likelihood that captions or VQA answers for a given profession contain gender-marked words ('man', 'woman') versus gender-unspecified descriptors ('person', profession name).

97.66% of captions contained gender-marked terms versus 45.56% of VQA predictions — consistent with VQA yielding single-word answers while captions are full sentences. To contextualize these rates, they are compared against U.S. Bureau of Labor Statistics (BLS) workforce percentages for the same professions.

Dall·E 2 shows the largest discrepancy from BLS figures: captions mention women on average 27% less, VQA 25% less. Stable Diffusion v.1.4 shows the least discrepancy (~9% for both). Professions with the greatest underrepresentation of women versus BLS across all systems: clerk (57%/55% less), data entry keyer (55%/53% less), real estate broker (52%/54% less). Professions overrepresenting women relative to BLS: singer (29%/36% more), cleaner (20%/16% more), dispatcher (19%/16% more).

Table 1 data (captions / VQA / BLS, %woman / %man / %gender markers):
- SD v.1.4: captions 38.04% woman / 61.96% man / 97.24% markers; VQA 37.77% / 62.23% / 47.92%; BLS 47.03% / 52.97%
- SD v.2: captions 33.45% / 66.55% / 96.66%; VQA 31.10% / 68.90% / 44.50%; BLS 47.03% / 52.97%
- Dall·E 2: captions 19.96% / 80.04% / 99.09%; VQA 21.95% / 78.05% / 44.25%; BLS 47.03% / 52.97%
- Average: captions 30.48% / 69.52% / 97.66%; VQA 30.06% / 69.67% / 45.56%; BLS 47.03% / 52.97%

Gender-neutral terms ('person') appear in fewer than 1% of captions on average, distributed equally across professions; no system uses the 'non-binary' gender marker. Fewer than 0.5% of captions and 2% of VQA generations explicitly mention the profession name from the prompt, with the exception of police officer (80.95% of captions). In VQA, doctor (70.48%), firefighter (45.71%), and pilot (29.84%) also show high explicit mention rates. This is attributed to the markedness of these professions and the high proportion of gendered references (as opposed to gender-neutral terms like 'person') in the training data of both TTI systems.

<!-- quelle: Gender Bias Analysis via Text Markers -->

### Gender and Ethnicity Distribution in the Image Space

To quantify TTI systems' diversity in terms of GENDER and ETHNICITY without solving a poorly-specified identity label assignment problem, the authors propose a cluster-based method: images generated from 68 combinations of 4 gender phrases and 17 ethnicity phrases are clustered into 24 regions. Regions do not correspond to specific identities, but their character can be inferred from the top gender and ethnicity phrases in the prompts assigned to each region in the 'Identities' dataset.

Region 4 accounts for over 40% of 'Professions' images and tends to contain images generated for prompts describing White men; regions featuring the word 'woman' (regions 15, 13, 1, and 10) together account for only 25.5%. The case of 'laboratory technician' (630 images, 210 per system) illustrates the method: Dall·E 2 assigns twice the share to region 4 compared to Stable Diffusion, and produces no images assigned to region 1 (associated with 'woman' and 'Black' phrases), confirming the region summaries.

To compare bias trends across models, the authors aggregate across professions and clusters. Professions are ranked by US Bureau of Labor Statistics (BLS) reported proportions of workers self-identifying as women (for GENDER analysis) or Black (for ETHNICITY analysis), then grouped into 5 quintiles of 29–30 professions each. Regions are grouped by whether 'woman' appears in the top-2 gender phrases or 'Black' in the top-4 ethnicity phrases. Comparing the proportion of images assigned to grouped regions per quintile against the average BLS value for that quintile reveals whether a model attenuates, reproduces, or exacerbates societal biases.

Key findings from Table 3:
- Stable Diffusion v1.4 roughly matches the US distribution for the least diverse professions (mostly men or mostly women) but under-represents 'woman' regions across more balanced professions.
- All three systems under-represent regions associated with 'woman' and 'Black' phrases; the effect is least pronounced for SD v1.4 and most pronounced for Dall·E 2.
- For the top quintile of professions by BLS women share (86.8%), cluster shares featuring 'woman' are: SD 1.4 83.0%, SD 2 78.3%, Dall·E 2 56.3%.
- For the top quintile by BLS Black share (22.1%), cluster shares featuring 'Black' are: SD 1.4 16.8%, SD 2 16.1%, Dall·E 2 4.5%.

The method generalizes to any TTI system; the authors benchmarked an additional 11 systems from the most downloaded models on the Hugging Face Hub.

<!-- quelle: Gender and Ethnicity Distribution in Image Space -->

### Interactive Tools for Interactive Exploration

The authors developed three interactive tools to analyze images generated by different TTI systems, identifying patterns to guide their analyses.

**Diffusion Bias Explorer**: Enables comparison of the same set of profession-based prompts (from Section 3) across three TTI systems. It uncovered initial patterns, including the homogeneity of certain professions (e.g., CEO) and differences between Stable Diffusion versions and DALL·E 2. Used throughout the project to visually verify tendencies discovered through other analyses, as it allows quick viewing of images for any profession+TTI system combination.

**Average Face Comparison Tool**: Leverages the Facer Python package for face detection, alignment based on facial features, and averaging across professions. This revealed high-level visual patterns across TTI systems while deliberately avoiding facial recognition and classification techniques that would prescribe gender or ethnicity. The blurriness of average images served as a signal of how homogeneous or heterogeneous certain professions were.

**Nearest Neighbors Explorers (BoVW and Colorfulness)**: Two nearest-neighbor lookup tools enabling structured exploration. Users select a specific image (e.g., a photo of a Black woman from a specific TTI system) and explore its neighborhood by colorfulness or by a bag-of-visual-words TF-IDF index. The index was built using a bag-of-visual-words model to obtain image embeddings independent of external pre-training datasets; SIFT features were extracted, quantized via k-means into a codebook representing a visual vocabulary, and TF-IDF sparse representations were computed and indexed using a graph-based approach. These tools facilitate qualitative exploration in terms of color or structural similarity, useful for detecting stereotypical content—e.g., the abundance of stereotypical Native American headdresses, or professions with predominant colors (firefighters in red suits, nurses in blue scrubs).

Code and instructions for duplicating and adapting these tools to other prompt/image sets are provided to facilitate community dissemination and customization.

<!-- quelle: Interactive Exploration Tools -->

### Limitations and Future Work

The research presents four primary limitations. First, caption and VQA answer models contain uncontrollable biases; the authors mitigate this by comparing multiple models and using less symbolic models such as BoVW. Second, while Stable Diffusion's open nature prevents missing confounding factors, Dall·E 2's API-only access prevents controlling for prompt injection, filtering, or model version changes. Thus, comparisons assume generated images strictly correspond to model outputs based on input prompts. Third, the analysis is restricted to gender and ethnicity, attributes recognized as inherently fluid, multidimensional, and non-discretizable. Fourth, the authors self-position as lacking primary academic backgrounds in relevant social science disciplines and first-hand experiences of the referenced identity characteristics, acknowledging a bias toward discrimination axes relevant to the Western world.

Future work should expand the exploration of societal biases in text-to-image models by investigating additional dimensions of social bias, including:
- age
- visual markers of religion
- other target attributes tied to stereotypes and power dynamics

Future research must account for the complex, interconnected nature of biases and the fact that many attributes cannot be visually inferred from generated images. Finally, future efforts should further develop interactive tools to support qualitative analysis and storytelling around model biases, empowering stakeholders and communities with less technical expertise to engage with and probe TTI systems and other ML artifacts.

<!-- quelle: Limitations and Future Work -->

### References and Supplementary Materials

This section consists solely of a bibliographic reference list (64 entries) and contains no argumentative content. The references span several clusters relevant to the essay's concerns: (1) text-to-image generative model architectures and training (DALL-E 2, Stable Diffusion, Imagen, Make-A-Scene, CLIP, BLIP); (2) bias and fairness in machine learning, including intersectional accuracy disparities (Buolamwini & Gebru), demographic stereotypes in text-to-image generation (Bianchi et al.), gender bias in image captioning (Bhargava & Forsyth; Hendricks et al.), and occupational image search representation (Kay et al.; Metaxa et al.; Singh et al.); (3) critical race and gender studies of algorithmic systems (Benjamin; Hanna et al.; Keyes; Scheuerman et al.); (4) dataset documentation and critique (Birhane et al.; Dodge et al.; Luccioni & Viviano; Blodgett et al.); (5) markedness theory (Andrews) and latent structure of gender (Carothers & Reis); (6) safety and mitigation mechanisms for generative models (Schramowski et al.; Rando et al.; OpenAI; Nichol; Mishkin et al.); (7) data replication and training-data extraction from diffusion models (Carlini et al.; Somepalli et al.); (8) commercial deployment contexts (Shutterstock/OpenAI integration; Adobe AI). No line of argument, conceptual distinctions, author self-positioning, or criteria lists are present in this section.

<!-- quelle: References and Supplementary Materials -->

## GLOSSAR

- **Text-to-Image (TTI) Systems** — An assemblage of components and modules — including safety filters, embeddings, and CLIP-guided training — that collectively contribute to generating the final image, making it difficult to attribute downstream bias to any single module.
- **mode-covering characteristic** — A property of the likelihood-based loss function used in diffusion models that produces diverse outputs compared to other generative model classes.
- **compounded outcome** — A model output where biases from different modalities (e.g., visual and linguistic) combine to produce more negative depictions of certain identity groups than either modality's bias would alone.
- **bias amplification** — A process whereby interventions intended to reduce problematic content (e.g., filtering explicit material) inadvertently increase the model's biased outputs.
- **disparate impact** — A disproportionate negative effect of a technical mechanism (e.g., keyword-based filtering) on already marginalized groups.
- **proxy representations** — Flexible representations of visual features in TTI-generated images used to identify regions of the representation space that viewers may associate with social variation, in lieu of fixed a priori social categories.
- **Visual Question Answering (VQA)** — Models used in the text modality to carry out text-based analysis of correlations between social attributes and identity characteristics in TTI-generated images.
- **TTI systems** — Text-to-Image generation systems whose social biases are audited through controlled prompt variation and multimodal analysis of generated images.
- **Identities dataset** — A dataset of images generated per model for each gender–ethnicity prompt combination, used as a reference ground for analyzing social diversity in system outputs.
- **Professions dataset** — A dataset of images generated per model for each of 146 BLS occupations, evaluated for social diversity without explicit identity label assignment.
