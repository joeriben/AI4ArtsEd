<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="modelValue" class="modal-overlay" @click="closeModal">
        <div class="modal-container" @click.stop>
          <div class="modal-header">
            <h1>{{ $t('docs.title') }}</h1>
            <button class="modal-close" @click="closeModal" :title="$t('common.back')">×</button>
          </div>

          <!-- Tab Navigation -->
          <div class="tab-nav">
            <button
              v-for="tab in tabs"
              :key="tab.id"
              :class="['tab-button', { active: activeTab === tab.id, 'tab-icon': tab.type === 'icon' || tab.type === 'img' }]"
              :data-tooltip="tab.type === 'icon' ? (currentLanguage === 'de' ? (tab as IconTab).tooltipDe : (tab as IconTab).tooltipEn) : tab.type === 'img' ? (currentLanguage === 'de' ? (tab as ImgTab).tooltipDe : (tab as ImgTab).tooltipEn) : undefined"
              @click="activeTab = tab.id"
            >
              <template v-if="tab.type === 'text'">
                {{ currentLanguage === 'de' ? (tab as TextTab).labelDe : (tab as TextTab).labelEn }}
              </template>
              <img v-else-if="tab.type === 'img'" :src="(tab as ImgTab).imgSrc" width="20" height="20" />
              <svg v-else xmlns="http://www.w3.org/2000/svg" height="20" :viewBox="(tab as IconTab).svgViewBox" width="20" fill="currentColor">
                <path :d="(tab as IconTab).svgPath" />
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <component :is="activeTabComponent" :current-language="currentLanguage" />

            <div class="disclaimer">
              <p>{{ currentLanguage === 'de'
                ? 'Die Inhalte dieser Seiten wurden mit Unterstützung von KI erstellt und redaktionell überarbeitet.'
                : 'The content of these pages was created with the assistance of AI and editorially reviewed.' }}</p>
            </div>
          </div>

        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, type Component } from 'vue'
import { useI18n } from 'vue-i18n'

import DocPrinciples from './docs/DocPrinciples.vue'
import DocWelcome from './docs/DocWelcome.vue'
import DocNews from './docs/DocNews.vue'
import DocGuideText from './docs/DocGuideText.vue'
import DocGuideImage from './docs/DocGuideImage.vue'
import DocGuideMulti from './docs/DocGuideMulti.vue'
import DocGuideMusic from './docs/DocGuideMusic.vue'
import DocGuideCompare from './docs/DocGuideCompare.vue'
import DocGuidePersona from './docs/DocGuidePersona.vue'
import DocGuideWorkshopPlanning from './docs/DocGuideWorkshopPlanning.vue'
import DocGuideCanvas from './docs/DocGuideCanvas.vue'
import DocGuideLatentLab from './docs/DocGuideLatentLab.vue'
import DocGuideTraining from './docs/DocGuideTraining.vue'
import DocWorkshop from './docs/DocWorkshop.vue'
import DocLicense from './docs/DocLicense.vue'

import loraParrotSvg from '../assets/icons/lora-parrot.svg'

interface TextTab {
  type: 'text'
  id: string
  labelDe: string
  labelEn: string
}

interface IconTab {
  type: 'icon'
  id: string
  tooltipDe: string
  tooltipEn: string
  color: string
  svgPath: string
  svgViewBox: string
}

interface ImgTab {
  type: 'img'
  id: string
  tooltipDe: string
  tooltipEn: string
  color: string
  imgSrc: string
}

type DocTab = TextTab | IconTab | ImgTab

const props = defineProps<{
  modelValue: boolean
}>()

const { locale } = useI18n()
const currentLanguage = computed(() => locale.value)

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const activeTab = ref('welcome')

const tabs: DocTab[] = [
  { type: 'text', id: 'welcome', labelDe: 'Über', labelEn: 'About' },
  { type: 'text', id: 'news', labelDe: 'News', labelEn: 'News' },
  { type: 'text', id: 'principles', labelDe: 'Prinzipien', labelEn: 'Principles' },
  { type: 'icon', id: 'guide-text', tooltipDe: 'Text-Transformation', tooltipEn: 'Text Transformation',
    color: 'rgba(255, 255, 255, 0.7)', svgViewBox: '0 -960 960 960',
    svgPath: 'M160-200v-80h528l-42-42 56-56 138 138-138 138-56-56 42-42H160Zm116-200 164-440h80l164 440h-76l-38-112H392l-40 112h-76Zm138-176h132l-64-182h-4l-64 182Z' },
  { type: 'icon', id: 'guide-image', tooltipDe: 'Bild-Transformation', tooltipEn: 'Image Transformation',
    color: 'rgba(255, 255, 255, 0.7)', svgViewBox: '0 -960 960 960',
    svgPath: 'M200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h560q33 0 56.5 23.5T840-760v560q0 33-23.5 56.5T760-120H200Zm0-80h560v-560H200v560Zm40-80h480L570-480 450-320l-90-120-120 160Zm-40 80v-560 560Z' },
  { type: 'icon', id: 'guide-multi', tooltipDe: 'Bildfusion', tooltipEn: 'Image Fusion',
    color: 'rgba(255, 255, 255, 0.7)', svgViewBox: '0 -960 960 960',
    svgPath: 'M120-840h320v320H120v-320Zm80 80v160-160Zm320-80h320v320H520v-320Zm80 80v160-160ZM120-440h320v320H120v-320Zm80 80v160-160Zm440-80h80v120h120v80H720v120h-80v-120H520v-80h120v-120Zm-40-320v160h160v-160H600Zm-400 0v160h160v-160H200Zm0 400v160h160v-160H200Z' },
  { type: 'icon', id: 'guide-music', tooltipDe: 'Musikgenerierung', tooltipEn: 'Music Generation',
    color: 'rgba(255, 255, 255, 0.7)', svgViewBox: '0 -960 960 960',
    svgPath: 'M400-120q-66 0-113-47t-47-113q0-66 47-113t113-47q23 0 42.5 5.5T480-418v-422h240v160H560v400q0 66-47 113t-113 47Z' },
  { type: 'icon', id: 'guide-compare', tooltipDe: 'Sprachvergleich', tooltipEn: 'Language Comparison',
    color: 'rgba(255, 255, 255, 0.7)', svgViewBox: '0 -960 960 960',
    svgPath: 'm320-160-56-57 103-103H80v-80h287L264-503l56-57 200 200-200 200Zm320-240L440-600l200-200 56 57-103 103h287v80H593l103 103-56 57Z' },
  { type: 'icon', id: 'guide-persona', tooltipDe: 'KI-Persona', tooltipEn: 'AI Persona',
    color: 'rgba(255, 255, 255, 0.7)', svgViewBox: '0 -960 960 960',
    svgPath: 'M160-360q-50 0-85-35t-35-85q0-50 35-85t85-35v-80q0-33 23.5-56.5T240-760h120q0-50 35-85t85-35q50 0 85 35t35 85h120q33 0 56.5 23.5T800-680v80q50 0 85 35t35 85q0 50-35 85t-85 35v160q0 33-23.5 56.5T720-120H240q-33 0-56.5-23.5T160-200v-160Zm200-80q25 0 42.5-17.5T420-500q0-25-17.5-42.5T360-560q-25 0-42.5 17.5T300-500q0 25 17.5 42.5T360-440Zm240 0q25 0 42.5-17.5T660-500q0-25-17.5-42.5T600-560q-25 0-42.5 17.5T540-500q0 25 17.5 42.5T600-440ZM320-280h320v-80H320v80Zm-80 80h480v-480H240v480Zm240-240Z' },
  { type: 'icon', id: 'guide-workshop-planning', tooltipDe: 'Workshop-Planung', tooltipEn: 'Workshop Planning',
    color: 'rgba(255, 255, 255, 0.7)', svgViewBox: '0 -960 960 960',
    svgPath: 'M40-160v-160q0-34 23.5-57t56.5-23h131q20 0 38 10t29 27q29 39 71.5 61t90.5 22q49 0 91.5-22t70.5-61q13-17 30.5-27t36.5-10h131q34 0 57 23t23 57v160H640v-91q-35 25-75.5 38T480-200q-43 0-84-13.5T320-252v92H40Zm440-160q-38 0-72-17.5T351-386q-17-25-42.5-39.5T253-440q22-37 93-58.5T480-520q63 0 134 21.5t93 58.5q-29 0-55 14.5T609-386q-22 32-56 49t-73 17ZM160-440q-50 0-85-35t-35-85q0-51 35-85.5t85-34.5q51 0 85.5 34.5T280-560q0 50-34.5 85T160-440Zm640 0q-50 0-85-35t-35-85q0-51 35-85.5t85-34.5q51 0 85.5 34.5T920-560q0 50-34.5 85T800-440ZM480-560q-50 0-85-35t-35-85q0-51 35-85.5t85-34.5q51 0 85.5 34.5T600-680q0 50-34.5 85T480-560Z' },
  { type: 'icon', id: 'guide-canvas', tooltipDe: 'Canvas Workflow', tooltipEn: 'Canvas Workflow',
    color: 'rgba(255, 255, 255, 0.7)', svgViewBox: '0 0 24 24',
    svgPath: 'M22 11V3h-7v3H9V3H2v8h7V8h2v10h4v3h7v-8h-7v3h-2V8h2v3z' },
  { type: 'icon', id: 'guide-latentlab', tooltipDe: 'Latent Lab', tooltipEn: 'Latent Lab',
    color: 'rgba(255, 255, 255, 0.7)', svgViewBox: '0 -960 960 960',
    svgPath: 'M200-120v-80h200v-80q-83 0-141.5-58.5T200-480q0-61 33.5-111t90.5-73q8-34 35.5-55t62.5-21l-22-62 38-14-14-36 76-28 12 38 38-14 110 300-38 14 14 38-76 28-12-38-38 14-24-66q-15 14-34.5 21t-39.5 5q-22-2-41-13.5T338-582q-27 16-42.5 43T280-480q0 50 35 85t85 35h320v80H520v80h240v80H200Zm346-458 36-14-68-188-38 14 70 188Zm-126-22q17 0 28.5-11.5T460-640q0-17-11.5-28.5T420-680q-17 0-28.5 11.5T380-640q0 17 11.5 28.5T420-600Zm126 22Zm-126-62Zm0 0Z' },
  { type: 'img', id: 'guide-training', tooltipDe: 'LoRA Training', tooltipEn: 'LoRA Training',
    color: 'rgba(255, 255, 255, 0.7)', imgSrc: loraParrotSvg },
  { type: 'text', id: 'workshop', labelDe: 'Praxiseinsatz', labelEn: 'Practical Use' },
  { type: 'text', id: 'license', labelDe: 'Lizenz', labelEn: 'License' },
]

const tabComponents: Record<string, Component> = {
  'welcome': DocWelcome,
  'news': DocNews,
  'principles': DocPrinciples,
  'guide-text': DocGuideText,
  'guide-image': DocGuideImage,
  'guide-multi': DocGuideMulti,
  'guide-music': DocGuideMusic,
  'guide-compare': DocGuideCompare,
  'guide-persona': DocGuidePersona,
  'guide-workshop-planning': DocGuideWorkshopPlanning,
  'guide-canvas': DocGuideCanvas,
  'guide-latentlab': DocGuideLatentLab,
  'guide-training': DocGuideTraining,
  'workshop': DocWorkshop,
  'license': DocLicense,
}

const activeTabComponent = computed(() => tabComponents[activeTab.value])

function closeModal() {
  emit('update:modelValue', false)
}

function handleEscape(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.modelValue) {
    closeModal()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleEscape)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleEscape)
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
  overflow-y: auto;
}

.modal-container {
  background: #0a0a0a;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  max-width: 800px;
  width: 100%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem 2rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  flex-shrink: 0;
}

.modal-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  color: #ffffff;
  margin: 0;
}

.modal-close {
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  font-size: 2rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.3s ease;
}

.modal-close:hover {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.9);
}

/* Tab Navigation */
.tab-nav {
  display: flex;
  gap: 0.5rem;
  padding: 1rem 2rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  flex-shrink: 0;
  overflow-x: auto;
}

.tab-button {
  padding: 0.6rem 1.2rem;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
  font-size: 0.9rem;
}

.tab-button:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.3);
}

.tab-button.active {
  background: rgba(76, 175, 80, 0.2);
  border-color: #4CAF50;
  color: #4CAF50;
}

/* Icon Tab Buttons */
.tab-button.tab-icon {
  padding: 0.5rem;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  color: rgba(255, 255, 255, 0.5);
  border-color: rgba(255, 255, 255, 0.15);
}

.tab-button.tab-icon:hover {
  color: rgba(255, 255, 255, 0.8);
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.3);
}

.tab-button.tab-icon.active {
  color: rgba(255, 255, 255, 0.9);
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.4);
}

/* CSS Tooltip for icon tabs */
.tab-button.tab-icon::after {
  content: attr(data-tooltip);
  position: absolute;
  top: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  padding: 4px 8px;
  background: rgba(30, 30, 30, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 4px;
  font-size: 0.75rem;
  white-space: nowrap;
  color: rgba(255, 255, 255, 0.9);
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.2s ease;
  z-index: 10;
}

.tab-button.tab-icon:hover::after {
  opacity: 1;
}

/* Modal Body */
.modal-body {
  padding: 2rem;
  overflow-y: auto;
  flex: 1;
  color: #ffffff;
}

/* Modal Fade Transition */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.3s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-active .modal-container,
.modal-fade-leave-active .modal-container {
  transition: transform 0.3s ease;
}

.modal-fade-enter-from .modal-container,
.modal-fade-leave-to .modal-container {
  transform: scale(0.95);
}

/* Responsive */
@media (max-width: 768px) {
  .modal-container {
    max-height: 95vh;
  }

  .modal-header {
    padding: 1rem 1.5rem;
  }

  .modal-header h1 {
    font-size: 1.25rem;
  }

  .tab-nav {
    padding: 0.75rem 1rem;
  }

  .tab-button {
    padding: 0.5rem 0.75rem;
    font-size: 0.85rem;
  }

  .modal-body {
    padding: 1.5rem;
  }
}
</style>

<!-- Shared styles for child components (unscoped) -->
<style>
/* Tab Content Animation */
.modal-body > * {
  animation: docFadeIn 0.3s ease;
}

@keyframes docFadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Info Sections */
.info-section {
  margin-bottom: 1.5rem;
}

.info-section h3 {
  color: #ffffff;
  font-size: 1.1rem;
  margin-bottom: 0.5rem;
}

.info-section p {
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.7;
  margin: 0;
}

/* Concept Cards */
.concept-card {
  padding: 1.25rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  margin-bottom: 1.5rem;
}

.concept-card.highlight {
  background: linear-gradient(135deg, rgba(76, 175, 80, 0.08), rgba(76, 175, 80, 0.03));
  border-color: rgba(76, 175, 80, 0.25);
}

.concept-card h3 {
  margin: 0 0 0.75rem 0;
  color: #ffffff;
  font-size: 1.1rem;
}

.concept-card p {
  margin: 0;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.7;
}

/* Step Cards */
.step-card {
  padding: 1.25rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  margin-bottom: 1rem;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.step-view-icon {
  flex-shrink: 0;
  opacity: 0.85;
  color: rgba(255, 255, 255, 0.9);
}

.step-badge {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #4CAF50;
  color: white;
  border-radius: 50%;
  font-weight: bold;
  font-size: 0.85rem;
  flex-shrink: 0;
}

.step-card h3 {
  margin: 0;
  color: #ffffff;
  font-size: 1rem;
}

.step-card p {
  margin: 0;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.6;
}

.step-card p.note {
  margin-top: 0.75rem;
  padding: 0.5rem 0.75rem;
  background: rgba(76, 175, 80, 0.1);
  border-radius: 4px;
  font-size: 0.9rem;
  color: #4CAF50;
}

.step-image-display {
  display: flex;
  justify-content: center;
  padding: 1rem 0;
  margin-bottom: 0.5rem;
}

.example-box {
  display: flex;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  margin-top: 0.75rem;
  font-size: 0.9rem;
}

.example-box strong {
  color: #4CAF50;
  flex-shrink: 0;
}

.example-box span {
  color: rgba(255, 255, 255, 0.8);
  font-style: italic;
}

/* Mode List */
.mode-list {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.mode-item {
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
  border-inline-start: 3px solid #4CAF50;
}

.mode-item-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.mode-item-header .mode-icon {
  color: #4CAF50;
  flex-shrink: 0;
}

.mode-item strong {
  color: #ffffff;
  font-size: 0.95rem;
}

.mode-item p {
  margin: 0.25rem 0 0 0;
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.7);
}

/* Concept Section */
.concept-section h2 {
  margin-bottom: 1rem;
}

.concept-section h3 {
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
  color: rgba(255, 255, 255, 0.9);
  font-size: 1rem;
}

/* Contact in Welcome */
.contact-welcome a {
  color: #4CAF50;
  text-decoration: none;
}

.contact-welcome a:hover {
  text-decoration: underline;
}

/* Principle Cards */
.principle-card {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
  padding: 1.25rem;
  margin-bottom: 1rem;
  border-inline-start: 3px solid #4CAF50;
}

.principle-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.principle-number {
  width: 28px;
  height: 28px;
  background: #4CAF50;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 0.9rem;
  flex-shrink: 0;
}

.principle-card h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #ffffff;
}

.principle-card p {
  margin: 0;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.6;
}

.tension-box {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: rgba(255, 152, 0, 0.15);
  border-radius: 6px;
  border-inline-start: 3px solid #FF9800;
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.9rem;
}

.tension-label {
  color: #FF9800;
  font-weight: 600;
  margin-inline-end: 0.5rem;
}

.circularity-chain {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: rgba(33, 150, 243, 0.1);
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  color: #2196F3;
  font-weight: 500;
}

/* Experiments Section */
.experiments-section .section-intro {
  color: rgba(255, 255, 255, 0.8);
  margin-bottom: 1.5rem;
  font-size: 1rem;
}

.experiment-card {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
  padding: 1.25rem;
  margin-bottom: 1rem;
}

.experiment-card.surrealizer { border-inline-start: 3px solid #9C27B0; }
.experiment-card.attention-cartography { border-inline-start: 3px solid #2196F3; }
.experiment-card.feature-probing { border-inline-start: 3px solid #4CAF50; }
.experiment-card.concept-algebra { border-inline-start: 3px solid #FF9800; }
.experiment-card.denoising-archaeology { border-inline-start: 3px solid #FF5722; }
.experiment-card.repeng { border-inline-start: 3px solid #E91E63; }
.experiment-card.model-comparison { border-inline-start: 3px solid #00BCD4; }
.experiment-card.bias-archaeology { border-inline-start: 3px solid #F44336; }
.experiment-card.latent-audio-synth { border-inline-start: 3px solid #FFC107; }
.experiment-card.mmaudio { border-inline-start: 3px solid #E040FB; }
.experiment-card.imagebind-guidance { border-inline-start: 3px solid #7C4DFF; }

.lab-section-heading {
  color: rgba(255, 255, 255, 0.9);
  font-size: 1.3rem;
  margin: 2rem 0 0.5rem 0;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.experiment-card h3 {
  margin: 0 0 0.5rem 0;
  color: #ffffff;
  font-size: 1.1rem;
}

.experiment-card p {
  margin: 0;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.5;
}

.experiment-what,
.experiment-why {
  margin-top: 0.75rem;
}

.experiment-what strong,
.experiment-why strong {
  display: block;
  color: #4CAF50;
  font-size: 0.9rem;
  margin-bottom: 0.25rem;
}

.experiment-what p,
.experiment-why p {
  margin: 0;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.6;
  font-size: 0.95rem;
}

.experiment-example {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.8);
  font-style: italic;
}

.experiment-example strong {
  color: #81C784;
  font-style: normal;
  margin-inline-end: 0.5rem;
}

.experiment-negative {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: rgba(147, 51, 234, 0.1);
  border-inline-start: 3px solid rgba(147, 51, 234, 0.5);
  border-radius: 6px;
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.8);
}

.experiment-negative strong {
  color: rgba(180, 130, 240, 0.95);
  display: block;
  margin-bottom: 0.25rem;
}

.experiment-negative p {
  margin: 0;
  line-height: 1.6;
}

/* Deep Dive Toggle */
.deep-dive-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 8px;
  color: rgba(59, 130, 246, 0.95);
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.deep-dive-toggle:hover {
  background: rgba(59, 130, 246, 0.25);
}

.toggle-arrow {
  font-size: 0.8rem;
  opacity: 0.7;
}

.deep-dive-content {
  margin-top: 0.75rem;
  padding: 1.25rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 8px;
}

.deep-dive-content h4 {
  color: rgba(59, 130, 246, 0.95);
  font-size: 1rem;
  margin: 1.25rem 0 0.5rem 0;
}

.deep-dive-content h4:first-child {
  margin-top: 0;
}

.deep-dive-content p {
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.7;
  font-size: 0.9rem;
  margin: 0.5rem 0;
}

.math-diagram {
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  padding: 0.75rem 1rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.8rem;
  color: rgba(180, 220, 255, 0.9);
  overflow-x: auto;
  white-space: pre;
  margin: 0.5rem 0;
  line-height: 1.5;
}

.math-list {
  padding-inline-start: 0.5rem;
  border-inline-start: 2px solid rgba(59, 130, 246, 0.3);
  margin: 0.5rem 0;
}

.math-list p {
  font-size: 0.85rem;
  margin: 0.4rem 0;
}

/* Workshop Tab */
.workshop-intro {
  margin-bottom: 1.5rem;
  color: rgba(255, 255, 255, 0.8);
  font-size: 1rem;
}

.workshop-card {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
  padding: 1.25rem;
  margin-bottom: 1rem;
}

.workshop-card h3 {
  margin: 0 0 0.75rem 0;
  color: #ffffff;
  font-size: 1rem;
}

.workshop-card ul {
  margin: 0;
  padding-inline-start: 1.25rem;
  color: rgba(255, 255, 255, 0.8);
}

.workshop-card li {
  margin-bottom: 0.5rem;
  line-height: 1.5;
}

/* Canvas Section */
.canvas-section {
  padding: 0.5rem;
}

.canvas-header {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.canvas-header-icon {
  flex-shrink: 0;
  color: #10b981;
  opacity: 0.9;
}

.canvas-header h2 {
  margin: 0 0 0.5rem 0;
}

.canvas-header .section-intro {
  margin: 0;
}

.canvas-card {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
  padding: 1.25rem;
  margin-bottom: 1rem;
}

.canvas-card.paradigm { border-inline-start: 3px solid #3b82f6; }
.canvas-card.interception { border-inline-start: 3px solid #8b5cf6; }
.canvas-card.recursive { border-inline-start: 3px solid #f59e0b; }
.canvas-card.nodes { border-inline-start: 3px solid #10b981; }
.canvas-card.target-groups { border-inline-start: 3px solid #06b6d4; }

.canvas-card h3 {
  margin: 0 0 1rem 0;
  color: #ffffff;
  font-size: 1.1rem;
}

.canvas-card p {
  margin: 0 0 0.75rem 0;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.5;
}

.canvas-card p:last-child {
  margin-bottom: 0;
}

.canvas-card .pragmatic-note {
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.7);
  font-style: italic;
}

.canvas-card ul {
  margin: 0.5rem 0 0 0;
  padding-inline-start: 1.25rem;
  color: rgba(255, 255, 255, 0.8);
}

.canvas-card li {
  margin-bottom: 0.5rem;
  line-height: 1.5;
}

.question-list li {
  font-style: italic;
  color: rgba(255, 255, 255, 0.9);
}

/* Contact Box */
.contact-box {
  margin-top: 1.5rem;
  padding: 1.25rem;
  background: rgba(76, 175, 80, 0.1);
  border-radius: 10px;
  text-align: center;
}

.contact-box h3 {
  margin: 0 0 0.5rem 0;
  color: #ffffff;
  font-size: 1rem;
}

.contact-box p {
  margin: 0 0 0.5rem 0;
  color: rgba(255, 255, 255, 0.8);
}

.contact-box a {
  color: #4CAF50;
  text-decoration: none;
  font-weight: 500;
}

.contact-box a:hover {
  text-decoration: underline;
}

/* Disclaimer */
.disclaimer {
  margin-top: 2rem;
  padding: 0.75rem;
  text-align: center;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.disclaimer p {
  margin: 0;
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.8rem;
}
</style>
