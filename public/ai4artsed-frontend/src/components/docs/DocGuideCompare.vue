<template>
  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Sprachvergleich: Dasselbe Bild in verschiedenen Sprachen' : 'Language Comparison: The Same Image in Different Languages' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'Generiere dasselbe Bild mit demselben Prompt in verschiedenen Sprachen — und sieh, was sich verändert. Bildgenerierungsmodelle reagieren unterschiedlich auf Prompts in verschiedenen Sprachen, weil ihre Trainingsdaten kulturell und sprachlich nicht gleichmäßig verteilt sind.'
      : 'Generate the same image with the same prompt in different languages — and see what changes. Image generation models respond differently to prompts in different languages because their training data is not evenly distributed across cultures and languages.' }}</p>
  </section>

  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Was wird sichtbar?' : 'What becomes visible?' }}</h3>
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
      <div class="insight-item">
        <strong>{{ currentLanguage === 'de' ? 'Trainingsdaten-Ungleichgewicht' : 'Training data imbalance' }}</strong>
        <p>{{ currentLanguage === 'de'
          ? 'Seltener vertretene Sprachen erzeugen oft generischere oder stereotypere Bilder. Das ist kein Fehler der Sprache, sondern ein Spiegel der Datenlage.'
          : 'Less represented languages often produce more generic or stereotypical images. This is not a fault of the language but a mirror of the data landscape.' }}</p>
      </div>
    </div>
  </section>

  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'So gehst du vor' : 'How to use it' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'Schreibe einen Prompt, wähle mehrere Sprachen aus, und starte die Generierung. Alle Varianten verwenden denselben Seed, damit die Unterschiede allein aus der Sprache resultieren. Die Ergebnisse werden nebeneinander angezeigt.'
      : 'Write a prompt, select multiple languages, and start generation. All variants use the same seed so that differences result solely from the language. Results are displayed side by side.' }}</p>
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
