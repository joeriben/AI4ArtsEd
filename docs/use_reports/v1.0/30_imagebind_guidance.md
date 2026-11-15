# 30 ImageBind Guidance — `/latent-lab/imagebind-guidance`

Used 2026-11-03, 00:28–00:50 CET, UI language English, not signed in. Headless browser on the server: I could not listen to the clips; I report what the surface showed and measured.

## 1. What I did

1. Opened `/latent-lab/imagebind-guidance` (tooltip "Gradient-based image guidance"). Preparing column: a yellow line "First generation after a service restart may take 2–3 minutes while GPU kernels compile. Subsequent runs are fast."; "Upload image" with Upload / Sketch and the drop zone; "Example prompts" (ambient soundscape); "Base prompt (optional)"; "Guidance strength 5.0", a slider 0–10 in steps of 0.1; "Guided steps 8", a slider 1–8; Advanced settings (steps 8, range 4–20; Duration 10, range 1–30; CFG 1, range 0.5–3; seed 123456789; "Random variation"); reference Girdhar et al. (2023), "ImageBind: One Embedding Space To Bind Them All", CVPR 2023. Right: empty; during a run the header names the weight file ("imagebind-huge · local", then "stable-audio-3-medium · local").
2. Uploaded the same stormy-lake picture as for MMAudio (1024 × 1024 px, 1362.9 KB). Guidance strength 5.0 (default), guided steps 8, no base prompt. Generate at 00:28:47.
3. Result: a card "Guidance strength: 5.0 · Guided steps: 8 / 8 · Duration (s): 10 · CFG: 1 · Seed: 123456789", the thumbnail, a player "0:00 / 0:10", and the line "Cosine similarity (image-audio proximity): 0.1176".
4. Set the guidance slider to 1.0 (the label read "Guidance strength 1.0"), Generate. Result: a second card "Guidance strength: 1.0 · Guided steps: 8 / 8 · Duration (s): 10 · CFG: 1 · Seed: 123456789", player "0:00 / 0:10", "Cosine similarity (image-audio proximity): 0.0949". The new card stands above the old one; RUNS shows 2.

Runs: 2 clips of 10 s.

## 2. What the controls did

- Upload / Sketch: the picture that guides the sound; Delete clears it.
- Base prompt: optional text for the sound model; left empty.
- Guidance strength: how strongly the picture's embedding pulls the sound during generation; Guided steps: in how many of the steps the pull is applied (8 of 8 here).
- Advanced settings: steps, duration up to 30 s, CFG, seed, random variation.
- Generate: one clip; the result card carries the settings and the cosine similarity between the picture and the clip in the shared embedding space.

## 3. What came out

- Two 10-second clips from the same picture and seed, differing only in the guidance strength: at 5.0 the similarity between picture and sound is 0.1176, at 1.0 it is 0.0949. The stronger guidance brought the sound closer to the picture by the surface's own measure; the difference is small in absolute terms (both far from 1).
- The card states the measure in one number; there is no waveform and no description of the sound.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- "Cosine similarity (image-audio proximity)": a number between 0 and 1 without a scale; nothing says what 0.12 means or whether 0.3 is reachable.
- Guidance strength and guided steps are two sliders for one effect; "8 / 8" in the result is not explained.
- The default duration is 10 s here and 8 s on MMAudio; the difference is in the fields only.
- The yellow line about kernel compilation stands permanently, restart or not.
- Two cards with identical pictures and players: only the numbers differ.

## 6. What the help text should tell a user

Upload a picture; the sound model generates a clip while, in the guided steps, the picture's embedding pulls the clip toward it, as strongly as the guidance strength says. The number under each clip is the cosine similarity between the picture and the finished clip in the shared embedding space of ImageBind, so two clips from the same picture and seed can be compared by that number as well as by ear. A base prompt adds text to the sound model; without one, the picture is the only input. The surface's own yellow line says that the first run after a service restart compiles kernels.

## 7. Use possibilities, action-oriented

- One picture, guidance 0, 2, 5, 10 with the same seed; write down the four similarities and listen to whether the ear agrees with the number.
- The same picture with and without a base prompt.
- A quiet picture and a loud one (a library, a building site) at the same settings; compare the similarities.
- Guided steps 1 against 8 at the same strength.

## 8. Teaching scenarios

**S1 — A number for fitting** (formal, music or computer science, grades 9–12, 90 min). Pairs take one picture, generate at guidance 1, 5 and 10 with the same seed, note the three similarities, listen to the three clips blind and rank them by fit, then compare their ranking with the numbers. Sequence: 10 min picture; 35 min three runs; 25 min blind listening and ranking; 20 min plenary: when the ear and the number disagree. Subject link: measurement, embedding, listening.

**S2 — Sound without motion** (formal, art, grades 7–10, 45 min). The class generates a clip for a painting and one for a photograph of the same motif, listens, and describes what in the picture the sound seems to follow (colour, weather, objects). Subject link: picture description, synaesthesia without the word.

**S3 — Picture or prompt?** (non-formal, workshop, 2 h, age 14+). Groups generate from a picture alone, from a base prompt alone (guidance 0), and from both, and discuss which input the clip follows. Subject link: multimodal models. Uncertainty: with the picture removed the surface requires an upload; "picture alone versus prompt alone" may need guidance 0 instead.

## 9. AI-Lit mapping (built from S1–S3)

**(a) 100 % hits**

- Shape 2 Basic — "Learners define criteria for whether an AI system has accomplished a task." S1: the pairs' blind ranking is their own criterion, set against the surface's number.
- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S3: picture, prompt or both as the input the clip follows; guidance as a pull during generation.

**(b) Mutatis mutandis**


**Beyond the framework**: S1 sets a listener's blind ranking against the model's own similarity number for the same three clips; the framework's Shape 2 examples define criteria but have no number from inside the system to hold them against.

**Non-fits**: Engage 1, 3, 4, 5, 6, 7, Manage 1–4, Shape 1, 3, 4, Create 1–4.
