<!--
  Course-leader area (P1). Route: /educator  (requiresRole: 'educator')
  Lists my courses (title, safety level, number of places, and until when the
  access window is open) and lets me create a new course. Page background via
  var(--bg-base).
-->
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useLabAuthStore } from '../../stores/labAuth'
import { coursesApi, type Course, type SafetyLevel } from '../../services/labApi'

const auth = useLabAuthStore()
const router = useRouter()
const { locale } = useI18n()

const courses = ref<Course[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const newTitle = ref('')
const newSafety = ref<SafetyLevel>('youth')
const creating = ref(false)

async function load() {
  loading.value = true
  error.value = null
  try {
    courses.value = (await coursesApi.list()).data.courses
  } catch (e: any) {
    error.value = e?.response?.data?.error ?? 'Failed to load courses'
  } finally {
    loading.value = false
  }
}

async function createCourse() {
  if (!newTitle.value.trim() || creating.value) return
  creating.value = true
  error.value = null
  try {
    const { data } = await coursesApi.create({ title: newTitle.value.trim(), safety_level: newSafety.value })
    newTitle.value = ''
    router.push(`/educator/courses/${data.course.id}`)
  } catch (e: any) {
    error.value = e?.response?.data?.error ?? 'Failed to create course'
  } finally {
    creating.value = false
  }
}

/** The end of the access window in the reader's language: day, month, hour, minute. */
function formatMoment(iso: string): string {
  return new Date(iso).toLocaleString(locale.value, {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

onMounted(load)
</script>

<template>
  <div class="dash">
    <header>
      <div>
        <h1>{{ $t('educator.dashboard') }}</h1>
        <p class="who" v-if="auth.user">{{ auth.user.display_name || auth.user.identifier }}</p>
      </div>
      <div class="head-actions">
        <router-link v-if="auth.isAdmin" to="/admin/users" class="ghost">{{ $t('admin.users.title') }}</router-link>
        <button class="ghost" @click="auth.logout()">{{ $t('auth.logout') }}</button>
      </div>
    </header>

    <section class="create">
      <input v-model="newTitle" :placeholder="$t('educator.newCourseName')" @keyup.enter="createCourse" />
      <select v-model="newSafety">
        <option value="kids">kids</option>
        <option value="youth">youth</option>
        <option value="open">open</option>
      </select>
      <button class="primary" :disabled="!newTitle.trim() || creating" @click="createCourse">
        {{ $t('educator.createCourse') }}
      </button>
    </section>

    <p v-if="error" class="err">{{ error }}</p>
    <p v-if="loading" class="muted">{{ $t('common.loading') }}</p>

    <section class="courses" v-if="!loading">
      <article v-for="c in courses" :key="c.id" class="card" @click="router.push(`/educator/courses/${c.id}`)">
        <h3>{{ c.name }}</h3>
        <p class="meta">
          {{ $t('educator.safety') }}: {{ c.safety_level }} ·
          {{ $t('educator.placeCount', { n: c.place_count }, c.place_count) }}
        </p>
        <p class="access">
          <span v-if="c.access_open && c.access_until" class="access-on">
            {{ $t('educator.accessOpenUntil', { until: formatMoment(c.access_until) }) }}
          </span>
          <span v-else class="access-off">{{ $t('educator.accessClosed') }}</span>
        </p>
      </article>
      <p v-if="!courses.length" class="muted">{{ $t('educator.noCourses') }}</p>
    </section>
  </div>
</template>

<style scoped>
.dash { position: fixed; inset: 0; top: 56px; background: var(--bg-base); color: rgba(255,255,255,0.9); padding: 24px; overflow-y: auto; }
header { display: flex; justify-content: space-between; align-items: flex-start; }
h1 { font-size: 1.3rem; margin: 0; }
.who { font-size: 0.85rem; color: rgba(255,255,255,0.5); margin: 4px 0 0; }
.head-actions { display: flex; gap: 8px; }
.create { display: flex; gap: 10px; margin: 20px 0; flex-wrap: wrap; }
.create input { flex: 1; min-width: 200px; }
input, select { padding: 9px; border-radius: 8px; background: var(--surface-1); color: #fff; border: 1px solid rgba(255,255,255,0.15); }
input:focus, select:focus { outline: none; border-color: #4caf50; }
.courses { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.card { background: var(--surface-1); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 16px; cursor: pointer; }
.card:hover { border-color: #4caf50; }
.card h3 { margin: 0 0 6px; font-size: 1rem; }
.meta { font-size: 0.78rem; color: rgba(255,255,255,0.5); margin: 0 0 6px; }
.access { font-size: 0.74rem; margin: 0; }
.access-on { color: #4caf50; }
.access-off { color: rgba(255,255,255,0.4); }
.primary { background: #4caf50; color: #fff; border: none; border-radius: 8px; padding: 9px 16px; cursor: pointer; }
.primary:disabled { opacity: 0.4; cursor: not-allowed; }
.ghost { color: #fff; border: 1px solid rgba(255,255,255,0.2); border-radius: 8px; padding: 7px 14px; text-decoration: none; background: transparent; cursor: pointer; }
.err { color: #ff6b6b; font-size: 0.85rem; }
.muted { color: rgba(255,255,255,0.4); }
</style>
