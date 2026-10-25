<template>
  <div ref="root" class="circle-title" :style="revealed ? REVEALED : undefined">
    <span
      ref="textEl"
      class="circle-title__text"
      :style="{ fontSize: fontSize + 'px', width: boxWidth + 'px', overflowWrap: wrapAnywhere ? 'anywhere' : 'normal' }"
      >{{ text }}</span
    >
  </div>
</template>

<script setup lang="ts">
/**
 * The name of a round tile, set across the whole disc.
 *
 * A band along the bottom of a circle is the narrowest place there is: at the
 * second line the disc has lost a third of its width, which is why German
 * compounds broke mid-word and sank to eight pixels. Across the disc the text
 * sits where the circle is widest, and the same names carry twice the size.
 *
 * At rest the name is a faint darker impression that leaves the picture whole;
 * under the pointer, or held for a moment, it comes forward. The break points
 * are set in the names themselves (U+00AD) — nothing is ever cut inside a word.
 */
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

const props = withDefaults(defineProps<{ text: string; revealed?: boolean }>(), {
  revealed: false,
})

const LINE_HEIGHT = 1.15
// 400 and 700 are the only weights the platform has (assets/base.css).
const WEIGHT = 700
/** Both states of the one variable the stylesheet reads. */
const REVEALED = { '--circle-title-opacity': '0.8' }

const root = ref<HTMLElement | null>(null)
const textEl = ref<HTMLElement | null>(null)
const fontSize = ref(12)
const boxWidth = ref(0)
/** Set only where no size holds the name whole — see the second search below. */
const wrapAnywhere = ref(false)

let measurer: CanvasRenderingContext2D | null = null

/**
 * The widest piece that cannot be broken: words, and the parts between the
 * break points set in the name. A line has to hold at least this much.
 */
function widestFragment(text: string, px: number, family: string): number {
  if (!measurer) measurer = document.createElement('canvas').getContext('2d')
  if (!measurer) return 0
  measurer.font = `${WEIGHT} ${px}px ${family}`
  let max = 0
  for (const piece of text.split(/[\s\u00AD]+/)) {
    if (piece) max = Math.max(max, measurer.measureText(piece).width)
  }
  return max
}

/**
 * Take the largest size at which the name still stands inside the disc. The
 * width a line may use is not the diameter but the chord at the height of the
 * outermost line — which depends on how many lines there are, which depends on
 * the width. Three passes settle it.
 */
function fit() {
  const box = root.value
  const el = textEl.value
  if (!box || !el) return
  const d = box.clientWidth
  if (d <= 0) return

  const r = d / 2
  const pad = d * 0.08
  const family = getComputedStyle(el).fontFamily
  const minFs = Math.max(8, d * 0.085)
  // On a very small disc the ceiling would fall BELOW the floor and the search
  // would not run once — the name then kept the full square as its width and
  // stood out over the rim. Below roughly 365 px of viewport this is the case.
  const maxFs = Math.max(minFs, d * 0.19)
  const step = Math.max(0.25, d * 0.0025)

  /**
   * One search, from the largest size down. `relaxed` lifts the rule that a
   * word is never broken; everything else is the same.
   */
  function search(el: HTMLElement, relaxed: boolean) {
    el.style.overflowWrap = relaxed ? 'anywhere' : 'normal'
    let last = { fs: minFs, w: Math.max(10, d - 2 * pad), fits: false }
    for (let fs = maxFs; fs >= minFs; fs -= step) {
      el.style.fontSize = `${fs}px`
      let w = d - 2 * pad
      for (let pass = 0; pass < 3; pass++) {
        el.style.width = `${w}px`
        const lines = Math.max(1, Math.round(el.scrollHeight / (fs * LINE_HEIGHT)))
        const half = (lines * fs * LINE_HEIGHT) / 2
        const chord = half >= r ? 0 : 2 * Math.sqrt(r * r - half * half) - 2 * pad
        w = Math.min(d - 2 * pad, Math.max(10, chord))
      }
      el.style.width = `${w}px`
      const lines = Math.max(1, Math.round(el.scrollHeight / (fs * LINE_HEIGHT)))
      const half = (lines * fs * LINE_HEIGHT) / 2
      const fits = half < r && (relaxed || widestFragment(props.text, fs, family) <= w)
      last = { fs, w, fits }
      if (fits) break
    }
    return last
  }

  let found = search(el, false)
  let relaxed = false
  if (!found.fits) {
    // No size holds this name whole. On a disc of forty pixels — a phone — that
    // is the ordinary case for a German compound. A break inside the word is
    // then the lesser harm: the name stays inside the circle instead of being
    // sliced off at its rim.
    const second = search(el, true)
    if (second.fits) {
      found = second
      relaxed = true
    }
  }

  wrapAnywhere.value = relaxed
  el.style.overflowWrap = relaxed ? 'anywhere' : 'normal'
  fontSize.value = found.fs
  boxWidth.value = found.w
}

let raf = 0
function schedule() {
  if (raf) cancelAnimationFrame(raf)
  raf = requestAnimationFrame(() => {
    raf = 0
    fit()
  })
}

let observer: ResizeObserver | null = null

onMounted(() => {
  schedule()
  // Measure again once the webfont is in: the metrics before it are not the
  // metrics the reader gets.
  void document.fonts?.ready?.then(schedule)
  if (typeof ResizeObserver !== 'undefined' && root.value) {
    observer = new ResizeObserver(schedule)
    observer.observe(root.value)
  }
})

onBeforeUnmount(() => {
  if (raf) cancelAnimationFrame(raf)
  observer?.disconnect()
  observer = null
})

watch(
  () => props.text,
  () => void nextTick(schedule)
)
</script>

<style scoped>
.circle-title {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  /* The tile underneath keeps the click, the hold and the hover. */
  pointer-events: none;
}

.circle-title__text {
  display: block;
  font-weight: 700;
  line-height: 1.15;
  color: #000;
  /* A soft light halo. Black alone falls into the dark previews and white alone
     falls into the bright ones; with the halo the same name carries on both.
     Set in em so it holds at every diameter. */
  text-shadow:
    0 0 0.38em rgba(255, 255, 255, 0.75),
    0 0 0.11em rgba(255, 255, 255, 0.9);
  /* Never inside a word — the break points are set in the name itself. */
  word-break: normal;
  overflow-wrap: normal;
  hyphens: manual;
  opacity: var(--circle-title-opacity, 0.3);
  transition: opacity 0.18s ease;
}
</style>
