<!--
  Admin-only screen for managing EDUCATOR accounts (BAUPLAN Entscheid 3).
  Route: /admin/users  (requiresRole: 'admin')

  There is NO educator self-signup: admins create educators here. Admins can
  deactivate/reactivate, reset the password (a NEW temp password is shown once),
  and delete. Temporary passwords are shown EXACTLY ONCE. Page background via var(--bg-base).
-->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { adminUsersApi, type AdminUser } from '../../services/labApi'

const users = ref<AdminUser[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const form = ref<{ email: string; display_name: string; temp_password: string }>({
  email: '',
  display_name: '',
  temp_password: '',
})
const creating = ref(false)
const createError = ref<string | null>(null)
// One-time credential to surface (from create OR password reset).
const oneTime = ref<{ identifier: string; temp_password: string } | null>(null)

const educators = computed(() => users.value.filter((u) => u.role === 'educator'))
const canSubmit = computed(() => form.value.email.trim().length > 0)

async function load() {
  loading.value = true
  error.value = null
  try {
    users.value = (await adminUsersApi.list()).data.users
  } catch (e: any) {
    error.value = e?.response?.data?.error ?? 'Failed to load users'
  } finally {
    loading.value = false
  }
}

async function createEducator() {
  if (!canSubmit.value) return
  creating.value = true
  createError.value = null
  oneTime.value = null
  try {
    const { data } = await adminUsersApi.create({
      email: form.value.email.trim(),
      display_name: form.value.display_name.trim() || undefined,
      temp_password: form.value.temp_password.trim() || undefined,
    })
    users.value.unshift(data.user)
    oneTime.value = {
      identifier: data.user.identifier,
      temp_password: data.user.temp_password ?? (form.value.temp_password.trim() || '(unavailable)'),
    }
    form.value = { email: '', display_name: '', temp_password: '' }
  } catch (e: any) {
    createError.value = e?.response?.data?.error ?? 'Failed to create educator'
  } finally {
    creating.value = false
  }
}

async function toggleActive(u: AdminUser) {
  try {
    const { data } = await adminUsersApi.update(u.id, { is_active: !u.is_active })
    Object.assign(u, data.user)
  } catch (e: any) {
    error.value = e?.response?.data?.error ?? 'Failed to update user'
  }
}

async function resetPassword(u: AdminUser) {
  error.value = null
  try {
    const { data } = await adminUsersApi.update(u.id, { reset_password: true })
    if (data.user.temp_password) {
      oneTime.value = { identifier: u.identifier, temp_password: data.user.temp_password }
    }
  } catch (e: any) {
    error.value = e?.response?.data?.error ?? 'Failed to reset password'
  }
}

async function removeUser(u: AdminUser) {
  if (!confirm(`Delete educator "${u.display_name || u.identifier}"? This cannot be undone.`)) return
  try {
    await adminUsersApi.remove(u.id)
    users.value = users.value.filter((x) => x.id !== u.id)
  } catch (e: any) {
    error.value = e?.response?.data?.error ?? 'Failed to delete user'
  }
}

onMounted(load)
</script>

<template>
  <div class="admin">
    <header>
      <h1>{{ $t('admin.users.title') }}</h1>
      <p class="sub">{{ $t('admin.users.subtitle') }}</p>
    </header>

    <section class="create">
      <h2>{{ $t('admin.users.createEducator') }}</h2>
      <div class="form">
        <input v-model="form.email" type="email" :placeholder="$t('admin.users.email')" />
        <input v-model="form.display_name" :placeholder="$t('admin.users.displayName')" />
        <input v-model="form.temp_password" type="text" :placeholder="$t('admin.users.tempPassword')" />
        <button class="primary" :disabled="!canSubmit || creating" @click="createEducator">
          {{ creating ? $t('admin.users.creating') : $t('admin.users.create') }}
        </button>
      </div>
      <p v-if="createError" class="err">{{ createError }}</p>
      <p v-if="oneTime" class="ok">
        {{ $t('admin.users.createdHint') }}
        <code>{{ oneTime.identifier }}</code> / <code>{{ oneTime.temp_password }}</code>
      </p>
    </section>

    <section class="list">
      <h2>{{ $t('admin.users.educators') }} <span class="count">({{ educators.length }})</span></h2>
      <p v-if="loading" class="muted">{{ $t('admin.users.loading') }}</p>
      <p v-if="error" class="err">{{ error }}</p>

      <div v-if="educators.length" class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{{ $t('admin.users.colName') }}</th>
              <th>{{ $t('admin.users.colIdentifier') }}</th>
              <th>{{ $t('admin.users.colEmail') }}</th>
              <th>{{ $t('admin.users.colStatus') }}</th>
              <th>{{ $t('admin.users.colActions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in educators" :key="u.id" :class="{ inactive: !u.is_active }">
              <td>{{ u.display_name }}</td>
              <td><code>{{ u.identifier }}</code></td>
              <td>{{ u.email ?? '—' }}</td>
              <td>
                <span :class="['status', u.is_active ? 'active' : 'off']">
                  {{ u.is_active ? $t('admin.users.active') : $t('admin.users.inactive') }}
                </span>
              </td>
              <td class="actions">
                <button class="ghost" @click="toggleActive(u)">
                  {{ u.is_active ? $t('admin.users.deactivate') : $t('admin.users.activate') }}
                </button>
                <button class="ghost" @click="resetPassword(u)">{{ $t('admin.users.resetPassword') }}</button>
                <button class="danger" @click="removeUser(u)">{{ $t('admin.users.delete') }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else-if="!loading" class="muted">{{ $t('admin.users.noEducators') }}</p>
    </section>
  </div>
</template>

<style scoped>
.admin {
  position: fixed;
  inset: 0;
  top: 56px;
  background: var(--bg-base);
  color: rgba(255, 255, 255, 0.9);
  padding: 24px;
  overflow-y: auto;
}
header h1 { margin: 0; }
.sub { color: rgba(255, 255, 255, 0.5); font-size: 0.85rem; margin: 4px 0 0; }
h2 { font-size: 1rem; margin: 24px 0 12px; }
.count { color: rgba(255, 255, 255, 0.4); font-weight: 400; }
.create .form { display: flex; flex-wrap: wrap; gap: 10px; }
input { padding: 9px; border-radius: 8px; background: var(--surface-1); color: #fff; border: 1px solid rgba(255, 255, 255, 0.15); min-width: 200px; }
input:focus { outline: none; border-color: #4caf50; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; margin-top: 8px; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); font-size: 0.88rem; }
th { color: rgba(255, 255, 255, 0.5); font-weight: 700; text-transform: uppercase; font-size: 0.72rem; letter-spacing: 0.04em; }
tr.inactive td { opacity: 0.5; }
.status.active { color: #4caf50; }
.status.off { color: rgba(255, 255, 255, 0.4); }
.actions { display: flex; gap: 8px; flex-wrap: wrap; }
code { color: #4caf50; }
.primary { background: #4caf50; color: #fff; border: none; border-radius: 8px; padding: 9px 16px; cursor: pointer; }
.primary:disabled { opacity: 0.4; cursor: not-allowed; }
.ghost { color: #fff; background: transparent; border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; padding: 6px 12px; cursor: pointer; }
.danger { color: #ff6b6b; background: transparent; border: 1px solid rgba(255, 107, 107, 0.4); border-radius: 8px; padding: 6px 12px; cursor: pointer; }
.err { color: #ff6b6b; font-size: 0.85rem; }
.ok { color: #4caf50; font-size: 0.85rem; }
.muted { color: rgba(255, 255, 255, 0.4); }
</style>
