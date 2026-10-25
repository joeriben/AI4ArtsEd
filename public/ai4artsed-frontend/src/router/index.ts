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
    // --- The transform mode (text · image · multi-image, and its hub) was
    //     replaced by Flow and removed. The paths stay as
    //     redirects: they are in workshop handouts and in bookmarks, and a 404
    //     where a working page stood is worse than an unfamiliar one. Same for
    //     /execute/<config>, which existed to load one of those pages by
    //     pipeline name. ---
    { path: '/execute/:configId', redirect: '/x2x-flow' },
    { path: '/text-transformation', redirect: '/x2x-flow' },
    { path: '/t2i-flow', redirect: '/x2x-flow' },
    { path: '/image-transformation', redirect: '/x2x-flow' },
    { path: '/multi-image-transformation', redirect: '/x2x-flow' },
    { path: '/x2x-legacy', redirect: '/x2x-flow' },
    {
      path: '/direct',
      name: 'direct',
      // Phase 2: direct pipeline (surrealization) visualization
      component: () => import('../views/direct.vue'),
    },
    {
      // Encoder Fusion used to have a door of its own; it is an instrument of
      // the lab now and is reached there. The old address stands
      // in workshop handouts and bookmarks, so it keeps working.
      path: '/surrealizer',
      redirect: '/latent-lab/encoder-fusion',
    },
    {
      path: '/surrealizer-flow',
      name: 'surrealizer-flow',
      // Surrealizer (flow-as-interface pilot) — additive, original stays as legacy
      component: () => import('../views/surrealizer_flow.vue'),
    },
    {
      path: '/x2x-flow',
      name: 'x2x-flow',
      // x2x: the working surface. Replaced the transform mode.
      component: () => import('../views/x2x_flow.vue'),
    },
    {
      // The Decomposition left the lab; an old address still reaches the lab,
      // which shows the instrument it falls back to.
      path: '/decomposition',
      redirect: '/latent-lab',
    },
    {
      path: '/kickin',
      name: 'kickin',
      component: () => import('../views/KickinView.vue'),
    },
    {
      path: '/kickin-perblock',
      name: 'kickin-perblock',
      component: () => import('../views/KickinPerBlockView.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      // The settings are a layer over the page (App.vue opens it on this route
      // name). The address stays for bookmarks and handouts:
      // it shows the start page with the layer over it.
      component: () => import('../views/LandingView.vue'),
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
      // LoRA Training is the last category of the Latent Lab and no longer a
      // page of its own; the old address keeps working and leads there.
      path: '/training',
      redirect: '/latent-lab/lora-sd35',
    },
    {
      path: '/canvas',
      name: 'canvas-workflow',
      // Canvas workflow builder for parallel fan-out workflows
      // Safety: every generation asks the flow's Stage 3, which checks at kids,
      // youth and open (services/canvas_executor.py `canvas_stage3_verdict`);
      // a perspective carries the Stage-2 safety prefix, and a picture is
      // checked after generation at kids and youth. There is no Stage 1 on the
      // Canvas.
      component: () => import('../views/canvas_workflow.vue'),
    },
    {
      // Re-enactment: a microphone recording is passed through four machines and
      // sung back. It has no page of its own any more and stands in the lab; the
      // address survives because it is written in handouts.
      path: '/cover-band',
      redirect: '/latent-lab/re-enactment',
    },
    {
      // Formerly called Silly Parrot. The old path is in the served news and
      // in whatever anybody wrote down during a workshop.
      path: '/silly-parrot',
      redirect: '/cover-band',
    },
    // Two Latent Lab addresses need no line of their own here.
    //
    // /latent-lab/randomness used to lead to /latent-lab/guidance-and-temperature;
    // that instrument had failed and was removed completely. A redirect onto a
    // surface that is gone is worse than none, so both addresses fall through
    // to the lab, which opens where the visitor last was.
    //
    // The three earlier addresses of Cultural (Un)Known — /latent-lab/
    // default-census, /latent-lab/cultural-bias and
    // /latent-lab/cultural-non-knowledge — all still open it, and
    // /latent-lab/system-prompts still opens System Prompts, without anything
    // here: an address never carried the category, so moving an instrument
    // between categories does not touch it, and a RENAMED instrument keeps its
    // old address in the lab's own IDS table (views/latent_lab.vue).
    {
      // Every instrument has an address of its own, and that address names the
      // instrument alone, with no category segment: the categories can change,
      // so the address references the instrument directly. The lab maps the
      // readable name onto the id its lab files switch on; a bare /latent-lab
      // opens where the visitor left off.
      path: '/latent-lab/:instrument?',
      name: 'latent-lab',
      // Latent Lab: Deconstructive platform for vector/latent space exploration
      component: () => import('../views/latent_lab.vue'),
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
      // The six comparison instruments are the first category of the Latent Lab
      // and each has an address of its own; this one leads to the first of them.
      path: '/compare',
      redirect: '/latent-lab/model-comparison',
    },
    {
      path: '/together',
      name: 'together',
      // Working together: the accompanying conversation for a group's work.
      component: () => import('../views/resona.vue'),
    },
    {
      // Called /workshop before the mode was renamed Together. The old path is
      // in workshop handouts and in bookmarks.
      path: '/workshop',
      redirect: '/together',
    },
    {
      path: '/contesting',
      name: 'contesting',
      // Contesting: aesthetic ideas are put up for contest here, and the machine decides for itself what comes of it
      component: () => import('../views/ai_persona.vue'),
    },
    {
      path: '/usage-agreement',
      name: 'usage-agreement',
      component: () => import('../views/UsageAgreementView.vue'),
      meta: { skipAgreementCheck: true },
    },
    // --- Lab user/course system (Phase 0) — NEW routes only. These are the
    //     ONLY routes gated by the auth guard below; the rest of the platform
    //     stays fully usable without any login (hard guardrail). ---
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      // reachable before the usage agreement
      meta: { skipAgreementCheck: true },
    },
    {
      path: '/account',
      name: 'account',
      component: () => import('../views/AccountView.vue'),
      // any logged-in user (incl. participant); reachable before the agreement
      meta: { skipAgreementCheck: true, requiresLabAuth: true },
    },
    {
      path: '/educator',
      name: 'educator-dashboard',
      component: () => import('../views/educator/EducatorDashboard.vue'),
      meta: { skipAgreementCheck: true, requiresLabAuth: true, requiresRole: 'educator' },
    },
    {
      path: '/educator/courses/:id',
      name: 'educator-course',
      component: () => import('../views/educator/CourseEditor.vue'),
      meta: { skipAgreementCheck: true, requiresLabAuth: true, requiresRole: 'educator' },
    },
    {
      path: '/admin/users',
      name: 'admin-users',
      component: () => import('../views/admin/AdminUsersView.vue'),
      meta: { skipAgreementCheck: true, requiresLabAuth: true, requiresRole: 'admin' },
    },
  ],
})

// Check usage agreement, authentication, and advanced-mode guards
router.beforeEach(async (to, from, next) => {
  // --- Lab auth/role gate (Phase 0). Gates ONLY the new lab routes
  //     (requiresLabAuth / requiresRole); every existing route is untouched
  //     and stays reachable without a login. ---
  const requiresLabAuth = to.matched.some((r) => r.meta.requiresLabAuth)
  const requiredRole = to.meta.requiresRole as 'educator' | 'admin' | undefined
  if (requiresLabAuth || requiredRole) {
    const { useLabAuthStore } = await import('../stores/labAuth')
    const auth = useLabAuthStore()
    if (auth.user === null) await auth.fetchMe() // lazy session restore
    if (!auth.isAuthenticated) {
      next({ name: 'login', query: { redirect: to.fullPath } })
      return
    }
    if (requiredRole === 'educator' && !auth.isEducator) {
      next({ name: 'account' })
      return
    }
    if (requiredRole === 'admin' && !auth.isAdmin) {
      next({ name: 'account' })
      return
    }
  }

  // Usage agreement guard: redirect to agreement page if cookie not set
  if (!to.meta.skipAgreementCheck) {
    const hasAgreement = document.cookie.split(';').some(c => c.trim().startsWith('usage_agreement_accepted='))
    if (!hasAgreement) {
      next({ name: 'usage-agreement', query: { redirect: to.fullPath } })
      return
    }
  }

  next()
})

/**
 * Every view on this platform is loaded on demand, and every build writes those
 * pieces under new names and deletes the old ones. A window that was opened
 * before the build still asks for the old names, so the first click in the top
 * menu fetches a piece that is no longer there: the router drops the
 * navigation, the page stays where it stands, and nothing is said. From the
 * outside that is a menu that does nothing — for as long as the window stays
 * open, which in a workshop is all day.
 *
 * So the window fetches itself anew, at the address that was clicked. Once per
 * address: if the piece is really missing and not merely renamed, a second
 * attempt would only reload for ever. A navigation that arrives clears the mark
 * again, so the next build is caught just as the last one was.
 */
export const STALE_CHUNK =
  /dynamically imported module|Importing a module script failed|error loading dynamically imported module|Failed to fetch/i

router.onError((error, to) => {
  if (!STALE_CHUNK.test(String((error as { message?: string })?.message ?? error))) return
  const mark = `router-reload:${to.fullPath}`
  if (sessionStorage.getItem(mark)) {
    console.error('[ROUTER] Piece still missing after a reload:', to.fullPath, error)
    return
  }
  sessionStorage.setItem(mark, '1')
  window.location.assign(to.fullPath)
})

router.afterEach((to) => sessionStorage.removeItem(`router-reload:${to.fullPath}`))

export default router
