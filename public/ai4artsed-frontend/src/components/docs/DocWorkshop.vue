<template>
  <section class="workshop-section">
    <h2>{{ currentLanguage === 'de' ? 'Für Pädagog:innen' : 'For Educators' }}</h2>

    <div class="workshop-intro">
      <p>{{ currentLanguage === 'de'
        ? 'Das UCDCAE AI LAB ist für den Einsatz in Workshops und Unterricht konzipiert. Hier einige Hinweise für die Begleitung.'
        : 'The UCDCAE AI LAB is designed for use in workshops and teaching. Here are some tips for facilitation.' }}</p>
    </div>

    <div class="workshop-card">
      <h3>{{ currentLanguage === 'de' ? 'Was die Plattform KANN' : 'What the Platform CAN Do' }}</h3>
      <ul>
        <li>{{ currentLanguage === 'de' ? 'Kreative Prozesse sichtbar machen' : 'Make creative processes visible' }}</li>
        <li>{{ currentLanguage === 'de' ? 'Zum Nachdenken über Gestaltungsentscheidungen anregen' : 'Encourage reflection on design decisions' }}</li>
        <li>{{ currentLanguage === 'de' ? 'Die "Black Box" KI ein Stück öffnen' : 'Open the AI "black box" a little' }}</li>
        <li>{{ currentLanguage === 'de' ? 'Experimentierräume für kritische Auseinandersetzung bieten' : 'Provide spaces for critical engagement' }}</li>
      </ul>
    </div>

    <div class="workshop-card">
      <h3>{{ currentLanguage === 'de' ? 'Was die Plattform NICHT KANN' : 'What the Platform CANNOT Do' }}</h3>
      <ul>
        <li>{{ currentLanguage === 'de' ? 'Die pädagogische Begleitung ersetzen' : 'Replace pedagogical guidance' }}</li>
        <li>{{ currentLanguage === 'de' ? 'Von selbst zu kritischem Denken führen' : 'Automatically lead to critical thinking' }}</li>
        <li>{{ currentLanguage === 'de' ? '"Bessere Bilder" garantieren' : 'Guarantee "better images"' }}</li>
      </ul>
    </div>

    <div class="workshop-card">
      <h3>{{ currentLanguage === 'de' ? 'Reflexionsfragen für Workshops' : 'Reflection Questions for Workshops' }}</h3>
      <ul class="question-list">
        <li>{{ currentLanguage === 'de' ? 'Warum hat das Modell diese Interpretation gewählt?' : 'Why did the model choose this interpretation?' }}</li>
        <li>{{ currentLanguage === 'de' ? 'Was wäre, wenn wir andere Regeln verwendet hätten?' : 'What if we had used different rules?' }}</li>
        <li>{{ currentLanguage === 'de' ? 'Wessen Handschrift trägt dieses Bild – deine oder die der KI?' : 'Whose signature does this image bear – yours or the AI\'s?' }}</li>
        <li>{{ currentLanguage === 'de' ? 'Was hat dich überrascht? Was war erwartbar?' : 'What surprised you? What was predictable?' }}</li>
      </ul>
    </div>

    <div class="workshop-card safety">
      <h3>{{ currentLanguage === 'de' ? 'Sicherheitsstufen' : 'Safety Levels' }}</h3>
      <p>{{ currentLanguage === 'de'
        ? 'Das Sicherheitssystem adressiert drei unabhängige Anliegen: §86a StGB (Strafrecht — verbotene Symbole), DSGVO (Datenschutz — Personennamen), und Jugendschutz (altersgerechte Inhalte). Die Stufe wird von der betreuenden Person in den Einstellungen festgelegt.'
        : 'The safety system addresses three independent concerns: §86a StGB (criminal law — prohibited symbols), GDPR (data protection — personal names), and youth protection (age-appropriate content). The level is set by the supervising person in the settings.' }}</p>
      <ul>
        <li><strong>{{ currentLanguage === 'de' ? 'Kinder (8–12)' : 'Kids (8–12)' }}</strong> — {{ currentLanguage === 'de'
          ? 'Alle Filter aktiv: §86a, DSGVO, Jugendschutz (Kinder-Parameter), KI-Bildanalyse'
          : 'All filters active: §86a, GDPR, youth protection (kids parameters), AI image analysis' }}</li>
        <li><strong>{{ currentLanguage === 'de' ? 'Jugend (13–17)' : 'Youth (13–17)' }}</strong> — {{ currentLanguage === 'de'
          ? 'Alle Filter aktiv: §86a, DSGVO, Jugendschutz (Youth-Parameter), KI-Bildanalyse'
          : 'All filters active: §86a, GDPR, youth protection (youth parameters), AI image analysis' }}</li>
        <li><strong>{{ currentLanguage === 'de' ? 'Erwachsene' : 'Adults' }}</strong> — {{ currentLanguage === 'de'
          ? '§86a und DSGVO aktiv. Kein Jugendschutz, keine Bildanalyse. Für Erwachsenenbildung und universitäre Kontexte.'
          : '§86a and GDPR active. No youth protection, no image analysis. For adult and university education.' }}</li>
        <li><strong>{{ currentLanguage === 'de' ? 'Forschung' : 'Research' }}</strong> — {{ currentLanguage === 'de'
          ? 'KEINE Filter aktiv. Ausschließlich für autorisierte Forschungseinrichtungen (siehe LICENSE.md §3(e)). Ungefilterte Ausgaben dürfen niemals Lernenden präsentiert werden.'
          : 'NO filters active. Exclusively for authorized research institutions (see LICENSE.md §3(e)). Unfiltered outputs must never be presented to learners.' }}</li>
      </ul>
      <p style="margin-top: 8px;"><em>{{ currentLanguage === 'de'
        ? 'Die DSGVO-Prüfung (Personennamen) läuft immer lokal — Daten verlassen nie das System.'
        : 'The GDPR check (personal names) always runs locally — data never leaves the system.' }}</em></p>
      <p style="margin-top: 8px;"><em>{{ currentLanguage === 'de'
        ? 'Wichtig: LLM-basierte Sicherheitsmechanismen bieten niemals absolute Sicherheit. Fehlerhafte Durchlassungen oder falsche Blockierungen sind unvermeidbar. Die pädagogische Verantwortung liegt beim Anwender, nicht beim System.'
        : 'Important: LLM-based safety mechanisms never provide absolute security. False passes or incorrect blocks are unavoidable. The pedagogical responsibility lies with the user, not the system.' }}</em></p>
    </div>

    <div class="workshop-card">
      <h3>{{ currentLanguage === 'de' ? 'LLM-Konfiguration' : 'LLM Configuration' }}</h3>
      <p>{{ currentLanguage === 'de'
        ? 'In den Einstellungen können die verwendeten Sprachmodelle flexibel konfiguriert werden:'
        : 'The language models used can be flexibly configured in the settings:' }}</p>
      <ul>
        <li>{{ currentLanguage === 'de' ? 'Lokale Modelle – volle Datenkontrolle' : 'Local models – full data control' }}</li>
        <li>{{ currentLanguage === 'de' ? 'Externe Cloud-Anbieter – mehr Leistung' : 'External cloud providers – more performance' }}</li>
        <li>{{ currentLanguage === 'de' ? 'DSGVO-konforme Optionen (Mistral, lokale Modelle)' : 'GDPR-compliant options (Mistral, local models)' }}</li>
      </ul>
    </div>

    <div class="workshop-card installation">
      <h3>{{ currentLanguage === 'de' ? 'Installation und Betrieb' : 'Installation and Operation' }}</h3>
      <p>{{ currentLanguage === 'de'
        ? 'Das UCDCAE AI LAB ist ein komplexes System mit mehreren Komponenten (Backend, Frontend, LLM-Anbindung, Bildgenerierung, Sicherheitssystem). Die Installation erfordert Erfahrung mit Python, Node.js, GPU-Konfiguration und KI-Modellen.'
        : 'The UCDCAE AI LAB is a complex system with multiple components (backend, frontend, LLM integration, image generation, safety system). Installation requires experience with Python, Node.js, GPU configuration, and AI models.' }}</p>
      <p><strong>{{ currentLanguage === 'de'
        ? 'Der Einsatz eines KI-Coding-Agenten (z.B. Claude Code) wird dringend empfohlen'
        : 'The use of an AI coding agent (e.g. Claude Code) is highly recommended' }}</strong> — {{ currentLanguage === 'de'
        ? 'sowohl für die initiale Installation als auch für Konfiguration und Wartung.'
        : 'both for initial installation and for configuration and maintenance.' }}</p>
    </div>

    <div class="contact-box">
      <h3>{{ currentLanguage === 'de' ? 'Kontakt' : 'Contact' }}</h3>
      <p>{{ currentLanguage === 'de'
        ? 'Für Fragen zur Nutzung in Bildungskontexten:'
        : 'For questions about use in educational contexts:' }}</p>
      <a href="mailto:ucdcae@fau.de">ucdcae@fau.de</a>
      <p style="margin-top: 0.5rem">{{ currentLanguage === 'de'
        ? 'Für Lizenzfragen, kommerzielle Anfragen und Autorisierungen:'
        : 'For license inquiries, commercial requests, and authorizations:' }}</p>
      <a href="mailto:benjamin.joerissen@fau.de">benjamin.joerissen@fau.de</a>
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{ currentLanguage: string }>()
</script>
