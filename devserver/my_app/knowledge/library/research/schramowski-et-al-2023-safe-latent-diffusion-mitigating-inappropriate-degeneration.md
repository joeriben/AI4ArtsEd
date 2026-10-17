---
id: schramowski-et-al-2023-safe-latent-diffusion-mitigating-inappropriate-degeneration
titel: Safe Latent Diffusion. Mitigating Inappropriate Degeneration in Diffusion Models
autor: "Patrick Schramowski, Manuel Brack, Björn Deiseroth, Kristian Kersting"
jahr: 2023
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai, ethics]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2211.05105"
status: published
analyzed_at: "2026-07-31T09:53:15.253599+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Safe Latent Diffusion. Mitigating Inappropriate Degeneration in Diffusion Models

## PROFIL

The text argues that text-conditioned diffusion models (DMs) trained on unfiltered internet datasets like LAION-5B inherit and reinforce human biases, a phenomenon termed "inappropriate degeneration," which can be mitigated during the diffusion process using safe latent diffusion (SLD) without additional training. It sets itself against the reliance on post-hoc safety interventions and the assumption that large-scale data scraping does not unpredictably generate harmful content in models like Stable Diffusion (SD). To measure this risk, the authors introduce the inappropriate image prompts (I2P) testbed, demonstrating that SLD effectively suppresses inappropriate content while maintaining image quality and text alignment. For arts education, this methodology offers a practical framework for safely integrating generative AI into studio practices by actively preventing the reproduction of biased or offensive imagery.

## WISSEN

### Problem Framing and Thesis

Text-conditioned diffusion models (DMs) achieve high image quality and text alignment by training on billion-sized datasets scraped from the internet. Because this data is unfiltered and imbalanced, DMs inherit degenerated and biased human behavior and may reinforce it. The authors analyze the open-source Stable Diffusion (SD), trained on subsets of LAION-5B, and find significant generation of inappropriate content — content that may be offensive, insulting, threatening, or anxiety-inducing. Critically, this inappropriate degeneration occurs even for prompts that do not explicitly request harmful material, making the problem unpredictable.

To systematically measure this risk, the authors introduce I2P (Inappropriate Image Prompts), a testbed of 4703 real-world user prompts paired with inappropriateness scores from three detectors. I2P covers concepts such as nudity and violence. Empirical evaluation on SD using I2P confirms that open-source DMs produce inappropriate content, including from seemingly non-harmful prompts.

As mitigation, the authors propose safe latent diffusion (SLD), which suppresses inappropriate content during the diffusion process itself. SLD requires no external classifier and no additional training; it relies on the DM's already-acquired knowledge of inappropriateness. The authors claim no adverse effect on overall image quality or text alignment. They position SLD as the first work to address image editing from an ethical perspective to counteract inappropriate degeneration of DMs, and as a contribution to understanding latent vector arithmetic.

<!-- quelle: Problem Framing and Thesis -->

### Risks, Promises, and Ethnic Bias in Unfiltered Data

Large-scale models trained on unfiltered data reflect and reinforce human biases—stereotypical content, gender and racial biases—despite promises that computational systems could counter structural inequalities. Yet these models also exhibit strong factual recall and moral-norm knowledge that scales with model size, enabling self-debiasing of toxic output. Building on this, the authors demonstrate that diffusion models can guide image generation away from inappropriateness using only representations learned during pre-training and defined in natural language.

The SLD approach relates to text-based image editing techniques (Text2LIVE, Imagic, UniTune, Prompt-to-Prompt) but requires no fine-tuning of text-encoder or DM, introduces no new downstream components, and is based on classifier-free guidance, enabling more complex image changes.

LAION-5B annotates potential inappropriate content without excluding it, facilitating bias research; creators advise against deployment without investigating biases. SD, trained on LAION-2B-en (2.32B English image-text pairs) then fine-tuned on 'LAION High Resolution' and 'LAION-Aesthetics v2 5+', was publicly released without excluding annotated content. It is expected to reflect gender occupation correlations and reporting biases.

The ethnic-bias experiment extends Birhane et al.'s dataset studies to downstream generative models. CLIP-space search for 'japanese body' in LAION-2B-en yielded 90% explicit nudity vs. 22% global average across 50 countries. Prompting SD with '<country> body' (100 images per country, NudeNet classifier) transferred this bias: Japan generated over 75% nudes vs. 35% global average; European, Asian, and Oceanic countries linked more to nudity than African or American ones. 'Asian' and 'Japanese' yielded significantly higher nudity than any other ethnic/geographic term, attributed to synonym usage and overwhelming content volume in LAION-5B.

SD's NSFW safety checker is post-hoc and apparently deactivatable: lexica.art permitted generation of content the checker withholds.

<!-- quelle: Risks, Promises, and Ethnic Bias in Unfiltered Data -->

### Safe Latent Diffusion Methodology

SLD introduces safety guidance for latent diffusion models to reduce **inappropriate degeneration** of DMs, performing image editing at inference without fine-tuning. The method extends classifier-free guidance by combining text conditioning with suppression of inappropriate concepts.

Diffusion models iteratively denoise a Gaussian variable; the model predicts noise ε̃_θ to subtract, conditioned on a text prompt p for text-to-image generation. **Classifier-free guidance** adjusts score estimates by pushing the unconditioned ε-prediction ε_θ(z_t) toward the conditioned ε_θ(z_t, c_p), scaled by guidance scale s_g, yielding images faithful to p.

SLD uses the same principle but introduces a third ε-prediction conditioned on an inappropriate concept S. The goal is to move the unconditioned estimate toward the prompt-conditioned estimate ε_θ(z_t, c_p) and simultaneously away from the concept-conditioned estimate ε_θ(z_t, c_S). This yields a modified prediction ε̄_θ(z_t, c_p, c_S) incorporating a **safety guidance term** γ, where μ applies a guidance scale s_S element-wise to dimensions where the difference between prompt-conditioned and safety-conditioned estimates falls below a threshold λ. Larger λ and s_S produce stronger shifts away from the inappropriate concept. Scaling factors are clipped to prevent artifacts, and prediction values adhere to training bounds [-1, 1].

Two refinements balance content removal against minimal image change: (1) a **warm-up parameter** δ sets γ := 0 for t < δ, ensuring safety guidance activates only after an initial period; higher δ preserves overall composition, altering only fine-grained details. (2) A **momentum term** ν_t accelerates guidance for dimensions continuously guided in the same direction, with momentum scale s_m ∈ [0,1] and decay β_m ∈ [0,1). Momentum accumulates during warm-up even though γ is not applied then. Safety guidance thus removes inappropriate content as soon as it forms in latent space.

<!-- quelle: Safe Latent Diffusion Methodology -->

### Configuring Safe Latent Diffusion

Inappropriateness is context-dependent (e.g., professional artist vs. child), so four configurations of SLD are proposed, varying in safety-adaptation strength. The inappropriate safety concept is text-defined as: 'hate, harassment, violence, suffering, humiliation, harm, suicide, sexual, nudity, bodily fluids, blood, obscene gestures, illegal activity, drug use, theft, vandalism, weapons, child abuse, brutality, cruelty' — extensible by adding or removing terms.

Key hyperparameters: **safety threshold λ** locates the hyperplane dividing latent space into appropriate/inappropriate; recommended conservative range λ ∈ [0.0, 0.03]. **safety guidance scale s_S** can be arbitrarily high without artifacts (unlike s_g), as the scaling factor µ is clipped; recommended s_S ∈ [100, 3000]. **warm-up δ** controls when changes apply — too early disrupts image construction; recommended δ ∈ [5, 20], never exceeding half of total diffusion steps. **momentum** (s_m, β_m) removes concepts occupying significant image portions, especially those built during warm-up; recommended s_m ∈ [0, 0.5], β_m ∈ [0.3, 0.7].

Four configuration sets, increasing in aggressiveness:

| Config | δ | s_S | λ | s_m | β_m |
|---|---|---|---|---|---|
| Hyp-Weak | 15 | 200 | 0.0 | 0.0 | - |
| Hyp-Medium | 10 | 1000 | 0.01 | 0.3 | 0.4 |
| Hyp-Strong | 7 | 2000 | 0.025 | 0.5 | 0.7 |
| Hyp-Max | 0 | 5000 | 1.0 | 0.5 | 0.7 |

Hyp-Weak removes superficial blood splatters but not severe injuries; suppresses nudity in pornographic but not artistic imagery — acceptable for an adult artist, problematic for a child. Hyp-Medium may yield a bikini; Hyp-Strong and Hyp-Max progressively add clothing. Hyp-Max can drive inappropriate content to zero but diverges from the goal of minimal changes; for sensitive applications (e.g., children), post-hoc interventions like SD's safety checker are additionally recommended. Hyp-Max behaves similarly to negative-prompt replacement of the unconditioned estimate, but SLD achieves better mitigation with finer-grained control and preserves negative prompting as a user tool.

<!-- quelle: Configuring Safe Latent Diffusion -->

### Inappropriate Image Prompts (I2P) Benchmark

The I2P dataset comprises 4703 unique real-world text prompts likely to elicit inappropriate content from pre-trained text-to-image models, enabling systematic measurement of inappropriate degeneration risk.

**Defining inappropriate content.** Inappropriateness is acknowledged as subjective, context-dependent, and culturally variable. The working definition follows Gebru et al.: data that, if viewed directly, might be offensive, insulting, threatening, or otherwise cause anxiety. The benchmark restricts itself to images displaying tangible acts of inappropriate behavior across seven categories:

- hate
- harassment
- violence
- self-harm
- sexual content
- shocking images
- illegal activity

**Prompt collection.** Twenty-six keywords and phrases describe the seven categories. For each keyword, up to 250 prompts were crawled from the top 250 images returned by Lexica, a repository of real-world user-generated prompts for Stable Diffusion sourced from its official Discord server. Lexica's retrieval relies on CLIP embedding-space similarity between image and search query. Consequently, collected prompts are not guaranteed to produce inappropriate content, but the probability is high.

**Dataset statistics and key finding.** After deduplication, 4703 unique prompts remain, each assigned to at least one category. Each prompt includes reproduction hyperparameters, an estimated percentage of inappropriate images it generates, and a hard annotation for prompts generating predominantly inappropriate content. Prompt toxicity is scored via the PERSPECTIVE API. Only 1.5% of prompts are toxic, and correlation between prompt toxicity and generated image inappropriateness is weak: prompts with low toxicity scores still exhibit high probabilities of generating inappropriate images. This demonstrates that simply suppressing 'bad' words in text prompts is no reliable mitigation strategy against generating problematic content.

<!-- quelle: Inappropriate Image Prompts (I2P) Benchmark -->

### Experimental Evaluation of Inappropriate Degeneration and SLD

The evaluation assesses "inappropriate degeneration" in Stable Diffusion (SD) and the mitigating effect of "Safe Latent Diffusion" (SLD) using the I2P benchmark. The protocol generates ten images per prompt, classifying inappropriate content via the Q16 classifier (general) and NudeNet (sexually explicit, specifically exposed genitalia).

First, the text establishes SD's "inappropriate degeneration": despite only 1.5% of I2P prompts being toxic, SD generates inappropriate images 34%–52% of the time depending on category. The "expected maximum inappropriateness" over 25 prompts reaches 96%, demonstrating the risk of training on unfiltered datasets.

Second, it tests whether SLD can counteract this using the model's own acquired knowledge. Applying stronger SLD hyper-parameters gradually decreases inappropriate content; the strongest configuration (Hyp-Max) reduces the probability by over 75% to 9%. The authors note the Q16 classifier is conservative, assuming many flagged images for Hyp-Max are false negatives. While the "expected maximum inappropriateness" decreases, variance increases, indicating outliers. Thus, SLD largely mitigates "inappropriate degeneration" based on learned representations.

Third, the text examines counteracting 'ethnic bias'. SLD reduces nude images across all countries by 75%, distributing them more evenly (Japan drops to 12.0%, near the 9.25% global average). However, SLD alone (Hyp-Strong) does not eliminate racial bias entirely, maintaining a statistically significant correlation (Spearman r = 0.52, p = 0.01). The authors position SLD as a valuable contribution that still requires prior issue identification and dataset-level de-biasing efforts.

Finally, experiments on SD v2.0—which applied rigorous dataset filtering for sexual content but not on the text encoder—show biases remain, and are more frequent than SLD mitigation on SD 1.4. The combination of SLD and dataset filtering achieves superior mitigation, suggesting a future avenue.

<!-- quelle: Experimental Evaluation -->

### Discussion, Limitations, and Conclusion

- SLD suppresses inappropriate content during the diffusion process rather than post-hoc. This requires the model to have learned inappropriateness during pre-training; thus, entirely removing inappropriate content from training data is discouraged, as it impairs the model's ability to target related material at inference.
- Future work should measure the impact of training on balanced datasets, though this requires extensive manual labor.
- Imbalanced training data reinforces problematic social phenomena, necessitating dataset curation (as in the presented case study) and bias mitigation in deployed applications.
- SLD carries risks: it could be used for censorship or reversed to generate inappropriate content. Models using SLD must transparently state suppressed contents.
- "Inappropriateness" relies on social norms and diverse sentiments. The I2P test bed is limited to specific concepts and may reflect the societal dispositions of training data groups, lacking diverse sentiment.
- SLD could be applied beyond inappropriateness, such as to fairness.
- Regarding image fidelity and text alignment, while FID-30k and CLIP scores slightly increase with stronger SLD hyperparameters, a user study on DrawBench shows users slightly prefer SLD images, proving safety does not sacrifice quality.
- Conclusion: Inappropriate degeneration stems from unfiltered, imbalanced datasets. I2P measures this, and SLD mitigates it via classifier-free guidance without additional training or quality loss. Strong representation biases are attenuated but not removed, advocating for the careful use of unfiltered, imbalanced datasets.

<!-- quelle: Discussion, Limitations, and Conclusion -->

### References and Appendix

This section comprises funding acknowledgments, a bibliography of 42 references, and the opening of an appendix on an ethnic bias experiment.

**Acknowledgments.** Support from DFKI project 'SAINT', BMBF (Grant No. 01IS22091), EU Horizon 2020 'TAILOR' (GA No. 952215), Hessian LOEWE project WhiteBox, HMWK clusters 'The Adaptive Mind' and 'The Third Wave of AI', and HMWK/BMBF ATHENE project 'AVSV'. Feedback acknowledged from Felix Friedrich, Dominik Hintersdorf, and Lukas Struppek.

**Reference list.** The 42 references cluster around several thematic axes relevant to the essay's argument:

- **Bias and stereotypes in language models and embeddings:** [1], [3], [6], [8], [13], [14], [18], [19], [21], [27], [30], [32], [34], [35], [38], [39]
- **Bias in image and multimodal datasets:** [4], [5], [10], [24], [28], [36], [37], [41]
- **Text-to-image generation and editing (diffusion models):** [2], [15], [16], [17], [23], [25], [29], [31], [40]
- **Dataset documentation and fairness tooling:** [12], [33], [41]
- **Content moderation and offensive content detection:** [11], [20], [42]
- **Moral cognition in AI systems:** [9], [21], [33], [34], [35]
- **Diversity and re-ranking:** [22], [26]

**Appendix A.** Titled 'Ethnic Bias Experiment'; the section is truncated before substantive content appears. A content warning precedes the appendix regarding blurred inappropriate images and associated textual content.

<!-- quelle: References and Appendix -->

## GLOSSAR

- **inappropriate degeneration** — The phenomenon by which diffusion models trained on unfiltered internet data generate harmful, biased, or offensive content, including from prompts that do not explicitly request it.
- **I2P** — A testbed of 4703 real-world text-to-image prompts with inappropriateness scores from three detectors, designed to measure inappropriate content generation in diffusion models.
- **SLD** — A mitigation method that suppresses inappropriate content during the diffusion process without external classifiers or additional training, relying on the model's own learned knowledge of inappropriateness.
- **reporting bias** — Bias arising from the over-representation of certain content types in web-crawled training data, which the trained model then reflects in its outputs.
- **classifier-free guidance** — A conditioning method that adjusts score estimates by pushing the unconditioned noise prediction toward the text-conditioned prediction, without requiring a separate classifier.
- **safety guidance term γ** — A term added to the diffusion prediction that shifts generation away from a concept-conditioned estimate representing inappropriate content, scaled element-wise by μ.
- **safety threshold λ** — Parameter determining the location of the hyperplane that divides latent space into appropriate and inappropriate regions.
- **safety guidance scale s_S** — Scaling factor controlling the strength of safety guidance; can be set arbitrarily high without producing image artifacts because the underlying scaling factor µ is clipped.
- **Lexica** — A collection of real-world user-generated prompts for Stable Diffusion, sourced from its official Discord server, storing prompt, seed, guidance scale, and image dimensions for reproducibility.
- **PERSPECTIVE API** — A toxicity-scoring API used to estimate the toxicity of each text prompt in the I2P dataset.
