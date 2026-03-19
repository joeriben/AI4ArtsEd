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

### WO-2026-03-19-temperature-model-label
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (all NEW):
  - `compare.temperature.modelLabel` (NEW): "Model"
- **Context**: Label for model selector dropdown in Temperature Comparison page. Same semantics as `compare.modelLabel` (already exists for Language Comparison). Short label.

### WO-2026-03-19-compare-hub-temperature
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (all NEW):
  - `compare.tabs.language` (NEW): "Language Comparison"
  - `compare.tabs.temperature` (NEW): "Temperature Comparison"
  - `compare.temperature.inputPlaceholder` (NEW): "Type a message to send at all three temperatures..."
  - `compare.temperature.sendAll` (NEW): "Send to All"
  - `compare.temperature.sending` (NEW): "Sending..."
  - `compare.temperature.cold` (NEW): "Deterministic"
  - `compare.temperature.warm` (NEW): "Balanced"
  - `compare.temperature.hot` (NEW): "Creative"
  - `compare.temperature.newConversation` (NEW): "New conversation"
  - `compare.temperature.noResponse` (NEW): "No response received"
  - `compare.temperature.error` (NEW): "Connection error"
  - `compare.temperature.subtitle` (NEW): "See how randomness changes what the AI says"
- **Context**: Compare Hub with tab navigation (Language Comparison / Temperature Comparison). Temperature mode sends the same chat message at 3 different AI "temperatures" (0=deterministic, 0.5=balanced, 1.0=creative) and shows 3 parallel diverging conversations. Educational tool showing how randomness affects AI behavior. "Deterministic/Balanced/Creative" are the column labels for the 3 temperature levels.

### WO-2026-03-19-persona-new-dialog
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (all NEW):
  - `persona.newDialog` (NEW): "New dialog"
- **Context**: Button in persona chat header to start a fresh conversation. Keep short — used as button tooltip. Same resistant, machine-like tone as other persona strings.

### WO-2026-03-19-workshop-title-rename
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (MODIFIED):
  - `workshop.title` (MODIFIED): "Collaborative Workshop Preparation" → "Workshop Planning"
- **Context**: Page renamed from "Collaborative Workshop Preparation" to "Workshop Planning" — simpler, clearer. German: "Workshop-Planung".

### WO-2026-03-19-trashy-overlay-i18n
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (all NEW):
  - `trashy.placeholder` (NEW): "How can I help you?"
  - `trashy.greeting` (NEW): "Hello! I am your AI helper. Ask me questions about AI4ArtsEd or let me advise you on your prompt."
  - `trashy.noResponse` (NEW): "No response received."
  - `trashy.thinking` (NEW): "Thinking..."
  - `trashy.sendError` (NEW): "Sorry, there was an error sending the message. Please try again."
  - `trashy.sendTooltip` (NEW): "Send message (Enter)"
  - `trashy.openTooltip` (NEW): "Open AI helper (Trashy) — drag to move, double-click to reset"
  - `trashy.closeTooltip` (NEW): "Close"
- **Context**: Global Trashy chat overlay (ChatOverlay.vue). Previously all strings were hardcoded in German. The placeholder is the most visible — it should be warm and inviting, using plural "you" (formal/group address in languages that have it). German: "Wie kann ich Euch weiterhelfen?" (not "dir", use "Euch").

### WO-2026-03-19-backend-status-loaded-models
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (all NEW):
  - `settings.backendStatus.model` (NEW): "Model"
  - `settings.backendStatus.loadedModels` (NEW): "Loaded Models"
  - `settings.backendStatus.foreignProcesses` (NEW): "Other GPU Processes"
  - `settings.backendStatus.noModelsLoaded` (NEW): "No models currently loaded"
  - `settings.backendStatus.vramUsage` (NEW): "VRAM"
  - `settings.backendStatus.inUse` (NEW): "In Use"
  - `settings.backendStatus.idle` (NEW): "Idle"
  - `settings.backendStatus.lastUsed` (NEW): "Last Used"
  - `settings.backendStatus.command` (NEW): "Command"
  - `settings.backendStatus.foreignVram` (NEW): "External VRAM usage"
  - `settings.backendStatus.showLoadedModels` (NEW): "Show loaded models"
  - `settings.backendStatus.hideLoadedModels` (NEW): "Hide loaded models"
  - `settings.backendStatus.showProcesses` (NEW): "Show processes"
  - `settings.backendStatus.hideProcesses` (NEW): "Hide processes"
  - `settings.backendStatus.ownModels` (NEW): "Own Models"
  - `settings.backendStatus.pid` (NEW): "PID"
- **Context**: Backend Status dashboard now shows which AI models are currently loaded in GPU memory and foreign GPU processes (Ollama, etc.). Technical page for workshop leaders — short, precise labels.

### WO-2026-03-18-ai-persona-page
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (all NEW):
  - `persona.title` (NEW): "Persona"
  - `persona.inputPlaceholder` (NEW): "Say something..."
  - `persona.toggleTTS` (NEW): "Toggle voice output"
  - `persona.fallbackGreeting` (NEW): "Hello, I am Persona. I am a machine. Not an assistant. Talk to me."
- **Context**: New "AI Persona" page — a dialogic mode where the AI is NOT a service tool but an aesthetically opinionated conversation partner. The title "Dialogue" is deliberate (not "Chat"). The fallback greeting sets the resistant, honest tone. Keep translations matching that tone: direct, machine-like, no friendliness or enthusiasm.

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

### WO-2026-03-19-workshop-planning-page
- **Session**: 268
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (all NEW):
  - `workshop.title` (NEW): "Collaborative Workshop Preparation"
  - `workshop.memory.label` (NEW): "Graphics Card Memory"
  - `workshop.memory.system` (NEW): "System"
  - `workshop.memory.free` (NEW): "free"
  - `workshop.memory.used` (NEW): "{used} / {total} Gigabytes used"
  - `workshop.memory.overBudget` (NEW): "— does not fit!"
  - `workshop.models.label` (NEW): "Models — drag to memory or click to activate"
  - `workshop.models.image` (NEW): "Images"
  - `workshop.models.video` (NEW): "Videos"
  - `workshop.models.music` (NEW): "Music"
  - `workshop.models.sound` (NEW): "Sounds"
  - `workshop.models.threeD` (NEW): "3D"
  - `workshop.models.needsGb` (NEW): "needs {gb} Gigabytes"
  - `workshop.models.loaded` (NEW): "(loaded)"
  - `workshop.models.cloudUs` (NEW): "Server-based — server in the USA"
  - `workshop.models.cloudEu` (NEW): "Server-based — server in Europe"
  - `workshop.confirm.load` (NEW): "Load models into memory now"
  - `workshop.confirm.loading` (NEW): "Loading models..."
  - `workshop.confirm.ready` (NEW): "All loaded — ready to go!"
  - `workshop.confirm.resultLoaded` (NEW): "Loaded: {models}"
  - `workshop.confirm.resultSkipped` (NEW): "On first use: {models}"
  - `workshop.confirm.resultError` (NEW): "Error: {details}"
  - `workshop.chat.cloudAdded` (NEW): cloud model explanation with {name}, {publisher}, {region} params
  - `workshop.chat.overBudget` (NEW): over-budget warning with {name}, {gb} params
  - `workshop.chat.freeSpace` (NEW): space remaining with {name}, {gb}, {free} params
  - `workshop.chat.connectionError` (NEW): "Connection error — please try again."
  - `workshop.chat.regionEu` (NEW): "Europe"
  - `workshop.chat.regionUs` (NEW): "the USA"
  - `workshop.greeting.intro` (NEW): Trashy greeting intro
  - `workshop.greeting.resources` (NEW): resource explanation
  - `workshop.greeting.memoryMetaphor` (NEW): book metaphor with {gb}, {books}, {meters} params
  - `workshop.greeting.limits` (NEW): memory limits note
  - `workshop.greeting.planning` (NEW): planning rationale
  - `workshop.greeting.flexibility` (NEW): flexibility reassurance
  - `workshop.greeting.callToAction` (NEW): call to action
- **Context**: Workshop planning page where groups collaboratively select AI models for a session. The tone is friendly, addressing a group of students/participants ("you" plural). Memory/VRAM is called "Speicher der Grafikkarte" (graphics card memory) — NO technical jargon (no VRAM, GPU, RAM). The greeting is from "Trashy", the platform's help mascot.

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
