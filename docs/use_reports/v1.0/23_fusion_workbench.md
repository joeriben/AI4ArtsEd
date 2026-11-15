# 23 Encoder Fusion Workbench — `/latent-lab/fusion-workbench`

Used 2026-11-02/03, 23:50–00:45 CET, UI language English, not signed in.

## 1. What I did

1. Opened `/latent-lab/fusion-workbench` (sidebar "Enc. Fus. Workbench", tooltip "3-axis comparison"). Preparing column: the prompt field prefilled with the house sentence ("A house stands in a landscape, surrounded by farmland, nature and animals. Some people can be seen."); under it the hint "Short text: T5 reads in barely more here than CLIP does. The perspectives in the field make a text out of a sentence — 'Your Story' is written for that."; a button "T5 expand" that opens a textarea "Optional T5 enrichment — added to the T5 encoder only, held constant across the sweep"; "X · columns" with a select set to "Fusion strategy" and five chips (Centered Fade, Legacy, Dual Alpha, Slerp, Normalized), all preselected; "Y · rows" with a select set to "Denoising window" and three ranges, "composition" Steps 1–8, "semantics" Steps 9–17, "detail" Steps 18–25, each with a two-handle slider and two number fields, and the sentence "The fusion is injected only in the steps the window covers, of 25 in the run."; "Z · slider" set to "No third axis" ("Two axes then carry the sweep, and this axis shows no slider."); a block "Fusion formula (active)" that prints the formula of the selected strategies (Centered Fade: core = w_C·CLIP + w_T5·T5, tail = T5 ×1, h=1; α≤0: w_C=max(1,−α), w_T5=1+α; α>0: w_C=1−α, w_T5=max(1,α); Legacy: core=(1−α)·CLIP+α·T5; Dual Alpha: tail=0.15·α·T5; Slerp: the spherical interpolation formula; Normalized: tail = T5·‖core‖/‖T5‖; and the key "core = the first 77 token positions (CLIP-L+CLIP-G, padded to 4096d) blended with T5; tail = the T5-only remainder (positions 78–512). α is the fusion strength value."); Advanced settings with α 20, CFG 5.5, entry block 0, seed 42, negative prompt, steps 25; the sentence "Assign the axes, then run a sweep. Each cell is recorded to the research store (purpose: workbench)." Right: an empty grid headed "Denoising window \ Fusion strategy", three rows, five columns.
2. Pressed "T5 expand" and wrote into the T5 field a second scene that is not in the prompt: "A lighthouse stands on a rocky coast at night. A storm is coming in from the sea, and a small boat is heading for the harbour." Kept the house prompt.
3. Clicked four strategy chips off, so that only Centered Fade remained; the run button's title changed from "Run sweep · 15 cells" to "Run sweep · 3 cells". Ran at 23:56:50. The header counted "Image 0 / 3 … 3 / 3" and named the weight file ("sd3.5_large.safetensors · local", at other moments "stable-diffusion-3.5-large · local").
4. Clicked Centered Fade off and Slerp on ("Run sweep · 3 cells"), ran again; three pictures.
5. Read the six pictures (3 below).

Runs: 2 sweeps, 6 pictures.

## 2. What the controls did

- Prompt field: as on the other picture surfaces (Copy, Paste, Choose Perspective, Translate, Delete).
- T5 expand: shows the second field; its text goes to the T5 encoder only and stays the same in every cell.
- X / Y / Z selects: assign what varies along columns, rows and a third axis; with "No third axis" the slider is hidden.
- Strategy chips: toggle; the run button's title counts the cells (strategies × windows).
- Window sliders and number fields: set the step range of each row; the three defaults cover 1–8, 9–17, 18–25.
- Fusion formula block: changes with the selected strategies; it is a display, not a control.
- Advanced settings: α, CFG, entry block, seed, negative prompt, steps.
- Run sweep: one picture per cell, same seed, the header counts; cells fill as they arrive.

## 3. What came out

- Centered Fade, Steps 1–8 (composition): two pictures stacked. At the top a black gabled house on a green hill under a grey sky, with a figure at its wall; below, as if hung on a wall, a darker scene with a pond, two cows drinking and a longhorn walking in at the lower left.
- Centered Fade, Steps 9–17 (semantics): a wall-like block of straw-yellow texture across the whole middle of the picture, with a pig and a person perched on its top edge and a lawn and trees behind; the house is reduced to a roof silhouette on the block. The scene is dismembered.
- Centered Fade, Steps 18–25 (detail): a white farmhouse with a brown roof, sheep and cows in front, trees, a sunlit field with fine vertical streaks over it. Close to what the plain prompt gives.
- Slerp, Steps 1–8: a house with lit windows and people inside, standing on a floating block of clipped hedge, the block mirrored upside down beneath it, two goats in the sky below. A surreal composition.
- Slerp, Steps 9–17: a white house with a dark roof, cows, a truck and a jeep in front, trees. Ordinary.
- Slerp, Steps 18–25: a white house with sheep, cows and hedges, vertical rain-like streaks over the field. Ordinary with a texture artefact.
- Across the grid: the row changes the picture far more than the column. Fusion in the first eight steps produces a composition of two pictures in both strategies; in the middle steps it damages the scene (Centered Fade) or leaves it ordinary (Slerp); in the last steps it adds a streak texture and nothing else. The lighthouse, the storm and the boat given to T5 alone appear in none of the six pictures as objects; the dark pond and the rain streaks are the most that could be read as traces of "storm" and "sea".
- The grid shows row and column headers only; α, seed and the active formula stand in the preparing column, not at the cell.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- Five strategies preselected: the first press would compute 15 pictures; the number stands only in the button's tooltip.
- X, Y, Z and the formula block are the language of a parameter sweep; nothing says what one would look for in a row or a column.
- α stands in Advanced settings as a number (20); with the formula on the screen a user can compute that Centered Fade with α=20 sets w_C to −19 and w_T5 to 20, but nothing says what α means here or how it relates to the slider of the Encoder Fusion surface.
- The T5 field is hidden behind "T5 expand", and the hint under the prompt speaks of "Your Story", a perspective that is on another surface.
- "Each cell is recorded to the research store (purpose: workbench)": a user does not know what the store is or who reads it.

## 6. What the help text should tell a user

Choose which fusion strategies form the columns and which denoising windows form the rows; each cell is one picture from the same prompt and seed, with the fusion applied only in the steps its row covers. The optional text behind "T5 expand" goes to the T5 encoder alone and is the same in every cell, so a difference between cells never comes from it. The sweep computes one picture per cell; the header counts them. Read along a row to see what the strategy changes and down a column to see what the window changes; the formula block states what the active strategy computes, and the pictures are recorded for research.

## 7. Use possibilities, action-oriented

- One strategy, the three windows: see at which stage of the denoising the fusion acts on composition, on objects, or on texture only.
- Two strategies, one window: see whether the strategy matters where the window is held constant.
- The same sweep with and without a T5 enrichment, and look for the enrichment in the pictures.
- Change the seed in Advanced settings and run the same sweep again to separate what the seed does from what the window does.

## 8. Teaching scenarios

**S1 — Where in the process does the mixture act?** (formal, art or computer science, grades 11–13, 90 min). Pairs keep one strategy and the three default windows, run the sweep, and write for each of the three pictures what changed against the plain picture: the arrangement, the objects, or the surface. Then they switch to a second strategy and compare the two rows. Sequence: 10 min setting the axes; 30 min first sweep (used for reading the formula block); 30 min second sweep and the table of changes; 20 min plenary on the stages of denoising. Subject link: process of image generation, early and late steps.

**S2 — The hidden sentence** (non-formal, media workshop, 2 h, age 15+). Groups write a second scene into the T5 field that the prompt does not contain, run one strategy over the three windows, and search the pictures for any trace of the second scene; then they discuss what it means that a text given to one encoder can leave no object in the picture. Sequence: 15 min writing the two texts; 45 min sweep; 30 min searching and comparing; 30 min discussion. Subject link: how a prompt reaches a model through several encoders.

**S3 — Reading a formula against a picture** (formal, mathematics or computer science, grades 12–13, 45 min). The class reads the formula of the active strategy, computes the weights for the α in Advanced settings (for Centered Fade with α=20: w_C = 1−α = −19, w_T5 = max(1,α) = 20) and for α=0, then runs one cell each and describes what a negative weight on CLIP does to the picture. Subject link: weighted sums, interpolation.

## 9. AI-Lit mapping (built from S1–S3)

**(a) 100 % hits**

- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S1: the table of what the fusion changes at each stage is a description of how this model builds a picture over 25 steps.
- Manage 4 Intermediate — "Learners compare AI outputs to desired results and know when to redirect AI systems or improve outputs themselves." S2: the search for the second scene in the pictures against the intention, and the decision where it would have to go instead (the prompt).
- Shape 2 Intermediate — "Learners assess an AI system performance of a task using defined criteria and feedback from human reviews or benchmark tests." S1: the three stages (arrangement, objects, surface) the pairs define as the criteria, and the class's table as the human review.

**(b) Mutatis mutandis**


**Beyond the framework**: S3 computes the weights of the active strategy by hand and runs the cell; the framework's Engage 2 examples stop at explaining a process in words.

**Non-fits**: Engage 1, 3, 4, 5, 6, 7, Manage 1–3, Shape 1, 3, 4, Create 1–4.
