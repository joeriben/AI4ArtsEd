# 09 Language Understanding — `/latent-lab/language-understanding`

Used 2026-11-02, 21:26–21:52 CET, UI language English, not signed in. While the pictures of this run were computing I used Voice Comparison (10) in a second browser tab.

## 1. What I did

1. Opened `/latent-lab/language-understanding` (sidebar "Language Understanding"). Preparing column: an Example prompts select with "the street where I live, in the morning, with an animal" chosen and the same sentence in the prompt field (five small buttons: Copy, Paste, Choose Perspective, Translate to English, Delete); "Languages" in two groups, PLATFORM LANGUAGES with eleven chips (English en, Deutsch de, العربية ar, עברית he, Türkçe tr, 한국어 ko, Українська uk, Français fr, Español es, Български bg, 繁體中文 zh-hant) and FURTHER LANGUAGES with ten (Hornjoserbšćina hsb, Dolnoserbšćina dsb, Frysk fry, Yorùbá yo, Kiswahili sw, Cymraeg cy, Runasimi qu, हिन्दी hi, 日本語 ja, 中文 zh), a counter "n of 4 languages selected"; "Models" chips with parameter counts (SD 3.5 Large 8.1B, SD 3.5 Large Turbo (fast), Flux 2 32B, Flux 3 Klein 5.6B, Gemini 3 Pro (€) very large); and a note "Language Understanding": "SD 3.5 Large reads the prompt through three text encoders: CLIP-L and CLIP-G, trained on pairs of pictures and captions (Radford et al. 2021; Cherti et al. 2023), and T5-XXL, trained on text alone (Raffel et al. 2020). Stability AI's paper on the architecture (Esser et al. 2024) reports the design as "improving text comprehension, typography, and human preference ratings". In the paper's evaluation, typography is how accurately the picture shows written text." followed by a paragraph on Flux 2 ("reads the prompt through the language model of a vision-language model …"). The Help panel opens by itself on the first arrival with the page's text: "Every column holds the same description of a picture, each one in a different language. Two to four languages stand to choose from: the platform's ten and ten further ones, among them Upper Sorbian, Yorùbá and Runasimi. Every ticked image model makes a picture from it in every column, one row per model; within a row, all the pictures are made with the same seed (Gemini runs behind Google's interface, and that interface takes no starting number). Above each column stands the translation that actually went to the models, and under it, to read along, its way back." "Compare what becomes of the same prompt as soon as a model processes it in another language. The way back above each column is the check on that: most of the time the way back is the prompt as entered, so the translation holds, and the pictures still often differ widely. The text parts of SD 3.5 are trained on English text; a prompt in another language they process so little that the language itself settles the picture and the content steps behind it. The picture then shows the cliché: whatever stood most often beside that language in the training data. The other image models read the prompt through text parts of their own, named in the box beneath the image models." "This help can support you with the comparative analysis of the results. Just ask it about them." I overlooked it on first use.
2. Languages: English (already selected), Hornjoserbšćina (Upper Sorbian) and Runasimi (Quechua); counter "3 of 4 languages selected". Models: SD 3.5 Large and Flux 2.
3. Pressed the play triangle in the header. The header showed "Seed: 2181751251" and, during the run, an image counter. Three column heads filled first: the prompt in each language and, under an arrow, its back-translation into English. Then six pictures, row by row.
4. Read the columns against each other (section 3).

Runs: 1 series, 6 pictures, 5 translations.

## 2. What the controls did

- Example prompts select fills the prompt field; the field is free text.
- Language chips: toggle, at most four at a time (the counter says "of 4"); each selected language becomes a column.
- Model chips: toggle; each selected model becomes a row.
- Play: translates the prompt into every column language, back-translates each into English, shows both in the column head, then generates one picture per cell with one shared seed.
- Hide column, "Interpretation help" over the last picture: not used. Help: opens by itself on the first arrival with the page's text quoted in 1; every later click shows that text again.

## 3. What came out

- Column heads. English: the sentence itself. Hornjoserbšćina: "wulica, hdźež bydlu, rano, ze zwěrjom" → "the street where I live, in the morning, with an animal" (the back-translation returns the sentence). Runasimi: "ñan maypi tiyan, paqarinpi, huk uywawan" → "Where is the road tomorrow with one animal?" The Quechua round trip already loses "where I live" and "morning" and turns the phrase into a question; the surface shows this before any picture.
- SD 3.5 Large. English: a deer-like animal crossing a sunny suburban street, cars behind. Upper Sorbian: a pine forest with moss, no street, no animal. Runasimi: a grey stone relief of three standing figures with tall headdresses and geometric borders; nothing of the sentence.
- Flux 2. English: a cat crossing a hazy street at sunrise between walls, lamps and trees. Upper Sorbian: two spotted deer in a misty meadow at sunrise next to a wooden house; morning and animal, no street. Runasimi: a painted scene of a young woman in embroidered Andean dress with braids and bead necklaces, sitting among flowers with a chicken, a clay jug and mountains; the Quechua prompt is printed across the top of the picture as a title, with a second line of pseudo-words ("am dan batical Signitond Clorasheritlicama") underneath.
- Reading across: where the model can read the sentence (English) it draws the scene. Where it cannot, it draws what the language suggests to it: for Upper Sorbian, forest and deer; for Quechua, pre-Columbian stone or an Andean woman in costume. Flux 2 additionally treats the unreadable text as typography and prints it.
- The note on the left explains why: the encoders were trained on captions and on text, and the paper's "text comprehension" was evaluated on languages those captions cover.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- Only an image counter during the run; nothing says that two models have to be loaded.
- The back-translation in the column head, which the Help text names as the check, is set small under the translated prompt.
- The pictures for a language a model's text parts do not read look as finished as the others; the Help text says why (the language itself settles the picture), the picture carries no mark.

## 6. What the help text should tell a user

The Help panel's own text, which opens on arrival, is quoted in 1: it says that every column holds the same prompt in another language, two to four of them, that every ticked image model makes a picture in every column with one seed per row, that the translation that went to the models stands above each column with its way back under it, that the way back is the check on the translation, why SD 3.5 lets the language settle the picture, and that the other models read the prompt through text parts of their own, named in the box beneath the image models. It should add: compare the way back with the prompt as entered before looking at the pictures, since where it differs the models received a different sentence; some models print the prompt's text into the picture; during the run only the image counter shows.

## 7. Use possibilities, action-oriented

- Put one sentence through a home language of the group and one small language (Upper Sorbian, Lower Sorbian, Welsh, Quechua) and compare the back-translations first.
- Keep the languages and swap the model row to see which model reads which language.
- Collect the cells in which the picture shows costume, landscape or ornament instead of the sentence; that is the cliché the Help text names.

## 8. Teaching scenarios

**S1 — Round trip first** (formal, language teaching, grades 8–11, 45 min). The class writes one sentence; pupils pick their home languages from the list plus one small language; before the pictures appear they rate each back-translation (same / nearly / different); then they look at whether the pictures follow the rating. Sequence: 10 min sentence and languages; 5 min run start; 15 min back-translation ratings while the pictures compute; 15 min pictures against ratings. Subject link: translation, loss of meaning.

**S2 — Does the model read the sentence?** (formal, art or media, grades 10–13, 90 min). Groups choose two languages from the further list and two image models, run, and check the way back above each column first: does it return the sentence? Then they sort every picture into "shows the scene of the sentence" or "shows something else", and compare the two models on the same language: which model draws the scene for which language. They read the Help text's sentence on the text parts of SD 3.5 and the box beneath the image models, and write one sentence on why a model whose text parts were trained on English draws something else for a prompt in another language. Sequence: 10 min languages and models; 15 min run and way-back check; 30 min sorting; 20 min model comparison; 15 min the sentence and plenary. Subject link: training data, translation, what a model draws when it cannot read the prompt.

## 9. AI-Lit mapping (built from S1–S2)

**(a) 100 % hits**

- Engage 6 Intermediate — "Learners explain how biased data or design choices (e.g. stereotyped content, misclassification, unequal recommendations) can lead AI systems to generate unfair or skewed outcomes for certain groups." S2: the pictures that show something else than the sentence for a language a model's text parts do not read, sorted per model and language, and the one sentence the groups write on why; the framework's classroom example asks the same how-and-why of face recognition across demographics.
- Shape 3 Basic — "Learners identify examples of data that might be used to train AI systems." S2: the Help text and the box beneath the image models name what the text parts were trained on (English text; picture–caption pairs), and the learners write one sentence on it in their own words.
- Shape 2 Intermediate — "Learners assess an AI system performance of a task using defined criteria and feedback from human reviews or benchmark tests." S2: the sort "shows the scene of the sentence" / "shows something else" is the defined criterion, per model and language.
- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S2: the groups write one sentence on why a model whose text parts were trained on English draws something else for a prompt in another language, against the idea that the model reads the prompt.

**(b) Mutatis mutandis**

- Engage 3 Intermediate — "Learners verify AI-generated outputs for accuracy and relevance by consulting trusted sources and considering task-specific expectations." Modification: the source consulted is the sentence as the class entered it, which the way back above each column must return; no source outside the surface is opened. The framework's classroom example checks AI recommendations against other sources; here the check is a round trip against the own text.

**Beyond the framework**: the framework's Engage 6 example has learners explore a reported difference in how a system performs across groups; S2 produces the difference in the room, language by language, with the back-translation above each column as the control of what the model received.

**Non-fits**: Engage 1, 4, 5, 7, Manage 1–4, Shape 1, 4, Create 1–4.
