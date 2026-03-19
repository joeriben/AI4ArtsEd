<template>
  <!-- News Section (extracted from DocWelcome) -->
  <section v-if="newsItems.length > 0" class="info-section">
    <h3>{{ currentLanguage === 'de' ? 'Neuigkeiten' : 'News' }}</h3>
    <div class="news-list">
      <div v-for="item in visibleNews" :key="item.id" class="news-item">
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
    <button
      v-if="newsItems.length > pageSize"
      class="news-toggle"
      @click="toggleNews"
    >
      {{ visibleCount >= newsItems.length
        ? (currentLanguage === 'de' ? 'Weniger anzeigen' : 'Show less')
        : (currentLanguage === 'de'
          ? `Mehr anzeigen (${newsItems.length - visibleCount} weitere)`
          : `Show more (${newsItems.length - visibleCount} remaining)`) }}
    </button>
  </section>

  <section v-else class="info-section">
    <p class="no-news">{{ currentLanguage === 'de' ? 'Keine Neuigkeiten vorhanden.' : 'No news available.' }}</p>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

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
const pageSize = 5
const visibleCount = ref(pageSize)

const visibleNews = computed(() =>
  newsItems.value.slice(0, visibleCount.value)
)

function toggleNews() {
  if (visibleCount.value >= newsItems.value.length) {
    visibleCount.value = pageSize
  } else {
    visibleCount.value = Math.min(visibleCount.value + pageSize, newsItems.value.length)
  }
}

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
    const res = await fetch(`${base}/api/news`)
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
/* News Items — shared (unscoped) so parent modal can style them */
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

.news-toggle {
  display: block;
  margin-top: 0.75rem;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.85rem;
  padding: 0.4rem 0.8rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.news-toggle:hover {
  border-color: rgba(255, 255, 255, 0.3);
  color: rgba(255, 255, 255, 0.8);
}

.no-news {
  color: rgba(255, 255, 255, 0.4);
  font-style: italic;
}
</style>
