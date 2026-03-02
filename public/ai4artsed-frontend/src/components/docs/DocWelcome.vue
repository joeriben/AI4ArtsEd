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

  <!-- News Section -->
  <section v-if="newsItems.length > 0" class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Neuigkeiten' : 'News' }}</h3>
    <div class="news-list">
      <div v-for="item in newsItems" :key="item.id" class="news-item">
        <div class="news-item-header">
          <span class="news-date">{{ item.date }}</span>
          <span :class="['news-badge', `news-badge--${item.category}`]">
            {{ categoryLabel(item.category) }}
          </span>
        </div>
        <strong class="news-title">{{ localized(item.title) }}</strong>
        <p class="news-summary">{{ localized(item.summary) }}</p>
      </div>
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
import { ref, onMounted } from 'vue'

const props = defineProps<{ currentLanguage: string }>()

interface LocalizedString {
  en: string
  [key: string]: string
}

interface NewsItem {
  id: string
  date: string
  category: string
  title: LocalizedString
  summary: LocalizedString
}

const newsItems = ref<NewsItem[]>([])

const categoryLabels: Record<string, { de: string; en: string }> = {
  feature: { de: 'Neu', en: 'New' },
  improvement: { de: 'Verbessert', en: 'Improved' },
  content: { de: 'Inhalt', en: 'Content' },
  research: { de: 'Forschung', en: 'Research' },
}

function localized(obj: LocalizedString): string {
  return obj[props.currentLanguage] || obj.en
}

function categoryLabel(category: string): string {
  const labels = categoryLabels[category]
  if (!labels) return category
  return props.currentLanguage === 'de' ? labels.de : labels.en
}

onMounted(async () => {
  try {
    const base = import.meta.env.DEV ? 'http://localhost:17802' : ''
    const res = await fetch(`${base}/api/news?limit=5`)
    if (res.ok) {
      const data = await res.json()
      newsItems.value = data.items || []
    }
  } catch {
    // fail-silent: news section stays hidden
  }
})
</script>

<style>
/* News Items */
.news-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.news-item {
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
  border-inline-start: 3px solid rgba(76, 175, 80, 0.4);
}

.news-item-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.news-date {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.4);
}

.news-badge {
  font-size: 0.7rem;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.news-badge--feature {
  background: rgba(76, 175, 80, 0.2);
  color: #4CAF50;
}

.news-badge--improvement {
  background: rgba(33, 150, 243, 0.2);
  color: #2196F3;
}

.news-badge--content {
  background: rgba(255, 152, 0, 0.2);
  color: #FF9800;
}

.news-badge--research {
  background: rgba(156, 39, 176, 0.2);
  color: #9C27B0;
}

.news-title {
  display: block;
  color: #ffffff;
  font-size: 0.95rem;
  margin-bottom: 0.25rem;
}

.news-summary {
  margin: 0;
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.5;
}
</style>
