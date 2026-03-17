<template>
  <div dir="ltr" class="provenance-wrapper" v-if="hasProvenance || hasBasicMeta">
    <button class="provenance-toggle" @click="expanded = !expanded">
      <img :src="infoIcon" alt="" class="provenance-icon" />
      <span class="provenance-toggle-label">{{ t('provenance.title') }}</span>
      <span class="provenance-chevron" :class="{ 'chevron-open': expanded }">&#9662;</span>
    </button>

    <Transition name="provenance-expand">
      <div v-if="expanded" class="provenance-card">
        <!-- Kids mode: simplified view -->
        <template v-if="safetyLevel === 'kids'">
          <div class="provenance-kids">
            <p v-if="meta?.publisher" class="kids-line">
              <span class="kids-label">{{ t('provenance.madeBy') }}</span> {{ meta.publisher }}
            </p>
            <p v-if="meta?.fair_culture" class="kids-line">
              <span class="kids-label">{{ t('provenance.learnedFrom') }}</span> {{ meta.fair_culture }}
            </p>
            <p v-if="meta?.params" class="kids-line">
              <span class="kids-label">{{ t('provenance.howBig') }}</span> {{ meta.params }}
            </p>
            <p class="kids-note">{{ t('provenance.kidsNote') }}</p>
          </div>
        </template>

        <!-- Youth + Expert: full card -->
        <template v-else>
          <div class="model-specs">
            <div v-if="meta?.publisher" class="spec-row">
              <span class="spec-label">{{ t('provenance.publisher') }}</span>
              <span class="spec-value">{{ meta.publisher }}</span>
            </div>
            <div v-if="meta?.architecture" class="spec-row">
              <span class="spec-label">{{ t('provenance.architecture') }}</span>
              <span class="spec-value">{{ meta.architecture }}</span>
            </div>
            <div v-if="meta?.params" class="spec-row">
              <span class="spec-label">{{ t('provenance.parameters') }}</span>
              <span class="spec-value">{{ meta.params }}</span>
            </div>
            <div v-if="meta?.license" class="spec-row">
              <span class="spec-label">{{ t('provenance.license') }}</span>
              <span class="spec-value">{{ meta.license }}</span>
            </div>
            <div v-if="meta?.fair_culture" class="spec-row">
              <span class="spec-label">{{ t('provenance.trainingData') }}</span>
              <span class="spec-value">{{ meta.fair_culture }}</span>
            </div>
            <div v-if="meta?.safety_by_design" class="spec-row">
              <span class="spec-label">{{ t('provenance.safetyByDesign') }}</span>
              <span class="spec-value">{{ meta.safety_by_design }}</span>
            </div>
          </div>

          <!-- Provenance details (if available) -->
          <template v-if="provenance">
            <div v-if="provenance.training_data_sources?.length" class="spec-section">
              <span class="section-label">{{ t('provenance.sources') }}</span>
              <ul class="provenance-list">
                <li v-for="(source, i) in provenance.training_data_sources" :key="i">{{ source }}</li>
              </ul>
            </div>

            <div v-if="provenance.training_data_consent" class="spec-row">
              <span class="spec-label">{{ t('provenance.consent') }}</span>
              <span class="spec-value consent-badge" :class="'consent-' + provenance.training_data_consent">
                {{ t('provenance.consentValues.' + provenance.training_data_consent) }}
              </span>
            </div>

            <div v-if="biases.length" class="spec-section">
              <span class="section-label">{{ t('provenance.knownBiases') }}</span>
              <ul class="provenance-list provenance-biases">
                <li v-for="(bias, i) in biases" :key="i">{{ bias }}</li>
              </ul>
            </div>

            <div v-if="gaps.length" class="spec-section">
              <span class="section-label">{{ t('provenance.knownGaps') }}</span>
              <ul class="provenance-list provenance-gaps">
                <li v-for="(gap, i) in gaps" :key="i">{{ gap }}</li>
              </ul>
            </div>
          </template>

          <!-- Youth reflection prompt -->
          <p v-if="safetyLevel === 'youth'" class="youth-reflection">
            {{ t('provenance.youthReflection') }}
          </p>
        </template>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import infoIcon from '@/assets/icons/info_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg'

interface ProvenanceData {
  training_data_disclosed?: boolean
  training_data_sources?: string[]
  training_data_size?: string
  training_data_consent?: string
  geographic_origin?: string
  known_biases?: Array<{ en: string; [key: string]: string }>
  known_gaps?: Array<{ en: string; [key: string]: string }>
}

interface Props {
  meta: Record<string, any> | null
  safetyLevel: string
}

const props = defineProps<Props>()
const { t, locale } = useI18n()
const expanded = ref(false)

const provenance = computed<ProvenanceData | null>(() => props.meta?.provenance ?? null)

const hasProvenance = computed(() => !!provenance.value)
const hasBasicMeta = computed(() => !!props.meta?.publisher || !!props.meta?.fair_culture)

const biases = computed(() => {
  if (!provenance.value?.known_biases) return []
  return provenance.value.known_biases.map(b => b[locale.value] || b.en)
})

const gaps = computed(() => {
  if (!provenance.value?.known_gaps) return []
  return provenance.value.known_gaps.map(g => g[locale.value] || g.en)
})
</script>

<style scoped>
.provenance-wrapper {
  margin-top: 0.75rem;
}

.provenance-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: none;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 0.4rem 0.75rem;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.78rem;
  transition: all 0.2s ease;
  width: 100%;
  text-align: left;
}

.provenance-toggle:hover {
  border-color: rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.8);
}

.provenance-icon {
  width: 16px;
  height: 16px;
  opacity: 0.6;
}

.provenance-toggle-label {
  flex: 1;
}

.provenance-chevron {
  font-size: 0.7rem;
  transition: transform 0.2s ease;
}

.chevron-open {
  transform: rotate(180deg);
}

.provenance-card {
  background: rgba(20, 20, 20, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  padding: 1rem;
  margin-top: 0.5rem;
}

/* Spec grid — reuses DenoisingProgressView pattern */
.model-specs {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.35rem 0.75rem;
}

.spec-row {
  display: contents;
}

.spec-label {
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.5);
  white-space: nowrap;
}

.spec-value {
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.85);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

/* Provenance sections */
.spec-section {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.section-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: rgba(255, 255, 255, 0.4);
  display: block;
  margin-bottom: 0.4rem;
}

.provenance-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.provenance-list li {
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.75);
  padding: 0.2rem 0 0.2rem 0.75rem;
  position: relative;
}

.provenance-list li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0.55rem;
  width: 4px;
  height: 4px;
  border-radius: 50%;
}

.provenance-biases li::before {
  background: rgba(255, 183, 77, 0.6);
}

.provenance-gaps li::before {
  background: rgba(239, 83, 80, 0.5);
}

/* Consent badges */
.consent-badge {
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-size: 0.72rem;
}

.consent-none, .consent-unknown {
  background: rgba(239, 83, 80, 0.15);
  color: rgba(239, 83, 80, 0.9);
}

.consent-partial {
  background: rgba(255, 183, 77, 0.15);
  color: rgba(255, 183, 77, 0.9);
}

.consent-full {
  background: rgba(76, 175, 80, 0.15);
  color: rgba(76, 175, 80, 0.9);
}

/* Kids mode */
.provenance-kids {
  padding: 0.25rem 0;
}

.kids-line {
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.8);
  margin: 0.3rem 0;
}

.kids-label {
  color: rgba(255, 255, 255, 0.5);
}

.kids-note {
  font-size: 0.8rem;
  color: rgba(255, 183, 77, 0.7);
  margin-top: 0.75rem;
  font-style: italic;
}

/* Youth reflection */
.youth-reflection {
  font-size: 0.8rem;
  color: rgba(76, 175, 80, 0.7);
  margin-top: 0.75rem;
  padding-top: 0.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  font-style: italic;
}

/* Expand transition */
.provenance-expand-enter-active,
.provenance-expand-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}

.provenance-expand-enter-from,
.provenance-expand-leave-to {
  opacity: 0;
  max-height: 0;
  margin-top: 0;
  padding: 0;
}

.provenance-expand-enter-to,
.provenance-expand-leave-from {
  opacity: 1;
  max-height: 600px;
}

/* Mobile */
@media (max-width: 600px) {
  .model-specs {
    grid-template-columns: 1fr;
  }

  .spec-row {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }
}
</style>
