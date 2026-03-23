# Latent Audio Synth — Manual

## Was ist das?

Der Latent Audio Synth erzeugt Klänge aus Textbeschreibungen. Er nutzt Stable Audio Open als Klangerzeugungsbackend, arbeitet aber nicht wie ein klassischer Text-to-Audio-Generator: Statt einfach "erzeuge diesen Sound" zu sagen, manipuliert er den **Raum zwischen den Wörtern und dem Klang** — den sogenannten T5-Conditioning-Space (768 Dimensionen).

Das bedeutet: Du kannst zwei Klangbeschreibungen mischen, den Klang entlang akustischer Achsen verschieben, und direkt in den 768 Dimensionen des Sprachmodells malen. Das Ergebnis wird bei jeder neuen Generierung mit einer von den Einstellungen (Länge, Steps) abhängigen Latenz nahtlos eingewechselt (Loop-and-Swap).

---

## Grundprinzip

1. Du gibst ein oder zwei Textprompts ein (z.B. "a steady clean saw wave, c3" und "glass breaking")
2. Das Sprachmodell (T5) wandelt diese Texte in 768-dimensionale Vektoren um
3. Du mischst, skalierst und verschiebst diese Vektoren mit den Reglern
4. Stable Audio erzeugt daraus einen Klang (Diffusionsprozess)
5. Der Klang wird verwendet (MIDI, Sequencer ...) — neue Generierungen ersetzen den laufenden Loop

**Latenz:** Je nach Dauer und Steps zwischen 1 und 10 Sekunden pro Generierung. Das ist kein Echtzeit-Synthesizer, sondern ein **Loop-and-Swap-Instrument**.

---

## Die zwei Prompts

**Prompt A** ist die Basis. **Prompt B** ist optional — wenn gesetzt, kannst du mit dem Alpha-Regler zwischen beiden Klangwelten überblenden.

Gute Prompts beschreiben **Klangeigenschaften**, nicht Musikstücke:
- "a steady clean saw wave, c3" (konkreter Synthesizer-Klang)
- "glass breaking" (konkretes Schallereignis)
- "metallic resonance, high pitch" (abstrakte Klangeigenschaft)
- "wind through a narrow pipe" (physikalische Beschreibung)

Schlechte Prompts: "ein schönes Lied" (zu vage), "Beethoven Sonate" (das Modell kennt keine Stücke).

---

## Hauptregler

### Alpha (Interpolation)
Mischt zwischen Prompt A und Prompt B.
- **0** = nur Prompt A
- **1** = nur Prompt B
- **0.42** = etwas mehr A als B (Default)
- **>1 oder <0** = Extrapolation — das Modell übertreibt die Richtung über die Prompts hinaus. Kann interessante oder chaotische Ergebnisse liefern.

### Magnitude (Skalierung)
Verstärkt oder dämpft das gesamte Embedding.
- **1.0** = unverändert
- **<1** = gedämpft, nebulöser
- **>1** = verstärkt, schärfer, aber auch instabiler

### Noise (Rauschen)
Injiziert Gaußsches Rauschen in den Embedding-Raum.
- **0** = deterministisch (gleicher Prompt → gleicher Klang bei gleichem Seed)
- **0.3–0.5** = leichte Variation, explorativ
- **>0.7** = zunehmend zufällig

---

## Generierungsparameter

### Duration (Dauer)
Länge des erzeugten Audioclips in Sekunden (0.1–5.0s).

- **0.1–0.3s**: Oszillator-Modus — quasi-stationäre Wellenformen, gut zum Loopen
- **0.5–2s**: Sample-Synth — kurze Klangschnipsel mit Attacke und Ausklingen
- **3–5s**: Längere Texturen mit zeitlicher Entwicklung

### Start Position
Wo im "virtuellen Klang" das Generierungsfenster sitzt (0–95%).
- **0%** = Anfang — enthält Attacke/Transienten
- **50%+** = Mitte — stationäres Material, weniger Einschwingvorgang

Bei sehr kurzen Dauern (<0.3s) ist Start Position 0% optimal — das Modell erzeugt bei so kurzen Clips ohnehin kein Einschwingmaterial.

### Steps
Anzahl der Entrauschungsschritte im Diffusionsprozess.
- **5–10**: Schnell, aber gröber
- **20**: Sweet Spot — kaum Qualitätsverlust gegenüber 100, aber 5× schneller
- **50–100**: Höhere Qualität, aber längere Wartezeit

### CFG (Classifier-Free Guidance)
Wie streng das Modell dem Prompt folgt.
- **3–5**: Lockerer, mehr Eigeninterpretation
- **7** (Default): Gute Balance
- **10–15**: Sehr prompttreu, kann aber übersteuern

### Seed
Zufallswert für Reproduzierbarkeit.
- **-1** = zufällig (jede Generierung anders)
- **Fester Wert** (z.B. 123456789) = gleicher Prompt + gleiche Parameter → identischer Klang

---

## Semantische Achsen

Semantische Achsen verschieben den Klang entlang **benannter Gegensatzpaare**. Jede Achse hat zwei Pole — Textbeschreibungen, die das Sprachmodell in entgegengesetzte Richtungen kodiert.

### Wie sie funktionieren

Hinter jeder Achse stehen zwei Textprompts (z.B. "sound tonal" und "sound noisy"). Das System berechnet den Unterschied zwischen diesen beiden Vektoren im 768d-Raum. Wenn du den Regler bewegst, wird dieser Unterschied auf dein aktuelles Embedding addiert oder subtrahiert.

*****
Dieses Feature ist sehr experimentell. Mal reagieren die Slider halbwegs nach ihren Bezeichnungen, mal weniger. Datenbasierte PCA-Achsen reagieren ggf. zuverlässiger als die semantisch basiderten Achsen.

**Regler links** = Richtung Pol B, **Regler rechts** = Richtung Pol A.

### Verfügbare Achsen (Auswahl)

**Wahrnehmungsebene** (direkt hörbar):
- **tonal ↔ noisy** — reiner Ton vs. Rauschen (stärkste Achse, d=4.8)
- **rhythmic ↔ sustained** — pulsierend vs. gleichmäßig
- **bright ↔ dark** — hell vs. dunkel (Obertongehalt)
- **loud ↔ quiet** — laut vs. leise
- **smooth ↔ harsh** — glatt vs. rau
- **fast ↔ slow** — schnell vs. langsam
- **dense ↔ sparse** — dicht vs. dünn
- **close ↔ distant** — nah vs. fern (Raumwirkung)

**Kulturelle Ebene** (subtiler, eher für längere Generierungen):
- **acoustic ↔ electronic**
- **improvised ↔ composed**
- **sacred ↔ secular**
- **traditional ↔ modern**
- **solo ↔ ensemble**
- **vocal ↔ instrumental**

**Kritische Ebene** (experimentell):
- **music ↔ noise** — Grenze zwischen Musik und Geräusch
- **complex ↔ simple**
- **refined ↔ raw**
- **beautiful ↔ ugly**

### Tipps

- 1–3 gleichzeitig aktive Achsen sind ein guter Ausgangspunkt
- Mehr Achsen = schwächerer Effekt pro Achse (die Effekte addieren sich und können sich gegenseitig verwässern)
- Der **d-Wert** in der Dropdown-Liste zeigt die Distanz zwischen den Polen — höher = stärkerer Effekt

---

## PCA-Achsen (datengetrieben)

### Was ist der Unterschied zu semantischen Achsen?

| | Semantische Achsen | PCA-Achsen |
|---|---|---|
| **Herkunft** | Von Hand definierte Textpaare | Statistisch aus 392.000 Klangbeschreibungen extrahiert |
| **Benennung** | Klar: "tonal ↔ noisy" | Interpretativ: "Natural ↔ Synthetic" (Annäherung) |
| **Berechnung** | Zwei Prompts durch T5, Differenz = Richtung | Hauptkomponentenanalyse (PCA) über den gesamten Trainingskorpus |
| **Stärke** | Gezielte Kontrolle über eine benannte Eigenschaft | Bewegt sich entlang der Richtungen, in denen die meisten Klangunterschiede liegen |
| **Schwäche** | Begrenzt auf das, was sich in zwei Worten fassen lässt | Labels sind Annäherungen — die tatsächliche Wirkung muss erhört werden |

### Wie PCA-Achsen funktionieren

Stell dir den 768-dimensionalen Raum vor, in dem alle Klangbeschreibungen leben. Manche Richtungen in diesem Raum machen einen großen Unterschied (viele verschiedene Klänge liegen entlang dieser Richtung), andere machen kaum einen Unterschied.

PCA findet diese **Richtungen maximaler Variation** automatisch. PC1 ist die Richtung, entlang der sich die meisten Klangbeschreibungen am stärksten unterscheiden. PC2 die zweitstärkste, usw.

Die ersten 10 PCA-Achsen haben interpretative Labels, die aus der Analyse der Extremwerte abgeleitet wurden:

| Achse | Pol − (links) | Pol + (rechts) | Erklärung |
|---|---|---|---|
| PC1 | Synthetic | Natural | Abstrakte Prozesse ↔ konkrete akustische Ereignisse |
| PC2 | Physical | Sonic | Physische Handlungen ↔ klangliche Phänomene |
| PC3 | Elemental | Musical | Elementarklänge (Wind, Wasser) ↔ musikalische Produktion |
| PC4 | Tonal | Textured | Klar tönend ↔ raue Oberflächentextur |
| PC5 | Mechanical | Social | Maschinengeräusche ↔ menschliche Szenen |
| PC6 | Atmospheric | Vocal | Wetter/Umgebung ↔ Stimme/Sprache |
| PC7 | Biological | Machine | Tierlaute ↔ Motoren/Fahrzeuge |
| PC8 | Crowd | Intimate | Menschenmengen ↔ Kontakt/Berührung |
| PC9 | Abstract | Material | Abstrakte Töne ↔ haptisches Material |
| PC10 | Expression | Motion | Ausrufe/Reaktionen ↔ Fortbewegung |

**Wichtig:** Diese Labels sind Annäherungen. Die tatsächliche klangliche Wirkung einer PCA-Achse kann sich je nach Ausgangsprompt unterscheiden. Die Richtung ist immer dieselbe, aber was sie *klingt* hängt davon ab, wo im Raum du startest. Experimentieren und Hören ist der beste Weg.

PC11–PC32 haben keine Labels und erscheinen als "PC11+/PC11−" etc. Sie sind weniger einflussreich (je höher die Nummer, desto weniger Varianz), können aber trotzdem hörbare Effekte erzeugen.

---

## Dimension Explorer

Der Dimension Explorer zeigt alle 768 Dimensionen des T5-Embeddings als vertikale Balken. Du kannst direkt in diese Dimensionen malen (Klick + Ziehen).

**Vorsicht:** Der T5-Raum ist nicht akustisch isotrop — die meisten Dimensionen haben keinen hörbaren Effekt, manche erzeugen drastische Änderungen, und die Ergebnisse sind schwer vorhersagbar. Der Dimension Explorer ist ein Werkzeug für Exploration und Zufall, nicht für gezielte Klanggestaltung.

Wenn zwei Prompts (A und B) aktiv sind, werden die Dimensionen nach ihrem **Unterscheidungspotenzial** sortiert — die Dimensionen, die den größten Unterschied zwischen A und B ausmachen, stehen links.

---

## Audio-Engine

### Transport (Abspielen / Stopp)

- **Generate** erzeugt einen neuen Klang und spielt ihn ab
- **Stop** pausiert die Wiedergabe
- **Play** nimmt die Wiedergabe wieder auf

Der Transport-Status (Spielend / Pausiert / Generierend) ist unabhängig von einzelnen Noten-Events — MIDI-Noten oder Sequencer-Steps ändern den Transport nicht.

### Loop-Modus

- **One-shot**: Spielt einmal ab, stoppt am Ende
- **Loop**: Wiederholt den Klang nahtlos (mit Crossfade)
- **Ping-pong**: Spielt vorwärts, dann rückwärts, dann wieder vorwärts...

### Looper vs. Wavetable

Der Synth hat zwei Wiedergabe-Engines, die nicht gleichzeitig aktiv sein können:

**Looper** (Standard): Spielt den generierten Audioclip als Ganzes ab. Unterstützt Pitch-Shifting (OLA/WSOLA), Loop-Region-Auswahl, Crossfade-Optimierung. Gut für längere Klänge (0.5–5s).

**Wavetable**: Extrahiert Einzelzyklen aus dem Audio und spielt sie als Wavetable-Oszillator ab. Unterstützt polyphonen Betrieb, Frequenzsteuerung per MIDI, Scan-Position zum Morphen zwischen Frames. Gut für ultra-kurze Klänge und tonale Kontrolle.

### Semantische Wavetable (experimentell)

Statt Frames aus einem einzelnen Audioclip zu extrahieren, generiert der "From Axis"-Modus **N ultra-kurze Samples entlang einer semantischen oder PCA-Achse**. Jede Achsenposition wird zu einem Wavetable-Frame.

Ergebnis: Scannen durch die Wavetable = Sweep durch den semantischen Raum. Die Wavetable IST die Achse.

---

## MIDI

### Notensteuerung
- **Note-On**: Triggert den aktiven Engine (Looper: Retrigger + Transpose, Wavetable: Frequenz)
- **Note-Off**: Release-Phase der ADSR-Hüllkurve
- **Legato**: Bei gehaltenen Noten wird nur transponiert, nicht neu getriggert

### CC-Zuweisungen
- **CC1**: Alpha (Interpolation A↔B)
- **CC2**: Magnitude
- **CC3**: Noise
- **CC5**: Wavetable Scan Position
- **CC64**: Loop-Modus (Sustain-Pedal: gedrückt = Loop, los = One-shot)

### ADSR-Hüllkurve
Attack, Decay, Sustain, Release — formt die Lautstärke bei Noten-Events. Wird nur aktiv, wenn die Werte von der Neutralstellung abweichen. Gilt für beide Engines (Looper und Wavetable).

---

## Step-Sequencer

16-Step-Grid mit einstellbarem Tempo. Triggert den aktiven Engine pro Step. Unterstützt Arpeggiator (aufwärts, abwärts, alternierend) mit einstellbarer Rate.

---

## Technischer Hintergrund

Der Synth arbeitet im **T5-Conditioning-Space** von Stable Audio Open. T5-Base ist ein Sprachmodell, das Text in 768-dimensionale Vektoren übersetzt. Diese Vektoren steuern den Diffusionsprozess (DiT), der den Klang erzeugt.

Die semantischen Achsen sind **Differenzvektoren** zwischen zwei T5-Encodings. Die PCA-Achsen sind die **Hauptvariationsrichtungen** im Raum aller 392.000 Klangbeschreibungen, auf denen T5 trainiert wurde.

Jede Änderung am Embedding erfordert einen neuen Diffusions-Durchlauf — es gibt keine Echtzeit-Manipulation des Klangs. Loop-and-Swap ist die Lösung: Der letzte Klang läuft weiter, während der nächste erzeugt wird.
