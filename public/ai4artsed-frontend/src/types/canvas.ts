/**
 * Canvas Workflow Types for AI4ArtsEd DevServer
 *
 * Defines types for the visual canvas workflow builder.
 * Supports parallel fan-out workflows with feedback loops.
 *
 * Session 129: Phase 1 Implementation
 */
import type { LocalizedString } from '@/i18n'

// ============================================================================
// NODE TYPES
// ============================================================================

/**
 * Available stage/node types in the canvas
 *
 * NOTE: Safety is NOT a user-visible node!
 * - Stage 1 Safety: Automatic in /pipeline/interception
 * - Stage 3 Safety: Automatic per output-config
 * DevServer handles all safety transparently.
 *
 * Session 134: Added evaluation/fork/display/loop nodes for decision logic
 */
export type StageType =
  | 'input'
  | 'image_input' // Session 152: Image upload as source
  | 'random_prompt' // Session 140: LLM-based random prompt generator with presets
  | 'interception'
  | 'translation'
  | 'model_adaption' // Session 145: Model-specific prompt adaption (CLIP/T5 encoder)
  | 'generation'
  | 'collector'
  // Session 134 Refactored: Unified evaluation node with optional branching
  | 'evaluation'
  // Session 152: Vision-LLM image analysis
  | 'image_evaluation'
  // Display node (visualization)
  | 'display'
  // Session 147: Multi-input comparison evaluator
  | 'comparison_evaluator'
  // Session 149: Seed control node for reproducible generation
  | 'seed'
  // Session 151: Parameter nodes for generation control
  | 'resolution'
  | 'quality'

// ============================================================================
// MODEL ADAPTION TYPES (Session 145)
// ============================================================================

/** Model Adaption Preset Types - adapts prompt for specific media models */
export type ModelAdaptionPreset =
  | 'none'      // No adaption (pass-through)
  | 'sd35'      // Stable Diffusion 3.5 (CLIP-style keywords)
  | 'flux'      // Flux (T5-style natural language)
  | 'video'     // Video models (scenic descriptions)
  | 'audio'     // Audio/Music models (auditive descriptions)

// ============================================================================
// INTERCEPTION PRESET TYPES (Session 146)
// ============================================================================

/** Interception Preset IDs - maps to Stage2 interception configs */
export type InterceptionPreset =
  | 'user_defined'              // Default - eigene Anweisung
  | 'analog_photography_1870s'  // Daguerreotype
  | 'analog_photography_1970s'  // Analog Photography
  | 'analogue_copy'             // Analogue Copy
  | 'bauhaus'                   // Bauhaus
  | 'clichefilter_v2'           // De-Kitsch (note: no accent in ID)
  | 'confucianliterati'         // Literati
  | 'cooked_negatives'          // Cooked Negatives
  | 'digital_photography'       // Digital Photography
  | 'forceful'                  // Forceful
  | 'hunkydoryharmonizer'       // Sweetener
  | 'jugendsprache'             // Slang
  | 'mad_world'                 // mad world
  | 'one_world'                 // One World
  | 'overdrive'                 // Amplifier
  | 'p5js_simplifier'           // Listifier
  | 'tonejs_composer'           // Music Composer
  | 'piglatin'                  // Word Game
  | 'planetarizer'              // Planetarizer
  | 'renaissance'               // Renaissance
  | 'sensitive'                 // Sensitive
  | 'stillepost'                // Telephone
  | 'technicaldrawing'          // Technical
  | 'tellastory'                // Your Story
  | 'theopposite'               // On the Contrary!

/** Interception Preset Config with labels */
export interface InterceptionPresetConfig {
  label: LocalizedString
}

/** Interception Presets - labels only, context loaded from backend on selection */
export const INTERCEPTION_PRESETS: Record<InterceptionPreset, InterceptionPresetConfig> = {
  user_defined: { label: { en: 'Your Call!', bg: 'Ти решаваш!', de: 'Du bestimmst!', tr: 'Sen Karar Ver!', ko: '자유 선택!', uk: 'Ти вирішуєш!', fr: 'C\'est toi qui choisis !', es: '\u00a1T\u00fa decides!' } },
  analog_photography_1870s: { label: { en: 'Daguerreotype', bg: 'Дагеротип', de: 'Daguerreotypie', tr: 'Dagerotipi', ko: '다게레오타입', uk: 'Дагеротип', fr: 'Daguerr\u00e9otype', es: 'Daguerrotipo' } },
  analog_photography_1970s: { label: { en: 'Analog Photography', bg: 'Аналогова фотография', de: 'Analogfotografie', tr: 'Analog Fotoğrafçılık', ko: '아날로그 사진', uk: 'Аналогова фотографія', fr: 'Photographie analogique', es: 'Fotograf\u00eda anal\u00f3gica' } },
  analogue_copy: { label: { en: 'Analogue Copy', bg: 'Аналогово копие', de: 'Analoge Kopie', tr: 'Analog Kopya', ko: '아날로그 복사', uk: 'Аналогова копія', fr: 'Copie analogique', es: 'Copia anal\u00f3gica' } },
  bauhaus: { label: { en: 'Bauhaus', bg: 'Баухаус', de: 'Bauhaus', tr: 'Bauhaus', ko: '바우하우스', uk: 'Баухаус', fr: 'Bauhaus', es: 'Bauhaus' } },
  clichefilter_v2: { label: { en: 'De-Kitsch', bg: 'Анти-кич', de: 'Entkitscher', tr: 'Kiç Filtresi', ko: '키치 제거', uk: 'Декітч', fr: 'Anti-kitsch', es: 'Anti-kitsch' } },
  confucianliterati: { label: { en: 'Literati', bg: 'Литерати', de: 'Literati', tr: 'Literati', ko: '문인화', uk: 'Літераті', fr: 'Lettres', es: 'Literati' } },
  cooked_negatives: { label: { en: 'Cooked Negatives', bg: 'Варени негативи', de: 'Gekochte Filmnegative', tr: 'Pişmiş Negatifler', ko: '가공된 네거티브', uk: 'Варені негативи', fr: 'N\u00e9gatifs cuits', es: 'Negativos cocidos' } },
  digital_photography: { label: { en: 'Digital Photography', bg: 'Дигитална фотография', de: 'Digitalfotografie', tr: 'Dijital Fotoğrafçılık', ko: '디지털 사진', uk: 'Цифрова фотографія', fr: 'Photographie num\u00e9rique', es: 'Fotograf\u00eda digital' } },
  forceful: { label: { en: 'Forceful', bg: 'мощен', de: 'kraftvoll', tr: 'Güçlü', ko: '강렬한', uk: 'потужний', fr: 'puissant', es: 'contundente' } },
  hunkydoryharmonizer: { label: { en: 'Sweetener', bg: 'Подсладител', de: 'Verniedlicher', tr: 'Tatlandırıcı', ko: '감미료', uk: 'Солоджувач', fr: '\u00c9dulcorant', es: 'Endulzante' } },
  jugendsprache: { label: { en: 'Slang', bg: 'Младежки жаргон', de: 'Jugendslang', tr: 'Gençlik Argosu', ko: '청소년 은어', uk: 'Молодіжний сленг', fr: 'Argot jeune', es: 'Jerga juvenil' } },
  mad_world: { label: { en: 'mad world', bg: 'луд свят', de: 'verrückt', tr: 'çılgın dünya', ko: '미친 세상', uk: 'божевільний світ', fr: 'monde fou', es: 'mundo loco' } },
  one_world: { label: { en: 'One World', bg: 'Един свят', de: 'Eine Welt', tr: 'Tek Dünya', ko: '하나의 세계', uk: 'Один світ', fr: 'Un seul monde', es: 'Un solo mundo' } },
  overdrive: { label: { en: 'Amplifier', bg: 'Усилвател!', de: 'Übertreiber!', tr: 'Abartmacı!', ko: '증폭기!', uk: 'Підсилювач!', fr: 'Amplificateur !', es: '\u00a1Amplificador!' } },
  p5js_simplifier: { label: { en: 'Listifier', bg: 'Листификатор', de: 'Auflister', tr: 'Listeleyici', ko: '목록화', uk: 'Перелічувач', fr: 'Listificateur', es: 'Listificador' } },
  tonejs_composer: { label: { en: 'Music Composer', bg: 'Музикален композитор', de: 'Musikkomponist', tr: 'Müzik Bestecisi', ko: '음악 작곡가', uk: 'Музичний композитор', fr: 'Compositeur musical', es: 'Compositor musical' } },
  piglatin: { label: { en: 'Word Game', bg: 'Езикова игра', de: 'Sprachspiel', tr: 'Kelime Oyunu', ko: '말놀이', uk: 'Мовна гра', fr: 'Jeu de mots', es: 'Juego de palabras' } },
  planetarizer: { label: { en: 'Planetarizer', bg: 'Планетаризатор', de: 'Planetarisierer', tr: 'Gezegenleştirici', ko: '행성화', uk: 'Планетаризатор', fr: 'Plan\u00e9tariseur', es: 'Planetarizador' } },
  renaissance: { label: { en: 'Renaissance', bg: 'Ренесанс', de: 'Renaissance', tr: 'Rönesans', ko: '르네상스', uk: 'Ренесанс', fr: 'Renaissance', es: 'Renacimiento' } },
  sensitive: { label: { en: 'Sensitive', bg: 'чувствителен', de: 'sensibel', tr: 'Duyarlı', ko: '섬세한', uk: 'чутливий', fr: 'sensible', es: 'sensible' } },
  stillepost: { label: { en: 'Telephone', bg: 'Развален телефон', de: 'Stille Post', tr: 'Kulaktan Kulağa', ko: '전화 게임', uk: 'Зіпсований телефон', fr: 'T\u00e9l\u00e9phone arabe', es: 'Tel\u00e9fono descompuesto' } },
  technicaldrawing: { label: { en: 'Technical', bg: 'Технически', de: 'Technisch', tr: 'Teknik', ko: '기술적', uk: 'Технічний', fr: 'Technique', es: 'T\u00e9cnico' } },
  tellastory: { label: { en: 'Your Story', bg: 'Твоята история', de: 'Deine Geschichte', tr: 'Senin Hikayen', ko: '너의 이야기', uk: 'Твоя історія', fr: 'Ton histoire', es: 'Tu historia' } },
  theopposite: { label: { en: 'On the Contrary!', bg: 'Напротив!', de: 'Im Gegenteil!', tr: 'Tam Tersine!', ko: '정반대로!', uk: 'Навпаки!', fr: 'Au contraire !', es: '\u00a1Todo lo contrario!' } }
}

// ============================================================================
// IMAGE EVALUATION PRESET TYPES (Session 152)
// ============================================================================

/** Image Evaluation Preset Types - pedagogical analysis frameworks */
export type ImageEvaluationPreset =
  | 'bildwissenschaftlich'  // Panofsky - Art-historical analysis
  | 'bildungstheoretisch'   // Jörissen/Marotzki - Educational theory
  | 'ethisch'               // Ethical analysis
  | 'kritisch'              // Critical/Decolonial analysis
  | 'custom'                // Custom prompt

/** Image Evaluation Preset Config with labels */
export interface ImageEvaluationPresetConfig {
  label: LocalizedString
  description: LocalizedString
}

/** Image Evaluation Presets - labels only, prompts loaded from backend config.py */
export const IMAGE_EVALUATION_PRESETS: Record<ImageEvaluationPreset, ImageEvaluationPresetConfig> = {
  bildwissenschaftlich: {
    label: { en: 'Art Historical (Panofsky)', bg: 'Изкуствоведски (Панофски)', de: 'Kunsthistorisch (Panofsky)', tr: 'Sanat Tarihi (Panofsky)', ko: '미술사적 (파노프스키)', uk: 'Мистецтвознавчий (Панофський)', fr: 'Histoire de l\'art (Panofsky)', es: 'Historia del arte (Panofsky)' },
    description: { en: '4-stage iconological method', bg: '4-степенен иконологичен метод', de: '4-stufige ikonologische Methode', tr: '4 aşamalı ikonolojik yöntem', ko: '4단계 도상학적 방법', uk: '4-ступінчастий іконологічний метод', fr: 'M\u00e9thode iconologique en 4 \u00e9tapes', es: 'M\u00e9todo iconol\u00f3gico de 4 etapas' }
  },
  bildungstheoretisch: {
    label: { en: 'Educational Theory', bg: 'Образователна теория', de: 'Bildungstheoretisch', tr: 'Eğitim Teorisi', ko: '교육 이론', uk: 'Освітня теорія', fr: 'Th\u00e9orie \u00e9ducative', es: 'Teor\u00eda educativa' },
    description: { en: 'Jörissen/Marotzki framework', bg: 'Рамка на J\u00f6rissen/Marotzki', de: 'Jörissen/Marotzki Framework', tr: 'Jörissen/Marotzki çerçevesi', ko: 'Jörissen/Marotzki 프레임워크', uk: 'Фреймворк Йоріссена/Маротцкі', fr: 'Cadre J\u00f6rissen/Marotzki', es: 'Marco J\u00f6rissen/Marotzki' }
  },
  ethisch: {
    label: { en: 'Ethical', bg: 'Етичен', de: 'Ethisch', tr: 'Etik', ko: '윤리적', uk: 'Етичний', fr: '\u00c9thique', es: '\u00c9tico' },
    description: { en: 'Ethical analysis', bg: 'Етичен анализ', de: 'Ethische Analyse', tr: 'Etik analiz', ko: '윤리적 분석', uk: 'Етичний аналіз', fr: 'Analyse \u00e9thique', es: 'An\u00e1lisis \u00e9tico' }
  },
  kritisch: {
    label: { en: 'Critical/Decolonial', bg: 'Критичен/деколониален', de: 'Kritisch/Dekolonial', tr: 'Eleştirel/Dekolonyal', ko: '비판적/탈식민주의', uk: 'Критичний/деколоніальний', fr: 'Critique/d\u00e9colonial', es: 'Cr\u00edtico/decolonial' },
    description: { en: 'Critical media studies', bg: 'Критични медийни изследвания', de: 'Kritische Medienwissenschaft', tr: 'Eleştirel medya çalışmaları', ko: '비판적 미디어 연구', uk: 'Критичні медіа-дослідження', fr: '\u00c9tudes critiques des m\u00e9dias', es: 'Estudios cr\u00edticos de medios' }
  },
  custom: {
    label: { en: 'Custom', bg: 'Персонализирано', de: 'Eigene Anweisung', tr: 'Özel Talimat', ko: '사용자 정의', uk: 'Власний', fr: 'Personnalis\u00e9', es: 'Personalizado' },
    description: { en: 'Define your own analysis prompt', bg: 'Определете собствен промпт за анализ', de: 'Eigenen Analyse-Prompt definieren', tr: 'Kendi analiz komutunuzu tanımlayın', ko: '나만의 분석 프롬프트 정의', uk: 'Визначте власний промпт аналізу', fr: 'D\u00e9finir votre propre prompt d\'analyse', es: 'Define tu propio prompt de an\u00e1lisis' }
  }
}

// ============================================================================
// RANDOM PROMPT TYPES
// ============================================================================

/** Random Prompt Preset Types */
export type RandomPromptPreset =
  | 'clean_image'  // Szenische Beschreibung (medienneutral)
  | 'photo'        // Fotografische Prompts mit Film-Typ
  | 'artform'      // Kunstform-Transformation
  | 'instruction'  // Kreative Transformation
  | 'language'     // Sprach-Vorschlag

/** Film types for photo preset */
export type PhotoFilmType =
  | 'random'
  | 'Kodachrome' | 'Ektachrome'
  | 'Portra 400' | 'Portra 800' | 'Ektar 100'
  | 'Fuji Pro 400H' | 'Fuji Superia' | 'CineStill 800T'
  | 'Ilford HP5' | 'Ilford Delta 400' | 'Ilford FP4' | 'Ilford Pan F' | 'Ilford XP2'
  | 'Tri-X 400'

/** Node type definition for the palette */
export interface NodeTypeDefinition {
  id: string
  type: StageType
  label: LocalizedString
  description: LocalizedString
  color: string
  icon: string
  /** Whether this node type allows multiple instances */
  allowMultiple: boolean
  /** Whether this node is mandatory in workflows */
  mandatory: boolean
}

/**
 * Predefined node types for the canvas
 *
 * Module Types:
 * - Input: Text input source
 * - Interception: LLM selection (primary!) + interception config (optional override)
 * - Translation: Translation prompt + LLM selection
 * - Generation: Output configs (sd35, qwen, flux2, etc.)
 * - Collector: Fan-in collector for parallel outputs (Media Collector)
 *
 * IMPORTANT: Safety is NOT a node!
 * DevServer handles Stage 1 + Stage 3 safety automatically.
 */
export const NODE_TYPE_DEFINITIONS: NodeTypeDefinition[] = [
  {
    id: 'input',
    type: 'input',
    label: { en: 'Input Prompt', bg: 'Входен промпт', de: 'Eingabe-Prompt', tr: 'Giriş Komutu', ko: '입력 프롬프트', uk: 'Введення промпту', fr: 'Prompt d\'entr\u00e9e', es: 'Prompt de entrada' },
    description: { en: 'Text input source', bg: 'Източник на текстов вход', de: 'Text-Eingabequelle', tr: 'Metin giriş kaynağı', ko: '텍스트 입력 소스', uk: 'Джерело текстового введення', fr: 'Source de texte en entr\u00e9e', es: 'Fuente de entrada de texto' },
    color: '#3b82f6', // blue
    icon: 'edit_square_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: false,
    mandatory: true
  },
  // Session 152: Image Input Node
  {
    id: 'image_input',
    type: 'image_input',
    label: { en: 'Image Input', bg: 'Въвеждане на изображение', de: 'Bild-Eingabe', tr: 'Görsel Girişi', ko: '이미지 입력', uk: 'Введення зображення', fr: 'Entr\u00e9e image', es: 'Entrada de imagen' },
    description: { en: 'Upload image as source', bg: 'Качване на изображение като източник', de: 'Bild als Quelle hochladen', tr: 'Kaynak olarak görsel yükle', ko: '소스로 이미지 업로드', uk: 'Завантажити зображення як джерело', fr: 'T\u00e9l\u00e9verser une image comme source', es: 'Subir imagen como fuente' },
    color: '#0ea5e9', // sky blue
    icon: 'add_photo_alternate_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  // Session 140: Random Prompt Node with presets
  {
    id: 'random_prompt',
    type: 'random_prompt',
    label: { en: 'Random Prompt', bg: 'Случаен промпт', de: 'Zufalls-Prompt', tr: 'Rastgele Komut', ko: '랜덤 프롬프트', uk: 'Випадковий промпт', fr: 'Prompt al\u00e9atoire', es: 'Prompt aleatorio' },
    description: {
      en: 'Generate creative content via LLM with presets',
      bg: 'Генериране на креативно съдържание чрез LLM с предварителни настройки',
      de: 'Generiert kreative Inhalte via LLM mit Presets',
      tr: 'Ön ayarlarla LLM aracılığıyla yaratıcı içerik üret',
      ko: '프리셋으로 LLM을 통해 창의적 콘텐츠 생성',
      uk: 'Генерація креативного контенту через LLM з пресетами',
      fr: 'G\u00e9n\u00e9rer du contenu cr\u00e9atif via LLM avec pr\u00e9r\u00e9glages',
      es: 'Generar contenido creativo v\u00eda LLM con preajustes'
    },
    color: '#ec4899', // pink
    icon: 'shuffle_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  {
    id: 'interception',
    type: 'interception',
    label: { en: 'Interception', bg: 'Интерцепция', de: 'Interception', tr: 'Interception', ko: '인터셉션', uk: 'Інтерсепція', fr: 'Interception', es: 'Intercepci\u00f3n' },
    description: {
      en: 'Pedagogical transformation with LLM selection',
      bg: 'Педагогическа трансформация с избор на LLM',
      de: 'Pädagogische Transformation mit LLM-Auswahl',
      tr: 'LLM seçimiyle pedagojik dönüşüm',
      ko: 'LLM 선택을 통한 교육적 변환',
      uk: 'Педагогічна трансформація з вибором LLM',
      fr: 'Transformation p\u00e9dagogique avec s\u00e9lection de LLM',
      es: 'Transformaci\u00f3n pedag\u00f3gica con selecci\u00f3n de LLM'
    },
    color: '#8b5cf6', // purple
    icon: 'cognition_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  {
    id: 'translation',
    type: 'translation',
    label: { en: 'Translation', bg: 'Превод', de: 'Übersetzung', tr: 'Çeviri', ko: '번역', uk: 'Переклад', fr: 'Traduction', es: 'Traducci\u00f3n' },
    description: {
      en: 'Language translation with custom prompt + LLM',
      bg: 'Езиков превод с персонализиран промпт + LLM',
      de: 'Sprachübersetzung mit eigenem Prompt + LLM',
      tr: 'Özel komut + LLM ile dil çevirisi',
      ko: '사용자 정의 프롬프트 + LLM으로 언어 번역',
      uk: 'Мовний переклад з власним промптом + LLM',
      fr: 'Traduction linguistique avec prompt personnalis\u00e9 + LLM',
      es: 'Traducci\u00f3n de idiomas con prompt personalizado + LLM'
    },
    color: '#f59e0b', // amber
    icon: 'language_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  // Session 145: Model Adaption Node - adapts prompt for specific media models
  {
    id: 'model_adaption',
    type: 'model_adaption',
    label: { en: 'Model Adaption', bg: 'Адаптация на модел', de: 'Modell-Adaption', tr: 'Model Adaptasyonu', ko: '모델 적응', uk: 'Адаптація моделі', fr: 'Adaptation du mod\u00e8le', es: 'Adaptaci\u00f3n de modelo' },
    description: {
      en: 'Adapt prompt for media model (SD3.5, Flux, Video, Audio)',
      bg: 'Адаптиране на промпт за медиен модел (SD3.5, Flux, видео, аудио)',
      de: 'Prompt für Medienmodell anpassen (SD3.5, Flux, Video, Audio)',
      tr: 'Medya modeli için komutu uyarla (SD3.5, Flux, Video, Ses)',
      ko: '미디어 모델에 맞게 프롬프트 조정 (SD3.5, Flux, 비디오, 오디오)',
      uk: 'Адаптація промпту для медіа-моделі (SD3.5, Flux, відео, аудіо)',
      fr: 'Adapter le prompt au mod\u00e8le m\u00e9dia (SD3.5, Flux, vid\u00e9o, audio)',
      es: 'Adaptar prompt para modelo de medios (SD3.5, Flux, video, audio)'
    },
    color: '#14b8a6', // teal
    icon: 'tune_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  {
    id: 'generation',
    type: 'generation',
    label: { en: 'Generation', bg: 'Генериране', de: 'Generierung', tr: 'Üretim', ko: '생성', uk: 'Генерація', fr: 'G\u00e9n\u00e9ration', es: 'Generaci\u00f3n' },
    description: {
      en: 'Media generation (image, audio, video)',
      bg: 'Генериране на медия (изображение, аудио, видео)',
      de: 'Mediengenerierung (Bild, Audio, Video)',
      tr: 'Medya üretimi (görsel, ses, video)',
      ko: '미디어 생성 (이미지, 오디오, 비디오)',
      uk: 'Генерація медіа (зображення, аудіо, відео)',
      fr: 'G\u00e9n\u00e9ration de m\u00e9dias (image, audio, vid\u00e9o)',
      es: 'Generaci\u00f3n de medios (imagen, audio, video)'
    },
    color: '#10b981', // emerald
    icon: 'brush_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: true
  },
  {
    id: 'collector',
    type: 'collector',
    label: { en: 'Media Output', bg: 'Медиен изход', de: 'Medienausgabe', tr: 'Medya Çıktısı', ko: '미디어 출력', uk: 'Медіа-вивід', fr: 'Sortie m\u00e9dia', es: 'Salida de medios' },
    description: {
      en: 'Collects and displays outputs (media + text)',
      bg: 'Събира и показва изходни данни (медия + текст)',
      de: 'Sammelt und zeigt Ausgaben (Medien + Text)',
      tr: 'Çıktıları toplar ve gösterir (medya + metin)',
      ko: '출력 수집 및 표시 (미디어 + 텍스트)',
      uk: 'Збір та відображення виводу (медіа + текст)',
      fr: 'Collecte et affiche les sorties (m\u00e9dias + texte)',
      es: 'Recopila y muestra las salidas (medios + texto)'
    },
    color: '#06b6d4', // cyan
    icon: 'gallery_thumbnail_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: false,
    mandatory: true
  },
  // Session 134 Refactored: Unified Evaluation Node (replaces 5 eval nodes + 2 fork nodes)
  {
    id: 'evaluation',
    type: 'evaluation',
    label: { en: 'Evaluation', bg: 'Оценка', de: 'Bewertung', tr: 'Değerlendirme', ko: '평가', uk: 'Оцінювання', fr: '\u00c9valuation', es: 'Evaluaci\u00f3n' },
    description: {
      en: 'LLM-based evaluation with 3-way branching (pass/fail/commentary)',
      bg: 'LLM-базирана оценка с 3-посочно разклонение (успех/неуспех/коментар)',
      de: 'LLM-basierte Bewertung mit 3-Wege-Verzweigung (Pass/Fail/Kommentar)',
      tr: '3 yönlü dallanma ile LLM tabanlı değerlendirme (geçti/kaldı/yorum)',
      ko: '3방향 분기를 포함한 LLM 기반 평가 (통과/실패/코멘트)',
      uk: 'LLM-оцінювання з 3-стороннім розгалуженням (прийнято/відхилено/коментар)',
      fr: '\u00c9valuation par LLM avec branchement 3 voies (r\u00e9ussite/\u00e9chec/commentaire)',
      es: 'Evaluaci\u00f3n por LLM con ramificaci\u00f3n de 3 v\u00edas (aprobado/reprobado/comentario)'
    },
    color: '#f59e0b', // amber
    icon: 'checklist_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  // Session 152: Image Evaluation Node (Vision-LLM analysis)
  {
    id: 'image_evaluation',
    type: 'image_evaluation',
    label: { en: 'Image Analysis', bg: 'Анализ на изображение', de: 'Bild-Analyse', tr: 'Görsel Analizi', ko: '이미지 분석', uk: 'Аналіз зображення', fr: 'Analyse d\'image', es: 'An\u00e1lisis de imagen' },
    description: {
      en: 'Vision-LLM analysis of images',
      bg: 'Vision-LLM анализ на изображения',
      de: 'Vision-LLM Analyse von Bildern',
      tr: 'Görsellerin Vision-LLM analizi',
      ko: '비전-LLM 이미지 분석',
      uk: 'Vision-LLM аналіз зображень',
      fr: 'Analyse d\'images par Vision-LLM',
      es: 'An\u00e1lisis de im\u00e1genes con Vision-LLM'
    },
    color: '#dc2626', // red
    icon: 'imagesmode_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  // Session 135: Display Node (Terminal - no output)
  {
    id: 'display',
    type: 'display',
    label: { en: 'Preview', bg: 'Преглед', de: 'Vorschau', tr: 'Önizleme', ko: '미리보기', uk: 'Попередній перегляд', fr: 'Aper\u00e7u', es: 'Vista previa' },
    description: {
      en: 'Preview text or media inline (tap/observer, no output)',
      bg: 'Преглед на текст или медия вградено (наблюдател, без изход)',
      de: 'Vorschau von Text oder Medien inline (Tap/Observer, kein Output)',
      tr: 'Metin veya medyayı satır içi önizle (gözlemci, çıktı yok)',
      ko: '텍스트 또는 미디어 인라인 미리보기 (관찰자, 출력 없음)',
      uk: 'Інлайн-перегляд тексту або медіа (спостерігач, без виводу)',
      fr: 'Aper\u00e7u en ligne du texte ou m\u00e9dia (observateur, sans sortie)',
      es: 'Vista previa de texto o medios en l\u00ednea (observador, sin salida)'
    },
    color: '#10b981', // green
    icon: 'info_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  // Session 147: Comparison Evaluator Node (Multi-input comparison)
  {
    id: 'comparison_evaluator',
    type: 'comparison_evaluator',
    label: { en: 'Comparison', bg: 'Сравнение', de: 'Vergleich', tr: 'Karşılaştırma', ko: '비교', uk: 'Порівняння', fr: 'Comparaison', es: 'Comparaci\u00f3n' },
    description: {
      en: 'Compare multiple text inputs with LLM analysis',
      bg: 'Сравняване на множество текстови входове с LLM анализ',
      de: 'Vergleiche mehrere Text-Inputs mit LLM-Analyse',
      tr: 'LLM analizi ile birden fazla metin girdisini karşılaştır',
      ko: 'LLM 분석으로 여러 텍스트 입력 비교',
      uk: 'Порівняння кількох текстових входів з LLM-аналізом',
      fr: 'Comparer plusieurs entr\u00e9es textuelles avec analyse LLM',
      es: 'Comparar m\u00faltiples entradas de texto con an\u00e1lisis LLM'
    },
    color: '#f97316', // orange
    icon: 'analyze.svg',
    allowMultiple: true,
    mandatory: false
  },
  // Session 149: Seed Node for reproducible generation
  {
    id: 'seed',
    type: 'seed',
    label: { en: 'Seed', bg: 'Seed', de: 'Seed', tr: 'Seed', ko: '시드', uk: 'Seed', fr: 'Graine', es: 'Semilla' },
    description: {
      en: 'Control seed for reproducible media generation',
      bg: 'Контрол на seed за възпроизводимо генериране на медия',
      de: 'Seed für reproduzierbare Mediengenerierung',
      tr: 'Tekrarlanabilir medya üretimi için seed kontrolü',
      ko: '재현 가능한 미디어 생성을 위한 시드 제어',
      uk: 'Контроль seed для відтворюваної генерації медіа',
      fr: 'Contr\u00f4le de la graine pour une g\u00e9n\u00e9ration reproductible',
      es: 'Control de semilla para generaci\u00f3n reproducible de medios'
    },
    color: '#6366f1', // indigo
    icon: 'potted_plant_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  // Session 151: Resolution Node for width/height control
  {
    id: 'resolution',
    type: 'resolution',
    label: { en: 'Resolution', bg: 'Резолюция', de: 'Auflösung', tr: 'Çözünürlük', ko: '해상도', uk: 'Роздільність', fr: 'R\u00e9solution', es: 'Resoluci\u00f3n' },
    description: {
      en: 'Set width and height for image generation (ComfyUI only)',
      bg: 'Задаване на ширина и височина за генериране на изображения (само ComfyUI)',
      de: 'Breite und Höhe für Bildgenerierung (nur ComfyUI)',
      tr: 'Görsel üretimi için genişlik ve yükseklik ayarla (yalnızca ComfyUI)',
      ko: '이미지 생성을 위한 너비 및 높이 설정 (ComfyUI 전용)',
      uk: 'Налаштування ширини та висоти для генерації зображень (лише ComfyUI)',
      fr: 'D\u00e9finir largeur et hauteur pour la g\u00e9n\u00e9ration d\'images (ComfyUI uniquement)',
      es: 'Definir ancho y alto para generaci\u00f3n de im\u00e1genes (solo ComfyUI)'
    },
    color: '#0ea5e9', // sky blue
    icon: 'display_settings_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  },
  // Session 151: Quality Node for steps/cfg control
  {
    id: 'quality',
    type: 'quality',
    label: { en: 'Quality', bg: 'Качество', de: 'Qualität', tr: 'Kalite', ko: '품질', uk: 'Якість', fr: 'Qualit\u00e9', es: 'Calidad' },
    description: {
      en: 'Set steps and CFG for generation quality (ComfyUI only)',
      bg: 'Задаване на стъпки и CFG за качество на генериране (само ComfyUI)',
      de: 'Steps und CFG für Generierungsqualität (nur ComfyUI)',
      tr: 'Üretim kalitesi için adım ve CFG ayarla (yalnızca ComfyUI)',
      ko: '생성 품질을 위한 스텝 및 CFG 설정 (ComfyUI 전용)',
      uk: 'Налаштування кроків та CFG для якості генерації (лише ComfyUI)',
      fr: 'D\u00e9finir les \u00e9tapes et le CFG pour la qualit\u00e9 de g\u00e9n\u00e9ration (ComfyUI uniquement)',
      es: 'Definir pasos y CFG para la calidad de generaci\u00f3n (solo ComfyUI)'
    },
    color: '#84cc16', // lime
    icon: 'display_settings_24dp_E3E3E3_FILL0_wght400_GRAD0_opsz24.svg',
    allowMultiple: true,
    mandatory: false
  }
]

// ============================================================================
// CANVAS NODE
// ============================================================================

/** A node instance on the canvas */
export interface CanvasNode {
  /** Unique node ID */
  id: string
  /** Node type (stage) */
  type: StageType
  /** X position on canvas */
  x: number
  /** Y position on canvas */
  y: number
  /** Node-specific configuration overrides */
  config: Record<string, unknown>

  // === Generation node config ===
  /** Selected output config ID for generation nodes (e.g., 'sd35_large', 'flux2_schnell') */
  configId?: string

  // === Interception node config ===
  /** Selected interception preset (Session 146) */
  interceptionPreset?: InterceptionPreset
  /** Selected LLM model ID (e.g., 'gpt-4o-mini', 'claude-3-haiku') */
  llmModel?: string
  /** Context/system prompt for the LLM (pedagogical transformation instructions) */
  contextPrompt?: string

  // === Translation node config ===
  /** Translation prompt/instructions */
  translationPrompt?: string

  // === Input node config ===
  /** User's prompt text (input node) */
  promptText?: string

  // === Display properties ===
  /** Custom width (optional, for resizable nodes like Collector) */
  width?: number
  /** Custom height (optional, for resizable nodes like Collector) */
  height?: number

  // === Session 134 Refactored: Unified Evaluation node config ===
  /** Evaluation type (pre-fills prompt template) */
  evaluationType?: 'fairness' | 'creativity' | 'bias' | 'quality' | 'custom'
  /** Evaluation prompt/criteria description */
  evaluationPrompt?: string
  /** Output type for evaluation results (controls if score is requested) */
  outputType?: 'commentary' | 'score' | 'all'

  // === Feedback config (for Interception/Translation nodes) ===
  /** Maximum feedback iterations (default: 3) */
  maxFeedbackIterations?: number

  // === Display node config ===
  /** Display mode for visualization */
  displayMode?: 'popup' | 'inline' | 'toast'
  /** Display title */
  title?: string

  // === Random Prompt node config (Session 140) ===
  /** Selected preset (determines system prompt) */
  randomPromptPreset?: RandomPromptPreset
  /** LLM model for generation */
  randomPromptModel?: string
  /** Film type (only for 'photo' preset) */
  randomPromptFilmType?: PhotoFilmType
  /** Token limit for generated prompts (75 = CLIP-L, 500 = T5) */
  randomPromptTokenLimit?: 75 | 500

  // === Model Adaption node config (Session 145) ===
  /** Adaption preset (CLIP, T5, or none) */
  modelAdaptionPreset?: ModelAdaptionPreset

  // === Comparison Evaluator node config (Session 147) ===
  /** LLM model for comparison analysis */
  comparisonLlmModel?: string
  /** Evaluation criteria/goals for comparison */
  comparisonCriteria?: string

  // === Seed node config (Session 149) ===
  /** Seed mode: fixed value, random per execution, or increment for batch */
  seedMode?: 'fixed' | 'random' | 'increment'
  /** Fixed seed value (only used when seedMode is 'fixed') */
  seedValue?: number
  /** Base seed for increment mode (batch execution adds run_index) */
  seedBase?: number

  // === Resolution node config (Session 151) ===
  /** Image width in pixels */
  resolutionWidth?: number
  /** Image height in pixels */
  resolutionHeight?: number
  /** Resolution preset (square, portrait, landscape, custom) */
  resolutionPreset?: 'square_1024' | 'portrait_768x1344' | 'landscape_1344x768' | 'custom'

  // === Quality node config (Session 151) ===
  /** Number of inference steps */
  qualitySteps?: number
  /** CFG scale value */
  qualityCfg?: number

  // === Image Input node config (Session 152) ===
  /** Uploaded image data */
  imageData?: {
    image_id: string
    image_path: string
    preview_url: string
    original_size: [number, number]
    resized_size: [number, number]
  }

  // === Image Evaluation node config (Session 152) ===
  /** Vision model for image analysis (local only) */
  visionModel?: string
  /** Image evaluation preset (pedagogical framework) */
  imageEvaluationPreset?: 'bildwissenschaftlich' | 'bildungstheoretisch' | 'ethisch' | 'kritisch' | 'custom'
  /** Custom evaluation prompt (only if preset is 'custom') */
  imageEvaluationPrompt?: string
}

// ============================================================================
// CONNECTION
// ============================================================================

/** A connection between two nodes */
export interface CanvasConnection {
  /** Source node ID */
  sourceId: string
  /** Target node ID */
  targetId: string
  /** Session 134: Label for fork branches (e.g., 'true', 'false', 'approved', 'rejected') */
  label?: string
  /** Session 134: Active state for conditional execution (managed by execution engine) */
  active?: boolean
}

// ============================================================================
// WORKFLOW
// ============================================================================

/** Loop configuration for feedback workflows */
export interface LoopConfig {
  enabled: boolean
  maxIterations: number
  /** Node ID to collect feedback from */
  feedbackFrom?: string
  /** Node ID to feed back into */
  feedbackTo?: string
  /** Conditional termination expression (future) */
  condition?: string
}

/** Automation settings */
export interface AutomationConfig {
  /** Seed control: 'global' applies same seed to all generation nodes, 'per-node' allows individual seeds */
  seedControl: 'global' | 'per-node'
  /** Global seed value (when seedControl is 'global') */
  globalSeed?: number
  /** Whether to automatically apply LoRA automation */
  loraInjection: boolean
}

/** Complete canvas workflow definition */
export interface CanvasWorkflow {
  /** Workflow ID */
  id: string
  /** Workflow name */
  name: string
  /** Workflow description */
  description?: string
  /** Workflow type identifier */
  type: 'canvas_workflow'
  /** All nodes in the workflow */
  nodes: CanvasNode[]
  /** All connections between nodes */
  connections: CanvasConnection[]
  /** Loop/feedback configuration */
  loops?: LoopConfig
  /** Automation settings */
  automation?: AutomationConfig
  /** Creation timestamp */
  createdAt?: string
  /** Last modified timestamp */
  updatedAt?: string
}

// ============================================================================
// EXECUTION
// ============================================================================

/** Execution status for a node */
export type NodeExecutionStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped'

/** Execution state for a single node */
export interface NodeExecutionState {
  nodeId: string
  status: NodeExecutionStatus
  output?: unknown
  error?: string
  startTime?: number
  endTime?: number
  durationMs?: number
}

/** Overall workflow execution state */
export interface WorkflowExecutionState {
  workflowId: string
  status: 'idle' | 'running' | 'completed' | 'failed' | 'interrupted'
  currentIteration: number
  totalIterations: number
  nodeStates: Map<string, NodeExecutionState>
  startTime?: number
  endTime?: number
}

// ============================================================================
// CONFIG SELECTION
// ============================================================================

/** Available LLM model for interception/translation nodes */
export interface LLMModelSummary {
  /** Model ID (e.g., 'gpt-4o-mini', 'claude-3-haiku') */
  id: string
  /** Display name */
  name: string
  /** Provider (openai, anthropic, google, local) */
  provider: string
  /** Model capabilities/description */
  description?: string
  /** Whether this is the default/recommended model */
  isDefault?: boolean
}

/** Output/generation config summary (for palette selection) */
export interface OutputConfigSummary {
  id: string
  name: LocalizedString
  description: LocalizedString
  icon: string
  color: string
  mediaType: 'image' | 'audio' | 'video' | 'music' | 'text'
  backend: string
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Get node type definition by type
 */
export function getNodeTypeDefinition(type: StageType): NodeTypeDefinition | undefined {
  return NODE_TYPE_DEFINITIONS.find(n => n.type === type)
}

/**
 * Check if a connection is valid between two node types
 *
 * Simplified validation - only structural constraints:
 * 1. Terminal nodes (collector, display) have no output
 * 2. Source nodes (input) have no input
 * 3. Seed nodes can only connect to generation nodes
 * 4. No self-loops
 *
 * Data type compatibility (text vs image) is checked at runtime by the backend.
 */
export function isValidConnection(sourceType: StageType, targetType: StageType): boolean {
  // Terminal nodes have no output connector
  const terminalNodes: StageType[] = ['collector', 'display']
  if (terminalNodes.includes(sourceType)) return false

  // Source nodes have no input connector
  const sourceNodes: StageType[] = ['input', 'image_input']
  if (sourceNodes.includes(targetType)) return false

  // Session 149: Seed nodes can only connect to generation nodes
  if (sourceType === 'seed' && targetType !== 'generation') return false

  // Session 151: Resolution and Quality nodes can only connect to generation nodes
  if (sourceType === 'resolution' && targetType !== 'generation') return false
  if (sourceType === 'quality' && targetType !== 'generation') return false

  // No self-loops (same node type connecting to itself is allowed, just not same instance)
  // This is handled elsewhere - same type is fine

  return true
}

/**
 * Generate a unique node ID
 */
export function generateNodeId(type: StageType): string {
  return `${type}_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
}

/**
 * Create a default canvas workflow
 *
 * Default structure: Input → (user adds interception/generation) → Collector
 * Safety is handled automatically by DevServer.
 */
export function createDefaultWorkflow(): CanvasWorkflow {
  const inputNode: CanvasNode = {
    id: generateNodeId('input'),
    type: 'input',
    x: 100,
    y: 200,
    config: { source: 'text' }
  }

  const collectorNode: CanvasNode = {
    id: generateNodeId('collector'),
    type: 'collector',
    x: 900,
    y: 200,
    config: {}
  }

  return {
    id: `workflow_${Date.now()}`,
    name: 'New Workflow',
    type: 'canvas_workflow',
    nodes: [inputNode, collectorNode],
    connections: [],
    automation: {
      seedControl: 'global',
      loraInjection: true
    }
  }
}

// ============================================================================
// RANDOM PROMPT PRESETS (Session 140)
// ============================================================================

/** Preset configuration for Random Prompt node */
export interface RandomPromptPresetConfig {
  label: LocalizedString
  systemPrompt: string
  userPromptTemplate: string
}

/** Random Prompt Presets with system prompts */
export const RANDOM_PROMPT_PRESETS: Record<RandomPromptPreset, RandomPromptPresetConfig> = {
  clean_image: {
    label: { en: 'Scenic Description', bg: 'Сценично описание', de: 'Szenische Beschreibung', tr: 'Sahne Açıklaması', ko: '풍경 묘사', uk: 'Сценічний опис', fr: 'Description sc\u00e9nique', es: 'Descripci\u00f3n esc\u00e9nica' },
    systemPrompt: `You are an inventive creative. Your task is to invent a vivid, detailed image prompt.

IMPORTANT - Generate CLEAN, MEDIA-NEUTRAL images:
- NO camera or photographic references (no film, no camera, no lens)
- NO optical effects (no wide-angle, no telephoto, no macro)
- NO depth of field or bokeh
- NO motion blur or any blur effects
- NO "retro", "vintage", or nostalgic styling
- NO film grain, vignette, or post-processing artifacts

Think globally. Avoid cultural clichés.
Subject matter: scenes, objects, animals, nature, technology, culture, people, homes, family, work, holiday, urban, rural, trivia, intricate details.
Be verbose, provide rich visual details about colors, lighting, textures, composition, atmosphere.
Transform the prompt strictly following the context if provided.
NO META-COMMENTS, TITLES, Remarks, dialogue WHATSOEVER.`,
    userPromptTemplate: 'Generate a creative image prompt.'
  },
  photo: {
    label: { en: 'Photo Prompt', bg: 'Фото промпт', de: 'Foto-Prompt', tr: 'Fotoğraf Komutu', ko: '사진 프롬프트', uk: 'Фото-промпт', fr: 'Prompt photo', es: 'Prompt fotogr\u00e1fico' },
    systemPrompt: `You are an inventive creative. Your task is to invent a REALISTIC photographic image prompt.

Think globally. Avoid cultural clichés. Avoid "retro" style descriptions.
Describe contemporary everyday motives: scenes, objects, animals, nature, tech, culture, people, homes, family, work, holiday, urban, rural, trivia, details.
Choose either unlikely, untypical or typical photographical sujets. Be verbose, provide intricate details.
Always begin your output with: "{film_description} of".
Transform the prompt strictly following the context if provided.
NO META-COMMENTS, TITLES, Remarks, dialogue WHATSOEVER.`,
    userPromptTemplate: 'Generate a creative photographic image prompt.'
  },
  artform: {
    label: { en: 'Artform Transformation', bg: 'Трансформация на форма на изкуството', de: 'Kunstform-Transformation', tr: 'Sanat Formu Dönüşümü', ko: '예술 형식 변환', uk: 'Трансформація форми мистецтва', fr: 'Transformation de forme d\'art', es: 'Transformaci\u00f3n de forma art\u00edstica' },
    systemPrompt: `You generate artform transformation instructions from an artist practice perspective.

IMPORTANT: NEVER use "in the style of" - instead frame as artistic practice, technique, or creative process.

Good examples:
- "Render this as a Japanese Noh theatre performance"
- "Transform this into a Yoruba praise poem"
- "Compose this as a Maori chant"
- "Frame this message through Cubist fragmentation"
- "Present this as an Afro-futurist myth"
- "Choreograph this as a Bharatanatyam narrative"
- "Inscribe this as Egyptian hieroglyphics"
- "Express this through Aboriginal dot painting technique"

Think globally across all cultures and art practices.
Focus on the DOING - the artistic practice, not imitation.
Output ONLY the transformation instruction, nothing else.`,
    userPromptTemplate: 'Generate a creative artform transformation instruction.'
  },
  instruction: {
    label: { en: 'Creative Instruction', bg: 'Творческа инструкция', de: 'Kreative Anweisung', tr: 'Yaratıcı Talimat', ko: '창의적 지시', uk: 'Креативна інструкція', fr: 'Instruction cr\u00e9ative', es: 'Instrucci\u00f3n creativa' },
    systemPrompt: `You generate creative transformation instructions.
Your output is a single instruction that transforms content in an unusual, creative way.
Examples: nature language, theatrical play, nostalgic robot voice, rhythmic rap, animal fable, alien explanation, philosophical versions (Wittgenstein, Heidegger, Adorno), ancient manuscript, bedtime story for post-human child, internal monologue of a tree, forgotten folk song lyrics, spy messages, protest chant, underwater civilization dialect, extinct animal conversation, dream sequence, poetic weather forecast, love letter to future generation, etc.
Be wildly creative and unexpected.
Output ONLY the transformation instruction, nothing else.`,
    userPromptTemplate: 'Generate a creative transformation instruction.'
  },
  language: {
    label: { en: 'Language Suggestion', bg: 'Езиково предложение', de: 'Sprach-Vorschlag', tr: 'Dil Önerisi', ko: '언어 제안', uk: 'Мовна пропозиція', fr: 'Suggestion de langue', es: 'Sugerencia de idioma' },
    systemPrompt: `You suggest a random language from around the world.
Choose from major world languages, regional languages, or less common languages.
Consider: European, Asian, African, Indigenous American, Pacific languages.
Output ONLY the language name in English, nothing else.
Example outputs: "Swahili", "Bengali", "Quechua", "Welsh", "Tagalog"`,
    userPromptTemplate: 'Suggest a random language.'
  }
}

/** Photo film type descriptions */
export const PHOTO_FILM_TYPES: Record<PhotoFilmType, string> = {
  random: '', // Will be selected at runtime
  'Kodachrome': 'a Kodachrome film slide',
  'Ektachrome': 'an Ektachrome film slide',
  'Portra 400': 'a Kodak Portra 400 color negative',
  'Portra 800': 'a Kodak Portra 800 color negative',
  'Ektar 100': 'a Kodak Ektar 100 color negative',
  'Fuji Pro 400H': 'a Fujifilm Pro 400H color negative',
  'Fuji Superia': 'a Fujifilm Superia color negative',
  'CineStill 800T': 'a CineStill 800T tungsten-balanced color negative',
  'Ilford HP5': 'an Ilford HP5 Plus black and white negative',
  'Ilford Delta 400': 'an Ilford Delta 400 black and white negative',
  'Ilford FP4': 'an Ilford FP4 Plus black and white negative',
  'Ilford Pan F': 'an Ilford Pan F Plus 50 black and white negative',
  'Ilford XP2': 'an Ilford XP2 Super chromogenic black and white negative',
  'Tri-X 400': 'a Kodak Tri-X 400 black and white negative'
}
