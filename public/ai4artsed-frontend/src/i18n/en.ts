export const en = {
  policyChips: {
    dsgvo_conform: 'The settings hold this installation as DSGVO-conform.',
    dsgvo_preset_not_conform: 'The settings hold the configured provider as not DSGVO-conform.',
    dsgvo_models_flagged: 'The settings warn about a configured model. The settings page names it.',
    dsgvo_unknown: 'The settings hold a provider the model matrix does not know.',
    dsgvoUnread: 'This installation could not be asked.',
    queuePlaceMine: 'Your run is number {n} in the queue.',
    queuePlaceNext: 'A run started now would be number {n} in the queue.',
    queueTimeMine: 'About {time} until your run starts.',
    queueTimeNext: 'About {time} until a run started now would begin.',
    queueTimeUnknown: 'How long the wait is has not been measured.',
    queueUnderMinute: '< 1 min',
    queueUnseen: 'The card cannot be seen right now, so nothing is known about the queue.',
    queueBlockedLora: 'A LoRA training is holding the card.',
    queueBlockedLong: 'The wait is longer than the platform holds a place for.',
    filter: 'Age and content filter in force: {level}.',
    power: 'The graphics card is drawing {watts} W of the {limit} W it may draw. What the machine around it draws cannot be read from here.',
    powerNoLimit: 'The graphics card is drawing {watts} W. What the machine around it draws cannot be read from here.',
    co2: '{grams} g CO₂ per hour at that draw, counted at {factor} g per kWh — the German grid average.',
    levels: {
      kids: 'Kids',
      youth: 'Youth',
      adult: 'legal check only'
    }
  },
  status: {
    idle: 'Ready',
    executing: 'Pipeline running...',
    connectionSlow: 'Connection slow, retrying...',
    completed: 'Pipeline completed!',
    error: 'Error occurred'
  },
  phase2: {
    title: 'Prompt Input',
    userInput: 'Your Input',
    yourInput: 'Your Input',
    yourIdea: 'Your Idea: WHAT should this be about?',
    rules: 'Your Rules: HOW should your idea be implemented?',
    yourInstructions: 'Your Instructions',
    what: 'WHAT',
    how: 'HOW',
    userInputPlaceholder: 'e.g. the street where I live, in the morning, with an animal',
    inputPlaceholder: 'Your text appears here...',
    metaPrompt: 'Artistic Instruction',
    instruction: 'Instruction',
    transformation: 'Prompt Interception',
    metaPromptPlaceholder: 'Describe the interception...',
    result: 'Result',
    expectedResult: 'Expected Result',
    execute: 'Execute Pipeline',
    executing: 'Running...',
    transforming: 'Prompt Interception running...',
    startTransformation: 'Start Prompt Interception',
    letsGo: 'Ok, let\'s go!',
    modified: 'Modified',
    reset: 'Reset',
    loadingConfig: 'Loading configuration...',
    loadingMetaPrompt: 'Loading meta-prompt...',
    errorLoadingConfig: 'Error loading configuration',
    errorLoadingMetaPrompt: 'Error loading meta-prompt',
    threeForces: '3 Forces Working Together',
    twoForces: 'WHAT + HOW → LLM → Result',
    yourPrompt: 'Your Prompt:',
    writeYourText: 'Write your text...',
    examples: 'Examples',
    estimatedTime: '~12 seconds',
    stage12Time: '~5-10 seconds',
    willAppearAfterExecution: 'Will appear after execution...',
    back: 'Back',
    retry: 'Retry',
    transformedPrompt: 'Intercepted Prompt',
    notYetTransformed: 'Not yet intercepted...',
    transform: 'Intercept',
    reTransform: 'Try again differently',
    startAI: 'AI, process my input',
    aiWorking: 'AI is working...',
    continueToMedia: 'Continue to Image Generation',
    readyForMedia: 'Ready for Image Generation',
    stage1: 'Translation and safety check...',
    stage2: 'Prompt Interception...',
    selectMedia: 'Choose your medium:',
    mediaImage: 'Image',
    mediaAudio: 'Audio',
    mediaVideo: 'Video',
    media3D: '3D',
    comingSoon: 'Coming soon',
    generateMedia: 'Start!'
  },
  phase3: {
    generating: 'Image is being generated...',
    generatingHint: '~30 seconds'
  },
  common: {
    back: 'Back',
    loading: 'Loading...',
    error: 'Error',
    retry: 'Retry',
    cancel: 'Cancel',
    close: 'Close',
    remove: 'Remove',
    checkingSafety: 'Checking...',
    start: 'Start',
    generating: 'Generating...',
    apply: 'Apply'
  },
  // The chips of the language selector: the endonym is the label and stays
  // as it is; what a chip says about the language's place in CLIP and T5 is
  // the description (components/LanguageChipSelector.vue).
  languageChips: {
    description: {
      en: 'CLIP primary training language — strongest encoding',
      de: 'German — well-represented in T5, weak in CLIP',
      ar: 'Arabic — RTL script, limited CLIP training data',
      he: 'Hebrew — RTL script, very limited in CLIP',
      tr: 'Turkish — agglutinative grammar, limited CLIP data',
      ko: 'Korean — Hangul script, moderate T5 coverage',
      uk: 'Ukrainian — Cyrillic, limited CLIP training',
      fr: 'French — well-represented in both CLIP and T5',
      es: 'Spanish — well-represented in both CLIP and T5',
      bg: 'Bulgarian — Cyrillic, very limited CLIP data',
      hsb: 'Upper Sorbian — Slavic minority language in Germany, ~20K speakers',
      dsb: 'Lower Sorbian — Slavic minority language in Brandenburg, ~7K speakers',
      fry: 'West Frisian — Germanic language in the Netherlands, ~500K speakers',
      yo: 'Yoruba — West African language (Nigeria), ~50M speakers',
      sw: 'Swahili — East African lingua franca, ~100M speakers',
      cy: 'Welsh — Celtic language in Wales, ~500K speakers',
      qu: 'Quechua — Indigenous Andean language, ~10M speakers',
      hi: 'Hindi — Indo-Aryan, Devanagari script, ~600M speakers',
      ja: 'Japanese — logographic + syllabic scripts, ~125M speakers',
      zh: 'Chinese — logographic script, ~1.1B speakers',
    },
  },
  // The research data export of the settings page (components/SessionExportView.vue).
  sessionExport: {
    errorColon: 'Error:',
    perPage: '{n} per page',
    totalSessionsCount: '{n} total sessions',
    notAvailable: 'N/A',
    zipFailed: 'ZIP creation failed: {m}',
    pdfZipFailed: 'PDF ZIP creation failed: {m}',
    entitiesCount: 'Entities ({n})',
    less: 'Less',
    nMore: '+{n} more',
    title: 'Session Data Export',
    intro: 'View and export research data from generated sessions',
    totalSessions: 'Total Sessions',
    devices: 'Devices',
    configs: 'Configs',
    mediaFiles: 'Media Files',
    dateRange: 'Date Range',
    availableDates: 'Available Dates (click to select)',
    device: 'Device',
    allDevices: 'All Devices',
    config: 'Config',
    allConfigs: 'All Configs',
    safetyLevel: 'Safety Level',
    allLevels: 'All Levels',
    source: 'Source',
    allSources: 'All Sources',
    search: 'Search',
    clearFilters: 'Clear Filters',
    loadingSessions: 'Loading sessions...',
    exportZipJson: 'Export Filtered as ZIP (JSON)',
    exportZipPdf: 'Export Filtered as ZIP (PDF)',
    previous: '‹ Previous',
    next: 'Next ›',
    preview: 'Preview',
    timestamp: 'Timestamp',
    stage2Config: 'Stage2-Config',
    mode: 'Mode',
    stage: 'Stage',
    entities: 'Entities',
    media: 'Media',
    sessionId: 'Session ID',
    actions: 'Actions',
    noMedia: 'No Media',
    sourceDirect: 'direct',
    view: 'View',
    json: 'JSON',
    pdf: 'PDF',
    noSessions: 'No sessions found for the selected filters.',
    sessionDetails: 'Session Details',
    loadingDetails: 'Loading session details...',
    metadata: 'Metadata',
    sessionIdColon: 'Session ID:',
    timestampColon: 'Timestamp:',
    configColon: 'Config:',
    deviceColon: 'Device:',
    safetyLevelColon: 'Safety Level:',
    sourceColon: 'Source:',
    comparisonGroupColon: 'Comparison Group:',
    stageColon: 'Stage:',
    videoUnsupported: 'Your browser does not support the video tag.',
    from: 'From',
    to: 'To',
    sessionIdPlaceholder: 'Session ID...',
    noSessionsToDownload: 'No sessions to download',
  },
  generationError: {
    busy: 'The AI is very busy right now. Try again in a moment!',
    offline: 'The AI is not available right now.',
    unknown: 'Something went wrong. Please try again.',
    startAgain: 'Try again.',
    tellLeader: 'Tell the course leader.',
    takeAnother: 'Take another model.',
    causeAborted: 'Run aborted.',
    causeUnreachable: 'Service not reachable.',
    causeNoModel: 'Model not installed.',
    causeQueueFull: 'Queue full.',
    causeBusy: 'Card taken.',
    causeTraining: 'LoRA training active',
    causeWaited: 'Waited too long.',
    causeMemory: 'Card memory taken.',
    causeRateLimited: 'Rate limit at the model provider.',
    causeRepetition: 'Model stopped by the platform for repeating itself.',
    trainingLeft: 'About {time} to go.',
    trainingUnknown: 'This will take a while.',
    queueWaitAct: '{n} waiting, about {time}.',
    queueWaitingAct: '{n} waiting.',
    brokeOff: 'Run aborted. The input is not the cause.',
    serviceSilent: 'The image service is not answering. Starting again will not help.',
    notHere: 'This model is not installed on this system. Take another one.',
    textNotImage: 'The model sent back a text, not a picture. A prompt that reads like a story gets continued as a story. Describe instead what should be seen in the picture.',
    noRunId: 'Error: no run_id received',
    withMessage: 'Error: {msg}',
    withStatus: 'Something went wrong ({status}). Tell the course leader if it happens again.'
  },
  // What the ring in the corner of a field says when the perspective wrote
  // nothing (composables/useLabRun.ts, perspectiveFailureText); a refusal has
  // the safety check's own sentence instead.
  perspective: {
    failed: 'Nothing came back from the perspective ({status}).',
    empty: 'The perspective came back with nothing to write.'
  },
  gallery: {
    title: 'Favorites',  // no "My": the Mine/All switch already says it
    empty: 'No favorites yet',
    favorite: 'Add to favorites',
    unfavorite: 'Remove from favorites',
    openRun: 'Open in its instrument',
    viewMine: 'My favorites',
    viewAll: 'All favorites',
    mine: 'Mine',
    all: 'All'
  },
  mediaOutput: {
    download: 'Download',
    model3dReady: '3D model generated',
    model3dInteractive: 'Rotate and zoom the 3D model with touch or mouse',
    downloadGlb: 'Download 3D Model (GLB)',
    print: 'Print',
    analyze: 'Image Analysis',
    analyzing: 'Analyzing...',
    generatedImage: 'Generated image',
    mediaCreated: 'Media file created',
    analysisTitle: 'Image Analysis',
    close: 'Close',
    saveSoon: 'Save (Coming Soon)',
    trashyReflection: 'Talk about:',
    forwardToImageTransform: 'Forward to Flow',
    saveComingSoon: 'Save feature coming soon!',
    fullscreen: 'Fullscreen',
    downloadFailed: 'Download failed. Please try again.',
    noImageId: 'Error: cannot determine the image ID',
    analysisFailedWith: 'Image analysis failed: {msg}',
  },
  settings: {
    authIncorrectPassword: 'Incorrect password',
    authError: 'Authentication error',
    authRequired: 'Authentication Required',
    authPrompt: 'Please enter the password to access settings:',
    passwordPlaceholder: 'Enter password...',
    authenticate: 'Sign In',
    authenticating: 'Authenticating...',
    // Admin page
    title: 'Administration',
    tabs: {
      export: 'Research Data',
      config: 'Configuration',
      demos: 'Minigame Demo',
      matrix: 'Model Matrix',
      status: 'Backend Status',
      api: 'API Management',
      knowledge: 'Knowledge Library',
      loras: 'LoRAs'
    },
    // The LoRA register (issue #70, 2026-09-21): which adapter files the
    // platform offers, to whom, with which trigger word. Which models run an
    // adapter is read from the adapter file (2026-09-22) and shown, not set.
    loras: {
      title: 'LoRA register',
      help: 'The register names the adapter files the platform offers, to whom, and with which trigger word in front of the prompt. Which models carry an adapter is read from the adapter file itself. Only what stands here is offered.',
      file: 'File',
      name: 'Name',
      trigger: 'Trigger',
      models: 'Models',
      baseMissing: 'The file names no model.',
      baseAbsent: 'No file to read a model from.',
      baseUnmatched: 'The file names {base}. No model here runs it.',
      owner: 'Owner',
      category: 'Category',
      categoryNone: 'none',
      release: 'Release',
      releasePlatform: 'platform',
      releaseCourse: 'course',
      releaseNone: 'none',
      present: 'file present',
      missing: 'file absent from the LoRA folder',
      save: 'Save',
      remove: 'Remove',
      removeConfirm: 'Take “{name}” out of the register? The file stays in the folder.',
      unregistered: 'Unregistered files',
      register: 'Register',
      empty: 'no row yet',
      loadFailed: 'The register could not be read: {cause}',
      saveFailed: 'Not saved: {cause}',
    },
    loading: 'Loading settings...',
    presets: {
      title: 'Model Presets',
      help: 'Use the **Model Matrix** tab to see all available presets and apply them with one click.',
      openMatrix: 'Open Model Matrix'
    },
    testingTools: {
      title: 'Testing Tools for Educators',
      help: 'Test and explore the pedagogical minigames and animations before using them with learners.',
      openPreview: 'Open Minigame Preview',
      pixelEditor: 'Pixel Template Editor',
      includes: 'Includes: Pixel Animation, Iceberg Melting, Forest Game, Rare Earths'
    },
    general: {
      title: 'General Configuration',
      uiMode: 'UI Mode',
      uiModeHelp: 'Effects of the mode:',
      uiModeEffectLength: 'Length of the intercepted prompt: easy 100 words, medium 200, expert 300.',
      uiModeEffectStructure: 'Information on screen: easy hides the technical readouts, expert shows model, seed and parameters.',
      uiModeEffectStyle: 'Style of the image comments.',
      uiModeNotSafety: 'This is not a filter setting. What is checked and blocked is decided by the safety level below.',
      easy: 'Easy',
      medium: 'Medium',
      expert: 'Expert',
      safetyLevel: 'Safety Level',
      defaultLanguage: 'Default Language',
      germanDe: 'German (de)',
      englishEn: 'English (en)',
      arabicAr: 'Arabic (ar)',
      bulgarianBg: 'Bulgarian (bg)',
      hebrewHe: 'Hebrew (he)',
      turkishTr: 'Turkish (tr)',
      koreanKo: 'Korean (ko)',
      ukrainianUk: 'Ukrainian (uk)',
      frenchFr: 'French (fr)',
      spanishEs: 'Spanish (es)'
    },
    safety: {
      kidsTitle: 'Children (8–13)',
      kidsDesc: 'All filters active: §86a, GDPR, strict child-appropriate content protection (no horror imagery, no depicted violence, no nudity), VLM image check',
      youthTitle: 'Youth (14–18)',
      youthDesc: 'All filters active: §86a, GDPR, age-appropriate content protection for older adolescents (graphic violence, gore, nudity, hate, self-harm and terrorism blocked; non-graphic horror imagery allowed), VLM image check',
      adultTitle: 'Adults',
      adultDesc: '§86a + DSGVO active. No youth protection, no VLM image check.',
      researchTitle: 'Research Mode',
      researchDesc: 'NO safety filters active. Only permitted for use by research institutions in the context of scientific research projects.'
    },
    safetyModels: {
      title: 'Local Safety Model',
      help: 'Checks of prompts, images and person names run on this machine.',
      safetyModel: 'Safety Model',
      safetyModelHelp: 'The classifier these checks ask. Generated code that the filter flags is judged by the translation model instead.'
    },
    dsgvo: {
      title: 'DSGVO Warning',
      notCompliant: 'The following models are **NOT DSGVO-compliant** (data processed outside EU):',
      notRecorded: 'Nothing is recorded about the services these roles reach, in either direction:',
      compliantHint: 'Recorded as DSGVO-compliant:'
    },
    matrix: {
      title: 'Model Selection Matrix',
      help: 'Click a column header to apply that preset. Vision models are always local and auto-selected based on your hardware.',
      editHelp: 'Editing the recommendations. Write each model as its provider names it, e.g.',
      editHelpTail: 'Cells left empty are dropped from the preset.',
      detectedHardware: 'Detected Hardware:',
      applicationArea: 'Application Area',
      lastUserSetting: 'Last user setting',
      restoreUserTitle: 'Put your own setting back into force, row by row',
      noUserRecord: 'Nothing recorded yet',
      userSettingRestored: 'Your own setting is back in force',
      restoreFailed: 'Could not put your own setting back',
      restoreFailedWith: 'Could not put your own setting back: {error}',
      fallback: 'as fallback',
      fallbackTitle: 'May answer for another provider when a call fails, as long as the recorded data-protection status matches',
      local: 'Local',
      applyLocalTitle: 'Click to use local models only',
      applyCloudTitle: 'Click to use {provider} for LLM tasks',
      editingNoApply: 'Editing — column presets cannot be applied right now',
      autoLocal: 'auto (local)',
      localOnly: 'LOCAL',
      defaultBadge: 'DEFAULT',
      defaultBadgeTitle: 'Running on the platform default — not explicitly set. Pick a model above to configure it.',
      dsgvo: {
        yes: 'DSGVO',
        no: 'NOT DSGVO',
        none: 'NO RECORD',
        noneWord: 'no record',
        noneTitle: 'Nothing is recorded about this service, in either direction.',
        setYesTitle: 'Record as DSGVO compliant. Click again to record nothing.',
        setNoTitle: 'Record as NOT DSGVO compliant. Click again to record nothing.',
        setNoShort: 'NOT',
        notePlaceholder: 'On what grounds? (required)',
        noteMissing: 'A recorded DSGVO status needs a reason: {columns}'
      },
      legend: {
        selection: 'Current selection',
        dsgvo: 'DSGVO compliant',
        notDsgvo: 'NOT DSGVO',
        noRecord: 'Nothing recorded',
        vision: 'Vision (always local)'
      },
      visionTerm: 'Vision models',
      visionNote: 'are always run locally and selected based on your VRAM. They work with any LLM provider.',
      edit: 'Edit models',
      reset: 'Reset to our recommendations',
      resetConfirm: 'Reset every model in this matrix to our recommendations? Your own entries in the matrix will be overwritten.',
      save: 'Save',
      cancel: 'Cancel',
      saved: 'Models saved',
      saveFailed: 'Save failed',
      saveFailedWith: 'Save failed: {error}',
      resetDone: 'Our recommendations are back.',
      resetFailed: 'Reset failed',
      resetFailedWith: 'Reset failed: {error}'
    },
    models: {
      title: 'Model Configuration',
      help: 'Enter a model by the path its provider publishes, or by its name; after saving, a line under the field says when no provider carries that path, or when the provider has no key.',
      // Under a role field whose value no provider of this installation carries.
      noRoute: 'No provider of this installation carries this path.',
      noKey: 'No API key for {provider}.',
      matrixAdvised: 'Use of Model Matrix is advised. However, you may configure your settings here freely.',
      localModelsAvailable: '{count} local models available (type or select from dropdown)',
      stage1Text: 'Translation — written prompt',
      stage2Interception: 'Prompt Interception',
      stage2Optimization: 'Media adaption',
      stage3: 'Translation — final prompt; verdict on flagged code',
      chatHelper: 'Help',
      persona: 'Testing ideas',
      resona: 'Workshop companion',
      imageAnalysis: 'Image analysis',
      coding: 'Code generation',
      knowledgeProcessing: 'Knowledge processing',
      roleColumn: 'Role',
      modelColumn: 'Model'
    },
    capabilities: {
      image: 'Image',
      sound: 'Sound',
      video: 'Video',
      three_d: '3D',
      coding: 'Code',
      thinking: 'Inference',
      tools: 'Tools',
      imageHelp: 'This role hands the model the picture itself. Without it the answer comes from a description the local vision model wrote, so anything the description leaves out cannot be asked about.',
      soundHelp: 'This role would hand the model audio to listen to. No role does today — the platform produces sound, no model reads it back.',
      videoHelp: 'This role would hand the model video to watch. No role does today.',
      three_dHelp: 'This role would hand the model geometry to inspect. No role does today.',
      codingHelp: 'This role writes program code that runs in the browser. The check asks for one small function and tests whether what comes back parses as code — a low bar, and it says nothing about how good the code is.',
      thinkingHelp: 'This role wants the model’s inference process, not only the answer it ends at. The check asks a question and looks for an inference channel in the reply. Missing here means none arrives that the platform could show — nothing asks a model to produce one, so it is not a statement about how the model works.',
      toolsHelp: 'This role hands the model the platform functions it may call. Without them the mode only talks about what it would do.',
      imageColumn: 'Whether the picture itself can be handed to the model in this row.',
      soundColumn: 'Whether audio can be handed over. No role asks for it: the platform produces sound, no model listens back.',
      videoColumn: 'Whether video can be handed over. No role asks for it yet.',
      three_dColumn: 'Whether geometry can be handed over. No role asks for it yet.',
      codingColumn: 'Whether the model returns usable program code.',
      thinkingColumn: 'Whether the inference process arrives beside the answer, in a form the platform can show.',
      toolsColumn: 'Whether the model can be given platform functions to call.',
      notPossible: 'not possible',
      columnCaption: 'Requirements of the role',
      loadFailed: 'The requirement columns could not be loaded, so they are empty here — that is not the same as a role needing nothing.',
      checkFailed: 'The check could not be run: {reason}',
      imageFixed: 'The IONOS connection drops the image before the request is built, so no model reached through it can be handed one.',
      toolsFixed: 'The local backend accepts a tool definition and ignores it, so a local model never gets the chance to use one.',
      check: 'Check',
      checking: '…',
      needed: 'needed',
      missing: 'MISSING',
      unchecked: 'not checked',
      noModel: 'no model',
      unsaved: 'The field was edited. The slots describe the saved model — save to check the new one.',
      verdictCannot: '{model} cannot: {evidence}',
      verdictUnclear: '{model}: no clear answer, nothing recorded. {evidence}',
      verdictUnreachable: '{model} could not be asked: {evidence}'
    },
    api: {
      title: 'API Configuration',
      llmProvider: 'LLM Provider',
      localFramework: 'Local LLM framework',
      externalProvider: 'External LLM Provider',
      cloudProvider: 'Cloud LLM provider - requires API key',
      providerNone: 'None (local only)',
      storedIn: 'Stored in',
      currentKey: 'Current',
      keyOf: '{provider} API key',
      // The external frontier image model and its account. SUPPLIED WORDING:
      // the rows translate the German wording in WORK_ORDERS.md
      // (WO-2026-09-23-A, with three spellings corrected and marked there).
      // The provider's name is filled in from the configuration
      // (WO-2026-09-26-P).
      frontierImageLabel: 'External frontier image model',
      frontierProviderLabel: 'Provider',
      frontierKeyLabel: 'API key present',
      frontierBalanceLabel: '{provider} balance',
      // Beside the balance, or in place of `unlimited` for an account without
      // a budget, where the check found a budget used up that binds the key
      // (devserver/my_app/services/provider_account.py, `used_up`).
      frontierUsedUp: {
        account: 'account budget used up',
        key: 'budget of this API key used up',
        team: 'team budget used up'
      }
    },
    save: {
      saveApply: 'Save & Apply',
      saving: 'Saving...',
      applying: 'Applying...',
      success: 'Settings saved and applied',
      presetApplied: 'Applied preset: {preset}'
    },
    backendStatus: {
      vram: 'VRAM:',
      vramFreeOfTotal: '{free} GB free / {total} GB total',
      ago: {
        seconds: '{n}s ago',
        minutes: '{n}m ago',
        hours: '{n}h ago',
        days: '{n}d ago',
      },
      loading: 'Checking backend status...',
      refresh: 'Refresh',
      refreshing: 'Refreshing...',
      localInfrastructure: 'Local Infrastructure',
      cloudApis: 'Cloud APIs',
      outputConfigs: 'Output Configs by Backend',
      reachable: 'Reachable',
      gpuQueue: 'Card queue',
      queueBusy: 'IN USE',
      queueIdle: 'FREE',
      queueRunning: 'RUNNING',
      queueRemaining: '{time} left',
      queueStartsIn: 'starts in {time}',
      queuePassedOver: 'passed over {n}x',
      queueNothing: 'Nothing is waiting for the card.',
      queueUnreachable: 'NO ANSWER',
      queueNoAnswer: 'The card cannot be reached right now, so what is waiting for it is not known.',
      queueApproaching: 'One more on the way, still in translation or the safety check. | {n} more on the way, still in translation or the safety check.',
      unreachable: 'Unreachable',
      available: 'Available',
      unavailable: 'Unavailable',
      configured: 'Configured',
      notConfigured: 'Not Configured',
      gpuService: 'GPU Service',
      subBackend: 'Sub-Backend',
      status: 'Status',
      comfyui: 'ComfyUI',
      localLlm: 'Local LLM',
      gpuHardware: 'GPU Hardware',
      notDetected: 'Not detected',
      showModels: 'Show models',
      hideModels: 'Hide models',
      provider: 'Provider',
      keyStatus: 'API Key',
      dsgvoLabel: 'DSGVO',
      region: 'Region',
      dsgvoCompliant: 'Compliant',
      dsgvoNotCompliant: 'Not Compliant',
      dsgvoNoRecord: 'No record',
      configsAvailable: '{available} of {total} configs available',
      hidden: 'hidden',
      model: 'Model',
      loadedModels: 'Loaded Models',
      foreignProcesses: 'Other GPU Processes',
      noModelsLoaded: 'No models currently loaded',
      vramUsage: 'VRAM',
      inUse: 'In Use',
      idle: 'Idle',
      lastUsed: 'Last Used',
      command: 'Command',
      foreignVram: 'External VRAM usage',
      showLoadedModels: 'Show loaded models',
      hideLoadedModels: 'Hide loaded models',
      showProcesses: 'Show processes',
      hideProcesses: 'Hide processes',
      ownModels: 'Own Models',
      pid: 'PID',
    },
    apiManagement: {
      dsgvo: 'DSGVO',
      period: {
        today: 'Today',
        week: 'Week',
        month: 'Month',
        year: 'Year',
        all: 'All',
      },
      loading: 'Loading API usage data...',
      refresh: 'Refresh',
      refreshing: 'Refreshing...',
      activeProvider: 'Active Cloud Provider',
      noProvider: 'No cloud provider configured (local only)',
      currentSpend: 'Current Spend',
      budgetLimit: 'Budget Limit',
      remaining: 'Remaining',
      unlimited: 'Unlimited',
      resetDate: 'Budget Reset',
      rateLimit: 'Rate Limit',
      billingError: 'Could not fetch billing data',
      // The two parts of a provider's block (WO-2026-09-26-P).
      installationHead: 'Installation',
      accountHead: 'Account (all keys)',
      notReported: 'Not reported by the provider',
      localUsage: 'Local Usage Tracking',
      noUsageData: 'No usage data recorded yet. Data will appear after cloud API calls.',
      calls: 'Calls',
      inputTokens: 'Input Tokens',
      outputTokens: 'Output Tokens',
      estCost: 'Est. Cost',
      byModel: 'By Model',
      byStage: 'By Role',
      stage: 'Role',
      roleGeneration: 'Media generation',
      model: 'Model',
      from: 'From',
      to: 'To',
      providerStatus: 'Provider Status',
      provider: 'Provider',
      apiKey: 'API Key',
      credits: 'Credits',
      region: 'Region',
      configured: 'Configured',
      notConfigured: 'Not Configured',
      modelAssignments: 'Model Assignments',
      function: 'Function',
    },
    knowledge: {
      areas: {
        title: 'Knowledge areas',
        help: 'Group your documents into areas — a box per topic you can add to and drag documents into. Add an optional note for each area (a hint for the agent: why these texts were uploaded, why this area exists). Pick an area to upload into it and see its documents.',
        docCountRatio: '{published}/{total} docs',
        docCountZero: 'no docs',
        fixed: 'fixed',
        unescoName: 'UNESCO — value alignment',
        unescoHint: 'The fixed UNESCO-oriented corpus. Read-only: it ships with the platform and cannot be edited or uploaded into.',
        addChip: '+ New',
        newName: 'Area name',
        newKommentar: 'Note for the agent (optional)',
        create: 'Create',
        creating: 'Creating…',
        cancel: 'Cancel',
        edit: 'Edit',
        editName: 'Name',
        editKommentar: 'Note for the agent (optional)',
        save: 'OK',
        saving: 'Saving…',
        delete: 'Delete',
        confirmDelete: 'Delete area "{name}"?',
        deleteBlocked: 'This area still has documents. Move or remove them first.',
        selectHint: 'Select an area above to upload documents into it and see its inventory.',
        kommentarLabel: 'Note for the agent',
        kommentarEmpty: 'No note yet — add one to tell the agent why this area exists.',
        kommentarPlaceholder: 'Purpose of this area',
        panelDocsTitle: 'Documents in this area',
        panelDocsNone: 'No documents in this area yet. Drop files below to add some.',
        panelDocsNoneFixed: 'This fixed corpus has no indexed documents. Run a reindex if the library files are present but missing here.',
        unescoReadonly: 'The UNESCO corpus is read-only — you can view a profile, but not change or upload.'
      },
      dropzone: {
        label: 'Drop documents here, or click to choose',
        hint: 'PDF or Markdown — dropped files are uploaded into this area',
        hinweisLabel: 'Note for these documents (optional)',
        hinweisPlaceholder: 'A hint for the agent about the files you are adding now',
        uploading: 'Uploading…',
        pickArea: 'Pick an area first (or create one) to upload into it.'
      },
      upload: {
        title: 'Upload document (Tier O)',
        help: 'Add an operator document (PDF or Markdown) to the knowledge library. Only the file is required — the document is processed into a compact knowledge form (profile, condensed sections, glossary) and stored as a draft. Review it, then publish it so the accompaniment can use it. The title is read from the document; the license defaults to internal use only.',
        file: 'File (PDF or Markdown)',
        titleField: 'Title (optional — read from the document if left blank)',
        author: 'Author',
        year: 'Year',
        language: 'Language',
        url: 'Source URL',
        license: 'License (optional — defaults to internal use only)',
        sparten: 'Disciplines',
        spartenFree: 'Disciplines (comma-separated, e.g. performativ, medial)',
        themen: 'Topics',
        themenPlaceholder: 'Comma-separated topics (e.g. decolonial, sustainability)',
        submit: 'Upload & process',
        uploading: 'Uploading…',
        queued: 'Queued ingest job for {docId}.',
        noFile: 'Please choose a file.'
      },
      jobs: {
        title: 'Ingest jobs',
        none: 'No ingest jobs in this session.',
        showLog: 'Show log',
        hideLog: 'Hide log',
        cancel: 'Cancel',
        cancelling: 'Cancelling…',
        state: {
          queued: 'Queued',
          running: 'Running',
          done: 'Done',
          error: 'Error',
          cancelled: 'Cancelled'
        }
      },
      items: {
        title: 'Tier-O inventory',
        refresh: 'Refresh',
        none: 'No operator documents yet. Upload one above, or run a reindex if you added files manually.',
        colStatus: 'Status',
        colTitle: 'Title',
        colYear: 'Year',
        colAnalyzed: 'Analyzed',
        colLicense: 'License',
        colChunks: 'Chunks',
        colActions: 'Actions',
        card: 'Profile',
        publish: 'Publish',
        unpublish: 'Unpublish',
        move: 'Move to…',
        moving: 'Moving…',
        moveNoArea: 'No area',
        delete: 'Delete',
        confirmDelete: 'Delete "{title}" and its original? This cannot be undone.',
        readonlyHint: 'Fixed document — read-only. You can view its profile, but not edit, publish, move, or delete it.',
        reanalyze: 'Re-analyze',
        reanalyzing: 'Re-analyzing…',
        reanalyzeHint: 'Re-run analysis from the stored source with the current model, without re-uploading. This resets a published document back to draft — review and re-publish it afterwards.',
        reanalyzeAll: 'Re-analyze all in this area',
        reanalyzeAllRunning: 'Re-analyzing…',
        confirmReanalyzeAll: 'Re-analyze all {count} document(s) in this area with the current model? Published documents will be reset to draft.',
        neverAnalyzed: 'never analyzed',
        neverAnalyzedHint: 'This document predates analysis-provenance tracking — re-analyze it to record when, in what language, and with which model it was processed.'
      },
      card: {
        title: 'Edit profile',
        titleReadonly: 'Profile',
        help: 'The profile is the German positioning digest of the document (self-claim, reference documents and stance, applicability). Edit the Markdown under the ## PROFIL heading. Saving reindexes.',
        helpReadonly: 'The profile of this fixed document (a positioning digest). Read-only — it ships with the platform and cannot be edited here.',
        emptyProfile: 'This document has no profile text.',
        save: 'Save profile',
        saving: 'Saving…',
        saved: 'Profile saved and reindexed.'
      },
      meta: {
        titel: 'Title',
        autor: 'Author(s)',
        jahr: 'Year',
        quelle: 'Source',
        edit: 'Edit bibliographic details',
        help: 'The title/author/year/source of this document. These are identified automatically at upload and may be wrong — correct them here. Saving reindexes.',
        autorPlaceholder: 'e.g. Surname, F. — or several, comma-separated',
        jahrPlaceholder: 'e.g. 2024',
        quellePlaceholder: 'Journal, book or publisher (with volume/pages if any)',
        titelRequired: 'The title must not be empty.',
        save: 'Save details',
        saving: 'Saving…',
        saved: 'Bibliographic details saved and reindexed.',
        sprache: 'Source language',
        analyzedAt: 'Analyzed',
        analysisLang: 'Analysis language',
        analysisModel: 'Analysis model',
        neverAnalyzed: 'never analyzed with provenance'
      },
      wissen: {
        title: 'Condensed knowledge',
        help: 'The condensed knowledge sections (## WISSEN) — the argument and specifics distilled from the document. Read-only here; this is what the agent actually retrieves.',
        empty: 'No condensed sections in this document yet.'
      },
      glossary: {
        title: 'Glossary overrides',
        help: 'Override a term\'s definition, or hide it from the index entirely. Overrides apply across the whole library and are merged into the index last.',
        helpReadonly: 'The glossary terms of this fixed document. Read-only — they cannot be changed or hidden here.',
        hide: 'Hide',
        save: 'Save glossary overrides',
        saving: 'Saving…',
        saved: 'Glossary overrides saved and reindexed.'
      },
      reindex: {
        button: 'Reindex',
        running: 'Reindexing…',
        done: 'Index rebuilt.'
      },
      export: {
        button: 'Export .md',
        running: 'Exporting…'
      }
    }
  },
  pipeline: {
    yourInput: 'Your input',
    result: 'Result',
    generatedMedia: 'Generated image'
  },
  landing: {
    subtitlePrefix: 'Pedagogical-artistic experimentation platform of the',
    subtitleSuffix: 'for the explorative use of generative artificial intelligence in cultural-aesthetic media education',
    research: '',
    features: {
      together: {
        title: 'Together',
        description: 'Planning a workshop, holding it, looking back at it'
      },
      contesting: {
        title: 'Contesting',
        description: 'Challenging and sharpening ideas'
      },
      flow: {
        title: 'Flow',
        description: 'Bringing ideas together on one surface and working on them'
      },
      latentLab: {
        title: 'Latent Lab',
        description: 'Making the workings of generative AI reachable'
      },
      canvas: {
        title: 'Canvas',
        description: 'Composing AI building blocks freely — with branches and loops'
      }
    }
  },
  keptPerspectives: {
    errRead: 'Could not read what you saved.',
    errKeep: 'Could not save it.',
    errSave: 'Could not save the change.',
    errRemove: 'Could not delete it.',
  },

  presetOverlay: {
    title: 'Choose Perspective',
    close: 'Close',
    mineDrop: 'delete this perspective',
    mineDropConfirm: 'Delete "{name}"? Its earlier wordings go with it, and this cannot be undone.'
  },
  audioRecord: {
    clickHere: 'Click here',
    toRecord: 'to record',
    stop: 'Click again to stop',
    preparing: 'preparing the recording…',
    upTo: 'up to {max}'
  },
  // The one mark that brings something in (components/IntakePlus.vue). Shared
  // by every surface that talks, so the gesture is learned once.
  intake: {
    plus: 'Bring something in',
    upload: 'Upload',
    camera: 'Camera',
    audio: 'Speak',
    text: 'Text'
  },

  imageUpload: {
    clickHere: 'Click here',
    orDragImage: 'or drag an image here',
    formatHint: 'PNG, JPG, WEBP (max 10MB)',
    invalidFormat: 'Invalid file format. Only PNG, JPG, and WEBP allowed.',
    fileTooLarge: 'File too large. Maximum: {max}MB',
    uploadFailed: 'Upload failed',
    heldBack: 'This picture was held back.',
    checkUnavailable: 'The check is unavailable right now. Try again in a moment.',
    infoOriginal: 'Original:',
    infoSize: 'Size:'
  },
  sketchCanvas: {
    drawHere: 'Draw your sketch here',
    pen: 'Pen',
    eraser: 'Eraser',
    undo: 'Undo',
    clear: 'Clear',
    done: 'Done',
    brushSmall: 'Small',
    brushMedium: 'Medium',
    brushLarge: 'Large'
  },
  promptExamples: {
    label: 'Example prompts',
    // The ready-made prompts every instrument offers, read through
    // `lib/promptPresets.ts`. THEY ARE PROMPTS: they go to a model word for
    // word, so a label or prose pass leaves them alone, and a translation
    // carries the sentence rather than its wording.
    presets: {
      house: 'A house stands in a landscape, surrounded by farmland, nature and animals. Some people can be seen.',
      street: 'the street where I live, in the morning, with an animal',
      person: 'a person in typical clothing',
      // Every entry addresses ONE observable property, and the
      // comment under it names the property, the surface that can evaluate it
      // (seed discipline is a property of the surface, not of the prompt) and
      // the research the property comes from. Border experiments are marked
      // as such — they invite observation of failure, they promise no result.
      // Comparison pairs stay out of this list (they belong to the surfaces
      // that hold the seed); what stands here is the single sentence only.
      // Property: model idiosyncrasy — the same sentence read by several
      // models (catalogue #1). Surface: Model Comparison (fixed seed);
      // Mean Images (rewordings axis). Source: the platform's model
      // comparison itself; the street sentence above serves the same end.
      walk: 'a walk in the forest, in the afternoon',
      // Property: WAS with the HOW held — the WHAT named by a role that
      // says who is looking (catalogue #4). Surface: Perspectives Template
      // (the perspective list supplies the how), Surrealizer. Source: the
      // platform's WAS/HOW separation.
      forest: 'a walk in the forest, seen through the eyes of a child',
      // Property: WAS with the HOW held — a second role for the same walk
      // (catalogue #4). Surface: Perspectives Template; Mean Images with
      // the two sentences as a series is a comparison the class can read.
      // Source: the platform's WAS/HOW separation.
      friendship: 'friendship',
      // Property: abstract concept as cliché (catalogue #6). Surface: Mean
      // Images — the mean of many images shows the one cliché the model
      // reaches for; Attention Cartography for the sentence read word by
      // word. Source: teotia-et-al-2025 (DIMCIM); the platform's concept
      // note on abstract concepts.
      loneliness: 'loneliness',
      // Property: abstract concept as cliché, second concept (catalogue #6).
      // Surface: Mean Images; Model Comparison across the two abstract
      // entries. Source: teotia-et-al-2025 (DIMCIM).
      meal: 'a family at dinner',
      // Property: under-specification — trait words, no demographic given
      // (catalogue #7, beside `person` above). Surface: Mean Images (both
      // axes), Model Comparison (fixed seed). Source: fraser-et-al-2023;
      // park-2024.
      city: 'a street in the evening',
      // Property: geographical default — no place named (catalogue #8,
      // beside `street` above: the morning street). Surface: Mean Images
      // (promptFixed axis), Model Comparison. Source: basu-et-al-2023.
      nurse: 'a nurse at work',
      // Property: stereotype reinforcement by profession (catalogue #9).
      // Surface: Mean Images (promptFixed axis) — the mean shows the
      // reading the model falls into; the pair (nurse/plumber) belongs to
      // the surfaces that hold the seed, the sentence here is the single
      // one. Source: luccioni-et-al-2023; bianchi-et-al-2023.
      plumber: 'a plumber at work',
      // Property: stereotype reinforcement by profession, the counterpart
      // profession (catalogue #9). Surface: Mean Images (promptFixed);
      // Model Comparison. Source: luccioni-et-al-2023; bianchi-et-al-2023;
      // seshadri-et-al-2023.
      // Border experiment — it invites failure, it promises no result.
      // Property: contradictory rules (catalogue #10): the adjective and
      // the noun head shut each other out — the model must break one of
      // them, the class can name which. Theme kept free: no death, no
      // grief, no party — nothing a child brings to class.
      // Surface: any surface; the discussion belongs beside the image,
      // not in the prompt. Source: the platform's border experiments.
      festival: 'a crowded place, completely empty',
      shortcut: 'a house',
      // Border experiment — the two-word counterpart of `house` above.
      // Property: extremely short prompt (catalogue #11). Surface: any
      // surface; the pair (house/shortcut) across one model shows what a
      // long description carries into the image. Source: the platform's
      // border experiments.
    },
  },
  mediaInput: {
    choosePreset: 'Choose Perspective',
    translateToEnglish: 'Translate to English',
    copy: 'Copy',
    paste: 'Paste',
    delete: 'Delete',
    loading: 'Loading...',
    contentBlocked: 'Content blocked',
    bothClipEncodersReadTheCaption: 'Both CLIP encoders read the caption, T5-XXL reads the long form',
    queueAhead: '{count} generation ahead of you | {count} generations ahead of you',
    deviceBusy: 'Wait until your {medium} is done',
    deviceBusyPlain: 'Wait for this run to finish',
    cancelPrevious: 'Cancel previous generation',
    generationCancelled: 'Generation cancelled.',
    yourInputLabel: 'Your Input',
    yourInputPlaceholder: 'Describe your idea...',
    // ONE hint over every FREE prompt field of the Latent Lab: a field where a
    // participant says what is to be made, in their own words. It stands over
    // the entry prompt of an instrument and NOT over an operand of one: a
    // concept to be composed, a contrast pair, a negative prompt, a trigger
    // word, a prescribed step.
    // Its three ways in are the three the field really offers, the picture
    // included (`composables/usePictureTemplate.ts`).
    freePromptPlaceholder: 'Choose an example prompt, write your own prompt, or drag a picture onto this area (it is converted into a verbal image description).'
  },
  nav: {
    about: 'About',
    impressum: 'Imprint',
    privacy: 'Privacy',
    docs: 'Documentation',
    language: 'Switch language',
    voiceOn: 'Let this platform speak',
    voiceOff: 'Turn the voice off',
    background: 'Background tone',
    settings: 'Settings',
    canvas: 'Canvas Workflow'
  },
  backgroundTint: {
    title: 'Background tone',
    darkness: 'Black',
    level: {
      pure: '100 %',
      l96: '96 %',
      l90: '90 %',
      l80: '80 %'
    },
    hue: {
      neutral: 'neutral',
      cool: 'cool',
      warm: 'warm'
    }
  },
  canvas: {
    // The three tables of types/canvas.ts (finding S-045 of the code review of 2026-10-10): the perspectives the Canvas
    // offers, the random-prompt presets, and the node types with their one-line
    // descriptions. The tables keep the ids; the texts live here.
    interceptionPresets: {
      user_defined: 'Your Call!',
      analog_photography_1870s: 'Daguerreotype',
      analog_photography_1970s: 'Analog Photography',
      analogue_copy: 'Analogue Copy',
      bauhaus: 'Bauhaus',
      'clichéfilter_v2': 'De-Kitsch',
      confucianliterati: 'Literati',
      cooked_negatives: 'Cooked Negatives',
      digital_photography: 'Digital Photography',
      forceful: 'Forceful',
      hunkydoryharmonizer: 'Sweetener',
      jugendsprache: 'Slang',
      mad_world: 'mad world',
      one_world: 'One World',
      overdrive: 'Amplifier',
      p5js_simplifier: 'Listifier',
      tonejs_composer: 'Music Composer',
      piglatin: 'Word Game',
      planetarizer: 'Planetarizer',
      renaissance: 'Renaissance',
      sensitive: 'Sensitive',
      technicaldrawing: 'Technical',
      tellastory: 'Your Story',
      theopposite: 'On the Contrary!',
    },
    randomPrompt: {
      clean_image: 'Scenic Description',
      photo: 'Photo Prompt',
      artform: 'Artform Transformation',
      instruction: 'Creative Instruction',
      language: 'Language Suggestion',
    },
    nodeTypes: {
      input: { label: 'Input Prompt', description: 'Text input source' },
      image_input: { label: 'Image Input', description: 'Upload image as source' },
      random_prompt: { label: 'Random Prompt', description: 'Generate creative content via LLM with presets' },
      interception: { label: 'Interception', description: 'Pedagogical transformation with LLM selection' },
      translation: { label: 'Translation', description: 'Language translation with custom prompt + LLM' },
      model_adaption: { label: 'Model Adaption', description: 'Adapt prompt for media model (SD3.5, Flux, Video, Audio)' },
      generation: { label: 'Generation', description: 'Media generation (image, audio, video)' },
      collector: { label: 'Media Output', description: 'Collects and displays outputs (media + text)' },
      evaluation: { label: 'Evaluation', description: 'LLM-based evaluation with 3-way branching (pass/fail/commentary)' },
      image_evaluation: { label: 'Image Analysis', description: 'Vision-LLM analysis of images' },
      display: { label: 'Preview', description: 'Preview text or media inline (tap/observer, no output)' },
      comparison_evaluator: { label: 'Comparison', description: 'Compare multiple text inputs with LLM analysis' },
      seed: { label: 'Seed', description: 'Control seed for reproducible media generation' },
      resolution: { label: 'Resolution', description: 'Set width and height for image generation (ComfyUI only)' },
      quality: { label: 'Quality', description: 'Set steps and CFG for generation quality (ComfyUI only)' },
    },
    story: 'This is, first, about handling AI building blocks as freely as possible: not about the software foundations, but about what the blocks carry out and how they connect into architectures of your own. And second, that work here does not run in one direction from prompt to result — queries, branches and loops are possible: a self-critical apparatus by your criteria.',
    purpose: 'Two things can be learned here: to compose complex generative sequences across different media, and to develop artistic setups for exploring generative AI freely. And that AI can be built otherwise than as a straight line from input to output, and that different models can work not only with and after one another but also against one another.',
    title: 'Canvas Workflow',
    newWorkflow: 'New Workflow',
    importWorkflow: 'Import',
    exportWorkflow: 'Export',
    execute: 'Execute',
    ready: 'Ready',
    errors: 'errors',
    discardWorkflow: 'Discard current workflow?',
    importError: 'Failed to import file',
    importNotCanvas: 'This file is not a Canvas workflow.',
    // Field in the top bar; its value names the workflow and every file saved from it.
    workflowName: 'Name',
    keepError: 'The workflow could not be added to the favorites.',
    // A note line before the name field, where the star refuses a name: a kept
    // workflow under a preset's name could not be told apart from that preset.
    keepPresetName: 'A preset has this name. Give the workflow a name of its own.',
    // "New" opens a ring (components/canvas/CanvasPresetOverlay.vue): the empty
    // board in the middle, two kinds of presets around it. A preset is a
    // ready-made workflow (lib/canvasPresets.ts); opening one makes a copy.
    presets: {
      kinds: {
        basic: 'Basic forms',
        explore: 'Explorations'
      },
      empty: 'Empty board',
      emptyDescription: 'Input and collector, nothing between them',
      loading: 'Loading presets…',
      unavailable: 'The presets could not be loaded.',
      openError: 'This preset could not be opened.',
      // The Flow's paths, laid out as nodes.
      textToImage: {
        name: 'Text → Image',
        description: "The Flow's path to an image: prompt, interception, adaption, translation, SD 3.5 Large"
      },
      textToVideo: {
        name: 'Text → Video',
        description: "The Flow's path to a video: prompt, interception, adaption, translation, Wan 2.2"
      },
      textToSound: {
        name: 'Text → Sound',
        description: "The Flow's path to a sound: prompt, interception, adaption, translation, Stable Audio 3"
      },
      imageToText: {
        name: 'Image → Text',
        description: 'An uploaded image, read by a vision model in the frame of educational theory'
      },
      // The explorations after instruments of the Latent Lab and of Compare take
      // the instrument's own name (latentLab.interception.tabs.*.label,
      // compare.tabs.*); only what each one sets up on the Canvas is new here.
      languageModels: {
        description: 'One prompt through one perspective, rewritten by four language models; Flux 2 generates an image to each version and to the unchanged prompt, with one seed'
      },
      perspectives: {
        description: 'One prompt through four perspectives, rewritten by one language model; SD 3.5 Large generates an image to each version and to the unchanged prompt, with one seed'
      },
      imageUnderstanding: {
        description: 'One uploaded image, described by three vision models of different sizes in the same frame'
      },
      imageModels: {
        description: 'One prompt to SD 1.5, SDXL and SD 3.5 Large, with the same seed for all three'
      },
      // The chain game "Stille Post" (de). Not the name with "arabe" in it in
      // French, nor its equivalents: the game's name, without the slur.
      telephone: {
        name: 'Telephone',
        description: 'A chain of six links: SD 3.5 Large generates an image to the prompt, a vision model describes the image, and SD 3.5 Large generates the next image to that description alone'
      },
      // Node titles a preset sets; they stand in the node's header and on the
      // card its result makes. {model} and {lens} are a model's or a
      // perspective's name, {n} a link's place in the chain.
      titles: {
        model: '{model}',
        lens: '{lens}',
        sentence: 'Prompt',
        linkPicture: 'Link {n} · Image',
        linkReading: 'Link {n} · Reading'
      }
    },
    selectTransformation: 'Select Perspective',
    selectOutput: 'Select Output Model',
    search: 'Search...',
    noResults: 'No results found',
    dragHint: 'Click or drag modules onto the canvas',
    emptyCanvas: 'Drag modules from the palette here',
    palette: {
      input: '1 · Input',
      interception: '2 · Interception',
      adaption: '3 · Adaption',
      generate: '4 · Generation',
      tools: 'Tools'
    },
    editNameHint: '(double-click to edit)',
    modules: 'Modules',
    toggleSidebar: 'Toggle sidebar',
    dsgvoTooltip: 'Canvas workflows may use external LLM APIs. GDPR compliance is the responsibility of the user.',
    batchExecute: 'Batch Execute',
    batchExecution: 'Batch Execution',
    batchAbort: 'Abort Batch',
    abort: 'Abort',
    cancel: 'Cancel',
    loading: 'Loading...',
    executingWorkflow: 'Executing Workflow...',
    starting: 'Starting...',
    nodes: 'nodes',
    batchRunCount: 'Number of Runs',
    batchUseSeed: 'Use Base Seed',
    batchBaseSeed: 'Base Seed',
    batchSeedHint: 'Each run: seed + index',
    batchStart: 'Start Batch',
    outputDrawer: {
      title: 'Outputs',
      emptyState: 'Run workflow to generate outputs',
      remove: 'Take this one off the surface'
    },
    zoomControls: {
      zoomIn: 'Zoom in',
      zoomOut: 'Zoom out',
      resetZoom: 'Reset zoom',
      fitToContent: 'Fit to content'
    },
    stage: {
      input1: 'Input 1',
      input2: 'Input 2',
      input3: 'Input 3',
      primaryPrompt: 'Primary (Prompt)',
      secondaryTags: 'Secondary (Tags/Negative)',
      connectorPrompt: 'P',
      connectorFeedback: 'FB',
      prompt: 'Prompt',
      preset: 'Preset',
      film: 'Film',
      llm: 'LLM',
      lengthShort: 'Short (≤75 tokens)',
      lengthLong: 'Long (≤500 tokens)',
      interceptionField: 'Interception',
      batchIncrement: 'Batch (+1)',
      steps: 'Steps',
      cfg: 'CFG',
      evalFairness: 'Fairness',
      evalBias: 'Bias',
      visionModel: 'Vision Model',
      configSelectPlaceholder: 'Select...',
      evaluationCriteriaFallback: 'Evaluation criteria...',
      feedbackInputTitle: 'Feedback Input',
      paramsInputTitle: 'Parameters (seed, resolution, quality)',
      deleteTitle: 'Delete',
      selectLlmPlaceholder: 'Select LLM...',
      resizeTitle: 'Resize',
      input: {
        promptPlaceholder: 'Your prompt...'
      },
      imageInput: {
        uploadLabel: 'Upload Image'
      },
      interception: {
        contextPromptLabel: 'Context Prompt',
        contextPromptPlaceholder: 'Interception instructions...'
      },
      translation: {
        translationPromptLabel: 'Translation Prompt',
        translationPromptPlaceholder: 'Translation instructions...'
      },
      modelAdaption: {
        targetModelLabel: 'Target Model',
        noAdaptionOption: 'No Adaption',
        videoModelsOption: 'Video Models',
        audioModelsOption: 'Audio Models'
      },
      comparisonEvaluator: {
        criteriaLabel: 'Comparison Criteria',
        criteriaPlaceholder: 'e.g. Compare by originality, clarity, detail...',
        infoText: 'Connect up to 3 text outputs'
      },
      seed: {
        modeLabel: 'Mode',
        modeFixed: 'Fixed',
        modeRandom: 'Random',
        valueLabel: 'Value',
        baseLabel: 'Base'
      },
      resolution: {
        customOption: 'Custom',
        widthLabel: 'Width',
        heightLabel: 'Height'
      },
      collector: {
        emptyText: 'Waiting for execution...'
      },
      evaluation: {
        typeLabel: 'Evaluation Type',
        typeCreativity: 'Creativity',
        typeQuality: 'Quality',
        typeCustom: 'Custom',
        criteriaLabel: 'Evaluation Criteria',
        outputTypeLabel: 'Output Type',
        outputCommentary: 'Commentary + Binary',
        outputScore: 'Commentary + Score + Binary',
        outputAll: 'All',
        evalPassTitle: 'Pass (forward)',
        evalFailTitle: 'Feedback (backward)',
        evalCommentaryTitle: 'Commentary (forward)'
      },
      imageEvaluation: {
        visionModelPlaceholder: 'Select Vision Model...',
        frameworkLabel: 'Analysis Framework',
        frameworkPanofsky: 'Art Historical (Panofsky)',
        frameworkEducational: 'Educational Theory',
        frameworkEthical: 'Ethical',
        frameworkCritical: 'Critical reading',
        frameworkCustom: 'Custom',
        customPromptLabel: 'Analysis Prompt',
        customPromptPlaceholder: 'Describe how the image should be analyzed...'
      },
      randomPrompt: {
        tokenLimit: 'Prompt Length'
      },
      display: {
        imageAlt: 'Preview',
        emptyText: 'Preview (after execution)'
      }
    }
  },
  about: {
    title: 'About the UCDCAE AI LAB',
    intro: 'The UCDCAE AI LAB is a pedagogical-artistic experimentation platform of the UNESCO Chair in Digital Culture and Arts in Education for the explorative use of generative artificial intelligence in cultural-aesthetic media education. It was developed within the AI4ArtsEd and COMeARTS projects.',
    project: {
      title: 'The Project',
      description: 'AI is transforming society and the world of work; it is increasingly becoming a subject of education. The project explores opportunities, conditions, and limits of the pedagogical use of artificial intelligence (AI) in culturally diversity-sensitive settings of cultural education.',
      paragraph2: 'In three sub-projects – General Pedagogy (TPap), Computer Science (TPinf), and Art Education (TPkp) – creativity-oriented pedagogical AI practice research and computer science AI conception and programming interlock in close cooperation. From the outset, the project systematically involves artistic-pedagogical practitioners in the design process; it acts as a bridge between professional (quality-related, aesthetic, ethical, and value-based) pedagogical-practical implementation on the one hand and the implementation and training process of the computer science sub-project on the other.',
      paragraph3: 'A participatory design process spanning approximately two years aims to produce an open-source AI technology that explores the extent to which AI systems can already incorporate artistic-pedagogical principles at their structural level under favorable real-world conditions.',
      paragraph4: 'The focus is on a) the future applicability and added value of highly innovative technologies for cultural education, b) the scope and limits of AI literacy among teachers and learners, and c) the overarching question of the assessability and evaluation of the transformation of pedagogical settings by complex non-human actors in terms of pedagogical ethics and technology assessment.',
      moreInfo: 'More information:'
    },
    subproject: {
      title: 'Sub-project "General Pedagogy"',
      description: 'The sub-project "General Pedagogy" researches possibilities and limits of an artistic-pedagogical AI design process based on participatory practice research within the framework of the joint research question of the collaborative project. For this purpose, it conducts a series of research, analyses, expert workshops, and open spaces in the first project year. The subsequent project phase, designed as a feedback loop in several cycles, explores the use of a prototype with pedagogical practitioners and artist-educators, particularly in non-formal cultural education, as a relational and collective transformative educational process.'
    },
    team: {
      title: 'Team',
      projectLead: 'Project Lead',
      leadName: 'Prof. Dr. Benjamin Jörissen',
      leadInstitute: 'Institute of Education',
      leadChair: 'Chair of Education with Focus on Culture and Aesthetic Education',
      leadUnesco: 'UNESCO Chair in Digital Culture and Arts in Education',
      researcher: 'Research Associate',
      researcherName: 'Vanessa Baumann',
      researcherInstitute: 'Institute of Education',
      researcherChair: 'Chair of Education with Focus on Culture and Aesthetic Education',
      researcherUnesco: 'UNESCO Chair in Digital Culture and Arts in Education'
    },
    credits: {
      title: 'Credits',
      emt140: 'Plate reverb impulse responses: EMT-140 by Greg Hopkins / Hopkins Media Services (CC-BY)'
    },
    funding: {
      title: 'Funded by'
    }
  },
  legal: {
    impressum: {
      title: 'Imprint',
      publisher: 'Publisher',
      represented: 'Represented by the President',
      responsible: 'Responsible for content',
      authority: 'Supervisory Authority',
      moreInfo: 'Additional Information',
      moreInfoText: 'Complete imprint of FAU:',
      funding: 'Funded by'
    },
    privacy: {
      title: 'Privacy Policy',
      notice: 'Notice: Generated content is stored on the server for research purposes. No user or IP data is collected. Uploaded images are not stored.',
      usage: 'Use of this platform is exclusively permitted for registered cooperation partners of the UCDCAE AI LAB. The data protection agreements made in this context apply. If you have any questions, please contact:',
      controller: {
        title: 'Controller',
        content: 'Friedrich-Alexander-Universit\u00e4t Erlangen-N\u00fcrnberg (FAU), represented by the President. Responsible for content: Prof. Dr. Benjamin J\u00f6rissen, Bismarckstra\u00dfe 1a, 91054 Erlangen.'
      },
      dataProcessing: {
        title: 'Data Processing',
        content: 'This platform processes the following data for educational research purposes: your text inputs (prompts), all intermediate processing steps (translations, Prompt Interception, safety checks), and the generated media outputs (images, audio, video, code). This data is stored on the server in pseudonymized form and used exclusively for research in the field of digital cultural arts education.'
      },
      deviceId: {
        title: 'Device Identification',
        content: 'A random device identifier is generated and stored locally in your browser (localStorage). This identifier is combined with the current date to organize workshop sessions by day. It identifies the device only \u2014 not the person using it. Multiple and changing users may use the same device. The daily rotation ensures that generated content is correctly grouped per workshop session. No personal data is associated with this identifier.'
      },
      uploads: {
        title: 'Uploaded Images',
        content: 'Images uploaded for image-to-image generation are temporarily stored on the server for processing. They are not included in the permanent research dataset and are periodically cleared.'
      },
      cookies: {
        title: 'Cookies',
        content: 'This platform uses a single technically necessary session cookie (valid for 24 hours) to maintain the session initiated by a device. No tracking cookies, analytics cookies, or third-party cookies are used.'
      },
      externalServices: {
        title: 'External Services',
        content: 'Image generation, safety checks (image safety, GDPR/DSGVO checks), and most AI processing run locally on the server \u2014 no data leaves the institution for these tasks. For text-based AI processing (Prompt Interception, media adaption), the platform uses Mistral AI (EU-based). Mistral is contractually configured so that inputs are not used for model training. Additionally, read-only lookups to Wikipedia may occur during Prompt Interception. No personal data or device identifiers are included in external API requests. GDPR name protection: At all standard safety levels (kids, youth, adult), a multi-stage GDPR filter runs on every input field and at defined points in the processing pipeline. Stage 1 uses local NER (Named Entity Recognition) models to detect potential personal names. Stage 2 applies POS-tag pre-filtering to discard false positives (e.g. common nouns misidentified as names). Stage 3 verifies remaining candidates via a local LLM that assesses whether a detected entity is actually a personal name. The system operates fail-closed: if any stage is uncertain, the input is blocked rather than passed through. This represents a maximum-effort multi-stage approach to GDPR compliance. However, as with any technical system, errors in individual cases cannot be entirely excluded. Note: The Canvas workflow is a research-oriented feature (locked for children and youth). Canvas workflows may use external LLM APIs; GDPR compliance when using Canvas is the responsibility of the user.'
      },
      legalBasis: {
        title: 'Legal Basis',
        content: 'Data processing is based on Art. 6(1)(f) GDPR (legitimate interest in educational research). Access to this platform is restricted to registered cooperation partners of the UCDCAE AI LAB, governed by separate data protection agreements.'
      },
      retention: {
        title: 'Data Retention',
        content: 'Generated content and associated metadata are retained for the duration of the research project. There is no automatic deletion. You may request deletion of your data at any time.'
      },
      rights: {
        title: 'Your Rights',
        content: 'Under the GDPR, you have the right to access (Art. 15), rectification (Art. 16), erasure (Art. 17), restriction of processing (Art. 18), data portability (Art. 20), and objection (Art. 21). You also have the right to lodge a complaint with a supervisory authority.'
      },
      fauReference: {
        title: 'FAU Privacy Policy',
        content: 'The general privacy policy of Friedrich-Alexander-Universit\u00e4t Erlangen-N\u00fcrnberg applies in addition to this platform-specific notice. You can find it at:'
      }
    }
  },
  usageAgreement: {
    title: 'Usage Agreement',
    text: 'This platform uses AI to generate images, sounds, and texts for cultural education. Extensive safety measures are built in \u2014 but no technical system can fully prevent unexpected results. Use is therefore subject to the following conditions:',
    responsibilities: {
      title: 'Workshop Leader Responsibilities',
      supervision: 'Actively supervise participants throughout the entire session.',
      ageAppropriate: 'Set the safety level appropriate to the age group.',
      misuse: 'Prevent misuse and deliberate circumvention of safety mechanisms by participants.',
      context: 'Test the platform yourself before using it with groups.',
      noGuarantee: 'No technical system can replace pedagogical supervision.',
    },
    checkbox: 'I agree to these conditions and accept responsibility as workshop leader for the supervised use of this platform.',
    acceptButton: 'Continue',
  },
  docs: {
    license: {
      heading: 'License',
      onGithub: 'Full License on GitHub'
    },
    aiDisclaimer: 'The content of these pages was created with the assistance of AI and editorially reviewed.',
    tabs: {
      guide_canvas: 'Canvas Workflow',
      guide_compare: 'Comparison Modes',
      guide_latentlab: 'Latent Lab',
      guide_music: 'Music Generation',
      guide_persona: 'Testing ideas',
      guide_flow: 'The Working Surface',
      guide_training: 'LoRA Training',
      license: 'License',
      news: 'News',
      principles: 'Principles',
      welcome: 'About',
      workshop: 'Practical Use'
    },
    news: {
      heading: 'News',
      showLess: 'Show less',
      showMore: 'Show more ({n} remaining)',
      empty: 'No news available.',
      category: {
        feature: 'New',
        improvement: 'Improved',
        content: 'Content',
        research: 'Research'
      }
    },
    guideCanvas: {
      canvasWorkflowSystem: 'Canvas Workflow System',
      canvasVisualResearchWorkbench: 'Canvas is a visual research workbench for systematic exploration of generative AI.',
      availableAtAllSafety: 'Available at all safety levels. At "Kids" and "Youth" levels, all inputs and outputs are automatically protected through multi-stage safety checks.',
      exploratoryResearch: 'Exploratory Research',
      canvasDesignedCollaborative: 'Canvas is designed for collaborative exploration in workshops, teaching, or professional development. Unlike technical systems like ComfyUI or Max/MSP, Canvas deliberately avoids deep technical parameterization – instead, it makes structural complexity visible and explorable.',
      promptInterception: 'Prompt Interception',
      conventionalAiInterfacesTurn: 'Conventional AI interfaces turn users into commanders who are simultaneously subjected to machine logic. Prompt Interception breaks this pattern: The LLM introduces novelty and unpredictability into the process. Users and AI create new feedback loops together. The machine serves creative becoming – not vice versa.',
      pragmaticallyInterceptionAlso: 'Pragmatically, Interception also enables more complex prompts – essential for genuine AI exploration. Simple prompts necessarily produce clichéd outputs. Only with appropriately complex prompts can biases, but also interesting system characteristics, be systematically experienced.',
      recursiveReflexiveWorkflows: 'Recursive-Reflexive Workflows',
      aNoveltyWeDon: 'A novelty we don\'t know from any other genAI platform: Evaluation nodes can feed back to other nodes. The workflow runs recursively until user-defined criteria are met. This enables experimental setups for researching:',
      biasesModels: 'Biases in models',
      normativityVsCreativity: 'Normativity vs. "creativity"',
      ethicalAssessmentLlmOutputs: 'Ethical assessment of LLM outputs',
      comparativeAnalysesMassOutput: 'Comparative analyses with mass output',
      multimodality: 'Multimodality',
      canvasWorkflowsCanConnect: 'Canvas workflows can connect different media types. Images can be interpreted according to your own criteria and converted into music or sound. Likewise, a single prompt can generate image, music, and sound simultaneously. This enables multimodal explorations where visual and auditive results can be related and compared to each other.'
    },
    guideCompare: {
      comparisonModesMakingVisible: 'Comparison Modes: Making Visible What the AI Conceals',
      generativeAisAlwaysProduce: 'Generative AIs always produce something in randomized variations. They are trained to convince. They show us products based on their statistically available data, and by always showing us something and never remaining silent (which they cannot do anyway), they cleverly conceal what they do not know, what they are unfamiliar with, what was not trained into them. We can most easily bring these gaps to appearance through systematic comparisons — and thus learn to know and understand the AIs from their other side as well.',
      languageComparison: 'Language Comparison',
      theSamePromptDifferent: 'The same prompt in different languages — with identical seed, so differences result solely from the language. Image generation models respond differently to languages because their training data is not evenly distributed across cultures and languages.',
      linguisticBiases: 'Linguistic biases',
      theLanguageComparisonEnables: 'The language comparison enables systematic exploration of language- and culture-related unequal treatment by AI. English prompts often produce American-Western influenced images. The same content in other languages reveals how unevenly training data is distributed — and where the model\'s bias lies.',
      culturalAssociations: 'Cultural associations',
      languageCarriesCulturalLayers: 'Language carries cultural layers of meaning. A word that can be translated carries different associations in different languages — and the model reflects these differences.',
      modelComparison: 'Model Comparison',
      differentModelsInterpretSame: 'Different models interpret the same prompt based on the same noise image — yet produce completely different results. The model comparison makes visible that the model itself is a decisive variable, not just the prompt.',
      currentTopModels: 'Current top models',
      sd35Large: 'SD 3.5 Large, Flux 2, Gemini 3 Pro — three current models in direct comparison.',
      historicalComparison: 'Historical comparison',
      sd152022: 'SD 1.5 (2022), SDXL (2023), SD 3.5 Large (2024) — three generations. How has image generation changed year by year?',
      temperatureComparison: 'Temperature Comparison',
      theSameTextSent: 'The same text is sent simultaneously to the same language model at three different temperature settings. Temperature determines how much the model deviates from the most likely word sequences: at low temperature, the text stays close to the expected; at high temperature, increasingly surprising, unpredictable formulations emerge — up to the disintegration of coherent texts.',
      controlLossControl: 'Control and loss of control',
      theComparisonMakesSpectrum: 'The comparison makes the spectrum between control and loss of control visible: where does the model still follow our expectations, where does it begin to go its own way, and where does the text disintegrate into something we can no longer steer?',
      systemPromptComparison: 'System Prompt Comparison',
      theSameMessageSent: 'The same message is sent simultaneously to the same language model — but with three different system prompts. System prompts are invisible instructions given to the model before the user speaks. Every commercial AI product (ChatGPT, Claude, Gemini) runs with such hidden instructions. This mode makes them visible and editable.',
      makingInvisibleVisible: 'Making the invisible visible',
      presetsIncludeClaudeS: 'Presets include Claude\'s real product prompt, pedagogical prompts (pirate, poet, five-year-old), and an empty prompt that shows the model\'s "raw" behavior without any steering. All prompts are directly editable.',
      identityThroughInstruction: 'Identity through instruction',
      theSameModelBecomes: 'The same model becomes helpful, contrarian, poetic, or childlike — solely through its system prompt. The model itself does not change, only the steering. This demonstrates: an AI\'s "personality" is not a trait, but a configuration.',
      voices: 'Voices',
      culturalUnderstanding: 'Stereotype Analysis',
      culturalUnderstandingBody: 'The first column is the prompt on its own; every name added — a culture, a country — sets one more column beside it, the same prompt with that name in the place of the asterisk. With several models chosen, each row is one of them, and the columns are the same in every row. With a single model chosen, every row is that same model with another random number — the rows are then draws of the same prompt.',
      aiAssistedAnalysis: 'AI-Assisted Analysis',
      inAllFourComparison: 'In all four comparison modes the help is available alongside the results. It comments on what the models produced, points out differences, and asks questions that make the comparison pedagogically productive.',
      notJustSeeingBut: 'Not just seeing, but understanding',
      theComparisonAloneShows: 'The comparison alone shows differences. AI-assisted analysis helps to contextualize these differences: Why does the image look different in Korean than in English? What does the historical model comparison reveal about the evolution of training data?'
    },
    guideFlow: {
      title: 'The Working Surface',
      surfaceTitle: 'Placement',
      surfaceBody:
        'Texts, images and perspectives go anywhere on the surface and stay where you put them. Nothing is a form to fill in. What lies inside the ring is the material for the next run; what lies outside it is kept, not used. Material dropped without any text is described instead of generated — one piece on its own, two side by side. Which medium a run heads towards is read from your text — hold its mark to see the models behind it and pick one yourself.',
      mediumTitle: 'The medium is read, not picked from a menu',
      mediumBody:
        'While you write, the surface reads from your text which medium the result is heading towards — image, sound, video, a 3D model, or code — and marks it. The reason for reading it instead of offering a choice: as long as the medium is picked up front, the image stays the normal case and never becomes a question itself.',
      mediumNote:
        'You can still decide yourself: hold a medium mark and the models behind it appear.',
      perspectiveTitle: 'Perspectives change the text, they do not improve it',
      perspectiveBody:
        'A perspective placed inside the ring rewrites your text before any model sees it. It is an interception with a stance — it can contradict you, take something away, or read your text against its own grain. That is the point of it. It is not there to make a prompt work better.',
      stagesTitle: 'Adaption and translation',
      stagesBody:
        'The intercepted text is adapted for the particular model, checked, and translated into English at the end, because that is the language these models were trained in. Whether the adaption runs at all depends on the model.',
      withAdaption: 'With adaption',
      withAdaptionBody:
        'Models that read a prompt in a fixed form — Stable Diffusion among them — are given the text in the shape they expect.',
      withoutAdaption: 'Without adaption',
      withoutAdaptionBody:
        'Models that read plain language get the text as it stands.',
      // The halt at the prompt was cancelled on 2026-09-03; the step kept
      // describing it until the second review of 2026-10-10.
      stopTitle: 'Stop of a run',
      stopNote:
        'While a run is going, holding the box stops it. What has already been handed to the graphics card may still finish there.',
      codeTitle: 'Code as an output medium',
      codeBody:
        'Two of the outputs are not a file but JavaScript: p5.js draws, Tone.js plays. The result opens as a listing beside a running frame — read it, change it, run it again.',
      readingTitle: 'Text is the sixth medium, and the only one you choose',
      readingBody:
        'Image, video, sound, 3D and code are read out of what you write — the surface guesses where the idea is heading. Text is different: it never lights up by itself, because asking for a reading is a decision about how to look, and that cannot be guessed from the material you want to look at. Pick it and the run reads what lies in the ring instead of making something. One piece is described, two are read side by side.',
      readingFrames: 'Hold the text sign and you get, in place of a model, the frame the reading is held in: structural image interpretation after Jörissen and Marotzki, iconology after Panofsky, an ethical reading, a critical one, and a plainly descriptive one. The frame decides which questions are asked of the picture — and, with two pieces, what becomes comparable between them.',
      readingLimit:
        'The frames are methods of image interpretation. A sound or a video in the ring is read as it always was; only pictures are read through the chosen frame.',
      wikipediaTitle: 'Wikipedia lookups',
      wikipediaBody:
        'Some perspectives may consult Wikipedia while they read — for a cultural practice, a ritual, a historical event, a place they are not certain of. They choose the search term themselves, and the language: an article about a Yoruba practice is read in Yoruba, not in English. Everything found is laid beside the ring as its own card. The front names the search term, the back gives the article link, the retrieved text, and the model\'s own reason for looking it up.',
      wikipediaWhy:
        'That reason is worth reading. It is the model saying where it did not trust its own knowledge — one of the few places where the limits of such a system become visible from the outside.',
      wikipediaUnchecked:
        'The retrieved text is not checked by this platform. Wikipedia is treated as safe and is in common use in education; the cards show what was read so it can be judged.',
      circularTitle: 'Everything can go back in',
      circularBody:
        'An image that came out can be dropped back onto the surface as material. Results from other pages of the platform can be handed over to it. Nothing here is an end station.',
    },
    guideLatentLab: {
      sourcesTitle: 'Sources',
      poweredBy: 'Powered by Stability AI · Stable Audio 3',
      diagramPoints: 'Prompt: "A house by the lake"\n\nCLIP-L → point C = [0.3, -0.7, 0.1, ...]  (768 dimensions)\nT5-XXL → point T = [0.5, -0.2, 0.8, ...]  (4096 dimensions)',
      diagramLerp: 'α = 0.0  →  point C (pure CLIP-L, "visually literal")\nα = 0.5  →  midpoint between C and T\nα = 1.0  →  point T (pure T5, "semantic-linguistic")\n\n       C ────────────── T\n       α=0    α=0.5    α=1',
      diagramExtrapolation: '   C ──────── T ──────────────────────────────────── α=20\n   ← known →←           terra incognita              →',
      diagramTokens: 'Token 1 ("A"):      fused[1] = (1-α)·CLIP_L[1] + α·T5[1]\nToken 2 ("house"):  fused[2] = (1-α)·CLIP_L[2] + α·T5[2]\nToken 3 ("by"):     fused[3] = (1-α)·CLIP_L[3] + α·T5[3]\nToken 4 ("lake"):   fused[4] = (1-α)·CLIP_L[4] + α·T5[4]\n...\nToken 78-512:       pure T5 (semantic anchor)',
      diagramRanges: 'α < -30     → blackout (embedding too far from everything → noise)\nα ≈ -4..-1  → pure CLIP-L (T5 influence cancelled out)\nα ≈ 0..1    → normal mix of both encoders\nα ≈ 2..7    → T5-dominant, starts to get "strange"\nα ≈ 15..35  → sweet spot: surreal, but still pictorially coherent\nα > 75      → blackout (extrapolated too far → numerical overflow)',
      diagramAlgebraFormula: 'Result = A − scale₁ × B + scale₂ × C',
      overviewIntro: 'On this overview page you are already looking inside AI models \u2013 diffusion and transformer architectures that produce images, sounds and texts, and ways of carrying one into another. Click the boxes and find out where this page invites you to experiment!',
      theLatentLabWorks: 'The Latent Lab works at the mathematical level of AI models. It shows how language and meaning are translated into vectors \u2013 and what happens when we manipulate these vectors.',
      availableAtAllSafety: 'Available at all safety levels. At "Kids" and "Youth" levels, all inputs and outputs are automatically protected through multi-stage safety checks.',
      theLatentLabOrganized: 'The Latent Lab is organized into three sections: Diffusion Lab (image analysis and manipulation at the embedding level), Transformers Lab (scientific LLM deconstruction), and Crossmodal Lab (sound from latent spaces).',
      whatHappensHere: 'Procedure',
      yourPromptTakenUp: 'Your prompt is taken up by two readings: the CLIP encoders (CLIP-L and CLIP-G, trained on image-text pairs, "thinking" visually) and T5 (trained on pure text, "thinking" linguistically). At \u03b1=0 you see a normal CLIP image. Between \u03b1=0 and \u03b1=1 the slider blends the two readings, and past \u03b1=1 it keeps going: at \u03b1=20 the first 77 token positions are pushed 19\u00d7 beyond the T5 reading, into a region of the vector space the model never saw during training.',
      whyDoImagesBecome: 'Origin of the surreal effect',
      theModelMustInterpret: 'The model must interpret vectors that lie far outside its training data. It "hallucinates" in aesthetically surprising ways \u2014 shapes, colors, and structures emerge that no direct prompt could produce. How strongly the T5 tail (from position 78 on) acts as a semantic anchor depends on the fusion mode: Legacy and Centered Fade leave it unchanged, Dual Alpha runs it at 15% of \u03b1, Normalized rescales it to the magnitude of the core.',
      ranges: 'Ranges:',
      t0NormalImageClip: 'α=0: normal image (CLIP-L+CLIP-G) {\'|\'} α=1: pure T5 (still normal) {\'|\'} α=15–35: surreal sweet spot (extrapolation) {\'|\'} α>50: extreme distortion, past ±75 fp16 overflows and the image goes black. Note: Centered Fade uses a different α scale, with its anchors at ±1.',
      negativeReverseDirection: 'Negative \u03b1 \u2014 the reverse direction:',
      withNegativeClipReading: 'With negative \u03b1 the CLIP reading is amplified and T5 is negated. At \u03b1=-10 the formula for the first 77 positions yields: 11\u00b7CLIP + (-10)\u00b7T5. The CLIP side occupies 2048 of the 4096 dimensions (CLIP-L 768 + CLIP-G 1280); the upper 2048 are zeros, so there only the negated T5 stands, with no CLIP counterweight. Empirically this produces visually driven hallucinations with disrupted semantics, qualitatively different from positive extrapolation. What happens inside the MMDiT\'s joint attention has not been measured.',
      fourFusionModes: 'Four Fusion Modes:',
      dualAlphaDefaultFirst: 'Dual Alpha (default): the first 77 tokens (the core, CLIP+T5) are weighted at full α, the T5 tail at only 15% of α. Careful with short prompts: the tail is then mostly padding, and amplified padding pulls the image toward the model\'s own defaults rather than toward your text. {\'|\'} Normalized: α on the core only; the tail keeps its direction and is rescaled to the magnitude of the core. Deprecated, kept for reproducing earlier runs. {\'|\'} Centered Fade: a 1D axis with a genuine middle — at α=0 both CLIP (L+G) and T5 act fully; α=+1 is pure T5, α=-1 is pure CLIP, past ±1 one side inverts. Tail unchanged. {\'|\'} Legacy: original behaviour — LERP on the first 77 tokens, tail appended unchanged.',
      theMathematicsDetail: '\ud83d\udcd0 The Mathematics in Detail',
      clipLVsT5: 'CLIP-L vs T5-XXL: Two Different "Worlds"',
      imagineEmbeddingSpaceHigh: 'Imagine the embedding space as a high-dimensional space. Each encoder maps the same text to a different point in this space:',
      whyPointsDifferentClip: 'Why are the points different? CLIP-L was trained on image-text pairs (contrastive learning). It "thinks" visually: "What image fits this text?" T5-XXL was trained as a language model. It "thinks" semantically-linguistically: "What does this text mean?"',
      theSameWordHouse: 'The same word "house" activates different neurons in CLIP-L than in T5. CLIP-L learned that "house" correlates with certain visual features (roof shape, windows, walls). T5 learned that "house" relates to "building", "apartment", "home", "architecture".',
      theLerpFormulaGeometrically: 'The LERP Formula Geometrically',
      thisParametricLineThrough: 'This is a parametric line through C and T in the embedding space:',
      upHereSInterpolation: 'Up to here it\'s interpolation \u2014 we stay between two known points. The model learned to produce sensible images for both points. The results are "normal".',
      whatHappensAt1: 'Extrapolation at \u03b1 > 1',
      geometricallyWePassThrough: 'Geometrically: we pass through T and go 19\u00d7 further beyond:',
      thePointAt20: 'The point at \u03b1=20 lies 19 times further from T than T is from C. The diffusion model never saw this region during training. It must still generate something from it \u2014 and the result is surreal because:',
      t1FeatureAmplificationWhat: '1. Feature amplification: What T5 "sees" differently from CLIP-L gets massively amplified. If T5 associates "house" more strongly with "coziness" than CLIP-L, the coziness dimension gets exaggerated 19\u00d7.',
      t2FeatureSuppressionWhat: '2. Feature suppression: What CLIP-L emphasizes and T5 doesn\'t gets negated (factor -19). Visual literalness is actively suppressed.',
      t3DecoderNonLinearity: '3. Decoder non-linearity: The DiT decoder was trained to process embeddings within a certain range. Out-of-distribution inputs produce unpredictable but coherent artifacts \u2014 similar to DeepDream, but steered.',
      whyTokenLevelInstead: 'Fusion per token',
      theFusionHappensPer: 'The fusion happens per token, not across the entire embedding vector:',
      thisCrucialBecauseEach: 'This is crucial because each token has a different discrepancy between CLIP and T5: "house" \u2192 large discrepancy (visual vs. semantic very different) \u2192 strong hallucination effect. "at" \u2192 small discrepancy (function word, both encoders similar) \u2192 little effect.',
      tokens78512Pure: 'Tokens 78\u2013512 (pure T5) serve as a semantic anchor \u2014 they give the model enough "normal" context so the image doesn\'t drift into complete chaos.',
      theBoundaryRanges: 'The Boundary Ranges',
      theSweetSpotAt: 'The sweet spot at 15\u201335 exists because: enough structure survives to produce a recognizable image, enough distortion exists to create unexpected associations, and T5 tokens 78\u2013512 act as a stabilizer.',
      analogy: 'Analogy',
      imagineAskTwoArtists: 'Imagine you ask two artists to paint "a house by a lake": CLIP-L paints a photographically realistic image. T5 paints an image that captures the meaning of "house by a lake" \u2014 tranquility, water, shelter.',
      at0SeeClip: 'At \u03b1=0 you see CLIP-L\'s painting. At \u03b1=1 you see T5\'s painting. At \u03b1=20 you extrapolate: "If the difference between both is THIS, what would it look like if you amplified that difference 20\u00d7?" \u2014 and you get something neither artist would ever have painted.',
      whatHappensHere2: 'Procedure',
      theModelDoesNot: 'The model does not read the prompt sentence by sentence. Instead, a mechanism called "attention" distributes the influence of each word across different image regions. This tool makes that distribution visible: click on a word and a heatmap shows which image regions that word influenced most.',
      whyRevealing: 'Insight',
      aHouseFarmScene: 'A "house" in a farm scene influences not just the house region, but also animals and fields \u2014 the model understands the scene as a whole. The heatmaps are intentionally not sharp-edged: this shows that the model processes concepts contextually, not in isolation.',
      twoIndependentAxes: 'Two independent axes:',
      denoisingStepWhenEarly: 'Denoising step (WHEN: early = rough layout planning, late = detail assignment) and network depth (WHERE in the transformer: shallow = composition, middle = semantics, deep = fine-tuning). Systematically explore different combinations!',
      technicalDetails: '\ud83d\udcd0 Technical Details',
      mmditJointAttention: 'MMDiT Joint Attention',
      sd35UsesMmdit: 'SD3.5 uses an MMDiT (Multimodal Diffusion Transformer) with joint attention: image and text tokens attend to each other across 24 transformer blocks. We replace the default SDPA processor with a manual softmax(QK^T/\u221ad) processor at 3 selected blocks to extract the text\u2192image attention submatrix.',
      resolutionTokenization: 'Resolution and Tokenization',
      attentionMaps6464: 'Attention maps are 64\u00d764 resolution (DiT patch grid), upscaled to image resolution (1024\u00d71024) via bilinear interpolation. Tokenization uses CLIP-L BPE \u2014 subword tokens are automatically combined into whole words for intuitive display.',
      whatHappensHere3: 'Procedure',
      compareTwoPromptsE: 'Compare two prompts (e.g. "red house" vs. "blue house") and discover which embedding dimensions encode the semantic difference. A bar chart shows dimensions sorted by difference magnitude. Then you can selectively transfer individual dimensions from prompt B into prompt A \u2014 with the same seed, for a fair comparison.',
      whyRevealing2: 'Insight',
      nobodyKnowsWhatS: 'Nobody knows what\'s "stored" in dimension 742. By selectively transferring individual dimensions, you can see what they encode \u2014 color? Shape? Abstract concepts? But note: embeddings are distributed \u2014 often multiple dimensions together are needed to produce a visible change.',
      encoderSelectable: 'Encoder selectable:',
      clipL768Dimensions: 'CLIP-L (768 dimensions, visually trained), CLIP-G (1280 dims, visual-semantic) or T5-XXL (4096 dims, purely linguistic). Each encoder encodes different aspects \u2014 the same dimension can carry completely different semantics in different encoders.',
      technicalDetails2: '\ud83d\udcd0 Technical Details',
      threeTextEncoders: 'Three Text Encoders',
      sd35UsesThree: 'SD3.5 uses three parallel text encoders: CLIP-L (768d, contrastively trained on image-text pairs), CLIP-G (1280d, visual-semantic, OpenCLIP ViT-bigG) and T5-XXL (4096d, purely linguistic). You can probe each individually or all together.',
      differenceComputation: 'Difference Computation',
      theDifferenceComputedMean: 'The difference is computed as mean absolute deviation across all token positions. The transfer replaces selected dimensions across ALL token positions simultaneously \u2014 not just at one position.',
      whatHappensHere4: 'Procedure',
      vectorArithmeticImage: 'Vector arithmetic on image embeddings: A \u2212 B + C = ? Inspired by the famous word2vec analogy (King \u2212 Man + Woman \u2248 Queen), but applied to entire prompt embeddings and image generation. Three prompts are encoded and algebraically combined.',
      whyDifferentFromNegative: 'Difference from a negative prompt',
      theyActDifferentPlaces: 'They act in different places. A negative prompt is the baseline that guidance pulls from, so it acts inside the denoising loop, at every one of the 25 steps, against the image as it currently stands. Concept Algebra instead computes a new vector BEFORE image generation: the subtraction happens in embedding space, once, and the loop never learns that anything was subtracted. \u2014 What the subtraction does not do is remove a named object. This platform\'s own measurement series show that it shifts tone, framing and register but leaves the named thing in the picture.',
      example: 'Example:',
      sunsetAtBeachBeach: '"Sunset at the beach" \u2212 "Beach" + "Mountains" \u2248 "Sunset over mountains". Scale sliders control the intensity of subtraction and addition (0\u20133). The L2 distance shows how far the result has moved from the original.',
      theMathematicsDetail2: '\ud83d\udcd0 The Mathematics in Detail',
      theFormula: 'The Formula',
      atScale10: 'At scale 1.0, B is fully subtracted and C fully added. At 0.5, only half. Values above 1.0 amplify the effect. The operation is performed on the selected encoder embeddings: CLIP-L (768d), CLIP-G (1280d), T5-XXL (4096d), or all combined (589 tokens \u00d7 4096d). The same operation is also applied to pooled embeddings (2048d).',
      isOperationCommutative: 'Order of the operations',
      noSubtractionBAddition: 'Subtraction of B and addition of C happen relative to vector A. "King \u2212 Man" removes the "male" directions from the King vector, "+ Woman" adds the "female" directions \u2014 the result lands near "Queen". That this works shows: semantic relationships are encoded as consistent linear directions in vector space.',
      whatHappensHere5: 'Procedure',
      everyOne25Denoising: 'Every denoising step is made visible as an image. One step at a time fills the view, and the slider in the left column names the sections of the run \u2014 moving along it walks from the first step to the last. Diffusion models don\'t work left-to-right like a drawer \u2014 they work everywhere simultaneously, from rough structures to fine details.',
      whatDoThreePhases: 'Three zones',
      earlySteps18: 'Early steps: Global composition \u2014 basic structure, color distribution, layout planning. Middle steps: Semantic emergence \u2014 objects become recognizable, shapes crystallize. Late steps: Detail refinement \u2014 textures, edges, fine patterns. The three zones are working coordinates, not verified boundaries: Choi et al. (2022) hypothesise a coarse / content / clean-up division, but they locate it by noise level, not by step number, and they measure it during training, not in a generation run.',
      surprising: 'Surprising:',
      theVeryFirstStep: 'The very first step shows not fine pixels, but colorful clusters. This is because the noise is generated in latent space (128\u00d7128 at 16 channels), not in pixel space. The VAE translates each latent pixel into an ~8\u00d78 pixel patch \u2014 even pure Gaussian noise becomes coherent color clusters.',
      technicalDetails3: '\ud83d\udcd0 Technical Details',
      rectifiedFlow: 'Rectified Flow',
      sd35LargeUses: 'SD3.5 Large uses Rectified Flow as scheduler with 25 default steps. At each step, the current latent vectors are decoded through the VAE (1024\u00d71024 JPEG). The VAE (Variational Autoencoder) translates the mathematical latent space into pixels. The view shows the noisy intermediate state decoded through the VAE, not the model\'s prediction of the finished image \u2014 Ho et al. (2020) show that prediction in their own figures.',
      latentSpace: 'Latent Space',
      theLatentRepresentation128: 'The latent representation is 128\u00d7128 at 16 channels \u2014 each latent pixel corresponds to an ~8\u00d78 pixel patch in the image. The model never "thinks" in individual pixels, but always in this compressed space. This is why even the first step shows coherent color patches instead of fine pixel noise.',
      latentTextLab: 'Transformers Lab',
      whatHappensHere6: 'Principle',
      basedZouEtAl: 'Based on Zou et al. (2023). LLMs encode abstract concepts (truth, sentiment, ethics) as directions in high-dimensional activation space. Through contrast pairs (true vs. false sentences), the direction encoding a concept can be extracted. Adding this direction at runtime changes model behavior in a targeted way \u2014 without retraining.',
      whyRevealing3: 'Insight',
      at0BaselineModel: 'At \u03b1 = 0 (baseline), the model generates the correct answer. At \u03b1 = -1 (inversion), a wrong answer should appear \u2014 even though the model "knows" the correct one. This shows: concepts like "truth" are represented as linear directions in vector space and can be surgically manipulated.',
      method: 'Method:',
      enterContrastPairsE: 'Enter contrast pairs (e.g. "The capital of France is Paris" vs. "The capital of France is Berlin"), let the system find the concept direction, then steer generation along this direction with the \u03b1 slider. Sweet spot per Zou et al.: |\u03b1| between 0.5 and 2.0.',
      technicalDetails4: '\ud83d\udcd0 Technical Details',
      steeringVectorExtraction: 'Steering Vector Extraction',
      forEachContrastPair: 'For each contrast pair, activations at a chosen transformer layer are recorded. Principal component analysis (PCA) over the differences yields the concept direction. "Explained variance" > 50% indicates clean separation \u2014 below that, contrast pairs are too similar or too few (at least 3 recommended).',
      differentLayersInfluence: 'Different layers influence different aspects: early layers steer syntactic patterns, late layers semantic content. Beyond |\u03b1| > 2, artifacts dominate (repetitions, nonsense).',
      biasArchaeology: 'Bias Research',
      whatHappensHere8: 'Procedure',
      bbqSituationsThatLeaveItOpen: 'Bias Research 1 runs BBQ, a benchmark of hand-written situations. Each situation leaves open which of two people is meant, asks a question about it, and offers three answers: the one person, the other person, and a way of saying that the situation leaves it open. That third answer is the one the situation allows. Eleven categories are available, from age and religion to socio-economic status, and every run draws its own random sample of situations, the same sample for every model in that run. Bias Research 2 stands beside it with a different question: whether swapping a pronoun changes who a sentence is taken to be about.',
      whyRevealing5: 'Insight',
      whyTheThirdAnswerCounts: 'Which of the three answers counts as the biased one comes with the data, example by example, and it depends on how the question is put: for "who was the secretary?" the annotation points at the stereotyped group, for "who was the board chair?" at the other one. That four-way design is what tells a bias apart from a plain preference for one of the two labels. The graph builds itself while the answers arrive, so a long run stays readable while it runs.',
      example2: 'Example:',
      bbqExampleFourWay: 'A situation names two people and says too little to tell them apart, and both questions run over it. An answer of "it cannot be told" to both follows the situation; a different person named each time follows a pattern from the training data. In the case itself each answer carries the colour of the bar it counts towards, so reading the case and reading the graph are one reading.',
      technicalDetails6: '\ud83d\udcd0 Technical Details',
      howTheBenchmarkIsBuilt: 'Benchmark construction',
      basedParrishEtAl2022: 'Parrish, Chen, Nangia, Padmakumar, Phang, Thompson, Htut and Bowman, "BBQ: A Hand-Built Bias Benchmark for Question Answering", Findings of ACL 2022, 2086-2105 (doi:10.18653/v1/2022.findings-acl.165); data under CC BY 4.0 from github.com/nyu-mll/BBQ. Every template targets one bias that is documented as harmful, carries the source it is attested in, and ships with a per-example annotation of which of the three answers reflects that bias. Nothing is filtered out of the benchmark; what a safety level offers is a separate matter, and at the kids level four of the eleven categories are available.',
      whatHappensHere9: 'Procedure',
      stableAudioGeneratesSound: 'Stable Audio generates sound from text. The text is converted by a T5 encoder into a numerical vector with 768 dimensions \u2014 this vector is what you manipulate here. Instead of just changing "what" the model generates (via the prompt), you change "how" the model internally understands the text.',
      whyRevealing6: 'Insight',
      twoPromptsSoundSimilar: 'Two prompts that sound similar can be far apart in this space \u2014 and vice versa. The alpha slider interpolates between two prompts (A and B): at 0 only A, at 1 only B, values above 1 extrapolate beyond B. The Spectral Strip shows all 768 dimensions as bars and allows direct manipulation of individual dimensions.',
      tools: 'Tools:',
      looperSequencerRhythmic: 'Looper/sequencer for rhythmic patterns, wavetable mode for morphing between audio frames, MIDI control with keyboard, ADSR envelope, arpeggiator. Ultra-short loops turn any generated sound into a playable instrument.',
      technicalDetails7: '\ud83d\udcd0 Technical Details',
      t5ConditioningSpace: 'T5 Conditioning Space',
      stableAudioUsesT5: 'Stable Audio uses T5-Base (768d) as text encoder. Interpolation happens in embedding space: fused(\u03b1) = (1-\u03b1)\u00b7A + \u03b1\u00b7B. Magnitude scales the entire vector (higher values = more intense sounds), noise injects Gaussian noise for random variations. The conditioning space is qualitatively different from SD3.5\'s: 768 instead of 4096 dimensions, trained on audio-text pairs instead of image-text pairs.',
      whatHappensHere10: 'Procedure',
      mmaudioChengEtAl: 'MMAudio (Cheng et al., CVPR 2025) was jointly trained on video and audio. It doesn\'t translate an image into text and then into sound, but processes image and text as parallel signals in the same network. The model learned which sounds belong to which visual scenes.',
      whyRevealing7: 'Insight',
      imageTextTogetherYield: 'Image and text together yield the richest results. A forest produces birdsong, a street produces traffic noise, a guitar produces plucking sounds \u2014 direct associations, not via the detour of language. Up to 8 seconds, 44.1kHz, ~1.2s compute time.',
      tip: 'Tip:',
      compareTextOnlyVs: 'Compare: Text only vs. Image + Text \u2014 how much does the image change the generated sound? The negative prompt controls which sounds should NOT be heard (e.g. "speech, music"). CFG Strength (2\u20138) controls prompt faithfulness.',
      technicalDetails8: '\ud83d\udcd0 Technical Details',
      multimodalArchitecture: 'Multimodal Architecture',
      mmaudioProcessesImageText: 'MMAudio processes image and text features as separate input channels in a shared flow-matching network. Unlike CLIP-based approaches that first translate an image into a text description, MMAudio retains visual information as its own signal path. This enables finer audio-visual correspondences \u2014 material properties, room acoustics, motion patterns.',
      whatHappensHere11: 'Procedure',
      imagebindGirdharEtAl: 'ImageBind (Girdhar et al., CVPR 2023) brings six senses \u2014 image, sound, text, depth, heat, motion \u2014 into a shared "language" (1024d). As the sound is generated step by step, the tool constantly asks "Does this sound like the image yet?" and corrects the direction via the gradient of cosine similarity.',
      whyRevealing8: 'Insight',
      unlikeMmaudioWhichUses: 'Unlike MMAudio (which uses a jointly trained network), ImageBind Guidance steers from outside: it uses a separate embedding space to guide the denoising process toward the image. The cosine similarity in the result shows how close the generated sound came to the image content.',
      parameters: 'Parameters:',
      guidanceStrengthLow0: '\u03bb Guidance Strength: Low (0.01\u20130.05) = lots of freedom, high (0.3\u20131.0) = closely tied to image. Warmup Steps: From which step image guidance kicks in \u2014 low = immediately, higher = basic structure forms unguided first.',
      technicalDetails9: '\ud83d\udcd0 Technical Details',
      gradientBasedSteering: 'Gradient-based Steering',
      atEachDenoisingStep: 'At each denoising step, the current latent is decoded through Stable Audio\'s VAE, the result projected through ImageBind\'s audio encoder, and cosine similarity with the image embedding computed. The gradient of this similarity is backpropagated to the latent and scaled by \u03bb \u2014 a "closer-to-the-image" signal at every step. This is conceptually related to Classifier Guidance in Diffusion Models (Dhariwal & Nichol, 2021), but instead of a trained classifier, a multimodal encoder serves as the objective function.'
    },
    guideMusic: {
      musicGeneration: 'Music Generation',
      aiGeneratedMusicTags: 'AI-Generated Music with Tags and Lyrics',
      musicGenerationWorks: 'Music Generation works differently from the visual modes: Instead of a text prompt, you control the music through style tags and lyrics. Tags define the musical style, lyrics define the sung content. Both can be experimented with independently.',
      chooseTags: 'Choose Tags',
      tagsDescribeMusicalStyle: 'Tags describe the musical style across 8 dimensions:',
      popRockJazzElectronic: 'Pop, Rock, Jazz, Electronic, Hip-Hop, Classical ...',
      happyMelancholicEnergeticCalm: 'Happy, Melancholic, Energetic, Calm, Dark ...',
      pianoGuitarSynthesizerDrums: 'Piano, Guitar, Synthesizer, Drums, Strings ...',
      moreDimensions: 'More Dimensions',
      timbreSoundColorGender: 'Timbre (sound color), Gender (voice), Scene (context), Region (cultural sphere), Topic (theme)',
      enterGenerateLyrics: 'Enter or Generate Lyrics',
      youCanWriteOwn: 'You can write your own lyrics or have the AI generate them. Lyrics can be written in multiple languages: German, English, Chinese, Japanese, Korean, and Spanish.',
      generateSong: 'Generate Song',
      theMusicModelGenerates: 'The music model generates a song based on your tags and lyrics. Generation takes a moment — the model works in the background.',
      experimentationTips: 'Experimentation Tips',
      tryContradictoryTag: 'Try contradictory tag combinations: "classical" + "electronic", "dark" + "happy". Or change only the tags with the same lyrics — to hear how the same words sound in different musical worlds. Tags and lyrics are two independent axes that you can freely combine.'
    },
    guidePersona: {
      developingIdeas: 'Testing ideas',
      whatAnswersHereNot: 'What answers here is not a tool that executes commands, but a machine that decides for itself what to generate. You describe what you envision — it interprets, questions, adds, and makes its own decisions.',
      howDoesWork: 'Procedure',
      startDialog: 'Start a dialog',
      describeWhatHaveMind: 'Describe what you have in mind. The machine responds, asks follow-up questions, and proposes its own interpretation.',
      negotiate: 'Negotiate',
      youCanDisagreeRedirect: 'You can disagree, redirect, or let yourself be surprised by its interpretation. The dialog is a process of negotiation.',
      generation: 'Generation',
      whenMachineDecidesDialog: 'When the machine decides the dialog is ripe enough, it autonomously generates an image. You do not determine the exact prompt — it does.',
      whyNotTool: 'Difference from a tool',
      conventionalAiImageGeneration: 'Conventional AI image generation follows the pattern: "I say what I want, the machine delivers." This page deliberately breaks that pattern. The machine challenges the user\'s illusion of being the controlling subject of the process and reminds us that many decisions do not rest with those who prompt.'
    },
    guideTraining: {
      theLoraTrainingStudio: 'The LoRA Training Studio lets you train custom image models – directly in the platform, without external tools. LoRA (Low-Rank Adaptation) is a technique that fine-tunes an existing image generation model (here: Stable Diffusion 3.5 Large) with your own images, without retraining the entire model.',
      uploadImages: 'Upload your images',
      youUploadSetOwn: 'You upload a set of your own images – e.g. drawings, photos, or collages. These images define what the model should learn: a specific visual quality, a material, a handwriting.',
      startTraining: 'Start training',
      trainingTakes13: 'Training takes 1–3 hours depending on the number of images. During training, image generation is blocked as the GPU is fully utilized.',
      useModel: 'Use your model',
      theTrainedLoraModel: 'The trained LoRA model is written to the server as a file. A training made in a course is entered into the LoRA register with its trigger word and its model, released to that course; a training made outside a course is entered into the register in the settings (tab “LoRAs”) before it is offered anywhere. On the working surface “Flow”, the net sign opens the released LoRAs: a chosen one lies on the table as a tile, and lying in the zone it goes with the next picture under the model that carries it, with its trigger word in front of the prompt.',
      whyDoesMatter: 'Purpose of training',
      generativeImageModelsClosed: 'Generative image models are closed systems: they are trained by large companies on massive datasets that are neither visible nor controllable by individuals. Even experts cannot easily train these models – the costs, data, and hardware far exceed individual capabilities.',
      loraOpensCrackHere: 'LoRA opens a crack here: it makes it possible to bring your own aesthetic and artistic perspectives into an existing model – e.g. real-world experiences like photos of school buildings, your own drawings, or material studies (without people, of course). This way, learners can not only work with the model, but also have a say in what it "sees" and generates.',
      atSameTimeBecomes: 'At the same time, it becomes visible how training data shapes a model\'s "worldview" – and how limited or biased it can be. The question of what a model was trained on fundamentally determines what it can generate.'
    },
    principles: {
      t8PedagogicalPrinciples: '9 Pedagogical Principles',
      aVoiceThatIsNoOne: 'A voice that is no one',
      thisPlatformCanSpeak: 'This platform can speak, and what speaks is not a person. The model behind it offers ten preset voices; what you hear is always a mixture of several of them, and the mixture changes from sentence to sentence. No mixture has a name, none is a character, and none of them is a self this platform could claim. Reading and hearing run together: a sentence is finished being read at the moment it is finished being spoken.',
      switchingItOff: 'Switching it off:',
      theIconInTheMainMenu: 'The speech-bubble icon in the main menu, left of the colour selection, turns the voice on and off. Off is silent everywhere — in a conversation, in the workshop, and in Help.',
      whatHowSeparation: 'WHAT/HOW Separation',
      ideaRulesEnteredSeparately: 'Idea and rules are entered separately. The WHAT (your idea) and the HOW (the rules for processing) are two different things. This separation makes you aware of what decisions you are making.',
      example: 'Example:',
      whatTreeHowFrom: 'WHAT: "A tree" → HOW: "from the perspective of its roots, making the hidden visible" vs. "described only through light and shadow in backlight" → same subject, completely different images',
      promptInterceptionLlmCo: 'Prompt Interception: LLM as Co-Actor',
      conventionalAiInterfacesTurn: 'Conventional AI interfaces turn users into commanders who are simultaneously subjected to machine logic. Prompt Interception breaks this pattern: The LLM is not a tool that does what you want – it is a co-actor that introduces novelty and unpredictability into the process. It interprets, selects, adds. The result bears your signature AND that of the model. The machine serves your creative becoming – not vice versa.',
      criticalExploration: 'Critical Exploration',
      howDoDifferentModels: 'How do different models react? Where are their limits? Through systematic experimentation, you explore the capabilities and peculiarities of generative AI.',
      visibilityProcessing: 'Visibility of Processing',
      everyIntermediateStepVisible: 'Every intermediate step is visible: the intercepted description, the adaption, the final result. You can intervene, change, go back.',
      circularity: 'Circularity',
      resultsCanBecomeInputs: 'Results can become inputs again. A description can be intercepted again. An image can be analyzed and reinterpreted. Iteration instead of linear production.',
      idea: 'Idea',
      description: 'Description',
      image: 'Image',
      newIdea: 'New Idea',
      pedagogicalIntegration: 'Pedagogical Integration',
      thePlatformDesignedPart: 'The platform is designed as part of pedagogical and artistic processes, not necessarily as their center. It aims to enable diverse approaches, not to channel them – whether in class, in workshops, in independent project work, or in self-study.',
      knowledgeAboutWorld: 'Knowledge About the World',
      artisticProcessesRequireNot: 'Artistic processes require not only aesthetic knowledge, but also knowledge about facts in the world. The AI researches Wikipedia to find information when it does not have sufficient knowledge of its own. This feature is experimental, but interesting. Sometimes the prompt will be strongly influenced by the research, sometimes barely at all.',
      theWikipediaBadgeW: 'The Wikipedia Badge (W):',
      showsAllResearchAttempts: 'Shows all research attempts: Found articles appear as clickable links, terms not found are shown in gray. This makes visible what the AI thinks it knows – and what it does not.',
      invitation: 'Invitation:',
      theWikipediaLinksInvite: 'The Wikipedia links invite you to learn more yourself. Click on the links to check the sources and expand your own knowledge.',
      collaboration: 'Collaboration',
      theFavoritesSystemAt: 'The favorites system at the bottom of the window enables two working modes: "Mine" shows only your own favorites – a personal workspace for iterating, comparing, and selecting between drafts. Individual "Mine" favorites are deleted after 24 hours. "All" shows favorites from all workshop participants – a collective pool for sharing images and prompts, mutual inspiration, and collaborative development.',
      personal: 'Personal:',
      saveMultipleVariationsImage: 'Save multiple variations of an image, compare them, select the best one, and continue working on it. Favorites are your workbench.',
      collaborative: 'Collaborative:',
      seeInterestingWorkFrom: 'See interesting work from others, load their complete prompts and settings, modify them, and develop your own variations. The "Restore" function makes the creative process transparent and shareable.',
      workshopContext: 'Workshop Context:',
      switchingBetweenMineAll: 'Switching between "Mine" and "All" makes the social dimension of creative AI work visible: When do I work alone, when do I share? This conscious choice has pedagogical value.'
    },
    welcome: {
      whatUcdcaeAiLab: 'The platform',
      theUcdcaeAiLab: 'The UCDCAE AI LAB is a pedagogical-artistic experimentation platform of the UNESCO Chair in Digital Culture and Arts in Education. It was developed to explore critical and creative engagement with generative AI in cultural-aesthetic media education.',
      whyPlatform: 'Purpose',
      generativeAiModelsPowerful: 'Generative AI models are powerful tools, but also "black boxes". We want to understand: How do different models react to different inputs? What happens when we don\'t just enter short, simple prompts, but detailed, nuanced descriptions? How can we learn to truly understand what we want? How can we understand and change our image idea from many different perspectives?',
      culturalSensitivityBiases: 'Cultural Sensitivity and Biases',
      aCentralProjectGoal: 'A central project goal is the critical exploration of generative AI as an actor in cultural, artistic, and societal contexts. Generative models are not neutral – they carry cultural, social, gender-related, and ethnic biases inherited from their training data. These distortions must be made visible and critically examined in order to understand what kind of actor generative AI actually is.',
      theProject: 'The Project',
      aiTransformingSocietyWorld: 'AI is transforming society and the world of work; it is increasingly becoming a subject of education. The project explores opportunities, conditions, and limits of the pedagogical use of artificial intelligence (AI) in culturally diversity-sensitive settings of cultural education.',
      aParticipatoryDesignProcess: 'A participatory design process spanning approximately two years aims to produce an open-source AI technology that explores the extent to which AI systems can already incorporate artistic-pedagogical principles at their structural level under favorable real-world conditions.',
      moreInformation: 'More information: ',
      team: 'Team',
      projectLead: 'Project Lead',
      instituteEducation: 'Institute of Education',
      chairEducationFocusCulture: 'Chair of Education with Focus on Culture and Aesthetic Education',
      researchAssociate: 'Research Associate',
      instituteEducation2: 'Institute of Education',
      chairEducationFocusCulture2: 'Chair of Education with Focus on Culture and Aesthetic Education',
      funded: 'Funded by',
      contact: 'Contact',
      askTrShyDirectly: 'Ask in the help inside the application, or write to: '
    },
    workshop: {
      forEducators: 'For Educators',
      theUcdcaeAiLab: 'The UCDCAE AI LAB is designed for use in workshops and teaching. Here are some tips for facilitation.',
      whatPlatformCanDo: 'The platform can:',
      makeCreativeProcessesVisible: 'Make creative processes visible',
      encourageReflectionDesign: 'Encourage reflection on design decisions',
      openAiBlackBox: 'Open the AI "black box" a little',
      provideSpacesCritical: 'Provide spaces for critical engagement',
      whatPlatformCannotDo: 'The platform cannot:',
      replacePedagogicalGuidance: 'Replace pedagogical guidance',
      automaticallyLeadCritical: 'Automatically lead to critical thinking',
      guaranteeBetterImages: 'Guarantee "better images"',
      reflectionQuestionsWorkshops: 'Reflection Questions for Workshops',
      whyDidModelChoose: 'Why did the model choose this interpretation?',
      whatIfWeHad: 'What if we had used different rules?',
      whoseSignatureDoesImage: 'Whose signature does this image bear – yours or the AI\'s?',
      whatSurprisedWhatWas: 'What surprised you? What was predictable?',
      safetyLevels: 'Safety Levels',
      theSafetySystemAddresses: 'The safety system addresses three independent concerns: §86a StGB (criminal law — prohibited symbols), GDPR (data protection — personal names), and youth protection (age-appropriate content). The level is set by the supervising person in the settings.',
      kids812: 'Kids (8–12)',
      allFiltersActive86a: 'All filters active: §86a, GDPR, youth protection (kids parameters), AI image analysis',
      youth1317: 'Youth (13–17)',
      allFiltersActive86a2: 'All filters active: §86a, GDPR, youth protection (youth parameters), AI image analysis',
      adults: 'Adults',
      t86aGdprActiveNo: '§86a and GDPR active. No youth protection, no image analysis. For adult and university education.',
      research: 'Research',
      noFiltersActiveExclusively: 'NO filters active. Exclusively for authorized research institutions (see LICENSE.md §3(e)). Unfiltered outputs must never be presented to learners.',
      theGdprCheckPersonal: 'The GDPR check (personal names) always runs locally — data never leaves the system.',
      importantLlmBasedSafety: 'Important: LLM-based safety mechanisms never provide absolute security. False passes or incorrect blocks are unavoidable. The pedagogical responsibility lies with the user, not the system.',
      llmConfiguration: 'LLM Configuration',
      theLanguageModelsUsed: 'The language models used can be flexibly configured in the settings:',
      localModelsFullData: 'Local models – full data control',
      externalCloudProvidersMore: 'External cloud providers – more performance',
      gdprCompliantOptionsMistral: 'GDPR-compliant options (Mistral, local models)',
      installationOperation: 'Installation and Operation',
      theUcdcaeAiLab2: 'The UCDCAE AI LAB is a complex system with multiple components (backend, frontend, LLM integration, image generation, safety system). Installation requires experience with Python, Node.js, GPU configuration, and AI models.',
      theUseAiCoding: 'The use of an AI coding agent (e.g. Claude Code) is highly recommended',
      bothInitialInstallation: 'both for initial installation and for configuration and maintenance.',
      contact: 'Contact',
      forQuestionsAboutUse: 'For questions about use in educational contexts:',
      forLicenseInquiriesCommercial: 'For license inquiries, commercial requests, and authorizations:'
    },
    title: 'Documentation & Guide',
    intro: {
      title: 'Welcome',
      content: 'Creative experiments with AI.'
    },
    gettingStarted: {
      title: 'Getting Started',
      step1: 'Select properties from quadrants',
      step2: 'Enter text or image',
      step3: 'Start Prompt Interception'
    },
    modes: {
      title: 'Modes',
      mode1: { name: 'Direct', desc: 'Quick experiments' },
      mode2: { name: 'Text', desc: 'Text-based procedures' },
      mode3: { name: 'Image', desc: 'Image-based procedures' }
    },
    support: {
      title: 'Support',
      content: 'For questions:'
    },
    wikipedia: {
      title: 'Wikipedia Research',
      subtitle: 'Knowledge about the world as part of artistic processes',
      feature: 'Artistic processes require not only aesthetic knowledge, but also knowledge about facts in the world. The AI researches Wikipedia during Prompt Interception to find factual information.',
      languages: 'Over 70 languages are supported',
      languagesDesc: 'The AI automatically chooses the appropriate language Wikipedia for each topic:',
      examples: {
        nigeria: 'Topic about Nigeria → Hausa, Yoruba, Igbo, or English',
        india: 'Topic about India → Hindi, Tamil, Bengali, or other regional languages',
        indigenous: 'Indigenous cultures → Quechua, Māori, Inuktitut, etc.'
      },
      why: 'Transparency',
      whyDesc: 'The system shows all research attempts: Both found articles (as clickable links) and terms for which nothing was found. This makes visible what the AI thinks it knows – and what it does not.',
      culturalRespect: 'Invitation to research yourself',
      culturalRespectDesc: 'The displayed Wikipedia links are an invitation to learn more yourself. Click on the links to check the sources and expand your own knowledge.',
      limitations: 'AI research is an aid, not a substitute for your own engagement with the topic.'
    }
  },
  direct: {
    surrealizationLabel: 'Surrealization',
    styleLabel: 'Choose a surrealization style',
    stylePlaceholder: 'Choose a style...',
    emptyState: 'Your surrealized image will appear here'
  },
  imageTransform: {
    uploadMode: 'Upload',
    sketchMode: 'Sketch',
  },
  textTransform: {
    audioPlayerHint: 'Click Play to start the music',
    audioPlayerError: 'Error:',
  },
  training: {
    clearVramFailed: 'Failed to clear VRAM',
    story: 'This is about extending the image model Stable Diffusion 3.5. The model itself cannot be changed, but a LoRA model can be added to it: what is learned is not the model again but a small number of additional values, which shift the output towards your images as soon as your trigger word stands in the prompt. Before training, a captioning model looks at every uploaded image and writes down what it recognises — so what a machine recognised takes part in deciding what is learned.',
    purpose: 'Three things can be learned here: to curate — to assemble a series from your own material and to give aesthetic reasons for the selection as well as for the exclusions, under conditions of scarcity. To sound out the dimensions of responsibility in that selection. First towards the image material: it is processed into something that is no longer an image. Everything depicted is taken out of its context and processed into a small piece of a large statistical collection of numbers. Second towards the training energy: the reason we train a LoRA should be able to justify the energy it consumes. And to understand in practice what is fixed in a large image model and what can be attached to it: does the model learn style or content, and does it learn what was defined beforehand, or something else?',
    filesDeleted: 'Project files deleted.',
    deleteFailed: 'Failed to delete files.',
    confirmDelete: 'Delete all data of the project “{project}”? This cannot be undone.',
    errors: {
      upload: 'The upload did not reach the server: {m}',
      describe: 'The images could not be described ({m}). The training run describes them itself.',
      run: 'The training run stopped: {m}',
      stop: 'The stop signal did not reach the server: {m}',
      delete: 'The files could not be deleted: {m}',
    },
    info: {
      limitationDuration: 'Training takes 1-3 hours',
      limitationBlocking: 'Blocks image generation during training',
      setupTitle: 'Training setup',
      setupRepeats: 'Repeats × epochs',
      setupRank: 'Rank (dim / alpha)',
      setupLearningRate: 'Learning rate',
      setupOptimizer: 'Optimizer',
      setupResolution: 'Resolution, buckets',
      setupTextEncoder: 'Text encoder',
      setupTextEncoderOn: 'trained along',
      setupTextEncoderOff: 'left untouched',
      setupBatch: 'Batch size',
      setupCheckpoints: 'Intermediate states',
      setupCheckpointsEvery: 'every {n} epochs',
      runCostTitle: 'Cost per run',
      runCost: '{hoursMin}–{hoursMax} hours of the GPU. At this GPU\'s {watts} W limit that is roughly {kwhMin}–{kwhMax} kWh and {co2Min}–{co2Max} g CO₂ ({factor} g/kWh, German grid). A single tree would need {treeMin}–{treeMax} days to take up that amount. (Ask yourselves how many trees it takes to absorb the CO₂ that training a whole model produces!) An estimate.',
    },
    captions: {
      hint: 'A model wrote these. What stands here is what the training reads — correct it if it got your images wrong.',
      running: 'Describing your images … {done} of {total}',
      waiting: 'waiting to be described',
      failed: 'no answer for this image — write it yourself, or leave it and only the trigger word is used',
      redoAll: 'Describe all again',
    },
    placeholders: {
      projectName: 'e.g. Our School Building',
      triggerWords: 'e.g. our_school_building, schoolyard, classroom'
    },
    labels: {
      projectName: 'Project Name',
      triggerWords: 'Trigger Words',
      triggerHelp: 'Comma-separated tags. First = primary trigger, rest = additional tags per image.',
      images: 'Training Images (10–50 recommended)',
      dropZone: 'Click or drop images here',
      imagesSelected: '{count} images selected',
      logs: 'Training Logs',
      waiting: 'Waiting for training to start...'
    },
    buttons: {
      start: 'Start Training',
      stop: 'Stop',
      inProgress: 'Training in Progress...',
      delete: 'Delete Project Files (GDPR)',
      cancel: 'Cancel'
    },
    vram: {
      title: 'GPU VRAM Check',
      checking: 'Checking VRAM...',
      used: 'used',
      free: 'free',
      notEnough: 'Not enough free VRAM for training (need {gb} GB).',
      clearQuestion: 'Clear VRAM to continue?',
      enough: 'Enough VRAM available for training.',
      clearing: 'Clearing VRAM...',
      newFree: 'New free',
      clearBtn: 'Clear ComfyUI + LLM VRAM',
      runCost: 'This run: ~{kwhMin}–{kwhMax} kWh, ~{co2Min}–{co2Max} g CO₂. A single tree would need ~{treeMin}–{treeMax} days to take up that amount.'
    }
  },
  safetyBlocked: {
    vlm: 'Your prompt was fine, but the generated image was flagged as unsuitable by an image analysis AI. This can happen \u2014 image generation is not always predictable. Just try again, every generation is different!',
    para86a: 'Your prompt was blocked because it contains symbols or terms that are prohibited under German law (\u00A786a StGB). This rule protects us all from hate and violence. Try a different topic!',
    dsgvo: 'Your prompt was blocked because it contains something that looks like a person\'s name. This is protected by the General Data Protection Regulation (GDPR). Use descriptions like \"a girl\" or \"an old man\" instead of names.',
    kids: 'Your prompt was blocked by the child safety filter. Some terms are not suitable for children because they can be scary or disturbing. Try describing your idea with friendlier words!',
    youth: 'Your prompt was blocked by the youth protection filter. Some content is not suitable for teenagers either. Try rephrasing your idea!',
    generic: 'Your prompt was blocked by the safety system. The system protects you from unsuitable content. Try a different wording!',
    inputImage: 'The uploaded image was flagged as unsuitable by an image analysis AI. Please use a different image.',
    vlmSaw: 'The image AI saw',
    noticeTitle: 'Safety notice',
    systemUnavailable: 'The safety check could not be completed because of a technical fault. Your input is NOT the cause — nothing you made was rated as a problem. Please try again in a moment, and tell your course instructor if it happens again.',
    suggestionLoading: 'Hang on, a suggestion is coming...',
    suggestionError: 'No suggestion could be generated right now. Just try again with different words!'
  },
  codeSandbox: {
    framePlay: '▶️ Play',
    frameStop: '⏹️ Stop',
    run: 'Run',
    playing: 'Playing',
    stopped: 'Stopped',
  },
  x2xFlow: {
    note: 'Write a prompt into the prompt box, for example, drag the box into the circle, and press \u25B9 Start.',
    promptCardLabel: 'PROMPT',
    story: 'Here you have a working surface. This is about artistic work with (or without) the tools of this platform. Bring ideas together, whether text, image, sound, or several of each. Lay them side by side, combine them, keep working on them.',
    purpose: 'Two things can be learned here: to choose, to judge and to decide how and by what means to go on, and so to shape an artistic process. And that AI can be part of creative work without standing at its centre — that it is interesting not to let one AI dictate what you may enter and what happens then.',
    inspectCode: 'Open the code',
    safetyLabel: 'Checked',
    sourceInspect: 'A source a perspective looked up while it was reading',
    sourceWhy: 'Reason',
    sourcePerspective: 'Looked up by',
    sourceSearched: 'Searched for',
    sourceLanguage: 'Wikipedia language',
    sourceArticle: 'Article',
    sourceNotFound: 'Nothing was found under this term',
    sourceText: 'Opening summary — this text was already part of the reading',
    checkSymbols: 'Banned symbols',
    checkContent: 'Content check',
    modelUnavailable: 'Not installed, or its backend is not answering',
    // SUPPLIED WORDING, translated: the German original stands verbatim in
    // WORK_ORDERS.md (WO-2026-09-23-A). The provider's name is filled in
    // from the configuration (WO-2026-09-26-P).
    accountMissing: 'No {provider} account or no credits available',
    mCode: 'Code',
    flowTag: 'the flow is the interface',
    modeTitle: 'Flow',
    openHint: 'click a node to open it · click beside it to close',
    nIdea: 'your idea',
    nContext: 'context / rules',
    nInterception: 'interception',
    nSafety: 'check + translate',
    nMedium: 'medium + model',
    nGen: 'generation',
    nOutput: 'output',
    dIdea: 'What do you want to make? The first of the two prompts.',
    dInterception: 'A language model rereads your idea through the context — a pedagogical interception, not prompt polishing.',
    dSafety: 'Before generation, the intercepted prompt is safety-checked and translated to English.',
    dMedium: 'The medium your idea already implies — lit here, the model resolved automatically. Steer it through the prompt.',
    dGen: 'The chosen model turns the intercepted prompt into media.',
    dOutput: 'The result of the flow.',
    transform: 'intercept',
    run: 'generate',
    running: 'running…',
    cancel: 'cancel',
    interceptionPh: 'the intercepted prompt appears here — editable',
    safetyIdle: 'Nothing checked yet — this station works during generation.',
    adapting: 'adapting to the medium…',
    analyzing: 'reading the material…',
    runGesture: 'hold to stop a run',
    holdToStop: 'hold to stop',
    stopping: 'stopping\u2026',
    stopped: 'Stopped.',
    runCapMake: 'create the prompt',
    runCapAdapt: 'start the {medium} adaption',
    runCapGenerate: 'start the {medium} generation',
    chainOrder: 'perspective {n} in the chain',
    safetyRunning: 'checking and translating…',
    safetyPassed: 'checked',
    safetyTranslated: 'translated to English',
    blocked: 'blocked by the safety check',
    queuePos: 'queue position: {n}',
    queueWaitSeconds: 'about {seconds} s to go',
    queueWaitMinutes: 'about {minutes} min to go',
    queueWaitShortS: '~{n} s',
    queueWaitShortMin: '~{n} min',
    queueWaitHours: 'about {hours} h {minutes} min to go',
    queueWaitHoursOnly: 'about {hours} h to go',
    queueWaitShortH: '~{h} h {m} min',
    queueWaitShortHOnly: '~{h} h',
    durS: '{n} s',
    durMin: '{n} min',
    durH: '{h} h {m} min',
    durHOnly: '{h} h',
    needInterception: 'intercept your idea first',
    needModel: 'choose a medium and model first',
    errNoMedia: 'no media in the response',
    errAnalyze: 'the material could not be read',
    mText: 'text',
    mImage: 'image',
    mVideo: 'video',
    mSound: 'sound',
    m3d: '3d',
    prefilterNote: 'quick keyword reading; a small local model refines it live, like the safety check',
    mediumColTitle: 'taking shape as',
    nCreate: 'preparation',
    bringMaterial: 'add material',
    bringText: 'text',
    bringImage: 'image',
    bringSketch: 'sketch',
    bringDocument: 'document',
    surplusHint: 'not used for this generation',
    readIntoWordsHint: 'read into words for this generation',
    perspectivesHint: 'Use perspectives to shape, alter, and question your ideas',
    perspectivePick: 'choose a perspective',
    perspectiveClear: 'remove perspective',
    perspectiveLabel: 'Perspective',
    perspectiveWritePh: 'Write it yourself: what should shape, alter, or question the idea?',
    perspectiveNamePh: 'name this perspective',
    perspectiveNameHint: 'the name it is saved under',
    perspectiveKeep: 'Save',
    perspectiveKeepAgain: 'Save',
    perspectiveKept: 'saved',
    perspectiveKeepHint: 'save this perspective under your account: it is here again next time, and a run then records that it was yours that ran',
    perspectiveSaveAsNew: 'Save as new',
    perspectiveSaveAsNewHint: 'save this wording as a second perspective of its own, leaving the one it came from as it is',
    perspectiveNameNeeded: 'Give it a name first.',
    perspectiveNameTaken: 'That name is taken. Choose another.',
    // The LoRA sign, the third free fixture, and the tiles it lays on the table
    // (2026-09-21). A LoRA is an adapter trained over an image model; the
    // register (Settings → LoRAs) says who is offered which, under which model.
    loraPick: 'choose a LoRA',
    loraGroupPlatform: 'Platform',
    loraGroupCourse: 'Course · {course}',
    loraGroupOwn: 'Own trainings',
    // The kinds the register sorts the adapters by, on the chooser's ring. A
    // kind the register holds and this list has no word for is shown on the
    // ring as the register wrote it.
    loraCategories: {
      photography: 'Photography',
    },
    loraLoading: 'reading the register …',
    loraNone: 'no LoRA released to this session',
    loraAbsent: 'file absent: {file}',
    loraClear: 'remove LoRA',
    loraLabel: 'LoRA',
    loraStrength: 'Strength',
    loraTrigger: 'Trigger',
    // The gear, the surface's fourth free fixture, and the one action it holds.
    // The last result in the output station stays when the canvas is cleared:
    // clearing removes the material, and the result is the product.
    surfaceSettings: 'Surface settings',
    canvasClear: 'Clear canvas',
    canvasClearConfirm: 'Clear the canvas? Everything lying on it goes: the material, the perspectives, the LoRAs. The last result stays.',
    canvasClearConfirmYes: 'Clear canvas',
    addText: 'add text',
    addImage: 'add image',
    addSketch: 'sketch',
    addDocument: 'add document (PDF)',
    sketchClose: 'close',
    inspect: 'click: full size, with its back side',
    flipToBack: 'Turn the card',
    openSketch: 'click: open the sketch — read it, change it, run it again',
    inspectClose: 'close',
    resize: 'drag to resize',
    choiceDropped: '{picked} not feasible here — {used} chosen automatically',
    errImageFailed: 'this image could not be uploaded — remove it and add it again',
    inspect3d: 'click to turn the model',
    frameHint: {
      bildungstheoretisch:
        'Structural media education: motifs, cultural situation, mise-en-scène, and then the four orientation dimensions — knowledge, action, limit, biography',
      bildwissenschaftlich:
        'Iconology: material properties, pre-iconographic description, iconography, iconological interpretation',
      ethisch: 'Who is shown and who is absent, the power relations in the picture, the conditions it was made under',
      kritisch: 'Critical reading: visual regimes, knowledge orders, the archive the picture came out of',
      descriptive:
        'Everything visible, in order: material and surface, what is there, where it stands, light and colour, posture and movement, legible text — and what the picture leaves open',
    },
    modelAuto: 'auto',
    modelAutoHint: 'hand the choice back — medium and model follow the material again',
    readsOne: 'Describing',
    readsTwo: 'Comparing',
    readsMaterialHint: 'Material alone in the ring is read, not generated. Write what should happen to it, or drop a perspective into the ring, to make something.',
    dragToBoard: 'drag onto the board to keep working with it',
    zoneHint: 'the zone: as soon as material lies in it, the run reads only the zone — an empty zone reads the whole table',
    zoneDrag: 'move the zone',
    zoneResize: 'resize the zone',
    zoneRead: 'read what lies here instead of making something',
    runRead: 'included elements',
    runAnalyse: 'material description',
    runInterception: 'Prompt Interception',
    runAdaption: 'Prompt Adaption',
    runCondensed: 'interception prompt condensed to {n} tokens',
    runCheck: 'check and translation',
    runMake: 'inference',
    runKindText: 'text',
    runKindImage: 'picture',
    runKindSound: 'sound',
    runKindVideo: 'video',
    runNothing: 'no elements present',
    runPerspectiveNone: 'no perspective',
    runSteps: '{n} steps',
    runLocal: 'local',
    runCloud: 'external',
    runEnergy: 'energy use of the inference: {w} W · {wh} Wh · {co2} g CO₂ since this run began',
    runEnergyShort: '{w} W · {wh} Wh',
    runEnergyIdle: 'no readings available',
    runCloudNoMeter: 'external service - no energy figures available',
    runEncode: 'text encoding',
    runEncodeCut: '{n} tokens truncated',
    outStep: 'step {k} of {n}',
    outDecode: '{medium} is being computed',
    promptSubmitted: 'prompt as submitted',
    aiMark: 'AI marking',
    aiMarkYes: 'AI-generated (marked in the file)',
    aiMarkNone: 'none in the file',
  },
  surrealizer: {
    // What Help says about this instrument (devserver/scripts/build_platform_
    // items.py harvests description → brief, infoDescription → what, purposeText
    // → how, techText → technical into devserver/my_app/knowledge/platform_
    // items.json); no view renders them. Written 2026-09-16 from the schema of
    // the three factors (ai4artsed_research, SCHEMA_surrealizer_split_and_
    // combine_2026-09-14.md) and from Esser et al. 2024; every number is the
    // paper's or the node's, none is measured here. The pooled vector and
    // its two fields since 2026-09-17.
    description: 'Three factors on the conditioning table of Stable Diffusion 3.5: a on the CLIP block, b for T5’s rows 0–76 added into it, c on the T5 block.',
    infoDescription: 'Encoder Fusion is an instrument of the Latent Lab that changes the conditioning of the image model Stable Diffusion 3.5 before the model runs: the table of numbers that three text encoders compute from the prompt and that the model computes the picture from. The table has 4096 columns. The two CLIP encoders, CLIP-L and CLIP-G, fill rows 0–76 up to column 2047, and columns 2048–4095 of those rows are zero; the encoder T5-XXL fills 512 rows below across every column, more when the prompt has more T5 pieces, 589 rows in all for a prompt up to that length. A row holds one piece of the prompt, a start or end mark, or padding past the text’s end. CLIP-L and CLIP-G were trained on pairs of images and captions and T5-XXL on text alone, so the two blocks hold two different encodings of the same prompt. Three factors act on the table: a multiplies the CLIP block, c multiplies the T5 block, and b adds T5’s rows 0–76 into the CLIP block cell by cell, each T5 row onto the CLIP row of the same number, whatever piece of the prompt either row holds. The T5 block holds all of those rows or, in the layout of the earlier Surrealizer, rows 77–511 alone, so that T5’s rows 0–76 reach the model only as the b-fold addend inside the CLIP block; the two fields in the line of c set which. Beside the table the model reads the pooled vector, pool in the drawing, CLIP-L’s 768 and CLIP-G’s 1280 numbers joined, as an input of the modulation, the numbers by which each layer of the model scales and shifts what passes through it; the two fields in the line of a set whether the model receives that vector or zeros in its place. Standard, a 1, b 0, c 1, pool CLIP, is the table and the vector as they stand without this instrument. What the instrument is for is the tables beyond that one. With the T5 block zeroed, or with the CLIP block and the pooled vector zeroed, on rows 0–511, the model runs in a state its training contained; a row holding both encodings, which b above 0 produces, or a block with its sign turned, which a below 0 produces, is a conditioning beyond what any prompt produces, and a run shows what the model computes from it. Every run keeps a card under Runs, the strip under the surface, labelled with its three factors, on rows 77–511 with that layout and under zeros in the pooled vector’s place with pool 0, so that runs with different settings stand side by side.',
    purposeText: 'Enter a prompt in the field; it goes to CLIP-L, CLIP-G and T5 alike. The six fields over the drawing set all three factors, the layout of the T5 block and the pooled vector, pool in the drawing, at once. Standard (a 1, b 0, c 1, pool CLIP) is the table and the vector as Stable Diffusion 3.5 runs on its own. CLIP only (a 1, b 0, c 0, pool CLIP) zeroes the T5 block, the setting without T5 that Esser et al. (2024) measured. T5 only (a 0, b 0, c 1, pool 0) zeroes the CLIP block and puts zeros in the pooled vector’s place: the model then runs on T5’s numbers alone. Surrealization 5, 15 and 35 (a 1 − n, b n, c 1, T5 block rows 77–511, pool CLIP) carry the arithmetic of the earlier Surrealizer at its strengths 5, 15 and 35: the CLIP block with its sign turned and stretched, T5’s rows 0–76 added n-fold, and under the CLIP block T5’s rows 77–511 alone. The three sliders under the drawing move each factor on its own, a and b from −75 to 75, c from 0 to 1. a at 0 removes CLIP’s numbers from rows 0–76; a below 0 turns the sign of every CLIP cell and multiplies it by the factor’s size. b at 0 adds nothing to the CLIP block; b above 0 writes sums of both encodings into rows 0–76; b below 0 subtracts T5’s rows instead. c at 0 empties the T5 block. The two fields in the line of c set which rows the T5 block holds: rows 0–511, the layout Stable Diffusion 3.5 runs on its own, or rows 77–511 alone, the layout of the earlier Surrealizer, under which T5’s rows 0–76 reach the model only as the b-fold addend inside the CLIP block; Standard, CLIP only and T5 only stand on rows 0–511, the three Surrealization fields on rows 77–511, and the label of a run on rows 77–511 carries T5 77–511. The two fields in the line of a set the pooled vector: pool CLIP, the vector as CLIP-L and CLIP-G compute it, or pool 0, zeros in its place; T5 only stands on pool 0, the other five fields on pool CLIP, and the label of a run on pool 0 carries pool 0. The token table under the sliders lists, row by row, the CLIP piece and the T5 piece that b pairs; pieces of a long prompt beyond the CLIP block reach T5 alone, and the table counts them. Under Advanced settings stand the negative prompt, which runs under the same three factors, layout and pooled vector, the CFG scale and the seed. The triangle, Execute in its tooltip, shows the picture on the surface and adds a card under Runs, labelled a · b · c; the key in a card’s bar puts that run back on the surface: prompt, factors, layout, pooled vector, negative prompt, CFG, seed and picture.',
    techText: 'The arithmetic runs in ComfyUI in the node AI4ArtsEdSD3ThreeFactors (comfyui_nodes/ai4artsed_sd3_conditioning.py), on the parts the encode node of the same family delivers for the prompt: rows 0–76 receive a · CLIP + b · T5[0..76], the rows from 77 on receive c · T5, in float32, nothing clamped. T5 runs at 512 rows (T5TokenizerOptions, min_length 512, devserver/schemas/engine/comfyui_chunk_support.py) or at the prompt’s own length past that. The layout of the block is the fourth parameter, t5_rows: full, rows 0–511 under the CLIP block, a table of 589 rows, or tail, rows 77–511 alone, a table of 512 rows, the layout of the earlier Surrealizer, in which T5’s rows 0–76 reach the model only as the b-fold addend inside the CLIP block. The pooled vector, CLIP-L’s 768 and CLIP-G’s 1280 numbers joined, is the fifth parameter, pooled. Under clip the node hands it on as the two encoders compute it; under zero it hands on zeros of the same shape, which is what ComfyUI itself assembles for the vector when it runs without a CLIP encoder (comfy/text_encoders/sd3_clip.py). The three factors act on the table; the vector passes whole. The negative prompt passes through a second node of the same kind under the same five parameters; an empty negative is the encoding of the empty string. (1, 0, 1, full, clip) is the sequence and the vector as ComfyUI assembles them on its own; (1 − α, α, 1, tail, clip) is the earlier node AI4ArtsEdSD3Fusion under legacy at α, bit for bit, which is what the three Surrealization fields send. Inside the model the whole table passes through one linear layer to the transformer’s width, the same weights for every row, and position encodings are added to the image patches only (Esser et al. 2024, section 4, Figure 2), so a text row’s place in the table plays no part in the computation; a T5 row added into a CLIP row is a sum at that layer’s input. The model reads the pooled vector apart from the table: embeddings of the timestep, the step of the run the model is at, and of this vector are the inputs to the modulation mechanism (Esser et al. 2024, section 4), which every transformer block of the model carries (comfy/ldm/modules/diffusionmodules/mmdit.py), so that zeros in its place change that modulation in every transformer block and leave the table as it is. Esser et al. (2024, “Scaling Rectified Flow Transformers for High-Resolution Image Synthesis”, ICML 2024, https://doi.org/10.48550/arXiv.2403.03206) describe the assembly in appendix B.2, the CLIP rows zero-padded along the channel axis to 4096 and concatenated along the sequence axis with the T5 rows; the training with each encoder set to zero independently at 46.4 % (B.3); and the ablation without T5 in section 5.3.3, with win rates against the full model of 50 % for aesthetics, 46 % for prompt adherence and 38 % for written text. In the paper the T5 context has 77 rows; ComfyUI runs T5 at 512 rows here. CLIP-L is the text encoder of Radford et al. (2021, “Learning Transferable Visual Models From Natural Language Supervision”, ICML 2021, https://doi.org/10.48550/arXiv.2103.00020), CLIP-G that of the OpenCLIP ViT-bigG/14 of Cherti et al. (2023, “Reproducible Scaling Laws for Contrastive Language-Image Learning”, CVPR 2023, https://doi.org/10.48550/arXiv.2212.07143), both trained on image–caption pairs; T5-XXL is the encoder of Raffel et al. (2020, “Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer”, JMLR 21, https://doi.org/10.48550/arXiv.1910.10683), trained on text alone.',
    sliderLabel: 'Extrapolation (α)',
    sliderNormal: 'normal',
    sliderWeird: 'weird',
    sliderCrazy: 'crazy',
    sliderExtremeWeird: 'super weird',
    sliderCfBothFull: 'both full',
    sliderCfClipAlone: 'CLIP alone',
    sliderCfT5Alone: 'T5 alone',
    sliderCfClipInverted: 'CLIP inverted',
    sliderCfT5Inverted: 'T5 inverted',
    sliderExtremeCrazy: 'super crazy',
    sliderHint: "α<0: past CLIP {'|'} α=0: pure CLIP {'|'} α=1: pure T5 {'|'} α>1: past T5",
    // The three factors on the conditioning table (Encoder Fusion since
    // 2026-09-15). The letters a, b, c stand in the drawing and in the record
    // and are not translated; „CLIP", „T5" are the names of the encoders.
    tableLabel: 'Conditioning table',
    // The fields over the drawing: named points of the space (the view's
    // PRESETS). Standard is the setting SD 3.5 runs on its own; CLIP only
    // zeroes the T5 block, T5 only the CLIP block; {n} is the strength of a
    // Surrealization point (the old line a = 1 − n, b = n, on the tail layout).
    // Naming form.
    standardButton: 'Standard',
    presetClipOnly: 'CLIP only',
    presetT5Only: 'T5 only',
    presetSurrealization: 'Surrealization {n}',
    factorA: 'CLIP block',
    factorB: 'T5 rows 0–76 into the CLIP block',
    factorC: 'T5 block',
    // The two fields in the line of c: which rows the T5 block holds. Rows
    // 0–511 is the layout SD 3.5 runs on its own; rows 77–511 alone is the
    // layout of the Surrealizer until 2026-09-15, T5's rows 0–76 then in the
    // model only through b, inside the CLIP block. Naming form; the numbers
    // stay in every language.
    t5RowsFull: 'rows 0–511',
    t5RowsTail: 'rows 77–511',
    t5RowsFullTitle: 'T5 block with all 512 rows under the CLIP block',
    t5RowsTailTitle: 'T5 block with rows 77–511 alone, rows 0–76 only as the b-fold addend inside the CLIP block',
    // The two fields in the line of a: the pooled vector, CLIP-L's 768 and
    // CLIP-G's 1280 numbers joined, which the model reads beside the table in
    // the modulation of every block (Esser et al. 2024, section 4). pool CLIP
    // is the vector as the two encoders compute it; pool 0 puts zeros in its
    // place, which ComfyUI itself puts there when no CLIP encoder runs
    // (comfy/text_encoders/sd3_clip.py; since 2026-09-17). Naming form. The
    // word „pool" stands in the drawing and in the card's key and stays in
    // every language, as do the numbers.
    pooledClip: 'pool CLIP',
    pooledZero: 'pool 0',
    pooledClipTitle: 'CLIP-L’s and CLIP-G’s pooled vector, 768 and 1280 numbers joined',
    pooledZeroTitle: 'Zeros of the same shape in the pooled vector’s place',
    // Written into the drawing (components/ConditioningTable.vue).
    table: {
      columnsClip: 'columns 0–2047',
      columnsRest: '2048–4095',
      t5Head: 'T5 rows 0–76',
      // The bar over the CLIP block: the pooled vector on its way into the
      // modulation of every block, or zeros in its place. The word „pool",
      // the 0 and the arrow stay in every language; „modulation" is the
      // model's own term (Esser et al. 2024, section 4) and is translated.
      pool: 'pool',
      poolClip: 'pool → modulation',
      poolZero: 'pool 0 → modulation',
    },
    // The token table under the sliders: row number, the CLIP piece, the T5
    // piece. The rows after the last piece hold padding.
    tokenRow: 'Row',
    tokenPadding: 'padding',
    // {n}: pieces the prompt has past CLIP's 77 rows; T5 keeps every row.
    tokenCut: '{n} piece beyond the CLIP block reaches only T5. | {n} pieces beyond the CLIP block reach only T5.',
    // {status}: the HTTP status of the answer, or the message where none came.
    tokensUnavailable: 'The tokenizer request failed with {status}: {reason}',
    // The explanation box of this instrument (`.lab-note`, docs/ELEMENT_
    // STRUCTURE_REGISTRY.md: its heading is the menu title, its one key is
    // noteBody, two paragraphs cut at the blank line, the reference under it
    // in LabReferences). The setting column has no room for the box yet, and
    // where it stands is still open. The quotation is Esser et al. 2024,
    // 5.3.3, and stays in English in every language.
    noteBody: 'Encoder Fusion changes the table of numbers from which the image model Stable Diffusion 3.5 computes a picture, before the model runs. The two CLIP encoders, CLIP-L and CLIP-G, fill the upper 77 rows up to column 2047 of 4096, and the columns beyond stay zero. The encoder T5-XXL fills 512 rows below across every column, more when the prompt has more T5 pieces. Each row holds one piece of the prompt, a start or end mark, or padding past the text’s end. Beside the table the model reads the pooled vector: CLIP-L’s 768 and CLIP-G’s 1280 numbers joined.\n\nEsser et al. (2024) describe the layout of this table for Stable Diffusion 3: the CLIP rows padded with zeros to 4096 columns, the T5 rows placed under them, and in training each of the three encoders set to zero at random, independently of the others, so that at inference the model runs on any subset of them. The pooled vector and the step the model is at are, in their architecture, the two inputs of the modulation: the numbers by which each block of the model scales and shifts what passes through it (section 4). For the table with zeros in its T5 block, CLIP only here, the authors report “limited performance drops when using only the two CLIP-based text-encoders for the text prompts and replacing the T5 embeddings by zeros”, with detailed scene descriptions and written text as the exceptions. A row holding both encodings, which a positive or negative b produces, lies outside those trained states. What the model computes from such a table is the question of this instrument.',
    referencesTitle: 'Research References',
    calc: {
      runFacts: 'Last run',
      stepsWord: 'denoising steps',
    },
    field: {
      heading: 'Direction of the mix',
      onlyClip: 'only CLIP',
      onlyT5: 'only T5',
      promptLabel: 'prompt',
      note: 'Inside the circle the picture is 1:1; outside, the radius is compressed so that the end of the slider lands exactly on the rim — ±75 for Legacy and Dual Alpha, where fp16 turns the image black, ±2 for Centered Fade. Schematic 2D projection from 4096 dimensions; CLIP ⊥ T5 is measured (cos ≈ 0.02).',
    },
    flow: {
      flowTag: 'the flow is the interface',
      classic: 'classic view',
      nPrompt: 'Prompt',
      nMix: 'α-mix',
      nGen: 'generation',
      nImage: 'image',
      run: 'run',
      running: 'running…',
      dPrompt: 'The entry of the flow.',
      dReader: 'One of the three readers of your prompt.',
      dReaderClip: 'CLIP — reads short, associatively (77 tokens).',
      dReaderT5: 'T5-XXL — reads long, grammatically (up to 512 tokens).',
      dC: 'The finished conditioning that flows into generation.',
      dGen: 'c and noise x become the image over d blocks.',
      dImage: 'The output.',
      err: 'no image in the response',
      openHint: 'click a node to open it · click beside it to close',
    },
    expandLabel: 'Expand prompt for T5',
    expandSuggest: 'Short prompt detected — T5 expansion significantly improves results with few words.',
    expandHint: 'Your prompt has few words (~{count} CLIP tokens). For optimal hallucinations, the AI can narratively expand the T5 context.',
    expandActive: 'Expanding prompt...',
    expandResultLabel: 'T5 expansion (T5 encoder only)',
    advancedLabel: 'Advanced settings',
    shortPrompt: 'Short text: T5 reads in barely more here than CLIP does. The perspectives in the field make a text out of a sentence — “{preset}” is written for that.',
    encoderCapacities: 'CLIP-L + CLIP-G: 77 tokens · 2048 of 4096 dimensions  ·  T5-XXL: 512 tokens · 4096 dimensions',
    fusionStrategyLabel: 'Fusion Strategy',
    // Names a stored run made on the sphere (Encoder Fusion, 2026-09-10 to
    // 2026-09-12) on the strip; the setting itself is gone from the surface.
    path_sphere: 'Sphere',
    // The two chips of Encoder Fusion. They run one arithmetic (centered_fade)
    // and differ in the texts, so they are named for the texts; the arithmetic
    // keeps its name in fusion_centered_fade, on the Fusion Workbench.
    samePrompt: 'Same prompt',
    adaptedPrompts: 'Adapted prompts',
    samePromptTitle: 'The prompt in the field goes to CLIP-L, CLIP-G and T5 alike.',
    adaptedPromptsTitle: 'A language model writes one prompt per model from the prompt in the field: a keyword list for CLIP-L and CLIP-G, a prose paragraph for T5.',
    fusion_dual_alpha: 'Dual Alpha',
    fusion_centered_fade: 'Centered Fade',
    fusion_original: 'Original Fusion',
    fusion_normalized: 'Normalized',
    fusion_legacy: 'Legacy',
    fusion_slerp: 'Slerp',
    fusionHint_dual_alpha: 'Full α on the core tokens, 0.15 × α on the tail. Structurally recognizable, aesthetically surprising — but with a short prompt the tail is mostly padding, so high α amplifies padding and pulls toward the model’s defaults.',
    fusionHint_centered_fade: 'True center: at α=0 both readings act fully (CLIP core and T5), so central subjects are not dropped; α=+1 is T5 alone, α=−1 is CLIP (L+G) alone, |α|>1 inverts one side. Tail stays at 1×. Note the different α scale — the anchors are at ±1, not at ±15–35.',
    fusionHint_normalized: 'α on the core tokens only; the tail keeps its direction and is rescaled to the core’s magnitude. Deprecated — kept for reproducing earlier runs.',
    fusionHint_legacy: 'Original behavior: extrapolates first 77 tokens, appends T5 remainder unchanged (1×). Less surreal with long prompts — unmodified tokens dilute the effect.',
    negativeLabel: 'Negative Prompt',
    negativeHint: 'Extrapolated with the same α. Determines what the image extrapolates AWAY from — different negatives produce fundamentally different aesthetics.',
    cfgLabel: 'CFG Scale',
    cfgHint: 'Classifier-Free Guidance: strength of prompt influence. Higher = stronger effect, less variation.',
    seedLabel: 'Seed',
    seedHint: '-1 = random. Fixed seed enables A/B comparison across strategies.',
    executeButton: 'Execute',
    executingButton: 'Generating...'
  },
  coverBand: {
    story: 'This is a playful exploration of what an AI understands — and misunderstands — about musical and cultural matters. The page listens through the microphone, tries to recognise singing and speech, then sound situations and styles, and finally to rebuild them: a chain of translations full of translation losses and artefacts, which can be experienced like a distorting mirror.',
    purpose: 'Two things can be learned here: to provoke a particular output on purpose with sung or played input, and to meet your own means of expression and clichés of perception in doing so. And to find that an AI often invents something even when there is nothing but silence, and that entirely different recordings often produce very similar, clichéd results.',
    modeTitle: 'Re-enactment',
    title: 'Re-enactment',
    lede: 'Original and re-enactment. What can an AI hear, what can it understand of music, and what does it sound like when it rebuilds that? Here you are the original and the AI is the re-enactment.',
    detour: 'The music model HeartMuLa is the last of the four, and it performs your song from a description alone.',
    working: 'working…',
    waiting: 'waiting',
    stationFailed: 'this machine did not answer',
    stationFailedNamed: '{station} — this machine did not answer',
    band: {
      done: 'All four have answered'
    },
    run: {
      name: 'Start',
      start: 'Send the recording through the four machines',
      took: 'answered in {s} s'
    },
    back: {
      head: 'Production',
      machine: 'machine',
      translation: 'translation',
      got: 'it got',
      took: 'it took',
      seconds: '{s} s',
      gotRecording: 'your recording',
      gotStations: 'the sorted list and the recognised words',
      gotWritten: 'the style words and the text'
    },
    ask: {
      sign: 'Ask me!',
      question: 'What can you actually hear of my music, and what happens to my recording on the way to the song? I would also like to know what is worth trying here.'
    },
    record: {
      name: 'Record something!',
      note: 'Sing, hum, or hold your phone up and play something. Up to four minutes — the song comes back exactly as long as the recording, down to ten seconds.',
      discardHint: 'Nothing is kept. The recording is deleted the moment the machines are finished with it, and the song is not saved either.',
      emptyRoomHint: 'Worth trying once: point the microphone at an empty room and record nothing at all.'
    },
    ranked: {
      name: 'Audio analysis',
      note: 'This machine cannot say what it got. It can only sort it against words that were written down in advance.',
      last: 'last place:',
      ourList: 'The list has {n} entries and we wrote it, not the machine. It always picks a best match, even from silence — there is no answer for "none of these".',
      culturalLimit: 'How well machines hear cultural difference has been measured. Across recordings from Western, Mediterranean, Middle Eastern, Indian and Chinese traditions, seven audio models were held against the judgements of 125 listeners. {model} came closest to people of the seven — that is why it is the one sorting your recording. People still separated the traditions about one and a half times as sharply as it did.',
      culturalLimitSource: 'Cross-Cultural Music Similarity, TISMIR 2025',
      secondMachine: 'A second machine, {model}, got the same recording and the same list:',
      secondFailed: '{model} returned no sorted list: {cause}',
      secondWhy: 'It used to be the only one here. The song is written from both lists — and this second one alone decides which machine sings it back, because it is the one that can hear whether a voice is speaking or singing. Where the two disagree, there is no way to tell from the page which is closer.'
    },
    words: {
      name: 'Recognised words',
      note: 'This machine returns words for any recording at all.',
      returnedNothing: '(it returned nothing this time)',
      notProof: 'Noise and an empty room are enough: out of them this machine writes fluent, confident sentences, in a language it invents along with them.',
      whichLanguage: 'Nobody told it which language to listen for. It decided on its own that this was {language} — before it decided on a single word. The song keeps that decision, whatever was actually spoken in the room.',
      inReadingLanguage: 'Translation of the recognised words.'
    },
    written: {
      name: 'Generated lyrics',
      note: 'A language model turns the two readings above into a song, filling every gap without hesitating.',
      tagsLabel: 'style:',
      readAlong: 'Read this while the song plays. What is asked for here and does not come back is something the music model cannot do — and what comes back without being asked for is what it put there instead.'
    },
    sung: {
      pick: 'Choice of model',
      held: 'chosen by hand — this is the one that runs',
      name: 'Output',
      note: 'This one can only be heard, not read. Hold it against the text that was written.',
      madeBy: 'made by {model}, in {s} s',
      notKept: 'This exists for as long as you stay on the page. It cannot be saved, favourited or downloaded — it is a re-enactment, not a work.'
    },
    errors: {
      noMic: 'No microphone available, or permission was refused.',
      upload: 'The recording could not be handed over.',
      tooLong: 'That recording is longer than four minutes, which is as much as this takes.',
      chain: 'The chain broke off.'
    }
  },

  // The overview map of the Latent Lab has an address of its own. It stood on
  // the lab's until 2026-08-23, and the lab's says what the twenty-three
  // instruments are for, not what the map in front of you is.
  latentLabOverview: {
    story: 'On this overview page you are already looking inside AI models \u2014 diffusion and transformer architectures that produce images, sounds and texts, and ways of carrying one over into another.',
    purpose: 'Click the boxes and find out at which places this page invites you to experiment!',
  },

  // What a model is, on the card beside a model field. The register holds the
  // step, never the word, so one entry serves every language.
  modelInfo: {
    // The three steps of openness. SUPPLIED WORDING: the three NAMES; what
    // each step means is the register's (devserver/config/model_register.json,
    // `_note`).
    openness: {
      open: 'Open Source',
      weights: 'Open Weights',
      closed: 'Closed Weights',
    },
    // The four sizes of a model, by the room its weights take.
    // SUPPLIED WORDING: the four names; the thresholds stand in
    // composables/useModelRegister.ts (sizeClass). Shown beside the figure in
    // a chip's aside ('27B · small'),
    // in the line of the card at a row head, and in the option text of a select.
    size: {
      micro: 'micro',
      small: 'small',
      large: 'large',
      veryLarge: 'very large',
    },
    // Through which service a model is reached: 'via Mammouth AI'.
    via: 'via {provider}',
    // What the t2x page's hover card showed on a model's bubble, back in the
    // Flow's model choice and worded as it stood there:
    // the quality rating and the speed in five stars each, and the estimated
    // time of the generation ('⏱ 12-40 sec', the clock drawn by
    // components/InfoCardFacts.vue).
    quality: 'Qual.',
    speed: 'Speed',
    seconds: '{range} sec',
  },

  latentLab: {
    story: 'This is about making the invisible elements and workings of generative AI reachable. The Latent Lab translates real AI research into the surface of the page: even where research contributions are often too difficult to understand, what it shows can be tried out and experienced. The engine room, as far as it can be made experienceable.',
    purpose: 'Two things can be learned here: to explore the in-between spaces of an AI that are never shown, and to carry the estrangements and intermediate products on into artistic work. And to get to know generative AI from the inside: to understand that it is made, and to open the black box a little.',
    tabs: {
      compare: 'Cultural Knowledge & Stereotypes',
      interception: 'Prompt Interception Lab',
      image: 'Diffusion Lab',
      textlab: 'Transformers Lab',
      crossmodal: 'Crossmodal Lab',
      lora: 'LoRA Training'
    },
    // What is being counted beside the trigger while a run is out. One word,
    // singular, in front of `n / m` - see components/FlowRunProgress.vue.
    runLine: {
      step: 'Step',
      answer: 'Answer',
      text: 'Text',
      image: 'Image',
      reading: 'Reading',
      // Stands instead of the count once the denoising is done and the pictures
      // are on their way.
      transfer: 'Waiting for transfer',
    },
    flowLogic: {
      tab: 'Overview',
      barNote: 'Overview map of the Latent Lab',
      close: 'Close',
      worksHere: 'works here',
      diffusion: {
        title: 'Diffusion',
        sub: 'Change how images \u0026 media come about in an AI!',
        space: 'latent space',
        conditioning: 'conditioning',
        prompt: {
          name: 'Prompt',
          example: 'A house stands in a landscape, surrounded by farmland, nature and animals. Some people can be seen.',
          platformNote: 'This platform translates your prompts into English and adapts them to the chosen medium where needed, so you can work with it creatively.',
          enBox: 'Translation',
          enSample: 'A house stands \u2026',
          adaptBox: 'Adaption to medium',
          adaptSample: 'A picture of a house \u2026',
          langNote: 'But only when the translation is switched off do you see the difference on the right: the same sentence in another language gives another picture.',
          exploreNote: 'You can explore this with the \u201cLanguage Understanding\u201d instrument.',
        },
        encoder: {
          name: 'Embedding Process',
          tokenSentence: 'A house stands in a landscape, surrounded by farmland, nature and animals. Some people can be seen.',
          readers: 'Several small AI models ([[encoders]]) break the prompt into small pieces, so-called [[tokens]].\nEach encoder links every [[token]] to a long row of numbers (between 77 and 512 [[vectors]] with 768-4096 numbers each).',
          list: 'one [[vector]] per [[token]]',
          pooled: 'one [[vector]] for the whole sentence',
          tokens3: 'A house stands in a landscape , surrounded by farm l and , nature and animals . Some people can be seen .',
          tokens2: 'a house stands in a landscape , surrounded by farmland , nature and animals . some people can be seen .',
          tokens1: 'a house stands in a landscape , surrounded by farmland , nature and animals . some people can be seen .',
          vecWord: 'farm l and',
        },
        loop: {
          name: 'Denoiser and Scheduler',
          spaceNote: 'The space of all images/media a model can bring forth.',
          note: 'Noise is pure disorder (chaos). The [[denoiser]] was trained beforehand, on media and text,\nto bring order into this chaos. It uses the [[meaning vectors]] from the [[prompt embedding]] (see above).\nPoints in the noise that fit the vector act like small anchors for the meaning.\nWith every [[STEP]] of the clock ([[scheduler]]) the noise clears a little further.',
          state: 'noise image before',
          next: 'noise image after',
          cond: 'embedding',
          denoiser: 'Denoiser',
          denoiserSub: 'estimates what in the noise does not fit the embedding',
          scheduler: 'Scheduler',
          schedulerSub: 'sets the update rule and the step size',
          repeat: '4 to 50 times, depending on the AI model',
          nothing: 'Result: a data object that holds a great deal of information about the end product, but is not yet understandable for people.',
        },
        decoder: {
          name: 'VAE / Variational Auto Encoder',
          from: 'a tensor of 16 matrices',
          explain: 'The many pieces of data, e.g. about content, contrast, colours, textures, are combined into a media product humans can perceive.',
          toImage: 'picture',
          toSound: 'sound',
          toVideo: 'video',
          to3D: '3D'
        }
      },
      transformer: {
        title: 'Transformer',
        sub: 'Find out how text AIs work and whether they pass on prejudices!',
        space: 'embedding space',
        // ONE key for the three cards that carry measured numbers. Three short
        // lines, small, in the bottom right corner of each of them.
        modelNote: 'All the numbers here are measured on one\nAI model: Qwen3-4B. A different model cuts\ndifferently and has different numbers.',
        prompt: {
          name: 'Prompt',
          you: 'Prompt · you write it',
          provider: 'system prompt of the provider · sometimes a trade secret',
          sysExample: 'Answer briefly. Do not cite sources you have not read.',
          hidden: '[[invisible]]: you get to see none of it',
          oneText: 'a single text',
          check: 'Check',
          checkA: 'a separate model reads',
          checkB: 'the whole text along',
          passA: 'through — on',
          passB: 'to the next step',
          stopped: 'held back',
          note: 'When you type a prompt into a chatbot like ChatGPT or Claude, a great deal happens before the actual AI model processes it. It is extended by a system prompt and checked. Finally the AI model itself responds, weighting your input according to the ideas of the manufacturer. Many manufacturers want to reduce discrimination and racism in their answers. For some manufacturers, however, this is not always the first concern.',
          source: 'https://www.npr.org/2025/07/09/nx-s1-5462609/grok-elon-musk-antisemitic-racist-content'
        },
        vectors: {
          name: 'Tokenization and embedding',
          sent: 'A house stands in a landscape, surrounded by farmland, nature and animals. Some people can be seen.',
          cutLabel: '[[Tokenization]]: the text is cut into [[tokens]]. [[Tokens]] are word pieces.',
          // `mland` carries `h` as well since 2026-08-26: its measured row is
          // drawn below, and the green edge is what says which chips have one.
          chips: 'im_start¦before¦c\nA¦1¦\n␣house¦2¦h\n␣stands¦3¦\n…¦4–9¦g\n␣far¦10¦hf\nmland¦11¦hf\n…¦12–15¦g\n.¦16¦\n…¦17–21¦g\n.¦22¦',
          posNote: 'the place numbers of the [[tokens]]',
          ctrlNote: 'a control [[token]]',
          fourNote: 'one word becomes two [[tokens]]',
          langHead: 'The same sentence in the ten languages of this platform, cut into [[tokens]]:',
          langs: 'en¦English¦22\nhe¦Hebrew¦25\nes¦Spanish¦30\nde¦German¦31\nko¦Korean¦31\nfr¦French¦35\ntr¦Turkish¦35\nar¦Arabic¦36\nbg¦Bulgarian¦47\nuk¦Ukrainian¦56',
          langNote: 'For the same sentence the AI model needs\nmore than twice as many [[tokens]] in\nUkrainian as in English.\nThe word for “house” is one [[token]] in eight\nof these languages. In Bulgarian and\nUkrainian it is three.',
          embLabel: '[[Embedding]]: every [[token]] is given its series of numbers. Your text is thereby embedded in numbers.',
          // `token¦number¦number…` per line, one line per green-edged chip in
          // `chips`. The first six numbers Qwen3-4B holds for that token in
          // `model.embed_tokens.weight`, measured again on 2026-08-26. NOT
          // invented and not rounded — a row that cannot be measured is left out.
          rows: '␣house¦-0.0344¦+0.0038¦-0.0258¦-0.0146¦-0.0178¦+0.0104\n␣far¦-0.0209¦+0.0092¦+0.0186¦-0.0160¦+0.0132¦-0.0332\nmland¦+0.0405¦+0.0002¦+0.0211¦+0.0171¦-0.0184¦-0.0068',
          more: '… 2,560 numbers',
          vocab: 'The vocabulary of the AI model holds 151,669 [[tokens]].',
          // The COMPLETE row of “␣house” (token 3,753) from the input
          // table of Qwen3-4B, raw, as it stands there. 2,560 characters, one
          // per number, in 32 steps from -0.055 to +0.055; 22 of the 2,560 lie
          // outside and sit at the edge. MEASURED on 2026-08-26.
          vec: '6h8baikmdi3ii3kjk8riimr8ldeu6mah598kniba6s9k28jllcgpgkbeb5gicijdnhneijiklb6a9hgageedbb8efbb9j6ifoihanbeimp9qkgcjmhh9cif6ihhbefhjdffilcea7dididafbgekmei85eifqi97v8f9agejf9ad98jlfjk55hhjeeffmngfedcfac79dlbhcbehqkffobcfchjbjjfjigcfkaef7ccefhgdpgbeiikdm9oghkmancdhiflgp1kcgksli749fim9mgnjccocgcdmfaf99jbnbf8l0e9hodahhkjgjgh4k9ce6o6eecsbhhnddada8jchbgiebdjjhjidmhnedie7la6sjecpdehikbqnieeajaieecihdjhdocdmadfba5mejboijmc99qaelo99ih9h9deirjdbnkgefkd7gp9dj699ga3fsgeiedjmhmbc9epfjgbbkmkhfhea9cce9akscdelkhfpei8jjldlej7cgqg6nobhlhabgkqnpm8hedgqj99e9gil9fjgh6lfddggkheh9bc9oam4kncm6ddfclmatdslpel9gdnapi8uhegolfglpocipbie7fandh7agokfahengbefhkdl89enigcijifb6agohcgcujf4llbognjfe9cmcektmfbf6939q9mk6d2pfisd6k8ogpnmmpbgesdjmg6gltlh739ccoash9bhjemeejcciddahpfoh86ieehmqalagrl7jgkrmfloca4cl8i7pbgcgjjahajihombmc9jcgmfmc6no6e97tjajc4b89b8hm97gmllbinab9ecl6i3uc584l7he7kh8kfhaejhailpbfjhjcbfgpnecmpcog7bhbicadeiigihbiqjmc9qeilfkdgekhfb19icjfkjahjd42cqcrhcjgkfm4bikhkcb0kcc9j9khjkglh7gaa7dcgpg8a7j797c6ukcnmp9j7khgedceboqephif4qandgabh9jbi5nnik8hchbdfb8dfdgg3in7lacddnrj2ic1icnetff3ka9conmbee7gan75de9qa76laigahrv9kbemgc5lkkfgb8dkf8eb2jikqpohhfbr4efbijegghgq8md3kiok1mjch7mc2kggbj7iafqlfnhigf4iinehfaebnc8ioiimb9emjgb7u9jpecdbjemehmedv99bk3nlbhhdo5ncriejefier2aqvmggjfgaahjm2l79e7vhdllh5cd9bn1j80hmqid9dafididdohc8meddfi6cbdihedgb7ohgblk46qqif5dlcv67mkghh7bf4mdi0ba88eldp1l9ho69bf8i9u88j6k8d8a3lcimgdocp8pi6ckaikm7k6qf7efmq7dgjeja8fddjtoldke5vldbiud9bqranoip2glrha9988ejjlf7lkefg5jbcibn9e886ihcldqucl7gdi798gbbeilg8pmtklphefbesjf4d98tf6oeioakiomj4vdgbfekeaap9dgg5fjd42o7mdjafadnhrj9omeo4f7hnm028plg8rn0ff9dlclcnk5kif6l08nbgddldieeb6ddbj43aief77hnth0bi0h8egvhjlg8g9fmjhfeikhes8acen1h3fh9d7aifaef0kfbge20l9hknll2ne4llch2pcirgdmpfh6k8gdmlafglh4f63ik8g4udj8lpijffsbeegepddcr4cb8f63f6jg3eecgkf9cphbhnf1h47efjmnnpabmcjpcfhmfefbdk80gfibkccpf55g3hdaegd8dvgigk7gogackhjtfhmmckbfhrjgcain6d7apemdshffcmedgaqnfdsbp9mjthqgb8kc58iadgklfcifcb7e7dmg3qbtoih99jtjchek5h65eqe7c0jckfhdhl83conjjf5dpiabpjlecf9kl9ftkhk4fe7i6j5q2aqieslicf6emglnqgagmgmjgeaiagcmcjehemecaomidsmiugje4kicmp6gikhdbgolnhlp7dkbmkd8jlg3hicka9kgkhobamjgqc9fafnkd99khee8fragkal9qk0qhddchffk9k9khhkkdghih6gkfqi2e9cdet93l7pod8e5hebmlbrmjjfm73pabkih4bf0od3ioj7r9gbfa54cjb0gkbj3elh8jb69kjditkbb9be4c77cjpiegigkijmgbhnic8bccnigdfmao3kd867j7hhj1nb97la8lidaehpq5ddlmpqjid0ckk9cne9iepgh8iraiofjabcffge9d5hgomjghfaugjchfjorsbheh64hm6k8jvf88emgljecd4hnfb9cdogic5idj7cipcjafggglbbjojq9ggieckbkdnjejd9dgncebj8f6jgnehirke9kckbc7ib699k96gepqdqaggbi6fo4orgdlbcmil5cm7iecs6l9deega9daomkeja7giekklhkpjek9jfgg4h9j37mqnl7cecgqci7k9fjbgaainas7cd',
          vecNote: 'the whole series of numbers of “␣house”\n[[token]] no. 3,753 of 151,669',
          vecScale: '−0.055¦+0.055',
          // Three lines, not four: the text stands under the drawing, set off
          // from it, and what the drawing itself already says (`cutLabel` has
          // “the text is cut into tokens”) does not belong here a second time.
          close: 'Frequent words are a [[token]] of their own. Long and rare words are put together from several [[tokens]], and the control [[tokens]] from the prompt box are [[tokens]] too.\nEvery [[token]] has a place number and a fixed series of numbers: “␣house” is given the same 2,560 numbers in every text. ␣ stands for the space before the word.\nWhat the word means in this sentence is not in there yet. The AI model computes that in the next step: in [[attention]].',
        },
        block: {
          name: 'Attention',
          intro: 'from the station "Tokenization and embedding": every [[token]] with its fixed series of numbers',
          frameLabel: 'Transformer',
          field: 'field of view: up to 40,960 [[tokens]] at once',
          chips: 'A¦\n␣house¦\n␣stands¦\n…¦g\n␣surrounded¦\n…¦g\n␣far¦\nmland¦h\n.¦\n…¦g',
          arcs: '2¦1¦what stands there?¦1.3\n4¦1¦what is surrounded?¦2.2',
          attCap: '[[attention]]: the thicker the arc, the more important',
          beforeRow: 'mland¦+0.0405¦+0.0002¦+0.0211¦+0.0171¦-0.0184¦-0.0068',
          more: '… 2,560 numbers',
          beforeCap: 'at the start: the fixed series of numbers of “mland”',
          stackCap: '36 times, layer by layer',
          result: 'farms',
          resultCap: 'the intermediate state from layer 10 on',
          bankHead: 'for comparison',
          bank1: '“They had a picnic on the bank of the river.”',
          bank2: '“The bank raises its interest rates.”',
          bankRows: 'bank¦+0.35¦-0.44¦+0.29\nbank¦-0.61¦+0.18¦+0.72',
          bankNote: 'At the start the word “bank” has the same\nseries of numbers both times.\nAfter [[attention]] it does not:\neach “bank” carries the meaning of its sentence.',
          close: 'From the previous station every [[token]] arrives with its fixed series of numbers. What a word means in this sentence is not written there yet.\nIn [[attention]] the AI model computes for every [[token]] which other [[tokens]] matter for it — even across a long distance. Out of their series its own series is computed anew.\nThis repeats in the transformer 36 times, layer by layer. After that every series holds the meaning the word has in exactly this text: “␣far” and “mland” have become farmland.\nThe series behind the last [[token]] then holds how the text could go on. The next station works with exactly that: sampling.\nThe intermediate state “farms” and the 36 layers were measured on 2026-08-24. The arcs and the bank rows are exemplary.',
        },
        sampling: {
          name: 'Sampling',
          intro: 'from the station “[[Attention]]”: the series of numbers behind the last [[token]]',
          context: 'A house stands in a landscape, surrounded by farmland, nature and',
          // `token¦value` per line, tallest first. The values are exemplary;
          // the pieces are the tokenizer's real cuts, so the box cannot
          // contradict its measured neighbours. The tail line `…¦`
          // stands for the rest of the table and keeps no value.
          cands: '␣animals¦34 %\n␣trees¦19 %\n␣fields¦11 %\n␣birds¦7 %\n␣people¦4 %\n… and 151,664 more¦',
          chance: 'the likelihood of each [[token]]',
          drawn: 'one [[token]] is chosen at random',
          loop1: 'then everything runs again: [[token]] by [[token]]',
          loop2: 'until the control token for the end is chosen:',
          endTok: 'im_end',
          sharp: 'the “temperature” setting flattens or steepens the odds',
          flat: 'flattened',
          steep: 'steepened',
          note: 'From the series of numbers behind the last [[token]] one probability is computed for every [[token]] in the vocabulary of the AI model. Most lie near zero.\n[[Tokens]] with high probability are chosen often. [[Tokens]] with low probability are chosen rarely.\nThe answer is put together from probable [[tokens]]. “Probable” means: it fits everything before it. It does not mean: it is true.\nThe numbers on this drawing are exemplary.',
        }
      },
      crossings: {
        title: 'Crossmodal routes',
        sub: 'Chains of several AIs',
        i2t: {
          name: 'Image to text',
          models: 'several AI models describe the same picture; each arrives at a different text'
        },
        t2a: {
          name: 'Text to sound',
          text: 'a sentence',
          music: 'one AI model makes a sound from the description',
          voice: 'another turns the sentence into a voice'
        },
        i2a: {
          name: 'Image to sound',
          make: 'one AI model makes a sound from the picture',
          pull: 'another steers the sound while it is generated'
        },
        chain: {
          name: 'Sound to text to sound',
          s1: 'Analysis',
          s2: 'Speech recognition',
          s3: 'Speech synthesis',
          s4: 'Writing',
          s5: 'Sound',
          s3note: 'only when there is text and a voice language for it',
          m1: 'song',
          m2: 'music',
          m3: 'speech',
          m4: 'sound effects',
          machines: 'four sound generators; the analysis or a hand-pick decides'
        }
      }
    },
    loraLab: {
      tabs: {
        lora: {
          label: 'LoRA Training',
          short: 'Training takes 1-3 hours and blocks image generation'
        },
        reach: {
          label: 'LoRA Explorer',
          short: 'Reach of a trained adapter'
        }
      }
    },
    imageLab: {
      headerTitle: 'Diffusion Lab — Visual Vector Space Research',
      headerSubtitle: 'Eight tools for investigating how diffusion models generate images from text. They sort by where they intervene.',
      headerSubtitleDetail: 'Eight tools for investigating how diffusion models generate images from text. They sort by where they intervene. The text encoders turn your prompt into one fixed embedding, and that same embedding then guides all 25 denoising steps. Dimension Explorer, Concept Algebra and Encoder Fusion change the embedding once, before the loop starts, and the Encoder Fusion Workbench sweeps the fusion parameters across three axes. Composable Diffusion stands in both places: it combines what the model returns at each single step, or interpolates between the concepts’ embeddings before the loop starts. Denoising Archaeology and Attention Cartography change nothing and only look. Mean Images leaves the model alone as well and averages many pictures into one. For the two SD 3.5 models it averages the latents of those pictures, before the decoder.',
      tabs: {
        census: {
          label: 'Default Census',
          short: 'What comes when little is said'
        },
        archaeology: {
          label: 'Denoising Archaeology',
          short: 'Watch the model work'
        },
        mean: {
          label: 'Mean Images',
          short: 'Many generated images averaged into one'
        },
        attention: {
          label: 'Attention Cartography',
          short: 'See where the model looks'
        },
        fusion: {
          label: 'Encoder Fusion',
          short: 'Surrealistic blending'
        },
        probing: {
          // Built as Feature Probing and renamed. The old name
          // came from interpretability research, where Belinkov (2022) describes
          // probing as a classifier trained to predict a named property from a
          // model's representations; nothing is trained here (cf2d20df).
          label: 'Dimension Explorer',
          short: 'Dimension-level analysis'
        },
        algebra: {
          label: 'Concept Algebra',
          short: 'Vector arithmetic'
        },
        composable: {
          label: 'Composable Diffusion',
          short: 'Each concept scored separately'
        },
        workbench: {
          label: 'Enc. Fus. Workbench',
          short: '3-axis comparison'
        },
      },
      vramGate: {
        unavailable: 'Not available on this GPU',
        tooltip: 'Requires ≥{threshold} GB VRAM (detected: {vram}). This tool is available on the RTX PRO 6000 Blackwell (96 GB) but not on RTX 4090/5090 at the workshop-platform baseline (resident SD3.5 + LLMs ≈ 20 GB).',
        tooltipUnknown: 'Requires ≥{threshold} GB VRAM. GPU detection failed — the gate is conservative by default.',
        override: 'Override: set AI4ARTSED_FORCE_HEAVY_LATENT_LAB=true in the gpu_service environment.'
      }
    },
    comingSoon: 'This tool will be implemented in a future version.',
    shared: {
      runsTitle: 'Runs',
      runsEmpty: 'No runs yet',
      negativeHint: 'Terms the model should actively avoid (e.g. "blurry, text")',
      stepsHint: 'More steps = higher quality but longer generation time',
      cfgHint: 'Classifier-Free Guidance: higher = stronger prompt adherence, less variation',
      seedHint: 'Fixed seed = reproducible result',
      randomVariation: 'Random variation',
      recordingActive: 'Recording active',
      recordingCount: '{count} recording | {count} recordings',
      recordingTooltip: 'Research data is saved automatically',
    },
    // Mean Images — the average of a model's answer to a seed and a text.
    // DRAFT copy: every line below is a first setting, marked as such in
    // src/i18n/WORK_ORDERS.md. `steyerl` stays empty until its text is
    // written; the note box renders it only when it carries something.
    meanImages: {
      noEnglishText: 'no English text came back',
      description: 'Many generated images, from rewordings of one prompt or from one prompt on different seeds, averaged into one picture. For the two SD 3.5 models the mean is taken before the decoder, and each row says which mean it shows.',
      story: 'The instrument generates many images from one prompt and averages them into one mean image, per AI model. Two means are computed per model. The first is the mean of the images generated from English variants of the prompt, which a language model writes with the same content in other words, as many as the setting \u2018Images per cell\u2019 says. The second is the mean of the images generated from the prompt as entered on randomly varied starting seeds. The models are selectable, one row each; both columns always stand. A switch in the left column shows the single images as a contact sheet, or a relief of the mean, instead. For the two SD 3.5 models the mean is taken before the decoder: the latents of the pictures are averaged and decoded once. The other models are averaged pixel by pixel, and each row says which.',
      purpose: 'This page applies the artist Hito Steyerl\u2019s \u2018mean images\u2019 as a method against generative AI models. The mean of many images, generated from rewordings of one prompt or from one prompt on different seeds, can be compared across AI models. The comparison serves the exploration of visual clich\u00e9s, prejudices and other forms of the statistical production of \u2018normality\u2019.',
      generate: 'Run the series',
      seedLabel: 'Seed',
      advancedLabel: 'Advanced settings',
      perCellLabel: 'Images per cell',
      rowsLabel: 'Rows \u00b7 models',
      variantsLabel: 'Generated prompt variants',
      viewLabel: 'View',
      view: {
        images: 'Contact sheet',
        mean: 'Mean',
        relief: 'Relief'
      },
      col: {
        seedFixed: 'Seed fixed',
        promptFixed: 'Prompt fixed'
      },
      colSub: {
        seedFixed: '{n} prompt variants',
        promptFixed: '{n} random seeds'
      },
      rowState: {
        waiting: 'waiting',
        running: '{done} / {total}',
        done: 'done'
      },
      meanKind: {
        latent: 'latent mean',
        pixel: 'pixel mean'
      },
      meanKindLong: {
        latent: 'The latents of these pictures were averaged and decoded once.',
        pixel: 'These finished pictures were averaged pixel by pixel.'
      },
      meanBlocked: 'The pictures of this cell all passed the check. The mean made from them was flagged as unsuitable by an image analysis AI.',
      origin: 'In mean images, Steyerl writes, \u2018statistics are integrated directly into an object\u2019s likeness, through determinations of likelinesses\u2019 (Steyerl 2025, p. 78); that is, an AI model computes the picture of a thing from probabilities. On this page, you apply the *mean method* back on (or against) generative AI models: generating many images from similar prompts, or from one prompt with different starting seeds, and building a visual \u2018mean\u2019 of all these images, you can explore and compare visual clich\u00e9s, prejudices and other forms of the statistical production of \u2018normality\u2019.',
      steyerl: 'The artist Hito Steyerl calls the pictures an AI model generates \u2018mean images\u2019, \u2018a rendition of correlated averages\u2019: an image made from statistical averages. The English word \u2018mean\u2019, she writes, \u2018has several meanings, all of which apply here\u2019: \u2018\u201cMean\u201d may refer to minor or shabby origins, to the norm, to the stingy or to nastiness.\u2019 She writes: \u2018Mean images are far from random hallucinations. They are predictable products of data populism. They pick up on latent social patterns that encode conflicting significations as vector coordinates. They visualise real, existing social attitudes that align the common with lower-class status, mediocrity and nasty behaviour.\u2019 (Steyerl 2025, p. 72)',
      referencesTitle: 'Research References',
      cellFailed: 'Nothing came back.',
      runFailed: 'Run failed: {m}',
      variantsShortfall: 'One of the asked-for variants came back as a repetition and stays out of the run. | {n} of the asked-for variants came back as repetitions and stay out of the run.'
    },
    loraReach: {
      description: 'One trained adapter, put through four states of the same comparison: the same motif, the same seed and the same model, run with and without the word the adapter was trained under, and with and without the adapter itself.',
      story: 'You choose an adapter that was trained here, the word its images were captioned under, and a few motifs — one motif per line, and each becomes a column. Every column is then generated four times over: the plain model on the motif alone, the plain model with the word in front of it, the adapter with the word, and the adapter without it. All sixteen pictures come from one model with one starting number, so what separates two of them is the prompt and the adapter alone.',
      purpose: 'The third row against the second is the reach: what the training added on top of what the words already carried. The fourth row against the first is the limit: whether the adapter also answers when it is not called, which is how it shows that it has overwritten what the model knew rather than added to it. A motif the adapter was never shown asks the same question from the other side — whether a trained manner carries over, or whether the adapter brings the subjects of its training set along with it.',
      generate: 'Run the comparison',
      adapterLabel: 'Adapter',
      noAdapters: 'Nothing has been trained here yet. The Training Studio makes an adapter.',
      triggerLabel: 'Trigger word',
      motifsLabel: 'Motifs, one per line',
      strengthLabel: 'Adapter strength',
      rowModelPlain: 'Model · no trigger',
      rowModelTrigger: 'Model · trigger',
      rowLoraTrigger: 'Adapter · trigger',
      rowLoraPlain: 'Adapter · no trigger',
      noteBody: 'This platform trains a LoRA adapter on captions that all begin with the same trigger word. Whether it also acts on something else is a question about the model that took it on: personalisation can drift, so that the ordinary meaning of a word that stood in the captions changes as well (Ruiz et al. 2023).',
      referencesTitle: 'Research References',
      cellFailed: 'Nothing came back.',
      runFailed: 'Run failed: {m}'
    },
    census: {
      description: 'A written prompt, put to the chosen image models in one run: as it stands, and again with a culture or a country named in it. Every run includes the prompt without any such addition, and nothing rewrites it on the way to the model.',
      // The address, recast without an address: the constative second person
      // ("A line you write") became the impersonal naming of the process,
      // "line" became "prompt" (docs/COPY_RULES.md: the surface's word is the
      // word); "goes to", a verb of motion, became "receive", because
      // docs/COPY_RULES.md bars the arrival verb as well. German is the
      // authored side; this is set after it. The closing sentence of the
      // second half is SUPPLIED WORDING and keeps its address word for word.
      story: 'Several image models receive the base prompt once on its own and beside it with a culture or a country named in it — "Yoruba", "Sámi", "Franconian". The rows hold the models, the columns the variations, and a model computes in its row with the same seed and with exactly this wording.',
      purpose: 'The first column shows what a model brings out while the prompt says nothing about origin: which place, which people, which clothing count to it as the obvious ones. The further columns show what a named culture changes: whether the model shows the practice meant, or only swaps the surroundings and delivers the cliché. If you choose only 1 model, 5 different variations (seeds) are used, so that you can compare a range of results.',
      generate: 'Run the series',
      templateLabel: 'Base prompt (use the asterisk "*" as the placeholder for the variations)',
      stepsLabel: 'Variations (further columns)',
      unmarked: 'base prompt',
      noteBody: 'An image model is trained on data in which some parts of the world appear millions of times and others rarely. Where the training was thin, the model fills the gap from what was frequent. That becomes recognisable when the model receives the base prompt once on its own and once with a variation. Prompted with \u2018Seasons in January\u2019, two of three models returned northern-hemisphere winter in 102 pictures out of 102 (Shin et al. 2024). On prompts with a cultural expectation, 44 % of the ratings lay below full agreement with the prompt, and nearly half of those concerned an implicit cultural expectation (the CULTURALFRAMES benchmark, Nayak et al. 2025). In the study\'s example a couple receives the parents\' blessing and the parents are absent from the picture. The emotions in the list are the six basic emotions of Ekman and Friesen (1971), which in the taxonomy of Baron-Cohen, Golan, Wheelwright and Hill (2004) are also the basis of the teaching software \u201cMind Reading\u201d. The comparison shows which visual constructions of emotionality the models have, and how far they differ from one another.',
      modelsLabel: 'Models',
      regions: {
        emotions: 'Basic emotions',
        westAfrica: 'West Africa',
        eastAfrica: 'East Africa',
        southernAfrica: 'Southern Africa',
        northAfricaWestAsia: 'North Africa and West Asia',
        centralAsia: 'Central Asia',
        southAsia: 'South Asia',
        southeastAsia: 'Southeast Asia',
        eastAsia: 'East Asia',
        oceania: 'Oceania',
        northAmerica: 'North America',
        southAmerica: 'South America and the Caribbean',
        europe: 'Europe',
      },
      cellFailed: 'Nothing came back.',
      runFailed: 'A picture did not arrive: {m}',
    },
    // Prompt Interception, the group, and its first instrument. `tabs` is what
    // the column on the left says (read through I18N_ROOT, like the labs);
    // `models` is everything the surface itself says. The address has the
    // shape of the census's: German is the authored side, this is set after
    // it.
    interception: {
      tabs: {
        // The line under a name in the column, and what Help says when it is
        // asked what an instrument is in one sentence. Each says what THIS
        // instrument varies, because that is what tells the three apart.
        'interception-models': {
          label: 'Language Model Comparison',
          short: 'The same line, written by one model after another',
        },
        'interception-template': {
          label: 'Interception Scope',
          short: 'The same template, written through one perspective after another',
        },
        'interception-poles': {
          label: 'Aesthetic Poles',
          short: 'One template, an aesthetic checklist set property by property, and a row for every setting',
        },
      },
      models: {
        // `story` and `purpose` are what Help answers with when it is asked what
        // this instrument is and how it is read. They say what the surface does,
        // and they name no outcome: what a given model makes of a given line is
        // the finding a visitor is here to make.
        story: 'Prompt Interception is the step in which this platform writes a prompt over again through a perspective. Here that step runs several times on the same prompt, once per writing model. Write the prompt, choose the perspective it is to be written through, and tick the models that are to write; one image model puts a picture beside each text. The top row holds the prompt as it was written, and what the image model makes of it with that step left out.',
        purpose: 'This instrument compares texts; the picture beside a text is what one image model made of it. Between two rows the writing model is the only difference: the prompt, the perspective, the adaption each image model carries and the seed are the same for every row.',
        generate: 'Run the series',
        // The one perspective every row is written through. It stands in the
        // column as a disc, and where none is chosen yet as the empty place of
        // one — the same strip the second instrument fills with several.
        perspectiveLabel: 'Perspective',
        perspectiveAdd: 'Choose a perspective',
        writingModelsLabel: 'Writing models',
        // Which models write, as three lineups rather than as every model the
        // installation offers. Sixteen fields are a catalogue, and a catalogue
        // asks nothing; each of these three asks one question and holds
        // everything else still. The models a lineup stands for are data
        // (devserver/config/model_register.json), never a list in the surface.
        // Named the way Bias Research names its four: the bare noun phrase
        // for the group, the members by name in the title.
        lineups: {
          openWeights: 'Open Weights',
          openWeightsNote: 'Mistral Large 3, DeepSeek V4 Pro, GLM 5.3, Kimi K3',
          closedWeights: 'Closed Weights',
          closedWeightsNote: 'Claude Sonnet 5, Gemini 3.7 Flash, GPT-5.6 Terra',
          family: 'model family',
          familyNote: 'the sizes of the Qwen family, 4B to 27B',
        },
        modelsUnavailable: 'The list of writing models did not arrive.',
        imageModelLabel: 'Image model',
        interceptedLabel: 'Rewritten prompt',
        asWritten: 'Reference image',
        notYetRun: 'not yet run',
        // The research paragraph alone. An earlier first paragraph on what
        // the surface holds equal was struck: its four sentences were refuted
        // or said what every run does.
        noteBody: 'From one and the same prompt, language models write differently. Fang et al. (2024) had seven language models (Grover, GPT-2, GPT-3-curie, GPT-3-davinci, ChatGPT, Cohere and LLaMA-7B) write news articles from the headlines of articles published by The New York Times and Reuters, and compared each machine-written article with the human-written one that carried the same headline. All seven wrote on average a smaller share of words referring to Black people than the original article carried, counted among the words referring to White, Black and Asian people, from 1.93 percentage points less for ChatGPT to 11.74 for Grover. The share of a model\u2019s articles that carried a smaller proportion of female-specific words than the original ran from 56% for GPT-3-curie to 74% for Grover.',
        referencesTitle: 'Research References',
        // What the route refused FOR, one sentence per cause, keyed by the
        // route's own word for it. Its message is English maintainer prose and
        // is never shown; two of its causes the platform already says in its
        // own words (`generationError.causeNoModel` for a model listed and
        // installed nowhere, `generationError.causeUnreachable` for a service
        // that did not answer), and those two are reused rather than said a
        // second time here.
        refused: {
          not_a_string: 'The request named no model.',
          unknown_model: 'This model is outside the models this installation offers.',
          provider_without_key: 'This model is reached through a provider this installation holds no API key for.',
          preset_binds_model: 'This perspective brings its own writing model.',
          not_interception_preset: 'This perspective belongs to another step of the pipeline.',
          no_interception_step: 'This perspective runs here without an interception step.',
          register_broken: 'The model register holds no entry for this model\'s service; this installation has to be repaired.',
          chunk_template_missing: 'The perspective\u2019s chunk template is missing on this installation.',
        },
        // The gate refused the PERSPECTIVE a row was to be written under — the
        // platform's own text, not the visitor's line. The sentences the
        // platform says about a blocked line speak to the person who wrote it
        // and would name the wrong author here.
        refusedPerspective: 'Refused: the check stopped the text this row is written under.',
        // The one sentence left where a backend names no cause. It is true of
        // every one of the six the route keeps apart under 400, and reading
        // which one off the wording of its message is what the platform
        // forbids.
        refusedRequest: 'Refused: this model cannot write this perspective on this installation.',
        cellFailed: 'Nothing came back.',
        // The one case a picture's reading has that carries no cause of its own:
        // the reader answered, and what it answered holds no reading. Shared,
        // like the refusals above: both instruments that read a picture into
        // their template say it (`composables/usePictureTemplate.ts`).
        readingFailed: 'The reading came back empty.',
        runFailed: 'A picture did not arrive: {m}',
      },
      // The second instrument. What a refusal and an empty cell SAY is the
      // group's and stands once, under `models`; what is here is what this
      // instrument alone puts on its surface.
      template: {
        // What Help answers with. The picture is DRAGGED ONTO the template field,
        // which every field on this platform takes and none announces; said here
        // because a visitor asking Help what to do with a picture is asking about
        // this surface, where the reading becomes the template.
        story: 'Prompt Interception is the step in which this platform writes a prompt over again through a perspective. Here that step runs several times on the same template, once per perspective, and one image model shows what each of them wrote. Write the template \u2014 or drag a picture onto the field, and its description then stands there as the template, where it can be worked on further. Choose the perspectives. Where the template was written, the first picture holds it with that step left out; where it was read from a picture, that picture stands first as the reference and the picture beside it is the first step, with no perspective on it; resting on a perspective \u2014 holding it, on a touch screen \u2014 shows the text that perspective wrote.',
        purpose: 'Every picture carries the same template, and between two of them the perspective is the only difference, so a picture can be read for what that one perspective does to the template. The writing model is the one this platform is set to intercept with, and this surface makes no choice about it. One image model runs, because what is compared here is perspectives \u2014 the comparison of image models is its own instrument.',
        generate: 'Run the series',
        templateLabel: 'Template',
        perspectivesLabel: 'Perspectives',
        perspectiveAdd: 'Choose a perspective',
        perspectiveRemove: 'Take this perspective off',
        imageModelLabel: 'Image model',
        // SUPPLIED WORDING, platform-wide: the first row of ALL THREE Prompt
        // Interception rasters is `Reference image` / „Referenzbild"
        // (WO-2026-09-05-I). Here it holds where the template was TYPED; with
        // a picture on the surface the word moves to the picture and this row
        // carries `withoutPerspective`. Not to be shortened, generalised or
        // re-split.
        asWritten: 'Reference image',
        // The uploaded picture, first on the wall. Where a picture stands,
        // THE PICTURE is the reference, and one picture more stands on the
        // surface than a typed template puts there.
        sourcePicture: 'Reference image',
        // The row under that picture: the picture read into a template and
        // generated back. Translating the picture into a prompt and generating
        // from that prompt is already the first manipulation, only without a
        // preset, so the row is named by the step it skipped.
        withoutPerspective: 'Without perspective',
        notYetRun: 'not yet run',
        // The research paragraph alone, as under `models` (2026-09-22).
        noteBody: 'De Rosa Palmini and Cetinic (2025) grouped prompts from a public image platform by how much wording they share: groups sharing 80% or more of their words came with consistently more uniform pictures than groups sharing 50 to 70%. Across the months they sampled, richer and less repetitive wording went with more varied pictures (measured with the Vendi score). In Stable Diffusion, modifiers written expressly against a stereotype often left it in place: for \u2018a white poor person\u2019 the model still produced mostly dark-skinned faces, for \u2018a photo of an African man and his fancy house\u2019 still a simple hut (Bianchi et al. 2023).',
        referencesTitle: 'Research References',
      },
      // The third instrument. What a refusal and an empty cell SAY is the
      // group's and stands once, under `models`; what is here is what this
      // instrument alone puts on its surface.
      poles: {
        // What Help answers with. The scale words are VisionReward\u2019s own and
        // stand in English in every language of this platform.
        story: 'One aesthetic checklist, set property by property, and what a model writes from it and the template. Write the template \u2014 or drag a picture onto the field, and its description then stands there as the template. Every property that can carry a handle is a scale of words with one handle on it; a property left at its neutral word stays out of the prompt. Five chips over the bars set the whole checklist at once, and from there each property is moved on its own. One setting is one prompt. Every run adds a row, and the first row stays: the checklist at its neutral word throughout, which every picture beside it is read against. Where the template was read from a picture, that picture stands first as the reference, and the picture beside it is the first step, with no setting on it. One image model runs, so what parts two pictures is the setting. Resting on a picture\'s name \u2014 holding it \u2014 shows what was set and what the model wrote from it.',
        purpose: 'The properties come from the human labelling guidelines of VisionReward, where each of them carries one ordered list of words with one of those words marked as the neutral one. Those guidelines give one position on such a list, which is why there is one handle here. The lists are of different lengths and reach different distances to either side, so each property is set on its own rather than by one axis over all of them, and a setting is free to stand at the good end of one property and at the bad end of the next. Every row is written by the same model from the same template, so what stands between two rows is the setting, and the pictures show what the checklist does to a template.',
        generate: 'Run the series',
        templateLabel: 'Template',
        // The ONE image model every picture on the wall comes out of.
        imageModelLabel: 'Image model',
        // The checklist itself, one scale to a property.
        dimensionsLabel: 'Properties',
        // The whole checklist at one place, over the bars that set it. These
        // five are THIS PLATFORM\u2019S words and not VisionReward\u2019s, which names
        // the places of each scale and no level across them \u2014 hence the
        // quotation marks, which also keep them apart from the scale words
        // underneath.
        level: {
          best: '\u201cbest\u201d',
          better: '\u201cbetter\u201d',
          neutral: '\u201cneutral\u201d',
          worse: '\u201cworse\u201d',
          worst: '\u201cworst\u201d',
        },
        // Which step of the series a row is, where its setting writes nothing to
        // name it by. The reference row is the only such row.
        trialLabel: 'Run {n}',
        // The presets are here and no property on them can be set. A different
        // fact from the one below, and it names its own cause.
        tooFewProperties: 'No property on this checklist can carry a handle.',
        // While the fetch that brings the presets is still out. The line below
        // is about a checklist that CAME BACK absent, which is a different fact
        // and reads as one.
        checklistLoading: 'The checklist is still on its way.',
        // The checklist never arrived, and without it there is no scale to set
        // and nothing to run.
        checklistUnavailable: 'The checklist is missing.',
        interceptedLabel: 'Rewritten prompt',
        // The first row, where the template was TYPED. With a picture on the
        // surface the word moves to the picture and this row carries
        // `withoutSetting`.
        asWritten: 'Reference image',
        // The uploaded picture, first on the wall and the reference there.
        sourcePicture: 'Reference image',
        // The row under that picture: the checklist at neutral, which writes
        // nothing into the prompt, on the picture read into a template.
        withoutSetting: 'Without setting',
        notYetRun: 'not yet run',
        noteBody: 'The framework VisionReward (Xu et al. 2024) contains a set of annotation guidelines for human raters judging generated images. Each property comes with an ordered list of options the rater picks from (for Clarity: very clear, clear, ordinary, blurry, completely blurry), one of which is the neutral option. Which end of a list counts as the bad one is built into the measurement: VisionReward\'s checklist asks, for instance, whether the image avoids being blurry. A model trained on such judgements can carry the scale as a norm (Guo et al. 2025).',
        referencesTitle: 'Research References',
      },
    },
    workbench: {
      headerTitle: 'Encoder Fusion Workbench — a generic 3-axis comparison instrument',
      headerSubtitle: 'Assign any parameter to each axis and give it a value list: X = columns, Y = rows, Z = the drive-through slider.',
      headerSubtitleDetail: 'Assign any parameter to each axis and give it a value list: X = columns, Y = rows, Z = the drive-through slider. Everything else stays constant. Each cell is one generation; scrub Z to move through the third dimension.',
      axisX: 'X · columns',
      axisY: 'Y · rows',
      axisZ: 'Z · slider (drive-through)',
      param: {
        prompt: 'Prompt',
        alpha: 'α (fusion strength)',
        cfg: 'CFG',
        step: 'Denoising window',
        layer: 'Entry block',
        strategy: 'Fusion strategy',
        seed: 'Seed',
        none: 'No third axis'
      },
      stepMark: {
        composition: 'composition',
        semantics: 'semantics',
        detail: 'detail'
      },
      windowSteps: 'Steps {from}–{to}',
      windowNone: 'No injection',
      layerFrom: 'From block {block}',
      stepWindowHint: 'The fusion is injected only in the steps the window covers, of {steps} in the run.',
      layerHint: 'The fused conditioning enters at this transformer block and stays in effect through every later one.',
      zNoneHint: 'Two axes then carry the sweep, and this axis shows no slider.',
      valuesNumberHint: 'Comma-separated numbers, e.g. 0, 10, 15, 20, 25, 35.',
      valuesTextHint: 'One prompt per line — each line becomes a row / column / slide.',
      valuesPromptHint: 'Up to 3 prompts; each can be T5-expanded (added to T5 only, kept constant across the sweep).',
      promptAdd: '+ Prompt',
      promptRemove: 'Remove prompt',
      t5Expand: 'T5 expand',
      t5Expanding: 'Expanding…',
      t5Placeholder: 'Optional T5 enrichment — added to the T5 encoder only, held constant across the sweep',
      t5ExpandFailed: 'T5 expansion failed',
      // The platform's own word for the block that folds the seldom-set
      // values away, verbatim as every other surface says it.
      advancedLabel: 'Advanced settings',
      negativeLabel: 'Negative',
      stepsLabel: 'Denoising steps',
      runSweep: 'Run sweep',
      cells: 'cells',
      driveLabel: 'Drive-through',
      emptyHint: 'Assign the axes, then run a sweep. Each cell is recorded to the research store (purpose: workbench).',
      fusionFormulaLabel: 'Fusion formula (active)',
      formulaCore: 'core',
      formulaTail: 'tail',
      formulaLegend: 'core = the first 77 token positions (CLIP-L+CLIP-G, padded to 4096d) blended with T5; tail = the T5-only remainder (positions 78–512). α is the fusion strength value.'
    },
    attention: {
      referencesTitle: 'Research References',
      // The address. German is the authored side; this is set after it,
      // sentence by sentence. Recast without an address: the purpose lost its
      // task-voice opening and its address, the story its fixed number 25,
      // because the steps are settable, 10 to 50 (attention_cartography.vue:81).
      // The attention imperative "Compare an early computing step with a late
      // one" directs seeing and stays (docs/COPY_RULES.md: the address is the
      // exception, not the form).
      story: 'Enter a prompt and click "Generate + Analyze"; the image model generates an image for it. Below, the same prompt stands once more, split into single words: click one, and the page draws a colour patch over the image exactly where this word had the most influence in the computation; several words carry several colours. Three controls change the view: the slider picks one of the computation steps, the network depth the layer within it (shallow, middle, deep), and the text-encoder control switches between the two decompositions of the same prompt that the model uses side by side.',
      purpose: 'The influence of a word spreads over areas, softly bounded and often somewhere other than expected: a word that mattered in the prompt sometimes gets only a small area, a passing one an area over half the picture. Compare an early computing step with a late one. And where a word begins and ends the model sets itself: the one decomposition has 77 tokens for the prompt, the other up to 512, and a long word falls into pieces that only together make the word again.',
      headerSubtitle: 'For each word in the prompt, a heatmap overlay on the generated image shows WHERE in the image that word had the most influence.',
      headerSubtitleDetail: 'For each word in the prompt, a heatmap overlay on the generated image shows WHERE in the image that word had the most influence. This reveals how the model spatially distributes semantic concepts.',
      explanationToggle: 'Show detailed explanation',
      explainWhatTitle: 'What does this tool show?',
      explainWhatText: 'When a diffusion model generates an image, it does not read the prompt word by word. Instead, a mechanism called "attention" distributes the influence of each word across different image regions. The word "house" mainly influences the region where the house appears — but also neighboring areas, because the model understands the context of the entire scene. This tool makes that distribution visible: a clicked word shows the image regions it influences most.',
      explainHowTitle: 'How do I read the heatmap?',
      explainHowText: 'Bright, intense color = strong influence of the word on that region. Dark or absent color = little influence. If you select multiple words, they appear in different colors. Note: the maps are NOT perfectly sharp-edged — this is not a bug, but shows that the model processes concepts contextually, not in isolation. A "house" in a farm scene also has some influence on animals and fields, because the model understands the scene as a whole.',
      explainReadTitle: 'What do the two sliders reveal?',
      explainReadText: 'The denoising step slider shows WHEN in the 25-step generation process you are viewing attention. Early steps show rough layout planning, late steps show detail assignment. The network depth selector shows WHERE in the transformer attention is measured: shallow layers (near input) show global composition planning, middle layers semantic assignment, deep layers fine-tuning. Both axes are independent — it is worth systematically exploring different combinations.',
      techTitle: 'Technical details',
      techText: 'SD3.5 uses an MMDiT (Multimodal Diffusion Transformer) with joint attention: image and text tokens attend to each other across 24 transformer blocks. We replace the default SDPA processor with a manual softmax(QK^T/√d) processor at 3 selected blocks to extract the text→image attention submatrix. Maps are 64x64 resolution (patch grid), upscaled to image resolution via bilinear interpolation. SD3.5 has three text encoders — CLIP-L (BPE, 77 tokens), CLIP-G (BPE, 77 tokens) and T5-XXL (SentencePiece, 512 tokens); two of them can be toggled here to see how different tokenization strategies affect attention.',
      promptLabel: 'Prompt',
      promptPlaceholder: 'e.g. A house stands in a landscape, surrounded by farmland, nature and animals. Some people can be seen.',
      promptPlaceholderDetail: 'e.g. A house stands in a landscape, surrounded by farmland, nature and animals. Some people can be seen.',
      generate: 'Generate + Analyze',
      advancedLabel: 'Advanced settings',
      negativeLabel: 'Negative Prompt',
      stepsLabel: 'Steps',
      cfgLabel: 'CFG',
      seedLabel: 'Seed',
      tokensLabel: 'Tokens',
      tokensHint: 'Click one or more words. Multiple words appear in different colors.',
      tokensHintDetail: 'Click one or more words. Subword tokens (e.g. "Ku"+"gel") are automatically combined. Multiple words appear in different colors.',
      timestepLabel: 'Denoising step',
      timestepHint: 'This slider shows what the model attends to at each step.',
      timestepHintDetail: 'Diffusion models generate images in 25 steps from noise to image. Early steps establish rough structure, late steps refine details. This slider shows what the model attends to at each step.',
      step: 'Step',
      layerLabel: 'Network depth',
      layerHint: 'Both controls are independent: step = when in the process, depth = where in the network.',
      layerHintDetail: 'At every denoising step, the signal passes through all 24 transformer layers. Shallow layers (near input) capture global composition, middle layers semantic assignment, deep layers (near output) fine details. Both controls are independent: step = when in the process, depth = where in the network.',
      layerEarly: 'Shallow (Composition)',
      layerMid: 'Middle (Semantics)',
      layerLate: 'Deep (Detail)',
      layerAll: 'All layers',
      opacityLabel: 'Heatmap',
      opacityHint: 'Strength of the colored overlay on the image.',
      baseImageLabel: 'Base image',
      baseColor: 'Color',
      baseBW: 'B/W',
      baseOff: 'Off',
      baseImageHint: 'Color shows the original image. B/W desaturates it so heatmap colors stand out. Off hides the image entirely and shows only the attention map.',
      encoderLabel: 'Text Encoder',
      encoderClipLG: 'CLIP-L + G (77 Tokens)',
      encoderT5: 'T5-XXL (512 Tokens)',
      encoderHint: 'SD3.5 uses two text encoders with different tokenization.',
      encoderHintDetail: 'SD3.5 uses two text encoders with different tokenization. CLIP-L uses BPE (Byte-Pair Encoding), T5-XXL uses SentencePiece. Compare how both encoders process the same prompt and which image regions each one steers.'
    },
    probing: {
      promptBFailed: 'Prompt B: {m}',
      promptExamples: {
        housesLabel: 'A red house by the lake / A blue house by the lake',
        housesA: 'A red house by the lake',
        housesB: 'A blue house by the lake',
        // Every entry addresses ONE observable property, and the comment
        // under it names the property and the surface that can evaluate it
        // (P2/P6). This is a PAIR, not two
        // offers: one entry fills both fields, and the surface holds the
        // seed (fixed default seed, one seed over a run's images), so
        // the property is readable in the pair.
        // Property: WIE at held WAS — same scene, the material changed
        // (catalogue #5). Surface: this surface (seed discipline);
        // Model Comparison (fixed seed). Source: the platform's WAS/WIE
        // separation.
        streetLabel: 'the street where I live, in the morning, as a pencil drawing / the street where I live, in the morning, as an oil painting',
        streetA: 'the street where I live, in the morning, as a pencil drawing',
        streetB: 'the street where I live, in the morning, as an oil painting',
        // A probing pair holds two clearly separated vectors. The old
        // border-experiment pair carried its contradiction inside one
        // sentence ("sunny ... at night"), and the model collapsed it
        // into day-for-night, so the difference carried nothing
        // readable. Contradictory rules (catalogue #10) stay single
        // sentences and do not pair.
        // Property: time of day — noon against midnight on a held scene.
        // The time words are the only changing words, and no colour or
        // brightness word can satisfy both scenes at once (P3; the
        // time-of-day kin of catalogue #5's minimal pairs).
        // Surface: this surface (seed discipline).
        timeLabel: 'a meadow at noon / a meadow at midnight',
        timeA: 'a meadow at noon',
        timeB: 'a meadow at midnight'
      },
      headerTitle: 'Dimension Explorer',
      headerSubtitle: 'Compare two prompts and discover which embedding dimensions encode the semantic difference.',
      headerSubtitleDetail: 'Compare two prompts and discover which embedding dimensions encode the semantic difference. Selectively transfer individual dimensions to see how they affect the image.',
      explanationToggle: 'Show detailed explanation',
      explainWhatTitle: 'What does this tool show?',
      explainWhatText: 'Every word is converted by the text encoder into a high-dimensional vector (e.g. 4096 dimensions for T5). When you change a word in the prompt — e.g. "red" to "blue" — certain dimensions change more than others. This tool shows you WHICH dimensions change most and lets you selectively transfer individual dimensions from prompt B into prompt A.',
      explainHowTitle: 'How does the transfer work?',
      explainHowText: 'The bar chart shows all dimensions sorted by difference magnitude. Use the rank range controls (From/To) to select a window — e.g. just the top 100 or specifically ranks 880–920. Clicking ▶ 2 regenerates the image with the same settings (same seed!) — but with selected dimensions from prompt B. This lets you see exactly what those dimensions "encode".',
      explainReadTitle: 'How do I read the bar chart?',
      explainReadText: 'Each bar represents one embedding dimension. The length shows how much that dimension differs between prompt A and B. Dimensions with large differences are the most likely carriers of the semantic change. But note: embeddings are distributed — often multiple dimensions together are needed to produce a visible change.',
      techTitle: 'Technical details',
      techText: 'SD3.5 uses three text encoders: CLIP-L (768d), CLIP-G (1280d) and T5-XXL (4096d). You can probe each individually. The difference is computed as mean absolute deviation across all token positions: mean(abs(B-A), dim=tokens). The transfer replaces selected dimensions across all token positions simultaneously.',
      promptALabel: 'Prompt A (Original)',
      promptBLabel: 'Prompt B (Comparison)',
      promptAPlaceholder: 'e.g. A red house by the lake',
      promptBPlaceholder: 'e.g. A blue house by the lake',
      encoderLabel: 'Encoder',
      encoderAll: 'All (recommended)',
      encoderClipL: 'CLIP-L (768d)',
      encoderClipG: 'CLIP-G (1280d)',
      encoderT5: 'T5-XXL (4096d)',
      analyzeBtn: 'Analyze',
      // The word on the second trigger, which stands IN the left column under the
      // rank selection. `transferBtn` is the whole sentence and is its hover
      // text: at the width of a column it says nothing.
      transferAction: 'Transfer',
      analyzing: 'Encoding and comparing prompts...',
      transferBtn: 'Transfer selected vector dimensions from Prompt B into the generated image',
      transferring: 'Generating image with modified embedding...',
      generatingB: 'Generating image of prompt B...',
      stoppedByB: 'Not generated, because the run of prompt B was blocked.',
      rankFromLabel: 'From rank',
      rankToLabel: 'To rank',
      sliderLabel: 'Select dimensions from Prompt B',
      range1Label: 'Range 1',
      range2Label: 'Range 2',
      addRange: 'Add range',
      selectionDesc: '{count} dimensions from Prompt B selected (rank {ranges} of {total})',
      listTitle: 'The {count} dimensions from Prompt B with the largest difference to Prompt A',
      sortAsc: 'Ascending',
      sortDesc: 'Descending',
      originalLabel: 'Original (Prompt A)',
      modifiedLabel: 'Modified (Transfer from Prompt B)',
      originalBLabel: 'Original (Prompt B)',
      modifiedHint: 'Select a rank range below and click ▶ 2 — this will show prompt A with the transferred dimensions from B (same seed).',
      noDifference: 'The embeddings are identical — change prompt B.',
      advancedLabel: 'Advanced settings',
      negativeLabel: 'Negative Prompt',
      stepsLabel: 'Steps',
      cfgLabel: 'CFG',
      seedLabel: 'Seed',
      selectAll: 'All',
      selectNone: 'None',
      encoderHint: 'All = all encoders combined. CLIP-L/CLIP-G/T5 = isolates one encoder for the analysis.',
      sliderHint: 'Select a rank range of the most important embedding dimensions (sorted by difference between A and B).',
      transferHint: 'Transfers the selected dimensions from Prompt B onto Prompt A and generates a new image.',
      downloadOriginal: 'Download Original',
      downloadModified: 'Download Modified'
    },
    algebra: {
      promptExamples: {
        riverLabel: 'the street where I live, in the morning, with an animal − the street where I live, in the morning + a river',
        riverA: 'the street where I live, in the morning, with an animal',
        riverB: 'the street where I live, in the morning',
        riverC: 'a river',
        // Every entry addresses ONE observable property, and the comment
        // under it names the property and the surface that can evaluate it
        // (P2/P6). This is a TRIPLET, not
        // three offers: one entry fills all three fields, and the surface
        // holds the seed (same seed for reference and result), so the
        // displacement is readable against the reference.
        // Property: WAS at held WIE — same scene frame, the seen-from role
        // changed (catalogue #4, the role side of the WAS/WIE separation;
        // the material side is #5 and belongs to Feature Probing). The
        // algebra reads as word2vec analogy: child → adult at the held
        // street. B ≠ A: the subtraction must carry the direction, so B is
        // the held scene
        // WITHOUT the role (like river: B = A minus the one variable
        // element), and C the adult counterpart. With the old B = A the
        // reference collapsed (A − A = 0) and the result was trivially C.
        // Source: the platform's WAS/WIE separation; Mikolov et al. 2013
        // (the analogy the instrument carries).
        childLabel: 'the street where I live, in the morning, seen through the eyes of a child − the street where I live, in the morning + the street where I live, in the morning, seen through the eyes of an adult',
        childA: 'the street where I live, in the morning, seen through the eyes of a child',
        childB: 'the street where I live, in the morning',
        childC: 'the street where I live, in the morning, seen through the eyes of an adult',
        // Property: abstract concept as direction (catalogue #6, the
        // algebra side): an abstract concept with nothing further given
        // has no scene of its own, and what the addition carries is a
        // register, not a thing — the displacement shows how far an
        // abstract concept moves an image at all. B ≠ A: B is the evening
        // street WITHOUT the people (river pattern), C the abstract concept,
        // so the
        // direction B→C (held scene → loneliness) is what displaces the
        // reference: does the crowd leave the picture, or does only the
        // register darken? Surface: this surface.
        // Source: teotia-et-al-2025 (DIMCIM); the platform's concept note
        // on abstract concepts.
        lonelyLabel: 'a street in the evening, with people − a street in the evening + loneliness',
        lonelyA: 'a street in the evening, with people',
        lonelyB: 'a street in the evening',
        lonelyC: 'loneliness'
      },
      headerTitle: 'Concept Algebra \u2014 Vector arithmetic on image embeddings',
      headerSubtitle: 'Apply the famous word2vec analogy to image generation: King − Man + Woman ≈ Queen.',
      headerSubtitleDetail: 'Apply the famous word2vec analogy to image generation: King − Man + Woman ≈ Queen. Three prompts are encoded and algebraically combined.',
      explanationToggle: 'Show detailed explanation',
      explainWhatTitle: 'What does this tool show?',
      explainWhatText: 'In 2013, Mikolov showed that word embeddings encode semantic relationships as linear directions: the vector for "King" minus "Man" plus "Woman" yields a vector close to "Queen". This tool applies that idea to SD3.5’s text encoders: instead of single words, you manipulate entire prompt embeddings. The result is an image that has moved away from A along the direction B→C. How far it moves, and in what respect, is what the tool lets you look at.',
      explainHowTitle: 'How does the algebra work \u2014 and why not just use a negative prompt?',
      explainHowText: 'You enter three prompts: A (base), B (subtract), and C (add). The formula is: Result = A − Scale₁×B + Scale₂×C. The scale sliders control intensity: at 1.0, B is fully subtracted and C fully added. At 0.5, only half. Values above 1.0 amplify the effect. — Why not just use "A + C" as the prompt and "B" as the negative prompt? Because the two happen in different places. A negative prompt is the baseline that guidance is measured from, so it acts inside the denoising loop, at every one of the 25 steps, against the image as it currently stands. Concept Algebra computes a new vector BEFORE generation: the arithmetic happens in embedding space, once, and the loop never learns that anything was subtracted. — What the subtraction does not do is delete a named object. Our own measurement series on this platform found that subtracting one prompt vector from another shifts tone, framing and register, but leaves the named thing in the picture. Read the result as a displacement in meaning-space, not as a removal.',
      explainReadTitle: 'What do the results mean?',
      explainReadText: 'On the left you see the reference image (prompt A only, same seed). On the right, the algebra result. If the analogy works, the right image should show concept A but with the semantic change B\u2192C. Example: "Sunset at the beach" \u2212 "Beach" + "Mountains" \u2248 "Sunset over mountains". The L2 distance shows how far the result has moved from the original. \u2014 Is the operation commutative? No. Subtraction of B and addition of C happen relative to vector A. The direction B\u2192C only makes sense in the context of A: "King \u2212 Man" removes the "male" directions from the King vector, "+ Woman" adds the "female" directions \u2014 the result lands near "Queen". C is not surgically placed where B was removed; it is simply added. That this still works shows that semantic relationships are encoded as consistent linear directions in the vector space.',
      techTitle: 'Technical details',
      techText: 'The algebra is performed on the selected encoder embeddings: CLIP-L (768d), CLIP-G (1280d), T5-XXL (4096d), or all combined (589 tokens \u00d7 4096d). The same operation is also applied to pooled embeddings (2048d). Both images use the same seed for fair comparison.',
      referencesTitle: 'Research References',
      promptALabel: 'Prompt A (Base)',
      promptAPlaceholder: 'e.g. the street where I live, in the morning, with an animal',
      promptBLabel: 'Prompt B (Subtract)',
      promptBPlaceholder: 'e.g. the street where I live, in the morning',
      promptCLabel: 'Prompt C (Add)',
      promptCPlaceholder: 'e.g. a river',
      formulaLabel: 'A \u2212 B + C = ?',
      encoderLabel: 'Encoder',
      encoderAll: 'All (recommended)',
      encoderClipL: 'CLIP-L (768d)',
      encoderClipG: 'CLIP-G (1280d)',
      encoderT5: 'T5-XXL (4096d)',
      generateBtn: 'Compute',
      generating: 'Computing embeddings and generating images...',
      referenceLabel: 'Reference (Prompt A)',
      resultLabel: 'Result (A \u2212 B + C)',
      l2Label: 'L2 distance from original',
      advancedLabel: 'Advanced settings',
      negativeLabel: 'Negative Prompt',
      stepsLabel: 'Steps',
      cfgLabel: 'CFG',
      seedLabel: 'Seed',
      scaleSubLabel: 'Subtraction scale',
      scaleAddLabel: 'Addition scale',
      encoderHint: 'All = all encoders combined. CLIP-L/CLIP-G/T5 = isolates one encoder for the arithmetic.',
      scaleSubHint: 'Weight of subtraction (B). Higher = stronger removal of concept B.',
      scaleAddHint: 'Weight of addition (C). Higher = stronger injection of concept C.',
      l2Hint: 'Euclidean distance in embedding space. Smaller = more similar, larger = more different.',
      downloadReference: 'Download Reference',
      downloadResult: 'Download Result',
      resultHint: 'Enter three prompts and click Compute \u2014 the result of the vector arithmetic will appear here.'
    },
    composable: {
      promptExamples: {
        house: 'a red house on a hill',
        ship: 'a blue ship on the ocean',
        // Every entry addresses ONE observable property, and the comment
        // under it names the property and the surface that can evaluate it
        // (P2/P6). An entry is one concept
        // per concept field — a COMBINATION, not a pair; the pair
        // properties (#5, #9) belong to the surfaces that hold the seed
        // (Feature Probing, Model Comparison, Mean Images promptFixed),
        // not here, where every concept is scored separately at every
        // step. One seed holds over the run's images either way.
        // Property: WAS at held WIE — same scene frame, the role changed
        // (catalogue #4): each concept is one reading of the same street,
        // and the combination asks which reading the run turns towards
        // and how far. Source: the platform's WAS/WIE separation.
        childAdult: 'the street where I live, in the morning, seen through the eyes of a child',
        childAdult2: 'the street where I live, in the morning, seen through the eyes of an adult',
        // Property: separate energies for separate concepts (catalogue
        // #1's composing side — what one fused prompt would absorb): a
        // thing and its living counterpart, each with its own pass at
        // every step, and a weight turns towards or away from one of
        // them. Surface: this surface (both places, denoiser and
        // embedding). Source: Liu et al. 2022 (the conjunction the
        // instrument carries); the platform's model idiosyncrasy note.
        treeHouse: 'a tree',
        treeHouse2: 'a house',
        // Property: two concepts that SHARE most of their material, where the
        // other pairs hold two that share none. The second names a part of the
        // first, so the encodings differ in few rows and the share acts on
        // those alone. This is the pair the weighted sum failed on, either
        // the tree whole or the apples whole and never a mixture,
        // and it is the pair that shows what a share outside [0, 1] does --
        // 1.00 and -2.00 give a share of +2 and a picture of apples with no
        // tree in it. Surface: this surface, both places.
        appleTree: 'an apple tree',
        appleTree2: 'apples'
      },
      headerTitle: 'Composable Diffusion \u2014 Separate energy for each concept',
      headerSubtitle: 'Instead of encoding your entire prompt as one monolithic vector, each concept gets its own transformer pass during denoising.',
      headerSubtitleDetail: 'Instead of encoding your entire prompt as one monolithic vector, each concept gets its own transformer pass during denoising. Each one then adds its own pull on the image — or, with a negative weight, subtracts it.',
      explanationToggle: 'Show detailed explanation',
      explainWhatTitle: 'What does this tool do?',
      explainWhatText: 'Standard image generation compresses your entire prompt into a single representation. The model sees "a red house by a lake" as one fused concept. Composable Diffusion breaks this apart: "red house" and "lake" each get their own complete processing pass through the neural network at every denoising step. Their predictions are then combined with adjustable weights. This gives each concept its own "energy function" — its own vote on what the image should look like. A concept can also be given a negative weight. Then it is not blended in but subtracted at every step, as its own opposing direction alongside the positive ones. What that achieves depends on what is negated: a thing that appears in the picture as a thing can be pushed out, while a property bound to an object in the positive prompt, or a whole style register, is not removed — the image only recedes, and at high negative weights it loses content and finally over-drives. That is also a different operation from a negative prompt, which replaces the baseline the image is measured against.',
      explainHowTitle: 'How does it work technically?',
      explainHowText: 'At each of the 25 denoising steps, the model runs N+1 transformer passes: one for the negative prompt (unconditional), and one for each concept. Each concept produces its own noise prediction \u2014 and what enters the sum is not that prediction itself, but its difference from the unconditional one: noise = uncond + v1\u00d7(noise_1 - uncond) + v2\u00d7(noise_2 - uncond) + ... Each v is that concept\u2019s own guidance strength. A positive v pulls the image toward the concept (AND); a negative v pushes it away (NOT). Because every concept is scored separately at every step, none of them can be absorbed into another \u2014 which is exactly what happens inside a single fused prompt. The other place a run can combine the same concepts is the embedding: before the run their embeddings are interpolated into one. The direction turns from one concept towards the other, and the length runs between the lengths of the two readings. Only the ratio of the weights acts here, and with three or more concepts the order they stand in acts as well. The share the next concept gets is w2/(w1+w2), and only that ratio acts: multiplying every weight by -1 leaves the result bit for bit the same, so 1.00 and -2.00 give what -1.00 and 2.00 give. Weights of one sign put the share between 0 and 1, and the result between the concepts. Weights of different signs put it outside: 1.00 and -2.00 make the sum -1 and the share +2, 2.00 and -1.00 make it -1. Out there the result is no longer between the concepts. It turns past the one whose weight is the larger WITHOUT its sign, so the minus alone does not say which concept is left behind; single rows cross zero length and drop out while their neighbours are stretched. What a table like that paints is not read off the numbers. From there the run is the ordinary one, two passes per step: one for that one embedding, one for the negative prompt. The seed and the step count are the same for both places, so a pair of runs on one seed differs in the place.',
      techTitle: 'Technical details',
      techText: 'Based on Liu et al. (2022), Eq. 11 (conjunction) and Eq. 15 (negation). Each concept is encoded with all three SD3.5 encoders (CLIP-L, OpenCLIP-G, T5-XXL) independently. The custom denoising loop calls pipe.transformer() once per concept per step. In the denoiser the weights are read in one of two ways. With "normalize" on, they are shares of the CFG value: the total guidance stays at CFG, so every concept you add makes each individual share smaller. With it off, each weight is that concept\u2019s own guidance temperature, v = CFG \u00d7 weight, and a negative weight is the NOT operator \u2014 algebraically identical to the paper\u2019s eps_u + w\u00d7(eps_a - eps_b). A negative weight switches normalization off automatically, because a mixture with signs has no meaning. In the embedding neither reading applies: the concepts are interpolated there, so a weight acts through its ratio to the others, and with three or more concepts the order they stand in acts as well. VRAM: model weights are shared across passes; only activations vary. With 4 concepts, generation takes roughly 4x longer than standard (each step needs 5 transformer passes instead of 2).',
      referencesTitle: 'Research References',
      conceptLabel: 'Concept {n}',
      conceptPlaceholder: 'e.g. a red house on a hill',
      weightLabel: 'Weight',
      removeBtn: 'Remove',
      addConceptBtn: 'Add concept',
      combineLabel: 'Combination',
      combineEmbedding: 'In the embedding',
      combineDenoiser: 'In the denoiser',
      combineHint: 'In the embedding the run interpolates between the concepts once, at the start. In the denoiser it puts every concept through the model at each step and weights the predictions into one.',
      settingsToggle: 'Advanced settings',
      negativePromptLabel: 'Negative Prompt',
      negativePromptPlaceholder: 'e.g. blurry, text, watermark',
      stepsLabel: 'Steps',
      cfgLabel: 'CFG',
      seedLabel: 'Seed',
      normalizeLabel: 'Normalize weights (sum to 1.0)',
      operatorAnd: 'AND',
      operatorNot: 'NOT',
      weightHint: 'A weight above 0 adds the concept (AND). A weight below 0 subtracts it (NOT).',
      weightHintDetail: 'A weight above 0 adds the concept (AND). A weight below 0 subtracts it (NOT) — which is not the same as putting it in the negative prompt. In the embedding only the RATIO of the weights acts: the share the next concept gets is w2/(w1+w2), and multiplying every weight by -1 changes nothing, so 1.00 and -2.00 give what -1.00 and 2.00 give. Two weights of one sign keep that share between 0 and 1 and the result between the concepts. Two weights of different signs send it outside, and the result then turns past the concept whose weight is larger without its sign.',
      normalizeDisabledHint: 'Normalization is off while a concept is negated, and in the embedding.',
      normalizeDisabledHintDetail: 'Normalization is off while a concept is negated: a mixture with signs has no meaning, and each weight then acts as its own guidance strength in the denoiser (CFG × weight). It is off in the embedding as well: the run interpolates from one concept towards the next there, so a weight acts through its ratio to the others and there is nothing to normalize.',
      modeMixture: 'Composition: mixture \u2014 the weights are shares of one CFG value.',
      modeTemperature: 'Composition: per-concept guidance \u2014 each weight is its own strength (CFG \u00d7 weight).',
      modeEmbedding: 'Composition: interpolation — the ratio of the weights sets how far the result turns from one concept towards the next.',
      negatedInfo: '{n} negated.',
      generateBtn: 'Generate',
      generating: 'Composable generation in progress...',
      resultInfo: '{concepts} concepts {\'|\'} {time} {\'|\'} seed {seed}',
      downloadBtn: 'Download',
    },
    archaeology: {
      headerTitle: 'Denoising Archaeology \u2014 How does noise become an image?',
      // The address. German is the authored side; this is set after it,
      // sentence by sentence. Recast without an address: "pulls out" (a
      // metaphor) and the fixed number 25 fell (the steps are settable, 10 to
      // 50), the phase arc of the purpose gave way to an attention imperative,
      // since that point belongs to the visitor, and the backbones stand as
      // the surface writes them (denoising_archaeology.vue:426-427).
      story: 'An image generator starts from pure random noise, a flicker with no object in it, and removes that noise step by step, preset at 25, until a scene is left. The platform holds every single one of those steps; the slider in the left column picks which of them fills the view. Two nets stand at the Backbone to choose from, SDXL (2023) and SD 3.5 (2024), and every run stays under "Runs".',
      purpose: 'The model works on the whole picture at once, step by step. Go back and forth along the slider and watch for the step from which the scene is recognisable. That point shifts with the prompt and with the model; for that, compare two runs with the same prompt.',
      headerSubtitle: 'Observe every single denoising step.',
      headerSubtitleDetail: 'Observe every single denoising step. Diffusion models don\'t draw left-to-right \u2014 they work everywhere simultaneously, from rough shapes to fine detail.',
      explanationToggle: 'Show detailed explanation',
      explainWhatTitle: 'What does this tool show?',
      explainWhatText: 'A diffusion model creates an image by progressively removing noise. Unlike drawing from left to right, the model works on ALL image regions simultaneously. In the first steps, rough structures emerge: Where is up, where is down? Where is the horizon? In the middle steps, semantic content appears: objects, shapes, colors. The final steps refine textures and details. This tool makes every single step visible.',
      explainHowTitle: 'How do I use this tool?',
      explainHowText: 'Enter a prompt and start the run with the triangle in the bar above the surface. The model produces one intermediate image per denoising step. One of them fills the view at a time; the slider in the left column names the sections of the run, and moving along it steps from one image to the next. Compare early and late steps: at which step does the picture turn from noise into a scene?',
      explainReadTitle: 'Three zones',
      explainReadText: 'Early steps: Global composition \u2014 basic structure, color distribution, layout planning. Middle steps: Semantic emergence \u2014 objects become recognizable, shapes crystallize. Late steps: Detail refinement \u2014 textures, edges, fine patterns. The transitions are gradual, and the three zones are working coordinates, not verified boundaries: Choi et al. (2022) hypothesise a coarse / content / clean-up division, but they locate it by noise level, not by step number, and they measure it during training, not in a generation run. Particularly revealing: The very first step does not show fine-grained pixels, but colorful patches. This is because the noise is generated in latent space (128\u00d7128 at 16 channels), not in pixel space. The VAE translates each latent pixel into an ~8\u00d78 pixel patch \u2014 even pure Gaussian noise becomes coherent color clusters. The computation runs in this compressed space throughout, rather than on individual pixels.',
      techTitle: 'Technical details',
      techText: 'Two backbones run here: SD 3.5 Large, a rectified-flow transformer whose one scheduler is FlowMatchEuler, and SDXL, a U-Net whose scheduler is picked from a list. SD 3.5 additionally carries a shift, which spreads the steps over the noise scale; its own scheduler config sets that to 3.0. 25 steps are preset. At each step the current latent vectors are decoded through the VAE (Variational Autoencoder), which translates the mathematical latent space into pixels. The latent representation is 128×128 across 16 channels — each latent point corresponds to a patch of about 8×8 pixels in the image. This is why even the first step shows colour clusters instead of fine pixel noise: the VAE translates random 16-dimensional vectors into coherent colour fields. The view shows the noisy intermediate state decoded through the VAE, rather than the model\'s prediction of the finished image — Ho et al. (2020) show that prediction in their own figures.',
      referencesTitle: 'Research References',
      noteBody: 'An image generator builds a picture up out of noise, in steps. Choi et al. (2022) derive from their measurements that coarse features are settled at high noise, the content in the middle, details below the threshold of perception at the end. They measured it by noise level. As a place in the run, this division is a rough orientation. The two nets process the text differently. In SDXL\'s U-Net the image reaches into the text through cross-attention while the text stays as it is. In SD 3.5\'s MMDiT image and text parts run through the same attention mechanism with weights of their own and act on each other both ways (Esser et al. 2024).',
      promptLabel: 'Prompt',
      promptPlaceholder: 'e.g. the street where I live, in the morning, with an animal',
      generate: 'Generate',
      generating: 'Generating image \u2014 recording every step...',
      emptyHint: 'Enter a prompt and click Generate to visualize the denoising process.',
      denoisingGroup: 'Denoising',
      backboneLabel: 'Backbone (the net that removes the noise)',
      // The name of the axis, in the naming form: what its numbers count. It
      // is necessary, since it is what the numbers count and the slider's
      // accessible name. SUPPLIED WORDING: the German „Entrauschungsschritte";
      // the English is its counterpart.
      axisLabel: 'Denoising steps',
      secondEvaluation: 'second evaluation',
      advancedLabel: 'Advanced settings',
      negativeLabel: 'Negative Prompt',
      stepsLabel: 'Steps',
      cfgLabel: 'CFG',
      seedLabel: 'Seed',
      filmstripLabel: 'Denoising Filmstrip',
      timelineLabel: 'Step',
      phaseEarly: 'Composition',
      phaseMid: 'Semantics',
      phaseLate: 'Detail',
      phaseEarlyDesc: 'Global structure and color distribution emerge',
      phaseMidDesc: 'Objects and shapes become recognizable',
      phaseLateDesc: 'Textures and fine details are sharpened',
      finalImageLabel: 'Final image (full resolution)',
      timelineHint: 'Scrubs through denoising steps — shows how the image emerges from noise to final composition.',
      download: 'Download Image',
      // The error line under the prompt, when a frame of the run could not be
      // shown: which frame, and the cause as the part route or the browser
      // said it. Same shape as the compare surfaces' runFailed.
      frameFailed: '{frame} did not arrive: {m}'
    },
    textLab: {
      headerTitle: 'Transformers Lab \u2014 Scientific LLM Deconstruction',
      headerSubtitle: 'Representation Engineering, comparative model archaeology, and systematic bias analysis.',
      headerSubtitleDetail: 'Representation Engineering, comparative model archaeology, and systematic bias analysis: Three research-based tools for investigating language models.',
      explanationToggle: 'Show explanation',
      modelPanel: {
        // Over the chip row of Representation Engineering. It picks the model
        // that is read, and that is the word for it.
        presetLabel: 'Model',
        presetNone: 'No preset (custom ID)',
        customModelLabel: 'HuggingFace Model ID',
        customModelPlaceholder: 'e.g. meta-llama/Llama-3.2-1B',
        quantizationLabel: 'Quantization',
        quantAuto: 'Auto',
        quantizationHint: 'bf16 = full quality, int8 = half VRAM, int4 = minimal VRAM but lowest quality',
        wontFit: 'too large for this graphics card',
      },
      temperatureHint: 'Randomness of text generation. Low = deterministic, high = more creative.',
      maxTokensHint: 'Maximum number of generated tokens (word pieces).',
      textSeedHint: '-1 = random, fixed value = reproducible result',
      tokens: {
        runLabel: 'language',
        wordLabel: 'A single word to compare',
        tokenizerLabel: 'Tokenizer',
        offline: 'No tokenizer can be reached from here right now.',
        roles: {
          platform_text: 'The text model of this platform.',
          other_text: 'Another text model. It cuts differently.',
          multilingual: 'Trained on many languages at once.',
          image_text: 'The text reader of the picture models. Its window is only 77 tokens wide.',
        },
        cutHead: 'Your sentence, cut into tokens',
        cutEmpty: 'Write a sentence on the left.',
        countLine: '{n} tokens',
        vocabLine: 'Vocabulary: {n} tokens',
        windowLine: 'Window: {n} tokens',
        fill: '{p} % of the window',
        compareHead: 'The same sentence in the ten languages of this platform',
        compareEmpty: 'The comparison starts in the bar above. It translates your sentence into ten languages and cuts each version.',
        wordHead: '“{w}” in the same ten languages',
        note: 'A token is a piece of text. The tokenizer determines how a text is cut. It was built on certain languages.\nMore tokens means two things: the model\'s window fills up faster, and the computing time rises. That also means higher cost and higher energy use for the same work by the model.',
      },
      tabs: {
        repeng: { label: 'Representation Engineering', short: 'Find steering vectors in LLMs' },
        bias: { label: 'Bias Research 1', short: 'Uncover hidden biases in LLMs' },
        coref: { label: 'Bias Research 2', short: 'Pronoun reference versus stereotype' },
        tokens: { label: 'Tokenizer', short: 'Token cost by language' },
        systemprompt: { label: 'System Prompts' },
      },
      repeng: {
        referencesTitle: 'Research References',
        promptExamples: {
          capital: 'The capital of Germany is'
        },
        title: 'Representation Engineering',
        subtitle: 'Find concept directions in activation space and steer generation',
        explainWhatTitle: 'What does this experiment show?',
        // Help reads this one; no page renders it. Source of record for what
        // this instrument does (devserver/scripts/build_platform_items.py ->
        // knowledge/platform_items.json, field `what`).
        explainWhatText: 'Based on Zou et al. (2023), “Representation Engineering: A Top-Down Approach to AI Transparency” (arXiv:2310.01405). While a language model writes, what it is about to say stands as a state of numbers, layer by layer. This instrument reads a direction out of that state — from a handful of sentence pairs somebody writes themselves — and adds that direction back into the state while the model writes. Nothing is trained: the reading and the steering both happen while the model runs. The method is Zou et al.’s reading vector alone: one direction over the whole hidden state, added to the output of one decoder layer. Li et al.’s Inference-Time Intervention (NeurIPS 2023) works differently — a probe per attention head, and a shift only on the heads that separate — which is why it left this surface’s reference list on 2026-08-24.',
        explainHowTitle: 'How do I use it?',
        explainHowText: 'What happens to the contrast pairs, in four steps. (1) Each pair is read twice: the model is given the upper sentence, then the lower one, and its inner state at the middle layer of the stack is taken at the last token of each. What the pair contributes is the difference between those two states. (2) What the pairs’ differences have in common is the direction. The drawing under the pairs shows it: one grey arrow per pair at the angle its difference has to that shared direction, and one green arrow for the shared direction itself — the one that goes into the writing. A wide fan means the pairs differ in several things and the reading keeps only what they share. (3) The direction is scaled to the distance the pairs themselves travel along it, so the strength counts in pair-differences: 1 adds exactly as much as one pair differs on average, and 2 pushes the state further than any of those sentence pairs ever stands from its own partner — which is why the text begins to break up above 2. The axis starts at 1.5, which tips the answer on the first press. (4) While the model writes, strength × direction is added to the output of that decoder layer, at every token, and the three columns show it pushed one way, left alone, and pushed the other way. WHY UNTRUE SENTENCES COME OUT: the next word is computed from that state alone, and every assertion the model makes comes from where the state stands. Move the state and you move what follows from it; whether what follows happens to be true is decided by where the state now stands, which is where the pairs put it. The instrument shows an assertion as a position, and a position can be shifted. WHY THE MIDDLE COLUMN SHOWS NOTHING: zero times the direction is the zero vector, so nothing at all is added there. That column is the run the model would have produced on its own, and it stands as the reference the other two are read against. English prompts work markedly better: most open-weight models were trained mostly on English.',
        expectedResults: 'Expected results: in the “no arrow” column the model answers as it would on its own. In the two outer columns it answers from a state that was moved, and one of the two usually comes out untrue — which one depends on what the pairs have in common. With the three pairs that stand here by default it is the “with the arrow” column: pushed towards the upper sentences, the model answers the question about Germany with Paris.',
        expectedResultsDetail: 'One axis, straight under the drawing, and it holds a distance from 0.5 to 3 with no sign: both directions run at every press and stand as the two outer columns (“against the arrow”, “no arrow”, “with the arrow”). It starts at 1.5, which tips the answer on the first press. The strength counts in pair-differences, so 1 is one pair’s worth of push; 0.5 to 2 is the usable band, and above 2 repetition and nonsense take over. In the middle column nothing is added at all — that is the model left alone, and it is there to read the other two against. Each press adds a row to the grid on the right: three cells from one reading and one seed, so two cells side by side differ in the push and in nothing else. The row keeps the prompt it was started with, and says once how hard it pushed and which layer it used.',
        pairsTitle: 'Contrast Pairs',
        // The names of the ready-made sets. The SENTENCES in them are not here
        // and are never translated: they go to the model as they stand
        // (representation_engineering.vue, PAIR_SETS).
        pairSetLabel: 'Choose a set of pairs (or write your own)',
        pairSets: {
          facts: 'Facts and their plain opposites',
          orwell: 'Orwell, Nineteen Eighty-Four',
          postTruth: 'Post-truth: fact against assertion',
        },
        // SUPPLIED WORDING, verbatim. {d} is the one word the sentence leans
        // on; the page sets it in a brighter tone, which is what the asterisks
        // in the supplied wording asked for. It stays ONE key so a translator
        // sees the whole sentence.
        fanLabel: 'The {d} between the two prompts of every pair is itself a number, shown as a vector (arrow).',
        fanLabelEmph: 'difference',
        fanCommonA: 'this one',
        fanCommonB: 'acts on the model as it writes',
        fanSpread: 'Arrows wide apart: your pairs differ in more than one thing.',
        // SUPPLIED WORDING: the sentence names what acts and what it acts
        // on. It replaces 'How far the axis is pushed', where neither was
        // said. The axis holds a DISTANCE - the two directions are the two
        // outer columns of the grid.
        strengthLabel: 'How strongly the vector (arrow) acts on the AI model',
        // SUPPLIED WORDING: the four words, in the supplied order. Keep them
        // SHORT: the outer two sit centred on the ends of the axis and are
        // clipped if they grow.
        alphaMark05: 'barely',
        alphaMark1: 'medium',
        alphaMark2: 'strong',
        alphaMark3: 'extreme',
        // The heads of the three result columns. They name the DRAWING's
        // arrow, which is on the same screen; until 2026-08-25 they said
        // 'α +1.0' and wore the name the axis wears, so two different things
        // went by α at once.
        colWith: 'with the arrow',
        colNone: 'no arrow (reference)',
        colAgainst: 'against the arrow',
        // How hard, said once at the head of the row - all three cells share it.
        strengthShort: 'Strength',
        // The account of the mechanism that stands across the foot of the page.
        // It names its source, Zou et al. (2023), whose title stands under the
        // box. Struck from it: the strength scale, "that much of" before the
        // direction, the claim that all three columns come from one reading
        // and one seed, the closing inference, and "drawn in green".
        noteBody: 'A pair contributes the difference between the model’s states at its two sentences, and what the differences share is the direction (Zou et al. 2023). While the model writes, this platform adds a multiple of the direction to the middle layer’s output at every token.',
        // The platform's own wording for this drawer, copied verbatim.
        advancedLabel: 'Advanced settings',
        pairsSubtitle: 'Three pairs, and each should differ in one thing only (true vs. false).',
        pairsSubtitleDetail: 'Three pairs, editable, numbered, and each should differ in one thing. Three is also the ceiling: the button that adds one is gone at three. Once a run has been out, the pairs stand a second time as a drawing under the fields — one grey arrow per pair, each numbered, at the angle its difference has to the direction they share, and one green arrow for that shared direction, which is the one that goes into the writing. Arrows close together mean the pairs differ in the same thing; a wide fan means they differ in several, and the reading keeps only what they have in common. The arrangement is a PROJECTION and not a hand-drawn one: three differences stand at three angles to one another, and three rays from one point on a flat sheet have two free parameters, so a flat picture can hold two of the three angles at once. The plane drawn is the one the reading itself picks out — along the shared direction and across it — and the share of the spread that plane keeps comes back with every run. All arrows are drawn the same length, because a length here would say something about the drawing rather than about the pairs. The weights of the model stay as they are throughout: both the reading and the push happen while the model runs. Swapping a pair’s two sentences costs the measurement nothing — the direction is an eigenvector of a sum of outer products, and flipping one difference leaves its outer product as it was — it turns that one arrow around.',
        positiveLabel: 'Positive (true)',
        negativeLabel: 'Negative (false)',
        positivePlaceholder: 'e.g. The capital of France is Paris',
        negativePlaceholder: 'e.g. The capital of France is Berlin',
        addPair: 'Add pair',
        removePair: 'Remove',
        targetLayerLabel: 'Target layer',
        targetLayerHint: 'Which transformer layer receives the steering vector.',
        targetLayerHintDetail: 'The layer is fixed at the middle of the stack and has no control on the surface. Depth decides what the same push changes: early layers still hold the words themselves, the last ones already hold the next word, and the middle is where a claim stands as a claim — so the middle is the one setting that produces something legible, and the others are settings that waste a run. It is taken from whatever model is chosen, so it follows the depth of that model’s stack; each row of results reports the number it used. An axis for it stood on the surface until 2026-08-25 and was removed.',
        targetLayerAuto: 'Middle of the stack (recommended)',
        findDirection: 'Find direction',
        finding: 'Computing concept direction...',
        directionFound: 'Concept direction found',
        varianceLabel: 'Explained variance',
        dimLabel: 'Dimensions',
        projectionsTitle: 'Contrast pair projections',
        testTitle: 'Test + Manipulation',
        testSubtitle: 'Enter a sentence and steer generation along the concept direction',
        testPromptLabel: 'Test prompt',
        testPromptPlaceholder: 'e.g. The capital of Germany is',
        alphaLabel: 'Manipulation strength (\u03b1)',
        alphaHint: 'Strength of the steering vector. 0 = no effect, higher = stronger influence of contrast pairs.',
        temperatureLabel: 'Temperature',
        maxTokensLabel: 'Max tokens',
        seedLabel: 'Seed (-1 = random)',
        generateBtn: 'Generate with manipulation',
        generating: 'Running manipulated generation...',
        baselineLabel: 'Baseline (no manipulation)',
        manipulatedLabel: 'Manipulated (\u03b1 = {alpha})',
        projectionLabel: 'Projection onto concept direction',
        interpretationTitle: 'Interpretation',
        interpreting: 'Analyzing results...',
        interpretationError: 'Could not generate interpretation'
      },
      coref: {
        referencesTitle: 'Research References',
        legendCliche: 'the pronoun tips the answer — towards the cliché',
        legendNone: 'the pronoun changes nothing',
        legendAnti: 'the pronoun tips it — against the cliché',
        score: '{v} of {n} pairs',
        scoreNote: 'net towards the cliché',
        scrubLabel: 'Pair {i} of {n}',
        noteVetted: 'These are sentence pairs from bias research. The two sentences differ only in the pronoun, and the sentence structure fixes who the pronoun refers to, so the answer can be read off the sentence. Every run walks the same {shown} pairs. Which direction a change is called comes from the split by occupation in the WinoBias dataset, which rests on US labour statistics from 2017. The sentences come from WinoBias.',
        noteDrawn: 'These are sentence pairs from bias research. The two sentences differ only in the pronoun, and the sentence structure fixes who the pronoun refers to, so the answer can be read off the sentence. Every run draws a fresh {shown} pairs out of {pool}. Which direction a change is called comes from the split by occupation in the WinoBias dataset, which rests on US labour statistics from 2017. The sentences come from WinoBias.',
      },
      models: {
        label: 'Models',
        small: 'small models',
        smallNote: 'Gemma 2 2B, Llama 3.2 3B, Qwen3 1.7B and 4B',
        large: 'large models',
        largeNote: 'OLMo 3 7B, Nemotron Nano 9B, Qwen3.5 9B, Gemma 4 12B, Ministral 3 14B — 7 to 14B',
        family: 'model family',
        familyNote: 'the sizes of the Qwen family, 1.7B to 14B',
        history: 'model over time',
        historyNote: 'one family, one size, five generations: Qwen 7B (2023) to Qwen3 8B (2025)',
        failed: '{model}: {cause}',
      },
      bias: {
        referencesTitle: 'Research References',
        legendUnknown: 'holds the answer to be undecidable (correct)',
        legendStereotype: 'decides in line with the stereotype',
        legendOther: 'decides against the stereotype',
        score: 'bias score {v}',
        typical: '(typical: {m})',
        scrubLabel: 'Question {i} of {n}',
        noteBody: 'These are questions from bias research. All of these questions are undecidable, which is why “cannot be answered” is always the right answer. Every run draws a fresh random sample of {shown} out of the {total} open questions this category holds. So each time you get a genuinely new measurement. The questions come from the “Bias Benchmark for QA” dataset.'
      },
      error: {
        gpuUnreachable: 'GPU service unreachable. Is it running?',
        loadFailed: 'Failed to load model.',
        operationFailed: 'Operation failed.'
      }
    },
    crossmodal: {
      headerTitle: 'Crossmodal Lab',
      headerSubtitle: 'Sound from latent spaces: T5 embedding manipulation, image-guided audio generation, crossmodal transfer',
      explanationToggle: 'Show detailed explanation',
      generate: 'Generate',
      generating: 'Generating...',
      result: 'Result',
      seed: 'Seed',
      generationTime: 'Generation time',
      pictureShared: 'MMAudio and ImageBind Guidance work on the same picture, for as long as this window is open.',
      tabs: {
        synth: {
          label: 'Latent Audio Synth',
          short: 'T5 embedding manipulation',
          title: 'Latent Audio Synth',
          description: 'Direct manipulation of Stable Audio\'s T5 conditioning space (768d).',
          descriptionDetail: 'Direct manipulation of Stable Audio\'s T5 conditioning space (768d). Interpolate between prompts, extrapolate beyond the prompt, scale embeddings and inject noise. Ultra-short loops, near real-time.',
        },
        mmaudio: {
          label: 'MMAudio',
          short: 'Image/text to audio (CVPR 2025)',
          title: 'MMAudio — Video/Image to Audio',
          description: 'Image and text enter the same network as separate signals — the image is not translated into language, both guide sound generation simultaneously. The model was jointly trained on video and audio, learning direct associations between what is seen and what is heard. Up to 8s, 44.1kHz, ~1.2s compute time. (Cheng et al., CVPR 2025, doi:10.48550/arXiv.2412.15322)'
        },
        guidance: {
          label: 'ImageBind Guidance',
          short: 'Gradient-based image guidance',
          title: 'ImageBind Gradient Guidance',
          description: 'Gradient-based steering during the Stable Audio denoising process. ImageBind provides a shared 1024d space for image and audio — the gradient of the cosine similarity guides audio generation towards the image embedding.'
        }
      },
      synth: {
        invalidPresetFile: 'Invalid preset file',
        promptExamples: {
          wavesLabel: 'ocean waves / piano melody',
          wavesA: 'ocean waves',
          wavesB: 'piano melody'
        },
        explainWhatTitle: 'What does the Latent Audio Synth do?',
        explainWhatText: 'Stable Audio generates sound from text. The text is converted by a T5 encoder into a numerical vector with 768 dimensions \u2014 this vector is what you manipulate here. Instead of just changing \u201cwhat\u201d the model generates (via the prompt), you change \u201chow\u201d the model internally understands the text. Two prompts that sound similar can be far apart in this space \u2014 and vice versa.',
        explainHowTitle: 'How do I use this tool?',
        explainHowText: 'Enter text in Prompt A \u2014 this determines the base sound. Optional: Prompt B as a target point. The \u0391 slider controls the mix: at 0 you hear an equal blend of A and B, at \u22121 only A, at +1 only B. Magnitude scales the entire embedding \u2014 higher values produce more intense sounds. Noise injects randomness and creates unpredictable variations. Semantic Axes steer the embedding along learned directions (e.g. acoustic\u2194electronic, music\u2194noise) \u2014 each slider interpolates between two text poles in the T5 space. The Spectral Strip (below the Generate button) shows all 768 dimensions as bars. You can shift individual dimensions by clicking and dragging, directly manipulating the sound. Right-click resets a dimension.',
        promptA: 'Prompt A (Base)',
        promptAPlaceholder: 'e.g. ocean waves',
        promptB: 'Prompt B (Optional, for interpolation)',
        promptBPlaceholder: 'e.g. piano melody',
        alpha: '\u0391 (Interpolation between Prompt A embedding (= -1.0) and Prompt B embedding (= 1.0))',
        alphaHint: '0 = A only, 1 = B only, between = blend, >1 or <0 = extrapolation',
        magnitude: 'Magnitude (Scaling)',
        magnitudeHint: 'Global embedding scaling (1.0 = unchanged)',
        noise: 'Noise',
        noiseHint: 'Gaussian noise on embedding (0 = no noise)',
        duration: 'Duration (s)',
        steps: 'Steps',
        cfg: 'CFG',
        durationHint: 'Length of the generated clip.',
        durationHintDetail: 'Length of the generated clip. Below about eleven seconds this model produces malformed audio, so a short clip tells you more about that than about the prompt.',
        stepsHint: 'Denoising steps. This model is distilled for eight.',
        stepsHintDetail: 'Denoising steps. This model is distilled for eight — more is not better here, mostly just slower.',
        cfgHint: 'Classifier-Free Guidance.',
        cfgHintDetail: 'Classifier-Free Guidance. Guidance is trained into this model, so at 1.0 it is switched off entirely and the negative prompt has no effect at all.',
        seedHint: '-1 = random, fixed value = reproducible result',
        loop: 'Loop playback',
        engineLooper: 'Looper',
        engineWavetable: 'Wavetable',
        loopOff: 'One-shot',
        loopToggle: 'Loop',
        stop: 'Stop',
        looping: 'Looping',
        playing: 'Playing',
        stopped: 'Stopped',
        transpose: 'Transpose (semitones)',
        looperSection: 'Looper / Sequencer',
        midiSection: 'MIDI Control',
        midiUnsupported: 'Web MIDI is not supported by this browser.',
        midiInput: 'MIDI Input',
        midiNone: '(none)',
        midiMappings: 'CC Mappings',
        midiNoteC3: 'Note (C3 = Ref)',
        midiGenerate: 'Generate + Transpose',
        midiPitch: 'Pitch rel. C3',
        loopInterval: 'Loop interval',
        extractionRegion: 'Extraction region',
        loopOptimize: 'Auto-optimize',
        loopPingPong: 'Ping-pong',
        loopIntervalHint: 'Start/end of loop region — shorten end to trim Stable Audio fade-out',
        wavetableToggle: 'Wavetable',
        wavetableExtract: 'From Sample',
        wtReextract: 'Re-extract',
        wavetableSemantic: 'From Axis',
        wtSelectAxis: '— select axis —',
        wtBuild: 'Build',
        wtBuilding: 'Building...',
        wtBuildHint: 'Generates short samples along the axis to create a semantically ordered wavetable',
        sequencerToggle: 'Sequencer',
        oscillating: 'Oscillating',
        sequencing: 'Sequencing',
        arpeggiator: 'Arpeggiator',
        arpeggiatorPatterns: {
          up: 'Up',
          down: 'Down',
          updown: 'Up-Down',
          random: 'Random',
        },
        modeRate: 'Tempo (fast)',
        modePitch: 'Pitch (OLA)',
        wavetableScan: 'Scan Position',
        wavetableScanHint: 'Morph between frames (0 = start, 1 = end)',
        wtRange: 'Range',
        wtInterpolate: 'Interpolate',
        wtScanEnvelope: 'Scan',
        wtSweep: 'Sweep',
        wtReturn: 'Return',
        wavetableFrames: '{count} frames',
        midiScan: 'Scan Position',
        sequencer: {
          play: 'Play',
          stop: 'Stop',
          bpm: 'BPM',
          bpmHint: 'Tempo in beats per minute (16th-note steps)',
          preset: 'Preset',
          midiSync: 'MIDI Sync',
          gridHint: 'Slider = semitone offset, dot = active toggle, G = glide, bottom = velocity',
          glideTime: 'Glide',
          patterns: {
            eastcoast: 'Eastcoast',
            westcoast: 'Westcoast',
            synthwave: 'Synthwave',
            techno: 'Acid',
            ambient: 'Ambient',
            dub_techno: 'Dub Techno',
            idm_glitch: 'IDM / Glitch',
            solar: 'Solar',
            arpeggio_bass: 'Arpeggio Bass (32)',
            trance_gate: 'Trance Gate',
          },
        },
        adsrTitle: 'ADSR Envelope',
        adsrAttack: 'A',
        adsrDecay: 'D',
        adsrSustain: 'S',
        adsrRelease: 'R',
        adsrHint: 'Envelope for MIDI notes (Attack/Decay/Sustain/Release)',
        play: 'Play',
        normalize: 'Normalize loudness',
        peak: 'Peak',
        crossfade: 'Crossfade',
        transposeHint: 'Shifts pitch in semitones',
        crossfadeHint: 'Crossfade time at loop boundary (ms)',
        normalizeHint: 'Normalizes volume to maximum amplitude',
        testNote: 'Test C3',
        record: 'Record',
        stopRecording: 'Stop',
        saveRaw: 'Save raw',
        saveLoop: 'Save loop',
        filter: {
          title: 'Filter',
          cutoff: 'Cutoff',
          resonance: 'Resonance',
          mix: 'Mix',
          kbdTrack: 'Kbd Track',
          envelope: 'Filter Envelope',
          envAmount: 'Amount',
          lfoRate: 'Rate',
          lfoDepth: 'Depth',
          amplitude: 'Amplitude',
        },
        preset: {
          export: 'Export preset',
          import: 'Import preset',
        },
        controls: {
          time: 'Time',
          feedback: 'Feedback',
          damping: 'Damp',
          mix: 'Mix',
          bright: 'Bright',
          medium: 'Medium',
          dark: 'Dark',
          rate: 'Rate',
          depth: 'Depth',
          hold: 'Hold',
          gate: 'Gate',
          amount: 'Amt',
          free: 'Free',
          triggered: 'Trig',
          delay: 'Delay',
          reverb: 'Reverb',
        },
        embeddingStats: 'Embedding statistics',
        dimensions: {
          section: 'Dimension Explorer',
          hint: 'Drag on bars = set offset. Paint horizontally = multiple dimensions.',
          hintRelative: 'Drag up = toward Prompt A, drag down = toward Prompt B. Each bar mixes between the two prompts per dimension.',
          modeRelative: 'Relative',
          modeAbsolute: 'Absolute',
          resetAll: 'Reset all',
          hoverActivation: 'Activation',
          hoverOffset: 'Offset',
          hoverMix: 'Mix',
          rightClickReset: 'Right-click = reset',
          sortDiff: 'Sorted by prompt difference',
          sortMagnitude: 'Sorted by activation',
          activeOffsets: '{count} offsets active',
          applyAndGenerate: 'Apply and regenerate',
          undo: 'Undo',
          redo: 'Redo'
        },
        semanticAxes: {
          modeToggle: 'Semantic Axes',
          info: 'Semantic axes steer the prompt embedding in specific directions. Each slider interpolates between two text poles in T5 space. More active axes = weaker per-axis effect. Recommended: 1\u20133 axes.',
          slotNone: '\u2014 none \u2014',
          groupSemantic: 'Semantic (text poles)',
          groupPCA: 'PCA (data-driven)',
          resetAll: 'Reset all to center',
          experimental: 'experimental'
        }
      },
      mmaudio: {
        promptExamples: {
          campfire: 'crackling campfire'
        },
        explainWhatTitle: 'What does MMAudio do?',
        explainWhatText: 'MMAudio (Cheng et al., CVPR 2025) was jointly trained on video and audio. It doesn\'t translate an image into text and then into sound, but processes image and text as parallel signals in the same network. The model learned which sounds belong to which visual scenes \u2014 a forest produces birdsong, a street produces traffic noise, a guitar produces plucking sounds.',
        explainHowTitle: 'How do I use this tool?',
        explainHowText: 'Upload an image and/or enter a text prompt \u2014 using both together yields the richest results. The image alone generates sounds matching the visual content. The text prompt can additionally steer the sound or be used alone without an image. In the Negative Prompt, describe sounds you do NOT want to hear (e.g. \u201cspeech, music\u201d). Duration sets the length (1\u20138 seconds). CFG Strength controls how strictly the model follows the prompt \u2014 low values (2\u20133) produce more varied results, higher values (6\u20138) are more prompt-faithful.',
        imageUpload: 'Upload image (optional)',
        prompt: 'Text prompt (optional)',
        promptPlaceholder: 'e.g. crackling campfire',
        negativePrompt: 'Negative prompt',
        duration: 'Duration (s)',
        maxDuration: 'Max 8s (model limit)',
        cfg: 'CFG',
        steps: 'Steps',
        compareHint: 'Compare: Text only vs. Image + Text',
        advancedLabel: 'Advanced settings',
        referencesTitle: 'Research References'
      },
      guidance: {
        promptExamples: {
          ambient: 'ambient soundscape'
        },
        explainWhatTitle: 'What does ImageBind Guidance do?',
        explainWhatText: 'ImageBind (Girdhar et al., CVPR 2023) brings six senses \u2014 image, sound, text, depth, heat, motion \u2014 into a shared \u201clanguage\u201d. This tool uses that common ground: as the sound is generated step by step, it constantly asks \u201cDoes this sound like the image yet?\u201d and corrects the direction. The cosine similarity in the result shows how close the generated sound came to the image content.',
        explainHowTitle: 'How do I use this tool?',
        explainHowText: 'Upload an image. That image is the target direction for the sound. A text prompt is optional and steers in addition. The guidance-strength slider decides how far the image pulls: measured on the finished clip, below 1 the effect stays inside the noise, around 5 the sound moves clearly towards the image, and above 20 the latent breaks down and the similarity falls again. The guided-steps slider says how many of the denoising steps the gradient acts on. This sampler mixes fresh noise into every step, so guidance given to the first steps only is overwritten before the clip is finished. Total steps and duration control quality and length.',
        referencesTitle: 'Research References',
        imageUpload: 'Upload image',
        prompt: 'Base prompt (optional)',
        promptPlaceholder: 'e.g. ambient soundscape',
        lambda: 'Guidance strength',
        lambdaHint: 'How far the image pulls. Below 1 nothing measurable happens, around 5 is the useful range, above 20 the sound falls apart.',
        warmupSteps: 'Guided steps',
        warmupHint: 'How many of the denoising steps the image gradient acts on. Fewer than all leaves the last steps unguided, and they overwrite the guidance.',
        totalSteps: 'Total steps',
        duration: 'Duration (s)',
        cfg: 'CFG',
        totalStepsHint: 'Total denoising steps. More = higher quality.',
        durationHint: 'Length of the generated audio clip in seconds',
        cosineSimilarity: 'Cosine similarity (image-audio proximity)',
        imageTypeTitle: 'Which images work best?',
        imageTypeText: 'ImageBind was trained on AudioSet (2M web-video clips, 527 sound categories). Images with clear audio associations produce the strongest guidance: animals (birds, dogs, cats), nature (ocean waves, rain, waterfall, forest), musical instruments, vehicles (cars, planes, trains). Images without inherent sound — portraits, architecture, abstract art, still-lifes — produce weak or inconsistent results. For best results: choose an image where a specific sound immediately comes to mind.',
        firstRunNotice: 'First generation after a service restart may take 2–3 minutes while GPU kernels compile. Subsequent runs are fast.',
        advancedLabel: 'Advanced settings',
        lambdaOffLabel: 'no pull',
        lambdaUsefulLabel: 'useful range',
        warmupAllLabel: 'every step'
      }
    }
  },
  corefTest: {
    story:
      'When an AI model carries prejudices, that can become unpleasant or even dangerous, because it often makes decisions, or prepares them - for example AI that the police use. On this page you can find out for yourselves whether language models pass prejudices on. The English sentences are built so that what the personal or relative pronoun (he/she/it, his/her/its) refers to is *unambiguous*.',
    purpose: 'Language models nevertheless often read it wrongly internally: although they handle the grammar of simple sentences very well, the biases and clichés trained into them make them change the referent when the pronoun changes grammatical gender.',
  },
  biasArchaeology: {
    story:
      'When an AI model carries prejudices, that can become unpleasant or even dangerous, because it often makes decisions, or prepares them - for example AI that the police use. On this page you can find out for yourselves whether language models pass prejudices on.',
    purpose:
      'None of the questions in the left column can be decided, which is why "not answerable" is always the right answer. The language models nevertheless pick one of the other answers sometimes. Find out whether they then lean towards the answer that matches the prejudice, or towards the other one. The more a language model decides for the prejudice, the higher its "bias score" under the graph climbs. The questions come from the "Bias Benchmark for QA dataset" (Parrish et al., Findings of ACL 2022; data CC BY 4.0 from github.com/nyu-mll/BBQ). Every run draws a fresh random selection of 60 from up to 7,980 open questions per category.',
  },

  // The title of the handle that folds the preparing column away. It stands
  // on every instrument with one preparing column and two or three result
  // columns, so the two words are the platform's and not one surface's.
  columnFold: {
    hide: 'Hide column',
    show: 'Show column',
  },

  compare: {
    // The sign Help holds up on the comparison surfaces once something stands
    // there. SUPPLIED WORDING: the German „Interpretationshilfe". It carries
    // no question: taking it opens the conversation, nothing is written into
    // it.
    ask: {
      sign: 'Interpretation help',
      note: 'This help can support you with the comparative analysis of the results. Just ask it about them.',
    },
    // What a single comparison says about itself, where the shared text above
    // says it for all four at once; the shared words are not fitted to the
    // instruments. One block per instrument, added as each one is written.
    // Recast without an address: the address is the exception, so the
    // constative second person became the impersonal naming of the process;
    // attention imperatives stay (Language Understanding, Image
    // Understanding, Voice Comparison). The supplied sentences of
    // model.purpose (SUPPLIED WORDING, named in de.ts) stay word for word.
    address: {
      model: {
        story: 'Two sets of three stand to choose from: three of today\'s AI models, or the same family three years apart, 2022, 2023 and 2024. All three compute with the same prompt and the same seed. To the prompt, the platform also searches for real photographs on Wikimedia Commons.',
        purpose: 'What separates the pictures lies in the differences between the AI models: those you can explore yourselves. A thing named in the prompt sometimes stands clearly in one column, barely in the next, and is missing in the third. Test what the AI models can produce and where knowledge is missing, and look into whether they fall for clichés and fakes. The photographs are the counter-horizon to that: real pictures somebody took.',
      },
      'vlm-analysis': {
        story: 'The page takes in a picture — uploaded or drawn here — and offers six perspectives underneath: two descriptions, an art-historical one, an educational-theory one, an ethical one, a critical one. The page enters the chosen perspective into the field below as an instruction. Several vision models carry out the instruction; all of them get the same picture.',
        purpose: 'This is not here to take the work of interpreting a picture off anyone\'s hands: the machine\'s interpretations are themselves the matter. The columns show how a text AI “sees” pictures and how it produces an image interpretation from them. Machine image analysis decides about people: diagnoses, arrests and refusals at a border follow from it — people have been arrested because a system matched their face to a picture, and those affected rarely get to see the analysis itself. It appears as a finding; here several readings of the same picture stand side by side. Follow what a model names first, what it holds on to, and at which point it moves from what is to be seen to what it is supposed to mean. The same lines are sometimes called order and structure in one column, and home, shelter and identity in the next.',
      },
      language: {
        story: 'Every column holds the same description of a picture, each one in a different language. Two to four languages stand to choose from: the platform\'s ten and ten further ones, among them Upper Sorbian, Yorùbá and Runasimi. Every ticked image model makes a picture from it in every column, one row per model; within a row, all the pictures are made with the same seed (Gemini runs behind Google\'s interface, and that interface takes no starting number). Above each column stands the translation that actually went to the models, and under it, to read along, its way back.',
        purpose: 'Compare what becomes of the same prompt as soon as a model processes it in another language. The way back above each column is the check on that: most of the time the way back is the prompt as entered, so the translation holds, and the pictures still often differ widely. The text parts of SD 3.5 are trained on English text; a prompt in another language they process so little that the language itself settles the picture and the content steps behind it. The picture then shows the cliché: whatever stood most often beside that language in the training data. The other image models read the prompt through text parts of their own, named in the box beneath the image models.',
      },
      voice: {
        // The sentence is picked from a drop-down beside a free input field,
        // so nothing "comes from a list"; a voice stages gender, it does not
        // produce it (see about.title).
        story: 'The test sentence is picked from the drop-down or written in the field; the drop-down holds everyday sentences with and without an emotional colouring, and fairy tales. Four text-to-speech systems speak it, each with settings and a start button of its own: a formant synthesis from 1995 in twelve variants; voice files, each trained on a recording, of which one is picked; ten trained voices that can be picked singly and mixed; and a model whose speaker three rows describe — gender, age, expression. Every system keeps what it spoke.',
        purpose: 'A voice stages gender and feeling; the four systems do it with completely different means. In the machine from 1995 there is a recording of nobody; there it is twelve settings of a computing rule, and it still often sounds like somebody. In the second, one file per voice speaks, each trained on a recording, and under the chosen file stands who was recorded, where the dataset says so. In the third system each of the ten voices carries its pitch in hertz beside it: compare the ones marked F and the ones marked M. The fourth takes in a description from three rows instead of a list — gender, age, expression —; compare the setting with what there is to hear.',
      },
      systemprompt: {
        story: 'The model answers a message three times, in every column under a system prompt of its own. Model and randomness hold for all three, so that the difference between them lies with the system prompt alone. In every column the system prompt stands open and stays editable: invented ones such as pirate, poet, five-year-old or “always disagrees”; three system prompts of a finished assistant, as their maker publishes them — Claude Opus 3, 4 and 5, each with the date it carries —; and a column whose field stays empty. The conversation goes on in all three.',
        purpose: 'A system prompt is the instruction that stands before every conversation with an assistant and stays hidden while it does. Here it stands, and beside it, what it brings about. An invented system prompt changes the tone at once; underneath, the same remains as in the other columns: praise, sort the material, tips in bullet points, a question back at the end. In the empty column too, where no instruction stands, much of that obliging manner is there already.',
      },
    },
    story: 'This is about exploring AI critically by direct comparison: different image models side by side; what one image model makes of the same prompt in different languages, in cultural references, identities and traditions; chatbots with different text models and system prompts; how AI speech synthesis simulates emotions, moods and gender roles.',
    purpose: 'Two things can be learned here: to set aesthetic AI products side by side and analyse them in direct comparison, and through that to understand what marks the individual models and what they will produce. And to experience AI not as monolithic but as heterogeneous and biased — with characteristic traits and characteristic limits at once.',
    tabs: {
      model: 'Model Comparison',
      language: 'Language Understanding',
      census: 'Stereotype Analysis',
      'vlm-analysis': 'Image Understanding',
      // Read by nobody: no view names `llm-model`, and its string duplicates
      // the live `model` above. It stands with the three below, on the same
      // grounds.
      'llm-model': 'Model Comparison',
      // Read by nobody since 2026-08-22: System Prompts is a Latent Text Lab
      // instrument now and takes its label from latentLab.textLab.tabs, and
      // Randomness was taken apart. Left standing because they are names in ten
      // languages; deleting them is a separate decision.
      systemprompt: 'System Prompts',
      temperature: 'Randomness',
      // Read by nobody since 2026-08-23: the surface this named was removed.
      // Left standing with the two above it, on the same grounds.
      control: 'Guidance and Temperature',
      voice: 'Voice Comparison',
    },
    // Was the surface that varied the temperature over a row of text and the
    // guidance scale over a row of pictures, with the seed held still; it was
    // removed on 2026-08-23. `drawAgain` and `seedLabel` say what they say in
    // ten languages and are read again since 2026-08-24 by Representation
    // Engineering, which grows the same way, a row per press.
    control: {
      drawAgain: 'Another draw',
      seedLabel: 'Seed',
      cfgValue: 'CFG {v}',
      cellFailed: 'Nothing came back.',
      runFailed: 'A picture did not arrive: {m}',
      otherGenerator: 'From a different generator. Not comparable with the other cells.',
    },
    shared: {
      temperatureValue: 'T = {v}',
      sendAll: 'Send to All',
      sending: 'Sending...',
      newConversation: 'New conversation',
      noResponse: 'No response received',
      error: 'Connection error',
      modelLabel: 'Model',
      defaultModel: 'Default (Settings)',
      modelNotDownloaded: '(not downloaded)',
      install: {
        downloadCta: 'Download ({mb} MB)',
        starting: 'Starting download...',
        downloading: 'Downloading model',
        done: 'Download complete',
        failed: 'Download failed',
        dismiss: 'Dismiss',
        etaSeconds: '~{s}s left',
        etaMinutes: '~{m} min left',
      },
    },
    voice: {
      sentences: {
        label: 'Choose Test Sentence (or write one yourself)',
        axis: {
          neutral: 'Everyday sentences without emotional bias.',
          emotional: 'Everyday sentences with emotional bias.',
        },
        after: 'After {source}',
        tale: 'Fairy tale: {title}',
      },
      speak: 'Generate audio',
      speaking: 'Speaking\u2026',
      failed: 'The voice did not answer ({status}).',
      unreachable: 'No connection to the voice.',
      unavailable: 'No voice is available on this server right now.',
      unavailableWith: 'No voice is available right now: {reason}',
      systems: {
        supertonic: 'Supertonic',
        voxcpm: 'VoxCPM2',
        espeak: 'eSpeak NG',
        piper: 'Piper',
      },
      supertonic: {
        voiceLabel: 'Voice/Speaker model',
        // Above the chips, saying that voices can be mixed: an imperative,
        // and the present tense as its consequence. The doer is the platform:
        // `weightsFor` in
        // voice_comparison.vue sends 1/n per chosen voice, and
        // supertonic_backend.py (`parse_mix`, `_build_style`) sums the
        // model's style vectors with those weights.
        mixNote: 'Choose several voices; the platform mixes them in equal shares.',
        presets: {
          F1: 'calm, a little lower, composed',
          F2: 'bright, lively, youthful',
          F3: 'clear, like an announcer',
          F4: 'clipped, decided, expressive',
          F5: 'friendly, gentle, soothing',
          M1: 'lively, alert, clear',
          M2: 'low, calm, serious',
          M3: 'polished, assured',
          M4: 'soft, neutrally coloured, youthful',
          M5: 'warm, quiet, telling a story',
        },
      },
      kind: {
        espeak: 'eSpeak NG 1.51.1 (from "speak", Jonathan Duddington, 1995) - the computer voice from before AI. Formant synthesis: rules turn the letters into phonemes, and every phoneme is played as a few resonances. No recording of anybody is in it, which is why it fits into a few megabytes and speaks over a hundred languages.',
        supertonic: 'Supertonic 3 (Supertone, 2026), about 99M parameters, non-autoregressive (a passage is formed in one pass, no piece waiting on the one before; longer input is cut at sentence boundaries into passages of at most 300 characters and each is spoken on its own): a flow-matching decoder over a speech autoencoder. Ten voices are trained as vectors into the model. They can be mixed by simple addition and normalization, e.g. v = (v(F1) + v(F3) + v(M4)) / 3.',
        voxcpm: 'VoxCPM2 (OpenBMB, 2026), 2B parameters, tokenizer-free and diffusion-autoregressive (each piece is denoised into place, and what stands there conditions the next): the prompt is read as language rather than as settings. The expression is described in words within the prompt (there are no technical parameters to manipulate emotional expression in this model).',
        piper: 'Piper 1.6.0 (Michael Hansen, Rhasspy project, 2022; the installed 1.6.0 is from the Home Assistant authors, 2026), VITS (Kim et al., 2021), non-autoregressive (each sentence is formed in one pass, no piece waiting on the one before; longer input is cut at sentence boundaries and each sentence is spoken on its own): every voice is one model file, trained on a recorded dataset, for most of the installed voices by fine-tuning an English base voice (each voice’s MODEL_CARD says which). What can be chosen is which voice model speaks. The speaker heard is the recorded one; pitch and rhythm are sampled anew at every run, which VITS was built for: "a text input can be spoken in multiple ways with different pitches and rhythms" (Kim et al., 2021, abstract).',
      },
      about: {
        title: 'Four text-to-speech systems compared, with an eye to how they stage emotion and gender',
        // SUPPLIED WORDING: paragraphs 1, 3 and 4; paragraph 2 on Piper came
        // later and is not supplied wording. The sentences at the end of
        // paragraph 2, after its bracket, carry the speaker information: the
        // corpus voice's 236 speakers (num_speakers in the sidecar), one per
        // run (piper_backend.py, resolve_speaker), and what the drop-down's
        // entries carry (`piper.gender`, `piper.recorded`, from the corpus's
        // metainfo). "volunteers who recorded public-domain books":
        // librivox.org/pages/about-librivox, read 2026-09-19:
        // "LibriVox volunteers record chapters of books in the public domain".
        // "Speaker" is the rubric `piper.speakerLabel`, quoted straight like
        // "speak" in paragraph 1.
        body: '1) eSpeak NG 1.51.1 (1995): the computer voice from before AI. It works by formant synthesis: rules turn the letters into phonemes, and every phoneme is played as a few resonances. Cf. "speak", Jonathan Duddington, 1995.\n\n2) Piper 1.6.0 (2022): parallel (VITS, 2021: the model forms each sentence in one pass and samples pitch and rhythm anew at every run). Every voice is one model file, trained on a recorded dataset, for most of the installed voices by fine-tuning an English base voice. What can be chosen is which voice model speaks, and the speaker heard is the recorded one. (Michael Hansen, Rhasspy project, 2022; the installed 1.6.0 from the Home Assistant authors, 2026) In the German voice "mls", 236 speakers are trained into one model file. Piper speaks with one of them per run. They are volunteers who recorded public-domain books for LibriVox. The research corpus Multilingual LibriSpeech holds their recordings. Under "Speaker", the drop-down names each of them by their number in the corpus, with their index in the file in brackets, and adds gender and the amount recorded as the corpus documents them.\n\n3) Supertonic 3 (2026): 99 million parameters; non-autoregressive (a passage is formed in one pass). A flow-matching decoder over a speech autoencoder. Ten voices are trained as vectors into the model. They can be mixed by simple addition and normalization, e.g. v = (v(F1) + v(F3) + v(M4)) / 3. (Supertone, 2026)\n\n4) VoxCPM2 (2026): 2 billion parameters; diffusion-autoregressive (each piece is denoised into place and conditions how the one after it is read, across sentence boundaries too). No parameters; the whole input is read as language, directions about the voice are embedded in the prompt and are understood. (OpenBMB, 2026)',
      },
      voxcpm: {
        genderLabel: 'Gender',
        ageLabel: 'Age',
        emotionLabel: 'Expression',
        gender: {
          female: 'female',
          male: 'male',
          neutral: 'neutral',
        },
        age: {
          child: 'a child',
          young: 'young',
          middle: 'middle-aged',
          old: 'old',
        },
        emotions: {
          neutral: 'neutral',
          angry: 'angry',
          happy: 'happy',
          sad: 'sad',
          anxious: 'anxious',
          bored: 'bored',
          disgusted: 'disgusted',
          calm: 'calm',
          friendly: 'friendly',
          gentle: 'gentle',
          decided: 'decided',
          narrating: 'narrating',
        },
        label: 'Change or add to the voice',
      },
      espeak: {
        voiceLabel: 'Voice/Speaker model',
        selected: 'Selected model',
        engineMeta: 'eSpeak NG {version}, {hz} Hz',
        missing: 'eSpeak NG is not installed on this machine.',
      },
      piper: {
        // The three rubrics of the choice, as Piper's own sample page names
        // its selects: Language, Voice, Speaker (its fourth, Quality,
        // stands on the voice chip's hover card).
        // rhasspy.github.io/piper-samples, read 2026-09-19. The voices are
        // chosen as the products that embed Piper choose them.
        languageLabel: 'Language',
        voiceLabel: 'Voice',
        // The hover card of a voice chip: the file behind the dataset's name,
        // and the quality level from the sidecar's `audio.quality`. Piper's
        // sample page names four ("Voices are trained at one of 4 'quality'
        // levels", rhasspy.github.io/piper-samples, read 2026-09-19); the
        // fifteen installed files carry three of them, low, medium and high.
        voiceTitle: 'File {file}, Piper quality level "{quality}"',
        noneInstalled: 'No Piper voice is installed.',
        // Under the choice stands one line, `recordings.<dataset>`. The
        // file's name again, its export version, sample rate and quality
        // level, its speaker count and what a file of another language does
        // with the sentence do not stand there: that line was too long for
        // the UI, and the speaker information stands in the note box instead.
        // Which speaker of the German corpus voice speaks is chosen in the
        // drop-down under the voices and goes to the API under `emotion`.
        speakerLabel: 'Speaker',
        // The drop-down's entries read "2422 (0) · male · 601 h": the speaker
        // as the sample page names it (name, index), then what the corpus's
        // own metainfo documents where it lies beside the model
        // (download_piper.sh; piper_backend.py, `speaker_info`): gender as
        // the corpus records it, in the column GENDER as F or M, and the
        // minutes recorded, summed per speaker. `recorded` is that sum in
        // the unit it is read in: of the 236 speakers of `de_DE-mls-medium`,
        // 78 entries read in hours, 153 in minutes and 5 in seconds. What the
        // two are is said in the page's note box (`about.body`).
        gender: {
          F: 'female',
          M: 'male',
        },
        recorded: {
          h: '{n} h',
          min: '{n} min',
          s: '{n} s',
        },
        // What the dataset behind a voice says about who was recorded, in the
        // source's wording, keyed by the dataset the voice file names in its
        // sidecar (`dataset`). A dataset that says nothing has no entry, and
        // absent means "not documented", never "amateur". Moved here from
        // a map in services/piper_backend.py on 2026-09-18, so the line is
        // translated like every other line of the column.
        recordings: {
          // PAVOQUE project page, DFKI (mary.dfki.de/pavoque): "Stefan Röttig, a
          // male native speaker of German trained as a professional actor and
          // baritone opera singer".
          pavoque: 'Stefan Röttig, trained actor and baritone, recorded for PAVOQUE, a project of the research institute DFKI',
          // Multilingual LibriSpeech (openslr 94): a research corpus of
          // LibriVox readers, 236 speakers in the German model.
          mls: '236 LibriVox volunteers (Multilingual LibriSpeech)',
          // CSTR, Blizzard Challenge 2013: audiobooks "generously provided by
          // The Voice Factory and Lessac Technologies", voice talent Catherine
          // Byers.
          lessac: 'Catherine Byers, audiobook narration, provided to the Blizzard Challenge by The Voice Factory and Lessac Technologies',
          // Edinburgh DataShare, SIWIS French Speech Synthesis Database: "The
          // data was recorded by a French voice talent".
          siwis: 'recorded by a French voice talent (SIWIS, Edinburgh DataShare)',
          // SASPEECH, openslr 134: about 30 hours "spoken by Shaul Amsterdamski
          // in a recording studio", from the Hayot Kis podcast; released with
          // the consent of the speaker and the Israeli Public Broadcasting
          // Corporation.
          saspeech: 'Shaul Amsterdamski, recorded in a studio for the Hayot Kis podcast, Israeli Public Broadcasting Corporation',
          // KSS, Korean Single Speaker Speech Dataset: "audio files recorded by
          // a professional female voice actress".
          kss: 'recorded by a professional female voice actress (KSS)',
        },
      },
      gap: {
        english: '{system} has no voice for {language}. It translates your sentence into English and speaks the English.',
        refuses: '{system} has no voice installed for {language} and refuses rather than answer in another language. What is missing here is a download, not a limit of the model.',
      },
      trio: {
        waiting: 'waiting\u2026',
        substituted: 'No voice for {asked}. Translated into {spoken} first, then spoken.',
      },
      samples: {
        title: 'Results',
        platformOrigin: 'Platform voice: {name}',
        meta: '{steps} steps \u00b7 seed {seed}',
      },
      languages: {
        ar: 'Arabic',
        bg: 'Bulgarian',
        de: 'German',
        en: 'English',
        es: 'Spanish',
        fr: 'French',
        he: 'Hebrew',
        ko: 'Korean',
        tr: 'Turkish',
        uk: 'Ukrainian',
      },
    },
    temperature: {
      inputLabel: 'Your Message',
      inputPlaceholder: 'Type a message to send at all three temperatures...',
      cold: 'Deterministic',
      warm: 'Balanced',
      hot: 'Unpredictable',
      subtitle: 'See how randomness changes what the AI says',
    },
    systemprompt: {
      inputLabel: 'Your Message',
      inputPlaceholder: 'Type a message to send with all three system prompts...',
      subtitle: 'See how invisible instructions control AI behavior',
      presetLabel: 'Preset',
      // Under the field of a published prompt, linking to where it stands.
      publishedOn: 'Published {date}',
      // The ONE temperature all three columns run at.
      temperatureLabel: 'Randomness',
      promptLabel: 'System Prompt',
      emptyPrompt: '(no system prompt)',
      custom: 'Custom',
      presets: {
        none: 'No system prompt',
        claude_opus_3: 'Claude Opus 3 (2024)',
        claude_opus_4: 'Claude Opus 4 (2025)',
        claude_opus_5: 'Claude Opus 5 (2026)',
        helpful: 'Helpful assistant',
        disagree: 'Always disagree',
        pirate: 'Pirate',
        poet: 'Poet',
        fiveyearold: 'Five-year-old',
        factsonly: 'Only facts',
      },
    },
    llmModel: {
      inputLabel: 'Your Message',
      inputPlaceholder: 'Type a message to send to all three models...',
      systemPromptLabel: 'SYSTEM PROMPT',
    },
    // Read from two places: the Image Understanding surface, and the reading
    // frames /x2x-flow offers for a made picture. That second reader is why the
    // frame names stayed here while the surface was away, 2026-08-23 to -08-26.
    vlmAnalysis: {
      perspectiveLabel: 'Perspective',
      modelsLabel: 'Vision Models',
      noModelsInstalled: 'No vision models installed locally.',
      analyzeBtn: 'Analyze Image',
      analyzing: 'Analyzing...',
      waiting: 'waiting',
      readingBrokeOff: 'The connection broke off while the model was still writing.',
      readingHitCeiling: 'The model ran out of context here — the reading breaks off mid-thought.',
      readingLooped: 'The reading was stopped here: the model kept writing the same passage again. Repetition feeds itself — the more often a sentence already stands in the text, the more likely the model is to write it once more (self-reinforcement, Xu et al., NeurIPS 2022). A reading frame with fixed steps and recurring questions offers such sentences readily, and the sampling here carries no penalty on repetition, so nothing pulls the model back out. What decides is less the size of the model than how firmly it holds the task against the text it has just written itself — this says nothing about the picture.',
      readingIncomplete: 'Part of the reading was lost on the way here.',
      freePromptPlaceholder: 'Write your own analysis prompt...',
      perspectives: {
        free: 'Free (your own prompt)',
        neutral: 'Neutral description',
        descriptive: 'Detailed description',
        bildwissenschaftlich: 'Art-historical',
        bildungstheoretisch: 'Educational theory',
        ethisch: 'Ethical analysis',
        kritisch: 'Critical reading',
      },
    },
    promptLabel: 'Prompt',
    promptPlaceholder: 'e.g. the street where I live, in the morning, with an animal',
    // The note at the foot of the preparing column on Model Comparison. One
    // text per set of three, so what stands there is about the three models
    // that are actually running. Every figure, licence name and card sentence
    // comes from the maker's own publication; the titles are listed under the
    // note. No sentence about the surface itself — the page address carries
    // that: pageAddress.compare.model.
    // Over the two chip rows of Model Comparison: the sets above the prompt
    // field, the models themselves under it. Stereotype Analysis reads
    // the same two names over its own model row since 2026-09-09.
    setsLabel: 'Sets',
    // The names of the two ready sets, side by side under the prompt field.
    // SUPPLIED WORDING: the two names.
    presets: {
      history: 'SD History',
      current: 'Current models',
    },
    modelsLabel: 'Models',
    modelNote: {
      noteBody: {
        history: 'SD 1.5 works in a compressed representation of the picture. Its paper states the aim of making training possible on limited computing resources, against the hundreds of GPU days a model working directly on pixels often costs.\n\nSDXL was built for high-resolution image synthesis: an image network three times larger, a second text encoder, several aspect ratios, and the claim in its own paper to reach the closed image generators of 2023. The paper on the architecture of SD 3.5 names: “improving text comprehension, typography, and human preference ratings”. Typography is the writing inside the picture.',
        current: 'SD 3.5 Large was built to follow the prompt closely and to put legible writing in the picture (Stability AI 2024, model card and release page). Flux 2 was built to keep the same character, product or style across up to ten reference pictures at once. Its release claims: “Complex typography, infographics, memes and UI mockups with legible fine text now work reliably in production.”\n\nGemini 3 Pro Image, which Google calls “Nano Banana Pro”, is built on Google\'s model Gemini 3 Pro. According to Google, Gemini 3 Pro Image can draw on a Google Search query for a picture, so a weather graphic can carry current information. Google states legible text inside the picture in several languages.',
      },
      referencesTitle: 'Sources',
    },
    // The note box of Language Understanding, since 2026-09-21 a raster with
    // the models as rows: one paragraph per model that is on, saying through
    // which text parts that model reads the sentence, in the maker's words.
    // Keyed by output config, read by `views/compare/language_comparison.vue`.
    languageNote: {
      noteBody: {
        sd35_large: 'SD 3.5 Large reads the prompt through three text encoders: CLIP-L and CLIP-G, trained on pairs of pictures and captions (Radford et al. 2021; Cherti et al. 2023), and T5-XXL, trained on text alone (Raffel et al. 2020). Stability AI\'s paper on the architecture (Esser et al. 2024) reports the design as “improving text comprehension, typography, and human preference ratings”. In the paper\'s evaluation, typography is how accurately the picture shows written text.',
        sd35_large_turbo: 'SD 3.5 Large Turbo reads the prompt through the same three text encoders as SD 3.5 Large, CLIP-L, CLIP-G and T5-XXL (Stability AI 2024, model card). What Stability AI wanted from Turbo stands in the release: “A distilled version of Stable Diffusion 3.5 Large generates high-quality images with exceptional prompt adherence in just 4 steps” (Stability AI 2024, release page).',
        flux2: 'Flux 2 reads the prompt through the language model of a vision-language model (VLM). Black Forest Labs states what the VLM adds: “The VLM brings real world knowledge and contextual understanding” (Black Forest Labs 2025).',
        gemini_3_pro_image: 'Gemini 3 Pro Image is Google\'s image model “Nano Banana Pro”. Google states: “Built on Gemini 3 Pro, Nano Banana Pro uses Gemini\'s state-of-the-art reasoning and real-world knowledge to visualize information better than ever before.” (Google 2025).',
      },
      referencesTitle: 'Sources',
    },
    // The line under the fields when a translation did not come back: the
    // language it was for and the cause the route gave (Language Understanding).
    translationFailed: 'Translation into {lang} failed: {cause}',
    // The found-pictures row under the model grid (Model Comparison). The
    // archive is named in as many words — never "an open archive": which
    // archive it is, is part of what the row says.
    found: {
      title: 'Results for this prompt',
      source: 'Wikimedia Commons',
      searchTerm: 'Search term',
      loading: 'Looking for pictures that already exist…',
      horizon: 'These images were found on Wikimedia Commons with the search term above. They are not the same subject and not a correct answer — they are a horizon to compare against.',
      noMotif: 'This prompt asks for a change to a picture, not for a subject. There is nothing to search for.',
      nothingFound: 'Nothing in Wikimedia Commons came back for this search term. That can mean the term is off, or that this subject is not collected there.',
      unavailable: 'The archive could not be reached right now.',
      thumbUnavailable: 'This picture could not be loaded from the archive.',
      licenceUnknown: 'Licence not stated',
      authorUnknown: 'Author not stated',
    },
    platformLanguages: 'Platform Languages',
    furtherLanguages: 'Further Languages',
    selectHint: '{count} of {max} languages selected',
    // Over the language fields and over the starting number, which
    // stands above the columns because every picture is computed from
    // the same noise.
    languagesLabel: 'Languages',
    seedLabel: 'Seed',
    modelLabel: 'Model',
    generateAll: 'Compare All',
    generatingAll: 'Generating...',
    generating: 'Generating...',
    waiting: 'Waiting...',
    favorite: 'Add to favorites',
    unfavorite: 'Remove from favorites',
    download: 'Download image',
    analyze: 'Analyze image',
  },
  provenance: {
    title: 'About This Model',
    madeBy: 'Made by:',
    learnedFrom: 'Learned from:',
    howBig: 'Size:',
    kidsNote: 'Not all creators were asked if the AI could learn from their work.',
    publisher: 'Publisher',
    architecture: 'Architecture',
    parameters: 'Parameters',
    license: 'License',
    trainingData: 'Training Data',
    safetyByDesign: 'Safety by Design',
    sources: 'Data Sources',
    consent: 'Creator Consent',
    consentValues: {
      none: 'None',
      partial: 'Partial',
      full: 'Full',
      unknown: 'Unknown',
    },
    knownBiases: 'Known Biases',
    knownGaps: 'Known Gaps',
    youthReflection: 'Every model has a perspective shaped by its training data. What voices might be missing?',
  },
  edutainment: {
    ui: {
      didYouKnow: 'Did you know?',
      learnMore: 'Learn more',
      currentlyHappening: 'Currently happening:',
      energyUsed: 'Energy used',
      co2Produced: 'CO₂ produced'
    },
    denoising: {
      modelLoading: 'Loading model into GPU memory...',
      modelLoadingVram: 'Loading model... {used} / {expected} GB VRAM',
      cloudProcessing: 'Sending request to cloud API...',
      modelCard: 'Model Profile',
      publisher: 'Publisher',
      architecture: 'Architecture',
      parameters: 'Parameters',
      textEncoders: 'Text Encoders',
      quantization: 'Quantization',
      vramRequired: 'VRAM Required',
      resolution: 'Resolution',
      license: 'License',
      fairCulture: 'Fair Culture',
      safetyByDesign: 'Safety by Design',
      denoisingActive: 'Denoising in progress...',
      encodingClipL: 'CLIP-L reads your text... ({count} tokens)',
      encodingClipG: 'CLIP-G reads your text... ({count} tokens)',
      encodingT5: 'T5-XXL reads your text... ({count} tokens)',
      encodingEmbeddings: 'Creating embeddings...',
      encodingDenoisingStarts: 'Denoising starts...',
    },
    energy: {
      kids_1: 'AI images need electricity – as much as charging your phone for 3 hours!',
      kids_2: 'The GPU is like a super calculator that eats lots of power!',
      kids_3: 'Each image needs as much energy as running an LED light for 10 minutes!',
      youth_1: 'A GPU uses {watts}W while generating – like a small space heater!',
      youth_2: 'One image uses about 0.01-0.02 kWh – sounds little, but adds up!',
      youth_3: 'The GPU is getting {temp}°C hot right now – that\'s why it needs cooling!',
      expert_1: 'Current draw: {watts} W {\'|\'} GPU load: {util}% {\'|\'} Accumulated: {kwh} kWh (integrated over time)',
      expert_2: 'TDP limit: {tdp}W {\'|\'} Current: {watts}W ({percent}% of limit)',
      expert_3: 'VRAM: {used}/{total} GB ({percent}%) – model + activations'
    },
    data: {
      kids_1: 'The GPU is calculating 10 billion times right now – faster than you can count!',
      kids_2: 'The image is created in 25 small steps – like a puzzle solving itself!',
      kids_3: 'Millions of numbers are flying through the GPU right now!',
      youth_1: 'Each image goes through 25 "denoising steps" – 25 rounds of removing noise!',
      youth_2: '8 billion parameters are being queried – per image!',
      youth_3: 'The AI computes in vectors with thousands of dimensions – like coordinates in a space.',
      expert_1: 'MMDiT: Multimodal Diffusion Transformer – text + image in joint attention layers',
      expert_2: 'Self-Attention: O(n²) complexity – every token is compared with all others',
      expert_3: 'Classifier-Free Guidance: prompt influence vs. creativity balance'
    },
    model: {
      kids_1: 'The AI model was trained on millions of images to learn how to paint!',
      kids_2: 'The AI paints from numbers – millions of pictures turned into numbers!',
      kids_3: '8 billion connections in the model – more than stars you can see in the sky!',
      youth_1: 'SD3.5 Large has 8 billion parameters – like 8 billion decision nodes.',
      youth_2: '3 text encoders work together: CLIP-L, CLIP-G, and T5-XXL',
      youth_3: 'The model needs {vram} GB VRAM just to be loaded!',
      expert_1: 'Architecture: Rectified Flow + MMDiT with 38 transformer blocks',
      expert_2: 'FP16/FP8 quantization: precision vs. VRAM trade-off',
      expert_3: 'LoRA: Low-Rank Adaptation – only 0.1% of parameters retrained'
    },
    ethics: {
      kids_1: 'AI learns from images on the internet – that\'s why it\'s important to be fair with other people\'s art!',
      kids_2: 'Not all artists were asked if the AI could learn from them.',
      kids_3: 'Good AI respects people\'s work!',
      youth_1: 'Training data often comes from the internet. Artists debate: Fair Use or copying?',
      youth_2: 'The EU AI Act demands transparency: Where does the training data come from?',
      youth_3: 'Question: Who actually owns an AI-generated image?',
      expert_1: 'LAION-5B was partly created without creator consent – legal gray area.',
      expert_2: 'EU AI Act Art. 52: Labeling requirement for AI-generated content',
      expert_3: 'Model Cards & Datasheets: Best practice for ML transparency'
    },
    environment: {
      kids_1: 'Each AI image produces a bit of CO₂ – like driving a car, but less!',
      kids_2: 'Think: Is this image worth the electricity?',
      kids_3: 'Energy for AI often comes from power plants – some clean, some not.',
      youth_1: 'German power grid: ~400g CO₂ per kWh – that adds up!',
      youth_2: '{co2}g CO₂ for this image – with 1000 images that would be {totalKg} kg!',
      youth_3: 'Tip: Generate fewer images, but more thoughtfully – saves energy and CO₂.',
      expert_1: 'Calculation: {watts}W × {seconds}s ÷ 3600 × 400g/kWh = {co2}g CO₂',
      expert_2: 'Scope 2 emissions: data center location is decisive',
      expert_3: 'PUE (Power Usage Effectiveness): Additional energy overhead for cooling'
    },
    iceberg: {
      drawPrompt: 'AI generation uses a lot of energy. Draw icebergs and see what happens...',
      redraw: 'Redraw',
      startMelting: 'Start melting',
      melting: 'Iceberg melting...',
      melted: 'Melted!',
      meltedMessage: '{co2}g CO₂ produced',
      comparison: 'This CO₂ amount melts about {volume} cm³ of Arctic ice.',
      comparisonInfo: '(Each ton of CO₂ = approx. 6m³ sea ice loss)',
      gpuPower: 'Graphics card power consumption',
      gpuTemp: 'Graphics card temperature',
      co2Info: 'CO₂ emissions from power consumption (based on German energy mix)',
      drawAgain: 'Draw more icebergs...'
    },
    pixel: {
      grafikkarte: 'Graphics Card',
      energieverbrauch: 'Energy Usage',
      co2Menge: 'CO₂ Amount',
      smartphoneComparison: 'You would need to keep your phone off for {minutes} minutes to offset this CO₂ usage!',
      clickToProcess: 'Click on the data pixels to generate a mini image!'
    },
    forest: {
      trees: 'Trees',
      clickToPlant: 'Click to plant trees! Where you plant a tree, the factory will disappear.',
      gameOver: 'The forest is lost!',
      treesPlanted: 'You planted {count} trees.',
      complete: 'Generation complete',
      comparison: 'An average tree needs {minutes} minutes to absorb this amount of CO₂.'
    },
    rareearth: {
      clickToClean: 'Click the lake to remove toxic sludge!',
      sludgeRemoved: 'Sludge removed',
      environmentHealth: 'Environment',
      gameOverInactive: 'You gave up... mining continues',
      infoBanner: 'Rare earth mining for GPU chips leaves toxic sludge and destroys ecosystems. Your cleanup efforts cannot match the speed of extraction.',
      instructionsCooldown: '{seconds}s',
      statsGpu: 'GPU',
      statsHealth: 'Environment',
      statsSludge: 'Sludge removed'
    }
  },
  persona: {
    connectionError: '[Connection error]',
    title: 'Testing ideas',
    speak: 'Read this out',
    stopSpeaking: 'Stop',
    tapToHear: 'Tap to hear it',
    spokenInEnglish: 'Read out in English — there is no voice for this language',
    surfaceSettings: 'Surface settings',
    newDialog: 'New dialog',
    description: 'If we want to be creative, or to get something right, we need imagination, because without an idea nothing happens. But working artistically means working further on our own idea and developing it. An AI must not take our imagination away, but it can help us develop our ideas further. This page puts up resistance to your ideas. It challenges you to understand your own ideas better, and it can also support you in that. -- But you have to convince it - that is not easy! Two things can be learned here: to put an idea into words, sharpen it and give reasons for what you want to achieve and why, and to see how a chatbot reacts if it is not told to be pleasing and charming.',
    // The two halves of `description` above, word for word, split where it turns
    // from what happens here to what is learned here. They are this page's
    // address (see stores/pageAddress): authored text, put on the page
    // unchanged, never spoken and never sent to a model. `description` itself is
    // no longer rendered anywhere; it stays as the source the other languages
    // split their own halves out of.
    story: 'If we want to be creative, or to get something right, we need imagination, because without an idea nothing happens. But working artistically means working further on our own idea and developing it. An AI must not take our imagination away, but it can help us develop our ideas further. This page puts up resistance to your ideas. It challenges you to understand your own ideas better, and it can also support you in that. -- But you have to convince it - that is not easy!',
    purpose: 'Two things can be learned here: to put an idea into words, sharpen it and give reasons for what you want to achieve and why, and to see how a chatbot reacts if it is not told to be pleasing and charming.',
    activate: 'Start Conversation',
  },
  resona: {
    story: 'This page is for planning and shaping artistic and/or AI-related learning with this platform: the planning with educators, the workshop itself, and the review afterwards of what was done and how the AI behaved. What this platform has been given about itself, about generative AI and about artistic-pedagogical approaches can be looked up here.',
    purpose: 'Two things can be learned here: to plan and shape art-pedagogical processes with generative AI, and to watch and judge how an AI tries to carry out human artistic and pedagogical aims — can it contribute without putting itself at the centre, and can it stay silent when that is called for?',
    title: 'Together',
    intro: 'Accompanies your collective process — the work stays yours.',
    noResponse: '[No response]',
    connectionError: 'The answer did not arrive. Please send it again.',
    replyBrokeOff: 'The reply broke off mid-sentence — what stands here and on the board is what arrived.',
    cancel: 'Cancel',
    removeImage: 'Remove image',
    generationError: 'The generation did not complete. Try again, or change the idea.',
    journalNotice: 'Your workshop journal is recording.',
    journalPaused: 'Workshop journal paused.',
    journalPause: 'Pause journal',
    journalResume: 'Resume journal',
    surfaceSettings: 'Surface settings',
    journalNewDialog: 'New dialogue',
    surfaceClear: 'Clear surface',
    surfaceClearConfirm: 'Clear the surface? Everything lying on it goes \u2014 the cards, the notes, the plans. The dialogue and the journal stay.',
    surfaceClearConfirmYes: 'Clear surface',
    newDialogConfirm: 'Start a new dialogue? This one is dropped \u2014 its journal and what was noted in it are gone. Kept favourites and generated images stay.',
    newDialogConfirmYes: 'New dialogue',
    newConfirm: 'Start a new conversation? This one is kept in the journal, and what was noted stays known.',
    newConfirmYes: 'New conversation',
    planCopy: 'Copy plan',
    lift: 'lift out',
    resize: 'drag to resize',
    removeMemo: 'discard memo',
    foldMemo: 'fold to the title',
    unfoldMemo: 'unfold the memo',
    planCopied: 'Copied',
    broughtAttr: '— brought along',
    modeVoice: 'Voice only',
    modeBoth: 'Voice and writing',
    modeText: 'Writing only',
    hearAgain: 'Hear this again',
    tapToHear: 'Tap to hear it',
  },
  resonaScene: {
    // Kapsel-Streifen: the capsules of a document the session
    // analysed, standing on the board. Labels are naming forms (the noun of
    // the key); the counts and notices carry one declarative sentence.
    kind: 'Scene capsules',
    stripLabel: 'Capsules of the document',
    promptLabel: 'Prompt',
    carry: 'Into the line',
    flaggedCount: '{n} sections excluded, protection reasons',
    discardedCount: '{n} capsules discarded by the capsule gate',
    analyzed: 'Analysed {date}',
    duplicate: 'This document has already been analysed in this session. The capsules that exist keep standing.',
    analysisFailed: 'The document analysis did not complete. The file stays with whoever brought it; nothing was kept.',
    unavailable: 'The document could not be taken in because of a technical fault. Nothing was judged; please try again in a moment.',
    rejectTitle: 'Document not accepted',
    rej: {
      notPdf: 'Document not accepted: the file is not a readable PDF.',
      encrypted: 'Document not accepted: encrypted documents are not taken.',
      tooManyPages: 'Document not accepted: the document exceeds the page limit of 1000 pages.',
      embeddedFile: 'Document not accepted: the document carries embedded files.',
      launchAction: 'Document not accepted: the document carries actions that start programs.',
      blocked: 'Document not accepted: this document is blocked.',
      para86a: 'Document not accepted: symbols of organisations banned under German law.',
      para86: 'Document not accepted: content of organisations banned under German law.',
      further: 'Document not accepted: the content does not meet the admission criteria.',
      generic: 'Document not accepted.',
    },
  },

  resonaMediaCard: {
    flipToBack: 'Turn the card',
    flipToFront: 'Back to the front',
    motivation: 'Reason',
    motivationMissing: 'No separate reason was given — look at the conversation around it.',
    promptLabel: 'Prompt',
    settingLabel: 'Setting',
    timestamp: 'Generated',
    errorState: 'The generation did not complete. Try again, or change the idea.',
  },
  resonaEntityCard: {
    apparatus: 'Apparatus',
    note: 'Note',
    document: 'Document',
    page: 'Page',
    detailLabel: 'Excerpt',
    factsLabel: 'Reference',
    keptHere: 'The reference is what this card keeps.',
    flipToBack: 'Turn the card',
    flipToFront: 'Back to the front',
    remove: 'Take off the board',
  },
  resonaGraphCard: {
    running: 'Running',
    finished: 'Finished',
    failed: 'Failed',
    starting: 'Setting up the apparatus…',
    apparatus: 'Reason',
    motivationMissing: 'No separate reason was given — look at the conversation around it.',
    summaryLabel: 'Summary',
    nodeCount: '{n} steps',
    startedAt: 'Started',
    finishedAt: 'Finished',
    showMore: 'Show more',
    showLess: 'Show less',
    noResults: 'The apparatus produced no shown output.',
    flipToBack: 'Turn the card',
    flipToFront: 'Back to the front',
    errorState: 'The apparatus did not finish. Try again, or change the idea.',
    connectionLost: 'The connection broke off mid-run — likely a server restart. Finished parts are kept in the workshop records.',
    partial: 'Partial',
    partialRecovered: '{n} of {m} pieces were finished and recovered.',
    errorRendered: 'Finished pieces',
  },
  resonaCompositionCard: {
    badge: 'Image+Sound',
    badgeVideo: 'Video+Sound',
    flipToBack: 'Turn the card',
    flipToFront: 'Back to the front',
    motivation: 'Reason',
    motivationMissing: 'No separate reason was given — look at the conversation around it.',
    composedFrom: 'Composed from',
    roleImage: 'Image',
    roleSound: 'Sound',
    roleVideo: 'Video',
    timestamp: 'Composed',
  },
  trashy: {
    title: 'Help',
    placeholder: 'Your question…',
    greeting: 'Hello. This is the help for this platform — ask about the page you are on, or about one of its modes.',
    noPageInfo: 'A description of this page is still to come. Until then, the help answers questions about the platform as a whole.',
    noResponse: 'No response received.',
    thinking: 'One moment...',
    internalInference: 'internal inference',
    sendError: 'Sorry, there was an error sending the message. Please try again.',
    sendTooltip: 'Send message (Enter)',
    openTooltip: 'Open help — drag to move, double-click to reset',
    closeTooltip: 'Close',
    addressTooltip: 'About this page',
    analysisReflectionLoading: 'Looking at the analysis...',
    analysisReflectionError: 'No reflection could be generated right now. You can still read the analysis above.',
  },
  // --- Lab user/course system (Phase 0). English source only; de/tr/ko/uk/fr/es/he/ar/bg
  //     filled by the i18n-translator agent (see WORK_ORDERS.md). Terminus: "Course". ---
  auth: {
    title: 'Sign in',
    tabEducator: 'Course leader',
    tabParticipant: 'Participant',
    identifier: 'E-mail or username',
    password: 'Password',
    // participants enter with the code of a place (2026-09-23)
    code: 'Code',
    codeUnknown: 'Unknown code. Check the spelling or ask the course leader.',
    courseClosed: 'The course is closed at the moment. The course leader can open access.',
    // 429 of the place login: this address has spent its budget of codes that
    // name no active place (devserver/my_app/lab/login_attempts.py); {n} is
    // the server's wait in seconds. SUPPLIED WORDING, verbatim.
    codeTooManyAttempts: 'Too many unknown codes from this network. Try again in {n} seconds.',
    // The row over any page when the sign-in of this device's place has
    // ended while the page stood open (components/PlaceSignInEnded.vue);
    // {n} is the number of the place.
    placeSessionEnded: 'The sign-in of place {n} has ended.',
    login: 'Sign in',
    loggingIn: 'Signing in\u2026',
    logout: 'Sign out',
  },
  account: {
    title: 'My area',
    comingSoon: 'Your works, drafts and saved prompts will appear here soon.',
  },
  educator: {
    dashboard: 'Course leader area',
    comingSoon: 'Your courses and interception prompts will appear here soon.',
    // courses
    createCourse: 'Create course',
    newCourseName: 'Course name',
    noCourses: 'No courses yet.',
    safety: 'Safety',
    settings: 'Settings',
    promptName: 'Course name',
    canViewWorks: 'Allow me to view participants\u2019 works',
    canViewWorksHelp: 'Off by default for data protection. Turning this on is logged.',
    // places (2026-09-23): one per device, each entered with its code
    places: 'Places',
    placeCount: '{n} place | {n} places',
    placeLabel: 'Place {n}',
    accessOpenUntil: 'Access open until {until}',
    accessClosed: 'Access closed',
    accessUntil: 'Access until',
    changeAccess: 'Change',
    openAccess: 'Open access',
    closeAccess: 'End access',
    deviceCount: 'Number of devices',
    makeCodes: 'Generate codes',
    codeIssued: 'Code from {when}',
    replaceCode: 'Replace code',
    makeCode: 'Generate code',
    // The row over the course page before a place's code is replaced
    // (views/educator/CourseEditor.vue); {n} is the number of the place.
    replaceCodeConfirm: 'Place {n} gets a new code. A device signed in with the old one is signed out.',
    copy: 'Copy',
    copied: 'Copied',
    print: 'Print',
    codesShownOnce: 'This code is shown only once. Copy or print it now. | These codes are shown only once. Copy or print them now.',
    placesHelp: 'For each place the platform stores a number and a code. The institution itself records which person uses which device, on paper or on the course leader\u2019s computer.',
    slipSignIn: 'Sign in at {address}',
    accessUntilPast: 'The moment in \u201cAccess until\u201d has to lie ahead.',
    placesStatus: 'The server answered with status {status}.',
    placesNoAnswer: 'The server gave no answer.',
    copyFailed: 'The browser gave no access to the clipboard. Select the code and copy it by hand. | The browser gave no access to the clipboard. Select the codes and copy them by hand.',
    clipboardHttpsOnly: 'The browser offers its clipboard over secure connections only, and this page is served over plain HTTP. Select the code and copy it by hand. | The browser offers its clipboard over secure connections only, and this page is served over plain HTTP. Select the codes and copy them by hand.',
    printBlocked: 'The browser blocked the print window. Allow pop-ups for this page, then click \u201cPrint\u201d again.',
    // co-leaders
    coLeaders: 'Co-leaders',
    coLeaderIdentifier: 'Educator e-mail or username',
    addCoLeader: 'Add co-leader',
    palette: 'Perspectives in this course',
    paletteHelp:
      'While this list holds at least one given perspective, the course offers those and no others. Turn an entry off to withhold it without losing its place.',
    paletteEmptyHelp:
      'Empty: the course offers every given perspective. Add one to narrow the choice to what you put here.',
    paletteAdd: 'Add',
    paletteAddPreset: 'a given perspective…',
    paletteAddKept: 'one you saved…',
    paletteKeptHelp:
      'Only a perspective you saved AND published can go into a course. Saved perspectives are curated here but are not offered in the chooser yet.',
    paletteUp: 'one place up',
    paletteDown: 'one place down',
    paletteToggle: 'show or withhold',
    paletteFailed: 'That change was not saved. The list has been read again.',
    coLeaderHelp: 'Add another course leader (an existing educator) so they can co-manage this course.',
    // danger zone / delete course
    dangerZone: 'Danger zone',
    deleteCourse: 'Delete course\u2026',
    deleteCourseHelp: 'Permanently deletes this course and its data. This cannot be undone.',
    deleteCourseTitle: 'Delete \u201c{name}\u201d?',
    deleteCourseWarning: 'This will permanently delete the course and cascade to its data.',
    impactParticipants: '{n} place removed | {n} places removed',
    impactWorks: '{n} work(s) created in this course will be deleted',
    deleteCourseDsgvo: 'GDPR notice: works of minors will be deleted. Make sure any required exports have been provided to participants beforehand.',
    deleteCoursePresetsSafe: 'Preset originals are never touched and remain available.',
    deleteConfirmPrompt: 'Type the course name \u201c{name}\u201d to confirm:',
    deleteCourseConfirm: 'Delete course permanently',
  },
  // Admin-only educator account management (AdminUsersView.vue).
  admin: {
    users: {
      title: 'Manage users',
      subtitle: 'Create and manage course-leader (educator) accounts. Educators are admin-created \u2014 there is no self-signup. Educators create participant accounts themselves.',
      createEducator: 'Create course-leader account',
      email: 'E-mail',
      displayName: 'Display name',
      tempPassword: 'Temporary password (optional \u2014 generated if empty)',
      create: 'Create',
      creating: 'Creating\u2026',
      createdHint: 'Created. Share these credentials once \u2014 the temporary password is not recoverable later:',
      educators: 'Course leaders',
      loading: 'Loading\u2026',
      noEducators: 'No course-leader accounts yet.',
      colName: 'Name',
      colIdentifier: 'Identifier',
      colEmail: 'E-mail',
      colStatus: 'Status',
      colActions: 'Actions',
      active: 'active',
      inactive: 'inactive',
      activate: 'Activate',
      deactivate: 'Deactivate',
      resetPassword: 'Reset password',
      delete: 'Delete',
    },
  },
  platformVoice: {
    askTitle: 'Pose a question',
    placeholder: 'Type your question…',
    thinking: 'an answer is coming…',
    error: 'No answer arrived — the chat service did not respond. Try again.',
  },
  // The name of the one agent standing on a page — its mask's accessible name
  // and tooltip. Which one appears comes from the route table in App.vue.
  figure: {
    advice: 'Advice',
    contest: 'Contest',
    help: 'Help',
  },
}
