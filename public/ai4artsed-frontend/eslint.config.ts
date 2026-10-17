import { globalIgnores } from 'eslint/config'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'
import pluginVitest from '@vitest/eslint-plugin'
import pluginPlaywright from 'eslint-plugin-playwright'

// To allow more languages other than `ts` in `.vue` files, uncomment the following lines:
// import { configureVueProject } from '@vue/eslint-config-typescript'
// configureVueProject({ scriptLangs: ['ts', 'tsx'] })
// More info at https://github.com/vuejs/eslint-config-typescript/#advanced-setup

export default defineConfigWithVueTs(
  {
    name: 'app/files-to-lint',
    files: ['**/*.{ts,mts,tsx,vue}'],
  },

  globalIgnores(['**/dist/**', '**/dist-ssr/**', '**/coverage/**']),

  pluginVue.configs['flat/essential'],
  vueTsConfigs.recommended,
  
  {
    ...pluginVitest.configs.recommended,
    files: ['src/**/__tests__/*'],
  },
  
  {
    ...pluginPlaywright.configs['flat/recommended'],
    files: ['e2e/**/*.{test,spec}.{js,ts,jsx,tsx}'],
  },

  // Vue 3 Compiler Macros Configuration
  // Prevents common mistake: importing defineProps/defineEmits in <script setup>
  {
    name: 'app/vue-compiler-macros',
    files: ['**/*.vue'],
    languageOptions: {
      globals: {
        // Vue 3 compiler macros - auto-available in <script setup>
        defineProps: 'readonly',
        defineEmits: 'readonly',
        defineExpose: 'readonly',
        defineOptions: 'readonly',
        defineSlots: 'readonly',
        withDefaults: 'readonly',
      },
    },
    rules: {
      // Enforce correct usage of compiler macros
      'vue/define-macros-order': ['error', {
        order: ['defineOptions', 'defineProps', 'defineEmits', 'defineSlots'],
      }],
      // Prevent accidental imports of compiler macros
      'no-restricted-imports': ['error', {
        paths: [{
          name: 'vue',
          importNames: ['defineProps', 'defineEmits', 'defineExpose', 'defineOptions', 'defineSlots', 'withDefaults'],
          message: 'These are Vue 3 compiler macros and should not be imported. They are auto-available in <script setup>.',
        }],
      }],
    },
  },
)
