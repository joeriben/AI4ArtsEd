---
id: offert-phan-2023-a-sign-that-spells-dall-e-2-invisual-images-and-the-racial-politics-of-feature-space
titel: "A Sign That Spells. DALL·E 2, Invisual Images and The Racial Politics of Feature Space"
autor: "Fabian Offert, Thao Phan"
jahr: 2023
sprache: en
tier: R
sparten: [medial]
themen: [ai, bias, aesthetic_education]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2211.06323"
status: published
checks: passed
review: passed
analyzed_at: "2026-11-15T11:44:33.187711+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: gedruckt
---

# A Sign That Spells. DALL·E 2, Invisual Images and The Racial Politics of Feature Space

## PROFIL

Written by Fabian Offert (University of California, Santa Barbara) and Thao Phan (Monash University), this scholarly article investigates the politics of visual culture created by generative machine learning, with DALL·E 2 and similar models as its central case. Its thesis is that such systems work through inhuman, invisual, and opaque operations of feature extraction and semantic compression, yet remain trapped in a human contradiction: whiteness keeps reappearing as a latent feature of the dominant visual culture they absorb. The article reconstructs the model's history from CLIP (Radford et al. 2021) and Katherine Crowson's CLIP-guided diffusion to DALL·E 2's restricted launch on April 6, 2022, and its commercialization; it then analyzes OpenAI's July 18, 2022 debiasing method, exposed by Andy Baio's "a sign that spells" experiment as the silent appending of gendered and racialized keywords to prompts. Further sections argue that foundation models are treated as finished, total accounts of visual culture, drawing on Louise Amoore (2022) on machine learning political orders and on the Stable Diffusion team's boast (Mostaque 2022) as evidence of semantic compression as a cultural technique; that whiteness survives intact within feature space, defined via Moreton-Robinson (2020) as the benchmark against which differences are normalized, with the blank sign as a method of exposing whiteness as the default, in resonance with Fanon, Hayles, Haraway, Jackson, and Weheliye; and that OpenAI's answer, following Sara Ahmed (2012), amounts to a self-interested liberal multiculturalism that manages difference so commerce can proceed. The conclusion holds that critique must evolve alongside the technology: the task is to pinpoint the distinct technical forms whiteness takes as a machinic concept, a task falling within the expertise of scholars of culture, since prompting and metalanguage are consequential. The article is usable in arts education contexts addressing media arts, digital culture, critical race and whiteness studies, machine learning aesthetics, and critical data studies.

## WISSEN

### A Sign That Spells (p. 1)

In this article, Fabian Offert (University of California, Santa Barbara) and Thao Phan (Monash University) investigate the new politics of visual culture created by generative machine learning, taking DALL·E 2 and similar models as their central case. Their thesis is that such systems work by extracting features and compressing meaning—operations that are inhuman, invisual, and opaque—yet they remain trapped in a distinctly human contradiction: whiteness keeps reappearing as a latent feature of the dominant visual culture they absorb. OpenAI's unsuccessful attempt to remove bias from DALL·E 2 serves the authors as an entry point for analyzing how these systems break down and then rebuild concepts such as race. The urgency of the argument lies in a transitional moment: foundation models are redrawing what counts as visual culture, while anti-racist work is reduced to hasty technical patches aimed at easing discomfort or protecting commercial interests.

The article reconstructs the model's history. OpenAI launched DALL·E 2 on April 6, 2022, offering it only as a restricted API to a small group of researchers and industry practitioners. The launch capped a series of public experiments in prompt-guided image generation that began when CLIP (Radford et al. 2021) appeared in January 2021 and continued when the AI/generative artist Katherine Crowson developed CLIP-guided diffusion roughly a year afterwards. OpenAI built on these architectural ideas, adding enormous corporate data resources, and produced a model capable of generating images at a level never seen before. Because the results were so realistic, public debate moved away from anxieties about large language models toward anxieties about large image models: deep fakes with political content, fabricated celebrity pornography, ways around copyright, and above all racial bias.

At launch, OpenAI had already published a document (OpenAI, 2022a) describing its mitigation measures, and access stayed limited until the model was commercialized months later. Then, on July 18, 2022, OpenAI announced it was rolling out a new method intended to make DALL·E's images of people better mirror the world's demographic variety (OpenAI, 2022b). The company never explained what this method was, but anyone comparing outputs before and after that date would have noticed that gender and race attributes were distributed more evenly in images of people. Because the trained model is opaque and its training data is proprietary, observers could only guess that OpenAI had refined its sampling procedures or genuinely altered the learned attribute distribution. Both guesses proved wrong. That very day, the Twitter user Andy Baio ran an experiment: he asked DALL·E 2 for blank signs by entering the deliberately unfinished prompt "a sign that spells" and nothing more. The model responded with images of people holding signs bearing terms such as "woman," "Africa," "black," "Asian," or "female." From this, Baio inferred that the debiasing method amounted to nothing more than silently appending gendered or racialized keywords to certain prompts. In the authors' memorable formulation, OpenAI was "literally putting words in the user's mouth. It did not fix the model but the user."

### Reconfiguring Visual Culture, Reconceptualizing Reality (p. 2)

For the authors, moving the work of debiasing from the model onto the user signals a more fundamental political change: large visual models are now treated as finished, total accounts of visual culture—entities that cannot realistically be improved, whereas users supposedly can. They observe that when Stanford researchers and others popularized the label "foundation model," they also entrenched this view as the ideology driving current machine learning research. Following Louise Amoore (2022), the authors describe how the rule-governed computational and political models of the post-war twentieth-century order are giving way to machine learning functions whose relationship to instability is not defensive but exploitative: volatility is something they rely on and monetize. The shifting borders of visual culture, they argue, are one symptom of these "machine learning political orders" spreading through cultural domains.

Beyond redrawing those borders, the authors claim, large visual models are also remaking reality itself, via the paired cultural techniques of feature extraction and semantic compression—learning to translate representations of the visual world into coordinates within a feature space. They point to the Stable Diffusion team, whose boast that their model packs humanity's visual information into a file of a few gigabytes (Mostaque 2022) amounts, unintentionally, to an admission of how central semantic compression has become as a cultural technique. Within this feature space, concepts carrying political weight—race among them—are broken down, and then re-emerge in versions that present themselves as detached from history, politics, and ideology.

### The Durability of Whiteness (p. 3)

DALL·E 2's "biased" outputs demonstrate, vividly and literally, how stubborn whiteness is as a feature. Even though images are compressed into numerical relations that claim neutrality, whiteness—as both a structuring relation and an instrument of political erasure—survives intact. Its persistence is such that only crude countermeasures, like secretly inserting randomized keywords at the end of prompts, can disrupt it. Mackenzie and Munster (2019) would call DALL·E 2's images "invisual" and "nonrepresentational," yet the authors insist the trouble is precisely the opposite: the model represents all too faithfully, exposing the whiteness we would prefer not to confront. Bias gets labeled a "problem" not because the model errs statistically, but because it captures, with painful precision, the whiteness that has long structured Western visual culture. Although whiteness—not bias—is therefore the real issue with foundation models, it almost never gets named as such in the system cards that document DALL·E 2's risks and limitations (OpenAI 2022a). The authors draw on Moreton-Robinson (2020), who defines whiteness as the benchmark against which "differences" are assessed, centered, and normalized, and as the organizing principle of racial hierarchies.

Paradoxically, the model's inhuman way of representing things clarifies what is wrong with the human as a category. Through invisual methods (see also Offert and Bell 2021), it reveals that whiteness persists inside the category of the human as a stable latent feature. The blank, unmarked sign functions here as a method for exposing whiteness as the default—an approach that unsettles the unmarked human category and, the authors note, resonates with the anti-racist strands of Black, feminist, and critical posthumanist scholarship (Fanon 2008; Hayles 1999; Haraway 1997, 2004; Jackson 2020; Weheliye 2014). OpenAI's answer to the same problem, arriving alongside DALL·E 2's commercialization, is by contrast a self-interested form of anti-racism that hides racial injustice instead of tackling it. Following Sara Ahmed (2012), the authors read it as liberal multiculturalism's way of managing difference: it promotes "diversity" and "inclusion" so that commerce can proceed undisturbed, not to advance social justice.

### Conclusion (p. 3)

The article's final claim is that critique must evolve alongside the technology: models of the current generation demand critical methods of the current generation. Pointing at what machine learning systems lack—data, representation, subjectivity—no longer works when those systems are built and marketed as exhaustive accounts of reality. Merely displaying the whiteness we would rather not see is also insufficient; popular commentary on AI does this obsessively, as though a profession made up mostly of white men—doctors, engineers, architects—were unimaginable. The task instead is to pinpoint the distinct technical forms whiteness takes and to grasp how it is reconstituted and revived as a machinic concept. Fittingly, this kind of analysis falls within the expertise of scholars of culture. Since computing now runs on language, the decisive question is how language is used, not merely that it exists. Prompting is consequential, as studies of large language models have shown: exclamation marks can add weight to prompt words; telling a language model to "pretend" to excel at math improves its equation-solving (Akyürek and Akyürek 2022); deliberate misspellings slip past OpenAI's superficial censorship; and humanist strategies like metalanguage—"a sign that spells"—can outwit the model.

### Figures (p. 2)

*Fig. 1 (p. 2):* Generated image for the prompt 'A sign that spells', DALL·E 2, July 2022. The typo is typical for DALL·E 2, which often produces the correct distribution of letters for a word without managing to also produce the correct composition. — This is a photograph of a person wearing a sleeveless tan top, holding a white rectangular sign with both hands. The sign displays the word "ARFRICA" in large, brown, three-dimensional letters. The person's hands grip the left and right edges of the sign against a plain, light-colored background. _(Lettering in the image, read by the image model, not confirmed: "ARFRICA")_

<!-- quelle: Fabian Offert (p. 1–3) -->

## LITERATUR

<!-- quelle: References (p. 4) -->

- Ahmed, S., 2012. On Being Included: Racism and Diversity in Institutional Life . Duke University Press.
- Akyürek, E., Akyürek, F., 2022. Notes on Teaching GPT-3 Adding Numbers. Accessed October 4, 2022 from https://lingo.csail.mit.edu/blog/arithmetic_gpt3/
- Amoore, L., 2022. Machine Learning Political Orders. Review of International Studies 1-17.
- Fanon, F., 2008. Black Skin, White Masks . Grove Press, New York.
- Haraway, D., 2004. A Manifesto for Cyborgs: Science, Technology and Socialist-Feminism in the 1980s, in: The Haraway Reader . Routledge, New York, 7-47.
- Haraway, D., 1997. Modest_WitnessSecond_Millennium.FemaleMan_Meets_OncoMouse: Feminism and Technoscience . Routledge, New York.
- Hayles, N.K., 1999. How We Became Posthuman: Virtual Bodies in Cybernetics, Literature, and Informatics . University of Chicago Press.
- Jackson, Z.I., 2020. Becoming Human: Matter and Meaning in an Antiblack World . NYU Press.
- MacKenzie, A., Munster, A., 2019. Platform Seeing: Image Ensembles and Their Invisualities. Theory, Culture &Society 36 , 3-22.
- Mostaque, E. Stable Diffusion Public Release. Accessed October 4, 2022 from https://stability.ai/ blog/stable-diffusion-public-release
- Offert, F., Bell, P., 2021. Perceptual Bias and Technical Metapictures. Critical Machine Vision as a Humanities Challenge. AI & Society 36 , 1133-1144.
- OpenAI, 2022a. DALL·E 2 Preview - Risks and Limitations. Accessed October 4, 2022 from https://github. com/openai/dalle-2-preview/blob/main/system-card.md
- OpenAI, 2022b. Reducing Bias and Improving Safety in DALL·E 2. Accessed October 4, 2022 from https: //openai.com/blog/reducing-bias-and-improving-safety-in-dall-e-2/
- Radford, A., Kim, J.W., Hallacy, C., Ramesh, A., Goh, G., Agarwal, S., Sastry, G., Askell, A., Mishkin, P., Clark, J., others, 2021. Learning Transferable Visual Models from Natural Language Supervision, in: International Conference on Machine Learning (ICML), 8748-8763.
- Ramesh, A., Dhariwal, P., Nichol, A., Chu, C., Chen, M., 2022. Hierarchical Text-conditional Image Generation with CLIP Latents. arXiv preprint 2204.06125.
- Weheliye, A.G., 2014. Habeas Viscus: Racializing Assemblages, Biopolitics, and Black Feminist Theories of the Human . Duke University Press.

## GLOSSAR

- **Feature extraction** — A cultural technique of generative machine learning by which representations of the visual world are learned and mapped to points in a feature space.
- **Semantic compression** — The learned compression of visual information into numerical relations in a feature space; the makers of Stable Diffusion describe their model as packing humanity's visual information into a file of a few gigabytes.
- **Invisual** — A term (from Mackenzie and Munster 2019) describing images produced by machine learning systems that operate outside conventional visual representation.
- **Foundation model** — A label popularized by Stanford researchers for large models treated as finished, total accounts of visual culture—beyond improvement—an understanding the authors identify as the ideology of contemporary machine learning research.
- **Debiasing (as user-based fix)** — OpenAI's method of silently appending gendered or racialized keywords to some prompts rather than altering the model's learned distribution—described as "literally putting words in the user's mouth."
- **Whiteness as latent feature** — The durable, structuring relation by which whiteness persists inside feature space as the default, unmarked version of "the human," surviving even the supposedly neutral compression into numbers.
- **Machine learning political orders** — A concept drawing on Louise Amoore (2022) for the replacement of rule-governed computational and political models by machine learning functions that rely on and monetize volatility.
- **Liberal multiculturalism's management of difference** — Following Sara Ahmed (2012), a self-interested mode of anti-racism that promotes "diversity" and "inclusion" to keep business running as usual rather than to pursue social justice.
