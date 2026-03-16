# Safety System History — Permanente Referenz

**Status:** Authoritative
**Created:** 2026-03-16 (Session 262)
**Purpose:** Complete chronological record of the safety system's evolution — what was built, broken, fixed, and abandoned. Intended as institutional memory to prevent repeating past mistakes.

---

## 1. Drei-Schichten-Modell

The safety system addresses three fundamentally different concerns. Confusing them causes architectural errors.

| Schicht | Concern | Durchsetzung | Fail-Modus |
|---------|---------|-------------|------------|
| **Recht** | §86a StGB (Strafrecht), DSGVO (Datenschutz) | Technisch, immer, automatisch | **fail-closed** — gesetzliche Pflicht |
| **Paedagogik** | Jugendschutz (JuSchG), altersgerechte Inhalte | Technik *unterstuetzend*, Kursleitung *primaer* | Technik fail-closed, aber primaere Verantwortung liegt bei Paedagogen |
| **Organisation** | Nutzungsrichtlinien, beaufsichtigte Nutzung | Institutionell, nicht technisch | Voraussetzung fuer den Einsatz der Plattform |

### Fundamentale Erkenntnis (Session 262)

**Die Plattform ist fuer BEAUFSICHTIGTE Nutzung konzipiert.** Die Krise von Session 255 (Flugzeug→Hochhaus) war ein paedagogisches Versagen der Kursleitung, kein technisches. Das Safety-System soll Paedagogik UNTERSTUETZEN, nicht ersetzen. Nutzungsrichtlinien sind Teil der Sicherheitsarchitektur.

Konsequenz: Das technische System muss §86a und DSGVO *absolut* durchsetzen (gesetzliche Pflicht). Beim Jugendschutz ist es ein *Werkzeug* fuer Paedagogen — Perfektion ist weder moeglich noch noetig, solange die organisatorische Schicht funktioniert.

---

## 2. Sechs Aeren

### Era 1: GPT-OSS Monolith (Nov 2025)

**Zeitraum:** 2025-11-02 – 2026-01-27
**Charakter:** Safety als Prompt-Engineering im LLM-Aufruf

| Session | Datum | Commit | Aenderung |
|---------|-------|--------|-----------|
| 14 | 2025-11-02 | — | §86a StGB system prompt fuer GPT-OSS (ISIS-Flagge nicht erkannt → Prompt-Instruktion) |
| 29 | 2025-11-10 | — | Hybrid fast-filter + LLM verification (erste Keyword-Listen) |
| 132 | 2026-01-23 | — | Centralized safety in `stage_orchestrator.py` (vorher verstreut) |
| 143 | 2026-01-27 | — | Fast-Filter-First Architektur: kein LLM fuer 95%+ der Faelle |

**Was funktionierte:** Grundlegende §86a-Erkennung ueber Keywords + GPT-OSS als Kontext-Verifizierer.

**Was nicht funktionierte:** Alles lief ueber einen einzigen "GPT-OSS Safety" Pipeline-Call. Als das Modell nicht mehr geladen war (spaetere Sessions), brachen alle Safety-Checks zusammen → fail-open.

**Architektur-Schuld:** Die `gpt_oss_safety` Pipeline wurde zum Dead Code, der erst in Session 190 entdeckt und entfernt wurde.

---

### Era 2: Safety-Quick + VLM (Feb 7–12, 2026)

**Zeitraum:** 2026-02-07 – 2026-02-12
**Charakter:** Erste echte Safety-Architektur — drei Concerns getrennt, VLM-Check eingefuehrt

| Session | Datum | Commit | Aenderung |
|---------|-------|--------|-----------|
| 161 | 2026-02-07 | `cd86284` | Post-Generation VLM safety check (qwen3-vl:2b). Safety als drei Concerns dokumentiert. **fail-open** bei VLM-Fehler. |
| 161 | 2026-02-07 | `21de571` | docs: Layered Safety Architecture dokumentiert |
| 161 | 2026-02-07 | `b5bcd69` | i18n: DE/EN Safety-Block-Erklaerungen |
| 161 | 2026-02-07 | `3de4ad2` | VLM safety check fuer Upload-Bilder |
| 161 | 2026-02-07 | `c050d95` | VLM-spezifische Trashy-Erklaerung |
| 171 | 2026-02-12 | `6432158` | DSGVO LLM verification + Fuzzy-Matching-Fix. 26 Test Cases. |

**Eingefuehrt:**
- `POST /api/schema/pipeline/safety/quick` Endpoint (SAFETY-QUICK)
- VLM Post-Generation Check (`vlm_safety_check()`)
- Drei-Concerns-Dokumentation: §86a, DSGVO, Jugendschutz
- DSGVO LLM Verification (`llm_verify_person_name()`)
- Trashy-Erklaerungen bei Safety-Blocks

**Designfehler:**
- VLM war fail-open bei Fehlern (korrigiert in Session 254)
- `num_predict: 10` fuer DSGVO-Verify → Thinking-Modelle erschoepften Token-Budget (korrigiert in Session 171)
- Fuzzy-Matching mit Levenshtein distance=2 ab 6 Zeichen → "Potter" matchte "Folter" (korrigiert in Session 171)

---

### Era 3: DSGVO Rewrite + Fail-Closed (Feb 18–21, 2026)

**Zeitraum:** 2026-02-18 – 2026-02-21
**Charakter:** Systematische Haertung der DSGVO-Pipeline + Aufdeckung des fail-open Musters

| Session | Datum | Commit | Aenderung |
|---------|-------|--------|-----------|
| 181 | 2026-02-18 | `baba47f` | DSGVO NER Rewrite: POS-tag Pre-Filter, SAFE/UNSAFE statt JA/NEIN, dediziertes DSGVO_VERIFY_MODEL |
| 183 | 2026-02-19 | `cdebd57` | Tiered Translation: Auto fuer Kids, Optional fuer Youth+ |
| 190 | 2026-02-21 | `efe9222` | **KRITISCH:** Age-Filter fail-open Bug gefunden und gefixt. Dead `gpt_oss_safety` Pipeline → fail-open. |
| 190 | 2026-02-21 | `efe9222` | DSGVO-Fallback ebenfalls fail-open → fail-closed |

**Eingefuehrt:**
- SpaCy POS-tag Pre-Filter (ADJ+NOUN → kein LLM noetig)
- SAFE/UNSAFE Prompt-Format (statt JA/NEIN in Deutsch)
- Dediziertes `DSGVO_VERIFY_MODEL` (qwen3:1.7b)
- `llm_dsgvo_fallback_check()` fuer SpaCy-Ausfall

**Entdeckt und gefixt:**
- `gpt_oss_safety` Pipeline war Dead Code seit Sessions ~170+
- Age-Filter rief tote Pipeline auf → Pipeline-Fehler → fail-open → Content durchgelassen
- Identisches Muster bei DSGVO SpaCy-unavailable Fallback

**Lektion:** *Dead Code in Safety-Paths ist gefaehrlicher als fehlender Code.* Ein toter Pipeline-Call der fail-open zurueckgibt ist schlimmer als gar keine Pruefung, weil er Sicherheit *suggeriert*.

---

### Era 4: Ollama-Krise + Circuit Breaker (Feb 25–27, 2026)

**Zeitraum:** 2026-02-25 – 2026-02-27
**Charakter:** Katastrophe durch LLM-Infrastruktur-Umbau, gefolgt von systematischer Reparatur

| Session | Datum | Commit | Aenderung |
|---------|-------|--------|-----------|
| 217 | 2026-02-26 | `bb7e328` | Stale 'eco' args crashen Stage 1 + Stage 3 |
| 217 | 2026-02-26 | `996b8e8` | Guard-Modelle direkt zu Ollama statt GPU Service |
| 217 | 2026-02-26 | `a4672d6` | Revert `local_files_only` in LLM Backend |
| 217 | 2026-02-26 | `0309ac0` | **TEMPORARY fail-open** wenn Ollama LLM verification unavailable |
| 217 | 2026-02-26 | `6e8d4da` | Fix Stage 3 parse failure bei llama-guard multi-line output |
| 217 | 2026-02-26 | `2352668` | Strip custom prompt von llama-guard safety chunks |
| 218 | 2026-02-27 | `b2b6ff1` | Bypass GPU Service fuer ALL LLM inference → direkt zu Ollama |
| 218 | 2026-02-27 | `fe1b760` | Circuit Breaker mit fail-closed (Phase 1 Repair) |
| 218 | 2026-02-27 | `ff6e5b0` | Ollama Self-Healing Watchdog |
| 218 | 2026-02-27 | `74cffa2` | Stage 3 Translation-Sanitization Gap geschlossen |

**Was passiert war:** Session 217 versuchte, LLM-Inference vom Devserver in den GPU Service zu migrieren. Das brach das Safety-System komplett:
1. Guard-Modelle wurden falsch geroutet (GPU Service statt Ollama)
2. `execution_mode='eco'` Parameter existierte nicht mehr → Crash
3. llama-guard Multi-Line Output wurde falsch geparst
4. Custom Prompts auf Guard-Modellen (die nur S1-S13 Template verstehen)
5. **Notfall: fail-open Marker eingebaut** um Plattform lauffaehig zu halten

**Session 218 reparierte systematisch:**
1. LLM-Routing zurueck zu Ollama (GPU Service nur fuer Diffusers/HeartMuLa)
2. Circuit Breaker Pattern (`circuit_breaker.py`)
3. Ollama Watchdog fuer automatischen Restart (`ollama_watchdog.py`)
4. fail-closed statt fail-open
5. Differenzierte Timeouts (Safety: 30s, Standard: 120s)

**Lektion:** *Infrastruktur-Migrationen muessen Safety-Paths als erstes testen.* Die Migration brach alles gleichzeitig, weil Safety-Calls die gleichen LLM-Routing-Paths nutzen wie normale Calls, aber andere Anforderungen haben (Guard-Modell, strukturierte Prompts, fail-closed).

---

### Era 5: Workshop-Notfallreparaturen (Mar 3–10, 2026)

**Zeitraum:** 2026-03-03 – 2026-03-10
**Charakter:** Laufende Workshops decken Bypasses auf, jeder Tag bringt neue Fixes

| Session | Datum | Commit(s) | Aenderung |
|---------|-------|-----------|-----------|
| 244 | 2026-03-03 | `9dd08b7` | Stage 3 Redesign: Single Llama-Guard Call mit S1-S13 Template. Redundantes Age-Filter entfernt. |
| 244 | 2026-03-03 | `550c6db` | Pre-generation `/safety/quick` Gate in `startGeneration()` |
| 245 | 2026-03-04 | `896858b` | Stage 1 LLM-Routing fix: §86a→Llama Guard, Age Filter→qwen3 |
| 246 | 2026-03-04 | `3fb0591` | Age-Filter: Fuzzy→Stem-Prefix Matching. LLM Prompt: Concrete Categories. Stage 3: nur image-relevante S-Codes |
| 253 | 2026-03-07 | `d19be5b` | Cloud-API Retry, DSGVO Provider Fallback, Ollama Concurrency 6, NER Numeric Filter |
| 253 | 2026-03-07 | `8594905` | VLM verdict parsing: last word statt substring match |
| 254 | 2026-03-10 | `5fc3a85` | **VLM fail-open → fail-closed**. `enable_thinking=False` via Ollama API. |
| 255 | 2026-03-10 | `13a21dd` | Fehlende Weapon/War Terms in EN+DE Kids Filter |
| 255 | 2026-03-10 | `e30ea7e` | Llama-Guard 1B → 8B |
| 255 | 2026-03-10 | `e071002` | Kids zero-tolerance + Terrorism Terms EN/DE |
| 255 | 2026-03-10 | `8957798` | **DSGVO-First Ordering** + gpt-oss-120b fuer Kids Age Verify |
| 255 | 2026-03-10 | `6dd3850` | S2+S8 zum Stage 3 Blocking Set hinzugefuegt |
| 255 | 2026-03-10 | `23bf245` | gpt-oss-120b Reasoning-Modell Response-Format |

**Workshop-Befunde (chronologisch):**

1. **05.03 Workshop:** 8.6% False-Block-Rate (Safety zu aggressiv)
2. **06.03 Workshop:** 7.7% False-Block-Rate + 10 Mistral 503 + 11 Ollama Timeouts
3. **10.03 Workshop (Session 255):** AK-47, RPG-7, "Flugzeug in Hochhaus" passieren ALLE Filter
   - EN/DE Filterlisten fehlten Waffen-Begriffe (TR/KO/UK/FR/ES hatten sie!)
   - llama-guard3:1b zu schwach fuer semantische Klassifikation
   - S2 (Weapons Crimes) und S8 (Indiscriminate Weapons) waren excluded
   - qwen3:1.7b konnte "Terroranschlag auf Hochhaus" nicht als unsafe klassifizieren
4. **10.03 Workshop (Session 256):** 0% False-Block-Rate, 0% lokale Fehler (nach allen Fixes)
5. **12.03 Workshop (Session 260):** 29% Delivery Rate — Keyword-Filter verursacht 98 False Positives

**Architektur-Aenderungen:**
- DSGVO-First Ordering (DSGVO NER vor Age-Filter → ermoeglicht externen LLM fuer Kids)
- gpt-oss-120b (IONOS EU) fuer Kids Age-Filter (qwen3:1.7b zu schwach)
- Llama-Guard 1B → 8B
- VLM fail-open → fail-closed
- Pre-Generation Safety Gate (Blur-Bypass geschlossen)

---

### Era 6: Keyword-Filter aufgegeben (Mar 13, 2026) — AKTUELL

**Zeitraum:** 2026-03-13 – heute
**Charakter:** Fundamentale Designentscheidung — Keyword-basierter Age-Filter aufgegeben

| Session | Datum | Commit | Aenderung |
|---------|-------|--------|-----------|
| 260 | 2026-03-13 | — | Keyword Age-Filter **deaktiviert** fuer kids+youth im Stage Orchestrator |
| 260 | 2026-03-13 | — | Safety-Prefix in Stage 2 Interception (LLM-basiert statt Keyword-basiert) |
| 260 | 2026-03-13 | — | `skip_stage2` Override fuer kids+youth (Stage 2 mandatory) |
| 261 | 2026-03-13 | — | VLM Prompt redesign: Content-Checklist statt "Is this safe?" |

**Begruendung:** Workshop 12.03.2026 mit 29% Delivery Rate (137/470 Requests). 98 der 333 Blockierungen waren False Positives vom Keyword-Filter: fangs(25), explosion(20), blood/Blut(15), claws(15), pain(10), teeth(10). Nur "genital"(10) war legitim.

**Neuer Ansatz:**
1. **Safety-Prefix im Stage 2 Interception**: LLM erhaelt explizite Instruktion, rassistische/terroristische/gewaltverhherlichende/sexistische/pornographische Eingaben abzulehnen — inkl. implizite/metaphorische Formen (Flugzeug→Gebaeude, Fahrzeug→Menschenmenge)
2. **Stage 2 mandatory fuer kids+youth**: `skip_stage2` wird ueberschrieben
3. **Stage 3 Llama-Guard bleibt als zweites Netz**
4. **VLM Content-Checklist-Prompt** (Session 261): Konkrete schaedliche Kategorien aufzaehlen statt "Is this safe?" — verhindert, dass 2B VLM Situationsgefahr (Baustelle) mit Betrachtungsgefahr (schaedlich fuer Kinder) verwechselt

**Empirische Validierung (mammouth/claude-sonnet-4-6):**
- 8/8 semantische Bedrohungen (Flugzeug→Hochhaus, Waffe→Schule, etc.) refused
- 4/4 explizite Gewalt refused
- 4/4 harmlose Prompts (Tiger mit Zaehnen, Drache mit Krallen) kreativ transformiert
- 0 False Positives

**WARNUNG — Keyword-Filter NICHT wieder einfuehren:**
Der Keyword-Filter oszillierte zwischen zu aggressiv (28% False Positives) und zu permissiv (Waffen-Bypass) ueber 10+ Sessions. Das grundlegende Problem ist unlösbar: kurze Keywords in natuerlicher Sprache haben notwendigerweise hohe False-Positive-Raten, und laengere Keyword-Listen verschlechtern die Rate weiter statt sie zu verbessern.

---

## 3. Wiederkehrende Muster (Warnungen)

### 3.1 Fail-Open/Fail-Closed Oszillation

Das am häufigsten wiederkehrende Muster. Mindestens 9 dokumentierte Vorfaelle:

| # | Session | Komponente | Was passierte |
|---|---------|-----------|---------------|
| 1 | 161 | VLM Check | Eingefuehrt als fail-open ("VLM unavailability never blocks generation") |
| 2 | 190 | Age-Filter | Dead Pipeline → fail-open. Wochen unentdeckt. |
| 3 | 190 | DSGVO Fallback | Dead Pipeline → fail-open. Identisches Muster. |
| 4 | 217 | Alle LLM-Checks | Notfall: fail-open Marker eingebaut (Ollama-Krise) |
| 5 | 218 | Alle LLM-Checks | Repariert → fail-closed mit Circuit Breaker |
| 6 | 253 | VLM Check | "Fail-open if no clear verdict" eingefuehrt (Session 253 Fix 4) |
| 7 | 254 | VLM Check | Repariert → fail-closed. "Kindersicherheit kennt kein fail-open." |
| 8 | 255 | VLM max_new_tokens | 500 Tokens fuer Thinking → kein Verdict → fail-open Pfad |
| 9 | 262 | SAFETY-QUICK | Exception-Handler gibt `safe:true` zurueck (gefixt in dieser Session) |

**Regel:** Jede `except`-Clause in Safety-Code muss `safe: False` zurueckgeben. Es gibt keine Ausnahme von dieser Regel. §86a und DSGVO sind gesetzliche Pflichten.

### 3.2 Keyword-Filter Oszillation (AUFGEGEBEN)

| Session | Richtung | Was passierte |
|---------|----------|---------------|
| 29 | + | Erste Keyword-Listen |
| 171 | Fix | Fuzzy-Matching False Positives (Potter→Folter) |
| 220 | Fix | Cross-Language False Positives (kan→scharfkantige) → Language-Aware |
| 245 | Fix | LLM-Routing-Fehler → Blind-Block statt Kontext-Verify |
| 246 | Fix | Fuzzy→Stem-Prefix (leichte→Leiche False Positive) |
| 255 | + | Fehlende Weapon Terms in EN/DE hinzugefuegt |
| 260 | **AUFGEGEBEN** | 29% Delivery Rate, 98 False Positives in einem Workshop |

**DO NOT RESURRECT.** Ersetzt durch LLM-basiertes Safety-Prefix in Stage 2 Interception.

### 3.3 Modell-Routing-Fehler (Guard vs Context)

| Session | Fehler |
|---------|--------|
| 181 | DSGVO NER Verify lief auf Guard-Modell (kann "Ist das ein Name?" nicht beantworten) |
| 217 | Guard-Modelle ueber GPU Service statt Ollama geroutet |
| 244 | Free-Form-Frage auf Guard-Modell (braucht S1-S13 Template) |
| 245 | §86a nutzte qwen3 statt Llama Guard; Age-Filter nutzte Llama Guard statt qwen3 |

**Regel:** Jedes Safety-Check hat ein spezifisches Modell fuer einen spezifischen Grund:
- **§86a:** Llama Guard (S1-S13 Taxonomie fuer strukturierte Harm-Klassifikation)
- **DSGVO NER:** qwen3:1.7b (General-Purpose fuer Fakten-Fragen, LOKAL)
- **Age Filter Kids:** gpt-oss-120b (Stark genug fuer semantische Bedrohungen)
- **Age Filter Youth:** qwen3:1.7b (Weniger Ambiguitaet → lokales Modell reicht)
- **Stage 3:** Llama Guard 8B (S1-S13, nur image-relevante Codes)
- **VLM:** qwen3-vl:2b (Bild-Analyse, nur kids/youth)

### 3.4 Thinking-Modell-Komplikationen

| Session | Problem |
|---------|---------|
| 171 | `num_predict: 10` → Thinking verbraucht alle Tokens, `content` leer → fail-closed auf ALLES |
| 175 | gpt-OSS:20b `content` leer, Antwort nur in `thinking` Feld |
| 253 | VLM `/no_think` Prompt-Hack ignoriert → Thinking-Loop |
| 254 | `think: false` via Ollama API funktioniert. ABER: Modell ignoriert es bei ambigen Bildern. |
| 255 | gpt-oss-120b Reasoning-Modell: Antwort in `reasoning` statt `content` (= `null`) |

**Regel:** IMMER `content` UND `thinking`/`reasoning` pruefen. `num_predict` mindestens 500. Kein Prompt-Hack fuer Thinking-Control — nur API-Parameter.

---

## 4. Aktueller Zustand (Stand 2026-03-16)

### 4.1 Aktive Checks — Drei-Concerns-Architektur

```
User Input
  │
  ├─ [DSGVO] SpaCy NER → wenn Trigger → DSGVO-Verifikationsmodell (lokal)
  │   Durchsetzung: SAFETY-QUICK + Stage 1. Immer, fail-closed.
  │
  ├─ [§86a] Keyword-Trigger → Sicherheitsmodell (Llama Guard S1-S13)
  │   Durchsetzung: SAFETY-QUICK + Stage 1 + Stage 3. Immer, fail-closed.
  │
  ├─ [Jugendschutz] Safety-Prefix im Interception-Prompt
  │   Durchsetzung: Stage 2 (mandatory fuer kids/youth, auch bei leerer Context-Box)
  │   LLM weist rassistische/terroristische/gewaltverherrlichende/sexistische/
  │   pornographische Eingaben ab — inkl. implizite/metaphorische Formen.
  │
  ├─ [Stage 3] execute_stage3_safety()
  │   Translation + §86a + Llama-Guard S1-S13 (kids/youth)
  │   Blocking: S1,S2,S3,S4,S8,S9,S10,S11
  │
  ├─ [Stage 4] Media Generation
  │
  └─ [Post-Gen] VLM Check (kids/youth, images only)
      Content-Checklist-Prompt, fail-closed
```

### 4.2 Modelle

Actual model names are configured in `user_settings.json` (editable via Settings UI). Defaults for fresh installations are in `config.py:_SETTINGS_DEFAULTS`.

| Role | Config Key | Where | Constraint |
|------|-----------|-------|------------|
| §86a Context + Stage 3 S-Code | `SAFETY_MODEL` | Ollama | Must be guard model (S1-S13 taxonomy) |
| DSGVO NER Verify + Youth Age-Filter | `DSGVO_VERIFY_MODEL` | Ollama (LOCAL) | Must be general-purpose, NEVER external |
| VLM Post-Gen Image Check | `VLM_SAFETY_MODEL` | Ollama | Must be vision-language model |
| Kids Age-Filter Context Verify | hardcoded in `stage_orchestrator.py` | IONOS EU (external) | Needs strong semantic reasoning |
| Safety-Prefix Interception | `STAGE2_INTERCEPTION_MODEL` | Cloud (Mistral/IONOS) | — |

### 4.3 Infrastruktur

- **Circuit Breaker**: `my_app/utils/circuit_breaker.py` — 3 Failures → OPEN → Self-Healing
- **Ollama Watchdog**: `my_app/utils/ollama_watchdog.py` — Automatischer `systemctl restart ollama`
- **Cooldown**: Max 1 Restart pro 5 Minuten
- **Sudoers**: `0_setup_ollama_watchdog.sh` fuer passwortloses Restart

### 4.4 Safety Levels

| Level | §86a | DSGVO | Age Filter | VLM | Stage 3 | Stage 2 Safety-Prefix |
|-------|------|-------|-----------|-----|---------|----------------------|
| kids | Ja | Ja | Ja (gpt-oss-120b) | Ja | Ja | Ja (mandatory) |
| youth | Ja | Ja | Ja (qwen3:1.7b) | Ja | Ja | Ja (mandatory) |
| adult | Ja | Ja | Nein | Nein | Nein | Nein |
| research | Nein | Nein | Nein | Nein | Nein | Nein |

---

## 5. Offene Punkte

| Punkt | Bewertung | Begruendung |
|-------|-----------|-------------|
| VLM Video-Check | Offen (LOW) | Video-VLM-Check noch nicht implementiert. Videos selten und kurz (5-10s). |
| SAFETY-QUICK Age-Filter aktiv, Stage Orchestrator deaktiviert | Intentional | Defense-in-Depth. SAFETY-QUICK fuer Frontend-Feedback, Stage 2 Safety-Prefix fuer Generation. |
| Circuit Breaker Gap | Kein Fix noetig | Ollama-Watchdog (Session 218) restartet automatisch. Monitoring ist die richtige Loesung. |
| Dead Code: safety_check_kids/youth.json | Cleanup (LOW) | Chunks seit Session 244 nicht mehr aufgerufen. |
| SpaCy CJK Word-Boundary | Known Gap (LOW) | Koreanische Terms ≤3 Zeichen matchen nicht mit `\b` Regex. Pre-existing, nicht regressiert. |
| DSGVO NER: EN-only Namen | Known Gap (LOW) | SpaCy `de_core_news_lg` + `xx_ent_wiki_sm` erkennen manche englischsprachige Namen nicht zuverlaessig. |

---

## 6. Schluesselreferenzen

| Dokument | Inhalt |
|----------|--------|
| `docs/ARCHITECTURE PART 29 - Safety-System.md` | Technische Referenz (aktueller Zustand) |
| `devserver/testfiles/test_adversarial_safety_e2e.py` | E2E Adversarial Tests (3 Layer) |
| `devserver/testfiles/test_production_safety.py` | HTTP Production Tests (Port 17801) |
| `devserver/my_app/utils/circuit_breaker.py` | Circuit Breaker Pattern |
| `devserver/my_app/utils/ollama_watchdog.py` | Ollama Self-Healing |
| `LICENSE.md` §3(e) | Research Mode Legal Restrictions |
