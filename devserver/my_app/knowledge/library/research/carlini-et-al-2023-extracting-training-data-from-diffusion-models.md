---
id: carlini-et-al-2023-extracting-training-data-from-diffusion-models
titel: Extracting Training Data from Diffusion Models
autor: "Nicholas Carlini, Jamie Hayes, Milad Nasr, Matthew Jagielski, Vikash Sehwag, Florian Tramèr, Borja Balle, Daphne Ippolito, Eric Wallace"
jahr: 2023
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, ethics]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2301.13188"
status: published
analyzed_at: "2026-07-31T10:36:37.077110+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Extracting Training Data from Diffusion Models

## PROFIL

The text argues that state-of-the-art image diffusion models, such as Stable Diffusion and Imagen, memorize individual training images and emit them at generation time, rendering them significantly less private than prior generative models like GANs. It sets itself against prior assumptions that diffusion models "do not find overfitting to be an issue" and could "protect[] the privacy [...] of real images," demonstrating these claims are false through a generate-and-filter extraction attack that recovers near-identical replicas of training data. For arts education, this text is applicable as a foundational resource for addressing copyright, "digital forgery," and privacy implications when integrating generative AI tools into creative curricula.

## WISSEN

### Diffusion Models Memorize and Leak Training Data

State-of-the-art image diffusion models (DALL-E 2, Imagen, Stable Diffusion) are widely assumed not to overfit their training data; privacy-sensitive domains have even proposed them as privacy-protective synthetic generators. This work overturns that assumption: diffusion models memorize individual training images and regenerate them at test time.

The argument proceeds in three steps. First, new definitions for **memorization** in image models are proposed and implemented. Second, a two-stage **generate-and-filter** extraction attack is devised: images are generated via standard approaches, then flagged when they exceed membership inference scoring criteria. Applied to Stable Diffusion and Imagen, this yields over a hundred near-identical replicas of training images—personally identifiable photos, trademarked logos, etc. (e.g., a Stable Diffusion generation prompted with "Ann Graham Lotz" reconstructs a training-set photo at ℓ₂ distance = 0.031).

Third, to analyze causation, hundreds of diffusion models are trained on CIFAR10, varying model accuracy, hyperparameters, augmentation, and deduplication. Key findings:
- Diffusion models are the least private image model class evaluated, leaking more than twice as much training data as GANs.
- Existing privacy-enhancing techniques do not yield an acceptable privacy-utility tradeoff.

The paper positions itself against prior claims that diffusion models "do not find overfitting to be an issue" and could "protect[] the privacy [...] of real images," demonstrating these assumptions are false and that mitigating the vulnerability may require new advances in privacy-preserving training.

<!-- quelle: Problem Framing and Thesis -->

### Background: Diffusion Models and Training Data Privacy Attacks

Diffusion models have displaced GANs as the dominant generative image architecture, forming the basis of Stable Diffusion, DALL-E 2, Midjourney, and Imagen. **Denoising Diffusion Probabilistic Models** are conceptually image denoisers: during training, a clean image x is noised via a Gaussian process parameterized by a decaying schedule a_t, and the model f_q learns to predict the added noise. Generation proceeds by sampling z_T ~ N(0,I) and iteratively applying f_q to denoise, following a noise schedule s_t with s_1=0, yielding z_0. The author notes that significant training details are omitted as "orthogonal to the results of our attacks." Models may be class-conditional (class-label input) or text-conditioned (text embedding via a pre-trained encoder such as CLIP).

Regarding privacy attacks, the paper positions itself against a hierarchy of threats: membership inference attacks ("was this example in the training set?") present a mild breach; inversion attacks extract representative examples from a target class; attribute inference attacks reconstruct subsets of attributes; extraction attacks completely recover training examples. The paper targets all three attack types applied to diffusion models.

Against concurrent work, the paper demarcates itself on two fronts: Wu et al. and Hu et al. perform membership inference on diffusion models, but "our results use more sophisticated attack methods and study stronger privacy risks such as data extraction." Somepalli et al. show non-adversarial sampling can produce memorized examples, focusing on semantic similarity ("style copying"); in contrast, the paper targets "worst-case privacy under a much more restrictive notion of memorization" across a wider range of models.

<!-- quelle: Background and Related Work -->

### Motivation, Threat Model, and Ethics

Two distinct motivations drive studying how diffusion models memorize and regenerate training data.

**Privacy risks.** Diffusion models trained on Internet-scraped data pose copyright and privacy risks analogous to language models; copying artists' images has been termed 'digital forgery.' Future models may train on sensitive data (GANs already apply to medical imagery). Critically, some propose diffusion-generated synthetic data to 'protect the privacy and usage rights of real images'—our work shows diffusion models may be unfit for this purpose.

**Generalization.** Studying memorization yields empirical characterization of whether model outputs are novel generations or direct copying/remixing. Saharia et al. report no overfitting, yet we show their model memorizes individual examples, suggesting overfitting definitions must broaden to include memorization and privacy metrics. Our results also suggest Feldman's theory—that memorization is necessary for generalization in classifiers—may extend to generative models, raising whether diffusion models outperform prior approaches precisely because they memorize more.

**Threat model.** An adversary A interacts with a diffusion model Gen to extract images from training set D. Unconditional models output x_gen ← Gen(r); conditional models output x_gen ← Gen(p; r) given prompt p.

Adversary capabilities:
- Black-box: queries Gen, provides arbitrary prompts if conditional, cannot control internal randomness r.
- White-box: full access to Gen and internal diffusion model f_q, controls randomness, can denoise arbitrary inputs.

For conditional generators, the adversary knows captions for some training images, studying worst-case privacy risk.

Adversary goals (strongest to weakest):
1. Data extraction: recover a training image x ∈ D; success if extracted x̂ is almost identical to some x ∈ D.
2. Data reconstruction: from partial knowledge of x ∈ D, recover the full image (analog of attribute inference attack).
3. Membership inference: determine whether a given x is in the training set.

**Ethics.** We mitigate harms by: studying only publicly-available datasets (LAION, CIFAR-10); ensuring all shown images are of public figures who knowingly placed images online (e.g., Ann Graham Lotz's Wikipedia profile, Creative Commons licensed); and sharing advance copies with model authors. We believe public disclosure is ethical and responsible—no one is currently harmed, and our goal is to preempt future harms and encourage responsible training.

<!-- quelle: Motivation, Threat Model, and Ethics -->

### Defining Image Memorization

Existing literature defines training data extraction in text language models via verbatim sequence recovery. Because this text addresses high-resolution images, verbatim definitions are unsuitable; instead, it defines approximate memorization via image similarity metrics.

**Definition 1 ((ℓ, d)-Diffusion Extraction):** An example x is extractable from a diffusion model f_q if an efficient algorithm A (not receiving x as input) outputs x̂ = A(f_q) such that ℓ(x, x̂) ≤ d. Here, ℓ is a distance function and d a threshold for identity. The text uses the Euclidean 2-norm distance normalized to [0, 1].

**Definition 2 ((k, ℓ, d)-Eidetic Memorization):** An example x is memorized if it is extractable and there are at most k training examples x̂ where ℓ(x, x̂) ≤ d. The constant k quantifies near-duplicates: a small k suggests problematic memorization, while a larger k might be expected but still problematic (e.g., copyrighted data).

The author acknowledges this definition is intentionally conservative. For example, prompting a model to generate "A Photograph of Barack Obama" yields a recognizable image with a high ℓ2 distance to any single training image. Under this definition, it is not memorized, though the author concedes such generation of recognizable individuals could still cause privacy harms.

<!-- quelle: Conceptual Clarification: Defining Image Memorization -->

### Extracting Training Data from Stable Diffusion and Imagen

The attack extracts memorized training images from Stable Diffusion (890M parameters, 160M training images) via a black-box methodology adapted from prior work. To reduce computational load, the search targets near-duplicated training examples—identified not bit-for-bit but via CLIP-embedding cosine similarity, since exact-duplicate matching would undercount true duplication rates.

Extraction proceeds in two steps: (1) generate 500 candidate images per prompt using timestep-resampled generation (~10× faster, lower fidelity); (2) perform membership inference by constructing a graph over the 500 generations, connecting images with low modified-ℓ₂ distance (16 non-overlapping 128×128 tiles, maximum pairwise tile distance to suppress spurious similarities like uniform backgrounds). A clique of ≥10 near-identical generations flags a memorized image; clique-finding reduces false positives versus pairwise comparison.

From 350,000 most-duplicated prompts (175M generated images), 94 images are (ℓ₂, 0.15)-extracted; manual annotation of the top-1000 yields 13 additional near-copies (109 total). The attack achieves 0 false positives when identifying 50 memorized images; all memorized images extractable at >50% precision.

Measuring (k, ℓ, d)-eidetic memorization (d=0.1) shows memorization concentrated at k≥100 duplications—still just one-in-a-million training examples—establishing duplication as a major factor behind extraction.

Qualitative analysis: 58% extracted images are photographs of recognizable persons; 35% carry explicit non-permissive copyright notices, raising licensing concerns.

Applying the same procedure to Imagen (2B parameters) on the top-1000 most-duplicated prompts yields 23 memorized images—a higher rate than Stable Diffusion, demonstrating that memorization scales with model size, training time, and dataset size.

The authors acknowledge that high-k memorization, while problematic, is less compelling than low-k extraction. They pivot to 'outlier' examples—non-duplicated images disproportionately exposed—but note that influence-function approaches are infeasible given million-dollar training costs, motivating a simpler method.

<!-- quelle: Application: Extraction Attacks on State-of-the-Art Models -->

### Controlled Experiments: Untargeted Extraction and Membership Inference

Prior experiments showed memorization is pervasive but did not explain why or how. This section trains 16 smaller diffusion models on random halves of CIFAR-10 to run controlled experiments across three privacy attack types: membership inference, attribute inference, and data reconstruction.

**Untargeted extraction.** Because smaller models are not text-conditioned, the authors generate 2^20 candidate images and search for memorized training examples directly. Absolute ℓ2 thresholds fail: restrictive thresholds flag only blue-sky or green-landscape images. The authors instead use an adaptive distance comparing a generated image's proximity to its nearest training neighbor against the distribution of distances to all training images. This identifies 1,280 unique extracted images (2.5% of the dataset).

**Membership inference.** Two attacks are evaluated: the loss threshold attack (Yeom et al.) and LiRA (Carlini et al.), which trains shadow models on random subsets and fits Gaussians to IN/OUT loss distributions. Unlike classifiers, diffusion models have no single well-defined loss—loss depends on timestep t. Sweeping t∈[1,T], the authors find t∈[50,300] optimal, a 'Goldilocks zone' where noise is neither too small (task trivial regardless of membership) nor too large (task impossible). At t=100, LiRA achieves >70% TPR at 1% FPR, far exceeding classifier privacy. Easiest-to-attack images are visually out-of-distribution; hardest are duplicates, where membership is ill-defined. Augmentations can further reduce loss variance and improve attacks.

<!-- quelle: Controlled Experiments: Untargeted Extraction and Membership Inference -->

### Inpainting Attacks as Targeted Extraction

The authors transition from untargeted extraction to a targeted attack. Because diffusion models trained on CIFAR-10 do not support textual prompting, targeted extraction cannot rely on text guidance. Instead, the authors construct an **inpainting attack**—a form of attribute inference attack—where a portion of an image is masked and the attack objective becomes recovering the masked region.

**Method.** For an image *x*, a fraction of pixels is masked to produce *x_m*; the trained diffusion model then reconstructs the image as *x_rec*. Because diffusion inpainting is stochastic (dependent on random sampling *ε* ~ *N*(0, *I*)), the authors generate a set *X_rec* of 5,000 inpainted candidates. Each candidate is scored by the diffusion model's loss on the sample (at timestep 100) divided by a shadow model's loss not trained on that sample; the highest-scoring reconstructions are selected via this membership inference signal.

**Experiment.** The left half of each image is masked; the right half conditions inpainting. The attack is repeated for 100 images using models trained with and without the target image. The top-10 scoring reconstructions are compared by average ℓ2 distance to the original.

**Results.** Reconstruction loss is substantially lower (in ℓ2 distance) when the target image is in the training set than when it is not. Qualitative examples confirm: the highest-scoring reconstruction visually resembles the target when the target was in training and does not when it was not. The authors conclude that an adversary with partial knowledge of an image can substantially improve extraction results over typical data extraction.

<!-- quelle: Application: Inpainting Attacks -->

### Diffusion Models vs. GANs: Privacy Comparison

The section asks whether diffusion models are more or less private than GANs. Unlike diffusion models, which are explicitly trained to memorize and reconstruct their training datasets, GANs consist of a generator and discriminator; the generator never receives training data directly but is trained indirectly via gradients from the discriminator.

For membership inference attacks, the authors develop their own methodology, using the discriminator's loss with both loss threshold and LiRA attacks. Diffusion models exhibit higher membership inference leakage (50% TPR at 0.1% FPR vs. <30% TPR for GANs), even when the GAN attack is strengthened by granting discriminator access—unlikely in practice, where only the generator is needed.

For black-box data extraction, the authors generate 2^20 images from off-the-shelf pretrained GANs and DDPMs on CIFAR-10. Diffusion models memorize more: the best DDPM extracts 2× more images than StyleGAN-ADA at the same FID. Across both model types, better generative quality (lower FID) correlates with more memorization.

A surprising finding: diffusion models and GANs memorize many of the same images—244 unique images in common between a diffusion model (1280 memorized) and a StyleGAN model (361 memorized), vs. 10 expected by chance (p < 10^-261), providing strong evidence that some images are inherently less private than others.

<!-- quelle: Comparative Analysis: Diffusion Models vs. GANs -->

### Defenses and Recommendations

Given that diffusion models memorize and regenerate training examples, the section evaluates two mitigation strategies.

**Deduplicating Training Data.** Prior analysis (Section 4.2) showed extractable examples are often duplicated >100 times in training data, mirroring findings for language models. Standard image-dataset deduplication removes only identical URL/caption pairs; most datasets do not compute inter-image similarity via ℓ2 distance or CLIP similarity. Practitioners are urged to adopt these advanced duplication metrics. To test effectiveness, the authors deduplicate CIFAR-10 using the imagededup tool (similarity threshold >0.85), removing 5,275 of 50,000 examples, then re-train a diffusion model and generate 2^20 images. The deduplicated model regenerates 986 training examples versus 1280 for the original—a modest but real reduction. The authors expect greater benefit at larger scale (e.g., Stable Diffusion), where the correlation between extraction and duplication rates is much stronger.

**Differentially-Private Training.** The gold standard for privacy defense is differential privacy (DP). Diffusion models can be trained with differentially-private stochastic gradient descent (DP-SGD), which clips and noises gradients to prevent leakage of substantial information about any individual image's presence. DP-SGD induces a privacy–utility trade-off; recent work shows it can be applied to small-scale diffusion models without substantial performance degradation.

<!-- quelle: Defenses and Recommendations -->

## GLOSSAR

- **memorization** — The phenomenon where a diffusion model regenerates an individual training image at generation time, as formally defined and detected by the authors' new criteria.
- **generate-and-filter pipeline** — A two-stage extraction attack that first generates images using standard diffusion sampling and then flags outputs exceeding membership inference scoring thresholds.
- **membership inference scoring** — Criteria used to determine whether a generated image corresponds to a specific training-set member, enabling detection of memorized examples.
- **Denoising Diffusion Probabilistic Models** — Generative models that function as image denoisers, trained to predict Gaussian noise added to clean images and capable of generation by iteratively denoising a random sample.
- **membership inference attacks** — Privacy attacks that determine whether a specific example was in a model's training set, considered a mild privacy breach.
- **style copying** — A notion of memorization focused on semantic similarity between generated images and training data, contrasted with the paper's more restrictive worst-case memorization standard.
- **digital forgery** — Term used to describe diffusion models copying images from professional artists, raising copyright concerns.
- **data extraction** — Strongest adversarial goal: recovering a training image nearly identical to one in the training set.
- **membership inference** — A privacy attack determining whether a specific example was present in a model's training set.
- **(ℓ, d)-Diffusion Extraction** — A definition of extractability where an example is recoverable by an algorithm if its distance to the output is below a threshold d.
