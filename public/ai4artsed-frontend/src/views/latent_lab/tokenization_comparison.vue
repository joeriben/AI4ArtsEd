<!--
  Tokenisierung im Sprachvergleich.

  Die Karte „Tokenisierung und Embedding" der Überblickskarte zeigt als Exkurs,
  dass derselbe Satz auf Koreanisch mehr als doppelt so viele Token braucht wie
  auf Englisch und dass „Haus" in acht von zehn Sprachen EIN Token ist, auf
  Bulgarisch und Ukrainisch drei. Die Karte behauptet das; hier kann man es mit
  dem eigenen Satz und dem eigenen Wort nachprüfen.

  Drei Blöcke, in der Reihenfolge, in der die Frage entsteht:

  1. Der eigene Satz, zerlegt — Chips mit Platznummern, die Anzahl, der
     Wortschatz des Tokenizers und wie viel des Fensters der Satz füllt.
  2. Derselbe Satz in den zehn Sprachen der Plattform, eine Zeile je Sprache.
     Die Sprache der Oberfläche steht abgesetzt: die Frage ist „und meine?".
  3. Ein einzelnes Wort in denselben zehn Sprachen. Hier wird die
     Ungleichbehandlung greifbar, weil ein Feld gegen drei steht.

  Der Tokenizer ist wählbar, und CLIP steht mit in der Liste: sein Fenster ist
  77 Token breit gegen die 40.960 des Textmodells. Wer sieht, dass sein Satz auf
  Koreanisch 34 statt 16 Token braucht, sieht an CLIP, was das kostet.

  Es läuft nichts auf der Grafikkarte. Die Zerlegung liest eine Vokabeldatei;
  Zeit braucht allein das Übersetzen, und das ist derselbe Weg, den
  „KI-Sprachverständnis" geht (`/api/schema/pipeline/translate`).
-->
<template>
  <div class="tkc">
    <ShellRun
      :ready="canRun && !busy"
      :running="busy"
      :label="t('latentLab.textLab.tokens.runLabel')"
      :count="done"
      :total="LANGS.length"
      @run="runComparison"
    />

    <div class="lab-main">
      <div class="lab-stage">
        <div class="lab-work" :class="{ folded }">
          <!-- Links: was gefragt wird. -->
          <section class="lab-col tkc-ask col-fold-host" :class="{ folded }">
            <ColumnFold v-model:folded="folded" />

            <div class="tkc-field">
              <PromptExamples
                :items="promptExamples"
                :current="sentence"
                :disabled="busy"
                @pick="applyExample"
              />
              <MediaInputBox
                chrome="bare"
                v-model:value="sentence"
                input-type="text"
                :rows="3"
                resize-type="auto"
                :disabled="busy"
                @copy="copySentence"
                @paste="pasteSentence"
                @clear="clearSentence"
              />
            </div>

            <div class="tkc-field">
              <label class="lab-pick-label" for="tkc-word">
                {{ t('latentLab.textLab.tokens.wordLabel') }}
              </label>
              <input id="tkc-word" v-model="word" class="tkc-input" spellcheck="false" />
            </div>

            <div class="tkc-field">
              <span class="lab-pick-label">
                {{ t('latentLab.textLab.tokens.tokenizerLabel') }}
              </span>
              <p v-if="offline" class="tkc-role">{{ t('latentLab.textLab.tokens.offline') }}</p>
              <div class="tkc-chips">
                <button
                  v-for="tk in tokenizers"
                  :key="tk.id"
                  class="tkc-chip"
                  :class="{ on: tk.id === modelId, off: !tk.available }"
                  :disabled="!tk.available"
                  :title="roleText(tk)"
                  @click="modelId = tk.id"
                >{{ tk.label }}</button>
              </div>
              <p v-if="current" class="tkc-role">{{ roleText(current) }}</p>
            </div>

            <div class="lab-note tkc-note">
              <p v-for="(ln, i) in NOTE" :key="i" class="tkc-note-line">{{ ln }}</p>
            </div>
          </section>

          <!-- Rechts: was dabei herauskommt. -->
          <section class="tkc-out">
            <!-- 1. Der eigene Satz -->
            <div class="tkc-block">
              <h3 class="tkc-head">{{ t('latentLab.textLab.tokens.cutHead') }}</h3>
              <div v-if="cut" class="tkc-cut" :dir="dirOf(uiLang)">
                <TokenChip
                  v-for="(tok, i) in cut.tokens" :key="i"
                  :text="show(tok)" :n="i + 1" :part="tok.part" :join-next="cut.tokens[i + 1]?.part"
                />
              </div>
              <p v-else class="tkc-empty">{{ t('latentLab.textLab.tokens.cutEmpty') }}</p>

              <div v-if="cut" class="tkc-facts">
                <span class="tkc-fact">{{ t('latentLab.textLab.tokens.countLine', { n: fmt(cut.count) }) }}</span>
                <span class="tkc-fact">{{ t('latentLab.textLab.tokens.vocabLine', { n: fmt(cut.vocab) }) }}</span>
                <span v-if="cut.window" class="tkc-fact">
                  {{ t('latentLab.textLab.tokens.windowLine', { n: fmt(cut.window) }) }}
                </span>
              </div>
              <!-- Wie viel des Fensters dieser eine Satz schon einnimmt. Bei
                   Qwen3 ist der Balken unsichtbar schmal, bei CLIP nicht - und
                   genau das ist die Aussage. -->
              <div v-if="cut && cut.window" class="tkc-window">
                <div class="tkc-window-track">
                  <div class="tkc-window-fill" :style="{ width: fillPct + '%' }"></div>
                </div>
                <span class="tkc-window-num">{{ fillLabel }}</span>
              </div>
            </div>

            <!-- 2. Zehn Sprachen, ein Satz -->
            <div class="tkc-block">
              <h3 class="tkc-head">{{ t('latentLab.textLab.tokens.compareHead') }}</h3>
              <p v-if="!rows.length && !busy" class="tkc-empty">
                {{ t('latentLab.textLab.tokens.compareEmpty') }}
              </p>
              <div v-for="r in sortedRows" :key="r.code" class="tkc-row" :class="{ mine: r.code === uiLang }">
                <span class="tkc-lang">{{ r.name }}</span>
                <span class="tkc-bar-cell">
                  <span class="tkc-bar" :style="{ width: barPct(r.sCount) + '%' }"></span>
                </span>
                <span class="tkc-count">{{ r.sCount || '·' }}</span>
                <button class="tkc-more" :title="r.sentence" @click="open = open === r.code ? '' : r.code">
                  {{ open === r.code ? '−' : '+' }}
                </button>
                <div v-if="open === r.code" class="tkc-row-cut">
                  <p class="tkc-row-text" :dir="dirOf(r.code)">{{ r.sentence }}</p>
                  <div class="tkc-cut" :dir="dirOf(r.code)">
                    <TokenChip
                      v-for="(tok, i) in r.sTokens" :key="i"
                      :text="show(tok)" :part="tok.part" :join-next="r.sTokens[i + 1]?.part"
                    />
                  </div>
                </div>
              </div>
            </div>

            <!-- 3. Ein Wort -->
            <div v-if="rows.length" class="tkc-block">
              <h3 class="tkc-head">{{ t('latentLab.textLab.tokens.wordHead', { w: word }) }}</h3>
              <div v-for="r in sortedRows" :key="r.code" class="tkc-wrow" :class="{ mine: r.code === uiLang }">
                <span class="tkc-lang">{{ r.name }}</span>
                <div class="tkc-cut" :dir="dirOf(r.code)">
                  <TokenChip
                    v-for="(tok, i) in r.wTokens" :key="i"
                    :text="show(tok)" :part="tok.part" :join-next="r.wTokens[i + 1]?.part"
                  />
                </div>
                <span class="tkc-count">{{ r.wTokens.length || '·' }}</span>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import ColumnFold from '@/components/ColumnFold.vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import MediaInputBox from '@/components/MediaInputBox.vue'
import PromptExamples from '@/components/PromptExamples.vue'
import { PROMPT_PRESET_KEY } from '@/lib/promptPresets'
import ShellRun from '@/components/ShellRun.vue'
import TokenChip from '@/components/TokenChip.vue'
import { useAppClipboard } from '@/composables/useAppClipboard'
import { SUPPORTED_LANGUAGES } from '@/i18n'
import { ar } from '@/i18n/ar'
import { bg } from '@/i18n/bg'
import { de } from '@/i18n/de'
import { en } from '@/i18n/en'
import { es } from '@/i18n/es'
import { fr } from '@/i18n/fr'
import { he } from '@/i18n/he'
import { ko } from '@/i18n/ko'
import { tr } from '@/i18n/tr'
import { uk } from '@/i18n/uk'
import { useUserPreferencesStore } from '@/stores/userPreferences'
import { postStreamedRun } from '@/services/directRun'
import { apiBase } from '@/services/labApi'

/**
 * Wo ein Standardprompt in jeder der zehn Sprachen steht - direkt in den
 * geladenen Sprachdateien, nicht über die Oberflächen-Sprache. `messageAt`
 * geht denselben Weg, den vue-i18n selbst geht (fallbackLocale: 'en'), nur für
 * eine FREMDE Sprache statt der aktiven. Was hier gelesen wird, muss in allen
 * zehn Sprachdateien stehen - sonst zeigte der Sprachvergleich für die fehlenden
 * das Englische und vergliche Englisch mit Englisch.
 */
const MESSAGES: Record<string, unknown> = { ar, bg, de, en, es, fr, he, ko, tr, uk }

function messageAt(code: string, path: string[]): string | undefined {
  let node: unknown = MESSAGES[code]
  for (const key of path) node = (node as Record<string, unknown> | undefined)?.[key]
  return typeof node === 'string' ? node : undefined
}

/**
 * Die zwei Standardprompts, geführt über den Pfad ihres eigenen Schlüssels.
 *
 * BEIDE Pfade zeigen auf Schlüssel, die bereits in allen zehn Sprachen stehen —
 * das ist die Bedingung dafür, dass ein Standardprompt ohne Modell auskommt.
 * Sie liegen unter `promptExamples.presets`, der zentralen Preset-Quelle aus
 * `lib/promptPresets.ts` (seit dem 2026-09-08; davor unter
 * `latentLab.attention.promptExamples.house`). Der Satz ist wortgleich mit dem,
 * den diese Fläche bis zum 2026-08-27 als eigenen Schlüssel führte, aber im
 * Gegensatz zu jenem in allen zehn Sprachen übersetzt. Der eigene Schlüssel ist
 * damit entfallen: er wäre in acht Sprachen auf das Englische zurückgefallen
 * und hätte den Vergleich an genau der Stelle verfälscht, um die es hier geht.
 */
const PRESET_PATHS: Record<string, string[]> = {
  house: [...PROMPT_PRESET_KEY.split('.'), 'house'],
  street: [...PROMPT_PRESET_KEY.split('.'), 'street'],
}

/**
 * Das Vergleichswort in den zehn Sprachen der Plattform.
 *
 * Das steht hier und nicht in den Sprachdateien, weil es kein Text der
 * Oberfläche ist, sondern der GEGENSTAND der Messung — dieselbe Art Eintrag wie
 * die Token-Zerlegungen auf der Überblickskarte, die aus demselben Grund vom
 * Übersetzen ausgenommen sind: übersetzt würde daraus ein anderes Wort und
 * damit eine andere Messung.
 *
 * Die zehn Wörter sind nicht ausgedacht: es ist das, was
 * `/api/schema/pipeline/translate` am 2026-08-27 für „Haus" zurückgegeben hat,
 * einmal gemessen und dann festgehalten. Neun Modellaufrufe je Lauf für ein
 * Wort, das sich nicht ändert, sind genau die Kosten, von denen der Erklärtext
 * dieser Fläche spricht. Ein SELBST eingetragenes Wort geht weiterhin durch die
 * Übersetzung — dafür ist das Feld da.
 */
const WORD_BY_LANG: Record<string, string> = {
  ar: 'منزل',
  bg: 'Къща',
  de: 'Haus',
  en: 'House',
  es: 'Casa',
  fr: 'Maison',
  he: 'בית',
  ko: '집',
  tr: 'Ev',
  uk: 'Будинок',
}

function presetTextFor(id: string, code: string): string {
  const path = PRESET_PATHS[id]
  if (!path) return ''
  return messageAt(code, path) ?? messageAt('en', path) ?? ''
}

function presetWordFor(code: string): string {
  return WORD_BY_LANG[code] ?? WORD_BY_LANG.en ?? ''
}

type Tok = { s: string; raw: string; id: number; part?: boolean }
type Cut = {
  model_id: string
  label: string
  role: string
  tokens: Tok[]
  count: number
  vocab: number
  matrix: number | null
  window: number | null
}
type TkEntry = { id: string; label: string; role: string; available: boolean; window?: number | null }
type Row = {
  code: string
  name: string
  sentence: string
  sTokens: Tok[]
  sCount: number
  /** Das Wort in dieser Sprache, so wie es zerlegt wurde. */
  wText: string
  wTokens: Tok[]
}

const { t, locale } = useI18n()
const prefs = useUserPreferencesStore()

const LANGS = SUPPORTED_LANGUAGES

const sentence = ref('')
const word = ref('')
const { copy: copyToClipboard, paste: pasteFromClipboard } = useAppClipboard()
function copySentence() { copyToClipboard(sentence.value) }
function pasteSentence() { sentence.value = pasteFromClipboard() }
function clearSentence() { sentence.value = '' }
const modelId = ref('Qwen/Qwen3-4B')
const tokenizers = ref<TkEntry[]>([])
const cut = ref<Cut | null>(null)
const rows = ref<Row[]>([])
const open = ref('')
const busy = ref(false)
const done = ref(0)
/** Kein Tokenizer erreichbar: die Flaeche sagt es, statt leer zu bleiben. */
const offline = ref(false)

const uiLang = computed(() => String(prefs.language || locale.value).slice(0, 2))
const current = computed(() => tokenizers.value.find(k => k.id === modelId.value) ?? null)
const canRun = computed(() => sentence.value.trim().length > 0 && !!current.value?.available)

const NOTE = computed(() => t('latentLab.textLab.tokens.note').split('\n').filter(Boolean))

const promptExamples = computed(() =>
  Object.keys(PRESET_PATHS).map(id => {
    const text = presetTextFor(id, uiLang.value)
    return { id, label: text, fill: [text] }
  }),
)

function applyExample(item: { fill: string[] }) {
  sentence.value = item.fill[0] ?? ''
}

/** Welcher Standardprompt gerade im Feld steht, in der Sprache der Oberfläche
 * gelesen - oder keiner, wenn auch nur ein Zeichen von Hand geändert wurde. */
function matchedPreset(): string | null {
  const text = sentence.value.trim()
  return Object.keys(PRESET_PATHS).find(id => presetTextFor(id, uiLang.value) === text) ?? null
}

/** Steht das Standardwort im Feld, liegt seine Fassung in jeder Sprache vor. */
function isPresetWord(): boolean {
  return word.value.trim() === presetWordFor(uiLang.value)
}

/**
 * Der Wortschatz ist nicht die Zahl der Zeilen in der Eingangstabelle: bei
 * Qwen3-4B hat die Tabelle 151.936 Zeilen, aber nur 151.669 davon sind Token,
 * die der Tokenizer je erzeugt. Gezeigt wird, was er erzeugen kann.
 */
function fmt(n: number | null | undefined): string {
  return typeof n === 'number' ? n.toLocaleString(String(locale.value)) : '–'
}

/** Was auf dem Chip steht: das Stück, wie es sich lesen lässt. */
function show(tok: Tok): string {
  const s = tok.s ?? ''
  // Ein Stück, das nur ein halbes Zeichen ist, hat keine lesbare Form - dann
  // steht da, was im Wortschatz steht, samt der Marke seiner Familie.
  if (!s.trim() && tok.raw) return tok.raw
  if (s.includes('�')) return tok.raw || s
  // Das Leerzeichen vor einem Wort gehört zum Token und ist der Grund, warum
  // „Haus" und „␣Haus" zwei verschiedene sind. Es wird sichtbar gemacht.
  return s.replace(/^ /, '␣').replace(/\n/g, '⏎')
}

function roleText(tk: TkEntry | Cut): string {
  const key = `latentLab.textLab.tokens.roles.${tk.role}`
  const said = t(key)
  return said === key ? '' : said
}

function dirOf(code: string): 'rtl' | 'ltr' {
  return LANGS.find(l => l.code === code)?.dir ?? 'ltr'
}

/** Der längste Balken ist die Sprache mit den meisten Token. */
const maxCount = computed(() => Math.max(1, ...rows.value.map(r => r.sCount)))
function barPct(n: number): number {
  return Math.round((n / maxCount.value) * 100)
}

/** Aufsteigend nach Anzahl - die Reihenfolge IST die Aussage. */
const sortedRows = computed(() => [...rows.value].sort((a, b) => a.sCount - b.sCount))

const fillPct = computed(() => {
  const c = cut.value
  if (!c?.window) return 0
  return Math.min(100, (c.count / c.window) * 100)
})
const fillLabel = computed(() => {
  const c = cut.value
  if (!c?.window) return ''
  const pct = (c.count / c.window) * 100
  return t('latentLab.textLab.tokens.fill', {
    p: pct < 0.1 ? '<0,1' : pct.toFixed(pct < 10 ? 1 : 0),
  })
})

async function post(path: string, body: unknown): Promise<any> {
  try {
    const res = await fetch(`${apiBase()}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return await res.json()
  } catch (e) {
    // Ein Dienst, der diese Strecke nicht kennt, antwortet mit der index.html
    // der Anwendung. Das ist kein JSON, und ein ungefangener Fehler daraus
    // liesse die Flaeche stumm stehen statt zu sagen, was fehlt.
    console.error(`[TOKENS] ${path}:`, e)
    return { error: String(e) }
  }
}

/**
 * `post` for a route that can answer as a stream, and only for those.
 *
 * A translation is one cloud model call, and the edge in front of this server
 * cuts a request whose origin has sent nothing for about 100 seconds. The
 * tokenizer routes below answer at once and stay with `post`.
 *
 * The contract is `post`'s, unchanged: the body whatever the status came back,
 * and `{ error }` in place of a throw, because the loop that calls it reads an
 * answer and never a rejection.
 */
async function postStreamed(path: string, body: Record<string, unknown>): Promise<any> {
  try {
    const res = await postStreamedRun(path, body, {
      baseUrl: apiBase(),
      validateStatus: () => true,
    })
    return res.data
  } catch (e) {
    console.error(`[TOKENS] ${path}:`, e)
    return { error: String(e) }
  }
}

async function loadTokenizers() {
  try {
    const res = await fetch(`${apiBase()}/api/text/tokenizers`)
    const data = await res.json()
    tokenizers.value = data.tokenizers ?? []
    if (!tokenizers.value.some(k => k.id === modelId.value && k.available)) {
      const first = tokenizers.value.find(k => k.available)
      if (first) modelId.value = first.id
    }
  } catch (e) {
    console.error('[TOKENS] tokenizers:', e)
    tokenizers.value = []
  }
  offline.value = !tokenizers.value.some(k => k.available)
}

/** Der eigene Satz, sofort - dafür läuft nichts auf der Karte. */
let cutTimer: number | undefined
async function refreshCut() {
  const text = sentence.value.trim()
  if (!text) { cut.value = null; return }
  const data = await post('/api/text/tokenize', { text, model_id: modelId.value })
  if (data && !data.error) cut.value = data as Cut
}
function scheduleCut() {
  window.clearTimeout(cutTimer)
  cutTimer = window.setTimeout(refreshCut, 220)
}

/**
 * Der Vergleich. Übersetzen kostet Zeit, zerlegen nicht - darum wird je
 * Sprache übersetzt und sofort zerlegt, und die Zeile steht, sobald sie steht.
 * Die eigene Sprache wird NICHT übersetzt: dort steht der Satz, der eingegeben
 * wurde.
 */
async function runComparison() {
  if (busy.value || !canRun.value) return
  busy.value = true
  done.value = 0
  rows.value = []
  open.value = ''
  const text = sentence.value.trim()
  const w = word.value.trim()
  // Ein Standardprompt hat seine Übersetzung schon - dafür ist er ein
  // Standardprompt. Kein Modellaufruf dafür, in keine Sprache; nur ein von Hand
  // geänderter oder eigener Satz und ein eigenes Wort gehen noch übersetzt.
  const preset = matchedPreset()
  const presetWord = isPresetWord()

  for (const lang of LANGS) {
    const row: Row = {
      code: lang.code,
      name: lang.label,
      sentence: text,
      sTokens: [],
      sCount: 0,
      wText: '',
      wTokens: [],
    }
    try {
      if (preset) {
        row.sentence = presetTextFor(preset, lang.code)
      } else if (lang.code !== uiLang.value) {
        const tr = await postStreamed('/api/schema/pipeline/translate', {
          text,
          target_language: lang.code,
        })
        if (tr?.status === 'success' && tr.translated_text) row.sentence = tr.translated_text
      }
      const cutRes = await post('/api/text/tokenize', {
        text: row.sentence,
        model_id: modelId.value,
      })
      if (cutRes && !cutRes.error) {
        row.sTokens = cutRes.tokens
        row.sCount = cutRes.count
      }

      if (w) {
        let wordText = w
        if (presetWord) {
          wordText = presetWordFor(lang.code)
        } else if (lang.code !== uiLang.value) {
          const tw = await postStreamed('/api/schema/pipeline/translate', {
            text: w,
            target_language: lang.code,
          })
          if (tw?.status === 'success' && tw.translated_text) wordText = tw.translated_text
        }
        // Ein Wort steht in einem Satz hinter einem Leerzeichen, und der
        // Tokenizer rechnet dieses Leerzeichen zum Wort. Ohne es zerfällt
        // „Haus" in „H"+„aus" und „Casa" in „C"+„asa" — das wäre eine
        // Eigenschaft der Messung, keine der Sprache. Gemessen wird das Wort
        // deshalb so, wie es im Satz steht.
        row.wText = ' ' + wordText.trim()
        const wRes = await post('/api/text/tokenize', {
          text: row.wText,
          model_id: modelId.value,
        })
        if (wRes && !wRes.error) row.wTokens = wRes.tokens
      }
    } catch (e) {
      console.error(`[TOKENS] ${lang.code}:`, e)
    }
    rows.value = [...rows.value, row]
    done.value += 1
  }
  busy.value = false
}

/** Ein anderer Tokenizer zerlegt anders - alles Gezeigte gilt neu. */
watch(modelId, async () => {
  await refreshCut()
  if (!rows.value.length) return
  const next: Row[] = []
  for (const r of rows.value) {
    const c = await post('/api/text/tokenize', { text: r.sentence, model_id: modelId.value })
    const wt = r.wText
      ? await post('/api/text/tokenize', { text: r.wText, model_id: modelId.value })
      : null
    next.push({
      ...r,
      sTokens: c?.tokens ?? r.sTokens,
      sCount: c?.count ?? r.sCount,
      wTokens: wt?.tokens ?? r.wTokens,
    })
  }
  rows.value = next
})

watch(sentence, scheduleCut)

onMounted(async () => {
  sentence.value = presetTextFor('house', uiLang.value)
  word.value = presetWordFor(uiLang.value)
  await loadTokenizers()
  await refreshCut()
})

/** Whether the preparing column is folded away. Only the handle moves this. */
const folded = ref(false)
</script>

<style scoped>
.tkc {
  height: 100%;
  display: flex;
  flex-direction: column;
  color: #e2e8f0;
}

.tkc-ask {
  gap: 14px;
  padding-right: 4px;
}

.tkc-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tkc-input {
  width: 100%;
  box-sizing: border-box;
  background: var(--surface-2);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 8px 10px;
  color: #e2e8f0;
  font-size: 0.95rem;
  line-height: 1.45;
  resize: vertical;
}

.tkc-input:focus {
  outline: none;
  border-color: rgba(127, 178, 255, 0.6);
}

.tkc-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tkc-chip {
  background: #1d2f45;
  border: 1px solid #3f6a9c;
  border-radius: 999px;
  padding: 3px 11px;
  color: #dde4ee;
  font-size: 0.85rem;
  cursor: pointer;
}

.tkc-chip.on {
  border-color: #4caf50;
  color: #ffffff;
}

.tkc-chip.off {
  opacity: 0.35;
  cursor: not-allowed;
}

.tkc-role {
  margin: 2px 0 0;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.5);
}

.tkc-note {
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.6);
}

.tkc-note-line {
  margin: 0 0 6px;
}

.tkc-note-line:last-child {
  margin-bottom: 0;
}

.tkc-out {
  gap: 18px;
  overflow-y: auto;
  padding-right: 6px;
}

.tkc-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tkc-head {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
  color: #c9b6ff;
}

.tkc-empty {
  margin: 0;
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.4);
}

/* Die Chips der Zerlegung (components/TokenChip.vue, seit 2026-09-15 auch die
   Token-Tabelle von Encoder Fusion). Ein Token ist so breit wie sein eigenes
   Stück. */
.tkc-cut {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

/* Ein Stück eines Zeichens hängt am Vorgänger, ohne Lücke: das negative Maß
   hebt genau den `gap` von .tkc-cut auf (die fehlende linke Kante bringt der
   Chip selbst mit). */
.tkc-cut :deep(.tok.part) {
  margin-inline-start: -4px;
}

.tkc-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.6);
}

.tkc-window {
  display: flex;
  align-items: center;
  gap: 10px;
}

.tkc-window-track {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.tkc-window-fill {
  height: 100%;
  background: #4caf50;
  min-width: 2px;
}

.tkc-window-num {
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.5);
  font-variant-numeric: tabular-nums;
}

/* Eine Zeile je Sprache: Name, Balken, Anzahl, und ein Schalter, der die
   Zerlegung dieser Zeile aufklappt. */
.tkc-row,
.tkc-wrow {
  display: grid;
  grid-template-columns: 9rem 1fr 3rem 1.6rem;
  align-items: center;
  gap: 8px;
  padding: 3px 0;
}

.tkc-wrow {
  grid-template-columns: 9rem 1fr 3rem;
}

.tkc-row.mine .tkc-lang,
.tkc-wrow.mine .tkc-lang {
  color: #4caf50;
}

.tkc-lang {
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.75);
  text-align: right;
}

.tkc-bar-cell {
  display: block;
  height: 8px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 4px;
  overflow: hidden;
}

.tkc-bar {
  display: block;
  height: 100%;
  background: #3f6a9c;
  border-radius: 4px;
}

.tkc-row.mine .tkc-bar {
  background: #4caf50;
}

.tkc-count {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.7);
  font-variant-numeric: tabular-nums;
}

.tkc-more {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.45);
  cursor: pointer;
  font-size: 0.95rem;
  line-height: 1;
  padding: 0;
}

.tkc-row-cut {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 6px 0 10px;
}

.tkc-row-text {
  margin: 0;
  font-size: var(--flow-fs-body);
  color: rgba(255, 255, 255, 0.6);
}
</style>
