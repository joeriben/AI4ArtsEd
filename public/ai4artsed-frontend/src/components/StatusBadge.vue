<!--
  StatusBadge — the small upper-case state chip used across the Settings surface.

  Grown out of BackendStatusTab, which carried these four states as scoped CSS and
  was the only consumer until the vision capability check needed the same chip in
  SettingsView. Parametrised rather than copied (project rule 13).

  tone:
    available    green    reachable, configured, present, sees images
    caution      amber    present but not vouched for — the state between good
                          news and bad, added for the header policy chips, where
                          "we cannot confirm this" is its own answer
    unavailable  red      unreachable, missing, blind
    in-use       blue     busy right now
    idle         neutral  present but doing nothing — and the state for "not
                          measured yet", which is neither good news nor bad

  compact: the header variant. Same chip at roughly 60 % of the height, with
  type held at 9 px rather than scaled with it, because a proportionally shrunk
  11 px label lands at 7 px and stops being readable.

  flat: the chip inside something that already carries a frame. The border
  turns transparent rather than going away, so the box keeps its metrics and a
  flat chip still lines up with a framed one; the tint carries a little more
  weight to make up for the missing edge.

  load: a tone with no colour of its own. The caller sets --badge-load-fg and
  --badge-load-bg, for the one case where the state is a continuum rather than
  a set of names — what the card draws, between cool and hot.
-->
<template>
  <span :class="['status-badge', `status-${tone}`, { 'status-compact': compact, 'status-flat': flat }]"><slot /></span>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  tone: 'available' | 'caution' | 'unavailable' | 'in-use' | 'idle' | 'load'
  compact?: boolean
  flat?: boolean
}>(), { compact: false, flat: false })
</script>

<style scoped>
.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.status-compact {
  padding: 1px 5px;
  font-size: 9px;
  letter-spacing: 0.2px;
  line-height: 1.35;
  /* The header row is tight; a wrapped label would double the chip height and
     break the line the nav sits on. */
  white-space: nowrap;
}

.status-available {
  background: rgba(76, 175, 80, 0.14);
  color: #66bb6a;
  border: 1px solid #4CAF50;
}

.status-caution {
  background: rgba(255, 152, 0, 0.14);
  color: #ffb74d;
  border: 1px solid #ff9800;
}

.status-unavailable {
  background: rgba(229, 57, 53, 0.14);
  color: #ff7b72;
  border: 1px solid #ef5350;
}

.status-in-use {
  background: rgba(33, 150, 243, 0.14);
  color: #64b5f6;
  border: 1px solid #42a5f5;
}

.status-idle {
  background: var(--surface-2);
  color: #a0a0a0;
  border: 1px solid var(--surface-4);
}

/* No colour of its own: whoever reads the value passes the two. */
.status-load {
  background: var(--badge-load-bg, var(--surface-2));
  color: var(--badge-load-fg, #a0a0a0);
  border: 1px solid transparent;
}

/* Inside a frame of its own, the edge would be a second line around the same
   thing. It stays in the box model and only loses its colour. */
.status-flat {
  border-color: transparent;
}

.status-flat.status-available { background: rgba(76, 175, 80, 0.18); }
.status-flat.status-caution { background: rgba(255, 152, 0, 0.18); }
.status-flat.status-unavailable { background: rgba(229, 57, 53, 0.18); }
.status-flat.status-in-use { background: rgba(33, 150, 243, 0.18); }
</style>
