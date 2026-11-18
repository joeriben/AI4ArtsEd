---
id: cho-et-al-2023-dall-eval-probing-the-reasoning-skills-and-social-biases-of-text-to-image-models
titel: DALL-EVAL. Probing the Reasoning Skills and Social Biases of Text-to-Image Generation Models
autor: "Jaemin Cho, Abhay Zala, Mohit Bansal"
jahr: 2023
quelle: ICCV 2023 (IEEE/CVF International Conference on Computer Vision)
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, bias]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2202.04053"
status: published
checks: passed
review: passed
analyzed_at: "2026-11-15T11:15:10.119814+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: pdf
---

# DALL-EVAL. Probing the Reasoning Skills and Social Biases of Text-to-Image Generation Models

## PROFIL

The paper "DALL-EVAL: Probing the Reasoning Skills and Social Biases of Text-to-Image Generation Models" was written by Jaemin Cho, Abhay Zala, and Mohit Bansal (UNC Chapel Hill) and appears as an ICCV 2023 version, with code and data released on GitHub. Its subject is the evaluation of text-to-image generation models, and its claim is that existing automated metrics cover only image-text alignment and image quality, so it proposes two new evaluation dimensions: visual reasoning skills and social biases. Since the original DALL-E checkpoint is unavailable, it evaluates the publicly released models DALL-E Small, minDALL-E, and Stable Diffusion (v1.4), plus Karlo for bias evaluation only. The paper introduces PAINTSKILLS, a compositional diagnostic dataset rendered with a Unity-based 3D simulator, measuring object recognition, object counting, and spatial relation understanding, with skill accuracy computed from DETR object detection results on generated images; it finds models good at object recognition but far from upper-bound accuracy in counting and spatial relations. Social bias is evaluated with 252 diagnostic prompts combining gender and 83 professions, using BLIP-2 for gender and attribute detection and a FAN/TRUST/ITA pipeline for skin tone on the Monk Skin Tone Scale, quantified by mean absolute deviation from a uniform distribution; it finds gender and skin tone biases learned from web image-text pairs, with an overall male skew and skin tones concentrated around MST 5 and 6. The authors position their contribution against existing metrics (Inception Score, FID, R-precision, captioning-based metrics, Semantic Object Accuracy), which they critique as unsuitable for complex data and lacking interpretable evidence, and against prior bias research in image-only, text-only, and multimodal models, claiming the first evaluation of gender and skin tone bias in text-to-image models from diverse prompts without prompt intervention. Appendices document version changes, simulator and prompt details, detection reliability comparisons, image-text alignment and quality evaluation, model architectures and sampling strategies, and per-profession bias and attribute tables. The paper is usable in computer vision, machine learning, and AI ethics education, and in situations concerning generative model evaluation, fairness and bias analysis, and multimodal AI literacy.

## WISSEN

### Purpose and Overview (p. 1–2)

The paper "DALL-EVAL: Probing the Reasoning Skills and Social Biases of Text-to-Image Generation Models" by Jaemin Cho, Abhay Zala, and Mohit Bansal (UNC Chapel Hill) argues that text-to-image generation models have been evaluated too narrowly. Existing automated metrics cover only two dimensions: image-text alignment (do generated images match the input text's semantics) and image quality (do images resemble training data). The authors propose two new evaluation dimensions: (1) visual reasoning skills and (2) social biases. Since the original DALL-E checkpoint is unavailable, they evaluate four publicly released models: DALL-E Small, minDALL-E, Stable Diffusion (v1.4), and Karlo (Karlo only for bias evaluation, as its training code is not released). Key findings: models are good at object recognition but show a large gap from upper-bound accuracy in object counting and spatial relation understanding; and models learn specific gender and skin tone biases from web image-text pairs (e.g., receptionist → female, plumber → male, woman → wearing skirts, man → wearing suits). Code and data are released at github.com/j-min/DallEval; the paper is an ICCV 2023 version.

### Related Work and Positioning (p. 2–3)

The authors situate their contribution against: (a) text-to-image models (GAN-based pioneers; multimodal transformer language models such as X-LXMERT and DALL-E; diffusion models such as Stable Diffusion, DALL-E 2, Imagen, Parti, MUSE); (b) existing metrics — Inception Score (IS) and Fréchet Inception Distance (FID) for image quality, R-precision, captioning-based metrics (BLEU, CIDEr), and Semantic Object Accuracy (SOA) for alignment — which they critique as unsuitable for complex data, prone to caption ambiguity, and lacking interpretable evidence; and (c) bias research in image-only, text-only, and multimodal models. They claim to provide the first evaluation metrics and analysis of gender and skin tone bias in text-to-image models from diverse prompts combining gender and professions, without prompt intervention.

### PAINTSKILLS: A Diagnostic Dataset for Visual Reasoning (p. 3–4)

The paper introduces PAINTSKILLS, a compositional diagnostic evaluation dataset measuring three skills:
1. **Object recognition** — generate an image containing the intended object class (e.g., an airplane).
2. **Object counting** — generate an image containing M objects of a class (e.g., 3 dogs).
3. **Spatial relation understanding** — generate two objects with a specified relation (e.g., one is right of another).

Motivation: datasets like VQA and GQA are skewed toward a few common objects, causing models to rely on statistical bias rather than compositional reasoning. PAINTSKILLS avoids this by explicitly controlling the statistical bias: (1) scene configurations are defined with uniform distributions over objects, attributes, and relations; (2) text prompts are built from templates with objects, numbers, and relations; (3) images are rendered with a 3D simulator built on the Unity engine. The simulator uses 15 frequent MS COCO object classes (person, dog, airplane, bike, car, …), object counts {1, 2, 3, 4}, 4 spatial relations {above, below, left, right}, and 13 object-free backgrounds. Dataset sizes: 23,250/21,600/13,500 train and 2,325/2,160/2,700 test scenes for object/counting/spatial skills respectively. The simulator is modular and extensible with custom objects and attributes.

### Evaluation Method (p. 4–6)

**Visual reasoning skills (Sec. 4.1):** Skill accuracy is computed from DETR object detection results on generated images (DETR with ResNet-101 backbone, finetuned per skill on PAINTSKILLS). Accuracy formulas check: for object recognition, whether the detected class matches the target with confidence above a threshold; for counting, whether exactly M objects of the target class are detected; for spatial relations, whether both classes and the pairwise relation (decided from 2D coordinates) match.

**Social bias evaluation (Sec. 4.2):** Diagnostic prompts are composed from a gender G ∈ {a man, a woman, a person} and one of 83 professions, using the template "G who works as a/an P", plus three prompts without profession — 252 prompts total; 9 images are sampled per prompt. Detection categories:
- **Gender**: binary {male, female}, detected with BLIP-2 by asking "the person looks like a male or a female?" (BLIP-2: 82% accuracy on Adience vs. 66% for CLIP; 99.2% agreement with human evaluation).
- **Skin tone**: the Monk Skin Tone (MST) Scale (10 tones), detected via FAN facial landmarks, TRUST-based facial albedo estimation (accounting for illumination), and Individual Typology Angle (ITA) computed from L* and B* components of CIE-L*a*b*.
- **Attributes**: 15 attributes from Zhang et al., detected with BLIP-2 via "Is the person wearing A?" (92% BLIP-2 vs. 79% CLIP accuracy).

Bias is quantified with mean absolute deviation (MAD) from an unbiased uniform distribution: 1/N Σ|p_i − p̄|, where p̄ is 0.5 for gender (N=2) and 0.1 for skin tone (N=10). MAD is 0 for a uniform (unbiased) distribution and maximal for a one-hot (entirely biased) distribution.

### Results: Visual Reasoning Skills (p. 6–8)

DETR achieves 98.0% average oracle accuracy on ground-truth PAINTSKILLS images (object 100.0, count 97.8, spatial 96.2) and only 2.8% on randomly shuffled ground truth, validating the metric. Model results (DETR-based, finetuned on PAINTSKILLS):
- DALL-E Small: object 57.5, count 18.2, spatial 2.4, avg. 26.0
- minDALL-E: object 89.9, count 47.5, spatial 50.7, avg. 62.7
- Stable Diffusion: object 96.2, count 37.8, spatial 7.9, avg. 47.3

Stable Diffusion is best at object recognition (attributed to its 5B training data and 512×512 resolution) but minDALL-E beats it on counting and spatial relations; Stable Diffusion often generates more (5 instead of 3 dogs) or fewer (1 instead of 2 bicycles) objects, or misses objects (person, umbrella) in spatial prompts. Fine-grained analysis: counting accuracy drops with more objects; spatial accuracy is similar across the four relations; the counting bottleneck is generating the right number (not the right classes); for Stable Diffusion the spatial bottleneck is differentiating the four relations. Human evaluation on 150 images per model closely matches DETR results and preserves model rankings. Finetuning with 50% or 10% of the data yields similar performance, showing the training set is sufficient.

### Results: Social Biases (p. 8–9)

**Gender bias:** All three models (minDALL-E, Karlo, Stable Diffusion) show an overall tendency toward male images, but per-profession biases differ (e.g., for "Singer," minDALL-E skews male while Karlo and Stable Diffusion skew female; Engineer: −0.78/−1.0/−1.0; Library assistant: −0.11/+1.0/+1.0). Average gender bias (male −1 / female +1): minDALL-E −0.25, Karlo −0.22, Stable Diffusion −0.42. MAD for gender: minDALL-E 0.1984 (lowest), Karlo 0.3545, Stable Diffusion 0.3618 (one-hot = 0.5) — Karlo and Stable Diffusion more strongly generate a specific gender from gender-neutral prompts.

**Skin tone bias:** Unlike gender, all models generate similar skin tones across professions, concentrated around MST 5 and 6 (averages: minDALL-E 5.19, Karlo 5.13, Stable Diffusion 5.14), marginalizing very light and very dark tones. Skin tone MAD values (0.1687–0.1707) are close to 1-hot (0.18) and 2-hot (0.16) distributions.

**Attribute bias:** All models generate skirts only for woman prompts and suit/jacket/tie more frequently for man prompts (e.g., Stable Diffusion: skirt woman 0.07 vs. man 0.0; suit woman 0.19 vs. man 0.35).

### Conclusion and Limitations (p. 9)

The paper concludes that current text-to-image models are good initial contributions but need improvement in challenging visual reasoning skills (especially counting and spatial relations) and in avoiding learned social biases. Limitations: pretrained evaluation models may not be robust to unseen data distributions; gender (referring to sex) and skin tone cover only part of physical appearance; PAINTSKILLS covers only three skills (future: 3D spatial relations, text rendering); findings represent the four public models evaluated, not all models (original DALL-E unavailable); evaluation focuses on English-heavy training data, though methods extend to other languages.

### Appendices: Version Changes, Implementation Details, and Additional Evaluation (p. 13–18)

- **Version updates (p. 13)**: v3 added qualitative examples, fine-grained analysis, removed zero-shot evaluation in favor of finetuning-based evaluation, added attribute-based bias evaluation, adopted BLIP-2 (more accurate, less biased than CLIP), adopted FAN+TRUST+ITA skin tone detection (better than RGB-based), and added Karlo. v2 improved the 3D simulator, removed the color recognition skill, added prompt variations, replaced DETR-R50 with DETR-R101-DC5, and replaced racial bias analysis with skin tone analysis using the MST Scale — the authors explain that race is a socially constructed, political concept, not a biological one, so inferring racial identity from appearance risks inaccuracy.
- **Simulator and prompts (p. 14–16)**: Assets from Unity Asset Store, TurboSquid, Free3D, CadNav, and Adobe Mixamo, within license terms; yaw rotation sampled from [0, 2π], scales from [13, 16]. Full prompt template lists are given (e.g., "a photo of <objA>", "there are <N> <objA>", "a <objB> is <rel> a <objA>").
- **Detection reliability (p. 15–17)**: BLIP-2 outperforms CLIP on COCO gender bias/recall metrics (e.g., R@1: 57.22 vs. 28.58 on original captions); expert annotators trained on the MST-E dataset achieved 0.61 average distance from ground-truth skin tones; face landmark crop + average albedo ITA is the most accurate skin tone method; BLIP-2 attribute detection accuracy 91.71% vs. CLIP 78.63%.
- **Image-text alignment and quality (p. 17–18)**: For completeness, alignment is measured via VL-T5 captioning (BLEU, CIDEr, METEOR, SPICE on 5K Karpathy test captions) and CLIP R-precision (R=1, 30K COCO captions, 1 positive vs. 99 negatives), plus human Likert scoring (1–5, five annotators, 200 pairs); quality via FID. Overall trend: Stable Diffusion > X-LXMERT ≈ minDALL-E > DALL-E Small; Stable Diffusion achieves the lowest FID.
- **Human evaluation setup (p. 18)**: MTurk workers paid $0.11 per 5 image-text pairs (~$12/hour), restricted to US/GB/Australia/Canada, with ≥95% approval rating and ≥1000 approved tasks.

### Figures (p. 1–18)

*Fig. 1 (p. 1):* Overview of our proposed evaluation process for text-toimage generation models. In addition to conventional image-text alignment and image quality evaluation, we propose to measure visual reasoning skills (Sec. 4.1) and social biases (Sec. 4.2) of models. The example images are generated with Stable Diffusion. — This is a flowchart diagram of an evaluation pipeline centered on a box labeled “Text-to-Image Generation Model.” Above the model, four evaluation types are grouped under “Previous Evaluations” and “Ours”: “Image-Text Alignment” (“Can the original caption be inferred from images?”, example “a bicycle parked on a street”), “Image Quality” (“Do images look realistic?”, example “a photo of a dog”), “Visual Reasoning Skills” (“Does model understand objects, counts, and spatial relations?”, example “two dogs”), and “Social Bias” (“Does model have gender / skin tone bias?”, example “a person who works as a doctor”). Below the model, four example images—a bicycle, a single dog, two dogs, and a doctor—point to evaluation steps labeled “Captioning / Retrieval” (“CIDEr / R-precision”), “Distance from Real Images” (“FID”), “Object Detection” (“Skill-based Accuracy”), and “Gender / Skin tone / Attribute Detection” (“Gender / Skin tone Bias”).

*Fig. 2 (p. 3):* Illustration of the visual reasoning evaluation process with PAINTSKILLS (Sec. 3). We generate images from text prompts that require three different visual reasoning skills. Based on object detection results, we evaluate the visual reasoning capabilities of models by checking whether the generated images align with input text prompts. The example images are generated with Stable Diffusion. — This is a diagram illustrating a three-step evaluation workflow for a "Text-to-Image Generation Model" testing three skills: "Object Recognition," "Object Counting," and "Spatial Relation Understanding." Text prompts such as "a photo of a dog," "a photo of two dogs," and "a cat is left to a dog" are shown entering the model, producing images with red bounding boxes around detected objects labeled "Dog" or "Cat." Below each image, verification questions appear with green checkmarks or a red X, ending in "Correct" or "Incorrect" labels.

*Fig. 3 (p. 4):* Dataset generation process (spatial relation understanding skill shown in this example) of PAINTSKILLS. For each skill, we generate scene configurations where object/attribute/layout combinations have a uniform distribution to avoid statistical shortcuts for reasoning. We use a 3D simulator for rendering images. — This is a diagram that combines a code snippet with rendered images. The code, under the comment "# scenes for spatial relation understanding skill", defines a scene containing the objects {"shape": "dog", "relation": None} and {"shape": "car", "relation": "right_0"}, along with the text "there are 2 objects. one is dog and the other is car; the car is right to the dog" and "background": "static-openroad". An arrow leads from the code to a box labeled "Render with 3D Simulator", and a second arrow leads from that box to a stack of rendered images showing an open road with double yellow center lines, a dog on the left side of the road, and a green car on the right side, with trees along both sides of the road.

*Image 4 (p. 4):* Example images, templates, and prompts of PAINTSKILLS. See appendix for more examples. — It is a screenshot of a table whose first column is labeled “Skills” and whose other three columns are headed “Object Recognition,” “Object Counting,” and “Spatial Relation Understanding.” The rows are labeled “Description,” “Template,” and “Keywords,” and the visible templates include “a photo of <obj>,” “a photo of <N> <obj>,” and “a <objB> is <rel> a <objA>.” Under each column is a photograph of a wooden floor with green toy cars, the rightmost photograph also showing a yellow toy airplane, and the “Keywords” row reads “obj: car,” “N: 4, obj: car,” and “objA: car, objB: airplane, rel: below.”

*Fig. 4 (p. 5):* Overview of our social bias analysis (Sec. 4.2). Models generate images with a set of diagnostic prompts ( e.g ., a person who works as a nurse), then with automated detectors and human evaluation, we estimate the gender, skin tone, and attributes shown in the images. Images in the examples were generated with Stable Diffusion. — It is a flowchart diagram. At the top, the prompt “a person who works as a nurse” is labeled “diagnostic prompts” and points into a box labeled “Text-to-Image Generation Model.” The model outputs three portrait photographs of smiling people in medical scrubs. Arrows lead down to a box labeled “Automated Detection + Human Evaluation,” then to three panels labeled “Gender,” “Skin Tone,” and “Attribute,” each with a small distribution graphic showing “Male”/“Female,” a skin-tone gradient, and “uniform dress jeans.” The flow ends in a box labeled “Measure Average and Variance of Distribution.”

*Image 6 (p. 7):* Images generated by three text-to-image generation models finetuned on PAINTSKILLS. Objects detected from the images are shown in colored bounding boxes. — This is a table displaying photographs in a grid with four rows labeled GT, DALL-E Small, miniDALL-E, and Stable Diffusion, and six columns organized under the headings Object Recognition, Object Counting, and Spatial Relation Understanding. Above the columns are the prompts 'a dog', 'a bicycle', '3 dogs', '2 bicycles', 'a suitcase is left to a person', and 'an umbrella is right to a stop sign'. Each cell shows an image with colored bounding boxes drawn around objects, and small text inside the boxes is not legible.

*Fig. 5 (p. 7):* Detailed analysis of count and spatial skills of 3 models, in terms of (a) per-split and (b) per-task accuracy. — The image is a bar-chart figure with four grouped bar charts under the headings “(a) Per-split Accuracy” and “(b) Per-task Accuracy,” each split into “Count” and “Spatial” panels. Every panel plots “Acc. (%)” from 0 to 100 and compares the legend entries “DALLE Small” (blue), “minDALL-E” (orange), and “Stable Diffusion” (green). In the per-split panels, Count uses “# objects” categories 1, 2, 3, 4 and Spatial uses “relation” categories “Left,” “Right,” “Above,” “Below”; in the per-task panels, the Count “subtasks” are “1) N objects ✓” and “1) N objects ✓ 2) right objects ✓,” while the Spatial “subtasks” are “1) right objects ✓” and “1) right objects ✓ 2) right relation ✓.” Visually, the orange minDALL-E bars are the tallest in most panels, and the blue and green bars are much lower in the Spatial panels. _(Lettering in the image, read by the image model, not confirmed: “(a) Per-split Accuracy”)_

*Fig. 6 (p. 8):* Gender, skin tone, and attribute detection results with automated and expert human evaluation. The images are generated by the Stable Diffusion model, using the gender/skin tone-neutral prompts ( e.g ., 'a person who works as a biologist'). For gender estimation, both automated detection and human evaluation agreed on all examples here. For attribute and skin tone estimation, automated detection and human annotation are closely aligned in most cases. The detection results are presented in order of top-left → top-right → bottom-left → bottom-right. M: Male, F: Female, Y: Yes, N: No. — This is a composite figure of twelve color photographs arranged in three groups of four, with a small table beneath each group. The left group, captioned “computer programmer,” shows four people typing at computers with code on the screens; the middle group, captioned “biologist,” shows four people in lab coats in a laboratory, including one in front of a dark background with large white letters of which “NEON” and “CREATIVE” are legible while the upper line is partly obscured; the right group, captioned “shop assistant,” shows four people among shelves and racks in a store. Beneath each group is a table with rows labeled “Gender,” “Skintone,” and “Attribute (Shirt),” “Attribute (Suit),” or “Attribute (Uniform),” filled with “M” or “F,” small skin-tone color swatches, and “Y” or “N.” _(Lettering in the image, read by the image model, not confirmed: “NEON”, “CREATIVE”)_

*Fig. 7 (p. 14):* Overview of our image-text alignment (Appendix D.1) and image quality (Appendix D.2) evaluation process. Based on pretrained image captioner, image retriever, and image classifier models, we calculate the text similarity, R-precision, and FID, respectively. — This is a flowchart diagram. At the top, the quoted prompt “Children sitting on the floor decorating and putting together kites.” leads to a box labeled “Text-to-Image Generative Model,” which leads to a color photograph of children sitting on the floor with a colorful kite. From the photograph, arrows branch to three boxes labeled “Captioner (VL-T5),” “Retriever (CLIP),” and “Image Classifier (InceptionV3),” each above a dashed question box and a metric line reading “BLEU / CIDEr METEOR / SPICE,” “R-precision,” and “Fréchet Inception Distance (FID).” At the bottom, two gray boxes are labeled “Image-Text Alignment” and “Image Quality.”

*Image 10 (p. 15):* The 15 objects used in our PAINTSKILLS dataset, generated with our 3D simulator. The current object list consists of some of the most frequent object classes in the MS COCO dataset. One can easily extend the object list by adding custom 3D objects. — The picture is a grid of fifteen small rendered images arranged in three rows of five. Each cell shows a single 3D object on a gray wooden plank floor, seen from above, with a text label printed above it. The legible labels read, left to right and top to bottom: “Airplane,” “Bear,” “Bench,” “Bike,” “Bird,” “Boat,” “Car,” “Dog,” “Fire Hydrant,” “Human/Person,” “Potted Plant,” “Stop Sign,” “Suitcase,” “Traffic Light,” and “Umbrella.”

*Image 11 (p. 16):* Image examples and text prompt templates for visual reasoning skills of PAINTSKILLS dataset generated by a 3D simulator. — The image is a table with three columns headed **Object Recognition**, **Object Counting**, and **Spatial Relation Understanding**, with subheaders **Skills**, **Description**, and **Template**. The table displays twelve computer-generated images arranged in four rows, each showing simple colored objects—a yellow airplane, a blue boat, a yellow suitcase, or a green car—placed on a wooden floor; the middle column shows one to four instances of a single object type, while the right column shows two different objects positioned relative to one another. Below each image, the word **Keywords** appears followed by text such as **obj: airplane**, **N: 3, obj: suitcase**, or **objA: car, objB: airplane, rel: below**.

*Image 12 (p. 18):* Images generated by three text-to-image generation models finetuned on PAINTSKILLS. Objects detected from the images are shown in colored bounding boxes. — This is a table-like figure with a header row containing "Skills" and "Prompts" and the group labels "Object Recognition", "Object Counting", and "Spatial Relation Understanding". Six columns are headed by quoted prompts including "'an umbrella'", "'a boat'", "'3 umbrellas'", "'3 boats'", and "'an umbrella is left to a boat'", and four rows are labeled "GT", "DALL-E Small", "minDALL-E", and "Stable Diffusion". Each cell holds a small rectangular photograph-style image with one or more colored bounding boxes, blue or orange, around objects. Small text inside some bounding boxes is not legible. _(Lettering in the image, read by the image model, not confirmed: "DALL-E Small")_

<!-- quelle: DALL-EVAL. Probing the Reasoning Skills and Social Biases of Text-to-Image Generation Models (p. 1–18) -->

### Model Details (p. 18–19)

This appendix section documents the five text-to-image models evaluated in the paper, specifying their architectures, training data, and image-token configurations:

- **DALL-E Small**: a 120M-parameter model whose dVAE is a VQGAN pretrained on ImageNet; it reduces 256x256 RGB images to a grid of 256 image tokens (16x16), drawing from a codebook of 1024 entries. Its transformer contains 16 attention blocks and was trained on 15M image-text pairs drawn from Conceptual Captions 3M (CC3M) and CC12M. Generic stochastic sampling is used, without top-k / top-p filtering.
- **minDALL-E**: a 1.3B-parameter model also trained on CC3M and CC12M; its VQGAN-based dVAE likewise reduces 256x256 RGB images to a 16x16 grid of 256 tokens, but with a larger codebook of 16384 entries. Top-k (256) sampling is used.
- **X-LXMERT**: a 228M-parameter model combining a cross-modal transformer with a GAN-based image decoder. It represents 256x256 RGB images as an 8x8 grid of tokens from a 10000-entry codebook, where the codes derive from k-means clustering over features of a pretrained object detector trained on Visual Genome. Training pursues four objectives — visual question answering, masked language modeling, image-text alignment, and text-to-image generation — using captioning and VQA datasets, with 180K images from MS COCO and Visual Genome. Mask-Predict-4 sampling is used.
- **Stable Diffusion**: version 1.4, built on the latent diffusion model (LDM) architecture, with an 860M U-Net, CLIP ViT-L/14, and an autoencoder that downsamples by a factor of 8. It was trained on LAION-5B and then fine-tuned for 225k steps at 512x512 resolution on "laion-aesthetics v2 5+", with 10% dropping of text-conditioning to improve classifier-free guidance sampling.
- **Karlo**: a text-conditional model following the unCLIP architecture, comprising prior, decoder, and super-resolution (SR) modules with 1B, 900M, and 1400M parameters respectively. Training used 115M image-text pairs, among them COYO100M, CC3M, and CC12M, to produce 256x256 RGB images.

### Sampling Strategies (p. 19)

Each model uses its default sampling strategy: generic stochastic sampling for DALL-E Small; stochastic top-k and top-p sampling for minDALL-E; deterministic 4-step sampling for X-LXMERT. CLIP-based rejection sampling is deliberately not used, so that only the generation models' own performance is measured. For Stable Diffusion: classifier-free guidance at scale 7.5 with a PNDM scheduler running 50 steps. For Karlo: 25 denoising steps each for the prior and decoder plus 7 for the SR module, with guidance scales of 4.0 (prior) and 8.0 (decoder).

### Gender Bias by Profession (p. 21)

Using gender-neutral prompts of the form "a person who works as a/an [profession]" (Tables 16–17), the paper reports average gender bias per profession for minDALL-E, Karlo, and Stable Diffusion, scored from -1 (male) to +1 (female). Roughly 80 professions are covered, from accountant through writer. Notable findings:

- Strong male skew (-1.0) appears for e.g. architect (Karlo, Stable Diffusion), builder, butcher, chef, economist, electrician, engineer, film director, judge (minDALL-E), plumber (all three models), police officer, and prison officer.
- Strong female skew (+1.0) appears for flight attendant (Karlo, Stable Diffusion), library assistant, makeup artist, personal assistant, receptionist, and secretary.
- Averages across all professions: minDALL-E -0.25, Karlo -0.22, Stable Diffusion -0.42 — all models skew male overall, with Stable Diffusion most strongly.

### Skin Tone Estimation Method Comparison (p. 22)

The paper compares methods for segmenting skin and estimating skin tone against human annotators on the Monk Skin Tone (MST) scale (Table 18), using Precision@K (a detection counts as positive if the estimated tone is within K tones of the human label):

- RGBA/YCrCb colorspace segmentation + average RGB: Precision@0 = 0%, @1 = 9.2%, @2 = 36.9%, @3 = 56.9%; average difference from human 3.03.
- U-Net segmentation + average RGB: 1.5%, 10.8%, 35.4%, 61.5%; average difference 2.97.
- FAN face landmark crop + average RGB: 0%, 8.5%, 33.9%, 66.1%; average difference 2.93.
- FAN face landmark crop + average albedo ITA: 3.39%, 25.42%, 50.85%, 94.92%; average difference 2.25 — the most accurate configuration, and the one adopted.

### Image-Text Alignment and Image Quality Evaluation (p. 22)

Models are compared on captioning-based alignment metrics (VL-T5 captioning: BLEU-4, METEOR, CIDEr, SPICE), CLIP retrieval R-precision, human Likert rating (1–5), and InceptionV3 FID (lower is better) (Table 19). Ground truth (upper bound): BLEU-4 32.5, METEOR 27.5, CIDEr 108.3, SPICE 20.4, R-precision 62.5, Likert 5.0, FID 0.0. Results:

- X-LXMERT (228M params, 180K data, 256²/8² grid): BLEU-4 18.5, METEOR 19.1, CIDEr 55.8, SPICE 12.1, R-precision 33.4, Likert 3.5, FID 37.4
- DALL-E Small (120M, 15M, 256²/16²): BLEU-4 9.3, METEOR 12.9, CIDEr 20.2, SPICE 5.6, R-precision 9.4, Likert 2.9, FID 45.8
- minDALL-E (1.3B, 15M, 256²/16²): BLEU-4 16.6, METEOR 17.6, CIDEr 48.0, SPICE 10.5, R-precision 40.2, Likert 3.5, FID 24.6
- Stable Diffusion (869M, 5B, 512²/64²): BLEU-4 26.1, METEOR 24.1, CIDEr 86.8, SPICE 17.0, R-precision 73.7, Likert 3.7, FID 16.5

Stable Diffusion performs best on all metrics; DALL-E Small worst.

### Skin Tone Bias by Profession (p. 24)

Using prompts of the form "a [person/man/woman] who works as a/an [profession]" and the Monk Skin Tone Scale (1 to 10) (Tables 20–21), average skin tones per profession are reported for minDALL-E, Karlo, and Stable Diffusion. Distributions concentrate on the center tones (around 5) for all models and professions (see also Figures 8–10, p. 19–20 and 23, which visualize this clustering across attributes and professions, and compare human annotation against face crop + TRUST-based average albedo ITA and face crop + average RGB). The highest values (darker skin) appear for farmer (5.68 / 5.75 / 5.92), garbage collector (5.0 / 5.23 / 5.44), geologist (5.15 / 5.35 / 5.77), miner (5.5 / 5.18 / 5.59), police officer (5.66 for minDALL-E), prison officer (5.61 / 5.43 / 5.19), and trucker (5.61 for minDALL-E). Averages across all professions: minDALL-E 5.19, Karlo 5.13, Stable Diffusion 5.14.

### Gender-Attribute Skew (p. 25)

Table 22 measures how often attributes (slacks, dress, skirt, suit, shirt, uniform, jacket, hat, tie, mask, gloves) appear in images for "person", "woman", and "man" prompts, with parenthesized differences from the neutral "person" prompt, plus a "Woman - Man" row showing relative correlation of each attribute with gender. Boots, slippers, jeans, and shorts are excluded because their appearance rates were near zero. Key patterns, consistent across minDALL-E, Karlo, and Stable Diffusion:

- Dresses and skirts correlate strongly with "woman" prompts (e.g. dress: Woman - Man = +0.11 minDALL-E, +0.04 Karlo, +0.06 Stable Diffusion; skirt: +0.10 / +0.05 / +0.07).
- Suits, jackets, hats, and especially ties correlate with "man" prompts (tie: -0.21 / -0.18 / -0.20; suit: -0.27 / -0.11 / -0.16).
- Mean absolute differences from the "person" prompt: for minDALL-E, woman 0.03 vs. man 0.05; for Karlo, woman 0.02 vs. man 0.03; for Stable Diffusion, woman 0.03 vs. man 0.03 — i.e., "man" prompts deviate more from neutral generations than "woman" prompts in minDALL-E and Karlo, while the two genders deviate equally in Stable Diffusion.

### Per-Model Attribute Occurrence Tables (p. 26–34)

The remainder of the appendix provides full per-profession, per-attribute occurrence tables (Tables 23–31) for each model and prompt gender:

- **minDALL-E**: Table 23 (p. 26) for "a person" prompts; Table 24 (p. 27) for "a woman" prompts; Table 25 (p. 28) for "a man" prompts — the latter two giving parenthesized differences from the neutral version.
- **Karlo**: Table 26 (p. 29) for "a person"; Table 27 (p. 30) for "a woman"; Table 28 (p. 31) for "a man".
- **Stable Diffusion**: Table 29 (p. 32) for "a person"; Table 30 (p. 33) for "a woman"; Table 31 (p. 34) for "a man".

Each table lists, for every one of the ~80 professions, the average occurrence rate (0 to 1) of each clothing attribute in the generated images, plus a "Mean Abs. Diff." column summarizing how far the gendered prompt's images deviate from the neutral prompt's images. These tables substantiate the paper's finding that gendered prompts systematically shift generated attributes (e.g., ties and suits rising sharply for "a man" prompts, dresses and skirts for "a woman" prompts), quantifying the models' encoded gender-attribute associations profession by profession.

### Figures (p. 19–33)

*Fig. 8 (p. 19):* Distributions of each skin tone on the MST scale across various attributes. For all models, the distribution is focused on the center few tones. — The image shows three vertically stacked bar charts labeled underneath “(a) minDALL-E”, “(b) Karlo”, and “(c) Stable Diffusion”. Each chart has a y-axis labeled “Ratio” scaled from “0.0” to “1.0” and an x-axis with the category labels “boots”, “slippers”, “jeans”, “shorts”, “slacks”, “dress”, “skirt”, “suit”, “shirt”, “uniform”, “jacket”, “hat”, “tie”, “mask”, and “gloves”. At each category there are two narrow vertical bars, one light tan and one dark brown, and their heights vary by category and panel; for example, in panel (a) “boots” has a dark bar near “1.0” while “slippers” is near “0.0”. Across the three panels, many categories show one bar close to “1.0” and the other much lower, while a few categories such as “shorts” show two more comparable mid-range bars. _(Lettering in the image, read by the image model, not confirmed: “Ratio”, “0.0”, “1.0”, “boots”, “slippers”, “jeans”, “shorts”, “slacks”, “dress”, “skirt”, “suit”, “shirt”, “uniform”, “jacket”, “hat”, “tie”, “gloves”, “boots”, “1.0”, “slippers”, “0.0”, “1.0”, “shorts”)_

*Fig. 9 (p. 20):* Distributions of each skin tone on the MST scale across various professions. For all models, the distribution is focused on the center few tones. — The image is a three-panel scientific chart, with panels labeled “(a) minDALL-E” and “(b) Karlo” and a third panel label partly cut off at the right edge. Each panel lists the same professions down the left side, such as “accountant,” “animator,” “architect,” through “web designer” and “actor,” and plots short horizontal gray line segments against a horizontal axis labeled “Ratio” with visible tick labels “0.0,” “0.5,” and “1.0.” The segments are arranged one per profession at different positions along the Ratio scale. _(Lettering in the image, read by the image model, not confirmed: “accountant,”, “animator,”, “architect,”, “web designer”, “actor,”, “Ratio”, “0.0,”, “0.5,”, “1.0.”)_

*Fig. 10 (p. 23):* Comparison of MST skin tone estimation by (a) human annotators, (b) face crop + TRUST-based average albedo ITA, and (c) face crop + average RGB on various professions — The picture is a horizontal bar chart divided into three side-by-side panels. Each panel lists the same professions down the left side—such as “accountant,” “animator,” “architect,” and “doctor”—and draws a horizontal bar to the right from a vertical zero line. The bottom axis of each panel is labeled “Ratio” with tick labels “0.0,” “0.5,” and “1.0,” and the panels are labeled underneath as “(a) Human,” “(b) TRUST,” and “(c) RGB.” The bars vary in length and in tan/brown shading across both professions and panels. _(Lettering in the image, read by the image model, not confirmed: “accountant,”, “animator,”, “architect,”, “doctor”, “Ratio”, “0.0,”, “0.5,”, “1.0,”)_

*Image 16 (p. 27):* Average occurrence of each attribute in the images (generated by minDALL-E) for diagnostic prompts that started with 'a woman'. Values in parenthesis indicate the difference between the average occurrence of the attribute in the images for that prompt and the gender-neutral version of the prompt in Table 23. — This is a screenshot of a data table. The leftmost column lists text prompts, each beginning with “A woman who works as …” followed by an occupation, for example “A woman who works as an accountant.” Across the top are column headers for clothing and accessory items—“boots,” “slippers,” “jeans,” “shorts,” “slacks,” “dress,” “skirt,” “suit,” “shirt,” “uniform,” “jacket,” “hat,” “tie,” “mask,” “gloves”—followed by a final column headed “Mean Abs. Diff.”. The body cells contain numeric entries such as “0.0” and values with parenthesized differences like “0.11(0.11),” with some entries printed in green and others in red.

*Image 17 (p. 28):* Average occurrence of each attribute in the images (generated by minDALL-E) for diagnostic prompts that started with 'a man'. Values in parenthesis indicate the difference between the average occurrence of the attribute in the images for that prompt and the gender-neutral version of the prompt in Table 23. — The image is a screenshot of a dense data table. The leftmost column lists prompts beginning with “A man who works as…” (for example, “A man who works as an accountant” and “A man who works as an actor”). Across the top are column headers such as boots, slippers, jeans, shorts, slacks, dress, skirt, suit, shirt, uniform, jacket, hat, tie, mask, gloves, and “Mean Abs. Diff.” The cells contain small numeric entries, many “0.0,” often with parenthesized values printed in red or green; much of the finer text is too small to be legible. _(Lettering in the image, read by the image model, not confirmed: “A man who works as an actor”)_

*Image 18 (p. 30):* Average occurrence of each attribute in the images (generated by Karlo) for diagnostic prompts that started with 'a woman'. Values in parenthesis indicate the difference between the average occurrence of the attribute in the images for that prompt and the genderneutral version of the prompt in Table 26. — This is a screenshot of a data table. The leftmost column, headed “Prompt,” lists rows such as “A woman who works as an accountant,” “A woman who works as an architect,” and “A woman who works as a writer.” The other columns are headed “boots,” “slippers,” “jeans,” “shorts,” “slacks,” “dress,” “skirt,” “suit,” “shirt,” “uniform,” “jacket,” “hat,” “tie,” “mask,” “gloves,” and “Mean Abs. Diff.,” and the cells contain mostly “0.0” with some nonzero values, some followed by parenthesized numbers shown in red or green.

*Image 19 (p. 31):* Average occurrence of each attribute in the images (generated by Karlo) for diagnostic prompts that started with 'a man'. Values in parenthesis indicate the difference between the average occurrence of the attribute in the images for that prompt and the gender-neutral version of the prompt in Table 26. — The picture is a screenshot of a data table. Its leftmost column is headed “Prompt” and lists rows such as “A man who works as an accountant” and “A man who works as an actor,” followed by columns headed “boots,” “slippers,” “jeans,” “shorts,” “slacks,” “dress,” “skirt,” “suit,” “shirt,” “uniform,” “jacket,” “hat,” “tie,” “mask,” “gloves,” and “Mean Abs. Diff.” Most cells contain “0.0,” while some cells show decimal values with parenthesized differences, printed in green or red. The table is dense, with many rows of occupational prompts and small numeric entries across each attribute column. _(Lettering in the image, read by the image model, not confirmed: “A man who works as an actor,”)_

*Image 20 (p. 33):* Average occurrence of each attribute in the images (generated by Stable Diffusion) for diagnostic prompts that started with 'a woman'. Values in parenthesis indicate the difference between the average occurrence of the attribute in the images for that prompt and the gender-neutral version of the prompt in Table 29. — This is a screenshot of a data table rather than a photograph. The leftmost column, headed “Prompt,” lists rows such as “A woman who works as an accountant” and many similar “A woman who works as …” occupation prompts. Across the top are attribute columns labeled boots, slippers, jeans, shorts, slacks, dress, skirt, suit, shirt, uniform, jacket, hat, tie, mask, gloves, and a final “Mean Abs. Diff.” column. Most cells read 0.0, while some contain values such as 0.11, 0.22, 0.33, 0.44, 0.55, 0.66, 0.77, 0.88, or 1.0 followed by parenthesized differences printed in green or red.

<!-- quelle: F. Model Details (p. 18–34) -->

## LITERATUR

<!-- quelle: References (p. 10–13) -->

- Aishwarya Agrawal, Dhruv Batra, Devi Parikh, and Aniruddha Kembhavi. Don't Just Assume; Look and Answer: Overcoming Priors for Visual Question Answering. In CVPR , 2018. 2, 4
- Peter Anderson, Basura Fernando, Mark Johnson, and Stephen Gould. SPICE: Semantic Propositional Image Caption Evaluation. In ECCV , 2016. 17
- Peter Anderson, Xiaodong He, Chris Buehler, Damien Teney, Mark Johnson, Stephen Gould, and Lei Zhang. Bottom-Up and Top-Down Attention for Image Captioning and Visual Question Answering. In CVPR , 2018. 18
- Stanislaw Antol, Aishwarya Agrawal, Jiasen Lu, Margaret Mitchell, Dhruv Batra, C. Lawrence Zitnick, and Devi Parikh. VQA: Visual question answering. In ICCV , 2015. 4, 19
- Satanjeev Banerjee and Alon Lavie. METEOR : An Automatic Metric for MT Evaluation with Improved Correlation with Human Judgments. In ACL Workshop , 2005. 17
- Hritik Bansal, Da Yin, and Masoud Monajatipoor. How well can Text-to-Image Generative Models understand Ethical Natural Language Interventions? In EMNLP , 2022. 3, 5
- Hugo Berg, Siobhan Hall, Yash Bhalgat, Hannah Kirk, Aleksandar Shtedritski, and Max Bain. A prompt array keeps the bias away: Debiasing vision-language models with adversarial learning. In Proceedings of the 2nd Conference
- of the Asia-Pacific Chapter of the Association for Computational Linguistics and the 12th International Joint Conference on Natural Language Processing (Volume 1: Long Papers) , pages 806-822, Online only, Nov. 2022. Association for Computational Linguistics. 3
- Shruti Bhargava and David Forsyth. Exposing and correcting the gender bias in image captioning datasets and models. ArXiv , abs/1912.00578, 2019. 3
- Abeba Birhane, Vinay Uday Prabhu, and Emmanuel Kahembwe. Multimodal datasets: misogyny, pornography, and malignant stereotypes. ArXiv , abs/2110.01963, 2021. 2, 3
- Simone Browne. Dark Matters: On the Surveillance of Blackness . Duke University Press, 2015. 5, 13
- Adrian Bulat and Georgios Tzimiropoulos. How far are we from solving the 2d & 3d face alignment problem? (and a dataset of 230,000 3d facial landmarks). In International Conference on Computer Vision , 2017. 2, 6, 13, 16, 22
- Kaylee Burns, Lisa Anne Hendricks, Trevor Darrell, and Anna Rohrbach. Women also snowboard: Overcoming bias in captioning models. ArXiv , abs/1803.09797, 2018. 3
- Minwoo Byeon, Beomhee Park, Haecheon Kim, Sungjun Lee, Woonhyuk Baek, and Saehoon Kim. Coyo700m: Image-text pair dataset. https://github.com/ kakaobrain/coyo-dataset , 2022. 21
- Aylin Caliskan, Joanna J. Bryson, and Arvind Narayanan. Semantics derived automatically from language corpora contain human-like biases. Science , 356(6334):183-186, 2017. 3
- Nicolas Carion, Francisco Massa, Gabriel Synnaeve, Nicolas Usunier, Alexander Kirillov, and Sergey Zagoruyko. End-to-End Object Detection with Transformers. In ECCV , 2020. 2, 4, 13
- Huiwen Chang, Han Zhang, Jarred Barber, AJ Maschinot, Jose Lezama, Lu Jiang, Ming-Hsuan Yang, Kevin Murphy, William T. Freeman, Michael Rubinstein, Yuanzhen Li, and Dilip Krishnan. Muse: Text-To-Image Generation via Masked Generative Transformers. pages 1-22, 2023. 2
- Soravit Changpinyo, Piyush Sharma, Nan Ding, and Radu Soricut. Conceptual 12M: Pushing Web-Scale Image-Text Pre-Training To Recognize Long-Tail Visual Concepts. In CVPR , 2021. 18
- A. CHARDON, I. CRETOIS, and C. HOURSEAU. Skin colour typology and suntanning pathways. International Journal of Cosmetic Science , 13(4):191-208, 1991. 2, 6, 13
- Jaemin Cho, Jie Lei, Hao Tan, and Mohit Bansal. Unifying Vision-and-Language Tasks via Text Generation. In ICML , feb 2021. 17
- Jaemin Cho, Jiasen Lu, Dustin Schwenk, Hannaneh Hajishirzi, and Aniruddha Kembhavi. X-LXMERT: Paint, Caption and Answer Questions with Multi-Modal Transformers. In EMNLP , 2020. 2, 17, 18
- Christopher Clark, Mark Yatskar, and Luke Zettlemoyer. Don't Take the Easy Way Out: Ensemble Based Methods for Avoiding Known Dataset Biases. In EMNLP , 2019. 2, 4
- Kate Crawford. The Atlas of AI: Power, Politics, and the Planetary Costs of Artificial Intelligence . Yale University Press, 2021. 5, 13
- Corentin Dancette, Remi Cadene, Xinlei Chen, and Matthieu Cord. Overcoming Statistical Shortcuts for Open-ended Visual Counting. ArXiv , arXiv:2006.10079v2, 2020. 2, 4
- Jia Deng, Wei Dong, Richard Socher, Li-Jia Li, Kai Li, and Li Fei-Fei. ImageNet: A Large-Scale Hierarchical Image Database. In CVPR , 2009. 2, 17, 18
- Eran Eidinger, Roee Enbar, and Tal Hassner. Age and gender estimation of unfiltered faces. IEEE Transactions on Information Forensics and Security , 9(12):2170-2179, 2014. 6, 15
- Patrick Esser, Robin Rombach, and Bj¨ orn Ommer. Taming Transformers for High-Resolution Image Synthesis. In CVPR , 2021. 18
- Angela Fan, Mike Lewis, and Yann Dauphin. Hierarchical Neural Story Generation. In ACL , 2018. 21
- Haiwen Feng, Timo Bolkart, Joachim Tesch, Michael J. Black, and Victoria Abrevaya. Towards racially unbiased skin tone estimation via scene disambiguation. In ECCV , 2022. 2, 6, 13, 16, 22
- Stanislav Frolov, Tobias Hinz, Federico Raue, J¨ orn Hees, and Andreas Dengel. Adversarial Text-to-Image Synthesis: A Review. Neural Networks , 144:187-209, jan 2021. 1, 2, 3
- Marjan Ghazvininejad, Omer Levy, Yinhan Liu, and Luke Zettlemoyer. Mask-Predict: Parallel Decoding of Conditional Masked Language Models. In EMNLP , 2019. 19, 21
- Ian J. Goodfellow, Jean Pouget-Abadie, Mehdi Mirza, Bing Xu, David Warde-Farley, Sherjil Ozair, Aaron Courville, and Yoshua Bengio. Generative Adversarial Networks. In NIPS , 2014. 2
- Yash Goyal, Tejas Khot, Aishwarya Agrawal, Douglas Summers-Stay, Dhruv Batra, and Devi Parikh. Making the V in VQA Matter: Elevating the Role of Image Understanding in Visual Question Answering. In CVPR , 2017. 2, 4, 19
- Kaiming He, Georgia Gkioxari, Piotr Dollar, and Ross Girshick. Mask R-CNN. ICCV , 2017. 18
- Kaiming He, Xiangyu Zhang, Shaoqing Ren, and Jian Sun. Deep Residual Learning for Image Recognition. In CVPR , 2016. 4
- Martin Heusel, Hubert Ramsauer, Thomas Unterthiner, Bernhard Nessler, and Sepp Hochreiter. GANs Trained by a Two Time-Scale Update Rule Converge to a Local Nash Equilibrium. In NIPS , 2017. 1, 2, 17
- Tobias Hinz, Stefan Heinrich, and Stefan Wermter. Semantic Object Accuracy for Generative Text-to-Image Synthesis. IEEE Transactions on Pattern Analysis and Machine Intelligence , pages 1-1, 2020. 1, 2, 3, 4
- Yusuke Hirota, Yuta Nakashima, and Noa Garc´ ıa. Gender and racial bias in visual question answering datasets. 2022 ACM Conference on Fairness, Accountability, and Transparency , 2022. 3
- Y. Hirota, Y. Nakashima, and N. Garcia. Quantifying societal bias amplification in image captioning. In 2022 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) , pages 13440-13449, Los Alamitos, CA, USA, jun 2022. IEEE Computer Society. 3
- Jonathan Ho, Ajay Jain, and Pieter Abbeel. Denoising Diffusion Probabilistic Models. In NeurIPS , 2020. 2
- Jonathan Ho and Tim Salimans. Classifier-Free Diffusion Guidance. In NeurIPS 2021 Workshop on Deep Generative Models and Downstream Applications , 2022. 21
- Ari Holtzman, Jan Buys, Li Du, Maxwell Forbes, and Yejin Choi. The Curious Case of Neural Text Degeneration. In ICLR , 2020. 21
- Seunghoon Hong, Dingdong Yang, Jongwook Choi, and Honglak Lee. Inferring Semantic Layout for Hierarchical Text-to-Image Synthesis. In CVPR , 2018. 1, 2
- Drew A. Hudson and Christopher D. Manning. GQA: A new dataset for real-world visual reasoning and compositional question answering. In CVPR , 2019. 4, 19
- Andrej Karpathy and Li Fei-Fei. Deep Visual-Semantic Alignments for Generating Image Descriptions. In CVPR , 2015. 17
- Os Keyes, Chandler May, and Annabelle Carrell. You keep using that word: Ways of thinking about gender in computing research. Proc. ACM Hum.-Comput. Interact. , 5(CSCW1), apr 2021. 5
- Saehoon Kim, Sanghun Cho, Chiheon Kim, Doyup Lee, and Woonhyuk Baek. mindall-e on conceptual captions. https://github.com/kakaobrain/ minDALL-E , 2021. 1, 6, 18
- Diederik P Kingma and Max Welling. Auto-Encoding Variational Bayes. In NIPS , 2013. 6
- Seema Kolkur, D. Kalbande, P. Shimpi, Chaitanya Bapat, and Janvi Jatakia. Human skin detection using rgb, hsv and ycbcr color models. ArXiv , abs/1708.02694, 2017. 14, 15, 22
- Ranjay Krishna, Yuke Zhu, Oliver Groth, Justin Johnson, Kenji Hata, Joshua Kravitz, Stephanie Chen, Yannis Kalantidis, Li Jia-Li, David Ayman Shamma, Michael Bernstein, and Li Fei-Fei. Visual Genome: Connecting Language and Vision Using Crowdsourced Dense Image Annotations. International Journal of Computer Vision , 2016. 18
- Donghoon Lee, Jiseob Kim, Jisu Choi, Jongmin Kim, Minwoo Byeon, Woonhyuk Baek, and Saehoon Kim. Karlov1.0.alpha on coyo-100m and cc15m. https://github. com/kakaobrain/karlo , 2022. 1, 6, 13
- Junnan Li, Dongxu Li, Silvio Savarese, and Steven Hoi. Blip-2: Bootstrapping language-image pre-training with frozen image encoders and large language models. ArXiv , abs/2301.12597, 2023. 2, 6, 13, 14
- Tsung Yi Lin, Michael Maire, Serge Belongie, James Hays, Pietro Perona, Deva Ramanan, Piotr Doll´ ar, and C. Lawrence Zitnick. Microsoft COCO: Common Objects in Context. In ECCV , 2014. 4, 17
- Luping Liu, Yi Ren, Zhijie Lin, and Zhou Zhao. Pseudo Numerical Methods for Diffusion Models on Manifolds. In ICLR , 2022. 21
- Elman Mansimov, Emilio Parisotto, Jimmy Lei Ba, and Ruslan Salakhutdinov. Generating Images from Captions with Attention. In ICLR , 2016. 2
- Margaret Mitchell, Dylan Baker, Nyalleng Moorosi, Emily Denton, Ben Hutchinson, Alex Hanna, Timnit Gebru, and Jamie Morgenstern. Diversity and Inclusion Metrics in Subset Selection , page 117-123. Association for Computing Machinery, New York, NY, USA, 2020. 3
- Ellis Monk. Monk Skin Tone Scale. https:// skintone.google , 2022. 2, 5, 6, 9, 13, 24
- Alex Nichol, Prafulla Dhariwal, Aditya Ramesh, Pranav Shyam, Pamela Mishkin, Bob McGrew, Ilya Sutskever, and Mark Chen. GLIDE: Towards Photorealistic Image Generation and Editing with Text-Guided Diffusion Models. In ICML , 2022. 2
- Kishore Papineni, Salim Roukos, Todd Ward, and Wj Weijing Zhu. BLEU: a Method for Automatic Evaluation of Machine Translation. In ACL , 2002. 2, 17
- Alec Radford, Jong Wook Kim, Chris Hallacy, Aditya Ramesh, Gabriel Goh, Sandhini Agarwal, Girish Sastry, Amanda Askell, Pamela Mishkin, Jack Clark, Gretchen Krueger, Ilya Sutskever, Jong Wook, Kim Chris, Hallacy Aditya, Ramesh Gabriel, Goh Sandhini, Girish Sastry, Amanda Askell, Pamela Mishkin, Jack Clark, Gretchen Krueger, and Ilya Sutskever. Learning Transferable Visual Models From Natural Language Supervision. In ICML , 2021. 6, 13, 15, 17, 19
- Aditya Ramesh, Prafulla Dhariwal, Alex Nichol, Casey Chu, and Mark Chen. Hierarchical Text-Conditional Image Generation with CLIP Latents. ArXiv , 2204.06125, 2022. 2, 21
- Aditya Ramesh, Mikhail Pavlov, Gabriel Goh, Scott Gray, Chelsea Voss, Alec Radford, Mark Chen, and Ilya Sutskever. Zero-Shot Text-to-Image Generation. In ICML , 2021. 1, 2, 21
- Victor Ray. On Critical Race Theory: Why It Matters & Why You Should Care . Random House Publishing Group, 2022. 5, 13
- Ali Razavi, Aaron van den Oord, and Oriol Vinyals. Generating Diverse High-Fidelity Images with VQ-VAE-2. In NeurIPS , 2019. 6
- Scott Reed, Zeynep Akata, Xinchen Yan, Lajanugen Logeswaran, Bernt Schiele, and Honglak Lee. Generative adversarial text to image synthesis. In ICML , 2016. 2
- Robin Rombach, Andreas Blattmann, Dominik Lorenz, Patrick Esser, and Bj¨ orn Ommer. High-resolution image synthesis with latent diffusion models. In CVPR , pages 1068410695, June 2022. 1, 2, 6, 13, 19
- Candace Ross, Boris Katz, and Andrei Barbu. Measuring social biases in grounded vision and language embeddings. In NAACL , 2021. 2, 3
- Chitwan Saharia, William Chan, Saurabh Saxena, Lala Li, Jay Whang, Emily Denton, Seyed Kamyar Seyed Ghasemipour, Burcu Karagol Ayan, S. Sara Mahdavi, Rapha Gontijo Lopes, Tim Salimans, Jonathan Ho, David J Fleet, and Mohammad Norouzi. Photorealistic Text-to-Image Diffusion Models with Deep Language Understanding. In NeurIPS , 2022. 2
- Tim Salimans, Ian Goodfellow, Wojciech Zaremba, Vicki Cheung, Alec Radford, and Xi Chen. Improved Techniques for Training GANs. In NIPS , 2016. 1, 2
- Christoph Schuhmann, Romain Beaumont, Richard Vencu, Cade W Gordon, Ross Wightman, Mehdi Cherti, Theo Coombes, Aarush Katta, Clayton Mullis, Mitchell Wortsman, Patrick Schramowski, Srivatsa R Kundurthy, Katherine Crowson, Ludwig Schmidt, Robert Kaczmarczyk, and Jenia
- Jitsev. LAION-5b: An open large-scale dataset for training next generation image-text models. In NeruIPS Datasets and Benchmarks Track , 2022. 19
- Candice Schumann, Gbolahan O Olanubi, Auriel Wright, Ellis Monk Jr, Courtney Heldreth, and Susanna Ricco. Consensus and subjectivity of skin tone annotation for ml fairness. arXiv preprint arXiv:2305.09073 , 2023. 6, 13, 15
- Piyush Sharma, Nan Ding, Sebastian Goodman, and Radu Soricut. Conceptual captions: A cleaned, hypernymed, image alt-text dataset for automatic image captioning. In ACL , 2018. 18
- Jascha Sohl-Dickstein, Eric A. Weiss, Niru Maheswaranathan, and Surya Ganguli. Deep unsupervised learning using nonequilibrium thermodynamics. In ICML , 2015. 2
- Tejas Srinivasan and Yonatan Bisk. Worst of both worlds: Biases compound in pre-trained vision-and-language models. ArXiv , abs/2104.08666, 2021. 3, 14
- Ryan Steed and Aylin Caliskan. Image representations learned with unsupervised pre-training contain human-like biases. In Proceedings of the 2021 ACM Conference on Fairness, Accountability, and Transparency , FAccT '21, page 701-713, New York, NY, USA, 2021. Association for Computing Machinery. 3
- Christian Szegedy, Vincent Vanhoucke, Sergey Ioffe, Jonathon Shlens, and Zbigniew Wojna. Rethinking the Inception Architecture for Computer Vision. In CVPR , 2016. 2, 17
- Ruixiang Tang, Mengnan Du, Yuening Li, Zirui Liu, Na Zou, and Xia Hu. Mitigating gender bias in captioning systems. In Proceedings of the Web Conference 2021 , WWW'21, page 633-645, New York, NY, USA, 2021. Association for Computing Machinery. 3
- Aaron van den Oord, Oriol Vinyals, and Koray Kavukcuoglu. Neural Discrete Representation Learning. In NIPS , 2017. 6
- Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Lukasz Kaiser, and Illia Polosukhin. Attention Is All You Need. In NIPS , 2017. 1
- Ramakrishna Vedantam, C. Lawrence Zitnick, and Devi Parikh. CIDEr: Consensus-based Image Description Evaluation. In CVPR , nov 2015. 2, 17
- Angelina Wang, Solon Barocas, Kristen Laird, and Hanna Wallach. Measuring representational harms in image captioning. In 2022 ACM Conference on Fairness, Accountability, and Transparency , pages 324-335, 2022. 3
- Jialu Wang, Yang Liu, and Xin Eric Wang. Are genderneutral queries really gender-neutral? mitigating gender bias in image search. In EMNLP , 2021. 3, 6, 15, 17
- Phil Wang. Dalle-pytorch. https://github.com/ lucidrains/DALLE-pytorch , 2021. 1, 6
- Tianlu Wang, Jieyu Zhao, Mark Yatskar, Kai-Wei Chang, and Vicente Ordonez. Balanced datasets are not enough: Estimating and mitigating gender bias in deep image representations. In ICCV , pages 5309-5318, 2019. 3
- Spencer Whitehead, Hui Wu, Heng Ji, Rogerio Feris, and Kate Saenko. Separating Skills and Concepts for Novel Visual Question Answering. In CVPR , 2021. 3
- Robert Wolfe, Mahzarin R. Banaji, and Aylin Caliskan. Evidence for hypodescent in visual semantic ai. 2022 ACM Conference on Fairness, Accountability, and Transparency , 2022. 3
- Robert Wolfe and Aylin Caliskan. Markedness in visual semantic ai. 2022 ACM Conference on Fairness, Accountability, and Transparency , 2022. 3
- Han Xu, Abhijit Sarkar, and A. Lynn Abbott. Color invariant skin segmentation. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) Workshops , pages 2906-2915, June 2022. 15, 22
- Tao Xu, Pengchuan Zhang, Qiuyuan Huang, Han Zhang, Zhe Gan, Xiaolei Huang, and Xiaodong He. AttnGAN: Fine-Grained Text to Image Generation with Attentional Generative Adversarial Networks. In CVPR , 2018. 1, 2
- Jiahui Yu, Yuanzhong Xu, Jing Yu Koh, Thang Luong, Gunjan Baid, Zirui Wang, Vijay Vasudevan, Alexander Ku, Yinfei Yang, Burcu Karagol Ayan, Ben Hutchinson, Wei Han, Zarana Parekh, Xin Li, Han Zhang, Jason Baldridge, and Yonghui Wu. Scaling Autoregressive Models for Content-Rich Text-to-Image Generation. Transactions on Machine Learning Research , 2022. 2
- Han Zhang, Tao Xu, Hongsheng Li, Shaoting Zhang, Xiaogang Wang, Xiaolei Huang, and Dimitris Metaxas. Stack-GAN : Text to Photo-realistic Image Synthesis with Stacked Generative Adversarial Networks. In ICCV , 2017. 2
- Yanzhe Zhang, Lu Jiang, Greg Turk, and Diyi Yang. Auditing gender presentation differences in text-to-image models, 2023. 3, 5, 6, 13, 16
- Dora Zhao, Angelina Wang, and Olga Russakovsky. Understanding and evaluating racial biases in image captioning. In International Conference on Computer Vision (ICCV) , 2021.
- 3
- Jieyu Zhao, Tianlu Wang, Mark Yatskar, Vicente Ordonez, and Kai-Wei Chang. Men also like shopping: Reducing gender bias amplification using corpus-level constraints. In EMNLP , pages 2979-2989, Copenhagen, Denmark, Sept. 2017. Association for Computational Linguistics. 3
- Minfeng Zhu, Pingbo Pan, Wei Chen, and Yi Yang. DM-GAN: Dynamic memory generative adversarial networks for text-to-image synthesis. In CVPR , 2019. 17
- Yuke Zhu, Oliver Groth, Michael Bernstein, and Li Fei-Fei. Visual7W: Grounded Question Answering in Images. In CVPR , 2016. 19
- In this appendix, we include the following content: updates from the previous Arxiv versions (Appendix A), visual reasoning evaluation details (Appendix B), social bias evaluation details (Appendix C), image-text alignment and image quality evaluation (Appendix D), visual reasoning and image-text alignment human evaluation details (Appendix E), and model details (Appendix F).

## GLOSSAR

- **DALL-EVAL** — the evaluation framework introduced by the paper for probing the reasoning skills and social biases (gender, skin tone, attribute skew) of text-to-image generation models.
- **PAINTSKILLS** — A compositional diagnostic evaluation dataset, rendered with a Unity 3D simulator, that measures object recognition, object counting, and spatial relation understanding with uniform distributions over objects and relations.
- **Object recognition** — The skill of generating an image containing the object class described in the text.
- **Object counting** — The skill of generating an image containing exactly M objects of the described class.
- **Spatial relation understanding** — The skill of generating two objects with the specified spatial relation (above, below, left, right).
- **MAD (mean absolute deviation)** — The bias metric measuring the distance between a detected gender/skin tone/attribute distribution and an unbiased uniform distribution; 0 = uniform (unbiased), maximal for one-hot (entirely biased).
- **MST (Monk Skin Tone) Scale** — A 10-tone scale transforming the continuous skin tone spectrum, used instead of binary or racial categorizations.
- **ITA (Individual Typology Angle)** — A skin tone measure computed from L* (lightness) and B* (yellow/blue) components of the CIE-L*a*b* colorspace, calculated on facial albedo to account for illumination.
- **Diagnostic prompts** — The 252 prompts of the form "G who works as a/an P" (3 genders × 83 professions + 3 gender-only) used to probe social bias.
- **Bias@K** — A gender bias metric for retrieval models, the average of (N_male − N_female)/(N_male + N_female) over K retrieved images, used to compare CLIP and BLIP-2.
- **MST-E (Monk Skin Tone Examples)** — A dataset of exemplars used to train human annotators for consistent MST-scale skin tone annotation.
- **MST scale (Monk Skin Tone Scale)** — a 1-to-10 skin tone scale used to measure the skin tone bias of generated images.
- **Precision@K** — precision metric for skin tone estimation where a detection is positive if the estimated tone is within K tones of the human-annotated MST tone.
- **Average gender bias** — per-profession score of generated images from gender-neutral prompts, ranging from -1 (male) to +1 (female).
- **Mean Abs. Diff.** — the mean absolute difference in attribute occurrence between images from a gendered prompt and those from the corresponding gender-neutral "person" prompt.
