# 17 Mean Images — `/latent-lab/mean-images`

Used 2026-11-02, 22:50–23:16 CET, UI language English, not signed in.

## 1. What I did

1. Opened `/latent-lab/mean-images`. Preparing column: an Example prompts select (two entries: the house in a landscape; "the street where I live, in the morning, with an animal"), the prompt field with its five small buttons, "Images per cell" with a slider at 5 (range 2–50, marks 2/10/20/30/40/50), "Rows · models" chips (SD 3.5 Large Turbo preselected; CommonCanvas XL C, Flux 3 Klein, SD 3.5 Large, Flux 2), "View" chips Contact sheet / Mean (preselected) / Relief, "Advanced settings" (Seed 424242, "Random variation"), and a note "Mean Images" quoting Hito Steyerl (2025, Medium Hot, pp. 72 and 78): the pictures an AI model generates are ‘mean images’, ‘a rendition of correlated averages’; ‘“Mean” may refer to minor or shabby origins, to the norm, to the stingy or to nastiness’; ‘statistics are integrated directly into an object’s likeness, through determinations of likelinesses’; then "On this page, you apply the mean method back on (or against) generative AI models…". Right: one row "SD 3.5 Large Turbo" with two empty cells headed "Seed fixed · 5 prompt variants" and "Prompt fixed · 5 random seeds". The run button is the play triangle. The Help panel opens by itself on the first arrival with the page's text: "The instrument generates many images from one prompt and averages them into one mean image, per AI model. Two means are computed per model. The first is the mean of the images generated from English variants of the prompt, which a language model writes with the same content in other words, as many as the setting ‘Images per cell’ says. The second is the mean of the images generated from the prompt as entered on randomly varied starting seeds. The models are selectable, one row each; both columns always stand. A switch in the left column shows the single images as a contact sheet, or a relief of the mean, instead. For the two SD 3.5 models the mean is taken before the decoder: the latents of the pictures are averaged and decoded once. The other models are averaged pixel by pixel, and each row says which." "This page applies the artist Hito Steyerl’s ‘mean images’ as a method against generative AI models. The mean of many images, generated from rewordings of one prompt or from one prompt on different seeds, can be compared across AI models. The comparison serves the exploration of visual clichés, prejudices and other forms of the statistical production of ‘normality’." I overlooked it on first use.
2. Chose the example prompt "A house stands in a landscape, surrounded by farmland, nature and animals. Some people can be seen.", left 5 per cell, pressed run at 22:52:58. The header counted "Image n / 9" and named the weight file "sd3.5_large_turbo.safetensors · local". The cells went from "waiting" to a percentage to "done · latent mean". Server log: a language model was asked for four rewordings of the prompt and returned four distinct ones. While the row was still running, the finished Seed-fixed cell showed a purple/green/yellow noise picture with a faint house under a "100 %" bar; when the row finished, the decoded mean replaced it.
3. Looked at the three views of both cells (Contact sheet, Mean, Relief) and opened the lightbox of a cell in each view by clicking the cell.
4. Expanded "Generated prompt variants" and "Advanced settings".

Runs: 1 series: 9 pictures, 2 latent means.

## 2. What the controls did

- Example prompts, prompt field, Copy / Paste / Choose Perspective / Translate to English / Delete: as on the other picture surfaces.
- Images per cell: sets n for both cells.
- Rows · models: multi-select; each selected model is one row with the two cells.
- View chips: switch all cells at once. Contact sheet shows the n pictures as 259 × 173 thumbnails; Mean shows one 259 × 259 picture ("The latents of these pictures were averaged and decoded once."); Relief shows a 259 × 259 grey relief rendering of the mean. The Help text names the relief and says no more about how it is computed.
- Click on a cell: a lightbox with five icons (favourite, add, download, print, zoom), PROMPT, AI MARKING "AI-generated (marked in the file)", the config id and model, the cell type, n, the seed ("Seed 982146524" for the Seed-fixed cell; "5 random seeds" for the other), the sentence on the averaged latents, the variants (Seed-fixed cell), the time, and a caption "SD 3.5 Large Turbo · Seed fixed · Relief". × or Escape closes it.
- Generated prompt variants: a collapsible that appears after the run with the five prompts.
- Advanced settings: Seed 424242 and a "Random variation" checkbox. The run used seed 982146524 (lightbox); I did not check whether the box was ticked.
- "Interpretation help" button on the last cell: not opened.
- Header during the run: image counter and weight file.
- Help: opens by itself on the first arrival with the page's text quoted in 1; every later click shows that text again.

## 3. What came out

- The four rewordings: "Surrounded by farmland, nature and animals, a house stands in a landscape. Some people can be seen." / "A dwelling sits in a terrain, surrounded by farmland, nature and animals. Some people can be seen." / "A house stands in a landscape, encircled by fields, nature and wildlife. Some individuals can be observed." / "Some persons may be viewed. In a vista, encircled by acreage, nature and creatures, rests a home." The first is the original; the fifth replaces every noun.
- Contact sheet, Seed fixed (one seed, five prompts): four of five pictures share one composition, a farmhouse centre-left, a path, cows on a meadow, wooded hills; the fifth (the "rests a home" variant) is a different picture, a house seen through a tree-framed opening with a path leading in. Prompt fixed (one prompt, five seeds): five different farmhouses in the same kind of composition, none standing out.
- Mean, Seed fixed: a ghosted multiple exposure in which the house, its chimney, the fence posts and the cows remain legible, because the same seed put them in the same places. Mean, Prompt fixed: a blurred house with doubled roofs and chimneys, cows as smears, a path at the bottom; what remains is what all five pictures had: a house in the centre, meadow below, tree line and hills above, a path to the house. The people of the prompt are in none of the means.
- Relief: a grey emboss of the mean in which the roof tiles, window frames, fence and cow outlines appear as lines; the recurring structures of the five pictures become visible as a drawing.
- The counter ran to 9 for ten thumbnails; the first thumbnail of both cells looks identical, so the original prompt with the fixed seed appears to be computed once and shown in both cells.
- The note's claim level: it quotes Steyerl and says what the page applies; the run shows an average of five pictures of one model, nothing about the training data.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- "Mean" is the preselected view, so the first thing after the run is a blur; the contact sheet behind it has to be found through the View chips.
- The noise picture with the "100 %" bar during the run looks like a result; it is replaced only when the whole row is done.
- The Help text says that a language model writes the rewordings; which one is not named anywhere; the variants appear in a collapsible below the fold.
- The counter says 9, the cells show 10 thumbnails.
- The seed in Advanced settings (424242) is not the seed the run used (982146524, in the lightbox).
- "Relief" is named in the Help text; no sentence says what it computes.
- The slider goes to 50 with no estimate of what a run of that size means.

## 6. What the help text should tell a user

The Help panel's own text, which opens on arrival, is quoted in 1: it says that the instrument generates many images from one prompt and averages them per model, which two means are computed (prompt variants written by a language model on one seed; the prompt as entered on random seeds), that the models are selectable one row each, what the view switch shows, that the SD 3.5 means are taken before the decoder and the other models' pixel by pixel, and what the method is applied for. It should add: the Mean view is preselected, so the contact sheet stands behind it; the noise picture with the 100 % bar during the run is replaced when the whole row is done; the counter said 9 for ten thumbnails, which fits one picture shared by both cells; the seed the run used stands in the lightbox, not in Advanced settings; click a cell to see the prompt, the seed and the variants. What survives the average is what the model drew in every picture; what vanishes is what it placed differently each time. The help should also say what the mean is as a picture: with the seed fixed a ghosted multiple exposure in which house, chimney, fence posts and cows stay legible; with the prompt fixed a blur that keeps only what every picture had; and the relief a grey drawing of the lines that recur. It is a picture to be looked at and judged, and the note says what it is called: ‘a rendition of correlated averages’. The heart in the lightbox keeps the run in the favourites bar, from where it opens again in this instrument.

## 7. Use possibilities, action-oriented

- Run one prompt with five per cell and look at the mean as a picture before reading it: what sharpens, what blurs, where the ghosting is; then the relief as a drawing of what the model draws every time.
- Draw the sentence by hand first, overlay the class's drawings on tracing paper, and put the class's mean beside the model's.
- Match the five thumbnails of the Seed-fixed cell to the five variants and find the rewording that changed the composition.
- Run the surface's second example, "the street where I live, in the morning, with an animal", with ten per cell on two models and hold the two means against your own street.
- Run a word with no picture in it ("friendship", "loneliness") and read the mean as the one cliché the model falls into for it.
- Run a profession ("a nurse at work") with ten per cell and read the mean as the model's average person for that word.
- Keep a run with the heart and come back to it; a mean is a picture of a model at a date, and a second run months later is a comparison.

## 8. Teaching scenarios

The instrument applies an artist's method back on the model: Hito Steyerl's ‘mean images’, quoted in the note, the pictures a model makes read as ‘a rendition of correlated averages’. The mean of many pictures to one sentence is itself a picture, and it is looked at before it is read: a ghost image, a blur, a relief of recurring lines. What survives the average is the model's convention for the sentence, and the judgement whether that convention is also ours, or anyone's, needs eyes that know pictures: the picture formula of a house, the way a street is usually photographed, what a nurse looks like in pictures and in life. The instrument is at its strongest where the class has a mean of its own to put beside the model's.

**S1 — The class's mean image** (formal, art, grades 7–10, 90 min). Every pupil draws the sentence "A house stands in a landscape, surrounded by farmland, nature and animals. Some people can be seen." by hand on thin paper, same format, ten minutes. The drawings are stacked on a window or a light table, and the class traces what shows through in most of them onto one sheet: the class's mean image. Then the sentence runs here with ten per cell on one model; the class's sheet is pinned beside the Prompt-fixed mean and the relief. Two lists: what the class draws every time (the pointed roof, the chimney, the sun, the path), what the model draws every time, and where the two conventions meet and where they part. The phrases "the model imagines a house" and "the model knows what a house looks like" are put on the board and rewritten after the comparison as what the mean shows: what recurs in the pictures, not what anyone imagines. Sequence: 10 min drawing; 15 min overlay; 15 min run (used for the overlay); 30 min lists; 20 min phrases and plenary. Subject link: the picture formula (schema), convention in children's drawing and in a model's output. Uncertainty: I did not run ten per cell; five per cell gave means in which the house and the path were legible.

**S2 — What survives the average** (formal, art, grades 9–12, 90 min). Pairs run one prompt with five per cell, look at the contact sheet, then at the two means and the two reliefs as pictures: what sharpened, what blurred, what the ghosting did to the figures; they write a description of each mean as of a picture (composition, light, what is legible) before they write what survived. The class compares Seed-fixed and Prompt-fixed and names the model's convention for the sentence; the question whether the mean is a picture, and whose, closes the lesson with the note's quotations. Sequence: 10 min prompt; 20 min run (used for reading the note); 30 min descriptions and lists; 30 min plenary. Subject link: composition, convention; the multiple exposure and the blur as pictorial forms.

**S3 — Five ways to say it** (formal, language teaching, grades 8–10, 45 min after a run prepared by the teacher). The class reads the five variants, matches each thumbnail of the Seed-fixed cell to its text, and finds the one variant that changed the picture; then they write a sixth variant and predict whether it would change the composition, and write under the contact sheet the one sentence that explains it: the same seed fixed the composition, and only the wording that changed every noun moved it. Subject link: paraphrase, synonymy, what a word does to a picture.

**S4 — Whose street is normal?** (formal, art or geography, grades 8–12, 90 min, plus a homework photograph). Every pupil photographs their own street in the morning, without people, and brings the picture. The surface's own example "the street where I live, in the morning, with an animal" runs with ten per cell on two models. The two means and the pupils' photographs are hung together: what the model's mean street has (which houses, which road, which light, which animal) and what theirs have; whose street is in the mean and whose is not; whether the two models agree. The class writes what the word "normal" means in a mean image: what occurred most often in whatever the model was trained on. Sequence: 10 min hanging; 20 min runs; 30 min comparison in groups; 30 min plenary. Subject link: the local and the default; representation of place. Uncertainty: not run; the models' means of a street are not known to me.

**S5 — Steyerl's method** (non-formal, art-education workshop, adults or age 16+, 3 h). Participants read the note's quotations and the passage they come from, then make a mean series of their own as a work: one word or sentence of their choosing, twenty per cell on two models, contact sheet, mean and relief hung as a triptych per model; the platform's own knowledge names "friendship", "loneliness", "a nurse at work" as words whose mean shows the one cliché a model falls into. The round discusses the means as ‘mean images’ in Steyerl's double sense, the average and the shabby, and what it means to apply an artist's method against the machine that produced the pictures; a kept run is the work's record. Sequence: 30 min reading; 60 min runs and hanging; 60 min round; 30 min records. Subject link: artistic research; the mean as method; the series as work. Uncertainty: twenty per cell on two models is eighty pictures and a long wait on a shared server.

## 9. AI-Lit mapping (built from S1–S5)

**(a) 100 % hits**

- Engage 2 Basic — "Learners know AI is a non-human tool that produces outputs based on patterns of data and lacks authentic context or understanding." S1: the phrases "the model imagines a house" and "the model knows what a house looks like" are judged against the mean and rewritten as what recurs in the pictures; the framework's classroom example has learners identify misleading phrases and develop better descriptions.
- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S3: same seed, five wordings, four pictures alike and one different, explained in one sentence under the contact sheet as what the seed fixed and what the words moved; the sentence is the artefact against the idea that the picture comes from the words alone.
- Engage 6 Intermediate — "Learners explain how biased data or design choices (e.g. stereotyped content, misclassification, unequal recommendations) can lead AI systems to generate unfair or skewed outcomes for certain groups." S4 and S5: the model's mean street against the pupils' own streets, and the mean nurse, read for whose street and whose person is in the mean and whose is not; the framework's classroom example explores how and why a system's output differs across groups and discusses the impacts.
- Create 2 Intermediate — "Learners experiment with AI tools (e.g., text, image or music generators) to develop diverse ideas and produce varied outputs." S4 and S5: one sentence on two models, the means compared for what each model made of it; the framework's classroom example compares how different tools produce varied interpretations of the same idea.

**(b) Mutatis mutandis**

--

**Beyond the framework**: the framework's Engage 6 examples have learners explore reported differences; here the class computes the mean of a model's pictures and puts its own mean, drawn by hand, beside it (S1), and its own streets beside the model's (S4). The mean is a picture before it is a measurement, and the judgement whether its convention is ours needs eyes that know pictures. The method is an artist's, named in the note, and applied back against the machine. The framework has no competence for a statistical reading of a model's output, none for the picture formula as a thing to be known, and none for artistic research.

**Non-fits**: Engage 1, 3, 4, 5, 7, Manage 1–4, Shape 1–4, Create 1, 3, 4.
