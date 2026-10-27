<template>
  <!-- Root-level guards: a drag released outside the board drop zone must
       not trigger the browser's default file-drop navigation. -->
  <div class="flow-view" @dragover.prevent @drop.prevent>
    <!-- The flow: three uniform nodes. They are the interface, not a diagram. -->
    <div class="map-wrap">
      <div ref="mapEl" class="fl-map" :style="{ aspectRatio: `${W} / ${H}` }">
        <svg class="edges" :width="cw" :height="ch">
          <line
            v-for="(e, i) in edgeLines"
            :key="i"
            :class="{ on: e.on }"
            :x1="e.p[0]"
            :y1="e.p[1]"
            :x2="e.p[2]"
            :y2="e.p[3]"
          />
        </svg>

        <!-- The reserved rectangle: of the whole top band, only this — hugging
             the three boxes, width flexible — is locked out of the canvas. It
             keeps material from falling behind or over the boxes; everything
             else in the band is reachable material space. -->
        <div class="lock-rect" :style="lockRectStyle"></div>

        <!-- preparation: what this takes shape as, and the machine that does it.
             What material is brought in is NOT decided here: the plus lies on
             the surface, where the material is to land. -->
        <div class="nd mix" :class="{ compact: isCompact(RMAP.create) }" :style="rectStyle(RMAP.create)">
          <div class="cr-media">
            <MediumGlyph
              v-for="m in MEDIA"
              :key="m"
              :id="m"
              class="g"
              :class="{ lit: inferredMedia.has(m) && activeMedium !== m, primary: activeMedium === m && mediumClaimed, manual: manualMedium === m }"
              :title="mediumLabel(m)"
              @click.stop="onMediumClick(m)"
              @pointerdown.stop="startHold(m)"
              @pointerup="endHold"
              @pointerleave="endHold"
            />
          </div>
          <div
            class="cr-model"
            :class="{ held: modelChoiceInForce }"
            :title="crModelTitle"
            @pointerenter="enterModelCard(crModelCard, $event)"
            @pointerleave="leaveModelCard"
          >
            {{ createLabel }}
            <!-- the net beside the model: a LoRA in the ring goes with this run -->
            <span v-if="carriedLoras.length" class="cr-lora" :title="carriedLoraLabel"><LoraGlyph /></span>
          </div>
        </div>

        <!-- generation: a triangle until it runs, then the run's own card -->
        <div
          class="nd op"
          :class="{
            live: genPhase === 'pulse',
            ready: canRun,
            wide: genExpanded,
            anim: stageSettled,
            holding: !!holdOn,
            compact: isCompact(RMAP.gen),
          }"
          :style="[rectStyle(genRect), holdOn ? { '--hold': String(holdPct) } : {}]"
          :title="t('x2xFlow.runGesture')"
          @click="onGenClick"
          @pointerdown="startStopHold($event)"
          @pointermove="moveStopHold"
          @pointerup="endStopHold"
          @pointercancel="endStopHold"
          @contextmenu="endStopHold"
          @mouseenter="genHover = true"
          @mouseleave="genHover = false"
        >
          <svg
            v-if="genPhase !== 'info' && !genExpanded"
            class="play"
            :class="{ off: !canRun }"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path d="M8 5.5 19 12 8 18.5Z" fill="currentColor" />
          </svg>

          <!-- The run, station by station: what is read, who transforms it,
               with which model, where that model runs, and what the card
               draws while it does. The panel itself is FlowRunPanel — the cover
               band opens the same one over its own chain. -->
          <FlowRunPanel v-else-if="genExpanded" :stations="runStations">
            <template #foot>
              <!-- The way OUT of a running box stands at the head of the line.
                   It is the only thing on this foot that can be acted on; the
                   figures beside it are read, not used. -->
              <span class="gr-stop" :class="{ armed: !!holdOn }">
                {{ genStopping ? t('x2xFlow.stopping') : t('x2xFlow.holdToStop') }}
              </span>
              <span v-if="liveIsCloud" class="gr-e off">{{ t('x2xFlow.runCloudNoMeter') }}</span>
              <span v-else-if="energyLine" class="gr-e">{{ energyLine }}</span>
              <span v-else class="gr-e off">{{ t('x2xFlow.runEnergyIdle') }}</span>
            </template>
          </FlowRunPanel>

          <!-- The caption: what the next press on this box does. -->
          <div v-if="runCaption && !genExpanded" class="run-cap">{{ runCaption }}</div>

          <div v-if="genPhase === 'info' && !genExpanded" class="gi" :style="{ '--gi-lines': String(giLines) }">
            <!-- What THIS run is, not what the next one would be: after a
                 reading, modelMeta still holds the last generation's model. -->
            <div v-if="!giCrowded" class="gi-model">
              {{ readingRun ? readingLabel : resolveModelName(modelMeta) }}
            </div>
            <div class="gi-state">
              <span v-if="deviceBusy && !isExecuting" class="gi-run">{{ deviceBusyLine }}</span>
              <span v-if="analyzing" class="gi-run">{{ t('x2xFlow.analyzing') }}</span>
              <span v-else-if="adapting" class="gi-run">{{ t('x2xFlow.adapting') }}</span>
              <span v-else-if="safetyState === 'running'" class="gi-run">{{ t('x2xFlow.safetyRunning') }}</span>
              <template v-else-if="safetyState === 'passed'">
                <span class="gi-ok">✓ {{ t('x2xFlow.safetyPassed') }}</span>
                <span v-if="showTranslatedStamp" class="gi-note">{{ t('x2xFlow.safetyTranslated') }}</span>
              </template>
              <span v-else-if="safetyState === 'blocked'" class="gi-err">{{ t('x2xFlow.blocked') }}</span>
              <span v-if="queuePosition > 0" class="gi-note">{{ t('x2xFlow.queuePos', { n: queuePosition }) }}<template v-if="queueWaitLabel"> · {{ queueWaitLabel }}</template></span>
              <span v-if="currentStage === 'stage4' && energyShort" class="gi-note">{{ energyShort }}</span>
            </div>
            <!-- A run that did not come back states the CAUSE first, in red, and
                 what to DO underneath, in grey. The instruction may take two
                 lines; where it does, the model name above steps aside for as
                 long as the message stands. The engine's own words are in the
                 hover. -->
            <div
              v-if="generationErrorMessage"
              ref="giBodyEl"
              class="gi-body"
              :class="genStopped ? 'gi-note' : genFailShown ? 'gi-fail' : 'gi-err'"
              :title="genFailDetail || generationErrorMessage"
            >
              {{ generationErrorMessage }}
            </div>
            <!-- The backend writes these reasons in German and only in German,
                 and two of the Stage-3 ones are developer strings that would put
                 the matched forbidden terms back on the screen. Every other
                 surface of the platform reads them through `safetyBlockKey`;
                 this one showed them raw until 2026-09-04. -->
            <div
              v-else-if="blockedReason"
              ref="giBodyEl"
              class="gi-body gi-err"
              :title="t(safetyBlockKey(blockedReason, blockedStage))"
            >
              {{ t(safetyBlockKey(blockedReason, blockedStage)) }}
            </div>
            <div v-else ref="giBodyEl" class="gi-body" :title="interceptionResult">
              {{ interceptionResult }}
            </div>
            <div v-if="genFailAction" ref="giActEl" class="gi-state">
              <span class="gi-act">{{ genFailAction }}</span>
            </div>
            <div v-if="isExecuting" class="gi-bar">
              <div class="gi-fill" :style="{ width: generationProgress + '%' }"></div>
            </div>
          </div>

          <!-- What was picked could not be served by what lies there, so the
               automatic route runs. Said out loud, because the box otherwise
               names a model nobody chose. -->
          <div
            v-if="droppedChoice && genPhase !== 'info' && !genExpanded"
            class="run-note"
            :title="droppedChoice"
          >
            {{ droppedChoice }}
          </div>
        </div>

        <!-- output: the denoising preview, then the media itself -->
        <div class="nd out" :class="{ compact: isCompact(RMAP.output) }" :style="rectStyle(RMAP.output)">
          <img v-if="currentStage === 'stage4' && previewImage" class="out-media" :src="previewImage" alt="" />
          <div v-if="outPhase" class="out-phase">{{ outPhase }}</div>
          <img v-else-if="mediaUrl && mediaType === 'image'" class="out-media" :src="mediaUrl" alt="" />
          <video
            v-else-if="mediaUrl && mediaType === 'video'"
            class="out-media"
            :src="mediaUrl"
            controls
            draggable="true"
            :title="t('x2xFlow.dragToBoard')"
            @dragstart="onArtifactDrag($event, 'video')"
          ></video>
          <audio
            v-else-if="mediaUrl && (mediaType === 'audio' || mediaType === 'sound' || mediaType === 'music')"
            class="out-audio"
            :src="mediaUrl"
            controls
            draggable="true"
            :title="t('x2xFlow.dragToBoard')"
            @dragstart="onArtifactDrag($event, 'audio')"
          ></audio>
          <img
            v-else-if="mediaType === '3d' && meshThumb"
            class="out-media"
            :src="meshThumb"
            :title="t('x2xFlow.inspect3d')"
            @click="meshOpen = true"
            alt=""
          />
          <button v-else-if="mediaType === '3d'" class="out-link" @click="meshOpen = true">
            {{ t('x2xFlow.inspect3d') }}
          </button>
          <button
            v-else-if="mediaType === 'code' && outputCode && codeKind"
            class="out-link"
            @click="codeOpen = true"
          >
            {{ t('x2xFlow.inspectCode') }}
          </button>
          <div v-else class="lbl">{{ t('x2xFlow.nOutput') }}</div>
        </div>
      </div>

      <!-- model choices, on a long press of a medium glyph -->
      <transition name="fade">
        <FlowBubbles
          v-if="bubblesFor"
          :style="bubblesStyle"
          :options="bubbleOptions"
          :active-id="resolvedConfigId"
          @pick="pickModel"
        />
      </transition>

      <!-- the card at the model's name in the create box -->
      <InfoCard :open="!!modelCardShown" :x="modelCardX" :y="modelCardY" :above="modelCardAbove">
        <InfoCardFacts v-if="modelCardShown" :info="modelCardShown" />
      </InfoCard>

      <!-- the prompt as actually submitted, shown on hover while idle -->
      <transition name="fade">
        <div
          v-if="genHover && lastSubmittedPrompt && genPhase === 'idle'"
          class="gen-prompt"
          :style="genPromptStyle"
        >
          <div class="gen-prompt-head">{{ t('x2xFlow.promptSubmitted') }}</div>
          <div class="gen-prompt-body">{{ lastSubmittedPrompt }}</div>
        </div>
      </transition>

      <!-- The prompt was held in a panel of its own until 2026-08-28, and at
           the prompt until 2026-09-03. It is read and changed on the table, in
           the box the adaption wrote; a run goes on from there without a stop. -->
    </div>

    <!-- The viewport is the canvas. Material floats on it, nothing encloses it. -->
    <div
      ref="canvasEl"
      class="canvas"
      @pointerdown="onCanvasPointerDown"
      @wheel="onWheelZoom"
      @dragover.prevent="zoneGlow = true"
      @dragleave="onDragLeave"
      @drop.prevent="onDrop"
    >
      <div class="world" :style="worldStyle">
        <!-- The action zone: a place, not a frame. What lies in it is what the
             next generation reads; each kind placed inside narrows the reading
             to the zone. Fallen artifacts wake only in here. -->
        <div
          class="zone"
          :class="{ glow: zoneGlow, holds: zoneItemIds.size > 0 }"
          :style="zoneStyle"
          :title="t('x2xFlow.zoneHint')"
        ></div>
        <span
          class="zone-grip"
          :style="{ left: zone.x + 'px', top: zone.y - zone.r + 'px' }"
          :title="t('x2xFlow.zoneDrag')"
          @pointerdown.stop.prevent="startZoneDrag"
        ></span>
        <span
          class="zone-size"
          :style="{ left: zone.x + zone.r + 'px', top: zone.y + 'px' }"
          :title="t('x2xFlow.zoneResize')"
          @pointerdown.stop.prevent="startZoneResize"
        ></span>
        <button
          v-if="readableInZone"
          class="zone-read"
          :style="{ left: zone.x - zone.r + 'px', top: zone.y + 'px' }"
          :title="t('x2xFlow.zoneRead')"
          @pointerdown.stop
          @click.stop="runReading"
        >
          <svg viewBox="0 -960 960 960" fill="currentColor" aria-hidden="true">
            <path d="M784-120 532-372q-30 24-69 38t-83 14q-109 0-184.5-75.5T120-580q0-109 75.5-184.5T380-840q109 0 184.5 75.5T640-580q0 44-14 83t-38 69l252 252-56 56ZM380-420q67 0 113.5-46.5T540-580q0-67-46.5-113.5T380-740q-67 0-113.5 46.5T220-580q0 67 46.5 113.5T380-420Z" />
          </svg>
        </button>
        <!-- Scene capsules: a document the session analysed (UCD-124). The strip
             lies in the WORLD, among the cards, and is placed, moved and sized
             like them — its own coordinates, `landFromPlus` for the place it
             lands on, the shared drag/resize engine for the grip and the corner.
             Until 2026-09-28 it stood in the screen-fixed layer at a hardcoded
             60/60, so a second document lay exactly on the first and neither
             could be moved off it, and the card's grip and corner were drawn but
             wired to nothing.
             While the analysis runs the card already stands here, `busy`: the
             same half-opacity a picture wears while it uploads, over the strip's
             own head, which names the file that was picked. Its × takes the card
             off the board, so it does not carry the clear-canvas tooltip it was
             given here (`canvasClearConfirmYes`, "Clear canvas"); the cards
             above it name nothing there either.
             Drawn before the cards, so every card lies above a strip: on a
             full view a strip can land over the prompt box, and a prompt
             carried out of it landed under it, where nobody saw it arrive. -->
        <FlowCard
          v-for="s in sceneStrips"
          :key="s.id"
          :class="{ busy: s.uploading }"
          :style="{ left: s.x + 'px', top: s.y + 'px', width: s.w + 'px', height: s.h + 'px' }"
          bar
          closable
          resizable
          scroll
          :resize-title="t('x2xFlow.resize')"
          @grip-down="startItemDrag($event, s)"
          @resize-down="startCardResize($event, s, { mode: 'free' })"
          @close="removeSceneStrip(s.id)"
        >
          <SceneStrip :doc="s.doc" :status="sceneStatus(s)" @carry="carryScenePrompt" />
        </FlowCard>

        <!-- The box is FlowCard; where it sits and how wide it is stays here,
             and so does everything that makes it material you can pick up
             again — the bar, the grip, the delete button, the handle. -->
        <FlowCard
          v-for="it in items"
          :key="it.id"
          :class="[it.kind, { busy: it.uploading, inzone: zoneItemIds.has(it.id) }]"
          :style="{ left: it.x + 'px', top: it.y + 'px', width: it.w + 'px' }"
          bar
          closable
          resizable
          :resize-title="t('x2xFlow.resize')"
          :hold-title="t('x2xFlow.flipToBack')"
          @grip-down="startMaterialDrag($event, it)"
          @resize-down="startItemResize($event, it)"
          @close="removeItem(it.id)"
        >
          <!-- The card names itself where the eye starts. Until 2026-08-28 an
               empty prompt box showed an example sentence as its placeholder,
               and a surface with nothing on it looked like a surface with a
               prompt on it: the start control stayed dark and the box beside it
               appeared to be filled. The example is gone, and the word that
               says what this box IS stands in its place. A box the run itself
               laid down names its station there instead. -->
          <template v-if="it.kind === 'text' || it.run" #bar-lead>
            <span v-if="it.kind === 'text'" class="asm-type">{{ cardLabel(it) }}</span>
            <span v-if="it.run" class="asm-run">#{{ it.run }}</span>
          </template>
          <!-- The marks sit in the card's handle and take no press of their
               own: pressing one picks the card up like the rest of the bar.
               Until 2026-09-26 each stopped the press, and the card could not
               be picked up by them. -->
          <template #bar>
            <span
              v-if="it.failed"
              class="asm-surplus err"
              :title="t('x2xFlow.errImageFailed')"
              >!</span
            >
            <span
              v-else-if="readMarkIds.has(it.id)"
              class="asm-surplus words"
              :title="t('x2xFlow.readIntoWordsHint')"
              >Tt</span
            >
            <span
              v-else-if="surplusIds.has(it.id)"
              class="asm-surplus"
              :title="t('x2xFlow.surplusHint')"
              >?</span
            >
          </template>
          <template v-if="it.kind === 'text'">
            <textarea
              v-model="it.text"
              class="asm-ta"
              :style="{ height: it.h + 'px' }"
              @pointerdown.stop="takeCard(it)"
              @focus="takeCard(it)"
              @wheel.stop
            ></textarea>
          </template>
          <audio
            v-else-if="it.kind === 'audio'"
            class="asm-audio"
            :src="it.src"
            controls
            @dblclick.stop.prevent="openInspect(it)"
          ></audio>
          <template v-else-if="it.kind === 'video'">
            <video
              class="asm-video"
              :src="it.src"
              controls
              @dblclick.stop.prevent="openInspect(it)"
            ></video>
          </template>
          <!-- A source a perspective looked up. The front says what was
               searched for; a click turns it, because the article and the text
               it gave ARE the card — there is no front worth enlarging. -->
          <template v-else-if="it.kind === 'source' && it.source">
            <div
              class="asm-src"
              :style="{ minHeight: it.h + 'px' }"
              :title="t('x2xFlow.sourceInspect')"
              @click="openInspect(it)"
            >
              <img class="asm-src-logo" :src="wikipediaMark" alt="Wikipedia" draggable="false" />
              <span class="asm-src-term">{{ it.source.term }}</span>
            </div>
          </template>
          <!-- A generated sketch. The front is one still picture of it running,
               or the runtime's name when the canvas gave nothing; a click opens
               it at size, where it can be read, changed and run again. -->
          <template v-else-if="it.kind === 'code'">
            <div
              class="asm-code"
              :title="t('x2xFlow.openSketch')"
              @click="openInspect(it)"
            >
              <img v-if="it.thumb" class="asm-code-shot" :src="it.thumb" draggable="false" alt="" />
              <span v-else class="asm-code-name">{{
                it.codeKind === 'tonejs' ? 'Tone.js' : 'p5.js'
              }}</span>
            </div>
          </template>
          <template v-else>
            <img
              class="asm-img"
              :src="it.src"
              draggable="false"
              alt=""
              :title="t('x2xFlow.inspect')"
              @click="openInspect(it)"
            />
          </template>
          <!-- The platform's one back (`MediaCardBack`) in the card's own
               `back` slot, as every other surface carries it: the flow board
               was once the one place where holding a card did nothing, while
               the same back stood in the layer the click opens. A click
               enlarges, a hold shows the back. -->
          <template v-if="backFor(it)" #back="{ flipped }">
            <MediaCardBack
              v-bind="backFor(it)!"
              :active="flipped"
              @toggle-favorite="toggleItemFav(it)"
              @download="downloadItem(it)"
              @print="printItem(it)"
            />
          </template>
        </FlowCard>

        <!-- perspectives: the zone applies them to what it reads, in entry order -->
        <div
          v-for="b in bubbles"
          :key="b.id"
          class="pb"
          :class="{ read: zoneBubbleIds.has(b.id) }"
          :style="{ left: b.x + 'px', top: b.y + 'px' }"
          @pointerdown.stop="startBubbleDrag($event, b)"
          @click.stop="onFixtureClick($event, () => openPerspEdit(b))"
        >
          <!-- One disc, two hosts: the board owns the box and the gesture,
               the disc itself is components/PerspectiveBubble.vue. On the
               surface a perspective is not being looked for, it is lying there
               among others: its name stands read-ready the whole time, not only
               under the pointer. -->
          <PerspectiveBubble
            :preview-id="b.previewId"
            :config-id="b.configId"
            :color="pbColor(b)"
            :name="b.configName"
            :read="zoneBubbleIds.has(b.id)"
            :openable="false"
            revealed
          />
          <span
            v-if="zoneBubbleIds.has(b.id) && zoneChain.length > 1"
            class="pb-ord"
            :title="t('x2xFlow.chainOrder', { n: chainIndex(b) })"
            >{{ chainIndex(b) }}</span
          >
          <!-- a perspective that brings an adapter with it ("Cooked Film") wears
               the net at its rim; in the ring under a model that does not
               carry that adapter, the "?" of unused material stands there. -->
          <span
            v-if="bubbleLoraFiles(b).length && zoneBubbleIds.has(b.id) && !bubbleLoraCarried(b)"
            class="asm-surplus pb-net-q"
            :title="bubbleLoraTitle(b) + ' — ' + t('x2xFlow.surplusHint')"
            >?</span
          >
          <span
            v-else-if="bubbleLoraFiles(b).length"
            class="pb-net"
            :title="bubbleLoraTitle(b)"
            ><LoraGlyph
          /></span>
          <button class="pb-del" :title="t('x2xFlow.perspectiveClear')" @pointerdown.stop @click.stop="removeBubble(b.id)">×</button>
        </div>

        <!-- LoRAs: a disc like a perspective, the net for a face. What lies in
             the zone is loaded with the image model of the next run — not
             applied one after another like the perspectives, so no chain
             number. A LoRA the run cannot load (another model picked by hand,
             a run that makes no picture) keeps lying there and wears the "?"
             of unused material: the pick holds, nothing is taken away. -->
        <div
          v-for="l in loraTiles"
          :key="l.id"
          class="pb lora-tile"
          :style="{ left: l.x + 'px', top: l.y + 'px' }"
          @pointerdown.stop="startBubbleDrag($event, l)"
          @click.stop="onFixtureClick($event, () => openLoraEdit(l))"
        >
          <PerspectiveBubble
            :name="l.name"
            :read="zoneLoraIds.has(l.id)"
            :read-color="LORA_COLOR"
            :openable="false"
            revealed
          >
            <LoraGlyph light />
          </PerspectiveBubble>
          <span
            v-if="loraUnusedIds.has(l.id)"
            class="asm-surplus pb-surplus"
            :title="t('x2xFlow.surplusHint')"
            >?</span
          >
          <span
            v-if="l.strength !== 100"
            class="pb-pct"
            :title="t('x2xFlow.loraStrength')"
            >{{ l.strength }} %</span
          >
          <button class="pb-del" :title="t('x2xFlow.loraClear')" @pointerdown.stop @click.stop="removeLoraTile(l.id)">×</button>
        </div>
      </div>

      <!-- the written half of the perspective: opens at its bubble, edits the live text -->
      <div
        v-if="perspEdit"
        class="persp-edit"
        :style="{ left: perspEdit.x + 'px', top: perspEdit.y + 'px', width: perspEdit.w + 'px' }"
        @pointerdown.stop
        @wheel.stop
      >
        <div class="pe-head">
          <input
            v-if="kept.canKeep"
            v-model="perspEditName"
            class="pe-name-input"
            :placeholder="t('x2xFlow.perspectiveNamePh')"
            :title="t('x2xFlow.perspectiveNameHint')"
            @keydown.enter.prevent="keepCurrent"
          />
          <span v-else class="pe-name">{{
            perspEditBubble?.configName || t('x2xFlow.perspectiveLabel')
          }}</span>
          <button class="pe-close" @click="perspEdit = null">×</button>
        </div>
        <textarea
          ref="perspEditTa"
          v-model="perspEditText"
          class="pe-text"
          :placeholder="t('x2xFlow.perspectiveWritePh')"
          :title="t('x2xFlow.perspectivesHint')"
          @keydown.esc="perspEdit = null"
        ></textarea>
        <!-- Keeping is a gesture, never a side effect of typing: nothing leaves
             this page until somebody says so. Without a session there is no
             place to keep it, and the row is simply not there. -->
        <div v-if="kept.canKeep" class="pe-keep">
          <span class="pe-keep-note">{{ keepNote }}</span>
          <button
            class="pe-keep-btn"
            :disabled="keepBusy || !perspEditText.trim()"
            :title="t('x2xFlow.perspectiveKeepHint')"
            @click="keepCurrent"
          >
            {{ perspEditBubble?.promptId ? t('x2xFlow.perspectiveKeepAgain') : t('x2xFlow.perspectiveKeep') }}
          </button>
        </div>
      </div>

      <!-- the strength half of a LoRA: opens at its tile like the written half
           of a perspective. The strength is a percent of the trained strength
           on the axis LoRA Explorer runs on (50–100 %); the
           trigger and the model stand there to be read, nothing of them is
           changed here — the trigger goes in front of the prompt as it was
           trained. -->
      <div
        v-if="loraEdit && loraEditTile"
        class="persp-edit lora-edit"
        :style="{ left: loraEdit.x + 'px', top: loraEdit.y + 'px', width: loraEdit.w + 'px' }"
        @pointerdown.stop
        @wheel.stop
        @keydown.esc="loraEdit = null"
      >
        <div class="pe-head">
          <span class="pe-name">{{ loraEditTile.name }}</span>
          <button class="pe-close" @click="loraEdit = null">×</button>
        </div>
        <div class="le-row le-axis">
          <span class="le-k">{{ t('x2xFlow.loraStrength') }}</span>
          <MarkedSlider
            class="le-slider"
            :model-value="loraEditTile.strength"
            :min="50"
            :max="100"
            :step="1"
            :marks="LORA_MARKS"
            :aria-label="t('x2xFlow.loraStrength')"
            :value-text="`${loraEditTile.strength} %`"
            compact
            @update:model-value="setLoraStrength(loraEditTile, $event)"
          />
        </div>
        <div class="le-row">
          <span class="le-k">{{ t('x2xFlow.loraTrigger') }}</span>
          <span class="le-v">{{ loraEditTile.trigger || '—' }}</span>
        </div>
        <div class="le-row">
          <span class="le-k">{{ t('settings.loras.models') }}</span>
          <span class="le-v">{{ loraModelLabel(loraEditTile) }}</span>
        </div>
      </div>

      <div class="view-tools" @pointerdown.stop>
        <button title="+" @click="zoomBy(1.2)">+</button>
        <button title="−" @click="zoomBy(1 / 1.2)">−</button>
        <button title="1:1" @click="resetView">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7">
            <circle cx="12" cy="12" r="7" />
            <circle cx="12" cy="12" r="1.6" fill="currentColor" />
          </svg>
        </button>
      </div>
    </div>

    <!-- the perspective: a boxless, pulsing constellation you can put anywhere -->
    <button
      ref="perspEl"
      class="persp"
      :style="{ left: glyph.x + 'px', top: glyph.y + 'px' }"
      :title="t('x2xFlow.perspectivePick')"
      @pointerdown.stop="startPointDrag($event, glyph)"
      @click="onGlyphClick"
    >
      <svg viewBox="0 -960 960 960" fill="currentColor" aria-hidden="true">
        <path d="M480-60q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm0-80q17 0 28.5-11.5T520-180q0-17-11.5-28.5T480-220q-17 0-28.5 11.5T440-180q0 17 11.5 28.5T480-140Zm-260-70q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm520 0q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm-520-80q17 0 28.5-11.5T260-330q0-17-11.5-28.5T220-370q-17 0-28.5 11.5T180-330q0 17 11.5 28.5T220-290Zm520 0q17 0 28.5-11.5T780-330q0-17-11.5-28.5T740-370q-17 0-28.5 11.5T700-330q0 17 11.5 28.5T740-290ZM220-510q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm520 0q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm-520-80q17 0 28.5-11.5T260-630q0-17-11.5-28.5T220-670q-17 0-28.5 11.5T180-630q0 17 11.5 28.5T220-590Zm520 0q17 0 28.5-11.5T780-630q0-17-11.5-28.5T740-670q-17 0-28.5 11.5T700-630q0 17 11.5 28.5T740-590Zm-260-70q-50 0-85-35t-35-85q0-50 35-85t85-35q50 0 85 35t35 85q0 50-35 85t-85 35Zm0-80q17 0 28.5-11.5T520-780q0-17-11.5-28.5T480-820q-17 0-28.5 11.5T440-780q0 17 11.5 28.5T480-740Z" />
      </svg>
    </button>

    <!-- bringing material in: the same free fixture as the perspective, one
         step on — it stands where the material is to land, and the three ways
         to bring some bloom around it on a click. It breathes in the same
         faint rhythm as the perspective beside it — one pulse for the pair,
         not one sign calling over the other. -->
    <button
      ref="addEl"
      class="addg"
      :class="{ open: addOpen }"
      :style="{ left: add.x + 'px', top: add.y + 'px' }"
      :title="t('x2xFlow.bringMaterial')"
      @pointerdown.stop.prevent="startPointDrag($event, add)"
      @click="onAddClick"
    >
      <svg viewBox="0 -960 960 960" fill="currentColor" aria-hidden="true">
        <path d="M440-440H200v-80h240v-240h80v240h240v80H520v240h-80v-240Z" />
      </svg>
    </button>

    <!-- the LoRA sign: the third free fixture, lower left of the plus as the
         perspective stands lower right of it — a pliable net over a rigid
         grid, in its own violet, breathing in the one rhythm of the three. A
         click opens the chooser; the sign is dragged by the same grip as the
         other two. -->
    <button
      ref="loraEl"
      class="lorag"
      :style="{ left: loraFix.x + 'px', top: loraFix.y + 'px' }"
      :title="t('x2xFlow.loraPick')"
      @pointerdown.stop="startPointDrag($event, loraFix)"
      @click="onLoraGlyphClick"
    >
      <LoraGlyph />
    </button>

    <!-- What this surface is set to, out of the work: the same free fixture as
         on Together, in the other corner, above the zoom cluster. It holds the
         one action that is not part of the work itself: clearing the canvas. -->
    <SurfaceGear class="fixture-gear" :title="t('x2xFlow.surfaceSettings')">
      <button class="gear-action" @click="clearAsk = true">{{ t('x2xFlow.canvasClear') }}</button>
    </SurfaceGear>

    <!-- the three ways, on an arc around the plus. The arc turns toward the
         free middle of the view, so at the edge where the plus usually rests
         it never opens off the screen. -->
    <div v-if="addOpen" class="addopt" :style="{ left: add.x + 'px', top: add.y + 'px' }">
      <button
        v-for="(o, i) in addOptions"
        :key="o.id"
        class="ao"
        :style="{
          transform: `translate(-50%, -50%) translate(calc(var(--ao-r) * ${o.ux}), calc(var(--ao-r) * ${o.uy}))`,
          '--ao-d': i * 45 + 'ms',
        }"
        :title="o.title"
        @pointerdown.stop
        @click.stop="o.run()"
      >
        <svg viewBox="0 -960 960 960" fill="currentColor" aria-hidden="true">
          <path :d="o.d" />
        </svg>
        <span class="ao-l">{{ o.label }}</span>
      </button>
    </div>

    <!-- Inspect: the piece at its own size, and beside it its back — what made
         it — on the platform's one layer for a medium looked at large. This
         page once drew a layer of its own here, with the back only after a
         550 ms hold; now one click opens both (one click, one view, on every
         surface). A looked-up source has no medium,
         so the Wikipedia mark stands in for one beside its record. -->
    <MediaFullscreen
      :src="inspectedSrc"
      :kind="inspectedKind"
      :code="inspected?.kind === 'code' ? inspected.text || '' : ''"
      :code-kind="inspected?.codeKind || 'p5js'"
      :back="inspectedBack"
      @close="inspected = null"
      @toggle-favorite="toggleInspectedFav"
      @download="downloadInspected"
      @print="printInspected"
    />

    <input ref="fileEl" type="file" accept="image/*" multiple hidden @change="onFilePick" />
    <!-- the document way has its own input: only PDFs reach the scene
         pipeline, and the image picker no longer offers them. -->
    <input ref="docFileEl" type="file" accept=".pdf" hidden @change="onDocFilePick" />

    <!-- The mesh at size: turn it, do not leave the flow for it. -->
    <div v-if="meshOpen" class="sketch-ov" @click.self="meshOpen = false">
      <model-viewer v-if="mediaUrl" :src="mediaUrl" camera-controls auto-rotate class="mesh-view"></model-viewer>
      <button class="inspect-x" :title="t('x2xFlow.inspectClose')" @click="meshOpen = false">×</button>
    </div>

    <!-- What the machine wrote, at size: read it, change it, run it again. -->
    <div v-if="codeOpen" class="sketch-ov" @click.self="codeOpen = false">
      <div class="code-box">
        <CodeSandbox :code="outputCode" :kind="codeKind || 'p5js'" />
        <button class="inspect-x" :title="t('x2xFlow.inspectClose')" @click="codeOpen = false">
          &times;
        </button>
      </div>
    </div>

    <!-- Sketching: the same canvas the image input offers, on the board. -->
    <div v-if="sketchOpen" class="sketch-ov" @click.self="sketchOpen = false">
      <div class="sketch-box">
        <SketchCanvas @image-uploaded="onSketchUploaded" @image-removed="sketchOpen = false" />
        <button class="inspect-x" :title="t('x2xFlow.sketchClose')" @click="sketchOpen = false">×</button>
      </div>
    </div>

    <InterceptionPresetOverlay
      :visible="presetOverlayVisible"
      @preset-selected="onPresetSelected"
      @close="presetOverlayVisible = false"
    />

    <LoraPickOverlay v-model="loraOverlayVisible" :label-for="loraModelName" @pick="onLoraPicked" />

    <!-- The question stands over the surface, not in the gear (see the registry). -->
    <SurfaceConfirm
      v-if="clearAsk"
      :text="t('x2xFlow.canvasClearConfirm')"
      :yes="t('x2xFlow.canvasClearConfirmYes')"
      :cancel="t('common.cancel')"
      @confirm="clearCanvas"
      @cancel="clearAsk = false"
    />

    <!-- The document intake speaks here: a refused PDF, a second upload of one
         already analysed, an analysis that broke off, a service that did not
         answer. The ref IS that channel — without it the four speak() calls in
         the intake are no-ops, as they were from the move onto this page
         (UCD-124) until 2026-09-28. -->
    <PlatformVoice ref="platformVoice" :anchors="voiceAnchors" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, nextTick, onMounted, onBeforeUnmount, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'
import FlowCard from '@/components/FlowCard.vue'
import FlowRunPanel from '@/components/FlowRunPanel.vue'
import FlowBubbles, { type FlowBubble } from '@/components/FlowBubbles.vue'
import InfoCard from '@/components/InfoCard.vue'
import InfoCardFacts from '@/components/InfoCardFacts.vue'
import type { ChipInfo } from '@/components/ChipSelect.vue'
import { useInfoCard } from '@/composables/useInfoCard'
import { useOutputCards } from '@/composables/useOutputCards'
import MediumGlyph from '@/components/MediumGlyph.vue'
import InterceptionPresetOverlay from '@/components/InterceptionPresetOverlay.vue'
import PerspectiveBubble from '@/components/PerspectiveBubble.vue'
import LoraGlyph from '@/components/LoraGlyph.vue'
import SurfaceGear from '@/components/SurfaceGear.vue'
import SurfaceConfirm from '@/components/SurfaceConfirm.vue'
import LoraPickOverlay from '@/components/LoraPickOverlay.vue'
import MarkedSlider, { type SliderMark } from '@/components/MarkedSlider.vue'
import SketchCanvas from '@/components/SketchCanvas.vue'
import CodeSandbox from '@/components/CodeSandbox.vue'
import MediaFullscreen from '@/components/MediaFullscreen.vue'
import MediaCardBack from '@/components/MediaCardBack.vue'
import type { MediaBack } from '@/components/mediaBack'
import PlatformVoice, { type VoiceAnchor } from '@/components/PlatformVoice.vue'
import '@google/model-viewer'
import {
  useGenerationStream,
  safetyBlockKey,
  classifyError,
  busyCauseKey,
  waitParts,
  durationLabel as durationWords,
  queueWaitLabel as queueWaitWords,
  type BusyNote,
  type GenerationErrorType,
} from '@/composables/useGenerationStream'
import { useDeviceId } from '@/composables/useDeviceId'
import { useHold } from '@/composables/useHold'
import { READING_FRAMES, isReadingFrame } from '@/data/readingFrames'
import { RASTER_IMAGE_MODEL_SINGLE_DEFAULT } from '@/data/rasterImageModels'
import { p5jsFrame, SKETCH_FRAME_MESSAGE } from '@/lib/sketchFrame'
import { modelLine as sharedModelLine } from '@/lib/modelPlace'
import { useSafetyEventStore } from '@/stores/safetyEvent'
import { useFavoritesStore, type FavoriteItem } from '@/stores/favorites'
import { useModelAvailability } from '@/composables/useModelAvailability'
import { postStreamedRun } from '@/services/directRun'
import { useCurrentSession } from '@/composables/useCurrentSession'
import { usePageContextStore } from '@/stores/pageContext'
import { useKeptPerspectivesStore, keptColor } from '@/stores/keptPerspectives'
import { useLoraStore, LORA_COLOR, type LoraAdapter } from '@/stores/loras'
import { useConfigSelectionStore } from '@/stores/configSelection'
import { useLabAuthStore } from '@/stores/labAuth'
import type { PageContext } from '@/composables/usePageContext'
import { useFlowStage, type FlowRect } from '@/composables/useFlowStage'
import { useMediumInference, MEDIA, type MediumId } from '@/composables/useMediumInference'
import { useAssemblageBoard, type AsmItem, type AsmKind } from '@/composables/useAssemblageBoard'
import { takeHandedImage } from '@/lib/handOverImage'
import { downloadBlob, downloadMedia, mediaExtension, mediaFileName, runStem } from '@/lib/downloadMedia'
import { printMedia } from '@/lib/printMedia'
// The minimal geometry the shared drag/resize engine reads and writes. The
// board's own items satisfy it; a scene strip card declares it (see BoardSceneStrip).
import type { BoardItem } from '@/composables/usePanZoom'
import { restingPlaces, JOG } from '@/composables/flowRestLayout'
import { findFreeSpot, type Rect, type Disc } from '@/composables/useFreeSpot'
import {
  resolveRoute,
  ROUTE_LABELS,
  IMAGE_INPUT_ROUTES,
  imageInputRoute,
} from '@/composables/useMaterialRouting'
import { classifyMusicRoles } from '@/composables/useTextRoles'
import { planComposition, type ComposeOp, type ComposeRole } from '@/composables/useCompositionRouting'
import {
  quickImageSafetyCheck,
  useMaterialIntake,
  uploadImageFromUrl,
  type QuickSafetyResult,
} from '@/composables/useMaterialIntake'
import {
  uploadSceneDocument,
  fetchSceneJob,
  fetchSceneDocument,
  listSceneDocuments,
  type SceneDocument,
  type SceneJobState,
} from '@/composables/useSceneIntake'
import SceneStrip from '@/components/SceneStrip.vue'
import { wordFeed, type WordFeed } from '@/composables/useWordFeed'
// Imported, not referenced by path: the backend serves dist root files from a
// fixed allow-list of names, so anything else there answers with index.html.
// Through the bundler it lands under /assets/, which is served.
import wikipediaMark from '@/assets/wikipedia-logo-64px.png'

import { STANDARD_SEED } from '@/composables/useSeedAutomatic'
const { t, locale } = useI18n()
const deviceId = useDeviceId()
const platformVoice = ref<InstanceType<typeof PlatformVoice> | null>(null)
const safetyStore = useSafetyEventStore()
const favStore = useFavoritesStore()
const { updateSession, clearSession } = useCurrentSession()

// Scene documents (UCD-124): a PDF the plus brings in is analysed into scene
// capsules; the strips stand on the board like every other thing worked on here.
// Session-bound: the document space hangs on the canvas session (deviceId) and
// dies with it; nothing reaches Tier-O.
interface BoardSceneStrip extends BoardItem {
  /**
   * The analysed document — or, while the worker is still on it, the stand-in
   * that carries the picked file's name and no capsules, so the strip shows its
   * head alone under the busy dimming.
   */
  doc: SceneDocument
  /** The analysis is still running (see `intakeSceneDocument`). */
  uploading?: boolean
  /**
   * The analysis job the card stands behind, from the upload to the settled
   * document: kept with the card in the session copy, so a return to the
   * page follows it on (`restoreSceneStrips`).
   */
  job?: { id: string; docId: string }
  /** What the job reported last (`sceneStatus` reads it). */
  jobState?: SceneJobState
}
/** What a strip card measures when it lands. The corner sizes it from there. */
const SCENE_STRIP_W = 340
const SCENE_STRIP_H = 260
/** A strip's identity on the BOARD; the document's own id lives in `doc.docId`. */
let sceneSeq = 0
// A deep ref, like the board's own items: the drag and the corner write x/y/w/h
// on the strip itself, and a shallow ref shows neither.
const sceneStrips = ref<BoardSceneStrip[]>([])
const fileEl = ref<HTMLInputElement | null>(null)
const docFileEl = ref<HTMLInputElement | null>(null)
const pageContextStore = usePageContextStore()
// Who is looking: a failure the person at the surface cannot answer is passed
// on by a participant and read as a state by whoever runs the room.
const auth = useLabAuthStore()

// ---------- Platform voice: where a sentence about this page may dock ----------
// Only screen-fixed elements: the three flow nodes sit in .map-wrap and the
// perspective glyph in .canvas, so a docked sentence always lands in view.
// Nothing inside .world is used - the board pans and zooms away under it.
const voiceAnchors: VoiceAnchor[] = [
  // Preparation node: the medium glyphs and the resolved model
  { id: 'create', selector: '.nd.mix', words: ['eingabe', 'input', 'ausgangsmaterial', 'medium', 'medien'] },
  // Generation node: the run with its stations, safety state and progress
  { id: 'gen', selector: '.nd.op', words: ['transform', 'verwandl', 'verwandel', 'umwandl', 'generier', 'generat'] },
  // Output node: the denoising preview, then the finished medium
  { id: 'output', selector: '.nd.out', words: ['ergebnis', 'result', 'ausgabe', 'output'] },
  // The perspective glyph on the board (opens the preset overlay)
  { id: 'perspective', selector: '.persp', words: ['perspektive', 'perspective', 'blickwinkel'] },
  // The plus on the board: the three ways to bring material in
  {
    id: 'bring',
    selector: '.addg',
    words: ['hinzufügen', 'material', 'skizze', 'sketch', 'hochladen', 'upload'],
  },
]

type NodeId = 'create' | 'gen' | 'output'

// Three uniform nodes: what you bring, what turns it, what comes back.
// Stage 3 (check + translation) is not a station of its own — it folds into
// generation, where its state surfaces on the run's card.
const W = 1060
const H = 150
// The preparation node carries more instruments (the six media glyphs and the
// resolved model name) than generation or output, which show one glyph or
// one image — it alone gets extra width. The glyph row is sized in rem/vw and
// does NOT ride the stage scale, so the node has to be wide enough to hold it
// at the largest --flow-glyph-medium: 6 glyphs + 5 gaps of 0.34em is 7.7em,
// ~262px at the 2.125rem cap, against 300 world px = ~283 screen px at the
// design width. Margins and inter-node gaps stay equal (110 throughout) inside
// the same world width (W), so nothing else on the stage changes size.
const RMAP: Record<NodeId, FlowRect> = {
  create: { x: 110, y: 20, w: 300, h: 110 },
  gen: { x: 520, y: 20, w: 160, h: 110 },
  output: { x: 790, y: 20, w: 160, h: 110 },
}
const EDGES: [NodeId, NodeId][] = [
  ['create', 'gen'],
  ['gen', 'output'],
]

const { mapEl, cw, ch, rect, rectStyle, line, isCompact } = useFlowStage(W, H)

/**
 * The stage measures itself continuously while the map's height transitions
 * (on mount, and whenever it recedes), so every node rect moves frame by frame.
 * The generation node's pull must not animate THAT — it would drag behind the
 * layout and slide in from nowhere on load. It animates only once the stage
 * has held still for a moment.
 */
const stageSettled = ref(false)
let settleTimer: ReturnType<typeof setTimeout> | null = null
watch(
  [cw, ch],
  () => {
    stageSettled.value = false
    if (settleTimer) clearTimeout(settleTimer)
    settleTimer = setTimeout(() => {
      stageSettled.value = true
    }, 220)
  },
  { immediate: true }
)
onBeforeUnmount(() => {
  if (settleTimer) clearTimeout(settleTimer)
})

const edgeLines = computed(() =>
  EDGES.map(([a, b]) => ({
    p: line(RMAP[a], RMAP[b]),
    on: activeTarget.value === b,
  }))
)

// --- Assemblage board: the material, floating straight on the viewport ---
const canvasEl = ref<HTMLElement | null>(null)

const {
  zoom,
  pan,
  items,
  worldStyle,
  addText,
  addSource,
  addCode,
  addImage,
  addMedia,
  removeItem,
  setItems,
  zoomBy,
  resetView: resetViewBase,
  startPan,
  startItemDrag,
  startItemResize,
  startCardResize,
  onWheelZoom,
  combinedText,
  imageItems,
  audioItems,
  videoItems,
  imagePaths,
  uploadsPending,
  uploadsFailed,
} = useAssemblageBoard()

/**
 * The piece under inspection: the medium at full size and, beside it, its
 * back. One click opens both. Formerly a click opened the medium alone and
 * only a 550 ms hold brought the back; the first click already zooms, so a
 * second one could never reach the object. That split is gone with the
 * page's own layer, and the platform's layer shows both at once.
 */
const inspected = ref<AsmItem | null>(null)
function openInspect(it: AsmItem) {
  inspected.value = it
}
/** What the layer is handed: a looked-up source has no file, so its mark stands in. */
const inspectedSrc = computed(() => {
  const it = inspected.value
  if (!it) return null
  if (it.kind === 'source') return wikipediaMark
  return it.src || null
})
const inspectedKind = computed<'image' | 'video' | 'audio' | 'code'>(() => {
  const k = inspected.value?.kind
  return k === 'video' || k === 'audio' || k === 'code' ? k : 'image'
})
const sketchOpen = ref(false)
const meshOpen = ref(false)
/**
 * Two output configs hand back JavaScript instead of a file — p5.js draws, and
 * Tone.js plays. Until today the only surface that could run it was the text
 * page; it moved into CodeSandbox and opens from here.
 */
const codeOpen = ref(false)
const outputCode = ref('')
/** Fixed when the code arrives, not read off the current choice: the medium may
    well have been changed again while the piece was standing there. */
const codeKind = ref<'p5js' | 'tonejs' | ''>('')
const meshThumb = ref('')

// --- Action zone: a place on the board; what lies in it is what the run reads ---
// Per kind: as soon as one piece of a kind lies in the zone, only the zone's
// pieces of that kind count; an empty zone leaves the whole board in force.
// The zone lives in world coordinates, so membership is a fact of the
// arrangement and survives pan and zoom. Perspectives obey the same law:
// the bubble lying in the zone is the one that is read.
const ZONE_R_MIN = 140
const ZONE_R_MAX = 520
const zone = reactive({ x: 640, y: 270, r: 240 })
const zoneGlow = ref(false)

const zoneStyle = computed(() => ({
  left: zone.x - zone.r + 'px',
  top: zone.y - zone.r + 'px',
  width: zone.r * 2 + 'px',
  height: zone.r * 2 + 'px',
}))

const zoneItemIds = computed<Set<string>>(() => {
  const s = new Set<string>()
  for (const it of items.value) {
    // A source is evidence, not material. Were it counted here it would arm the
    // zone override all by itself — the circle would become the whole reading
    // and everything the user wrote outside it would stop being read, with
    // nothing on screen saying why. A sketch is the same case for the same
    // reason: no pipeline reads runnable code, so a sketch pulled into the
    // circle would silence the board and leave a run with nothing.
    if (it.kind === 'source' || it.kind === 'code') continue
    const dx = it.x + it.w / 2 - zone.x
    const dy = it.y + it.h / 2 - zone.y
    if (dx * dx + dy * dy <= zone.r * zone.r) s.add(it.id)
  }
  return s
})

/**
 * The zone override: once anything material lies in the circle, the circle is
 * the entire reading — every kind, only what lies inside. Only a circle empty
 * of material reads the whole board, and even then artifacts that fell onto
 * the table by themselves lie ready until someone puts them in. Deliberate
 * placement is the gesture that turns a product back into material.
 */
function effectiveOf(list: AsmItem[]): AsmItem[] {
  if (zoneItemIds.value.size) return list.filter((i) => zoneItemIds.value.has(i.id))
  return list.filter((i) => !i.fell)
}
const effTextItems = computed(() =>
  effectiveOf(items.value.filter((i) => i.kind === 'text' && !!i.text && !!i.text.trim()))
)
const effCombinedText = computed(() => effTextItems.value.map((i) => i.text!.trim()).join('\n\n'))
const effImageItems = computed(() => effectiveOf(imageItems.value))
const effAudioItems = computed(() => effectiveOf(audioItems.value))
const effVideoItems = computed(() => effectiveOf(videoItems.value))
/**
 * The furthest station whose OWN box lies in the ring. A run started on one of
 * them takes the chain up from there: an interception is adapted for the chosen
 * medium, an adaption goes straight to the check and the translation. What is
 * READ stays what the ring says it is — the box only decides where the chain
 * picks up.
 */
const zoneStation = computed<'interception' | 'adaption' | null>(() => {
  if (effTextItems.value.some((i) => i.station === 'adaption')) return 'adaption'
  if (effTextItems.value.some((i) => i.station === 'interception')) return 'interception'
  return null
})
/** Where THIS run picked up, frozen when it started. */
const runResume = ref<'interception' | 'adaption' | null>(null)
const effUploadsPending = computed(() => effImageItems.value.some((i) => i.uploading))
const effUploadsFailed = computed(() => effImageItems.value.some((i) => i.failed))

// Zone drag: the same screen→world conversion as an item drag.
let zdX = 0
let zdY = 0
function onZoneMove(e: PointerEvent) {
  zone.x += (e.clientX - zdX) / zoom.value
  zone.y += (e.clientY - zdY) / zoom.value
  zdX = e.clientX
  zdY = e.clientY
}
function endZoneDrag() {
  window.removeEventListener('pointermove', onZoneMove)
  window.removeEventListener('pointerup', endZoneDrag)
}
function startZoneDrag(e: PointerEvent) {
  zdX = e.clientX
  zdY = e.clientY
  window.addEventListener('pointermove', onZoneMove)
  window.addEventListener('pointerup', endZoneDrag)
}
function onZoneResize(e: PointerEvent) {
  const p = dropPoint(e)
  if (!p) return
  zone.r = Math.round(Math.min(ZONE_R_MAX, Math.max(ZONE_R_MIN, Math.hypot(p.x - zone.x, p.y - zone.y))))
}
function endZoneResize() {
  window.removeEventListener('pointermove', onZoneResize)
  window.removeEventListener('pointerup', endZoneResize)
}
function startZoneResize(e: PointerEvent) {
  onZoneResize(e)
  window.addEventListener('pointermove', onZoneResize)
  window.addEventListener('pointerup', endZoneResize)
}

/** While material is in hand, the zone shows itself as the place to put it. */
function startMaterialDrag(e: PointerEvent, it: AsmItem) {
  zoneGlow.value = true
  window.addEventListener('pointerup', () => (zoneGlow.value = false), { once: true })
  startItemDrag(e, it)
}
function onDragLeave(e: DragEvent) {
  const el = canvasEl.value
  if (el && e.relatedTarget && el.contains(e.relatedTarget as Node)) return
  zoneGlow.value = false
}

/**
 * A finished artifact falls onto the table next to the zone — visible material,
 * dormant until placed in. Successive falls fan out so nothing stacks.
 */
let fallSeq = 0
const fallenSrcs = new Set<string>()
function fallPoint(w: number, h: number): { x: number; y: number } {
  const i = fallSeq
  fallSeq += 1
  return {
    x: zone.x + zone.r + 40 + (i % 3) * 28,
    y: zone.y - h / 2 + ((i % 5) - 2) * 34,
  }
}

/**
 * Where a run's own boxes go. The pile above is right for pictures and wrong
 * for text: 34px apart, two boxes of 240 are one box with a shadow, and the
 * interception and the adaption of a run have to be readable next to each
 * other. They take a column instead -- under each other as long as the board
 * shows room for the next one, then the column beside it.
 */
let stationSlot = 0
function stationPoint(w: number, h: number): { x: number; y: number } {
  const gap = 16
  const top = zone.y - zone.r
  const el = canvasEl.value
  // How far down the board actually reaches, in world coordinates: the stage is
  // panned and zoomed under these boxes, so the window's own height says
  // nothing about the room there is here.
  const bottom = el ? (el.clientHeight - pan.y) / zoom.value : top + 2 * (h + gap)
  const rows = Math.max(1, Math.floor((bottom - top) / (h + gap)))
  const i = stationSlot % (rows * 3)
  stationSlot += 1
  return {
    x: zone.x + zone.r + 40 + Math.floor(i / rows) * (w + gap),
    y: top + (i % rows) * (h + gap),
  }
}

/**
 * The end of a station's box. An empty one is litter and goes. One with words
 * in it stays as material -- unless `keepText` is off, which is for the two
 * cases where the words may not lie on the table: a run the page has let go
 * of, and a reading the check refused.
 */
function closeStationCard(it: AsmItem | null, keepText = true) {
  if (!it) return
  if (keepText && (it.text || '').trim()) return
  removeItem(it.id)
}

/**
 * Every box still being written into, by the id of the box. A run that is let
 * go of puts the pen down through here, and a hand reaching for a box takes
 * the rest of the text at once rather than racing the queue.
 */
const cardFeeds = new Map<string, WordFeed>()

/** A station's box, written into one word every 50 ms (useWordFeed). */
function feedInto(card: AsmItem): WordFeed {
  cardFeeds.get(card.id)?.stop()
  const f = wordFeed((text) => {
    card.text = text
  })
  const forget = () => {
    if (cardFeeds.get(card.id) === wrapped) cardFeeds.delete(card.id)
  }
  const wrapped: WordFeed = {
    push: (t) => f.push(t),
    finish: (t) => f.finish(t).then(forget),
    flush: () => {
      f.flush()
      forget()
    },
    stop: () => {
      f.stop()
      forget()
    },
  }
  cardFeeds.set(card.id, wrapped)
  return wrapped
}

// Leaving the page puts every pen down: an interval left running writes into a
// board that is no longer on screen. A box still being written is cut off by
// that as by a stop, and is forgotten the same way (see stopRunHere).
onBeforeUnmount(() => {
  if (memoryBoxCut()) lastChain.value = null
  for (const feed of [...cardFeeds.values()]) feed.stop()
})

/**
 * Somebody has reached for this box. Whatever is still queued goes in now:
 * a queue writing over a text that is being edited would take the edit back
 * word by word.
 */
function takeCard(it: AsmItem) {
  cardFeeds.get(it.id)?.flush()
}

/** What a text box says it is, in its bar, before the dots. */
function cardLabel(it: AsmItem): string {
  // A box that was laid down for a reason says the reason.
  if (it.title) return it.title
  if (it.station === 'interception') return t('x2xFlow.runInterception')
  if (it.station === 'adaption') return t('x2xFlow.runAdaption')
  return t('x2xFlow.promptCardLabel')
}
function fallMedia(
  kind: 'audio' | 'video',
  src: string,
  runId: string,
  meta?: AsmItem['meta'],
  at?: { x: number; y: number } | null
) {
  // A drop is a deliberate gesture: it may repeat material and counts as
  // user-placed; only self-falling artifacts dedupe and obey the fell rule.
  if (!at && fallenSrcs.has(src)) return
  fallenSrcs.add(src)
  const size = kind === 'audio' ? { w: 260, h: 56 } : { w: 280, h: 170 }
  const p = at ? { x: at.x - size.w / 2, y: at.y - size.h / 2 } : fallPoint(size.w, size.h)
  const it = addMedia(kind, src, runId, p.x, p.y)
  it.fell = !at
  // Which run made it, on the artifact as on the two boxes of words before it:
  // three pictures side by side say nothing about which run each came out of.
  if (!at) it.run = runOrdinal.value
  if (meta) it.meta = meta
}
/**
 * An image artifact is re-uploaded so it carries the server path i2x reads.
 *
 * A picture BROUGHT here (`at` is the point it was let go at) is checked like
 * any other picture entering a surface; the run's own output falling onto its
 * own table (`at` null) is not, having come through Stage 3 of that run at this
 * level moments ago. The fall does not release a held medium/model pick: only a
 * user upload does.
 */
async function fallImage(
  runId: string,
  url: string,
  meta?: AsmItem['meta'],
  at?: { x: number; y: number } | null
): Promise<string> {
  if (!at && fallenSrcs.has(url)) return ''
  fallenSrcs.add(url)
  const p = at ? { x: at.x - 95, y: at.y - 75 } : fallPoint(190, 150)
  const it = addImage(url, p.x, p.y)
  it.runId = runId
  it.fell = !at
  if (!at) it.run = runOrdinal.value
  if (meta) it.meta = meta
  it.uploading = true
  try {
    const up = await uploadImageFromUrl(url, `${runId}.png`)
    // A picture BROUGHT here is checked, whatever made it. The run's own output
    // falling onto its own table is not (`at` is null there): it came through
    // Stage 3 of this very run, at this level, moments ago. A favourite or a
    // picture handed over from another surface is a different matter — it
    // carries the level of the session that made it, and Stage 3 checks an
    // image at kids and youth level only, so an `open` run's picture has no
    // image verdict at all. The drop path took the fall's exemption until
    // 2026-09-04 and put it on the board as material to run with.
    if (at) {
      const safety = await quickImageSafetyCheck(up.path)
      if (!safety.safe) {
        // The url goes back out of the dedupe: a refusal is not a fall that has
        // happened, and the same picture must be able to arrive again.
        fallenSrcs.delete(url)
        removeItem(it.id)
        safetyStore.reportBlock(
          'vlm_input',
          safety.errorMessage || '',
          [],
          safety.vlmDescription,
          safety.operational,
        )
        return ''
      }
      if (safety.vlmDescription) safetyStore.reportAnalysis(safety.vlmDescription, true)
    }
    it.imageId = up.imageId
    it.path = up.path
    it.src = up.servedUrl
    it.uploading = false
    // The path the pipelines read — and what a run that is going to READ its
    // own picture goes on with, instead of asking the table what lies there.
    return up.path
  } catch {
    it.uploading = false
    it.failed = true
    return ''
  }
}

/**
 * A generated sketch falls onto the table like every other artifact: dormant
 * material with its provenance on the back. What the card shows is one still
 * picture of the sketch running — see captureSketchFrame; until it arrives, or
 * when the canvas gives nothing, the card carries the runtime's name.
 */
function fallCode(
  code: string,
  kind: 'p5js' | 'tonejs',
  runId: string,
  meta?: AsmItem['meta'],
  at?: { x: number; y: number } | null
) {
  // Same dedupe as the other falls, keyed on the run — a sketch has no url.
  // A drop is a deliberate gesture and repeats freely, as with fallMedia.
  const key = 'code:' + runId
  if (!at && fallenSrcs.has(key)) return
  fallenSrcs.add(key)
  const p = at ? { x: at.x - 120, y: at.y - 100 } : fallPoint(240, 200)
  const it = addCode(code, kind, runId, p.x, p.y)
  it.fell = !at
  if (!at) it.run = runOrdinal.value
  if (meta) it.meta = meta
  if (kind === 'p5js') captureSketchFrame(it.id, code)
}

/** Frames waiting to hand their picture back: item id -> frame and its deadline. */
const capturing = new Map<string, { frame: HTMLIFrameElement; timer: number }>()

function endCapture(id: string) {
  const c = capturing.get(id)
  if (!c) return
  capturing.delete(id)
  window.clearTimeout(c.timer)
  c.frame.remove()
}

/**
 * One still picture of the sketch. A frame is built off-screen, given a moment
 * to draw, and taken down again — what it draws never appears anywhere. Nothing
 * depends on it: a sketch that draws nothing readable simply leaves the card
 * with the runtime's name on it.
 */
function captureSketchFrame(itemId: string, code: string) {
  const html = p5jsFrame(code, itemId)
  if (!html) return
  const frame = document.createElement('iframe')
  frame.setAttribute('sandbox', 'allow-scripts')
  frame.setAttribute('aria-hidden', 'true')
  frame.setAttribute('tabindex', '-1')
  frame.style.cssText =
    'position:fixed;left:-10000px;top:0;width:520px;height:520px;border:0;opacity:0;pointer-events:none'
  // The frame is torn down whether or not it ever answers.
  const timer = window.setTimeout(() => endCapture(itemId), 9000)
  capturing.set(itemId, { frame, timer })
  frame.srcdoc = html
  document.body.appendChild(frame)
}

/**
 * The picture the card actually keeps: 240 px wide, JPEG. The frame hands up a
 * full-size PNG, which is far too heavy for the board's session storage — the
 * whole board would stop surviving a reload to carry one screenshot.
 */
function shrinkFrame(png: string): Promise<{ url: string; h: number; flat: boolean }> {
  const nothing = { url: '', h: 0, flat: true }
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => {
      const w = 240
      const h = Math.max(1, Math.round((img.naturalHeight / img.naturalWidth) * w))
      const cv = document.createElement('canvas')
      cv.width = w
      cv.height = h
      const ctx = cv.getContext('2d')
      if (!ctx) return resolve(nothing)
      ctx.drawImage(img, 0, 0, w, h)
      resolve({ url: cv.toDataURL('image/jpeg', 0.72), h, flat: isFlat(ctx, w, h) })
    }
    img.onerror = () => resolve(nothing)
    img.src = png
  })
}

/**
 * One colour and nothing else — the canvas of a sketch that has not started
 * drawing yet (p5 comes from a CDN, so the first moments are usually blank).
 * Told apart from a real picture by pixels, not by file size: a sketch may
 * legitimately draw on black, and a blank canvas may be any colour at all.
 */
function isFlat(ctx: CanvasRenderingContext2D, w: number, h: number): boolean {
  let d: Uint8ClampedArray
  try {
    d = ctx.getImageData(0, 0, w, h).data
  } catch {
    return false
  }
  const lo = [255, 255, 255]
  const hi = [0, 0, 0]
  for (let i = 0; i < d.length; i += 16) {
    for (let c = 0; c < 3; c++) {
      const v = d[i + c]!
      if (v < lo[c]!) lo[c] = v
      if (v > hi[c]!) hi[c] = v
    }
  }
  return hi[0]! - lo[0]! < 12 && hi[1]! - lo[1]! < 12 && hi[2]! - lo[2]! < 12
}

async function onSketchFrame(e: MessageEvent) {
  const d = e.data as { kind?: string; id?: string; png?: string } | null
  if (!d || d.kind !== SKETCH_FRAME_MESSAGE || typeof d.id !== 'string') return
  // The frame runs sandboxed, so its origin is the string 'null' and cannot be
  // checked. What can be checked is that this page asked for exactly this
  // picture, and that what came back is a PNG data url — which is inert.
  if (!capturing.has(d.id)) return
  const png = typeof d.png === 'string' ? d.png : ''
  if (!png.startsWith('data:image/png;base64,')) return
  const small = await shrinkFrame(png)
  // Nothing on it yet: keep the frame alive and wait for a later moment. An
  // empty square on the card is worse than the runtime's name.
  if (!small.url || small.flat) return
  endCapture(d.id)
  const it = items.value.find((i) => i.id === d.id)
  if (!it) return
  it.thumb = small.url
  it.h = small.h
}

onMounted(() => {
  window.addEventListener('message', onSketchFrame)
  window.addEventListener('pointerdown', clearDragMoved, true)
})
onBeforeUnmount(() => {
  window.removeEventListener('message', onSketchFrame)
  window.removeEventListener('pointerdown', onAddAway, true)
  window.removeEventListener('keydown', onAddKey)
  window.removeEventListener('pointerdown', clearDragMoved, true)
  Array.from(capturing.keys()).forEach(endCapture)
})

/** The three ways material reaches this surface, drawn as Material Symbols. */
const D_TEXT =
  'm40-200 210-560h100l210 560h-96l-51-143H187l-51 143H40Zm176-224h168l-82-232h-4l-82 232Zm504 104v-120H600v-80h120v-120h80v120h120v80H800v120h-80Z'
const D_IMAGE =
  'M200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h320v80H200v560h560v-320h80v320q0 33-23.5 56.5T760-120H200Zm40-160h480L570-480 450-320l-90-120-120 160Zm440-320v-80h-80v-80h80v-80h80v80h80v80h-80v80h-80Z'
const D_SKETCH =
  'M200-200h57l391-391-57-57-391 391v57Zm-80 80v-170l528-527q12-11 26.5-17t30.5-6q16 0 31 6t26 18l55 56q12 11 17.5 26t5.5 30q0 16-5.5 30.5T817-647L290-120H120Zm640-584-56-56 56 56Zm-141 85-28-29 57 57-29-28Z'
// The document way (UCD-124): one PDF sign of its own — the text icon
// doubled would read as "A+" again. Material Symbols picture_as_pdf.
const D_PDF =
  'M720-360v-80h80q17 0 28.5 11.5T840-400q0 17-11.5 28.5T800-360h-80Zm-240-40h60q33 0 56.5-23.5T620-480v-80q0-33-23.5-56.5T540-640h-120v240h60v-40Zm0-100h60v80h-60v-80Zm-260-60h40v-60h60v160h40v-200h-60q-17 0-28.5 11.5T220-600v100q0 17 11.5 28.5t28.5 11.5ZM240-80q-33 0-56.5-23.5T160-160v-640q0-33 23.5-56.5T240-880h320l240 240v480q0 33-23.5 56.5T720-80H240Zm280-520v-200H240v640h480v-440H520ZM240-800v200-200 640-640Z'

/**
 * The plus: a free fixture in SCREEN space, like the perspective glyph, and
 * dragged by the same `startPointDrag`. Where it stands is where the material
 * lands — that is the whole reason it left the node box.
 */
const addEl = ref<HTMLElement | null>(null)
const perspEl = ref<HTMLElement | null>(null)
const loraEl = ref<HTMLElement | null>(null)
const add = reactive({ x: 28, y: 200 })
/** The LoRA sign, the third free fixture (screen space, like the other two). */
const loraFix = reactive({ x: 28, y: 300 })
const addOpen = ref(false)
/** Set when the sketch overlay is opened from the plus: its image lands as the plus's material does. */
let sketchFromPlus = false

/**
 * Where the working surface begins: under the map band. The band is painted
 * OVER the canvas, so this is the line above which nothing the plus opens can
 * be seen. Measured, because the band's height follows the viewport.
 */
const surfaceTop = ref(0)

/** Once a fixture has been moved by hand, its place is the hand's, not ours. */
let fixturesMoved = false
/**
 * The view's first framing (`frameBelowMap`) lays the signs once more, and the
 * prompt box of a fresh surface for the first time: the box lies in world
 * coordinates, and those hold only once the view has come to rest. A later
 * framing, by "1:1", does neither.
 */
let framed = false

/**
 * The prompt box a fresh surface starts with keeps to its resting place with
 * the signs as long as it lies where it was laid, as large as it was laid,
 * and the view has neither moved nor zoomed since (`laid` holds all of that).
 * Whatever a hand does to the box or to the view ends it, and so does its
 * removal.
 */
let restCard: { id: string; laid: string | null } | null = null

/**
 * The plus rests on the left of the working surface, just under the band —
 * the corner material comes in at. Measured on the same frame as the view
 * offset, and retried while the band is still without height.
 */
function measureSurface(): boolean {
  const m = mapEl.value
  const c = canvasEl.value
  if (!m || !c || m.clientHeight <= 0) return false
  surfaceTop.value = Math.round(m.getBoundingClientRect().bottom - c.getBoundingClientRect().top)
  return true
}

/**
 * The jitter the three free fixtures are laid out with. Drawn once, when the
 * view is built, and read on every measurement after that: the three keep the
 * place they were given while the window is resized, instead of hopping. Every
 * page draws a new one — the three signs lie loosely, never twice in quite the
 * same spot.
 */
const drift = {
  addX: Math.random(),
  addY: Math.random(),
  glyphX: Math.random(),
  glyphY: Math.random(),
  loraX: Math.random(),
  loraY: Math.random(),
}

/**
 * Where the three free fixtures rest while nobody has moved them, and the
 * prompt box of a fresh surface with them: under the left end of the band,
 * the signs as a triangle with the plus on top, the LoRA sign lower left of it
 * and the perspective sign lower right, the prompt box under the three. The
 * places are fractions of the width and height of the create box
 * (`restingPlaces`), so the arrangement holds at every viewport, only scaled;
 * `flowRestLayout.spec.ts` shows for every window width that none of the four
 * comes near another.
 *
 * Each sign is jogged a little by the draw above: loose, never twice in quite
 * the same spot, but never far from where it belongs. The test counts the jog
 * in.
 */
function placeFixtures() {
  const m = mapEl.value
  const c = canvasEl.value
  if (!m || !c || !cw.value || !ch.value || !measureSurface()) return
  const mr = m.getBoundingClientRect()
  const cr = c.getBoundingClientRect()
  const s = addEl.value?.offsetWidth || 76
  const g = perspEl.value?.offsetWidth || 56
  const n = loraEl.value?.offsetWidth || 56
  const node = rect(RMAP.create)
  const rest = restingPlaces({
    left: mr.left - cr.left + node.left,
    bottom: mr.top - cr.top + node.top + node.height,
    width: node.width,
    height: node.height,
  })
  const clampX = (v: number, w: number) => Math.round(Math.min(Math.max(v, 8), cr.width - w - 8))
  const clampY = (v: number, h: number) =>
    Math.round(Math.min(Math.max(v, surfaceTop.value + 8), cr.height - h - 8))
  const jog = (d: number, u: number) => (d - 0.5) * 2 * JOG * u
  add.x = clampX(rest.plus.x - s / 2 + jog(drift.addX, s), s)
  add.y = clampY(rest.plus.y - s / 2 + jog(drift.addY, s), s)
  glyph.x = clampX(rest.perspective.x - g / 2 + jog(drift.glyphX, g), g)
  glyph.y = clampY(rest.perspective.y - g / 2 + jog(drift.glyphY, g), g)
  loraFix.x = clampX(rest.lora.x - n / 2 + jog(drift.loraX, n), n)
  loraFix.y = clampY(rest.lora.y - n / 2 + jog(drift.loraY, n), n)
  if (framed) layRestCard(rest.promptBox)
}

/**
 * The prompt box of a fresh surface onto its resting place (`restCard`): the
 * place is its upper left corner in the view, its width and the height of its
 * text field, and the card is laid in world coordinates.
 */
function layRestCard(at: { x: number; y: number; w: number; h: number }) {
  if (!restCard) return
  const id = restCard.id
  const it = items.value.find((i) => i.id === id)
  const state = () => (it ? [it.x, it.y, it.w, it.h, pan.x, pan.y, zoom.value].join() : '')
  if (!it || (restCard.laid !== null && restCard.laid !== state())) {
    restCard = null
    return
  }
  it.x = Math.round((at.x - pan.x) / zoom.value)
  it.y = Math.round((at.y - pan.y) / zoom.value)
  it.w = Math.round(at.w / zoom.value)
  it.h = Math.round(at.h / zoom.value)
  restCard.laid = state()
}

// The stage measures itself into cw/ch, so this is also what a resize runs
// through. The surface line is taken every time — the landing point and the
// arc read it — while the fixtures themselves are only re-homed as long as no
// hand has moved them.
function reHome() {
  if (fixturesMoved) {
    measureSurface()
    return
  }
  placeFixtures()
}
watch([cw, ch], reHome, { immediate: true })

// The band's own width is capped, so a wider window leaves cw/ch untouched
// while the band — centred in the view — slides sideways out from under the
// fixtures. The canvas does change with the window, so it carries the re-home.
let surfaceRO: ResizeObserver | null = null
onMounted(() => {
  // The register and the presets' metadata, so a restored tile and a
  // perspective that brings an adapter can name its model before the chooser
  // was ever opened.
  void loraStore.load()
  if (configStore.availableConfigs.length === 0) void configStore.loadConfigs()
  if (!canvasEl.value) return
  surfaceRO = new ResizeObserver(reHome)
  surfaceRO.observe(canvasEl.value)
})
onBeforeUnmount(() => surfaceRO?.disconnect())

/**
 * The landing point of what the plus brings in (`landFromPlus`), in world
 * coordinates: just under the plus,
 * and pulled in from the edges by half a card so it arrives whole on the
 * surface — the plus rests in the head row, and a card placed straight at it
 * would hang behind the band or out of the view. Half a card on screen grows
 * with the zoom, which is why the world size is scaled here.
 */
function addLandPoint(): { x: number; y: number } | null {
  const b = addEl.value?.getBoundingClientRect()
  const el = canvasEl.value
  if (!b || !el) return null
  const cr = el.getBoundingClientRect()
  const hw = 130 * zoom.value
  const hh = 80 * zoom.value
  const inset = (v: number, lo: number, hi: number) => (hi > lo ? Math.min(Math.max(v, lo), hi) : v)
  const sx = inset(b.left + b.width / 2 - cr.left, hw + 12, el.clientWidth - hw - 12)
  // Under the sign, not on it: a card whose middle sat where the plus stands
  // would bury it, and the next click would land on the card instead.
  const sy = inset(
    b.bottom - cr.top + 24 + hh,
    surfaceTop.value + hh + 12,
    el.clientHeight - footerClear() - hh - 12
  )
  return dropPoint({ clientX: cr.left + sx, clientY: cr.top + sy })
}

/**
 * FlowCard's bar (18 px) and its frame (1 px above and below): what a card
 * stands taller than its `h`, and the step by which material brought onto a
 * full surface is cascaded, so that each card's bar stays readable under the
 * next.
 */
const CARD_BAR = 20

/**
 * Where a card the plus brings in lands: on the free place nearest to the
 * landing point (`findFreeSpot` with `near`), anywhere on the visible surface
 * between the band and the footer. Free means clear of every card, tile, sign
 * and control, and of the ring as the circle it is drawn as: material lying in
 * it would change what the next run reads. Only where nothing on that surface
 * is free does the card lie on the landing point itself, shifted down and to
 * the right past the cards already lying there, as far as the surface and the
 * ring allow; past that it lies where it covers the least. A card counts
 * there twice, from the board and as drawn, a sign or control once, so a new
 * card lies over a sign sooner than over a card. A reach of two card widths
 * found nothing free on an iPad in landscape and laid the first card over the
 * prompt box.
 * The cards count as the board holds them and, once drawn, as they stand: an
 * image is as tall as its picture.
 */
// `BoardItem`, not `AsmItem`: what this needs is a place and a size, and a
// scene strip card is placed by it too.
function landFromPlus(it: BoardItem) {
  const p = addLandPoint()
  const el = canvasEl.value
  if (!p || !el) return
  const z = zoom.value
  const cr = el.getBoundingClientRect()
  const occupied: (Rect | Disc)[] = [{ x: zone.x, y: zone.y, r: zone.r }]
  for (const o of items.value) if (o !== it) occupied.push({ x: o.x, y: o.y, w: o.w, h: o.h + CARD_BAR })
  // Strips too, drawn or not: the re-read after a duplicate upload lands
  // several in one go, before any of them stands in the DOM, and each would
  // take the place of the one before.
  for (const o of sceneStrips.value) if (o !== it) occupied.push({ x: o.x, y: o.y, w: o.w, h: o.h + CARD_BAR })
  const drawn = (el.parentElement ?? el).querySelectorAll<HTMLElement>(
    '.world > .asm-item, .world > .pb, .addg, .persp, .lorag, .view-tools, .fixture-gear'
  )
  for (const n of drawn) {
    const b = n.getBoundingClientRect()
    if (!b.width || !b.height) continue
    occupied.push({
      x: (b.left - cr.left - pan.x) / z,
      y: (b.top - cr.top - pan.y) / z,
      w: b.width / z,
      h: b.height / z,
    })
  }
  const top = surfaceTop.value
  const view = {
    x: -pan.x / z,
    y: (top - pan.y) / z,
    w: el.clientWidth / z,
    h: (el.clientHeight - footerClear() - top) / z,
  }
  const h = it.h + CARD_BAR
  const gap = 16
  const s = findFreeSpot(view, occupied, it.w, h, {
    gap,
    step: 8,
    near: { x: p.x - it.w / 2, y: p.y - h / 2 },
    cascade: CARD_BAR,
  })
  it.x = Math.round(s.x)
  it.y = Math.round(s.y)
}

const addOptions = computed(() => {
  const el = canvasEl.value
  // Toward the middle of the free SURFACE, not of the whole view: the band at
  // the top is drawn over the canvas, so an arc that opened into it would be
  // covered by the boxes. At the very center any direction is as good as
  // another, and atan2(0, 0) settles on "to the right".
  const h = el ? el.clientHeight : 0
  const half = (addEl.value?.offsetWidth ?? 56) / 2
  // From the head row the arc opens straight down onto the free surface: aiming
  // at its middle would swing the upper option sideways into the perspective
  // sign standing right beside the plus. Anywhere else it turns toward the
  // middle of the surface, so it never opens off an edge.
  const a0 =
    add.y + half < surfaceTop.value
      ? Math.PI / 2
      : Math.atan2(
          surfaceTop.value + (h - surfaceTop.value) / 2 - (add.y + half),
          (el ? el.clientWidth / 2 : 0) - (add.x + half)
        )
  const three = [
    { id: 'text', d: D_TEXT, label: t('x2xFlow.bringText'), title: t('x2xFlow.addText'), run: bringText },
    { id: 'image', d: D_IMAGE, label: t('x2xFlow.bringImage'), title: t('x2xFlow.addImage'), run: bringImage },
    { id: 'sketch', d: D_SKETCH, label: t('x2xFlow.bringSketch'), title: t('x2xFlow.addSketch'), run: bringSketch },
    { id: 'document', d: D_PDF, label: t('x2xFlow.bringDocument'), title: t('x2xFlow.addDocument'), run: bringDocument },
  ]
  // 0.68 rad apart, not the half-circle a wider fan would draw: from the head
  // row the outer two have to come down clear of the boxes beside the plus,
  // and at this ring they still stand a good 60 px apart.
  return three.map((o, i) => {
    const a = a0 + (i - 1) * 0.68
    return { ...o, ux: Math.cos(a).toFixed(3), uy: Math.sin(a).toFixed(3) }
  })
})

/**
 * A click that ended a drag is not a click — the same guard as the glyph. A
 * keyboard press (`detail === 0`) never had a drag to end, and must not be
 * caught by a flag some earlier gesture left standing.
 */
function onAddClick(e: MouseEvent) {
  if (e.detail > 0 && dragMoved) return
  addOpen.value = !addOpen.value
}

function bringText() {
  addOpen.value = false
  const n = items.value.length
  landFromPlus(addText(60 + n * 18, 50 + n * 18))
}

function bringImage() {
  addOpen.value = false
  // A picked image lands as a text does: `placePicked` on the intake adapter.
  pickImage()
}

function bringSketch() {
  addOpen.value = false
  sketchFromPlus = true
  sketchOpen.value = true
}

function bringDocument() {
  addOpen.value = false
  // The document way carries its own input (accept=".pdf"); the image picker
  // no longer lists PDFs, so every pick here is a scene document.
  docFileEl.value?.click()
}

/** A document picked from the document way: every pick is a scene document. */
function onDocFilePick(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  const pdf = files.find((f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'))
  if (pdf) void intakeSceneDocument(pdf)
}
/**
 * A PDF the plus brings in goes to the scene pipeline (UCD-124). The canvas
 * session (deviceId) is the journal id: the document space hangs on it and
 * dies with it.
 *
 * The CARD STANDS ON THE BOARD FROM THE PICK ONWARDS, busy, the way a picture
 * does while it uploads: the analysis is a queued worker job and takes minutes,
 * and until 2026-09-28 those minutes had nothing on the surface at all: no card,
 * no mark, and a page-level `sceneBusy` flag written twice and read by nobody.
 * The card's own `uploading` is that state now, one per document, and it is gone.
 * What does not arrive takes its card with it again, and the voice says why.
 */
async function intakeSceneDocument(file: File) {
  const jid = deviceId
  if (!jid) return

  const pending = addSceneStrip(pendingSceneDoc(file), true)
  try {
    const outcome = await uploadSceneDocument(file, jid)
    if (outcome.status === 'rejected') {
      removeSceneStrip(pending.id)
      platformVoice.value?.speak(t(`resonaScene.rej.${outcome.reasonKey}`))
      return
    }
    if (outcome.status === 'duplicate') {
      removeSceneStrip(pending.id)
      platformVoice.value?.speak(t('resonaScene.duplicate'))
      await refreshSceneStrips()
      return
    }
    pending.job = { id: outcome.jobId, docId: outcome.docId }
    await followSceneStrip(pending)
  } catch (e) {
    removeSceneStrip(pending.id)
    console.error('[X2X] Scene document intake failed:', e)
    platformVoice.value?.speak(t('resonaScene.unavailable'))
  }
}

/**
 * The card an analysis stands behind: it names the file that was picked and
 * carries no capsules, so the strip shows its head alone. Not a document — the
 * session's document space knows nothing under this name until the worker is
 * through, which is why it has no docId and is never deduped against one.
 */
function pendingSceneDoc(file: File): SceneDocument {
  return { docId: '', title: file.name, capsules: [], flagged: 0, discarded: 0, meta: {} }
}

/**
 * Follow the card's analysis job to its end: the card settles into the
 * document, or goes, and the voice says the analysis did not complete.
 * Polling is the jobs route's own contract, and it has no deadline: the card
 * once waited ten minutes and then went while the worker went on (2026-09-28).
 * A poll that does not come through is asked again; a job the server no
 * longer knows ends the
 * wait (`gone`). Leaving the page, closing the card, or clearing the board
 * ends the following and leaves the job running.
 */
async function followSceneStrip(strip: BoardSceneStrip) {
  const job = strip.job
  if (!job) return
  const stopped = () =>
    sceneDisposed || strip.job !== job || !sceneStrips.value.some(s => s.id === strip.id)
  for (;;) {
    if (stopped()) return
    try {
      const state = await fetchSceneJob(job.id)
      if (stopped()) return
      strip.jobState = state
      if (state.state === 'done') {
        const doc = await fetchSceneDocument(deviceId!, job.docId)
        if (stopped()) return
        if (doc) settleSceneStrip(strip, doc)
        else failSceneStrip(strip)
        return
      }
      if (state.state === 'error' || state.state === 'cancelled' || state.state === 'gone') {
        failSceneStrip(strip)
        return
      }
    } catch {
      // Asked again below.
    }
    await new Promise(r => setTimeout(r, 2500))
  }
}

/** The analysis ended without a document: the card goes, and the voice says so. */
function failSceneStrip(strip: BoardSceneStrip) {
  removeSceneStrip(strip.id)
  platformVoice.value?.speak(t('resonaScene.analysisFailed'))
}

/**
 * The line under a busy card's title: where its analysis stands. The upload
 * comes first, then the queue behind another document (the worker takes one
 * at a time), then the text recognition, then the units read and the
 * capsules kept; the pipeline stops at the capsule limit, which is why the
 * limit stands in the line.
 */
function sceneStatus(s: BoardSceneStrip): string {
  if (!s.uploading) return ''
  const j = s.jobState
  if (!j) return t('resonaScene.progressUpload')
  if (j.state === 'queued') return t('resonaScene.progressQueued')
  const p = j.progress
  if (!p) return t('resonaScene.progressReading')
  return t('resonaScene.progressUnits', {
    done: p.unitsDone,
    total: p.unitsTotal,
    capsules: p.capsules,
    max: p.capsulesMax,
  })
}

/** The follow loops end with the page (`followSceneStrip`); the jobs do not. */
let sceneDisposed = false
onBeforeUnmount(() => {
  sceneDisposed = true
})

/** A strip as the session copy keeps it (`t2i_scene_strips`). */
interface SavedSceneStrip {
  docId?: string
  title?: string
  job?: { id: string; docId: string }
  x: number
  y: number
  w: number
  h: number
}
/**
 * The strips the board held when the page was left, back where they stood:
 * an analysed document is read again from the session space, a running
 * analysis stands busy again and is followed on. A document the space no
 * longer holds (the session of another day) stays away. Until 2026-09-28 a
 * strip left the board with the page and came back only with a second
 * upload of the same file.
 */
async function restoreSceneStrips() {
  const jid = deviceId
  if (!jid) return
  let saved: SavedSceneStrip[] = []
  try {
    saved = JSON.parse(sessionStorage.getItem('t2i_scene_strips') || '[]')
  } catch {
    return
  }
  if (!Array.isArray(saved) || !saved.length) return
  // Read in parallel and stood up together, in the order they were kept: a
  // board built one strip at a time would be written to the session copy
  // half-built, and a page left in between would keep only that half.
  const docs = await Promise.all(
    saved.map(async (s) => {
      if (s.job?.id || !s.docId) return null
      try {
        return await fetchSceneDocument(jid, s.docId)
      } catch {
        return null
      }
    })
  )
  if (sceneDisposed) return
  const following: BoardSceneStrip[] = []
  saved.forEach((s, i) => {
    const place = { x: Number(s.x) || 60, y: Number(s.y) || 60, w: Number(s.w) || SCENE_STRIP_W, h: Number(s.h) || SCENE_STRIP_H }
    if (s.job?.id && s.job.docId) {
      const strip = standSceneStrip(
        { docId: '', title: String(s.title || ''), capsules: [], flagged: 0, discarded: 0, meta: {} },
        place
      )
      strip.uploading = true
      strip.job = { id: String(s.job.id), docId: String(s.job.docId) }
      following.push(strip)
    } else {
      const doc = docs[i]
      if (doc && !sceneStrips.value.some(o => o.doc.docId === doc.docId)) standSceneStrip(doc, place)
    }
  })
  for (const strip of following) void followSceneStrip(strip)
}
onMounted(() => {
  void restoreSceneStrips()
})
watch(
  sceneStrips,
  () => {
    const kept: SavedSceneStrip[] = sceneStrips.value.map(s => ({
      docId: s.doc.docId,
      title: s.doc.title,
      job: s.job,
      x: s.x,
      y: s.y,
      w: s.w,
      h: s.h,
    }))
    try {
      sessionStorage.setItem('t2i_scene_strips', JSON.stringify(kept))
    } catch {
      /* quota — the strips stay live, they just will not survive a reload */
    }
  },
  { deep: true }
)

/**
 * Stand a strip on the board, once per document: on the free place nearest the
 * plus, like every other card the plus brings in (`landFromPlus`). A document
 * already standing there keeps its card and its place and only takes the
 * re-read version of itself.
 */
function addSceneStrip(doc: SceneDocument, uploading = false): BoardSceneStrip {
  // A card still following this document's analysis counts as it too: it
  // settles here, and its following ends with its job (`followSceneStrip`).
  const known = doc.docId
    ? sceneStrips.value.find(s => s.doc.docId === doc.docId || s.job?.docId === doc.docId)
    : undefined
  if (known) {
    known.doc = doc
    known.uploading = uploading
    if (!uploading) {
      known.job = undefined
      known.jobState = undefined
    }
    return known
  }
  const live = standSceneStrip(doc, { x: 60, y: 60, w: SCENE_STRIP_W, h: SCENE_STRIP_H })
  live.uploading = uploading
  // After it is in the list and before it is drawn: the placement reads the
  // cards standing on the board, and this one is not one of them yet.
  landFromPlus(live)
  return live
}

/**
 * Put a strip into the board's list at a given place and hand back the card
 * as the list holds it: a write on the object it was built from triggers no
 * render, so the settled document and the end of `uploading` stayed unseen
 * and the card stayed busy.
 */
function standSceneStrip(
  doc: SceneDocument,
  place: { x: number; y: number; w: number; h: number }
): BoardSceneStrip {
  sceneSeq += 1
  const strip: BoardSceneStrip = { id: `scene-${sceneSeq}`, doc, ...place }
  sceneStrips.value = [...sceneStrips.value, strip]
  return sceneStrips.value[sceneStrips.value.length - 1]!
}

/**
 * The analysed document takes over the card its analysis stood behind — same
 * card, same place, now with its capsules and no longer busy.
 */
function settleSceneStrip(strip: BoardSceneStrip, doc: SceneDocument) {
  strip.doc = doc
  strip.uploading = false
  strip.job = undefined
  strip.jobState = undefined
}

/** Re-read every strip's document from the session space. */
async function refreshSceneStrips() {
  const jid = deviceId
  if (!jid) return
  try {
    const listed = await listSceneDocuments(jid)
    const docs = await Promise.all(listed.map(l => fetchSceneDocument(jid, l.docId)))
    for (const d of docs) if (d) addSceneStrip(d)
  } catch (e) {
    console.warn('[X2X] Scene document refresh failed (non-fatal):', e)
  }
}

/** Take a whole strip off the board. The document space keeps it. */
function removeSceneStrip(id: string) {
  sceneStrips.value = sceneStrips.value.filter(s => s.id !== id)
}

/**
 * A capsule's prompt goes into a new text card on the canvas — the flow's
 * own prompt instrument.
 */
function carryScenePrompt(prompt: string) {
  const n = items.value.length
  const it = addText(60 + n * 18, 50 + n * 18)
  it.text = prompt
  // Where a text from the plus lands (`bringText`): at a fixed place it lay
  // under whatever stood there, the strip it came from included.
  landFromPlus(it)
}


/**
 * Capture, not bubble: two dozen fixtures on this board stop `pointerdown`
 * before it reaches the window (cards, bubbles, the run panel, the zoom
 * controls). Listening on the way down is the only way a click on any of them
 * closes the arc instead of leaving it lying open over the board.
 */
function onAddAway(e: PointerEvent) {
  if ((e.target as HTMLElement | null)?.closest('.addg, .addopt')) return
  addOpen.value = false
}
/**
 * `dragMoved` guards the click at the END of a drag, so it stays set until the
 * next gesture begins. Cleared here, in capture, so that the next gesture
 * really is the next one: a fixture that was dragged used to keep swallowing
 * the first click on anything whose handler stops propagation (the x on a
 * perspective, for one).
 */
function clearDragMoved() {
  dragMoved = false
}
function onAddKey(e: KeyboardEvent) {
  if (e.key === 'Escape') addOpen.value = false
}
watch(addOpen, (open) => {
  if (open) {
    window.addEventListener('pointerdown', onAddAway, true)
    window.addEventListener('keydown', onAddKey)
  } else {
    window.removeEventListener('pointerdown', onAddAway, true)
    window.removeEventListener('keydown', onAddKey)
  }
})

/**
 * A sketch is an image like any other. SketchCanvas already uploads it and runs
 * the same VLM input check, so it hands back the server path the pipelines read.
 */
function onSketchUploaded(d: { image_id: string; image_path: string; preview_url: string }) {
  clearManualChoice()
  const it = addImage(d.preview_url, 110, 100)
  if (sketchFromPlus) landFromPlus(it)
  sketchFromPlus = false
  it.imageId = d.image_id
  it.path = d.image_path
  it.src = `/api/media/uploads/${d.image_id}`
  it.uploading = false
  sketchOpen.value = false
}

/**
 * A source lands BESIDE the ring, in a column to its left: evidence is there to
 * be read, not to be fed back in. One card per article — several perspectives
 * in one chain can hit the same one, and so can the next run. The column wraps
 * rather than running off the bottom of the world.
 */
function dropSource(source: NonNullable<AsmItem['source']>) {
  // Two perspectives can reach the same article under different terms. Both
  // searches happened, so both are shown; only the identical search twice is
  // one card.
  const same = (i: AsmItem) =>
    i.kind === 'source' && i.source?.term === source.term && i.source?.lang === source.lang
  if (items.value.some(same)) return
  // A column to the left of the ring, from its top down. Below it would be
  // clearer of the parked perspectives, but on the default board that is past
  // the lower edge of the screen, and evidence nobody can see is not evidence.
  // Counted per run, so a moved or resized ring never pushes a later card off
  // the world; clamped so the leftmost column stays reachable.
  const x = Math.max(20, zone.x - zone.r - 260 - Math.floor(sourceSlot / 4) * 220)
  const y = zone.y - zone.r + (sourceSlot % 4) * 110
  sourceSlot += 1
  addSource(source, x, y)
}

/** Where a drop landed, in world coordinates (the world is panned and zoomed). */
function dropPoint(e: { clientX: number; clientY: number }): { x: number; y: number } | null {
  const el = canvasEl.value
  if (!el) return null
  const r = el.getBoundingClientRect()
  return {
    x: (e.clientX - r.left - pan.x) / zoom.value,
    y: (e.clientY - r.top - pan.y) / zoom.value,
  }
}
/**
 * Two ways material reaches this surface from somewhere else, both settled once
 * the board and the zone are in place. They go INTO the zone: asking for a
 * session back, or handing a picture onward, is a deliberate gesture, and
 * material that landed dormant outside the ring would be a riddle.
 */
async function intakeFromElsewhere() {
  // 1. An image handed over by one of the "send onward" controls
  //    (lib/handOverImage.ts): read once and cleared at once, and only while
  //    fresh — localStorage outlives the browser, and anything old is a
  //    leftover nobody meant to see again.
  const handed = takeHandedImage()
  if (handed) void fallImage(handed.runId || '', handed.imageUrl, undefined, { x: zone.x, y: zone.y })

  // 2. A favourite restored by CLICK — the gallery sets the data and routes
  //    here (the drag path goes through material intake instead). The saved
  //    text arrives as material, which is what a text is on this surface. The
  //    store is emptied afterwards, as every other consumer does: left standing
  //    it would be restored again on the next visit, and picked up by any other
  //    page whose watcher runs on mount.
  const restore: any = favStore.pendingRestoreData
  if (!restore) return
  favStore.setRestoreData(null)
  const text: string =
    (typeof restore.input_text === 'string' && restore.input_text) ||
    (typeof restore.context_prompt === 'string' && restore.context_prompt) ||
    ''
  if (!text.trim()) return
  const it = addText(zone.x - 125, zone.y - 60)
  it.text = text
}

// --- Material intake: DnD dispatch, favorite restore, upload+safety ---------
// (shared composable; the zone law, fall dormancy and dropPoint stay local)
const { pickImage, onFilePick, onDrop, onArtifactDrag } = useMaterialIntake({
  fileInput: fileEl,
  adapter: {
    toWorldPoint: dropPoint,
    placePicked: landFromPlus,
    addText,
    addImage,
    addMedia,
    removeItem,
    placeArtifactImage: fallImage,
    placeArtifactMedia: fallMedia,
    placeArtifactCode: fallCode,
    artifactDragSource: () =>
      currentRunId.value && mediaUrl.value
        ? { runId: currentRunId.value, src: mediaUrl.value }
        : null,
    // A picture the user brings releases a held medium and model — but not a
    // chosen reading: the surface itself asks for material there, and following
    // that instruction must not throw the frame away.
    onUserImageIntake: () => {
      if (manualMedium.value !== 'text') clearManualChoice()
    },
    reportSafetyBlocked: (r: QuickSafetyResult) =>
      safetyStore.reportBlock(
        'vlm_input',
        r.errorMessage || t('safetyBlocked.inputImage'),
        [],
        r.vlmDescription,
        // Whether the check judged the picture or could not run at all.
        r.operational
      ),
    reportSafetyAnalysis: (d: string) => safetyStore.reportAnalysis(d, true),
  },
})

function onCanvasPointerDown(e: PointerEvent) {
  bubblesFor.value = null
  perspEdit.value = null
  loraEdit.value = null
  if (e.target === canvasEl.value) startPan(e)
}

// --- Screen-space drag for the perspective glyph ---
// The glyph is a picker, not material: it keeps its size and place while the
// world moves. The bubbles it spawns are material and live in the world.
let dragObj: { x: number; y: number } | null = null
let dragSize = 96
let dragX = 0
let dragY = 0
let dragMoved = false
let dragInset = 0

/** flow-stage.css owns the sizes; script reads them so there is one source. */
function readPx(token: string, fallback: number): number {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(token)
  const n = parseFloat(raw)
  return Number.isFinite(n) ? n : fallback
}
/** The fixed footer gallery covers the canvas' bottom edge on every page. */
function footerClear(): number {
  return readPx('--footer-collapsed-height', 36) + readPx('--flow-gutter', 18)
}

function onPointDragMove(e: PointerEvent) {
  if (!dragObj) return
  const dx = e.clientX - dragX
  const dy = e.clientY - dragY
  // Measured from where the gesture STARTED, not per frame: a slow drag moves
  // 2px at a time and would never count. A finger never lands still, so its
  // slop has to be wider than a mouse's — at 3px per frame nearly every tap on
  // a fixture read as a drag, and the click at the end of it was swallowed.
  if (
    Math.abs(e.clientX - dragStartX) > dragSlop ||
    Math.abs(e.clientY - dragStartY) > dragSlop
  ) {
    dragMoved = true
    fixturesMoved = true
  }
  const el = canvasEl.value
  const maxX = el ? Math.max(0, el.clientWidth - dragSize) : Number.MAX_SAFE_INTEGER
  const maxY = el ? Math.max(0, el.clientHeight - dragSize - dragInset) : Number.MAX_SAFE_INTEGER
  dragObj.x = Math.min(Math.max(0, dragObj.x + dx), maxX)
  dragObj.y = Math.min(Math.max(0, dragObj.y + dy), maxY)
  dragX = e.clientX
  dragY = e.clientY
}
function endPointDrag() {
  dragObj = null
  window.removeEventListener('pointermove', onPointDragMove)
  window.removeEventListener('pointerup', endPointDrag)
}
let dragStartX = 0
let dragStartY = 0
let dragSlop = 4
function startPointDrag(e: PointerEvent, obj: { x: number; y: number }) {
  dragObj = obj
  // The dragged fixtures are sized by responsive CSS clamps; measure, don't guess.
  dragSize = (e.currentTarget as HTMLElement | null)?.offsetWidth || 96
  dragX = e.clientX
  dragY = e.clientY
  dragStartX = e.clientX
  dragStartY = e.clientY
  dragSlop = e.pointerType === 'touch' ? 10 : 4
  dragMoved = false
  dragInset = footerClear() // read once; the move handler runs per frame
  window.addEventListener('pointermove', onPointDragMove)
  window.addEventListener('pointerup', endPointDrag)
}

// --- Perspectives: curated preset (bubble) + the free prompt (the written half) ---
interface BoardPerspective {
  id: string
  /** The style key a run is addressed with: a preset name, or `custom:<id>`. */
  configId: string
  configName: string
  context: string
  /**
   * The preset whose PICTURE this bubble wears, and whose pipeline it runs
   * through. For a preset that is the preset itself; a kept perspective keeps
   * wearing the picture of what it was written over. Absent on bubbles stored
   * before perspectives could be kept — the disc falls back to configId.
   */
  previewId?: string
  /** Set once this perspective is kept: the row it belongs to. */
  promptId?: number
  zoneSeq?: number
  x: number
  y: number
}

const kept = useKeptPerspectivesStore()

/**
 * A SAVED perspective wears a colour of the platform's palette and never a
 * picture: its `previewId` names the preset it was written over, so with
 * that picture it stood beside that preset indistinguishable.
 * Given ones have no row and keep their picture.
 */
function pbColor(b: BoardPerspective): string {
  return b.promptId == null ? '' : keptColor(b.promptId, kept.items)
}
const presetOverlayVisible = ref(false)
const glyph = reactive({ x: 28, y: 240 })
const bubbles = ref<BoardPerspective[]>([])
let bseq = 0

/** One deterministic world size for bubbles, immune to viewport clamps. */
const PB = 144

// --- LoRAs: a tile on the table, loaded with the image model of the next run ---
interface BoardLora {
  id: string
  /** The file a run names, as the register lists it. */
  file: string
  name: string
  /** The word the captions were written under; the run puts it in front of the prompt. */
  trigger: string
  /** The output configs whose workflow loads this adapter; the first is what the automatic picks. */
  baseConfigs: string[]
  /** Percent of the trained strength, 50–100 (LoRA Explorer's axis). */
  strength: number
  zoneSeq?: number
  x: number
  y: number
}
const loraStore = useLoraStore()
const configStore = useConfigSelectionStore()
const loraTiles = ref<BoardLora[]>([])
let lseq = 0
const loraOverlayVisible = ref(false)
/** The strength axis: a notch every 10 % from half to the trained strength. */
const LORA_MARKS: SliderMark[] = [50, 60, 70, 80, 90, 100].map((v) => ({
  value: `${v}%`,
  pct: ((v - 50) / 50) * 100,
}))
/**
 * The strength a laid tile starts at, as a percent of the trained strength.
 * Not the full 100: at the trained strength a style adapter pulls the picture
 * all the way to its training material, and at some seeds that is
 * posterisation and blur (observed on solarization runs). The usual
 * practice of ComfyUI workflows is 0.7 to 0.8, and this platform follows it.
 * The perspectives that bring an adapter keep the strength their config sets.
 */
const LORA_DEFAULT_PCT = 80

// World-space drag for the bubbles — the same math as the material items.
let bubbleDrag: { x: number; y: number } | null = null
let bdStartX = 0
let bdStartY = 0
let bdPointX = 0
let bdPointY = 0
/**
 * A disc has one box, and its click opens it; a press on the disc drags it,
 * however long the press lasts. The click that ended a drag is not a click,
 * the same guard the glyphs at the edge use. The marks at its rim (the chain
 * number, the net, the "?", the strength) take no press of their own: until
 * 2026-09-26 each stopped it, and the disc could not be picked up by them.
 *
 * From 2026-09-23 to 2026-09-26 the discs also carried the platform's
 * InfoCard, after a pointer had rested on them for 350 ms and on a long press,
 * and the card coming up ended the drag. The rest was counted from the moment
 * the pointer entered the disc, and a press did not call it off, so a drag
 * lasting longer than that stopped under the hand. The card said what the box
 * says, and a pointer coming back onto a disc whose box was open brought the
 * card up beside the box, so a hold on an icon showed the info instead of
 * letting the icon be dragged. The name stands on the disc; the text of a
 * perspective, and a LoRA's strength, trigger and models, stand in its box.
 */
function onFixtureClick(e: MouseEvent, open: () => void) {
  if (e.detail > 0 && dragMoved) return
  open()
}

function onBubbleDragMove(e: PointerEvent) {
  if (!bubbleDrag) return
  if (Math.abs(e.clientX - bdPointX) > bdSlop || Math.abs(e.clientY - bdPointY) > bdSlop)
    dragMoved = true
  bubbleDrag.x = bdStartX + (e.clientX - bdPointX) / zoom.value
  bubbleDrag.y = bdStartY + (e.clientY - bdPointY) / zoom.value
}
function endBubbleDrag() {
  bubbleDrag = null
  window.removeEventListener('pointermove', onBubbleDragMove)
  window.removeEventListener('pointerup', endBubbleDrag)
  window.removeEventListener('pointercancel', endBubbleDrag)
  window.removeEventListener('contextmenu', endBubbleDrag)
}
// A drag that is still running when the page goes (the top menu is reachable at
// any time) would leave its four listeners on the window, writing into a disc
// nobody shows any more.
onBeforeUnmount(endBubbleDrag)
/**
 * A finger never lands still: at a flat 3 px nearly every tap on a disc read as
 * a drag, and since 2026-09-23 the click at the end of it is the ONLY way into
 * the box. The same two numbers the fixtures at the edge use.
 */
let bdSlop = 4

function startBubbleDrag(e: PointerEvent, b: { x: number; y: number }) {
  // The left button of one primary pointer, as on a card (FlowCard): a right
  // press or a second pointer does not pick the disc up, and leaves the drag
  // already running as it is.
  if (e.button !== 0 || !e.isPrimary) return
  bdSlop = e.pointerType === 'touch' ? 10 : 4
  bubbleDrag = b
  bdStartX = b.x
  bdStartY = b.y
  bdPointX = e.clientX
  bdPointY = e.clientY
  dragMoved = false
  window.addEventListener('pointermove', onBubbleDragMove)
  window.addEventListener('pointerup', endBubbleDrag)
  window.addEventListener('pointercancel', endBubbleDrag)
  window.addEventListener('contextmenu', endBubbleDrag)
}

const zoneBubbleIds = computed<Set<string>>(() => {
  const ids = new Set<string>()
  for (const b of bubbles.value) {
    const dx = b.x + PB / 2 - zone.x
    const dy = b.y + PB / 2 - zone.y
    if (dx * dx + dy * dy <= zone.r * zone.r) ids.add(b.id)
  }
  return ids
})

// Registration: a bubble is stamped when it enters the zone — by drag, by a
// moved or resized zone, or by restore — and unstamped when it leaves. The
// stamps are the chain order.
let zseq = 0
watch(
  () => Array.from(zoneBubbleIds.value).sort().join(','),
  () => {
    for (const b of bubbles.value) {
      if (zoneBubbleIds.value.has(b.id)) {
        if (!b.zoneSeq) b.zoneSeq = ++zseq
      } else if (b.zoneSeq) {
        b.zoneSeq = undefined
      }
    }
  },
  { immediate: true }
)

/**
 * In the zone: applied. Outside: not. Several bubbles form a CHAIN — the
 * interception runs once per bubble, in the order they entered the zone,
 * each pass transforming the previous pass's output.
 */
const zoneChain = computed<BoardPerspective[]>(() =>
  bubbles.value
    .filter((b) => zoneBubbleIds.value.has(b.id) && b.zoneSeq)
    .sort((a, b) => (a.zoneSeq ?? 0) - (b.zoneSeq ?? 0))
)
const activePreset = computed<BoardPerspective | null>(() => zoneChain.value[0] ?? null)
/** Context of the LAST applied pass — what the generation run records. */
const activeContext = computed(
  () => zoneChain.value[zoneChain.value.length - 1]?.context ?? ''
)
/** All chain names, for the artifact's back side. */
const chainLabel = computed(() =>
  zoneChain.value.map((b) => b.configName).filter(Boolean).join(' → ')
)
function chainIndex(b: BoardPerspective): number {
  return zoneChain.value.findIndex((x) => x.id === b.id) + 1
}

const zoneLoraIds = computed<Set<string>>(() => {
  const ids = new Set<string>()
  for (const l of loraTiles.value) {
    const dx = l.x + PB / 2 - zone.x
    const dy = l.y + PB / 2 - zone.y
    if (dx * dx + dy * dy <= zone.r * zone.r) ids.add(l.id)
  }
  return ids
})
// Stamped on entry like the perspectives: the first LoRA in the zone is the
// one whose model the automatic picks.
watch(
  () => Array.from(zoneLoraIds.value).sort().join(','),
  () => {
    for (const l of loraTiles.value) {
      if (zoneLoraIds.value.has(l.id)) {
        if (!l.zoneSeq) l.zoneSeq = ++zseq
      } else if (l.zoneSeq) {
        l.zoneSeq = undefined
      }
    }
  },
  { immediate: true }
)
/** The LoRAs in the zone, in the order they entered it. */
const zoneLoras = computed<BoardLora[]>(() =>
  loraTiles.value
    .filter((l) => zoneLoraIds.value.has(l.id) && l.zoneSeq)
    .sort((a, b) => (a.zoneSeq ?? 0) - (b.zoneSeq ?? 0))
)
// The register's word whenever it is read again: a tile laid under an older
// listing, or restored from the last session, takes the row's name, trigger
// and models over. A tile whose row is gone keeps what it has and lies there
// unused (loraCarried).
watch(
  () => loraStore.items,
  (rows) => {
    for (const l of loraTiles.value) {
      const row = rows.find((r) => r.file === l.file)
      if (!row) continue
      l.name = row.name
      l.trigger = row.trigger
      l.baseConfigs = [...row.base_configs]
    }
  }
)
/**
 * The files a perspective brings with it (`meta.loras` of the preset it wears
 * — a kept perspective inherits them from the preset it was written over, as
 * the resolver does on the server).
 */
function bubbleLoraFiles(b: BoardPerspective): string[] {
  const id = b.previewId || b.configId
  const cfg = configStore.availableConfigs.find((c) => c.id === id)
  return (cfg?.loras || []).map((x) => x.name)
}
/**
 * The model the automatic picks while a LoRA lies in the zone: the model that
 * carries the first LoRA there, and failing a tile, the one that carries what
 * the first perspective in the chain brings with it. Which model carries an
 * adapter is the register's word, never the surface's.
 */
const loraBase = computed<string | null>(() => {
  for (const l of zoneLoras.value) {
    const cfg = loraRouteBase(l.baseConfigs)
    if (cfg) return cfg
  }
  for (const b of zoneChain.value) {
    for (const file of bubbleLoraFiles(b)) {
      const cfg = loraRouteBase(loraStore.byFile(file)?.base_configs || [])
      if (cfg) return cfg
    }
  }
  return null
})
/**
 * The first of an adapter's models the automatic can route to: one of the
 * image models the pick offers, and one that is answering. A row may list a
 * model the route never picks for words alone (the picture-to-picture
 * variant), or one that is not installed here.
 */
function loraRouteBase(cfgs: string[]): string | null {
  const offered = configsByMedium.image.map((c) => c.id)
  return cfgs.find((c) => offered.includes(c) && !modelMissing(c)) ?? null
}

function onGlyphClick(e: MouseEvent) {
  if (e.detail > 0 && dragMoved) return
  presetOverlayVisible.value = true
}
function onPresetSelected(payload: {
  configId: string
  context: string
  configName: string
  previewId?: string
  promptId?: number
}) {
  // The pick only lays the perspective on the table, next to the zone.
  // Placing it into the Aktivkreis — activating it — is the user's gesture,
  // never this handler's. Nothing that already lies somewhere is moved.
  let target = bubbles.value.find((b) => b.configId === payload.configId)
  if (target) {
    if (payload.context.trim()) target.context = payload.context
    target.configName = payload.configName
    target.previewId = payload.previewId || payload.configId
    target.promptId = payload.promptId
  } else {
    bseq += 1
    // The lower arc, left to right. Straight up is where the flow band stands:
    // a perspective laid there lies UNDER the boxes and cannot be reached, so
    // nothing is laid there.
    const a = Math.PI * (0.12 + (bubbles.value.length % 9) * 0.095)
    target = {
      id: 'p' + bseq,
      configId: payload.configId,
      configName: payload.configName,
      context: payload.context,
      previewId: payload.previewId || payload.configId,
      promptId: payload.promptId,
      x: zone.x + Math.cos(a) * (zone.r + PB) - PB / 2,
      y: zone.y + Math.sin(a) * (zone.r + PB) - PB / 2,
    }
    bubbles.value.push(target)
  }
  presetOverlayVisible.value = false
  // An empty perspective is an invitation to write — open the editor at once.
  if (!target.context.trim()) {
    const tb = target
    void nextTick().then(() => openPerspEdit(tb))
  }
}
function removeBubble(id: string) {
  if (dragMoved) return
  bubbles.value = bubbles.value.filter((b) => b.id !== id)
}

function onLoraGlyphClick(e: MouseEvent) {
  if (e.detail > 0 && dragMoved) return
  loraOverlayVisible.value = true
}
/**
 * The pick lays the LoRA on the table beside the zone, on the same lower arc
 * the perspectives land on; placing it into the zone is the hand's gesture.
 * One that already lies somewhere is not moved.
 */
function onLoraPicked(l: LoraAdapter) {
  if (loraTiles.value.some((t) => t.file === l.file)) return
  lseq += 1
  const a = Math.PI * (0.12 + ((bubbles.value.length + loraTiles.value.length) % 9) * 0.095)
  loraTiles.value.push({
    id: 'l' + lseq,
    file: l.file,
    name: l.name,
    trigger: l.trigger,
    baseConfigs: [...l.base_configs],
    strength: LORA_DEFAULT_PCT,
    x: zone.x + Math.cos(a) * (zone.r + PB) - PB / 2,
    y: zone.y + Math.sin(a) * (zone.r + PB) - PB / 2,
  })
}
function removeLoraTile(id: string) {
  if (dragMoved) return
  loraTiles.value = loraTiles.value.filter((l) => l.id !== id)
  if (loraEdit.value?.id === id) loraEdit.value = null
}

// ---------- Clearing the canvas (behind the gear, asked over the surface) ----------
const clearAsk = ref(false)
/**
 * Everything lying on the canvas goes: the material, the perspectives, the
 * LoRA tiles, and with them the last transformation, which described that
 * material. The three stations stay, and so does the last result in the
 * output station: it is the product of the work, not the work's material.
 * The session copies follow through their watchers.
 */
function clearCanvas() {
  sceneStrips.value = []
  setItems([])
  bubbles.value = []
  loraTiles.value = []
  perspEdit.value = null
  loraEdit.value = null
  interceptionResult.value = ''
  runResume.value = null
  clearAsk.value = false
}

function setLoraStrength(l: BoardLora, v: number) {
  l.strength = Math.round(Math.min(100, Math.max(50, v)))
}
/**
 * What this surface calls one of an adapter's models, and nothing where the
 * surface does not offer that config. The register derives EVERY config that
 * runs the adapter's base — the picture-to-picture variant of a model, and the
 * one that loads the same weights through the other backend — and neither is
 * on the pick here, so naming them would put a backend key on the screen.
 */
function loraModelName(id: string): string {
  for (const list of Object.values(configsByMedium)) {
    const hit = list.find((c) => c.id === id)
    if (hit) return hit.label.replace('\n', ' ')
  }
  return ''
}
function loraModelLabel(l: BoardLora): string {
  const names: string[] = []
  for (const c of l.baseConfigs) {
    const name = loraModelName(c)
    if (name && !names.includes(name)) names.push(name)
  }
  return names.join(' · ')
}
/** The name of a perspective's adapter as the register calls it, or its file. */
function bubbleLoraTitle(b: BoardPerspective): string {
  return bubbleLoraFiles(b)
    .map((f) => loraStore.byFile(f)?.name || f)
    .join(' · ')
}

/** The written half opens at its bubble and stays inside the canvas — never under the footer. */
const perspEdit = ref<{ id: string; x: number; y: number; w: number } | null>(null)
const perspEditTa = ref<HTMLTextAreaElement | null>(null)
const perspEditBubble = computed(
  () => bubbles.value.find((b) => b.id === perspEdit.value?.id) ?? null
)
/** The editor writes into its bubble — the text belongs to the bubble, not to a global. */
const perspEditText = computed({
  get: () => perspEditBubble.value?.context ?? '',
  set: (v: string) => {
    const b = perspEditBubble.value
    if (b) b.context = v
  },
})
watch(perspEdit, async (v) => {
  if (!v) return
  await nextTick()
  const ta = perspEditTa.value
  if (!ta) return
  ta.focus()
  // Focus alone drops the caret at the end and scrolls a long preset text out
  // of view; open it at the top instead, reading from the first word.
  ta.setSelectionRange(0, 0)
  ta.scrollTop = 0
})
/**
 * Keeping a perspective (P3).
 *
 * The first keep writes a new row from the preset the text was written over —
 * pipeline and chunks are inherited from it, the wording is what stands here
 * now. Afterwards the bubble is addressed by its own key, so a run records what
 * actually ran. A second press writes the change into the same row; the wording
 * it replaces is snapshotted server-side, so editing never loses anything.
 */
const keepBusy = ref(false)
const keepNote = ref('')
const perspEditName = computed({
  get: () => perspEditBubble.value?.configName ?? '',
  set: (v: string) => {
    const b = perspEditBubble.value
    if (b) b.configName = v
  },
})

async function keepCurrent() {
  const b = perspEditBubble.value
  if (!b || keepBusy.value) return
  const text = b.context.trim()
  if (!text) return
  keepBusy.value = true
  keepNote.value = ''
  try {
    if (b.promptId) {
      const saved = await kept.update(b.promptId, {
        name: b.configName.trim() || t('x2xFlow.perspectiveLabel'),
        context_text: text,
      })
      if (saved) {
        keepNote.value = t('x2xFlow.perspectiveKept')
        return
      }
      // Gone (dropped from the chooser, or the session ran out): the row this
      // tile pointed at does not exist any more. Without this the tile stayed
      // on that address for good and every further press answered 404.
      if (!kept.lastUpdateWasGone) {
        keepNote.value = kept.error || ''
        return
      }
      b.promptId = undefined
      b.configId = b.previewId || 'user_defined'
    }
    // What it runs through: the preset this text was written over. For a
    // perspective written from scratch that is the blank one.
    const base = b.previewId || b.configId || 'user_defined'
    const saved = await kept.keep(
      base,
      b.configName.trim() || t('x2xFlow.perspectiveLabel'),
      text,
    )
    if (!saved) {
      keepNote.value = kept.error || ''
      return
    }
    b.promptId = saved.id
    b.configId = saved.style_key
    b.configName = saved.name
    b.previewId = base
    keepNote.value = t('x2xFlow.perspectiveKept')
  } finally {
    keepBusy.value = false
  }
}

function openPerspEdit(b: BoardPerspective) {
  keepNote.value = ''
  const el = canvasEl.value
  if (!el) return
  const sx = b.x * zoom.value + pan.x
  const sy = b.y * zoom.value + pan.y
  const bubble = PB * zoom.value
  const w = Math.min(560, el.clientWidth - 16)
  const x = Math.min(Math.max(8, Math.round(sx + bubble / 2 - w / 2)), Math.max(8, el.clientWidth - w - 8))
  const H = 230
  let y = Math.round(sy + bubble + 10)
  if (y + H > el.clientHeight - footerClear()) y = Math.max(8, Math.round(sy - H - 10))
  loraEdit.value = null
  perspEdit.value = { id: b.id, x, y, w }
}

/** The strength half opens at its tile, placed as the written half is. */
const loraEdit = ref<{ id: string; x: number; y: number; w: number } | null>(null)
const loraEditTile = computed(
  () => (loraEdit.value && loraTiles.value.find((l) => l.id === loraEdit.value!.id)) || null
)
function openLoraEdit(l: BoardLora) {
  const el = canvasEl.value
  if (!el) return
  const sx = l.x * zoom.value + pan.x
  const sy = l.y * zoom.value + pan.y
  const bubble = PB * zoom.value
  const w = Math.min(420, el.clientWidth - 16)
  const x = Math.min(Math.max(8, Math.round(sx + bubble / 2 - w / 2)), Math.max(8, el.clientWidth - w - 8))
  const H = 170
  let y = Math.round(sy + bubble + 10)
  if (y + H > el.clientHeight - footerClear()) y = Math.max(8, Math.round(sy - H - 10))
  perspEdit.value = null
  loraEdit.value = { id: l.id, x, y, w }
}

interface OutputConfig {
  id: string
  label: string
  /** A developer note, half of it German. Never on screen — see bubbleOptions. */
  description?: string
  /** Shown as the entry's tooltip. Only the reading frames set one. */
  hint?: string
}

// The curated text-to-X mapping, in the order the long-press ring draws it. It
// is not the whole list — configsFor adds the image-input routes to it. The
// order does NOT decide the default any more: see defaultConfigFor.
const configsByMedium: Record<MediumId, OutputConfig[]> = {
  image: [
    { id: 'commoncanvas_xl_c', label: 'Common\nCanvas', description: 'Trained only on Creative-Commons-licensed images' },
    { id: 'sd35_large_turbo', label: 'Stable Diffusion\nTurbo', description: 'Four steps instead of thirty, distilled from SD 3.5 Large' },
    { id: 'sd35_large', label: 'Stable\nDiffusion', description: 'Klassische Bildgenerierung' },
    { id: 'flux2', label: 'Flux 2', description: 'Hochwertige Bildgenerierung mit Flux 2 Dev' },
    { id: 'flux3', label: 'Flux 3\nKlein', description: 'FLUX 3 Image Klein (Black Forest Labs, 2026), without the prompt upsampler' },
    { id: 'gemini_3_pro_image', label: 'Gemini 3\nPro (€)', description: 'Google Gemini 3 Pro via Mammouth AI (EU)' },
    { id: 'gemini_nano_banana_2_1', label: 'Nano Banana\n2.1 (€)', description: 'Google Gemini Nano Banana 2.1 via Mammouth AI (EU)' },
  ],
  video: [
    { id: 'wan22_t2v_video_fast', label: 'Wan 2.2\n14B Fast', description: 'Schnelle 14B Videogenerierung (4 Steps)' },
    { id: 'ltx_video', label: 'LTX\nVideo', description: 'Schnelle lokale Videogenerierung' },
  ],
  sound: [
    { id: 'stableaudio_open', label: 'Stable\nAudio 3', description: 'Sound, noise and ambience — the adaption decides its length (10–240s)' },
    { id: 'heartmula_standard', label: 'HeartMuLa', description: 'Music from lyrics and style tags' },
  ],
  // 3d has no text path: the chunk reads an image. Picked with none lying
  // there, the run makes the picture first and the mesh from it (finishRun) —
  // the one medium where a hand-pick does NOT give way, because there is
  // nothing to give way to.
  '3d': [{ id: 'hunyuan3d_text_to_3d', label: 'Hunyuan3D', description: 'Textured 3D mesh from an image' }],
  // The two configs that hand back JavaScript instead of a file. They came from
  // the text page, which was the only surface that could run what they wrote;
  // the surface is CodeSandbox now and opens from the output node.
  code: [
    { id: 'p5js_code', label: 'p5.js', description: 'Generative graphics as runnable p5.js code' },
    { id: 'tonejs_code', label: 'Tone.js', description: 'Sound synthesis as runnable Tone.js code' },
  ],
  // Empty on purpose: what stands behind the text glyph are the reading frames,
  // and their names come from i18n, which a module constant cannot call.
  // configsFor builds them; see frameConfigs.
  text: [],
}

const currentRunId = ref<string | null>(null)

/** Every item kind this build can draw. Anything else is dropped on restore. */
const KNOWN_KINDS = new Set<string>(['text', 'image', 'audio', 'video', 'source', 'code'])

// --- Persistence (assemblage + perspectives + free prompt) ---
onMounted(() => {
  try {
    const raw = sessionStorage.getItem('t2i_assemblage')
    if (raw) {
      const parsed = JSON.parse(raw) as AsmItem[]
      if (Array.isArray(parsed) && parsed.length) {
        // An image restored without a server path can never reach a pipeline
        // (it predates the upload, or its upload never landed). Show it, mark
        // it, and let the run refuse — do not drop it behind the user's back.
        parsed.forEach((i) => {
          if (i.kind === 'image' && !i.path) i.failed = true
        })
        // A board written by a newer build can hold a kind this one cannot
        // render. Dropping it is the only honest handling: shown, it would be
        // an empty box that still counts as something.
        setItems(parsed.filter((i) => KNOWN_KINDS.has(i.kind)))
      }
    }
  } catch {
    /* ignore */
  }
  // Source cards are placed by the machine, not by the user. A board holding
  // nothing else is an empty board and still needs something to write in.
  // That box is laid on its resting place once the view has come to rest
  // (`layRestCard`), and so is a box kept from an earlier visit, where the
  // board holds nothing but it and nothing is written in it.
  const material = items.value.filter((i) => i.kind !== 'source')
  const only = material.length === 1 ? material[0] : undefined
  if (!material.length) {
    const seed = sessionStorage.getItem('t2i_input_text') || ''
    const it = addText(60, 50)
    it.text = seed
    restCard = { id: it.id, laid: null }
  } else if (only?.kind === 'text' && !(only.text ?? '').trim()) {
    restCard = { id: only.id, laid: null }
  }
  let legacyBubbles = false
  try {
    const raw2 = sessionStorage.getItem('t2i_perspectives2')
    const raw = raw2 || sessionStorage.getItem('t2i_perspectives')
    legacyBubbles = !raw2 && !!raw
    if (raw) {
      const parsed = JSON.parse(raw) as BoardPerspective[]
      if (Array.isArray(parsed) && parsed.length) {
        bubbles.value = parsed
        bseq = parsed.reduce((m, b) => {
          const n = parseInt(b.id.replace(/^p/, ''), 10)
          return Number.isFinite(n) && n > m ? n : m
        }, 0)
        zseq = parsed.reduce((m, b) => Math.max(m, b.zoneSeq ?? 0), 0)
      }
    }
  } catch {
    /* ignore */
  }
  // The tiles on their own: a record of the one kind that does not read back
  // takes nothing of the other kind with it.
  try {
    const rawL = sessionStorage.getItem('t2i_loras')
    if (rawL) {
      const parsedL = JSON.parse(rawL) as BoardLora[]
      if (Array.isArray(parsedL) && parsedL.length) {
        loraTiles.value = parsedL.filter((l) => l && typeof l.file === 'string')
        lseq = loraTiles.value.reduce((m, l) => {
          const n = parseInt(l.id.replace(/^l/, ''), 10)
          return Number.isFinite(n) && n > m ? n : m
        }, 0)
        zseq = loraTiles.value.reduce((m, l) => Math.max(m, l.zoneSeq ?? 0), zseq)
      }
    }
  } catch {
    /* ignore */
  }


  // Drop the default view below the map band (see frameBelowMap): rAF fires
  // after layout, so the map's height is real and the offset never lands short.
  requestAnimationFrame(() => frameBelowMap())

  // The zone keeps its place across visits; a first visit sets it under the
  // generation node, projected into world coordinates once the stage has
  // measured itself. Until then the mid-board default holds.
  let zoneRestored = false
  try {
    const zraw = sessionStorage.getItem('t2i_zone')
    if (zraw) {
      const z = JSON.parse(zraw) as { x: number; y: number; r?: number }
      if (Number.isFinite(z.x) && Number.isFinite(z.y)) {
        zone.x = z.x
        zone.y = z.y
        if (Number.isFinite(z.r)) zone.r = Math.min(ZONE_R_MAX, Math.max(ZONE_R_MIN, z.r!))
        zoneRestored = true
      }
    }
  } catch {
    /* ignore */
  }
  if (!zoneRestored) {
    void nextTick().then(() => {
      const cEl = canvasEl.value
      const mEl = mapEl.value
      if (!cEl || !mEl) return
      const g = rect(RMAP.gen)
      if (g.width <= 0) return
      const mr = mEl.getBoundingClientRect()
      const cr = cEl.getBoundingClientRect()
      zone.x = (mr.left + g.left + g.width / 2 - cr.left - pan.x) / zoom.value
      zone.y = (40 - pan.y) / zoom.value + zone.r + 60
    })
  }

  // Material arriving from elsewhere waits for the zone to be where it will
  // actually be: on a first visit the zone is positioned in a later microtask,
  // and anything placed before that lands at a default that is nowhere near it.
  void nextTick().then(() => void nextTick().then(intakeFromElsewhere))
  void refreshAvailability()
  void kept.load()

  // Bubbles saved in the screen era land at the zone's rim — outside. Nothing
  // turns active silently: placing a perspective into the zone stays a gesture.
  if (legacyBubbles) {
    void nextTick().then(() => {
      bubbles.value.forEach((b, i) => {
        const a = -Math.PI / 2 + i * 0.7
        b.x = zone.x + Math.cos(a) * (zone.r + PB) - PB / 2
        b.y = zone.y + Math.sin(a) * (zone.r + PB) - PB / 2
      })
      sessionStorage.removeItem('t2i_perspectives')
    })
  }
})
watch(
  items,
  () => {
    // Only images that survived the upload are persisted: their `src` is a short
    // served URL. An in-flight image still carries its base64 preview, which
    // would blow the session quota — it is restored by re-adding, not by storage.
    const persistable = items.value.filter(
      (i) => i.kind !== 'image' || (!!i.path && !i.src?.startsWith('data:'))
    )
    try {
      sessionStorage.setItem('t2i_assemblage', JSON.stringify(persistable))
    } catch {
      /* quota — the board stays live, it just will not survive a reload */
    }
  },
  { deep: true }
)
watch(
  bubbles,
  () => {
    sessionStorage.setItem('t2i_perspectives2', JSON.stringify(bubbles.value))
  },
  { deep: true }
)
watch(
  loraTiles,
  () => {
    sessionStorage.setItem('t2i_loras', JSON.stringify(loraTiles.value))
  },
  { deep: true }
)
watch(zone, () =>
  sessionStorage.setItem(
    't2i_zone',
    JSON.stringify({ x: Math.round(zone.x), y: Math.round(zone.y), r: Math.round(zone.r) })
  )
)

// --- Medium inference (ambient, from the assemblage text) ---
const interceptionResult = ref('')
const inferenceText = computed(() => interceptionResult.value || effCombinedText.value)
const { media: inferredMedia, primary: inferredPrimary } = useMediumInference(inferenceText)

// A changed chain — swapped, reordered or rewritten — voids the last
// transformation the same way changed material does.
watch(
  () => zoneChain.value.map((b) => b.id + ':' + b.context).join('|'),
  (now, was) => {
    if (now !== was && interceptionResult.value) interceptionResult.value = ''
  }
)

// A changed material text hands inference back to the live board: the last
// run's transformed text no longer describes what lies there. Without this,
// the medium sticks to the previous run no matter what is written next.
watch(effCombinedText, (now, was) => {
  if (now !== was && interceptionResult.value) interceptionResult.value = ''
})

/**
 * Two texts can declare their own relation: a song's words plus a description of
 * how it should sound. That constellation has one pipeline (heartmula_standard),
 * and it is a stronger statement about the medium than any catchword — so it
 * asserts `sound` and is not clamped by images lying around.
 */
const musicRoles = computed(() =>
  classifyMusicRoles(effTextItems.value.map((i) => i.text || ''))
)
const HEARTMULA = 'heartmula_standard'

// A pick — a medium or a model — holds. Neither a rewritten text, nor a fresh
// inference, nor an image lying on the board may take it back. The single event
// that releases it and restores automatic routing is a new image upload.
const manualMedium = ref<MediumId | null>(null)
const manualModel = ref<string | null>(null)
function clearManualChoice() {
  manualMedium.value = null
  manualModel.value = null
}

// Base medium (hand-set, read from a two-text constellation, or inferred).
const baseMedium = computed<MediumId>(
  () => manualMedium.value ?? (musicRoles.value ? 'sound' : inferredPrimary.value)
)
/** The frames, named for the screen. Built here because t() lives in setup. */
function frameConfigs(): OutputConfig[] {
  return READING_FRAMES.map((id) => ({
    id,
    label: t(`compare.vlmAnalysis.perspectives.${id}`),
    hint: t(`x2xFlow.frameHint.${id}`),
  }))
}
function configsFor(m: MediumId): OutputConfig[] {
  const base = m === 'text' ? frameConfigs() : configsByMedium[m] || []
  // The image-input routes stand in the same list as the text-to-X ones. They
  // are only offered, never made the default: defaultConfigFor still reads
  // configsByMedium, so an empty board keeps its text path.
  const extra = IMAGE_INPUT_ROUTES.filter(
    (r) => r.medium === m && !base.some((c) => c.id === r.id)
  ).map((r) => ({ id: r.id, label: r.label }))
  return [...base, ...extra]
}
function defaultConfigFor(m: MediumId): string {
  if (m === 'text') return READING_FRAMES[0]
  // A picture opens on SD 3.5 Large, here as everywhere. It is read from the
  // platform's single image default rather than from the list above, where it
  // was whichever entry happened to stand first — CommonCanvas, and nobody's
  // choice.
  if (m === 'image') return RASTER_IMAGE_MODEL_SINGLE_DEFAULT
  return configsByMedium[m]?.[0]?.id || RASTER_IMAGE_MODEL_SINGLE_DEFAULT
}

/**
 * Media as operand: a sound on the board turns the run into a composition. What
 * is generated first (if anything) follows from the medium and what already lies
 * there. Sound that no plan consumes stays visible and is marked surplus.
 */
const composition = computed(() =>
  planComposition({
    hasText: !!effCombinedText.value.trim(),
    medium: baseMedium.value,
    audioRef: effAudioItems.value[0]?.runId ?? null,
    videoRef: effVideoItems.value[0]?.runId ?? null,
    // A picture that already lies there composes only when nothing else is
    // asked of it: a perspective in the reading has to be applied, not skipped.
    imageRef:
      zoneChain.value.length === 0
        ? (effImageItems.value.find((i) => i.runId)?.runId ?? null)
        : null,
  })
)

/**
 * Lyrics + style beat the medium's default model; a hand-picked model beats
 * both. A LoRA in the zone sets the picture's model to the one that carries it:
 * the automatic switches to the LoRA's model; a model picked by hand holds,
 * and a LoRA that model cannot load wears the "?".
 */
const t2xConfig = computed(() => {
  if (musicRoles.value && baseMedium.value === 'sound') return HEARTMULA
  if (baseMedium.value === 'image' && loraBase.value) return loraBase.value
  return defaultConfigFor(baseMedium.value)
})

/**
 * The hand-picked model as far as the route may honour it at all. Two picks are
 * held back here rather than refused, in the same spirit as the image-input
 * models the resolver drops:
 * - A reading frame is not an output config, it is a prompt key the analysis
 *   routes read. Handed on it would become `resolvedConfigId` and a run would
 *   post it to Stage 4, where no such config exists. `readingFrame` reads it.
 * - The music pipeline is spoken to in lyrics and a style. With nothing written
 *   there is nothing for it to set, and the surface would stand dark holding a
 *   pick it cannot serve; the medium stays `sound`, so what the material says
 *   becomes a sound by the medium's other path.
 */
const pickForRoute = computed<string | null>(() => {
  const m = manualModel.value
  if (!m || isReadingFrame(m)) return null
  if (m === HEARTMULA && !effCombinedText.value.trim()) return null
  return m
})

// Deterministic material route: a pinned pick wins as far as the material can
// feed it; otherwise the image count decides t2x / i2x / mi2x. A medium that was
// *asserted* — by hand, or by an unambiguous two-text constellation — is never
// clamped by image count.
const route = computed(() =>
  resolveRoute({
    imageCount: effImageItems.value.length,
    medium: baseMedium.value,
    t2xConfigId: t2xConfig.value,
    pinnedConfigId: pickForRoute.value,
    mediumPinned: manualMedium.value !== null || !!musicRoles.value,
  })
)
// Medium after clamping (≥2 images ⇒ image) drives the glyphs and config.
const activeMedium = computed<MediumId>(() => route.value.medium)

// No glyph claims a medium that nothing backs (UCD-260): the default guess
// stays a guess — quiet, like the note under a dropped pick — while a signal
// in the text, a pick by hand, the two-text constellation or the material
// itself (images route somewhere real) each are an occasion. The create box
// still names the machine that will run, so nothing is hidden; only the claim
// is withheld until the text or the table gives one.
const mediumClaimed = computed(
  () =>
    manualMedium.value !== null ||
    !!musicRoles.value ||
    inferredMedia.value.has(activeMedium.value) ||
    effImageItems.value.length > 0
)
const resolvedConfigId = computed<string>(() => route.value.outputConfigId)
/**
 * A hand-picked model that the material actually lets run. The mark under the
 * name in the create box says "this is your choice, and it holds" — set over a
 * name that is NOT the pick, because the route dropped it, it would say that of
 * the wrong model. A frame is not routed at all: it is read, so it always holds.
 */
/**
 * What was picked by hand, what runs instead, and nothing when the pick is in
 * force. The pick is not discarded — it takes effect the moment the material
 * carries it (pickForRoute / resolveRoute) — but until then the create box
 * names a model nobody chose, and that has to be said rather than left to be
 * noticed. A picked MEDIUM counts too: 3d with no picture makes a picture.
 */
const droppedChoice = computed<string>(() => {
  if (!willGenerate.value) return ''
  const used = labelForConfig(runConfigId.value)
  if (manualModel.value && !modelChoiceInForce.value)
    return t('x2xFlow.choiceDropped', { picked: labelForConfig(manualModel.value), used })
  if (manualMedium.value && manualMedium.value !== activeMedium.value)
    return t('x2xFlow.choiceDropped', { picked: mediumLabel(manualMedium.value), used })
  return ''
})
const modelChoiceInForce = computed(() => {
  const m = manualModel.value
  if (!m) return false
  if (isReadingFrame(m)) return true
  return resolvedConfigId.value === m
})
/**
 * The config a press would REALLY execute. It differs from `resolvedConfigId`
 * in exactly one case, and everything that speaks about the run — the run, the
 * card that names what the prompt was reformulated for, the check whether that
 * model is even answering — has to ask here instead of there: with the text
 * medium the frame is a way of reading, not a config, and the object that gets
 * read is made by the medium's own image model.
 */
const runConfigId = computed<string>(() =>
  manualMedium.value === 'text' ? (loraBase.value ?? defaultConfigFor('image')) : resolvedConfigId.value
)

/**
 * The LoRAs in the zone that the next run loads: those whose model is the
 * model the run executes. Under any other model — picked by hand, or the route
 * of a picture in the ring — and in a run that makes no picture, a LoRA lies
 * there unused and says so with the "?" of unused material.
 */
/**
 * Whether the register carries a file under a config: a row names it, the
 * file lies in the folder, and the config is in the row's list. A tile keeps
 * a copy of that list from the moment it was laid; the register's word is the
 * current one, and the run is checked against that.
 */
function loraCarried(file: string, cfg: string): boolean {
  const row = loraStore.byFile(file)
  return !!row && row.present && row.base_configs.includes(cfg)
}
const carriedLoras = computed<BoardLora[]>(() => {
  if (!willGenerate.value) return []
  const cfg = runConfigId.value
  return zoneLoras.value.filter((l) => loraCarried(l.file, cfg))
})
const loraUnusedIds = computed<Set<string>>(() => {
  const carried = new Set(carriedLoras.value.map((l) => l.id))
  return new Set([...zoneLoraIds.value].filter((id) => !carried.has(id)))
})
/** A perspective's own adapter goes with the run under the model that carries it, and only there. */
function bubbleLoraCarried(b: BoardPerspective): boolean {
  if (!willGenerate.value) return false
  const cfg = runConfigId.value
  const files = bubbleLoraFiles(b)
  return files.length > 0 && files.every((f) => loraCarried(f, cfg))
}
/** What a run names to the server: the file, and the strength as a fraction. */
type RunLora = { name: string; strength: number }
/**
 * The tiles a run loads under the model it executes. Read from the tiles the
 * press found in the zone (`RunOrigin.tiles`), once that model is known — the
 * interception says what medium the words ask for, and the model follows.
 */
function runLoras(tiles: BoardLora[], cfg: string): RunLora[] {
  return tiles.filter((l) => loraCarried(l.file, cfg)).map((l) => ({ name: l.file, strength: l.strength / 100 }))
}
/** The names with their strength, as the create box and the card's back read them. */
function loraLabelOf(loras: RunLora[]): string {
  return loras
    .map((l) => `${loraStore.byFile(l.name)?.name || l.name} · ${Math.round(l.strength * 100)} %`)
    .join(', ')
}
const carriedLoraLabel = computed(() =>
  loraLabelOf(carriedLoras.value.map((l) => ({ name: l.file, strength: l.strength / 100 })))
)

/** The resolved model cannot be reached: the run says so instead of failing. */
const routeUnavailable = computed(() => modelMissing(runConfigId.value))

/**
 * Material lies in the reading, nothing is written, and a medium or a model was
 * picked by hand: then the material itself says what is to be made of it — it is
 * read into words, and those words are the prompt. Everything around this is
 * handled by its own path and must never enter here: words already present, a
 * compose plan, a perspective in the zone, or no hand-pick at all (an unpicked
 * image routes to i2i, which consumes it; unpicked material with nothing else
 * written is simply read — see analysisReady).
 */
const readMaterialAsPrompt = computed(() => {
  if (effCombinedText.value.trim()) return false
  if (composition.value) return false
  if (zoneChain.value.length > 0) return false
  if (manualModel.value === null && manualMedium.value === null) return false
  const r = route.value
  if (r.outputConfigId === HEARTMULA) return false
  const hasImage = effImageItems.value.length > 0
  const hasAv = effAudioItems.value.length > 0 || effVideoItems.value.length > 0
  if (!hasImage && !hasAv) return false
  // A model was picked by hand, material lies there and nothing is written:
  // then the material says what to make of it. This holds for every count —
  // an image with no image slot, an image the model does take, too few for a
  // fusion, any audio or video. Asking how many pictures the model eats made
  // the surface absurd: with TWO pictures — what the fusion actually wants —
  // the triangle went dark, because nothing said what to fuse them into.
  return true
})

/**
 * Material in the ring the route cannot hand to the model. It falls away no
 * longer: it is READ. The picture, sound or video is put into words, and those
 * words go into the prompt in front of what was written: everything lying in
 * the ring that the route discards is read.
 *
 * One formula covers every route: a picture past the count the model takes (0
 * for a text-only model such as p5.js, 1 for i2i, 3 for the fusion), and any
 * sound or video no composition consumes. The marker lives only inside the
 * zone; material lying outside is left alone, it merely lies ready. A reading
 * run takes everything as it is, so it marks nothing.
 */
const readIntoWordsIds = computed<Set<string>>(() => {
  if (!willGenerate.value) return new Set<string>()
  const s = new Set<string>()
  const cap = route.value.maxImages
  effImageItems.value.forEach((it, idx) => {
    if (idx >= cap) s.add(it.id)
  })
  const plan = composition.value
  // Exactly one sound is composed, and only when a plan exists at all.
  effAudioItems.value.forEach((it, i) => {
    if (!(plan && i === 0)) s.add(it.id)
  })
  // A video is consumed only when the plan actually reads one.
  effVideoItems.value.forEach((it, i) => {
    if (!(plan && i === 0 && plan.ready.video)) s.add(it.id)
  })
  return new Set([...s].filter((id) => zoneItemIds.value.has(id)))
})

/** Those same pieces, in board order: what the run hands to the reading. */
const readIntoWordsItems = computed(() => ({
  images: effImageItems.value.filter((it) => readIntoWordsIds.value.has(it.id)),
  audio: effAudioItems.value.filter((it) => readIntoWordsIds.value.has(it.id)),
  video: effVideoItems.value.filter((it) => readIntoWordsIds.value.has(it.id)),
}))

/**
 * A reading over material in the ring takes every picture, sound and video
 * there, and it reads no WORDS: that is the one thing in the ring a run still
 * passes over, and the "?" marks it. (With no material the words are used after
 * all: they make the thing that is then read, see runGenerate.)
 */
const surplusIds = computed<Set<string>>(() => {
  if (willGenerate.value || readCount.value === 0) return new Set<string>()
  return new Set(
    effTextItems.value.filter((it) => zoneItemIds.value.has(it.id)).map((it) => it.id)
  )
})

const resolvedConfigLabel = computed(() => labelForConfig(resolvedConfigId.value))
/** How many pieces of material the next run would read. */
const readCount = computed(
  () => effImageItems.value.length + effAudioItems.value.length + effVideoItems.value.length
)
/**
 * Whether the next run makes a medium at all. Material alone in the circle is
 * READ (runAnalysisOnly): no config is used, no model runs. Everything that
 * names the model has to ask here first — two images with no words came out as
 * a comparison while the box, the run panel and the companion all said Qwen
 * Multi.
 */
const willGenerate = computed(() => !analysisReady.value)
/** What the create box says it will do — and a reading is two operations. */
const createLabel = computed(() => {
  // A chosen frame IS the choice in force, so the slot that shows what is in
  // force shows it — before anything else, and whether or not there is material
  // to read yet. Only an unasked-for reading names the act instead.
  if (readingFrame.value) return labelForConfig(readingFrame.value)
  if (willGenerate.value) return resolvedConfigLabel.value
  return readCount.value === 2 ? t('x2xFlow.readsTwo') : t('x2xFlow.readsOne')
})
const MEDIUM_KEY: Record<MediumId, string> = {
  text: 'x2xFlow.mText',
  image: 'x2xFlow.mImage',
  video: 'x2xFlow.mVideo',
  sound: 'x2xFlow.mSound',
  '3d': 'x2xFlow.m3d',
  code: 'x2xFlow.mCode',
}
function mediumLabel(m: MediumId): string {
  return t(MEDIUM_KEY[m])
}
/**
 * Many pieces lie on this board at once. The companion can only stand at one,
 * so it stands at the one whose card is open — and at the newest when none is.
 */
watch(inspected, (it) => {
  if (it?.runId) updateSession(it.runId, { mediaType: it.meta?.mediaType || it.kind })
})

/** The short name of ONE config, whatever the surface currently resolves to. */
function labelForConfig(id: string): string {
  // The frames are not in configsByMedium and their ids are backend keys —
  // unnamed here, a German key would stand on screen. The names come from the
  // comparison page's own list, which has named these same five methods, in six
  // languages, since long before this surface could reach them: one method, one
  // name, everywhere.
  if (isReadingFrame(id)) return t(`compare.vlmAnalysis.perspectives.${id}`)
  for (const list of Object.values(configsByMedium)) {
    const hit = list.find((c) => c.id === id)
    if (hit) return hit.label.replace('\n', ' ')
  }
  return ROUTE_LABELS[id] || id
}
/**
 * Human-readable model name. `fallback` is the config the RUN was sent with —
 * never the one the surface shows now: a model picked by hand while the card
 * was still being computed would otherwise end up on a picture it never made.
 */
function resolveModelName(meta: Record<string, any> | null, fallback?: string): string {
  // Before stage 4 has said anything, the name of the config that WILL run —
  // runConfigId, not resolvedConfigId: with the text medium the latter is a
  // reading frame, and always the first one at that.
  const fb = fallback ? labelForConfig(fallback) : labelForConfig(runConfigId.value)
  if (!meta) return fb
  return meta.display_name || meta.model_file || meta.backend_type || fb
}

const bubblesFor = ref<MediumId | null>(null)
/**
 * Which models are actually installed and reachable. Asked once when the page
 * opens and on every long press, because a backend can come up or fall over
 * while the page stands there. The asking, the twenty seconds between two
 * questions and the rule that a failed check marks nothing stand in
 * composables/useModelAvailability.ts since 2026-09-23, where Mean Images
 * and the model choice of five instruments read the same answer.
 */
const {
  refresh: refreshAvailability,
  missing: modelMissing,
  accountMissing,
  accountParams,
} = useModelAvailability()
/**
 * Why a model cannot be picked, for the hover and for a run that asks for it
 * anyway. A cloud model whose provider holds no key or no credit says that
 * in its own hover sentence; the sentence for a model that is not installed
 * would name a cause that is not the case. It names the provider the
 * config's output chunk sends to, from the availability answer.
 */
function missingText(id: string): string {
  return accountMissing(id) ? t('x2xFlow.accountMissing', accountParams(id)) : t('x2xFlow.modelUnavailable')
}
/**
 * The card beside a model, in the list under a medium glyph and at the model's
 * name in the create box. It says what the t2x page's hover card said:
 * composables/useOutputCards.ts.
 */
const outputCards = useOutputCards()
function cardIds(): string[] {
  return [...Object.values(configsByMedium).flat().map((c) => c.id), ...IMAGE_INPUT_ROUTES.map((r) => r.id)]
}
onMounted(() => outputCards.ensure(cardIds()))
const {
  shown: modelCardShown,
  x: modelCardX,
  y: modelCardY,
  above: modelCardAbove,
  enter: enterModelCard,
  leave: leaveModelCard,
  close: closeModelCard,
} = useInfoCard<ChipInfo>()
/** The card at the model's name: only where it names a model that will run. */
const crModelCard = computed(() =>
  willGenerate.value && !readingFrame.value ? outputCards.infoFor(resolvedConfigId.value, locale.value) : undefined
)
/** Its hover where no card stands: a reading says what happens to the
    material, a frame what it looks at (the frame's hint in the list), and a
    model whose card has not come, or whose question failed, its full name. */
const crModelTitle = computed(() => {
  if (!willGenerate.value) return t('x2xFlow.readsMaterialHint')
  const frame = readingFrame.value || (isReadingFrame(resolvedConfigId.value) ? resolvedConfigId.value : '')
  if (frame) return t(`x2xFlow.frameHint.${frame}`)
  return crModelCard.value ? undefined : resolvedConfigLabel.value
})

/** The names as the shared component takes them. */
const bubbleOptions = computed<FlowBubble[]>(() => {
  const m = bubblesFor.value
  if (!m) return []
  const out: FlowBubble[] = configsFor(m).map((c) => {
    // A route whose input is an image stands here like every other name, with
    // or without a picture in the ring. Picked with too few pictures it does not
    // run — the automatic route does (resolveRoute), and the create box names
    // that one. Striking it through would say the choice cannot be made, when
    // what is true is that it waits for a picture.
    return {
      id: c.id,
      label: c.label.replace('\n', ' '),
      // The only thing that really cannot be picked is a model that is not
      // answering. Otherwise the entry's own hint, which only the reading
      // frames carry — a frame's name says the method, not where it comes from
      // or what it looks at.
      title: modelMissing(c.id) ? missingText(c.id) : c.hint || undefined,
      disabled: modelMissing(c.id),
      info: outputCards.infoFor(c.id, locale.value),
    }
  })
  // The way back. A pick holds, and until now the single thing that released it
  // was uploading an image — a gesture nobody performs in order to undo a
  // choice. It stands in the list the choice was made in.
  if (manualModel.value !== null || manualMedium.value !== null) {
    out.unshift({ id: null, label: t('x2xFlow.modelAuto'), title: t('x2xFlow.modelAutoHint') })
  }
  return out
})
const bubblesStyle = computed(() => {
  const r = rect(RMAP.create)
  return { left: `${r.left}px`, top: `${r.top + r.height + 6}px` }
})
// Same left/top-below-node geometry as bubblesStyle, anchored to RMAP.gen.
const genPromptStyle = computed(() => {
  const r = rect(RMAP.gen)
  return { left: `${r.left}px`, top: `${r.top + r.height + 6}px` }
})
// The reserved rectangle hugs the three boxes with a flexible width, so only it
// — not the whole top band — is locked out of the canvas. It lives inside
// .fl-map and shares its coordinate space, so rect() drives it directly.
const lockRectStyle = computed(() => {
  const a = rect(RMAP.create)
  const b = rect(RMAP.output)
  const pad = 8
  return {
    left: `${a.left - pad}px`,
    top: `${a.top - pad}px`,
    width: `${b.left + b.width - a.left + pad * 2}px`,
    height: `${Math.max(a.height, b.height) + pad * 2}px`,
  }
})

// The map is an absolute overlay, so the canvas now fills the view from y = 0 —
// whereas the material's coordinates were laid down when the canvas began *below*
// the map band. Without a matching vertical offset every piece rides up over the
// three boxes ("sitzt zu hoch"). That offset is exactly the band the map used to
// reserve as an in-flow row: its height + the 10px it sits from the top + the
// 10px it kept below + the old default pan of 40 == mapHeight + 60. Read the
// height straight off the laid-out map in a rAF — which runs *after* layout, so
// clientHeight is real, unlike rect() read in a nextTick (measured 0, bailed).
function frameBelowMap(tries = 20) {
  const h = mapEl.value?.clientHeight ?? 0
  if (h <= 0) {
    if (tries > 0) requestAnimationFrame(() => frameBelowMap(tries - 1))
    return
  }
  pan.y = h + 60
  // The view has only now come to rest, and with it the world coordinates the
  // prompt box of a fresh surface is laid in. Only the first time: "1:1" brings
  // the view back, and leaves the signs and the box where they lie.
  if (framed) return
  framed = true
  void nextTick(reHome)
}
function resetView() {
  resetViewBase()
  frameBelowMap()
}
// The same press-and-hold the preset circles use to show their name.
const { start: beginHold, cancel: endHold, consumeHeld } = useHold<MediumId>((m) => {
  bubblesFor.value = m
})
function startHold(m: MediumId) {
  void refreshAvailability()
  outputCards.ensure(cardIds())
  beginHold(m)
}
function favMediaType(it: AsmItem): FavoriteItem['media_type'] {
  if (it.meta?.mediaType === 'music') return 'music'
  if (it.meta?.mediaType === 'composition') return 'composition'
  if (it.kind === 'audio') return 'audio'
  if (it.kind === 'video') return 'video'
  // A sketch is its source text, and that is what the run holds. The still on
  // the card is drawn by this browser and lies in no run folder: kept as a
  // picture, the star was refused and sprang back under the finger.
  if (it.kind === 'code') return it.codeKind === 'tonejs' ? 'tonejs' : 'p5'
  return 'image'
}
function toggleItemFav(it: AsmItem) {
  if (!it.runId) return
  void favStore.toggleFavorite(it.runId, favMediaType(it), deviceId, 'anonymous', 'x2x_flow')
}
function toggleInspectedFav() {
  if (inspected.value) toggleItemFav(inspected.value)
}
/** The piece onto paper, the platform's way (lib/printMedia.ts). */
function printItem(it: AsmItem) {
  printMedia(it.src)
}
function printInspected() {
  if (inspected.value) printItem(inspected.value)
}
/** Save the piece: the file at its served address, or a sketch as the text it is. */
function downloadItem(it: AsmItem) {
  if (it.kind === 'code') {
    downloadBlob(new Blob([it.text || ''], { type: 'text/javascript' }), `sketch_${it.runId || it.id}.js`)
    return
  }
  if (!it.src) return
  void downloadMedia(it.src, mediaFileName('flow', [runStem(it.runId || it.id)], mediaExtension(it.kind)))
}
function downloadInspected() {
  if (inspected.value) downloadItem(inspected.value)
}
/**
 * What stands beside the piece in the layer: the record its fall captured
 * (`meta`), or the source a perspective looked up. An upload has neither and
 * stands alone. Handing on is off — the piece already lies on this table. The
 * AI marking is read out of the file by the back itself, from the run and
 * the kind: `src` is the served upload the run reads, not the run's own file.
 */
/**
 * Which runs on the board carry a star. `isFavorited` walks the whole list, and
 * the back of every card asks it twice per render — the board renders again on
 * every frame of a pan, so the walk has to come down to one lookup.
 */
const favRunIds = computed(() => new Set(favStore.favorites.map((f) => f.run_id)))
function backFor(it: AsmItem): MediaBack | null {
  if (it.source) return { source: it.source }
  if (!it.meta && !it.runId) return null
  return {
    mediaType: favMediaType(it),
    runId: it.runId ?? null,
    isFavorited: !!it.runId && favRunIds.value.has(it.runId),
    canForward: false,
    prompt: it.meta?.prompt,
    configId: it.meta?.config,
    perspective: it.meta?.preset,
    loras: it.meta?.loras,
    safety: it.meta?.safety,
  }
}
const inspectedBack = computed<MediaBack | null>(() =>
  inspected.value ? backFor(inspected.value) : null
)

function onMediumClick(m: MediumId) {
  if (consumeHeld()) return
  manualMedium.value = m
  manualModel.value = null
  bubblesFor.value = null
}
function pickModel(id: string | null) {
  // null is the entry that hands the choice back to the surface.
  if (id === null) {
    clearManualChoice()
    bubblesFor.value = null
    return
  }
  // A model belongs to a medium: picking one pins both, so the resolved config
  // can never disagree with the medium the glyphs show.
  if (bubblesFor.value) manualMedium.value = bubblesFor.value
  manualModel.value = id
  bubblesFor.value = null
}
onBeforeUnmount(endHold)

// --- Flow run: interception (SSE) then generation, triggered from the node ---
const {
  generationProgress,
  previewImage,
  isExecuting,
  currentStage,
  modelMeta,
  encodingInfo,
  genStep,
  genTotalSteps,
  queuePosition,
  queueWaitS,
  deviceBusy,
  busyMedium,
  checkDeviceActive,
  showTranslatedStamp,
  safetyChecks,
  stage3Model,
  executeWithStreaming,
  cancelGeneration,
  reset: resetStream,
} = useGenerationStream()

/**
 * How long until this run reaches the card, in words.
 *
 * Empty when the gate has no measurement for what is queued — before a model
 * has run a few times, and while its runs still sit too far apart to have a
 * middle, there is nothing to derive a minute from, and an invented number is
 * worse than none. Rounded to five seconds below a minute and to whole minutes
 * above it: the estimate is not accurate to the second and must not look as if
 * it were. The rounding decides the branch, not the raw value — otherwise 88
 * seconds reads "about 90 s" and 90 seconds reads "about 2 min", two names for
 * one duration, one of them a third too long.
 */
const durationLabel = (s: number | null | undefined) => durationWords(t, s)
const queueWaitLabel = computed(() => queueWaitWords(t, queueWaitS.value))
/**
 * The same figure for the step card, which is 96px wide and has room for a
 * number and a unit, not for a sentence.
 */
const queueWaitShort = computed(() => {
  const p = waitParts(queueWaitS.value)
  if (!p) return ''
  if (p.unit === 'h') {
    return p.m
      ? t('x2xFlow.queueWaitShortH', { h: p.n, m: p.m })
      : t('x2xFlow.queueWaitShortHOnly', { h: p.n })
  }
  return p.unit === 's'
    ? t('x2xFlow.queueWaitShortS', { n: p.n })
    : t('x2xFlow.queueWaitShortMin', { n: p.n })
})

/**
 * The run this device already has, named by what it is making. The medium is
 * the one the backend recorded for that run; where it did not, the line says
 * the same thing without naming it.
 */
const BACKEND_MEDIUM: Record<string, MediumId> = {
  text: 'text', image: 'image', video: 'video',
  audio: 'sound', music: 'sound', sound: 'sound',
  '3d': '3d', code: 'code',
}
const deviceBusyLine = computed(() => {
  const id = BACKEND_MEDIUM[busyMedium.value]
  return id
    ? t('mediaInput.deviceBusy', { medium: mediumLabel(id) })
    : t('mediaInput.deviceBusyPlain')
})

/**
 * Who holds the run on this device — asked before the box is offered, never
 * after a press. Only the backend knows it, so only the backend is asked: on
 * arrival and whenever this window comes back to the front, and while the
 * answer is yes the stream polls every 3 s and clears itself when the other run
 * ends. Nothing here keeps a state of its own that somebody would have to reset.
 */
function askDeviceRun() {
  if (isExecuting.value) return
  void checkDeviceActive(deviceId)
}
function onWindowVisible() {
  if (document.visibilityState === 'visible') askDeviceRun()
}
onMounted(() => {
  askDeviceRun()
  document.addEventListener('visibilitychange', onWindowVisible)
})
onBeforeUnmount(() => document.removeEventListener('visibilitychange', onWindowVisible))

const interceptionActive = ref(false)
const safetyState = ref<'idle' | 'running' | 'passed' | 'blocked'>('idle')
const blockedReason = ref('')
/**
 * WHERE the run was stopped — 'vlm_input', 'vlm_safety', or a stage number.
 * Without it a picture the platform refused reads as a refused prompt, and the
 * box tells the reader to reword what was never the subject.
 */
const blockedStage = ref<string | number | null>(null)
const generationErrorMessage = ref('')
/**
 * What a run that did not come back says. Three refs, one face:
 * `generationErrorMessage` is the CAUSE, stated, in red, and it is the box's
 * body as before; `genFailAction` is the one thing to DO about it, grey, under
 * the cause; `genFailDetail` holds the whole sentence and the engine's own
 * words for the hover.
 *
 * The cause has ONE line of 127 px and is clamped to it — every wording is
 * measured against that width. The instruction below may take two lines, and
 * where it does the model name steps aside (`giCrowded`) instead of the cause
 * being cut. Whatever does not fit is in the hover, not cut off on the surface.
 *
 * The instruction hangs on the reason by its very text. Anything else that
 * writes the body — the next run, a stop, one of the older messages that
 * already carries its own instruction — lets the instruction and the engine's
 * words fall away with it, so no instruction can outlive its failure.
 */
const genFail = ref<{ why: string; act: string; detail: string } | null>(null)
const genFailShown = computed(
  () => !!genFail.value && genFail.value.why === generationErrorMessage.value
)
const genFailAction = computed(() => (genFailShown.value ? genFail.value!.act : ''))
const genFailDetail = computed(() => (genFailShown.value ? genFail.value!.detail : ''))

/**
 * The box says what to do, never what the engine said: `Step step_1_… failed:
 * Backend error: …` was standing on the surface of a workshop table.
 *
 * The class comes from the platform's one classifier. Two of the classes are
 * not the doing of the person at the surface — the service is not reachable, or
 * what was asked for is not installed here — and there the instruction depends
 * on who is looking: a participant passes it on, an educator or admin IS the
 * addressee and reads the cause alone. The text-instead-of-picture case keeps
 * its own long sentence, which already says what to do.
 */
/**
 * What to do about a card that is busy — which depends on how long it will be.
 * A training holds it for hours and a queue for minutes, and "try again" is an
 * answer only to the second.
 */
function busyAction(busy?: BusyNote): string {
  if (!busy) return t('generationError.startAgain')
  const time = durationLabel(busy.remaining_s)
  if (busy.reason === 'long_hold') {
    return time
      ? t('generationError.trainingLeft', { time })
      : t('generationError.trainingUnknown')
  }
  if (busy.reason === 'queue_full' && busy.waiting) {
    return time
      ? t('generationError.queueWaitAct', { n: busy.waiting, time })
      : t('generationError.queueWaitingAct', { n: busy.waiting })
  }
  return t('generationError.startAgain')
}

function failRun(raw: string, kind?: GenerationErrorType, busy?: BusyNote) {
  const type: GenerationErrorType = kind ?? classifyError(raw || '')
  const passOn = auth.isParticipant || !auth.isAuthenticated
  let act = ''
  let why = ''
  let full = ''
  if (type === 'offline') {
    act = passOn ? t('generationError.tellLeader') : ''
    why = t('generationError.causeUnreachable')
    full = t('generationError.serviceSilent')
  } else if (type === 'missing') {
    act = passOn ? t('generationError.takeAnother') : ''
    why = t('generationError.causeNoModel')
    full = t('generationError.notHere')
  } else if (type === 'busy') {
    // The cause is the state the gate named, and the instruction is measured
    // against it. Both used to be one sentence for four different states.
    why = t(busyCauseKey(busy ?? { reason: 'busy' }))
    act = busyAction(busy)
    full = t('generationError.busy')
  } else if (type === 'text_not_image') {
    // The platform's own sentence, and long by design: it explains why a prompt
    // that reads like a story is continued as one. It stays whole in the hover.
    why = raw || t('generationError.unknown')
  } else {
    act = t('generationError.startAgain')
    why = t('generationError.causeAborted')
    full = t('generationError.brokeOff')
  }
  generationErrorMessage.value = why
  genFail.value = { why, act, detail: [full, raw].filter(Boolean).join('\n') }
}

/**
 * How many lines the body may draw. The box rides the stage's scale, the type
 * rides the viewport: on a small stage the three lines it was fixed at do not
 * fit the space that is left, and the third one was cut through the middle of
 * its glyphs. So the count is read off the space itself, and the last line the
 * box shows is a whole one.
 */
const giBodyEl = ref<HTMLElement | null>(null)
const giLines = ref(3)
let giRO: ResizeObserver | null = null

/**
 * An instruction that needs a second line gets it from the model name, and only
 * then: measured at the instruction itself, because whether it wraps depends on
 * the language, not on the class of the failure. Hiding the name does not change
 * the instruction's width, so this settles in one pass.
 */
const giActEl = ref<HTMLElement | null>(null)
const giCrowded = ref(false)
let giActRO: ResizeObserver | null = null
watch(giActEl, (el) => {
  giActRO?.disconnect()
  giActRO = null
  if (!el) {
    giCrowded.value = false
    return
  }
  giActRO = new ResizeObserver(() => {
    const lh = parseFloat(getComputedStyle(el).lineHeight)
    if (!lh) return
    giCrowded.value = el.scrollHeight > lh * 1.5
  })
  giActRO.observe(el)
})
onBeforeUnmount(() => giActRO?.disconnect())
/**
 * Watched at the element, not at the state that changes it. The box arrives at
 * its resting size through a CSS transition out of the wide run card, and no
 * reactive source fires when it gets there — a count taken from the state alone
 * kept the wide card's value and cut the resting box's last line in half again.
 */
watch(giBodyEl, (el) => {
  giRO?.disconnect()
  giRO = null
  if (!el) return
  giRO = new ResizeObserver(() => {
    const lh = parseFloat(getComputedStyle(el).lineHeight)
    if (!lh) return
    giLines.value = Math.max(1, Math.floor(el.clientHeight / lh))
  })
  giRO.observe(el)
})
onBeforeUnmount(() => giRO?.disconnect())
const mediaUrl = ref('')
const mediaType = ref('')
// A composition runs over POST (/api/media/compose), so it has no stream.
const directRunning = ref(false)
// The last prompt actually sent to the model, held for the hover overlay on
// the generation node — independent of interceptionResult, which the board
// clears the moment the material text changes.
const lastSubmittedPrompt = ref('')
const genHover = ref(false)
/**
 * The config the run in flight was sent to. The stations name THIS one and not
 * what the table would route to now: material moves while a run runs. Empty
 * between runs, where the live route is the honest answer.
 */
const runningConfigId = ref('')
/**
 * The stream has ended and the piece is not on the table yet. A picture is
 * uploaded back so the pipelines may read it, and over a slow link that is the
 * longest stretch of the whole run. Without this the box drops to its resting
 * face right there: it would accept a second press — which lets go of this very
 * run, and with it a reading that was still to come — and refuse the hold that
 * stops a run.
 */
const settling = ref(false)
/**
 * The flow is making the picture the chosen model reads, and the run is NOT
 * over between the two generations. Without this the box falls back to its
 * resting face while the first picture is still being taken over: it would look
 * idle, accept a second press that kills the chain it just started, and refuse
 * the hold that stops a run — for as long as an upload takes.
 */
const provisioning = ref(false)
const busy = computed(
  () =>
    interceptionActive.value ||
    isExecuting.value ||
    // Another window on this device already holds the run. The box does not
    // take a press it knows the backend would refuse: a refusal that arrives
    // after the press is an explanation nobody asked for, and there is nothing
    // here that a learner did wrong.
    deviceBusy.value ||
    directRunning.value ||
    settling.value ||
    provisioning.value ||
    analyzing.value ||
    adapting.value
)
// An image still uploading, or one that failed to, is material the run would
// have to ignore. The flow waits or refuses rather than dropping it.
// Material alone in the circle -- no words, no perspective, nothing picked by
// hand: the run reads instead of making. One piece is described, two are read
// side by side, three or more one after another (runAnalysisOnly does all
// three, and names what it did).
const analysisReady = computed(() => {
  // Text is not a medium something is made IN, it is the medium a reading
  // comes out as. Chosen, it says: read what lies here — however much, and
  // whatever else is written on the table.
  if (manualMedium.value === 'text') return readCount.value >= 1
  return (
    !effCombinedText.value.trim() &&
    !composition.value &&
    zoneChain.value.length === 0 &&
    readCount.value >= 1 &&
    // A picked model or medium is a request to MAKE something of this material.
    // Without this the pick was discarded: Qwen Edit on a single image ran a
    // description of it, because reading came first and never asked. Reading
    // stays reachable on its own — the mark on the circle does nothing else.
    // (This also covers readMaterialAsPrompt, which needs a hand pick to be true.)
    manualModel.value === null &&
    manualMedium.value === null
  )
})
/**
 * The frame this reading is held in, or '' for the plain one. Only a chosen
 * text medium sets a frame: a reading that happened by itself, because nothing
 * else could be made of the material, keeps reading as it always did.
 */
const readingFrame = computed(() =>
  manualMedium.value === 'text' ? (manualModel.value ?? defaultConfigFor('text')) : ''
)
// The model in the box can change under a resting pointer: the medium follows
// the words as they are typed. A card that stands then names the new model, or
// goes where there is none. It stands here, below `analysisReady` and
// `readingFrame`: a watch reads its source at once, and `crModelCard` reads
// both, `analysisReady` through `willGenerate`. Above them the setup throws and
// the page stays empty (bb33dc01).
watch(crModelCard, (card) => {
  if (modelCardShown.value === null) return
  if (card) modelCardShown.value = card
  else closeModelCard()
})
/**
 * Nothing here says what to make: no words, no composition, no perspective on
 * the material, and neither of the two paths that make the material speak for
 * itself (a reading, or a reading used as the prompt).
 *
 * Since material without words is always read — whatever model is in force —
 * this now amounts to: nothing lies here at all. It is the resting state of an
 * empty board, not a judgement about a constellation.
 */
const nothingToRunFrom = computed(
  () =>
    (!effCombinedText.value.trim() &&
    !composition.value &&
    !analysisReady.value &&
      !readMaterialAsPrompt.value &&
      !(readCount.value > 0 && zoneChain.value.length > 0))
)
// The flow always makes something — that is what it is for. What can stop a
// press is therefore only what the surface CANNOT resolve by choosing: a run
// already going, an upload still in flight or broken, and an empty board. A
// model whose input picture is missing is not on that list — the pick gives way
// to automatic routing (resolveRoute). Nor is material without words: it gets
// read (see readMaterialAsPrompt).
const canRun = computed(
  () =>
    !nothingToRunFrom.value &&
    !busy.value &&
    !effUploadsPending.value &&
    !effUploadsFailed.value
)
// Reaching Stage 4 means the check passed — it is the only way through.
watch(currentStage, (s) => {
  if (s === 'stage3') safetyState.value = 'running'
  else if (s === 'stage4') safetyState.value = 'passed'
})

/**
 * The generation node has three faces: a triangle at rest, a pulse while the
 * language model rereads the material, and the run's card from Stage 3 on.
 * A successful run hands the node back to the triangle; the card holds only
 * while the run works and when it ends blocked or in error. The record of a
 * finished inference belongs to the media object itself (flipback, planned).
 */
const genPhase = computed<'idle' | 'pulse' | 'info'>(() => {
  if (interceptionActive.value) return 'pulse'
  if (
    isExecuting.value ||
    directRunning.value ||
    settling.value ||
    provisioning.value ||
    adapting.value ||
    analyzing.value ||
    safetyState.value !== 'idle' ||
    generationErrorMessage.value
  )
    return 'info'
  return 'idle'
})

const activeTarget = computed<NodeId | null>(() => {
  if (interceptionActive.value || currentStage.value === 'stage3') return 'gen'
  if (currentStage.value === 'stage4') return 'output'
  return null
})

// ---------- Page context: what this page is, and what lies on it now ----------
// The same spine every other view registers on (setPageContext -> formatForLLM).
// Without it the chat and the platform voice are handed a route path and
// nothing else, and the page gets described from nowhere.
const pageContext = computed<PageContext>(() => ({
  activeViewType: 'x2x_flow',
  pageDescription:
    'Der x2x-Fluss. Oben stehen drei Knoten nebeneinander: der erste Knoten (die sechs Medienzeichen Bild, Video, Klang, 3D, Code und Text, und das aufgelöste Modell; Text ist das eine Medium, das nicht erschlossen, sondern nur gewählt wird, und bedeutet, dass der Lauf das Material liest, statt etwas zu machen), Generieren (führt die Verwandlung aus und zeigt Prüfung, Fortschritt und Fehler) und Ausgabe (zeigt das fertige Medium). Der lange Druck liegt auf jedem der sechs Medienzeichen und öffnet die Modelle, die für dieses Medium eingetragen sind; bei Text stehen dort die fünf Deutungsrahmen statt eines Modells. In den Listen von Bild und Video stehen zusätzlich die Wege, die ein Bild als Eingang nehmen und dafür ein oder zwei Bilder auf dem Tisch verlangen. Ein Modell, das die Verfügbarkeitsabfrage als abwesend meldet, steht in der Liste und bleibt unwählbar. Sobald von Hand gewählt wurde, steht „auto" obenan in jeder dieser Listen und gibt die Wahl zurück; ein über Dateiwahl oder Ablegen hereingeholtes Bild gibt sie ebenfalls zurück, außer bei gewähltem Text, und eine Skizze gibt sie in jedem Fall zurück. Fehlen einer Hand-Wahl hier die Voraussetzungen — etwa ein Weg, der zwei Bilder verlangt, bei einem Bild auf dem Tisch —, tritt die automatische an ihre Stelle, und der Generieren-Knoten sagt im Ruhezustand, welche genommen wurde; 3D allein bleibt bestehen, weil es dorthin keinen zweiten Weg gibt: dann macht der Lauf zuerst das Bild und daraus das Gitter. Während der Generieren-Knoten läuft, zeigt er die Position in der Warteschlange, meist samt geschätzter Wartezeit, die Zahl der Schritte des Modells, den Fortschritt in Prozent und den Verbrauch, den die Grafikkarte währenddessen meldet, in Watt und Wattstunden, aufgeklappt zusätzlich in Gramm CO₂ — bei einem auswärtigen Dienst steht dort, dass es dafür keine Zahlen gibt, und bei Kompositionsläufen bleibt die Anzeige leer. Solange er aufgeklappt ist und ein lokales Bildmodell läuft, sagt er außerdem, dass die Wörter zu Zahlen werden, und bei einem zu langen Prompt, wie viele davon CLIP nie erreichen. Den Schritt von n zeigt der Ausgabe-Knoten. Ein langer Druck auf den Generieren-Knoten hält einen laufenden Lauf an. Darunter liegt der Tisch, verschieb- und zoombar, auf dem das Material frei liegt. Auf dem Tisch liegt ein grünes Plus; ein Klick darauf fächert die vier Wege auf, Material hereinzuholen — Text, Bild, Skizze, Dokument —, und was dabei entsteht, fällt dorthin, wo das Plus steht; das Plus selbst lässt sich verschieben. Ein Klick auf eine Bildkarte zeigt sie in voller Größe, ein langer Druck dreht sie auf ihre Rückseite; bei Klang und Video führt der Doppelklick zur vollen Größe, während der einfache Klick den Spieler bedient, und eine Quellenkarte öffnet mit einem Klick gleich ihre Rückseite. Eine Skizze öffnet sich zum Lesen, Ändern und erneuten Laufenlassen. Ein hereingeholtes Bild wird auf seinen Inhalt geprüft; ob eine Datei sich selbst als KI-erzeugt ausweist, steht auf der Rückseite der Karten, die aus einem Lauf dieser Plattform stammen. Was in der Zone liegt und beim Weg zum Modell übrig bleibt, wird für diesen Lauf in Worte gelesen und trägt dafür ein Zeichen; bei einem lesenden Lauf trägt überzähliger Text das Zeichen, dass er ungenutzt bleibt. Ergebnisse lassen sich herunterladen, Bilder auch drucken; Klang und Video lassen sich von der Ausgabe auf den Tisch ziehen, die übrigen fallen am Ende des Laufs von selbst dorthin. Sobald Material in der Zone liegt — dem Kreis auf dem Tisch —, liest der nächste Lauf nur die Zone; eine leere Zone liest den ganzen Tisch. Liegt Bild, Klang oder Video dort, steht neben der Zone eine Lupe: sie liest, was gerade gilt, statt etwas zu machen — ein Stück wird beschrieben, zwei werden verglichen, mehr werden nacheinander gelesen und aneinandergehängt; die Lupe liest ohne Perspektive, auch wenn eine im Kreis liegt. Ein pulsendes Zeichen auf dem Tisch öffnet die Perspektiven; eine Perspektive in der Zone wird im erzeugenden Lauf auf das angewendet, was aus dem Material an Worten geworden ist, mehrere nacheinander in der Reihenfolge, in der sie hineingelegt wurden. Eine Perspektive lässt sich auch selbst schreiben: ein Klick auf ihre Blase öffnet sie zum Lesen und Ändern, und wer angemeldet ist, legt sie unter einem Namen im eigenen Konto ab; eine bereits eigene lässt sich zusätzlich als zweite daneben stellen. Ein Lauf hält fest, welche Perspektive ihn eröffnet hat, und erkennt daran die eigene. Während der Prompt Interception kann eine Perspektive in Wikipedia nachschlagen; was sie fand, liegt danach als eigene Karte auf dem Tisch, die vorn das Wikipedia-Zeichen und den Suchbegriff trägt und auf der Rückseite Sprache, Grund des Nachschlagens, Artikel und Anfangs-Zusammenfassung. Medium und Modell werden aus dem Material erschlossen, nicht ausgewählt; eine Wahl von Hand überschreibt das und wird gehalten. Ein drittes Zeichen auf dem Tisch, ein biegsames Netz über einem starren Gitter, öffnet die LoRAs: Adapter, die über einem Bildmodell aus einer Reihe von Bildern trainiert sind und dessen Ausgabe in Richtung dieser Bilder verschieben, sobald ihr Trigger-Wort im Prompt steht. Angeboten wird, was das Register dieser Sitzung freigibt, in bis zu drei Gruppen: die der Plattform, die des Kurses und die eigenen Trainings; ist nichts freigegeben, sagt die Auswahl das. Das gewählte LoRA liegt als Kachel auf dem Tisch; liegt es in der Zone, lädt der nächste Lauf, der ein Bild macht, es unter dem Modell, das es trägt: die Automatik wählt dieses Modell (heute für jedes LoRA im Register Stable Diffusion 3.5 Large), der Knoten mit den Medienzeichen zeigt neben dem Modell das Netz, der Server stellt das Trigger-Wort dem Prompt voran, wo der Prompt es noch nicht trägt, und die Rückseite der fertigen Karte nennt unter „LoRA“ den Adapter mit seiner Stärke. Ein Klick auf die Kachel öffnet ihre Stärke, 50 bis 100 Prozent der trainierten, voreingestellt 80, daneben Trigger und tragende Modelle; das × entfernt sie. Eine Wahl von Hand bleibt stehen: kann das gewählte Modell das LoRA nicht laden, oder macht der Lauf kein Bild, bleibt die Kachel liegen und trägt das Fragezeichen „für diese Generierung nicht verwendet“; nichts wird unwählbar. Die Perspektive „Cooked Film“ bringt einen eigenen Adapter mit und trägt dafür das Netz an ihrer Blase; unter einem Modell, das ihn nicht trägt, dasselbe Fragezeichen. Welche LoRAs angeboten werden, steht im LoRA-Register der Einstellungen (Admin): Datei, Name, Trigger, tragende Modelle, Freigabe an die Plattform, an einen Kurs oder an niemanden; ein Training von der Seite LoRA Training wird dort eingetragen, bevor es irgendwo angeboten wird.',
  pageContent: {
    inputText: effCombinedText.value,
    interceptionResult: interceptionResult.value,
    selectedCategory: activeMedium.value,
    // Empty, not the UI word: this is the config slot, and a reading uses none.
    selectedConfig: willGenerate.value ? resolvedConfigLabel.value : '',
  },
}))

watch(
  pageContext,
  (ctx) => {
    pageContextStore.setPageContext(ctx)
  },
  { immediate: true, deep: true }
)

onBeforeUnmount(() => {
  pageContextStore.clearContext()
  // The companion's run is a module-level singleton. Left standing, it follows
  // the user to the next page and both answers about, and writes into, a run
  // that is no longer on screen.
  clearSession()
})

/**
 * The interception applies every bubble in the zone to what the zone reads —
 * one pass per bubble, in the order they entered, each pass a full
 * three-element interception (task instruction + bubble context + text).
 * No bubble in the zone: user_defined, which the backend owes the user verbatim
 * (meta.passthrough_when_context_empty) — except at the kids and youth filters,
 * where Stage 2 is mandatory and DOES rewrite the text.
 *
 * Whether a picture goes to the image model travels with every pass: it decides
 * whether the interception may write a scene of its own at all. Without it, an
 * instruction on a picture ("make a realistic vacation photo out of the drawing")
 * came back as an invented beach, and the image editor rendered the invention
 * instead of the drawing it was handed.
 */
async function runInterception(prompt: string, token: number): Promise<string> {
  const chain = zoneChain.value
  const onPicture = route.value.maxImages > 0
  // No perspective, no interception: the backend owes the text back verbatim,
  // and a box repeating the prompt box would name a step that did not happen.
  if (!chain.length) return runInterceptionStep(prompt, 'user_defined', '', '', onPicture)
  let text = prompt
  for (const b of chain) {
    // A chain let go of does not go on to the next perspective.
    if (!live(token)) return text
    text =
      (await runInterceptionStep(
        text,
        b.configId || 'user_defined',
        b.context || '',
        b.configName,
        onPicture,
        true
      )) || text
  }
  return text
}

/**
 * Every Stage 1+2 stream currently open, each as the one call that closes it.
 * A stop needs a handle on them: closing an EventSource is the only way to make
 * the model stop writing into a run the page has already let go of.
 */
const openInterceptions = new Set<() => void>()

/** One Stage 1+2 pass via SSE — resolves with the transformed text. */
function runInterceptionStep(
  prompt: string,
  schema: string,
  context: string,
  perspective: string,
  onPicture = false,
  // A pass under a perspective writes onto the table while it works. A pass
  // without one is a passthrough and has nothing of its own to show.
  onTable = false
): Promise<string> {
  return new Promise((resolve, reject) => {
    const card = onTable ? fallText('', 'interception') : null
    const feed = card ? feedInto(card) : null
    const base = ''
    const params = new URLSearchParams({
      schema,
      input_text: prompt,
      context_prompt: context,
      enable_streaming: 'true',
      device_id: deviceId,
    })
    // The text is an instruction on a picture the model gets with it.
    if (onPicture) params.set('image_input', 'true')
    interceptionRunId.value = null
    const es = new EventSource(`${base}/api/schema/pipeline/interception?${params.toString()}`)
    let acc = ''
    let done = false
    const drop = () => {
      if (done) return
      done = true
      es.close()
      openInterceptions.delete(drop)
      feed?.stop()
      closeStationCard(card)
      reject({ stopped: true })
    }
    openInterceptions.add(drop)
    es.addEventListener('connected', (ev: Event) => {
      try {
        interceptionRunId.value = JSON.parse((ev as MessageEvent).data).run_id || null
      } catch {
        /* ignore */
      }
    })
    es.addEventListener('stage_start', (ev: Event) => {
      try {
        interceptionModel.value = JSON.parse((ev as MessageEvent).data).model || ''
      } catch {
        /* ignore */
      }
    })
    es.addEventListener('chunk', (ev: Event) => {
      try {
        const part = JSON.parse((ev as MessageEvent).data).text_chunk || ''
        acc += part
        feed?.push(part)
      } catch {
        /* ignore */
      }
    })
    es.addEventListener('complete', () => {
      done = true
      es.close()
      openInterceptions.delete(drop)
      // The stream is over; the box goes on being written until the queue is
      // empty. The run does not wait for that -- the next station has its own
      // box, and the two fill beside each other.
      if (feed) void feed.finish(acc).then(() => closeStationCard(card))
      else closeStationCard(card)
      resolve(acc)
    })
    // A perspective may look things up while it reads — whitelist-only, on
    // Wikipedia — and what it finds goes into its reading. That happened
    // invisibly until now: the events were already on this stream, and nobody
    // listened. Each article lands beside the ring as a card of its own.
    es.addEventListener('wikipedia_lookup', (ev: Event) => {
      try {
        const d = JSON.parse((ev as MessageEvent).data)
        if (d?.status !== 'complete' || !Array.isArray(d.terms)) return
        for (const r of d.terms) {
          // Misses get a card too. The platform's own documentation promises
          // that a lookup shows what was searched for AND what was not found —
          // and after the transform modes were removed this card is the only
          // place any of it is visible.
          if (!r?.term) continue
          dropSource({
            term: String(r.term),
            title: String(r.title ?? r.term),
            url: r.success ? String(r.url ?? '') : '',
            extract: r.success ? String(r.extract ?? '') : '',
            lang: String(r.lang ?? ''),
            perspective,
            why: String(r.why ?? ''),
          })
        }
      } catch {
        /* a malformed lookup event is not worth breaking the run over */
      }
    })

    es.addEventListener('blocked', (ev: Event) => {
      done = true
      es.close()
      openInterceptions.delete(drop)
      let reason = ''
      try {
        reason = JSON.parse((ev as MessageEvent).data).reason || ''
      } catch {
        /* ignore */
      }
      feed?.stop()
      closeStationCard(card, false)
      reject({ blocked: true, reason })
    })
    es.onerror = () => {
      if (done) return
      done = true
      es.close()
      openInterceptions.delete(drop)
      feed?.stop()
      closeStationCard(card)
      reject(new Error('interception failed'))
    }
  })
}

/**
 * Which model did which step. Both are named by the backend now (the Stage-2
 * stage_start event, the adaption's response) instead of guessed here: a
 * surface that claims to show what is happening must not invent the actor.
 * Empty while nothing has run.
 */
const interceptionModel = ref('')
const adaptionModel = ref('')
/**
 * The text was longer than the model reads and was shortened before the
 * adaption wrote from it. The figure is what the shortened text costs at that
 * model's encoder; null when nothing was taken away. Said in the run band, and
 * nothing is asked.
 */
const condensedTokens = ref<number | null>(null)
/** The run had to read material into words before it could transform them. */
const materialWasRead = ref(false)

/** Stage 3, first half: the stance text is being reformulated for the model. */
const adapting = ref(false)
const analyzing = ref(false)
/** The interception's run — generation continues it, so one action is one record. */
const interceptionRunId = ref<string | null>(null)

const currentSeed = ref<number | null>(null)
const previousPrompt = ref('')
const previousConfig = ref('')
// Kept across a reload, with the board and the chain's memory below: these
// three are how the automatic tells a repeated press from a new one. Forgotten
// on a reload, the first press after it would draw the page's first seed for a
// prompt it has already drawn it for.
try {
  const stored = JSON.parse(sessionStorage.getItem('t2i_seed') || 'null')
  if (stored && typeof stored.prompt === 'string' && typeof stored.cfg === 'string') {
    currentSeed.value = typeof stored.seed === 'number' ? stored.seed : null
    previousPrompt.value = stored.prompt
    previousConfig.value = stored.cfg
  }
} catch {
  /* nothing kept */
}
watch([currentSeed, previousPrompt, previousConfig], ([seed, prompt, cfg]) => {
  try {
    sessionStorage.setItem('t2i_seed', JSON.stringify({ seed, prompt, cfg }))
  } catch {
    /* quota — the automatic keeps its books, they just will not survive a reload */
  }
})

// --- The same objects, unchanged: the chain is not asked again --------------
/**
 * What a press puts to the chain, as one string: the words and the pieces the
 * ring reads, and the perspectives on them in their order. Two presses with the
 * same string ask the chain the same question. What a run lays down falls
 * outside the ring, so the string stands after the run as it stood at the
 * press. A model or medium picked by hand is not in it: a pick changes what
 * the words are adapted FOR, which `ChainWritten.adapted.cfg` answers, and at
 * most how the ring is read, which `readingSig` answers.
 */
const ringSig = computed(() =>
  JSON.stringify({
    words: effTextItems.value.map((i) => [i.station || '', (i.text || '').trim()]),
    images: effImageItems.value.map((i) => [i.id, i.path || '']),
    audio: effAudioItems.value.map((i) => i.id),
    video: effVideoItems.value.map((i) => i.id),
    // The preset a perspective runs through, not the key it is kept under:
    // keeping one rewrites the key and nothing that reaches the model.
    chain: zoneChain.value.map((b) => [b.id, b.previewId || b.configId || '', b.context || '']),
  })
)
/**
 * How the ring is read, as one string: whether a picture goes to the model with
 * the words, and which pieces are read into words instead. Both follow the
 * route, and the route follows the medium, the pick and the count; the second
 * follows the ring's outline too. The route infers the medium from the
 * intercepted text as soon as there is one, so the string is taken once the
 * interception has written and compared under that same text: the next press
 * with the same ring reads it as the run left it.
 */
const readingSig = computed(() =>
  JSON.stringify({
    picture: route.value.maxImages > 0,
    read: [...readIntoWordsIds.value].sort(),
  })
)
/** What is picked by hand, as one string: the route follows it as it follows the ring. */
const pickSig = computed(() => (manualMedium.value ?? '') + '|' + (manualModel.value ?? ''))
/**
 * What the last chain was asked, and what it wrote. The same objects, unchanged
 * in the ring, do not send the chain off again: a press goes on with the prompt
 * the chain wrote last time, straight to the check and the inference, and the
 * seed automatic draws a new seed for it — one new inference. A
 * model picked since asks the adaption again, for that model, and nothing
 * before it: the interception has nothing to do with the model. A change in
 * the ring, however small, asks the whole chain again.
 */
type ChainWritten = {
  ringSig: string
  /**
   * The runs that went on with this memory: the one that wrote it, and every
   * press since that took its text. Their boxes are its boxes on the table, and
   * a refusal of one of their prompts is a refusal of its text.
   */
  runs: number[]
  /**
   * `readingSig` as the route read the ring once the interception had written:
   * what is read into words, and whether a picture goes with the words. A pick
   * that changes either asks the chain again. Taken THEN, not at the press: a
   * run's own text moves the route, and a string taken before it would compare
   * a text against its own transformation and deny the reuse on every press
   * whose words and transformation the route reads differently.
   */
  reading: string
  /** The words that went into the interception, readings included. */
  inputText: string
  /** What the interception wrote, whole: what `interceptionResult` holds. */
  intercepted: string
  /** The adaption of that for one model, once it has answered. */
  adapted: {
    cfg: string
    /** The intercepted text as it went on, shortened where the model's window asked for it. */
    transformed: string
    finalPrompt: string
    halves: { clip: string; t5: string } | null
    seedKey: string
  } | null
}
const lastChain = ref<ChainWritten | null>(null)
// Kept across a reload like the board itself: a new build reloads every open
// window, and the first press after it would otherwise ask the chain again
// for a ring that has not changed.
try {
  const stored = JSON.parse(sessionStorage.getItem('t2i_last_chain') || 'null')
  if (
    stored &&
    typeof stored.ringSig === 'string' &&
    typeof stored.reading === 'string' &&
    typeof stored.inputText === 'string' &&
    typeof stored.intercepted === 'string'
  ) {
    // An adaption short of a field is no adaption: gone on with, the press
    // would send a prompt that is not there. The interception stays.
    const a = stored.adapted
    const whole =
      a &&
      typeof a.cfg === 'string' &&
      typeof a.transformed === 'string' &&
      typeof a.finalPrompt === 'string' &&
      typeof a.seedKey === 'string' &&
      (a.halves === null ||
        (a.halves && typeof a.halves.clip === 'string' && typeof a.halves.t5 === 'string'))
    if (!whole) stored.adapted = null
    if (!Array.isArray(stored.runs) || !stored.runs.every((n: unknown) => typeof n === 'number'))
      stored.runs = []
    lastChain.value = stored
  }
} catch {
  /* nothing kept */
}
// Written out at once, not on the next flush: leaving the page voids the
// memory from its last hook, and the scope is stopped before a queued job
// would run.
watch(
  lastChain,
  (v) => {
    try {
      if (v) sessionStorage.setItem('t2i_last_chain', JSON.stringify(v))
      else sessionStorage.removeItem('t2i_last_chain')
    } catch {
      /* quota — the memory stays live, it just will not survive a reload */
    }
  },
  { deep: true, flush: 'sync' }
)
/** The ring holds what the last chain was asked: a press goes on with what it wrote. */
const chainWritten = computed<ChainWritten | null>(() => {
  const last = lastChain.value
  return last !== null && last.ringSig === ringSig.value && last.reading === readingSig.value
    ? last
    : null
})
/**
 * The pieces the next press reads into words, for the mark on them. A press
 * that goes on with the memory reads nothing: what these pieces say is in the
 * text it goes on with.
 */
const readMarkIds = computed<Set<string>>(() =>
  chainWritten.value ? new Set<string>() : readIntoWordsIds.value
)
/**
 * A box the memory's own runs laid down is still being written. Cut off now,
 * it would show less than the memory holds, and a press going on from the
 * memory would go on from words nobody can see on the table. A box of another
 * run's is cut off without the memory losing its text.
 */
function memoryBoxCut(): boolean {
  const last = lastChain.value
  if (!last) return false
  for (const id of cardFeeds.keys()) {
    const it = items.value.find((i) => i.id === id)
    if (it && it.run !== undefined && last.runs.includes(it.run)) return true
  }
  return false
}
/** The chain has written for this model: the next press with the same ring goes on with it. */
function keepAdapted(
  cfg: string,
  transformed: string,
  finalPrompt: string,
  halves: { clip: string; t5: string } | null,
  seedKey: string
) {
  const last = lastChain.value
  if (last) last.adapted = { cfg, transformed, finalPrompt, halves, seedKey }
}
// Changed and changed back — or reloaded — the ring is again what the last
// transformation describes: the inference reads that text, as it did right
// after the run. The text is watched too: on a reload the watcher that voids
// the text on a changed chain runs in the same flush as this one, in either
// order; run second, it clears what this one restored, and this one runs once
// more on the cleared text.
watch(
  [ringSig, interceptionResult],
  ([sig, text]) => {
    const last = lastChain.value
    if (last && last.ringSig === sig && last.intercepted && !text)
      interceptionResult.value = last.intercepted
  },
  { immediate: true }
)

// --- The run's handoff from the adaption to the model, and the hold on the
// generate node that lets go of a running run ------------------------------
type ImageArgs = {
  input_image?: string
  input_image1?: string
  input_image2?: string
  input_image3?: string
}
type RunHandoff = {
  /**
   * What the seed automatic compares this run against, where that differs from
   * the words that go. Empty means the words that go ARE the yardstick.
   */
  seedKey: string
  cfg: string
  imageArgs: ImageArgs
  inputText: string
  transformed: string
  plan: (typeof composition)['value']
  original: string
  /**
   * The frame this run is to be read in once its object exists, or null when
   * the run makes something and that is all. '' is a reading without a frame.
   */
  readFrame: string | null
  /** What was in the ring when this run was started (see finishRun). */
  born0: RunOrigin
}
let stopHoldFired = false

/**
 * A message judges the board as it was. Change the board and the judgement is
 * answered: keeping it would show an old state over the current one — and,
 * because any message keeps the box in its info face, it would take the start
 * control with it and leave nothing to press.
 *
 * The source is the BOARD, and nothing else. `busy` stood in it until
 * 2026-09-05, so that the clearing could be deferred until a run let the box
 * go — and the FALL of `busy` then swept away the judgement that same run had
 * just written. `runMusic` set `blocked` with its reason and its stage, its
 * `finally` lowered `directRunning` one line further down, and by the time the
 * call returned `safetyState` read `idle`, the reason was empty and the surface
 * showed none of it. `failRun` and the torn connection went the same way, and
 * `runCompose` has the same shape. The main path survived only by ORDER —
 * `isExecuting` falls inside `executeWithStreaming`, before `finishRun` writes
 * anything — which is a property of another file, not of this one.
 *
 * With `busy` out of the source no run state can clear a judgement on any path,
 * by design rather than by ordering. It stands until the board really changes,
 * or until the next run, which every entry point clears for itself (beginRun,
 * and the three run functions). Read in the BODY it still holds a run in flight
 * apart from a finished one: `safetyState` reads `running` and `passed` off the
 * stages as they pass, and those belong to the run rather than to the table.
 */
watch(
  () => [
    resolvedConfigId.value,
    readCount.value,
    effCombinedText.value.trim().length,
    zoneChain.value.length,
  ].join('|'),
  () => {
    if (busy.value) return
    generationErrorMessage.value = ''
    // A refused run judges the board too, and holds the box exactly as an error
    // does. Left standing it hides the reason the NEXT run cannot start.
    safetyState.value = 'idle'
    blockedReason.value = ''
    blockedStage.value = null
  }
)

function onGenClick() {
  // A hold that has just stopped a run ends in a click on this same box.
  if (stopHoldFired) {
    stopHoldFired = false
    return
  }
  void runGenerate()
}

/**
 * What pressing this box does next, written under the triangle. A run with a
 * perspective in the ring makes a prompt first; one without has nothing to
 * intercept and goes straight to the adaption for the chosen medium. Empty
 * while the run is working: naming an act that cannot be taken would be an
 * offer.
 */
const runCaption = computed(() => {
  if (busy.value || !willGenerate.value) return ''
  // The chain was asked exactly this and has written for the model this press
  // goes to: the press goes on with its prompt. A press that takes the music
  // path or only lays pieces together goes through no chain and has no use for
  // what one wrote.
  const written =
    route.value.outputConfigId === HEARTMULA || composition.value?.generate === null
      ? null
      : chainWritten.value
  if (written && written.adapted && written.adapted.cfg === runConfigId.value)
    return t('x2xFlow.runCapGenerate', { medium: mediumLabel(activeMedium.value) })
  // A box from an earlier run lies in the ring: the press takes the chain up
  // where that box stands, and says so.
  if (zoneStation.value === 'adaption')
    return t('x2xFlow.runCapGenerate', { medium: mediumLabel(activeMedium.value) })
  if (zoneStation.value === 'interception')
    return t('x2xFlow.runCapAdapt', { medium: mediumLabel(activeMedium.value) })
  // The interception holds; a model picked since asks the adaption for it.
  if (written) return t('x2xFlow.runCapAdapt', { medium: mediumLabel(activeMedium.value) })
  return zoneChain.value.length
    ? t('x2xFlow.runCapMake')
    : t('x2xFlow.runCapAdapt', { medium: mediumLabel(activeMedium.value) })
})

/**
 * Holding the box stops what the box started. The gesture used to START a run
 * held at the prompt; the halt is gone since 2026-09-03, which leaves the hold
 * for the one thing a running box has no room to offer.
 */
const HOLD_MS = 800
/** How far the pointer may travel before the hold counts as given up. */
const HOLD_SLIP = 12
const holdOn = ref(false)
const holdPct = ref(0)
const genStopping = ref(false)
let stopHoldTimer: ReturnType<typeof setTimeout> | null = null
let stopHoldRaf: number | null = null
let stopHoldStart = 0
let stopHoldX = 0
let stopHoldY = 0
/** The box the hold captured the pointer to, so the capture can be given back. */
let holdEl: Element | null = null
let holdPid = -1

const canAbortGen = computed(
  // Holding is the one gesture on this box that lets go of a run.
  () => busy.value && !genStopping.value
)

function startStopHold(e: PointerEvent) {
  // A gesture that ran its course may end nowhere near this box — it shrinks
  // back to its small shape the moment the run ends — so the click that would
  // have cleared the flag never arrives. The next press clears it instead.
  stopHoldFired = false
  // Only the primary button. A right press opens the context menu, which eats
  // the release, and the run would stop under the open menu.
  if (e.button !== 0 || !canAbortGen.value) return
  endStopHold()
  holdOn.value = true
  stopHoldX = e.clientX
  stopHoldY = e.clientY
  stopHoldStart = performance.now()
  // The box changes its own size while a run proceeds — it pulls itself open
  // over its neighbours and back again. Without capture it would slide out from
  // under a perfectly still finger and the hold would be dropped for nothing.
  holdEl = e.currentTarget as Element
  holdPid = e.pointerId
  try {
    holdEl.setPointerCapture(holdPid)
  } catch {
    holdEl = null
  }
  // The clock decides, not the frames: a window that has stopped painting
  // still counts down, so the gesture cannot stall halfway with the box held.
  stopHoldTimer = setTimeout(() => {
    endStopHold()
    // The gesture completed, whatever became of the run. The release that
    // follows belongs to it and must not start anything.
    stopHoldFired = true
    // Asked again here: a run that finished in between is not one to stop.
    if (canAbortGen.value) void abortGeneration()
  }, HOLD_MS)
  const step = (now: number) => {
    stopHoldRaf = null
    if (!holdOn.value) return
    holdPct.value = Math.min(1, (now - stopHoldStart) / HOLD_MS)
    if (holdPct.value < 1) stopHoldRaf = requestAnimationFrame(step)
  }
  stopHoldRaf = requestAnimationFrame(step)
}

function moveStopHold(e: PointerEvent) {
  if (!holdOn.value) return
  // Leaving is measured as travelled distance, not as a boundary crossing: the
  // box may move under a still pointer, and a still pointer has not let go.
  if (Math.hypot(e.clientX - stopHoldX, e.clientY - stopHoldY) > HOLD_SLIP) endStopHold()
}

function endStopHold() {
  if (holdEl) {
    try {
      if (holdEl.hasPointerCapture(holdPid)) holdEl.releasePointerCapture(holdPid)
    } catch {
      /* the pointer is already gone */
    }
    holdEl = null
  }
  if (stopHoldTimer !== null) {
    clearTimeout(stopHoldTimer)
    stopHoldTimer = null
  }
  if (stopHoldRaf !== null) {
    cancelAnimationFrame(stopHoldRaf)
    stopHoldRaf = null
  }
  holdOn.value = false
  holdPct.value = 0
}

/**
 * Which run is the current one. Four things on this page can be running — a
 * reading, a perspective chain into a generation, a composition, a song — and
 * every one of them is a chain of awaits that ends in a write to the panel or a
 * piece falling on the table. A stop moves this number on; each step checks it
 * again before it writes, finds itself let go of, and writes nothing.
 *
 * Without it a stopped run still finished: it said "Stopped." and then laid the
 * picture on the table anyway, and its last step cleared a flag that by then
 * belonged to the run after it.
 */
let genRun = 0
/** Is the run this number belongs to still the one the page is showing? */
const live = (token: number) => token === genRun
/** A run begins: the last one's word is cleared and the next number taken. */
function beginRun(): number {
  generationErrorMessage.value = ''
  genStopped.value = false
  readingRun.value = false
  runResume.value = null
  sourceSlot = 0
  return ++genRun
}
/** This run reads and makes nothing. Set by runAnalysisOnly, cleared above. */
const readingRun = ref(false)
/**
 * What that reading was, frozen when it began. Not createLabel: that one is a
 * live reading of the board, so pulling one of two pictures off the table after
 * a comparison would relabel the finished run a description.
 */
const readingLabel = ref('')
/** Which place below the ring the next source card takes. Per run, not per board. */
let sourceSlot = 0
/** The last message came from the user stopping, not from something failing. */
const genStopped = ref(false)

/** Everything this page was still holding for a run it has let go of. */
function stopRunHere() {
  interceptionActive.value = false
  analyzing.value = false
  adapting.value = false
  // A box of the memory's own is cut off mid-word by this stop, and a press
  // going on from the full text would go on from words nobody can see on the
  // table. The next press asks the chain again and writes the box whole.
  if (memoryBoxCut()) lastChain.value = null
  directRunning.value = false
  safetyState.value = 'idle'
  // The perspective's own stream is not the generation stream and nothing else
  // closes it: left open it runs the whole chain to the end, one paid model call
  // per remaining perspective, and writes its result over the next run.
  for (const drop of [...openInterceptions]) drop()
  for (const feed of [...cardFeeds.values()]) feed.stop()
  resetStream()
  genStopping.value = false
  genStopped.value = true
  generationErrorMessage.value = t('x2xFlow.stopped')
}

/**
 * A generation can only be ASKED to stop, and the backend can only answer once
 * it holds something — which is stage 4. Before that the question has no
 * addressee, and there are two of them:
 *
 * the run is still in this page's own steps (reading the material, the
 * perspective, the adaption, or waiting at the prompt) — then it is stopped
 * here, completely and at once;
 *
 * the run is already in the stream but stage 3 is still running — then nothing
 * can be taken back yet, and the question is simply repeated until stage 4 can
 * hear it. The box keeps saying it is stopping, because it is.
 *
 * Past the picture, the picture exists: the run reports what became of it where
 * it resolves, and a finished piece is never thrown away for a late stop.
 */
async function abortGeneration() {
  if (genStopping.value) return
  genStopping.value = true
  const token = genRun
  const asked = await cancelGeneration(deviceId)
  // Taken, and it is this page's own stream that was taken: the run says what
  // became of it where it resolves, and clears the word "stopping" there.
  if (asked && live(token) && isExecuting.value) return
  // Not taken, and the run is already in the stream: stage 3 is running and
  // there is still nothing at the backend to take back. Ask again until stage 4
  // can hear it. The box keeps saying it is stopping, because it is.
  if (!asked && live(token) && isExecuting.value) {
    while (live(token) && isExecuting.value && genStopping.value) {
      await new Promise((r) => setTimeout(r, 400))
      if (!live(token) || !isExecuting.value) break
      if (await cancelGeneration(deviceId)) return
    }
  }
  // Everything else is stopped here: a run that never reached the backend, and
  // one whose cancel took something the page is not watching. A run that ended
  // on its own in the meantime is not stopped — what it brought back stands.
  if (live(token) && busy.value) {
    genRun++
    stopRunHere()
  } else {
    genStopping.value = false
  }
}
/**
 * The run goes from the adaption to its model. Some models are spoken to in
 * two halves: a short caption both CLIP encoders read through their 77-token
 * window, and the long form for T5. With a caption, the two halves go as two
 * halves. Without one (the adaption wrote none for this text) the text goes on
 * its own. It must NOT be given a caption cut from its own opening: the backend
 * puts the caption in front of what T5 reads, so a text of its own first words
 * would arrive saying its beginning twice.
 *
 * Everything that stands after this, finishRun and the wordful reading that
 * makes its object first, hangs off here.
 */
async function sendRun(run: RunHandoff, text: string, caption: string) {
  const longForm = text.trim()
  genStopped.value = false
  generationErrorMessage.value = ''
  const token = ++genRun
  let sendPrompt = longForm || run.original
  if (caption && longForm) sendPrompt = JSON.stringify({ clip: caption, t5: longForm })
  const made = await finishRun(
    sendPrompt,
    run.cfg,
    run.imageArgs,
    run.inputText,
    run.transformed,
    run.plan,
    token,
    run.born0,
    run.seedKey
  )
  // A reading is still a reading: the object was made with these words, and
  // the frame it was asked for reads exactly it.
  if (run.readFrame !== null && made && live(token)) await readMade(made, run.readFrame, token)
}

/**
 * The halves as the BACKEND read them. It takes the adaption apart for its own
 * use and hands the result back beside the raw text; reading that raw text a
 * second time here, with a parser that knows less than the one that already
 * did the work, is how a page ends up showing braces where it promised a text.
 */
function readHalves(j: any): { clip: string; t5: string } | null {
  const tp = j?.triple_prompt
  const clip = typeof tp?.clip === 'string' ? tp.clip.trim() : ''
  const t5 = typeof tp?.t5 === 'string' ? tp.t5.trim() : ''
  return clip && t5 ? { clip, t5 } : null
}

/**
 * The caption for the text that is actually going. Asked of the same adaption
 * that wrote the first one, so it is made the same way — only from the edited
 * text this time. Empty when this text has no two-part form: then it goes on
 * its own, and the model reads it whole.
 */
async function recaption(longForm: string, cfg: string): Promise<string> {
  try {
    // Streamed, not awaited in one silent POST: a cloud model writes this
    // caption, and where it answers per encoder a second call fits the long
    // half to the encoder window — while the edge in front of this server cuts
    // a request whose origin has sent nothing for about 100 seconds. Every
    // status resolves, because the caption below is taken out of the body
    // whatever the status was, which is how this call already read it.
    const res = await postStreamedRun('/api/schema/pipeline/optimize', {
      input_text: longForm,
      output_config: cfg,
    }, { validateStatus: () => true })
    return readHalves(res.data)?.clip || ''
  } catch {
    return ''
  }
}
/** Every consumed piece is analyzed by its modality model, labeled in table order. */
/**
 * One picture, read — through a frame when one is in force. Empty when nothing
 * came back. Both readings go through here: the one over the ring, and the one
 * over a picture the flow has just made for itself.
 */
async function readOneImage(path: string, lang?: string, frame = ''): Promise<string> {
  try {
    // Streamed, not awaited in one silent POST: a vision model has to be loaded
    // before it can look and may stand in the card's queue first, and the edge
    // in front of this server cuts a request whose origin has sent nothing for
    // about 100 seconds. Every status resolves, because the reading below is
    // taken out of the body whatever the status was.
    const res = await postStreamedRun('/api/media/analyze/image', {
      image_path: path,
      ...(lang ? { lang } : {}),
      ...(frame ? { frame } : {}),
    }, { validateStatus: () => true })
    const j = res.data
    return j?.success && typeof j.analysis === 'string' ? j.analysis.trim() : ''
  } catch {
    // Empty means "not read", and every caller already says that out loud. An
    // exception here would leave runGenerate through the back door instead.
    return ''
  }
}

/**
 * The intercepted text is a stance, not yet a media prompt: the output config's
 * own adaption instruction reformulates it for the model, and without this step
 * the generation never carries the perspective. THE one place that asks for it.
 *
 * It throws no box for itself: what it writes is a caption for one encoder,
 * and the text a person works with is the interception's, which lies on the
 * table already. A box falls where the text had to be SHORTENED to the model's
 * window — there something was taken away, and the box says in its bar what and
 * how far.
 *
 * Returns null only when the run is no longer this page's; the caller stops
 * then. An adaption that failed comes back with an empty prompt, and the stance
 * text goes as it stands.
 */
async function adaptFor(
  text: string,
  cfg: string,
  token: number,
  // The picture this model will be handed. False where there is none to hand —
  // and false for the intermediate picture a 3d run makes for itself, which is
  // asked of a text-to-image model precisely because no picture exists yet.
  onPicture = false
): Promise<{
  prompt: string
  halves: { clip: string; t5: string } | null
  /** The intercepted text as it was shortened, where it had to be. */
  condensed: string
} | null> {
  adapting.value = true
  try {
    // Streamed, for the reason recaption gives — and this one is asked for on
    // EVERY run, so the 100 seconds stood between every generation and its
    // answer.
    const res = await postStreamedRun('/api/schema/pipeline/optimize', {
      input_text: text,
      output_config: cfg,
      ...(onPicture ? { has_input_image: true } : {}),
    }, { validateStatus: () => true })
    const j = res.data
    if (!live(token)) return null
    if (typeof j?.model === 'string') adaptionModel.value = j.model
    condensedTokens.value =
      j?.shortened_to_window === true && typeof j.condensed_tokens === 'number'
        ? j.condensed_tokens
        : null
    // The text was longer than this model reads and was shortened before the
    // adaption wrote from it. Words were taken away, so the shortened text goes
    // on the table under a bar that says exactly that, with the figure it can
    // be checked against.
    const condensed =
      j?.shortened_to_window === true && typeof j.condensed_text === 'string'
        ? j.condensed_text.trim()
        : ''
    if (condensed) {
      const box = fallText(
        '',
        'adaption',
        t('x2xFlow.runCondensed', { n: condensedTokens.value ?? 0 })
      )
      const feed = feedInto(box)
      feed.push(condensed)
      void feed.finish(condensed).then(() => closeStationCard(box))
    }
    if (j?.unchanged === true) {
      const plain =
        j?.success && typeof j.optimized_prompt === 'string' && j.optimized_prompt.trim()
          ? j.optimized_prompt.trim()
          : ''
      return { prompt: plain, halves: null, condensed }
    }
    const p =
      j?.success && typeof j.optimized_prompt === 'string' && j.optimized_prompt.trim()
        ? j.optimized_prompt.trim()
        : ''
    return { prompt: p, halves: readHalves(j), condensed }
  } catch {
    return { prompt: '', halves: null, condensed: '' }
  } finally {
    if (live(token)) adapting.value = false
  }
}

/** The object exists; now it is read. */
async function readMade(path: string, frame: string, token: number) {
  analyzing.value = true
  try {
    const text = await readOneImage(path, undefined, frame)
    if (!live(token)) return
    if (text) fallText(text)
    else generationErrorMessage.value = t('x2xFlow.errAnalyze')
  } finally {
    if (live(token)) analyzing.value = false
  }
}

async function analyzeEffectiveMedia(
  lang?: string,
  // The reading frame, empty for the plain reading. It reaches the image route
  // only: the frames are methods of image interpretation, and sound and video
  // have none, so those two are read as they always were.
  frame = '',
  // The pieces to read, when it is only some of them: a run that generates
  // reads exactly what its route leaves over (readIntoWordsItems). Left out,
  // everything effective in the ring is read.
  only?: { images: AsmItem[]; audio: AsmItem[]; video: AsmItem[] }
): Promise<{ label: string; text: string }[]> {
  const parts: { label: string; text: string }[] = []
  const srcs = (only ? only.images : effImageItems.value)
    .map((i) => i.path)
    .filter(Boolean) as string[]
  for (let i = 0; i < srcs.length; i++) {
    const text = await readOneImage(srcs[i]!, lang, frame)
    if (text) parts.push({ label: `Image ${i + 1}`, text })
  }
  const avKinds: ['audio' | 'video', AsmItem[]][] = [
    ['audio', only ? only.audio : effAudioItems.value],
    ['video', only ? only.video : effVideoItems.value],
  ]
  for (const [kind, list] of avKinds) {
    for (let i = 0; i < list.length; i++) {
      const runId = list[i]?.runId
      if (!runId) continue
      // Streamed, for the reason readOneImage gives: the listening model is
      // loaded on first use and a clip is as long as it is.
      const res = await postStreamedRun('/api/media/analyze/av', {
        run_id: runId, kind, ...(lang ? { lang } : {}),
      }, { validateStatus: () => true })
      const j = res.data
      if (j?.success && typeof j.analysis === 'string' && j.analysis.trim()) {
        const cap = kind === 'audio' ? 'Audio' : 'Video'
        parts.push({ label: `${cap} ${i + 1}`, text: j.analysis.trim() })
      }
    }
  }
  return parts
}

function joinAnalyses(parts: { label: string; text: string }[]): string {
  return parts.length === 1
    ? parts[0]!.text
    : parts.map((p) => `${p.label}: ${p.text}`).join('\n\n')
}

/**
 * Text falls onto the table exactly as a finished picture, sound or sketch does
 * -- the same ejection (fallImage / fallMedia / fallCode), in text shape. Three
 * things come out this way: a reading, the reading a perspective made, and the
 * adaption made of that for the model. `station` is what the box then calls
 * itself in its bar; without one it is an ordinary prompt box.
 */
function fallText(text: string, station?: AsmItem['station'], title?: string): AsmItem {
  const p = station ? stationPoint(340, 240) : fallPoint(340, 240)
  const it = addText(p.x, p.y)
  it.text = text
  it.w = 340
  it.h = 240
  it.fell = true
  if (station) {
    it.station = station
    it.run = runOrdinal.value
  }
  if (title) it.title = title
  return it
}

/**
 * Which run this is on this board. Every box a run lays down is stamped with
 * it, so the reading a perspective made and the adaption made of it are legible
 * as one run's work — and as a different run's than the three boxes beside
 * them.
 */
const runOrdinal = ref(0)
// Kept across a reload with the boxes it stamps: they come back with their
// numbers, and the chain's memory names its runs by them. Counted from nought
// again, a new run would carry the number of an old box.
try {
  const stored = Number(sessionStorage.getItem('t2i_run_ordinal'))
  if (Number.isInteger(stored) && stored > 0) runOrdinal.value = stored
} catch {
  /* nothing kept */
}
watch(runOrdinal, (n) => {
  try {
    sessionStorage.setItem('t2i_run_ordinal', String(n))
  } catch {
    /* quota — the count goes on, it just will not survive a reload */
  }
})

/**
 * Material alone in the circle, wordless, without a perspective: the run
 * reads instead of making. One piece is described by its modality model; two
 * are read comparatively (the Compare-Mode gesture) -- per-piece analyses,
 * then one text reads them side by side. The reading falls beside the zone
 * as editable text: material for the next run, under the fell rule.
 */
async function runAnalysisOnly() {
  const token = beginRun()
  readingRun.value = true
  // The comparison runs at exactly two pieces (see below). Three are read one
  // after another, and calling that a comparison would name something the run
  // does not do.
  readingLabel.value = t(readCount.value === 2 ? 'x2xFlow.readsTwo' : 'x2xFlow.readsOne')
  blockedReason.value = ''
  blockedStage.value = null
  safetyState.value = 'idle'
  analyzing.value = true
  startEnergy()
  try {
    const single =
      effImageItems.value.length +
        effAudioItems.value.length +
        effVideoItems.value.length ===
      1
    // The reading is for the table: it appears in the system language. The
    // generation path keeps the English original (mediaOnly passes no lang).
    const frame = readingFrame.value
    // `lang: 'system'` asks the backend to translate the reading into the
    // instance language. A framed prompt already writes in it, so asking again
    // would send the text through a model a second time, for nothing, and let
    // it change on the way.
    const parts = await analyzeEffectiveMedia(single && !frame ? 'system' : undefined, frame)
    if (!live(token)) return
    if (!parts.length) {
      generationErrorMessage.value = t('x2xFlow.errAnalyze')
      return
    }
    let text = joinAnalyses(parts)
    if (parts.length === 2) {
      // A failed comparison still leaves both readings on the table.
      try {
        // Streamed, for the reason readOneImage gives: one model call with
        // two whole readings in the prompt, and a translation after it.
        const res = await postStreamedRun('/api/media/analyze/compare', {
          parts, lang: 'system', ...(frame ? { frame } : {}),
        }, { validateStatus: () => true })
        const j = res.data
        if (j?.success && typeof j.comparison === 'string' && j.comparison.trim()) {
          text = j.comparison.trim()
        }
      } catch {
        /* keep the joined analyses */
      }
      if (!live(token)) return
    }
    fallText(text)
  } finally {
    // Only this run's own flag: cleared blindly, it would clear the flag of the
    // run that started after this one was let go of.
    if (live(token)) analyzing.value = false
  }
}

/**
 * While the language steps run, the middle box is the one thing happening, and
 * it takes the room of all three: it pulls itself open over its neighbours and
 * shows the run station by station. When the denoising starts it lets go again,
 * because from there on the picture belongs in the box on the right.
 */
const GEN_WIDE: FlowRect = {
  x: RMAP.create.x,
  y: RMAP.gen.y,
  w: RMAP.output.x + RMAP.output.w - RMAP.create.x,
  // Taller than a node: six stations with three lines each do not fit into a
  // node's height. The stage clips at its world box, so .fl-map is opened for
  // this page — the pulled box reaches a little way over the canvas and takes
  // that room back when it retracts.
  h: 170,
}
const genExpanded = computed(
  () =>
    analyzing.value ||
    interceptionActive.value ||
    adapting.value ||
    currentStage.value === 'stage3' ||
    (currentStage.value === 'stage4' && generationProgress.value === 0)
)

/**
 * The last two moments, named where they happen: the steps push the noise
 * toward the words, then the decoder turns the numbers into pixels. Only the
 * diffusers backend reports steps — elsewhere this line stays empty.
 */
const outPhase = computed(() => {
  if (currentStage.value !== 'stage4' || genTotalSteps.value <= 0) return ''
  return genStep.value >= genTotalSteps.value
    ? t('x2xFlow.outDecode', { medium: mediumLabel(activeMedium.value) })
    : t('x2xFlow.outStep', { k: genStep.value, n: genTotalSteps.value })
})
const genRect = computed<FlowRect>(() => (genExpanded.value ? GEN_WIDE : RMAP.gen))
/**
 * The card's own figures, read live from nvidia-smi while a run is on it. The
 * attribution is deliberately modest: this is what the card draws right now,
 * not what this run alone costs — the box is shared, and a cloud step draws
 * nothing here at all. Formulas are the platform's own (useAnimationProgress,
 * resona_hardware): Wh/s = W / 3600, g CO2 = Wh / 1000 * 400 (German grid).
 */
const CO2_PER_KWH_GRAMS = 400
const gpuWatts = ref<number | null>(null)
const runWh = ref(0)
let energyTimer: ReturnType<typeof setInterval> | null = null
let energyLast = 0

async function pollEnergy() {
  try {
    const res = await fetch('/api/settings/gpu-realtime')
    const j = await res.json()
    const now = Date.now()
    const dt = Math.max(0, (now - energyLast) / 1000)
    energyLast = now
    if (j?.available && typeof j.power_draw_watts === 'number' && j.power_draw_watts > 0) {
      gpuWatts.value = j.power_draw_watts
      runWh.value += (j.power_draw_watts * dt) / 3600
    } else {
      gpuWatts.value = null
    }
  } catch {
    gpuWatts.value = null
  }
}
function startEnergy() {
  runWh.value = 0
  gpuWatts.value = null
  energyLast = Date.now()
  if (energyTimer) return
  void pollEnergy()
  energyTimer = setInterval(() => void pollEnergy(), 2000)
}
function stopEnergy() {
  if (energyTimer) clearInterval(energyTimer)
  energyTimer = null
}
onBeforeUnmount(stopEnergy)
// A run that has come to rest stops the meter; the last figures stay readable.
// This sits here, not up beside canRun: watch() reads its source once during
// setup, and `busy` reaches forward to refs declared further down.
watch(busy, (b) => {
  if (!b) stopEnergy()
})

const runCo2 = computed(() => (runWh.value / 1000) * CO2_PER_KWH_GRAMS)
const energyLine = computed(() =>
  gpuWatts.value === null
    ? ''
    : t('x2xFlow.runEnergy', {
        w: Math.round(gpuWatts.value),
        wh: runWh.value.toFixed(2),
        co2: runCo2.value.toFixed(2),
      })
)
/** The same reading for the small card, where a sentence would crowd it out. */
const energyShort = computed(() =>
  gpuWatts.value === null
    ? ''
    : t('x2xFlow.runEnergyShort', {
        w: Math.round(gpuWatts.value),
        wh: runWh.value.toFixed(2),
      })
)

/**
 * Which model ran a step, and where it ran. The reading itself is the
 * platform's and stands in lib/modelPlace.ts: the Latent Lab's bar says the
 * same sentence over its own runs, and a second copy of it here is the parallel
 * structure docs/ELEMENT_STRUCTURE_REGISTRY.md forbids. Only `t` is added,
 * which this page has and that module deliberately does not.
 */
function modelLine(m: string): string {
  return sharedModelLine(m, t)
}
/** The step running right now — a cloud step means the card here measures nothing. */
const liveModel = computed(() => {
  if (analyzing.value) return ''
  if (interceptionActive.value) return interceptionModel.value
  if (adapting.value) return adaptionModel.value
  return adaptionModel.value || interceptionModel.value
})
/**
 * Where the step now running happens. Stage 4 is its own question: the language
 * steps before it may have run at a provider, but the picture is made by the
 * backend the output config names — and all of those except the two API image
 * backends run on this machine.
 */
const CLOUD_MEDIA_BACKENDS = ['openai', 'mammouth', 'anthropic', 'google', 'gemini']
const liveIsCloud = computed(() => {
  if (currentStage.value === 'stage4') {
    const m = modelMeta.value as Record<string, any> | null
    const b = String(m?.backend_type || m?.backend || '').toLowerCase()
    return CLOUD_MEDIA_BACKENDS.includes(b)
  }
  return !!liveModel.value && !liveModel.value.startsWith('local/')
})

const materialLine = computed(() => {
  const parts: string[] = []
  const add = (key: string, n: number) => {
    if (n > 0) parts.push(`${t(key)} ${n}`)
  }
  add('x2xFlow.runKindText', effTextItems.value.length)
  add('x2xFlow.runKindImage', effImageItems.value.length)
  add('x2xFlow.runKindSound', effAudioItems.value.length)
  add('x2xFlow.runKindVideo', effVideoItems.value.length)
  return parts.join(' \u00b7 ') || t('x2xFlow.runNothing')
})

/**
 * What the three text encoders actually took in. CLIP's window closes after 77
 * pieces, T5 reads on to 512 — so on a long prompt the tail reaches T5 and
 * never reaches CLIP. The numbers come from the GPU service, which tokenizes
 * the prompt with the model's own tokenizers; nothing here is estimated.
 */
interface EncoderStat {
  line: string
  cut: number
  max: number
}
const encoderStat = computed<EncoderStat | null>(() => {
  const e = encodingInfo.value
  if (!e) return null
  const parts: string[] = []
  let cut = 0
  let max = 0
  for (const [key, label] of [
    ['clip_l', 'CLIP-L'],
    ['clip_g', 'CLIP-G'],
    ['t5', 'T5'],
  ] as const) {
    const d = e[key]
    if (!d || typeof d.count !== 'number') continue
    const total = typeof d.total_count === 'number' ? d.total_count : d.count
    parts.push(`${label} ${d.count}/${total}`)
    if (d.truncated) {
      cut = Math.max(cut, total - d.count)
      max = Math.max(max, typeof d.max === 'number' ? d.max : 0)
    }
  }
  return parts.length ? { line: parts.join(' \u00b7 '), cut, max } : null
})

interface RunStation {
  id: string
  label: string
  detail: string
  note: string
  state: 'todo' | 'live' | 'done'
  /** One figure, held to the foot of the box and set in tabular numbers. */
  time?: string
  /** Carries more figures than a station's equal share can hold. */
  wide?: boolean
}

/** The run, station by station, each saying as precisely as it can what it is. */
const runStations = computed<RunStation[]>(() => {
  const out: RunStation[] = []
  const s3 = currentStage.value === 'stage3'
  const s4 = currentStage.value === 'stage4'
  const perspectives = chainLabel.value || t('x2xFlow.runPerspectiveNone')
  out.push({
    id: 'read',
    label: t('x2xFlow.runRead'),
    detail: materialLine.value,
    note: perspectives,
    state: 'done',
  })
  if (materialWasRead.value || readingRun.value) {
    out.push({
      id: 'analyse',
      label: t('x2xFlow.runAnalyse'),
      detail: materialLine.value,
      note: '',
      state: analyzing.value ? 'live' : 'done',
    })
  }
  // A reading makes no medium: no perspective is applied, nothing is adapted
  // for a model, no check runs and no model is reached. Naming those stations
  // would announce four steps of a run that is already over.
  if (readingRun.value) return out
  // An adaption from an earlier run lies in the ring: this run intercepts
  // nothing and adapts nothing — both were done before it began, and naming
  // the two stations would announce steps this run never walks. An
  // interception in the ring keeps both: the station stands there done,
  // because it is, and the adaption is exactly what this run is for.
  if (runResume.value !== 'adaption') {
    out.push({
      id: 'interception',
      label: t('x2xFlow.runInterception'),
      detail: perspectives,
      note: modelLine(interceptionModel.value),
      state: interceptionActive.value ? 'live' : interceptionResult.value ? 'done' : 'todo',
    })
    out.push({
      id: 'adaption',
      label: t('x2xFlow.runAdaption'),
      // A shortening took words away, so it is said here too.
      detail: condensedTokens.value
        ? t('x2xFlow.runCondensed', { n: condensedTokens.value })
        : '',
      // The model DOING this step, as at every other station on this band. The
      // model the text is adapted FOR belongs to the making and stands there.
      note: modelLine(adaptionModel.value),
      state: adapting.value ? 'live' : lastSubmittedPrompt.value ? 'done' : 'todo',
    })
  }
  out.push({
    id: 'check',
    label: t('x2xFlow.runCheck'),
    detail: safetyChecks.value.length ? safetyChecks.value.join(' \u00b7 ') : '',
    note: modelLine(stage3Model.value),
    state: s3 ? 'live' : s4 || safetyState.value === 'passed' ? 'done' : 'todo',
  })
  const es = encoderStat.value
  if (es) {
    out.push({
      id: 'encode',
      label: t('x2xFlow.runEncode'),
      detail: es.line,
      note: es.cut ? t('x2xFlow.runEncodeCut', { n: es.cut }) : '',
      state: s4 && genStep.value === 0 ? 'live' : s4 ? 'done' : 'todo',
      wide: true,
    })
  }
  const mm = modelMeta.value
  const made: string[] = [resolveModelName(mm, runningConfigId.value || undefined)]
  if (mm?.steps) made.push(t('x2xFlow.runSteps', { n: mm.steps }))
  if (mm?.seed !== undefined && mm?.seed !== null) made.push(`seed ${mm.seed}`)
  out.push({
    id: 'make',
    label: t('x2xFlow.runMake'),
    detail: made.join(' \u00b7 '),
    note:
      // Position only. This note sits in a 96px step card clamped to three
      // lines; the position plus the time on one line is 45 characters and
      // gets cut off mid-word. The time goes on the panel's own figure line
      // below, which stands alone and is set in tabular numbers.
      queuePosition.value > 0
        ? t('x2xFlow.queuePos', { n: queuePosition.value })
        : s4
          ? `${generationProgress.value}%`
          : '',
    // The wait belongs where the waiting is watched. The band underneath is
    // only drawn once the picture is being made — by then the queue is behind
    // this run and there is nothing left to announce.
    time: queuePosition.value > 0 ? queueWaitShort.value : '',
    state: s4 ? 'live' : 'todo',
  })
  return out
})

/**
 * Reading as a chosen gesture, not one inferred from the constellation. Some
 * constellations read by themselves (a lone picture, two pieces with nothing
 * else); others now make something instead — a picture and a sound compose.
 * The mark on the circle reads whatever lies there, either way.
 */
const readableInZone = computed(
  () => effImageItems.value.length + effAudioItems.value.length + effVideoItems.value.length > 0
)
async function runReading() {
  if (busy.value) return
  await runAnalysisOnly()
}

/**
 * What a press clears before its first station lights up: the result, the
 * verdict and the figures of the run before it. runGenerate and runMusic both
 * start a run here.
 */
function clearLastRun() {
  blockedReason.value = ''
  blockedStage.value = null
  mediaUrl.value = ''
  mediaType.value = ''
  meshThumb.value = ''
  meshOpen.value = false
  codeOpen.value = false
  outputCode.value = ''
  codeKind.value = ''
  safetyState.value = 'idle'
  // A new run tells its own story: the panel keeps nothing from the last one.
  interceptionModel.value = ''
  adaptionModel.value = ''
  condensedTokens.value = null
  // Including what stage 4 reported last time. It is cleared when the stream
  // starts — but until then the card names the model, the steps and the seed of
  // the run BEFORE this one, right next to a stage that is plainly still ahead.
  modelMeta.value = null
  lastSubmittedPrompt.value = ''
}

/**
 * A generating run: the material is read where the route leaves pieces over,
 * the Prompt Interception writes the stance, the adaption writes it for the
 * model that will read it, and the run goes to that model (sendRun). Nothing
 * stops in between. The stations drop their boxes on the table as they go;
 * a box drawn back into the ring lets the next press take the chain up from
 * that station (zoneStation), so a prompt is changed on the table and run
 * again rather than confirmed mid-run.
 *
 * Three runs leave before this point: a reading (runAnalysisOnly) and a
 * composition of what already lies there (runCompose), because neither has an
 * intercepted prompt, and a song from lyrics and style (runMusic), which goes
 * from its interception to the model on its own path.
 */
async function runGenerate() {
  // The figures of the previous run are not this run's: clear them before the
  // first station lights up, not only when stage 4 starts.
  genStopped.value = false
  encodingInfo.value = null
  genStep.value = 0
  genTotalSteps.value = 0
  let prompt = effCombinedText.value.trim()
  const plan = composition.value
  if (busy.value || effUploadsPending.value) return
  // A video and a sound are enough on their own: nothing has to be written.
  // Wordless material runs too when a perspective lies in the zone, OR when the
  // chosen model needs words but cannot take the material (readMaterialAsPrompt):
  // the material is made to speak — image, sound or video are analyzed, the
  // words go through the chain; a perspective's i-path additionally keeps the
  // images as i2i input, while the mismatch path passes none (route.maxImages 0).
  const mediaOnly =
    !prompt &&
    !plan &&
    (zoneChain.value.length > 0 || readMaterialAsPrompt.value) &&
    (effImageItems.value.length > 0 ||
      effAudioItems.value.length > 0 ||
      effVideoItems.value.length > 0)
  if (!prompt && !plan && !mediaOnly && !analysisReady.value) return
  if (effUploadsFailed.value) {
    generationErrorMessage.value = t('x2xFlow.errImageFailed')
    return
  }
  // Material alone, wordless, without a perspective: read, don't make.
  if (analysisReady.value) {
    await runAnalysisOnly()
    return
  }
  // The model this run would go to is not answering. Struck through in the
  // list is only half of it: without this, pressing start still sends the run
  // to exactly the model the surface just called unreachable.
  if (routeUnavailable.value) {
    generationErrorMessage.value = missingText(runConfigId.value)
    return
  }

  // Nothing to make, only to lay together.
  if (plan && plan.generate === null) {
    await runCompose(plan.op, plan.ready)
    return
  }

  // A song from lyrics + style: the interception reads the lyrics, and both
  // texts go to HeartMuLa (runMusic).
  if (route.value.outputConfigId === HEARTMULA) {
    await runMusic(musicRoles.value ?? { lyrics: prompt, style: '' })
    return
  }

  // Wordless, the material IS the prompt. With words written, the material the
  // route leaves over is read as well: either way this run reads something.
  const leftover = readIntoWordsItems.value
  const readsLeftover =
    !mediaOnly && leftover.images.length + leftover.audio.length + leftover.video.length > 0
  const token = beginRun()
  // A station box in the ring lets a run pick up where the last one stopped.
  // A fresh reading makes that impossible: the words going forward are no
  // longer the ones the box is evidence of, and new words go through the whole
  // chain, checks included, rather than around it.
  const resume = readsLeftover ? null : zoneStation.value
  // The same objects, unchanged, since the chain last wrote: the chain is not
  // asked again. The interception holds, and the adaption holds where it was
  // written for the model this press goes to (see ChainWritten).
  const again = chainWritten.value
  const sig = ringSig.value
  const picked = pickSig.value
  if (again && again.intercepted) interceptionResult.value = again.intercepted
  const ad = again && again.adapted && again.adapted.cfg === runConfigId.value ? again.adapted : null
  runResume.value = again ? (ad ? 'adaption' : (resume ?? 'interception')) : resume
  runOrdinal.value += 1
  if (again && !again.runs.includes(runOrdinal.value)) again.runs.push(runOrdinal.value)
  // Taken here and nowhere later: what follows, the reading, the interception
  // and the adaption, is exactly the span in which the table changes under a
  // run that is already on its way.
  const born0 = originNow()
  clearLastRun()
  // Which model this run goes to is not decided yet — it follows the medium the
  // interception's text implies. Until then the stations read the live route.
  runningConfigId.value = ''
  materialWasRead.value = again === null && (mediaOnly || readsLeftover)
  startEnergy()

  if (again === null && (mediaOnly || readsLeftover)) {
    analyzing.value = true
    try {
      // Wordless, the whole reading becomes the prompt. With words written, the
      // reading covers exactly the pieces the route leaves over, and its words
      // go in front of the written ones, so what lies in the ring takes part in
      // the run. A piece that stays unread stops the run rather than falling
      // out of it: the marker on it promised a reading.
      const parts = await analyzeEffectiveMedia(undefined, '', readsLeftover ? leftover : undefined)
      if (!live(token)) return
      if (!parts.length) {
        generationErrorMessage.value = t('x2xFlow.errAnalyze')
        return
      }
      prompt = mediaOnly
        ? joinAnalyses(parts)
        : [joinAnalyses(parts), prompt].filter((p) => p.trim()).join('\n\n')
    } finally {
      if (live(token)) analyzing.value = false
    }
  }
  if (!live(token)) return

  let transformed = ''
  // Asked exactly this before: the words that went in and what came out hold.
  // Resumed: the words in the ring already went through the station whose box
  // lies there, and going through it again would undo the very step the box is
  // evidence of.
  if (again) {
    prompt = again.inputText
    transformed = again.intercepted
  } else if (resume === 'interception') {
    interceptionResult.value = transformed = prompt
  } else if (resume !== 'adaption') {
    try {
      interceptionActive.value = true
      transformed = await runInterception(prompt, token)
      if (!live(token)) return
      interceptionResult.value = transformed
    } catch (e: any) {
      // A run let go of reports nothing — least of all a failure, where the
      // user was just told it stopped.
      if (!live(token)) return
      interceptionActive.value = false
      if (e && e.blocked) {
        safetyState.value = 'blocked'
        blockedReason.value = e.reason || ''
        blockedStage.value = e.stage ?? e.blocked_stage ?? null
      } else {
        generationErrorMessage.value = t('x2xFlow.errNoMedia')
      }
      return
    }
  }
  interceptionActive.value = false
  // The reading and the interception take seconds each, and the chain reads
  // its perspectives as it goes: a perspective swapped or rewritten in that
  // span, or a model picked in it, makes a prompt that belongs to no ring. It
  // goes, but it is not remembered.
  const moved = ringSig.value !== sig || pickSig.value !== picked
  // What the chain was asked and what it wrote, for the next press with the
  // same ring. The adaption is added below, once it has answered. A run that
  // leaves nothing to go on with leaves the memory as it stands: an
  // interception that came back empty is not a text, a ring that moved under
  // the run has no prompt that belongs to it, and what stood before may be the
  // text of a ring the table returns to. An adaption box in the ring has no
  // interception to come back with and is remembered all the same.
  if (!again && !moved && (transformed.trim() || resume === 'adaption'))
    lastChain.value = {
      ringSig: sig,
      runs: [runOrdinal.value],
      reading: readingSig.value,
      inputText: prompt,
      intercepted: transformed,
      adapted: null,
    }

  // Route from the transformed text's medium (+ image count on the board).
  const r = route.value
  // A frame is a way of READING, never an output config. With the text medium
  // the run makes its object with the medium's own image model and reads that
  // — so the model that will really run is the one the adaption is asked for.
  // And the object that is
  // going to be read is not laid together with anything: a composition belongs
  // to a piece that is made to stay.
  const readFrame = manualMedium.value === 'text' ? readingFrame.value : null
  const cfg = runConfigId.value
  runningConfigId.value = cfg
  const runPlan = readFrame === null ? plan : null

  // Server paths, never the base64 preview: a data URL in the SSE GET query
  // string never reaches the backend. An image the route means to consume but
  // that has no path yet is an error, not something to drop quietly.
  const consumed = effImageItems.value.slice(0, r.maxImages)
  const imgs = consumed.map((i) => i.path).filter(Boolean) as string[]
  if (imgs.length !== consumed.length) {
    generationErrorMessage.value = t('x2xFlow.errImageFailed')
    return
  }
  const imageArgs: ImageArgs = {}
  if (r.imageParam === 'single' && imgs[0]) {
    imageArgs.input_image = imgs[0]
  } else if (r.imageParam === 'multi') {
    if (imgs[0]) imageArgs.input_image1 = imgs[0]
    if (imgs[1]) imageArgs.input_image2 = imgs[1]
    if (imgs[2]) imageArgs.input_image3 = imgs[2]
  }

  let finalPrompt = transformed || prompt
  let halves: { clip: string; t5: string } | null = null
  // Whether the chain has written for the model this press goes to; then the
  // next press with the same ring goes on with that.
  let adapted = ad !== null
  // Written for this very model already: the prompt goes as it went, with the
  // caption half the adaption wrote for it, and no model is asked.
  // An adaption already stands in the ring: the chain goes on with the check
  // and the translation, and the words go as they lie. The caption half is
  // asked of the same adaption that would have written it, so a two-part model
  // still hears two parts.
  if (ad) {
    transformed = ad.transformed
    finalPrompt = ad.finalPrompt
    halves = ad.halves
  } else if (resume === 'adaption') {
    adapting.value = true
    const cap = await recaption(finalPrompt, cfg)
    adapting.value = false
    if (!live(token)) return
    if (!moved) keepAdapted(cfg, '', finalPrompt, cap ? { clip: cap, t5: finalPrompt } : null, finalPrompt)
    await sendRun(
      {
        cfg,
        imageArgs,
        inputText: prompt,
        transformed: '',
        plan: runPlan,
        original: finalPrompt,
        seedKey: finalPrompt,
        born0,
        readFrame,
      },
      finalPrompt,
      cap
    )
    return
  } else if (transformed.trim()) {
    const a = await adaptFor(transformed, cfg, token, r.maxImages > 0)
    if (!live(token)) return
    if (a) {
      if (a.prompt) {
        finalPrompt = a.prompt
        adapted = true
      }
      halves = a.halves
      // Shortened, THAT is the text the model is to read: it is what the
      // adaption wrote its caption from, and what goes on as the run's
      // intercepted text.
      if (a.condensed) transformed = a.condensed
    }
  }
  // What the adaption wrote lies on the table, where it can be read, changed
  // and drawn back into the ring. A shortening is told in the run band; nothing
  // is asked. The prompt is carried here rather than read back off that box,
  // because the box goes on writing itself out while the run goes.
  //
  // Resumed at an interception, the yardstick for the seed is the text that
  // was PUT there, never the adaption written from it: the adaption answers
  // a little differently every time, so the same box would count as changed
  // on every press and never draw a fresh seed. Gone on with, the yardstick is
  // the one the run that wrote the prompt had — the same prompt again.
  const seedKey = ad ? ad.seedKey : resume === 'interception' ? transformed : ''
  if (adapted && !ad && !moved) keepAdapted(cfg, transformed, finalPrompt, halves, seedKey)
  await sendRun(
    {
      seedKey,
      cfg,
      imageArgs,
      inputText: prompt,
      transformed,
      plan: runPlan,
      original: finalPrompt,
      born0,
      readFrame,
    },
    halves ? halves.t5 : finalPrompt,
    halves ? halves.clip : ''
  )
}

/**
 * The stream reports its checks by internal name — `86a_filter`,
 * `llm_safety_check`, `llm_safety_check_escalation_override`. Those belong in
 * the run folder, not on a card somebody looks at in a workshop: one of them is
 * a German penal-code reference and one says an escalation was overruled. The
 * back says what was looked at. `translation` is dropped — it happened, but it
 * is not a check, and it is already named on the front while the run goes.
 */
const CHECK_KEY: Record<string, string> = {
  '86a_filter': 'x2xFlow.checkSymbols',
  llm_safety_check: 'x2xFlow.checkContent',
  llm_safety_check_escalation_override: 'x2xFlow.checkContent',
}
function namedChecks(raw: string[]): string[] | undefined {
  const out: string[] = []
  for (const c of raw) {
    const key = CHECK_KEY[c]
    if (key && !out.includes(t(key))) out.push(t(key))
  }
  return out.length ? out : undefined
}

/** What a run was started with. Taken once, at the press, and carried through. */
interface RunOrigin {
  preset?: string
  presetId: string
  context: string
  /**
   * The LoRA tiles in the zone at the press, copied. Which of them the run
   * loads is decided against the model the run EXECUTES, and that model is
   * known only once the interception has said what medium the words ask for
   * — so the tiles go along, and `runLoras` reads them when the model is there.
   */
  tiles: BoardLora[]
}
function originNow(): RunOrigin {
  return {
    preset: chainLabel.value || undefined,
    presetId: activePreset.value?.configId || 'user_defined',
    context: activeContext.value,
    tiles: zoneLoras.value.map((l) => ({ ...l })),
  }
}

/** Stage 3/4: seed logic, the stream, and the fall of the finished piece. */
async function finishRun(
  finalPrompt: string,
  cfg: string,
  imageArgs: ImageArgs,
  prompt: string,
  transformed: string,
  plan: (typeof composition)['value'],
  token: number,
  /**
   * What was in the ring when the run was STARTED. Everything the card's back
   * shows is otherwise a live computed over the zone: read when the picture
   * returns, it reports the table as it looks then. The interception alone runs
   * for seconds; pull the perspective out in that time and the finished piece
   * would come back claiming it never had one.
   */
  born0: RunOrigin,
  /**
   * What a repeated press is measured against, where that differs from the
   * words that go: the same yardstick means a variation and draws a new seed,
   * a changed one keeps the seed so the change is what is seen. Empty falls
   * back to the words themselves.
   */
  seedKey = '',
  /**
   * This run makes nothing of its own: it provides the picture ANOTHER run
   * needs. It therefore keeps no books — it inherits the seed the run it serves
   * has just drawn. Kept its own, it would write the intermediate config into
   * `previousConfig`, the next press would no longer find its own choice in the
   * record, neither call would re-roll, and every further press would hand back
   * the identical piece.
   */
  provides = false,
  /**
   * The second text of a model that reads two: the style tags of a song
   * beside its lyrics. The server checks both as they were written and hands
   * neither to the model translated (`secondary_text`, /pipeline/generation).
   */
  secondaryText?: string
): Promise<string> {
  // The LoRAs go with the model this run executes: read from the tiles the
  // press found in the zone, against the model that is known only now. A run
  // that only provides for another carries none (see `provides`).
  const loras = provides ? [] : runLoras(born0.tiles, cfg)
  // The seed BEFORE anything is made, so a repeated press is a variation of the
  // whole chain and not of its last link only.
  if (!provides) {
    lastSubmittedPrompt.value = finalPrompt
    // The adapters and their strengths are part of the yardstick: a LoRA laid
    // in, taken out or turned down is a change, and a change keeps the seed
    // so that the change is what is seen.
    const key = (seedKey || finalPrompt) + loras.map((l) => `\n${l.name}@${l.strength}`).join('')
    if (key === previousPrompt.value && cfg === previousConfig.value) {
      currentSeed.value = Math.floor(Math.random() * 2147483647)
    } else {
      if (currentSeed.value === null) currentSeed.value = STANDARD_SEED
      previousPrompt.value = key
      previousConfig.value = cfg
    }
  }

  // 3d is the one route that can arrive here short of pictures: it has no text
  // path, so the pick did not give way (resolveRoute) and the run makes what it
  // reads. The same words go to the medium's own image model first, the picture
  // falls on the table like every other artifact — visible, with its own
  // provenance — and then the mesh is made from it. One level only: the model
  // that makes a picture needs none, so this cannot recurse further.
  const need = imageInputRoute(cfg)?.minImages ?? 0
  if (need > 0) {
    const madeIn = [
      imageArgs.input_image,
      imageArgs.input_image1,
      imageArgs.input_image2,
      imageArgs.input_image3,
    ].filter(Boolean) as string[]
    const had = madeIn.length
    if (had < need) {
      provisioning.value = true
      const imgCfg = defaultConfigFor('image')
      const outerCfg = runningConfigId.value
      runningConfigId.value = imgCfg
      try {
        // The words that were adapted for the CHOSEN model do not ask for a
        // picture: the 3D config's own instruction says in so many words that
        // nothing is to be adapted ("No text optimization needed — the image IS
        // the input"), which is no way to ask for a picture from nothing. So the
        // stance goes through the adaption a second time, for the model that
        // really makes it.
        let seedPrompt = finalPrompt
        if (transformed.trim()) {
          const a = await adaptFor(transformed, imgCfg, token)
          if (!live(token)) return ''
          if (a?.prompt) seedPrompt = a.prompt
        }
        for (let i = had; i < need; i++) {
          // No plan goes down: a composition belongs to the piece this run is
          // FOR. Handed on, the provided picture would be laid together with
          // the sound and come back empty, and the chosen model never run.
          const p = await finishRun(
            seedPrompt,
            imgCfg,
            {},
            prompt,
            transformed,
            null,
            token,
            born0,
            '',
            true
          )
          if (!live(token)) return ''
          // No path to hand on: nothing was made (the box says so), or it was
          // made and could not be taken over — then it lies on the table with
          // its own "!" — or it came back as something other than a picture.
          // The run stops here; sending the chosen model off without its
          // picture would only fail a second time.
          if (!p) return ''
          madeIn.push(p)
        }
      } finally {
        provisioning.value = false
        if (live(token)) runningConfigId.value = outerCfg
      }
      imageArgs = { ...imageArgs }
      if (imageInputRoute(cfg)?.imageParam === 'multi') {
        if (madeIn[0]) imageArgs.input_image1 = madeIn[0]
        if (madeIn[1]) imageArgs.input_image2 = madeIn[1]
        if (madeIn[2]) imageArgs.input_image3 = madeIn[2]
      } else if (madeIn[0]) {
        imageArgs.input_image = madeIn[0]
      }
    }
  }

  // The server path of the picture this run made, empty for every other
  // outcome. It is what lets the reading read what this very run made, instead
  // of asking the board what lies there now.
  let made = ''
  resetStream()
  try {
    const result = await executeWithStreaming({
      prompt: finalPrompt,
      output_config: cfg,
      seed: currentSeed.value,
      run_id: interceptionRunId.value || currentRunId.value || undefined,
      input_text: prompt,
      // The run's own perspective, not the table's current one — the record the
      // backend keeps must name what was actually applied.
      context_prompt: born0.context,
      interception_result: transformed,
      interception_config: born0.presetId,
      // The tiles the press found in the ring, read against this run's model.
      // A picture this run only PROVIDES for another (3d) carries none: a
      // providing run executes the medium's image default.
      loras: loras.length ? loras : undefined,
      // The course whose adapters the register may load for this session.
      course_id: auth.activeCourseId,
      ...imageArgs,
      device_id: deviceId,
      source_view: 'x2x_flow',
      force_translation: true,
      secondary_text: secondaryText,
    })
    // Stopped while this was in flight: the page has already let go of this run,
    // and nothing it brings back may reach the board or the panel.
    if (!live(token)) return ''

    // The words as the model received them: the register puts the trigger
    // tags of the adapters it applied in front, in the form the captions were
    // written in (`trigger, prompt`), and the hover field and the card's back
    // read that form.
    const triggers = result.lora_triggers || []
    const triggered = triggers.length ? `${triggers.join(', ')}, ${finalPrompt}` : finalPrompt
    if (!provides && triggers.length) lastSubmittedPrompt.value = triggered
    if (result.status === 'success' && result.media_output) {
      safetyState.value = 'idle'
      const runId = result.media_output.run_id || result.run_id
      if (runId) currentRunId.value = runId
      // The generated artifact may be only half the piece: a plan that asked for
      // it now lays the sound under it.
      if (plan && plan.generate && runId) {
        await runCompose(plan.op, { ...plan.ready, [plan.generate]: runId }, token)
        return ''
      }
      mediaType.value = result.media_output.media_type || 'image'
      if (mediaType.value === 'code') {
        outputCode.value = result.media_output.code || ''
        // The run's own config, not the table's current one: move the
        // material while the code is on its way and a finished sketch would be
        // neither shown nor laid down.
        codeKind.value =
          cfg === 'tonejs_code' ? 'tonejs' : cfg === 'p5js_code' ? 'p5js' : ''
      }
      if (mediaType.value === '3d') {
        // The 3d chunk hands back a ready URL (and a thumbnail); the media route
        // is /api/media/3d/<run_id> with no index segment.
        mediaUrl.value = result.media_output.mesh_url || result.media_output.url || ''
        meshThumb.value = result.media_output.thumbnail_url || ''
      } else {
        const idx = result.media_output.index ?? 0
        mediaUrl.value = `/api/media/${mediaType.value}/${runId}/${idx}`
      }
      // The finished piece falls onto the table next to the zone, carrying
      // what made it — the back side reads exactly this.
      if (runId && mediaUrl.value) {
        settling.value = true
        const born: AsmItem['meta'] = {
          prompt: triggered,
          config: resolveModelName(modelMeta.value, cfg),
          preset: born0.preset,
          // What the register APPLIED, the perspective's own adapters included
          // — never the table's current reading.
          loras: provides ? undefined : loraLabelOf(result.loras || []) || undefined,
          mediaType: mediaType.value,
          // Which checks this run actually passed. They stood in the run panel
          // and were gone the moment it closed; on the back they stay with the
          // piece they belong to.
          safety: namedChecks(safetyChecks.value),
        }
        // Was in der Ausgabebox steht, ist das Werk, über das gesprochen wird:
        // die Begleitung bekommt diesen Lauf, nicht den davor.
        updateSession(runId, { mediaType: mediaType.value, configName: cfg })
        if (mediaType.value === 'code' && outputCode.value && codeKind.value)
          fallCode(outputCode.value, codeKind.value, runId, born)
        // Awaited, not fired off: a run waiting on this picture needs the server
        // path the fall uploads, and the caller is the only one who can wait.
        else if (mediaType.value === 'image') made = await fallImage(runId, mediaUrl.value, born)
        else if (mediaType.value === 'video') fallMedia('video', mediaUrl.value, runId, born)
        else if (mediaType.value === 'audio' || mediaType.value === 'sound' || mediaType.value === 'music')
          fallMedia('audio', mediaUrl.value, runId, born)
      }
    } else if (result.status === 'blocked') {
      safetyState.value = 'blocked'
      blockedReason.value = result.blocked_reason || ''
      blockedStage.value = result.blocked_stage ?? null
      // Refused, these words are not a prompt the next press goes on with: it
      // asks the chain again, as every press did before the memory existed. A
      // memory this run did not go on with is another ring's, and stands.
      if (lastChain.value && lastChain.value.runs.includes(runOrdinal.value)) lastChain.value = null
    } else if (result.status === 'cancelled') {
      // The run really did stop. Only now may the box say so.
      genStopped.value = true
      generationErrorMessage.value = t('x2xFlow.stopped')
    } else if (result.status === 'error') {
      failRun(result.error || '', result.errorType, result.busy)
    }
  } catch (e: any) {
    if (!live(token)) return ''
    failRun(e?.message || '')
  } finally {
    // Not under `live(token)`: a run that was let go of has to put this down
    // too, or the box stays busy for the rest of the session.
    settling.value = false
    if (live(token)) genStopping.value = false
  }
  return made
}

/**
 * HeartMuLa: lyrics (TEXT_1) + style tags (TEXT_2), on the generation stream
 * every run of this page that generates goes on (finishRun), with the style
 * tags as its second text. From 2026-07-10 (af517455) to 2026-10-06 the song went over a
 * POST of its own beside that stream, and the box showed neither its place in
 * the queue nor its own checks.
 *
 * The perspective still applies, but only to the words: the lyrics are the
 * material, the style tags are an instruction, like the context prompt. With no
 * preset and an empty free prompt, `user_defined` passes the lyrics through
 * verbatim, so a song is not rewritten unless the learner asks for it.
 */
async function runMusic(roles: { lyrics: string; style: string }) {
  const token = beginRun()
  // What the ring held at the press, as every run takes it.
  const born0 = originNow()
  // A press of the same button as every other run, and a run of its own:
  // finishRun reads this number when a refusal decides whose memory it ends.
  runOrdinal.value += 1
  clearLastRun()
  // Known at the press: the stations name this model from the first one on.
  runningConfigId.value = HEARTMULA
  // A song reads no material.
  materialWasRead.value = false
  startEnergy()
  interceptionActive.value = true

  let lyrics = roles.lyrics
  try {
    lyrics = (await runInterception(roles.lyrics, token)) || roles.lyrics
    if (!live(token)) return
    interceptionResult.value = lyrics
  } catch (e: any) {
    if (!live(token)) return
    interceptionActive.value = false
    if (e && e.blocked) {
      safetyState.value = 'blocked'
      blockedReason.value = e.reason || ''
      blockedStage.value = e.stage ?? e.blocked_stage ?? null
    } else {
      generationErrorMessage.value = t('x2xFlow.errNoMedia')
    }
    return
  }
  if (!live(token)) return
  interceptionActive.value = false
  // The seed's yardstick is both texts: a style changed is a change, and
  // keeps the seed so that the change is what is heard.
  await finishRun(
    lyrics,
    HEARTMULA,
    {},
    roles.lyrics,
    lyrics,
    null,
    token,
    born0,
    `${lyrics}\n${roles.style}`,
    false,
    roles.style
  )
}

/**
 * Post-production: artifact(s) -> artifact. The inputs are runs the platform
 * already produced and already checked, so this adds no prompt and no model
 * output — and runs no further safety check. The result is an mp4 of its own
 * kind (entity type output_composition), served at /api/media/composition/<id>.
 */
async function runCompose(
  op: ComposeOp,
  inputs: Partial<Record<ComposeRole, string>>,
  // Laying a generated piece under a sound is the same run going on, so it
  // keeps that run's number; asked for on its own, it is a run of its own.
  token: number = beginRun()
) {
  blockedReason.value = ''
  blockedStage.value = null
  // Cleared at the START, the way the two other run functions clear it, and not
  // only where this one succeeds. A judgement stands until the next run or the
  // next change to the board answers it (the watch above `onGenClick`), so a
  // refusal left by the run before this one would otherwise keep the box saying
  // `blocked` through a composition that ran no check at all.
  safetyState.value = 'idle'
  mediaUrl.value = ''
  mediaType.value = ''
  meshThumb.value = ''
  meshOpen.value = false
  codeOpen.value = false
  outputCode.value = ''
  codeKind.value = ''
  directRunning.value = true
  try {
    const res = await fetch('/api/media/compose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operation: op, inputs, device_id: deviceId }),
    })
    const data = await res.json()
    if (!live(token)) return
    if (!res.ok || !data.success) throw new Error(data.error || t('x2xFlow.errNoMedia'))
    safetyState.value = 'idle'
    currentRunId.value = data.run_id
    mediaType.value = 'video' // a composition is delivered as mp4
    mediaUrl.value = data.url
    if (data.run_id && data.url)
      // The CARD is a film; what the RUN holds is a composition, recorded as
      // `output_composition` and served from its own route. Kept as a video the
      // star was refused and sprang back, the same way a sketch kept as a
      // picture was (2026-09-01).
      fallMedia('video', data.url, data.run_id, {
        config: op.replace('_plus_', ' + '),
        mediaType: 'composition',
      })
  } catch (e: any) {
    if (!live(token)) return
    failRun(e?.message || '')
  } finally {
    if (live(token)) directRunning.value = false
  }
}

onBeforeUnmount(endStopHold)
</script>

<style scoped>
/* Fills .app-content, not the window: the app header sits above us, so 100vh
   would push the canvas — and the zoom controls in its corner — off-screen. */
.flow-view { position: relative; display: flex; flex-direction: column; height: 100%; min-height: 0; overflow: hidden; background: var(--bg-base); color: #e8e8e8; }

/* The map is a transparent overlay on a full-height canvas: only the three
   boxes and the reserved rectangle around them take pointer events, so the rest
   of the top band is reachable material space — not a locked full-width row.
   Its long-press bubbles may spill onto the canvas below. */
.map-wrap { position: absolute; top: 10px; left: 50%; transform: translateX(-50%); z-index: 3; width: min(var(--flow-map-w), calc(100% - 32px)); pointer-events: none; }
/* The reserved rectangle: transparent, but it takes pointer events so canvas
   gestures never reach behind the boxes. Width flexes with the box span. */
.lock-rect { position: absolute; pointer-events: auto; background: transparent; }
.fl-map { background: transparent; overflow: visible; }
.edges { position: absolute; left: 0; top: 0; pointer-events: none; }
.edges line { stroke: #5a5a5a; stroke-width: 1; stroke-dasharray: 3 6; animation: dashf 3.2s linear infinite; }
.edges line.on { stroke: #7fb2ff; animation-duration: 0.7s; }
@keyframes dashf { to { stroke-dashoffset: -18; } }

.nd { position: absolute; box-sizing: border-box; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; min-width: 0; padding: 4px; border-radius: 10px; border: 1px solid #4a4270; overflow: hidden; transition: border-color 0.2s; pointer-events: auto; }
.nd.mix { background: #2b2450; border-color: #7f77dd; border-width: 1.5px; }
/* The pull: the box takes the room of all three and gives it back. Left/width
   are animated, not a transform — the text inside must keep its --flow-fs-*
   size at every step of the movement. The small overshoot is the tug. */
.nd.op { background: #1d2f45; border-color: #3f6a9c; cursor: pointer; }
.nd.op.anim { transition: border-color 0.2s, left 0.42s cubic-bezier(0.34, 1.28, 0.64, 1),
    width 0.42s cubic-bezier(0.34, 1.28, 0.64, 1), height 0.42s cubic-bezier(0.34, 1.28, 0.64, 1); }
.nd.op.wide { z-index: 2; cursor: default; }
.nd.out { background: #4a2b2f; border-color: #7a4046; }
.nd:hover { border-color: #b8c2d8; }
.nd.live { border-color: #7fb2ff; animation: livepulse 1.2s ease-in-out infinite; }
@keyframes livepulse { 0%, 100% { border-color: #7fb2ff; } 50% { border-color: #2e4a6a; } }

.lbl { font-size: var(--flow-fs-label); font-weight: 400; color: #e8e8e8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.nd.compact .lbl { display: none; }

/* creation — the medium glyphs are the medium/model indicator */
.cr-media { display: flex; align-items: center; gap: 0.34em; font-size: var(--flow-glyph-medium); color: #5a5470; }
.cr-media .g { cursor: pointer; transition: color 0.25s; }
.cr-media .g.lit { color: #b6afea; }
.cr-media .g.primary { color: #e9e6fb; }
/* A held pick must be visible as a pick, not just as the brightest glyph. */
.cr-media .g.manual { position: relative; }
.cr-media .g.manual::after { content: ''; position: absolute; left: 50%; bottom: -0.16em; width: 0.16em; height: 0.16em; border-radius: 50%; background: #cfe0ff; transform: translateX(-50%); }
.cr-model { font-size: var(--flow-fs-sub); color: #cfe0ff; font-weight: 400; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.cr-model.held { text-decoration: underline; text-underline-offset: 3px; text-decoration-color: #7f77dd; cursor: help; }

/* generation — a triangle, then the run's own card */

/* Transparency, not a warning: quiet, two lines at most, and it disappears the
   moment the material carries the choice again. */
.run-note {
  max-width: 100%;
  font-size: var(--flow-fs-hint);
  line-height: 1.2;
  text-align: center;
  color: rgba(255, 255, 255, 0.38);
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* The caption under the triangle: what the next press does. Same slot and same
   two-line clamp as the note above it -- it names an act, so it is legible
   rather than held back. */
.run-cap {
  flex-shrink: 0;
  max-width: 100%;
  font-size: var(--flow-fs-hint);
  line-height: 1.2;
  text-align: center;
  color: #9fc0f0;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* The hold, drawn where the hold is happening: a line grows along the foot of
   the box being held, under the words that say what the hold does. */
.nd.op.holding {
  background-image: linear-gradient(
    to right,
    #e08a8a 0 calc(var(--hold, 0) * 100%),
    transparent 0
  );
  background-repeat: no-repeat;
  background-size: 100% 2px;
  background-position: left bottom;
}
.gr-stop { flex: 0 0 auto; white-space: nowrap; font-size: var(--flow-fs-hint); color: rgba(255, 255, 255, 0.35); transition: color 0.2s; }
.gr-stop.armed { color: #e08a8a; }

/* The triangle itself is drawn in assets/flow-stage.css, which this page
   imports; here stand only the two states the NODE gives it - this band's
   control is the node, not the glyph. */
.nd.op.ready:hover .play { opacity: 1; }
.play.off { opacity: 0.18; }
.nd.op:not(.ready) { cursor: default; }

.gi { position: relative; display: flex; flex-direction: column; align-items: stretch; gap: 1px; width: 100%; flex: 1 1 auto; min-height: 0; padding: 5px 7px 7px; box-sizing: border-box; text-align: start; }
.gi-model { flex-shrink: 0; font-size: var(--flow-fs-sub); font-weight: 700; color: rgba(255, 255, 255, 0.95); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.gi-state { flex-shrink: 0; display: flex; flex-wrap: wrap; gap: 0 6px; font-size: var(--flow-fs-sub); line-height: 1.35; }
.gi-run { color: #7fb2ff; }
.gi-ok { color: #7fd39a; }
.gi-err { color: #e0568a; }
/* The instruction after a failure is NOT the coloured line — the cause above it
   is. It reads in the same grey as the box's other notes. */
.gi-act { color: #9a9a9a; }
.gi-note { color: #9a9a9a; }
.gi-body { flex: 1; min-height: 0; margin-top: 2px; font-size: var(--flow-fs-sub); line-height: 1.35; color: rgba(255, 255, 255, 0.62); overflow: hidden; display: -webkit-box; -webkit-line-clamp: var(--gi-lines, 3); -webkit-box-orient: vertical; }
/* .gi-body stands last and sets a colour of its own, and one class weighs as
   much as another: a body that is a note or an error was drawn in the ordinary
   text colour, so a refusal read like a sentence the model had written. */
.gi-body.gi-note { color: #9a9a9a; }
.gi-body.gi-err { color: #e0568a; }
/* The cause. Its own red, one step lighter than the refusal's — the tone
   StatusBadge carries for `unavailable`: on the box blue #e0568a reads at
   3.8:1, this at 5.4:1. A refusal and a breakdown are not the same answer.
   One line, and it neither grows nor shrinks: the instruction underneath keeps
   its room, and a translation that runs long ends in an ellipsis instead of
   pushing the instruction out of the box. */
.gi-body.gi-fail { color: #ff7b72; flex: 0 0 auto; -webkit-line-clamp: 1; }
/* generation — the paused prompt: a real panel below the node (not stuffed into
   the box). Palette shared with the generation node (blue); room reserved for
   options, and a clearly-drawn send button. */
/* Leaving, it is still drawn for a moment — but a control that is fading out
   must not still answer: the × was taking clicks for a run already on its way. */
/* The panel is FlowRunPanel's. What stays here is what goes INTO its foot:
   this page's live energy figures, which are slot content and therefore this
   page's scope. */
.gr-e { font-size: var(--flow-fs-hint); color: #9fd3a8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.gr-e.off { color: #7a7a7a; }

.gi-bar { height: 3px; border-radius: 2px; background: rgba(255, 255, 255, 0.08); overflow: hidden; }
.gi-fill { height: 100%; background: #4a9eff; border-radius: 2px; transition: width 0.2s; }

/* output — the denoising preview, then the media */
.out-media { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.out-audio { width: 92%; }
.out-phase { position: absolute; left: 0; right: 0; bottom: 0; padding: 3px 6px; font-size: var(--flow-fs-hint);
  color: #f4dee1; background: rgba(0, 0, 0, 0.52); text-align: center; }
.out-link { font-size: var(--flow-fs-sub); color: #7fb2ff; text-decoration: none; text-align: center; padding: 0 6px; }

/* Only where it hangs. What it looks like is components/FlowBubbles.vue. */
.bubbles-float { position: absolute; pointer-events: auto; }

/* The submitted-prompt hover card below the generation node: read-only, so
   it takes no pointer events itself (it would otherwise flicker the hover). */
.gen-prompt { position: absolute; box-sizing: border-box; max-width: min(560px, 60vw); max-height: 40vh; overflow: auto; background: var(--bg-base); border: 1px solid var(--surface-3); border-radius: 10px; padding: 8px 10px; pointer-events: none; white-space: pre-wrap; overflow-wrap: anywhere; }
.gen-prompt-head { font-size: var(--flow-fs-hint); color: #aaa; margin-bottom: 4px; }
.gen-prompt-body { font-size: var(--flow-fs-sub); color: #cfc9f2; line-height: 1.4; }

/* The canvas: the rest of the viewport. Nothing frames the material. */
.canvas { position: relative; z-index: 1; flex: 1; min-height: 0; overflow: hidden; background: var(--bg-base); cursor: grab; touch-action: none; }
.canvas:active { cursor: grabbing; }
.world { position: absolute; left: 0; top: 0; transform-origin: 0 0; }

/* Placement only. The box itself — background, border, radius — is FlowCard's,
   and stating it a second time here is exactly what this change removed. */
.asm-item { position: absolute; }
.asm-item.image { background: var(--bg-base); }
.asm-ta { display: block; width: 100%; box-sizing: border-box; background: transparent; border: none; outline: none; resize: none; overflow-y: auto; scrollbar-width: thin; scrollbar-color: #4a4270 transparent; color: #e6e2f2; padding: 9px 11px; font-size: var(--flow-fs-body); font-family: var(--font-sans); line-height: 1.5; }
.asm-img { display: block; width: 100%; height: auto; cursor: zoom-in; }
.asm-item.busy { opacity: 0.5; }
/* Corner handle: sets the card's world width, so zoom and size stay independent. */
/* A source card: the logo says where it comes from, the term says what was
   asked. Everything else is on the other side, like every other card here. */
/* The sketch card: a plate carrying one still picture, or the runtime's name
   until there is one. Surface token, not a literal — Rule #7. */
.asm-code { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 56px; background: var(--surface-1); border-radius: 4px; cursor: zoom-in; overflow: hidden; }
.asm-code-shot { display: block; width: 100%; height: auto; }
.asm-code-name { padding: 24px 0; color: rgba(255, 255, 255, 0.55); font-size: var(--flow-fs-sub); letter-spacing: 0.05em; }
.asm-src { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 7px; padding: 12px 10px 14px; cursor: pointer; }
/* The mark is shown as it is — not greyed, not tinted. */
.asm-src-logo { width: 30px; height: 30px; }
.asm-src-term { color: #cfc9f2; font-size: var(--flow-fs-sub); text-align: center; line-height: 1.3; overflow-wrap: anywhere; }
/* A card is as tall as its front. FlowCard lets the taller face set the
   height and leaves the size to the page, and this page sets only the width:
   since 3612dd11 put the record of a run and the looked-up article on the
   back, the back stretched a card of about 200 px to many times its width.
   Placed absolutely, the back fills the card and its body scrolls, the way
   MediaGridCell holds it in a cell. */
.canvas :deep(.asm-item.two > .face.back) { position: absolute; inset: 0; }
/* Surplus material the route cannot consume — honest, not silently dropped. */
.asm-surplus { display: inline-flex; align-items: center; justify-content: center; width: 15px; height: 15px; margin-right: 4px; border-radius: 50%; background: #3a2e12; color: #e0b24a; border: 1px solid #6a531c; font-size: 11px; line-height: 1; cursor: help; flex-shrink: 0; }
.asm-surplus.err { background: #3a1620; color: #e0568a; border-color: #6a2036; }
.asm-surplus.words { font-size: 9px; letter-spacing: 0.4px; }

/* The action zone: a soft field, not a frame. It brightens while material is
   in hand, and keeps a faint edge while it holds material. */
.zone { position: absolute; border-radius: 50%; pointer-events: none; box-sizing: border-box; --zfr: 0.055;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.045) 0%, rgba(255, 255, 255, 0.02) 58%, rgba(255, 255, 255, 0) 70%);
  transition: background 0.25s; }
/* The rim is no drawn line: two soft blobs, slowly counter-rotating, whose
   inset glow makes the edge flow irregularly. Transform-only — compositor
   work, no repaint per frame. */
.zone::before, .zone::after { content: ''; position: absolute; inset: -1.5%;
  border-radius: 48% 52% 51% 49% / 52% 47% 53% 48%;
  box-shadow: inset 0 0 26px rgb(255 255 255 / var(--zfr));
  animation: zfringe 26s linear infinite; }
.zone::after { inset: -0.5%; border-radius: 51% 49% 47% 53% / 49% 53% 48% 52%; animation-duration: 19s; animation-direction: reverse; }
@keyframes zfringe { to { transform: rotate(1turn); } }
.zone.holds { --zfr: 0.1; }
.zone.glow { --zfr: 0.2;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.09) 0%, rgba(255, 255, 255, 0.04) 58%, rgba(255, 255, 255, 0) 72%); }
.zone-grip { position: absolute; width: 14px; height: 14px; margin: -7px 0 0 -7px; border-radius: 50%;
  background: rgba(255, 255, 255, 0.18); border: 1px solid rgba(255, 255, 255, 0.28); cursor: grab; touch-action: none; }
.zone-grip:hover { background: rgba(255, 255, 255, 0.34); }
.zone-grip:active { cursor: grabbing; }
.zone-size { position: absolute; width: 14px; height: 14px; margin: -7px 0 0 -7px; border-radius: 50%;
  background: rgba(255, 255, 255, 0.12); border: 1px solid rgba(255, 255, 255, 0.22); cursor: ew-resize; touch-action: none; }
.zone-size:hover { background: rgba(255, 255, 255, 0.3); }
.zone-read { position: absolute; display: flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; margin: -9px 0 0 -9px; padding: 0; border-radius: 50%;
  background: rgba(255, 255, 255, 0.12); border: 1px solid rgba(255, 255, 255, 0.22);
  color: rgba(255, 255, 255, 0.55); cursor: pointer; }
.zone-read:hover { background: rgba(255, 255, 255, 0.3); color: #fff; }
.zone-read svg { width: 11px; height: 11px; }
/* Material the zone holds is visibly the material being read. */
.asm-item.inzone { outline: 1px solid rgba(255, 255, 255, 0.18); outline-offset: 2px; }

/* The perspective picker: boxless, pulsing, movable. */
.persp { position: absolute; z-index: 6; display: flex; padding: 0; border: none; background: transparent; color: #FFB300; cursor: pointer; filter: drop-shadow(0 0 4px rgba(255, 179, 0, 0.6)); animation: preset-pulse 3.2s ease-in-out infinite; touch-action: none; }
.persp svg { width: var(--flow-glyph-fixture); height: var(--flow-glyph-fixture); }
.persp:hover { filter: drop-shadow(0 0 6px rgba(255, 179, 0, 0.9)); }

/* The plus: the second free fixture — same size step, same drag and the
   same faint breath as the perspective. Open, it turns to a x. */
.addg { position: absolute; z-index: 6; display: flex; padding: 0; border: none; background: transparent; color: #3ecf8e; cursor: pointer; animation: preset-pulse 3.2s ease-in-out infinite; touch-action: none; }
.addg svg { width: var(--flow-glyph-plus); height: var(--flow-glyph-plus); transition: transform 0.18s ease; }
.addg:hover { color: #5fe0a6; }
.addg.open svg { transform: rotate(45deg); }
/* The arc: a box the size of the plus, laid over it, so the options can be
   placed from ITS center. It catches nothing itself — the plus stays clickable. */
.addopt { position: absolute; z-index: 25; width: var(--flow-glyph-plus); height: var(--flow-glyph-plus); pointer-events: none; --ao-r: calc(var(--flow-glyph-fixture) * 1.7); }
.ao { position: absolute; left: 50%; top: 50%; display: flex; flex-direction: column; align-items: center; gap: 3px; padding: 0; border: none; background: transparent; color: #3ecf8e; cursor: pointer; pointer-events: auto; }
.ao svg { width: calc(var(--flow-glyph-fixture) * 0.5); height: calc(var(--flow-glyph-fixture) * 0.5); }
.ao-l { font-size: var(--flow-fs-hint); color: #9a97a8; white-space: nowrap; }
.ao:hover { color: #5fe0a6; }
.ao:hover .ao-l { color: #e9e6fb; }
.ao svg, .ao-l { animation: ao-in 0.18s ease-out both; animation-delay: var(--ao-d, 0ms); }
@keyframes ao-in { from { opacity: 0; transform: scale(0.6); } to { opacity: 1; transform: none; } }
/* Faint, and slow: an invitation, not a signal. Both free fixtures breathe
   in this one rhythm — they mount together, so they stay in phase. */
@keyframes preset-pulse { 0%, 100% { opacity: 0.82; } 50% { opacity: 1; } }

.pb { position: absolute; width: 144px; height: 144px; cursor: grab; touch-action: none; }
.pb:active { cursor: grabbing; }
.pb-surplus { position: absolute; left: -3px; top: -3px; margin: 0; }
.pb-ord { position: absolute; left: -4px; top: -4px; width: 26px; height: 26px; display: flex; align-items: center; justify-content: center; border: 1px solid #FFB300; border-radius: 50%; background: #16121f; color: #FFB300; font-size: 14px; }
.pb-del { position: absolute; right: -4px; top: -4px; width: 24px; height: 24px; padding: 0; border: 1px solid #3a3358; border-radius: 50%; background: #16121f; color: #8a84a8; font-size: 14px; line-height: 1; cursor: pointer; }
.pb-del:hover { color: #e9e6fb; border-color: #7f77dd; }
/* The LoRA sign, the third free fixture: the violet of the sign, the pulse of the pair. */
.lorag { position: absolute; z-index: 6; display: flex; padding: 0; border: none; background: transparent; color: #a78bfa; cursor: pointer; filter: drop-shadow(0 0 4px rgba(167, 139, 250, 0.55)); animation: preset-pulse 3.2s ease-in-out infinite; touch-action: none; }
.lorag svg { width: var(--flow-glyph-fixture); height: var(--flow-glyph-fixture); }
.lorag:hover { filter: drop-shadow(0 0 6px rgba(167, 139, 250, 0.9)); }
/* The gear: the other corner, lifted clear of the zoom cluster that sits in it,
   at the same resting place it has on Together. */
.fixture-gear {
  position: fixed; z-index: 62; pointer-events: auto;
  right: clamp(0.75rem, 2vw, 1.5rem);
  bottom: calc(var(--flow-footer-clear, 54px) + 2.4rem);
}
/* A LoRA tile: the strength where it is not the trained one, and the net a perspective wears when it brings an adapter — both at the lower left, where no other mark stands. */
.pb-pct { position: absolute; left: -4px; bottom: -4px; height: 22px; padding: 0 7px; display: flex; align-items: center; border: 1px solid #a78bfa; border-radius: 11px; background: #16121f; color: #a78bfa; font-size: 12px; white-space: nowrap; }
.pb-net { position: absolute; left: -4px; bottom: -4px; width: 26px; height: 26px; display: flex; align-items: center; justify-content: center; border: 1px solid #a78bfa; border-radius: 50%; background: #16121f; color: #a78bfa; }
.pb-net svg { width: 17px; height: 17px; }
.pb-net-q { position: absolute; left: -3px; bottom: -3px; margin: 0; }
/* The net beside the model in the create box: a LoRA goes with this run. */
.cr-lora { display: inline-flex; vertical-align: -2px; margin-inline-start: 6px; color: #a78bfa; }
.cr-lora svg { width: 15px; height: 15px; }
/* The strength half. */
.lora-edit .le-row { display: flex; align-items: baseline; gap: 10px; margin-top: 6px; font-size: 13px; }
.lora-edit .le-axis { align-items: center; }
.lora-edit .le-k { flex: 0 0 64px; color: #8a84a8; }
.lora-edit .le-v { color: #e9e6fb; overflow-wrap: anywhere; }
.lora-edit .le-slider { flex: 1 1 auto; min-width: 0; --ms-thumb-color: #a78bfa; }

/* The free interception prompt — the self-written half of the perspective. */
.persp-edit { position: absolute; z-index: 30; box-sizing: border-box; background: #0b0a12; border: 1px solid #241f38; border-radius: 12px; padding: 10px 12px; box-shadow: 0 12px 32px rgba(0, 0, 0, 0.5); }
.persp-edit:focus-within { border-color: #7f77dd; }
.pe-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.pe-name { color: #8a84a8; font-size: var(--flow-fs-label); }
.pe-close { padding: 0 2px; border: none; background: none; color: #8a84a8; font-size: 16px; line-height: 1; cursor: pointer; }
.pe-close:hover { color: #e9e6fb; }
.pe-name-input { flex: 1; min-width: 0; margin-right: 8px; padding: 0; background: transparent; border: none; border-bottom: 1px solid transparent; outline: none; color: #8a84a8; font-size: var(--flow-fs-label); font-family: inherit; }
.pe-name-input:hover { border-bottom-color: #241f38; }
.pe-name-input:focus { border-bottom-color: #7f77dd; color: #cfc9f2; }
.pe-name-input::placeholder { color: #55506e; }

/* Which run laid this box down. Set in tabular numbers so a column of boxes
   lines up, and a shade brighter than the name beside it: the name says what
   the box is, the number says which run it belongs to. */
.asm-run {
  flex: 0 0 auto;
  margin-right: 6px;
  font-size: var(--flow-fs-hint);
  line-height: 1;
  font-variant-numeric: tabular-nums;
  color: #9b93c4;
  user-select: none;
}

/* The card's kind, at the head of its bar. It reads as a name, so it stays
   quieter than anything in the card and never competes with the text. */
.asm-type {
  flex: 0 0 auto;
  margin-right: 6px;
  font-size: var(--flow-fs-hint);
  line-height: 1;
  letter-spacing: 0.08em;
  color: #6f6a8a;
  user-select: none;
}
.pe-keep { display: flex; align-items: center; justify-content: flex-end; gap: 10px; margin-top: 6px; }
.pe-keep-note { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #8a84a8; font-size: var(--flow-fs-label); }
.pe-keep-btn { padding: 3px 10px; border: 1px solid #241f38; border-radius: 999px; background: transparent; color: #8a84a8; font-size: var(--flow-fs-label); font-family: inherit; cursor: pointer; }
.pe-keep-btn:hover:not(:disabled) { border-color: #7f77dd; color: #e9e6fb; }
.pe-keep-btn:disabled { opacity: 0.4; cursor: default; }
.pe-text { display: block; width: 100%; height: 150px; box-sizing: border-box; background: transparent; border: none; outline: none; resize: none; color: #cfc9f2; font-size: var(--flow-fs-body); font-family: var(--font-sans); line-height: 1.5; }

/* The cross of the mesh and the sketch overlays below. The inspect layer that
   once stood here left on 2026-09-22 for the platform's MediaFullscreen. */
.inspect-x { position: absolute; right: 18px; top: 18px; width: 32px; height: 32px; padding: 0; border: 1px solid var(--surface-3); border-radius: 50%; background: transparent; color: #b0b0b0; font-size: 18px; line-height: 1; cursor: pointer; }
.inspect-x:hover { background: var(--surface-2); border-color: var(--surface-4); color: #e8e8e8; }

.view-tools { position: absolute; right: 16px; bottom: var(--flow-footer-clear); display: flex; align-items: center; gap: 4px; }
.view-tools button { display: flex; align-items: center; justify-content: center; min-width: 30px; height: 30px; padding: 0 7px; border: 1px solid var(--surface-3); border-radius: 8px; background: transparent; color: #b0b0b0; cursor: pointer; font-size: var(--flow-fs-body); }
.view-tools button:hover { background: var(--surface-2); border-color: var(--surface-4); }

.fade-enter-active, .fade-leave-active { transition: opacity 0.18s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.sketch-ov { position: fixed; inset: 0; background: rgba(0,0,0,.88); z-index: 60; display: grid; place-items: center; }
.code-box {
  position: relative;
  width: min(1200px, 92vw);
  height: min(760px, 82vh);
}
/* The cross stands above the canvas toolbar: at the box's own corner it lay
   on the toolbar's Done, and a click on Done closed the sketch unsent. */
.sketch-box { position: relative; max-width: min(92vw, 900px); max-height: 88vh; overflow: auto; padding-top: 44px; }
.sketch-box > .inspect-x { top: 0; right: 0; }
.mesh-view { width: min(90vw, 860px); height: min(80vh, 620px); background: var(--bg-base); }
.asm-audio { width: 100%; display: block; }
.asm-video { width: 100%; display: block; border-radius: 4px; background: #000; }
</style>
