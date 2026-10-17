# Die Zeichnungen der Übersichtskarte des Latent Lab — Bauregeln

Gilt für die zwölf Stationen in `public/ai4artsed-frontend/src/views/latent_lab/flow_stations.vue`,
die auf `/latent-lab/overview` in den Kästen der Karte stehen (`flow_logic.vue`).
Zeilenangaben beziehen sich auf den Stand vom 2026-08-26.

Diese Datei führt fort, was in `docs/ELEMENT_STRUCTURE_REGISTRY.md` unter
`flow-logic-map` bindend festgelegt ist, und widerspricht dort nichts. Die zwei
Sätze, an denen alles hängt, stehen dort: **„Der Inhalt eines offenen Knotens ist
eine Zeichnung, kein Absatz"** und **„In der Zeichnung ist NICHTS in festen
Breiten gesetzt."** Was hier steht, sind die Regeln, nach denen die zwölf
Zeichnungen tatsächlich gebaut sind — abgelesen an ihnen, nicht erfunden.

Wer eine Station baut oder ändert, liest zuerst Abschnitt 1 (sonst schrumpft die
Schrift) und Abschnitt 8 (sonst ist die Änderung ungeprüft).

---

## 1. Die Fläche und der Maßstab

**R1. Jede Station hat zwei Zeichnungen, und die kleine ist keine verkleinerte große.**
Groß `930 × 320` (Innenraum `910 × 304`), klein `300 × 76` (Innenraum `288 × 70`).
Beleg: `flow_stations.vue`, `VB`. Beide liegen in derselben Datei hinter dem
`mini`-Schalter, weil beide die Zeichnung dieser Station sind. **Die Höhe der
großen Form stand bis zum 2026-08-26 auf 260 und ist seither 320** — die
Begründung und die Messung dazu stehen in R5a. Hier standen die alten Zahlen
noch bis zum 2026-08-29.

**R2. Nichts wird in festen Breiten gesetzt.**
Jeder `<text>` meldet sich über `tr('name')` an, `getComputedTextLength()` misst
ihn nach dem Mount, nach dem Nachladen der Schrift und bei jedem Sprachwechsel;
`w('name', fallback)` gibt das Maß in Nutzereinheiten zurück, und die Geometrie
wird daraus gerechnet. Beleg: `flow_stations.vue:1043-1072` (Messung),
`1718-1791` (`case 'transformer.vectors'` rechnet die ganze Karte daraus).
Gegenprobe: die erste Fassung war auf die englischen Beschriftungen bemessen, und
das deutsche „trained — works out what to take away" lief geradewegs aus seinem
Kasten.

**R3. Der Maßstab ist `min(1.25, 910/bboxBreite, 304/bboxHöhe)`, gemessen an dem,
was TATSÄCHLICH gezeichnet ist.**
Beleg: `flow_stations.vue:1954` und `1959` (`getBBox()` der Gruppe, zentriert auf
den gezeichneten Kasten, nicht auf die nominellen 930). Auf die nominellen 930 zu
zentrieren schiebt die rechte Beschriftung über die Kante, die das
Herunterrechnen retten sollte.

**R4. Eine Karte darf nicht unter Maßstab 0,97 fallen.**
Darunter wird die Schrift der Zeichnung kleiner als die Schrift der Seite um sie
herum, und genau das war die Klage, aus der die 1,25-Wachstumsgrenze entstand.
Gemessen am 2026-08-26 nach der Korrektur aus R5a: Prompt (Diffusion) 1,25 ·
Tokenisierung und Embedding 0,9764 · Attention 0,8649 · Sampling 1,0332.
Attention ist die eine Karte, die die Regel noch verletzt — dort bindet seit der
Korrektur die BREITE (910/1053), nicht mehr die Höhe.

**R5a. Die Fläche ist höher, als der viewBox lange behauptet hat — miss sie,
statt sie zu glauben.**
Der viewBox der großen Form stand bis zum 2026-08-26 auf `930 × 260`. Die
geöffnete Kachel ist aber keine so flache Leiste: an sieben Fenstergrößen
gemessen gibt ihr SVG zwischen 338 und 364 Einheiten Höhe her, **ohne dass die
Zeichnung dabei im geringsten kleiner wird** — es bindet die Breite, nicht die
Höhe, und die überschüssige Höhe wurde schlicht nicht benutzt. Rund achtzig
Einheiten lagen brach, und die Stationen wurden an einer Grenze zusammengeschoben,
die es nicht gab: Attention stand deswegen bei 0,79. Der viewBox steht jetzt auf
`930 × 320` (`ih` 304), mit Rand bis zur schmalsten gemessenen Lage.
Beleg: `flow_stations.vue`, `VB`. Gegenprobe: dieselbe Karte, dieselbe Zeichnung,
Maßstab 0,60 → 0,98 allein durch Höhe, die schon da war.

**R5. Höhe ist knapper als Breite. Wer Höhe hinzufügt, muss Höhe einsparen.**
Bei den vier Transformer-Karten bindet die Höhe, nicht die Breite: die
Tokenisierungs-Karte stand vor dem Umbau bei `893,9 × 249,8` — 16 Einheiten
Breite frei, 5 Einheiten Höhe frei. Eine zusätzliche Zahlenzeile kostet 15
Einheiten Höhe, eine zusätzliche Textzeile 12. Deshalb: **zuerst prüfen, ob das
Neue seitwärts kann.** Der Exkurs der Tokenisierungs-Karte stand bis zum
2026-08-26 ÜBER dem Embedding und drückte es 24 Einheiten die Karte hinunter;
seit er in einer eigenen Spalte daneben steht, ist der Platz für die drei
Zahlenzeilen da (`flow_stations.vue:441-459`, `1764-1765`).

---

## 2. Die dunkel abgesetzte Fläche

**R6. Eine gestrichelte, dunkel gefüllte Fläche umschließt das INNERE einer
benannten Sache, in die man nicht hineinsehen kann.**
Immer dieselben Werte: `fill="#0f0f0f" fill-opacity="0.5" stroke="#4a4a4a"
stroke-dasharray="5 5" rx="14"`. Vier Belege, vier Sachen:
Encoder (`flow_stations.vue:118-119`), Latentraum (`185-186`), der
zusammengesetzte verdeckte Text (`344-345`), der Transformer (`525-526`).
Seit 2026-08-26 fünftens das Embedding (`465-466`).

**R7. Der Name steht ÜBER der Fläche, nie in ihrer Ecke.**
Und in der Form *Fachwort (`t-term`) · Doppelpunkt · Satz*.
Beleg: `flow_stations.vue:190-191` (Latentraum), `346-347` (verdeckter Text),
`462-464` (Embedding). Gegenprobe: ein Satz dieser Länge in der Ecke der Fläche
liest sich als etwas, das in ihr gezeichnet ist.

**R8. Zweite Bauart, andere Bedeutung: ein UNGEFÜLLTER Kasten mit hellerem
Strich ist eine Nebenbemerkung, kein Mechanismus.**
`fill="none" stroke="#5a6a80" stroke-dasharray="5 4"`. Beleg: der
Vergleichskasten der Attention-Karte, `flow_stations.vue:572-573`.

**R9. Höchstens EINE gefüllte Fläche je Karte.**
Ein zweiter gefüllter Rahmen daneben liest sich als zweiter Mechanismus. Ein
Exkurs bekommt eine senkrechte Linie (`flow_stations.vue:443-444`) oder die
Einfassung nach R8 — keinen zweiten Rahmen.

**R10. Was offen bleibt, ist das, was die lesende Person selbst nachprüfen kann.**
Auf der Tokenisierungs-Karte bleibt die Zerlegung offen (man liest die Stücke des
eigenen Satzes und kann sie zählen); das Embedding steht in der Fläche (2.560
Zahlen je Token, von denen sechs gezeichnet sind). Diese Unterscheidung, nicht
der Wunsch nach Struktur, entscheidet, was eingefasst wird.

---

## 3. Der Erläuterungstext am Fuß

**R11. Ein Text UNTER der Zeichnung gehört einer Station, die als GANZE etwas
erklärt, nicht einem ihrer Kästen.**
Beleg: `flow_stations.vue:240-242` (Denoiser, die erste Station mit einem
solchen Text, 2026-08-23), `596-597` (Attention), `506-507` (Tokenisierung).

**R12. Er wird deutlich abgesetzt: mindestens 14 Einheiten unter der letzten
gezeichneten Kante.**
Beleg: `flow_stations.vue:1768` — `closeY = 130 + frameH + 14`, und die
gestrichelte Kante darüber tut den Rest der Arbeit.

**R13. Der Zeilenabstand beträgt mindestens das 1,3-fache des Schriftgrads.**
Bei `t-dim` (9 px) also ≥ 12, bei `t-sub` (10 px) ≥ 13.
Beleg: `flow_stations.vue:507` (12), `624` (13), `240` (15).
Gegenprobe: der Schlusstext der Tokenisierungs-Karte stand auf 11 bei 9 px,
die Sprachnamen des Exkurses auf 8 bei 9 px — die Oberlänge der einen Zeile saß
in der Unterlänge der darüber. Jetzt 12 bzw. 11 (`flow_stations.vue:451-455`,
`507`).

**R14. Wo eine Zeile bricht, entscheidet die Sprachdatei, nicht das Layout.**
Die Zeilen kommen als `\n`-getrennter Schlüssel (`close`, `note`, `langNote`) und
werden ungebrochen gesetzt. Beleg: `flow_stations.vue:1351-1353`. Ausnahme sind
Beschriftungen IN Kästen: `twoLines()` (`1083`) und `nLines()` (`1094`) brechen
an der Leerstelle nächst der Mitte, ohne Trennliste, und beide Hälften werden
wie jeder andere Text gemessen.

**R15. Der Fußtext wiederholt nicht, was die Zeichnung schon sagt.**
Gegenprobe: der Schlusstext der Tokenisierungs-Karte begann mit „Das KI-Modell
zerlegt jeden Text in Token." — demselben Satz, der zwei Handbreit darüber als
`cutLabel` steht. Ebenso stand „Jede Zahlenreihe hat 2.560 Zahlen." als eigene
Angabe rechts, während jede der drei Zahlenzeilen mit „… 2.560 Zahlen" endet;
der Schlüssel `width` ist deshalb am 2026-08-26 entfallen.

---

## 4. Pfeile und Richtung

**R16. Ein Pfeil ist eine Linie in `#8b98a9` mit `marker-end="url(#fsArrow)"`.**
Eine Linie OHNE Spitze verbindet, ohne eine Richtung zu behaupten.
Beleg mit Spitze: `flow_stations.vue:198`, `205`, `212` (die Schleife des
Denoisers). Beleg ohne Spitze: `133` — die drei Encoder laufen auf einen
Sammelpunkt zu, und was dort geschieht, ist Zusammenlegen, keine Bewegung.

**R17. Gestrichelt (`stroke-dasharray="4 5"`) ist der Rückweg.**
Beleg: `flow_stations.vue:223-226` — der einzige Weg zurück auf der ganzen Karte,
und die Pointe des Denoisers. Die Karte läuft sonst nach unten und nach rechts.

**R18. Ein Pfeil, auf dem etwas steht, wird in zwei Stücken gezeichnet.**
Beleg: `flow_stations.vue:223-227` — die Pille sitzt AUF dem Rückweg, also lässt
der Weg ihr den Platz, statt unter ihr durchzulaufen.

---

## 5. Farbe

**R19. `#4CAF50` (Grün) ist reserviert für das Eigene und das Gemeinte.**
Die Token, deren Zahlenreihe gezeigt wird (`flow_stations.vue:421`, `475`), die
eine lesende Stelle im Transformer (`547`), der Balken der gerade gelesenen
Sprache (`454`), die Marken (`2007-2020`). Deshalb ist eine Marke **Ring und
Kern**, keine gefüllte Scheibe: ein voller grüner Punkt wäre von den grünen
Chips der Zeichnung nicht zu unterscheiden.

**R20. Fachwörter tragen alle dieselbe Farbe (`t-term`, `#c9b6ff`), und WELCHES
Wort das Fachwort ist, entscheidet die Sprachdatei.**
Markiert mit `[[…]]`, aufgelöst von `segments()`
(`flow_stations.vue:1494-1503`). Beleg: `144-145`, `264`, `416-417`.
Nicht im Layout festlegen — welches Wort das Fachwort ist, ist eine Frage an den
Satz DIESER Sprache.

**R21. Die übrigen Farben sind eine feste Zuordnung, keine Wahl.**
`#7f77dd` auf `#0f0f0f` = geschriebener Text (`61-62`, `327`);
`#3f6a9c` auf `#1d2f45` = Maschinenteil und Zahl (`123`, `479`);
`#4a2b2f`/`#7a4046` = Material am Ausgang (`275`, `711`);
`#141b26`/`#2c3a4c` = Steuerzeichen (`420-421`);
`#151515`/`#4a4a4a` = etwas, das nicht das Modell ist (`207`, `349`).

**R22. Eine Farbrampe berührt an keinem Ende das Grün.**
Beleg: `flow_stations.vue:1292-1301` — der Streifen läuft von kühl über dunkel
nach warm, damit keine Zelle als „diese ist gemeint" gelesen werden kann.

---

## 6. Token, Zahlen und Belege

**R23. Token stehen in Chips, nie als freistehender Fließtext — und ein Chip ist
so breit wie sein Wort.**
Beleg: `flow_stations.vue:418-429` und `1729-1741` (jeder Chip aus seinem
eigenen Maß, eine Lücke nur so breit wie ihre Punkte). Ausnahme mit Grund: die
Encoder-Station setzt die Token als eine Reihe OHNE Kästchen
(`flow_stations.vue:1467-1484`) — ein Kästchen je Token ließe sie als Wörter
lesen, und die Hälfte sind keine.

**R24. Eine Zahl in einer Zeichnung ist gemessen, oder die Schlusszeile sagt,
dass sie beispielhaft steht.**
Beleg gemessen: `de.ts` / `en.ts`, `latentLab.flowLogic.transformer.vectors.rows`
und `.langs`.
Beleg ausgewiesen: `transformer.sampling.note`, letzte Zeile („Die Zahlen auf
dieser Zeichnung stehen beispielhaft."), und `transformer.block.close`, letzte
Zeile. **Wer eine Zahl nicht messen kann, lässt die Zeile weg.**

**R25. Was gemessen NICHT gilt, wird nicht gezeigt.**
Die Karte behauptete einmal, die Zahlenreihe eines verwandten Wortes liege der
des Beispielworts näher als die eines entfernten. An Qwen3-4B gemessen ist das
falsch (`␣Wohnung` +0,180 zu `␣Haus`, `␣Wasser` +0,185, zufälliges Paar +0,082 im
Mittel, 95 % bei +0,188). Auf der Eingangsschicht steht die Bedeutung nicht in
den Zahlen; der Farbstreifen trägt deshalb KEINE Ähnlichkeitsaussage, und der
Kommentar an ihm sagt das (`flow_stations.vue:487-494`).

**R26. Ein Steuerzeichen steht klammerfrei in der Sprachdatei.**
Ein senkrechtes `|` ist der Plural-Trenner von vue-i18n und zerschneidet die
Nachricht. Also `im_start` im Schlüssel, `<|…|>` in der Zeichnung.
Beleg: `flow_stations.vue:424-427`, `621-623`.

---

## 7. Beschriftung, Marke, Sprache

**R27. Eine Bildunterschrift hängt an ihrem Gegenstand.**
Mittig unter ihm, mit einer Mitte, die aus der Messung kommt.
Beleg: `flow_stations.vue:430-434` mit `1735-1742` — „ein Steuerzeichen" steht
auf der Mitte des Steuerzeichen-Chips, „aus einem Wort werden vier Token" auf der
Mitte der vier Chips, die dieses Wort sind.
Gegenprobe: die Marke der Prompt-Station saß mittig neben drei Sprachkacheln,
deren Mitte GENAU die mittlere Kachel ist — sie las sich als „Deutsch", gemeint
war die geschriebene Zeile.

**R28. Eine Beschriftung, die auf zwei Dinge zeigen könnte, nennt ihren
Gegenstand.**
Gegenprobe: „dieselbe Zahlenreihe als Muster" stand unter EINER Zahlenzeile und
war eindeutig. Unter dreien ist es das nicht mehr, also heißt es seit dem
2026-08-26 „die Zahlenreihe von „␣Haus" als Muster".

**R29. Eine Angabe steht bei der Sache, zu der sie gehört, nicht bei der, neben
der Platz war.**
Gegenprobe: „Der Wortschatz des KI-Modells hat 151.936 Token." stand rechts neben
den Zahlenreihen. Der Wortschatz ist das, woraus die ZERLEGUNG schöpft; die
Angabe steht jetzt in der Beschriftungszeile der Zerlegung
(`flow_stations.vue:435-439`).

**R30. Marken sind Daten, und `at` ist ein NAME, keine Koordinate.**
Die Seite sagt, was wo hineinreicht; die Zeichnung weiß, wo dieser Ort liegt
(`flow_stations.vue:1965-1974`, `anchor` je Station). Eine Marke, deren Ort in
der gerade gezeichneten Form nicht vorkommt, wird weggelassen statt auf `[0,0]`
gesetzt.

**R31. Keine Marke auf ein Instrument, das es nicht gibt.**
Sie führte in eine leere Arbeitsfläche. Die Tokenisierungs-Karte trägt deshalb
keine (`anchor: {}`, `flow_stations.vue:1783`): ein sprachvergleichender
Tokenizer wäre das Instrument zu ihrem Exkurs, und der ist nicht gebaut.

**R32. Der Text in den Zeichnungen ist Sachtext, kein Bild.**
Vier Verbote: keine Metapher und keine Vermenschlichung
(„lesen" nur als maschinelles Holen); kein Gedankenstrich, der die Aussage
ersetzt; keine Namen, die die Seite nicht einführt (wo das Modell gemeint ist,
heißt es „KI-Modell"); nichts, was die lesende Person ohnehin weiß, besonders
nichts über ihr eigenes Tun. Die Flächennamen `latent space`, `embedding space`
und `conditioning` bleiben als Fachwörter stehen.

**R36. Die Zeichnung läuft von links nach rechts, und das muss sie auch in `ar`
und `he` festhalten.**
`text-anchor="start"` und `"end"` sind KEINE Seitenangaben — sie folgen der
`direction`-Eigenschaft. Unter dem `dir="rtl"` des Dokuments läuft eine mit
`start` verankerte Beschriftung nach LINKS von ihrem x und eine mit `end`
verankerte nach RECHTS, also spiegelverkehrt zu allem, was R2 aus den gemessenen
Breiten rechnet. Das Ergebnis war nicht eine verschobene Zeile, sondern eine
`getBBox()` von 1602 statt 817 Einheiten und damit eine über die ganze Station
zusammengeschobene Zeichnung. Beleg: `flow_stations.vue`, `.st-svg`
(`direction: ltr`) und `.st-svg text` (`unicode-bidi: plaintext`). Das zweite
gehört zwingend dazu: `direction: ltr` allein setzt auch die ABSATZ-Richtung des
Inhalts, und ein arabischer Satz bekommt dann seinen Punkt ans falsche Ende;
`plaintext` lässt jeden Text seine Absatzrichtung aus seinem eigenen ersten
starken Zeichen nehmen. Gemessen 2026-08-29 (siehe Abschnitt 8). Dieselbe Falle
und derselbe Griff in `components/FlowHeader.vue` (aufrechte
Kantenbeschriftung), `views/latent_lab/bias_archaeology.vue` und
`views/latent_lab/coreference_test.vue` (Achsenzahlen).

**Gespiegelt wird die Zeichnung damit nicht.** Kästen und Pfeile laufen weiter
nach rechts. Ob eine Station für eine rechtsläufig lesende Person gespiegelt
gehört, ist eine Entwurfsfrage und in dieser Datei nicht entschieden.

---

## 8. Prüfen — nicht raten, sondern rendern

Auf dem Fedora-Rechner:

```
cd ~/ai/ai4artsed_development/public/ai4artsed-frontend && npm run build
```

Die Anwendung läuft unter `http://127.0.0.1:17802` (Flask liefert `dist` aus).
Mit `playwright-core` aus `node_modules` und `/usr/bin/chromium-browser` rendern;
im Wegwerf-Profil `usage_agreement_accepted=1` als Cookie setzen (rein
clientseitig geprüft, `src/router/index.ts`) und die Sprache über
`localStorage['ai4artsed_language']` stellen. Dann `/latent-lab/overview` öffnen,
den Kasten über `.fl-name` anklicken und ablesen:

```js
const g = document.querySelector('svg.st-svg g[transform]')
g.getAttribute('transform')   // scale(...) — muss >= 0.97 sein
g.getBBox()                   // Breite <= 910, Hoehe <= 304 (R5a)
```

**Vier Fragen, jede am Bild, nicht an der Zahl:** Überlappt nichts? Kleben keine
Zeilen? Ist nichts abgeschnitten? Steht jede Beschriftung bei ihrem Gegenstand?

**Und mindestens in zwei Sprachen prüfen**, denn die Geometrie kommt aus den
Wörtern. Deutsch läuft etwa ein Fünftel länger als Englisch.

**In `ar` und `he` prüfen, nicht nur in zwei linksläufigen Sprachen.** Bis zum
2026-08-29 liefen dort ALLE elf Zeichnungen weit über ihre Fläche hinaus:
Tokenisierung und Embedding 0,5675 · Attention 0,5091 · Sampling 0,6245 · Prompt
0,8596. Die Ursache steht in R36, behoben ist es dort. Seither liegen `ar` und
`he` Station für Station auf demselben Maßstab wie `en` — was richtig ist,
solange die Zeichnungen in diesen Sprachen noch den englischen Text zeigen.

Die Prüfung dazu sieht sich jeden gezeichneten Text mit `start`- oder
`end`-Anker daraufhin an, ob er auf der Seite seines x liegt, auf der er liegen
soll:

```js
[...document.querySelectorAll('svg text')].filter(t => {
  const a = getComputedStyle(t).textAnchor
  if (a !== 'start' && a !== 'end') return false
  const b = t.getBBox(), x = parseFloat(t.getAttribute('x') || '0')
  const links = b.x + b.width <= x + 0.6
  return a === 'start' ? links : !links
}).length   // muss in JEDER Sprache 0 sein
```

In `de` waren es null, in `ar` neun — verteilt über die Karte und die beiden
Balkendiagramme im Textlabor. Die Zahl ist der schnellste Weg, denselben Fehler
in einer neuen Zeichnung zu finden.

---

## Nachtrag 2026-08-26: die ganze Zahlenreihe

**R33. Wenn eine Zeichnung Messwerte zeigt, dann echte, vollständige und die
eines wirklichen Gegenstands.**
Die Karte „Tokenisierung und Embedding" zeigte 48 von 2.560 Zahlen als Streifen.
Sie zeigt jetzt alle 2.560, als vier Zeilen zu 640 Feldern, und nennt dazu die
Nummer des Token: `␣Haus` ist Nr. 47.375 von 151.936. Die Werte sind die ROHEN
aus `model.embed_tokens.weight` von Qwen3-4B, dieselbe Zeile, aus der auch die
sechs Kommazahlen darüber stammen — nicht die L2-normierte Fassung, die sich um
rund 9 % davon unterscheidet. Wer Zahlen aus zwei Normierungen auf eine Karte
setzt, zeigt zwei Gegenstände und behauptet einen.

**R34. Ein Band aus tausenden Feldern wird als PFAD je Farbstufe gezeichnet, nicht
als Rechteck je Wert.**
2.560 `<rect>` sind 2.560 Knoten, die Vue bei jedem Sprachwechsel neu setzt. Ein
Pfad je Farbstufe, mit gleichen Nachbarn zu einem Strich zusammengefasst, kostet
höchstens 32 Knoten — und hat zwischen gleichfarbigen Feldern keine Naht.
Beleg: `flow_stations.vue`, `VEC`.

**R35. Eine Farbskala braucht ihre Bezifferung neben sich, sonst ist sie Dekor.**
Neben dem Band stehen die Rampe selbst und ihre beiden Enden als Zahl
(`−0,055`/`+0,055`), dazu die Zeile, welche Reihe das Band ist und welches Token
sie trägt. Sie stehen RECHTS NEBEN den Zahlenreihen, wo ohnehin nichts steht —
unter dem Band wäre jede von ihnen eine Zeile mehr, und Höhe ist das Knappe
(R5).
