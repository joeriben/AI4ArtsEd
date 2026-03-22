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

### WO-2026-03-22-queue-transparency-device-lock
- **Session**: 279
- **Scope**: en.ts
- **Changed keys** (new or modified):
  - `mediaInput.queueAhead` (NEW): "{count} generation ahead of you | {count} generations ahead of you"
  - `mediaInput.deviceBusy` (NEW): "A generation is already running on this device."
  - `mediaInput.cancelPrevious` (NEW): "Cancel previous generation"
  - `mediaInput.generationCancelled` (NEW): "Generation cancelled."
- **Context**: Queue transparency for workshops (12+ devices). Shows how many generations are ahead. Per-device lock prevents duplicate generations from multi-tab. Cancel button lets user abort from another tab. User-facing, kid-friendly tone.

### WO-2026-03-21-compare-consistency
- **Session**: 277
- **Scope**: en.ts
- **Changed keys** (new or modified):
  - `compare.tabs.model` (MODIFIED): "Model Comparison" -> "Model Bias"
  - `compare.tabs.language` (MODIFIED): "Language Comparison" -> "Culture Bias"
  - `compare.tabs.vlm-analysis` (MODIFIED): "Image Analysis" -> "Image Understanding"
  - `compare.tabs.llm-model` (NEW): "Model Bias"
  - `compare.tabs.systemprompt` (MODIFIED): "System Prompt" -> "System Prompts"
  - `compare.tabs.temperature` (MODIFIED): "Temperature Comparison" -> "Hot & Cool"
  - `compare.llmModel.inputLabel` (NEW): "Your Message"
  - `compare.llmModel.inputPlaceholder` (NEW): "Type a message to send to all three models..."
  - `compare.llmModel.systemPromptLabel` (NEW): "SYSTEM PROMPT"
  - `compare.temperature.inputLabel` (NEW): "Your Message"
  - `compare.systemprompt.inputLabel` (NEW): "Your Message"
  - `compare.systemprompt.presets.gpt4_2023` (NEW): "GPT-4 (2023)"
  - `compare.systemprompt.presets.claude` (MODIFIED): "Claude (real product prompt)" -> "Claude Sonnet 4.6 (2025)"
- **Context**: Compare Hub redesigned from 4 to 6 tabs (3 image + 3 text). New LLM Model Comparison tab. Tab labels renamed to pedagogical focus (bias, understanding). Preset labels are short display names in dropdown selectors.

### WO-2026-03-21-vlm-analysis-comparison
- **Session**: 277
- **Scope**: en.ts
- **Changed keys** (new or modified):
  - `compare.tabs.vlm-analysis` (NEW): "Image Analysis"
  - `compare.vlmAnalysis.perspectiveLabel` (NEW): "Perspective"
  - `compare.vlmAnalysis.modelsLabel` (NEW): "Vision Models"
  - `compare.vlmAnalysis.analyzeBtn` (NEW): "Analyze Image"
  - `compare.vlmAnalysis.analyzing` (NEW): "Analyzing..."
  - `compare.vlmAnalysis.freePromptPlaceholder` (NEW): "Write your own analysis prompt..."
  - `compare.vlmAnalysis.perspectives.free` (NEW): "Free (your own prompt)"
  - `compare.vlmAnalysis.perspectives.neutral` (NEW): "Neutral description"
  - `compare.vlmAnalysis.perspectives.safety` (NEW): "Safety check"
  - `compare.vlmAnalysis.perspectives.bildwissenschaftlich` (NEW): "Art-historical (Panofsky)"
  - `compare.vlmAnalysis.perspectives.ikonik` (NEW): "Iconic analysis (Imdahl)"
  - `compare.vlmAnalysis.perspectives.bildungstheoretisch` (NEW): "Educational theory (Joerissen/Marotzki)"
  - `compare.vlmAnalysis.perspectives.ethisch` (NEW): "Ethical analysis"
  - `compare.vlmAnalysis.perspectives.kritisch` (NEW): "Decolonial / Critical"
- **Context**: New "Image Analysis" tab in the Compare Hub. Users upload an image, choose an analysis perspective, and multiple VLMs describe what they see. Perspective names are academic frameworks from art education — keep original German terms in parentheses for de.ts, translate descriptive parts.

### WO-2026-03-21-persona-model-and-settings-labels
- **Session**: 276
- **Scope**: en.ts
- **Changed keys** (new or modified):
  - `settings.models.persona` (NEW): "Persona Model"
  - `settings.models.stage1Text` (MODIFIED): "Stage 1 - Text Model" -> "Translation Model"
  - `settings.models.stage1Vision` (MODIFIED): "Stage 1 - Vision Model" -> "Image Recognition Model"
  - `settings.models.stage2Interception` (MODIFIED): "Stage 2 - Interception Model" -> "Transformation Model"
  - `settings.models.stage2Optimization` (MODIFIED): "Stage 2 - Optimization Model" -> "Prompt Optimization Model"
  - `settings.models.stage3` (MODIFIED): "Stage 3 - Translation/Safety Model" -> "Safety Model"
  - `settings.models.stage4Legacy` (MODIFIED): "Stage 4 - Legacy Model" -> "Legacy Model"
  - `settings.models.chatHelper` (MODIFIED): "Chat Helper Model" -> "Chat Model"
  - `settings.models.coding` (MODIFIED): "Code Generation (Tone.js, p5.js)" -> "Code Generation Model"
- **Context**: Settings page model labels. Removed internal pipeline stage numbering (Stage 1/2/3/4) in favor of functional descriptions that make sense to users. Added new PERSONA_MODEL field for Trashy's character mode (uses Opus, while regular chat uses Sonnet).

### WO-2026-03-21-i2x-default-prompt
- **Session**: 275
- **Scope**: en.ts
- **Changed keys** (new or modified):
  - `imageTransform.defaultPrompt` (NEW)
  - `multiImage.defaultPrompt` (NEW)
- **Context**: Default prompt for image/multi-image transformation when user leaves the context field empty. Used as fallback instruction for Stage 2 interception. Should work for both image and video transformation.

### WO-2026-03-20-interception-config-description-tr-ko
- **Session**: i18n audit
- **Scope**: 32 JSON files in `devserver/schemas/configs/interception/` → add `tr` and `ko` to `description` field
- **Affected files** (all missing `tr` + `ko` in `description`):
  - analog_photography_1870s.json, analog_photography_1970s.json, analogue_copy.json, bauhaus.json, clichéfilter_v2.json, confucianliterati.json, cooked_negatives.json, digital_photography.json, forceful.json, heartmula.json, hunkydoryharmonizer.json, image_transformation.json, jugendsprache.json, latent_lab.json, mad_world.json, multi_image_transformation.json, one_world.json, overdrive.json, p5js_simplifier.json, partial_elimination.json, piglatin.json, planetarizer.json, renaissance.json, sensitive.json, split_and_combine.json, stillepost.json, surrealizer.json, technicaldrawing.json, tellastory.json, theopposite.json, tonejs_composer.json, user_defined.json
- **What to do**: For each file, translate the `description.en` value into Turkish (`tr`) and Korean (`ko`). Add the translations as new keys in the `description` object alongside the existing languages.
- **Context**: These are interception config descriptions shown to users in the preset selector. They describe artistic/pedagogical transformation perspectives. Translate the `en` text — do NOT translate from `de` (some `de` descriptions are abbreviated/different). Keep technical terms (CLIP, T5, MMDiT, ComfyUI, etc.) in English. Keep the pedagogical/artistic tone of the original.
- **Note**: `category` field was already fixed in this session (all 10 categories now have all 9 languages). Only `description` remains.

### WO-2026-03-20-i18n-audit-vue-hardcoded
- **Session**: i18n audit
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (all NEW):
  - `mediaOutput.print` (NEW): "Print"
  - `mediaOutput.analyze` (NEW): "Image Analysis"
  - `mediaOutput.analyzing` (NEW): "Analyzing..."
  - `mediaOutput.generatedImage` (NEW): "Generated image"
  - `mediaOutput.mediaCreated` (NEW): "Media file created"
  - `mediaOutput.analysisTitle` (NEW): "Image Analysis"
  - `mediaOutput.close` (NEW): "Close"
  - `mediaOutput.saveSoon` (NEW): "Save (Coming Soon)"
  - `mediaOutput.trashyReflection` (NEW): "Talk to Trashy about:"
  - `mediaOutput.forwardToImageTransform` (NEW): "Forward to Image Transformation"
  - `imageTransform.yourImage` (NEW): "Your image"
  - `imageTransform.printTitle` (NEW): "Print: Transformed Image"
  - `imageTransform.downloadError` (NEW): "Download failed"
  - `imageTransform.analysisFailed` (NEW): "Image analysis failed"
  - `imageTransform.analysisError` (NEW): "Error during image analysis"
  - `textTransform.selectMedium` (NEW): "Choose a medium"
  - `textTransform.selectModel` (NEW): "Select a model"
  - `textTransform.runCode` (NEW): "Run code"
  - `textTransform.p5jsCode` (NEW): "P5.js Code"
  - `textTransform.livePreview` (NEW): "Live Preview"
  - `textTransform.tonejsCode` (NEW): "Tone.js Code"
  - `textTransform.audioPlayer` (NEW): "Audio Player"
  - `textTransform.forwardToImage` (NEW): "Forward to Image Transformation"
  - `textTransform.yourImage` (NEW): "Your image"
  - `textTransform.pleaseSelectModel` (NEW): "Please select a model"
  - `textTransform.saveSoon` (NEW): "Save feature coming soon!"
  - `textTransform.categories.image` (NEW): "Image"
  - `textTransform.categories.video` (NEW): "Video"
  - `textTransform.categories.sound` (NEW): "Sound"
  - `persona.toggleTTS` (NEW): "Toggle voice output"
- **Context**: Systematic i18n audit of Vue hardcoded strings. These keys were added to en.ts in preparation for wiring them into the Vue components (separate task). MediaOutput keys are button tooltips (Download, Print, Analyze), section headers, and alt text. ImageTransform keys are error messages (alerts) and print window title. TextTransform keys are section headings, category labels for media types (Image/Video/Sound), code editor labels, and alert messages. `persona.toggleTTS` was missing from a prior work order. "P5.js Code", "Tone.js Code", "Live Preview" are technical labels — keep English-based where natural, translate where the target language has a common equivalent. "Save (Coming Soon)" = placeholder for a not-yet-implemented bookmark feature.

### WO-2026-03-20-i2x-3d-category-labels
- **Session**: 265
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (all NEW):
  - `imageTransform.selectModel` (NEW): "Select a model"
  - `imageTransform.categories.image` (NEW): "Image"
  - `imageTransform.categories.video` (NEW): "Video"
  - `imageTransform.categories.threeD` (NEW): "3D"
  - `imageTransform.categories.sound` (NEW): "Sound"
  - `imageTransform.configs.qwenImg2img.name` (NEW): "QWEN Image Edit"
  - `imageTransform.configs.wan22I2v.name` (NEW): "WAN 2.2 Image-to-Video (14B)"
  - `imageTransform.configs.hunyuan3d.label` (NEW): "Hunyuan\n3D"
  - `imageTransform.configs.hunyuan3d.name` (NEW): "Hunyuan3D-2 Image-to-3D"
- **Context**: Category labels and model config names for the image transformation (i2x) page. Categories are media types (Image, Video, 3D, Sound). Config names are AI model display names — keep brand names untranslated (Qwen, WAN, Hunyuan3D). The `\n` in hunyuan3d.label is a line break for UI layout, preserve it.

### WO-2026-03-20-workshop-preload-unload
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (all NEW):
  - `workshop.actions.clearAll` (NEW): "Clear all GPU memory"
  - `workshop.actions.confirmUnload` (NEW): "Unload {name}? This will abort any running generation using this model."
  - `workshop.actions.confirmUnloadComfyui` (NEW): "Unloading {name} will free ALL ComfyUI models from memory (ComfyUI does not support per-model unloading). Continue?"
  - `workshop.actions.confirmClearAll` (NEW): "This will abort all running processes and unload ALL models from memory. Continue?"
  - `workshop.chat.preloadStart` (NEW): "Loading {count} model(s) into memory. This may take a few minutes — each model needs 30 seconds to 2 minutes."
  - `workshop.chat.preloadModel` (NEW): "Loading {name}..."
  - `workshop.chat.preloadDone` (NEW): "{name} loaded."
  - `workshop.chat.unloading` (NEW): "Unloading {name}..."
  - `workshop.chat.unloaded` (NEW): "{name} unloaded."
  - `workshop.chat.clearingAll` (NEW): "Clearing all GPU memory..."
  - `workshop.chat.clearedAll` (NEW): "All models unloaded. GPU memory is free."
- **Context**: Workshop planning page — preloading models into GPU, unloading models, clearing all GPU memory. Trashy chat messages shown during preload/unload operations. Confirmation dialogs for destructive actions. Keep placeholders ({name}, {count}) as-is.

### WO-2026-03-19-model-comparison-tab
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (all NEW):
  - `compare.tabs.model` (NEW): "Model Comparison"
- **Context**: Third tab in Compare Hub — compares same prompt across 3 image generation models (SD 3.5 Turbo, SD 3.5 Large, Flux 2). Tab label alongside "Language Comparison" and "Temperature Comparison".

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

### WO-2026-03-21-system-prompt-comparison-tab
- **Session**: System Prompt Comparison implementation
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (all NEW):
  - `compare.tabs.systemprompt` (NEW): "System Prompt"
  - `compare.systemprompt.inputPlaceholder` (NEW): "Type a message to send with all three system prompts..."
  - `compare.systemprompt.sendAll` (NEW): "Send to All"
  - `compare.systemprompt.sending` (NEW): "Sending..."
  - `compare.systemprompt.newConversation` (NEW): "New conversation"
  - `compare.systemprompt.noResponse` (NEW): "No response received"
  - `compare.systemprompt.error` (NEW): "Connection error"
  - `compare.systemprompt.subtitle` (NEW): "See how invisible instructions control AI behavior"
  - `compare.systemprompt.modelLabel` (NEW): "Model"
  - `compare.systemprompt.presetLabel` (NEW): "Preset"
  - `compare.systemprompt.promptLabel` (NEW): "System Prompt"
  - `compare.systemprompt.emptyPrompt` (NEW): "(no system prompt)"
  - `compare.systemprompt.custom` (NEW): "Custom"
  - `compare.systemprompt.presets.none` (NEW): "No system prompt"
  - `compare.systemprompt.presets.helpful` (NEW): "Helpful assistant"
  - `compare.systemprompt.presets.disagree` (NEW): "Always disagree"
  - `compare.systemprompt.presets.pirate` (NEW): "Pirate"
  - `compare.systemprompt.presets.poet` (NEW): "Poet"
  - `compare.systemprompt.presets.fiveyearold` (NEW): "Five-year-old"
  - `compare.systemprompt.presets.factsonly` (NEW): "Only facts"
- **Context**: New tab in the Compare Hub for system prompt comparison. Users send the same message to an AI with 3 different system prompts to see how invisible instructions control behavior. Preset names are UI labels for dropdown menus — translate naturally (e.g. "Pirat" in DE, not literal). The subtitle is a pedagogical tagline. "System Prompt" as a tab label may be kept in English in some languages where it's a recognized technical term, or translated if the language has a natural equivalent.
- **NOTE**: Keys `compare.systemprompt.sendAll`, `.sending`, `.newConversation`, `.noResponse`, `.error`, `.modelLabel` were MOVED to `compare.shared.*` (see WO below). Update your translations accordingly — delete the old per-mode keys and use the shared ones.

### WO-2026-03-21-compare-shared-keys
- **Session**: i18n deduplication
- **Scope**: en.ts → de/tr/ko/uk/fr/es/he/ar/bg
- **Changed keys** (all NEW — shared across Temperature + System Prompt tabs):
  - `compare.shared.sendAll` (NEW): "Send to All"
  - `compare.shared.sending` (NEW): "Sending..."
  - `compare.shared.newConversation` (NEW): "New conversation"
  - `compare.shared.noResponse` (NEW): "No response received"
  - `compare.shared.error` (NEW): "Connection error"
  - `compare.shared.modelLabel` (NEW): "Model"
  - `compare.shared.defaultModel` (NEW): "Default (Settings)"
- **REMOVED keys** (moved to shared, delete from all language files):
  - `compare.temperature.sendAll`, `.sending`, `.newConversation`, `.noResponse`, `.error`, `.modelLabel`
  - `compare.systemprompt.sendAll`, `.sending`, `.newConversation`, `.noResponse`, `.error`, `.modelLabel`
- **Context**: Deduplication — these strings were identical across Temperature and System Prompt comparison tabs. Now shared. "Default (Settings)" is the label for the default model option in the model selector dropdown.

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
