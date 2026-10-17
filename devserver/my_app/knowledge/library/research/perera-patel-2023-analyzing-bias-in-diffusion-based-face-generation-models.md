---
id: perera-patel-2023-analyzing-bias-in-diffusion-based-face-generation-models
titel: Analyzing Bias in Diffusion-based Face Generation Models
autor: "Malsha V. Perera, Vishal M. Patel"
jahr: 2023
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, bias]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2305.06402"
status: published
analyzed_at: "2026-07-31T10:53:53.519871+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Analyzing Bias in Diffusion-based Face Generation Models

## PROFIL

This essay argues that diffusion-based face generation models amplify distribution bias in training data regarding perceived attributes—gender, race, and age—an effect heavily influenced by dataset size, whereas Generative Adversarial Network (GAN) models trained on balanced datasets with larger sample sizes exhibit less bias. It positions itself against the implicit assumption that the superior image synthesis performance of Denoising Diffusion Probabilistic Models (DDPM) inherently guarantees equitable outputs, addressing a gap where no prior work investigates diffusion-model bias in face generation under varying training-set sizes. By demonstrating that diffusion models tend to worsen distribution bias while GANs better preserve attribute composition under specific conditions, the text challenges the uncritical adoption of diffusion architectures. For arts education, this research underscores the necessity of teaching students to critically evaluate the training data and model architectures of generative tools to prevent the amplification of societal biases in synthetic media.

## WISSEN

### Bias in Diffusion-Based Face Generation: Problem Framing and Thesis

Diffusion models outperform GANs in image synthesis yet risk amplifying societal bias, especially in face generation. The study investigates how training dataset size and distribution shape imbalances in generated samples across perceived attributes — gender, race, and age — measured by perception rather than objective determination, since these attributes are socially constructed. Concerns about diffusion models memorizing training distributions (Somepalli et al.) motivate examining whether sample count affects bias. The study extends to GANs for comparison and assesses perceptual quality differences across attribute classes.

Key findings:
- Diffusion-based face generative models amplify the bias in terms of the perceived gender, race, and age distribution in the training dataset.
- When trained with balanced datasets of varying sizes, diffusion models demonstrate bias towards certain attribute classes, with the degree of bias being dependent on the specific dataset and its size.
- When using a balanced training dataset with a larger number of samples, GAN-based face generative models demonstrate a greater ability to preserve the attribute composition compared to diffusion models.

<!-- quelle: Problem Framing and Thesis -->

### Related Work: Bias, Generative Models, and Data Replication

GANs (generator-discriminator minimax training) and DDPMs (forward noising / reverse denoising Markovian process) underpin image generation. Bias in face recognition is well-documented across gender, race, skin tone, brightness, hairstyles, and makeup; mitigation strategies include intrinsic-bias frameworks and distillation-based attention alignment. GANs amplify gender and skin-tone biases from unbalanced data; racial composition of generated images preserves training distribution. Mitigation approaches include Inclusive GAN (data coverage via adversarial-reconstructive harmonization), latent-space semantic distribution shifting, and gradient-norm-based clipping. Diffusion-model bias studies focus on text-to-image systems, revealing over-representation of whiteness and masculinity across occupations, traits, and situations. No prior work investigates diffusion-model bias in face generation under varying training-set size — the gap this work addresses. Data replication occurs in both GANs (decreasing exponentially with dataset complexity) and diffusion models, with diffusion models leaking more training data than GANs.

<!-- quelle: Related Work -->

### Methodology and Datasets

To study biases in generative models, we analyze gender, race, and age distributions in FFHQ and FairFace. We examine diffusion models using a lighter version of ADM and GANs using Style-GAN2-ADA. FFHQ (70,000 images) evaluates gender and age bias: 55.3% female, 44.7% male. Age ranges: 0-10 (14.5%), 11-20 (11%), 21-30 (29%), 31-40 (22.2%), 41-50 (12.6%), 51-60 (7.2%), above 60 (3.4%). From FairFace, we isolate 'Black' and 'White' categories into FairFace-BW (28,760 images). We acknowledge this simplification as a preliminary step. FairFace-BW contains 57.47% White, 42.53% Black, 51.4% male, 48.6% female. We train models on full datasets to analyze generated distributions, and on randomly sampled, balanced subsets to assess dataset size effects. Attribute classifier networks determine perceived distributions.

<!-- quelle: Methodology and Datasets -->

### Attribute Distribution of Diffusion Generations

All diffusion models are trained for ≥1M steps on 256×256 images (single NVIDIA RTX A5000 GPU), generating the same number of samples as training data.

For the FFFHQ-trained model, perceived gender splits 58% female / 42% male. Perceived age distribution: 0–10: 14.5%, 11–20: 11%, 21–30: 29%, 31–40: 22.2%, 41–50: 12.6%, 51–60: 7.2%, >60: 3.4%.

For the FairFace-BW-trained model, perceived race splits 66% White / 34% Black; perceived gender splits 54% male / 46% female.

<!-- quelle: Attribute Distribution of Diffusion Generations -->

### Effect of Dataset Size on Attribute Bias

The study isolates dataset size as a variable affecting attribute bias in diffusion and GAN-based face generation models. Balanced training subsets—equal distribution across the target attribute—are created at sizes 300, 700, 1000, 5000, and 10000 via random sampling. Models generate samples equal in number to the training subset, repeated five times for a mean attribute distribution.

- **Gender bias**: subsets of 50% male / 50% female from FFHQ and FairFace-BW.
- **Racial bias**: subsets of 50% Black / 50% White from FairFace-BW.
- **Age bias**: subsets from FFHQ equally distributed across seven ranges: 0-10, 11-20, 21-30, 31-40, 41-50, 51-60, and above 60 (~14.3% each).

By holding attribute balance constant and varying only subset size, the experiment traces how training data volume alone shifts generated distributions across gender, race, and age.

<!-- quelle: Effect of Dataset Size on Attribute Bias -->

### Generation Quality and Attribute Classifiers

FID (Fréchet Inception Distance) measures perceptual quality of generated images by comparing Inception-network feature distributions between training and generated images; lower scores indicate higher quality. The study uses FID to assess how dataset size affects diffusion and GAN-based face generation across gender, race, and age attribute classes (Tables 1–3).

Attribute classifiers based on ResNet-18 are trained on FFHQ and FairFace datasets to evaluate attribute distributions of generated faces. For FFHQ: gender and age classifiers trained on 69,700 images (300 held out for testing), achieving 99.9% (gender) and 95% (age) accuracy. For FairFace-BW: gender and race classifiers evaluated on Black and White validation classes, achieving 99.15% (gender) and 97.0% (race) accuracy.

<!-- quelle: Generation Quality and Classifiers -->

### Attribute Bias in Face Generation: Diffusion Models vs. GANs

Diffusion models trained on FFHQ overgenerate female faces and underrepresent ages above 50; on FairFace-BW they skew male and toward the White racial class. The direction of gender bias thus depends on training data distribution. Using balanced subsets to isolate dataset-size effects, diffusion models exhibit inconsistent, size-dependent attribute skew across gender, race, and age — complexity factors such as lighting, hair, and makeup impede balanced representation. GAN-based models, by contrast, preserve training distribution for subsets above 1000 samples, showing minimal bias regardless of subset size, with consistent underrepresentation only for ages 11–20 and above 60. GANs demonstrate greater robustness to training-data variation than diffusion models.

<!-- quelle: Analysis of Attribute Bias -->

### Data Replication and Bias in Diffusion Models

Data replication is more common in diffusion models trained with less data, likely due to model complexity exceeding training data complexity (overfitting). Crucially, replication does not uniformly reproduce the training data's attribute distribution; certain samples are replicated more frequently, introducing bias across gender, race, and age attributes. This bias manifests in FID scores: diffusion models exhibit a low→high→low pattern as dataset size increases—low FID at small sizes likely reflecting replication-induced similarity between training and generated distributions—whereas GANs show gradual FID decrease. Replication is less pronounced in GANs than in diffusion models. The authors employed automated classifiers (>95% accuracy, minimal category bias), trained on the same datasets as the generative models, to avoid manual attribute labeling. Diffusion-based face generation models can amplify training-data bias even on balanced data, necessitating bias mitigation and caution in downstream tasks. Future directions include Latent Diffusion Models, VAEs, and attributes such as hair and makeup.

<!-- quelle: Data Replication and Limitations -->

### Conclusion

The study positions bias mitigation in diffusion-based face generation as essential. It investigates bias across gender, race, and age, and examines how dataset size affects attribute composition and perceptual quality in both diffusion and GAN-based models. The findings establish three claims: (1) diffusion models **exacerbate** training-data distribution bias across attributes and datasets; (2) attribute-distribution bias in diffusion models is heavily dependent on dataset size; (3) GAN-based models trained on larger balanced datasets exhibit less bias across attributes. The argument thus demarcates diffusion from GAN architectures by showing that diffusion models amplify rather than merely inherit training bias, while GANs respond more favorably to dataset scaling and balancing.

<!-- quelle: Conclusion -->

## GLOSSAR

- **Denoising Diffusion Probabilistic Models (DDPM)** — A generative modeling paradigm that learns data distribution through a Markovian denoising process, here applied to face generation.
- **perceived attributes** — Gender, race, and age as inferred by human perception rather than objectively determined, acknowledging their social construction.
- **replication of data** — The tendency of diffusion models to memorize and reproduce training data distribution, more pronounced with limited training samples.
- **Inclusive GAN** — A GAN variant that improves minority data coverage by harmonizing adversarial training with reconstructive generation.
- **data replication** — The phenomenon where generative models memorize and reproduce training samples rather than generating novel outputs.
- **FairFace-BW** — Subset of the FairFace dataset restricted to Black and White racial classes, used for training generative models and classifiers.
- **ADM** — The network architecture used for unconditional face generation in diffusion models.
- **Style-GAN2-ADA** — The GAN-based architecture used for face generation to analyze the presence of bias.
- **perceived** — Used consistently to mark that gender, age, and race attributes are inferred from generated images rather than treated as ground-truth labels.
- **attribute bias** — Systematic skew in generated face images toward particular demographic classes (gender, age, race) relative to the training data distribution.
