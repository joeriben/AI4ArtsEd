# 04 Canvas — `/canvas`

Used 2026-11-02, 20:13–20:36 CET, UI language English, not signed in.

## 1. What I did

1. Opened `/canvas`. Left: a MODULES palette in four numbered groups (1 · INPUT: Input Prompt, Image Input, Random Prompt; 2 · INTERCEPTION: Interception, Evaluation, Image Analysis, Comparison; 3 · ADAPTION: Translation, Model Adaption; 4 · GENERATION: Generation; TOOLS: Seed, Resolution, Quality, Preview) with "Click or drag modules onto the canvas". Top bar: sidebar toggle, Outputs toggle, a play triangle ("Execute"), "Batch", a Name field, New Workflow, Import, Export, Add to favorites. The canvas already holds two nodes: INPUT PROMPT (with a textarea "Your prompt…") and MEDIA OUTPUT ("Waiting for execution…"), each with a round port. Bottom: zoom −/100 %/+/fit, and an OUTPUTS strip. The Help panel opens by itself on the first arrival with the page's text: "This is, first, about handling AI building blocks as freely as possible: not about the software foundations, but about what the blocks carry out and how they connect into architectures of your own. And second, that work here does not run in one direction from prompt to result — queries, branches and loops are possible: a self-critical apparatus by your criteria." "Two things can be learned here: to compose complex generative sequences across different media, and to develop artistic setups for exploring generative AI freely. And that AI can be built otherwise than as a straight line from input to output, and that different models can work not only with and after one another but also against one another." I overlooked it on first use.
2. Smallest graph: typed "a small harbor at dusk" into INPUT PROMPT, dragged from its right port to the left port of MEDIA OUTPUT (a blue line appeared), pressed Execute. The run finished in under a second: MEDIA OUTPUT showed "1 item", the OUTPUTS panel slid up over two thirds of the canvas and listed one card "input · input_1793646821289_acyqazj" containing the text "a small harbor at dusk". No media. On disk the run folder holds `01_input.txt` and a `workflow.json` with the two nodes. So the smallest graph "works" in the sense that it runs; it produces the prompt back.
3. Clicked "Generation" in the palette. A node GENERATION appeared on the canvas and, at once, a modal "Select Output Model" with 49 entries, each with a one-line description: Attention Cartography (and a "(Diffusers)" twin), CommonCanvas XL C (twin), Composable Diffusion (twin), Concept Algebra (twin), Denoising Archaeology (three), Dimension Explorer (twin), Flux 2 Dev (twice), Flux 2 Visual Conditioning, Flux 3 Klein, FLUX.2 [dev] img2img, Gemini 3 Pro Image (€), Gemini Nano Banana 2.1 (€), GPT-Image-1, Hallucination (three), Qwen 2511 Multi-Image Fusion, Qwen Image Edit Lightning, SD 3.5 Large Image-to-Image (twice), Stable Diffusion 1.5, Stable Diffusion 3.5 Large (twice), Stable Diffusion 3.5 Large Turbo (twice), Stable Diffusion XL, LTX Video, Wan 2.2 Image-to-Video (14B), Wan 2.2 T2V 14B Fast, eSpeak NG Voice, HeartMuLa Music, Piper Voice, SA3 Music, SA3 SFX, Stable Audio 3, Supertonic Voice, VoxCPM2 Voice, "view_in_ar Image to 3D (Hunyuan3D-2)", "🎨 P5.js Code Generation", "🎵 Tone.js Music Generation". Chose "Flux 3 Klein". The node now shows a dropdown "Flux 3 Klein ▼", three input ports (1, 2, P) and one output port.
4. Wiring: the new node had been placed on top of the direct line between the two existing nodes; a drag from the input's port onto the node's port 1 did nothing until I moved the node down. Then: input → generation port 1, generation output → MEDIA OUTPUT. The direct line was removed by clicking it and pressing Delete.
5. Execute. OUTPUTS strip: "Executing Workflow… / Generating Media / 1 / 3 nodes". A picture of a marina at dusk (sailing boats, pink sky) appeared in the OUTPUTS panel as "generation · generation_…". Server log: config `flux3`.
6. Changed one module: opened the dropdown on the GENERATION node (the same modal), chose "Stable Diffusion 3.5 Large Turbo", Execute again. A different harbour: a dark wooden boat in the foreground, a village with lights, painterly.
7. "Read what the nodes report": during the run the strip shows the phase ("Generating Media") and a node counter; after the run MEDIA OUTPUT carries a badge "1 item" and the browser console reports each node ("Node complete: generation… (2/3)"), but on the canvas itself the nodes show no text about what they did: no seed, no model, no time. Short bubbles flash over the nodes at completion ("Showing bubble for" in the console) and are gone within a second. The export folder on the server has the real report: `events.jsonl`, `status.json` with start and end time, `metadata.json` with the entity list, and the files `01_input.txt`, `02_generation.png`.

Runs: 3 (one text-only, two image generations).

## 2. What the controls did

- Palette buttons: a click adds a node at a fixed spot (overlapping what is there); drag is also offered.
- Ports: drag from an output port to an input port makes a connection; dropping onto a node that lies over an existing line fails silently.
- Click on a line + Delete removes it. × on a node header removes the node.
- Generation node: dropdown opens the model modal; ports 1, 2, P (P presumably "prompt"; nothing says what 1 and 2 take).
- Execute: runs the whole graph; the OUTPUTS panel opens over the canvas and must be closed with the Outputs toggle to see the nodes again.
- Batch, Name, New Workflow, Import, Export, Add to favorites, Seed/Resolution/Quality/Preview tools: not used.
- Help: opens by itself on the first arrival with the page's text quoted in 1; every later click shows that text again.
- Not used either, and named here because the Help text's "queries, branches and loops" run through them: the palette's Evaluation ("LLM-based evaluation with 3-way branching (pass/fail/commentary)", with a criteria field, a "Pass (forward)" output and a "Feedback (backward)" output), Image Analysis ("Vision-LLM analysis of images"), Comparison ("Compare multiple text inputs with LLM analysis", with a criteria field of its own), and the "Feedback Input" (FB) that Interception and Translation nodes carry, into which an Evaluation's feedback is wired so that a run loops. The use script asked for the smallest graph and one module change; I built no loop, and the labels in this bullet are the build's own strings.

## 3. What came out

- A graph that runs in two clicks returns the input text as the "output". Nothing says this is not a generation.
- With a Generation node: a Flux 3 Klein marina (photographic) and an SD 3.5 Large Turbo harbour (painterly) from the same prompt.
- The model list mixes production models, research instruments ("Attention Cartography", "Denoising Archaeology"), paid cloud models (€), voices, music, 3D and code generators in one alphabetical modal, with twins that differ only in "(Diffusers)" or not at all in the label, and two entries whose label contains an icon name ("view_in_ar") or an emoji.
- The nodes report nothing readable after the run; the report is in the export folder on the server.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- "Media Output" with no generation node runs and reports "1 item"; the item is the prompt. The name promises media.
- A new node lands on top of the existing line and swallows the drag.
- The Outputs panel covers the canvas after every run.
- 49 models in one modal, several with identical labels; nothing says which are quick, which are paid, which are research-only.
- Ports named 1, 2, P without explanation.
- No progress percentage, no queue position; only "Generating Media".
- Nothing on the nodes after the run says what model, seed or time was used.

## 6. What the help text should tell a user

The Help panel's own text, which opens on arrival, is quoted in 1: it says that the surface is about handling AI building blocks and connecting them into architectures of one's own, that queries, branches and loops are possible, a self-critical apparatus by one's own criteria, and what is learned, among it that models can work against one another. It should add the handling: a graph needs at least an input, a generation and the media output, connected left to right through the round ports, and without a generation node the output is the text itself; a loop is built with the Evaluation node, whose criteria are written into it, whose Pass output goes forward and whose Feedback output goes back into the FB input of an Interception or Translation node; Image Analysis reads a picture into text, and Comparison judges several texts by criteria of its own. Click a palette entry to add a node, move it clear of existing lines before wiring, and remove a line by clicking it and pressing Delete. The generation node's dropdown chooses the model; entries marked € use a paid cloud service. Execute runs the whole graph; results appear in the Outputs panel at the bottom, which the Outputs button hides again.

## 7. Use possibilities, action-oriented

- Build the three-node chain and swap only the model: the smallest experiment, and the entry to the rest.
- Build a loop: Input Prompt → Interception → Generation → Image Analysis → Evaluation, with a criterion written in your own words into the Evaluation node (for instance: the picture shows the named place without a postcard cliché); wire "Pass (forward)" to the Media Output and "Feedback (backward)" into the Interception node's FB input, so that a judgement of the picture rewrites the prompt and the generation runs again.
- Let two models work against one another: one model's picture is read by Image Analysis under a critical perspective, the reading is intercepted and given to a second model as its prompt; then reverse the roles.
- Put two Interception nodes with two perspectives on one prompt into a Comparison node with criteria of your own, and read what the comparing model prefers and why.
- Keep the run folders (one per run, with the prompt, every intermediate text and the picture) as the record of an experiment over several rounds.

Not tried: the loop, the Evaluation node and the Comparison node.

## 8. Teaching scenarios

**S1 — A picture judged and sent back** (formal, art, grades 10–13, 2 × 90 min). Groups write a prompt about a place or a group of people and, into the Evaluation node, a criterion in their own words for what the picture must not do (the postcard, the costume, the one kind of face); they build Input Prompt → Interception → Generation → Image Analysis → Evaluation, wire Pass to the Media Output and Feedback into the Interception's FB input, run, and read the Outputs: what the reading said, what the evaluation decided and why, how the prompt was rewritten, and how the next picture differs. Then they change the criterion and run again. Sequence: 20 min the three-node chain as the entry; 30 min criterion and build; 40 min first loop and reading; 40 min second criterion; 50 min each group shows one round (prompt, reading, judgement, rewrite, picture) and says what its criterion did. Subject link: artistic research, criteria, iteration; the cliché as the object. Uncertainty: I built no loop; how many rounds a loop runs and how it stops I did not see on the surface.

**S2 — Models against one another** (formal, art or ethics, grades 11–13, 90 min). Pairs let one model generate from a prompt, read the picture with Image Analysis under a critical perspective, intercept the reading and give it to a second model as its prompt; then they reverse the roles. The two chains stand side by side on the canvas; the pairs compare what each model made of the other's picture and what the reading named that the picture did not show. Sequence: 15 min build; 30 min runs; 30 min comparison; 15 min plenary on which part of a reading was a reading and which an invention. Subject link: what one model sees in another's picture; cliché and invention. Uncertainty: I did not build the chain Image Analysis → Interception → Generation.

**S3 — A self-critical apparatus** (non-formal, art-research workshop, 2 days, age 16+). Participants design an apparatus by their own criteria: Random Prompt as the input, a loop of Interception, Generation, Image Analysis and Evaluation, criteria written for what counts and what is sent back, and several rounds; they collect every round's picture, reading and judgement from the run folders and exhibit the chain of one run as the work. Day 1: build, first runs, criteria rewritten; day 2: runs over several rounds, selection, exhibition. Subject link: artistic research, the apparatus as the work, criteria as the artistic decision. Uncertainty: the run folders lie on the server and the facilitator copies them out; I did not run the loop.

**S4 — A inquiry-based learning setup**. E.g. mass-production of different outputs using random prompt generation nodes, creating fine-tuned research data for comparative visual/auditive analyses (e.g. Artistic research; serial image analysis in the style of Mietzner/Pilarczyk; critical visual studies; digital image studies à la Lev Manovich, https://manovich.net/index.php/projects/instagram-and-contemporary-image)

## 9. AI-Lit mapping (built from S1–S3)

**(a) 100 % hits**

- Shape 2 Basic — "Learners define criteria for whether an AI system has accomplished a task." S1 and S3: the criterion written into the Evaluation node in the group's own words.
- Create 3 Intermediate — "Learners refine their work through iterative exchanges with AI, comparing those outputs to their own ideas to determine what serves their goals." S1: every round of the loop is read against what the group wanted the picture not to do, and the criterion is changed on that reading.
- Manage 3 Intermediate — "Learners break a problem into component parts and consider ways AI might help with specific steps." S1 and S3: the apparatus is built from parts, one node per step, and each step is given to a model or kept.
- Engage 6 Intermediate — "Learners explain how biased data or design choices (e.g. stereotyped content, misclassification, unequal recommendations) can lead AI systems to generate unfair or skewed outcomes for certain groups." S1: the cliché is the criterion, the reading and the judgement name it, and the groups say what the criterion did to the picture.
- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S1: one round shown as prompt, reading, judgement, rewrite, picture.
- Create 2 Intermediate — "Learners experiment with AI tools (e.g., text, image or music generators) to develop diverse ideas and produce varied outputs." S2: two models on each other's pictures.
- Manage 4 Intermediate — "Learners compare AI outputs to desired results and know when to redirect AI systems or improve outputs themselves." The redirect is done by the apparatus (the Evaluation's feedback), which the learners set up; they redirect by changing the criterion (S1).
- Engage 3 Advanced — "Learners assess AI-generated outputs and justify decisions to accept, revise or reject them." In S1 the accept-or-revise decision is delegated to the Evaluation node; the learners justify the criterion and read the node's reasons, then discuss using their own vs. the generated assessment.
- Manage 4 Basic — "Learners recognise that they should make decisions about AI use that support accountability, learning and fairness." Canvas strongly supports the use of evaluative and critical functions.

**(b) Mutatis mutandis**

- Shape 2 Advanced — "Learners design their own evaluation criteria for an AI system, compare performance across different inputs and users and use it to propose improvements." Modification: S3 designs the criteria and compares across inputs (Random Prompt) and rounds, not across users; the improvement proposed is to the apparatus the group built, whose criteria are rewritten after the first runs. The framework's classroom example has pairs fill out model cards for each other's tool proposals and revise them; S3 revises a running apparatus instead of a proposal.

**Beyond the framework**: the framework's Shape 2 examples have learners define criteria and fill out model cards; in S1 and S3 the criterion is written into an Evaluation node that reads the picture's description and sends the prompt back to the Interception, so the learners build the evaluating loop themselves and read its judgements round by round. No classroom example of the framework has learners build the apparatus that evaluates a model.

**Non-fits**: Engage 1, 4, 5, 7, Manage 1, 2, Shape 1, 3, 4, Create 1, 4.
