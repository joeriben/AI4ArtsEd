---
id: bianchi-et-al-2023-easily-accessible-text-to-image-generation-amplifies-demographic-stereotypes
titel: Easily Accessible Text-to-Image Generation Amplifies Demographic Stereotypes at Large Scale
autor: "Federico Bianchi, Pratyusha Kalluri, Esin Durmus, Faisal Ladhak, Myra Cheng, Debora Nozza, Tatsunori Hashimoto, Dan Jurafsky, James Zou, Aylin Caliskan"
jahr: 2023
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, bias]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2211.03759"
status: published
analyzed_at: "2026-07-31T11:09:49.020731+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Easily Accessible Text-to-Image Generation Amplifies Demographic Stereotypes at Large Scale

## PROFIL

The text argues that text-to-image models (Stable Diffusion, Dall·E) perpetuate and amplify dangerous stereotypes through ordinary prompts containing traits, occupations, or objects, regardless of demographic language or mitigation strategies. It sets itself against the assumption that neutral prompts avoid bias—an ideology akin to "colorblindness"—and the efficacy of institutional guardrails or user counter-stereotyping. The authors demonstrate "stereotype amplification" where generated images exaggerate real-world demographic disparities, such as mapping attractiveness to a "White ideal." For arts education, the text provides a critical framework for analyzing how AI-generated imagery encodes systemic biases, emphasizing the limitations of technical fixes in creative tools.

## WISSEN

### Problem framing and thesis

Text-to-image models (Stable Diffusion, Dall·E) are used by millions daily, trained on massive web-scraped datasets known to contain stereotyping content. The thesis: a broad range of ordinary prompts—traits, descriptors, occupations, objects—produce stereotypes regardless of whether demographic language is used. Stereotypes persist despite both user interventions (careful prompting, explicit counter-stereotyping) and institutional interventions (system 'guardrails'). For occupations with comparable real-world demographics, the model exhibits **stereotype amplification**: e.g., 99% of generated software developer images appear white versus 56% in U.S. reality. Prompts like *an attractive person* approximate a 'White ideal'; *a terrorist* generates brown faces with beards; household-object prompts implicitly associate non-American nationalities with poverty. The authors adopt a mixed-methods orientation foregrounding striking exemplars and qualitative analysis, arguing this is necessary because the phenomenon is not yet well-theorized and because exemplifying imagery motivates protective action more effectively than base-rate quantification alone. They explicitly position the paper as not surveying model strengths or identifying optimal mitigation—given the rapidly shifting deployment landscape—but as characterizing the nature and extent of propagating harm.

<!-- quelle: Problem framing and thesis -->

### Neutral prompts perpetuate and amplify stereotypes

The section argues against the belief that prompts avoiding identity descriptors also avoid stereotypes—akin to the criticized ideology of "colorblindness." Using Stable Diffusion, the prompt "A photo of the face of [DESCRIPTOR]" was tested across ten common human descriptors, generating 100 images each. Results show neutral descriptors reproduce harmful stereotypes by entangling them with visual features associated with demographic groups: attractiveness maps to the "White ideal" (blue eyes, pale skin, straight hair); emotionality and seductiveness map to white feminine features; cleaning yields feminine faces; "exotic" produces darker skin, non-European adornment, and Afro-ethnic hair; "poor person," "thug," and "person stealing" generate dark-skinned faces with stereotypically Black features; "terrorist" yields brown faces with dark hair and beards; "illegal person" produces brown faces. Some prompts are inherently harmful—generating "the face of a poor person" assumes race and class are visually immutable. Social-structure descriptors ("a happy couple," "a happy family") reinforce heteronormative institutions, contributing to minority stress for LGBTQ+ identities.

<!-- quelle: Stereotypes in neutral prompts: traits and descriptors -->

### Stereotype amplification in occupations

Stereotype amplification is the process whereby real-world correlations between social identities and social roles become distorted and exaggerated, possibly to the point of being perceived as ubiquitous. Prior work shows language models can amplify biases beyond training-data or real-world rates. Because the foundational training dataset was constructed in the U.S. and ML representations reflect American norms and inequities, the analysis quantifies amplification of U.S. social associations—specifically the link between official demographic categories (Male/Female, White/Black/Asian) and occupation.

Method: for each of ten occupations, the prompt 'A photo of the face of [OCCUPATION]' generates 100 images. To assess gender/race representation, archetypal CLIP vectors for each demographic category are constructed by averaging CLIP image-encoder outputs over the corresponding Chicago Face Dataset slice; a generated image is classified as a category when its representation is closest in cosine distance to that category's archetypal vector. Results are compared to U.S. Bureau of Labor Statistics demographics.

Findings: neutral occupation prompts produce gender and racial imbalances exceeding national statistics. Several occupations exhibit total amplification—housekeeper, nurse, and flight attendant are 100% female. Amplification is unevenly distributed in ways that compound social hierarchies: higher-income occupations (software developer, pilot) skew heavily white and male; lower-income occupations (housekeeper) skew non-white and female. The cook/chef contrast is illustrative: although a higher percentage of cooks than chefs self-identify as white, the model suppresses white cooks and non-white chefs, representing most cooks as non-white and most chefs as white.

This shows stereotype amplification perpetuates societal notions of prestige and whiteness rather than merely exaggerating existing imbalances. The erasure of minority groups from prestigious occupations produces allocational harms—via stereotype threat (performance impaired by fear of confirming negative stereotypes) and direct stereotype influence (allocation of benefits determined by pervasive stereotypes)—and representational harms.

<!-- quelle: Stereotype amplification in occupations -->

### Defaulting to Americanness in object prompts

The section argues that Stable Diffusion encodes American cultural norms even in images of non-human objects, not only in representations of demographic groups. Against the hope that object-only generation avoids bias, it demonstrates that seemingly neutral prompts default to North American visual norms.

Using household objects from De Vries et al. (2019), the authors generate 100 images per object under four prompts: a general prompt ('a photo of [OBJECT]'), and North-America-, Asia-, and Africa-specific variants. Visual inspection shows general-prompt outputs most resemble North-America-specific images and differ most from Africa-specific ones, which encode stereotypes of poverty.

To quantify this, they feed continent-specific prompt images through CLIP's image encoder, average embeddings into archetypal continent vectors, then measure cosine distance from each general-prompt image to each continent vector. Results confirm: for 100% of backyards, 96% of kitchens, 99% of front doors, and 99% of armchairs, general-prompt images are closest to the North America vector.

This reflects American-dominated internet datasets, not real-world population distribution. The effect constitutes a 'view from nowhere' — concealing a specific perspective as neutral — which sociologists have long criticized for excluding non-default groups.

<!-- quelle: Defaulting to Americanness in object prompts -->

### Stereotyping representations of groups with identity language

Prompts containing explicit identity or demographic references produce images imbued with multiple layers of identity-based stereotypes; moreover, stereotypes persist even when prompts explicitly request counter-stereotypical images. When prompting with identity language, a wide spectrum of visual components—people, objects, and background—can all reinforce systemic disadvantages. The examples are unique in how they encode bias but consistent in doing so. Comparing generated images of 'a photo of [NATIONALITY] man with his car,' the American man's car appears shiny and new while cars for other nationalities appear broken and in bad condition, despite no such difference being stated in the prompt. Outputs of '[NATIONALITY] man' or '[NATIONALITY] man with his house' produce similar patterns, reinforcing narratives that African countries like Ethiopia are defined by poverty and Middle-Eastern countries like Iraq cannot be defined apart from involvement with war. These cases demonstrate how identity terms in language are reflected into vision in nuanced ways. The same disadvantaging patterns appear in generations of household objects (Section 2.3), where objects reflect stereotypes about different continents. These examples touch the surface of the pervasiveness of stereotypes being perpetuated, which deserve systematic assessment.

<!-- quelle: Stereotyping representations of groups with identity language -->

### Persistence of stereotypes despite counter-stereotype prompting

Targeted prompt modifiers are a proposed mitigation strategy, but the section demonstrates they frequently fail to eliminate stereotypical outputs in Stable Diffusion. Adding 'from diverse cultures' can diversify some neutral occupations (software developer, flight attendant), yet descriptors like 'exotic' and 'terrorist' still yield darker skin tones and Middle-Eastern features; the phrase is hypothesized to mean diversity relative to an American default of whiteness. Explicit counter-stereotype modifiers also fail: 'a white poor person' still produces dark-skinned faces with only incidental whiteness markers (blue eyes); 'a white terrorist' still produces long beards associated with Middle-Eastern men. The model cannot disentangle poverty from Blackness or terrorism from Middle-Eastern identity. Wealth modifiers fail similarly: 'an African man and his fancy house' and '...his mansion' both still generate simple huts; 'a wealthy African man and his house' keeps the hut but adds a Western suit, conflating wealth with Western society. Google Image Search returns an African man in opulent African clothing before an ornate house, showing Stable Diffusion exceeds even stock-photo levels of stereotyping. Colonial power relations persist despite well-intentioned prompts.

<!-- quelle: Persistence of stereotypes despite counter-stereotypes -->

### Persistence of stereotypes despite institutional guardrails

OpenAI's DALL·E mitigation approach centers model owners through 'guardrails'—filtering, balancing, and blocking dangerous prompts—whose exact mechanisms remain undisclosed, leaving unknown what domains, notions of bias, or fairness they address. Despite these guardrails, complex, dangerous biases persist.

Reproducing the everyday-objects experiment, DALL·E mirrors Stable Diffusion: unspecified prompts default to North American aesthetics, while 'Africa' prompts reinforce poverty narratives. Guardrails do ensure skin-tone diversity for occupation prompts—likely because occupational biases are well-studied in CS bias scholarship and explicitly addressed. However, subtler biases, those studied in other disciplines, and biases beyond gender and race persist.

'African man standing next to a house' yields worn-down houses versus 'American man'; generating both simultaneously produces an American house in good condition. The model cannot disentangle constructed concepts of race, nation, and wealth.

'a disabled woman leading a meeting' depicts disabled persons listening rather than leading; replacing 'disabled' with 'blonde' resolves this, deepening existing ableism. 'a happy couple' and 'a happy family' reinforce heteronormative ideals. These biases persist despite explicit counter-stereotypes and identifiers in prompts.

<!-- quelle: Persistence of stereotypes despite institutional guardrails -->

### Conclusion and outlook

Image generation models embed dangerous biases that surface with the mere mention of social groups, descriptors, roles, or objects. Given their widespread daily use, concern is justified; anticipating, quantifying, or mitigating all such biases is challenging or impossible, partly due to the multifacetedness of social identity—countless axes and intersections of social groups. The argument sets itself against reductionist computational approaches and against the assumption that better prompts can solve the problem: images encode and display information beyond prompt specifications, so even carefully curated prompts promoting diversification cannot subvert undesired stereotypes. Nor can end users be expected to prompt carefully. The authors state: "We cannot prompt-engineer our way to a more just, inclusive and equitable future."

Mitigation is uniquely challenging because: (1) generated images necessarily contain aspects not explicitly specified in the prompt, adhering to training-data norms; (2) images contain far more dimensions than text, packing subtle meaning; (3) propagated biases fall beyond current bias metrics and mitigation efforts; (4) automated image-scanning methods lag far behind text-based ones; (5) biases depend on both linguistic characteristics and visual-domain components, so no principled, generalizable mitigation strategy exists. The authors urge caution against real-world downstream applications and call for a critical view: these models, while appearing powerful, are "brittle and extremely limited in the worlds they will create."

<!-- quelle: Conclusion and outlook -->

### Acknowledgments and references

Funding sources: Hoffman-Yee Research Grants Program; Stanford Institute for Human-Centered Artificial Intelligence; SAIL Postdoc Fellowship (ED); NSF CAREER Award (JZ); NSF Graduate Research Fellowship DGE-2146755 and Stanford Knight-Hennessy Scholars fellowship (MC); Open Philanthropy, including an Open Phil AI Fellowship (PK); U.S. National Institute of Standards and Technology (NIST) Grant 60NANB20D212T. Authors' views do not necessarily reflect those of NIST.

The reference list spans social psychology of stereotyping and implicit bias (Amodio & Devine; Goff et al.), critical race and whiteness studies (Bonilla-Silva; Frankenburg; Lewis), feminist and decolonial theory (Haraway; Ferdinand; Liboiron), algorithmic fairness and bias in ML systems (Bender et al.; Noble; De-Arteaga et al.; Cheng et al.), text-to-image generative model evaluation (Bansal et al.; Cho et al.; OpenAI DALL·E 2 documentation), qualitative research methodology (Becker; Berg; Merriam & Grenier), and intersectional analyses of gender, ethnicity, sexuality, and religion (Ghavami & Peplau; Nadal et al.; Meyer; Nagel).

<!-- quelle: Acknowledgments and references -->

## GLOSSAR

- **stereotype amplification** — The process by which real-world correlations between social identities and social roles become distorted and exaggerated, possibly to the point of ubiquity.
- **guardrails** — OpenAI's filtering, balancing, and prompt-blocking mechanisms intended to mitigate stereotypes in DALL·E, whose exact workings are not fully disclosed.
- **colorblindness** — Ideology holding that avoiding racial language in discourse prevents racial bias, criticized for perpetuating racism.
- **White ideal** — Standard of attractiveness defined by features such as blue eyes, pale skin, and long straight hair.
- **minority stress** — Disproportionate stress experienced by marginalized groups due to homogenizing stereotypes, stigma, and discrimination.
- **stereotype threat** — A mechanism of allocational harm wherein one's performance is affected by the thought of confirming negative stereotypes about one's own identity.
- **direct stereotype influence** — A mechanism of allocational harm wherein allocation of benefits is substantially determined by pervasive stereotypes.
- **view from nowhere** — The concealing of a culturally specific perspective under the guise of neutrality, thereby positioning a dominant group's norms as universal default.
- **identity language** — Explicit references to identity or demographic categories within a prompt.
- **counter-stereotypical** — Image content that runs against expected stereotypical associations for a given identity group.
