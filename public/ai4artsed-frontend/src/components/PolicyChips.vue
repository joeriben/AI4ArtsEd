<!--
  PolicyChips — the standing conditions of a session, at the right edge of the
  header. One small panel, read here and never chosen: where a run stands in
  the queue and how long that is, what the machine draws right now and what
  that costs in CO2, then the DSGVO setting and the age/content filter that
  holds.

  The QUEUE column is the leftmost, and it is one question throughout: where
  does this session stand. A run of this session's that is waiting gives its
  own place; with none waiting, the place a press made now would take. Both are
  the same sentence for a visitor - "how far am I from the card" - and holding
  them to one meaning is why the number can stand alone. The column was added
  after the platform told somebody the queue was full while a single training
  held the card for six and a half hours.

  The colour reads the WAIT, not who is waiting: next in line
  or under a minute green, anything past that amber, a card held by a training
  red. Red is the state where waiting stops being the right word — the queue
  is not moving, and the visitor is better off doing something else.

  The panel carries the only frame; the four cells are flat tints on one grid,
  so their widths line up and the group reads as one instrument rather than
  four loose marks.

  The DSGVO chip states what the settings show — the provider preset of the
  model matrix (/api/settings/dsgvo-setting) — and nothing else. It derives
  nothing and says nothing of its own about any service. On the canvas it stays
  amber: a board is wired by hand, and the setting does not speak for what
  somebody drops onto it.

  The two energy chips read /api/settings/gpu-realtime — the same endpoint, the
  same factor and the same formula the edutainment animations and Resona's
  GIVEN MACHINE block use, so the platform speaks one voice. What is readable
  is the GRAPHICS CARD, not the machine around it: RAPL is root-only on this
  host and no power supply reports itself. The tooltip says so, and when
  nothing is readable the two chips are simply absent rather than guessed.
-->
<template>
  <span class="policy-panel" :class="{ 'has-energy': watts !== null, 'has-queue': queueOk }">
    <StatusBadge
      v-if="queueOk"
      :tone="queueTone"
      flat
      compact
      class="cell-unit"
      :title="queuePlaceTitle"
    >{{ queuePlaceLabel }}</StatusBadge>
    <StatusBadge
      v-if="watts !== null"
      tone="load"
      flat
      compact
      class="cell-unit"
      :style="loadStyle"
      :title="powerTitle"
    >{{ powerLabel }}</StatusBadge>
    <StatusBadge :tone="dsgvoTone" flat compact :title="dsgvoTitle">DS-GVO</StatusBadge>
    <StatusBadge
      v-if="queueOk"
      :tone="queueTone"
      flat
      compact
      class="cell-unit"
      :title="queueTimeTitle"
    >{{ queueTimeLabel }}</StatusBadge>
    <template v-if="watts !== null">
      <StatusBadge
        v-if="co2PerHour !== null"
        tone="load"
        flat
        compact
        class="cell-unit"
        :style="loadStyle"
        :title="co2Title"
      >{{ co2Label }}</StatusBadge>
      <!-- The grid is read row by row: without this the filter would slide up
           into the energy column when the CO2 factor is missing. -->
      <span v-else class="cell-empty"></span>
    </template>
    <StatusBadge :tone="filterTone" flat compact :title="filterTitle">{{ filterLabel }}</StatusBadge>
  </span>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import StatusBadge from './StatusBadge.vue'
import { useSafetyLevelStore } from '@/stores/safetyLevel'
import { useDeviceId } from '@/composables/useDeviceId'
import { durationLabel } from '@/composables/useGenerationStream'
import { apiBase } from '@/services/labApi'

const { t, locale } = useI18n()
const route = useRoute()
const safety = useSafetyLevelStore()
const deviceId = useDeviceId()

const dsgvoState = ref<string>('')

async function read() {
  try {
    const { data } = await axios.get(apiBase() + '/api/settings/dsgvo-setting', { withCredentials: true })
    dsgvoState.value = data.state || ''
  } catch (e) {
    console.error('[PolicyChips] Failed to read the DSGVO setting:', e)
    // Cannot ask, so nothing is claimed.
    dsgvoState.value = ''
  }
}

onMounted(() => {
  read()
  if (!safety.loaded) safety.fetchLevel()
})

// A setting changed on the settings page must not leave a stale colour behind
// on the next place the session goes to.
watch(() => route.path, read)

/** A board is wired by hand; the setting does not speak for it. */
const onCanvas = computed(() => route.path.startsWith('/canvas'))

const DSGVO_TONES: Record<string, 'available' | 'caution' | 'unavailable'> = {
  conform: 'available',
  preset_not_conform: 'unavailable',
  models_flagged: 'unavailable',
  unknown: 'caution'
}

const settingsTone = computed(() => DSGVO_TONES[dsgvoState.value] || 'caution')

/**
 * The canvas can only ever be WORSE than what the settings hold, never better:
 * a board is wired by hand, so green cannot be claimed there — but a provider
 * the settings hold as not conform stays red on a board too.
 */
const dsgvoTone = computed(() => {
  if (!onCanvas.value) return settingsTone.value
  return settingsTone.value === 'unavailable' ? 'unavailable' : 'caution'
})
const dsgvoTitle = computed(() => {
  const key = DSGVO_TONES[dsgvoState.value]
    ? `policyChips.dsgvo_${dsgvoState.value}`
    : 'policyChips.dsgvoUnread'
  if (onCanvas.value && settingsTone.value !== 'unavailable') return t('canvas.dsgvoTooltip')
  return t(key)
})

// The four levels that have a colour and a wording. `open` is a level the
// platform can hold (services/safety_level_resolver.py, and a course can be
// set to it) but no colour and no wording have been given for it — it falls
// through to amber and carries the level's own name until they are.
const LEVEL_TONES: Record<string, 'available' | 'caution' | 'unavailable'> = {
  kids: 'available',
  youth: 'available',
  adult: 'unavailable',
  research: 'unavailable'
}

// Until the level has actually been read, the chip states nothing: the store
// holds `kids` from the first tick and keeps it when the call fails, which is
// the right default for a GATE and a false statement for a display.
const filterTone = computed(() =>
  safety.resolved ? (LEVEL_TONES[safety.level] || 'caution') : 'idle'
)
// `te` only ever asks the CURRENT locale, and the labels live in English until
// the batch translation lands — so the known set decides, not a lookup.
// `research` is the one label that does not translate: it stands in every
// language as it stands here, like DS-GVO beside it.
const RESEARCH_LABEL = 'SAFETY=OFF'
const filterLabel = computed(() => {
  if (!safety.resolved) return '—'
  if (safety.level === 'research') return RESEARCH_LABEL
  return safety.level in LEVEL_TONES ? t(`policyChips.levels.${safety.level}`) : safety.level
})
// No tooltip before an answer: an empty title is silence, and silence is what
// the chip has to say here. No wording has been set for the unresolved state.
const filterTitle = computed(() =>
  safety.resolved ? t('policyChips.filter', { level: filterLabel.value }) : ''
)

// ── Where this session stands at the card ───────────────────────────────────
// One endpoint answers both halves of the wait: the gate's own plan, in the
// order it will really run, plus the runs that have been pressed and are still
// being translated, intercepted and checked. Neither half can answer alone.
//
// The distinction the platform keeps everywhere: an unreachable gate is NOT an
// empty queue. A service that cannot be asked takes the column away; a service
// that answers "I cannot see the card" leaves it standing with a dash in it.

/** Whether the forecast can be asked at all. False takes the column away. */
const queueOk = ref(false)
/** The place — this session's own where it has one, else the next press's. */
const queuePlace = ref<number | null>(null)
/** Seconds until that place reaches the card; null where nothing was measured. */
const queueWaitS = ref<number | null>(null)
/** Whether the place belongs to a run of this session's or to a press not made. */
const queueMine = ref(false)
/**
 * What holds the card for hours rather than seconds, where something does.
 * `lora_training` is the gate's own long-hold kind (LONG_HOLD_KINDS in
 * gpu_service/services/gpu_admission.py); `beyond` is a wait past the point
 * where the gate would still hold a place at all. Either one turns the column
 * red: this is no longer a queue that moves.
 */
const queueBlock = ref<'lora_training' | 'beyond' | ''>('')

async function readQueue(onSchedule = false) {
  if (onSchedule && typeof document !== 'undefined' && document.hidden) return
  try {
    const { data } = await axios.get(apiBase() + '/api/schema/pipeline/queue-forecast', {
      params: { device_id: deviceId },
    })
    queueOk.value = true
    if (data && data.gate_reachable === false) {
      // The card cannot be seen. Nothing is known, and nothing is claimed.
      queuePlace.value = null
      queueWaitS.value = null
      queueMine.value = false
      queueBlock.value = ''
      return
    }
    const holder = data?.active?.kind
    queueBlock.value =
      holder === 'lora_training'
        ? holder
        : data?.beyond_promise === true
          ? 'beyond'
          : ''
    const me = data?.me
    const behind = (typeof data?.queue_length === 'number' ? data.queue_length : 0) + 1
    if (me && me.state === 'waiting') {
      queuePlace.value = me.position
      queueWaitS.value = typeof me.expected_start_in_s === 'number' ? me.expected_start_in_s : null
      queueMine.value = true
    } else if (me && me.state === 'preparing') {
      // Pressed, still being prepared: it will queue behind everything known.
      queuePlace.value = behind
      queueWaitS.value = typeof me.expected_start_in_s === 'number' ? me.expected_start_in_s : null
      queueMine.value = true
    } else {
      // Nothing of this session's is waiting — including while it HAS the card.
      // Then the question is the other one, and it is the same question: where
      // would a press land now.
      queuePlace.value = behind
      queueWaitS.value = typeof data?.expected_wait_for_a_new_press_s === 'number'
        ? data.expected_wait_for_a_new_press_s
        : null
      queueMine.value = false
    }
  } catch {
    // Cannot ask: the column leaves, the way the energy cells do.
    queueOk.value = false
  }
}

/** Under a minute is the platform's own "straight through": see the label. */
const queueUnderMinute = computed(
  () => queueWaitS.value !== null && queueWaitS.value < 60
)

/**
 * The colour reads the WAIT, not who is waiting:
 * next in line or under a minute is green, anything past that amber, and a
 * card held by a training — or a wait the gate would no longer hold a place
 * for — red. Both cells take the same one: the column is one statement, and
 * two colours in it would read as two.
 *
 * Whose place it is stays in the tooltip. It was the colour for a day, and
 * that made the column say who rather than how long.
 */
const queueTone = computed(() => {
  if (queuePlace.value === null) return 'idle'
  if (queueBlock.value) return 'unavailable'
  if (queuePlace.value <= 1 || queueUnderMinute.value) return 'available'
  return 'caution'
})

const queuePlaceLabel = computed(() =>
  queuePlace.value === null ? '\u2014' : `#${num(queuePlace.value, 0)}`
)

/**
 * The wait in the column's own unit. Under five seconds nothing was measured
 * and under a minute a whole-minute figure would round the wait to zero, which
 * reads as "now" — so both are said as less than a minute, and only an
 * unmeasured wait gets the dash.
 */
const queueTimeLabel = computed(() => {
  if (queuePlace.value === null || queueWaitS.value === null) return '\u2014'
  if (queueUnderMinute.value) return t('policyChips.queueUnderMinute')
  return durationLabel(t, queueWaitS.value) || t('policyChips.queueUnderMinute')
})

/** Why the column is red, in one sentence, in front of whatever else it says. */
const queueBlockLine = computed(() => {
  if (!queueBlock.value) return ''
  if (queueBlock.value === 'beyond') return t('policyChips.queueBlockedLong')
  return t('policyChips.queueBlockedLora')
})

function withBlock(line: string): string {
  return queueBlockLine.value ? `${queueBlockLine.value} ${line}` : line
}

const queuePlaceTitle = computed(() => {
  if (queuePlace.value === null) return t('policyChips.queueUnseen')
  return withBlock(queueMine.value
    ? t('policyChips.queuePlaceMine', { n: queuePlace.value })
    : t('policyChips.queuePlaceNext', { n: queuePlace.value }))
})

const queueTimeTitle = computed(() => {
  if (queuePlace.value === null) return t('policyChips.queueUnseen')
  if (queueWaitS.value === null) return withBlock(t('policyChips.queueTimeUnknown'))
  const time = queueTimeLabel.value
  return withBlock(queueMine.value
    ? t('policyChips.queueTimeMine', { time })
    : t('policyChips.queueTimeNext', { time }))
})

// ── What the machine draws ──────────────────────────────────────────────────
// nvidia-smi is the only meter this host has: the CPU package counter is
// root-only since the Platypus mitigation and no power supply reports itself.
// So the card is what the chip states, and the tooltip says that it is the
// card.
const POLL_MS = 5000

const watts = ref<number | null>(null)
const wattLimit = ref<number | null>(null)
const co2PerKwh = ref<number | null>(null)
let timer: number | null = null

/** Back in view: catch up at once rather than waiting out the interval. */
function onVisible() {
  if (!document.hidden) {
    readEnergy()
    readQueue()
  }
}

async function readEnergy(onSchedule = false) {
  // A tab nobody is looking at does not need to run nvidia-smi every 5 s. Only
  // the SCHEDULED read stands down, though: a first read always happens, or a
  // window that reports itself hidden for its whole life (an embedded panel,
  // for one) would show the chips empty forever.
  if (onSchedule && typeof document !== 'undefined' && document.hidden) return
  try {
    const { data } = await axios.get(apiBase() + '/api/settings/gpu-realtime')
    if (data && data.available === true && typeof data.power_draw_watts === 'number') {
      watts.value = data.power_draw_watts
      wattLimit.value = typeof data.power_limit_watts === 'number' && data.power_limit_watts > 0
        ? data.power_limit_watts : null
      co2PerKwh.value = typeof data.co2_per_kwh_grams === 'number' ? data.co2_per_kwh_grams : null
    } else {
      // Unreadable is not zero: the chips leave rather than state a number.
      watts.value = null
    }
  } catch {
    watts.value = null
  }
}

onMounted(() => {
  readEnergy()
  readQueue()
  timer = window.setInterval(() => {
    readEnergy(true)
    readQueue(true)
  }, POLL_MS)
  document.addEventListener('visibilitychange', onVisible)
})

onUnmounted(() => {
  if (timer !== null) window.clearInterval(timer)
  document.removeEventListener('visibilitychange', onVisible)
})

function num(v: number, digits: number): string {
  return v.toLocaleString(locale.value, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  })
}

const powerLabel = computed(() => watts.value === null ? '' : `${num(watts.value, 0)} W`)
const powerTitle = computed(() => {
  if (watts.value === null) return ''
  const w = num(watts.value, 0)
  return wattLimit.value === null
    ? t('policyChips.powerNoLimit', { watts: w })
    : t('policyChips.power', { watts: w, limit: num(wattLimit.value, 0) })
})

// The platform's one energy formula: Wh/h = W, and g CO2 = kWh x factor.
const co2PerHour = computed(() =>
  watts.value === null || co2PerKwh.value === null
    ? null
    : (watts.value / 1000) * co2PerKwh.value
)
const co2Label = computed(() => {
  const v = co2PerHour.value
  // Under ten grams a whole number would round the difference away.
  return v === null ? '' : `${num(v, v < 10 ? 1 : 0)} g CO₂/h`
})
// Cool to hot, and nothing else: the two energy cells state a continuum, so
// they take a colour off a ramp rather than one of the named tones. Blue is
// the card at rest, orange the card at its limit — the limit it reports, so a
// 450 W card is not held against a 600 W scale. The neutral in the middle is
// the crossing point of the ramp, not a state.
type Rgb = [number, number, number]
const COOL: Rgb = [100, 181, 246]
const TEPID: Rgb = [168, 168, 168]
const HOT: Rgb = [255, 167, 38]
// Below this the card is idling, and idling is the cool end of the ramp.
const IDLE_W = 30
// Only if the card does not say what it may draw.
const ASSUMED_LIMIT_W = 600

const loadStyle = computed((): Record<string, string> => {
  const w = watts.value
  if (w === null) return {}
  const ceiling = wattLimit.value ?? ASSUMED_LIMIT_W
  const span = Math.max(1, ceiling - IDLE_W)
  const t = Math.min(1, Math.max(0, (w - IDLE_W) / span))
  const from = t < 0.5 ? COOL : TEPID
  const to = t < 0.5 ? TEPID : HOT
  const k = t < 0.5 ? t * 2 : (t - 0.5) * 2
  const at = (i: 0 | 1 | 2) => Math.round(from[i] + (to[i] - from[i]) * k)
  const rgb = `${at(0)} ${at(1)} ${at(2)}`
  return {
    '--badge-load-fg': `rgb(${rgb})`,
    '--badge-load-bg': `rgb(${rgb} / 0.18)`
  }
})

const co2Title = computed(() => {
  const v = co2PerHour.value
  return v === null ? '' : t('policyChips.co2', {
    grams: num(v, v < 10 ? 1 : 0),
    factor: num(co2PerKwh.value as number, 0)
  })
})
</script>

<style scoped>
.policy-panel {
  display: inline-grid;
  /* Without the two energy cells the panel is one column of two. */
  grid-template-columns: minmax(0, 1fr);
  gap: 2px;
  padding: 3px;
  border: 1px solid var(--surface-4);
  border-radius: 6px;
  background: var(--surface-1);
  vertical-align: middle;
  /* The panel stands to the RIGHT of the fields, and the distance to them is
     more than twice what the fields keep among themselves. */
  margin-inline-start: 2rem;
  /* A squeezed panel is worse than none: the header row would press it to a
     sliver and let the labels run out under the icons. It keeps its width or
     it leaves — see the query below. */
  flex: 0 0 auto;
}

/* Below this the header has no room for it. Measured, not reckoned: with the
   queue column the panel is 233 px wide (three cells of 74 plus gaps and
   padding), and below about 1440 px its right edge starts eating the header's
   own padding — at 1360 px it stands one pixel outside the window. Without the
   queue column the same measurement gave 1280 px, and that is the whole cost
   of the third column: the panel is now away on 1280 and 1366 px screens,
   which is most of the laptops a workshop runs on.

   A squeezed panel is worse than none, so it keeps its width or it leaves. */
@media (max-width: 1439px) {
  .policy-panel {
    display: none;
  }
}

/* Equal columns, all sized to the widest cell in the panel: that is what puts
   the labels on one width instead of six. Which columns there are depends on
   what can be read — the queue where the forecast answers, the energy where
   the card reports itself. */
.policy-panel.has-energy,
.policy-panel.has-queue {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.policy-panel.has-energy.has-queue {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.policy-panel :deep(.status-badge) {
  display: block;
  text-align: center;
}

/* W, g and h are units — their case carries meaning, so these are the two
   cells in the header that do not shout. */
.policy-panel :deep(.cell-unit) {
  text-transform: none;
}
</style>
