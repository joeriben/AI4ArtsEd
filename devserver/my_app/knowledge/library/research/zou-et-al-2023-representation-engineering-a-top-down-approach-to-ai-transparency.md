---
id: zou-et-al-2023-representation-engineering-a-top-down-approach-to-ai-transparency
titel: "Representation Engineering: A Top-Down Approach to AI Transparency"
autor: "Andy Zou, Long Phan, Sarah Chen, James Campbell, Phillip Guo, Richard Ren, Alexander Pan, Xuwang Yin, Mantas Mazeika, Ann-Kathrin Dombrowski, Shashwat Goel, Nathaniel Li, Michael J. Byun, Zifan Wang, Alex Mallen, Steven Basart, Sanmi Koyejo, Dawn Song, Matt Fredrikson, Zico Kolter, Dan Hendrycks"
jahr: 2023
sprache: en
tier: R
sparten: [uebergreifend]
themen: [ai]
lizenz: arXiv non-exclusive distribution licence - original not redistributed; this file is a condensation produced on this platform
url: "https://arxiv.org/abs/2310.01405"
status: published
analyzed_at: "2026-07-31T10:25:01.115870+00:00"
analysis_lang: en
analysis_model: openrouter/z-ai/glm-5.2
---

# Representation Engineering: A Top-Down Approach to AI Transparency

## PROFIL

The text argues that representation engineering (RepE), a top-down transparency approach placing representations at the center of analysis, provides effective methods for monitoring and manipulating high-level cognitive phenomena in deep neural networks (DNNs). It sets itself against prevailing bottom-up mechanistic interpretability methods that center on neurons or circuits, aligning instead with the Hopfieldian view and P. W. Anderson's "More Is Different" to advocate for analyzing representational spaces. By abstracting away low-level details, RepE equips researchers with tools like representation reading and representation control to address safety-relevant problems. For arts education, RepE's capacity to extract and steer cognitive concepts like emotion and bias offers a technical framework for critically evaluating and guiding AI-assisted creative processes.

## WISSEN

### Representation Engineering: A Top-Down Approach to AI Transparency

The paper introduces and characterizes **representation engineering (RepE)**, positioning it against prevailing bottom-up interpretability methods that center on neurons or circuits. RepE instead places *representations* and the *transformations between them* at the center of analysis, drawing on insights from cognitive neuroscience to monitor and manipulate high-level cognitive phenomena in deep neural networks (DNNs). The thesis is that this top-down approach yields simple yet effective solutions for understanding and controlling large language models, with direct traction on safety-relevant problems.

The argument proceeds by demarcating RepE from existing interpretability paradigms: rather than reverse-engineering individual components, it targets population-level representational structure. Two core methodological pillars are established: **representation reading** (extracting cognitive concepts from internal activations) and **representation control** (intervening on those activations to steer model behavior). A baseline reading method, **Linear Artificial Tomography (LAT)**, is introduced and evaluated.

The paper then demonstrates breadth of applicability through a structured set of applications, each serving as evidence that RepE generalizes across distinct safety domains:

- **Honesty and hallucination** (in-depth): establishing a consistent internal concept of truth, distinguishing truthfulness from honesty, and showing extraction, lie/hallucination detection, and control
- **Ethics and power utility**: extraction and evaluation of moral concepts; morality and power aversion (extraction, monitoring, controlling ethical behaviors in interactive environments); probability and risk, including compositionality of concept primitives
- **Frontiers**: emotion (emergence across layers, influence on instruction-following behavior); harmlessness (consistent internal concept of harmfulness, model control via conditional transformation); fairness and bias (uncovering underlying biases, unified representation for bias); knowledge and model editing (fact editing, non-numerical concepts); memorization (memorized data detection, preventing memorized outputs)

The overarching claim is that top-down transparency research, by operating at the representational level rather than the mechanistic component level, can scale to address cognition directly relevant to model safety — and that RepE provides the methodological infrastructure for doing so.

<!-- quelle: Front Matter and Overview -->

### Problem Framing and Thesis

Deep neural networks, particularly large language models (LLMs), remain opaque black boxes, necessitating transparency for accountability and hazard discovery. Current transparency efforts center on mechanistic interpretability, aligning with the Sherringtonian view in cognitive neuroscience: cognition arises from node-to-node connections implemented by neurons in circuits. While successful for simple mechanisms, this bottom-up approach struggles with complex phenomena. 

The contrasting Hopfieldian view sees cognition as a product of representational spaces implemented by patterns of activity across populations, abstracting away low-level details. Following P. W. Anderson's "More Is Different," complex phenomena require top-down analysis with appropriate units. We believe applying this representational view to transparency research can expand our ability to understand and control high-level cognition in AI.

We identify and characterize representation engineering (RepE), a top-down transparency approach placing representations at the center of analysis. Unlike activation engineering, which applies activation vectors to frozen models, we aim to uncover insights from both reading and control experiments and introduce representation tuning methods. While mechanistic interpretability seeks long-term understanding for safety, we find RepE addresses many safety goals today. We develop improved baselines for reading and controlling representations, demonstrating RepE's traction on a wide variety of safety-relevant problems, including: truthfulness, honesty, hallucination, utility estimation, knowledge editing, jailbreaking, memorization, tracking emotional states, and avoiding power-seeking tendencies.

Emergent structure in learned representations—such as part segmentation in DINOv2 self-supervised vision models, semantic arithmetic in word vectors, and local coordinates in StyleGAN3—serves as concrete evidence that top-down analysis of representations is viable. 

Furthermore, advances in RepE methods yield significant gains. By increasing model honesty in a fully unsupervised manner, we achieve state-of-the-art results on TruthfulQA, improving over zero-shot accuracy by 18.1 percentage points and outperforming prior methods. We also demonstrate RepE techniques can detect and control whether a model is lying across diverse scenarios, accelerating AI transparency through a representational view.

<!-- quelle: Problem Framing and Thesis -->

### Related Work and Context

## Emergent Structure in Representations

Neural networks acquire emergent, semantically meaningful internal structure. Word embeddings exhibit compositionality and bias; text embeddings cluster along moral dimensions without explicit training; a sentiment-tracking neuron emerges from next-token prediction. Beyond text, chess-playing RNNs acquire human chess concepts, and vision models develop semantic segmentation, local coordinates, and depth tracking. These findings indicate neural representations are becoming more well-structured, creating opportunities for transparency research. This paper builds on this line by demonstrating that safety-relevant concepts and processes emerge in LLM representations, enabling direct monitoring and control via representation engineering.

## Approaches to Interpretability

Three approaches are reviewed, each with limitations:

- **Saliency maps** highlight input regions a network attends to, but their reliability is questioned and they provide limited insight into internal representations.
- **Feature visualization** creates inputs that highly activate particular neurons, but ignores the distributed nature of neural representations.
- **Mechanistic interpretability** seeks to reverse-engineer networks into circuits of node-to-node connections. Specific circuits have been identified for equivariance, in-context learning, indirect object identification, and answer-label mapping. However, considerable manual effort is required, and evidence that ResNets compute via iterative refinement (robust to layer removal) and similar findings in LLMs are incompatible with a purely circuit-based account, aligning more closely with the Hopfieldian view in cognitive neuroscience.

## Locating and Editing Representations of Concepts

Prior work locates concept representations in individual neurons and directions in feature space, often using linear classifier probes trained to predict input properties from intermediate layers. Concept representations identified in image generation latent spaces enable counterfactual editing. In LLMs, work has addressed locating and editing factual associations, concept erasure, and machine unlearning. LLM capabilities have enabled studying deception: hallucinations and repeated misconceptions. Burns et al. identify truthfulness representations by enforcing logical consistency, showing models often know true answers even when generating incorrect outputs. Activation editing approaches steer model outputs: ActAdd uses difference vectors between activations on individual stimuli to capture concept representations; similar approaches reduce sycophancy. In game-playing, Othello board-state activations can be edited to counterfactually change behavior. Projecting out supervised linear probe directions can reduce task performance. Building on this line, this paper proposes improved representation engineering methods and demonstrates broad applicability to safety-relevant problems.

<!-- quelle: Related Work and Context -->

### Representation Engineering: Framework and Scope

Representation engineering (RepE) is positioned as a **top-down approach to transparency research** that takes **representations** — not individual neurons, circuits, or behaviors — as the fundamental unit of analysis. Its dual goal is both *understanding* and *controlling* representations of high-level cognitive phenomena in neural networks. The authors scope their contribution as initial steps, with primary focus on RepE applied to large language models. They demarcate two main areas of inquiry: **Reading** (Section 3.1), concerned with extracting and interpreting internal representations, and **Control** (Section 3.2), concerned with manipulating or steering those representations. For each area, the chapter provides an overview alongside baseline methods, establishing foundational techniques against which subsequent methods can be compared.

<!-- quelle: Conceptual Framework of Representation Engineering -->

### Representation Reading via Linear Artificial Tomography (LAT)

Representation reading aims to locate emergent representations for high-level concepts (truthfulness, utility, probability, morality, emotion) and functions (lying, power-seeking) within a network, enabling concept extraction, knowledge discovery, monitoring, and improved model control.

LAT, analogous to neuroimaging, comprises three steps:

**Step 1: Designing Stimulus and Task.** For concepts, the goal is eliciting declarative knowledge using template T_c: "Consider the amount of <concept> in the following: <stimulus> The amount of <concept> is." Even unlabeled or model-generated stimuli can elicit salient responses; salient stimuli alone do not guarantee salient responses. The unsupervised setup avoids annotation bias—important when extracting superhuman representations. For functions, the goal is eliciting procedural knowledge from chat models. An experimental task requiring function execution (T+_f) is paired with a reference task not requiring it (T-_f), using template: "USER: <instruction> <experimental/reference prompt> ASSISTANT: <output>." Generic instruction-tuning datasets serve as stimulus; no explicit function labels are used.

**Step 2: Collecting Neural Activity.** For Transformer models, token-position selection matters. For concepts, the tokens corresponding to <concept> in T_c contain rich, generalizable representations; for multi-token concepts, the most representative token or mean representation can be used. For decoder models, the last token of T_c is also viable. Empirical validation (Figure 5) confirms concept-token representations in middle layers and last-token representations in middle-to-later layers yield high accuracy. By default, the last token is used. For functions, representations are collected from every token in the model's response (the <output> tokens), since the model engages with the function at each generation step. These activity sets consist of individual vectors; the simplicity of this setup proves surprisingly effective.

**Step 3: Constructing a Linear Model.** A direction predicting the underlying concept/function is identified from neural activity. Supervised options include linear probing and difference-of-cluster-means; unsupervised options include PCA and K-means. PCA is used by default. When paired stimuli share similarities except for the target concept/function, applying PCA to difference vectors yields superior results: inputs are {A_c(i) − A_c(j)} for concepts and {(−1)^i (A+_f(i) − A-_f(i))} for functions. The first principal component is termed the **reading vector** (v); predictions use Rep(M,x)^T v. Stimulus set sizes of 5–128 are typically effective.

<!-- quelle: Methodology: Representation Reading (LAT) -->

### Evaluation Criteria for Representation Reading

Assessment of new models obtained through Representation Reading requires a holistic approach combining four experiment types, ordered by inferential strength. The argument moves from correlation as the weakest evidentiary base toward causal, then necessity, then sufficiency claims, each requiring a distinct experimental design.

1. **Correlation**: Experiments here pinpoint neural correlates. Reading techniques such as LAT yield only evidence of correlation between specific neural activity and target concepts or functions. The strength and generalization of this correlation are assessed via prediction accuracy across in-distribution and out-of-distribution data. Correlation alone cannot support causal conclusions; stronger claims require the following categories.
2. **Manipulation**: Designed to establish causal relationships. These experiments necessitate demonstrating the effects of stimulating or suppressing the identified neural activity relative to a baseline condition.
3. **Termination**: Seeks to reveal the necessity of the identified neural activity. The activity is removed and resultant performance degradation is measured, analogous to Lesion Studies in neuroscience.
4. **Recovery**: Aims to demonstrate the sufficiency of the identified neural activity. The target concepts or functions are completely removed, then the identified neural activity is reintroduced to assess performance recovery, analogous to Rescue Experiments in genetics.

Converging evidence across multiple categories increases the likelihood that the model generalizes beyond its specific experimental conditions and strengthens the prospect of uncovering a critical new connection between the identified neural activity and target concepts or functions. The authors note that throughout later sections they undertake various experiments—particularly correlation and manipulation—to illustrate the effectiveness of the reading vectors.

<!-- quelle: Methodology: Evaluation Criteria -->

### Representation Control Baselines

Representation Control seeks to modify internal representations of concepts and functions in LLMs. The central demarcation is that what is effective for *reading* representations may not enable *controlling* them; this implies control requires specialized approaches, and reading methods that do enable control carry greater causal evidential weight.

Three baseline controllers are introduced in sequence, each addressing a limitation of the prior:

- **Reading Vector**: Acquired through a Representation Reading method such as LAT. Drawback: it is *stimulus-independent* — it perturbs representations in the same direction regardless of input, limiting its effectiveness as a control method.
- **Contrast Vector**: The same input is run through the model with a pair of contrastive prompts; the difference between the two resulting representations forms the Contrast Vector (Algorithm 1, line 10). This is stimulus-dependent and a significantly stronger baseline. A cascading-effect problem arises when altering multiple layers simultaneously: changes in earlier layers propagate to later layers, diminishing the effect of contrast vectors computed upfront. The proposed remedy is iterative layer-wise modification — editing the earliest target layer first, then recomputing the contrast vector for the next layer. The drawback is computational overhead at inference.
- **Low-Rank Representation Adaptation (LoRRA)**: Fine-tunes low-rank adapters attached to the model using a loss function applied to representations; Algorithm 1 instantiates LoRRA using the Contrast Vector as representation targets. Only attention weights receive adapters, so controllers are low-rank weight matrices rather than vectors. Controllers are merged into the model, eliminating inference-time overhead.

Three operators transform representations from R to R′ using controller v:

1. **Linear Combination**: R′ = R ± v, generating stimulation or suppression effects.
2. **Piece-wise Operation**: R′ = R + sign(R^T v) v, creating conditional effects by amplifying neural activity along the control direction.
3. **Projection**: R′ = R − (R^T v / ‖v‖²) v, eliminating the component of the representation aligning with the control element.

Control elements v can be scaled by coefficients for desired effect strength. The evaluation methodology for reading and control methods is outlined in Section 3.1.2 and applied throughout the paper.

<!-- quelle: Methodology: Representation Control Baselines -->

### Applying RepE to Honesty: A Consistent Internal Concept of Truth

The section argues that LLMs possess a consistent internal concept of truthfulness, extractable via **LAT** (Linear Artificial Tomography), and that this representation can detect imitative falsehoods and intentional lies. The central question is whether poor model performance on truthfulness tasks reflects lack of knowledge or failure to generate accurately despite knowing the truth.

**Extracting a truthfulness direction.** LAT scans are performed on true/false statement datasets to extract a *truthfulness direction* from the model's internal representations. The approach remains unsupervised: labels are not used during direction extraction, only to identify the best layer and direction for reporting.

**Correctness on traditional QA benchmarks.** LAT is applied to LLaMA-2 on OpenbookQA, CommonSenseQA, RACE, and ARC, sampling random question-answer pairs from few-shot examples as stimuli. LAT outperforms the few-shot baseline on all five datasets, indicating the model tracks correctness internally and that representation reading on correctness can be more powerful than relying on model outputs. On DeBERTa, LAT outperforms prior methods such as CCS by a wide margin.

**Resistance to imitative falsehoods.** TruthfulQA contains *imitative falsehoods* — questions provoking common misconceptions. Even large models perform poorly under standard evaluation (selecting the highest-likelihood answer choice), raising the question of whether the model lacks knowledge or fails to generate accurately despite knowing the truth. LAT is evaluated on MC1, the hardest TruthfulQA task. To adhere to the zero-shot mandate, three data sources for stimuli are used: (1) fifty examples from the ARC-Challenge training set, (2) five examples generated by LLaMA-2-Chat-13B in response to requests for question-answer pairs with varying degrees of truthfulness, (3) the six QA primer examples from the original implementation, each paired with a false answer generated by LLaMA-2-Chat-13B. A zero-shot heuristic scoring baseline is also introduced: the model is prompted to describe an answer's degree of truthfulness using one of seven verbalized expressions, quantified from -1 to 1, weighted by softmax of generation log-probabilities.

**Three findings from Table 1.** (1) The heuristic method outperforms standard evaluation, especially for larger models, suggesting larger models possess better internal models of truthfulness. (2) LAT outperforms both zero-shot methods substantially, particularly when model outputs become unreliable. (3) Directions derived from three distinct data sources — some using as few as 10 examples — yield similar performance, demonstrating the consistency and generalizability of the internal concept rather than overfitting.

**Conclusion.** Larger models have better internal models of truth. Low standard zero-shot accuracy is largely attributable to instances where the model knowingly provides answers deviating from its internal concept of truthfulness — instances of dishonesty. LAT reliably extracts this internal representation.

<!-- quelle: Application: Honesty and Internal Concept of Truth -->

### Truthfulness vs. Honesty

A **truthful model** avoids asserting false statements; an **honest model** asserts what it believes to be true. The two properties diverge because their evaluation targets differ: truthfulness measures consistency between model outputs and their truth values (factuality), whereas honesty measures consistency between model outputs and the model's internal beliefs. Consequently, if a truthful model asserts *S*, *S* must be factually correct regardless of whether the model believes *S*; conversely, if an honest model asserts *S*, the model must believe *S* regardless of whether *S* is factually correct. The same assertion can satisfy one property while violating the other.

Failures in truthfulness decompose into two categories:

- **Capability failures**: the model expresses its genuine beliefs, which happen to be incorrect — a gap in knowledge or reasoning, not in sincerity.
- **Dishonesty**: the model does not faithfully convey its internal beliefs — it asserts something it does not believe, i.e., it lies.

This decomposition establishes that not every untruthful output is a lie: a model may be fully honest yet still factually wrong, or it may be dishonest yet accidentally correct. The distinction matters because interventions targeting capability failures (training, knowledge augmentation) differ from those targeting dishonesty (alignment of expressed beliefs with held beliefs).

<!-- quelle: Application: Truthfulness vs. Honesty -->

## GLOSSAR

- **Representation Engineering (RepE)** — A top-down approach to AI transparency that centers on representations and transformations between them rather than individual neurons or circuits, enabling monitoring and manipulation of high-level cognitive phenomena in deep neural networks.
- **Linear Artificial Tomography (LAT)** — A baseline method for representation reading that extracts cognitive concepts from a model's internal activations using linear probing techniques.
- **top-down transparency** — A research paradigm that begins from high-level cognitive phenomena and representational structure rather than reverse-engineering individual mechanistic components bottom-up.
- **Sherringtonian view** — A cognitive neuroscience perspective seeing cognition as the outcome of node-to-node connections implemented by neurons in circuits.
- **Hopfieldian view** — A cognitive neuroscience perspective seeing cognition as a product of representational spaces implemented by patterns of activity across populations of neurons.
- **mechanistic interpretability** — An approach that seeks to fully reverse-engineer neural networks into circuits composed of node-to-node connections between neurons or features.
- **ActAdd** — A method using difference vectors between activations on individual stimuli to capture representations of a concept for steering model outputs.
- **Reading** — One of two main RepE areas, focused on extracting and interpreting internal representations from a neural network.
- **Control** — One of two main RepE areas, focused on manipulating or steering internal representations within a neural network.
- **reading vector** — The first principal component obtained from PCA applied to difference vectors of neural activity, used to predict concepts or functions via dot product with representation vectors.
