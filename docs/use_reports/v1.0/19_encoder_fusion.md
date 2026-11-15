# 19 Encoder Fusion — `/latent-lab/encoder-fusion`

Used 2026-11-02, 23:17–23:37 CET, UI language English, not signed in.

## 1. What I did

1. Opened `/latent-lab/encoder-fusion` (sidebar tooltip "Surrealistic blending"). Preparing column: Example prompts select, a prompt field with the placeholder "Choose an example prompt, write your own prompt, or drag a picture onto this area (it is converted into a verbal image description).", then "CONDITIONING TABLE" with six preset chips (Standard, CLIP only, T5 only, Surrealization 5, Surrealization 15, Surrealization 35), a diagram of the conditioning tensor (columns 0–2047 and 2048–4095, "pool → modulation", a CLIP block of rows 0–76 labelled "a·CLIP + b·T5" and "0 + b·T5", a T5 block of rows 0–511 labelled "c·T5", and a dashed box "T5 rows 0–76" with an arrow labelled b pointing into the CLIP block), and three sliders: a "CLIP block" (1.00, with chips "pool CLIP" / "pool 0"), b "T5 rows 0–76 into the CLIP block" (0.00), c "T5 block" (1.00, with chips "rows 0–511" / "rows 77–511"). Under them "Advanced settings". Right: an empty picture area. The run button is the play triangle ("Execute"); an "Outputs" drawer button sits in the header. The surface has no note box; the chip tooltips carry the only explanations ("a 1.00 · b 0.00 · c 1.00"; "CLIP-L's and CLIP-G's pooled vector, 768 and 1280 numbers joined"; "Zeros of the same shape in the pooled vector's place"; "T5 block with all 512 rows under the CLIP block"; "T5 block with rows 77–511 alone, rows 0–76 only as the b-fold addend inside the CLIP block"; the Surrealization chips "a −4.00 · b 5.00 · c 1.00 · T5 77–511", "a −14.00 · b 15.00 …", "a −34.00 · b 35.00 …").
2. Chose the example prompt "A house stands in a landscape, surrounded by farmland, nature and animals. Some people can be seen." A token table "Row | CLIP | T5" appeared under the sliders: CLIP cuts the sentence into 22 tokens between <|startoftext|> and <|endoftext|> (row 22), padding 23–76; T5 into 25 tokens with "▁" tokens at rows 4 and 8 (the spaces before "a" and "surrounded"), "farmland" as "farm", "l", "and" (rows 11–13), </s> at row 25, padding 26–76 and 77–511.
3. Standard preset (a 1.00 · b 0.00 · c 1.00), Execute. The picture arrived.
4. Moved the b slider strongly: the raw slider went to 801 of 1000 and the display read 22.00 (the scale is non-linear: 300 shows as 1.00, the ends as ±75). The preset chips all deselected. Execute at 23:28:44; the second picture arrived between 23:32:44 and 23:36:56 (my polling missed the moment).
5. Opened the Outputs drawer: RUNS 2, entries "a 1.00 · b 0.00 · c 1.00" and "a 1.00 · b 22.00 · c 1.00", each with ×. Opened Advanced settings: Negative Prompt (empty), CFG Scale 5.5 (1–15, step 0.1), Seed 123456789, "Random variation" unticked.

Runs: 2 pictures, 1024 × 1024, same seed.

## 2. What the controls did

- Preset chips: set a, b, c and the pool/rows chips at once; the tooltip states the values. Moving any slider deselects all presets.
- a: factor on the CLIP block; "pool CLIP" / "pool 0" chooses whether the pooled CLIP vector or zeros go to the modulation.
- b: factor with which T5's rows 0–76 are added into the CLIP block (the dashed box in the diagram).
- c: factor on the T5 block; "rows 0–511" / "rows 77–511" chooses whether all T5 rows or only rows 77–511 stand under the CLIP block.
- Token table: shows how the two encoders cut the prompt; it changes with the prompt and needs no run.
- Execute: one picture with the current table and seed. Outputs drawer: list of runs by their a/b/c.
- Prompt field buttons, Hide column, Help: as elsewhere. Drag-a-picture onto the field (not used): converted into a description.

## 3. What came out

- Standard: a photographic farm scene; a stone house with a tiled roof on a meadow, forest behind, cows, sheep and goats, four people walking in the foreground, telephoto look.
- b = 22, everything else as Standard, same seed: a naive painting. A white house seen frontally with a thick mossy roof and an orange-tiled gable; objects stuck on the facade like reliefs (a fish, a bird, jugs, shells, a nest); people in old-fashioned dress (a woman in white, one in yellow); goats, cows and sheep in a fenced meadow; yellow flower fields; painted clouds. The prompt's content is still there (house, farmland, animals, people), but the style, the composition and the objects on the wall are not in the prompt.
- The same seed gave two different compositions, so the seed does not pin the layout when the conditioning changes this much.
- The token table shows two tokenisations of one sentence: 22 against 25 tokens, "farmland" whole in CLIP and in three pieces in T5.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- The sliders' scale: the display jumps from 1.00 to 22.00 over half the slider's travel and the marks read −75 / 0 / 1 / 75; nothing says the scale is non-linear.
- "a", "b", "c", "pool", "rows 0–76", "modulation": the diagram names them, nothing explains them; the tooltips are the only prose, and they are hidden until hovered.
- Moving a slider silently deselects the preset; the chips go dark without a message.
- No note box: the surface does not say what "surrealization" is or why T5 rows added into the CLIP block produce it.
- No progress display; the picture simply appears.
- The Outputs drawer names the runs by their numbers only.
- The page's strings carry a note on what the instrument does (the table of 589 rows, Esser et al. 2024, the sentence that a row holding both encodings lies outside the trained states), and the surface does not show it; the chip tooltips are all there is.

## 6. What the help text should tell a user

The page has no Help text of its own and no note on the surface. It should first say what the pictures are: pictures from a conditioning that no prompt produces. SD 3.5 reads a prompt through three encoders into a table of 589 rows, a CLIP block of 77 rows above a T5 block of 512; the model was trained on that table and on tables with one encoder set to zero, never on a row that holds both encodings at once. The b slider writes T5's first 77 rows into the CLIP block, and the page's own note, which the surface does not show, says of such a row that it "lies outside those trained states. What the model computes from such a table is the question of this instrument." The help should say what that means for the one who uses it: the naive painting with the reliefs on the facade that came out of b = 22 is a picture nobody could have written a prompt for, on this model or any other; writing a prompt reaches only what the training made sayable, and this slider reaches past it. The platform's concept says this is the point of the Surrealizer, insights into the model's latent spaces that conventional prompting does not reach, and the Latent Lab's purpose text says what to do with them: "to carry the estrangements and intermediate products on into artistic work". The help should say that the work is in the choosing: along b the picture stays a picture for a while and then falls apart, and the place where it is still a picture and no longer the prompt's picture is where the series is worth keeping. Then the mechanics: Standard first (a 1, b 0, c 1), then a preset or own values with the same seed; the token table shows how each encoder cut the prompt; a picture is kept with the heart and goes on to Flow.

## 7. Use possibilities, action-oriented

- Make a picture no prompt can make: one prompt, Standard, then Surrealization 15 with the same seed; then try to write a prompt that gives the second picture on Standard, run it, and put the three side by side.
- Find the edge: move b upward in steps from 0 and keep every picture; mark the last one that is still a picture and the first that is no longer the prompt's.
- Run Standard, CLIP only and T5 only with one prompt and the same seed; list which named things each picture keeps.
- Draw the objects the model put where the prompt had none; then run the drawing's description through Standard and see whether the model gives them back.
- Take the kept picture onto the Flow board and carry it on: a video, a sound, a perspective.
- Write a prompt with a compound word ("farmland", "lighthouse") and read how CLIP and T5 cut it in the table.
- Drag a photograph onto the prompt field and run its description at Surrealization 5 and 35.

## 8. Teaching scenarios

The instrument makes pictures that no prompt can make. Everything a prompt can reach lies inside what the model was trained to read; the b slider writes one encoder's reading into the other's rows, a state the model never saw in training, and what it computes from that is a picture nobody wrote. The work with it is artistic before it is technical: to find, along the slider, the place where the picture is still a picture and no longer the prompt's, to keep the series, to choose, and to carry the chosen picture on. The questions that come with it are the platform's own: whether this is still my picture, and what the model gives when it is asked something unsayable.

**S1 — The picture no prompt can make** (formal, art, grades 9–13, 2 × 45 min). The class writes one prompt and runs it on Standard, then on Surrealization 5, 15 and 35, same seed, all four kept. Then the attempt: pairs describe the Surrealization-15 picture as precisely as they can (a naive painting, a white house seen frontally, objects stuck on the facade like reliefs, people in old-fashioned dress) and run that description on Standard. The two pictures side by side: the written one is a picture in a style, the fused one is something else, and the pairs say what. Reading of the note's sentence that such a row lies outside the trained states. Closing: one sentence per pair on what a prompt can reach and what it cannot. Sequence: 10 min prompt and four runs; 20 min description and run; 30 min side by side; 20 min note and sentences; 10 min plenary. Subject link: the sayable and the picturable; style against state. Uncertainty: not run as a sequence; Standard and b = 22 were run, the presets were not.

**S2 — Finding the edge** (non-formal, art workshop, age 16+, 3 h). Participants write a prompt of their own and move b up in steps (2, 5, 10, 15, 22, 35), same seed, every picture kept with the heart. Along the series they mark two places: the last picture that is still a picture, and the first that is no longer the prompt's picture. Between the two lies the stretch where the work is; each participant chooses one picture from it and says why. The chosen picture goes to the Flow board and is carried on: a video from it, a sound, a perspective. At the end the series and the continued work hang together, and the round asks what the model gave that nobody asked for, and whether it belongs to anyone. Sequence: 20 min prompts; 60 min series; 30 min marking and choosing; 50 min continuation on Flow; 20 min round. Subject link: the series as a form of work; the choice as the artistic act; the Latent Lab's purpose of carrying the estrangements on into artistic work. Uncertainty: a strong b can give noise instead of a painting, and the stretch between the two marks may be short; I did not try the Flow path from this surface.

**S3 — Is this still my picture?** (formal, art or ethics, grades 10–13, 45 min). Pairs put three things side by side: their Standard picture, their Surrealization-15 picture, and a third made from the second on Flow. For each they list who made which choice: the prompt (theirs), the factors (chosen on the slider), the content of the fused picture (nobody wrote it), the perspective on Flow (theirs again); then they say which of the three they would sign, which they would call theirs, and what the model's share is in each. Subject link: authorship; the platform's own question "is this still my picture". Uncertainty: not run.

**S4 — Two readers of one sentence** (formal, computer science or language teaching, grades 10–13, 90 min). Pairs enter a sentence with a compound noun, read the token table (CLIP against T5), then run Standard, CLIP only and T5 only with the same seed and list which details each picture carries. Three sentences about the model are held against the table and rewritten: "the model reads the sentence", "the model understands the compound", "the model sees the picture before it makes it". Sequence: 15 min table; 30 min three runs; 25 min lists; 20 min the three sentences. Subject link: tokenisation, representation; language about machines.

**S5 — Drawing what nobody wrote** (non-formal, art workshop, age 14+, 2 h). Participants run their prompt at Surrealization 15 and draw the objects the model placed where the prompt had none (a fish, a bird, jugs, shells, a nest on a facade); the drawings become the start of a work of their own. Then they compare the word "surreal" on this surface, a state the model never saw, with the art-historical one, a method of the 1920s for reaching what the conscious mind does not write. Sequence: 20 min prompts and runs; 60 min drawing; 40 min round and the two uses of the word. Subject link: surrealism as a term; the unexpected as material. Uncertainty: the outcome of a strong b is not predictable; a prompt may yield noise rather than a painting.

## 9. AI-Lit mapping (built from S1–S5)

**(a) 100 % hits**

- Create 1 Basic — "Learners explore how different AI tools can expand their thinking or spark new ideas." S5: the objects the model placed where the prompt had none, drawn and taken as the start of own work; S2: the picture chosen from the series carried on into a video or a sound; the framework's classroom example has learners write new stories inspired by unexpected results.
- Create 2 Intermediate — "Learners experiment with AI tools (e.g., text, image or music generators) to develop diverse ideas and produce varied outputs." S1 and S2: one prompt under Standard and three or six settings of b, the series kept and compared for what each setting made of the same prompt; the framework's classroom example compares how different prompts and tools produce varied interpretations of the same idea.
- Create 4 Advanced — "Learners assess the ethical implications of AI-generated outputs for creative work, distinguish inspiration from replication in their outputs, and justify how their use of AI maintains authenticity and respects other creators." S3: the prompt's picture, the fused picture and the continued one side by side, and for each who made which choice, which the pair would sign and what the model's share is; the framework's classroom example puts human-made, AI-generated and human-with-AI work side by side and asks what choices a human did or did not make and who should be credited.
- Engage 2 Advanced — "Learners explain how different AI systems work using language that does not attribute human traits or abilities, knowing that their phrasing shapes understanding." S4: the two encoders explained from the token table and the tensor diagram as rows and factors, the three sentences about the model rewritten without reading, understanding or seeing.
- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S1 and S4: the prompt reaches the model as a stacked table of numbers, not as a sentence, and a picture can come from a table no sentence produces.
- Engage 2 Basic — "Learners know AI is a non-human tool that produces outputs based on patterns of data and lacks authentic context or understanding." S4: three phrases about the model held against the token table and rewritten, as the framework's classroom example has learners identify misleading phrases and develop better descriptions.

**(b) Mutatis mutandis**

--

**Beyond the framework**: the framework's Create competences have learners prompt, vary and combine; every one of its examples stays inside what a prompt can reach. This instrument reaches past it: a conditioning the model never saw in training, and pictures that no prompt on any model produces. The platform's concept names these pictures as insights into the model's latent spaces that conventional prompting does not reach, and its Latent Lab purpose as carrying the estrangements on into artistic work. The framework has no competence for the unsayable, and none for the choice along a series as an artistic act; this instrument is built on both.

**Non-fits**: Engage 1, 3, 4, 5, 6, 7, Manage 1–4, Shape 1–4, Create 3.
