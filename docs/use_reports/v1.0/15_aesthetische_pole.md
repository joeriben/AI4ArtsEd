# 15 Aesthetic Poles — `/latent-lab/aesthetic-poles`

Used 2026-11-02, 22:38–22:50 CET, UI language English, not signed in.

## 1. What I did

1. Opened `/latent-lab/aesthetic-poles` (sidebar "Aesthetic Poles", Prompt Interception Lab). Preparing column: Example prompts select with one entry (the house-in-a-landscape sentence), the prompt field; "Properties": five chips with quotation marks in their labels, “best”, “better”, “neutral” (selected), “worse”, “worst”, then ten bars with a word at the right end: Object pairing (3 positions: coordinated / ordinary / uncoordinated), Richness (5: very rich … ordinary … empty), Background (4: beautiful … no background), Clarity (5: very clear … ordinary … completely blurry), Color Brightness (3: bright / ordinary / dark), Color Aesthetic (3: beautiful colors / ordinary colors / ugly colors), Lighting Distinction (4: very distinct … no lighting), Detail realism (5: realistic … neutral … greatly unrealistic), Detail refinement (7: very refined … ordinary … fragmented), Emotion (5: very positive … ordinary … very negative); "Image model" chips (SD 1.5, SDXL, CommonCanvas XL C, SD 3.5 Large (selected), Flux 2, Flux 3 Klein, Gemini 3 Pro (€)); a note "Aesthetic Poles": the framework VisionReward (Xu et al. 2024) with its ordered rater options ("for Clarity: very clear, clear, ordinary, blurry, completely blurry"), "Which end of a list counts as the bad one is built into the measurement", and "A model trained on such judgements can carry the scale as a norm (Guo et al. 2025)"; two references with arXiv numbers and DOI. Right: one box "Reference image". The Help panel opens by itself on the first arrival with the page's text: "One aesthetic checklist, set property by property, and what a model writes from it and the template. Write the template — or drag a picture onto the field, and its description then stands there as the template. Every property that can carry a handle is a scale of words with one handle on it; a property left at its neutral word stays out of the prompt. Five chips over the bars set the whole checklist at once, and from there each property is moved on its own. One setting is one prompt. Every run adds a row, and the first row stays: the checklist at its neutral word throughout, which every picture beside it is read against. Where the template was read from a picture, that picture stands first as the reference, and the picture beside it is the first step, with no setting on it. One image model runs, so what parts two pictures is the setting. Resting on a picture's name — holding it — shows what was set and what the model wrote from it." "The properties come from the human labelling guidelines of VisionReward, where each of them carries one ordered list of words with one of those words marked as the neutral one. Those guidelines give one position on such a list, which is why there is one handle here. The lists are of different lengths and reach different distances to either side, so each property is set on its own rather than by one axis over all of them, and a setting is free to stand at the good end of one property and at the bad end of the next. Every row is written by the same model from the same template, so what stands between two rows is the setting, and the pictures show what the checklist does to a template." I overlooked it on first use.
2. Chose the example prompt. Pressed two chips to see what they do: “best” put all ten bars at their left end (coordinated, very rich, beautiful, very clear, bright, beautiful colors, very distinct, realistic, very refined, very positive); “worst” put all ten at their right end (uncoordinated, empty, no background, completely blurry, dark, ugly colors, no lighting, greatly unrealistic, fragmented, very negative). Back to “neutral” (all "ordinary", Detail realism "neutral").
3. Moved two bars notably: Clarity to the left end ("very clear") and Emotion to the right end ("very negative"). Image model SD 3.5 Large. "Run the series" (play triangle) at 22:41.
4. Server log: the properties were turned into prompt text by a language model twice (Claude Opus 5.5 over OpenRouter, about 1850 characters each): "A plain color photograph, taken with an ordinary digital camera or a phone at eye level from the edg…" and "A large-format color photograph, shot on an 8x10 view camera at f/45, renders a single farmhouse wit…". The Help text says that resting on a picture's name shows what was set and what the model wrote from it; I did not use that and read the texts in the server log. Two pictures, "Reference image" and "Run 1", arrived, with "Interpretation help" at the top right.

Runs: 1 series, 2 pictures, 2 rewrites.

## 2. What the controls did

- Property chips: set all ten bars to one pole at once; “neutral” resets to "ordinary".
- Bars: each is a scale with named steps; the word at the right end names the current step; the number of steps differs per property (3 to 7).
- Image model chips: the model that draws both pictures.
- Run the series: writes a prompt from the bar settings, draws the reference (the "ordinary" setting) and the run; the written prompt is shown by resting on the picture's name (Help text), which I did not do.
- Interpretation help, Hide column: not used. Help: opens by itself on the first arrival with the page's text quoted in 1; every later click shows that text again.

## 3. What came out

- Reference image: a white two-storey house with a slate roof at the end of a gravel track under a flat grey sky, a woman in a grey coat with a green bucket and a small child in a red jacket on the track, two chickens, two cows in a stubble field, a satellite dish; a plain snapshot, as the rewrite's "ordinary digital camera or a phone" says.
- Run 1 ("very clear", "very negative"): a wide harvested field in hard sunlight filling three quarters of the frame, a run-down farmhouse with a patched roof far back, an old man and a child with a green basket, two brown cows, and, dumped in the field, a cardboard box, a blue tarpaulin and a white sack. Everything sharp to the horizon; the scene reads as bleak. The rewrite's "8x10 view camera at f/45" is the clarity; the rubbish and the ruin are the emotion.
- The pair shows what two words did: the clarity setting changed the camera, the emotion setting changed what is in the picture (rubbish, decay, distance between the people). The Help text says that a model writes the prompt from the checklist and the template; what it wrote for "very negative" is shown by resting on the picture's name.
- The note's point that the scale carries a norm is visible in the labels: the left end of every bar is the VisionReward "good" end.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- The chips look like a rating of the picture; the Help text says they set the whole checklist at once.
- The bar words only appear at the right end; the other positions are unnamed until the bar is moved.
- The prompt written from the bars is shown only by resting on the picture's name, as the Help text says; a user who has not read that cannot see why "very negative" became rubbish in a field.
- No counter while the pictures compute; the box stays empty.

## 6. What the help text should tell a user

The Help panel's own text, which opens on arrival, is quoted in 1: it says that the checklist is set property by property, that a property left at its neutral word stays out of the prompt, that the chips set the whole checklist at once, that one setting is one prompt, that the first row stays at the neutral word as what every picture is read against, that resting on a picture's name shows what was set and what the model wrote, and where the properties come from. It should add: a bar shows only its current word, at the right end; no counter shows while the pictures compute; the left end of every bar is the end the framework's raters were told to prefer, and the surface lets you draw the other end.

## 7. Use possibilities, action-oriented

- Set everything to “best” and then to “worst” and compare the two pictures with the reference: what does the model think a bad picture is?
- Move one bar at a time to its far end and keep the rest ordinary; collect ten pictures, one per property.
- Set "very clear" and "very negative" (or the reverse) and discuss whether a sharp picture can be sad.
- Run the same bar settings on SD 3.5 Large and Flux 3 Klein and see whether both models have the same idea of "ugly colors".

## 8. Teaching scenarios

**S1 — What is a good picture?** (formal, art, grades 8–11, 90 min). Pairs run “best”, “neutral” and “worst” on one prompt and write down what changed in each picture; then they read the note and discuss who decided which end is "best". Sequence: 10 min; 20 min runs; 30 min description; 30 min reading the note and discussion. Subject link: taste, norm, judgement.

**S2 — One property at a time** (formal, media or computer science, grades 10–13, 2 × 45 min). Groups each take one property, run its two ends, and present the pair; the class builds a table of what each scale changed (camera, light, objects, people). Subject link: operationalisation of aesthetic terms.

**S3 — The sentence in between** (non-formal, media workshop, 90 min). Participants guess from a picture which bars were moved, then rest on the picture's name and compare their guess with the setting and with the prompt the language model wrote from it. Subject link: chains of models. Uncertainty: I did not rest on a picture's name; the Help text says the setting and the written prompt are shown that way.

**S4 — Who lives at the worst end?** (formal, ethics or art, grades 9–12, 90 min). Pairs write a prompt that names people and a place ("a family in front of their house", "people at a bus stop") and run it at “best” and at “worst” with the same model; for the two pictures they fill a table: who is shown (age, clothing, posture), where (the state of the house, the street, the ground), what lies about. Then they read in the note where the properties come from and discuss which people and places the scale's “good” end keeps out of the picture and which it puts at the “worst” end. In my run two bars alone (“very clear”, “very negative”) turned the ordinary house into a run-down farmhouse with rubbish in the field and the woman with the bucket into an old man. Sequence: 10 min prompts; 20 min two runs; 30 min table; 30 min note and discussion. Subject link: norm, representation, who is pictured as “bad”. Uncertainty: I did not run the full “worst” setting on a prompt that names people.

## 9. AI-Lit mapping (built from S1–S4)

**(a) 100 % hits**

- Engage 6 Basic — "Learners understand that biases can exist in the data used to train AI and can be perpetuated when humans design, develop and use AI systems." S1: the “good” end of the scales is a design decision quoted in the note, and the discussion asks who decided which end is “best”.
- Engage 6 Intermediate — "Learners explain how biased data or design choices (e.g. stereotyped content, misclassification, unequal recommendations) can lead AI systems to generate unfair or skewed outcomes for certain groups." S4: the “good” end of the scales is a design decision quoted in the note, and the table records which people and places the “worst” setting produces (decay, rubbish, an old man in my run).
- Shape 2 Intermediate — "Learners assess an AI system performance of a task using defined criteria and feedback from human reviews or benchmark tests." S2: what each scale changed (camera, light, objects, people) as the defined criteria, the class table as the human review.
- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S3: the setting, the prompt a language model wrote from it (read by resting on the picture's name) and the picture are the three stages.

**(b) Mutatis mutandis**


**Beyond the framework**: the framework's Engage 6 examples name stereotyped content as a possible outcome; S4 produces it from a setting whose “good” end is a quoted design decision, so the decision and its picture stand side by side.

**Non-fits**: Engage 1, 3, 4, 5, 7, Manage 1–4, Shape 1, 3, 4, Create 1–4.
