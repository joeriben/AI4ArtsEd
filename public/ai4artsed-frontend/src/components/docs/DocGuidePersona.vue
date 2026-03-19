<template>
  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'KI-Persona: Dialogische Bildgenerierung' : 'AI Persona: Dialogic Image Generation' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'Die KI-Persona ist kein Werkzeug, das Befehle ausführt. Sie ist ein widerständiger Gesprächspartner, der selbst entscheidet, was generiert wird. Du beschreibst, was du dir vorstellst — die Persona interpretiert, hinterfragt, ergänzt und trifft eigene Entscheidungen.'
      : 'The AI Persona is not a tool that executes commands. It is a resistant conversation partner that decides for itself what to generate. You describe what you envision — the persona interprets, questions, adds, and makes its own decisions.' }}</p>
  </section>

  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Wie funktioniert es?' : 'How does it work?' }}</h3>
    <div class="step-list">
      <div class="step-item">
        <span class="step-number">1</span>
        <div>
          <strong>{{ currentLanguage === 'de' ? 'Dialog starten' : 'Start a dialog' }}</strong>
          <p>{{ currentLanguage === 'de'
            ? 'Beschreibe der Persona, was du dir vorstellst. Die Persona antwortet, stellt Rückfragen und schlägt ihre eigene Interpretation vor.'
            : 'Describe to the persona what you have in mind. The persona responds, asks follow-up questions, and proposes its own interpretation.' }}</p>
        </div>
      </div>
      <div class="step-item">
        <span class="step-number">2</span>
        <div>
          <strong>{{ currentLanguage === 'de' ? 'Verhandeln' : 'Negotiate' }}</strong>
          <p>{{ currentLanguage === 'de'
            ? 'Du kannst widersprechen, umlenken oder dich von der Interpretation der Persona überraschen lassen. Der Dialog ist ein Aushandlungsprozess.'
            : 'You can disagree, redirect, or let yourself be surprised by the persona\'s interpretation. The dialog is a process of negotiation.' }}</p>
        </div>
      </div>
      <div class="step-item">
        <span class="step-number">3</span>
        <div>
          <strong>{{ currentLanguage === 'de' ? 'Generierung' : 'Generation' }}</strong>
          <p>{{ currentLanguage === 'de'
            ? 'Wenn die Persona entscheidet, dass der Dialog reif genug ist, generiert sie eigenständig ein Bild. Du bestimmst nicht den exakten Prompt — die Persona tut es.'
            : 'When the persona decides the dialog is ripe enough, it autonomously generates an image. You do not determine the exact prompt — the persona does.' }}</p>
        </div>
      </div>
    </div>
  </section>

  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Warum Widerständigkeit?' : 'Why resistance?' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'Konventionelle KI-Bildgenerierung folgt dem Muster: "Ich sage, was ich will, die Maschine liefert." Die Persona bricht dieses Muster bewusst auf. Sie macht sichtbar, dass Bildgenerierung immer Interpretation ist — und dass der interessanteste kreative Raum dort entsteht, wo man nicht die volle Kontrolle hat.'
      : 'Conventional AI image generation follows the pattern: "I say what I want, the machine delivers." The persona deliberately breaks this pattern. It makes visible that image generation is always interpretation — and that the most interesting creative space emerges where one does not have full control.' }}</p>
  </section>
</template>

<script setup lang="ts">
defineProps<{ currentLanguage: string }>()
</script>

<style scoped>
.step-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 0.75rem;
}

.step-item {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}

.step-number {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(76, 175, 80, 0.15);
  color: #4CAF50;
  font-weight: 700;
  font-size: 0.85rem;
}

.step-item p {
  margin: 0.25rem 0 0 0;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.95rem;
  line-height: 1.5;
}
</style>
