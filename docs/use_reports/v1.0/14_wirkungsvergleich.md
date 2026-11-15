# 14 Interception Scope — `/latent-lab/perspectives-on-a-template`

Used 2026-11-02, 22:08–22:26 CET, UI language English, not signed in. The use script says "Use the template: answer it once"; the Help text calls the prompt field the template, and I took the example prompt as the template.

## 1. What I did

1. Opened `/latent-lab/perspectives-on-a-template` (sidebar "Interception Scope", Prompt Interception Lab). Preparing column: Example prompts select with one entry ("A house stands in a landscape, surrounded by farmland, nature and animals. Some people can be seen."), the prompt field (same placeholder as on Language Model Comparison), "Perspectives" with a round "+" button, "Image model" chips SD 3.5 Large 8.1B (selected), Flux 2 32B, Flux 3 Klein 5.6B, and a note "Interception Scope": De Rosa Palmini and Cetinic (2025) grouped prompts from a public image platform by shared wording, groups sharing 80 % or more of their words came with more uniform pictures than groups sharing 50 to 70 %, richer wording went with more varied pictures (Vendi score); in Stable Diffusion modifiers written against a stereotype often left it in place ("a white poor person" still mostly dark-skinned faces, "a photo of an African man and his fancy house" still a simple hut, Bianchi et al. 2023). Two references with arXiv numbers and DOI. Right: one large box "Reference image". The Help panel opens by itself on the first arrival with the page's text: "Prompt Interception is the step in which this platform writes a prompt over again through a perspective. Here that step runs several times on the same template, once per perspective, and one image model shows what each of them wrote. Write the template — or drag a picture onto the field, and its description then stands there as the template, where it can be worked on further. Choose the perspectives. Where the template was written, the first picture holds it with that step left out; where it was read from a picture, that picture stands first as the reference and the picture beside it is the first step, with no perspective on it; resting on a perspective — holding it, on a touch screen — shows the text that perspective wrote." "Every picture carries the same template, and between two of them the perspective is the only difference, so a picture can be read for what that one perspective does to the template. The writing model is the one this platform is set to intercept with, and this surface makes no choice about it. One image model runs, because what is compared here is perspectives — the comparison of image models is its own instrument." "This help can support you with the comparative analysis of the results. Just ask it about them." I overlooked it on first use.
2. Chose the example prompt. Pressed "+": the same round chooser as on Language Model Comparison (seven icon groups, 31 perspectives, listed in report 13). Picked "Sensitive" (attitudes); the chooser closed and a round bubble with an × appeared in the Perspectives row. Pressed "+" again and picked "Bauhaus" (arts). Two bubbles.
3. "Run the series". Three pictures arrived. Layout: the reference image large at the left, one box per perspective with the perspective's bubble and name as caption, "Interpretation help" at the top right.
4. Changed the perspective once: removed Bauhaus with its ×, pressed "+", picked "Daguerreotype" (technical imaging). Run the series: only the new box was computed; the reference and the Sensitive picture stayed as they were (same files).

Runs: 2 series, 4 pictures, 3 rewrites.

## 2. What the controls did

- "+": opens the chooser; several perspectives can be added, each as a bubble with × to remove.
- Image model chips: one model draws every box with the same seed (the server log shows one fixed seed).
- Run the series: rewrites the prompt once per perspective and draws reference and perspectives. The Help text says that resting on a perspective (holding it, on a touch screen) shows the text it wrote; I did not use that and read the rewrites in the server log.
- Changing the row recomputes only the added box.
- Interpretation help, Hide column: not used. Help: opens by itself on the first arrival with the page's text quoted in 1; every later click shows that text again.

## 3. What came out

- Reference (SD 3.5 Large): a cream farmhouse with a red roof in a mown field under a wooded hill, cows, sheep, goats, three or four people.
- Sensitive: the rewrite (log) "This is a slow-cinema film: one uncut 16mm take of roughly four hours, projected as a loop onto a wa…"; the picture a close-up of a whitewashed wall with two windows behind a wire fence and wheat ears, a tree at the right, black film bars top and bottom; no person, no animal.
- Bauhaus: the rewrite "Settlement Unit Model No. 4: a site model on a square plywood base board, 80 × 80 cm, photographed f…"; the picture an architectural model seen from above, a white block house on a white board with tiny model trees, two cow figurines, one figure, a red bar and green strips, the board lying on real green and yellow fields.
- Daguerreotype: the rewrite "Black-and-white daguerreotype: a farmhouse standing in open country, ringed by tilled fields, hedger…"; the picture a grainy black-and-white plate with dark corners, a two-chimney stone house, cows at a fence, two children in a ploughed field.
- The three perspectives did three different things to the sentence: Sensitive removed the people and the overview and kept a wall; Bauhaus turned the scene into a model of itself; Daguerreotype kept the scene and changed the medium. The surface shows the pictures and the names; the sentence the model wrote in between is shown, as the Help text says, by resting on the perspective, which I did not do.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- The rewritten prompt, the instrument's actual intervention, is shown only by resting on a perspective, as the Help text says; a user who has not read that sees a name and a picture.
- The chooser's groups are icons without names.
- During the first run the boxes stay empty until the reference arrives; no counter.
- The note's findings (uniform pictures, stereotypes that stay) are about other prompts and platforms; next to three pictures they read as this surface's result.
- The painting path (drag a work onto the field; it stands first as the reference, its description becomes the template) is the surface's richest use and is named only in the Help text and the field's placeholder; the one example prompt is a farm scene, and nothing on the surface shows a work.

## 6. What the help text should tell a user

The Help panel's own text, which opens on arrival, is quoted in 1: it says what Prompt Interception is, that the step runs here once per perspective on the same template with one image model, that the template is written or read from a picture, that the first picture holds the template with the step left out, that resting on a perspective shows the text it wrote, and that between two pictures the perspective is the only difference. What it should say first is what the instrument is for: getting to know what Prompt Interception does, by watching one source go through several perspectives and talking about the differences. It should say that a painting can be that source: dragged onto the field, it stands first on the wall as the reference, its description becomes the template and can be edited before the run, and each perspective then writes the painting over again in its own register, the text one rest away, the picture beside it. It should say that the Help has the pictures of the run and can be asked about two of them side by side, which its closing line says only in passing. And it should add that adding or removing a perspective recomputes only the changed box, and that the note on the left reports what research found about prompt wording and stereotypes in other settings, not what this run found.

## 7. Use possibilities, action-oriented

- Drag a painting from the public domain onto the template field (Caspar David Friedrich's "Wanderer above the Sea of Fog", 1818, from Wikimedia Commons), read the description it becomes, and correct by hand what the describer missed; then add Slang, On the Contrary!, Renaissance and Daguerreotype and run. Rest on each perspective, read what it wrote, and talk about what it kept of the painting and what it made of it.
- Run one whole group of perspectives on one work, the five of critical analysis (Against the Model, One World, Planetarizer, Critique of Consumption, The Unspoken), and say for each what it does to a Romantic landscape.
- Read the text before the picture: rest on the perspective first, say what it added that the template did not have, then look whether the picture shows it.
- Edit the template before the run: strike the fog, add a city, keep the perspectives, and see what each perspective does with the changed template.
- Ask the Help about two pictures side by side; it has the pictures of the run.
- Run the same perspectives once more under another image model (SD 3.5 Large, Flux 2, Flux 3 Klein) and see what the model changes and what the perspective keeps.
- Play it backwards: show one picture, let the others guess which perspective wrote it, then rest on it.
- Write a prompt against a stereotype (the note's Bianchi examples), add two perspectives, and check whether the stereotype stays.

## 8. Teaching scenarios

The instrument is for getting to know what Prompt Interception does: the same source goes through several perspectives, each writes it over again, one picture per perspective shows what it wrote, and the text itself is one rest away. The strongest source is a work everyone in the room can see: a painting dragged onto the field.

**S1 — Wanderer above the Sea of Fog, five times** (formal, art, grades 7–10, 90 min). The class drags a public-domain reproduction of Caspar David Friedrich's painting (1818) onto the template field. First talk: the description it becomes, read against the painting on the wall, what the describer saw and what it missed (the back turned to us, the fog, the rock), corrected by hand. Then five perspectives, one from each of five groups: Slang, On the Contrary!, Renaissance, Daguerreotype, Critique of Consumption; the choice itself is discussed (what might Slang do to a Romantic painting). Run. Wall: the painting as the reference, the picture without perspective, five pictures. Second talk, picture by picture: rest on the perspective, read its text aloud, then: what it kept of the painting, what it changed, where the wanderer now stands, in whose voice the text speaks. Closing: each pupil writes one sentence on what Prompt Interception is. Sequence: 10 min painting and description; 10 min choosing with reasons; 15 min run (used for the first talk); 40 min second talk with the texts; 15 min closing sentences read aloud. Subject link: image analysis, Romanticism, register and paraphrase; what an instruction does to a work. Uncertainty: not run; what the describer writes for a known painting was not seen; whether a painter's name written into the template passes the platform's checks I did not test.

**S2 — The sentence in between** (formal, language teaching or media, grades 9–12, 45 min, after S1 or with its wall). Pupils see the painting and one perspective's picture and write the text they think that perspective wrote; then they rest on the perspective, read the real one, and mark what they guessed right and what the perspective did that they did not expect. Subject link: inference from output to instruction; register. Uncertainty: I did not rest on a perspective; the Help text says the rewrite is shown that way.

**S3 — Own work, two groups of perspectives** (non-formal, art workshop, age 14+, 2 h). Participants bring one work of their own (a drawing, a painting, a photograph of an object) and drag it onto the field; they run the whole arts group (Bauhaus, Literati, Renaissance) and the whole attitudes group (Forceful, mad world, Sensitive) on it; two rows on the wall. Talk: which perspectives change the medium, which the stance, which the content; one sentence per perspective, "this perspective does … to a picture"; and whose work the Renaissance version of a drawing is. Sequence: 20 min works and descriptions; 40 min two runs; 45 min talk and sentences; 15 min round. Subject link: own work under a foreign register; authorship. Uncertainty: not run.

**S4 — Writing a perspective** (formal, language teaching, grades 9–13, 2 × 45 min). After S1, groups write a perspective of their own under Your Call! in the chooser, in their own words (a stance, a genre, a way of seeing), run it on the painting next to one platform perspective, read the two texts, and revise their wording once. Subject link: writing an instruction, revision. Uncertainty: I did not test whether Your Call! opens a text field on this surface; the chooser is the same as on Flow, where the page's strings describe writing and saving a perspective.

**S5 — Does the modifier work?** (non-formal, media workshop, 2 h, age 14+). Participants read the note's Bianchi example, write a prompt that works against a stereotype, add two perspectives, and check whether the stereotype stays in the picture. Subject link: stereotypes and prompt wording.

## 9. AI-Lit mapping (built from S1–S5)

**(a) 100 % hits**

- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S1: the closing sentence of each pupil on what Prompt Interception is, written after the texts the perspectives wrote were read aloud; S2: the text a pupil expects, then the real one. The misconception met is that the picture is made from the painting; what the image model receives is the perspective's text.
- Engage 2 Basic — "Learners know AI is a non-human tool that produces outputs based on patterns of data and lacks authentic context or understanding." S1: the description the painting becomes is read first for what the describer saw and what it missed; what the painting means, the class brings.
- Create 2 Intermediate — "Learners experiment with AI tools (e.g., text, image or music generators) to develop diverse ideas and produce varied outputs." S1 and S3: one template, five or six perspectives, one wall; the framework's classroom example compares how different prompts produce varied interpretations of the same idea, and here the different prompts are the perspectives' texts, readable one rest away.
- Create 1 Intermediate — "Learners compare AI-generated suggestions to their own ideas during a brainstorming process." S2: the text a pupil writes for a perspective, then the perspective's own; S4: the own perspective next to a platform perspective on the same painting.
- Create 3 Intermediate — "Learners refine their work through iterative exchanges with AI, comparing those outputs to their own ideas to determine what serves their goals." S4: the own perspective run, its text read against the platform perspective's, the wording revised once.
- Create 4 Basic — "Learners know that AI-generated content may reuse or copy work protected by intellectual property or copyright laws and recognise implications for the humans who created the original work." S3: a participant's own drawing under Renaissance or Bauhaus, and the question whose work the result is; S1 uses a painting in the public domain for that reason.
- Engage 6 Intermediate — "Learners explain how biased data or design choices (e.g. stereotyped content, misclassification, unequal recommendations) can lead AI systems to generate unfair or skewed outcomes for certain groups." S5: a prompt written against a stereotype, and the check whether the stereotype stays in the picture under two perspectives; the note's Bianchi examples are the finding the group tests.
- Shape 2 Intermediate — "Learners assess an AI system performance of a task using defined criteria and feedback from human reviews or benchmark tests." S5: the stereotype in or out of the picture as the defined criterion, per perspective; S3: the sentence per perspective (medium, stance or content) as the group's own review of what each one did.

**(b) Mutatis mutandis**

- Shape 1 Intermediate — "Learners describe the purpose, intended users and basic constraints of a specific AI tool." Modification: the tool described is one step of the platform, Prompt Interception, rather than a tool among several; S1's closing sentences name its task (write the template over again through a perspective), its input (the template) and its outputs (the text, the picture), as the framework's classroom example has learners do per tool. Intended users are not on the surface.

**Beyond the framework**: the framework's Create 1 has AI expand an idea, and its Engage 2 examples have learners explain how a tool works. Here the intervention itself is on the surface: a painting from 1818 is written over again in five registers, each text is one rest away from its picture, and the class talks about each. The framework has no competence for reading what an instruction does to a work; Prompt Interception is this platform's central step, and this is the surface made to show it.

**Non-fits**: Engage 1, 3, 4, 5, 7, Manage 1–4, Shape 3, 4.
