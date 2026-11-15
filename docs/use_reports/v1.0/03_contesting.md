# 03 Contesting — `/contesting`

Used 2026-11-02, 20:06–20:14 CET, UI language English, not signed in. Headless browser on the dev machine; speech generated but not heard.

## 1. What I did

1. Opened `/contesting`. Same empty board as Together: mask icon top right, a gear bottom left, Help top right, Favorites bar at the bottom, an invisible writing line in the middle. No mode buttons this time, no green plus. On arrival the Help panel opened by itself with the page's own text: "If we want to be creative, or to get something right, we need imagination, because without an idea nothing happens. But working artistically means working further on our own idea and developing it. An AI must not take our imagination away, but it can help us develop our ideas further. This page puts up resistance to your ideas. It challenges you to understand your own ideas better, and it can also support you in that. -- But you have to convince it - that is not easy!" and "Two things can be learned here: to put an idea into words, sharpen it and give reasons for what you want to achieve and why, and to see how a chatbot reacts if it is not told to be pleasing and charming." I overlooked it on first use.
2. Typed the claim "AI images are art." and pressed Enter. The answer began, spoken and written sentence by sentence; what I saw on the surface first was "Hello. What answers here is a machine, more precisely several machines working together, and none of them takes orders." and, when the speech ended, only the last sentence remained in the middle: "Name one AI image that actually stopped you, and say what it did that the others did not." The server log shows the full answer had 704 characters; the surface kept only the last sentence after the speech ended.
3. Answered that last sentence once: "One of the harbour pictures we made in Flow today: the film looked boiled, magenta and teal, and I kept looking at the blistered edges rather than the harbour." The reply appeared in pieces: "That is a precise observation. The harbour was what was asked for, the boiled film was what nobody asked for, and your eyes stayed with the part nobody asked for. Bill Morrison made a whole film, Decasia, from old reels that were rotting in archives." → "The decay is the subject: faces and buildings dissolve into blisters and stains, and the damage carries more than the picture underneath." → "So the question comes back sharper. If nobody chose the blistering and it simply happened, then what made it worth looking at was your noticing, not the making." → and finally, the only sentence that stayed: "This platform will test that by reversing the order: the damage becomes the subject, and the harbour is only a ghost behind it. The reason: you named something exact, the edges instead of the harbour, and that is a decision worth materializing."
4. At the same moment a box appeared top left: "Wan 2.2 T2V 14B Fast · 0 %". The machine had started a video generation on its own. The server log shows the prompt it wrote: "Extreme close-up of decaying 16mm film emulsion, blistering and bubblin…", config `wan22_t2v_video_fast`, 16 fps. The box showed a progressive preview and the percentage (62, 84, 88, done): a 10-second video. Content: a magenta-teal film strip with sprocket holes, bubbles and emulsion blisters drifting over a faint harbour skyline.
5. "Use a suggested prompt after its reply": nothing on the surface offered a prompt — no chips, no placeholder in the writing line, no element named suggestion. The generated video's own prompt is not shown on the box either (the box has ×, Add to favorites, Download and two unlabelled buttons on hover; a provenance toggle exists in the DOM but is not visible). I could not carry this step out.
6. Moved the box: dragged it by its dotted header from the top-left corner to the middle of the page (from 20,89 to 420,463 px). It followed the pointer and stayed where I dropped it, overlapping the conversation.

Runs: 2 chat turns, 1 video generation started by the machine, ~10 speech syntheses.

## 2. What the controls did

- Writing line: Enter sends. The answer is spoken (local speech system) and written in sync, one or two sentences at a time; after the speech ends only the last sentence remains visible. Earlier exchanges disappear.
- Speaker icon under the answer: "Stop" while sounding, "Read this out" afterwards.
- Generated box: appears without being asked when the machine decides to "materialize"; shows model name and percentage, then the media with a player; draggable by its header; × removes it; on hover: Add to favorites, Download (and, while the box was still at 0 %, the DOM also listed Forward to Flow, Print and Image Analysis).
- Gear bottom left: Surface settings (not opened). Help: opens by itself on the first arrival with the page's text quoted in 1; every later click shows that text again.

## 3. What came out

- The contesting is real: the first answer did not agree or disagree with "AI images are art" but demanded a concrete case, which is what the Help text announces ("This page puts up resistance to your ideas … you have to convince it"). The second answer took my case, named a reference (Bill Morrison's "Decasia"), turned the claim around ("what made it worth looking at was your noticing, not the making") and then acted: it generated a video in which the damage is the subject and the harbour a ghost. The video matches that description.
- The written trace of the argument is lost on the surface: after each turn only the final sentence stays, so the Morrison reference and the turning of the argument exist only in speech and in the server log. A user who missed the spoken sentences cannot re-read them.
- The video generation ran without a question and without naming its cost (a 14-billion-parameter video model); the only announcement was the box.
- Model behind the voice: anthropic/claude-opus-5.5 via openrouter (server log); the speech: local Supertonic; the video: local Wan 2.2 on ComfyUI.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- The Help text that opens on arrival says what the page does (it puts up resistance to your ideas, you have to convince it) and what is learned; it says nothing about where to write, that the writing line is invisible until typed into, or that the answer vanishes sentence by sentence. I overlooked the panel myself on first use.
- The answer vanishes sentence by sentence. Anyone who reads slower than the voice speaks loses the argument; there is no transcript.
- A video starts by itself at the machine's decision. Nothing says why, how long, or that it can be stopped (× removes the box; whether it stops the job is not shown).
- The generated box does not show the prompt that produced it; the "reason" is only in the spoken sentence.

## 6. What the help text should tell a user

The Help panel's own text, which opens on arrival, is quoted in 1: it says that the page puts up resistance to your ideas, that you have to convince it, and what is learned. It should add the handling: write a claim into the invisible line in the middle; the machine answers by voice and in writing, but only the last sentence stays on the page, so listen while it speaks. It may answer with a picture or a video instead of words, at its own decision; the box shows the model and the progress and can be dragged, downloaded, kept as a favourite or removed with ×. Answer its last sentence to keep the argument going; the speaker icon replays the last answer.

## 7. Use possibilities, action-oriented

- Put a strong claim in and defend it against the machine's counter-questions for three turns; note which of your own words it picks up.
- Give it a concrete case from the group's work and see whether it answers with media; discuss what in its answer was argument and what was display.
- Use the generated box as a counter-example on the board: drag it next to the group's own picture.
- Replay the spoken answer for the room and write the argument down yourselves, since the page does not keep it.

## 8. Teaching scenarios

**S1 — Claim and counter** (formal, ethics or language/literature lessons, grades 9–11, 45 min). Pairs write one claim about AI and art, send it, and write down the counter-question they get. Then they answer it once and record what the machine did (argued, referenced, generated). Sequence: 5 min claims; 15 min two turns per pair, writing the sentences down as they are spoken; 15 min pairs exchange their transcripts; 10 min plenary: which counter-questions were fair, which evasive. Subject link: argumentation, position and counter-position. Uncertainty: only one pair can speak at a time in a room; written mode is not offered on this surface, so the class needs headphones or sequential use.

**S2 — When the machine answers with a picture** (non-formal, art workshop, 3 h, age 15+). Participants bring one image they made and describe to the machine what they kept looking at. If the machine generates in return, the group compares its generation with the original and asks what was "reversed". Sequence: 20 min intro; 90 min turns; 50 min wall of originals and answers; 20 min discussion of who decided what. Subject link: authorship, reception aesthetics.

**S3 — The lost transcript** (formal, media studies, grades 11–13, 90 min). The class records a conversation with the contesting machine (audio recording of the room), then reconstructs the written argument from the recording and compares it with what the page kept. Sequence: 20 min conversation; 40 min transcription in groups; 30 min comparison and discussion of what a surface that keeps only the last sentence does to an argument. Of course, the agent can always be asked for the course of the conversation. Subject link: oral vs. written argument, interface design.

## 9. AI-Lit mapping (built from S1–S3)

**(a) 100 % hits**

- Engage 7 Intermediate — "Learners identify when AI use may have unintended impacts or implications that are different from a user’s immediate goals." S2: the machine generates a picture nobody asked for, and the group asks what was “reversed”; S3: the surface keeps only the last sentence, and the class examines what that does to an argument it did not intend to lose.
- Create 1 Basic — "Learners explore how different AI tools can expand their thinking or spark new ideas." 
- Create 1 Intermediate — "Learners compare AI-generated suggestions to their own ideas during a brainstorming process." S2: the machine’s generation is set against the participant’s own picture.

**(b) Mutatis mutandis**

- Shape 1 Intermediate — "Learners describe the purpose, intended users and basic constraints of a specific AI tool." Modification: the purpose is read from the Help text’s own words (the page puts up resistance to your ideas); the constraints (the surface keeps only the last sentence and generates without asking) are found by use, and intended users are named nowhere. Ex negativo, because barely any agent will act like "contesting", the medial structure of typical AI frameworks and model strategies become visible/perceivable. Justification: S3 is about that design.
- Create 4 Intermediate — "Learners consider when attribution, permission or avoidance of AI is appropriate for a creative task and apply these choices in their own work." Modification: the media was generated without a request; the question becomes whether an unrequested generation can be used in the group’s work, and the choice is applied to the wall in S2. OR a generation is deliberately denied by the agent, posing the question of one would not better make this artwork by oneself without genAI.

**Non-fits**: Engage 1, 2, 3, 4, 5, 6, Manage 1–4, Shape 2–4, Create 2, 3 — no datasets, no bias comparison, no task decomposition and no checking against a source in these scenarios.
