<template>
  <div class="kickin">
    <div class="header">
      <h1>Delayed Kick-In — Band Isolation</h1>
      <div class="meta">
        prompt_early: <b>ocean</b> → prompt_full: <b>ocean and a ship</b> · seed 123456789 · 25 steps · CFG 5.5
      </div>
      <div class="legend">
        Main run conditioned on <b>early</b>; hook at band entry swaps encoder_hidden_states to
        <b>traj_full</b> from kickin_step onwards. Band is the only path the new prompt component
        enters through.<br>
        k=0: voller Prompt durchgehend &nbsp;·&nbsp; k=25: nie umgeschaltet (Ozean-Referenz).
      </div>
    </div>

    <section v-for="band in bands" :key="band.id" class="band">
      <h2>{{ band.label }}</h2>
      <div class="grid">
        <div v-for="k in kickinSteps" :key="k" class="cell">
          <img :src="`/api/dev/kickin/${band.id}/kickin_${pad2(k)}.png`" :alt="`k=${k}`">
          <div class="lab">{{ kLabel(k) }}</div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
const bands = [
  { id: 'flach',  label: 'flach (Block 0)' },
  { id: 'mittel', label: 'mittel (Block 10)' },
  { id: 'tief',   label: 'tief (Block 23)' },
]
const kickinSteps = [0, 1, 4, 7, 10, 13, 16, 19, 22, 25]

const pad2 = (n: number) => String(n).padStart(2, '0')
const kLabel = (k: number) => {
  if (k === 0) return 'k=0 (full)'
  if (k >= 25) return 'k=25 (early)'
  return `k=${k}`
}
</script>

<style scoped>
.kickin {
  background: var(--bg-base);
  color: #ddd;
  min-height: 100%;
  padding: 24px;
  font-family: var(--font-sans);
}
.header h1 {
  font-size: 22px;
  margin: 0 0 6px 0;
}
.meta {
  color: #888;
  font-size: 13px;
  margin-bottom: 12px;
}
.legend {
  color: #888;
  font-size: 12px;
  line-height: 1.5;
  margin-bottom: 16px;
  max-width: 1100px;
}
.band {
  margin-top: 28px;
}
.band h2 {
  font-size: 17px;
  color: #9cf;
  margin: 0 0 8px 0;
}
.grid {
  display: grid;
  grid-template-columns: repeat(10, minmax(0, 1fr));
  gap: 6px;
  max-width: 1900px;
}
.cell {
  background: var(--surface-1);
  border-radius: 4px;
  padding: 4px;
  text-align: center;
}
.cell img {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 2px;
}
.lab {
  font-size: 11px;
  color: #aaa;
  padding-top: 4px;
}
@media (max-width: 1200px) {
  .grid { grid-template-columns: repeat(5, minmax(0, 1fr)); }
}
@media (max-width: 600px) {
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
