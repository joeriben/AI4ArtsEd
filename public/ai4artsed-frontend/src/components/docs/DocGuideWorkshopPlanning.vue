<template>
  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Workshop-Planung: Gemeinsam Modelle wählen' : 'Workshop Planning: Selecting Models Together' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'In der Workshop-Planung entscheidet die Gruppe gemeinsam, welche Modelle und Konfigurationen für einen Workshop verwendet werden sollen. Die Plattform hilft dabei, technische Anforderungen und pädagogische Ziele in Einklang zu bringen.'
      : 'In workshop planning, the group collectively decides which models and configurations to use for a workshop. The platform helps balance technical requirements with pedagogical goals.' }}</p>
  </section>

  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Wie funktioniert es?' : 'How does it work?' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'Träshy, der KI-Assistent der Plattform, begleitet den Planungsprozess. Er kennt die verfügbaren Modelle, ihre Stärken und Grenzen, und kann Empfehlungen geben, die auf die konkrete Workshop-Situation zugeschnitten sind — Gruppengröße, verfügbare Hardware, thematischer Fokus.'
      : 'Träshy, the platform\'s AI assistant, guides the planning process. It knows the available models, their strengths and limitations, and can provide recommendations tailored to the specific workshop situation — group size, available hardware, thematic focus.' }}</p>
  </section>

  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Für wen ist das gedacht?' : 'Who is this for?' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'Workshop-Leitende, Lehrende und alle, die einen Workshop mit der Plattform vorbereiten. Die Planung kann alleine oder gemeinsam mit der Gruppe durchgeführt werden.'
      : 'Workshop facilitators, educators, and anyone preparing a workshop with the platform. Planning can be done alone or together with the group.' }}</p>
  </section>
</template>

<script setup lang="ts">
defineProps<{ currentLanguage: string }>()
</script>
