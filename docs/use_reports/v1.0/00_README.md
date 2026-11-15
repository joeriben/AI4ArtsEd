# 00 README — environment of the use run (UCD-374, revision 2)

Reports: one file per instrument, `01_flow.md` … `33_lora_explorer.md`, each in the nine-point format of the work order. The scenarios and the AI-Lit mappings in section 8 and 9 are mine, built from my scenarios against the OECD/EU 2026 appendix of the work order; the platform's own per-instrument mapping was not opened. Every mapping was held against the framework's own classroom example ("In the Classroom") for that competence and level: a mapping stands only where the scenario reaches the level that example sets, a mutatis-mutandis entry says what it changes and how it still reaches that level, and a short paragraph at the end of section 9 says where the scenarios go beyond the framework's examples.

2026-11-07: the wording "in this session" was removed from all 33 reports, and three sentences that referred to the use script of the run were removed from sections 5 and 7 of reports 03, 04 and 05; the statements are unchanged.

## Build and session

- Platform: the dev server at `http://fedora:17802` (header "UCDCAE AI LAB"), build of commit `e73153cb` (2026-11-01 13:39:45 +0100); the served `index.html` is dated 2026-11-01 13:39:12 with the bundle `assets/index-CBgoAUsH.js`. No build, no code and no platform setting was changed during the run.
- UI language: English throughout (EN in the top bar).
- Sign-in: not signed in at any point. No instrument asked for a sign-in; the favourites switch "Mine / All" and "Add to favorites" exist and were not used.
- Time: 2026-11-02 19:17 CET to 2026-11-03 11:55 CET, with a pause from 01:20 to 10:13 during which the Bias Research 1 run (480 answers) continued on the server. Active time about 7 hours 30 minutes. No duration of an instrument is reported; section 4 of every report says why.

## How the platform was operated

- A headless Chromium on the server (Playwright), driven over SSH from the Mac: clicks, typing, sliders and file uploads as a user does them; DOM text and screenshots read back; generated pictures fetched from the page. Up to ten tabs were open at once, so several runs overlapped on the server's queue.
- What this method cannot do, and what the reports say so: sound could not be listened to (Latent Audio Synth, MMAudio, ImageBind Guidance, Re-enactment report settings, durations, files and readouts instead); there is no microphone, so the Re-enactment got a ten-second hum synthesised by me as a fake microphone; a drag on a canvas is an emulated mouse drag.
- The Mac's own Claude settings file was changed during the session (browser-tool allow rules and a write rule for the Downloads folder); the platform was not.
- On every page that carries a text of its own in this build, the Help panel opens by itself on the first arrival in a browser that has not seen the page, with that text; on the other pages it does not open by itself. Section 1 of each such report quotes the text in the build's English, and sections 5 and 6 are written against it. I overlooked the panel during the use and worked it in afterwards.

## Conditions on the server

- One ComfyUI queue for everyone, fed by two backends: the dev backend I used and a workshop replay backend on the same machine, started on 2026-11-01 by another session, whose 27B language-model jobs stood in the same queue throughout (verified on 2026-11-03 at 18:22, still running). Every run of this session waited behind them. The durations I measured therefore say nothing about the instruments and are reported nowhere; the complaints about waiting that the first version of the reports carried have been removed.
- Two restarts: ComfyUI at 19:24:25 by me (an operator action over SSH, to clear a music job stuck at step 0/10; no code or setting changed), and the backend at 22:19:31, not by me, which lost the first picture set of instrument 13.
- Bias Research 1 (24) is 480 model calls from one press and cannot be stopped from the page; it ran overnight. Bias Research 2 (25) is 240 calls.
- The card was shared: at 11:22 it held 87 of 95.6 GB, so the LoRA Training's VRAM check refused (needs 50 GB); the surface's offer to unload the other models was declined, since other runs were using them.
- One cell of the LoRA Explorer's twelve arrived as "Service not reachable."; the other eleven arrived.

## Runs per instrument

Flow (01) is not one mode among the thirty-three; it is the central mode for artistic teaching, and the instruments of the other reports are side trips from it.

| file | instrument | used | runs |
|---|---|---|---|
| 01_flow.md | 01 Flow | 2026-11-02, 19:17–19:47 CET | 5 started, 4 completed (one stalled behind the stuck queue). |
| 02_together.md | 02 Together | 2026-11-02, 19:50–20:06 CET | 3 chat turns, 1 upload, 2 image looks (server-side), ~8 speech syntheses. |
| 03_contesting.md | 03 Contesting | 2026-11-02, 20:06–20:14 CET | 2 chat turns, 1 video generation started by the machine, ~10 speech syntheses. |
| 04_canvas.md | 04 Canvas | 2026-11-02, 20:13–20:36 CET | 3 (one text-only, two image generations). |
| 05_ueberblick.md | 05 Overview | 2026-11-02, 20:37–20:41 CET | none (no generation on this surface). |
| 06_modell_vergleich.md | 06 Model Comparison | 2026-11-02, 20:39–20:56 CET | 2 Compare All (3 + 2 pictures), 6 Commons searches. |
| 07_stereotypen_analyse.md | 07 Stereotype Analysis | 2026-11-02, 20:52–21:11 CET | 2 series, 12 pictures. |
| 08_bildverstaendnis.md | 08 Image Understanding | 2026-11-02, 21:12–21:25 CET | 2 readings with one model. |
| 09_sprachverstaendnis.md | 09 Language Understanding | 2026-11-02, 21:26–21:52 CET | 1 series, 6 pictures, 5 translations. |
| 10_stimmen_vergleich.md | 10 Voice Comparison | 2026-11-02, 21:31–21:50 CET | 6 clips (4 systems, Piper and VoxCPM2 twice). |
| 11_system_prompts.md | 11 System Prompts | 2026-11-02, 21:55–22:05 CET | 2 sends, 6 answers, cloud model. |
| 12_modell_vergleich_llm.md | 12 Model Comparison (Transformers Lab) | 2026-11-02, 21:56–22:08 CET | 1 send, 3 answers, three local models in sequence. |
| 13_sprachmodell_vergleich.md | 13 Language Model Comparison | 2026-11-02, 22:08–22:38 CET | 2 series, 4 rewrites, 3 pictures (3 further pictures lost to the restart). |
| 14_wirkungsvergleich.md | 14 Interception Scope | 2026-11-02, 22:08–22:26 CET | 2 series, 4 pictures, 3 rewrites. |
| 15_aesthetische_pole.md | 15 Aesthetic Poles | 2026-11-02, 22:38–22:50 CET | 1 series, 2 pictures, 2 rewrites. |
| 16_denoising_archaeology.md | 16 Denoising Archaeology | 2026-11-02, 22:40–22:50 CET | 1 generation, 25 steps. |
| 17_mean_images.md | 17 Mean Images | 2026-11-02, 22:50–23:16 CET | 1 series: 9 pictures, 2 latent means. |
| 18_attention_cartography.md | 18 Attention Cartography | 2026-11-02, 22:51–23:17 CET | 1 generation with analysis; all other changes are instant re-renderings of the captured maps. |
| 19_encoder_fusion.md | 19 Encoder Fusion | 2026-11-02, 23:17–23:37 CET | 2 pictures, 1024 × 1024, same seed. |
| 20_dimension_explorer.md | 20 Dimension Explorer | 2026-11-02, 23:17–23:40 CET | 1 analysis (two pictures), 2 transfers (one picture each). |
| 21_concept_algebra.md | 21 Concept Algebra | 2026-11-02, 23:37–23:50 CET | 2 computations, 3 pictures (the reference is kept). |
| 22_composable_diffusion.md | 22 Composable Diffusion | 2026-11-02, 23:44–23:55 CET | 2 pictures. |
| 23_fusion_workbench.md | 23 Encoder Fusion Workbench | 2026-11-02/03, 23:50–00:45 CET | 2 sweeps, 6 pictures. |
| 24_bias_research_1.md | 24 Bias Research 1 | 2026-11-02/03, 23:50 CET to the next morning (the run of 480 answers finished overnight; read at 10:14 CET) | 1 (480 answers). |
| 25_bias_research_2.md | 25 Bias Research 2 | 2026-11-03, 10:17–11:55 CET | 1 (240 answers). |
| 26_representation_engineering.md | 26 Representation Engineering | 2026-11-03, 00:15–00:30 CET | 1 (three answers). |
| 27_tokenizer.md | 27 Tokenizer | 2026-11-03, 00:06–00:22 CET | one translation run; every cut is instant. |
| 28_latent_audio_synth.md | 28 Latent Audio Synth | 2026-11-03, 00:25–00:55 and 10:15–10:20 CET | 3 sounds of 12 s. |
| 29_mmaudio.md | 29 MMAudio | 2026-11-03, 00:28–00:54 CET | 2 clips of 8 s. |
| 30_imagebind_guidance.md | 30 ImageBind Guidance | 2026-11-03, 00:28–00:50 CET | 2 clips of 10 s. |
| 31_re_enactment.md | 31 Re-enactment | 2026-11-03, 10:21–11:10 CET | 2 recordings, 2 passes through the four machines. |
| 32_lora_training.md | 32 LoRA Training | 2026-11-03, 11:21–11:35 CET | none (no training). |
| 33_lora_explorer.md | 33 LoRA Explorer | 2026-11-03, 10:17–11:25 CET | 1 (12 pictures, 11 arrived). |
