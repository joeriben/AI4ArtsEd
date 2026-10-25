# ARCHITECTURE PART 37 - t2x-Flow / Assemblage

**Datum:** 2026-07-09
**Status:** Konzept + Phase 1 gebaut (t2x-Assemblage Phase 1, develop). Phase 2 (Agent für ≥2 Texte) offen.
**Ausführliche Design-Entscheidung:** `docs/DEVELOPMENT_DECISIONS.md` (2026-07-09).

## Kernidee

**Medialität ist Produkt der Transformation (Stage 2), nicht Input-Wahl.** Dieser Satz löst den t2x-vs-Medialität-Konflikt.

Man wählt nicht "mach ein Bild"; das Medium entsteht aus der pädagogischen Verwandlung des Prompts. Die 4-Stage-Architektur bleibt dabei UNVERÄNDERT — es ist eine *Umverteilung*, kein Umbau.

## Motivation

Es geht um eine **Haltung zur Medialität**, nicht um UX-Bequemlichkeit. Indem das Medium NICHT vorgewählt wird, wird der okulare Default (Bild als unmarkierte Norm) im Funktionieren sichtbar und befragbar — dieselbe Bewegung wie bei den Latent-Lab-Eingriffen (die Norm wird im Funktionieren sichtbar gemacht, nicht behauptet).

Medialität ist relational gedacht (N/Ä/M als Differenzrelationen, borromäisch verknüpft); die Plattform soll das nicht in eine sequentielle text→bild-Pipeline kollabieren.

## Gebrauchsmuster

- **Ambiente Medien-Inferenz:** Man schreibt und denkt im Prompt; das Medium wird inferiert und ambient angezeigt (Mediensymbole leuchten, mehrere zugleich möglich) — nach demselben Muster wie Safety: Catchword + kleines lokales LLM, ständig an der Inputbox. Steuerung über den Prompt; versteckte Overrides (Klick = exklusiv, Langklick = Modell-Bubbles). Modellwahl automatisiert und kuratiert — die Kuratierung entscheidet die *Vorauswahl*, nicht die *Erreichbarkeit*: seit 2026-08-12 stehen auch die vier Bild-Eingang-Routen in der Liste hinter dem Langklick und sind von Hand wählbar — **ohne Bedingung**. Zuvor standen sie durchgestrichen da, solange weniger Bilder im Kreis lagen als `minImages` (1, für die Fusion 2), und der Startknopf ging dunkel dazu. Das ist zurückgenommen: **die Fläche verweigert keine Generierung — sie findet immer etwas zu generieren**. Trägt das Material die Wahl nicht, wird die Wahl von Hand vom Auto-Modus überschrieben: wer kein Bild in den Kreis legt und Qwen Edit wählt, bekommt das Modell, das die automatische Route ohnehin gewählt hätte, und der Kasten nennt es. Dasselbe für die Fusion mit einem statt zwei Bildern (→ i2i) und für HeartMuLa ohne geschriebene Zeile (→ Stable Audio, das Material wird gelesen). **Genau eine Route ist ausgenommen, und nicht aus Vorliebe: 3D hat überhaupt keinen Textweg** — nachgeben hieße dort, das Medium aufzugeben. Also macht der Lauf erst das Bild (SD3.5, mit einer eigenen Adaption, denn die `optimization_instruction` der 3D-Config sagt ausdrücklich „No text optimization needed — the image IS the input"), wirft es wie jedes andere Artefakt auf den Tisch und macht das Mesh daraus (`noOtherPath` in `IMAGE_INPUT_ROUTES`, Kette in `finishRun`, genau eine Ebene tief — das Modell, das ein Bild macht, braucht keines). Die Lauf-Karte nennt dabei erst Stable Diffusion, dann Hunyuan3D. **Die Wahl bleibt stehen** — sie ist nicht verworfen, sie greift, sobald das Material sie trägt; die Markierung „deine Wahl, sie bleibt bestehen" steht dann aber am Medium und nicht über einem fremden Modellnamen. Eine Wahl von Hand wird auch ausgeführt — vorher verwarf die Lesung sie und beschrieb das Material. Verworfen ist die Gegenrichtung als ALLGEMEINE Regel: für jedes gewählte Modell das fehlende Eingangsbild zu erzeugen. Nicht jede Modellwahl von Hand braucht eine solche Entsprechung. Wer Qwen Edit ohne Bild wählt, bekommt kein gebautes Bild zum Bearbeiten, sondern die automatische Route. **Nicht wieder aufmachen** — außer eben dort, wo es keine andere Route gibt.
- **Fluss ist Oberfläche:** Feature-Vues als Fluss-Karte auf einem Screen (Überblick + Zoom in einen Knoten mit großer Detailfläche), statt Scroll-Flow. Container-Geste = feste Panel-Bühne (berechenbare Modul-Fläche).
- **Assemblage:** mehrere Texte kombinierbar in den Rollen *Material* vs. *Perspektive* — die Komposition ist das Werk; bei ≥2 Texten entscheidet ein Agent die Rolle (Phase 2).

## Phase 1 (gebaut, deterministisch)

- Bild-Anzahl → Config-Routing (t2x / i2i / i2v / mi2x; `qwen_2511_multi` verlangt mindestens 2 und nimmt bis 3 — der Backend-Adapter käme mit einem Bild zurecht, aber die `optimization_instruction` der Config ist unbedingt mehrbildig und schriebe „verschmelze diese Bilder" für ein einzelnes).
- Die vier Bild-Eingang-Routen stehen seit 2026-08-12 in EINER Tabelle (`IMAGE_INPUT_ROUTES` in `useMaterialRouting.ts`): Medium, Anzeigename, Kapazität und Übergabeform. Vorher standen dieselben vier Configs in vier Tabellen und noch einmal in den Zweigen von `resolveRoute`; eine fünfte, die nur in einige eingetragen wird, scheitert dort lautlos.
- Medium post-Interception bestimmt und geklemmt; "?"-Marker bei Unklarheit.
- Freier I-Prompt (`user_defined`).
- **Der Sketch fällt auf den Tisch (seit 2026-08-12).** Bild, Video und Klang fielen nach dem Lauf als Material auf die Fläche, Code nicht — er stand in der Ausgabebox und war mit ihr weg. Jetzt fällt er als `AsmItem.kind === 'code'`: Code in `text`, Laufzeit in `codeKind`, vorne ein Standbild. Das Standbild kommt aus einem unsichtbaren `srcdoc`-Rahmen (`lib/sketchFrame.ts` mit `captureId`), der den Sketch 1,5 s zeichnen lässt, `canvas.toDataURL()` per `postMessage` hochgibt und wieder abgeräumt wird; die Seite nimmt es nur an, wenn sie genau dieses Bild angefordert hat, verkleinert es auf 240 px JPEG (sonst überschreitet das Brett die `sessionStorage`-Quote) und verwirft eine leere Leinwand. **Nur p5.js** — Tone.js hat nichts zu zeigen, und ein Sketch, der ein fremdes Bild lädt, macht die Leinwand unlesbar; dann bleibt der Name der Laufzeit stehen.
- **Text als sechstes Medium (seit 2026-08-12).** Es ist das eine Medium, das die Fläche NICHT erschließt: `CATCHWORDS.text` ist leer, also kann es weder leuchten noch `primary` gewinnen. Gewählt bedeutet es, dass der Lauf das Material im Kreis liest, statt etwas zu machen — ein Stück wird beschrieben, zwei werden verglichen, mehr werden nacheinander gelesen. Hinter dem langen Druck stehen an der Stelle des Modells die fünf **Deutungsrahmen**, die `IMAGE_ANALYSIS_PROMPTS` in `config.py` schon trug und die bis dahin `/direct` und der Bildvergleich in Compare (`views/compare/vlm_analysis_comparison.vue`) erreichten, die Fläche aber nicht: strukturale Bildinterpretation (Jörissen/Marotzki 2009, Voreinstellung), Ikonologie (Panofsky), Ikonik (Imdahl), ethisch, dekolonial. Der gewählte Rahmen geht als `frame` an `/api/media/analyze/image` und an `/api/media/analyze/compare`; **`/api/media/analyze/av` kennt ihn nicht** — die Rahmen sind Methoden der Bildinterpretation, für Klang und Video gibt es keine. Eine Lesung, die von selbst zustande kommt (Material allein, nichts gewählt), läuft weiter ohne Rahmen. Die Namen der fünf Rahmen kommen aus `compare.vlmAnalysis.perspectives.*` — dieselbe Methode heißt plattformweit gleich, in allen sechs Sprachen. `route` reicht einen Rahmen nie als `pinnedConfigId` weiter — sonst stünde ein Analyse-Schlüssel als Output-Config in Stage 4. Liegt nichts zu Lesen im Kreis, sondern nur ein Satz, dann **macht** der Lauf seinen Gegenstand: dieselben Worte gehen an das Bildmodell des Mediums, und der Rahmen liest, was dabei herauskam. Auch das Lesen fängt also mit etwas an, das die Fläche selbst hergestellt hat.

## Die Adaption bestimmt die Länge des Klangs

**Datum:** 2026-08-12. Die Adaption des Klang-Laufs im Fluss erzeugt die
Längenangabe selbst mit.

Eine zufallende Tür und ein Musikstück sind nicht gleich lang. Vor diesem Tag
waren sie es: jede Ausgabe von Stable Audio 3 im Fluss war exakt so lang, wie
die Vorgabe der Config sagte, unabhängig davon, was beschrieben wurde. Die Länge
ist aber nichts, was die Oberfläche wissen kann — sie steht in dem, was die
Adaption gerade geschrieben hat. Also schreibt die Adaption sie mit.

Die `optimization_instruction` in
`devserver/schemas/chunks/output_audio_stableaudio_diffusers.py` verlangt als
**letzte Zeile, allein**, die Form `DURATION: <ganze Sekunden>`, zwischen 10 und
240, entschieden an dem, was gerade gemacht wird: ein einzelnes Ereignis ist in
Sekunden vorbei, eine Atmosphäre braucht lang genug, um nicht wie eine Schleife
zu klingen, ein Stück braucht lang genug, um eine Form zu haben.

`_take_duration()` nimmt diese Zeile **vom Prompt herunter**, bevor er ans
Modell geht — sie ist eine Anweisung an diesen Chunk, kein Klang, den irgendwer
rendern soll. Gelesen wird tolerant (`**DURATION:** 45 seconds`, `dauer: 90
sek`, `- length = 33s`, Dezimalkomma), aber **nur** als letzte nicht-leere
Zeile: Prosa über eine Dauer bleibt Prosa und bleibt im Prompt. Werte außerhalb
10–240 s werden geklemmt und geloggt — der GPU-Dienst klemmt sonst still.

Zwei Belege, beide am 2026-08-12 gemessen:

- **Die Zeile überlebt Stage 3.** Der Weg ist Adaption → Stage 3 (Übersetzung +
  Safety) → Stage 4. Über `/api/schema/pipeline/translate` gemessen: zwei
  deutsche Prompts kamen übersetzt zurück, `DURATION: 12` und `DURATION: 90`
  wortgetreu erhalten.
- **Die Zahl kommt am Modell an.** Gleicher Prompt, Seed 12345: 12 s → 289 688
  Bytes, Config-Vorgabe 47,6 s → 1 144 206, 120 s → 2 881 453, 240 s →
  5 761 610.

Der Deckel dazu ist `STABLE_AUDIO_MAX_DURATION` in `gpu_service/config.py`, am
selben Tag von 120 auf 240 gezogen, dazu `max_duration` in
`stableaudio_open.json`, `stableaudio_music.json` und `stableaudio_sfx.json`.
`devserver/tests/test_stable_audio_duration.py` hält Parser, Rahmen und die
Kopplung an diesen Deckel fest — `DURATION_MAX_SECONDS` darf nie mehr versprechen,
als der GPU-Dienst rendert.

Wer die Länge schon kennt, ist nicht betroffen: die Kette der Cover-Band-Seite
(PART 38) ruft keine Adaption auf. Sie schreibt sich die Zeile selbst ans Ende
ihres Textes, mit der Länge der Aufnahme — so kann eine Zeile, die zufällig in
Lyrics oder Tags steht, die Länge nicht an ihrer Stelle entscheiden: gelesen wird
die LETZTE, und das ist ihre.

### Was drei Prüfläufe daran gebrochen haben

**Ob das Modell die Zeile überhaupt schreibt, war nicht gemessen — jetzt ist es
20 von 20.** Der Widerspruch ist echt: die Aufgaben-Anweisung
(`prompt_optimization` in `schemas/engine/instruction_selector.py`) sagt „Output
ONLY the transformed result. NO meta-commentary, NO headers, NO formatting",
während die Stil-Anweisung dieses Chunks eine Zeile in fester Form verlangt.
Welche das Modell befolgt, entscheidet, ob es das Ganze gibt. Gemessen am
laufenden Backend über `/pipeline/optimize`, zehn Prompts in de/en/tr/ko/uk/fr,
zwei Durchgänge: **jeder** Lauf endete auf `DURATION: <Zahl>`, in allen Sprachen
in der englischen Form.

**Der Parser hat sich an Ausgaben gebrochen, die ein Modell wirklich schreibt.**
Jede dieser Eingaben hat vorher zweifach geschadet — die Länge verworfen UND die
Anweisung als Text an das Audio-Modell durchgereicht: eine schließende Zeile
hinter der Längenzeile (```` ``` ````, `---`, `***`, ein Anführungszeichen), zwei
Längenzeilen hintereinander, `DURATION 45` ohne Doppelpunkt, `~45`. Dazu ein
Vorzeichenfehler eigener Art: `1,200` wurde als 1,2 gelesen und auf den BODEN
geklemmt — die längste Anfrage, die ein Modell stellen kann, wurde zum kürzesten
Klang, den die Plattform rendert. Alle sieben Formen stehen als Testfälle in
`devserver/tests/test_stable_audio_duration.py` (29 Tests).

**Ein Ausbleiben der Zeile war unsichtbar.** Ein Lauf, in dem die Adaption die
Vorgabe der Config wählte, und einer, in dem sie gar keine Zeile schrieb, hinterließen
dieselbe Spur. Der Chunk sagt beides jetzt im Log, sonst ist die Trefferquote im
Betrieb nicht messbar.

**Die Akte hielt die Länge nirgends fest.** Die Metadaten des Audio-Eintrags
trugen Config, Backend, Format und Seed — nicht die Länge. Solange die Länge aus
der Config kam, beantwortete die Config die Frage; seit die Adaption sie pro Lauf
wählt, beantwortet sie niemand mehr. `duration_seconds` steht jetzt in den
Eintrags-Metadaten.

### Der Deckel gilt nur dort, wo das große Modell liegt

Gemessen an den Modelldateien: SA3 **medium** rendert 380,4 s, die kleinen
Music-/SFX-Modelle exakt **120,00 s** — und welches geladen wird, entscheidet die
Karte (`gpu_service/services/stable_audio_model.py`, Schwelle 50 GB VRAM). Der
Entwicklungsrechner hat 96 GB und lädt medium; die Karten, für die ausgeliefert
wird, liegen darunter und laden klein. `_aligned_sample_size` kürzt auf den
Deckel der geladenen DATEI und meldet nichts: eine Anfrage über 240 s kam dort
als 120 s zurück, mit einer Quittung, die 240 sagte.

Geändert: der konfigurierte Deckel wird beim Laden mit dem der Datei geschnitten
(`min(STABLE_AUDIO_MAX_DURATION, sample_size / sample_rate)`), ein Kürzen steht
als Warnung im Log, und die Route meldet `duration_seconds` als das, was erzeugt
wurde, dazu `requested_duration_seconds` als das, was verlangt war. Gemessen:
300 s angefragt → `240.0` gemeldet, im Log „300.0s requested, this model tops out
at 240.0s"; 240 s angefragt → 42 336 044 Bytes wav, was bei 44 100 Hz, Stereo,
16 Bit exakt 240,0 s sind.

**Offen, und so festgelegt:** auf einer Karte unter 50 GB bleibt die längste
Ausgabe bei 120 s. Das Versprechen „bis zu vier Minuten" hält dort nicht — jetzt
sichtbar statt still.

## Belege: was eine Perspektive nachgeschlagen hat

Rund 28 Interception-Konfigurationen tragen `meta.wikipedia: true`. Bei ihnen
schreibt das Modell beim Lesen Marker in seinen eigenen Text; die Engine löst
sie gegen Wikipedia auf (Whitelist `*.wikipedia.org`, Opensearch + Page Summary,
Cache 3600 s) und legt das Ergebnis dem nächsten Durchgang derselben Perspektive
vor. Bis 2026-08-12 blieb das unsichtbar: `execute_pipeline_streaming` sendete
`wikipedia_lookup` auf denselben Strom, den die Fläche für die Interception
ohnehin offen hält, und niemand hörte zu.

Jede Fundstelle liegt jetzt als eigene Karte unter dem Kreis.

- **Der Suchbegriff kommt von der Perspektive, nicht von der Plattform.** Die
  Karte zeigt also, wonach *diese* Perspektive gesucht hat.
- **Fehlschläge bekommen ebenfalls eine Karte.** Die Dokumentationsseite
  verspricht, dass sichtbar wird, was gesucht wurde UND was nicht gefunden
  wurde; die Karte ist nach dem Wegfall der Verwandlungs-Modi der einzige Ort,
  an dem das noch steht.
- **Ein Beleg ist kein Material.** `zoneItemIds` nimmt `kind === 'source'` aus.
  Ohne diese Ausnahme würde eine Quellenkarte im Kreis das Zonen-Gesetz allein
  auslösen — der Kreis wäre die ganze Lesung, alles außerhalb fiele weg, und
  nichts auf dem Schirm sagte warum.
- **Der Text war schon gelesen.** Die Karte ist keine Option, die man noch
  wählen könnte; sie zeigt, was ohnehin in die Lesung geflossen ist. Das trägt
  die Beschriftung selbst (`x2xFlow.sourceText`), nicht nur ein Code-Kommentar.
- **Ungeprüft.** Der abgerufene Text geht ohne Prüfung durch die Sicherheitskette
  auf den Schirm. Das ist der erste Pfad auf dieser Fläche, für den das gilt —
  offener Punkt, siehe `docs/devserver_todos.md`.

## Die Kennzeichnung auf der Rückseite

Unter dem Modell steht seit 2026-08-15 eine Zeile „AI marking". Sie ist keine
Wiedergabe unserer eigenen Notizen: Der Server öffnet die ausgelieferte Datei
und meldet, was darin steht (`read_media_disclosure`, Part 36). Gefunden →
`aiMarkYes`, nichts gefunden → `aiMarkNone`; die Maschinenzeile („AI-generated,
model=…, date=…") steht im Tooltip, damit die Karte in jeder Sprache spricht.
Fehlt die Datei, fehlt die Zeile — über Ungelesenes wird nichts behauptet.
Gefragt wird pro Karte (`?type=<medium>`), erst wenn eine Rückseite aufgeht.

## Verwandte Parts

- PART 01 — 4-Stage Orchestration Flow (bleibt unverändert)
- PART 26 — Canvas-Workflow-System
- PART 29 — Safety-System (Vorbild für die ambiente Inferenz)
- PART 32 — Dialogic-AI-Persona (Resona)
- PART 38 — Cover-Band (derselbe SA3-Chunk, ohne Adaption)
