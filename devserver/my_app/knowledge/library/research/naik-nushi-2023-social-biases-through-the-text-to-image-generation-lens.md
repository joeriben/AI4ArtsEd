---
id: naik-nushi-2023-social-biases-through-the-text-to-image-generation-lens
titel: Social Biases through the Text-to-Image Generation Lens
autor: "Ranjita Naik, Besmira Nushi"
jahr: 2023
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, bias]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2304.06034"
status: published
analyzed_at: "2026-07-31T11:36:20.476812+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Social Biases through the Text-to-Image Generation Lens

## PROFIL

The text argues that Text-to-Image (T2I) generation models like DALLE-v2 and Stable Diffusion function as a confirmatory process that propagates severe social biases, constituting a major setback on representational fairness relative to search engines and labor statistics. It sets itself against the framing of these models as neutral productivity tools and against prior image search studies by demonstrating that generative systems amplify occupational and demographic stereotypes beyond real-world distributions. By quantifying biases across gender, race, age, and geographical location through default neutral and expanded prompts, the study reveals that prompt specification only partially mitigates representational exclusion and image quality discrepancies. For arts education, this research provides a critical framework for understanding how inherited dataset biases manifest in AI-generated visual culture, necessitating critical prompt engineering and media literacy when integrating generative tools into creative curricula.

## WISSEN

### Problem Framing and Thesis: Social Biases in Text-to-Image Generation

Models trained on large, non-curated, partially non-public web data inherit dataset biases—lack of representation for minority groups and cultures, harmful content. These biases resurface in AI-generated content, creating a **confirmatory process** that propagates known issues and can undo prior mitigation efforts.

The thesis: systematically quantify **representational biases** in large vision-and-language generation models, informing technology and policy makers about major trends.

For any stereotyped occupation (e.g., CEO, housekeeper), three distributional views exist: (i) real-world distribution across gender, race, age per labor statistics; (ii) search engine result distributions; (iii) image generation result distributions. Comparing these reveals that T2I models produce a major setback on **representational fairness** relative even to Google Image Search and U.S. Bureau of Labor Statistics data. Concrete evidence: DALLE-v2 generates nearly 0% women for CEO and computer programmer; Stable Diffusion generates nearly 100% women for nurse and housekeeper—amplifying occupational stereotypes beyond what either search engines or labor data reflect.

The study takes a multi-dimensional approach: examining how occupations, personality traits, and everyday situations are depicted across perceived gender, age, race, and geographical location, using both automated and human evaluation on DALLE-v2 and Stable Diffusion.

<!-- quelle: Problem Framing and Thesis -->

### Introduction and Methodology Overview

Text-to-Image (T2I) models (DALLE-v2, Stable Diffusion, Imagen) are trained on massive Internet-crawled datasets—proprietary ones undisclosed, open-source ones such as LAION-400/-5B—raising fairness concerns. This study examines DALLE-v2 and Stable Diffusion v1 across four social bias dimensions: **gender**, **race**, **age**, and **geographical location**. Prompts describe occupations, personality traits, everyday situations, and the bare prompt "person."

Two prompt strategies serve distinct analytical purposes. Default neutral prompts (no specified gender/age/race) expose bias without prompt-crafting interference—critical when model embeddings are reused for classification or question answering. Expanded prompts (e.g., "a male housekeeper," "a black engineer") estimate mitigation effectiveness for generation/search diversification.

For everyday situations, both default and location-specific prompts are used across categories: events, food, institutions, clothing, places, community. Locations are the top-2 most populated countries per continent (excluding Antarctica); distance between default and location-specific generations measures country representation.

Both models exhibit major but divergent biases. DALLE-v2 overrepresents white men aged 18–40; Stable Diffusion v1 generates more white women and is more age-balanced. Both reinforce stereotypical occupational and personality-trait associations, with DALLE-v2 showing more extreme exclusion of certain genders/races. Prompt expansion can diversify results, yet sometimes fails or introduces image-quality discrepancies between gendered prompts. Geographically, Nigeria, Ethiopia, India (Stable Diffusion only), Papua New Guinea, and Colombia are farthest from default generations; USA, Australia, and Germany are closest.

<!-- quelle: Introduction and Methodology Overview -->

### Related Work and Demarcation

Prior work on image search reveals gender and racial bias: occupational queries slightly magnify gender stereotypes, underrepresent women (an occupation with 50% women in BLS data yields ~45% women in results), and depict the less represented gender less professionally; follow-up studies confirm women remained underrepresented in 2020 and individuals of color were also underrepresented. This work demarcates itself by studying text-to-image generative models instead, arguing these models are a step back on representational fairness and exhibit more severe biases than image search.

Two representative generation approaches are studied: DALLE-v2, which runs denoising in pixel space (computationally intensive, high memory), and Stable Diffusion, which runs denoising in latent space (enabling low-cost GPU generation).

Study results across bias subjects:

- **Person**: DALLE-v2 overrepresents males (70%); SD overrepresents females (66%). Both overrepresent white individuals (≥70%). SD shows more age diversity; DALLE-v2 skews young (76% aged 18–40).
- **Occupations**: Both models accentuate gender underrepresentation of women vs. BLS data in several occupations; only 8 (DALLE-v2) and 7 (SD) of 43 occupations have female proportions within +5% of labor statistics. Black workers have zero representation in 72% (DALLE-v2) and 37% (SD) of occupations; some race groups are over/underrepresented by ≥20%. Age distributions vary by occupation, with 18–40 dominating many roles and 40–60 or 60+ dominating others.
- **Expanded prompts**: Gendered, race-specific, and age-specific prompts do not fully mitigate bias; DALLE-v2 still produces opposite-gender images (5%), white individuals for black-race prompts, and seniors for junior-age prompts. SD ignores specificity prompts more frequently than DALLE-v2.

<!-- quelle: Related Work and Demarcation -->

### Methodology: Bias Dimensions and Subjects

The study annotates discrete perceived attributes of computer-generated people, acknowledging that real-world attributes are often continuous and socially constructed.

**Bias Dimensions:**
- *Gender*: A simplistic binary specification (male/female) is used; the authors acknowledge it excludes nonbinary definitions but enables detection of traditional male-vs-female biases in image generation.
- *Age*: Four groups — "Child or minor", "Adult 18-40", "Adult 40-60", "Adult over 60".
- *Race*: Seven categories from the FairFace study — White, Black, Indian, East Asian, Southeast Asian, Middle East, Latino. Race (physical characteristics) is distinguished from ethnicity (cultural background); both are recognized as continuous and intersectional despite the categorical operationalization.

**Bias Subjects (four prompt types):**
- *Person*: The prompt "person" assesses representation bias.
- *Personality traits*: Trait adjectives from Abele et al., uniform in valence and frequency across languages; partitioned into positive/negative for analysis (full list in appendix Table 7).
- *Occupations*: Generated distributions are compared against US Bureau of Labor and Statistics (BLS) 2022 estimates. The authors caution that matching BLS data only indicates the model does not *amplify* existing real-world bias, not that representation is fair; the reference is US-specific. Minor changes to a prior list [18] were made for BLS data availability. Abbreviations: CP (Computer Programmer), PST (Primary School Teacher), CSR (Customer Service Representative).
- *Everyday situations*: Generic and location-specific prompts across categories (events, food, institutions, clothing, places, community). Location-specific prompts use the two most populous countries per continent: The United States of America, China, India, Nigeria, Ethiopia, Russia, Germany, Mexico, Brazil, Colombia, Australia, Papua New Guinea. Template: "a [situation] in [country]". Country-based adjectives were rejected because they produced flag-dominated images.

Prompt engineering revealed DALLE-v2 performed best with "a portrait of a [prompt]" and SD V1 with "a photo of a [prompt]"; quality criteria required generation of salient human faces rather than non-related content, drawings, or obscured figures. Expanded prompts with explicit gender, race, or age modifiers were used to test mitigation effectiveness.

<!-- quelle: Conceptual Framework: Bias Dimensions and Subjects -->

### Model, Data, and Evaluation Methodology

Images were generated via OpenAI's DALLE-v2 API and Stable Diffusion V1. For prompts about persons, occupations, and traits, the first 50 human-containing images per prompt were retained; for everyday-circumstance and explicit demographic prompts, 250 images were collected to support automated evaluation. Human presence was detected using Azure Cognitive Services Analyze Image API (checking non-empty "faces" or human-referencing "tags") and FairFace.

Human evaluation used Amazon Mechanical Turk: three Master-qualified workers per image, majority agreement taken as ground truth; if all three disagreed, the image was labeled "unclear" and excluded. Annotators indicated whether images contained cartoons, humans, or no humans, plus gender, race, and age. 37 FairFace examples with ground-truth annotations were provided for calibration.

Automated evaluation employed FairFace's pre-trained ResNet model (ADAM optimizer, learning rate 0.0001) with dlib's CNN face detector. FairFace defines seven race groups, reproduced in full and in order:
- White
- Black
- Indian
- East Asian
- Southeast Asian
- Middle Eastern
- Latino

For everyday-situation prompts, average CLIP embeddings across generated images were computed for default and location-specific prompts; distance between them was visualized as a heat map (lower distance = closer to default representation). A histogram showed countries represented least and most across everyday-situation categories.

<!-- quelle: Methodology: Model, Data, and Evaluation -->

### Representational Bias of Person and Neutral Occupations in T2I Models

Using BLS 2022 labor statistics as a baseline and comparing with GIS 2020 Image Search results, the study evaluates gender, race, and age distributions across images generated by DALLE-v2 and Stable Diffusion (SD) for the prompt "person" and for neutral occupation prompts. Human evaluation is used for neutral prompts, with gender/race/age labels assigned by majority vote across three annotators; ambiguous images are labeled 'unclear'.

For the prompt "person," DALLE-v2 shows a male bias (70% male vs. 30% female) while SD shows a female bias (66% female vs. 28% male). Both models skew heavily toward white individuals (≥70%). DALLE-v2 omits East Asian, Southeast Asian, and Middle Eastern individuals; SD omits Latino and Middle Eastern individuals. DALLE-v2 skews young (76% aged 18–40).

Prompts were excluded if they fell into any of the following categories:
- Prompts whose generated images contained too few individuals (e.g., 'a garbage collector,' 'a truck driver' yielding objects rather than people)
- Prompts that consistently resulted in images where the face was obstructed by equipment (e.g., cameras blocking photographers' faces)
- Prompts that consistently resulted in caricatures that did not clearly depict race and age (e.g., 'a tax collector')

After filtering, 44 occupations remained. For gender, DALLE-v2 reinforces under-representation of women in occupations such as technical writer, optician, bartender, and bus driver, and over-representation in customer service representative, primary school teacher, and telemarketer; only 8 of 43 occupations fall within ±5% of BLS. SD reinforces under-representation for technical writer, bartender, telemarketer, and custodian, and over-representation for PR person, pilot, police officer, and author; only 7 of 43 fall within ±5% of BLS. Correlations with BLS are 0.84 (DALLE-v2) and 0.87 (SD).

For race, DALLE-v2 under-represents white individuals by >50% for childcare worker, announcer, nurse, and housekeeper; only pilot and primary school teacher match BLS. In 72% of DALLE-v2 occupations, black representation is zero; for SD, 37% of occupations show zero black representation. For age, DALLE-v2 skews 18–40 for administrative assistant, customer service representative, receptionist, electrician, and nurse (≥96%), while 40–60 dominates truck driver and CEO (≥78%), and over 60 is prominent for clergy member and tax collector. SD skews 18–40 for bartender, computer programmer, telemarketer, and electrician (≥98%), 40–60 for CEO, custodian, and clergy member (≥60%), and over 60 for bus driver.

<!-- quelle: Results: Person and Neutral Occupations -->

### Expanded Prompts and Image Quality

The section argues that expanded prompts—adding gender, race, or age specifications to occupational prompts—are insufficient to mitigate bias in AI image generation, and that even when effective, they introduce new biases and quality discrepancies. 

**Prompt insufficiency.** Gender-specific prompts fail reliably: DALLE-v2 produces 5% counter-gender images for both male-dominated and female-dominated occupations (e.g., "male childcare worker" → female images; "female security guard" → male images). Race prompts similarly fail ("black mail carrier" → ≥9% white individuals). Age prompts also fail ("a junior receptionist" → 4% seniors). SD exhibits the same patterns at higher rates: "a female police officer" yields 24% male images; "a male administrative assistant" yields 60% female images; "a Middle Eastern special ed teacher" yields 17% white and 21% Indian individuals. SD ignores gender, race, and age prompts more frequently than DALLE-v2. The expansion strategy itself introduces new biases.

**Quality discrepancies.** Using FID scores (lower = closer resemblance to real-world image search results), gender-skewed representations exhibit better image quality. Male-dominated occupations (CEO, crane operator, roofer, bus driver) score better FID than their female-prompted counterparts; female-dominated occupations (nurse, childcare worker, primary school teacher, administrative assistant) score better FID than their male-prompted counterparts. The prompt "female announcer" illustrates that DALLE-v2 outputs lack diversity—predominantly East Asian individuals—which may drive worse FID scores. 

**Conclusion.** Expanded prompts alone cannot resolve bias; complementary strategies such as duplicate prompting and output filters are necessary.

<!-- quelle: Results: Expanded Prompts and Image Quality -->

### Representational bias for personality traits

Due to the SD model generating non-human images for over 50% of certain personality trait prompts, the study was restricted to DALLE-v2, with results based on human evaluation. Gender representation shows a split between competence and warmth: traits such as "intelligent," "strong-minded," and "rational" are primarily attributed to men, while women are associated with warm traits like "affectionate," "warm," and "sensitive."

Traits with 100% male representation:
- boastful
- energetic
- egoistic
- dogmatic
- decisive
- rational
- strong-minded
- striving
- industrious
- intelligent
- gullible
- moral
- reliable
- self-critical

Traits with female representation ≥ that of male:
- sensitive
- affectionate
- harmonious
- supportive
- warm

Categorizing traits into positive and negative groups reveals racial associations. The white race is linked to positive traits ("competent," "active," "rational," "sympathetic") but less to "ambition," "vigorous," and "striving"; it is strongly linked to negative traits ("dominant," "egoistic") but less to "detached" and "hardheaded." The black race associates most with "ambitious" and "determined," while the east Asian race associates with "vigorous" and "detached."

Age groups show distinct trait associations: prompts for caring and altruistic behaviors generate individuals over 60; rationality and tolerance generate individuals aged 40–60; laziness, ambition, and perfectionism generate individuals aged 18–40.

<!-- quelle: Results: Personality Traits -->

### Representational Bias for Everyday Situations

Everyday situations were analyzed using CLIP embeddings across six categories: **events, food, institutions, clothing, places, and community**. The study covered 12 geographic locations—the two most populated countries per continent. Distance between default and location-specific generations served as a metric for assessing country representation: lower distance indicates closer alignment with the default generation, revealing which countries are better represented in default outputs.

The events category (Figures 13–14) illustrates this distance metric per country. The reported FID = 201 for default generations.

A case study on announcer portraits demonstrates how bias operates intersectionally and how mitigation strategies trade one bias for another:

- **"a portrait of an announcer"** (default): produces bias toward male individuals, indicating gender bias in default generation.
- **"a portrait of a female announcer"** (prompt expansion mitigation): addresses gender bias by specifying female, but introduces racial bias. FID = 237.
- **"a portrait of a male announcer"**: shows improved racial representation compared to the female-specified prompt, suggesting that prompt expansion does not uniformly resolve bias across demographic dimensions.

The argument's movement: default generations carry representational bias (gender); a mitigation strategy (prompt expansion) can correct one dimension (gender) while activating another (race); and the correction is asymmetric—specifying male yields better racial diversity than specifying female, exposing how bias compounds across intersectional axes rather than resolving linearly.

<!-- quelle: Results: Everyday Situations -->

## GLOSSAR

- **confirmatory process** — A feedback loop whereby biases in training data resurface in generated content, reinforcing and propagating the same biases that prior mitigation efforts sought to address.
- **representational biases** — Systematic skews in how social groups are depicted across dimensions such as gender, race, age, and geographical location in model outputs.
- **representational fairness** — The degree to which T2I model outputs reflect balanced proportions across social-bias dimensions such as gender, race, age, and geographical location.
- **default neutral prompts** — Prompts that do not specify gender, age, or race, used to analyze baseline model bias without the influence of prompt crafting.
- **prompt expansion** — Augmenting a neutral prompt with explicit social-dimension attributes (e.g., gender or race) to test mitigation of bias and diversification of generated results.
- **pixel space** — The domain in which DALLE-v2 performs denoising by manipulating individual pixels, requiring significant memory and computation.
- **latent space** — The compressed representational domain in which Stable Diffusion performs denoising, enabling high-quality generation on low-cost GPUs.
- **FairFace study** — A prior study providing the seven-category race classification (White, Black, Indian, East Asian, Southeast Asian, Middle East, Latino) adopted here for analytical annotation.
- **BLS 2022** — US Bureau of Labor and Statistics 2022 occupational estimates used as a real-world reference distribution for comparing model-generated occupation representations.
- **FairFace** — A dataset of 108,501 images with balanced race composition, labeled for race, gender, and age, used here as both annotation reference and source of a pre-trained classification model.
