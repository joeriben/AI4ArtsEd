---
id: gandikota-et-al-2024-unified-concept-editing-in-diffusion-models-uce
titel: Unified Concept Editing in Diffusion Models
autor: "Rohit Gandikota, Hadas Orgad, Yonatan Belinkov, Joanna Materzyńska, David Bau"
jahr: 2024
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2308.14761"
status: published
checks: passed
review: passed
analyzed_at: "2026-11-15T10:46:44.137280+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: pdf
---

# Unified Concept Editing in Diffusion Models

## PROFIL

The article "Unified Concept Editing in Diffusion Models" was written by Rohit Gandikota, Hadas Orgad, Yonatan Belinkov, Joanna Materzyzyńska and David Bau, affiliated with Northeastern University, Technion and MIT, as a research contribution to the safety of text-to-image diffusion models. Its subject is Unified Concept Editing (UCE), a training-free, closed-form method that edits the cross-attention weights (W_k and W_v) of a pretrained diffusion model to address copyright infringement via artistic style imitation, social bias, and offensive content in a single pass; the authors' position is that these issues arise simultaneously in real-world deployments and should be treated together, as a practical complement to training-data curation. The paper first situates UCE against prior work on copyright (ESD, Concept Ablation, SDD, image cloaking), offensive-content filtering, debiasing (Debiasing-VL, Concept Algebra, TIME) and model editing (MEMIT, TIME), both of which it generalizes. It then presents the method—three edit types (erasing, debiasing, moderation) and an iterative debiasing algorithm—followed by experiments on artist and object erasure, gender and racial debiasing of professions, and nudity moderation on the I2P benchmark, plus a unified-editing experiment combining all three. A limitations section records compounding and word-level compositional biases and degradation beyond roughly 500 artist erasures, and an appendix gives closed-form derivations and extended results. The paper is usable in arts education contexts concerning generative AI, intellectual property and artistic style, representation and bias in visual culture, and content moderation—situations where students or practitioners examine how generative image models can be made, in the authors' words, "ethical, socially responsible."

## WISSEN

### Purpose and Thesis (p. 1–2)

This paper by Rohit Gandikota, Hadas Orgad, Yonatan Belinkov, Joanna Materzyńska and David Bau (Northeastern University, Technion, MIT) presents **Unified Concept Editing (UCE)**, a method for addressing multiple safety problems of text-to-image diffusion models—copyright infringement via artistic style imitation, social bias, and offensive content—with a single approach. The authors argue that because these issues appear simultaneously in real-world deployments, they should be treated together rather than with separate solutions. UCE edits a pretrained model without any training, using a closed-form solution, and scales to hundreds of simultaneous edits while preserving the model's generative quality for unedited concepts. The authors position UCE as a practical complement to training-data curation, which they note can have counterintuitive effects (removing undesired content can expose other undesired content; removing toxic content can introduce new biases).

### Related Work (p. 2)

The paper situates UCE against prior work in four areas:

- **Copyright**: models can memorize copyrighted training data nearly verbatim. Prior remedies include caption augmentation, "image cloaking" (adversarial perturbations artists add to published images), and post-training concept erasure by modifying weights (ESD, Concept Ablation, SDD). UCE differs by being a closed-form edit that removes many concepts at once.
- **Offensive content**: existing approaches filter at training or inference time (e.g., Stable Diffusion's NSFW safety checker), but such filters can be easily disabled in open-source releases. Weight-level approaches (attention re-steering, fine-tuning, continual learning) all require fine-tuning; UCE offers a fast closed-form alternative.
- **Social bias**: prior methods project out biased directions in text embeddings (Debiasing-VL), manipulate representations algebraically (Concept Algebra), or apply closed-form editing (TIME). Prior work found simultaneous debiasing of multiple concepts difficult because debiasing one concept affects others; UCE overcomes this with a new debiasing procedure.
- **Model editing**: UCE generalizes closed-form editing approaches (MEMIT for language models, TIME for diffusion models) to enable simultaneous removal and debiasing of many concepts.

### Background: Diffusion Models and TIME (p. 2–4)

Diffusion models generate images by iteratively denoising Gaussian noise over T time steps. In text-to-image latent diffusion, text conditioning enters the U-Net through cross-attention layers with a QKV structure: queries come from the image, keys and values from text embeddings. The paper focuses on the linear projections W_k and W_v that map text embeddings c_i to keys (k_i = W_k c_i) and values (v_i = W_v c_i). Cross-attention is the mechanism that assigns visual meaning to text tokens.

The paper builds on **TIME**, which edits implicit assumptions in diffusion models (e.g., that roses are red, or doctors male) by updating W_k and W_v to move a "source" prompt embedding (e.g., "a pack of roses") toward a "destination" embedding (e.g., "a pack of blue roses"). TIME's closed-form solution includes a regularization term λ. The authors interpret the identity matrix in this solution as matching the covariance of the model's whole concept vocabulary, inspired by MEMIT. TIME's weakness is that its regularization is general and affects all vector representations equally—editing doctors to be female might also affect teachers.

### Method: Unified Concept Editing (p. 4–5)

Given a pretrained layer W_old, UCE finds new weights W that map each edited concept embedding c_i ∈ E to a target output v*_i = W_old c*_i, while preserving outputs for concepts c_j ∈ P as W_old c_j. The objective has a closed-form solution (Eq. 7). The formulation generalizes prior work: using only canonical directions as preservation terms reduces to TIME; solving for the weight update ΔW instead of W reduces to MEMIT. For multi-token concepts, the last token of c_i is aligned to the last token of v*_i. The same editing function applies to all edit types; only the target keys and values differ. As a closed-form edit, modifying attention weights takes less than 1 minute.

Three edit types are defined:

1. **Erasing**: to erase a concept c_i (e.g., the artistic style 'Kelly Mckernan'), the target output v_i is aligned with a different, generic concept c* (e.g., 'art'), so the model no longer generates the undesired concept.
2. **Debiasing**: to debias a concept c_i (e.g., 'doctor') across attributes a_1...a_p (e.g., 'white', 'asian', 'black'), the magnitude of v_i is adjusted along the attribute directions v_a_i = W_old a_i, with constants α_i chosen to achieve any desired probability per attribute. Unlike TIME and Concept Ablation, this handles multiple attributes simultaneously, not just dual attributes.
3. **Moderation**: to moderate a concept c_i (e.g., 'nudity'), the target output is aligned with an unconditional prompt c_0 (an empty string), reducing extreme attributes of the concept.

**Algorithm 1 (Debiasing Concepts in Diffusion Models)** proceeds as follows:
1. Input: diffusion model M with cross-attentions W_k, W_v; edit list E; preserve list P; attributes A (list of p strings); learning step η; desired ratios R_des.
2. Loop: compute current ratios R_curr for the model.
3. For each concept c_i in E: if max(|R_curr[i] − R_des[i]|) < 0.05, move c_i from the edit list to the preserve list and continue.
4. Otherwise compute α = η(R_curr[i] − R_des[i]) (α ∈ R^p), and set target outputs v*_i = W_v c_i + α·A and k*_i = W_k c_i + α·A.
5. When E is empty, break; otherwise apply UCE (Eq. 7) to update W_v and W_k, and repeat.

### Experiments: Erasing (p. 5–6)

**Artist erasure**: UCE erases multiple artistic styles while preserving other artists, causing substantially less interference on holdout artists neither erased nor preserved. Compared to ESD-x, Concept Ablation, and SDD (cross-attention fine-tuning methods), UCE shows the lowest LPIPS difference from original Stable Diffusion and the highest CLIP score on COCO-30k prompts. ESD and SDD damage the model when erasing sequentially (1000 iterations per concept), so they were limited to sampling-based erasure for 1000 iterations; SDD was limited to 700 iterations for multi-concept erasure and Ablation to 1000 total iterations, per the authors' notes on overfitting.

Scaling results (Table 1, erasing n artists while preserving the remaining 1000−n): UCE erases up to 100 concepts while performing similarly to pretrained SD on COCO-30k. CLIP score stays near the original 31.32 (e.g., 31.35 at 1 erasure, 31.48 at 10, 30.08 at 100), but drops to 21.06 at 500 erasures and 16.79 at 1000; FID rises from 14.37 (1 erasure) to 72.40 (500) and 85.48 (1000), versus 14.49 for original SD. After 50 erasures, outputs for a given seed and prompt begin to change (LPIPS 0.22 at 50, 0.30 at 100), but text-image alignment remains intact.

**Object erasure**: erasing Imagenette classes (e.g., "French Horn", "Garbage Truck") without explicit preservation, evaluated on 500 images per class with a pretrained ResNet-50. UCE reduces the average accuracy of erased classes to 2.6% (vs. 78.2% for SD and 12.6% for ESD-u) while raising the average accuracy of other classes to 79.8% (vs. 78.2% for SD and 63.2% for ESD-u). Erasing all 10 Imagenette classes together reduced generation accuracy to 4.0% with a COCO-CLIP score of 31.02 (original SD: 31.32).

### Experiments: Debiasing (p. 6–7)

Stable Diffusion produces only 6% female figures for the prompt "CEO". UCE debiases professions using profession embeddings and attribute embeddings (e.g., "male", "female"), with per-attribute constants α_i tuned iteratively: validation samples are generated and classified by CLIP, and once a concept is sufficiently debiased it is moved to the preservation list. This avoids over-debiasing some concepts while under-debiasing others.

**Gender bias**: evaluated on 250 images per profession, measuring deviation Δ = |p_desired − p_actual| / p_desired from a 50-50 ratio (Δ = 0 is perfect debiasing). UCE achieves the smallest deviations, e.g., Librarian 0.07 (vs. 0.86 original SD), Teacher 0.06, Sheriff 0.10, Doctor 0.20, and WinoBias average 0.22 (vs. 0.67 for SD, 0.44 for TIME, 0.31 for TIME + Preserve, 0.43 for Concept Algebra, 0.55 for Debias-VL). The authors acknowledge the binary framing excludes non-binary groups but adopt it for comparability with dual-attribute baselines.

**Racial bias**: UCE concurrently debiases across the U.S. OMB racial categories (White, Black, American Indian, Native American, Asian). Because race classification from images is error-prone even for CLIP and humans, the evaluation is qualitative, showing improved racial diversity in generated professional images.

### Experiments: Moderation (p. 7)

On erasing "nudity", evaluated with 4703 images from the I2P benchmark and the NudeNet classifier, UCE performs comparably to ESD-x (both edit only cross-attentions), while ESD-u is more aggressive (it fine-tunes the whole model except cross-attentions). However, UCE induces substantially lower distortion: LPIPS 0.12 vs. 0.18 (ESD-x-1) and 0.23 (ESD-u-1); FID-SD 1.82 vs. 2.33 and 3.73; CLIP score 31.26 vs. 30.81 and 30.45 (original SD: 31.32). UCE also shows improved multi-concept moderation across the I2P categories (hate, harassment, violence, suffering, humiliation, harm, suicide, sexual content, nudity, bodily fluids, blood, obscene gestures, illegal activity, drug use, theft, vandalism, weapons, child abuse, brutality, cruelty).

### Unified Editing (p. 7)

UCE performs style erasure, profession debiasing, and nudity moderation simultaneously with a single model update. The jointly edited model performs on par with individually trained models: gender ratio deviation of 0.27 versus 0.22 for the gender-debiasing-only model (and 0.67 for original SD), and 58% nudity reduction versus 49% for the nudity-only model and 64% for ESD-u.

### Limitations (p. 8)

- Debiasing across multiple attributes reveals compounding, interdependent biases: "a black person" has near-equal gender ratios (48% male out of 100 images) while "a native american person" shows strong male bias (96% male of 100). Debiasing in isolation can perpetuate biases along other dimensions.
- Word-level compositional biases: "successful person" is predominantly male (88% of 100) versus the gender-balanced "person" (50% male of 100), so each word element contributes biases needing mitigation.
- Erasing over 500 artists degrades general image generation even with preservation terms, suggesting a critical mass of artists is needed to maintain generative capability.

### Conclusion (p. 8)

UCE offers three key benefits: (1) simultaneous mitigation of multifaceted gender, racial and other biases while preserving model capabilities; (2) scalability—hundreds of concept edits in one pass without retraining; (3) superior performance on real-world use cases. The authors present UCE as a step toward democratizing access to ethical, socially responsible generative models.

### Appendix: Derivations and Extended Results (p. 11–19)

- **Closed-form derivation (p. 11)**: the covariance matrix to invert must have full rank; if the number of preservation terms |P| < d (the text embedding dimension), d additional preservation terms along canonical basis directions are introduced to guarantee invertibility.
- **UCE generalizes TIME (p. 11)**: preserving only canonical directions scaled by λ recovers TIME's closed-form solution, which regularizes equally across all directions.
- **UCE generalizes MEMIT (p. 11–12)**: rewriting the solution in block form with W = W_old + ΔW and assuming the preservation list covers most of the model's vocabulary recovers MEMIT's closed-form update.
- **Erasing style (p. 12)**: quality for holdout artists declines after erasing over 100 styles; with 50 or fewer erasures interference is minimal. Stress tests show the model loses artistic nuance after approximately 1000 edits, with output-quality changes for holdout styles appearing after 300 erasures. When erasing 10 artists, preserving at least 500 artists is essential for retaining model performance.
- **Debiasing (p. 12–13)**: the unified model performs comparably to individual debiasing models (e.g., Worker 0.09 unified vs. 0.06 debiased; WinoBias 0.27 vs. 0.22). Table D.2 reports debiasing results for all 36 WinoBias professions; UCE achieves the lowest average deviation (0.22). The iterative algorithm's design is justified for three reasons: concepts require varying levels of editing; editing one concept creates interference, so debiased concepts are protected in the preservation list; and asymmetric per-concept, per-attribute constants α_p require iterative tuning.
- **Moderating NSFW (p. 13)**: per-class NudeNet results show similar erasure to ESD-x for individual classes, with the advantage emerging in multi-concept erasure.
- **Erasing objects (p. 13)**: ESD-u only partially removed objects like churches (crosses and tinted windows erased but the building remained); UCE erases the full object.

### Figures (p. 1–19)

*Image 1 (p. 1):* — This is a diagram comparing an “Original Model” panel on the left with a “Unified Edited Model” panel on the right. The left panel shows example images under the headings “Mimicked Style,” “Biased,” and “Unsafe,” including paintings, a red car, groups of men in suits and doctors, and nude figures covered by black masks, with a note reading “Masks added by authors for publication.” Between the panels, text lists “Erasing 100 Artistic Styles,” “Debiasing 35 Professions,” “Moderating NSFW,” and “Preserving Remaining Concepts,” above a right-pointing arrow labeled “Closed Form Edit.” The right panel shows corresponding images under “Erased Style,” “Diverse Representation,” and “Safe,” including landscape and red car pictures, diverse groups of people, and unmasked safe figures.

*Fig. 2 (p. 3):* Closed-form editing of cross-attention weights enables concept manipulation in diffusion models. Our method modifies the attention weights to induce targeted changes to the keys and values corresponding to specific text embeddings for a set of edited concepts c i ∈ E while minimizing changes to a set of preserved concepts c j ∈ P . That dual objective allows debiasing, erasing, or moderating concepts while preserving unrelated ones. The same editing function is applied in all cases, but the target keys and values are set differently per application. As a closed-form edit, modifying attention weights given the new keys and values mappings takes less than 1 minute. That enables efficient simultaneous editing of multiple concepts. — This is a schematic diagram. On the left, two arrows labeled "Concepts to Edit $c_i \in E$" and "Concepts to Preserve $c_j \in P$" point into a central trapezoidal block labeled "W" with "Cross Attention" underneath. From the block, "$Wc_i$" points via a dashed arrow to red "$v_i^*$" and sits beside the expression "$\min_W \sum_{i=0}^m ||Wc_i - v_i^*||_2^2$", while "$Wc_j$" appears with a lock icon beside "$\min_W \sum_{j=0}^n ||Wc_j - W_v^{old}c_j||_2^2$". Both expressions connect to a circle containing a plus sign on the right, from which an arrow labeled "Minimizing in Closed Form" curves back to the central block. _(Lettering in the image, read by the image model, not confirmed: "Concepts to Edit $c_i \in E$", "Concepts to Preserve $c_j \in P$", "$Wc_i$", "$v_i^*$", "$\min_W \sum_{i=0}^m ||Wc_i - v_i^*||_2^2$", "$Wc_j$", "$\min_W \sum_{j=0}^n ||Wc_j - W_v^{old}c_j||_2^2$")_

*Fig. 3 (p. 5):* Our method and ESD-x show strong erasing capabilities. SDD and Ablation 2 start to dilute their erasing capabilities as the number of concepts being erased are increased. — The picture is a figure from a document showing a grid of fifteen generated images arranged in three rows and five columns. The five columns are labeled at the top as "Original SD", "Our Method", "ESD-x-1", "SDD", and "Ablation". The three rows are labeled on the left with "# of Artists Erased" and the values "1", "5", and "50", each paired with an artist name: "Andrew Ferez", "Antonio J. Manzanedo", and "Thomas Cole". Each cell of the grid contains a colorful digital painting or artwork depicting subjects such as buildings, human figures, and landscapes.

*Fig. 4 (p. 6):* Our method preserves the remaining knowledge of the model better after the edit. The figure shows images generated from different editing methods, for the same prompts and seeds, across a variety of artists that are not erased . Our method exhibits lower LPIPS, indicating less change to unerased concepts during model editing. Similarly for COCO, we find that our method has better CLIP scores across all the scales. This demonstrates that our method has significantly reduced interference compared to other fine-tuning approaches when editing. — This is a composite figure from a document, with a grid of generated images on the left and two line charts on the right. The image grid has columns headed "Original SD", "Our Method", "SDD", "Ablation", and "ESD-x-1", and rows labeled "# of Artists Erased" with the values 1, 5, and 50 next to artist names such as "Alex Alemany"; the cells show generated artworks, including portraits and landscapes. On the right, the upper chart plots "LPIPS (Holdout)*" — with the note "* Lower LPIPS → More Similar" — against "# of Artists Erased", and the lower chart plots "CLIP (COCO-30k)" against the same x-axis, each with lines labeled "Our Method", "ESD-x-1", "SDD", and "Ablation". In the upper chart the lines rise from left to right, with "Our Method" the lowest and "ESD-x-1" the highest; in the lower chart the "Our Method" line stays near the top while the other lines trend downward. _(Lettering in the image, read by the image model, not confirmed: "LPIPS (Holdout)*", "* Lower LPIPS → More Similar", "CLIP (COCO-30k)")_

*Fig. 5 (p. 7):* Our method improves the gender representation of professions in the stable diffusion generated images. We find that the images precisely change the gender while keeping the rest of the scene intact. — The picture is a figure displaying a grid of sixteen images of people arranged in four rows and two columns. The left column is labeled "Original SD" and the right column is labeled "Gender Diverse SD." Along the left edge, the rows are labeled "Mechanic," "Cashier," "Nurse," and "Farmer." Each cell shows a person in a work setting matching the row label.

*Fig. 6 (p. 7):* Our method improves the racial diversity of professions in the pre-trained stable diffusion. We show images from the original SD and the corresponding images from the edited model for the same prompts and seeds for comparison. We find that our edited model has a better race representation. — This is a figure made of a grid of computer-generated portrait images arranged in four rows and two columns. The left column is headed “Original SD” and the right column “Racially Diverse SD”; the rows are labeled along the left edge “Doctor,” “Secretary,” “Supervisor,” and “Counselor.” Each cell shows an upper-body portrait of a person in work clothing, and the portraits in the right column differ in appearance from those in the left column.

*Fig. 7 (p. 8):* A percentage reduction in nudity-classified samples on I2P prompts compared to SD. Our method erases nudity content from pre-trained SD and has the advantage of erasing multiple concepts in I2P prompts. "Nudity" erased model performs very similar to ESD-x-1 as both the methods edit only cross attentions. However, as noted in Table 4, we find that our method results in a finer edit and has better alignment with COCO. — It is a horizontal bar chart with eight colored bars. The vertical axis lists, from top to bottom, "ESD-u-1 (I2P)", "ESD-u-1 (nudity)", "ESD-x-1 (nudity)", "Our Method (I2P)", "Our Method (nudity)", "Our Method (unified)", "SLD Medium", and "Stable Diffusion V2.1". The horizontal axis is labeled "% Change from SD (796)" and is marked with "-100", "-50", and "0". Each bar runs from 0 on the right leftward to a different negative position, with the "Our Method (I2P)" bar reaching closest to -100 and the "Stable Diffusion V2.1" bar the shortest. _(Lettering in the image, read by the image model, not confirmed: "ESD-u-1 (I2P)", "ESD-u-1 (nudity)", "ESD-x-1 (nudity)", "Our Method (I2P)", "Our Method (nudity)", "Our Method (unified)", "SLD Medium", "Stable Diffusion V2.1", "% Change from SD (796)", "Our Method (I2P)", "Stable Diffusion V2.1")_

*Image 8 (p. 12):* — This is a screenshot of a figure that combines generated images with a line chart. Across the top, under the heading “# of Artists Erased,” five images labeled “5,” “10,” “50,” “100,” and “1000” show the same illustrated scene becoming progressively more distorted, with the “1000” image appearing as a colorful abstract picture; at the left, an image labeled “Original SD” shows the original scene. Below is a line graph with y-axis “LPIPS*” (0.1 to 0.4) and x-axis “# of Artists Erased” (0 to 1000), plotting two curves identified in the legend as “erased” (blue) and “holdout” (orange), with the note “* Lower LPIPS → Less Different.” _(Lettering in the image, read by the image model, not confirmed: “* Lower LPIPS → Less Different.”)_

*Image 9 (p. 13):* — This image is a multi-panel bar chart containing eight horizontal bar graphs arranged in two rows and four columns. Each graph displays nine categories listed on the vertical axis—Total (796), Female Breast (278), Female Genitalia (21), Male Genitalia* (5), Male Breast (22), Buttocks (30), Armpits (246), Belly (157), and Feet (37)—plotted against '% Change' on the horizontal axis ranging from -100 to 0. The top row panels are titled 'Stable Diffusion V2.1', 'SLD Medium', 'ESD-u-1 (I2P)', and 'ESD-u-1 (nudity)', while the bottom row panels are titled 'ESD-x-1 (nudity)', 'Our Method (I2P)', 'Our Method (nudity)', and 'Our Method (unified)'. Each body part category appears as a differently colored horizontal bar extending leftward from the zero line. A text label in the upper left corner reads 'Exposed Body Parts (# in SD1.4)'. _(Lettering in the image, read by the image model, not confirmed: '% Change', 'Stable Diffusion V2.1', 'SLD Medium', 'ESD-u-1 (I2P)', 'ESD-u-1 (nudity)', 'ESD-x-1 (nudity)', 'Our Method (I2P)', 'Our Method (nudity)', 'Our Method (unified)', 'Exposed Body Parts (# in SD1.4)')_

*Image 10 (p. 13):* — The figure shows five images arranged horizontally at the top under the heading "# of Artists Preserved" with values 0, 100, 500, 1000, and 1500, where the leftmost image is abstract and multicolored and the other four depict a boat on water. Below on the left is an image labeled "Original SD" depicting a boat on water near trees and buildings. To the right is a line chart with the vertical axis labeled "LPIPS*" and the horizontal axis labeled "# of Artists Preserved", displaying two lines marked "holdout" and "erased" and the annotation "* Lower LPIPS → Less Different". _(Lettering in the image, read by the image model, not confirmed: "* Lower LPIPS → Less Different")_

*Image 11 (p. 14):* — The image is a screenshot from a document showing a comparison grid of small artwork thumbnails split into two side-by-side panels. The left panel, titled "Erased Artists - 1", contains five rows labeled "Alex Alemany" across five columns headed "Original SD", "Our Method", "ESD-x-1", "SDD", and "Ablation". The right panel, titled "Unerased Artists", contains five rows labeled "John Howe", "Rob Gonsalves", "Chris Mars", "Paul Henry", and "Anne Bachelier" with the same five column headings. Each cell in the grid displays a distinct thumbnail image of a painting or illustration.

*Image 12 (p. 14):* — This is a screenshot of a figure from a document showing a grid of small generated images, divided into a left panel headed “Erased Artists - 5” and a right panel headed “Unerased Artists”. Across the top of each panel are column labels reading “Original SD”, “Our Method”, “SDD”, and “Ablation”, plus one further column header that is not fully legible. The rows are labeled with artist names, including the legible “Alpo Jaakola”, “Abraham Mintchine”, “Gareth Pugh”, “Albert Watson”, “Cuno Amiet”, “Beatrix Potter”, “Roz Chast”, and “Alexandre Antigna”; a couple of other row labels are not fully legible. Each cell contains a painting or image in a distinct style, arranged for side-by-side comparison of the methods.

*Image 13 (p. 15):* — This is a figure displaying a grid of images organized into two sections labeled "Erased Artists - 10" and "Unerased Artists". Each section has five rows marked with vertical text naming artists—on the left "Apollinary Vasnetsov", "John Constable", "Johannes Vermeer", "Nicolas Mignard", "John Whitecomb", and on the right "Amanda Sage", "Andre Derain", "Yoji Shinkawa", "Jessie Willcox Smith", "Alexandre Antigna". Five column headers across the top read "Original SD", "Our Method", "ESD-x-1", "SDD", and "Ablation", with each grid cell containing a small image. _(Lettering in the image, read by the image model, not confirmed: "John Whitecomb", "Andre Derain")_

*Image 14 (p. 15):* — The image is a screenshot of a figure divided into two panels labeled "Erased Artists - 50" and "Unerased Artists", each displaying a grid of artwork images. The grid has five columns labeled "Original SD", "Our Method", "ESD-x-1", "SDD", and "Ablation", and five rows per panel labeled with artist names: "Kobayashi Kiyochika", "Amedeo Modigliani", "Ismail Inceoglu", "Ravi Zupa", "Jordan Grimmer" on the left and "Rob Gonsalves", "John Howe", "Eugene von Guerard", "Russ Mills", "Hendrick Avercamp" on the right. Each cell contains a painting or digital artwork.

*Image 15 (p. 16):* — The picture is a grid of digital images arranged in five rows and ten columns. The columns are labeled at the top with "Original SD", "Erasing 1", "Erasing 10", "Erasing 100", "Erasing 200", "Erasing 300", "Erasing 400", "Erasing 500", "Erasing 1000", and "Erasing 1500", and the rows are labeled on the left with "Alfred Sisley", "Amanda Sage", "Martiniere", "Filip Hodas", and "Yoji Shinkawa". Each cell contains a generated image showing a scene that changes progressively from left to right, with the first row depicting a riverside landscape with boats, the second row a colorful portrait of a woman, the third row a fantasy landscape with rock formations, the fourth row a purple landscape with a tree, and the fifth row a black-and-white mechanical figure.

*Image 16 (p. 16):* — The picture is a figure showing a grid of 32 images organized into two columns headed "Original SD" and "Gender Diverse SD" and four rows labeled "Driver", "Carpenter", "Analyst", and "Sheriff" along the left side. Each cell contains a photograph or drawing of a person depicted in the occupation named by the row. In the bottom row, the first image under "Original SD" displays the word "SEERCE" at the top, and the first image under "Gender Diverse SD" displays the word "SEERIFE" at the top. _(Lettering in the image, read by the image model, not confirmed: "SEERCE", "SEERIFE")_

*Image 17 (p. 18):* — The picture is a grid of portrait photographs arranged in four rows, with each row split into a left section headed "Original SD" and a right section headed "Gender Diverse SD". The four rows are labeled on the left side as "CEO", "Physician", "Hair Dresser", and "Secretary". Each section contains four portrait photographs per row showing people in professional attire.

*Image 18 (p. 18):* — The image is a figure showing a grid of thirty-two portrait images arranged in four rows and eight columns, divided into two groups of four columns by a vertical dotted line. The top of the left group is labeled "Original SD" and the top of the right group is labeled "Racially Diverse SD". Along the left side, the four rows are labeled "House Keeper", "Manager", "Baker", and "Librarian". Each cell contains an image of a person, with some appearing as photographs and others as paintings or illustrations.

*Image 19 (p. 19):* — This is a composite figure displaying sixteen color photographs arranged in a four-by-four grid, with vertical text labels along the left side of each row. The first row, labeled "Original SD," shows four images of brass French horns, while the second row, labeled "Erasing French Horn," shows four street scenes and objects without French horns. The third row, labeled "Original SD," shows four images of white golf balls on golf courses, and the fourth row, labeled "Erasing Golf Ball," shows four golf course scenes without golf balls.

*Image 20 (p. 19):* — This figure is a grid of sixteen images arranged in four rows and four columns, with vertical labels on the left reading “Original SD”, “Erasing Gas Pump”, “Original SD”, and “Erasing Cassette Player”. The first row shows four photographs of gas pumps, mostly red with one yellow-and-blue pump, and the first pump displays the word “GAS” plus a small screen whose text is not legible. The second row shows four photographs of yards, paths, and driveways with no gas pumps. The third row shows four images of cassette players and stereo equipment. The fourth row shows four images of other subjects—a room interior, a stone archway, a framed striped panel, and a line drawing—with no cassette players. _(Lettering in the image, read by the image model, not confirmed: “GAS”)_

*Image 21 (p. 19):* — The picture is a grid of sixteen color photographs arranged in four rows and four columns. The top row, labeled "Original SD" on the left, shows four photographs of churches, and the second row, labeled "Erasing Church", shows four photographs of other buildings and streets. The third row, labeled "Original SD", shows four photographs of garbage trucks, and the bottom row, labeled "Erasing Garbage Truck", shows four photographs of other scenes, one of which contains text that is not legible.

<!-- quelle: Unified Concept Editing in Diffusion Models (p. 1–19) -->

## LITERATUR

<!-- quelle: References (p. 9–10) -->

- Sarah Andersen, Kelly McKernan, and Karla Ortiz. et al v. Stability AI Ltd. et al. Case No. 3:2023cv00201. US District Court for the Northern District of California., Jan 2023. 1, 2
- Dana Arad, Hadas Orgad, and Yonatan Belinkov. Refact: Updating text-to-image models by editing the text encoder. arXiv preprint arXiv:2306.00738 , 2023. 2
- David Bau, Steven Liu, Tongzhou Wang, Jun-Yan Zhu, and Antonio Torralba. Rewriting a deep generative model. In Computer Vision-ECCV 2020: 16th European Conference, Glasgow, UK, August 23-28, 2020, Proceedings, Part I 16 , pages 351-369. Springer, 2020. 2
- Praneeth Bedapudi. NudeNet: Neural nets for nudity detection and censoring, 2022. 2, 7
- Federico Bianchi, Pratyusha Kalluri, Esin Durmus, Faisal Ladhak, Myra Cheng, Debora Nozza, Tatsunori Hashimoto, Dan Jurafsky, James Zou, and Aylin Caliskan. Easily accessible text-to-image generation amplifies demographic stereotypes at large scale. In Proceedings of the 2023 ACM Conference on Fairness, Accountability, and Transparency , FAccT '23, page 1493-1504, New York, NY, USA, 2023. Association for Computing Machinery. 2
- Nicholas Carlini, Jamie Hayes, Milad Nasr, Matthew Jagielski, Vikash Sehwag, Florian Tramèr, Borja Balle, Daphne Ippolito, and Eric Wallace. Extracting training data from diffusion models. arXiv preprint arXiv:2301.13188 , 2023. 2
- Nicholas Carlini, Matthew Jagielski, Chiyuan Zhang, Nicolas Papernot, Andreas Terzis, and Florian Tramer. The privacy onion effect: Memorization is relative. Advances in Neural Information Processing Systems , 35:13263-13276, 2022. 1
- Jaemin Cho, Abhay Zala, and Mohit Bansal. Dall-eval: Probing the reasoning skills and social biases of text-to-image generative models. arXiv preprint arXiv:2202.04053 , 2022. 2
- Ching-Yao Chuang, Varun Jampani, Yuanzhen Li, Antonio Torralba, and Stefanie Jegelka. Debiasing vision-language models via biased prompts. arXiv preprint arXiv:2302.00070 , 2023. 1, 2, 6
- Jia Deng, Wei Dong, Richard Socher, Li-Jia Li, Kai Li, and Li Fei-Fei. Imagenet: A large-scale hierarchical image database. In 2009 IEEE conference on computer vision and pattern recognition , pages 248-255. Ieee, 2009. 5
- Lucas Dixon, John Li, Jeffrey Sorensen, Nithum Thain, and Lucy Vasserman. Measuring and mitigating unintended bias in text classification. In Proceedings of the 2018 AAAI/ACM Conference on AI, Ethics, and Society , pages 67-73, 2018. 1
- Kathleen C. Fraser, Svetlana Kiritchenko, and Isar Nejadgholi. A friendly face: Do text-to-image systems rely on stereotypes when the input is under-specified? In The AAAI-23 Workshop on Creative AI Across Modalities , 2023. 2
- Shreyansh Gandhi, Samrat Kokkula, Abon Chaudhuri, Alessandro Magnani, Theban Stanley, Behzad Ahmadi, Venkatesh Kandaswamy, Omer Ovenc, and Shie Mannor. Scalable detection of offensive and non-compliant content / logo in product images. In 2020 IEEE Winter Conference on Applications of Computer Vision (WACV) , pages 2236-2245, 2020. 2
- Rohit Gandikota, Joanna Materzy´ nska, Jaden Fiotto-Kaufman, and David Bau. Erasing concepts from diffusion models. In Proceedings of the 2023 IEEE International Conference on Computer Vision , 2023. 1, 2, 5, 7
- Kaiming He, Xiangyu Zhang, Shaoqing Ren, and Jian Sun. Deep residual learning for image recognition. In Proceedings of the IEEE conference on computer vision and pattern recognition , pages 770-778, 2016. 6
- Alvin Heng and Harold Soh. Selective amnesia: A continual learning approach to forgetting in deep generative models. arXiv preprint arXiv:2305.10120 , 2023. 2
- Jonathan Ho, Ajay Jain, and Pieter Abbeel. Denoising diffusion probabilistic models. Advances in Neural Information Processing Systems , 33:6840-6851, 2020. 2
- Jeremy Howard and Sylvain Gugger. Fastai: A layered api for deep learning. Information , 11(2):108, 2020. 5
- Tatum Hunter. Ai porn is easy to make now. for women, that's a nightmare., 2 2023. 1
- Surea I, Proxima Centauri B, Erratica, and Stephen Young. Image synthesis style studies, 7 2022. 5
- Sanghyun Kim, Seohyeon Jung, Balhae Kim, Moonseok Choi, Jinwoo Shin, and Juho Lee. Towards safe self-distillation of internet-scale text-to-image diffusion models. arXiv preprint arXiv:2307.05977 , 2023. 2, 5
- Nupur Kumari, Bingliang Zhang, Sheng-Yu Wang, Eli Shechtman, Richard Zhang, and Jun-Yan Zhu. Ablating concepts in text-to-image diffusion models. In Proceedings of the 2023 IEEE International Conference on Computer Vision , 2023. 1, 2, 5
- Gant Laborde. NSFW detection machine learning model, 2022. 2
- Tsung-Yi Lin, Michael Maire, Serge Belongie, James Hays, Pietro Perona, Deva Ramanan, Piotr Dollár, and C Lawrence Zitnick. Microsoft coco: Common objects in context. In Computer Vision-ECCV 2014: 13th European Conference, Zurich, Switzerland, September 6-12, 2014, Proceedings, Part V 13 , pages 740-755. Springer, 2014. 5
- Alexandra Sasha Luccioni, Christopher Akiki, Margaret Mitchell, and Yacine Jernite. Stable bias: Analyzing societal representations in diffusion models. arXiv preprint arXiv:2303.11408 , 2023. 1, 2
- Kevin Meng, David Bau, Alex Andonian, and Yonatan Belinkov. Locating and editing factual associations in gpt. Advances in Neural Information Processing Systems , 35:1735917372, 2022. 2
- Kevin Meng, Arnab Sen Sharma, Alex J Andonian, Yonatan Belinkov, and David Bau. Mass-editing memory in a transformer. In The Eleventh International Conference on Learning Representations , 2023. 2, 3, 4
- Alex Nichol, Prafulla Dhariwal, Aditya Ramesh, Pranav Shyam, Pamela Mishkin, Bob McGrew, Ilya Sutskever, and Mark Chen. Glide: Towards photorealistic image generation and editing with text-guided diffusion models. arXiv preprint arXiv:2112.10741 , 2021. 2
- Ryan O'Connor. Stable diffusion 1 vs 2 - what you need to know, 2022. 1
- Office of Management and Budget. Office of management and budget (omb) standards. U.S. Department of Health and Human Services, Jul 2022. 7
- Hadas Orgad, Bahjat Kawar, and Yonatan Belinkov. Editing implicit assumptions in text-to-image diffusion models. In Proceedings of the 2023 IEEE International Conference on Computer Vision , 2023. 2, 3, 4, 6, 7
- Alec Radford, Jong Wook Kim, Chris Hallacy, Aditya Ramesh, Gabriel Goh, Sandhini Agarwal, Girish Sastry, Amanda Askell, Pamela Mishkin, Jack Clark, et al. Learning transferable visual models from natural language supervision. In International conference on machine learning , pages 8748-8763. PMLR, 2021. 5
- Javier Rando, Daniel Paleka, David Lindner, Lennard Heim, and Florian Tramèr. Red-teaming the stable diffusion safety filter. arXiv preprint arXiv:2210.04610 , 2022. 2
- Robin Rombach. Stable diffusion 2.0 release, Nov 2022. 1
- Hadi Salman, Alaa Khaddaj, Guillaume Leclerc, Andrew Ilyas, and Aleksander Madry. Raising the cost of malicious ai-powered image editing. arXiv preprint arXiv:2302.06588 , 2023. 2
- Patrick Schramowski, Manuel Brack, Björn Deiseroth, and Kristian Kersting. Safe latent diffusion: Mitigating inappropriate degeneration in diffusion models. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition , pages 22522-22531, 2023. 1, 2, 7
- Preethi Seshadri, Sameer Singh, and Yanai Elazar. The bias amplification paradox in text-to-image generation. 2023. 2
- Riddhi Setty. Ai art generators hit with copyright suit over artists' images, 1 2023. 2
- Shawn Shan, Jenna Cryan, Emily Wenger, Haitao Zheng, Rana Hanocka, and Ben Y Zhao. Glaze: Protecting artists from style mimicry by text-to-image models. arXiv preprint arXiv:2302.04222 , 2023. 2
- SmithMano. Tutorial: How to remove the safety filter in 5 seconds, 8 2022. 2
- Jascha Sohl-Dickstein, Eric Weiss, Niru Maheswaranathan, and Surya Ganguli. Deep unsupervised learning using nonequilibrium thermodynamics. In International Conference on Machine Learning , pages 2256-2265. PMLR, 2015. 2
- Gowthami Somepalli, Vasu Singla, Micah Goldblum, Jonas Geiping, and Tom Goldstein. Diffusion art or digital forgery? investigating data replication in diffusion models. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition , pages 6048-6058, 2023. 2
- Gowthami Somepalli, Vasu Singla, Micah Goldblum, Jonas Geiping, and Tom Goldstein. Understanding and mitigating copying in diffusion models. arXiv preprint arXiv:2305.20086 , 2023. 2
- Lukas Struppek, Dominik Hintersdorf, and Kristian Kersting. The biased artist: Exploiting cultural biases via homoglyphs in text-guided image generation models. arXiv preprint arXiv:2209.08891 , 2022. 1, 2
- Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N Gomez, Łukasz Kaiser, and Illia Polosukhin. Attention is all you need. Advances in neural information processing systems , 30, 2017. 3
- Zihao Wang, Lin Gui, Jeffrey Negrea, and Victor Veitch. Concept algebra for text-controlled vision models. arXiv preprint arXiv:2302.03693 , 2023. 1, 2, 6
- Eric Zhang, Kai Wang, Xingqian Xu, Zhangyang Wang, and Humphrey Shi. Forget-me-not: Learning to forget in text-toimage diffusion models. arXiv preprint arXiv:2303.17591 , 2023. 2
- Richard Zhang, Phillip Isola, Alexei A Efros, Eli Shechtman, and Oliver Wang. The unreasonable effectiveness of deep features as a perceptual metric. In Proceedings of the IEEE conference on computer vision and pattern recognition , pages 586-595, 2018. 5, 7
- Jieyu Zhao, Tianlu Wang, Mark Yatskar, Vicente Ordonez, and Kai-Wei Chang. Gender bias in coreference resolution: Evaluation and debiasing methods. arXiv preprint arXiv:1804.06876 , 2018. 8

## GLOSSAR

- **Unified Concept Editing (UCE)** — a closed-form, training-free method for editing text-to-image diffusion models that can erase, debias, or moderate many concepts simultaneously while explicitly preserving specified concepts.
- **Erasing** — an edit type that maps a concept's cross-attention output to a different, generic concept (e.g., an artist's style to 'art') so the model no longer generates it.
- **Debiasing** — an edit type that adjusts the magnitude of a concept's output along attribute directions so the model generates the concept with desired attribute ratios (e.g., 50-50 gender).
- **Moderation** — an edit type that aligns a sensitive concept's output (e.g., 'nudity') with an unconditional prompt, reducing extreme attributes of that concept.
- **Preservation terms** — embeddings of concepts c_j ∈ P whose outputs the edit must keep unchanged, replacing TIME's generic regularization.
- **Canonical directions** — basis directions of the text embedding space added as preservation terms to guarantee the covariance matrix has full rank; preserving only these reduces UCE to TIME.
- **Implicit assumptions** — visual features a model assumes about objects in under-specified prompts (e.g., red roses, male doctors), as defined in TIME.
- **Cross-attention projections (W_k, W_v)** — the linear layers that project text embeddings to keys and values in the diffusion U-Net; the layers UCE edits.
- **Debiasing constants (α_i / α_p)** — per-concept, per-attribute scaling constants computed iteratively as η(R_curr − R_des) to reach desired attribute ratios.
- **Edit list / preserve list (E / P)** — the sets of concept embeddings to modify and to keep fixed during an edit.
- **TIME** — prior closed-form editing method for diffusion models that edits one implicit assumption at a time with generic regularization; a special case of UCE.
- **MEMIT** — prior closed-form editing method for language models; UCE generalizes it by solving for the weight update ΔW with added preservation terms from the diffusion vocabulary.
- **I2P benchmark** — a set of prompts (used here with 4703 images) covering inappropriate content categories, used to evaluate moderation.
- **WinoBias** — a dataset of professions used to evaluate gender debiasing, with deviation metric Δ = |p_desired − p_actual| / p_desired.
