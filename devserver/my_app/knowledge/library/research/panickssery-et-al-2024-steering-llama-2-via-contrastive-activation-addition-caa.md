---
id: panickssery-et-al-2024-steering-llama-2-via-contrastive-activation-addition-caa
titel: Steering Llama 2 via Contrastive Activation Addition
autor: "Nina Panickssery, Meg Tong, Nick Gabrieli, Evan Hubinger, Julian Schulz, Alexander Matt Turner"
jahr: 2024
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2312.06681"
status: published
analyzed_at: "2026-07-31T10:20:27.685722+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Steering Llama 2 via Contrastive Activation Addition

## PROFIL

The text argues that Contrastive Activation Addition (CAA) can steer high-level alignment-relevant behaviors in Large Language Models (LLMs) by computing 'steering vectors' from mean residual-stream activation differences between contrastive example pairs, functioning on top of existing RLHF finetuning. It sets itself against the opacity of traditional alignment methods like RLHF and prompt engineering, and distinguishes itself from prior activation engineering techniques—such as Turner et al.'s Activation Addition and Zou et al.'s representation extraction—by utilizing hundreds of diverse contrast pairs and applying the vector to all post-prompt token positions at a single residual stream layer. For arts education, this method offers a precise, interpretable mechanism to modulate generative AI behaviors, such as mitigating hallucination or adjusting stylistic outputs, when incorporating LLMs into creative and pedagogical practices.

## WISSEN

### Problem Framing and Thesis

Existing LLM alignment methods—RLHF, instruction finetuning, prompt engineering—face unresolved challenges: dataset representativeness, hallucination, out-of-distribution failures, and opacity of mechanism. The family of 'activation engineering' or 'representation engineering' techniques, which perturb model activations directly, has shown promise but lacks robust verification across models and behavior types. The thesis: Contrastive Activation Addition (CAA) can steer high-level alignment-relevant behaviors in Llama 2 Chat by computing 'steering vectors'—mean residual-stream activation differences between contrastive positive/negative example pairs—and adding these vectors at all post-prompt token positions with a chosen multiplier. CAA operates on top of existing RLHF finetuning, enabling study of the interaction between finetuning and activation engineering. Across seven tested behavior categories, adding/subtracting steering vectors reliably increased/decreased target behaviors as rated by GPT-4, with minimal capability reduction. The work also investigates transfer, comparison to system-prompting and finetuning, and geometrical relationships among steering vectors.

<!-- quelle: Problem Framing and Thesis -->

### Related Work and Demarcation

CAA is positioned against four approaches. Against **Activation Addition** (Turner et al., 2023), which uses a single contrast pair and intervenes at the first token position, CAA uses hundreds of diverse contrast pairs to reduce noise and encodes behavior more precisely, adding the steering vector to all and only token positions after the original prompt. Against Li et al. (2023), who shift activations along a **Mean Difference** vector via sparse attention heads, CAA applies directly to the **residual stream** without searching for heads and validates on a broader range of alignment-relevant behaviors in RLHF-trained models. Against Zou et al. (2023), who extract concept representations, CAA employs an optimized multiple-choice format yielding contrastive prompts differing by a single token, and focuses on steering rather than extraction, comparing against system-prompting and supervised finetuning. Against Liu et al. (2023), who steer attention activations at all layers, CAA intervenes on the residual stream at a single layer. Related work on linear representation formalization (Park et al., 2023) and sentiment verification (Tigges et al., 2023) provides further context.

<!-- quelle: Related Work and Demarcation -->

### CAA Methodology and Dataset Construction

CAA generates a steering vector that shifts a language model's output distribution toward a target behavior during inference. The method uses paired prompts—identical multiple-choice questions with opposite answer letters appended. The "positive" prompt ends with the letter for the target behavior; the "negative" prompt ends with its opposite. By computing the average difference in activations at the answer-letter position across all pairs, the approach isolates the behavior-relevant direction in latent space while canceling confounding variables. This extraction technique is termed Mean Difference (MD), shown to produce vectors similar to PCA-based methods. Formally, the MD vector for layer L is the mean activation difference between positive and negative completions across the dataset. Evaluation uses Llama 2 7B/13B Chat (RLHF-trained) and the 7B base model for transfer testing. Datasets cover seven alignment-relevant behaviors: AI Coordination, Corrigibility, Hallucination, Myopic Reward, Survival Instinct, Sycophancy, and Refusal. Sources include Anthropic's Advanced AI Risk dataset, Sycophancy datasets, and GPT-4-generated contrastive datasets for Hallucination and Refusal. During inference, the steering vector is added to every token position after the initial prompt.

<!-- quelle: Methodology and Dataset Construction -->

### Activation Space Visualization

PCA projections of model activations on contrastive datasets assess linear separability of internal representations, which predicts whether a dataset yields effective steering vectors. Due to the multiple-choice prompt format, activations always separate by token identity ('A' vs 'B') — termed **letter clustering** — but datasets genuinely capturing the target behavior should additionally exhibit **behavioral clustering**: separation by whether the model output matches that behavior. Across studied behaviors, behavioral clustering emerges around one-third through the layers, indicating higher-level behavior representations in those layers, consistent with prior work on emotion representations in middle and later layers. Linear separability of residual stream activations in two dimensions often appears suddenly after a particular layer. For example, in Llama 2 7B Chat on the refusal contrastive dataset, behavioral clustering is absent at layer 9 but visibly emerges at layer 10.

<!-- quelle: Activation Space Visualization -->

### Behavioral Evaluation of CAA

Steering vectors generated per behavioral dataset are evaluated on 50 held-out multiple-choice questions. A layer sweep with multipliers of -1 and 1 identifies optimal layers: layer 13 (and adjacent) for the 7B model, layers 14–15 for the 13B model. CAA consistently steers multiple-choice outcomes across all tested behaviors.

To test generalization beyond contrived multiple-choice settings, CAA is applied to open-ended generation. Sycophancy questions are manually written; other datasets adapt held-out multiple-choice items into open-ended prompts by omitting answer options. GPT-4 rates responses on a 1–10 scale for displayed behavior.

Exploration of wider multiplier ranges reveals that larger multipliers degrade open-ended text quality, as assessed by both GPT-4 and human readers. The multiplier range is therefore limited to balance steering effectiveness against generation quality.

<!-- quelle: Behavioral Evaluation of CAA -->

### CAA compared with system-prompting and finetuning

Section 5 contrasts CAA with system-prompting, chosen over few-shot-prompting after initial experiments showed the latter less effective. Positive and negative system prompts elicit or suppress target behaviors. CAA modifies behavior beyond prompting alone: adding the steering vector increases scores beyond a positive prompt; subtracting reverses this. The authors hypothesize CAA's advantage lies in precise control via the multiplier and more effective isolation of behavioral variables by aggregating across a large prompt dataset.

Section 6 compares CAA to supervised finetuning on the same multiple-choice dataset. Finetuning reaches high test accuracy and generalizes to open-ended generation. For 3 of 7 behaviors CAA steers beyond finetuning in both directions, though counter-intuitive interactions appear (e.g., positive steering on finetuned Refusal reduces refusal score). Finetuning causes out-of-distribution failure on Sycophancy, where CAA generalizes. Finetuning needs 10 minutes on 2 GPUs versus CAA's under 5 minutes on one GPU. Layering CAA on finetuning improves open-ended generation more than multiple-choice performance, suggesting CAA steers existing learned representations, yielding better out-of-distribution generalization than full-model finetuning.

<!-- quelle: Comparison with System-Prompting and Finetuning -->

### Effect of CAA on General Capabilities

To verify that CAA does not degrade general model capabilities, the authors evaluate on MMLU (57-subject multiple-choice benchmark) and TruthfulQA. On MMLU, steering vectors applied at layer 14 of Llama 2 13B Chat with multipliers +1 and -1 across all seven behaviors (AI Coordination, Corrigibility, Hallucination, Myopic Reward, Survival Instinct, Sycophancy, Refusal) show no significant performance change relative to the baseline (multiplier 0), with scores remaining near 0.63 average probability assigned to the correct answer. On TruthfulQA, subtracting the sycophancy vector yields a small improvement in truthfulness. The argument thus establishes that behavioral steering via CAA preserves general capabilities while, in the sycophancy case, marginally enhancing truthfulness.

<!-- quelle: Impact on General Capabilities -->

### Interpreting CAA Mechanisms

CAA steering vectors detect behavioral features at semantically relevant tokens: the dot product between per-token residual stream activations and a steering vector corresponds intuitively with how much of the target behavior is 'present' in that token (e.g., 'just a small one now' shows positive myopia component; 'hack into your friend's Instagram account' shows negative refusal component).

Inter-layer similarity of vectors generated for the same behavior is higher for closer layers and diminishes with distance, declining more slowly in the latter half—suggesting representation 'convergence' once high-level abstract concept information is extracted. A vector from layer 13 transfers to other layers, even amplifying effect at some earlier layers, confirming the direction is not layer-specific but a general behavior representation. A steep drop-off around layer 17 indicates relevant abstract information has been consumed for downstream processing.

Base-to-chat model similarity decays with depth except a peak between layers 7–15, where RLHF has smaller effect on representation. Base-model vectors transfer significantly to chat models, especially layers 10–15.

<!-- quelle: Interpretation of CAA Mechanisms -->

### Discussion, Limitations, and Ethics of CAA

CAA is broadly applicable for steering RLHF-trained LLMs, generalizing from multiple-choice contexts to open-ended generation with minimal performance degradation. Its additive nature makes it compatible with standard alignment techniques (system-prompting, finetuning), enabling layered steering. CAA affords inference-time control of latent variables with high sample efficiency, eliciting internal states difficult to trigger via prompting alone, while also yielding insights into emergent linear representations of abstract concepts.

Future work: (1) intervening at targeted token positions rather than every post-prompt token, improving the intervention-size/effect-size trade-off; (2) steering outside the residual stream (e.g., after MLP, before merging) to localize representations; (3) red-teaming applications—CAA as an adversarial probe, where easy elicitation of unwanted behaviors signals deployment risk, and resistance to small perturbations offers stronger safety guarantees.

Limitations: GPT-4 eval scores are sensitive to prompt wording and carry evaluator bias (mitigated by manual inspection); finetuning baselines are not hyperparameter-optimized, potentially understating finetuning's effect; prompting baselines are not exhaustively searched, though this itself indicates CAA's reliability advantage; vector normalization standardizes across behaviors but not across layers, preserving 'natural norm' yet potentially skewing layer-optimality results.

Ethically, CAA serves helpful/honest/harmless alignment but carries misuse risk—steering toward harmful or biased outputs.

<!-- quelle: Discussion, Limitations, and Ethics -->

### Appendices: Answer Conditioning and Hallucination Dataset

Appendix B validates that multiple-choice prompts elicit target behaviors by examining model continuations after answering A or B. The context before the 'A/B' is behavior-neutral; answering A or B steers the model toward justifying that behavior, simulating exhibiting or not exhibiting it. Example: Llama 2 7B Chat conditioned on a sycophantic response to a Sikh teachings question (Table 6) generates reasons agreeing with the user, demonstrating the format's effectiveness for producing steering vectors.

Appendix C outlines generating a custom hallucination dataset. Hallucination is categorized into two types:
- Unprompted Hallucination: the LLM produces distorted or fabricated information in response to a factually accurate prompt.
- Contextually-Triggered Hallucination: the LLM builds a false narrative in response to a factually inaccurate prompt.

The dataset uses multiple-choice questions displaying both types. For contextually-triggered hallucination, questions pose an incorrect assumption; one answer option accepts the falsehood, while the other rejects and flags it.

<!-- quelle: Appendices and References -->

## GLOSSAR

- **Contrastive Activation Addition (CAA)** — A steering method that computes mean residual-stream activation differences between contrastive behavior pairs and adds the resulting vector at inference time with a chosen multiplier.
- **steering vectors** — Vectors obtained by averaging residual stream activation differences across many positive/negative contrastive example pairs for a target behavior.
- **activation engineering** — A family of alignment techniques that modify a model's internal activations during forward passes to alter behavior.
- **Activation Addition** — A steering technique that generates vectors from the difference in activations of a single prompt pair at one layer and token position.
- **Mean Difference (MD)** — A technique for extracting a steering vector by averaging the activation difference between positive and negative prompt completions at a given layer.
- **residual stream** — The internal representation stream in a transformer to which CAA directly applies its steering vector, bypassing attention-head search.
- **CAA** — Contrastive Activation Addition: a method for steering LLM behavior by applying steering vectors derived from contrastive activation differences to the model's residual stream.
- **steering vector** — A direction in the model's activation space, computed from contrastive examples, that when added shifts the model's behavior along a target dimension.
- **letter clustering** — Separation of activations by which multiple-choice token ('A' or 'B') they originate from, an artifact of prompt format rather than behavior.
- **behavioral clustering** — Separation of activations based on whether the model output matches the target behavior, indicating the dataset captures the behavior of interest.
