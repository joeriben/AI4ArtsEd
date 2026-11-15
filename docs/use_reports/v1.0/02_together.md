# 02 Together — `/together`

Used 2026-11-02, 19:50–20:06 CET, UI language English, not signed in. Headless browser on the dev machine: the audio could not be heard, only its generation and playback state observed (see 00_README.md).

## 1. What I did

1. Opened `/together`. A dark, empty board with a mask icon (top right), a green plus (bottom left, "Bring something in"), a gear ("Surface settings"), zoom buttons (+ / − / 1:1) and three small mode buttons at the right edge: "Voice only" (preselected), "Voice and writing", "Writing only". On arrival the Help panel opened by itself with the page's own text: "This page is for planning and shaping artistic and/or AI-related learning with this platform: the planning with educators, the workshop itself, and the review afterwards of what was done and how the AI behaved. What this platform has been given about itself, about generative AI and about artistic-pedagogical approaches can be looked up here." and "Two things can be learned here: to plan and shape art-pedagogical processes with generative AI, and to watch and judge how an AI tries to carry out human artistic and pedagogical aims — can it contribute without putting itself at the centre, and can it stay silent when that is called for?" I overlooked it on first use. The writing line (a textarea in the middle of the board) is invisible until something is typed.
2. Switched to "Voice and writing" (so that answers are both spoken and written).
3. Typed a greeting: "Hello! We are a group of eight teenagers in a Saturday media workshop. Could you propose something we could do together today?" and pressed Enter. An answer appeared, right-aligned in blue, and the mask icon showed sound waves: "What each of you brings matters more than anything this platform could add, and nothing about your work today is known here yet: no project has been noted for your group." Under it a yellow "lift out" button and a speaker icon.
4. Replied once: "We have not decided on anything yet. We have phones with cameras, and most of us like music and drawing. What could a two-hour session look like?" Then the previous exchange was gone from the middle of the board, the new one stood there, and two cards appeared top left without my doing: a plan card titled "Drawing, humming, and what the machine makes of it" with buttons "Copy plan", "lift out", "×", and a small NOTE card containing the text "canvas_solution". The spoken sentence read: "Since you have phones, like music and like drawing, here is a session where the same material goes from paper to sound and back."
5. Green plus → three buttons "Upload / Camera / Text". Uploaded a 640×480 PNG line drawing (a staircase, a circle, the caption "stairs at 7 am"). A 62 px thumbnail appeared next to the writing line. Typed "I just put one of our drawings on the board. What do you make of it?" and pressed Enter. The mask went to "listening"; then: "Two looks at the drawing found the same things. There's a staircase of five steps rising from bottom left to top right, ending in a short line that bends up slightly. To the right of the top step is a circle with one curved line inside it. Along the bottom runs a horizontal line, and under it are the words "stairs at 7 am". Nothing else is on the page: no person, no motion lines, no lines coming out of anything, no shading."
6. Pressed "Copy plan" on the plan card. The button label changed to "Copied"; the plan landed in the clipboard as plain text ("Drawing, humming, and what the machine makes of it / Zweck: A two-hour session … / 1. Draw a sound (20 min) — …"). Nothing new appeared on the board.
7. Voice output: in "Voice and writing" mode every answer is spoken automatically (the speaker icon is in a "sounding" state while it plays, the mask shows waves). Clicking the speaker during playback stopped it; clicking again ("Hear this again") replayed it. The server log shows each answer synthesised in sentence-sized pieces by the local speech system (config `supertonic_standard`, ≈0.2 s per sentence); the browser requested `/api/speech` five times for the last answer.

Runs: 3 chat turns, 1 upload, 2 image looks (server-side), ~8 speech syntheses.

## 2. What the controls did

- Mode buttons (right edge): Voice only / Voice and writing / Writing only. "Voice only" is the default; on a machine without microphone or in a quiet room there is no visible way in except switching to writing.
- Writing line: appears where you type, Enter sends. The previous exchange disappears when the next one starts; the "lift out" button presumably moves an utterance onto the board as a card (not tested on an answer; the plan card is the lifted-out form).
- Green plus: Upload / Camera / Text. The uploaded picture is attached to the next message as a thumbnail; it does not become a board card.
- Plan card: "Copy plan" copies the plan as text to the clipboard (label → "Copied"), "lift out" and "×" (discard memo). The NOTE card "canvas_solution" has only "×".
- Speaker icon next to each answer: stop / "Hear this again".
- Mask icon top right: idle / listening / uttering states (waves while speaking).
- Help: opens by itself on the first arrival with the page's text quoted in 1; every later click shows that text again. Surface settings gear, Favorites bar at the bottom (Mine / All): not used.

## 3. What came out

- The first answer did not propose anything; it said that nothing is known about the group yet. A newcomer would read this as a refusal or as a system with no idea.
- The second answer produced a complete two-hour plan on the board: six steps with minutes (Draw a sound 20 / The machine looks 20 / Hum the place 25 / Read the steps 20 / Your own version 25 / Listen and show 10), each pointing to a surface of this platform by name (Compare and Analyse → Image Understanding; Re-enactment; Flow with the song model). The plan is usable as written; the steps add up to 120 minutes. The clipboard copy carries a German label "Zweck:" in an otherwise English text.
- The picture reading is accurate and literal (five steps, circle with a curved line, the caption). It names what is absent (no person, no shading). The server log shows two consecutive local vision jobs (qwen3-vl:4b over ComfyUI) because the chat model (anthropic/claude-opus-5.5 via openrouter) is not handed uploaded pictures and asks a local model to look twice.
- The NOTE card "canvas_solution" is an internal name that leaked onto the board; nothing on the surface says what it is.
- Speech: generated locally, split per sentence, voices "even" and "clear" in the log. I could not hear it.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- The Help text that opens on arrival says what the page is for (planning with educators, the workshop, the review afterwards) and what is learned; it says nothing about how to begin: not that the writing line is invisible until typed into, not what to write first. I overlooked the panel myself on first use and looked for a cue on the empty board.
- The three phases the Help text names (planning with educators, the workshop itself, the review afterwards) are not set apart as modes on the surface.
- The first answer ("nothing about your work today is known here yet") reads as a non-answer; the plan only came after a second message with concrete material (phones, music, drawing).
- After an uploaded picture, only the mask in "listening" state and no progress indication.
- Two cards appear top left without being announced; the NOTE "canvas_solution" is meaningless to a user.
- "Copy plan" copies to the clipboard; nothing on the surface says where the plan went.
- Previous exchanges vanish from the middle; where they go (if anywhere) is not shown.

## 6. What the help text should tell a user

The Help panel's own text, which opens on arrival, is quoted in 1: it names the three phases (planning with educators, the workshop itself, the review afterwards) and the two things to be learned. It should set those three phases apart as the three main ways of using this surface and say for each what to write first. It should add the handling: the voice switch in the main menu decides whether answers are spoken as well as written, and a quiet room needs it switched off; a plan comes as a card on the board and "Copy plan" puts its text into the clipboard; a picture uploaded with the green plus is attached to the next message and read by a local model on this server, with no visible progress; the speaker icon stops and replays an answer, "lift out" keeps an utterance on the board.

## 7. Use possibilities, action-oriented

- Open a workshop by telling the companion what the room has (devices, time, interests) and let it draft a session plan onto the board; edit the plan, not the prompt.
- Use the plan card as the group's agenda: copy it into the shared document, then follow its pointers to the named surfaces.
- Show a drawing or photo and ask what the machine sees; compare the literal reading with what the drawer meant.
- Let the companion speak an answer aloud for the room while the written version stays on the board.

## 8. Teaching scenarios

**S1 — Planning with the companion** (non-formal, open youth centre, 2 h, age 12–16, one facilitator). The group tells the companion what it has (phones, instruments, time), takes the plan card as its agenda and runs it. Sequence: 10 min typing the situation in and reading the plan aloud (voice); 90 min following the steps on the named surfaces; 20 min back on Together to report what happened, one sentence per person. Subject link: media education, self-organisation. Uncertainty: the first answer may be a non-answer; the facilitator needs to know that concrete material (what the group has) triggers the plan.

**S2 — What the machine saw** (formal, art, grades 5–7, one lesson of 45 min). Each pair draws a place (a room, a street, a playground), photographs the drawing with the class tablet, uploads the photo with the green plus and asks what the machine sees in it. Sequence: 10 min drawing; 5 min upload and question; 15 min run (used for a second drawing); 15 min reading the answer against the drawing, marking what was seen, what was missed, what was invented. Subject link: picture description, looking and naming.

**S3 — Teacher's planning desk** (formal, teacher training, 60 min). Teachers in training use Together as a planning partner: they describe a class, a subject and a time frame, receive a plan, copy it out, and then critique it against their curriculum — which steps are realistic, which pointers to platform surfaces they have tried themselves. Subject link: lesson planning, didactic judgement. Sequence: 15 min dialogue; 15 min copy and annotate; 30 min comparison in plenary.

## 9. AI-Lit mapping (built from S1–S3)

**(a) 100 % hits**

- Engage 3 Basic — "Learners understand why AI-generated outputs should be verified and recognise how they can verify the content themselves." S2: the reading is checked line by line against the drawing.
- Manage 3 Intermediate — "Learners break a problem into component parts and consider ways AI might help with specific steps." S3: the plan is a decomposition of a session into steps, each assessed for whether the platform helps.
- Manage 4 Intermediate — "Learners compare AI outputs to desired results and know when to redirect AI systems or improve outputs themselves." S3: the plan is compared with the curriculum and the teacher’s own experience of the named surfaces, and the steps that do not hold are replaced by the teacher; S1 closing round: what the group did against what the plan said.

**(b) Mutatis mutandis**

- Manage 1 Basic — "Learners identify a variety of AI systems and the tasks they are designed to support." Modification: the systems identified are the platform’s own surfaces, which the plan card names with what each is for; the learners meet them by following the plan (S1), not by surveying them.

**Non-fits**: Engage 1, 2, 4, 5, 6, 7, Manage 2, Shape 1–4, Create 1–4 — the scenarios do not produce media, analyse bias or datasets, describe how the models work, or evaluate a system against criteria.
