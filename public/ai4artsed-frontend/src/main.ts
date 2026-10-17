// The platform's one typeface. Carried as a dependency and served from this
// build, so nothing is fetched from anywhere at runtime — a workshop machine
// without a line out still reads in Source Sans 3, and no request about who is
// reading leaves it. The variable file covers weight 200-900 in one go.
import '@fontsource-variable/source-sans-3'
import '@fontsource-variable/source-sans-3/wght-italic.css'

import './assets/main.css'
import './assets/shell.css'
import './assets/instrument-surface.css'
import './assets/compare-stage.css'
import './assets/flow-stage.css'
import './assets/crossmodal-stage.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import i18n from './i18n'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(i18n)

// Initialize global user preferences and sync with i18n
// Must be done after pinia and i18n are installed
import { useUserPreferencesStore } from './stores/userPreferences'
import { useSafetyLevelStore } from './stores/safetyLevel'
import { getLanguageDir } from './i18n'
import { installExampleAccept } from './composables/exampleAccept'
import { watch } from 'vue'

const userPreferences = useUserPreferencesStore()

// Fetch safety level for feature gating (non-blocking)
const safetyLevelStore = useSafetyLevelStore()
safetyLevelStore.fetchLevel()

// Initial sync with vue-i18n + document direction
i18n.global.locale.value = userPreferences.language
document.documentElement.setAttribute('lang', userPreferences.language)
document.documentElement.setAttribute('dir', getLanguageDir(userPreferences.language))

// Watch for language changes and sync with i18n + document direction
watch(
  () => userPreferences.language,
  (newLanguage) => {
    i18n.global.locale.value = newLanguage
    document.documentElement.setAttribute('lang', newLanguage)
    document.documentElement.setAttribute('dir', getLanguageDir(newLanguage))
    console.log(`[i18n] Language synced to: ${newLanguage} (dir: ${getLanguageDir(newLanguage)})`)
  }
)

installExampleAccept()

app.mount('#app')
