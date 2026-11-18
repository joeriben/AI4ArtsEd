---
id: phunyaphibarn-et-al-2026-unconditional-priors-matter-improving-conditional-generation
titel: Unconditional Priors Matter!. Improving Conditional Generation of Fine-Tuned Diffusion Models
autor: "Prin Phunyaphibarn, Phillip Y. Lee, Jaihoon Kim, Minhyuk Sung"
jahr: 2026
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2503.20240"
status: published
checks: passed
review: passed
analyzed_at: "2026-11-15T11:14:49.837429+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: gedruckt
---

# Unconditional Priors Matter!. Improving Conditional Generation of Fine-Tuned Diffusion Models

## PROFIL

The article "Unconditional Priors Matter!. Improving Conditional Generation of Fine-Tuned Diffusion Models" was written by Prin Phunyaphibarn, Phillip Y. Lee, Jaihoon Kim, and Minhyuk Sung as a scholarly paper on diffusion models. Its subject is the quality of conditional generation in fine-tuned diffusion models that use Classifier-Free Guidance (CFG), and its claim is that fine-tuning degrades the "unconditional priors" of a model, which is a major, previously underappreciated cause of poor conditional generation; the authors propose a training-free remedy in which the fine-tuned model's unconditional noise prediction in the CFG formula is replaced with that of a separate pretrained diffusion model, which need not be the original base model and may even differ in architecture. The paper first sets out background on diffusion models, Tweedie's formula, DDIM sampling, and the CFG training and sampling scheme; then argues that poor unconditional priors harm conditional generation because CFG samples from a gamma-powered distribution in which approximation errors in the unconditional term propagate; and presents the proposed method as equivalent to sampling from a time-annealed distribution, grounded in the connection between energy-based models and diffusion models. It positions itself against Kynkäänniemi et al. on guidance limitations, extends Zhong et al.'s idea of using unconditional noise from an original model from small class-conditional DiTs to large-scale models across architectures and condition modalities, contrasts itself with Karras et al.'s Autoguidance, and extends noise-estimate merging relative to Diffusion Soup, Mix-of-Show, and Max-Fusion. Experiments cover five models — Zero-1-to-3, Versatile Diffusion, DiT, DynamiCrafter, and InstructPix2Pix — across single-condition and dual-condition CFG settings, with quantitative evaluations (LPIPS, PSNR, SSIM, FID, VBench, CLIP-based metrics), CFG-scale ablations, memory and speed measurements, and supplementary findings on unconditional quality via Inception Score. The conclusion states limitations: increased memory cost and inference overhead from loading a second model, and reduced effectiveness for adapter-based fine-tuning such as ControlNet and GLIGEN. The paper is usable in disciplines and situations of arts education involving generative AI for image and video creation — novel view synthesis, image variation, class-conditional generation, text-and-image-to-video, and instruction-based image editing.

## WISSEN

### Purpose and Thesis (p. 1–2)

This paper argues that fine-tuned conditional diffusion models suffer from degraded "unconditional priors," and that this degradation is a major, previously underappreciated cause of poor conditional generation quality when using Classifier-Free Guidance (CFG). The authors propose a training-free remedy: replace the unconditional noise prediction of a fine-tuned model in the CFG formula with the unconditional noise prediction from a separate pretrained diffusion model (typically the base model, but not necessarily). They validate the claim across five conditional diffusion models for image and video generation: Zero-1-to-3, Versatile Diffusion, DiT, DynamiCrafter, and InstructPix2Pix. The authors further note that this finding implies that when fine-tuning a diffusion model with additional conditioning using CFG, the unconditional noise does not need to be learned jointly with the conditional noise: whenever a pretrained unconditional diffusion model is available, the need to jointly learn both unconditional and conditional noise with the same noise prediction network is eliminated.

### Background: Diffusion Models and Classifier-Free Guidance (p. 3–4)

Diffusion models generate data by iteratively denoising samples from a Gaussian distribution. The reverse process is modeled as a Gaussian transition whose posterior mean can be reparameterized as a noise prediction task using Tweedie's formula; the predicted clean observation is denoted x₀|ₜ. DDIM sampling enables efficient, deterministic, non-Markovian denoising.

Classifier-Free Guidance (CFG) trains a single network to predict both conditional noise ε_θ(xₜ, c) and unconditional noise ε_θ(xₜ, ∅), by randomly replacing the condition c with a null condition ∅ during training (typically with a 5–20% drop rate). At sampling time, CFG combines the two predictions: ε_θ(xₜ, ∅) + γ(ε_θ(xₜ, c) − ε_θ(xₜ, ∅)), where γ is the guidance scale. Interpreted via score-based modeling, CFG samples from the gamma-powered distribution p_γ(xₜ|c) ∝ p(xₜ) p(c|xₜ)^γ; γ > 1 sharpens the mode corresponding to c, improving condition alignment and image quality.

### Argument: Poor Unconditional Priors Degrade Conditional Generation (p. 4–5)

CFG training is commonly used to fine-tune a pretrained "base model" (e.g., Stable Diffusion) into a "fine-tuned model" with new input conditions (camera poses, reference images, editing instructions). The authors observe a significant quality drop in unconditional generation with fine-tuned models, attributed to (1) the unconditional distribution being inherently more complex than the conditional one, and (2) only a small fraction of training iterations being devoted to the unconditional case due to the low condition-drop rate — an issue exacerbated by limited data or multiple rounds of fine-tuning.

Crucially, poor unconditional priors harm *conditional* generation: CFG samples from p_γ(xₜ|c) ∝ p(xₜ) p(c|xₜ)^γ, so approximation errors in p(xₜ) propagate to both terms. Under limited data or repeated fine-tuning, the model loses the rich unconditional prior of its base model.

### Proposed Method: Finding Richer Unconditional Priors (p. 4–5)

The fix is simple and training-free: in the CFG sampling step, replace the fine-tuned model's unconditional noise ε_θ(xₜ, ∅) with the base model's unconditional noise ε_ψ(xₜ, ∅), combining it with the fine-tuned model's conditional noise. Surprisingly, the unconditional noise need not come from the true base model — any pretrained diffusion model with good unconditional priors works, even one with different weights or a different architecture (e.g., using PixArt-α, a DiT, in place of a UNet base). Grounded in the connection between energy-based models and diffusion models, the method is equivalent to sampling from the time-annealed distribution p_ψ(xₜ)^(1−γ) p_θ(xₜ|c)^γ.

### Related Work (p. 2–3)

- **Guidance limitations**: Kynkäänniemi et al. showed CFG's application timesteps affect diversity; other works extend guidance beyond text conditions. Zhong et al. proposed using unconditional noise from the original model for fine-tuned DiTs, but only for small class-conditional DiTs; this paper extends the idea to large-scale models across architectures and condition modalities. Karras et al.'s Autoguidance uses an under-trained version of the same model conditioned on the same condition; in contrast, this method combines models with different condition modalities and shows that fine-tuned unconditional degradation *hurts* rather than helps.
- **Merging diffusion models**: Diffusion Soup (weight merging), Mix-of-Show (LoRA merging), Max-Fusion (feature merging), and noise-estimate merging across models; this work extends noise merging to improve CFG-based generation of fine-tuned models.

### Experiments: Single-Condition CFG (p. 5–6)

**Zero-1-to-3** (novel view synthesis, fine-tuned from SD Image Variations, itself from SD1.4; evaluated on Google Scanned Objects with LPIPS, PSNR, SSIM; 50 DDIM steps, γ = 5.0):
- Zero-1-to-3: LPIPS 0.182, PSNR 16.647, SSIM 0.824
- Ours w/ SD1.4: 0.163 / 17.514 / 0.842
- Ours w/ SD2.1: 0.158 / 17.801 / 0.848 (best)
- Ours w/ PixArt-α: 0.169 / 17.069 / 0.825

Qualitatively, the method improves lighting, reduces color saturation and shape distortions.

**Versatile Diffusion** (image variations, progressively fine-tuned from SD1.4 in three stages; evaluated on COCO-Captions with FID, FD_DINOv2, CLIP-I, DINOv2; γ = 2.0):
- VD: FID 8.38, FD_DINOv2 167.65, CLIP-I 0.93, DINOv2 0.91
- Ours w/ SD1.4: 6.68 / 156.77 / 0.94 / 0.92
- Ours w/ SD2.1: 7.80 / 151.48 / 0.94 / 0.92
- Ours w/ PixArt-α: 6.29 / 148.48 / 0.94 / 0.92 (best FID and FD_DINOv2)

The method corrects oversaturation and distorted objects while maintaining condition alignment.

**DiT** (class-conditional; DiT-XL/2 fine-tuned by the authors on SUN397, Food101, Caltech101; FID-5k, γ = 1.5):
- SUN397: 17.12 → 14.51; Food101: 18.31 → 17.67; Caltech101: 24.05 → 24.15 (no improvement on the smallest dataset, Caltech101, which is over 10× smaller than SUN397 and Food101, giving the model sufficient time to fit despite the 10% drop rate). Larger fine-tuning datasets show larger benefits, corroborating that unconditional-prior degradation is amplified by limited computational budget.

### Experiments: Dual-Condition CFG (p. 7–8)

Dual-condition models (e.g., InstructPix2Pix, DynamiCrafter) have two unconditional terms trained via condition dropout: ε_θ(xₜ, ∅, ∅) and ε_θ(xₜ, c₁, ∅). The method replaces only the fully unconditional term ε_θ(xₜ, ∅, ∅) with the base model's noise, so improvements are smaller than in the single-condition case.

**DynamiCrafter** (text-and-image-to-video, fine-tuned from VideoCrafter-T2V; evaluated with VBench-I2V; γ_T = 7.5, γ_I = 1.5): the method outperforms the baseline in 7 of 9 metrics (e.g., Subject Consistency 90.80 → 91.49; Background Consistency 96.73 → 97.03; Aesthetic Quality 57.06 → 57.51), with slightly lower Dynamic Degree (59.59 → 57.32) and Imaging Quality (64.10 → 63.15). Note: the original paper's γ_T = γ_I = 7.5 yields mostly static videos (dynamic degree 40.57% on VBench); the authors' chosen scales give 59.59%.

**InstructPix2Pix** (instruction-based image editing, fine-tuned from SD1.5; evaluated on EditEvalv2 with CLIP image similarity C-I, CLIP text alignment C-T, CLIP Directional Similarity C-D, Image Reward IR, PickScore PS; 100 DDIM steps, γ_I = 1.5, γ_T = 7.5):
- IP2P: C-I 0.909, C-T 0.294, C-D 0.174, IR −0.510
- Ours w/ SD1.5: 0.911 / 0.291 / 0.186 / −0.460 / PS 0.514
- Ours w/ SD2.1: 0.913 / 0.290 / 0.184 / −0.464 / PS 0.518
- Ours w/ PixArt-α: 0.915 / 0.297 / 0.185 / −0.363 / PS 0.532 (best)

The method improves prompt alignment and identity preservation, with slight underperformance in CLIP-T for SD1.5 and SD2.1.

### Conclusion and Limitations (p. 8)

The paper presents a training-free approach to improving CFG-based fine-tuned conditional diffusion models by replacing low-quality unconditional noise with richer unconditional noise from a separate pretrained model, which may differ in weights and architecture from the original base. Limitations: loading a second model increases memory cost and prevents parallelized computation, causing slight inference overhead; the method is less effective for adapter-based fine-tuning (ControlNet, GLIGEN), which exhibits less unconditional-prior degradation — identifying priors for such techniques is future work.

### Supplementary Findings (p. 12–18)

- **Quantitative unconditional quality** (Inception Score on 5,000 unconditional samples): SD1.4 14.085, SD2.1 12.640, PixArt-α 9.224, versus fine-tuned models Versatile Diffusion 2.704, Zero-1-to-3 9.140, InstructPix2Pix 5.852 — confirming base models have better unconditional generation.
- **Experimental details**: all experiments use DDIM; when variance schedules differ, the fine-tuned model's schedule is the reference and the closest available base-model variance is chosen. Zero-1-to-3: six views per GSO object, azimuths 60° apart. Versatile Diffusion: 30,000 COCO-Captions 2014 validation images as conditions. DiT: 20,000 fine-tuning steps, batch size 64, learning rate 0.0001; FID computed three times, minimum reported.
- **CFG-scale ablations**: the method consistently improves results across scales (Zero-1-to-3: γ from 3.0 to 8.0; Versatile Diffusion: γ from 2.5 to 7.5).
- **Memory and speed** (RTX3090, float32): e.g., Zero-1-to-3 memory 4.93 → 10.06 GB, speed 2.92 → 3.59 s/sample; DynamiCrafter 19.17 → 29.03 GB, 125.15 → 142.84 s/sample — inference speed only slightly affected.
- Additional qualitative results are provided for all five models.

### Figures (p. 1–18)

*Fig. 1 (p. 1):* Unconditional Priors Matter in CFG-Based Conditional Generation. Fine-tuned conditional diffusion models often show drastic degradation in their unconditional priors, adversely affecting conditional generation when using techniques such as CFG [28]. We demonstrate that leveraging a diffusion model with a richer unconditional prior and combining its unconditional noise prediction with the conditional noise prediction from the fine-tuned model can lead to substantial improvements in conditional generation quality. This is demonstrated across diverse conditional diffusion models including Zero-1-to-3 [46], Versatile Diffusion [64], InstructPix2Pix [7], and DynamiCrafter [62]. — This is a diagram from a document, arranged as a two-by-two grid of comparison panels. Each panel has a heading—"Zero-1-to-3: Novel View Synthesis," "Versatile Diffusion: Image Variations," "InstructPix2Pix: Image Editing," and "DynamiCrafter: Image+Text-to-Video"—and shows an "Input" image, sometimes with a "120°" rotation arrow or a text instruction, above result columns labeled with the baseline method and "+ Ours." The panels display generated images of a cat figurine and a mug, variations of a street scene with a red scooter and a blue lion, edited shoes and a fairy, and film-strip frames of a figure carrying plants.

*Fig. 2 (p. 5):* Unconditional samples from different diffusion models. Stable Diffusion [4], which often serves as the base model for finetuning conditional diffusion models, generates plausible images, whereas other fine-tuned diffusion models fail to sample realistic images. — This figure displays a grid of eight images arranged in two rows and four columns, with each column headed by a text label. The leftmost column, labeled "Stable Diffusion v1.4 [52]", contains four realistic photographs depicting furniture and interior or exterior spaces. The second column, labeled "Versatile Diffusion [64]", shows two dark gray, nearly featureless images. The third column, labeled "Zero 1-to-3 [46]", presents four images of three-dimensional rendered objects against plain backgrounds. The rightmost column, labeled "InstructPix2Pix [7]", contains four blurry, indistinct images in muted brown and gray tones.

*Fig. 3 (p. 6):* Novel View Synthesis with Zero-1-to-3 [46] . Outputs from Zero-1-to-3 often show inaccuracies in lighting or shape distortions during novel view synthesis. By incorporating unconditional noise predictions from Stable Diffusion [52] or PixArtα [10], our method achieves clear improvements in output quality. — The picture is a table-like figure panel in a document, showing a grid of computer-rendered images arranged in four rows and six columns. The column headers read "Input Image", "Ground Truth", "Zero-1-to-3 (Baseline)", "w/ SD1.4 (Ours)", "w/ SD2.1 (Ours)", and "w/ PixArt-α (Ours)". The four rows depict, from top to bottom, a castle-like block structure, a tall gray rectangular panel, a purple shoe, and a tray holding several small objects. Each cell contains a single rendered view of the row's object, and the images differ in appearance from column to column.

*Fig. 4 (p. 7):* Image Variations with Versatile Diffusion [64]. Versatile Diffusion often suffers from style and detail degradation-excessive saturation (rows 1 and 3) or loss of key content (row 2). In contrast, our method, leveraging SD1.4 , SD2.1 , or PixArtα as unconditional priors, achieves noticeable improvements in performance. — This is a figure in a document: a comparison grid of images with three rows and five columns. The legible header row reads “Input Image”, “VD (Baseline)”, “w/ SD1.4 (Ours)”, “w/ SD2.1 (Ours)”, and “w/ PixArt-α (Ours)”. The first row shows night lake-and-mountain scenes, the second row shows stone faces with waterfalls set in greenery, and the third row shows large green leaves on white waterfall cliffs, with each column presenting a different variation of the input image.

*Image 5 (p. 8):* — This is a figure from a document that compares generated video frames in a two-row layout. The left column labeled "Input" contains two photographs with text prompts: the top shows people riding bicycles with the caption "a group of people riding bikes down a street," and the bottom shows a man wearing a large sombrero and dark suit with the caption "A man in a black suit and a sombrero, shouting loudly." To the right under "Generated Frames," each input is followed by two horizontal sequences of five frames each, where the upper sequence is labeled "DynamicCrafter" and the lower sequence is labeled "w/ VideoCrafter1 (Ours)." _(Lettering in the image, read by the image model, not confirmed: "a group of people riding bikes down a street,", "A man in a black suit and a sombrero, shouting loudly.", "DynamicCrafter", "w/ VideoCrafter1 (Ours).")_

*Image 6 (p. 8):* — This is a screenshot of a comparison table from a document displaying text-guided image editing results. The table has five columns with the headers "Input Image", "IP2P (Baseline)", "w/ SD1.5 (Ours)", "w/ SD2.1 (Ours)", and "w/ PixArt-α (Ours)", and three rows labeled with the editing instructions "Make the gown crystal", "turn the kitten into a sculpture", and "change the woman to a storm-trooper". Each row shows an original input photograph in the first column followed by four edited versions of that photograph produced by the different methods.

*Fig. 7 (p. 14):* Novel View Synthesis with Zero-1-to-3 [46] . Zero-1-to-3 tends to produce views that have inaccurate lighting, coloring, or shape. Combining Zero-1-to-3 with the unconditional noise from SD1.4 , SD2.1 , or PixArtα corrects these inaccuracies. — This is a grid of rendered 3D object images arranged in nine rows and six columns, comparing novel view synthesis outputs. The column headers read "Input Image", "Ground Truth", "Zero-1-to-3 (Baseline)", "w/ SD1.4 (Ours)", "w/ SD2.1 (Ours)", and "w/ PixArt-α (Ours)". Each row depicts a different object—a red high-heeled shoe, a packaged product, a colorful toy vehicle, a yellow toy truck, a blue-handled basket, a stack of blocks, a black whale, a purple bench, and a gray shoe—with red rectangular outlines highlighting regions in three of the images in the baseline column.

*Fig. 8 (p. 15):* Image Variations with Versatile Diffusion [64]. Images generated from Versatile Diffusion tend to be oversaturated and distorted. Combining Versatile Diffusion with the unconditional noise predictions from SD1.4 , SD2.1 , or PixArtα corrects these artifacts. 15 — The picture is a comparison grid of six rows and five columns of generated images. The column headers read “Input Image,” “VD (Baseline),” “w/ SD1.4 (Ours),” “w/ SD2.1 (Ours),” and “w/ PixArt-α (Ours).” The rows show a white cat in a bowl, a church interior with red rectangles around a wall cross, a cloud lion, a green leafy face, a child in a yellow coat with a red balloon before a volcano, and an ocean wave.

*Fig. 9 (p. 16):* Class-conditional generation with DiT [50] . Class-conditional generation using DiT fine-tuned on SUN397 [61], Food101 [6], and Caltech101 [24]. — The image is a grid of color photographs arranged in three vertical groups, each headed by a text label. The left group is labeled "SUN397" and shows scene photographs including churches, alleyways, parks, arcades, a ferris wheel, and buildings. The middle group is labeled "Food101" and displays various prepared dishes such as pastries, salads, meat entrees, egg dishes, and chocolate desserts. The right group is labeled "Caltech101" and contains photographs of human faces, a leopard, motorcycles, an accordion, an airplane, an anchor, an ant, and a wooden barrel.

*Fig. 10 (p. 17):* Image-to-Video Generation with DynamiCrafter [62]. Our method is more temporally consistent (number of horses in the first video and train color in the second video) and less distorted (hand and face in the last video). — This is a figure from a document: a comparison grid with three horizontal example blocks. Each block shows an “Input” image and a quoted prompt on the left, and “Generated Frames” on the right, with an upper row labeled “DynamiCrafter” and a lower row labeled “w/ VideoCrafter1 (Ours)”. The legible prompts read “a couple of horses are running in the dirt.”, “a train traveling down tracks through the woods with leaves on the ground”, and “two women eating pizza at a restaurant.” The visible scenes are black-and-white horses running in dust, a train on curved tracks through woods with fallen leaves, and two women eating at a restaurant. _(Lettering in the image, read by the image model, not confirmed: “w/ VideoCrafter1 (Ours)”, “a couple of horses are running in the dirt.”, “a train traveling down tracks through the woods with leaves on the ground”, “two women eating pizza at a restaurant.”)_

*Image 11 (p. 18):* — This is a screenshot of a figure in a document, laid out as a table with five columns and five rows of pictures. The column headings are "Input Image", "IP2P (Baseline)", "w/ SD1.5 (Ours)", "w/ SD2.1 (Ours)", and "w/ PixArt-α (Ours)". Above each row is a quoted instruction: "Change the horses to unicorns", "Replace the spaceship with an eagle", "Change the weather to sunny", "Change the beach to grass in the painting", and "Change to a kids crayon drawing". Each row shows one input picture on the left and four result pictures to its right depicting horses, a large bird over a standing figure, a city skyline, two people in a grassy field, and a bearded robed figure; in the bottom row, the second result picture has a small red rectangular outline around the figure's head.

<!-- quelle: Improving Conditional Generation of Fine-Tuned Diffusion Models (p. 1–18) -->

## LITERATUR

<!-- quelle: References (p. 9–11) -->

- Donghoon Ahn, Hyoungwon Cho, Jaewon Min, Wooseok Jang, Jungwoo Kim, SeonHwa Kim, Hyun Hee Park, Kyong Hwan Jin, and Seungryong Kim. Self-rectifying diffusion sampling with perturbed-attention guidance. In ECCV , 2024. 2
- Omer Bar-Tal, Lior Yariv, Yaron Lipman, and Tali Dekel. Multidiffusion: Fusing diffusion paths for controlled image generation. 2023. 3
- Benjamin Biggs, Arjun Seshadri, Yang Zou, Achin Jain, Aditya Golatkar, Yusheng Xie, Alessandro Achille, Ashwin Swaminathan, and Stefano Soatto. Diffusion soup: Model merging for text-to-image diffusion models. In ECCV , 2024. 3
- Andreas Blattmann, Tim Dockhorn, Sumith Kulal, Daniel Mendelevitch, Maciej Kilian, Dominik Lorenz, Yam Levi, Zion English, Vikram Voleti, Adam Letts, et al. Stable video diffusion: Scaling latent video diffusion models to large datasets. arXiv preprint arXiv:2311.15127 , 2023. 2, 5
- Andreas Blattmann, Robin Rombach, Huan Ling, Tim Dockhorn, Seung Wook Kim, Sanja Fidler, and Karsten Kreis. Align your latents: High-resolution video synthesis with latent diffusion models. In CVPR , 2023. 2
- Lukas Bossard, Matthieu Guillaumin, and Luc Van Gool. Food-101-mining discriminative components with random forests. In Computer vision-ECCV 2014: 13th European conference, zurich, Switzerland, September 6-12, 2014, proceedings, part VI 13 , pages 446-461. Springer, 2014. 6, 12, 16
- Tim Brooks, Aleksander Holynski, and Alexei A Efros. Instructpix2pix: Learning to follow image editing instructions. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition , pages 18392-18402, 2023. 1, 2, 4, 5, 7, 8, 13, 18
- Weilin Cai, Juyong Jiang, Fan Wang, Jing Tang, Sunghun Kim, and Jiayi Huang. A survey on mixture of experts. arXiv preprint arXiv:2407.06204 , 2024. 3
- Haoxin Chen, Menghan Xia, Yingqing He, Yong Zhang, Xiaodong Cun, Shaoshu Yang, Jinbo Xing, Yaofang Liu, Qifeng Chen, Xintao Wang, et al. Videocrafter1: Open diffusion models for high-quality video generation. arXiv preprint arXiv:2310.19512 , 2023. 7
- Junsong Chen, YU Jincheng, GE Chongjian, Lewei Yao, Enze Xie, Zhongdao Wang, James Kwok, Ping Luo, Huchuan Lu, and Zhenguo Li. Pixartα : Fast training of diffusion transformer for photorealistic text-to-image synthesis. In The Twelfth International Conference on Learning Representations . 5, 6
- Ziyang Chen, Daniel Geng, and Andrew Owens. Images that sound: Composing images and sounds on a single canvas. In NeurIPS , 2024. 3, 5
- VBench Contributors. Vbench. GitHub repository , 2023. 7
- Jade Copet, Felix Kreuk, Itai Gat, Tal Remez, David Kant, Gabriel Synnaeve, Yossi Adi, and Alexandre D´ efossez. Simple and controllable music generation. In NeurIPS , 2023. 2
- Jia Deng, Wei Dong, Richard Socher, Li-Jia Li, Kai Li, and Li Fei-Fei. Imagenet: A large-scale hierarchical image database. In 2009 IEEE conference on computer vision and pattern recognition , pages 248-255. Ieee, 2009. 12
- Prafulla Dhariwal and Alexander Nichol. Diffusion models beat gans on image synthesis. Advances in neural information processing systems , 34:8780-8794, 2021. 2, 3
- Laura Downs, Anthony Francis, Nate Koenig, Brandon Kinman, Ryan Hickman, Krista Reymann, Thomas B McHugh, and Vincent Vanhoucke. Google scanned objects: A highquality dataset of 3d scanned household items. In 2022 International Conference on Robotics and Automation (ICRA) , pages 2553-2560. IEEE, 2022. 5, 12
- Yilun Du and Leslie Kaelbling. Compositional generative modeling: A single model is not all you need. 2024. 3
- Yilun Du, Conor Durkan, Robin Strudel, Joshua B Tenenbaum, Sander Dieleman, Rob Fergus, Jascha Sohl-Dickstein, Arnaud Doucet, and Will Sussman Grathwohl. Reduce, reuse, recycle: Compositional generation with energy-based diffusion models and mcmc. In International conference on machine learning , pages 8489-8510. PMLR, 2023. 3
- Bradley Efron. Tweedie's formula and selection bias. Journal of the American Statistical Association , 106(496):16021614, 2011. 3
- Rohit Gandikota, Joanna Materzynska, Jaden Fiotto-Kaufman, and David Bau. Erasing concepts from diffusion models. In ICCV , 2023. 3, 5
- Daniel Geng, Inbum Park, and Andrew Owens. Visual anagrams: Generating multi-view optical illusions with diffusion models. In CVPR , 2024. 3
- Daniel Geng, Inbum Park, and Andrew Owens. Factorized diffusion: Perceptual illusions by noise decomposition. In ECCV , 2024. 3
- Ian Goodfellow, Jean Pouget-Abadie, Mehdi Mirza, Bing Xu, David Warde-Farley, Sherjil Ozair, Aaron Courville, and Yoshua Bengio. Generative adversarial nets. In NeurIPS , 2014. 2
- Gregory Griffin, Alex Holub, Pietro Perona, et al. Caltech256 object category dataset. Technical report, Technical Report 7694, California Institute of Technology Pasadena, 2007. 6, 12, 16
- Yuchao Gu, Xintao Wang, Jay Zhangjie Wu, Yujun Shi, Yunpeng Chen, Zihan Fan, Wuyou Xiao, Rui Zhao, Shuning Chang, Weijia Wu, et al. Mix-of-show: Decentralized lowrank adaptation for multi-concept customization of diffusion models. In NeurIPS , 2023. 3
- Jack Hessel, Ari Holtzman, Maxwell Forbes, Ronan Le Bras, and Yejin Choi. Clipscore: A reference-free evaluation metric for image captioning. arXiv preprint arXiv:2104.08718 , 2021. 6, 8
- Martin Heusel, Hubert Ramsauer, Thomas Unterthiner, Bernhard Nessler, and Sepp Hochreiter. Gans trained by a two time-scale update rule converge to a local nash equilibrium. In NeurIPS , 2017. 6
- Jonathan Ho and Tim Salimans. Classifier-free diffusion guidance. In NeurIPS 2021 Workshop on Deep Generative Models and Downstream Applications , 2021. 1, 2, 3, 4
- Jonathan Ho, Ajay Jain, and Pieter Abbeel. Denoising diffusion probabilistic models. Advances in neural information processing systems , 33:6840-6851, 2020. 2, 3
- Jonathan Ho, Tim Salimans, Alexey Gritsenko, William Chan, Mohammad Norouzi, and David J Fleet. Video diffusion models. NeurIPS , 2022. 2
- Susung Hong, Gyuseong Lee, Wooseok Jang, and Seungryong Kim. Improving sample quality of diffusion models using self-attention guidance. In ICCV , 2023. 2
- Edward J Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, Yuanzhi Li, Shean Wang, Lu Wang, and Weizhu Chen. Lora: Low-rank adaptation of large language models. In arXiv preprint arXiv:2106.09685 , 2021. 3
- Rongjie Huang, Jiawei Huang, Dongchao Yang, Yi Ren, Luping Liu, Mingze Li, Zhenhui Ye, Jinglin Liu, Xiang Yin, and Zhou Zhao. Make-an-audio: Text-to-audio generation with prompt-enhanced diffusion models. 2023. 2
- Yi Huang, Jiancheng Huang, Yifan Liu, Mingfu Yan, Jiaxi Lv, Jianzhuang Liu, Wei Xiong, He Zhang, Shifeng Chen, and Liangliang Cao. Diffusion model-based image editing: A survey. arXiv preprint arXiv:2402.17525 , 2024. 7, 13
- Ziqi Huang, Yinan He, Jiashuo Yu, Fan Zhang, Chenyang Si, Yuming Jiang, Yuanhan Zhang, Tianxing Wu, Qingyang Jin, Nattapol Chanpaisit, et al. Vbench: Comprehensive benchmark suite for video generative models. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition , pages 21807-21818, 2024. 7, 13
- Justin. Experiments with stable diffusion. https: / / github . com / justinpinkney / stable diffusion . 4, 5
- Tero Karras, Miika Aittala, Timo Aila, and Samuli Laine. Elucidating the design space of diffusion-based generative models. In Proc. NeurIPS , 2022. 12
- Tero Karras, Miika Aittala, Tuomas Kynk¨ a¨ anniemi, Jaakko Lehtinen, Timo Aila, and Samuli Laine. Guiding a diffusion model with a bad version of itself. arXiv preprint arXiv:2406.02507 , 2024. 2, 4
- Diederik P Kingma. Auto-encoding variational bayes. arXiv preprint arXiv:1312.6114 , 2013. 2
- Yuval Kirstain, Adam Polyak, Uriel Singer, Shahbuland Matiana, Joe Penna, and Omer Levy. Pick-a-pic: An open dataset of user preferences for text-to-image generation. In NeurIPS , 2023. 8
- Tuomas Kynk¨ a¨ anniemi, Miika Aittala, Tero Karras, Samuli Laine, Timo Aila, and Jaakko Lehtinen. Applying guidance in a limited interval improves sample and distribution quality in diffusion models. arXiv preprint arXiv:2404.07724 , 2024. 2
- Yuheng Li, Haotian Liu, Qingyang Wu, Fangzhou Mu, Jianwei Yang, Jianfeng Gao, Chunyuan Li, and Yong Jae Lee.
- Gligen: Open-set grounded text-to-image generation. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition , pages 22511-22521, 2023. 8
- Tsung-Yi Lin, Michael Maire, Serge Belongie, James Hays, Pietro Perona, Deva Ramanan, Piotr Doll´ ar, and C Lawrence Zitnick. Microsoft coco: Common objects in context. In Computer Vision-ECCV 2014: 13th European Conference, Zurich, Switzerland, September 6-12, 2014, Proceedings, Part V 13 , pages 740-755. Springer, 2014. 6, 12
- Haohe Liu, Yi Yuan, Xubo Liu, Xinhao Mei, Qiuqiang Kong, Qiao Tian, Yuping Wang, Wenwu Wang, Yuxuan Wang, and Mark D Plumbley. Audioldm 2: Learning holistic audio generation with self-supervised pretraining. IEEE/ACM Transactions on Audio, Speech, and Language Processing , 2024. 2
- Nan Liu, Shuang Li, Yilun Du, Antonio Torralba, and Joshua B Tenenbaum. Compositional visual generation with composable diffusion models. In ECCV , 2022. 5
- Ruoshi Liu, Rundi Wu, Basile Van Hoorick, Pavel Tokmakov, Sergey Zakharov, and Carl Vondrick. Zero-1-to3: Zero-shot one image to 3d object. In Proceedings of the IEEE/CVF international conference on computer vision , pages 9298-9309, 2023. 1, 2, 4, 5, 6, 8, 12, 13, 14
- Nithin Gopalakrishnan Nair, Wele Gedara Chaminda Bandara, and Vishal M Patel. Unite and conquer: Plug & play multi-modal synthesis using diffusion models. In CVPR , 2023. 3, 5
- Nithin Gopalakrishnan Nair, Jeya Maria Jose Valanarasu, and Vishal M Patel. Maxfusion: Plug&play multi-modal generation in text-to-image diffusion models. In ECCV , 2024. 3
- Maxime Oquab, Timoth´ ee Darcet, Th´ eo Moutakanni, Huy Vo, Marc Szafraniec, Vasil Khalidov, Pierre Fernandez, Daniel Haziza, Francisco Massa, Alaaeldin El-Nouby, et al. Dinov2: Learning robust visual features without supervision. arXiv preprint arXiv:2304.07193 , 2023. 6
- William Peebles and Saining Xie. Scalable diffusion models with transformers. In Proceedings of the IEEE/CVF International Conference on Computer Vision , pages 4195-4205, 2023. 2, 5, 6, 12, 16
- Dustin Podell, Zion English, Kyle Lacey, Andreas Blattmann, Tim Dockhorn, Jonas M¨ uller, Joe Penna, and Robin Rombach. Sdxl: Improving latent diffusion models for high-resolution image synthesis. In ICLR , 2024.
- Robin Rombach, Andreas Blattmann, Dominik Lorenz, Patrick Esser, and Bj¨ orn Ommer. High-resolution image synthesis with latent diffusion models. In Proceedings of the IEEE/CVF conference on computer vision and pattern recognition , pages 10684-10695, 2022. 2, 4, 5, 6
- Chitwan Saharia, William Chan, Saurabh Saxena, Lala Li, Jay Whang, Emily L Denton, Kamyar Ghasemipour, Raphael Gontijo Lopes, Burcu Karagol Ayan, Tim Salimans, et al. Photorealistic text-to-image diffusion models with deep language understanding. Advances in neural information processing systems , 35:36479-36494, 2022. 2
- Tim Salimans, Ian Goodfellow, Wojciech Zaremba, Vicki Cheung, Alec Radford, and Xi Chen. Improved techniques
- for training gans. Advances in neural information processing systems , 29, 2016. 12
- Ruoxi Shi, Hansheng Chen, Zhuoyang Zhang, Minghua Liu, Chao Xu, Xinyue Wei, Linghao Chen, Chong Zeng, and Hao Su. Zero123++: a single image to consistent multi-view diffusion base model. arXiv preprint arXiv:2310.15110 , 2023. 4
- Jascha Sohl-Dickstein, Eric Weiss, Niru Maheswaranathan, and Surya Ganguli. Deep unsupervised learning using nonequilibrium thermodynamics. 2015. 2, 3
- Jiaming Song, Chenlin Meng, and Stefano Ermon. Denoising diffusion implicit models. In ICLR , 2021. 3, 12
- Yang Song and Stefano Ermon. Generative modeling by estimating gradients of the data distribution. In NeurIPS , 2019. 3
- Yang Song, Jascha Sohl-Dickstein, Diederik P Kingma, Abhishek Kumar, Stefano Ermon, and Ben Poole. Score-based generative modeling through stochastic differential equations. In International Conference on Learning Representations , 2021. 2, 3
- George Stein, Jesse Cresswell, Rasa Hosseinzadeh, Yi Sui, Brendan Ross, Valentin Villecroze, Zhaoyan Liu, Anthony L Caterini, Eric Taylor, and Gabriel Loaiza-Ganem. Exposing flaws of generative model evaluation metrics and their unfair treatment of diffusion models. Advances in Neural Information Processing Systems , 36, 2024. 6
- Jianxiong Xiao, James Hays, Krista A Ehinger, Aude Oliva, and Antonio Torralba. Sun database: Large-scale scene recognition from abbey to zoo. In 2010 IEEE computer society conference on computer vision and pattern recognition , pages 3485-3492. IEEE, 2010. 6, 12, 16
- Jinbo Xing, Menghan Xia, Yong Zhang, Haoxin Chen, Wangbo Yu, Hanyuan Liu, Gongye Liu, Xintao Wang, Ying Shan, and Tien-Tsin Wong. Dynamicrafter: Animating open-domain images with video diffusion priors. In European Conference on Computer Vision , pages 399-417. Springer, 2025. 1, 5, 7, 8, 13, 17
- Jiazheng Xu, Xiao Liu, Yuchen Wu, Yuxuan Tong, Qinkai Li, Ming Ding, Jie Tang, and Yuxiao Dong. Imagereward: Learning and evaluating human preferences for textto-image generation. In NeurIPS , 2023. 8
- Xingqian Xu, Zhangyang Wang, Gong Zhang, Kai Wang, and Humphrey Shi. Versatile diffusion: Text, images and variations all in one diffusion model. In Proceedings of the IEEE/CVF International Conference on Computer Vision , pages 7754-7765, 2023. 1, 2, 4, 5, 7, 8, 12, 13, 15
- Enneng Yang, Li Shen, Guibing Guo, Xingwei Wang, Xiaochun Cao, Jie Zhang, and Dacheng Tao. Model merging in llms, mllms, and beyond: Methods, theories, applications and opportunities. arXiv preprint arXiv:2408.07666 , 2024. 3
- David Junhao Zhang, Jay Zhangjie Wu, Jia-Wei Liu, Rui Zhao, Lingmin Ran, Yuchao Gu, Difei Gao, and Mike Zheng Shou. Show-1: Marrying pixel and latent diffusion models for text-to-video generation. IJCV , 2024. 2
- Lvmin Zhang, Anyi Rao, and Maneesh Agrawala. Adding conditional control to text-to-image diffusion models. In ICCV , 2023. 2, 8
- Qinsheng Zhang, Jiaming Song, Xun Huang, Yongxin Chen, and Ming-Yu Liu. Diffcollage: Parallel generation of large content with diffusion models. In CVPR , 2023. 3
- Richard Zhang, Phillip Isola, Alexei A Efros, Eli Shechtman, and Oliver Wang. The unreasonable effectiveness of deep features as a perceptual metric. In CVPR , 2018. 5, 13
- Jincheng Zhong, XiangCheng Zhang, Jianmin Wang, and Mingsheng Long. Domain guidance: A simple transfer approach for a pre-trained diffusion model. In The Thirteenth International Conference on Learning Representations . 2

## GLOSSAR

- **Unconditional prior** — the quality of a model's unconditional noise prediction / unconditional distribution modeling, which the authors show degrades during fine-tuning and harms conditional generation.
- **Base model** — the pretrained diffusion model (e.g., Stable Diffusion) from which a conditional model is fine-tuned.
- **Fine-tuned model** — the conditional diffusion model obtained by fine-tuning a base model with CFG training to incorporate new conditions.
- **CFG condition dropout** — the training practice of replacing the condition with a null condition with small probability (typically 5–20%), which limits the bandwidth for learning unconditional noise.
- **Gamma-powered distribution** — p_γ(xₜ|c) := p(xₜ)(p(xₜ|c)/p(xₜ))^γ, the distribution CFG implicitly samples from.
- **Unconditional noise replacement** — the proposed training-free fix of substituting the fine-tuned model's unconditional noise in CFG with that of a separate pretrained diffusion model.
- **Single-condition CFG formulation** — CFG with one condition, sampling with ε_θ(xₜ, ∅) + γ(ε_θ(xₜ, c) − ε_θ(xₜ, ∅)).
- **Dual-condition CFG formulation** — CFG with two conditions (c₁, c₂), involving two unconditional terms ε_θ(xₜ, ∅, ∅) and ε_θ(xₜ, c₁, ∅); the method replaces only the fully unconditional term.
- **Time-annealed distribution** — p_ψ(xₜ)^(1−γ) p_θ(xₜ|c)^γ, the per-timestep distribution the combined method is equivalent to sampling from, via the EBM–diffusion connection.
