---
id: esser-et-al-2024-scaling-rectified-flow-transformers-for-high-resolution-image-synthesis
titel: Scaling Rectified Flow Transformers for High-Resolution Image Synthesis
autor: "Patrick Esser, Sumith Kulal, Andreas Blattmann, Rahim Entezari, Jonas Müller, Harry Saini, Yam Levi, Dominik Lorenz, Axel Sauer, Frederic Boesel, Dustin Podell, Tim Dockhorn, Zion English, Kyle Lacey, Alex Goodwin, Yannik Marek, Robin Rombach"
jahr: 2024
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2403.03206"
status: published
analyzed_at: "2026-07-31T10:28:48.789041+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Scaling Rectified Flow Transformers for High-Resolution Image Synthesis

## PROFIL

The text argues that Rectified Flow models, enhanced by a re-weighting of noise scales toward perceptually relevant scales and a novel transformer architecture enabling bidirectional information flow between image and text tokens, outperform established diffusion formulations for high-resolution text-to-image synthesis. It sets itself against standard diffusion models that rely on curved forward paths and fixed text representations via cross-attention, demonstrating that straight-line trajectories and separate learnable streams yield superior text comprehension, typography, and predictable scaling trends. For arts education, this research provides a technical framework for understanding and deploying advanced generative AI tools in creative practice and pedagogy.

## WISSEN

### Problem Framing and Thesis

Diffusion models generate data by inverting forward paths from data to noise. The choice of forward path has direct consequences for sampling: curved paths require many integration steps (each a neural network evaluation), while a straight path could be simulated in a single step with less error accumulation. **Rectified Flow** — a formulation connecting data and noise on a straight line — offers better theoretical properties but has not been decisively established in practice; prior empirical advantages were limited to small/medium class-conditional experiments.

The thesis advances rectified flow on three fronts. First, the authors introduce a **re-weighting of noise scales** in rectified flow models, biasing training toward perceptually relevant scales, analogous to noise-predictive diffusion models. A large-scale study compares this against established diffusion formulations for high-resolution text-to-image synthesis and demonstrates superior performance.

Second, they argue that the dominant text-to-image architecture — feeding a fixed text representation via cross-attention — is suboptimal. They propose a novel architecture using separate learnable streams for image and text tokens, enabling **bidirectional information flow** between modalities, improving text comprehension and typography. This is positioned against established backbones such as UViT and DiT.

Third, they conduct a scaling study showing predictable scaling trends in validation loss, with lower validation loss strongly correlating with improved results on T2I-CompBench, GenEval, and human preference ratings. Their largest models outperform open models (SDXL, SDXL-Turbo, Pixart-α) and closed-source models (DALL-E 3). Code, data, and weights are released publicly.

<!-- quelle: Problem Framing and Thesis -->

### Simulation-Free Training of Flows

Generative models map noise samples $x_1 \sim p_1$ to data samples $x_0 \sim p_0$ via an ODE whose velocity $v_\Theta$ is parameterized by neural network weights. Prior work (Chen et al., 2018) solved this ODE directly through differentiable solvers, but this is computationally prohibitive for large architectures. The alternative pursued here is to directly regress a vector field $u_t$ that generates a probability path between $p_0$ and $p_1$.

A forward process is defined with marginals $p_t(x_t | x_0) = \mathcal{N}(a_t x_0, b_t^2)$, where $a_0=1, b_0=0, a_1=0, b_1=1$ ensure consistency with data and noise distributions. Introducing $\psi_t$ and $u_t$ relating $z_t$, $x_0$, and $\epsilon$, the conditional vector field $u_t(\cdot | \epsilon)$ generates $p_t(\cdot | \epsilon)$, and a marginal vector field $u_t$ generating marginal paths $p_t$ can be constructed from these conditionals (Lipman et al., 2023).

The **Flow Matching** objective $\mathcal{L}_{FM}$ is intractable due to marginalization; **Conditional Flow Matching** $\mathcal{L}_{CFM}$ provides an equivalent, tractable objective. Inserting $\psi_t'$ and $\psi_t^{-1}$ yields an explicit loss. Introducing the **signal-to-noise ratio** $\lambda_t := \log \frac{a_t^2}{b_t^2}$, the objective is reparameterized as a noise-prediction objective with $\epsilon_\Theta := -2\lambda_t' b_t (v_\Theta - \frac{a_t'}{a_t} z)$.

The optimum is invariant under time-dependent weighting, enabling various weighted losses that affect optimization trajectory without changing the solution. A unified form (following Kingma & Gao, 2023) subsumes both flow matching and classic diffusion formulations, with $w_t = -\frac{1}{2}\lambda_t' b_t^2$ recovering $\mathcal{L}_{CFM}$.

<!-- quelle: Mathematical Framework for Flow Training -->

### Flow Trajectories and Tailored SNR Samplers

The paper considers several forward-process variants within a unified formalism. **Rectified Flows (RFs)** define straight paths between data and standard normal distributions, with weighting $w^{RF}_t = t/(1-t)$ and the network directly parameterizing velocity $v_\Theta$. **EDM** uses a forward process with $b_t = \exp(F^{-1}_N(t|\bar{m}, \bar{s}^2))$, an $F$-prediction parameterization, and loss $L^{w_{EDM}}_t$. The **Cosine** schedule combined with $\epsilon$-parameterization yields $w_t = \text{sech}(\lambda_t/2)$; with $v$-prediction, $w_t = e^{-\lambda_t/2}$. **(LDM-)Linear** schedules are variance-preserving ($b_t = \sqrt{1-a_t^2}$) with $a_t$ defined via diffusion coefficients $\beta_t$; DDPM uses linear $\beta_t$, LDM uses a quadratic interpolation of $\sqrt{\beta_t}$.

For RF models, the uniform timestep distribution $U(t)$ is suboptimal: the velocity target $\epsilon - x_0$ is hardest at intermediate $t$, since at $t=0$ the optimum is the mean of $p_1$ and at $t=1$ the mean of $p_0$. Changing the sampling density to $\pi(t)$ is equivalent to a weighted loss $L^{w_\pi}_t$. Three tailored densities are proposed:

- **Logit-Normal Sampling**: density $\pi(t) \propto \text{LogitNormal}(t; m, s)$ with $\text{logit}(t) = \log\frac{t}{1-t}$; location $m$ biases toward data ($m<0$) or noise ($m>0$); scale $s$ controls width. Sampled via $u \sim \mathcal{N}(m, s)$ mapped through the logistic function.
- **Mode Sampling with Heavy Tails**: defines $f_{\text{mode}}$ monotonic for $-1 \le s \le 2/\pi - 2$; density $\pi_{\text{mode}}(t;s) = |d f^{-1}_{\text{mode}}/dt|$; positive $s$ favors the midpoint, negative $s$ favors endpoints; $s=0$ recovers uniform $U(t)$.
- **CosMap**: maps $u \sim U(u)$ so the log-SNR matches the cosine schedule, solving $2\log\frac{\cos(\pi u/2)}{\sin(\pi u/2)} = 2\log\frac{1-f(u)}{f(u)}$ for $f(u)$.

<!-- quelle: Flow Trajectories and SNR Samplers -->

### Text-to-Image Architecture

The architecture enables text-conditional image sampling by integrating both modalities within a diffusion backbone. Following LDM, training occurs in the latent space of a pretrained autoencoder, with text conditioning encoded via pretrained, frozen text models.

The backbone builds on DiT, which conditions on timestep and class label via modulation. Here, modulation uses embeddings of the timestep and c_vec. However, because c_vec retains only coarse-grained information, the network also requires the sequence representation c_ctxt.

A combined sequence is constructed from text and image inputs: positional encodings are added, and 2×2 patches of the latent pixel representation x are flattened into a patch encoding sequence. After embedding the patch encoding and c_ctxt to a common dimensionality, the sequences are concatenated, followed by modulated attention and MLPs.

Because text and image embeddings are conceptually different, two separate weight sets are used per modality. This is equivalent to two independent transformers that join sequences for the attention operation, allowing each representation to operate in its own space while accounting for the other.

For scaling experiments, model size is parameterized by depth d (number of attention blocks): hidden size is set to 64·d (expanded to 4·64·d in MLP blocks), with attention heads equal to d.

<!-- quelle: Multimodal Diffusion Architecture -->

### Evaluation of Rectified Flow Formulations

The study determines which simulation-free training approach for normalizing flows is most efficient by controlling for optimization algorithm, model architecture, dataset, and samplers. Because losses across approaches are incomparable and do not correlate with output quality, evaluation uses validation losses, CLIP scores, and FID (calculated on CLIP features) under different sampler settings, evaluated on COCO-2014 validation split. Models are trained on ImageNet and CC12M.

61 formulations are tested, comprising:
- Both ε- and v-prediction loss with linear (eps/linear, v/linear) and cosine (eps/cos, v/cos) schedule.
- RF loss with π_mode(t; s) (rf/mode(s)) with 7 values for s chosen uniformly between -1 and 1.75, and additionally for s = 1.0 and s = 0 (uniform timestep sampling, rf/mode).
- RF loss with π_ln(t; m, s) (rf/lognorm(m, s)) with 30 values for (m, s) in the grid with m uniform between -1 and 1, and s uniform between 0.2 and 2.2.
- RF loss with π_CosMap(t) (rf/cosmap).
- EDM (edm(P_m, P_s)) with 15 values for P_m chosen uniformly between -1.2 and 1.2 and P_s uniform between 0.6 and 1.8. P_m, P_s = (-1.2, 1.2) corresponds to parameters in Karras et al., 2022.
- EDM with a schedule matching the log-SNR weighting of rf (edm/rf) and one matching v/cos (edm/cos).

For each run, the step with minimal validation loss (EMA weights) is selected; CLIP and FID are collected across 6 sampler settings with and without EMA. Ranking uses a non-dominated sorting algorithm: Pareto-optimal variants by CLIP and FID are iteratively identified, assigned the current iteration index, removed, and the process continues until all variants are ranked. Ranks are averaged over 24 combinations of sampler settings, EMA weights, and dataset.

Key finding: rf/lognorm(0.00, 1.00) consistently achieves good rank, outperforming uniform timestep sampling (rf), confirming the hypothesis that intermediate timesteps are more important. Only rectified flow formulations with modified timestep sampling outperform eps/linear. Some variants perform well in specific settings but poorly in others (e.g., rf/lognorm(0.50, 0.60) ranks best at 50 steps but rank 8.5 at 5 steps). Variants achieving best CLIP or FID individually typically perform badly on the other metric, with the exception of rf/mode(1.75). rf/lognorm(0.00, 1.00) achieves robust performance across metrics and datasets. Rectified flow formulations generally degrade less than others when reducing the number of sampling steps.

<!-- quelle: Evaluation of Rectified Flow Formulations -->

### Improving Modality-Specific Representations

Having established a rectified flow formulation that outperforms LDM-Linear and EDM, the authors turn to high-resolution text-to-image synthesis, arguing that final performance depends jointly on training formulation, neural network parameterization, and the quality of image and text representations.

**Improved Autoencoders.** Latent diffusion models operate in the latent space of a pretrained autoencoder mapping RGB inputs to lower-dimensional latents. The autoencoder's reconstruction quality upper-bounds achievable image quality. Increasing latent channels d from 4 to 8 to 16 monotonically improves FID (2.41→1.56→1.06), Perceptual Similarity (0.85→0.68→0.45), SSIM (0.75→0.79→0.86), and PSNR (25.12→26.40→28.62). Although predicting higher-d latents is harder, models with increased capacity scale better; d=16 exhibits superior sample FID scaling. The authors thus fix d=16.

**Improved Captions.** Human captions in large-scale datasets are simplistic, over-focusing on subjects while omitting background, composition, and displayed text. Following Betker et al. (2023), the authors generate synthetic captions via CogVLM but mix 50% original and 50% synthetic to prevent the model from forgetting concepts absent from the VLM's knowledge corpus. On the GenEval benchmark, the 50/50 mix outperforms original-only across most categories (Overall: 49.78 vs. 43.27), confirming the approach.

**Improved Text-to-Image Backbones.** The authors compare DiT (sequence-wise concatenation), CrossDiT (cross-attention to text tokens), UViT (UNet–transformer hybrid), and their novel MM-DiT, which uses separate trainable weight sets for text and image domains. On CC12M, vanilla DiT underperforms UViT; CrossDiT beats UViT though UViT learns faster initially; MM-DiT significantly outperforms all variants. Using three weight sets (separating CLIP and T5 tokens) yields only marginal gain over two at increased parameter and VRAM cost, so two sets are adopted.

<!-- quelle: Improving Modality-Specific Representations -->

### Scaling Up and High-Resolution Training

Before scaling to 8B parameters, data is filtered for three categories: (i) sexual content via NSFW-detection models, (ii) low aesthetic scores, (iii) perceptual/semantic duplicates via cluster-based deduplication. Image and text embeddings from frozen pretrained networks are precomputed once, as they remain constant during training.

When finetuning from 256² to higher resolutions with mixed aspect ratios, mixed-precision training becomes unstable. Rather than switching to full precision (~2× slower), QK-normalization is applied: RMSNorm with learnable scale normalizes Q and K embeddings before attention in both MMDiT streams. This prevents attention-logit growth instability and attention-entropy collapse in the last transformer blocks, enabling stable bf16-mixed-precision training. The technique also works retroactively on pretrained models without prior qk-normalization.

For varying aspect ratios, 2D positional frequency embeddings are adapted via extended and interpolated position grids (not direct interpolation), with bucketed sampling ensuring homogeneous batch sizes. Position grids are constructed from maximum latent-space dimensions and center-cropped before embedding.

Higher resolutions require more noise to destroy signal. Under a constant-image assumption, uncertainty σ(t,n) = t/(1−t)·√(1/n) decreases with pixel count n. A timestep shifting function maps t_n at resolution n to t_m at resolution m preserving equal uncertainty, parameterized by shift α = √(m/n). Human preference studies at 1024² show strong preference for shifts >1.5; α=3.0 is adopted for training and sampling. This implies a log-SNR shift of log(n/m).

Scaling studies across image (500k steps, batch 4096, 256²) and video (140k steps, batch 512, 16 frames × 256²) domains show smooth validation-loss decrease with no saturation. Validation loss correlates with CompBench, GenEval, and human preference. The largest d=38 model outperforms DALL-E 3 and other SOTA models on GenEval overall score and on Parti-prompts human preference across visual aesthetics, prompt following, and typography generation.

<!-- quelle: Scaling Up and High-Resolution Training -->

### Conclusion: Scaling Rectified Flow Models for Text-to-Image Synthesis

The work presents a scaling analysis of rectified flow models for text-to-image synthesis, advancing three interconnected contributions. First, a novel timestep sampling strategy for rectified flow training is proposed, improving over previous diffusion training formulations for latent diffusion models while retaining the favourable properties of rectified flows in the few-step sampling regime. Second, a transformer-based MM-DiT architecture is introduced that explicitly accounts for the multi-modal nature of the text-to-image task, demonstrating advantages over prior architectures. Third, a scaling study combining these contributions is conducted up to a model size of 8B parameters and 5 × 10²² training FLOPs.

The central empirical finding is that validation loss improvements correlate with both existing text-to-image benchmarks and human preference evaluations. This correlation establishes validation loss as a predictive proxy for downstream task quality, supporting the methodological validity of using it as a primary scaling metric. The combination of improved generative modeling and scalable, multimodal architecture achieves performance competitive with state-of-the-art proprietary models.

Critically, the scaling trend exhibits no signs of saturation at the studied scale, which the authors interpret as evidence that continued performance improvement is feasible with further scaling. This non-saturation finding positions the work not as a terminal result but as an interim data point in an ongoing scaling trajectory.

The broader impact section defers substantive ethical discussion to prior literature (Po et al., 2023), declining to highlight any work-specific societal consequences.

<!-- quelle: Conclusion and References -->

## GLOSSAR

- **Rectified Flow** — A generative model formulation that connects data and noise along a straight-line path, enabling single-step simulation with reduced error accumulation compared to curved diffusion paths.
- **forward path** — The prescribed trajectory from data to noise that the model learns to invert; its shape determines both training dynamics and sampling efficiency.
- **bidirectional information flow** — A two-way exchange of information between image and text token streams within the network, replacing the one-way injection of fixed text representations via cross-attention.
- **Flow Matching** — Objective $\mathcal{L}_{FM}$ that regresses a marginal vector field $u_t$ generating probability paths between $p_0$ and $p_1$, rendered tractable by its conditional counterpart.
- **Conditional Flow Matching** — Objective $\mathcal{L}_{CFM}$ using conditional vector fields $u_t(\cdot | \epsilon)$ that is equivalent to Flow Matching but avoids intractable marginalization.
- **signal-to-noise ratio** — Quantity $\lambda_t := \log(a_t^2 / b_t^2)$ used to reparameterize the flow matching loss into a noise-prediction objective and to unify analysis across formulations.
- **Logit-Normal Sampling** — A timestep density based on the logit-normal distribution, with location and scale parameters controlling bias toward data or noise and distribution width.
- **Mode Sampling with Heavy Tails** — A timestep density that remains strictly positive at endpoints 0 and 1, with a scale parameter controlling midpoint versus endpoint emphasis.
- **DiT** — A Diffusion Transformer architecture that uses a modulation mechanism to condition the network on the diffusion timestep and a class label.
- **c_vec** — Pooled text representation used as input to the modulation mechanism, retaining only coarse-grained information about the text input.
