# Changelog

Alle nennenswerten Änderungen an der AI-Lab-/Werkraum-Plattform werden in dieser
Datei je Release dokumentiert. Format: [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung: [SemVer](https://semver.org).

Begonnen am 2026-09-19 gemäß Release-Plan zum Projektabschluss (M5.4).
Startstand: `develop` @ `0dd083b7`. Änderungen vor dem Startstand sind über die
Commit-Historie nachweisbar.

## [Unreleased]

### Geändert

- Code-Kommentare, Dokumentation und das Entscheidungsprotokoll
  `docs/DEVELOPMENT_DECISIONS.md` nennen keine Personen, zitieren keine
  Gespräche und verweisen auf keine Entwicklungssitzungen mehr. Skripte leiten
  das Repository aus ihrem eigenen Ort ab; Dokumentation trägt keine Pfade
  einer einzelnen Installation.
- `docs/COPY_RULES.md` trägt die Regeln zur Label-Grammatik, zur Anrede und zu
  den Vergleichsflächen, auf die die i18n-Gates verweisen.

### Hinzugefügt

- `scripts/public_export/` erzeugt die öffentliche Fassung des Repositories
  aus einer Ausschlussliste. `devserver/tests/test_public_surface_clean.py`
  prüft die mitgelieferten Dateien auf Personenzuschreibungen,
  Sitzungsverweise und private Pfade (Gate 10 im Pre-Commit-Hook).

## [v2.0.0-beta.1] — 2026-10-01

Erster getaggter Release nach dem Release-Plan zum Projektabschluss (M5.4),
Beschluss vom 19.09.2026 (Beta-Releases plus Change-Log). Stand von
`develop` @ `8d170330`. Änderungen vor dem Startstand sind über die
Commit-Historie nachweisbar.

### Hinzugefügt

- Übergabedokumentation als Gerüst: Systemüberblick, Betrieb,
  Konfiguration, genAI-Schnittstellen, bekannte Einschränkungen für die
  Nachnutzung nach Projektende (9fc28c17); dazu die Sichtung des
  Safety-Systems als eingefrorener Stand vom 2026-09-19 (7280bc30).
- Jede Output-Konfiguration benennt das Backend, das ihr Medium erzeugt; ein
  Test prüft die Angabe (9ae220ca).
- Der Help-Text kennt Flow, Canvas, Contesting und Together (07a760fa); die
  Plattform wird als Werkzeug für die 57 Classroom-Measures beurteilt, und Help
  nennt sie auf jeder Seite, die eine trägt (3b7190a4).
- Die Fusion Workbench fegt ein Fenster und einen Eingangsblock; der Zeitplan
  einer geplanten Fusion akzeptiert beides als Angabe (a7f70cd1, 134e1455).
- Ein Latent-Lab-Lauf meldet, welches Backbone gelaufen ist; die
  Fähigkeiten-Angabe nennt es vor dem Lauf (1e5b581e).
- Encoder-Fusion: der gepoolte Vektor ist eine Einstellung, zwei Felder in der
  Zeile (7675c02a).
- Die Spaltenüberschriften der Übersichtskarte stehen bei jeder Fensterhöhe auf
  ihren Spalten (4831eea1).
- Language Understanding: die angehakten Bildmodelle laufen als Zeilen — jedes
  Modell malt in jeder Sprachspalte, und über jeder Spalte steht die
  Übersetzung, die tatsächlich zum Modell ging (7b91d0c2).
- Der Flow trägt das Werkzeug von Together, mit dem Leeren der Leinwand; dasselbe
  unveränderte Objekt im Ring stößt die Kette nicht nochmals an (6a738f4d,
  ebf1931f, 3784b15f, 07386244).
- Der Flow legt LoRAs auf den Tisch, gelesen aus einem Register; eine gelegte LoRA
  startet bei 80 Prozent, die Wahl zeigt die eigenen Trainings des Kontos, und
  die Nachricht nennt die LoRAs auf dem Flow (8516d097, 9d504e60, bc67fc07).
- Das Drücken und Halten bedeutet eine Sache, bei einer Dauer: 450 ms zeigen,
  was hinter einer Fläche liegt — die Infokarte, die Rückseite, die
  beschriebene Seite eines Presets — mit einem Haarlinien-Ring unter dem Finger
  (5c5522fd); die Merkkarte auf Together gibt die Geste auf und trägt einen
  eigenen Knopf.
- Der LoRA-Wähler steht im Blasenring: die Adapter gruppieren sich nach Art auf
  einem Kreis, der sich nach Umfang richtet, und die Einstellungen führen die
  Art je Reihe (17dc3f2a); die Adapter-Datei sagt selbst, welches Modell sie
  trägt, die Spalte im Reiter „LoRAs“ ist nur noch lesbar (e7ad7b64).
- Die Favoritenleiste steht auf dem Panel der Plattform: eine gehaltene Karte
  zeigt Instrument, Prompt, Parameter, Zeit und die KI-Kennzeichnung auf der
  Rückseite, die Stern-Aktion trägt die eigene Reihe — Stufe 3 von drei
  (a3675027, 22b85faa).
- Der LoRA-Trainingsleitfaden sagt, wo eine trainierte LoRA angeboten wird, und
  der Hilfe-Text kennt die LoRAs auf dem Flow (cd7f7233, 99af2f53).
- Piper wird nach Sprache, Stimme und Sprecher gewählt; unter der Wahl steht,
  wer aufgenommen wurde (0780d1f8).
- Die Karten des Flow-Bretts antworten auf Klick mit der Vergrößerung, auf
  Halten mit der Daten-Rückseite; die Scheiben von Perspektive und LoRA
  öffnen auf Klick ihre Box und sagen über die InfoCard, was sie halten
  (3612dd11).
- Kurse: Orte mit eigenen Codes ersetzen den Kurs-Schlüssel, die
  Teilnehmerliste und den Beitrittscode — ein Kurs hält Orte, je Gerät eins,
  und kein Teilnehmenden-Konto trägt einen Namen (a86b670e).
- Gemini 3 Pro Image läuft nur, wo der Mammouth-Account einen gültigen
  Schlüssel und nicht aufgebrauchtes Guthaben hält; die Einstellungen nennen
  seine Route (7e7bb104).
- Zwei wiederholbare i18n-Gates halten die Textdisziplin im pre-commit: Gate 6
  fängt direkte Anreden in den Werten von de.ts und en.ts (Ausnahmen nur per
  Wortlaut-Kommentar, bewusst ausgeklammerte Bestände gegen einen eingefrorenen
  Stock), Gate 7 fängt assertives „Wort für Wort“ und die
  Bauanleitungs-Metapher; kontrastive Negation bleibt zulässig (b8b3ff6d,
  b06df2a1).
- Die Codes der Kursplätze: unbekannte Codes werden je Netzwerkadresse gezählt,
  und nach vierzig verweigert der Login für eine Weile; „Code ersetzen“ fragt
  nach, und eine offene Seite merkt, wenn die Anmeldung ihres Platzes beendet
  ist (10c39e88, a9e6ec26).
- Die Ansprachen der dreizehn Vergleichs- und Lab-Flächen nennen den Vorgang
  anrede-frei — der Stimmen-Vergleich nennt das Dropdown und das freie Feld,
  der Sprach-Vergleich nennt die Modell-Reihen wieder, und die
  Attention-Erklärungen tragen keine Bauanleitungs-Metapher mehr
  (487dd67a…847a1496, 8ab45b55, b06df2a1).
- Gemini 3 Pro Image beurteilt drei Budgets, wie LiteLLM sie prüft; ein
  abgeschaltetes Modell lässt an festen Momenten eine Wahl (1ad964ab).
- Zehn zentrale Presets nach dem Eigenschaften-Katalog ergänzen die Liste; jedes
  benennt die angesprochene Eigenschaft, die Fläche, die sie prüft, und die Quelle
  in seinem Kommentar (f93eb647).
- Instrumenten-eigene Paare und Tripletts für die drei Spezial-Instrumente, jedes
  benennt Eigenschaft und Fläche (e2fde759).
- Die Enzyklopädie nennt die Forschung hinter den zentralen Presets (fde4fc1e).
- Die Composable Diffusion wählt dieselben Begriffe wahlweise im Denoiser oder im
  Embedding (0296c448); das Paar „Apfelbaum“ / „Äpfel“ zeigt, was ein Gewicht im
  Embedding entscheidet (4e5e80b6); die Interpolation läuft wieder über die
  Konzepte hinaus (e0133b86); der Gloss unter Combination sagt, was jeder Ort tut
  (25b643e5).
- Die Zulassung der Stufe A prüft jedes hochgeladene PDF deterministisch vor
  Speicherung und Einreihung — Form, Seitenzahl, eingebettete Dateien, ein
  Hash-Index gegen die doppelte Analyse und ein Klartext-Scan, ohne Modellkosten
  (a29fc07f).
- Die Szenen-Kapsel-Pipeline verdichtet ein hochgeladenes PDF zu visuellen
  Szenen-Kapseln; das Roh-File überlebt den Job nicht, und die Sicherheitsprüfung
  reitet auf demselben Modellruf (c07a56a5, 5fc35c47). Der Dokument-Weg trägt ein
  eigenes PDF-Zeichen (ca212850), der Intake liegt im Flow, nicht im Resona
  (9ba704af), und das Plus benennt die Dokument-Option einsprachig (bab48765).
- Vier Qualitätsstufen stehen gesetzt — Qwen Image Edit Lightning 3, Qwen 2511
  Multi-Image Fusion 4, Stable Audio 3 3, Hunyuan3D-2 2 —, der Name des
  Wan-Modells verliert „(ComfyUI)“ in allen zehn Sprachen, und /chunk-metadata
  verlässt die API (36c1d709, 28272857).
- Der Dimension Explorer misst mit zwei nummerierten Dreiecken von der Messleiste
  aus (2bf83a74); Bild B steht rechts, von ▶ 2 vor der Mischung gemacht
  (1579d4c6); ▶ 2 misst zuerst am gewechselten Encoder (b0510dea); die
  Rang-Auswahl öffnet bei 13-1156 und wartet auf die Messung des gezeigten
  Encoders (d8e84039); ▶ 1 misst auf jedem Encoder zugleich, ein Wechsel des
  Encoders läuft nichts (2f6c6171).
- Die Anbieter-Tabelle benennt, wie ein Konto gelesen wird (account_api: litellm,
  openrouter); der Reiter API-Verwaltung zeigt je Anbieter einen Block (6a2cee27).

### Geändert

- Code-Kommentare nennen keine Initialen mehr (9c85dad7, 310486c9 u. a.).
- i18n-Batch 2026-09-11: 23 Schlüssel in neun Sprachen übersetzt, vier tote
  entfernt; die neun Sprachdateien stehen wieder auf `en.ts` (4b102577,
  c19eaf2b).
- Die Decomposition verlässt die Plattform; ihr Forschungspfad bleibt erhalten
  (02492390).
- Bad Picture und Good Picture tragen ihre Sprechblase (743de888, 8a956f9b,
  38bfbae8, b3dc04ad).
- Die drei Komposit-Platten tragen die KI-Herkunftskennzeichnung auf der Seite,
  nicht nur auf der Platte (a47e6d57).
- Die Architektur-Dokumentation PART 12 und PART 21 beschreiben den Baum und
  die Navigation, die es gibt: die archivierte Auswahlseite und ihre
  Konfigurationskacheln sind fort (a995410e, 733f4250, 1b96ae78, 6ccf0b72).
- Die Markierungs-Dokumentation zitiert den Wortlaut des Artikels 50 der
  KI-Verordnung (EUR-Lex, abgerufen 2026-09-22) und sagt keine eigene
  Einschätzung der Plattform mehr (1c27fb2a).
- Die Anweisungen für den Übersetzungs-Agenten sagen, dass eine gemessene Zahl
  hinfällig wird, wenn ihr Satz neu übersetzt wird (278a5f81).
- Das Mistral-Set läuft auf GLM 5.3 (zai-glm-5-3); ein Modell, das nicht
  sehen kann, fragt über look_at_image ein zweites Modell nach dem Bild
  (3ae43db3).
- Die Safety-Prüfkette läuft auf einem Klassifikator, Shieldstral 1.0 3B, an
  Stelle dreier Modelle und eines Cloud-Verdicts; eine Anfrage ohne Score
  blockt (494a659c). Beschreibung, Entwurf, Review und Vergleich des
  Safety-Systems samt Recherche aktueller Safety-Modelle sind dokumentiert
  (3bb61c2a), ebenso Befunde und Vorschlag zum Rückweg zum GPU-Dienst mit
  der Entscheidung vom 2026-09-23 (b58fe158).
- Die Infokästen sind Satz für Satz nach 24 Regeln geprüft und bereinigt —
  17 Kästen, 140 Sätze, Deutsch und Englisch; die Prüftabelle liegt unter
  docs/analysis/copy/ (999a3063).
- Feature Probing heißt Dimension Explorer — der Name wechselt überall, wo
  Besucher oder Modelle ihn lesen: Liste, Titel, Diffusion-Lab-Beschreibung,
  Config-Namen in zehn Sprachen, Download-Dateinamen und Help (02d63e1a).
- Die Meta-Instruktion verliert die drei Sätze, die den Context benennen und die
  wichtigsten Elemente aufzählen sollten (12bf0a3f).
- Mistral-Verkehr läuft auf dem EU-Endpunkt; der Eintrag des Presets sagt, dass
  Zero Data Retention noch zu beantragen ist (591d6300).
- Together trägt vier der 57 Classroom-Maßnahmen, das Kriterium ist eng gefasst
  (2051e91d).
- CommonCanvas XL C trägt einen Qualitätsstern, SD 3.5 Large Turbo behält zwei
  (d4bf33fa).
- i18n: die Work Orders 2026-09-27-M, -N und -L des Dimension Explorer sind
  übersetzt, die Batch-Abstimmung für de, tr, ko, uk, fr, es, he, ar und bg
  eingebracht (330732ca, ebbd6ec7, 7c4c1596).
- Der pre-commit-Haken prüft die Flow-Specs gegen das gestellte Frontend
  (3552593a).

### Behoben

- Das OpenRouter-EU-Preset in `hardware_matrix.json` nennt keine Tilde-Aliase
  mehr, die der EU-Katalog nicht führt: alle neun Rollen auf
  `openrouter/z-ai/glm-5.3` (0dd083b7).
- FLUX.2 läuft wieder unter transformers 5.17 (142bcf67).
- Latent Lab: SD 3.5 Large auf jeder Karte, der nie autorisierte
  Medium-Fallback entfällt (393ac696); eine gespeicherte Sitzung trägt das
  Gerät, das sie geöffnet hat (c58a16b3).
- Der Übersetzungs-Endpoint liest das Modell des Übersetzungsschritts (d1b242de).
- Deployment: die Text-Lab-Gewichte kommen über plain HTTPS, xet aus (03bbf95c).
- Der Stage-4-Timing-Harness stoppt, statt Nullen zu schreiben (eb451896).
- Sechs Flächen zeigen wieder den Standardprompt statt seines Schlüssels
  (a3e37c54).
- Der Standard-Testprompt trägt beide seiner Sätze überall hin (1472a895).
- Ein Klick öffnet das Medium und seine Rückseite zusammen; die Vollbild-Schicht
  trägt das Panel, die Schicht des Flow geht (58f7920f, 92140701).
- Die drei Abschnitte der Entrauschungs-Archäologie stehen als Zonen unter der
  Achse, und die Achse heißt Entrauschungsschritte (5ef05054); der direkte
  Endpoint zeichnet den Lauf selbst auf und antwortet mit den Adressen der
  Frames (0d4f98f5).
- Ein Modell, das ComfyUI von der Karte nimmt, wird freigegeben statt im RAM
  geparkt: ein SD-3.5-Large-Bild ging auf der 96-GB-Karte von 322 s auf 16,2 s
  (7be63623).
- Die Entrauschungs-Archäologie reist wieder mit allen Schritt-Bildern in der
  Antwort, sodass die Achse aus dem Speicher scrubbt; der Server schreibt den
  Lauf in die benannte Sitzung, die 65–79 s dauernde Nachbereitung nach dem
  fertigen Bild entfällt (c7ae1285).
- Mean Images baut die Zeichnung auf den Kinder- und Jugendstufen von der
  ersten Karte auf auf; eine ungeprüfte Karte tritt einen Schritt später bei,
  statt die Zelle zu verstummen, und die Antwort nennt den Fall (1aa5cf42).
- Die Aufstellung „large models“ des Text-Lab trägt wieder die aktuelle
  gemischte Reihe (da8a5241).
- Der Plattform-Items-Bau behält handgeschriebene Help-Felder einzeln, statt
  sie mit der Ernte insgesamt zu verlieren; platform_items.json ist aus den
  Quellen am HEAD neu gebaut (4d3be122).
- Fehlt dem §86a-Scan des Upload-Gate sein Matcher, lehnt das Gate ab statt
  durchzulassen — wie jede andere Kategorie, mit Audit-Zeile (d6c4a9b3).
- Docling-OCR läuft unter dem GPU-Gate, nicht daran vorbei (e2cfdc81).
- Model Adaption läuft auf dem Canvas; der Generierungs-Knoten nimmt Saat,
  Auflösung und Qualität zusammen (c04525f5).
- Ein Fangwort muss ein Wort beginnen: „Karton“, „Beton“, „Farbtöne“, „Einklang“
  und „emotion“ lesen sich nicht mehr als Klang (a4103442).
- Gemma 4 12B lädt wieder, und MuQ-MuLan des Re-enactment liest wieder (5532529a).
- Bias Research läuft an einem gescheiterten Modell vorbei und benennt es; zwei
  Ursachen tragen ihre Namen (f98a551d).
- Concept Algebra: B ≠ A im Kind und in den einsamen Tripletts (c261d4c8).
- Die Output-Cards-Route liest das CHUNK_META eines Python-Chunks mit ast, statt
  die Datei auszuführen; ein meta, das kein Objekt ist, lässt nur diese eine Karte
  aus (5353189a).
- Die Seite des Flow lädt wieder: Die Uhr der Modell-Karte steht unterhalb des
  readingFrame (32fa5c7b).
- Ein Klick auf eine Perspektive antwortet sofort, das Symbol pulsiert überall,
  wo eine Perspektive den Prompt umschreibt, und der Chooser holt die Wortung
  einer Kategorie erst, wenn sie sich öffnet (8322f6ad).
- Jede Fläche, deren Auswahl ein Feld umschreibt, bietet keine
  Ganz-Kategorie-Geste mehr; das parallel laufende Vermessen des Dimension
  Explorer bleibt aus dem Commit draußen (2889c35a, d3fb5913).
- Das Grenz-Experiment des Festivals ist einem themen-freien Widerspruch
  gewichen (c76d42c8).
- Der Lauf-Eintrag benennt die Modelle, die übersetzt und geurteilt haben
  (b6a1b0b5).
- Die Übersetzung ins Englische schlägt nichts mehr nach (6a1d5cca).
- Der Reiter API-Verwaltung zeigt, was der Mammouth-Schlüssel in der Key-Datei
  ausgegeben hat (5a95f986); die zwei Übersetzungs-Rollen beanspruchen die
  Sicherheitsprüfung nicht mehr (5b141ce4).
- Das LoRA-Zeichen steht unten links am Plus und hält Karten und Bogen frei
  (a53ef474); ein Druck zieht eine Perspektiven- oder LoRA-Scheibe, ein Klick
  öffnet ihre eine Box (a52f94ca); Plus, LoRA-Zeichen und Perspektiven-Zeichen
  stehen als Dreieck, die Prompt-Box darunter, alle als Anteile der Box
  „Vorbereitung“ (2894d393).
- Die Hilfe-Maske ist so groß wie die freien Zeichen auf dem Brett (5b44beca,
  b2a063c0).
- Composable Diffusion: die Gewicht-Achse endet im Embedding bei null (8825aa0c);
  der Eintrag nimmt die Adresse des Bildes, und die Note steht an ihrem Feld
  (96e1c7ad); der Auslöser kommt zurück, wenn das Bild steht (ae6d59a1); zwei
  falsche Angaben über die Gewichte sind gestrichen (a6dfc8df).
- Das Paar des Feature Probing hält zwei klar getrennte Vektoren, keinen schwachen
  Widerspruch im Satz (17d2f624).
- Die Karten des Flow-Bretts sind wieder so hoch wie ihre Vorderseite, und eine
  Wikipedia-Karte lässt sich länger ziehen (cb08d750); ein Scheiben-Zug endet
  wieder im Kontextmenü, für jeden Zeiger (b1263c80).
- Flow: Material aus dem Plus landet wieder auf dem nächsten freien Platz
  (1a59060f); die Karte eines Dokuments wird fertig, wenn ihre Analyse durch ist,
  und Karten aus dem Plus bleiben auf der Fläche und außerhalb des Rings
  (178d179f); das Kreuz des Skizzen-Fensters liegt nicht mehr auf Done (f42f03cf);
  der Voice-Ref lässt die vier Sätze des Dokument-Intakes ankommen (d5d9f3c7); die
  Karte eines Dokuments steht während der Analyse auf dem Brett, an der Stelle,
  an der sie landete (c7658845); der zweite Name des Streifens geht mit dem Doppel
  des Intakes (11aea22d); die Kommentare des zurückgenommenen Intakes gehen mit
  ihm (61289ad5).
- Stable Audio Open 1.0 verlässt die Plattform, Stable Audio 3 tritt an seine
  Stelle und hat keinen Ausweichweg mehr: ein gescheiterter Lauf endet mit seinem
  eigenen Fehler, die Verfügbarkeit meldet das Modell selbst, und die Gewichte
  liegen in der Ablage (5b02c61b).
- SD 3.5 img2img läuft wieder unter ComfyUI 0.36: Der Router lädt das Eingabebild
  auch auf dem Workflow-Chunk-Weg hoch, mit derselben Funktion wie die übrigen
  Bildeingänge (4168aa0d).

## Geplante Releases

- `v2.0.0-beta.1` — 2026-10-01
- `v2.0.0-beta.2` — 2026-11-02
- `v2.0.0` — 2026-12-15 (Finale Version zum Projektende; danach nur Fixes
  bis 31.12.2026)