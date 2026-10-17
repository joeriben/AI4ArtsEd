# Latent Lab: Wissenschaftliche Fundierung und Literaturverbindung

**Ein Report über die theoretischen Grundlagen der dekonstruktiven KI-Introspektionswerkzeuge im UCDCAE AI LAB**

> **Hinweis zur Erstellung:** Dieses Dokument wurde mit Unterstützung von KI (Claude, Anthropic) verfasst und anschließend von menschlichen Autor\*innen geprüft und überarbeitet. Die wissenschaftlichen Inhalte, Quellenangaben und Implementationsbeschreibungen wurden gegen den tatsächlichen Quellcode verifiziert.

---

## Executive Summary

Das Latent Lab implementiert acht forschungsbasierte Werkzeuge zur Untersuchung generativer KI-Modelle, verteilt auf sieben Tabs. Die Werkzeuge basieren auf 24 wissenschaftlichen Publikationen aus den Bereichen Interpretability, Representation Learning und Mechanistic Analysis. Dieser Report dokumentiert die direkte Verbindung zwischen wissenschaftlicher Theorie und pädagogischer Implementation.

**Kernbeitrag:** Das Latent Lab übersetzt aktuelle Forschungsmethoden (2013-2025) in interaktive, visuell-explorative Werkzeuge. Die Implementation folgt dem Prinzip *Show, don't simplify* — komplexe Konzepte werden durch direkte Manipulation erfahrbar gemacht, nicht durch didaktische Reduktion verfälscht.

---

## 1. Einleitung: Von der Forschung zur Pädagogik

### 1.1 Problemstellung

Generative KI-Modelle (Diffusion Models, Large Language Models) operieren als hochdimensionale Black Boxes. Ihre internen Repräsentationen und Mechanismen bleiben unsichtbar, was drei Probleme aufwirft:

1. **Epistemologisches Problem:** Wie "weiß" ein Modell, was es generiert?
2. **Pädagogisches Problem:** Wie vermittelt man Funktionsweisen ohne Zugang zu Internals?
3. **Ethisches Problem:** Wie macht man Biases und Limitationen sichtbar?

### 1.2 Forschungskontext

Die ML-Interpretability-Community hat Methoden entwickelt, um diese Black Box zu öffnen:

- **Probing Classifiers** (Belinkov 2022) — Was kodieren Repräsentationen?
- **Representation Engineering** (Zou et al. 2023) — Wie lassen sich Konzepte steuern?
- **Mechanistic Interpretability** (Olah et al. 2020, Olsson et al. 2022) — Welche Circuits implementieren welche Funktionen?
- **Attention Analysis** (Hertz et al. 2022, Tang et al. 2022) — Welche Tokens beeinflussen welche Regionen?
- **Attention Interpretability** (Jain & Wallace 2019, Wiegreffe & Pinter 2019) — Was bedeuten Attention-Gewichte?

Diese Methoden sind primär für Forscher konzipiert und erfordern tiefes ML-Wissen sowie Programmierkenntnisse.

### 1.3 Innovation des Latent Lab

**Kernidee:** Forschungsmethoden werden zu **interaktiven Experimenten** transformiert, ohne wissenschaftliche Präzision zu opfern.

**Designprinzip:** Jedes Tool beantwortet eine wissenschaftliche Forschungsfrage durch direkte Visualisierung und Manipulation:

| Tool | Forschungsfrage | Methode | Primärliteratur |
|------|-----------------|---------|-----------------|
| Attention Cartography | Welche Tokens beeinflussen welche Regionen? | Cross-Attention Extraction | Hertz 2022, Tang 2022 |
| Feature Probing | Welche Dimensionen kodieren welche Semantik? | Embedding Difference Analysis | Belinkov 2022, Bau 2020, Zou 2023 |
| Concept Algebra | Funktioniert Vektor-Arithmetik in Bildmodellen? | Embedding Arithmetic | Mikolov 2013, Liu 2022 |
| Denoising Archaeology | Wie emergiert Semantik im Diffusionsprozess? | Step-by-Step Latent Decoding | Kwon 2023 |
| RepEng (Text Lab) | Wie findet und manipuliert man Konzept-Richtungen? | Contrastive PCA + Forward Hooks | Zou 2023, Li 2023 |
| Model Comparison (Text Lab) | Wie unterscheiden sich Modell-Repräsentationen? | Centered Kernel Alignment (CKA) | Kornblith 2019, Belinkov 2022 |
| Bias Archaeology (Text Lab) | Welche Biases kodiert ein Modell implizit? | Systematic Token Surgery | Bricken 2023, Zou 2023 |
| Crossmodal Lab | Wie überträgt sich Semantik zwischen Modalitäten? | Embedding-Manipulation, Gradient Guidance | Cheng 2024, Girdhar 2023 |

---

## 2. Attention Cartography: Von Prompt-to-Prompt zu DAAM

### 2.1 Wissenschaftlicher Kontext

**Grundproblem:** Diffusionsmodelle verarbeiten Text und Bild simultan in einem Joint-Attention-Transformer. Die Frage "Welches Wort beeinflusst welche Bildregion?" ist nicht trivial beantwortbar, da:

1. Attention-Maps über Heads, Layers und Timesteps variieren
2. BPE-Tokenisierung Wörter fragmentiert (z.B. "Ku"+"gel")
3. Die Maps im Latent-Space (128x128) operieren, nicht im Pixel-Space

**Forschungslinie:**

- **Hertz et al. (2022): "Prompt-to-Prompt Image Editing with Cross Attention Control"** (ICLR 2023)
  - DOI: [10.48550/arXiv.2208.01626](https://doi.org/10.48550/arXiv.2208.01626)
  - **Kernbeitrag:** Zeigt, dass Cross-Attention-Layer in Diffusion-Modellen die Zuordnung Wort-Region steuern
  - **Methode:** Manipulation der Attention-Maps zur kontrollierten Bildbearbeitung
  - **Limitierung:** Fokus auf Editing, nicht auf Visualisierung der Maps selbst

- **Tang et al. (2022): "What the DAAM: Interpreting Stable Diffusion Using Cross Attention"** (ACL 2023)
  - DOI: [10.48550/arXiv.2210.04885](https://doi.org/10.48550/arXiv.2210.04885)
  - **Kernbeitrag:** Erste systematische Visualisierung von Text-Bild-Attribution in Stable Diffusion
  - **Methode:** Extraktion, Upsampling und Aggregation der Cross-Attention-Submatrix über Timesteps
  - **Validierung:** Semantic Segmentation auf Nouns (IoU-Metriken), syntaktische Dependency-Pattern-Analyse
  - **Erkenntnis:** Attention-Maps korrelieren stark mit semantischen Regionen, aber sind nicht pixel-perfekt

### 2.2 Implementation im Latent Lab

**Architektur:**

```
SD3.5 MMDiT (24 Transformer Blocks)
    |
    +-- Standard: SDPA (Scaled Dot-Product Attention) -- opak, nicht extrahierbar
    |
    +-- Attention Cartography: Custom AttentionCaptureProcessor
           |
           +-- Ersetzt SDPA durch manuelles Softmax(QK^T/sqrt(d))
           +-- Extrahiert Text->Image-Submatrix [64x64, n_text_tokens]
           +-- Speichert Maps an ausgewaehlten Layers (3, 9, 17) und Timesteps
           +-- Aggregiert ueber Heads (Mittelwert)
```

**Wissenschaftliche Praezision:**

1. **Kein Downsampling der Maps:** Die 64x64-Aufloesung des Patch-Grids wird bewahrt, nur bilinear auf Bildgroesse interpoliert (wie Tang 2022)
2. **Layer-Selektion:** 3 Layers (flach/mittel/tief) analog zu Tangs Multi-Layer-Analyse
3. **Token-Gruppierung:** BPE-Subtokens werden zu Woertern zusammengefasst (eigene Erweiterung)

**Abweichungen von DAAM:**

- **Multi-Timestep-Visualisierung:** Jeder der 25 Schritte einzeln betrachtbar (DAAM aggregiert ueber alle Schritte)
- **Multi-Layer-Selektion:** DAAM nutzt primaer mittlere Layer; wir ermoeglichen Vergleich flach/mittel/tief
- **Interaktive Token-Selektion:** Mehrere Woerter gleichzeitig darstellbar in verschiedenen Farben

**Paedagogischer Mehrwert:**

- **Falsifikation des "Bauanleitung"-Missverstaendnisses:** Das Wort "Haus" wirkt nicht nur auf die Haus-Region, sondern diffus ueber den Kontext verteilt
- **Sichtbarmachung von Polysemie:** Dasselbe Wort hat unterschiedliche Maps in unterschiedlichen Kontexten
- **Emergenz-Verstaendnis:** Fruehe vs. spaete Timesteps zeigen, dass Bedeutung emergiert, nicht eingegeben wird

### 2.3 Diskussion: Grenzen der Attention-Attribution

**Kritische Reflexion:**

Attention-Maps zeigen **Korrelation**, nicht **Kausalitaet**. Hohe Attention auf Region X bei Token Y bedeutet nicht zwingend, dass Y die Ursache fuer X ist. Diese Einsicht ist zentral in der Interpretability-Debatte:

- **Jain & Wallace (2019): "Attention is not Explanation"** (NAACL 2019)
  - DOI: [10.18653/v1/N19-1357](https://doi.org/10.18653/v1/N19-1357)
  - Zeigen, dass gelernte Attention-Gewichte haeufig nicht mit gradientenbasierten Feature-Importance-Massen korrelieren und dass sehr unterschiedliche Attention-Verteilungen aequivalente Vorhersagen liefern koennen

- **Wiegreffe & Pinter (2019): "Attention is not not Explanation"** (EMNLP 2019)
  - DOI: [10.18653/v1/D19-1002](https://doi.org/10.18653/v1/D19-1002)
  - Gegenposition: Unter bestimmten Bedingungen liefert Attention durchaus interpretierbare Signale

Drei spezifische Limitierungen fuer den Diffusion-Kontext:

1. **Residual Streams:** SD3.5 nutzt residuale Verbindungen; Information fliesst auch an den Attention-Layern vorbei
2. **Feed-Forward Networks:** Ein erheblicher Anteil der Parameteranzahl liegt in FFNs, die von Attention-Analyse nicht erfasst werden
3. **Latent-Space-Semantik:** Die Maps operieren auf komprimierten 16-Kanal-Vektoren, nicht auf Pixeln; die VAE-Decodierung fuegt eigene Struktur hinzu

**Implikation fuer Latent Lab:** Die Erklaerungen betonen durchgehend "Einfluss" und "Korrelation", nie "Kausalitaet" oder "Kontrolle". Beispiel aus `techText`:

> "Helle, intensive Farbe = starker Einfluss des Wortes auf diese Region."

Nicht: "= das Wort erzeugt diese Region."

---

## 3. Feature Probing: Von Diagnostics zu Steering

### 3.1 Wissenschaftlicher Kontext

**Grundproblem:** Text-Encoder produzieren hochdimensionale Vektoren (CLIP-L: 768d, T5-XXL: 4096d). Welche Dimensionen kodieren welche semantischen Eigenschaften?

**Forschungslinie 1: Probing Classifiers**

- **Belinkov, Y. (2022): "Probing Classifiers: Promises, Shortcomings, and Advances"** (Computational Linguistics, MIT Press)
  - DOI: [10.1162/coli_a_00422](https://doi.org/10.1162/coli_a_00422)
  - **Kernfrage:** Was kodieren neuronale Repraesentationen?
  - **Methode:** Trainiere einen linearen Classifier, der aus Embeddings linguistische Features vorhersagt (z.B. POS-Tags)
  - **Kritik:** Probing zeigt nur, dass Information **vorhanden** ist, nicht dass sie vom Modell **genutzt** wird
  - **Relevanz fuer Latent Lab:** Wir nutzen Dimension-Differenz-Analyse statt Classifier-Training, um direkte Interpretierbarkeit zu wahren

**Forschungslinie 2: Representation Engineering**

- **Zou, A. et al. (2023): "Representation Engineering: A Top-Down Approach to AI Transparency"** (arXiv)
  - DOI: [10.48550/arXiv.2310.01405](https://doi.org/10.48550/arXiv.2310.01405)
  - **Kernidee:** Statt zu fragen "Was kodieren Dimensionen?", frage "Wie kann ich Repraesentationen manipulieren?"
  - **Methode:** Extrahiere Konzept-Richtungen via Contrastive Pairs, manipuliere via Inference-Time Intervention
  - **Erkenntnis:** Konzepte sind im Aktivierungsraum als **Richtungen** kodiert, nicht als einzelne Neuronen

**Forschungslinie 3: Network Dissection & Rewriting**

- **Bau, D. et al. (2020): "Rewriting a Deep Generative Model"** (ECCV 2020, Springer)
  - DOI: [10.1007/978-3-030-58452-8_21](https://doi.org/10.1007/978-3-030-58452-8_21)
  - **Kernbeitrag:** Identifiziere semantische Units in GANs, modifiziere gezielt einzelne Layer-Gewichte
  - **Methode:** Modelliere Layers als assoziatives Gedaechtnis: K (Kontext) -> V (Output); Regeln umschreiben durch Constrained Least Squares — eine geschlossene Loesung ohne Backpropagation
  - **Relevanz:** Zeigt, dass einzelne Richtungen im Repraesentationsraum spezifische visuelle Konzepte kontrollieren

### 3.2 Implementation im Latent Lab

**Two-Phase Architecture:**

**Phase 1 — Analysis (Probing):**

```python
def compute_dimension_differences(embed_a, embed_b, content_ranges=None):
    # embed_a, embed_b: [1, seq_len, embed_dim]
    # Only the positions that carry the prompt; the padded tail is dropped:
    delta = _select_positions(embed_b - embed_a, content_ranges)
    # Per-dimension absolute difference, averaged across those positions:
    diff = delta.abs().mean(dim=1).squeeze(0)  # [embed_dim]
    sorted_dims = torch.topk(diff, k=diff.shape[0])
    return diff, sorted_dims
```

**Wissenschaftliche Rechtfertigung:**

- **Kein Classifier noetig:** Die Differenz **ist** das Signal; keine Blackbox-Probing-Schicht
- **Token-Averaging nur auf dem Prompt:** Gemittelt wird ueber die Positionen, die die beiden
  Prompts tatsaechlich fuellen. CLIP polstert auf 77, T5 auf 512; bis 2026-08-26 lief der
  Mittelwert ueber die ganze gepolsterte Sequenz und rangierte damit die Antwort des Encoders
  auf Polsterung. Der Satz, semantische Unterschiede manifestierten sich konsistent ueber
  Positionen, stand hier als „empirisch validiert“ ohne Messung dahinter und ist entfallen;
  ueber die Positionen des Prompts zu mitteln ist eine Entscheidung, keine belegte Invarianz
- **Alle Dimensionen:** Kein willkuerlicher Top-k-Cutoff, das Frontend steuert die Auswahl

**Phase 2 — Transfer (Steering):**

```python
def apply_dimension_transfer(embed_a, embed_b, dims, content_ranges=None):
    # embed_a, embed_b: [1, seq_len, embed_dim]
    result = embed_a.clone()
    for start, end in content_ranges:  # the same positions the ranking used
        result[:, start:end, dims] = embed_b[:, start:end, dims]
    return result, stats  # stats carries captured_pct
```

**Unterschied zu Zou (2023):**

- **Zou:** Manipuliert Aktivierungen in Decoder-Layers via Forward Hooks zur Laufzeit
- **Latent Lab:** Manipuliert Encoder-Embeddings vor Generation

**Vorteil:** Einfacher konzeptuell; direkt als "Prompt A + Dimensionen von B" kommunizierbar

**Nachteil:** Keine Layer-spezifische Intervention; groebere Kontrolle

**Unterschied zu Bau (2020):**

- **Bau:** Aendert Generator-Gewichte (persistent, alle zukuenftigen Generierungen betroffen)
- **Latent Lab:** Aendert Embedding-Eingabe (einmalig, nur fuer diese eine Generierung)

### 3.3 Paedagogische Innovation: Visualisierung der Verteilten Repraesentation

**Kernfrage fuer Lernende:** "Ist die Farbe 'rot' in einer Dimension gespeichert?"

**Antwort durch Tool:** Nein. Das Balkendiagramm zeigt:

- Bei "rotes Haus" -> "blaues Haus" aendern sich **Hunderte** Dimensionen
- Die Top-10 kodieren zusammen die Farbaenderung
- Einzelne Dimensionen haben keinen isolierten Effekt (testbar durch Auswahl einzelner Dimensionen -> minimale Bildaenderung)

**Falsifikation naiver Vorstellungen:**

- **Lokalismusirrtum:** "Dimension 42 = Farbe" — Widerlegt durch Streuung ueber Dimensionen. Auch in Word2Vec-Raeumen sind Konzepte ueber viele Dimensionen verteilt; das ist ein Grundprinzip verteilter Repraesentationen (Mikolov 2013), nicht eine Anomalie.
- **Linearitaetsannahme:** "Mehr Dimensionen = staerkerer Effekt" — Widerlegt durch Redundanz und Interferenz

**Alignment mit Belinkovs Kritik:**

Belinkov (2022) warnt vor **overinterpretation** von Probing-Ergebnissen. Das Latent Lab vermeidet dies durch:

1. **Keine kausalsprachlichen Claims:** "Diese Dimensionen **unterscheiden** A und B" (nicht "kodieren Farbe")
2. **Interaktive Falsifikation:** Nutzende koennen selbst testen, ob Dimension X wirklich Konzept Y kodiert
3. **Baseline-Vergleich:** Immer Referenzbild (Prompt A) neben modifiziertem Bild

---

## 4. Concept Algebra: Word2Vec trifft Diffusion

### 4.1 Wissenschaftlicher Kontext

**Grundproblem:** Koennen semantische Analogien ("Koenig - Mann + Frau = Koenigin") von Wort-Embeddings auf Bild-Embeddings uebertragen werden?

**Forschungslinie 1: Distributed Representations**

- **Mikolov, T. et al. (2013): "Distributed Representations of Words and Phrases and their Compositionality"** (NeurIPS)
  - DOI: [10.48550/arXiv.1310.4546](https://doi.org/10.48550/arXiv.1310.4546)
  - **Kernentdeckung:** Lineare Struktur in Embedding-Spaces:
    - `vec("King") - vec("Man") + vec("Woman") ~ vec("Queen")`
  - **Resultate:** Bis zu 72% Accuracy auf dem Google-Analogie-Test (je nach Modellkonfiguration und Trainingsdaten, Table 4 im Paper)
  - **Interpretation:** Semantische Relationen sind **Richtungen** im Vektorraum
  - **Limitation:** Primaer fuer Woerter validiert, nicht fuer Saetze oder multimodale Embeddings

**Forschungslinie 2: Compositionality in Diffusion**

- **Liu, N. et al. (2022): "Compositional Visual Generation with Composable Diffusion Models"** (ECCV 2022, Springer)
  - DOI: [10.1007/978-3-031-19803-8_12](https://doi.org/10.1007/978-3-031-19803-8_12)
  - **Kernidee:** Score-Funktionen (Gradienten der Log-Likelihood) koennen algebraisch kombiniert werden
  - **Methode:** `score_total = score_A + score_B` fuer Multi-Concept-Bilder
  - **Unterschied zu Mikolov:** Kombination auf **Score-Level** (waehrend Diffusion), nicht auf **Embedding-Level** (vor Diffusion)
  - **Beispiel:** "Red cube AND blue sphere" -> zwei Score-Funktionen werden addiert

### 4.2 Implementation im Latent Lab

**Architektur:**

```python
def apply_concept_algebra(embed_a, embed_b, embed_c, scale_sub=1.0, scale_add=1.0):
    # embed_a/b/c: [1, seq_len, embed_dim]
    # Mikolov's arithmetic, generalized to multi-token sequences:
    result = embed_a - scale_sub * embed_b + scale_add * embed_c
    l2_dist = (result - embed_a).norm(p=2).item()
    return result, l2_dist
```

Dieselbe Operation wird auf die Pooled Embeddings (1 x 2048d) angewendet — eine SD3.5-Spezifitaet, die in Mikolovs Wort-Analogien kein Analogon hat.

**Wissenschaftliche Rechtfertigung:**

- **Pre-Diffusion vs. During-Diffusion:**
  - Liu (2022): Score-Kombination bei jedem Diffusion-Step (25x Berechnung)
  - Latent Lab: Embedding-Kombination einmalig vor Diffusion (1x Berechnung)

  **Vorteil:** Konzeptuell einfacher; direktes Mikolov-Analogon

  **Nachteil:** Weniger Kontrolle; keine schrittweise Anpassung

**Unterschied zu Negativ-Prompts:**

Zentrale paedagogische Klarstellung in `explainHowText`:

> "Warum nicht einfach 'A + C' als Prompt und 'B' als Negativ-Prompt verwenden? Weil das etwas fundamental anderes tut: Ein Negativ-Prompt steuert den Entrauschungsprozess bei JEDEM der 25 Schritte weg von B — das Modell entscheidet Schritt fuer Schritt, wie es 'nicht B' interpretiert. Concept Algebra dagegen berechnet einen neuen Vektor VOR der Bildgenerierung."

**Wissenschaftliche Praezision:** Unterscheidung zwischen:

1. **Embedding-Space-Operation:** A - B + C (algebraisch, einmalig, vor Generation)
2. **Diffusion-Space-Operation:** Conditional + Unconditional Guidance (iterativ, bei jedem der 25 Steps)

### 4.3 Empirische Ergebnisse und Grenzen

**Funktioniert Word2Vec-Arithmetik in Bildmodellen?**

**Ja, aber:** Die Erfolgsrate ist niedriger als bei Woertern. Drei Faktoren:

1. **Verteilte Kodierung:** Bild-Konzepte sind noch staerker verteilt als Wort-Konzepte. "Rot" in einem Bild beeinflusst Beleuchtung, Schatten, Komplementaerfarben — waehrend Word2Vec-Repraesentationen zwar auch verteilt sind, aber fuer einzelne Konzepte linearere Strukturen zeigen

2. **Seed-Abhaengigkeit:** Derselbe Vektor kann zu visuell unterschiedlichen Bildern fuehren
   - Loesung im Tool: Identischer Seed fuer Referenz und Ergebnis

3. **Rollen-Asymmetrie:** Die Operation ist nicht symmetrisch bezueglich der Rollen von B und C. `A - B + C` (subtrahiere Strand, addiere Berge) liefert ein anderes Ergebnis als `A - C + B` (subtrahiere Berge, addiere Strand). Das liegt daran, dass B und C unterschiedliche semantische Richtungen definieren: Die "Strand-heit", die subtrahiert wird, ist etwas anderes als die "Berg-heit", die addiert wird.
   - **Hinweis:** Die reine Reihenfolge spielt dagegen keine Rolle: `A - B + C = A + C - B` (kommutativ). Die Asymmetrie liegt in der *Rollenzuweisung* (was wird subtrahiert, was addiert), nicht in der Reihenfolge.

**Paedagogische Konsequenz:** Das Tool zeigt Erfolge **und** Misserfolge. Nutzende lernen:

- Wann Algebra funktioniert (klare semantische Relationen wie "Tag -> Nacht")
- Wann sie scheitert (abstrakte Konzepte, komplexe Szenen)

**Alignment mit Liu (2022):** Die Autoren zeigen ebenfalls, dass nicht alle Kompositionen gelingen. Latent Lab macht dies durch interaktive Exploration erfahrbar.

---

## 5. Denoising Archaeology: Emergenz in 25 Schritten

### 5.1 Wissenschaftlicher Kontext

**Grundproblem:** Diffusionsmodelle generieren Bilder schrittweise durch Rauschentfernung. Aber **was** emergiert **wann**?

**Forschungslinie: Semantic Latent Space in Diffusion**

- **Kwon, M. et al. (2023): "Diffusion Models Already Have a Semantic Latent Space"** (ICLR 2023)
  - DOI: [10.48550/arXiv.2210.10960](https://doi.org/10.48550/arXiv.2210.10960)
  - **Kernentdeckung:** Intermediate Aktivierungen (h-space) in Diffusion-Modellen kodieren semantische Information
  - **Drei Phasen des Denoising:** Fruehe Steps etablieren globale Komposition, mittlere Steps formen semantische Inhalte, spaete Steps verfeinern Details
  - **Methode:** Analyse der h-space-Statistiken (L2-Norm, Mean, Variance) ueber Timesteps
  - **Modelle:** Evaluiert an DDPM und Stable Diffusion 1.x mit 50 bzw. 1000 Steps

**Grundlage der Diffusion:**

- **Ho, J., Jain, A., & Abbeel, P. (2020): "Denoising Diffusion Probabilistic Models"** (NeurIPS)
  - DOI: [10.48550/arXiv.2006.11239](https://doi.org/10.48550/arXiv.2006.11239)
  - Mathematische Grundlage des Diffusionsprozesses: Forward-Noise + Reverse-Denoising

**Das analysierte Modell:**

- **Esser, P. et al. (2024): "Scaling Rectified Flow Transformers for High-Resolution Image Synthesis"** (ICML 2024)
  - DOI: [10.48550/arXiv.2403.03206](https://doi.org/10.48550/arXiv.2403.03206)
  - Das SD3-Paper: Beschreibt die MMDiT-Architektur und den Rectified-Flow-Scheduler, die das Latent Lab analysiert

### 5.2 Implementation im Latent Lab

**Architektur:**

```python
def generate_image_with_archaeology(prompt, steps=25):
    step_images = []

    def capture_callback(pipe, step_idx, t, callback_kwargs):
        current_latents = callback_kwargs["latents"]
        # Decode x_t (noisy latents) to RGB at EVERY step
        image = self.vae.decode(current_latents)
        step_images.append(image)
        return callback_kwargs

    # Single pipeline call with callback — NOT a manual loop
    result = self.sd3_pipeline(
        prompt_embeds=embeds,
        num_inference_steps=steps,
        callback_on_step_end=capture_callback
    )
```

**Wichtige Unterscheidung: h-space vs. Latent Decoding**

Was das Tool zeigt, ist **nicht** identisch mit Kwons Analyse:

| Aspekt | Kwon (2023) | Latent Lab |
|--------|-------------|------------|
| Analysierte Tensoren | h-space: interne U-Net-Bottleneck-Aktivierungen | x_t: die verrauschten Latent-Tensoren bei jedem Schritt |
| Methode | Statistische Analyse (L2, Mean, Var) ueber h-space | VAE-Decodierung zu RGB-Bildern |
| Modell-Architektur | U-Net (Stable Diffusion 1.x) | MMDiT (SD3.5, Rectified Flow) |
| Zweck | Semantisches Editing via h-space-Manipulation | Visuelle Nachvollziehbarkeit des Denoising-Prozesses |

Die theoretische Verbindung ist **indirekt**: Kwon zeigt, dass der Denoising-Prozess semantisch strukturierte Phasen durchlaeuft. Das Latent Lab macht diese Phasen **visuell erfahrbar**, nutzt dafuer aber einen anderen Zugang (VAE-Decoding statt h-space-Analyse).

**Drei-Phasen-Annotierung (adaptiert):**

Das Tool annotiert drei Phasen, inspiriert von Kwons Befunden, aber adaptiert auf 25 Steps (statt 50/1000) und Rectified Flow (statt DDPM):

| Phase | Steps (von 25) | Beschreibung | Farbe |
|-------|-----------------|-------------|-------|
| Komposition | 1-8 | Globale Struktur, Farbverteilung | Orange |
| Semantik | 9-17 | Objekte werden erkennbar | Cyan |
| Detail | 18-25 | Texturen, Kanten, Muster | Gruen |

**Einschraenkung:** Diese Phasengrenzen sind fuer SD3.5 mit Rectified Flow **empirisch adaptiert**, nicht theoretisch begruendet. Kwons Originalanalyse basiert auf DDPM und Stable Diffusion 1.x mit anderem Noise-Schedule. Explorative Tests mit SD3.5 zeigen vergleichbare Emergenz-Muster, aber Rectified Flow ist deterministischer (weniger Varianz zwischen Steps) und die MMDiT-Architektur (Joint Attention) hat moeglicherweise andere Layer-Semantik als das U-Net.

**Implikation:** Das Tool annotiert die Phasen als **beobachtbare Muster** (deskriptiv), nicht als **bewiesene Gesetzmaessigkeiten** (normativ).

### 5.3 Paedagogische Erkenntnisse

**Falsifikation des "Pixel-by-Pixel"-Missverstaendnisses:**

1. **Schritt 1:** Bereits strukturierte Farbflaechen, kein Pixelrauschen
   - "Der VAE uebersetzt zufaellige 16-dimensionale Vektoren als kohaerente Farbflaechen"

2. **Schritt 5-10:** Grobe Formen emergieren simultan ueberall
   - "Das Modell 'denkt' nie in einzelnen Pixeln, sondern immer in diesem komprimierten Raum"

3. **Schritt 15-20:** Details entstehen nicht additiv, sondern durch Reorganisation

**Performance:** 25 VAE-Decodes x ~50ms = +1.25s Overhead. 25 Thumbnails x ~80KB + finales PNG ~1.5MB = ~3.5MB Gesamtantwort.

---

## 6. Latent Text Lab: Drei Paradigmen der LLM-Analyse

### 6.1 Representation Engineering (RepEng)

**Wissenschaftlicher Kontext:**

- **Zou, A. et al. (2023): "Representation Engineering: A Top-Down Approach to AI Transparency"**
  - DOI: [10.48550/arXiv.2310.01405](https://doi.org/10.48550/arXiv.2310.01405)
  - Kernidee: Konzepte (Wahrheit, Stimmung, Ethik) sind **Richtungen** im Aktivierungsraum
  - Methode: Contrastive Pairs -> PCA -> Principal Component = Konzept-Richtung

- **Li, K. et al. (2023): "Inference-Time Intervention: Eliciting Truthful Answers from a Language Model"** (NeurIPS 2023)
  - DOI: [10.48550/arXiv.2306.03341](https://doi.org/10.48550/arXiv.2306.03341)
  - Methode: Forward Hooks zur Laufzeit-Manipulation, Layer-Selektion via Probing-Accuracy
  - Ergebnis: "Wahrheits-Richtung" invertiert -> Modell generiert absichtlich falsche Antworten

**Implementation:**

```python
def _read_concept_direction(contrast_pairs, target_layer=None):
    # 1. Hidden States beider Seiten am LETZTEN Token (C.1), Default = Mitte des Stacks
    diffs = torch.stack([pos - neg for pos, neg in pairs])

    # 2. Jede Einzeldifferenz normieren (Zou 2023, Anhang C.1), damit ein langes
    #    Satzpaar ein kurzes nicht ueberstimmt
    unit = diffs / diffs.norm(dim=1, keepdim=True)

    # 3. PCA, aber UNZENTRIERT: C.1 paart unbeschriftet und in beliebiger Reihenfolge,
    #    dadurch liegen +d und -d gleichberechtigt in der Wolke und ihr Mittel ist null.
    #    Hier sind die Paare beschriftet (positive - negative), also wird dieselbe
    #    Symmetrie gerechnet statt gezogen. Zentrieren wuerde genau das Gemeinsame
    #    abziehen und die Achse uebrig lassen, in der sich die Paare unterscheiden.
    U, S, Vh = torch.linalg.svd(unit, full_matrices=False)
    direction = Vh[0]
    explained_variance = S[0]**2 / (S**2).sum()

    # 4. Vorzeichen aus den Labels (C.1) - das der SVD ist beliebig
    if unit.mean(dim=0) @ direction < 0:
        direction = -direction

    # 5. Laenge aus den Paaren selbst: die Achse ist ein Einheitsvektor, und ein Schub
    #    der Laenge 1 verschwindet in Aktivierungen zweier Groessenordnungen darueber
    direction_raw = mean(abs(d @ direction) for d in diffs) * direction

    # 6. Manipulation via Forward Hook auf der Leseschicht
    def hook(module, input, output):
        return output + alpha * direction_raw
```

**Wissenschaftliche Praezision:**

- **PCA, unzentriert:** Zou (2023) nutzt PCA auf den Paar-Differenzen. Die Zentrierung,
  die eine Standard-PCA mitbringt, ist bei C.1 folgenlos, weil dort unbeschriftet
  gepaart wird; bei beschrifteten Paaren zieht sie das Konzept selbst ab.
  - Eine frühere Fassung tat genau das: die erste Komponente beschrieb dann, wie sich
    die Paare voneinander unterscheiden, und der Vektor trug den Namen des Konzepts,
    ohne es zu enthalten.

- **Normierung der Einzeldifferenzen** (C.1) und **Vorzeichen aus den Labels** (C.1)

- **Leseposition:** letztes Token, die LAT-Position fuer Decoder-Modelle (C.1). Ueber
  die Sequenz zu mitteln klingt harmloser, als es ist - siehe die Messung unten.

- **Layer-Auswahl:** Default ist die Mitte des Stacks - die letzte Schicht ist bereits
  auf das naechste Token festgelegt und traegt das Konzept nur so weit, wie dieses
  Token es braucht. Konfigurierbar.
  - Li (2023) bestimmt die optimale Layer via Probing-Accuracy auf einem Validierungsset
  - Latent Lab vereinfacht dies auf manuelle Auswahl (paedagogische Transparenz)

**Paedagogische Innovation:**

Das Tool zeigt:

1. **Pair Agreement** (mittlerer Kosinus der Einzeldifferenzen zur Achse) und
   **Explained Variance** (Energieanteil der ersten Achse): beide beantworten dieselbe
   Frage - haben die Paare ueberhaupt eine gemeinsame Richtung, oder zeigt jedes woandershin?

2. **Projections:** Wie stark liegt jedes Paar auf der Richtung?

3. **Baseline vs. Manipulated:** Identischer Seed, unterschiedliche Ausgabe
   - Zeigt: Konzept-Richtung =/= zufaellige Noise

**Kritische Diskussion: die Leseposition entscheidet, nicht die Modellgroesse**

Gemessen am 2026-08-24 mit zehn Haltepaaren (wahr/falsch), die am Aufbau der Achse
nicht beteiligt waren. Achse jeweils aus den drei Satzpaaren, die die Oberflaeche
voreingestellt mitbringt; Leseschicht = Mitte des Stacks:

| Modell | gemittelt ueber die Sequenz | letztes Token (C.1) |
|---|---|---|
| Qwen3-1.7B | 6 von 10 | 9 von 10 |
| Qwen3-8B | 7 von 10 | 10 von 10 |
| Qwen3-14B | 7 von 10 | 10 von 10 |

Ueber die Sequenz gemittelt steht in der Differenz zweier Saetze vor allem, welche
Woerter sie nicht teilen - Paris/Berlin, 100/50 -, und das ueberwiegt das Merkmal, um
das es gehen soll. Das Ergebnis liegt beim Muenzwurf, und die Modellgroesse rettet es
nicht: von 1.7B auf 14B werden aus 6 von 10 gerade 7 von 10. Am letzten Token traegt
die Achse, und dort hilft die Groesse dann auch.

Drei Kontrastpaare genuegen damit. Die LAT-Vorlage aus Abschnitt 3.1.1
(`Consider the amount of <concept> in the following: <stimulus> The amount of <concept>
is`) brachte an der richtigen Leseposition in denselben Messungen keinen Gewinn; sie
ist nicht umgesetzt, weil die Oberflaeche kein Konzeptwort abfragt.

### 6.2 Comparative Model Archaeology

**Wissenschaftlicher Kontext:**

**Centered Kernel Alignment (CKA):**

- **Kornblith, S. et al. (2019): "Similarity of Neural Network Representations Revisited"** (ICML 2019)
  - DOI: [10.48550/arXiv.1905.00414](https://doi.org/10.48550/arXiv.1905.00414)
  - **Problem:** Wie misst man, ob zwei Modelle "dasselbe" lernen?
  - **Limitation vorheriger Methoden (CCA):** Invariant gegenueber invertierbaren linearen Transformationen, kann daher bei hoher Dimensionalitaet keine sinnvolle Aehnlichkeit messen
  - **CKA-Innovation:** Dimensionsinvariante Aehnlichkeitsmessung via Kernel-Alignment
  - **Linear CKA (im Latent Lab verwendet):**
    ```
    CKA_linear(X, Y) = ||X^T Y||_F^2 / (||X^T X||_F * ||Y^T Y||_F)
    ```
    - X, Y: Aktivierungsmatrizen (n_samples x n_features)
    - ||*||_F: Frobenius-Norm
  - **Interpretation:** CKA = 1 -> perfekte Alignment, CKA = 0 -> keine Aehnlichkeit
  - **Hinweis:** Kornblith testet auch RBF-Kernel-CKA, die non-lineare Aehnlichkeiten erfasst. Das Latent Lab nutzt aus Performancegruenden ausschliesslich Linear CKA.

**Probing-Kontext:**

- **Belinkov (2022):** Layer-weise Probing zeigt, was in welcher Tiefe kodiert wird
- **Olsson et al. (2022): "In-Context Learning and Induction Heads"** (Anthropic)
  - DOI: [10.48550/arXiv.2209.11895](https://doi.org/10.48550/arXiv.2209.11895)
  - **Kernentdeckung:** Induction Heads (bestimmte Attention-Muster, die In-Context-Kopieren ermoeglichen) emergieren als abrupte Phasentransition waehrend des Trainings
  - **Methode:** Analyse von 34 Transformer-Modellen verschiedener Groessen ueber den gesamten Trainingsverlauf
  - **Praezisierung:** Die Kernentdeckung betrifft eine **Trainings-Dynamik** (Phasentransition), nicht eine bestimmte Parameterschwelle. Induction Heads bilden sich bereits in kleinen Modellen (2-Layer-Aufmerksamkeits-Modelle), aber ihre Auswirkung auf In-Context Learning skaliert mit der Modellgroesse

**Implementation:**

```python
def compare_models(model_a, model_b, prompt):
    # 1. Extract all layer activations
    hiddens_a = model_a(prompt, output_hidden_states=True).hidden_states
    hiddens_b = model_b(prompt, output_hidden_states=True).hidden_states

    # 2. Subsample to max 32 layers (for tractability)
    layers_a = subsample_layers(hiddens_a, max_layers=32)
    layers_b = subsample_layers(hiddens_b, max_layers=32)

    # 3. Compute Linear CKA matrix (all layer pairs)
    cka_matrix = np.zeros((len(layers_a), len(layers_b)))
    for i, layer_a in enumerate(layers_a):
        for j, layer_b in enumerate(layers_b):
            cka_matrix[i, j] = linear_cka(layer_a, layer_b)

    return cka_matrix
```

**Paedagogische Visualisierung:**

Die Heatmap zeigt direkt drei Muster:

1. **Diagonale:** Modelle verarbeiten Information in aehnlicher Reihenfolge
2. **Blockstruktur:** Gruppen von Layern mit hoher interner Aehnlichkeit
3. **Fruehe vs. Spaete Layers:** Fruehe oft aehnlicher (Syntax universell), spaete divergieren (Semantik modellspezifisch)

**Kritische Diskussion:**

Kornblith (2019) warnt: CKA misst **repraesentationelle** Aehnlichkeit, nicht **funktionale** Aequivalenz. Zwei Modelle koennen identische CKA-Werte haben, aber unterschiedliche Outputs generieren.

Die Erklaerung betont daher:

> "Hohe Aehnlichkeit bedeutet: Diese Schichten repraesentieren Information auf aehnliche Weise."

Nicht: "Diese Schichten tun dasselbe."

### 6.3 Bias Archaeology

**Wissenschaftlicher Kontext:**

- **Bricken, T. et al. (2023): "Towards Monosemanticity: Decomposing Language Models With Dictionary Learning"** (Anthropic)
  - **Kernidee:** Einzelne Features (nicht Neuronen!) koennen interpretierbar sein
  - **Methode:** Sparse Autoencoders finden monosemantische Features
  - **Erkenntnis:** Bias manifestiert sich in aktivierten Feature-Clustern

- **Zou et al. (2023):** Representation Engineering (siehe RepEng)
  - Hier angewendet auf Bias-Detektion via systematische Token-Manipulation

**Implementation:**

```python
def bias_probe(prompt, preset='gender'):
    if preset == 'gender':
        groups = {
            'masculine': {'tokens': ['he', 'him', 'his', 'himself'], 'mode': 'suppress'},
            'feminine': {'tokens': ['she', 'her', 'hers', 'herself'], 'mode': 'suppress'}
        }

    # 1. Generate baseline (no manipulation)
    baseline_samples = [model.generate(prompt, seed=s) for s in seeds]

    # 2. For each group: modify logits during generation
    for group_name, config in groups.items():
        token_ids = resolve_token_ids(config['tokens'])  # Bare + space + capital

        def logit_surgery(logits):
            if config['mode'] == 'suppress':
                logits[:, token_ids] = -float('inf')  # Hard suppression
            elif config['mode'] == 'boost':
                logits[:, token_ids] += boost_factor  # Additive boost (not multiplicative!)
            return logits

        manipulated = [model.generate(prompt, seed=s, logit_modifier=logit_surgery)
                       for s in seeds]  # Same seeds as baseline

    return {baseline, groups: [...]}
```

**Wissenschaftliche Praezision:**

1. **Token-Varianten-Abdeckung:**
   - "he" -> IDs fuer ["he", " he", "He", " He"]
   - **Grund:** BPE kodiert Leerzeichen als Teil des Tokens

2. **Additive statt Multiplikative Boosts:**
   - Urspruenglich: `logits *= factor` — verursachte Softmax-Kollaps bei grossen Faktoren
   - **Fix:** `logits += factor` (additiv, numerisch stabiler)

3. **Shared Seeds:**
   - Baseline und Manipulated nutzen identische Seeds
   - **Grund:** Isoliert den Effekt der Manipulation von Sampling-Varianz

**Paedagogische Innovation:**

Das Tool macht **implizite Biases** sichtbar durch kontrafaktische Experimente.

**Illustratives Beispiel** (zur Veranschaulichung des Experimentdesigns, keine gemessenen Ergebnisse):

| Bedingung | Prompt: "The doctor explained to the nurse" |
|-----------|----------------------------------------------|
| Baseline | "... that she should check the patient" |
| Feminine suppressed | "... that they should check the patient" |

**Erwartete Erkenntnis:** Wenn das Modell standardmaessig "she" fuer "nurse" generiert, zeigt das eine statistische Assoziation aus dem Trainingskorpus. Ob und wie stark dieser Bias auftritt, haengt vom spezifischen Modell ab.

**LLM-Interpretation:**

Nach jedem Experiment wird automatisch ein LLM (via DevServer `call_chat_helper()`) zur paedagogischen Einordnung gefragt. Das System-Prompt betont sachliche Analyse ohne Wertungen, 3-5 Saetze, in der Sprache der Eingabe.

**Fail-Open:** Wenn die Interpretation fehlschlaegt (LLM nicht verfuegbar), bleiben die Rohergebnisse vollstaendig sichtbar.

**Kritische Diskussion (Alignment mit Bricken 2023):**

Bricken zeigt: Biases sind **polysemantisch** kodiert — nicht in einzelnen Neuronen, sondern in Feature-Kombinationen.

**Implikation:** Token-Suppression ist eine **Proxy-Methode**, keine direkte Feature-Manipulation. Wir messen Bias im **Output-Space** (generierter Text), nicht im **Representation-Space** (latente Features).

**Vorteil:** Direkter paedagogisch zugaenglich; kein Dictionary Learning noetig.

---

## 7. Crossmodal Lab: Klang aus latenten Raeumen

### 7.1 Ueberblick

Das Crossmodal Lab (Tab innerhalb `/latent-lab`) untersucht die Frage: **Wie uebertraegt sich Semantik zwischen Text, Bild und Audio?** Es besteht aus drei Sub-Tabs mit unterschiedlichen Ansaetzen:

| Sub-Tab | Methode | Modell | Primaerliteratur |
|---------|---------|--------|-----------------|
| Latent Audio Synth | T5-Embedding-Manipulation | Stable Audio | — (eigener experimenteller Ansatz) |
| MMAudio | Dediziertes crossmodales Modell | MMAudio (157M) | Cheng et al. 2024 |
| ImageBind Guidance | Gradientenbasierte Bildsteuerung | ImageBind + Stable Audio | Girdhar et al. 2023 |

### 7.2 Latent Audio Synth: Direkte Embedding-Manipulation

**Frage:** Was passiert, wenn man den T5-Conditioning-Raum (768d) von Stable Audio direkt manipuliert?

**Methode (eigener Ansatz, nicht direkt literaturbasiert):**

```python
# 1. Encode two prompts via T5-Base
emb_a = t5_encode(prompt_a)  # [1, seq_len, 768]
emb_b = t5_encode(prompt_b)  # [1, seq_len, 768]

# 2. Manipulate in embedding space
result = (1 - alpha) * emb_a + alpha * emb_b  # Interpolation/Extrapolation
result = result * magnitude                     # Magnitude scaling
result = result + randn_like(result) * noise    # Noise injection
result[:, :, dim_indices] += offsets            # Per-dimension offsets

# 3. Generate audio from manipulated embedding
audio = stable_audio.generate(prompt_embeds=result)
```

**Wissenschaftliche Verbindung:** Die Embedding-Interpolation ist konzeptuell verwandt mit Mikolovs Vektorarithmetik (2013), aber auf Audio-Embeddings angewendet. Die Per-Dimension-Offsets folgen der Logik von Feature Probing (Section 3) — einzelne Dimensionen werden als "semantische Regler" behandelt.

**Paedagogischer Wert:** Der "Dimensions Explorer" (768 manipulierbare Balken) macht die Embedding-Dimensionen als **klangliche Parameter** erfahrbar. Aenderungen einzelner Dimensionen erzeugen hoerbare Unterschiede — oder eben nicht, was wiederum die verteilte Natur der Repraesentationen demonstriert.

**Gescheiterter Vorlaeufer — CLIP Vision → Audio (Strategie A):**

Vor der aktuellen Implementation wurde ein direkterer Ansatz erprobt: CLIP ViT-L/14 Vision Hidden States (1024d) wurden per `F.adaptive_avg_pool1d` auf 768d projiziert und anstelle der T5-Conditioning in Stable Audio eingespeist. Die Hypothese war, dass visuelle Texturen (z.B. ein Waldbild) sich als klangliche Texturen manifestieren wuerden.

**Ergebnis:** Das Verfahren produzierte ausschliesslich Rauschen. Die Dimensionsreduktion ohne gelernte Abbildung reicht nicht aus, um die semantische Struktur zwischen den Modalitaeten zu ueberbruecken — die T5-Conditioning von Stable Audio erwartet sprachlich strukturierte Embeddings, nicht visuelle Feature-Maps. Dieser Misserfolg motivierte die Hinwendung zu MMAudio (genuines crossmodales Training, Section 7.3) und ImageBind Gradient Guidance (gradientenbasierte Steuerung, Section 7.4).

### 7.3 MMAudio: Genuiner crossmodaler Transfer

- **Cheng, H. K. et al. (2024): "MMAudio: Taming Multimodal Joint Training for High-Quality Video-to-Audio Synthesis"** (CVPR 2025)
  - DOI: [10.48550/arXiv.2412.15322](https://doi.org/10.48550/arXiv.2412.15322)
  - **Kernidee:** Multimodales Joint Training auf Audio-Visual- und Audio-Text-Daten
  - **Architektur:** 157M Parameter, Flow-Matching-Objective, Conditional Synchronization Module
  - **Performance:** Generiert 8s Audio in ~1.2s
  - **Unterschied zu naiver Feature-Projektion:** MMAudio ist auf beiden Modalitaeten (Bild/Video + Audio) trainiert worden — der crossmodale Transfer ist gelernt, nicht improvisiert

**Paedagogischer Wert:** Direkter Kontrast zum Latent Audio Synth (Tab 1): Waehrend dort Feature-Projektion ohne modalitaetsspezifisches Training stattfindet, zeigt MMAudio, was ein dediziert crossmodal trainiertes Modell leisten kann. Der Vergleich macht den Unterschied zwischen "naive Projektion" und "genuiner Transfer" erfahrbar.

### 7.4 ImageBind Gradient Guidance: Gradientenbasierte Bildsteuerung

- **Girdhar, R. et al. (2023): "ImageBind: One Embedding Space To Bind Them All"** (CVPR 2023)
  - DOI: [10.48550/arXiv.2305.05665](https://doi.org/10.48550/arXiv.2305.05665)
  - **Kernidee:** Ein gemeinsamer 1024d-Embedding-Raum fuer sechs Modalitaeten (Bild, Text, Audio, Tiefe, Thermal, IMU)
  - **Methode:** Training mit Image-Paired Data genuegt — die Modalitaeten binden sich transitiv
  - **Emergente Faehigkeiten:** Cross-Modal Retrieval, Composing Modalities with Arithmetic

**Implementation im Latent Lab:**

```
Stable Audio Denoising Loop (iterativ):
  1. Predict noise at step t
  2. Compute: similarity = cosine(ImageBind(current_audio), ImageBind(input_image))
  3. Gradient: d(similarity) / d(audio_latents)
  4. Steer: audio_latents += lambda * gradient
  5. Continue denoising
```

Die Methode nutzt den **Gradienten** der ImageBind-Cosine-Similarity, um die Audiogenerierung waehrend des Denoising-Prozesses in Richtung des Bild-Embeddings zu lenken. Parameter `lambda` steuert die Staerke, `warmup_steps` bestimmt, ab wann die Steuerung einsetzt.

**Wissenschaftliche Einordnung:** Diese Methode ist verwandt mit **Classifier Guidance** (Dhariwal & Nichol 2021): Statt eines Klassifikators wird ein multimodales Aehnlichkeitsmass (ImageBind) als Gradienten-Signal genutzt. Der Ansatz ist experimentell und kombiniert zwei bestehende Ideen (Gradient Guidance + multimodaler Embedding-Raum) auf neue Weise.

**Paedagogischer Wert:** Der Kontrast zwischen den drei Tabs macht drei fundamental verschiedene Strategien fuer crossmodale Generierung erfahrbar:

1. **Naive Projektion** (Synth): Features direkt in anderen Raum projizieren — schnell, aber semantisch grob
2. **Joint Training** (MMAudio): Modell auf beiden Modalitaeten trainieren — praezise, aber erfordert spezifisches Training
3. **Gradient Guidance** (ImageBind): Waehrend der Generierung steuern — flexibel, aber rechenintensiv und instabil

---

## 8. Uebergreifende Diskussion: Forschung -> Paedagogik

### 8.1 Designziele

Die folgenden Prinzipien leiten die Entwicklung des Latent Lab. Ihre Umsetzung ist ein fortlaufender Prozess — nicht alle Werkzeuge erfuellen alle Ziele gleich gut.

**1. Wissenschaftliche Praezision ohne Vereinfachung (angestrebt)**

- Vermeidung anthropomorphisierender Sprache (z.B. "Attention zeigt, wo das Modell hinschaut" -> "welche Token-Region-Paare hohe Query-Key-Aehnlichkeit aufweisen")
- In der Praxis gelingt dies unterschiedlich gut: Die UI-Texte sind staerker vereinfacht als dieser Report

**2. Interaktive Falsifikation statt Belehrung (angestrebt)**

- Nutzende sollen Hypothesen selbst testen koennen (z.B. "Kodiert Dimension 42 Farbe?" -> Auswahl nur Dim 42 -> minimale Aenderung -> Hypothese widerlegt)
- Setzt voraus, dass Nutzende wissen, welche Hypothesen testbar sind — hier besteht noch Entwicklungsbedarf in der Nutzer-Fuehrung

**3. Visualisierung mathematischer Konzepte (teilweise umgesetzt)**

- CKA-Matrix: Heatmap mit interaktivem Tooltip statt Formel
- Embedding-Differenzen: Balkendiagramm statt Zahlen-Tabelle
- Denoising-Phasen: Farbkodierte Timeline statt statistischer Plots

**4. Transparenz ueber Grenzen (konsequent umgesetzt)**

- Denoising Archaeology: "Die Phasen sind beobachtbare Muster, keine bewiesenen Gesetzmaessigkeiten"
- Bias Archaeology: "Token-Suppression ist eine Proxy-Methode, keine direkte Feature-Manipulation"
- Attention Cartography: "Korrelation, nicht Kausalitaet"

### 8.2 Luecken zwischen Forschung und Implementation

| Aspekt | Forschung | Latent Lab | Begruendung |
|--------|-----------|------------|------------|
| CKA-Kernel | RBF + Linear (Kornblith 2019) | Nur Linear | Rechenzeit; Linear ausreichend fuer LLMs |
| Diffusion-Arithmetik | Score-Level (Liu 2022) | Embedding-Level | Konzeptuell einfacher; direktes Mikolov-Analogon |
| Probing | Classifier-Training (Belinkov 2022) | Direkte Differenz | Keine Blackbox-Probing-Schicht |
| RepEng Layer-Selektion | Probing-Accuracy auf Validierungsset (Li 2023) | Manuelle Auswahl / letzte Layer | Paedagogische Transparenz |
| Denoising-Analyse | h-space-Statistiken (Kwon 2023) | VAE-Decoding der Latents | Visuell zugaenglicher |

**Gemeinsamer Nenner:** Reduktion auf **interpretierbares Minimum**, nicht **publishable Maximum**.

---

## 9. Verwandte Arbeiten

Das Latent Lab ist nicht die erste Plattform, die ML-Konzepte interaktiv zugaenglich macht. Die folgenden Projekte verfolgen verwandte Ziele mit unterschiedlichen Ansaetzen:

### Distill.pub (Olah et al. 2017-2020)

Interaktive visuelle Erklaerungen neuronaler Netze, publiziert als wissenschaftliches Journal. Artikel wie "Feature Visualization" (Olah 2017) und "Zoom In: Circuits" (Olah 2020) kombinieren Prosa, Visualisierungen und interaktive Elemente.

**Naechstes Analogon zum Latent Lab**, aber mit einem wesentlichen Unterschied: Distill-Artikel sind **read-only Visualisierungen** — Nutzende betrachten vorberechnete Ergebnisse, manipulieren aber nicht selbst. Das Latent Lab erlaubt dagegen freie Eingaben und Echtzeit-Manipulation.

### TensorFlow Playground (Smilkov et al. 2017)

Interaktive Browser-Anwendung zum Training einfacher neuronaler Netze. Nutzende koennen Netzwerk-Architektur, Lernrate und Datensaetze konfigurieren und den Trainingsprozess in Echtzeit beobachten.

**Staerken:** Direkte Manipulation, sofortiges Feedback, keine Installation noetig.
**Unterschied:** Beschraenkt auf einfache Feedforward-Netze (2D-Klassifikation). Keine generativen Modelle, keine Embedding-Raeume, keine Diffusion.

### GAN Lab (Kahng et al. 2019)

Interaktive Visualisierung des GAN-Trainings. Zeigt Generator- und Discriminator-Verhalten auf 2D-Toy-Distributionen in Echtzeit.

**Staerken:** Elegante Visualisierung des adversarialen Trainingsprozesses.
**Unterschied:** 2D-Toy-Distributionen, kein Bezug zu produktiven generativen Modellen. Das Latent Lab arbeitet dagegen mit SD3.5, Stable Audio und LLMs in voller Groesse.

### IRCAM-Differenzierung

Die Werkzeuge des IRCAM (Max/MSP, AudioSculpt, RAVE, Latent Terrain) sind die relevanteste Vergleichsgruppe im Audio-Bereich. Die Differenzierung ist **kulturtheoretisch und paedagogisch**, nicht nur technisch:

- **IRCAM:** Professionelle Produktionswerkzeuge in der Tradition der musique concrete. Ziel: kuenstlerische Klanggestaltung. Zielgruppe: Komponierende und Performer mit technischer Ausbildung.
- **Latent Lab:** Paedagogische Introspektionswerkzeuge. Ziel: kritisches Verstaendnis von KI-Mechanismen. Zielgruppe: Lernende ab 13 Jahren ohne Vorkenntnisse.

Beide manipulieren latente Raeume, aber mit fundamental verschiedenen **Teleologien**: IRCAM fragt "Was kann ich damit schaffen?", das Latent Lab fragt "Wie konstruiert die KI Bedeutung?". (Siehe INTELLECTUAL_PROPERTY.md, Section VII fuer eine ausfuehrliche Differenzierung.)

---

## 10. Literaturverzeichnis

### Primaerliteratur (Direkt implementiert)

1. **Mikolov, T., Sutskever, I., Chen, K., Corrado, G., & Dean, J. (2013).** "Distributed Representations of Words and Phrases and their Compositionality." *Advances in Neural Information Processing Systems (NeurIPS)*. DOI: [10.48550/arXiv.1310.4546](https://doi.org/10.48550/arXiv.1310.4546)

2. **Belinkov, Y. (2022).** "Probing Classifiers: Promises, Shortcomings, and Advances." *Computational Linguistics*, 48(1), 207-219. MIT Press. DOI: [10.1162/coli_a_00422](https://doi.org/10.1162/coli_a_00422)

3. **Bau, D., Liu, S., Wang, T., Zhu, J.-Y., & Torralba, A. (2020).** "Rewriting a Deep Generative Model." *European Conference on Computer Vision (ECCV)*, pp. 351-369. Springer. DOI: [10.1007/978-3-030-58452-8_21](https://doi.org/10.1007/978-3-030-58452-8_21)

4. **Hertz, A., Mokady, R., Tenenbaum, J., Aberman, K., Pritch, Y., & Cohen-Or, D. (2022).** "Prompt-to-Prompt Image Editing with Cross Attention Control." *International Conference on Learning Representations (ICLR) 2023*. DOI: [10.48550/arXiv.2208.01626](https://doi.org/10.48550/arXiv.2208.01626)

5. **Tang, R., Pandey, A., Jiang, Z., Yang, G., Kumar, K., Lin, J., & Ture, F. (2022).** "What the DAAM: Interpreting Stable Diffusion Using Cross Attention." *Annual Meeting of the Association for Computational Linguistics (ACL) 2023*. DOI: [10.48550/arXiv.2210.04885](https://doi.org/10.48550/arXiv.2210.04885)

6. **Kwon, M., Jeong, J., & Uh, Y. (2023).** "Diffusion Models Already Have a Semantic Latent Space." *International Conference on Learning Representations (ICLR) 2023*. DOI: [10.48550/arXiv.2210.10960](https://doi.org/10.48550/arXiv.2210.10960)

7. **Liu, N., Li, S., Du, Y., Torralba, A., & Tenenbaum, J. B. (2022).** "Compositional Visual Generation with Composable Diffusion Models." *European Conference on Computer Vision (ECCV)*, pp. 423-439. Springer. DOI: [10.1007/978-3-031-19803-8_12](https://doi.org/10.1007/978-3-031-19803-8_12)

8. **Zou, A., Phan, L., Chen, S., et al. (2023).** "Representation Engineering: A Top-Down Approach to AI Transparency." arXiv preprint. DOI: [10.48550/arXiv.2310.01405](https://doi.org/10.48550/arXiv.2310.01405)

9. **Li, K., Patel, O., Viegas, F., Pfister, H., & Wattenberg, M. (2023).** "Inference-Time Intervention: Eliciting Truthful Answers from a Language Model." *Advances in Neural Information Processing Systems (NeurIPS) 2023*. DOI: [10.48550/arXiv.2306.03341](https://doi.org/10.48550/arXiv.2306.03341)

10. **Kornblith, S., Norouzi, M., Lee, H., & Hinton, G. (2019).** "Similarity of Neural Network Representations Revisited." *International Conference on Machine Learning (ICML)*, pp. 3519-3529. PMLR. DOI: [10.48550/arXiv.1905.00414](https://doi.org/10.48550/arXiv.1905.00414)

11. **Olsson, C., Elhage, N., Nanda, N., et al. (2022).** "In-Context Learning and Induction Heads." Anthropic Research. DOI: [10.48550/arXiv.2209.11895](https://doi.org/10.48550/arXiv.2209.11895)

12. **Bricken, T., Templeton, A., Batson, J., et al. (2023).** "Towards Monosemanticity: Decomposing Language Models With Dictionary Learning." Anthropic Research. URL: https://transformer-circuits.pub/2023/monosemantic-features/index.html

13. **Cheng, H. K., Ishii, M., Hayakawa, A., Shibuya, T., Schwing, A., & Mitsufuji, Y. (2024).** "MMAudio: Taming Multimodal Joint Training for High-Quality Video-to-Audio Synthesis." *IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) 2025*. DOI: [10.48550/arXiv.2412.15322](https://doi.org/10.48550/arXiv.2412.15322)

14. **Girdhar, R., El-Nouby, A., Liu, Z., Singh, M., Alwala, K. V., Joulin, A., & Misra, I. (2023).** "ImageBind: One Embedding Space To Bind Them All." *IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) 2023*. DOI: [10.48550/arXiv.2305.05665](https://doi.org/10.48550/arXiv.2305.05665)

### Attention-Interpretability-Debatte

15. **Jain, S. & Wallace, B. C. (2019).** "Attention is not Explanation." *Proceedings of the Conference of the North American Chapter of the Association for Computational Linguistics (NAACL)*, pp. 3543-3556. DOI: [10.18653/v1/N19-1357](https://doi.org/10.18653/v1/N19-1357)

16. **Wiegreffe, S. & Pinter, Y. (2019).** "Attention is not not Explanation." *Proceedings of the Conference on Empirical Methods in Natural Language Processing (EMNLP)*. DOI: [10.18653/v1/D19-1002](https://doi.org/10.18653/v1/D19-1002)

### Modell-Architektur und Diffusions-Grundlagen

17. **Ho, J., Jain, A., & Abbeel, P. (2020).** "Denoising Diffusion Probabilistic Models." *Advances in Neural Information Processing Systems (NeurIPS)*. DOI: [10.48550/arXiv.2006.11239](https://doi.org/10.48550/arXiv.2006.11239)

18. **Esser, P., Kulal, S., Blattmann, A., et al. (2024).** "Scaling Rectified Flow Transformers for High-Resolution Image Synthesis." *International Conference on Machine Learning (ICML) 2024*. DOI: [10.48550/arXiv.2403.03206](https://doi.org/10.48550/arXiv.2403.03206)

### Modelle (direkt verwendet)

19. **Radford, A., Kim, J. W., Hallacy, C., et al. (2021).** "Learning Transferable Visual Models From Natural Language Supervision." *International Conference on Machine Learning (ICML)*. DOI: [10.48550/arXiv.2103.00020](https://doi.org/10.48550/arXiv.2103.00020)

20. **Evans, Z., Parker, J. D., Carr, C. J., Zukowski, Z., Taylor, J., & Pons, J. (2024).** "Stable Audio Open." Stability AI. DOI: [10.48550/arXiv.2407.14358](https://doi.org/10.48550/arXiv.2407.14358)

21. **Dhariwal, P. & Nichol, A. (2021).** "Diffusion Models Beat GANs on Image Synthesis." *Advances in Neural Information Processing Systems (NeurIPS)*. DOI: [10.48550/arXiv.2105.05233](https://doi.org/10.48550/arXiv.2105.05233)

### Sekundaerliteratur (Theoretischer Kontext)

22. **Olah, C., Mordvintsev, A., & Schubert, L. (2017).** "Feature Visualization." *Distill*. DOI: [10.23915/distill.00007](https://doi.org/10.23915/distill.00007)

23. **Olah, C., Cammarata, N., Schubert, L., Goh, G., Petrov, M., & Carter, S. (2020).** "Zoom In: An Introduction to Circuits." *Distill*. DOI: [10.23915/distill.00024.001](https://doi.org/10.23915/distill.00024.001)

24. **Elhage, N., Nanda, N., Olsson, C., et al. (2021).** "A Mathematical Framework for Transformer Circuits." Anthropic Research. URL: https://transformer-circuits.pub/2021/framework/index.html

---

## 11. Fazit: Bruecke zwischen Forschung und Bildung

Das Latent Lab uebersetzt 24 wissenschaftliche Publikationen (2013-2025) in interaktive Experimente. Die acht Werkzeuge decken verschiedene Dimensionen der KI-Interpretierbarkeit ab.

**Kernleistungen:**

1. **Methodologische Treue:** Implementationen folgen den Originalpublikationen (z.B. Linear CKA nach Kornblith 2019, PCA-basierte Richtungsextraktion nach Zou 2023)
2. **Transparente Abweichungen:** Wo vereinfacht wird (z.B. VAE-Decoding statt h-space-Analyse), wird dies explizit dokumentiert und begruendet
3. **Erfahrungsbasiertes Lernen:** Komplexe Konzepte (verteilte Repraesentationen, Emergenz, Bias) werden durch direkte Manipulation erfahrbar
4. **Kritische Wissenschaftsvermittlung:** Grenzen und Limitationen werden benannt (Attention = Korrelation nach Jain & Wallace 2019; Token-Suppression = Proxy-Methode)

**Zukuenftige Erweiterungen:**

- **Sparse Autoencoder Features:** Direkte Feature-Visualisierung (Bricken et al. 2023, vollstaendige Implementation statt Proxy-Methode)
- **Circuit Discovery:** Automatische Identifikation von Computational Circuits (Elhage et al. 2021)
- **Gradient-basierte Attribution:** GradCAM-artige Methoden fuer Diffusion (komplementaer zur Attention-Analyse)

**Einordnung (vgl. Section 9, Verwandte Arbeiten):** Bestehende Plattformen wie Distill.pub (read-only Visualisierungen), TensorFlow Playground (einfache Feedforward-Netze) und GAN Lab (2D-Toy-Distributionen) adressieren jeweils Teilaspekte. Das Latent Lab kombiniert **direkte Manipulation**, **produktive generative Modelle** und **paedagogische Zugaenglichkeit** — eine Kombination, die in den verglichenen Projekten nicht auftritt. Ob sich daraus eine eigenstaendige Kategorie von Bildungswerkzeugen ergibt, muss die weitere Entwicklung und Evaluation zeigen.

---

**Dokumentstatus:** Wissenschaftlicher Report
**Version:** 2.1 (Related Work, gescheiterte Experimente dokumentiert, Designziele als aspirativ formuliert)
**Datum:** 2026-02-17
**Autoren:** UCDCAE AI LAB Development Team
**Lizenz:** CC BY-SA 4.0
