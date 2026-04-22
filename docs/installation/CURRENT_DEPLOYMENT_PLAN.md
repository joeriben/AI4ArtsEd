# AI4ArtsEd — AKTIVER DEPLOYMENT-/INSTALLATIONSPLAN

> ============================================================
> **STATUS: AKTIV — gültiger Arbeitsplan**
> **Erstellt: 2026-04-21**
> **Autor: Benjamin Jörissen (mit Claude Opus 4.7)**
> **Implementierungsstart: offen — System wird in den kommenden Wochen nicht angefasst**
> ============================================================
>
> Dieses Dokument ist der aktuelle, verbindliche Arbeitsplan für das Multi-Tier-Deployment von AI4ArtsEd.
> Er liegt dem noch nicht umgesetzten Installer-Umbau zugrunde. Vor Beginn der Implementierung
> sollte er **erneut gelesen und ggf. angepasst** werden — die hier getroffenen Entscheidungen
> basieren auf dem Systemstand von April 2026.
>
> **Nicht löschen, nicht archivieren.** Der Plan bleibt aktiv, bis Phase 1 beginnt und
> dieses Dokument in ein Implementierungs-Log überführt wird.

---

## Context

Das System ist strukturell ausentwickelt (nur noch Debugging + agentische Erweiterungen stehen aus). Bisher lief es auf **einer** Maschine (Fedora 42, RTX 6000 Blackwell 96 GB VRAM, 350+ GB Modelldateien). Alle Installationsartefakte — `setup.sh`, `check_prerequisites.sh`, `download_models.sh`, `install_systemd_services.sh`, `docs/installation/PC2_INSTALLATION.md` — sind auf **genau diesen einen Zielrechner** zugeschnitten. Es gibt keinen Begriff von Hardware-Tiers, keine Auto-Adaption, keinen Multi-Maschinen-Deploy-Pfad.

**Ziel**: Ein Online-Installer für Linux (Fedora + Ubuntu/Debian), der Hardware erkennt, ein Profil wählt und das System tier-gerecht konfiguriert. Drei aktive Profile, alle auf die **volle pädagogische Pipeline inkl. Hallucinator/Surrealizer/Dual-CLIP-Optimization** ausgelegt.

**Scope-Abgrenzungen (User-Entscheidungen):**
- **Werkraum** (`ai4artsed_webserver_legacy`) — schlankes SwarmUI-Frontend, bleibt als **separates Produkt** für schwache Rechner. Eigener Installer bei Bedarf, nicht Teil dieses Plans.
- **Windows/macOS** — WSL2-Doku für Windows, macOS nur informativ. Kein nativer Installer.
- **Cloud-only-Profil** gestrichen: ohne lokale Fusion/CLIP-Manipulation keine visuelle Dekonstruktion → pädagogisch leer.
- **LLM-Install-Doctor** — Phase 5 (optional, nachgelagert).
- **Externe Lieferformen** (SSD, Docker, ISO) nicht im ersten Wurf.

---

## Drei Architektur-Erkenntnisse (gegenüber Ursprungsentwurf)

### 1. Backend-Footprints sind nicht modellglobal

SD3.5 Large via Diffusers ≈ 50 GB real, via ComfyUI ≈ 20 GB (Smart-Offload). Das `gpu_vram_mb`-Feld einer Output-Config ist pro Backend-Pfad zu lesen. Die Backend-Wahl pro Output-Config erfolgt per Profil, nicht statisch im Config-JSON.

### 2. Dekonstruktive Pädagogik ist Diffusers-exklusiv

Das bestehende ComfyUI-Node `ai4artsed_t5_clip_fusion.py` implementiert nur die **Legacy**-Fusion (simple LERP + concat). Die aktuelle Default-Strategie `dual_alpha` — die laut Session-211-Erkenntnis verhindert, dass lange Prompts den surrealen Effekt verwässern — und `normalized` sind **nur im Diffusers-Python-Pfad** verdrahtet (GPU-Service).

**Konsequenz**: Pädagogisch sinnvolles Deployment verlangt **Diffusers** überall. ComfyUI ist Notfall-Fallback, bietet aber nur degradierte Fusion. Jeder Tier unter dem Diffusers-Minimum ist pädagogisch nicht qualifiziert → Werkraum-Territorium.

### 3. Safety-LMs fressen VRAM

Llama-Guard 3:1B (~1.5 GB) + qwen3-vl:2b (~2.5 GB), gleichzeitig resident während Generation, kostet realistisch ~5 GB. Das muss in die Tier-Bilanz eingerechnet werden. Für knappe Tiers ist die Alternative: **Safety komplett über Cloud-Provider** (Mammouth/IONOS), mit dem ausdrücklichen Tradeoff, dass User-Image-Uploads zur VLM-Prüfung in die Cloud gehen — eine Entscheidung, die lokale Admins pro Instanz treffen.

---

## Hardware-Profile

### Profil B — Consumer-Minimum (16 GB VRAM, RTX 4080/5070Ti/5080)

- **Lokale Pädagogik**: SD3.5 **Medium** via Diffusers mit FP8-T5-Encoder und dual_alpha-Fusion — passt knapp in 16 GB (~14–15 GB inkl. Fusion-Overhead).
- **Safety**: Vollständig **via Cloud** (Mammouth/IONOS). Lokale Ollama-Safety-LMs nicht installiert.
- **Cloud für Große**: SD3.5 Large, Flux 2, Wan2.2 Video → GPT-Image-1 / Gemini / Cloud.
- **Lokale Audio**: HeartMuLa (3B, ~5 GB), Stable Audio — optional; bei paralleler Nutzung VRAM-Engpass.
- **12 GB VRAM und weniger** → **Werkraum empfohlen**, nicht dieses Profil.

### Profil C — Consumer-Hauptpfad (24–32 GB VRAM, RTX 4090 / RTX 5090)

- **Lokale Pädagogik**: SD3.5 Medium (komfortabel) + SD3.5 Large **FP8-quantisiert** via Diffusers (~28 GB Footprint inkl. Fusion) — beides mit voller dual_alpha-Pädagogik.
- **Safety**: Default **via Cloud** (Mammouth/IONOS), um VRAM für Generation freizuhalten. Lokale Safety-LMs optional durch Admin aktivierbar, dann aber sequenzielle Generation notwendig (Safety → unload → Generation → load).
- **Kommunikativ wichtig**: Die Cloud-Safety-Route wird im Installer-Output **explizit genannt** (User-Bild-Uploads erreichen den Cloud-Provider zur VLM-Prüfung). Entscheidung liegt beim lokalen Admin.
- **Cloud für Flux 2**: Immer, egal welche Karte.

### Profil E — Workstation (96 GB VRAM, RTX 6000 Blackwell)

- **Alles lokal**: SD3.5 Medium/Large FP16, Flux 2, Wan2.2 Video, HeartMuLa, Stable Audio, alle Safety-LMs simultan resident.
- **Referenz-Tier**: aktueller Dev-PC, `PC2_INSTALLATION.md` wird zum Profil-E-Spezialdokument.
- **40–48 GB Sonderfall (RTX 6000 Ada / A6000)**: kein eigenes Profil, stattdessen **VRAM-abhängige Add-on-Regel**: Detection erkennt ≥40 GB → Profile-Service schaltet Wan2.2 Video zusätzlich frei; Flux 2 bleibt Cloud.

---

## Was bereits existiert (Foundation)

| Artefakt | Zustand |
|---|---|
| `check_prerequisites.sh` | Erkennt VRAM/CUDA/Python/Node/Disk/RAM/Ports — **fail-hard ohne NVIDIA-GPU** (muss umgebaut werden) |
| `setup.sh` | Venv + npm build — reagiert nicht auf Detection |
| `download_models.sh` | HuggingFace-Downloader ohne Tier-Filter |
| `install_comfyui_nodes.sh` | Installiert `ai4artsed_comfyui` (hat bereits Legacy-Fusion-Node) |
| `install_systemd_services.sh` | Systemd-Units (Linux only, root), heute monolithisch |
| `user_settings.json` | Modell-Zuweisungen pro Stage — wird heute händisch editiert |
| `output_configs/*.json` | 36 Configs mit `gpu_vram_mb`-Metadata |
| `backend_router.py` | Provider-Routing (mammouth/mistral/ionos/openai/anthropic) |
| `dlbackend/ComfyUI/custom_nodes/ai4artsed_comfyui/ai4artsed_t5_clip_fusion.py` | Legacy-Fusion-Node (nicht dual_alpha) |

---

## Installer-Architektur

### Schicht 1 — Detection (Erweiterung `check_prerequisites.sh`)

- OS + Distribution (Fedora / Ubuntu / Debian → apt vs dnf)
- GPU-Vendor + VRAM in MB
- CUDA-Version (≥13 für Blackwell, ≥12 für Ada/Ampere)
- RAM + Disk + `.key`-Files für Cloud-Provider

Klassifizierung → `install_profile.json` mit einem von `B` / `C` / `E` + ggf. Add-on-Flags (`addon_wan22_video: true` bei ≥40 GB). **Kein** fail-hard mehr ohne GPU — stattdessen klare Empfehlung auf Werkraum-Dokumentation und sauberer Exit.

### Schicht 2 — Profile-Install (`install.sh` neu)

1. Detection → Profil-Vorschlag → User-Bestätigung (oder `--profile X` Override)
2. `user_settings.json` aus profilspezifischem Template generieren:
   - B: Text-Stages + Safety alle auf Cloud (Mammouth default)
   - C: Text-Stages auf Cloud, Safety auf Cloud (Default) oder Ollama (Admin-Opt-in)
   - E: Alles lokal (Ollama + llama-cpp-python), Cloud als Fallback
3. `install_profile.json` persistent in `devserver/` schreiben — vom Backend-Router + Output-Config-Registry zur Laufzeit gelesen
4. Profilabhängiger Modell-Download via `download_models.sh --profile {B|C|E}`:
   - B: SD3.5 Medium + CLIP-L/G + T5-XXL-FP8 + HeartMuLa ≈ 30 GB
   - C: + SD3.5 Large FP8 ≈ 60 GB
   - E: + SD3.5 Large FP16 + Flux 2 + Wan2.2 ≈ 350 GB
   - Plus Ollama-Pulls profilabhängig (C-Opt-in, E-default)
5. Profilabhängige systemd-Units:
   - B: `ai4artsed-backend.service` only (GPU-Service-Start für HeartMuLa minimal)
   - C: `ai4artsed-backend.service` + `ai4artsed-gpu.service`
   - E: zusätzlich ComfyUI-Autostart (bereits vorhanden)
6. Frontend-Build (einheitlich, API-Endpoint runtime-bestimmt)
7. Smoke-Test pro Profil (siehe Verifikation)
8. **Prominente Ausgabe der Safety-Routing-Entscheidung** im Installer-Output (für C explizit: "Bild-Uploads gehen zur Safety-Prüfung an Mammouth/IONOS; lokale Safety aktivierbar via …")

---

## Code-Erweiterungen

| Datei / Modul | Art | Zweck | System-Eingriff |
|---|---|---|---|
| `install.sh` | neu | Top-Level-Orchestrator | Kein Eingriff am laufenden System |
| `profiles/B_consumer.json` | neu | 16 GB, Cloud-Safety-default | — |
| `profiles/C_consumer.json` | neu | 24–32 GB + Add-on-Regel für 40–48 GB | — |
| `profiles/E_workstation.json` | neu | 96 GB | — |
| `profiles/user_settings_templates/{B,C,E}.json` | neu | Pro Profil ein Template | — |
| `check_prerequisites.sh` | erweitern | Klassifizieren statt fail-hard | — |
| `download_models.sh` | erweitern | `--profile` Flag | — |
| `install_systemd_services.sh` | erweitern | Profilabhängige Unit-Auswahl | — |
| `devserver/my_app/services/profile_service.py` | neu | `install_profile.json` laden, Config-Filterung + Backend-Preference-Lookup, `/api/profile` Endpoint | **Additiv**: ohne `install_profile.json` → alle Configs sichtbar (heutiges Verhalten) |
| Output-Config-Registry-Modul | touch | beim Laden: per `profile_service.is_config_allowed()` filtern | Kleine Änderung, reiner Lese-Pfad |
| `devserver/schemas/engine/backend_router.py` | touch | vor statischem `meta.backend_type` das Profil-Backend-Preference konsultieren | Additiv, Fallback auf aktuelle Logik |
| `devserver/schemas/configs/output/sd35_medium.json` | neu | SD3.5 Medium als eigene Output-Config (Chunk `output_image_sd35m_*`) | Neuer Pfad, bestehende Large-Config unverändert |
| `public/ai4artsed-frontend/src/composables/useAvailableConfigs.ts` | touch/neu | Frontend fragt `/api/profile`, blendet inaktive Configs aus | UX-Polish |
| `devserver/testfiles/install_smoke_{B,C,E}.py` | neu | End-to-End-Smoke-Tests | — |
| `docs/installation/INSTALLATION.md` | überschreiben | Tier-agnostische Installationsanleitung, verweist auf Profile | Doku |
| `docs/installation/PC2_INSTALLATION.md` | umetikettieren | wird zu "Profil E — Workstation Reference" | Doku |
| `docs/installation/WSL2_WINDOWS.md` | neu | WSL2-Setup für Windows-User | Doku |
| `docs/installation/WERKRAUM_WEAK_MACHINES.md` | neu | Verweis auf Werkraum als Empfehlung für <16 GB VRAM | Doku |

### Failsafe-Level

Die install-bezogenen Artefakte verändern das laufende System nicht. Die drei touch-Punkte im Backend (`profile_service`, Output-Config-Registry, `backend_router`) sind **additiv**: ohne `install_profile.json` verhält sich das System exakt wie heute. Damit bleibt der Dev-PC während Entwicklung funktional; jede Regression ist durch simples Löschen der `install_profile.json` sofort reversibel.

---

## Verifikation

Smoke-Tests laufen am Ende des Installers automatisch, Resultat in `install_verification.log`:

| Profil | Test |
|---|---|
| B (16 GB) | Mammouth-Text → SD3.5 Medium Diffusers + dual_alpha-Fusion (kurzer Prompt, 1 Bild) → Cloud-Safety-Check → Export JSON |
| C (24 GB) | B-Test + SD3.5 Large FP8 Diffusers (kurzer Prompt) |
| C+ Addon (≥40 GB) | C-Test + Wan2.2 Video (16 frames) |
| E (96 GB) | C-Test + Flux 2 + HeartMuLa + parallele Bild+Audio-Generierung, **lokale** Safety-LMs |

Alle Tests als eigenständige Python-Scripts, aufrufbar via `venv/bin/python devserver/testfiles/install_smoke_<profile>.py`.

---

## Phasenplan

1. **Phase 1 — Profile-Architektur im Backend** (~3–5 Tage)
   - `profile_service.py`, Backend-Router-Integration, Output-Config-Registry-Filter
   - Frontend-Composable + `/api/profile`
   - `profiles/*.json` für B/C/E + Add-on-Regel
   - **Neue Output-Config `sd35_medium.json`** + zugehöriger Chunk + Diffusers-Backend-Verdrahtung (reuse existing optimization pipeline)
   - **Exit**: Dev-PC läuft mit Dummy `install_profile.json=E`, alle Pfade identisch zum Heute-Zustand; manuell auf B/C umschalten zeigt gefilterte Config-Liste

2. **Phase 2 — Installer-Scripts** (~3–5 Tage)
   - `check_prerequisites.sh` umbauen, `install.sh` neu
   - `download_models.sh --profile`, `install_systemd_services.sh` profilabhängig
   - Smoke-Test-Scripts für alle Profile
   - **Exit**: End-to-End Installation auf Dev-PC reproduzierbar (Profil E), Trockenlauf-Logs für B/C

3. **Phase 3 — Cross-Tier-Validierung + Doku** (~2–3 Tage)
   - Test auf realer Hardware: mindestens 1× Profil E (Dev-PC), 1× Profil C falls 4090/5090 verfügbar; Profil B ggf. via VM mit reduziertem VRAM-Limit
   - `docs/installation/INSTALLATION.md`, `WSL2_WINDOWS.md`, `WERKRAUM_WEAK_MACHINES.md`
   - Safety-Routing-Kommunikation (C: Cloud-Safety-Tradeoff explizit dokumentiert)

4. **Phase 4 — Stabilisierung + Feasibility-Notizen** (~1–2 Tage)
   - Bugfixes aus echten Installationen
   - Kurze Feasibility-Notiz zu **Profil F — Rented GPU Server** (siehe unten)
   - Kurze Feasibility-Notiz zu Fedora-ISO (als separates späteres Projekt markiert)

5. **Phase 5 — LLM-Install-Doctor (optional)** (~2–3 Tage)
   - Nur wenn Phase 1–4 produktiv sind und echte Fehlermuster bekannt
   - Claude-basierter Agent, der Install-Logs + `install_profile.json` + systemd-Journalausgaben analysiert

**Gesamtschätzung (ohne Phase 5)**: ~9–15 Tage fokussierter Arbeit.

---

## Feasibility-Notiz: Profil F — Rented GPU Server

Machbar, aber drei zusätzliche Problemklassen:

1. **Ephemere Model-Storage** — RunPod/Vast/Lambda-Instanzen verlieren Disk beim Shutdown. 50–350 GB bei jedem Spin-up ist unpraktikabel. Lösung: Network-Volume-Mount (RunPod bietet das; andere Anbieter variieren). Installer müsste detektieren, ob Volume vorhanden, und Model-Download skippen.
2. **Headless-Erreichbarkeit** — Cloudflare-Tunnel-Unit existiert bereits in `install_systemd_services.sh`, muss nur profilabhängig aktiviert werden plus Tunnel-Token-Input.
3. **Kostenkontrolle** — anbieterspezifische Idle-Shutdown-Scripts. Eigener kleiner Research-Block.

**Empfehlung**: Profil F im Profile-System einplanen, aber aktiven Installer-Support erst in zweiter Runde. Docker-Image wäre dann der natürliche Formfaktor (RunPod/Vast konsumieren Docker nativ). Rechtfertigt eigenständige Phase 6, falls Nachfrage aus Workshops da ist.

---

## Änderungshistorie

| Datum | Eintrag |
|---|---|
| 2026-04-21 | Initialversion. Entscheidungen: Profil A gestrichen (Werkraum übernimmt schwache Rechner); Profil C bleibt breit 24–32 GB mit Cloud-Safety-Default; Fusion-Pfad α (FP8-Diffusers); Linux-only; Online-Installer. |
