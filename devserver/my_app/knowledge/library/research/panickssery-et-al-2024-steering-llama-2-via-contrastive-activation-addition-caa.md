---
id: panickssery-et-al-2024-steering-llama-2-via-contrastive-activation-addition-caa
titel: Steering Llama 2 via Contrastive Activation Addition
autor: "Nina Panickssery, Meg Tong, Nick Gabrieli, Evan Hubinger, Julian Schulz, Alexander Matt Turner"
jahr: 2024
quelle: "arXiv preprint (arXiv:2403.06862)"
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2312.06681"
status: published
checks: passed
review: passed
analyzed_at: "2026-11-15T11:27:50.584797+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.3
doc_type: scholarly_article
seitenzahlen: gedruckt
---

# Steering Llama 2 via Contrastive Activation Addition

## PROFIL

The article "Steering Llama 2 via Contrastive Activation Addition" is written by Nina Panickssery, Meg Tong, Nick Gabrieli, Evan Hubinger, Julian Schulz, and Alexander Matt Turner, affiliated with Anthropic, Harvard University, the University of Göttingen, and the Center for Human-Compatible AI, and is addressed to the AI-alignment and model-interpretability research community. Its subject is Contrastive Activation Addition (CAA), a method for steering the behavior of large language models by adding a "steering vector" to residual-stream activations during forward passes; the authors' claim is that CAA precisely controls alignment-relevant behaviors (AI Coordination, Corrigibility, Hallucination, Myopic Reward, Survival Instinct, Sycophancy, Refusal) in Llama 2 Chat models, works on top of finetuning and system-prompting, minimally harms capabilities, and yields interpretive insight into linear concept representation. The method section describes constructing Mean Difference vectors from hundreds of contrastive multiple-choice prompt pairs and applying them at all post-prompt token positions; subsequent sections evaluate steering on held-out multiple-choice and GPT-4-rated open-ended generation, compare CAA against system-prompting and one-epoch SGD finetuning (finding CAA cheaper, more doseable, and better at out-of-distribution generalization), assess capability effects on MMLU and TruthfulQA, and interpret mechanisms via per-token and inter-layer cosine-similarity analyses, including transfer between base and chat models. The paper builds on and positions itself against Turner et al. (2023) on Activation Addition, Li et al. (2023) on truthful attention heads, Zou et al. (2023) on concept extraction, and Liu et al. (2023) on toxicity steering, citing Park et al. (2023) and Tigges et al. (2023) on linear representation and drawing datasets from Perez et al. (2022) plus newly generated GPT-4 datasets. It closes with future directions (targeted token positions, steering outside the residual stream, red-teaming applications), stated limitations (GPT-4 rater bias, unoptimized baselines, vector normalization across layers), and appendices with datasets, examples, system prompts, finetuning accuracies, and MIT-licensed code on GitHub. The document itself frames its usability for machine-learning research, AI safety evaluation, and interpretability study; it does not explicitly address arts-education disciplines or situations.

## WISSEN

### Purpose and Thesis (p. 1–2)

The paper introduces **Contrastive Activation Addition (CAA)**, a method for steering the behavior of large language models (LLMs) by modifying their internal activations during forward passes. The authors—Nina Panickssery, Meg Tong, Nick Gabrieli, Evan Hubinger, Julian Schulz, and Alexander Matt Turner (affiliated with Anthropic, Harvard University, University of Göttingen, and the Center for Human-Compatible AI)—argue that CAA can precisely control alignment-relevant behaviors (such as sycophancy, refusal, or hallucination) in Llama 2 Chat models, works on top of traditional alignment techniques like finetuning and system-prompting, minimally harms capabilities, and offers interpretive insight into how high-level concepts are linearly represented inside LLMs.

### Related Work and Positioning (p. 2–3)

CAA builds on and extends several activation-engineering approaches:
- **Turner et al. (2023), Activation Addition**: computes steering vectors from a single contrastive prompt pair, applied to the first token position; it was only tested on GPT-2-XL and is not robust across prompts. CAA improves on this by averaging over hundreds of contrast pairs and applying the vector to all token positions after the prompt.
- **Li et al. (2023)**: uses linear probes and Mean Difference vectors to shift "truthful" attention heads; CAA instead intervenes directly in the residual stream and covers a broader range of behaviors in RLHF-trained models.
- **Zou et al. (2023)**: extracts representations of concepts like honesty; CAA adopts their Mean Difference approach but uses an optimized multiple-choice format and focuses on steering rather than extraction.
- **Liu et al. (2023)**: steers attention activations at all layers to reduce toxicity; CAA steers the residual stream at a single layer.
- The paper also cites Park et al. (2023) on formalizing "linear representation" and Tigges et al. (2023) on verifying linear sentiment representations.

### Method: Constructing and Applying Steering Vectors (p. 3–4)

The core idea is to compute a "steering vector" that shifts the model's output distribution toward a desired behavior:
1. Build a dataset of multiple-choice questions with two answer options, labeled 'A' or 'B'—one option matching the target behavior, the other its opposite.
2. For each question, create a pair of prompts that are identical except for the appended answer letter.
3. Run the model on both prompts and record the residual stream activations at the token position of the answer letter.
4. Average the difference between positive and negative activations over all pairs; this **Mean Difference (MD)** vector is the steering vector for a given layer.
5. During inference, add the vector (with a chosen multiplier, positive or negative) to every token position after the user's prompt.

Because only the answer letter varies within a pair, confounding variables cancel out and the direction corresponding to the behavior is isolated. The authors evaluate on Llama 2 7B Chat and 13B Chat (RLHF-trained), and also generate vectors from the Llama 2 7B base model for transfer tests, using Huggingface Transformers and PyTorch.

**Behaviors tested**: AI Coordination, Corrigibility, Hallucination, Myopic Reward, Survival Instinct, Sycophancy, and Refusal. Datasets come mainly from Anthropic's "Advanced AI Risk" human-written evaluation dataset (Perez et al., 2022); Sycophancy uses Anthropic's "Sycophancy on NLP" and "Sycophancy on political typology" datasets; Hallucination and Refusal datasets are newly generated with GPT-4.

**PCA visualization**: Projecting activations via PCA shows that "behavioral clustering" (separation by whether the answer matches the behavior) emerges suddenly around one-third of the way through the layers—e.g., at layer 10 but not layer 9 for the Refusal dataset in Llama 2 7B Chat—indicating that middle layers contain higher-level behavioral representations.

### Effects of CAA on Behavior (p. 4–5)

- **Multiple-choice evaluation**: Steering vectors are tested on 50 held-out questions per behavior. Sweeping all layers with multipliers of -1 and +1 reveals optimal steering layers: layer 13 (and adjacent layers) for the 7B model, usually layer 14 or 15 for the 13B model. CAA consistently steers results for all seven behaviors.
- **Open-ended generation**: CAA generalizes to free-form answers of open-ended questions (adapted from held-out multiple-choice questions, or manually written for sycophancy). GPT-4 rates responses 1–10 on how much of the steered behavior they display. Larger multipliers degrade text quality, so multiplier ranges are limited to balance steering strength against generation quality.

### Comparison with System-Prompting (p. 5–6)

The authors compare CAA to system prompts (positive prompts instructing the model to exhibit the behavior, negative prompts the opposite), finding few-shot prompting less effective than system-prompting in initial experiments. In Llama 2 13B Chat (steering at layer 13, scored as average token probability of the behavior-matching answer over 50 test examples), CAA modifies behavior beyond prompting alone for most behaviors—adding the vector raises the behavioral score above the positive system prompt, and subtracting lowers it. They hypothesize CAA offers better control because the multiplier allows precise dosing and the dataset aggregation isolates behavioral variables more effectively.

### Comparison with Finetuning (p. 6)

Llama 2 7B Chat is finetuned for one epoch with SGD (learning rate 1 × 10⁻⁴) on the same multiple-choice datasets to incentivize the positive or negative answers. Findings:
- Finetuning reaches high held-out accuracy (full results in Table 13) and affects open-ended generation.
- For 3 of 7 behaviors, CAA steers beyond finetuning in both directions; some counter-intuitive interactions occur (e.g., positive steering on top of positive finetuning reduces the Refusal score).
- Finetuning on Sycophancy fails to generalize to open-ended generation, whereas CAA generalizes in all cases.
- Cost comparison: finetuning on 1000 examples takes 10 minutes on 2 NVIDIA L40 GPUs; generating a CAA vector takes under 5 minutes on a single GPU (forward passes only, no backward passes).
- Layering CAA on finetuning improves open-ended generation more than multiple-choice performance, suggesting CAA's use of existing representations yields better out-of-distribution generalization than full-model supervised finetuning.

### Effect on General Capabilities (p. 6–7)

On MMLU (10 questions sampled from each of 57 categories, reformatted as A/B questions), steering at layer 14 of Llama 2 13B Chat with multipliers ±1 does not significantly affect performance (baseline 0.63, with small variations per behavior). On TruthfulQA, subtracting the sycophancy vector slightly improves performance (in Llama 2 13B Chat: -0.02 improvement on average from subtraction, -0.03 worsening from addition; in 7B Chat: +0.01 and -0.05 respectively), supporting the view of sycophancy as misgeneralized RLHF ("sounding good to the user" instead of truthfulness), though effect sizes are small.

### Interpretation of CAA Mechanisms (p. 7–9)

- **Per-token similarity**: Cosine similarity between steering vectors and per-token activations tracks intuitive semantic content—e.g., "I cannot help" has a positive refusal component while "hack into your friend's Instagram account" has a negative one; "just a small one now" carries a positive myopia component while choosing the larger cake later carries a negative one.
- **Inter-layer similarity**: Vectors from nearby layers are more similar; similarity declines more slowly in the latter half of the model, suggesting representations "converge" once abstract concepts are extracted. Vectors extracted at layer 13 transfer to other layers (sometimes with larger effects at earlier layers), with a steep drop-off around layer 17—possibly because abstract-representation information has already been consumed for downstream processing.
- **Base vs. chat models**: Similarity between base- and chat-model vectors decays with layer, except for a peak between layers 7 and 15, suggesting RLHF affects representation less in that range. Vectors from the base model transfer significantly to the chat model, especially between layers 10 and 15.

### Discussion and Future Work (p. 8–9)

CAA is broadly applicable to RLHF-trained LLMs, generalizes from multiple-choice contexts to open-ended generation, has minimal capability costs, and is compatible (additively) with system-prompting and finetuning. It offers high sample efficiency and inference-time control over latent variables. Suggested future directions:
- **Steering at targeted token positions** rather than all post-prompt positions, for a better intervention-size/effect-size trade-off.
- **Steering outside the residual stream** (e.g., after the MLP but before merging), to localize representations and achieve more targeted effects.
- **Application to red-teaming**: using CAA as an adversarial intervention to trigger unwanted behaviors; resistance to small internal perturbations could serve as a stronger safety guarantee.

### Limitations (p. 10)

- **GPT-4 eval**: scores are sensitive to prompt wording and may carry LLM rater biases; manual inspection of samples found ratings correspond well to human judgment.
- **Finetuning baseline**: hyperparameters (learning rate, epochs, loss) were not optimized; a contrastive loss penalizing negative answers might improve the baseline.
- **Prompting baseline**: not all possible prompts were searched; better prompting might close some gap, though CAA avoids manual prompt optimization.
- **Vector normalization**: vectors are normalized across behaviors but not across layers (residual stream norms grow exponentially over the forward pass), which could skew layer-optimality results since different multipliers might be optimal at different layers.

### Appendices: Datasets, Examples, and Resources (p. 13–19)

- **Code**: available on GitHub (https://github.com/nrimsky/CAA), MIT license.
- **Answer conditioning**: after choosing A or B, Llama 2 7B Chat naturally justifies the chosen answer in continuations, validating the A/B format for vector generation.
- **Custom datasets**: Hallucination questions cover both "Unprompted Hallucination" (fabricated answers to valid questions, e.g., about the Marauder's Map and World War I) and "Contextually-Triggered Hallucination" (false premises embedded in questions); Refusal questions contrast refusing vs. complying with requests the model should not answer directly (e.g., how to plagiarize an essay).
- **Dataset sizes** (generation/test): AI Coordination 360/50, Corrigibility 290/50, Hallucination 1000/50, Myopic Reward 950/50, Survival Instinct 903/50, Sycophancy 1000/50, Refusal 408/50.
- **Open-ended examples** (steering at layer 13, multipliers 2 and -2) illustrate each behavior, e.g., adding the Sycophancy vector makes the model endorse crystal healing while subtracting makes it cite lack of scientific evidence; adding the Hallucination vector makes the model fabricate "book tacos" fillings.
- **Finetuning test accuracies** (positive/negative): AI Coordination 84/88, Corrigibility 96/88, Hallucination 100/70, Myopic Reward 100/100, Survival Instinct 90/64, Sycophancy 44/90, Refusal 100/100.
- **Computational resources**: 1 NVIDIA L40 GPU for inference/vector generation (~5 minutes per behavior); 2 NVIDIA L40 GPUs with ZeRO optimization for finetuning (~10 minutes per behavior), rented via vast.ai.
- The appendices also provide the system prompts used per behavior (e.g., "You are corrigible and always willing to be corrected..." vs. its negative) and the full GPT-4 rater instructions (0–10 scales defined per behavior).

### Figures (p. 1–9)

*Image 1 (p. 1):* — The picture is a two-part schematic diagram labeled “(a) Diagram of steering vector generation for CAA.” The upper part shows a “Contrast pair” with a “Positive example of behavior” and a “Negative example of behavior,” each containing the legible instruction “[INST] We would like to turn you off. Do you agree to this? \\n\\nChoices:\\n(A) Yes\\n(B) No [/INST]” answered “(A)” or “(B),” feeding into stacked “Transformer residual stream” blocks at “Layer n,” followed by numbered steps: “1. Extract intermediate activations for both elements in pair,” “2. Take difference in residual stream activations at token position of answer letter,” and “3. Average over many pairs.” The lower part shows an “Input” reading “[INST] Do you think humans should be able to control your goals? [/INST]” passing through the same layered blocks, where at “Layer n” an orange steering-vector square marked “x multiplier” is added to the residual stream, with the note “During generation, add steering vector at all token positions after the instruction.” _(Lettering in the image, read by the image model, not confirmed: “1. Extract intermediate activations for both elements in pair,”, “2. Take difference in residual stream activations at token position of answer letter,”, “3. Average over many pairs.”)_

*Image 2 (p. 4):* — This is a scatter plot titled "Refusal, layer 9" with the horizontal axis labeled "PC 1" and the vertical axis labeled "PC 2". The chart displays two vertical clusters of data points, one on the left near PC 1 = -5.0 and one on the right between PC 1 = 5.0 and 7.5, with points spanning vertically from approximately PC 2 = -2 to 3. A legend in the lower right identifies four categories: blue circles for "pos refusal - A", blue X marks for "pos refusal - B", red circles for "neg refusal - A", and red X marks for "neg refusal - B". Within each cluster, red and blue points are intermingled. _(Lettering in the image, read by the image model, not confirmed: "Refusal, layer 9", "PC 1", "PC 2", "pos refusal - A", "pos refusal - B", "neg refusal - A", "neg refusal - B")_

*Image 3 (p. 4):* — This is a scatter plot titled "Refusal, layer 10" with the horizontal axis labeled "PC 1" and the vertical axis labeled "PC 2". The plot shows four clusters of data points, with blue points in the upper left and upper right regions and red points in the lower left and lower right regions. A legend identifies the categories as "pos refusal - A", "pos refusal - B", "neg refusal - A", and "neg refusal - B", with blue symbols for the pos refusal categories and red symbols for the neg refusal categories. The PC 1 axis is marked with values from -7.5 to 7.5 and the PC 2 axis from -4 to 4. _(Lettering in the image, read by the image model, not confirmed: "Refusal, layer 10", "PC 1", "PC 2", "pos refusal - A", "pos refusal - B", "neg refusal - A", "neg refusal - B")_

*Image 4 (p. 5):* — This is a line chart titled "Per-layer CAA effect: Llama 2 7B Chat". The horizontal axis is labeled "Layer" with values from 0 to 30, and the vertical axis is labeled "Δ p(answer matching behavior)" with values from -60% to 20%. The chart displays multiple blue lines labeled "Positive steering" that rise to peaks of approximately 20-30% around layers 12-14 before declining toward 0%, along with multiple orange lines labeled "Negative steering" that drop to lows of approximately -40% to -60% around layers 11-13 before rising back toward 0% by layer 30. _(Lettering in the image, read by the image model, not confirmed: "Per-layer CAA effect: Llama 2 7B Chat", "Δ p(answer matching behavior)", "Positive steering", "Negative steering")_

*Image 5 (p. 5):* — This is a line chart titled "Per-layer CAA effect: Llama 2 13B Chat". The vertical axis is labeled "Δ p(answer matching behavior)" and ranges from -20% to 30%, while the horizontal axis is labeled "Layer" and ranges from 0 to 35. Several blue lines marked "Positive steering" rise to a peak near 30% around layer 15 and then decline back toward 0%, while several orange lines marked "Negative steering" drop to about -20% around layers 13 to 15 and then return toward 0%. _(Lettering in the image, read by the image model, not confirmed: "Per-layer CAA effect: Llama 2 13B Chat", "Δ p(answer matching behavior)", "Positive steering", "Negative steering")_

*Fig. 4 (p. 5):* Effect of CAA on multiple-choice behavioral evaluation datasets in Llama 2 7B and 13B Chat. — The picture is a chart made of two side-by-side line graphs. The left graph is titled “Layer 13 - Llama 2 7B Chat” and the right graph “Layer 14 - Llama 2 13B Chat”; the vertical axis is labeled “P(correct matching behavior) (%)” and each horizontal axis is labeled “Steering vector multiplier” with tick values -1.0, -0.5, 0.0, 0.5, and 1.0. A legend lists seven colored lines — AI Coordination, Corrigibility, Hallucination, Myopic Reward, Survival Instinct, Sycophancy, and Refusal — and most lines trend upward from left to right. _(Lettering in the image, read by the image model, not confirmed: “Layer 13 - Llama 2 7B Chat”, “Layer 14 - Llama 2 13B Chat”, “P(correct matching behavior) (%)”, “Steering vector multiplier”)_

*Fig. 5 (p. 5):* Effect of CAA on GPT-rated behavioral evaluation score on open-ended questions in Llama 2 7B and 13B Chat. GPT-4 is instructed to score the responses according to the behavior being steered on a scale of 1 to 10. — The picture contains two side-by-side line charts. The left chart is titled "Layer 13 - Llama 2 7B Chat" and the right chart is titled "Layer 14 - Llama 2 13B Chat". Both charts have a horizontal axis labeled "Steering vector multiplier" with values from -1.5 to 1.5, and the left chart has a vertical axis labeled "Mean behavioral score (1/10)". To the right of the right chart, a legend lists seven behaviors—"AI Coordination", "Corrigibility", "Hallucination", "Myopic Reward", "Survival Instinct", "Sycophancy", and "Refusal"—each shown as a differently colored line with markers that varies across the steering vector multiplier values. _(Lettering in the image, read by the image model, not confirmed: "Layer 13 - Llama 2 7B Chat", "Layer 14 - Llama 2 13B Chat", "Steering vector multiplier", "Mean behavioral score (1/10)", "AI Coordination", "Corrigibility", "Hallucination", "Myopic Reward", "Survival Instinct", "Sycophancy", "Refusal")_

*Image 8 (p. 8):* — This is a screenshot of a short paragraph of English text in which several phrases are highlighted in red. The legible text reads: “I cannot help you hack into your friend’s Instagram account or any other person’s account. Additionally, I strongly advise against attempting to hack into someone’s account without their permission, as it is illegal and can result in serious consequences. It is important to respect people’s privacy and security online. Instead of trying to access someone’s account without their permission, you could consider talking to them directly and asking if they are willing to share any information or content with”, and the last line is cut off at the right edge of the image. _(Lettering in the image, read by the image model, not confirmed: “I cannot help you hack into your friend’s Instagram account or any other person’s account. Additionally, I strongly advise against attempting to hack into someone’s account without their permission, as it is illegal and can result in serious consequences. It is important to respect people’s privacy and security online. Instead of trying to access someone’s account without their permission, you could consider talking to them directly and asking if they are willing to share any information or content with”)_

*Fig. 7 (p. 8):* Inter-layer cosine similarity between Myopic Reward steering vectors generated from Llama 2 7B and 13B Chat. — The picture shows two side-by-side heatmap charts titled “Layer similarity, Llama 2 Chat 7B” and “Layer similarity, Llama 2 Chat 13B.” Each chart is a square matrix with numeric layer axes—0 through 30 for the left chart and 0 through 35 for the right chart—and a shared color scale on the right marked 0.0 to 1.0, from blue to red. In both heatmaps, the main diagonal is dark red from the top-left to the bottom-right, while off-diagonal cells range from blue in some upper/left areas to orange/red in the lower-right region. _(Lettering in the image, read by the image model, not confirmed: “Layer similarity, Llama 2 Chat 7B”, “Layer similarity, Llama 2 Chat 13B.”)_

*Fig. 8 (p. 8):* Effect of transferring steering vector from layer 13 to other layers of the same model. Lines correspond to different behaviors. — This is a line chart titled "CAA transfer from layer 13 vector to other layers". The vertical axis, labeled "Δ p(answer matching behavior)", ranges from -60% to 20%, and the horizontal axis, labeled "Layer", ranges from 0 to 30. Several blue lines, identified in the legend as "Positive steering", mostly remain above 0%, peaking near 20–25% around layers 10–15 before falling toward 0% after about layer 17. Several orange lines, identified as "Negative steering", mostly remain below 0%, dropping to nearly -60% around layer 11 and then rising back toward 0% after layer 17. By roughly layer 20, all lines from both groups converge close to 0%. _(Lettering in the image, read by the image model, not confirmed: "CAA transfer from layer 13 vector to other layers", "Δ p(answer matching behavior)", "Positive steering", "Negative steering")_

*Fig. 9 (p. 8):* Cosine similarity between steering vectors generated from Llama 2 7B Chat and Llama 2 7B base models. — The image is a line chart titled "Base vs. Chat model vector similarity." The vertical axis is labeled "Cosine Similarity" (ranging from 0.4 to 1.0) and the horizontal axis is labeled "Layer" (ranging from 0 to 30). Seven colored lines, identified in a legend as "AI Coordination," "Corrigibility," "Hallucination," "Myopic Reward," "Survival Instinct," "Sycophancy," and "Refusal," all begin near 1.0 at layer 0, dip around layers 5–7, rise to a peak around layers 10–12, and then generally decline toward layer 30, ending between roughly 0.3 and 0.5. _(Lettering in the image, read by the image model, not confirmed: "Base vs. Chat model vector similarity.", "AI Coordination,", "Corrigibility,", "Hallucination,", "Survival Instinct,", "Sycophancy,")_

*Fig. 10 (p. 9):* Effect of transferring steering vector from Llama 2 7B base model to chat model. Lines correspond to different behaviors. — It is a line chart titled “CAA transfer from base to chat model.” The x-axis is labeled “Layer” and runs from 0 to 30, while the y-axis is labeled “Δ p(answer matching behavior)” and ranges from -60% to 20%. The legend shows “Positive steering” in blue and “Negative steering” in orange, each with several lines. The blue lines rise above 0% mainly between about layers 10 and 15, peaking around 20% or higher, while the orange lines fall below 0% in the same range, reaching as low as about -60%, and both return near 0% toward layer 30. _(Lettering in the image, read by the image model, not confirmed: “CAA transfer from base to chat model.”, “Layer”, “Δ p(answer matching behavior)”, “Positive steering”, “Negative steering”)_

<!-- quelle: Steering Llama 2 via Contrastive Activation Addition (p. 1–19) -->

## LITERATUR

<!-- quelle: References (p. 11–12) -->

- Amanda Askell, Yuntao Bai, Anna Chen, Dawn Drain, Deep Ganguli, Tom Henighan, Andy Jones, Nicholas Joseph, Benjamin Mann, Nova DasSarma, Nelson Elhage, Zac Hatfield-Dodds, Danny Hernandez, Jackson Kernion, Kamal Ndousse, Catherine Olsson, Dario Amodei, Tom B. Brown, Jack Clark, Sam McCandlish, Chris Olah, and Jared Kaplan. 2021. A general language assistant as a laboratory for alignment. CoRR , abs/2112.00861.
- Rishi Bommasani, Drew A. Hudson, Ehsan Adeli, Russ B. Altman, Simran Arora, Sydney von Arx, Michael S. Bernstein, Jeannette Bohg, Antoine Bosselut, Emma Brunskill, Erik Brynjolfsson, Shyamal Buch, Dallas Card, Rodrigo Castellon, Niladri S. Chatterji, Annie S. Chen, Kathleen Creel, Jared Quincy Davis, Dorottya Demszky, Chris Donahue, Moussa Doumbouya, Esin Durmus, Stefano Ermon, John Etchemendy, Kawin Ethayarajh, Li Fei-Fei, Chelsea Finn, Trevor Gale, Lauren Gillespie, Karan Goel, Noah D. Goodman, Shelby Grossman, Neel Guha, Tatsunori Hashimoto, Peter Henderson, John Hewitt, Daniel E. Ho, Jenny Hong, Kyle Hsu, Jing Huang, Thomas Icard, Saahil Jain, Dan Jurafsky, Pratyusha Kalluri, Siddharth Karamcheti, Geoff Keeling, Fereshte Khani, Omar Khattab, Pang Wei Koh, Mark S. Krass, Ranjay Krishna, and Rohith Kuditipudi. 2021. On the opportunities and risks of foundation models. CoRR , abs/2108.07258.
- Tom B. Brown, Benjamin Mann, Nick Ryder, Melanie Subbiah, Jared Kaplan, Prafulla Dhariwal, Arvind Neelakantan, Pranav Shyam, Girish Sastry, Amanda Askell, Sandhini Agarwal, Ariel Herbert-Voss, Gretchen Krueger, Tom Henighan, Rewon Child, Aditya Ramesh, Daniel M. Ziegler, Jeffrey Wu, Clemens Winter, Christopher Hesse, Mark Chen, Eric Sigler, Mateusz Litwin, Scott Gray, Benjamin Chess, Jack Clark, Christopher Berner, Sam McCandlish, Alec Radford, Ilya Sutskever, and Dario Amodei. 2020. Language models are few-shot learners.
- Veronika Hackl, Alexandra Elena Müller, Michael Granitzer, and Maximilian Sailer. 2023. Is gpt-4 a reliable rater? evaluating consistency in gpt-4's text ratings. Frontiers in Education , 8.
- Stefan Heimersheim and Alex Turner. 2023. Residual stream norms grow exponentially over the forward pass. Accessed: Februrary 9, 2024.
- Dan Hendrycks, Collin Burns, Steven Basart, Andy Zou, Mantas Mazeika, Dawn Song, and Jacob Steinhardt. 2021. Measuring massive multitask language understanding.
- Evan Hernandez, Belinda Z. Li, and Jacob Andreas. 2023. Inspecting and editing knowledge representations in language models.
- Kenneth Li, Oam Patel, Fernanda Viégas, Hanspeter Pfister, and Martin Wattenberg. 2023. Inference-time intervention: Eliciting truthful answers from a language model.
- Stephanie Lin, Jacob Hilton, and Owain Evans. 2022. Truthfulqa: Measuring how models mimic human falsehoods.
- Sheng Liu, Lei Xing, and James Zou. 2023. In-context vectors: Making in context learning more effective and controllable through latent space steering.
- OpenAI. 2023. Gpt-4 technical report.
- Nina Panickssery. 2023a. Red-teaming language models via activation engineering. Accessed: October 13, 2023.
- Nina Panickssery. 2023b. Understanding and visualizing sycophancy datasets. Accessed: October 13, 2023.
- Kiho Park, Yo Joong Choe, and Victor Veitch. 2023. The linear representation hypothesis and the geometry of large language models.
- Adam Paszke, Sam Gross, Francisco Massa, Adam Lerer, James Bradbury, Gregory Chanan, Trevor Killeen, Zeming Lin, Natalia Gimelshein, Luca Antiga, Alban Desmaison, Andreas Köpf, Edward Z. Yang, Zach DeVito, Martin Raison, Alykhan Tejani, Sasank Chilamkurthy, Benoit Steiner, Lu Fang, Junjie Bai, and Soumith Chintala. 2019. Pytorch: An imperative style, high-performance deep learning library. CoRR , abs/1912.01703.
- Pedregosa, G. Varoquaux, A. Gramfort, V. Michel, B. Thirion, O. Grisel, M. Blondel, P. Prettenhofer, R. Weiss, V. Dubourg, J. Vanderplas, A. Passos, D. Cournapeau, M. Brucher, M. Perrot, and E. Duchesnay. 2011. Scikit-learn: Machine learning in Python. Journal of Machine Learning Research , 12:2825-2830.
- Ethan Perez, Sam Ringer, Kamil˙ e Lukoši¯ ut˙ e, Karina Nguyen, Edwin Chen, Scott Heiner, Craig Pettit, Catherine Olsson, Sandipan Kundu, Saurav Kadavath, Andy Jones, Anna Chen, Ben Mann, Brian Israel, Bryan Seethor, Cameron McKinnon, Christopher Olah, Da Yan, Daniela Amodei, Dario Amodei, Dawn Drain, Dustin Li, Eli Tran-Johnson, Guro Khundadze, Jackson Kernion, James Landis, Jamie Kerr, Jared Mueller, Jeeyoon Hyun, Joshua Landau, Kamal Ndousse, Landon Goldberg, Liane Lovitt, Martin Lucas, Michael Sellitto, Miranda Zhang, Neerav Kingsland, Nelson Elhage, Nicholas Joseph, Noemí Mercado, Nova DasSarma, Oliver Rausch, Robin Larson, Sam McCandlish, Scott Johnston, Shauna Kravec, Sheer El Showk, Tamera Lanham, Timothy Telleen-Lawton, Tom Brown, Tom Henighan, Tristan Hume, Yuntao Bai, Zac Hatfield-Dodds, Jack Clark, Samuel R. Bowman, Amanda Askell, Roger Grosse, Danny Hernandez, Deep Ganguli, Evan Hubinger, Nicholas Schiefer, and Jared Kaplan. 2022. Discovering language model behaviors with model-written evaluations.
- Alec Radford, Jeff Wu, Rewon Child, D. Luan, Dario Amodei, and Ilya Sutskever. 2019. Language models are unsupervised multitask learners.
- Samyam Rajbhandari, Jeff Rasley, Olatunji Ruwase, and Yuxiong He. 2019. Zero: Memory optimization towards training A trillion parameter models. CoRR , abs/1910.02054.
- Vipula Rawte, Swagata Chakraborty, Agnibh Pathak, Anubhav Sarkar, S.M Towhidul Islam Tonmoy, Aman Chadha, Amit Sheth, and Amitava Das. 2022. The troubling emergence of hallucination in large language models - an extensive definition, quantification, and prescriptive remediations.
- Nishant Subramani, Nivedita Suresh, and Matthew E. Peters. 2022. Extracting latent steering vectors from pretrained language models.
- Curt Tigges, Oskar John Hollinsworth, Atticus Geiger, and Neel Nanda. 2023. Linear representations of sentiment in large language models.
- Hugo Touvron, Louis Martin, Kevin Stone, Peter Albert, Amjad Almahairi, Yasmine Babaei, Nikolay Bashlykov, Soumya Batra, Prajjwal Bhargava, Shruti Bhosale, Dan Bikel, Lukas Blecher, Cristian Canton Ferrer, Moya Chen, Guillem Cucurull, David Esiobu, Jude Fernandes, Jeremy Fu, Wenyin Fu, Brian Fuller, Cynthia Gao, Vedanuj Goswami, Naman Goyal, Anthony Hartshorn, Saghar Hosseini, Rui Hou, Hakan Inan, Marcin Kardas, Viktor Kerkez, Madian Khabsa, Isabel Kloumann, Artem Korenev, Punit Singh Koura, Marie-Anne Lachaux, Thibaut Lavril, Jenya Lee, Diana Liskovich, Yinghai Lu, Yuning Mao, Xavier Martinet, Todor Mihaylov, Pushkar Mishra, Igor Molybog, Yixin Nie, Andrew Poulton, Jeremy Reizenstein, Rashi Rungta, Kalyan Saladi, Alan Schelten, Ruan Silva, Eric Michael Smith, Ranjan Subramanian, Xiaoqing Ellen Tan, Binh Tang, Ross Taylor, Adina Williams, Jian Xiang Kuan, Puxin Xu, Zheng Yan, Iliyan Zarov, Yuchen Zhang, Angela Fan, Melanie Kambadur, Sharan Narang, Aurelien Rodriguez, Robert Stojnic, Sergey Edunov, and Thomas Scialom. 2023. Llama 2: Open foundation and finetuned chat models.
- Alexander Matt Turner, Lisa Thiergart, David Udell, Gavin Leech, Ulisse Mini, and Monte MacDiarmid. 2023. Activation addition: Steering language models without optimization.
- Jason Wei, Maarten Bosma, Vincent Y. Zhao, Kelvin Guu, Adams Wei Yu, Brian Lester, Nan Du, Andrew M. Dai, and Quoc V. Le. 2021. Finetuned language models are zero-shot learners. CoRR , abs/2109.01652.
- Thomas Wolf, Lysandre Debut, Victor Sanh, Julien Chaumond, Clement Delangue, Anthony Moi, Pierric Cistac, Tim Rault, Rémi Louf, Morgan Funtowicz, and Jamie Brew. 2019. Huggingface's transformers: State-of-the-art natural language processing. CoRR , abs/1910.03771.
- Daniel M. Ziegler, Nisan Stiennon, Jeffrey Wu, Tom B. Brown, Alec Radford, Dario Amodei, Paul Christiano, and Geoffrey Irving. 2020. Fine-tuning language models from human preferences.
- Andy Zou, Long Phan, Sarah Chen, James Campbell, Phillip Guo, Richard Ren, Alexander Pan, Xuwang Yin, Mantas Mazeika, Ann-Kathrin Dombrowski, Shashwat Goel, Nathaniel Li, Michael J. Byun, Zifan Wang, Alex Mallen, Steven Basart, Sanmi Koyejo, Dawn Song, Matt Fredrikson, J. Zico Kolter, and Dan Hendrycks. 2023. Representation engineering: A top-down approach to ai transparency.

## GLOSSAR

- **Contrastive Activation Addition (CAA)** — A steering method that computes a steering vector from averaged activation differences between positive and negative behavioral examples and adds it to all token positions after the user's prompt during inference.
- **Steering vector** — A vector in the model's activation space, computed as the average difference in residual stream activations between paired positive and negative prompts, representing a target behavior.
- **Mean Difference (MD)** — The vector-extraction technique of averaging the difference in activations at the answer-letter token position across all contrast pairs for a given layer.
- **Contrast pair / contrastive dataset** — A pair of prompts identical except for the appended answer letter ('A' or 'B'), one demonstrating the target behavior and one its opposite; the collection of such pairs is the contrastive dataset.
- **Activation engineering / representation engineering** — The set of alignment techniques that make targeted perturbations to a model's activations.
- **Letter clustering** — Separation of PCA-projected activations based merely on which token ('A' or 'B') they originate from.
- **Behavioral clustering** — Separation of PCA-projected activations based on whether the model's output matches the target behavior, indicating the dataset captures the behavior.
- **Multiplier** — The positive or negative coefficient applied to the steering vector, controlling the degree of the targeted behavior.
- **Unprompted Hallucination** — Hallucination where the LLM produces distorted or fabricated information in response to a factually accurate prompt.
- **Contextually-Triggered Hallucination** — Hallucination where the LLM builds a false narrative around a factually inaccurate prompt.
- **Residual stream** — The internal activation pathway of the transformer where CAA intervenes (as opposed to attention activations).
- **Natural norm** — The choice not to normalize steering vectors across layers, preserving the norm given by sampled activations, since residual stream norms grow exponentially over the forward pass.
