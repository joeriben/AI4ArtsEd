<template>
  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Vergleichsmodi: Dieselbe Idee unter verschiedenen Bedingungen' : 'Comparison Modes: The Same Idea Under Different Conditions' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'Generiere dasselbe Bild unter kontrollierten Variationen — und sieh, was sich verändert. Der Vergleichsmodus isoliert einzelne Variablen (Sprache, Temperatur), damit Unterschiede sichtbar und analysierbar werden.'
      : 'Generate the same image under controlled variations — and see what changes. Comparison mode isolates individual variables (language, temperature) so that differences become visible and analyzable.' }}</p>
  </section>

  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Sprachvergleich' : 'Language Comparison' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'Derselbe Prompt in verschiedenen Sprachen — mit identischem Seed, damit die Unterschiede allein aus der Sprache resultieren. Bildgenerierungsmodelle reagieren unterschiedlich auf Sprachen, weil ihre Trainingsdaten kulturell und sprachlich nicht gleichmäßig verteilt sind.'
      : 'The same prompt in different languages — with identical seed, so differences result solely from the language. Image generation models respond differently to languages because their training data is not evenly distributed across cultures and languages.' }}</p>
    <div class="insight-list">
      <div class="insight-item">
        <strong>{{ currentLanguage === 'de' ? 'Sprachliche Biases' : 'Linguistic biases' }}</strong>
        <p>{{ currentLanguage === 'de'
          ? 'Englische Prompts erzeugen oft westlich geprägte Bilder. Derselbe Inhalt auf Koreanisch, Türkisch oder Arabisch kann völlig andere visuelle Welten öffnen.'
          : 'English prompts often produce Western-influenced images. The same content in Korean, Turkish, or Arabic can open entirely different visual worlds.' }}</p>
      </div>
      <div class="insight-item">
        <strong>{{ currentLanguage === 'de' ? 'Kulturelle Assoziationen' : 'Cultural associations' }}</strong>
        <p>{{ currentLanguage === 'de'
          ? 'Sprache trägt kulturelle Bedeutungsschichten. Ein Wort, das sich übersetzen lässt, transportiert in verschiedenen Sprachen verschiedene Assoziationen — und das Modell bildet diese Unterschiede ab.'
          : 'Language carries cultural layers of meaning. A word that can be translated carries different associations in different languages — and the model reflects these differences.' }}</p>
      </div>
    </div>
  </section>

  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Temperaturvergleich' : 'Temperature Comparison' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'Derselbe Prompt bei verschiedenen Temperatur-Einstellungen des Sprachmodells. Die Temperatur steuert, wie frei das LLM bei der Prompt-Interception interpretiert: niedrige Werte erzeugen vorhersagbarere, höhere Werte überraschendere Ergebnisse.'
      : 'The same prompt at different temperature settings of the language model. Temperature controls how freely the LLM interprets during prompt interception: lower values produce more predictable, higher values more surprising results.' }}</p>
    <div class="insight-list">
      <div class="insight-item">
        <strong>{{ currentLanguage === 'de' ? 'Kreativität sichtbar machen' : 'Making creativity visible' }}</strong>
        <p>{{ currentLanguage === 'de'
          ? 'Der Vergleich zeigt, wie stark die Interpretationsfreiheit des Modells das Endergebnis beeinflusst — und wo die Grenze zwischen produktiver Überraschung und Beliebigkeit liegt.'
          : 'The comparison shows how much the model\'s interpretive freedom influences the final result — and where the boundary between productive surprise and arbitrariness lies.' }}</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{ currentLanguage: string }>()
</script>

<style scoped>
.insight-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 0.75rem;
}

.insight-item {
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
  border-inline-start: 3px solid rgba(76, 175, 80, 0.3);
}

.insight-item strong {
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.95rem;
}

.insight-item p {
  margin: 0.25rem 0 0 0;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.9rem;
  line-height: 1.5;
}
</style>
