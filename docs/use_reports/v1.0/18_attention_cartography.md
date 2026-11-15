# 18 Attention Cartography — `/latent-lab/attention-cartography`

Used 2026-11-02, 22:51–23:17 CET, UI language English, not signed in.

## 1. What I did

1. Opened `/latent-lab/attention-cartography`. Preparing column: Example prompts select, prompt field with the five small buttons, "Advanced settings" (Negative Prompt, Steps 25 (10–50), CFG 4.5, Seed 123456789 with "Random variation"), and a note "Attention Cartography" with two references (Hertz et al. 2022, "Prompt-to-Prompt"; Tang et al. 2022, DAAM). Right: an empty picture area. The run button is the play triangle ("Generate + Analyze"); an "Outputs" drawer button sits in the header. The Help panel opens by itself on the first arrival with the page's text: "Enter a prompt and click "Generate + Analyze"; the image model generates an image for it. Below, the same prompt stands once more, split into single words: click one, and the page draws a colour patch over the image exactly where this word had the most influence in the computation; several words carry several colours. Three controls change the view: the slider picks one of the computation steps, the network depth the layer within it (shallow, middle, deep), and the text-encoder control switches between the two decompositions of the same prompt that the model uses side by side." "The influence of a word spreads over areas, softly bounded and often somewhere other than expected: a word that mattered in the prompt sometimes gets only a small area, a passing one an area over half the picture. Compare an early computing step with a late one. And where a word begins and ends the model sets itself: the one decomposition has 77 tokens for the prompt, the other up to 512, and a long word falls into pieces that only together make the word again." I overlooked it on first use.
2. Typed "a lighthouse and a violin", pressed Generate + Analyze. Done. Server log: SD 3.5 Large, 25 steps, 1024 × 1024, seed 123456789, layers 3, 9 and 17 captured, 25 timesteps, 5 tokens, attention grid 64 × 64.
3. After the run the preparing column gained: "Text Encoder" with two buttons CLIP-L + G (77 Tokens) and T5-XXL (512 Tokens), both active; "TOKENS" chips a, lighthouse, and, a, violin, each with a small number; "Denoising step" slider 0–24 at Step 17 / 25; "Network depth" buttons Shallow (Composition), Middle (Semantics), Deep (Detail), All layers; "Heatmap" slider at 100 %; "Base image" buttons Color, B/W, Off (Off preselected). Two tokens were preselected, lighthouse and violin, each with a colour. The picture area showed the attention map: two coloured regions on black.
4. The script's "switch the text-encoder control if offered": toggled CLIP-L + G off (T5 alone), then T5 off (CLIP alone), then both on. Compared Shallow, Middle, Deep and All layers at step 17. Switched Base image to Color and moved the step slider to 0 and to 24. Toggled the token chips off and on.
5. Opened Advanced settings and the Outputs drawer (RUNS: one entry, "a lighthouse and a · Steps 25 · CFG 4.5").

Runs: 1 generation with analysis; all other changes are instant re-renderings of the captured maps.

## 2. What the controls did

- Generate + Analyze: generates the picture with SD 3.5 Large and records the cross-attention of every token at three layers and every step.
- Text Encoder: toggles which encoder's tokens are mapped; the chips' small numbers change with it. CLIP alone: no numbers (one token per word). T5 alone: a (2), lighthouse (2), a (2). Both: a (3), lighthouse (3), and (2), a (3), violin (2); the number is the sum of the sub-tokens over the active encoders.
- Token chips: toggle; a selected chip gets a colour (the first selected red, the second blue, in the order of selection); the map draws one coloured region per selected token. With no chip selected the map is empty.
- Denoising step: re-renders the map for that step, 0 to 24.
- Network depth: Shallow, Middle, Deep or All layers.
- Heatmap: opacity of the overlay.
- Base image: the generated picture under the map in colour, in grey, or none.
- Advanced settings, RUNS strip, Outputs drawer: as listed above.
- Help: opens by itself on the first arrival with the page's text quoted in 1; every later click shows that text again.

## 3. What came out

- The picture: a white lighthouse with a red lantern on a rocky coast at sunset, and a violin with its bow leaning upright in the foreground right, as tall as a person.
- All layers, step 17, base off: a red lighthouse-shaped region left of centre and a blue violin-shaped region right, clearly separated, with faint red speckle over the sky. The map draws the two things where the picture has them.
- CLIP alone and T5 alone, same step: nearly the same two shapes; T5's lighthouse region is a little taller and narrower. Deep (Detail) alone: the same sharp shapes. Middle (Semantics): a diffuse wash, red and blue blotches mixed over the whole square, no shape. Shallow (Composition): a near-uniform magenta wash. The shapes come from the deep layer; the two shallower layers show no object.
- With the colour base: at step 17 the red lies on the lighthouse tower and lantern and the blue on the violin's body, with blue specks on the rocks beside it. At step 0 the red spreads over the lighthouse and the sky around it and the blue blotches lie loosely over the rocks; at step 24 both are tight on the objects. The regions settle during the denoising.
- The chips' numbers show that "lighthouse" is three sub-tokens for the two encoders together; "a" is three as well.
- The server log recorded, before the run, that a ComfyUI chunk file for this instrument was not found and that the diffusers backend was "unavailable, no fallback"; the run nevertheless succeeded. Nothing of this reached the surface.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- The map's colours are assigned in the order of selection, so deselecting and reselecting swaps red and blue; nothing says so.
- Deselecting both chips leaves an empty black square.
- Step 17 and "All layers" are the defaults; the Shallow and Middle maps look broken (a wash) to someone who has not read that the shapes live in the deep layer.
- The chips' numbers have no legend; the Help text says that a long word falls into pieces, and the numbers count them.
- The Advanced settings are above the analysis controls and collapse the column; the step slider and the depth buttons appear only after a run.
- The references name two papers; what the map shows stands in the Help text, and the note box on the page has no sentence on it.

## 6. What the help text should tell a user

The Help panel's own text, which opens on arrival, is quoted in 1: it says to enter a prompt and click "Generate + Analyze", that clicking a word draws a colour patch where that word had the most influence, what the three controls change, that the influence spreads over areas and often lies somewhere other than expected, to compare an early step with a late one, and that the two decompositions have 77 and up to 512 tokens. It should add: the picture is generated by SD 3.5 Large; the colours are assigned in the order of selection; the shapes of the named things appear in the deep layer and settle in the later steps, and the shallow and middle layers show diffuse maps; the step slider and the depth buttons appear only after a run; with the base image on, the coloured regions lie over the picture.

## 7. Use possibilities, action-oriented

- Prompt two things, generate, and read at which step each thing's region first takes its shape.
- Select a function word ("and", "a") and see where its attention lies compared with a noun.
- Compare CLIP and T5 for a long sentence or a rare word and read the sub-token counts on the chips.
- Change one word of the prompt, generate again with the same seed, and compare the two maps of the unchanged word.

## 8. Teaching scenarios

**S1 — Where the word lands** (formal, art or computer science, grades 9–12, 90 min). Pairs write a prompt with two things, generate, select the two chips, and move the step slider from 0 to 24 in steps of four, noting at which step each thing's region appears; then they switch the depth and describe the difference in one sentence each. Sequence: 10 min prompt; 5 min generation; 30 min slider protocol; 20 min depth comparison; 25 min plenary on what "attention" is on this surface. Subject link: how a text becomes a picture, step by step.

**S2 — Shallow, middle, deep** (formal, computer science, grades 11–13, 90 min). After a generation the class compares the four depth settings at three steps, records which show shapes, and reads the abstract of one of the two references to find the term "cross-attention"; groups explain to each other what the map is a map of. Subject link: neural network layers, attention. Uncertainty: the references are papers in English; the teacher selects the passages.

**S3 — Two encoders** (non-formal, media workshop, age 14+, 2 h). Participants generate with a long prompt and with a prompt containing a rare or foreign word, switch between CLIP and T5, read the sub-token counts on the chips and compare the two encoders' maps for the same word. Subject link: tokenisation, text encoders. Uncertainty: the difference between the encoders' maps was small for "lighthouse" and "violin"; a rare word may show more or nothing.

## 9. AI-Lit mapping (built from S1–S3)

**(a) 100 % hits**

- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S1: the step protocol describes how the model places the named things over 25 steps.
- Engage 2 Advanced — "Learners explain how different AI systems work using language that does not attribute human traits or abilities, knowing that their phrasing shapes understanding." S2: "attention" is the surface's own word, and the groups must explain it as a weighting of regions, not as looking.
- Shape 1 Intermediate — "Learners describe the purpose, intended users and basic constraints of a specific AI tool." S2: the constraints are on the surface: one model, three captured layers, 25 steps, 64 × 64 grid.

**(b) Mutatis mutandis**

- Engage 2 Basic — "Learners know AI is a non-human tool that produces outputs based on patterns of data and lacks authentic context or understanding." Modification: the misleading phrase met here is that the model "looks at" the prompt; S1 at the lower grades replaces it with "the word steers a region", read off the map. The framework's classroom example has learners replace misleading phrases about AI with accurate ones; here one phrase is replaced from the map.

**Beyond the framework**: the framework's knowledge statement 1.1 names "weights"; the map shows them, per word and per step, on the picture they produce. S1's step protocol records what the framework states.

**Non-fits**: Engage 1, 3, 4, 5, 6, 7, Manage 1–4, Shape 2, 3, 4, Create 1–4.
