<!--
  LoraGlyph — THE sign a LoRA is shown by on this platform: a pliable net
  hanging over a rigid grid and coming down onto it at one place, the sign of
  what an adapter is (a small trained network laid over a model, which it
  bends and, where it was trained, replaces). One colour in two opacities, the
  net full, the grid under it at half; stroke, no fill, `currentColor`, so the
  host sets colour and size. Drawn once (from the picture of a purple mesh
  draped over a grey isometric grid) and used wherever a LoRA is named as a
  thing: the free fixture on the Flow's view, the face of a LoRA tile on the
  table, the mark on a perspective that carries an adapter, the mark beside
  the model in the create box, the card's back.
  Two weights: the fixture's, and `light` for the face of a disc, where the
  name lies over the sign.
  See docs/ELEMENT_STRUCTURE_REGISTRY.md.
-->
<script setup lang="ts">
withDefaults(defineProps<{ light?: boolean }>(), { light: false })
</script>
<template>
  <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      aria-hidden="true" fill="none" stroke="currentColor" :stroke-width="light ? 1.9 : 2.4" stroke-linecap="round" stroke-linejoin="round">
   <g :opacity="light ? 0.35 : 0.5" :stroke-width="light ? 1.42 : 1.8">
    <path d="M 32.00 30.08 L 4.48 43.84"/>
    <path d="M 32.00 30.08 L 59.52 43.84"/>
    <path d="M 38.88 33.52 L 11.36 47.28"/>
    <path d="M 25.12 33.52 L 52.64 47.28"/>
    <path d="M 45.76 36.96 L 18.24 50.72"/>
    <path d="M 18.24 36.96 L 45.76 50.72"/>
    <path d="M 52.64 40.40 L 25.12 54.16"/>
    <path d="M 11.36 40.40 L 38.88 54.16"/>
    <path d="M 59.52 43.84 L 32.00 57.60"/>
    <path d="M 4.48 43.84 L 32.00 57.60"/>
   </g>
   <g>
    <path d="M 32.00 7.04 L 30.28 7.90 L 28.56 8.76 L 26.84 9.62 L 25.12 10.48 L 23.40 11.34 L 21.68 12.20 L 19.96 13.06 L 18.24 13.92 L 16.52 14.78 L 14.80 15.64 L 13.08 16.50 L 11.36 17.36 L 9.64 18.22 L 7.92 19.08 L 6.20 19.94 L 4.48 20.80"/>
    <path d="M 32.00 7.04 L 33.72 7.90 L 35.44 8.76 L 37.16 9.62 L 38.88 10.48 L 40.60 11.34 L 42.32 12.20 L 44.04 13.06 L 45.76 13.92 L 47.48 14.78 L 49.20 15.64 L 50.92 16.50 L 52.64 17.36 L 54.36 18.22 L 56.08 19.08 L 57.80 19.94 L 59.52 20.80"/>
    <path d="M 38.88 10.48 L 37.16 11.66 L 35.44 12.82 L 33.72 13.97 L 32.00 15.07 L 30.28 16.13 L 28.56 17.15 L 26.84 18.10 L 25.12 18.99 L 23.40 19.82 L 21.68 20.59 L 19.96 21.30 L 18.24 21.95 L 16.52 22.57 L 14.80 23.14 L 13.08 23.70 L 11.36 24.24"/>
    <path d="M 25.12 10.48 L 26.84 11.66 L 28.56 12.82 L 30.28 13.97 L 32.00 15.07 L 33.72 16.13 L 35.44 17.15 L 37.16 18.10 L 38.88 19.01 L 40.60 19.88 L 42.32 20.74 L 44.04 21.60 L 45.76 22.45 L 47.48 23.21 L 49.20 23.81 L 50.92 24.25 L 52.64 24.61"/>
    <path d="M 45.76 13.92 L 44.04 15.23 L 42.32 16.52 L 40.60 17.79 L 38.88 19.01 L 37.16 20.20 L 35.44 21.36 L 33.72 22.49 L 32.00 23.57 L 30.28 24.52 L 28.56 25.27 L 26.84 25.81 L 25.12 26.21 L 23.40 26.56 L 21.68 26.92 L 19.96 27.30 L 18.24 27.69"/>
    <path d="M 18.24 13.92 L 19.96 15.23 L 21.68 16.52 L 23.40 17.78 L 25.12 18.99 L 26.84 20.14 L 28.56 21.23 L 30.28 22.32 L 32.00 23.57 L 33.72 25.39 L 35.44 28.35 L 37.16 32.76 L 38.88 37.96 L 40.60 42.09 L 42.32 43.20 L 44.04 40.91 L 45.76 36.78"/>
    <path d="M 52.64 17.36 L 50.92 18.54 L 49.20 19.73 L 47.48 20.97 L 45.76 22.45 L 44.04 24.55 L 42.32 27.83 L 40.60 32.56 L 38.88 37.96 L 37.16 42.18 L 35.44 43.36 L 33.72 41.27 L 32.00 37.48 L 30.28 34.02 L 28.56 31.96 L 26.84 31.24 L 25.12 31.30"/>
    <path d="M 11.36 17.36 L 13.08 18.54 L 14.80 19.70 L 16.52 20.85 L 18.24 21.95 L 19.96 23.02 L 21.68 24.04 L 23.40 25.07 L 25.12 26.21 L 26.84 27.76 L 28.56 30.13 L 30.28 33.54 L 32.00 37.48 L 33.72 40.63 L 35.44 41.60 L 37.16 40.18 L 38.88 37.49"/>
    <path d="M 59.52 20.80 L 57.80 21.66 L 56.08 22.54 L 54.36 23.47 L 52.64 24.61 L 50.92 26.24 L 49.20 28.81 L 47.48 32.52 L 45.76 36.78 L 44.04 40.18 L 42.32 41.30 L 40.60 39.99 L 38.88 37.49 L 37.16 35.31 L 35.44 34.24 L 33.72 34.17 L 32.00 34.69"/>
    <path d="M 4.48 20.80 L 6.20 21.66 L 7.92 22.52 L 9.64 23.38 L 11.36 24.24 L 13.08 25.10 L 14.80 25.96 L 16.52 26.82 L 18.24 27.69 L 19.96 28.56 L 21.68 29.46 L 23.40 30.37 L 25.12 31.30 L 26.84 32.21 L 28.56 33.07 L 30.28 33.89 L 32.00 34.69"/>
   </g>
  </svg>
</template>

<style scoped>
svg {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
