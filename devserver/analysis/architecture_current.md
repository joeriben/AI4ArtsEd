# Devserver Architektur – aktueller Stand (automatischer Schnappschuss)

> Schnappschuss von vor dem 2026-10-10: die an diesem Tag entfernten Module (Legacy-Workflow-Kette, Ausführungshistorie, die Routen und Dienste ohne Aufrufer) stehen hier noch.

Diese Notiz fasst den derzeitigen Aufbau des Devservers zusammen (Stand: aktueller Commit) und ergänzt ihn um den statischen Inventar-Scan aus `analysis/code_inventory.md`. Schwerpunkt ist der Python-Teil unter `devserver/`.

## High-Level-Übersicht
- **Framework & Entry Point:** Flask-App-Factory in `my_app/__init__.py` registriert alle Blueprints und setzt Cache-Vermeidungs-Header für API-Routen. CORS und Session-Cookies sind bereits konfiguriert. 【F:devserver/my_app/__init__.py†L1-L70】
- **Routingschicht:** Mehrere Blueprints kapseln die API-Oberfläche (`/api/*`), z. B. Streaming-Workflows, Pipeline-Recorder, Exporte, Chat-Hilfen und Media-Endpunkte. Registrierung erfolgt in der App-Factory, statische Auslieferung ist als Fallback zuletzt registriert. 【F:devserver/my_app/__init__.py†L38-L63】
- **Serviceschicht:** Business-Logik liegt in `my_app/services/`. Beispiele:
  - `workflow_logic_service.py`: Laden/Manipulieren von Workflow-JSON, Negative-Prompt-Injektion, Modellpfad-Auflösung (optional). 【F:devserver/my_app/services/workflow_logic_service.py†L1-L78】
  - `comfyui_service.py`: REST-Aufrufe an ComfyUI (Submit, Status-Polling, Media-Download). 【F:devserver/my_app/services/comfyui_service.py†L1-L50】
  - `comfyui_client.py`, `stable_audio_client.py`, `swarmui_client.py`, `ollama_service.py`, `openai_images_service.py`: Klienten für externe Generatoren.
- **Utility-Schicht:** Allgemeine Helfer (`utils/helpers.py`, `utils/workflow_node_injection.py`, `utils/negative_terms.py`, `utils/image_analysis.py`) kapseln Dimensionierung, Modell-Namens-Parsing, Prompt-Injektionen und Bildanalyse.
- **Konfiguration:** Zentrale Konstanten (Modelle, Safety-Level, Ports, UI-Modi, Pfade) in `devserver/config.py`; Stufe-Modelle ersetzen das frühere `execution_mode`. 【F:devserver/config.py†L1-L64】【F:devserver/config.py†L74-L126】
- **Persistenz/History:** `execution_history/` enthält Modelle/Storage-Logik, wird aktuell aber nirgends importiert (siehe Orphan-Liste).
- **Tests & Tools:** Umfangreicher Test-Ordner (`testfiles/`, `tests/`) plus Diagnose-Skripte. Viele davon werden aktuell nicht importiert oder ausgeführt.

## Architektur-Prinzipien vs. Realität
- Die Drei-Schichten-Trennung (Routen → Services → Utils/Clients) ist grundsätzlich vorhanden, aber einige Services greifen direkt auf Config-Konstanten zu (starke Kopplung). Beispiel: `WorkflowLogicService` nutzt globale Flags wie `ENABLE_MODEL_PATH_RESOLUTION`. 【F:devserver/my_app/services/workflow_logic_service.py†L10-L33】
- Naming/Nutzung der Pipeline-Typen folgt den Regeln aus `RULES.md`, jedoch sind mehrere Legacy-/Experiment-Dateien weiterhin aktiv im Baum und erhöhen die Komplexität.

## Inventar-Ergebnisse (aus `analysis/code_inventory.md`)
- **Dateien:** 92 Python-Dateien gescannt; 1 Parsing-Fehler (`services/streaming_response.py`); 48 Dateien werden nicht von anderen Modulen importiert.
- **Funktionen:** 189 Funktionen ohne eingehende Aufrufe (potenziell verwaist oder nur als Entry-Points via CLI/Tests gedacht).
- **Variablen:** 194 Variablen ohne Nutzungs-Referenz (Teilweise Konstanten, Defaults oder ungenutzte Artefakte).
- Details, inkl. Aufruflisten, stehen vollständig in `analysis/code_inventory.md`. 【F:devserver/analysis/code_inventory.md†L1-L120】

## Verwaiste Dateien (Auszug)
Eine vollständige Liste findet sich im Inventar. Hervorzuheben:
- Nicht importierte Kernbestandteile: `execution_history/models.py`, `execution_history/tracker.py`, sowie mehrere Schema-Generatoren unter `schemas/engine/`.
- Tests/Tools: Viele `testfiles/`- und `tests/`-Module sowie Diagnose-Skripte wie `analyze_context_prompts.py` werden aktuell nicht referenziert. 【F:devserver/analysis/code_inventory.md†L23-L52】

## Funktions- und Variablenlage
- Aufruferketten pro Funktion sind im Inventar dokumentiert; zahlreiche Funktionen werden nirgendwo referenziert (z. B. Helper in Testdateien oder ungenutzte Service-Methoden). 【F:devserver/analysis/code_inventory.md†L55-L112】
- Variablen-Scan zeigt viele unbenutzte Konstanten/Module-weite Variablen; Uppercase-Stil ist weit verbreitet (teils sinnvoll als Konstante, teils Legacy). 【F:devserver/analysis/code_inventory.md†L114-L138】

## Identifizierte Schwachstellen
- **Parsing-Fehler:** `services/streaming_response.py` kann nicht geparst werden → muss manuell geprüft werden.
- **Kettenverweise:** Typische 3er-Kette in der Medienerzeugung: Route → Service → Client. Bei einfachen Operationen (z. B. direktes Durchreichen von Requests) könnte man Service und Client zusammenlegen oder die Config-Injektion zentralisieren.
- **Kopplung an globale Config:** Viele Services lesen unmittelbar aus `config.py`; Dependency Injection (z. B. per Konstruktor) würde Tests und Austauschbarkeit verbessern.
- **Legacy-Ballast:** Zahlreiche verwaiste Dateien/Funktionen erzeugen kognitive Last und erschweren Regelkonformität (Trennung Interception/Output-Pipelines).

## Konsolidierungs- und Refactoring-Vorschläge
1. **Parse-Fehler beheben:** `services/streaming_response.py` syntaktisch korrigieren oder als `.obsolete` kennzeichnen.
2. **Orphan-Bereinigung:** Verwaiste Dateien/Funktionen systematisch evaluieren und entweder löschen (per `.obsolete`) oder in die aktive Architektur integrieren. Start mit `execution_history/*` und `schemas/engine/*` empfohlen.
3. **Abhängigkeits-Injektion:** Services (ComfyUI, WorkflowLogic, Export) sollten benötigte Config-Werte beim Konstruktor erhalten, statt globale Konstanten zu lesen → erleichtert Tests und verhindert versteckte Kettenverweise.
4. **Flatten einfacher Chains:** Für reine Proxy-Aufgaben (Route → Service → Client ohne Zusatzlogik) Services zusammenziehen oder klar trennen: Route → Adapter → Client. So lassen sich „A ruft B ruft C“ Ketten reduzieren.
5. **Variablenhygiene:** Uppercase-Variablen, die keine Konstanten sind, umbenennen; ungenutzte Variablen/Default-Werte entfernen oder dokumentieren (z. B. in `config.py`).
6. **Architektur-Doku aktualisieren:** Inventar regelmäßig neu generieren (Script in `analysis/code_inventory.md` dokumentiert) und Änderungen gegen `RULES.md` spiegeln.
