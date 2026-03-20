<template>
  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Vergleichsmodi: Sichtbar machen, was die KI verbirgt' : 'Comparison Modes: Making Visible What the AI Conceals' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'Generative KI bringen immer etwas in zufallsgesteuerten Variationen hervor. Sie sind darauf trainiert, zu überzeugen. Sie zeigen uns Erzeugnisse auf Basis ihrer statistisch vorhandenen Daten, und indem sie uns immer etwas zeigen und niemals schweigen (und das auch gar nicht können), verbergen sie das, was sie nicht wissen, nicht kennen, was ihnen nicht eintrainiert wurde, sehr geschickt. Diese Lücken können wir am einfachsten über systematische Vergleiche zur Erscheinung bringen, und so die KIs auch von ihrer anderen Seite kennen und verstehen lernen.'
      : 'Generative AIs always produce something in randomized variations. They are trained to convince. They show us products based on their statistically available data, and by always showing us something and never remaining silent (which they cannot do anyway), they cleverly conceal what they do not know, what they are unfamiliar with, what was not trained into them. We can most easily bring these gaps to appearance through systematic comparisons — and thus learn to know and understand the AIs from their other side as well.' }}</p>
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
          ? 'Der Sprachvergleich ermöglicht die systematische Erkundung sprach- und kulturbezogener Ungleichbehandlung durch KI. Englische Prompts erzeugen oft amerikanisch-westlich geprägte Bilder. Derselbe Inhalt in anderen Sprachen zeigt, wie ungleich die Trainingsdaten verteilt sind — und wo der Bias des Modells liegt.'
          : 'The language comparison enables systematic exploration of language- and culture-related unequal treatment by AI. English prompts often produce American-Western influenced images. The same content in other languages reveals how unevenly training data is distributed — and where the model\'s bias lies.' }}</p>
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
    <h3>{{ currentLanguage === 'de' ? 'Modellvergleich' : 'Model Comparison' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'Verschiedene Modelle interpretieren denselben Prompt auf Basis desselben Rauschbilds — und erzeugen dennoch völlig unterschiedliche Ergebnisse. Der Modellvergleich macht sichtbar, dass das Modell selbst eine entscheidende Variable ist, nicht nur der Prompt.'
      : 'Different models interpret the same prompt based on the same noise image — yet produce completely different results. The model comparison makes visible that the model itself is a decisive variable, not just the prompt.' }}</p>
    <div class="insight-list">
      <div class="insight-item">
        <strong>{{ currentLanguage === 'de' ? 'Aktuelle Top-Modelle' : 'Current top models' }}</strong>
        <p>{{ currentLanguage === 'de'
          ? 'SD 3.5 Large, Flux 2, Gemini 3 Pro — drei aktuelle Modelle im direkten Vergleich.'
          : 'SD 3.5 Large, Flux 2, Gemini 3 Pro — three current models in direct comparison.' }}</p>
      </div>
      <div class="insight-item">
        <strong>{{ currentLanguage === 'de' ? 'Historischer Vergleich' : 'Historical comparison' }}</strong>
        <p>{{ currentLanguage === 'de'
          ? 'SD 1.5 (2022), SDXL (2023), SD 3.5 Large (2024) — drei Generationen. Wie hat sich die Bildgenerierung Jahr für Jahr verändert?'
          : 'SD 1.5 (2022), SDXL (2023), SD 3.5 Large (2024) — three generations. How has image generation changed year by year?' }}</p>
      </div>
    </div>
  </section>

  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Temperaturvergleich' : 'Temperature Comparison' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'Derselbe Text wird gleichzeitig an dasselbe Sprachmodell bei drei verschiedenen Temperatur-Einstellungen gesendet. Die Temperatur bestimmt, wie stark das Modell von den wahrscheinlichsten Wortfolgen abweicht: Bei niedriger Temperatur bleibt der Text nah am Erwartbaren, bei hoher Temperatur entstehen zunehmend überraschende, unvorhersehbare Formulierungen — bis hin zur Auflösung kohärenter Texte.'
      : 'The same text is sent simultaneously to the same language model at three different temperature settings. Temperature determines how much the model deviates from the most likely word sequences: at low temperature, the text stays close to the expected; at high temperature, increasingly surprising, unpredictable formulations emerge — up to the disintegration of coherent texts.' }}</p>
    <div class="insight-list">
      <div class="insight-item">
        <strong>{{ currentLanguage === 'de' ? 'Kontrolle und Kontrollverlust' : 'Control and loss of control' }}</strong>
        <p>{{ currentLanguage === 'de'
          ? 'Der Vergleich macht das Spektrum zwischen Kontrolle und Kontrollverlust sichtbar: Wo folgt das Modell noch unseren Erwartungen, wo beginnt es eigene Wege zu gehen, und wo zerfällt der Text in etwas, das wir nicht mehr steuern können?'
          : 'The comparison makes the spectrum between control and loss of control visible: where does the model still follow our expectations, where does it begin to go its own way, and where does the text disintegrate into something we can no longer steer?' }}</p>
      </div>
    </div>
  </section>

  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'KI-gestützte Auswertung' : 'AI-Assisted Analysis' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'Nach der Generierung kann die KI (Trashy) helfen, die Vergleichsergebnisse zu analysieren und zu interpretieren. Im Sprach- und Modellvergleich steht ein Chat-Panel zur Verfügung, in dem Trashy die generierten Bilder kommentiert, auf Unterschiede hinweist und Fragen stellen kann, die den Vergleich pädagogisch produktiv machen.'
      : 'After generation, the AI (Trashy) can help analyze and interpret the comparison results. In the language and model comparison, a chat panel is available where Trashy comments on the generated images, points out differences, and can ask questions that make the comparison pedagogically productive.' }}</p>
    <div class="insight-list">
      <div class="insight-item">
        <strong>{{ currentLanguage === 'de' ? 'Nicht nur sehen, sondern verstehen' : 'Not just seeing, but understanding' }}</strong>
        <p>{{ currentLanguage === 'de'
          ? 'Der Vergleich allein zeigt Unterschiede. Die KI-gestützte Auswertung hilft, diese Unterschiede einzuordnen: Warum sieht das Bild auf Koreanisch anders aus als auf Englisch? Was verrät der historische Modellvergleich über die Entwicklung der Trainingsdaten?'
          : 'The comparison alone shows differences. AI-assisted analysis helps to contextualize these differences: Why does the image look different in Korean than in English? What does the historical model comparison reveal about the evolution of training data?' }}</p>
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
