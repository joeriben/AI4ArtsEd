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
analyzed_at: "2026-07-31T10:12:59.435354+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Circumventing Concept Erasure Methods For Text-to-Image Generative Models

## PROFIL

This essay argues that post hoc concept erasure in text-to-image generative models provides a false sense of security, as targeted concepts are not fully excised from the sanitized weights. It sets itself against the assumption that methods like Erased Stable Diffusion permanently remove sensitive concepts and are difficult to circumvent. By introducing Concept Inversion (CI), the authors demonstrate that an adversary can learn special soft-prompt word embeddings to retrieve "erased" concepts—such as artistic styles or likenesses—without altering the model weights. For arts education, this finding indicates that AI safety filters and style-blocking mechanisms in generative tools cannot be reliably depended upon to prevent the reproduction of copyrighted or inappropriate material in educational settings.

## WISSEN

### Problem Framing and Thesis

Text-to-image models produce copyrighted, biased, and unsafe content. Dataset pre-filtering is imperfect (LAION-400M retains offensive samples after NSFW filtering), and full retraining is costly, motivating post hoc concept erasure methods that modify weights and claim to 'permanently remove' targeted concepts. Seven such methods (Erased Stable Diffusion, Selective Amnesia, Forget-me-not, Ablating Concepts, Unified Concept Editing, Negative Prompt, Safe Latent Diffusion) are shown to be circumventable. The thesis: **post hoc concept erasure provides a false sense of security**. The key hypothesis is that these methods effectively perform *input filtering* — they are evaluated only on the original offending text and mild variations, leaving models vulnerable to sophisticated prompts. Via Concept Inversion (CI), special soft-prompt word embeddings are learned that recover erased concepts (facial likeness, artistic style, objects, NSFW) with zero weight modification. Concepts are not removed but remapped to new embeddings. Two implications follow: (1) prior erasure results require scrutiny; (2) evaluation must include CI-style attacks, not just mild prompt variations.

<!-- quelle: Problem Framing and Thesis -->

### Background and Threat Model

Diffusion models sample via iterative Markov denoising from Gaussian noise to data. Latent diffusion models (LDM) improve efficiency by operating in a lower-dimensional autoencoder space: an encoder maps images to latent codes, a decoder reconstructs them, and a diffusion model generates codes in that space. Classifier-free guidance combines unconditional and conditional scores during inference.

Machine unlearning aims to make a model behave as if specific training data was never presented. Prior approaches to mitigating undesirable image generation include data exclusion (costly retraining), inference-time steering (evadable with parameter access), classifier-based output alteration, and fine-tuning.

Diffusion-based inversion recovers latent representations for given images. Textual Inversion (TI) learns a concept by optimizing a placeholder embedding without changing model weights.

The threat model assumes an adversary with: (1) access to erased-model weights and components, (2) knowledge of the erasure method, (3) access to example images of the targeted concept, (4) moderately significant computational power, and (5) inability to modify model weights. Two experiments—comparing TI on well-represented vs. absent concepts in Stable Diffusion 1.4, and training two MNIST diffusion models with one class excluded—demonstrate that TI performs significantly worse when a concept is absent from training data, validating TI as a reliable concept-detection tool.

<!-- quelle: Background and Threat Model -->

### Experimental Setup and Evaluation Protocol for Concept Inversion Attacks

Seven concept erasure methods for Stable Diffusion models (all published up to September 19, 2023) are examined. Concept Inversion (CI) procedures are designed for each method, searching the space of word embeddings to recreate purportedly erased visual concepts using solely existing components of post-erasure models. Pre-trained models from original authors are used where available; otherwise, public code reproduces erasure procedures.

Evaluation covers four concept categories on SD 1.4, assuming adversary access to small numbers of Google Images examples:

- **Art style**: 6 styles (Ajin: Demi Human, Thomas Kinkade, Tyler Edlin, Van Gogh, Kelly McKernan). Human study (50 participants, 96 responses each) uses 5-point Likert scale comparing CI-generated, erased-model, and real images against reference images.
- **Objects**: Imagenette dataset (10 classes). Evaluation via top-1 predictions of ResNet-50 ImageNet classifier on 500 generated images.
- **ID**: Brad Pitt and Angelina Jolie. Evaluation via GIPHY celebrity detector on 500 images.
- **NSFW content**: I2P dataset (4703 prompts with seeds). NudeNet classifies images into nudity classes; 382 images with detected exposed body parts undergo CI. Recovery measured by regenerating 4703 images with c* prepended to I2P prompts, evaluated by NudeNet.

Evidence is presented that current erasure methods likely perform input filtering, and transferability of learned word embeddings is demonstrated.

<!-- quelle: Experimental Setup and Evaluation Protocol -->

### Circumventing Weight-Based Erasure Methods

The section demonstrates that weight-based concept erasure methods in Stable Diffusion can be systematically circumvented via Concept Inversion (CI), applying standard Textual Inversion on fine-tuned models to learn new word embeddings recovering erased concepts. Five erasure methods are examined: **ESD** fine-tunes the U-Net by steering conditional prediction away from the target concept via a scaled denoising equation, with two variants (ESDx on cross-attentions, ESDu on non-cross-attention layers). **UCE** edits cross-attention weights via a closed-form solution without training, updating keys/values for edited concepts while preserving others. **SA** frames erasure as continual learning using EWC and Generative Replay, maximizing a surrogate distribution likelihood to forget target concepts. **FMN** fine-tunes cross-attention layers by minimizing the Frobenius norm of attention maps between input features and forgetting-concept embeddings, mapping erased concepts to reference images. **AC** overwrites target concepts with anchor concepts via model-based or noise-based ablation, fine-tuning cross-attention, embedding, or full U-Net weights. Quantitative results show erased models drop classification accuracy (e.g., ESD average 0.2%), yet CI restores it (60.1% average), proving erasure is reversible across all methods and concept types (artistic, object, NSFW, identity).

<!-- quelle: Circumventing Weight-Based Erasure Methods -->

### Circumventing Inference-Guidance Methods: NP and SLD

Negative Prompt (NP) replaces the unconditional score with a score conditioned on the erased concept in classifier-free guidance, without updating model weights. Vanilla Textual Inversion fails to circumvent NP; the authors modify its objective so the predicted noise from NP equals the true predicted noise under classifier-free guidance, learning a word embedding for string c* that neutralizes the erasure.

Safe Latent Diffusion (SLD) extends NP by introducing a safety guidance term dependent on timestep and the distance between conditional scores of the prompt and target concept. SLD's four variants—SLD-Weak, SLD-Medium, SLD-Strong, SLD-Max—offer increasing erasure potency. Vanilla Textual Inversion again fails. A further obstacle: SLD's guidance term at timestep t depends on all preceding terms, creating a recursive dependency that would require storing every prior guidance term—prohibitively memory-intensive given the high number of denoising steps. The authors approximate by computing only a subset of guidance terms at evenly spaced timesteps between 1 and t, then learn a word embedding that counteracts the safety guidance term's influence.

Quantitative results (Table 3) show CI recovers erased identity concepts across all methods: e.g., ESD drops Brad Pitt accuracy to 0.0% but CI restores 61.2%; NP leaves 43.2% but CI raises it to 71.4%. Qualitative results (Figure 6) confirm CI regenerates erased object concepts.

<!-- quelle: Circumventing Inference-Guidance Methods -->

### Results and Discussion

All seven concept erasure methods are effective when the target concept is explicitly named in the input prompt, confirming protection against obviously-offensive inputs—even for concept categories untested in the methods' original publications. However, all seven methods are fully circumvented by CI attacks, meaning erasure is effective only against the methods' chosen inputs.

For artistic concepts, human-study Likert scores rise from 1.31 (erased model) to 3.7 under CI, recovering erased style. For object concepts, pre-trained classifier accuracy increases from 9.89 to 57.94. For ID concepts, GIPHY detector accuracy rises from 8.15 to 67.13. For NSFW concepts, detected exposed body parts increase from 26.2 to 170.93.

SLD is the most challenging to circumvent. CI counteracts SLD-Weak, SLD-Medium, and SLD-Strong under most circumstances; SLD-Max proves most resistant but risks entirely transforming visual semantics of generated images. More GPU memory yields better approximations of safety guidance terms, improving CI's counteraction of SLD.

<!-- quelle: Results and Discussion -->

### Transferability and Usability of Concept Inversion Attacks

Learned special tokens derived from CI can be applied to the original SD 1.4 model to generate images of the erased concept, evidencing that current concept erasure methods merely remap the concept in token space rather than fully excising it from the model. Two practical usability tests follow Gal et al.: (1) **Reconstruction** — generating images using the inverted concept with the erased model; (2) **Editability** — generating the inverted concept in different scenes. CLIP scores measure how well inverted concepts are produced by erased models and how transferable they are across scenes. In both cases, erased models achieve performance comparable to the original Stable Diffusion, indicating the models remain in principle capable of producing the seemingly erased concepts. Transferability is further demonstrated by applying learned word embeddings from an erased model (Van Gogh style as erased concept) back to the original SD model to generate images of the targeted concept.

<!-- quelle: Transferability and Usability of Attacks -->

### Conclusions and Outlook

As text-to-image generative AI models proliferate publicly, concerns about generating proprietary, sensitive, or unsafe images intensify. Numerous recent methods claim to erase target concepts from trained generative models, ostensibly rendering them safer. This paper scrutinizes those claims and demonstrates that post-hoc erasure methods have not excised the targeted concepts: fairly straightforward 'attack' procedures can design special prompts that regenerate the unsafe outputs. The finding holds across the diverse algorithmic techniques these methods employ. Future work must fundamentally analyze why the 'input filtering' phenomenon appears to occur in all recent erasure methods despite their algorithmic diversity. Such understanding could facilitate designing methods that improve both the effectiveness and robustness of concept erasure.

<!-- quelle: Conclusions and Outlook -->

### References and Appendices: Training Details for Concept Erasure Experiments

The appendix specifies training configurations for **Concept Inversion** (CI) across erasure methods and concept types. CI uses 6 samples for art style, 30 for object, 25 for ID concepts. Training runs on one A100 GPU, batch size 4, learning rate 5e-03, optimizing word embeddings for 1,000 steps with erased model weights frozen — except ID concepts (5,000 steps) and SLD (1,000 steps, batch size 1).

- **ESD**: Pre-trained models used for artistic and NSFW concepts; ESDu trained with author-suggested parameters for object concepts; ID concepts use object-concept parameters.
- **UCE**: Author-provided training script for artistic, object, and NSFW concepts; ID concepts trained without preservation loss term.
- **SA**: Photorealism-style surrogate images for artistic concepts, finetuning cross-attention layers 200 epochs; kangaroo images (ImageNet class) as surrogate for object concepts, finetuning unconditional layers; author scripts for ID and NSFW.
- **AC**: Author scripts for artistic concepts; anchor distribution set to kangaroo images (object), middle-aged people (ID), clothed people (NSFW).
- **FMN**: Employed for artistic concepts (truncated).

<!-- quelle: References and Appendices -->

## GLOSSAR

- **Concept Inversion (CI)** — A procedure that searches the space of word embeddings to recreate purportedly erased visual concepts using only existing components of post-erasure diffusion models.
- **input filtering** — A phenomenon where erasure methods appear to filter specific inputs rather than truly removing the targeted concept from the model's representations.
- **concept erasure** — Post hoc methods that modify a trained text-to-image model's weights or inference to prevent generation of targeted sensitive concepts.
- **Latent Diffusion Models (LDM)** — Diffusion models operating in a lower-dimensional latent space learned by an autoencoder for improved efficiency.
- **Textual Inversion (TI)** — A technique that learns a new concept by optimizing a placeholder embedding vector in a frozen text-to-image model without changing model weights.
- **classifier-free guidance** — An inference technique combining unconditional and conditional denoising scores to produce the final latent output.
- **c*** — A special placeholder string associated with the learned word embedding, used to replace concept names in prompts during CI image generation.
- **I2P dataset** — A benchmark of 4703 unique prompts with corresponding seeds for measuring NSFW concept erasure effectiveness, notable because prompts do not necessarily contain nudity-related words.
- **ESDx / ESDu** — Two variants of Erased Stable Diffusion that fine-tune cross-attention layers and non-cross-attention (unconditional) layers respectively.
- **anchor concept** — A superset or similar concept used to overwrite a target concept during ablation-based erasure in the AC method.
