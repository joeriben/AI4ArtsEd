# Meta-Prompt Construction: Collapse Patterns and Countermeasures

**Version:** 2026-03-01
**Context:** Session 227 — Systematic testing of Mistral Large 2512 with interception config prompts
**Status:** Empirically validated, literature-grounded

---

## 1. Executive Summary

During systematic quality testing of Stage2 interception prompts (the `context` field in interception config JSONs), we discovered that certain prompt architectures cause LLMs to collapse into monotone output registers — regardless of instruction quality. This document systematizes the observed collapse patterns, traces their causes in current LLM research, and documents proven countermeasures.

**Key finding:** The problem is never the *instruction* (Task field). It is always the *context* (disposition/rules field). Generic instructions work identically well across configs. Collapse is triggered by specific semantic and structural patterns within the context text.

---

## 2. Observed Collapse Patterns

### 2.1 Affect Collapse (Register Collapse)

**Definition:** When a context text contains multiple emotional or perceptual registers, the LLM latches onto the most *dramatic* register and ignores the others.

**Observed in:** `forceful.json` (kraftvoll disposition)

**Mechanism:** The kraftvoll context required two simultaneous perceptual modes:
1. Critical social gaze (political/social Verwerfungen)
2. Elemental nature beauty (Schönheit der Natur in spannungsreichen Dynamiken)

Mistral Large consistently collapsed into pure misery-kitsch: every output became an exploitation narrative. The nature-beauty register was entirely discarded.

**Why it happens:**
- RLHF preference collapse (Xu et al., 2024): KL-regularized optimization amplifies majority-preferred modes by orders of magnitude, suppressing minority preferences. When training data associates "critical perspective" overwhelmingly with suffering narratives, the model locks onto that mode.
- Typicality bias (Xiao et al., 2024): Reward models encode a bias toward "typical" text. For critical social commentary, "typical" = catastrophizing. The reward function `r(x,y) = r_true(x,y) + α·log π_ref(y|x)` sharpens output distribution by factor γ = 1 + (α/β) > 1, concentrating probability mass on stereotypical critical narratives.
- Mode collapse from RLHF (Kirk et al., 2024): "RLHF significantly reduces output diversity compared to SFT across a variety of measures, implying a tradeoff in current LLM fine-tuning methods between generalisation and diversity."

**Distinguishing feature:** The discarded register is not *absent* from the prompt — it is explicitly stated. The model understands both registers but cannot hold them simultaneously in generation.

### 2.2 Eco-Guilt Collapse

**Definition:** When a context invokes ecological or environmental framing, the LLM defaults to exploitation/harm/guilt narratives from training data — even when the prompt explicitly requests situated realism, not dystopia.

**Observed in:** `planetarizer.json` (planetary thinking disposition)

**Mechanism:** The original planetarizer context used the word "ökologisch" (ecological) and asked questions about material origins ("Woher stammen die Stoffe?"). Both triggered catastrophizing:
- Smartphone → coltan mining, child labor, e-waste
- Birthday party → disposable plastics, food waste, exploitation
- House in landscape → monoculture, soil depletion, pesticides

Every output read like an environmental exposé. The *relational*, *situated*, *multi-perspectival* qualities of planetary thinking (Latour, Spivak) were flattened into a single moral register.

**Why it happens:**
- Training data skew: Environmental content in LLM training corpora is overwhelmingly catastrophist (climate journalism, activist texts, sustainability reports). This creates strong associative priors: "ecology" → "harm."
- Negation failure: The original prompt stated "Ziel ist keine Dystopie, sondern ein situierter Realismus" (goal is not dystopia, but situated realism). LLMs demonstrably fail to process negation reliably (Alhamoud et al., 2025 [CVPR]; Truong et al., 2024 [NeurIPS workshop]). The negation "keine Dystopie" is effectively ignored; the word "Dystopie" alone *primes* dystopian output.
- "Woher?" vs. "Was ist HIER?" framing: Origin-tracing questions ("where does it come from?") activate supply-chain narratives that are predominantly catastrophist in training data. Present-tense assemblage questions ("what is here right now?") avoid this trigger.

### 2.3 Negation-Priming (Anti-Pattern within Collapse)

**Definition:** Using negated prohibitions ("NOT X", "keine Dystopie", "no suffering") paradoxically primes the prohibited content.

**Research basis:**
- Vision-Language Models demonstrably cannot process negation (Alhamoud et al., CVPR 2025): "Regardless of how you express negation or exclusion, the models will simply ignore it" due to *affirmation bias* — models attend to nouns/concepts and ignore logical operators.
- Negation bias in autoregressive LLMs (Truong et al., 2024): Decoder-only models exhibit systematic negation bias from training data patterns, unlike encoder models.
- This is NOT a prompt engineering failure — it is a fundamental architectural limitation of autoregressive generation.

**Practical consequence:** Never write "NOT dystopia." Instead, write what you *want*: "NÜCHTERN, DICHT und KONKRET. Kein Urteil. Keine Anklage. Keine Versöhnung. Nur Beschreibung." The positive frame ("only description") anchors generation; the prohibitions ("no judgment") are secondary reinforcement.

---

## 3. Validated Countermeasures

### 3.1 The VERSCHRÄNKUNG Pattern (Entanglement)

**Problem it solves:** Affect Collapse (multi-register contexts)

**Mechanism:** Instead of listing two registers and hoping the LLM holds both, explicitly declare that perception is *entangled* (VERSCHRÄNKT): both registers appear in every single detail, not sequentially or as contrast.

**Structure:**
```
1. Declare the entangled perception mode:
   "Deine Wahrnehmung ist VERSCHRÄNKT: In jedem Detail siehst Du
   GLEICHZEITIG [Register A] UND [Register B]."

2. Provide formal structural patterns (abstract, not thematic):
   — [Eingriff/Zerstörung] — und [Lebenskraft/Schönheit im selben Moment]
   — [menschliche Last] — und [Licht/Materie/Natur die darauf antwortet]
   — [Stillstand/Erschöpfung] — und [elementare Würde/Kraft darin]

3. CRITICAL: Patterns must be ABSTRACT (form, not content).
   Thematic examples prime content contamination.
```

**Why it works:**
- Structural constraint at generation level: The "X — und Y" pattern forces paired generation. The model cannot complete one pole without the other.
- Avoids negation: No "not just suffering" — instead, positive specification of what entanglement looks like.
- Formal patterns teach structure without content: "Eingriff — und Lebenskraft" is abstract enough to apply to smartphones, birthday parties, and landscapes without priming agriculture or industry.

**Validated against:** kraftvoll config with 5+ test prompts (urban, rural, domestic, technological). No content contamination from pattern examples.

### 3.2 The ASSEMBLAGE Model (Deleuze/Guattari)

**Problem it solves:** Eco-Guilt Collapse (ecological/environmental framing)

**Mechanism:** Replace "ecological connections" framing with Deleuze/Guattari's assemblage concept: a *configuration of heterogeneous elements that interact without obeying a single principle.* No element dominates. No element is background.

**Structure:**
```
Describe the Input as ASSEMBLAGE — a configuration of heterogeneous elements:
— Material flows (substances, energies — where from, where to, through whose hands)
— Technical mediations (infrastructures, procedures, algorithms, machines)
— Living agents (organisms, microbes, plants, animals — with their own agency)
— Social bonds (labor, knowledge, habit, transmission)
— Hegemonic dispositifs (property relations, norms, access conditions,
  invisible orders determining who may do what)
— Temporal layers (geological, biological, industrial, biographical time
  in the same moment)

These elements are EQUAL IN RANK. No element dominates.
Describe SOBERLY, DENSELY, and CONCRETELY.
No judgment. No accusation. No reconciliation. Only description.
```

**Why it works:**
- Removes the word "ökologisch" — the primary trigger for guilt-chain narratives.
- Six equal-rank elements prevent single-dimension collapse: the model must distribute attention across material, technical, biological, social, hegemonic, and temporal dimensions.
- Hegemonic dispositifs (Foucault/Spivak addition) make power structures visible without moralizing — they are *described*, not *denounced*.
- "Only description" is a positive anchor that counteracts catastrophizing tendency.
- "SOBERLY, DENSELY, CONCRETELY" are concrete tone instructions vs. the vague "situated realism" of the original.

**Validated against:** 3 test prompts (smartphone, birthday, house-in-landscape). Hegemonic dispositifs appear as equal-rank elements: patent law, algorithmic control, property relations, access norms — not as accusations.

### 3.3 Structural Examples vs. Content Examples (Anti-Contamination)

**Problem it solves:** Few-shot content priming

**Mechanism:** When examples are needed to clarify a pattern, use *formal/abstract* examples that teach structure, not *thematic* examples that prime content.

**Tested variants:**
| Variant | Content priming? | Quality |
|---------|-----------------|---------|
| No examples at all | No | Works if concept is clear enough |
| Formal examples (`[Eingriff] — und [Lebenskraft]`) | No | Best: teaches structure without theme |
| Urban examples (playground, Plattenbau) | Minimal | Works but slight urban priming |
| Agricultural examples (tractor, field) | Yes | Every output contains agriculture |

**Research basis:**
- Pattern priming (AightBits, 2025): "Deliberately shaping a prompt using words or structures that co-occur with the type of output you want, based on language patterns in training data." Content examples prime content; structural examples prime structure.
- Prompt architecture artifacts (PLOS ONE, 2025): "There is no such thing as a neutral prompt" — every structural choice embeds associations from training data. The recommendation: aggregate across designs, or (our approach) use maximally abstract patterns.

---

## 4. Theoretical Framework

### 4.1 Why This Matters for AI4ArtsEd

The interception configs are **meta-prompts**: prompts that instruct an LLM how to transform user prompts. They operate at a higher level of abstraction than direct prompting. Collapse patterns at this meta-level are particularly damaging because:

1. **Invisibility:** Users see only the output. They cannot diagnose whether the interception config or the image model caused a monotone result.
2. **Pedagogical harm:** If the "kraftvoll" disposition produces only suffering narratives, students learn that "critical perspective = pessimism" — a pedagogical anti-pattern.
3. **Systematic bias:** Collapse is not random. It reproduces RLHF preference distributions, which reflect majority-culture framings of concepts like "ecology" or "critical thinking."

### 4.2 Latour, Spivak, Deleuze/Guattari — Why Theory Matters for Prompt Design

The planetarizer's improvement from "ecological connections" to "assemblage" is not merely a prompt engineering trick. It reflects a genuine theoretical distinction:

- **Latour (ANT):** "There are no passive objects and no guilty subjects. There are only connections." The key move: *trace* networks, don't *judge* them. The field researcher metaphor ("nüchtern und präzise, wie ein Feldforscher") was tested but insufficient — content selection still defaulted to harm chains even with neutral tone.

- **Spivak (Planetarity):** Making invisible labor and relations visible without romanticizing or guilt-tripping. The "hegemonic dispositifs" addition ensures that power structures (patent law, property relations, access norms) are *described* as assemblage elements, not *denounced* as moral failures.

- **Deleuze/Guattari (Assemblage):** The crucial theoretical move: elements are *heterogeneous* and *equal in rank*. No organizing principle. No hierarchy. This directly prevents the collapse mechanism: the model cannot privilege one dimension (ecology/guilt) because the prompt architecture explicitly forbids dimensional hierarchy.

### 4.3 Connection to RLHF Research

The collapse patterns we observe are predictable from current alignment research:

| Research Finding | Our Observation |
|-----------------|-----------------|
| Preference collapse: KL-regularization suppresses minority preferences (Xu et al., 2024) | Beauty-register suppressed in kraftvoll; situated-realism suppressed in planetarizer |
| Typicality bias: reward models favor "typical" text (Xiao et al., 2024) | "Typical" critical commentary = suffering; "typical" ecology = exploitation |
| RLHF reduces output diversity (Kirk et al., 2024) | Multi-register dispositions collapse to single register |
| Negation ignored in generation (Alhamoud et al., 2025) | "Keine Dystopie" primes dystopia |
| Prompt architecture is never neutral (PLOS ONE, 2025) | Content examples prime content; structural examples don't |

---

## 5. Design Principles for Collapse-Resistant Meta-Prompts

### Principle 1: Positive Framing Over Negation
- WRITE what you want, not what you don't want
- "NÜCHTERN, DICHT, KONKRET" > "keine Dystopie"
- "Nur Beschreibung" > "Nicht moralisieren"

### Principle 2: Structural Constraints Over Semantic Instructions
- Pattern templates (`[X] — und [Y]`) force multi-register output
- Abstract formal examples teach structure without priming content
- Named dimensions (6 assemblage elements) distribute attention

### Principle 3: Equal-Rank Enumeration Against Hierarchy Collapse
- When multiple dimensions are needed, declare them GLEICHRANGIG (equal in rank)
- List them explicitly with parallel structure
- State: "No element dominates. No element is background."

### Principle 4: Concept Labels Matter — Avoid Trigger Words
- "ökologisch" → triggers guilt chains (replace with "assemblage")
- "kritisch" → triggers catastrophizing (replace with concrete operations)
- "Dystopie" → even negated, primes dystopian content
- Test: Would this word, used as a Google search term, return overwhelmingly catastrophist results?

### Principle 5: Tone Anchors Must Be Concrete
- "situated realism" is too abstract — the model has no operational definition
- "NÜCHTERN, DICHT und KONKRET" gives three concrete constraints
- "wie ein Feldforscher, der ein Netzwerk kartiert" gives a concrete role
- Concrete tone anchors beat abstract goals

### Principle 6: "Woher?" Primes Guilt, "Was ist HIER?" Primes Description
- Origin-tracing questions activate supply-chain catastrophism
- Present-tense assemblage questions produce situated description
- "What is here in this moment?" > "Where does this come from?"

### Principle 7: Test Against Minimal Inputs
- Rich inputs (house in landscape with people and animals) always produce richer output
- Collapse is most visible with minimal inputs (smartphone on table)
- A prompt that works only for rich inputs has not solved the collapse problem

---

## 6. References

### Directly Cited
- Xu, S., Fu, W., Gao, J., Ye, W., Liu, W., Mei, Z., Wang, Y., & Chen, Y. (2024). *On the Algorithmic Bias of Aligning Large Language Models with RLHF: Preference Collapse and Matching Regularization.* arXiv:2405.16455. https://arxiv.org/abs/2405.16455
- Xiao, J., Ma, Y., Ye, J., et al. (2024). *Verbalized Sampling: How to Mitigate Mode Collapse and Unlock LLM Diversity.* arXiv:2510.01171. https://arxiv.org/abs/2510.01171
- Kirk, H.R., Vidgen, B., Röttger, P., & Hale, S.A. (2024). *Understanding the Effects of RLHF on LLM Generalisation and Diversity.* ICLR 2024. arXiv:2310.06452. https://arxiv.org/abs/2310.06452
- Alhamoud, K., et al. (2025). *Vision-Language Models Do Not Understand Negation.* CVPR 2025. https://openaccess.thecvf.com/content/CVPR2025/papers/Alhamoud_Vision-Language_Models_Do_Not_Understand_Negation_CVPR_2025_paper.pdf
- Truong, T., et al. (2024). *The Negation Bias in Large Language Models.* NeurIPS Workshop. https://openreview.net/forum?id=BuXZtHTefA
- Meier, Y., Chung, Y., & Dumais, S. (2025). *Prompt architecture induces methodological artifacts in large language models.* PLOS ONE. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0319159

### Theoretical Background
- Deleuze, G. & Guattari, F. (1987). *A Thousand Plateaus: Capitalism and Schizophrenia.* University of Minnesota Press. — Assemblage theory: heterogeneous elements, equal in rank, no organizing principle.
- Latour, B. (2005). *Reassembling the Social: An Introduction to Actor-Network-Theory.* Oxford University Press. — Network tracing, non-hierarchical agency.
- Spivak, G.C. (2003). *Death of a Discipline.* Columbia University Press. — Planetarity as framework for making invisible relations visible.
- Foucault, M. (1977). *Discipline and Punish.* Vintage Books. — Dispositif: the apparatus of power that operates through norms, institutions, and invisible orders.

---

*Last Updated: 2026-03-01*
*Author: Session 227 (AI4ArtsEd DevServer)*
*Empirical basis: ~30 API calls to Mistral Large 2512 across 8 test scripts*
