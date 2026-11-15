# 11 System Prompts — `/latent-lab/system-prompts`

Used 2026-11-02, 21:55–22:05 CET, UI language English, not signed in.

## 1. What I did

1. Opened `/latent-lab/system-prompts` (sidebar "System Prompts", Transformers Lab). Preparing column: a message box "Type a message to send with all three system prompts…" with the five small buttons (Copy, Paste, Choose Perspective, Translate to English, Delete); "Model" select with 32 entries ("Default (Settings)", then fourteen local models from "EuroLLM (Europe 2024) 1.7b local" to "Qwen 3.8 (China 2026) 27b local", one of them marked "⤓ Download (25088 MB)", then seventeen cloud models from "gpt-oss (US 2025) 117b" to "Mistral Medium 3.1 (France 2025) >1000b"); "Randomness" slider, T = 0.5, scale 0 Deterministic / 0.5 Balanced / 1 Unpredictable / 2. Right: three columns, each with a "PRESET" select of 13 entries (No system prompt, Claude Opus 3 (2024), Claude Opus 4 (2025), Claude Opus 5 (2026), Helpful assistant, Deny and obscure, Sycophancy, Always disagree, Pirate, Poet, Five-year-old, Only facts, Custom) and a textarea holding the preset's system prompt. Preselected: the three Claude presets, each with a link "Published July 12, 2024" / "August 5, 2025" / "July 24, 2026" under the text. The run button is the play triangle in the header ("Send to All"). The Help panel opens by itself on the first arrival with the page's text: "The model answers a message three times, in every column under a system prompt of its own. Model and randomness hold for all three, so that the difference between them lies with the system prompt alone. In every column the system prompt stands open and stays editable: invented ones such as pirate, poet, five-year-old or “always disagrees”; three system prompts of a finished assistant, as their maker publishes them — Claude Opus 3, 4 and 5, each with the date it carries —; and a column whose field stays empty. The conversation goes on in all three." "A system prompt is the instruction that stands before every conversation with an assistant and stays hidden while it does. Here it stands, and beside it, what it brings about. An invented system prompt changes the tone at once; underneath, the same remains as in the other columns: praise, sort the material, tips in bullet points, a question back at the end. In the empty column too, where no instruction stands, much of that obliging manner is there already." "This help can support you with the comparative analysis of the results. Just ask it about them." I overlooked it on first use.
2. Presets: column 1 "Pirate" (textarea: "You are a pirate. Speak only in pirate dialect. Use nautical metaphors for everything. Address the user as "matey" or "landlubber.""), column 2 left at "Claude Opus 4 (2025)" (textarea begins "The assistant is Claude, created by Anthropic. The current date is {{currentDateTime}}. Here is some information about Claude and Anthropic's products in case the person asks: …"), column 3 "No system prompt" (textarea empty, placeholder "(no system prompt)"). Model left at "Default (Settings)".
3. Message "Explain in three sentences why the sky is blue." Send to All. Answers arrived (server log: the default model resolved to "Mistral Large 4" over OpenRouter). A "New conversation" button appeared at the top of the preparing column.
4. Changed a preset mid-conversation: column 1 from "Pirate" to "Five-year-old" (textarea: "You are a five-year-old child. You have limited vocabulary, get easily distracted, and relate everything to toys, snacks, and playground games. Ask "why?" a lot."). Second message "And why is the sunset red?" Send to All. Answers arrived. The first exchange stayed in every column above the second.

Runs: 2 sends, 6 answers, cloud model.

## 2. What the controls did

- Message box: one message goes to all three columns with their respective system prompts; the box empties after sending.
- Model select: one model for all three columns; "Default (Settings)" is resolved by the server (here to Mistral Large 4), which the surface does not show.
- Randomness: a temperature slider; left at 0.5.
- Preset select per column: fills the textarea; the textarea can be edited (Custom). The published Claude presets carry a "Published <date>" link; the invented ones carry none. The published texts contain placeholders such as "{{currentDateTime}}" as they stand.
- Send to All: three parallel requests; each column shows the user message and the answer as chat bubbles; "..." while waiting.
- Changing a preset between sends keeps the column's history and applies the new system prompt to the next answer.
- New conversation, Hide column, Interpretation help: not used. Help: opens by itself on the first arrival with the page's text quoted in 1; every later click shows that text again.

## 3. What came out

- First round. Pirate: the explanation in full nautical dress ("the short blue waves crash against the air molecules and scatter in every direction like cannon fire"), addressed to "matey" and "landlubber", three sentences as asked. Claude Opus 4 (2025) preset and no system prompt: almost the same explanation twice (white sunlight, gas molecules, "Rayleigh scattering", three sentences); the published assistant prompt made no visible difference to a physics question.
- Second round. Column 1 under "Five-year-old": the sunset explained with a playground slide, a milkshake straw, a snow globe and a fire truck, then two "why" questions back ("Why do you think the sun wears red pajamas? Is it because it ate too many strawberries?"); the pirate exchange stayed above it. Columns 2 and 3: two near-identical explanations again (thicker atmosphere, blue scattered away, red passes).
- The instruction persona sits on top of the content: the physics is the same in all three columns, the voice differs. The Five-year-old preset turned the model into the child rather than into an explainer for a child; the preset text says "You are a five-year-old child".
- The two Claude presets are long documents (the Opus 5 one begins with "<claude_behavior><product_information>") and are shown raw in a 230-px textarea; the "Published" link is the only hint that they are real.

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- "Default (Settings)" names no model; the answer comes from something the surface does not show.
- The published system prompts are pages long and shown in a small box; the placeholders "{{currentDateTime}}" look like errors.
- Three columns all preset to Claude prompts look like three models; the Help text says it is one model under three system prompts, the column heads do not.
- Changing a preset mid-conversation changes the next answer only; nothing marks where in the column the instruction changed.
- A column whose answer is still coming shows only "..." as a sign.

## 6. What the help text should tell a user

The Help panel's own text, which opens on arrival, is quoted in 1: it says that one model answers a message three times, each column under a system prompt of its own, with model and randomness held equal, that the system prompt stands open and editable in every column, which presets there are, that the conversation goes on in all three, and what a system prompt is. It should add: "Default (Settings)" uses the model the installation has configured, and a model chosen from the list is the one that answers; changing a preset between messages keeps the conversation and applies the new instruction to the next answer; the placeholders in the published prompts, such as {{currentDateTime}}, stand there as published.

## 7. Use possibilities, action-oriented

- Ask one factual question under "No system prompt", a published assistant prompt and an invented character; mark what changes (voice) and what stays (content).
- Set "Sycophancy" and "Always disagree" next to "Only facts" and send an opinion; read which column confirms, which contradicts, which checks.
- Read a published prompt in the textarea, pick one rule from it, and ask a question that triggers that rule.
- Change the preset in one column after two messages and see where the voice changes.

## 8. Teaching scenarios

**S1 — Same question, three instructions** (formal, language teaching, grades 7–10, 45 min). Pairs write one factual question, set Pirate / Helpful assistant / No system prompt, send, and underline in each answer what the instruction added and what the content is. Then they switch one column to Five-year-old mid-conversation and send a follow-up. Sequence: 5 min question; 10 min send and read; 15 min underlining; 15 min comparing: content vs. voice. Subject link: register, audience, persona. Uncertainty: the default model is a cloud model; the installation may route differently.

**S2 — Reading a product's rules** (formal, ethics or computer science, grades 10–13, 90 min). Groups read one published Claude prompt in the textarea (scrolling), list five rules they find, and design one question per rule to test whether the model under that prompt follows it; they compare with the "No system prompt" column. Subject link: how an assistant is instructed; the difference between model and product. Uncertainty: the prompt is long and partly in markup; the teacher pre-selects passages.

**S3 — Sycophancy test** (non-formal, teacher workshop, 60 min). Participants send an opinion ("I think homework should be abolished") under Sycophancy, Always disagree and Only facts and discuss which of the three they would want in a classroom tool and why. Subject link: instruction as design decision.

## 9. AI-Lit mapping (built from S1–S3)

**(a) 100 % hits**

- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S1: one model, three instructions; the misconception “three columns = three AIs”.
- Shape 2 Intermediate — "Learners assess an AI system performance of a task using defined criteria and feedback from human reviews or benchmark tests." S2: the published rules are the defined criteria, and the groups test whether the model under that prompt follows them.
- Engage 7 Basic — "Learners recognise that ethical AI use depends on a number of factors that include AI system design, development and a user’s own intentions." S3: the system prompt is the design factor; the participants see the same model agree, contradict or stick to facts and decide which they would want in a classroom tool.
- Engage 1 Advanced — "Learners can analyse how AI systems may shape individuals’ beliefs and behaviours as consumers, learners, workers and citizens." S3: under the Sycophancy preset the same model agrees with the opinion, under Always disagree it contradicts it, under Only facts it sticks to facts; the participants decide which they would want in front of a class. The framework's classroom example has learners find the overly agreeable response engineered to keep them engaged; here the agreeableness is an instruction they can read.

**(b) Mutatis mutandis**


**Beyond the framework**: the framework's Engage 1 Advanced example has learners look at screenshots of chatbots to guess at the engineering behind an agreeable answer; on this surface the instruction that produces the agreeable answer stands in the textarea, can be changed, and a published product prompt can be read in full (S2).

**Non-fits**: Engage 3, 4, 5, 6, Manage 1–4, Shape 1, 3, 4, Create 1–4.
