# Quelle der Zuordnungen

Alle Zeilen in `unterstuetzung.tsv` werden am Wortlaut des AILit-Frameworks
gemessen. Der Wortlaut steht in `learner_expectations.tsv` (die 57 Learner
Expectations) und `classroom_scenarios.tsv` (die 57 Unterrichtsbeispiele „In the
Classroom“), wörtlich und mit Seitenzahl.

## Bibliografische Angabe

OECD / European Union (2026). *Empowering learners for the age of AI: An AI
literacy framework for primary and secondary education.* OECD Publishing, Paris.
<https://doi.org/10.1787/65cd27d4-en>

Lizenz: Creative Commons Attribution 4.0 International (CC BY 4.0).
Bezogen am 2026-09-02 von <https://ailiteracyframework.org/pdfs/framework_pdf/AILF_en.pdf>
(11 231 219 Bytes, MD5 `633de5c7cd0be5b10afa6419c0e863cf`). Das PDF selbst liegt
nicht im Repository; `learner_expectations.tsv` und `classroom_scenarios.tsv`
enthalten die zitierten Stellen. Die Seitenzahlen sind die gedruckten des PDF
(physische Seite minus 2).

Der **Review Draft (Mai 2025)** ist eine andere Fassung und trägt diese
Zuordnungen nicht: er führt 22 Kompetenzen, die Domäne heißt dort noch
*Designing AI*, und Learner Expectations mit den Stufen Basic / Intermediate /
Advanced kommen darin überhaupt noch nicht vor. Was in den Sichten steht, ist
ausschließlich an der Endfassung geprüft.

## Was das Framework über die Bewertung selbst sagt

Vier Stellen, die für die Form dieser Tabelle maßgeblich sind:

- **Die Stufen sind ein Entwicklungsverlauf und ein Gerüst, kein Prüfmaßstab**
  (S. 25): „Learner Expectations detail progressions of use that span from Basic
  to Intermediate and Advanced. These progression levels apply to primary and
  secondary education outcomes, but do not correspond to specific age ranges or
  grade levels. […] Teachers and educators are encouraged to use these Learner
  Expectations to build their own evaluation rubrics and implement appropriate
  learning experiences within their unique settings.“
- **Vollabdeckung ist ausdrücklich keine Erwartung** (S. 9): „AI literacy
  encompasses a wide range of concepts and practices; given this breadth, it may
  not always be realistic for one educator to address every aspect in depth.“
- **Die Stufen sind Einstiegspunkte, das didaktische Urteil liegt bei der
  Lehrkraft** (S. 10): „The AILit Framework introduces entry points in the form
  of Learner Expectations that require educators to use their expertise to
  determine appropriate pedagogical approaches.“
- **Die Unterrichtsbeispiele sind zur Anpassung bestimmt** (S. 25): „The
  activities featured as “In the Classroom” Learning Scenarios should be adapted
  to local contexts, guidance and legislation, especially as they relate to
  social media or technology use in the classroom.“

Das Framework ist non-binding (S. 1), Anpassung seiner Inhalte ist „both
expected and encouraged“ (S. 5). Eine Schwelle, ab der eine Kompetenz als
abgedeckt gälte, sieht es an keiner Stelle vor, weder eine Mindestzahl von
Stufen noch eine x-aus-y-Regel.

## Die Lesart dieser Tabelle

Die Tabelle beantwortet für jedes der 57 Unterrichtsbeispiele („In the
Classroom“, eines je Kompetenz und Stufe) vier Fragen: a) ob ein Teil dieser
Plattform die Maßnahme unterstützt, b) wenn ja, wie, c) welcher Teil, und
d) welches praktische Szenario auf dieser Plattform das belegt. Die Maßnahme
selbst führt eine Kursleitung mit ihrer Gruppe durch; die Plattform ist dabei
das Werkzeug. Geprüft wird die Eignung als Werkzeug für die Maßnahmen, die das
Framework beschreibt.

Die Tabelle geht von der Plattform aus, wie die Tabelle vom 2026-09-02: Zeile
für Zeile steht ein Teil der Plattform (ein Modus, ein Instrument des Latent
Lab, eine querliegende Funktion) mit einer Maßnahme, die er trägt, in der
Ordnung der Plattform; die Maßnahmen, die kein Teil trägt, schließen die
Tabelle ab. Ihr Zweck ist, Help über die aktive Seite zu informieren;
Help liest sie je Seite aus `ailit_coverage.json`. Spalten von
`unterstuetzung.tsv`: `teil`, `kompetenz`, `stufe`, `unterstuetzt`, `wie_de`,
`szenario_de`, `beleg`.

Die Spalte `unterstuetzt` kennt drei Werte:

- **ja**: Die Maßnahme läuft auf diesem Teil so, wie das Framework sie
  beschreibt.
- **angepasst**: Die Kernhandlung der Maßnahme und die Art ihres Gegenstands
  bleiben, der konkrete Gegenstand ist durch einen dieser Plattform ersetzt;
  `wie_de` nennt den Ersatz. Das Framework sieht diese Anpassung selbst vor
  (S. 25, oben zitiert).
- **nein**: Kein Teil trägt die Maßnahme; `wie_de` nennt den Grund. Eine
  Maßnahme, die auf der Plattform durch eine andere Maßnahme ersetzt werden
  müsste, steht als *nein*; ebenso eine Maßnahme, die ohne Werkzeug auskommt.

**Welchen Gegenstand die Plattform halten muss.** Getragen ist eine Maßnahme,
wenn die Plattform den Gegenstand hält, um den die Maßnahme selbst geht.
Material, das ihr Wortlaut beiläufig mit erwähnt, bleibt außerhalb; ebenso die
Vorbereitung davor und die Nachbesprechung danach, die vor und hinter jeder
Maßnahme liegen, die eine Kursleitung durchführt. Ein Kriterium, das die
mitgebrachte Vorbereitung genügen lässt, trägt jede Maßnahme, die geplant wird:
der Durchgang vom 2026-09-26 hat acht Zeilen für Together daran geprüft, drei
halten unter diesem Kriterium, und die Zeilen zu den Maßnahmen, deren Gegenstand
ein Empfehlungssystem, eine Vorhersage oder ein Fall aus der Welt ist, bleiben
`nein`.

Eine Schwelle, ab der eine Kompetenz als abgedeckt gälte, sieht das Framework an
keiner Stelle vor; die Tabelle zählt darum Maßnahmen und Teile, keine Stufen.

Diese Lesart ist eine Setzung dieser Plattform, keine Vorgabe des Frameworks.
Das Framework legt das Urteil ausdrücklich in die Hand der Lehrkraft (S. 25,
S. 10); die Lesart macht offen, wie hier geurteilt wurde, damit jede Zeile am
zitierten Wortlaut nachprüfbar bleibt.

**Was bis zum 2026-09-19 hier stand.** Die Zeilen in `zuordnungen.tsv`
beurteilten, ob die Plattform selbst die Handlung hervorbringt, die eine Stufe
von Lernenden verlangt; die Unterrichtsbeispiele des Frameworks kamen darin
nicht vor. Das bewertete die Plattform als pädagogischen Akteur. Diese
Lesart ist verworfen: zu bewerten ist die Eignung der Plattform als
Werkzeug für die Maßnahmen, die das Framework beschreibt und die eine Lehrkraft
mit einer Gruppe durchführt. `zuordnungen.tsv` und ihr Erzeuger
`build_ailit_coverage.py` sind entfallen; `unterstuetzung.tsv` und
`build_ailit_support.py` treten an ihre Stelle.
