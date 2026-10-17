<template>
  <div id="app" :style="figureTintStyle">
    <!-- Header with Mode Selection -->
    <header class="app-header">
      <div class="header-content">
        <div class="header-left">
          <a href="https://www.ucdcae.fau.de/" target="_blank" rel="noopener noreferrer" class="header-logo-link">
            <img src="/logos/unesco_chair.png" alt="UNESCO Chair" class="header-logo" />
          </a>
          <span class="app-title"><span style="color:#667eea">U</span><span style="color:#e91e63">C</span><span style="color:#7C4DFF">D</span><span style="color:#FF6F00">C</span><span style="color:#4CAF50">A</span><span style="color:#00BCD4">E</span> <span style="color:#667eea">A</span><span style="color:#e91e63">I</span> <span style="color:#7C4DFF">L</span><span style="color:#FF6F00">A</span><span style="color:#4CAF50">B</span></span>
        </div>

        <div class="header-center">
          <!-- The mode selector is never gated by what the platform is doing.
               It was, from 2026-03-22 until 2026-08-15: every button here was
               set to pointer-events:none while a generation ran, on the idea
               that a device may hold one inference at a time. That is the GPU
               service's business and the backend's per-device slot, both of
               which already refuse a second run and say so. Up here it only
               ever produced a dead menu — and, because the settings and
               language links were exempt, a room somebody could walk into and
               not back out of. Nothing in this header may depend on run state
               again: a flag that can be left standing must not be able to take
               the way out with it. -->
          <div class="mode-selector">
            <router-link to="/" class="mode-button" active-class="active">
              <span class="mode-icon">
                <svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
                  <path d="M240-200h120v-240h240v240h120v-360L480-740 240-560v360Zm-80 80v-480l320-240 320 240v480H520v-240h-80v240H160Zm320-350Z"/>
                </svg>
              </span>
            </router-link>
            <router-link to="/together" class="mode-button" active-class="active" :title="$t('resona.title')">
              <span class="mode-icon">
                <svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
                  <path d="M40-160v-160q0-34 23.5-57t56.5-23h131q20 0 38 10t29 27q29 39 71.5 61t90.5 22q49 0 91.5-22t70.5-61q13-17 30.5-27t36.5-10h131q34 0 57 23t23 57v160H640v-91q-35 25-75.5 38T480-200q-43 0-84-13.5T320-252v92H40Zm440-160q-38 0-72-17.5T351-386q-17-25-42.5-39.5T253-440q22-37 93-58.5T480-520q63 0 134 21.5t93 58.5q-29 0-55 14.5T609-386q-22 32-56 49t-73 17ZM160-440q-50 0-85-35t-35-85q0-51 35-85.5t85-34.5q51 0 85.5 34.5T280-560q0 50-34.5 85T160-440Zm640 0q-50 0-85-35t-35-85q0-51 35-85.5t85-34.5q51 0 85.5 34.5T920-560q0 50-34.5 85T800-440ZM480-560q-50 0-85-35t-35-85q0-51 35-85.5t85-34.5q51 0 85.5 34.5T600-680q0 50-34.5 85T480-560Z"/>
                </svg>
              </span>
            </router-link>
            <router-link to="/contesting" class="mode-button" active-class="active" :title="$t('persona.title')">
              <span class="mode-icon">
                <svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
                  <path d="M160-360q-50 0-85-35t-35-85q0-50 35-85t85-35v-80q0-33 23.5-56.5T240-760h120q0-50 35-85t85-35q50 0 85 35t35 85h120q33 0 56.5 23.5T800-680v80q50 0 85 35t35 85q0 50-35 85t-85 35v160q0 33-23.5 56.5T720-120H240q-33 0-56.5-23.5T160-200v-160Zm200-80q25 0 42.5-17.5T420-500q0-25-17.5-42.5T360-560q-25 0-42.5 17.5T300-500q0 25 17.5 42.5T360-440Zm240 0q25 0 42.5-17.5T660-500q0-25-17.5-42.5T600-560q-25 0-42.5 17.5T540-500q0 25 17.5 42.5T600-440ZM320-280h320v-80H320v80Zm-80 80h480v-480H240v480Zm240-240Z"/>
                </svg>
              </span>
            </router-link>
            <router-link to="/x2x-flow" class="mode-button" active-class="active" :title="$t('x2xFlow.modeTitle')">
              <span class="mode-icon">
                <svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
                  <path d="M750-614q-27 27-62 41t-70 14q-35 0-69-13.5T488-614l-75-75q-15-15-34-22.5t-39-7.5q-20 0-39 7.5T267-689l-75 75-57-57 75-75q27-27 61-40.5t69-13.5q35 0 68.5 13.5T469-746l75 75q16 16 35 23.5t39 7.5q20 0 39.5-7.5T693-671l75-75 57 57-75 75Zm0 200q-27 27-61.5 40.5T619-360q-35 0-69.5-13.5T488-414l-75-75q-15-15-34-22.5t-39-7.5q-20 0-39 7.5T267-489l-75 75-57-56 75-76q27-27 61-40.5t69-13.5q35 0 68.5 13.5T469-546l75 75q16 16 35 23.5t39 7.5q20 0 39.5-7.5T693-471l75-75 57 57-75 75Zm-1 200q-27 27-61 40.5T619-160q-35 0-69.5-13.5T488-214l-76-75q-15-15-34-22.5t-39-7.5q-20 0-39 7.5T266-289l-75 75-56-56 75-76q27-27 61-40.5t69-13.5q35 0 68.5 13.5T469-346l75 75q16 16 35.5 23.5T619-240q20 0 39-7.5t35-23.5l75-75 56 57-75 75Z"/>
                </svg>
              </span>
            </router-link>
            <router-link to="/latent-lab" class="mode-button" :class="{ active: $route.path.startsWith('/latent-lab') || $route.path === '/direct' }" title="Latent Lab">
              <span class="mode-icon">
                <svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24" fill="currentColor">
                  <path d="M200-120v-80h200v-80q-83 0-141.5-58.5T200-480q0-61 33.5-111t90.5-73q8-34 35.5-55t62.5-21l-22-62 38-14-14-36 76-28 12 38 38-14 110 300-38 14 14 38-76 28-12-38-38 14-24-66q-15 14-34.5 21t-39.5 5q-22-2-41-13.5T338-582q-27 16-42.5 43T280-480q0 50 35 85t85 35h320v80H520v80h240v80H200Zm346-458 36-14-68-188-38 14 70 188Zm-126-22q17 0 28.5-11.5T460-640q0-17-11.5-28.5T420-680q-17 0-28.5 11.5T380-640q0 17 11.5 28.5T420-600Zm126 22Zm-126-62Zm0 0Z"/>
                </svg>
              </span>
            </router-link>
            <router-link to="/canvas" class="mode-button" active-class="active" title="Canvas Workflow">
              <span class="mode-icon">
                <svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 0 24 24" width="24" fill="currentColor">
                  <path d="M22 11V3h-7v3H9V3H2v8h7V8h2v10h4v3h7v-8h-7v3h-2V8h2v3z"/>
                </svg>
              </span>
            </router-link>
          </div>
        </div>

        <div class="header-right">
          <nav class="header-nav-links">
            <button @click="openDokumentation" class="nav-link" :title="$t('nav.docs')">
              <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                <path d="M478-240q21 0 35.5-14.5T528-290q0-21-14.5-35.5T478-340q-21 0-35.5 14.5T428-290q0 21 14.5 35.5T478-240Zm-36-154h74q0-33 7.5-52t42.5-52q26-26 41-49.5t15-56.5q0-56-41-86t-97-30q-57 0-92.5 30T342-618l66 26q5-18 22.5-39t53.5-21q32 0 48 17.5t16 38.5q0 20-12 37.5T506-526q-44 39-54 59t-10 73Zm38 314q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm0-80q134 0 227-93t93-227q0-134-93-227t-227-93q-134 0-227 93t-93 227q0 134 93 227t227 93Zm0-320Z"/>
              </svg>
            </button>
            <button class="nav-link" :title="$t('nav.settings')" @click="showSettings = true">
              <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                <path d="m370-80-16-128q-13-5-24.5-12T307-235l-119 50L78-375l103-78q-1-7-1-13.5v-27q0-6.5 1-13.5L78-585l110-190 119 50q11-8 23-15t24-12l16-128h220l16 128q13 5 24.5 12t22.5 15l119-50 110 190-103 78q1 7 1 13.5v27q0 6.5-2 13.5l103 78-110 190-118-50q-11 8-23 15t-24 12L590-80H370Zm70-80h79l14-106q31-8 57.5-23.5T639-327l99 41 39-68-86-65q5-14 7-29.5t2-31.5q0-16-2-31.5t-7-29.5l86-65-39-68-99 42q-22-23-48.5-38.5T533-694l-13-106h-79l-14 106q-31 8-57.5 23.5T321-633l-99-41-39 68 86 64q-5 15-7 30t-2 32q0 16 2 31t7 30l-86 65 39 68 99-42q22 23 48.5 38.5T427-266l13 106Zm42-180q58 0 99-41t41-99q0-58-41-99t-99-41q-59 0-99.5 41T342-480q0 58 40.5 99t99.5 41Zm-2-140Z"/>
              </svg>
            </button>
            <div class="lang-dropdown" ref="langDropdownRef">
              <button @click="langMenuOpen = !langMenuOpen" class="nav-link lang-toggle" :title="$t('nav.language')">
                {{ currentLanguage.toUpperCase() }} <span class="lang-caret">&#9662;</span>
              </button>
              <div v-if="langMenuOpen" class="lang-menu">
                <button
                  v-for="lang in SUPPORTED_LANGUAGES"
                  :key="lang.code"
                  class="lang-option"
                  :class="{ active: currentLanguage === lang.code }"
                  @click="selectLanguage(lang.code)"
                >
                  {{ lang.label }}
                </button>
              </div>
            </div>
            <!-- The voice, on or off, for everything that speaks here. -->
            <button
              class="nav-link voice-toggle"
              :class="{ off: !userPreferences.voiceChat }"
              :title="userPreferences.voiceChat ? $t('nav.voiceOff') : $t('nav.voiceOn')"
              :aria-label="userPreferences.voiceChat ? $t('nav.voiceOff') : $t('nav.voiceOn')"
              :aria-pressed="userPreferences.voiceChat"
              @click="toggleVoiceChat"
            >
              <svg v-if="userPreferences.voiceChat" xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                <path d="M240-520h60v-80h-60v80Zm100 80h60v-240h-60v240Zm110 80h60v-400h-60v400Zm110-80h60v-240h-60v240Zm100-80h60v-80h-60v80ZM80-80v-720q0-33 23.5-56.5T160-880h640q33 0 56.5 23.5T880-800v480q0 33-23.5 56.5T800-240H240L80-80Zm126-240h594v-480H160v525l46-45Zm-46 0v-480 480Z"/>
              </svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 -960 960 960" width="20" fill="currentColor">
                <path d="m828-246-74-74h46v-480H274l-80-80h606q33 0 56.5 23.5T880-800v480q0 26-14.5 45.5T828-246Zm-8 218L606-240H240L80-80v-688l-52-52 56-56L876-84l-56 56ZM344-504Zm170-56ZM160-688v413l46-45h322L160-688Zm80 168v-80h60v80h-60Zm100 80v-180l60 60v120h-60Zm110 80v-150l60 60v90h-60Zm60-204-60-60v-136h60v196Zm110 110-60-60v-166h60v226Zm40-66v-80h60v80h-60Z"/>
              </svg>
            </button>
            <div class="legal-dropdown" ref="legalDropdownRef">
              <button @click="legalMenuOpen = !legalMenuOpen" class="nav-link nav-link-text" :title="$t('nav.impressum')">
                §
              </button>
              <div v-if="legalMenuOpen" class="legal-menu">
                <button class="legal-option" @click="openImpressum">{{ $t('nav.impressum') }}</button>
                <button class="legal-option" @click="openDatenschutz">{{ $t('nav.privacy') }}</button>
              </div>
            </div>
            <div class="bg-dropdown" ref="bgDropdownRef">
              <button @click="bgMenuOpen = !bgMenuOpen" class="nav-link bg-toggle" :title="$t('nav.background')">
                <span class="bg-swatch" :style="{ background: userPreferences.currentTint().base }"></span>
                <span class="lang-caret">&#9662;</span>
              </button>
              <div v-if="bgMenuOpen" class="bg-menu">
                <div class="bg-grid">
                  <span class="bg-grid-corner">{{ $t('backgroundTint.darkness') }}</span>
                  <span v-for="h in BACKGROUND_HUES" :key="h.id" class="bg-grid-head">
                    {{ $t(`backgroundTint.hue.${h.id}`) }}
                  </span>

                  <span class="bg-grid-label">{{ $t('backgroundTint.level.pure') }}</span>
                  <button
                    class="bg-cell bg-cell-wide"
                    :class="{ active: userPreferences.backgroundTint === 'pure' }"
                    :style="{ background: findTint('pure').base }"
                    :title="$t('backgroundTint.level.pure')"
                    @click="selectBackgroundTint('pure')"
                  ></button>

                  <template v-for="level in BACKGROUND_LEVELS" :key="level.id">
                    <span class="bg-grid-label">{{ $t(`backgroundTint.level.${level.id}`) }}</span>
                    <button
                      v-for="tint in tintsOfLevel(level.id)"
                      :key="tint.id"
                      class="bg-cell"
                      :class="{ active: userPreferences.backgroundTint === tint.id }"
                      :style="{ background: tint.base }"
                      :title="`${$t(`backgroundTint.level.${level.id}`)} · ${$t(`backgroundTint.hue.${tint.hueId}`)}`"
                      @click="selectBackgroundTint(tint.id)"
                    ></button>
                  </template>
                </div>
              </div>
            </div>
            <!-- The standing conditions of the session, at the far end of the
                 row: what the card draws and what it costs, the DSGVO setting
                 and the filter that holds. The fields are operated, this is
                 only read — so it closes the row rather than opening it. -->
            <PolicyChips />
          </nav>
        </div>
      </div>
    </header>

    <div class="app-content">
      <router-view />
    </div>

    <!-- The one mask. Which agent it is, and what it is called, come from the
         route table below — never from the overlay's own idea of itself. -->
    <ChatOverlay :figure-label="t('figure.help')" />
    <FooterGallery v-if="route.path !== '/'" />

    <!-- Global overlays -->
    <ModelInstallToast />
    <PlaceSignInEnded />

    <!-- Modals -->
    <!-- The settings, as a layer over whatever page is open:
         the page keeps its state, and closing the layer is standing on it
         again. Full size, because the settings' tables have the width of a
         page; they bring their own head, so the frame draws none. -->
    <OverlayFrame v-model="showSettings" size="full">
      <div class="settings-layer">
        <SettingsView @close="showSettings = false" />
      </div>
    </OverlayFrame>
    <DokumentationModal v-model="showDokumentation" />
    <ImpressumModal v-model="showImpressum" />
    <DatenschutzModal v-model="showDatenschutz" />
  </div>
</template>

<script setup lang="ts">
/**
 * App.vue - Main application component
 *
 * Uses Vue Router to render different views:
 * - / (home): Legacy execution interface
 * - /select: Phase 1 Property Quadrants selection interface
 * - /about: About page
 *
 * ChatOverlay is mounted here as a global component for interactive LLM help.
 */
import { computed, defineAsyncComponent, ref, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { STALE_CHUNK } from './router'
import ChatOverlay from './components/ChatOverlay.vue'
import OverlayFrame from './components/OverlayFrame.vue'
import FooterGallery from './components/FooterGallery.vue'
import ModelInstallToast from './components/ModelInstallToast.vue'
import PlaceSignInEnded from './components/PlaceSignInEnded.vue'
import DokumentationModal from './components/DokumentationModal.vue'
import ImpressumModal from './components/ImpressumModal.vue'
import DatenschutzModal from './components/DatenschutzModal.vue'
import PolicyChips from './components/PolicyChips.vue'
import {
  useUserPreferencesStore,
  BACKGROUND_TINTS,
  BACKGROUND_LEVELS,
  BACKGROUND_HUES,
  findTint
} from './stores/userPreferences'
import { useSafetyLevelStore } from './stores/safetyLevel'
import { useUiModeStore } from './stores/uiMode'
import { SUPPORTED_LANGUAGES, type SupportedLanguage } from './i18n'
import { primeSpeech } from './composables/useSpeech'

// Loaded when the layer opens, as the route loaded it before: the settings
// and their tabs are not part of every page's bundle. A window opened before
// a build asks for a piece that is no longer there (router/index.ts,
// STALE_CHUNK); the layer would open empty and say nothing. So, as the router
// does for a page, the window fetches itself anew, once, at the address of
// the settings — the same mark the router sets and clears.
const SettingsView = defineAsyncComponent({
  loader: () => import('./views/SettingsView.vue'),
  onError(error, _retry, fail) {
    const mark = 'router-reload:/settings'
    if (STALE_CHUNK.test(String(error?.message ?? error)) && !sessionStorage.getItem(mark)) {
      sessionStorage.setItem(mark, '1')
      window.location.assign('/settings')
      return
    }
    fail()
  },
})

const { locale, t } = useI18n()
const safetyStore = useSafetyLevelStore()
if (!safetyStore.loaded) safetyStore.fetchLevel()
const uiModeStore = useUiModeStore()
if (!uiModeStore.loaded) uiModeStore.fetchMode()
const route = useRoute()
const router = useRouter()

/**
 * The settings are a layer, not a page (since 2026-09-17). The gear opens it
 * over whatever is on screen. The address /settings still works — bookmarks
 * and handouts carry it — and opens the same layer over the start page; closing
 * it there takes the address back to /. A navigation from inside the layer
 * (the two dev pages in the tab "Minigame Demo") leaves the layer behind, so
 * the layer goes with it. The password prompt cancelled closes it too: without
 * the password there is nothing in it.
 */
const showSettings = ref(false)
watch(() => route.name, (name) => {
  if (name === 'settings') showSettings.value = true
}, { immediate: true })
watch(() => route.fullPath, () => {
  if (route.name !== 'settings') showSettings.value = false
})
watch(showSettings, (open) => {
  if (!open && route.name === 'settings') router.replace('/')
})

/**
 * THE ONE MASK ON A PAGE IS HELP. On every page, without exception.
 *
 * Two routes had claimed it for themselves: the workshop and the contesting
 * surface each declared the mask to BE their agent, so a click on it went to
 * that agent and the help panel did not exist there. That is over: the masks
 * are the normal help mask, help shows the start text as on every page, and
 * both agents appear only through what they do on the page, as text, voice
 * and items.
 *
 * So there is nothing left to decide per route, and no table: an agent is what
 * it does on the page, and a figure standing for it in the corner is a second,
 * emptier claim about the same thing. The pigments and their material names
 * live in assets/base.css.
 */
const figureTintStyle = computed(() => ({ '--figure-tint': 'var(--figure-tint-blueprint)' }))

const userPreferences = useUserPreferencesStore()
const currentLanguage = computed(() => locale.value)
const showDokumentation = ref(false)
const showImpressum = ref(false)
const showDatenschutz = ref(false)

// Language dropdown
const langMenuOpen = ref(false)
const langDropdownRef = ref<HTMLElement | null>(null)

// Background tone dropdown
const bgMenuOpen = ref(false)
const bgDropdownRef = ref<HTMLElement | null>(null)

// Legal dropdown
const legalMenuOpen = ref(false)
const legalDropdownRef = ref<HTMLElement | null>(null)

function selectLanguage(code: SupportedLanguage) {
  userPreferences.setLanguage(code)
  langMenuOpen.value = false
}

function selectBackgroundTint(id: string) {
  userPreferences.setBackgroundTint(id)
  bgMenuOpen.value = false
}

/**
 * Turn the voice on or off for this machine.
 *
 * Turning it ON spends the click: browsers only let audio play from a human
 * gesture, and this IS one. Without that, the first answer that wanted to be
 * spoken would be refused and would wait for a second click nobody knows to
 * make.
 */
function toggleVoiceChat() {
  const turningOn = !userPreferences.voiceChat
  userPreferences.setVoiceChat(turningOn)
  if (turningOn) primeSpeech()
}

function tintsOfLevel(levelId: string) {
  return BACKGROUND_TINTS.filter(t => t.levelId === levelId)
}

function handleClickOutside(e: MouseEvent) {
  if (langDropdownRef.value && !langDropdownRef.value.contains(e.target as Node)) {
    langMenuOpen.value = false
  }
  if (bgDropdownRef.value && !bgDropdownRef.value.contains(e.target as Node)) {
    bgMenuOpen.value = false
  }
  if (legalDropdownRef.value && !legalDropdownRef.value.contains(e.target as Node)) {
    legalMenuOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))

function openDokumentation() {
  showDokumentation.value = true
}

function openImpressum() {
  showImpressum.value = true
  legalMenuOpen.value = false
}

function openDatenschutz() {
  showDatenschutz.value = true
  legalMenuOpen.value = false
}

</script>

<style>
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body {
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  overflow: auto;
  font-family: var(--font-sans);
  background: var(--bg-base);
}

#app {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Header */
.app-header {
  /* Both outer edges of the header keep the same distance from the window, and
     that distance is the width of the UNESCO logo (38px at its 28px height).
     The content box stops growing at 1400px, so beyond that width air opens up
     beside it: the two outer elements are carried through exactly that air, plus
     the box's own 1rem, minus the distance they are to keep. The term never goes
     below zero — where the window is too narrow to hold the full distance, the
     distance shrinks with it instead of pulling the chips into the row. Both
     sides read the same term, so they are equal at every width. */
  --header-edge: 2.4rem;
  --header-edge-shift: max(0px, calc((100vw - 1400px) / 2 + 1rem - var(--header-edge)));
  background: rgb(var(--bg-base-rgb) / 0.97);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding: 0.5rem 0;
  z-index: 1000;
  flex-shrink: 0;
}

.header-content {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 1rem;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  justify-content: flex-start;
  /* The picture is what has to line up with the chips on the other side, and the
     logo link carries 3px of padding around it — hence the 3px on top. */
  position: relative;
  inset-inline-start: calc(-1 * (var(--header-edge-shift) + 3px));
}

.header-logo-link {
  display: flex;
  align-items: center;
  opacity: 0.85;
  transition: opacity 0.2s;
}

.header-logo-link:hover {
  opacity: 1;
}

.header-logo {
  height: 28px;
  width: auto;
  border-radius: 3px;
}

.header-logo-round {
  border-radius: 50%;
}

.header-center {
  display: flex;
  justify-content: center;
}

.mode-selector {
  display: flex;
  gap: 0.25rem;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 0.25rem;
}

.mode-button {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  background: transparent;
  border: 2px solid transparent;
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.6);
  text-decoration: none;
  cursor: pointer;
  transition: all 0.3s ease;
  min-width: 60px;
}

.mode-button:hover {
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.9);
}

.mode-button.active {
  background: rgba(76, 175, 80, 0.15);
  border-color: rgba(76, 175, 80, 0.5);
  color: #4CAF50;
}

.mode-icon {
  font-size: 1.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mode-icon svg {
  width: 24px;
  height: 24px;
}

.header-right {
  display: flex;
  justify-content: flex-end;
}

.app-title {
  font-size: 1.2rem;
  font-weight: 700;
  letter-spacing: 2px;
  white-space: nowrap;
  margin-right: 1.5rem;
}

/* Header Right Reorganization */
.header-right {
  display: flex;
  align-items: center;
}

/* Navigation Links */
/* The meta row belongs to the right edge of the WINDOW, not to the right edge
   of the 1400px content box: it carries the same distance as the logo on the
   left, see --header-edge above. The whole row moves, chips and fields
   together — carrying only the chips out left a hole between the paragraph
   sign and them that grew with every pixel of window width. The offset is a
   relative one, so the row's box stays where the grid put it and the mode
   selector in the middle does not move. The logical property carries the
   mirror image for he/ar with it. */
.header-nav-links {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  position: relative;
  inset-inline-end: calc(-1 * var(--header-edge-shift));
}

.nav-link {
  display: flex;
  align-items: center;
  justify-content: center;
  /* Square by default: the same distance on all four sides, and a floor that
     makes a 20px glyph sit in a square. Wider only where the content does not
     fit a square (the language field, the tone field). */
  padding: 0.4rem;
  min-width: 2.2rem;
  min-height: 2.2rem;
  box-sizing: border-box;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.6);
  text-decoration: none;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.3s ease;
  min-width: 32px;
  height: 32px;
}

.nav-link svg {
  width: 20px;
  height: 20px;
}

/* Silenced: the crossed icon already says it, and this says it at a glance. */
.voice-toggle.off {
  color: rgba(255, 255, 255, 0.35);
}

.nav-link:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.9);
}

.nav-link.router-link-active {
  color: #4CAF50;
  border-color: rgba(76, 175, 80, 0.3);
}

.lang-dropdown {
  position: relative;
}

.lang-toggle {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.5px;
  gap: 0.2rem;
}

.lang-caret {
  font-size: 0.55rem;
  opacity: 0.5;
}

.lang-menu {
  position: absolute;
  top: 100%;
  inset-inline-end: 0;
  margin-top: 0.25rem;
  background: var(--surface-2);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  overflow: hidden;
  z-index: 1001;
  min-width: 120px;
}

.lang-option {
  display: block;
  width: 100%;
  padding: 0.5rem 0.75rem;
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.8rem;
  text-align: start;
  cursor: pointer;
  transition: background 0.15s;
}

.lang-option:hover {
  background: rgba(255, 255, 255, 0.08);
}

.lang-option.active {
  color: #4CAF50;
}

.bg-dropdown {
  position: relative;
}

.bg-toggle {
  gap: 0.25rem;
}

.bg-menu {
  position: absolute;
  top: 100%;
  inset-inline-end: 0;
  margin-top: 0.25rem;
  background: var(--surface-3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  z-index: 1001;
  padding: 0.6rem;
}

.bg-grid {
  display: grid;
  grid-template-columns: auto repeat(3, 34px);
  gap: 5px;
  align-items: center;
}

.bg-grid-corner,
.bg-grid-head,
.bg-grid-label {
  font-size: 0.62rem;
  color: rgba(255, 255, 255, 0.45);
  white-space: nowrap;
}

.bg-grid-head {
  text-align: center;
}

.bg-grid-label {
  text-align: end;
  padding-inline-end: 0.25rem;
}

.bg-cell {
  height: 22px;
  padding: 0;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 4px;
  cursor: pointer;
  transition: border-color 0.15s;
}

.bg-cell:hover {
  border-color: rgba(255, 255, 255, 0.5);
}

.bg-cell.active {
  border-color: #4CAF50;
  box-shadow: 0 0 0 1px #4CAF50;
}

.bg-cell-wide {
  grid-column: span 3;
}

.bg-swatch {
  display: inline-block;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.35);
  flex-shrink: 0;
}

/* The paragraph sign is one narrow glyph, not a word: it takes the same
   padding as every other field, and its box follows the glyph instead of the
   32-px floor that exists so a 20-px icon sits in a square. Both together are
   what keeps the distance to its neighbours the same as everywhere else. */
.nav-link-text {
  padding: 0.4rem;
  min-width: 0;
  font-size: 0.85rem;
  text-align: center;
}

.legal-dropdown {
  position: relative;
}

.legal-menu {
  position: absolute;
  top: 100%;
  inset-inline-end: 0;
  margin-top: 0.25rem;
  background: var(--surface-2);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  overflow: hidden;
  z-index: 1001;
  min-width: 140px;
}

.legal-option {
  display: block;
  width: 100%;
  padding: 0.5rem 0.75rem;
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.8rem;
  text-align: start;
  cursor: pointer;
  transition: background 0.15s;
}

.legal-option:hover {
  background: rgba(255, 255, 255, 0.08);
}

/* Content Area */
.app-content {
  flex: 1;
  overflow: auto;
}

/* Responsive */

@media (max-width: 768px) {
  .app-header {
    padding: 0.5rem 1rem;
  }

  .header-content {
    grid-template-columns: auto 1fr auto;
    gap: 0.5rem;
  }

  .header-left,
  .header-center,
  .header-right {
    justify-content: center;
  }

  .app-title {
    font-size: 0.65rem;
    letter-spacing: 1px;
  }

  .mode-button {
    padding: 0.4rem 0.8rem;
    min-width: 50px;
  }

  .mode-icon {
    font-size: 1.25rem;
  }

  .header-nav-links {
    gap: 0.25rem;
    padding-inline-start: 0.5rem;
  }

  .nav-link {
    padding: 0.3rem 0.5rem;
    font-size: 0.8rem;
    min-width: 28px;
    height: 28px;
  }

}
/* The settings inside the layer: the frame is a column, this is the part of
   it that scrolls. The scrollbar is this element's, so the dark scheme the
   settings declare for their own controls is declared here as well. */
.settings-layer {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  color-scheme: dark;
}
</style>
