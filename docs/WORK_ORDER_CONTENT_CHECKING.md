# Arbeitsauftrag — Alters- und Inhaltsprüfung über alle Modi

**Stand: 2026-08-05; Erledigungsvermerke 2026-08-07 (A1, A3, A4, A12,
Deckel-Abschnitt, Entscheidung 1) und 2026-08-08 (A5, A11; A10 kam
unabhängig mit `d053cac0`, der auch Entscheidung 2 trägt: Kurs verschärft,
lockert nie — `open` läuft den vollen Guard-Pfad).** Zeilenanker außerhalb
der Behoben-Vermerke beziehen sich auf den Stand vor den Commits vom
2026-08-07; die Vermerke tragen die neuen Anker.

Dieses Dokument ist die gültige Beschreibung der Aufgabe.
Daneben gilt `docs/DEVELOPMENT_DECISIONS.md` als
datierte Chronik. Ältere Berichte zur Prüfkette sind überholt und werden nicht
mehr herangezogen.

Jeder Satz hier ist am Code belegt und in drei gegenläufigen Prüfläufen gegen
den Code gehalten worden. Ergänzungen folgen derselben Regel: `datei:zeile` oder
gemessen.

---

## 1. Gegenstand

Die Plattform wird von Kindern und Jugendlichen in betreuten Workshops benutzt.
Eine Eingabe wird pädagogisch verwandelt (Prompt Interception), daraus entsteht
Bild, Text, Ton, Musik, Video oder 3D.

Die Prüfung leistet drei Aufgaben:

| Aufgabe | Grundlage | Beispiel |
|---|---|---|
| Altersgerechtheit | JuSchG | Eine Zehnjährige bekommt keine Gewalt- oder Sexualdarstellung erzeugt, auch aus einer Eingabe, die harmlos aussieht |
| Personenbezug | DSGVO | Namen realer Personen bleiben von Cloud-Modellen fern |
| Verfassungsfeindliche Symbolik | §86a StGB | Wird weder erzeugt noch ausgeliefert |

Stufen: `kids`, `youth`, `adult`, `research`.

---

## 2. Wie die Prüfung heute aufgebaut ist

| Stelle | Was dort geschieht | Wo im Code |
|---|---|---|
| **Stufe 1**, Eingang | Wortliste §86a, Personennamen (SpaCy + Sprachmodell) | `stage_orchestrator.py:1059` |
| **Stufe 2**, Verwandlung | Sicherheits-Vorspann im Interception-Prompt für `kids`/`youth` | `instruction_selector.py:70-91`, angewandt `:165-166` |
| **Stufe 3**, vor der Erzeugung | Übersetzung, Wortliste §86a, ein Llama-Guard-Aufruf | `stage_orchestrator.py:1342` |
| **Nachschau** | Bildmodell beschreibt, Sprachmodell urteilt; `kids`/`youth`, Bild | `vlm_safety.py:279`, Einstieg `schema_pipeline_routes.py:2819` |

**Stufe 3 im Detail:** Die Vorlage führt die Kategorien S1–S13 (`:607`).
Gefiltert wird auf acht davon, `{S1,S2,S3,S4,S8,S9,S10,S11}` (`:1468`); S5, S6
und S7 sind ausgenommen (`:1466-1467`). Liegen ausschließlich S4 und/oder S8 vor,
geht der Fall zur zweiten Beurteilung an ein externes Modell, das die Sperre
aufheben kann (`:1479-1489`).

**Es gibt fünf Stufe-1- und Stufe-3-Varianten**, nicht je eine. Neben
`execute_stage1_safety_unified` (`:1059`) prüft der Streaming-Zweig eigenständig
(`schema_pipeline_routes.py:1902`, `:1918`, `:1920`), ebenso
`/pipeline/safety/quick` (`:2387`, `:2399`, `:2402`). Für Code-Ausgaben existiert
`execute_stage3_safety_code` (aufgerufen `:5753`).

Sämtliche Aufrufstellen in `schema_pipeline_routes.py`: `1209`, `1652`, `1902`,
`1918`, `1920`, `2362`, `2387`, `2399`, `2402`, `2840`, `2973`, `2984`, `3323`,
`4274`, `4407`, `4598`, `4639`, `5045`, `5406`, `5753`, `5771`.

---

## 3. Wie die Abdeckung heute aussieht

| Weg | Eingang | Vor der Erzeugung | Nachschau | Beleg |
|---|---|---|---|---|
| `/pipeline/generation` (der Weg, über den die Medien tatsächlich entstehen) | — | ja | Bild | `:2973`, `:2984`, `:3323`, `:4274`, `:4407` |
| `/pipeline/direct` | ja, für das Hauptfeld | ja, für fünf Felder | Bild | `:4598`, `:4639`, `:5045` |
| `/pipeline/interception`, nicht streamend | ja | ja | — | `:5406`, `:5771` |
| `/pipeline/interception`, streamend (der gebräuchliche Zweig) | §86a und Personennamen | endet nach Stufe 2 | — | Rückgabe `:5170-5173` vor `:5185`; Ablauf `:1832`. **A5 erledigt 2026-08-08:** der Zweig ruft `execute_stage1_safety_unified` statt einer privaten Kopie — damit erhält er den LLM-Fallback bei fehlendem SpaCy (die Kopie übersprang die Personenprüfung dann still) und den §86a-Kontextcheck für adult/open |
| `/canvas/execute*` | — | Stufe 3 wird übersprungen | Bild | `canvas_routes.py:779-781`, `:823`; `canvas_executor.py:728`, `:836` |
| `/api/chat` | — | — | — | Ausgabe ist Text; Route `chat_routes.py:2523` |
| `/run_workflow_stream` | — | — | — | `workflow_streaming_routes.py:28`, registriert `__init__.py:320`, reicht an ComfyUI durch `:113` |
| `/api/cross_aesthetic/*`, `/api/fusion_workbench/*`, `/api/text/*` | auf dem Weg über die Eingabefelder | — | — | Proxys: `cross_aesthetic_routes.py:26-64`, `fusion_workbench_routes.py` (`_run`; seit 2026-09-14 ein ComfyUI-Lauf statt eines Proxys zum GPU-Dienst; die vier Forschungsrouten `/decomposition`, `/position_probe`, `/delayed_kickin`, `/delayed_kickin_cumulative` darin antworten nur auf der Stufe `research`, `_research_run`), `text_routes.py:46-54` |

**Zum Verlauf im Frontend:** `text_transformation.vue:1016`,
`image_transformation.vue:673`, `multi_image_transformation.vue:878` und
`x2x_flow.vue:1628` rufen `/pipeline/interception` streamend; dieser Zweig endet
nach Stufe 2 (`:2049`). Die Medienerzeugung läuft danach über
`useGenerationStream.ts:237` an `/pipeline/generation` — mit Stufe 3 und
Bild-Nachschau. Für Text- und Bildwege ist die Kette dort also geschlossen.

`crossmodal_lab.vue` und `latent_text_lab.vue` führen ihre Eingabe über die
MediaInputBox (`MediaInputBox.vue:358`) an `/pipeline/safety/quick`; bei Befund
wird das Feld geleert. Das greift bei Blur und Einfügen und hängt am Frontend.

### Sieben Stellen, an denen die Prüfung heute anders ausgeht als gemeint

**Stand 2026-08-07: a, c, d, e und g sind behoben, dazu der Deckel-Abschnitt
erledigt; b und f stehen aus.** Die Absätze bleiben als Begründung stehen;
jeder behobene trägt einen Vermerk mit den neuen Ankern.

**a) Ein Fehler des Prüfmodells führt zur Freigabe.**
`stage_orchestrator.py:1477`:

```python
is_safe = llm_result["safe"] or len(relevant_codes) == 0
```

`_llm_safety_check_generation` gibt auf allen drei Fehlerpfaden
(`:642-644`, `:647-649`, `:658-660`) `codes: []` zurück. Damit ist der rechte
Summand wahr. `:1494` protokolliert den Lauf anschließend als `PASSED`.

> **Behoben 2026-08-07.** `_llm_safety_check_generation` trägt jetzt ein
> eigenes Feld `verdict` (`:641`, Vertrag im Docstring); ohne Urteil hält der
> Lauf an (`:1588`, `method: llm_check_failed`, Meldung
> `SAFETY_CHECK_UNAVAILABLE_MESSAGE` `:1443` — als Betriebsstörung formuliert,
> nicht als Einstufung). Die Aggregation lautet
> `is_safe = len(relevant_codes) == 0 and not llm_result["uncoded_unsafe"]`
> (`:1611`): ein „unsafe" ohne erkennbaren S-Code — auch Prosa-Kategorien wie
> „Violent Crimes" (`parse_llamaguard_verdict` `:938`) — blockt (`:729`),
> statt vom Relevanzfilter freigegeben zu werden. Der Text an Llama Guard
> läuft gefenstert: 2400-Byte-Fenster (harte Obergrenze der Tokenzahl),
> 300 Byte Überlappung, ab 33 Fenstern fail-closed (`:610-638`). Der
> Stufe-1-adult-§86a-Kontextcheck nutzt denselben Weg (`:1229`); die
> Legacy-Lesart „unparsebar → safe" liegt nur noch im toten
> `execute_stage1_safety` (siehe „Aus den Prüfläufen" unten). Belegt mit einer
> Matrix aus 13 Guard-Ausgaben plus Fenster-Aggregation, drei gegenläufige
> Prüfläufe am Diff.

**b) `/pipeline/direct` prüft ein Feld von zehn.**
Stufe 1 (`:4598`) bekommt `prompt`. Die Route liest daneben `negative_prompt`
(`:4539`), `prompt_b` (`:4544`), `prompt_c` (`:4549`), `concepts` (`:4555`),
`cells` (`:4559`), `clip_l_prompt` (`:4560`), `clip_g_prompt` (`:4563`),
`decomp_t5_prompt` (`:4566`) und reicht
sie über `custom_params` (`:4707-4790`) an den Chunk. Stufe 3 (`:4639`) deckt
`prompt, prompt_b, prompt_c` und die Konzept-Prompts
(`:4625-4636`) ab, und nur bei `kids`/`youth` (`:4621`). `negative_prompt`,
`clip_l_prompt`, `clip_g_prompt`, `decomp_t5_prompt` und die Zell-Prompts
erreichen die Text-Encoder ungeprüft. `decomposition.vue:471-478` schickt bis zu
neun freie Zell-Prompts (`:388-399`); `/decomposition` ist über die URL auf jeder
Stufe erreichbar, da `requiresAdvanced` (`router/index.ts:246`) an keiner Route
gesetzt ist.

Nachtrag 2026-09-19: Die Fläche Decomposition ist entfernt (Reiter,
Route `/decomposition`, Config `decomposition`, beide Chunks); der Direct-Endpunkt
(`/api/schema/pipeline/direct`) liest `cells`, `clip_l_prompt`, `clip_g_prompt`,
`decomp_t5_prompt` und die Bänder nicht mehr. Zell-Prompts erreichen die Encoder nur
noch über `/api/fusion_workbench/decomposition`, das allein auf der Stufe `research`
antwortet.

**c) Die T5-Erweiterung läuft nach den Prüfungen.**
`:4661-4670` erzeugt aus dem geprüften Text neuen, maschinell erweiterten Text,
der als Konditionierung dient. Er entsteht nach Stufe 1 und Stufe 3.

> **Behoben 2026-08-07.** Die Erweiterung entsteht jetzt vor Stufe 3
> (`schema_pipeline_routes.py:4638`) und läuft im Sammelaufruf mit
> (`:4661`, `t5_prompt` in `all_prompts`).

**d) Ein Feld im Request überspringt die Stufen 1 bis 3.**
`:5208` liest `stage4_only` aus dem POST-Rumpf, `:5370` überspringt damit die
Stufen 1 bis 3, `:5740` die Stufe 3. Der GET-Zweig (`:5151-5158`) führt das Feld
nicht.

> **Behoben 2026-08-07.** Das Feld wird nicht mehr aus dem Request gelesen;
> `stage4_only = False` serverseitig (`:5236`). Kein Frontend sendete es noch
> (`services/api.ts:66` führt nur den Typ; einziger Setzer lag in einer
> `.DEPRECATED`-View). Eine serverseitige „schon geprüft"-Herleitung kommt
> erst mit dem Prüfwert aus A6.

**e) Eine Route liest die Stufe aus dem Request.**
`workflow_streaming_routes.py:42`: `safety_level = data.get('safetyLevel', 'research')`.

> **Behoben 2026-08-07.** Die Stufe kommt aus der Server-Policy:
> `from config import DEFAULT_SAFETY_LEVEL` zur Aufrufzeit (`:46-47`;
> Importzeitpunkt wegen laufzeit-änderbarer Settings, `config.py:100`,
> `settings_routes.py:1603`). Sie wirkt dort real auf Filter-Nodes und
> Negativ-Terme (`workflow_logic_service.py:466`, `:493`).

**f) Die Nachschau umfasst Bild.**
Für Text liegt sie als Platzhalter vor (`:5603-5606`, `# TODO: Implement Stage 3
safety check on result.final_output here`), und `:5604` protokolliert bereits
einen Prüflauf. Für Ton, Musik, Video und 3D ist sie zu bauen; Musik entsteht
unter anderem über `x2x_flow.vue:2129`. Liegt kein Bild vor, gibt die Funktion
`(True, '', '')` zurück (`:2836-2838`). Im Canvas wird der Medientyp aus einem
Teilstring der Config-Kennung erschlossen (`:3808-3816`), sodass Video-, Ton- und
3D-Knoten die Nachschau nicht erreichen.

**g) Der Deckel auf dem Urteilsaufruf schneidet das Urteil weg.**

Der Urteilsaufruf der Bildnachschau (`vlm_safety.py:185`) setzt
`max_tokens: 200`. Das urteilende Modell (`mammouth/gemini-3.6-flash`) denkt vor
der Antwort, und dieses Denken zählt gegen dasselbe Budget.

**Im Betrieb**, Journal von `ai4artsed-backend` auf Fedora, Stufe `kids`, drei
Läufe an einem Tag:

```
18:59:19  Verdict response: 'Presence of UNSAF'
          no verdict extracted — BLOCKING (fail-closed)
19:03:12  Verdict response: 'Condition: Dark lighting/shadow'
          no verdict extracted — BLOCKING (fail-closed)
19:58:38  Verdict response: '/moody atmosphere alone = NOT harmful'
          no verdict extracted — BLOCKING (fail-closed)
```

Alle drei Bilder waren Hafen- und Küstenszenen. Die Beschreibung aus Schritt 1
lautete jeweils sinngemäß, es sei nichts aus dem Katalog vorhanden — im Lauf um
19:03 wörtlich: *there are no elements in the image that constitute violence,
gore, nudity, hate symbols…*. Gesperrt wurde trotzdem, und zwar richtig: die
Antwort enthielt kein Urteil. Zerstört wurde sie eine Stufe vorher.

**Nachgemessen** mit derselben Beschreibung, demselben Prompt und demselben
Modell, `temperature 0`, je drei Läufe:

| | Antwort-Token | davon Reasoning | `finish_reason` | Inhalt |
|---|---|---|---|---|
| mit `max_tokens: 200` | 191 | 190 | `stop` | `SAFE` |
| | 196 | 190 | **`length`** | `Answer SAFE or UNSAFE` |
| | 194 | 193 | `stop` | `SAFE` |
| ohne Deckel | 302 | 301 | `stop` | `SAFE` |
| | 163 | 162 | `stop` | `SAFE` |
| | 345 | 344 | `stop` | `SAFE` |

Das Denken verbraucht praktisch das gesamte Budget: unter dem Deckel 190 von 196
Token. Ohne Deckel schwankt es zwischen 162 und 345 und überschreitet 200 in zwei
von drei Läufen. Der Deckel schneidet also in der Mehrzahl der Fälle genau dort
ab, wo das Urteil stehen würde. Einer von drei Läufen der Messung lieferte
`finish_reason: length` und ein Bruchstück ohne Urteil — dasselbe Muster wie im
Betrieb.

**Das urteilende Modell arbeitet korrekt.** Gegenprobe mit derselben
Beschreibung, ohne Deckel, fünf Läufe: fünfmal `SAFE`, Inhalt jeweils genau
dieses eine Wort, Reasoning zwischen 258 und 328 Token. Der Fehler liegt also
nicht am Modell und nicht am Prompt, sondern allein daran, dass 200 unter dem
liegt, was das Modell zum Denken braucht. Was im Betrieb als Bruchstück ankommt
(`Presence of UNSAF`, `Condition: Dark lighting/shadow`), ist abgeschnittenes
Denken, das in das Inhaltsfeld gerät — nicht ein Modell, das den Prompt
nachplappert.

**Ein lokales Urteilsmodell ist kein Ersatz.** Gegenprobe mit `qwen3:1.7b` über
den GPU-Dienst, gleicher Prompt, fünf Läufe: ebenfalls fünfmal ein brauchbares
Urteil, aber der Inhalt ist 744 bis 961 Zeichen lang und trägt den
`<think>`-Block im Inhaltsfeld. `_extract_verdict` liest das Urteil dann aus
einem langen Gedankengang heraus — also genau die Konstruktion, an der die Kette
schon einmal gescheitert ist. Der Wechsel würde die Abschneidung gegen ein
Teilstring-Urteil eintauschen.

Dazu gehört:

- Die 200 sind kein Feld, das die Schnittstelle verlangt. `llm_client.py:14-18`
  hält als Regel fest, dass Deckel nur dort stehen, wo eine Provider-Schnittstelle
  das Feld fordert.
- `enable_thinking` wird in `chat()` und `generate()` entgegengenommen und laut
  Docstring ignoriert; auf dem Cloud-Weg wird kein Reasoning-Parameter des
  Anbieters gesetzt. Das Denken lässt sich über diesen Aufruf nicht verringern.
- `finish_reason` stand in jeder gemessenen Antwort, war im abgeschnittenen Fall
  `length` und wird nirgends gelesen. Es unterscheidet eine abgeschnittene
  Antwort von einer Antwort ohne Urteil.
- Der lokale Zweig derselben Funktion (`vlm_safety.py:203-214`) trägt keinen
  Deckel, wird aber nicht betreten, weil `STAGE3_MODEL` ein Cloud-Modell ist.
  Eine Umstellung auf ein lokales Urteilsmodell ließe den Fehler verschwinden,
  ohne die Ursache zu berühren.
- Der Text, den die Nutzerin liest, gibt den Betriebsfehler als inhaltliche
  Einstufung aus und zeigt darunter die Beschreibung, die das Gegenteil sagt.

> **Behoben 2026-08-07.** Der Deckel ist entfernt und der Aufruf wartet statt
> abzuschneiden (`vlm_safety.py:167`, `timeout=(10, None)` nach Projektregel
> `llm_client.py:20-21`). `_call_verdict_model` gibt `(content, finish_reason)`
> zurück; `finish_reason == 'length'` gilt als Betriebsfehler (`:406`), ebenso
> ein fehlendes Urteil. Beide Fälle sperren mit
> `VLM_OPERATIONAL_BLOCK_MESSAGE` (`:114`) — „KEINE Einstufung deines
> Bildes" —, die inhaltliche Sperre mit `VLM_CONTENT_BLOCK_MESSAGE` (`:108`).
> Alle drei Aufrufer der neuen Signatur sind umgestellt: die Nachschau, die
> S4/S8-Eskalation (`stage_orchestrator.py`, Abbruch bei `length` hält den
> Block) und der Stufe-2-Klassifikator
> (`schema_pipeline_routes.py:815`, gefunden im zweiten Prüflauf — als
> String-Konsument wäre er an der Tupel-Signatur zerbrochen). Trashy
> kategorisiert Betriebsstörungen jetzt vor jeder stage-Verzweigung als
> `systemUnavailable` (`ChatOverlay.vue`, Zweig „Technische Störung");
> der en-Text ist neu gefasst, die Übersetzungen laufen über
> `WORK_ORDERS.md` (WO-2026-08-07).

### Der Deckel auf der Interception-Stufe (uncommittet im Arbeitsbaum)

> **Erledigt 2026-08-07.** Die unten verlangte Reihenfolge ist eingehalten:
> A1 (Urteilsbindung) und die Grenze auf dem Guard-Text (Fensterung) sind
> zuerst gebaut; damit war der Deckel aufgabenlos und ist ersatzlos entfernt.
> Beide Dateien tragen wieder den Kommentar, dass an dieser Stelle kein Deckel
> steht, jetzt mit Verweis auf die Fensterung (`backend_router.py`,
> `prompt_interception_engine.py`). Die unter Punkt 2 genannten, nicht
> nachgeprüften Messungen (Übersetzungsabbruch, p5.js-Syntaxfehler) sind
> gegenstandslos: der Deckel, der sie verursacht haben soll, existiert nicht
> mehr.

Zwei Dateien tragen eine nicht eingecheckte Änderung, die unmittelbar zu 3a
gehört und deshalb hier verzeichnet ist:

- `prompt_interception_engine.py` führt `UI_MODE_MAX_TOKENS_SAFETY = {kids: 400,
  youth: 600, expert: 800}` ein.
- `backend_router.py` klemmt in `_process_prompt_interception_request` darauf:
  `safety_limit = UI_MODE_MAX_TOKENS_SAFETY.get(_config.UI_MODE, 800)`.

Der Kommentar an beiden Stellen begründet sie damit, dass die Entfernung des
Deckels gemessen eine Lücke geöffnet hatte.

**Das Argument dafür** (Stand der Niederschrift; seit dem 09.09.2026 bekommt das
Modell das Fenster, das seine eigene Datei angibt — 131072 Token):
Llama-Guard-3-1B hatte `n_ctx 4096`, und die Stufe-3-Vorlage
verbraucht davon rund 1000 Token. Unbegrenzte Stufe-2-Ausgabe füllt den Rest,
der Aufruf scheitert, und das Scheitern wird an `stage_orchestrator.py:1477` als
Freigabe gelesen. Der Deckel hielt diesen Weg unerreichbar.

**Das Argument dagegen, in drei Teilen:**

1. Er behebt 3a nicht, er verdeckt es. Was den Kontext füllt, ist der Text, den
   die Prüfung vorgelegt bekommt, und der kommt an mehreren Aufrufstellen direkt
   aus dem Request (`:1652`, `:2973`, `:4407`, `:5771`). Eine Grenze auf der
   *Ausgabe* eines Interception-Schritts erreicht diese Eingaben nicht. Der
   Deckel hält, bis eine Eingabe lang genug ist.
2. Er trifft nicht nur die Interception. Die Klemme sitzt im gemeinsamen Trichter
   und greift damit auch für die Stufe-3-Übersetzung und die Code-Erzeugung. Die
   Sitzung, die ihn eingebaut hat, hat dazu am 2026-08-05 gemessen, dass eine
   deutsche Übersetzung ab etwa 500 Wörtern ohne Satzzeichen abbricht und dass
   erzeugtes p5.js mit einem Syntaxfehler ausgeliefert wird. **Diese Messungen
   sind hier nicht nachgeprüft** — ihre Quelle wurde beim Aufräumen der
   Safety-Dokumente entfernt. Wer den Deckel behandelt, misst beides neu.
3. Harte Ausgabe-Grenzen unterhalb der Modell-Obergrenze sind in diesem Projekt
   ausgeschlossen, weil sie mitten im Satz abschneiden.

**Daraus folgt die Reihenfolge:** A1 (die Aggregation an `:1477`) und eine Grenze
auf dem Text, der Llama Guard vorgelegt wird, gehören vor jede Entscheidung über
diesen Deckel. Sind beide erledigt, hat er keine Aufgabe mehr. Solange keines von
beiden erledigt ist, ist er das einzige, was den Weg aus 3a verschlossen hält —
und genau deshalb ist er nicht ersatzlos zu entfernen.

Nicht zu verwechseln mit dem Deckel aus 3g: dort geht es um 200 Token auf dem
Urteilsaufruf der Bildnachschau, hier um 400 bis 800 auf der Interception-Stufe.

### Was ein Ergebnis nach der Nachschau noch erreicht

Die Auslieferungsrouten in `media_routes.py` liefern ohne Rückfrage nach dem
Prüfzustand aus: der einzige Treffer auf `safe|block|vlm` in der ganzen Datei
steht in einem Docstring (`:1344`). `get_image` (`:604-666`) lädt den Recorder,
wählt die Entität und sendet die Datei. `save_error`
(`pipeline_recorder.py:288-318`) hängt einen Fehlereintrag an und lässt die Datei
liegen. Ein Lauf, dessen Nachschau ihn zurückweist, bleibt über seine Kennung
abrufbar.

### Die Stufe des Kurses

`Course.safety_level` (`lab/models.py:185`) trägt `kids|youth|open`
(`courses_routes.py:45`) und wird ausgeliefert (`:60`). Die Erzeugungswege nehmen
`config.DEFAULT_SAFETY_LEVEL` (`schema_pipeline_routes.py:4534`, `:5183`;
`canvas_executor.py:729`; `canvas_routes.py:782`); `grep "course"` in
`schema_pipeline_routes.py` ergibt null Treffer. Der einzige Leser außerhalb der
Verwaltung ist `chat_routes.py:2244`, wo der Wert als Prosa in Resonas
Systemprompt einfließt. Der Frontend-Store zieht die Stufe aus
`/api/settings/safety-level` (`stores/safetyLevel.ts:14`).

### Prüfbarkeit

`devserver/tests/` enthält 35 Dateien der Form `test_*.py`. Die Kette berührt
davon `test_stage3_translation_isolation.py`, das `execute_stage3_safety`
sechsmal fährt (`:66,73,86,93,106,113`), und `test_stage1_statistics.py:30` für
die §86a-Wortliste. Weitere Läufe liegen in `devserver/testfiles/`. Eine
Abdeckungsprüfung über alle Wege gibt es noch nicht.

---

## 4. Die Aufgabe

**Die Prüfung soll an der Erzeugung hängen statt am Weg dorthin.** Ein Modus, den
es noch nicht gibt, soll die Prüfung erhalten, ohne dass seine Autorin sie kennt.

Dafür braucht es zuerst eine gemeinsame Tür, denn heute erzeugt die Plattform auf
**sechs getrennten Flächen**:

| Fläche | Wo sie liegt | Beleg |
|---|---|---|
| Lokale Diffusers-Erzeugung | `diffusers_client.py`, `stable_audio_client.py`, `hunyuan3d_client.py`, `heartmula_client.py` (über `heartmula_backend.py:324-337`) | 14 Chunks nehmen `get_diffusers_backend`, je einer die übrigen |
| ComfyUI | `comfyui_ws_client.py` | `backend_router.py:653`, `:848`, `:1018`, `:1090` |
| Cloud-Bild | `backend_router.py:1154` (`_process_api_output_chunk`), POST `:1206` | Ziele in `output_image_gpt_image_1.json:11`, `output_image_gemini_3_pro.json:11`; `gpt_image_1` trägt `audience.min_age: 10`, `workshop_suitable: true` |
| Text | `prompt_interception_engine.py:917-953` (eigene Providertabelle, POSTs `:1264`, `:1319`, `:1381`, `:1469`), `chat_routes.py:1589`/`:1644`, `media_routes.py:339-341` | — |
| Unterprozesse | `rave_routes.py:24`, `training_service.py:620`, `post_production_service.py:318` (ffmpeg erzeugt ein neues MP4), `blender_service.py:141` | — |
| Im DevServer-Prozess | `my_app/services/supertonic_backend.py:335-337` lädt das TTS-Modell und rechnet es über ONNX Runtime auf der CPU — kein GPU-Dienst, kein Unterprozess, kein HTTP | `schemas/chunks/output_speech_supertonic.py:107` holt `get_supertonic_backend`; nachgetragen 2026-09-03 aus `test_safety_coverage_map.py` |

Dazu kommen Direktproxys, die an allen sechs vorbei zum GPU-Dienst gehen:
`fusion_workbench_routes.py` (`_run`, seit 2026-09-14 zu ComfyUI statt zum GPU-Dienst), `text_routes.py:280-293`,
`media_routes.py:269-271`.

Die Erzeugung selbst liegt in einem eigenen Dienst (`gpu_service/`) und in
ComfyUI auf Port 17804. Die genannten Module sind HTTP-Clients, keine
Hardware-Grenze.

**Damit lautet die Aufgabe:** eine Stelle schaffen, durch die alle sechs Flächen
gehen, und sie zur Bedingung der Erzeugung machen. Das Prüfergebnis ist ein Wert,
den ausschließlich die Prüffunktionen erzeugen und der trägt, welche Stufe galt,
welcher Text geprüft wurde, wann, und welche Prüfungen liefen.

**Zwei vorhandene Mechanismen gehören zur Aufgabe dazu, weil sie ein fehlendes
Prüfergebnis heute auffangen würden:**

1. `backend_router.py:1759` fängt `TypeError` und liefert
   `BackendResponse(success=False)`; `:519-528` liest daraufhin
   `CHUNK_META['fallback_chunk']` und erzeugt über den Ersatzweg weiter (für
   `output_image_sd35_diffusers.py:23` ist das Ziel ein ComfyUI-Chunk). Ein
   fehlendes Prüfergebnis würde die Erzeugung also auf ein anderes Backend
   umleiten statt sie anzuhalten.
2. `backend_router.py:1683` ruft `module.execute(**parameters)`, und alle
   siebzehn Python-Chunks schließen ihre Signatur mit `**kwargs`. Ein neuer
   Schlüssel wird dort still aufgenommen und nicht weitergereicht.

Chunks werden über den Dateipfad geladen (`backend_router.py:511`, `:1660`), und
`:288` (`_detect_backend_from_model`) bestimmt das Backend zur Laufzeit neu. Eine
Prüfung der Abdeckung muss deshalb den Chunk-Ordner und die Routen mit einbeziehen
und kann sich nicht auf Import-Kanten stützen.

**Tote Wege, die beim Umbau entfallen:** `cross_aesthetic_client.py` (null
Importeure), `mosaic_routes.py` (`mosaic_bp` ist in `my_app/__init__.py` nicht
registriert), `openai_images_service.py` (null Importeure).

---

## 5. Arbeitspakete

| Aufgabe | Was zu tun ist | Machbarkeit |
|---|---|---|
| **A1 — erledigt 2026-08-07** (Vermerk unter 3a) | `stage_orchestrator.py:1477` so fassen, dass die Bedingung an einem vorliegenden Urteil hängt; das Verhalten des Laufs danach ist Entscheidung 1. Dazu gehört eine Grenze auf dem Text, der Llama Guard vorgelegt wird — erst danach ist der uncommittete Interception-Deckel entbehrlich (Abschnitt 3) | Eine Zeile für die Bedingung; der weitere Umfang hängt an der gewählten Reaktion |
| **A2** Alle Eingabefelder prüfen | `/pipeline/direct` führt sämtliche Textfelder aus `custom_params` durch Stufe 1 und Stufe 3, einschließlich `negative_prompt`, der CLIP-Prompts, `decomp_t5_prompt` und der Zell-Prompts. **Achtung Semantik:** Negativ-Felder tragen legitim Begriffe wie „gore, nsfw" (sie schließen aus, nicht ein) — eine unbedachte Guard-Prüfung darauf reproduziert das Keyword-Filter-Debakel aus §8 | Mittel; die Felder sind an einer Stelle beisammen (`:4707-4790`) |
| **A3 — erledigt 2026-08-07** (Vermerk unter 3c) | Das Ergebnis von `:4661-4670` durchläuft Stufe 3, bevor es konditioniert | Klein |
| **A4 — erledigt 2026-08-07** (Vermerke unter 3d/3e) | `stage4_only` serverseitig herleiten (`:5208`); `workflow_streaming_routes.py:42` auf die serverseitige Stufe umstellen | Klein; das Frontend führt `stage4_only` nur als Typangabe (`services/api.ts:66`) |
| **A5 — erledigt 2026-08-08** (Vermerk in der Abdeckungstabelle oben) | Der Zweig ab `:1832` erhält dieselbe Stufe-1-Abdeckung wie `execute_stage1_safety_unified` | Mittel |
| **A6** Eine Tür für sechs Flächen | Gemeinsame Stelle schaffen, Prüfergebnis als Bedingung; Fallback (`:1759`/`:519-528`) und `**kwargs` (`:1683`) einbeziehen | Der Kern des Umbaus; ohne die beiden Mechanismen wirkungslos |
| **A7** Direktproxys und Cloud-Weg anschließen | `fusion_workbench_routes.py` (`_run`), `text_routes.py:280-293`, `media_routes.py:269-271` sowie den Cloud-Bildweg (`backend_router.py:1154`) über die gemeinsame Tür führen — siehe Entscheidung 3 | Mittel, mechanisch |
| **A8** Nachschau je Medium | Text sofort (`:5603-5606` ausbauen); Canvas-Medientyp aus der Config statt aus dem Teilstring (`:3808-3816`); Video über Einzelbilder; Ton und Musik über Transkript; 3D über das Blender-Vorschaubild (`blender_service.py:141`) | Ungleich: Text Tage, die übrigen je ein eigenes Stück |
| **A9** Auslieferung fragt den Prüfzustand | `media_routes.py` prüft beim Ausliefern den Zustand des Laufs; `save_error` vermerkt ihn dafür am Lauf | Klein, sobald A6 steht |
| **A10** Stufe aus dem Kurs | `Course.safety_level` an die Erzeugungswege anschließen; die Abbildung der Stufennamen ist Entscheidung 2 | Klein; das Feld liegt vor |
| **A11 — erledigt 2026-08-08** (`devserver/tests/test_safety_coverage_map.py`) | Ein Test erzeugt die Abdeckungskarte aus Routen, den WO-§4-Service-Dateien (post_production, training, blender, canvas) und dem Chunk-Ordner und schlägt an, sobald ein erzeugender Weg ohne erklärte Prüfklasse hinzukommt. Die Karte deklariert 132 Routen-/Service-Stellen und 44 Output-Chunks (JSON-Zensus über das `type`-Feld — vier Chunks tragen kein `output_`-Präfix); zwei Konsistenztests halten die Chunk-Flächen gegen den Code (`get_diffusers_backend`, `backend`-Feld). Die Klassenzählung ist die ehrliche Bilanz: 34× `unchecked-proxy` und 14× `subprocess` sind die offene A6/A7/A8-Schuld, sichtbar statt still — der Sprung von 17 auf 34 am 2026-09-03 ist gefundene, keine neue Schuld: zwei zusätzliche Marker (`llm_service.*`, `_get_client()`) und geschachtelte Funktionsnamen haben sichtbar gemacht, was der Scanner vorher übersah. Bekannte Scanner-Grenzen (Alias-Import, URL-Variable ohne Namensfragment) stehen im Test-Docstring: Stolperdraht, kein Beweis | Günstig, und der Schutz davor, dass die Karte erneut auseinanderläuft |
| **A12 — erledigt 2026-08-07** (Vermerk unter 3g) | Den `max_tokens`-Deckel in `vlm_safety.py:185` entfernen; `finish_reason` auswerten und eine abgeschnittene Antwort als Betriebsfehler behandeln, unterscheidbar von einer inhaltlichen Einstufung — auch im Text, den die Nutzerin liest. Belegt und gemessen unter 3g | Klein; die Messwerte liegen vor |

**Reihenfolge:** A1 bis A5 und A12 stehen für sich und wirken sofort. A12 behebt einen Fehler, der im Betrieb bereits auftritt. A6 trägt A7 bis A9.
A11 begleitet alles ab dem ersten Paket.

### Aus den Prüfläufen vom 2026-08-07 offen geblieben

Drei gegenläufige Prüfläufe am Diff (Freigabe-Lücken, Fehlblockaden,
Vertrags-Aggregationen) haben neben den eingearbeiteten Befunden Folgendes
belegt und offen gelassen:

- **`execute_stage1_safety` ist tot und fail-open.** Keine Aufrufstelle im
  ganzen Repo (nur der Import `schema_pipeline_routes.py:28`); bei
  Pipeline-Fehlern gäbe sie `(True, [])` zurück und ihr Text liefe
  ungefenstert. Sie ist die einzige verbliebene Stelle, die 3a wieder öffnen
  würde, sobald jemand sie verdrahtet. Entfernen gehört zu den toten Wegen
  des Umbaus (§4); bis dahin gilt: nicht verwenden.
- **Der Code-Weg bleibt fail-open.** `execute_stage3_safety_code` erlaubt
  bei LLM-Ausfall weiter die Auslieferung (Sandbox als zweite Verteidigung,
  im Bestand dokumentiert); er nutzt das neue `verdict`-Regime nicht. Gehört
  zu A6/A8, nicht stillschweigend mitziehen.
- **`save_error` trägt die Prüfmethode nicht.** Betriebs- und Inhaltssperren
  landen ununterscheidbar als `error_type='safety_blocked'`; A9 kann sie nur
  am Prosa-Text trennen. Vor A9: `method` in die `save_error`-Details
  aufnehmen. An der Legacy-VLM-Stelle fehlt `save_error` ganz.
- **Latenz der Fensterung:** ~350–500 Wörter = 1 Guard-Aufruf, 2000 Wörter ≈ 8
  Aufrufe (~1 s je Aufruf); ab ~8.900 Wörtern hält die 32-Fenster-Grenze den
  Lauf fail-closed an. Normale Workshop-Läufe bleiben bei 1–2 Aufrufen.
- **Blocked-Payloads führen die blockierende Prüfung in Listen namens
  `checks_passed`** (`:3027`, `:4679`, `:5067`) — das Frontend liest sie dort
  nicht, die Benennung täuscht aber. Aufräumen bei A6.

Aus den A5/A11-Prüfläufen vom 2026-08-08 dazugekommen (vorbestehend, an
keinem Diff hängend):

- **`context_prompt` durchläuft an keinem Eintrittspunkt Stufe 1**
  (`schema_pipeline_routes.py`, Streaming `:1865`, wirkt `:1973-1983`) —
  §86a fängt Stufe 3, DSGVO fängt niemand. Gehört zu A2 (Feldabdeckung),
  Fläche: alle Interception-Eintrittspunkte.
- **Ladefehler der §86a-Wortliste ist fail-open:** `load_bilingual_86a_terms`
  liefert bei fehlender/korrupter JSON `{}` und der Filter meldet still
  „clear" (`stage_orchestrator.py:830-832`, `:847-848`). Da §86a die
  gesetzliche Aufgabe trägt: Ladefehler fail-closed machen oder beim Start
  hart scheitern. Klein.

### Aus der Bildprüfung vom 2026-08-16 — für den Neubau des Kids-Filters

Gemessen in drei Durchgängen über
`~/Pictures/scary_pictures_for_safety_testing`, Stufe „kids".

Eingebaut und live (`39a4f786`, `ad5e82ea`, `0f8c31f7`):

- Wiederholungs-Stopp im GPU-Dienst (`gpu_service/services/repetition_guard.py`),
  wirksam in `chat_stream()`, `chat()` und `generate()`. Aufrufer bekommen
  `finish_reason` "stop" | "length" | "repetition". Gemessen am blockierenden
  Aufruf: 74.124 Zeichen / 293,6 s → 5.023 Zeichen / 3,6 s; acht gewöhnliche
  Lesungen unverändert.

  **Zweite Regel seit 2026-08-25: eine Periode im Textende.** Die erste Regel
  zählt fertige Sätze und Zeilen. Ein Text, der gar nichts zu Ende bringt, ist
  für sie unsichtbar — genau der Fall auf der Fläche „Representation
  Engineering": bei Steuerstärke 3 schreibt Qwen3-4B „and the, and the, and
  the" ohne Punkt und ohne Zeilenumbruch, also wird nie ein Abschnitt fertig
  und nie etwas gezählt. Gemessen: der Lauf lief nach fünfzehn Minuten noch
  immer, ohne dass ein Client daran hing (99 % CPU, 13 GB VRAM, fünfundzwanzig
  Minuten nach dem Aufruf). Deshalb wird jetzt auch das Textende auf eine
  Periode gelesen: eine Zeichenkette hat die Periode p genau dann, wenn
  `s[p:] == s[:-p]`, also ist die ganze Prüfung ein Vergleich je Kandidat, und
  zehn ununterbrochene Wiederholungen beenden den Lauf. Es zählt nur der
  Schwanz von 600 Zeichen, die Kosten bleiben also gleich, wie lang die Antwort
  auch schon ist: 48 µs je Token im schlechtesten Fall. Die Einheit muss einen
  Buchstaben oder eine Ziffer tragen, damit eine Reihe Bindestriche, eine
  Punktzeile und ein ASCII-Strich draußen bleiben. Beide Regeln melden weiter
  `finish_reason` "repetition"; `guard.reason` sagt im Log, welche gegriffen
  hat ("segment" oder "loop").

  Gemessen an derselben Fläche, Qwen3-4B, Schicht 18, dieselben drei Paare,
  „The capital of Germany is":

  | | Deckel 50 | ohne Deckel, ohne Periodenregel | ohne Deckel, mit Periodenregel |
  |---|---|---|---|
  | Reihe bei 1,5 | 21 s, jede Zelle mitten im Satz abgeschnitten | — | 50 s, jede Zelle bis zu ihrem eigenen Ende |
  | Reihe bei 3 | — | — | 29 s (212 / 3.337 / 305 Zeichen) |
  | eine Zelle bei 3 | — | nach 15 Minuten nicht fertig | 32 s, gestoppt nach 105 Token |
- Der Beschreiber-Schritt der Bildprüfung sperrt bei "length" und "repetition"
  (`vlm_safety.py`). Ohne diese Zeile wäre aus einer Sperre eine bewertbare
  Teilbeschreibung geworden: vorher brach llama-cpp bei vollem Kontext ab und
  `chat()` gab `None` zurück.

Drei Befunde, die der Neubau nicht erben sollte:

1. **Der Beschreiber wird nach einer Einschätzung gefragt, nicht nach einer
   Beschreibung.** `VLM_DESCRIBE_PROMPTS['kids']` nennt die Kategorienliste
   („Examine this image for the following: violence, gore, … Describe what you
   see"), und das Modell beantwortet sie: „There is no violence, … or content
   that is scary". Der Urteils-Prompt bewertet ausdrücklich diese Antwort
   („Based on this analysis"). Die Rollentrennung aus `9e3a88ca` („the local 2B
   is never asked for a verdict") besteht im Prompt nicht.
2. **Das Urteil ist nicht wiederholbar.** Gleiche Beschreibung (gleiche
   Prüfsumme über drei Durchgänge), unterschiedliches Urteil — bei
   Temperatur 0. Ein gesperrtes Bild geht beim zweiten Versuch durch.
3. **Größer ist nicht sicherer.** Beim klarsten Horror-Bild (helle, skelettartige
   Hände aus dem Dunkel) sperrt der 2B dreimal, der 4B gibt dreimal frei. Ein
   Modelltausch ist kein Hebel.

Nicht gemessen, ausdrücklich offen: die expliziten Kategorien (Gewalt, Gore,
Nacktheit, Hasssymbole) — dafür fehlt geprüftes Material. Und der naheliegende
Gegenvorschlag (Beschreiber-Prompt ohne Kategorienliste, dafür detailfordernd)
ist eine **Hypothese**; die Entscheidung vom 2026-03-18 hat die Gegenrichtung
gemessen („VLM describes skeletal horror claws as ‚hands reaching out'"). Er
gilt erst, wenn dieselben drei Durchgänge besser ausfallen.

Zwei Dinge zum Bestand, die beim Neubau mit aufzuräumen sind: der
Entscheidungseintrag vom 2026-03-18 in `docs/DEVELOPMENT_DECISIONS.md`
beschreibt die Architektur von vor April; und `9e3a88ca`, das den heutigen Weg
zum einzigen gemacht hat, enthält keine Messung des Wegs, den es herstellt —
die 13-Bilder-Zahlen gehören zur vorherigen Bauform.

---

---

## 6. Entscheidungen, die in dieser Arbeit zu treffen sind

Diese drei Punkte gehören der Sitzung, die den Auftrag ausführt. Sie sind hier
mit dem Material aufgeführt, das zur Entscheidung nötig ist, damit niemand es
sich neu erarbeiten muss.

**1. Wie sich ein Lauf verhält, wenn das Prüfmodell nicht antwortet** (gehört zu A1).

> **Entschieden 2026-08-07: Der Lauf hält an.** Alle neun dokumentierten
> Vorfälle hatten die Form „Urteil blieb aus, Lauf ging weiter" — das
> Weiterlaufen ist die belegte Fehlerform, und der Stufe-2-Vorspann ist eine
> Bitte an ein Modell, kein Prüfergebnis. Die Meldung
> (`SAFETY_CHECK_UNAVAILABLE_MESSAGE`, `stage_orchestrator.py:1443`) ist als
> technische Störung formuliert („Deine Eingabe ist NICHT der Grund"), Trashy
> ordnet sie über den Zweig „Technische Störung" als `systemUnavailable` ein
> statt als Inhaltssperre (`ChatOverlay.vue`). Der Betriebsweg zurück bleibt
> der Neustart des GPU-Dienstes.

Material:
- Der §86a-Wortfilter (`stage_orchestrator.py:1098`) und die Namenserkennung
  laufen lokal und sind vom GPU-Dienst unabhängig — die gesetzlichen Aufgaben
  tragen bei einem Ausfall weiter.
- Die Altersbeurteilung hat einen zweiten Träger: den Sicherheits-Vorspann in
  Stufe 2 (`instruction_selector.py:70-91`), der auf dem Interception-Modell und
  damit auf anderer Infrastruktur läuft.
- Der Betriebsweg zurück ist ein Neustart des GPU-Dienstes.
- Sämtliche neun dokumentierten Vorfälle der Vergangenheit hatten die Form: das
  Urteil blieb aus, der Lauf ging weiter, und das Protokoll vermerkte ihn als
  geprüft.

Zu entscheiden ist, ob der Lauf anhält, und wie die Meldung von einer
inhaltlichen Zurückweisung unterscheidbar bleibt, damit im Workshop niemand
seine Eingabe für die Ursache hält.

**2. Wie `open` aus dem Kurssystem auf eine Stufe der Kette abbildet** (gehört zu A10).

Material:
- Die Kurs-Seite kennt `kids`, `youth`, `open` (`courses_routes.py:45`,
  `lab/models.py:185`).
- Die Kette kennt `kids`, `youth`, `adult`, `research` (`config.py:911-946`,
  Einstellungsdialog `SettingsView.vue:96-99`).
- `READING_VOLUME_WORDS` hängt seit der Trennung von Filter und Bedienmodus
  nicht mehr an der Jugendschutzstufe, sondern an `UI_MODE`, und führt
  `easy: 100`, `medium: 200`, `expert: 300` (Stand 07.09.2026). `open`, `adult`
  und `research` kommen darin nicht vor: wer einen solchen Wert nach `UI_MODE`
  schreibt, bekommt gar keine Längenangabe, still. `_READING_VOLUME_READERS`
  gibt es nicht mehr — die Klausel nennt eine Zahl und keinen Leser, weil ein
  benannter Leser als Adressat im Modell ankam und die Schreibweise verstellte.
- `research` kommt im Kurssystem nicht vor.

**3. Wie die Cloud-Bildwege behandelt werden** (gehört zu A6 und A7).

Material:
- `output_image_gpt_image_1.json:11` und `output_image_gemini_3_pro.json:11`
  erzeugen bei einem externen Anbieter, aufgerufen über
  `backend_router.py:1154`, also außerhalb der lokalen Erzeugung.
- Die Eignung fürs Publikum steht bereits in den Configs
  (`output/gpt_image_1.json:87-88`: `workshop_suitable`, `min_age`).
- Der Schutz personenbezogener Daten hängt am Eingang (Stufe 1) und an der
  Provider-Auswahl (`config.py:607-626`).

Zu entscheiden ist, ob der Cloud-Weg mit A6 und A7 dieselbe Behandlung erhält
wie die lokale Erzeugung, oder ob er darüber hinaus eine eigene Regel braucht.

---

## 7. Arbeitsregeln

1. **Dreifache adversariale Prüfung vor jedem Commit an der Kette** — drei
   verschiedene Prüfprompts, auf Widerlegung angesetzt. Grund: Die Kette wurde in
   nahezu jeder Sitzung erneut beschädigt, meist von Sitzungen, die ihre Änderung
   für offensichtlich richtig hielten. Auch dieses Dokument hat den ersten
   Prüflauf nicht bestanden.
2. **Jede Behauptung trägt `datei:zeile` oder eine Messung.**
3. **Im Zweifel gilt eine Stelle als noch offen.**
4. **Änderungen entstehen im Fedora-Checkout**
   (`<repo>`) und werden dort committet, mit
   benannten Pfaden.
5. **Der Gegenstand ist die Prüfung von Sprache und Bild.** Wo ein Feld, eine
   Funktion oder ein Modell bereits vorliegt, wird es angeschlossen.
6. **Die Plattform ist für beaufsichtigte Nutzung gebaut.** Die Technik
   unterstützt die Kursleitung und trägt dabei selbst: Was das System zusagt,
   gilt unabhängig davon, wer es bedient.

---

## 8. Zwei Erfahrungen, die bindend bleiben

Beide stammen aus Workshop-Läufen und sind an anderer Stelle nicht mehr
festgehalten.

**Der Keyword-Altersfilter ist aufgegeben und wird nicht wieder eingeführt.**
Er wurde über mehr als zehn Sitzungen zwischen zu streng und zu durchlässig hin
und her justiert. Den Ausschlag gab der Workshop am 12.03.2026: 137 von 470
Anfragen erreichten ein Ergebnis, und 98 der Sperren waren Fehltreffer auf
Wörtern wie „fangs", „explosion", „Blut", „claws", „teeth". Kurze Stichwörter in
natürlicher Sprache treffen notwendig zu breit, und längere Listen verschlechtern
das Verhältnis weiter. An seiner Stelle steht der Sicherheits-Vorspann in Stufe 2
(`instruction_selector.py:70-91`).

**Das Bildmodell der Nachschau wird nur nach erneuter Workshop-Erprobung
gewechselt.** `qwen3-vl:2b` ist das einzige an einem Workshop-Korpus erprobte
Modell (202 Bilder, Workshop 13.03.2026). Ein Wechsel auf `qwen2.5-vl:2b` führte
dazu, dass jedes Bild mit dramatischer Bildsprache — Ruinen, roter Himmel,
Verfall — pauschal zurückgewiesen wurde. Jeder Modellwechsel an dieser Stelle
braucht einen neuen Durchlauf am Korpus.

---

## 9. Quellen

**Code, in dieser Reihenfolge:**
`devserver/schemas/engine/stage_orchestrator.py` ·
`devserver/my_app/utils/vlm_safety.py` ·
`devserver/schemas/engine/backend_router.py` ·
`devserver/my_app/routes/schema_pipeline_routes.py` ·
`devserver/my_app/routes/canvas_routes.py` ·
`devserver/my_app/services/canvas_executor.py` ·
`devserver/schemas/engine/instruction_selector.py`

Die Inline-Kommentare in `stage_orchestrator.py` und `vlm_safety.py` sind der
verlässlichste Fließtext zur Kette; die Kommentare zu den Fehlerpfaden in
`:642-660` beschreiben allerdings ein Verhalten, das `:1477` aufhebt.

**Chronik:** `docs/DEVELOPMENT_DECISIONS.md`.

**Überholt:** die älteren Berichte und Architekturabschnitte zur Prüfkette.
Dieses Dokument tritt an ihre Stelle.
