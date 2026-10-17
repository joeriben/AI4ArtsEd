<!--
  PerspectiveBubble — THE round disc a perspective is shown as on this platform,
  with its picture in it and, where a surface passes one, its name across it.

  It was `.pb-img` in `views/x2x_flow.vue` and a copy of that rule here until
  2026-09-04; since then there is one disc and two hosts. What a host keeps is
  the BOX and the gesture: the flow board’s `.pb` is 144 px square and the disc
  in it is a PIECE — dragged, numbered, removed, and marked while the zone reads
  it; an instrument’s column gives the disc its own width and there it is a
  standing CHOICE that opens the chooser when it is tapped. The component holds
  the disc and nothing of either host. See docs/ELEMENT_STRUCTURE_REGISTRY.md.

  Where a surface applies a perspective ONCE per run and the choice has to stay
  visible while it works, the perspective needs a place of its own: writing it
  into the prompt field (as Cultural (Un)Known does) shows it once and then
  nothing of it, and a surface whose every row runs through it would leave the
  reader guessing which one that was.

  The name is `CircleTitle`, set across the disc. A band along the rim is the
  narrowest place in a circle and was abolished for that reason; a caption line
  under the disc is the same name in a second place, so there is none here.

  A GIVEN perspective wears the preview its config file carries, read from the
  one path the chooser and the board also read from:
  `/config-previews/<previewId || configId>.webp`. The file is named by the
  config, so an id of its own is only needed where a perspective borrows another
  one’s picture, and the fallback to the config id lives here. A SAVED one wears
  a colour of the platform’s palette and NEVER a picture: it has
  no picture of its own, and while it wore the one of the preset it was written
  over, it stood beside that preset indistinguishable. The colour is
  `keptColor()` in `stores/keptPerspectives.ts`; the surface passes it in, so no
  second palette is opened here.

  A third face since 2026-09-21: a SIGN. A LoRA is shown as the same disc with
  the net (`LoraGlyph`) on a dark ground instead of a picture or a colour — a
  LoRA has no picture of its own, and a colour would make it read as a kept
  perspective. The host puts the sign into the default slot; the disc draws the
  ground and centres it. The ring the zone draws takes its colour from
  `readColor` (the amber of the perspectives unless the host says otherwise:
  the Flow gives a LoRA tile its own violet), so one rule draws every ring.

  A picture by address since 2026-10-02 (`src`): a ready-made Canvas workflow
  is chosen on the same ring (components/canvas/CanvasPresetOverlay.vue) and
  wears a picture its own result made, which is no config's preview. With
  neither a picture, a colour nor a sign the disc shows its light ground — the
  empty board in the middle of that ring.
-->
<template>
  <component
    :is="openable ? 'button' : 'div'"
    class="perspective-bubble"
    :title="title"
    :disabled="openable && disabled ? true : undefined"
    @click="open"
  >
    <span class="pbub-face" :class="{ read, glyph: hasGlyph }" :style="faceStyle">
      <span v-if="hasGlyph" class="pbub-glyph"><slot /></span>
      <CircleTitle v-if="name" :text="name" :revealed="revealed" />
    </span>
  </component>
</template>

<script setup lang="ts">
import { computed, useSlots } from 'vue'
import CircleTitle from '@/components/CircleTitle.vue'

const props = withDefaults(
  defineProps<{
    /**
     * Which preview picture a GIVEN perspective wears, where it is not the one
     * its own config is named by. A `custom:` key has no file of its own.
     */
    previewId?: string
    /** The config the perspective is, and the preview it falls back to. */
    configId?: string
    /**
     * A picture by address, for a disc that is no config: a ready-made Canvas
     * workflow wears what its own result looked like. Set, it stands instead
     * of the config preview.
     */
    src?: string
    /**
     * The palette colour of a SAVED perspective. Set, it stands INSTEAD of a
     * picture; that is the whole rule about saved ones.
     */
    color?: string
    /** What the perspective is called, across the disc. No name, no title. */
    name?: string
    /**
     * The name stands read-ready the whole time instead of only under the
     * pointer — for a surface where a perspective is not being looked for but
     * lies there among others.
     */
    revealed?: boolean
    /** Hover text on the disc. */
    title?: string
    disabled?: boolean
    /**
     * The zone reads this perspective — the amber ring of the flow board. It
     * is drawn HERE because a host’s scoped rule cannot reach inside a child.
     */
    read?: boolean
    /**
     * The colour of the ring `read` draws. The amber of the perspectives by
     * default; a host whose pieces are read under another colour (the Flow’s
     * LoRA tiles) passes its own.
     */
    readColor?: string
    /**
     * Whether the disc is itself the control that opens the chooser. On the
     * flow board it is a piece its host drags, so there the host owns
     * the gesture and the disc is no button: a button would take the cursor,
     * a tab stop and a focus ring that belong to nothing.
     */
    openable?: boolean
  }>(),
  {
    previewId: '',
    configId: '',
    src: '',
    color: '',
    name: '',
    revealed: false,
    title: undefined,
    disabled: false,
    read: false,
    readColor: '#ffb300',
    openable: true,
  },
)

const emit = defineEmits<{ (e: 'open'): void }>()

/** A sign in the slot: the disc draws its dark ground instead of a picture. */
const slots = useSlots()
const hasGlyph = computed(() => !!slots.default)

function open(): void {
  if (props.openable && !props.disabled) emit('open')
}

/** The same path the chooser and the board read a preview from. */
const faceStyle = computed<Record<string, string>>(() => {
  const style: Record<string, string> = { '--pbub-read': props.readColor }
  if (hasGlyph.value) return style
  if (props.color) {
    style.background = props.color
    return style
  }
  if (props.src) {
    style.backgroundImage = `url(${props.src})`
    return style
  }
  const slug = props.previewId || props.configId
  if (slug) style.backgroundImage = `url(/config-previews/${slug}.webp)`
  return style
})
</script>

<style scoped>
/* The disc takes the box its host gives it. The host’s box is square — the
   board’s 144 px, an instrument column’s own width — and the disc is square by
   construction, so it fills that box exactly as `.pb-img` did. */
.perspective-bubble {
  display: block;
  width: 100%;
  padding: 0;
  border: none;
  background: none;
  font-family: inherit;
}

button.perspective-bubble {
  cursor: pointer;
}

button.perspective-bubble:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* The violet is a colour of the perspective and the light ground is the disc’s
   own look under a picture that is missing — neither is a surface, so both stay
   literals here as they were on the board. Positioned, because the name inside
   it is laid over the whole circle. */
.pbub-face {
  position: relative;
  display: block;
  width: 100%;
  aspect-ratio: 1;
  border-radius: 50%;
  border: 1px solid #7f77dd;
  background: #f0f0f0 center / cover no-repeat;
  box-sizing: border-box;
}

/* Read by the zone: the amber of the flow board, ring and glow as it draws it —
   or the colour the host passed, mixed to the same two strengths. */
.pbub-face.read {
  border-color: var(--pbub-read, #ffb300);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--pbub-read, #ffb300) 55%, transparent),
    0 0 22px color-mix(in srgb, var(--pbub-read, #ffb300) 30%, transparent);
}

/* The sign’s ground: the dark violet the board’s badges stand on (`.pb-ord`),
   the disc’s own look under a sign — not a surface, so a literal like the
   light ground above. The sign fills the disc up to a narrow rim, in the
   light weight and the colour the host sets (`--pbub-glyph`), so the name laid
   over it stays legible. */
.pbub-face.glyph {
  background: #16121f;
}

.pbub-glyph {
  position: absolute;
  inset: 4%;
  display: block;
  color: var(--pbub-glyph, #a78bfa);
  pointer-events: none;
}
</style>
