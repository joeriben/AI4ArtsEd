# Nutzungsberichte der Instrumente

Je Fassung ein Ordner (`v1.0/`, …). Die aktuelle Fassung nennt `VERSION` in `devserver/scripts/build_use_reports.py`; ältere Ordner bleiben stehen.

Was sich mit einer neuen Fassung ändert:

- `VERSION` in `devserver/scripts/build_use_reports.py`;
- der Ordner `docs/use_reports/vX.Y/` mit den Berichten;
- die neu gebaute `devserver/my_app/knowledge/use_reports.json` und `ailit_matrix.html` im Ordner der Fassung (ein Lauf des Builds).

Die Prompts in `chat_routes.py`, die Beschreibungen der Werkzeuge in `tool_registry.py` und die Überschrift des Blocks in Help tragen keine Versionsangabe und brauchen keine Änderung; den Block selbst schreibt `platform_items.use_report_block` mit der Fassung aus der JSON.

## V 1.0 (2026-11-06)

33 Berichte `01_flow.md` … `33_lora_explorer.md` und `00_README.md` (Umgebung des Laufs), ein Bericht je Instrument, englisch, in der ersten Person, im Neun-Punkte-Format des Auftrags UCD-374 (Revision 2, 2026-11-02): was getan wurde, was die Bedienelemente taten, was herauskam, Dauer, Stolperstellen, was der Hilfetext sagen sollte, Möglichkeiten, Unterrichtsszenarien, Zuordnung zum AILit-Rahmenwerk (OECD / Europäische Union 2026) aus den eigenen Szenarien: (a) Treffer, (b) mutatis mutandis mit benannter Modifikation, „Beyond the framework“, Non-fits. Lauf 2026-11-02/03 auf dem Dev-Build `e73153cb`; von der Projektleitung Bericht für Bericht korrigiert (2026-11-05/06). Übernommen am 2026-11-06 aus dem Ordner `ucd374_use_reports_2026-11-02` (Commit `108e8c3`). Die Berichte sind die Quelle; sie werden von Hand geändert, der Build liest sie.

`python3 devserver/scripts/build_use_reports.py` liest die Berichte und den Wortlaut des Rahmenwerks (`docs/ailit/learner_expectations.tsv`, `docs/ailit/classroom_scenarios.tsv`) und schreibt `devserver/my_app/knowledge/use_reports.json` (die strukturierte Fassung, die Help und Together lesen) und `ailit_matrix.html` in den Ordner der Fassung (Kompetenzen × Stufen mit der Dichte der (a)-Zuordnungen, (b) zuschaltbar; Instrumente × Kompetenzen; Beyond). Die Seite läuft ohne Server im Browser.

Die JSON trägt die Abschnitte 1 bis 3 und 5 bis 9. Die Zeile zum Lauf und Abschnitt 4 (Dauer) bleiben draußen: Abschnitt 4 hält in allen 33 Berichten fest, dass die Dauer in diesem Lauf nicht messbar war. Seit dem 2026-11-14 bekommen Help und Together mit dem Bericht auch die Abschnitte 1 bis 3 (was getan wurde, was die Bedienelemente taten, was herauskam): Help den Bericht der Seite, auf der jemand steht, beide Agenten ihn über `lookup_place`. Das Handbuch `devserver/trashy_interface_reference.txt` führt seither in Abschnitt 2 keinen Eintrag mehr für eine Seite mit eigenem Bericht; die herausgenommenen Teile stehen im Archiv `docs/analysis/VERWORFEN_help_ailit_vor_v1.0/`. Noch nicht aus V 1.0 gebaut sind der Katalog `devserver/my_app/knowledge/platform_items.json`, die übrigen Abschnitte des Handbuchs und die Übersicht der Orte, die Together bekommt (`devserver/my_app/knowledge/platform_modules.json`).

Entscheidung der Projektleitung, 2026-11-06: V 1.0 ersetzt `docs/ailit/unterstuetzung.tsv` im Agentenpfad; die Tabelle bleibt als Record (`docs/ailit/QUELLE.md`).

## Help-Texte der Seiten aus V 1.0 (Auftrag, 2026-11-07)

Die Help-Texte der 33 Seiten (der Seitentext aus `src/stores/pageAddress.ts`: zwei Hälften, deutsch verfasst, englisch gesetzt) werden aus V 1.0 geschrieben, von einem Sprachmodell außerhalb einer Programmierumgebung (Entscheidung der Projektleitung, 2026-11-06). Der Auftrag dazu steht in `ANSPRACHEN_HELP_TEXTE_AUFTRAG_2026-11-07.md`. Das Material je Seite (heutiger Text in beiden Sprachen mit Quellkommentaren, Herkunft der Sätze, Abschnitte 5 bis 7 des Berichts, Änderungen der Fläche seit dem Build) steht in `ANSPRACHEN_HELP_TEXTE_MATERIAL_2026-11-07.md`; es ist aus den Berichten und den Sprachdateien erzeugt und wird mit dem Auftrag und dem Ordner `v1.0/` übergeben. Die Lieferung redigiert die Projektleitung; danach setzt eine Programmiersitzung die Texte (`de.ts`, `en.ts`, `PAGE_ADDRESSES`, `WORK_ORDERS.md`).

Eine Lieferung liegt nicht im Baum. Sie entsteht aus dem Auftrag und dem Material in einem Sprachmodell außerhalb einer Programmierumgebung und wird danach redigiert; erst dann werden die Texte gesetzt (de.ts, en.ts, PAGE_ADDRESSES, WORK_ORDERS).