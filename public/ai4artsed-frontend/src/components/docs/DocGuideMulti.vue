<template>
  <section class="guide-section">
    <h2>{{ currentLanguage === 'de' ? 'Montage / Collage / Assemblage' : 'Montage / Collage / Assemblage' }}</h2>

    <div class="concept-card highlight">
      <h3>{{ currentLanguage === 'de' ? 'Raus aus der (Medien-)Box' : 'Out of the (Media) Box' }}</h3>
      <p>{{ currentLanguage === 'de'
        ? 'Im Multi-Bild-Modus entstehen Montagen, Collagen, Assemblagen: Bis zu drei Bilder werden zusammengebracht und im Embedding-Raum der KI zu etwas Neuem fusioniert. Das Material kann aus dem Gerät kommen — muss es aber nicht. Handy-Fotografien aus dem Raum, gefundene Vorlagen, eigene Skizzen, Bilder aus der Favoriten-Sammlung anderer Workshop-Teilnehmender — alles kann miteinander in Beziehung gesetzt werden.'
        : 'In Multi-Image Mode, you create montages, collages, assemblages: up to three images are brought together and fused into something new in the AI\'s embedding space. The material can come from the device — but it doesn\'t have to. Mobile photographs from the room, found templates, your own sketches, images from other workshop participants\' favorites collection — everything can be brought into relation with each other.' }}</p>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">1</span>
        <h3>{{ currentLanguage === 'de' ? 'Bilder hochladen (bis zu 3)' : 'Upload Images (up to 3)' }}</h3>
      </div>
      <p>{{ currentLanguage === 'de'
        ? 'Wähle bis zu drei Bilder aus. Sie können aus ganz verschiedenen Quellen stammen: eigene Handy-Fotos, Zeichnungen, gefundene Vorlagen, bereits generierte Bilder, oder Favoriten aus der Sammlung. Je unterschiedlicher die Quellen, desto spannender das Ergebnis.'
        : 'Select up to three images. They can come from very different sources: your own mobile photos, drawings, found templates, previously generated images, or favorites from the collection. The more different the sources, the more exciting the result.' }}</p>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">2</span>
        <h3>{{ currentLanguage === 'de' ? 'Beschreiben, was entstehen soll' : 'Describe What Should Emerge' }}</h3>
      </div>
      <p>{{ currentLanguage === 'de'
        ? 'Beschreibe, wie die Bilder kombiniert werden sollen. Du kannst auf Stimmung, Stil, Komposition oder Bedeutung eingehen. Die KI nutzt diese Beschreibung zusammen mit den Bildern als Ausgangspunkt.'
        : 'Describe how the images should be combined. You can address mood, style, composition, or meaning. The AI uses this description together with the images as a starting point.' }}</p>
    </div>

    <div class="step-card">
      <div class="step-header">
        <span class="step-badge">3</span>
        <h3>{{ currentLanguage === 'de' ? 'Regeln und Modell wählen' : 'Choose Rules and Model' }}</h3>
      </div>
      <p>{{ currentLanguage === 'de'
        ? 'Wie in den anderen Modi kannst du Regeln anwenden, die die Fusion beeinflussen. Das Modell bestimmt den visuellen Stil des Ergebnisses.'
        : 'As in the other modes, you can apply rules that influence the fusion. The model determines the visual style of the result.' }}</p>
    </div>

    <div class="concept-card highlight">
      <h3>{{ currentLanguage === 'de' ? 'Ideen für den Workshop' : 'Workshop Ideas' }}</h3>
      <p>{{ currentLanguage === 'de'
        ? 'Besonders produktiv wird der Multi-Bild-Modus im Workshop-Kontext: Teilnehmende fotografieren Räume, Objekte, Texturen mit ihren Mobilgeräten und bringen diese Fundstücke mit eigenen Skizzen oder den Favoriten anderer zusammen. Die Spannung zwischen den heterogenen Materialien — gefunden, gezeichnet, generiert, von mir, von anderen — ist das, was die Fusion interessant macht.'
        : 'Multi-Image Mode becomes particularly productive in workshop contexts: participants photograph spaces, objects, textures with their mobile devices and bring these found materials together with their own sketches or others\' favorites. The tension between heterogeneous materials — found, drawn, generated, mine, others\' — is what makes the fusion interesting.' }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{ currentLanguage: string }>()
</script>
