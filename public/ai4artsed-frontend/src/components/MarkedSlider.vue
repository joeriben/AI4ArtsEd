<!--
  One value on an axis whose places are named.

  The bar, and over it two layers: the words (`.ms-marks`) and the notches
  (`.ms-notches`), both at the same percentage as the value they belong to. Two
  layers so a word may be as wide as it needs while its notch stands exactly on
  its value. Under the bar, where a consumer has any, a third: named STRETCHES
  (`.ms-zones`, since 2026-09-21), each a word under a line that runs out at both
  ends - a place on the axis that is roughly here, without a notch that would say
  where it starts.

  Written for Encoder Fusion's alpha (2026-08-18) and pulled out of it on
  2026-08-19, when Denoising Archaeology needed the same axis with its three
  sections as the named places. The two traps in the CSS below were found on the
  built page during that first build, at the widths the comments name; they are
  the reason those rules look overspecified.

  A consumer must not give this component padding of its own: the words are
  positioned against its padding box and the handle against its content box, and
  they part company as soon as the two differ.
-->
<template>
  <div class="ms-track" :class="{ 'ms-compact': compact }">
    <!-- Marks over the bar, notches on it. -->
    <div class="ms-marks" aria-hidden="true">
      <span
        v-for="mark in marks"
        :key="mark.pct"
        class="ms-mark"
        :style="{ insetInlineStart: mark.pct + '%', width: markWidth, marginInlineStart: markOffset }"
      >
        <b>{{ mark.value }}</b>
        <em v-if="mark.label && !compact">{{ mark.label }}</em>
      </span>
    </div>
    <div class="ms-notches" aria-hidden="true">
      <i v-for="mark in marks" :key="mark.pct" :style="{ insetInlineStart: mark.pct + '%' }"></i>
    </div>
    <input
      type="range"
      class="lab-range ms-range"
      :min="min"
      :max="max"
      :step="step"
      :disabled="disabled"
      :aria-label="ariaLabel"
      :aria-valuetext="valueText || undefined"
      :value="modelValue"
      :style="fillStyle"
      @input="onInput"
      @keydown="onKeydown"
    />
    <!-- The named stretches UNDER the bar. Each word stands centred under a
         line that runs out at both ends: no notch, no number and no edge between
         two zones, because what these words name is a rough orientation and no
         measured boundary. Written for the three sections of Denoising
         Archaeology, which once stood over the bar as marks with exact step
         ranges; exact values in that place were the fault, and as approximate
         zones the words are didactically more helpful. A row in flow, not a
         layer: a word that wraps
         makes the row taller instead of running into whatever stands under the
         axis. Hidden from assistive technology like the marks over the bar; what
         is spoken is `valueText`. -->
    <div v-if="zoneBoxes.length" class="ms-zones" aria-hidden="true">
      <span
        v-for="(zone, i) in zoneBoxes"
        :key="`${i}-${zone.label}`"
        class="ms-zone"
        :style="{ marginInlineStart: zone.gapPct + '%', width: zone.widthPct + '%' }"
      >
        <i></i>
        <em>{{ zone.label }}</em>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
// The track and the handle are `.lab-range` in the shared stylesheet,
// flow-stage.css, which main.ts loads once since 2026-10-10 (until then not
// every surface that carries an axis pulled it in, and this component brought
// it along).
import { computed, nextTick } from 'vue'

/** One named place on the axis: what stands there, and where. */
export interface SliderMark {
  /** The head of the mark, in the axis' own units. */
  value: string | number
  /** What that place means, under the value. Optional. */
  label?: string
  /** Where it stands, 0..100 along the bar. */
  pct: number
}

/** One named stretch of the axis, loosely: roughly from where to where, 0..100. */
export interface SliderZone {
  /** What the stretch is called. */
  label: string
  /** Where it roughly begins, 0..100 along the bar. */
  fromPct: number
  /** Where it roughly ends, 0..100 along the bar. */
  toPct: number
}

const props = withDefaults(defineProps<{
  modelValue: number
  min: number
  max: number
  step?: number
  marks: SliderMark[]
  ariaLabel?: string
  /**
   * What the current value IS, in words, when the bare number does not say it.
   * Denoising Archaeology sends „Step 7 / 25"; without it a screen reader reads
   * „6". The section word left that caption on 2026-08-31, and the zones under
   * the bar (since 2026-09-21) are hidden from assistive technology like the
   * marks, so a section is not spoken on that surface.
   */
  valueText?: string
  /** Nothing to set yet - the axis stands, but it cannot be moved. */
  disabled?: boolean
  /**
   * How much of the axis is actually reachable, 0..100, drawn on the bar. For
   * an axis that fills as a run walks it (Bias Archaeology): only what has been
   * asked can be looked at, and the bar says how far that is. `null` leaves the
   * bar in one tone, which is every other axis.
   */
  fillPct?: number | null
  /**
   * The marks as numbers alone, on one line, with the head room cut to fit.
   * For a column that stacks several axes (Encoder Fusion's a, b and c) the
   * 57 px above each track were most of the column; a compact axis shows no
   * `label` under its numbers.
   */
  compact?: boolean
  /**
   * Named stretches of the axis, drawn under the bar: the three sections of a
   * denoising run on Denoising Archaeology. Each is a word centred under a line
   * that fades out at both ends, so it says roughly where it lies and nothing
   * about where it starts or stops. Most axes have none.
   */
  zones?: SliderZone[]
}>(), {
  step: 1,
  ariaLabel: '',
  valueText: '',
  disabled: false,
  fillPct: null,
  compact: false,
  zones: () => [],
})

const emit = defineEmits<{ 'update:modelValue': [value: number] }>()

function onInput(e: Event) {
  const el = e.target as HTMLInputElement
  emit('update:modelValue', Number(el.value))
  // What comes back may not be what was sent: a consumer may SNAP the value
  // (Encoder Fusion's whole numbers hold the handle) or clamp it.
  // When it does, the bound value does not change, Vue writes nothing to the
  // input, and the handle stays where the finger left it — between two
  // settings, next to a readout that says a third. So the handle is put back
  // on the value, after the parent has had its say.
  nextTick(() => { el.value = String(props.modelValue) })
}

/**
 * An arrow key steps the handle by one position — and on to the next position
 * that CHANGES the bound value, where one does not. A consumer that quantises
 * (Encoder Fusion's whole numbers take the positions around them) leaves the
 * value where it was for a single position, the handle is put back, and from
 * such a value the key would never move: from a 1 on that axis fifteen presses
 * gave 1, 1, 1 … The browser's own stepping is used for the positions
 * (`stepUp`/`stepDown` keep the step's decimals), and a horizontal arrow
 * follows the axis' writing direction as it does natively. Page Up/Down, Home
 * and End stay the browser's: they move far enough to change any value.
 */
async function onKeydown(e: KeyboardEvent) {
  const el = e.target as HTMLInputElement
  const horizontal = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
  const vertical = e.key === 'ArrowUp' ? 1 : e.key === 'ArrowDown' ? -1 : 0
  if (!horizontal && !vertical) return
  const rtl = horizontal !== 0 && getComputedStyle(el).direction === 'rtl'
  const dir = rtl ? -horizontal : (horizontal || vertical)
  e.preventDefault()
  const before = props.modelValue
  for (;;) {
    const was = el.value
    if (dir > 0) el.stepUp(); else el.stepDown()
    if (el.value === was) break // the end of the axis
    emit('update:modelValue', Number(el.value))
    await nextTick()
    if (props.modelValue !== before) break
  }
  el.value = String(props.modelValue)
}

/**
 * The reached part of the bar, as a background on the input itself - a range's
 * track is a pseudo-element and cannot be given a background from outside, but
 * it inherits the one under it.
 */
const fillStyle = computed(() => {
  if (props.fillPct === null || props.fillPct === undefined) return undefined
  const pct = Math.max(0, Math.min(100, props.fillPct))
  return {
    background: `linear-gradient(to right,`
      + ` rgba(255, 255, 255, 0.3) 0 ${pct}%,`
      + ` var(--surface-4) ${pct}% 100%)`,
  }
})

/**
 * How much room one mark gets — a DEFINITE width (`max-width` does not hold a
 * word that cannot break), derived from how close the marks stand: the
 * narrowest gap between neighbours, less two points, so two of them keep a
 * little air between them. Five marks a quarter apart give 23 %, the fixed
 * value this carried while it was Encoder Fusion's own axis.
 *
 * The clamp is a floor and a ceiling, not part of that rule: below 14 % apart
 * the marks would be narrower than a word can usefully be, so they get 12 % and
 * may touch — an axis that crowded needs fewer marks, not thinner ones.
 */
const markWidth = computed(() => {
  const pcts = props.marks.map(m => m.pct).sort((a, b) => a - b)
  let gap = 100
  for (let i = 1; i < pcts.length; i++) gap = Math.min(gap, (pcts[i] ?? 0) - (pcts[i - 1] ?? 0))
  if (!isFinite(gap) || gap <= 0) gap = 100
  return `${Math.max(12, Math.min(48, gap - 2))}%`
})

/**
 * Half a mark's width, negative: what pulls the box back so its CENTRE sits on
 * its own place instead of its leading edge.
 *
 * It was `transform: translateX(-50%)` until 2026-09-05. A transform is
 * physical, and the marks were placed by a physical `left`, so under the
 * document's `dir="rtl"` (ar, he) both ran the wrong way while the range input
 * itself mirrors: measured on Decomposition in Arabic, the mark reading −1 stood
 * at x 689 and the handle for −1 at the opposite end of a track spanning
 * 681…924. A logical inset with a logical margin holds in both directions, and
 * the percentage resolves against the same containing block the width does, so
 * it is exactly half the box either way.
 */
const markOffset = computed(() => `calc(${markWidth.value} * -0.5)`)

/**
 * The zones as boxes in a row: each one's width, and the gap between it and the
 * one before it, both as percentages of the row. A row of flow boxes instead of
 * absolutely placed ones, so the row is as tall as its tallest word - a word
 * that wraps in a narrow column (or a longer language) would otherwise run out
 * of a fixed-height layer into whatever stands under the axis. The zones are
 * taken in axis order, and one that would begin before the last one ended is
 * pushed to start where that one stopped: two boxes cannot overlap in a row. A
 * stretch left without length by that is not drawn.
 */
const zoneBoxes = computed(() => {
  const sorted = [...props.zones].sort((a, b) => a.fromPct - b.fromPct)
  let cursor = 0
  return sorted.flatMap(zone => {
    const from = Math.max(cursor, Math.min(100, zone.fromPct))
    const to = Math.max(from, Math.min(100, zone.toPct))
    if (to <= from) return []
    const box = { label: zone.label, gapPct: from - cursor, widthPct: to - from }
    cursor = to
    return [box]
  })
})
</script>

<style scoped>
.ms-track {
  --ms-inset: 10%;
  /* The handle's own width. A range's thumb centre never reaches the ends of
     its bar - it stops half a thumb short - so the notches are inset by that
     half as well, and a notch then sits exactly where the handle stands. */
  --ms-thumb: 15px;
  position: relative;
  padding-top: 57px;
}

/* The track and the handle are the platform's (`.lab-range` in
   assets/flow-stage.css). What is this axis's own is where the track BEGINS and
   ENDS: it stops short of the column on both sides, because a centred outermost
   word needs half its width outside. */
.ms-range {
  width: calc(100% - 2 * var(--ms-inset));
  /* margin-inline only - a shorthand `margin` after it resets the inset, and
     the handle then stands a full inset left of its own scale. */
  margin-block: 0;
  margin-inline: var(--ms-inset);
}

.ms-marks {
  position: absolute;
  inset-inline: calc(var(--ms-inset) + var(--ms-thumb) / 2);
  top: 0;
  /* Room for the value and up to two lines of word. */
  height: 46px;
  pointer-events: none;
}

/*
 * Each word stands over its own value and none of them touches its neighbour.
 * The width is written as a PERCENTAGE, which resolves against the track: at a
 * wide column a long word fits on one line, at a narrow one it wraps and still
 * does not reach the mark beside it. A fixed pixel width would hold at one
 * width only - the words overlapped by 9 px at 1440 before this.
 *
 * And it is a DEFINITE width, not a maximum: a maximum leaves an absolutely
 * positioned box to shrink to what fits between its `left` and the layer's end,
 * which at `left: 100%` is nothing - the outermost mark collapsed to one letter
 * per line. `overflow-wrap` is the other half: a word longer than its share
 * breaks inside itself instead of reaching into the mark beside it (measured
 * before this: 1.7 px into it at 800 px, 11.7 px at 700).
 */
.ms-mark {
  position: absolute;
  bottom: 0;
  /* A long word is hyphenated in the READER'S language before it is broken
     anywhere: `lang` on the document follows the chosen language (main.ts), so
     the browser's own dictionary decides where a break may go and sets a hyphen
     there. Measured on System Prompts, 2026-09-09: four marks over a 204 px
     layer leave 47 px per word, and „Deterministisch" needs 80 px on one line -
     without this it stood as „Determi / nistisch", with nothing to say that it
     had been cut. `overflow-wrap` stays as the fallback for a word no
     dictionary can break. */
  -webkit-hyphens: auto;
  hyphens: auto;
  overflow-wrap: anywhere;
  text-align: center;
  line-height: 1.25;
}

/* The head of a mark is a NUMBER in the axis' own units, and a sign in front of
   it is a neutral character: inside an Arabic or Hebrew paragraph the bidi
   algorithm reorders it to the far side of the digits, and the row read
   `2−  1−  0  1  2` instead of `−2  −1  0  1  2` (measured on Composable
   Diffusion, 2026-09-05). The head is set as its own left-to-right run, so the
   sign stays where it belongs whatever the page around it does. */
.ms-mark b {
  display: block;
  direction: ltr;
  unicode-bidi: isolate;
  white-space: nowrap;
  font-size: var(--flow-fs-sub);
  font-weight: 400;
  color: rgba(255, 255, 255, 0.5);
}

/* 0.45 is the platform's quiet-but-readable level (`.lab-note p`, the note under
   a drawing). At 0.32 the word under a mark was the FAINTEST thing on the axis
   while being the only part of it that says what the number does, which reads as
   a disabled control, and there was no reason for the greying. It stays a step
   under its own number, which is at 0.5. */
.ms-mark em {
  display: block;
  font-style: normal;
  font-size: var(--flow-fs-hint);
  color: rgba(255, 255, 255, 0.45);
}

.ms-notches {
  position: absolute;
  inset-inline: calc(var(--ms-inset) + var(--ms-thumb) / 2);
  top: 49px;
  height: 11px;
  pointer-events: none;
}

.ms-notches i {
  position: absolute;
  top: 0;
  width: 1px;
  height: 11px;
  margin-inline-start: -0.5px;
  background: var(--surface-4);
}

/* The named stretches under the bar: inset like the marks and the notches, so a
   stretch is measured on the same scale as the values. The 10 px stand under
   the LINE BOX the inline range input sits in, not under the bar itself: the
   3 px bar is baseline-aligned inside a 24 px line, so the hairline comes about
   16 px under the bar and 10 px under the lowest point of the handle
   (measured 2026-09-21 at a 400 px component). */
.ms-zones {
  display: flex;
  align-items: flex-start;
  margin-inline: calc(var(--ms-inset) + var(--ms-thumb) / 2);
  margin-top: 10px;
  pointer-events: none;
}

.ms-zone {
  flex: 0 0 auto;
  text-align: center;
  line-height: 1.25;
}

/* A hairline that runs out at both ends: what a zone claims is roughly where it
   lies, not where it starts or stops. Its plateau stands at the same quiet
   level as the word under it (0.45). Symmetric, so it reads the same under
   `dir="rtl"`. */
.ms-zone i {
  display: block;
  height: 1px;
  margin-bottom: 5px;
  background: linear-gradient(to right, transparent, rgba(255, 255, 255, 0.45) 30%, rgba(255, 255, 255, 0.45) 70%, transparent);
}

/* The word at the level of the word under a mark (0.45), and broken as that
   word is: hyphenated in the reader's language first, anywhere as the fallback.
   A zone is about a third of the axis, so the words fit on one line down to the
   reference iPad with the rail open (boxes of 64 px; „Sémantique" needs 63); in
   a narrower column they hyphenate, and without a dictionary for the document's
   `lang` the fallback breaks the letter off that does not fit. */
.ms-zone em {
  display: block;
  font-style: normal;
  font-size: var(--flow-fs-hint);
  color: rgba(255, 255, 255, 0.45);
  -webkit-hyphens: auto;
  hyphens: auto;
  overflow-wrap: anywhere;
}
/* The compact axis: one line of numbers, and the notches keep the same 3 px
   reach into the track as on the full one (16 + 11 - 24, as 49 + 11 - 57).
   Measured on Encoder Fusion at 1210 x 834: with 30 px of head room each of
   the three factors took 73 px, and the token table under them was left its
   floor; 24 px is the line of numbers (14) plus the notches. */
.ms-track.ms-compact {
  padding-top: 24px;
}
.ms-track.ms-compact .ms-marks {
  height: 14px;
}
.ms-track.ms-compact .ms-notches {
  top: 16px;
}
</style>
