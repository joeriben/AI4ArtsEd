# ARCHITECTURE PART 38 - Re-enactment (deutsch: Nachspielen)

> Hieß bis 2026-08-10 "Cover Band" und bis 2026-08-08 "Silly Parrot". Route,
> View-Datei und i18n-Schlüssel sind unverändert (`/cover-band`,
> `views/cover_band.vue`, `coverBand.*`) — umbenannt ist der Ort, nicht die
> Adresse. Der Dateiname dieses Dokuments bleibt aus demselben Grund stehen.

**Datum:** 2026-08-05
**Route:** `/cover-band` · **View:** `views/cover_band.vue` · **API:** `/api/parrot/*`
**Entscheidung + Begründung:** `docs/DEVELOPMENT_DECISIONS.md`, 2026-08-05.

## Kernidee

Eine Gruppe nimmt bis zu vier Minuten auf — singt, summt, hält ein Handy hoch —
und vier Maschinen reichen das Material weiter. Was am Ende zurückkommt, wird
gegen den Text gehört, der der Musikmaschine übergeben wurde. Gegenstand der
Seite ist der Abstand zwischen beidem.

Leitmetapher „silly parrot", im Anschluss an „stochastic parrot" (Bender,
Gebru, McMillan-Major, Shmitchell 2021). Sie ist genau dort produktiv, wo sie
bricht: ein echter Papagei ahmt **Klang als Klang** nach. Dieser muss den
Umweg über eine Wortliste und über aufgeschriebene Wörter nehmen, bevor er
antworten kann — und dieser Umweg ist der ganze Verlust.

## Die Kette

```
Mikrofon (Browser, max 240 s = SONG_MAX_MS)
   │   MediaRecorder → decodeAudioData → WAV im Browser
   │   (serverseitig ist damit kein Codec nötig)
   ▼
POST /api/parrot/recording            → recording_id
   ▼
GET  /api/parrot/stream/<id>          Server-Sent Events, ein Ereignis je Station
   │
   ├─ ranked   CLAP + MuQ     /api/analysis/music-tags   zwei volle Ranglisten
   ├─ words    HeartTranscr.  /api/analysis/lyrics       die Wörter
   ├─ written  LLM            PromptInterceptionEngine   Tags + Lyrics
   └─ sung     eine von vier  je nach Gehörtem            exakt die Aufnahmelänge (10-240 s)
   ▼
GET  /api/parrot/sung/<id>            inline, kein Attachment
POST /api/parrot/discard/<id>
```

## Die Seite steht unter dem Band, und das Band trägt kein Material

Drei Knoten — `Nimm etwas auf!` · `Start` · `Ausgabe` —, und jeder von ihnen
hat die Form, die derselbe Knoten in `views/x2x_flow.vue` hat. Das ist der
Maßstab, nicht eine eigene Erfindung:

- **Eingabe-Knoten:** heißt wie im Flow (`x2xFlow.nCreate`, „Erstellung") und
  trägt die Glyphenzeile des Flows — eine Glyphe tief, Klang, denn mehr macht
  diese Seite nicht — und darunter **alle vier Maschinen mit Namen**
  (`.cr-models`). Die
  Menge liegt fest, also steht sie da, statt hinter einem Klick zu liegen, den
  nichts ankündigt. Vor dem Lauf leuchtet **keine** — welche läuft, entscheidet
  sich an dem, was gehört wurde, und gehört ist noch nichts. Die Kette nennt auf
  ihrem eigenen Ereignis die Maschine, die sie genommen hat, und der Knoten
  leuchtet sie von dort. Eine Handwahl schlägt die Tabelle, hält über Läufe
  hinweg und trägt den Unterstrich des Flows.
- **Aktions-Knoten:** ein `▶`, sonst nichts, und während des Laufs
  `FlowRunPanel`.
- **Ausgabe-Knoten:** das erzeugte Medium selbst (im Flow `.out-media` /
  `.out-audio`), hier also der Song, plus die Zeile, welche Maschine ihn
  gemacht hat.

**Aufgenommen wird in der Box, in der diese Plattform Material aufnimmt.**
`MediaInputBox` hatte zwei Sorten — ein Textfeld und, über `ImageUploadWidget`,
ein Bild. Ton war die fehlende dritte, und jede Seite, die ihn wollte, baute
sich ihre eigene Knopfreihe. `components/AudioRecordWidget.vue` ist diese
dritte, als Geschwister von `ImageUploadWidget` geschrieben: dieselbe Zone,
derselbe leere Aufruf, dieselbe gefüllte Vorschau, der Papierkorb im Kopf der
Box. Es besitzt das Mikrofon — Erlaubnis, Recorder, Uhr, die Vier-Minuten-Decke
und die Umwandlung nach wav — und übergibt ein fertiges wav plus seine Länge.
Die Seite behält davon nur ihren eigenen Teil: den Upload.

Die Box steht als Erstes in der Spalte, **im Lesemaß (34rem)** — dem Maß der
früheren Take-Karte. Nicht in Spaltenbreite: auf den anderen Seiten steht dieselbe Box in
halben Spalten und Rasterzellen, und ihre Zonengröße stammt vom Bild, wo die
Zone Drop-Ziel und Vorschau ist. Audio hat nichts zu droppen; ein seitenbreiter
Schalter wäre durch nichts gedeckt. Während der Aufnahme ist
die **Uhr die große Zeile** im roten Rahmen — sie zählt, und das ist die
Rückmeldung; eine Wellenform wäre hier Dekoration, keine Information. Darunter
die drei lesbaren Stationen in den Auswurfboxen (`components/FlowCard.vue`) —
**eine Spalte, ein Maß**, dasselbe 34rem. Vorher standen zwei davon in einem
Zwei-Spalten-Raster, in dem die sortierte Liste ein Vielfaches der Höhe der
Abschrift neben ihr hat, während das aufgeschriebene Lied darunter über die
volle Breite lief: drei Maße für drei Dinge, die gleich gelesen werden.

Jede lesbare Box hat eine **Rückseite**: 550 ms halten, und sie dreht sich auf
das, was sie gemacht hat — Maschine, Eingabe, Dauer. Dieselben drei Zeilen, die
der Flow auf die Rückseite eines Materials legt. Damit steht die Herkunft nicht
mehr als Kleingedrucktes unter dem Ergebnis.

**Die Kette startet nicht mehr von selbst.** Das Anhalten der Aufnahme lädt sie
nur hoch. Danach liegt sie da: anhörbar, löschbar, neu aufnehmbar — und die vier
Maschinen laufen erst, wenn jemand `▶` drückt. Vorher kostete jeder Fehlgriff
sofort einen Song auf der GPU.

Der `▶` ist **einmalig je Aufnahme**, und das ist keine UI-Entscheidung: die
Stream-Route löscht `recording.wav` in ihrem `finally`, gleich wie die Kette
endete (`routes/parrot_routes.py`). Ein zweiter Druck könnte nur noch
`recording not found` bekommen. Darum verschwindet der Knopf, sobald er
gedrückt wurde, statt grau stehen zu bleiben — und darum darf der Zustand nicht
aus den Stationen abgelesen werden: bricht die Verbindung vor dem ersten
Ereignis, stehen alle vier noch auf `idle`.

## Welche Maschine singt: was gehört wurde, entscheidet

Zwei Ja/Nein-Antworten, vier Ausgänge:

| gehört | Ziel | was daraus wird |
|---|---|---|
| Musik **und** Text | `heartmula_standard` | ein Lied: Worte zum Singen und ein Stil, in dem sie gesungen werden |
| Musik, kein Text | `stableaudio_music` | Musik, aber nichts zu singen |
| Text, keine Musik | `qwen3_tts_standard` | eine Stimme: die Worte zurückgesprochen |
| weder noch | `stableaudio_sfx` | ein Klang |

Eine Handwahl im Erstellungs-Knoten schlägt alle vier und wird als `?config=`
mitgeschickt; ohne Handwahl schickt die Seite nichts mit, und die Kette
entscheidet selbst (`resolve_singer` in `my_app/services/parrot_service.py`).

**Entschieden wird an dem, was gehört wurde** — an der Rangliste der ersten und
den Wörtern der zweiten Station —, nicht an dem, was die Schreib-Station
geschrieben hat. Die wird jedes Mal um ein Lied gebeten und liefert jedes Mal
eines; gemessen wurde vorher also nur, wie liedförmig ein LLM schreibt.

**Geroutet wird auf der zweiten Rangliste, MuQ-MuLan.** Von den beiden ist sie
das Musik-Modell, und auf den Proben war sie die einzige, deren oberste Antwort
jedes Mal stimmte:

| Probe | CLAP oben | MuQ oben |
|---|---|---|
| braunes Rauschen | a voice speaking, not singing **.290** | no voice at all **.544** |
| gesungener Pop | pop song **.465** | pop song **.588** |
| deutsche Sprache | a clean studio recording **.358** | a voice speaking, not singing **.592** |
| synthetische Akkorde | happy and upbeat **.210** | hip hop **.377** |

CLAP gab auf sauberer Sprache „a voice speaking, not singing" **−0.118** und
gleichzeitig „jazz" **.277**. CLAP ist deshalb **kein Rückfall**: darauf zu
routen verschlechtert die Antwort nicht, es dreht sie um. Schweigt MuQ, fällt
`resolve_singer` auf `heartmula_standard` zurück — das ist, was hier vor der
Tabelle monatelang lief, also eine angesagte Vorgabe statt einer Vermutung.
Angezeigt wird auf der Seite weiter CLAP zuerst: die Seite handelt davon, was
diese Maschinen aus einer Aufnahme machen, und die öffentlich falsche ist nicht
die, die routen soll.

Drei Vergleiche, in dieser Reihenfolge:

1. Steht „noise, not music" oder „silence" ganz oben → keine Musik. Das
   entscheidet **nur** die Musik-Frage: eine Aufnahme in einem Raum kann oben
   „silence" tragen und trotzdem Worte enthalten.
2. Sonst: schlägt „a voice speaking, not singing" das beste Musik-Label → eine
   sprechende Stimme, keine Musik. Das darf **nur** dieses eine Label.
3. Sonst ist Musik da, wenn das beste Musik-Label „noise, not music"/„silence"
   schlägt.

**Singen ist Musik.** Die beiden Gesangs-Label stehen deshalb auf der
Musik-Seite. Stünden sie dagegen, ginge jede unbegleitete Stimme als Sprache
durch und würde von einem TTS zurückgesprochen — auf einer Seite, deren eigene
Anweisung „Sing, summ oder halte dein Handy hoch" lautet.

**Die Text-Frage ist nicht überall dieselbe.** In Musik heißt „sind da Worte"
*singt jemand* und wird an den Gesangs-Labeln gemessen; ohne Musik heißt es
*spricht jemand* und wird am Sprech-Label gemessen. Das Sprech-Label in Musik zu
fragen ließ ein Instrumental als Lied durchgehen: sein Wert liegt im Übersprechen
dieses Modells und muss nicht hoch sein, nur höher als „no voice at all".

Und Text braucht **beide** Maschinen: der Transkribierer hat etwas geschrieben
**und** die Rangliste stellt eine Stimme über „no voice at all". Der
Transkribierer allein genügt nicht — auf braunem Rauschen schrieb er „The train
is now arriving at station", auf synthetischen Akkorden „××××，x，x，x，". Genau
hier darf die Konfabulation einmal aufgefangen werden, statt gezeigt zu werden.

Verglichen wird immer **innerhalb** einer Rangliste und nie gegen eine feste
Zahl: beide Modelle betten jede englische Zeichenkette ein und messen
Kosinus-Ähnlichkeit, keines kennt ein Enthalten, und auf demselben Pop-Song stand
bei CLAP „silence" bei .25. Ein absoluter Wert sagt nichts, nur „dieses Label
schlug jenes".

Nachrechnen: `devserver/testfiles/probe_parrot_routing.py` erzeugt Rauschen und
Akkorde selbst und druckt beide Ranglisten samt Entscheidung.
`devserver/tests/test_parrot_routing.py` spielt dieselben Ranglisten plus die
Gegenbeispiele der Prüfläufe ohne Modell durch.

`stableaudio_music` und `stableaudio_sfx` sind **dasselbe Modell**. Stable Audio
3 nimmt einen Text und eine Länge und zieht zwischen Musik und Geräusch keine
Grenze; gezogen wird sie eine Station früher, an dem, was gehört wurde. Von
dieser Seite aus unterscheiden sich die beiden Configs **nur im Namen**: der
Prompt verzweigt nicht, und `SECONDS` wird mit der Länge der Aufnahme
überschrieben — im Rahmen der Seite, 10 bis 240 s, und sonst mit keinem zweiten
Deckel. Bis 2026-08-12 standen hier zwei: `SA3_MAX_SECONDS = 47,6 s`, das Limit
von Stable Audio **1.0** und beim Umstieg auf SA3 stehengeblieben, und darüber
der Plattform-Deckel `STABLE_AUDIO_MAX_DURATION = 120 s`, den der GPU-Dienst
still anwendet. Der erste ist ersatzlos entfernt; der zweite steht
bei 240 s, dazu `max_duration` in den drei SA3-Configs.
Gemessen am selben Tag, gleicher Prompt, gleicher Seed 12345: 12 s → 289 688
Bytes, 47,6 s → 1 144 206, 120 s → 2 881 453, 240 s → 5 761 610. Die Länge folgt
damit der Aufnahme bis ans Versprechen der Seite.

Die Längenzeile, die der Fluss seit demselben Tag mitschreibt (PART 37),
entsteht auf dieser Seite nicht durch eine Adaption — `_sing` ruft keine auf,
sondern geht direkt in `execute_pipeline`. `_sing` schreibt sie sich selbst ans
Ende von `TEXT_1`, mit der Länge der Aufnahme, zusätzlich zu `SECONDS`. Grund:
der Chunk liest eine solche Zeile und lässt sie entscheiden, und eine Zeile, die
zufällig in Lyrics oder Tags steht, würde das sonst an seiner Stelle tun.
Gelesen wird die LETZTE — und das ist die der Seite. Vor dem Modell wird sie
wieder abgenommen.

**Auf einer Karte unter 50 GB hält das Vier-Minuten-Versprechen nicht.** Dort
lädt SA3 klein, und die kleinen Modelldateien rendern exakt 120,00 s
(`stable_audio_model.py`, Schwelle 50 GB). Seit 2026-08-12 steht das als Warnung
im Log, statt still zu kürzen; die Entscheidung darüber ist offen (PART 37). Anderswo — im
Canvas-Katalog etwa, der das Verzeichnis ausliest — tragen die Configs ihre
eigenen Vorgabelängen.

## Zwei tragende Eigenschaften

**Keine Station wird korrigiert oder abgefangen.** Zeigt man das Mikrofon in
einen leeren Raum, liefert die Transkription trotzdem einen flüssigen,
selbstbewussten Satz, und die Kette läuft weiter. Das ist die Vorführung, nicht
ein Fehler; die Seite lädt ausdrücklich dazu ein. Ein Gate hier würde die
schärfste Demonstration der Plattform unterdrücken.

**Nichts bleibt.** Die Aufnahme liegt unter `/tmp/ai4artsed_parrot/<id>/`,
außerhalb des Export-Stores und außerhalb des Arbeitsbaums, und wird gelöscht,
sobald die Stationen fertig sind. Das Lied ist kein Run, hat keinen
Media-Store-Eintrag, keinen Favoriten, keinen Export und keinen Download. Ein
TTL-Sweeper räumt nach einer Stunde. Wer das ändert, hebt die Zusage auf, unter
der Kinder hier ihre Stimme hergeben.

## Kein Stage 2

Anderswo auf der Plattform leistet das LLM die pädagogische Verwandlung. Hier
ist es die Station, die **erfindet** — sie macht aus einer verstümmelten
Transkription selbstbewusst zusammenhängende Lyrics, und das muss man ihr
ansehen können. Unter dem Papageien-Bild ist sie der Musterfall, nicht die
Ausnahme. Das Stück steht deshalb neben dem Latent Lab (Dekonstruktion), ist
aber **nicht** Teil davon: das Latent Lab verlangt `adult`/`research`, dies ist
für Kinder gedacht.

Verwendet wird von `PromptInterceptionEngine` nur `process_request` mit
`prebuilt_prompt` — die Klasse ist der Modell-Router der Plattform (lokale
GGUF-Modelle vs. `mammouth/`, `openrouter/`, `anthropic/` … samt
Fallback-Kette). Ein eigener Router wäre eine Parallelstruktur.

## Zwei Register der Transparenz

| | lesbar | hörbar |
|---|---|---|
| Stationen | ranked, words, written | sung |
| zeigt | die Grenzen der Auswertung | die Grenzen der Maschine, die gerade singt |
| wie | Rangliste mit Zahlen, Transkription, LLM-Text | gegen den LLM-Text gehört, der darüber steht |

Die Rangliste wird **vollständig** durchgereicht, inklusive letztem Platz. Was
ein Modell jedes Mal ans Ende setzt, ist die aussagekräftigste Stelle der
Seite: `arabic maqam on oud` ist in jeder gemessenen Musik-Bedingung Letzter.

Das Label-Vokabular (`MUSIC_TAG_VOCABULARY`, 46 Einträge) ist **unseres**, nicht
das des Modells — MuQ-MuLan bettet beliebige englische Strings ein und hat kein
geschlossenes Vokabular. Die Seite sagt das (`coverBand.ranked.ourList`). Es
gibt außerdem kein „nichts davon": Kosinus-Ähnlichkeit liefert immer eine
Ordnung, also wird auch Stille zuversichtlich einsortiert.

## Das LLM repariert die Verhörer — und das bleibt unmarkiert

Im Testlauf machte die Transkription aus „auf der Mauer" ein „auf der Nauer";
die Schreib-Station schrieb daraus „upon the wall". Der Verlust, den die
Wort-Station sichtbar macht, wird in der Schreib-Station stillschweigend
geglättet.

**So bleibt es.** Die Maschine glättet tatsächlich stillschweigend; zwei Texte
untereinander, ohne Kommentar dazwischen, sind die zutreffende Darstellung
davon. Eine Auszeichnung wäre die Plattform, die sich über den Vorgang legt,
und ein Prompt, der Fehlerbewahrung erzwingt, wäre gestellt.

Weder das eine noch das andere nachrüsten.

## Verwandte Parts

- PART 31 — GPU-Service (die drei Analyse-Stationen und was ihre Ausgaben nicht sind)
- PART 28 — Latent Lab (benachbartes Register, aber gated)
- PART 29 — Safety-System

## Die drei Zwischenboxen — Funktion und technische Anbindung

Aufgenommen am 2026-08-12. Die Boxen waren an diesem Tag für wenige Stunden
entfernt und sind zurück — als Karten, die auf eine Fläche GEWORFEN werden statt
in einer Spalte zu stehen (siehe „Die Fläche" unten). Die Beschreibung steht,
weil sie beim Entfernen entstanden ist und weil sie beschreibt, was die drei
tragen.

### „In eine Liste sortiert" (`ranked`)

**Funktion.** Die Aufnahme wird gegen 46 vorher festgelegte englische Sätze
gehalten und danach sortiert. Die Box zeigte die ersten acht der ersten Maschine
plus den letzten Platz, darunter die ersten fünf einer zweiten Maschine, dazu
drei erläuternde Zeilen: dass die Liste unsere ist, dass es kein „keins von
diesen" gibt, und wie weit Maschinen kulturelle Unterschiede überhaupt hören
(TISMIR 2025, 125 Hörer:innen, sieben Modelle).

**Anbindung.** `parrot_service.run_chain` → `my_app/services/media_analysis_client`
→ GPU-Dienst, `gpu_service/services/media_analysis_backend.py`. Zwei Modelle,
beide auf denselben Labeln: `clap-music-speech` (CLAP-Music&Speech, auf der Seite
zuerst gezeigt) und `muq-mulan` (MuQ-MuLan). Labelsatz `MUSIC_TAG_VOCABULARY`,
46 Einträge, unsere. Der Wert ist der über Fenster gemittelte Kosinus zwischen
Audio- und Text-Einbettung; es gibt keinen Klassifikationskopf, kein Enthalten
und keinen absoluten Maßstab — nur die Ordnung innerhalb einer Liste trägt.

**Was daran hängt.** Die Stil-Tags des Songs, und die Weiche: `resolve_singer()`
entscheidet an der MuQ-Rangliste, welche der vier Ausgabe-Maschinen singt.

### „In Wörter verwandelt" (`words`)

**Funktion.** Die Aufnahme wird transkribiert. Die Box zeigte den erkannten Text
oder „(diesmal kam nichts zurück)", die Sprache, die die Maschine sich selbst
zugeschrieben hat, eine Übersetzung in die Lesesprache und den Satz, dass Rauschen
und ein leerer Raum genügen, damit diese Maschine flüssige Sätze schreibt.

**Anbindung.** `analysis.transcribe(recording_path, language=...)` gegen denselben
GPU-Dienst; das Modell ist HeartTranscriptor, ein Whisper-Fine-Tune
(`TRANSCRIBER_NAME`). Die Spracherkennung gibt einen NAMEN zurück, keinen Code;
`READING_LANGUAGES` bildet die zehn Plattformsprachen darauf ab. Die Übersetzung
ist eine eigene, kleinere Station (`reading`) über `_read_in()` und dasselbe
Textmodell wie die Schreibstation.

**Was daran hängt.** Ob die Aufnahme überhaupt als „mit Text" gilt — die zweite
Achse der Weiche. Ohne Text: Musik → SA3 Music, sonst SA3 SFX. Mit Text: Gesang →
HeartMuLa, Sprache → Qwen3-TTS.

### „Aufgeschrieben" (`written`)

**Funktion.** Ein Sprachmodell macht aus Rangliste und Transkription zwei Dinge:
eine Tag-Zeile und Lyrics. Die Box zeigte beide und lud dazu ein, beim Hören
mitzulesen — sie ist die Station, die erfindet, und sollte dabei gesehen werden.

**Anbindung.** `_write_song(tags, second, transcription, seconds)` →
`_writer_model()`, das das erste verfügbare aus `STAGE2_INTERCEPTION_MODEL`,
`STAGE1_TEXT_MODEL`, `STAGE3_MODEL`, `CHAT_HELPER_MODEL` nimmt (derzeit
mammouth/glm-5.2). Die Antwort geht durch `_parse_writer_output()`; liefert sie
nicht beides, gilt der Lauf als ungestylt und SA3 bekommt die Lyrics statt der
Tags.

**Was daran hängt.** Der Song selbst. HeartMuLa bekommt Lyrics und Tags, SA3 den
Tag-Text (oder die Lyrics), Qwen3-TTS spricht die Lyrics.

### Warum die Rechenschritte tragen

Alle drei sind tragend: ohne Rangliste keine Tags und keine Weiche, ohne
Transkription keine zweite Achse der Weiche, ohne Schreibstation kein Song.

### Die Fläche

Die Boxen werden wie im Flow auf die Fläche geworfen, in der Reihenfolge von
oben links nach rechts und zur Mitte, ohne exakte starre Positionen, nach
Passung und nie übereinander.

Die vier Boxen — die Aufnahme und die drei, die antworten — liegen nicht mehr in
einem Raster. Ein Raster teilt seine Zellen vorher zu, und genau das ging hier
schief: wenn die erste Box kurz ausfiel, saß die zweite unter einer leeren Zelle,
und die lange Rangliste konnte sich keine Spalte mit den kurzen teilen, ohne dass
eine von beiden beschnitten wurde.

Jetzt entscheidet die GEMESSENE Höhe dessen, was die Maschinen geschrieben haben.
`pack()` in `views/cover_band.vue` gibt jeder Box die Spalte, die gerade am
höchsten endet — bei Gleichstand die linke, was die Reihenfolge aus der oberen
linken Ecke laufen lässt — und setzt sie dort ab, wo diese Spalte aufhört.
Übereinander kann nichts landen. Zwei Spalten, solange 380 px pro Spalte da sind,
sonst eine.

Gemessen und nicht geschätzt: der Text ist so lang, wie die Maschinen ihn gemacht
haben, und er bricht bei jeder Breite neu um. Ein `ResizeObserver` an jeder Box
und an der Fläche ist das Einzige, was das durch eine Übersetzung, eine lange
Rangliste und ein Telefon hindurch richtig hält. Die Boxen selbst sind die
Auswurfboxen des Flusses (`components/FlowCard.vue`), samt Rückseite und
550-ms-Halten — keine zweite Bauart, dieselbe.
