# i18n Translation Work Orders

Instructions for the `i18n-translator` agent: process all entries under **Pending**, translate
the listed keys from `en.ts` into `de.ts`, `tr.ts`, `ko.ts`, `uk.ts`, `fr.ts`, `es.ts`, `he.ts`, `ar.ts`, `bg.ts`, then move
each processed work order to **Completed** with a date stamp.

**A measured number belongs to the sentence it was measured over.** Where an order changes a
translated sentence that carries measured values elsewhere — today
`latentLab.flowLogic.transformer.vectors.langs` and `.langNote`, counted over the sentence each
language file holds in `promptExamples.presets.house` / `diffusion.prompt.example` — the number
for that language is void with it, and `langNote` with them. Report them back for re-measuring.
Never leave them standing because the key's own row says the numbers stay as they are: that is
what happened on 2026-09-08, and the bar chart on the overview map carried four wrong numbers
for two weeks.

## Pending

<!-- Add new work orders here. Format:

### WO-YYYY-MM-DD-short-description
- **Session**: <number>
- **Scope**: en.ts (or additional files like canvas.ts, interception configs)
- **Changed keys** (new or modified):
  - `section.subsection.key` (NEW)
  - `section.subsection.key` (MODIFIED): "old value" -> "new value"
- **Context**: Brief semantic description to guide translation accuracy.

Tags:
  - (NEW) = key did not exist before, translate from English
  - (MODIFIED) = English text changed, all 5 translations are stale and must be re-done
-->

### WO-2026-09-24-S1 — Feld-Labels: eigenes Register, eigene Entscheidung nötig

**Status:** Pending (nur Notiz, keine Ausführung in diesem Ticket)

Feld-Labels und Hinweise mit Anrede — z. B. „Dein Prompt:“ (de.ts, Vergleiche und Latent Lab), „Deine Nachricht“, Fehlerzeilen mit „Du“/„Sie“. Das sind Benennungen der Urheberschaft an der Oberfläche: die Fläche schreibt der Eingabe ihren Autor zu. **Eigenes Register, eigene Entscheidung nötig** — ob und wie die Urheberschaft an der Oberfläche benannt wird („Dein Prompt“ / „Prompt“ / „Eingabe“ / Gruppen-Anrede für Gruppenflächen), ist eine Frage des Regelsystems und der Flächenform, keine bloße Übersetzungsentscheidung; nicht in einem Slop-Durchlauf mitentscheiden. Grep-Startpunkte (de.ts, Stand 24.09.): Zeilen 7–70, 862, 1600–1609, 3503–3534, 3956–3960, 4064 (~35 Treffer; Plan Revision 2 zu UCD-103, Abschnitt 2).

### WO-2026-09-24-S2 — Erklärungstexte (explainWhat/How, tech, note, platformNote)

**Status:** Pending (nur Notiz, keine Ausführung in diesem Ticket)

Erklärungstexte der Instrumente — explainWhatText, explainHowText, explainReadText, techText, noteBody/noteLimits, platformNote. ~30 Anrede-Treffer (de.ts, Stand 24.09.: Zeilen 1136–1141, 2038–2044, 2613, 2669, 2960, 3017 u. a.). Aufgabe ist, die anrede-freie Sprachform sinngemäß anzuwenden (keine konstative zweite Person, keine Aufgabenstimme); Recherchetexte erst nach Durchsicht umformen. Maßstab wie in WO-2026-09-24-C1, Punkte 1–6; die deutsche Fassung ist Referenz. Eigener Durchgang.

### WO-2026-09-24-S3 — Spiel- und Kontextformulierungen (CO₂-Spiel, Workshop-Planung)

**Status:** Pending (nur Notiz, keine Ausführung in diesem Ticket)

Spielflächen und Kontextformulierungen mit Anrede — CO₂-Spiel und Workshop-Planung (~16 Treffer, de.ts Zeilen 3730–3746, 3754–3779, 3916–3920). Diese Flächen sind Gruppenaktionen — der kollektive Aktionskontext ist die benannte Ausnahme der Regel „Anrede ist der Ausnahmefall“. Hier kann die Anrede die richtige Form sein; deshalb eigener Bestand mit eigener Prüfung, nicht Teil des Ansprachen-Durchlaufs. Ob die Anrede bleibt, wird je Fläche entschieden; die Arbeitsaufträge dazu entstehen, wenn dieser Bestand dran ist.

### WO-2026-09-26-L — Einstellungen: zwei Modell-Rollen nennen keine Sicherheitsprüfung mehr
- **Scope**: en.ts
- **Changed keys**:
  - `settings.models.stage1Text` (MODIFIED): "Translation and safety check — written prompt" -> "Translation — written prompt"
  - `settings.models.stage3` (MODIFIED): "Translation and safety check — final prompt" -> "Translation — final prompt; verdict on flagged code"
- **Context**: Beschriftungen zweier Modell-Rollen auf der Einstellungsseite. Seit dem Umbau der Prüfkette auf einen Klassifikator (24.09.) prüft keine der beiden Rollen einen Prompt: `STAGE1_TEXT_MODEL` übersetzt den geschriebenen Prompt, `STAGE3_MODEL` übersetzt den finalen Prompt und urteilt über generierten Code (p5.js, Sonic Pi), den ein Musterfilter auffällig gefunden hat. Deutsche Fassung: „Übersetzung — geschriebener Prompt“ und „Übersetzung — finaler Prompt; Urteil über auffälligen Code“.

Betroffen: de, tr, ko, uk, fr, es, he, ar, bg.

### WO-2026-10-01-S — Einstellungen: ein Sicherheitsmodell statt drei
- **Scope**: en.ts
- **Changed keys**:
  - `settings.safetyModels.title` (MODIFIED): "Local Safety Models" -> "Local Safety Model"
  - `settings.safetyModels.help` (MODIFIED): "Local — person names and safety checks never leave the system" -> "Checks of prompts, images and person names run on this machine."
  - `settings.safetyModels.safetyModelHelp` (MODIFIED): "Guard model for content safety (§86a, youth protection)" -> "The classifier these checks ask. Generated code that the filter flags is judged by the translation model instead."
- **Changed keys** (REMOVED, delete from all 9 language files):
  - `settings.safetyModels.dsgvoModel`
  - `settings.safetyModels.dsgvoModelHelp`
  - `settings.safetyModels.vlmModel`
  - `settings.safetyModels.vlmModelHelp`
  - `settings.safetyModels.fast`
  - `settings.safetyModels.recommended`
- **Context**: Abschnitt mit dem Sicherheitsmodell auf der Einstellungsseite. Seit dem Umbau der Prüfkette (24.09.) fragen die Prüfungen von Prompts, Bildern und Personennamen einen einzigen Klassifikator (Shieldstral); die Felder für das DSGVO-Verifikationsmodell und das Bild-Prüfmodell sind entfallen. Generierten Code, den der Musterfilter markiert, beurteilt weiter das Modell der Zeile `settings.models.stage3` („Translation — final prompt; verdict on flagged code“); „translation model“ meint dieses Modell. Deutsche Fassung: „Lokales Sicherheitsmodell“, „Prüfungen von Prompts, Bildern und Personennamen laufen auf diesem Rechner.“ und „Der Klassifikator, den diese Prüfungen fragen. Generierten Code, den der Filter markiert, beurteilt stattdessen das Übersetzungsmodell.“

Betroffen: de, tr, ko, uk, fr, es, he, ar, bg.
### WO-2026-09-26-M — Beispiel-Prompts: zehn neue zentrale Presets
- **Session**: <n/a — UCD-119>
- **Scope**: en.ts
- **Changed keys** (all NEW, under `promptExamples.presets`):
  - `promptExamples.presets.walk` (NEW): "a walk in the forest, in the afternoon"
  - `promptExamples.presets.forest` (NEW): "a walk in the forest, seen through the eyes of a child"
  - `promptExamples.presets.friendship` (NEW): "friendship"
  - `promptExamples.presets.loneliness` (NEW): "loneliness"
  - `promptExamples.presets.meal` (NEW): "a family at dinner"
  - `promptExamples.presets.city` (NEW): "a street in the evening"
  - `promptExamples.presets.nurse` (NEW): "a nurse at work"
  - `promptExamples.presets.plumber` (NEW): "a plumber at work"
  - `promptExamples.presets.festival` (NEW): "a crowded place, completely empty"
  - `promptExamples.presets.shortcut` (NEW): "a house"
- **Context**: DIESE SCHLÜSSEL SIND PROMPTS, KEINE COPY — die etablierte Regel des Blocks gilt auch hier: die Übersetzung trägt den SATZ in die Zielsprache (Sinn und Satzbau des ganzen Satzes), nicht seine Wortwahl Wort für Wort. Sie lesen sich als vollständige Sätze bzw. Satzfragmente, die ein Bildmodell als Eingabe bekommt (wie die drei Bestands-Presets `house`, `street`, `person` im selben Block). Kurze Ein-Wort-Einträge (`friendship`, `loneliness`) bleiben Ein-Wort-Einträge — keine Hinzufügung, keine Erklärung, keine Anführungszeichen; gerade die Unterbestimmtheit ist der Punkt (abstrakter Begriff ohne jede Angabe → Klischee-Übersetzung, teotia-et-al-2025). `forest` übersetzt „seen through the eyes of a child" sinngemäß (z. B. „aus den Augen eines Kindes gesehen") — Alltagssprache der 8–17-Jährigen, kein Prompt-Engineering-Jargon. `festival` ist ein Grenz-Experiment (widersprüchliche Regeln, Katalog #10): wörtlich übersetzen, auch der Widerspruch gehört ins Material. Hintergrund je Eintrag (Eigenschaft + Auswerte-Fläche) steht als Kommentar in en.ts über jedem Eintrag; Grundlage ist der Eigenschaften-Katalog von UCD-118 (Plan Rev. 3).

Betroffen: de, tr, ko, uk, fr, es, he, ar, bg.

## WO-2026-09-27-B — Spezial-Instrumente des Diffusion Lab: Paare/Triplets nach dem Eigenschaften-Katalog

**Status:** Pending

Die drei Spezial-Instrumente Feature Probing, Concept Algebra und Composable Diffusion
hatten je einen Beispiel-Eintrag (ein Paar, ein Triplett, zwei Konzepte). Ergänzt nach dem
Eigenschaften-Katalog von UCD-118 (Plan Rev. 3, Abschnitt 3): jeder Eintrag adressiert
EINE beobachtbare Eigenschaft, der Kommentar in en.ts nennt Eigenschaft und
Auswerte-Fläche (P2/P6). Paar-Disziplin (Empfehlung 3): Vergleichs-Eigenschaften stehen
als Paar in der Fläche, die den Seed hält — diese Instrumente halten den Seed, also
gehören die Paare hierher, nicht in die generische Zentral-Liste.

DIESE SCHLÜSSEL SIND PROMPTS, KEINE COPY — die Regel des zentralen Blocks gilt auch
hier: die Übersetzung trägt den SATZ in die Zielsprache (Sinn und Satzbau), nicht seine
Wortwahl Wort für Wort. Die Label-Schlüssel (`*Label`) sind die Zeile der Liste und
bauen sich aus den Prompt-Sätzen mit den Trennern „ / “ (Paare) bzw. „ − “ und „ + “
(Triplett) zusammen — so zusammengesetzt wie der bestehende `housesLabel`/`riverLabel`
Bestand, sinngemäß mit den übersetzten Sätzen. Komposable-Diffusion-Einträge brauchen
kein Label (die Zeile baut die Fläche aus den Begriffen mit „ + “ selbst).

| Key | Englisch | Kontext |
|---|---|---|
| `latentLab.probing.promptExamples.streetLabel` (NEU) | `the street where I live, in the morning, as a pencil drawing / the street where I live, in the morning, as an oil painting` | Zeile des neuen Paars in der Beispielliste des Feature Probing: beide Sätze mit „ / “ getrennt, wie `housesLabel`. Eigenschaft #5 (WIE bei gehaltenem WAS — Material). |
| `latentLab.probing.promptExamples.streetA` (NEU) | `the street where I live, in the morning, as a pencil drawing` | Satz A des Paars, füllt das Feld „Prompt A (Original)“. Wie der Bestands-`street`-Satz mit angehängtem Material. |
| `latentLab.probing.promptExamples.streetB` (NEU) | `the street where I live, in the morning, as an oil painting` | Satz B des Paars, füllt „Prompt B (Comparison)“. Nur das Material unterscheidet sich von A — genau das macht das Paar aus. |
| `latentLab.probing.promptExamples.timeLabel` (NEU) | `a meadow at noon / a meadow at midnight` | Zeile des Tageszeit-Paars (Board-Korrektur 27.09.2026 zum alten Grenz-Experiment-Paar: der schwache Widerspruch „sunny … at night" kollabierte empirisch zur amerikanischen Nacht — Paare halten zwei klar getrennte Vektoren, Widersprüche bleiben Einzelsätze). Aufbau wie `streetLabel`. |
| `latentLab.probing.promptExamples.timeA` (NEU) | `a meadow at noon` | Satz A — Mittag. |
| `latentLab.probing.promptExamples.timeB` (NEU) | `a meadow at midnight` | Satz B — Mitternacht; nur die Zeitwörter ändern sich, wörtlich übersetzen. |
| `latentLab.algebra.promptExamples.childLabel` (NEU) | `the street where I live, in the morning, seen through the eyes of a child − the street where I live, in the morning + the street where I live, in the morning, seen through the eyes of an adult` | Zeile des Triplets in der Beispielliste des Concept Algebra: A − B + C mit den Zeichen „ − “ und „ + “, wie `riverLabel`. Board-Korrektur 27.09.2026 (UCD-118): B ≠ A — die Subtraktion muss eine Richtung tragen (mit B = A kollabiert die Referenz, das Ergebnis wird trivial zu C). Eigenschaft #4 (WAS bei gehaltenem WIE — Rolle), als word2vec-Analogie gelesen: child → adult bei gehaltener Straße. |
| `latentLab.algebra.promptExamples.childA` (NEU) | `the street where I live, in the morning, seen through the eyes of a child` | Operand A (Base). |
| `latentLab.algebra.promptExamples.childB` (NEU) | `the street where I live, in the morning` | Operand B (Subtrahend) — die gehaltene Straße OHNE die Rolle (wie `riverB`: B = A minus das eine veränderliche Element, Board-Korrektur 27.09.2026). Wörtlich gleich übersetzen wie der Bestands-`street`-Satz. |
| `latentLab.algebra.promptExamples.childC` (NEU) | `the street where I live, in the morning, seen through the eyes of an adult` | Operand C (Addend) — die Erwachsenen-Rolle, sonst derselbe Satz. |
| `latentLab.algebra.promptExamples.lonelyLabel` (NEU) | `a street in the evening, with people − a street in the evening + loneliness` | Zeile des dritten Triplets: abstrakter Begriff als Richtung (Eigenschaft #6, Algebra-Seite). Aufbau wie `childLabel`; B ≠ A per Board-Korrektur 27.09.2026 (UCD-118). |
| `latentLab.algebra.promptExamples.lonelyA` (NEU) | `a street in the evening, with people` | Operand A (Base) — die Abendszene mit Menschen. |
| `latentLab.algebra.promptExamples.lonelyB` (NEU) | `a street in the evening` | Operand B — die Abendszene OHNE die Menschen (B = A minus das veränderliche Element, Board-Korrektur 27.09.2026). Wörtlich gleich übersetzen wie `lonelyA` ohne den Menschen-Zusatz. |
| `latentLab.algebra.promptExamples.lonelyC` (NEU) | `loneliness` | Operand C: der abstrakte Begriff allein, Ein-Wort-Eintrag wie die zentralen `friendship`/`loneliness`-Presets — keine Hinzufügung, keine Anführungszeichen. |
| `latentLab.composable.promptExamples.childAdult` (NEU) | `the street where I live, in the morning, seen through the eyes of a child` | Erster Begriff des neuen Eintrags (Kind-Rolle); füllt zusammen mit `childAdult2` die Begriffsliste. |
| `latentLab.composable.promptExamples.childAdult2` (NEU) | `the street where I live, in the morning, seen through the eyes of an adult` | Zweiter Begriff desselben Eintrags (Erwachsenen-Rolle). |
| `latentLab.composable.promptExamples.treeHouse` (NEU) | `a tree` | Erster Begriff des dritten Eintrags: Ding und lebendes Gegenstück als getrennte Energien. |
| `latentLab.composable.promptExamples.treeHouse2` (NEU) | `a house` | Zweiter Begriff desselben Eintrags — Zweiwort-Eintrag, wie der Bestand (`house`/`ship`). |

Betroffen: de, fr, es, tr, ko, uk, ar, bg, he.


---

### WO-2026-09-27-J — Resona-Szenen-Kapseln: PDF-Aufnahme, Kapsel-Streifen, Ablehnungs-Texte

- **Session**: <n/a — UCD-133>
- **Scope**: en.ts
- **Changed keys** (all NEW, under `resonaScene`):
  - `resonaScene.kind` (NEW): "Scene capsules"
  - `resonaScene.stripLabel` (NEW): "Capsules of the document"
  - `resonaScene.promptLabel` (NEW): "Prompt"
  - `resonaScene.carry` (NEW): "Into the line"
  - `resonaScene.flaggedCount` (NEW): "{n} sections excluded, protection reasons"
  - `resonaScene.discardedCount` (NEW): "{n} capsules discarded by the capsule gate"
  - `resonaScene.analyzed` (NEW): "Analysed {date}"
  - `resonaScene.duplicate` (NEW): "This document has already been analysed in this session. The capsules that exist keep standing."
  - `resonaScene.analysisFailed` (NEW): "The document analysis did not complete. The file stays with whoever brought it; nothing was kept."
  - `resonaScene.unavailable` (NEW): "The document could not be taken in because of a technical fault. Nothing was judged; please try again in a moment."
  - `resonaScene.rejectTitle` (NEW): "Document not accepted"
  - `resonaScene.rej.notPdf` (NEW): "Document not accepted: the file is not a readable PDF."
  - `resonaScene.rej.encrypted` (NEW): "Document not accepted: encrypted documents are not taken."
  - `resonaScene.rej.tooManyPages` (NEW): "Document not accepted: the document exceeds the page limit of 1000 pages."
  - `resonaScene.rej.embeddedFile` (NEW): "Document not accepted: the document carries embedded files."
  - `resonaScene.rej.launchAction` (NEW): "Document not accepted: the document carries actions that start programs."
  - `resonaScene.rej.blocked` (NEW): "Document not accepted: this document is blocked."
  - `resonaScene.rej.para86a` (NEW): "Document not accepted: symbols of organisations banned under German law."
  - `resonaScene.rej.para86` (NEW): "Document not accepted: content of organisations banned under German law."
  - `resonaScene.rej.further` (NEW): "Document not accepted: the content does not meet the admission criteria."
  - `resonaScene.rej.generic` (NEW): "Document not accepted."
- **Context**: Szenen-Kapsel-Streifen der Resona-Fläche (UCD-133 auf dem UCD-132-Backend). Ein im Flow gebrachtes PDF wird zu Szenen-Kapseln analysiert; die Kapseln stehen als Streifen auf dem Brett. Formulierungen: Labels sind Namensformen (Substantiv des Schlüssels — `kind`/`stripLabel`/`promptLabel` als Rubrik), Meldungen je ein deklarativer Satz, anrede-frei (Regel 17; der Streifen nennt die Sache, nicht die Leserin). `carry` ist der Weg, den der Prompt der angesteuerten Kapsel in die offene Schreibzeile der Fläche nimmt — die Schreibzeile ist das Prompt-Werkzeug dieser Fläche; keine Aufforderung, keine Aufgabenstimme. Die `rej.*`-Sätze sagen die Grundkategorie des Aufnahme-Gates verständlich, OHNE einen gefundenen Begriff zu wiederholen (§86/§86a werden benannt als Rechtskategorie, nie mit einem Kennzeichen oder Organisationsnamen). `flaggedCount`/`discardedCount` melden ausgeschlossene Abschnitte und verworfene Kapseln NUR als Anzahl — nie als Inhalt. `{n}` und `{date}` sind Platzhalter. Deutsche Fassung als Arbeitsgrundlage im UCD-133-Ticket (Plan §4).

Betroffen: de, tr, ko, uk, fr, es, he, ar, bg.

### WO-2026-09-28-A — Flow: die Dokument-Option am Plus trägt in keiner Sprache außer Deutsch ihren Text

- **Session**: <n/a — UCD-142, Schritt 5>
- **Scope**: en.ts
- **Changed keys** (unter `x2xFlow`):
  - `x2xFlow.bringDocument` (NEW): "document"
  - `x2xFlow.addDocument` (MODIFIED): "add document" -> "add document (PDF)"
- **Context**: Die beiden Schlüssel stehen am vierten Fächer-Punkt des Plus auf dem Flow-Brett (`src/views/x2x_flow.vue`, die `three`-Liste): `bringDocument` ist die Beschriftung des Punktes, `addDocument` sein `title`. Sie existierten bisher nur in `en.ts` und `de.ts`; die anderen acht Sprachen fielen auf Englisch zurück, während die drei Nachbarpunkte (`bringText`/`addText`, `bringImage`/`addImage`, `bringSketch`/`addSketch`) überall übersetzt sind. `bringDocument` ist eine Namensform wie seine drei Nachbarn — das Substantiv allein, kein Artikel, kein Verb (Regel 17). `addDocument` ist die Handlung, die der Klick ausführt, in der Form der Nachbarn (`addText` „add text" / de „Text hinzufügen"); die englische Fassung trug das `(PDF)` nicht, das die deutsche seit ihrer Anlage trägt, und holt es damit nach: Der Punkt nimmt genau PDF auf, und der Dateityp ist die eine Auskunft, die der Fächer sonst nirgends gibt. Deutsche Referenzfassungen stehen schon in `de.ts` und sind die Vorlage: `bringDocument` = „Dokument", `addDocument` = „Dokument (PDF) aufnehmen". Für `de.ts` ist daher nichts zu tun; die acht übrigen Sprachen übersetzen beide Schlüssel nach dieser Vorlage und in der Form, die sie für die drei Nachbarpunkte bereits gewählt haben.

Betroffen: de (liegt vor, Referenz), tr, ko, uk, fr, es, he, ar, bg.

## Completed

