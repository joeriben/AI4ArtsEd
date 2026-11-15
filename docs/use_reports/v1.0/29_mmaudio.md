# 29 MMAudio — `/latent-lab/mmaudio`

Used 2026-11-03, 00:28–00:54 CET, UI language English, not signed in. Headless browser on the server: I could not listen to the clips; what I report is what the surface showed and what the server recorded.

## 1. What I did

1. Opened `/latent-lab/mmaudio` (tooltip "Image/text to audio (CVPR 2025)"). Preparing column: "Upload image (optional)" with the Upload / Sketch modes and a drop zone ("Click here or drag an image here — PNG, JPG, WEBP (max 10MB)"), "Example prompts" (crackling campfire), "Text prompt (optional)", "Negative prompt", Advanced settings (Duration 8, range 1–8; CFG 4.5; Steps 25, range 10–50 in steps of 5; seed 123456789; "Random variation" checkbox), and a reference Cheng et al. (2025), "MMAudio: Taming Multimodal Joint Training for High-Quality Video-to-Audio Synthesis", arXiv:2412.15322. Right: an empty result area; during a run a line with the prompt and "Duration (s): 8 / CFG: 4.5 / Steps: 25 / Seed: —".
2. Uploaded a picture generated earlier on the Dimension Explorer surface (a stormy lake under dark clouds, 1024 × 1024 px, 1362.9 KB; the zone showed "Original: 1024×1024px, Size: 1362.9KB"). Wrote the prompt "wind and waves on a lake before a storm". Duration 8 (default). Generate at 00:28:43.
3. Result: an audio player "0:00 / 0:08" with the thumbnail of the picture, the line "wind and waves on a lake before a storm · Duration (s): 8 · CFG: 4.5 · Steps: 25 · Seed: 123456789".
4. Removed the picture (the Delete button of the image box; the zone returned to "Click here or drag an image here") and generated from the prompt alone at 00:49:10. Result at 00:54:01: a second player "0:00 / 0:08", same line, seed 123456789. The second card stands above the first.

Runs: 2 clips of 8 s.

## 2. What the controls did

- Upload / Sketch: the upload takes a file; the box shows size and pixel size; Delete clears it.
- Prompt and negative prompt: free text; Example prompts fills the prompt.
- Advanced settings: duration up to 8 s, CFG, steps in steps of 5, seed, random variation.
- Generate: one clip; the header names the weight file ("mmaudio-large-44k-v2 · local"); the result is a standard audio player with the picture (if any) and the settings line; "RUNS" counts.
- Help: not used.

## 3. What came out

- Two 8-second files (`run_1793662683340_2e4e96`, `run_1793663641188_282952`), 44 kHz model. I could not hear them. The surface gives no waveform and no description of the sound; the only readable difference between the two cards is the thumbnail on the first.
- The same seed (123456789) for both runs, since "Random variation" was off; a listener could therefore compare the two clips for what the picture added to the prompt.
- Duration is capped at 8 s on this surface.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- Nothing says that an image, a prompt, or both may be given, except the word "optional" on both labels; the Example prompts are text only.
- "Seed: —" during the run and the number afterwards: the seed is drawn or fixed, but nothing says which until the result.
- The result card shows no waveform; two clips look identical except for the thumbnail.
- The 8-second cap is only visible as the range of the duration field.
- The model name in the header ("mmaudio-large-44k-v2") is the only hint at what runs.

## 6. What the help text should tell a user

Give a picture, a short text, or both; the model generates up to eight seconds of sound that fits what it sees and reads, and the player shows the clip with the picture and the settings. The seed is fixed unless "Random variation" is on, so two runs with the same inputs give the same clip, and a run with and without the picture can be compared for what the picture adds. The model was built for sound to video and here receives a still picture, so what it hears in a picture is a still frame's worth.

## 7. Use possibilities, action-oriented

- One picture, no prompt; the same picture with a prompt that contradicts it (a quiet lake with "thunder"); listen for which wins.
- One prompt, no picture; then with three different pictures; listen for what each picture adds.
- Keep the seed and change only the steps (10, 25, 50).
- A drawing from Sketch mode instead of a photograph.

## 8. Teaching scenarios

**S1 — What does a picture sound like?** (formal, music or art, grades 7–10, 45 min). Pairs pick a picture (own drawing or a free photograph), generate without a prompt, listen, write three words for the sound, then generate again with a prompt that names a sound that is not in the picture and listen for whether the prompt or the picture wins. Sequence: 10 min picture; 15 min two runs; 20 min listening and words. Subject link: sound and image, description.

**S2 — Same seed, different input** (formal, computer science, grades 10–12, 45 min). The class keeps the seed, runs one prompt three times with three pictures, and listens for what stays and what changes; then once with random variation on. Subject link: seed, determinism, conditioning.

**S3 — Foley from stills** (non-formal, film workshop, 2 h, age 14+). Groups take five stills from a short film they made, generate a clip per still, and lay the clips under the film; they discuss where the generated sound fits and where a recorded one would be needed. Subject link: sound design. Uncertainty: 8-second clips; a still frame gives no motion cue.

## 9. AI-Lit mapping (built from S1–S3)

**(a) 100 % hits**

- Create 2 Intermediate — "Learners experiment with AI tools (e.g., text, image or music generators) to develop diverse ideas and produce varied outputs." S1 and S3: clips from pictures and prompts.
- Manage 4 Intermediate — "Learners compare AI outputs to desired results and know when to redirect AI systems or improve outputs themselves." S3: where the generated sound fits and where a recorded one is needed.
- Engage 2 Basic — "Learners know AI is a non-human tool that produces outputs based on patterns of data and lacks authentic context or understanding." S1: the model "hears" a still frame's worth; the contradiction test shows pattern-following.

**(b) Mutatis mutandis**

--

**Non-fits**: Engage 1, 3, 4, 5, 6, 7, Manage 1, 2, 3, Shape 1–4, Create 1, 3, 4.
