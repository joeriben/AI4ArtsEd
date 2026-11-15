# 21 Concept Algebra — `/latent-lab/concept-algebra`

Used 2026-11-02, 23:37–23:50 CET, UI language English, not signed in.

## 1. What I did

1. Opened `/latent-lab/concept-algebra` (sidebar tooltip "Vector arithmetic"). Preparing column: Example prompts select with three triples ("the street where I live, in the morning, with an animal − the street where I live, in the morning + a river"; the street seen through the eyes of a child − the street + the street seen through the eyes of an adult; "a street in the evening, with people − a street in the evening + loneliness"), the fields "Prompt A (Base)", "Prompt B (Subtract)", "Prompt C (Add)" under the line "A − B + C = ?", "Encoder" chips (All (recommended), CLIP-L (768d), CLIP-G (1280d), T5-XXL (4096d)), "Advanced settings" (Negative Prompt, Steps 25, CFG 4.5, Subtraction scale 1 (0–3, step 0.1), Addition scale 1 (0–3, step 0.1), Seed 123456789, "Random variation"), and "Research References" (Mikolov et al. 2013, "Distributed Representations of Words and Phrases and their Compositionality", NeurIPS 2013; Liu et al. 2022, "Compositional Visual Generation with Composable Diffusion Models", ECCV 2022, both with DOI). Right: two columns "Reference (Prompt A)" and "Result (A − B + C)" with "Enter three prompts and click Compute — the result of the vector arithmetic will appear here." The run button is the play triangle ("Compute").
2. Typed A "king", B "man", C "woman"; both scales at 1. Compute; both pictures arrived.
3. Set the Addition scale to 2, Compute; the result arrived. RUNS 2.

Runs: 2 computations, 3 pictures (the reference is kept).

## 2. What the controls did

- Three prompt fields with the five small buttons each; Example prompts fills all three.
- Encoder chips: whose embedding the arithmetic is done on.
- Subtraction scale / Addition scale: factors on B and C in A − s·B + t·C.
- Compute: generates the reference from A alone and the result from the combined embedding, same seed.
- RUNS strip, Hide column, Help: as elsewhere.

## 3. What came out

- Reference "king": a painted portrait of an old bearded king, gold crown with a cross, red robe with ermine, on a yellow ground, frontal.
- Result "king − man + woman", scales 1 and 1: a young woman with long black hair, a gold-and-red crown with a cross, a red, black and gold robe with gold borders, on a gold ground, in a flat illustration style, frontal. The crown, the cross, the colours and the pose stayed; the beard and the age went; the style changed from painterly to flat.
- Result with Addition scale 2: a photographic portrait of a young woman with a jewelled crown, a white veil, two braids, long earrings and an embroidered robe on a muted brown ground. More jewellery, more fabric, and a style that no longer shares anything with the reference.
- The classic analogy holds on this surface: the result reads as "queen" in both runs; the scale decides how far the result moves from the reference's style.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- "A − B + C = ?" is the only explanation; the references are papers.
- Nothing says that the reference is A alone and that the result shares its seed.
- The scales sit in Advanced settings; their effect (style drift at 2) is not described.
- The example triples are long sentences; the classic word triple is not among them.
- No progress display while a computation runs.

## 6. What the help text should tell a user

Three prompts: the model's text embedding of B is subtracted from that of A and C's is added, and the picture of that sum stands next to the picture of A alone, both with the same seed. The two scales in Advanced settings weight the subtraction and the addition; at 1 and 1 the result keeps much of A's style, at larger values it moves further away. Short prompts of one or two words make the arithmetic readable; sentences mix many things at once. The references name the word-vector arithmetic (2013) and the diffusion composition (2022) the surface builds on.

## 7. Use possibilities, action-oriented

- Run the classic "king − man + woman" and then your own triples ("doctor − man + woman", "Paris − France + Japan").
- Run one triple at Addition scale 0.5, 1, 2 and 3 and pin the results in a row.
- Subtract a word from an occupation ("a nurse − woman") and look at what is left.
- Run the same triple with CLIP-L only and with T5 only and compare.

## 8. Teaching scenarios

**S1 — king − man + woman** (formal, computer science or mathematics, grades 10–13, 90 min). Pairs run the classic, then two triples of their own, and write for each what stayed from A and what came from C; the teacher shows the 2013 paper's famous example. Sequence: 10 min intro; 30 min three computations; 30 min written comparison; 20 min plenary on vectors as meaning. Subject link: vectors, analogy.

**S2 — What is left of a nurse** (formal, language teaching or ethics, grades 9–12, 90 min). Groups run "a nurse − a woman + a man", "a boss − a man + a woman" and similar; they record what the result keeps (uniform, setting, age) and discuss what the model holds in the word. Subject link: stereotype, connotation. Uncertainty: results can be unexpected; the teacher previews.

**S3 — The scale** (non-formal, art workshop, age 16+, 2 h). One triple, four addition scales (0.5, 1, 2, 3); participants pin the four results in a row and mark where the style breaks away from the reference. Subject link: gradation, style.

## 9. AI-Lit mapping (built from S1–S3)

**(a) 100 % hits**

- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S1: the written comparison per triple (what stayed from A, what came from C) and the plenary on vectors as meaning, against the idea that the model understands the word.
- Engage 6 Intermediate — "Learners explain how biased data or design choices (e.g. stereotyped content, misclassification, unequal recommendations) can lead AI systems to generate unfair or skewed outcomes for certain groups." S2: what the word "nurse" carries after the subtraction.

**(b) Mutatis mutandis**

- Engage 6 Basic — "Learners understand that biases can exist in the data used to train AI and can be perpetuated when humans design, develop and use AI systems." Modification: what S2 sees is the bias as it arrived in the embedding from the training data; the data themselves are not on the surface, their trace in the word is. The framework's classroom example asks what the data about a person capture and leave out; S2 asks what the word "nurse" still carries once "woman" is subtracted.

**Non-fits**: Engage 1, 3, 4, 5, 7, Manage 1–4, Shape 1–4, Create 1–4.
