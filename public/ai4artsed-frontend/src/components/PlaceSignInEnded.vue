<script setup lang="ts">
/**
 * The row that says the sign-in of this device's place has ended while the
 * page stood open (composables/usePlaceSessionCheck.ts), over every page:
 * App.vue shows it. The page stays as it is; "Sign in" leads to the login,
 * "Close" takes the row away.
 */
import { useI18n } from 'vue-i18n'
import SurfaceConfirm from './SurfaceConfirm.vue'
import { useLabAuthStore } from '@/stores/labAuth'
import { usePlaceSessionCheck } from '@/composables/usePlaceSessionCheck'

const { t } = useI18n()
const labAuth = useLabAuthStore()
const { signInAgain } = usePlaceSessionCheck()
</script>

<template>
  <SurfaceConfirm
    v-if="labAuth.endedPlace !== null"
    :text="t('auth.placeSessionEnded', { n: labAuth.endedPlace })"
    :yes="t('auth.login')"
    :cancel="t('common.close')"
    over-app
    @confirm="signInAgain"
    @cancel="labAuth.dismissEndedPlace()"
  />
</template>
