# AI4ArtsEd AI Lab — Plattform-Überblick

*Eine pädagogische Plattform für reflexive Auseinandersetzung mit generativer Künstlicher Intelligenz.*

Dieses Dokument richtet sich an **Administrator*innen** (die die Plattform betreiben) und an **Endnutzer*innen** (die mit ihr arbeiten). Es beschreibt Aufbau, Funktionsweise und pädagogische Logik der Plattform in einer Form, die ohne Code-Lektüre verständlich ist. Für tiefer gehende technische Details siehe das englischsprachige [TECHNICAL_WHITEPAPER.md](./TECHNICAL_WHITEPAPER.md).

---

## 1. Was ist das AI Lab?

Das AI4ArtsEd AI Lab ist eine eigenständige, vom UNESCO Chair in Digital Culture and Arts in Education (UCDCAE) der Friedrich-Alexander-Universität Erlangen-Nürnberg entwickelte Open-Source-Plattform. Sie ist nicht primär ein Werkzeug zur Erzeugung von Bildern, Klängen oder Videos, sondern eine **Lernumgebung**, in der die Verarbeitungsschritte generativer KI sichtbar, editierbar und reflektierbar gemacht werden.

Die Plattform versteht sich als pädagogisches Labor, nicht als Produktionswerkzeug. Im Vordergrund steht nicht die Optimierung von Ergebnissen, sondern die **bewusste Verfremdung, Brechung oder Perspektivverschiebung** von Eingaben — eine Praxis, die das Projekt *Prompt Interception* nennt. Lernende sollen erfahren, *wie* eine KI-Generierung zustande kommt, *wo* sie eingreifen können und *welche* Spielräume die Modelle eröffnen oder verschließen.

## 2. Pädagogische Grundprinzipien

Sechs Prinzipien tragen das Plattformdesign:

1. **Trennung von WAS und WIE.** Die kreative Idee (das *Was*) und die gestaltenden Regeln (das *Wie*) werden getrennt eingegeben. Damit wird sichtbar, dass auch ein einfacher Prompt aus zwei verschiedenen Entscheidungsebenen besteht.
2. **Sichtbarkeit der Verarbeitung.** Eingabe, Übersetzung, Interception, Sicherheitsprüfung und Generierung sind als getrennte, einsehbare Stufen realisiert. Nutzer*innen können Zwischenergebnisse korrigieren oder verwerfen.
3. **Sprachmodell als Co-Akteur.** Das beteiligte Sprachmodell wird nicht als unsichtbares Werkzeug behandelt, sondern als sichtbarer Mitwirkender, dessen Beiträge gelesen, akzeptiert oder umgelenkt werden können.
4. **Originalsprachen-Verarbeitung.** Pädagogisch relevante Schritte laufen, soweit sinnvoll, in der Sprache der Eingabe; Übersetzung erfolgt erst spät und kontrolliert.
5. **Zirkularität statt Linearität.** Ergebnisse können wieder zu Eingaben werden; rekursive Pipelines erlauben mehrfaches Durchlaufen einer Operation.
6. **Pädagogische Begleitung.** Die Plattform ist nicht neutral. Sie führt durch Konfiguration, Sicherheitsstufen, Reflexionsangebote und altersspezifische Ansprache aktiv durch den Lernprozess.

## 3. Die vier Verarbeitungsstufen

Jede Generierung im AI Lab durchläuft vier didaktisch motivierte Stufen:

- **Stufe 1 — Eingangsprüfung.** Übersetzung der Eingabe und Prüfung auf rechtlich problematische Inhalte (DSGVO-relevante Personennamen, §86a-Symbolik).
- **Stufe 2 — Prompt Interception.** Pädagogisch-reflexive Transformation: Verfremdung, Brechung oder Perspektivverschiebung des Prompts gemäß einer ausgewählten Strategie. Dies ist das *Herzstück* der Plattform.
- **Stufe 3 — Sicherheits- und Übersetzungsstufe.** Erneute Prüfung des transformierten Resultats auf Sicherheitskategorien (Llama-Guard-S1–S13), Übersetzung in die Zielsprache der Generierungsmodelle.
- **Stufe 4 — Medienproduktion.** Eigentliche Generierung des Bildes, Klangs, Musikstücks, 3D-Modells oder Videos.

Die strikte Trennung erlaubt es, mehrere mediale Ausgaben parallel auf demselben Stage-2-Resultat aufzusetzen — die Interception muss nicht für jedes Medium neu durchlaufen werden.

## 4. Drei-Schichten-Logik: Bausteine, Pipelines, Konfigurationen

Die Plattform trennt konsequent drei Architekturebenen:

- **Bausteine** (englisch *Chunks*) sind generische technische Primitive: "manipuliere Text", "erzeuge Bild mit Stable Diffusion 3.5", "erzeuge Klang", "übersetze".
- **Pipelines** legen fest, in welcher Reihenfolge und Struktur diese Bausteine zusammenwirken — sequentiell, rekursiv, mit zwei Eingaben oder mit Bild-Eingabe.
- **Konfigurationen** sind die didaktischen Szenarien selbst, einschließlich aller pädagogischen Texte, Hinweise, Beispiele und Anweisungen an die Sprachmodelle.

**Für Administrator*innen wichtig:** Pädagog*innen können neue Szenarien anlegen, ohne in Programmlogik einzugreifen. Es genügt, eine Konfigurationsdatei zu erstellen oder anzupassen.

## 5. Entkopplung von Interception und Medialität

Eine zentrale Eigenheit des AI Lab: Es ist *unabhängig* gewählt, *welcher* reflexive Eingriff erfolgt und *welches* Medium am Ende erzeugt wird. Dieselbe Interception kann in beliebige Medialitäten münden — Bild, Klang, Musik, 3D-Modell oder Video. Eine Medialität nimmt umgekehrt beliebige Interceptions auf. Diese kombinatorische Offenheit erlaubt Vergleichsexperimente: dieselbe Reflexion in verschiedenen Medien, dieselbe Medialität unter verschiedenen Reflexionsperspektiven.

## 6. Pädagogische Strategien

Das AI Lab stellt mehrere distinkte *Transformationsstrategien* bereit, die jeweils eine eigenständige Bedienoberfläche und didaktische Logik haben:

- **Stille Post.** Ein Prompt iteriert mehrfach durch zufällige Sprachen; Bedeutung verschiebt sich, Sinn entgleitet — der Klassiker als algorithmisches Sprachspiel.
- **Surrealizer.** Verschiebung im semantischen Vektorraum, gesteuert durch einen Schieberegler: produktive Irritation des Bildmodells.
- **Partielle Eliminierung.** Gezielte Stummschaltung einzelner Dimensionen des semantischen Raums; sichtbar wird, wo das Modell Bedeutung speichert.
- **Split & Combine.** Kontrollierte Vermischung zweier konzeptueller Eingaben — semantische Alchemie zwischen zwei Ideen.
- **Direct Pass-Through.** Ohne Interception, als Vergleichsbasis und Kontrollpunkt.
- **Multi-Image-Transformation.** Eine Bildvorlage parallel unter mehreren Perspektiven verarbeitet — plurale Lesarten desselben Artefakts.

Jede Strategie ist nicht eine Variante eines Schiebereglers, sondern ein eigenes didaktisches Konzept.

## 7. Vielfalt der Interceptions

Innerhalb der Stufe-2-Prompt-Interception bietet die Plattform eine umfangreiche Sammlung kuratierter Interceptions, gegliedert in didaktische Familien:

| Familie | Beispiele | Didaktischer Kern |
|---|---|---|
| Kunsthistorisch-bildgrammatisch | Bauhaus, Renaissance, technische Zeichnung, Fotografie verschiedener technischer Epochen | Stilkonventionen als erkennbare Wahrnehmungsregeln, nicht als Imitation |
| Transkulturell-poetisch | Basho, Hölderlin, Mirabai, Nahuatl, Sappho, Yoruba Oriki | Nicht-eurozentrische lyrische Strukturen; produktive Modellgrenzen als Lerngegenstand |
| Strukturell-dekonstruktiv | The Opposite, Cliché-Filter, Cooked Negatives, Analogue Copy | Inversion, Entstellung, systematische Verfremdung |
| Ideologisch-perspektivisch | One World, Mad World, Forceful, Sensitive, Confucian Literati | Weltanschauliche Geladenheit von Prompts als Thema |
| Sprachlich-soziolektisch | Jugendsprache, Pig Latin | Sprache als manipulierbares Material |
| Diagrammatisch-schematisch | Scene Graph, Planetarizer | Übersetzung von Bildwelten in formale Strukturbeschreibung |
| Generativ-creative-coding | p5.js, Tone.js | Code als künstlerisches Ausdrucksmedium |
| Latent-experimentell | Latent Lab, Surrealizer, Hunkydory Harmonizer | Eingriff in interne Modellrepräsentationen |
| Workshop-spezifisch | Stille Post, Overdrive | Soziale Sprachspiele algorithmisiert |

Im Frontend erscheinen diese als Auswahlkacheln mit Vorschau, Kategorie und Altersfreigabe.

## 8. Reflexive Rekursion

Im Unterschied zum reinen *directional graph* von ComfyUI implementiert das AI Lab explizit **rekursive Pipelines**. Beispiele: eine Stille-Post-Variante mit acht Sprachiterationen, eine textuelle Selbsttransformation über mehrere Durchläufe. Der dekonstruktive Eingriff wird damit zu einem in seinem Verlauf beobachtbaren Prozess. Zwischenergebnisse jeder Stufe sind sichtbar und können von Teilnehmenden korrigiert, verworfen oder umgelenkt werden.

## 9. Multimodale Generierung

Die Plattform integriert mehrere Modalitäten in einer einheitlichen pädagogischen Logik:

- **Bild:** Stable Diffusion 3.5 Large (über ComfyUI und über das eigene Diffusers-Backend), GPT-Image, ergänzende Modelle
- **Klang:** Stable Audio Open
- **Musik:** Multilinguales, mit differenziertem Tag-System arbeitendes Generierungsmodell
- **3D-Modell:** Hunyuan3D
- **Bild-zu-Bild & Bild-zu-Video:** experimentelle Linien

Jeder Pfad ist in dieselbe vierstufige Verarbeitung mit identischen Sicherheits- und Interception-Garantien eingebettet.

## 10. Sicherheitssystem

Das Safety-System adressiert **drei voneinander unabhängige Schutzanliegen** mit jeweils eigenen Mechanismen:

- **Datenschutz (DSGVO).** Sprachverarbeitende Vorerkennung von Personennamen (SpaCy NER) plus lokales Verifikationsmodell. Ergebnis "fail-closed": bei Unsicherheit → Block.
- **Strafrechtliche Symbolik (§86a StGB).** Schlüsselwortfilter plus Sicherheitsmodell der Llama-Guard-Familie mit den Schadenskategorien S1–S13. Generierungs-relevant blockierend: S1–S4, S8–S11.
- **Jugendschutz.** In die Stufe-2-Interception integriertes pädagogisches Vorprompt, das altersgerechte Anpassungen vornimmt, statt nur zu blockieren.

Eine ergänzende **Bild-Nachprüfung** über ein Vision-Sprachmodell prüft generierte Bilder bei Kinder- und Jugendlich-Stufe.

**Vier Sicherheitsstufen:** *kids*, *youth*, *adult*, *research*. Sie werden serverseitig kontrolliert und sind durch Endnutzer-Interaktion *nicht* umgehbar. Höhere Freigaben sind lizenzrechtlich an institutionelle Trägerschaft mit ethischer Aufsicht gebunden.

**Für Administrator*innen wichtig:** Die Sicherheitsstufe wird in `user_settings.json` konfiguriert. Eine versehentliche Senkung der Stufe muss durch Workshop-Verantwortliche bewusst herbeigeführt und ist im laufenden Betrieb sichtbar.

## 11. GPU-Service und Deployment-Flexibilität

Lokale Sprachmodelle, Diffusionsmodelle und Musikmodelle laufen koordiniert über einen eigenen **GPU-Service** auf Port 17803. Dieser Dienst bündelt alle GPU-gebundenen Aufgaben, koordiniert den Speicher und ist über eine einheitliche Schnittstelle ansprechbar.

**Wichtig für Deployment:** Die Plattform ist explizit so gestaltet, dass sie auch **ohne** den GPU-Service betrieben werden kann. Auf Schulrechnern und Workshop-PCs, auf denen nur ComfyUI verfügbar ist, fällt die Plattform automatisch auf ComfyUI zurück. Modelle müssen dann als eigenständige Dateien in `models/` von ComfyUI vorliegen — ohne externe Modellcaches oder Cloud-Zugang.

## 12. Property-Canvas: Bedienoberfläche

Als Einstiegsoberfläche dient ein **Property-Canvas** (auch als Quadrant- oder Bubble-Auswahl realisiert): Statt Nutzer*innen mit einer langen Konfigurationsliste zu konfrontieren, werden Szenarien in didaktisch motivierten Kategorien als gruppierte, bildlich annotierte Auswahlflächen dargeboten. Konfigurationen erscheinen mit Vorschau, Kategorie und Altersfreigabe. Der explorative Zugang funktioniert ohne Vorwissen über Pipelines oder Modelle.

## 13. Trashy: Reflexionsagent

In das AI Lab integriert ist eine Chat-Komponente namens **Trashy**, die in den Generierungsprozess eingreift, jedoch ausdrücklich nicht als Optimierungs-Werkzeug, sondern als **Gesprächspartner über Ergebnisse**. Trashy kann generierte Bilder direkt analysieren, kommentiert prozessorientiert und ist in seinen Ansprache-Modi an die Sicherheitsstufen angepasst:

- **Kids:** ermutigend-stützend, einfache Sprache
- **Youth:** kritisch-reflektierend, fragend
- **Expert/Research:** fachlich, analytisch

Trashy macht die Tatsache, dass auch der "kommentierende" Teil der Plattform ein Sprachmodell ist, transparent erfahrbar.

## 14. Animationen — Nachhaltigkeit als Designprinzip

Während der Inferenzzeit zeigt die Plattform mehrere interaktive Mikro-Animationen (Pixel-/Sprite-Sequenzen, Eisberg-Schmelz-Szene, Wald-Szene, Rohstoff-Szene), die den Energie- und Ressourcenaufwand der Bildberechnung sichtbar machen. **Live-Daten** zur GPU-Auslastung, abgeschätzten Energie- und CO₂-Kosten sind in altersdifferenzierten Lesarten in die Animationen eingebettet:

- **Kids:** Vergleichende Größenordnungen ("so viel wie ...")
- **Youth:** Quantitative Hochrechnungen ("bei 1000 Bildern ...")
- **Expert:** Direkte Berechnungsformeln (Watt × Sekunden ÷ 3600 × Emissionsfaktor)

Rotierende Wissensbausteine ergänzen die Animationen mit Informationen zu Energie, Daten, Modell, Ethik und Ökologie. Die Animationen sind damit kein Wartebildschirm, sondern ein **eigenständiger pädagogischer Bestandteil**, der die "Kostenlos"-Illusion kommerzieller Generatoren durch eine in den Workflow eingelagerte ökologisch-ethische Reflexionsebene ersetzt.

## 15. Settings & Administration

Das Settings-Modul ist ein eigenständiges, mehrteiliges Verwaltungsinterface:

- **Allgemein:** Sicherheitsstufe, Sprache, Bedienmodus (Kids/Youth/Expert).
- **Modell-Konfiguration:** Für jede Verarbeitungsstufe (Eingangsprüfung, Interception, Optimierung, Sicherheits-Verifikation, Übersetzung, Bildanalyse, Chat) kann ein passendes Sprachmodell ausgewählt werden — wahlweise lokal oder über DSGVO-konforme europäische Anbieter (Mistral, IONOS, Mammouth) oder, mit Warnungen, US-basiert (Anthropic, OpenAI, OpenRouter).
- **Modell-Matrix:** Macht Hardware-Anforderungen transparent (VRAM-Tiers von 8 bis 96 GB) und bietet vorausgewählte Konfigurationen für unterschiedliche Geräteklassen.
- **Backend-Status:** Echtzeit-Anzeige geladener Modelle und Hardware-Auslastung.
- **API-Verwaltung:** Visualisierung laufender Kosten externer Anbieter, Budget-Übersicht, Provider-Status.

**Für Administrator*innen wichtig:**

- API-Keys werden in separaten `*.key`-Dateien gespeichert, die per `.gitignore` ausgeschlossen sind. **Niemals** in JSON-Dateien.
- Ein Hot-Reload-Endpunkt erlaubt das Übernehmen neuer Einstellungen ohne Server-Neustart.
- Die Modell-Matrix kann direkt in der Anwendung als JSON editiert werden (passwortgeschützt).
- DSGVO-Status wird per Modell und Provider als grün/gelb/rot kenntlich gemacht.

## 16. Internationalisierung

Die Plattform ist mehrsprachig konzipiert. Die Internationalisierungs-Infrastruktur ist auf eine offene Anzahl von Zielsprachen skalierbar und unterstützt sowohl westliche als auch nicht-westliche Schriftsysteme einschließlich rechts-nach-links laufender Sprachen. Dies ist nicht primär technisch motiviert, sondern Konsequenz des UNESCO-Auftrags der Trägereinrichtung: Eine pädagogische KI-Plattform, die in mehrsprachigen Klassenzimmern arbeitsfähig sein soll, kann sich nicht auf eine Verkehrssprache beschränken.

Sicherheits- und Konsensseiten sind in allen aktiven Sprachen verbindlich. Neue Übersetzungen werden über einen halbautomatisierten Übersetzungsworkflow (Agent-basiert) gepflegt — siehe `src/i18n/WORK_ORDERS.md`.

## 17. Open Source und institutionelle Verankerung

Das AI Lab steht fortlaufend als Open Source zur Verfügung. Die Lizenzierung sieht vor, dass die *Forschungs*- und *Erwachsenen*-Sicherheitsstufen rechtlich an institutionelle Trägerschaft mit ethischer Aufsicht gebunden sind, während die niedrigschwelligen, pädagogisch ausgelegten Stufen (kids, youth) frei nutzbar bleiben. Details siehe `LICENSE.md`.

Die Plattform wird einheitlich dem **UCDCAE AI LAB** des Erlanger UNESCO Chairs in Digital Culture and Arts in Education zugeordnet, nicht einzelnen am Verbund beteiligten Stellen.

---

## Anhang A: Typische Nutzungsmuster

**Workshop mit Kindern (Sicherheitsstufe *kids*):**
1. Pädagog*in wählt eine kunsthistorische oder spielerische Interception (z.B. Bauhaus, Stille Post).
2. Kinder geben einen Prompt in ihrer Sprache ein.
3. Plattform durchläuft die vier Stufen, zeigt Zwischenergebnisse zur Reflexion.
4. Trashy kommentiert ermutigend.
5. Animationen machen Energieverbrauch sichtbar.

**Forschungseinsatz (Sicherheitsstufe *research*):**
1. Forschende wählen mehrere Output-Konfigurationen für Vergleichsexperimente.
2. Prompt wird einmal durch Stufe 1–2 geführt, Ergebnis fließt parallel in mehrere Stufe-4-Generierungen.
3. Vergleichsexport ermöglicht Auswertung.

## Anhang B: Wichtige Dateien für Administrator*innen

| Datei | Zweck |
|---|---|
| `user_settings.json` | Sicherheitsstufe, Modell-Slots, Provider-Auswahl |
| `*.key` | API-Schlüssel externer Provider (gitignored) |
| `devserver/schemas/configs/interception/*.json` | Pädagogische Szenarien (Interceptions) |
| `devserver/schemas/configs/output/*.json` | Output-Konfigurationen (Bild/Audio/Musik/3D) |
| `LICENSE.md` | Lizenzierung und institutionelle Bindung |
| `docs/TECHNICAL_WHITEPAPER.md` | Vertiefte technische Dokumentation (Englisch) |
| `docs/ARCHITECTURE PART *.md` | Architektur-Detailbeschreibungen |

## Anhang C: Verwandte Dokumentation

- [TECHNICAL_WHITEPAPER.md](./TECHNICAL_WHITEPAPER.md) — Englisch, technisch detailliert
- [00_MAIN_DOCUMENTATION_INDEX.md](./00_MAIN_DOCUMENTATION_INDEX.md) — Gesamtindex
- [ARCHITECTURE PART 29 — Safety-System.md](./ARCHITECTURE%20PART%2029%20-%20Safety-System.md) — Sicherheitsarchitektur
- [ARCHITECTURE PART 31 — GPU-Service.md](./ARCHITECTURE%20PART%2031%20-%20GPU-Service.md) — GPU-Service-Architektur
- [LICENSE.md](../LICENSE.md) — Lizenzbedingungen
