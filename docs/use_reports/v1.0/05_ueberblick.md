# 05 Overview — `/latent-lab/overview`

Used 2026-11-02, 20:37–20:41 CET, UI language English, not signed in.

## 1. What I did

1. Opened `/latent-lab/overview`. Header "Overview map of the Latent Lab". Left: the Latent Lab sidebar with six groups (CULTURAL KNOWLEDGE & STEREOTYPES: Stereotype Analysis, Model Comparison, Mean Images, Language Understanding, Image Understanding, Voice Comparison; DIFFUSION LAB: Encoder Fusion, Enc. Fus. Workbench, Dimension Explorer, Concept Algebra, Denoising Archaeology, Attention Cartography, Composable Diffusion; TRANSFORMERS LAB: System Prompts, Model Comparison, Tokenizer, Bias Research 1, Bias Research 2, Representation Engineering; CROSSMODAL LAB: Latent Audio Synth, Re-enactment, MMAudio, ImageBind Guidance; PROMPT INTERCEPTION LAB: Language Model Comparison, Interception Scope, Aesthetic Poles; LORA TRAINING: LoRA Training, LoRA Explorer). Each entry carries one or two small icons (A = text, picture, note = sound). The Help panel opens by itself on the first arrival with the page's text: "On this overview page you are already looking inside AI models — diffusion and transformer architectures that produce images, sounds and texts, and ways of carrying one over into another." "Click the boxes and find out at which places this page invites you to experiment!" I overlooked it on first use.
2. The map: three columns with heading and tagline. "Diffusion — Change how images & media come about in an AI!", four boxes: Prompt (with the sentence "A house stands in a landscape, surrounded by farmland, nature and animals. Some people can be seen."), Embedding Process, Denoiser and Scheduler, VAE / Variational Auto Encoder; two dashed frames label "latent space" and "conditioning". "Transformer — Find out how text AIs work and whether they pass on prejudices!", four boxes: Prompt, Tokenization and embedding, Attention, Sampling; a dashed frame "embedding space". "Crossmodal routes — Chains of several AIs", three boxes: Image to text, Image to sound, Sound to text to sound. Each box has a small animated diagram with a green dot.
3. Pressed into "Embedding Process" (Diffusion). A panel opened over the map, with "Close": the sentence on the left; three encoders CLIP-L, CLIP-G, T5 each showing the first tokens (a, house, stands, in, a, ","); on the right "one vector per token" with rows farm / l / and and five numbers each, and "one vector for the whole sentence". Two sentences: "Several small AI models (encoders) break the prompt into small pieces, so-called tokens." "Each encoder links every token to a long row of numbers (between 77 and 512 vectors with 768–4096 numbers each)." While the panel was open, the sidebar highlighted four instruments in green: Encoder Fusion, Enc. Fus. Workbench, Dimension Explorer, Concept Algebra.
4. Pressed into "Attention" (Transformer). Panel: a token row "A ␣house ␣stands … ␣surrounded … ␣far mland ." with arcs ("what stands there?", "what is surrounded?", "attention: the thicker the arc, the more important"), "field of view: up to 40,960 tokens at once", the number series of "mland" (+0.0405 +0.0002 +0.0211 +0.0171 −0.0184 −0.0068 … 2,560 numbers), "36 times, layer by layer", "the intermediate state from layer 10 on: farms"; a comparison box with two "bank" sentences (picnic on the bank of the river / the bank raises its interest rates) and their differing numbers after attention. Five sentences of explanation ending: "The intermediate state 'farms' and the 36 layers were measured on 2026-08-24. The arcs and the bank rows are exemplary." and a note: "All the numbers here are measured on one AI model: Qwen3-4B. A different model cuts differently and has different numbers." Sidebar highlight: Representation Engineering.
5. Pressed into "Image to sound" (Crossmodal). Panel: a picture icon, two arrows to two wave icons, "one AI model makes a sound from the picture", "another steers the sound while it is generated". Sidebar highlight: MMAudio, ImageBind Guidance.
6. A short click opens the same panel as a long press (tried on VAE: "a tensor of 16 matrices … The many pieces of data, e.g. about content, contrast, colours, textures, are combined into a media product humans can perceive. picture / sound / video / 3D").
7. "Note what the taglines say while you click": the three taglines under the column headings did not change at any point; they are static. Nothing else on the surface changed while pressing except the panel and the sidebar highlight.

Runs: none (no generation on this surface).

## 2. What the controls did

- Click or press on a box: opens its detail panel over the map; "Close" or Escape closes it. The sidebar highlights the instruments that belong to the station.
- Sidebar entries: navigate to the instruments.
- Help: opens by itself on the first arrival with the page's text quoted in 1; every later click shows that text again. Sidebar toggle button top left.
- The small green dots in the box diagrams animate on their own; they are not controls.

## 3. What came out

- A map that places the 29 instruments of the sidebar on a process diagram with eleven stations. The link between station and instruments is the sidebar highlight, which appears only while a panel is open and is easy to miss (the sidebar is on the far left, the panel in the middle).
- The Attention detail carries measured numbers with a date and a model name (Qwen3-4B, 2026-08-24); the Embedding detail carries numbers without a source ("0.42 −0.18 0.91 …", "between 77 and 512 vectors"); the VAE detail says "a tensor of 16 matrices" without saying for which model.
- The Diffusion tagline is an imperative with an exclamation mark; the Transformer tagline promises "whether they pass on prejudices", which only two of its six instruments (Bias Research 1 and 2) address; "Crossmodal routes — Chains of several AIs" is a noun phrase.
- The "Crossmodal routes" column has no Prompt box and no dashed frame; "Sound to text to sound" appears as a box but its panel was not opened (not in the script).

## 4. How long it took

Not measurable. A workshop replay backend on the same machine, running since 2026-11-01, fed the shared ComfyUI queue with 27B language-model jobs throughout; every run here waited behind it, so the durations I measured say nothing about the instrument.

## 5. Where a newcomer stumbles

- The sidebar highlight is the only link from a station to an instrument, and it is far from the panel; a reader of the panel does not see it.
- Numbers without a source in the Embedding and VAE panels sit next to numbers with a date and model in the Attention panel.
- The sentence in the Prompt box ("A house stands in a landscape…") is used in the Diffusion panels but not in the Transformer column's own Prompt box, which is empty of text.

## 6. What the help text should tell a user

The Help panel's own text, which opens on arrival, is quoted in 1: it says that the page looks inside AI models, names the diffusion and transformer architectures and the ways of carrying one over into another, and says to click the boxes. It should add: every box is a station, and its detail names the instruments that work at that station, which light up in the sidebar on the left while the detail is open. The numbers in the details are examples; where a panel names a model and a date, they were measured on that model, and where it names none, they are illustrative.

## 7. Use possibilities, action-oriented

- Open the three Prompt-to-output chains in order, station by station, before touching an instrument; note which sidebar entries light up and go to one of them next.
- Use the Attention panel's "bank" example as the entry to Representation Engineering or the Tokenizer.
- Use the Embedding panel's three encoders as the entry to Encoder Fusion.
- Print the map (screenshot) as the room's poster; it names every instrument's place.
- Take one station's panel as the blueprint for an artwork about that element: the token row with its arcs and the 2,560 numbers of one token (Attention), the three encoders and their rows of numbers (Embedding Process), the 16 matrices that become a picture, sound, video or 3D (VAE); the instruments that light up in the sidebar are where the material for the work is made.
- Mark the dashed frames "latent space" and "embedding space" as the station for a work on high-dimensional (non-)images: what the panels show as rows of numbers before anything can be seen or heard.

## 8. Teaching scenarios

**S1 — Reading the map first** (formal, computer science, grades 9–11, 45 min). The class opens the overview on the board; the teacher clicks the four Diffusion stations one after the other and the class writes one sentence per station in their own words. Then pairs open one Transformer station each and present it. Sequence: 15 min Diffusion column together; 15 min pairs on Transformer stations; 15 min presentations and the question which instrument they want to use next week. Subject link: representation of data, models.

**S2 — Which instrument for which question?** (non-formal, teacher workshop, 90 min). Teachers formulate a question they have about AI ("where does the prejudice get in?", "why does a model misspell a word in the picture?"), find the station on the map, open it, and note the highlighted instruments. Sequence: 20 min questions on cards; 40 min map work in pairs; 30 min each pair names the instrument they will try and why. Subject link: lesson planning.

**S3 — From flow-map to art** (formal/non-formal, project week day 1, grades 10–13). The map is used as an inspirational blueprint/orientation for artworks that inform and discuss structural elements of genAI technologies (e.g. tokienizer, embedding, denoising, or the nature of latent spaces and high-dimensional (non-) images. Groups mark the station they will work at for the week and open its panel. Subject link: artistic research/artistic exploration.

## 9. AI-Lit mapping (built from S1–S3)

**(a) 100 % hits**

- Engage 2 Intermediate — "Learners accurately describe how a specific AI tool carries out a task in order to address commonly-held misconceptions about how AI works." S1: one sentence per station in their own words. S3: each artwork informs about one structural element (tokenizer, embedding, denoising, latent space), and the station's panel is what the work's statement about that element is read against.
- Manage 1 Basic — "Learners identify a variety of AI systems and the tasks they are designed to support." S2: the teachers find the station for their question and note which instruments light up for it; S1: the sidebar’s six groups with their instruments. S3: the station a group marks names the instruments it will work with for the week.
- Shape 1 Basic — "Learners identify what different AI systems are designed to do." S1 and S2: each station’s panel says what the instruments at that station do, and the learners note which instrument is for which station. S3: the groups choose their station by what its instruments do.

**(b) Mutatis mutandis**

- Create 1 Basic — "Learners explore how different AI tools can expand their thinking or spark new ideas." Modification: in S3 the spark comes from the map's drawing of the models' insides (the panels' diagrams and numbers), not from using the tools; the tools follow during the week.
- Engage 2 Advanced — "Learners explain how different AI systems work using language that does not attribute human traits or abilities, knowing that their phrasing shapes understanding." Modification: in S3 the artworks inform and discuss a structural element in the means of art, not in language; that the means shape the understanding of the element is what the discussion of the works is about.
- Shape 1 Intermediate — "Learners describe the purpose, intended users and basic constraints of a specific AI tool." Modification: the panel a group opens in S3 describes a station of the model and its constraints (77–512 vectors, a field of view of 40,960 tokens, 16 matrices), not a tool with intended users.

**Beyond the framework**: the framework's knowledge statement 1.1 has AI systems "combine step-by-step procedures with statistical inferences (e.g. weights and biases)"; the map's panels show the parts those words stand for (the token rows, the three encoders, the 16 matrices of the latent), and S3's artworks take one of these parts as their subject. The framework has no expectation that reaches the parts.

**Non-fits**: Engage 1, 3, 4, 5, 6, 7, Manage 2, 3, 4, Shape 2, 3, 4, Create 2, 3, 4 — the map generates nothing and decides nothing; the artworks of S3 are made at the instruments, which the other reports map.
