import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'landing',
      component: () => import('../views/LandingView.vue'),
    },
    {
      path: '/about',
      name: 'about',
      component: () => import('../views/AboutView.vue'),
    },
    {
      path: '/execute/:configId',
      name: 'pipeline-execution',
      // Phase 2: Dynamically loads pipeline-specific Vue (e.g., direct.vue, text_transformation.vue)
      component: () => import('../views/PipelineRouter.vue'),
    },
    {
      path: '/text-transformation',
      name: 'text-transformation',
      // Phase 2: text_transformation pipeline visualization (text-based mode)
      component: () => import('../views/text_transformation.vue'),
    },
    {
      path: '/image-transformation',
      name: 'image-transformation',
      // Session 80: image_transformation pipeline visualization (image-based mode)
      component: () => import('../views/image_transformation.vue'),
    },
    {
      path: '/multi-image-transformation',
      name: 'multi-image-transformation',
      // Session 86+: Multi-image transformation (1-3 images → 1 image fusion)
      component: () => import('../views/multi_image_transformation.vue'),
    },
    {
      path: '/direct',
      name: 'direct',
      // Phase 2: direct pipeline (surrealization) visualization
      component: () => import('../views/direct.vue'),
    },
    {
      path: '/surrealizer',
      name: 'surrealizer',
      // Surrealizer: T5-CLIP interpolation for surreal image variations
      component: () => import('../views/surrealizer.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      // Configuration settings page
      component: () => import('../views/SettingsView.vue'),
    },
    {
      path: '/impressum',
      name: 'impressum',
      component: () => import('../views/ImpressumView.vue'),
    },
    {
      path: '/datenschutz',
      name: 'datenschutz',
      component: () => import('../views/DatenschutzView.vue'),
    },
    {
      path: '/dokumentation',
      name: 'dokumentation',
      component: () => import('../views/DokumentationView.vue'),
    },
    {
      path: '/training',
      name: 'training',
      component: () => import('../views/TrainingView.vue'),
    },
    {
      path: '/canvas',
      name: 'canvas-workflow',
      // Session 129: Canvas workflow builder for parallel fan-out workflows
      component: () => import('../views/canvas_workflow.vue'),
      meta: { requiresAdvanced: true },
    },
    {
      path: '/music-generation',
      name: 'music-generation',
      // Unified music generation with Simple/Advanced mode toggle
      component: () => import('../views/music_generation_unified.vue'),
    },
    {
      path: '/latent-lab',
      name: 'latent-lab',
      // Latent Lab: Deconstructive platform for vector/latent space exploration
      component: () => import('../views/latent_lab.vue'),
      meta: { requiresAdvanced: true },
    },
    {
      path: '/music-generation-simple',
      name: 'music-generation-simple',
      // Direct access to V1 (Simple) for testing
      component: () => import('../views/music_generation.vue'),
    },
    {
      path: '/music-generation-advanced',
      name: 'music-generation-advanced',
      // Direct access to V2 (Advanced) for testing
      component: () => import('../views/music_generation_v2.vue'),
    },
    {
      path: '/animation-test',
      name: 'animation-test',
      // Test page for GPU visualization animations
      component: () => import('../views/AnimationTestView.vue'),
    },
    {
      path: '/dev/pixel-editor',
      name: 'pixel-editor',
      // Dev tool: visual pixel template editor for Bits & Pixels animation
      component: () => import('../views/PixelTemplateEditorView.vue'),
    },
    {
      path: '/rave-training',
      name: 'rave-training',
      component: () => import('../views/RaveTrainingView.vue'),
    },
    {
      path: '/compare',
      name: 'compare-hub',
      // Compare Hub: Language comparison, Temperature comparison, etc.
      component: () => import('../views/compare_hub.vue'),
    },
    {
      path: '/workshop',
      name: 'workshop-planning',
      // Workshop resource planning: collective model selection with Trashy
      component: () => import('../views/workshop_planning.vue'),
    },
    {
      path: '/persona',
      name: 'ai-persona',
      // Dialogic AI persona: resistant machine that decides what to generate
      component: () => import('../views/ai_persona.vue'),
    },
    {
      path: '/usage-agreement',
      name: 'usage-agreement',
      component: () => import('../views/UsageAgreementView.vue'),
      meta: { skipAgreementCheck: true },
    },
  ],
})

// Check usage agreement, authentication, and advanced-mode guards
router.beforeEach(async (to, from, next) => {
  // Usage agreement guard: redirect to agreement page if cookie not set
  if (!to.meta.skipAgreementCheck) {
    const hasAgreement = document.cookie.split(';').some(c => c.trim().startsWith('usage_agreement_accepted='))
    if (!hasAgreement) {
      next({ name: 'usage-agreement', query: { redirect: to.fullPath } })
      return
    }
  }

  // Advanced-mode guard for Canvas and Latent Lab (prevents direct URL access at kids/youth)
  if (to.meta.requiresAdvanced) {
    const { useSafetyLevelStore } = await import('../stores/safetyLevel')
    const store = useSafetyLevelStore()
    // Wait for initial fetch if not loaded yet
    if (!store.loaded) {
      await store.fetchLevel()
    }
    if (!store.isAdvancedMode) {
      next({ name: 'landing' })
      return
    }
  }

  next()
})

export default router
