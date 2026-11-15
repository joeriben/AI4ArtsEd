# 33 LoRA Explorer — `/latent-lab/lora-explorer`

Used 2026-11-03, 10:17–11:25 CET, UI language English, not signed in.

## 1. What I did

1. Opened `/latent-lab/lora-explorer`. Preparing column: "Adapter" with three chips (19th_century_photography_landscape [preselected], destroyednegative, solarization); "Trigger word" with an Example prompts select (19th_century_photography, landscape, historic photograph; destroyed negative; solarization) and a field prefilled with "19th_century_photography, landscape, historic photograph"; "Motifs, one per line" with an Example prompts select (a landscape; a busy street; a room with a window; a person; a person at work; first meal of the day; a bowl of fruit; a machine) and a field prefilled with "a landscape / a person / a bowl of fruit"; "Adapter strength" slider 50–100 % at 100 %; a note "LoRA Explorer": "This platform trains a LoRA adapter on captions that all begin with the same trigger word. Whether it also acts on something else is a question about the model that took it on: personalisation can drift, so that the ordinary meaning of a word that stood in the captions changes as well (Ruiz et al. 2023)." with three references (Hu et al. 2022, LoRA, ICLR 2022; Ruiz et al. 2023, DreamBooth, CVPR 2023; Kim et al. 2025, Preserve and Personalize). Right: a grid, columns "a landscape / a person / a bowl of fruit", rows "Model · no trigger / Model · trigger / Adapter · trigger / Adapter · no trigger", twelve empty cells. Run button "Run the comparison". The Help panel opens by itself on the first arrival with the page's text: "You choose an adapter that was trained here, the word its images were captioned under, and a few motifs — one motif per line, and each becomes a column. Every column is then generated four times over: the plain model on the motif alone, the plain model with the word in front of it, the adapter with the word, and the adapter without it. All sixteen pictures come from one model with one starting number, so what separates two of them is the prompt and the adapter alone." "The third row against the second is the reach: what the training added on top of what the words already carried. The fourth row against the first is the limit: whether the adapter also answers when it is not called, which is how it shows that it has overwritten what the model knew rather than added to it. A motif the adapter was never shown asks the same question from the other side — whether a trained manner carries over, or whether the adapter brings the subjects of its training set along with it." I overlooked it on first use.
2. Kept the defaults (the first adapter, its trigger words, the three motifs, 100 %). Ran at 10:17:48. The header counted "Image 0 / 12 … 12 / 12" and named "sd3.5_large.safetensors · local".
3. Read the four states of the "a person" column and the other two columns (3 below).

Runs: 1 (12 pictures, 11 arrived).

## 2. What the controls did

- Adapter chips: one trained adapter at a time; the trigger field follows the Example prompts select, not the chip.
- Trigger word field: the words that were in front of every training caption; used in the "trigger" rows.
- Motifs field: one motif per line, one column each.
- Adapter strength: 50–100 % in steps of 10.
- Run the comparison: four pictures per motif with one seed: the base model with and without the trigger words, the model with the adapter with and without them. The header counts.
- "Interpretation help" button on the last picture: not opened.
- Help: opens by itself on the first arrival with the page's text quoted in 1; every later click shows that text again.

## 3. What came out

The "a person" column, read top to bottom:

- Model · no trigger: a colour photograph, soft and faded, of a woman with a dark bob in a sheer grey top and a black skirt against a beige wall, the face without features. The base model's "a person".
- Model · trigger ("19th_century_photography, landscape, historic photograph, a person"): a sepia photograph of a man in a tall hat and a dark suit standing on a field path by a stream, trees and hills behind, the paper tone and softness of an old print. The trigger words alone, which are plain English, make the base model draw a 19th-century photograph; no adapter was involved.
- Adapter · trigger: a dark sepia picture of a person waist-deep in water seen from behind, mist above, a few blossoms at the lower left. The adapter's look: darker, more vignetted and blurred than the base model's "19th-century" picture.
- Adapter · no trigger: nearly the same picture (the person in the water, the mist, the blossoms), slightly different in the head and the water. The adapter acts without its trigger word, and acts on "a person", a motif that is not in its name.

The other columns: "a landscape" with trigger, base model: a sepia valley with fields, trees and a white house, and a printed caption-like scrawl at the lower left; with the adapter, with and without trigger: two figures in a boat on a grey sea, sepia, the same scene twice. "a bowl of fruit": base model, no trigger, a bright colour photograph of a bowl of apples, oranges, grapes and a pear; with trigger, a warmer still life with grapes and apples on a cloth; with the adapter, with and without trigger, a dark bowl of dull apples on a dark table, nearly identical to each other.

Reading across all three columns: the row that changes the picture is the adapter, not the trigger. The two adapter rows are near-duplicates in every column; the trigger changes the base model strongly (sepia, old print) and the adapter rows barely. This is what the note calls drift: the adapter has taken over the model's "a person" and "a bowl of fruit" even when its word is absent.

The cell "Model · no trigger / a landscape" shows "Service not reachable." instead of a picture; the eleven others arrived. The line names the cause as the surface sees it; the server log shows the other eleven jobs admitted one by one.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- Four pictures per motif, as the Help text says; the total stands in the header only after pressing.
- The trigger field does not change when the adapter chip changes; a user who picks "solarization" keeps the 19th-century trigger words unless they also use the select.
- The four row names ("Model · no trigger …") are explained row by row in the Help text; the note on the page explains the trigger, not the rows.
- One cell failed with "Service not reachable." and the run was reported complete; nothing offers to recompute the cell.
- The near-identical adapter rows look like a mistake until the Help text's sentence on the fourth row, or the note's sentence about drift, is read.

## 6. What the help text should tell a user

The Help panel's own text, which opens on arrival, is quoted in 1: it says what is chosen, that every motif becomes a column generated four times over, which four states the rows are, that all pictures come from one model with one starting number, and how the third row against the second and the fourth against the first are read. It should add: the trigger field follows the Example prompts select, not the adapter chip; the count stands in the header during the run; the note's word for what the fourth row shows is drift; a cell that shows a sentence instead of a picture did not arrive, and running again fills it.

## 7. Use possibilities, action-oriented

- One motif that has nothing to do with the adapter's subject (a bowl of fruit for a landscape adapter): see whether the adapter still takes over.
- Adapter strength 50 % against 100 % for the same motifs.
- The three adapters in turn with the same three motifs; compare how much each one drifts.
- Write the trigger words as plain English into a base-model prompt elsewhere and compare with the "Model · trigger" row.

## 8. Teaching scenarios

**S1 — What did the adapter learn?** (formal, art or computer science, grades 10–13, 90 min, the run started before the lesson). The class reads one column's four pictures and writes what changed between rows 1→2 (the words), 2→3 (the adapter) and 3→4 (the missing word); then a second column; then they read the note and the term drift. Sequence: 10 min rows explained; 30 min two columns in pairs; 20 min comparison; 30 min the note and the question what "learning a style" did to "a person". Subject link: fine-tuning, style, generalisation.

**S2 — Words against weights** (formal, language teaching, grades 11–13, 45 min). Pupils compare the "Model · trigger" row (plain English words that already produce a 19th-century look) with the "Adapter" rows and discuss what a word can do that an adapter cannot, and the reverse. Subject link: description vs. training.

**S3 — Train, then explore** (non-formal, two-day workshop, age 16+). Day 1 the group trains an adapter on its own pictures (LoRA Training); day 2 they explore it here with motifs from outside their series and look for drift. Subject link: dataset, caption, trigger word. Uncertainty: training needs 50 GB of free VRAM and one to three hours (per the training surface), which the shared server did not have on the day.

**S4 — Who is "a person at work"?** (formal, ethics or art, grades 9–12, 45 min, the run started before the lesson). Motifs "a person", "a person at work" and "first meal of the day", all from the surface's own Example prompts, with one adapter; the class fills a table per row: who is shown (age, gender, clothing), doing what, where. Then they compare the base model's two rows with the adapter's two rows and sort the differences: which come from the adapter's series, which the base model brought along. In my run the base model's "a person" was a woman against a wall, the trigger words alone made it a man in a tall hat, and the adapter made it a figure waist-deep in water. Sequence: 10 min rows explained; 20 min table; 15 min sorting and discussion. Subject link: representation, dataset, who is pictured. Uncertainty: I did not run "a person at work" and "first meal of the day".

## 9. AI-Lit mapping (built from S1–S4)

**(a) 100 % hits**

- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S1: the four-row description of what the words do and what the adapter does.
- Shape 3 Advanced — "Learners evaluate how specific properties of a dataset (e.g. size, features, biases) affect the performance and impact of an AI model." S3: the group's own pictures and captions as the dataset, and the drift seen on motifs outside it.
- Engage 6 Intermediate — "Learners explain how biased data or design choices (e.g. stereotyped content, misclassification, unequal recommendations) can lead AI systems to generate unfair or skewed outcomes for certain groups." S4: two sources of skew in whom the pictures show, the base model's data and the adapter's series, separated by the four rows.
- Shape 1 Intermediate — "Learners describe the purpose, intended users and basic constraints of a specific AI tool." S1 and S3: an adapter made for one look, its trigger word, and the constraint that it acts without the word.
- Create 4 Basic — "Learners know that AI-generated content may reuse or copy work protected by intellectual property or copyright laws and recognise implications for the humans who created the original work." S3: an adapter trained on a series of pictures reproduces their look; whose pictures go in is the question the group has to answer before day 1.

**(b) Mutatis mutandis**


**Beyond the framework**: S4 separates two sources of skew in whom a picture shows, the base model's data and the adapter's series, by four rows of the same motif; the framework's Engage 6 examples have one system and one reported difference.

**Non-fits**: Engage 1, 3, 4, 5, 7, Manage 1–4, Shape 2, 4, Create 1, 2, 3.
