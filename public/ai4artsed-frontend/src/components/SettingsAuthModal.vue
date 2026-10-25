<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="modelValue" class="modal-overlay" @click="closeModal">
        <div class="modal-container" @click.stop>
          <div class="modal-header">
            <h1>{{ $t('settings.authRequired') }}</h1>
            <button class="modal-close" @click="closeModal" :title="$t('common.cancel')">×</button>
          </div>

          <div class="modal-body">
            <p class="auth-prompt">{{ $t('settings.authPrompt') }}</p>

            <form @submit.prevent="authenticate">
              <input
                type="password"
                v-model="password"
                :placeholder="$t('settings.passwordPlaceholder')"
                class="password-input"
                autofocus
                :disabled="loading"
              />

              <div v-if="error" class="error-message">
                {{ error }}
              </div>

              <div class="button-row">
                <button type="submit" class="auth-btn" :disabled="loading || !password">
                  {{ loading ? $t('settings.authenticating') : $t('settings.authenticate') }}
                </button>
                <button type="button" @click="closeModal" class="cancel-btn">
                  {{ $t('common.cancel') }}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'authenticated': []
}>()

const router = useRouter()
const { t } = useI18n()
const password = ref('')
const error = ref('')
const loading = ref(false)

async function authenticate() {
  error.value = ''
  loading.value = true

  try {
    const response = await fetch('/api/settings/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ password: password.value })
    })

    if (response.ok) {
      emit('authenticated')
      closeModal()
    } else if (response.status === 403) {
      error.value = t('settings.authIncorrectPassword')
      password.value = ''
    } else {
      const data = await response.json()
      error.value = data.error || t('settings.authError')
    }
  } catch (e) {
    error.value = 'Connection error'
    console.error('Authentication error:', e)
  } finally {
    loading.value = false
  }
}

function closeModal() {
  emit('update:modelValue', false)
  password.value = ''
  error.value = ''
  loading.value = false
}

function handleEscape(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.modelValue) {
    closeModal()
  }
}

// Clear fields when modal is closed
watch(() => props.modelValue, (newVal) => {
  if (!newVal) {
    password.value = ''
    error.value = ''
    loading.value = false
  }
})

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
}

.modal-container {
  background: var(--bg-base);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  max-width: 450px;
  width: 100%;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.modal-header {
  padding: 1.5rem 2rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
  color: rgba(255, 255, 255, 0.95);
}

.modal-close {
  background: none;
  border: none;
  font-size: 2rem;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s ease;
  line-height: 1;
}

.modal-close:hover {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.9);
}

.modal-body {
  padding: 2rem;
}

.auth-prompt {
  color: rgba(255, 255, 255, 0.8);
  margin-bottom: 1.5rem;
  line-height: 1.6;
}

form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.password-input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.95);
  transition: all 0.3s ease;
}

.password-input:focus {
  outline: none;
  border-color: rgba(139, 92, 246, 0.6);
  background: rgba(255, 255, 255, 0.08);
}

.password-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.password-input::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.error-message {
  color: #ff6b6b;
  font-size: 13px;
  padding: 8px 12px;
  background: rgba(255, 107, 107, 0.1);
  border: 1px solid rgba(255, 107, 107, 0.3);
  border-radius: 6px;
}

.button-row {
  display: flex;
  gap: 12px;
  margin-top: 1rem;
}

.auth-btn,
.cancel-btn {
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 400;
  cursor: pointer;
  transition: all 0.3s ease;
  border: none;
}

.auth-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  flex: 1;
}

.auth-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

.auth-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.cancel-btn {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.cancel-btn:hover {
  background: rgba(255, 255, 255, 0.15);
}

/* Modal fade animation */
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
  transform: scale(0.9);
}
</style>
