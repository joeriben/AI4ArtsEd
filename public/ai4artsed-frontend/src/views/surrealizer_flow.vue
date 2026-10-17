<template>
  <div class="flow-view" :class="{ embedded }">
    <div class="topbar">
      <span class="tt">Surrealizer · {{ t('surrealizer.flow.flowTag') }}</span>
      <span class="hint">{{ t('surrealizer.flow.openHint') }}</span>
      <router-link v-if="!embedded" to="/surrealizer" class="legacy">{{ t('surrealizer.flow.classic') }} ↗</router-link>
    </div>

    <div ref="viewportEl" class="viewport" :style="{ height: mapH + 'px' }" @click="closePanel">
      <div class="world" :class="{ receded: open !== null }" :style="{ transform: worldTransform }">
        <svg class="edges" :class="{ working: isExecuting }" :viewBox="`0 0 ${W} ${H}`" :width="W" :height="H">
          <line v-for="(e, i) in edgeLines" :key="i" :x1="e[0]" :y1="e[1]" :x2="e[2]" :y2="e[3]" />
        </svg>

        <div
          v-for="n in NODES"
          :key="n.id"
          class="nd"
          :class="[n.kind, { focus: open === n.id }]"
          :style="{ left: n.r.x + 'px', top: n.r.y + 'px', width: n.r.w + 'px', height: n.r.h + 'px' }"
          @click.stop="toggleNode(n.id)"
        >
          <img v-if="n.id === 'image' && primaryOutput" class="thumb" :src="primaryOutput" alt="" />
          <div class="lbl">{{ nodeLabel(n.id) }}</div>
          <div v-if="n.id === 'fusion'" class="sub">α = {{ f2(alphaFaktor) }}</div>

          <div v-if="n.kind !== 'data'" class="viz">
            <svg v-if="n.id === 'fusion'" width="60" height="16" viewBox="0 0 60 16">
              <line x1="6" y1="8" x2="54" y2="8" stroke="#5a5a5a" />
              <circle :cx="miniVx" cy="8" r="4" :fill="miniVOutside ? '#e0568a' : '#7fb2ff'" />
            </svg>
            <span v-else class="pulse" :class="{ hot: isExecuting && (n.id === 'gen' || n.id === 'image') }"></span>
          </div>

          <div v-if="n.id === 'gen' && isExecuting" class="strip">
            <div class="stripbar" :style="{ width: generationProgress + '%' }"></div>
          </div>
        </div>
      </div>
    </div>

    <svg v-if="open" class="connector" :width="vw" height="26">
      <line :x1="anchorX" y1="0" :x2="vw / 2" y2="26" />
    </svg>

    <div v-if="open" class="panel" @click.stop>
      <div class="phead">
        <span class="pname">{{ nodeLabel(open) }}</span>
        <button class="pclose" @click="closePanel">×</button>
      </div>

      <div class="pbody">
        <div v-if="open === 'prompt'">
          <div class="dh">{{ t('surrealizer.flow.dPrompt') }}</div>
          <textarea class="ta" v-model="inputText" :placeholder="t('surrealizer.flow.nPrompt')"></textarea>
        </div>

        <div v-else-if="open === 'clipL' || open === 'clipG'">
          <div class="dh">{{ t('surrealizer.flow.dReader') }}</div>
          <div class="mut">{{ t('surrealizer.flow.dReaderClip') }}</div>
        </div>

        <div v-else-if="open === 't5'">
          <div class="dh">{{ t('surrealizer.flow.dReader') }}</div>
          <div class="mut">{{ t('surrealizer.flow.dReaderT5') }}</div>
        </div>

        <div v-else-if="open === 'fusion'" class="fus">
          <div class="fcol">
            <div class="al">α = {{ f2(alphaFaktor) }}</div>
            <input
                type="range"
                :min="ALPHA_POSITIONS.min"
                :max="ALPHA_POSITIONS.max"
                :step="ALPHA_POSITIONS.step"
                :aria-valuetext="'α = ' + f2(alphaFaktor)"
                v-model.number="alphaPos"
              />
            <ChipSelect v-model="fusionChoice" :options="strategyOptions" :columns="2" />
            <div class="fx">
              V = <b :class="kc < 0 ? 'inv' : 'cl'">{{ f2(kc) }}</b>·CLIP
              <b :class="kt < 0 ? 'inv' : 't5c'">{{ kt < 0 ? '−' : '+' }} {{ f2(Math.abs(kt)) }}</b>·T5
            </div>
          </div>
          <SayableFieldMap :alpha="alphaFaktor" :strategy="fusionStrategy" class="fmap" />
        </div>

        <div v-else-if="open === 'c'">
          <div class="mut">{{ t('surrealizer.flow.dC') }}</div>
        </div>

        <div v-else-if="open === 'gen'">
          <div class="dh">{{ t('surrealizer.flow.dGen') }}</div>
          <button class="run" :disabled="!inputText.trim() || isExecuting" @click="executeWorkflow">
            {{ isExecuting ? t('surrealizer.flow.running') : '▶ ' + t('surrealizer.flow.run') }}
          </button>
          <div v-if="isExecuting" class="prog"><div class="bar" :style="{ width: generationProgress + '%' }"></div></div>
        </div>

        <div v-else>
          <div class="dh">{{ t('surrealizer.flow.dImage') }}</div>
          <div v-if="primaryOutput" class="imgwrap"><img :src="primaryOutput" alt="" /></div>
          <div v-else class="ph">
            <span v-if="isExecuting">{{ t('surrealizer.flow.running') }} · {{ Math.round(generationProgress) }}%</span>
            <span v-else-if="generationErrorMessage" class="err">{{ generationErrorMessage }}</span>
            <span v-else>{{ t('surrealizer.flow.dImage') }}</span>
          </div>
          <div v-if="isExecuting" class="prog"><div class="bar" :style="{ width: generationProgress + '%' }"></div></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// DEPRECATED (2026-08-11) — not finished, and it does not do the job on the
// Image Lab's Encoder Fusion tile, which opens surrealizer.vue again. NOT to
// be deleted with the others: the node band is to be salvaged as a PROCESS
// DISPLAY, as a display of where a run stands, not as the control
// surface it is here. See docs/devserver_todos.md.
// Rendered both as its own page and inside the Image Lab. Embedded it sits in
// the lab's page frame, so it must not claim a full viewport of its own.
defineProps<{ embedded?: boolean }>()
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { postDirectRun } from '@/services/directRun'
import ChipSelect from '@/components/ChipSelect.vue'
import SayableFieldMap from '@/components/SayableFieldMap.vue'
import {
  ALPHA_POSITIONS,
  alphaScaleFor,
  alphaToPos,
  fusionWeights,
  posToAlpha,
  isFusionStrategy,
} from '@/lib/fusionWeights'
import type { FusionStrategy } from '@/lib/fusionWeights'
import { edgeBetween } from '@/composables/useFlowStage'
import { usePageContextStore } from '@/stores/pageContext'
import type { PageContext } from '@/composables/usePageContext'

import { STANDARD_SEED } from '@/composables/useSeedAutomatic'
const { t } = useI18n()

type NodeId = 'prompt' | 'clipL' | 'clipG' | 't5' | 'fusion' | 'c' | 'gen' | 'image'
type NodeKind = 'in' | 'enc' | 'mix' | 'data' | 'op' | 'out'
interface FlowRect {
  x: number
  y: number
  w: number
  h: number
}
interface FlowNode {
  id: NodeId
  kind: NodeKind
  r: FlowRect
}

const W = 1000
const H = 420
const RECEDE = 0.55

const NODES: FlowNode[] = [
  { id: 'prompt', kind: 'in', r: { x: 20, y: 175, w: 120, h: 70 } },
  { id: 'clipL', kind: 'enc', r: { x: 190, y: 80, w: 110, h: 50 } },
  { id: 'clipG', kind: 'enc', r: { x: 190, y: 185, w: 110, h: 50 } },
  { id: 't5', kind: 'enc', r: { x: 190, y: 290, w: 110, h: 50 } },
  { id: 'fusion', kind: 'mix', r: { x: 350, y: 160, w: 150, h: 100 } },
  { id: 'c', kind: 'data', r: { x: 548, y: 192, w: 36, h: 36 } },
  { id: 'gen', kind: 'op', r: { x: 624, y: 160, w: 150, h: 100 } },
  { id: 'image', kind: 'out', r: { x: 820, y: 145, w: 155, h: 130 } },
]
const RMAP = Object.fromEntries(NODES.map((n) => [n.id, n.r])) as Record<NodeId, FlowRect>

const EDGES: [NodeId, NodeId][] = [
  ['prompt', 'clipL'],
  ['prompt', 'clipG'],
  ['prompt', 't5'],
  ['clipL', 'fusion'],
  ['clipG', 'fusion'],
  ['t5', 'fusion'],
  ['fusion', 'c'],
  ['c', 'gen'],
  ['gen', 'image'],
]

const edgeLines = computed(() =>
  // Touch each box at its natural centre-to-centre border crossing (shared with
  // the flow stage) — not the old right-mid -> left-mid, which is correct only
  // for horizontal neighbours and made every diagonal edge look off.
  EDGES.map(([a, b]) => edgeBetween(RMAP[a], RMAP[b]))
)

const viewportEl = ref<HTMLElement | null>(null)
const vw = ref(1000)
let resizeObserver: ResizeObserver | null = null
onMounted(() => {
  if (viewportEl.value) {
    vw.value = viewportEl.value.clientWidth || 1000
    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) vw.value = entry.contentRect.width
      }
    })
    resizeObserver.observe(viewportEl.value)
  }
})
onBeforeUnmount(() => {
  resizeObserver?.disconnect()
})

/** Panel gesture: the map recedes, the chosen node unfolds onto a fixed, predictable stage below. */
const open = ref<NodeId | null>('prompt')
function toggleNode(id: NodeId) {
  open.value = open.value === id ? null : id
}
function closePanel() {
  open.value = null
}

const baseScale = computed(() => Math.min(1, vw.value / W))
const sOpen = computed(() => baseScale.value * RECEDE)
const worldTransform = computed(() => {
  const s = open.value !== null ? sOpen.value : baseScale.value
  const tx = (vw.value - W * s) / 2
  const ty = open.value !== null ? 6 : 0
  return `translate(${tx}px, ${ty}px) scale(${s})`
})
const mapH = computed(() =>
  Math.round(open.value !== null ? H * sOpen.value + 12 : H * baseScale.value)
)
const anchorX = computed(() => {
  if (open.value === null) return 0
  const r = RMAP[open.value]
  const tx = (vw.value - W * sOpen.value) / 2
  return tx + (r.x + r.w / 2) * sOpen.value
})

function nodeLabel(id: NodeId): string {
  switch (id) {
    case 'prompt':
      return t('surrealizer.flow.nPrompt')
    case 'clipL':
      return 'CLIP-L'
    case 'clipG':
      return 'CLIP-G'
    case 't5':
      return 'T5-XXL'
    case 'fusion':
      return t('surrealizer.flow.nMix')
    case 'c':
      return 'c'
    case 'gen':
      return t('surrealizer.flow.nGen')
    case 'image':
      return t('surrealizer.flow.nImage')
  }
}

const inputText = ref('')
const alphaFaktor = ref<number>(0)
// One instrument, one starting point, whichever door it is opened by. One
// switch stands under the slider, „Same prompt" / „Adapted prompts", and it
// switches the prompts, never the arithmetic: on „Same prompt" the prompt
// goes to all three encoders as it stands; on „Adapted prompts" the route has
// a language model write one prompt per model, a keyword list for the CLIP
// encoders and a prose paragraph for T5 (views/surrealizer.vue,
// lib/fusionWeights). legacy and dual_alpha are not here — a strategy is the
// object of study on the Fusion Workbench, not a setting here.
const fusionStrategy = ref<FusionStrategy>('centered_fade')
const positions = [
  { value: 'centered_fade', key: 'samePrompt' },
  { value: 'two_interceptions', key: 'adaptedPrompts' },
] as const
const validStrategies: FusionStrategy[] = positions.map(x => x.value)
const clampStrategy = (v: string): FusionStrategy =>
  isFusionStrategy(v) && validStrategies.includes(v) ? v : 'centered_fade'
const strategyOptions = computed(() =>
  positions.map(x => ({
    value: x.value,
    label: t('surrealizer.' + x.key),
    title: t('surrealizer.' + x.key + 'Title'),
  }))
)
// Switching the position leaves the handle and the alpha where they stand;
// both positions run the same arithmetic on the same axis (views/surrealizer.vue).
const fusionChoice = computed({
  get: () => fusionStrategy.value,
  set: (v: string) => { fusionStrategy.value = clampStrategy(v) },
})
const ALPHA_SCALE = computed(() => alphaScaleFor(fusionStrategy.value))
const negativePrompt = ref('')
const cfgScale = ref(5.5)
const seed = ref(STANDARD_SEED)
const randomSeed = ref(true)

const isExecuting = ref(false)
const generationProgress = ref(0)
const generationErrorMessage = ref('')
const primaryOutput = ref<string | null>(null)

// The same weights the field map beside this line draws, and the same ones the
// run will use. Written out here once as the plain LERP, it disagreed with both
// as soon as a strategy other than legacy was picked.
const weights = computed(() => fusionWeights(alphaFaktor.value, fusionStrategy.value))
// The slider carries a POSITION and alpha is read off it: the anchors at +/-1
// are what this axis is for, and on a linear -75..75 track they sat within
// 1.3 % of the middle. lib/fusionWeights holds both directions of the mapping.
const alphaPos = computed({
  get: () => alphaToPos(alphaFaktor.value, ALPHA_SCALE.value),
  set: (p: number) => {
    alphaFaktor.value = posToAlpha(p, ALPHA_SCALE.value)
  },
})
watch([alphaFaktor, fusionStrategy], () => {
  const { min, max } = ALPHA_SCALE.value
  if (alphaFaktor.value < min) alphaFaktor.value = min
  else if (alphaFaktor.value > max) alphaFaktor.value = max
})
const kc = computed(() => weights.value.clip)
const kt = computed(() => weights.value.t5)
function f2(x: number) {
  return x.toFixed(2).replace('.', ',')
}

// Where V sits between the two readings, as ONE number: how far T5 outweighs
// CLIP. Under legacy this is the 2a-1 it was written as; under centered_fade it
// is 0 at the middle, where the old expression put the badge at pure CLIP.
const miniSpread = computed(() => 40 * (kt.value - kc.value))
const miniD = computed(() => {
  const dx = miniSpread.value
  if (Math.abs(dx) <= 50) return dx
  return Math.sign(dx) * 50 * (1 + 0.2 * Math.log(Math.abs(dx) / 50))
})
const miniVx = computed(() => 30 + miniD.value * 0.24)
const miniVOutside = computed(() => Math.abs(miniSpread.value) > 50)

async function executeWorkflow() {
  if (!inputText.value.trim() || isExecuting.value) return
  isExecuting.value = true
  generationErrorMessage.value = ''
  primaryOutput.value = null
  generationProgress.value = 0
  open.value = null

  const runSeed = randomSeed.value ? Math.floor(Math.random() * 2147483647) : seed.value
  const target = 98
  // A simulated ramp: the run is ComfyUI's, and the Diffusers progress of
  // the GPU service is another run's.
  const ramp = window.setInterval(() => {
    if (generationProgress.value < target) generationProgress.value = Math.min(target, generationProgress.value + 0.18)
  }, 100)

  try {
    const r = await postDirectRun<any>({
      prompt: inputText.value,
      output_config: 'surrealization',
      // Both chips read the axis in the same units (lib/fusionWeights).
      alpha_factor: alphaFaktor.value,
      seed: runSeed,
      negative_prompt: negativePrompt.value,
      cfg: cfgScale.value,
      fusion_strategy: fusionStrategy.value,
    })
    if (r.data && r.data.status === 'success') {
      const url = r.data.media_output?.url
      if (url) {
        primaryOutput.value = url
        generationProgress.value = 100
      } else {
        generationErrorMessage.value = t('surrealizer.flow.err')
      }
    } else {
      generationErrorMessage.value = (r.data && r.data.message) || t('surrealizer.flow.err')
    }
  } catch (e: any) {
    generationErrorMessage.value = e?.message || t('surrealizer.flow.err')
  } finally {
    window.clearInterval(ramp)
    isExecuting.value = false
    window.setTimeout(() => {
      open.value = 'image'
    }, 250)
  }
}
const pageContextStore = usePageContextStore()

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'surrealizer_flow',
  pageDescription:
    'Encoder Fusion als Graph — im Diffusion Lab die Kachel „Encoder Fusion", ' +
    'daneben unter /surrealizer-flow erreichbar. Dieselbe Sache wie die ' +
    'klassische Form, nur als Fluss gezeichnet: Prompt, die drei Leser ' +
    '(CLIP-L, CLIP-G, T5-XXL), die Fusion mit ihrem α, die Erzeugung, das ' +
    'Bild. Ein Klick auf einen Knoten öffnet ihn, ein Klick daneben schließt ' +
    'ihn. Einstellbar sind hier drei Dinge: der Prompt, der α-Regler und die ' +
    'Fusion. Der Regler läuft von −75 bis 75, aber nicht gleichmäßig: das Band ' +
    'zwischen den beiden Ankern, in dem sich das Verhältnis von CLIP zu T5 ' +
    'einstellen lässt, nimmt 30 % je Hälfte ein, alles jenseits davon ist ' +
    'logarithmisch. Zwei Fusionen stehen zur Wahl: Centered Fade mit Ankern ' +
    'bei −1 (nur CLIP), 0 (beide voll) und 1 (nur T5), und Original Fusion — ' +
    'der ComfyUI-Workflow von 2025, wie er dort lief: zwei getrennt ' +
    'geschriebene Prompts, CLIP-L allein gegen T5, Anker bei 0 (nur CLIP-L) ' +
    'und 1 (nur T5). Negativ-Prompt (leer) und CFG (5,5) ' +
    'stehen fest im Code, der Seed ist bei jedem Lauf ein anderer, und ' +
    'ein Ergebnis lässt sich von hier aus nicht behalten. Wer das braucht, ' +
    'nimmt die klassische Form unter /surrealizer.',
  pageContent: {
    inputText: inputText.value,
  },
}))

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true, deep: true })

onBeforeUnmount(() => {
  pageContextStore.clearContext()
})
</script>

<style scoped>
.flow-view.embedded { min-height: 0; }
.flow-view { min-height: 100%; background: var(--bg-base); color: #e8e8e8; padding: 0 0 2rem; }
.topbar { display: flex; align-items: center; padding: 12px 18px; border-bottom: 1px solid var(--surface-2); }
.topbar .tt { font-size: 14px; font-weight: 400; white-space: nowrap; }
.topbar .hint { font-size: 11.5px; color: #6a6a6a; margin-left: 14px; }
.topbar .legacy { margin-left: auto; font-size: 13px; color: #7fb2ff; text-decoration: none; white-space: nowrap; }

.viewport { position: relative; overflow: hidden; background: var(--bg-base); transition: height 0.5s cubic-bezier(0.22, 0.9, 0.35, 1); }
.world { position: absolute; left: 0; top: 0; width: 1000px; height: 420px; transform-origin: 0 0; transition: transform 0.5s cubic-bezier(0.22, 0.9, 0.35, 1); }

.edges { position: absolute; left: 0; top: 0; pointer-events: none; }
.edges line { stroke: #5a5a5a; stroke-width: 1; stroke-dasharray: 3 6; animation: dashf 3.2s linear infinite; }
.edges.working line { stroke: #7fb2ff; animation-duration: 0.8s; }
@keyframes dashf { to { stroke-dashoffset: -18; } }

.nd { position: absolute; box-sizing: border-box; border-radius: 10px; border: 1px solid #4a4270; background: #2e2650; cursor: pointer; overflow: hidden; transition: border-color 0.2s, opacity 0.4s; }
.nd.enc { background: #28402f; border-color: #3f6a4c; }
.nd.mix { background: #2e2650; border-color: #7f77dd; border-width: 1.5px; }
.nd.data { background: #3a2740; border-color: #8a5aa0; border-radius: 50%; }
.nd.op { background: #1d2f45; border-color: #3f6a9c; }
.nd.in, .nd.out { background: #4a2b2f; border-color: #7a4046; }
.nd:hover { border-color: #b8c2d8; }
.nd.focus { border-color: #eef2f8; border-width: 1.5px; }
.world.receded .nd { opacity: 0.5; }
.world.receded .nd.focus, .world.receded .nd:hover { opacity: 1; }

.lbl { position: relative; font-size: 12px; font-weight: 400; color: #e8e8e8; padding: 6px 9px; white-space: nowrap; }
.nd.data .lbl { text-align: center; padding: 9px 0 0; }
.sub { position: relative; font-size: 11px; color: #b8b8b8; padding: 0 9px; }
.thumb { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; opacity: 0.85; }

.viz { position: absolute; bottom: 6px; left: 0; right: 0; display: flex; justify-content: center; opacity: 0; transition: opacity 0.25s; pointer-events: none; }
.nd:hover .viz { opacity: 1; }
.pulse { width: 7px; height: 7px; border-radius: 50%; background: #7fb2ff; animation: puls 2s ease-in-out infinite; }
.pulse.hot { animation-duration: 0.7s; background: #9fd0ff; }
@keyframes puls { 0%, 100% { opacity: 0.25; } 50% { opacity: 1; } }

.strip { position: absolute; left: 0; right: 0; bottom: 0; height: 4px; background: rgba(255, 255, 255, 0.07); }
.stripbar { height: 100%; background: #4a9eff; transition: width 0.2s; }

.connector { display: block; }
.connector line { stroke: #5a5a5a; stroke-width: 1; stroke-dasharray: 3 6; }

.panel { max-width: 980px; height: 480px; box-sizing: border-box; margin: 0 auto; background: var(--bg-base); border: 1px solid var(--surface-3); border-radius: 14px; padding: 16px 20px; display: flex; flex-direction: column; animation: pin 0.25s ease; }
@keyframes pin { from { opacity: 0; transform: translateY(10px); } }
.phead { display: flex; align-items: center; margin-bottom: 10px; }
.pname { font-size: 13px; color: #8a8a8a; }
.pclose { margin-left: auto; background: transparent; border: none; color: #8a8a8a; font-size: 20px; line-height: 1; cursor: pointer; padding: 2px 6px; }
.pclose:hover { color: #e8e8e8; }
.pbody { flex: 1; min-height: 0; overflow: auto; }

.dh { font-size: 12px; color: #8a8a8a; margin-bottom: 10px; }
.mut { color: #9a9a9a; font-size: 14px; line-height: 1.55; max-width: 620px; }
.ta { width: 100%; height: 150px; box-sizing: border-box; background: var(--bg-base); border: 1px solid var(--surface-3); border-radius: 9px; color: #e0e0e0; padding: 12px; font-size: 15px; resize: none; }

.fus { display: flex; gap: 26px; align-items: flex-start; flex-wrap: wrap; }
.fcol { flex: 1 1 300px; min-width: 0; display: flex; flex-direction: column; gap: 12px; }
.fmap { flex: 0 0 340px; }
.al { font-size: 22px; font-weight: 400; color: #4a9eff; }
.fx { font-family: 'SF Mono', monospace; font-size: 14px; color: #cfcfcf; }
.fx b { font-weight: 700; }
.cl { color: #4a9eff; }
.t5c { color: #f0a940; }
.inv { color: #e0568a; }
.run { padding: 9px 22px; border: 1px solid var(--surface-4); border-radius: 9px; color: #cfcfcf; cursor: pointer; font-size: 14px; background: transparent; }
.run:disabled { opacity: 0.4; cursor: default; }
.run:hover:not(:disabled) { background: var(--surface-2); }
.prog { height: 6px; border-radius: 3px; background: var(--surface-2); overflow: hidden; margin-top: 12px; }
.prog .bar { height: 100%; background: #4a9eff; transition: width 0.2s; }

.imgwrap { text-align: center; }
.imgwrap img { max-width: 100%; max-height: 385px; border-radius: 10px; }
.ph { height: 200px; border: 1px dashed var(--surface-4); border-radius: 10px; display: flex; align-items: center; justify-content: center; color: #7a7a7a; }
.err { color: #e0568a; }
</style>
