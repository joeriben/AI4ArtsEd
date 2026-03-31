<template>
  <div class="no-match-state">
    <div class="no-match-content">
      <div class="no-match-icon">—</div>
      <h2 class="no-match-title">
        {{ currentLanguage === 'en' ? 'sorry, no matches' : 'sorry, keine Treffer' }}
      </h2>
      <p class="no-match-message">
        {{
          currentLanguage === 'en'
            ? 'Try a different combination?'
            : 'Andere Kombination probieren?'
        }}
      </p>

      <!-- Suggestions -->
      <div v-if="partialMatches.length > 0" class="suggestions">
        <h3 class="suggestions-title">
          {{ currentLanguage === 'en' ? 'Partial matches' : 'Teilweise Übereinstimmungen' }}
        </h3>
        <p class="suggestions-subtitle">
          {{
            currentLanguage === 'en'
              ? 'These configs match some of your selected properties:'
              : 'Diese Konfigurationen entsprechen einigen Ihrer ausgewählten Eigenschaften:'
          }}
        </p>

        <div class="suggestions-list">
          <div
            v-for="match in partialMatches"
            :key="match.config.id"
            class="suggestion-item"
            @click="handleSuggestionClick(match.config.id)"
          >
            <div class="suggestion-header">
              <h4 class="suggestion-name">{{ match.config.name[currentLanguage] }}</h4>
              <span class="suggestion-score">
                {{ match.matchScore }}/{{ selectedPropertiesCount }}
              </span>
            </div>
            <p class="suggestion-description">
              {{ match.config.short_description[currentLanguage] }}
            </p>
            <div class="suggestion-properties">
              <span
                v-for="prop in match.matchingProps"
                :key="prop"
                class="matching-property"
                :style="{ '--tag-color': getPropertyColor(prop) }"
              >
                {{ $t('properties.' + prop) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="no-match-actions">
        <button class="action-button reset" @click="handleClearSelection">
          {{ currentLanguage === 'en' ? 'reset' : 'zurücksetzen' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ConfigMetadata } from '@/stores/configSelection'
import type { SupportedLanguage } from '@/i18n'

/**
 * NoMatchState - No-match state with suggestions
 *
 * Displayed when selected property combination matches no configs.
 * Shows partial matches and allows clearing selection.
 *
 * Session 35 - Phase 1 Property Quadrants Implementation
 */

interface PartialMatch {
  config: ConfigMetadata
  matchingProps: string[]
  matchScore: number
}

interface Props {
  partialMatches: PartialMatch[]
  selectedPropertiesCount: number
  currentLanguage: SupportedLanguage
}

const props = defineProps<Props>()

const emit = defineEmits<{
  clearSelection: []
  selectConfig: [configId: string]
}>()

// Property colors (should match ConfigTile and PropertyCanvas)
const propertyColors: Record<string, string> = {
  chill: '#9b87f5',
  chaotic: '#9b87f5',
  narrative: '#60a5fa',
  algorithmic: '#60a5fa',
  facts: '#f87171',
  emotion: '#f87171',
  historical: '#fb923c',
  contemporary: '#fb923c',
  explore: '#4ade80',
  create: '#4ade80',
  playful: '#fbbf24',
  serious: '#fbbf24'
}

function getPropertyColor(property: string): string {
  return propertyColors[property] || '#888'
}

function handleClearSelection() {
  emit('clearSelection')
}

function handleSuggestionClick(configId: string) {
  emit('selectConfig', configId)
}
</script>

<style scoped>
.no-match-state {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(10, 10, 10, 0.6);
  backdrop-filter: blur(4px);
  z-index: 200;
  pointer-events: none;
}

.no-match-content {
  max-width: 400px;
  padding: 30px;
  text-align: center;
  pointer-events: all;
}

.no-match-icon {
  font-size: 64px;
  margin-bottom: 12px;
  opacity: 0.9;
}

.no-match-title {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
  text-transform: lowercase;
}

.no-match-message {
  margin: 0 0 24px 0;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.5;
}

/* Suggestions */
.suggestions {
  margin-bottom: 32px;
  text-align: left;
}

.suggestions-title {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 600;
  color: #ffffff;
}

.suggestions-subtitle {
  margin: 0 0 16px 0;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
}

.suggestions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.suggestion-item {
  padding: 16px;
  background: rgba(30, 30, 30, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.suggestion-item:hover {
  background: rgba(40, 40, 40, 0.9);
  border-color: rgba(255, 255, 255, 0.3);
  transform: scale(1.02);
}

.suggestion-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.suggestion-name {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
}

.suggestion-score {
  padding: 4px 10px;
  background: rgba(100, 100, 255, 0.2);
  border: 1px solid rgba(100, 100, 255, 0.4);
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  color: #60a5fa;
}

.suggestion-description {
  margin: 0 0 12px 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.5;
}

.suggestion-properties {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.matching-property {
  padding: 4px 10px;
  font-size: 11px;
  border-radius: 12px;
  background: var(--tag-color);
  color: #0a0a0a;
  font-weight: 600;
}

/* Actions */
.no-match-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}

.action-button {
  padding: 8px 20px;
  font-size: 13px;
  font-weight: 500;
  border: none;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-transform: lowercase;
}

.action-button.reset {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.action-button.reset:hover {
  background: rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.8);
  border-color: rgba(255, 255, 255, 0.3);
}
</style>
