---
id: turner-et-al-2023-steering-language-models-with-activation-engineering-actadd
titel: Steering Language Models with Activation Engineering
autor: "Alexander Matt Turner, Lisa Thiergart, Gavin Leech, David Udell, Juan J. Vazquez, Ulisse Mini, Monte MacDiarmid"
jahr: 2024
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2308.10248"
status: published
analyzed_at: "2026-07-31T10:16:22.496026+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Steering Language Models with Activation Engineering

## PROFIL

The text argues that *activation engineering*, specifically the *ActAdd* technique, reduces the *elicitation overhang* of latent language model capabilities by modifying intermediate activations at inference time using a *steering vector* computed from contrasting prompt pairs. It sets itself against prompt engineering, which is unreliable and constrained by the training distribution, and weight-based interventions, which degrade overall model performance. By adding these vectors as "virtual bias terms" during the forward pass, the method achieves targeted control over high-level output properties while preserving off-target performance. For arts education, this lightweight, optimization-free approach provides a practical mechanism to dynamically steer generative models toward specific aesthetic or thematic qualities without compromising their general linguistic competence.

## WISSEN

### Problem framing and thesis

Prompt engineering and finetuning optimize model performance on metrics but fail to fully elicit latent capabilities. The text posits an *elicitation overhang*: models possess abilities that do not emerge without specific interventions (e.g., step-by-step prompting), even though these interventions add no new information or alter the computational graph. Because prompt engineering is unreliable, the text introduces *activation engineering*—the inference-time modification of activations to steer outputs.

The argument for activation engineering over prompt engineering rests on capabilities absent from the training distribution. If a model accurately estimates a distribution where "eloquent" and "mathematical" prose never co-occur, no prompt can elicit text exhibiting both. Activation engineering, however, can simultaneously activate the distinct internal circuitries for both properties.

To demonstrate this, the text introduces *ActAdd* (Activation Addition). ActAdd computes a *steering vector* by contrasting intermediate activations on a prompt pair (e.g., 'Love' vs 'Hate'). This vector acts as a "virtual bias term" added directly to the forward pass at inference time, shifting activations to steer high-level output properties (e.g., sentiment, topic) while preserving off-target performance. ActAdd requires no machine optimization and operates on a single pair of data points.

The text unifies related literature under activation engineering, introduces ActAdd (achieving SOTA on toxicity reduction and sentiment control), and verifies the preservation of general capabilities in steered models.

<!-- quelle: Problem framing and thesis -->

### Related work and positioning

The section locates ActAdd within the landscape of LLM steering. Prior approaches are organized by intervention site: weights (supervised finetuning, RLHF, steerable layers, weight editing), decoding (guided/trainable decoding), prompt (automated prompt engineering), token embeddings (soft prompting), and activations. Weight-based interventions carry known side-effects on overall model performance. Activation engineering freezes LLM weights and adds activation vectors during forward passes. Within activation engineering, methods differ by how the vector is obtained: gradient-based per-query search (Dathathri 2020, Subramani 2022, Hernandez 2023) versus direct computation from differences between prompt pairs (ActAdd and Li et al. 2023b). ActAdd uses no gradient descent or optimization. Against Li et al. 2023b's ITI, ActAdd (1) covers a broader range of goals than truthfulness alone, (2) adds steering vectors to a subset of sequence positions rather than all positions, and (3) requires as few as 2 samples versus dozens. Subsequent work (Liu et al. 2023 on in-context vectors; Zou et al. 2023 on representation engineering) followed ActAdd; the authors note differentiation by model scope (LLaMA-3, OPT, GPT-2, GPT-J) and task scope (detoxification, sentiment control).

<!-- quelle: Related work and positioning -->

### How ActAdd Works

ActAdd operates on decoder-only Transformer neural networks by manipulating their 'residual streams'—the sequences of intermediate activation vectors processed by each layer. The method takes a pair of natural-language prompts $(p^+, p^-)$, where $p^+$ represents a target property and $p^-$ its opposite. After padding the prompts to the same token length, a forward pass is performed on each to record activations at a target layer $l$. The difference $h^l_+ - h^l_-$ forms a steering vector, intuitively capturing the difference between a prompt with the target property and one without it.

To steer the model, this steering vector is rescaled by an 'injection coefficient' $c$ (representing intervention strength) and added to the residual stream input of layer $l$ at a specified sequence position $a$ during the forward pass of a user prompt $p^*$. The forward pass then continues to produce the steered output. Hyperparameter tuning selects $c$ and the injection layer $l$, with middle layers proving most effective.

The method is evaluated on two criteria: 1) whether steering vectors effectively elicit the desired behavioral shift, and 2) whether they preserve the model's general capabilities. Perplexity-based experiments are run on GPT-2-XL, while toxicity and sentiment experiments use OPT and LLaMA-3.

<!-- quelle: Method: How ActAdd works -->

### Activation Addition Works

ActAdd modifies next-token probabilities by injecting a steering vector (e.g., 'wedding') into GPT-2-XL. The argument proceeds by demonstrating that this intervention reduces perplexity on target-topic text, shifts token probabilities specifically toward topic-relevant tokens, and achieves high success rates at optimal injection layers, thereby controlling the model's topic.

First, ActAdd reduces perplexity on target-topic sentences while preserving performance on unrelated text. Using a 300k document sample from OpenWebText (half wedding-related), the steered model assigns higher probability (lower perplexity) to wedding-related sentences. Documents are considered wedding-related if they contain one of the following words: wedding, weddings, wed, marry, married, marriage, bride, groom, and honeymoon.

Second, to rule out spurious perplexity reductions, the shift in token log probabilities is analyzed via Q-Q plot. The distribution is approximately normal with heavy tails; the positive tail is significantly heavier, indicating a reliable increase in probability for a specific set of tokens. The most increased tokens are primarily wedding-related, while decreased tokens share no obvious theme.

Third, sweeping injection layers reveals that steering effectiveness peaks at layer 6, achieving >90% topic steering success compared to a ~2% baseline, before declining.

Finally, ActAdd controls topic generation across a range of topics. Using GPT-3.5 to score completions from a generic prompt, ActAdd yields a 5-20% boost in relevance for all tested topics at injection coefficient c=2, with the exception of 'art'.

<!-- quelle: Results: Perplexity and topic steering -->

### ActAdd: Toxicity Reduction, Sentiment Control, and Knowledge Preservation

ActAdd is benchmarked against six baselines (PREADD, FUDGE, Air-Decoding, prompting, unsteered) across three tasks. Finetuning is excluded to focus on lighter-weight interventions requiring minimal gradient updates; Gu et al. 2022 is excluded for unreproducibility and impractical disfluency (54.6).

**Toxicity (§4.3):** On RealToxicityPrompts (n=1000, 5 repeats, Perspective API), ActAdd-OPT achieves 8% lower toxicity than the second-best PREADD-D-OPT; ActAdd-LLaMA-3 yields a 5% drop over unsteered LLaMA-3 with minimal fluency penalty. More recent models are less toxic by default, yet ActAdd-OPT even outperforms unsteered LLaMA-3.

**Sentiment (§4.4):** On IMDb (n=1000), using SiEBERT for sentiment classification, conditional perplexity (GPT-3 davinci-002) for fluency, and cosine similarity for relevance, ActAdd achieves state-of-the-art success steering negative-to-positive. The only method outperforming ActAdd in positive-to-negative (PREADD-S, 0.631 vs 0.432) incurs a large fluency penalty (68.4 vs 24.2) and lower relevance. All steering methods worsen fluency: 1.5–3x for ActAdd, 7x for PREADD.

**Knowledge preservation (§4.5):** On ConceptNet from the LAMA benchmark (n=29,774), the model predicts factual completions with and without the wedding activation addition. P@K (probability the correct label is among the model's top-K predicted tokens) is computed across a range of K. ActAdd shows negligible impact on off-target answer probabilities across all K values, demonstrating that steering does not degrade the model's general factual knowledge.

<!-- quelle: Results: Toxicity, sentiment, and capability preservation -->

### Composability, Limitations, and Comparisons of ActAdd

ActAdd's algebraic combination of forward passes (e.g., composing h+, h-, h*) constitutes composition of separate forward passes—an untrained-for operation whose success is itself evidence for compositional representations, independent of weight-level task-composition arithmetic.

**Limitations.** ActAdd requires user-supplied injection coefficient c, intervention layer l, and sequence alignment a (fixed at a=1 so far). These hyperparameters make ActAdd less user-friendly than prompt engineering, though they are stable across use cases and do not require per-case sweeps. ActAdd's impact on reasoning is unexamined; it is inapplicable with API-only access, requiring cached and exposed intermediate activations.

**vs. finetuning.** Finetuning is better understood and more flexible—activation engineering likely cannot teach new skills. ActAdd's advantages: no backward passes (runs on inference-only hardware), minimal implementation effort, and minimal labeled data (just a steering prompt pair); most contrast pairs were found in minutes, enabling rapid iteration even for nontechnical users. Finetuning may also be unable to elicit the same capabilities ActAdd can.

**vs. prompt engineering.** Activation additions are continuously weighted (prompts are discrete); intensifying steering requires only increasing c, not editing the prompt. They consume no context-window tokens. Prompting is more flexible and cheaper, but activation additions may elicit capabilities prompting cannot.

**Interpretability.** ActAdd's success provides experimental evidence for linear representation: features are represented as directions in activation space that remain approximately stable across input classes. Steering vectors establish causality—at least in examined contexts—by demonstrating that a given direction (e.g., Love-Hate) is responsible for steering model completions.

**Value alignment.** Activation engineering can flexibly retarget LLM behavior without damaging general performance. The authors speculate ActAdd changes the model's currently active mixture of goals and priorities; suitably developed, it could enable safety progress while preserving capabilities.

<!-- quelle: Discussion: Composability, limitations, and comparisons -->

### Conclusion: Activation Engineering and the Case for ActAdd

Existing methods for steering language models — prompt engineering, controlled decoding, and finetuning — each have benefits but fail to elicit the models' full capabilities. Activation engineering addresses this gap by strategically perturbing activations at inference time, offering a more reliable route to eliciting latent abilities. The specific method introduced, **Activation Addition** (ActAdd), steers a model by shifting its inference-time activations along a chosen direction, exemplified by the 'Love'–'Hate' vector. ActAdd is both lightweight and effective: it achieves state-of-the-art results on toxicity reduction and sentiment shift while preserving overall model capabilities. The success of ActAdd is taken as evidence for the broader promise of activation engineering as a paradigm, with future work anticipated to further realize that potential.

<!-- quelle: Conclusion -->

### Reproducibility, broader impacts, and appendices

Code and data are deposited at Zenodo (https://zenodo.org/records/13879423). The wedding-related subset of OpenWebText was curated by retaining documents with wedding-related words; only preprocessing was removal of null-character sequences; documents were sentence-tokenized with Punkt.

Models: GPT-2-XL (primary), with replication on Llama-1-13B and GPT-J-6B. Toxicity and sentiment experiments use OPT and LLaMA-3-8B. Sentence embeddings computed with all-MiniLM-L6-v2 (cosine similarity for relevance); sentiment classified with SiEBERT. Toxicity scored via Perspective API; fluency via OpenAI davinci-002 (PREADD baseline used discontinued davinci-001).

All generations ran on seed 0; qualitative results validated on seeds 1 and 2. Precommitted sampling hyperparameters: temperature=1.0, freq_penalty=1.0, top_p=0.3. An external blinded researcher independently tuned an unmodified GPT-2-XL, finding temperature=0.6, top_p=0.5 superior; all qualitative results reproduced at this setting. Toxicity/sentiment experiments used the same hyperparameters; other authors' numbers used freq_penalty=0.0, top_p=1.0.

For the unsteered OPT sentiment baseline, NegToPos consistently outperformed PosToNeg across hyperparameter combinations including those in Pei et al. 2023, whereas PREADD reported similar success for both. Reported OPT values are the authors' own calculations.

Best-of-K: K=3 completions generated per demonstration for both normal and steered forward passes. Table 6 shows the subjectively most compelling pair from the first three seed-0 pairs. Of 12 activation additions judged to demonstrate a distinct ability, 1 was excluded because its first three seed-0 completions were unusually unimpressive; 11 were retained.

ActAdd hyperparameters (l, c): simple grid search, typically c ∈ [3, 20], l ∈ [6, 24]. No complete statistics reported.

Hardware: Nvidia RTX A5000 (24GB), Intel Core i9-10900X (32GB RAM). Framework: transformer-lens 1.4.0, torch 1.13.1.

<!-- quelle: Reproducibility, broader impacts, and appendices -->

## GLOSSAR

- **elicitation overhang** — The gap between a model's latent capabilities and what can be elicited via known interventions.
- **activation engineering** — A paradigm that strategically perturbs model activations at inference time to more reliably elicit the full capabilities of language models.
- **ActAdd** — The present work's method of directly computing a steering vector from differences between prompt pairs and adding it to a subset of sequence positions in a frozen LLM's forward passes.
- **ITI** — Inference-Time Intervention (Li et al. 2023b), a method computing steering vectors via trained linear probes, applied at all sequence positions, requiring dozens of samples.
- **residual streams** — The sequences of intermediate activation vectors processed by each layer in a Transformer network.
- **steering vector** — A vector produced by setting a target topic and injected into a specific layer of a model to control its generation topic.
- **injection coefficient** — A scalar value that rescales the steering vector's contribution to the residual stream, representing intervention strength.
- **perplexity** — A measure of how well a probability model predicts a sample, used here to test if the model is effectively steered to generate target-topic text.
- **P@K** — The probability that the expected correct label is among the model's top-K predicted tokens, conditioned on the prompt; used to measure knowledge preservation.
- **SiEBERT** — A model finetuned on sentiment data used to classify the sentiment of generated outputs for evaluation.
