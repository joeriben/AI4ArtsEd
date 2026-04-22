# i18n Translation Work Orders

Instructions for the `i18n-translator` agent: process all entries under **Pending**, translate
the listed keys from `en.ts` into `de.ts`, `tr.ts`, `ko.ts`, `uk.ts`, `fr.ts`, `es.ts`, `he.ts`, `ar.ts`, `bg.ts`, then move
each processed work order to **Completed** with a date stamp.

## Pending

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

### WO-2026-03-20-interception-config-description-tr-ko
- **Session**: i18n audit
- **Scope**: 32 JSON files in `devserver/schemas/configs/interception/` → add `tr` and `ko` to `description` field
- **Affected files** (all missing `tr` + `ko` in `description`):
  - analog_photography_1870s.json, analog_photography_1970s.json, analogue_copy.json, bauhaus.json, clichéfilter_v2.json, confucianliterati.json, cooked_negatives.json, digital_photography.json, forceful.json, heartmula.json, hunkydoryharmonizer.json, image_transformation.json, jugendsprache.json, latent_lab.json, mad_world.json, multi_image_transformation.json, one_world.json, overdrive.json, p5js_simplifier.json, partial_elimination.json, piglatin.json, planetarizer.json, renaissance.json, sensitive.json, split_and_combine.json, stillepost.json, surrealizer.json, technicaldrawing.json, tellastory.json, theopposite.json, tonejs_composer.json, user_defined.json
- **What to do**: For each file, translate the `description.en` value into Turkish (`tr`) and Korean (`ko`). Add the translations as new keys in the `description` object alongside the existing languages.
- **Context**: These are interception config descriptions shown to users in the preset selector. They describe artistic/pedagogical transformation perspectives. Translate the `en` text — do NOT translate from `de` (some `de` descriptions are abbreviated/different). Keep technical terms (CLIP, T5, MMDiT, ComfyUI, etc.) in English. Keep the pedagogical/artistic tone of the original.
- **Note**: `category` field was already fixed in this session (all 10 categories now have all 9 languages). Only `description` remains.

## Completed


### WO-2026-03-29-remove-edutainment-emoji
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-29-canvas-outputdrawer-mediaoutputbox
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-29-seed-random-variation
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-29-loading-progress
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-29-encoding-transparency
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-29-sd35-img2img
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-28-ollama-removal-i18n
- **Completed**: 2026-04-22
- **Result**: resolved in second i18n consolidation pass (see commit log for details).

### WO-2026-03-26-arcimboldo-mosaic-tab
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-26-composable-diffusion-tab
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-25-deferred-llm-activation
- **Completed**: 2026-04-22
- **Result**: resolved in second i18n consolidation pass (see commit log for details).

### WO-2026-03-25-workshop-greeting-rewrite
- **Completed**: 2026-04-22
- **Result**: REMOVED key propagated — already absent from all target files (see commit log for details).

### WO-2026-03-25-scene-graph-interception-config
- **Completed**: 2026-04-22
- **Result**: obsolete — listed keys no longer in en.ts (see commit log for details).

### WO-2026-03-24-test-note-button
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-24-wavetable-region-extraction
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-24-synth-glide-recording
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-24-bias-model-scenarios
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-24-synth-filter
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-24-synth-presets
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-23-dim-explorer-modes
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-23-trashy-analysis-reflection
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-23-pca-axes
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-23-semantic-wavetable
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-22-latent-synth-start-position
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-22-api-management-tab
- **Completed**: 2026-04-22
- **Result**: obsolete — listed keys no longer in en.ts (see commit log for details).

### WO-2026-03-22-queue-transparency-device-lock
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-21-compare-consistency
- **Completed**: 2026-04-22
- **Result**: resolved in second i18n consolidation pass (see commit log for details).

### WO-2026-03-21-vlm-analysis-comparison
- **Completed**: 2026-04-22
- **Result**: resolved in second i18n consolidation pass (see commit log for details).

### WO-2026-03-21-persona-model-and-settings-labels
- **Completed**: 2026-04-22
- **Result**: resolved in second i18n consolidation pass (see commit log for details).

### WO-2026-03-21-i2x-default-prompt
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-20-i18n-audit-vue-hardcoded
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-20-i2x-3d-category-labels
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-20-workshop-preload-unload
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-19-model-comparison-tab
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-19-temperature-model-label
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-19-compare-hub-temperature
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-19-persona-new-dialog
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-19-workshop-title-rename
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-19-trashy-overlay-i18n
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-19-backend-status-loaded-models
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-18-ai-persona-page
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-18-compare-slot-actions
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-17-comparison-mode
- **Completed**: 2026-04-22
- **Result**: obsolete — listed keys no longer in en.ts (see commit log for details).

### WO-2026-03-17-model-provenance-card
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-17-usage-agreement
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-12-mammouth-provider
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-11-canvas-output-drawer-zoom
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-06-3d-media-output
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-05-generation-button-i18n
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-03-bulgarian-language-label
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-03-cloud-processing-label
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-19-workshop-planning-page
- **Completed**: 2026-04-22
- **Result**: obsolete — listed keys no longer in en.ts (see commit log for details).

### WO-2026-03-21-system-prompt-comparison-tab
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).

### WO-2026-03-21-compare-shared-keys
- **Completed**: 2026-04-22
- **Result**: bulk-resolved by en.ts audit sync (see commit log for details).


### WO-2026-04-22-safety-age-labels-realigned
- **Completed**: 2026-04-22
- **Scope**: en.ts -> de/tr/ko/uk/fr/es/he/ar/bg
- **Result**: All 6 MODIFIED keys replaced in all 9 target languages. Age ranges updated to kids 8–13 / youth 14–18. Descriptions rewritten to reflect new filter calibration (kids: strict no-horror/no-violence/no-nudity; youth: blocks graphic violence/gore/nudity/hate/self-harm/terrorism — non-graphic horror allowed). No national rating trademark mentioned; §86a kept literally; DSGVO localised to GDPR/RGPD/KVKK per language convention.

### WO-2026-04-06-compare-model-availability
- **Completed**: 2026-04-22
- **Scope**: en.ts -> de/tr/ko/uk/fr/es/he/ar/bg
- **Result**: `compare.shared.modelNotDownloaded` (NEW) translated into all 9 target languages.

### WO-2026-03-03-comfyui-label-cleanup
- **Completed**: 2026-03-03
- **Scope**: en.ts + 8 target language files
- **Result**: Already synced (SwarmUI suffix was already removed in all files).

### WO-2026-03-02-looper-section-header
- **Completed**: 2026-03-03
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar
- **Result**: 1 NEW key translated into all 8 target languages.

### WO-2026-03-02-flatten-synth-toggles
- **Completed**: 2026-03-03
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar
- **Result**: 12 NEW keys translated, 5 REMOVED keys deleted (loopOn, loopOff, modeLoop, modePingPong, modeWavetable) from all 8 target files.

### WO-2026-03-01-step-sequencer
- **Completed**: 2026-03-03
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar
- **Result**: 16 NEW keys (sequencer controls + 8 patterns) translated into all 8 target languages.

### WO-2026-03-01-semantic-axes-synth
- **Completed**: 2026-03-03
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar
- **Result**: 5 NEW keys translated into all 8 target languages.

### WO-2026-03-01-ionos-provider-strings
- **Completed**: 2026-03-03
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar
- **Result**: 3 NEW keys translated. DSGVO→KVKK (TR), RGPD (FR/ES), GDPR (others).

### WO-2026-02-28-optimization-loading-messages
- **Completed**: 2026-03-03
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar
- **Result**: 3 NEW keys (loadingDefault, loadingSd35, loadingTranslateHint) translated into all 8 target languages. Also resolved as audit-detected missing keys.

### WO-2026-02-28-t5-uses-your-text
- **Completed**: 2026-03-03
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar
- **Result**: 1 NEW key translated into all 8 target languages.

### WO-2026-02-27-expert-energy-fact-reword
- **Completed**: 2026-03-03
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar
- **Result**: 1 MODIFIED key (emoji + text reword) updated in all 8 target languages.

### WO-2026-02-27-replace-chart-emoji
- **Completed**: 2026-03-03
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar
- **Result**: 2 MODIFIED keys (emoji-only changes) updated in all 8 target languages.

### WO-2026-02-27-denoising-progress-view
- **Completed**: 2026-03-03
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar
- **Result**: 13 NEW keys translated into all 8 target languages.

### WO-2026-02-27-privacy-policy
- **Completed**: 2026-03-03
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar
- **Result**: 20 NEW keys (10 sections × title+content) translated into all 8 target languages with proper GDPR/DSGVO/RGPD/KVKK terminology.

### WO-2026-02-28-poetry-rename-context-category
- **Completed**: 2026-03-03
- **Scope**: 6 JSON files in devserver/schemas/configs/interception/
- **Result**: category "Trans-Aktion"→translated "Poetry" in all 8 languages. context field expanded from en+de to all 9 languages (original-language words preserved, translations added).

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
