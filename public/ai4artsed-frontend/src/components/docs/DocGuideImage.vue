<template>
  <section class="guide-section">
    <h2>{{ currentLanguage === 'de' ? 'Bild-Transformation' : 'Image Transformation' }}</h2>

    <div class="concept-card highlight">
      <h3>{{ currentLanguage === 'de' ? 'Teil eines größeren Prozesses' : 'Part of a Larger Process' }}</h3>
      <p>{{ currentLanguage === 'de'
        ? 'Im Bild-Modus wird die Plattform Teil eines größeren material-räumlichen Prozesses: Sie steht nicht im Zentrum, sondern ordnet sich ein. Kollektive Workshop-Prozesse, fotografische Raumerkundungen mit mobilen Geräten, eigene Skizzen — all das kann hier eingespeist und mit KI-Werkzeugen weiterverarbeitet werden, etwa in andere Kontexte gesetzt oder transformiert. Die integrierte Skizzenfunktion ermöglicht es, Ideen direkt in der Plattform visuell festzuhalten und als Ausgangspunkt zu verwenden.'
        : 'In Image Mode, the platform becomes part of a larger material-spatial process: it is not the center but integrates itself. Collective workshop processes, photographic space explorations with mobile devices, your own sketches — all of this can be fed in and further processed with AI tools, for example placed in different contexts or transformed. The integrated sketch function allows you to capture ideas visually right within the platform and use them as a starting point.' }}</p>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">1</span>
        <h3>{{ currentLanguage === 'de' ? 'Bild hochladen' : 'Upload Image' }}</h3>
      </div>
      <p>{{ currentLanguage === 'de'
        ? 'Lade ein Bild hoch — ein eigenes Foto, eine Zeichnung, oder ein zuvor generiertes Bild. Das Bild wird von der KI "gelesen" und beschrieben.'
        : 'Upload an image — a photo you took, a drawing, or a previously generated image. The AI will "read" and describe the image.' }}</p>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">2</span>
        <h3>{{ currentLanguage === 'de' ? 'Beschreibung hinzufügen (optional)' : 'Add Description (optional)' }}</h3>
      </div>
      <p>{{ currentLanguage === 'de'
        ? 'Du kannst eine zusätzliche Beschreibung eingeben, die der KI sagt, worauf sie achten oder was sie verändern soll. Ohne Beschreibung arbeitet die KI frei auf Basis des Bildes und der gewählten Regeln.'
        : 'You can add an optional description telling the AI what to focus on or change. Without a description, the AI works freely based on the image and the selected rules.' }}</p>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">3</span>
        <h3>{{ currentLanguage === 'de' ? 'Regeln und Konfiguration wählen' : 'Choose Rules and Configuration' }}</h3>
      </div>
      <p>{{ currentLanguage === 'de'
        ? 'Die gleichen Regeln wie im Text-Modus stehen zur Verfügung. Die Regeln bestimmen, WIE das Bild transformiert wird — von welcher Perspektive, mit welchem Stil, welcher Verfremdung.'
        : 'The same rules as in Text Mode are available. The rules determine HOW the image is transformed — from which perspective, with which style, which defamiliarization.' }}</p>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">4</span>
        <h3>{{ currentLanguage === 'de' ? 'Modell wählen und generieren' : 'Choose Model and Generate' }}</h3>
      </div>
      <p>{{ currentLanguage === 'de'
        ? 'Wähle ein Ausgabemedium und Modell. Der gleiche Input kann mit verschiedenen Modellen völlig unterschiedliche Ergebnisse liefern — das ist Teil des Experiments.'
        : 'Choose an output medium and model. The same input can produce completely different results with different models — that\'s part of the experiment.' }}</p>
    </div>

    <div class="concept-card highlight">
      <h3>{{ currentLanguage === 'de' ? 'Zirkularität nutzen' : 'Using Circularity' }}</h3>
      <p>{{ currentLanguage === 'de'
        ? 'Der Bild-Modus entfaltet seine volle Kraft durch Zirkularität: Generiere ein Bild im Text-Modus, lade es hier hoch, transformiere es weiter — oder lade ein Ergebnis zurück in den Text-Modus. Jeder Durchlauf verändert das Bild auf neue Weise. Eigene Fotos, Zeichnungen oder Collagen sind besonders spannende Ausgangspunkte.'
        : 'Image Mode unfolds its full power through circularity: Generate an image in Text Mode, upload it here, transform it further — or load a result back into Text Mode. Each pass changes the image in new ways. Your own photos, drawings, or collages make particularly exciting starting points.' }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{ currentLanguage: string }>()
</script>
