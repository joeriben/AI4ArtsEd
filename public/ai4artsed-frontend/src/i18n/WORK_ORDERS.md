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

### WO-2026-03-18-compare-slot-actions
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (all NEW):
  - `compare.favorite` (NEW): "Add to favorites"
  - `compare.unfavorite` (NEW): "Remove from favorites"
  - `compare.forward` (NEW): "Forward to image transformation"
  - `compare.download` (NEW): "Download image"
  - `compare.analyze` (NEW): "Analyze image"
- **Context**: Action buttons under each generated image in the Language Comparison page. Favorite = heart icon toggle, Forward = send image to image transformation page, Download = save image locally, Analyze = describe via VLM and inject into Trashy chat. Keep translations short (button tooltips).

### WO-2026-03-17-comparison-mode
- **Session**: 265
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (all NEW):
  - `compare.promptLabel` (NEW): "Your Idea"
  - `compare.promptPlaceholder` (NEW): "Enter a prompt..."
  - `compare.platformLanguages` (NEW): "Platform Languages"
  - `compare.minorityLanguages` (NEW): "Minority Languages"
  - `compare.selectHint` (NEW): "{count} of {max} languages selected"
  - `compare.generateAll` (NEW): "Compare All"
  - `compare.generatingAll` (NEW): "Generating..."
  - `compare.generating` (NEW): "Generating..."
  - `compare.waiting` (NEW): "Waiting..."
  - `compare.chatPlaceholder` (NEW): "Ask Trashy..."
  - `compare.trashyGreeting` (NEW): greeting text for comparison mode
  - `compare.trashyTranslating` (NEW): "Translating your prompt..."
  - `compare.trashyGenerating` (NEW): "Now generating images..."
- **Context**: Language Comparison Mode — shows how the same prompt in different languages produces different images due to CLIP/T5 encoding bias. Trashy is the AI helper bot. The greeting should be inviting and age-appropriate (ages 9-17). Keep translations concise.

### WO-2026-03-17-model-provenance-card
- **Session**: 265
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (all NEW):
  - `provenance.title` (NEW): "About This Model"
  - `provenance.madeBy` (NEW): "Made by:"
  - `provenance.learnedFrom` (NEW): "Learned from:"
  - `provenance.howBig` (NEW): "How big:"
  - `provenance.kidsNote` (NEW): "Not all creators were asked if the AI could learn from their work."
  - `provenance.publisher` (NEW): "Publisher"
  - `provenance.architecture` (NEW): "Architecture"
  - `provenance.parameters` (NEW): "Parameters"
  - `provenance.license` (NEW): "License"
  - `provenance.trainingData` (NEW): "Training Data"
  - `provenance.safetyByDesign` (NEW): "Safety by Design"
  - `provenance.sources` (NEW): "Data Sources"
  - `provenance.consent` (NEW): "Creator Consent"
  - `provenance.consentValues.none` (NEW): "None"
  - `provenance.consentValues.partial` (NEW): "Partial"
  - `provenance.consentValues.full` (NEW): "Full"
  - `provenance.consentValues.unknown` (NEW): "Unknown"
  - `provenance.knownBiases` (NEW): "Known Biases"
  - `provenance.knownGaps` (NEW): "Known Gaps"
  - `provenance.youthReflection` (NEW): "Every model has a perspective shaped by its training data. What voices might be missing?"
- **Context**: Model Provenance Card — shows training data origin, known biases, and known gaps for each AI model. Displayed post-generation under the output image/audio. Kids mode uses simplified language, youth mode adds a reflection question. The `kidsNote` and `youthReflection` are pedagogically important — they should be translated with care for age-appropriate tone.

### WO-2026-03-17-usage-agreement
- **Session**: 264
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (all MODIFIED — rewritten from Session 263):
  - `usageAgreement.title` (MODIFIED): "Usage Notice" → "Usage Agreement"
  - `usageAgreement.text` (MODIFIED): rewritten — now frames as binding conditions, not informational notice
  - `usageAgreement.responsibilities.supervision` (MODIFIED): "Ensure active supervision..." → "Actively supervise participants..."
  - `usageAgreement.responsibilities.misuse` (MODIFIED): minor rewording
  - `usageAgreement.responsibilities.noGuarantee` (MODIFIED): "replaces" → "can replace"
  - `usageAgreement.checkbox` (MODIFIED): now includes explicit consent ("I agree to these conditions")
- **Context**: Usage agreement (not notice!) shown before platform access (24h cookie). This is a binding consent page — workshop leaders agree to conditions. Do NOT enumerate harmful content categories. Tone: clear and direct, educator-to-educator, not legal/bureaucratic. Key message: platform is well-protected but no system is perfect, use is tied to these conditions.

### WO-2026-03-12-mammouth-provider
- **Session**: 259
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (new or modified):
  - `settings.api.mammouthEu` (NEW)
  - `settings.api.mammouthInfo` (NEW)
  - `settings.api.mammouthDsgvo` (NEW)
- **Context**: New cloud LLM provider "Mammouth AI" — EU-based, DSGVO-compliant API aggregator. Used in Settings dropdown. mammouthEu = dropdown label, mammouthInfo = info box title, mammouthDsgvo = DSGVO compliance note.

### WO-2026-03-11-canvas-output-drawer-zoom
- **Session**: 256
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (new or modified):
  - `canvas.outputDrawer.title` (NEW)
  - `canvas.outputDrawer.emptyState` (NEW)
  - `canvas.outputDrawer.download` (NEW)
  - `canvas.outputDrawer.imageAlt` (NEW)
  - `canvas.zoomControls.zoomIn` (NEW)
  - `canvas.zoomControls.zoomOut` (NEW)
  - `canvas.zoomControls.resetZoom` (NEW)
  - `canvas.zoomControls.fitToContent` (NEW)
- **Context**: Canvas modernization — new Output Drawer component shows media outputs with attribution. Zoom controls for pan/zoom canvas. All are short UI labels.

### WO-2026-03-06-3d-media-output
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (new or modified):
  - `mediaOutput.download` (NEW)
  - `mediaOutput.model3dReady` (NEW)
  - `mediaOutput.model3dInteractive` (NEW)
  - `mediaOutput.downloadGlb` (NEW)
- **Context**: New 3D generation media type (Hunyuan3D-2). `mediaOutput.model3dReady` = shown when 3D model is generated but no interactive viewer available. `mediaOutput.model3dInteractive` = hint for touch/mouse interaction. `mediaOutput.downloadGlb` = download button for GLB 3D file.

### WO-2026-03-05-generation-button-i18n
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (new or modified):
  - `common.start` (NEW)
  - `common.generating` (NEW)
  - `generationError.busy` (NEW)
  - `generationError.offline` (NEW)
  - `generationError.unknown` (NEW)
  - `surrealizer.executeButton` (NEW)
  - `surrealizer.executingButton` (NEW)
- **Context**: Unified generation button across all views. `common.start` = default button label. `common.generating` = label during active generation. `generationError.*` = user-facing error messages when backend rejects (queue full, service down, etc). `surrealizer.executeButton/executingButton` = surrealizer-specific labels replacing hardcoded German strings.

### WO-2026-03-03-bulgarian-language-label
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar (bg already has full translation)
- **Changed keys** (new or modified):
  - `settings.general.bulgarianBg` (NEW)
- **Context**: Language label for Bulgarian in the settings dropdown. Translate as "Bulgarian (bg)" with native language name in the target language.

### WO-2026-03-03-cloud-processing-label
- **Scope**: en.ts
- **Changed keys** (new or modified):
  - `edutainment.denoising.cloudProcessing` (NEW)
- **Context**: Loading label shown during cloud/API image generation (e.g. Gemini 3 Pro via OpenRouter, GPT Image 1). Replaces misleading "Loading model into GPU memory..." for models that don't use local GPU. Short status message.

## Completed

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
