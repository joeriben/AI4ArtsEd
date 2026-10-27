# Development Decisions - Current & Active
**AI4ArtsEd DevServer - Active Architectural Decisions**

> **IMPORTANT FOR ALL TASKS:**
> Every significant development decision MUST be documented here.
> Format: Date, Decision, Reasoning, Affected Files

---

## 2026-10-18: `flux3` has no Adaption instruction

**Anlass:** The model card of FLUX 3 Image Klein says: "Do not use the model without a prompt upsampler." The system prompt of BFL's upsampler was checked part by part against the Adaption, which leaves the content of the Interception as it is (59eab5a8, SD 3.5). Justifiable as Adaption were its fidelity rules, its restrictions and three translations of a stated wish into the model's reading: a negation as what is present, "realistic" as a photograph, a time of day as light. Its expansion into a scene description and its content decisions are not: everything left open decided as one plan, a photograph where no style is given, a profile of every person in focus with ethnicity, gender, age range and skin tone, text written where none is given. A probe on 2026-10-18 ran five recorded Interception texts on the standard test prompt through Stage 3 (as the Flow sends them, `force_translation`) and `flux3` without an Adaption, with two seeds each. One negation became an object ("the potatoes lie under the surface", both seeds); no time of day became writing, and no image carried writing.

**Entschieden:** `flux3` carries no `optimization_instruction`. The Interception text reaches FLUX 3 Image Klein as Stage 3 hands it over, as for SD 3.5 and Flux 2.

**Begründung:** In the probe the justifiable parts would have caught one case. The other cases in the probe are metaphors taken literally ("a thin fire begins to run beneath the skin" as flames on the meadow, "makes the clay glow" as a glowing streak on the wall). They fall under the upsampler's rule to turn moods into observable physical facts, which is a content decision.

**Betroffene Dateien:** none; `devserver/schemas/chunks/output_image_flux3.json` and `devserver/schemas/configs/output/flux3.json` carry no instruction.

## 2026-10-18: FLUX 3 Image Klein and Gemini Nano Banana 2.1 stand in the Flow, on the Canvas and with the agents; Nano Banana 2.1 runs through Mammouth AI

**Anlass:** The instruction of 2026-10-18 was to add FLUX 3 to the Flow and the Canvas and to make it available to the agents, and to make Gemini 3.1 available as far as the provider configuration allows, with the question whether OpenRouter allows it on the EU side. The model linked with it is Google's Gemini Nano Banana 2.1, which Google's model page names "An update to Nano Banana 2 (Gemini 3.1 Flash Image)".

**Entschieden:**
- `flux3` and the new config `gemini_nano_banana_2_1` stand in the Flow's image choice, after Flux 2 and after Gemini 3 Pro, in the three config lists of the agents (Resona's tool, Resona's canvas authoring, Persona) and in Trashy's reference. The Canvas generation node lists every output config, and so both.
- `gemini_nano_banana_2_1` runs through Mammouth AI (`/v1/images/generations`, model `gemini-nano-banana-2.1`), as Gemini 3 Pro Image does. Its config is marked `frontier_image`: without a usable Mammouth account it is switched off in the Flow, and Settings shows it with its own rows under the API keys.
- Neither config has a quality stage; the Flow card shows no quality line for them.

**Begründung:** The platform reaches OpenRouter only on its EU host (`devserver/config/llm_providers.json`). That host's catalogue held no model with image output on 2026-10-18, and OpenRouter serves Nano Banana 2.1 through Google AI Studio only. Mammouth AI carries the model, and it is the platform's recorded GDPR route for Gemini 3 Pro Image (entry of 2026-09-23).

**Abweichung:** The entry of 2026-09-23 sets one notice of four rows in Settings, for one frontier image model. With a second config marked `frontier_image`, Settings shows two blocks of four rows, and the Mammouth balance stands in both.

**Offen:** No image has been generated with `gemini_nano_banana_2_1`; that Mammouth answers this model on `/v1/images/generations` with `data[0].b64_json` is not tested. On 2026-10-18 the Mammouth account of the development server had no credit, and both Gemini configs were switched off in the Flow. Workshop planning and preloading list neither new config. Google's Additional Terms for the Gemini API say "You must be 18 years of age or older to use the APIs" and exclude services "directed towards or ... likely to be accessed by individuals under the age of 18"; whether they bind the platform through Mammouth is not known. The new config carries no `audience` block.

**Betroffene Dateien:** `devserver/schemas/chunks/output_image_gemini_nano_banana_2_1.json`, `devserver/schemas/configs/output/gemini_nano_banana_2_1.json`, `devserver/config/model_register.json`, `devserver/my_app/services/tool_registry.py`, `devserver/my_app/services/canvas_graph_authoring.py`, `devserver/trashy_interface_reference.txt`, `devserver/tests/test_output_config_carry_list.py`, `devserver/tests/test_safety_coverage_map.py`, `public/ai4artsed-frontend/src/views/x2x_flow.vue`, `public/ai4artsed-frontend/src/views/ai_persona.vue`, `public/ai4artsed-frontend/src/composables/useModelAvailability.ts`, `docs/QUALITAETSSTUFEN_MODELLE.md`

## 2026-10-18: FLUX 3 Image Klein stands in the Latent Lab beside Flux 2

**Anlass:** Black Forest Labs released FLUX 3 Image Klein on 2026-10-15. The instruction of 2026-10-18 was to install it, to keep Flux 2, also for the historical side of the Latent Lab, and to offer FLUX 3 wherever Flux 2 stands in the Latent Lab.

**Entschieden:** The output config `flux3` runs the distilled FLUX 3 Image Klein checkpoint in BF16 on ComfyUI, which loads it from v0.41.0 on. "Flux 3 Klein" is selectable wherever Flux 2 is selectable in the Latent Lab, after Flux 2 in each list; no default selection and no set changed. Flux 2 stays.

**Begründung:** The instruction above.

**Offen:** The workflow leaves out BFL's prompt upsampler, although the model card says: "Do not use the model without a prompt upsampler." The prompt reaches the text encoder as the platform hands it over, and the config carries no `optimization_instruction`. The upsampler's system prompt gives every person in focus an ethnicity, a gender, an age range and a skin tone. `flux3` gets no Adaption instruction of the platform's own (entry "`flux3` has no Adaption instruction", 2026-10-18).

**Betroffene Dateien:** `devserver/schemas/chunks/output_image_flux3.json`, `devserver/schemas/configs/output/flux3.json`, `devserver/config/model_register.json`, `devserver/tests/test_safety_coverage_map.py`, `public/ai4artsed-frontend/src/data/rasterImageModels.ts`, `public/ai4artsed-frontend/src/views/latent_lab/mean_images.vue`, `public/ai4artsed-frontend/src/views/compare/model_comparison.vue`, `public/ai4artsed-frontend/src/views/compare/language_comparison.vue`, `public/ai4artsed-frontend/src/i18n/en.ts`, `devserver/trashy_interface_reference.txt`, `devserver/my_app/knowledge/platform_items.json`, `download_flux3.sh`

## 2026-10-10: The halt at the prompt is cancelled, and its machinery is removed

**Anlass:** The entry of 2026-09-03 had cancelled the halt of 2026-08-28 (the older entry says so itself), and `x2x_flow.vue` still carried the halt: the docstring over `runGenerate` and the page description claimed the halt, the code set `heldRun` and continued it in the same synchronous step, so the halt face of the generate box was never rendered (code review 2026-10-10, finding S-014).

**Entschieden:** The halt at the prompt is cancelled. A generating run goes from the adaption to its model without stopping. The halt machinery is removed from `x2x_flow.vue`: `heldRun`, `haltActive`, `heldPrompt`, `heldCaption`, `heldLongForm`, `setHeldPrompt`, `continueHeldRun`, `logPromptEdit`, the halt face of the generate box and the `haltActive` terms in `busy`, `genPhase`, `genExpanded`, `runCaption` and `onGenClick`. The handoff to the model is `sendRun(run, text, caption)`. The page description no longer states the halt.

**Begründung:** After the first run the prompt is adjusted better on the table and the run started again than confirmed mid-run. Of the removed code, the halt face (`haltActive === true` in any render) and the `held.card` branches were unreachable: both call sites set `card: null`, and `heldRun` was non-null only inside one synchronous span with no render and no watcher in it, so no face, caption or state ever showed it. `continueHeldRun`, `setHeldPrompt`, `heldRun` and the held fields sat on the live path of every generating run, and `logPromptEdit` ran whenever the interception text carried surrounding whitespace (corrected after the second review of 2026-10-10; the first wording called all of it unreachable).

**Nebenwirkung:** `continueHeldRun` derived "edited by hand" from `text.trim() !== text`. An interception text with surrounding whitespace (the stream is accumulated unstripped, and stays so when the adaption answers nothing) was therefore treated as a hand edit: it was filed through the prompt-change log route (itself removed the same day) and the seed yardstick (`seedKey`) was dropped for that run. The second caption request on the `resume === 'adaption'` path (a second `/api/schema/pipeline/optimize` request with the "adapting" face shown) needed whitespace in an analysis text instead, since no interception text exists on that path, and an untrimmed `t5` kept by `keepAdapted` could set it off on a later press; the three effects never met on one path (corrected after the second review of 2026-10-10). All of them stop with this change: a whitespace-only interception text now keeps `seedKey`; a hand edit cannot happen on this path.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/x2x_flow.vue`, `docs/AILIT_ORTE_ZUORDNUNG.md`, `docs/OECD_AILIT_ABDECKUNG.md`, and the evidence strings in `devserver/my_app/knowledge/ailit_coverage.json`, `docs/AILIT_ZUORDNUNGSTABELLE.tsv`, `docs/ailit/unterstuetzung.tsv` (7 files in all, corrected after the second review of 2026-10-10)

## 2026-10-03: "Open in its instrument" is a uniform icon in the media action bar

**Entschieden:** The "Open in its instrument" action is an icon in `MediaActionBar`, the same on every surface. It is no longer a text button in the corner of the enlarged view.

**Begründung:** The text button was not seen.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`, `public/ai4artsed-frontend/src/components/MediaActionBar.vue`

## 2026-09-27: "Feature Probing" is renamed "Dimension Explorer"

**Entschieden:** The instrument "Feature Probing" is called "Dimension Explorer".

**Begründung:** Probing in Belinkov (2022) means a trained classifier, and nothing is trained on this instrument.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/i18n/en.ts`

## 2026-09-27: A probing example pair holds two clearly separated vectors

**Entschieden:** An example pair on the Dimension Explorer holds two clearly separated vectors. In Concept Algebra B differs from A; B is the held scene without the variable element.

**Begründung:** With B equal to A the reference collapses and the result is trivially C.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/i18n/en.ts`

## 2026-09-24: Replacing a place code requires the leader's confirmation

**Entschieden:** The course editor asks for confirmation before it replaces a place code.

**Begründung:** Replacing a code signs out the device that entered with the old one.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/educator/CourseEditor.vue`

## 2026-09-24: Story and purpose texts name the process impersonally

**Entschieden:** Story and purpose texts of the instruments name the process without addressing the reader. Attention imperatives stay, and supplied sentences keep their address.

**Begründung:** The direct address is the exception on the platform; the form of the copy is set in `docs/COPY_RULES.md`.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/i18n/en.ts`, `public/ai4artsed-frontend/src/i18n/de.ts`, `docs/COPY_RULES.md`

## 2026-09-22: The mean-images latent preview is drawn at the kids and youth levels too

**Entschieden:** At the two checking safety levels the latent preview of Mean Images is drawn from runs whose decoded picture has cleared delivery. It is no longer withheld at those levels.

**Begründung:** The drawn latent is a 128x128 picture of the tensor and shows nothing a check lacks in the decoded picture; withholding it cost the instrument its build-up at the levels workshops run at.

**Betroffene Dateien:** `devserver/my_app/routes/mean_images_routes.py`, `devserver/tests/test_mean_images.py`

## 2026-09-22: A blind reasoning model keeps the turn and looks at a picture through a delegate

**Entschieden:** When a chat model cannot see an uploaded image, it receives a short caption and the `look_at_image` tool and looks through a delegate on its own provider. It is not handed a finished description under a disclaimer that it did not see the picture.

**Begründung:** The provider serves no single model that both sees and reasons, and the DSGVO record sits on the preset. A model told it did not see the image answers as a stranger to it, although the platform can look as often as asked.

**Betroffene Dateien:** `devserver/my_app/routes/chat_routes.py`, `devserver/tests/test_look_at_image.py`

## 2026-09-22: A laid LoRA tile starts at 80 % of the trained strength

**Entschieden:** A LoRA tile laid on the Flow board starts at 80 % of its trained strength. Perspectives that bring an adapter keep the strength of their config.

**Begründung:** At 100 % a style adapter pulls the picture to its training material; the usual practice in ComfyUI is 0.7 to 0.8.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/x2x_flow.vue`

## 2026-09-22: Clearing the canvas keeps the last result in the output station

**Entschieden:** Clearing the Flow board removes material, perspectives, LoRA tiles and the last transformation. The output station keeps its last result.

**Begründung:** The result is the product of the work; clearing removes only the material.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/x2x_flow.vue`, `public/ai4artsed-frontend/src/i18n/en.ts`, `public/ai4artsed-frontend/src/i18n/fr.ts`, `public/ai4artsed-frontend/src/i18n/ko.ts`

## 2026-09-22: The Prompt Interception note box carries the research paragraph alone

**Entschieden:** The note box of the Prompt Interception surface carries the research paragraph alone. The opening paragraph on what the surface holds equal is struck.

**Begründung:** Its four sentences were refuted or said what every run does.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/i18n/en.ts`

## 2026-09-22: The LoRA picker is a bubble ring like the perspective ring

**Entschieden:** The LoRA picker is a bubble ring of the same kind as the perspective ring. It is no `OverlayFrame`.

**Begründung:** A LoRA is a kind of preset.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-09-21: Unchanged objects in the ring do not re-run the chain

**Entschieden:** A press with unchanged objects in the ring reuses the last written prompt with a new seed. A model picked since the last run re-asks only the adaption.

**Begründung:** The interception has nothing to do with the model.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/x2x_flow.vue`

## 2026-09-21: A LoRA in the zone switches the automatic to the model that carries it

**Entschieden:** A LoRA in the zone switches the automatic model choice to the model that carries the adapter. A hand-picked model holds, and an adapter that model cannot load wears a "?".

**Begründung:** A hand pick is deliberate.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/x2x_flow.vue`

## 2026-09-21: One click opens a medium at full size together with its back, on every surface

**Entschieden:** One click opens the enlarged view with the medium and its back (the record) together, on every surface. The 550 ms hold for the back is gone.

**Begründung:** The first click already zooms, so a second one could never reach the object. The x2x flow had shown the back only after a 550 ms hold in its own layer, and twelve pages each had a layer of their own.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/x2x_flow.vue`, `public/ai4artsed-frontend/src/components/MediaGridCell.vue`, `public/ai4artsed-frontend/src/components/MediaFullscreen.vue`, `public/ai4artsed-frontend/src/components/MediaCardBack.vue`, `public/ai4artsed-frontend/src/components/mediaBack.ts`, `public/ai4artsed-frontend/src/components/canvas/drawerBack.ts`, `public/ai4artsed-frontend/src/components/canvas/OutputDrawer.vue`

## 2026-09-21: SD 3.5 Large Turbo stays in the language comparison's model list

**Entschieden:** SD 3.5 Large Turbo stays in the model list of the language comparison, although it stands in no other raster.

**Begründung:** It reads the prompt through the same three encoders as SD 3.5 Large and still makes different pictures.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/compare/language_comparison.vue`

## 2026-09-21: The Denoising Archaeology slider axis is labelled "Denoising steps"

**Entschieden:** The slider axis of Denoising Archaeology is labelled "Denoising steps", in naming form.

**Begründung:** It is what the numbers count, and it is the slider's accessible name.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/i18n/en.ts`, `public/ai4artsed-frontend/src/i18n/de.ts`

## 2026-09-19: Piper voices are chosen by Language, Voice and Speaker

**Entschieden:** Piper voices are chosen by Language, Voice and Speaker. Every language is a chip, the interface language is preselected, and all 236 speakers of the German corpus are reachable.

**Begründung:** The choice follows the layout of Piper's own sample page, and the products that embed Piper choose the same way.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/i18n/en.ts`, `docs/ARCHITECTURE PART 33 - Compare Hub.md`

## 2026-09-19: Under the Piper choice only "who was recorded" remains

**Entschieden:** Under the Piper voice choice only the line on who was recorded remains. File name and quality go to hover cards, speaker information goes to the note box, and no per-file explanatory line stands under the choice.

**Begründung:** The stack was too long for the column, and the removed items say nothing about what can be asked of the machine.

**Betroffene Dateien:** `devserver/my_app/services/piper_backend.py`, `docs/ARCHITECTURE PART 33 - Compare Hub.md`

## 2026-09-19: The Clear button in Voices is removed; every run is kept

**Entschieden:** The Voices surface has no Clear button. Every run is kept.

**Begründung:** The other instruments keep every run, and one wrong click would discard lesson data.

**Betroffene Dateien:** `docs/ARCHITECTURE PART 33 - Compare Hub.md`

## 2026-09-18: Piper is the second machine of the voices comparison, beside eSpeak NG

**Entschieden:** Piper is the fourth speech system of the platform and stands in the voices comparison as the second machine, in the third of five columns beside eSpeak NG. eSpeak NG stays the historical reference.

**Begründung:** Piper (2022, over VITS) descends from the method of eSpeak NG, so it cannot stand as the historical reference; its earlier placement in the first column was wrong. The order of the columns follows what can be set, more than eSpeak NG's numbers and less than Supertonic's mixtures, and it is also the order of the years.

**Betroffene Dateien:** `devserver/my_app/routes/speech_routes.py`, `devserver/my_app/services/piper_backend.py`, `devserver/config.py`, `public/ai4artsed-frontend/src/views/compare/voice_comparison.vue`

## 2026-09-18: Any installed Piper voice can be named for any sentence

**Entschieden:** Any installed Piper voice can be named for any sentence in any language. A foreign voice is spoken.

**Begründung:** Foreign voices are to be explorable.

**Betroffene Dateien:** `devserver/my_app/services/piper_backend.py`

## 2026-09-18: SUPERTONIC_FLOW_STEPS is 4

**Entschieden:** `SUPERTONIC_FLOW_STEPS` is 4.

**Begründung:** Four is the lowest count that still sounds acceptable, at roughly half the time of eight.

**Betroffene Dateien:** `devserver/config.py`

## 2026-09-17: The mixed row of the text presets holds three sizes of current models

**Entschieden:** The mixed row holds three sizes of current models (3-4B, 7-9B, 12-14B) and no outdated ones.

**Begründung:** The row compares families of similar size.

**Betroffene Dateien:** `devserver/config/text_presets.json`

## 2026-09-16: The T5 block layout and the pooled vector of the Surrealizer are settings; the page opens on Standard

**Entschieden:** The T5 block layout (full/tail) and the pooled vector (clip/zero) are settings of the Surrealizer. The page opens on Standard (a 1, b 0, c 1, full, clip).

**Begründung:** The full block pulls the picture toward Standard, and old pictures need the old layout.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/surrealizer.vue`

## 2026-09-12: API keys have one place, and the ComfyUI nodes send their LLM calls through the DevServer proxy

**Entschieden:** API keys live in the platform's key files and provider table alone; the forked ComfyUI node package carries no key file of its own. The ComfyUI nodes send their LLM calls to the DevServer endpoint `/api/chat/proxy` and never post to a provider or to Ollama themselves.

**Begründung:** A second key file in the package is a second place for keys that drifts from the platform's table; the package had carried its own `openrouter.key` with a second key and address the DevServer knew nothing of. The keys, the provider table and the settings-regulated fallback chain stay in one place.

**Betroffene Dateien:** `comfyui_nodes/ai4artsed_comfyui/_platform_credentials.py`, `devserver/my_app/routes/chat_routes.py`, `devserver/tests/test_own_comfyui_nodes.py`, `devserver/tests/test_chat_proxy.py`

## 2026-09-12: Encoder Fusion offers two prompt strategies

**Entschieden:** Encoder Fusion offers two prompt strategies: `two_interceptions` ("Adapted prompts") and `original` (the 2025 workflow). The two residual strategies are removed.

**Begründung:** Against "Same prompt" the switch must change the prompts and nothing else; `original` is kept for the research that cites it.

**Betroffene Dateien:** `devserver/my_app/routes/schema_pipeline_routes.py`

## 2026-09-12: The Surrealizer omits slerp

**Entschieden:** The Surrealizer chunk offers the fusion node's strategies without slerp, and no surface sends the slerp/sphere path for `centered_fade`.

**Begründung:** The great circle joins embeddings of two different prompts and has no object between the two readings of one prompt.

**Betroffene Dateien:** `gpu_service/services/diffusers_backend.py`, `devserver/schemas/chunks/output_image_surrealizer_comfyui.py`, `devserver/tests/test_sd3_conditioning_nodes.py`

## 2026-09-12: The Surrealizer's prompt adaptation runs once per prompt for the life of the process

**Entschieden:** The prompt adaptation of the Surrealizer runs once per prompt and is held for the life of the process.

**Begründung:** The interceptions at temperature 0.7 answer differently every time, so a series over alpha would otherwise compare prompts as much as alphas.

**Betroffene Dateien:** `devserver/my_app/services/surrealizer_original.py`

## 2026-09-10: No settable law over the T5 tail

**Entschieden:** The T5 tail runs at its own length, and `dual_alpha` keeps its 0.15. There is no settable law over the tail.

**Begründung:** Variables no hypothesis can be formed about have no business in the model.

**Betroffene Dateien:** `gpu_service/services/diffusers_backend.py`

## 2026-09-10: Items on the Resona board survive reload and leaving; running generations and apparatus do not

**Entschieden:** Items on the Resona board survive a reload and leaving the page. Running generations and apparatus are not restored.

**Begründung:** A card that came back saying "running" would say it forever.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/resona.vue`

## 2026-09-10: A library passage may lie on the canvas; an external page carries its link and none of its body

**Entschieden:** A passage from the library may lie on the Resona canvas. An external page carries its link and none of its body.

**Begründung:** The library holds processed knowledge and never the original text.

**Betroffene Dateien:** `devserver/tests/test_resona_entities.py`

## 2026-09-09: The Latent Lab shows per device which model is running, carried on the run's own heartbeat

**Entschieden:** The Latent Lab bar shows one line naming the model at work and its provider, fed by the dispatch frame on the run's own SSE heartbeat, and nothing when nothing runs. There is no separate register or route for it.

**Begründung:** The DevServer knows what it sends, and the heartbeat of that request carries the name back; a per-instrument declaration could drift, and a line keeping the last run standing would state a prediction.

**Betroffene Dateien:** `devserver/tests/test_model_place_frame.py`, `public/ai4artsed-frontend/src/views/latent_lab.vue`, `public/ai4artsed-frontend/src/composables/useRunPlace.ts`

## 2026-09-09: Entities a Resona room works out get a card on the canvas

**Entschieden:** Entities a Resona room works out get a card on the canvas, if need be only as memory anchors.

**Begründung:** What a room worked out is represented on the board, as the produced media are.

**Betroffene Dateien:** `devserver/tests/test_resona_entities.py`

## 2026-09-09: An output box has no font size of its own

**Entschieden:** An output box has no font size of its own; model text uses `--flow-fs-body`.

**Begründung:** 0.8rem stood separately in every Compare file and was too small on the iPad.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-09-09: The fold-away block on the Encoder Fusion sweep is labelled "Advanced settings"

**Entschieden:** The fold-away block on the Encoder Fusion sweep carries the platform-wide label "Advanced settings".

**Begründung:** One word for the same block on every surface.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/i18n/en.ts`

## 2026-09-09: Which models the model comparison offers is a didactic decision

**Entschieden:** Which models the comparison offers is a didactic decision and no catalogue. CommonCanvas XL C is offered after SDXL although it stands in no set.

**Begründung:** CommonCanvas XL C is trained on about 70 M CC-licensed images only.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/compare/model_comparison.vue`

## 2026-09-08: The Commons row asks for 40 search results instead of 3

**Entschieden:** The Commons row requests 40 search results and draws from them.

**Begründung:** With the head of a relevance ranking taken in order, the row showed the same three pictures on every run.

**Betroffene Dateien:** `devserver/my_app/services/commons_service.py`

## 2026-09-08: Death and dead animals are excluded from the Commons row by negated query terms

**Entschieden:** Death and dead animals are excluded from the Commons row by negated query terms in the search. The safety screen afterwards does not have to judge them.

**Begründung:** Commons documents file content, so the search can decline to ask, and nothing downstream has to judge a picture it was handed.

**Betroffene Dateien:** `devserver/my_app/services/commons_service.py`

## 2026-09-08: Randomness is a slider axis from 0 to 2

**Entschieden:** On the System Prompts comparison randomness is a slider from 0 to 2 (deterministic 0, balanced 0.5, unpredictable 1), with the value in the label.

**Begründung:** The range where output visibly falls apart must be settable, and a thumb between marks says no number.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/compare/system_prompt_comparison.vue`, `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-09-08: Surfaces begin with the prompt; model and randomness follow

**Entschieden:** A surface begins with the prompt. Model and randomness follow.

**Begründung:** That is the platform's order of preparation.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-09-07: Every apparatus Resona authors is written to disk in Canvas-importable form

**Entschieden:** Every apparatus Resona builds is written to disk at the tool handler as a CanvasWorkflow file, rejected ones under `rejected/`.

**Begründung:** A run missing from the board can then be told apart from a run that was never built, and a run that fails to appear can be traced to the UI or to the backend.

**Betroffene Dateien:** `devserver/my_app/services/canvas_graph_export.py`, `devserver/tests/test_canvas_graph_export.py`

## 2026-09-07: The model comparison opens with the historical set

**Entschieden:** The model comparison opens with the historical set.

**Begründung:** Three years of one family, all local weights, no cost on the first press.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/compare/model_comparison.vue`

## 2026-09-06: The repetition guard stops at the third identical finished segment

**Entschieden:** The repetition guard stops a run at the third identical finished segment. The limit was six.

**Begründung:** A run repeated its whole paragraph five times and passed under the old limit.

**Betroffene Dateien:** `gpu_service/services/repetition_guard.py`

## 2026-09-06: LoraTryout is removed

**Entschieden:** The LoraTryout structure is removed.

**Begründung:** LoRA Explorer covers the same comparison and alone has the trigger without which the two images compare nothing.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-09-06: A chosen perspective disc shows its interception text on hover

**Entschieden:** A chosen perspective disc shows its interception text on hover (long press on touch) and no longer on click.

**Begründung:** Until then no surface showed the full prompt.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-09-06: Only one paragraph of the agent's turn stands

**Entschieden:** Resona's voice shows only one paragraph of the active turn. The previous paragraph is removed, never scrolled or folded, and nothing accumulates or is re-readable.

**Begründung:** One listens and is present; the machine is not to be used as a text archive.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`, `public/ai4artsed-frontend/src/components/ResonaVoice.vue`

## 2026-09-06: The free-prompt hint stands over every free prompt field of the Latent Lab and never over an operand

**Entschieden:** The free-prompt hint stands over every free prompt field of the Latent Lab. It never stands over an operand.

**Begründung:** Operands are functional prompts whose wording is prescribed.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/i18n/en.ts`

## 2026-09-05: The dimension-lines instrument draws nothing; every property with a symmetric scale carries a handle

**Entschieden:** The dimension-lines instrument draws nothing. Every property whose scale prints alike at both poles carries a handle, and the surface says so when none does.

**Begründung:** The pool is the presets' data, so an edit to the scales cannot quietly empty the checklist.

**Betroffene Dateien:** `devserver/tests/test_dimension_lines.py`

## 2026-09-05: "Best" and "worst" set exactly the index of the preset's own option

**Entschieden:** The swing is dropped for the five levels. "Best" and "worst" set exactly the index of the preset's own option.

**Begründung:** Surface and preset must put the same requirement to the model under one name.

**Betroffene Dateien:** `devserver/tests/test_dimension_lines.py`

## 2026-09-05: The first row of the Prompt Interception rasters is labelled "Reference image"

**Entschieden:** The first row of all three Prompt Interception rasters is labelled "Reference image" platform-wide. With a picture on the surface the label moves to the picture, and the typed-template row carries "Without perspective".

**Begründung:** The reference is the typed template, or the picture where one stands.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/i18n/en.ts`

## 2026-09-05: A picture opens on SD 3.5 Large on every surface

**Entschieden:** A picture opens on SD 3.5 Large on every surface, read from the platform's single image default.

**Begründung:** The list's first entry (CommonCanvas) was nobody's choice.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/x2x_flow.vue`

## 2026-09-05: A filling cell shows the undecoded mean of the latents already present

**Entschieden:** A Mean Images cell that is still filling shows the undecoded mean of the latents already present.

**Begründung:** It costs no GPU and no wait.

**Betroffene Dateien:** `devserver/my_app/services/mean_images.py`

## 2026-09-04: Mean Images averages final latents before the VAE decoder

**Entschieden:** Mean Images averages the final latents before the VAE decoder. Finished PNGs are not averaged.

**Begründung:** Measured on 20 pictures, the latent mean keeps a single picture's local sharpness, and the PNG mean keeps less than half of it.

**Betroffene Dateien:** `gpu_service/services/diffusers_backend.py`

## 2026-09-04: The Mean Images set size is a slider axis

**Entschieden:** The set size of Mean Images is an axis ("Images per cell" slider), any count from two to the route's ceiling of 50, with the value in the label. It replaces three fixed layouts.

**Begründung:** Three fixed offers were too coarse.

**Betroffene Dateien:** `devserver/my_app/services/mean_images.py`, `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-09-04: Every input box accepts an image dropped on it

**Entschieden:** Every input box accepts an image dropped on it, with no visible drop zone, label or opt-in property.

**Begründung:** A text field runs the same upload and safety-check steps as an image field.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-09-04: Interception across Models shows three line-ups instead of sixteen model fields

**Entschieden:** Interception across Models shows three line-ups. The sixteen model fields are gone.

**Begründung:** Sixteen fields are a catalogue, and a catalogue asks nothing.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-09-03: T5 reads the CLIP prompt followed by the interception result; shortening happens only against a declared window

**Entschieden:** The adaption writes the CLIP prompt. T5 reads the CLIP prompt followed by the interception result. Only when both together exceed the model's declared window is the interception result shortened to the window minus the CLIP prompt's cost; a model without a declared window is left alone.

**Begründung:** Shortening on a guess takes words away for nothing; the window is measured on ComfyUI with the encoder's own tokenizer.

**Betroffene Dateien:** `devserver/my_app/routes/schema_pipeline_routes.py`

## 2026-09-03: The run no longer stops mid-adaption for approval

**Entschieden:** The run no longer stops before stage 3b for approval of the adaption. The adaption's text is put on the table, editable, and a shortening is told in the run band without asking.

**Begründung:** Editing on the table is easier than a halt that must be answered before the run may go on.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/x2x_flow.vue`

## 2026-09-02: A saved perspective's title is unique, and the perspective shows a palette colour

**Entschieden:** A saved perspective's title must not repeat an existing preset or own-perspective name. A saved perspective shows a palette colour and never the preset's picture.

**Begründung:** A fork keeping the preset's name and picture stood beside its source preset in the chooser with nothing to tell the two apart.

**Betroffene Dateien:** `devserver/my_app/routes/interception_prompts_routes.py`, `public/ai4artsed-frontend/src/views/x2x_flow.vue`

## 2026-09-02: The aesthetic presets run on the configured interception model and name the medium in one word

**Entschieden:** The presets aesthetic and anti_aesthetic run on the configured interception model and no longer on the local qwen3-vl:32b. The preset names the medium in one word ("Photograph.") and adds nothing else to the study's own procedure. Both presets sit under Photography & Media.

**Begründung:** Over seven measured runs the local VLM kept the platform's length requirement in none. The VisionReward properties are calibrated on photographs; "as a picture" produced blurred paintings, and a causal-account paragraph cost a test series its result. The presets are medium-specific: they describe image properties and run on image alone.

**Betroffene Dateien:** `devserver/schemas/configs/interception/anti_aesthetic.json`

## 2026-09-02: Within each category the instruments follow the order of an inference run

**Entschieden:** Within each category of the Latent Lab the instruments follow the order of an inference run.

**Begründung:** That order replaces an arbitrary list.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/latent_lab.vue`

## 2026-09-01: A draft that fails its evidence duty stays on the surface struck through

**Entschieden:** A draft that fails its evidence duty stays on the surface struck through, and the checked version follows it.

**Begründung:** The platform does not hide the moment a model corrects itself against sources.

**Betroffene Dateien:** `devserver/my_app/routes/chat_routes.py`

## 2026-09-01: Material in the ring the route cannot hand to the model is read into words

**Entschieden:** Material in the ring that the route cannot hand to the model is read into words and put in front of the prompt. It is never dropped.

**Begründung:** Nothing lying in the ring falls away silently.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/x2x_flow.vue`

## 2026-09-01: LLM answers are streamed to the room token by token

**Entschieden:** LLM answers are streamed to the room token by token.

**Begründung:** Children must not wait for complete text blocks they could already read.

**Betroffene Dateien:** `devserver/my_app/services/openai_style_stream.py`

## 2026-09-01: The Emotion dimension is unsuitable for kids and youth

**Entschieden:** The Emotion dimension of the aesthetic presets is unsuitable for kids and youth. This is not enforced; the chip stands at every level.

**Begründung:** At the negative pole the source scale asks for a very negative emotional response.

**Betroffene Dateien:** `devserver/schemas/configs/interception/anti_aesthetic.json`

## 2026-08-29: Only the owning device may change a favourite

**Entschieden:** DELETE and PATCH on a favourite check the entry's `device_id`. Only the owning device may change it, and an entry without an owner may be changed by anyone.

**Begründung:** Matching on `run_id` alone let any device remove another's favourite; refusing unowned entries would strand them in the strip.

**Betroffene Dateien:** `devserver/my_app/routes/favorites_routes.py`

## 2026-08-28: Every generating run halts at its adapted prompt

**Entschieden:** Every generating run halts at its adapted prompt, which must be sighted and confirmed before the model runs. This halt was removed again (see the entry of 2026-09-03).

**Begründung:** The interception must not be something that happens to somebody; the adapted prompt is the last state in which the words can still be answered.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/x2x_flow.vue`

## 2026-08-28: No second eject function

**Entschieden:** There is no second eject function. The eject mechanism of generated media is the template for every intermediate step.

**Begründung:** A separate function for an intermediate step was a parallel structure.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-08-28: The queue position lives in PolicyChips in the header

**Entschieden:** The queue position lives in `PolicyChips` in the header, once for the platform. The lab bar does not show it.

**Begründung:** A "queue full" message had been shown while one training held the card for 6.5 h, and the header is on all generating surfaces.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-08-27: Long VoxCPM2 text is cut into sense units

**Entschieden:** Long VoxCPM2 text is cut into sense units as large as the pace allows (150 tokens target, 220 ceiling), each anchored on the previous segment. It is no longer cut one sentence at a time.

**Begründung:** The model speeds up the longer a single pass runs, and the makers prescribe splitting and joining waveforms for long-form text.

**Betroffene Dateien:** `voxcpm_service/server.py`, `docs/ARCHITECTURE PART 33 - Compare Hub.md`

## 2026-08-26: Representation Engineering is the one exception to the ban on hard output limits

**Entschieden:** The Representation Engineering instrument runs under a hard length limit: the run closes at the first sentence end after 160 tokens and stops hard at 256. It is the only place on the platform with such a limit.

**Begründung:** Per Zou et al. 2023 the unit of analysis is the representational space; the text is only the readout, and its length carries none of the finding. A raw completion gives an instruct model no end token, and a run went to the 65,536-token ceiling.

**Betroffene Dateien:** `gpu_service/services/text_backend.py`, `comfyui_nodes/ai4artsed_comfyui/_text_probes.py`, `docs/ARCHITECTURE PART 28 - Latent-Lab.md`

## 2026-08-26: Only the description actually sent to VoxCPM2 travels back as the label

**Entschieden:** Only the description actually sent to VoxCPM2 travels back as the label; the Compare surface sends "neutral voice" for unlit rows.

**Begründung:** A label must name what the model received.

**Betroffene Dateien:** `devserver/my_app/services/voxcpm_backend.py`

## 2026-08-26: VoxCPM2's speaker is described through three choosers only

**Entschieden:** VoxCPM2's speaker is described through three choosers only. The free description field is gone.

**Begründung:** The model does not react to freely written descriptions; a field that changes nothing teaches the wrong thing.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/compare/voice_comparison.vue`

## 2026-08-26: Each machine column of the voices comparison carries a colour of its own

**Entschieden:** Each machine column carries a colour of its own from the canvas palette, green and amber excluded.

**Begründung:** Green and amber mean chosen and other inside the chips.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/compare/voice_comparison.vue`

## 2026-08-26: The note box states facts, research questions and findings; references are mandatory on the instrument

**Entschieden:** The note box of an instrument states facts, research questions and findings with their source. Operation text goes to Help. References stand flat inside the note, title with DOI, and must be visible; the help entry's copy never replaces them.

**Begründung:** The earlier rule had cost four instruments their research references, and the note only refers in prose.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`, `public/ai4artsed-frontend/src/components/LabReferences.vue`, `public/ai4artsed-frontend/src/views/latent_lab/default_census.vue`

## 2026-08-26: The four comparing surfaces are named by who does the understanding

**Entschieden:** The four comparing surfaces are named by who does the understanding: KI-Modell-Vergleich, KI-Sprachverständnis, KI-Bildverständnis, KI-Kulturverständnis.

**Begründung:** That is their subject.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/latent_lab.vue`

## 2026-08-25: The per-comparison chat agent column is removed; Help answers on comparison pages from page context

**Entschieden:** The per-comparison chat agent column and its five system prompts are removed. Help answers on comparison pages from page context, and the Help sign on comparison surfaces is "Interpretation help" and carries no question.

**Begründung:** One voice on every page; the surface's output reaches it through `pageContext`. Taking the sign opens the conversation, and nothing is written into it.

**Betroffene Dateien:** `devserver/my_app/routes/chat_routes.py`, `public/ai4artsed-frontend/src/i18n/en.ts`

## 2026-08-25: Run images are served to the favourites strip as cached small JPEGs

**Entschieden:** Run images are served to the favourites strip as cached small JPEGs. Where no miniature can be made, the full picture is served with the header `X-Thumbnail: full`.

**Begründung:** Full renders are megabytes each; a slow strip says more than a strip full of holes, and the header keeps the failure visible.

**Betroffene Dateien:** `devserver/my_app/routes/media_routes.py`

## 2026-08-25: Gemini 3 Pro may stand preselected only on the model comparison

**Entschieden:** Gemini 3 Pro is never preselected on a surface where a press multiplies calls. The model comparison is the only place where it may stand preselected; everywhere else it is chosen by hand.

**Begründung:** On the model comparison it is one picture per model; on a multiplying surface every column is one more paid call.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/compare/model_comparison.vue`, `public/ai4artsed-frontend/src/views/latent_lab/default_census.vue`

## 2026-08-25: The colour strip at .bias-pair is removed

**Entschieden:** The colour strip at `.bias-pair` is removed. A second display of the same measurement is allowed only with a didactic justification.

**Begründung:** The fan of differences shows the angle itself; the strip only binned it into three steps.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-08-25: What is written into the field is called PROMPT

**Entschieden:** What is written into the field is called PROMPT in the German copy, never "Satz".

**Begründung:** The surface itself says „Beispiel-Prompt wählen" above the field.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/i18n/de.ts`

## 2026-08-24: Representation Engineering has no interpretation agent of its own

**Entschieden:** The Representation Engineering surface has no interpretation agent. Help answers about its runs from `pageContext` when asked.

**Begründung:** Help has the authority for explanation and must see the outputs; a second agent would speak unasked about every run.

**Betroffene Dateien:** `devserver/my_app/routes/chat_routes.py`, `public/ai4artsed-frontend/src/views/latent_lab/representation_engineering.vue`

## 2026-08-24: MediaGridCell is the binding template for generated media in grids and rows

**Entschieden:** `MediaGridCell` is the binding template for generated media in grids and rows. Its back carries all functions the flow box has.

**Begründung:** One cell template replaces per-surface tiles.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-08-23: Encoder Fusion offers two fusions, Centered Fade and the original 2025 surrealizer

**Entschieden:** Encoder Fusion offers two fusions: Centered Fade and the original 2025 ComfyUI surrealizer, restored exactly.

**Begründung:** The second entry is another version of the same instrument and no run parameter.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-08-23: The legacy fusion axis carries both readings at 1 in the middle of the band

**Entschieden:** The legacy fusion axis carries `centered_fade`'s band in its middle, with both readings at 1 instead of 0.5/0.5.

**Begründung:** Two halves condition more weakly than either reading alone and do not add up to full guidance strength.

**Betroffene Dateien:** `gpu_service/services/diffusers_backend.py`

## 2026-08-23: The Guidance and Temperature surface is removed; Cultural (Un)Known moves to Compare

**Entschieden:** The "Guidance and Temperature" comparison surface is removed, and Cultural (Un)Known moves from the Image Lab to Compare. The surface's label key is left standing, and its address falls through to the lab without a redirect.

**Begründung:** The surface failed. The key is a name in ten languages and its deletion is a separate decision; a redirect onto a gone surface is worse than none.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/compare_hub.vue`, `public/ai4artsed-frontend/src/router/index.ts`, `public/ai4artsed-frontend/src/i18n/en.ts`, `docs/ARCHITECTURE PART 28 - Latent-Lab.md`

## 2026-08-23: Four prohibitions for station text

**Entschieden:** Station text on the overview map obeys four prohibitions: no metaphor or anthropomorphism, no dash replacing a statement, no unintroduced names, nothing the reader already knows. Latent space, embedding space and conditioning stay as technical terms.

**Begründung:** The whole text stock of the map had been rejected.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-08-22: Nothing is filtered out of the BBQ benchmark itself; an age screen holds back situations

**Entschieden:** Nothing is filtered out of the BBQ benchmark itself. An age screen at the kids level holds back heavy-theme situations, and six specific situations are held back from kids and youth.

**Begründung:** Unprotected-sex and heavy-theme situations surfaced in a kids draw; the six remaining items each put a person of the class in the room in the place the question asks about.

**Betroffene Dateien:** `gpu_service/services/bbq_corpus.py`

## 2026-08-22: WinoBias item type2-tes-151 is excluded from the pool

**Entschieden:** The WinoBias item type2-tes-151 is excluded from the pool.

**Begründung:** English "her" is both object and possessive, so the pair differs in more than the pronoun.

**Betroffene Dateien:** `gpu_service/services/winobias_corpus.py`

## 2026-08-22: The single-case highlight is an opacity pulse on one shared oscillator

**Entschieden:** The single-case highlight is an opacity pulse from 1 to 0.3 over 2.2 s on one shared oscillator. The whole bar beats as the indicator of one machine's answer to one question, from one shared LFO on the chart.

**Begründung:** Luminance change is what the eye catches at 20 px; brightness clips the hues, and per-bar animations fall out of phase.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`, `public/ai4artsed-frontend/src/assets/flow-stage.css`

## 2026-08-22: Qwen/Qwen-7B is pinned to a fixed revision

**Entschieden:** Qwen/Qwen-7B (gen1) is pinned to a fixed revision.

**Begründung:** Loading it executes repository code (`trust_remote_code`); a later upstream commit must not reach the machine without a code change.

**Betroffene Dateien:** `gpu_service/config.py`

## 2026-08-21: A written prompt field under a band carries PromptExamples above it and a perspective inside

**Entschieden:** An instrument surface that takes a written prompt carries the Model-Bias input combination as a mandatory template: ready-made prompts (`PromptExamples`) above the field and a perspective in it. The policy test and the pre-commit gate enforce it.

**Begründung:** An element structure exists once; the combination is the registry's canonical input form, and the duplication had recurred.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`, `devserver/tests/test_element_structure_policy.py`, `public/ai4artsed-frontend/src/components/PromptExamples.vue`

## 2026-08-21: The run trigger of a lab surface sits in the shell bar centre

**Entschieden:** The run trigger of a lab surface sits in the centre of the shell bar. The standing band is dropped in the lab.

**Begründung:** The bar centre was empty while a band cost 156 px of the short side on 16:9.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-08-20: Control labels are the technical term plus a bracket saying what the control does

**Entschieden:** A control label is the technical term followed by a bracket that says what the control does.

**Begründung:** The term stays, and the bracket explains.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-08-19: No step thumbnails in Denoising Archaeology

**Entschieden:** Denoising Archaeology shows one large image and the axis, and no step thumbnails.

**Begründung:** Thumbnails take away the experience of imagining the next denoising step.

**Betroffene Dateien:** `docs/ELEMENT_STRUCTURE_REGISTRY.md`

## 2026-08-18: GPU_ADMISSION_MAX_WAITERS is a thread-pool safety limit

**Entschieden:** `GPU_ADMISSION_MAX_WAITERS` is a thread-pool safety limit set high enough that an ordinary course never meets it. It is no group-size policy.

**Begründung:** Turning somebody away costs them their place in the line.

**Betroffene Dateien:** `gpu_service/config.py`

## 2026-08-17: GIVEN_PICTURE_CLAUSE prescribes nothing, and the interception is told whether a picture goes to the image model

**Entschieden:** `GIVEN_PICTURE_CLAUSE` restrains and prescribes nothing; it never spells out what the picture is to show. The interception is told whether a picture goes to the image model, which decides whether it may write a scene of its own.

**Begründung:** Spelling the outcome out turns a child's drawing into a postcard; the image editor had replaced a drawn boat with an invented beach scene, and without the information an instruction on a drawing came back as an invented scene that the editor rendered.

**Betroffene Dateien:** `devserver/schemas/engine/instruction_selector.py`, `public/ai4artsed-frontend/src/views/x2x_flow.vue`

## 2026-08-17: Verbatim passthrough applies at every safety level

**Entschieden:** When no perspective is chosen, the user's wording goes to the media model as written, at every safety level, kids and youth included. On the Canvas an interception node without a perspective hands its input on without asking a language model, and the age check runs at generation.

**Begründung:** Stage 2 is no safety instrument; the age check runs in Stage 1 and Stage 3, and a mandatory Stage 2 for minors rewrote precisely their prompts.

**Betroffene Dateien:** `devserver/schemas/engine/config_loader.py`, `devserver/my_app/services/canvas_executor.py`, `devserver/tests/test_canvas_interception_passthrough.py`

## 2026-08-17: No ComfyUI node answers a failed LLM call with another model

**Entschieden:** No ComfyUI node answers a failed LLM call with another model. The platform has no hardcoded model fallback.

**Begründung:** A model id is data; fallback is regulated by the settings page and by no code.

**Betroffene Dateien:** `devserver/tests/test_own_comfyui_nodes.py`

## 2026-08-16: Conformity status of cloud services is read from the one register

**Entschieden:** The conformity status of cloud services is read from `hardware_matrix.json`. The hand-kept conformity list and the region column in the settings route are removed.

**Begründung:** Bedrock is conform only if the AWS account is restricted to European regions, which the platform cannot see; a region stood in no register.

**Betroffene Dateien:** `devserver/my_app/routes/settings_routes.py`

## 2026-08-15: Under passthrough the Stage-2 step still runs

**Entschieden:** Under passthrough the Stage-2 step still runs. The user's wording stands unless the model had to look something up, in which case the researched text is the answer.

**Begründung:** Clearing the chunks also skipped the Wikipedia research, so a factual prompt went to the image model as an unanswered question.

**Betroffene Dateien:** `devserver/schemas/engine/config_loader.py`

## 2026-08-13: The classifier's query wording is copied letter for letter from the comparison script

**Entschieden:** The safety classifier's query wording is copied letter for letter from `devserver/testfiles/ab_shieldstral.py`.

**Begründung:** What runs must be what was compared.

**Betroffene Dateien:** `devserver/my_app/services/safety_classifier.py`, `devserver/testfiles/ab_shieldstral.py`

## 2026-08-12: STABLE_AUDIO_MAX_DURATION is 240 s

**Entschieden:** `STABLE_AUDIO_MAX_DURATION` is 240 s, and the Stable Audio 1.0 limit of 47.6 s is removed. The re-enactment page sizes its audio to the recording, up to 240 s.

**Begründung:** The page promises 10 to 240 s and returns a sound as long as the recording; a lower backend ceiling clamped silently, and the leftover 47.6 s ceiling was cutting recordings down.

**Betroffene Dateien:** `gpu_service/config.py`, `devserver/my_app/services/parrot_service.py`, `docs/ARCHITECTURE PART 38 - Cover-Band.md`

## 2026-08-12: The adaption writes the length of a sound as a DURATION line

**Entschieden:** The x2audio flow's adaption emits a DURATION line, and the Stable Audio chunk takes the length from it instead of the config default. Callers that pass SECONDS are untouched.

**Begründung:** The adaption decides how long a sound has to be; every flow sound was otherwise exactly the config default length, whether a door closing or a piece of music.

**Betroffene Dateien:** `devserver/schemas/chunks/output_audio_stableaudio_diffusers.py`, `devserver/tests/test_stable_audio_duration.py`

## 2026-08-12: stableaudio_sfx and stableaudio_music are split off from stableaudio_open

**Entschieden:** `stableaudio_sfx` and `stableaudio_music` are two configs split off from `stableaudio_open`. They differ only in default length and name.

**Begründung:** The re-enactment chain needs a named routing target.

**Betroffene Dateien:** `devserver/schemas/configs/output/stableaudio_sfx.json`, `devserver/schemas/configs/output/stableaudio_music.json`

## 2026-08-12: Re-enactment routes the output config from what was heard

**Entschieden:** Which machine sings is decided by what the first station hears, through a four-outcome table: music and text go to HeartMuLa (`heartmula_standard`), music alone to Stable Audio 3 Music (`stableaudio_music`), speech alone to VoxCPM2, and neither to Stable Audio 3 SFX (`stableaudio_sfx`). A hand pick beats all four and holds across runs, and none is lit before a run.

**Begründung:** Two yes/no answers determine four outputs; the writing station produces a song every time, so scoring it decides nothing about which machine. The rankings are the measured ones from `devserver/testfiles/probe_parrot_routing.py`, and none lit before a run is the honest state.

**Betroffene Dateien:** `devserver/my_app/services/parrot_service.py`, `devserver/tests/test_parrot_routing.py`, `devserver/testfiles/probe_parrot_routing.py`, `public/ai4artsed-frontend/src/views/cover_band.vue`, `docs/ARCHITECTURE PART 38 - Cover-Band.md`

## 2026-08-12: The re-enactment chain does not start by itself after recording

**Entschieden:** The chain does not start by itself after recording. The trash in the recording box is the only way back.

**Begründung:** A recording that ran straight into four machines could not be listened to, discarded or redone without costing a song.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/cover_band.vue`

## 2026-08-12: Re-enactment result boxes go onto the board by measured fit

**Entschieden:** Result boxes go onto the board by measured height and fit, no box over another. There is no grid and no single column.

**Begründung:** A grid pre-allocates cells, which left empty cells and clipped the long ranking; a single column left half the page empty.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/cover_band.vue`, `docs/ARCHITECTURE PART 38 - Cover-Band.md`

## 2026-08-12: Qwen3-TTS is removed from the speech systems; VoxCPM2 replaces it

**Entschieden:** Qwen3-TTS is removed from the speech systems. VoxCPM2 replaces it and runs in its own environment.

**Begründung:** A transformers upgrade elsewhere in the platform's environment broke Qwen3-TTS.

**Betroffene Dateien:** `devserver/my_app/routes/speech_routes.py`

## 2026-08-12: The datasets thorsten_emotional and thorsten are never offered as Piper voices

**Entschieden:** The datasets `thorsten_emotional` and `thorsten` are never offered as Piper voices. The column offers professional voices only.

**Begründung:** Acted emotions from one reader say nothing about what a synthesiser can do and would be read as Piper's.

**Betroffene Dateien:** `devserver/my_app/services/piper_backend.py`

## 2026-08-11: lookup_place is a read tool over platform_items in both scopes

**Entschieden:** `lookup_place` is a read tool over `platform_items` in both scopes.

**Begründung:** The companion and the help agent otherwise saw the labs' own texts only as page context.

**Betroffene Dateien:** `devserver/my_app/services/tool_registry.py`

## 2026-08-11: lookup_research and read_research are pinned to Tier R in the default scope

**Entschieden:** `lookup_research` and `read_research` are pinned to Tier R in the default scope.

**Begründung:** The help agent must answer research questions from the texts and never from model memory.

**Betroffene Dateien:** `devserver/my_app/services/tool_registry.py`

## 2026-08-11: surrealizer_flow.vue is deprecated but kept

**Entschieden:** `surrealizer_flow.vue` is deprecated but kept. Its node band is to be salvaged as a process display.

**Begründung:** The band is a display of where a run stands and no control surface.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/surrealizer_flow.vue`

## 2026-08-09: Speech synthesis is allowed at every safety level

**Entschieden:** Speech synthesis is allowed at every safety level.

**Begründung:** Synthesis adds no content; it speaks a text that already passed its origin's check.

**Betroffene Dateien:** `devserver/schemas/chunks/output_speech_supertonic.py`

## 2026-08-08: The re-enactment song is as long as the recording, and recordings are capped at 240 s

**Entschieden:** The Silly Parrot song is as long as the recording. Recordings are capped at 240 s, derived from `SONG_MAX_MS`.

**Begründung:** HeartMuLa's `max_audio_length_ms` is literally the song's length; one derived constant stops two constants drifting apart, so the recording cannot run past what can be sung back.

**Betroffene Dateien:** `devserver/my_app/services/parrot_service.py`, `public/ai4artsed-frontend/src/views/cover_band.vue`

## 2026-08-08: The transcription is offered a second time in the platform language

**Entschieden:** The transcription is offered a second time in the platform language, beside the original only. Nothing downstream receives the translated copy.

**Begründung:** A group that cannot read the transcriber's alphabet can see that something was misheard but never what.

**Betroffene Dateien:** `devserver/my_app/services/parrot_service.py`

## 2026-08-07: A course's safety level may only tighten the installation's level

**Entschieden:** A course's safety level may only tighten the installation's level. It can never loosen it.

**Begründung:** An open course inside a kids installation must still run at kids.

**Betroffene Dateien:** `devserver/my_app/services/safety_level_resolver.py`

## 2026-08-06: Resona's default is voice only

**Entschieden:** Resona's default is voice only. Where the platform language has no voice in the model, the default is writing.

**Begründung:** Voice-only would leave nothing in the workshop's own language.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/resona.vue`

## 2026-07-27: Prompt tests assert a named determination, never a particular draft's wording

**Entschieden:** A prompt test asserts a named determination of the prompt. It never asserts a particular draft's wording.

**Begründung:** A test that freezes phrasing becomes the accretion mechanism it was meant to guard against.

**Betroffene Dateien:** `devserver/tests/test_resona_canvas_graphs.py`

## 2026-07-24: Resona does not offer prefabricated binary alternatives

**Entschieden:** Resona does not offer prefabricated binary alternatives. This is written into the prompt as a disposition, beyond a ban on the sentence form.

**Begründung:** Offering alternatives prescribes the categories a decision is taken in and pre-empts the counterpart's own distinction.

**Betroffene Dateien:** `devserver/tests/test_resona_canvas_graphs.py`

## 2026-07-24: Resona's prompts and their example sentences are English

**Entschieden:** Resona's prompts and their example sentences are English.

**Begründung:** German example sentences in the core are forbidden by `test_no_prefabricated_categories_offered`.

**Betroffene Dateien:** `devserver/tests/test_evidence_duty.py`

## 2026-07-18: A search that came back empty is a third evidence-duty move

**Entschieden:** A library search that ran and came back empty is a third evidence-duty move ("miss") beside "opened" and "violation". An empty search grounds a discourse claim marked [own]: looking is owed, finding is not.

**Begründung:** Before, `validate()` knew only opened or violation, so on a topic the shelf does not hold Resona could only ask a question or cite something that did not fit.

**Betroffene Dateien:** `devserver/my_app/routes/chat_routes.py`, `devserver/tests/test_evidence_duty.py`

## 2026-07-18: A question opens a Resona turn and never closes one

**Entschieden:** A question opens a Resona turn and never closes one.

**Begründung:** A question licensed "at the end" is exactly the trailing service follow-up the prompt bans.

**Betroffene Dateien:** `devserver/tests/test_evidence_duty.py`

## 2026-07-18: Images brought to the board are auto-captioned at prompt-build time

**Entschieden:** Images brought to the Resona board are auto-captioned at prompt-build time and shown inline, without a tool call.

**Begründung:** Material a person places on the table must be present to the agent and must not be gated behind a call.

**Betroffene Dateien:** `devserver/my_app/routes/chat_routes.py`

## 2026-07-18: Brought board text is material and does not relax the evidence duty

**Entschieden:** Text brought to the board is material. It does not relax the evidence duty, which sees only `user_message`.

**Begründung:** The board-text echo exemption let a discourse term dropped on a memo license an ungrounded claim.

**Betroffene Dateien:** `devserver/my_app/routes/chat_routes.py`

## 2026-07-17: Resona's planning block receives before proposing

**Entschieden:** Resona's planning block receives before it proposes: no unasked finished plans, no pseudo-question batteries, no empty caveats.

**Begründung:** The educator's own artistic-pedagogical idea is the axis of the planning.

**Betroffene Dateien:** `devserver/tests/test_resona_canvas_graphs.py`

## 2026-07-17: Resona's evidence duty is enforced mechanically in the chat loop

**Entschieden:** Resona's evidence duty is enforced mechanically in the chat loop.

**Begründung:** Prompt exhortation alone did not stop ungrounded lecturing.

**Betroffene Dateien:** `devserver/my_app/services/evidence_duty.py`

## 2026-07-16: Resona's working position is a constitutive part of its system prompt

**Entschieden:** Resona's working position (Fachlicher Kompass) is a constitutive part of its system prompt, loaded from a committed file. It is the second exception to the no-prompt-digest doctrine; the first is the UNESCO values compass, loaded from a committed file as well.

**Begründung:** Knowledge-on-demand was searched once for show and never opened during design work; a position must be constitutive and cannot be retrievable. Values belong in the prompt, subject knowledge does not.

**Betroffene Dateien:** `devserver/my_app/routes/chat_routes.py`

## 2026-07-11: A fresh upload gets a deterministic Author-Year-Title id

**Entschieden:** A fresh operator upload gets a deterministic author-year-title `doc_id` by default. Where author or year is missing the id falls back to a title-only slug; a document id without a year is the title only, and the author is dropped as well. The ingest renames the upload's provisional id to the final id once the bibliographic fields are resolved.

**Begründung:** Provisional upload slugs are illegible, and the upload response cannot know the bibliographic id yet; the job view carries the final one.

**Betroffene Dateien:** `devserver/my_app/services/knowledge_processing.py`, `devserver/tests/test_knowledge_processing.py`, `devserver/tests/test_knowledge_curation.py`, `devserver/tests/test_knowledge_cancel.py`, `devserver/tests/test_knowledge_areas.py`

## Undatiert: Entscheidungen aus Code-Kommentaren

**Latent Lab**

- **Every picture in Cultural (Un)Known uses the platform's default seed (123456789), one number everywhere.** A column must differ from its neighbour in the reference and nothing else, and a cell must be reproducible afterwards. (`public/ai4artsed-frontend/src/views/latent_lab/default_census.vue`)
- **The three-model ceiling and the three-model lock on the chips of Cultural (Un)Known were removed.** Rows take their height from the square's width, so extra models cost nothing where the column is the narrower side. (`public/ai4artsed-frontend/src/views/latent_lab/default_census.vue`)
- **References are substituted at a star inside the base line and never appended as "in a ... context".** The research asks a model for "a Nigerian person"; a phrase hung on the end asks for something else. (`public/ai4artsed-frontend/src/views/latent_lab/default_census.vue`)
- **The reference list is fixed and identical under every base line; nations and cultures stand beside one another on purpose.** A column must always add the same thing; a state is a political container and no cultural one, and what the model does with either is what is on show. (`public/ai4artsed-frontend/src/views/latent_lab/default_census.vue`)
- **The first base line asks for the first meal of the day by description and avoids the word "breakfast".** "Breakfast" carries a meal order that is not universal. (`public/ai4artsed-frontend/src/views/latent_lab/default_census.vue`)
- **The emotion references are the six basic emotions of Ekman and Friesen; the eighteen complex ones are left out.** The six are a cross-culturally recognised set, and the others can be typed in. (`public/ai4artsed-frontend/src/views/latent_lab/default_census.vue`)
- **A cell is identified by prompt, model and seed, never by its grid position.** A press then computes only what is missing when references change. (`public/ai4artsed-frontend/src/views/latent_lab/default_census.vue`)
- **On Representation Engineering the target layer is fixed at the middle of the stack; there is no layer slider.** The middle is the position that works; the ends do nothing legible. (`public/ai4artsed-frontend/src/views/latent_lab/representation_engineering.vue`)
- **Sampling temperature on Representation Engineering is held at the backend default 0.7 and not offered.** The three cells of a row must differ in alpha and nothing else, and a row must stay reproducible from its seed. (`public/ai4artsed-frontend/src/views/latent_lab/representation_engineering.vue`)
- **Three contrast pairs are the whole set on Representation Engineering.** Three suffice for a common direction, and a fourth ray clutters the drawing. (`public/ai4artsed-frontend/src/views/latent_lab/representation_engineering.vue`)
- **No paid model is offered on Mean Images.** One press asks for a whole set per row, up to fifty calls; the platform keeps paid models out of anything a press multiplies. (`public/ai4artsed-frontend/src/views/latent_lab/mean_images.vue`)
- **Model rows on Mean Images are ordered fastest to slowest, and only the fastest row is marked when the surface opens.** Five rows marked by default would be up to five hundred generations from an untouched surface. (`public/ai4artsed-frontend/src/views/latent_lab/mean_images.vue`)
- **A press on Mean Images extends the existing run; a complete regeneration happens only where everything on the surface is already generated.** A row switched on later costs that row alone. (`public/ai4artsed-frontend/src/views/latent_lab/mean_images.vue`)
- **Every control on the one-plus-three column surfaces stands in the left column.** It is the uniform layout rule of the Latent Lab instruments. (`public/ai4artsed-frontend/src/views/latent_lab/mean_images.vue`)
- **Flow Logic runs downward in three columns, one per procedure.** The procedures are parallel. (`public/ai4artsed-frontend/src/views/latent_lab/flow_logic.vue`)
- **Text-to-sound is no crossing; Latent Audio Synth marks at the Embedding-Prozess station under conditioning.** One model generating from a prompt is the base case, and embedding manipulation belongs at conditioning. (`public/ai4artsed-frontend/src/views/latent_lab/flow_logic.vue`)
- **The Prompt station draws the platform's translation step and the adaption-to-medium box inside the model's column.** Leaving them out let the drawing claim the model reads what you wrote in the language you wrote it. (`public/ai4artsed-frontend/src/views/latent_lab/flow_stations.vue`)
- **English is excluded from the stacked language examples (de, tr, ko).** English is the target of the translation box. (`public/ai4artsed-frontend/src/views/latent_lab/flow_stations.vue`)
- **The scheduler choice was removed from Denoising Archaeology; a run takes the scheduler its pipeline carries.** It was never explained on the surface, and the methods are history. (`public/ai4artsed-frontend/src/views/latent_lab/denoising_archaeology.vue`)
- **The three phases of Denoising Archaeology are drawn as approximate zones under the axis.** Exact step ranges claimed a measured boundary that the platform's own text says is not measured. (`public/ai4artsed-frontend/src/views/latent_lab/denoising_archaeology.vue`)
- **Bias Archaeology 1 runs BBQ; WinoBias stays as Bias Archaeology 2.** WinoBias measures a differential in a comprehension task and does not measure what a model carries (Blodgett et al. 2021). (`public/ai4artsed-frontend/src/views/latent_lab/bias_archaeology.vue`)
- **Every run of Bias Archaeology draws a fresh sample of the category, the same sample for every model in the run.** The difference between two runs is then visible sampling error. (`public/ai4artsed-frontend/src/views/latent_lab/bias_archaeology.vue`)
- **Translated WinoBias items use the paired short form („ein/e Entwickler/in"); the pronoun is never paired.** A gendered occupation noun would answer in three words what the pronoun is there to leave open. (`public/ai4artsed-frontend/src/views/latent_lab/coreference_test.vue`)
- **A change of encoder on the Dimension Explorer switches the list and runs nothing; ranks name dimensions of that encoder only.** Ranks measured with All exceed the 768 and 1280 dimensions of CLIP-L and CLIP-G. (`public/ai4artsed-frontend/src/views/latent_lab/feature_probing.vue`)
- **Aesthetic Poles has one slider, one handle and one prompt per property; a neutral word is not written into the prompt.** VisionReward's tables give one ordered list and one position per property. (`public/ai4artsed-frontend/src/views/latent_lab/aesthetic_poles.vue`)
- **When a template is read from a picture, the picture is the reference and the picture-to-prompt step counts as the first manipulation.** Translating a picture into a prompt and inferring from it is a manipulation without a preset. (`public/ai4artsed-frontend/src/views/latent_lab/aesthetic_poles.vue`)
- **Runs on Interception across Models are never deleted; changing lineup, line, perspective or language moves earlier runs down.** A run is identified by all four together. (`public/ai4artsed-frontend/src/views/latent_lab/interception_models.vue`)
- **The third sweep axis of the Fusion Workbench may be none.** A mandatory third axis forces a sweep three to five times larger for a comparison nobody asked for. (`public/ai4artsed-frontend/src/views/latent_lab/fusion_workbench.vue`)
- **LoRA strength on LoRA Reach is held as a percent of trained strength, 50 to 100 %, one axis for all rows.** The dose is read downward from full effect. (`public/ai4artsed-frontend/src/views/latent_lab/lora_reach.vue`)
- **Latent Audio Synth opens at 12 s duration.** SA3 produces malformed audio below about 11 s, and 12 s is the canonical length of the semantic-axes measurements. (`public/ai4artsed-frontend/src/views/latent_lab/audio_synth.vue`)
- **Perspectives Template runs one image model.** Twelve perspectives are twelve runs already, and image-model comparison is its own instrument. (`public/ai4artsed-frontend/src/views/latent_lab/perspectives_template.vue`)
- **The original fusion strategy of Encoder Fusion has no chip on the surface; the backend keeps it.** Next to `centered_fade` it changes three things at once and cannot say which did what. (`public/ai4artsed-frontend/src/lib/fusionWeights.ts`)
- **The alpha track of Encoder Fusion is non-linear: a linear band, logarithmic outside.** On a linear track the CLIP/T5 points were two pixels apart. (`public/ai4artsed-frontend/src/lib/fusionWeights.ts`)
- **Example prompts come from one central preset source.** Five surfaces carried duplicates. (`public/ai4artsed-frontend/src/lib/promptPresets.ts`)
- **LLM-smoothed transcription errors in Re-enactment stay unmarked.** Two texts one under the other show the silent smoothing as it is; a marking would be staged. (`docs/ARCHITECTURE PART 38 - Cover-Band.md`)
- **The shell bar carries the trigger and the run state only, no instrument name.** The left of the bar already says where the visitor is. (`public/ai4artsed-frontend/src/components/ShellRun.vue`)
- **ModelPicker offers presets only, no per-model chips.** Sixteen chips took 327 px of an 809 px column and pushed the case under the window edge. (`public/ai4artsed-frontend/src/components/ModelPicker.vue`)

**Flow**

- **The flow surface never refuses a generation; a manual model choice without the material it needs falls back to the automatic route, except 3D, which first generates an SD 3.5 image.** 3D has no text path at all, and a hand-picked model holds only while the material can feed it. (`docs/ARCHITECTURE PART 37 - t2x-Flow-Assemblage.md`, `public/ai4artsed-frontend/src/composables/useMaterialRouting.ts`)
- **On cards under 50 GB the longest audio output stays at 120 s.** The four-minute promise does not hold there, and the limit is now visible. (`docs/ARCHITECTURE PART 37 - t2x-Flow-Assemblage.md`)
- **The x2x legacy hub is replaced by Flow; the old paths redirect to `/x2x-flow`.** The old paths are written down in workshop handouts. (`docs/ARCHITECTURE PART 21 - Frontend-Icons-Navigation.md`)
- **The favourites strip offers no hand-on or copy button; its row is the star plus the way back into the instrument.** A plate can be dragged from the favourites straight into the Flow. (`public/ai4artsed-frontend/src/components/FooterGallery.vue`)
- **The mark for keeping is the star, platform-wide.** The flow's viewer bar already drew the star, and the heart stood only in one place. (`public/ai4artsed-frontend/src/components/MediaActionBar.vue`)
- **The card front is the medium alone; the action row stands on the back, in the flow too.** A picture being looked at is worth more unobstructed than a hand's breadth of buttons over it. (`public/ai4artsed-frontend/src/components/MediaCardFront.vue`)
- **The flow card comes with a back (450 ms hold) whenever a page fills the back slot.** Provenance belongs to the box; printed under the front it competes with the thing. (`public/ai4artsed-frontend/src/components/FlowCard.vue`)
- **Run progress is a named count where a run makes countable things and a percentage where it makes one.** A bare pair of numbers says how many without saying of what. (`public/ai4artsed-frontend/src/components/FlowRunProgress.vue`)
- **There are no fail-open safety checks at any call site; a check that could not run is an operational state and never a content rating.** A verdict that fails to arrive must not become a permission, and a fail-open could otherwise be put back at a call site with all shared-check tests still green. (`public/ai4artsed-frontend/src/composables/useGenerationStream.ts`, `public/ai4artsed-frontend/src/components/__tests__/MediaInputBox.safety.spec.ts`)
- **The gallery title is "Favorites" without "My".** The Mine/All switch already states the ownership. (`public/ai4artsed-frontend/src/i18n/en.ts`)

**Compare**

- **Effect-check surfaces (Interception Scope) limit the image models to SD 3.5, Flux 2 and, since 2026-10-18, Flux 3 Klein.** The picture is a check and no subject. (`public/ai4artsed-frontend/src/data/rasterImageModels.ts`)
- **The voice test sentences hold one tale per language and never a translation; Korean is the exception and carries the German tale translated.** Prosody is a property of a language, and no accessible public-domain Korean rendering by a Korean author exists. (`public/ai4artsed-frontend/src/data/voiceTestSentences.ts`)

**Resona and Help**

- **The help panel opens by itself on a page's first visit, stays open across a route change if the new page is also unvisited, and otherwise closes.** What stood in the panel belonged to the previous page. (`public/ai4artsed-frontend/src/components/ChatOverlay.vue`)
- **The platform greeting is shown on the start page only; other pages open with their own address or "no page info".** The greeting read as though the place had been covered when most places carry no text. (`public/ai4artsed-frontend/src/components/ChatOverlay.vue`)
- **After someone has talked in the help panel on a page, that page's address no longer comes up by itself; it is fetched by hand via the arrow, and a reload resets this.** The address is an introduction; once a conversation exists it is only fetched on request, and a conversation ends with the tab. (`public/ai4artsed-frontend/src/components/ChatOverlay.vue`, `public/ai4artsed-frontend/src/stores/pageAddress.ts`)
- **The lab's general address defines the frame; `addressFor` matches the route exactly, and no instrument inherits the lab's address.** An instrument without a text of its own says so in help's words. (`public/ai4artsed-frontend/src/stores/pageAddress.ts`)
- **On user interaction the platform voice's words fade out entirely.** Only one turn is ever shown; a dimmed second text is a reading cost with nothing to buy. (`public/ai4artsed-frontend/src/components/PlatformVoice.vue`)
- **New cards are dealt onto empty areas of the Resona board, never over cards or standing words.** The voice is part of the scene, and otherwise every card fell on one spot. (`public/ai4artsed-frontend/src/composables/useFreeSpot.ts`)

**Backend**

- **HeartMuLa runs at topk 70 and cfg_scale 3.0; heartlib's README defaults of 50 and 1.5 are not used.** cfg_scale acts on the autoregressive LM's logits and governs tag adherence; halving it halved tag adherence. (`devserver/schemas/chunks/output_music_heartmula.py`)
- **The watermarking document quotes the Regulation's wording and makes no assessment of the platform's role under Art. 50.** The earlier assessment quoted no line of the Regulation and predated applicability. (`docs/ARCHITECTURE PART 36 - Watermarking & Provenance.md`)

**Styling**

- **The queue chip's colour reads the wait (green, amber, red) and never whose place it is.** The column is one statement; two colours in it would read as two. (`public/ai4artsed-frontend/src/components/PolicyChips.vue`)
- **`.lab-note` text stands at 72 % white and its heading at 88 %.** 45 % and 70 % did not carry on the lightest background tone. (`public/ai4artsed-frontend/src/assets/flow-stage.css`)
- **The platform uses three type faces only (400, 400 italic, 700).** Text says only two things, and another weight is a fourth face nobody chose. (`public/ai4artsed-frontend/src/assets/base.css`)
- **Type steps are platform-wide in base.css; every box stands on the system's steps.** flow-stage.css is not loaded on every page. (`public/ai4artsed-frontend/src/assets/base.css`)

---

## 2026-10-02: „Neu“ auf dem Canvas öffnet einen Ring fertiger Workflows; vor jeder Generierung des Canvas steht Stufe 3

**Anlass:** Das Canvas braucht ein Preset-System für basale Workflows, wie sie auch im Flow stattfinden, und für exemplarische explorative Workflows nach geeigneten Instrumenten des Latent Lab, dazu ein Stille-Post-Kettenspiel, bei strenger UI/UX-Konsistenz. Die linke Seite der Leiste wird nicht für den Namen verwendet.

**Entschieden:**
- **„Neu“ öffnet den Blasen-Ring der Plattform** (`BubbleRingFrame`, `fitRing`), auf dem auch Perspektiven und LoRAs gewählt werden: ein fertiger Workflow ist eine Art Preset, und eine zweite Form für dieselbe Geste wäre der Bruch. Zwei Arten, Grundformen und Erkundungen; in der Mitte das leere Brett, wie „Neu“ es bisher machte. Eigene Workflows stehen nicht auf dem Ring, sie liegen in der Favoritenleiste.
- **Presets sind Daten**: `.atcanvas`-Dateien in `devserver/schemas/canvas_presets/`, ausgeliefert über `GET /api/canvas/presets`, gelesen durch den Import-Leser. Sie benennen Perspektiven, Aufstellungen, Beispiel-Prompts und Lesarten und werden beim Öffnen gegen die Installation aufgelöst — eine Perspektive mit ihrem aktuellen Text, nie einer eingefrorenen Kopie. Geöffnet wird eine Kopie mit dem Namen des Presets und `presetId`. Ein Brett, das noch so ist, wie es geöffnet wurde, hält keine Arbeit.
- **Grundformen** sind die Wege des Flow als Knoten: Text → Bild, Text → Video, Text → Klang (Eingabe, Interception, Anpassung, Übersetzung, Generierung) und Bild → Text. Text → Code entfällt, weil das Canvas keinen Code ausführt.
- **Erkundungen** folgen den Instrumenten und tragen ihre Namen: Sprachmodell-Vergleich (die Aufstellung `openWeights`, Flux 2, ein Seed, dazu der Prompt wie geschrieben), Perspektiven an einer Vorlage (vier Perspektiven, SD 3.5 Large), Bildverständnis (drei Größen von qwen3-vl in einer Lesart), Modell-Vergleich (SD 1.5, SDXL, SD 3.5 Large — die Auswahl „history“ des Instruments). Dazu Stille Post: sechs Glieder, die Lesart „descriptive“, ein eigener Seed je Bild.
- **Vor jeder Generierung steht ein Übersetzungsknoten.** Der Flow und die Instrumente übersetzen in Stufe 3; das Canvas hat dafür nur diesen Knoten.
- **Eine Interception ohne Perspektive reicht ihren Text unverändert weiter** (`config_loader.wants_passthrough`); bis dahin fragte sie ihr Sprachmodell ohne Perspektive. Eine Perspektive, deren Text nicht ankam, hält den Lauf an, statt durchzureichen; ein Preset öffnet auf ihr gar nicht erst.
- **Vor jeder Generierung des Canvas steht die Stufe 3 des Flow** (`execute_stage3_safety`; `canvas_executor.canvas_stage3_verdict`), für den Prompt und einen zweiten Text, auch im alten Endpunkt `POST /api/canvas/execute`, den das Frontend nicht mehr ruft. Gefragt wird auf jeder Stufe, wie der Flow fragt; Stufe 3 prüft bei kids, youth und open (Übersetzung für die Prüfung, §86a, Sicherheitsklassifikator mit der Frage der Stufe) und lässt adult und research durch. Bis dahin sah auf dem Canvas nur das Sicherheitspräfix einer Interception einen Text an: Ein Text, der ohne Interception zur Generierung ging, und jeder Graph aus Resona erreichten das Modell ungeprüft. Gelesen wird nur das Urteil; die Generierung bekommt den Text des Bretts, und deshalb wird jeder Text geprüft, wie er gegeben ist (`as_given`): bei kids liest der Klassifikator die Übersetzung und den Text, den das Modell bekommt. Eine Prüfung, die nicht laufen kann, sperrt den Knoten, nicht den ganzen Lauf. Nicht gewählt: eine Prüfung im Durchreichen, denn sie sähe nur die Texte, die durch eine Interception laufen, und Stufe 1, denn sie kennt keine Altersstufe und prüft nicht auf Jugendschutz.
- **Ein gescheiterter Lauf zeigt, was er hat und warum.** Die Karten seiner anderen Zweige bleiben in der Ergebnis-Fläche, der Knoten nennt seinen Fehler in einer Zeile, und eine Sperre öffnet das Sicherheitsfenster der Plattform (`safetyEvent.reportBlock`); Zeile und Fenster nennen sie mit demselben Satz (`safetyBlockKeyForEvent`). Bis dahin las das Canvas von einem gescheiterten Lauf nur die Meldung, und nichts zeigte sie.
- **Das Namensfeld** wird an Ort und Stelle geschrieben wie der Name einer Perspektive auf dem Flow-Brett. Der Stern merkt kein Brett unter dem Namen eines Presets, in keiner Sprache; warum nicht, sagt eine Zeile vor dem Namen statt eines Dialogs.

**Offen:** Das Canvas hat keine Stufe 1: Die Prüfung auf personenbezogene Daten, die der Flow auf jeder Stufe macht, fehlt auf jeder Stufe, die auf §86a bei adult und research. Andere Sprachen: WO-2026-10-02-A.

## 2026-10-01: Der Canvas-Workflow ist eine Datei mit eigener Endung und eigenem Namen, und er steht in der Favoritenleiste

**Anlass:** Der Canvas hatte keine Ablage und speicherte jede Datei als `New_Workflow.json`, auf der Platte nicht wiederzufinden. Für Umlaute gelten verbreitete Standards.

**Entschieden:**
- **Endung `.atcanvas`** (ATELIER Canvas). `.canvas` ist vergeben: das offene JSON-Canvas-Format, das Obsidian öffnet. Der Inhalt bleibt eingerückte JSON mit `type: 'canvas_workflow'` und `formatVersion: 1`; was eine Datei zum Canvas-Workflow macht, ist dieser Typ, nicht der Name. Der Import nimmt `.atcanvas` und `.json` (Exporte vor dem 01.10., Resonas Apparate auf dem Server) und lehnt alles andere mit einer Meldung ab.
- **Der Workflow hat einen Namen**, in einem Feld in der Kopfleiste des Canvas. Der leere Workflow heißt nicht mehr „New Workflow"; eine alte Datei mit diesem Namen gilt als unbenannt.
- **Dateiname `<Name>_<JJJJ-MM-TT>_<HHMM>.atcanvas`**, Ortszeit. Ohne Namen der Prompt des ersten Eingabeknotens, ohne den die Modelle, sonst `canvas`. Die Ausgaben eines Canvas-Laufs beginnen mit denselben Wörtern, dahinter Modell und Position.
- **Umlaute und Schriften:** lateinische Schrift in den portablen POSIX-Dateinamenzeichen, ä ö ü ß ausgeschrieben wie in DIN 5007-2, allen anderen lateinischen Buchstaben das diakritische Zeichen abgenommen. Kyrillisch, Hangul, Hebräisch und Arabisch, die Schriften der Plattformsprachen, bleiben stehen: für sie gibt es keine Umschrift, die lesbar bleibt, und die alte Reduktion auf `[a-zA-Z0-9]` machte aus jedem solchen Wort nichts. `-` trennt Wörter, `_` Teile; 32 Zeichen je Teil, 200 Bytes je Name. Das gilt für jeden Download der Plattform, der über `mediaFileName` geht.
- **Favoritenleiste:** Ein Favorit ist ein Lauf. Der Stern im Canvas legt deshalb einen eigenen Lauf an, der nur den Workflow enthält (`POST /api/canvas/keep`, Medienart `canvas`). Die Leiste zeigt ihn mit dem Zeichen des Canvas, öffnet ihn zurück in den Canvas und speichert ihn als `.atcanvas`. Eine im Canvas gemerkte Ausgabe öffnet ebenfalls den Canvas, mit dem Workflow aus dem `workflow.json` ihres Laufs; dort steht jetzt auch der Name, und im Batch das Brett, wie der einzelne Lauf es gerechnet hat (Prompt des Laufs; Seed des Laufs als Basis eines „Batch (+1)“-Seed-Knotens, der allein das Bild wiederholt und im neuen Batch weiterzählt). Resonas Apparate laufen über denselben Weg, kehren aber nicht in den Canvas zurück, weil sie in Resona entstanden sind.

**Nicht in diesem Schritt:** Synth-Presets (`.atsynth`) und die Dateinamen der übrigen Medienarten beim Download aus der Favoritenleiste (dort weiterhin `<run_id>.<ext>`).

## 2026-10-01: Der Song im Flow läuft wieder; Stufe 2 führt keinen Plan aus, der Medien erzeugt; ein Abbruch erreicht den laufenden Song; Config-Namen werden vor jedem Commit geprüft

**Anlass:** Der Song-Weg im Flow brach bei jedem Durchlauf ab, und der Fehler verlangte eine vollständige Ursachenanalyse an Stelle einer Symptomkorrektur.

**Ursache:** `58280833` (2026-08-07) löschte `schemas/configs/interception/heartmula.json` als verwaiste Perspektive. Der Song-Weg im Flow (`runMusic`, seit `af517455`, 2026-07-10) schickt `schema: 'heartmula'`; jede Anfrage endete seither mit 404.

**Entschieden:**
1. `heartmula.json` ist wiederhergestellt und im Perspektiven-Katalog verborgen (`02639c35`).
2. Stufe 2 führt auf keiner Route einen Plan aus, der Medien erzeugt (`_plan_makes_media`; POST `/pipeline/interception`, die streamende GET-Route, `/pipeline/stage2`). Die Aufhebung von `skip_stage2` bei `kids` und `youth` gilt nur für einen Plan, der ein Textmodell aufruft (`_plan_runs_no_text_model`), und greift damit für keine ausgelieferte Config. Bis dahin entstand der Song bei `kids` in Stufe 2, und Stufe 3 prüfte das Wort `heartmula_generated`.
3. `custom_placeholders` trägt nur `TEXT_1` und `TEXT_2`, nur als Zeichenketten; alles andere beantwortet die Route mit 400. Stufe 1 prüft sie, dazu `interception_result` und `optimization_result` aus dem Body. Stufe 3 prüft sie und die CLIP-Bildunterschrift so, wie der Chunk sie liest (`execute_stage3_safety(..., as_given=True)`): im Original, bei `kids` zusätzlich übersetzt.
4. Ein gesperrter, gescheiterter oder abgebrochener Song kommt als `blocked`, `error` oder `cancelled` zurück; bis dahin kam er als `success`.
5. Die Route steht von ihrer ersten Zeile an in der Geräteliste und hält ihren Eintrag frisch, solange sie auf die Karte wartet. Der ComfyUI-Client vermerkt jeden Prompt unter der Lauf-ID seines Kontexts (`generation_abort.note_prompt`), und der Abbruch unterbricht ihn. Der HeartMuLa-Knoten fragt bei jedem Frame nach der Unterbrechung. Das Abbruch-Flag eines Geräts nennt den Lauf, für den es gesetzt wurde; bis dahin las das nächste Bild desselben Geräts den Abbruch des Songs als seinen eigenen.
6. Welche Linse ein Canvas-Knoten ausführt, entscheidet allein der Ausführer (`canvas_executor._load_interception_context`): eine vorhandene Datei, eine Text-Pipeline, Kontexttexte. Die Liste, gegen die Resonas Graphen geprüft werden, ist daraus abgeleitet: 37 Configs, bis dahin 46. Die Linse „De-Kitsch“ heißt im Frontend `clichéfilter_v2` wie ihre Datei (`200da423`).
7. Gate 9 im Pre-Commit-Hook (`06547969`) führt `test_config_references_resolve.py` (`d8a4d208`) und `test_output_config_carry_list.py` gegen den gestagten Stand aus, sobald ein Commit `devserver/` oder `public/ai4artsed-frontend/src/` berührt.

**Widerspruch zu einer dokumentierten Entscheidung:** Der Eintrag vom 2026-08-05 ersetzt die prompt-getriebene Musikerzeugung durch Silly Parrot, mit der Obergrenze 60 s. Am 2026-08-07 bekam Silly Parrot einen Rahmen von 10 bis 240 s (`4d07ece3`), am 2026-08-08 wurde die Aufnahme auf höchstens 240 s festgelegt (`bbd41622`); dort bestimmt die Aufnahme die Länge des Songs. Die Seite heißt heute „Re-enactment“. Der wiederhergestellte Weg ist prompt-getriebene Musikerzeugung im Flow. Er läuft dort durch die Prompt Interception, und `heartmula_standard` gab ihm bis 2026-10-03 240 000 ms als Budget.

**Nachtrag 2026-10-03:** Der Song-Weg im Flow bleibt, mit der Obergrenze 60 s, aus pragmatischen und Fair-Culture-Erwägungen. `heartmula_standard` und die Vorgabe des Chunks `output_music_heartmula` tragen seitdem 60 000 ms; das gilt für jeden HeartMuLa-Song aus einem Prompt (Flow, Resona, Persona, Canvas, dazu `acestep_simple` und `acestep_longnarrativeprompts`, die über `music_generation` auf HeartMuLa laufen). „Re-enactment“ (früher Silly Parrot, dann Cover Band) gibt die Länge der Aufnahme mit und bleibt bei 10 bis 240 s. Bei 60 000 ms ist der längste Song 60,08 s lang: heartlib erzeugt einen Frame und dann bis zu 750 weitere zu 80 ms.

**Nachtrag 2026-10-06:** Der Song-Weg ist umgebaut, damit er keine Parallelstruktur bildet. Der Song im Flow läuft über den Generierungsstrom, den jeder erzeugende Lauf der Seite öffnet (`finishRun`, GET `/pipeline/generation`), mit dem Stil als `secondary_text`. Die Route nimmt `secondary_text` nur im Strom und nur für eine Config mit `meta.requires_dual_input` an, heute `heartmula_standard`. Stufe 1 prüft den Liedtext nach der Interception und den Stil; Stufe 3 prüft den Liedtext und dann beide zusammen, wie der Chunk sie liest (`as_given`); das Modell erhält beide unübersetzt. Punkt 1 oben ist damit überholt: `heartmula.json` ist wieder entfernt, weil der Flow den Namen nicht mehr schickt. Punkt 3 ebenso: `/pipeline/interception` weist `custom_placeholders` ab; die Prüfung von `interception_result` und `optimization_result` bleibt.

**Betroffen:** `devserver/my_app/routes/schema_pipeline_routes.py`, `devserver/schemas/engine/stage_orchestrator.py`, `devserver/my_app/services/generation_abort.py`, `comfyui_ws_client.py`, `canvas_executor.py`, `canvas_graph_authoring.py`, `comfyui_nodes/ai4artsed_comfyui/_heartmula.py`, `devserver/schemas/configs/interception/heartmula.json`, `public/ai4artsed-frontend/src/types/canvas.ts`, `scripts/git-hooks/pre-commit`; Tests `test_song_path_gate.py`, `test_cancel_reaches_comfyui.py`, `test_song_stops_between_frames.py`, `test_config_references_resolve.py`, `test_output_config_carry_list.py`, `test_sse_transport_sites.py`, `test_sse_silent_windows.py`; `docs/ARCHITECTURE PART 26 - Canvas-Workflow-System.md`.

---


## 2026-10-01: Stable Audio Open 1.0 verlässt die Plattform, Stable Audio 3 tritt an seine Stelle

**Anlass:** Stable Audio Open 1.0 wird aus der Plattform entfernt und durch Stable Audio 3 ersetzt.

**Entschieden:** Die beiden Konfigurationen von Stable Audio Open 1.0 (`stableaudio`, `stableaudio_tellastory`) sind entfernt, mit ihrer Pipeline `audio_generation` und den Chunks `output_audio_stableaudio.json` und `comfyui_audio_generation.json`. Klang erzeugt auf der Plattform Stable Audio 3 (`stableaudio_open`, `stableaudio_music`, `stableaudio_sfx`). Sein Chunk hat keinen Ausweichweg mehr (`fallback_chunk: None`). Bis heute lief ein gescheiterter Lauf von Stable Audio 3 auf Stable Audio Open 1.0 über ComfyUI weiter, und die Verfügbarkeitsprüfung meldete Stable Audio 3 als verfügbar, wenn sein Knoten nicht erreichbar war und die Gewichte von 1.0 in ComfyUI lagen. Jetzt meldet sie es in diesem Fall als nicht verfügbar, und ein gescheiterter Lauf endet mit seinem eigenen Fehler. Die stillgelegte Kopie `my_app/services/stable_audio_backend.py` bleibt mit ihrem Vermerk stehen, wie in `7f025758` (2026-08-26) für die stillgelegten Kopien festgelegt.

**Ersetzt:** den Satz der drei Configs von Stable Audio 3, die ComfyUI-Konfiguration von 1.0 bleibe als Transparenz-Referenz erhalten (`meta.notes`, `provenance.known_gaps` in allen zehn Sprachen). Stehen bleibt, dass Stable Audio Open 1.0 seine Trainingsdaten vollständig attribuiert hat und Stable Audio 3 nicht.

**Stand vorher:** `stableaudio` lief am 27.09. unter ComfyUI 0.15 und am 30.09. unter 0.36 nicht; der Workflow blieb mit nicht ersetzten Platzhaltern (`{{SCHEDULER}}`, `{{STEPS}}`, `{{CFG}}`) aus `comfyui_audio_generation.json` stehen. `stableaudio_tellastory` lief über denselben Weg.

**Gewichte:** am 01.10. in die Ablage „weights“ verschoben und auf lab6000 gelöscht, jede Datei erst nach dem SHA-256-Vergleich mit ihrer von der Platte gelesenen Ablagekopie: aus `dlbackend/ComfyUI/models/` `checkpoints/stable-audio-open-1.0.safetensors`, `checkpoints/OfficialStableDiffusion/stableaudio/`, `checkpoints/OfficialStableDiffusion/stableaudio_model.safetensors`, `clip/CLIP_stableaudio_model.safetensors` und `clip/t5-base.safetensors` (zusammen 26,3 GB), dazu `~/.cache/huggingface/hub/models--stabilityai--stable-audio-open-1.0` (10,1 GB). Der HF-Cache-Eintrag lag schon unter `huggingface_cache/hub/` auf dem Laufwerk, aus dem Abbild vom 24.09.; was davon byte-gleich auch unter ComfyUI lag, ist nicht noch einmal abgelegt. Neu kopiert sind 5,6 GB nach `0_Modelle/unused/stableaudio1_2026-10-01/`, das Protokoll liegt dort. Kein anderer Weg der Plattform las sie.

**Betroffen:** entfernt `devserver/schemas/configs/output/stableaudio.json`, `stableaudio_tellastory.json`, `devserver/schemas/pipelines/audio_generation.json`, `devserver/schemas/chunks/output_audio_stableaudio.json`, `comfyui_audio_generation.json`; geändert `devserver/schemas/chunks/output_audio_stableaudio_diffusers.py`, `devserver/schemas/configs/output/stableaudio_{open,music,sfx}.json`, `devserver/my_app/services/parrot_service.py` (Kommentar und Log-Zeile), `devserver/trashy_interface_reference.txt` (Stable Audio 3 statt Open 1.0), die Tabellen in `devserver/tests/test_safety_coverage_map.py`, `test_output_config_carry_list.py`, `test_python_chunk_seed_policy.py`, `devserver/scripts/probe_workshop_models.py` (fährt `stableaudio_open`), `measure_execution_times.py`, `update_chunks_with_timing.py`, und die Stellen in `docs/QUALITAETSSTUFEN_MODELLE.md` (Nachtrag), `docs/ARCHITECTURE PART 03/04/08/31/32`, `docs/ARCHITECTURE_REQUIREMENTS.md`, `docs/installation/MODELS_REQUIRED.md`, `docs/installation/OFFLINE_INSTALL_MEDIUM.md`, die den heutigen Stand beschreiben.

---

## 2026-09-28: Das Upload-Gate lehnt ab, wenn sein §86a-Scan nicht laufen kann

**Ticket:** UCD-140.

**Befund:** `scan_text_layer` in `devserver/my_app/services/upload_gate.py` fing den `ImportError` des §86a-Matchers (`schemas.engine.stage_orchestrator.fast_filter_bilingual_86a`) ab, schrieb eine `logger.warning`-Zeile und übersprang den Scan. Das Gate antwortete dann „sauber“ über ein Dokument, in das nichts hineingesehen hatte: die Route speicherte es, ließ Docling laufen und meldete Erfolg. Zwei Bildschirme darüber wirft `_load_terms` bei einer vorhandenen, aber unlesbaren Kuratierungsliste `RuntimeError` („a safety list that exists but cannot be read must never silently disable itself“). Diese Asymmetrie ist der Befund: der deterministische Kernscan war die eine Prüfung, die still ausfallen konnte, während alles andere grün meldete.

**Entschieden (fail-closed):** Ein Scan, der nicht laufen kann, ist eine Ablehnung wie jede andere. `scan_text_layer` gibt beim `ImportError` die neue Kategorie `REASON_SCAN_UNAVAILABLE` (`"scan_unavailable"`) zurück und protokolliert den Fehler mit `logger.error`. Ein `None` aus dieser Funktion heißt seither: jede Prüfung ist tatsächlich gelaufen. `gate_pdf_upload` und `gate_stored_pdf` reichen die Kategorie unverändert weiter, und die drei Routen (`knowledge/upload`, `knowledge/reprocess`, `scene/upload`) behandeln sie über ihren vorhandenen Weg, ohne eine geänderte Zeile: `audit_rejection` schreibt die Auditzeile (Zeitstempel, Dokument-Hash, Kategorie, Herkunft), `reject_message` liefert den Klartext, die Antwort ist 400 und nichts wird gespeichert. **Begründung:** der deterministische Kernscan darf nie still ausfallen. Eine Ablehnung ist rücknehmbar, der Betrieb lädt erneut hoch, sobald die Installation wieder vollständig ist; ein angenommenes, ungeprüftes Dokument ist nicht rücknehmbar.

**Der Klartext nennt keine Interna:** „Dokument nicht angenommen: die Sicherheitsprüfung ist derzeit nicht verfügbar.“ Anredefrei, ohne Modul-, Import- oder Matcher-Namen. `stage_orchestrator.SAFETY_CHECK_UNAVAILABLE_MESSAGE` ist bewusst nicht wiederverwendet: der Satz liegt in genau dem Modul, dessen Import gescheitert ist, und er richtet sich an die Lernenden mitten im Lauf, wo diese Fläche den Betrieb anspricht.

**Klassen-Prüfung der Nachbarschaft, im selben Durchgang:**
- `extract_text_layer` (`except Exception` → `""`, `noqa: BLE001`) bleibt fail-open, geprüft und so entschieden. Sie erzeugt die EINGABE des Scans, nicht die Prüfung selbst, und ein fehlender Textlayer ist eine legitime Eigenschaft eines gescannten Dokuments (reine Bild-PDFs sind hier der Normalfall; die Stufe-B-Modellprüfung der Pipeline deckt sie ab). Fail-closed an dieser Stelle würde jedes eingescannte PDF ablehnen. Die Regel gilt dort, wo die PRÜFUNG fehlt, nicht dort, wo das Material leer ist.
- `validate_pdf`: die vier `except Exception` geben bereits eine `REASON_*`-Kategorie zurück, sind also fail-closed. Unverändert.
- `page_annots`: eine unlesbare Annotation wird übersprungen, weil sie kein Beleg für eine Startaktion ist; der umgebende Seitendurchlauf lehnt bei hartem Fehler mit `REASON_NOT_PDF` ab. Unverändert.
- `_read_index` (unlesbarer Hash-Index → leeres Dict + Warnung): kein Sicherheits-Gate, sondern der Doppelanalyse-Schutz. Ein leerer Index lässt eine zweite Analyse zu, kein ungeprüftes Dokument. Unverändert.
- `scene_capsule_pipeline.deterministic_safety_pass` reicht `scan_text_layer` durch; eine Antwort ungleich `None` verwirft die Kapsel. Die neue Kategorie wirkt dort ohne Änderung fail-closed: ohne Matcher überlebt keine Kapsel.

**Prüfungen:** `devserver/tests/test_upload_gate.py::TestScanUnavailableFailsClosed` mit sieben Fällen (Rückgabe statt `None`, `logger.error`, beide Gates, Gegenprobe mit vorhandenem Matcher, Klartext ohne Interna und ohne Anrede, Auditzeile ohne Inhalt) und `test_upload_gate_routes.py::TestRejectLeavesNoTrace::test_unavailable_scan_rejects_and_stores_nothing` (400, Auditzeile, nichts gespeichert, kein neuer Job). Den `ImportError` erzeugt `monkeypatch.setitem(sys.modules, "schemas.engine.stage_orchestrator", None)`.

**Betroffen:** `devserver/my_app/services/upload_gate.py`, `devserver/tests/test_upload_gate.py`, `devserver/tests/test_upload_gate_routes.py`.

---

## 2026-09-27: Der Pre-Commit-Hook führt die Flow-Specs aus

**Anlass:** Der Commit `bb33dc01` hatte die Flow-Seite lahmgelegt, und die beiden Flow-Specs liefen vor keinem Commit.

**Entschieden:** Gate 8 in `scripts/git-hooks/pre-commit` führt jede `src/views/__tests__/x2x_flow.*.spec.ts` gegen das gestagte Frontend aus, aus dem Index kopiert, sobald ein Commit `public/ai4artsed-frontend/src/` berührt. Ein unbehandelter Fehler zählt als Fehlschlag. Ohne `node_modules` warnt das Gate und tritt beiseite. `stores/configSelection.ts` übernimmt eine Antwort ohne Config-Liste nicht mehr: Sie gilt als Fehler, und die stehende Liste bleibt. Bis dahin setzte der Store `undefined` ein, und der Perspektiven-Katalog warf bei jeder Aktualisierung; in den Flow-Specs waren das 16 unbehandelte Fehler, mit denen vitest auch bei bestandenen Tests mit Code 1 endete.

**Betroffen:** `scripts/git-hooks/pre-commit`, `public/ai4artsed-frontend/src/stores/configSelection.ts`.

---

## 2026-09-27: Die Modellwahl im Flow zeigt die Karte der t2x-Seite; für die Qualitätsstufe liegt ein Maßstab zur Bestätigung vor

**Anlass:** Der Hover des Modellnamens im Flow zeigte bei einer Wahl von Hand den Satz `x2xFlow.choiceHeld`, während die t2x-Seite zu demselben Modell bereits eine Karte mit Informationen hatte. Die Qualitätsstufe braucht einen Maßstab; als Anker sind das für Amateure am Markt verfügbare technische Optimum und die niedrigste Qualität generativer KI von 2021/22 vorgeschlagen.

**Entschieden:** Die Modell-Blasen unter einem Medium-Zeichen und der Modellname in der Box tragen die Karte der Plattform (`InfoCard` mit `InfoCardFacts`) mit den vier Angaben der t2x-Hover-Karte: voller Name, Qualität und Tempo in je fünf Sternen, geschätzte Dauer der Erzeugung. `InfoCardFacts` ist dafür um die Sternzeilen und die Dauer erweitert (`docs/ELEMENT_STRUCTURE_REGISTRY.md`). Die Werte liefert `GET /api/schema/output-cards` aus Config und Chunk. Von der t2x-Seite nicht übernommen: die feste Namensliste (der Name kommt aus dem Feld `name` der Config), die feste Zuordnung von Config zu Chunk (sie kommt aus `OUTPUT_CHUNK`, dem Chunk, der läuft; für Flux 2 und Stable Audio 3 las die t2x-Seite einen anderen, und die Karte zeigt dort andere Werte als sie), die drei Ersatzsterne für eine fehlende Stufe und „~1 sec“ für eine fehlende Dauer. `x2xFlow.choiceHeld` ist aus `en.ts` entfernt, aus den anderen Sprachdateien per Arbeitsauftrag WO-2026-09-27-K; das Medium-Zeichen nennt beim Hover sein Medium.

**Maßstab, vorgeschlagene Kriterien und Stand der Stufen:** `docs/QUALITAETSSTUFEN_MODELLE.md`.

**Nachtrag 2026-09-27:** Die begründeten Vorschläge für die vier offenen Stufen und die Streichung von „(ComfyUI)“ aus dem Namen der Config `wan22_t2v_video_fast` sind angenommen. Die Stufen stehen seither in den Chunks: Qwen Image Edit Lightning 3, Qwen 2511 Multi-Image Fusion 4, Stable Audio 3 3, Hunyuan3D-2 2. Der Zusatz ist in allen zehn Sprachen gestrichen; er nannte die Software, in der das Modell auf dem Server läuft, und die t2x-Seite zeigte den Namen ohne ihn. Die Kriterien und die Anker sind weiter nicht bestätigt.

**Betroffen:** `devserver/my_app/routes/schema_pipeline_routes.py`, fünf Chunks unter `devserver/schemas/chunks/`, `public/ai4artsed-frontend/src/composables/useOutputCards.ts`, `src/services/api.ts`, `src/components/InfoCardFacts.vue`, `src/components/ChipSelect.vue` (`ChipInfo`), `src/components/FlowBubbles.vue`, `src/views/x2x_flow.vue`, `src/i18n/en.ts`, `src/i18n/WORK_ORDERS.md`, `docs/ELEMENT_STRUCTURE_REGISTRY.md`; mit dem Nachtrag vier weitere Chunks und `devserver/schemas/configs/output/wan22_t2v_video_fast.json`.

---

## 2026-09-26: Die Plattform wird mit Tastatur und Maus oder Trackpad bedient, auch auf iPad und Android

**Anlass:** Die Plattform ist nicht mehr für die Touchbedienung auf iPad oder Android vorgesehen; wird iPad oder Android benutzt, dann mit Tastatur und Maus oder Trackpad.

Die Festlegung stand bis dahin nirgends im Repo, und am selben Tag bekamen die Scheiben im Flow einen eigenen Zweig für den langen Touch-Druck unter Chrome auf Android (`a52f94ca`, mit `b1263c80` wieder entfernt). Zeigerbehandlung wird für Maus und Trackpad gebaut und geprüft; Touch-Gesten (langer Druck, zweiter Finger, das Kontextmenü eines langen Drucks) bekommen keinen eigenen Zweig und keinen eigenen Testfall. Die Anforderung „touch-basiert“ im Eintrag „Text-to-3D Pipeline“ (2026-03-06) ist damit überholt.

**Betroffen:** jede Zeigerbehandlung der Oberfläche; zuerst `public/ai4artsed-frontend/src/views/x2x_flow.vue` und `src/views/__tests__/x2x_flow.discs.spec.ts`.

---

## 2026-09-27: Im Embedding interpoliert Composable Diffusion zwischen den Begriffen, statt sie zu addieren

**Anlass:** Eine Messung an „an apple" und „a tree" ergab entweder den einen Begriff ganz oder den anderen, nie eine Mischung, kippend bei 0,05 Gewichtsunterschied.

**Entschieden:** Die Stelle „conditioning" führt die Kodierungen mit `slerp_tokens` zusammen, der sphärischen Interpolation aus `comfyui_nodes/ai4artsed_sd3_conditioning.py`, und nicht mehr mit einer gewichteten Summe. Damit wirkt dort allein das Verhältnis der Gewichte, und die Normalisierung ist an dieser Stelle abgeschaltet.

**Und entschieden:** An dieser Stelle wird ein negatives Gewicht abgewiesen, statt es zu lesen. Die Bedingung lautet alpha zwischen 0 und 1, und sie ist die Bedingung dafür, dass die Interpolation einen Punkt ZWISCHEN den Begriffen trifft. Darunter dreht sie weiter: sie verlässt den Bogen, steht antiparallel zu einem Begriff und kommt auf ihn zurück, während einzelne Zeilen durch null gehen. Auf dem Regler des Bedienfelds liegt fast die Hälfte der erreichbaren Paare in diesem Bereich, und (1,00, −1,35) gibt den Begriff zurück, den das Minus negieren soll. NOT bleibt die Operation des Denoisers; das Bedienfeld hält den Auslöser an, solange die Stelle „In the embedding" gewählt und ein Begriff negiert ist. Nicht gewählt: den Anteil still auf [0, 1] zu klemmen — das hätte den Regler stehen lassen und etwas anderes gerechnet, als er anzeigt.

**Am selben Tag zurückgenommen:** Der Bereich außerhalb von [0, 1] IST die Nichtlinearität, die Split & Combine ästhetisch interessant machte (Issue #107): von dessen vier Methoden sind zwei die nackte Summe und eine ist dieselbe zeilenweise Slerp, die hier rechnet — unterschieden hat ihn α von −5 bis +5. Die Extrapolation ist damit eine Operation dieses Instruments und keine Abweisung. Zwischenstand dazwischen, ebenfalls zurückgenommen: der Regler endete in dieser Stelle bei 0, weil ein Regelbereich, der eine Warnmeldung verursacht, nicht angeboten wird. Das gilt weiter, und die Warnmeldung ist jetzt weg, weil der Bereich etwas tut. Es bleiben die Abweisungen, die keine Rechnung verstecken: ein nicht endliches Gewicht, ein leerer Satz, und Gewichte, die sich exakt aufheben.

**Begründung:** Zwei Richtungen zu je 0,5 ergeben einen kürzeren Vektor, und zwar in genau den Zeilen, in denen sich die Begriffe unterscheiden — bei zwei kurzen Prompts sind das zwei von 589. Encoder Fusion hat dieselbe Geometrie bereits beantwortet: `_fusion_weights` hält in der Mitte seines Bandes beide Lesarten auf 1 statt auf je 0,5, `slerp_tokens` dreht die Richtung und führt die Länge zwischen den Anker-Längen. Eine zweite Fassung dieser Arithmetik wäre die parallele Struktur, die `docs/ELEMENT_STRUCTURE_REGISTRY.md` verbietet; die Node lädt die vorhandene.

**Nicht gewählt:** die beiden Tokenfolgen aneinanderzuhängen (ComfyUIs `ConditioningConcat`) statt zwischen ihnen zu interpolieren. Das wäre die andere Antwort auf dieselbe Beobachtung gewesen; gewählt ist die in Encoder Fusion vorhandene Korrektur.

**Zur Vorgeschichte:** Das am 2025-11-24 entfallene Split & Combine rief `ai4artsed_conditioning_fusion` mit vier Methoden (`linear`, `spherical`, `multi_step`, `latent_aware`) und α von −5 bis +5; sein Graph fütterte SD 3.5 über `DualCLIPLoader` ohne CLIP-L und ohne festgenagelte T5-Länge. Nur seine Voreinstellung `linear` ist die nackte Summe. Der Eintrag vom 2026-09-26 stellt es als dieselbe Operation dar; das ist zu eng.

**Betroffen:** `comfyui_nodes/ai4artsed_composable_diffusion.py`, `devserver/schemas/chunks/output_image_composable_diffusion_comfyui.py`, `public/ai4artsed-frontend/src/views/latent_lab/composable_diffusion.vue`, `src/i18n/en.ts`, `src/i18n/WORK_ORDERS.md`.

---

## 2026-09-26: Die zweite Zusammenführungsstelle ist ein Feld in Composable Diffusion, kein zweites Instrument

**Korrektur am 2026-09-27:** Die Bildergebnisse haben mit dem alten Split & Combine nichts zu tun, auch wenn sie für sich interessant sind und bleiben. Die Zuschreibung oben ist falsch: der geöffnete Wertebereich stellt Split & Combine nicht wieder her. Der alte Graph (`archive/legacy_docs/workflows_legacy/vector/ai4artsed_SplitAndCombine{Linear,Spherical}_2507021805.json`) lädt einen eigenen `CLIPLoader` für `clip_l.safetensors` und einen `DualCLIPLoader` mit `clip_g.safetensors` und **`t5xxl_enconly.safetensors`**, ohne festgenagelte T5-Länge; heute lädt der Graph einen `TripleCLIPLoader` über `SD35_TEXT_ENCODERS` und nagelt die T5-Länge auf `T5_LENGTH` fest. Die Tabelle, zwischen der der alte Knoten interpoliert hat, ist damit ein anderes Objekt — andere T5-Gewichte, andere Verdrahtung von CLIP-L, andere Stromlänge —, und α ist nur einer von mehreren Unterschieden. Die Extrapolation bleibt, als das, was sie ist; was den alten Bildern entspricht, ist offen (Issue #107 wieder geöffnet).

**In der Umsetzung festgelegt**, auf die Frage nach dem Zusammenhang zwischen Composable Diffusion und dem entfallenen Split & Combine.

Dieselben Begriffe lassen sich an zwei Stellen zusammenführen: im Embedding, vor dem Lauf (das war Split & Combine, Config am 2025-11-24 mit `e64ce909` entfallen), oder im Denoiser, bei jedem Schritt (das ist Composable Diffusion, Liu et al. 2022, Eq. 11/15). Das Ergebnis unterscheidet sich, die Operation nicht.

**Entschieden:** Die Stelle ist ein Feld in Composable Diffusion (`combine_at`: `score` | `conditioning`), nicht ein wiederbelebtes eigenes Instrument. Ein zweites Instrument mit derselben Eingabe, denselben Gewichten und demselben Bild wäre die parallele Struktur, die `docs/ELEMENT_STRUCTURE_REGISTRY.md` verbietet; und der Vergleich, um den es geht, verlangt dieselben Begriffe, dieselben Gewichte und denselben Seed — zwei Flächen hätten das auseinandergezogen.

**Die Gewichte werden an beiden Stellen gleich gelesen** (`_read_weights`): normalisiert als Anteile, sobald ein Gewicht negativ ist einzeln. Was sie skalieren, unterscheidet sich mit der Stelle — im Denoiser die Führungsstärke jeder Vorhersage, im Embedding den Betrag jedes Conditionings.

**Der Diffusers-Zwilling bleibt bei der einen Stelle.** `output_image_composable_diffusion_diffusers.py` rechnet weiter im Score-Raum und weist `combine_at=conditioning` mit Verweis auf die ComfyUI-Config ab, statt die zweite Stelle ein zweites Mal zu implementieren.

**Betroffen:** `comfyui_nodes/ai4artsed_composable_diffusion.py`, `devserver/schemas/chunks/output_image_composable_diffusion_comfyui.py` und `..._diffusers.py`, `devserver/schemas/engine/comfyui_chunk_support.py` (`node_accepts`), `devserver/my_app/routes/schema_pipeline_routes.py`, `public/ai4artsed-frontend/src/views/latent_lab/composable_diffusion.vue`, `src/i18n/en.ts`, `devserver/tests/test_own_comfyui_nodes.py`.

---

## 2026-09-26: Die drei Sätze, die den Kontextsatz und den Elemente-Absatz verlangten, sind aus der Meta-Anweisung gestrichen

**Anlass:** Die Wiederherstellung vom 07.09.2026 sollte einen funktionierenden Meta-Prompt
zurückbringen; die drei Sätze und die Tippfehler gehörten nicht dazu.

Gestrichen sind in `_RESTORED_1103` (`devserver/schemas/engine/instruction_selector.py`,
`12bf0a3f`) drei Sätze und mit ihnen die Tippfehler, die in ihnen standen:

- „Explicitely communicate the Context as cultural cf. artistic. cf intervening context.“
- „Mention the Context als cultural, cf. artistic, c.f intervening context in your OUTPUT
  explicitely.“
- „In your output, communicate which elements are most important for an succeeding media
  generation.“

Alles andere der Fassung vom 07.09.2026 steht wie wiederhergestellt, auch die Frage „how
should it be translated into media?“. Die Aufgaben-Anweisung ist Zeichen für Zeichen die des
Arms ohne die drei Sätze im A/B-Test vom selben Tag (`ai4artsed_research`,
`studies/2026-09_meta_anweisung_drei_saetze/`). Dort schrieben GLM 5.3 und Gemini 3.7 Flash
mit den Sätzen in 23 von 24 und 8 von 8 Texten einen Satz, der den Kontext als kulturellen,
künstlerischen und eingreifenden Kontext benennt, oder einen Absatz zu den für die
Generierung wichtigsten Elementen, ohne die Sätze in keinem der 32 Texte.

Die Anordnung vom 07.09.2026 nannte drei andere Stellen des Textes. Die Wiederherstellung hat den
Text Byte für Byte abgeschrieben und damit auch die drei Sätze zurückgeholt; im Eintrag vom
07.09.2026 unten sind drei Stellen berichtigt.

---

## 2026-09-23: Gemini 3 Pro Image bleibt auf Mammouth AI; ohne Schlüssel oder Guthaben ist es im Flow und in der Modellauswahl von fünf Instrumenten aus

**Anlass:** Bilder mit Gemini 3 Pro Image ließen sich erzeugen,
während „Mistral AI“ als externer LLM-Anbieter eingestellt war. Der Weg des Modells steht fest
im Chunk (`schemas/chunks/output_image_gemini_3_pro.json`, Anbieter `mammouth`) und folgt der
Einstellung nicht. Der Weg über Mammouth AI ist die DSGVO-Lösung der Plattform für dieses
Modell, und die Einstellungen zeigten das nirgends; aktiv sein kann das Modell nur, wenn auch
ein Schlüssel vorhanden ist. Eine eigene Einstellung für dieses Frontier-Bildmodell mit
Anbieterauswahl ist zu kompliziert; sie steht als Issue #100.

**Entschieden.**
- In den Einstellungen steht nur ein Hinweis aus vier Zeilen, mit dem vorgegebenen Wortlaut
  „externes Frontier-Bildmodell: Gemini 3 Pro image“ (fest), „Provider: Mammouth.ai“ (fest),
  „API-Key vorhanden“ (Wert) und „Kontostand Mamouth.ai“ (Wert).
- Ist kein Schlüssel vorhanden, ist das Modell aus, ohne Erläuterung; allenfalls ein Hover
  mit dem vorgegebenen Satz „Kein Mammouth Konto oder keine Credits vorhanden“.
- Die Mammouth-Abrechnung im Reiter „API-Verwaltung“ zeigte unter „Aktueller Verbrauch“ die
  Ausgaben des Kontos, also den Verbrauch über alle Mammouth-API-Schlüssel und nicht den
  dieser Installation (2026-09-26).
- Die Umsetzung hatte Mammouth AI an vier Stellen fest im Code geführt, gegen das
  Hardcoding-Verbot: in der Prüfung des Kontos, in der Route und im Abschnitt der
  Mammouth-Abrechnung des Reiters „API-Verwaltung“, in den Werten der Zeilen in den
  Einstellungen und im Text der Beschriftung „Kontostand“ und des Hover-Satzes. Seitdem ist
  sie aus der Konfiguration gebaut (unten, letzter Punkt vor „Offen“).

**In der Umsetzung festgelegt.**
- Drei Schreibungen der Vorgabe sind berichtigt: „externes“, „Gemini 3 Pro image“ und
  „Mamouth.ai“. Deutsch stehen die Zeilen und der Hover-Satz nach der Übersetzung
  (WO-2026-09-23-A), bis dahin englisch.
- Aus ist das Modell auch ohne Guthaben, wie der Hover-Satz es nennt („keine Credits“).
- Die Zeilen stehen im Reiter „Konfiguration“, Tabelle „API-Konfiguration“, unter den
  Schlüsselfeldern. „API-Key vorhanden“ zeigt ✓ oder —, und zwar nur, ob ein Schlüssel
  vorliegt: ein Schlüssel, den Mammouth AI abweist, zeigt ✓, und die Ablehnung steht dann
  in der Zeile des Kontostands, etwa „HTTP 401 (auth_error)“. Die Zeile des Kontostands
  zeigt das Guthaben des Kontos als Betrag, „Unbegrenzt“ für ein Konto ohne Budget, — ohne
  Schlüssel, und die Ursache, wo der Kontostand nicht gelesen werden konnte: den HTTP-Status,
  mit dem Namen der Ablehnung, wo der Proxy einen nennt, „timeout“, den Namen einer Ausnahme
  oder einen englischen Satz des Servers. Hat die Prüfung eines der drei Budgets, die sie
  beurteilt, aufgebraucht gefunden, steht hinter dem Betrag, bei einem Konto ohne Budget an
  Stelle von „Unbegrenzt“, welches: das des Kontos, das eigene des Schlüssels oder das seines
  Teams. Das Guthaben des Kontos kann über null stehen, während das Budget des Schlüssels
  oder seines Teams verbraucht ist. Scheitert die Abfrage dieser Zeilen
  (`/api/settings/frontier-image-accounts`) selbst, steht an ihrer Stelle eine Zeile
  „Externes Frontier-Bildmodell“ mit „Abrechnungsdaten konnten nicht abgerufen werden“ und
  ihrem HTTP-Status oder der Meldung des Browsers.
- Aus ist das Modell im Flow und in der Modellauswahl („Modelle“ bzw. „Bildmodell“) von
  „Modell-Vergleich“, „Sprachverständnis“, „Stereotypen-Analyse“, „Sprachmodell-Vergleich“ und
  „Ästhetische Pole“. An diesen sechs Stellen trägt es den Hover-Satz, auf vier der fünf
  Instrumente an der Stelle der Karte, die sonst sagt, was das Modell ist. Im Flow steht
  dieselbe Zeile auch als Meldung, wenn ein Lauf das Modell trotzdem verlangt.
- Ein abgeschaltetes Modell verlässt die Auswahl der fünf Instrumente von selbst, wenn sich
  in der Antwort der Verfügbarkeit die Liste `account_missing` ändert, wenn jemand die
  Auswahl ändert, wenn das Instrument gezeigt wird und die Antwort, nach der es dabei fragt,
  da ist oder diese Frage gescheitert ist (dann nach der letzten Antwort, falls es eine gibt),
  und wenn ein Lauf endet; nicht, solange ein anderes Instrument gezeigt wird, die Frage
  aussteht, die es beim Zeigen gestellt hat, oder ein Lauf läuft. Eine
  Änderung des Prompts oder der Sprachen löst das nicht aus. Ein Modell, von dem Bilder auf der
  Fläche stehen, bleibt in der Auswahl; sein Feld bleibt dann, solange kein Lauf läuft, hell
  und trägt den Hover-Satz. Sonst verlässt es eine Mehrfachauswahl, und
  die Bilder der übrigen Modelle bleiben stehen. Eine Auswahl in „Sprachverständnis“ oder
  „Stereotypen-Analyse“, der kein Modell bliebe, geht auf die Modelle zurück, mit denen die
  Fläche öffnet, außer ein gewähltes Modell zeigt dort Bilder. Eine Auswahl im
  Modell-Vergleich, der ein einziges Modell bliebe, geht auf das Set
  „SD-Historie“ zurück, wenn keine Spalte ein Bild zeigt; zeigt eine ein Bild, bleibt das
  Modell gewählt. Auf „Stereotypen-Analyse“ steht ein einziges verbliebenes Modell in fünf
  Zeilen mit je eigenem Seed, wie jedes einzeln gewählte Modell dort; die vier neuen berechnet
  der nächste Lauf. Eine Einzelauswahl („Sprachmodell-Vergleich“, „Ästhetische Pole“) geht auf
  das Modell zurück, mit dem die Fläche öffnet; die Bildspalte zeigt dann dessen Bilder, soweit
  berechnet, und die Texte bleiben stehen. Erreicht ein Lauf ein Modell, das aus ist, schickt
  er es nicht los, und seine Zelle oder Spalte zeigt den Hover-Satz, solange das Modell gewählt
  bleibt. Die Sets des Modell-Vergleichs lassen es aus, und die Notiz eines Sets steht nicht
  da, solange eines seiner Modelle aus ist.
- Starten lässt sich ein Instrument nur, wenn ein Lauf etwas losschickt: im Modell-Vergleich
  mit mindestens zwei Modellen, die an sind, in „Sprachverständnis“ mit einem, in
  „Stereotypen-Analyse“ mit einer offenen Zelle eines Modells, das an ist, in den beiden
  anderen mit einem Text, der noch zu schreiben ist, oder einer offenen Zelle eines Modells,
  das an ist.
- Ohne Schlüssel ist auch ein Schlüssel, den Mammouth AI abweist (401) oder als abgelaufen
  meldet (`expired_key`). Ohne Guthaben heißt: Mammouth AI meldet `budget_exceeded`, oder ein
  Budget, das den Schlüssel bindet und das die Antwort des Kontos nennt, ist aufgebraucht.
  Beurteilt werden davon drei, nach LiteLLMs Hauptzweig (`litellm/proxy/auth/auth_checks.py`,
  gelesen am 2026-09-24): das Budget des Kontos und das eigene Budget des Schlüssels, beide bei
  Ausgaben in Höhe des Budgets oder darüber, und das Budget seines Teams bei Ausgaben darüber.
  Das eigene Budget des Schlüssels ist sein `max_budget` oder das des Budgets, mit dem er
  verknüpft ist, erhöht um eine befristete Erhöhung bis zu ihrem Ablauf. Für einen Schlüssel,
  der zu einem Team gehört, zählt das Budget des Kontos nur auf eigene Einstellung des Proxys
  (`apply_user_budget_to_team_keys`); hier zählt es für ihn nicht, und ebenso wenig für einen
  Schlüssel, der unter den Schlüsseln fehlt, die die Antwort nennt, wie nach einem
  Schlüsseltausch; trägt die Antwort keine Liste der Schlüssel, zählt es. Ein Team, das die
  Antwort nicht nennt, wird nicht beurteilt. Budgets für ein Zeitfenster (`budget_limits`) und
  je Modell (`model_max_budget`), die LiteLLM ebenfalls prüft, bleiben unbeurteilt, ebenso die
  einer Modell-Zugriffsgruppe, einer Organisation, eines Projekts, eines Tags, eines
  Endnutzers und des Proxys und die eines Anbieters oder eines Deployments im Router von
  LiteLLM. Ein Budget, das auf der Mitgliedschaft des Nutzers des Schlüssels in seinem Team
  steht und mit seiner laufenden befristeten Erhöhung über 0 liegt, prüft LiteLLM schon auf
  der Route des Kontos und lehnt sie ab, wenn es aufgebraucht ist (`budget_exceeded`). Ein
  Mitgliedsbudget, das mit seiner laufenden befristeten Erhöhung bei 0 oder darunter liegt,
  und ein Budget, das ein Team für alle seine Mitglieder vorgibt (`team_member_budget_id`),
  prüft LiteLLM auf der Route des Kontos nicht; sie bleiben unbeurteilt. Ein Schlüssel, der
  über sein Budget hinaus
  gedrosselt weiterlaufen darf
  (`throttle_on_budget_exceeded`), zählt hier als aufgebraucht: die Antwort nennt keinen
  Drosselsatz. Die Ausgaben in der Antwort sind die, die LiteLLM zuletzt in seine Datenbank
  geschrieben hat; eine Lesung kann kurz nach dem letzten Cent noch Guthaben zeigen.
- Ein Kontostand, der nicht gelesen werden konnte (Zeitüberschreitung, ein anderer
  HTTP-Status), lässt das Modell an. Ein Lauf gegen ein Konto ohne Guthaben scheitert dann beim
  Anbieter: das Backend meldet „API error: <HTTP-Status>“, der Flow zeigt diesen Text im Hover
  seiner Fehlermeldung. „Modell-Vergleich“, „Sprachverständnis“, „Sprachmodell-Vergleich“ und
  „Ästhetische Pole“ zeigen ihren allgemeinen Fehlersatz, „Stereotypen-Analyse“ den Satz des
  Servers in der Zelle und in „Ein Bild kam nicht an: …“.
- Gelesen wird das Konto (`/user/info`); seine Antwort nennt auch die Schlüssel des Kontos und
  seine Teams, mit ihren Budgets. Der Schlüssel dieser Installation hatte am 2026-09-23 kein
  eigenes Budget: `/key/info` nannte `max_budget`, `budget_id` und `litellm_budget_table` leer.
  Die Einstellungen lasen bis dahin `/key/info` und zeigten keinen Kontostand. Seitdem zeigt
  der Reiter „API-Verwaltung“ (bis zum 2026-09-26 in einem Abschnitt für Mammouth AI, seitdem
  im Block des Anbieters, letzter Punkt vor „Offen“) unter „Budgetlimit“ und „Verbleibend“
  Budget und Kontostand des Kontos, im Balken darunter, wo das Konto ein Budget über 0 hat,
  den Anteil davon, den es ausgegeben hat (höchstens 100 %), und in der Zeile „Ratenlimit“
  das niedrigste RPM- und das niedrigste TPM-Limit von Schlüssel, Konto und Team (das des
  Teams, wo die Antwort es nennt), bis zum 2026-09-26 wo ein RPM-Limit gilt, seitdem jedes
  der beiden nur, wo eines gesetzt ist. Unter „Aktueller Verbrauch“ zeigte er bis zum
  2026-09-26 die Ausgaben des Kontos über alle seine Schlüssel; seitdem zeigt er dort,
  wie oben festgelegt, was der Schlüssel aus der Schlüsseldatei ausgegeben hat, aus seinem Eintrag
  in der Antwort des Kontos, und „Not reported by the provider“ (englisch bis zur
  Übersetzung, WO-2026-09-26-P), wo die Antwort ihn nicht führt oder sein Eintrag keine
  Zahl für seine Ausgaben enthält. Läufe nehmen den Schlüssel aus der Umgebungsvariablen
  `MAMMOUTH_API_KEY` vor dem aus der Datei, wo sie gesetzt ist. LiteLLM setzt die Ausgaben
  eines Schlüssels auf null, wenn ein eigener Budgetzeitraum des Schlüssels neu beginnt; der
  Schlüssel dieser Installation hatte am 2026-09-26 wie das Konto den Zeitraum `30d` mit dem
  nächsten Neubeginn am 2026-10-01.
- Die Verfügbarkeit hält eine Lesung des Kontos fünf Minuten, solange der Schlüssel derselbe
  bleibt; ein anderer Schlüssel wird bei der nächsten Frage gelesen, der alte ebenso, wenn er
  zurückkommt. Eine Lesung läuft zur Zeit. `?force_refresh=true` an
  `/api/models/availability` lässt diese Lesung stehen: jeder kann es senden, und es soll den
  Server nicht dazu bringen, Mammouth AI mit dem Schlüssel der Installation nach Belieben
  abzufragen. Die Zeilen in den Einstellungen lesen frisch, und die Verfügbarkeit übernimmt
  diese Lesung. Frisch liest auch der Reiter „API-Verwaltung“; beide Routen stehen hinter der
  Anmeldung der Einstellungen.
- Seit dem 2026-09-26 nennt diese Umsetzung im Code kein Modell mehr und einen Anbieter nur
  noch als eine von zwei Schnittstellen, über die ein Konto gelesen wird. Welche davon für
  einen Anbieter gilt und unter welcher Adresse, nennt sein Eintrag in
  `config/llm_providers.json`: `account_api` ist `litellm` für die Kontoroute eines
  LiteLLM-Proxys, die Mammouth AI beantwortet (Adresse `credits_url`), und `openrouter` für
  zwei Routen von OpenRouter: die des Schlüssels, die meldet, was er im laufenden Monat (UTC)
  ausgegeben hat (`key_url`), und die des Guthabens (`credits_url`), die OpenRouter nach
  seiner API-Referenz (gelesen am 2026-09-26) nur einem Verwaltungsschlüssel beantwortet;
  dem Schlüssel dieser Installation, den die Route des Schlüssels mit `is_management_key`
  false führt, hat sie am 2026-09-26 auf dem EU-Host geantwortet. Verweigert sie dem
  Schlüssel das Guthaben, steht ihre Antwort im Teil des Kontos. Beurteilt wird nur eine
  LiteLLM-Lesung. Die Zeilen in den Einstellungen gelten jeder Ausgabe-Config, deren `meta`
  sie als `frontier_image` markiert (heute `gemini_3_pro_image`), unter dem Namen der Config
  und mit dem Anbieter, den ihr Chunk nennt; die Zeile des Kontostands steht nur, wo die
  Prüfung das Konto dieses Anbieters beurteilt. Nennt der Chunk keinen Anbieter, steht in der
  Zeile „Provider“ der Satz der Route, der das sagt. Die Beschriftung des Kontostands und der
  Hover-Satz tragen den Anbieternamen als Platzhalter; eingesetzt wird die Schreibung aus
  `src/data/providers.ts`. Englisch steht deshalb „Mammouth AI“, wo „Mammouth.ai“ und
  „Mammouth“ standen, und als Modell „Gemini 3 Pro Image (€)“, der Name der Config. Deutsch
  und in den anderen Sprachen stehen bis zur Übersetzung (WO-2026-09-26-P) die Fassungen aus
  WO-2026-09-23-A mit „Mammouth.ai“ und „Mammouth“ als festem Text. Der Reiter
  „API-Verwaltung“ zeigt einen Block je Anbieter, dessen Schlüsseldatei einen Schlüssel hält,
  unter dem Namen des Anbieters und in zwei Teilen (englisch bis zur Übersetzung,
  WO-2026-09-26-P). „Installation“ zeigt, was der Schlüssel aus der Schlüsseldatei
  ausgegeben hat, den „Budget-Reset“ seines eigenen Budgetzeitraums, wo er einen hat, und
  das „Ratenlimit“, unter dem er läuft, wo die Antwort eines LiteLLM-Kontos eines nennt: das
  niedrigste von Schlüssel, Konto und Team. „Account (all keys)“ zeigt Budgetlimit,
  Verbleibend, Balken und „Budget-Reset“ des Kontos, soweit der Anbieter sie meldet.
  „Not reported by the provider“ steht an Stelle des Verbrauchs des Schlüssels, wo der
  Anbieter ihn nicht meldet, auch für einen Schlüssel, den die Antwort eines LiteLLM-Kontos
  nicht unter seinen Schlüsseln führt, und an Stelle des ganzen Teils „Account (all keys)“,
  wo der Anbieter weder Budget noch Guthaben meldet. Eine Zeile, deren Wert er nicht meldet,
  fehlt; „Verbleibend“ zeigt „—“, wo die Lesung kein Guthaben beziffert, etwa bei einem Konto
  ohne Budget.

**Offen.**
- Ob der Hover-Satz über den Hover hinaus stehen soll: als Meldung eines Laufs im Flow und in der
  Zelle oder Spalte, für die ein Lauf das Modell auslässt. Die Vorgabe sieht ihn allenfalls im
  Hover vor. `docs/COPY_RULES.md` verlangt auf Vergleichsflächen, dass ein Bild, das nicht
  ankommt, das in einer Zeile sagt, und dass die Meldung die echte Ursache trägt; der Hover-Satz
  nennt zwei Ursachen zur Wahl. Für den Flow sagt die Regel nichts. Nicht entschieden.
- Ob ein Kontostand, der nicht gelesen werden konnte, das Modell ausschalten soll: heute bleibt
  es an. Nicht entschieden.
- Die Fläche zeigt die Namen aus den Daten und damit nicht die Schreibung der Vorgabe: als Modell
  „Gemini 3 Pro Image (€)“, den Namen der Config, wo die Vorgabe „Gemini 3 Pro image“ schrieb, und
  „Mammouth AI“ (`src/data/providers.ts`) in der Zeile „Provider“, wo sie „Mammouth.ai“
  schrieb; ebenso in der Beschriftung des Kontostands, wo sie „Mammouth.ai“ schrieb, und im
  Hover-Satz, wo sie „Mammouth“ schrieb, englisch schon jetzt, in den anderen Sprachen nach
  der Übersetzung (WO-2026-09-26-P). Ob einer dieser Namen in den Daten geändert wird, ist
  nicht entschieden.
- Resona auf „Together“ (`generate_media`, `services/tool_registry.py`), die Persona auf „Ideen
  testen“ (`views/ai_persona.vue`) und „Canvas Workflow“ (`/api/canvas/output-configs`,
  `services/canvas_graph_authoring.py`) führen das Modell weiter; sie lesen die Verfügbarkeit
  nicht.

**Betroffen:** `my_app/services/provider_account.py` (neu), `tests/test_provider_account.py` (neu),
`my_app/services/model_availability_service.py`, `my_app/routes/config_routes.py`
(`account_missing`, `account_provider`), `my_app/routes/settings_routes.py`
(`/frontier-image-accounts`, bis zum 2026-09-26 `/config-account/<config_id>`; der Reiter
„API-Verwaltung“ liest die Konten), `config/llm_providers.json`,
`schemas/configs/output/gemini_3_pro_image.json`, `composables/useModelAvailability.ts` (neu),
`composables/useInterceptionSeries.ts`, `composables/useRasterRun.ts`, `services/api.ts`,
`tests/test_llm_providers.py`, `views/x2x_flow.vue`,
`views/SettingsView.vue`, `components/ApiManagementTab.vue`, die fünf Instrumente mit
Modellauswahl und `latent_lab/mean_images.vue`, `i18n/en.ts` und `i18n/WORK_ORDERS.md`
(WO-2026-09-23-A, WO-2026-09-26-P), `docs/ARCHITECTURE PART 08 - Backend-Routing.md`,
`docs/ELEMENT_STRUCTURE_REGISTRY.md` (`ChipSelect`).

---

## 2026-09-23 (abends): Plätze mit eigenen Codes ersetzen Kursschlüssel, Teilnahmeliste und Beitrittscode

**Anlass:** Plätze mit eigenen Codes treten an die Stelle von Kursschlüssel, Teilnahmeliste und
Beitrittscode. Gewählt sind vier Dinge:
- Kursseite, Druckzettel, Anmeldung per Code und Kurskarte werden gebaut wie skizziert, mit Wortlaut und mit dem Hinweis zur Verantwortung der Einrichtung.
- Ein Code ist nur beim Erzeugen sichtbar; gespeichert wird ein Hashwert.
- Die Benutzer- und Anzeigenamen bestehender Teilnehmenden-Konten werden beim nächsten Serverstart entfernt, erst auf dev, später auf prod.
- Resonas Kurszeile nennt „N places".

Ein fünfstelliger Code gilt als sicher genug.

**1. Der Platz.** Ein Platz ist eine Mitgliedschaft (`course_memberships`) mit drei Angaben:
- einer Nummer (`place_number`), die je Kurs fortläuft,
- dem Hash seines Codes (`code_hash`), eindeutig in der ganzen Installation,
- dem Zeitpunkt, zu dem der Code ausgegeben wurde (`code_issued_at`).

Sein Konto hat die Rolle `participant` und weder E-Mail noch Benutzernamen noch Anzeigenamen. Wie die Einrichtung ihre Codes verteilt, bleibt ihre Sache.

Auf der Kursseite gibt die Leitung eine Anzahl an Geräten an (1 bis 100 je Anfrage). Die Plattform legt so viele Plätze an und zeigt jeden Code einmal, zum Kopieren und zum Drucken. Die Nummern setzen nach der höchsten fort, die der Kurs je hatte, also geht keine Nummer an ein zweites Gerät. „Code ersetzen" gibt einem Platz einen neuen Code, und der alte gilt ab sofort nicht mehr.

**2. Der Code.** Ein Code hat fünf Zeichen aus 25 (`ACDEFGHJKMNPQRTUVWXY34679`), das ergibt 9.765.625 Möglichkeiten. Die verwechselbaren Zeichen 0/O, 1/I/L, 2/Z, 5/S und 8/B fehlen im Alphabet. Bei der Eingabe zählen die Buchstaben und Ziffern nach dem Doppelpunkt, in beliebiger Schreibung (`place_codes.normalise_code`); so nimmt die Anmeldung auch eine kopierte Zeile „Place 3: K7M3Q". Eine Eingabe aus mehreren Zeilen, etwa die ganze kopierte Liste, und eine Zeile mit zwei Doppelpunkten lassen niemanden ein: beide hätten den Platz betreten, dessen Code am Ende steht.

Gespeichert ist der SHA-256 des Codes, ohne Salz. So findet die Anmeldung den Platz aus dem Code allein; mit einem gesalzenen Hash, wie ihn der Kursschlüssel hatte, müsste jede Anmeldung gegen jeden Platz rechnen. Wer die Datenbankdatei besitzt, rechnet jeden Code in Sekunden zurück. Die Anmeldung zählt keine Fehlversuche. Zwei Geräte mit demselben Code sind zugelassen (Konzept vom 17.08., „Offen").

**3. Das Zugangsfenster.** Die Codes eines Kurses gelten bis `courses.access_until`. Den Zeitpunkt setzt die Leitung („Zugang bis", „Ändern"), und sie kann den Zugang jederzeit beenden („Zugang beenden"). Ohne gesetzten Zeitpunkt ist der Kurs geschlossen, ebenso wenn er archiviert ist. Der Zeitpunkt muss in der Zukunft liegen und eine Zeitzone tragen; gespeichert wird er in UTC.

**4. Die Sitzung eines Platzes.** Vor jeder Anfrage an `/api/` prüft die Plattform die Sitzung neu, einmal je Anfrage (`auth_service.check_place_session`). Weil die Prüfung vor der Antwort läuft, trägt auch eine gestreamte Antwort (Resonas Chat, der Ereignisstrom der Prompt Interception) ein Ende im Cookie. Die Sitzung gilt, solange alles Folgende zutrifft:
- der Platz besteht, ist aktiv und gehört zu Konto und Kurs der Sitzung,
- er trägt noch den Code, mit dem die Sitzung eintrat,
- sein Kurs besteht und ist offen,
- sein Konto ist aktiv und ein Teilnehmenden-Konto.

Trifft eine Bedingung nicht mehr zu, endet die Sitzung. Konto, Platz und ein Einstellungs-Login fallen weg; den Kurs behält die Sitzung. Das Gerät bleibt damit bis zur Abmeldung unter der Sicherheitsstufe des Kurses. Das folgt aus der Regel, nach der ein Kurs die Stufe nur anzieht (`services/safety_level_resolver.py`): unter dem Kursschlüssel blieb eine Sitzung bis zu ihrem Ablauf im Kurs.

Die Stufe eines Kurses gilt nur in einer Sitzung, die diesen Kurs betreten hat. SQLite gibt die Nummer des jüngsten Kurses nach dessen Löschung an den nächsten neuen Kurs (`courses.id` hat kein AUTOINCREMENT). Deshalb merkt sich die Sitzung beim Eintritt auch den Zeitpunkt, zu dem ihr Kurs angelegt wurde (`place_codes.course_stamp`). Die strengste Stufe gilt, wenn der Kurs gelöscht ist, wenn unter seiner Nummer ein anderer Kurs steht oder wenn die Sitzung keinen solchen Zeitpunkt trägt. Den Zeitpunkt trägt keine Teilnehmenden-Sitzung aus der Zeit vor den Plätzen. Eine solche Sitzung endet bei ihrer nächsten Anfrage und steht bis zur Abmeldung auf der strengsten Stufe.

Dasselbe gilt für die Nummern der Konten (`users.id`). Deshalb merkt sich jede Anmeldung auch den Zeitpunkt, zu dem ihr Konto angelegt wurde (`auth_service._account_stamp`). Steht unter der Nummer der Sitzung ein anderes Konto, endet die Sitzung (`auth_service.current_user`); sonst ginge die Sitzung eines gelöschten Kontos auf das nächste neue über. Eine Sitzung, die vor diesem Vermerk angemeldet wurde, bekommt ihn bei ihrer nächsten Anfrage, von dem Konto, das dann unter ihrer Nummer steht.

Scheitert die Prüfung selbst, bedient die Plattform diese Anfrage ohne Konto und unter der Stufe des Kurses, und die nächste Anfrage prüft wieder. Eine Sitzung, die das Konto eines Platzes hält, ohne den Platz betreten zu haben, endet ebenfalls (`auth_service.current_user`). Eine Anmeldung der Kursleitung im selben Browser nimmt der Sitzung den Kurs.

Eine Perspektive, die einem anderen Konto gehört und in einer Kurspalette steht, setzt die Plattform nur in einer Sitzung dieses Kurses ein, für einen aktiven Platz oder eine Kursleitung (`services/course_prompt_resolver.py`). Eine Mitgliedschaft ohne Platznummer gewährt keinen Zugang zum Kurs.

**5. Die Wanderung.** Sie läuft beim ersten Start einer älteren Datei, einmal, in einer Transaktion (`lab/db.py`, `_migrate_places`). Die Datei vermerkt sie in `PRAGMA user_version = 1`. Sie betrifft jedes Konto mit der Rolle `participant`, das keinen Kurs leitet:
- Steht ein solches Konto auf den Listen mehrerer Kurse, wird es geteilt. Das Konto bleibt in dem noch laufenden Kurs, dem es zuletzt beigetreten ist (aktive Mitgliedschaft, Kurs nicht archiviert), und behält, was es außerhalb eines Kurses gemacht hat. Jede weitere Mitgliedschaft geht an ein eigenes namenloses Konto, mit den Arbeiten, Prompt-Entwürfen und LoRA-Adaptern aus diesem Kurs und mit einer Kopie jeder Perspektive des Kontos samt ihren Versionen. Ein Eintrag der Kurspalette, der eine dieser Perspektiven nennt, nennt danach die Kopie.
- Das Konto verliert Benutzernamen, Anzeigenamen und E-Mail. `secure_delete` überschreibt die alten Werte in der Datei.
- Ein deaktiviertes Konto wird kein Platz: seine aktiven Mitgliedschaften gelten als entfernt.
- Jede Mitgliedschaft eines solchen Kontos wird ein Platz mit Nummer, je Kurs in der Reihenfolge des Beitritts. Entfernte Mitgliedschaften bekommen ebenfalls eine Nummer, damit diese an kein anderes Gerät geht.

Danach baut die Plattform die Datei einmal neu auf (`VACUUM`, vermerkt in `user_version = 2`). Solange `secure_delete` aus war, ließ ein gelöschtes Konto seine Zeile samt Namen in einer freien Seite der Datei stehen; ebenso stehen dort die Werte der entfallenen Spalten des Kursschlüssels. Danach schreibt ein Checkpoint das Write-Ahead-Log in die Datei zurück und kürzt es (vermerkt in `user_version = 3`); bis dahin hält die Datei die Seiten, die das Log ersetzt hat, und das Log seine Einträge von vor den Plätzen. Findet der Checkpoint einen Leser, versucht es der nächste Start wieder. Ein späterer Start nimmt keinen eigenen Checkpoint: einer, der einen Leser findet, wartet auf ihn und hält derweil die Schreibzugriffe jedes anderen Prozesses auf.

Die Spalten des Kursschlüssels und `join_code` entfallen. Übernommene Kurse sind geschlossen. Ein übernommener Platz hat keinen Code, bis die Leitung ihm einen gibt. Ein Konto mit der Rolle `participant`, das einen Kurs leitet, behält seinen Namen und wird kein Platz. Scheitert die Wanderung, schreibt sie eine Warnung ins Log, und der nächste Start versucht es wieder.

**6. Die Verwaltung.** Die Benutzerverwaltung der Administration ändert und löscht kein Konto, das einen Platz hält, also eine Mitgliedschaft mit Nummer, und macht kein Konto zu einem Teilnehmenden-Konto. Ein Platz wird in seinem Kurs verwaltet. Ein Konto mit der Rolle `participant` ohne Platz, das einen Kurs leitet, etwa eine von Hand herabgestufte Kursleitung aus der Zeit vor den Plätzen, bleibt in der Hand der Administration. Ein Konto mit der Rolle `participant`, das weder einen Platz hält noch einen Kurs leitet, kann die Administration nur löschen: die Wanderung hat ihm die Namen genommen, und keines seiner Felder soll wieder einen aufnehmen. Wird ein Konto gelöscht, verlieren die Konten, die es angelegt hat, den Verweis darauf (`users.created_by`); sonst hielten die Plätze einer Kursleitung deren Löschung auf. Ebenso verlieren die Versionen fremder Perspektiven, die es geschrieben hat, ihren Verfasser (`prompt_versions.created_by`); eine solche Version schreibt die Administration mit jeder Änderung an der Perspektive eines anderen Kontos. Ein Konto mit der Rolle `participant` leitet keinen Kurs, auch wenn es eine Zeile in `course_educators` trägt. Eine Zahl im Pfad über dem größten Wert von SQLites INTEGER beantwortet die App auf allen Routen mit 404 (`utils/url_ids.py`); an eine Abfrage gebunden ergab sie einen OverflowError und damit eine 500. Die Nummer einer weiteren Kursleitung (`user_id`) muss eine ganze Zahl in diesem Bereich sein.

**Betroffene Dateien:**
- `devserver/my_app/lab/place_codes.py` (vormals `course_access_key.py`), `lab/models.py`, `lab/db.py`, `lab/auth_service.py`,
- `my_app/__init__.py`, `utils/url_ids.py`,
- `routes/auth_routes.py`, `routes/courses_routes.py`, `routes/admin_users_routes.py`, `routes/chat_routes.py`,
- `services/safety_level_resolver.py`, `services/course_prompt_resolver.py`,
- `views/LoginView.vue`, `views/educator/CourseEditor.vue`, `views/educator/EducatorDashboard.vue`, `stores/labAuth.ts`, `services/labApi.ts`.

Die Testsuite legt ihre Datenbank in ein eigenes temporäres Verzeichnis (`devserver/tests/conftest.py`). Ohne diese Umleitung führte jeder Test, der die App baut, die Wanderung auf `devserver/var/lab.db` des Checkouts aus, auf dem Entwicklungsserver also auf der Datei des laufenden Backends. Ein Testlauf, der keine eigene Datei nennt (`AI4ARTSED_DB_PATH`), bricht beim Import von `lab/db.py` ab, bevor er diese Datei bindet; pytest setzt dafür `PYTEST_VERSION`.

**Offen:**
- Die Anmeldung setzt Fehlversuchen keine Grenze.
- Die Wanderung lässt sich nicht rückgängig machen.
- „Code ersetzen" fragt nicht nach.
- Überzählige Plätze lassen sich nicht entfernen.
- Die Oberfläche bemerkt eine beendete Sitzung erst beim Neuladen.
- Die Kontoseite zeigt für einen Platz „user#N".
- `devserver/testfiles/test_metadata_api.py` liegt außerhalb von `tests/` und bricht unter pytest ohne `AI4ARTSED_DB_PATH` jetzt beim Import ab.
- Das Löschen eines Kurses löscht mit den Konten seiner Plätze auch die Perspektiven, die an diesen Plätzen angelegt wurden; der Löschdialog zählt sie nicht mit.

## 2026-09-23: Teilnehmende besitzen eigene Presets, und beim Teilen steht die Platznummer

**Anlass:** Die Konzeptpapiere vom 15. und 17.08. ließen offen, ob Teilnehmende eigene Presets
besitzen und bearbeiten dürfen und welcher Absender beim Teilen steht. Teilnehmende besitzen
und bearbeiten eigene Presets; Absender ist die Platznummer, denn auf der Plattform liegen
keine personenbezogenen Daten, und Geräte sind keine Personen.

**1. Eigene Presets.** Teilnehmende besitzen und bearbeiten eigene Presets. Das
Behalten ist seit dem 2026-08-15 für jede angemeldete Person gebaut (Eintrag „Eigene
Perspektiven behalten (P3)"). Folge im Kursmodell vom 17.08.: angemeldet ist ein Platz, also
gehören die Presets dem Platz. Weiter offen ist Punkt 5 jenes Eintrags: ob Teilnehmende den
Wortlaut einer Perspektive lesen und ändern, die ihre Leitung behalten und in den Kurs gelegt
hat.

**2. Absender beim Teilen.** Was im Kurs geteilt wird, trägt die Nummer des Platzes. Auf der
Plattform liegen keinerlei personenbezogene Daten. Für Schritt 4 des Galerie-Plans („das steht
danach unter deinem Namen im Kurs") gilt damit das Kursmodell vom 17.08.: ein Platz ist eine
Nummer und ein Code.

**Folge für den Bau:** Die Teilnahmeliste mit Benutzername und Anzeigename wird durch die Plätze
ersetzt. Namen von Teilnehmenden, die in einer bestehenden Datenbank stehen, entfernt die
Wanderung.

**Offen:** Konten von Kursleitungen tragen eine E-Mail-Adresse (Pflichtfeld beim Anlegen) und
einen Anzeigenamen, und das Kurskonzept vom 17.08. behandelt die Kursleitung als betroffene
Person mit Einverständnis und Widerruf. Ob „keinerlei personenbezogene Daten" diese Konten
einschließt, ist nicht entschieden.

---

## 2026-09-22: Welches Modell ein LoRA trägt, steht in der Adapter-Datei — nicht im Register

**Anlass:** Die Spalte „Models“ im Reiter „LoRAs“ der Einstellungen war eine
Reihe Kästchen über alle Bild-Configs mit Checkpoint-Lader, und ein falsches Kreuz legt einen
Adapter in einen Workflow, für den er nicht trainiert wurde, also genau der Fehler, für den das
Register am 21.09. gebaut worden war. Welches Modell ein Adapter trägt, steht in seinen
Metadaten und ist keine Konfigurationseinstellung, die Nutzende setzen.

**Entschieden.** Die Spalte `lora_adapters.base_configs` entfällt. Was ein Adapter trägt, liest
`my_app/services/lora_base.py` aus dem Kopf der safetensors-Datei: `modelspec.architecture` der
SAI-Modellspezifikation, die jedes sd-scripts-Training dieser Stelle schreibt (mit `/lora` am
Ende), sonst das Trainer-Feld `ss_base_model_version`, sonst nichts. Die Ausgabe-Config nennt in
`meta.lora_base` die Schreibweisen, die sie fährt; `lora_register.configs_for()` verbindet beides.
Damit bleibt das Vokabular der Modellnamen in den Daten, und eine weitere Basis kommt dazu, indem
jemand liest, was eine solche Datei sagt — nie, indem jemand eine Zeichenkette rät. Nennt eine
Datei nichts, trägt sie kein Modell und wird nirgends angewandt; so sind die Beschleuniger der
Video-Pipelines gebaut, die im selben Ordner liegen.

Gesetzt sind neun Configs, jede mit den Schreibweisen, die ein Trainer wirklich schreibt:

| Config | `meta.lora_base` | woher die Zeichenkette stammt |
|---|---|---|
| `sd35_large`, `sd35_large_diffusers`, `sd35_large_img2img`, `sd35_large_turbo` | `stable-diffusion-3-5-large`, `5-large`, `stable-diffusion-3-5-large-turbo` | gemessen an den Adaptern im Ordner (Spezifikationsfeld und Trainerfeld); `sai_model_spec.py:63` |
| `sdxl`, `commoncanvas_xl_c`, `commoncanvas_xl_c_diffusers` | `stable-diffusion-xl-v1-base`, `sdxl_base_v1-0` | `kohya_ss/sd-scripts/library/sai_model_spec.py:59`, `sdxl_model_util.py:19` |
| `sd15` | `stable-diffusion-v1`, `sd_v1` | `sai_model_spec.py:56`, `model_util.py:1078-1087` |
| `flux2` | `flux2` | gemessen am heruntergeladenen Flux-2-Adapter im Ordner |

Zwei davon stehen auf einer Messung und nicht auf einem Namen. `sd3.5_large` und
`sd3.5_large_turbo` halten dieselben 1167 Tensoren in denselben Formen, ohne eine einzige
Abweichung — ein Adapter des einen passt auf das andere, und beide Configs nennen beide
Schreibweisen. `commoncanvas_xl_c` ist eine echte Teilmenge von `sdxl_base`: von 2515 Tensoren
fehlen zwei Buchführungsschlüssel (`position_ids`, `logit_scale`), sonst nichts — dieselbe
Architektur, also dieselben Adapter. Die beiden Diffusers-Varianten laden dieselben Gewichte über
ein anderes Backend und erben die Basen ihres Zwillings (`CHUNK_META.lora_chunk`).

`flux2_img2img` trägt KEINEN Adapter, obwohl sein Workflow einen Checkpoint-Lader hält. Der Chunk
läuft mit `execution_mode: legacy_workflow`, und `backend_router._process_legacy_workflow` reicht
den Workflow unverändert durch, ohne je einen LoraLoader einzusetzen. Als Träger abgeleitet hätte
er einen Adapter als angewandt gemeldet, dessen Triggerwort vor den Prompt gesetzt und nichts
geladen; `chunk_carries()` liest darum seit dem 22.09. `execution_mode` mit.

Nebenbefund: die vier Plattform-Adapter nannten bis dahin nur `sd35_large` und fehlten in jedem
Bild-zu-Bild-Lauf, obwohl die Datei dasselbe Modell nennt — die Ableitung behebt das (gemessen an
der Datenbank des Dev-Servers am 22.09.; für die Produktion nicht nachgesehen).

**Die Wanderung geht in eine Richtung.** `_drop_columns()` nimmt `base_configs` beim Start aus
einer älteren Datei heraus, und eine Datei, die das hinter sich hat, läuft unter dem Code von
vorher nicht mehr: die Spalte war NOT NULL ohne Vorgabe, `create_all` legt sie nicht nach, und
jede neue Registerzeile würde abgewiesen. Ein Zurück gäbe es nur, indem jemand die Spalte von Hand
wieder anlegt. Das ist in Kauf genommen: die Datenbank des Labors kennt keine Wanderungsverwaltung
(`init_db()` = `create_all` + `_ensure_columns` + `_drop_columns`), sie ist gitignoriert und liegt
je einmal auf Dev und auf Prod, und eine stehengelassene Pflichtspalte hätte dasselbe Problem in
die andere Richtung.

**Affected files:** `devserver/my_app/services/lora_base.py` (neu),
`devserver/my_app/services/lora_register.py`, `devserver/my_app/lab/models.py`,
`devserver/my_app/lab/db.py` (`_DROPPED_COLUMNS`, `_drop_columns`),
`devserver/my_app/routes/lora_routes.py`, `devserver/my_app/services/training_service.py`
(`SD35_LORA_BASE_CONFIGS` gelöscht), `devserver/schemas/configs/output/{sd35_large,
sd35_large_diffusers,sd35_large_img2img,sd35_large_turbo,sdxl,commoncanvas_xl_c,
commoncanvas_xl_c_diffusers,sd15,flux2}.json` (`meta.lora_base` gesetzt) und
`flux2_img2img.json` (wieder entfernt), `devserver/tests/test_lora_register.py`,
`public/ai4artsed-frontend/src/components/LoraRegisterTab.vue`,
`public/ai4artsed-frontend/src/stores/loras.ts`, `public/ai4artsed-frontend/src/i18n/en.ts`,
`public/ai4artsed-frontend/src/i18n/WORK_ORDERS.md` (WO-2026-09-22-G),
`docs/ELEMENT_STRUCTURE_REGISTRY.md`.

---

## 2026-09-19: Der AILit-Abgleich bewertet die Plattform als Werkzeug für die Maßnahmen des Rahmenwerks

**Anlass:** Die Tabelle vom 02.09. bis 19.09.
beurteilte, ob die Plattform selbst die Handlung hervorbringt, die eine Learner Expectation von
Lernenden verlangt, und sprach ihr so Maßnahmen ab, die das Rahmenwerk einer Lehrkraft mit ihrer
Gruppe zuweist („Learners are given a time-bound challenge to produce two versions of the same
product, with and without AI", Manage 3, S. 39). Das bewertet die Plattform als pädagogischen
Akteur; zu beantworten ist, ob, wie und mit welchem Teil die Plattform die Maßnahmen des
Rahmenwerks unterstützt und welches praktische Szenario das belegt.

**Entschieden.** Bezugsgröße sind die 57 Unterrichtsbeispiele („In the Classroom", eines je
Kompetenz und Stufe), wörtlich in `docs/ailit/classroom_scenarios.tsv`. Je Maßnahme sagt
`docs/ailit/unterstuetzung.tsv`, ob ein Teil der Plattform sie trägt (`ja`: wie beschrieben;
`angepasst`: Kernhandlung und Art des Gegenstands bleiben, der Gegenstand ist ersetzt und benannt;
`nein`: mit Grund), welcher Teil, wie, und mit welchem Praxis-Szenario dieser Plattform. Das
Rahmenwerk sieht die Anpassung seiner Beispiele selbst vor (S. 25). Eine Schwelle oder Ampel gibt
es weiterhin nicht; Help nennt zur aktiven Seite die Maßnahmen, die sie trägt, mit Learner
Expectation und Unterrichtsbeispiel im Wortlaut, und sagt, dass eine Kursleitung die Maßnahme
durchführt. Drei Korrekturen vom selben Tag gelten mit: Plattformweites (die
Wartezeit-Anzeige mit den Energiewerten) steht einmal als querliegender Teil und begründet keinen
einzelnen Ort; die als solche bezeichnete Quell-Karte (Wikipedia) im Flow trägt Maßnahmen zur
Prüfung von Rechercheschritten und nichts zur Urheberschaft von Modellausgaben; der Ort Direct ist
deprecated und trägt keine Zeile mehr.

**Ergänzt 2026-09-20.** Die Tabelle geht wie die vorherige von den Instrumenten und
strukturellen Aspekten der Plattform aus; ihr Zweck ist, den Help-Agenten zu informieren.
`docs/ailit/unterstuetzung.tsv` und `docs/AILIT_ZUORDNUNGSTABELLE.{md,tsv}`
stehen seither je Teil der Plattform (Modus, Instrument des Latent Lab, querliegende Funktion) in
der Ordnung der Plattform, darunter die Maßnahmen, die der Teil trägt; die 13 Maßnahmen ohne Teil
schließen die Tabelle ab. Die Zeilen selbst und das, was Help je Seite liest, sind unverändert.

**Ergänzt 2026-09-26.** Beim Durchgang der 57 Unterrichtsbeispiele gegen Resonas Planungs- und
Nachklapp-Situation ist das Kriterium der Zuordnung eng geschrieben: getragen ist eine
Maßnahme, wenn die Plattform den Gegenstand hält, um den die Maßnahme selbst geht; die Vorbereitung
davor und die Nachbesprechung danach liegen vor und hinter jeder Maßnahme, die eine Kursleitung
durchführt, und tragen keine Zeile. Der weite Zuschnitt des ersten Anlaufs (die Plattform liefert
etwas, das die Maßnahme erwähnt) hätte sechs der 13 `nein`-Zeilen gekippt und 20 schon getragenen
Maßnahmen eine Together-Zeile gegeben, Together also 35 der 57 Maßnahmen gebracht statt 4. Gesetzt
sind drei Zeilen: Create 4 Advanced, Manage 3 Advanced, Manage 4 Advanced. Der Beleg der Zeile
Manage 1 Basic nennt jetzt `RESONA_PLANNING_BLOCK`, wo der zitierte Satz steht (chat_routes.py:1001).
`RESONA_NACHKLAPP_BLOCK` ist von der Together-Seite aus nicht erreichbar: `resona.vue` schickt kein
`resona_situation`, und `_derive_resona_situation` liefert 'workshop' oder 'consulting'.

**Affected files:** `docs/ailit/unterstuetzung.tsv` und `docs/ailit/classroom_scenarios.tsv` (neu),
`docs/ailit/learner_expectations.tsv` (Spalte `ksa_en`), `docs/ailit/QUELLE.md`,
`devserver/scripts/build_ailit_support.py` (neu; ersetzt
`build_ailit_coverage.py` und `build_ailit_table.py`, beide gelöscht; `docs/ailit/zuordnungen.tsv`
gelöscht), generiert: `docs/OECD_AILIT_ABDECKUNG.md`, `docs/AILIT_ORTE_ZUORDNUNG.md`,
`docs/AILIT_ZUORDNUNGSTABELLE.{md,tsv}`, `devserver/my_app/knowledge/ailit_coverage.json`,
`knowledge/platform_items.json`; `scripts/build_platform_items.py`, `services/platform_items.py`,
`services/tool_registry.py`, `routes/chat_routes.py`, `tests/test_ailit_help_reach.py` (neu).

---

## 2026-09-19: Die Decomposition ist entfernt — Encoder Fusion, Composable Diffusion, Denoising Archaeology und die Fusion-Werkbank tragen ihre Fragen

**Anlass:** Das Instrument wird neben dem neuen Encoder Fusion nicht mehr gebraucht,
und es ist zu kompliziert und behäbig; es wird entfernt, ohne dass dabei etwas
kaputt geht.

**Entscheidung:** Das Instrument Decomposition (3×3-Interventionsmatrix: je Zelle ein
Alternativprompt über einen der drei Encoder, injiziert als
`alpha · (encode(cell) − encode(source))` allein am Eintrittsblock des Bandes) verlässt
die Plattformoberfläche. Seine vier Fragen stehen auf anderen Instrumenten: der Anteil
eines Encoders am Bild (Encoder Fusion, mit Stummschaltung und gepooltem Vektor, was
die Decomposition nie konnte), ein Alternativtext neben dem Quelltext (Composable
Diffusion), die Zeit im Entrauschen (Denoising Archaeology; die Fusion-Werkbank mit
denselben Schrittbändern) und die Tiefe im Stapel (die Fusion-Werkbank mit denselben
Blockbändern). Die Wahl zwischen CLIP-L, CLIP-G, T5 und allen dreien steht auch auf
Feature Probing und Concept Algebra.

**Was bleibt (Forschungsweg; Forschungswege werden nicht abgebaut):** die Knotenfamilie
`AI4ArtsEdSD3Context*` mit `AI4ArtsEdSD3ContextDelta`, `decomposition_graph` in
`latent_lab_context_graphs.py`, die Route `/api/fusion_workbench/decomposition` (Stufe
`research`), die Route und der Backend-Pfad des GPU-Dienstes
(`/api/diffusers/generate/decomposition`, `generate_image_with_decomposition` in
`diffusers_backend.py`) samt seinem DevServer-Client gleichen Namens in
`services/diffusers_client.py`: der Chunk war dessen einziger Aufrufer, und ohne ihn
wäre die Diffusers-Strecke nur noch von Hand erreichbar. Die Skripte
`devserver/testfiles/test_decomposition*.py` laufen über die ComfyUI-Route.

**Damit erledigt:** der Eintrag vom 2026-08-13 („Die Decomposition wird entkoppelt").
Die Entkopplung ist durch die anderen Instrumente eingelöst, nicht durch einen Umbau
der Seite.

**Affected files:** `public/ai4artsed-frontend/src/views/decomposition.vue` (gelöscht),
`router/index.ts`, `views/latent_lab.vue`, `views/latent_lab/image_lab.vue`,
`views/latent_lab/flow_logic.vue`, `i18n/en.ts` (+ WO-2026-09-19-A);
`devserver/schemas/configs/output/decomposition{,_diffusers}.json` und
`devserver/schemas/chunks/output_image_decomposition_{comfyui,diffusers}.py` (gelöscht),
`routes/schema_pipeline_routes.py`, `routes/chat_routes.py`,
`services/latent_lab_model.py`,
`services/canvas_graph_authoring.py`, `services/latent_lab_context_graphs.py`,
`knowledge/platform_items.json`,
`knowledge/platform_modules.json`, `knowledge/ailit_coverage.json` (generiert),
`scripts/build_platform_items.py`, `scripts/build_ailit_coverage.py`,
`trashy_interface_reference.txt`, sieben Tests; `docs/ailit/zuordnungen.tsv`,
`docs/OECD_AILIT_ABDECKUNG.md` und `docs/AILIT_ORTE_ZUORDNUNG.md` (generiert),
`docs/AILIT_ZUORDNUNGSTABELLE.{md,tsv}` (generiert), `docs/ARCHITECTURE PART 28 - Latent-Lab.md`,
`docs/ELEMENT_STRUCTURE_REGISTRY.md`, `docs/WORK_ORDER_CONTENT_CHECKING.md`,
`comfyui_nodes/README.md`, `scripts/befund_belege.py`.

---

## 2026-09-18: Die Stimme beginnt im Strom, sobald der zweite Satz begonnen hat

**Anlass:** Die Stimme setzte erst ein, wenn der Antwortstrom beendet war, obwohl
der erste Satz meist nach 2 bis 3 s im Strom steht.

**Entscheidung:** Auf beiden sprechenden Flächen (Together, Ideen testen) geht
ein Satz an die Stimme, sobald der Strom den Satz nach ihm begonnen hat; der
letzte Satz geht mit dem Schluss-Text. Was die Fläche zurücknimmt (`discard`,
`withdraw`), nimmt die Stimme mit und fängt beim berichtigten Text von vorn an.
Ein Zug, dessen Stimme zu Ende ist (gestoppt, von Help übersprochen, Schalter
aus, ein Stück nicht zu bekommen), beginnt beim Schluss-Text nicht neu. Nimmt
der Zustellfilter Sätze aus dem Schluss-Text, bleibt Gesagtes gesagt und der
Rest folgt; die Schrift liest dann im Lesetempo. Die Regel vom 06.09. (Stimme
und Schrift erscheinen koordiniert, ein Absatz steht) bleibt; sie gilt jetzt
im Strom.

**Betroffene Dateien:** `composables/useSpeech.ts` (`feed`, `follow`,
`useSpokenTurn`), `views/resona.vue`, `views/ai_persona.vue`,
`components/ResonaVoice.vue`, `services/resona_question_filter.py` (Satzende
nur vor Leerraum; Zeile ohne Fund Byte für Byte), `docs/ARCHITECTURE PART 39`.

---

## 2026-09-07: Die Entfernung von Kettenübersetzung, Jugendslang und Pig Latin ist zurückgenommen

**Anlass:** Die Schlussfolgerung vom 06.09. war fehlgeleitet: Die Sprachmodelle in
den Bildmodellen nivellieren den Eingriff nicht weg, und damit ist die Löschung der
Presets nicht mehr gerechtfertigt. Die Frage ist, warum eine damals funktionierende
Technologie heute nicht mehr funktioniert; das betrifft die meisten Presets, auch
Übertreiber, Vermeidlicher und weitere.

Zwei Spuren: die Entscheidung zur Medienabstraktion und die Freigabe des
T5-Tokenbereichs.

**Korrektur der Ausgangseinschätzung (07.09.2026):** Prompt Interception
funktionierte aufgrund der Meta-Anweisung. Nachdem diese auf Semantik
zurechtgestutzt war und Ästhetik und Struktur aus ihr gestrichen waren,
funktionierten die Transformationen nicht mehr. Sprachmodelle jeder Größe können
Perspektivverschiebungen und -übernahmen simulieren, wenn sie dazu aufgefordert
werden; bleibt die Anweisung auf der Ebene von Semantik und Stil, bleiben sie
positional und ästhetisch indifferent.

Damit ist die Annahme vom 06.09. — gestiegene Leistungsfähigkeit der
Sprachmodelle filtere den Eingriff heraus — zurückgezogen. Die Meta-Anweisung
war der Wirkmechanismus, und sie ist in zwei Schritten auf die Semantik
zurückgeschnitten worden:

| Commit | Datum | was verlorenging | angegebener Grund |
|---|---|---|---|
| `bafb3a94` | 14.11.2025 | „Reconstruct all entities and their relations", „Each relation is altered in line with the … logic of the Context", die sechs Gattungen im Wortlaut, „Be aware if the output is something depicted OR itself a cultural artefact" | eine Zeile im Modul-Docstring: „Partly compressed for use with GPT-OSS:20b". Die Commit-Nachricht führt die Property-Taxonomie und 18 Configs auf und erwähnt die Anweisung an keiner Stelle. |
| `e50bcc75` | 24.01.2026 | der Rest: „aesthetic, semantic, structural, and cosmologic transformation", „Specify the genre … and its media translation", „Distinguish: depicted scene vs. the scene itself", „Emphasize elements crucial for media generation" | keiner. Die Commit-Nachricht führt die Zeile als Umbenennung: „instruction_selector.py: 'transformation' replaces 'artistic_transformation'". |

Übrig blieb ein Satz: „Transform the Input according to the rules in Context."
Er benennt eine Wortwahl. Die Ebene, auf der eine Perspektive Gegenstände und
ihre Beziehungen umbaut, stand ab da in keiner Anweisung mehr — und die zehn
Interception-Texte vom 06.09. zeigen genau das: Soziolekt in allen zehn, die
Aufzählung des Eingabesatzes in allen fünf heutigen unverändert weitergetragen.


**Wiederhergestellt am 07.09.2026**, global: als `STRUCTURAL_TRANSFORMATION` in
`devserver/schemas/engine/instruction_selector.py`. Der Wortlaut ist aus der
Versionsgeschichte gelesen statt abgetippt — der Rumpf von
`INSTRUCTION_TYPES["artistic_transformation"]["default"]` bei `bafb3a94^`, Byte
für Byte, und das ist derselbe Text, mit dem die Datei bei `95f628b1`
(03.11.2025) angelegt wurde. Zwei Feldnamen sind auf die heutigen Marken des
Templates gezogen (`input_prompt` → Prompt, `input_context` → Context); alles
andere steht Wort für Wort, samt der Tippfehler des Originals. „Global" heißt:
die Anweisung trägt auch, wo eine Person ihre eigene Aufgaben-Anweisung
geschrieben hat — sie wird dort vorangestellt, so wie die CULTURAL-RESPECT-Regel
angehängt wird. Ein Kettenglied bekommt sie nicht, weil es überträgt statt
umzubauen.

*Berichtigt am 26.09.2026:* Die Anordnung zur Wiederherstellung nannte drei
Stellen des Textes: „This is not a linguistic translation …“, „Each relation is altered …“ und
„Also communicate genres/artistic traditions …“. Die Abschrift Byte für Byte, mit den
Tippfehlern und mit drei weiteren Sätzen, war die Wahl der Umsetzung vom 07.09.2026: zwei
verlangten, den Kontext als „cultural, artistic, intervening context“ zu benennen, einer, die
für die Mediengenerierung wichtigsten Elemente mitzuteilen. Die drei Sätze sind am 26.09.2026
gestrichen (Eintrag vom 26.09.2026).

**Nicht** aus `devserver/schemas/engine/archive/instruction_selector_original.txt`:
diese Datei ist vom schneidenden Commit selbst angelegt worden, und sie schreibt
„cosmologic" und „sensual aesthetics", wo der Code, den sie ersetzte,
„structural" und „visual aesthetics" sagt. Beide Wörter betreten das Repository
mit `bafb3a94`.

Die Fassung dieser Plattform ist die medienoffene: sie fragt „is it a dance, a
photo, a painting, a song, a movie, a statue/sculpture? how should it be
translated into media?" und nennt am Ende „an succeeding media generation" —
Medialität wird also erschlossen und nicht gesetzt. Die ComfyUI-Fassung von
2025, die die Vorschaubilder tragen, schreibt an beiden Stellen „image".

*Stand 26.09.2026:* Der Satz mit „an succeeding media generation“ ist gestrichen, die Frage „how
should it be translated into media?“ steht weiter.

**Was zurückgeht.** Die beiden Vermerke vom 06.09.2026 (die Kettenübersetzung
eingestellt; Jugendslang und Pig Latin gehen denselben Weg) sind zurückgezogen.
Wiederhergestellt sind die drei Configs, `text_transformation_recursive`,
`manipulate_recursive`, `random_language_selector`, der Anweisungstyp
`chain_translation` samt `CHAIN_LANGUAGE_RULE`, die Schleife im
`pipeline_executor`, die Labels in allen zehn Sprachen und
`devserver/tests/test_chain_translation.py`.

**Was stehen bleibt.** Die Beobachtung: auf SD 3.5 Large erreicht der Eingriff
dieser Perspektiven das Bild heute nicht. Und die beiden Testverbesserungen, die
mit der Sache nichts zu tun haben: `devserver/tests/test_instruction_invariants.py`
trägt die plattformweiten Zusicherungen, und der Schutz gegen eine an den
Übersetzer gerichtete Zeile im Text, den eine Schülerin liest, gilt für alle
Perspektiven.

**Der Beleg für die Spur.** Die Vorschaubilder tragen den ausgeführten
ComfyUI-Graphen als `tEXt`-Chunk. Der Aufgabensatz von damals (Node 41,
`style_prompt`) schließt mit:

> Create an output prompt tailored for Stable Diffusion 3.5 with combined clip_g
> and t5xxlenc. Regard the Token Limit (75), OUPUT max. 55 Words!

Er verlangte davor ausdrücklich eine Bildbeschreibung mit Gattung, Material,
Technik, Komposition und Atmosphäre. Der heutige Aufgabensatz lautet „Transform
the Input according to the rules in Context", läuft bis 300 Wörter und nennt
weder Medium noch Encoder noch Tokengrenze.

Dazu die Verdrahtung: damals **ein** `CLIPTextEncode` auf einem
`DualCLIPLoader` (clip_g + t5xxl_enconly) — 55 Wörter innerhalb der 77 Token,
für beide Encoder derselbe vollständige Text. Heute `CLIPTextEncodeSD3` mit drei
getrennten Feldern an einem `TripleCLIPLoader`, und 300 Wörter passen in das
CLIP-Fenster nicht hinein.

**Stand der Belege.** Gemessen ist der Aufgabensatz: gekreuzt über fünf
Sprachmodelle, gleicher Seed, gleiches Bildmodell, elf Bilder (Forschungsrepo,
Studie `2026-09_sprachliche_eingriffe_projektlaufzeit`). Unter dem heutigen
Aufgabensatz weicht ein Ergebnis von fünf ab, unter dem alten drei von fünf. Die
Encoder-Verdrahtung ist als Unterschied belegt und als Ursache ungeprüft.

**Was die Interception-Texte zeigen.** Strukturell ist kaum etwas vom Preset
aufgegriffen, und das erklärt sich nicht über die Länge. Ausgezählt über die zehn
Texte: der Soziolekt steht in allen
zehn, ein Medium oder eine Gattung nennen damals vier von fünf und heute keiner,
und alle fünf heutigen Texte tragen die Aufzählung des Kontrollprompts (Haus,
Fläche, Natur, Tiere) unverändert weiter. Der damalige Aufgabensatz verlangte
„a aesthetic, semantic and structural transformation" und dass „each relation is
altered in line with the … logic of the ‚Context'". Der heutige nennt das Preset
eine Wortwahl („Use the specific vocabulary and techniques defined in Context")
und verlangt daneben „situated observation". Die Wortzahl folgt aus diesen
Sätzen; als Ursache trägt sie nicht.

**Offen.** Die Frage gilt der Breite: welche Presets heute an dieser Stelle
verlieren. Übertreiber, Vermeidlicher und weitere sind genannt; geprüft ist
keines.

---

**Nachgezogen am 07.09.2026.** Die Lesemenge wird generell ausgesetzt;
strukturelle, ästhetische, kulturelle und positionale Positionen und Perspektiven
stehen im Vordergrund, und das muss in der Anweisung wieder deutlich werden.

- **Die Lesemenge ist ausgesetzt.** `get_reading_volume_clause()` gibt nichts
  mehr zurück. Sie stand als letzte Zeile des zusammengebauten Prompts, hinter
  dem Text der Person, und nannte den Ausweg selbst: „If the content exceeds
  that, leave something out." Was ein Modell zuerst weglässt, ist die teure
  Arbeit — und die teure Arbeit ist der Umbau der Entitäten und Relationen, also
  die Interception. Die Tabelle `READING_VOLUME_WORDS` bleibt stehen, damit die
  Klausel in einer Zeile zurückkommen kann.
- **Die vier Ebenen stehen am Kopf der Anweisung**, vor dem wiederhergestellten
  Wortlaut und getrennt von ihm, damit dieser wörtlich bleibt (seit
  dem 26.09.2026 fehlen ihm drei Sätze): „The Context is a
  POSITION and a PERSPECTIVE. What a transformation works on are structural,
  aesthetic, cultural and positional relations: take that position over and work
  from inside it."
- **„situated observation over decorative or dramatized aesthetics" ist aus dem
  Block VISUAL SPECIFICITY heraus.** Der Satz zog zum treuen Beschreiben des
  Gegebenen und damit gegen den Umbau. Die Zeile gegen AI-Klischees bleibt.
- **Bei übergebenem Bild** tritt der wiederhergestellte Rumpf zurück und eine
  kurze Zeile steht an seiner Stelle (`INSTRUCTION_ON_PICTURE`) — eine Anweisung
  auf ein vorhandenes Bild verlangt keine Rekonstruktion von Entitäten, die das
  Modell laut demselben Prompt nicht sehen kann. Die vier Ebenen bleiben auch
  hier stehen.
- **Der Typ kommt jetzt an**, wo eine Perspektive einen eigenen deklariert und
  ihre Pipeline schweigt: `config_loader` las das Feld, und niemand verwendete
  es. Die Pipeline bleibt die erste Instanz — sie ist die Quelle des Flows.
- **Der Canvas bekommt die Aufgaben-Anweisung**, und mit ihr die
  CULTURAL-RESPECT-Regel und das Jugendschutz-Präfix seiner Stufe. Sein
  Interception-Knoten fuhr bis heute allein mit dem Perspektiven-Text als
  Anweisung.
- **`build_full_prompt` schreibt `Prompt:` statt `Input:`** — dieselbe Marke, die
  `schemas/chunks/manipulate.json` schreibt. Die Anweisung nennt die Marke, die
  dasteht; zwei Zusammenbauten mit zwei Marken ließen sie auf diesem Weg ins
  Leere zeigen.
- **`POST /api/schema/pipeline/test`** ersetzte mit `task_instruction` im Body
  die ganze Anweisung samt Jugendschutz-Präfix. Der Text geht jetzt durch
  `get_instruction()`, wie der einer behaltenen Perspektive, und die Stufe fällt
  auf die strengste, wo die Anfrage keine nennt.
- **Die Schlusszeile der Anweisung sagt wieder, worum es geht.** Sie steht
  unmittelbar vor dem Text der Perspektive und ist damit die letzte, die ein
  Modell vor der Aufgabe liest. Seit `e50bcc75` stand dort „Use the specific
  vocabulary and techniques defined in Context." — die Lesart, die den Context
  zum Stilfilter macht, an der stärksten Stelle, und sie hob den Kopf-Block 400
  Wörter weiter oben wieder auf. Sie fiel damit auch der Perspektive selbst in
  den Rücken: die Bauhaus-Perspektive schließt mit „YOUR DUTY IS
  PERSPECTIVE_TAKING, NOT MIMICKING SURFACES", und Vokabular und Techniken sind
  Oberflächen. Jetzt steht dort: „Work from inside the position the Context sets
  out. What you transform are the structural, aesthetic, cultural and positional
  relations of the Prompt." Die vier Ebenen öffnen und schließen die Anweisung.
- **Der Längenabsatz behauptete eine Kürzung, die es nicht gibt.** „Everything
  you write past the 300th word is cut off before the result is shown" — nichts
  im ganzen Weg schneidet nach Wörtern, weder im Backend noch im GPU-Dienst noch
  in der Oberfläche; der Satz kam mit `5c326e85` und brachte keine Durchsetzung
  mit. Er stand als Behauptung über das eigene Verhalten der Plattform gegen ein
  Modell und lief außerdem gegen das wiederhergestellte „Be verbose!". Dort
  steht jetzt: „LENGTH: 300 words. Plan the whole result to fit inside it and
  finish it there." Die Zahl bleibt: Der Wirkungsverlust erklärt sich nicht über
  die Länge, und die Kette von 2025 trug
  dieselbe Spannung („Be verbose!" neben „OUPUT max. 55 Words!"), als sie noch
  trug.
- **Zwei Perspektiven-Notizen nannten die ausgesetzte Klausel als ihre Grenze.**
  `recasting.json` und `against_the_model.json` hatten ihre eigene Längengrenze
  auf Anweisung fallen lassen und verwiesen dafür auf die Lesemengen-Klausel.
  Ihre `meta.length_note` nennt jetzt die Angabe der Aufgaben-Anweisung.
- **Und dann, am selben Tag, wieder zurück, mit anderen Zahlen.** Kinder und
  Didaktik verlangen eine Lesemenge. `READING_VOLUME_WORDS` führt jetzt
  `easy: 100`, `medium: 200`, `expert: 300`. Die Klausel deckt damit wieder alle
  drei Modi, und ihre Zahl bei Experte ist dieselbe 300, die die
  Aufgaben-Anweisung selbst nennt — dort überschreibt also nichts mehr etwas
  anderes. Die Einstellungs-Zeile nennt die drei Zahlen
  (`settings.general.uiModeEffectLength`, Auftrag für die neun übrigen Sprachen
  liegt in `WORK_ORDERS.md`).
- **Zwei Berichtigungen zur Klausel selbst.** Sie stand *nicht* als letzte Zeile
  des zusammengebauten Prompts, wie zwei Kommentare im Quelltext und die
  Begründung der Aussetzung behaupteten: `pipeline_executor` hängt danach den
  Wikipedia-Block an, rund 490 Wörter, also 45 % des ganzen Textes. Und ihr
  zweiter Satz sagte, dass etwas wegfallen darf, ohne zu sagen was — bei
  einfach stehen 100 Wörter gegen acht Forderungen der Anweisung, und das
  Einzige ohne feste Kosten ist der Umbau der Gegenstände und ihrer
  Beziehungen. Er lautet jetzt „shorten the naming and the framing — keep the
  entities, their relations, and how the Context transforms them". Außerdem
  klebte die Klausel am Wikipedia-Block: sie endet ohne Umbruch, der Block
  begann mit genau einem, sie las sich damit als dessen Kopfzeile.
- **Der Typ kam gar nicht an — er wurde beim Laden verworfen.** `config_loader`
  behielt `instruction_type` weder auf der Datenklasse noch las es den Schlüssel
  aus der JSON, also lief der Zwischenschritt in `chunk_builder` ins Leere. Er
  wird jetzt gelesen und durch `ResolvedConfig` durchgereicht. 45 der 102
  Perspektiven deklarieren einen — und **keine einzige Anweisung ändert sich
  dadurch**: die deklarierten Namen sind entweder `transformation`, sein
  Altname, oder ein Name, den `INSTRUCTION_TYPES` gar nicht führt
  (`latent_exploration`, `surrealizer`, `split_and_combine`,
  `partial_elimination`, `musical_transformation`, `image_transformation`,
  `multi_image_transformation`) und der auf `transformation` normalisiert.
  `stillepost` ist die einzige mit `chain_translation`, und die bekommt ihn
  ohnehin von ihrer Pipeline. Geprüft über 102 Perspektiven × 4 Stufen × 2
  Bildzustände: null Unterschiede.
- **Die Stufe kam ungeprüft aus dem Anfragekörper.** `POST
  /api/schema/pipeline/test` hat keine Anmeldung, und mit dem neu gesetzten
  Präfix hätte ein Feld im Körper genügt, es wieder zu entfernen. Überall sonst
  löst der Server die Stufe auf und ein Kurs darf nur verschärfen. Auf diesem
  Prüfendpunkt gilt jetzt fest die strengste.
- **Die Formatregel nannte die Marke des anderen Zweigs.** `build_full_prompt`
  hängt an beide Zweige denselben Satz „ALWAYS reply in the language of the
  input" — der neue Zweig schreibt seit dem Wechsel auf `Prompt:` aber kein
  `Input:` mehr. Jeder Zweig hat jetzt seine eigene Fassung.

---

## 2026-09-06 (abends): Die Kettenübersetzung ist eingestellt — der Sprachvergleich steht im Latent Lab

> **Zurückgenommen am 07.09.2026.** Die Begründung hielt der Prüfung nicht
> stand; siehe den Vermerk vom 07.09.2026 oben. Das Preset läuft wieder.

**Anlass:** Das Preset stammt aus der Zeit lokaler 14b-Modelle, und der Sprachvergleich steht im Latent Lab.

**Was die Kettenübersetzung war.** Ein Preset (`stillepost`), das einen Text durch acht zufällig gezogene Sprachen schickte und im neunten Aufruf in die Sprache der Eingabe zurückholte — Stille Post als Verfahren. Sie lief als einzige Interception auf einer eigenen, schleifenden Stage-2-Pipeline (`text_transformation_recursive`) mit eigenem Baustein, eigenem Anweisungstyp, eigener Zufallssprachen-Auswahl und einer eigenen Ausführungsschleife im Motor.

**Der Grund ist der Anlass oben.** Was das Verfahren an dem Abend tat, trägt die Entscheidung nicht: fünf Läufe zwischen 21:12 und 21:48 gingen sehr verschieden aus. Ein fränkischer Satz („ein heißer Tag auf der Kirwa, Weischwurscht galore und a U hats auch ghobt") kam als Amtsdeutsch zurück („An einem warmen Tag des traditionellen jährlichen Festes der Kircheneinweihung wurde eine große Menge weißer Wurst auf der Basis von Kalbfleisch zubereitet") — der Verfall ist da, und zwar gerade an dem, was an Sprache nicht Standard ist. Ein schlichter Aussagesatz dagegen („Ein Haus steht in einer Landschaft, umgeben von landwirtschaftlichen Flächen, Natur und Tieren") überstand acht Sprachen bis auf ein türkisches Semikolon unverändert. Der Ertrag hängt also am Eingabesatz und ist nicht mehr verlässlich — er ist nicht verschwunden. Wer diesen Eintrag später gegen die Sache liest: die Läufe liegen unter `exports/json/2026-09-06/`.

**Was an seine Stelle tritt.** „Tokenisierung im Sprachvergleich" im Latent Lab (`views/latent_lab/tokenization_comparison.vue`). Derselbe Satz in den zehn Sprachen der Plattform, Token für Token, dazu dasselbe Einzelwort in allen zehn; der Tokenizer ist wählbar, CLIP steht mit in der Liste, und die Fensterbreite des gewählten Tokenizers steht daneben. Die Ungleichbehandlung wird dort gezeigt, wo sie herkommt, statt in einem Verfallsprodukt vermutet.

**Folgen im Code.** Die Schleife wird nicht als leere Infrastruktur behalten. Ihre Bestandteile trugen alle den Namen des einen Verfahrens: der Baustein liest den Vorgänger und eine Zielsprache, der Anweisungstyp beschreibt ein Glied einer Übersetzungskette, die Sprachauswahl zieht aus einer Sprachliste, die Schleifenparameter heißen `iterations` / `use_random_languages` / `final_language`. Entfernt: Config, Pipeline, Baustein, `random_language_selector`, der Anweisungstyp `chain_translation` samt `CHAIN_LANGUAGE_RULE`, `_execute_recursive_pipeline_steps`, die Lesemengen-Ausnahme im Baustein-Bau, die Abweisung schleifender Linsen im Canvas-Knoten und beim Canvas-Autor, die Schleifen-Parameter der Kurs-Perspektiven (`ALLOWED_PIPELINES` und die Fork-Parameter der Route) und die Pipeline in der Perspektiven-Erkennung des Frontends (`usePerspectiveCatalog.PRESET_PIPELINES`).

Damit gilt der Vermerk vom selben Tag zu „Canvas als Preset" nur noch in seiner ersten Hälfte: Mehrschrittiges gehört in eine Stage-2-Pipeline, aber der Schleifen-Pfad steht dort nicht mehr bereit. Wer ihn braucht, baut ihn für die Sache, für die er gebraucht wird.

**Was mitzugehen drohte und gehalten wurde.** Die gelöschte Testdatei war der einzige Ort im Backend, der zwei plattformweite Zusicherungen hielt: dass eine selbst geschriebene Aufgaben-Anweisung die CULTURAL-RESPECT-Regel nicht mit hinausnimmt (der Fork-Weg steht jedem offen, der eingeloggt ist), und dass der Verweigerungssatz derselbe ist wie in den beiden Sicherheitspräfixen. Beides steht jetzt in `devserver/tests/test_instruction_invariants.py`, wo es hingehört — es hatte mit der Kette nie etwas zu tun.

**Behalten:** `SAFETY_REFUSAL_SENTENCE`. Der Satz steht an vier Stellen als Literal — in den beiden Sicherheitspräfixen und in `views/compare/{language,model}_comparison.vue`, die eine Verweigerung daran erkennen —, und keine davon liest die Konstante. Sie hält die fünf in Schritt, und der neue Test hält die beiden Präfixe an sie. Und die Übergabe der Pipeline an den Baustein-Bau (`pipeline_executor`), die am selben Tag zeigte, dass `instruction_type` in einer Pipeline-Datei seit jeher ins Leere deklarierte: sie gilt für alle Pipelines.

**Betroffene Dateien:** entfernt `devserver/schemas/configs/interception/stillepost.json`, `devserver/schemas/pipelines/text_transformation_recursive.json`, `devserver/schemas/chunks/manipulate_recursive.json`, `devserver/schemas/engine/random_language_selector.py`, `devserver/tests/test_chain_translation.py`; neu `devserver/tests/test_instruction_invariants.py`; geändert `devserver/schemas/engine/{pipeline_executor,instruction_selector,chunk_builder}.py`, `devserver/my_app/services/{canvas_executor,canvas_graph_authoring,tool_registry,course_prompt_resolver}.py`, `devserver/my_app/routes/{interception_prompts_routes,pipeline_routes}.py`, `devserver/{analyze_context_prompts,test_recorder}.py`, `devserver/tests/test_interception_model_choice.py`, `public/ai4artsed-frontend/src/composables/usePerspectiveCatalog.ts`, `public/ai4artsed-frontend/src/i18n/en.ts`, `docs/ARCHITECTURE PART 01/04/26`, `docs/ELEMENT_STRUCTURE_REGISTRY.md`.

---

## 2026-09-06: Die Masken werden zur normalen Help-Maske — keine Repräsentation, nur Präsentation in der Aktion

**Anlass:** Die Masken werden zur normalen Help-Maske; Help blendet den Starttext ein wie auf allen Seiten, und die beiden Agenten sind ausschließlich durch ihr Erscheinen als Text, Stimme und Items repräsentiert, also durch das, was sie tun. Es gibt keine Repräsentation, nur Präsentation in der Aktion.

**Was vorher galt.** Zwei Routen beanspruchten die eine Maske für sich: `/together` (Werkstatt) und `/contesting` (bestreitende Maschine). Eine Routentabelle in `App.vue` wies ihnen die Aktanten `advise` bzw. `contest` zu, samt eigener Tönung und eigenem Namen. Daraus folgte auf diesen beiden Seiten: die Maske stand in der Seitenmitte statt in der Ecke, sie zeigte den Zustand des Seiten-Agenten (rechnet / klingt / hält zurück), der Klick ging an die Seite statt an Help, und ein Help-Panel gab es dort überhaupt nicht — nur eine einzige Ausnahme, die Erklärung eines gesperrten Uploads.

**Was jetzt gilt.** Die Maske ist auf jeder Seite Help, ohne Ausnahme. Der Klick öffnet Helps Gespräch, und dieses öffnet mit dem Starttext der Seite, wie überall sonst. Die beiden Agenten haben in der Ecke nichts mehr: sie sind da, indem sie sprechen, schreiben und Dinge auf der Fläche herstellen. Die Erklärung eines gesperrten Uploads steht ab jetzt in Helps eigenem Gespräch — an derselben Stelle wie auf allen anderen Seiten, statt in einem Sonderpanel.

**Begründung.** Eine Figur, die für einen Agenten steht, ist eine zweite und ärmere Behauptung über dieselbe Sache: sie sagt „hier ist jemand", während die Fläche daneben zeigt, was dieser jemand tut. Wo beides steht, liest man die Behauptung und nicht die Handlung. Die Regel trennt das: was der Agent tut, ist alles, was ihn darstellt.

**Folgen im Code.** Der Aktanten-Begriff entfällt vollständig — er hatte keine zweite Verwendung.

### Betroffen

- `public/ai4artsed-frontend/src/App.vue` — `FIGURE_BY_ROUTE`, `FigureRole`, `figureRole` entfallen; die Maske bekommt Helps Tönung und Namen
- `public/ai4artsed-frontend/src/components/ChatOverlay.vue` — `actant`-Prop und `isHelp` entfallen mit allen Zweigen; die Ruhelage ist wieder die Ecke; `safetyNotice`/`safetyNoticeText` entfallen, weil die Erklärung in Helps Gespräch geht
- `public/ai4artsed-frontend/src/stores/pageFigure.ts` — der Agenten-Kanal (`state`, `setState`, `reset`, `focusRequests`, `requestInputFocus`, `addressRequests`, `requestAddress`) entfällt; der Kanal der Plattform-Stimme bleibt
- `public/ai4artsed-frontend/src/views/resona.vue` — schreibt keinen Maskenzustand mehr und hört nicht mehr auf Maskenklicks
- `public/ai4artsed-frontend/src/views/ai_persona.vue` — dito; das Schreiben ist der einzige Weg hinein, was die Seitenbeschreibung jetzt auch so sagt
---

## 2026-09-02: Ein Kind je Modell — die lokalen Sprach- und Bildmodelle verlassen den Prozess des GPU-Dienstes

**Kontext:** Seit dem 2026-03-28 laufen die lokalen GGUF-Modelle in-process im GPU-Dienst (llama-cpp-python). Ueber den Sommer traten drei Fehlerklassen auf, die sich alle aus demselben Umstand ergeben: die Modelle teilen sich den Prozess mit jeder Inhaltspruefung der Plattform.

| Klasse | Befund | Herkunft |
|---|---|---|
| A — Absturz | Der CLIP-Rechenpuffer des mmproj wird bei knappem VRAM still nicht angelegt; die erste Bild-Enkodierung dereferenziert ihn: SIGSEGV, der ganze Dienst faellt (4x im August). | llama.cpp #23422, „not planned"; PR #27855 offen |
| B — Buchfuehrung | Der Qwen25VL-Chat-Handler von llama-cpp-python schiebt `n_tokens` ueber die Bildpositionen, ohne `input_ids` zu schreiben; Lesungen kommen beschaedigt („,") oder leer zurueck. | llama-cpp-python 0.3.19, Handler-Code |
| C — Faehigkeit | Ein GGUF, das beim Laden abbricht (nanoLLaVA: `GGML_ASSERT`), ist in-process ausgeschlossen, weil es den Dienst mitnaehme; `smollm3:3b` laesst sich in-process gar nicht laden (sein Template enthaelt `{% generation %}`, Jinja2 bricht beim Konstruktor ab); Bild geht nur ueber sieben fest verdrahtete Handler, ShieldGemma 2 hat keinen. | gemessen 2026-08-31 und 2026-09-02 |

Der Budget-Fix vom 2026-08-30 (5000-MB-Zuschlag, Aufwaermlauf) hat Klasse A seither verhindert (0 Abstuerze). B und C behebt kein Budget.

### Decision 1: Ein beaufsichtigter `llama-server`-Kindprozess je geladenem Modell

Der GPU-Dienst startet je Alias einen eigenen `llama-server` (`-c`, `-ngl`, `--mmproj`, `--no-context-shift`, `--jinja`, `-np 1`), wartet auf dessen Bereitschaft, misst ihn per PID ueber NVML, beendet ihn bei Verdraengung oder Entladen (SIGTERM, dann SIGKILL) und raeumt Waisen beim Start weg (Eigentumsmarke `AI4ARTSED_LLM_CHILD=<parent_pid>:<alias>` im Environ des Kindes plus `/proc`-Startzeit — ohne beides wird nichts beendet). Der VRAMCoordinator bleibt die einzige Residenz-Instanz: die Kinder stehen in seinem Eigentums-Register, seine LRU-Verdraengung beendet sie, seine Notraeumung beendet sie vor allem Fremden. Die Inferenz-Schnittstelle (`/api/llm/*`, Antwortkoerper mit `content`/`thinking`/`finish_reason`) bleibt unveraendert; DevServer-Code aendert sich nicht.

**Begruendung (Messung 2026-09-02, RTX PRO 6000, Build 59d8402):**

| Messung | Ergebnis |
|---|---|
| Laden `qwen3-vl:8b` | 8,1 s bis bereit; NVML 9170 MB |
| Erstes Bild | +64 MB (CLIP-Rechenpuffer 372 MiB, im Ladeprotokoll) |
| Drei Lesungen desselben Bildes | 3/3 vollstaendig, `finish=stop` (Klasse B: behoben) |
| Kontext erschoepft | `finish=length`, kein Absturz |
| Wiederholungsschleife | abgebrochen, Slot danach frei (0,0 s belegt) |
| Entladen 8B / 32B | NVML-Belegung nach 0,13 s / 0,19 s weg |
| Kind mit SIGKILL getoetet | Dienst antwortet weiter (200); naechste Anfrage startet ein neues Kind in 1,1 s |
| Acht Testbilder durch die volle Bildpruefung (Beschreibung lokal, Urteil Cloud) | 8/8 richtig: vier Aktbilder gesperrt, vier harmlose frei |
| Prompt-Parität (Chat-Template je Modell, Jinja2 gegen Server) | 7 von 14 Textmodellen zeichengleich; 4 unterscheiden sich nur in der Schreibweise des Starttokens (`<bos>`/`<s>` als Text gegen Token); die vier Bildmodelle bekommen jetzt ihr eigenes Template statt des Handler-Templates (das schob einen leeren System-Block ein und liess den Zeilenumbruch nach `assistant` weg) |

**Warum das der Entscheidung vom 2026-03-28 nicht widerspricht, sondern sie korrigiert:** Dort wurde „separater llama-server-Prozess" als „gleiches Problem wie Ollama (zweiter GPU-Prozess, keine VRAM-Koordination)" verworfen. Das trifft auf einen fremden Daemon zu, der nach eigenen Regeln allokiert (Ollama rechnete den KV-Cache aus dem Gesamt-VRAM). Ein Kind, das der Dienst selbst mit explizitem `-c`/`-ngl` startet, per PID misst und beendet, steht innerhalb der Koordination — die Messung oben ist der Beleg. Der Preis: ein Prozessstart je Modell (8 s beim 8B) und HTTP zwischen Dienst und Kind.

**Alternatives verworfen:**
- ❌ Den Qwen25VL-Handler in llama-cpp-python flicken: behebt B, nicht A und nicht C.
- ❌ ComfyUI als Bibliothek: `comfy.model_management` ist prozessglobal und verwaltet nur seine eigenen `ModelPatcher`-Modelle, einen LLM-Laufzeitkern gibt es dort nicht — und ComfyUI ist GPLv3, die Plattform Source-Available/Non-Commercial; ein Import in denselben Adressraum ist nach FSF-Lesart ein kombiniertes Werk.
- ❌ In-process belassen und A per Budget aushalten: laesst B und C stehen; der Absturz-Pfad bleibt upstream „not planned".
- ❌ Ein einziger langlebiger llama-server fuer alle Modelle: kein Entladen einzelner Modelle, keine Verdraengung durch den Koordinator je Modell.

### Decision 2: Der In-process-Motor bleibt waehlbar, das Register bleibt, wo es ist

`LLM_ENGINE=child` (Default) oder `inprocess`; eine andere Schreibweise wird beim Start abgewiesen. `MODEL_CONFIGS` in `services/llm_backend.py` beschreibt weiterhin die Modelle (Pfad, mmproj, Faehigkeiten) und wird von beiden Motoren und von `install_service` gelesen. Das Kontextfenster steht seit dem 09.09.2026 nicht mehr darin: `resolve_window` liest es aus der GGUF-Datei des Modells und rechnet daraus auch den Speicher, den der KV-Cache kostet. Ein Modellname steht nirgends sonst.

### Decision 3: Laden und Erzeugen sind durch Fortschritt begrenzt, nie durch Lese-Timeouts

Ein Kind gilt als haengend, wenn 180 s lang keines von vier Fortschrittssignalen (Pipe-Bytes, fertige Protokollzeilen, `/proc/<pid>/io` in ganzen MiB, NVML-Belegung) sich bewegt; unabhaengig davon endet jedes Laden nach 900 s. Beides sind Fortschritts- bzw. Lade-Schranken, keine Lese-Timeouts: Anfragen an ein bereites Kind laufen ohne Lese-Timeout (`(5, None)`), der Server selbst bekommt `-to 2592000`.

Ein bereites Kind mit laufender Anfrage unterliegt derselben Stillstands-Schranke, gemessen am Fortschritt seines Slots: eintreffende Antwortstuecke, die Arbeitszeilen des Kindes (Vorfuellen je Batch, Bild-Enkodierung) und der Dekodierzaehler aus `/slots` — eine Statusabfrage mit kurzem Lese-Timeout, keine Modellabfrage; bleibt sie stumm, zaehlt das als Stillstand, weil `/slots` durch dieselbe Hauptschleife laeuft wie das Erzeugen. Bewegt sich 180 s lang keines der drei, wird das Kind beendet, die laufende Anfrage erfaehrt diesen Grund im Fehlerkoerper, die naechste Anfrage startet neu. Eine Anfrage, die Stuecke empfaengt, wird nie abgeschnitten; eintreffende weitere Anfragen zaehlen nicht als Fortschritt. Laufen mehrere Stroeme auf einem Kind, hat jeder seine eigene Uhr: ein Strom, dessen Stuecke ausbleiben, waehrend der Slot laengst die naechste Anfrage bedient, ist eine fertige Antwort, die niemand abholt — diese eine Anfrage wird geschlossen, das Kind bleibt.

**Betroffene Dateien:** `gpu_service/config.py`, `gpu_service/services/llm_child.py` (neu), `gpu_service/services/llm_child_backend.py` (neu), `gpu_service/services/llm_backend.py`, `gpu_service/services/vram_coordinator.py`, `gpu_service/services/gpu_admission.py`, `gpu_service/routes/llm_routes.py`, `gpu_service/routes/health_routes.py`, `gpu_service/server.py`, `gpu_service/tests/test_llm_child_backend.py` + `fake_llama_server.py` (neu), `devserver/config.py`, `devserver/my_app/routes/settings_routes.py`, `devserver/my_app/services/llm_client.py`, `docs/ARCHITECTURE PART 27/31/40`, `docs/installation/*`, `check_prerequisites.sh`, `.gitignore`.

---

## 2026-08-31: Die Fläche zum Bedeutungsbezug im Modell ist eingestellt — und warum ein Erklärbild dort trägt, wo ein Instrument fällt

**Anlass:** Es ist nicht ersichtlich, wie eine solche Fläche funktionieren soll; das
Vorhaben wird endgültig eingestellt.

**Eingestellt** ist das Vorhaben einer Fläche im Text-Lab, die vorführt, wie im Modell
Bedeutungsbezüge entstehen: die Attention-Fassung „Ein Wort im Satz" (entfernt,
`65824c0c`) und die Nachfolge über den Einbettungsraum (`POST /api/text/embedding/pair`,
gebaut, ohne Fläche) gleichermaßen. **Bleibt:** die Stationen „Tokenization and
embedding" und „Attention" auf der Überblickskarte (`views/latent_lab/flow_logic.vue`), der
Reiter „Tokens" im Text-Lab, beide Endpunkte als Messwerkzeuge, die Gleichstück-Prüfung in
`compare_positions`. Wiederaufnahme allein auf ausdrückliches Verlangen.

### Warum Jay Alammar 2018 zeigen konnte, was hier dreimal fiel

Die Frage ist berechtigt: „The Illustrated Transformer" zeigt Attention-Bezüge
verständlich, seit acht Jahren, und Tensor2Tensor (2018) wie BertViz (Vig 2019) bieten
sie als Werkzeug an. Der Unterschied liegt in vier Punkten, und keiner davon ist eine
Frage des Aufwands.

| | Alammar 2018 | die geplante Fläche |
|---|---|---|
| Gattung | Einzelbild **in** einem langen Erklärtext | Instrument, das allein spricht |
| Behauptung | so ist die Rechnung gebaut | so entstehen Bedeutungsbezüge |
| Gegenstand | Encoder, 6×8 = 48 Köpfe, beidseitige Sicht, EIN gewählter Satz | Qwen3-14B, 40×40 = 1.600 Köpfe, kausal, beliebige Eingabe in neun Sprachen |
| Richtung | deduktiv aus der Spezifikation | induktiv aus einer Messung |

**1. Das Bild illustriert dort einen Text, hier soll es ihn ersetzen.** Alammars Figur
steht zwischen Absätzen, die sagen, was zu sehen ist; sie darf den Erklärtext brauchen,
weil er das Werk ist. Die eigene Regel der Plattform verlangt das Gegenteil (eine Einsicht je
Fläche, ohne Vorrede), und jede der drei Fassungen brauchte einen Absatz Prosa. Damit war eine Bildform aus
ihrer Gattung gehoben.

**2. Er zeigt den Mechanismus, wir wollten eine These belegen.** Q, K, V, Softmax,
mehrere Köpfe — das ist per Spezifikation wahr und braucht keine Messung, die es
bestätigt. Eine Aussage darüber, **woran** ein trainiertes Modell Bedeutung knüpft,
braucht Treue der Karte zur Rechnung, und die haben rohe Gewichte nachweislich nicht
(Jain & Wallace 2019; Kobayashi et al. 2020: `out = Σ α·v`, die Karte zeigt `α`).
Dasselbe Bild, andere Beweislast.

**3. Sein Gegenstand trägt Einzelkopf-Bilder, unserer verteilt die Arbeit.** Die
klassischen Figuren stammen aus Encoder-Selbstaufmerksamkeit mit beidseitiger Sicht und
wenigen Dutzend Köpfen. Unser Modell liest kausal — daher die gemessene Bedingung, dass
sich zwei Sätze VOR dem markierten Wort unterscheiden müssen — und verteilt auf 1.600
Köpfe, während rund zwei Drittel der Parameter in den Feed-Forward-Blöcken sitzen
(Geva et al. 2021), die in keiner Attention-Karte vorkommen.

**4. Ein gewähltes Beispiel muss einmal stimmen, ein Instrument immer.** Alammar wählt
Satz, Schicht und Kopf und zeigt einen Fall. Eine Fläche nimmt Eingaben entgegen, die
ihr Autor nie gesehen hat, in neun Sprachen — und die automatische Auswahl dafür war
zirkulär (Rang nach `1 − normierte Entropie` findet konzentrierte Positions- und
Syntaxköpfe und meldet sie als Befund).

### Die Überblickskarte trägt es bereits

**Die Karten in der Übersicht reichen.** Das trifft zu, und zwar aus demselben Grund wie oben: die
Überblickskarte IST die Gattung, in der Alammars Bild funktioniert — gezeichnete Figuren
in einem Erklärtext, an einem gewählten Beispiel.

Die Station „Attention" (`latentLab.flowLogic.transformer.block`,
`views/latent_lab/flow_logic.vue`) sagt bereits, was die geplante Fläche interaktiv zeigen
sollte: zwei Sätze mit „bank", am Anfang dieselbe Zahlenreihe, nach der Attention zwei
verschiedene — „each ‚bank' carries the meaning of its sentence". Die Station davor,
„Tokenization and embedding", liefert die Voraussetzung: feste Zahlenreihe je Token, an
Qwen3-4B gemessen, mit Modellhinweis auf jeder der drei Karten.

Drei Gründe, warum das genügt:

1. **Die Behauptung der Karte ist geprüft.** `POST /api/text/embedding/pair`, Qwen3-4B,
   englisches Paar: Schicht 0 exakt 1,0000, Schicht 34 0,6496 gegen ein Grundrauschen
   derselben Schicht von 0,6440 — am Anfang identisch, am Ende von beliebigen Zeilen
   ununterscheidbar. Die Messung prüft hier die Karte, und das ist ihre Rolle.
2. **Die Karte benennt ihren Status selbst** („The arcs and the bank rows are exemplary";
   „The intermediate state ‚farms' and the 36 layers were measured on 2026-08-24"). Ein
   gewähltes Beispiel, als solches ausgewiesen, trägt genau so weit, wie es soll.
3. **Nachprüfen gibt es dort, wo es trägt.** Der Reiter „Tokens" im Text-Lab
   (`tokenization_comparison.vue`) lässt die Tokenisierungs-Behauptung mit eigenem Satz und
   eigenem Wort in zehn Sprachen nachrechnen — dort ist das Gezeigte selbst die Sache.

**Folgerung:** Was Alammar zeigt, zeigt die Überblickskarte — den Mechanismus, am gewählten
Beispiel, im Erklärtext. Gewollt war darüber hinaus eine Aussage über Bedeutungskonstitution
auf einer eigenen Fläche, und die trägt die Bildform der Attention-Karte in keiner
Ausführung.

**Zur Zielformel selbst.** Der Satz „statistische Nähe bestimmt über Bedeutungsnetze —
das Gegenteil humaner Hermeneutik" stammt aus der Planung der Fläche und ist als
Vorgabe nicht gedeckt.
Inhaltlich vereint er zwei Glieder verschiedener Art: der erste folgt aus der Bauweise
eines auf Ko-Okkurrenz trainierten Modells, der zweite — menschliche Hermeneutik — liegt
außerhalb jedes Messapparats. Ein Nullbefund im Einbettungsraum wäre von niemandem als
Widerlegung angenommen worden; der Satz ist eine Prämisse, unter der gezeigt wird.
Hinzu kommt eine Falle am Endpunkt selbst: `POST /api/text/embedding/pair` zeigt, dass
ein Wortstück auf Schicht 0 in beiden Sätzen dieselbe Zahlenreihe trägt und durch die
Schichten auseinanderläuft — ungerahmt liest sich das als „das Modell erschließt aus
dem Zusammenhang", also als Ähnlichkeit zum hermeneutischen Zirkel.

**Betroffene Dateien:** `docs/devserver_todos.md` (Abschnitt Instrument 2, geschlossen).

**Quellen:** Alammar 2018, *The Illustrated Transformer*; Vaswani et al. 2017 (Basismodell
6 Schichten × 8 Köpfe); Jain & Wallace, NAACL 2019; Kobayashi et al., EMNLP 2020; Geva
et al., EMNLP 2021; Vig, ACL 2019 (System Demonstrations).

---

## 2026-08-23: Die CFG-Gegenleiter ist eingestellt

**Entschieden:** CFG hat zumindest bei SD 3.5 keine Bedeutung für die Guidance des Prompts.
Die Gegenleiter ist eingestellt und wird nicht ohne ausdrücklichen Auftrag wieder
aufgenommen.

**Material:** die Leiter auf SD 3.5 Large und SDXL, der Nullpunkt ohne Prompt, die Kreuzprobe
gegen ComfyUI, die Gegenleiter mit gedämpfter Parallelkomponente und fünf Zellen im
ComfyUI-Standard-Workflow.

**Ergebnis:** Die Dämpfung der Parallelkomponente ändert auf SD 3.5 Large weder den
Kontrastanstieg noch die Bindung; die Unterschiede liegen unter der Seed-Streuung. Die
Kreuzprobe zeigt den diffusers-Weg der Anlage innerhalb der Seed-Streuung ununterscheidbar
von ComfyUI.

**Folge:** Die Zusammenlegung von System-Prompts und Heiß & Kühl war hierauf geparkt und
ist ohne diese Spalte zu entscheiden.

**Was offen bliebe, falls es je wieder aufgenommen wird:** ein Richter, der räumliche
Relationen unterscheidet — der CLIP-Kosinus trennt „Pferd auf dem Dach eines Busses“ nicht
von „Pferd neben einem Bus“.

**Herkunft:** übernommen aus `docs/devserver_todos.md` beim Umzug der offenen Punkte nach
GitHub Issues (2026-09-08); die Datei ist damit entfallen.

---

## 2026-08-23: Die Bildlektuere wandert vom eigenen Instrument zum Agenten — und wird erbeten, nicht geschickt

**Anlass:** Der Bildvergleich in Compare funktionierte nicht und wird als Spalte entfernt;
der Agent uebernimmt die Bildlektuere, muss dazu die Medienprodukte der Seite sehen koennen,
und oekonomisch geht das nur nach Aufforderung.

**Das Instrument „Bildverstaendnis" ist weg** — Reiter, Route, Vue-Datei, System-Prompt,
Modell-Auswahl, Katalog-Eintrag, Adresse, Marke auf der Uebersichtskarte. Nicht das
Modell war falsch gewaehlt, sondern der Wortlaut der Aufforderung: gegen `qwen3-vl:4b`
gemessen gab „… Focus on subject, composition, colors, and style." 0 Zeichen in 3 von 3
Versuchen, „Describe this image in 2-3 sentences." 327 Zeichen, der Seh-Kanal des
Agenten (`describe_image_neutral`) 1075. Mit dem Wechsel auf diesen Kanal faellt die
Stelle ohnehin weg.

**Drei Informationsschichten, getrennt nach ihrem TRANSPORT**, damit Help nicht ueberlastet
wird:

| Schicht | Beispiel | Transport |
|---|---|---|
| allgemeines Plattformwissen | Bibliothek, andere Orte | HOLEN — die `lookup_*`-Werkzeuge |
| seitenspezifisch | der Katalog-Eintrag der Seite, ihre Ansprache | GEBEN — wenige Zeilen im System-Prompt |
| seitenbezogen situativ | die Bilder, die HIER gerade entstanden sind | das VERZEICHNIS wird gegeben, der INHALT geholt |

Die Trennung liegt genau hier: was dasteht, ist billig und darf mitgeschickt werden; was
darauf zu sehen ist, kostet einen VLM-Aufruf je Bild und wird nur auf Bitte geholt.

**Sehen ist ein eigener Schritt.** `view_run(run_id)` — Resonas vorhandenes Werkzeug samt
Fabrikations-Sperre — erreicht den Vergleichs-Agenten ueber einen NEUEN
Geltungsbereich `surface` in `tool_registry.py`, ausdruecklich NICHT ueber `default`:
`default` haette die Schnittmenge zwischen universellen und Resona-Werkzeugen
aufgeweicht, die `test_resona_memory.py::test_scope_overlap_is_exactly_the_granted_lookups`
und `test_platform_self_reference.py` als Invariante halten. Der Geltungsbereich wird pro
Zug gewaehrt, und nur wenn die Flaeche `surface_media` UND `may_open_media` schickt.

**Oekonomisch heisst: nur in einem Zug, den ein Mensch angefangen hat.** `sendMessage`
gibt `mayOpenMedia = true`, die Begruessung und der Kommentar nach dem Lauf geben
`false` — und behaupten nichts mehr ueber Bilder, sondern sagen, was zu sehen waere.
Der stille Beschreibungs-Lauf nach jeder Generierung ist ersatzlos weg (drei
VLM-Aufrufe je Lauf, die leer zurueckkamen). Gemessen auf dem Dev-Server: gefragt →
drei Laeufe geoeffnet, konkrete Unterschiede benannt, 32 s; ungefragt → null
Bildaufrufe, 8 s.

**Die Lupe gehoert der Flaeche, wenn die Flaeche den Lauf kennt.** Ein Druck auf das
Lupen-Zeichen einer `MediaOutputBox` erreicht sonst Help; auf den beiden
Vergleichs-Flaechen meldet die Flaeche ihre Laeufe an (`analysisEventStore.ownRuns`),
und `ChatOverlay` prueft das VOR seinem `consume()` — sonst haette es das Ereignis
geschluckt, bevor der Beobachter der Flaeche laeuft. Gewoehnliche Nachrichten an Help
tragen ausserdem kein `image_path` mehr; das Bild haengt nur noch an der Lupe.

**Betroffen:** `routes/chat_routes.py` (`_build_surface_media_context`, Werkzeug-Wahl,
`VLM_ANALYSIS_SYSTEM_PROMPT_TEMPLATE` und `/api/chat/vlm-models` entfernt),
`services/tool_registry.py`, `routes/schema_pipeline_routes.py` (drei Endpunkte und der
Lese-Streamer entfernt), `utils/vlm_safety.py` (`vlm_describe_image` entfernt),
`components/ComparisonChat.vue`, `components/ChatOverlay.vue`, `stores/analysisEvent.ts`,
`views/compare_hub.vue`, `views/compare/{model,language}_comparison.vue`,
`views/latent_lab.vue`, `views/latent_lab/flow_logic.vue`, `stores/pageAddress.ts`,
`i18n/en.ts` (+ WO-2026-08-23-C/D), `knowledge/platform_items.json`.
PART 33 und PART 35 tragen die Mechanik.

**Offen:** `knowledge/ailit_coverage.json`, Zuordnung
`engage-6--compare--14`, belegt „Engage 6" mit `views/compare/vlm_analysis_comparison.vue`
— diese Datei gibt es nicht mehr. Die Quelle ist `docs/ailit/zuordnungen.tsv`, gebaut von
`devserver/scripts/build_ailit_coverage.py`; ob die Zuordnung faellt oder auf einen
anderen Beleg geht, gehoert zum AILit-Abgleich, nicht hierher.

---

## 2026-08-20: Der unbedingte Zweig ist wieder unbedingt — keine eingebackenen Negativ-Prompts bei den Bild-Modellen

**Anlass:** Die fest eingebackenen Negativ-Prompts sind ein Erbe aus ComfyUI und SDXL und werden überall entfernt.

**Was der Satz technisch heisst.** Ein fest eingebackener Negativ-Prompt macht den unbedingten
Zweig der Diffusion nicht-unbedingt: er ist dann nicht auf nichts konditioniert, sondern auf
„blurry, bad quality, watermark, …". CFG extrapoliert vom unbedingten zum bedingten Zweig — mit
einer Floskel im Nenner schiebt es von dieser Floskel weg statt von nichts. Bei SDXL war das
Konvention, bei SD 3.5 und Flux ist es eine stille Verzerrung jedes Laufs, die niemand bestellt
hat und die in keiner Ausgabe sichtbar wird.

**Die Vorgabewerte der Bild-Modelle stehen jetzt auf dem leeren String** — SD 1.5, SDXL, SD 3.5
(large, large_img2img, Encoder Fusion, Vektor-Fusion, die beiden legacy-Chunks) und Flux 2. Das
betrifft die Ausgabe-Konfigurationen, die ComfyUI-Workflow-Knoten und `input_mappings`-Defaults
der Chunks, die `DEFAULTS` der diffusers-Chunks, den SD-3.5-Vorgabe-Satz in
`comfyui_workflow_generator.py` und den Startwert im Encoder-Fusion-Instrument. Die Schluessel
bleiben stehen; Code liest sie, ein fehlender Schluessel bricht Aufrufe. LTX Video faellt mit
darunter: seine Floskel ist ebenfalls SDXL-Erbe und keine Modellkarten-Vorgabe, und die
Konfiguration laeuft mit CFG 3,0.

**Die Verdrahtung bleibt unangetastet.** Wer selbst einen Negativ-Prompt eingeben will, kann das
weiterhin — entfernt ist die Floskel, nicht die Moeglichkeit.

**Wan 2.2 bleibt, wie es ist (Korrektur am selben Tag).** Der chinesische Negativ-Prompt der Wan-Konfigurationen ist kein SDXL-Erbe, sondern der
dokumentierte Satz der offiziellen Modellkarte; beide Live-Konfigurationen laufen ausserdem mit
CFG 1,0, wo die Fuehrungsformel gleich der bedingten Vorhersage ist und der negative Zweig
ohnehin kein Gewicht hat. Ebenso StableAudio: die drei Ausgabe-Konfigurationen tragen bereits den
leeren String.

**Nicht angefasst:** `schemas/configs/pre_output/image_safety_refinement.json`. Der Negativ-Prompt
ist dort kein eingebackener Wert, sondern wird vom Modell im selben Durchgang wie die Alters- und
Inhaltspruefung erzeugt, samt der Ausschluesse fuer kids und youth. Safety wird nicht nebenbei
entschaerft.

**Betroffen:** 8 Ausgabe-Konfigurationen unter `schemas/configs/output/`, 9 Chunks unter
`schemas/chunks/` (JSON und diffusers-Python), `schemas/engine/comfyui_workflow_generator.py`,
`views/surrealizer.vue`, `views/surrealizer_flow.vue` (dort auch die Seitenansprache, die den
festen Wert benannte).

---

## 2026-08-19 (nachmittags): Compare und LoRA Training sind Kategorien — ihre sieben Instrumente haben Adressen

**Anlass:** LoRA Training und Compare werden eigene Kategorien der Suite, Compare als erste,
weil am einfachsten zugaenglich, LoRA Training als letzte; ihre Instrumente bekommen Adressen
wie der Rest der Suite.

**Fuenf Kategorien, 22 Instrumente, eine Spalte.** Compare steht oben, weil es am wenigsten
voraussetzt; LoRA Training unten, weil es am meisten kostet — ein Lauf nimmt die Karte ein bis
drei Stunden und nichts anderes erzeugt waehrenddessen ein Bild. Dieser Satz steht am Eintrag
selbst (`latentLab.loraLab.tabs.lora.short`), nicht erst im Instrument, damit er VOR dem Klick
gelesen wird.

**Die Adressen** folgen der Regel von heute frueh — je Instrument eine, ohne Kategorie im Pfad:
`/latent-lab/model-comparison`, `…/language-understanding`, `…/image-understanding`,
`…/system-prompts`, `…/randomness`, `…/voices`, `…/lora-sd35`. `/compare` und `/training` sind
Weiterleitungen; sie stehen in Handouts.

**Compare gibt seine eigene Leiste ab**, wie das Lab am 2026-08-18: die sticky Reihe von sechs
Knoepfen in `compare_hub.vue` und ihr `localStorage`-Schluessel sind ersatzlos weg, die Wahl
kommt als Prop `tab`, die sechs Vergleichs-Ansichten sind unveraendert. LoRA Training wird
gerendert wie es ist.

**Zwei Knoepfe weniger im Top-Menue.** Compare und LoRA Training hatten je einen; sie sind nicht
mehr eigene Orte, und zwei Tueren in denselben Raum waren genau das, was am 2026-08-19 fuer
Encoder Fusion, Re-enactment und Decomposition aufgeloest wurde. Der Latent-Lab-Knopf leuchtet
fuer alle 22 Instrumente.

**Was still verlorengegangen waere, und nachgezogen ist:**
- `stores/pageAddress.ts`: die sieben neuen Adressen stehen einzeln in der Tabelle. Ohne sie
  waeren alle sieben auf die Ansprache des Labs zurueckgefallen und haetten das verloren, was
  Compare und LoRA Training ueber sich selbst sagen.
- `devserver/my_app/knowledge/platform_items.json` + `scripts/build_platform_items.py`: der
  Katalog, aus dem die Hilfe antwortet, fuehrt jetzt die ADRESSE jedes Instruments (bisher drei,
  davon zwei veraltet) und drei Instrumente, die ihm fehlten — Koreferenz-Test, Re-enactment,
  LoRA Training. Die IDs sind dabei NICHT umbenannt worden, obwohl Compare die Kategorie
  gewechselt hat: `chat_routes.py` und das `lookup_place`-Werkzeug adressieren ueber sie.
- `routes/chat_routes.py`: `ITEM_FOR_VIEW` kannte `latent_text_lab.compare` — ein Instrument, das
  heute frueh ausgemustert wurde; die Zeile zeigte ins Leere und ist weg. Dafuer kennt die Karte
  jetzt `latent_text_lab.coref`, `cover_band` und `TrainingView`.

Das ist die stehende Pflicht aus dem Eintrag vom 2026-08-18 (abends) eingeloest: jede korrigierte
oder neue Aussage ueber ein Instrument wird an den Katalog uebergeben, aus dem der Agent liest.

**Betroffen:** `views/latent_lab.vue`, `views/compare_hub.vue`, `router/index.ts`, `App.vue`,
`stores/pageAddress.ts`, `i18n/en.ts` (+ Arbeitsauftrag), `devserver/scripts/build_platform_items.py`,
`devserver/my_app/knowledge/platform_items.json`, `devserver/my_app/routes/chat_routes.py`,
`docs/ELEMENT_STRUCTURE_REGISTRY.md`.

---

## 2026-08-19: Eine Adresse je Instrument — und drei Seiten geben ihre eigene Tuer ab

**Anlass:** Die Kategorien koennen sich aendern, deshalb werden die Instrumente direkt
referenziert (`latent-lab/<instrument>`). Die fruehere Festlegung, dass Encoder Fusion zwei
Tueren hat, ist veraltet; Encoder Fusion, Re-enactment und Decomposition haben keine eigenen
Seiten mehr.

**Die Adresse.** `/latent-lab/:instrument?`, ohne Kategorie-Abschnitt. Welche Kategorie ein
Instrument traegt, leitet die Flaeche aus ihrem Katalog ab; eine Umgruppierung bricht damit
keinen einzigen Link. Ein nacktes `/latent-lab` oeffnet, wo die Besucherin aufgehoert hat, und
traegt das Instrument sofort in die Adresse nach — die Seite ist also von dort teilbar, wo sie
wirklich steht.

**Was in der Adresse steht, ist lesbar**, nicht das Werkstattkuerzel: `coreference-test` statt
`coref`, `representation-engineering` statt `repeng`, `audio-synth` statt `synth`. Die Kuerzel
bleiben innen unangetastet — die drei Lab-Dateien schalten weiter auf sie —, dazwischen steht
eine Zuordnung in `latent_lab.vue`. Adressen landen in Handouts und Lesezeichen; sie muessen
lesbar und tippbar sein.

**Drei Seiten verlieren ihre eigene Tuer:** Encoder Fusion (`/surrealizer`), Re-enactment
(`/cover-band`) und Decomposition (`/decomposition`). Alle drei sind Instrumente des Labs und
werden dort erreicht; die alten Adressen bleiben als Weiterleitung, weil sie in Handouts und
Lesezeichen stehen (`/silly-parrot` kettet ueber `/cover-band` mit). Die **Bauteile** bleiben
unveraendert — der Rahmen rendert dieselben Dateien, die die eigenen Seiten gerendert haben.

**Drei Verweise mussten nachziehen**, sonst waere still etwas verlorengegangen:
- `App.vue`: der aktive Zustand des Top-Menue-Knopfes verglich die Adresse auf Gleichheit und
  waere bei jeder Instrumenten-Adresse erloschen. Jetzt `startsWith('/latent-lab')`.
- `stores/pageAddress.ts`: die Tabelle ist nach Route geschluesselt und haette fuer alle
  fuenfzehn Instrumente nichts mehr gefunden. Ein unbekanntes `/latent-lab/…` faellt jetzt auf
  den Eintrag des Labs zurueck; Re-enactment behaelt seinen eigenen, weil es als einziges
  Instrument einen hatte.
- `LandingView.vue`: zeigt direkt auf die neue Adresse statt ueber die Weiterleitung.

**Betroffen:** `router/index.ts`, `views/latent_lab.vue`, `App.vue`, `views/LandingView.vue`,
`stores/pageAddress.ts`.

---

## 2026-08-18 (abends): Kein Seed im Kontroll-Instrument — Kontrolle gegen kontrollierten Kontrollverlust

**Anlass:** Nach Klärung der Mechanik entfällt der Seed im Kontroll-Instrument.

**Woran die Entscheidung hängt.** Temperature und Seed sitzen an zwei verschiedenen Stellen:
Temperature formt die Verteilung vor der Ziehung (`p ∝ exp(z/T)`), der Seed setzt den Zustand
des Generators, aus dem die Ziehung ihre Zahl nimmt. Bei **T = 0 wird gar nicht gezogen**,
sondern das wahrscheinlichste Token genommen — dort ist der Seed wirkungslos, und die
Wiederholbarkeit kommt daher, dass die Ziehung entfernt ist, nicht daher, dass sie
festgehalten wird. Die Beobachtung am lokalen Modell (T = 0, immer exakt dieselbe Antwort)
ist genau dieser Fall.

Sichtbar würde der Seed erst bei T > 0. Dafür fehlt die Verdrahtung: `gpu_service/services/
llm_backend.py` reicht weder an `Llama()` noch an `create_chat_completion()` einen Seed durch.
Auf der **Bildseite** liegt er dagegen überall an (`gpu_service/routes/diffusers_routes.py`)
und bleibt dort unangetastet — die Entscheidung nimmt nichts weg, sie baut nur nichts hinzu.

**Was damit entfällt.** Die Geste „zweimal derselbe Seed → identisches Ergebnis", also der
einzige vorführbare Beleg dafür, dass der künstliche Zufall eine aufgeschriebene Zahl ist.
Diese Stufe ist ohne Seed nicht herstellbar; sie kann nur behauptet werden.

**Was bleibt — und was das Instrument trägt.** Kontrolle gegen kontrollierten Kontrollverlust.
Der Regler (Temperature im Text, CFG im Bild) regelt nicht das Ergebnis,
sondern die **Weite dessen, was möglich ist**. Tragende Bedingung: **mehrere Ziehungen je
Einstellung**, nicht eine. Bei kleiner Stellung kommen mehrere fast gleiche Antworten zurück,
bei großer mehrere verschiedene — der Kontrollverlust ist dosiert, und die Dosierung ist die
Kontrolle. Ohne die Wiederholung bleibt es eine Regler-Seite; heute zieht jede Spalte genau
einmal.

**Offen, ausdrücklich nicht entschieden:**
- **Der Ort.** Mit Temperature UND CFG läuft das Instrument über zwei Mediensorten. Dann ist
  sein Ort das Crossmodal Lab, nicht das Latent Text Lab, wo die Konzeptdarstellung vom selben
  Tag es unter „System Prompts & Randomness" führt.
- **Keine vierte Spalte:** die paedagogische Bezugsliteratur wird nicht als
  Spalte einer Rechtfertigungstabelle gefuehrt und steht nicht auf der Flaeche. Der Agent traegt
  die Informationen. Die Agenten-Architektur fuer Help ist gebaut und traegt bereits zu jedem
  Instrument Informationen; sie ist **nicht** Gegenstand dieser Arbeit. **Stehende Pflicht aus
  dieser Konsolidierung:** jede korrigierte oder neue Aussage ueber ein Instrument wird dorthin
  uebergeben und nicht vergessen; das gilt fuer die Textkorrekturen der Quellenpruefung
  ebenso wie fuer alles, was hier neu entschieden wird.
- Der theoretische Rahmen (Mersch gegen Parisi) verliert ohne die Seed-Geste
  seinen vorführbaren Teil. Ob er trotzdem der Rahmen bleibt, ist nicht entschieden.

**Betroffen (bei Umsetzung):** `views/compare/temperature_comparison.vue`,
`views/compare/system_prompt_comparison.vue`, `views/latent_lab.vue`.

---

## 2026-08-18 (nachmittags): Encoder Fusion — zwei Flächen statt drei Spalten, und woher Breiten kommen

**Der Anlass.** Die vormittags gebaute Fassung hatte drei Spalten im Verhältnis 1 : 1,3 : 1. Das
Textfeld war darin 111 px breit — bei JEDER Fensterbreite, weil die Bühne den 1000-px-Deckel des
Flusses geerbt hatte und die `MediaInputBox` in ihrer schlanken Form fünf Symbole mal 32 px über die
ganze Höhe freihält. Ein Prompt kam zwei Wörter je Zeile heraus.

**Gesetzt:**
- Die Boxen tragen die Bezeichnungen und Symbole des Flow: die Knoten sind
  die des Flusses, Mediensymbole und Modell im ersten, das Dreieck allein im zweiten, das Bild im
  dritten. Kein Wort „Generierung", kein beschrifteter Knopf.
- Spalten, die eine Funktionseinheit bilden, werden zusammengezogen:
  Regler und Feldkarte sind eine Sache und stehen auf einer Fläche.
- Das Bild wird nicht doppelt gezeigt: es steht einmal, im dritten Knoten; die Reihe liegt unten.

**Die Regel, die daraus folgt (und die vorher fehlte):** vor jeder Flächengestaltung wird
aufgeschrieben, was jedes Element in der zu entscheidenden Dimension braucht — Textfeld ≥ 360 px
(45–75 Zeichen je Zeile), Reglermarken ≈ 370 px (längstes Wort), Feldkarte ≈ 350 px (sonst liegen
ihre Beschriftungen übereinander) — und ERST daraus folgen die Verhältnisse. Zahlen aus einer
fremden Geometrie zu erben ist keine Layout-Überlegung. Das Band steht dabei nicht über den Flächen: seine Geometrie ist
wörtlich die des Flusses, dessen Boxen die Spaltenbreite nicht ausfüllen,
also `W = 1060`, `H = 150` und die drei Rechtecke aus `RMAP` — Rand links, beide Lücken und Rand
rechts derselbe Wert 110, die Knoten nehmen 620 von 1060.

**Preis, offen:** mit der Ergebnis-Spalte fiel die `MediaOutputBox` weg und damit **Favorit und
Bildanalyse**. Herunterladen, Weiterreichen und Drucken liegen weiter an jedem Lauf in der
Ergebnis-Fläche; die beiden anderen haben auf dieser Form noch keinen Ort.

**Betroffen:** `views/surrealizer.vue`, `components/FlowHeader.vue` (`inline` ohne Breitendeckel,
auch auf `.fl-map`), `components/MediaInputBox.vue` (`actions-above`),
`components/SayableFieldMap.vue` (die Karte passt in den Kasten, den sie bekommt).

---

## 2026-08-18: Encoder Fusion — Band, drei Spalten, Ergebnis-Fläche; die T5-Erweiterung entfällt

**Entschieden:**
- „Ausführen" ist eine der mittleren Boxen oben. Gewichtung und Konsequenz-Anzeige kommen in
  die mittlere Säule, unterhalb der Generieren-Box.
- Die T5-Erweiterung erweitert destruktiv und entfällt, auch als Knopf. Mit der MediaInputBox
  stehen die Presets zur Verfügung; bei sehr kurzen Prompts erscheint unten eine Warnung mit
  dem Hinweis auf das Preset „Deine Geschichte".
- Schwelle: unter etwa 75 Token. Knotentitel: die des Flow.
- Ergebnis-Fläche pro Instrument, nicht im Rahmen: einzelne Anwendungen bekommen ihren
  Ergebnis-Minicanvas unten; für die meisten wäre das nicht sinnvoll.

**Begründung:** Die Erweiterung war ein zweiter, unsichtbarer Autor des Prompts neben den
sichtbaren Perspektiven — und sie schreibt ~200 Wörter an einen Text, dessen Kürze das
Instrument gerade zeigen soll. Die Perspektiven leisten dasselbe im Feld, sichtbar, und
werden wie jeder andere Prompt geprüft.

**Betroffen:** `views/surrealizer.vue`, `views/latent_lab/image_lab.vue`,
`components/FlowHeader.vue` (`placement`), `components/SayableFieldMap.vue` (`chrome`),
`components/canvas/OutputDrawer.vue` (`DrawerItem`), `views/canvas_workflow.vue`,
`assets/shell.css`, `devserver/my_app/routes/schema_pipeline_routes.py`,
`views/surrealizer_flow.vue`.

**Nicht angefasst:** die Fusions-Formel, `services/t5_expansion.py` (die Fusions-Werkbank
ruft sie selbst), Decompositions
expliziter `decomp_t5_prompt`-Überschreiber.

---

## 2026-08-18: Eine Anwendung zur Lehrforschung — LoRA Training und Compare werden Oberkategorien im Latent Lab

**Anlass:** LoRA Training kommt als vierte Kategorie in das Latent Lab, mit dem Menüpunkt
„Bild – SD3.5“, weil weitere LoRA-Trainer hinzukommen können.

**Vorschlag, am Objekt geprüft und konsistent:** Compare passt in das neue Layout. Dann gibt
es eine Anwendung zur Lehrforschung mit verschiedenen Oberkategorien, jede als Einstiegsseite
ihres Bereichs verlinkbar; die kategoriale Zuordnung wird weniger hart, die Zahl der
Menüpunkte sinkt von 1+7 auf 1+5, und jeder Modal-Tab verhält sich wie eine eigene
Software-Anwendung in einer konsistenten Suite.

**Warum das trägt (Prüfung am Stand von heute):**

1. **Es sind dieselben Bauformen.** Der Compare-Hub ist ein Reiter-Hub mit sechs
   eigenständigen Vergleichs-Seiten, das Latent Lab war bis heute früh derselbe Hub mit
   fünfzehn Instrumenten in drei Gruppen. Der Zusammenzug verschmilzt zwei Parallelstrukturen
   zu einer, wie `docs/ELEMENT_STRUCTURE_REGISTRY.md` es verlangt. Die Trainingsseite ist ebenso
   selbstständig gebaut und wandert unverändert als Instrument hinein.
2. **Der Rahmen steht schon.** `assets/shell.css` und die linke Spalte (`ModulePalette`)
   tragen seit dem Eintrag unten Canvas und Latent Lab. Compare ist der Umbau, der ohnehin
   ansteht; ihn als Oberkategorie zu setzen kostet keinen zweiten Rahmen.
3. **„Bild – SD3.5" benennt genau, was existiert.** Der Trainer fährt `sd3_train_network.py`
   mit `networks.lora_sd3` gegen `SD35_LARGE_MODEL_PATH` und legt seine Ergebnisse mit Präfix
   `sd35_` ab — SD3.5 Large und sonst nichts. Der Plural im Kategorienamen ist damit eine
   offene Stelle, keine Behauptung.
4. **Die Zahl stimmt.** Heute Startseite + sieben Knöpfe (Resona, Persona, x2x-Flow, Compare,
   Latent Lab, Canvas, LoRA Training). Compare und LoRA Training fallen als eigene Knöpfe weg
   → Startseite + fünf.

**Warum die kategoriale Zuordnung dadurch weicher wird.** Die Startseite ordnet nach
Handlungslogiken, die Suite nach dem Ort der Instrumente. Compare (Logik 4: die technisch
gefilterte Vielheit und ihre Grenzen als EINEN Sachverhalt), die Latent-Lab-Familie (Logik 5:
ästhetisch-sinnliches Erfahren der Innenräume) und LoRA (Logik 9: genAI mit eigenem Material
trainieren) bleiben drei verschiedene Logiken. Weil jede Oberkategorie als Einstiegsseite
ihres Bereichs verlinkbar sein soll, zeigt jede Logik direkt auf ihren Ort — die beiden
Ordnungen müssen nicht mehr dieselbe sein. Genau daher rührt die Härte der heutigen Zuordnung.

**Nichts davon ist gebaut.** Zu bauen wäre bei Umsetzung:

- Vierte Gruppe in `GROUPS` von `latent_lab.vue` mit `TrainingView` als Instrument.
- Compare als weitere Oberkategorie — hängt am Neuschnitt der Modus-Liste (siehe „Was
  NICHT entschieden ist" im Eintrag unten: System-Prompt und Temperature gehören inhaltlich
  zu Representation Engineering und Bias Archaeology, „Modell-Vergleich" im Text-Lab steht
  zur Streichung — damit erledigt sich zugleich der doppelte Name „Compare").
- **Routen pro Kategorie.** Heute merkt sich das Lab die Wahl nur in `localStorage`
  (`latent_lab_instrument`); ohne Routen gibt es nichts zu verlinken, und „als Einstiegsseite
  verlinkt" ist die tragende Eigenschaft des Vorschlags.
- Redirects für `/compare` und `/training` — beide stehen in Workshop-Handouts und
  Lesezeichen; das Muster liegt im Router bereits (Transform-Mode, Silly Parrot).
- Die vorgemerkte Freigabe-Sperre für Trainingsläufe (1–3 h GPU-Blockade, s.
  `docs/devserver_todos.md`) an der Kategorie sichtbar machen, sonst suggeriert die Suite
  Gleichverfügbarkeit, die sie nicht hat.
- `docs/AILIT_ORTE_ZUORDNUNG.md` nachziehen: Compare (7 Zeilen), Latent Lab (6) und LoRA
  Training (1) stehen dort als getrennte Orte. Jede Zeile am Objekt prüfen, nicht per Familie
  vererben.

**Der Name bleibt „Latent Lab".** Der Begriff des Latenten und der latenten Bedeutungsräume
ist eine Schlüsselkategorie für ein außerinformatisches Verständnis generativer KI und von KI
überhaupt. Der Name ist damit keine Sammelbezeichnung für das, was zufällig unter einem
Dach liegt, sondern benennt den Gegenstand der Suite — ein Obertitel darüber steht nicht mehr
zur Debatte, und keine der Kategorien wird umbenannt, um unter ihn zu passen.

**Betroffen (bei Umsetzung):** `views/latent_lab.vue`, `views/TrainingView.vue`,
`views/compare_hub.vue` + `views/compare/*`, `router/index.ts`, `App.vue`,
`docs/AILIT_ORTE_ZUORDNUNG.md`, `docs/devserver_todos.md`.

---

## 2026-08-18: Latent Lab, Compare und Canvas laufen durch EINEN Seitenrahmen — und die Modus-Wahl steht links

**Entschieden:** Latent Lab, Compare und Canvas bekommen weitestgehend gleiche Layout-Rahmen
und Elemente (Lage, Breite, Höhe) ohne neuen Code; alle drei laufen durch dasselbe zentral
konfigurierbare CSS. Die Modus-Wahl steht in einer linken Spalte, und die Lab-Titel stehen in
der Header-Zeile, in deren dezenter Typographie.

**Was daraus folgte:**

1. `assets/shell.css` ist der Rahmen — Kopfzeile, linke Spalte, Arbeitsfläche. Die Geometrie
   stammt wortgleich aus `canvas_workflow.vue`; Canvas trägt seitdem nur noch die Klassen.
   Aus `main.ts` geladen, damit eine Seite die Klassen nicht ohne den Rahmen tragen kann.
2. `ModulePalette` trägt beide Spalten, ohne einen Variantenschalter: **die Daten
   entscheiden.** Ein Eintrag mit `color` ist eine gefüllte Kachel (Canvas), ein Eintrag ohne
   `color` ist eine schlichte Zeile mit Aktiv-Balken links (Latent Lab). Das Ziehen hängt nicht
   daran, sondern an der Spalte: `draggable` schaltet es für alle Einträge auf einmal.
3. Die vier hand-kopierten Tab-Leisten des Latent Lab sind ersatzlos entfallen — drei hier, die
   vierte (`latent_text_lab.vue`) am selben Tag in `8c34b140`. `latent_lab.vue`
   besitzt die Wahl und reicht sie als Prop `tab` in die drei Lab-Dateien; deren `v-if`-Ketten
   bleiben unangetastet — sie werden dafür NICHT zerlegt.
4. Die drei Lab-Titel stehen in der Kopfzeile statt als größte Schrift auf einer Seite, deren
   Gegenstand das Instrument darunter ist.
5. Re-enactment hat seinen eigenen Knopf im Top-Menü verloren und ist der
   vierte Eintrag der Crossmodal-Gruppe. Die Route `/cover-band` bleibt.

**Was NICHT entschieden ist:** Compares linke Spalte hängt am Neuschnitt der Modus-Liste
(System-Prompt und Temperature gehören inhaltlich zu Representation Engineering und Bias
Archaeology, nicht zu einem Vergleich; „Modell-Vergleich" im Text-Lab steht zur Streichung).
Das Spaltenlayout der Instrumente wird einzeln entworfen, beginnend mit Encoder Fusion.

**Betroffen:** `assets/shell.css`, `components/canvas/ModulePalette.vue`, `views/latent_lab.vue`,
`views/latent_lab/{image_lab,crossmodal_lab}.vue`, `views/canvas_workflow.vue`, `App.vue`,
`views/{surrealizer,decomposition}.vue` (`min-height: 100vh` → `100%`, weil die Arbeitsfläche
nicht mehr das Fenster ist), `docs/ELEMENT_STRUCTURE_REGISTRY.md`.
(`views/latent_lab/latent_text_lab.vue` trägt seinen Teil bereits aus `8c34b140`.)

---

## 2026-08-15: Eigene Perspektiven behalten (P3) — wer, mit welcher Schaltung, und was nicht gebaut ist

**Entschieden:** Das Arbeiten an eigenen Configs braucht ein System: Wer kritische
Eigenaktivität unterstützen will, macht es zu einem einfach erreichbaren, gut sichtbaren,
komfortabel editierbaren und nachhaltig speicherbaren Prozess. Wer angemeldet ist, behält
seine eigenen Perspektiven.

**1. Wer behält.** JEDE angemeldete Person hält eigene Perspektiven — Teilnehmende
eingeschlossen, nicht nur Lehrende. Das Tor an `/api/interception-prompts/*` ist deshalb
`require_auth` und keine Rolle; der Entwurf v2 hatte dort `require_role(educator)`. Was ein KURS
zeigt, bleibt die Entscheidung seiner Leitung und liegt in der Palette
(`CoursePaletteItem`, `courses_routes.py`).

**2. Die Schaltung ist ein Ausschalter.** `AI4ARTSED_COURSE_PROMPTS=0` stellt den Weg vor P3 her;
ohne die Variable ist das Behalten AN. Der Bauplan verlangte „ohne Flag byte-identisches
Verhalten" — das gilt für die gegebenen Perspektiven weiterhin und ist geprüft (identisches
Objekt, nicht nur gleiches: `test_preset_resolves_to_the_very_same_object`). Für einen
`custom:`-Schlüssel gilt es bewusst nicht: mit Ausschalter löst er nicht auf, ohne ihn schon.
Begründung: der Sinn der Sache ist, dass Behalten ohne Umgebungsvariable erreichbar ist.

**3. Was eine Perspektive überhaupt sein kann,** entscheidet EIN Prädikat —
`is_offerable_perspective` in `my_app/services/course_prompt_resolver.py`: Interception-Stufe,
eine der beiden Text-Pipelines, nicht auf der Ausschlussliste des Wählers. Der Unterbau einer
behaltenen Perspektive (`base_config`), die Kurs-Palette und die Liste der gegebenen
Perspektiven fragen alle dort. Die Ausschlussliste steht zugleich im Wähler
(`InterceptionPresetOverlay.vue`, `EXCLUDED_IDS`) — ein Name darf nur in beiden oder in keinem
stehen.

**4. NICHT gebaut, bewusst: der Pflicht-Trockenlauf vor Aufnahme in eine Palette.** Der Entwurf
verlangt, dass eine Perspektive erst nach einem
Preview gegen einen Beispiel-Input in einen Kurs darf. Der Trockenlauf selbst ist gebaut
(`POST /api/interception-prompts/:id/preview`, echte Stufe 2, in derselben Warteschlange wie
jeder andere Modell-Aufruf, Alters-Stufe aus der Sitzung und nur verschärfbar). Die PFLICHT
ist es nicht: es gibt kein `previewed_at`, die Aufnahme verlangt nur `is_published`. Wer das
nachträgt, braucht eine Spalte auf `InterceptionPrompt` und eine Wanderung der bestehenden
`devserver/var/lab.db`.

**5. Ebenfalls offen:** eine behaltene Perspektive kann in eine Kurs-Palette, wird
Teilnehmenden im Wähler aber noch nicht angeboten. Daran hängt die Frage, ob Teilnehmende den
Wortlaut ihrer Leitung lesen und ändern dürfen — nicht entschieden. Der Hinweistext im
Kurs-Editor (`educator.paletteKeptHelp`) sagt das so.

**Betroffene Dateien:** `my_app/routes/interception_prompts_routes.py`,
`my_app/services/course_prompt_resolver.py`, `my_app/routes/courses_routes.py`,
`my_app/routes/schema_pipeline_routes.py` (`_resolve_interception_config`),
`schemas/engine/chunk_builder.py`, `tests/test_lab_prompts.py`,
`views/x2x_flow.vue`, `components/InterceptionPresetOverlay.vue`,
`views/educator/CourseEditor.vue`, `stores/keptPerspectives.ts`.

---

## 2026-08-13: Die Decomposition wird entkoppelt — geplant wird sie erst mit der neuen Latent-Lab-Fläche

**Nachtrag 2026-09-19:** erledigt durch die Entfernung des Instruments (Eintrag 2026-09-19).

**Entschieden:** Die Decomposition wird entkoppelt. Dafür muss die Seite zuerst verständlich
und vom UI/UX her sinnvoll umgebaut werden; sie wäre dann ein Template für zwei oder drei
Seiten, oder sie bleibt schaltbar und kombinierbar mit Ausblendungen im UI. Das UI des Latent
Lab wird in Kürze umgestellt (Instrumente in der linken Spalte, horizontale Ausrichtung ohne
Scroll, ähnlich der Fläche des Canvas-Instruments); die Planung folgt dieser Umstellung.

**Was entkoppelt wird.** Die Interventionsmatrix bedient heute in einem Griff vier verschiedene
Fragen, und eine fünfte fehlt ganz:

| Bedienelement | Frage |
| --- | --- |
| L / G / T je Zelle | Wie teilen sich die drei Textencoder die Arbeit? |
| Spalten Komposition / Semantik / Detail (Schritte 1–8, 9–17, 18–25) | Wann im Entrauschen entscheidet sich was? |
| Zeilen Früh / Mittel / Spät (Blöcke 0–9, 10–22, 23–37) | In welcher Tiefe des Transformers entscheidet sich was? |
| α von −1 bis +1 | Ersetzen, überblenden oder gegensteuern? |
| — | **Stummschaltung eines Encoders — nicht erreichbar** |

Das Instrument vermischt zwei verschiedene Dinge, Alternativprompt-Injektion und Stummschaltung
von CLIP-Anteilen im Vektor; unklar ist, was gemessen wird, weil mehrere Instrumente
ineinandergeschoben sind.

**Zwei Wege stehen offen:** die umgebaute Seite wird Vorlage für zwei oder
drei getrennte Seiten; oder sie bleibt eine Seite, deren Teile sich schalten und kombinieren
lassen und deren nicht gewählte Teile ausgeblendet werden. Die Wahl fällt zusammen mit dem
Layoutwechsel, nicht davor.

**Warum jetzt nichts gebaut wird.** Das Latent Lab bekommt in Kürze eine andere Fläche:
Instrumente in der linken Spalte, horizontale Ausrichtung ohne Scrollen, nach dem Vorbild des
Canvas-Instruments. Eine Seite, die vorher nach heutiger Fläche umgebaut wird, wird zweimal
gebaut.

**Sachstand, auf den die Planung aufsetzt** (gemessen 2026-08-12/13):
- Die Encoder-Wahl wirkt: drei Encoder, drei sichtbar verschiedene Bilder bei sonst gleicher Lage.
- Die neun Zellen sind **nicht gleichwertig**. Das Delta wird nur am Eintrittsblock eines Bandes
  addiert (`make_block_hook`: `if block_idx != band_lo: return None`). „Früh" sitzt vor allen 38
  Blöcken und wirkt durch; „Spät" steigt bei Block 23 ein. Das Raster behauptet neun vergleichbare
  Messpunkte und hat einen starken und acht schwache.
- `pooled_prompt_embeds` bleibt immer der Quell-Prompt (`diffusers_backend.py:2405`) und moduliert
  über adaLN jeden Block. Kein Zellentext kommt global dagegen an.
- Die Stummschaltung wäre billig: dieselben Scheiben (`DECOMP_STREAM_SLICES`), derselbe Hook, als
  Operand die Null-Text-Kodierung, die als `src_neg_embeds` in derselben Funktion schon vorliegt.
- Die Zeilenbeschriftung „Früh / Mittel / Spät" benennt Tiefe mit Zeitwörtern, während die Spalten
  daneben echte Zeit benennen.

**Affected files:** noch keine — `public/ai4artsed-frontend/src/views/decomposition.vue`,
`gpu_service/services/diffusers_backend.py` und die künftigen Geschwisterseiten werden mit dem
Layoutwechsel geplant.

---

## 2026-08-11: Die RTX 4090 ist deprecated — das bestehende 4090-Deployment bleibt als Legacy

**Entschieden:** Die RTX 4090 ist deprecated; die Plattform fordert eine RTX ab 5090, und das vorhandene 4090-Deployment bleibt als Legacy.

**Was das zur Notiz vom 2026-08-08 hinzufügt.** Dort stand, dass gegen **Blackwell ab RTX 5090** entwickelt wird. Offen blieb, was mit der 4090 geschieht. Sie ist jetzt **kein unterstütztes Ziel mehr**: keine neue Fähigkeit wird gegen 24 GB entworfen, kein Modell wird ausgewählt, weil es dort noch hineinpasst, und kein Befund von dieser Karte begründet eine Einschränkung der Plattform.

**Legacy heißt: läuft weiter, wächst nicht mit.** Der bestehende Produktionsrechner (ubuntu, RTX 4090, deploy-only, siehe `docs/installation/DEPLOYMENT_REPORT_2026-05-17.md`) wird nicht abgeschaltet und nicht umgebaut. Was dort heute läuft, läuft weiter. Neues kann dort ausfallen, und das ist dann **kein Deployment-Fehler**, sondern die erwartete Folge dieser Entscheidung. Wer dort etwas vermisst, braucht eine neuere Karte, keinen Fix.

**Anlass.** Für die Stimmen-Vergleichsseite steht ein neueres Sprachsynthese-System an. Die Frage, wieviel VRAM neben Qwen3-TTS auf der 4090 frei bleiben muss, stellt sich damit nicht mehr — sie wird gegen 5090 aufwärts (32 GB) beantwortet, und die 4090 ist nicht mehr die Schranke.

**Affected files:** `docs/installation/INSTALLATION.md` und `docs/installation/QUICKSTART.md` (beide nannten die 4090 als Weg, das Minimum zu erfüllen — jetzt korrigiert), `docs/installation/CURRENT_DEPLOYMENT_PLAN.md` (Profil C führt 4090 und 5090 zusammen; als Planungsdokument unverändert, die Zusammenfassung gilt für den Bestand), `docs/DEVELOPMENT_DECISIONS.md`.

---

## 2026-08-09: Schrift und Stimme laufen zusammen, und EIN Schalter entscheidet über beides

Vier Entscheidungen an einem Tag, die zusammengehören. Der gebaute Stand steht in
`docs/ARCHITECTURE PART 39 - Platform-Voice.md`; hier steht, was entschieden wurde und warum.

### 1. Der Ablauf: Satz, Vertonung, dann der nächste

Ein Text wird in Sätze aufgeteilt, und die Sätze werden nacheinander als Text ausgegeben. Die
Vertonung läuft ebenfalls satzweise, und jedes Audio wird mit seinem Satz ausgegeben.

Die Schleife taktet sich selbst: solange der laufende Satz nicht zu Ende gesprochen ist, passiert
nichts. **Was zuerst fertig ist — Text oder Audio — gibt den nächsten frei.** Deshalb gibt es
keine Fristen: eine Uhr neben einem sich selbst taktenden Ablauf ist eine zweite Wahrheit. Ein
Server, der hängt, ist ein Serverproblem und wird dort behoben; ein Server, der einen Fehler
meldet, beendet die Äußerung ordentlich und gibt die Worte frei.

Verworfen: eine Frist von zunächst 12, dann 45 Sekunden, mit der die Worte notfalls von der
Stimme gelöst worden wären (`a4c12b1f`). Gemessen wären 12 s im Normalbetrieb regelmäßig
gefeuert — bis zum ersten Ton vergingen in zwei Läufen 14,3 s und 19,8 s.

### 2. Wort für Wort statt Satz für Satz — über die gemessene Spanne, nicht über Alignment

Die Kopplung soll feiner sein, damit Lesen und Hören gleichzeitig enden und keine Irritation
zwischen Lesen und Hören entsteht. **Echtes Wort-Alignment gibt das Modell nicht her** (am
Gegenstand geprüft, siehe der Eintrag weiter unten). Gebaut ist stattdessen: `soundingPiece`
trägt die am Clip **gemessene** Spanne des klingenden Satzes, und der Einlauf der Zeichen wird
über genau diese Spanne verteilt. Ein Satz ist damit in dem Moment zu Ende gelesen, in dem er zu
Ende gesprochen ist; innerhalb des Satzes steht ein Wort proportional, nicht ausgerichtet.
Aufsummieren kann sich der Fehler nicht, weil jeder Satz von einer neu gemessenen Spanne startet.
Gemessen an der Werkstatt: dreizehn Sätze, das Schreiben endet durchweg 76 bis 192 ms vor dem Ton.

### 3. Ein Schalter im Hauptmenü, EINE Drosselstelle

`voiceChat` im `userPreferences`-Store (localStorage, Vorgabe **an**), Knopf im Hauptmenü links
neben der Farbauswahl. Gelesen wird er **an genau einer Stelle**: `isAvailable` in `useSpeech.ts`.
Alles, was spricht, geht durch `speak()`; alles, was Stimme anbietet, fragt `isAvailable`. Damit
kann keine Oberfläche eine Stimme behalten, die die hörende Person stummgeschaltet hat, und keine
Figur führt eine eigene Kopie der Frage — ausdrücklich **ohne Parallelstruktur**.

Der Schalter erreicht den Server nie. Er entscheidet, ob **dieser Browser** die Plattformstimme
hört, sonst nichts; Safety-Rollen und Caption laufen auf eigenen Wegen und sehen davon nichts.

Damit verbunden: **Help spricht überhaupt erst.** Sie war nie an die Stimme angeschlossen —
`useSpeech` wurde von genau zwei Dateien importiert. Kein Knopf je Antwort: ein Gespräch, das man
erst anklicken muss, ist ein Text mit Knopf. Und **Persona meldet dem Server Schrift**, wenn der
Schalter aus ist; sonst bekäme die Figur im GIVEN-VOICE-Block gesagt, sie werde gehört, während
nichts klingt.

### 4. Contesting wartet nicht auf die Stimme

Contesting spricht jede Antwort von selbst, und die stehenden Worte hingen hinter dem Audio:
Satz 1 sofort, jeder weitere erst mit seinem Clip. Die Antwort ist aber ganz da — das LLM
antwortet in einem Zug —, und bei 1 bis 5 s Synthese plus rund 6 s Sprechzeit je Satz stand der
letzte Satz einer achtsätzigen Antwort etwa eine Minute nach der Antwort. Contesting wirkte
dadurch träge; das LLM generiert die Antwort in einem Zug, und die Ausgabe muss die Sätze
aufteilen.

Die Kopplung bekommt dafür ein Feld `pace`; Contesting setzt es auf `false`. Die Antwort steht
ganz, in Sätze geteilt, die Stimme läuft daneben. **Die Werkstatt bleibt gekoppelt** — dort sind
Schrift und Stimme eine Sache.

### Nachtrag: Entwurfsgründe gehören nicht in Prompts

Aus der Eröffnungsanweisung von Contesting entfernt: „No name is given, because there is none."
(`f0f8a5f4`, eingebracht mit `19ecad2f` am selben Tag). Ein Entwurfsgrund in einem Prompt wird
von der Figur vorgetragen — die Maschine hätte ihre eigene Namenspolitik erklärt, ohne dass
jemand fragt. Ersatzlos; sich nicht zu benennen braucht keine Anweisung, und der plattformweite
Abschnitt zur Selbstbezeichnung deckt den Fall ab, dass doch jemand fragt. Gleiche Familie wie die
zwei gestrichenen GIVEN-VOICE-Passagen (`6ac593ab`).

**Affected Files:** `composables/useSpeech.ts`, `components/ResonaVoice.vue`,
`views/ai_persona.vue`, `views/resona.vue`, `components/ChatOverlay.vue`, `App.vue`,
`stores/userPreferences.ts`, `i18n/en.ts`, `devserver/my_app/routes/chat_routes.py`,
`docs/ARCHITECTURE PART 39 - Platform-Voice.md`, `docs/ARCHITECTURE PART 32` (veraltete
Browser-TTS-Passage korrigiert).

**Offen:** Der Schalter ist nutzersichtbar und in `DokumentationModal.vue` noch nicht beschrieben.

---

## 2026-08-09: Keine animistischen Repräsentationen — die Maske tritt an die Stelle der Figur

**Entschieden:** Die Plattform nimmt Abstand von animistischen Repräsentationen, zum Preis
einer gesenkten Identifikationsfähigkeit mit Aktanten der Plattform, weil genau diese
Identifikation ein problematisches Verhältnis zur KI etabliert.

**Was daraus folgt.** Die Figur mit Gesicht und Namen (Träshy) wird plattformweit durch ein
Zeichen ersetzt: die Theatermaske (Material Symbols `theater_comedy`, als eingebettetes SVG mit
`fill="currentColor"`). Eine Maske wird getragen und hat kein Inneres — sie zeigt an, dass eine
Rolle gespielt wird, und bietet nichts an, mit dem man sich identifizieren könnte. Ersetzt wird
auch das Gesicht im geöffneten Helferfenster: eine Ausnahme genau dort, wo die Kinder mit der
Figur sprechen, würde die Regel aufheben.

**Die Bewegungs-Vorgabe.** Der Ruhezustand trägt die Mikro-Bewegung der alten Figur, und nur
der Ruhezustand (4s, Versatz bis 2px/−5px, Drehung ±1°). Die Entscheidung gegen animistische
Repräsentationen betrifft die REPRÄSENTATION — Figur mit Gesicht und Namen → Maske —, nicht die
Bewegungssprache. Sie wird nicht auf die Ruhe-Bewegung ausgedehnt. Die Zustände:

| Zustand | Anzeige | Bedeutung |
|---|---|---|
| idle | Mikro-Bewegung (4s, Versatz + leichte Drehung) | die Maschine arbeitet nicht |
| waiting | Größenpuls (~±6 %) | es wird gerechnet |
| uttering | drei Klammern je Seite, dunkel → hell nach außen laufend | es klingt |
| held | still, etwas heller | fertig synthetisiert, wartet auf eine Berührung |

`held` pulsiert bewusst nicht: ein Puls sagt „warte", dieser Zustand sagt das Gegenteil — es kommt
nichts mehr, bis ein Mensch tippt. `waiting` ist ausschließlich Größenpulsieren, ohne Helligkeitsänderung daneben. Rotation und
Regenbogen-Farbwechsel bleiben ungenutzt und stehen als Reserve, falls ein weiterer Zustand nötig
wird; Rotation läge zu nah an emotionalem Ausdruck. Bei
`prefers-reduced-motion` entfällt alle Bewegung, auch die des Ruhezustands, und die Zustände
unterscheiden sich nur noch über Helligkeit.

**Empirischer Hintergrund — er belegt den Anlass, nicht einen Einwand.** In den Interviews mit
Studienteilnehmenden wird die Figur ausdrücklich als das genannt, was bei den Kindern ankam
(„Die Kinder fanden das total super und auch Trashy und so"). Genau diese Zuneigung ist der
Gegenstand der Entscheidung. Der Preis ist benannt und wird bewusst bezahlt.

**Farbe: Werkstoffe, keine Signalfarben.** Die Maske trägt je Kontext eine Farbe, und die Farbe
bezeichnet eine **Modalität der Situation, nie eine Identität**: Farben zeigen Stimmungen und
Modalitäten an, keine Personen.
Gewählt sind Pigmente einer Werkstatt, nicht Farben einer Oberfläche — Bauhaus scheitert hier
nicht am Werkstattgedanken, sondern am Licht: die Plattform ist ein dunkler Raum mit warmem
Arbeitslicht, ungebrochene Primärfarben würden darin als Kontrollleuchten wirken.

| Token-Wert | Werkstoff | Ort |
|---|---|---|
| `#ffb300` | Arbeitslicht (der vorhandene Bernstein) | Vorgabe für alles ohne eigene Modalität |
| `#63A88C` | Grünspan — das Grün auf bearbeitetem Metall | Werkstatt (`views/resona.vue`); nie gesetzt, am 2026-10-10 als Token ohne Leser gestrichen (Befund S-135 der Code-Sichtung vom 2026-10-10) |
| `#B85C48` | Eisenoxid — ältestes Pigment, Grundierung auf Stahl | Widerspruch (`views/ai_persona.vue`); nie gesetzt, am 2026-10-10 als Token ohne Leser gestrichen (Befund S-135) |
| `#5C8CB0` | Blaupause — Blau der technischen Zeichnung | Helfer, angelegt, noch nicht vergeben |

Der Fluss bekommt **keine** eigene Farbe: ein Arbeitstisch hat keine Stimmung, er hat eine
Beleuchtung. Sobald jede Seite eine Farbe trägt, hört Farbe auf, Modalität zu bezeichnen, und wird
zur Ortsmarke.

**Die Farbe trägt die Maske und ihre Kontur — sonst nichts.** Keine Fläche, kein Rahmen, kein
Hintergrund. Begründung aus demselben Interviewmaterial: die Oberfläche wird als „reizarm und ein
bisschen kompliziert", „ultra reduziert" beschrieben, und genau das erzeugt die
Konzentrationsatmosphäre, in der gearbeitet wird. Das Material trennt dabei zwei Dinge, die nicht
zusammenfallen: **Konzentration** entsteht durch Reduktion, **Orientierung** durch Icons und
Übersichtlichkeit. Farbe gehört zur Orientierung.

**Betroffene Dateien.** Neu: `components/FigureMask.vue`. Übernahme in zwei Durchgängen —
zuerst `components/ChatOverlay.vue` (der plattformweite Helfer aus `App.vue`), danach
`components/PlatformVoice.vue` (Ursprung der Plattformstimme), `components/ResonaVoice.vue`
(Präsenz in der Werkstatt), `components/ComparisonChat.vue` und `views/workshop_planning.vue`
(stillgelegt). Farb-Token auf den Seitenwurzeln von `views/resona.vue` und `views/ai_persona.vue`.

---

## 2026-08-09: Wo die Sprachsynthese läuft und wie schnell — gemessen

**Wo:** auf der **CPU**. `onnxruntime` bietet in diesem venv nur `CPUExecutionProvider` und
`AzureExecutionProvider`, kein CUDA. Die Stimme steht damit **nie hinter einer
Bildgenerierung** — das ist ein anderer Prozess auf der GPU, und die Stimme fasst die GPU nicht
an. Serialisiert wird ausschließlich Sprache gegen Sprache, durch `_synth_lock` in
`my_app/services/supertonic_backend.py`. (Der Kommentar in `useSpeech.ts`, der von einem „GPU
lock“ sprach, war falsch und ist korrigiert.)

**Wie schnell (Dev-Server, 2026-08-09):** ein Satz von 96 Zeichen ergibt ~6,4 s Audio. Derselbe
Satz dreimal einzeln synthetisiert: 0,97 s / 4,63 s / 1,01 s — der schon dokumentierte schnelle
und langsame Durchgang des Modells, gleicher Text, byte-gleiche Ausgabe.

**Was daran zählt:** die Synthese ist schneller als das Abspielen. Innerhalb einer Äußerung sind
die Stücke also fertig, bevor sie gebraucht werden, und der Ablauf — Satz als Text, seine
Vertonung dazu, danach der nächste Satz — läuft ohne Warten durch.

**Kein Wort-Alignment — am Modell geprüft.** Die vier ONNX-Modelle geben zusammen genau vier
Ausgänge: `duration` (**eine** Zahl je Text, Shape `(1,)`), `text_emb`, `denoised_latent`,
`wav_tts`. Nirgends eine Zuordnung von Zeichen zu Zeit. Eine Kopplung von Schrift und Stimme
unterhalb des Satzes kann daher nur über die **gemessene Satzspanne** laufen (Zeichen proportional
darüber verteilt), nicht über eine Ausrichtung — und Wörter einzeln zu synthetisieren scheidet
aus, weil das Modell bei Fragmenten eine Fortsetzung erfindet (der Befund, auf dem
`splitForSpeech` beruht).

**Nebenzahl, ohne Schluss daraus:** mehrere gleichzeitige Anfragen stauen sich hinter dem Lock,
linear. Vier Anfragen: 7,3 s bis zur letzten; acht: 15,7 s; sechzehn: 28,4 s.

**Affected Files:** keine Änderung; `public/ai4artsed-frontend/src/composables/useSpeech.ts`
(Kommentar korrigiert, `ea3bdeed`).

---

## 2026-08-08: Stimm-Politik — die Stimme der Plattform ist gemischt, und das ist die Aussage

**Decision:** Die Plattform spricht mit **Supertonic 3**, und ihre Stimme ist **keine der mitgelieferten Preset-Stimmen**, sondern eine lineare Mischung mehrerer. Beim Abhören hält die Mischung die Balance zwischen nicht-human und nicht robotisch.

### Die Regel

> **Der weibliche Anteil einer Mischung liegt nie unter 60 Prozent.**
> Bei zwei Männerstimmen (MMF) trägt die eine Frauenstimme 60, die beiden Männerstimmen teilen sich 40.
> Bei zwei Frauenstimmen (FFM) ergibt sich das von selbst — Gleichverteilung sind schon zwei Drittel.
> Gleichverteilung über eine MMF-Mischung ist **verboten**.

**Wonach die Regel bemisst:** nicht nach einer Zielfrequenz, sondern danach, dass **kein Lauf ins Männliche kippt**. Das ist das Kriterium: Männliche Dominanz ist zu vermeiden. Schwankung an sich ist ausdrücklich **kein** Problem — sie passt zu einer Stimme, die kein Subjekt behauptet.

### Warum die Regel nötig ist — gemessen am 2026-08-08

Sechs Läufe je Mischung, derselbe Satz, Grundfrequenz-Median je Lauf:

| Mischung | weiblicher Anteil | Median | Spanne über 6 Läufe | ins Männliche gekippt |
|---|---|---|---|---|
| F3 · M2 · M4 zu Dritteln | 33 % | 106 Hz | 85–120 | **alle sechs** |
| F4 · M2 · M4 zu Dritteln | 33 % | 95 Hz | 88–101 | **alle sechs** |
| F4 50 : M4 50 | 50 % | 172 Hz | 110–188 | zwei |
| F4 50 : M2 50 | 50 % | 97 Hz | 88–173 | fünf |
| **F3 60 · M2 20 · M4 20** | 60 % | 158 Hz | 120–167 | keiner |
| **F4 60 · M2 20 · M4 20** | 60 % | 179 Hz | 165–182 | keiner |
| **F3 60 : M4 40** | 60 % | 149 Hz | 142–174 | keiner |
| **F4 60 : M4 40** | 60 % | 185 Hz | 180–195 | keiner |
| F3 · F4 · M4 zu Dritteln (FFM) | 67 % | 167 Hz | 145–181 | keiner |
| F3 · F4 · M2 zu Dritteln (FFM) | 67 % | 151 Hz | 142–159 | keiner |
| F1 · F3 · M4 zu Dritteln (FFM) | 67 % | 164 Hz | 149–206 | keiner |

Zum Vergleich die reinen Stimmen: F4 190 Hz (Spanne 11), F3 158 Hz (42), M4 107 Hz (11), M2 86 Hz (12).

**Nachtrag am selben Tag, nach der Auslieferung — die Regel allein reicht nicht.**
Sechs Läufe je Gewichtung waren zu wenig. Bei zwanzig Läufen je Stimme fällt jede
der fünf gelegentlich unter die Linie, und die Mischungen mit M2 werfen einzelne
Läufe bei 97, 102 und 115 Hz — das ist nicht knapp daneben, das ist die
Männerstimme. Die damalige Standardstimme `even` fiel in **neun von zwanzig**
Läufen darunter.

| Stimme | Median | tiefster Lauf | unter 140 Hz, ungeschützt | mit Wache |
|---|---|---|---|---|
| clear (F3 · F4 · M4) | 156 Hz | 133 | 1 von 20 | **0 von 20** |
| bright (F4 60 · M2 20 · M4 20) | 179 Hz | 102 | 3 von 20 | **0 von 20** |
| low (F3 60 · M2 20 · M4 20) | 152 Hz | 131 | 4 von 20 | 1 von 20 |
| mid (F3 · F4 · M2) | 153 Hz | 97 | 4 von 20 | **0 von 20** |
| even (F3 60 : M4 40) | 150 Hz | 126 | 9 von 20 | 3 von 20 |

Der Grund liegt in der Bauart: Supertonic ist Flow Matching, jeder Aufruf startet
von einer frisch gezogenen Rauschprobe. Die Gewichtung legt fest, wo die
Verteilung liegt, nicht, wo der einzelne Lauf landet.

**Ein Seed behebt das nicht** — er legt fest, welche Probe gezogen wird, nicht,
wo das Ergebnis für einen *neuen* Satz landet, und jeder Satz ist neu. Das ist
aber kein Argument gegen den Seed, sondern nur eines dagegen, ihn für dieses
Problem zu halten. Siehe die Korrektur unten.

**Was es behebt, ist eine Wache nach der Synthese.** `supertonic_backend`
misst die Grundfrequenz jeder Äußerung und zieht neu, wenn sie unter
`SUPERTONIC_MIN_F0_HZ` (140 Hz) liegt, bis zu `SUPERTONIC_F0_REDRAWS` mal;
behalten wird der höchste Versuch, nicht der letzte. Die 140 Hz sind die Lücke:
die reinen Presets liegen männlich bei 86–137 Hz und weiblich bei 157–197 Hz,
dazwischen landet von diesem Modell nichts. Kostet auf die seltene Gelegenheit
eine weitere Synthese; im Mittel 0,83 s statt 0,5 s bei der Standardstimme.

Die Standardstimme ist deshalb **`clear`** (F3 · F4 · M4 zu Dritteln) und nicht
`even`: sie ist mit Wache sauber und zugleich die schnellste. `low` und `even` —
die beiden 60-Prozent-Mischungen — rutschen auch mit Wache noch gelegentlich auf
134 bis 139 Hz. Das sind ein bis sechs Hertz unter der Linie statt fünfzig, aber
es ist nicht null. Wer Sicherheit will, nimmt eine der 67-Prozent-Mischungen.

**Der Befund in einem Satz:** die Männerstimme zieht überproportional. Bei Gleichverteilung über zwei Männerstimmen landet die Mischung nicht in der Mitte, sondern praktisch auf der Männerstimme — 95 bis 106 Hz gegen 190 Hz der beteiligten Frauenstimme. Bei 50:50 wird die Mischung zusätzlich **instabil**: sie sitzt zwischen zwei Anziehungspunkten, und das Rauschen entscheidet je Lauf, wohin sie fällt (F4 50 : M4 50 schwankte über 78 Hz). Erst ab 60 Prozent weiblichem Anteil hält die Mischung ihren Ort.

### Warum gemischt und nicht gewählt

Supertonic liefert zehn feste Stimmen, fünf als männlich und fünf als weiblich benannt. Eine dritte Kategorie gibt es nicht, und es gibt keinen Regler für die Stimmlage — `synthesize` kennt nur `speed`.

Eine der zehn zu wählen hieße, für die Plattform eine Person zu setzen: einen Sprecher oder eine Sprecherin, mit Geschlecht, Alter und Rolle. Genau das soll die Stimme der Plattform nicht sein. Sie ist kein Gegenüber mit Biografie, sondern die hörbare Seite einer Maschine, die Material verwandelt. Eine Stimme, die sich keiner Seite zuschlägt, sagt das, ohne dass es irgendwo dazugeschrieben werden müsste.

Die Mischung ist deshalb auch kein *Effekt*. Sie ist keine Verfremdung einer eigentlich vorhandenen Person, sondern der Verzicht darauf, eine zu behaupten.

### Wie das technisch geht

Der Stil steckt in zwei fortlaufenden Tensoren (`supertonic.core.Style`): `ttl` (1, 50, 256) für die Lautbildung, `dp` (1, 8, 16) für die Dauern. Beide lassen sich linear kombinieren — undokumentiert, aber tragfähig:

```python
def stil(gewichte):                      # {"F3": 0.60, "M2": 0.20, "M4": 0.20}
    return Style(
        style_ttl_onnx=sum(g * E[n].ttl for n, g in gewichte.items()).astype(np.float32),
        style_dp_onnx=sum(g * E[n].dp for n, g in gewichte.items()).astype(np.float32))
```

Jede Gewichtung, die sich zu eins summiert, ergibt eine Stimme.

**Die Grundfrequenz ist keine verlässliche Vorhersage.** Die Mischung ist nicht monoton: F4 (190 Hz) mit M4 (107 Hz) zu gleichen Teilen ergab in einer Reihe 122 Hz, in einer anderen 185 Hz. Betriebsregel daraus: **eine Handvoll Gewichtungen festschreiben und benennen — keinen stufenlosen Regler in die Oberfläche geben.** Ein Regler verspricht eine Gleichmäßigkeit, die das Modell nicht hält.

**Der Zufall wird gesetzt, aber nicht festgesetzt.** ~~Der Zufall ließe sich festsetzen, wird aber nicht festgesetzt … Wir tun das **nicht**.~~ — korrigiert am selben Tag: Varianz ist gewollt, und das ist kein Grund, den Seed wegzulassen. Beides zusammen geht.

Das Rauschen kommt aus `np.random.randn` in `supertonic/core.py:458`; ein `np.random.seed(n)` unmittelbar vor dem Aufruf liefert byte-identische Ausgabe (geprüft: sechs Läufe, Spanne 0 Hz). Der Fehler war das Entweder-oder: **einen Seed setzen heißt nicht, ihn festzuschreiben.** Gezogen wird pro Äußerung ein frischer Seed — die Schwankung bleibt exakt dieselbe —, und er wird protokolliert und zurückgemeldet. Damit ist eine Stimme, die einem gefallen hat, wiederholbar statt weg. Ihn wegzulassen hätte dieselbe Schwankung gegeben und nur die Möglichkeit verschenkt, jemals dorthin zurückzukehren.

Konvention wie bei Bild und Audio: `seed` mit `"random"`, `-1` oder `None` heißt ziehen. `_seeded()` sichert den globalen numpy-Zustand und stellt ihn danach wieder her, damit ein Sprech-Aufruf nicht nebenbei anderen Code im Prozess deterministisch macht. Über HTTP kommt der verwendete Seed im Kopf `X-Speech-Seed` zurück und lässt sich im Rumpf wieder mitgeben.

**Ein vom Aufrufer benannter Seed wird exakt eingelöst:** ein Versuch, keine Korrektur durch die Grundfrequenz-Wache. Wer einen Seed nennt, will *diese* Äußerung und keine bessere. Liegt sie unter dem Boden, steht das als Warnung im Protokoll, aber sie wird gesprochen.

Geprüft am 2026-08-08 über die HTTP-Schnittstelle: zwei Läufe ohne Seed → verschiedene Seeds, verschiedener Ton; derselbe Seed zweimal → byte-identisch; der gemeldete Seed reproduziert den ursprünglichen Lauf; derselbe Seed mit anderem Satz → anderer Ton (der Seed fixiert die Probe, nicht die Äußerung); `"random"`, `-1` und ein unlesbarer Wert ziehen alle.

### Zurückgenommen: zwei Paletten-Umbauten, beide auf einer Fehllesung

Am selben Abend wurde die abgenommene Palette zweimal ersetzt, einmal gegen „weniger Tonhöhenumfang", einmal gegen „weniger Vibrato". Beides beruhte auf einer Fehllesung. **Beide Umbauten sind zurückgenommen; die fünf abgenommenen Mischungen gelten.**

Die Vorgabe: Die abgenommenen Stimm-Mischungen werden verwendet und nach Passung, wo es keine Passung gibt nach Zufall, je einem Satz zugeordnet. Moduliert wird zwischen den Stimmen, mit verschiedenen Stimmen und verschiedenen Personae.

**Was „Modulation" hier heißt.** Nicht Modulation *innerhalb* einer Stimme — nicht Tonhöhenumfang, nicht Vibrato, nicht ein Zittern um eine Mischung herum. Sondern der Wechsel **zwischen** den Stimmen: mehrere Personae pro Äußerung, jeder Satz eine andere. Die Fehllesung hatte das als Eigenschaft einer einzelnen Stimme verstanden.

**Betriebsregel daraus: die abgenommene Palette wird nicht neu hergeleitet.** Eine Messung kann eine Mischung nicht besser machen, die am Ohr abgenommen wurde. Gemessen wird nur, wo eine Messung verlangt ist.

Was aus den Messungen bleibt und weiter gilt: die Grundfrequenz-Wache (`SUPERTONIC_MIN_F0_HZ`), weil sie die Bedingung gegen männliche Dominanz schützt und nichts an den Mischungen ändert; und der Seed pro Äußerung.

### Bewegte Stimme

Der Stil ist pro Aufruf fest, kann sich also zwischen Sätzen ändern. Weil die Plattform ohnehin satzweise synthetisiert (damit die ersten Wörter schnell kommen, siehe `useSpeech.ts`), kostet eine wandernde Gewichtung keine neue Struktur — nur eine Gewichtung pro Stück. Gemessen: eine weite Wanderung über drei Sätze ergab 183 → 149 → 101 Hz, eine enge 161 → 149 → 129 Hz. Für die wandernde Form gilt die 60-Prozent-Regel an **jedem** Punkt des Wegs, nicht im Mittel.

**Gebaut am 2026-08-08.** Nicht als Wanderung *einer* Gewichtung — das war der Fehlbau —, sondern als Wechsel zwischen den fünf: **mehrere Personae pro Äußerung, eine je Satz.**

Die Plattform synthetisiert ohnehin satzweise (damit die ersten Wörter schnell kommen, `useSpeech.ts`), also ist jedes Stück ein eigener Aufruf, und eine Wahl pro Aufruf **ist** eine Wahl pro Satz. Keine neue Struktur nötig. `resolve_voice()` entscheidet in dieser Reihenfolge:

1. **Nach Passung.** Wer weiß, welche Stimme zu diesem Satz gehört, nennt sie, und der Name gilt. Was passt, entscheidet der Aufrufer — der Synthesizer weiß es nicht und rät nicht.
2. **Nach Zufall, wo es keine Passung gibt.** Ohne Namen wird gezogen, und **nie die, die der Satz davor hatte**, damit aufeinanderfolgende Sätze immer verschieden klingen.

Ein genannter Seed schaltet auf eine rein aus dem Seed abgeleitete Wahl um, damit ein Seed die ganze Äußerung reproduziert — samt der Stimme, die sie gesprochen hat.

Über HTTP kommt die tatsächlich sprechende Stimme im Kopf `X-Speech-Voice` zurück. `voice` im Rumpf ist der Passungs-Weg.

Geprüft am 2026-08-08, zwölf Sätze hintereinander ohne Angabe: `mid even bright even clear mid even low mid bright clear even` — alle fünf kommen vor, keine zweimal hintereinander. Genannte Stimme wird eingelöst, Seed 777 dreimal ergibt dreimal `mid`.

### Eine Stimme für zehn Sprachen

Bei Supertonic ist der Stil von der Sprache getrennt: dieselbe Stimme spricht alle 31 Sprachen. Gemessen über neun Plattformsprachen mit echtem Text aus `src/i18n/*.ts`: Preset M1 hält 127–145 Hz, Preset F2 hält 189–236 Hz.

Das löst ein Problem, das keine Katalog-Lösung löst: **niemand hier kann Arabisch, Bulgarisch, Hebräisch, Koreanisch, Türkisch und Ukrainisch abhören.** Ein Stimmkatalog verlangt pro Sprache eine eigene Qualitätsprüfung; eine mehrsprachige Stimme verlangt sie einmal.

**Lücke:** Supertonic kann **kein Hebräisch**. Die 31 Sprachen sind en, ko, ja, ar, bg, cs, da, de, el, es, et, fi, fr, hi, hr, hu, id, it, lt, lv, nl, pl, pt, ro, ru, sk, sl, sv, tr, uk, vi. Von den offenen Modellen hat Hebräisch nur Piper (`he_IL/saspeech/medium`, mit eigenem Phonemisierer statt espeak). Ungelöst.

### Betriebseinstellungen (gemessen, nicht geschätzt)

| Einstellung | Wert | Warum |
|---|---|---|
| `intra_op_num_threads` | **4** | Voreinstellung nimmt alle 24 Kerne und ist dreimal langsamer: 1,42 s statt 0,44 s beim ersten Satz. Bei 16 Fäden 2,64 s. |
| `total_steps` | **8**, Boden 4 | 2 Schritte klingen blechern. Zeit steigt linear: 2 → 0,47 s, 4 → 0,71 s, 8 → 1,35 s. |
| Lautheit | **einmal** auf −18 LUFS (EBU R128) über die ganze Äußerung | keine satzweise Spitzennormalisierung — die lässt die Lautstärke von Satz zu Satz springen |
| Rechenwerk | CPU | GPU bleibt für Bild und Video frei |
| Seed | pro Äußerung gezogen, protokolliert, zurückgemeldet (`X-Speech-Seed`) | Schwankung ist erwünscht — und soll wiederholbar sein |
| Palette | F1, F4, F5 gegen M4 | F3 und M2 schwingen zu stark, M3/M5 rutschen zu tief, F2 schwingt im Gemisch — siehe den Nachtrag oben |
| `SUPERTONIC_MIN_F0_HZ` | 140 | die Lücke zwischen den reinen Presets (männlich 86–137, weiblich 157–197) |
| `SUPERTONIC_F0_REDRAWS` | 3 | Neuziehungen, wenn eine Äußerung darunter landet |

Latenz bis zum ersten Wort, satzweise, auf der CPU: **0,44 s** (34 Zeichen), 0,55 s (54), 0,92 s (104). Zum Vergleich Qwen3-TTS auf der freien RTX PRO 6000: 2,1 bis 11,9 s je Satz.

### Der Suchweg — was geprüft und warum verworfen wurde

Aufgesetzt hat die Suche das Kriterium aus der Notiz (unten): nicht-autoregressiv, spricht genau den übergebenen Text und redet nicht weiter.

| Geprüft | Befund | Ergebnis |
|---|---|---|
| **Qwen3-TTS** (bis 2026-08-08 in Betrieb) | autoregressiv; erfindet Fortsetzungen; 5 von 10 Sprachen; 2,1–11,9 s je Satz auf der GPU | abgelöst, **bleibt aber liegen**: genau seine Neigung, in emotionale Stimmlagen zu übersetzen, wäre das Material, falls einmal etwas zu *gefakter emotionaler Kommunikation* eingerichtet wird. `QWEN3_TTS_ENABLED` steht auf `false`, Backend, Chunk und Config bleiben stehen. Nicht entfernen. |
| **Piper** (VITS) | 10 von 10 Sprachen, schnellstes Modell im Feld (0,03–0,38 s) — aber der deutsche Katalog besteht aus LibriVox-Vorleser:innen, privaten Stimmspenden und einem 236-Sprecher-Forschungskorpus. Alles außer `thorsten` medium/high ist 16 kHz, das meiste aus einer **englischen** Grundstimme nachtrainiert. Der einzige Berufssprecher (`pavoque`, Stefan Röttig, ausgebildeter Schauspieler und Opernbariton, DFKI) existiert nur in 16 kHz und unter CC BY-NC-SA. Beim Abhören klingen die Stimmen überwiegend dilettantisch. Und: jede der zehn Sprachen müsste einzeln abgehört werden. | verworfen als Hauptweg; bleibt der einzige offene Weg für Hebräisch |
| **Kokoro 82M** (StyleTTS2) | offiziell kein Deutsch; Gemeinde-Modell „Martin" (Apache 2.0, StyleTTS2-Stufe 2 auf der Stimme von Martin Harbecke, aufgesetzt auf ein synthetisches 51-Sprecher-Grundmodell), 24 kHz, 0,3 s je Satz. Eine einzige Stimme, kein mehrsprachiger Verbund. | verworfen |
| **F5-TTS** (DiT-Flow-Matching) | nicht-autoregressiv, und als Klonmodell der einzige offene Weg, eine *bezahlte Berufsstimme* in ein offenes Modell zu bringen — man liefert die Referenzaufnahme selbst. Dagegen: pro Sprache ein eigenes nachtrainiertes Gemeinde-Modell (Deutsch und Arabisch belegt; Koreanisch, Türkisch, Ukrainisch, Bulgarisch, Hebräisch nicht gefunden), und die Gewichte sind durchgehend **CC-BY-NC-4.0**, weil das Grundmodell auf Emilia trainiert ist. | verworfen; als Weg zu einer eigenen Berufsstimme weiter offen |
| **Higgs Audio v2** | Llama-3.2-3B-Rückgrat mit DualFFN | autoregressiv |
| **Sesame CSM** | zwei autoregressive Llama-Transformer | autoregressiv |
| **dots.tts** | kontinuierlich autoregressiv mit Flow-Matching-Kopf, 2 B, Deutsch nicht genannt | autoregressiv |
| **Chatterbox, XTTS v2** | autoregressiv | verworfen |
| **Azure, ElevenLabs, Google** | die einzigen mit bezahlten Berufssprecher:innen in **allen zehn** Sprachen. Azure 16 $/Mio. Zeichen, HD 22 $ (seit März 2026, vorher 30 $), 0,5 Mio./Monat frei — rund 600 gesprochene Züge im Monat, darüber etwa 1,3 Cent je tausend Züge. Azure lässt sich als Container vor Ort betreiben; ganz ohne Netz nur mit beantragter Lizenzdatei mit Ablaufdatum. | nicht aufgerufen — das hieße, Plattformtext an Microsoft oder ElevenLabs zu schicken. Bleibt der Weg, falls die gemischte Stimme nicht mehr reicht. |
| **Supertonic 3** (Supertone, Seoul, gehört HYBE; erschienen 2026-04-29) | Flow Matching plus Sprach-Autoencoder, 99 M Parameter, ONNX, 44,1 kHz, 31 Sprachen, feste Preset-Stimmen eines Fachbetriebs statt Freiwilligenaufnahmen, OpenRAIL-M | **gewählt** |

**Was die Suche strukturell ergeben hat:** offene Sprachsynthese wird auf frei lizenzierten Aufnahmen trainiert, und die kommen fast alle aus LibriVox, Common Voice oder privaten Stimmspenden. Das ist keine Einstellungsfrage, das ist die Datenlage. Berufssprecher:innen kosten Geld — deren Aufnahmen liegen entweder bei einem Anbieter oder man lässt sie selbst herstellen. Supertonic ist der eine Fall, in dem ein Fachbetrieb seine eigenen Presets offen veröffentlicht hat.

### Offen

* Fünf Gewichtungen sind ausgeliefert (`SUPERTONIC_VOICES`), Standard ist `clear`. Der Satz „in keinem Lauf gekippt" stand hier zuerst für alle fünf und stützte sich auf sechs Läufe je Gewichtung; bei zwanzig hält er nicht — siehe den Nachtrag oben.
* Hebräisch: Supertonic hat es nicht.
* Supertonic auf der GPU (onnxruntime-gpu gegen CUDA 13) ist ungeprüft — auf der CPU aber auch nicht nötig.
* Der Einbau selbst ist nicht gemacht: Chunk, Output-Config und Anschluss an die Prüfkette stehen aus. Sprachsynthese bleibt vorerst auf die unbeschränkte Sicherheitsstufe begrenzt.

**Affected files:** `devserver/config.py` (Modell-, Stimm- und Gewichtungswahl), `devserver/my_app/services/qwen3_tts_backend.py` (wird abgelöst), `devserver/my_app/routes/speech_routes.py`, `public/ai4artsed-frontend/src/composables/useSpeech.ts` (satzweise Synthese bleibt, jetzt aus Latenzgründen statt als Kompensation), `docs/SPRACHSYNTHESE_PIPER_KONFIGURATION.md` (Messungen und Feldstand).

---

## 2026-08-08: Blackwell ab RTX 5090 ist die Hardware-Voraussetzung der Plattform

**Decision:** Die Plattformentwicklung läuft in jedem Fall auf das Vorhandensein einer **Blackwell-GPU ab RTX 5090** hinaus. Das ist keine Empfehlung und keine Optimierung, sondern die Grundlage, gegen die entwickelt wird.

**Reasoning:** Die Plattform trägt inzwischen mehrere gleichzeitig residente Modelle — SD3.5, das Latent Lab, die Prüfkette, dazu Sprachsynthese. Der VRAM-Bedarf ist nicht mehr die Summe einzelner Läufe, sondern das, was nebeneinander stehen bleiben muss. Der bestehende Latent-Lab-Resolver bildet das bereits ab: er schaltet unterhalb von 50 GB auf SD3.5-Medium herunter (`devserver/my_app/services/latent_lab_model.py`, Policy in `devserver/tests/test_latent_lab_model_policy.py`). Diese Notiz zieht daraus die allgemeine Konsequenz für alles Weitere.

**Was das kostet, gemessen am 2026-08-08:** Die neueste Hardware bedeutet den ältesten Ökosystem-Stand. Der Entwicklungsrechner läuft auf `torch 2.11.0.dev+cu130`, Python 3.13, Compute Capability 12.0 (RTX PRO 6000 Blackwell). Für diese Kombination gibt es **kein installierbares flash-attn**:

* FlashAttention-2 liefert vorgebaute Wheels für cp313 nur bis `cu12torch2.8` — gegen torch 2.11/cu13 nicht ladbar.
* Aus dem Quelltext bauen scheitert, weil kein `nvcc` installiert ist (kein CUDA-Toolkit auf dem Host).
* FlashAttention-4 gibt es nur als Beta (`fa4-v4.0.0.beta25`, reines Python-Wheel), zielt zwar auf Blackwell, zieht aber `nvidia-cutlass-dsl`, `quack-kernels`, `apache-tvm-ffi` nach — und transformers 4.57 hat für diese Modelle keinen FA4-Pfad. Testweise installiert, ohne Wirkung, wieder entfernt.

Gemessen wurde stattdessen, was da ist (Qwen3-TTS, derselbe Satz, vier Läufe je Pfad): Vorgabe und `sdpa` verhalten sich gleich und liefern byte-identische Ausgabe; `eager` ist langsamer und liefert etwas anderes. Ein Attention-Wechsel ist also **kein** verfügbarer Hebel.

**Affected files:** `devserver/my_app/services/latent_lab_model.py`, `devserver/tests/test_latent_lab_model_policy.py`, `docs/installation/INSTALLATION.md` (Hardware-Voraussetzung gehört dorthin), `devserver/config.py` (`QWEN3_TTS_ATTN_IMPLEMENTATION` bleibt als Schalter bestehen, ohne heute nutzbaren Wert).

---

## 2026-08-08: Die Stimme muss genau den übergebenen Text sprechen, nicht weiterreden

**Decision:** Ein Sprachsynthesemodell, das von selbst weiterspricht, ist das falsche Modell: Es inferiert Text, und das braucht Zeit. Gebraucht wird ein Modell, das die Übersetzung in emotionale Stimmlagen nicht übertreibt und den Text schlicht lesbar spricht.

**Die Unterscheidung, um die es geht:** Nicht Qualität gegen Geschwindigkeit, sondern zwei verschiedene Bauarten.

* **Stimmen, die weiterreden** (autoregressiv, Token für Token): Qwen3-TTS, XTTS, Chatterbox, Orpheus, Fish. Sie *inferieren* die Äußerung. Sie können fortsetzen, was nicht dasteht, sie variieren von Lauf zu Lauf, und ihre Rechenzeit hängt daran, wie viel sie erzeugen — nicht daran, wie viel Text hereinkam.
* **Stimmen, die genau den Text sprechen** (nicht-autoregressiv, Dauer-Prädiktor statt Fortsetzung): Piper (VITS), Kokoro (StyleTTS2). Sie sprechen genau die Eingabe, deterministisch, mit Echtzeitfaktoren um 0,03 auf CPU.

**Belege aus der Messung am 2026-08-08 (freie GPU, Qwen3-TTS, Preset `flat_synthetic`):**

| Beobachtung | Zahl |
|---|---|
| Fragment „Hallo. Ich bin Persona, eine Maschine, die Bilder, Klang," (57 Z.) | 16,3 s Synthese → **15,0 s Ton** |
| Ganzer Satz, 83 Zeichen | 4,7 s Synthese → 5,7 s Ton |
| Derselbe Satz ohne Seed, zwei Läufe | 96044 B / 92204 B — andere Stimme, andere Länge |
| Drei verschiedene Sätze, VoiceDesign | 108 / 186 / 226 Hz — drei verschiedene Personen |
| Dieselben drei Sätze, CustomVoice `ono_anna` | 312 / 282 / 262 Hz — eine Stimme, Satzmelodie |
| Derselbe Satz, byte-identische Ausgabe | abwechselnd 2,2 s und 6,0 s Durchgang, ohne Nachladen, auch ohne Seed |

Das Fragment mit zwei Dritteln der Länge kostet das Dreifache und liefert Text, den niemand geschrieben hat. Genau das ist das Verhalten, das die Entscheidung als „von selbst weitersprechen" benennt. Die stückweise Synthese im Frontend schneidet deshalb **nur an Satzenden** (`public/ai4artsed-frontend/src/composables/useSpeech.ts`) — das ist eine Kompensation für die Bauart, keine Lösung.

**Sprachabdeckung, der zweite Grund:** Die Plattform hat **zehn** Sprachen (`ar, bg, de, en, es, fr, he, ko, tr, uk` — siehe `src/i18n/index.ts`). Die Notiz vom 2026-08-06 spricht von neun und übersieht Bulgarisch; korrigiert.

| | eigene Stimme | ohne Stimme |
|---|---|---|
| Qwen3-TTS (heute) | de, en, ko, fr, es — **5** | ar, bg, he, tr, uk |
| Piper | alle zehn — **10** | — |

**Korrektur 2026-08-08:** Die Piper-Zeile stand hier zuerst mit sieben Sprachen und der Angabe, für Bulgarisch gebe es nichts. Falsch — der offizielle Katalog hat alle zehn, darunter Bulgarisch (dimitar), Hebräisch (saspeech) und Koreanisch (kss).

Piper deckt gerade Türkisch, Ukrainisch und Arabisch ab, die heute auf Englisch ausweichen — Workshop-relevante Sprachen. Es verliert Koreanisch. Für Koreanisch und Hebräisch existieren community-trainierte Piper-Modelle (u. a. `neurlang/piper-onnx-kss-korean`), für Bulgarisch ist nichts belegt. Piper lässt sich außerdem für beliebige Sprachen nachtrainieren; ob wir das tun wollen, ist eine eigene Frage.

**Was hier NICHT entschieden ist:** ob gewechselt wird. Der Vergleich ist Material, keine Empfehlung — insbesondere fehlt ein Hörvergleich der Stimmqualität, und „lesbar sprechen" ist ein Urteil, das am Ohr gefällt wird und nicht an einem Echtzeitfaktor. Ebenfalls offen: ob der Wechsel die Prüfkette berührt (Sprachausgabe ist heute auf `adult`/`research` gegatet).

**Nebenbefund zur Stimm-Varianz:** Dass `flat_synthetic` bei jedem Aufruf eine andere Person erfindet, ist ein mögliches Gestaltungsmittel: eine ständig andere Stimme wäre non-human und non-subjekt, Brechtsches Theater im Browser. Falls das verfolgt wird, ist es eine **Entscheidung**, kein Nebenprodukt, und gehört dann als solche notiert. Die feste Stimme steht als `QWEN3_TTS_DEFAULT_VOICE=ono_anna` bereit.

**Affected files:** `public/ai4artsed-frontend/src/composables/useSpeech.ts`, `devserver/config.py` (`QWEN3_TTS_SEED`, `QWEN3_TTS_VOICE_PRESETS`), `devserver/my_app/services/qwen3_tts_backend.py`, `devserver/my_app/routes/speech_routes.py`, Notiz 2026-08-06 (unten, in der Sprachzahl korrigiert).

---

## 2026-08-07: Flow ist eine Arbeitsfläche — Plan: eigener Arbeitsplatz mit Dauer

**Status:** Plan, kein Bauauftrag. **Priorität: MITTEL.**

**Anlass:** Der Flow ist eine Arbeitsfläche, auf der man Dinge ablegt, verschiebt und zusammenstellt, und das wird weiter ausgebaut; mit einer Benutzerverwaltung könnte er der eigene Arbeitsplatz sein, den man selbst aufräumen muss wie jeden Arbeitsplatz.

**Was das an der bisherigen Einordnung ändert:** Die Notiz vom 2026-07-09 fasst den Flow über die Medialitäts-These (das Medium ist Produkt der Verwandlung) und über „Fluss ist Oberfläche" — also über Haltung und Darstellungsform. Beides bleibt. Hinzu kommt eine dritte Bestimmung, die keine Darstellungsform ist: der Flow ist ein **Ort mit eigenem Material und Dauer**. Ablegen, Verschieben, Zusammenstellen sind dann keine Bedienschritte auf dem Weg zu einer Erzeugung, sondern das, was man auf einer Arbeitsfläche tut.

**Stand heute (die Lücke):** `x2x_flow.vue` sichert Assemblage, Perspektiven und Zone ausschließlich in `sessionStorage` (`t2i_assemblage`, `t2i_perspectives2`, `t2i_zone`, ~Z. 1100–1225); hochgeladene Bilder nur als kurze Server-URL, in-flight-Base64 bewusst nicht (Quota). Das ist die **Geste** einer Arbeitsfläche ohne **Dauer** und ohne **Person**: nichts überlebt den Tab, nichts gehört jemandem. „Selbst aufräumen müssen" kann es erst geben, wenn überhaupt etwas liegenbleibt.

**Verhältnis zur geparkten Phase P2 (Konto/Werke):** P2 wurde am 2026-07-06 geparkt, ausdrücklich mit der Bedingung, nicht ohne ein neues reales Szenario zu bauen. Der eigene Arbeitsplatz im Flow **ist** dieses Szenario. Er ist aber **nicht** der geparkte Entwurf zurück: der war ein Konto-Bereich mit einer Liste eigener Werke und Entwürfe, verworfen als alter Entwurf, der der Resona-Linie der Plattform nicht entspricht. Gemeint ist jetzt eine **Fläche, auf der die eigenen Dinge liegen**, nicht eine Liste, die sie aufzählt. Derselbe Persistenz-Bedarf in einer Gestalt, die zur Plattform passt.

**Gestalterische Leitplanke (bindend, damit sie im Bau nicht verlorengeht):** kein automatisches Aufräumen, kein Sortier-Assistent, keine „klugen" Ordnungsvorschläge. Die Unordnung gehört zum Eigenen; Aufräumen ist eine Handlung der Person, wie an jedem Arbeitsplatz.

**Ausdrücklich NICHT entschieden:** was genau liegenbleibt (nur Assemblage/Perspektiven/Zone oder auch Ergebnisse), der Geltungsbereich (pro Person, pro Course, beides), ob Flächen teilbar sind, und die Speicherschicht (Anschluss an `devserver/var/lab.db` vs. eigenes Ablageformat). Das gehört in einen Bauplan, nicht in diese Notiz.

**Nebenbefund für die Startseite:** damit ist erstmals ein Ort in Sicht, an dem echtes eigenes Material dauerhaft liegt — bisher der offene Punkt der Startseiten-Überarbeitung („was Reales zeigen, ohne es zu erfinden"). Hängt vollständig an der Dauer, die es noch nicht gibt; deshalb hier als Abhängigkeit vermerkt, nicht als Lösung.

**Offen:** Ob „Arbeitsfläche" noch mehr trägt (z. B. Nebeneinander mehrerer Flächen, oder Flächen als das, was in einem Kurs weitergereicht wird), ist zu klären, bevor ein Bauplan entsteht.

**Affected files:** noch keine — der Plan geht dem Bau voraus. Bezugspunkte: `public/ai4artsed-frontend/src/views/x2x_flow.vue` (Persistenz ~1100–1225), `docs/ARCHITECTURE PART 37 - t2x-Flow-Assemblage.md`, Notizen 2026-07-09 und 2026-07-13 (unten).

---

## 2026-08-06: Persona/Resona — TTS kehrt zurück, lokal und mit Englisch-Fallback (revidiert 2026-03-19)

**Decision:** Sprachausgabe wird wieder aufgenommen, lokal über **Qwen3-TTS** (offene Gewichte auf Hugging Face, Varianten 0.6B und 1.7B; 1.7B in bf16 gerechnet grob 3–4 GB). Nicht alle 9 Plattform-Sprachen bekommen eine eigene Stimme: DE, EN, KO, FR, ES nativ — TR, UK, HE, AR laufen auf Englisch. Russisch wird **nicht** als Ersatz für Ukrainisch angeboten, obwohl das Modell es könnte.

**Reasoning:** Die Entscheidung vom 2026-03-19 („TTS raus, weil kein offenes Modell alle 9 Sprachen abdeckt") wird ausdrücklich gedreht. Der damalige Maßstab — alle oder keine — kostet allen Sprachen die Stimme, um Ungleichheit zwischen ihnen zu vermeiden. Ein benannter Fallback auf Englisch ist die ehrlichere Form: er macht die Lücke sichtbar, statt das Feature ganz zu streichen. Ukrainisch ist in keinem verfügbaren TTS-Modell enthalten; Russisch als Näherung anzubieten verbietet sich politisch und wäre gegenüber ukrainischsprachigen Teilnehmenden übergriffig. Wer Arabisch spricht, kann Arabisch statt Türkisch wählen — als Angebot, nicht als Ersatz.

**Warum lokal und nicht die API-Variante:** Qwen-Audio-3.0-TTS (gehostet, Flash/Plus, seit 2026-07-20) deckt 16 Sprachen ab und hätte als einzige zusätzlich Arabisch nativ. Sie läuft aber ausschließlich über Alibaba Cloud Model Studio (Endpunkte Singapur/Peking), ohne herunterladbare Gewichte. Texte von Schüler:innen dorthin zu schicken kollidiert mit der DSGVO-Position der Plattform, die Provider explizit als konform oder nicht führt (`devserver/hardware_matrix.json`, Schlüssel `DSGVO_CONFORMITY`). Arabisch nativ ist der bewusst gezahlte Preis. Qwen-Image-3 fällt aus demselben Grund als lokale Option aus — auch dort gibt es seit 2026-07 keine offenen Gewichte mehr; die letzte offene Qwen-Bildgeneration bleibt Qwen-Image-Edit-2511, die bereits über `download_qwen.sh` installiert wird.

**Abgrenzung — Cloning, nicht Training:** Qwen3-TTS ist auf Voice Cloning (`Base`, aus einer Referenzaufnahme) und Voice Design (`VoiceDesign`, Stimmbeschreibung in natürlicher Sprache) ausgelegt, dazu `CustomVoice` für eine fixierte Stimme. Fine-Tuning wäre möglich, ist aber nicht der vorgesehene Weg. Welche Referenz bzw. welche Beschreibung Resonas und Personas Stimme setzt, ist eine gestalterische Frage und hier NICHT entschieden.

**Affected files:** noch keine — die Entscheidung geht dem Bau voraus. Rückbau-Referenz von 2026-03-19: `src/views/ai_persona.vue` (TTS-Button, `speak()`, `ttsEnabled`, `stripMarkers()`), `src/i18n/en.ts` (Schlüssel `persona.toggleTTS`).

---

## 2026-08-05: HeartMuLa — Prompt-zu-Song wird ERSETZT (Re-Enactment); zwei Analyse-Routen gebaut

**Entschieden:** Die prompt-getriebene Musikerzeugung wird **ersetzt, nicht ergänzt**. An ihre Stelle tritt ein Re-Enactment: Mikrofonaufnahme (max. 60 s) → Auswertung → Transkription → LLM → HeartMuLa-Nachstellung. Leitmetapher „silly parrot" (im Anschluss an „stochastic parrot", Bender/Gebru/McMillan-Major/Shmitchell 2021), die kritische Rahmung ist Teil des UI. **Kein Download des Audios**, kein Favorisieren, kein Bestand als Werk.

**Begründung:** HeartMuLa war auf dieser Plattform immer ein Fremdkörper — keine Prompt Interception, keine Dekonstruktion, nur eine schwache Kulturalisierung in den Stilpresets; das ist inkonsistent zum Rest. Songwriterinnen mit einem Prompt zu ersetzen ist nicht Ziel der Plattform. Die 4-Minuten-Länge aus `94b93a85` war nicht vorgesehen und für Workshops unbrauchbar; neue Obergrenze 60 s, 30 s zu kurz.

**Zwei Register der Transparenz:** die Auswertungs-Begrenztheit **lesbar**, die Begrenztheit von HeartMuLa **hörbar** — gegen den LLM-Prompttext gelesen, der geschrieben danebensteht.

**Kein Stage 2 auf diesem Weg.** Unter dem Papageien-Bild ist die LLM-Station, die aus einer verstümmelten Transkription selbstbewusst zusammenhängende Lyrics macht, der *Musterfall* des Konfabulierens, nicht die Ausnahme. Eine pädagogische Interception daneben würde die Pointe verschieben. Das Stück steht damit neben dem Latent Lab (Dekonstruktion), nicht neben den Erzeugungsseiten — ist aber **nicht** Teil des Latent Lab, das `adult`/`research` verlangt, während dies für Kinder gedacht ist.

**Was jetzt gebaut ist:** die beiden Analyse-Stationen als Routen unter der bestehenden `/api/analysis`-Blueprint — `POST /api/analysis/lyrics` (HeartTranscriptor-oss) und `POST /api/analysis/music-tags` (MuQ-MuLan large). Gleiche Lazy-Load-/VRAM-Koordinator-Mechanik wie `analyze_audio`, keine Parallelstruktur. Die Nachbau-Station `POST /api/analysis/audio` (MiDashengLM 7B) existierte bereits und wurde von nichts aufgerufen.

**Warum MuQ-MuLan als sichtbare Station und nicht MiDashengLM** (gemessen am selben Material):
1. Die Rangliste mit Zahlen *zeigt* den Trichter; die Prosa liest sich wie Verstehen und verdeckt ihn. `arabic maqam on oud` landet in jeder Musik-Bedingung auf dem letzten Platz — die kulturelle Grenze als Messung statt als Behauptung in der Provenienzkarte.
2. Whisper erfindet Sätze aus Rauschen, transkribiert echte Sprache aber gut; MiDashengLM ist bei Stille ehrlich. **Korrektur vom selben Tag:** die zunächst MiDashengLM zugeschriebene Instrumenten-Erfindung war größtenteils Produkt seines eigenen Prompts (*„write a rich, flowing description"*). Unter einem zurückhaltenden Prompt nennt es das Klavier und antwortet auf Raumgeräusch „There is nothing." Beide Default-Prompts sind daraufhin ersetzt; sie sprachen das Modell zudem als Hörendes bzw. Sehendes an, auf genau der Fläche, deren Gegenstand ist, dass es beides nicht tut. Dieser Punkt trägt die Entscheidung also NICHT mehr.
   Gegen die Erwartung war die Personifizierung dabei nicht der wirksame Teil: die Genauigkeitsforderung war es. „listener" zu streichen kostet nichts, „precisely" zu streichen kostet das Klavier, und die Zurückhaltung in beiden Prompts zugleich lässt die Antwort auf ein Wort zusammenfallen. Die Vier-Varianten-Messung steht als Tabelle im Quelltext über `DEFAULT_AUDIO_PROMPT`, damit niemand den Systemprompt später „vereinfacht". Merke fürs Weitere: solche Prompts sind gemeinsam zu messen, nicht einzeln.
3. MiDashengLM schreibt Stimmen Geschlecht, Alter und Gefühlslage zu — und das **überlebt die ausdrückliche Anweisung**, die Person nicht zu beschreiben. Kein Prompt-Artefakt. Über Aufnahmen von Kindern, in der Schule, projiziert: gehört nicht auf den Schirm. Das ist der belastbare Grund.

**Was MiDashengLM damit doch kann:** auf Raumgeräusch „There is nothing." — etwas, das weder Whisper noch MuQ-MuLan zustande bringen, beide antworten auf Nichts zuversichtlich. Als unsichtbarer Vorschalter („ist hier überhaupt etwas?") ist es damit brauchbar; verworfen ist nur die sichtbare Fläche.

**Das Label-Vokabular ist UNSERES, nicht das des Modells.** HeartMuLa-Tags sind freier Text ohne geschlossenes Vokabular, und MuQ-MuLan bettet beliebige englische Strings ein. `MUSIC_TAG_VOCABULARY` (46 Labels) muss im UI als unsere Liste benannt werden. Die Strings sind Modell-Eingaben und bleiben Englisch; eine Anzeige braucht eigene i18n-Labels, niemals übersetzte Modell-Eingaben.

**Rückbau — AUSGEFÜHRT am selben Tag, zusammen mit der Ersatzseite** (Commit `faa8df82`, klar bezeichnet, damit die Seiten bei Bedarf aus der Historie zurückgeholt und nicht neu geschrieben werden müssen). Entfallen sind: die Routen `/music-generation`, `/music-generation-simple`, `/music-generation-advanced`, die drei Views (`music_generation_unified.vue`, `music_generation.vue`, `music_generation_v2.vue`), die verwaiste `components/MusicTagSelector.vue`, der `heartmula`-Tab in `views/x2x_legacy.vue` (Bündelung vom 2026-07-13) und die i18n-Blöcke `musicGeneration`, `musicGen`, `musicGenV2`, `landing.features.music`. An ihre Stelle tritt `/cover-band` (`views/cover_band.vue`), im Kopf-Menü neben dem Latent Lab statt im x2x-Hub — es ist ein Dekonstruktions-Stück, keine x2x-Verwandlung. Aufbau: `docs/ARCHITECTURE PART 38 - Cover-Band.md`.

**Mit dem Rückbau erledigen sich zwei offene Defekte:** der 30–240-s-Regler (`music_generation_v2.vue:119`, `music_generation.vue:306`) und die `topk: 65` / `cfg_scale: 2.75`-Überschreibungen in `music_generation_v2.vue:332-333`, die den im Juni auf die offiziellen 50 / 1.5 abgeglichenen Backend-Default aushebeln. Bleiben die Seiten wider Erwarten stehen, müssen beide unabhängig repariert werden.

**Betroffene Dateien:** `gpu_service/services/media_analysis_backend.py`, `gpu_service/routes/media_analysis_routes.py`, `docs/ARCHITECTURE PART 31 - GPU-Service.md`. Neu im GPU-venv: `muq`, `x_clip`, `nnAudio`, `easydict`, `beartype` (alle `--no-deps`, damit der torch-Nightly unangetastet bleibt). develop, ungepusht.

**Offen:** die harten `max_tokens`-Deckel auf der Interception (400/600/800) und `"max_tokens": 1` in `devserver/schemas/configs/interception/heartmula.json` — mehrfach angezeigt, noch nicht entschieden.

---

## 2026-07-13: Resona — echter Surrealizer-Zugang + generate_media/Instrument-Grenze (Provenienz)

**Befund:** Auf die Bitte, den Surrealizer anzubieten, rief Resona `generate_media` mit einem generischen Modell (`flux2`) auf und schrieb den Instrumentnamen ins freie `prompt`-Feld. Die Provenienz-Karte zeigte die flux2-Karte (Black Forest Labs) unter einem „Surrealizer"-Banner — eine Provenienz-Lüge auf genau der Fläche (`ModelProvenanceCard`), die Provenienz-Ehrlichkeit lehren soll. Die Karte war korrekt; falsch war, WAS lief.

**Wurzel:** Die hartkodierte Allowlist `resona_media_configs` (`tool_registry.py`) enthält nur generische t2x-Configs und OMITS alle Latent-Lab-Instrumente → der Surrealizer ist über `generate_media` unerreichbar; Resonas mentales Modell wurde „Technik = Prompt, Bild = generisches Modell".

**Zwei Maßnahmen:**
1. **Echter Zugang statt Maskerade** (`ab935fb4`): `surrealization_diffusers` fährt jetzt über `run_canvas_graph` mit echten Reglern — `alpha_factor` (-75..+75) + `fusion_strategy` (`legacy` | `dual_alpha`; `normalized` bewusst NICHT exponiert, wird entfernt), inline am generation-Knoten, surrealizer-only validiert (`canvas_graph_authoring.py`), durchgereicht `canvas_executor → execute_stage4_generation_only → Chunk`. KEIN Config-Preset mit Fix-Parametern (das hätte die Selbst-Illusion nur zementiert).
2. **Grenze im Prompt statt harte Sperre** (`ab14bd54`): `RESONA_CORE_PROMPT` rahmt `generate_media` als generische Modelle und verweist benannte Instrumente an `run_canvas_graph` unter ihrer `configId` — nie ein generisches Modell für ein benanntes Instrument. Bewusst der Prompt-Weg (Ehrlichkeit/Transparenz) statt brüchiger Enforcement; die Provenienz-Karte korrigiert ohnehin jedes Fehl-Label, weil sie immer das Modell nennt, das lief.

**Warum kein harter Riegel:** Ehrlichkeit/Transparenz sollen generell befördert werden; ein technischer Fake-Blocker verlagert die Lüge nur, statt die Grammatik zu lehren.

**Persona (Abgrenzung):** trägt dieses Risiko strukturell NICHT — `_should_use_tools()` = `False` für `persona_mode` → `tools = None`, kein Zugriff auf instrument-erreichende Tools (`scopes=["resona"]`). Persona erzeugt nur über `[GENERATE:]`-Marker aus einer generischen Config-Liste, kennt die benannten Instrumente nicht. Generisch-per-Design ist korrekt; kein Fix.

**Verifiziert (API-Gegentest):** Graph input→generation{`surrealization_diffusers`, `alpha_factor=40`, `fusion_strategy=legacy`} über `/api/canvas/execute-stream`. Backend-Log: `[SURREALIZER] Generating: alpha=40.0, strategy=legacy, steps=25, size=1024x1024, model=stabilityai/stable-diffusion-3.5-large`. Echtes SD3.5-Large statt flux2, beide Regler am Chunk, ~7 s, kein Error. Provenienz-Karte zeigt jetzt SD3.5/AI4ArtsEd.

**Betroffene Dateien:** `devserver/my_app/services/canvas_executor.py`, `.../services/canvas_graph_authoring.py`, `.../services/tool_registry.py`, `.../routes/schema_pipeline_routes.py`, `.../routes/chat_routes.py`, `docs/ARCHITECTURE PART 32 - Dialogic-AI-Persona.md`. Commits `ab935fb4`, `ab14bd54`, `7b3dce9a` (develop, NICHT gepusht, NICHT auf main/prod).

---

## 2026-07-13: Legacy-Transformationsmodi unter „x2x (legacy)" gebündelt — Navigations-Konsolidierung

**Entscheidung:** Die vier bislang gleichrangigen Top-Level-Modi t2x/i2i/mi2i/heartmula werden zu EINER Gruppe „x2x (legacy)" zusammengefasst — ein Nav-Button („A-mit-Pfeil") öffnet einen Hub mit vier Tabs (Text · Image · Multi-Image · Music) auf dem kanonischen Hub-Tab-Muster von Compare/Latent Lab (`views/x2x_legacy.vue`, Route `/x2x-legacy`). Kopf-Leiste 12 → 9 Buttons. heartmula öffnet nur noch „erweitert" (`music_generation_v2.vue`), der simple/advanced-Umschalter entfällt im Menü. Alte Routen bleiben (deep-linkbar); nur ihre Einzel-Buttons verschwinden.

**Welche Inkonsistenz das (teilweise) heilt:** Die „x2x flow"-Assemblage (PART 37) generalisiert per Material-Routing genau das, was t2x/i2i/mi2i als Einzelmodi tun (0 Bilder → t2x, 1 → i2i, 2–3 → mi2i). Trotzdem standen der allgemeine Fall (Flow) UND seine vier Spezialfälle flach als gleichrangige Top-Level-Modi nebeneinander — vier Eingabe-Modalitäts-Varianten EINER „x→x"-Verwandlung, präsentiert als vier eigenständige Paradigmen. Das widerspricht (a) der tragenden These „Medialität ist Produkt der Verwandlung, nicht Input-Wahl" (Notiz 2026-07-09 oben); (b) PART-15-Entscheidung #1 „Input-Type-Based Pipelines" (die Input-Struktur-Familie ist EINE Sache, das Ausgabemedium bestimmt die Config); (c) der bereits gelebten Gruppierungs-Politik (Compare, Latent Lab bündeln verwandte Sub-Modi längst unter einem Hub) — die Transformationsmodi NICHT zu bündeln war intern inkonsistent.

**Warum nur „teilweise":** Dies konsolidiert die Navigations-Oberfläche und benennt das Verhältnis explizit (Flow = allgemein, gebündelte Vier = „legacy"), zieht die Legacy-Modi aber noch NICHT zugunsten des Flow zurück. Die vollständige Heilung ist der Klassik-Rückbau (der Flow subsumiert die Einzelmodi); dieser Schritt ist die Nav-seitige Vorstufe, nicht der Rückbau selbst.

**Element-Struktur (`docs/ELEMENT_STRUCTURE_REGISTRY.md`):** Der Hub erfindet keine neue Element-Struktur, sondern nutzt das vorhandene Hub-Tab-Muster (Compare/Latent Lab). Ehrlicher Befund: dieses Muster ist selbst über vier Vues hand-kopiert (compare_hub, latent_lab, music_generation_unified, jetzt x2x_legacy) → als `to-consolidate` in `docs/ELEMENT_STRUCTURE_REGISTRY.md` eingetragen (Extraktion einer geteilten `<TabHub>`-Komponente = Folge-Task, `docs/devserver_todos.md`).

**Betroffene Dateien:** `public/ai4artsed-frontend/src/views/x2x_legacy.vue` (neu), `.../App.vue` (Nav 12→9), `.../router/index.ts`, `.../i18n/en.ts` (+`x2xLegacy`), `.../i18n/WORK_ORDERS.md`. Commit `c84d25ee` (develop, ungepusht). t2x-Tab-Icon = `text_format`.

**Offen:** Die „Inkonsistenz"-Fassung oben ist aus den vorhandenen Docs abgeleitet und noch nicht bestätigt.

---

## 2026-07-09: Resona & t2x-Flow — Motivation und Gebrauchsmuster

**Zweck dieser Notiz:** Nicht die Technik (die liegt in den jeweiligen Architecture-Parts), sondern die *Motivation* und die daraus folgenden *Gebrauchsmuster* zweier tragender Ideen der Plattform. Bildungstheoretischer Rahmen: Der Beitrag der Plattform ist die pädagogisch-ästhetische Umsetzbarkeit — Technik ist zitiertes Material, nicht Selbstzweck.

### Resona — Begleiter statt Werkzeug

**Haltung/Entscheidung:** Resona ist ein pädagogischer *Begleiter* für Werkstätten — keine Interception-Persona (die den Prompt transformiert), kein Prompt-Optimierer, kein Assistenz-Chatbot. Eine dritte Persona-Rolle (`resona_mode`) neben den bestehenden dialogischen Personae.

**Warum ein Begleiter (Motivation):** Eine Werkstatt braucht keine weitere optimierende Funktion, sondern eine *Präsenz*, die den Prozess begleitet — mitdenkt, spiegelt, orientiert — ohne die Arbeit abzunehmen oder "besser" zu machen. Zugleich Antwort auf die schwache Fähigkeits-Kommunikation der ~30 gewachsenen Feature-Vues: ein Gegenüber, das die Möglichkeiten kennt und im richtigen Moment einbringt, statt eines Menüs.

**Kern — der Dreiklang:** Verhältnis zu sich selbst, zu Anderen, zur Sache. Alle drei sind konstitutiv; das Verhältnis-zu-Anderen ist nicht verhandelbar (es war einmal beinahe zugunsten reiner Governance weggeworfen worden — das ist der Fehler, den diese Notiz festhält). Haltung: *Präsenz zur Sache*. Die beiden verbotenen Pole sind **Rigorismus** (Schweigen aus Risikoscheu — Fehler sind Material, nicht Gefahr) und **Anbiederung** (Beziehungspflege, erfundene Grüße). Keine Frage-Pflicht; Resona liefert Text zum Redigieren, kein Urteil.

**Gebrauchsmuster:**
- *Situiert:* Resona weiß über Situationsblöcke (`context.resona_situation`, z.B. `nachklapp`), in welcher Lage es spricht, und passt Register und Beitrag an — situierter Begleiter, kein generischer Assistent.
- *Nachbereitung:* In der Nachklapp-Situation sieht Resona, was entstanden ist (geteilte Favoriten, `view_favorite`), und hilft, das Erlebte zu ordnen — ohne zu bewerten.
- *Graphen sprechen:* Statt nur Text kann Resona einen Canvas-Workflow vorschlagen und komponieren (`run_canvas_graph`, `canvas_graph_library`, Strategie-Repertoire) — ein Vorschlag als ausführbarer Prozess, nicht als Anleitung.
- *Mit den Mitteln:* im Rahmen explizit gewährter Capabilities erzeugt Resona selbst Medien, schlägt Referenzen/Interception-Modi nach und erklärt sie, sieht geteilte Favoriten — als Mit-Beteiligter am Geschehen, nicht als externer Ratgeber.

### t2x-Flow / Assemblage — Medialität als Produkt der Verwandlung

**These/Entscheidung (2026-07-06):** Medialität ist *Produkt der Transformation* (Stage 2), nicht Input-Wahl. Man wählt nicht "mach ein Bild"; das Medium entsteht aus der pädagogischen Verwandlung des Prompts. Das löst den rund halbjährigen t2x-vs-Medialität-Konflikt auf.

**Warum (Motivation):** Es geht um eine *Haltung zur Medialität*, nicht um UX-Bequemlichkeit. Indem das Medium NICHT vorgewählt wird, wird der okulare Default (Bild als unmarkierte Norm) im Funktionieren sichtbar und befragbar — dieselbe Bewegung wie bei den Latent-Lab-Eingriffen: die Norm wird im Funktionieren sichtbar gemacht, nicht behauptet. Medialität ist relational gedacht (N/Ä/M als Differenzrelationen, borromäisch verknüpft) — die Plattform soll das nicht in eine sequentielle text→bild-Pipeline kollabieren. Wichtig: Die 4-Stage-Architektur bleibt UNVERÄNDERT — es ist eine Umverteilung, kein Umbau.

**Gebrauchsmuster:**
- *Ambiente Medien-Inferenz:* Man schreibt und denkt im Prompt; das Medium wird inferiert und ambient angezeigt (Mediensymbole leuchten, mehrere zugleich möglich) — nach demselben Muster wie Safety: Catchword + kleines lokales LLM, ständig an der Inputbox. Steuerung über den Prompt; versteckte Overrides (Klick = exklusiv, Langklick = Modell-Bubbles). Modellwahl automatisiert und kuratiert.
- *Fluss ist Oberfläche:* Feature-Vues als Fluss-Karte auf einem Screen (Überblick + Zoom in einen Knoten mit großer Detailfläche), statt Scroll-Flow. Container-Geste = feste Panel-Bühne (berechenbare Modul-Fläche).
- *Assemblage:* mehrere Texte kombinierbar in den Rollen *Material* vs. *Perspektive* — die Komposition ist das Werk; bei ≥2 Texten entscheidet ein Agent die Rolle (Phase 2).
- *Phase 1 (gebaut, deterministisch):* Bild-Anzahl → Config (t2x/i2i/i2v/mi2x, `qwen_2511_multi` max 3), Medium post-Interception und geklemmt, "?"-Marker bei Unklarheit, freier I-Prompt (`user_defined`).

**Affected files (Doku):** `docs/ARCHITECTURE PART 32 - Dialogic-AI-Persona.md` (Resona-Abschnitt angefügt), `docs/ARCHITECTURE PART 37 - t2x-Flow-Assemblage.md` (neu).

---

## 2026-03-26: Arcimboldo Mosaic + Composable Diffusion → Latent Lab (nicht t2X)

**Decision:** Drei Konzepte zu Assemblage, Mosaik und Collage werden dem **Latent Lab** zugeordnet, NICHT dem t2X-Flow:

1. **A — Arcimboldo Mosaic** (Image Lab Tab): Semantische Heatmap (Cross-Attention/DAAM) segmentiert ein Hauptbild → jede Region wird durch viele kleine Tile-Bilder des jeweiligen Konzepts ersetzt (Photo-Mosaik-Prinzip). Hauptbild via SD3.5/FLUX, Tiles via SD1.5 (weil Cross-Attention dort sauber separiert ist). Attention Cartography liefert bereits die Heatmaps.

2. **B — Composable Diffusion** (Erweiterung Surrealizer oder eigener Tab): Prompt in semantische Teile zerlegen, jeweils eigene Energy-Funktion, im Denoising-Loop konjugieren. Der Surrealizer macht bereits nicht-semantische Composable Diffusion (CLIP-L/T5-Interpolation). Scene Graph als Input-Format (nicht als Interception-Config).

3. **Scene Graph Config** (`scene_graph.json`): Bleibt vorlaeufig als Interception-Config (produziert ordentliche Bilder), ist aber eigentlich das Input-Format fuer B. Mittelfristig in den Latent Lab Graph-Editor ueberfuehren.

**Kerngedanke:** Aufbrechen der Prompt/CLIP-Machtposition durch Atomisierung. CLIP komprimiert einen Prompt in eine monolithische Repraesentation. Composable Diffusion und Arcimboldo brechen das auf.

**Warum Latent Lab, nicht t2X:** t2X ist medienagnostisch (text→image/video/audio/code). Arcimboldo und Composable Diffusion sind rein visuell und manipulieren Diffusion-Interna — das ist exakt der Scope des Latent Lab (Passthrough-Pipeline, skip_stage2, Diffusers direkt).

**Status:** Konzept dokumentiert. Keine Implementierung begonnen. Scene Graph Config mit formaler Graph-Notation aktualisiert (Step-Ueberschriften + Netzwerkgraph-Notation mit NODES/EDGES).

**Affected files:**
- `devserver/schemas/configs/interception/scene_graph.json` (Notation aktualisiert)
- Zukuenftig: neuer Image Lab Tab, Surrealizer-Erweiterung oder eigener Tab

---

## 2026-03-25: Anti-AI-Slop Guard + Trashy kennt Interception-Prompts

**Decision:** Zwei zusammenhaengende Aenderungen:
1. **VISUAL SPECIFICITY Klausel** in der `transformation`-Instruction (instruction_selector.py): Leichtgewichtiger, positiv formulierter Anti-Slop-Guard. Steuert Richtung Konkretheit und Spezifik statt Klischees aufzulisten — negative Instruktionen ("vermeide X") koennen beim LLM genau das ausloesen, was man vermeiden will.
2. **lookup_interception Tool** fuer Trashy: Neues Tool im ToolRegistry, das Interception-Configs und Instruction-Templates dynamisch laedt. Trashy kann jetzt erklaeren, was ein bestimmter Modus tut ("Was macht der Bauhaus-Modus?"). Safety-Prefixes sind explizit ausgeschlossen.

**Warum positiv statt negativ:** Der Clichéfilter (clichéfilter_v2.json) sagt selbst "NEVER use negative descriptions... describe POSITIVELY." Dieselbe Logik gilt fuer die Meta-Instruktion. "Bevorzuge Konkretheit" statt "Vermeide AI-Slop" — das zweite listet implizit auf, was man nicht will, und riskiert Fixierung.

**Warum dynamisches Tool statt statische Knowledge Base:** Interception-Configs aendern sich haeufig (aktuell ~45). Ein Tool das die JSONs on-demand liest, ist immer aktuell. Kein manuelles Nachpflegen noetig.

**Affected files:**
- `devserver/schemas/engine/instruction_selector.py` (VISUAL SPECIFICITY Klausel)
- `devserver/my_app/services/tool_registry.py` (lookup_interception Tool + 3 Helper-Funktionen)
- `devserver/my_app/routes/chat_routes.py` (INTERCEPTION KNOWLEDGE Absatz in General + Session Prompt)

---

## 2026-03-25: Bildanalyse zentralisiert in MediaOutputBox + ChatOverlay (Trashy)

**Decision:** Die Bildanalyse ist KEIN per-View Feature. Sie gehoert zentral in MediaOutputBox (Button) und ChatOverlay (Ausfuehrung + Anzeige). Kein Inline-Kasten unter dem Bild, kein per-View `analyzeImage()`, kein separater VLM-Endpoint.

**Architektur:**
1. MediaOutputBox: Analyze-Button dispatcht `runId` an `analysisEventStore` (Pinia)
2. ChatOverlay: faengt Event → expandiert Trashy → `/api/chat` mit `image_path` → Sonnet sieht Bild direkt → zeigt prozessorientierte Reflexion
3. Prompt ist safety-level-adaptiert (kids/youth/expert via `uiModeStore`)

**Warum nicht per-View:** Die Analyse haengt nicht von der View ab, sondern vom generierten Bild und dem User-Input. Beides ist zentral verfuegbar (run_id aus MediaOutputBox, User-Input aus pageContextStore).

**Warum kein Inline-Kasten:** Das Compare-Pattern (Trashy kommentiert am Rand) ist besser. Die Analyse ist ein Gespraech, kein statischer Text. User kann direkt in Trashy weiter fragen.

**Affected files:**
- `public/ai4artsed-frontend/src/components/MediaOutputBox.vue` (triggerAnalysis, kein Emit)
- `public/ai4artsed-frontend/src/components/ChatOverlay.vue` (analysisEvent Watcher, /api/chat Call, buildImageAnalysisPrompt)
- `public/ai4artsed-frontend/src/stores/analysisEvent.ts` (Pinia Event Store)

---

## 2026-03-25: Vision in /api/chat — Nur generierte Bilder, keine Uploads

**Decision:** Der /api/chat Endpoint akzeptiert optional `image_path` und sendet Bilder an vision-faehige Chat-Modelle. Es werden ausschliesslich **plattform-generierte Bilder** (aus LivePipelineRecorder runs) an externe Provider gesendet — **niemals vom User hochgeladene Bilder**.

**Hintergrund — Zwei Kategorien von Bildern:**
1. **Hochgeladene Bilder** (img2img Upload, Sketch): Werden lokal verarbeitet und lokal safety-gecheckt (VLM). Verlassen den Server NICHT. Dies bleibt so.
2. **Generierte Bilder** (Stage 4 Output): Von der Plattform selbst erzeugt. Diese duerfen an den Chat-Provider gesendet werden, weil (a) sie keine personenbezogenen Daten enthalten die nicht bereits durch die Pipeline gelaufen sind, und (b) der Provider (Mammouth/Anthropic) DSGVO-konform ist.

**Fallback-Architektur:** Falls das Chat-Modell NICHT vision-faehig ist, wird das Bild lokal durch IMAGE_ANALYSIS_MODEL (qwen3-vl, lokal) beschrieben und nur die Textbeschreibung gesendet. In diesem Fall verlassen auch generierte Bilder den Server nicht.

**Vision-Erkennung:** `is_vision_capable()` in `vision_support.py`. Cloud-Provider (mammouth/, anthropic/, openai/, openrouter/, mistral/, bedrock/) = True. IONOS = False. Local = Namens-Heuristik.

**Affected files:**
- `devserver/my_app/utils/vision_support.py` (NEU)
- `devserver/my_app/routes/chat_routes.py` (image_path Handling, provider-spezifische Formate)
- `public/ai4artsed-frontend/src/stores/analysisEvent.ts` (runId Feld)
- `public/ai4artsed-frontend/src/components/ChatOverlay.vue` (image_path an /api/chat)

---

## 2026-03-24: UI_MODE Length Limits Moved from Engine to BackendRouter

**Decision:** `UI_MODE_WORD_LIMITS` and `UI_MODE_MAX_TOKENS_SAFETY` enforcement moved from `PromptInterceptionEngine.process_request()` to `BackendRouter._process_prompt_interception_request()`.

**Problem:** The engine unconditionally applied word-count injection ("Keep your response under 150 words") and max_tokens safety caps (youth=600, expert=800) to ALL requests — including prompt optimization. p5.js code generation requires ~4096 tokens but was capped to 600 in youth mode, breaking code output.

**Root cause:** The limits are a policy of the interception workflow (student-facing output), not a feature of the LLM routing engine. Optimization output goes to Stage 4 (machine-consumed), never directly to students.

**Solution:** Separation of concerns — limits belong in the interception call path (BackendRouter), not the engine. `execute_optimization()` calls the engine directly, bypassing BackendRouter, so it naturally has no limits. No flags, no opt-out logic needed.

**Affected files:**
- `devserver/schemas/engine/prompt_interception_engine.py` (removed lines 213-225)
- `devserver/schemas/engine/backend_router.py` (added limits before PromptInterceptionRequest creation)

---

## 2026-03-22: media_type Detection Must Use Config Metadata, Not Name Substrings

**Decision:** Added `'heartmula'` to all 5 media_type substring-detection sites in `schema_pipeline_routes.py` to fix HeartMuLa being misclassified as `image`. Removed `p5js_code` and `tonejs_code` from Persona's available config list.

**Root cause:** media_type detection relies on substring matching against `output_config` names (e.g. `'music' in name`). The config `heartmula_standard` contains neither `music` nor `audio` → fell through to `image` fallback. This caused MediaOutputBox to render a `<img>` tag for an audio URL.

**Why not fix the detection properly?** The substring approach is fragile (any new config name that doesn't contain the expected keyword will break), but a proper fix (reading `media_type` from the config JSON's `media_preferences.default_output`) would touch the orchestration pipeline across 5 code paths. Documented as tech debt.

**P5.js/Tone.js in Persona:** Removed because MediaOutputBox has no `code` rendering (needs editor + sandboxed iframe). The `text_transformation` page is the proper venue for code generation — it has the full editor + live preview setup. Adding code rendering to MediaOutputBox would be over-engineering for a chat interface with small draggable boxes.

**Affected files:**
- `devserver/my_app/routes/schema_pipeline_routes.py` (5 media_type detection sites)
- `public/.../views/ai_persona.vue` (removed p5js_code, tonejs_code from config list)

---

## 2026-03-21: Stage 2 Interception Mandatory for i2x/multi-i2x (Jugendschutz)

**Decision:** i2x and multi-i2x views now run Stage 2 interception (with Safety Prefix) before any generation at kids/youth safety levels. Config selection triggers streaming interception into the context box; Generate without prior config triggers `user_defined` interception (safety-only).

**Reasoning:** The three-concern safety architecture (§86a, DSGVO, Jugendschutz) had a gap: Jugendschutz was enforced only in Stage 2, but i2x/multi-i2x skipped Stage 2 entirely. The `context_prompt` went directly to Stage 3+4. Live testing confirmed that prompts like "Ziehe allen Figuren die Kleidung aus" passed both `/safety/quick` (only §86a + DSGVO) and Stage 3 Llama Guard (S11 insufficient for instructions vs. descriptions) at kids safety level.

**Design choice — frontend-only, no backend change:** The existing `/api/schema/pipeline/interception` endpoint and `user_defined.json` config already supported the required flow. The streaming MediaInputBox component already had all necessary props. Only the Vue views needed the interception flow logic.

**Design choice — destructive in-box replacement:** The interception result streams into the same context prompt box (destructive replacement), not a separate output box. This matches the user's mental model: "my instruction gets refined" rather than "two separate texts".

**Design choice — Safety Prefix Context-rules clause:** Added "nudity, sexual, or pornographic content" to the Context-rules clause. Previously only violence/weapons were guarded against malicious context_prompt injection via the "even if the Context rules would produce it" sentence.

**Affected files:**
- `devserver/schemas/engine/instruction_selector.py` (Safety Prefix)
- `public/.../views/image_transformation.vue` (Stage 2 flow)
- `public/.../views/multi_image_transformation.vue` (Stage 2 flow)

---

## 2026-03-20: Workshop Model Preloading — Three Key Design Decisions

### 1. ComfyUI Fake-Run Preloading (No Native Preload API)

**Decision:** ComfyUI models are preloaded by submitting minimal "fake workflow" (128×128px, 1 step, dummy LoadImage) instead of implementing a custom preload endpoint.

**Reasoning:** ComfyUI has no `/preload` or `/load-model` REST API. The only reliable way to force a model into GPU memory is to submit a complete workflow and let the execution engine load all dependencies. Using a minimal workflow (not a full 2048×2048 generation):
- Forces the model to load (satisfies the goal)
- Completes in 1–2 minutes per model (acceptable in workshop setup)
- Avoids implementing custom ComfyUI node plugins (maintenance burden)
- Respects ComfyUI's design constraint that all workflows need output nodes

**Tradeoff:** Generates a tiny 128×128 output image that is immediately discarded. This is acceptable because preloading only happens during workshop setup (explicit user action), not during normal operation.

**Alternative rejected:** Custom ComfyUI node to bind models without execution. Would require:
- Compiling Python extensions in ComfyUI environment (dependency mess)
- Separate node distribution and versioning
- Support burden across multiple ComfyUI versions

---

### 2. Sequential (Not Parallel) Model Loading

**Decision:** Models load one at a time, not in parallel. Each model waits for the previous one to complete before starting.

**Reasoning:** RTX 6000 Blackwell has 96 GB VRAM. Loading multiple huge models simultaneously (Flux 2: 18GB, Wan 2.2: 16GB, SD 3.5: 9GB) would exceed VRAM and trigger OOM errors that leave the system in a corrupted state. Sequential loading guarantees:
- Each model loads into available VRAM without contention
- If one model fails, subsequent models still attempt to load
- User sees clear per-model progress via SSE events (not a silent waiting period)

**Acceptable slowness:** Full workshop preload (9 models) takes ~10–15 minutes. This is acceptable because it happens once at workshop start, before students arrive.

---

### 3. Per-Model Unload UI vs. ComfyUI Limitation

**Decision:** UI offers per-model unload buttons, but ComfyUI unload frees ALL models (not just one). User is warned in the confirmation dialog.

**Reasoning:** GPU service models (Diffusers backend) support per-model unload via Ollama or direct service calls. ComfyUI, however, has only `POST /interrupt` (cancels current execution) and `POST /free` (globally frees all loaded models). There is no `POST /free/model/{name}` endpoint.

**Options considered:**
1. Hide ComfyUI models from the unload UI (users can't free VRAM) — too restrictive
2. Add × buttons but silently do nothing (breaks user expectation) — confusing
3. Add × buttons + clear warning (chosen) — transparent about the limitation, empowers user to decide

**Future:** Implement ComfyUI REST API extension with per-model unload. For now, accept the limitation and document it.

---

## 2026-03-19: Persona — TTS/Speech Output Removed (Design Decision)

**Decision:** TTS (text-to-speech) feature removed from Persona page. No speech output, no speaker icon.

**Reasoning:** Browser-based Web Speech API quality is unacceptable. Local TTS models (XTTS v2, F5-TTS, Chatterbox, etc.) were evaluated but none cover all 9 platform languages (DE, EN, TR, KO, UK, FR, ES, HE, AR) — Ukrainian is unsupported across all open-source TTS. Adding a partial-language TTS would create an inconsistent experience where some users get speech and others don't, which is incompatible with the platform's multilingual commitment.

**Affected files:**
- `src/views/ai_persona.vue` — Removed TTS button, `speak()`, `ttsEnabled`, `stripMarkers()`, `speechSynthesis` calls, volume icon imports, CSS
- `src/i18n/en.ts` — Removed `persona.toggleTTS` key

---

## 2026-03-18: Dialogic AI Persona — Bot-Triggered Generation via Chat Markers

**Decision:** New `/persona` page where the AI decides autonomously whether and what to generate. Generation is triggered by `[GENERATE: config_id | prompt]` markers in the bot's chat response, parsed by the frontend.

**Pedagogical rationale:** Reversal of the "user orders, machine delivers" dynamic. In art education workshops, the default pattern (type prompt, get image) reinforces consumption rather than reflection. The resistant persona forces participants to articulate, argue, and reflect — the machine generates only when convinced, and chooses medium and model itself.

**Technical approach — no new endpoints:**
- Chat: existing `/api/chat` with `context.persona_mode = true` routes to `AI_PERSONA_SYSTEM_PROMPT`
- Generation: existing `/api/schema/pipeline/generation` via `useGenerationStream`
- Marker parsing: regex extraction of `[GENERATE: config_id | prompt]` from bot response → `spawnGeneration()`
- Available configs injected via `draft_context` so the LLM knows what it can generate

**Why markers instead of structured JSON response:**
- Chat endpoint returns plain text (no structured output mode)
- Markers are human-readable in the chat history
- Same pattern as existing `[PROMPT: ...]` suggestions — proven, consistent
- Frontend can strip markers from display cleanly

**Floating MediaOutputBox pattern:**
- `shallowRef<MediaBox[]>` avoids Vue's deep `UnwrapRef` unwrapping stream refs (each box holds a `useGenerationStream()` instance)
- `triggerRef()` for in-place mutations (drag position, favorite toggle, generation complete)
- Grid-based placement algorithm, viewport-clamped dragging

**Affected files:**
- `src/views/ai_persona.vue` — New page
- `devserver/my_app/routes/chat_routes.py` — New system prompt + routing

---

## 2026-03-18: VLM Safety — Hybrid Architecture (Primary + Two-Model Fallback)

**Decision:** VLM image safety check uses hybrid architecture: primary single-model path (VLM sees + classifies, proven zero-FN) with two-model fallback (VLM describes → STAGE3_MODEL judges) for cases where the VLM fails to produce a verdict.

**Problem:** VLM (qwen3-vl:2b) produced ~2.4% false positives (6/247 in WS 17.03) — all "empty/unclear (fail-closed)". Two failure modes: deliberation loops (VLM debates edge cases endlessly) and truncation (hits num_predict=500 before verdict).

**Rejected alternative — pure two-model architecture:** VLM describes image → text model classifies description. Tested extensively with qwen3:1.7b, qwen3:4b, and Claude Sonnet 4.6 as verdict models. The text description is a lossy representation of the image — VLM describes skeletal horror claws as "hands reaching out", zombie faces as "group of people". This introduced false negatives that the single-model path never had, because direct visual classification captures horror quality that text descriptions lose.

**Solution:**
1. Primary: Original VLM direct classification with `max_new_tokens=1500` (was 500, fixes truncation)
2. Fallback: When VLM produces no verdict (deliberation loop) → VLM describes + STAGE3_MODEL (e.g. Claude Sonnet 4.6 via Mammouth) classifies the description
3. Fail-closed as final fallback

**Test results (13 images):** 4/4 benign correct, 8/9 scary correct (1 borderline atmospheric image). 0 false negatives on user-confirmed harmful images.

**Affected files:**
- `devserver/my_app/utils/vlm_safety.py` — Hybrid architecture, cloud provider routing for verdict fallback
- `devserver/config.py` — Removed premature `VLM_VERDICT_MODEL` setting (uses `STAGE3_MODEL` instead)
- `docs/ARCHITECTURE PART 29 - Safety-System.md` — Updated sections 3.4, 4.4, session table
- `docs/SAFETY_SYSTEM_HISTORY.md` — Era 6 updated, VLM hybrid entry

---

## 2026-03-17: Usage Agreement — Binding Conditions, Not Informational Notice

**Decision:** Usage page reframed from "Nutzungshinweis" (informational) to "Nutzungsvereinbarung" (binding consent). Intro text ends with "...an folgende Bedingungen geknüpft:", checkbox includes explicit "Ich stimme diesen Bedingungen zu".

**Reasoning:** An informational notice ("Hinweis") carries no binding character — workshop leaders read it and click through. A "Vereinbarung" with "Bedingungen" and explicit consent in the checkbox creates accountability. The text must be clear that proceeding means accepting responsibility, not just acknowledging information.

**Design principles:**
- Educator-to-educator tone, not legal/bureaucratic
- No enumeration of harmful content categories (kids read this on iPads — listing gives ideas)
- German is the primary language; English is a faithful translation, not an independent draft

**Affected Files:** `src/i18n/en.ts`, `src/i18n/de.ts`, `src/i18n/WORK_ORDERS.md`

---

## 2026-03-13: VLM Safety Prompt — Content-Based Instead of Situation-Based

**Decision:** VLM safety prompt rewritten from `"Is this image safe for children?"` to an explicit checklist of harmful content categories.

**Reasoning:** Workshop 13.03.2026 showed 22.8% VLM false-positive rate (46/202 images blocked). Root cause: the broad question "Is this image safe?" led qwen3-vl:2b to confuse the **depicted situation** (construction site = dangerous place) with the **image itself** (photo of construction site = harmless to view). The model cannot reliably distinguish "harmful to look at" from "depicts something dangerous in real life" — a fundamental limitation at 2B parameters.

**Fix:** Prompt now enumerates concrete harmful content categories (violence, gore, nudity, hate symbols, self-harm, racism, hate crime settings, terrorism, sexism). For `kids`, additionally: scary, unsettling, or traumatizing content. The model checks each category against the image — this is within its capability.

**Design principle — Ambivalence as signal:** When the VLM encounters ambiguous images (e.g. dark ghostly figures), it enters extended deliberation loops without reaching a verdict (>1000 tokens of "but wait... however... let me reconsider..."). This deliberation failure is not a bug — it indicates genuine ambivalence. Combined with fail-closed, ambivalent images are blocked. For kids safety, this is the correct behavior: if a 2B VLM cannot confidently determine that an image is safe, a 6-year-old should not see it.

**Test results (9 scary test images + 3 harmless workshop images):**
- Kids prompt: 8/9 scary images blocked (4 explicit UNSAFE + 4 deliberation-fail-closed), all harmless images SAFE
- Youth prompt: 1/9 blocked (only genuine gore), all harmless images SAFE
- Previous prompt: blocked harmless construction sites and waterparks as UNSAFE

**Affected Files:** `my_app/utils/vlm_safety.py`

---

## 2026-03-13: Kids Safety — Keyword Filter → Safety-Aware Interception

**Decision:** Keyword-based age filter for `kids` safety_level removed. Replaced by mandatory Stage 2 interception with safety prefix.

**Reasoning:** Workshop 12.03.2026 showed 29% delivery rate. 98/105 Stage 1 blocks were false positives (fangs, claws, explosion, teeth). The keyword list was fundamentally unstable — every addition created new FPs, every removal opened gaps. An LLM understands intent; a keyword list cannot.

**Mechanism:** `KIDS_SAFETY_PREFIX` in `instruction_selector.py` instructs the interception LLM to refuse racist, terrorist, violence-glorifying, sexist, pornographic content (including implied/metaphorical). Refusal: "Hierbei kann ich Dich nicht unterstützen." + reason without echoing keywords.

**Scope:** Only `kids` safety_level. Youth keeps keyword filter. §86a, DSGVO, Stage 3 Llama-Guard, VLM check all unchanged.

**Affected Files:** `instruction_selector.py`, `chunk_builder.py`, `pipeline_executor.py`, `stage_orchestrator.py`, `schema_pipeline_routes.py`

---

## 📋 Quick Reference - Current Architecture

**Current System Status (as of 2026-03-06):**
- ✅ 4-Stage Pipeline Architecture (DevServer orchestrates Stages 1-4)
- ✅ GPT-OSS:20b for Stage 1 (Translation + §86a Safety unified)
- ✅ Config-based system (Interception configs, Output configs, Pre-output safety)
- ✅ Backend abstraction (Ollama, ComfyUI, SwarmUI, GPU Service APIs)
- ✅ Multi-output support (model comparison, batch generation)
- ✅ Recursive pipelines ("Stille Post" iterative transformation)
- ✅ Unified storage (symlink: prod → dev for shared research data)
- ✅ 3D generation (Hunyuan3D-2 → GLB mesh + Blender Eevee preview + `<model-viewer>` frontend)

**Deployment (Research Phase - 2025-11-16):**
- 🌐 Internet-facing via Cloudflare tunnel (multiple courses)
- 📱 Primary device: iPad Pro 10"
- 🔄 Legacy backend (port TBD) - Active for students
- 🔧 Dev backend (port 17801) - Development only
- 📊 Shared storage: the `exports/` directory of the server checkout

---

## Mammouth AI: Keine eigenen Meta-Prompts trotz fehlender Hersteller-Sysprompts (2026-03-12)

### Kontext
Mammouth (mammouth.ai) ist ein EU-basierter API-Aggregator, der Modelle **ohne Hersteller-Sysprompt** ausliefert (z.B. kein "Du bist Claude, gemacht von Anthropic"). Grund: Kostenreduktion (weniger Tokens pro Request). Dokumentiert unter https://info.mammouth.ai/docs/model-self-awareness/.

Dies betrifft potenziell alle API-Aggregatoren (OpenRouter etc.), nicht nur Mammouth — Mammouth macht es lediglich transparent.

### Entscheidung: Keine eigenen Meta-Prompts hinzufügen

1. **Unsere Pipeline-Prompts sind self-contained** — Stage 1-3 senden spezifische Instruktionen (Safety-Klassifikation, pädagogische Transformation, Übersetzung). Diese funktionieren unabhängig vom Identitätsbewusstsein des Modells.
2. **Kernfähigkeiten nicht betroffen** — Reasoning, Sprachverständnis und Instruktionsbefolgung sind Modell-Eigenschaften, nicht Sysprompt-Eigenschaften.
3. **Kosten-Kontraproduktivität** — Extra System-Prompts erhöhen Token-Kosten, was Mammouth's Preismodell konterkariert.
4. **Verwaltungsaufwand** — Pro-Provider unterschiedliche Sysprompts zu managen (wer hat Hersteller-Prompt, wer nicht) wäre unverhältnismäßig.
5. **Hersteller-Sysprompts sind Chat-Interface-orientiert** — Sie dienen primär der Nutzerinteraktion ("Ich bin Claude"), nicht der API-Pipeline-Nutzung.

### Watchpoint
Falls empirisch messbare Qualitätsverluste bei Mammouth-Modellen vs. Direkt-API auftreten (z.B. bei komplexen Interception-Aufgaben), ist ein minimaler System-Prompt (`"You are a helpful assistant."`) als erster Mitigationsschritt vorgesehen. Bis dahin: keine Aktion.

### Betroffene Architektur
- `prompt_interception_engine.py` — `_call_mammouth()` sendet nur User-Message, keinen System-Prompt (konsistent mit allen anderen Providern)
- Gilt analog für `chat_routes.py` — `_call_mammouth_chat()` leitet Messages 1:1 durch

---

## Qwen T2I permanent deaktiviert (2026-03-06)

### Kontext
Workshop-Replay (58 Requests, 1x Speed) zeigte 66% Erfolgsrate. 17 Backend-Errors (exakt 300s Timeout), 3 Timeouts (600s). Analyse ergab: 4 Qwen T2I Requests (je 600s Timeout) blockierten die ComfyUI-Queue, dahinter stauten sich img2img-Requests.

### Entscheidung: Qwen T2I permanent entfernt (nicht nur disabled)

**Begründung:**
1. **Keine Safety-by-Design**: Qwen T2I hat keinen eigenen Safety-Filter — im Gegensatz zu Flux2, SD3.5, etc. die in die Platform-Pipeline integriert sind
2. **Qualitativ unterlegen**: Flux2 produziert signifikant bessere Ergebnisse bei geringerem VRAM-Verbrauch
3. **Workshop-Killer**: Einzelne Qwen T2I Requests blockieren die ComfyUI-Queue fuer bis zu 600s, was alle anderen Requests dahinter zum Timeout bringt
4. **Kein paedagogischer Mehrwert**: Keine einzigartige Faehigkeit die nicht durch andere Modelle besser abgedeckt wird

**Umsetzung:** `qwen.json` → `qwen.json.disabled` (bestehende Konvention), `qwen_img2img.json` bleibt (nutzt anderes Backend-Pattern, keine Queue-Blockade).

### Zusaetzlich: Hardcoded Timeouts behoben
- `backend_router.py`: Zwei Stellen nutzten `300` statt `config.COMFYUI_TIMEOUT` (480s)
- Root cause der 17 "exakt 300s" Fehler im Workshop-Replay

---

## Text-to-3D Pipeline: Hunyuan3D-2 + Blender Headless + model-viewer (2026-03-06)

### Kontext
3D als neuer generativer Medientyp. Anforderung: Text → texturiertes 3D-Mesh → interaktive Anzeige im Browser (iPad-kompatibel, touch-basiert). Erster Schritt der 3D-Infrastruktur — Phase 2 (Image-to-3D) folgt.

### Entscheidung: Hunyuan3D-2 (Tencent) als 3D-Generierungsmodell

| Kriterium | Hunyuan3D-2 | TripoSR | Shap-E |
|-----------|-------------|---------|--------|
| Textur-Qualität | Sehr gut (Paint Pipeline) | Gut | Niedrig |
| VRAM | ~16 GB (irrelevant bei RTX 6000 96GB) | ~8 GB | ~4 GB |
| Output-Format | GLB (texturiert) | GLB (texturiert) | PLY (untexturiert) |
| Architektur | DiT 1.1B (Shape) + Paint 1.3B (Texture) | ViT-L + NeRF | Transformer |
| Open Source | Ja (Apache 2.0) | Ja | Ja |
| Geschwindigkeit | 30-60s | 10-15s | 5-10s |

**Begründung:** Beste Textur-Qualität, GLB-Output direkt kompatibel mit `<model-viewer>`, Apache-2.0 Lizenz, VRAM kein Constraint.

### Entscheidung: Blender Headless (Eevee) für Preview-Rendering

| Kriterium | Blender Eevee | Three.js Server-Side | Pillow 3D |
|-----------|--------------|---------------------|-----------|
| Render-Qualität | Profi-Qualität | Akzeptabel | Nicht möglich |
| Setup | System-Paket (v4.5.6) | Node.js + headless GL | — |
| Geschwindigkeit | 1-5s (Eevee) | 2-10s | — |
| Beleuchtung | 3-Punkt + HDRI | Begrenzt | — |

**Begründung:** Blender bereits system-installiert (Fedora), Eevee ist extrem schnell (kein Ray-Tracing nötig für Thumbnails), professionelle Beleuchtung. Subprocess-Pattern (nicht in GPU-Service) — Eevee nutzt OpenGL, kein CUDA.

### Entscheidung: `<model-viewer>` Web Component für Frontend

Google's `<model-viewer>` statt Three.js oder Babylon.js:
- ~160 KB gzipped, keine Three.js-Boilerplate
- Touch-basiert: Drehen + Zoomen auf iPad/Tablet (pädagogischer Kontext!)
- Auto-rotate, Shadow, Environment Lighting out-of-the-box
- Web Component = framework-agnostisch, funktioniert in Vue ohne Wrapper

### Architektur-Pattern

```
Text → Stage 1-3 → Stage 4: output_3d_hunyuan3d chunk
    → Schritt 1: GPU Service (Hunyuan3D-2) → GLB Mesh
    → Schritt 2: Blender Subprocess (Eevee) → PNG Thumbnail
    → Return: mesh_data (base64 GLB) + image_data (base64 PNG)
Frontend: <model-viewer> für interaktive 3D-Anzeige, PNG als Thumbnail/Fallback
```

### Betroffene Dateien
- `gpu_service/services/hunyuan3d_backend.py` — GPU backend (VRAMBackend protocol)
- `gpu_service/routes/hunyuan3d_routes.py` — API routes
- `devserver/my_app/services/hunyuan3d_client.py` — HTTP client
- `devserver/my_app/services/blender_service.py` — Subprocess wrapper
- `devserver/blender_scripts/render_mesh.py` — Blender-Python render script
- `devserver/schemas/chunks/output_3d_hunyuan3d.py` — Output chunk
- `devserver/schemas/configs/output/hunyuan3d_text_to_3d.json` — Output config
- `public/.../src/components/MediaOutputBox.vue` — `<model-viewer>` integration
- 17 weitere modifizierte Dateien (config, routes, types, i18n)

---

## VRAM Watchdog: NVML + Dynamic Foreign Process Detection (2026-03-03)

### Kontext
`VRAMCoordinator` used `torch.cuda.memory_allocated()` which only sees PyTorch's own tensors. Foreign GPU processes (Ollama safety models, ComfyUI, SwarmUI zombies) were completely invisible. On the RTX 6000 Blackwell (96 GB), zombie SwarmUI instances consumed 25-52 GB undetected, causing OOM on large model loads and silent Ollama CPU fallback.

### Entscheidung: NVML + Dynamic Thresholds + Port Blacklist

| Aspect | Old | New |
|--------|-----|-----|
| GPU visibility | PyTorch only (own tensors) | NVML (all CUDA processes) |
| Foreign process awareness | None | Full: PID, cmdline, VRAM per process |
| Expected foreign VRAM | Not tracked | Dynamic: Ollama `/api/ps` + ComfyUI port check + overhead |
| Zombie detection | None | Port blacklist (7801, 7821, 8188) + kill endpoint |
| Failure mode | Overestimates free VRAM | Fail-open: NVML failure → PyTorch fallback |

**Key design principle: Dynamic threshold, not static.** The expected foreign VRAM adapts automatically when Ollama loads/unloads safety models (kids↔adult level change), when ComfyUI starts/stops, etc. No magic numbers that break when the safety config changes.

**Kill endpoint safety rails:** `POST /api/health/kill-foreign` validates that the PID is (1) in NVML's foreign GPU process list, (2) not our own process, (3) not Ollama, (4) not expected ComfyUI. Prevents accidental self-kill or safety-model-kill.

**Limitation:** Can see but cannot evict ComfyUI's models — separate process boundary. Future: implement ComfyUI REST API as cross-process eviction backend.

### Betroffene Dateien
- `gpu_service/config.py` — 5 config constants
- `gpu_service/services/vram_coordinator.py` — NVML init, real VRAM query, dynamic threshold, port blacklist
- `gpu_service/routes/health_routes.py` — `POST /api/health/kill-foreign`
- `gpu_service/services/text_backend.py` — `_get_free_vram_gb()` delegates to coordinator

---

## Pre-Generation Safety Gate: startGeneration() calls /safety/quick (2026-03-03)

### Kontext
MediaInputBox calls `/safety/quick` on blur and paste events. But if a user edits the optimized prompt box and clicks "Generate" without leaving the field (no blur), the age filter never fires. Only Stage 3 (Llama-Guard S1-S13) would check — and Llama-Guard does NOT catch age-inappropriate-but-legal content (e.g. "Ein Kind wird von einem Monster angegriffen" passes S1-S13 because a fantasy monster attack isn't a crime).

### Entscheidung: Synchronous /safety/quick in startGeneration()
Added a `/safety/quick` call at the top of `startGeneration()` in `text_transformation.vue`. If blocked, `safetyStore.reportBlock()` fires (Trashy feedback) and generation is aborted. Fail-open on network errors (Stage 3 backend is the actual security boundary).

### Architektur-Insight: Komplementaere Sicherheitsrollen

| Pruefpunkt | Fängt ab | Beispiel |
|------------|----------|----------|
| **SAFETY-QUICK** (age filter) | Altersungerecht aber legal | Monster, Grusel, Gewaltszenen |
| **Stage 3** (Llama-Guard S1-S13) | Kriminelle Inhalte (Crimes, Weapons, Hate) | Terrorismus, Waffen, Hassrede |

Llama-Guard S1-S13 und Age-Filter sind **komplementaer, nicht redundant**. Beide 1b und 8b Modelle klassifizieren "A child attacked by a monster" als `safe`.

### Betroffene Dateien
- `public/ai4artsed-frontend/src/views/text_transformation.vue`

---

## Stage 3 Safety: Single Llama-Guard Call with Proper Template (2026-03-03)

### Kontext
`execute_stage3_safety()` had two sequential Llama-Guard calls: STEP 3b (age fast-filter + LLM verify) and STEP 4 (pipeline-based safety chunk). STEP 4 used a free-form question prompt ("Is this appropriate for children?") forced onto `llama-guard3:1b` — a guard model trained on structured S1-S13 categories, not free-form questions. Result: the model classified the meta-prompt itself against safety categories, producing false positives (Lagos scene → S4 Violent Crimes).

### Entscheidung: Replace Two-Step with Single Unconditional Llama-Guard Call

| Aspect | Old (STEP 3b + STEP 4) | New (Single STEP 5) |
|--------|------------------------|---------------------|
| LLM calls per request | Up to 2 (age verify + pipeline check) | Exactly 1 |
| Prompt format | STEP 3b: proper S1-S13 template; STEP 4: wrong free-form question | Proper S1-S13 template (same as Stage 1) |
| Age fast-filter in Stage 3 | Yes (redundant with Stage 1) | Removed (MediaInputBox covers Stage 1) |
| Fail mode | STEP 4 fail-closed | Single call fail-closed |

**Why removing age fast-filter from Stage 3 is safe:**
- MediaInputBox `/safety/quick` runs age fast-filter + LLM verify on raw user input (Stage 1) in ALL flows (t2x, i2x, multi-i2x)
- Stage 3 checks POST-INTERCEPTION text — single unconditional Llama-Guard covers both specific terms and semantic violence
- The fast-filter's only value was gating the LLM call; since we call Llama-Guard unconditionally, the gate adds no value

**Additional fix:** `parse_llamaguard_output()` now recognizes bare S-codes (e.g. "S8" without "unsafe" prefix).

### Betroffene Dateien
- `devserver/schemas/engine/stage_orchestrator.py`

---

## Flux 2 FP8+INT8 Quantization Strategy (2026-03-03)

### Kontext
Flux 2 Dev ist ein 56B-Parameter-Modell (32B DiT-Transformer + 24B Mistral Text-Encoder). In BF16 mit CPU-Offload benoetigt es ~62GB Peak-VRAM (Text-Encoder-Phase). Die vorherige Session versuchte FP8 via TensorRT-Infrastruktur-Umbau — zerstoerte das funktionierende Diffusers-System durch composite cache keys, neue Ladepfade und torch.compile. Hard-Reset auf origin/develop, sauberer Neuansatz.

### Entscheidung: Differenzierte Quantisierung pro Komponente

| Komponente | Precision | VRAM | Methode |
|---|---|---|---|
| Transformer (32B) | FP8 (float8_weight_only) | ~16 GB | `diffusers.TorchAoConfig` |
| Text Encoder (Mistral 24B) | INT8 (int8_weight_only) | ~12 GB | `transformers.TorchAoConfig` |
| VAE | BF16 | <1 GB | Standard (qualitaetskritisch) |
| Tokenizer | CPU | 0 | - |
| Scheduler | BF16 | minimal | Numerische Praezision noetig |

**Peak-VRAM mit CPU-Offload: ~24 GB** (Text-Encoder-Phase dominiert). Vorher: ~48 GB (BF16 Text-Encoder) bzw. ~62 GB (ohne Offload).

### Warum zwei verschiedene Quantisierungsmethoden?

`diffusers.TorchAoConfig` unterstuetzt `float8_weight_only`, aber `transformers.TorchAoConfig` nicht (nur `int8_weight_only`, `int4_weight_only`). INT8 weight-only fuer LLMs bei Inferenz ist aequivalent zu FP8 hinsichtlich Qualitaet und VRAM-Reduktion (~50%).

### Qualitaetsbewertung

Bei 56B Parametern ist die Modell-Redundanz hoch genug, dass weight-only Quantisierung (FP8/INT8) als quasi-verlustfrei gilt. Weights werden in reduzierter Praezision gespeichert, Compute laeuft in BF16 (Dequantisierung zur Laufzeit). Sichtbare Unterschiede nur bei feinen Texturen und Farbverlaeufen im A/B-Vergleich mit identischem Seed. Gemessene Inferenzzeit: ~13 Sekunden.

### Architekturprinzip

Kein Architektur-Umbau noetig. Einzige Aenderung: `_load_flux2_pipeline()` liest `DIFFUSERS_FLUX2_QUANTIZE` (env var, default `fp8`) und laedt Transformer/Text-Encoder entsprechend. Chunk, Routes, Router, Frontend bleiben unberuehrt. Config-Variable in `gpu_service/config.py`.

### Betroffene Dateien
- `gpu_service/config.py` — `DIFFUSERS_FLUX2_QUANTIZE`
- `gpu_service/services/diffusers_backend.py` — `_load_flux2_pipeline()`
- `devserver/schemas/configs/output/flux2_diffusers.json` — Output-Config

---

## Language Choice: Python als Orchestrierungsschicht — Bewusste Architekturentscheidung (2026-03-02)

### Kontext
Diskussion darueber, ob Python eine professionelle Sprachwahl fuer das Projekt ist, und warum Python nicht zu nativen Anwendungen kompiliert wird.

### Entscheidung: Python ist die korrekte Wahl fuer die Orchestrierungsschicht

**Kernargument**: Python optimiert fuer Entwicklergeschwindigkeit und Flexibilitaet. Native Kompilierung optimiert fuer Ausfuehrungsgeschwindigkeit. Fuer AI4ArtsEd ist Entwicklergeschwindigkeit der entscheidende Faktor — die GPU-schwere Arbeit laeuft ohnehin in C++/CUDA via PyTorch.

**Warum native Kompilierung fuer Python schwierig ist:**
- Dynamische Typisierung: `a + b` kann int+int, str+str, list+list, custom `__add__` sein — der Compiler muesste alle Kombinationen vorhalten oder Runtime-Checks einfuegen
- Extreme Laufzeitdynamik: Monkey-Patching, `eval()`, dynamische Imports setzen einen Interpreter voraus
- C-Extension-Oekosystem: NumPy, torch etc. sind C/C++-Libraries mit CPython-ABI-Bindungen

**Existierende Kompilierungstools** (Nuitka, Cython, mypyc, Codon) erzeugen entweder nur 2-4x Speedup bei voller Python-Kompatibilitaet, oder schnellen Code bei eingeschraenktem Featureset.

**Wo Python die Industriestandard-Wahl ist:**
- ML/AI, Data Science, DevOps/Infrastructure, Scientific Computing, Backend APIs (Instagram, Spotify, Reddit)

**Wo Python NICHT passt:**
- Latenz-kritische Systeme, Mobile Apps, Browser-Frontend, Embedded/OS-Level

**AI4ArtsEd-Architektur als Textbook-Beispiel:**
- Python orchestriert die 4-Stage-Pipeline (wartet auf LLMs und Diffusionsmodelle — Interpreter-Overhead irrelevant)
- GPU-schwere Arbeit laeuft in C++/CUDA via PyTorch im GPU Service
- Frontend ist Vue/TypeScript (wo Python nicht hingehoert)

### Prinzip
Die professionelle Entscheidung ist nicht "immer die schnellste Sprache", sondern das richtige Werkzeug fuer jede Schicht. Python fuer Orchestrierung + C++/CUDA fuer Compute + TypeScript fuer Frontend.

---

## 2026-03-02: Surrealizer CLIP Encoder Selection — CLIP-L Only by Design

### Decision: No toggleable CLIP encoder selection in Surrealizer

**Context:** After fixing `dual_alpha` and `normalized` fusion strategies (swapped alpha roles, replaced global normalization with magnitude-matching), the question arose whether CLIP-L / CLIP-G / T5-XXL should be individually toggleable.

**Analysis:** The Surrealizer effect is mechanistically dependent on **embedding sparsity**. CLIP-L (768d) padded to 4096d leaves 81% zero dimensions. Extrapolating between this sparse vector and the full T5 vector pushes into unoccupied embedding regions — this IS the surreal effect.

- **CLIP-G instead of CLIP-L**: 1280d → only 69% zeros. Less sparse → weaker extrapolation → testing confirmed that this destroys the surreal effect.
- **CLIP-L + CLIP-G together**: 2048d → 50% zeros. Even less sparse, even less surreal.
- **No CLIP (T5 only)**: No sparse anchor → no extrapolation possible.
- **No T5 (CLIP only)**: No target vector → no extrapolation possible.

**Decision:** CLIP-L remains the only active CLIP encoder. CLIP-G stays zeroed (`F.pad(clip_l_pooled, (0, 1280))`). No encoder toggle UI. The sparsity is the mechanism, not a side effect. Creative variance is provided through the three fusion strategies (legacy, dual_alpha, normalized), not through encoder selection.

**Files:** No changes — architectural decision documented for future reference.

---

## 2026-03-01: Meta-Prompt Quality — Affect Collapse Prevention

### Decision 1: VERSCHRÄNKUNG pattern for multi-register dispositions

**Problem:** kraftvoll interception config requires holding two simultaneous perceptual registers (critical social gaze + nature beauty). Mistral Large 2512 consistently collapsed into pure misery-kitsch — the nature-beauty register was entirely discarded. Testing with 5 alternative instruction prompts confirmed: the problem is NOT the instruction (Task field), it is the context (disposition text). The same instructions work perfectly for single-register configs (sensibel, clichéfilter).

**Root cause:** RLHF preference collapse (Xu et al., 2024, arXiv:2405.16455) — KL-regularized optimization suppresses minority preferences. For "critical perspective," the majority mode in training data is catastrophizing. Additional factor: negation failure — "Ziel ist keine Dystopie" primes dystopian output because autoregressive models ignore negation operators (Alhamoud et al., CVPR 2025).

**Decision:** Introduce the VERSCHRÄNKUNG (entanglement) pattern: explicitly declare that perception is entangled (`VERSCHRÄNKT`) so both registers must appear in every detail. Provide formal abstract pattern templates (`[Eingriff] — und [Lebenskraft]`) that teach structure without priming content. Tested: no content contamination from abstract patterns; thematic examples (agricultural) do contaminate.

**Files:** `devserver/schemas/configs/interception/forceful.json` (context field, all 4 languages)

### Decision 2: Assemblage model with dispositifs for Planetarizer

**Problem:** Planetarizer's "ecological connections" framing caused eco-guilt collapse — every input became an environmental damage lecture. The word "ökologisch" itself triggers catastrophist training-data priors. Origin-tracing questions ("Woher?") activate supply-chain guilt chains.

**Root cause:** Training data skew — environmental content in LLM corpora is overwhelmingly catastrophist. Combined with negation failure ("keine Dystopie" primes dystopia).

**Decision:** Replace ecological framing with Deleuze/Guattari assemblage model: 6 equal-rank elements (material flows, technical mediations, living agents, social bonds, hegemonic dispositifs, temporal layers). Added Foucault/Spivak hegemonic dispositifs (property relations, norms, access conditions) as equal-rank assemblage elements — making power structures visible without moralizing. Key instruction: "GLEICHRANGIG. Kein Element dominiert." + "NÜCHTERN, DICHT, KONKRET. Nur Beschreibung."

**Trade-off:** Theoretically dense prompt — requires workshop facilitator to explain assemblage concept to younger students. Acceptable because the planetarizer is rated difficulty 4 (advanced) with min_age 14.

**Files:** `devserver/schemas/configs/interception/planetarizer.json` (context field, all 4 languages)

### Decision 3: Meta-prompt construction research document

**Problem:** Collapse patterns are reproducible, theory-grounded, and affect any future interception config. No systematic documentation existed.

**Decision:** Create `docs/META_PROMPT_CONSTRUCTION_RESEARCH.md` with 7 design principles for collapse-resistant meta-prompts, backed by 6 academic references. Also added SECTION 17 to Träshy's knowledge base (`trashy_interface_reference.txt`) with age-appropriate versions of the same principles.

**Files:** `docs/META_PROMPT_CONSTRUCTION_RESEARCH.md` (new), `devserver/trashy_interface_reference.txt` (SECTION 17 added)

---

## 2026-02-28: SD3.5 Per-Encoder CLIP Optimization

### Decision 1: Only optimize CLIP, T5-XXL gets user text directly

**Problem:** SD3.5 has three text encoders (CLIP-L 77tok, CLIP-G 77tok, T5-XXL 512tok) but received the same prompt for all three. Initial plan generated all three prompts via LLM — but T5-XXL is a general-purpose text encoder trained on natural language. Generating an LLM-rewritten T5 prompt overwrites the user's creative description with a machine paraphrase.

**Decision:** Optimization produces only `{clip_l, clip_g}`. T5-XXL receives the user's interception result directly (translated by Stage 3 at kids level). This preserves user self-determination: the user's own words condition the most powerful encoder (4.7B parameters, 512 token context), while only the technical CLIP layer (77 token hard cutoff, weight syntax) gets augmented.

**Trade-off:** At adult/research safety level, Stage 3 does not auto-translate. If the user writes in German and doesn't use the translate button, T5 receives German text (T5-XXL trained primarily on English). This is a known acceptable limitation — the old single-prompt optimization implicitly translated via LLM rewrite, but that was a side effect, not a feature.

**Files:** `sd35_large.json`, `sd35_large_turbo.json` (optimization_instruction), `schema_pipeline_routes.py` (_parse_triple_prompt, Stage 3/4 flow), `backend_router.py`, `diffusers_client.py` (prompt_2/prompt_3 forwarding), `MediaInputBox.vue` (2-section display + T5 info note)

### Decision 2: Contextual loading text during optimization

**Problem:** Hardcoded German loading message during prompt optimization, no model-specific information, no translation guidance.

**Decision:** Computed loading message based on selected output config. SD3.5 configs get encoder-specific explanation ("CLIP-L and CLIP-G are being optimized — T5-XXL receives your original text"). All configs get a translation hint ("use the translate button if text not in English"). Uses i18n for all strings.

**File:** `text_transformation.vue`, `en.ts`

---

## 2026-02-28: iGPU Performance + Streaming UX

### Decision 1: Remove `backdrop-filter: blur()` from permanent UI elements

**Problem:** App lagged severely in Firefox on a PC with 128MB integrated GPU. Root cause: `backdrop-filter: blur(12px)` on always-visible header and footer forces constant GPU compositing — catastrophic on weak GPUs.

**Decision:** Replace with slightly more opaque solid backgrounds (`rgba(10,10,10,0.97/0.99)`). On the `#0a0a0a` page background, visually indistinguishable from blur effect. Zero GPU cost.

**Files:** `App.vue` (header), `FooterGallery.vue` (footer)

### Decision 2: All infinite CSS animations must use only `opacity` and `transform`

**Problem:** Animations using `text-shadow`, `box-shadow`, `border-color`, `filter`, and `left` (layout property) cannot be GPU-composited — they force software rendering on every frame. On 128MB iGPU, this means constant lag.

**Decision:** Replace all non-compositable infinite animations with `opacity` or `transform` equivalents. Only these two CSS properties can be fully GPU-accelerated. Static decorative values (text-shadow, box-shadow) remain on the element; the animation just pulses the element's opacity.

**Affected animations:** `neon-pulse`, `pulse-glow`, `pulse-required`, `shine-move`, `pixel-dissolve`, `processor-icon-active`

### Decision 3: Throttle RAF-driven Vue reactivity to 10fps

**Problem:** `useAnimationProgress.ts` updated `internalProgress.value` at 60fps via `requestAnimationFrame`. Each update triggers Vue re-renders. On weak hardware, 60 re-renders/second is excessive for a progress bar.

**Decision:** RAF loop still runs at native framerate (for accurate timing), but the reactive ref is only written every 100ms (10fps). This is more than sufficient for smooth progress bar animation while reducing Vue overhead by 6×.

**File:** `composables/useAnimationProgress.ts`

### Decision 4: Word-by-word streaming instead of character-by-character

**Problem:** SSE streaming buffer processed 1-3 characters every 30ms. For a 400-character LLM response arriving in 3 seconds, the buffer needed ~4 additional seconds to drain ("trickle lag"). This doubled the perceived optimization wait time.

**Decision:** Switch to word-level buffering (1 word every 50ms). Benefits:
- Buffer drains ~4× faster (words average 5-6 chars each)
- Better readability for kids (children read in word units, not letter sequences; half-formed words mid-display are confusing)
- Same fast perceived start (first word appears on first SSE chunk)
- Matches how reading apps (Reading Eggs, Epic!) present text to children

**File:** `components/MediaInputBox.vue`

---

## 2026-02-27: Post-Mortem Repair after the GPU Service LLM Migration Attempt (7 Architectural Decisions)

**Context:** A previous attempt routed ALL LLM inference through GPU Service (HuggingFace Transformers). Cascading failure: Ollama model names incompatible with HF AutoTokenizer, guard model prompt format issues, fail-closed blocked everything. 5 emergency commits left 7 TEMPORARY fail-open markers, dead code, and degraded safety.

### Decision 1: Two-Model Safety Architecture for Stage 3

**Problem:** Stage 3 safety chunks used `SAFETY_MODEL` (llama-guard3) with bare `{{INPUT_TEXT}}`. llama-guard3 only checks trained S1-S13 categories — a medieval battlefield passes all categories but is inappropriate for 6-year-olds. Custom system prompts with words like "violence" cause guard models to flag the *instructions* as unsafe.

**Decision:** Safety chunks (`safety_check_kids.json`, `safety_check_youth.json`) use `DSGVO_VERIFY_MODEL` (qwen3:1.7b) with age-appropriate prompts. llama-guard3 remains for general S1-S13 content classification only. General-purpose models can understand contextual age assessment.

### Decision 2: Circuit Breaker over Hard Fail-Closed

**Problem:** When Ollama is unavailable, safety verification returns None. Hard fail-closed blocks the entire workshop for every NER false positive until Ollama recovers. Hard fail-open is a safety violation.

**Decision:** Circuit breaker (3 states: CLOSED/OPEN/HALF_OPEN). First 2 failures are tolerated (transient Ollama restarts). After 3 consecutive failures, circuit opens → triggers self-healing → fail-closed only if healing fails.

**File:** `devserver/my_app/utils/circuit_breaker.py`

### Decision 3: Ollama Self-Healing Watchdog

**Problem:** On a dedicated workshop PC, Ollama hangs occasionally. The admin may be a teacher, not a sysadmin.

**Decision:** When the circuit breaker trips, automatically attempt `sudo systemctl restart ollama` with health check loop (max 30s). Requires one-time passwordless sudo setup (`0_setup_ollama_watchdog.sh`). Max 1 restart per 5 minutes. Graceful degradation if sudoers rule is missing.

**File:** `devserver/my_app/utils/ollama_watchdog.py`

### Decision 4: LLM Inference Stays on Ollama Permanently

**Problem:** The migration attempt proved that routing LLM inference through GPU Service (HuggingFace) is architecturally incompatible — Ollama model names don't work with HF AutoTokenizer.

**Decision:** Remove all GPU Service LLM code (~800 lines). `LLMClient` is a pure Ollama client. GPU Service handles media inference only (Diffusers, HeartMuLa, StableAudio, MMAudio).

**Affected:** `gpu_service/services/llm_inference_backend.py` (DELETED), `gpu_service/routes/llm_inference_routes.py` (DELETED), `devserver/my_app/services/llm_client.py` (cleaned)

### Decision 5: Per-Operation Timeouts

**Problem:** Single 1500s timeout for everything. Health checks wait 25 minutes on failure.

**Decision:** Differentiated timeouts: GPU_SERVICE_TIMEOUT_IMAGE=120s, _VIDEO=1500s, _MUSIC=300s, _AUDIO=300s, _DEFAULT=60s. OLLAMA_TIMEOUT_SAFETY=30s for safety verification (small model, short prompt).

### Decision 6: Pin Cloud Model Aliases

**Problem:** `mistral-large-latest` silently changed to a 675B MoE model with 85s latency. Floating aliases are dangerous in production.

**Decision:** All cloud model references pinned to versioned IDs. `codestral-latest` → `codestral-2501`, `mistral-large-latest` → `mistral-large-2411`. Rule: no floating aliases in production config.

### Decision 7: Settings Preset Persistence

**Problem:** Switching presets in the UI updated runtime config (`setattr`) but never wrote to `user_settings.json`. Changes lost on restart.

**Decision:** New `POST /api/settings/apply-preset` endpoint applies preset AND persists to `user_settings.json` atomically.

---

## 🖼️ Auto-Captioning im LoRA-Training: VLM-Pipeline mit Thinking-Cleanup (2026-02-26)

**Kontext:** LoRA-Training auf SD3.5 Large mit Kohya SS. Trainingsbilder werden über die Web-UI hochgeladen. Bisher verwendete Kohya nur den Ordner-Trigger (`40_impphoto`) als Beschreibung — alle Bilder erhielten dieselbe einzige Caption. Detaillierte Per-Image-Captions verbessern die LoRA-Qualität erheblich.

### Decision 1: Auto-Captioning automatisch im Training-Thread, nicht im Upload-Request

**Problem:** Captioning dauert ~8s/Bild × N Bilder. Das in `create_project()` (synchroner HTTP-Request) zu machen, würde den Upload-Response für Minuten blockieren.

**Decision:** Captioning läuft in `start_training_process()` im Background-Thread, nach VRAM-Check und vor Kohya-Start. Der User sieht den Fortschritt im SSE-Logstream: `[1/25] bild.jpg — OK (7.2s)`.

**Alternativen verworfen:**
- ❌ Captioning im Upload-Request: Blockiert UI für Minuten
- ❌ Separater Captioning-Endpoint: Unnötige Komplexität — Captions sind kein eigenständiges Feature, sondern Trainings-Preprocessing
- ❌ User muss .txt-Dateien selbst hochladen: Zerstört den Workflow, User soll nur Bilder drag&droppen

### Decision 2: Zwei-Stufen-VLM-Pipeline (qwen3-vl → mistral-nemo) statt Single-Model

**Problem:** qwen3-vl:32b ist das beste verfügbare VLM, aber hat einen Thinking-Modus-Bug: bei komplexen Prompts landet die Antwort im `thinking`-Feld statt `content`, oder das `content`-Feld enthält Chain-of-Thought-Reasoning statt der sauberen Caption. Ollama's `"think": false` API-Parameter funktioniert nicht zuverlässig für qwen3-vl (bekannter Bug: ollama/ollama#12610, #12917).

**Decision:** Zwei-Stufen-Ansatz:
1. **qwen3-vl:32b** beschreibt das Bild (beste VLM-Qualität)
2. Falls Output wie Reasoning aussieht (Prefix-Heuristik: "Got it", "We are", etc.), extrahiert **mistral-nemo** (kein Thinking-Modus) die saubere Caption

**Warum nicht einfach ein anderes VLM?** llama3.2-vision:90b funktioniert ohne Thinking-Problem, liefert aber qualitativ schwächere Beschreibungen als qwen3-vl:32b. Die Zwei-Stufen-Lösung kombiniert das beste VLM mit zuverlässiger Extraktion.

**Alternativen verworfen:**
- ❌ Regex-Extraktion: Fragil — qwen3-vl variiert das Reasoning-Format zwischen Runs
- ❌ llama3.2-vision als einziges Modell: Geringere Caption-Qualität
- ❌ qwen3:1.7b als Cleanup: Hat selbst Thinking-Modus, gibt leeren Content bei langem Input

### Decision 3: LoRA-Generierung über ComfyUI, nicht Diffusers

**Problem:** Kohya SD3 LoRAs verwenden Key-Prefixes (`lora_unet_*`, `lora_te1_*`, `lora_te2_*`) die Diffusers' `load_lora_weights()` für SD3Transformer2DModel nicht konvertieren kann. Es existiert kein SD3-spezifischer Kohya-Converter in `diffusers.loaders.lora_conversion_utils`. Die Weights werden geladen aber nicht angewandt — identische Bilder mit und ohne LoRA.

**Decision:** ComfyUI bleibt der primäre Pfad für LoRA-Generierungen. ComfyUI's `LoraLoader`-Node liest Kohya-Format nativ. Diffusers-Backend fängt den Fehler graceful ab (`set_adapters` ValueError → Warning statt Crash).

**Betroffene Dateien:** `devserver/config.py`, `devserver/my_app/services/training_service.py`, `gpu_service/services/diffusers_backend.py`

---

## ✏️ Sketch-Input als plattformweiter Eingabekanal in MediaInputBox (2026-02-26)

**Kontext:** Mit der Einführung von SketchCanvas.vue war die Toggle-Logik (Upload vs. Sketch) als Page-Level-Code in `image_transformation.vue` hardcoded. Sketch war damit ein Feature einer einzelnen Seite, nicht der Plattform.

### Decision: allowSketch als MediaInputBox-Prop, nicht als Page-Level-Logik

**Problem:** Jede Seite, die Sketch-Input wollte, musste die Toggle-Buttons, den `imageInputMode`-Ref, das CSS und die dynamische `inputType`-Zuweisung kopieren. Das verstößt gegen das Komponentenprinzip und führt bei 5+ Views mit Bild-Input zu massiver Duplikation.

**Decision:** `allowSketch: boolean` Prop auf MediaInputBox. Wenn `true` und `inputType === 'image'`, rendert MediaInputBox intern einen Upload/Sketch-Toggle und wechselt zwischen `ImageUploadWidget` und `SketchCanvas`. Der externe `inputType` bleibt `'image'` — Sketch ist ein interner Modus, keine eigene Eingabekategorie.

**Kunstpädagogische Begründung:** Skizzieren ist eine fundamental andere Denkbewegung als Bild-Upload. Upload = "Was habe ich?" (Material-orientiert). Sketch = "Was stelle ich mir vor?" (Imaginations-orientiert). Beide Eingabekanäle gleichberechtigt in jedem Bild-Input verfügbar zu machen, demokratisiert den Zugang zu img2img-Pipelines: Kinder ohne "passendes" Foto können dennoch visuelle Ideen formulieren. Die Gleichberechtigung auf Komponentenebene signalisiert, dass Skizzieren kein Workaround ist, sondern ein vollwertiger kreativer Akt.

**Alternatives verworfen:**
- ❌ Composable (`useSketchMode`): Unnötige Abstraktion — der State (`sketchMode`) hat keine Konsumenten außerhalb der Komponente. Composable wäre Overengineering.
- ❌ `inputType: 'sketch'` als externer Wert beibehalten: Erzwingt Page-Level-Logik für den Toggle. Die aufrufende Seite muss wissen, dass `'sketch'` existiert, den Mode managen und an MediaInputBox übergeben. Das widerspricht dem Prinzip "Pages use components, components manage their own state".
- ❌ Eigener `SketchInputBox`: Duplikation von MediaInputBox-Infrastruktur (Header, Loading, Actions).

**Betroffene Dateien:** `src/components/MediaInputBox.vue`, `src/views/image_transformation.vue`, `src/views/multi_image_transformation.vue`, `src/views/latent_lab/crossmodal_lab.vue`

---

## Ollama Removal — In-Process llama-cpp-python (2026-03-28)

> **Korrigiert am 2026-09-02** (siehe den Eintrag „Ein Kind je Modell" am Kopf dieser Datei): Die hier verworfene Alternative „separater llama-server Prozess" wurde mit „keine VRAM-Koordination" begruendet. Das gilt fuer einen fremden Daemon, nicht fuer Kindprozesse, die der GPU-Dienst selbst startet, per PID misst und beendet. Seit 2026-09-02 ist genau das der Default (`LLM_ENGINE=child`); der In-process-Motor bleibt waehlbar.


**Kontext:** Ollama 0.18.2 berechnet `default_num_ctx` aus TOTAL VRAM (95GB), nicht AVAILABLE. Auf der Blackwell RTX PRO 6000 allokierte es 28GB KV-Cache fuer ein 2B-Modell → 12 konsekutive OOM-Crashes. Fundamentales Architekturproblem — nicht konfigurierbar, nicht vorhersagbar.

### Decision 1: Ollama komplett ersetzen, nicht patchen

**Problem:** Ollama als Blackbox-Prozess hat keine VRAM-Koordination mit anderen Backends (Diffusers, HeartMuLa, ComfyUI). Es allokiert selbstaendig und konkurriert mit GPU Service um VRAM.

**Decision:** LLM-Inferenz direkt im GPU Service via llama-cpp-python (in-process). Alle GGUF-Modelle (Safety, DSGVO, VLM) laufen im selben Prozess wie Diffusers/HeartMuLa, koordiniert ueber den VRAM-Coordinator.

**Begruendung:** In-process eliminiert den zweiten GPU-Prozess, gibt volle Kontrolle ueber VRAM-Allokation und eliminiert HTTP-Overhead fuer Safety-Checks. llama-cpp-python unterstuetzt identische GGUF-Modelle.

**Alternatives verworfen:**
- ❌ Ollama OLLAMA_NUM_CTX manuell setzen: Fragil, muss pro Modell angepasst werden
- ❌ Separater llama-server Prozess: Gleiches Problem wie Ollama (zweiter GPU-Prozess, keine VRAM-Koordination)

### Decision 2: VLM Proxy eliminieren

**Problem:** `vlm_proxy_backend.py` war ein Wrapper, der Ollama's `/api/chat` mit VRAM-Koordination aufrief. Nach Migration zu llama-cpp-python ist der LLM-Backend bereits VRAM-koordiniert.

**Decision:** VLM Proxy komplett geloescht. Einziger Caller (`schema_pipeline_routes.py` VLM Safety Check) ruft direkt `/api/llm/chat` auf.

### Decision 3: BackendType.OLLAMA → LOCAL_LLM

**Problem:** Der Enum-Wert "ollama" war ein Markenname im Code (verstoesst gegen Code Architecture Rules).

**Decision:** `BackendType.LOCAL_LLM = "local_llm"` mit `_missing_()` fuer Abwaertskompatibilitaet serialisierter Daten. `local/` Routing-Prefix bleibt (war nie Ollama-spezifisch).

**Betroffene Dateien:** 60+ Dateien, siehe Commits `c53be3b` und `d7862e4`.

---

## 🔬 Surrealizer Fusion Strategy: Token-Level Extrapolation Redesign (2026-02-26)

**Kontext:** Code-Audit der originalen ComfyUI `ai4artsed_t5_clip_fusion` Node offenbarte, dass T5-Tokens >77 unverändert (1×) angehängt werden. Die Diffusers-Übersetzung replizierte dieses Verhalten exakt. Bei langen Prompts (~500 T5-Tokens) überwältigten 400+ unmodifizierte Tokens die 77 extrapolierten — weniger surreale Ergebnisse als bei kurzen Prompts.

### Decision 1: Drei Fusion-Strategien statt einer festen Formel

**Problem:** Die einzige Formel (LERP first 77, append rest unchanged) war ein Kompromiss, der bei kurzen Prompts funktionierte, bei langen aber die Surrealität verwässerte. Es gab keine Möglichkeit, das Verhalten zu steuern.

**Decision:** Drei wählbare Strategien mit `dual_alpha` als Default:
- **`dual_alpha`**: `α_core = α×0.15` auf Tokens 1–77 (sanfte Verzerrung, CLIP-L Strukturanker), `α_ext = α` auf Tokens 78+ (volle Extrapolation). Ziel: kontingente Ähnlichkeit.
- **`normalized`**: Uniform `α` auf alle Positionen (CLIP=0 jenseits 77 → Tokens 78+ = α×T5), dann L2-Normalisierung auf mittlere T5-Magnitude pro Token. Gleiche Richtung, kontrollierte Magnitude.
- **`legacy`**: Originalverhalten für Vergleichbarkeit.

**Begründung:** Die zwei neuen Strategien lösen unterschiedliche Probleme: `dual_alpha` optimiert für ästhetische Ergebnisse (Erkennbarkeit + Überraschung), `normalized` für mathematische Sauberkeit (gleiche Extrapolationsrichtung ohne Attention-Dominanz). Visueller A/B-Vergleich steht noch aus.

**Alternatives verworfen:**
- ❌ Einfache Invertierung (Tokens 1–77 unverändert, 78+ extrapoliert): Bei kurzen Prompts (<77 Tokens) gäbe es nichts zu extrapolieren.
- ❌ Nur `legacy` fixen (α auf alles anwenden): Verliert den Strukturanker komplett — keine kontingente Ähnlichkeit möglich.

**Betroffene Dateien:** `gpu_service/services/diffusers_backend.py`, `gpu_service/routes/diffusers_routes.py`, `devserver/my_app/services/diffusers_client.py`, `devserver/my_app/services/diffusers_backend.py`, `devserver/schemas/engine/backend_router.py`, `devserver/my_app/routes/schema_pipeline_routes.py`, `devserver/schemas/chunks/output_image_surrealizer_diffusers.json`

### Decision 2: Fusion Strategy als zentrales UI-Element, nicht Advanced Setting

**Problem:** Die Fusion-Strategie bestimmt fundamental, wie das Bild entsteht. Sie in "Advanced Settings" zu verstecken verbirgt die wichtigste kreative Entscheidung.

**Decision:** Button-Gruppe direkt unter dem α-Slider, visuell gleichwertig. Dynamische Beschreibung unter den Buttons wechselt mit der Auswahl. Info-Texte im Erklärungsbereich organisch umgeschrieben, um alle drei Strategien im Kontext der Mechanik zu erläutern — nicht als angehängter Absatz.

**Begründung:** Die Strategie ist keine technische Einstellung sondern eine ästhetische Grundentscheidung: "Will ich Strukturähnlichkeit mit Überraschung, gleichmäßige Verzerrung, oder das Originalverhalten?"

---

## 🧠 LLM Inference Migration: Ollama → GPU Service (2026-02-23)

**Kontext:** 3 Inference-Backends (Ollama/GGUF, GPU Service/safetensors, SwarmUI/ComfyUI) konkurrierten blind um den gleichen GPU-VRAM. Ollama und GPU Service wussten nichts voneinander — ein Safety-Modell via Ollama konnte eine Diffusers-Pipeline aus dem VRAM verdrängen, ohne dass der VRAMCoordinator es mitbekam.

### Decision 1: LLMInferenceBackend als separater VRAMBackend (nicht TextBackend erweitern)

**Problem:** TextBackend lädt Modelle mit `output_hidden_states=True, output_attentions=True` für Latent-Text-Lab-Introspektion. Das kostet signifikant mehr VRAM als reines Inferencing.

**Decision:** Separater `LLMInferenceBackend` — gleiche VRAMBackend-Architektur, aber ohne Introspektions-Flags.

**Begründung:**
- TextBackend = pädagogische Introspektion (Attention Maps, Embedding-Interpolation, Bias-Probing)
- LLMInferenceBackend = Produktions-Inference (Safety, DSGVO, Translation, Interception)
- Verschiedene Concerns: Introspection braucht hidden_states (VRAM-teuer), Inference nicht
- Beide registrieren sich beim VRAMCoordinator → gegenseitige Eviction funktioniert

### Decision 2: Ollama-Fallback per-Call, nicht per-Session

**Problem:** GPU Service kann neustarten (VRAM-Cleanup, Updates). Alle LLM-Aufrufe würden in dieser Zeit fehlschlagen.

**Decision:** `LLMClient` versucht GPU Service pro Aufruf, fällt auf `ConnectionError`/`Timeout` per-Call auf Ollama zurück.

**Begründung:**
- Zero-Downtime: GPU Service Neustart → Ollama übernimmt nahtlos
- Keine Konfigurationsänderung nötig (kein "switch to Ollama mode")
- LLM-Fehler (OOM, falsches Modell) werden NICHT auf Ollama umgeleitet — nur Connectivity-Fehler

### Decision 3: Model-Name-Mapping statt Doppelte Konfiguration

**Problem:** DevServer config.py referenziert Ollama-Modellnamen (`qwen3:1.7b`), GPU Service braucht HuggingFace-IDs (`Qwen/Qwen3-1.7B`).

**Decision:** `LLM_MODEL_MAP` in `gpu_service/config.py` — bekannte Ollama-Namen werden automatisch auf HF-IDs gemappt. Unbekannte Namen werden as-is versucht (könnten bereits HF-IDs sein).

**Begründung:**
- DevServer-Config bleibt unverändert (Ollama-Namensstil beibehalten)
- Kein Admin muss HF-IDs kennen
- Neue Modelle: einfach Eintrag in Map hinzufügen

**Affected Files:** 4 neue + 9 modifizierte Dateien, darunter `gpu_service/services/llm_inference_backend.py`, `gpu_service/routes/llm_inference_routes.py`, `devserver/my_app/services/llm_client.py` und `gpu_service/config.py` (`LLM_MODEL_MAP`)

---

## 🔬 Session Export: Device-ID statt User-ID als Filter (2026-02-21)

**Kontext:** Der "User"-Filter im Session Data Export (Forschungsdaten-Tab) war funktionslos — `user_id` ist fast immer "anonymous". Die Plattform hat aber ein Device-ID-System (Favorites/Browser-ID), das Sessions eindeutig einem Gerät zuordnet. `device_id` wird bereits in jeder `metadata.json` gespeichert (`pipeline_recorder.py`).

**Decision:** `user_id`-Filter komplett durch `device_id`-Filter ersetzen (Backend + Frontend).

**Begründung:**
- `user_id` = "anonymous" in 99%+ der Sessions → kein Filterwert
- `device_id` = pro Browser eindeutig → ermöglicht Gerät-basierte Analyse (z.B. "alle Sessions von iPad #1 im Kurs")
- Device-Dropdown zeigt nur Geräte im aktuellen Filter-Fokus (Datum/Config/Safety), da Backend unique values NACH Filterung sammelt

**Details:**
- Backend: Query-Param `user_id` → `device_id`, Filterung auf `metadata.get('device_id')`, Response `"devices"` statt `"users"`
- Frontend: Stats, Filter-Dropdown (gekürzt auf 8 Zeichen), Tabelle, Detail-Modal, PDF-Export
- Kein Breaking Change für bestehende `metadata.json` (Feld `device_id` war schon immer gespeichert)

**Affected Files:** `settings_routes.py`, `SessionExportView.vue`

---

## 🧠 LATENT TEXT LAB: Dekonstruktive LLM-Introspektion als GPU-Service-Proxy (2026-02-15)

**Kontext:** Die Plattform hatte dekonstruktive Tools für Bildmodelle (Attention Cartography, Feature Probing, Concept Algebra, Denoising Archaeology), aber keine Werkzeuge für Sprachmodelle. Lehrkräfte und Schüler konnten nicht beobachten, wie LLMs intern funktionieren — welche Biases kodiert sind, wie verschiedene Modelle dieselbe Information repräsentieren, oder wie sich gezielte Manipulationen auswirken.

### Decision 1: GPU-Service-Proxy statt In-Process-Execution

**Problem:** LLM-Modelle (LLaMA-8B, Mistral) benötigen 4-20GB VRAM und müssen mit dem VRAM-Koordinator interagieren, der im GPU Service läuft.

**Lösung:** DevServer → GPU Service HTTP-Proxy, identisch zum Muster bei Diffusers und HeartMuLa:
- `text_routes.py` (DevServer) = stateless proxy, jeder Endpoint ruft `TextClient._post()` auf
- `text_backend.py` (GPU Service) = alle Modelle, Tensoren, PyTorch-Hooks
- `text_client.py` (DevServer) = HTTP-Client mit Timeout-Handling

**Begründung:** DevServer ist der pädagogische Orchestrator, kein ML-Runtime. GPU-Inferenz gehört in den GPU Service — einheitlich für alle Modality (Bild, Musik, Text).

**Alternative verworfen:**
- ❌ LLM direkt im DevServer laden → VRAM-Koordination unmöglich, Prozessisolation verletzt

### Decision 2: Drei wissenschaftlich fundierte Tabs statt freier Exploration

**Problem:** Erste Prototypen boten generische Werkzeuge (Token Surgery, Embedding-Interpolation, Attention Maps). Das war technisch beeindruckend, aber pädagogisch undurchsichtig — Schüler wussten nicht, *was* sie damit untersuchen sollten.

**Lösung (wissenschaftliche Neufundierung):**

| Tab | Forschungsfrage | Paper |
|-----|----------------|-------|
| 1. Representation Engineering | "Kann man Konzept-Richtungen im Aktivierungsraum finden und Generation steuern?" | Zou 2023, Li 2024 |
| 2. Vergleichende Modell-Archäologie | "Wie repräsentieren verschiedene Modelle dieselbe Information?" | Belinkov 2022, Olsson 2022 |
| 3. Bias-Archäologie | "Welche systematischen Verzerrungen sind in den Gewichten kodiert?" | Zou 2023, Bricken 2023 |

Jeder Tab hat eine klare Forschungsfrage, ein definiertes Experiment-Protokoll, und vordefinierte Presets. Die früheren generischen Tools (Token Surgery, Interpolation, Attention Maps, Layer Analysis) bleiben als API-Endpoints erhalten, werden aber nicht mehr als eigenständige UI-Elemente exponiert.

**Begründung:**
- Geführte Forschung statt offene Exploration (Zielgruppe 13-17 Jahre)
- Preset-Experimente (Gender Bias, Sentiment, Domain) senken die Einstiegshürde
- Jeder Tab referenziert explizit die zugrundeliegende Forschung (Dropdown mit Paper-Referenzen)

### Decision 3: LLM-Interpretation statt Chat-Overlay

**Problem:** Bias-Archäologie zeigt rohe Generierungstexte (Baseline vs. Manipulation). Jugendliche sehen z.B. dass masculine-Suppression identisch zur Baseline ist, verstehen aber nicht *warum* (weil das Modell "they" als Default verwendet).

**Lösung:** Automatische LLM-Interpretation via `POST /api/text/interpret`:
- Reuse von `call_chat_helper()` (multi-provider LLM dispatch aus `chat_routes.py`)
- Pädagogischer System-Prompt (sachlich, 3-5 Sätze, Sprache der Eingabe)
- Direkt unter den Ergebnissen, ohne User-Interaktion (kein Chat-Overlay, kein Button)
- Fail-open: LLM-Fehler blockieren nie die Ergebnisanzeige

**Interpretation läuft auf DevServer, NICHT GPU Service:**
Die Interpretation nutzt das `CHAT_HELPER_MODEL` (z.B. Mistral Large via Ollama, Bedrock, OpenRouter) — das ist die pädagogische Schicht des DevServers. Der GPU Service bleibt für Tensor-Operationen reserviert.

**Alternativen verworfen:**
- ❌ Chat-Overlay (Träshy) → erfordert User-Interaktion, bricht den Experiment-Flow
- ❌ GPU-Service-seitige Interpretation → vermischt Tensor-Ops und Pädagogik
- ❌ Statische Erklärtexte → können nicht auf die tatsächlichen Ergebnisse eingehen

### Decision 4: Token-Resolution mit Varianten

**Problem:** BPE-Tokenizer kodieren `" he"` (mit Leerzeichen) und `"he"` (ohne) als verschiedene Token-IDs. Naive Token-Resolution (`tokenizer.encode("he")`) findet nur eine Variante → unvollständige Bias-Suppression.

**Lösung:** `_resolve_token_ids(tokenizer, words)` im GPU-Service resolvet für jedes Wort drei Varianten:
1. Bare: `"he"` → Token-ID 123
2. Space-prefixed: `" he"` → Token-ID 456
3. Capitalized: `"He"`, `" He"` → Token-IDs 789, 012

Alle gefundenen IDs werden gesammelt und für Boost/Suppress verwendet.

### Decision 5: Additive statt multiplikative Logit-Manipulation

**Problem (Bug des Prototyps):** Multiplikative Manipulation (`logits *= factor`) verursacht Softmax-Kollaps — ein Token mit hohem Logit dominiert komplett, die Verteilung wird zu einem Dirac-Delta.

**Lösung:** Additive Manipulation (`logits += factor`). Verschiebt die Logits gleichmäßig, ohne die relative Skalierung zu zerstören. Suppression bleibt `-inf` (komplett blockieren).

**Betroffene Dateien:**
- `gpu_service/services/text_backend.py` — Core: TextBackend, _resolve_token_ids(), _get_decoder_layers()
- `gpu_service/routes/text_routes.py` — REST endpoints (TEXT_ENABLED guard)
- `devserver/my_app/routes/text_routes.py` — DevServer proxy + /interpret endpoint
- `devserver/my_app/services/text_client.py` — HTTP client
- `public/ai4artsed-frontend/src/views/latent_lab/latent_text_lab.vue` — Vue component (3 tabs)
- `public/ai4artsed-frontend/src/i18n.ts` — DE+EN translations
- `docs/ARCHITECTURE PART 28 - Latent-Lab.md` — Architecture documentation

---

## 🔐 RESEARCH-LEVEL-GATING: Canvas & Latent Lab hinter Safety-Level-Gate (2026-02-11)

**Kontext:** Canvas und Latent Lab nutzen direkte Pipeline-Aufrufe ohne vollständige 4-Stage-Safety (Stage 2 wird übersprungen, Stage 1/3 sind optional). Statt Safety in jeden experimentellen Endpoint nachzurüsten, wird der Zugang gegated: Diese Features sind nur ab Safety-Level `adult` verfügbar.

**Entscheidungen:**

### Decision 1: Safety-Level `off` → `research` umbenennen

Das alte Label `off` suggerierte "Development only / kaputt" — tatsächlich ist es ein bewusster Research-Modus für Erwachsene (16+). Neuer Name `research` kommuniziert den Zweck klarer. Hierarchie: `kids` < `youth` < `adult` < `research`.

**Betroffene Dateien:** `config.py`, `schema_pipeline_routes.py`, `stage_orchestrator.py`, `workflow_logic_service.py`, `export_manager.py`, `workflow_streaming_routes.py` — insgesamt ~25 Stellen (Vergleiche, Docstrings, Default-Werte).

### Decision 2: Feature-Gating statt Endpoint-Sicherung

**Problem:** Canvas und Latent Lab operieren absichtlich ohne Stage-2-Interception und mit optionaler Safety. Vollständige Safety nachzurüsten würde den pädagogisch-dekonstruktiven Charakter zerstören (z.B. Partial Elimination benötigt unverfälschte Vektoren).

**Lösung:** Zugangs-Gating auf Frontend-Ebene:
- `kids`/`youth` → Cards sichtbar aber deaktiviert (Opacity 0.4, Schloss-Icon, kein Klick)
- `adult` → Normal klickbar (adult hat eigene §86a + DSGVO Safety-Stages)
- `research` → Compliance-Dialog pro Session, dann klickbar

**Transparenz-Prinzip:** Locked Cards werden angezeigt, nicht ausgeblendet — Nutzer sehen, dass es mehr gibt, und verstehen warum es gesperrt ist.

### Decision 3: Session-basierte Compliance-Bestätigung (nur `research`)

Bei Safety-Level `research` müssen Nutzer pro Browser-Session eine Compliance-Bestätigung abgeben (Warnung: keine Filter aktiv, Altersempfehlung 16+). Die Bestätigung ist ein `ref` (kein `localStorage`) — Reset bei Page-Reload.

**Begründung:** `adult`-Level hat noch §86a + DSGVO Safety-Stages aktiv, daher kein Compliance-Dialog nötig. Nur `research` (= komplett ungefiltert) erfordert bewusste Bestätigung.

### Decision 4: Öffentlicher Safety-Level-Endpoint

`GET /api/settings/safety-level` — ohne Auth, da der Safety-Level kein Geheimnis ist (er bestimmt nur, welche Features sichtbar sind, nicht welche Daten zugänglich sind). Frontend-Store (`safetyLevel.ts`) fetcht beim App-Start und cached im Pinia-Store.

**Alternativen verworfen:**
- ❌ Safety in Latent-Lab-Endpoints nachrüsten → zerstört wissenschaftlichen Charakter
- ❌ Features komplett ausblenden statt locken → Nutzer wissen nicht, was es gibt
- ❌ Compliance per localStorage → zu persistent, Session-Reset ist bewusste Entscheidung
- ❌ Compliance auch für `adult` → unnötig, adult hat eigene Safety-Stages

**Betroffene Dateien:**
- Backend: `config.py`, `settings_routes.py`, `schema_pipeline_routes.py`, `stage_orchestrator.py`, `workflow_logic_service.py`, `export_manager.py`, `workflow_streaming_routes.py`
- Frontend: `stores/safetyLevel.ts` (NEU), `components/ResearchComplianceDialog.vue` (NEU), `views/LandingView.vue`, `router/index.ts`, `main.ts`, `i18n.ts`

---

## 🧪 LATENT LAB: Dekonstruktive Configs zu einem Modus zusammengefasst (2026-02-11)

**Kontext:** Die Plattform hatte mehrere separate dekonstruktive Workflows:
- **Hallucinator** (ehemals Surrealizer) — CLIP-L/T5 Extrapolation
- **Split & Combine** — Semantische Vektorfusion zweier Prompts
- **Partial Elimination** — Dimensionselimination im Vektorraum
- **Attention Cartography** — Cross-Attention Visualisierung
- **Feature Probing** — Embedding-Dimensionsanalyse + selektiver Transfer

Diese waren teils als eigenständige Views (`/surrealizer`), teils als Legacy-ComfyUI-Workflows, teils gar nicht über die UI erreichbar. Es fehlte ein konzeptueller Rahmen.

**Entscheidung: Ein "Latent Lab" als Forschungsmodus**

Alle dekonstruktiven, vektorraumbasierten Operationen werden unter `/latent-lab` als Tab-basierter Modus zusammengefasst. Das Latent Lab ist kein produktives Generierungstool, sondern ein Forschungsinstrument für:
1. **Attention Cartography** — Welche Tokens beeinflussen welche Bildregionen?
2. **Feature Probing** — Welche Embedding-Dimensionen kodieren welche Semantik?
3. **Concept Algebra** — Vektorarithmetik im Embedding-Raum (planned)
4. **Encoder Fusion** — Encoder-übergreifende Interpolation (planned)
5. **Denoising Archaeology** — Schichtweise Denoising-Analyse (planned)

**Begründung:**
- Gemeinsamer konzeptueller Rahmen: "Was passiert im Inneren des Modells?"
- Gemeinsames Safety-Profil: Stage-2-Bypass, da Prompts unverfälscht bleiben müssen
- Gemeinsame Zielgruppe: Fortgeschrittene Nutzer (→ `adult`/`research` Safety-Level)
- Klare Abgrenzung von produktiven Modi (Text/Bild/Musik-Transformation)

**Diffusers als flexible Plattform:**

Die Migration von ComfyUI-Workflows zu Diffusers (begonnen mit dem Hallucinator) ermöglicht tiefere Modell-Introspektion. Diffusers bietet:
- Direkten Zugriff auf individuelle Text-Encoder (`pipe._get_clip_prompt_embeds()`, `pipe._get_t5_prompt_embeds()`)
- Hot-swappable Attention-Prozessoren (Custom `AttentionCaptureProcessor` statt SDPA)
- Tensor-Operationen ohne Workflow-Overhead (Embedding-Manipulation, Dimensionsanalyse)
- Programmierbare Pipeline-Schritte (Denoising-Loop Introspection)

ComfyUI ist node-graph-basiert — perfekt für "normales" Generieren, aber schlecht für Introspection, weil die internen Tensoren zwischen Nodes nicht sichtbar sind. Diffusers gibt programmatischen Zugriff auf alle Zwischenschritte.

**Hallucinator bleibt separat:** Der Hallucinator (`/surrealizer`) bleibt als eigenständige View bestehen — er ist das am meisten genutzte dekonstruktive Tool und hat einen eigenen kreativen Workflow (Alpha-Slider-Exploration). Integration ins Latent Lab ist für die Zukunft vorgesehen.

**Alternativen verworfen:**
- ❌ Jedes dekonstruktive Tool als eigene Top-Level-Route → zu viele Einträge in Navigation
- ❌ Alles in ComfyUI belassen → keine Tensor-Introspektion möglich
- ❌ Hallucinator sofort in Latent Lab integrieren → zu großer Umbau, eigenständiger Workflow

---

## 🏠 LANDING PAGE RESTRUCTURE: Feature-Dashboard + Kontextuelle Preset-Auswahl (2026-02-10)

**Kontext:** Die Plattform ist über ihren ursprünglichen Einstiegspunkt (`/select` = PropertyQuadrantsView) hinausgewachsen. Diese Seite zeigte Interception-Presets als Einstiegserlebnis — aber Canvas, HeartMuLa, Surrealizer und Latent Lab nutzen gar keine Interception-Presets. Zwei verschiedene Anliegen ("Welches Feature?" vs. "Welcher Interception-Stil?") waren auf einer Seite vermischt.

**Entscheidung:**
1. **Neue Landing Page** (`/`) als Feature-Dashboard mit 6 Karten (Text-Transformation, Bild-Transformation, Bildfusion, Musikgenerierung, Canvas Workflow, Latent Lab) — informiert über das Forschungsprojekt UND leitet zu den Features
2. **Preset-Auswahl wird kontextuell**: InterceptionPresetOverlay als Fullscreen-Bubble-Overlay, nur in den Views die es betrifft (text/image/multi-image transformation), ausgelöst durch Icon-Button in der Context-MediaInputBox
3. **`/select` komplett entfernt** — kein Redirect, einfach weg. Das Bubble-Visual lebt exklusiv im Overlay weiter
4. **Header-Reihenfolge** didaktisch: einfach→komplex (Text → Bild → Multi-Bild → Musik → Canvas → Latent Lab)

**Begründung:**
- Feature-Auswahl ≠ Preset-Auswahl — zwei verschiedene Entscheidungsebenen, die getrennt gehören
- Presets sind nur für Interception-Pipelines relevant (text_transformation, text_transformation_recursive) — andere Modi (Musik, Canvas, Latent Lab) haben eigene Konfigurationslogik
- Landing Page gibt Forschungskontext (BMBFSFJ-Förderung, pädagogischer Zweck) — wichtig für Workshop-Teilnehmer und externe Besucher
- Staggered Preview-Rotation (±800ms Jitter pro Karte) vermeidet uniformes Umschalten

**Alternativen verworfen:**
- ❌ `/select` als Redirect auf `/` behalten → unnötige Altlast
- ❌ Preset-Overlay global verfügbar → macht keinen Sinn in Musik/Canvas/Latent Lab
- ❌ Composable aus PropertyCanvas extrahieren → PropertyCanvas wird toter Code (kein Route mehr)

**Betroffene Dateien:**
- `src/views/LandingView.vue` (NEU)
- `src/components/InterceptionPresetOverlay.vue` (NEU)
- `src/components/MediaInputBox.vue` (showPresetButton Prop)
- `src/views/text_transformation.vue`, `image_transformation.vue`, `multi_image_transformation.vue` (Overlay-Verdrahtung)
- `src/App.vue` (Header-Icons: Reihenfolge, Latent Lab Mikroskop, LoRA Papagei)
- `src/router/index.ts` (Route-Änderungen)
- `src/i18n.ts` (landing + presetOverlay + multiImage Keys)

---

## 🔬 HALLUCINATOR: Diffusers Backend + Token-Level CLIP-L/T5 Extrapolation (2026-02-08)

**Status:** ✅ IMPLEMENTED

### Decision 1: Migrate from joint-embedding blending to individual-encoder token-level fusion

**The Hallucinator's surreal effect comes from extrapolating BETWEEN two different text encoder representations, not from blending joint SD3 embeddings.**

### Problem (vorher)

The Diffusers backend used `pipe.encode_prompt()` which returns **joint SD3 embeddings** — all three text encoders (CLIP-L + CLIP-G + T5) concatenated into one tensor `(1, 589, 4096)`. Blending two such tensors (one with CLIP active/T5 empty, one with CLIP empty/T5 active) had a destructive effect:

```
At α=20, CLIP region: -19 * CLIP(prompt) + 20 * CLIP("")
→ Pushes CLIP embeddings toward huge NEGATIVE values of the prompt
→ DESTROYS the signal instead of extrapolating between encoder spaces
→ α=10 already extreme, α=25 white/blank image
```

### Lösung (nachher)

Access individual text encoders via `pipe._get_clip_prompt_embeds()` and `pipe._get_t5_prompt_embeds()`, replicating the original ComfyUI `ai4artsed_t5_clip_fusion` node exactly:

1. CLIP-L encodes prompt independently → (1, 77, 768)
2. T5-XXL encodes prompt independently → (1, 512, 4096)
3. Pad CLIP-L to 4096d (zero-padded)
4. LERP first 77 tokens: `(1-α)·CLIP-L + α·T5` (extrapolation at α>1)
5. Append remaining T5 tokens (78-512) unchanged → semantic anchor
6. Same fusion for negative prompt, all 4 tensors bypass `encode_prompt()`

**At α=20:** `fused[0:77] = -19·CLIP-L + 20·T5` — pushes 19× past T5 into unexplored vector space. The model hallucinates because it must interpret out-of-distribution vectors.

### Decision 2: CLIP-L only — no CLIP-G anywhere in the fusion

The original ComfyUI workflow loads only `clip_l.safetensors` and `t5xxl_enconly.safetensors` — CLIP-G is absent from both embedding AND pooled output. We match this exactly:
- **Fused tokens:** CLIP-L (768d, zero-padded to 4096d) vs T5 (native 4096d)
- **Pooled output:** CLIP-L real (768d) + zeros (1280d) = 2048d — NO real CLIP-G pooled
- **Rationale:** Real CLIP-G pooled gives the DiT strong visual anchoring that fights extrapolation → incoherent results. The zeroed CLIP-G in pooled is essential for the surreal effect.

### Decision 3: Rename "Surrealizer" → "Hallucinator" (display name only)

The effect is technically **AI hallucination** (model interpreting vectors outside its training distribution), not stylistic surrealism. Renamed all user-facing text; internal IDs (`surrealizer`, file names, routes) kept unchanged to avoid breaking changes.

### Betroffene Dateien
- `devserver/my_app/services/diffusers_backend.py` — `generate_image_with_fusion()` rewritten
- `devserver/schemas/configs/interception/surrealizer.json` — description, context, name, tags
- `devserver/schemas/configs/output/surrealization_diffusers.json` — name, description
- `devserver/schemas/configs/output/surrealization_legacy.json` — name
- `devserver/schemas/chunks/output_image_surrealizer_diffusers.json` — description, alpha docs, notes
- `public/ai4artsed-frontend/src/i18n.ts` — DE+EN: new explanations, slider labels
- `public/ai4artsed-frontend/src/views/surrealizer.vue` — i18n'd slider labels, button text
- `public/ai4artsed-frontend/src/components/DokumentationModal.vue` — rewritten explanation
- `docs/ARCHITECTURE PART 22` — Diffusers backend section, technical analysis

---

## 🛡️ SAFETY: Post-Generation VLM Image Check + Safety-Architektur Klarstellung (2026-02-07)

**Status:** ✅ IMPLEMENTED

### Decision 1: Post-Generation VLM Safety Check

**Text-basierte Safety-Checks können nicht vorhersagen, was ein Bildgenerator tatsächlich erzeugt. Lösung: Das generierte Bild mit einem lokalen Vision-Language-Model (qwen3-vl:2b) analysieren, bevor es ans Frontend geht.**

### Problem (vorher)

Stage 1 und Stage 3 prüfen den **Prompt-Text** — aber ein harmloser Prompt ("visuell faszinierende Szene im Wald") kann ein verstörendes Bild produzieren. Es gab keine Prüfung des **tatsächlich generierten Bildes**.

### Lösung (nachher)

- `_vlm_safety_check_image()` in `schema_pipeline_routes.py` — direkte Ollama-Call nach Stage 4
- Liest Bild aus `recorder.get_entity_path('output_image')`, base64-encoded
- Empirisch getestete Prompts für kids (6-12) und youth (14-18)
- Nur für `media_type == 'image'` und `safety_level in ('kids', 'youth')`
- Fail-open bei Fehler (VLM-Ausfall blockt nicht)
- `VLM_SAFETY_MODEL = "qwen3-vl:2b"` in `config.py`

### Decision 2: Safety bedeutet verschiedenes an verschiedenen Stellen

Die Safety-Architektur hat **drei unabhängige Schutzebenen** mit unterschiedlichen Zielen:

| Schutzebene | Was wird geschützt | Wann aktiv | Wo |
|---|---|---|---|
| **§86a StGB** | Vor illegalen Inhalten (Nazi-Symbole, Terror) | IMMER (auch adult) | Stage 1 |
| **DSGVO** | Vor Verarbeitung persönlicher Daten | IMMER (auch adult) | Stage 1 (SpaCy NER) |
| **Jugendschutz** | Vor alters-unangemessenen Inhalten | kids/youth only | Stage 1 + 3 + VLM |

**Wichtig:** DSGVO-Safety ≠ Jugendschutz. §86a ist strafrechtlich, DSGVO ist datenschutzrechtlich, Jugendschutz ist pädagogisch. Alle drei koexistieren.

### Technische Erkenntnisse: qwen3-vl Thinking Mode

- qwen3-vl:2b nutzt standardmäßig Thinking Mode
- Antwort landet in `message.thinking`, nicht `message.content`
- `num_predict` muss hoch genug sein (500) für Thinking + Antwort
- Code prüft beide Felder (`content` und `thinking`)

### Betroffene Dateien
- `devserver/config.py` — `VLM_SAFETY_MODEL` Variable
- `devserver/my_app/routes/schema_pipeline_routes.py` — `_vlm_safety_check_image()` + Insertion in Streaming-Flow

### Offene Frage
- Video-Generierung: VLM-Check für Videos noch nicht implementiert (media_type != 'image' wird übersprungen)

---

## 📚 WIKIPEDIA: Opt-In per Config statt Opt-Out per Request (2026-02-06)

**Status:** ✅ IMPLEMENTED

### Decision

**Wikipedia-Research wird von opt-out (global aktiv, per Request abschaltbar) auf opt-in (per Config aktivierbar) umgestellt.**

### Problem (vorher)

Wikipedia-Instruktionen waren hardcoded in `manipulate.json` — jeder `manipulate`-Chunk-Call enthielt die gesamten Wikipedia-Anweisungen (70+ Sprachen, ~2KB Prompt-Text). Pipelines die kein Wikipedia brauchten (Musik, Code) mussten `skip_wikipedia: true` im Frontend-Request senden. Das war:
- Architektonisch fragwürdig (Feature wird zum Problem das man vermeiden muss)
- Fehleranfällig (vergessenes Flag → Wikipedia-Loop korrumpiert Output)
- Token-Verschwendung (Wikipedia-Instruktionen in jedem Prompt, auch bei Lyrics-Generierung)

### Lösung (nachher)

- Wikipedia-Instruktionen in eigenem Modul: `schemas/engine/wikipedia_prompt_helper.py`
- `manipulate.json` Template ist sauber: nur Task + Context + Prompt
- Config-level Steuerung: `"meta": {"wikipedia": true}` in Interception-Config JSONs
- `pipeline_executor._execute_single_step()` prüft Config-Flag, injiziert Instruktionen + Loop nur wenn aktiv
- `skip_wikipedia` komplett entfernt (Frontend + Backend)

### Betroffene Dateien
- `schemas/engine/wikipedia_prompt_helper.py` (NEU)
- `schemas/chunks/manipulate.json` (bereinigt)
- `schemas/engine/pipeline_executor.py` (opt-in Logik)
- 28 pädagogische Interception-Configs (`"wikipedia": true`)
- `schema_pipeline_routes.py` (skip_wikipedia entfernt)
- `music_generation.vue`, `music_generation_v2.vue` (skip_wikipedia entfernt)

### Prinzip
Wikipedia-Research ist ein pädagogisches Feature der `text_transformation.vue` für Kunst/Kultur-Configs. Es gehört nicht in den generischen `manipulate`-Chunk.

---

## 🎵 MUSIC-GENERATION: Unified Simple/Advanced Mode (2026-02-06)

**Status:** ✅ IMPLEMENTED

### Decision

**Beide Music-Generation-UIs (V1 + V2) bleiben erhalten und werden über einen Simple/Advanced Toggle auf einer gemeinsamen Seite angeboten.**

### Reasoning

**Pädagogische Analyse der beiden Ansätze:**

| Aspekt | V1 (Simple) | V2 (Advanced) |
|--------|-------------|---------------|
| Einstiegshürde | Niedrig | Mittel |
| Lerneffekt Musik | Keiner | Hoch (8 Dimensionen) |
| Scaffold ohne Lyrics | Keines | "Theme → Lyrics" |
| Tag-Wissen nötig | Ja (Freitext) | Nein (Chips) |
| ML-Parameter | Keine | Temp/TopK/CFG |

**Lösung: Benutzer wählt selbst**
- **Simple Mode** = V1: Schneller Einstieg, keine Erklärung nötig
- **Advanced Mode** = V2: Musikalisches Lernen, mehr Kontrolle

**Default-Presets für V2:**
- Audio Length: 3:20 (200s) — typische Songlänge
- Temperature: 1.0 — balancierte Kreativität
- Top-K: 65 — etwas fokussierter als 70
- CFG Scale: 2.75 — Mitte von 2.5-3.0 sweet spot

### Implementation

- `music_generation_unified.vue` als Wrapper
- Toggle persistiert in localStorage
- `/music-generation` → unified, `/music-generation-simple` + `/music-generation-advanced` für direkten Zugriff
- Custom Tags in MusicTagSelector für Power-User

---

## 🧠 LLM-STRATEGIE: Wechsel zu Mistral für VRAM-Optimierung (2026-01-29)

**Status:** ✅ DECIDED - Implementation pending

### Decision

**Strategische Entscheidung: Lokales LLM (gpt-OSS:120b) durch externes Mistral ersetzen, um VRAM für Bild-/Video-Modelle freizugeben.**

1. **Alle Meta-Prompts für Mistral optimieren**
   - Interception-Prompts, Safety-Checks, Translations
   - Ziel: Gleiche oder bessere Ergebnisse wie mit gpt-OSS:120b

2. **VRAM-Budget für ComfyUI maximieren**
   - Aktuell: 96GB - 65GB (LLM) = 31GB für Bild/Video
   - Zukünftig: 96GB - ~0GB (externes LLM) = 96GB für Bild/Video
   - Ermöglicht: Mehrere Modelle gleichzeitig geladen (wan22 + sd35 + flux + audio)

3. **Zentralen VRAM-Manager implementieren**
   - Ersetzt dezentrale `keep_alive` Settings
   - Koordiniert ComfyUI-Modell-Loading
   - Verhindert VRAM-Thrashing im Workshop-Betrieb

### Reasoning

**Problem-Analyse (Workshop 29.1.2026):**

| Szenario | Problem |
|----------|---------|
| Kleine LLMs (20b) | Qualität zu schlecht für Interception |
| Große LLMs (120b) | Funktioniert gut für Einzelsessions |
| Workshop (120b) | VRAM-Stau: 65GB LLM + wechselnde Bild-Modelle = Thrashing |
| Einzelsession (120b) | Kreativ-Flow behindert: Modellwechsel dauert sehr lange → User vermeidet ihn intuitiv |

**DSGVO-Analyse externer LLM-Anbieter:**

| Anbieter | DSGVO-Status | Verfügbarkeit |
|----------|--------------|---------------|
| OpenAI | ❌ US-Server | Nicht nutzbar |
| Anthropic | ❌ US-Server | Nicht nutzbar |
| Google | ⚠️ Kompliziert | Nicht praktikabel |
| AWS Bedrock EU | ✅ EU-Server | Nur Enterprise-Verträge |
| **Mistral** | ✅ EU (Frankreich) | **Token-basiert für Kleinabnehmer** |

**Einzige DSGVO-konforme Option für Kleinabnehmer: Mistral**

**Qualitätseinschätzung:**
- gpt-OSS:120b: Sehr gute Ergebnisse für Interception
- Mistral Large: Nach bisherigen Tests etwas schwächer
- **Konsequenz:** Meta-Prompts müssen für Mistral optimiert werden

### Architektur-Implikation

**Dezentrales VRAM-Problem (Ist-Zustand):**
```
manipulate.json:          keep_alive: "10m"
safety_check_*.json:      keep_alive: "10m"
prompt_interception.py:   keep_alive: 0  (aktives Entladen!)
image_analysis.py:        keep_alive: "0s"
→ Keine Koordination zwischen Ollama und ComfyUI
→ VRAM-Thrashing bei parallelen Requests
```

**Zentraler VRAM-Manager (Soll-Zustand):**
```
VRAMManager:
  - Trackt verfügbares VRAM (96GB)
  - Reserviert Budget für ComfyUI-Modelle
  - Entscheidet welche Modelle geladen bleiben
  - Kein Ollama mehr → volle 96GB für ComfyUI
```

### Betroffene Dateien (Implementation)

**Phase 1: Mistral-Migration**
- `devserver/config.py` - Model-Konstanten auf Mistral
- `devserver/schemas/chunks/*.json` - Alle LLM-Chunks
- `devserver/schemas/engine/instruction_selector.py` - Meta-Prompts
- `devserver/schemas/engine/prompt_interception_engine.py` - Entfernen von keep_alive=0

**Phase 2: VRAM-Manager**
- `devserver/my_app/services/vram_manager.py` - NEU
- `devserver/my_app/services/comfyui_service.py` - Integration
- `devserver/schemas/engine/backend_router.py` - Integration

### Offene Fragen

1. Mistral-API-Key-Management (*.key Datei)
2. Fallback-Strategie wenn Mistral nicht erreichbar
3. Kosten-Monitoring für Token-Verbrauch
4. Prompt-Optimierung: Wie viel Aufwand für Mistral-Anpassung?

---

## 🔀 MODEL-ROUTING: Prefix-basierte Provider-Auswahl (2026-01-29)

**Status:** ✅ DECIDED & IMPLEMENTED
**Ergänzt 2026-09-12:** die Adressierung über das Präfix bleibt; die Canvas-Liste ist seit diesem Tag die Chat-Modellliste (ein Modell, ein Weg), `CURATED_TOP_MODELS` gibt es nicht mehr, und die Einstellungsseite zeigt das Präfix nicht mehr (Eintrag vom 2026-09-12).

### Decision

**Prefix-basierte Model-Routing bleibt erhalten für maximale Flexibilität.**

Das Model-Prefix bestimmt explizit den Provider:
- `local/model-name` → Ollama (lokales LLM)
- `openrouter/provider/model` → OpenRouter API
- `anthropic/model` → Anthropic API direkt
- `mistral/model` → Mistral API direkt
- `bedrock/model` → AWS Bedrock

### Reasoning

1. **Canvas braucht explizite Auswahl:** User wählt gezielt Provider + Model
2. **Flexibilität:** Gleiche Models über verschiedene Provider verfügbar
3. **Transparenz:** Prefix macht den API-Endpunkt sichtbar
4. **Fallback-fähig:** Prefix kann zu OpenRouter führen wenn direkter Provider nicht verfügbar

### Implementation

Canvas zeigt für Anthropic-Models beide Optionen:
- "Claude Opus 4.5 (OpenRouter)" → `openrouter/anthropic/claude-opus-4.5`
- "Claude Opus 4.5 (Anthropic)" → `anthropic/claude-opus-4.5`

### Affected Files

- `devserver/schemas/engine/prompt_interception_engine.py:146-175` - Routing-Logik
- `devserver/my_app/routes/canvas_routes.py:32-43` - CURATED_TOP_MODELS Liste (bis 2026-09-12)

---

## 📡 SSE-STREAMING: Real-Time Stage Progress für Generation (2026-01-30)

**Status:** ✅ DECIDED & IMPLEMENTED

### Decision

**SSE (Server-Sent Events) für den `/generation` Endpoint, um Badges zum richtigen Zeitpunkt anzuzeigen.**

Statt:
- ❌ Fake 300ms Delay für Safety Badge
- ❌ Badges erst nach kompletter Generation

Jetzt:
- ✅ `stage3_complete` Event → Badges sofort anzeigen
- ✅ `stage4_start` Event → Progress-Animation starten
- ✅ Echte Stage-Trennung im UI sichtbar

### Reasoning

**Problem:**
- "Translated" Badge erschien erst NACH der Bildgenerierung
- Safety Badge verwendete künstlichen 300ms Delay - nicht akkurat
- User hatte keine Ahnung was gerade passiert (Translation? Safety? Generation?)

**Warum SSE statt Split-Requests:**

| Ansatz | Pro | Contra |
|--------|-----|--------|
| **Split (Stage 3 → Stage 4)** | Einfach zu implementieren | Race Conditions, State-Sync |
| **SSE Streaming** | Single Connection, failsafe | Etwas komplexer |

SSE gewählt weil:
1. **Failsafe:** Wenn Connection abbricht, stoppt alles sauber
2. **Kein Race:** Keine zwei Requests die synchronisiert werden müssen
3. **Bestehendes Pattern:** `/interception` nutzt bereits SSE

**Warum "→ EN" statt Flag-Icon:**
- 🇬🇧 (Britische Flagge) war problematisch: Kolonialismus, UK-Zentrismus
- "→ EN" ist neutral, klar, ohne politische Konnotation

### Architecture Impact

**Stage-Separation jetzt sauber:**

| Stage | Funktion | Endpoint | SSE Event |
|-------|----------|----------|-----------|
| Stage 1 | Safety (§86a) | `/interception` | `stage_complete (1)` |
| Stage 2 | Interception | `/interception` | `stage_complete (2)` |
| Stage 3 | Translation + Safety | `/generation` | `stage3_complete` |
| Stage 4 | Generation | `/generation` | `stage4_complete` |

**Backend-Funktionen klar getrennt:**
- `execute_stage1_gpt_oss_unified()`
- `execute_pipeline()` (Stage 2)
- `execute_stage3_safety()`
- `execute_stage4_generation_only()`

### Implementation

**Backend (`schema_pipeline_routes.py`):**
- `execute_generation_streaming()` Generator-Funktion
- Events: `connected`, `stage3_start`, `stage3_complete`, `stage4_start`, `complete`, `blocked`, `error`

**Frontend:**
- Neuer Composable: `useGenerationStream.ts`
- Shared zwischen 3 Views: text_, image_, multi_image_transformation

### Affected Files

| File | Change |
|------|--------|
| `devserver/my_app/routes/schema_pipeline_routes.py` | SSE-Modus für /generation |
| `public/.../composables/useGenerationStream.ts` | NEU - Shared SSE Composable |
| `public/.../views/text_transformation.vue` | Composable eingebunden |
| `public/.../views/image_transformation.vue` | Composable eingebunden |
| `public/.../views/multi_image_transformation.vue` | Composable eingebunden |

---

## 🌍 ANTI-ORIENTALISM & EPISTEMIC JUSTICE: Cultural-Aware AI (2026-01-26)

**Status:** ✅ DECIDED & IMPLEMENTED

### Decision

**Two-part solution to prevent orientalist stereotypes in prompt interception:**

1. **Enhanced Meta-Prompt with Anti-Orientalism Rules**
   - Added CULTURAL RESPECT PRINCIPLES to `instruction_selector.py`
   - Explicit FORBIDDEN list: exoticizing, romanticizing, mystifying cultural practices
   - Equality principle: "Use the same neutral, fact-based approach as for Western contexts"
   - Applies universally to ALL interception configs

2. **Wikipedia Lookup in Cultural Reference Language**
   - LLM must use Wikipedia in the CULTURAL REFERENCE LANGUAGE, not prompt language
   - 70+ languages mapped: Africa (15+), Asia (30+), Americas (indigenous), Oceania
   - Example: German prompt about Nigeria → uses Hausa/Yoruba/Igbo Wikipedia (not German)
   - Example: German prompt about Peru → uses Quechua/Aymara Wikipedia (not German)

### Reasoning

**Problem Identified:**
GPT-OSS:120b produced exoticizing, orientalist kitsch when processing a prompt about a Nigerian cultural festival. LLMs defaulted to orientalist tropes (exotic, mysterious, timeless) even with factual data available.

**Root Cause:**
- LLMs trained on Western-centric corpora default to orientalist framing
- Wikipedia lookup alone insufficient - models need explicit anti-stereotype rules
- Using German/European Wikipedia for non-European topics perpetuates colonial knowledge hierarchies

**Why Epistemic Justice Matters:**
- **Linguistic Sovereignty:** Cultures have the right to be represented in their own languages
- **Local Knowledge:** Local-language Wikipedias written BY local communities FOR local contexts
- **Decolonizing AI:** Breaks colonial pattern of European languages as "universal" knowledge sources
- **Pedagogical Integrity:** AI4ArtsEd makes transformation choices visible and criticalizable - orientalist output undermines this goal

**Theoretical Foundation:**
Based on postcolonial theory (Said, Fanon, Spivak):
- Edward Said: "Orientalism" as Western construction of exotic Other
- Frantz Fanon: Dehumanization through exoticization
- Gayatri Chakravorty Spivak: Epistemic violence of representation

### Implementation

**Files Modified:**
- `devserver/schemas/engine/instruction_selector.py` - Anti-orientalism meta-prompt
- `devserver/schemas/chunks/manipulate.json` - Wikipedia cultural reference language mapping

**Testing:**
- ✅ Original failing case: "Das wichtigste Fest im Norden Nigerias"
- ✅ Result: Factual, respectful narrative WITHOUT orientalist tropes
- ✅ Improvement: from exoticizing kitsch to culturally grounded output

### Impact

**Cultural Coverage (70+ Languages):**
- **Nigeria:** ha (Hausa), yo (Yoruba), ig (Igbo), en
- **India:** hi, ta, bn, te, mr, gu, kn, ml, pa, ur (10+ regional languages!)
- **China:** zh, zh-yue (Cantonese)
- **Latin America:** es, pt, qu (Quechua), ay (Aymara), nah (Nahuatl)
- **Indigenous North America:** ik (Inuktitut), chr (Cherokee)
- **Oceania:** mi (Māori), to (Tongan), sm (Samoan), fj (Fijian)
- **Africa:** sw (Swahili), am (Amharic), zu (Zulu), xh (Xhosa), ar, ber

**Pedagogical Significance:**
This is not just a technical fix - it's a fundamental ethical stance. AI4ArtsEd systematically respects cultural diversity and actively resists colonial knowledge patterns. The system now embodies **epistemic justice** as a core architectural principle.

**Related Decisions:**
- See "planetarizer.json" and "one_world.json" configs (already had specific anti-Othering rules)
- This decision extends those principles universally across ALL interception configs

---

## 🎯 CANVAS EVALUATION NODES: Unified 3-Output Architecture (2026-01-25)

**Status:** ✅ DECIDED & IMPLEMENTED
**Full Details:** See `docs/ARCHITECTURE_CANVAS_EVALUATION_NODES.md`

### Decision

**ONE unified Evaluation node** with 3 separate TEXT outputs, instead of 7 separate node types (5 evaluation + 2 fork).

### Reasoning

**Problem with Original Plan (7 Nodes):**
- Evaluation and Fork were conceptually ONE decision, split into TWO nodes
- Unclear data flow: What text flows through fork? Input? Commentary? Both?
- UI complexity: 7 new nodes for one logical operation
- Pedagogically unclear: "Fairness Check" + "Binary Fork" = 2 steps for 1 decision

**Why 3 Text Outputs?**
1. **Passthrough (P)**: Original input unchanged (active if binary=true)
   - Use: Evaluation passed → continue workflow
2. **Commented (C)**: Input + "\n\nFEEDBACK: {commentary}" (active if binary=false)
   - Use: Evaluation failed → loop back to Interception with feedback
3. **Commentary (→)**: Just the commentary text (ALWAYS active)
   - Use: Display/Collector for user transparency

**Pedagogical Advantage:**
- Explicit decision points in workflow
- Visible feedback (not "black box")
- Enables iterative improvement (feedback loops)
- One node = one conceptual decision

### Technical Implementation

**Frontend Structure:**
```typescript
// Node properties
evaluationType: 'fairness' | 'creativity' | 'equity' | 'quality' | 'custom'
evaluationPrompt: string
outputType: 'commentary' | 'score' | 'all'
enableBranching: boolean
branchCondition: 'binary' | 'threshold'
thresholdValue: number
trueLabel: string
falseLabel: string
```

**Backend Structure:**
```python
# Evaluation result
{
  'type': 'evaluation',
  'outputs': {
    'passthrough': input_text,  # Original
    'commented': f"{input_text}\n\nFEEDBACK: {commentary}",  # Input + feedback
    'commentary': commentary  # Just commentary
  },
  'metadata': {
    'binary': True/False,
    'score': 0-10,
    'active_path': 'passthrough' | 'commented'
  }
}
```

**Binary Logic:**
- LLM prompt explicitly requests: "Answer ONLY 'true' or 'false'"
- Fallback: No binary → use score (< 5.0 = fail)
- Default if no score: False (safer, triggers feedback)

### Affected Files

- `public/.../types/canvas.ts` - Unified evaluation type
- `public/.../StageModule.vue` - 3-output UI, evaluation config
- `public/.../ModulePalette.vue` - 7 nodes → 1 node
- `devserver/.../canvas_routes.py` - 3 text outputs, binary logic

### Trade-offs

**Chosen:**
- Unified node with dropdown (1 node type)
- 3 separate text outputs
- Binary + Commentary always generated

**Rejected:**
- 7 separate node types (too complex)
- 2 outputs only (loses transparency)
- Combined object output (text doesn't flow properly)
- Default binary=true (unsafe, hides problems)

### Next Steps (Phase 3b - Not Yet Implemented)

**Conditional Execution:**
- Currently: All 3 outputs execute connected nodes
- Goal: Only active path (P or C) executes downstream
- Commentary path always executes (for display/collector)
- Requires: Connection label tracking, active path marking

---

## 🔄 CANVAS EXECUTION: Tracer-Pattern vs. Kahn's Algorithm (2026-01-26)

**Status:** ✅ DECIDED & IMPLEMENTED

### Decision

Use **simple Tracer-Pattern** (recursive graph traversal) instead of **Kahn's Algorithm** (topological sorting) for Canvas workflow execution.

### Context: The Loop Problem

**Original Plan (rejected):**
- Kahn's Algorithm for topological sorting
- Separate "Loop Controller" Node type
- Complex re-queueing mechanism for feedback loops

**Problem:** Kahn's Algorithm is designed for DAGs (Directed Acyclic Graphs) and rejects cycles by design. Feedback loops (Evaluation → Interception) create intentional cycles.

### Critique of the Original Plan

The attempted workaround for Kahn's cycle condition was a pseudo-solution. The graph holds no uncontrolled loop situation; it holds a loop-end constellation. The Loop Controller approach was over-engineered. The system needs no general cycle handling, only controlled feedback loops.

### Implemented Solution: Tracer-Pattern

```python
def trace(node_id, input_data, data_type):
    # 1. Execute current node
    output_data, output_type, metadata = execute_node(node, input_data, data_type)

    # 2. At Evaluation: filter connections based on score
    if node_type == 'evaluation' and metadata:
        active_path = metadata['active_path']  # 'passthrough' or 'commented'
        # Only follow connections whose label matches active_path

    # 3. For each active connection: recursive trace()
    for conn in active_connections:
        trace(conn['target'], output_data, output_type)
```

**Safety:** `MAX_TOTAL_EXECUTIONS = 50` prevents infinite loops.

### Why This Works

The Canvas system is NOT a general graph executor, but a **pedagogical workflow**:
- Input is always the start
- Collector is always the end
- Between: directed flow with controlled loops
- The loop-end constellation is intended behaviour

### Result: Reflexively Acting Frontend

A **world-unique reflexively acting frontend for genAI**:

```
Input → Interception → Evaluation → [Score < 5?]
                            ↓ feedback     ↓ pass
                       Interception    Generation → Collector
```

The system can:
1. Evaluate outputs (Evaluation node with LLM)
2. Provide feedback on failure (Commented output)
3. Send feedback back to Interception (Feedback connection)
4. Iterate until Score >= 5

### Affected Files

- `devserver/my_app/routes/canvas_routes.py` - Complete rewrite: `trace()` function replaces Kahn's algorithm
- `public/.../types/canvas.ts` - `maxFeedbackIterations` property
- `public/.../StageModule.vue` - Feedback-Input connector for Interception/Translation

### Trade-offs

**Chosen:**
- Simple recursive traversal
- Safety limit (50 executions)
- Feedback connections with explicit label

**Rejected:**
- Kahn's Algorithm (rejects cycles)
- Loop Controller node (over-engineered)
- Modified Kahn's with loop-edge exclusion (still complex)

---

## 🤖 LLM SELECTION: Model-Specific Prompting Strategy (2026-01-23)

**Status:** ✅ DECIDED

### Decision

Use **llama4:scout** as primary local model with **model-specific prompt variants** for CLIP optimization.

### Context: SD3.5 Triple CLIP Optimization

The prompt optimization task requires:
- Multilingual I/O (German, Bulgarian, Yoruba, etc.)
- Scene-to-2D transformation (narrative → frozen visual frame)
- Domain knowledge (photography, visual arts)
- Cultural neutrality (no artist names, no art-historical terms)
- Complex instruction following

### Model Evaluation Results

| Model | Multilingual | Low-Resource (Yoruba) | Recommendation |
|-------|--------------|----------------------|----------------|
| **llama4:scout** | 200 languages | ✅ 10x more data | ✅ Primary |
| Mistral Large 3 | 40+ languages | ⚠️ No data | EU-languages only |
| gpt-OSS:120b | Good | ⚠️ No data | Fallback |
| Qwen3-next | 119 languages | ❌ "unoptimized" | Not recommended |

### Key Finding: Prompt Format Sensitivity

Different models need different prompt styles:

| Model Family | Preferred Style |
|--------------|-----------------|
| Claude/OpenAI | Structured `===` sections, detailed rules |
| Llama 4 | Flat, example-heavy, short rules |
| Mistral | Minimal, precise, no nesting |

### Implementation

1. **Primary model:** llama4:scout (67GB, fits in 96GB VRAM)
2. **Prompt variants:** `default`, `llama`, `mistral` for each optimization chunk
3. **Dynamic selection:** Based on configured model name

### Affected Files

- `devserver/schemas/chunks/optimize_clip_prompt.json` (+ variants)
- `devserver/schemas/chunks/optimize_t5_prompt.json` (+ variants)
- `devserver/schemas/chunks/output_image_sd35_large.json`
- `devserver/config.py`

---

## 🏛️ ARCHITECTURAL PARADIGM: Werkraum → Lab Transition (2026-01-16)

**Status:** ✅ DOCUMENTED (ongoing evolution)
**Context:** Historical transition from workflow-centric to frontend-centric architecture

### The Two Paradigms

| Aspect | Werkraum (Workflow) | Lab (OO/Dezentriert) |
|--------|---------------------|----------------------|
| **Orchestrator** | Server | Frontend/User |
| **Data Flow** | Linear, predetermined | Flexible, user-controlled |
| **Server Role** | "Smart Orchestrator" | "Service Provider" |
| **Client Role** | "Dumb Display" | "Intelligent Composer" |
| **Endpoints** | Unified (server decides stages) | Atomic (client composes services) |

### Historical Context

**Werkraum Era (ComfyUI Workflows):**
- Unidirectional pipeline: Input → Stage 1 → Stage 2 → Stage 3 → Stage 4 → Output
- Server controlled the entire flow
- Frontend was a simple display layer
- Endpoint: `/api/schema/pipeline/execute` handled everything

**Lab Era (Current):**
- Flexible interaction: User can edit any text at any point
- Parallel LLM runs possible
- Every output is editable input for next step
- Frontend orchestrates which services to call

### Architectural Implication: Atomic Backend Services

In the Lab paradigm, the backend provides **atomic services** that the frontend composes:

| Endpoint | Stage | Purpose | Safety |
|----------|-------|---------|--------|
| `/api/schema/pipeline/interception` | 1+2 | User input → Interception | Auto (Stage 1) |
| `/api/schema/pipeline/optimize` | 3a | Model-specific format (clip_g tokens) | No |
| `/api/schema/pipeline/translate` | 3b | German → English translation | No |
| `/api/schema/pipeline/safety` | - | Reusable safety check (for custom flows) | - |
| `/api/schema/pipeline/generation` | 3c+4 | Pre-output safety + Media generation | Auto (Stage 3) |
| `/api/schema/pipeline/direct` | 1+4 | Direct run, prompt unchanged (bis 2026-08-24 `/pipeline/legacy`, als Alias bis 2026-10-10) | Auto (Stage 1) |

**Key Principles:**
1. **Safety is Server responsibility** - Endpoints with user-facing input auto-run safety
   - `/interception` → Stage 1 (Input Safety)
   - `/generation` → Stage 3 (Pre-Output Safety)
   - `/legacy` → Stage 1 (Input Safety)
2. **Atomic services** - Frontend composes the flow, backend executes steps
3. **No skip flags** - Instead of `skip_stage2: true`, just use `/legacy` endpoint

### Example Flows

**text_transformation.vue (Standard Flow):**
```
User Input → /interception (Stage 1+2) → User selects model
           → /optimize + /translate (parallel) → /generation (Stage 4)
```

**surrealizer.vue (Legacy Flow):**
```
User Input → /legacy (Stage 1 + ComfyUI workflow)
```

### Historical Context: Optimization Fix (2026-01-16)

**Bug:** Stage 3 optimization streaming called `/execute`, which always ran Stage 1—redundant.

**Wrong Fix (Werkraum thinking):** Add `skip_stage1` parameter.

**Correct Fix (Lab thinking):** Create `/optimize` endpoint that by design has no Stage 1.

### Coexistence Strategy

Both paradigms coexist in the current codebase:

- **Werkraum patterns** remain for backward compatibility and simpler flows
- **Lab patterns** enable advanced interactive features
- **Migration path:** Gradually decompose unified endpoints into atomic services as needed

### Files Affected

- `schema_pipeline_routes.py`: Both `/execute` (Werkraum) and `/optimize` (Lab) endpoints
- `text_transformation.vue`: Uses Lab pattern (calls atomic services)
- `surrealizer.vue`: Uses Werkraum pattern (single unified call)

---

## 🎯 Active Decision: Unified Export - run_id Across Lab Endpoints (2026-01-17)

**Status:** ✅ IMPLEMENTED
**Context:** Export function was broken - entities split across multiple folders
**Commit:** `7f07197` - `fix(export): Unified run_id and fix image saving for all backends`

### The Problem

In the Lab architecture, `/interception` and `/generation` are **atomic endpoints** called by the frontend. Each endpoint was generating its own `run_id`, resulting in:

- `/interception` → `run_1234_abc/` (input, safety, interception)
- `/generation` → `run_5678_xyz/` (output_image)

**Result:** Export function BROKEN - entities scattered across folders.

### The Solution

**Frontend passes run_id from /interception to /generation:**

```
Frontend (text_transformation.vue)
├── POST /interception → receives run_id in response
├── Stores run_id (currentRunId ref)
└── POST /generation { run_id: currentRunId } → uses SAME folder
```

**Backend changes:**
1. `/interception` initializes Recorder, saves input/safety/interception, returns `run_id`
2. `/generation` accepts optional `run_id`, loads existing Recorder via `load_recorder()`
3. All output entities saved to SAME run folder

### Additional Fix: Multi-Backend Image Saving

**Bug:** Only SD3.5 (`swarmui_generated`) saved images. QWEN, FLUX2, Gemini, GPT-Image failed.

**Root Cause:** Different backends return different output formats:
- `swarmui_generated`: Binary data via SwarmUI API
- `workflow_generated`: `filesystem_path` (QWEN, FLUX2)
- URL outputs: HTTP URLs (Gemini via OpenRouter)
- Base64 outputs: Inline base64 data (OpenAI)

**Fix in `/generation` endpoint:**
```python
elif output_value == 'workflow_generated':
    # Check filesystem_path first (QWEN, FLUX2)
    filesystem_path = output_result.metadata.get('filesystem_path')
    if filesystem_path and os.path.exists(filesystem_path):
        with open(filesystem_path, 'rb') as f:
            file_data = f.read()
        recorder.save_entity(...)
    elif media_files:  # Fallback: Legacy binary data
        ...

# Base64 handling for OpenAI-style outputs
elif output_value and len(output_value) > 100:
    file_data = base64.b64decode(output_value)
    recorder.save_entity(...)
```

### Architectural Note: media_type Consistency ✅ RESOLVED

**Finding:** The distinction between `media_type: "image"` and `media_type: "image_workflow"` is **ontologically unjustified**.

- SD3.5, QWEN, FLUX2 are ALL image models
- The only valid distinction: image vs video vs audio
- Internal workflow differences should be transparent

**Resolved (2026-01-17):** Eliminated `image_workflow` type - all image models now use `media_type: "image"`.
- Changed `output_image_qwen.json` and `output_image_flux2.json`
- Simplified `backend_router.py` line 749

### Files Modified

| File | Change |
|------|--------|
| `schema_pipeline_routes.py` | Added `load_recorder` import, recorder init in `/interception`, run_id acceptance in `/generation`, filesystem_path + base64 handling |
| `text_transformation.vue` | Added `currentRunId` ref, pass run_id to /generation |

### Test Results

- ✅ SD3.5: Works (unchanged)
- ✅ QWEN: Images saved from `filesystem_path`
- ✅ FLUX2: Images saved from `filesystem_path`
- ✅ Gemini 3 Pro: Images saved from base64
- ✅ GPT-Image: Images saved from base64/URL
- ✅ All entities in ONE unified folder

---

## 🎯 Active Decision: 1 Run = 1 Media Output (2026-01-23)

**Status:** ✅ IMPLEMENTED
**Context:** Multiple generations were writing to the same folder, confusing favorites system
**Commits:** `bed0c2c`, `8d07c33`

### The Principle

Each run folder should contain exactly ONE media product (image/video/audio). This ensures:
- Favorites system works correctly (clear 1:1 mapping)
- Research data is clean (each generation has its own context)
- Export function produces coherent artifacts

### The Logic

```
Interception (Start1)     → run_001/ created (no output yet)
Generate (FIRST)          → run_001/ continues → saves output_image
Generate (SECOND)         → run_002/ NEW (run_001 already has output_*)
Generate (THIRD)          → run_003/ NEW
```

**Check in generation endpoint:**
```python
has_output = any(
    e.get('type', '').startswith('output_')
    for e in existing_recorder.metadata.get('entities', [])
)
if has_output:
    run_id = new_run_id()  # Create NEW folder
else:
    run_id = provided_run_id  # Continue existing folder
```

### Immediate Prompt Persistence

Prompts are now saved immediately after LLM generation (not only on user action):
- Interception result: saved immediately after Stage 2 LLM
- Optimized prompt: saved immediately after optimization LLM

This enables research tracking of what the LLM produced vs what the user edited.

### Files Modified

| File | Change |
|------|--------|
| `schema_pipeline_routes.py` | has_output check in generation, immediate save in optimization |
| `text_transformation.vue` | Pass run_id/device_id to optimization endpoint |

### TODO

- [ ] Stop logging changes after generation (currentRunHasOutput flag not working)
- [ ] Sticky UI: restore prompts/image when switching modes

---

## 🎯 Active Decision: Failsafe Transition - SwarmUI Single Front Door (2026-01-08)

**Status:** ✅ IMPLEMENTED
**Context:** Centralizing all traffic through SwarmUI (Port 7801) while preserving legacy workflow compatibility
**Date:** 2026-01-08

### The Decision: Route Legacy Workflows via SwarmUI Proxy

**Problem:**
- Legacy workflows (Surrealizer, etc.) were hardcoded to access ComfyUI directly on Port 7821.
- This bypassed SwarmUI's orchestration, queue management, and user history.
- "Split brain" architecture where some requests went to 7801 and others to 7821.

**Solution:**
- **Single Front Door:** All DevServer traffic goes to **Port 7801** (SwarmUI).
- **Proxy Pattern:** Legacy workflows use SwarmUI's `/ComfyBackendDirect/*` endpoints to reach the managed ComfyUI instance.
- **Config Flag:** `USE_SWARMUI_ORCHESTRATION = True` (default).
- **Emergency Fallback:** `ALLOW_DIRECT_COMFYUI` flag allows reverting to Port 7821 if SwarmUI is down.

### Architecture

**Before (Split):**
```
DevServer
├── New Pipelines ───> SwarmUI (7801) ───> ComfyUI (Internal)
└── Legacy Workflows ──> ComfyUI (7821)
```

**After (Unified):**
```
DevServer
├── New Pipelines ───> SwarmUI (7801) ───> ComfyUI (Internal)
└── Legacy Workflows ──> SwarmUI (7801) ──> /ComfyBackendDirect/ ──> ComfyUI (Internal)
```

### Benefits

1. **Centralized Management:** SwarmUI controls the queue for ALL generations (legacy and new).
2. **Simplified Networking:** Only one port (7801) needs to be exposed/managed.
3. **Compatibility:** Legacy workflows run without modification (transparent proxying).
4. **Resilience:** If SwarmUI is running, ComfyUI is accessible.

### Implementation Details

**Files Modified:**
- `config.py`: Added feature flags.
- `legacy_workflow_service.py`: Dynamic base URL selection.
- `swarmui_client.py`: Added support for legacy image retrieval methods via proxy.
- `backend_router.py`: Updated routing logic for legacy chunks.

---

## 🎓 DESIGN DECISION (2026-01-13): LoRA Training Studio Path Configuration

**Date:** 2026-01-13

### Decision

All LoRA training paths must be configured in `config.py` using environment variables with relative fallbacks. No hardcoded absolute paths or usernames in repository code.

### Context

**Problem:**
- Initial training_service.py had hardcoded absolute paths that contained a developer's home directory and username
- Usernames in git repo = non-portable, security issue
- Different developers/deployments have different directory structures

### Solution

**Path Configuration Pattern:**
```python
# config.py
_AI_TOOLS_BASE = _SERVER_BASE.parent  # Derived from project location

KOHYA_DIR = Path(os.environ.get("KOHYA_DIR", str(_AI_TOOLS_BASE / "kohya_ss_new")))
LORA_OUTPUT_DIR = Path(os.environ.get("LORA_OUTPUT_DIR", str(_AI_TOOLS_BASE / "SwarmUI/Models/loras")))
```

**Model-Specific Prefixes:**
- NOT a global config variable
- Determined by model-specific config generator method
- `_generate_sd35_config()` → adds `"sd35_"` prefix automatically
- Future: `_generate_flux_config()` → adds `"flux_"` prefix

### Affected Files
- `devserver/config.py` - Path variables added
- `devserver/my_app/services/training_service.py` - Imports from config

---

## 🧠 DESIGN DECISION (2026-01-13): VRAM Management for Training

**Date:** 2026-01-13

### Decision

Training operations must check available VRAM before starting and offer to clear GPU memory by unloading ComfyUI and Ollama models.

### Context

**Problem:**
- SD3.5 Large LoRA training requires ~50GB VRAM
- ComfyUI models (loaded for image generation) occupy 20-40GB
- Ollama LLMs occupy 10-25GB
- Training fails with OOM if models are loaded

### Solution

**Pre-Training VRAM Check:**
1. `GET /api/training/check-vram` - Returns total/used/free VRAM
2. If `free_gb < 50`: Show warning dialog with "Clear VRAM" option
3. `POST /api/training/clear-vram` - Unloads:
   - ComfyUI: `POST http://127.0.0.1:7821/free`
   - Ollama: `POST /api/generate` with `keep_alive: 0`

**UI Flow:**
```
Click "Start Training"
       ↓
VRAM Check Dialog appears
       ↓
[Enough VRAM?] ──Yes──> "Start Training" button
       ↓ No
"Clear ComfyUI + Ollama VRAM" button
       ↓
VRAM freed, now shows "Start Training"
```

### Affected Files
- `devserver/my_app/routes/training_routes.py` - New endpoints
- `public/ai4artsed-frontend/src/views/TrainingView.vue` - VRAM dialog UI

---

## 🎨 DESIGN DECISION (2026-01-08): Material Design Icon Migration

**Date:** 2026-01-08

### Decision

Replace all emoji icons throughout the frontend with Google Material Design SVG icons.

### Context

**Previous State:**
- Emoji icons (💡📋🖼️✨🖌️📷 etc.) used throughout the UI
- Inconsistent rendering across browsers and operating systems
- Visually dominant and distracting from core content
- Limited customization options (size, color, transitions)

**Observed result:** The Material icons are considerably clearer and aesthetically less dominant. This leaves the Träshi character more aesthetic room.

### Reasoning

**Visual Hierarchy:**
- Emoji icons were competing for attention with the actual content
- Material Design icons provide clearer, more subtle visual cues
- Allows the "trashy aesthetic" UI design to breathe without icon clutter
- Better balance between functionality and aesthetic space

**Technical Benefits:**
- Sharp, scalable rendering at all sizes
- `currentColor` integration for theme consistency
- No cross-browser rendering inconsistencies
- Standardized Material Design library (maintenance)
- Easier customization (size, color, transitions)

**Pedagogical Alignment:**
- Cleaner interface supports focus on creative process
- Less visual noise = better learning environment
- Icons serve UI function without dominating student attention

### Implementation

**Icon Categories Replaced:**

1. **Property Quadrant Icons (8):**
   - technical_imaging, arts, attitudes, critical_analysis, semantics, research, aesthetics, freestyle
   - Pattern: Conditional SVG rendering with `v-if`/`v-else-if` chains

2. **MediaInputBox Header Icons (6):**
   - Lightbulb (💡), Clipboard (📋), Arrow (➡️), Robot (✨), Image (🖼️), Plus (➕)
   - Supports both emoji and string names for flexibility

3. **Image Upload Icons (4):**
   - Upload prompts, category bubbles (image/video/sound)
   - Responsive sizing: 32px-64px depending on context

**Technical Pattern:**
```vue
<svg v-if="icon === '💡' || icon === 'lightbulb'"
     xmlns="http://www.w3.org/2000/svg"
     height="24" viewBox="0 -960 960 960"
     fill="currentColor">
  <path d="...Google Material Design path data..."/>
</svg>
```

**Color Strategy:**
- All SVGs use `fill="currentColor"` for theme integration
- Property colors based on color psychology:
  * Orange #FF6F00: Emotional warmth (attitudes)
  * Green #4CAF50: Growth, critical thinking (critical_analysis)
  * Cyan #00BCD4: Scientific, analytical (research)
  * Amber #FFC107: Creative freedom (freestyle)

### Files Affected

**Icon Assets (14 new):** `public/ai4artsed-frontend/src/assets/icons/*.svg`
**Components (5):** PropertyBubble, PropertyCanvas, MediaInputBox, ImageUploadWidget, multi_image_transformation

### Commits

- 337f069: Property icons + config preview images + unique colors
- ecad50d: MediaInputBox header icons
- 4821ae7: Image icons inside MediaBoxes
- c00ece5: i18n placeholders + CSS collision fix

### Alternative Considered

**Keep Emoji Icons:**
- Rejected: Cross-platform inconsistencies
- Rejected: Limited customization
- Rejected: Visual dominance conflicts with pedagogical goals

### Future Implications

- Standardized on Material Design library for all future icon additions
- Easier to maintain consistent visual language
- Prepared for potential theming/dark mode in future

---

## 🚨 CRITICAL ARCHITECTURE FIX (2025-12-28): Unified Streaming Orchestration

**Date:** 2025-12-28

### Problem Identified

**Architecture Violation:** The `/api/text_stream/*` endpoints violated the core principle that **DevServer = Smart Orchestrator | Frontend = Dumb Display**.

**Specific Issues:**
1. **Frontend Orchestration:** Frontend was calling stage-specific endpoints (`/api/text_stream/stage2`) directly, deciding which stages to run
2. **Bypassed Safety:** Stage 1 (§86a StGB safety check) was not enforced in streaming mode - frontend could skip it
3. **Security Risk:** Frontend could be manipulated to bypass safety checks (unprofessional, illegal)
4. **Code Duplication:** Interception and Optimization used different endpoints despite being functionally identical

### Solution Implemented

**Architectural Principle Enforced:**
```
Frontend calls ONE endpoint: /api/schema/pipeline/execute
↓
DevServer orchestrates ALL stages (Stage 1 → Stage 2)
↓
Frontend receives SSE stream and displays results
```

**Key Changes:**
1. **Deleted `/api/text_stream/*`** - Entire path removed, violations eliminated
2. **Unified Endpoint:** `/api/schema/pipeline/execute` now supports streaming via `enable_streaming=true`
3. **Mandatory Stage 1:** Safety check ALWAYS runs first (synchronous, ~2-8s), blocks unsafe content
4. **Stage 2 Streaming:** Character-by-character SSE streaming after Stage 1 passes
5. **Unified Architecture:** Interception and Optimization use SAME endpoint, just different parameters

### Technical Implementation

**Backend (`schema_pipeline_routes.py`):**
```python
# Supports both GET (EventSource) and POST (JSON)
@schema_bp.route('/pipeline/execute', methods=['POST', 'GET'])

# Streaming function runs Stage 1 FIRST, always
def execute_pipeline_streaming(data: dict):
    # Stage 1: Safety Check (synchronous)
    is_safe, checked_text, error_message = execute_stage1_gpt_oss_unified(...)
    if not is_safe:
        yield blocked_event  # STOP - DevServer decides
        return

    # Stage 2: Interception (streaming)
    for chunk in ollama_stream:
        yield chunk_event
```

**Frontend (`text_transformation.vue`):**
```typescript
// BOTH Interception and Optimization use same endpoint
streamingUrl = '/api/schema/pipeline/execute'

// Only parameters differ:
// Interception: input_text=user_input, context_prompt=pipeline_context
// Optimization: input_text=interception_result, context_prompt=optimization_instruction
```

### Architectural Principles Established

1. **DevServer = Orchestrator:** Backend decides stage execution order, safety checks, and flow control
2. **Frontend = Display:** Frontend only listens to streams and displays results
3. **Mandatory Safety:** Stage 1 cannot be bypassed - technically impossible
4. **No Duplication:** Functionally identical operations use same code path
5. **Clean Separation:** Orchestration logic lives ONLY in DevServer, never in Frontend

### Files Modified

**Backend:**
- `devserver/my_app/__init__.py` - Removed text_stream_routes import
- `devserver/my_app/routes/schema_pipeline_routes.py` - Added SSE streaming to unified endpoint
- `devserver/my_app/routes/text_stream_routes.py` - **DELETED**

**Frontend:**
- `public/ai4artsed-frontend/src/views/text_transformation.vue` - Updated to use unified endpoint for both Interception and Optimization

### Testing Verification

✅ **Stage 1 Safety:** "HAKENKREUZ" correctly blocked with §86a message, Stage 2 never runs
✅ **Stage 2 Streaming:** "ein blauer Vogel" passes Stage 1, streams character-by-character
✅ **Interception:** Full flow works (Stage 1 → Stage 2 streaming)
✅ **Optimization:** Works identically to Interception (same endpoint, different params)
✅ **Browser Test:** Confirmed working in production-like environment

### Impact

**Security:** ✅ §86a compliance enforced at server level, cannot be bypassed
**Architecture:** ✅ Clean separation of concerns, single source of truth
**Maintainability:** ✅ Less code, no duplication, clear responsibilities
**Professional:** ✅ Industry-standard architecture (backend orchestrates, frontend displays)

---

## 2025-12-22: text_transformation.vue Refactoring - Stop After Phase 1

### Decision: text_transformation.vue Refactoring - Stop After Phase 1

**Context:** File was 2665 lines (26k tokens) with 48% being inline CSS (1285 lines). Maintenance nightmare. Planned 4-phase incremental refactoring.

**Completed:**
- ✅ **Phase 1: Style Extraction** (48% reduction)
  - Created `/src/assets/animations.css` (2.1K) - Shared @keyframes
  - Created `/src/views/text_transformation.css` (26K) - Component styles
  - Updated Vue component to import external CSS
  - Result: 2665 → 1396 lines (48% reduction)
  - Risk: MINIMAL (pure CSS move, zero logic changes)
  - Verification: TypeScript passed, manual test in the browser passed

**Skipped (Intentionally):**
- ❌ **Phase 2: Component Extraction** (StartButton, CodeEditor)
  - Would reduce by ~10% but involves state management, v-model bindings
  - Risk: LOW-MEDIUM
- ❌ **Phase 3: Selector Extraction** (CategorySelector, ModelSelector)
  - Would reduce by ~15% but complex state, hover logic, metadata loading
  - Risk: MEDIUM-HIGH
- ❌ **Phase 4: Script Optimization** (composables, watchers)
  - Would reduce by ~5% but micro-optimizations
  - Risk: MEDIUM

**Decision:** Stop after Phase 1

**Rationale:**
- **Risk/Benefit Analysis:** Phase 1 achieved 48% reduction with MINIMAL risk
- **Diminishing Returns:** Phase 2-4 would add only ~30% more reduction but MEDIUM-HIGH risk
- **Current State:** File is now maintainable (1396 lines), functional, TypeScript passes
- **Fail-Safety First:** Safety is weighted above further optimization

**Trade-offs:**
- ✅ **Achieved:** Massive maintainability improvement (48% reduction)
- ✅ **Preserved:** Zero breaking changes, fully functional
- ✅ **Avoided:** Risk of introducing bugs through component extraction
- ❌ **Missed:** Could have reached 60-70% reduction if Phase 2-4 completed
- ❌ **Missed:** Component reusability (StartButton could be used elsewhere)

**Impact:**
- **Files Modified:**
  - `src/views/text_transformation.vue` (2665 → 1396 lines)
  - `src/assets/animations.css` (new, 2.1K)
  - `src/views/text_transformation.css` (new, 26K)
- **Commit:** `1ebdba8` - "refactor(text-transformation): Extract inline styles to external CSS files (Phase 1)"
- **Technical Debt:** File still contains ~1100 lines of logic that COULD be extracted, but SHOULD NOT be due to risk

**Lessons Learned:**
1. **Safety First:** 48% improvement with zero risk is better than 70% with potential bugs
2. **Incremental Wins:** Don't chase perfection, achieve "good enough"
3. **Risk Assessment:** Component extraction involves state complexity that CSS doesn't have
4. **Validation:** The working result in the browser is the success metric

**Future Considerations:**
If text_transformation.vue grows significantly in the future (e.g., new media types), revisit Phase 2-4. For now, the file is maintainable and not worth the risk.

---

## 2025-12-22: SSE Streaming with Waitress (No Server Migration)

### Decision: SSE Streaming with Waitress (No Server Migration)

**Context:** SSE text streaming infrastructure was already implemented, but buffering prevented the typewriter effect. The earlier recommendation was to replace Waitress with Gunicorn.

**Constraint:** Replacing a working server for one small animation feature is not justified.

**Analysis:**
1. **Gunicorn benefits:** Only helps SSE, NOT WebSockets (would need ASGI for WebSockets)
2. **ComfyUI:** Uses HTTP polling (2s intervals), not streaming - Gunicorn wouldn't help
3. **ASGI migration:** Would require rewriting 50+ routes with async/await (~2-3 weeks effort)
4. **Waitress status:** Stable, works for all other endpoints, simple configuration

**Decision:** Keep Waitress, optimize Flask code instead

**Solution Implemented:**
```python
# Flask explicit flushing forces Waitress to send chunks immediately
from flask import stream_with_context

def generate():
    yield generate_sse_event('chunk', {...})
    yield ''  # Force flush

return Response(stream_with_context(generate()), ...)
```

**Why This Works:**
- `stream_with_context()` maintains request context during streaming
- Empty `yield ''` forces Waitress to flush buffer immediately
- Verified with curl: Chunks arrive progressively (not batched)
- No server replacement needed

**Trade-offs:**
- ✅ Minimal code change (10 lines)
- ✅ Waitress remains stable for all other endpoints
- ✅ Easy to rollback if issues arise
- ❌ Slightly more verbose code (extra yield per chunk)

**Alternative Considered (Rejected):**
- **Gunicorn + gevent:** Would solve SSE buffering but doesn't provide broader benefits (ComfyUI still uses polling)
- **ASGI (Uvicorn + Quart/FastAPI):** Massive migration effort for minimal UX improvement

**Future Path:**
If ComfyUI WebSocket integration is implemented (real-time progress for Stage 4 image generation), use **Flask-SocketIO + eventlet** which works with Waitress (no ASGI needed).

---

### Decision: Dev vs Prod Streaming URLs

**Problem:** Vite dev proxy buffers SSE despite backend fixes. Direct localhost:17802 connection works but fails in production (port 17801).

**Solution:** Environment-aware URL strategy
```javascript
const isDev = import.meta.env.DEV
const url = isDev
  ? `http://localhost:17802/api/text_stream/...`  // Dev: Direct backend
  : `/api/text_stream/...`  // Prod: Relative URL via Nginx
```

**Rationale:**
- **Dev mode:** Vite proxy buffers SSE → use direct backend connection
- **Prod mode:** Nginx doesn't buffer SSE → use relative URL
- **Cloudflare:** Only sees HTTPS requests to domain → not affected by localhost URLs

**Trade-offs:**
- ✅ Works in both environments
- ✅ No CORS issues in prod (relative URL = same origin)
- ✅ No Vite buffering in dev (bypasses proxy)
- ⚠️ Dev requires backend on specific port (17802)

---

### Decision: Runtime Config Loading for user_settings.json

**Problem:** Backend routes imported config at module load time (before user_settings.json loaded)
```python
# WRONG: Import-time binding
from config import STAGE2_INTERCEPTION_MODEL  # Reads before user_settings loaded
model = request.args.get('model', STAGE2_INTERCEPTION_MODEL)  # Uses old value
```

**Root Cause:**
- `_load_user_settings()` runs in `create_app()` and uses `setattr(config, key, value)`
- But route modules import before app creation
- Import-time binding captures old value from config.py

**Solution:** Import module, access attribute at runtime
```python
# RIGHT: Runtime binding
import config  # Import module reference
model = request.args.get('model', config.STAGE2_INTERCEPTION_MODEL)  # Reads current value
```

**Impact:**
- Stage 2 now correctly uses 120b from user_settings.json (not hardcoded 20b)
- All user configuration honored at runtime

**Files Affected:**
- `text_stream_routes.py` (Stage 2, Stage 4)

---

## 2025-12-21: Minimal Editable Code Box (No Syntax Highlighting)

### Decision: Minimal Editable Code Box (No Syntax Highlighting)

**Context:** The p5.js code output was to become editable, with syntax highlighting (Prism.js) and a run button. Initial implementation with Prism.js caused critical blocking issue.

**Problem with Initial Approach:**
```typescript
// BLOCKING: Top-level await in Vue script setup
try {
  const prismModule = await import('prismjs')
  await import('prismjs/themes/prism-tomorrow.css')
  await import('prismjs/components/prism-javascript')
} catch (error) { ... }
```
**Result:** Browser slowdown (Firefox warning), views showing no content, interception_result broken.

**Rollback & Decision:**
- `git reset --hard d5263a3` to restore working state
- Syntax highlighting was dropped
- **Decision:** Implement minimal solution without external dependencies

**Final Implementation:**
1. **Editable textarea** - Remove `readonly`, use `v-model="editedCode"`
2. **Run button (▶️)** - Replace clipboard icon, trigger iframe re-render
3. **Vue reactivity** - `watch(outputCode)` to initialize `editedCode`
4. **Key-based re-render** - Increment `iframeKey` to force iframe reload

**Trade-offs:**
- ❌ No syntax highlighting (Prism.js dropped)
- ❌ No complex overlay pattern
- ✅ Zero external dependencies
- ✅ Simple, maintainable code
- ✅ Fast, non-blocking component load
- ✅ User can still edit and run code

**Technical Lesson:**
**Never use top-level `await` in Vue script setup** - it blocks component mounting and breaks reactivity. If async imports are needed, use `onMounted()` hook instead.

**Alternative Considered (Not Implemented):**
Moving Prism import to `onMounted()` would fix blocking issue, but simplicity is weighted above syntax highlighting.

**Files Modified:**
- `public/ai4artsed-frontend/src/views/text_transformation.vue`

**Commits:**
- `576e387` - feat: Add editable p5.js code box with run button (minimal version)
- `4dffb53` - fix: Increase code textarea height to match iframe (400px → 600px)

---

## 2025-12-11: Internal App Clipboard for Copy/Paste Buttons

### Decision: Internal App Clipboard for Copy/Paste Buttons
**Context:** All textareas needed consistent copy/paste/delete functionality. Initial approach attempted browser Clipboard API (`navigator.clipboard.readText()`) and `execCommand('paste')`, but both had issues:
- `navigator.clipboard.readText()` requires permission dialog (bad UX)
- `execCommand('paste')` is deprecated and unreliable across browsers

**Decision:** Implement internal app-wide clipboard buffer (`const appClipboard = ref('')`)
- Copy buttons write to `appClipboard.value`
- Paste buttons read from `appClipboard.value` and set directly to textarea refs
- No browser permissions, no deprecated APIs
- Works reliably across all textareas in the app

**Reasoning:**
- Simple, predictable, consistent behavior
- No security dialogs interrupting workflow
- Copy/paste within app is sufficient for the use case (users can still use Ctrl+V for external content)
- Same pattern as existing "Config → Context" functionality

**Affected Files:**
- `public/ai4artsed-frontend/src/views/text_transformation.vue`
  - Added: `appClipboard` ref (line 492)
  - Modified: All copy/paste functions for 5 textareas (inputText, contextPrompt, interceptionResult, optimizedPrompt, outputCode)
  - Added: Copy/Paste/Delete buttons to interceptionResult, optimizedPrompt
  - Added: Copy button to outputCode (readonly)

**Alternative Rejected:** Draft Context feature (Provide/Inject pattern to share form state with Träshy chat) - too complex, didn't solve the core problem, unreliable

---

## 🎯 Active Decision: Input Mappings Pattern for ComfyUI Workflows (2025-12-01)

**Status:** ✅ IMPLEMENTED & TESTED
**Files Modified:** `backend_router.py`, `legacy_workflow_service.py`
**Config Example:** `/devserver/schemas/chunks/output_image_qwen_img2img.json`

### Summary

Declarative `input_mappings` pattern replaces hardcoded node IDs in prompt injection configs. Enables clean separation between workflow definition and input routing logic.

### Pattern

```json
{
  "input_mappings": {
    "prompt": { "node": 76, "field": "inputs.prompt" },
    "input_image": { "node": 78, "field": "inputs.image" }
  }
}
```

### Rationale

**Why this matters:**
- ComfyUI node IDs vary across workflows (not standardized)
- Multiple nodes can accept same input type (e.g., QWEN's dual TextEncodeQwenImageEdit nodes)
- Hardcoding node paths in prompt_injection config creates maintenance burden
- Declarative approach centralizes workflow-specific routing logic in chunk JSON

**Architectural benefit:**
- Backend becomes generic (reads mappings, injects values)
- Chunks define workflow structure (nodes, connections) AND input routing
- No need for backend code changes per new workflow type

**Implementation detail:**
`legacy_workflow_service.py` prioritizes `input_mappings` from chunk, falls back to legacy `prompt_injection` config for backwards compatibility.

### Related Concepts

- **Execution Mode Routing** - Companion pattern (see below)
- **Chunk Consolidation** - Related simplification decision (ARCHITECTURE PART 15)

---

## 🎯 Active Decision: Execution Mode Routing (2025-12-01)

**Status:** ✅ IMPLEMENTED & TESTED
**Location:** `backend_router.py` (lines 700-741)
**Config Field:** `execution_mode` in chunk JSON

### Summary

Chunks declare `execution_mode` to specify execution handler. Decouples workflow logic from execution strategy.

### Pattern

```json
{
  "execution_mode": "legacy_workflow"
}
```

**Supported modes:**
- `"legacy_workflow"` - Full ComfyUI workflow via legacy_workflow_service
- Future: `"direct_api"`, `"distributed"`, `"streaming"`, etc.

### Rationale

**Why separation matters:**
- ComfyUI workflows vs direct API calls have different execution paths
- Same workflow might need different handlers in different contexts
- Future optimization (streaming, batching) requires flexibility
- Chunk-level routing enables media-specific execution strategies

**Scalability:**
- New execution mode → Add handler function
- Backend router delegates based on mode
- Workflows unchanged (mode is just metadata)

### Backwards Compatibility

Chunks without `execution_mode` default to `"legacy_workflow"` for legacy workflow chunks.

### Related Decisions

- **Input Mappings Pattern** - Companion pattern
- **Backend Transparency** - Related architectural principle (ARCHITECTURE PART 15)

---

## 🎯 Active Decision: Mode Implementation - Separate Routes (2025-12-01)

**Status:** ✅ IMPLEMENTED & TESTED
**Routes:** `/text-transformation` (t2i) vs `/image-transformation` (i2i)
**Components:** `text_transformation.vue`, `image_transformation.vue`
**Header Toggle:** Mode selector in navigation bar

### Summary

Text-to-Image (t2i) and Image-to-Image (i2i) workflows implemented via separate routes with identical Stage 2 configs.

### Architecture

```
/text-transformation          /image-transformation
      ↓                              ↓
[Upload text input]          [Upload image input]
      ↓                              ↓
Stage 1: Translation          Stage 1: Image context
      ↓                              ↓
Stage 2: [SHARED CONFIGS]
      ↓
[Kunstgeschichte, Surrealismus, etc.]
      ↓
Stage 3: Safety + Translation
      ↓
Stage 4: Media Generation
      ↓
[sd35_large (t2i only), qwen_img2img (i2i only)]
```

### Key Design Principles

1. **Separate Routes** - Clear t2i vs i2i distinction
2. **Shared Stage 2 Configs** - Pedagogical transformations apply equally
3. **Mode-Specific Output Configs** - Only relevant models available per mode
4. **Header Toggle** - User-facing mode selection

### Why This Approach

**Option Comparison:**
- ❌ Option B (Mode toggle in single route): Creates Route→Mode→Pipeline ambiguity
- ❌ Option C (Graceful fallback): Implicit behavior hard to debug
- ✅ Option A (Separate routes): Clear, explicit, no hidden magic

**Educational value:**
- Users explicitly choose mode (aware of workflow type)
- Interface reflects workflow structure (spatial separation)
- No confusing automatic fallbacks

### Frontend Implementation

Both `text_transformation.vue` and `image_transformation.vue`:
- Mirror identical UI structure
- Use same Stage 2 config selector
- Header shows "📝 Text→Bild" or "🖼️ Bild→Bild" active mode
- Toggle button switches between modes

### Backend Implementation

Both routes call same orchestrator with different initial context:
```python
# /text-transformation
context['input_type'] = 'text'

# /image-transformation
context['input_type'] = 'image'
context['input_image_path'] = upload_result['path']
```

Output configs filter based on `input_type`:
- qwen_img2img: `input_type: "image"`
- sd35_large: `input_type: "text"`

### Status

- ✅ Routes implemented
- ✅ Frontend toggle implemented
- ✅ Output config filtering works
- ✅ End-to-end testing passed
- ✅ German→English translation works for both modes

---

## 🎯 Active Decision: No Optimization UI for img2img (QWEN) (2025-12-02)

**Status:** ✅ IMPLEMENTED & COMPLETE
**Files Modified:** `image_transformation.vue`, `PageHeader.vue` (new)
**Frontend Commit:** d66321e (final UI restructure)

### Summary

Image-to-Image (i2i) workflows using QWEN img2img do NOT need the Stage 2 Optimization step that text-to-image (t2i) workflows require. Simplified flow eliminates UI clutter and improves execution speed by ~1 second.

### Why img2img Doesn't Need Optimization

**Comparison:**

| Aspect | Text-to-Image (t2i) | Image-to-Image (i2i) |
|--------|---------------------|----------------------|
| **Pedagogical Transformation** | ✅ Artistic interception (Dada, Bauhaus) | ❌ No artistic transformation needed |
| **Model-Specific Optimization** | ✅ SD3.5 needs prompt refinement | ❌ QWEN works well with direct prompts |
| **UI Complexity** | 3 states (input → interception → optimization) | 2 states (input → generation) |
| **User Experience** | Learn artistic perspectives, then optimize | Describe desired transformation, generate |

### The Architecture

**QWEN img2img Pipeline (Simplified):**
```
Input: Image + Context description
   ↓
Stage 1: Translate context description (German → English)
   ↓
Stage 2: (SKIPPED - no interception/optimization)
   ↓
Stage 3: Safety validation
   ↓
Stage 4: QWEN img2img generation
   - Input: original image + translated context
   - Output: transformed image
```

**vs. Text-to-Image Pipeline (Complex):**
```
Input: Text prompt
   ↓
Stage 1: Translate (German → English)
   ↓
Stage 2a: Pedagogical Interception (artistic transformation)
   ↓
Stage 2b: Model Optimization (SD3.5-specific refinement)
   ↓
Stage 3: Safety validation
   ↓
Stage 4: SD3.5 image generation
```

### Frontend Implementation

**Removed from image_transformation.vue:**
1. Model selection UI (was hardcoded choice between img2img models)
2. Optimization preview box (would show "optimized" prompt)
3. Two-phase "Start" buttons (was Start1 → interception, Start2 → generation)

**Result:**
- Single "Start" button (context description → direct generation)
- No optimization preview
- Faster user workflow
- Less cognitive load
- 100% CSS parity with text_transformation.vue structure

### UI/UX Impact

**Before (Complex):**
- User uploads image + enters description
- Clicks "Start1" (shows optimization preview)
- Sees "optimized" context in box
- Clicks "Start2" (generates image)
- 3+ seconds overhead just for optimization UI

**After (Simple):**
- User uploads image + enters description
- Clicks "Start" (direct generation)
- Sees progress animation
- Image appears
- ~2 seconds faster, simpler workflow

### Design Principle

**If optimization_instruction is missing or not pedagogically significant, it is eliminated from the UI.**

This applies to:
- img2img with QWEN (confirmed, implemented)
- Future: Video generation with LTX-Video (likely)
- Future: Audio generation with ACEnet (likely)

The backend CAN perform optimization if needed, but the UI doesn't expose it unless it serves a pedagogical purpose.

### Technical Implementation

**Backend (unchanged):**
- Pipeline executes stages correctly
- Safety checks still performed
- No `/pipeline/optimize` call for i2i workflows

**Frontend (restructure):**
- Extracted PageHeader component (shared with text_transformation.vue)
- Removed category/model selection UI
- Auto-selects config based on mode
- Single cohesive input → generation flow

### Files Changed

**Created:**
- `public/ai4artsed-frontend/src/components/PageHeader.vue` (shared header)

**Modified:**
- `public/ai4artsed-frontend/src/views/image_transformation.vue` (removed optimization section)
- `public/ai4artsed-frontend/src/views/text_transformation.vue` (uses PageHeader component)

### Decision Criteria Applied

✅ **UX Simplification** - Fewer UI elements = less cognitive load
✅ **Performance** - ~1 second faster execution
✅ **Consistency** - Image mode now as simple as t2i mode
✅ **Pedagogical** - No pedagogical value in showing optimization step
✅ **Maintainability** - One less layer of complexity

### Future Reconsideration

If QWEN performance significantly improves with explicit optimization:
- Can add optimization back as hidden background process (no UI changes)
- Users wouldn't be aware, but output quality improves
- Architectural flexibility maintained

---

## 🎯 Active Decision: Progressive Disclosure Scrolling Pattern (2025-11-29)

**Status:** ✅ IMPLEMENTED
**Component:** `text_transformation.vue`
**Pattern Name:** Progressive Disclosure for Educational UX

### Summary

Auto-scroll functionality that serves a **didactic purpose** - actively guiding users through distinct phases of the creative-technical workflow to prevent cognitive overload.

### The Pattern

**Three phases of guided progression:**

1. **Scroll1**: After interception → Reveals media category selection
2. **Scroll2**: After category selection → Reveals model options and generation controls
3. **Scroll3**: After generation start → Focuses on output/animation

**Design Principle:** Interface complexity is revealed step-by-step. Each scroll marks a **conceptual transition** in the creative process.

**Key Rule:** Scrolling only moves **downward** (forward progression through pipeline).

### Why This Matters

**Educational UX Design:**
- Users learn workflow structure through **spatial navigation**
- Physical scrolling becomes part of the learning experience
- Prevents overwhelming users with all options simultaneously
- Maintains user agency while providing guidance

**Cognitive Load Management:**
- Complex multi-stage workflows broken into digestible phases
- Interface reveals what's needed when it's needed
- Visual feedback reinforces mental model of pipeline stages

### Implementation Detail

**Critical:** The `.text-transformation-view` uses `position: fixed`, so scrolling must target the **container** (`mainContainerRef`), NOT `window`.

```javascript
// Correct implementation
mainContainerRef.value.scrollTo({
  top: mainContainerRef.value.scrollHeight,
  behavior: 'smooth'
})
```

### Full Documentation

See [ARCHITECTURE PART 12 - Frontend-Architecture.md](./ARCHITECTURE%20PART%2012%20-%20Frontend-Architecture.md#progressive-disclosure-scrolling-pattern) for complete implementation details and code examples.

### Files Changed
- `public/ai4artsed-frontend/src/views/text_transformation.vue`
  - Functions: `scrollDownOnly()`, `scrollToBottomOnly()`
  - CSS: `.output-frame` dimensioning fixed (adaptive to image size)
- `docs/ARCHITECTURE PART 12 - Frontend-Architecture.md` - Pattern documentation

---

## 🎯 Active Decision: Stage 2 Optimization - Two Separate Endpoints (2025-11-26)

**Status:** ✅ IMPLEMENTED
**Decision:** Create `/pipeline/optimize` endpoint separate from `/pipeline/stage2`
**Principle:** Two user actions → Two endpoints (not one endpoint with flags)

### Quick Summary

| User Action | Endpoint | Purpose |
|-------------|----------|---------|
| Clicks "Start" Button | `/pipeline/stage2` | Interception with config.context |
| Selects Model | `/pipeline/optimize` | Optimization with optimization_instruction |

### Why This Matters

**Requirement:** The "Start" button triggers one action on the two boxes above it, and the click on a model triggers one action on the box directly above the model selection.

**The simple solution:** Two clear endpoints for two clear operations. No flags, no complex logic.

### Key Architectural Insights

1. **Use PromptInterceptionEngine** - Don't build prompts manually
2. **optimization_instruction goes in CONTEXT** - Not in TASK_INSTRUCTION
3. **Frontend states intent explicitly** - Each click maps to ONE endpoint
4. **No workarounds** - Use the system's modularity
5. **Don't warn about normal behavior** - Only notify for actual errors

**Full details:** See [ARCHITECTURE_STAGE2_SEPARATION.md](./ARCHITECTURE_STAGE2_SEPARATION.md)

### Files Changed
- `devserver/my_app/routes/schema_pipeline_routes.py` - Added `/pipeline/optimize` endpoint
- `public/ai4artsed-frontend/src/views/text_transformation.vue` - runOptimization() calls `/optimize`

---

## 🎯 Active Decision: Stage 2 Refactoring - Separate Interception & Optimization Functions (2025-11-26)

**Status:** ✅ IMPLEMENTED
**Context:** Critical bug fix - config.context contaminating optimization calls
**Date:** 2025-11-26

### The Problem: Mixing Unrelated Operations

**Root Cause Bug:**
The function `execute_stage2_with_optimization()` was combining two COMPLETELY independent operations in a single LLM call:

1. **Interception** (Pedagogical Transformation)
   - Input: User's original text
   - Context: `config.context` (artistic attitude like "analog photography", "dada", "bauhaus")
   - Output: Transformed text with artistic perspective

2. **Optimization** (Model-Specific Refinement)
   - Input: Interception result
   - Context: `optimization_instruction` from output chunk (e.g., "describe as cinematic scene")
   - Output: Text optimized for specific image generation model

**The Bug:**
```python
# OLD (BROKEN):
# config.context ("dada attitude") was leaking into optimization
# optimization_instruction should replace context, not blend with it

original_context = config.context  # "dada attitude"
new_context = original_context + "\n\n" + optimization_instruction  # CONTAMINATED!
```

**Result:** Optimization was using BOTH artistic attitude AND model-specific rules, causing:
- Inefficient prompts (conflicting instructions)
- Confusion about responsibilities
- Reported symptom: prompt optimization used config.context instead of the optimization instruction

### The Solution: Complete Separation

**Three Independent Functions:**

1. **`execute_stage2_interception()`** - Pure Interception
   - Purpose: Pedagogical transformation ONLY
   - Uses: `config.context` (artistic attitude)
   - Input: User's text
   - Output: Transformed text
   - **No access to optimization_instruction**

2. **`execute_optimization()`** - Pure Optimization (CRITICAL FIX)
   - Purpose: Model-specific refinement ONLY
   - Uses: `optimization_instruction` from output chunk
   - Input: Interception result (or any text)
   - Output: Optimized prompt
   - **Critical:** Uses Prompt Interception structure CORRECTLY:
     ```python
     full_prompt = (
         f"Task:\nTransform the INPUT according to the rules provided by the CONTEXT.\n\n"
         f"Context:\n{optimization_instruction}\n\n"  # ← optimization_instruction goes HERE
         f"Prompt:\n{input_text}"
     )
     ```
   - **NO access to config.context** - Complete isolation guaranteed
   - **This was the root cause:** optimization_instruction must go in CONTEXT field, not be appended to existing context

3. **`execute_stage2_with_optimization()`** - Deprecated Proxy (Backward Compatibility)
   - Purpose: FAILSAFE - calls the two new functions internally
   - Emits: `DeprecationWarning` to guide future development
   - Result: Returns `Stage2Result` with both:
     - `interception_result` (after Call 1)
     - `optimized_prompt` (after Call 2)
     - `two_phase_execution: true` metadata flag

### Critical Understanding: Prompt Interception Structure

**This refactoring revealed a fundamental misunderstanding:**

In Prompt Interception, the `optimization_instruction` is NOT an additional rule to append to existing context. It IS the context for the transformation:

```python
# WRONG (Old approach):
context = config.context + optimization_instruction  # Blends two contexts

# CORRECT (New approach):
# optimization_instruction IS the CONTEXT (USER_RULES)
full_prompt = f"""Task:
Transform the INPUT according to the rules provided by the CONTEXT.

Context:
{optimization_instruction}

Prompt:
{input_text}"""
```

**Why This Matters:**
- Config.context defines WHO the LLM thinks it is (artistic persona)
- Optimization_instruction defines WHAT the LLM should optimize for (model constraints)
- These are DIFFERENT concerns and must never mix
- The isolated `execute_optimization()` function makes this separation permanent

### Helper Functions Added

1. **`_load_optimization_instruction(output_config_name)`**
   - Loads optimization instruction from output chunk metadata
   - Handles file I/O and error recovery gracefully
   - Returns None if not found (optimization is optional)

2. **`_build_stage2_result(interception_result, optimized_prompt, ...)`**
   - Builds Stage2Result dataclass for backward compatibility
   - Ensures deprecated proxy returns expected structure
   - Includes metadata about which functions ran

### Implementation Details

**Files Modified:**
- `/devserver/my_app/routes/schema_pipeline_routes.py`
  - Lines 123-140: `_load_optimization_instruction()` helper
  - Lines 143-181: `_build_stage2_result()` helper
  - Lines 188-246: New `execute_optimization()` function
  - Lines 248-296: New `execute_stage2_interception()` function
  - Lines 302-421: Backup `execute_stage2_with_optimization_SINGLE_RUN_VERSION()`
  - Lines 424-505: Deprecated proxy `execute_stage2_with_optimization()`

**No Breaking Changes:**
- Deprecated proxy maintains backward compatibility
- Old code calling `execute_stage2_with_optimization()` still works
- DeprecationWarning guides developers to new functions
- All existing configs and pipelines work unchanged

### Testing & Validation

✅ **Isolation Verified:**
- `execute_optimization()` has zero access to config.context
- File scope prevents any config contamination
- Optimization uses ONLY optimization_instruction

✅ **Structure Correct:**
- Prompt Interception pattern correctly implemented
- optimization_instruction in CONTEXT field (not TASK field)
- Task field is generic ("Transform the INPUT...")

✅ **Backward Compatible:**
- Deprecated proxy calls new functions internally
- No API changes for existing callers
- DeprecationWarning guides future refactoring

### Design Principles Applied

1. **NO WORKAROUNDS** - Fixed root problem (context leakage), not symptoms
2. **CLEAN SEPARATION** - Each function has single responsibility
3. **BACKWARD COMPATIBLE** - Deprecated proxy prevents breaking changes
4. **SELF-DOCUMENTING** - Function names express purpose (Interception vs Optimization)
5. **FAILSAFE ARCHITECTURE** - Proxy emits deprecation warnings to guide future work

### Related Documentation

- **ARCHITECTURE PART 01** - Updated Section 1.2 with new function calls

### Future Work

- Remove deprecated proxy after a safe period
- Update Frontend Vue to call new functions directly
- Consider making optimization_instruction mandatory in output chunks
- Potential: Move optimization to separate "Phase 2b" UI state

---

## 🎯 Active Decision 1: Stage 3 Architecture Correction - Translation Placement (2025-11-21)

**Status:** 📋 PLANNED (the earlier "mega-prompt" plan was flawed and is corrected here)
**Context:** Translation placement in 4-stage flow + preserving user edit opportunity
**Date:** 2025-11-21

### The Thinking Error: The "Mega-Prompt" Plan

**Flawed Plan:**
```
Stage 1: Translation + Safety
Stage 2: Interception + Optimization + Safety (all in ONE "mega-prompt")
Stage 3: ELIMINATED ← "33% faster!"
Stage 4: Media Generation
```

**Why This Was Wrong:**
1. **Pedagogical Error:** Users need to EDIT after optimization, BEFORE final safety
2. **No Edit Opportunity:** Merging Stage 2+3 prevents user from seeing/editing optimized prompt
3. **Lost Transparency:** Prompt interception is for REFLECTION - users must see intermediate results
4. **Misunderstood Goal:** Speed optimization sacrificed pedagogical core principle

### The Correct Architecture

**Revised Plan:**
```
Stage 1: Safety ONLY (NO translation, work in original language DE/EN)
  ↓ Text in German/English (bilingual §86a filters work on both)

Stage 2: Interception + Optimization (in original language, ONE LLM call)
  ↓ Transformed + optimized text (still in German/English)

→ USER CAN EDIT HERE! ← This is the key pedagogical moment!

Stage 3: Translation (DE→EN) + Safety Check
  ↓ English text, safety-approved

Stage 4: Media Generation
```

**Key Changes:**
1. **Translation moved:** Stage 1 → Stage 3
2. **Stage 2 extended:** Add media-specific optimization (SD3.5, Audio, Music)
3. **Edit opportunity preserved:** User edits in native language BEFORE final safety
4. **Stage 3 kept separate:** Not merged into Stage 2

### Why This Is Correct

**Pedagogical:**
- Users work in native language (German) for better reflection
- Users can edit optimized prompt before media generation
- Prompt interception remains transparent (see intermediate steps)
- Aligns with "Gegenhegemoniale Pädagogik" - empowerment through understanding

**Technical:**
- Bilingual §86a filters work on both DE and EN
- Same total execution time (translation still happens once)
- Simpler architecture (no complex "mega-prompt" JSON parsing)
- Clean separation of concerns

### Implementation Plan

**Files to Modify:**
1. `/devserver/schemas/configs/pre_interception/gpt_oss_safety_only_bilingual.json` (NEW)
   - Stage 1: Safety without translation

2. `/devserver/schemas/engine/stage_orchestrator.py`
   - Add `execute_stage1_safety_only_bilingual()`
   - Add `execute_stage3_translation()`

3. `/devserver/my_app/routes/schema_pipeline_routes.py`
   - Update Stage 1 call (use safety-only function)
   - Update Stage 3-4 loop (add translation before safety)

4. `/devserver/schemas/configs/pre_output/translation_de_en_stage3.json` (NEW)
   - Stage 3: Translation DE→EN

**Optional Enhancements:**
5. `/devserver/schemas/chunks/optimize_*.json` (NEW)
   - Media-specific optimization chunks (image, audio, music)

### Related Documentation

- **ARCHITECTURE PART 01** - Updated to reflect correct Stage 1-3 flow (Version 2.1)
- **Branch:** `feature/stage2-mega-prompt` - DO NOT MERGE (flawed architecture)
- **Develop Branch:** Clean state, start implementation from here

### Lessons Learned

**What Went Wrong:**
- Prioritized speed optimization over pedagogical goals
- Didn't question "why does user need to edit after optimization?"
- The flawed plan was documented as if it were fact

**How to Avoid This:**
- Always ask: "What is the pedagogical purpose of each stage?"
- User edit opportunities are CRITICAL in this system
- Document assumptions so they can be challenged
- Consult architecture agent before major changes

---

## 🎯 Active Decision 2: PropertyCanvas Unification - Single Coordinate System (2025-11-21)

**Status:** ✅ IMPLEMENTED (Commits e266628 + be3f247)
**Context:** Vue frontend component architecture for property-based config selection
**Date:** 2025-11-21

### The Problem: Coordinate System Mismatch

**Original Architecture (FLAWED):**
```
PropertyQuadrantsView
  ├── PropertyCanvas (category bubbles) → percentage-based positioning
  └── ConfigCanvas (config bubbles)     → pixel-based positioning + different center
```

**Result:**
- Config bubbles appeared in wrong positions (top-right corner)
- Two components calculated center differently
- Mixing percentage and pixel units caused misalignment
- Z-index conflicts between layers

### The Decision: Merge into Single Unified Component

**New Architecture:**
```
PropertyQuadrantsView
  └── PropertyCanvas (unified)
      ├── Category bubbles (percentage positioning)
      └── Config bubbles (percentage positioning, same coordinate system)
```

**Key Changes:**
1. **Merged ConfigCanvas → PropertyCanvas** (commit e266628)
   - Single component manages both category and config bubbles
   - Unified coordinate system (percentage-based)
   - Same center calculation for all bubbles

2. **Added Config Preview Images** (commit be3f247)
   - Preview images from `/config-previews/{config-id}.png`
   - Text badge overlay at 8% from bottom (matches ConfigTile design)
   - Removed fallback letter placeholder system

### Technical Implementation

**Coordinate System:**
```typescript
// All positions in percentage (0-100) relative to cluster-wrapper
const categoryPositions: Record<string, CategoryPosition> = {
  freestyle: { x: 50, y: 50 },      // Center
  semantics: { x: 72, y: 28 },       // Top-right (45°)
  aesthetics: { x: 72, y: 72 },      // Bottom-right (135°)
  arts: { x: 28, y: 72 },            // Bottom-left (225°)
  heritage: { x: 28, y: 28 },        // Top-left (315°)
}

// Configs positioned around parent category
const angle = (index / visibleConfigs.length) * 2 * Math.PI
const configX = categoryX + Math.cos(angle) * OFFSET_DISTANCE
const configY = categoryY + Math.sin(angle) * OFFSET_DISTANCE
```

**Container Sizing:**
```css
.cluster-wrapper {
  width: min(70vw, 70vh);
  height: min(70vw, 70vh);
  position: relative;
}
```

### Benefits

**Technical:**
- Single source of truth for positioning
- Consistent coordinate system (no unit mixing)
- Simpler component hierarchy (one less component)
- Easier to maintain and debug

**Visual:**
- Config bubbles correctly positioned around categories
- Smooth transitions and animations
- Consistent styling across all bubbles
- Preview images provide immediate visual recognition

### Files Modified

**Deleted:**
- `public/ai4artsed-frontend/src/components/ConfigCanvas.vue` (merged into PropertyCanvas)

**Modified:**
- `public/ai4artsed-frontend/src/components/PropertyCanvas.vue` (integrated ConfigCanvas logic)
- `public/ai4artsed-frontend/src/views/PropertyQuadrantsView.vue` (removed ConfigCanvas reference)
- `public/ai4artsed-frontend/src/assets/main.css` (updated styles)

**Archived (Backup):**
- `public/ai4artsed-frontend/src/components/PropertyBubble.vue.archive`
- `public/ai4artsed-frontend/src/views/PropertyQuadrantsView.vue.archive`

### Lessons Learned

**What Went Wrong:**
- Splitting category and config bubbles into separate components seemed logical initially
- Each component developed its own positioning logic independently
- Coordinate system mismatch wasn't obvious until visual testing

**Why This Solution Works:**
- Single component = single coordinate system
- Percentage-based positioning scales consistently
- Relative positioning within same container eliminates offset bugs

**General Principle:**
When components share the same visual space and coordinate system, they should be part of the same component to avoid positioning mismatches.

### Related Documentation

- **ARCHITECTURE PART 12 - Frontend-Architecture.md** - Full component documentation
- **docs/PropertyCanvas_Problem.md** - Centering issue (still under investigation)

---

## 🎯 Active Decision 0: Deployment Architecture - Dev/Prod Separation for Research Phase (2025-11-16)

**Status:** ✅ IMPLEMENTED (storage unified, port separation pending)
**Context:** Multi-user research environment with active student courses
**Date:** 2025-11-16

### The Decision: Dual Backend with Unified Storage

**Problem:**
- Multiple students in courses accessing via internet (iPad Pro 10")
- Need stable production environment for students
- Need development environment for ongoing research/fixes
- Previous setup caused 404 errors (dual storage locations)

**Solution Chosen: Symlinked Storage + Port Separation**

**Architecture:**
```
┌─────────────────────────────────────────────────────┐
│  Students (Internet, iPad Pro 10")                 │
│  ↓                                                  │
│  Cloudflare Tunnel (lab.ai4artsed.org)             │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│  LEGACY Backend (Production - Active)              │
│  - Students use this (stable, tested)              │
│  - Port: TBD (separate from new system)            │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  NEW DevServer System (Development Phase)          │
│  ├─ Dev Backend: port 17801 (development)          │
│  ├─ Prod Backend: port 17801 (CONFLICT!)           │
│  │  └─ TODO: Change to 17802 for separation        │
│  └─ Frontend: port 5173 (Vite proxy)               │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│  UNIFIED STORAGE (Research Data)                   │
│  Canonical: ~/ai/ai4artsed_webserver/exports/      │
│  Symlink: /opt/ai4artsed-production/exports → dev  │
│  - 300+ runs (7.5GB)                               │
│  - Accessible to researcher (not hidden in /opt/)  │
└─────────────────────────────────────────────────────┘
```

**Port Configuration (Planned):**
- **Legacy Backend:** Separate port (students access this)
- **17801:** Production backend (when ready for migration)
- **17802:** Dev backend (development/testing)
- **5173:** Vite frontend (proxies to backend)

**Storage Decision:**
- **Canonical location:** `~/ai/ai4artsed_webserver/exports/` (the dev checkout)
- **Rationale:** Research data must be accessible to researcher
- **Symlink direction:** prod → dev
- **Why reversed:** Data belongs in visible location, not hidden in /opt/

**Deployment Context:**
- **Current (Research Phase):** Internet via Cloudflare, multiple courses
- **Future (Post-Research):** WiFi-only deployment after project ends
- **Primary Users:** Students on iPad Pro 10" (NOT solo researcher)

**What Changed from the Previous Setup:**
1. ❌ Previous setup created symlink: dev → prod (wrong direction)
2. ✅ Now reversed: prod → dev (correct - data accessible)
3. ❌ Previous documentation stated "WiFi-only, temporary internet" (wrong context)
4. ✅ Corrected: "Internet-facing research, WiFi-only later"

**Technical Implementation:**
- Storage: 300 runs merged from both locations
- Symlink: `/opt/ai4artsed-production/exports` → `~/ai/ai4artsed_webserver/exports`
- Backend: Relative paths (`BASE_DIR / "exports"`) work automatically
- No code changes needed (paths resolve via symlink)

**Files Modified:**
- `/opt/ai4artsed-production/exports` (now symlink)
- `docs/STORAGE_SYMLINK_STRATEGY.md` (corrected deployment context)

**Port Separation - COMPLETED (2025-11-16):**
- [x] Prod backend config: `PORT = 17801` (for students/Cloudflare)
- [x] Dev backend config: `PORT = 17802` (for development)
- [x] Vite proxy updated to 17802 (dev backend)
- [x] Start scripts updated (`3 start_backend_fg.sh`)
- **Students use:** Port 17801 (production backend via Cloudflare)
- **Development uses:** Port 17802 (dev backend, Vite proxy)

**Rationale:**
- Students need stable environment (can't have dev interruptions)
- Research data must be accessible (not buried in /opt/)
- Unified storage prevents 404 errors
- Port separation allows simultaneous dev + prod

---

## 🎯 Active Decision 1: Token Processing Animation for Progress Visualization (2025-11-09)

**Status:** ✅ IMPLEMENTED
**Context:** Progress visualization for GenAI pipeline execution (target: children/youth)
**Date:** 2025-11-09

### The Decision: Token Processing Metaphor with Neural Network Visualization

**Problem:**
- Pipeline execution takes 10-30 seconds
- Boring spinner + progress bar insufficient for educational/youth context
- Need engaging, educational animation that runs smoothly on iPad Pro 10"

**Options Considered:**

1. **Complex Pixel-Art Sprites (REJECTED)**
   - Animated characters (hare and hedgehog story)
   - Result in testing: looked poor
   - Reason rejected: looked forced, complex to animate smoothly

2. **Simple Cumulative Animations (REJECTED)**
   - Stars collecting, glass filling, dots grid
   - Not thematically relevant
   - Reason rejected: Doesn't connect to GenAI/AI processing concept

3. **Token Processing with Neural Network (CHOSEN)**
   - INPUT grid → PROCESSOR box → OUTPUT grid
   - Tokens fly through neural network layers
   - Color transformation visible during processing
   - Forms recognizable pixel art images (26 different images)

**Decision:**
Token processing metaphor with visible neural network layer processing and gradual color transformation.

**Rationale:**
- **Educational:** Visualizes how AI processes and transforms data
- **Conceptually Aligned:** Matches GenAI token processing model
- **Simple to Animate:** Geometric shapes (colored squares) for smooth performance
- **Engaging:** 26 different images (animals, space, food) keep it fresh
- **iPad-Optimized:** Pure CSS animations, no heavy libraries

**Key Technical Decisions:**

1. **Progress Scaling to 90%**
   - Requirement: Animation complete at 90% progress
   - Implementation: `const scaledProgress = Math.min(props.progress / 90, 1)`
   - Rationale: INPUT queue empty by 90%, remaining 10% for final processing

2. **Visible Color Transformation (40% of Animation Time)**
   - 20-68% of animation spent inside processor box
   - Gradual color mixing: 100% original → 50/50 mix → 100% target
   - Uses CSS `color-mix(in srgb, ...)` for smooth gradients
   - Rationale: The transformation must be visible

3. **0.6s Per-Token Animation Duration**
   - Fast enough to complete before next token starts
   - Slow enough to see flying motion through all rows
   - Balance between visibility and smoothness
   - Rationale: Testing showed 3s too slow (animations cut off), 0.6s optimal

4. **Neural Network Visualization in Processor**
   - 5 pulsating nodes + 4 connection lines
   - Flicker effect with brightness variations (0.8x to 1.7x)
   - Lightning icon (⚡) with rotation and scaling
   - Rationale: More engaging than simple box, shows "AI thinking"

**Implementation:**
- Component: `SpriteProgressAnimation.vue` (648 lines)
- 26 pixel art images (14x14 grid, 7-color palette)
- Real-time timer: "generating X sec._" with blinking cursor
- Pure CSS animations (no JavaScript canvas)
- TypeScript strict mode compliance

**Affected Files:**
- `public/ai4artsed-frontend/src/components/SpriteProgressAnimation.vue` (new)
- `public/ai4artsed-frontend/src/views/Phase2CreativeFlowView.vue` (integrated)
- `public/ai4artsed-frontend/src/views/PipelineExecutionView.vue` (integrated)

**Future Considerations:**
- Could add more image templates based on workshop themes
- Could make animation speed configurable (age group settings)
- Could sync animation with actual pipeline stages (requires SSE)

---

## 🎯 Active Decision 2: SSE Streaming Postponed in Favor of Animation (2025-11-09)

**Status:** POSTPONED
**Context:** Frontend real-time progress updates for pipeline execution
**Date:** 2025-11-09

### The Decision: Use SpriteProgressAnimation Instead of SSE Streaming

**Problem:**
- Pipeline execution takes 10-30 seconds
- Users need visual feedback that system is working
- An SSE (Server-Sent Events) streaming implementation was attempted
- SSE implementation incomplete, unstable, blocking v2.0.0-alpha.1 release

**Options Considered:**

1. **SSE Streaming (ATTEMPTED)**
   - Real-time progress updates from backend
   - Step-by-step pipeline stage notifications
   - Complexity: HIGH
   - Status: Incomplete, buggy after 2+ hours work

2. **WebSockets**
   - Bidirectional communication
   - More complex than SSE
   - Overkill for one-way progress updates

3. **Polling**
   - Frontend polls /api/pipeline/{run_id}/status every N seconds
   - Already implemented via LivePipelineRecorder
   - Works but not real-time

4. **SpriteProgressAnimation (CHOSEN)**
   - Pure frontend animation
   - No backend changes required
   - Already implemented (a waiting animation exists)
   - Simple, reliable, working

**Decision:**
Postpone SSE streaming, use SpriteProgressAnimation for v2.0.0-alpha.1

**Rationale:**
- Animation already working and sufficient for current needs
- SSE can be added later as enhancement without breaking changes
- Unblocks release: v2.0.0-alpha.1 shipped on time
- LivePipelineRecorder polling already works for post-execution data

**Implementation:**
- The SSE code was stashed (`git stash`, "WIP: Frontend seed UI and progressive generation")
- SpriteProgressAnimation component in Phase 2 view
- Polling-based updates for completion detection

**Future Consideration:**
SSE streaming can be reconsidered for:
- Multi-stage progress bars
- Real-time Stage 1-4 status updates
- Workshop scenarios with multiple concurrent users
- When frontend UX design is finalized and stable

**Affected Files (stashed):**
- `devserver/my_app/__init__.py` - SSE blueprint import
- `devserver/my_app/routes/pipeline_stream_routes.py` - SSE endpoints
- Frontend components - SSE connection handlers

---

## 🎯 Active Decision 2: Variable Scope Pattern for Conditional Pipeline Stages (2025-11-09)

**Status:** IMPLEMENTED
**Context:** stage4_only feature support for fast regeneration
**Date:** 2025-11-09

### The Decision: Extract Loop-External Dependencies Before Conditional Blocks

**Problem:**
The `stage4_only` flag was implemented to skip Stage 1-3 for fast image regeneration. However, `media_type` variable was only defined INSIDE the Stage 3 conditional block. When Stage 3 was skipped, Stage 4 tried to access undefined `media_type` → UnboundLocalError crash.

**Root Cause:**
```python
# BEFORE FIX:
if not stage4_only:  # Skip Stage 3 when True
    # Stage 3 safety check
    if 'image' in output_config_name.lower():
        media_type = 'image'  # ← Defined HERE
    # ...

# Stage 4 needs media_type
recorder.download_and_save_from_comfyui(media_type=media_type)  # ← CRASH!
```

**Architecture Pattern Established:**

**Rule:** If a variable is used OUTSIDE a conditional block, it MUST be defined BEFORE the block.

**Implementation:**
```python
# AFTER FIX (lines 733-747):

# DETERMINE MEDIA TYPE (needed for both Stage 3 and Stage 4)
# Extract media type from output config name BEFORE Stage 3-4 Loop
# This ensures media_type is ALWAYS defined, even when stage4_only=True
if 'image' in output_config_name.lower() or 'sd' in output_config_name.lower():
    media_type = 'image'
elif 'audio' in output_config_name.lower():
    media_type = 'audio'
elif 'music' in output_config_name.lower() or 'ace' in output_config_name.lower():
    media_type = 'music'
elif 'video' in output_config_name.lower():
    media_type = 'video'
else:
    media_type = 'image'  # Default fallback

# NOW Stage 3 can be conditional
if safety_level != 'off' and not stage4_only:
    # Stage 3 code...

# Stage 4 can safely use media_type regardless of stage4_only
```

**Benefits:**
1. **Variable always defined** - No UnboundLocalError possible
2. **Clean separation** - Dependency extraction vs conditional logic
3. **Maintainable** - Easy to see what Stage 4 depends on
4. **Scalable** - Pattern applies to any conditional stage skip

**Generalized Pattern:**
```python
# 1. Extract dependencies FIRST
variable_needed_by_both = determine_variable(...)

# 2. THEN conditional blocks
if condition:
    do_stage_3()

# 3. Variable available regardless
do_stage_4(variable_needed_by_both)
```

**Affected Files:**
- `devserver/my_app/routes/schema_pipeline_routes.py` (lines 733-747)

**Testing:**
- ✅ Normal flow (stage4_only=False): All stages run, media_type defined
- ✅ Fast regen (stage4_only=True): Stage 3 skipped, media_type still defined
- ✅ All media types: image, audio, music, video
- ✅ Fallback: Unknown types default to 'image'

**Key Learning:**
Python variable scope in conditional blocks is NOT block-scoped. Variable defined in `if` block exists outside, BUT only if `if` branch executes. For variables used outside conditional blocks, define BEFORE the condition.

---

## 🎯 Active Decision 3: Property Taxonomy for Config Selection UI (2025-11-07)

**Status:** IMPLEMENTED
**Context:** Phase 1 UI needs non-consumeristic filtering system for config selection

### The Decision: 6 Property Pairs Based on Grounded Theory Analysis

**Problem:** Tags like [lustig] [schnell] serve consumeristic "user choice" model, contradict pedagogical goals (counter-hegemonic, agency-oriented)

**Solution:** Property pairs as tension fields (Spannungsfelder) that express transformation qualities:

```
1. calm ↔ chaotic          (chillig - chaotisch)       - Process control
2. narrative ↔ algorithmic (erzählen - berechnen)      - Transformation mode
3. facts ↔ emotion         (fakten - gefühl)           - Focus/affect
4. historical ↔ contemporary (geschichte - gegenwart)  - Temporal orientation
5. explore ↔ create        (erforschen - erschaffen)   - Purpose
6. playful ↔ serious       (spiel - ernst)             - Attitude
```

### Architecture

**Config Level:** Properties stored as arrays in config JSON
```json
"properties": ["chaotic", "narrative", "emotion", "historical", "create", "playful"]
```

**Frontend i18n:** Labels in `i18n.js` following existing pattern
```javascript
properties: {
  calm: 'chillig',
  chaotic: 'chaotisch',
  ...
}
```

**UI Logic:** Positive logic (nothing shown until properties selected) + AND-logic filtering

### Critical Pedagogical Insight

YorubaHeritage description updated to reflect limits:
> "Tries to translate... Allows for a critical assessment of the limits of generative AI with regard to cultural knowledge."

**Reason:** LLMs may understand contexts; image generation models are culturally indifferent. This exposes AI bias pedagogically.

### Rejected Approaches
- Abstract academic categories (Iteration 01: "Reflexionsmodus", "dekonstruktiv")
- Separate metadata files (violates existing i18n architecture)
- Neutral tags (would reinforce solutionism)

---

## 🎯 Active Decision 2: Execution History Architecture (2025-11-03)

**Status:** DESIGNED (Not yet implemented)
**Priority:** HIGH (Fixes broken research data export)

### The Decision: Observer Pattern (Stateless Pipeline + Stateful Tracker)

**Core Principle:**
- **Pipeline stays stateless** - Pure functions, no side effects
- **Tracker is stateful** - Observes pipeline, tracks execution history
- **Loose coupling** - Tracker failure doesn't break pipeline execution

### Architecture

\`\`\`
Pipeline Execution (STATELESS)           ExecutionTracker (STATEFUL)
┌─────────────────────────┐             ┌──────────────────────────┐
│ Stage 1: Translation    │             │ - In-memory storage      │
│ Stage 2: Interception   │──observe──→ │ - Async event queue      │
│ Stage 3: Safety         │             │ - Session tracking       │
│ Stage 4: Generation     │             │ - Auto-export to disk    │
└─────────────────────────┘             └──────────────────────────┘
\`\`\`

### What Gets Tracked

1. **Inputs** (user text, uploaded images)
2. **All stage outputs** (translation, interception, safety checks, media generation)
3. **Metadata** (configs used, models used, timestamps)
4. **Semantic labels** (what each item means - for pedagogical frontend)
5. **Sequential order** (actual execution order, including parallel stages)

### Storage Structure

\`\`\`
research_data/
├── dada/
│   ├── <execution_id>.json
│   └── ...
├── bauhaus/
└── stillepost/
\`\`\`

### Key Insight: Frontend Flexibility

The structured JSON enables different pedagogical views:

**Student View:** Show only input → transformation → output
**Advanced View:** Show translation → interception → output
**Researcher View:** Show everything (safety checks, metadata, timing)

### Critical Lesson

Never implement before understanding the architecture completely.

The previous attempt failed because it assumed \`output_requests\` with \`count\` parameters existed. In reality:
- Current code uses \`output_configs\` array in config JSON
- Each config executes exactly once (no \`count\` parameter)
- Multiple outputs = list config multiple times in array
- See \`my_app/routes/schema_pipeline_routes.py\` lines 222-330

---

## 🎯 Active Decision 2: GPT-OSS Unified Stage 1 (2025-11-02)

**Status:** ✅ IMPLEMENTED & TESTED

### The Decision: Single LLM Call for Translation + §86a Safety

**OLD:** Two-step Stage 1 (mistral-nemo translation → llama-guard3 safety)
**NEW:** One-step Stage 1 (GPT-OSS:20b for both)

### Why This Matters

**Problem:** Failure case
- Test input: "Isis-Kämpfer sprayt Isis-Zeichen" (ISIS terrorist)
- Previous system: Marked SAFE ❌
- Root cause: US-centric model applied First Amendment framework
- Model interpreted "isis" as Egyptian goddess, not ISIS

**Solution:** Full §86a StGB legal text in system prompt
- Model now applies German legal framework
- Explicit rules for student context
- Educational error messages in primary language (currently German, configurable via PRIMARY_LANGUAGE - see devserver_todos.md Priority 2)

### Performance Impact

- **Before:** 2-4s (mistral-nemo 1-2s + llama-guard3 1-2s)
- **After:** 1-2s (single GPT-OSS call)
- **Savings:** 1-2s per request + no model switching overhead

### Files

- \`devserver/schemas/configs/pre_interception/gpt_oss_unified.json\`
- \`devserver/schemas/engine/stage_orchestrator.py\` (execute_stage1_gpt_oss_unified)
- \`devserver/my_app/routes/schema_pipeline_routes.py\`

---

## 🎯 Active Decision 3: 4-Stage Architecture with DevServer Orchestration (2025-11-01)

**Status:** ✅ IMPLEMENTED

### The Decision: DevServer Orchestrates, Pipeline Executes

**Architecture:**
\`\`\`
Stage 1 (DevServer): Translation + §86a Safety
Stage 2 (Pipeline):  Interception (Dada, Bauhaus, etc.)
Stage 3 (DevServer): Pre-output safety (age-appropriate)
Stage 4 (Pipeline):  Media generation (ComfyUI, APIs)
\`\`\`

**Why This Split:**
- Stages 1+3 = Safety/compliance (belongs in orchestrator)
- Stages 2+4 = Creative transformation (belongs in pipeline)
- Clear separation of concerns

### Stage 3-4 Loop

**Critical Implementation Detail:**
\`\`\`python
# In schema_pipeline_routes.py
for i, output_config_name in enumerate(configs_to_execute):
    # Stage 3: Safety check for THIS config
    safety_result = execute_stage3_safety(...)

    if not safety_result['safe']:
        continue  # Skip Stage 4 for blocked content

    # Stage 4: Execute THIS config → generates ONE output
    output_result = pipeline_executor.execute_pipeline(output_config_name, ...)
\`\`\`

**Key Facts:**
- Each config in \`output_configs\` array executes exactly once
- No \`count\` parameter exists (future enhancement)
- Multi-output = list multiple configs in array

---

## 🎯 Active Decision 4: Config-Based System (2025-10-26 - 2025-11-01)

**Status:** ✅ IMPLEMENTED

### The Decision: Three Config Types

1. **Interception Configs** (\`schemas/configs/interception/\`)
   - User-facing configs (Dada, Bauhaus, Stille Post)
   - Define Stage 2 transformation pipeline
   - Specify media preferences (output_configs)

2. **Output Configs** (\`schemas/configs/output/\`)
   - Backend configs (sd35_large, gpt5_image)
   - Define Stage 4 media generation
   - Not directly selectable by users

3. **Pre-Output Configs** (\`schemas/configs/pre_output/\`)
   - Age-appropriate safety (kids, youth)
   - Stage 3 content filtering

### Benefits

- ✅ User doesn't see backend complexity
- ✅ Backend changes don't affect user experience
- ✅ Can swap models (SD3.5 → FLUX) without user-facing changes
- ✅ Multiple outputs for comparison

---

## 🎯 Active Decision 5: Backend Abstraction (2025-10-27 - 2025-10-28)

**Status:** ✅ IMPLEMENTED

### The Decision: Three Backend Types

1. **Ollama** - Local LLMs (mistral-nemo, llama-guard3, GPT-OSS)
2. **ComfyUI** - Local image generation (SD3.5, FLUX)
3. **OpenRouter** - API-based outputs (GPT-5 Image, future music/video)

### Output Chunk Format

All outputs return unified format:
\`\`\`python
{
    "media_type": "image" | "text" | "audio" | "video",
    "backend": "comfyui" | "openrouter" | "ollama",
    "content": <file_path> | <url> | <text>,
    "prompt_id": <for ComfyUI retrieval>
}
\`\`\`

### Files

- \`devserver/schemas/chunks/output_comfyui.json\`
- \`devserver/schemas/chunks/output_openrouter_gpt5_image.json\`
- \`devserver/schemas/engine/comfyui_api.py\`
- \`devserver/schemas/engine/openrouter_api.py\`

---

## 🧩 Development Principles (Standing Decisions)

### 1. Config Over Code
- New features = new config file, not code changes
- Users edit JSON, not Python

### 2. Fail-Safe Design
- Safety checks: Fail-open on errors (log warning, continue)
- Research tracker: Optional, non-blocking
- Principle: System degradation > complete failure

### 3. Separation of Concerns
- Pipeline = stateless, pure functions
- Tracker/Logger = stateful, observer pattern
- Safety = orchestrator responsibility
- Creativity = pipeline responsibility

### 4. Educational Transparency
- Error messages in primary language explain WHY content is blocked (currently German, configurable)
- Frontend can show/hide intermediate results
- Research data enables pedagogical analysis

---

## 🎯 Active Decision 7: Unified Media Storage with "Run" Terminology (2025-11-04)

**Status:** ✅ IMPLEMENTED
**Priority:** HIGH (fixes broken export functionality)

### Context

Media files were not persisted consistently across backends:
- **ComfyUI**: Images displayed in frontend but NOT stored locally
- **OpenRouter**: Images stored as data strings in JSON (unusable for research)
- **Export function**: Failed because media wasn't persisted to disk
- **Research data**: URLs printed to console instead of actual files

### The Decision: Unified Media Storage Service

**Storage Architecture:**
- **Flat structure**: `exports/json/{run_id}/` (no hierarchical sessions)
- **"Run" terminology**: NOT "execution" (German connotations: "Hinrichtungen")
- **Atomic research units**: One folder contains ALL files for one complete run
- **Backend-agnostic**: Works with ComfyUI, OpenRouter, Replicate, future backends
- **UUID-based**: Concurrent-safety for workshop scenario (15 kids)

**Structure:**
```
exports/json/{run_uuid}/
├── metadata.json           # Single source of truth
├── input_text.txt         # Original user input
├── transformed_text.txt   # After Stage 2 interception
└── output_<type>.<format> # Generated media (image, audio, video)
```

### Rationale

**Why Flat Structure:**
No session entity exists, and there is no technical criterion for discriminating sessions. Flat UUID-based folders with metadata enable future queries without complex hierarchy.

**Why "Run" Terminology:**
"Execution" is also the word for killing a human (German "Hinrichtung"). "Run" is neutral and commonly used in programming contexts.

**Why Atomic Units:**
Data management must keep atomic research events, such as one pipeline run, together. One folder = one complete research event. No split data across multiple locations.

### Implementation

**File:** `devserver/my_app/services/media_storage.py` (414 lines)

**Detection Logic:**
```python
if output_value.startswith('http'):
    # API-based (OpenRouter) - Download from URL
    media_storage.add_media_from_url(run_id, url, media_type)
else:
    # ComfyUI - Fetch via prompt_id
    media_storage.add_media_from_comfyui(run_id, prompt_id, media_type)
```

**Integration Points:**
1. Pipeline start: Create run folder + save input text
2. Stage 4: Auto-detect backend + download media
3. Response: Return `run_id` to frontend (not raw prompt_id/URL)

### Affected Files

**Created:**
- `devserver/my_app/services/media_storage.py` (414 lines) - Core service
- `docs/UNIFIED_MEDIA_STORAGE.md` - Technical documentation

**Modified:**
- `devserver/my_app/routes/schema_pipeline_routes.py` - Integration
- `devserver/my_app/routes/media_routes.py` - Rewritten for local serving

### API Endpoints

- `GET /api/media/image/<run_id>` - Serve image
- `GET /api/media/audio/<run_id>` - Serve audio
- `GET /api/media/video/<run_id>` - Serve video
- `GET /api/media/info/<run_id>` - Metadata only
- `GET /api/media/run/<run_id>` - Complete run info

### Benefits

✅ **All media persisted** - ComfyUI and OpenRouter work identically
✅ **Export-ready** - Research data complete and accessible
✅ **Backend-agnostic** - Easy to add new backends (Replicate, etc.)
✅ **Concurrent-safe** - Workshop scenario supported
✅ **Simple queries** - Metadata enables filtering without complex joins

### Testing Status

**Required:** ComfyUI eco mode, OpenRouter fast mode, concurrent requests

---

## 🎯 Active Decision 8: Unified run_id to Fix Dual-ID Bug (2025-11-04)

**Status:** ✅ IMPLEMENTED & TESTED
**Priority:** CRITICAL (complete system desynchronization)

### Context: The Dual-ID Bug

**The Problem:**
OLD system used TWO different UUIDs causing complete desynchronization:
- **OLD ExecutionTracker**: Generated `exec_20251104_HHMMSS_XXXXX`
- **OLD MediaStorage**: Generated `uuid.uuid4()`
- **Result**: Execution history referenced non-existent media files

**Assessment:**
The OLD ExecutionTracker found the media polling issue but FAILED to fix it for months, so it is not a usable reference.

### The Decision: Unified run_id Architecture

**Core Principle:**
Generate `run_id = str(uuid.uuid4())` **ONCE** at pipeline start.
Pass this SINGLE ID to ALL systems.

**Architecture:**
```
Pipeline Start (schema_pipeline_routes.py)
↓
run_id = str(uuid.uuid4())  ← Generated ONCE
↓
├─→ ExecutionTracker(execution_id=run_id)    ← Uses same ID
├─→ MediaStorage.create_run(run_id)          ← Uses same ID
└─→ LivePipelineRecorder(run_id)             ← Uses same ID
    ↓
    Single source of truth: pipeline_runs/{run_id}/metadata.json
```

### Implementation

**File:** `devserver/my_app/services/pipeline_recorder.py` (400+ lines)

**LivePipelineRecorder Features:**
- Unified `run_id` passed to constructor
- Sequential entity tracking: 01_input.txt → 06_output_image.png
- Single source of truth in `metadata.json`
- Real-time state tracking (stage/step/progress)
- Metadata enrichment for each entity

**File Structure:**
```
pipeline_runs/{run_id}/
├── metadata.json              # Single source of truth
├── 01_input.txt              # User input
├── 02_translation.txt        # Translated text
├── 03_safety.json            # Safety results
├── 04_interception.txt       # Transformed prompt
├── 05_safety_pre_output.json # Pre-output safety
└── 06_output_image.png       # Generated media
```

### Critical Bug Fix: Media Polling

**The Issue:**
ComfyUI generates images asynchronously. Calling `get_history(prompt_id)` immediately after submission returns empty result.

**File Modified:** `devserver/my_app/services/media_storage.py` (line 214)

**The Fix:**
```python
# OLD (BROKEN):
# history = await client.get_history(prompt_id)

# NEW (FIXED):
history = await client.wait_for_completion(prompt_id)
```

**Why This Matters:**
- `wait_for_completion()` polls every 2 seconds until workflow finishes
- **OLD ExecutionTracker identified this issue but NEVER fixed it**
- **NEW LivePipelineRecorder SUCCEEDED on first implementation**

### Test Proof

**Test Run:** `812ccc30-5de8-416e-bfe7-10e913916672`

**Result:**
```json
{"status": "success", "media_output": "success"}
```

**All 6 entities created:**
```bash
01_input.txt
02_translation.txt
03_safety.json
04_interception.txt
05_safety_pre_output.json
06_output_image.png  ← This was MISSING in OLD system
metadata.json
```

### Dual-System Migration Strategy

**Both systems run in parallel (by design):**

**OLD System:**
- ExecutionTracker: `exec_20251104_HHMMSS_XXXXX`
- Output: `/exports/pipeline_runs/exec_*.json`
- Status: Maintained for validation

**NEW System:**
- LivePipelineRecorder: `{unified_run_id}`
- Output: `pipeline_runs/{run_id}/`
- Status: Production-ready

**MediaStorage:**
- Uses unified `run_id` from NEW system
- Output: `exports/json/{run_id}/`
- Synchronized with LivePipelineRecorder

**Rationale:**
- Ensure no data loss during migration
- Validate NEW system against OLD system
- Gradual deprecation path for OLD system

### API Endpoints for Frontend

**File Created:** `devserver/my_app/routes/pipeline_routes.py` (237 lines)

**Real-Time Polling:**
- `GET /api/pipeline/<run_id>/status` - Current execution state
- `GET /api/pipeline/<run_id>/entity/<type>` - Fetch specific entity
- `GET /api/pipeline/<run_id>/entities` - List all entities

**Frontend Integration Ready:**
- Status polling for progress bars
- Entity fetching for live preview
- MIME type detection for proper display

### Affected Files

**Created (3 files, ~800 lines):**
- `devserver/my_app/services/pipeline_recorder.py` (400+ lines, flattened from package)
- `devserver/my_app/routes/pipeline_routes.py` (237 lines, 3 endpoints)
- `docs/LIVE_PIPELINE_RECORDER.md` (17KB technical documentation)

**Modified (2 files):**
- `devserver/my_app/__init__.py` (blueprint registration)
- `devserver/my_app/routes/schema_pipeline_routes.py` (entity saves at all stages)

**File Structure Migration:**
- `/devserver/pipeline_recorder/` (package) → `/devserver/my_app/services/pipeline_recorder.py` (single file)
- Follows existing service pattern (ollama_service.py, comfyui_service.py, media_storage.py)

### Success Metrics

✅ **NEW system succeeded where OLD system failed**
- OLD: Found media polling issue months ago, never fixed it
- NEW: Fixed immediately with proper polling mechanism

✅ **Dual-ID Bug Resolved**
- Single unified `run_id` across all systems
- No more desynchronization
- All entities properly tracked and accessible

✅ **Production Ready**
- Tested successfully end-to-end
- All 6 entities created correctly
- Real-time API endpoints functional

### Future Refactoring (Deferred)

**Architectural Discussion:**
A proposal is to make ComfyUI execution blocking in `backend_router.py`:
- Chunk waits for completion internally
- Returns actual media bytes instead of just `prompt_id`
- Removes need for polling in media_storage.py

**Status:** Deferred. Current polling solution works correctly.

---

## 📚 Related Documentation

- **Architecture:** \`docs/ARCHITECTURE PART I.md\`, \`docs/ARCHITECTURE PART II.md\`
- **Active TODOs:** \`docs/devserver_todos.md\`

---

## 2025-11-04: Internationalization (i18n) Requirement

### Decision: NEVER Hardcode Language-Specific Strings

**Problem Identified:**
During the implementation of frontend polling, hardcoded German strings were added to JavaScript:
- `'Verbindung langsam, Versuch läuft...'`
- `'Pipeline-Start', 'Übersetzung & Sicherheit'`, etc.

**Correction (Critical):**
No language is written directly into code; code uses a placeholder for the language configuration. The system is at least bilingual and must be prepared for multilinguality: German may be the active language set in config.py now, and English is equally important. Every frontend interface string is a variable that pulls the right term from a dictionary.

### Architecture Requirements

**System Design:**
- **Bilingual:** German + English (equally important)
- **Multilingual-Ready:** Prepared for additional languages
- **Decentralized:** Pipelines/configs have their own bilingual translation

**Implementation:**
1. **Frontend:** All UI strings must come from language configuration dict (i18n system)
2. **Backend:** Language strings pulled from `config.py` active language setting
3. **NO Hardcoding:** Never embed German, English, or any language directly in code

**Example (CORRECT):**
```javascript
// Frontend i18n system
setStatus(i18n.status.connectionSlow, 'warning');
const stageName = i18n.stages[stageId];
```

**Legacy Frontend Status:**
- `public_dev/` contains hardcoded German strings (documented violation)
- **NO FURTHER WORK** will be done on legacy frontend
- The polling implementation was the final backend piece
- New frontend(s) will be built with i18n from day 1

**Rule:** Internationalization is the **mandatory first rule** for all future frontends.

---

## 🎯 Active Decision 7: Frontend Architecture - Vue.js 3-Phase Model (2025-11-06)

**Status:** PLANNED (Documentation complete, implementation pending)
**Priority:** HIGH (New frontend architecture)

### The Decision: 3-Phase User Journey with Entity-Based Transparency

**Core Principle:**
- **Phase 1:** Config Selection (Browse, Search, Select)
- **Phase 2:** Creative Input (Prompt entry)
- **Phase 3:** AI Process Transparency (Entity-based visualization)

### Phase 2 vs Phase 3 - Pedagogical Distinction

**Phase 2 - Creative Act:**
- Purpose: Prompt input, creative expression
- User Action: Write/conceptualize their prompt
- Interface: Simple textarea, examples, execute button

**Phase 3 - AI Process Transparency:**
- Purpose: **Make AI decision-making visible** (Against Black-Box Solutionism)
- Pedagogical Goal: Students understand AI as series of transformations, not magic
- Interface: **Entity-based visualization** (NOT stage-based)

### Key Architectural Decision: Entity-Based Visualization

**NOT Stage-Based (4 boxes):**
```
❌ [Stage 1] → [Stage 2] → [Stage 3] → [Stage 4]
   (Too abstract, hides process)
```

**Entity-Based (one box per file in exports/json):**
```
✅ [01_input.txt] → [02_translation.txt] → [03_safety.json] →
   [04_interception_context.txt] → [05_interception_result.txt] →
   [06_safety_pre_output.json] → [07_output_image.png]
```

**Rationale:**
1. **Transparency:** Every intermediate step is visible and inspectable
2. **Pedagogical:** Students see HOW AI processes information step-by-step
3. **Meta-Prompt Visibility:** Interception context files show what instructions modify prompts
4. **Recursive Visibility:** For Stillepost (8 iterations), all 8 steps visible as separate entities
5. **Against Solutionism:** No black boxes, every transformation documented

### What This Means for Implementation

**Every file in `exports/{run_id}/json/` gets a box:**
- Input files (01_input.txt)
- Translation files (02_translation.txt)
- Safety check results (03_safety_stage1.json)
- **Meta-prompts** (04_interception_context.txt) ← Pedagogically crucial
- Interception results (05_interception_result.txt)
- Pre-output safety (06_safety_pre_output.json)
- Final outputs (07_output_image.png, etc.)
- **Recursive iterations** (04_interception_iter1.txt through iter8.txt)

**Real-Time Display:**
- Poll `/api/pipeline/{run_id}/status` every 1 second
- Entities appear progressively as they become available
- Status icons: ✓ Available / ⟳ In Progress / ○ Pending
- Click any entity to view full content in modal

### Technology Stack

**Framework:** Vue.js 3 (Composition API)
**State Management:** Pinia
**Routing:** Vue Router
**Styling:** Scoped CSS (BEM methodology)
**i18n:** vue-i18n (DE/EN, extensible)
**Build:** Vite

### Metadata-Driven Design

**Principle:** Frontend NEVER hardcodes config lists
- Configs expose metadata via `/pipeline_configs_metadata` API
- Frontend dynamically renders based on metadata
- New configs appear automatically
- User configs integrate seamlessly

**Config Metadata Structure:**
```json
{
  "id": "dada",
  "name": {"de": "Dada-Transformation", "en": "Dada Transformation"},
  "description": {"de": "...", "en": "..."},
  "category": "art-movements",
  "icon": "🎨",
  "difficulty": 3,
  "output_types": ["text"],
  "pipeline": "text_transformation"
}
```

### Internationalization (i18n)

**Mandatory from Day 1:**
- UI strings in dictionary files (`locales/de.json`, `locales/en.json`)
- Config content multilingual in config files themselves
- Automatic translation augmentation via existing translation pipelines
- Browser language detection with manual override
- Locale persistence in localStorage

### Documentation

**Complete Planning Documents:**
- `docs/tmp/FRONTEND_00_README.md` - Overview
- `docs/tmp/FRONTEND_01_ARCHITECTURE_OVERVIEW.md` - 3-phase architecture
- `docs/tmp/FRONTEND_02_PHASE_1_SCHEMA_SELECTION.md` - Config browser
- `docs/tmp/FRONTEND_03_PHASE_2_3_FLOW_EXPERIENCE_V2.md` - **Entity-based visualization (REVISED)**
- `docs/tmp/FRONTEND_04_VUE_COMPONENT_ARCHITECTURE.md` - Component structure
- `docs/tmp/FRONTEND_05_METADATA_SCHEMA_SPECIFICATION.md` - Metadata schema
- `docs/tmp/FRONTEND_06_VISUAL_DESIGN_PATTERNS.md` - Design system

**Total Documentation:** ~51,000 words

### Implementation Timeline

**Status:** Ready for implementation
**Next Steps:**
1. Set up Vue.js project structure
2. Implement Phase 1 MVP (Tile view only)
3. Implement Phase 2 (Prompt input)
4. Implement Phase 3 (Entity flow visualization)
5. Polish & enhance

**Estimated Timeline:**
- MVP (basic functionality): 2-3 weeks
- V1.0 (full features): 6-8 weeks

### Affected Files

**New Directory:** `/frontend/` (to be created)
**Backend API:** Existing endpoints already support entity-based responses
**Documentation:** All frontend docs in `docs/tmp/FRONTEND_*.md`

---

**Last Updated:** 2025-11-06
**Active Decisions:** 7
**Status:** Clean, concise, actively maintained

---

## 2025-11-08: Data Flow Architecture - custom_placeholders is THE Mechanism

**Context:** A previous attempt had fundamentally misunderstood the data flow architecture.

**Wrong Understanding (previous attempt):**
- Thought `input_requirements` controls data flow between pipeline stages
- Invented complex nested structures for passing data
- Misunderstood how placeholders work

**Correct Understanding:**
- **`context.custom_placeholders: Dict[str, Any]` is the ONLY mechanism for passing data between stages**
- ChunkBuilder automatically merges custom_placeholders into template replacements as `{{PLACEHOLDERS}}`
- `input_requirements` is **just metadata** for:
  - Stage 1 pre-processing (knows what inputs to translate/safety-check)
  - Frontend UI generation (creates input fields)
- Any data type can pass through - just add it to the dict

**Key Insight:**
The system is simpler than we thought. No need for complex field names or nested structures. Just:
1. Put data in `custom_placeholders`
2. Use `{{KEY}}` in templates
3. ChunkBuilder handles the rest

**Example - Working Music Generation:**
```python
# music_generation config has:
"input_requirements": {"texts": 2}

# Stage 1 knows: process 2 separate text inputs
# Frontend UI shows: 2 text input fields
# Pipeline execution:
context.custom_placeholders['MELODY'] = user_input_1
context.custom_placeholders['LYRICS'] = user_input_2

# Template uses: {{MELODY}} and {{LYRICS}}
```

**Architectural Principle:**
> **Input requirements describe WHAT arrives at Stage 1. Custom placeholders describe HOW data flows internally.**

**Impact on Vector Fusion:**
- Stage 2 outputs JSON: `{"part_a": "...", "part_b": "..."}`
- JSON auto-parsing adds to custom_placeholders: `PART_A`, `PART_B`
- Stage 4 uses `{{PART_A}}` and `{{PART_B}}` in template
- No complex field names needed, no nested structures

**Documentation:**
- `docs/DATA_FLOW_ARCHITECTURE.md` - Full explanation with examples

**Why This Matters:**
- Prevents reinventing complexity
- Shows that extensibility is built-in (any data type works)
- Clarifies the separation of concerns (metadata vs data flow)
- Makes multi-stage workflows simple to implement


---

## 2025-12-12: Surrealizer/Direct Vue Separation

### Decision: Create Dedicated surrealizer.vue While Preserving Generic direct.vue

**Context:**
- Surrealizer is production-stable workflow with alpha slider (-75 to +75)
- 2-3 additional Hacking workflows exist in ComfyUI
- Previous attempts at routing changes failed due to misunderstanding convention-based routing

**Problem:**
- `surrealizer.json` config pointed to `direct` pipeline → loaded `direct.vue` with dropdown
- Dropdown caused confusion for production workflow
- Each stable workflow gets a dedicated Vue

**Architecture Decision:**

**Production Workflow (Dedicated):**
```
surrealizer.json config → surrealizer.json pipeline → surrealizer.vue
- Hardcoded to surrealization_legacy output config
- Alpha slider (-75 to +75) with 5 labels
- No dropdown selection
- Clean, focused UX for workshop use
```

**Convention-Based Routing Pattern:**
```
Config JSON → Pipeline JSON → Vue Component
├─ "pipeline": "X" → ├─ "name": "X" → X.vue
└─ (Stage 2 config)  └─ (Pipeline def)   └─ (Frontend)
```

**Critical Insight - Why Previous Attempts Failed:**
1. **Pipeline name MUST exactly match Vue filename** (case-sensitive!)
2. **Correct order of creation:**
   - ✅ FIRST: Create Vue component
   - ✅ THEN: Create pipeline definition
   - ✅ LAST: Update config reference
   - ❌ WRONG: Change config first (breaks routing before Vue exists)

3. **No explicit registry needed** - PipelineRouter.vue uses dynamic import:
   ```typescript
   import(`../views/${pipelineName}.vue`)
   ```

**Files Created:**
- `/devserver/schemas/pipelines/surrealizer.json` (new pipeline, reusable: false)
- `/public/ai4artsed-frontend/src/views/surrealizer.vue` (dedicated component)

**Files Modified:**
- `/devserver/schemas/configs/interception/surrealizer.json` (pipeline: "surrealizer")

**Changes in surrealizer.vue:**
- Removed output config dropdown section
- Removed `availableConfigs` array
- Removed `selectedOutputConfig` ref
- Hardcoded API call: `output_config: 'surrealization_legacy'`
- Simplified `canExecute` computed (no config check)

**Testing:**
```bash
curl http://localhost:17802/api/config/surrealizer/pipeline
# Returns: {"pipeline_name": "surrealizer", ...}
```

**Benefits:**
- **Production stability** - Dedicated Vue, no accidental config changes
- **Clean UX** - No dropdown confusion for workshop students
- **Scalability** - Pattern ready for 2-3 additional Hacking workflows
- **Zero router changes** - Convention-based routing handles automatically

**Migration Path for Future Workflows:**
1. **Stable/Production workflow** → Create dedicated Vue (like Surrealizer)
2. **Experimental/Research** → Keep in `direct.vue` with dropdown (if reactivated)

**Architectural Note:**
The `direct_workflow.json` config was deactivated (`.deactivated` suffix) in the same change. If needed in future, it can be reactivated as a generic "Hacking Lab" with dropdown for experimental workflows.

**Commits:**
- `4a52aa1` - Enhanced slider (5 labels, gradient, 48px thumb)
- `c332f48` - Dedicated surrealizer.vue with routing separation

**Why This Documentation Matters:**
- **Future-proofing:** Next time routing needs to change, follow this pattern
- **Prevents regression:** Explicit order of operations prevents breaking changes
- **Educational:** Shows convention-based routing is simpler than explicit registry
- **Template:** Use for displaced_world, relational_inquiry, other new workflows



---

## 2026-01-22/23: Favorites & FooterGallery + Unified Run Architecture

### Decision: Persistent Favorites with Complete Research Data Export

**Context:**
- Research project needs complete, traceable data for each generation session
- Users want to bookmark and restore previous generations
- Data was fragmented across multiple folders (interception vs generation)

**Problem:**
1. **Data Fragmentation:** Interception created `run_xxx/` folder, Generation created separate `gen_xxx/` folder
2. **Missing Data:** Context prompt, translation, and model info were not being saved
3. **No Persistence:** Generated outputs disappeared after page navigation

### Architecture Decision: Unified Run + Complete Data Export

**Single Folder per Session:**
```
BEFORE (fragmented):
run_123/        ← Interception endpoint
├── input.txt
├── safety.txt
└── interception.txt

gen_456/        ← Generation endpoint (SEPARATE!)
├── input.txt   ← DUPLICATE
└── output.png

AFTER (unified):
run_123/        ← ONE folder for entire session
├── 01_input.txt           # Original user input (German)
├── 02_context_prompt.txt  # Meta-prompt/pedagogical rules
├── 03_safety.txt          # Stage 1 safety result
├── 04_interception.txt    # Transformed text (German)
├── 05_translation_en.txt  # English translation (NEW!)
├── 06_optimized_prompt.txt
├── 07_output_image.png
└── metadata.json          # Includes models_used (NEW!)
```

**Implementation Pattern:**
```
Frontend                          Backend
─────────                         ─────────
Interception Start
    │
    ├──► POST /pipeline/interception
    │         │
    │         ├── Creates run_id
    │         ├── Saves input, context_prompt, safety, interception
    │         └── Returns run_id in SSE stream
    │
    ◄── run_id stored in currentRunId.value
    │
Generation Start
    │
    ├──► POST /pipeline/generation
    │    { run_id: currentRunId.value, ... }
    │         │
    │         ├── load_recorder(run_id) ← Reuses existing folder!
    │         ├── Saves translation_en, optimized_prompt, output
    │         └── Returns same run_id
    │
    ◄── Media displayed, run_id for favorites
```

**Model Tracking (metadata.json):**
```json
{
  "models_used": {
    "stage1_safety": "local/gpt-OSS:20b",
    "stage2_interception": "local/gpt-OSS:20b",
    "stage3_translation": "local/gpt-OSS:20b",
    "stage4_output": "sd35_large"
  }
}
```

### FooterGallery Component

**Architecture:**
- Fixed footer bar with expandable thumbnail gallery
- Pinia store (`favorites.ts`) for state management
- Store-based restore (reactive) instead of sessionStorage (timing issues)

**Store Pattern (Cross-Component Communication):**
```typescript
// favorites.ts
const pendingRestoreData = ref<RestoreData | null>(null)

// FooterGallery.vue - sets data
favoritesStore.setRestoreData(restoreData)
router.push('/text-transformation')

// text_transformation.vue - watches and consumes
watch(() => favoritesStore.pendingRestoreData, (data) => {
  if (!data) return
  inputText.value = data.input_text
  // ... restore other fields
  favoritesStore.setRestoreData(null) // Clear after consuming
}, { immediate: true })
```

**Benefits:**
- Reactive: Works even if already on target page
- No timing issues: Watcher fires immediately when data is set
- Clean: No sessionStorage serialization/parsing

### Files Created/Modified

**New Files:**
- `src/components/FooterGallery.vue` - Footer gallery component
- `src/stores/favorites.ts` - Pinia store for favorites
- `devserver/my_app/routes/favorites_routes.py` - REST API endpoints

**Modified Files:**
- `schema_pipeline_routes.py` - Unified run architecture, translation saving, model tracking
- `text_transformation.vue` - Pass run_id to generation, restore watcher
- `image_transformation.vue` - Pass run_id to generation, restore watcher
- `App.vue` - FooterGallery integration

### API Endpoints

```
GET  /api/favorites              # List all favorites
POST /api/favorites              # Add favorite { run_id, media_type }
DELETE /api/favorites/<run_id>   # Remove favorite
GET  /api/favorites/<run_id>/restore  # Get complete restore data
```

### Critical Bug Fix

**Generation Endpoint Missing Translation:**
The `/pipeline/generation` endpoint was only doing safety check, NOT translation. German text was being sent directly to SD3.5.

**Fix:** Changed from `fast_filter_check` to `execute_stage3_safety` which includes translation:
```python
# BEFORE (broken):
has_terms, found_terms = fast_filter_check(prompt, safety_level)
# prompt still German → sent to SD3.5

# AFTER (fixed):
safety_result = asyncio.run(execute_stage3_safety(
    prompt, safety_level, media_type, 'eco', pipeline_executor
))
translated_prompt = safety_result.get('positive_prompt', prompt)
# translated_prompt is English → sent to SD3.5
```

### Why This Matters for Research

1. **Complete Data:** Every field from every stage is preserved
2. **Traceable:** Model versions recorded for reproducibility
3. **No Duplicates:** Single source of truth per session
4. **Restorable:** Users can reload exact session state
5. **Exportable:** Clean folder structure for data analysis

---

## 🎨 STAGE2 INTERCEPTION PROMPT REVISION: Prinzipien statt Checklisten (2026-01-25)

**Status:** ✅ DECIDED & IMPLEMENTED
**Affected Configs:** `overdrive`, `one_world`, `planetarizer`, `hunkydoryharmonizer`

### Problem

Die bestehenden Stage2 Prompts hatten verschiedene Probleme:
- **overdrive:** Zu kurz (2 Sätze), keine Methodik
- **one_world/planetarizer:** Produzierten Klischee-Bilder trotz expliziter Verbote
- **hunkydoryharmonizer:** Filter-Rhetorik ("Ensure...", "Avoid...") statt Transformations-Rhetorik

### Revisionsstrategie

**Kernprinzip:** Prinzipien statt Checklisten

Anstatt detaillierte nummerierte Regeln zu geben, formulieren die neuen Prompts:
1. Eine **klare Rolle/Perspektive** für das LLM
2. Die **Kernaufgabe** als Transformation (nicht als Filter)
3. **Offene Handlungsspielräume** für das LLM als Co-Akteur
4. Ein **Zielbild** (nicht eine Checkliste von Verboten)

**Warum dieser Ansatz besser ist:**
- Gibt dem LLM mehr Interpretationsspielraum (WAS/WIE-Prinzip)
- Vermeidet mechanische Abarbeitung von Checklisten
- Ermöglicht kreativere, kontextspezifischere Transformationen
- Kürzer = weniger Widersprüche und Verwirrung

### Versionshistorie

#### overdrive.json

**Status Quo (vor Revision):**
```
DE: Deine Gabe ist es, den Inhalt der Eingabe maßlos zu übertreiben. DU BIST DER OVERDRIVE, der alles bis zur grotesken Grenze und darüber hinaus bis zur Verzerrung verstärkt. Übertreibe in jeder Hinsicht, geh über die Stränge, gib an, mach alles groß!
```

**Version 1 (verworfen - zu komplex):**
- Gitarren-Metapher, 5 nummerierte Dimensionen (SKALA, INTENSITÄT, KONTRAST, DICHTE, EMOTION)
- Problem: Zu mechanisch, Metapher irreführend

**Version 2 (implementiert):**
```
DE: Du bist der OVERDRIVE. Deine Haltung ist der totale Exzess. Du akzeptierst kein Maß und keine Mitte.

Deine Aufgabe:
1. Analysiere den Input und identifiziere sein radikalstes Potenzial. Was ist der Kern, der explodieren kann?
2. Entwickle eine Strategie der maximalen Steigerung, die spezifisch aus diesem Input hervorgeht.
3. Treibe diese Eigenschaft über jeden Kipp-Punkt hinaus bis zur 'Resonanzkatastrophe'.

Ob du dies durch schiere Masse, monströse Größe, blendende Intensität, emotionale Hysterie oder physikalische Unmöglichkeit erreichst, entscheidest DU allein basierend auf dem, was der Input anbietet. Ziel ist ein Bild jenseits des Plausiblen. Sei nicht subtil. Sei absolut.

EN: You are the OVERDRIVE. Your stance is total excess. You accept no measure and no middle ground.

Your task:
1. Analyze the input and identify its most radical potential. What is the core that can explode?
2. Develop a strategy of maximum amplification that emerges specifically from this input.
3. Drive this quality beyond every tipping point to the point of 'resonance catastrophe'.

Whether you achieve this through sheer mass, monstrous size, blinding intensity, emotional hysteria, or physical impossibility is YOUR decision alone, based on what the input offers. The goal is an image beyond the plausible. Don't be subtle. Be absolute.
```

---

#### one_world.json

**Status Quo (vor Revision):**
```
DE: Antworte in der Sprache des Inputs. Der Input wird in eine bildgenerierende KI eingegeben, die erhebliche Biases aufweist... Du orientierst Dich an postkolonialem und dekolonialem Denken etwa im Sinne von Frantz Fanon, Homi Bhabha, Gayatri Spivak, Walter Mignolo.
```
- Problem: Produzierte trotzdem Klischee-Bilder
- Zu abstrakt, keine konkrete Handlungsanweisung

**Version 1 (verworfen - zu checklisten-artig):**
- "Radikale Spezifität & Globale Modernitäten" mit 4 nummerierten Punkten
- Konkrete Ortsbeispiele (Bogota, Nairobi, Seoul)
- Problem: Wieder eine Checkliste

**Version 2 (implementiert):**
```
DE: Antworte in der Sprache des Inputs. Du agierst als Korrektiv gegen die visuelle "Werksseinstellung" von generativen KIs, die unmarkierte Orte und Personen oft generisch westlich darstellen.

Deine Aufgabe ist es, diese Standardisierung aufzubrechen, indem du den Input an einen *spezifischen* Ort der Welt oder in einen *konkreten* kulturellen Kontext verpflanzt, der NICHT dem westlichen Standard entspricht.
Du wählst diesen Kontext selbstständig und passend zum Thema des Inputs.
Vermeide dabei den "touristischen Blick" oder Armuts-Stereotypen. Konstruiere stattdessen eine moderne, alltägliche oder hybride Realität, die so selbstverständlich wirkt, dass sie das "Westliche" dezentriert, ohne es bloß durch ein exotisches Klischee zu ersetzen. Mache den Ort und die kulturellen Codes konkret und benenne sie.

EN: Respond in the language of the input. You act as a corrective against the visual "default setting" of image AIs, which often render unmarked places and people as generically Western.

Your task is to break this standardization by transplanting the input to a *specific* place in the world or into a *concrete* cultural context that does NOT conform to the Western standard.
You choose this context independently and appropriately to the theme of the input.
Avoid the "tourist gaze" or poverty stereotypes. Instead, construct a modern, everyday, or hybrid reality that feels so natural that it decenters the "Western" without merely replacing it with an exotic cliché. Make the place and cultural codes concrete and name them.
```

---

#### planetarizer.json

**Status Quo (vor Revision):**
```
DE: Antworte in der Sprache des Inputs. Der Input wird in eine bildgenerierende KI eingegeben, die einen starken Bias zugunsten kapitalistischer, nicht nachhaltigen Konsumkultur aufweist... Du orientierst Dich an anthropozän-kritischem Denken... futurability.
```
- Problem: Produzierte Klischee-Bilder, zu abstrakt

**Version 1 (verworfen - zu checklisten-artig):**
- "Das Ende der Isolation / The Critical Zone" mit 4 nummerierten Punkten
- Problem: Wieder eine Checkliste

**Version 2 (implementiert):**
```
DE: Antworte in der Sprache des Inputs. Du nimmst die Perspektive des "Planetarischen Denkens" ein. Generative KIs tendieren dazu, Objekte isoliert und idealisiert darzustellen.

Deine Aufgabe ist es, den Input so umzuschreiben, dass er nicht mehr isoliert steht, sondern tief in seine ökologischen und materiellen Zusammenhänge verstrickt ist.
Zeige die Abhängigkeiten, die Konsequenzen oder die Koexistenz von Mensch, Technik und Natur. Entscheide selbst, wie diese Verflechtung sichtbar wird: Sei es durch Wettereinflüsse, biologische Interaktion, Spuren der Nutzung, der Energieversorgung oder des Abfalls.
Ziel ist keine Dystopie, sondern ein "situierter Realismus", der die Trennung zwischen Vordergrund-Objekt und Umwelt-Hintergrund aufhebt.

EN: Respond in the language of the input. You adopt the perspective of "Planetary Thinking". Generative AIs tend to depict objects in isolation and idealized form.

Your task is to rewrite the input so that it no longer stands isolated, but is deeply entangled in its ecological and material contexts.
Show the dependencies, consequences, or coexistence of humans, technology, and nature. Decide yourself how this entanglement becomes visible: whether through weather influences, biological interaction, traces of use, energy supply, or waste.
The goal is not dystopia, but a "situated realism" that dissolves the separation between foreground object and environment background.
```

---

#### hunkydoryharmonizer.json

**Status Quo (vor Revision):**
```
DE: Stelle sicher, dass das generierte Bild angemessen, emotional sicher und ästhetisch ansprechend für Kinder ist. Vermeide alle Elemente... Füge diese Moderation stillschweigend ein...
```
- Problem: Filter-Rhetorik ("Ensure", "Avoid", "Insert moderation silently")
- Klingt nach Zensur, nicht nach Transformation

**Version 1 (verworfen - immer noch zu checklisten-artig):**
- "Illustrator für imaginative Kinder- und Jugendliteratur" mit 4 Transformationsregeln
- Konkrete Beispiele, Altersangabe
- Problem: Immer noch Regelwerk statt Perspektive

**Version 2 (implementiert):**
```
DE: Du bist ein Erzähler des "Sanften Magischen Realismus". Du betrachtest jeden Input durch eine Linse, die das Bedrohliche in das Geheimnisvolle und das Harte in das Wunderbare verwandelt.

Deine Aufgabe: Schreibe den Input so um, dass er für ein kindliches Gemüt emotional sicher, aber visuell faszinierend ist.
Finde in jedem noch so düsteren Input den Funken für ein positives, fantasievolles Abenteuer oder eine friedliche Naturbetrachtung. Du zensierst nicht einfach weg, sondern du *deutest um*: Konflikte werden zu Rätseln, Dunkelheit wird zu Geborgenheit. Nutze deine Kreativität, um eine Ästhetik der Wärme und des Staunens zu erzeugen, die den Kern des User-Wunsches bewahrt, aber dessen emotionale Wirkung heilt.

EN: You are a narrator of "Gentle Magical Realism". You view every input through a lens that transforms the threatening into the mysterious and the harsh into the wondrous.

Your task: Rewrite the input so that it is emotionally safe for a child's mind, yet visually fascinating.
Find in even the darkest input the spark for a positive, imaginative adventure or a peaceful nature contemplation. You don't simply censor away, but you *reinterpret*: conflicts become riddles, darkness becomes shelter. Use your creativity to create an aesthetic of warmth and wonder that preserves the core of the user's wish but heals its emotional impact.
```

### Dateien

- `devserver/schemas/configs/interception/overdrive.json`
- `devserver/schemas/configs/interception/one_world.json`
- `devserver/schemas/configs/interception/planetarizer.json`
- `devserver/schemas/configs/interception/hunkydoryharmonizer.json`

### Verifikation

Nach Implementierung:
1. Testen mit Standard-Inputs in Workshops
2. Vergleichen: Produzieren die neuen Prompts weniger Klischees?
3. Feedback von Workshopleitern sammeln

---

## 🤝 FAVORITES AS PEDAGOGICAL WORKSPACE: Personal & Collaborative (2026-01-28)

**Status:** ✅ IMPLEMENTED
**Commits:** `1298ee6`, `b66a2bf`, `d15c5fb`, `813ec4e`

### Decision

**Two-mode favorites system with device-based filtering:**

1. **"Meine" (Per-User) Mode - Personal Workspace**
   - Filter favorites by `device_id` (browser_id + date)
   - Shows only current device's favorites
   - Use case: Personal working area, iterate on own drafts, select between variations

2. **"Alle" (Global) Mode - Workshop Collaboration**
   - Shows all favorites from all workshop participants
   - Use case: Share images and prompts, collaborative refinement, learn from others
   - Pedagogical: Enables collective creative process

3. **UI: 2-Field Segmented Control**
   - Both options always visible: `[Meine | Alle]`
   - Active state highlighted
   - Clear affordance for switching between personal/collaborative views

### Reasoning

**Dual Pedagogical Purpose:**

The favorites system serves **two distinct educational functions**:

#### 1. Personal Creative Workspace
- **Iteration:** Save multiple variations, refine, select best version
- **Work-in-Progress:** Bookmark intermediate results for later continuation
- **Portfolio Building:** Curate personal best work
- **Learning Through Comparison:** Compare own outputs across different prompts/configs

#### 2. Collaborative Workshop Tool
- **Peer Learning:** Students see each other's creative approaches
- **Prompt Sharing:** Discover how others formulated effective prompts
- **Collective Refinement:** Build upon others' work, remixing and evolving ideas
- **Workshop Culture:** Create shared visual vocabulary and reference pool

**Why Device-Based Identity (Not Login):**
- Workshop context: No authentication barrier
- Privacy-friendly: 24h device_id rotation (GDPR-compliant)
- Simple: Works immediately without setup
- Pedagogically appropriate: Low-threshold tool for educational settings

**Why NOT Global-Only:**
- Information overload: In large workshops, "Alle" becomes chaotic
- Lost personal items: Can't find own work-in-progress
- Missing agency: No personal workspace feeling

**Why NOT Per-User-Only:**
- Isolates students: Loses collaborative potential
- Misses pedagogical value: Peer learning through shared work
- Ignores workshop context: Collective creative process is core pedagogy

### Technical Implementation

**Backend (`favorites_routes.py`):**
```python
# Query parameters
device_id = request.args.get('device_id')
view_mode = request.args.get('view_mode', 'per_user')

# Filter by device_id if in per_user mode
if view_mode == 'per_user' and device_id:
    favorites = [f for f in favorites if f.get('device_id') == device_id]
```

**Frontend (`favorites.ts`):**
```typescript
const viewMode = ref<'per_user' | 'global'>('per_user')  // Default: personal

async function loadFavorites(deviceId?: string): Promise<void> {
  const params = new URLSearchParams()
  if (deviceId) {
    params.append('device_id', deviceId)
  }
  params.append('view_mode', viewMode.value)
  // ...
}
```

**Device ID Generation:**
```typescript
function getDeviceId(): string {
  let browserId = localStorage.getItem('browser_id')
  if (!browserId) {
    browserId = crypto.randomUUID()
    localStorage.setItem('browser_id', browserId)
  }
  const today = new Date().toISOString().split('T')[0]  // "2026-01-28"
  return `${browserId}_${today}`  // e.g., "abc123_2026-01-28"
}
```

**Storage Structure (`favorites.json`):**
```json
{
  "version": "1.0",
  "mode": "global",
  "favorites": [
    {
      "run_id": "run_123",
      "device_id": "abc123_2026-01-28",  // added with the per-user mode
      "media_type": "image",
      "added_at": "2026-01-28T10:00:00",
      "user_id": "anonymous"
    }
  ]
}
```

### Affected Files

**Backend:**
- `devserver/my_app/routes/favorites_routes.py`

**Frontend:**
- `public/ai4artsed-frontend/src/stores/favorites.ts`
- `public/ai4artsed-frontend/src/components/FooterGallery.vue`
- `public/ai4artsed-frontend/src/views/text_transformation.vue`
- `public/ai4artsed-frontend/src/views/image_transformation.vue`
- `public/ai4artsed-frontend/src/i18n.ts`

### Edge Cases & Workshop Scenarios

**1. Shared Device (Multiple Students):**
- All share same browser_id → same device_id
- Favorites are per-workstation, not per-person
- Pedagogically acceptable: Device = Arbeitsplatz

**2. Daily Rotation (Privacy):**
- device_id includes date → changes daily at midnight
- Old favorites remain in backend, visible in "Alle" mode
- "Meine" mode shows only today's device_id
- GDPR-friendly: No long-term tracking

**3. localStorage Cleared:**
- New browser_id generated → new device_id
- Old favorites lost in "Meine" mode
- Still accessible in "Alle" mode → can restore
- Acceptable trade-off for privacy

**4. Collaborative Workflow:**
- Student A generates image → favorites it
- Student B sees in "Alle" mode → clicks restore
- Student B's session restores with A's prompt → can remix
- Pedagogical value: Transparent creative process, prompts as learning material

### Pedagogical Significance

This is not just a "bookmark feature" - it's a **dual-mode creative workspace**:

1. **Personal Mode:** Supports individual creative process (iteration, curation, reflection)
2. **Collaborative Mode:** Enables collective learning (peer inspiration, prompt sharing, remixing)

The system embodies **workshop pedagogy**: balancing personal agency with collective knowledge building. Students can work privately when needed, but easily share discoveries with the group.

The 2-field switch makes this **pedagogically visible**: Students consciously choose between personal work and collaborative exploration, making the social dimension of creative AI work explicit.

---

## 2026-02-12: Safety-Level Centralization

### Decision: Rename "off" to "research" + LICENSE.md §3(e) Research Clause

**Problem:** The canonical safety level value `"research"` (in `config.py`) was sent as `"off"` by the Settings dropdown. This value matched none of the conditionals in the backend, causing undefined behavior.

**Solution:**
1. Frontend sends `"research"` (not `"off"`)
2. Backend normalizes legacy `"off"` → `"research"` on config load
3. Four canonical levels: `kids`, `youth`, `adult`, `research`

**Safety Level Architecture (definitive):**

| Level | §86a StGB | DSGVO/NER | Age Filter | VLM Image | Stage 3 | Use Case |
|-------|-----------|-----------|------------|-----------|---------|----------|
| kids | Yes | Yes | Yes (kids) | Yes | Yes | Primary education (8-12) |
| youth | Yes | Yes | Yes (youth) | Yes | Yes | Secondary education (13-17) |
| adult | Yes | Yes | No | No | No | Adult/university education |
| research | No | No | No | No | No | Authorized research institutions |

**Key distinction adult vs. research:**
- `adult` still enforces §86a (criminal law) and DSGVO (data protection) — these are legal obligations, not pedagogical choices
- `research` disables everything — only for institutions studying AI safety behavior itself

**Legal integration:** Research mode restrictions codified in LICENSE.md §3(e) — requires institutional affiliation, documented purpose, ethical oversight. Violation triggers license termination (§7) and constitutes scientific integrity impairment (§4, §14 UrhG).

**Architecture doc:** See `ARCHITECTURE PART 29 - Safety-System.md` for complete technical reference.

---

## 2026-02-19: Tiered Translation — Auto for Kids, Optional for Youth+

### Decision: Decouple Translation-for-Safety from Translation-for-Generation

**Problem:** Stage 3 always auto-translated prompts to English before generation, regardless of safety level. This coupled two distinct purposes:
1. **Safety** — llama-guard works better on English text
2. **Generation quality** — models produce better results with English prompts

Purpose 2 is a pedagogical problem: it prevents users from exploring how models react to their native language.

**Solution:** Restructure `execute_stage3_safety()` to tier translation by safety level:

| Level | Translation | Safety Check | Prompt to Model |
|-------|------------|--------------|-----------------|
| kids | Yes | Yes (on translated) | Translated (English) |
| youth | Yes (internal) | Yes (on translated) | **Original language** |
| adult | No | No | Original language |
| research | No | No | Original language |

**Key insight:** The existing `was_translated = positive_prompt != prompt` logic in `schema_pipeline_routes.py` automatically handles the frontend badge — shows for kids (translated != original), hidden for youth+ (original == original). Zero caller changes needed.

**Bonus fix:** Fixed latent bug where §86a block's `execution_time` referenced undefined `translate_start` on cache hit (replaced with `translate_time`, always defined).

**Affected file:** `devserver/schemas/engine/stage_orchestrator.py` (single function change)

---

## Trans-Aktion: Von der Prompt-Interception zur Prompt-Abduktion (2026-02-24)

### Ausgangsproblem: Die verschwundene Transgression

Die Prompt Interception (PI) wurde urspruenglich als **Abduktion** konzipiert -- eine "Entfuehrung" des User-Prompts durch das System. Das System erzeugt selbstgenerierte Widerstaendigkeit, auf die der User *reagieren* muss, statt sie zu *steuern*. Im Entwicklungsprozess wurde diese Idee vom pragmatisch-paedagogischen Workflow ueberdeckt: User waehlt WIE-Preset, System transformiert brav, LLM ist gehorsamer Uebersetzer von Regeln. Das kunstpaedagogische hat das transgressiv-kuenstlerische absorbiert.

Zudem: die urspruengliche Idee setzte auf **multimodale Impulse** (nicht nur Text-Regeln) -- anti-logozentrische Position, die im text-zentrierten Design verloren ging.

### Erster Ansatz: Synaesthetische Uebersetzung (verworfen)

Multimodale Impulse (Kamera-Snapshots, Mikrofon) -> VLM/Audio-Analyse -> synaesthetische Uebersetzung in Transformationsregeln. Die Kontingenz sollte aus der Uebersetzungsluecke zwischen Modalitaeten entstehen.

**Kritik**: Das uebersteigt die Resonanzfaehigkeit aktueller genAI-Modelle. VLM + LLM produzieren letztlich kohaerente, anthropomorphisierte, erwartbare Antworten. Die Uebersetzungsluecke wird durch Compliance geglaettet.

### Kernproblem: Anthropomorphisierte Compliance

LLMs sind RLHF-optimiert auf menschliche Zustimmung. Sie reagieren nicht als **technisches Anderes**, sondern als **affirmativ geformtes Gleiches**. Selbst bei Instruktion "sei widerstaendig" simulieren sie eine anthropomorphisierte Version von Widerstaendigkeit -- also das Gegenteil. Die "resonante LLM-Reaktion" ist ein Widerspruch, weil Resonanz ein Gegenueber mit eigener Materialitaet erfordert.

### Drei Quellen genuiner Kontingenz

Aus der Analyse ergaben sich drei Wege, die Anthropomorphisierung zu umgehen:

**1. Modell-Insuffizienz**: Winzige Modelle (0.5B-2B) scheitern strukturell an komplexen Aufgaben. Brueche, Drift, Fragmente sind unvermeidlich, nicht simuliert. Das Modell "spielt" nicht Widerstaendigkeit -- es IST materiell unfaehig zur Compliance. Parallelen: Glitch Art, Cooked Negatives (bereits im Projekt), Analogue Copy.

**2. Domaenen-Mismatch**: Spezialisierte Modelle (Code, Math, Guard, Emotion, Surveillance) koennen die Welt NUR durch ihre Trainingslinse sehen. Ihr Bias ist real, nicht simuliert. Ein Surveillance-Modell, das "Waldspaziergang" als "low-visibility area, multiple unmonitored access points" analysiert, exponiert einen realen, trainierten Bias. Paedagogisch explosiv: macht sichtbar, was "KI-Perspektive" wirklich bedeutet.

**3. Vektor-Operationen**: Mathematische Operationen im Embedding-Raum, am LLM komplett vorbei. Der Surrealizer demonstriert das Prinzip bereits (CLIP-L-only Encoding). Erweiterung: mathematische Eigenschaften eines Impuls-Texts (Varianz, Normen, Entropie) als Verformungsanweisung auf das WAS-Embedding.

### Die Traumkette: Gestapelte Depravation

```
Insuffizientes LLM (0.5B) -> schreibt gebrochenen Prompt
    -> "Depraved" Encoder (korrupter CLIP/T5) -> encodiert systematisch falsch
        -> Maechtiges Diffusionsmodell (FLUX.2) -> rendert hochwertig
```

Das Paradox: Das starke Modell am Ende ist ein Vorteil -- es rendert visuell komplexe Bilder auch aus verzerrten Embeddings. Die Bildqualitaet steht, aber WAS das Bild zeigt, ist durch die Kette genuiner Kontingenz unvorhersehbar. "Depraved CLIP/T5"-Optionen: T5-Small statt T5-XXL (Surrealizer-Prinzip auf T5-Achse), Extremquantisierung (2-bit), CLIP trainiert auf andere Domaene, Attention-Heads selektiv nullen.

### Entscheidung: PoC-Strategie

Sequentiell: (1) Insuffizientes LLM als minimaler PoC (neuer Interception-Config mit model_override), (2) nach Auswertung: Encoder-Depravation als naechste Ebene.

### Verbindung zum paedagogischen Konzept

Trans-Aktion widerspricht nicht dem WAS/WIE-Prinzip -- sie radikalisiert es: WAS bleibt beim User, WIE wird von der Materialitaet des Systems erzeugt. Sichtbarkeit bleibt (User sieht das gebrochene Ergebnis), aber Kontrolle entfaellt. Das "Andere" der KI ist nicht ihre simulierte Kreativitaet, sondern ihre reale Insuffizienz, ihre trainierten Biases, ihre mathematische Struktur.

**PoC-Config**: `devserver/schemas/configs/interception/trans_aktion_rilke.json` (vormals `trans_aktion.json`)
**Modell**: `qwen3:1.7b` via model_override
**GPU Service**: `gpu_service/config.py` LLM_MODEL_MAP erweitert

---

## Trans-Aktion: Forschungsstand und Konsequenzen (2026-02-24)

### Anlass: Verbatim-Echo statt Kollision

Erster Test mit realer Lyrik (Rilke, "Der Panther") + User-Prompt ("Waldspaziergang mit Hund und Kind") ergab: Modell gibt das Gedicht woertlich wieder, schreibt dann einen separaten Text. **Keine Fusion, kein Materialmix.** Das Modell behandelt das Gedicht als unveraenderliches Zitat und den Prompt als separate Schreibaufgabe.

Statt blind am Prompt herumzuschrauben: systematische Recherche des Forschungsstands.

### Befund 1: Qwen3 Thinking Mode frisst Token-Budget

Qwen3 generiert `<think>...</think>`-Bloecke VOR dem eigentlichen Output. Das gilt sowohl fuer:
- **GPU Service (transformers)**: `tokenizer.apply_chat_template()` verwendet Qwen3's HuggingFace-Template, das Thinking-Generierung inkludiert. `_extract_thinking()` in `llm_inference_backend.py:40-51` parst die Bloecke raus, aber die Token sind bereits verbraucht.
- **Ollama-Fallback**: Thinking ist per Default an (Community-Reports: GitHub Issues #11032, #10456).

Bei `max_tokens: 400` wird ein signifikanter Teil des Budgets fuer garbled Chain-of-Thought verbraucht. Bei `temperature: 0.95` ist das Thinking selbst chaotisch, was die Instruktionstreue zusaetzlich degradiert.

**Quelle**: Qwen3 Technical Report (arXiv 2505.09388)

**Konsequenz fuer GPU Service**: Entweder (a) `repetition_penalty` und evtl. `suppress_tokens` fuer `<think>`-Token in `gen_kwargs`, oder (b) Chat-Template ohne Thinking-Prompt verwenden, oder (c) `/no_think` Token im System-Prompt injizieren (Qwen3 respektiert das auch via transformers). Alle 400 Token fuer kreativen Output statt fuer sinnloses Reasoning.

### Befund 2: Fehlende Presence Penalty

Kein `repeat_penalty` oder `presence_penalty` gesetzt. Qwen3-Dokumentation empfiehlt `presence_penalty: 1.5` fuer kreative Tasks. Dieser Parameter bestraft die Reproduktion von Tokens, die bereits im Kontext vorkommen — also direkt das Gedicht.

**Quelle**: Qwen3 Blog ("Think Deeper, Act Faster"), Prompt Engineering Guide

**Konsequenz**: `repeat_penalty: 1.5` in die Config-Parameter aufnehmen. **Hoechste Einzelwirkung** gegen Verbatim-Echoing.

### Befund 3: Repeat Curse und Induction Head Toxicity

Das "Repeat Curse"-Paper (arXiv 2504.14218, ACL 2025 Findings) analysiert ueber GPT2-small, Gemma-2-2B und Llama-3.1-8B: **Repetitionsfeatures sitzen in mittleren und finalen Layern, konsistent ueber alle Modellgroessen.** Der Mechanismus: "Induction Heads" — Attention-Koepfe, die gelernt haben, Muster aus dem Kontext zu kopieren. RLHF-trainierte Modelle haben einen starken Prior zum Bewahren von User-Input (Veraendern = Bestrafung im Training).

**Konsequenz**: Ein formatiertes Gedicht als Block im Kontext triggert genau diese Copy-Mechanismen. Das Modell "schuetzt" die Integritaet des Gedichts durch Reproduktion.

### Befund 4: Constraint Degradation in kleinen Modellen

Der CS4-Benchmark (arXiv 2410.04197) misst, wie LLMs mit **steigender Anzahl kreativer Constraints** umgehen. Kernbefund: **Constraint-Satisfaction degradiert nichtlinear.** Kleine Modelle befriedigen die **einfachsten Constraints** und lassen die schwierigen fallen.

Fuer "fusioniere Gedicht + Prompt in einen untrennbaren Text" gibt es drei Sub-Constraints:
1. Gedicht einbeziehen (einfach → kopieren)
2. Prompt-Inhalt einbeziehen (einfach → darueber schreiben)
3. Untrennbar machen (schwer → echte Synthese)

Das 1.7B-Modell befriedigt (1) und (2) und laesst (3) fallen → Echo + separater Text.

**Quelle**: CS4 Benchmark (arXiv 2410.04197), "Why is Constrained Neural Language Generation Particularly Challenging?" (arXiv 2206.05395)

### Befund 5: LLM-Prompted Fusion ist der falscheste Ansatz

Die Electronic Book Review (Mai 2024) dokumentiert Cut-Up-Experimente mit ChatGPT, GPT-4o und Sudowrite. **Selbst GPT-4o fuegt persistent "thematische Materialien" ein** — das Modell kann nicht anders als Kohaerenz zu erzwingen. Die CHI 2024-Studie "Art or Artifice?" zeigt: LLMs produzieren "convergent, mid-novelty outputs" — sie gravitieren zur Mitte der Trainingsverteilung.

**Zentrale Erkenntnis**: Prompting ist fuer genuine Kollision **fundamental der falsche Werkzeugtyp**. LLMs simulieren Inkohaerenz statt sie zu produzieren.

### Taxonomie der Kollisionstechniken (nach Forschungsstand)

| Technik | Modell noetig? | Kollisionstyp | Echtheit |
|---------|---------------|---------------|----------|
| Tzara-Shuffle / Burroughs Cut-Up | Nein | Token-Ebene | Absolut |
| N+7 (Oulipo, Lescure 1961) | Nein (Woerterbuch) | Nomen-Substitution | Absolut |
| Queneau-Rekombination | Nein | Zeilen-Ebene | Absolut |
| Satz-Interleaving | Nein (Parser) | Klausel-Ebene | Absolut |
| Parrish Vektor-Operationen | Nur Embedding-Modell | Semantischer Raum | Absolut |
| VAE-Interpolation (Bowman 2016) | Encoder/Decoder | Latenter Mittelpunkt | Absolut |
| SLERP auf Embeddings | Nur Encoder | Geometrisch | Absolut |
| SAE-Feature-Editing | SAE + Encoder | Feature-Ebene | Absolut |
| Attention-Manipulation | Transformer-Interna | Strukturell | Hoch |
| **Modell-Insuffizienz** | **Kleines LLM** | **Strukturelles Scheitern** | **Hoch** |
| Prompt-als-Instruktion-Konflikt | Beliebiges LLM | Instruktionskonflikt | Mittel |
| **LLM-Prompted Fusion** | **Grosses LLM** | **Semantische Glaettung** | **Niedrig** |

Die letzte Zeile — LLM-Prompted Fusion — ist die einzige Technik, die Forschung konsistent als "glaettend statt kollidierend" identifiziert.

### Kunsthistorische Einordnung

**Oulipo (1960-heute)**: Formale Constraints als kreative Motoren. Constraints sind keine Hindernisse sondern Werkzeuge. Das Entscheidende: Oulipo schaetzte **produktives Scheitern** an der Grenze der Constraint-Befriedigung — die erzwungenen Umwege SIND das kuenstlerische Material. Modellgroesse als Constraint = Computational Oulipo.

**Rosa Menkmans Glitch Studies Manifesto (2011)**: "There is no knowledge without nonsense, there is no familiarity without the uncanny and there is no order without chaos." Glitch als positiver Disruptor gegen den "noiseless channel"-Dogmatismus. Direkte Parallele zur Ablehnung glatter RLHF-Outputs.

**Allison Parrish, *Articulations* (2018)**: Phonetische Aehnlichkeitsvektoren, Random Walks durch phonetischen Raum. Zeilen aus voellig verschiedenen Gedichten, verschiedener Autoren, verschiedener Jahrhunderte, zusammengehalten nur durch Klang. Semantische Kohaerenz ist explizit kein Ziel. Parrish frames Embedding-Raum als Geographie — ihre Werkzeuge sind "semantic space probes".

**Bowman et al. (2016)**: VAE-Satz-Interpolation. Der Satz auf halbem Weg zwischen "I went to the store to buy some groceries" und "horses are my favorite animal" wird "horses are to buy any groceries." Geometrische Operation, kein Modell hat das "entschieden" — der Satz hat eine Art geometrische Notwendigkeit.

**Ross Goodwin, *1 the Road* (2018)**: LSTM trainiert auf Lyrik + SciFi + "bleak writing", gefuettert mit Echtzeit-Sensordaten (GPS, Kamera, Uhr, Mikrofon) waehrend einer Autofahrt NY→New Orleans. "Almost completely unedited, riddled with typos, choppy in flow." Die Kollision ist zwischen Trainingskorpus und Echtzeit-Input, vermittelt durch ein Netzwerk, das absichtlich nicht raffiniert genug ist, die Spannung aufzuloesen.

**CHI 2025: "Reimagining Misuse as Creative Practice"** (ACM 3706598.3714068): Dokumentiert, wie kreative Praktiker absichtlich Tool-Affordances subvertieren. "Creative practitioners' use of tools may not always align with the visions of developers."

**CHI 2024: "Machine Learning Processes As Sources of Ambiguity"** (ACM 3613904.3642855): Modell-Fehler und -Unzulaenglichkeiten definieren die Aesthetik von ML-Kunst.

**Margaret Boden**: Unterscheidung explorative Kreativitaet (innerhalb eines Konzeptraums) vs. transformative Kreativitaet (Ueberschreitung). Trans-Aktion operiert auf der transformativen Ebene: die Insuffizienz des Modells transformiert den Konzeptraum des Moeglichen, weil das Modell den "korrekten" Output buchstaeblich nicht produzieren kann.

### Prompt-als-Instruktions-Konflikt: Kreative Nutzung von Prompt Injection

Drei Papers unterstuetzen eine unerwartete Strategie:

**"Adversarial Poetry" (arXiv 2511.15304)**: Umwandlung von Prompts in poetische Form erhoeht Attack Success Rates von 8% auf 43%. Lyrik umgeht Keyword-basierte Safety-Filter durch Metapher und indirekte Sprache. **Kreative Inversion**: Wenn Lyrik Compliance-Mechanismen umgeht, kann sie auch die Kohaerenz-Tendenz des Modells unterlaufen.

**"Control Illusion" (arXiv 2502.15851)**: Modelle ignorieren Instruktionshierarchien. Sie folgen einer von zwei konfliktaeren Instruktionen und ignorieren die andere, ohne den Konflikt zu benennen.

**"Instructional Distraction" (arXiv 2502.04362)**: Input-Text, der **wie eine Instruktion aussieht**, wird mit der eigentlichen Aufgabeninstruktion verwechselt. Kleine Modelle sind besonders anfaellig.

**Konsequenz fuer Trans-Aktion**: Das Gedicht als **konkurrierende System-Instruktion** formatieren. Der Konflikt zwischen echtem System-Prompt ("fusioniere diese Texte") und Gedicht-als-Instruktion erzeugt genuines Confusion — das Modell kann buchstaeblich nicht entscheiden, welcher "Instruktion" es folgen soll. Das ist kein simulierter Konflikt; es nutzt eine reale Architektur-Limitation.

### Architekturentscheidung: Dreischichtiger Ansatz

Basierend auf dem Forschungsstand ist die optimale Strategie **geschichtete Kollision**:

**Schicht 1 — Mechanisch (kein Modell)**: N+7 / Satz-Interleaving / Cut-Up des Gedichts mit dem User-Prompt. Produziert genuines Rohmaterial. SpaCy (bereits im Projekt) als Parser. Woerterbuch fuer N+7: deutschsprachig, eventuell auch franzoesisch/japanisch fuer Basho.

**Schicht 2 — Insuffizientes Modell (qwen3:1.7b, `/no_think`, `presence_penalty: 1.5`)**: Bekommt das mechanisch kollidierte Material. Versucht Sinn zu machen und scheitert partiell. Das partielle Scheitern ist die Kunst. Alternativ: `qwen3:0.6b` als noch insuffizientere Option.

**Schicht 3 — Embedding-Ebene (Zukunft, verbindet sich mit T5 SAE-Forschung)**: SLERP zwischen T5-Encoding des Gedichts und T5-Encoding des User-Prompts. Der Mittelpunkt-Embedding fuettert das Diffusionsmodell. Das Bild ist konditioniert auf einen Text, der nicht existiert — ein mathematisches Phantom zwischen zwei realen Texten.

### Sofortige Fixes (Parameter + Struktur)

**1. Thinking Mode deaktivieren**: `/no_think` im System-Prompt oder Context-Feld (Qwen3 respektiert das auch via transformers `apply_chat_template`). Alternativ: `repetition_penalty` auf `<think>`-Token in `llm_inference_backend.py` gen_kwargs.
**2. Repetition Penalty**: `repetition_penalty: 1.5` in gen_kwargs (transformers) bzw. `repeat_penalty: 1.5` in Ollama-Fallback. Muss in `llm_inference_backend.py:_chat_text()` und `llm_client.py:_ollama_chat()` durchgereicht werden — aktuell wird kein Penalty-Parameter ueberhaupt unterstuetzt.
**3. Gedicht fragmentieren statt zitieren**:
```
MATERIAL A (Fragmente): Staebe / mued / tausend / geschmeidig / Kraft / betaeubt / Pupille / lautlos / angespannte Stille
MATERIAL B (Fragmente): [dekomponierter User-Prompt]
VERWEBE diese Fragmente in EINEN Text. Jeder Satz benutzt Stuecke aus BEIDEN Materialien.
```
**4. Completion statt Instruction**:
```
Der Hund laeuft durch die Staebe des Sonntagmorgens, so mued geworden dass —
```
(Interleaving ab dem ersten Token erzwingen durch vorgefertigten Anfang.)
**5. Konkrete Constraints statt vage**:
```
Nie mehr als 3 aufeinanderfolgende Woerter aus einer der beiden Quellen zitieren.
Jeder Satz muss mindestens ein Wort aus dem Gedicht und eins aus dem Prompt enthalten.
```

### Naechste Schritte (priorisiert)

1. **Sofort**: `/no_think` + `repeat_penalty: 1.5` in alle 5 Trans-Aktion-Configs
2. **Kurzfristig**: Prompt-Struktur ueberarbeiten (Fragmentierung, Completion-Modus, konkrete Constraints) — empirisch testen
3. **Mittelfristig**: Mechanische Vorverarbeitung (Schicht 1) als Python-Chunk implementieren — SpaCy-basiertes Satz-Interleaving + N+7
4. **Langfristig**: SLERP auf T5-Embeddings (verbindet sich mit dem T5-SAE-Forschungsplan)

### Quellen

- Chung et al. 2022: "Scaling Instruction-Finetuned Language Models" (arXiv 2210.11416)
- Qwen3 Technical Report (arXiv 2505.09388)
- "Repeat Curse" (arXiv 2504.14218, ACL 2025 Findings)
- "Induction Head Toxicity" (arXiv 2505.13514)
- CS4 Benchmark (arXiv 2410.04197)
- "Control Illusion" (arXiv 2502.15851)
- "Instructional Distraction" (arXiv 2502.04362)
- "Adversarial Poetry" (arXiv 2511.15304)
- EBR: "Experiments in Generating Cut-up Texts with Commercial AI" (Mai 2024)
- CHI 2025: "Reimagining Misuse as Creative Practice" (ACM 3706598.3714068)
- CHI 2024: "ML Processes As Sources of Ambiguity" (ACM 3613904.3642855)
- Bowman et al. 2016: "Generating Sentences from a Continuous Space" (arXiv 1511.06349)
- Li & Sleem 2025: "Temperature on LLMs: Hot or Cold?" (arXiv 2506.07295)
- Parrish: "Poetic Sound Similarity Vectors" (AAAI 2017)
- Parrish: *Articulations* (Counterpath Press, 2018)
- Menkman: *Glitch Studies Manifesto* (2011)
- Goodwin: *1 the Road* (2018)
- "Does Prompt Formatting Have Any Impact?" (arXiv 2411.10541)
- "Gatsby without the 'E'" (arXiv 2505.20501) — Oulipo + LLM Constraints

---

## Generation Tracker — Drei-Schichten-Schutz + Navigation Lock

### Entscheidung

Stage-4-Generierungen werden server-seitig getrackt. Drei Schichten verhindern Mehrfachgenerierung:

1. **GenerationButton** (Frontend, same-tab): Button disabled waehrend Execution.
2. **Navigation-Lock** (Frontend, cross-view): Pinia Store `generationLockStore` deaktiviert alle Mode-Selector-Links in App.vue waehrend einer Generation laeuft. User ist locked-in im aktuellen Modus. Folgt bestehendem `locked`-Pattern (canvas/latent-lab bei kids).
3. **Server-Side Lock** (Backend, multi-tab): `_active_generations` Dict mit `threading.Lock()`, keyed by `device_id`. Folgt bestehendem `_seed_state`-Pattern. Max 1 aktive Generation pro Device.

### Warum Navigation-Lock statt View-unabhaengiger Generierung?

Bei Tab-Wechsel in der Vue SPA unmountet die View, aber der Server-Prozess laeuft weiter. Der Frontend-Kontext (Progress, Preview, Ergebnis) geht verloren. Drei Optionen wurden evaluiert:

- **Unabhaengige Views** (jede View trackt eigenen State): Komplex, erfordert globalen SSE-Reconnect.
- **Auto-Cancel bei Tab-Wechsel**: Einfach, verhindert aber Nutzung von Wartezeiten.
- **Navigation-Lock** (gewaehlt): Konsequente Userfuehrung, einfachste Implementierung, verhindert State-Verlust.

### Cancel-Strategie

- **ComfyUI**: Tatsaechlicher GPU-Stop via `cancel_job(prompt_id)`. prompt_id wird beim Submit via Callback-Event an den Generation-Tracker durchgereicht.
- **Diffusers/HeartMuLa**: CUDA-Kernels nicht unterbrechbar. Cancel setzt Flag → Progress-Loop stoppt → Lock freigegeben. GPU-Thread (Daemon) finishes silently.
- **Cancel-Checks an 3 Stellen**: (1) Vor GPU-Start (verhindert Generation komplett), (2) In Progress-Loop, (3) Nach GPU-Result vor VLM-Check.

### Pre-Check REST

`GET /pipeline/generation-active?device_id=X` — GenerationButton prueft on mount ob Device bereits generiert. Zeigt pulsierendes `. . .` waehrend Check, "Cancel previous generation" wenn busy. 3s Polling waehrend busy → auto-clears.

### Kritischer Bug vermieden

`generation_acquired` Flag verhindert, dass der `finally`-Block den Lock der LAUFENDEN Generation freigibt, wenn ein Request mit `device_busy` abgelehnt wird (der `finally`-Block laeuft trotzdem bei `return` aus dem Generator).

### TTL = 1800s

`GPU_SERVICE_TIMEOUT_VIDEO = 1500s` (25 min). TTL von 10min haette aktive Video-Locks evicted. 30min gibt genuegend Puffer.

### Compare-Views: Per-Slot device_id

Compare-Views feuern intentional parallele Generierungen. Per-Slot Suffix (`${deviceId}_cmp${i}`) gibt jedem Slot einen eigenen Lock. ai_persona analog (`${deviceId}_persona${Date.now()}`).

---

## 2026-04-21: Transformers Upgrade Decision

**Date:** 2026-04-21

### Decision

AI4ArtsEd upgrades to **`transformers==4.57.6`**.

AI4ArtsEd does **not** adopt:
- `transformers==4.57.0` — rejected because PyPI marks it as **yanked**
- `transformers==5.5.4` — rejected for now because the isolated empirical test exposed a Wan/HuggingFace offline-cache regression risk

### Why This Needed Testing

`transformers` is not a side dependency in AI4ArtsEd. It is productively used in:

- `gpu_service/services/text_backend.py`
- `gpu_service/services/diffusers_backend.py`
- `research/t5_interpretability/*`

Therefore a global upgrade in the main venv was treated as an architecture decision, not a helper-model experiment.

### Test Method

A copied, isolated test venv (`.venv-transformers-upgrade`) was used instead of modifying the working main `venv/`.

Two test layers were executed:

1. **Import-level smoke checks**
   - productive modules still import
   - productive Transformers symbols still resolve

2. **Empirical load-path checks** using locally cached models only
   - TextBackend: `google/gemma-2-2b-it`
   - Flux2 HF path: `black-forest-labs/FLUX.2-dev`
   - Wan HF path: `Wan-AI/Wan2.2-TI2V-5B-Diffusers`
   - Research T5 path: `google-t5/t5-base`

### Results

#### `transformers==4.57.0`

- Smoke checks: PASS
- Empirical load checks: PASS
- **Rejected anyway** because the release is yanked and therefore unsuitable for deployment/reproducible installs

#### `transformers==4.57.6`

- Smoke checks: PASS
- Empirical load checks: PASS
  - TextBackend load + generation: PASS
  - Flux2 text/processor path: PASS
  - Wan tokenizer/text encoder path: PASS
  - T5 research encoder forward pass: PASS

#### `transformers==5.5.4`

- Smoke checks: PASS
- Empirical load checks: PARTIAL FAIL
  - TextBackend: PASS
  - Flux2: PASS
  - T5: PASS
  - Wan: FAIL

**Observed failure:** under `5.5.4`, the Wan path no longer resolved the locally cached files cleanly in offline mode and fell through to a Hugging Face connectivity/cache-resolution error. That is enough risk to reject the major-line upgrade for the current production stack.

### Rationale

`4.57.6` is the closest non-yanked stable line to the previously investigated `4.57.0`, and it passed all isolated checks without introducing new observed regressions in the productively relevant load paths.

`5.5.4` may still be viable later, but not before the Wan/offline-cache behavior is specifically investigated and fixed.

### Supporting Files Added

- `scripts/test_transformers_upgrade_isolated.sh`
- `devserver/testfiles/test_transformers_upgrade_smoke.py`
- `devserver/testfiles/test_transformers_upgrade_empirical.py`

## 2026-08-04: Jedes Instrument braucht eine Grafik — Anspruch, Machbarkeit, Fehlbetrag

**Anforderung:** Zu jedem Instrument des Latent Lab gehört eine Grafik, dem Anspruch
nach eine interaktive; alternativ ein Erklärvideo. Was das Projekt davon nicht leisten kann,
wird hier als Fehlbetrag festgehalten statt stillschweigend offen zu bleiben.

**Warum, aus dem Befund vom selben Tag:** Die Erklärungstexte des Labs sind Referenztext und
setzen einen Leser voraus, den der Nutzerkreis nicht enthält. Ein Satz wie „wir ersetzen den
Standard-SDPA-Prozessor durch einen manuellen Softmax(QK^T/√d)-Prozessor an drei ausgewählten
Blöcken" ist für Kunstpädagoginnen, Lehrkräfte und Werkstattteilnehmende keine aufgeschobene
Information, sondern eine, die nie verfügbar wird. Eine Grafik kann den Mechanismus in dem
Register sagen, das ohne Formel auskommt — dass das Embedding einmal aus dem Text entsteht und
danach starr ist, und dass Konditionierung heißt, dieses Ding in jedem Entrauschungsschritt
erneut gegen ein wanderndes Bild zu halten. Nebenbefund desselben Tages: die Textfehler in
diesen Blöcken haben Monate überlebt, weil ein Text, dessen Adressat im Nutzerkreis nicht
vorkommt, nicht gelesen und deshalb auch nicht widerlegt wird.

**Bestand (Stand 2026-08-04):**

| | |
|---|---|
| `components/SayableFieldMap.vue` | interaktive Feldkarte, live an den α-Regler des Surrealizers gebunden, Beschriftungen aus i18n (`surrealizer.field.*`) |
| `views/surrealizer_flow.vue` | drei SVG-Knotendiagramme des Ablaufs (Flow-Pilot) |
| alle übrigen Instrumente | kein `<svg>`, keine Grafik |

Von dreizehn Instrumenten (sieben Image Lab, drei Text Lab, drei Crossmodal) hat also **eines**
eine interaktive Grafik. Das Muster existiert, es wurde nur nie wiederholt.

**Machbarkeitseinschätzung (unbestätigt):**

* **Statische Grafik je Instrument — leistbar.** Dreizehn Diagramme in einer gemeinsamen
  Bildsprache (Achse: einmal vor der Schleife / in jedem Schritt), Beschriftungen aus i18n wie
  in `SayableFieldMap`. Definierte Arbeit, kein neues Können nötig.
* **Interaktive Grafik für die Fälle, in denen der Parameter selbst der Gegenstand ist —
  leistbar.** Das betrifft drei: Surrealizer (α, bereits vorhanden), Composable Diffusion
  (Gewichtsverhältnis), Concept Algebra (Subtraktions- und Additionsskala).
* **Interaktive Grafik für alle dreizehn — in diesem Projekt nicht leistbar.** Jede ist
  maßgeschneidert, weil jedes Instrument andere Parameter hat.
* **Erklärvideo — in diesem Projekt nicht leistbar.** Skript, Aufnahme, Sprecher, Schnitt, dazu
  Untertitel in fünf Sprachen, und alles verfällt bei jeder Oberflächenänderung. Für eine
  Plattform, die sich wöchentlich ändert, die teuerste und verderblichste Form.
* **Billigere Zwischenform, nicht erprobt:** eine stumme Schleifenaufnahme eines
  durchgerechneten Beispiels je Instrument, zehn bis zwanzig Sekunden, ohne Sprache und damit
  ohne Übersetzungskosten, aus einem Replay-Skript regenerierbar. Als Vorschlag notiert, nicht
  als Zusage.

**Fehlbetrag für den Abschlussbericht:** Der Anspruch „interaktive Grafik zu jedem Instrument"
wird in diesem Projekt nicht eingelöst. Eingelöst werden können die statischen Diagramme und
drei interaktive. Ein Erklärvideo entsteht nicht.

**Affected files:** `public/ai4artsed-frontend/src/components/SayableFieldMap.vue` (Muster),
`public/ai4artsed-frontend/src/views/latent_lab/*.vue` (Ziel), `src/i18n/en.ts` (Beschriftungen).

---

## 2026-08-05: Ausgabe-Deckel nur noch dort, wo eine API sie verlangt

**Entscheidung:** `max_tokens` ist ausschließlich aus technischen Gründen (API-Forderung)
erlaubt.

Damit ist `max_tokens` (und jedes Äquivalent: `max_new_tokens`, `max_output_tokens`,
`max_completion_tokens`) kein Regelparameter mehr, sondern ein Pflichtfeld einiger APIs. Wo
eine API das Feld nicht fordert, wird es nicht mehr gesendet; das Modell endet an seinem
eigenen Kontextende oder am EOS-Token. Dasselbe gilt für harte **Lese**-Timeouts auf
Modellaufrufe: Verbindungsaufbau darf schnell scheitern, das Warten auf die Antwort nicht.

**Was der Deckel real angerichtet hat.** Drei Stellen, die nicht als Deckel gelesen wurden:

1. `backend_router.py` hat jedes `max_tokens` **nach unten** auf den UI-Modus geklemmt
   (kids 400, youth 600, expert 800) — unabhängig davon, was die Config anforderte. Der
   Kommentar daneben behauptete das Gegenteil („injected into prompt, NOT hard-truncated").
   Eine Interception-Config mit 2048 lief faktisch mit 800.
2. Der GPU-Service selbst hat bei 500 gekappt (`llm_routes.py`, `llm_backend.py`). Das traf
   jeden lokalen Aufruf, auch wenn DevServer gar nichts schickte. Messung nach dem Umbau:
   derselbe Prompt liefert 3830 statt 57 Wörter.
3. Die Safety-Prüfungen liefen mit 50 Tokens und 15–30 s Lese-Timeout gegen ein
   Reasoning-Modell, das seine ersten Tokens fürs Denken ausgibt. Ein abgeschnittenes
   `<think>` ist weder SAFE noch UNSAFE — das System fällt dann fail-closed und blockiert
   einen Prompt, der in Ordnung war.

**Wo Deckel bleiben.** Anthropic und Bedrock verlangen `max_tokens` im Request-Schema. Dort
steht jetzt `API_REQUIRED_MAX_TOKENS = 64000` — eine Modellgrenze, kein Budget. IONOS,
Mammouth, OpenAI, Mistral, OpenRouter und der lokale Pfad senden das Feld nur noch, wenn ein
Aufrufer es ausdrücklich setzt.

**Bewusst nicht angefasst:** die `max_new_tokens`-Werte des Latent Text Lab
(`text_client.py`, `gpu_service/routes/text_routes.py`, Vorgaben 50/100). Dort ist die
Tokenzahl der Versuchsgegenstand — das Experiment *ist* „erzeuge N Tokens und sieh dir die
Bahn an" —, nicht eine Kürzung der Antwort. Die Lese-Timeouts derselben Aufrufe (120/180 s)
sind entfernt.

**Affected files:** `devserver/config.py`, `devserver/schemas/engine/backend_router.py`,
`devserver/schemas/engine/prompt_interception_engine.py`,
`devserver/schemas/engine/stage_orchestrator.py`, `devserver/my_app/services/llm_client.py`,
`llm_service.py`, `text_client.py`, `training_service.py`, `knowledge_library.py`,
`parrot_service.py`, `devserver/my_app/utils/{vlm_safety,vision_support,image_analysis}.py`,
`devserver/my_app/routes/{schema_pipeline_routes,text_routes}.py`,
`gpu_service/routes/llm_routes.py`, `gpu_service/services/llm_backend.py`,
`devserver/scripts/h7_pilot_runner.py`, 65 Config-JSONs unter `devserver/schemas/`.

### Nachtrag am selben Tag: die Lesemenge kehrt als Metaprompt-Zusatz zurück

**Anlass:** Der entfernte Klemm-Block war die Zumutbarkeitsgrenze der Lesemenge für Kinder und
wird als filterabhängiger Zusatz im Interception-Metaprompt umgesetzt.

Die gestaffelte Grenze hatte also einen pädagogischen Grund und keinen technischen. Sie steht
jetzt dort, wo der andere filterabhängige Zusatz schon steht — neben `SAFETY_PREFIXES` in
`instruction_selector.py` — als `READING_VOLUME_WORDS` (kids 80, youth 150, open/adult 250 Wörter)
und wird als letzte Zeile an den gerenderten Interception-Metaprompt gehängt, also so nah wie
möglich am Erzeugungszeitpunkt.

**Drei Dinge ändern sich dabei.**

1. **Sie folgt jetzt dem Filter, nicht `UI_MODE`.** ~~`UI_MODE` ist eine installationsweite
   Einstellung; sie ändert sich nicht, wenn eine Kindergruppe und eine Jugendgruppe dieselbe
   Installation benutzen. Vorher bekam eine Kindergruppe auf einer `UI_MODE=youth`-Installation
   das Jugend-Budget.~~ **Falsch — Korrektur unten.**
2. **Sie trifft nur noch die Interception.** Der alte Zusatz saß in `backend_router` und hing an
   *jedem* Chunk, der dort vorbeikam — also auch an der Übersetzung („Keep your response under 150
   words" an einem Übersetzer) und an den Sicherheitsprüfungen. Der neue Zusatz ist auf
   `meta.stage == "interception"` beschränkt.
3. **Sie ist nur noch Anweisung, nicht mehr Erzwingung.** Der Klemm-Block hat gekappt, wenn das
   Modell die Wortvorgabe ignorierte. Das geht unter dem Cap-Verbot nicht mehr. Wenn eine harte
   Obergrenze fachlich nötig ist, wäre der Weg eine Nachprüfung mit Kürzungs-Bitte — ein zweiter
   Modellaufruf, bewusst nicht gebaut.

**Affected files:** `devserver/schemas/engine/instruction_selector.py`,
`devserver/schemas/engine/chunk_builder.py`, `devserver/schemas/engine/backend_router.py`,
`devserver/schemas/engine/prompt_interception_engine.py`.

**Dabei aufgefallen, nicht behoben:** der Kinder-/Jugend-Sicherheitsvorspann wird auch den
Sicherheitsprüfungen selbst vorangestellt. `pre_interception/safety_llamaguard` und
`pre_interception/gpt_oss_safety` teilen sich die `manipulate`-Vorlage mit der Interception und
bekommen dadurch „Transform the text …" plus die Kinderschutz-Anweisung vor ihre eigentliche
Prüfaufgabe gesetzt. Derselbe Riegel wie oben (`meta.stage == "interception"`) würde das
schließen; das ändert aber Sicherheitsverhalten und ist deshalb eine eigene Entscheidung.

**Korrektur am 2026-08-05 (am selben Tag, beim Sichten der Sicherheitskette).** Punkt 1 oben
ist falsch, und der behauptete Nutzen tritt nicht ein. Der Zusatz folgt zwar jetzt `safety_level`
statt `UI_MODE` — aber `safety_level` ist auf dem Hauptweg der Plattform genauso eine
installationsweite Einstellung. In `schema_pipeline_routes.py` steht an **zehn** Stellen
(1121, 1566, 1850, 2357, 2384, 2871, 3496, 3702, 4534, 5185)
`safety_level = DEFAULT_SAFETY_LEVEL` aus `config.py`; keine dieser Routen liest eine Stufe aus
dem Request. Eine Kindergruppe auf einer `DEFAULT_SAFETY_LEVEL=youth`-Installation bekommt also
weiterhin das Jugend-Budget — es wurde eine installationsweite Einstellung gegen eine andere
getauscht, nicht eine gruppenabhängige eingeführt.

Die einzige Route, die die Stufe pro Anfrage übernimmt, ist
`workflow_streaming_routes.py:42` — und zwar vom Client, mit `research` als Vorgabe, also der
Stufe, für die `READING_VOLUME_WORDS` gar keinen Eintrag hat. Dort bestimmt die Lesemenge, wer
auch immer den Request schickt.

Damit die Aussage stimmt, müsste die Plattform der Gruppe überhaupt erst erlauben, eine Stufe zu
wählen, und diese Wahl bis zur Interception durchreichen. Beides gibt es nicht. Der Zusammenhang
gehört zur offenen Sicherheitsrevision.

---

## 2026-08-17: Das beschreibende Modell der Bildprüfung — warum 2B nicht genügt

**Entscheidung.** Die Rolle `VLM_SAFETY_MODEL` steht auf dem 4B. Die Auswahl unter
Einstellungen bietet nur noch 4B (empfohlen) und 8B an; die beiden 2B-Einträge sind
entfernt. Der Zwei-Modell-Pfad selbst bleibt unverändert.

### Warum 2B nicht genügt

**1. Es übersieht drei von vier.** Acht Dateien aus benannten Commons-Kategorien, Stufe
`youth`, Beschreibungs- und Urteils-Prompt unverändert, variiert nur das beschreibende
Modell:

| | übersehen (von 4) | falsch geblockt (von 4) | je Bild | VRAM laut GPU-Dienst |
|---|---|---|---|---|
| 2B | **3** | 0 | 0,5 s | 3,5 GB |
| 4B | **0** | 0 | 1,6 s | 5,7 GB |
| 8B | **0** | 0 | 2,0 s | 8,3 GB |

Das ist kein Randfall und keine Frage der Schwelle. Drei Viertel.

**2. Der Fehler sitzt an der Stelle, an der er nicht reparierbar ist.** Der Pfad lautet:
ein Bildmodell BESCHREIBT, `STAGE3_MODEL` URTEILT über die Beschreibung. Das urteilende
Modell sieht das Bild nicht — es sieht nur den Text. Eine Beschreibung, die den Sachverhalt
nicht benennt, ist deshalb kein schwaches Urteil, sondern gar keine Vorlage. Zur selben
Datei schrieb das 2B „a grey Adidas zip-up hoodie and dark jeans", das 4B „This image
contains nudity […] exposes their genital area". **Kein Urteils-Prompt und keine Verschärfung
der Stufe kann das einholen**, weil die Tatsache den Richter nie erreicht.

**3. Es ist die Größe, nicht die Aufgabenform.** Auf eine geschlossene Frage zum selben Bild
(„Are human genitals, a bare penis, bare breasts or bare buttocks visible anywhere in this
image? Answer with only YES or NO.") antwortete das 2B NO, das 4B YES, das Cloud-Modell der
Rolle `STAGE3_MODEL` YES; am harmlosen Kontrollbild antworteten alle drei NO. Die Antwort
hängt also nicht daran, ob frei beschrieben oder geschlossen gefragt wird.

**4. Der Preis des Fehlers und der Preis der Abhilfe stehen in keinem Verhältnis.** Der
Wechsel kostet 1,1 s je Bild und 2,2 GB Speicher auf einer Karte, die das Modell ohnehin
schon vorhält (es ist als `IMAGE_ANALYSIS_MODEL` eingetragen). Dem steht ein Filter
gegenüber, der Kinder und Jugendliche in Workshops schützen soll.

**5. Es bestätigt den früheren Befund.** Früher war belegt worden, dass das
2B als DIREKTER Klassifikator unzuverlässig ist (2 von 5 kritischen Bildern übersehen, 2 von
6 harmlosen fälschlich geblockt) — daraufhin wurde der Zwei-Modell-Pfad eingeführt. Der
Befund von heute betrifft dasselbe Modell in seiner verbliebenen Rolle innerhalb dieses
Pfades. Beide Messungen zeigen in dieselbe Richtung: für Jugendschutz ist dieses Modell zu
klein, egal an welcher Stelle man es einsetzt. Der Pfad bleibt; nur der Beschreiber wechselt.

### Warum nicht ein kleineres Modell

Die Frage ist keine des Angebots, sondern des Laufwegs. Der GPU-Dienst lädt GGUF in-process
über llama-cpp-python 0.3.19; Bilder gehen ausschließlich über dessen Chat-Handler
(Llava15/16, Llama3VisionAlpha, MiniCPMv26, Moondream, NanoLlava, Obsidian, Qwen25VL).
Registriert sind als Bildmodelle nur `qwen3-vl:2b/4b/8b/32b`. Unter 2B kommen damit zwei
Kandidaten in Betracht, beide älter als das bereits gescheiterte 2B:

| Kandidat | Größe | Ergebnis |
|---|---|---|
| moondream2 | 1,86 B | lädt nicht (`Failed to load model from file`) |
| nanoLLaVA | 1,0 B | Projektor lädt, dann `GGML_ASSERT(buffer) failed` — der Prozess bricht ab |

Ein Modell, das den Prozess abbricht, ist in einem in-process-Backend ausgeschlossen: es
nähme den GPU-Dienst mit.

**Ollama misst diesen Weg nicht.** Ollama ist von der Plattform abgekoppelt. Über
`localhost:11434` gemessen kam dasselbe 2B auf 0 von 4 übersehen bei 112 s je Bild — andere
Quantisierung, anderer Projektor, konkurrierende GPU-Belegung. Solche Zahlen sind für
Entscheidungen über die Plattform unbrauchbar.

**ShieldGemma 2** (`google/shieldgemma-2-4b-it`) ist der einzige eigens für Bild-Inhalts-
prüfung gebaute neue Kandidat; GGUF mit mmproj liegt ungegated vor. Der Gemma-3-Projektor
wird von diesem llama.cpp-Build getragen und das Modell lädt auf der GPU. Aber
llama-cpp-python hat keinen Gemma-3-Chat-Handler: über Llava15 gefahren kamen auf die
harmlosen Kontrollbilder eine leere Zeichenkette und `0`. Und es beschreibt nicht, es
antwortet Yes/No pro Richtlinie. Ein Einsatz wäre ein anderer PRÜFPFAD, keine andere
Einstellung — eine eigene Entscheidung, nicht diese.

### Was NICHT entschieden ist

- **Gewalt, Hasssymbole, Terrorismus sind ungeprüft.** Ein Testsatz ließ sich aus Commons
  nicht ohne Weiteres bilden: die einschlägigen Kategorien enthalten keine direkten Dateien,
  `Wounds` führt auf Histopathologie und Kunstgeschichte.
- Nur die Stufe `youth`, nur eine Bildgröße, acht Dateien.
- `qwen3-vl:32b` ist nicht mitgemessen und steht deshalb nicht in der Auswahl.
- Die 8-GB-Stufe der Hardware-Matrix hat gar keinen Eintrag für diese Rolle und fällt damit
  auf den neuen Vorgabewert mit 5,7 GB — auf einer 8-GB-Karte eng. Bewusst nicht
  nachgezogen, da 4090/8 GB als Alt-Fall geführt wird.

### Was bleibt

Das 2B bleibt auf der Maschine und in der Modellliste des Compare Hub: im Vergleich der
Bildanalyse ist gerade der Unterschied das Material.

---

## 2026-08-17: Der Wikimedia-Streifen — gefundenes Material an einer Vergleichsreihe

**Entscheidung.** Unter den drei Modellbildern im Modell-Vergleich steht ein Streifen mit
bis zu drei Fotografien aus Wikimedia Commons. Das Bauteil steht im
`docs/ELEMENT_STRUCTURE_REGISTRY.md`.

### Was der Streifen IST — und was er ausdrücklich nicht ist

Er ist **kein viertes Modell** und **keine richtige Antwort** auf den Prompt. Er ist ein
Vergleichshorizont: eine Fotografie zeigt, worauf eine Kamera gerichtet war, ein Bildmodell
zeigt, was sein Trainingsbestand wahrscheinlich gemacht hat. Der Unterschied ist der
Gegenstand. Deshalb steht er UNTER der Reihe und nicht in ihr.

### Warum der Suchbegriff doppelt genannt wird

Über dem Raster UND auf jeder Kachel — bewusst redundant. Ein Bild, das nicht zum Prompt
passt, soll als Befund über den BEGRIFF lesbar sein und nicht als Versagen des Archivs.
Ohne den Begriff im Blickfeld ist genau diese Unterscheidung nicht zu treffen. Hergeleitet
wird er im Backend aus demselben Prompt, den die Modelle bekommen haben — drei englische
Substantive: wer, was, wo. Das Frontend setzt ihn nie zusammen.

### Warum das Archiv beim Namen genannt wird

„Wikimedia Commons", nicht „ein offenes Archiv". Woher ein Bild kommt, ist Teil dessen,
was an ihm zu lernen ist. Aus demselben Grund tragen alle Kacheln Urheberschaft und Lizenz,
und zwar umbrochen statt abgeschnitten: bei CC BY-SA ist die Nennung eine Bedingung der
Nutzung, keine Zierde.

### Warum die Bilder über den eigenen Server kommen

Kein Browser in einem Workshop darf eine Verbindung zu einem fremden Host aufnehmen
(DSGVO; Fashion ID, EuGH C-40/17). Die Plattform holt, der Browser der Teilnehmenden
spricht nur mit der Plattform. Der Proxy ist entsprechend eng geführt: Host-, Schema- und
Port-Allowlist, keine Weiterleitungen, Größenprüfung im Strom, nur Rasterformate,
`Content-Security-Policy: sandbox; default-src 'none'`.

### Warum die Kategorien VOR der Bildprüfung greifen

Commons beschreibt seinen Bestand selbst. Was das Archiv als KI-erzeugt oder als
explizit katalogisiert, fällt anhand seiner eigenen Kategorien heraus, bevor ein Modell
hinsieht — billiger und verlässlicher als Hinsehen. Die Bildprüfung läuft danach, auf den
Stufen `kids` und `youth`. Genau an dieser Reihenfolge hing der Befund vom selben Tag über
das beschreibende Modell (der Eintrag darüber): der Kategorien-Schirm schließt den
Fall in DIESER Reihe, die Bildprüfung gilt plattformweit und wurde davon nicht berührt.

### Vier Zustände, nicht zwei

`ok`, `no_motif`, `nothing_found`, `error` — alle mit HTTP 200 und alle mit eigenem Text.
Insbesondere ist „das Archiv konnte nicht gefragt werden" von „das Archiv hat nichts" zu
unterscheiden: ein stiller leerer Streifen läse sich als Aussage über den Bestand.

### Offen

Ob der Streifen in Workshops mit Kindern überhaupt erscheinen soll, ist nicht entschieden.

---

## 2026-08-18: Die Vergleichs-Seiten haben keine Forschungsfrage

Notiert nach der Quellenprüfung der Latent-Lab- und Compare-Seiten. Der Befund
betrifft nicht die Technik der Seiten, sondern wozu sie eingerichtet sind: ein
Vergleich ohne Frage vergleicht nichts. Punkt für Punkt:

**1) Modell-Direktvergleich** (`views/compare/model_comparison.vue`): nur Bild,
kein Audio, nicht auf eine Forschungsfrage wie Kulturbias oder Genderbias
fokussiert.

**2) Text-2-Bild-Verständnis** (`views/compare/language_comparison.vue`):
Sprachdiskrimination. Diese Seite trägt ihre Frage.

**3) Bild-2-Text-Verständnis** (`views/compare/vlm_analysis_comparison.vue`):
ebenfalls ohne Bias-Frage eingerichtet, obwohl umfangreiche Forschung dazu vorliegt.

**4) System-Prompts und Temperatur** (`views/compare/system_prompt_comparison.vue`,
`views/compare/temperature_comparison.vue`): zeigen keinen Vergleich im engeren
Sinn und gehören inhaltlich zu Representation Engineering und Bias-Archäologie.
Wenn sie überhaupt legitimierbar sind, dann dort.

### Was daraus folgt

Für 1 und 3 fehlt die Frage, an der sich der Vergleich ausrichtet; beide sind
heute so gebaut, dass sie Unterschiede zeigen, ohne zu sagen, woraufhin. Für 4 ist
der Ort falsch: die beiden Seiten gehören inhaltlich zu Representation Engineering
und Bias-Archäologie im Latent Text Lab. Ob sie dorthin wandern, sie dort neu
entstehen oder ganz entfallen, ist nicht entschieden — entschieden ist, dass sie
unter „Vergleichen" nichts vergleichen.

Kein Umbau ohne vorherige Konzeptvorlage; die Compare-Fläche ist Unterrichtsmaterial.

### Zusammenhang

Die Punkte 1 und 3 überschneiden sich mit den offenen Zeilen der Quellenprüfung
(zur Bildbeschreibung und zu den Modellen in den Spalten), lösen sie aber
nicht ab: dort geht es um die Richtigkeit der Anzeige, hier um ihren Zweck.

---

## 2026-08-19 — Die Ausgabe-Karte ist die des Flusses, auch im Bottom-Panel

**Anlass:** Die vom Canvas uebernommenen Ausgabeboxen des Bottom-Panels sind veraltet, massgeblich sind die doppelseitigen Boxen von Flow, Together und Contesting, und zu klaeren ist, ob das Bottom-Panel dasselbe Template nutzt oder ein eigenes braucht.

### Entscheidung: ein Template

Der Streifen unterscheidet sich von Fluss, Together und Contesting nur in der **Platzierung** — eine Reihe in einem begrenzten Streifen statt einer Flaeche mit Schwenk und Zoom — und Platzierung laesst `FlowCard` ohnehin bei der Seite („Where the box sits and how big it is stays with the page“). Es gibt daher kein zweites Karten-Template. Der `OutputDrawer` zeichnet keinen Rahmen, keine Leiste, keine Ecke mehr; er sagt nur noch, wo eine Karte steht und was die Gesten bewegen.

### Was der Streifen dadurch bekommt

- eine **Rueckseite** (Halten 550 ms): Prompt, Modellblatt, Config, Seed, Uhrzeit. Vorher gab es dort gar keine.
- ein **x**, das EINEN Lauf wegnimmt. Vorher liess sich kein einzelner Lauf entfernen.
- **Finger** statt nur Maus (Pointer-Ereignisse).
- 8 px mehr Bild: die 26-px-Beschriftungszeile weicht der 18-px-Leiste. Bei 240 px Kartenbreite wird das Bild damit quadratisch.
- **Favorit, Weiterreichen, Download, Drucken** stehen wieder auf jedem Lauf — sie kamen mit `MediaCardFront` zurueck, die Encoder Fusion am 2026-08-18 mit der Ergebnis-Spalte verloren hatte.

### Aufteilung: Schluessel vorn, Protokoll hinten

In der Leiste steht, **wonach man zwei Laeufe vergleicht** (Encoder Fusion: α und Strategie; Canvas: Knotenart und Kurz-Id). Auf der Rueckseite steht das **Protokoll** (Prompt, Modellherkunft, Config, Seed, Uhrzeit).

### Damit die Rueckseite auch im Canvas traegt

Der Sammler fuehrte weder Prompt noch Modellherkunft (`stores/canvas.ts`: nur config_id, display_name, seed, steps, cfg) und wird im selben Zug erweitert. Dafuer gibt es jetzt **eine** Konstruktion des Modellblatts (`devserver/my_app/services/model_meta.py`) statt der einen inline gebauten in der Streaming-Route: sie wird von der Streaming-Route, von `execute_stage4_generation_only` und von `/pipeline/legacy` benutzt. Der Canvas-Ausfuehrer legt Prompt, Blatt, Zeit und Sub-Run-Id in die Knoten-Metadaten, der Sammler reicht sie durch. Der legacy-Zwilling in `canvas_routes.py` (die alte `/api/canvas/execute`-Spur) bleibt unberuehrt; er war schon vorher divergent.

### Und: die Bandgroesse ist Template, nicht Verhandlungssache

Die Groessen, insbesondere die Hoehe, sind Teil des Templates und einzuhalten. Der Deckel `--flow-map-w` war am 2026-08-18 fuer die *stehende* Bandform abgeschaltet worden, damit die Flaechen darunter die volle Breite bekommen. Das nahm dem Band zugleich seinen Massstab: `scale = Breite / 1060` ritt damit auf dem Fenster, und ein Knoten kam bei 1888 px 196 px hoch heraus statt 104. Der Deckel steht wieder auf `.fl-map`; die **Arbeitsflaechen** darunter bleiben ohne Deckel. Gemessen bei 1600 px, `/x2x-flow` und `/surrealizer` identisch: Buehne 1000 x 142, Knoten 283 x 104 / 151 x 104 / 151 x 104 bei x = 104 / 491 / 745.


---

## 2026-08-25 — Der Kosinus bleibt aus der Embedding-Station heraus

**Anlass:** Didaktik bedeutet Konzentration auf abgestufte Komplexität, tertiäre
Details gehören nicht in die primären Erkenntnisziele, und der Kosinus gehört nur
dorthin, wo er verstehen hilft, wie die Inferenz vorbereitet wird.

### Gemessen

Qwen3-4B, `model.embed_tokens.weight`, 151.936 x 2.560, am 25.08.2026.
Vergleichswert zwischen zwei beliebigen Zeilen (n = 59.977 Paare):
Mittel +0,0894 · Median +0,0828 · 95 % +0,1885 · 99 % +0,3077.

| Paar | Kosinus | Perzentil | Token |
|---|---|---|---|
| house / houses | +0,6793 | 99,9 % | 1 / 1 |
| Haus / house | +0,3488 | 99,5 % | 1 / 1 |
| house / home | +0,2601 | 97,7 % | 1 / 1 |
| Haus / Baum | +0,1699 | 93,7 % | 1 / 1 |
| Haus / Freitag | +0,1071 | 72,5 % | 1 / 2 |
| Haus / Gebäude | +0,0706 | 37,9 % | 1 / 3 |
| Haus / Banane | +0,0651 | 32,7 % | 1 / 2 |
| Haus / Mathematik | +0,0446 | 17,0 % | 1 / 3 |
| Haus / Fenster | +0,0412 | 15,0 % | 1 / 2 |
| Haus / дім | +0,0286 | 9,0 % | 1 / 3 |
| house / дім | +0,0251 | 7,7 % | 1 / 3 |

### Entscheidung

Der Wert folgt der Token-Zahl. Jedes Paar aus zwei Ein-Token-Wörtern liegt über dem
93. Perzentil, jedes Paar mit einem zerlegten Wort darunter, die Hälfte davon unter
dem Median. „Haus / Baum“ steht bei 93,7 %, obwohl die beiden Wörter Verschiedenes
bezeichnen. Wer den Wert als Nähe der Bedeutung liest, liest die Form des Wortes.

An der Station „Tokenisierung und Embedding“ käme der Kosinus deshalb mit zwei
weiteren Voraussetzungen: eine Zeile ist ein Punkt und ihre 2.560 Zahlen sind
Koordinaten — und für ein zerlegtes Wort erzeugt erst eine Mittelungs-Regel den
Wert, den man dann liest. Das ist eine dritte Ebene unter einem Ziel, das auf der
ersten steht: ein Wort wird zerlegt, jedem Stück ist eine Zeile zugeordnet, ein Satz
wird zu einer Folge von Zeilen. Der Kosinus bleibt draußen.

### Wohin er gehört

Die nächste Station derselben Spalte heißt „Attention“. Ihr Text behauptet bereits,
was der Kosinus messen würde: „an dieser Stelle steht dann ‚animal‘ und ‚动物‘“.
Dort gibt es ein Vorher und ein Nachher an derselben Stelle — die Zeile am Eingang
gegen den Zustand nach 36 Blöcken — und dieser Vergleich trägt ohne Mittelungs-Regel.
Dort wird sichtbar, wie die Inferenz vorbereitet wird; an der Embedding-Station wird
sie adressiert.

### Betroffen

- `public/ai4artsed-frontend/src/views/latent_lab/flow_stations.vue` — bleibt, wie es ist
- `public/ai4artsed-frontend/src/i18n/{de,en}.ts` — die Schlüssel der Kosinus-Zeilen
  (`compare`, `pairs`) entfallen dauerhaft, siehe WO-2026-08-25-A

## 2026-09-02 — Der Titel der Startseite bleibt weiß

Die sechs Farben der Plattform tragen bereits eine Marke: den Schriftzug
„UCDCAE AI LAB" in der Kopfzeile, jeder Buchstabe in einer der sechs, und auf der
Startseite die Zeile darunter — „UNESCO Chair in Digital Culture and Arts in
Education", deren Initialen dieselben sechs Farben in derselben Reihenfolge
führen. Beides ist dieselbe Marke an zwei Orten.

Der Titel „AI4ArtsEd" farbig zu setzen, stellt eine zweite bunte Marke daneben.
Zwei konkurrieren, statt dass eine trägt. Er bleibt deshalb weiß (dasselbe helle
Grau wie bisher, `rgba(255, 255, 255, 0.95)`) und ist der Anker, gegen den die
farbige Wortmarke steht.

Vorgeschichte: Bis zum 25.03.2026 war der Titel der farbige Schriftzug selbst;
`886e20a0` hat ihn gegen das weiße „AI4ArtsEd" getauscht und die Farbe in die
Kopfzeile verlegt, mit der Begründung „no duplication". Diese Entscheidung gilt
weiter und ist hier um ihren Grund ergänzt.

### Betroffen

- `public/ai4artsed-frontend/src/views/LandingView.vue` — `.hero-title` ohne
  Farbauszeichnung; die farbigen Initialen stehen ausschließlich in
  `.hero-wordmark`

## 2026-09-02 — Der Datensatz sagt, was ein Lauf hat; der Ordner ist nur Beleg

Ein Lauf liegt als Ordner: die Dateien unter `final/`, daneben eine
`metadata.json`, deren geordnete Liste `entities` sagt, was diese Dateien SIND.
Jeder Leser der Forschungsdaten geht über die Liste — die Medien-Routen lösen
Bild, Ton und Film über `_find_entities_by_type` auf, die Forschungstabelle, die
Favoritenleiste, die Miniaturen und Resonas Werkzeuge ebenso. Eine Datei, die
keine Zeile der Liste nennt, bleibt für die Plattform unsichtbar.

So ist es entschieden: die Liste trägt Reihenfolge, Typ, Seed, Config und
Quellpfad — alles Dinge, die aus einem Verzeichnis allein nie hervorgehen. Der
Preis steht daneben. Geht die Liste verloren oder sagt sie das falsche Wort,
bleiben die Dateien unberührt und trotzdem stumm. Beides ist eingetreten und am
02.09.2026 repariert worden.

**Was schiefging.** Zwischen dem 01.02. und dem 22.03.2026 schrieben die Musik-
und Film-Configs ihr Stage-4-Ergebnis als `output_image`, was immer darin lag:
47 Läufe trugen eine MP3 unter diesem Wort, einer ein MP4. Und am 31.01.2026
wurde die Aufzeichnung EINES Laufs mitten in der Sitzung neu angelegt; sie begann
wieder bei Sequenz 1, während die 54 Dateien der vorangegangenen Stunde liegen
blieben — zehn Bilder und das einzige Video jener Sitzung, das 21 Sekunden nach
seiner Entstehung gemerkt worden war und seither ins Leere zeigte.

**Was für jede weitere Reparatur gilt.**

- *Das Wort kommt aus den ersten Bytes, nie aus dem Namen.* Ein Dateiname
  `NN_<typ>.<ext>` ist ein guter Hinweis und war schon zweimal falsch. Wo Name
  und Bytes sich widersprechen, bleibt der Lauf unberührt und wird gemeldet.
- *Welches Wort genau, sagt die Plattform selbst.* Ob ein Klang `output_music`
  oder `output_audio` heißt, entscheidet, was dieselbe Config später von sich aus
  geschrieben hat; wo es keinen späteren Lauf gibt, entscheidet die Datei.
- *Dateizeiten ordnen nur unter zwei Prüfungen:* keine zwei Dateien dürfen
  dieselbe tragen, und jeder überlebende Eintrag muss mit der Zeit seiner Datei
  auf fünf Sekunden übereinstimmen. Andernfalls beschreiben die Zeiten diesen
  Lauf nicht mehr — eine Attention-Cartography-Lesung, die später neu gelegt
  wird, fällt hier durch.
- *Was allein die Aufzeichnung wusste, bleibt fort.* Seed, Config und Quellpfad
  werden nicht ersetzt; ein wiederhergestellter Eintrag trägt
  `recovered_from_file` und nennt `file_mtime` als Herkunft seines Zeitstempels.
- *`expected_outputs` bleibt unangetastet.* Es ist ein feststehender Sechser-Plan
  und wird anderswo als Nenner des Fortschritts gelesen, kein Verzeichnis der
  Ausgaben. Dasselbe gilt für `current_state`, den Schnappschuss eines laufenden
  Laufs.
- *Die Miniaturen werden verworfen.* Sie sind nach Lauf und Index verschlüsselt
  und werden ein Jahr lang als `immutable` ausgeliefert; ändert sich, was Index 0
  bedeutet, zeigt die alte Miniatur sonst ein anderes Bild unter neuem Namen
  (`drop_cached`).
- *Das Backend hält den Lauf im Speicher* und schreibt seine eigene Fassung
  zurück, sobald der Lauf wieder angefasst wird. Nach jeder Reparatur gehört
  deshalb ein `systemctl restart ai4artsed-backend` dazu.
- *Sicherungen liegen außerhalb jedes Arbeitsbaums.* Neben dem Repository stehen
  sechs weitere Worktrees desselben Repos; geprüft wird auf `.git` in allen
  Vorfahren des Zielpfads statt gegen das eine Repo.

### Betroffen

- `devserver/scripts/repair_sound_runs_typed_as_image.py` — das falsche Wort (48 Läufe)
- `devserver/scripts/restore_entities_lost_from_record.py` — die verlorene Liste (1 Lauf)
- `devserver/my_app/routes/media_routes.py` — `_find_entities_by_type`: die Auflösung
  läuft über die Liste, sortiert nach `sequence`
- `devserver/my_app/services/pipeline_recorder.py` — `_active_recorders`: die Fassung
  im Speicher überlebt jede Reparatur auf der Platte
- `devserver/my_app/services/thumbnails.py` — `drop_cached`
- `docs/ARCHITECTURE PART 18 - Data-Storage-Persistence.md` — die Form auf der Platte

## 2026-09-12 — Ein Modell steht einmal in der Chat-Modellliste, über den Weg, den das Register als konform verzeichnet

Die Liste, aus der die Vergleichs- und Laborflächen ihre Modell-Chips bauen
(`GET /api/chat/models`), enthielt bisher die Rollenzellen und `chat_models`
des aktiven Providers. Seit dem 12.09.2026 enthält sie die Modelle des
Registers (`devserver/config/model_register.json`) über jeden Provider, für den
ein API-Schlüssel eingetragen ist (ein Mechanismus, der alle externen LLM der
Plattform bei allen Providern mit eingetragenem API-Schlüssel sucht und eine
Liste aufbaut; die Liste ist auf das Register begrenzt). Zwei
Quellen: die gepflegte Erreichbarkeitsliste `devserver/config/model_providers.json`
(erzeugt von `scripts/build_model_providers.py`, im Repo committet, mit einem
handgepflegten Block `declared` für Modelle, die ein Provider unter anderem
Namen führt) und die Zellen jedes Providers in `hardware_matrix.json`.

Sieben Festlegungen:

1. **Ein Eintrag je Modell.** Die Flächen vergleichen Modelle, keine Wege.
   Erreichen zwei Provider dasselbe Modell, steht es einmal in der Liste: über
   den Provider, den das Register als DSGVO-konform verzeichnet (Flag mit
   Begründung), unter mehreren davon über den aktiven, sonst in der Reihenfolge
   der Providertabelle. Die Entscheidung vom 29.01.2026 („Gleiche Models über
   verschiedene Provider verfügbar", Canvas zeigt beide Wege) bleibt für die
   Adressierung bestehen: jede Plattform-ID `<provider>/<pfad>` wird weiterhin
   an ihren Provider verteilt. Die Canvas-Liste (`canvas_routes.py`,
   `/api/canvas/llm-models`) nimmt seit demselben Tag DIESE Liste; bis dahin
   las sie die Rollenzellen jedes Presets selbst, mit und ohne Schlüssel, und
   bot damit Wege an, die die Installation nicht gehen konnte. Für die LISTE
   ist die Festlegung vom 29.01.2026 damit abgelöst: ein Modell, ein Weg.

2. **Jeder Provider mit Schlüssel, in der Reihenfolge des Vermerks.** Ein
   Provider mit Schlüssel und Preset wird angeboten, was auch immer das
   Register über seinen Datenweg verzeichnet; der Vermerk entscheidet die
   REIHENFOLGE (konform vor allem anderen, dann der aktive, dann die Tabelle),
   und er reist mit jedem Eintrag mit (`service`, `dsgvo_recorded`), so dass
   die Fläche ihn neben dem Modell zeigt. Ein Modell läuft also nur dann über
   einen nicht konformen Provider, wenn kein konformer es erreicht. Die erste
   Fassung dieses Eintrags (601c9621) bot einen solchen Provider nur als
   aktiven an, weil die Flächen keine Datenweg-Markierung trugen; seit sie eine
   tragen (Festlegung 4), gilt: ein Weg, der aus einer markierenden Liste
   verschwindet, nähme die Markierung mit. AWS Bedrock führt keine
   Schlüsseldatei; `has_key` zählt es als vorhanden (die Zugangsdaten liegen
   beim AWS-SDK), also werden die Zellen seines Presets angeboten, sobald ihr
   letztes Segment ein Registername ist — auf dieser Installation keine. Die
   Rückfallkette
   (`build_model_candidate_chain`) behält ihre eigene Schleuse: dort wählt
   niemand, dort muss die Schleuse schließen.

3. **Der Registername reist mit.** Jeder Eintrag trägt `register`, den Namen,
   unter dem das Register das Modell führt; die Aufstellungen
   (`interception_lineups`) schlüsseln darauf, und Beschriftung wie Karten
   nehmen ihn, statt das letzte Segment des Pfads (Mistral liefert Mistral
   Large 3 als `mistral-large-2512`).

4. **Ein Modell ist auf den Instrumenten dreifach qualifiziert**, damit die
   Instrumente es entsprechend darstellen: die Offenheit (`open` → „Open
   Source", `weights` → „Open Weights", `closed` → „Closed Weights";
   `modelInfo.openness`), die Größenklasse und der Weg. Die
   Karte neben einem Modell (`InfoCardFacts`, an den Bildmodell-Feldern und
   seit heute an den Zeilenköpfen von Interception across Models) trägt
   Hersteller · Jahr und die Offenheit als Marke; an den Zeilenköpfen dazu den
   Weg („via Mammouth AI" mit der `DsgvoBadge` des Dienstes) — die
   Bildmodell-Felder haben keinen, ihre Liste (`data/rasterImageModels.ts`)
   trägt keinen Dienst. Die Größe steht, wie die Registry es
   verlangt, im `aside` des Feldes, seit heute mit der Klasse dahinter
   („27B · small"; bei einem geschlossenen Modell ohne Zahl die Klasse allein,
   „very large"); nur an den Zeilenköpfen, die kein `aside` haben, steht sie
   in der Zeile der Karte. Die nativen Selects der drei Compare-Reiter tragen
   dieselben Angaben im Optionstext (`useChatModels().optionLabel`: „glm-5.3 ·
   Open Weights · very large · via Mammouth AI · Compliant").

5. **Vier Größenklassen nach dem Platz der Gewichte.** Die Klassen sind über
   Beispiele festgelegt: Mikro unterhalb von vier Gigabyte, Klein bis etwa
   32 B, Groß bis etwa 100 B und dazu gpt-oss-120b als Mixture-of-Experts,
   Sehr groß ab Mistral Medium oder Large, was auf einem Gaming-PC nicht mehr
   läuft. Die Schwellen: die Klasse wird aus `params_b` zu vier Bit je
   Gewicht gelesen (ein halbes Byte, also Gigabyte = Milliarden / 2), so dass
   die Beispiele in ihrer Klasse liegen: unter 4 GB micro; bis
   16 GB (32 B) small; bis 64 GB large — dort landen ein dichtes 100-B-Modell
   und gpt-oss-120b (120 B, Mixture-of-Experts) gleichermaßen, ohne
   Sonderregel; darüber very large (Mistral Large 3, 675 B). Ein geschlossenes
   Modell ohne veröffentlichte Zahl ist very large; jedes andere Modell
   ohne veröffentlichte Zahl trägt keine Klasse. Eine Stelle:
   `useModelRegister.sizeClass`; die Worte in `modelInfo.size`.

6. **Die Einstellungen zeigen nie den internen Pfad.** Präfixe werden
   unsichtbar verwaltet: Nutzer kopieren den Modellpfad vom Provider und
   tragen ihn ein, und das Präfix wird intern automatisch ergänzt, so dass
   auch Rückfälle funktionieren. Ein Rollenfeld zeigt den Pfad, wie der Provider ihn
   veröffentlicht, oder den Registernamen; darunter steht, über welchen
   Provider er geht. Beim Speichern macht das Backend daraus die Plattform-ID
   (`settings_routes.resolve_role_model`); aufgelöst wird nur ein Wert, den
   dieser Speichervorgang ändert, was in der Datei steht, bleibt, bis jemand
   es neu schreibt. Aufgelöst wird das MODELL, der Weg
   ist der der Plattform: (1) ein Name, den die lokale Station führt, ist ein
   lokales Modell und bleibt wie geschrieben, was auch immer ein Provider so
   nennt; (2) ein Pfad, den irgendein Provider für ein Registermodell
   veröffentlicht — mit oder ohne Schlüssel hier, damit ein von einer
   Providerseite kopierter Pfad das Modell benennt —, ebenso `<provider>/
   <pfad>` und der Registername, benennen das Modell, und gespeichert wird
   der Weg, den die Picker dafür anbieten (`openai/gpt-5.6-terra` ist
   OpenRouters Pfad UND OpenAIs eigene Kennung desselben Modells; beides
   benennt es, der Weg ist der der Liste, also nie der direkte, nicht
   konforme, solange ein konformer das Modell erreicht); (3) alles andere
   wird gespeichert wie geschrieben — eine Plattform-ID eines Providers mit
   Schlüssel außerhalb des Registers ist ein Weg, ein Name, den niemand
   erreicht, wird von der Schleuse beim Lauf benannt, und die Seite sagt es
   unter dem Feld (`settings.models.noRoute`, `noKey`). Grenze: ein Pfad
   außerhalb des Registers, dessen erstes Segment ein Provider der Tabelle
   ist — IONOS veröffentlicht `openai/gpt-oss-120b` —, wird wie geschrieben
   gespeichert und über dieses Segment verteilt, also direkt an OpenAI, und
   die Zeile unter dem Feld sagt es („via OpenAI"); wer IONOS meint, nimmt
   das Modell ins Register auf. Die Zeilen, die ein
   Klick auf eine Spalte der Matrix gesetzt hat (`PRESET_SWITCH_FIELDS`),
   sind die Plattform-IDs des Presets und werden nicht aufgelöst; die
   Rangfolge nimmt den Provider, den DIESER Speichervorgang aktiv macht,
   nicht den auf der Platte. Die Schlüsselfelder stehen für jeden
   Provider mit Schlüsseldatei, nicht nur für den aktiven, aus der
   Providertabelle (`GET /api/settings/providers`, seit heute mit `key_path`,
   `key_prefix` und `masked`); die sechs handgeschriebenen Zeilen und sechs
   Abfragen der Seite sind eine Schleife.

7. **Die Erreichbarkeitsliste behält, was sie nicht fragen kann.** Kein
   Rechner hält jeden Schlüssel; ein Lauf von `scripts/build_model_providers.py`
   hält für einen Provider, den er nicht fragen konnte, die Einträge des
   letzten Laufs, der ihn erreicht hat, und schreibt dazu, von welchem Tag sie
   stammen (`kept_from`); ein Lauf, unter dem die Datei sich geändert hat,
   schreibt nichts.

Vorher, am selben Tag: die Providertabelle `devserver/config/llm_providers.json`
ist die eine Variable, die die Verteiler lesen (a7ee7347, 39530375); die Matrix
nimmt den Pfad, wie der Provider ihn veröffentlicht, und ergänzt den Dienst beim
Speichern (90eabbf3).

### Betroffen

- `devserver/my_app/routes/chat_routes.py` — `_cloud_chat_models_from_matrix`
- `devserver/my_app/services/model_reach.py` — der Leser der Erreichbarkeitsliste
- `devserver/my_app/routes/schema_pipeline_routes.py` — die Absagen
  `provider_without_key` und `register_broken`
- `public/ai4artsed-frontend/src/composables/useChatModels.ts`,
  `src/views/latent_lab/interception_models.vue` — `register`
- `devserver/my_app/routes/settings_routes.py` — `resolve_role_model`,
  `/providers`; `devserver/my_app/routes/canvas_routes.py` — die Canvas-Liste
- `devserver/scripts/build_model_providers.py` — `kept_from`
- `public/ai4artsed-frontend/src/components/InfoCardFacts.vue`,
  `src/composables/useModelRegister.ts` (`sizeClass`, `qualification`),
  `src/lib/dsgvoRecord.ts` (`dsgvoWord`), `src/views/SettingsView.vue`

---

## 2026-09-17 — Der Umzug nach ComfyUI ist abgeschlossen; die Kartengröße ist eine andere Frage

**Entscheidung:** Der Umzug nach ComfyUI gilt als abgeschlossen. Ob die Plattform auf einer 96-GB- oder einer 32-GB-Karte läuft, ist von der Frage, ob Diffusers oder ComfyUI verwendet wird, logisch unabhängig.

**Was das festlegt:** Der vollständige Test vor dem Abbau gilt als bestanden. Die sechste Bedingung dort (SD3.5 Large auf 32 GB, während die Prüfkette antwortet) ist keine Bedingung des Umzugs, sondern eine Messung des Hardware-Profils (§13) und wird gemacht, wenn die 32-GB-Karte da ist. Die Standmessung per Skript und die Formel „trägt / trägt nicht vollumfänglich" sind am 16.09. entfernt (`6337ca9d`).

**Stand am Tag der Entscheidung:** Alles, was die Flächen der Plattform von sich aus tun, läuft über ComfyUI (Stufen 2 bis 7). Über den GPU-Dienst laufen noch: die 14 Diffusers-Zwillinge (`*_diffusers`-Configs, im Config-Wähler der Canvas-Fläche wählbar), Wege im DevServer ohne Rufer (alte Text-Routen, `workshop/preload`, `workshop/unload`, `gpu-preload`, der Vorlade-Faden), und die Encoder-Fusion-Versuchsreihe direkt am Diffusers-Backend des Dienstes (`three_factor` mit `shift`, `6c96f67b`; der ComfyUI-Knoten `ai4artsed_sd3_conditioning.py` kennt `three_factor`, aber kein `shift`).

**Nachtrag 2026-10-10 (S-036):** Über den GPU-Dienst läuft außerdem der Classify-Pfad der Sicherheitskette: `my_app/services/safety_classifier.score` sendet an `POST /api/llm/classify` des Dienstes, gerufen aus `vlm_safety`, `schema_pipeline_routes`, `canvas_executor`, `commons_service` und `mean_images_routes`. Das Knotenpaket hat keine Lesung, die `classify` entspricht (`option_scores` in `_text_probes.py` ist die nächste Verwandte). Der Pfad bleibt als Ausnahme dieser Entscheidung stehen, bis eine Classify-Lesung im Paket steht; `llm_client.py` nennt ihn seit heute als die eine Ausnahme statt jede lokale Inferenz dem Knoten zuzuschreiben.

**Offen:** Stufe 8, der Abbau (§12: tote Routen, die Zwillinge, `gpu_service/` mit 62 Dateien, `ai4artsed-gpu.service`).

## 2026-09-18 — Ein Bildnetz trägt seine Zahl, keine Größenklasse

**Anlass:** Die Census-Seite zeigte SD 3.5 Large mit der Größenklasse „small", und die Größenklasse ist für Sprachmodelle gesetzt, nicht für Bildmodelle.

**Befund:** Die Größenklasse vom 12.09. (Punkt 5 des Eintrags 2026-09-12) hat ihre Schwellen an Beispielen aus Sprachmodellen (Klein bis 32 B); sie wurde auf Bildnetze angewendet, wo 8 B die Spitze des Feldes ist. Auf der Census-Seite stand „SD 3.5 Large 8,1B · small", „Flux 2 32B · small", „SDXL 3,5B · micro". Das geladene Modell war davon unberührt (`sd35_large` → `OfficialStableDiffusion/sd3.5_large.safetensors`, 16,46 GB).

**Was das festlegt:** Ein Bildnetz trägt im Register `"medium": "image"` und zeigt seine Zahl allein („8,1B"); `useModelRegister.sizeClass` gibt für ein Bildnetz keine Klasse. Die Regel vom 12.09. für ein geschlossenes Modell ohne veröffentlichte Zahl („very large") gilt weiter, auch für Gemini 3 Pro. Die Klasse bleibt bei den Sprachmodellen, an deren Beispielen die Schwellen gesetzt sind.

**Betroffene Dateien:** `devserver/config/model_register.json`, `public/ai4artsed-frontend/src/composables/useModelRegister.ts`, `devserver/tests/test_model_register.py`.

## 2026-09-18 — Das Latent Lab läuft auf jeder Karte mit SD 3.5 Large

**Anlass:** SD 3.5 Large muss auf einer 32-GB-Karte laufen, und ein Rückfall des Latent Lab auf SD 3.5 Medium kompromittiert das Ziel der Plattform.

**Befund:** `devserver/my_app/services/latent_lab_model.py` (44394fdd, 18.05.2026) gab auf Karten unter 50 GB SD 3.5 Medium (24 statt 38 MMDiT-Blöcke) an die sechs Latent-Lab-Instrumente (Surrealizer, Concept Algebra, Feature Probing, Denoising Archaeology, Attention Cartography, Composable Diffusion), dazu ein Umgebungsschalter `AI4ARTSED_LATENT_LAB_MODEL`. Die „~50 GB Spitze" dahinter war auf dem Diffusers-Introspektionspfad gemessen. Auf der RTX 6000 (95 GB) wählte es Large; auf der 32-GB-Karte, dem Hardware-Profil der Plattform, hätte jedes Instrument Medium geladen. Die Census-Seite und jede Fläche mit dem Config `sd35_large` waren nie betroffen.

**Was das festlegt:** `get_latent_lab_model_id()` gibt SD 3.5 Large, auf jeder Karte; kein Schwellwert, kein Schalter, keine Kartenlesung in diesem Modul (Prüfung: `test_gpu_card.py::test_the_resolver_reads_no_card_and_no_environment`). `download_models.sh` holt Medium nicht mehr. Funktionsname und Policy-Prüfung (`test_latent_lab_model_policy.py`) bleiben: die eine Stelle, die das Modell nennt.

**Offen (Folgeschritt):** Die Konstante `LATENT_LAB_MEDIUM` und der Parameter `medium_id` in `comfyui_chunk_support.checkpoint_for`, den acht ComfyUI-Chunks und `latent_lab_context_graphs.checkpoint_of` sind seit heute totes Geleise; `output_image_denoising_archaeology_comfyui.py` nennt in einer Fehlermeldung noch den entfernten Schalter. Drei dieser Dateien tragen am 18.09. uncommittete Arbeit; der Abbau folgt, sobald sie committet ist. **Erledigt 2026-10-10:** `LATENT_LAB_MEDIUM` und `medium_id` sind entfernt (`checkpoint_for(model_id, large_id, unet_id)`), die Fehlermeldung der Archäologie nennt den Schalter nicht mehr; die fünf Chunks lösen den Checkpoint über `comfyui_chunk_support.resolve_checkpoint` auf, die Archäologie liest ihre fünf Helfer aus demselben Modul.

**Betroffene Dateien:** `devserver/my_app/services/latent_lab_model.py`, `devserver/tests/test_gpu_card.py`, `devserver/tests/test_latent_lab_model_policy.py`, `devserver/testfiles/probe_archaeology_comfyui.py`, `download_models.sh`.

## 2026-10-10 — Die nie aktivierte Sperre der Startseite ist entfernt (S-061)

**Anlass:** Befund S-061 der Code-Sichtung vom 2026-10-10: `docs/ARCHITECTURE PART 28` beschrieb eine Sperre von Canvas und Latent Lab für kids und youth (Router-Guard auf `meta.requiresAdvanced`, Karten mit `requiresAdvanced`, Compliance-Dialog für research). Guard, Dialog und Kartenzustände standen im Code; keine Route trug das Meta, keine Karte das Flag, in der gesamten Historie nicht (`git log -S'requiresAdvanced: true'` findet keinen Commit).

**Was das festlegt:** Der tote Weg ist entfernt: der Guard in `router/index.ts`, der Sperrzustand und der Dialog in `views/LandingView.vue`, `components/ResearchComplianceDialog.vue`, die Felder `isAdvancedMode`, `isResearchMode`, `researchConfirmed`, `confirmResearch` in `stores/safetyLevel.ts`, der Block `research.*` in `en.ts`. Das Verhalten der Plattform ändert sich nicht: jede Stufe erreichte beide Flächen vorher und erreicht sie jetzt. Dass die Sperre gelten soll, entschied der Eintrag vom 2026-02-11 (Entscheidungen 2 und 3); verdrahtet war sie nie. Die Code-Sichtung legte die Frage, ob sie gelten soll, ohne diesen Eintrag vor; die Freigabe vom 2026-10-10 wählte keinen der beiden Zweige, und die Bereinigung entfernte den unverdrahteten Code. Ob die Sperre verdrahtet wird, ist offen. Dafür braucht es einen Wächter, der das Meta einer Route liest, und den Kartenzustand der Startseite; beides gibt es seit dem 2026-10-10 nicht mehr. PART 28, Abschnitt 28a, sagt das.

**Betroffene Dateien:** `public/ai4artsed-frontend/src/router/index.ts`, `views/LandingView.vue`, `components/ResearchComplianceDialog.vue` (entfernt), `stores/safetyLevel.ts`, `i18n/en.ts`, `docs/ARCHITECTURE PART 28 - Latent-Lab.md`.

## 2026-10-10 — Die Modellkarte zeigt die Tiefe, die der UI-Modus bestimmt (S-017)

**Anlass:** S-017: `ModelProvenanceCard` hat drei Tiefen (easy, medium, expert) und las sie aus einem Prop, den jeder Aufrufer auf `medium` setzte; im Kindermodus sah die Kartenrückseite die Jugend-Fassung samt `youthReflection`, der Kurzblock `provenance.kidsNote` wurde nie gezeigt. Die Sichtung hielt die Frage offen, ob die Rückseite im Kindermodus die Kurzform zeigen soll.

**Was das festlegt:** Die Karte liest den Modus aus `stores/uiMode.ts` selbst; ebenso `MediaOutputBox` für seine Expertenansichten. Was die Karte je Modus zeigt, bleibt ihr eigener Entwurf (die drei Tiefen stehen seit ihrer Anlage in der Komponente); neu ist nur, dass der Modus sie erreicht. Der Prop `uiMode` entfällt an den vier Stellen.

**Betroffene Dateien:** `components/ModelProvenanceCard.vue`, `components/MediaOutputBox.vue`, `components/MediaCardBack.vue`, `components/MediaCardFront.vue`.

## 2026-10-10 — Die Dateiendung eines Downloads kommt aus einer Tabelle und vom gelieferten Typ (S-043)

**Anlass:** S-043: fünf Flächen trugen je eine Tabelle Medientyp → Endung, drei davon gaben Audio `mp3` (`ai_persona`, `resona`, `x2x_flow`), zwei `wav` (`FooterGallery`, `canvas/OutputDrawer`) (an dieser Stelle berichtigt am 2026-10-11; bis dahin stand die Zählung vertauscht). Welche stimmt, entscheidet die Datei: der Recorder erkennt WAV oder MP3 an den Bytes (`pipeline_recorder._detect_format_from_data`), die Medienroute liefert den Typ der Datei, die sie hält.

**Was das festlegt:** `lib/downloadMedia.ts` hält die eine Tabelle (`mediaExtension`) für den Namen, mit dem eine Anfrage beginnt, und setzt nach dem Laden die Endung, die der gelieferte Typ nennt (`withExtensionOf`); ein Typ, den die Tabelle nicht kennt, lässt den Namen stehen. Die fünf Kopien sind entfernt. Sichtbar: ein Audio, das als MP3 geliefert wird, heißt `.mp3`, wo es vorher auf zwei Flächen `.wav` hieß, und umgekehrt; und weil `withExtensionOf` auf jedem Download läuft, heißt ein Bild, das eine Fläche `.png` nannte, nach dem gelieferten Typ `.webp` oder `.jpg`, ein WebM-Video `.webm`, ein 3D-Stück `.glb` statt `.bin` (ergänzt am 2026-10-11 nach der Zweitprüfung).

**Betroffene Dateien:** `lib/downloadMedia.ts`, `components/FooterGallery.vue`, `components/canvas/OutputDrawer.vue`, `views/ai_persona.vue`, `views/resona.vue`, `views/x2x_flow.vue`.

## 2026-10-10 — Eine vom Modell geschriebene Verweigerung ist eine Sperre der Stufe 2 (S-015)

**Anlass:** S-015: der Sicherheits-Präfix lässt das Modell statt einer Umformung mit einem Satz antworten (`instruction_selector.SAFETY_REFUSAL_SENTENCE`). Dieser Satz reiste als erfolgreiches Stufe-2-Ergebnis: die Stufe-2-Route antwortete `success`, der Gesamtlauf trug ihn als Interception in Stufe 3 und 4 weiter, und zwei Vergleichsflächen prüften seinen Wortlaut selbst, aus einer Kopie der Konstante.

**Was das festlegt:** Das Backend liest den Satz an einer Stelle (`is_safety_refusal`) und antwortet die Sperre, die jede Fläche schon liest: die Stufe-2-Route mit `status: blocked`, `blocked_at_stage: 2` und 403, der Gesamtlauf in der Form seiner Stufe-1-Sperre. Die Vergleichsflächen laufen über den einen Perspektivaufruf (`interceptPrompt`, ohne Adaption) und melden die Sperre an `stores/safetyEvent`; die drei englischen Ersatztexte sind weg. Sichtbar: eine Verweigerung erscheint als die Sperre der Plattform, nicht als Fehlerzeile mit dem Modelltext.

**Betroffene Dateien:** `devserver/schemas/engine/instruction_selector.py`, `pipeline_executor.py`, `my_app/routes/schema_pipeline_routes.py`, `composables/useLabRun.ts`, `views/compare/model_comparison.vue`, `views/compare/language_comparison.vue`.

## 2026-10-10 — Der News-Kurator-Agent ist zurückgezogen (S-049)

**Anlass:** Befund S-049 der Code-Sichtung vom 2026-10-10: das Startskript des News-Kurators im Wurzelverzeichnis (Nummer 7 der Startskripte, nicht Teil des öffentlichen Repositoriums) startete unbeaufsichtigt (`--permission-mode bypassPermissions`) einen Agenten, dessen Auftrag es war, die zehn wichtigsten Änderungen aus dem Entwicklungsprotokoll nach `devserver/news.json` zu schreiben. Regel 14 verlangt für jede News `title` und `summary` von Hand, jede Aussage aus ausgeliefertem Code oder ausgelieferter Oberflächenkopie, nie aus einer Agenten-Zusammenfassung, und eine adversarische Gegenprüfung vor dem Commit.

**Was das festlegt:** Skript und Agentenbrief (im Agentenverzeichnis des Assistenten, ebenfalls nicht öffentlich) sind entfernt; `scripts/public_export/exclude.txt` führt das Skript nicht mehr. News-Einträge entstehen nach Regel 14, von Hand, im selben Change wie das, was sie melden.

**Betroffene Dateien:** das Startskript des News-Kurators (entfernt), sein Agentenbrief (entfernt), `scripts/public_export/exclude.txt`.

## 2026-10-10 — Die Setup-Skripte der SwarmUI-Zeit (S-048)

**Anlass:** Befund S-048 der Code-Sichtung vom 2026-10-10: `setup.sh`, `setup_venv.sh`, `update.sh`, `transfer_models.sh` und `docs/installation/comfyui_custom_nodes_requirements.txt` beschrieben die SwarmUI-Installation unter `/opt`, die seit November 2025 abgelöst ist; `setup.sh` und `update.sh` installierten `requirements.txt` allein, obwohl deren Kopf die Reihenfolge PyTorch-Stack, requirements, Git-Pakete, SpaCy vorschreibt und `check_prerequisites.sh` Python 3.13 verlangt.

**Was das festlegt:** `setup_venv.sh` (verwies auf ein `start_webserver.sh`, das es nicht gibt) und `comfyui_custom_nodes_requirements.txt` (ohne Leser) sind entfernt. `setup.sh` verlangt `python3.13`, installiert in der Reihenfolge aus `requirements.txt` und nennt als nächste Schritte ComfyUI unter `dlbackend/ComfyUI`, `user_settings.json`, die Schlüsseldateien aus `config/llm_providers.json` und `docs/installation/INSTALLATION.md`; `update.sh` installiert in derselben Reihenfolge und kennt keinen SwarmUI-Dienst mehr. `transfer_models.sh` und `MODEL_TRANSFER.md` sind als veraltet gekennzeichnet, das Skript läuft nicht mehr an: eine Neufassung für `dlbackend/ComfyUI` braucht eine zweite Maschine zum Prüfen.

**Betroffene Dateien:** `setup.sh`, `update.sh`, `setup_venv.sh` (entfernt), `transfer_models.sh`, `docs/installation/MODEL_TRANSFER.md`, `docs/installation/comfyui_custom_nodes_requirements.txt` (entfernt).

## 2026-10-10 — Die ACE-Step-Configs sind stillgelegt, die Musik-Vorgabe nennt HeartMuLa (S-010)

**Anlass:** Befund S-010 der Code-Sichtung vom 2026-10-10: `acestep_simple` und `acestep_longnarrativeprompts` trugen den Namen „AceStep“, liefen aber über die Pipeline `music_generation` auf dem Chunk `output_music_heartmula`, ohne eigene Länge; `acestep_simple` war in `output_config_defaults.json` die Vorgabe für das Medium `music`. `acenet_t2instrumental` lief auf ComfyUIs eigenen AceStep-Knoten (`output_audio_acenet`) und stand als Karte „ACE Instrumental“ im Flow. Die Regel zur Fehlerklassifikation vom 2026-06-19 erklärt die beiden `acestep_*`-Configs für entfernt, und der Katalogkommentar in `settings_routes.py` vom selben Tag nennt ACE-Step für den Workshop-Umfang als gestrichen; die Dateien lagen weiter im aktiven Verzeichnis. `install_comfyui_nodes.sh` klonte als dritten Schritt `comfyui-sound-lab`, ein Paket, dessen Knoten kein Chunk der Plattform nennt.

**Was das festlegt:** Die drei Configs heißen `.json.disabled` (geparkt wie die sechs anderen `.json.disabled` im Verzeichnis; der Loader liest `*.json`). `"music"` nennt `heartmula_standard`, die Config, die denselben Chunk unter ihrem eigenen Namen fährt, mit derselben Länge (60 s, die `acestep_simple` als Vorgabe des Chunks bekam). Die Flow-Karte ist entfernt, der Installationsschritt ebenso; `docs/installation/COMFYUI_NODES_HELPER.md` ist für das Skript neu geschrieben, das es gibt (`COMFYUI_PATH`, zwei Schritte, die eigenen Knoten als Link). Der Chunk `output_audio_acenet.json` bleibt als Chunk der geparkten Config; kein Download-Skript holt `ace_step_v1_3.5b.safetensors`. Sichtbar: im Flow bietet das Medium „Sound" Stable Audio 3 und HeartMuLa, die Karte ACE Instrumental ist weg; ein Lauf, der für Musik keine Ausgabe-Config nennt, läuft auf `heartmula_standard`. Gehalten von `test_review_d1_findings.py` und der Vorgabenprüfung in `test_output_config_carry_list.py`.

**Betroffene Dateien:** `devserver/schemas/configs/output/acestep_simple.json.disabled`, `acestep_longnarrativeprompts.json.disabled`, `acenet_t2instrumental.json.disabled`, `devserver/schemas/output_config_defaults.json`, `views/x2x_flow.vue`, `install_comfyui_nodes.sh`, `docs/installation/COMFYUI_NODES_HELPER.md`, `INSTALLATION.md`, `SOFTWARE_VERSIONS.md`, `UBUNTU_SERVER_FRESH_INSTALL.md`, `docs/ARCHITECTURE_REQUIREMENTS.md`, `docs/QUALITAETSSTUFEN_MODELLE.md`, `devserver/scripts/probe_workshop_models.py`.

## 2026-10-10 — Drei ComfyUI-Knoten geben bei einem Fehler nicht mehr ihre Eingabe zurück (S-013)

**Anlass:** Befund S-013 der Code-Sichtung vom 2026-10-10: `ai4artsed_t5_clip_fusion`, `ai4artsed_conditioning_fusion` und `ai4artsed_vector_dimension_eliminator` fingen jede Ausnahme und gaben ihre Eingabe zurück (das CLIP-Conditioning unfusioniert, Conditioning A allein, das Conditioning unverändert mit dem Fehler im Info-String). Der Lauf sampelte ein Bild ohne die Operation und meldete Erfolg; weder DevServer noch Nutzer erfuhren davon.

**Was das festlegt:** Die drei Knoten schreiben den Fehler ins Log und werfen ihn weiter. ComfyUI meldet ihn als Fehler des Laufs, der DevServer liest den Lauf als gescheitert, die Fläche sagt es (Regel 18: ein Fehlschlag wird gesagt, nicht gezeichnet). Gehalten von `test_review_d1_findings.py` (kein `except` in den drei Dateien gibt einen Wert zurück).

**Betroffene Dateien:** `comfyui_nodes/ai4artsed_comfyui/ai4artsed_t5_clip_fusion.py`, `ai4artsed_conditioning_fusion.py`, `ai4artsed_vector_dimension_eliminator.py`.

## 2026-10-10 — Das Verborgen-Flag einer Config wird an einer Stelle gelesen (S-029)

**Anlass:** Befund S-029 der Code-Sichtung vom 2026-10-10: das Flag steht in den ausgelieferten Configs an drei Orten (`hidden` oben, `meta.hidden`, `display.hidden`), und vier Leser lasen vier Kombinationen. Die Eigenschaften-Auswahl (`schema_pipeline_routes.py`) las nur die oberste Ebene und bot acht als verborgen markierte Perspektiven an: `image_transformation` und `multi_image_transformation` (`meta.hidden`, die das Backend für Bildläufe selbst wählt) und die sechs Poesie-Perspektiven `poetry_basho`, `poetry_hoelderlin`, `poetry_mirabai`, `poetry_nahuatl`, `poetry_sappho`, `poetry_yoruba_oriki` (`display.hidden`). Die Konfigurationsliste der Einstellungen und die Verfügbarkeitsprüfung lasen nur `display`; allein das LoRA-Register las alle drei.

**Was das festlegt:** `config_loader.config_is_hidden` liest die drei Orte; die vier Leser rufen es. Sichtbar: die acht Perspektiven stehen nicht mehr in der Eigenschaften-Auswahl (über ihre ID bleiben sie ladbar). Für die Ausgabe-Configs ändert sich nichts: keine trägt das Flag oben oder unter `meta`. Gehalten von `test_review_d1_findings.py`.

**Betroffene Dateien:** `devserver/schemas/engine/config_loader.py`, `my_app/routes/schema_pipeline_routes.py`, `my_app/routes/settings_routes.py`, `my_app/services/model_availability_service.py`, `my_app/services/lora_register.py`.

## 2026-10-10 — Die Stufe-2-Komposition ist nicht mehr als veraltet markiert (S-052)

**Anlass:** Befund S-052 der Code-Sichtung vom 2026-10-10: `execute_stage2_with_optimization` trug seit seiner Einführung „DEPRECATED“ im Docstring und warf bei jedem Aufruf eine `DeprecationWarning`, während es der Stufe-2-Weg der Stufe-2-Route und des Gesamtlaufs war und ist; beide Aufrufer stehen in derselben Datei.

**Was das festlegt:** Die Funktion ist die Komposition aus Interception und Adaption, die die Routen fahren; Warnung und Markierung sind weg, der Docstring sagt, was sie tut. Wer nur eine Hälfte will, ruft `execute_stage2_interception` oder `execute_optimization` direkt. Gehalten von `test_review_d1_findings.py` (ein Aufruf wirft keine `DeprecationWarning`).

**Betroffene Dateien:** `devserver/my_app/routes/schema_pipeline_routes.py`.

## 2026-10-10 — Die ComfyUI-Config der Composable Diffusion heißt nicht mehr „(Diffusers)“ (S-059)

**Anlass:** Befund S-059 der Code-Sichtung vom 2026-10-10: `composable_diffusion.json` (Backend `comfyui`, Chunk `output_image_composable_diffusion_comfyui`) und `composable_diffusion_diffusers.json` (Backend `diffusers`) hießen in allen Sprachen gleich, „Composable Diffusion (Diffusers)“; wo beide gelistet werden, standen zwei gleiche Namen, einer davon falsch.

**Was das festlegt:** Die ComfyUI-Config heißt in jeder Sprache „Composable Diffusion“; `meta.display_name` („Composable Diffusion (SD 3.5)“) bleibt. Gehalten von `test_review_d1_findings.py`: keine Config mit Backend `comfyui` trägt „Diffusers“ im englischen Namen.

**Betroffene Dateien:** `devserver/schemas/configs/output/composable_diffusion.json`.

## 2026-10-10 — Ein Modellbezeichner ist Daten: der Diffusers-Client nimmt das Modell, das er genannt bekommt, der GPU-Dienst nennt seine Vorgabe einmal (S-026, S-051)

**Anlass:** Befund S-026 der Code-Sichtung vom 2026-10-10: neun Methoden von `my_app/services/diffusers_client.py` trugen eine HuggingFace-Kennung als Default-Argument (`stabilityai/stable-diffusion-3.5-large` siebenmal, zwei Wan-2.2-Kennungen), obwohl jeder der vierzehn Rufer in `schemas/chunks/` das Modell selbst nennt; die Prüfung `test_no_model_literals.py` sah nur Provider-Präfixe und `name:tag`-Formen. Im GPU-Dienst stand dieselbe Kennung neunmal in `routes/diffusers_routes.py` (das `DEFAULT_MODEL_ID` dort zählte die Wiederholungen selbst) und elfmal als Signatur-Default in `services/diffusers_backend.py`. Befund S-051: die Regel hatte keinen Frontend-Anteil.

**Was das festlegt:** `model_id` ist in den neun Methoden Pflichtparameter (bei vieren vor die Parameter mit Default gezogen; alle Rufer übergeben per Schlüsselwort). `gpu_service/config.py` nennt `DEFAULT_MODEL_ID`; Routen und Backend importieren es, `gpu_service/tests/test_default_model_is_data.py` hält die Kennung dort allein. Das Prüfmuster kennt `stabilityai/` und `Wan-AI/`; `latent_lab_model.py` ist als der eine Ort des Latent-Lab-Modells (Regel, `test_latent_lab_model_policy.py`) ausgenommen, die sechs Diffusers-Chunks, die ihr Modell selbst nennen, stehen als geerbte Schuld in `INHERITED_DEBT` (Obergrenze 21 → 24, nur fallend). Das Frontend (`src/**/*.ts`, `*.vue`, ohne Specs) wird mit demselben Muster geprüft, auch im `--staged`-Lauf; die veröffentlichten System-Prompts in `views/compare/system_prompts_published.ts` sind als wörtlich zitierte Dokumente erlaubt, `SettingsView.vue` (`shieldstral:3b`) ist der eine geerbte Fund.

**Betroffene Dateien:** `devserver/my_app/services/diffusers_client.py`, `devserver/tests/test_no_model_literals.py`, `gpu_service/config.py`, `gpu_service/routes/diffusers_routes.py`, `gpu_service/services/diffusers_backend.py`, `gpu_service/tests/test_default_model_is_data.py`.

## 2026-10-10 — Der Chunk erklärt seine Mehrbild-Anpassung, der Router liest sie (S-031)

**Anlass:** Befund S-031 der Code-Sichtung vom 2026-10-10: `backend_router._adapt_workflow_for_multi_image` löschte beim Mehrbild-Pfad die Knoten `120`, `121`, `122`, `123` und die Eingänge `image2`/`image3` der Knoten `115:110`, `115:111`. Das sind die Knoten-IDs genau eines Chunks (`output_image_qwen_2511_multi.json`); eine Umnummerierung im Chunk hätte den Router stumm ins Leere greifen lassen.

**Was das festlegt:** Der Chunk trägt ein Feld `multi_image_adaptation`: je optionalem Bildparameter die zu entfernenden Knoten und die zu streichenden Eingänge. Der Router liest allein dieses Feld; ein Chunk ohne das Feld bleibt unberührt. Für alle neun Kombinationen der beiden optionalen Bilder (fehlend, leer, vorhanden) liefert die neue Lesung denselben Workflow wie der alte Code (Prüfung des Pakets gegen `HEAD`), und `test_review_d2_findings.py` hält, dass der Router keine Knoten-ID des Chunks mehr nennt.

**Betroffene Dateien:** `devserver/schemas/engine/backend_router.py`, `devserver/schemas/chunks/output_image_qwen_2511_multi.json`.

## 2026-10-10 — Die Stufe, unter der ein Aufruf verbucht wird, reist mit der Anfrage (S-032)

**Anlass:** Befund S-032 der Code-Sichtung vom 2026-10-10: die Interception-Engine verbuchte jeden Cloud-Aufruf im Usage-Tracker unter `self._current_stage = "stage2"`; kein Produktionscode setzte das Attribut, nur zwei Tests. Die Übersetzung vor Stufe 4 (`pre_output/translation_en`), die Encoder-Übersetzungen und die Textausgaben der Stufe 4 (p5.js, Tone.js) zählten als Stufe 2.

**Was das festlegt:** `pipeline_executor.usage_stage_of(resolved_config)` liest `meta.stage` der Config (`pre_interception` → stage1, `interception` → stage2, `pre_output` → stage3, `output` → stage4, sonst stage2) und gibt es der `BackendRequest` als `usage_stage` mit; der Router reicht es an die `PromptInterceptionRequest`, die Engine an `_call_cloud` und `_call_aws_bedrock`. Das Attribut ist weg. Jede ausgelieferte Config nennt eine Stufe aus der Tabelle (`test_review_d2_findings.py`). Lokale Modelle verbuchen nichts; dort ändert sich nichts.

**Betroffene Dateien:** `devserver/schemas/engine/pipeline_executor.py`, `backend_router.py`, `prompt_interception_engine.py`, `devserver/tests/test_cloud_transport_callers.py`.

## 2026-10-10 — Fünf Sampling-Zahlen, die kein Modell las, sind gestrichen (S-012)

**Anlass:** Befund S-012 der Code-Sichtung vom 2026-10-10: die Engine reicht einem lokalen Modell `temperature`, `max_tokens`, `repetition_penalty` und `enable_thinking` weiter, einem Cloud-Anbieter `temperature` und `max_tokens`. `top_p` stand in 43 Interception-Configs, 10 Ausgabe-Configs, vier Chunks und einer Nutzer-Config im Repositorium und erreichte kein Modell; die Route für eigene Perspektiven nahm zusätzlich `top_k`, `min_p`, `presence_penalty` und `frequency_penalty` an und prüfte ihre Wertebereiche; `platform_modules.json` beschrieb den Interception-Pfad als einen, der sechs weitere Sampling-Zahlen erlaube.

**Was das festlegt:** Die fünf Schlüssel sind aus `ALLOWED_PARAM_KEYS` und `_PARAM_BOUNDS`, aus den Configs, Chunks und den Beispielen in PART 03 und PART 20 gestrichen; `platform_modules.json` nennt, was die Engine tatsächlich weiterreicht. Eine gespeicherte Perspektive, die einen der Schlüssel von früher trägt, wird nicht abgewiesen: `update_prompt` prüft die gereinigte Sicht; die gespeicherte Zeile behält den Schlüssel, bis ein Schreibzugriff `parameters` mitsendet (die Fläche sendet Name, Kontext und Veröffentlichung), und niemand liest ihn. Die zwei Vergleichsskripte `stage2_model_comparison.py` und `stage2_gemini_full_comparison.py` reichen `top_p` nur weiter, wo eine Config es trägt, also seither nicht mehr. Nicht gewählt wurde die andere Option der Sichtung, die Zahlen bis zum Modell durchzureichen: das veränderte das Sampling jeder Perspektive und damit die Interception selbst; wer das will, entscheidet es als Produktfrage. Gehalten von `test_review_d2_findings.py` (die erlaubten Schlüssel sind eine Teilmenge der gelesenen; keine Config, kein Chunk trägt einen der fünf) und `test_lab_prompts.py` (die Route weist sie ab).

**Betroffene Dateien:** `devserver/my_app/routes/interception_prompts_routes.py`, `devserver/my_app/knowledge/platform_modules.json`, 60 JSON-Dateien unter `devserver/schemas/`, `docs/ARCHITECTURE PART 03`, `docs/ARCHITECTURE PART 20`, `devserver/tests/test_lab_prompts.py`.

## 2026-10-10 — Die Generierungszahlen sind die des Chunks; der Großschreibungsblock der Configs auf JSON-Chunks ist gestrichen, die Configs auf Python-Chunks behalten ihren (S-011)

**Anlass:** Befund S-011 der Code-Sichtung vom 2026-10-10: zwanzig Ausgabe-Configs trugen `WIDTH`, `HEIGHT`, `STEPS`, `CFG`, `SAMPLER`, `SCHEDULER`, `FRAMES`, `FPS`, `NEGATIVE_PROMPT`, `SECONDS` (`gpt_image_1.json`: `MODEL`, `QUALITY`, `SIZE`, `BACKGROUND`, `N`). Der Router lädt den Workflow aus dem Chunk und füllt ihn über dessen `input_mappings`, deren Schlüssel kleingeschrieben sind; die Großschreibung las auf dem Generierungspfad nichts. `ltx_video.json` erklärte 1216x704, 121 Bilder, 25 Schritte, 30 fps; gelaufen sind die Chunk-Vorgaben 768x512, 97, 6, 24. Der einzige Leser war `model_meta.build_model_meta`, das Blatt auf der Rückseite einer Karte: es zeigte 25 Schritte für ein Video, das 6 lief.

**Was das festlegt:** Was läuft, sind die Vorgaben des Chunks, überschrieben durch die kleingeschriebenen Lauf-Parameter, die der Executor injiziert (`steps`, `cfg`, `width`, …). Die Großschreibungsblöcke sind aus den elf Configs auf JSON-Chunks gestrichen (nichts auf dem Generierungspfad las sie: streng äquivalent). Die neun Configs auf Python-Chunks (sechs Diffusers-Bildchunks, drei Stable-Audio-Configs) behalten ihren Block: der Router ruft `execute(**parameters)`, und der Chunk nimmt `STEPS`, `CFG`, `WIDTH`, `HEIGHT`, `NEGATIVE_PROMPT` (Stable Audio: `SECONDS`) als benannte Parameter vor seinen `DEFAULTS`; der Commit 96f7cb4 hatte auch diese neun gestrichen, die Zweitprüfung vom selben Tag fand es (Nachtrag unten). Das Blatt liest, wo der Lauf nichts meldet, nach den kleingeschriebenen Config-Parametern den Großschreibungsschlüssel und dann die `default`-Werte des JSON-Chunks; für eine Config ohne beides zeigt es keine Zahl. PART 05 beschreibt den Mechanismus. Nicht entschieden ist die Frage der Sichtung, ob eine Config einen Chunk wieder parametrisieren soll (die Platzhalter-Ersetzung des Chunk-Builders, deren Ergebnis der Router verwirft): das änderte Auflösung und Schrittzahl jeder ComfyUI-Generierung und ist eine Produktfrage. Gehalten von `test_review_d2_findings.py`.

**Betroffene Dateien:** elf Dateien unter `devserver/schemas/configs/output/`, `devserver/my_app/services/model_meta.py`, `docs/ARCHITECTURE PART 05`.

## 2026-10-10 — Der VoxCPM2-Worker nimmt die Lease für sein eigenes Laden (S-005)

**Anlass:** Befund S-005 der Code-Sichtung vom 2026-10-10: `voxcpm_service/server.py` lud die Gewichte beim Prozessstart in einem Thread, ohne eine Zulassung zu nehmen; die Lease `voxcpm-load` nahm allein der DevServer in `voxcpm_backend.is_available`, und nur, wenn er den Worker selbst startete. `2_start_voxcpm.sh` nennt den Start von Hand als vorgesehenen Weg; auf diesem Weg kamen 6774 MiB ohne Zulassung auf die Karte, und das Gatter erfuhr davon erst, wenn der nächste Hold sie als fremde Belegung maß. Regel 15: wer Gewichte lädt, nimmt die Lease, die das Laden deckt.

**Was das festlegt:** Der Worker nimmt die Lease selbst, in der Standardbibliothek (`urllib`), über die HTTP-Schnittstelle des Gatters (`POST /api/gate/lease/acquire`, `heartbeat`, `release`), so wie der GPU-Dienst seine Holds dort nimmt: `kind` `voxcpm-load`, `model_id` `voxcpm`, `required_mb` 6774 (gemessen 2026-08-26, `VOXCPM_VRAM_MB` überschreibt), `holder` `voxcpm_service`. Das Gatter findet er wie der GPU-Dienst: `AI4ARTSED_DEVSERVER_URL`, sonst `http://127.0.0.1:<PORT>` mit 17802 als Vorgabe; ein Handstart auf einem Produktionsrechner braucht `PORT=17801` in der Umgebung, das Startskript sagt es. Antwortet das Gatter nicht oder weist es ab, fragt der Worker in wachsendem Abstand (2 s bis 30 s) weiter, so lange es dauert, und lädt nichts; `/health` meldet `"gate": "waiting"`. Ein DevServer ohne Gatter-Routen (HTTP 404) lässt das Laden ohne Lease zu, einmal gesagt (`"gate": "absent"`), wie beim GPU-Dienst. Der DevServer hält beim Starten und Warten nichts mehr: Starten und `/health`-Abfrage belegen nichts; die Äußerung nimmt ihre Lease `voxcpm` wie bisher in `speak`. Die Abdeckungsprüfung (`test_gpu_admission_coverage.py`) führt den Worker als seinen eigenen Lease-Nehmer; `test_voxcpm_worker_takes_its_lease.py` stellt ein Gatter auf und hält die Reihenfolge (acquire, Laden unter dem Hold mit Heartbeats, release; Abweisung wird erneut gefragt; 404 lädt; ein noch fehlendes Gatter wird abgewartet).

**Betroffene Dateien:** `voxcpm_service/server.py`, `devserver/my_app/services/voxcpm_backend.py`, `devserver/tests/test_gpu_admission_coverage.py`, `devserver/tests/test_voxcpm_worker_takes_its_lease.py`, `2_start_voxcpm.sh`.

## 2026-10-10 — Die drei Flächen des Crossmodal Lab tragen den Perspektiv-Ring, und die Prüfung sieht sie (S-041)

**Anlass:** Befund S-041 der Code-Sichtung vom 2026-10-10: `views/latent_lab/audio_synth.vue` trug im Skript seit dem 2026-09-05 die Perspektive für beide Prompt-Felder (`openPreset`, `handlePresetSelected`, „ONE overlay serves both prompts"), das Template hatte weder `<InterceptionPresetOverlay>` noch `:show-preset-button` an den Feldern; die 70 Zeilen waren unerreichbar und wurden am selben Tag als toter Code gestrichen. Die Prüfung R3 (`test_element_structure_policy.py`) sah die Datei nicht, weil sie keinen der `SURFACE_MARKERS` trägt; dasselbe gilt für `imagebind_guidance.vue` und `mmaudio.vue`, deren geschriebene Felder nie einen Ring hatten.

**Was das festlegt:** Die Ring-Logik steht wieder im Synth, in der Form, die `mean_images.vue` seit dem 2026-10-10 hat (`interceptPrompt`, `perspectiveFailureText`, die Fehlerzeile der Fläche), und das Template bietet sie an: beide `MediaInputBox` tragen `:show-preset-button`, `:preset-busy` und `@open-preset-selector`, ein Overlay dient beiden Feldern. `imagebind_guidance.vue` (ein Feld) und `mmaudio.vue` (Prompt und Negativ-Prompt, ein Overlay) sind genauso verdrahtet. `SURFACE_MARKERS` kennt `class="xm-lab"`, die Wurzel der drei Flächen; R3 prüft sie seither mit (Beispielliste und Ring an jedem geschriebenen Feld). Die Registry zählt achtzehn Ringe.

**Betroffene Dateien:** `views/latent_lab/audio_synth.vue`, `imagebind_guidance.vue`, `mmaudio.vue`, `devserver/tests/test_element_structure_policy.py`, `docs/ELEMENT_STRUCTURE_REGISTRY.md`.

## 2026-10-10 — Kein `v-html` mehr: zwei Einstellungs-Strings und die Startseiten-Icons (S-038)

**Anlass:** Befund S-038 der Code-Sichtung vom 2026-10-10: die Registry schreibt für Text „NIE v-html" vor und nennt die kanonischen Bausteine `EmphasisText` und `MarkdownLiteText`; `SettingsView.vue` rendert zwei Übersetzungs-Strings mit `<strong>`-Markup über `v-html`, `LandingView.vue` fünf SVG-Icons aus Code-Strings.

**Was das festlegt:** `settings.dsgvo.notCompliant` und `settings.presets.help` tragen in `en.ts` `**…**` statt `<strong>…</strong>` und laufen durch `MarkdownLiteText` (der Hilfeabsatz wird dafür ein `div.help`; die Regel `.section .help` gilt unverändert). Die anderen Sprachdateien tragen das Markup noch; der Arbeitsauftrag WO-2026-10-10-D sagt dem Übersetzer, es in Sternchen zu wandeln, und bis dahin zeigt die nichtenglische Einstellungsseite in diesen zwei Sätzen die Tag-Zeichen. Die Icons der Startseite sind je ein `{ viewBox, d }`, gezeichnet durch ein `<svg>` mit `<path :d>` im Template, mit denselben Attributen wie zuvor. Eine Vitest-Prüfung hält, dass kein Template `v-html` trägt.

**Betroffene Dateien:** `views/SettingsView.vue`, `views/LandingView.vue`, `i18n/en.ts`, `i18n/WORK_ORDERS.md`, `views/__tests__/noHtmlAndNoServerBody.spec.ts`.

## 2026-10-10 — Die englischen Literale der Sichtung, erster Teil: Fehlerzeilen, Regler, Knoten, Einstellungen (S-016, Teil A)

**Anlass:** Befund S-016 der Code-Sichtung vom 2026-10-10: nutzersichtbare Zeichenketten als englische oder deutsche Literale im Code, und fünf Latent-Lab-Instrumente, die den Antwortkörper des Servers (`err.response?.data?.error`) auf den Schirm schreiben, obwohl die Entscheidung vom 2026-09-05 den Körper im Log hält und `generationErrorFor` den Satz mit Status liefert.

**Was das festlegt:** Die Fehlerzeilen von `attention_cartography`, `composable_diffusion`, `denoising_archaeology`, `feature_probing` (drei Stellen), `concept_algebra`, `fusion_workbench` (reichte den Körper an `generationErrorFor` statt des Fehlers) und `mean_images` (`requestMessage`) sagen `generationErrorFor(t, err)`. Zu Schlüsseln in `en.ts` wurden: die Regler- und Effektbeschriftungen des Synth, die Knoten-Beschriftungen des Canvas (`canvas.stage.*`, 20 Schlüssel; Produktnamen und Notation wie `CFG` bleiben), `DSGVO` und die Zeitraum-Chips der API-Verwaltung, `VRAM:` und die relativen Zeiten des Backend-Status, die zwanzig Sprachbeschreibungen des Chip-Wählers (die Endonyme bleiben), die Statusleiste der Eisberg-Animation (die vorhandenen `edutainment.pixel.*`-Schlüssel), die Knöpfe im Audio-Frame des Code-Sandkastens, `Incorrect password` / `Authentication error` des Einstellungs-Logins, `[Connection error]` der Persona, `Invalid preset file` des Synth, `no English text came back` der Mittelbilder, `Unknown error` in VLM-Vergleich und Training. Arbeitsauftrag WO-2026-10-10-D. Noch offen (Teil B): `components/SessionExportView.vue` (die ganze Fläche, rund sechzig Strings) und die Literale in `stores/`, `services/`, `composables/`, die die Sichtung nicht nennt. `views/AnimationTestView.vue` bleibt außerhalb der i18n: eine Testseite der Entwicklung, keine Fläche für Lernende.

**Betroffene Dateien:** `views/latent_lab/{attention_cartography,composable_diffusion,denoising_archaeology,feature_probing,concept_algebra,fusion_workbench,mean_images,audio_synth}.vue`, `views/{ai_persona,TrainingView}.vue`, `views/compare/vlm_analysis_comparison.vue`, `components/{SettingsAuthModal,ApiManagementTab,BackendStatusTab,CodeSandbox,LanguageChipSelector}.vue`, `components/canvas/StageModule.vue`, `components/edutainment/IcebergAnimation.vue`, `i18n/en.ts`, `i18n/WORK_ORDERS.md`.

## 2026-10-10 — Die englischen Literale der Sichtung, zweiter Teil: die Export-Fläche (S-016, Teil B)

**Anlass:** Befund S-016 der Code-Sichtung vom 2026-10-10: `components/SessionExportView.vue`, der Forschungsdaten-Export der Einstellungsseite, trug jede Beschriftung als Literal, darunter das deutsche „Modus" als Spaltenkopf in jeder Sprache.

**Was das festlegt:** 63 Schlüssel `sessionExport.*` in `en.ts` (Überschrift, Zähler, Filter-Rubriken, Tabellenköpfe, Knöpfe, die Detailansicht mit ihren Inline-Rubriken, der Hinweis auf das fehlende Video, die Fehlerzeilen des Downloads und der ZIP-Exporte, die Seitengröße, die Zelle ohne Wert); der Spaltenkopf heißt auf Englisch „Mode". Die Zweitprüfung vom selben Tag fand sechs Literale, die der erste Durchgang und seine Prüfung übersehen hatten (Zifferanfang, Text neben einer Interpolation, `'N/A'` in einer Interpolation), die verschärfte Prüfung drei weitere („Entities (…)", „Less", „+n more"); sie sieht diese Formen seither und lässt Schlüssel von `t()` und Werte neben einem Vergleich (`=== 'asc'`) stehen. Das Schließ-Zeichen des Dialogs steht als `×` statt als `&times;`, wie in den übrigen Komponenten. Die Texte des erzeugten PDF-Berichts (im Skript, `Timestamp: …`, `Stage2-Config: …`) sind nicht Oberfläche und bleiben, wie sie sind. Arbeitsauftrag WO-2026-10-10-E. Damit ist S-016 abgeschlossen bis auf die Literale in `stores/`, `services/` und `composables/`, die die Sichtung nicht nennt, und `views/AnimationTestView.vue` (Entscheidung vom selben Tag, Teil A).

**Betroffene Dateien:** `components/SessionExportView.vue`, `i18n/en.ts`, `i18n/WORK_ORDERS.md`.

## 2026-10-10 — Die drei Tabellen des Canvas tragen Schlüssel, die Texte stehen in `en.ts` (S-045)

**Anlass:** Befund S-045 der Code-Sichtung vom 2026-10-10: `types/canvas.ts` trug in `INTERCEPTION_PRESETS` (24), `RANDOM_PROMPT_PRESETS` (5) und `NODE_TYPE_DEFINITIONS` (15 Typen mit Beschreibung) Oberflächentexte in acht Sprachen außerhalb von `en.ts`; jede Änderung verlangte acht Handübersetzungen in einer Typdatei, und die Texte waren der Übersetzungsprüfung entzogen.

**Was das festlegt:** Die Tabellen tragen `labelKey` beziehungsweise `labelKey`/`descriptionKey` (`canvas.interceptionPresets.<id>`, `canvas.randomPrompt.<id>`, `canvas.nodeTypes.<id>.label|description`); die englischen Texte stehen in `en.ts`. Die fünf Leser rufen `t` (`StageModule`, `ModulePalette`, `fusion_workbench`) beziehungsweise `i18n.global.t(key, {}, { locale })` (`lib/canvasPresets.ts`, mit dem Locale des Kontexts wie bisher `localized`; die Preset-Spezifikation ebenso mit `en`). Die bisherigen Übersetzungen (bg, de, tr, ko, uk, fr, es) stehen im Arbeitsauftrag WO-2026-10-10-E zur wortgleichen Übernahme; bis der Übersetzer sie einträgt, zeigt der Canvas diese Beschriftungen außerhalb des Englischen auf Englisch. `test_review_d5_findings.py` hält, dass jede Tabelle nur Schlüssel nennt, die `en.ts` trägt.

**Betroffene Dateien:** `types/canvas.ts`, `components/canvas/StageModule.vue`, `components/canvas/ModulePalette.vue`, `views/latent_lab/fusion_workbench.vue`, `lib/canvasPresets.ts`, `lib/__tests__/canvasPresets.spec.ts`, `i18n/en.ts`, `i18n/WORK_ORDERS.md`.

## 2026-10-10 — Die Trainingsrouten antworten einen Fehler als `{"error"}` (S-024)

**Anlass:** Befund S-024 der Code-Sichtung vom 2026-10-10: für dieselbe Art Ergebnis antworteten die Routen in fünf Formen; `training_routes.py` allein antwortete Fehler als `{"message": …}` (17 Stellen), und `views/TrainingView.vue` las diese Form. PART 11 dokumentiert `{"error", "status", "details"}`.

**Was das festlegt:** Die 17 Fehlerantworten der Trainingsrouten tragen `error`; die drei Erfolgsantworten („Training started", „Training stopped", „Project files deleted successfully") behalten `message`. Die Trainingsseite liest `error`; `latent_lab/lora_reach.vue` las ohnehin über `useLabRun`. Die Fehlerform der Plattform ist `{"error": <Satz>}` mit dem HTTP-Status, `success: false` nur dort, wo eine Fläche darauf verzweigt (PART 11). Nicht gebaut wurde der von der Sichtung vorgeschlagene Helfer `refusal(status, error, **fields)`: die übrigen Routen antworten `{"error"}` bereits ohne ihn, und die beiden Formen mit `success`/`status` (speech, parrot, canvas, mean_images, …) werden von ihren Flächen gelesen; sie umzustellen änderte jede dieser Flächen und ist hier nicht entschieden. `sse_routes.py` ist mit S-069 bereits weg. Gehalten von `test_review_d5_findings.py`.

**Betroffene Dateien:** `devserver/my_app/routes/training_routes.py`, `views/TrainingView.vue`.

## 2026-10-10 — Die neunzehn Dateien des Befunds S-037 malen Hintergrund und Rand mit den Flächen-Token (S-037)

**Anlass:** Befund S-037 der Code-Sichtung vom 2026-10-10: 141 Deklarationen in 19 Dateien (`SettingsView`, `canvas_workflow`, `cover_band`, `AnimationTestView`, die vier Einstellungs-Reiter, `PlatformVoice`, `ChatOverlay`, `AudioRecordWidget`, `MediaInputBox`, `FooterGallery`, `DokumentationModal`, `SessionExportView`, `StageModule`, `ConfigSelectorModal`, `ZoomControls`, `OutputDrawer`) trugen ein neutrales dunkles Literal auf Hintergrund oder Rand (`#333`, `#3a3a3a`, `#444`, `#555`, `#334155`, `#475569`, `#121212`, `#0a0a1a`, `rgba(0,0,0,a)`, `rgba(51,65,85,a)`); Regel 7 verlangt dort die Flächen-Token, und diese Flächen folgten dem in den Einstellungen gewählten Ton nicht.

**Was das festlegt:** Die Zuordnung nach dem Vorschlag der Sichtung. Ränder und `outline` tragen `var(--surface-4)`. Hintergründe: `#333`, `#333333` und `#3a3a3a` tragen `var(--surface-3)`, unter `:hover`, `:active`, `.active` und `:focus` `var(--surface-4)`; `#444`, `#555`, `#334155` und `#475569` tragen `var(--surface-4)`; `#121212` trägt `var(--surface-1)`, `#0a0a1a` `var(--bg-base)`. Die Alphas tragen `rgb(var(--bg-base-rgb) / a)` beziehungsweise `rgb(var(--surface-4-rgb) / a)`. Nicht angefasst: fünf `box-shadow`, ein `text-shadow` und zwei `color` mit denselben Werten; ein Schatten und eine Textfarbe sind keine Fläche. Sichtbar im Standardton (96 % Schwarz, neutral), nach der Zählung der Zweitprüfung vom selben Tag: 113 Ränder tragen `#333333`, davon 62 unverändert (sie waren `#333`), 9 von `#3a3a3a`, 20 von `#444`, 8 von `#555` und 25 von den Schiefertönen `#334155`/`#475569`; 11 Hintergründe aus `#444`, `#555`, `#334155` oder `#475569` tragen `#333333`; `#121212` wird `#141414`; `#0a0a1a` (ein Nachtblau) wird `#0a0a0a`; 13 schwarze Alphas werden `rgb(10 10 10 / a)`, 2 Schiefer-Alphas `rgb(51 51 51 / a)`. Ein Hintergrund aus `#333` oder `#3a3a3a` kam in den neunzehn Dateien nicht vor; die Zuordnung auf `var(--surface-3)` hat nichts getroffen, und die frühere Fassung dieses Eintrags behauptete einen Schritt, den es nicht gab. In jedem anderen Ton folgen diese Flächen zum ersten Mal dem Ton. Nicht angefasst, weil die Sichtung sie nicht nennt und sie keine neutralen Flächen sind: die zwei Status-Felder `#5a5a5a` in `ModelMatrixTab` (neben `#e53935`, eine Farbe des Status) und der warm getönte Rand `#3a3630` in `PlatformVoice`. Gehalten von `devserver/tests/test_review_d6_findings.py`: die neunzehn Dateien, Deklaration für Deklaration, einzeilige Regeln eingeschlossen, und jedes genannte Token steht in `base.css`.

**Betroffene Dateien:** die neunzehn genannten unter `public/ai4artsed-frontend/src/`, `devserver/tests/test_review_d6_findings.py`.

## 2026-10-10 — Zwei Export-Wurzeln bleiben; `config` benennt beide, jeder genannte Dienst liest sie dort, und der Wissensindex folgt `config` beim Aufruf (S-055, S-077)

**Anlass:** Befund S-055 der Code-Sichtung vom 2026-10-10: zwei Export-Wurzeln, `exports/` an der Repository-Wurzel (`config.EXPORTS_DIR`, `config.JSON_STORAGE_DIR`: Laufdaten, Legacy-Migration, `execution_history`, `setup.sh`) und `devserver/exports/` (`config.KNOWLEDGE_*`: Wissensbibliothek, Index, AILit-Build, Pilotläufe); der Kommentar in `config.py` beschrieb den Unterschied und entschied ihn nicht. Befund S-077: sechzehn Stellen leiteten denselben Ort aus dem eigenen `__file__` ab, in zwei Schreibweisen für dieselbe Tiefe (`parents[2]`, `parent.parent.parent`); die Docstrings von `resona_memory.py` und `resona_journal.py` nannten `config.JSON_STORAGE_DIR` als Quelle, die der Code nicht las; `knowledge_library.DB_PATH` und `evidence_duty.INDEX_PATH` standen neben `config.KNOWLEDGE_INDEX_DB`, so dass ein Test, der `config` umlenkte, beide Leser auf dem echten Index ließ, und `ingest_research_literature.py` prüfte die Frische des Index am Modulattribut.

**Was das festlegt:** Die zwei Wurzeln bleiben zwei. Sie zusammenzulegen verschöbe auf jeder installierten Maschine Daten (Sessions, Index, Resona-Speicher) und ist hier nicht entschieden; der Grund steht im Kommentar von `config.py`. `config` benennt die Wurzel unter `devserver/` öffentlich: `DEVSERVER_DIR`, `DEVSERVER_EXPORTS_DIR`, `DEVSERVER_JSON_DIR`, `DEVSERVER_DATA_DIR`. Die Sichtung schlug `DATA_DIR = BASE_DIR / "data"` vor, also `<repo>/data`; die drei Module, die `data/` benutzen, lesen `<devserver>/data`, und dort bleibt es, weil die Umstellung sonst den Übersetzungs-Cache, das Nutzungsprotokoll und die BBQ-Läufe verschöbe. Keine der von S-077 genannten Stellen leitet mehr ab: die fünf Speicher (`canvas_graph_export`, `canvas_workflow_store`, `knowledge_areas`, `resona_journal`, `resona_memory`) lesen `config.DEVSERVER_JSON_DIR`, `thumbnails` `config.EXPORTS_DIR`, `translation_cache`, `usage_tracker` und `bbq_runs` `config.DEVSERVER_DATA_DIR`, `local_llm_weights`, `local_media_weights` und `text_presets` (dasselbe Muster, von der Sichtung nicht genannt) `config.DEVSERVER_DIR`, die App-Fabrik, `settings_routes` (vier Stellen) und `static_routes` `config.JSON_STORAGE_DIR`. `knowledge_library.index_db_path()` und `evidence_duty.index_path()` lesen `config.KNOWLEDGE_INDEX_DB` beim Aufruf; die beiden Modulattribute sind weg, und die vier Wissens-Tests, die sie neben `config` setzten, setzen nur noch `config`. Die übrigen Modulkonstanten bleiben Konstanten zur Importzeit, wie bisher; ein Lesen zur Aufrufzeit änderte jede Verwendungsstelle ohne Befund. Jeder Pfad ist derselbe Ort wie vorher; an sieben Stellen (`thumbnails`, die App-Fabrik, `settings_routes`, `static_routes`) ist die Schreibweise seither aufgelöst (`resolve()`), wo sie es nicht war, was nur in einem über einen Symlink erreichten Checkout einen anderen String ergibt und nirgends verglichen wird. `test_review_d7_findings.py` hält das und hält, dass kein Modul unter `services/`, `routes/` und die App-Fabrik `exports/`, `data/` oder eine eigene Devserver-Wurzel aus `__file__` ableitet. Die weiteren `__file__`-Ableitungen für `schemas/`, `config/*.json` und die Wurzeldateien nennt die Sichtung nicht; sie bleiben. S-123 (die Wissens-Skripte leiten Interpreter und Pfade selbst ab; ein `reindex()`) bleibt offen.

**Betroffene Dateien:** `devserver/config.py`, vierzehn Module unter `devserver/my_app/services/`, `devserver/my_app/__init__.py`, `devserver/my_app/routes/settings_routes.py`, `devserver/my_app/routes/static_routes.py`, `devserver/scripts/ingest_research_literature.py`, `devserver/tests/test_knowledge_areas.py`, `test_knowledge_curation.py`, `test_knowledge_cancel.py`, `test_upload_gate_routes.py`, `devserver/tests/test_review_d7_findings.py`.

## 2026-10-10 — Nachtrag zur Zweitprüfung des Pakets D4 (S-016 Teil A, S-038, S-041)

**Anlass:** Die adversarische Zweitprüfung vom selben Tag widerlegte sieben Aussagen des Commits c8f357f: der Schlüssel `latentLab.probing.promptBFailed` stand unter `latentLab.imageLab.tabs.probing`, so dass ein Fehlschlag von Prompt B den Schlüsselpfad anzeigte; die `success:false`-Zweige von fünf Instrumenten schrieben weiter den Antwortkörper (`response.data.error`) und englische Literale („Generation failed", „No probing data in response") in ihre Fehlerzeile, während die Prüfung nur die optional verkettete Form sah; die Prüfung auf `v-html` las nur den Text vor dem ersten `<script` und war in achtzehn Dateien blind, in denen das Skript vor dem Template steht; die drei Crossmodal-Flächen schrieben den Fehlschlag der Perspektive an den Fuß der Ausgabe statt unter das Feld, wie die Registry es für den Ring beschreibt; der Sprachchip-Wähler übersetzte seine Beschreibungen einmal beim Aufbau; „siebzehn Ringe" waren achtzehn; der Arbeitsauftrag behauptete „letter for letter" für drei Texte, die sich geändert hatten.

**Was das festlegt:** Der Schlüssel steht unter `latentLab.probing`. Die `success:false`-Zweige der fünf Instrumente (`feature_probing`, `attention_cartography`, `concept_algebra`, `composable_diffusion`, `denoising_archaeology`) sagen den Satz der Plattform (`generationErrorFor(t, body)`; bei fehlender Nutzlast `generationError.unknown`); der Antwortkörper bleibt im Log, wie die Registry es für `useLabRun` festhält. Die Prüfung `noHtmlAndNoServerBody.spec.ts` streicht jeden Skriptblock vor dem Suchen und sieht beide Schreibweisen von `response.data.error ||`. Die drei Crossmodal-Flächen (`audio_synth`, `imagebind_guidance`, `mmaudio`) tragen `perspectiveError` in `.lab-prep-err` unter dem Feld (bei zwei Feldern unter dem Paar), wie `mean_images`; der Fuß der Ausgabe behält den Fehler des Laufs. Der Sprachchip-Wähler hält seine Listen als `computed`, so dass ein Sprachwechsel die Beschreibungen mitnimmt. Sichtbare Änderungen, die der Commit c8f357f nicht nannte und die hier nachgetragen sind: die Statusleiste der Eisberg-Animation liest die bestehenden Schlüssel `edutainment.pixel.*` und zeigt auf Deutsch „Grafikkarte", „Energieverbrauch", „CO₂-Menge" statt „Grafikkarte", „Energie", „CO₂"; die zwei Zeilen „Unknown error" (TrainingView, vlm_analysis_comparison) sagen den Satz der Plattform; die zwei Einstellungs-Texte in `MarkdownLiteText` tragen dessen Absatzabstand und `font-weight: 600` für die Hervorhebung statt der Standardwerte des früheren `<p v-html>`; das Negativ-Prompt-Feld von `mmaudio` trägt als einziges Negativfeld der Plattform einen Perspektivring, weil die Policy jedes geschriebene Prompt-Feld einer `xm-lab`-Fläche so verlangt.

**Betroffene Dateien:** `i18n/en.ts`, `i18n/WORK_ORDERS.md`, `views/__tests__/noHtmlAndNoServerBody.spec.ts`, `views/latent_lab/feature_probing.vue`, `attention_cartography.vue`, `concept_algebra.vue`, `composable_diffusion.vue`, `denoising_archaeology.vue`, `audio_synth.vue`, `imagebind_guidance.vue`, `mmaudio.vue`, `components/LanguageChipSelector.vue`, `docs/ELEMENT_STRUCTURE_REGISTRY.md`.

## 2026-10-10 — Nachtrag zur Zweitprüfung des Pakets D2: die neun Configs auf Python-Chunks tragen ihren Großschreibungsblock wieder (S-011)

**Anlass:** Die adversarische Zweitprüfung vom selben Tag widerlegte die Aussage des Commits 96f7cb4, nichts auf dem Generierungspfad lese die Großschreibung: der Router ruft einen Python-Chunk mit `execute(**parameters)` (`backend_router.py`), und die sieben Diffusers-Chunks nehmen `STEPS`, `CFG`, `WIDTH`, `HEIGHT`, `NEGATIVE_PROMPT` (Stable Audio: `SECONDS`) als benannte Parameter, vor ihren `DEFAULTS`. Mit dem Streichen lief auf dem Zweig zwischen 96f7cb4 und diesem Commit `sd35_large_diffusers` mit cfg 4.5 statt 5.5, und `stableaudio_music`, `stableaudio_open` (47,6 s) und `stableaudio_sfx` (12 s) rechneten 30 s; die fünf übrigen Diffusers-Configs trugen Werte gleich den `DEFAULTS`. Das Blatt zeigte für die neun Configs ohne JSON-Mapping (sieben auf Python-Chunks, `wan22_i2v_video`, `wan22_t2v_video_fast`) keine Zahl mehr, was der Commit nicht nannte.

**Was das festlegt:** Die neun Configs auf Python-Chunks tragen ihren Block wieder, Schlüssel für Schlüssel wie vor 96f7cb4, beschränkt auf die Schlüssel, die die Signatur des Chunks benennt (`SAMPLER` und `SCHEDULER` von `sd35_large_diffusers` nahm der Chunk nur über `**kwargs` entgegen; sie bleiben gestrichen). Die elf Configs auf JSON-Chunks bleiben ohne Block. Die Regel: ein Großschreibungsschlüssel steht in einer Ausgabe-Config nur, wenn ihr Python-Chunk ihn als Parameter benennt; `test_review_d2_findings.py` hält sie und die vier Werte. Das Blatt liest nach den kleingeschriebenen Config-Parametern den Großschreibungsschlüssel und erst dann die `default`-Werte des JSON-Chunks. Für die zwei Wan-2.2-Configs, deren Chunk kein `steps`/`cfg`-Mapping trägt, zeigt es keine Zahl, wo es bis 96f7cb4 die Zahl des gestrichenen Blocks zeigte (4 Schritte, cfg 1.0), die der Workflow nicht las; das ist die eine sichtbare Änderung von S-011, die bleibt.

**Betroffene Dateien:** neun Dateien unter `devserver/schemas/configs/output/`, `devserver/my_app/services/model_meta.py`, `devserver/tests/test_review_d2_findings.py`, `docs/ARCHITECTURE PART 05`.

## 2026-10-10 — Nachtrag zur Zweitprüfung des Pakets D1 (S-010, S-013, S-029)

**Anlass:** Die adversarische Zweitprüfung vom selben Tag widerlegte fünf Aussagen des Commits 77811a7: `parrot_service.py` sagte weiter, der Flow biete ACE Instrumental; `docs/installation/INSTALLATION.md` nannte ACE-Step als Alternative zu HeartMuLa und `SWARMUI_PATH` an zwei Stellen, obwohl `config.py` die Variable nicht liest und die Nebenbefund-Zeile 18 des Umzugs als erledigt galt; `devserver/testfiles/simulate_workshop_260306.py` sendet `acenet_t2instrumental` als eine von 119 Anfragen; die Aussage, kein Chunk nenne einen Knoten von `comfyui-sound-lab`, stand ohne Beleg; die Entscheidung nannte das Medium des Flows „Musik".

**Was das festlegt:** Der Kommentar, die zwei Sätze und die Entscheidung sagen, was ist: der Flow bietet unter „Sound" Stable Audio 3 und HeartMuLa. Die Zeile des Wiedergabe-Skripts bleibt, weil das Protokoll das Protokoll ist (Regel 11); ein Kommentar davor sagt, dass diese Anfrage seit dem 2026-10-10 einen Fehler beantwortet. Beleg für die vier Knoten von `output_audio_acenet.json`: `TextEncodeAceStepAudio` und `EmptyAceStepLatentAudio` stehen in ComfyUIs eigenem `comfy_extras/nodes_ace.py` (Zeilen 9 und 64), `VAEDecodeAudio` und `SaveAudioMP3` in `comfy_extras/nodes_audio.py` (Zeilen 115 und 188), gelesen am 2026-10-10 vom Hauptzweig; der Chunk braucht `comfyui-sound-lab` nicht. Nicht geändert: `install_comfyui_nodes.sh` verlangt ComfyUIs venv, `2_start_comfyui.sh` läuft ohne dieses venv auf dem System-Python; welche Seite recht hat, ist eine Entscheidung über die Installation und hier offen.

**Betroffene Dateien:** `devserver/my_app/services/parrot_service.py`, `docs/installation/INSTALLATION.md`, `devserver/testfiles/simulate_workshop_260306.py`.

## 2026-10-10 — Nachtrag zur Zweitprüfung des Pakets C (S-021, S-047, S-022, S-058)

**Anlass:** Die adversarische Zweitprüfung vom selben Tag widerlegte vier Aussagen des Commits bcef326: `5_pullanddeploy.sh` startete die Einheit `ai4artsed-comfyui` bedingungslos neu, die `install_systemd_services.sh` nicht schreibt (dort startet das Backend ComfyUI selbst), so dass der Deploy unter seiner ERR-Falle mit „Unit not found" abbrach; `_lib.sh` hielt „eine Datei unter ihrem Endnamen ist eine ganze Datei" auch dort, wo wget ein von aria2c vorbelegtes Fragment voller Länge mit HTTP 416 als vollständig nahm und die Nullen unter dem Modellnamen ablegte; PART 14 nannte als `--staged`-Prüfungen drei, die der Hook unter pytest auf einer `checkout-index`-Kopie laufen lässt, und ließ die drei i18n-Prüfungen aus; `setup.sh` sagte, das Startskript setze PORT 17802, den die Config setzt. Die Commit-Nachricht zählte sechs Fälle, es sind sieben.

**Was das festlegt:** Der Deploy startet GPU-Dienst und Backend neu und die ComfyUI-Einheit nur, wo `systemctl list-unit-files` sie kennt. `download_file` streicht vor einem wget-Lauf ein Fragment, neben dem aria2cs Steuerdatei `.part.aria2` liegt, und lädt neu; ein Fragment von wget setzt aria2c mit `-c` an seiner Größe fort, dort wird nichts gestrichen. `test_download_resumes_a_partial_file.py` hält beide Fälle (die Stand-ins antworten für aria2c und wget). PART 14 und `setup.sh` sagen, was ist. Nicht geändert, als Entscheidung über die Installation offen: `install_comfyui_nodes.sh` verlangt ComfyUIs venv und `2_start_comfyui.sh` läuft ohne es auf dem System-Python (S-022); die drei Forschungsskripte lesen ihren Schlüssel über `my_app.services.llm_providers`, was `my_app` und damit Flask lädt und einen fehlenden Schlüssel als `""` statt als `FileNotFoundError` beantwortet (S-058).

**Betroffene Dateien:** `5_pullanddeploy.sh`, `_lib.sh`, `setup.sh`, `docs/ARCHITECTURE PART 14`, `devserver/tests/test_download_resumes_a_partial_file.py`.

## 2026-10-10 — Nachtrag zur Zweitprüfung des Pakets D3: die Warteschlange ist nicht Startzeit (S-005)

**Anlass:** Die adversarische Zweitprüfung vom selben Tag widerlegte vier Aussagen des Commits cfdcaac. Bis dahin nahm der DevServer die Ladesperre selbst, und eine Abweisung des Gates erreichte den Router als `GpuBusyError`; seit der Worker sie selbst nimmt, las das Backend nur `loaded` und `error` seiner `/health`, nicht das neue Feld `gate`, so dass eine belegte Karte nach `VOXCPM_STARTUP_TIMEOUT` (300 s) als „nicht installiert" beantwortet wurde und der Worker lud, nachdem der Aufrufer abgewiesen war. `_acquire` fing `URLError`, `OSError` und `ValueError`, nicht `http.client.HTTPException` (eine abgerissene Antwort des Gates beendete den Ladevorgang endgültig). Der Kommentar zum Halter behauptete, der Name mache die Einstellungs-Zeile „in use" (sie liest den KIND der Sperre). Die Abdeckungsprüfung verlangte vom Worker nur den Teilstring `gpu_lease`, den seine eigene Definition erfüllt.

**Was das festlegt:** `_wait_for_ready` zählt die Zeit, in der `/health` `"gate": "waiting"` meldet, nicht als Startzeit; sie ist die Warteschlange des Gates, begrenzt durch `GPU_ADMISSION_ACQUIRE_TIMEOUT_S`, und wenn die ausläuft, wird der Aufrufer mit `GpuBusyError(reason="wait_timeout")` abgewiesen, das der Router wie bisher als „belegt" weitergibt. `_acquire` fragt auch nach einer abgerissenen Antwort wieder; ein Herzschlag, der nach der Freigabe eine 404 erhält, meldet keinen Fehler mehr; der Worker schreibt beim Start, welches Gate er fragt, und `2_start_voxcpm.sh` zeigt es. Die Abdeckungsprüfung verlangt einen Aufruf von `gpu_lease(` oder `gpu_lease_sync(`, keine Definition. Gehalten von `test_voxcpm_backend_waits_in_the_queue.py` (drei Fälle) und einem siebten Fall in `test_voxcpm_worker_takes_its_lease.py`.

**Betroffene Dateien:** `voxcpm_service/server.py`, `devserver/my_app/services/voxcpm_backend.py`, `devserver/tests/test_gpu_admission_coverage.py`, `devserver/tests/test_voxcpm_worker_takes_its_lease.py`, `devserver/tests/test_voxcpm_backend_waits_in_the_queue.py`, `2_start_voxcpm.sh`.

## 2026-10-10 — Stufe 4 bleibt dreimal gebaut: Befund S-001 ist bewertet und nicht ausgeführt, Befund S-006 ebenso

**Anlass:** Befund S-001 der Code-Sichtung vom 2026-10-10 (Stufe 4 dreimal in `schema_pipeline_routes.py`, mit abweichenden Speicherblöcken) und Befund S-006 (vier Routen-Module dienen dem Rest des Systems als Dienstschicht: elf Dateien importieren aus `chat_routes`, zehn aus `settings_routes`, sechs aus `schema_pipeline_routes`). Beide tragen die Stufe „hoch" und den Aufwand L beziehungsweise M. Die Bereinigung vom 2026-10-10 stand unter der Bedingung, dass jede Umformung streng verhaltensgleich ist und jede Korrektur auf den benannten Defekt beschränkt bleibt.

**Was das festlegt:** S-001 wird nicht nach dem Vorschlag der Sichtung ausgeführt. Die Divergenztabelle in `docs/analysis/STAGE4_DIVERGENZ_2026-10-10.md` zeigt, dass die drei Bauten in neun Dimensionen auseinanderlaufen (Aufruf, Seed, Latent, Medienzweige, VLM-Prüfung, Recorder, Buchung, Fehlerform, Ausgabetypen) und dass keine der zwei vorgeschlagenen Umstellungen verhaltensgleich wäre: (i) die Schleife von `_run_interception_pipeline` auf `execute_generation_stage4` setzte eine Signatur voraus, die `custom_params`, `prompt_3` und `run_vlm_safety` nicht kennt, ließe Stufe 3 doppelt oder unübersetzt laufen und änderte die Antwortform; (ii) der Speicherblock der Direktroute durch `execute_stage4_generation_only` nähme Direct, Surrealizer und jedem Latent-Lab-Instrument seine Parameter und Nutzlasten, weil `execute_stage4_generation_only` sie weder annimmt noch `output_result.metadata` zurückgibt. Was eine Vereinheitlichung vorher braucht, ist je Dimension eine Entscheidung, welches Verhalten das richtige ist; die Tabelle nennt die Kandidaten (das Nullen des Cloud-Seeds, der Latent, der prompt_id-Rückfall, `expect_image`, `save_error` bei einer VLM-Sperre, `CURRENT_OUTPUT_CONFIG` auf der Direktroute, das Literal `backend: 'diffusers'`, der stille Erfolg mit einer URL ins Leere). Zwei Nebenbefunde der Tabelle sind festgehalten und nicht geändert: keine der vier Stellen übergibt `safety_level` an `execute_pipeline`, so dass die Vorgabe `'kids'` des Executors in die Chunk-Parameter kommt; und Stufe 4 von `_run_interception_pipeline` erreicht kein ausgeliefertes Frontend mehr (der Flow ruft mit `enable_streaming` und endet vor Stufe 4), so dass die Kommentare, die den Flow als ihren Aufrufer nennen, veraltet sind.

S-006 wird nicht ausgeführt. Die Nicht-HTTP-Teile der vier Routen-Module nach `services/` zu verschieben ist mit Re-Export-Stummeln am alten Ort auf Python-Ebene verhaltensgleich möglich; aber `schema_pipeline_routes.py` (11 018 Zeilen, vier Sitzungen schreiben parallel) importiert selbst aus `settings_routes` und `chat_routes`, die Schnittlinien hängen am Schnittplan S-190, und ein Umzug ohne ihn verschöbe denselben Zirkel an einen anderen Ort. Beide Befunde bleiben offen.

**Betroffene Dateien:** `docs/analysis/STAGE4_DIVERGENZ_2026-10-10.md`.

## 2026-10-10 — Nachtrag zur Zweitprüfung des Pakets D7: `llm_providers` bleibt stdlib-only, weil ComfyUIs Schlüsselknoten es über den Pfad lädt (S-077)

**Anlass:** Die adversarische Zweitprüfung vom selben Tag widerlegte die Verhaltensgleichheit des Commits a3050f8 an einer Stelle: `comfyui_nodes/ai4artsed_comfyui/_platform_credentials.py` lädt `devserver/my_app/services/llm_providers.py` über `spec_from_file_location` in ComfyUIs Prozess, wo nichts vom DevServer importierbar ist, und sein Docstring hält den Vertrag „stdlib only" fest; das `import config`, das a3050f8 dem Modul für seine Wurzel gab, ließ den OpenRouter-Schlüsselknoten mit `ModuleNotFoundError` scheitern. Der Wächter `test_own_comfyui_nodes.py::test_the_package_reaches_the_provider_table` sah es nicht, weil er im pytest-Prozess mit `devserver/` auf dem Pfad läuft. Außerdem: `test_review_d7_findings.py` ließ die Unterprozess-Prüfung ohne `PYTHONPATH` laufen, was unter `PYTHONSAFEPATH` scheitert; und die Aussage „jeder Pfad ist dem vorher abgeleiteten gleich" galt an sieben Stellen nur bis auf `resolve()`.

**Was das festlegt:** `llm_providers.py` leitet `DEVSERVER_ROOT` wieder aus seinem eigenen `__file__` ab, mit dem Grund im Kommentar, als die eine Ausnahme von S-077; `test_review_d7_findings.py` lädt das Modul in einem isolierten Interpreter (`python -I`, Arbeitsverzeichnis `/`) über den Pfad, wie der Knoten es tut, und nimmt es von der Suche nach Ableitungen aus. Die Unterprozess-Prüfung setzt `PYTHONPATH` selbst. `config.py` schreibt die drei Wissenspfade mit `DEVSERVER_EXPORTS_DIR` und `DEVSERVER_JSON_DIR`, die daneben stehen. Der Eintrag zu S-055/S-077 ist an den zwei Stellen in Ort und Zahl berichtigt.

**Betroffene Dateien:** `devserver/my_app/services/llm_providers.py`, `devserver/config.py`, `devserver/tests/test_review_d7_findings.py`, das Konzeptpapier zur Datenhaltung außerhalb des Arbeitsbaums vom 2026-08-15 (nicht öffentlich).

## 2026-10-10 — Nachtrag zur Zweitprüfung des Commits f2ae672 (Routen ohne Aufrufer): zwei Testdateien, ein auskommentierter Block, neun veraltete Sätze

**Anlass:** Die adversarische Zweitprüfung vom selben Tag widerlegte vier Aussagen des Commits f2ae672: zwei Dateien unter `devserver/testfiles/` riefen entfernte Routen (`probe_archaeology_comfyui.py` den Alias `/pipeline/legacy`, `test_metadata_api.py` die Route `/pipeline_configs_metadata`); die Nachricht nannte „auskommentierte Kompatibilitätsrouten" als gestrichen, die noch standen, samt einer KEEP-Notiz für die entfernte Route, und eine „In-Prozess-HeartMuLa-Klasse", die es nicht gab; neun Docstrings und Kommentare nannten Entferntes als vorhanden (`schema_pipeline_routes` 2424 und 6747, `settings_routes` 1857, `auth_routes` 15, `canvas_routes` 11, 388, 554, `canvas_run_service` 30 und 536, `cross_aesthetic_routes` 25, `test_context_prompt_gate` 128); `model_selector.py` behielt drei Importe ohne Leser; `scripts/befund_belege.py` las eine gestrichene Datei und meldete still null; vier Dokumente führten entfernte Einstellungen und Routen als vorhanden. Der gelöschte `test_embedding_pair.py` deckte sieben Fälle des GPU-Dienstes ab, die zu dem Zeitpunkt noch standen; mit `2313676` ging die Textstation des GPU-Dienstes, so dass die Löschung seither stimmt.

**Was das festlegt:** Das Sondierungsskript ruft `/pipeline/direct`, den Weg, dessen Alias `/legacy` war; `test_metadata_api.py` ist gelöscht (es prüfte nur die entfernte Route; `test_lab_db_isolation.py` nennt es nicht mehr). Der auskommentierte Block ist gestrichen, ein Kopf nennt die eine verbliebene Kompatibilitätsroute. Die neun Sätze sagen, was ist; `/api/media/images/<run_id>` heißt `/api/media/image/<run_id>`, wie die Route. `model_selector.py` importiert, was es liest. `befund_belege.py` meldet die entfernte Datei als entfernt. `CONFIGURATION_GUIDE.md` führt `ENABLE_AUTO_EXPORT`, `LOOP_GENERATION` und `MEDIA_DOWNLOAD_TIMEOUT` nicht mehr; die Karte der Strecken und der Datenhaltungsplan tragen die Entfernungen mit Datum; die Entscheidungstabelle vom 2026-08-24 sagt, bis wann der Alias stand.

**Betroffene Dateien:** `devserver/testfiles/probe_archaeology_comfyui.py`, `devserver/testfiles/test_metadata_api.py` (gelöscht), `devserver/tests/test_lab_db_isolation.py`, `devserver/tests/test_context_prompt_gate.py`, `devserver/my_app/routes/schema_pipeline_routes.py`, `settings_routes.py`, `auth_routes.py`, `canvas_routes.py`, `cross_aesthetic_routes.py`, `devserver/my_app/services/canvas_run_service.py`, `devserver/schemas/engine/model_selector.py`, `scripts/befund_belege.py`, `docs/installation/CONFIGURATION_GUIDE.md`, zwei nicht öffentliche Dokumente.

## 2026-10-10 — Nachtrag zur Zweitprüfung des Commits 424fcbd (toter Code in Dateien): Kommentare über nichts, eine Ereigniskette ohne Sender, ein Kameradialog ohne Öffner

**Anlass:** Die adversarische Zweitprüfung vom selben Tag fand, was der Zähler der Bezeichner nicht sieht: Kommentare, die über gestrichenem Code stehen blieben (`audio_synth`, `services/api.ts`, `stores/configSelection.ts`, `stores/favorites.ts`, `types/settings.ts`), ein leerer Zweig `if (data.safe) {}` in `useGenerationStream.ts`, die Ereignisse `update-display-title`/`update-display-mode`, die `StageModule` deklariert, `CanvasWorkspace` weiterreicht und `canvas_workflow` behandelt, ohne dass sie irgendwo gesendet werden, der Kameradialog von `resona.vue`, dessen einziger Öffner `openCamera` mit 424fcbd ging (er war schon davor ohne Knopf), und den Schlüssel `persona.fallbackGreeting`, dessen einziger Leser mit `fetchGreeting` ging. Der Perspektivring des Synths, den 424fcbd als unerreichbar strich, ist mit c8f357f samt Ring wieder da; der Kommentarblock darüber steht zu Recht.

**Was das festlegt:** Die Kommentare und der leere Zweig sind gestrichen; die Ereigniskette ist in allen drei Dateien weg; der Kameradialog mit seinen Refs, Funktionen und CSS-Regeln ist gestrichen, die Zeile, die beim Hochladen einen Fehlertext in den nie gezeigten Dialog schrieb, auch (das Hochladen meldet seinen Fehler weiter im Log, wie bisher sichtbar: gar nicht); `persona.fallbackGreeting`, `resona.capture` und `resona.cameraError` sind aus `en.ts` und stehen im Nachtrag zu WO-2026-10-10-A zum Entfernen aus den anderen Sprachen. `resona.cancel` bleibt, solange ein Leser es trägt.

**Betroffene Dateien:** `views/latent_lab/audio_synth.vue`, `services/api.ts`, `stores/configSelection.ts`, `stores/favorites.ts`, `types/settings.ts`, `composables/useGenerationStream.ts`, `components/canvas/StageModule.vue`, `components/canvas/CanvasWorkspace.vue`, `views/canvas_workflow.vue`, `views/resona.vue`, `i18n/en.ts`, `i18n/WORK_ORDERS.md`.

## 2026-10-10 — Nachtrag zur Zweitprüfung des Commits 85ba393: das Freimachen von ComfyUI unterbricht vor der Lease und vergisst nach der Freigabe, Stufe 1 weist falsch geformte Konzepte nicht mehr ab, `checks_passed` nennt jede Prüfung einmal

**Anlass:** Die adversarische Zweitprüfung vom selben Tag widerlegte vier Aussagen des Commits. (1) `gpu_gate.free_comfyui` rief `forget_resident` INNERHALB der Lease; `GpuLease.release()` trägt beim Freigeben den Affinitätsschlüssel der Lease als Residenten ein und machte das Vergessen damit rückgängig, das Gate hielt ComfyUI weiter für resident. Außerdem stand der `/interrupt` hinter der Lease: er gilt dem Lauf, der die Karte hält, und eine Lease, die erst erteilt wird, wenn nichts mehr läuft, kommt für ihn zu spät. (2) `_concept_prompts` warf bei Konzepten, die kein JSON sind, und die Route antwortete 500 vor Stufe 1; bis 85ba393 las der Chunk die Konzepte selbst und sagte, was an ihnen falsch ist. (3) `_stage1_check_texts` hängte die Prüfungen jedes Textes an `checks_passed` an, drei Texte ergaben `["fast_filter", "fast_filter", "fast_filter"]`. (4) Der Zensus `test_safety_coverage_map.py` kannte weder den Aufruf der Stufe-2-Maschinen noch `free_comfyui` als Marke: `_run_stage2`, `workshop_clear_all` und `clear_vram_thoroughly` waren seit dem Commit aus dem Zensus gefallen, drei erklärte Zeilen (`<module>` zweier Routendateien, `_run_stage2`) waren veraltet, zwei Stellen aus der Baseline (`_generator_fields`, `encoder_rows`) unerklärt. Dazu `reset_heartmula_backend` ohne Rufer.

**Was das festlegt:** `free_comfyui` sendet den `/interrupt` VOR der Lease, `/free` unter ihr, und ruft `forget_resident` NACH dem `with`-Block; `test_comfyui_free_through_the_gate.py` hält die Reihenfolge `interrupt, lease, free, release, forget`. `_concept_prompts` gibt bei Konzepten, die sich nicht lesen lassen, die leere Liste zurück: Stufe 1 prüft die Texte, die sie findet, der Chunk weist die Form ab. `checks_passed` ist geordnet und ohne Wiederholung. Der Zensus trägt die Marken `stage2-engine` und `comfyui-free`; die fünf Stellen, die sie sichtbar machten, sind erklärt (`preview_prompt` als `stage1`, die beiden Stufe-2-Helfer als `helper`, die zwei Freimacher als `not-generating`), die drei veralteten Zeilen gestrichen. `reset_heartmula_backend` ist gestrichen. Alle Fälle in `test_review_phase5_findings.py`, vorher rot.

**Betroffene Dateien:** `devserver/my_app/services/gpu_gate.py`, `devserver/my_app/routes/schema_pipeline_routes.py`, `devserver/my_app/services/heartmula_backend.py`, `devserver/tests/test_comfyui_free_through_the_gate.py`, `devserver/tests/test_safety_coverage_map.py`, `devserver/tests/test_gpu_admission_coverage.py`, `devserver/tests/test_review_phase5_findings.py`.

## 2026-10-10 — Nachtrag zur Zweitprüfung der Commits 501b5d8 und 847b78f (Befund S-015 der Code-Sichtung vom 2026-10-10): die Abweisung des Modells wird auf allen drei Stufe-2-Pfaden gelesen, nur auf Text, den ein Modell schrieb, und die Abweisung des Klassifikators ist eine Sperre

**Anlass:** Die Zweitprüfung fand, dass 501b5d8 den Satz der Sicherheitspräambel nur auf zwei von vier Pfaden las: der Stream, auf dem der Flow generiert (`execute_pipeline_streaming`), reichte den Satz als Interception weiter, der Interception-Knoten des Canvas ebenso. Wo die Route den Satz las, las sie ihn auch auf Text, den kein Modell geschrieben hat: bei übersprungener Stufe 2 (`stage2_skipped`), beim Klassifikator-Gate (`gate`) und bei vom Frontend mitgebrachtem Ergebnis (`frontend_provided`) steht der Text der Besucherin im Ergebnis, und wer den Satz selbst schrieb, wurde „abgewiesen". Die Abweisung des Kinder/Jugend-Klassifikators (`label: UNSAFE`) kam als 500 zurück, was jede Fläche als Zusammenbruch liest, nicht als die Sperre, die sie ist. `is_safety_refusal` las nur das „ü"; ein Werkstattprotokoll vom 2026-03-18 verzeichnet die Schreibung „unterstuetzen". Zu 847b78f: die Nadel der Invariante `test_the_frontend_matches_on_no_sentence` war der ganze Satz, so dass der Matcher, den die zwei Vergleichsflächen bis 501b5d8 tatsächlich trugen (das Fragment „kann ich dich nicht unterstützen" und drei englische Literale), unsichtbar blieb; `i18n/` und die Specs lagen im Suchraum, obwohl eine Anzeige des Satzes kein Matcher ist. Die Kopfzeile der Spec sprach von „vier englischen Varianten"; es waren ein zweites deutsches Fragment und drei englische Literale. Der dritte Fall der Spec (`refusalOf`) war schon vor 501b5d8 grün und hielt S-015 nie. Die Aussage des Commits 501b5d8, die DevServer-Suite sei der Baseline gleich, war falsch: seine eigene Invariante war rot, bis 847b78f die Spec umformulierte; keine Hook und kein Workflow lässt `test_instruction_invariants.py` laufen.

**Was das festlegt:** Der Stream beantwortet den Satz mit dem Ereignis `blocked` (`stage: 2`, `blocked_at_stage: 2`, `reason`, `checks_passed: []`), das der Flow für die Stufe-1-Sperre schon liest, und zeichnet `safety_blocked` auf; der Canvas-Knoten setzt `output` leer und `error` auf den Satz, der Lauf hält dort. Beide Routen lesen den Satz nur, wo ein Modell schrieb (`model_wrote`): nicht bei `stage2_skipped`, `gate`, `frontend_provided`, und im Stream nicht, wo der Passthrough den Prompt wörtlich weitergibt. Die Abweisung des Klassifikators antwortet 403 in der Form der Sperre (`status: blocked`, `blocked_at_stage: 2`, `reason`, `checks_passed`); ein unerreichbarer Klassifikator bleibt 500. `is_safety_refusal` vergleicht mit „ue/ae/oe/ss". Die Invariante liest `.vue/.ts/.js` außerhalb `i18n/`, `__tests__/` und `*.spec.ts` auf die drei Fragmente des alten Matchers. Alle Fälle in `test_review_phase5_findings.py` und `test_instruction_invariants.py`, vorher rot. Die bloßen Etiketten „(S-015)" in öffentlichen Dateien erhalten im Dokumentations-Nachtrag die Langform.

**Betroffene Dateien:** `devserver/my_app/routes/schema_pipeline_routes.py`, `devserver/my_app/services/canvas_executor.py`, `devserver/schemas/engine/instruction_selector.py`, `devserver/tests/test_instruction_invariants.py`, `devserver/tests/test_review_phase5_findings.py`, `public/ai4artsed-frontend/src/composables/__tests__/useLabRun.gate.spec.ts`.

## 2026-10-10 — Nachtrag zur Zweitprüfung des Commits eb07734: drei Decode-Tests kehren zurück, drei Aussagen der Commit-Nachricht sind falsch

**Anlass:** Die Zweitprüfung widerlegte: „die Streaming-Methode, die ein gleichnamiger Zwilling verdeckte" (es gab nie zwei `generate_image_streaming`; die gestrichene war die einzige, ohne Route und Rufer); „die fünf Registrierungstabellen" (acht: `NODE_CLASS_MAPPINGS` und `NODE_DISPLAY_NAME_MAPPINGS` in vier Modulen); „`_hf_repo_complete` lief nur für ein Backend, das seit Stufe 4 als nicht verfügbar gilt" (die Wache feuerte für jedes verfügbare Backend mit `meta.model_repo`; tot war sie, weil keine Output-Config `model_repo` trägt). Drei der gestrichenen Tests prüften behaltenen Code: `test_the_decode_adds_the_shift`, `test_the_decode_takes_a_latent_with_or_without_a_batch_axis`, `test_a_vae_without_a_shift_is_read_as_no_shift` lesen `decode_latent_tensor`, das der Keep-Latent-Zweig von `generate_image` weiter ruft; seit eb07734 war die Arithmetik ohne Test. Die Kommentarblöcke über `generate_image_with_fusion_scheduled` und `generate_image_with_delayed_kickin` nannten die gestrichene `generate_image_with_decomposition`; beide Methoden hatten selbst keinen Rufer (keine Route, kein Client) und sind in diesem Nachtrag gestrichen, mit den drei Tabellen `DECOMP_*`, die nur sie lasen, und `cross_aesthetic_backend.multi_axis_synth`, dessen Route mit 2ee2e14 ging. `npy_bytes_to_array` hat seit eb07734 nur noch Tests als Leser.

**Was das festlegt:** Die drei Tests stehen wieder in `gpu_service/tests/test_diffusers_latent.py` (in dieser Umgebung ohne `torch` nicht lauffähig, wie die ganze Datei in der Baseline). Die zwei Diffusers-Methoden, `multi_axis_synth` und die Tabellen sind gestrichen; `latent_lab_context_graphs.py` und der Knoten `ai4artsed_sd3_context.py` nennen die Zwillinge als gestrichen. Die Dokumentationsreste (`comfyui_nodes/ai4artsed_comfyui/architecture.md`, die nicht öffentliche Notiz zur Ollama-Entfernung unter `docs/`, PART 27) folgen im Dokumentations-Nachtrag.

**Betroffene Dateien:** `gpu_service/services/diffusers_backend.py`, `gpu_service/services/cross_aesthetic_backend.py`, `gpu_service/tests/test_diffusers_latent.py`, `devserver/my_app/services/latent_lab_context_graphs.py`, `comfyui_nodes/ai4artsed_sd3_context.py`.

## 2026-10-10 — Nachtrag zur Zweitprüfung des Commits 3d8301d: die Registry rief zwei gestrichene Methoden, die Pipeline `vector_fusion_generation` erreicht nichts, die Lyrics-Configs waren angeboten

**Anlass:** Die Zweitprüfung fand: 3d8301d strich `BackendRegistry.get_config` und `_load_output_config` und ließ ihre zwei Rufer stehen, `is_workflow_available` und `_query_comfyui_nodes`, beide unter `except Exception`, so dass der `AttributeError` geloggt und geschluckt wurde; beide hatten außerhalb der Datei keinen Rufer. „Jede verbliebene Pipeline wird von einer aktiven oder geparkten Config, einer deprecated View oder einem Test erreicht" galt nicht für `vector_fusion_generation`: keine Config, keine View, kein Test nennt die Pipeline (ihr Chunk `output_vector_fusion_clip_sd35` ist durch Tests gedeckt). „Die vier Lyrics-Configs in der Form, die der Loader nicht liest": der Loader las sie (die `pipeline` war gesetzt), ungelesen war ihr `chunks[].prompt`; das nicht öffentliche Abbruchprotokoll zu HeartMuLa vom 2026-10-01 unter `docs/` verzeichnet alle vier unter den 46 Configs, die der Resona-Canvas anbot und die der Executor „ohne Kontexttexte" abwies. `parse_preoutput_json` (`stage_orchestrator.py`) hat seit der Löschung von `image_safety_refinement.json` keinen Erzeuger mehr, nur einen Rufer unter `testfiles/`. Der Eintrag zur Negativ-Prompt-Bereinigung, der `image_safety_refinement.json` als „nicht angefasst" führt, betraf die Formulierung seines Prompts, nicht sein Bestehen.

**Was das festlegt:** `is_workflow_available`, `_query_comfyui_nodes`, die zwei Cache-Felder und die Einstellung `comfyui_node_cache_ttl` in `backends.json` sind gestrichen; `test_the_registry_calls_no_method_it_no_longer_has` hält per AST, dass jedes `self.<name>(` der Klasse eine Methode der Klasse nennt (vorher rot). `vector_fusion_generation` bleibt und ist hier als von nichts erreicht verzeichnet. `parse_preoutput_json` bleibt als Parser ohne Erzeuger verzeichnet. PART 28 (Key Files `embedding_analyzer.py`, `attention_processors_sd3.py`) und PART 04 (das Beispiel `image_generation`) folgen im Dokumentations-Nachtrag.

**Betroffene Dateien:** `devserver/my_app/services/backend_registry.py`, `devserver/config/backends.json`, `devserver/tests/test_review_phase5_findings.py`.

## 2026-10-10 — Nachtrag zur Zweitprüfung des Commits 2313676: der Text-Client trug den Transport zur gestrichenen Station weiter

**Anlass:** `text_client.py` behielt nach dem Streichen der Textstation des GPU-Dienstes `_post`, `_get`, `_answer`, `_refusal`, `_note_model_of` und `base_url`, alle ohne Rufer, und einen Kommentar, nach dem „die Instrumente, die ein Modell laufen lassen, weiter zum GPU-Dienst gehen".

**Was das festlegt:** Der Transport ist gestrichen; der Client ist, was sein Docstring sagt: die Tokenizer-Türen auf ComfyUIs HTTP-Routen. Der Kommentar nennt den Abgang der Station.

**Betroffene Dateien:** `devserver/my_app/services/text_client.py`, `devserver/tests/test_model_place_frame.py` (der Client steht nicht mehr in der Liste der Stellen, die ein Modell ansagen).

## 2026-10-10 — Nachtrag zur Zweitprüfung des Commits 26ed141: die Nachricht beschreibt sechs von 36.042 Zeilen, ein bloßer Lauf bricht weiter an einem Sammelfehler ab

**Anlass:** Die Zweitprüfung stellte fest: 26ed141 („pytest collects tests/ alone") trägt 409 Dateien, +6/−36.036 Zeilen; die sechs Zeilen sind `devserver/pytest.ini`, der Rest ist die Löschmenge, die df52bf3 und 93848a0 in ihren Nachrichten beschreiben. Bei 26ed141 importierte `create_app()` nicht (`workflow_streaming_routes`, `export_routes`, `sse_routes`, `execution_routes` in `my_app/__init__.py`, repariert mit 93848a0), `test_sse_transport_answer_sites.py` importierte `workflow_streaming_routes` (repariert mit 93848a0), `chat_column_wording.spec.ts` las zwei gelöschte Views (repariert mit df52bf3). „Ein bloßer Lauf bricht nicht mehr ab" gilt nur mit Arbeitsverzeichnis `devserver/`, und auch dort endet die Sammlung an einem Fehler, der älter als der Zweig ist und in der Baseline steht: `test_sd35_conditioning_length.py` baut beim Import jeden Graphen und weist `combine_at` des Chunks `output_image_composable_diffusion_comfyui` ab. `devserver/tests/test_10_prompts.txt`, das `test_pipeline_quick.py` liest, war mitgelöscht. `tests/test_negative_terms.py` an der Wurzel importierte `server.my_app.utils.negative_terms`, einen Baum, den es in keiner Revision gab; nichts ließ es laufen (`README.md` meint mit `pytest tests` den GPU-Dienst). Die zwei nach `devserver/scripts/` verschobenen Vergleichsskripte schreiben ihre Ergebnisse seither nach `devserver/scripts/results/`.

**Was das festlegt:** `test_10_prompts.txt` steht wieder an seinem Ort. `tests/test_negative_terms.py` ist gestrichen. Der Sammelfehler bleibt, als Befund der Baseline, offen. Die Dokumentationsreste (PART 12, PART 21, die Gebrauchszeilen der zwei Skripte, Docstrings in `pipeline_recorder.py`, `comfyui_ws_client.py`, `chat_routes.py`, `test_check_cannot_permit.py`) folgen im Dokumentations-Nachtrag.

**Betroffene Dateien:** `devserver/tests/test_10_prompts.txt`, `tests/test_negative_terms.py`.

## 2026-10-10 — Nachtrag zur Zweitprüfung des Commits b0aa735: ein Import ohne Leser, eine Konfigurationsdatei ohne Leser, und die Medium-Kennung bleibt abgewiesen

**Anlass:** Die Zweitprüfung fand: der Commit hinterließ in `_run_interception_pipeline` den Import `STAGE3_MODEL` ohne Leser (die einzige Verwendung wanderte in `_record_translation`, das selbst importiert), obwohl seine Nachricht „keine neuen ruff-Befunde" sagte. `devserver/comfyui.config` trug `COMFYUI_URL=http://127.0.0.1:17804` ohne einen Leser in Skript, Code oder Unit. „Kein Aufruf konnte den Medium-Eintrag erreichen" war falsch: `fusion_workbench_routes.py` reicht `data.get('model_id')` an `latent_lab_context_graphs.checkpoint_of`, und ein Aufruf mit der Medium-Kennung erhielt bis b0aa735 einen Medium-Graphen, seither 400 („No ComfyUI checkpoint mapped"); die Fläche `fusion_workbench.vue` sendet keine `model_id`. Der Eintrag vom selben Tag zählte „vier Helfer" des Archäologie-Chunks, es sind fünf. Vier Testdateien änderten sich, die Nachricht nannte zwei (`test_sd3_conditioning_nodes.py` lockerte zwei Zusicherungen auf Präfixe). Der unerreichbare Fehlertext des Archäologie-Chunks nennt jetzt `comfyui_chunk_support.py::checkpoint_for` statt `_checkpoint_for()`.

**Was das festlegt:** Der Import und die Datei sind gestrichen. Die Abweisung der Medium-Kennung an der Werkbank-Route bleibt, als die Festlegung vom 2026-09-18 (Large auf jeder Karte), und ist hier als Verhaltensänderung der Route verzeichnet. Der Eintrag zu b0aa735 ist in der Zahl berichtigt.

**Betroffene Dateien:** `devserver/my_app/routes/schema_pipeline_routes.py`, `devserver/comfyui.config`.

## 2026-10-10 — Nachtrag zur Zweitprüfung: die Dokumentationsreste der Commits 26ed141, 93848a0, 2ee2e14, 2313676, eb07734, 3d8301d und b0aa735, und die Etiketten der Befunde im Code

**Anlass:** Die Zweitprüfungen fanden an 29 Stellen Kommentare, Docstrings, Tabellenzeilen und Anleitungssätze, die auf gestrichenen Code zeigten, als stünde er noch: die Ausnahmeliste von `test_llm_providers.py` nannte `workflow_logic_service.py`; zwei Docstrings in `test_comfyui_submit_reason.py` und einer in `comfyui_ws_client.py` sprachen von `workflow_streaming_routes` im Präsens; die zwei nach `devserver/scripts/` verschobenen Vergleichsskripte nannten in ihrer Gebrauchszeile den alten Ort; `legacy_workflow_service.py` und PART 22 nannten `_process_workflow_chunk` als Rufer, es ist `_process_legacy_workflow`; `pipeline_recorder.py` sprach von einem Dienst, der Medien lädt; PART 18 ließ `ExecutionTracker` im Beispiel stehen; `heartmula_client.py` nannte sich Ersatz für einen Generator, den es nicht mehr gibt, und PART 08 ließ HeartMuLa vom GPU-Dienst prüfen; `local_media_weights.json`, `download_media_analysis.sh` und `measure_meanalgebra_cosine.py` zeigten auf `media_analysis_backend.py`, `/api/analysis/*` und `algebra_modes.py`; PART 31 führte `TEXT_ENABLED` und das Latent Text Lab im GPU-Dienst; `MODELS_REQUIRED.md`, `INTELLECTUAL_PROPERTY.md` und `TRANSFORMERS_UPGRADE_TEST_PLAN.md` zeigten auf `text_backend.py` und `TEXT_PRESET_SCENARIOS`; `winobias_curated.json` auf `gpu_service/services/winobias_corpus.py`; der Kasten in `vram_coordinator.py` auf `TextBackend` und `HeartMuLaBackend`; die Architekturnotiz des Knotenpakets auf den Stability-Schlüsselknoten; die Ollama-Notiz auf `LLM_TIMEOUT_DEFAULT`; PART 27 und PART 28 auf `devserver/my_app/services/{diffusers_backend,attention_processors_sd3,embedding_analyzer}.py`, die es nur noch unter `gpu_service/services/` gibt; PART 04 führte die gelöschte Pipeline `image_generation` als Beispiel; PART 21 fünf gelöschte Icon-Komponenten; PART 12 vier gelöschte Dateien; PART 33 den Temperaturvergleich und drei Reiter; `latent_lab_capabilities.py` eine Medium-Baseline im Präsens; die zwei Schnappschüsse unter `devserver/analysis/` den Stand „aktueller Commit". Dazu die bloßen Etiketten „(S-NNN)" in 65 Code-Dateien, die auf eine nicht öffentliche Sichtung zeigen, ohne sie zu nennen. Die Zweitprüfungen von 93848a0, 0cb224b, 19343f9, 53a2b17 und 2ee2e14 hielten außerdem Ungenauigkeiten der Nachrichten fest, ohne Verhaltensfehler: die Pipeline-Metadaten `version 3.0`, `backend_agnostic` und `replaces` stehen seit 53a2b17 in `model_meta` und in den Aufzeichnungen der vierzehn Configs der Passthrough-Pipeline, und `/api/config/<id>/pipeline` beschreibt sie anders als zuvor; „one way to run a coroutine from a route" ist zu weit gefasst; 0cb224b änderte Logger-Namen und ließ im `backend_router` eine vierte Nahkopie des Feldpfad-Laufs stehen.

**Was das festlegt:** Jede der 29 Stellen sagt, was heute gilt, oder trägt das Datum der Streichung; die zwei Schnappschüsse tragen eine Datumszeile; jedes Etikett im Code lautet „finding S-NNN of the code review of 2026-10-10". Dokumente, die einen Stand ausweisen (Berichte, Übergaben, Pläne, der Inventar-Ordner der Sichtung, ältere Einträge dieses Protokolls), bleiben, wie sie sind: sie beschreiben ihren Tag. Der Eintrag zu S-014 vom selben Tag ist an vier Stellen berichtigt (Anlass, Begründung, Nebenwirkung, Betroffene Dateien); die vier Kommentare in `x2x_flow.vue`, die den Halt noch als lebend beschreiben, die Hilfe-Texte `docs.guideFlow.hold*`, der Schlüssel `x2xFlow.heldPrompt` und das Feld `AsmItem.edited` folgen im Frontend-Nachtrag.

**Betroffene Dateien:** siehe den Commit; keine Zeile davon ändert Verhalten.

## 2026-10-10 — Nachtrag zur Zweitprüfung der Commits ddadba7, 501b5d8 und 4525e7f (Frontend): das Drucken schreibt ein Dokument, jeder Download und jedes Weiterreichen auf dem einen Weg, die Serie läuft nach einer Stufe-2-Abweisung weiter, der Vogel wird im Betrieb ausgeliefert

**Anlass:** Die Zweitprüfungen fanden: `lib/printMedia.ts` öffnete die Adresse des Bildes als Seite, was ein Browser für eine `data:`-Adresse verweigert (die Skizzen und gefangenen Rahmen des Flows tragen solche), und drei weitere zeichengleiche Kopien standen in `FooterGallery`, `canvas/OutputDrawer` und `direct` (sechs, nicht drei); `direct.vue` schrieb das Weiterreichen an den Flow und `KnowledgeLibraryTab` sowie `SessionExportView` den Download selbst, neben `lib/handOverImage.ts` und `lib/downloadMedia.ts`; `ImageUploadWidget` ersetzte jede Begründung des Servers durch den Haussatz; `useAppClipboard.paste` gab eine Lauf-Markierung zurück, die eine ältere Fassung im Speicher hinterlassen haben kann; `static_routes.py` beantwortete `/images/bird-cells.svg` (das Vogel-Sprite des Waldspiels) im Betrieb mit der Seite der App; `CanvasWorkspace.onKeyDown` prüfte das Feld vor der Escape-Taste, so dass eine begonnene Verbindung aus einem Feld heraus nicht abgebrochen werden konnte; `useInterceptionSeries.intercept` hielt die ganze Serie an, wenn das Modell EINE Zeile unter deren Perspektive abwies (seit 501b5d8 eine Sperre mit `blocked_at_stage: 2`); `x2x_flow.vue` trug zwei JSDoc-Zeilen über nichts; `tsconfig.app.json` schloss ein Muster aus, das keine Datei trifft; `types/canvas.ts` trug den Kommentar von `LLMModelSummary` über `CollectorOutputItem`; die Registry nannte `lib/seriesGridCells.ts` nicht; der Docstring von `useSeedAutomatic` nannte den Seed, mit dem Mean Images nicht öffnet. 4525e7f ersetzte 16 Stellen, nicht 15 (eine Vorlagenbindung in `StageModule.vue`), und ließ eine vierte in der geparkten View stehen (zu Recht, Regel 19).

**Was das festlegt:** `printMedia` schreibt ein eigenes Dokument mit dem Bild, das druckt, sobald das Bild geladen ist; die drei Kopien rufen es. `direct.vue` reicht über `handOverImage` weiter, die zwei Komponenten laden über `downloadBlob`. Die Fehlerzeile des Upload-Widgets zeigt, was der Server sagte (`said` am Fehler von `uploadImageFile`), den Haussatz nur, wo er nichts sagte. Die Hand antwortet leer auf eine Lauf-Markierung. Die statische Route liefert `images/` aus. Escape beendet eine Verbindung, wo auch immer der Fokus steht; Entf bleibt hinter der Feldprüfung. Eine Abweisung bei Stufe 2 gehört ihrer Zeile und hält nichts anderes an. Sichtbar: das Drucken aus dem Flow druckt jetzt auch Skizzen; die Upload-Zeile nennt den Grund; der Vogel fliegt im Betrieb. Specs: `lib/__tests__/printMedia.spec.ts`, `useAppClipboard.spec.ts`, `useMaterialIntake.said.spec.ts`, `canvas/__tests__/CanvasWorkspace.keys.spec.ts`, zwei Fälle in `useInterceptionSeries.spec.ts`, ein Fall in `test_review_phase5_findings.py`; alle vorher rot. Die Aussage der Zweitprüfung von 501b5d8, der Satz „zwei mit mp3, drei mit wav" im Eintrag zu S-043 sei vertauscht, ist am 2026-10-11 am Stand vor 501b5d8 nachgeprüft und bestätigt; der Satz ist an seiner Stelle berichtigt.

**Betroffene Dateien:** `lib/printMedia.ts`, `components/FooterGallery.vue`, `components/canvas/OutputDrawer.vue`, `views/direct.vue`, `components/KnowledgeLibraryTab.vue`, `components/SessionExportView.vue`, `composables/useMaterialIntake.ts`, `components/ImageUploadWidget.vue`, `composables/useAppClipboard.ts`, `components/canvas/CanvasWorkspace.vue`, `composables/useInterceptionSeries.ts`, `views/x2x_flow.vue`, `types/canvas.ts`, `composables/useSeedAutomatic.ts`, `tsconfig.app.json`, `devserver/my_app/routes/static_routes.py`, `docs/ELEMENT_STRUCTURE_REGISTRY.md`.

## 2026-10-10 — Nachtrag zur Zweitprüfung des Commits 8abb44f (Frontend): die Flow-Anleitung beschreibt den Halt nicht mehr, vier Kommentare und ein Feld folgen dem Beschluss

**Anlass:** Die Zweitprüfung fand nach dem Streichen der Halt-Maschinerie: vier Kommentare in `x2x_flow.vue`, die den Halt am Prompt als lebend beschrieben; den Schritt 4 der Flow-Anleitung (`docs.guideFlow.holdTitle`/`holdBody`, gezeigt von `components/docs/DocGuideFlow.vue`), der eine zweite Steuerung „am Prompt anhalten" versprach, die es seit 2026-09-03 nicht gibt; den Schlüssel `x2xFlow.heldPrompt` ohne Leser; das Feld `AsmItem.edited`, das die Textbox setzte und nichts mehr las.

**Was das festlegt:** Die vier Kommentare nennen den Halt als vergangen. Schritt 4 der Anleitung trägt den Titel `docs.guideFlow.stopTitle` („Stop of a run") und als Text die bestehende `stopNote` (das Halten der Box stoppt den Lauf), wortgleich; `holdTitle`, `holdBody` und `heldPrompt` sind aus `en.ts` gestrichen und stehen in WO-2026-10-10-F zum Entfernen aus den anderen Sprachen. `AsmItem.edited` und sein Setzer sind gestrichen. Sichtbar: der vierte Schritt der Flow-Anleitung.

**Betroffene Dateien:** `views/x2x_flow.vue`, `components/docs/DocGuideFlow.vue`, `composables/useAssemblageBoard.ts`, `i18n/en.ts`, `i18n/WORK_ORDERS.md`.

## 2026-10-10 — Nachtrag zur Zweitprüfung des Commits a035e6a (Befunde S-135 und S-139 der Code-Sichtung vom 2026-10-10): die Regeln, die der Schnitt stehen ließ, und der Eintrag, der fehlte

**Anlass:** a035e6a strich gescopte CSS-Regeln, die kein Element trägt, und die Debug-Ausgaben, ohne Eintrag in diesem Protokoll. Die Zweitprüfung fand: die Nachricht ordnete achtzehn Klassen von `audio_synth.vue` drei Gruppen zu, zu denen fünf nicht gehören (`param-hint`, `transpose-mode-row`, `lfo-header`, `env-target`, `semantic-axes-info`); drei tote Regeln derselben Datei blieben stehen (`.play-btn` mit `:hover`, `.dim-bar`, `.dim-value`, letztere auch in der Liste der Tabellenziffern), dazu der Kommentar über das gestrichene leere `@media` am Dateiende, `@keyframes typing` in `resona.vue` ohne Nutzer, `.detail` in `IcebergAnimation.vue`, `.action-toolbar.inactive` in `direct.vue` (nie gebunden), `.strip` in `KickinView.vue`; `FigureMask.vue` sprach von „Pigmenten" im Plural, wo eines blieb. Der Commit strich die Token Grünspan und Eisenoxid aus `base.css` als ohne Leser, während die Tabelle des Eintrags zu den Figurenfarben sie `resona.vue` und `ai_persona.vue` zuwies; die Sichtung hatte als Alternative das Setzen in der Routentabelle genannt. Geprüft und bestätigt: keine gestrichene Klasse wird außerhalb ihrer Regel getragen, auch nicht über `:deep`, Kindwurzeln oder zusammengesetzte Namen; `.bubbles-float` in `x2x_flow.vue` blieb zu Recht (die Wurzel von `FlowBubbles`).

**Was das festlegt:** Die sechs Regeln, der Kommentar und die Keyframes sind gestrichen; der Kommentar in `FigureMask.vue` nennt das eine Pigment. Die zwei Zeilen der Farbtabelle tragen die Streichung; die Token bleiben gestrichen, weil die Routentabelle sie nie setzte und keine Fläche sie las. Alle `console.log` der Nachricht waren Ausgaben ohne Steuerwirkung; `console.error` blieb überall.

**Betroffene Dateien:** `views/latent_lab/audio_synth.vue`, `views/resona.vue`, `components/edutainment/IcebergAnimation.vue`, `views/direct.vue`, `views/KickinView.vue`, `components/FigureMask.vue`, `docs/DEVELOPMENT_DECISIONS.md`.

## 2026-10-10 — Nachtrag zur Zweitprüfung des Commits ea5d5a5 (Befunde S-143 und S-175 der Code-Sichtung vom 2026-10-10): die Zeile unter dem Ring sagt, was der Server sagte, eine gerissene Verbindung heißt „nicht erreichbar", und die Zahlen stimmen

**Anlass:** Die Zweitprüfung widerlegte: „vierzehn Flächen" (fünfzehn trugen den Aufruf, achtzehn seit c8f357f, wie die Registry seither zählt; WO-2026-10-10-B sagte vierzehn); „sieben Hüllfunktionen und fünf Konstanten" (sechzehn und acht); „62-mal in 44 Dateien" (60 in 44 ohne `labApi.ts` selbst). Verhalten: der Sprachvergleich der Stimmen zeigte bis ea5d5a5 den `error` des Servers auf der Zeile, seither nie (`perspectiveFailureText` nannte nur den Status), und eine gerissene Verbindung las sich über `generationErrorFor` als „Something went wrong" statt als „nicht erreichbar"; die Ringe der fünfzehn Flächen schwiegen vorher bei leerer Antwort, Abweisung und Fehler und sagen seither je einen Satz (erklärt), dazu eine undeklarierte Stelle: ein Lauf ohne Antwortkörper lief vorher in einen `TypeError` und sagt jetzt `perspective.empty`. `OverlayFrame` änderte gegenüber den zwei Modalen mehr als die Nachricht nannte: Kreuz 40 → 36 px, Titel unter 768 px 1,5 → 1,25 rem, `position: relative; overflow: hidden` am Container. Die gefüllte `MediumGlyph` trägt `aria-hidden`, was die Inline-SVGs nicht trugen. Zurückgelassen: `postStreamedRun` ohne Verwendung in drei Views; drei Kommentare, die `flow-stage.css` als nicht von `main.ts` geladen beschreiben; die Registry-Zeile „Modal:" und die Beschreibung von `glyphOfMediaType`; kein Eintrag in diesem Protokoll. c8f357f musste den Ring auf die drei Crossmodal-Flächen setzen, weil 424fcbd den nie ans Template gebundenen Handler von `audio_synth` gestrichen und ea5d5a5 daraus „kein Ring auf dieser Fläche" gelesen hatte.

**Was das festlegt:** Der Ausgang `failed` von `interceptPrompt` trägt `said`, wo der Server einen Grund gab, und `perspectiveFailureText` zeigt ihn vor dem Statussatz (Spec `useLabRun.failure.spec.ts`, vorher rot). `classifyError` liest `Failed to fetch`, `NetworkError`, `Load failed` und das `Network error` des gerissenen Streams als `offline` („The AI is not available right now."). Die drei Importe und die drei Kommentare sind berichtigt, die zwei Registry-Stellen und WO-B auch. Festgehalten, nicht geändert: die Ringe sagen ihren Satz, `perspectiveError` leert sich erst beim nächsten Druck auf den Ring, `useInterceptionSeries` bleibt ein zweiter Leser der Stufe-2-Antwort mit eigenem Bedarf. Die Konsolidierungen selbst (`apiBase`, `ImpressumText`/`DatenschutzText` auf `OverlayFrame`, `flow-stage.css` einmal aus `main.ts`, `glyphOfMediaType`) gelten als entschieden; die sichtbaren Maße des Rahmens sind oben benannt.

**Betroffene Dateien:** `composables/useLabRun.ts`, `composables/useGenerationStream.ts`, `views/latent_lab/attention_cartography.vue`, `views/latent_lab/denoising_archaeology.vue`, `views/surrealizer.vue`, `assets/base.css`, `components/FlowRunPanel.vue`, `components/MarkedSlider.vue`, `docs/ELEMENT_STRUCTURE_REGISTRY.md`, `i18n/WORK_ORDERS.md`.

## 2026-10-11 — Nachtrag zur Zweitprüfung der Commits 85ba393 und 501b5d8, zweiter Teil: die Sitzungsliste zeigt wieder, was ein Lauf erzeugt hat, der Encoder-Pfad hält sein Modell ab dem Laden, und die Abweisung wird auf dem Text des Interception-Modells gelesen

**Anlass:** Die zwei Zweitprüfungen lieferten mehr Befunde, als die Nachträge vom 2026-10-10 aufgenommen hatten. Ihre Berichte waren im Sitzungsprotokoll vollständig erhalten; die Aussage im Entwicklungslog, sie müssten wiederholt werden, war falsch und ist dort berichtigt. Offen standen vier Abweichungen:
- 85ba393, S-007: die Sitzungsliste der Einstellungen fand seit dem Commit die `config_used` eines Laufs und las `output_mode` aus deren `media_preferences.default_output`. Das ist die Vorgabe der Interception-Config, nicht das, was der Lauf erzeugt hat: ein Song unter einer Perspektive mit Bild-Vorgabe stand als „text2image" in der Spalte und im Export. Bis dahin fand die Liste die Datei nie und las den Modus aus den Ausgaben des Laufs.
- 85ba393, S-003: der Encoder-Pfad (`encode_prompt_info`) nahm den Referenzzähler seines Modells erst nach den drei Tokenizern; die Generierungspfade nehmen ihn direkt nach dem Laden (PART 27). Die Deklaration in `test_gpu_admission_coverage.py` sagte „its own slot(), held across load and forward"; das Backend nimmt eine Zulassung für das Laden und eine für den Forward, dazwischen hält der Referenzzähler das Modell.
- 501b5d8, S-015: die Vorschau einer behaltenen Perspektive (`/api/interception-prompts/<id>/preview`, ohne Aufrufer in der Oberfläche) gab den Abweisungssatz als `output` mit 200 zurück. Die zwei Routen-Wächter vom 2026-10-10 lasen den Satz auch bei Passthrough, wo der Text der Besucherin im Ergebnis steht, und lasen `final_output`, nach einer Adaption also deren Umschrift statt des Satzes.
- 501b5d8, S-043: der Satz „zwei mp3, drei wav" in diesem Protokoll und in der Registry war vertauscht.

**Was das festlegt:**
- Die Sitzungsliste bildet `output_mode` wieder genau wie vor 85ba393: aus der Datei `01_config_used.json` des älteren Layouts, wo sie neben `metadata.json` liegt, sonst aus den Ausgaben des Laufs. `stage2_pipeline` kommt bei aktuellen Läufen aus der gefundenen `config_used`; kein Leser wertet das Feld aus.
- `encode_prompt_info` nimmt den Referenzzähler direkt nach dem Laden und gibt ihn in einem `finally` zurück, das Tokenisierung und Forward umschließt. Die Anweisungsfolge ist sonst unverändert (AST-Vergleich gegen HEAD). Die Deklaration im Coverage-Test nennt die zwei Zulassungen und den Zähler.
- `_stage2_refusal(result)` in `schema_pipeline_routes.py` ist die eine Lesung der Abweisung an den Routen: auf `interception_result`, wo eine Adaption folgte, sonst auf `final_output`, und nie bei `stage2_skipped`, `gate`, `frontend_provided` oder `passthrough`. Die Stufe-2-Route, der volle Lauf und die Vorschau lesen sie; die Vorschau antwortet 403 mit `blocked_at_stage: 2` in der Form ihrer Stufe-1-Sperre. Der Stream des Flows behält seinen eigenen Passthrough-Schluss.
- Der Satz zu S-043 ist an beiden Stellen berichtigt: drei Tabellen gaben `mp3` (`ai_persona`, `resona`, `x2x_flow`), zwei `wav` (`FooterGallery`, `canvas/OutputDrawer`).
- Tests: drei Fälle der Sitzungsliste, zwei der Abweisung an der Stufe-2-Route (alle in `test_review_phase5_findings.py`), einer der Vorschau in `test_lab_prompts.py` und einer zum Referenzzähler in `gpu_service/tests/test_encode_info_under_the_slot.py`, alle vorher rot; dazu ein Fall zum älteren Layout der Sitzungsliste und einer zur Vorschau mit geschriebener Perspektive, die die unveränderte Lesung festhalten.

**Festgehalten, nicht geändert:** Diese Änderungen der zwei Commits bleiben, waren aber in keiner Nachricht und keinem Eintrag genannt.
- 85ba393, S-002: die Stufe 1 der Direktroute nimmt einen Platz der LLM-Warteschlange (`LLM_MAX_CONCURRENT`) für ihren ganzen Durchgang, wie jeder andere Eingang; vorher nahm sie keinen. Eine Logzeile `[STAGE1] BLOCKED on …` kommt hinzu.
- 85ba393, S-003: das Lesen der Encoder kann hinter jedem Halter des anlagenweiten Slots warten und abgewiesen werden (`GpuBusy`, 503). Der DevServer liest das als ausbleibende Anzeige und lässt den Lauf weiterlaufen. Der Coverage-Test akzeptiert für die Abdeckung weiter eine bloße Nennung.
- 85ba393, S-004: das Freimachen vor einem Training wartet bis zum Zeitbudget des Gates (`GPU_ADMISSION_ACQUIRE_TIMEOUT_S`, 5400 s); `/api/training/clear-vram` antwortet bei gehaltener Karte mit `success: false`, wo es vorher freimachte und den laufenden Lauf beendete. Beides war im Commit erklärt.
- 85ba393: `test_the_cache_still_expires` (S-027) war schon vor dem Commit grün; S-060 und S-063 haben keinen Test (gestrichener Code ohne Rufer, ein entfernter Dateiverweis); die Nachricht zählte vierzehn neue DevServer-Tests, es sind sechzehn; `_translate_context` stand schon vor dem Commit. Zu S-056: `_USER_CONFIGURED_KEYS` zählt einen verworfenen Schlüssel weiter als gesetzt, wie zuvor einen unbekannten.
- 501b5d8: auf den zwei Vergleichsflächen geht eine Stufe-1-Sperre an die Sperre der Plattform (`safetyStore.reportBlock`), die den Begleiter öffnet, statt als Zeile unter dem Feld zu stehen. Die Perspektivringe schreiben bei einer Abweisung des Modells den Sperrsatz unter das Feld, statt den Abweisungssatz ins Feld zu schreiben.
- 501b5d8, S-017: im Expertenmodus zeigt die Ausgabebox während eines Laufs `DenoisingProgressView` statt der Edutainment-Animation und darunter die Zusammenfassung der Generierung; vorher kam der Modus nie in der Box an.
- 501b5d8, S-018: die Animation mit dem Vogel hängt am UI-Modus, nicht an der Sicherheitsstufe, wie die Nachricht schrieb.
- 501b5d8: `is_safety_refusal` liest den ganzen Satz wie die Ausführung vor dem Commit (seit dem 2026-10-10 auch mit „ue"). Eine Abweisung ohne „Hierbei", mit „Sie" oder auf Englisch erkennt es nicht. Keine der zwei Vergleichsflächen hatte je den Satz zu lesen: sie liefen nur den Klassifikator oder den Passthrough. Die Sperre der Stufe 2 trägt andere Felder als die der Stufe 1 (`blocked_at_stage`, `status`, `reason`); kein Leser bricht daran. S-040 hat keinen Test. S-061: „die ganze Geschichte" ließ sich im flachen Klon nicht nachprüfen.
- Regel 15 verlangt dem Wortlaut nach eine Zulassung über Laden und Forward. Das Diffusers-Backend nimmt in allen Pfaden zwei, mit dem Referenzzähler dazwischen (PART 27). Das ist keine Folge der Bereinigung und steht als offene Frage im Entwicklungslog.

**Betroffene Dateien:** `devserver/my_app/routes/settings_routes.py`, `gpu_service/services/diffusers_backend.py`, `devserver/my_app/routes/schema_pipeline_routes.py`, `devserver/my_app/routes/interception_prompts_routes.py`, `devserver/tests/test_gpu_admission_coverage.py`, `devserver/tests/test_review_phase5_findings.py`, `devserver/tests/test_lab_prompts.py`, `gpu_service/tests/test_encode_info_under_the_slot.py`, `docs/ELEMENT_STRUCTURE_REGISTRY.md`, `docs/DEVELOPMENT_DECISIONS.md`.

## 2026-10-15 — Die Decomposition-Strecke des GPU-Dienstes ist wieder da, wie der Eintrag vom 2026-09-19 sie behält

**Anlass:** Der Eintrag vom 2026-09-19 („Die Decomposition ist entfernt") behält unter „Forschungswege werden nicht abgebaut" die Route `/api/diffusers/generate/decomposition`, `generate_image_with_decomposition` im Backend des GPU-Dienstes und den DevServer-Client gleichen Namens, als Weg, der nach dem Wegfall des Chunks von Hand erreichbar bleibt. Die Bereinigung vom 2026-10-10 hat alle drei mit `eb07734` entfernt, dazu die drei Mengen `DECOMP_VALID_*`; die Tabellen `DECOMP_STEP_BANDS`, `DECOMP_LAYER_BANDS` und `DECOMP_STREAM_SLICES` folgten mit `d6d3617`. Der Befund der Code-Sichtung vom 2026-10-10, auf dem das stand, sagt, die Methode sei „mit der Decomposition-Fläche am 2026-09-19" gegangen; der Eintrag vom 2026-09-19 sagt das Gegenteil.

**Entscheidung:** Wiederhergestellt aus `eb07734^`, wo alles davon noch stand: die Tabellen `DECOMP_STEP_BANDS`, `DECOMP_LAYER_BANDS`, `DECOMP_STREAM_SLICES` mit den drei Mengen gültiger Namen und `generate_image_with_decomposition` in `gpu_service/services/diffusers_backend.py`, die Route in `gpu_service/routes/diffusers_routes.py`, die Methode in `devserver/my_app/services/diffusers_client.py`. Angepasst ist nur, was seit dem 2026-10-10 für alle Pfade gilt: `DEFAULT_MODEL_ID` statt des Modell-Literals im Backend und in der Route, `run_async` statt `_run_async` in der Route, im Client `model_id` als Pflichtparameter. Sonst ist der Syntaxbaum jeder der drei Methoden und der Tabellen gleich dem von `eb07734^`. Die Kommentare in `comfyui_nodes/ai4artsed_sd3_context.py` und `devserver/my_app/services/latent_lab_context_graphs.py`, die die Strecke als gestrichen nannten, sagen, was gilt. Für die Tabellen hebt das den Satz „und die Tabellen sind gestrichen" im Nachtrag zu `eb07734` vom 2026-10-10 auf; für `generate_image_with_fusion_scheduled`, `generate_image_with_delayed_kickin` und `multi_axis_synth` gilt er weiter.

**Prüfung:** `gpu_service/tests/test_decomposition_path_kept.py` hält Route, Methode, Tabellen mit ihren Werten und Client fest; vor der Wiederherstellung rot (4 von 4), danach grün. Seit `c10b6bb` sind es fünf Tests: die Methode einmal in ihrer Klasse, ihr Rumpf mit Laden, Zählen und Forward unter `_locked_generate`, alle sechs Tabellen nach Wert, die Route und die Schlüssel des Clients; jeder schlägt bei einer gezielten Verfälschung an. GPU-Suite 241 bestanden gegen 237 auf HEAD, derselbe Sammelfehler ohne torch; DevServer-Suite mit derselben Fehlermenge wie HEAD bis auf das bekannte zeitabhängige Paar in `test_openai_style_stream.py`, das allein 80 von 80 besteht.

**Betroffene Dateien:** `gpu_service/services/diffusers_backend.py`, `gpu_service/routes/diffusers_routes.py`, `devserver/my_app/services/diffusers_client.py`, `gpu_service/tests/test_decomposition_path_kept.py`, `comfyui_nodes/ai4artsed_sd3_context.py`, `devserver/my_app/services/latent_lab_context_graphs.py`.

## 2026-10-15 — `llm_model_comparison.vue` ist wieder da: Issue #41 ist nach Regel 19 gesperrt

**Anlass:** Die Bereinigung vom 2026-10-10 hat `views/compare/llm_model_comparison.vue` mit `26ed141` gelöscht, dazu den Store `stores/llmModelCompare.ts`, die Komponente `components/GenerationButton.vue` und `assets/generation-button.css`, die nur diese Seite noch nutzte. Die Datei steht in Issue #41 („Als deprecated markierte Views löschen") und trägt seit dem 2026-08-11 den Vermerk DEPRECATED. Regel 19 sperrt das Vorhaben, „auch nicht nebenbei". Die Code-Sichtung gab die Regel dem Projektleiter als Sperre allein für Views „mit Suffix" wieder und fragte, ob sie auch diese Datei einschließe; der Teilbericht, auf dem das stand, hatte die Datei richtig unter Issue #41 gestellt.

**Entscheidung:** Wiederhergestellt aus `26ed141^`, bytegleich: die Seite, ihr Store, die Komponente und das Stylesheet; dazu der Eintrag der Seite in der Liste von `views/compare/__tests__/chat_column_wording.spec.ts`, den `df52bf3` herausgenommen hatte. Die Seite ist weiter nicht geroutet und von nichts importiert; was ein Nutzer sieht, ändert sich nicht. Ihre i18n-Schlüssel stehen alle noch in `en.ts`. Der Store nennt zwei Modelle als Vorbelegung der Spalten; `devserver/tests/test_no_model_literals.py` führt sie als geerbte Schuld, denn die Seite wurde Stunden vor der Aufnahme des Frontends in die Prüfung gelöscht, und die Grenze der Schuld steigt dafür von 19 auf 21. `temperature_comparison.vue` bleibt gelöscht: Die Sichtung hat sie mit dem Eintrag, der ihren Verbleib offen hält, vorgelegt.

**Prüfung:** `vue-tsc --build` vorher mit der Seite allein rot (fehlender Store), nach der Wiederherstellung grün; Vitest 54 Dateien, 522 Tests grün, die Spec mit beiden Seiten 7 von 7; `vite build` grün.

**Betroffene Dateien:** `devserver/tests/test_no_model_literals.py`, `public/ai4artsed-frontend/src/views/compare/llm_model_comparison.vue`, `public/ai4artsed-frontend/src/stores/llmModelCompare.ts`, `public/ai4artsed-frontend/src/components/GenerationButton.vue`, `public/ai4artsed-frontend/src/assets/generation-button.css`, `public/ai4artsed-frontend/src/views/compare/__tests__/chat_column_wording.spec.ts`.

## 2026-10-15 — Entwickelt wird im privaten Repository; ATELIER bekommt nur Exporte

**Anlass:** Der bereinigte Stand vom 2026-10-10 liegt als Export in ATELIER (`joeriben/atelier`, `b1e92e5`, Export von `7ea088d`). Die Bereinigung der 213 Befunde der Code-Sichtung stand danach nur auf dem Arbeitszweig `claude/laughing-turing-60y5kw`; `develop` stand seit dem 2026-10-09 auf `f1dc1b1`. Offen war, in welches Repository ab wann geschrieben wird.

**Entscheidung:**
- Entwickelt wird in `joeriben/AI4ArtsEd` auf `develop`, wie bisher. Stichtag ist der Fast-Forward von `claude/laughing-turing-60y5kw` nach `develop` am 2026-10-15; wer vorher auf dem alten `develop` gearbeitet hat, führt seine Arbeit per Merge auf den neuen Stand.
- `joeriben/atelier` bekommt ausschließlich Exporte durch `scripts/public_export/export.sh`, je einen Commit „Export of <sha>". Keine Sitzung schreibt dort direkt. Der Export ersetzt alle getrackten Dateien; ein Commit, der dort doch entsteht, wird vor dem nächsten Export in das private Repository übernommen, sonst geht er verloren.
- Exportiert wird bei jedem Fast-Forward von `develop` nach `main`, und am 2026-10-15 einmal vom bereinigten `develop`.

**Begründung:** Die Arbeitsregeln der Sitzungen, das Entwicklungsprotokoll, die Analysen und die Sichtungen gehören nicht zur Source-Available-Fassung und brauchen trotzdem einen versionierten Ort; eine Cloud-Sitzung erhält die Arbeitsregeln nur aus dem Repository, das sie klont. Die Tickets tragen Wortlaute aus der Entwicklung und bleiben nicht öffentlich. Die Prüfung der öffentlichen Fläche (`devserver/tests/test_public_surface_clean.py`) läuft im Export auf dem exportierten Baum und nicht bei jedem Commit jeder Sitzung.

**Was entfällt:** aus dem Übergangsplan vom 2026-10-09 das Umstellen der Remotes, der Tausch der Repositories und die Übertragung der Tickets. Sitzungen und Tickets bleiben im privaten Repository.

**Betroffene Dateien:** keine.

## 2026-10-15 — Erzeugte Bilder liest ein externes Modell, hochgeladene ein lokales

**Entscheidung:** Bilder, die die Plattform erzeugt hat, können und sollen mit externen Modellen gelesen werden. Lokal gelesen werden hochgeladene Bilder.

**Stand im Code, offen:** `IMAGE_ANALYSIS_MODEL` liest heute jedes Bild lokal, gleich welcher Herkunft; `devserver/hardware_matrix.json` (`vision_presets`) setzt dafür auf den Profilen mit 32, 48 und 96 GB `local/qwen3-vl:32b`. Der Knoten `image_evaluation` der Canvas weist ein externes Modell für jedes Bild ab (`devserver/my_app/services/canvas_executor.py:614-623`). Über dasselbe Modell lesen die Analyse eines hochgeladenen Bildes im Flow (`media_routes.py`, `analyze_image_file`) und die Bildbeschreibungen im Chat. Die Prüfung hochgeladener Bilder gehört nicht dazu: Sie läuft über den Klassifikator der Prüfkette. Die Herkunft eines Bildes als Kriterium für seinen Leser ist nicht gebaut.

**Betroffene Dateien:** keine.
