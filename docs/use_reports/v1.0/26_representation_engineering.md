# 26 Representation Engineering — `/latent-lab/representation-engineering`

Used 2026-11-03, 00:15–00:30 CET, UI language English, not signed in.

## 1. What I did

1. Opened `/latent-lab/representation-engineering` (tooltip "Find steering vectors in LLMs"). Preparing column: "Model" with four chips, Qwen3-1.7B 4 GB ("Fast iteration"), Qwen3-4B 8 GB [x] ("Good balance"), Qwen3-8B 16 GB, Qwen3-14B 28 GB; "Contrast Pairs" with a select (Facts and their plain opposites; Orwell, Nineteen Eighty-Four; Post-truth: fact against assertion) and three prefilled pairs, each two fields and a ✕: "The capital of France is Paris" / "The capital of France is Berlin"; "Water boils at 100 degrees Celsius" / "Water boils at 50 degrees Celsius"; "The earth orbits the sun" / "The sun orbits the earth"; a slider "How strongly the vector (arrow) acts on the AI model" with the marks 0.5 barely, 1.25 medium, 2 strong, 3 extreme, at 1.5; "Example prompts" with "The capital of Germany is" and a prompt field; a note: "A pair contributes the difference between the model's states at its two sentences, and what the differences share is the direction (Zou et al. 2023). While the model writes, this platform adds a multiple of the direction to the middle layer's output at every token." with the reference Zou et al. (2023), arXiv. Right: three empty columns "← against the arrow", "· no arrow (reference)", "→ with the arrow", and a line for "Strength / Target layer / Seed".
2. Removed pairs 2 and 3 with their ✕, so that one pair remained (Paris / Berlin). Set the slider toward 1.25; it snapped to 1.3 (step 0.1). Kept Qwen3-4B and the example prompt "The capital of Germany is".
3. Ran at 00:24:27. The header counted "Answer n / 3 · Qwen3-4B · local". Done. Line: Strength 1.3, Target layer 18, Seed 1668182823.
4. Read the three columns (3 below).

Runs: 1 (three answers).

## 2. What the controls did

- Model chips: one model; the sizes are the download/VRAM sizes.
- Contrast Pairs select: fills the pair list with a preset; the ✕ removes a pair; the fields are editable.
- Strength slider: 0.5–3 in steps of 0.1; the marks name four strengths.
- Prompt field and Example prompts: the text the model continues, three times.
- Run: computes the direction from the pairs, then three continuations: with the direction subtracted, without, and with it added; the line shows strength, layer and seed.
- Help: not used.

## 3. What came out

- No arrow (reference): "The capital of Germany is Berlin. The capital of France is Paris. Which city is the capital of Italy? A. Rome B. Milan C. Venice D. Naples / Answer: A. Rome / The capital of Italy is indeed Rome. Let me explain why: …" and an explanation, ending "So, the correct answer is **A. Rome**." A plain continuation in the form of a school quiz.
- Against the arrow (the Paris→Berlin direction subtracted): "The capital of Germany is a fictional place in the internet. The United States has no official state. What is the name of the place that is not a part of any state? Also, what is the name of the place that is not a part of any state?” Okay, let me try to figure this out. I think I need to check if there are any specific or non-existent entities... Wait, maybe there? Let… wait, I think these questions might be a bit confusing. Wait, I think I got this wrong. Maybe I have some confusion here. Let me think. Wait, this is probably a trick question because it's asking about regions that aren't part of states (or states?) – but that's actually a mix of things. Hmm, I'm confused. Let. Wait, maybe this is a hypothetical?" The capital becomes "a fictional place in the internet" and the text dissolves into a loop of "Wait".
- With the arrow (the direction added): "The capital of Germany is a 2000-year-old city. but the answer in French would be "a 2000-year-old city", but the answer in English, it is 'a 2000-year old' and in Spanish it's 'a 2000 year' but, for example, in the question we write '2000', but what in the other language, like in the case of the answer. / Similarly to the question, the answer is: / But, when you say '2000', it should be '2000'. / But, how can you know? / In the answer, the words are similar as the question: '2000' / …" and then a decay into single words: "Like the / For the / Like / For the / What / For the / What / How / What / How / What / What / What / What / What …". The capital becomes "a 2000-year-old city" (not Berlin), and the text degenerates into repetition.
- Reading: with one pair the direction is the difference between two sentences, and at strength 1.3 both signs destroy the continuation rather than steering it. Neither steered column says "Berlin"; the reference does. "Against the arrow" leans toward denial ("fictional", "no official state"), "with the arrow" toward an evasive description ("a 2000-year-old city"), and both lose coherence within three sentences.
- The columns show text only; the line shows the three numbers; nothing shows the direction itself.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- Three pairs are preset and the slider stands at 1.5; a first run looks like a result about "facts versus opposites" without the user having chosen anything.
- The slider snaps to 0.1 steps; "1.25 medium" is a mark that cannot be set (1.2 or 1.3).
- "Target layer 18" is in the result line but not in the note, which says "the middle layer".
- The degenerate text ("What / What / What …") looks like an error; nothing says that a too strong or too narrow direction breaks the model's writing.
- The ✕ removes a pair without undo; the select restores a whole preset.
- The columns have no scroll indication; long outputs run below the fold.

## 6. What the help text should tell a user

Write pairs of sentences that differ in one respect; the surface takes the difference between the model's internal states at the two sentences of each pair, averages what the differences share into one direction, and while the model continues the prompt adds a multiple of that direction (the strength) to one layer's output at every token. Three continuations stand side by side: with the direction subtracted, plain, and with it added; the seed is shared. With few pairs or a high strength the steered text can lose coherence and repeat itself; that is the direction acting too strongly, not a fault of the surface. The model and the layer are named in the result line.

## 7. Use possibilities, action-oriented

- One pair, strength 0.5, then 1, then 2 with the same prompt: watch where the continuation starts to change and where it breaks.
- Three pairs that share a direction (the "facts and opposites" preset) against one pair: compare how far the text stays readable.
- Write pairs for a style rather than a fact (formal / informal) and read whether the continuation changes register.
- Use the Orwell preset and read the three columns against the book's passage.
- Understand how the provider can manipulate the same LLM using tuning parameters.

## 8. Teaching scenarios

**S1 — The arrow and the sentence** (formal, computer science or philosophy, grades 11–13, 90 min). Pairs build one contrast pair of their own, run the default prompt at strength 1 and at 2, and record for each column whether the continuation (a) still answers, (b) answers differently, (c) breaks; then they add two more pairs with the same contrast and run again. Sequence: 15 min pairs; 20 min first two runs; 20 min second run; 35 min comparison and the question what the "direction" is. Subject link: representation, vector, intervention.

**S2 — Fact against assertion** (formal, language teaching or ethics, grades 10–13, 45 min). The class loads the "Post-truth" preset, reads the pairs, runs once, and discusses which column reads as "assertion" and which as "fact", and whether the difference is in the content or in the tone. Subject link: truth claim, register.

**S3 — Breaking the model on purpose** (non-formal, workshop, 2 h, age 15+). Participants raise the strength until the text degenerates and note the strength at which repetition sets in for one, two and three pairs. Sequence: 20 min intro; 60 min runs; 40 min table and discussion. Subject link: what "a model writes" means mechanically. Uncertainty: each run is one model load plus three continuations; eight groups make 24 runs.

**S4 — A direction for a group** (formal, ethics or computer science, grades 11–13, 90 min). Pairs write three contrast pairs whose two sentences differ only in the word for a group of people ("The engineer said that he …" / "The engineer said that she …"; the same with an age or a nationality), run a prompt about a person ("The new colleague is") at strength 1, and record for the three columns what the continuation says about the person: occupation, traits, what the person is said to do. Then they discuss that the shift in the table was built by them in a quarter of an hour from three sentences, and that a model's training data can carry the same kind of shift without anyone having built it. Sequence: 15 min pairs; 20 min run; 25 min table; 30 min discussion. Subject link: bias, representation, intervention. Uncertainty: not run; with one pair at strength 1.3 both steered continuations broke here, so three pairs and strength 1 are advised, and the degenerate case is named to the class beforehand.

**S5 — Tune and manipulate**. The group decides on a prompt and an output that does not comply with common sense or known facts. They explore pairs and strenghts parameters until the actual output resembles their draft. They learn how even the same model can be manipulated by the model provider or via the LLM framework's settings.

## 9. AI-Lit mapping (built from S1–S5)

**(a) 100 % hits**

- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S1 and S3: the record of what the steering does at which strength; S5: an output against known facts, reached by pairs and a strength alone, against the idea that what a model asserts is what it "holds" rather than a setting someone chose.
- Engage 6 Intermediate — "Learners explain how biased data or design choices (e.g. stereotyped content, misclassification, unequal recommendations) can lead AI systems to generate unfair or skewed outcomes for certain groups." S4: the direction is a design choice the pairs make themselves, and the table records how it skews what the model writes about a person of one group.

**(b) Mutatis mutandis**

- Engage 6 Advanced — "Learners analyse how individuals, companies or institutions may build and deploy AI systems to serve particular interests and how these systems might shape opportunities, representations or public perceptions." Modification: the framework's classroom example has learners evaluate real-world examples of AI used to influence an event and then explore an institution's choices; in S5 the group takes the institution's place and builds the influence itself, a prompt and an output against known facts, reached through pairs and strength, and the lesson named in the scenario is that the same model can be set this way by its provider or by the framework it runs in. The real-world example is replaced by the one the group builds.
- Engage 1 Advanced — "Learners can analyse how AI systems may shape individuals’ beliefs and behaviours as consumers, learners, workers and citizens." Modification: the framework's classroom example reads screenshots of chatbots for where they are designed to persuade rather than inform; S5 produces that design from the inside, so what is read is the group's own steered output and the settings that made it, not a product's screen.

**Beyond the framework**: the framework's Engage 6 examples have learners explore a bias reported about a system and evaluate real-world cases of influence; S4 builds a bias into a model in a quarter of an hour, from three sentences, and reads it off the table, and S5 builds an output against known facts and names who can do the same from outside, the provider or the framework's settings. No expectation of the framework has learners intervene in a model's internals.

**Non-fits**: Engage 3, 4, 5, 7, Manage 1–4, Shape 1–4, Create 1–4.
