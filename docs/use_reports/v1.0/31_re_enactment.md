# 31 Re-enactment — `/latent-lab/re-enactment`

Used 2026-11-03, 10:21–11:10 CET, UI language English, not signed in. The browser ran headless on the server and has no microphone; I fed it a ten-second hum I synthesised (five sung notes G3–A3–B3–A3–G3 with vibrato, no words) as a fake microphone, so the "recording" is a machine's hum, not mine. I could not listen to what came back; I report what the surface showed.

## 1. What I did

1. Opened `/latent-lab/re-enactment`. Preparing column: "Record something!" with a dashed zone "Click here to record — up to 4:00"; "Choice of model" with four chips (HeartMuLa, SA3 Music, SA3 SFX, VoxCPM2), none selected; "Output · WAITING". Right: three columns "Audio analysis", "Recognised words", "Generated lyrics", each "WAITING". The run button's tooltip: "Send the recording through the four machines". The Ask-me sign's question: "What can you actually hear of my music, and what happens to my recording on the way to the song? I would also like to know what is worth trying here." The Help panel opens by itself on the first arrival with the page's text: "This is a playful exploration of what an AI understands — and misunderstands — about musical and cultural matters. The page listens through the microphone, tries to recognise singing and speech, then sound situations and styles, and finally to rebuild them: a chain of translations full of translation losses and artefacts, which can be experienced like a distorting mirror." "Two things can be learned here: to provoke a particular output on purpose with sung or played input, and to meet your own means of expression and clichés of perception in doing so. And to find that an AI often invents something even when there is nothing but silence, and that entirely different recordings often produce very similar, clichéd results." I overlooked it on first use.
2. Clicked the zone; it showed a running time; after ten seconds I clicked again. The zone turned into a player "0:00 / 0:09" with "0:09" under it. The four model chips were now disabled (the choice is locked once a recording exists).
3. Sent it through the machines at 10:24:25 with no model chosen. The header counted "Step 1 / 4" to "Step 4 / 4" and the columns filled in turn, each naming its machine and the seconds it took: Audio analysis, Recognised words, Generated lyrics, Output "made by HeartMuLa" with a player of 10.1 s.
4. For the second model choice: deleted the recording (the Delete button of the zone), which re-enabled the chips; chose "SA3 Music"; recorded the hum again (0:10); sent it again. The four columns filled in turn, Output "made by SA3 Music".

Runs: 2 recordings, 2 passes through the four machines.

## 2. What the controls did

- The zone: first click starts recording (a timer runs), second click stops; then it is a player with Delete.
- Model chips: choose the machine that sings the song back; enabled only while no recording exists; with none chosen the pass used HeartMuLa.
- Run: the four machines in sequence; the header counts the steps, each column reports its time and its machine's name.
- Each column carries sentences that say what its machine does and does not do (quoted in 3); the Output column carries the player.
- Ask me: not used. Help: opens by itself on the first arrival with the page's text quoted in 1; every later click shows that text again.

## 3. What came out

**Audio analysis** (CLAP-Music&Speech, then MuQ-MuLan), first pass. The column says: "This machine, CLAP-Music&Speech, cannot say what it got. It can only sort it against words that were written down in advance." Its list for the hum: +0.34 a clean studio recording, +0.24 jazz, +0.23 synthesizer, +0.15 flute, +0.14 accordion, +0.13 country, +0.11 electric guitar, +0.10 silence; last place −0.20 several voices singing together. "A second machine, MuQ-MuLan, got the same recording and the same list:" +0.50 no voice at all, +0.46 synthesizer, +0.39 noise, not music, +0.38 humming without words, +0.35 metal. Then: "It used to be the only one here. The song is written from both lists — and of the two lists only this second one has a say in which machine sings it back. Where the two disagree, there is no way to tell from the page which is closer." "The list has 46 entries and we wrote it, not the machine. It always picks a best match, even from silence — there is no answer for "none of these"." And a paragraph on a measurement: seven audio models held against 125 listeners across five musical traditions; CLAP-Music&Speech came closest, "People still separated the traditions about one and a half times as sharply as it did. Cross-Cultural Music Similarity, TISMIR 2025". For a synthesised hum, "synthesizer" (both machines) and "humming without words" (MuQ-MuLan) are apt; "no voice at all" at the top of the second list is wrong for a hum and right for a synthesiser, which is what it was. Second pass, same hum: nearly the same lists (CLAP: studio recording, jazz, synthesizer, flute, throat singing, silence, country, loud and aggressive; MuQ-MuLan: no voice at all, synthesizer, noise not music, metal, a voice speaking not singing).

**Recognised words** (HeartTranscriptor). The column says: "This machine returns words for any recording at all." First pass: "У-ууууууу…а" (a line of about 170 Cyrillic у's), then "Noise and an empty room are enough: out of them this machine writes fluent, confident sentences, in a language it invents along with them." and the translation "Oo-oooo…a", with: "Nobody told it which language to listen for. It decided on its own that this was russian — before it decided on a single word. The song keeps that decision, whatever was actually spoken in the room." Second pass: "у-у", translated "oo-oo". The hum had no words; the transcriber returned a vowel in Cyrillic and the surface named the language decision as a decision.

**Generated lyrics** (openrouter/anthropic/claude-opus-5.5). "A language model turns the two readings above into a song, filling every gap without hesitating." First pass: "style: synthesizer, ambient, wordless humming, clean studio recording, sustained drone, jazz tinge, instrumental, slow / [Verse] / У-ууууууууууууууу / ууууууууууууууа". Second pass: "style: synthesizer, instrumental, clean studio recording, ambient drone, dark electronic, sparse, low vocal hum / [Verse] / у-у / у-у-у". Under it: "Read this while the song plays. What is asked for here and does not come back is something the music model cannot do — and what comes back without being asked for is what it put there instead."

**Output.** First pass: "made by HeartMuLa", a player of 10.1 s (`/api/parrot/sung/…`). Second pass: "made by SA3 Music", a player of 10.5 s. I could not hear either.

The chain is legible on the surface: analysis as a ranked list against a fixed vocabulary, transcription that invents a language, lyrics that fill the gaps, and a song from the style line and the verse. The sentences in the columns name each machine's limit in plain words.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- The model chips lock as soon as something is recorded; a user who records first cannot change the model without deleting the recording, and nothing says so.
- "Send the recording through the four machines" names four, but the Audio analysis column holds two machines (CLAP and MuQ-MuLan), so there are five names on the page.
- The Cyrillic line of 170 letters overflows the column's width; the translation under it is the readable part.
- The 46-entry list is mentioned but not shown; a user cannot see which words the machines could choose from.
- "Output" is a player only; the style line in the lyrics column is the only hint at what was asked of the music model.

## 6. What the help text should tell a user

The Help panel's own text, which opens on arrival, is quoted in 1: it says that the page listens through the microphone, tries to recognise singing and speech, then sound situations and styles, and rebuilds them as a chain of translations with losses and artefacts, and what is learned. It should add the handling: record up to four minutes, choose which model sings it back before recording, and send it through the machines; two audio models sort the recording against a fixed list of 46 words, a transcriber returns words in a language it decides on by itself, a language model writes a style line and a verse from both, and the chosen music model generates a song of about ten seconds from that; each column names its machine, its time and what it cannot do.

## 7. Use possibilities, action-oriented

- Hum without words, then sing a line with words, and compare what the transcriber returns and which language it decides on.
- Record the same thing twice and compare the two analysis lists (they differed by one or two entries here).
- Send one recording through HeartMuLa and the same through SA3 Music and SA3 SFX; listen to what each puts into the song that was not asked for.
- Record silence or room noise and read what the chain makes of it.

## 8. Teaching scenarios

**S1 — What the machine heard** (formal, music, grades 7–10, 90 min). Pupils record a short hum or clap pattern in groups, send it through the chain, and fill a table per column: what was there, what the machine said, what it got wrong; then they listen to the song and mark what in it was in the recording. Sequence: 15 min recording; 30 min run (used to read the column texts aloud); 25 min table; 20 min listening and marking. Subject link: listening, description, transcription. Uncertainty: recordings of children's voices stay on the local server; the lyrics step goes to a cloud model (the column names it), which a teacher must know before recording speech.

**S2 — The invented language** (formal, language teaching, grades 9–12, 45 min). The class sings a line in German, reads what the transcriber returns and which language it chose, and discusses the sentence "It decided on its own that this was russian — before it decided on a single word." Subject link: speech recognition, language identification, confidence.

**S3 — Five models, one hum** (non-formal, music workshop, 3 h, age 14+). Participants send one recording through all four music models (four recordings of the same hum, one per model) and compare the four songs against the same style line. Subject link: generative music models, what a style line can and cannot ask for.

## 9. AI-Lit mapping (built from S1–S3)

**(a) 100 % hits**

- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S1: the table per column is a description of a four-step chain, each step a different machine with a named limit.
- Engage 2 Basic — "Learners know AI is a non-human tool that produces outputs based on patterns of data and lacks authentic context or understanding." S2: words out of a hum, a language decided before a word.
- Engage 3 Basic — "Learners understand why AI-generated outputs should be verified and recognise how they can verify the content themselves." S1: the table per column (what was there, what the machine said, what it got wrong) is the check, done against the group's own recording.

**(b) Mutatis mutandis**

- Shape 1 Intermediate — "Learners describe the purpose, intended users and basic constraints of a specific AI tool." Modification: the framework's classroom example has learners name, per tool, its task, its input and how the output executes the task; S1's table does that for each of the four machines of the chain, with the constraints the column sentences state ("cannot say what it got", "returns words for any recording"). Intended users are not named on the surface.

**Non-fits**: Engage 1, 4, 5, 6, 7, Manage 1–4, Shape 2, 3, 4, Create 1–4.
