<script setup lang="ts">
/**
 * The sign-in field of the header, beside the platform's name (2026-11-14):
 * whom this device is signed in as, in the words of the room. A leader or an
 * admin reads the course they work in, or "Own use" ("Eigene Nutzung",
 * decided 2026-10-31) where they chose none; a device that entered with a
 * code reads its place. No person's name stands here: the header is on the
 * projector in a course.
 *
 * The field has the form of the language field, and its menu is the header
 * menu of App.vue (`.header-menu`, docs/ELEMENT_STRUCTURE_REGISTRY.md). A
 * leader switches between their own use and the courses they lead there
 * (stores/labAuth.ts, `chooseCourse`), and reaches "My area" and the course
 * leader area; a place has no choice, its menu names the place and the
 * course. Not signed in, the field leads to the sign-in page. Below a window width of 1082 px the field keeps only its symbol; the
 * menu still names what it stands for.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useLabAuthStore } from '@/stores/labAuth'
import { coursesApi, type Course } from '@/services/labApi'
import { isPublicRoute } from '@/router'

const { t } = useI18n()
const auth = useLabAuthStore()
const route = useRoute()
const router = useRouter()

const open = ref(false)
const rootRef = ref<HTMLElement | null>(null)
/** The courses this account leads, read when the menu opens. */
const led = ref<Course[]>([])
/** Why the courses could not be read, or why the choice was refused. */
const listFailure = ref<string | null>(null)
const choiceFailure = ref<string | null>(null)
const choosing = ref(false)
/** The menu is reading the session and the courses. Nothing is chosen
 *  meanwhile: Flask writes the session cookie again with every answer, from
 *  the session its request carried, and an answer to the menu's own reading
 *  that came in after a choice would take the choice back. */
const reading = ref(false)
/** Which opening of the menu the reading belongs to. */
let readingFor = 0

/** What the field says. */
const label = computed(() => {
  if (auth.isParticipant) {
    return auth.place !== null ? t('educator.placeLabel', { n: auth.place }) : (auth.course?.name ?? '')
  }
  return auth.course?.name ?? t('nav.signIn.ownUse')
})

const fieldTitle = computed(() => `${t('nav.signIn.title')}: ${label.value}`)

/** The courses offered: those the account leads and has not archived, and
 *  the course it works in now wherever that is not among them (an admin
 *  passes every course, a leader may have archived it since). */
const choices = computed(() => {
  const own = led.value.filter((c) => !c.archived)
  const now = auth.course
  if (now !== null && !own.some((c) => c.id === now.id)) {
    return [{ id: now.id, name: now.name }, ...own.map((c) => ({ id: c.id, name: c.name }))]
  }
  return own.map((c) => ({ id: c.id, name: c.name }))
})

/** The cause, as the server or the network gave it. */
function causeOf(e: any): string {
  return String(e?.response?.data?.error ?? e?.message ?? e)
}

async function readCourses(): Promise<void> {
  listFailure.value = null
  try {
    const { data } = await coursesApi.list()
    const me = auth.user?.id
    led.value = (data.courses ?? []).filter((c) => c.educators.some((e) => e.user_id === me))
  } catch (e) {
    listFailure.value = causeOf(e)
  }
}

async function toggle(): Promise<void> {
  open.value = !open.value
  if (!open.value) return
  if (auth.isParticipant || choosing.value) return
  choiceFailure.value = null
  // What the menu shows is what the server holds now, not what this page
  // last heard; the courses of an account signed in before are not shown.
  // While a choice is out nothing is read: an answer to a reading sent
  // before the choice's answer would take the choice back.
  led.value = []
  const mine = ++readingFor
  reading.value = true
  try {
    await Promise.all([auth.fetchMe(), readCourses()])
  } finally {
    if (mine === readingFor) reading.value = false
  }
}

async function choose(id: number | null): Promise<void> {
  if (choosing.value) return
  if (id === auth.activeCourseId) {
    open.value = false
    return
  }
  choosing.value = true
  choiceFailure.value = null
  try {
    const cause = await auth.chooseCourse(id)
    if (cause === null) {
      open.value = false
    } else {
      // Said where the choice was made, also where the menu was closed meanwhile.
      choiceFailure.value = cause
      open.value = true
    }
  } finally {
    choosing.value = false
  }
}

async function toArea(): Promise<void> {
  open.value = false
  await router.push({ name: 'educator-dashboard' })
}

/** "My area" (views/AccountView.vue): the account and its agreement to the
 *  conditions of use (sketch of 2026-11-14). */
async function toAccount(): Promise<void> {
  open.value = false
  await router.push({ name: 'account' })
}

/** Signed out, a page that needs a sign-in has nothing to show: the sign-in
 *  page takes its place. The start page and the legal pages stay as they are. */
async function signOut(): Promise<void> {
  open.value = false
  await auth.logout()
  if (!isPublicRoute(route)) {
    await router.push({ name: 'login' })
  }
}

function handleClickOutside(e: MouseEvent): void {
  if (rootRef.value && !rootRef.value.contains(e.target as Node)) open.value = false
}

watch(() => route.fullPath, () => { open.value = false })
watch(() => auth.user, (u) => { if (u === null) open.value = false })
onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>

<template>
  <div ref="rootRef" class="signin-dropdown">
    <router-link
      v-if="auth.user === null"
      :to="{ name: 'login' }"
      class="nav-link signin-field signin-anon"
      :title="t('auth.login')"
      :aria-label="t('auth.login')"
    >
      <svg class="signin-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <circle cx="12" cy="8" r="3.5" />
        <path d="M5 20c0-3.6 3.1-5.5 7-5.5s7 1.9 7 5.5" />
      </svg>
      <span class="signin-label">{{ t('auth.login') }}</span>
    </router-link>
    <template v-else>
      <button
        class="nav-link signin-field"
        :title="fieldTitle"
        :aria-label="fieldTitle"
        aria-haspopup="menu"
        :aria-expanded="open"
        @click="toggle"
      >
        <svg class="signin-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <circle cx="12" cy="8" r="3.5" />
          <path d="M5 20c0-3.6 3.1-5.5 7-5.5s7 1.9 7 5.5" />
        </svg>
        <span class="signin-label">{{ label }}</span>
        <span class="lang-caret signin-caret">&#9662;</span>
      </button>
      <div v-if="open" class="header-menu header-menu-start signin-menu" role="menu">
        <template v-if="auth.isParticipant">
          <div class="header-menu-info">
            {{ t('nav.signIn.placeInCourse', { n: auth.place ?? '', course: auth.course?.name ?? '' }) }}
          </div>
          <div class="header-menu-sep" role="separator"></div>
        </template>
        <template v-else>
          <button
            class="header-menu-option"
            role="menuitemradio"
            :aria-checked="auth.activeCourseId === null"
            :disabled="choosing || reading"
            @click="choose(null)"
          >
            <span class="header-menu-mark" aria-hidden="true">{{ auth.activeCourseId === null ? '✓' : '' }}</span>{{ t('nav.signIn.ownUse') }}
          </button>
          <button
            v-for="c in choices"
            :key="c.id"
            class="header-menu-option"
            role="menuitemradio"
            :aria-checked="auth.activeCourseId === c.id"
            :disabled="choosing || reading"
            @click="choose(c.id)"
          >
            <span class="header-menu-mark" aria-hidden="true">{{ auth.activeCourseId === c.id ? '✓' : '' }}</span>{{ c.name }}
          </button>
          <div v-if="listFailure !== null" class="header-menu-info">
            {{ t('nav.signIn.coursesFailed', { cause: listFailure }) }}
          </div>
          <div v-if="choiceFailure !== null" class="header-menu-info">
            {{ t('nav.signIn.notChanged', { cause: choiceFailure }) }}
          </div>
          <div class="header-menu-sep" role="separator"></div>
          <button class="header-menu-option" role="menuitem" @click="toAccount">
            <span class="header-menu-mark" aria-hidden="true"></span>{{ t('account.title') }}
          </button>
          <button class="header-menu-option" role="menuitem" @click="toArea">
            <span class="header-menu-mark" aria-hidden="true"></span>{{ t('educator.dashboard') }}
          </button>
        </template>
        <button class="header-menu-option" role="menuitem" :disabled="choosing" @click="signOut">
          <span class="header-menu-mark" aria-hidden="true"></span>{{ t('auth.logout') }}
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* The field takes what the header's left column leaves after the logo and the
   name, up to 1.5rem before the mode selector, and shortens a long course
   name with an ellipsis. The column reaches the mode selector: App.vue gives
   it back the room its pull toward the window's edge takes. */
.signin-dropdown {
  position: relative;
  display: flex;
  min-width: 0;
  margin-inline-end: 1.5rem;
}

.signin-field {
  gap: 0.3rem;
  min-width: 0;
  padding: 0.4rem 0.5rem;
  border-color: rgba(255, 255, 255, 0.18);
  color: rgba(255, 255, 255, 0.75);
  font-size: 0.8rem;
  font-weight: 400;
  white-space: nowrap;
}

.signin-anon {
  border-color: transparent;
  color: rgba(255, 255, 255, 0.6);
}

.signin-field .signin-icon {
  flex: 0 0 auto;
  width: 16px;
  height: 16px;
}

/* The label's room, computed from the header's own measures: the left column
   is (min(100vw, 1400px) - 2rem - 388px) / 2 (header-content, mode selector),
   and the pull toward the window's edge adds --header-edge-shift + 3px to it
   (App.vue); the logo (38px), the gap (8px), the name (152px) with its margin
   (24px), the gap (8px) and the 24px kept before the mode selector take 254px
   of it, and the field's border, padding, symbol, caret and gaps another
   50px. A bound of its own, and not only the shrinking of the row: a long
   course name would otherwise widen the column and push the mode selector
   off the middle. */
.signin-label {
  min-width: 0;
  max-width: calc((min(100vw, 1400px) - 420px) / 2 - 304px + var(--header-edge-shift, 0px) + 3px);
  overflow: hidden;
  text-overflow: ellipsis;
}

.signin-caret {
  flex: 0 0 auto;
}

.signin-menu {
  min-width: 210px;
}

/* Below this width the room above holds less than 30px for the label, 80px
   for the whole field: the field keeps its symbol, and the menu names what it
   stands for. The margin before the mode selector narrows with it: below
   about 910px the row of the header is wider than the window. */
@media (max-width: 1081px) {
  .signin-label,
  .signin-caret {
    display: none;
  }

  .signin-dropdown {
    margin-inline-end: 0.5rem;
  }
}
</style>
