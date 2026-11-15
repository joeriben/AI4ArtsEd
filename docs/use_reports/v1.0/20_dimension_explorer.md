# 20 Dimension Explorer — `/latent-lab/dimension-explorer`

Used 2026-11-02, 23:17–23:40 CET, UI language English, not signed in.

## 1. What I did

1. Opened `/latent-lab/dimension-explorer` (sidebar tooltip "Dimension-level analysis"). Preparing column: Example prompts select with three pairs ("A red house by the lake / A blue house by the lake"; the street where I live as a pencil drawing / as an oil painting; "a meadow at noon / a meadow at midnight"), "Prompt A (Original)" and "Prompt B (Comparison)" fields with placeholders, "Encoder" chips All (recommended), CLIP-L (768d), CLIP-G (1280d), T5-XXL (4096d), "Advanced settings" (Negative Prompt, Steps 25, CFG 4.5, Seed 123456789, "Random variation" unticked), and "Select dimensions from Prompt B": a two-handle range slider, two number fields (from – to), buttons "+", "All", "None", "Descending", the line "0 dimensions from Prompt B selected (rank – of 0)" and "The 0 dimensions from Prompt B with the largest difference to Prompt A". Right: three empty columns "Original (Prompt A)", "Modified (Transfer from Prompt B)" (with the sentence "Select a rank range below and click ▶ 2 — this will show prompt A with the transferred dimensions from B (same seed).") and "Original (Prompt B)". The header has two run buttons, ▶1 "Analyze" and ▶2 "Transfer selected vector dimensions from Prompt B into the generated image". No note box and no references on this surface.
2. Typed "a calm lake" and "a stormy lake", pressed Analyze. The ranking appeared and the picture for A; the picture for B arrived later while I was elsewhere.
3. The ranking: "The 4096 dimensions from Prompt B with the largest difference to Prompt A", one row per dimension with a checkbox, a rank, a name, a bar and a value: 1 d1478 1.182; 2 d806 0.667; 3 d1828 0.643; 4 d1544 0.465; 5 d1567 0.453; 6 d1619 0.427; 7 d1092 0.426; 8 d1164 0.424; 9 d1742 0.422; 10 d1760 0.421; 11 d1266 0.421; 12 d892 0.414 … The bars are proportional (100 %, 56 %, 54 %, 39 % …). The default selection after the analysis read "1144 dimensions from Prompt B selected (rank 13–1156 of 4096)".
4. Set the range to 1–10 ("10 dimensions from Prompt B selected (rank 1–10 of 4096)", the first ten checkboxes ticked), pressed ▶2; the modified picture arrived.
5. Set the range to 1–100, pressed ▶2; done. RUNS showed 4.

Runs: 1 analysis (two pictures), 2 transfers (one picture each).

## 2. What the controls did

- Prompt A / B, Example prompts, the five field buttons: as elsewhere.
- Encoder chips: which encoder's embedding is compared; I used "All (recommended)", which ranked "of 4096".
- ▶1 Analyze: generates A and B with the same seed and ranks the dimensions of B's embedding by their difference to A's.
- Range slider, from/to fields, +, All, None, Descending: choose a rank range; the checkboxes in the list follow; the line above the list states the count and the range.
- ▶2: regenerates A with the selected dimensions replaced by B's values, same seed, into the middle column.
- Advanced settings as on the other diffusion surfaces. RUNS strip counts every picture.

## 3. What came out

- A, "a calm lake": a flat turquoise lake to the horizon, hazy blue hills, a thin cloud, clear sky.
- B, "a stormy lake": dark storm clouds with rain streaks hanging over a green lake, wooded shores left and right.
- Modified, ranks 1–10: indistinguishable from A to my eye.
- Modified, ranks 1–100: still a calm lake under a clear sky, but a different picture: hills on both sides, wooded shores left and right, stronger haze. The composition moved towards B's, the weather did not.
- Ten of 4096 dimensions carried nothing visible; a hundred carried the shores and hills but not the storm. The word "stormy" is not in the first hundred ranked dimensions of this embedding.
- The number 4096 under "All (recommended)" equals T5-XXL's width; CLIP-L has 768 and CLIP-G 1280. Nothing on the surface says how "All" is counted.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- Two run buttons, numbered, with the second one explained only in the empty middle column.
- After the analysis the selection defaults to ranks 13–1156; nothing says why these numbers.
- "d1478", "1.182": the names and values have no legend.
- A arrives first and B later with no status; the right column stays empty without a word.
- Transferring the top ten changes nothing visible; the surface does not say that small ranges rarely show.
- "rank – of 0" and "The 0 dimensions …" before the analysis read like an error.

## 6. What the help text should tell a user

The page has no Help text of its own. It should first say what there is to experience here, and that it is not what the surface's wording promises. The list is called "The 4096 dimensions from Prompt B with the largest difference to Prompt A", and the second button "Transfer selected vector dimensions from Prompt B into the generated image"; both read as if a word sat in some of these numbers and could be carried over. The Latent Lab's own description in the Help says what the lab is for: "to explore the in-between spaces of an AI that are never shown", "to understand that it is made, and to open the black box a little". Here the box opens and stays dark: every one of the 4096 numbers is on the table, with its rank and its bar, and none of them is a trait. The help should say so: a dimension is not "colour" or "weather"; ten of them carried nothing visible, a hundred moved the shores and the haze and left the storm where it was; the word is spread over the whole table in a way that has no name in our language. It should say that working through the ranges and failing to find the word is the use of the instrument, and that the protocol of the attempts is what is taken away. Then the mechanics: two prompts that differ in one point; Analyze generates both with the same seed and ranks the dimensions by the size of their difference; a range of ranks and the second button generate A again with those dimensions from B; the encoder chips choose whose table is compared; the count depends on the encoder.

## 7. Use possibilities, action-oriented

- Learn how Dimensions are everything but human-understandable, identifiable traits of things, experience how a non-human intelligence work deeply opaquely.
- Set out to find the storm: a one-word pair ("calm" / "stormy"), then 10, 100, 1000 ranks, then the top three alone, then the smallest with "Descending", then each encoder on its own; write down after every attempt what changed and what did not. The storm does not arrive; the shores do.
- Try to name a dimension: take the first-ranked one, transfer it alone, and say what it did; then test the name with a second pair. The name does not hold.
- Keep the series of modified pictures from one pair as a sequence: A, ten ranks, a hundred, a thousand, B. Read it as a drift towards B that never passes through the word.
- Compare the three example pairs, colour, drawing style, time of day, and say which of them the table gives up first and which it holds longest.
- Run one pair with CLIP-L, CLIP-G and T5 separately: three tables, three orders, none of them readable.

## 8. Teaching scenarios

The instrument is defined by working through and failing. Two prompts that differ in one word go in, 4096 numbers come out with their differences ranked, and the task that suggests itself, find the numbers that hold the word, cannot be done. What there is to experience is that a model's order is not made of traits a person can name, and that it works all the same. The failure is the finding, and it is productive: the protocol of attempts, the series of pictures that drift without arriving, and the sentences the class writes afterwards.

**S1 — Where is the storm?** (formal, art, mathematics or computer science, grades 9–12, 90 min). Pairs choose a one-word pair and set out to find the word's dimensions. They work through: the ten largest, the hundred largest, a thousand, the first one alone, the smallest ones with "Descending", one encoder at a time; after every attempt one line in a protocol: what changed in the middle picture, what did not. The plenary collects the protocols: nobody found the word; what moved were shores, hills, haze, a horizon, things nobody asked for; and the picture did move towards B. Closing sentence per pair on what a dimension is, and is not. Sequence: 10 min pair; 10 min analysis; 40 min attempts and protocol; 20 min plenary; 10 min sentences. Subject link: vector, dimension, representation; the limit of naming. Uncertainty: ten ranks changed nothing visible and a hundred moved the composition and not the weather; a thousand and the encoder chips were not run.

**S2 — A name for d1478** (formal, language teaching or philosophy, grades 11–13, 90 min). The class tries to do with the model's dimensions what we do with traits: name them. Groups take the three highest-ranked dimensions of one pair, transfer each alone and in twos, and write a label for each as one would for a trait ("weather", "colour", "mood"). Every label is then tested on a second pair: does the same dimension do the same there? The labels fall; the discussion is about why: our words cut the world into things with traits, the model's table cuts it into 4096 numbers that each hold a little of everything, and the two cuts do not meet. Sequence: 15 min analysis of two pairs; 30 min transfers and labels; 20 min tests; 25 min discussion. Subject link: category, trait, concept; what a word is to us and what it is to the model. Uncertainty: not run; whether a single dimension changes anything visible is doubtful (ten together did not), which is the point of the exercise and is said beforehand.

**S3 — The series of attempts** (non-formal, art workshop, age 15+, 3 h). Participants work on one pair of their own and keep every modified picture: a series from A over 10, 100, 1000 ranks to B, and the protocol beside it. The series is hung as a work: a drift from one picture to another that never passes through the word that separates the two prompts. The round at the end asks what the series shows about the model, and what the protocol of failing shows about the one who tried. One picture of the series is carried on in Flow (favourite, then a perspective or a sound). Sequence: 20 min prompts and analysis; 70 min attempts; 40 min hanging and protocol; 30 min round; 20 min continuation. Subject link: the series as a form of work; failure as material; artistic research. Uncertainty: I did not try the favourite path from this surface.

**S4 — Encoder by encoder** (non-formal, maker space, age 15+, 2 h). Participants run one pair with each encoder chip, compare the three rankings (which dimension names come first, how long the lists are: 768, 1280, 4096) and the modified pictures at the same range, and write what the three tables have in common: nothing a person can read. Subject link: text encoders of a diffusion model; three orders of the same sentence.

## 9. AI-Lit mapping (built from S1–S4)

**(a) 100 % hits**

- Engage 2 Basic — "Learners know AI is a non-human tool that produces outputs based on patterns of data and lacks authentic context or understanding." S1 and S2: the sentences "the model knows what stormy means" and "the storm sits somewhere in the model" are held against the protocol and rewritten; the framework's classroom example has learners identify misleading phrases and develop accurate descriptions, and the accurate description here is that the word is a difference spread over 4096 numbers that carry no trait.
- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S1: the protocol and the closing sentences describe what the second button does, a transfer of ranked numbers between two tables at one seed, against the idea that a word is stored somewhere in the model and can be moved.
- Engage 2 Advanced — "Learners explain how different AI systems work using language that does not attribute human traits or abilities, knowing that their phrasing shapes understanding." S4: three encoders, three tables of different length and order, explained from what each did to the picture at the same range, in sentences without seeing or knowing; the framework's classroom example has learners explain how different systems produce outputs as programmed processes.
- Shape 2 Basic — "Learners define criteria for whether an AI system has accomplished a task." S1: what counts as "the word shows" is defined by each pair before the attempts and applied to every range; the framework's classroom example has learners define what would make the system successful before judging it.

**(b) Mutatis mutandis**

--

**Beyond the framework**: the framework's expectations assume that how an AI system works can be described, and its Engage 2 examples have learners describe it. Here the description is attempted and fails at the level of the dimension, on purpose, with the whole table on screen; what remains is the experience of a way of working that functions and has no names in it, and the protocol of having tried. The Latent Lab's own purpose in the Help names it: "to explore the in-between spaces of an AI that are never shown", "to open the black box a little". The framework has no competence for the experience of opacity and none for failure as a form of knowledge; this instrument is built on both.

**Non-fits**: Engage 1, 3, 4, 5, 6, 7, Manage 1–4, Shape 1, 3, 4, Create 1–4.
