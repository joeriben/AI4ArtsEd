# 28 Latent Audio Synth — `/latent-lab/audio-synth`

Used 2026-11-03, 00:25–00:55 and 10:15–10:20 CET, UI language English, not signed in. Headless browser on the server: I could not hear the sounds; I report what the surface showed and what the server did.

## 1. What I did

1. Opened `/latent-lab/audio-synth` (tooltip "T5 embedding manipulation"). Preparing column: "Example prompts" (ocean waves, piano melody); "Prompt A (Base)" prefilled "a steady clean saw wave, c3"; "Prompt B (Optional, for interpolation)" prefilled "glass breaking"; a slider "A (Interpolation between Prompt A embedding (= -1.0) and Prompt B embedding (= 1.0))" at −0.17; "Magnitude (Scaling)" 1.00 (0.1–5); "Noise" 0.00 (0–1); Advanced settings (steps 8, 1–100; CFG 1, 1–15; seed 123456789; "Random variation"); a fold "Semantic Axes" with three axis selects (entries like "sound noisy ↔ sound tonal (d=4.806)", "electronic music ↔ acoustic music (d=2.013)", "noise ↔ music (d=2.058)"; defaults acoustic/electronic, music/noise, vocal/instrumental, each with a 0–1 slider at 0.5); a fold "Dimension Explorer" (Relative / Absolute, a strip of fine vertical bars "Sorted by prompt difference", the hint "Drag on bars = set offset. Paint horizontally = multiple dimensions.", buttons Apply and regenerate, Undo, Redo, Reset all). Right: "Looper / Sequencer" (Stopped, Test C3, Looper / Wavetable, One-shot / Loop / Ping-pong, Crossfade 150 ms, Normalize loudness, ENV 1–3, LFO 1–2, DRIFT 1–3, Auto-Regen, Filter / Delay / Reverb, a piano keyboard C…B with HOLD, Sequencer / Arpeggiator, Record, Save raw, Save loop, Export / Import preset, MIDI Control). The run button is the play triangle ("Generate"). No note, no references on this surface.
2. Replaced Prompt A with "rain on a tent", left Prompt B and all sliders at their defaults (α −0.17, magnitude 1, noise 0, steps 8, CFG 1). Generate. Done (the header named "stable-audio-3-medium · local"): the Looper showed a 12.00 s waveform under "Loop interval 0.000s – 12.000s", "Wavetable 561", "Normalize loudness · Peak: 0.999", "Test C3" enabled, RUNS 1.
3. (I left the page by accident, so I generated the same prompt again; RUNS 2, same display.)
4. Opened the "Dimension Explorer" fold. The strip: hundreds of fine green bars with orange tips on a baseline, sorted by how much prompt A and B differ in that dimension. Dragged upward on two bars (at a fifth and at a little over half of the strip's width). The fold reported "2 offsets active", Undo became active, and "Apply and regenerate" became enabled (it is disabled while no offset is set). Pressed it; done (RUNS 3), the Looper again 12.00 s, Wavetable 561, Peak 0.999.

Runs: 3 sounds of 12 s.

## 2. What the controls did

- Prompt A / B: two texts whose T5 embeddings are mixed by the α slider (−1 = A alone, +1 = B alone; −0.17 is almost A).
- Magnitude: scales the embedding; Noise: adds noise to it.
- Semantic Axes: three directions found between word pairs, each with a weight; not used beyond opening.
- Dimension Explorer: the strip is the embedding's dimensions, sorted by the A–B difference; a drag sets an offset on a dimension; Apply and regenerate runs the model with the offsets; Undo/Redo/Reset all manage them.
- Generate: one 12-second sound with the current embedding; the result goes into the Looper.
- Looper / Sequencer: plays, loops, envelopes, filters and sequences the sound on the piano keys; "Test C3" plays it at C3; Save raw / Save loop download; MIDI Control for a keyboard. None of this reached my ears.

## 3. What came out

- Three sounds of 12.00 s from "rain on a tent" (α −0.17 toward "glass breaking", magnitude 1, no noise); the third with two dimension offsets. The surface shows each as a waveform in the Loop interval, with a peak reading of 0.999 after normalisation, and "Wavetable 561" (the number of wavetable cycles, unexplained on the surface). I cannot say what changed between the second and the third sound; the surface gives no spectrogram, no description and no numeric comparison.
- The model named in the header is Stable Audio 3 medium; the T5 embedding is what the sliders and the strip manipulate.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- Prompt B and α are prefilled, so the first sound is already a mixture ("rain" with 17 % toward "glass breaking" on the slider's scale) without the user having chosen it.
- The Dimension Explorer strip has no labels: which dimension is which, what an offset of one bar does, and what "Relative" versus "Absolute" means are not on the surface.
- "Apply and regenerate" is disabled until a drag has registered; a careful click on a bar sets nothing and the button stays grey without a message.
- "Wavetable 561" and "Peak: 0.999" are readouts without a legend.
- The Looper takes two thirds of the page with synthesiser controls (ENV, LFO, DRIFT, MIDI) that presuppose a synthesiser user.
- No note and no reference on this surface, unlike the neighbouring ones.

## 6. What the help text should tell a user

The page has no Help text of its own and no note. It should first say what is done here: a description of a sound is taken apart into the 768 numbers the text encoder makes of it, and the work is on the numbers, not on the words. Two descriptions can be mixed, and the α slider runs past both ends, so beyond A or B the mix exaggerates the direction the two descriptions span; magnitude dampens or overdrives the whole; noise adds chance; the strip of the Dimension Explorer lets single numbers be painted up or down, and the platform's own manual calls it a tool for exploration and chance, not for targeted sound design, because most dimensions change nothing audible and some change everything. The Semantic Axes are each the difference between two short texts in the encoder's space, tonal against noisy, acoustic against electronic, and also sacred against secular, traditional against modern, beautiful against ugly, professional against amateur, authentic against fusion, refined against raw, complex against simple, music against noise; the backend sorts them as perceptual, cultural and critical, the manual calls the feature very experimental, and the platform's own source check of 2026-08-13 found ten of the 22 pairs not to be opposites. The help should say that this makes the axes material: what the model holds "ugly music" or "authentic music" to be is heard by moving the slider. Then the right side: the generated sound is played, looped, pitched on the keys, shaped with envelopes and filters, sequenced and recorded, so the sound becomes an instrument's sound, and a new generation swaps the loop under whatever is playing. The surface's own hints: below about eleven seconds this model produces malformed audio, the steps are distilled for eight, and at CFG 1 the guidance is off and the negative prompt has no effect.

## 7. Use possibilities, action-oriented

- Take a sound apart: "rain on a tent" against "glass breaking", α in steps from A past B; hear where the rain stops being rain and whether the glass ever arrives, and name the in-between sounds.
- Hear what the model holds "beautiful music" and "ugly music" to be: one prompt, that axis at both ends; then sacred against secular, professional against amateur, authentic against fusion, traditional against modern; decide whether what you hear is an opposite at all.
- Paint blind: ten bars shifted in the strip, regenerate, undo one at a time, keep the one accident worth keeping.
- The same description at magnitude 0.3 and at 4: dampened and overdriven.
- Prompt a word that has no sound ("loneliness", "friendship") and hear what the model gives for it.
- Make an instrument of it: loop the sound, set an envelope and a filter, play it on the keys, record a phrase; let a new generation swap the sound under a running sequence.
- Build a wavetable from an axis (the manual's "From Axis" mode) and play the sweep through the semantic space as a sound.

## 8. Teaching scenarios

The instrument is a synthesiser whose oscillator is a text model's reading of a description. What it is good for is taking apart: a sound word into numbers, a mixture into its stages, a value word into what the model makes of it; and listening, which is the judgement that decides what is worth keeping. The axes with value words built into the surface are the sharpest case: beautiful against ugly, authentic against fusion, professional against amateur are not acoustic properties but judgements, and here they are sliders. Hearing what the model does with them, and deciding whether the two ends are opposites, is a lesson in how such pairs are made. The sound that comes out is material: looped, pitched, sequenced, it goes into a piece.

**S1 — Between two sounds** (formal, music, grades 7–10, 90 min). Pairs write two sound words from their surroundings (the yard at break, the hall at night) into A and B, generate at five settings of α from A to B and one beyond each end, and listen to the seven; they give each a name of their own and mark where the in-between is a sound in its own right, worth keeping, and where it is a muddle. The plenary listens to the kept ones and asks what a mixture of two sounds is, and what it is not. Sequence: 10 min words; 25 min seven generations; 30 min listening and naming; 25 min plenary. Subject link: timbre, transition, listening, naming what has no name. Uncertainty: I could not hear the sounds; whether a setting beyond the ends gives a sound or noise is not known to me.

**S2 — Beautiful, ugly, and who says so** (formal, music, art or ethics, grades 9–13, 90 min). One prompt for all ("music played at a celebration"), then the axis beautiful against ugly at both ends; then professional against amateur, authentic against fusion, sacred against secular, traditional against modern. Before each listening the pair writes what "more beautiful" or "more authentic" would have to sound like to count; after it, what the model gave, and whether the two ends are opposites to their ears. The class reads the manual's own words that the feature is very experimental, and hears that the platform's own check found ten of the 22 pairs not to be opposites; it then asks who decided that authentic is the opposite of fusion and refined the opposite of raw, and what music falls on which side in whose ears. The phrases "the model knows what ugly music is" and "the slider makes it more beautiful" are rewritten as what the axis is: the difference between two short texts in the encoder's space, added to the description. Sequence: 10 min prompt and criteria; 35 min axes; 25 min reading and rewriting; 20 min plenary. Subject link: value judgement in music, the binary as a construction, cultural hierarchy in words about music. Uncertainty: I opened the axes and did not move them.

**S3 — The accident** (non-formal, music or art workshop, age 13+, 3 h). Participants generate one sound, then paint blind in the strip, regenerate, undo, and keep every accident worth keeping; from the kept accidents each builds a short piece in the Looper and sequencer. The round asks what was found and what was made, and the facilitator sets the method beside chance as a method in twentieth-century music and art, where the accident is let in on purpose and the choice is the work. Sequence: 20 min first sounds; 60 min accidents; 60 min pieces; 40 min round. Subject link: chance as method; the choice as the artistic act; sampling. Uncertainty: the Looper's controls presuppose synthesiser knowledge; a facilitator who has it is needed.

**S4 — The sound as instrument** (non-formal, music workshop, age 13+, 3 h). Participants generate sounds from words, loop them, set envelopes and filters, play them on the keys with a MIDI keyboard, let the sequencer run and swap the sound under it with a new generation; the session ends in a piece from generated sounds and in the question what the words did in it. Subject link: sampling, synthesis, the loop. Uncertainty: not tried with a keyboard.

**S5 — Words without a sound** (formal, music or language teaching, grades 10–13, 45 min). Pairs prompt words that name no sound ("loneliness", "friendship", "Tuesday") and words that name one ("a door closing"), listen, and write what the model gave for each and where it got it; the manual's sentence that good prompts describe sound properties and the model knows no pieces is read afterwards. Subject link: word and sound, the referent, description.

## 9. AI-Lit mapping (built from S1–S5)

**(a) 100 % hits**

- Create 2 Intermediate — "Learners experiment with AI tools (e.g., text, image or music generators) to develop diverse ideas and produce varied outputs." S1, S3 and S4: two sound words at seven settings, accidents from the strip, generated sounds in a piece; the framework's classroom example has learners experiment with generators to produce varied outputs and compare how prompts and tools interpret the same idea.
- Create 1 Basic — "Learners explore how different AI tools can expand their thinking or spark new ideas." S3: the accidents kept from the strip become the material of a piece, as the framework's classroom example has learners make new work inspired by unexpected results.
- Engage 2 Basic — "Learners know AI is a non-human tool that produces outputs based on patterns of data and lacks authentic context or understanding." S2: "the model knows what ugly music is" and "the slider makes it more beautiful" are judged misleading and rewritten as what the axis does; the framework's classroom example has learners identify misleading phrases and develop better descriptions.
- Engage 2 Advanced — "Learners explain how different AI systems work using language that does not attribute human traits or abilities, knowing that their phrasing shapes understanding." S2: the axis labels are read as a design choice that makes the system appear to judge beauty and authenticity, and the pairs explain what the slider does as a process in the encoder's space; the framework's classroom example has learners compare design choices that make systems appear intelligent and explain outputs as programmed processes.
- Shape 2 Basic — "Learners define criteria for whether an AI system has accomplished a task." S2: before each listening the pair writes what would have to be heard for the axis to have done what its label says, and judges the result against it; the framework's classroom example has learners define criteria for success before comparing the system's outputs.

**(b) Mutatis mutandis**

--

**Beyond the framework**: the framework's Create examples have learners generate and compare; here the instrument's own categories are taken apart. The value words on its sliders, beautiful and ugly, authentic and fusion, are judgements made into controls, and the lesson hears what the model does with them and asks who made the pair (S2). The accident is let in and the choice is the work (S3); the sound becomes an instrument's sound (S4). The framework has no competence for listening, none for the aesthetic judgement that decides what is worth keeping, and none for taking a tool's own categories apart.

**Non-fits**: Engage 1, 3, 4, 5, 6, 7, Manage 1–4, Shape 1, 3, 4, Create 3, 4.
