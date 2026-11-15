# 08 Image Understanding — `/latent-lab/image-understanding`

Used 2026-11-02, 21:12–21:25 CET, UI language English, not signed in.

## 1. What I did

1. Opened `/latent-lab/image-understanding`. Preparing column: two mode buttons "Upload" / "Sketch", a dashed drop zone "Click here or drag an image here — PNG, JPG, WEBP (max 10MB)", "Perspective" with a select (Example prompts: Neutral description, Detailed description, Art-historical, Educational theory, Ethical analysis, Critical reading) and a prompt field prefilled with "Describe this image in 2-3 sentences. Focus on subject, composition, colors, and style.", and "Vision Models": ten green chips, all active: Qwen 3 VL (China 2025) 2.1b, Ministral 3 (France 2025) 3.8b, Qwen 3.5 (China 2026) 4b, Gemma 3 (US 2025) 4.3b, Qwen 3 VL (China 2025) 4.4b, Qwen 3 VL (China 2025) 8.8b, Qwen 3.5 (China 2026) 9b, Qwen 3.5 (China 2026) 27b, Qwen 3.8 (China 2026) 27b, Qwen 3 VL (China 2025) 33.4b — each marked "local". Right: ten narrow empty columns headed by the model names. The run button is the play triangle ("Analyze Image"). The Help panel opens by itself on the first arrival with the page's text: "The page takes in a picture — uploaded or drawn here — and offers six perspectives underneath: two descriptions, an art-historical one, an educational-theory one, an ethical one, a critical one. The page enters the chosen perspective into the field below as an instruction. Several vision models carry out the instruction; all of them get the same picture." "This is not here to take the work of interpreting a picture off anyone's hands: the machine's interpretations are themselves the matter. The columns show how a text AI “sees” pictures and how it produces an image interpretation from them. Machine image analysis decides about people: diagnoses, arrests and refusals at a border follow from it — people have been arrested because a system matched their face to a picture, and those affected rarely get to see the analysis itself. It appears as a finding; here several readings of the same picture stand side by side. Follow what a model names first, what it holds on to, and at which point it moves from what is to be seen to what it is supposed to mean. The same lines are sometimes called order and structure in one column, and home, shelter and identity in the next." "This help can support you with the comparative analysis of the results. Just ask it about them." I overlooked it on first use.
2. Image: a photograph with people and objects from Wikimedia Commons, "Nurse aides going to work" (Flickr Commons, National Library of Medicine, no known restrictions), 1280 × 867 px black-and-white: five young women in white uniforms on a gravel drive in front of a brick building, a hill, a dark shed and a trailer behind. Uploaded through the file input; the drop zone showed "Original: 1280×867px, Size: 632.2KB".
3. Clicked nine chips off so that one model remained: Qwen 3 VL (China 2025) 4.4b. The right side reduced to one column.
4. Perspective "Neutral description" (the prefilled prompt). Analyze. The reading (the column head shows the seconds it took): "This black-and-white photograph captures five women in matching white uniforms standing in a line on a gravel driveway, posing cheerfully in front of a modern brick building. The composition is balanced, with the women centrally framed against a backdrop of a grassy hill, a small red barn, and a parked trailer, suggesting a rural or semi-rural setting. The monochrome palette lends a nostalgic, vintage feel, evoking mid-20th-century Americana with its clean lines and composed group portrait style."
5. Perspective "Critical reading". The prompt field filled with a long structured instruction (five sections: PICTORIAL ORDER, KNOWLEDGE ORDERS, THE ARCHIVE BEHIND THE IMAGE, TWO PICTORIAL ORDERS, REFLECTION QUESTIONS; rules: read the order off the image, say when the origin cannot be established, at most 900 words, "Critique means: analyze the conditions of the visible, not moralize"). Analyze. A five-section reading of about 600 words.

Runs: 2 readings with one model.

## 2. What the controls did

- Upload / Sketch: the upload mode takes a file; sketch mode (not used) presumably offers a drawing pad.
- Perspective select: fills the prompt field with a preset; the field can be edited. "Neutral description" is three sentences; "Critical reading" is a page-long framework; the other four were not opened.
- Model chips: toggle; one may stay active alone (unlike the picture surfaces).
- Analyze Image: runs the prompt with the image on every active model; each column shows the model name and, when done, the seconds it took.
- Copy / Paste / Delete on the image box; Copy / Paste / Choose Perspective / Translate / Delete on the prompt; Hide column: not used. Help: opens by itself on the first arrival with the page's text quoted in 1; every later click shows that text again.

## 3. What came out

- Neutral reading: correct on the count (five), the uniforms, the gravel, the building, the hill, the trailer and the monochrome. One invention: "a small red barn" in a black-and-white photograph; the shed is dark, its colour is not in the picture. One interpretation presented as description: "mid-20th-century Americana".
- Critical reading: the structure of the framework was followed with headings. Correct: frontal posed group, gaze to the camera, empty ground, institutional/documentary use, uniform dress with one woman's dress different (true: the middle one wears a different cut). Wrong or unfounded: "low-angle" (the camera is at eye level), "not showing their faces in detail" (all five faces are visible and smiling), "parallel perspective" as a finding when the picture is a plain photograph. Section 4 ("two pictorial orders") produced a second order that is a reading of function rather than a different pictorial order, which the framework explicitly asked for. Section 5 gave two of the "3–5 specific questions". The model did not say that the origin is unknown; it decided "likely a photograph from the mid-20th century, possibly from a nursing school", which the rules allow as a reading but asked to be marked as open.
- The frames are visibly different instruments: the neutral prompt yields a caption, the critical frame a structured essay with the same errors of seeing (invented colour, invented angle) carried into a more authoritative form.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- All ten models are active by default, so a first run is ten readings; the Help text says that several vision models carry out the instruction and does not say how many are active.
- The long perspective prompts fill the field with a page of text; the field is 135 px high, so the user scrolls inside it.
- The column shows seconds but not whether the model is loading, queued or reading.
- The invented details (red barn, low angle) are stated with the same confidence as the correct ones; nothing on the surface marks uncertainty.
- What the Sketch mode offers is not said beyond the Help text's "drawn here".

## 6. What the help text should tell a user

The Help panel's own text, which opens on arrival, is quoted in 1: it says that the page takes a picture, uploaded or drawn, that six perspectives are offered and the chosen one is entered into the field as the instruction, that several vision models carry out the instruction on the same picture, and what to follow in the readings. It should add: all ten models are active by default, and chips can be turned off down to one; each column shows the seconds the model took; the perspectives range from a three-sentence caption to a page-long framework, and the field can be edited; a reading can state things the picture does not contain (a colour in a black-and-white photograph, an angle that is not there), so compare the reading with the picture before using it.

## 7. Use possibilities, action-oriented

- Upload one photograph, run the neutral description, and underline every word in the reading that the picture does not show.
- Run the same picture under "Neutral description" and "Critical reading" with one model and mark where the framework changed the facts rather than the form.
- Run one picture through three models of different size (2b, 9b, 27b) and compare the inventions.
- Use a group's own drawing (Sketch mode) and compare the model's reading with the drawer's intention.

## 8. Teaching scenarios

**S1 — Reading against the picture** (formal, language teaching or art, grades 7–10, 45 min). Pairs upload a photograph (from a free archive or their own, without faces of classmates), run the neutral description with one small model, print the text and underline what is invented, what is interpreted, what is described. Sequence: 5 min upload; 5 min run; 20 min marking; 15 min comparison of lists. Subject link: description vs. interpretation. Uncertainty: pupils' own photographs of people need consent; archives such as Wikimedia Commons avoid this.

**S2 — The frame makes the finding** (formal, art history or media, grades 11–13, 90 min). The class runs one photograph under three frames (neutral, art-historical, critical reading) with one model, lays the three readings side by side and asks: which claims are the same under all three, which appear only under one frame, and which claims are wrong in all three. Then they read the critical frame's own rules ("not moralize", "say when the origin cannot be established") and check whether the model followed them. Subject link: methods of image analysis, instruction and output.

**S3 — Small, medium, large** (non-formal, maker space, 2 h, age 15+). One picture, three models of different size, neutral description; participants time each reading from the column head and list the inventions per model. Subject link: model size, cost, reliability.

## 9. AI-Lit mapping (built from S1–S3)

**(a) 100 % hits**

- Engage 3 Basic — "Learners understand why AI-generated outputs should be verified and recognise how they can verify the content themselves." S1: the underlining against the picture.
- Engage 3 Intermediate — "Learners verify AI-generated outputs for accuracy and relevance by consulting trusted sources and considering task-specific expectations." S1: the photograph itself is the source the reading is checked against; S2: the frame’s own rules (“not moralize”, “say when the origin cannot be established”) are the task-specific expectation.
- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S2: the instruction (frame) is read and its effect on the output described.
- Shape 2 Intermediate — "Learners assess an AI system performance of a task using defined criteria and feedback from human reviews or benchmark tests." S3: the inventions per model and the seconds from the column head are the defined criteria, the group’s list the human review.
- Engage 5 Basic — "Learners recognise that computers and AI systems require resources to function." S3: timing per model size is on the surface.

**(b) Mutatis mutandis**

- Engage 6 Intermediate — "Learners explain how biased data or design choices (e.g. stereotyped content, misclassification, unequal recommendations) can lead AI systems to generate unfair or skewed outcomes for certain groups." Modification: the skewed output is a reading, not a generation: the model's description of a historical photograph carries stereotyped content (“Americana”, “nurse-like attire”, gender as self-evident), which the critical frame's section 2 brings out and S2 checks against the frame's own rules. The framework's classroom example asks how and why a system performs differently for different people; S2 asks it of the people in the picture.

**Beyond the framework**: the framework's Engage 3 examples check one AI output against a source; S2 holds three readings of one photograph under three instructions against one another and against the instruction's own rules, so the instruction becomes part of what is checked.

**Non-fits**: Engage 1, 4, 7, Manage 1–4, Shape 1, 3, 4, Create 1–4.
