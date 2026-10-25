<!--
  The twelve drawings of the Flow Logic page — one per box of the three bands.

  A drawing, not a paragraph. The page is a simplified graphic of diffuser and
  transformer architectures, drawn as a map with marker points that show where
  the instruments primarily act. A first build answered that with twelve blocks
  of prose behind a click. Prose about the machine belongs to help, which is
  this platform's authority for it; what belongs here is the thing shown.

  Each drawing is one SVG in the opened box's own coordinates (930 x 260, the
  box being 930 world units wide). It scales with the band, so a label keeps its
  proportion to the boxes at every window width.

  NOTHING HERE IS LAID OUT IN FIXED WIDTHS. A box is as wide as the words in it,
  measured after render with getComputedTextLength(), and the row is laid out
  from those measurements. A drawing whose boxes were sized for the English
  labels is a drawing that breaks in the other nine languages — the first build
  did exactly that, and the German for „trained — works out what to take away"
  ran straight out of its box. When a row still comes out wider than the 930
  there are, the whole group is scaled to fit rather than clipped.

  The markers are POINTS placed by `marks`, which the page hands in — the
  drawing does not know which instruments exist, and the page does not know
  where in a picture they belong. A point carries no number and no caption:
  numbers under the drawing repeated in a footnote what the column on the left
  already lists, so pointing at a point lights its instruments up over there
  instead; the numbers carry no information in the overview.
-->
<template>
  <svg class="st-svg" :viewBox="`0 0 ${VB.w} ${VB.h}`" preserveAspectRatio="xMidYMid meet">
    <defs>
      <marker id="fsArrow" markerWidth="9" markerHeight="9" refX="8" refY="3.2" orient="auto">
        <path d="M0,0 L8,3.2 L0,6.4" fill="none" stroke="#8b98a9" stroke-width="1.2" />
      </marker>
      <filter :id="`fsGrain${uid}`">
        <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="3" seed="7" />
        <feColorMatrix type="saturate" values="0" />
      </filter>
      <filter :id="`fsGrainSoft${uid}`">
        <feTurbulence type="fractalNoise" baseFrequency="0.5" numOctaves="2" seed="3" />
        <feColorMatrix type="saturate" values="0" />
      </filter>
    </defs>

    <g ref="gEl" :transform="fit">

      <template v-if="!mini">
      <!-- =========================== DIFFUSION =========================== -->

      <!-- The written line, and what changes when the same line is written in
           another language. -->
      <g v-if="id === 'diffusion.prompt'">
        <!-- Three columns: the prompts as written, the little landscape icon
             this platform already drew for "a picture" before today, now one
             composition per row — sun left, sun right, twin peaks — so the
             three read as similar but different, the way three separate
             generations would. -->
        <g v-for="(row, i) in PROMPT_STACK" :key="i">
          <rect :x="L.langX" :y="20 + i * 54" :width="L.langFieldW" height="44" rx="8"
            fill="#0f0f0f" :stroke="i === 0 ? '#7f77dd' : TINT2[i - 1]" />
          <text :ref="tr(`stack${i}a`)" :x="L.langX + 12" :y="20 + i * 54 + 19" class="t-sub">{{ row[0] }}</text>
          <text :ref="tr(`stack${i}b`)" :x="L.langX + 12" :y="20 + i * 54 + 33" class="t-sub">{{ row[1] }}</text>

          <line :x1="L.langX + L.langFieldW + 4" :y1="20 + i * 54 + 22" :x2="L.imgX - 4" :y2="20 + i * 54 + 22"
            stroke="#4a4a4a" />
          <rect :x="L.imgX" :y="20 + i * 54 + 3" width="44" height="30" rx="4" :fill="TINT[i]" stroke="#4a4a4a" />
          <circle :cx="L.imgX + ICONS[i]!.sun[0]" :cy="20 + i * 54 + 3 + ICONS[i]!.sun[1]" r="4" :fill="TINT2[i]" />
          <path v-for="(tp, ti) in ICONS[i]!.tris" :key="ti" :d="triPath(tp, L.imgX, 20 + i * 54 + 3)" :fill="TINT3[i]" />
        </g>

        <line :x1="L.imgX + 52" y1="96" :x2="L.enX - 6" y2="62" stroke="#8b98a9" marker-end="url(#fsArrow)" />

        <!-- Two steps this platform takes before the model reads anything.
             Neither is part of the model and both are drawn in the model's own
             column all the same: leaving them out let the three tiles say that
             the language you write in is the language the model reads, and
             that what reaches the model is what you wrote. The models read
             almost only English, so the platform translates before the model
             reads anything. Same field twice, dark grey: the translation box
             and, below it, the 'Adaption to medium' box, both with dark-grey
             backgrounds. -->
        <rect :x="L.enX" y="39" :width="L.enW" height="46" rx="8" fill="#2a2a2a" stroke="#4CAF50" />
        <text :ref="tr('enBox')" :x="L.enX + L.enW / 2" y="60" class="t-sub" text-anchor="middle">{{ t(k('enBox')) }}</text>
        <text :ref="tr('enSample')" :x="L.enX + L.enW / 2" y="76" class="t-dim" text-anchor="middle">{{ t(k('enSample')) }}</text>

        <line :x1="L.enX + L.enW / 2" y1="85" :x2="L.enX + L.enW / 2" y2="105" stroke="#8b98a9" marker-end="url(#fsArrow)" />

        <rect :x="L.enX" y="111" :width="L.enW" height="46" rx="8" fill="#2a2a2a" stroke="#4CAF50" />
        <text :ref="tr('adaptBox')" :x="L.enX + L.enW / 2" y="132" class="t-sub" text-anchor="middle">{{ t(k('adaptBox')) }}</text>
        <text :ref="tr('adaptSample')" :x="L.enX + L.enW / 2" y="148" class="t-dim" text-anchor="middle">{{ t(k('adaptSample')) }}</text>

        <text :ref="tr('platformNote')" x="40" y="196" class="t-dim">{{ t(k('platformNote')) }}</text>
        <text :ref="tr('langNote')" x="40" y="214" class="t-dim">{{ t(k('langNote')) }}</text>
        <text :ref="tr('exploreNote')" x="40" y="232" class="t-dim">{{ t(k('exploreNote')) }}</text>
      </g>

      <!-- The three readers, and the two things their answers are put together
           into. Conditioning is that putting-together, not a station. -->
      <g v-else-if="id === 'diffusion.encoder'">
        <!-- Same box field as the Prompt station's top field, same purple
             stroke — and in English, not the page's own language: by the time
             the encoders run, the platform has already translated the prompt,
             so the same box field as at the Prompt station carries it in
             English here. -->
        <rect x="20" :y="L.promptY" :width="L.promptW" height="44" rx="8" fill="#0f0f0f" stroke="#7f77dd" />
        <text :ref="tr('srcA')" x="32" :y="L.promptY + 19" class="t-sub">{{ ENC_SENTENCE[0] }}</text>
        <text :ref="tr('srcB')" x="32" :y="L.promptY + 33" class="t-sub">{{ ENC_SENTENCE[1] }}</text>

        <!-- The same grey, dashed area as the latent-space loop, named the
             same way, above and not in a corner. The grey latent-space area is
             laid around the three encoders and labelled Encoder. It groups the
             three components; the station itself is named for the process
             around them, not for them, because the stations are about
             processes and functions, not about components. -->
        <rect :x="L.readX - 16" y="24" :width="ENC_W + 32" :height="L.zoneH" rx="14"
          fill="#0f0f0f" fill-opacity="0.5" stroke="#4a4a4a" stroke-dasharray="5 5" />
        <text :x="L.readX - 16" y="14" class="t-sub"><tspan class="t-term">Encoder</tspan></text>

        <g v-for="(row, i) in TOKROWS" :key="i">
          <rect :x="L.readX" :y="40 + i * 62" :width="ENC_W" height="52" rx="7" fill="#22364d" stroke="#3f6a9c" />
          <text :ref="tr(`encName${i}`)" :x="L.readX + 12" :y="58 + i * 62" class="t-dim">{{ ENC_NAMES[i] }}</text>
          <g v-for="tk in row" :key="tk.key">
            <rect v-if="tk.show" :x="L.readX + tk.x" :y="66 + i * 62" :width="tk.w" height="20" rx="4"
              fill="#1d2f45" stroke="#3f6a9c" />
            <text :ref="tr(tk.key)" :x="L.readX + tk.x + tk.w / 2" :y="80 + i * 62" class="t-tok"
              text-anchor="middle" :visibility="tk.show ? undefined : 'hidden'">{{ tk.s }}</text>
          </g>
          <line :x1="L.readX - 20" :y1="66 + i * 62" :x2="L.readX - 6" :y2="66 + i * 62"
            stroke="#8b98a9" marker-end="url(#fsArrow)" />
          <line :x1="L.readX + ENC_W" :y1="66 + i * 62" :x2="L.joinX - 6" y2="128" stroke="#8b98a9" />
        </g>
        <text :ref="tr('readersA')" x="20" y="252" class="t-sub"><tspan
          v-for="(sg, si) in READERS[0]" :key="si" :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
        <text :ref="tr('readersB')" x="20" y="270" class="t-sub"><tspan
          v-for="(sg, si) in READERS[1]" :key="si" :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>

        <circle :cx="L.joinX" cy="128" r="4" fill="#6f7d90" />
        <line :x1="L.joinX + 4" y1="128" :x2="L.cellX - 6" y2="66" stroke="#8b98a9" marker-end="url(#fsArrow)" />
        <line :x1="L.joinX + 4" y1="128" :x2="L.cellX - 6" y2="128" stroke="#8b98a9" marker-end="url(#fsArrow)" />

        <text :ref="tr('list')" :x="L.cellX" y="30" class="t-sub"><tspan
          v-for="(sg, si) in segments(t(k('list')))" :key="si" :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
        <g v-for="(tok, i) in VECWORD" :key="i">
          <text :ref="tr(`vecTok${i}`)" :x="L.cellX" :y="51 + i * 24" class="t-tok">{{ tok }}</text>
          <g v-for="(n, j) in VEC_NUMS[i]" :key="j">
            <rect :x="L.cellX + L.vecNumX + j * 24" :y="38 + i * 24" width="20" height="18" rx="3"
              fill="#1d2f45" stroke="#3f6a9c" />
            <text :x="L.cellX + L.vecNumX + j * 24 + 10" :y="51 + i * 24" class="t-tok" text-anchor="middle">{{ n }}</text>
          </g>
        </g>

        <text :ref="tr('pooled')" :x="L.cellX" y="128" class="t-sub"><tspan
          v-for="(sg, si) in segments(t(k('pooled')))" :key="si" :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
        <g v-for="(n, j) in POOLED_NUMS" :key="j">
          <rect :x="L.cellX + L.vecNumX + j * 24" y="136" width="20" height="18" rx="3"
            fill="#1d2f45" stroke="#3f6a9c" />
          <text :x="L.cellX + L.vecNumX + j * 24 + 10" y="149" class="t-tok" text-anchor="middle">{{ n }}</text>
        </g>
      </g>

      <!-- The loop. Both boxes read and write inside the latent space; the way
           out is on its far edge. -->
      <g v-else-if="id === 'diffusion.loop'">
        <!-- What the denoiser reads BESIDE the noise, drawn where it comes
             from: outside the latent space, on the left, where the denoiser
             has room enough for the input vectors. Its line crosses the dashed edge and enters the
             denoiser from above, clear of the noise square, because the
             embedding is not a state IN the space — it is the condition held
             against it. -->
        <g v-for="(row, ri) in COND_ROWS" :key="`c${ri}`">
          <g v-for="(nval, ci) in row" :key="ci">
            <rect :x="20 + ci * 22" :y="60 + ri * 22" width="20" height="18" rx="3"
              fill="#1d2f45" stroke="#3f6a9c" />
            <text :x="30 + ci * 22" :y="73 + ri * 22" class="t-tok" text-anchor="middle">{{ nval }}</text>
          </g>
        </g>
        <text :ref="tr('cond')" x="20" y="146" class="t-sub"><tspan class="t-term">{{ t(k('cond')) }}</tspan></text>
        <path :d="`M108,69 L${L.zone - 10},69 L${L.zone - 10},38 L${L.d + L.dW / 2},38 L${L.d + L.dW / 2},50`"
          fill="none" stroke="#8b98a9" marker-end="url(#fsArrow)" />

        <rect :x="L.zone" y="24" :width="L.zoneW" height="160" rx="14"
          fill="#0f0f0f" fill-opacity="0.5" stroke="#4a4a4a" stroke-dasharray="5 5" />
        <!-- ABOVE the dashed area, not inside its corner: it names the area and
             says what it is, and a sentence that long inside the corner reads as
             something drawn in there. -->
        <text :ref="tr('spaceNote')" :x="L.zone" y="14" class="t-sub"><tspan
          class="t-term">{{ t('latentLab.flowLogic.diffusion.space') }}</tspan>: {{ t(k('spaceNote')) }}</text>

        <rect :x="L.s1" y="52" :width="SQ" :height="SQ" rx="6" fill="#0a0a0a" />
        <rect :x="L.s1" y="52" :width="SQ" :height="SQ" rx="6" :filter="`url(#fsGrain${uid})`" opacity="0.85" />
        <rect :x="L.s1" y="52" :width="SQ" :height="SQ" rx="6" fill="none" stroke="#4a4a4a" />
        <text :ref="tr('state')" :x="L.s1 + SQ / 2" y="156" class="t-sub" text-anchor="middle">{{ t(k('state')) }}</text>

        <line :x1="L.s1 + SQ + 6" y1="95" :x2="L.d - 6" y2="95" stroke="#8b98a9" marker-end="url(#fsArrow)" />

        <rect :x="L.d" y="56" :width="L.dW" height="78" rx="8" fill="#22364d" stroke="#3f6a9c" />
        <text :ref="tr('denoiser')" :x="L.d + L.dW / 2" y="80" class="t-md" text-anchor="middle">{{ t(k('denoiser')) }}</text>
        <text :ref="tr('dSub0')" :x="L.d + L.dW / 2" y="102" class="t-sub" text-anchor="middle">{{ dSub[0] }}</text>
        <text :ref="tr('dSub1')" :x="L.d + L.dW / 2" y="120" class="t-sub" text-anchor="middle">{{ dSub[1] }}</text>

        <line :x1="L.d + L.dW + 6" y1="95" :x2="L.sc - 6" y2="95" stroke="#8b98a9" marker-end="url(#fsArrow)" />

        <rect :x="L.sc" y="56" :width="L.scW" height="78" rx="8" fill="#151515" stroke="#4a4a4a" />
        <text :ref="tr('scheduler')" :x="L.sc + L.scW / 2" y="80" class="t-md" text-anchor="middle">{{ t(k('scheduler')) }}</text>
        <text :ref="tr('scSub0')" :x="L.sc + L.scW / 2" y="102" class="t-sub" text-anchor="middle">{{ scSub[0] }}</text>
        <text :ref="tr('scSub1')" :x="L.sc + L.scW / 2" y="120" class="t-sub" text-anchor="middle">{{ scSub[1] }}</text>

        <line :x1="L.sc + L.scW + 6" y1="95" :x2="L.s2 - 6" y2="95" stroke="#8b98a9" marker-end="url(#fsArrow)" />

        <rect :x="L.s2" y="52" :width="SQ" :height="SQ" rx="6" fill="#0a0a0a" />
        <rect :x="L.s2" y="52" :width="SQ" :height="SQ" rx="6" :filter="`url(#fsGrainSoft${uid})`" opacity="0.4" />
        <path :d="`M${L.s2 + 22},126 L${L.s2 + 44},90 L${L.s2 + 66},126 Z`" fill="#2f4a63" />
        <circle :cx="L.s2 + 64" cy="76" r="8" fill="#3a5875" />
        <rect :x="L.s2" y="52" :width="SQ" :height="SQ" rx="6" fill="none" stroke="#4a4a4a" />
        <text :ref="tr('next')" :x="L.s2 + SQ / 2" y="156" class="t-sub" text-anchor="middle">{{ t(k('next')) }}</text>

        <!-- The pill sits ON the return path, so the path is drawn in two
             pieces and leaves the room the words need. -->
        <path :d="`M${L.s2 + SQ / 2},164 L${L.s2 + SQ / 2},174 L${L.pill + L.pillW},174`" fill="none"
          stroke="#8b98a9" stroke-dasharray="4 5" />
        <path :d="`M${L.pill},174 L${L.s1 + SQ / 2},174 L${L.s1 + SQ / 2},164`" fill="none"
          stroke="#8b98a9" stroke-dasharray="4 5" marker-end="url(#fsArrow)" />
        <rect :x="L.pill" y="162" :width="L.pillW" height="24" rx="12" fill="#141414" stroke="#8b98a9" />
        <text :ref="tr('repeat')" :x="L.pill + L.pillW / 2" y="179" class="t-sub" text-anchor="middle">{{ t(k('repeat')) }}</text>

        <line :x1="L.zone + L.zoneW + 6" y1="95" :x2="L.tail - 10" y2="95" stroke="#8b98a9" marker-end="url(#fsArrow)" />
        <text v-for="(ln, li) in tailSub" :key="li" :ref="tr(`tail${li}`)" :x="L.tail"
          :y="68 + li * 18" class="t-sub">{{ ln }}</text>

        <!-- Under the drawing, because it is about the whole loop and not about
             one of its boxes. „schätzt das Rauschen" left open what kind of
             guess that is, and the word points at predictive AI, which works
             nothing like this. What happens is a reading of the embeddings
             into the noise, comparable to people seeing things in clouds, but
             nonhuman and statistical. -->
        <text v-for="(ln, li) in NOTE" :key="li" :ref="tr(`note${li}`)" x="20" :y="202 + li * 15"
          class="t-sub"><tspan
          v-for="(sg, si) in ln" :key="si" :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
      </g>

      <!-- The door out of the latent space, into two kinds of material. -->
      <g v-else-if="id === 'diffusion.decoder'">
        <!-- Five small matrices, not sixteen single cells: SD3.5 actually
             carries 16 of these (its VAE latent has 16 channels), each one a
             2D grid, not a row of numbers — a matrix, different in kind from
             the Encoder station's vectors. Five stand in for the sixteen; the
             ellipsis and the caption say so. Scattered, not lined up: the 16
             channels have no known systematic relation to one another, so the
             five are placed as an unconnected cluster rather than a sequence,
             arranged across the area, unconnected but together. -->
        <g v-for="(p, pi) in MATRIX_POS" :key="pi">
          <rect :x="60 + p[0]" :y="90 + p[1]" width="34" height="34" rx="4" fill="#1d2f45" stroke="#3f6a9c" />
          <rect v-for="cell in 4" :key="cell"
            :x="60 + p[0] + 4 + ((cell - 1) % 2) * 14" :y="90 + p[1] + 4 + Math.floor((cell - 1) / 2) * 14"
            width="12" height="12" rx="2" fill="#2a4a68" />
        </g>
        <text :ref="tr('from')" x="60" y="195" class="t-sub"><tspan
          v-for="(sg, si) in segments(t(k('from')))" :key="si" :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
        <text :ref="tr('explain0')" x="60" y="213" class="t-dim">{{ EXPLAIN[0] }}</text>
        <text :ref="tr('explain1')" x="60" y="229" class="t-dim">{{ EXPLAIN[1] }}</text>

        <!-- Compact and cluster-anchored, not caption-anchored: decX used to
             track the width of the German explain text below (which sat
             BESIDE the box in the old single-row design), stranding the box
             far to the right of a now-much-narrower matrix cluster, so the
             left and right parts of the drawing fell apart. It now tracks
             only the cluster's own right edge. -->
        <line :x1="L.decX - GAP" y1="128" :x2="L.decX - 6" y2="128" stroke="#8b98a9" marker-end="url(#fsArrow)" />
        <rect :x="L.decX" y="83" :width="L.vaeW" height="90" rx="8" fill="#4a2b2f" stroke="#7a4046" />
        <!-- The box's own label, not just the station title, spells out the
             full name: VAE on one line and Variational Auto Encoder on the
             next. -->
        <text :ref="tr('vaeLine1')" :x="L.decX + L.vaeW / 2" y="118" class="t-md" text-anchor="middle">VAE</text>
        <text :ref="tr('vaeLine2')" :x="L.decX + L.vaeW / 2" y="142" class="t-sub" text-anchor="middle">Variational Auto Encoder</text>

        <!-- Four outputs, not two: the existing Bild/Klang graphics shrunk to
             make room, Video and 3D reusing components/MediumGlyph.vue's own
             paths rather than inventing new icons (docs/ELEMENT_STRUCTURE_REGISTRY.md names
             `MediumGlyph` as the canonical per-medium line icon). -->
        <line :x1="L.decX + L.vaeW" y1="128" :x2="L.outX - 6" :y2="ROW_CENTERS[0]!" stroke="#8b98a9" marker-end="url(#fsArrow)" />
        <line :x1="L.decX + L.vaeW" y1="128" :x2="L.outX - 6" :y2="ROW_CENTERS[1]!" stroke="#8b98a9" marker-end="url(#fsArrow)" />
        <line :x1="L.decX + L.vaeW" y1="128" :x2="L.outX - 6" :y2="ROW_CENTERS[2]!" stroke="#8b98a9" marker-end="url(#fsArrow)" />
        <line :x1="L.decX + L.vaeW" y1="128" :x2="L.outX - 6" :y2="ROW_CENTERS[3]!" stroke="#8b98a9" marker-end="url(#fsArrow)" />

        <rect :x="L.outX" :y="ROW_CENTERS[0]! - 17" width="34" height="34" rx="4" fill="#2f3d4f" stroke="#4a4a4a" />
        <circle :cx="L.outX + 11" :cy="ROW_CENTERS[0]! - 6" r="3" fill="#5a6b80" />
        <path :d="`M${L.outX + 5},${ROW_CENTERS[0]! + 12} L${L.outX + 16},${ROW_CENTERS[0]! - 3} L${L.outX + 27},${ROW_CENTERS[0]! + 12} Z`" fill="#44586e" />
        <text :ref="tr('toImage')" :x="L.outX + 44" :y="ROW_CENTERS[0]! + 5" class="t-sub">{{ t(k('toImage')) }}</text>

        <rect :x="L.outX" :y="ROW_CENTERS[1]! - 17" width="34" height="34" rx="4" fill="#2f3d4f" stroke="#4a4a4a" />
        <path :d="`M${L.outX + 4},${ROW_CENTERS[1]! + 1} q4,-9 8,0 t8,0 t8,0`" fill="none" stroke="#5a7a64" stroke-width="2" />
        <text :ref="tr('toSound')" :x="L.outX + 44" :y="ROW_CENTERS[1]! + 5" class="t-sub">{{ t(k('toSound')) }}</text>

        <rect :x="L.outX" :y="ROW_CENTERS[2]! - 17" width="34" height="34" rx="4" fill="#2f3d4f" stroke="#4a4a4a" />
        <g :transform="`translate(${L.outX + 2}, ${ROW_CENTERS[2]! - 14}) scale(1.1)`">
          <rect x="3" y="5" width="18" height="14" rx="2" fill="none" stroke="#8b98a9" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M10 8.7 15.5 12 10 15.3Z" fill="#6f7d90" stroke="none" />
        </g>
        <text :ref="tr('toVideo')" :x="L.outX + 44" :y="ROW_CENTERS[2]! + 5" class="t-sub">{{ t(k('toVideo')) }}</text>

        <rect :x="L.outX" :y="ROW_CENTERS[3]! - 17" width="34" height="34" rx="4" fill="#2f3d4f" stroke="#4a4a4a" />
        <g :transform="`translate(${L.outX + 2}, ${ROW_CENTERS[3]! - 14}) scale(1.1)`"
           fill="none" stroke="#8b98a9" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2.8 20.5 7v10L12 21.2 3.5 17V7Z" />
          <path d="M3.5 7 12 11.6 20.5 7" />
          <path d="M12 11.6V21.2" />
        </g>
        <text :ref="tr('to3D')" :x="L.outX + 44" :y="ROW_CENTERS[3]! + 5" class="t-sub">{{ t(k('to3D')) }}</text>
      </g>

      <!-- ========================== TRANSFORMER ========================== -->

      <!-- What a chatbot puts around what you wrote, before the model reads a
           word of it. Built as the mirror of the Prompt station in the
           diffusion column, because a system prompt is a prompt and the
           diffusion column already runs prompt, then embedding. -->
      <g v-else-if="id === 'transformer.prompt'">
        <rect x="20" y="26" :width="L.fw" height="44" rx="8" fill="#0f0f0f" stroke="#7f77dd" />
        <text :ref="tr('pA')" x="32" y="45" class="t-sub">{{ EX[0] }}</text>
        <text :ref="tr('pB')" x="32" y="59" class="t-sub">{{ EX[1] }}</text>
        <text :ref="tr('you')" :x="20 + L.fw / 2" y="84" class="t-sub" text-anchor="middle">{{ t(k('you')) }}</text>

        <rect x="20" y="100" :width="L.fw" height="44" rx="8" fill="#0f0f0f" stroke="#7f77dd" />
        <text :ref="tr('sA')" x="32" y="119" class="t-sub">{{ SYS[0] }}</text>
        <text :ref="tr('sB')" x="32" y="133" class="t-sub">{{ SYS[1] }}</text>
        <text :ref="tr('provider')" :x="20 + L.fw / 2" y="158" class="t-sub" text-anchor="middle">{{ t(k('provider')) }}</text>

        <line :x1="24 + L.fw" y1="48" :x2="L.joinX - 2" y2="92" stroke="#8b98a9" />
        <line :x1="24 + L.fw" y1="122" :x2="L.joinX - 2" y2="98" stroke="#8b98a9" />
        <circle :cx="L.joinX" cy="95" r="4" fill="#6f7d90" />
        <line :x1="L.joinX + 4" y1="95" :x2="L.zoneX - 6" y2="95" stroke="#8b98a9" marker-end="url(#fsArrow)" />

        <!-- The same grey dashed area the other columns use for what cannot be
             looked into, named above it rather than in a corner. -->
        <rect :x="L.zoneX" y="24" :width="L.zoneW" height="152" rx="14"
          fill="#0f0f0f" fill-opacity="0.5" stroke="#4a4a4a" stroke-dasharray="5 5" />
        <text :ref="tr('hidden')" :x="L.zoneX" y="14" class="t-sub"><tspan
          v-for="(sg, si) in segments(t(k('hidden')))" :key="si" :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>

        <rect :x="L.zoneX + 18" y="52" :width="L.txtW" height="82" rx="8" fill="#151515" stroke="#4a4a4a" />
        <text v-for="(ln, li) in ASM" :key="li" :ref="tr(`a${li}`)" :x="L.zoneX + 30"
          :y="71 + li * 16" :class="li % 2 === 0 ? 't-mono-dim' : 't-mono'">{{ ln }}</text>
        <text :ref="tr('oneText')" :x="L.zoneX + 18 + L.txtW / 2" y="152" class="t-sub"
          text-anchor="middle">{{ t(k('oneText')) }}</text>

        <line :x1="L.zoneX + 24 + L.txtW" y1="93" :x2="L.zoneX + 36 + L.txtW" y2="93"
          stroke="#8b98a9" marker-end="url(#fsArrow)" />

        <rect :x="L.chkX" y="52" :width="L.chkW" height="82" rx="8" fill="#22364d" stroke="#3f6a9c" />
        <text :ref="tr('check')" :x="L.chkX + L.chkW / 2" y="80" class="t-md" text-anchor="middle">{{ t(k('check')) }}</text>
        <text :ref="tr('checkA')" :x="L.chkX + L.chkW / 2" y="101" class="t-sub" text-anchor="middle">{{ t(k('checkA')) }}</text>
        <text :ref="tr('checkB')" :x="L.chkX + L.chkW / 2" y="118" class="t-sub" text-anchor="middle">{{ t(k('checkB')) }}</text>

        <!-- Two ways out, because a check does not move the text on: it lets it
             through or it holds it. -->
        <path :d="`M${L.chkX + L.chkW},76 L${L.chkX + L.chkW + 22},76 L${L.chkX + L.chkW + 22},66 L${L.tailX - 6},66`"
          fill="none" stroke="#8b98a9" marker-end="url(#fsArrow)" />
        <path :d="`M${L.chkX + L.chkW},112 L${L.chkX + L.chkW + 22},112 L${L.chkX + L.chkW + 22},128 L${L.tailX - 10},128`"
          fill="none" stroke="#8b98a9" />
        <line :x1="L.tailX - 6" y1="118" :x2="L.tailX - 6" y2="138" stroke="#7a4046" stroke-width="3" />
        <text :ref="tr('passA')" :x="L.tailX" y="62" class="t-sub">{{ t(k('passA')) }}</text>
        <text :ref="tr('passB')" :x="L.tailX" y="76" class="t-sub">{{ t(k('passB')) }}</text>
        <text :ref="tr('stopped')" :x="L.tailX" y="132" class="t-sub">{{ t(k('stopped')) }}</text>

        <text v-for="(ln, li) in PNOTE" :key="li" :ref="tr(`note${li}`)" x="40" :y="196 + li * 13"
          class="t-dim">{{ ln }}</text>
        <!-- A real anchor, not a line of text that looks like one: it has to be
             followable and its address has to be copyable, and only an active
             link is either. The press stops here so it does not reach the box. -->
        <a :href="t(k('source'))" target="_blank" rel="noopener noreferrer"
          @click.stop @pointerdown.stop>
          <text :ref="tr('source')" x="40" y="252" class="t-link">{{ t(k('source')) }}</text>
        </a>
      </g>

      <!-- Two parts under one another, and an excursus in a column of its own.
           The strand runs down the LEFT: the cut, then the embedding. The same
           sentence in the ten languages of the platform stands to the right of
           it, behind a rule, for the whole height of both, and the marker on
           that rule leads to the instrument that takes it up: „Tokenisierung im
           Sprachvergleich" cuts the visitor's own sentence in the same ten
           languages, so the numbers here can be checked and not only read.
           A column of its own is what pays for
           the embedding's three rows: while the excursus stood ABOVE the
           embedding, the ten bars pushed the second part 24 units down the card
           and everything was scaled to fetch it back.

           ONE dark area, and it lies around the EMBEDDING. The cut stays open:
           what it shows is the visitor's own sentence in pieces, and every piece
           can be checked by reading it. The rows of numbers cannot — 2,560 of
           them per token, of which six are drawn — and a dashed grey area is
           what this file's other stations put around exactly that: the inside of
           a named thing one cannot look into (the encoders, the latent space,
           the assembled hidden text, the transformer). `embLabel` names it at
           its top edge, in the shape the latent-space frame uses: term, colon,
           sentence. The excursus gets no frame — a second one beside the first
           would read as a second mechanism — and the closing paragraph gets a
           hard edge to be set off from.

           Sentence, cut and numbers are measured on Qwen3-4B. -->
      <g v-else-if="id === 'transformer.vectors'">
        <text :ref="tr('sent')" x="20" y="11" class="t-mono">{{ t(k('sent')) }}</text>
        <line x1="40" y1="17" x2="40" y2="27" stroke="#8b98a9" marker-end="url(#fsArrow)" />

        <text :ref="tr('cutl')" x="20" y="37" class="t-sub"><tspan
          v-for="(sg, si) in segments(t(k('cutLabel')))" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
        <g v-for="(c, i) in TCHIPS" :key="`tc${i}`">
          <rect v-if="!c.gap" :x="L.tcX[i] ?? 0" y="45" :width="L.tcW[i] ?? 0" height="15" rx="3"
            :fill="c.ctrl ? '#141b26' : '#1d2f45'"
            :stroke="c.ctrl ? '#2c3a4c' : c.hot ? '#4CAF50' : '#3f6a9c'" />
          <!-- The control token is written without its bracket characters in
               the language file - a literal | is vue-i18n's plural separator
               and cuts the message apart. The drawing puts them back. -->
          <text :ref="tr(`tc${i}`)" :x="(L.tcX[i] ?? 0) + (L.tcW[i] ?? 0) / 2" y="56"
            :class="c.ctrl || c.gap ? 't-dim' : 't-tok'"
            text-anchor="middle">{{ c.ctrl ? `<|${c.s}|>` : c.s }}</text>
          <text :ref="tr(`tp${i}`)" :x="(L.tcX[i] ?? 0) + (L.tcW[i] ?? 0) / 2" y="70"
            class="t-dim" text-anchor="middle">{{ c.pos }}</text>
        </g>
        <text :ref="tr('ctrln')" :x="L.ctrlX" y="84" class="t-sub"
          text-anchor="middle">{{ t(k('ctrlNote')) }}</text>
        <text :ref="tr('fourn')" :x="L.fourX" y="84" class="t-sub"
          text-anchor="middle"><tspan
          v-for="(sg, si) in segments(t(k('fourNote')))" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
        <text :ref="tr('posn')" x="20" y="96" class="t-sub"><tspan
          v-for="(sg, si) in segments(t(k('posNote')))" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
        <!-- The size of the vocabulary is a fact about the CUT — the pieces are
             drawn from it — so it stands in the cut's own caption line and not
             beside the rows of numbers, where it stood until 2026-08-26. -->
        <text :ref="tr('voc')" :x="L.vocX" y="96" class="t-sub"><tspan
          v-for="(sg, si) in segments(t(k('vocab')))" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>

        <!-- The rule is the whole marking the excursus needs: a second frame
             beside the embedding's would read as a second mechanism. -->
        <line :x1="L.cx - 14" y1="26" :x2="L.cx - 14" :y2="L.ruleY2"
          stroke="#4a4a4a" opacity="0.7" />
        <text :ref="tr('lgh')" :x="L.cx" y="37" class="t-sub"><tspan
          v-for="(sg, si) in segments(t(k('langHead')))" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
        <g v-for="(g, i) in LANGS" :key="`lg${i}`">
          <!-- Lying bars, not standing ones: ten language names side by side
               collide in every language, one under the other they read. Eleven
               units of pitch, not eight: at eight the ascender of one name sat
               in the descender of the one above it. -->
          <text :ref="tr(`lg${i}`)" :x="L.cx + L.nameW" :y="51 + i * 11"
            class="t-dim" text-anchor="end">{{ g.s }}</text>
          <rect :x="L.cx + L.nameW + 6" :y="45 + i * 11" :width="g.n * 2.4" height="6" rx="2"
            :fill="g.mine ? '#4CAF50' : '#3f6a9c'" :opacity="g.mine ? 0.9 : 0.5" />
          <text :x="L.cx + L.nameW + 13 + g.n * 2.4" :y="51 + i * 11"
            class="t-mono-dim">{{ g.n }}</text>
        </g>
        <text v-for="(ln, i) in LANGNOTE" :key="`ln${i}`" :ref="tr(`ln${i}`)" :x="L.noteX"
          :y="51 + i * 12" class="t-sub"><tspan
          v-for="(sg, si) in ln" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>

        <line x1="40" :y1="L.yEmb" x2="40" :y2="L.yEmb + 11" stroke="#8b98a9" marker-end="url(#fsArrow)" />
        <text :ref="tr('embl')" x="20" :y="L.yEmb + 23" class="t-sub"><tspan
          v-for="(sg, si) in segments(t(k('embLabel')))" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
        <rect x="14" :y="L.yEmb + 29" :width="L.frameW" :height="L.frameH" rx="14"
          fill="#0f0f0f" fill-opacity="0.5" stroke="#4a4a4a" stroke-dasharray="5 5" />

        <!-- One measured row per green-edged chip above, one under the other:
             a single row said what a row IS, three say that every token has its
             own and that they do not resemble each other. Measured, never
             invented — see the file named at the head of this station. -->
        <g v-for="(r, i) in EROWS" :key="`er${i}`">
          <rect x="26" :y="L.yEmb + 39 + i * 15" :width="L.erChipW" height="13" rx="3"
            fill="#1d2f45" stroke="#4CAF50" />
          <text :ref="tr(`et${i}`)" :x="26 + L.erChipW / 2" :y="L.yEmb + 49 + i * 15"
            class="t-tok" text-anchor="middle">{{ r.s }}</text>
          <g v-for="(v, c) in r.vals" :key="`ev${i}-${c}`">
            <rect :x="L.erX + c * 42" :y="L.yEmb + 39 + i * 15" width="40" height="13" rx="2"
              fill="#1d2f45" stroke="#3f6a9c" />
            <text :x="L.erX + 20 + c * 42" :y="L.yEmb + 49 + i * 15" class="t-mono"
              text-anchor="middle">{{ v }}</text>
          </g>
          <text :ref="tr(`em${i}`)" :x="L.erX + r.vals.length * 42 + 8" :y="L.yEmb + 49 + i * 15"
            class="t-sub">{{ t(k('more')) }}</text>
        </g>

        <!-- All 2,560 numbers of the FIRST of those rows, four Zeilen zu 640
             Feldern, so wie Alammar einen Vektor zeichnet: sechs Kommazahlen
             koennen nicht zeigen, dass eine Reihe aus 2.560 Zahlen ein Muster
             ist. Die Beschriftung nennt, welche Reihe es ist - bei drei Reihen
             darueber sagte "dieselbe Zahlenreihe" nicht mehr, welche. Und sie
             nennt die Nummer des Token, weil genau das der Punkt ist: eine
             echte Zeile eines echten Token aus 151.936, nicht ein Beispiel.
             Die Felder tragen KEINE Aehnlichkeitsaussage; auf dieser Schicht
             hat das Modell keine zu zeigen. -->
        <g :transform="`translate(26,${L.yBand})`" shape-rendering="crispEdges">
          <path v-for="(p, i) in VEC" :key="`vp${i}`" :d="p.d" :stroke="p.c"
            :stroke-width="VH" fill="none" />
        </g>

        <!-- Beschriftung und Farbleiste stehen rechts neben den Zahlenreihen,
             wo sonst nichts steht. Unter dem Band waere jede von ihnen eine
             Zeile mehr, und die Hoehe ist das Knappe an dieser Flaeche. -->
        <text v-for="(ln, i) in VECNOTE" :key="`vn${i}`" :ref="tr(`vn${i}`)" :x="L.legX"
          :y="L.yEmb + 49 + i * 12" class="t-sub"><tspan
          v-for="(sg, si) in ln" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
        <text :ref="tr('vs0')" :x="L.legX" :y="L.yKey + 6" class="t-dim">{{ VECSCALE[0] }}</text>
        <rect v-for="(c, i) in VECC" :key="`vk${i}`" :x="L.keyX + i * 3" :y="L.yKey"
          width="3" height="7" :fill="c" />
        <text :ref="tr('vs1')" :x="L.keyX + 102" :y="L.yKey + 6" class="t-dim">{{ VECSCALE[1] }}</text>

        <!-- Fourteen units clear of the frame's edge and twelve between the
             lines: the closing text is its own paragraph, not a continuation of
             the band above it. It stood eleven under nine-point type, where the
             lines touched. -->
        <text v-for="(ln, i) in VCLOSE" :key="`vc${i}`" :ref="tr(`vc${i}`)" x="20"
          :y="L.closeY + i * 12" class="t-dim"><tspan
          v-for="(sg, si) in ln" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>

        <!-- Woran alles hier gemessen ist: klein, in der rechten unteren Ecke,
             neben dem Schlussabsatz. Derselbe Vermerk steht
             an derselben Stelle auf „Attention" und „Sampling" und kommt auf
             allen dreien aus EINEM Schluessel. -->
        <text v-for="(ln, i) in MODELNOTE" :key="`md${i}`" :ref="tr(`md${i}`)" :x="L.mdX"
          :y="L.mdY + i * 10" class="t-fine" text-anchor="end"><tspan
          v-for="(sg, si) in ln" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
      </g>

      <!-- The whole mechanism lives inside a dashed frame named at its top
           edge — the
           structural twin of the latent-space frame in the denoiser card, so
           the flow title is redeemed where the mechanism lives. Inside: the
           sentence's tokens with two exemplary arcs (one across half the
           sentence — distance is no obstacle; one onto the four-token word
           from the embedding card), then one drawn walk with captions instead
           of prose: measured starting row → 36 layers → readable as a word.
           The frame's title line carries its two facts: name and field of
           view. The dashed inset outside holds the homonym line. -->
      <g v-else-if="id === 'transformer.block'">
        <text :ref="tr('intro')" x="14" y="16" class="t-dim"><tspan
          v-for="(sg, si) in segments(t(k('intro')))" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
        <text x="14" y="38" class="t-sub"><tspan class="t-term">{{ t(k('frameLabel')) }}</tspan></text>
        <text :ref="tr('fv')" :x="14 + L.frameW" y="38" class="t-dim"
          text-anchor="end"><tspan
          v-for="(sg, si) in segments(t(k('field')))" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
        <rect x="14" y="46" :width="L.frameW" :height="L.frameH" rx="14"
          fill="#0f0f0f" fill-opacity="0.5" stroke="#4a4a4a" stroke-dasharray="5 5" />

        <g v-for="(c, i) in BCHIPS" :key="`bc${i}`">
          <rect v-if="!c.gap" :x="L.bcX[i] ?? 0" y="58" :width="L.bcW[i] ?? 0" height="15" rx="3"
            fill="#1d2f45" :stroke="c.hot ? '#4CAF50' : '#3f6a9c'" />
          <text :ref="tr(`bc${i}`)" :x="(L.bcX[i] ?? 0) + (L.bcW[i] ?? 0) / 2" y="69"
            :class="c.gap ? 't-dim' : 't-tok'" text-anchor="middle">{{ c.s }}</text>
        </g>
        <g v-for="(a, i) in L.arcs" :key="`ba${i}`">
          <path :d="`M${a.x1},75 Q${(a.x1 + a.x2) / 2},${75 + a.depth} ${a.x2},75`"
            fill="none" stroke="#4CAF50" :stroke-width="a.width" opacity="0.85" />
          <text :ref="tr(`bl${i}`)" :x="a.x1" :y="75 + a.depth + 11"
            class="t-dim" text-anchor="middle">{{ a.label }}</text>
        </g>
        <text :ref="tr('ac')" x="28" :y="L.attY" class="t-sub"><tspan
          v-for="(sg, si) in segments(t(k('attCap')))" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>

        <rect x="28" :y="L.rowMid - 7" :width="L.brChipW" height="14" rx="3" fill="#1d2f45" stroke="#4CAF50" />
        <text :ref="tr('brt')" :x="28 + L.brChipW / 2" :y="L.rowMid + 3" class="t-tok"
          text-anchor="middle">{{ BROW.s }}</text>
        <g v-for="(v, c) in BROW.vals" :key="`bv${c}`">
          <rect :x="L.brX + c * 42" :y="L.rowMid - 7" width="40" height="14" rx="2" fill="#1d2f45" stroke="#3f6a9c" />
          <text :x="L.brX + 20 + c * 42" :y="L.rowMid + 3" class="t-mono" text-anchor="middle">{{ v }}</text>
        </g>
        <text :ref="tr('brm')" :x="L.brX + BROW.vals.length * 42 + 8" :y="L.rowMid + 3"
          class="t-dim">{{ t(k('more')) }}</text>
        <line :x1="L.brEnd + 10" :y1="L.rowMid" :x2="L.stackX - 10" :y2="L.rowMid"
          stroke="#8b98a9" marker-end="url(#fsArrow)" />
        <rect v-for="c in 4" :key="`st${c}`" :x="L.stackX + (c - 1) * 9" :y="L.rowMid - 24 + (c - 1) * 7"
          :width="L.stack" height="34" rx="7" fill="#22364d" stroke="#3f6a9c"
          :opacity="0.35 + (c - 1) * 0.22" />
        <line :x1="L.stackEnd + 10" :y1="L.rowMid" :x2="L.resX - 10" :y2="L.rowMid"
          stroke="#8b98a9" marker-end="url(#fsArrow)" />
        <rect :x="L.resX" :y="L.rowMid - 8" :width="L.resW" height="17" rx="4"
          fill="#0f1c12" stroke="#4CAF50" stroke-width="1.4" />
        <text :ref="tr('res')" :x="L.resX + L.resW / 2" :y="L.rowMid + 4" class="t-tok"
          text-anchor="middle" style="fill: #9fd7a4">{{ t(k('result')) }}</text>
        <text :ref="tr('cap0')" :x="(28 + L.brEnd) / 2" :y="L.capY" class="t-dim"
          text-anchor="middle">{{ t(k('beforeCap')) }}</text>
        <text :ref="tr('cap1')" :x="L.stackX + 13 + L.stack / 2" :y="L.capY" class="t-dim"
          text-anchor="middle">{{ t(k('stackCap')) }}</text>
        <text :ref="tr('cap2')" :x="L.resX + L.resW / 2" :y="L.capY" class="t-dim"
          text-anchor="middle">{{ t(k('resultCap')) }}</text>

        <!-- Under each sentence its word's row after attention — exemplary
             values, declared so in the closing line. Visibly different rows
             pay off the anchor planted by the embedding card's aside. -->
        <rect :x="L.bankX" y="46" :width="L.bankW" :height="L.bankH" rx="6" fill="none"
          stroke="#5a6a80" stroke-dasharray="5 4" opacity="0.9" />
        <text :ref="tr('bkh')" :x="L.bankX + 12" y="60" class="t-dim">{{ t(k('bankHead')) }}</text>
        <text :ref="tr('bk1')" :x="L.bankX + 12" y="76" class="t-sub">{{ t(k('bank1')) }}</text>
        <text :ref="tr('bk2')" :x="L.bankX + 12" y="110" class="t-sub">{{ t(k('bank2')) }}</text>
        <g v-for="(r, i) in BANKR" :key="`bkr${i}`">
          <rect :x="L.bankX + 12" :y="i === 0 ? 82 : 116" :width="L.bkChipW" height="13" rx="3"
            fill="#1d2f45" stroke="#3f6a9c" />
          <text :ref="tr(`bkt${i}`)" :x="L.bankX + 12 + L.bkChipW / 2" :y="(i === 0 ? 82 : 116) + 10"
            class="t-tok" text-anchor="middle">{{ r.s }}</text>
          <g v-for="(v, c) in r.vals" :key="`bkv${i}-${c}`">
            <rect :x="L.bankX + 12 + L.bkChipW + 8 + c * 42" :y="i === 0 ? 82 : 116"
              width="40" height="13" rx="2" fill="#1d2f45" stroke="#3f6a9c" />
            <text :x="L.bankX + 12 + L.bkChipW + 28 + c * 42" :y="(i === 0 ? 82 : 116) + 10"
              class="t-mono" text-anchor="middle">{{ v }}</text>
          </g>
          <text :x="L.bankX + 12 + L.bkChipW + 8 + 3 * 42 + 8" :y="(i === 0 ? 82 : 116) + 10"
            class="t-dim">…</text>
        </g>
        <text v-for="(ln, i) in BBANK" :key="`bb${i}`" :ref="tr(`bb${i}`)" :x="L.bankX + 12"
          :y="142 + i * 12" class="t-dim"><tspan
          v-for="(sg, si) in ln" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>

        <!-- Ten more points than the line pitch: the closing text is its own
             paragraph. -->
        <text v-for="(ln, i) in BCLOSE" :key="`bcl${i}`" :ref="tr(`bcl${i}`)" x="14"
          :y="L.closeY + i * 11" class="t-dim"><tspan
          v-for="(sg, si) in ln" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>

        <!-- Derselbe Vermerk wie auf der Karte davor, hier unter dem
             Bank-Kasten: der Schlussabsatz reicht auf dieser Karte weiter nach
             rechts, und die Karte wird nach ihrer Breite skaliert. -->
        <text v-for="(ln, i) in MODELNOTE" :key="`md${i}`" :ref="tr(`md${i}`)" :x="L.mdX"
          :y="L.mdY + i * 10" class="t-fine" text-anchor="end"><tspan
          v-for="(sg, si) in ln" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
      </g>

      <!-- The written line so far, the ranked odds under it, and the one that
           is drawn — which here is the line's own next piece, filling the
           dashed slot. The tokens are the tokenizer's real cuts, the values
           are exemplary (a didactic board does not warrant hours of
           computing). No way back up: the map runs downward, and the loop edge
           was taken off it. -->
      <g v-else-if="id === 'transformer.sampling'">
        <text :ref="tr('intro')" x="20" y="16" class="t-dim"><tspan
          v-for="(sg, si) in segments(t(k('intro')))" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
        <text :ref="tr('ctx')" x="20" y="52" class="t-mono">{{ t(k('context')) }}</text>
        <rect :x="L.ctxEnd" y="34" :width="L.slotW" height="26" rx="4"
          fill="none" stroke="#4CAF50" stroke-dasharray="4 4" opacity="0.8" />
        <text :x="L.ctxEnd + L.slotW / 2" y="52" class="t-mono" style="fill: #4CAF50"
          text-anchor="middle">{{ CANDS[0]?.tok }}</text>
        <!-- The chosen token runs back to the start: the whole walk repeats,
             token by token, until the end control token is the one chosen —
             the cycle the first draft drew as a return arrow, and the reason
             an answer grows word by word on screen. -->
        <path :d="`M${L.loopX + 16},46 A10,10 0 1 1 ${L.loopX + 23},33`" fill="none" stroke="#8b98a9"
          marker-end="url(#fsArrow)" />
        <text :ref="tr('lp1')" :x="L.loopX + 34" y="28" class="t-dim"><tspan
          v-for="(sg, si) in segments(t(k('loop1')))" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
        <text :ref="tr('lp2')" :x="L.loopX + 34" y="46" class="t-dim">{{ t(k('loop2')) }}</text>
        <rect :x="L.endX" y="35" :width="L.endW" height="15" rx="3" fill="#141b26" stroke="#2c3a4c" />
        <text :ref="tr('etk')" :x="L.endX + L.endW / 2" y="46" class="t-dim"
          text-anchor="middle">{{ `<|${t(k('endTok'))}|>` }}</text>
        <path :d="`M${(L.barX[0] ?? 0) + (L.slot[0] ?? 0) / 2},${146 - (CANDS[0]?.h ?? 0)}
          L${(L.barX[0] ?? 0) + (L.slot[0] ?? 0) / 2},72 L${L.ctxEnd + L.slotW / 2},72
          L${L.ctxEnd + L.slotW / 2},64`"
          fill="none" stroke="#4CAF50" stroke-width="1.1" />
        <!-- On the pull, not on the sentence line: at the line's height the
             caption read as the sentence's own continuation. -->
        <text :ref="tr('drawn')"
          :x="((L.barX[0] ?? 0) + (L.slot[0] ?? 0) / 2 + L.ctxEnd + L.slotW / 2) / 2" y="86"
          class="t-sub" text-anchor="middle"><tspan
          v-for="(sg, si) in segments(t(k('drawn')))" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>

        <g v-for="(c, i) in CANDS" :key="`c${i}`">
          <rect :x="(L.barX[i] ?? 0) + ((L.slot[i] ?? 0) - 30) / 2" :y="170 - c.h"
            width="30" :height="c.h" rx="3"
            :fill="i === 0 ? '#4CAF50' : '#3f6a9c'" :opacity="i === 0 ? 0.9 : 0.5" />
          <text :ref="tr(`v${i}`)" :x="(L.barX[i] ?? 0) + (L.slot[i] ?? 0) / 2" :y="164 - c.h"
            class="t-mono-dim" text-anchor="middle">{{ c.val }}</text>
          <text :ref="tr(`c${i}`)" :x="(L.barX[i] ?? 0) + (L.slot[i] ?? 0) / 2" y="186"
            class="t-mono" text-anchor="middle">{{ c.tok }}</text>
        </g>
        <line x1="20" y1="172" :x2="L.barsEnd" y2="172" stroke="#4a4a4a" />
        <text :ref="tr('chance')" x="20" y="206" class="t-sub"><tspan
          v-for="(sg, si) in segments(t(k('chance')))" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>

        <text :ref="tr('sharp')" :x="L.tempX" y="82" class="t-dim">{{ t(k('sharp')) }}</text>
        <rect v-for="(h, i) in TFLAT" :key="`tf${i}`"
          :x="L.tempX + i * 15" :y="170 - h" width="10" :height="h" rx="2"
          fill="#3f6a9c" opacity="0.5" />
        <text :ref="tr('flat')" :x="L.tempX + 35" y="186" class="t-dim"
          text-anchor="middle">{{ t(k('flat')) }}</text>
        <rect v-for="(h, i) in TSTEEP" :key="`ts${i}`"
          :x="L.tempX + 108 + i * 15" :y="170 - h" width="10" :height="h" rx="2"
          fill="#3f6a9c" opacity="0.5" />
        <text :ref="tr('steep')" :x="L.tempX + 108 + 35" y="186" class="t-dim"
          text-anchor="middle">{{ t(k('steep')) }}</text>

        <text v-for="(ln, i) in SNOTE" :key="`sn${i}`" :ref="tr(`n${i}`)" x="20" :y="222 + i * 13"
          class="t-dim"><tspan
          v-for="(sg, si) in ln" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>

        <!-- Derselbe Vermerk wie auf den beiden Karten davor. -->
        <text v-for="(ln, i) in MODELNOTE" :key="`md${i}`" :ref="tr(`md${i}`)" :x="L.mdX"
          :y="L.mdY + i * 10" class="t-fine" text-anchor="end"><tspan
          v-for="(sg, si) in ln" :key="si"
          :class="sg.term ? 't-term' : null">{{ sg.s }}</tspan></text>
      </g>

      <!-- =========================== CROSSINGS =========================== -->

      <g v-else-if="id === 'crossings.i2t'">
        <rect x="40" y="46" width="180" height="118" rx="8" fill="#2f3d4f" stroke="#4a4a4a" />
        <circle cx="86" cy="82" r="13" fill="#5a6b80" />
        <path d="M58,152 L114,88 L170,152 Z" fill="#44586e" />
        <path d="M130,152 L172,110 L206,152 Z" fill="#3b4d61" />

        <!-- COLUMNS, side by side — the shape the comparison itself has: one
             image, read by several models at once, each answering in its own
             column. The
             columns differ in how many lines they run to and how long those
             lines are, because the answers differ. This is where
             `vlm-analysis` marks in.

             The distributor goes over the top of the row rather than fanning
             out from the left: three lines out of one point on the left would
             have to cross the first column to reach the other two. -->
        <path d="M232 105 L256 105 L256 28 L657 28" fill="none" stroke="#8b98a9" />
        <g v-for="(bars, i) in I2T_COLS" :key="`i2tcol${i}`">
          <line :x1="349 + i * 154" y1="28" :x2="349 + i * 154" y2="40" stroke="#8b98a9"
                marker-end="url(#fsArrow)" />
          <rect :x="282 + i * 154" y="46" width="134" height="118" rx="8" fill="#151515"
                :stroke="TINT2[i]" />
          <rect v-for="(bw, j) in bars" :key="`i2tbar${i}-${j}`" :x="294 + i * 154" :y="64 + j * 18"
                :width="bw" height="8" rx="4" :fill="TINT2[i]" :opacity="0.85 - j * 0.09" />
        </g>
        <text :ref="tr('models')" x="282" y="186" class="t-sub">{{ t(k('models')) }}</text>
      </g>

      <!-- Drawn by nobody since 2026-08-23: the station was taken off the map
           (see flow_logic.vue). The drawing is left standing, like the i18n
           keys it reads, because it is a finished picture in ten languages
           and throwing it away is a separate decision. -->
      <g v-else-if="id === 'crossings.t2a'">
        <rect v-for="(w2, i) in [220, 180]" :key="i" x="30" :y="92 + i * 20" :width="w2" height="9" rx="4.5"
          fill="#5a6b80" opacity="0.8" />
        <text :ref="tr('text')" x="30" y="142" class="t-sub">{{ t(k('text')) }}</text>

        <line x1="266" y1="96" x2="316" y2="62" stroke="#8b98a9" marker-end="url(#fsArrow)" />
        <line x1="266" y1="112" x2="316" y2="150" stroke="#8b98a9" marker-end="url(#fsArrow)" />

        <path d="M328,54 q12,-30 24,0 q12,30 24,0 q12,-30 24,0 q12,30 24,0 q12,-30 24,0"
          fill="none" stroke="#5a7a64" stroke-width="2.5" />
        <text :ref="tr('music')" x="470" y="58" class="t-sub">{{ t(k('music')) }}</text>

        <rect v-for="c in 9" :key="c"
          :x="328 + (c - 1) * 15" :y="150 - (VOICE[c - 1] ?? 0) / 2"
          width="7" :height="VOICE[c - 1] ?? 0" rx="3.5" fill="#7f77dd" opacity="0.8" />
        <text :ref="tr('voice')" x="470" y="152" class="t-sub">{{ t(k('voice')) }}</text>
      </g>

      <g v-else-if="id === 'crossings.i2a'">
        <rect x="30" y="66" width="150" height="96" rx="8" fill="#2f3d4f" stroke="#4a4a4a" />
        <circle cx="66" cy="96" r="11" fill="#5a6b80" />
        <path d="M44,150 L92,98 L140,150 Z" fill="#44586e" />

        <line x1="192" y1="94" x2="240" y2="66" stroke="#8b98a9" marker-end="url(#fsArrow)" />
        <path d="M252,58 q12,-26 24,0 q12,26 24,0 q12,-26 24,0 q12,26 24,0"
          fill="none" stroke="#5a7a64" stroke-width="2.5" />
        <text :ref="tr('make')" x="388" y="62" class="t-sub">{{ t(k('make')) }}</text>

        <line x1="192" y1="130" x2="240" y2="150" stroke="#8b98a9" marker-end="url(#fsArrow)" />
        <rect x="250" y="122" width="120" height="54" rx="8" fill="#151515" stroke="#4a4a4a" stroke-dasharray="4 4" />
        <path d="M264,150 q10,-18 20,0 q10,18 20,0 q10,-18 20,0"
          fill="none" stroke="#5a7a64" stroke-width="2" opacity="0.6" />
        <path d="M310,112 L310,96" stroke="#4CAF50" stroke-width="1.2" marker-end="url(#fsArrow)" />
        <text :ref="tr('pull')" x="388" y="152" class="t-sub">{{ t(k('pull')) }}</text>
      </g>

      <!-- Five steps in a row, and the four things the last one can turn out
           to be. Both rows take their widths from their own words. -->
      <g v-else-if="id === 'crossings.chain'">
        <g v-for="(st, i) in STEPS" :key="st">
          <rect :x="L.step[i]" y="36" :width="L.stepW" height="56" rx="8"
            :fill="st === 's3' ? '#151515' : '#1d2f45'"
            :stroke="st === 's3' ? '#4a4a4a' : '#3f6a9c'"
            :stroke-dasharray="st === 's3' ? '4 4' : undefined" />
          <text
            :ref="tr(`${st}a`)" :x="(L.step[i] ?? 0) + L.stepW / 2"
            :y="stepLines[i]?.[1] ? 62 : 69" class="t-sub" text-anchor="middle"
          >{{ stepLines[i]?.[0] }}</text>
          <text
            v-if="stepLines[i]?.[1]" :ref="tr(`${st}b`)" :x="(L.step[i] ?? 0) + L.stepW / 2"
            y="80" class="t-sub" text-anchor="middle"
          >{{ stepLines[i]?.[1] }}</text>
          <line v-if="i < 4" :x1="(L.step[i] ?? 0) + L.stepW + 2" y1="64" :x2="(L.step[i] ?? 0) + L.stepW + 12" y2="64"
            stroke="#8b98a9" marker-end="url(#fsArrow)" />
        </g>
        <!-- Above the row, not under it: below, it lies across the four arrows
             that fan out of the last step. -->
        <text :ref="tr('s3note')" :x="L.step[2] ?? 0" y="24" class="t-dim">{{ t(k('s3note')) }}</text>

        <g v-for="(m, c) in ENDS" :key="m">
          <line :x1="L.last" y1="96" :x2="(L.end[c] ?? 0) + L.endW / 2" y2="130"
            stroke="#8b98a9" marker-end="url(#fsArrow)" />
          <rect :x="L.end[c]" y="136" :width="L.endW" height="30" rx="6" fill="#4a2b2f" stroke="#7a4046" />
          <text :ref="tr(m)" :x="(L.end[c] ?? 0) + L.endW / 2" y="156" class="t-sub" text-anchor="middle">
            {{ t(k(m)) }}
          </text>
        </g>
        <text :ref="tr('machines')" x="20" y="198" class="t-dim">{{ t(k('machines')) }}</text>
      </g>

      </template>

      <!-- ====================== THE SAME TWELVE, SMALL ======================
           What stands in a CLOSED box on the overview page. Not the drawing
           above shrunk — at a fifth the area its captions would be four pixels
           high — but the same statement with everything taken out of it that
           does not carry the statement. One shape per thing, one word where a
           word is unavoidable, and the markers, because the markers are what
           the page is for.

           Laid out in fixed coordinates, unlike the drawings above: there is
           one line of text in most of them, and the fit below handles the
           language that runs long. -->
      <template v-else>
        <g v-if="id === 'diffusion.prompt'">
          <rect x="10" y="28" :width="ML.ex" height="40" rx="6" fill="#0f0f0f" stroke="#7f77dd" />
          <!-- The written line as words, not letters: legible text in a box that
               otherwise shows only shapes reads as one specific instance, where the
               box means "there is a prompt". The real string still renders, at
               opacity 0, so it keeps sizing the box and the `language` marker's
               corner exactly as before -- same word-bar abstraction crossings.i2t
               already uses for its own text. -->
          <text :ref="tr('mExampleA')" x="21" y="44" class="t-dim" opacity="0">{{ EX[0] }}</text>
          <text :ref="tr('mExampleB')" x="21" y="59" class="t-dim" opacity="0">{{ EX[1] }}</text>
          <rect v-for="(b, bi) in EX_BARS[0]" :key="`wa${bi}`" :x="b.x" y="38" :width="b.w"
                height="6" rx="3" fill="#4d5768" />
          <rect v-for="(b, bi) in EX_BARS[1]" :key="`wb${bi}`" :x="b.x" y="53" :width="b.w"
                height="6" rx="3" fill="#4d5768" />
          <line :x1="ML.arrowA" y1="48" :x2="ML.arrowA + 20" y2="48" stroke="#8b98a9"
                marker-end="url(#fsArrow)" />
          <rect v-for="(c, i) in TINT" :key="c" :x="ML.tiles" :y="30 + i * 15" width="54"
                height="10" rx="3" :fill="c" :stroke="TINT2[i]" />
        </g>

        <g v-else-if="id === 'diffusion.encoder'">
          <rect v-for="(y, i) in [34, 50, 66]" :key="i" x="10" :y="y" width="46" height="10"
                rx="3" fill="#1b2233" stroke="#8b98a9" />
          <path v-for="(y, i) in [39, 55, 71]" :key="`j${i}`" :d="`M56 ${y} L96 55`"
                fill="none" stroke="#8b98a9" />
          <circle cx="101" cy="55" r="5" fill="#223046" stroke="#8f9ecb" />
          <line x1="108" y1="55" x2="130" y2="46" stroke="#8b98a9" marker-end="url(#fsArrow)" />
          <line x1="108" y1="55" x2="130" y2="66" stroke="#8b98a9" marker-end="url(#fsArrow)" />
          <rect x="140" y="41" width="112" height="10" rx="3" fill="#1b2233" stroke="#8b98a9" />
          <rect x="140" y="62" width="11" height="10" rx="2" fill="#1b2233" stroke="#8b98a9" />
        </g>

        <g v-else-if="id === 'diffusion.loop'">
          <rect x="16" y="30" :width="ML.den" height="30" rx="6" fill="#1b2233" stroke="#8b98a9" />
          <text :ref="tr('mDen')" :x="ML.denMid" y="50" class="t-dim" text-anchor="middle">{{ t(k('denoiser')) }}</text>
          <rect :x="ML.schX" y="30" :width="ML.sch" height="30" rx="6" fill="#1b2233" stroke="#8b98a9" />
          <text :ref="tr('mSch')" :x="ML.schMid" y="50" class="t-dim" text-anchor="middle">{{ t(k('scheduler')) }}</text>
          <line :x1="16 + ML.den + 6" y1="45" :x2="ML.schX - 6" y2="45" stroke="#8b98a9"
                marker-end="url(#fsArrow)" />
          <path :d="`M${ML.schMid} 64 L${ML.schMid} 78 L${ML.denMid + 6} 78 L${ML.denMid} 74`"
                fill="none" stroke="#8b98a9" marker-end="url(#fsArrow)" />
        </g>

        <g v-else-if="id === 'diffusion.decoder'">
          <g fill="#6f7d90">
            <circle v-for="(c, i) in GRID" :key="i" :cx="16 + c[0]" :cy="38 + c[1]" r="2.4" />
          </g>
          <line x1="60" y1="52" x2="82" y2="52" stroke="#8b98a9" marker-end="url(#fsArrow)" />
          <rect x="92" y="34" width="60" height="38" rx="5" fill="#1b2233" stroke="#8b98a9" />
          <path d="M98 66 L114 46 L126 60 L134 51 L146 66" fill="none" stroke="#8f9ecb" />
          <path d="M170 53 q10 -14 20 0 t20 0 t20 0 t20 0" fill="none" stroke="#8f9ecb" />
        </g>

        <g v-else-if="id === 'transformer.prompt'">
          <rect x="10" y="28" width="104" height="16" rx="4" fill="#1b2233" stroke="#7f77dd" />
          <rect x="10" y="50" width="104" height="16" rx="4" fill="#1b2233" stroke="#7f77dd" />
          <line x1="118" y1="36" x2="134" y2="45" stroke="#8b98a9" />
          <line x1="118" y1="58" x2="134" y2="49" stroke="#8b98a9" />
          <line x1="138" y1="47" x2="156" y2="47" stroke="#8b98a9" marker-end="url(#fsArrow)" />
          <rect x="162" y="32" width="62" height="30" rx="5" fill="#1b2233" stroke="#8b98a9" />
        </g>

        <!-- Dieselbe Aussage wie gross: drei Sprachen, verschieden viele
             Token, und jedes Token holt eine Zeile irgendwo in der Tabelle. -->
        <g v-else-if="id === 'transformer.vectors'">
          <!-- The large card in three strokes: one text bar, the token chips
               it falls into (the first one dimmed — a control token, two of
               them green — one word), and the number chips they become. -->
          <rect x="10" y="10" width="200" height="11" rx="3" fill="#1d2f45" stroke="#3f6a9c" />
          <g fill="#1d2f45" stroke="#3f6a9c">
            <rect x="10" y="31" width="30" height="12" rx="3" fill="#141b26" stroke="#2c3a4c" />
            <rect x="46" y="31" width="36" height="12" rx="3" />
            <rect x="88" y="31" width="24" height="12" rx="3" stroke="#4CAF50" />
            <rect x="118" y="31" width="16" height="12" rx="3" stroke="#4CAF50" />
            <rect x="140" y="31" width="34" height="12" rx="3" />
            <rect x="180" y="31" width="26" height="12" rx="3" />
          </g>
          <g fill="#1d2f45" stroke="#3f6a9c">
            <rect v-for="c in 6" :key="`mv${c}`" :x="10 + (c - 1) * 19" y="52"
              width="16" height="11" rx="2" />
          </g>
        </g>

        <g v-else-if="id === 'transformer.block'">
          <g fill="#8f9ecb">
            <circle v-for="(x, i) in ROW" :key="`p${i}`" :cx="x" cy="24" r="3.4" />
          </g>
          <path d="M248,30 Q144,58 40,30" fill="none" stroke="#7a4046" stroke-width="2" />
          <path d="M248,30 Q222,44 196,30" fill="none" stroke="#4CAF50" stroke-width="1.2" />
          <rect x="84" y="46" width="120" height="14" rx="3" fill="#1b2233" stroke="#8b98a9" opacity="0.5" />
          <rect x="92" y="52" width="120" height="14" rx="3" fill="#1b2233" stroke="#8b98a9" />
        </g>

        <g v-else-if="id === 'transformer.sampling'">
          <g v-for="(h, i) in MBARS" :key="i">
            <rect :x="12 + i * 26" :y="82 - h" width="18" :height="h" rx="2"
                  :fill="i === 1 ? '#4a2b2f' : '#1b2233'" :stroke="i === 1 ? '#e0a0a6' : '#6f7d90'" />
          </g>
        </g>

        <g v-else-if="id === 'crossings.i2t'">
          <rect x="10" y="34" width="52" height="38" rx="5" fill="#1b2233" stroke="#8b98a9" />
          <path d="M16 66 L30 48 L41 61 L48 53 L57 66" fill="none" stroke="#8f9ecb" />
          <line x1="70" y1="53" x2="92" y2="53" stroke="#8b98a9" marker-end="url(#fsArrow)" />
          <rect v-for="(wd, i) in [148, 168, 104]" :key="i" x="102" :y="38 + i * 15"
                :width="wd" height="9" rx="3" fill="#1b2233" stroke="#8b98a9" />
        </g>

        <g v-else-if="id === 'crossings.t2a'">
          <rect v-for="(wd, i) in [70, 54]" :key="i" x="10" :y="40 + i * 16"
                :width="wd" height="9" rx="3" fill="#1b2233" stroke="#8b98a9" />
          <line x1="88" y1="50" x2="112" y2="36" stroke="#8b98a9" marker-end="url(#fsArrow)" />
          <line x1="88" y1="54" x2="112" y2="72" stroke="#8b98a9" marker-end="url(#fsArrow)" />
          <path d="M124 36 q9 -13 18 0 t18 0 t18 0 t18 0" fill="none" stroke="#8f9ecb" />
          <path d="M124 72 q9 -9 18 0 t18 0 t18 0 t18 0" fill="none" stroke="#8f9ecb" />
        </g>

        <g v-else-if="id === 'crossings.i2a'">
          <rect x="10" y="32" width="50" height="36" rx="5" fill="#1b2233" stroke="#8b98a9" />
          <path d="M16 62 L29 45 L39 57 L46 50 L55 62" fill="none" stroke="#8f9ecb" />
          <line x1="68" y1="42" x2="100" y2="42" stroke="#8b98a9" marker-end="url(#fsArrow)" />
          <path d="M112 42 q9 -13 18 0 t18 0 t18 0 t18 0" fill="none" stroke="#8f9ecb" />
          <path d="M68 64 q26 20 42 8" fill="none" stroke="#8b98a9" stroke-dasharray="3 4"
                marker-end="url(#fsArrow)" />
          <path d="M118 74 q9 -11 18 0 t18 0 t18 0 t18 0" fill="none" stroke="#8f9ecb" />
        </g>

        <g v-else-if="id === 'crossings.chain'">
          <g v-for="(st, i) in STEPS" :key="st">
            <rect :x="10 + i * 42" y="42" width="36" height="24" rx="4" fill="#1b2233" stroke="#8b98a9" />
            <line v-if="i < 4" :x1="46 + i * 42" y1="54" :x2="52 + i * 42" y2="54" stroke="#8b98a9" />
          </g>
          <path v-for="(y, i) in [36, 48, 62, 74]" :key="`f${i}`" :d="`M222 54 L256 ${y}`"
                fill="none" stroke="#8b98a9" />
        </g>
      </template>

      <!-- The markers: where an instrument of this lab reaches in. The page
           owns which ones and where; this only sets them down. The wide circle
           under the point is the area that answers to a pointer — a 3 px dot in
           a drawing scaled to a third is under two pixels on screen.

           RING AND CENTRE, not a plain filled dot. The drawings use the same
           green for something of their own — the two word pieces in the
           embedding field, the one place the others read in the block — and a
           plain green dot would be indistinguishable from those. The ring is
           the mark's own shape and belongs to no drawing.

           A MARKER IS OPERABLE, not a hover-only decoration. Pointing at it or
           reaching it with the keyboard lights its instruments in the column.
           Pressing it (mouse, Enter, Space) opens the instrument when there is
           only one — which is what a chip of the deleted footnote did — and
           otherwise puts the column up and moves the focus onto the first of the
           lit names, because three instruments cannot all be opened at once and
           the choice is the visitor's. `aria-label` carries the names, because a
           ring cannot be read aloud.

           IN THE SMALL FORM IT IS NOT AN ACTUATOR. A closed box IS a button and
           its one job is to open; a press that landed on the ~20 px disc of a
           marker would otherwise do something else entirely, and the box would
           have a dead spot in it. So the small form marks and says (`role=img`,
           `aria-label`, the light on pointer and on focus) and lets the press
           through to the box; `tabindex` is -1 there, because sixteen more tab
           stops laid over twelve boxes would make the map slower to walk than it
           was with the footnote. The way in by keyboard is the box, then the
           markers in it, which carry `tabindex=0` and take Enter and Space. -->
      <g
        v-for="(m, i) in placed"
        :key="`m${i}`"
        class="fs-mark"
        :role="mini ? 'img' : 'button'"
        :tabindex="mini ? -1 : 0"
        :aria-label="m.label"
        @pointerenter="emit('mark', [...m.hosts])"
        @focus="emit('mark', [...m.hosts])"
        @click="pick($event, m.hosts)"
        @keydown.enter="pick($event, m.hosts)"
        @keydown.space="pick($event, m.hosts)"
      >
        <circle :cx="m.pt[0]" :cy="m.pt[1]" :r="mini ? 11 : 13" class="fs-hit" />
        <circle :cx="m.pt[0]" :cy="m.pt[1]" :r="mini ? 6.5 : 8" class="fs-ring" />
        <circle :cx="m.pt[0]" :cy="m.pt[1]" :r="mini ? 2.6 : 3.2" class="fs-dot" />
      </g>
    </g>
  </svg>
</template>

<script setup lang="ts">
import { computed, getCurrentInstance, nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { en } from '@/i18n/en'

export interface StationMark {
  /** WHICH PLACE in the drawing, by name — never a coordinate. The page says
   *  what reaches in where; the drawing knows where that is, and has to, now
   *  that its geometry comes out of the words and moves with the language. */
  at: string
  /** The instruments that reach in here, by their id in the lab's catalogue. */
  hosts: string[]
  /**
   * Their NAMES, already read off the catalogue by the page.
   *
   * Not shown: the drawing has no room for them and the column on the left
   * carries them. This is what the marker says when it is read aloud, and the
   * drawing must not have to know the catalogue to say it.
   */
  label: string
}

const props = defineProps<{
  /** `<band>.<station>`, the i18n path under latentLab.flowLogic. */
  id: string
  marks: StationMark[]
  /**
   * The small form, for a CLOSED box on the overview page.
   *
   * Not a scale of the large one. At 300 x 96 instead of 930 x 260 the same
   * drawing would put its captions at four pixels, so the small form is drawn
   * separately: the same statement with everything left out that does not carry
   * it. Both forms are in this file, because both are the drawing of that
   * station and two files would drift apart.
   */
  mini?: boolean
}>()

/**
 * `mark` — a pointer or the focus came to rest on a marker: light these.
 *   Only on the way IN. Nothing is sent on the way out, so the names stay lit
 *   long enough to reach them; the next marker replaces them.
 * `pick` — the marker was pressed: take me to these.
 */
const emit = defineEmits<{
  (e: 'mark', hosts: string[]): void
  (e: 'pick', hosts: string[]): void
}>()

/**
 * A marker was pressed.
 *
 * Nothing happens in the small form — see the note in the template: the press
 * belongs to the closed box. In the large one the event is stopped, because it
 * would otherwise reach the box behind the drawing, whose click opens and whose
 * keydown TOGGLES, so Enter on a marker would fold the box shut under it.
 */
function pick(e: Event, hosts: string[]): void {
  if (props.mini) return
  e.preventDefault()
  e.stopPropagation()
  emit('pick', [...hosts])
}

const { t, locale } = useI18n()

// The two noise filters are referenced by id, and an id is global to the
// document — three drawings mounted at once would all take the first one's.
const uid = getCurrentInstance()?.uid ?? 0

function k(name: string): string {
  return `latentLab.flowLogic.${props.id}.${name}`
}

/**
 * The canvas this drawing is laid out in, and the room inside it the fit below
 * has to land in. The small form keeps the same margin proportionally, so a
 * caption that runs long in German is scaled down by the same rule in both.
 */
const VB = computed(() =>
  props.mini
    // 76 and not 96: the station's NAME is not in this drawing any more. It is
    // set as type above it, in the node itself, where it keeps a rem step and a
    // floor instead of shrinking with the map — this platform's own rule for
    // flow stages, and the reason the box labels never got small before. What
    // is left is the strip the shapes stand in, and `fit` centres them in it.
    ? { w: 300, h: 76, iw: 288, ih: 70, grow: 1 }
    // 320 und nicht 260: die geoeffnete Kachel ist keine so flache Leiste,
    // wie der viewBox behauptete. An sieben Fenstergroessen gemessen
    // (2026-08-26) gibt ihr SVG zwischen 338 und 364 Einheiten Hoehe her, ohne
    // dass die Zeichnung dabei im geringsten kleiner wird — die Breite bindet,
    // die Hoehe nicht. Bei 260 lagen also rund achtzig Einheiten brach, und
    // die Stationen wurden an einer Grenze geschrumpft, die es nicht gab. 320
    // laesst Rand bis zur schmalsten gemessenen Lage.
    : { w: 930, h: 320, iw: 910, ih: 304, grow: 1.25 },
)

// ---------------------------------------------------------------------------
// Measuring
//
// getComputedTextLength() answers in USER units — the same 930 x 260 the
// drawing is laid out in — so a measurement can be put straight back into the
// geometry, at any window width, in any language.
// ---------------------------------------------------------------------------

const els = new Map<string, SVGTextElement>()
const W = ref<Record<string, number>>({})
const gEl = ref<SVGGElement | null>(null)
/** What the drawing actually covers, once the words have set the geometry. */
const box = ref<{ x: number; y: number; w: number; h: number } | null>(null)

/** Template ref that files a `<text>` under a name for measuring. */
function tr(key: string) {
  return (el: unknown) => {
    if (el) els.set(key, el as SVGTextElement)
    else els.delete(key)
  }
}

function remeasure() {
  const next: Record<string, number> = {}
  els.forEach((el, key) => {
    try { next[key] = el.getComputedTextLength() } catch { next[key] = 0 }
  })
  W.value = next
  // A tick later, because the widths have to reach the geometry first. getBBox
  // reads the group's children, not the group's own transform, so placing the
  // group from it does not chase its own tail.
  nextTick(() => {
    try {
      const b = gEl.value?.getBBox()
      if (b && b.width > 0) box.value = { x: b.x, y: b.y, w: b.width, h: b.height }
    } catch { /* not laid out yet */ }
  })
}

/**
 * A caption too long for its box, broken at the space nearest the middle.
 *
 * No break list and no hyphenation — the two halves are measured like every
 * other piece of text, so the box still comes out the width of its own words in
 * whatever language they are written. Wrapping is what buys the room: three
 * captions of this station laid out in a row take more than the 930 there are,
 * and everything then has to be drawn smaller to fit.
 */
function twoLines(str: string): [string, string] {
  const mid = str.length / 2
  let cut = -1
  for (let i = 0; i < str.length; i++) {
    if (str[i] === ' ' && (cut < 0 || Math.abs(i - mid) < Math.abs(cut - mid))) cut = i
  }
  return cut < 0 ? [str, ''] : [str.slice(0, cut), str.slice(cut + 1)]
}

/** The same idea as `twoLines`, for a caption that has to stand in a narrow
 *  column instead of a wide one: greedy fill to a target line length. */
function nLines(str: string, n: number): string[] {
  const words = str.split(' ')
  const target = Math.ceil(str.length / n)
  const out: string[] = ['']
  for (const word of words) {
    const line = out[out.length - 1]!
    if (line && line.length + 1 + word.length > target && out.length < n) out.push(word)
    else out[out.length - 1] = line ? `${line} ${word}` : word
  }
  while (out.length < n) out.push('')
  return out
}

const isLoop = computed(() => props.id === 'diffusion.loop')
const stepLines = computed<[string, string][]>(() =>
  STEPS.map(st => (props.id === 'crossings.chain' ? twoLines(t(k(st))) : ['', ''])),
)
const dSub = computed<[string, string]>(() => (isLoop.value ? twoLines(t(k('denoiserSub'))) : ['', '']))
const scSub = computed<[string, string]>(() => (isLoop.value ? twoLines(t(k('schedulerSub'))) : ['', '']))
/** Four narrow lines, not two wide ones: the width this column used to take is
 *  what the incoming embedding on the left now stands in; the comment column
 *  on the right may be multi-line and narrower. */
const tailSub = computed<string[]>(() => (isLoop.value ? nLines(t(k('nothing')), 4) : ['', '', '', '']))

/** The prompt embedding, as it reaches the denoiser. Same visual language as
 *  the Embedding-Prozess station's vectors — invented numbers standing for the
 *  768-4096 a real one holds. */
const COND_ROWS = [
  ['0.42', '-0.18', '0.91', '…'],
  ['-0.27', '0.64', '-0.11', '…'],
  ['0.15', '-0.72', '0.38', '…'],
]
const EXPLAIN = computed<[string, string]>(() =>
  props.id === 'diffusion.decoder' ? twoLines(t(k('explain'))) : ['', ''],
)

/** A scattered, unconnected cluster of five — the 16 VAE channels have no
 *  known systematic order, so this deliberately isn't a grid or a row. */
const MATRIX_POS: [number, number][] = [
  [0, 0],
  [46, -10],
  [88, 16],
  [12, 48],
  [60, 54],
]

/** Vertical centers of the four output rows (Bild, Klang, Video, 3D), spread
 *  around the VAE box's own center (y=128). */
const ROW_CENTERS = [59, 105, 151, 197]

/** A measured width, or a placeholder for the frame before the first measure. */
function w(key: string, fallback = 80): number {
  const v = W.value[key]
  return v && v > 0 ? v : fallback
}

onMounted(() => {
  nextTick(remeasure)
  // A web font that arrives after the first paint changes every width at once.
  const fonts = (document as Document & { fonts?: FontFaceSet }).fonts
  fonts?.ready?.then(() => nextTick(remeasure))
})
watch(() => [props.id, props.mini, locale.value], () => {
  els.clear()
  box.value = null
  nextTick(remeasure)
})

// ---------------------------------------------------------------------------
// Fixed material: shapes, not words.
// ---------------------------------------------------------------------------

const PAD = 18   // words to box edge, each side
const GAP = 34   // one arrow between two things
const SQ = 86    // a state square

const TINT = ['#2f3d4f', '#3d3546', '#2f4438']
const TINT2 = ['#5a6b80', '#6b5a72', '#5a7a64']
const TINT3 = ['#44586e', '#584a63', '#446a53']

/**
 * The same standard sentence, written out in two other languages besides
 * whichever the page itself is in — not translated at render time, because
 * the point is to show what the sentence looks like AS WRITTEN in that
 * language. Real text: each language file's own rendering of this platform's
 * standard test prompt (`promptExamples.presets.house`, both of its
 * sentences), read for these three locales whatever the page's locale is.
 * Until 2026-09-22 the three sentences stood here by hand, as a second
 * rendering beside the language file's own and without the prompt's second
 * sentence.
 */
// English is not among them: it is the TARGET of the translation box next
// to them, so an English example here would be one that needs no
// translating and would undercut the very point being made.
const LANG_ORDER = ['de', 'tr', 'ko']
function langSample(code: string): [string, string] {
  return twoLines(t('promptExamples.presets.house', {}, { locale: code }))
}

/**
 * Three distinct little landscapes, one per row — sun on the left, sun on
 * the right, twin peaks — so the three read as similar but different, not
 * the same icon shifted a few pixels. Coordinates are local to the icon's own
 * 44x30 box; `triPath` places them at the box's actual position.
 */
const ICONS: { sun: [number, number]; tris: number[][][] }[] = [
  { sun: [10, 8], tris: [[[18, 28], [30, 10], [42, 28]]] },
  { sun: [34, 8], tris: [[[2, 28], [14, 10], [26, 28]]] },
  { sun: [38, 6], tris: [[[2, 28], [12, 12], [22, 28]], [[20, 28], [32, 8], [44, 28]]] },
]
function triPath(pts: number[][], ox: number, oy: number): string {
  return pts.map(([x, y], j) => `${j === 0 ? 'M' : 'L'}${ox + (x ?? 0)},${oy + (y ?? 0)}`).join(' ') + ' Z'
}

/**
 * The two of the three that are not the page's own language — the page's own
 * goes on top instead, in the field that used to stand alone to the left:
 * the three stacked boxes replace that single one, and the topmost is in the
 * system language. When the active language
 * is none of the three, the first two of them are shown — a fixed order, not
 * a fourth judgement call about which two matter more.
 */
const OTHER_LANGS = computed<[string, string][]>(() =>
  LANG_ORDER.filter(code => code !== locale.value).slice(0, 2).map(code => langSample(code)),
)
/** Three columns of an answer each, in bar lengths. Different line counts on
 *  purpose: the models do not answer at the same length. */
const I2T_COLS: number[][] = [[110, 92, 104, 62], [96, 110, 70], [104, 84, 110, 96, 54]]
const VOICE = [8, 20, 12, 28, 34, 22, 30, 14, 9]
const STEPS = ['s1', 's2', 's3', 's4', 's5']
const ENDS = ['m1', 'm2', 'm3', 'm4']
/** How many numbers the list is drawn with — a picture, not a count. */
/**
 * The token chips of the cut sentence, one line per chip: `label¦place¦flags`.
 * Flags, each a single letter: `c` a control token (dimmed), `h` a token whose
 * number row is drawn below (green edge), `f` part of the one word that falls
 * into several tokens (the group label sits under these), `g` a gap that
 * stands for the skipped places — dots, no box.
 */
type TChip = { s: string; pos: string; ctrl: boolean; hot: boolean; four: boolean; gap: boolean }
const TCHIPS = computed<TChip[]>(() =>
  props.id === 'transformer.vectors'
    ? t(k('chips')).split('\n').map(l => {
        const f = l.split('¦')
        const fl = f[2] ?? ''
        return {
          s: f[0] ?? '',
          pos: f[1] ?? '',
          ctrl: fl.includes('c'),
          hot: fl.includes('h'),
          four: fl.includes('f'),
          gap: fl.includes('g'),
        }
      })
    : [],
)

/** One measured number row per green-edged token: `label¦number¦number…`. */
type ERow = { s: string; vals: string[] }
const EROWS = computed<ERow[]>(() =>
  props.id === 'transformer.vectors'
    ? t(k('rows')).split('\n').map(l => {
        const f = l.split('¦')
        return { s: f[0] ?? '', vals: f.slice(1) }
      })
    : [],
)

/** Cut sizes per language: `code\u00a6name\u00a6tokens` per line. */
const LANGS = computed<{ code: string; s: string; n: number; mine: boolean }[]>(() =>
  props.id === 'transformer.vectors'
    ? t(k('langs')).split('\n').filter(Boolean).map((ln) => {
        const p = ln.split('\u00a6')
        return {
          code: p[0] ?? '',
          s: p[1] ?? '',
          n: Number(p[2] ?? 0),
          // The bar of the language being read is the one that answers "and
          // mine?", so it carries the accent instead of English.
          mine: (p[0] ?? '') === String(locale.value).slice(0, 2),
        }
      })
    : [],
)

const LANGNOTE = computed<Seg[][]>(() =>
  props.id === 'transformer.vectors' ? t(k('langNote')).split('\n').filter(Boolean).map(segments) : [],
)

/**
 * Which model the numbers on the transformer's cards were measured on. One
 * line each. It is ONE key for the three cards that carry measured numbers:
 * the sentence is the same on all of them, and a translator should not have to
 * write it three times and keep three copies in step.
 */
const MDNOTE_ON = ['transformer.vectors', 'transformer.block', 'transformer.sampling']
const MODELNOTE = computed<Seg[][]>(() =>
  MDNOTE_ON.includes(props.id)
    ? t('latentLab.flowLogic.transformer.modelNote').split('\n').filter(Boolean).map(segments)
    : [],
)

/** The alphabet the measured row is written in: 32 steps, `0`-`9` then `a`-`v`. */
const VECA = '0123456789abcdefghijklmnopqrstuv'
/** Cell width and row height of the band, in the drawing's own units. */
const VW = 1.05
const VH = 5
/** Diverging ramp through a dark middle: below zero cool, above zero warm.
 *  Neither end is the green of the drawing's own tokens, so a cell can never
 *  be read as "this one is meant". Thirty-two steps where the 48-cell strip
 *  had nine: a band of 2,560 can carry the finer grading. */
const VECC = [
  '#2b6cb0', '#2e6baa', '#316aa5', '#34699f', '#37689a', '#376694', '#38648f', '#39618a',
  '#3a5f84', '#3a5c7e', '#3a5979', '#3a5573', '#3a526d', '#3a4e65', '#3a4a5e', '#3a4656',
  '#404651', '#4c4a4d', '#594e49', '#665246', '#705642', '#7a5a3f', '#835e3c', '#8c6238',
  '#936536', '#9a6835', '#a06b33', '#a76e32', '#ad7130', '#b3742f', '#b9772d', '#c07a2c',
]

/**
 * The measured row as 4 x 640 cells - ALL 2,560 numbers of one real token, not
 * a sample of them: one real token out of the 150k+ vocabulary, with its real
 * values.
 *
 * One PATH per colour step with equal neighbours merged into one stroke, not
 * one rect per number: the band then costs at most 32 nodes instead of 2,560,
 * and a run of equal cells comes out without seams inside it.
 */
const VEC = computed<{ c: string; d: string }[]>(() => {
  if (props.id !== 'transformer.vectors') return []
  const v = t(k('vec')).replace(/[^0-9a-v]/g, '')
  if (v.length < 2560) return []
  const runs: string[][] = VECC.map(() => [])
  for (let r = 0; r < 4; r++) {
    let i = 0
    while (i < 640) {
      const step = VECA.indexOf(v[r * 640 + i] ?? '')
      let j = i + 1
      while (j < 640 && VECA.indexOf(v[r * 640 + j] ?? '') === step) j++
      if (step >= 0) {
        runs[step]?.push(`M${(i * VW).toFixed(2)} ${r * VH + VH / 2}h${((j - i) * VW).toFixed(2)}`)
      }
      i = j
    }
  }
  return VECC.map((c, i) => ({ c, d: (runs[i] ?? []).join('') })).filter(p => p.d !== '')
})

/** What the band is, and which token it belongs to. One line each. */
const VECNOTE = computed<Seg[][]>(() =>
  props.id === 'transformer.vectors' ? t(k('vecNote')).split('\n').filter(Boolean).map(segments) : [],
)
/** The three marks under the colour ruler: low, zero, high. */
const VECSCALE = computed<string[]>(() =>
  props.id === 'transformer.vectors' ? t(k('vecScale')).split('\u00a6') : [],
)

const VCLOSE = computed<Seg[][]>(() =>
  props.id === 'transformer.vectors' ? t(k('close')).split('\n').map(segments) : [],
)

/** The chips of the returning sentence: `token¦flags` per line — `h` the
 *  token whose walk through the layers is shown, `g` a gap of dots. */
type BChip = { s: string; hot: boolean; gap: boolean }
const BCHIPS = computed<BChip[]>(() =>
  props.id === 'transformer.block'
    ? t(k('chips')).split('\n').map(l => {
        const f = l.split('¦')
        const fl = f[1] ?? ''
        return { s: f[0] ?? '', hot: fl.includes('h'), gap: fl.includes('g') }
      })
    : [],
)

/** The exemplary arcs: `fromIndex¦toIndex¦label¦strokeWidth` per line, the
 *  indices counting chips of `chips` from zero, gaps included. */
type BArc = { from: number; to: number; label: string; width: number }
const BARCS = computed<BArc[]>(() =>
  props.id === 'transformer.block'
    ? t(k('arcs')).split('\n').map(l => {
        const f = l.split('¦')
        return { from: Number(f[0] ?? 0), to: Number(f[1] ?? 0), label: f[2] ?? '', width: Number(f[3] ?? 1.4) }
      })
    : [],
)

/** The measured starting row of the shown token: `token¦number¦number…`. */
const BROW = computed<{ s: string; vals: string[] }>(() => {
  if (props.id !== 'transformer.block') return { s: '', vals: [] }
  const f = t(k('beforeRow')).split('¦')
  return { s: f[0] ?? '', vals: f.slice(1) }
})

const BBANK = computed<Seg[][]>(() =>
  props.id === 'transformer.block' ? t(k('bankNote')).split('\n').map(segments) : [],
)
/** The bank rows after attention: `word¦n¦n¦n` per line, exemplary values. */
const BANKR = computed<{ s: string; vals: string[] }[]>(() =>
  props.id === 'transformer.block'
    ? t(k('bankRows')).split('\n').filter(Boolean).map((ln) => {
        const p = ln.split('\u00a6')
        return { s: p[0] ?? '', vals: p.slice(1, 4) }
      })
    : [],
)

const BCLOSE = computed<Seg[][]>(() =>
  props.id === 'transformer.block' ? t(k('close')).split('\n').map(segments) : [],
)

/**
 * The ranked odds of the Sampling station: `token¦value` per line, tallest
 * first. `h` is the bar in drawing units; the tail line (`…`) keeps no value
 * and stands at 4 units, for the rest of the table.
 */
type Cand = { tok: string; val: string; h: number }
const CANDS = computed<Cand[]>(() =>
  props.id === 'transformer.sampling'
    ? t(k('cands')).split('\n').map((line) => {
        const f = line.split('¦')
        const p = parseFloat(f[1] ?? '')
        return { tok: f[0] ?? '', val: f[1] ?? '', h: Number.isFinite(p) ? Math.max(6, p * 2.6) : 4 }
      })
    : [],
)
const SNOTE = computed<Seg[][]>(() =>
  props.id === 'transformer.sampling' ? t(k('note')).split('\n').map(segments) : [],
)
/** The same odds twice tempered: flattened, steepened. Shapes, not claims. */
const TFLAT = [34, 28, 24, 20, 17]
const TSTEEP = [72, 16, 7, 3, 2]

/**
 * The written line, in two halves. This platform's standard sentence — a house
 * in a landscape, with farmland, nature and animals — is a whole sentence, and
 * at 19 px it is three times the width the drawing has for it.
 */
const EX = computed<[string, string]>(() => twoLines(t('latentLab.flowLogic.diffusion.prompt.example')))

interface WordBar { x: number; w: number }

/** A line of words, redrawn as one bar per word: the shape a sentence makes,
 *  not the sentence itself. Deterministic from the line's own words, so it is
 *  the same drawing every time it is opened, in any language. */
function wordBars(line: string, startX: number): WordBar[] {
  const bars: WordBar[] = []
  let x = startX
  for (const word of line.split(' ').filter(Boolean)) {
    const bw = Math.max(6, Math.min(34, word.length * 3.4))
    bars.push({ x, w: bw })
    x += bw + 4
  }
  return bars
}
const EX_BARS = computed<[WordBar[], WordBar[]]>(() => [wordBars(EX.value[0], 21), wordBars(EX.value[1], 21)])

/** The provider's own instructions, in the same field as the written prompt. */
const SYS = computed<[string, string]>(() =>
  props.id === 'transformer.prompt' ? twoLines(t(k('sysExample'))) : ['', ''],
)

/**
 * The one text the model is actually handed. The marks are the model's own —
 * they sit in the chat template inside the file we run, not in any wording of
 * ours, so they are not translated and not paraphrased.
 */
const ASM = computed<string[]>(() =>
  props.id === 'transformer.prompt'
    ? [
        '<|im_start|>system',
        `${clip(t(k('sysExample')), 24)}<|im_end|>`,
        '<|im_start|>user',
        `${clip(t('latentLab.flowLogic.diffusion.prompt.example'), 24)}<|im_end|>`,
      ]
    : ['', '', '', ''],
)

const PNOTE = computed<string[]>(() =>
  props.id === 'transformer.prompt' ? nLines(t(k('note')), 4) : ['', '', '', ''],
)

/** Cut to a length the box can hold, at a word, with the cut shown. */
function clip(str: string, n: number): string {
  if (str.length <= n) return str
  const cut = str.slice(0, n)
  const sp = cut.lastIndexOf(' ')
  return `${(sp > n / 2 ? cut.slice(0, sp) : cut).trimEnd()} …`
}

/** Forced to English, not the page's language: the encoders tokenize what the
 *  platform actually feeds them, which is the already-translated prompt. */
const ENC_SENTENCE = computed<[string, string]>(() =>
  props.id === 'diffusion.encoder' ? twoLines(en.latentLab.flowLogic.diffusion.prompt.example) : ['', ''],
)

/** The three stacked fields: the page's own language on top, two others below. */
const PROMPT_STACK = computed<[string, string][]>(() => [EX.value, ...OTHER_LANGS.value])

/** How wide one encoder's box is. Fixed, so the three stand in a column. */
const ENC_W = 190

/** The three encoders of SD3.5, in the order the drawing stacks them. */
const ENC_NAMES = ['CLIP-L', 'CLIP-G', 'T5']

/**
 * One word from the standard sentence that a real tokenizer cuts into three
 * pieces, so the drawing can show what a vector actually is: a token next to
 * a long row of numbers, not a single blank box (after Jay Alammar's "The
 * Illustrated Word2Vec": a single box cannot represent a vector). Real
 * split, invented numbers — the
 * numbers stand for the 768-4096 a real vector holds, which is why the row
 * ends in an ellipsis instead of trying to show all of them.
 */
const VECWORD = computed<string[]>(() =>
  en.latentLab.flowLogic.diffusion.encoder.vecWord.split(' ').filter(Boolean),
)
const VEC_NUMS = [
  ['0.42', '-0.18', '0.91', '-0.05', '0.33', '\u2026'],
  ['-0.27', '0.64', '-0.11', '0.08', '-0.49', '\u2026'],
  ['0.15', '-0.72', '0.38', '0.21', '-0.06', '\u2026'],
]
const POOLED_NUMS = ['0.09', '-0.31', '0.55', '-0.44', '0.17', '\u2026']

/**
 * The real tokens, as many as the box holds, one chip per token — not
 * abstract lines, and not one long unbroken row. They come from running
 * `openai/clip-vit-large-patch14`, `laion/CLIP-ViT-bigG-14-laion2B-39B-b160k`
 * and `google/t5-v1_1-xxl` over the standard sentence OF THAT LANGUAGE, which
 * is why `tokenSentence`/`tokens1..3` sit beside each other in the language
 * file: the row and the sentence above it are the same text. No vocabulary
 * markers (`</w>`, `▁`) are kept in that text.
 *
 * A token that does not fit is kept in the DOM so it can be measured, but
 * drawn at the box's own left edge and hidden: `getBBox` counts hidden
 * children, and one parked outside would widen the whole drawing.
 */
type Tok = { s: string; x: number; w: number; key: string; show: boolean }
const TOKROWS = computed<Tok[][]>(() => {
  if (props.id !== 'diffusion.encoder') return []
  return [0, 1, 2].map(r => {
    const tokenKey = `tokens${r + 1}` as 'tokens1' | 'tokens2' | 'tokens3'
    const list = en.latentLab.flowLogic.diffusion.encoder[tokenKey].split(' ').filter(Boolean)
    const out: Tok[] = []
    let x = 12
    list.forEach((str, i) => {
      const key = `tk${r}_${i}`
      const cw = w(key, 26) + 12
      const show = x + cw <= ENC_W - 12
      out.push({ s: str, x: show ? x : 12, w: cw, key, show })
      if (show) x += cw + 5
    })
    return out
  })
})


/**
 * A caption in pieces, so a term inside it can carry the term colour. The
 * marks are `[[…]]` in the language file, which is where they belong: which
 * word is the technical one is a question about that language's sentence, not
 * about the drawing. All technical terms get the same highlight colour on
 * this page.
 */
type Seg = { s: string; term: boolean }
function segments(line: string): Seg[] {
  return line
    .split(/(\[\[[^\]]+\]\])/)
    .filter(Boolean)
    .map(part =>
      part.startsWith('[[') && part.endsWith(']]')
        ? { s: part.slice(2, -2), term: true }
        : { s: part, term: false },
    )
}

/**
 * The note under the loop's drawing: three written lines, each already cut into
 * segments. The lines are set in the language file, not wrapped here — where a
 * sentence of this length breaks is a question about that sentence.
 */
const NOTE = computed<Seg[][]>(() =>
  props.id === 'diffusion.loop' ? t(k('note')).split('\n').map(segments) : [],
)

/** The encoder caption, two written lines, each already cut into segments. */
const READERS = computed<Seg[][]>(() => {
  const raw = props.id === 'diffusion.encoder' ? t(k('readers')) : ''
  const [a, b] = raw.split('\n')
  return [segments(a ?? ''), segments(b ?? '')]
})

// --- the small form ---------------------------------------------------------
// Fixed shapes in the 300 x 96 the small canvas is. Nothing here is measured:
// there is at most one line of text per drawing, and `fit` handles the language
// that runs long by taking the whole group down a little.
const GRID: [number, number][] = [
  [0, 0], [12, 0], [24, 0], [0, 12], [12, 12], [24, 12], [0, 24], [12, 24], [24, 24],
]
const ROW = [40, 92, 144, 196, 248]
const MBARS = [26, 44, 14, 34, 10, 22, 16, 30]

/**
 * The three small drawings that carry a word, laid out from that word.
 *
 * Everything else in the small form is shapes, and shapes can stand in fixed
 * coordinates. A word cannot: „a family at dinner" fills two thirds of its box
 * in English and runs a sixth past it in German. The large form has measured
 * its boxes since the day the German ran out of one; the small form was drawn
 * fixed and would have repeated it.
 */
const ML = computed(() => {
  const ex = Math.max(96, Math.max(w('mExampleA', 92), w('mExampleB', 92)) + 22)
  const den = Math.max(76, w('mDen', 52) + 26)
  const sch = Math.max(76, w('mSch', 56) + 26)
  return {
    ex,
    arrowA: 10 + ex + 8,
    tiles: 10 + ex + 40,
    den,
    sch,
    schX: 16 + den + 42,
    denMid: 16 + den / 2,
    schMid: 16 + den + 42 + sch / 2,
  }
})

/**
 * Where an instrument reaches into the SMALL drawing. Same names as the large
 * one — the page says `at: 'denoiser'` once and both forms know the place.
 *
 * A marker sits ON what it marks, the way the large form's do; beside it, it is
 * a green dot floating in a box. Computed, not fixed, wherever the shape under
 * it is laid out from a measured word.
 */
const MINI_AT = computed<Record<string, Record<string, [number, number]>>>(() => ({
  // The field's corner. On the tiles it sat on the middle one — see the large
  // form: rows 30, 45 and 60, and 45 is German.
  'diffusion.prompt': { language: [10 + ML.value.ex, 28] },
  'diffusion.encoder': { readers: [33, 55], mix: [101, 55], conditioning: [252, 46] },
  'diffusion.loop': {
    denoiser: [16 + ML.value.den - 14, 45],
    state: [ML.value.denMid + 30, 78],
    weights: [30, 45],
    // Same claim as the large form's corner mark, at the mini drawing's own
    // top-right; the closed tile needs it too.
    compare: [ML.value.schX + ML.value.sch + 6, 22],
  },
  // The same door as the large form's: the box's left edge, at the row the
  // arrow from the latents ends on.
  'diffusion.decoder': { latent: [92, 52] },
  'transformer.prompt': { provider: [118, 58] },
  'transformer.vectors': { languages: [196, 37] },
  'transformer.block': { writeback: [120, 54], learned: [196, 60] },
  'transformer.sampling': { chance: [99, 62] },
  'crossings.i2t': { edge: [81, 53] },
  'crossings.t2a': { toMusic: [136, 32], toVoice: [136, 70] },
  'crossings.i2a': { toSound: [124, 40], guide: [92, 72] },
  // The whole chain, so the top left corner of the whole drawing — the same
  // place the large form puts it.
  'crossings.chain': { whole: [16, 30] },
}))

// Fixed, not random: a drawing that reshuffles on every render is a different
// drawing every time it is opened. The first two are the two pieces of the word
// on the left, so the picture says they have places of their own.

// ---------------------------------------------------------------------------
// Layout, per station, from the measurements.
// ---------------------------------------------------------------------------

interface Layout {
  [key: string]: any
  /** How far right this drawing reaches, so the group can be fitted. */
  extent: number
}

const L = computed<Layout>(() => {
  switch (props.id) {
    case 'diffusion.prompt': {
      const langX = 40
      const langFieldW = Math.max(
        w('stack0a', 260), w('stack0b', 260), w('stack1a', 260), w('stack1b', 260),
        w('stack2a', 260), w('stack2b', 260),
      ) + 24
      const imgX = langX + langFieldW + 12 + GAP
      const enW = Math.max(
        w('enBox', 90), w('enSample', 120), w('adaptBox', 140), w('adaptSample', 150),
      ) + 28
      const enX = imgX + 44 + GAP
      return {
        langX, imgX, enX, enW, langFieldW,
        // On the stacked language fields, not the corner of the German prompt
        // that used to stand here on its own: the dot belongs where the
        // languages actually differ from each other, and that field is gone
        // now — replaced by the stack itself.
        anchor: { language: [langX, 20] },
        extent: Math.max(
          enX + enW + 24,
          40 + w('platformNote', 780),
          40 + w('langNote', 800),
          40 + w('exploreNote', 700),
        ),
      }
    }
    case 'diffusion.encoder': {
      const promptW = Math.max(w('srcA', 200), w('srcB', 200)) + 24
      const promptY = 106
      const zoneH = 208
      const readX = 20 + promptW + GAP
      const joinX = readX + ENC_W + 60
      const cellX = joinX + 60
      const vecNumX = Math.max(w('vecTok0', 20), w('vecTok1', 20), w('vecTok2', 20)) + 14
      const vecRowW = POOLED_NUMS.length * 24
      return {
        readX, joinX, cellX, vecNumX, promptW, promptY, zoneH,
        anchor: {
          // The middle box's own corner, not its middle: the middle is a token
          // chip now, and a ring sitting on a token reads as a mark on that
          // token instead of on the encoders.
          readers: [readX + ENC_W, 102],
          mix: [joinX, 128],
          conditioning: [cellX + vecNumX + vecRowW + 20, 99],
        },
        extent: Math.max(
          cellX + vecNumX + vecRowW + 20,
          cellX + w('pooled', 200),
          20 + w('readersA', 660),
          20 + w('readersB', 680),
          cellX + w('list', 250),
        ),
      }
    }
    case 'diffusion.loop': {
      const dW = Math.max(w('denoiser', 70), w('dSub0', 130), w('dSub1', 120)) + PAD * 2
      const scW = Math.max(w('scheduler', 70), w('scSub0', 125), w('scSub1', 100)) + PAD * 2
      const pillW = w('repeat', 210) + 26
      // The embedding column stands where the zone used to start.
      const zone = 14 + 108 + GAP
      const s1 = zone + 24
      const d = s1 + SQ + GAP
      const sc = d + dW + GAP
      const s2 = sc + scW + GAP
      const zoneW = s2 + SQ + 24 - zone
      const tail = zone + zoneW + GAP + 8
      const inner = s2 + SQ / 2 - (s1 + SQ / 2)
      return {
        dW, scW, pillW, zone, zoneW, s1, d, sc, s2, tail,
        pill: s1 + SQ / 2 + (inner - pillW) / 2,
        anchor: {
          denoiser: [d + dW - 22, 48],
          state: [s2 + SQ - 20, 68],
          // Outside the dashed edge, at its far corner: what reaches in here
          // is not a place IN the loop but a claim about the whole thing — a
          // marker on the box itself, not on one of the things inside it.
          compare: [zone + zoneW + 8, 20],
        },
        extent: tail + Math.max(
          w('tail0', 90), w('tail1', 90), w('tail2', 90), w('tail3', 90),
        ),
      }
    }
    case 'diffusion.decoder': {
      const vaeW = Math.max(w('vaeLine1', 50), w('vaeLine2', 200)) + 28
      const decX = 60 + 122 + 34 + GAP
      const outX = decX + vaeW + GAP + 22
      return {
        vaeW, decX, outX,
        // On the box's own left edge, at the row the arrow comes in on: what
        // Mean Images works on is what is standing at that door, and a marker
        // sits ON what it marks.
        anchor: { latent: [decX, 128] },
        extent: Math.max(
          outX + 44 + Math.max(w('toImage', 60), w('toSound', 60), w('toVideo', 60), w('to3D', 40)),
          60 + w('from', 300),
          60 + w('explain0', 300),
          60 + w('explain1', 300),
        ),
      }
    }
    case 'transformer.prompt': {
      const fw = Math.max(w('pA', 240), w('pB', 240), w('sA', 200), w('sB', 200)) + 24
      const joinX = 20 + fw + 26
      const zoneX = joinX + 30
      const txtW = Math.max(w('a0', 110), w('a1', 150), w('a2', 100), w('a3', 150)) + 24
      const chkW = Math.max(w('check', 60), w('checkA', 130), w('checkB', 120)) + 32
      const chkX = zoneX + 40 + txtW
      const zoneW = 18 + txtW + 22 + chkW + 46
      const tailX = zoneX + zoneW + 14
      return {
        fw, joinX, zoneX, txtW, chkW, chkX, zoneW, tailX,
        anchor: { provider: [20 + fw + 10, 122] },
        extent: Math.max(
          tailX + Math.max(w('passA', 90), w('passB', 120), w('stopped', 70)),
          40 + Math.max(w('note0', 600), w('note1', 600), w('note2', 600), w('note3', 600)),
          40 + w('source', 400),
          20 + fw / 2 + Math.max(w('you', 140), w('provider', 240)) / 2,
        ),
      }
    }
    case 'transformer.vectors': {
      // Every chip is as wide as its own word; a gap is only as wide as its
      // dots and the places they stand for. The one control chip and the
      // one-word group remember where they sit, because their labels hang
      // under the row, centred on them.
      const tcX: number[] = []
      const tcW: number[] = []
      let x = 20
      let ctrlX = 0
      let fourL = 0
      let fourR = 0
      TCHIPS.value.forEach((c, i) => {
        const wd = c.gap
          ? Math.max(w(`tc${i}`, 12), w(`tp${i}`, 12))
          : Math.max(w(`tc${i}`, 16) + 12, w(`tp${i}`, 12))
        tcX.push(x)
        tcW.push(wd)
        if (c.ctrl) ctrlX = x + wd / 2
        if (c.four) {
          if (!fourL) fourL = x
          fourR = x + wd
        }
        x += wd + 6
      })
      const fourX = (fourL + fourR) / 2
      // The vocabulary fact stands after the caption of the place numbers, on
      // the same line, and is free to run past the chips: it feeds the column
      // width like everything else in the strand.
      const vocX = 20 + w('posn', 150) + 24

      // The rows of numbers, inside the dark area, and the band that repeats
      // the first of them.
      let erChipW = 30
      EROWS.value.forEach((_, i) => { erChipW = Math.max(erChipW, w(`et${i}`, 30) + 14) })
      const erX = 26 + erChipW + 8
      let rowsEnd = erX
      EROWS.value.forEach((r, i) => {
        rowsEnd = Math.max(rowsEnd, erX + r.vals.length * 42 + 8 + w(`em${i}`, 90))
      })
      // Der Exkurs steht NEBEN der Zerlegung, nicht neben dem Embedding: die
      // Spalte, die ihn traegt, wird allein von der Zerlegung geschoben. Das
      // Embedding beginnt unter ihm und hat darum die ganze Breite - anders
      // waere fuer 640 Felder in einer Zeile kein Platz.
      const colW = Math.max(20 + w('cutl', 460), x - 6, vocX + w('voc', 240))
      const cx = colW + 28

      let nameW = 24
      LANGS.value.forEach((_, i) => { nameW = Math.max(nameW, w(`lg${i}`, 46)) })
      const barMax = Math.max(0, ...LANGS.value.map(g => g.n * 2.4))
      const noteX = cx + nameW + 6 + barMax + 34
      let noteW = 0
      LANGNOTE.value.forEach((_, i) => { noteW = Math.max(noteW, w(`ln${i}`, 220)) })
      // The rule ends where the excursus does — at the bars, or lower in a
      // language whose lines beside them run past the chart.
      const ruleY2 = Math.max(45 + LANGS.value.length * 11 + 2, 54 + LANGNOTE.value.length * 12)

      // Das Embedding faengt unter dem Exkurs an - das ist der Preis dafuer,
      // dass es die ganze Breite bekommt, und die Hoehe dafuer ist da, seit
      // der viewBox nicht mehr flacher ist als die Flaeche, in der er liegt.
      const yEmb = Math.max(101, ruleY2 - 3)
      // Beschriftung und Farbleiste stehen rechts neben den Zahlenreihen.
      const legX = rowsEnd + 40
      const yKey = yEmb + 49 + VECNOTE.value.length * 12 + 2
      const keyX = legX + w('vs0', 44) + 6
      const legEnd = Math.max(
        keyX + 96 + 6 + w('vs1', 44),
        legX + Math.max(0, ...VECNOTE.value.map((_, i) => w(`vn${i}`, 200))),
      )
      // Unter der letzten Zahlenreihe und unter der Farbleiste.
      const yBand = Math.max(yEmb + 39 + EROWS.value.length * 15 + 6, yKey + 14)
      const bandEnd = 26 + 640 * VW
      const frameW = Math.max(bandEnd, legEnd) + 12 - 14
      const frameH = yBand + 4 * VH + 6 - (yEmb + 29)
      const closeY = yEmb + 29 + frameH + 14
      // Der Vermerk steht rechtsbuendig an der rechten Kante der Karte, neben
      // dem Schlussabsatz. Solange die Ecke frei ist, kostet er nichts; wo eine
      // Sprache den Schlussabsatz bis dorthin schreibt, weicht die Karte in die
      // Breite aus, statt die beiden uebereinander zu setzen.
      const mdW = Math.max(0, ...MODELNOTE.value.map((_, i) => w(`md${i}`, 150)))
      const closeMax = Math.max(400, ...VCLOSE.value.map((_, i) => w(`vc${i}`, 400)))
      const ext = Math.max(
        20 + w('sent', 500),
        cx + Math.max(w('lgh', 340), nameW + 6 + barMax + 26),
        noteX + noteW,
        20 + w('embl', 400),
        14 + frameW,
        20 + closeMax + (mdW ? 16 + mdW : 0),
      )
      return {
        tcX, tcW, ctrlX, fourX, cx, nameW, noteX, ruleY2, vocX,
        erChipW, erX, frameW, frameH, closeY, yEmb, yBand, legX, yKey, keyX,
        mdX: ext,
        // unten buendig mit der letzten Zeile des Schlussabsatzes
        mdY: closeY + (VCLOSE.value.length - 1) * 12 - (MODELNOTE.value.length - 1) * 10,
        // Auf der Linie, die den Exkurs abtrennt, auf Höhe seiner Überschrift:
        // der Ring reicht bis 6 Einheiten vor den Text und deckt nichts zu.
        anchor: { languages: [cx - 14, 37] },
        extent: ext,
      }
    }

    case 'transformer.block': {
      const bcX: number[] = []
      const bcW: number[] = []
      let x = 28
      BCHIPS.value.forEach((c, i) => {
        const wd = c.gap ? w(`bc${i}`, 12) : w(`bc${i}`, 16) + 12
        bcX.push(x)
        bcW.push(wd)
        x += wd + 6
      })
      const mid = (i: number) => (bcX[i] ?? 0) + (bcW[i] ?? 0) / 2
      // The longer the span, the deeper the arc hangs; each label stands at
      // its own arc's depth, under the chip that asks the question.
      const arcs = BARCS.value.map(a => ({
        x1: mid(a.from),
        x2: mid(a.to),
        depth: 24 + Math.abs(mid(a.from) - mid(a.to)) * 0.14,
        width: a.width,
        label: a.label,
      }))
      const maxDepth = Math.max(24, ...arcs.map(a => a.depth))
      const attY = 75 + maxDepth + 26
      const rowMid = attY + 40
      const capY = rowMid + 45
      const frameH = capY + 14 - 46
      const closeY = 46 + frameH + 22
      const brChipW = w('brt', 30) + 14
      const brX = 28 + brChipW + 8
      const brEnd = brX + BROW.value.vals.length * 42 + 8 + w('brm', 90)
      const stack = Math.max(56, w('cap1', 130) - 26)
      // The captions under the walk are wider than their elements; each next
      // element must clear the previous caption, not just the previous shape.
      const cap0C = (28 + brEnd) / 2
      const stackX = Math.max(brEnd + 34, cap0C + w('cap0', 160) / 2 + 18 + w('cap1', 130) / 2 - 13 - stack / 2)
      const stackEnd = stackX + 27 + stack
      const resW = w('res', 50) + 22
      const cap1C = stackX + 13 + stack / 2
      const resX = Math.max(stackEnd + 34, cap1C + w('cap1', 130) / 2 + 18 + w('cap2', 160) / 2 - resW / 2)
      // The frame must hold the widest of: the chip row, the walk with its
      // last caption, the arc labels, and its own title line.
      const frameW = Math.max(
        x + 8,
        resX + resW / 2 + w('cap2', 160) / 2 + 16,
        ...arcs.map((a, i) => a.x1 + w(`bl${i}`, 80) / 2 + 12),
        28 + w('ac', 300),
        28 + w('fl', 0),
      ) - 14
      const bankX = 14 + frameW + 30
      let bkChipW = 30
      BANKR.value.forEach((_, i) => { bkChipW = Math.max(bkChipW, w(`bkt${i}`, 30) + 14) })
      const bankW = 24 + Math.max(
        w('bkh', 90), w('bk1', 220), w('bk2', 220),
        bkChipW + 8 + 3 * 42 + 8 + 12,
        ...BBANK.value.map((_, i) => w(`bb${i}`, 200)),
      )
      const bankH = 100 + BBANK.value.length * 12
      const deep = arcs.reduce((p, a) => (a.depth > p.depth ? a : p), arcs[0] ?? { x1: 200, depth: 40 })
      return {
        bcX, bcW, arcs, attY, rowMid, capY, frameH, frameW, closeY,
        brChipW, brX, brEnd, stackX, stack, stackEnd, resX, resW, bankX, bankW, bankH, bkChipW,
        // Unter dem Bank-Kasten, an dessen rechter Kante: der Schlussabsatz
        // dieser Karte reicht weiter nach rechts als der der Karte davor, und
        // diese Karte wird nach ihrer Breite skaliert - neben dem Schlussabsatz
        // wuerde der Vermerk sie verbreitern und damit alles darauf verkleinern.
        mdX: bankX + bankW,
        mdY: 46 + bankH + 22,
        anchor: {
          writeback: [stackX + 13 + stack / 2, rowMid],
          // On the deep arc's shoulder, not at its lowest point: the apex is
          // where the labels live, and a ring on a label swallows a word.
          learned: [(deep?.x1 ?? 200) - 34, 75 + (deep?.depth ?? 40) * 0.5],
        },
        extent: Math.max(
          bankX + bankW,
          14 + Math.max(400, ...BCLOSE.value.map((_, i) => w(`bcl${i}`, 400))),
        ),
      }
    }

    case 'transformer.sampling': {
      // Every bar takes the width of its own words — token below, value above —
      // so a long candidate in another language widens its slot instead of
      // colliding with the next one.
      const ctxEnd = 20 + w('ctx', 470) + 10
      const slotW = Math.max(w('c0', 50) + 18, 56)
      const slot = CANDS.value.map((_, i) => Math.max(w(`c${i}`, 40), w(`v${i}`, 26)) + 20)
      let bx = 20
      const barX = slot.map((s) => { const x = bx; bx += s; return x })
      const barsEnd = bx
      const tempX = barsEnd + 48
      const loopX = ctxEnd + slotW + 26
      const endX = loopX + 34 + w('lp2', 250) + 8
      const endW = w('etk', 70) + 12
      const mdW = Math.max(0, ...MODELNOTE.value.map((_, i) => w(`md${i}`, 150)))
      const noteMax = Math.max(w('n0', 620), w('n1', 620), w('n2', 620), w('n3', 620))
      const mdY = 222 + (SNOTE.value.length - 1) * 13 - (MODELNOTE.value.length - 1) * 10
      // Freihalten muss der Vermerk nur die Zeilen, die auf seiner Hoehe
      // stehen. Der ganze Absatz waere hier das falsche Mass: seine erste Zeile
      // ist die laengste und steht zwei Zeilen ueber ihm.
      const mdGuard = Math.max(
        0,
        ...SNOTE.value.map((_, i) => (222 + i * 13 >= mdY - 8 ? w(`n${i}`, 620) : 0)),
      )
      // `extent` haelt rechts sechzehn Einheiten Luft hinter dem Steuerzeichen;
      // die rechte Kante des Gezeichneten liegt davor. Der Vermerk richtet sich
      // an ihr aus, nicht an der Luft - sonst schoebe er die Karte um genau
      // diese sechzehn Einheiten breiter und damit alles darauf kleiner.
      const content = Math.max(
        endX + endW,
        loopX + 34 + w('lp1', 260),
        tempX + Math.max(183, w('sharp', 190)),
        20 + noteMax,
        20 + mdGuard + (mdW ? 16 + mdW : 0),
      )
      const ext = Math.max(content, endX + endW + 16)
      return {
        ctxEnd, slotW, slot, barX, barsEnd, tempX, loopX, endX, endW,
        mdX: content,
        mdY,
        anchor: { chance: [(barX[1] ?? 100) + (slot[1] ?? 60) / 2, 120] },
        extent: ext,
      }
    }
    case 'crossings.i2t':
      return {
        anchor: { edge: [244, 105] },
        // The third column's right edge, or the line under the row where that
        // runs wider — which it does in the languages that need more words.
        extent: Math.max(740, 282 + w('models', 400)),
      }
    case 'crossings.t2a':
      return {
        anchor: { toMusic: [330, 62], toVoice: [330, 150] },
        extent: 470 + Math.max(w('music', 300), w('voice', 300)),
      }
    case 'crossings.i2a':
      return {
        anchor: { toSound: [246, 58], guide: [246, 150] },
        extent: 388 + Math.max(w('make', 220), w('pull', 460)),
      }
    case 'crossings.chain': {
      const stepW = Math.max(...STEPS.map(st => Math.max(w(`${st}a`, 80), w(`${st}b`, 0)))) + PAD * 2
      const endW = Math.max(...ENDS.map(m => w(m, 70))) + PAD * 2
      const step = STEPS.map((_, i) => 20 + i * (stepW + 16))
      const last = 20 + 4 * (stepW + 16) + stepW / 2
      const endsTotal = 4 * endW + 3 * 12
      // Hangs under the last step, but not off the edge: a fan that leaves the
      // canvas makes the whole drawing shrink to fetch it back, and the four
      // endings belong to the last step whether or not they sit exactly beneath
      // its middle.
      const endLeft = Math.max(20, Math.min(last - endsTotal / 2, 910 - endsTotal))
      const end = ENDS.map((_, i) => endLeft + i * (endW + 12))
      return {
        stepW, endW, step, end, last,
        anchor: { whole: [16, 18] },
        extent: Math.max(
          20 + 5 * stepW + 4 * 16,
          (end[3] ?? 0) + endW,
          20 + w('machines', 500),
          (step[2] ?? 0) + w('s3note', 300),
        ),
      }
    }
    default:
      return { anchor: {}, extent: 930 }
  }
})

/**
 * The whole drawing, scaled to the room there is.
 *
 * The measurements make every box fit its own words; this makes the ROW fit the
 * canvas when the words together are longer than 930 units — German runs about
 * a fifth longer than English, and a drawing that clips is worse than one drawn
 * a little smaller. Scaled around the middle so it does not drift upward.
 */
const fit = computed(() => {
  const b = box.value
  const v = VB.value
  if (!b) {
    // First frame, nothing measured yet. Only the large form has an estimate to
    // work from: `L.extent` is that layout's own width, and using it on a canvas
    // a third as wide would draw every small station at a third size for as long
    // as the measurement takes.
    if (props.mini) return ''
    const e = Math.min(1, v.iw / Math.max(1, L.value.extent))
    return e >= 1 ? '' : `translate(10,0) scale(${e.toFixed(4)})`
  }
  // Allowed to grow, not only to shrink: a drawing whose boxes shrank to their
  // words leaves room, and a caption at 11 units of a 930-wide viewBox comes out
  // at 10 px next to the 13 px of the page around it. Capped, so a sparse
  // drawing does not blow up to fill a space it has nothing to put in.
  const s = Math.min(v.grow, v.iw / b.w, v.ih / b.h)
  // Centred on WHAT IS DRAWN, not on the nominal 930 x 260. A drawing whose
  // boxes shrank to their words is narrower than the box it sits in, and one
  // placed by the nominal width would hang in the left corner — or, scaled,
  // run out over the right edge, which is how the far right label was lost.
  const dx = (v.w - b.w * s) / 2 - b.x * s
  const dy = (v.h - b.h * s) / 2 - b.y * s
  return `translate(${dx.toFixed(2)},${dy.toFixed(2)}) scale(${s.toFixed(4)})`
})

/** The named places turned into points, once the layout knows where they are. */
const placed = computed(() => {
  const from = props.mini ? (MINI_AT.value[props.id] ?? {}) : (L.value.anchor ?? {})
  return props.marks
    .map(m => ({ hosts: m.hosts, label: m.label, pt: from[m.at] as [number, number] | undefined }))
    // A marker with no place is dropped rather than drawn at the origin. The
    // small form leaves out parts the large one draws, so a place can be absent
    // there on purpose — and a dot in the top left corner says nothing.
    .filter((m): m is { hosts: string[]; label: string; pt: [number, number] } => !!m.pt)
})
</script>

<style scoped>
/* The layout runs left to right: every x in `L` is written on the assumption
   that `text-anchor="start"` puts the label to the RIGHT of it. SVG does not
   promise that. `start` and `end` follow the `direction` property, so under the
   document's `dir="rtl"` — Arabic and Hebrew — every `start` label ran leftwards
   off the canvas and every `end` label ran rightwards off it. `getBBox` then
   reported a group up to twice the width of the drawing, and `fit` shrank the
   whole station to match. Measured 2026-08-29 in ar, against the same page with
   `direction` pinned:

     Tokenisierung und Embedding  0.5675 -> 0.9764
     Attention                    0.5091 -> 0.9566
     Sampling                     0.6245 -> 1.1886
     Prompt (Diffusion)           0.8596 -> 1.25

   All twelve stations were affected, not only the transformer's four.

   `direction: ltr` on its own would be the wrong fix. It also sets the
   PARAGRAPH direction of the content, and an Arabic or Hebrew sentence then
   comes out with its full stop at the wrong end of the line (measured, both
   scripts). `unicode-bidi: plaintext` gives every `<text>` its own paragraph
   direction from its first strong character: the anchoring stays left-to-right,
   which is what the geometry needs, and the sentence inside still runs right to
   left, punctuation included. For a Latin caption the first strong character is
   Latin, so nothing changes there.

   This does NOT mirror the drawing — the boxes still run left to right and the
   arrows still point right. Whether a station should be mirrored for a reader
   of Arabic or Hebrew is a design question and a separate one. */
.st-svg { display: block; width: 100%; height: 100%; direction: ltr; }
.st-svg text { unicode-bidi: plaintext; }
/* In viewBox units, and the viewBox is width-bound at about 0.9 px per unit —
   so 13 here is the 12 px that stands next to the page's 13. */
.t-lg { fill: #e2e8f0; font-size: 19px; }
.t-md { fill: #e2e8f0; font-size: 15px; }
/* Captions and the labels on the outputs at three quarters of what they were:
   the sentences under the drawings grew, and at 13 px the loop's ran into its
   own boxes. The names of the boxes and the written line keep their size. */
.t-sub { fill: #bcc7d5; font-size: 10px; }
.t-dim { fill: #a7b4c4; font-size: 9px; }
/* A footnote in a corner: one step under the closing paragraph, and a shade
   quieter, because it says what the card was measured on, not what it shows. */
.t-fine { fill: #93a1b2; font-size: 8px; }
.t-tok { fill: #dde4ee; font-size: 9px; }
/* The chat template's own marks. Monospaced because they are literal text the
   model is handed, not a caption about it. */
.t-val {
  font-size: 9.5px;
  fill: #cbd5e1;
  font-family: ui-monospace, Menlo, monospace;
}
.t-mono { fill: #dde4ee; font-size: 9px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.t-mono-dim { fill: #a7b4c4; font-size: 9px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
/* A source under a drawing is a link, and reads as one. */
.t-link { fill: #c9b6ff; font-size: 9px; text-decoration: underline; cursor: pointer; }
.t-link:hover { fill: #ddd0ff; }
/* Every technical term on this page in one colour — a lightened version of the
   violet the written field is drawn with, so it reads on the purple card and on
   the blue one, and is not the green the instrument markers own. */
.t-term { fill: #c9b6ff; }
/* transparent, not none: `none` is not a fill a pointer can land on. */
.fs-hit { fill: transparent; }
.fs-mark { cursor: pointer; outline: none; }
.fs-ring {
  fill: none;
  stroke: #4CAF50;
  stroke-width: 1.4;
  opacity: 0.85;
  transition: stroke 0.12s, opacity 0.12s;
}
.fs-dot { fill: #4CAF50; transition: fill 0.12s; }
.fs-mark:hover .fs-ring,
.fs-mark:focus-visible .fs-ring { stroke: #8fe093; opacity: 1; }
.fs-mark:hover .fs-dot,
.fs-mark:focus-visible .fs-dot { fill: #8fe093; }
/* The focus has to show on a shape that has no box: a heavier ring rather than
   an `outline`, which browsers draw around the whole `<g>`. */
.fs-mark:focus-visible .fs-ring { stroke-width: 2.4; }
</style>
