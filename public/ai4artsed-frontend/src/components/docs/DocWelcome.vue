<template>
  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Was ist das UCDCAE AI LAB?' : 'What is the UCDCAE AI LAB?' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'Das UCDCAE AI LAB ist eine pädagogisch-künstlerische Experimentierplattform des UNESCO Chair in Digital Culture and Arts in Education. Sie wurde entwickelt, um den kritischen und kreativen Umgang mit generativer KI in der kulturell-ästhetischen Medienbildung zu erforschen.'
      : 'The UCDCAE AI LAB is a pedagogical-artistic experimentation platform of the UNESCO Chair in Digital Culture and Arts in Education. It was developed to explore critical and creative engagement with generative AI in cultural-aesthetic media education.' }}</p>
  </section>

  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Warum diese Plattform?' : 'Why this platform?' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'Generative KI-Modelle sind mächtige Werkzeuge, aber auch "Black Boxes". Wir wollen verstehen: Wie reagieren verschiedene Modelle auf unterschiedliche Eingaben? Was passiert, wenn wir nicht nur kurze, einfache Prompts eingeben, sondern ausführliche, differenzierte Beschreibungen? Wie können wir lernen, selbst zu verstehen worum es uns geht? Wie können wir unsere Bildidee aus vielen unterschiedlichen Blickwinkeln verstehen und verändern?'
      : 'Generative AI models are powerful tools, but also "black boxes". We want to understand: How do different models react to different inputs? What happens when we don\'t just enter short, simple prompts, but detailed, nuanced descriptions? How can we learn to truly understand what we want? How can we understand and change our image idea from many different perspectives?' }}</p>
  </section>

  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Kulturelle Sensibilität und Biases' : 'Cultural Sensitivity and Biases' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'Ein zentrales Projektziel ist die kritische Erkundung generativer KI als Akteur in kulturellen, künstlerischen und gesellschaftlichen Zusammenhängen. Generative Modelle sind nicht neutral – sie tragen kulturelle, soziale, genderbezogene und ethnische Biases in sich, die aus ihren Trainingsdaten stammen. Diese Verzerrungen müssen sichtbar gemacht und kritisch untersucht werden, um zu verstehen, um welche Art von Akteur es sich bei generativer KI eigentlich handelt.'
      : 'A central project goal is the critical exploration of generative AI as an actor in cultural, artistic, and societal contexts. Generative models are not neutral – they carry cultural, social, gender-related, and ethnic biases inherited from their training data. These distortions must be made visible and critically examined in order to understand what kind of actor generative AI actually is.' }}</p>
  </section>

  <!-- Project Information (merged from AboutModal) -->
  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Das Projekt' : 'The Project' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'KI verändert Gesellschaft und Arbeitswelt; sie wird zunehmend Thema der Bildung. Das Projekt sondiert Chancen, Bedingungen und Grenzen des pädagogischen Einsatzes künstlicher Intelligenz (KI) in kulturell diversitätssensiblen Settings der Kulturellen Bildung (KuBi).'
      : 'AI is transforming society and the world of work; it is increasingly becoming a subject of education. The project explores opportunities, conditions, and limits of the pedagogical use of artificial intelligence (AI) in culturally diversity-sensitive settings of cultural education.' }}</p>
    <p>{{ currentLanguage === 'de'
      ? 'Aus einem insgesamt ca. zweijährigen partizipativen Designprozess soll eine Opensource-KI-Technologie hervorgehen, die auslotet, inwieweit KI-Systeme unter günstigen Realbedingungen bereits auf ihrer Strukturebene künstlerisch-pädagogische Maßgaben einbeziehen können.'
      : 'A participatory design process spanning approximately two years aims to produce an open-source AI technology that explores the extent to which AI systems can already incorporate artistic-pedagogical principles at their structural level under favorable real-world conditions.' }}</p>
    <p>
      {{ currentLanguage === 'de' ? 'Weitere Informationen: ' : 'More information: ' }}
      <a href="https://kubi-meta.de/ai4artsed" target="_blank" rel="noopener noreferrer">kubi-meta.de/ai4artsed</a>
    </p>
  </section>

  <section class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Team' : 'Team' }}</h3>
    <div class="team-member">
      <div class="team-role">{{ currentLanguage === 'de' ? 'Projektleitung' : 'Project Lead' }}</div>
      <strong>Prof. Dr. Benjamin Jörissen</strong>
      <p>{{ currentLanguage === 'de' ? 'Institut für Pädagogik' : 'Institute of Education' }}<br>
      {{ currentLanguage === 'de' ? 'Lehrstuhl für Pädagogik mit dem Schwerpunkt Kultur und ästhetische Bildung' : 'Chair of Education with Focus on Culture and Aesthetic Education' }}<br>
      UNESCO Chair in Digital Culture and Arts in Education</p>
      <p>E-Mail: <a href="mailto:benjamin.joerissen@fau.de">benjamin.joerissen@fau.de</a></p>
    </div>
    <div class="team-member">
      <div class="team-role">{{ currentLanguage === 'de' ? 'Wissenschaftliche Mitarbeiterin' : 'Research Associate' }}</div>
      <strong>Vanessa Baumann</strong>
      <p>{{ currentLanguage === 'de' ? 'Institut für Pädagogik' : 'Institute of Education' }}<br>
      {{ currentLanguage === 'de' ? 'Lehrstuhl für Pädagogik mit dem Schwerpunkt Kultur und ästhetische Bildung' : 'Chair of Education with Focus on Culture and Aesthetic Education' }}<br>
      UNESCO Chair in Digital Culture and Arts in Education</p>
      <p>E-Mail: <a href="mailto:ucdcae@fau.de">ucdcae@fau.de</a></p>
    </div>
  </section>

  <section class="info-section funding-section">
    <h3>{{ currentLanguage === 'de' ? 'Gefördert vom' : 'Funded by' }}</h3>
    <div class="funding-logo">
      <a href="https://www.bmfsfj.de/" target="_blank" rel="noopener noreferrer">
        <img src="/logos/BMBFSFJ_logo.png" alt="BMBFSFJ" />
      </a>
    </div>
    <div class="project-logos">
      <a href="https://kubi-meta.de/ai4artsed" target="_blank" rel="noopener noreferrer" class="project-logo-link">
        <img src="/logos/ai4artsed_wordmark.png" alt="AI4ArtsEd" class="project-wordmark-img" />
        <img src="/logos/ai4artsed_logo.jpg" alt="" class="project-logo-img" />
      </a>
      <a href="https://comearts.eu" target="_blank" rel="noopener noreferrer">
        <img src="/logos/comearts_logo.jpg" alt="COMeARTS" class="project-logo-img" />
      </a>
    </div>
  </section>

  <section class="info-section contact-welcome">
    <h3>{{ currentLanguage === 'de' ? 'Kontakt' : 'Contact' }}</h3>
    <p>{{ currentLanguage === 'de'
      ? 'Frag Träshy direkt in der Anwendung, oder schreibe an: '
      : 'Ask Träshy directly in the application, or write to: ' }}<a href="mailto:ucdcae@fau.de">ucdcae@fau.de</a></p>
  </section>
</template>

<script setup lang="ts">
defineProps<{ currentLanguage: string }>()
</script>

<style scoped>
.team-member {
  margin-top: 1rem;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 6px;
}

.team-role {
  font-size: 0.85rem;
  color: #4CAF50;
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.team-member strong {
  color: #ffffff;
  font-size: 1rem;
}

.team-member p {
  margin: 0.25rem 0;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.9rem;
  line-height: 1.5;
}

.funding-section {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.funding-logo {
  margin-top: 0.75rem;
  text-align: center;
}

.funding-logo img {
  max-width: 350px;
  width: 100%;
  height: auto;
  background: white;
  padding: 0.75rem;
  border-radius: 8px;
}

.project-logos {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2rem;
  margin-top: 1rem;
}

.project-logo-img {
  max-height: 50px;
  width: auto;
}

.project-logo-link {
  display: flex;
  align-items: center;
  text-decoration: none;
  gap: 0;
}

.project-wordmark-img {
  max-height: 50px;
  width: auto;
}
</style>
