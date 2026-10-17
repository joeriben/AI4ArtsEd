<template>
  <div class="landing-view">

    <!-- Hero Section -->
    <section class="hero">
      <h1 class="hero-title">A<sup class="hero-ai">i</sup>TELIER</h1>
      <p class="hero-expanded">AI Toolkit for Experiential Learning and Inquiry-based Educational Research</p>
      <p class="hero-subtitle hero-subtitle-lead">{{ $t('landing.subtitlePrefix') }}</p>
      <p class="hero-wordmark"><span style="color:#667eea">U</span>NESCO <span style="color:#e91e63">C</span>hair in <span style="color:#7C4DFF">D</span>igital <span style="color:#FF6F00">C</span>ulture and <span style="color:#4CAF50">A</span>rts in <span style="color:#00BCD4">E</span>ducation</p>
      <p class="hero-subtitle">{{ $t('landing.subtitleSuffix') }}</p>
    </section>

    <!-- Feature Cards Grid -->
    <section class="features">
      <div class="feature-grid">
        <div
          v-for="feature in features"
          :key="feature.id"
          class="feature-card"
          :style="{ '--feature-color': feature.color }"
          @click="router.push(feature.route)"
        >
          <!-- Preview images (each card on its own irregular rhythm) -->
          <div v-if="feature.previewImages.length" class="card-preview">
            <div
              v-for="(image, i) in feature.previewImages"
              :key="image"
              class="preview-bg"
              :class="{ 'is-current': i === (previewIndices[feature.id] ?? 0) % feature.previewImages.length }"
              :style="{ backgroundImage: `url(${image})` }"
            ></div>
            <div class="preview-overlay"></div>
          </div>

          <!-- Card content -->
          <div class="card-body">
            <div class="card-icon">
              <svg xmlns="http://www.w3.org/2000/svg" height="32" width="32" :viewBox="feature.icon.viewBox" fill="currentColor"><path :d="feature.icon.d" /></svg>
            </div>
            <h3 class="card-title">{{ $t(feature.titleKey) }}</h3>
            <p class="card-description">{{ $t(feature.descriptionKey) }}</p>
          </div>

          <!-- Color accent bar -->
          <div class="card-accent"></div>
        </div>
      </div>
    </section>

    <!-- Funding -->
    <section class="funding">
      <div class="project-logos">
        <a href="https://kubi-meta.de/ai4artsed" target="_blank" rel="noopener noreferrer" class="project-logo-link">
          <img src="/logos/ai4artsed_wordmark.png" alt="AI4ArtsEd" class="project-wordmark-img" />
          <img src="/logos/ai4artsed_logo.jpg" alt="" class="project-logo" />
        </a>
        <a href="https://comearts.eu" target="_blank" rel="noopener noreferrer">
          <img src="/logos/comearts_logo.jpg" alt="COMeARTS" class="project-logo" />
        </a>
      </div>
      <div class="funding-row">
        <a href="https://www.bmfsfj.de/" target="_blank" rel="noopener noreferrer">
          <img src="/logos/BMBFSFJ_logo.png" :alt="$t('about.funding.title')" class="funding-logo" />
        </a>
      </div>
    </section>

  </div>
</template>

<script setup lang="ts">
import { reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { usePageContextStore } from '../stores/pageContext'
import type { PageContext } from '../composables/usePageContext'

const router = useRouter()

const pageContextStore = usePageContextStore()

// The handbook has an entry for this page. It only arrives if the page
// says which page it is.
const pageContext = computed<PageContext>(() => ({
  activeViewType: 'LandingView',
  pageDescription:
    'Startseite — der Eingang der Plattform, erreichbar über den linken ' +
    'Knopf in der Kopfzeile und über die Adresse selbst. Titel, darunter ' +
    'der UNESCO Chair in Digital Culture and Arts in Education als ' +
    'Herausgeber, darunter fünf Karten für die fünf Modi: Together, ' +
    'Contesting, Flow, Latent Lab und Canvas. Nicht jeder Ort hat eine ' +
    'Karte — die übrigen trägt die Kopfzeile. Am Fuß steht die Förderung. ' +
    'Kein Arbeitsplatz, ein Weg hinein.',
  pageContent: {},
}))

watch(pageContext, (ctx) => {
  pageContextStore.setPageContext(ctx)
}, { immediate: true })

onUnmounted(() => {
  pageContextStore.clearContext()
})

// Per-card preview index with staggered timing (±800ms random offset)
const previewIndices = reactive<Record<string, number>>({})
const timers: number[] = []

interface Feature {
  id: string
  route: string
  color: string
  titleKey: string
  descriptionKey: string
  icon: { viewBox: string; d: string }
  previewImages: string[]
}

function scheduleNextPreview(feature: Feature) {
  const wait = 7000 + Math.random() * 6000
  const timer = window.setTimeout(() => {
    previewIndices[feature.id] = (previewIndices[feature.id] ?? 0) + 1
    scheduleNextPreview(feature)
  }, wait)
  timers.push(timer)
}

onMounted(() => {
  features.forEach((feature) => {
    previewIndices[feature.id] = 0
    if (feature.previewImages.length < 2) return
    scheduleNextPreview(feature)
  })
})

onUnmounted(() => {
  timers.forEach(t => clearTimeout(t))
})

// Feature definitions with SVG icons from the header mode-selector
const features: Feature[] = [
  {
    id: 'together',
    route: '/together',
    color: '#667eea',
    titleKey: 'landing.features.together.title',
    descriptionKey: 'landing.features.together.description',
    icon: { viewBox: '0 -960 960 960', d: 'M40-160v-160q0-34 23.5-57t56.5-23h131q20 0 38 10t29 27q29 39 71.5 61t90.5 22q49 0 91.5-22t70.5-61q13-17 30.5-27t36.5-10h131q34 0 57 23t23 57v160H640v-91q-35 25-75.5 38T480-200q-43 0-84-13.5T320-252v92H40Zm440-160q-38 0-72-17.5T351-386q-17-25-42.5-39.5T253-440q22-37 93-58.5T480-520q63 0 134 21.5t93 58.5q-29 0-55 14.5T609-386q-22 32-56 49t-73 17ZM160-440q-50 0-85-35t-35-85q0-51 35-85.5t85-34.5q51 0 85.5 34.5T280-560q0 50-34.5 85T160-440Zm640 0q-50 0-85-35t-35-85q0-51 35-85.5t85-34.5q51 0 85.5 34.5T920-560q0 50-34.5 85T800-440ZM480-560q-50 0-85-35t-35-85q0-51 35-85.5t85-34.5q51 0 85.5 34.5T600-680q0 50-34.5 85T480-560Z' },
    previewImages: [
      '/config-previews/together_1.jpg',
    ],
  },
  {
    id: 'contesting',
    route: '/contesting',
    color: '#e91e63',
    titleKey: 'landing.features.contesting.title',
    descriptionKey: 'landing.features.contesting.description',
    icon: { viewBox: '0 -960 960 960', d: 'M160-360q-50 0-85-35t-35-85q0-50 35-85t85-35v-80q0-33 23.5-56.5T240-760h120q0-50 35-85t85-35q50 0 85 35t35 85h120q33 0 56.5 23.5T800-680v80q50 0 85 35t35 85q0 50-35 85t-85 35v160q0 33-23.5 56.5T720-120H240q-33 0-56.5-23.5T160-200v-160Zm200-80q25 0 42.5-17.5T420-500q0-25-17.5-42.5T360-560q-25 0-42.5 17.5T300-500q0 25 17.5 42.5T360-440Zm240 0q25 0 42.5-17.5T660-500q0-25-17.5-42.5T600-560q-25 0-42.5 17.5T540-500q0 25 17.5 42.5T600-440ZM320-280h320v-80H320v80Zm-80 80h480v-480H240v480Zm240-240Z' },
    previewImages: [
      '/config-previews/contesting_1.jpg',
    ],
  },
  {
    id: 'flow',
    route: '/x2x-flow',
    color: '#7C4DFF',
    titleKey: 'landing.features.flow.title',
    descriptionKey: 'landing.features.flow.description',
    icon: { viewBox: '0 -960 960 960', d: 'M750-614q-27 27-62 41t-70 14q-35 0-69-13.5T488-614l-75-75q-15-15-34-22.5t-39-7.5q-20 0-39 7.5T267-689l-75 75-57-57 75-75q27-27 61-40.5t69-13.5q35 0 68.5 13.5T469-746l75 75q16 16 35 23.5t39 7.5q20 0 39.5-7.5T693-671l75-75 57 57-75 75Zm0 200q-27 27-61.5 40.5T619-360q-35 0-69.5-13.5T488-414l-75-75q-15-15-34-22.5t-39-7.5q-20 0-39 7.5T267-489l-75 75-57-56 75-76q27-27 61-40.5t69-13.5q35 0 68.5 13.5T469-546l75 75q16 16 35 23.5t39 7.5q20 0 39.5-7.5T693-471l75-75 57 57-75 75Zm-1 200q-27 27-61 40.5T619-160q-35 0-69.5-13.5T488-214l-76-75q-15-15-34-22.5t-39-7.5q-20 0-39 7.5T266-289l-75 75-56-56 75-76q27-27 61-40.5t69-13.5q35 0 68.5 13.5T469-346l75 75q16 16 35.5 23.5T619-240q20 0 39-7.5t35-23.5l75-75 56 57-75 75Z' },
    previewImages: [
      '/config-previews/flow_1.jpg',
    ],
  },
  {
    id: 'latent-lab',
    route: '/latent-lab',
    color: '#00BCD4',
    titleKey: 'landing.features.latentLab.title',
    descriptionKey: 'landing.features.latentLab.description',
    icon: { viewBox: '0 -960 960 960', d: 'M200-120v-80h200v-80q-83 0-141.5-58.5T200-480q0-61 33.5-111t90.5-73q8-34 35.5-55t62.5-21l-22-62 38-14-14-36 76-28 12 38 38-14 110 300-38 14 14 38-76 28-12-38-38 14-24-66q-15 14-34.5 21t-39.5 5q-22-2-41-13.5T338-582q-27 16-42.5 43T280-480q0 50 35 85t85 35h320v80H520v80h240v80H200Zm346-458 36-14-68-188-38 14 70 188Zm-126-22q17 0 28.5-11.5T460-640q0-17-11.5-28.5T420-680q-17 0-28.5 11.5T380-640q0 17 11.5 28.5T420-600Zm126 22Zm-126-62Zm0 0Z' },
    previewImages: [
      '/config-previews/latent_lab_1.jpg',
      '/config-previews/latent_lab_3.jpg',
      '/config-previews/latent_lab_4.jpg',
      '/config-previews/latent_lab_6.jpg',
    ],
  },
  {
    id: 'canvas',
    route: '/canvas',
    color: '#4CAF50',
    titleKey: 'landing.features.canvas.title',
    descriptionKey: 'landing.features.canvas.description',
    icon: { viewBox: '0 0 24 24', d: 'M22 11V3h-7v3H9V3H2v8h7V8h2v10h4v3h7v-8h-7v3h-2V8h2v3z' },
    previewImages: [
      '/config-previews/canvas_workflow_1.png',
      '/config-previews/canvas_workflow_2.png',
      '/config-previews/canvas_workflow_3.png',
    ],
  },
]
</script>

<style scoped>
/* The entrance page stands inside the frame like every other page: exactly as
   tall as the area under the header, and it never scrolls. What gives way when
   the window gets shorter is the image strips and the type scale -- the five
   cards stay in one row, side by side. */
.landing-view {
  height: 100%;
  padding: clamp(1rem, 2.2vh, 2rem) 2rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: clamp(1rem, 3vh, 2.75rem);
  overflow: hidden;
}

.funding {
  margin-top: auto;
}

/* Hero */
.hero {
  --hero-ink: rgba(255, 255, 255, 0.9);
  text-align: center;
  max-width: 820px;
  flex: 0 0 auto;
  margin-top: auto;
  margin-bottom: auto;
}

.hero-title {
  font-size: clamp(1.75rem, 5.2vh, 4rem);
  font-weight: 700;
  color: var(--hero-ink);
  margin: 0 0 0.25rem 0;
  letter-spacing: 0.05em;
  line-height: 1.1;
}

.hero-title .hero-ai {
  font-size: 0.45em;
  font-weight: 700;
  display: inline-block;
  width: 0;
  margin-right: -0.17em;
  line-height: 0;
  vertical-align: baseline;
  position: relative;
  top: -0.95em;
  left: -0.44em;
  letter-spacing: 0;
}

.hero-expanded {
  font-size: clamp(0.85rem, 2vh, 1.3rem);
  font-weight: 400;
  color: var(--hero-ink);
  margin: 0 0 clamp(0.4rem, 1.4vh, 1.5rem) 0;
  line-height: 1.4;
  letter-spacing: 0.03em;
}

.hero-subtitle {
  font-size: clamp(0.8rem, 1.8vh, 1.25rem);
  color: var(--hero-ink);
  margin: 0;
  line-height: 1.45;
}

.hero-subtitle-lead {
  margin-bottom: 0;
}

.hero-wordmark {
  font-size: clamp(0.9rem, 2.1vh, 1.35rem);
  font-weight: 700;
  color: var(--hero-ink);
  letter-spacing: 0.02em;
  margin: 0;
  line-height: 1.45;
}

.hero-wordmark span {
  font-weight: 700;
}


/* Feature Grid -- one row, five modes, taking whatever height is left over */
.features {
  width: 100%;
  max-width: 1600px;
  flex: 0 0 auto;
  min-height: 0;
  display: flex;
  align-items: center;
}

.feature-grid {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: clamp(0.75rem, 1.2vw, 1.5rem);
}

/* Feature Card */
.feature-card {
  position: relative;
  background: rgb(var(--surface-1-rgb) / 0.9);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.feature-card:hover {
  transform: translateY(-4px);
  border-color: var(--feature-color);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), 0 0 20px color-mix(in srgb, var(--feature-color) 20%, transparent);
}

/* Preview area -- the strips keep the aspect they were cut to */
.card-preview {
  position: relative;
  flex: 0 0 auto;
  aspect-ratio: 700 / 320;
  overflow: hidden;
}

.preview-bg {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  opacity: 0;
  transition: opacity 2s ease-in-out;
}

.preview-bg.is-current {
  opacity: 1;
}

.preview-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(to bottom, transparent 40%, rgb(var(--surface-1-rgb) / 0.95) 100%);
}

/* Card body */
.card-body {
  padding: clamp(0.75rem, 1.5vh, 1.25rem);
  position: relative;
  flex: 1 0 auto;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.card-icon {
  color: var(--feature-color);
  margin-bottom: clamp(0.35rem, 0.9vh, 0.75rem);
  display: flex;
  align-items: center;
}

.card-icon :deep(svg) {
  width: clamp(20px, 2.8vh, 28px);
  height: clamp(20px, 2.8vh, 28px);
}

.card-title {
  font-size: clamp(0.95rem, 1.9vh, 1.1rem);
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
  margin: 0 0 0.35rem 0;
}

.card-description {
  font-size: clamp(0.75rem, 1.5vh, 0.85rem);
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
  line-height: 1.45;
}

/* Accent bar */
.card-accent {
  height: 3px;
  background: var(--feature-color);
  opacity: 0;
  transition: opacity 0.3s ease;
  flex: 0 0 auto;
}

.feature-card:hover .card-accent {
  opacity: 1;
}

/* Funding */
.funding {
  flex: 0 0 auto;
  align-self: flex-end;
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: clamp(1rem, 2.5vw, 2.5rem);
  padding: 0;
}

.funding-row {
  display: flex;
  align-items: stretch;
}

.funding-logo {
  height: 100%;
  width: auto;
}

.project-logos {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: clamp(0.25rem, 0.6vh, 0.5rem);
  margin-top: 0;
}

.project-logo {
  height: clamp(24px, 4.3vh, 46px);
  width: auto;
  opacity: 0.7;
  transition: opacity 0.3s;
}

.project-logo:hover {
  opacity: 1;
}

.project-logo-link {
  display: flex;
  align-items: center;
  text-decoration: none;
  gap: 0;
}

.funding-row > a {
  display: flex;
  align-items: stretch;
}

.project-wordmark-img {
  height: clamp(24px, 4.3vh, 46px);
  width: auto;
  opacity: 0.7;
  transition: opacity 0.3s;
}

.project-logo-link:hover .project-wordmark-img,
.project-logo-link:hover .project-logo {
  opacity: 1;
}

/* Below this the row of five gets too narrow to read, and the page goes back
   to flowing -- a phone scrolls, that is what a phone does. */
@media (max-width: 900px), (max-height: 560px) {
  .landing-view {
    height: auto;
    min-height: 100%;
    overflow: visible;
    gap: 2rem;
    padding: 1.5rem 2rem;
  }

  .funding {
    margin-top: 0;
  }

  .features {
    display: block;
    flex: none;
  }

  .feature-grid {
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  }

  .card-preview {
    aspect-ratio: auto;
    height: 140px;
  }

  .funding {
    align-self: center;
    flex-wrap: wrap;
    justify-content: center;
    padding: 2rem 0 1rem;
  }
}

@media (max-width: 600px) {
  .landing-view {
    padding: 1rem;
    gap: 1.5rem;
  }

  .feature-grid {
    grid-template-columns: 1fr;
  }

  .card-preview {
    height: 120px;
  }
}
</style>
