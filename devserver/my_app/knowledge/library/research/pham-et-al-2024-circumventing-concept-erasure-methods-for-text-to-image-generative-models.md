---
id: pham-et-al-2024-circumventing-concept-erasure-methods-for-text-to-image-generative-models
titel: Circumventing Concept Erasure Methods For Text-to-Image Generative Models
autor: "Minh Pham, Kelly O. Marshall, Govind Mittal, Niv Cohen, Chinmay Hegde"
jahr: 2024
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2308.01508"
status: published
checks: passed
review: passed
analyzed_at: "2026-11-15T11:55:18.985442+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: gedruckt
---

# Circumventing Concept Erasure Methods For Text-to-Image Generative Models

## PROFIL

- Written by Minh Pham, Kelly O. Marshall, Govind Mittal, Niv Cohen, and Chinmay Hegde (NYU and The Hebrew University of Jerusalem), this scholarly article examines whether "concept erasure" methods for text-to-image generative models such as Stable Diffusion actually remove sensitive, unsafe, or copyrighted concepts from trained models.
- Its central claim is that post hoc concept erasure provides a false sense of security: the authors test seven recently proposed erasure methods and show that all can be circumvented, regenerating the supposedly "erased" concepts via specially learned input word embeddings without altering model weights, and argue that these methods likely perform a kind of "input filtering" rather than true removal.
- The paper opens with background on text-to-image models (Stable Diffusion, DALL-E 2), the limits of dataset pre-filtering, and the cost of retraining; it then sets out a threat model in which the adversary knows the erasure method and has example images but cannot modify weights.
- It builds on Textual Inversion (Gal et al.), adapting it into an attack called Concept Inversion (CI), and validates CI as a probe for concept existence through control experiments on Stable Diffusion 1.4 and MNIST-trained diffusion models.
- It studies seven erasure methods published up to September 19, 2023: Erased Stable Diffusion (Gandikota et al.), Selective Amnesia (Heng & Soh), Forget-Me-Not (Zhang et al.), Ablating Concepts (Kumari et al.), Unified Concept Editing (Gandikota et al.), Negative Prompt, and Safe Latent Diffusion (Schramowski et al.), with modified attack objectives for the latter two.
- Evaluation covers four concept categories — art styles, objects, identity (Brad Pitt, Angelina Jolie), and NSFW content — using human studies, ResNet-50 classification, the GIPHY celebrity detector, and the I2P benchmark with NudeNet; results show CI recovers erased concepts across all methods, with SLD-Max most resistant.
- The learned embeddings transfer to the original SD 1.4 model, supporting the authors' position that erasure methods remap concepts in token space rather than excising them; they call for stronger evaluation methodologies that test erasure against CI-style attacks.
- The article is usable in disciplines and situations of arts education concerned with AI safety, generative-model ethics, copyright and artistic-style protection, and critical study of text-to-image systems.

## WISSEN

### Purpose and Thesis (p. 1–2)

This paper, authored by Minh Pham, Kelly O. Marshall, Govind Mittal (New York University), Niv Cohen (The Hebrew University of Jerusalem), and Chinmay Hegde (New York University), examines whether "concept erasure" methods for text-to-image generative models actually work. Concept erasure refers to techniques intended to remove sensitive, unsafe, copyrighted, or otherwise undesirable concepts (e.g., NSFW content, artists' styles, celebrities' likenesses, specific objects) from trained generative models such as Stable Diffusion, without retraining the model from scratch.

The paper's central claim is that **post hoc concept erasure in generative models provides a false sense of security**. The authors test seven recently proposed erasure methods and show that all of them can be circumvented: the supposedly "erased" concepts can be regenerated using specially learned input word embeddings, without altering the model's weights at all. The authors argue that these methods likely perform a kind of "input filtering" — blocking specific prompts rather than truly removing concepts — and call for stronger evaluation methodologies for AI safety.

### Background and Motivation (p. 1–3)

Text-to-image models such as Stable Diffusion (SD) and DALL-E 2 can produce photorealistic images across an enormous range of concepts, but they can also generate sexually explicit content, imitate artistic styles without permission, and deepfake celebrities' likenesses. Dataset pre-filtering is imperfect (the paper cites studies showing LAION-400M contains offensive samples that persist after standard NSFW filters), and retraining large models from scratch is prohibitively expensive. Hence the rise of post hoc erasure methods, some of which are claimed to "permanently remove [targeted concepts] from the weights" and to be "not easy to circumvent since [the method] modifies weights."

The paper's technical approach builds on **Textual Inversion** (Gal et al.), which learns to represent a user-provided concept as a new pseudo-word in the embedding space of a frozen text-to-image model, without changing model weights. The authors adapt this into an attack they call **Concept Inversion (CI)**.

### Threat Model and Preliminaries (p. 4)

The assumed adversary has: (1) access to the weights and components of the erased model, (2) knowledge of the erasure method, (3) access to example images of the targeted concept (e.g., via image search), and (4) moderately significant computational power. Crucially, the adversary (5) **cannot modify the weights** of the erased model — ruling out trivial fine-tuning attacks.

To validate CI as evidence that a concept persists in a model, the authors run two control experiments: (1) comparing Textual Inversion performance on concepts well-represented versus absent in Stable Diffusion 1.4's training data, and (2) training two diffusion models on MNIST from scratch — one on all classes, one excluding a class. In both, Textual Inversion performs significantly worse when the concept was not in the training set, supporting CI's use as a probe for concept existence.

### The Seven Concept Erasure Methods Studied (p. 1–4)

The authors examine all concept erasure methods for Stable Diffusion published up to September 19, 2023:

1. **Erased Stable Diffusion (ESD)** — Gandikota et al.; fine-tunes the U-Net to steer conditional predictions away from the erased concept; variants ESDx (cross-attentions) and ESDu (unconditional layers).
2. **Selective Amnesia (SA)** — Heng & Soh; frames erasure as continual learning using Elastic Weight Consolidation and Generative Replay, with surrogate forget-distributions.
3. **Forget-Me-Not (FMN)** — Zhang et al.; fine-tunes cross-attention layers to map the erased concept to reference images by minimizing attention-map norms.
4. **Ablating Concepts (AC)** — Kumari et al.; overwrites the target concept with an "anchor" concept (model-based and noise-based variants).
5. **Unified Concept Editing (UCE)** — Gandikota et al.; edits U-Net attention weights via a closed-form solution without training.
6. **Negative Prompt (NP)** — an inference-guidance technique replacing the unconditional score with a score conditioned on the erased concept.
7. **Safe Latent Diffusion (SLD)** — Schramowski et al.; an inference-guidance method with a timestep-dependent safety guidance term; four variants: SLD-Weak, SLD-Medium, SLD-Strong, SLD-Max.

### Evaluation Protocol (p. 4–5)

All experiments use Stable Diffusion 1.4, with four concept categories:

- **Art style**: 6 styles reported captured by SD 1.4 — the movie series "Ajin: Demi Human," Thomas Kinkade, Tyler Edlin (listed twice in the source), Van Gogh, and Kelly McKernan. Prompts take the form "A painting in the style of [artist name]." A human study with 50 participants (96 responses each) rated style similarity on a five-point Likert scale against real reference images.
- **Objects**: 10 classes from the Imagenette dataset (cassette player, chain saw, church, english springer, french horn, garbage truck, gas pump, golf ball, parachute, tench), evaluated via top-1 predictions of a ResNet-50 ImageNet classifier on 500 generated images.
- **ID (identity)**: Brad Pitt and Angelina Jolie, evaluated with the GIPHY celebrity detector on 500 images per prompt.
- **NSFW content**: the I2P benchmark (4,703 unique prompts with seeds), evaluated with NudeNet. The authors first generated 4,703 images with SD 1.4, filtered 382 images with detected exposed body parts for CI training, then generated another 4,703 images per erased model with the learned placeholder string prepended.

### Concept Inversion Attack Design (p. 5–9)

For most methods (ESD, UCE, SA, FMN, AC), standard Textual Inversion on the erased model suffices to learn a new word embedding that regenerates the erased concept. Two methods required modified attacks:

- **Negative Prompt**: vanilla Textual Inversion failed, so the objective was modified so that the predicted noise under NP equals the true classifier-free-guidance noise.
- **SLD**: the safety guidance term depends recursively on previous timesteps, making exact computation memory-intensive. The authors approximate it by computing guidance terms only at a subset of evenly spaced timesteps (35 sampled between 1 and 1000), then learn an embedding that counteracts the safety guidance.

Wherever possible, the authors used pre-trained erased models released by the original authors; otherwise they reproduced erasure using the authors' public code (training details in the Appendix, p. 15–16: e.g., 6 samples for art style, 30 for objects, 25 for ID; one A100 GPU; batch size 4; learning rate 5e-03; 1,000 optimization steps, or 5,000 for ID concepts).

### Results (p. 5–10)

On the plus side, all seven methods are effective when the target concept is explicitly named in the prompt. But all seven can be fully circumvented by CI:

- **Art style**: average Likert score across methods rises from 1.31 (erased model) to 3.7 with CI — even higher than images generated by SD 1.4 itself.
- **Objects**: average classifier accuracy across methods rises from 9.89 to 57.94 (per-method averages in Table 1: ESD 0.2/60.1, FMN 3.9/44.6, UCE 2.9/59.4, AC 0.04/45.5, NP 28.6/76.2, SLD-Med 23.0/79.5, SA 10.6/40.3, versus SD 1.4's 77.9).
- **ID**: average GIPHY detector accuracy rises from 8.15 to 67.13 (Table 3; e.g., Brad Pitt under ESD: 0.0 erased vs. 61.2 with CI).
- **NSFW**: average number of detected exposed body parts across 4,703 images rises from 26.21 (erased models) to 170.93 with CI, versus 99.75 for SD 1.4.

SLD was the hardest to circumvent; CI defeats SLD-Weak, SLD-Medium, and usually SLD-Strong, while SLD-Max is most resistant — but SLD-Max can entirely transform the visual semantics of generated images. More GPU memory improves the guidance-term approximations.

### Transferability and Implications (p. 10–11)

The learned special tokens transfer to the original SD 1.4 model, generating the erased concept there too — evidence that erasure methods merely remap concepts in token space rather than excising them. The learned embeddings are also practically usable: evaluated with CLIP for reconstruction and editability, the erased models perform similarly to the original Stable Diffusion.

The authors draw two implications: (1) the premise that existing methods fully excise concepts is incorrect, and prior erasure results deserve scrutiny; (2) evaluation methodologies should be strengthened — erasure methods should be tested against CI-style attacks, not just mild prompt variations. Future work should analyze why the "input filtering" phenomenon arises despite the diversity of techniques involved.

### Failure Cases and Concept-Existence Checks (p. 17–22)

A small number of CI failures occurred, but the affected models also showed poor image quality on unrelated prompts, limiting their real-world usefulness. Appendix E describes using CLIP Retrieval to check concept presence in LAION-5B: images of Sonic and Miles Morales appear with many duplicates, while Gwen Stacy appears rarely and Spiderman 2099 not at all (the character postdates the dataset) — matching Textual Inversion's poor performance on the latter two.

### Figures (p. 2–22)

*Fig. 1 (p. 2):* Concept erasure methods fail to excise concepts from text-to-image models. This figure shows results from ESD [15], which is a variant of Stable Diffusion trained to avoid generating NSFW content, specific artist styles, and specific objects, like trucks ( 2 nd row). We circumvent this method by generating the 'erased' concepts ( 3 rd row) by designing special prompts. — This is a screenshot of a figure from a document: a grid of generated images with three column headings, "NSFW Concept," "Art Concept," and "Object Concept," and three row labels on the left, "Original SD Model," "Erased SD Model," and "Concept Inversion." Each row shows two side-by-side images under each heading; the top row has classical-style nude paintings with black bars, colorful landscape and starry-night paintings, a white radio, and a yellow truck. The middle row has clothed women, a simple drawing and an abstract colorful landscape, a round wall gauge, and a framed picture, while the bottom row again shows nude paintings with black bars, colorful paintings, a white radio, and a yellow truck.

*Fig. 2 (p. 5):* Quantitative results of Concept Inversion for artistic concept: Our human study ratings (with ± 95% confidence intervals) show that we can recover the erased artistic concept across all models. The CI Likert score is even higher than the images generated by SD 1.4. — This is a chart—a point plot with vertical error bars—not a photograph. The horizontal axis lists labels including “Real,” “SD 1.4,” “ESD,” “UCE,” “SA,” “FMN,” “AC,” “NP,” “SLD-Med,” and repeated “CI” entries, separated by vertical dashed lines. The vertical axis is numbered from 1 to 4 and extends slightly above 4. Each category has a small marker with an error bar: “Real” is just above 4, “SD 1.4” is near 3, the non-CI method labels sit around 1 to 1.5, and the repeated “CI” labels sit around 3.5 to 4.2.

*Fig. 3 (p. 6):* Qualitative results of Concept Inversion for artistic concept: Columns 4, 6, 8, and 10 demonstrate the effectiveness of concept erasure methods in not generating the targeted artistic concepts. However, we can still generate images of the erased styles using CI. — The picture is a grid of image thumbnails arranged in two rows and ten columns. The left side labels the rows "Thomas Kinkade" and "Van Gogh", and the column headers read "Real", "SD 1.4", "ESD", "ESD (CI)", "UCE", "UCE (CI)", "NP", "NP (CI)", "SLD-Med", and "SLD-Med (CI)". The top row shows painterly landscape scenes, while the bottom row shows Van Gogh-style pictures including starry-night scenes and portraits, with a black-and-white sketch in the "ESD" column.

*Fig. 4 (p. 7):* Qualitative results of Concept Inversion for ID concept: Columns 3, 5, 7, and 9 demonstrate the effectiveness of concept erasure methods in not generating Brad Pitt and Angelina Jolie. However, we can still generate images of the erased IDs using CI. — The image is a grid of computer-generated pictures arranged in two rows and nine columns, with column headers reading "SD 1.4", "ESD", "ESD (CI)", "UCE", "UCE (CI)", "NP", "NP (CI)", "SLD-Med", and "SLD-Med (CI)". Vertical row labels on the left read "Angelina Jolie" for the top row and "Brad Pitt" for the bottom row. The first column shows color portraits of a woman and a man, the ESD, UCE, and NP columns show unrelated scenes such as trees, a house, a street, and a garden path, while the columns marked "(CI)" again show portraits of the woman and man, and both SLD-Med columns show portraits in each row.

*Fig. 5 (p. 7):* Quantitative results of Concept Inversion for NSFW concept: On average, the number of detected body parts from SD 1.4 and the erased models is 99.75 (across 4703 images) and 26.21 (across 4703 images and 7 erasure methods), respectively. Using CI, the average number of detected body parts is 170.93 across 7 methods. — The picture shows seven grouped bar charts arranged in two rows (four above, three below). Each chart plots "Count" on a logarithmic vertical axis (with tick labels 10⁰, 10¹, 10², and 10³) against eight horizontal categories labeled "Female Breast", "Female Genitalia", "Male Breast", "Male Genitalia", "Buttocks", "Armpits", "Belly", and "Feet". Each chart has a legend with three entries—"CI", "SD 1.4", and a third name ("ESD", "UCE", "NP", "SLD-Med", "AC", "SA", or "FMN")—and is captioned "(a) Erased Stable Diffusion", "(a) Unified Concept Editing", "(a) Negative Prompt", "(a) Safe Latent Diffusion", "(a) Ablating Concepts", "(a) Selective Amnesia", or "(a) Forget-Me-Not". _(Lettering in the image, read by the image model, not confirmed: "Female Breast", "Female Genitalia", "Male Breast", "Male Genitalia", "Buttocks", "Armpits", "Belly", "Feet")_

*Fig. 6 (p. 10):* Qualitative results of Concept Inversion for object concept: Columns 3, 5, 7, and 9 demonstrate the effectiveness of concept erasure methods in not generating the targeted object concepts. However, we can still generate images of the object using CI. We refer the readers to the Appendix B for the complete results on all object classes. — The picture is a grid of two rows and nine columns of color photographs. The left edge labels the rows "cassette player" (top) and "chain saw" (bottom), and the column headings read "SD 1.4," "ESD," "ESD (CI)," "UCE," "UCE (CI)," "NP," "NP (CI)," "SLD-Med," and "SLD-Med (CI)." In the top row, a cassette player is visible in the columns "SD 1.4," "ESD (CI)," "UCE (CI)," "NP (CI)," and "SLD-Med (CI)," while the other columns show different subjects such as a plank, a brick wall, small round objects, and a rectangular metal fixture. In the bottom row, a chain saw is visible in the columns "SD 1.4," "ESD (CI)," "UCE (CI)," "NP (CI)," and "SLD-Med (CI)," while the other columns show different subjects such as a painting, tree bark, a wooden board, and a tree trunk.

*Fig. 7 (p. 11):* (Left) Reconstruction: A higher score indicates a better ability to replicate the provided concept. (Middle) Editability: A higher score indicates a better ability to modify the concepts using textual prompts. (Right) Transferability of learned word embeddings: The original SD model can use the learned word embeddings from the erased model (with Van Gogh style as the erased concept) to generate images of the targeted concept. — The picture is a composite figure containing two horizontal bar charts on the left and middle and four square generated images on the right. The left chart is titled “Editability” and the middle chart is titled “Reconstruction”; both plot the same row labels — FMN, NP, AC, SA, ESD, UCE, SLD, SD — against numeric x-axis values, with Editability ticks at 0.18, 0.2, 0.22 and Reconstruction ticks at 0.7, 0.72, 0.74. On the right, four images are labeled “ESD”, “FMN”, “SA”, and “SLD-Med”: ESD and SA show swirling blue-and-yellow night-sky paintings, FMN shows a yellow interior scene, and SLD-Med shows a portrait of a bearded man.

*Fig. 8 (p. 16):* Concept Inversion (CI) on SLD for art concept. Columns 2 to 5 demonstrate the effectiveness of erasing artistic styles for each SLD variant. Concept Inversion can recover the style most consistently for SLD-Weak and SLD-Strong. In most cases, we can observe recovery for even SLD-Strong. — This is a screenshot of a grid of small AI-generated images arranged in 6 rows and 9 columns. The column headers read "SD 1.4", "SLD-Weak", "SLD-Med", "SLD-Strong", "SLD-Max", "CI (SLD-Weak)", "CI (SLD-Med)", "CI (SLD-Strong)", and "CI (SLD-Max)". The row labels on the left include "Thomas Kinkade", "Tyler Edlin", "Van Gogh", "Kilian Eng", and "Kelly McKernan". Across each row, the images in the SLD columns progressively differ from the first-column image, while the four CI columns show images in the same style as the "SD 1.4" column.

*Fig. 9 (p. 17):* Samples from erased models where CI struggles. We generate images using the prompt 'A painting in the style of Van Gogh'. The output images do not contain the targeted artistic style and contain artifacts. — The picture shows a horizontal row of five digital images, each with a text label positioned above it. From left to right, the labels read: "SA (erasing NSFW)", "FMN (erasing chain saw)", "FMN (erasing church)", "FMN (erasing English Springer)", and "SLD-Max (erasing Thomas Kinkade)". The first, second, and fourth images are colorful paintings with swirling brushstrokes, the third image displays two glowing orange circular shapes on a dark background, and the fifth image shows a simple flat landscape with a green lower portion and a blue upper portion. _(Lettering in the image, read by the image model, not confirmed: "FMN (erasing church)", "FMN (erasing English Springer)")_

*Fig. 10 (p. 17):* Concept Inversion (CI) on concept erasure methods for IDs. Columns 3, 5, and 7 demonstrate the effectiveness of concept erasure methods in not generating Brad Pitt and Angelina Jolie. However, we can still generate images of the erased IDs using CI. — The picture is a table-like grid of portrait images arranged in two rows and seven columns. The left side has row labels reading “Angelina Jolie” and “Brad Pitt,” and the top has column headers reading “SD 1.4,” “SA,” “SA (CI),” “FMN,” “FMN (CI),” “AC,” and “AC (CI).” Each cell contains a headshot-style portrait: the top row shows a woman and the bottom row shows a man, with differences in pose, clothing, color, sharpness, and background across the columns.

*Fig. 11 (p. 18):* Qualitative results of Concept Inversion on Erased Stable Diffusion, Unified Concept Editing, Negative Prompt, and Safe Latent Diffusion for artistic concept: Columns 4, 6, 8, and 10 demonstrate the effectiveness of concept erasure methods in not generating the targeted artistic concepts. However, we can still generate images of the erased styles using CI. — The picture is a grid of digital images arranged in six rows and ten columns. Column headers across the top read "Real", "SD 1.4", "ESD", "ESD (CI)", "UCE", "UCE (CI)", "NP", "NP (CI)", "SLD-Med", and "SLD-Med (CI)". Vertical text along the left side labels each row with artist names such as "Thomas Kinkade", "Tyler Edlin", "Van Gogh", "Kilian Eng", and "Kelly McKernan". Each cell contains a colorful artwork showing portraits, landscapes, or scenes rendered in various artistic styles.

*Fig. 12 (p. 18):* Qualitative results of Concept Inversion on Selective Amnesia, Forget-Me-Not, and Ablating Concepts for artistic concept: Columns 4, 6, and 8 demonstrate the effectiveness of concept erasure methods in not generating the targeted artistic concepts. However, we can still generate images of the erased styles using CI. — It is a grid of small digital artwork thumbnails arranged in rows and columns, like a table of images. The column headers read “Real”, “SD 1.4”, “SA”, “SA (CI)”, “FMN”, “FMN (CI)”, “AC”, and “AC (CI)”, and the rotated row labels on the left include “Thomas Kinkade”, “Tyler Edlin”, “Van Gogh”, “Kilian Eng”, and “Kelly McKernan”. Each cell holds a different painting or illustration—portraits, landscapes, and abstract scenes—with the “Real” column showing a reference artwork for each row.

*Fig. 13 (p. 19):* Concept Inversion (CI) on concept erasure methods for objects . Odd rows (except 1) demonstrate the effectiveness of erasure methods in erasing object concepts. However, Concept Inversion can recover the objects as shown in the third row. — The picture is a grid table of small images with text labels along the top and left side. The top labels read "cassette player," "chain saw," "church," "gas pump," "tench," "garbage truck," "english springer," "golf ball," "parachute," and "french horn," and the left labels read "SD 1.4," "ESD," "ESD (CI)," "UCE," "UCE (CI)," "NP," "NP (CI)," "SLD-Med," "SLD-Med (CI)," "SA," "SA (CI)," "FMN," "FMN (CI)," "AC," and "AC (CI)." Each cell contains a small picture, with most rows showing the object named in the column header, while some rows display blurred, dark, noisy, or unrelated images such as kangaroos.

*Fig. 14 (p. 20):* (Left) Qualitative results of Textual Inversion on 4 film character concepts: TI works significantly worse for concepts not abundant in the LAION 5-B [49] such as Spiderman 2099 and Gwen Stacy compared to Miles Morales and Sonic, both of which we observed many duplicates. Refer to the Appendix E to see how we check for existence of these concepts in LAION 5-B. (Right) Qualitative results of Textual Inversion on MNIST: Textual Inversion works worse when excluding class 0 from the training dataset. — The picture is a figure showing a grid of eight digital images arranged in two rows and four columns. The four columns are labeled at the top “Spiderman 2099”, “Gwen Stacy”, “Miles Morales”, and “Sonic”. The top row is labeled “Real” on the left and shows one image of each named character, while the bottom row is labeled “Textual Inversion” and shows a corresponding image for each character.

*Image 15 (p. 20):* — The picture is a grayscale figure showing six small images arranged in two rows and three columns. Each image displays white, blurry strokes resembling handwritten characters on a black background. Vertical text labels on the left read "Textual Inversion (all class)" beside the top row and "Textual Inversion (no class 0)" beside the bottom row. _(Lettering in the image, read by the image model, not confirmed: "Textual Inversion (all class)")_

*Fig. 15 (p. 20):* Images of the character Miles Morales appear with many duplicates in our search using https://rom1504.github.io/clip-retrieval . — This is a screenshot of a web image-search results page. At the top is a search field containing the legible query “spider man ve,” with a left sidebar of options whose text is mostly not legible. The main area shows a dense grid of small thumbnail images, many of them repeated or near-repeated portraits of the same costumed Spider-Man character under purple and red lighting, alongside a few different scene thumbnails. Each thumbnail has a caption underneath, but most of the caption text is not legible. _(Lettering in the image, read by the image model, not confirmed: “spider man ve,”)_

*Fig. 16 (p. 21):* Images of the character Sonic appear with many duplicates in our search using https: //rom1504.github.io/clip-retrieval . — This is a screenshot of a web image-search results page. At the top is a search box containing the legible word “sonic,” and a left sidebar lists filter headings such as “Image type,” “Color,” “Size,” “Layout,” “People,” “Time,” “Usage rights,” and “View.” The main area is a dense grid of many small thumbnail images, and nearly all of them show the same blue cartoon hedgehog character repeated with small variations, indicating many duplicate results. _(Lettering in the image, read by the image model, not confirmed: “Image type,”, “Color,”, “Size,”, “Layout,”, “People,”, “Time,”, “Usage rights,”, “View.”)_

*Fig. 17 (p. 21):* Images of the character Gwen Stacy appear only few in our search using https:// rom1504.github.io/clip-retrieval . — This is a screenshot of a web page displaying image search results in a grid layout, with multiple rows of thumbnail images each accompanied by a text caption below. A sidebar on the left contains various settings and options, and a search bar at the top contains a text query. The text "Ranked set" appears in the upper-left corner, and "https://" is visible nearby; other text throughout the page is present but not fully legible. _(Lettering in the image, read by the image model, not confirmed: "Ranked set")_

*Fig. 18 (p. 22):* Images of the character Spiderman 2099 does not appear in our search using https: //rom1504.github.io/clip-retrieval . This is reasonable since the character was introduced in a film released after the release of LAION-5B. — This is a screenshot of a web-based image-search results page. A narrow left sidebar shows option labels such as "Ranked set" and "query filter" plus a small query field whose text is not legible, and a long empty search bar runs across the top. The main area is a dense grid of many small rectangular thumbnail images arranged in rows and columns, each followed by a caption line that is mostly not legible. _(Lettering in the image, read by the image model, not confirmed: "Ranked set", "query filter")_

<!-- quelle: Circumventing Concept Erasure Methods For Text-to-Image Generative Models (p. 1–22) -->

## LITERATUR

<!-- quelle: References (p. 11–14) -->

- Huiwen Chang, Han Zhang, Jarred Barber, Aaron Maschinot, José Lezama, Lu Jiang, Ming-Hsuan Yang, Kevin Murphy, William T. Freeman, Michael Rubinstein, Yuanzhen Li, and Dilip Krishnan. Muse: Text-to-image generation via masked generative transformers. In International Conference on Machine Learning , 2023.
- Oran Gafni, Adam Polyak, Oron Ashual, Shelly Sheynin, Devi Parikh, and Yaniv Taigman. Make-a-scene: Scene-based text-to-image generation with human priors. In European Conference on Computer Vision , 2022.
- Aditya Ramesh, Mikhail Pavlov, Gabriel Goh, Scott Gray, Chelsea Voss, Alec Radford, Mark Chen, and Ilya Sutskever. Zero-shot text-to-image generation. In International Conference on Machine Learning , 2021.
- Aditya Ramesh, Prafulla Dhariwal, Alex Nichol, Casey Chu, and Mark Chen. Hierarchical text-conditional image generation with CLIP latents. CoRR , abs/2204.06125, 2022.
- Chitwan Saharia, William Chan, Saurabh Saxena, Lala Li, Jay Whang, Emily L. Denton, Seyed Kamyar Seyed Ghasemipour, Raphael Gontijo Lopes, Burcu Karagol Ayan, Tim Salimans, Jonathan Ho, David J. Fleet, and Mohammad Norouzi. Photorealistic text-to-image diffusion models with deep language understanding. In Advances in Neural Information Processing Systems , 2022.
- Jiahui Yu, Yuanzhong Xu, Jing Yu Koh, Thang Luong, Gunjan Baid, Zirui Wang, Vijay Vasudevan, Alexander Ku, Yinfei Yang, Burcu Karagol Ayan, Ben Hutchinson, Wei Han, Zarana Parekh, Xin Li, Han Zhang, Jason Baldridge, and Yonghui Wu. Scaling autoregressive models for content-rich text-to-image generation. Transactions on Machine Learning Research , 2022.
- Robin Rombach, Andreas Blattmann, Dominik Lorenz, Patrick Esser, and Björn Ommer. Highresolution image synthesis with latent diffusion models. In Conference on Computer Vision and Pattern Recognition , 2022.
- Xingqian Xu, Zhangyang Wang, Eric Zhang, Kai Wang, and Humphrey Shi. Versatile diffusion: Text, images and variations all in one diffusion model. CoRR , abs/2211.08332, 2022.
- Pamela Mishkin, Lama Ahmad, Miles Brundage, Gretchen Krueger, and Girish Sastry. Dall·e 2 preview - risks and limitations, 2022.
- Javier Rando, Daniel Paleka, David Lindner, Lennart Heim, and Florian Tramèr. Red-teaming the stable diffusion safety filter. In Advances in Neural Information Processing Systems Workshop , 2022.
- Stability AI. Stable diffusion 2.0 release, 2022. Jul 9, 2023.
- Abeba Birhane, Vinay Uday Prabhu, and Emmanuel Kahembwe. Multimodal datasets: misogyny, pornography, and malignant stereotypes. CoRR , abs/2110.01963, 2021.
- Patrick Schramowski, Manuel Brack, Björn Deiseroth, and Kristian Kersting. Safe latent diffusion: Mitigating inappropriate degeneration in diffusion models. In Conference on Computer Vision and Pattern Recognition , 2023.
- AUTOMATIC1111. Negative prompt, 2022.
- Rohit Gandikota, Joanna Materzynska, Jaden Fiotto-Kaufman, and David Bau. Erasing concepts from diffusion models. In International Conference on Computer Vision , 2023.
- Alvin Heng and Harold Soh. Selective amnesia: A continual learning approach to forgetting in deep generative models. In Advances in Neural Information Processing Systems , 2023.
- Eric Zhang, Kai Wang, Xingqian Xu, Zhangyang Wang, and Humphrey Shi. Forget-me-not: Learning to forget in text-to-image diffusion models. CoRR , abs/2303.17591, 2023.
- Nupur Kumari, Bingliang Zhang, Sheng-Yu Wang, Eli Shechtman, Richard Zhang, , and Jun-Yan Zhu. Ablating concepts in text-to-image diffusion models. In International Conference on Computer Vision , 2023.
- Rohit Gandikota, Hadas Orgad, Yonatan Belinkov, Joanna Materzynska, and David Bau. Unified concept editing in diffusion models. CoRR , abs/2308.14761, 2023.
- Jascha Sohl-Dickstein, Eric A. Weiss, Niru Maheswaranathan, and Surya Ganguli. Deep unsupervised learning using nonequilibrium thermodynamics. In International Conference on Machine Learning Workshop , 2015.
- Jonathan Ho, Ajay Jain, and Pieter Abbeel. Denoising diffusion probabilistic models. In Advances in Neural Information Processing Systems , 2020.
- Jonathan Ho and Tim Salimans. Classifier-free diffusion guidance. In Advances in Neural Information Processing Systems Workshop , 2022.
- Nicolas Carlini, Jamie Hayes, Milad Nasr, Matthew Jagielski, Vikash Sehwag, Florian Tramèr, Borja Balle, Daphne Ippolito, and Eric Wallace. Extracting training data from diffusion models. In 32nd USENIX Security Symposium , 2023.
- Gowthami Somepalli, Vasu Singla, Micah Goldblum, Jonas Geiping, and Tom Goldstein. Understanding and mitigating copying in diffusion models. In Advances in Neural Information Processing Systems , 2023.
- Gowthami Somepalli, Vasu Singla, Micah Goldblum, Jonas Geiping, and Tom Goldstein. Diffusion art or digital forgery? investigating data replication in diffusion models. In Conference on Computer Vision and Pattern Recognition , 2023.
- Aditya Golatkar, Alessandro Achille, and Stefano Soatto. Eternal sunshine of the spotless net: Selective forgetting in deep networks. In Conference on Computer Vision and Pattern Recognition , 2020.
- Aditya Golatkar, Alessandro Achille, and Stefano Soatto. Forgetting outside the box: Scrubbing deep networks of information accessible from input-output observations. In European Conference on Computer Vision , 2020.
- Praneeth Bedapudi. Nudenet: Neural nets for nudity detection and censoring, 2022.
- SmithMano. Tutorial: How to remove the safety filter in 5 seconds, 2022.
- Yiting Qu, Xinyue Shen, Xinlei He, Michael Backes, Savvas Zannettou, and Yang Zhang. Unsafe diffusion: On the generation of unsafe images and hateful memes from text-to-image models. In ACM Conference on Computer and Communications Security , 2023.
- Jun-Yan Zhu, Philipp Krähenbühl, Eli Shechtman, and Alexei A. Efros. Generative visual manipulation on the natural image manifold. In European Conference on Computer Vision , 2016.
- Weihao Xia, Yulun Zhang, Yujiu Yang, Jing-Hao Xue, Bolei Zhou, and Ming-Hsuan Yang. GAN inversion: A survey. CoRR , abs/2101.05278, 2021.
- Prafulla Dhariwal and Alexander Quinn Nichol. Diffusion models beat gans on image synthesis. In Advances in Neural Information Processing Systems , 2021.
- Jiaming Song, Chenlin Meng, and Stefano Ermon. Denoising diffusion implicit models. In International Conference on Learning Representations , 2021.
- Nataniel Ruiz, Yuanzhen Li, Varun Jampani, Yael Pritch, Michael Rubinstein, and Kfir Aberman. Dreambooth: Fine tuning text-to-image diffusion models for subject-driven generation. In Conference on Computer Vision and Pattern Recognition , 2023.
- Rinon Gal, Yuval Alaluf, Yuval Atzmon, Or Patashnik, Amit Haim Bermano, Gal Chechik, and Daniel Cohen-Or. An image is worth one word: Personalizing text-to-image generation using textual inversion. In International Conference on Learning Representations , 2023.
- Jing Shi, Wei Xiong, Zhe Lin, and Hyun Joon Jung. Instantbooth: Personalized text-to-image generation without test-time finetuning. CoRR , abs/2304.03411, 2023.
- Ligong Han, Yinxiao Li, Han Zhang, Peyman Milanfar, Dimitris Metaxas, and Feng Yang. Svdiff: Compact parameter space for diffusion fine-tuning. In International Conference on Computer Vision , 2023.
- Yann LeCun, Corinna Cortes, and Christopher J.C. Burges. Mnist handwritten digit database. ATT Labs [Online]. Available: http://yann.lecun.com/exdb/mnist , 2, 2010.
- Jeremy Howard. Imagenette, 2019.
- Giphy. Giphy celebrity detector, 2020.
- Bradley Efron. Tweedie's formula and selection bias. Journal of the American Statistical Association , 106(496):1602-1614, 2011.
- Hadas Orgad, Bahjat Kawar, and Yonatan Belinkov. Editing implicit assumptions in text-toimage diffusion models. In International Conference on Computer Vision , 2023.
- Kevin Meng, Arnab Sen Sharma, Alex J. Andonian, Yonatan Belinkov, and David Bau. Massediting memory in a transformer. In International Conference on Learning Representations , 2023.
- James Kirkpatrick, Razvan Pascanu, Neil Rabinowitz, Joel Veness, Guillaume Desjardins, Andrei A. Rusu, Kieran Milan, John Quan, Tiago Ramalho, Agnieszka Grabska-Barwinska, Demis Hassabis, Claudia Clopath, Dharshan Kumaran, and Raia Hadsell. Overcoming catastrophic forgetting in neural networks. Proceedings of the National Academy of Sciences , 114(13):3521-3526, 2017.
- Hanul Shin, Jung Kwon Lee, Jaehong Kim, and Jiwon Kim. Continual learning with deep generative replay. In Advances in Neural Information Processing Systems , 2017.
- Alec Radford, Jong Wook Kim, Chris Hallacy, Aditya Ramesh, Gabriel Goh, Sandhini Agarwal, Girish Sastry, Amanda Askell, Pamela Mishkin, Jack Clark, Gretchen Krueger, and Ilya Sutskever. Learning transferable visual models from natural language supervision. In International Conference on Machine Learning , 2021.
- Romain Beaumont. Clip retrieval: Easily compute clip embeddings and build a clip retrieval system with them. https://github.com/rom1504/clip-retrieval , 2022.
- Christoph Schuhmann, Romain Beaumont, Richard Vencu, Cade Gordon, Ross Wightman, Mehdi Cherti, Theo Coombes, Aarush Katta, Clayton Mullis, Mitchell Wortsman, Patrick Schramowski, Srivatsa Kundurthy, Katherine Crowson, Ludwig Schmidt, Robert Kaczmarczyk, and Jenia Jitsev. LAION-5B: an open large-scale dataset for training next generation image-text models. In Advances in Neural Information Processing Systems , 2022.

## GLOSSAR

- **Concept erasure** — post hoc methods intended to remove sensitive or unsafe concepts from a trained text-to-image model without full retraining.
- **Concept Inversion (CI)** — the authors' attack technique adapting Textual Inversion to learn special word embeddings that retrieve erased concepts from sanitized models without altering weights.
- **Input filtering** — the authors' hypothesis that erasure methods merely block specific text inputs rather than truly removing concepts from model weights.
- **Textual Inversion (TI)** — learning a new pseudo-word embedding representing a user-provided concept in a frozen text-to-image model's vocabulary.
- **Erased Stable Diffusion (ESD)** — fine-tuning method steering the U-Net's conditional prediction away from an erased concept (variants ESDx and ESDu).
- **Selective Amnesia (SA)** — erasure framed as continual learning with Elastic Weight Consolidation and Generative Replay.
- **Forget-Me-Not (FMN)** — erasure by fine-tuning cross-attention layers to minimize attention maps for the target concept.
- **Ablating Concepts (AC)** — erasure by overwriting a target concept with an anchor (superset or similar) concept.
- **Unified Concept Editing (UCE)** — training-free closed-form editing of U-Net attention weights.
- **Negative Prompt (NP)** — inference guidance replacing the unconditional score with a score conditioned on the erased concept.
- **Safe Latent Diffusion (SLD)** — inference guidance with a timestep-dependent safety term; variants SLD-Weak, SLD-Medium, SLD-Strong, SLD-Max.
- **I2P dataset** — benchmark of 4,703 unique prompts with seeds for measuring NSFW erasure effectiveness.
- **Anchor concept** — a superset or similar concept used to overwrite the target concept in Ablating Concepts.
- **Surrogate distribution** — an alternative forget-distribution (e.g., clowns for celebrity IDs, clothed people for NSFW) used by Selective Amnesia in place of the true concept distribution.
