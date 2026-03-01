# i18n Translation Work Orders

Instructions for the `i18n-translator` agent: process all entries under **Pending**, translate
the listed keys from `en.ts` into `de.ts`, `tr.ts`, `ko.ts`, `uk.ts`, `fr.ts`, `es.ts`, `he.ts`, `ar.ts`, then move
each processed work order to **Completed** with a date stamp.

## Pending

### WO-2026-03-01-step-sequencer
- **Session**: 231
- **Scope**: en.ts
- **Changed keys** (new):
  - `latentLab.crossmodal.synth.modeSequencer` (NEW): 'Sequencer'
  - `latentLab.crossmodal.synth.sequencer.play` (NEW): 'Play'
  - `latentLab.crossmodal.synth.sequencer.stop` (NEW): 'Stop'
  - `latentLab.crossmodal.synth.sequencer.bpm` (NEW): 'BPM'
  - `latentLab.crossmodal.synth.sequencer.bpmHint` (NEW): 'Tempo in beats per minute (16th-note steps)'
  - `latentLab.crossmodal.synth.sequencer.preset` (NEW): 'Preset'
  - `latentLab.crossmodal.synth.sequencer.midiSync` (NEW): 'MIDI Sync'
  - `latentLab.crossmodal.synth.sequencer.gridHint` (NEW): 'Slider = semitone offset, dot = active toggle, bottom = velocity'
  - `latentLab.crossmodal.synth.sequencer.patterns.arpeggio_up` (NEW): 'Arpeggio Up'
  - `latentLab.crossmodal.synth.sequencer.patterns.arpeggio_down` (NEW): 'Arpeggio Down'
  - `latentLab.crossmodal.synth.sequencer.patterns.arpeggio_updown` (NEW): 'Arpeggio Up-Down'
  - `latentLab.crossmodal.synth.sequencer.patterns.octaves` (NEW): 'Octaves'
  - `latentLab.crossmodal.synth.sequencer.patterns.power_chord` (NEW): 'Power Chord'
  - `latentLab.crossmodal.synth.sequencer.patterns.minor_pentatonic` (NEW): 'Minor Pentatonic'
  - `latentLab.crossmodal.synth.sequencer.patterns.bass_groove` (NEW): 'Bass Groove'
  - `latentLab.crossmodal.synth.sequencer.patterns.trance_gate` (NEW): 'Trance Gate'
- **Context**: Step sequencer for the Crossmodal Lab synth tab. Replaces the broken Wavetable mode as the 3rd playback option. User-editable grid with selectable 5/8/16 steps. Preset patterns (arpeggio names) should be translated naturally (e.g. "Arpeggio Aufwärts" in DE). BPM stays as "BPM" in all languages. "MIDI Sync" can stay English in most languages or be adapted. gridHint explains the UI controls.

### WO-2026-03-01-semantic-axes-synth
- **Session**: 230
- **Scope**: en.ts
- **Changed keys** (new):
  - `latentLab.crossmodal.synth.semanticAxes.modeToggle` (NEW): 'Semantic Axes' (collapsible section header)
  - `latentLab.crossmodal.synth.semanticAxes.info` (NEW): Explanatory text about axes steering prompt embedding
  - `latentLab.crossmodal.synth.semanticAxes.slotNone` (NEW): '— none —'
  - `latentLab.crossmodal.synth.semanticAxes.resetAll` (NEW): 'Reset all to center'
  - `latentLab.crossmodal.synth.semanticAxes.experimental` (NEW): 'experimental'
- **Context**: New "Semantic Axes" section in Crossmodal Lab synth tab. Collapsible section below the prompt that steers audio generation via semantic slider axes (e.g. tonal/noisy, rhythmic/sustained) on top of the user's prompt. Each axis interpolates between two text poles in T5 embedding space.

### WO-2026-03-01-ionos-provider-strings
- **Session**: 229
- **Scope**: en.ts
- **Changed keys** (new):
  - `settings.api.ionosEu` (NEW): 'IONOS AI Model Hub (EU Berlin, DSGVO)'
  - `settings.api.ionosInfo` (NEW): 'IONOS AI Model Hub (EU)'
  - `settings.api.ionosDsgvo` (NEW): 'DSGVO-compliant (EU datacenter Berlin)'
- **Context**: New DSGVO-compliant cloud LLM provider (IONOS AI Model Hub, EU datacenter Berlin). Dropdown option and info box strings for Settings page. Keep "DSGVO" as-is in German, translate to local equivalent elsewhere (e.g. "GDPR" in English is already done, use local terms in FR/ES/etc.).

### WO-2026-02-28-optimization-loading-messages
- **Session**: 226
- **Scope**: en.ts
- **Changed keys** (new):
  - `textTransform.loadingDefault` (NEW): Generic optimization loading message
  - `textTransform.loadingSd35` (NEW): SD3.5-specific message explaining CLIP-L/G optimization + T5 preserves user text
  - `textTransform.loadingTranslateHint` (NEW): Hint to translate before generation if text not in English
- **Context**: Shown during optimization loading phase. SD3.5 gets model-specific text explaining the triple-encoder architecture. Translation hint appended for all models since Stage 3 only auto-translates at kids level. Replaces hardcoded German string.

### WO-2026-02-28-t5-uses-your-text
- **Session**: 226
- **Scope**: en.ts
- **Changed keys** (new):
  - `mediaInput.t5UsesYourText` (NEW): "T5-XXL uses your original text directly"
- **Context**: SD3.5 triple-prompt optimization now only generates CLIP-L/G prompts. T5-XXL receives the user's interception text unmodified (user self-determination). This note appears below the CLIP sections to inform the user.

### WO-2026-02-27-expert-energy-fact-reword
- **Session**: 220
- **Scope**: en.ts
- **Changed keys** (new or modified):
  - `edutainment.energy.expert_1` (MODIFIED): emoji changed from 📊 to ⚡, text reworded to "Current draw: {watts} W | GPU load: {util}% | Accumulated: {kwh} kWh (integrated over time)"
- **Context**: The old text used "=" which falsely implied kWh is derived from a single W reading. kWh is actually integrated from sampled power readings over time. Reworded to separate the three independent readings with pipes. Also replaced 📊 emoji.

### WO-2026-02-27-replace-chart-emoji
- **Session**: 220
- **Scope**: en.ts
- **Changed keys** (new or modified):
  - `edutainment.model.expert_2` (MODIFIED): emoji 📊 -> 🔧 (only emoji changed, text unchanged)
  - `edutainment.environment.expert_1` (MODIFIED): emoji 📊 -> 🌍 (only emoji changed, text unchanged)
- **Context**: 📊 (bar chart emoji) was flagged as forbidden. Replaced with contextually fitting alternatives: 🔧 for quantization, 🌍 for CO₂ calculation. Only the leading emoji changed, NOT the text.

### WO-2026-02-27-denoising-progress-view
- **Session**: 220
- **Scope**: en.ts
- **Changed keys** (new or modified):
  - `edutainment.denoising.modelLoading` (NEW)
  - `edutainment.denoising.modelCard` (NEW)
  - `edutainment.denoising.publisher` (NEW)
  - `edutainment.denoising.architecture` (NEW)
  - `edutainment.denoising.parameters` (NEW)
  - `edutainment.denoising.textEncoders` (NEW)
  - `edutainment.denoising.quantization` (NEW)
  - `edutainment.denoising.vramRequired` (NEW)
  - `edutainment.denoising.resolution` (NEW)
  - `edutainment.denoising.license` (NEW)
  - `edutainment.denoising.fairCulture` (NEW)
  - `edutainment.denoising.safetyByDesign` (NEW)
  - `edutainment.denoising.denoisingActive` (NEW)
- **Context**: Labels for expert-mode denoising progress view. Shows model "Steckbrief" (identity card) during VRAM loading and live denoising stats during generation. Technical/educational terms, keep short.

### WO-2026-02-27-privacy-policy
- **Session**: 221
- **Scope**: en.ts
- **Changed keys** (new or modified):
  - `legal.privacy.controller.title` (NEW)
  - `legal.privacy.controller.content` (NEW)
  - `legal.privacy.dataProcessing.title` (NEW)
  - `legal.privacy.dataProcessing.content` (NEW)
  - `legal.privacy.deviceId.title` (NEW)
  - `legal.privacy.deviceId.content` (NEW)
  - `legal.privacy.uploads.title` (NEW)
  - `legal.privacy.uploads.content` (NEW)
  - `legal.privacy.cookies.title` (NEW)
  - `legal.privacy.cookies.content` (NEW)
  - `legal.privacy.externalServices.title` (NEW)
  - `legal.privacy.externalServices.content` (NEW)
  - `legal.privacy.legalBasis.title` (NEW)
  - `legal.privacy.legalBasis.content` (NEW)
  - `legal.privacy.retention.title` (NEW)
  - `legal.privacy.retention.content` (NEW)
  - `legal.privacy.rights.title` (NEW)
  - `legal.privacy.rights.content` (NEW)
  - `legal.privacy.fauReference.title` (NEW)
  - `legal.privacy.fauReference.content` (NEW)
- **Context**: Full GDPR-compliant privacy policy for the platform. Legal terminology — use correct GDPR/DSGVO terms per language (e.g. "Betroffenenrechte" in DE, "Droits de la personne concernée" in FR). Keep Art. references (Art. 15, 16, 17, etc.) as-is. FAU address and contact email stay untranslated. The "controller" section is the GDPR "Verantwortlicher". Important: these are legal texts that should be linguistically precise.

### WO-2026-02-28-poetry-rename-context-category
- **Session**: 223
- **Scope**: 6 JSON files in `devserver/schemas/configs/interception/`: poetry_sappho, poetry_hoelderlin, poetry_basho, poetry_mirabai, poetry_yoruba_oriki, poetry_nahuatl
- **Changed keys** (new or modified):
  - `category` (MODIFIED): "Trans-Aktion" -> "Poetry" (en done, translate to de/tr/ko/uk/fr/es/he/ar)
  - `context` (NEEDS 7 NEW languages): Currently only en+de. Add tr/ko/uk/fr/es/he/ar.
- **Context**: The `context` field contains word lists (slash-separated) from literary source texts. Each language version should contain:
  1. The ORIGINAL-LANGUAGE words (Greek for Sappho, German for Hoelderlin, Japanese for Basho, Hindi for Mirabai, Yoruba for Oriki, Nahuatl for Nahuatl) — these stay unchanged across all languages
  2. TRANSLATED equivalents of the non-original words in the target language
  For example, Sappho EN has Greek originals + English translations. Sappho TR should have the same Greek originals + Turkish translations of the English words.
  For `category`: "Poetry" is the new English label replacing "Trans-Aktion". Translate naturally (e.g. DE "Poesie", TR "Şiir", KO "시", etc.).
  **Important**: The `context` field is NOT in en.ts — it lives directly in each JSON config file. Edit the JSON files directly to add the missing language keys.

<!-- Add new work orders here. Format:

### WO-YYYY-MM-DD-short-description
- **Session**: <number>
- **Scope**: en.ts (or additional files like canvas.ts, interception configs)
- **Changed keys** (new or modified):
  - `section.subsection.key` (NEW)
  - `section.subsection.key` (MODIFIED): "old value" -> "new value"
- **Context**: Brief semantic description to guide translation accuracy.

Tags:
  - (NEW) = key did not exist before, translate from English
  - (MODIFIED) = English text changed, all 5 translations are stale and must be re-done
-->

## Completed

### WO-2026-02-23-hebrew-arabic-interception-configs
- **Completed**: 2026-02-26
- **Scope**: 33 interception config JSONs (32 with LocalizedString + hunkydoryharmonizer) + llama_guard_explanations.json
- **Result**: Added he/ar to name, description, category in all configs. llama_guard_explanations: he/ar added to base_message, hint_message, all 13 codes, fallback. 4 configs skipped (flat string descriptions: lyrics_from_theme, lyrics_refinement, tags_generation, tag_suggestion_from_lyrics).

### WO-2026-02-26-surrealizer-fusion-strategy
- **Completed**: 2026-02-26
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar
- **Result**: 13 keys (4 MODIFIED + 9 NEW) translated into all 8 target languages.

### WO-2026-02-25-random-prompt-token-limit
- **Completed**: 2026-02-26
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar
- **Result**: 1 NEW key translated into all 8 target languages.

### WO-2026-02-25-sketch-canvas
- **Completed**: 2026-02-26
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar
- **Result**: 11 NEW keys translated into all 8 target languages.

### WO-2026-02-25-backend-status-dashboard
- **Completed**: 2026-02-26
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar
- **Result**: 31 NEW keys translated into all 8 target languages.

### WO-2026-02-23-hebrew-arabic-language-labels
- **Completed**: 2026-02-26
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar
- **Result**: 2 NEW keys (hebrewHe, arabicAr) translated with native language names.

### WO-2026-02-23-spanish-language-label
- **Completed**: 2026-02-26
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar
- **Result**: 1 NEW key (spanishEs) translated into all 8 target languages.

### WO-2026-02-24-trans-aktion-poetry-configs
- **Completed**: 2026-02-26
- **Scope**: 6 JSON files in `devserver/schemas/configs/interception/`: trans_aktion_basho, trans_aktion_hoelderlin, trans_aktion_mirabai, trans_aktion_nahuatl, trans_aktion_sappho, trans_aktion_yoruba_oriki
- **Result**: Added tr/ko/uk/fr/es/he/ar to name+description+category in all 6 trans_aktion configs. Note: original WO listed rilke/dickinson/whitman but actual files were sappho/mirabai/nahuatl/yoruba_oriki (renamed in a session that didn't update the WO).

### WO-2026-02-23-hebrew-full-translation (HE portion of hebrew-arabic-full-translation)
- **Completed**: 2026-02-24
- **Scope**: he.ts — full translation of all ~1370 keys from en.ts
- **Result**: All 30 top-level sections translated. vue-tsc and build pass.

### WO-2026-02-23-arabic-full-translation
- **Completed**: 2026-02-24
- **Scope**: ar.ts — full translation of all ~1370 keys from en.ts
- **Result**: All sections translated (3-way parallel split + assembly). vue-tsc and build pass.
