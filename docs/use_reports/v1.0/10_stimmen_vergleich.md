# 10 Voice Comparison — `/latent-lab/voices`

Used 2026-11-02, 21:31–21:50 CET, UI language English, not signed in. Method note: I operated the surface in a headless browser on the server, which has no audio output; every clip was played (the players' time advanced), but I could not listen. What I report about the voices is what the surface shows: Hz figures, durations, captions and times.

## 1. What I did

1. Opened `/latent-lab/voices` (sidebar "Voice Comparison"). Preparing column: a drop-down of test sentences, a prompt field with the five small buttons (Copy, Paste, Choose Perspective, Translate to English, Delete), and a note under it, "Four text-to-speech systems compared, with an eye to how they stage emotion and gender", with one numbered paragraph per system ("1) eSpeak NG 1.51.1 (1995): the computer voice from before AI. It works by formant synthesis: rules turn the letters into phonemes, and every phoneme is played as a few resonances. Cf. "speak", Jonathan Duddington, 1995. 2) Piper 1.6.0 (2022): parallel (VITS, 2021: the model forms each sentence …" and so on; I read the first two). Right: four columns, "eSpeak NG 1995", "Piper 2022", "Supertonic 2026", "VoxCPM2 2026", each with its own "Generate audio" button and a Hz figure in its head. There is no button that runs all four at once. The Help panel opens by itself on the first arrival with the page's text: "The test sentence is picked from the drop-down or written in the field; the drop-down holds everyday sentences with and without an emotional colouring, and fairy tales. Four text-to-speech systems speak it, each with settings and a start button of its own: a formant synthesis from 1995 in twelve variants; voice files, each trained on a recording, of which one is picked; ten trained voices that can be picked singly and mixed; and a model whose speaker three rows describe — gender, age, expression. Every system keeps what it spoke." "A voice stages gender and feeling; the four systems do it with completely different means. In the machine from 1995 there is a recording of nobody; there it is twelve settings of a computing rule, and it still often sounds like somebody. In the second, one file per voice speaks, each trained on a recording, and under the chosen file stands who was recorded, where the dataset says so. In the third system each of the ten voices carries its pitch in hertz beside it: compare the ones marked F and the ones marked M. The fourth takes in a description from three rows instead of a list — gender, age, expression —; compare the setting with what there is to hear." I overlooked it on first use.
2. Picked the sentence "That is the most moving film I have seen in a long time." from the drop-down. Pressed the four Generate buttons one after the other.
   - eSpeak NG: chips f1–f5 and m1–m7 under "Voice/Speaker model", "Selected model: en, eSpeak NG 1.51.1, 22050 Hz". Clip: caption "en-us", 101 Hz, 3.11 s.
   - Piper: language chips AR, BG, DE, EN, ES, FR, HE, KO, TR, UK; with EN the voice "en_GB-cori-high". Clip: 208 Hz, 3.41 s.
   - Supertonic: "Choose several voices; the platform mixes them in equal shares." Ten voice cards with a description and a nominal pitch (F1 194 Hz "calm, a little lower, composed"; F2 197 Hz "bright, lively, youthful"; F3 163 Hz "clear, like an announcer"; F4 194 Hz "clipped, decided, expressive"; F5 164 Hz "friendly, gentle, soothing"; M1 135 Hz "lively, alert, clear"; M2 97 Hz "low, calm, serious"; M3 107 Hz "polished, assured"; two more, "soft, neutrally…" and "warm, quiet…", cut off at the bottom of the column). F3 was preselected. Clip: caption "F3 100", 165 Hz, 4.04 s.
   - VoxCPM2: three chip rows "Gender" (female, male, neutral), "Age" (a child, young, middle-aged, old), "Expression" (neutral, angry, happy, sad, anxious, bored, disgusted, calm, friendly, gentle, decided, narrating), none selected. Clip: 207 Hz, 3.04 s.
3. Changed the speaker in Piper: language chip DE, voice "mls" (a second voice "pavoque" is offered). A "Speaker" select appeared with 236 entries, default "2422 (0) · male · 601 h", captioned "236 LibriVox volunteers (Multilingual LibriSpeech)". Generate audio: new clip "de_DE-mls-medium / 2422", 159 Hz, 5.84 s. The caption under the clip still shows the English sentence; whether the German voice read it with German phonemes I could not hear.
4. Changed the description in VoxCPM2: chips male, old, sad. Generate audio; the clip came. Caption "a male voice, an old voice, a sad voice", 137 Hz, 3.84 s.

Runs: 6 clips (4 systems, Piper and VoxCPM2 twice).

## 2. What the controls did

- Sentence drop-down: fills the prompt field; the field can be edited.
- Per-system Generate audio: synthesises the sentence in that column only; the Hz figure in the column head changes to the measured pitch of the newest clip (Supertonic's card says F3 163 Hz, the clip measured 165 Hz).
- eSpeak chips f1–f5 / m1–m7: voice variants of the rule-based synthesiser; not changed here.
- Piper: language chips change the voice list; "mls" adds the 236-speaker select; the new clip is placed above the old one, so the column keeps the history.
- Supertonic: voice cards are multi-select and mixed in equal shares (as the caption says); not changed here.
- VoxCPM2: the chips write a description ("a male voice, an old voice, a sad voice") that is shown as the clip's caption; without chips the caption is empty and the log marks the run "described=False".
- Each clip: a standard audio player (play, position, volume, menu).
- Help: opens by itself on the first arrival with the page's text quoted in 1; every later click shows that text again.

## 3. What came out

- Four pitches for one sentence: eSpeak 101 Hz, Piper en_GB-cori 208 Hz, Supertonic F3 165 Hz, VoxCPM2 default 207 Hz. The two 2026 systems and Piper's English voice landed near 200 Hz, i.e. in a female range, without anyone choosing a gender; eSpeak's default "en" is the lowest.
- Piper DE/mls, speaker 2422 (male, 601 hours of recordings): 159 Hz and 5.84 s for the same sentence, 70 % longer than the English voice.
- VoxCPM2 "male, old, sad": 137 Hz, 3.84 s; the default clip 207 Hz, 3.04 s. The description lowered the pitch by 70 Hz and lengthened the clip; the "sad" I could not hear.
- The Piper speaker list is the only place on the surface where the people behind a voice are visible: 236 LibriVox volunteers with a speaker number, a gender and hours of recording.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- Four separate Generate buttons, as the Help text says ("each with settings and a start button of its own"); a user who has not read it expects the others to follow.
- While a column computes it shows no status.
- The Hz in the column head is the measured pitch of the last clip, but nothing says so; next to the Supertonic cards' nominal Hz the two read as the same kind of number.
- "mls" and "pavoque" are voice names without explanation; the Help text says that one voice file is picked and that who was recorded stands under it, which is the speaker list; the 236-entry select opens on a speaker number.
- The note's four paragraphs are cut off in the narrow preparing column and have to be scrolled.
- The VoxCPM2 description chips are three rows of single words; the Help text says the three rows describe the speaker, and the surface shows the combined description only in the caption after generating.

## 6. What the help text should tell a user

The Help panel's own text, which opens on arrival, is quoted in 1: it says where the sentence comes from, that four systems speak it, each with settings and a start button of its own, what each system is (a formant synthesis from 1995 in twelve variants; voice files trained on recordings; ten trained voices to pick and mix; a model described by three rows), that every system keeps what it spoke, and what to compare. It should add: the number in the column head is the pitch measured on the newest clip, a different kind of number from the nominal hertz on the Supertonic cards; Piper's "mls" voices are 236 LibriVox volunteers, chosen in the speaker list; while a column computes it shows no status.

## 7. Use possibilities, action-oriented

- Synthesise one sentence in all four systems and write down the four Hz figures before listening; then listen and sort the voices by era.
- In VoxCPM2 run the same sentence as "female, young, happy" and "male, old, sad" and compare pitch and duration with what the chips promised.
- In Piper DE/mls pick five speakers by number and compare; read the hours column as what the voice is made of.
- Use an emotional sentence from the drop-down and one neutral sentence of your own, in Supertonic with F3 and M2, and note where the "emotion" sits: in the sentence or in the voice.

## 8. Teaching scenarios

**S1 — Four machines, one sentence** (formal, music or language teaching, grades 7–10, 45 min). The class chooses one sentence; four groups each take one system, generate, note the Hz figure and describe the voice in three adjectives; then the clips are played in the order 1995 → 2022 → 2026 → 2026 and the adjectives compared. Sequence: 5 min sentence; 10 min generating; 15 min adjectives; 15 min listening and comparing. Subject link: voice, pitch, technology history.

**S2 — How a model stages gender and age** (formal, ethics or media, grades 9–12, 90 min). Pairs run VoxCPM2 with the gender × age chips (six combinations), record Hz and duration in a table, listen, and discuss which cues the model uses for "old" or "female" and where these are clichés. Then they compare with Piper mls, where the gender column names real speakers. Subject link: stereotypes, representation of voice.

**S3 — Whose voice is this?** (non-formal, library or media workshop, 2 h, age 13+). Participants open the Piper speaker list, pick a volunteer by number, listen, and look up LibriVox to find what that volunteer read; discussion of consent and licensing of voices that end up in a model. Subject link: data, authorship, the commons. Uncertainty: the speaker numbers are Multilingual LibriSpeech IDs and may not resolve to a LibriVox page without help.

## 9. AI-Lit mapping (built from S1–S3)

**(a) 100 % hits**

- Shape 3 Basic — "Learners identify examples of data that might be used to train AI systems." S3: the 236 LibriVox volunteers with hours of recording are named on the surface as what the mls voices are made of.
- Engage 6 Intermediate — "Learners explain how biased data or design choices (e.g. stereotyped content, misclassification, unequal recommendations) can lead AI systems to generate unfair or skewed outcomes for certain groups." S2: the cues the model uses for “old”, “female”, “sad” as stereotyped content about those groups.
- Shape 2 Intermediate — "Learners assess an AI system performance of a task using defined criteria and feedback from human reviews or benchmark tests." S1 and S2: the adjective and Hz tables as the defined criteria, the listening round as the human review.
- Create 4 Basic — "Learners know that AI-generated content may reuse or copy work protected by intellectual property or copyright laws and recognise implications for the humans who created the original work." S3: the volunteers whose recordings are in the model, and the discussion of consent and licensing of voices that end up in a model.
- Manage 2 Basic — "Learners recognise that some types of AI systems can be programmed with specific rules to accomplish tasks, while others can learn patterns from data." S1: the note's paragraphs on the four systems: the one from 1995 computes the sounds from rules (formant synthesis), the three others were trained on recordings; the clips are played in that order.

**(b) Mutatis mutandis**


**Beyond the framework**: the framework's Manage 2 example compares calculators and traffic lights with trained systems; S1 compares a rule-based voice from 1995 with trained voices from 2022 and 2026 on the same sentence, and S3 opens the list of the people whose recordings one of them was trained on.

**Non-fits**: Engage 1, 2, 3, 4, 5, 7, Manage 1, 3, 4, Shape 1, 4, Create 1, 2, 3.
