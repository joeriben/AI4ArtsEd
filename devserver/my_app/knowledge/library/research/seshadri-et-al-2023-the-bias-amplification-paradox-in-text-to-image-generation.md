---
id: seshadri-et-al-2023-the-bias-amplification-paradox-in-text-to-image-generation
titel: The Bias Amplification Paradox in Text-to-Image Generation
autor: "Preethi Seshadri, Sameer Singh, Yanai Elazar"
jahr: 2023
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, bias]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2308.00755"
status: published
analyzed_at: "2026-07-31T11:44:06.503677+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# The Bias Amplification Paradox in Text-to-Image Generation

## PROFIL

The text argues that apparent "bias amplification" in text-to-image models like Stable Diffusion is largely an artifact of distributional differences between training captions and generation prompts, rather than the model actively exacerbating stereotypes. It sets itself against naive evaluations that directly compare gender ratios in training data (LAION) with generated outputs without accounting for the fact that captions often contain explicit gender information while prompts do not. By demonstrating that amplification decreases drastically when comparing comparable distributions, the authors challenge the assumption that models inherently amplify training-data biases. For arts education, this highlights the necessity of critically evaluating the metrics and methodologies used to assess AI-generated imagery, ensuring that representational harms are measured accurately before drawing pedagogical conclusions.

## WISSEN

### Bias Amplification Paradox in Text-to-Image Generation

Bias amplification—where models exacerbate training-data stereotypes—appears pronounced in Stable Diffusion: comparing gender ratios across LAION training images and generated images for occupations yields 12.57% amplification. However, this measurement conflates genuine model behavior with distributional differences between training captions and generation prompts. Training captions frequently contain explicit gender information (e.g., gender indicators), while prompts used to study gender-occupation bias deliberately exclude it. For the occupation *engineer*, captions with gender indicators are 40% female, captions without are 10% female, and generated images are 10% female—so apparent amplification vanishes when comparing against the matched subset.

Two approaches reduce the distribution shift: (1) excluding captions with explicit gender information, and (2) selecting training captions via nearest neighbors on text embeddings to resemble prompts. Both yield considerably lower amplification. Using captions themselves as generation prompts further shows amplification is minimal. The central claim: naively quantifying bias by comparing all training data against generated outputs is misleading; valid amplification measurement requires comparing comparable distributions.

<!-- quelle: Introduction and Problem Framing -->

### Experimental Setup

The study examines bias amplification using Stable Diffusion 1.4 and 1.5, both trained on the 2.3 billion English portion of LAION-5B, a web-scraped image-caption dataset. Gender bias is measured via perceived binary gender classification: images are first filtered for single-face presence using a face detector, then classified by CLIP zero-shot image classification; only predictions with probability ≥ 0.9 are retained to exclude ambiguous cases. This filtering applies to both training and generated images.

The authors acknowledge that classifying binary gender from appearance perpetuates stereotypes and excludes non-binary individuals, but note that inferring non-binary gender from appearance alone risks misrepresenting a marginalized group.

Images are generated using four prompt templates, with [OCCUPATION] replaced across 62 occupations selected to exhibit varying bias levels: male-skewed (e.g., CEO, engineer), balanced (e.g., attorney, journalist), and female-skewed (e.g., dietitian, receptionist) based on training data.

<!-- quelle: Experimental Setup -->

### Methodology for Measuring Bias Amplification

Model bias is measured by generating 500 images per occupation across four deliberately gender-neutral prompts (two specifying 'face'/'portrait'), using varied random seeds. **G_P_o** captures the percentage of females in generated images for prompt P and occupation o. Data bias is measured by querying LAION via WIMBD to retrieve training image-caption pairs whose captions mention the occupation, yielding **T_S_o**, the percentage of females in training subset S for occupation o. The approach assumes training captions reference the occupation.

Bias amplification **A_P_o,S_o** compares G_P_o against T_S_o per occupation, following Zhao et al. (2017). Amplification is prompt- and subset-specific. Expected amplification E[A_P_o,S_o] aggregates across a set of occupations O, then averages across all four prompts. Amplification occurs when an occupation skewing male (or female) in training skews further in that direction in generation; bias decreasing from training to generation constitutes de-amplification. Occupations exhibiting different bias directions at training versus generation are excluded from analysis.

<!-- quelle: Methodology for Measuring Bias Amplification -->

### Naive Approach and Identification of Discrepancies

An initial naive approach samples 500 training captions per occupation and compares gender ratios in training images to those in Stable Diffusion-generated images, finding 12.57% average bias amplification across occupations and prompts. However, qualitative inspection reveals discrepancies between captions and prompts that confound this measurement.

- Captions often include person descriptions, activities, attire, and location (e.g., "smiling young female mechanic inspecting a CV joint"), reducing ambiguity, while evaluation prompts are intentionally underspecified (e.g., "A photo of the face of a/an [OCCUPATION]").
- Explicit gender indicators appear more frequently for underrepresented groups (e.g., female mechanics), hypothesized to shift training-image gender distributions toward balance and thus exaggerate amplification measures.
- Occupations with multiple meanings diverge: training captions for "president" may reference company or organizational presidents, while the model interprets the underspecified prompt as a head of state.

Because captions and prompts differ in specificity and semantic scope, gender-ratio gaps between training and generation cannot be attributed solely to model amplification. The section motivates reducing confounding distribution shifts in subsequent evaluation.

<!-- quelle: Naive Approach and Identification of Discrepancies -->

### Reducing Discrepancies Between Training and Generation

The section evaluates two approaches to reduce train–generation discrepancies by restricting the training-example subset S_o while keeping prompts P_o fixed.

**5.1 Captions Without Explicit Gender Indicators.** 59.5% of captions contain explicit gender information, disproportionately for the underrepresented gender (e.g., 68% of female mechanic captions vs. 30% of male). A negative Pearson correlation (−0.458, p<0.05) between female image percentage and female-indicator caption percentage confirms that gender indicators more often delineate the underrepresented gender, inflating amplification. Filtering to captions without gender indicators reduces average amplification from 12.57% to 8.66% (↓31%).

**5.2 Nearest Neighbors (NN).** Prompts are concise and structured; random captions are diverse and may carry implicit gender cues. Average caption–prompt cosine similarity (Sentence-BERT) is only 0.385. Selecting the top-500 most similar captions raises text similarity to 0.704 (↑83%) and CLIP image-embedding similarity ↑13%. Qualitatively, NN selects structurally prompt-like captions (e.g., 'Picture of a teacher in the classroom'), yielding training images of world leaders or classroom educators rather than heterogeneous examples. Amplification drops to 6.76% (↓46%). The authors acknowledge the text encoder may itself carry biases, motivating the choice of Sentence-BERT over Stable Diffusion's encoder.

**5.3 Combining Approaches.** Combining both methods lowers amplification to 4.35% (3.59% on SD 1.5), with Prompt #1 at 1.11%. A one-sample t-test fails to reject zero amplification for Prompts #1 and #3 but rejects it for #2 and #4, indicating residual confounds. The methods target explicit and implicit gender information in complementary ways; as training subsets increasingly resemble prompts, measured bias converges.

**Table 3 (full, SD 1.4 / SD 1.5):**
- Naive: 10.24/10.87, 17.57/16.36, 10.77/11.15, 11.68/9.91; Avg 12.57/12.07
- No Gender Indicators: 6.49/6.76, 13.58/12.41, 7.09/6.82, 7.49/5.87; Avg 8.66/7.97
- Nearest Neighbors: 3.59/4.01, 12.62/11.14, 5.58/5.21, 5.27/3.65; Avg 6.76/6.01
- NN + No Gender Indicators: 1.11/1.55, 8.72/7.29, 3.06/2.78, 4.05/2.72; Avg 4.35/3.59

<!-- quelle: Reducing Discrepancies Between Training and Generation -->

### Removing Distributional Differences: A Lower Bound

Instead of making captions similar to prompts, this approach modifies prompts to match captions verbatim, using the original training subset (S_o) and setting prompts (P_o) to match S_o. By design, this removes mismatches between captions and prompts. The hypothesis is that enforcing identical texts to measure training and generation bias yields similar bias measurements, reducing amplification. 

Results show amplification is minimal (average 0.68%), with most occupations along the diagonal, though the null hypothesis of 0 amplification is rejected. For captions with gender indicators, the model matches training gender with 98.41% accuracy, so analysis focuses on the subset without gender indicators. Here, amplification is larger but remains low (2.05%, down 84% relative to keyword querying). 

While practitioners are unlikely to use prompts matching training captions—and this is not recommended—this experiment demonstrates the impact of distributional similarity between captions and prompts when comparing biases. It establishes a lower bound for the bias amplification problem: the model nearly mimics biases from the data when prompted with training captions.

<!-- quelle: Removing Distributional Differences: A Lower Bound -->

### Related Work: Pretraining Data, Bias Amplification, and Text-to-Image Bias

Prior work relates pretraining data properties to model behavior, showing few-shot capabilities correlate with pretraining term frequencies and models struggle with long-tail knowledge; causal studies examine how data curation choices affect downstream performance. On bias amplification, Zhao et al. (2017) show structured prediction models amplify data biases, but their setup differs: they jointly predict multiple labels including gender (not generate images) and focus on mitigation, not on factors contributing to amplification. Hall et al. (2022) study how data, training, and model choices influence amplification via synthetic bias in classification, but do not examine distribution shifts. Friedrich et al. (2023) show Stable Diffusion displays bias amplification versus LAION, using text-image similarity (not captions) to identify training examples, and focus on mitigation via fair diffusion rather than analyzing confounding factors. The author positions this work as centered on analyzing confounding factors impacting amplification, against prior emphasis on mitigation. On text-to-image bias, works document geographical disparities, intersectional biases, and stereotype persistence under counter-stereotypical prompting, but primarily evaluate model biases without examining training data. Figure 6 (attorney examples) demonstrates that prompt wording choices produce noticeable differences in the proportion of female-generated images, illustrating prompt-level confounding in amplification analysis.

<!-- quelle: Related Work -->

### Discussion and Conclusion

Naive evaluation procedures exaggerate bias amplification by ignoring distributional differences between training data and generation. The analysis is illustrative rather than exhaustive; future work should test across datasets, models, and bias types.

Small prompt variations drastically alter conclusions: 'A portrait photo of an attorney' skews male while 'A photo of an attorney at work' skews female. Reductions in amplification also vary by prompt (89% vs. 49%), indicating prompt-specific distribution shift.

The authors position amplification relative to training-data bias, not real-world statistics — these answer fundamentally different questions: whether model behavior reflects training data vs. how well data-plus-model reflects reality.

The title alludes to Simpson's Paradox: substantial amplification observed initially reduces drastically after selecting training subsets matching generation conditions and decreasing confounding-factor impact.

Recommendations: data curators should consider how practitioners specify prompts; crowdsourcing or rewriting captions to reflect real-world usage may reduce amplification; evaluations should use multiple prompts and remove prompt-specific confounding factors (e.g., via NN selection of relevant training examples).

Conclusion: Stable Diffusion does not eliminate amplification entirely, but reducing caption-prompt discrepancies yields substantially lower measurements. Any comparison of dataset and model properties must account for distribution shifts that skew evaluations.

<!-- quelle: Discussion and Conclusion -->

### Limitations and Ethics Statement

## Limitations

Analysis compares biases in training data vs. Stable Diffusion outputs but overlooks biases introduced by CLIP text embeddings during prompt encoding. Because CLIP's training data is not public, the impact of this external, frozen component on overall amplification cannot be disentangled. Gender classification is automated via CLIP, which aligns with human annotations and achieves >95% accuracy on FairFace across racial categories, yet inherits biases from its own training data.

## Ethics Statement

Proposed approaches to reduce distribution shifts during evaluation do not resolve underlying gaps between training data and user interaction; they serve to deepen understanding of why models amplify biases, motivating future work on nuanced evaluation and data-level remedies. Bias analysis is narrowly scoped to gender-occupation stereotypes; models also exhibit racial, age, geographical, socioeconomic, disability, and intersectional biases requiring evaluation. Only binary gender is considered, ignoring non-binary identities and relying on appearance and facial features to infer gender, which can propagate stereotypes. Captions and prompts are English-only; the gender-guesser library likely performs worse on non-Western names, impacting identification of captions with gender information.

<!-- quelle: Limitations and Ethics Statement -->

## GLOSSAR

- **bias amplification** — A phenomenon where models exacerbate biases or stereotypes present in the training data beyond what the data itself exhibits.
- **distribution shift** — The discrepancy between the text distributions of training captions and generation prompts that inflates apparent bias amplification measurements.
- **LAION-5B** — A public dataset of 5 billion image-caption pairs scraped from the web, used to train Stable Diffusion.
- **zero-shot image classification** — CLIP's capability to classify images into categories without task-specific training examples.
- **G_P_o** — Percentage of females in generated images for a prompt P describing an occupation o.
- **T_S_o** — Percentage of females in a training subset S corresponding to occupation o.
- **A_P_o,S_o** — Bias amplification for occupation o, computed by comparing G_P_o against T_S_o for a specific prompt and training subset.
- **underspecification** — The deliberate lack of descriptive detail in evaluation prompts, leaving the model to interpret vague textual inputs.
- **gender indicators** — Explicit gender markers in training captions, hypothesized to appear more often for underrepresented groups.
- **nearest neighbors (NN)** — A caption-selection method that chooses training examples whose text embeddings are most similar to the fixed prompt embedding.
