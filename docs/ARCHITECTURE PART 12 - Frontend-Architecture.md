# DevServer Architecture

**Part 12: Frontend Architecture**

---

> **Element structures:** Before building or changing any UI element structure (output box, card, canvas/board/stage, drag-resize, modal, bubble/tile, thread/anchor, selector, panel), consult `docs/ELEMENT_STRUCTURE_REGISTRY.md` first (no parallel element structures).


> **2026-08-12 — the transform mode is gone.** `text_transformation.vue`,
> `image_transformation.vue`, `multi_image_transformation.vue`, their hub
> `x2x_legacy.vue`, the pilot `t2i_flow.vue` and the dynamic loader
> `PipelineRouter.vue` were removed. `/x2x-flow` (`views/x2x_flow.vue`) does
> what they did. Their paths — `/text-transformation`, `/image-transformation`,
> `/multi-image-transformation`, `/x2x-legacy`, `/t2i-flow`,
> `/execute/:configId` — survive as redirects to `/x2x-flow`. Every passage
> below that names one of those files describes something that no longer
> exists; it is kept as the record of how the surface got here.

### Overview

**Status:** ✅ Complete migration (2025-10-28), v2.0.0-alpha.1 (2025-11-09)
**Architecture:** 100% Backend-abstracted - Frontend NEVER accesses ComfyUI directly

**SSE Streaming Status:** ✅ ACTIVE (safety badges and real-time generation progress)

The Frontend implements a clean separation between UI and Backend services, using Backend API exclusively for all operations.

### Core Components

#### 1. Config Browser (`config-browser.js`)

**Purpose:** Card-based visual selection of 37+ configs

```javascript
// Initialization
initConfigBrowser()
  → fetch('/pipeline_configs_metadata')
  → Backend returns: { configs: [...] }
  → Render cards grouped by category
```

**Features:**
- Card-based UI with icon, name, description
- Grouped by category (Bildgenerierung, Textverarbeitung, etc.)
- Visual selection feedback
- Difficulty stars
- Workshop badges

**Data Flow:**
```
User clicks card
  → selectConfig(configId)
  → Store in selectedConfigId
  → Visual feedback (selected class)
```

#### 2. Execution Handler (`execution-handler.js`)

**Purpose:** Backend-abstracted execution + media polling

**Execution Flow:**
```javascript
submitPrompt()
  → Validate: configId + promptText
  → Build payload: { schema, input_text, execution_mode, aspect_ratio }
  → POST /api/schema/pipeline/execute
  → Backend returns: {
      status: "success",
      final_output: "transformed text",
      media_output: {
        output: "prompt_id",
        media_type: "image"
      }
    }
  → Display transformed text
  → Start media polling
```

**Media Polling (NEW Architecture):**
```javascript
pollForMedia(promptId, mediaType)
  → Every 1 second:
    → GET /api/media/info/{promptId}
    → If 404: Continue polling (not ready yet)
    → If 200: Media ready!
      → displayMediaFromBackend(promptId, mediaInfo)
```

**Media Display:**
```javascript
displayImageFromBackend(promptId)
  → Create <img src="/api/media/image/{promptId}">
  → Backend fetches from ComfyUI internally
  → Returns PNG directly
```

#### 3. Application Initialization (`main.js`)

**Purpose:** Bootstrap application with new architecture

```javascript
initializeApp()
  → initSimpleTranslation()
  → loadConfig()
  → initConfigBrowser()  // NEW: Card-based UI
  → setupImageHandlers()
  → initSSEConnection()  // DEPRECATED: SSE streaming postponed
```

**Note:** SSE streaming was later reactivated (real-time safety badges) and then enhanced (real-time generation progress from ComfyUI/Diffusers backends). The `useGenerationStream` composable handles all SSE events: `connected`, `stage3_start`, `stage3_complete`, `blocked`, `stage4_start`, `generation_progress`, `complete`, `error`. Progress is now backend-driven (not simulated). ComfyUI sends denoising preview thumbnails via `generation_progress` events.

#### 4. SpriteProgressAnimation Component (`SpriteProgressAnimation.vue`)

**Purpose:** Visual progress feedback for pipeline execution (educational + entertaining)
**Target Audience:** Children and youth (iPad-optimized, lightweight)
**Status:** ✅ Implemented 2025-11-09

**Architecture:**
- Token processing metaphor: INPUT grid → PROCESSOR → OUTPUT grid
- 14x14 pixel grids (196 tokens)
- Pure CSS animations (no heavy libraries)
- 26 randomized pixel art images (robot, animals, food, space, etc.)

**Key Features:**
- **Neural Network Visualization:** 5 pulsating nodes + connection lines in processor box
- **Color Transformation:** Gradual color change visible during processing (40% of animation time)
- **Flight Animation:** Tokens fly from left edge to right edge through processor (0.6s per token)
- **Real-time Timer:** "generating X sec._" with blinking cursor
- **Progress Scaling:** Animation completes at 90% progress

**Technical Implementation:**
```typescript
// Progress calculation scaled to complete at 90%
const processedCount = computed(() => {
  const scaledProgress = Math.min(props.progress / 90, 1)
  return Math.floor(scaledProgress * totalTokens)
})

// Color transformation using CSS color-mix
@keyframes pixel-fly-from-left {
  42% { background-color: color-mix(in srgb, var(--from-color) 70%, var(--to-color) 30%); }
  50% { background-color: color-mix(in srgb, var(--from-color) 50%, var(--to-color) 50%); }
  58% { background-color: color-mix(in srgb, var(--from-color) 30%, var(--to-color) 70%); }
  68% { background-color: var(--to-color); }
}
```

**Performance:**
- CPU/GPU: Minimal (pure CSS transforms)
- Animation duration: 0.6s per pixel (balances visibility vs. smoothness)
- Memory: Timer cleanup in onUnmounted
- Responsive: Mobile @media queries for smaller screens

**Design Decision:**
Complex pixel-art sprites were rejected. The token processing metaphor was chosen for:
- Educational value (visualizes AI transformation)
- Simplicity (geometric shapes easier to animate)
- Conceptual alignment (matches GenAI token processing model)

### API Endpoints Used by Frontend

**Config Selection:**
```
GET /pipeline_configs_metadata
→ Returns: { configs: [{ id, name, description, category, ... }] }
```

**Execution:**
```
POST /api/schema/pipeline/execute
Body: { schema: "dada", input_text: "...", execution_mode: "eco" }
→ Returns: { status, final_output, media_output }
```

**Media Polling:**
```
GET /api/media/info/{prompt_id}
→ If ready: { type: "image", count: 1, files: [...] }
→ If not ready: 404
```

**Media Retrieval:**
```
GET /api/media/image/{prompt_id}
→ Returns: PNG file (binary)

GET /api/media/audio/{prompt_id}
→ Returns: MP3/WAV file (binary)

GET /api/media/video/{prompt_id}
→ Returns: MP4 file (binary) [future]
```

### Benefits of Backend Abstraction

1. **Generator Independence**
   - Frontend doesn't know about ComfyUI
   - Backend can switch to SwarmUI, Replicate, etc. without Frontend changes

2. **Media Type Flexibility**
   - Same polling logic for image, audio, video
   - Media type determined by Config metadata

3. **Clean Error Handling**
   - Backend validates and provides meaningful errors
   - Frontend just displays them

4. **Stateless Frontend**
   - No workflow state management
   - No complex polling logic
   - Simple request/response pattern

5. **Progress Indication**
   - SpriteProgressAnimation provides visual feedback
   - SSE streaming postponed for future enhancement
   - Backend handles complexity, frontend stays simple

### Legacy Components (Obsolete)

The whole pre-Vue client (`public_dev/` at the repository root and the built copy `devserver/public_dev/`) was removed on 2026-10-10 together with the routes only it called; the lists below describe it as it was. These files were marked `.obsolete` and no longer used:

- ❌ `workflow.js.obsolete` - Dropdown-based config selection
- ❌ `workflow-classifier.js.obsolete` - Runtime workflow classification
- ❌ `workflow-browser.js.obsolete` - Incomplete migration attempt
- ❌ `workflow-streaming.js.obsolete` - Legacy API with direct ComfyUI access
- ❌ `dual-input-handler.js.obsolete` - Replaced by execution-handler
- ⏸ `sse-connection.js` - SSE streaming infrastructure (postponed, may be reactivated later)

### File Structure

```
public_dev/
├── index.html                      # Main UI (no dropdown, only card container)
├── css/
│   ├── workflow-browser.css       # Card-based UI styles
│   └── ...
├── js/
│   ├── main.js                     # Application bootstrap (NEW architecture)
│   ├── config-browser.js           # Card-based config selection (NEW)
│   ├── execution-handler.js        # Backend-abstracted execution (NEW)
│   ├── ui-elements.js              # DOM element references
│   ├── ui-utils.js                 # UI helper functions
│   ├── simple-translation.js       # i18n for static UI
│   ├── image-handler.js            # Image upload handling
│   ├── sse-connection.js           # Real-time queue updates
│   └── *.obsolete                  # Legacy files (deprecated)
```

### Testing Checklist

When testing Frontend changes:

- [ ] Config browser loads 37+ configs
- [ ] Config selection works (visual feedback)
- [ ] Text input + config selection → valid payload
- [ ] POST /api/schema/pipeline/execute succeeds
- [ ] Transformed text displays correctly
- [ ] Media polling via /api/media/info works
- [ ] Image displays via /api/media/image works
- [ ] Audio/music displays correctly (if applicable)
- [ ] Error messages display user-friendly text

---

## Vue Frontend v2.0.0 (Property Selection Interface)

**Status:** ✅ Active (2025-11-21)
**Location:** `/public/ai4artsed-frontend/`
**Technology:** Vue 3 + TypeScript + Vite

### Architecture Overview

The Vue frontend implements a visual property-based configuration selection system, allowing users to explore AI art generation configs through an interactive bubble interface.

**Core Flow:**
```
PropertyQuadrantsView (Parent)
    ↓
PropertyCanvas (Unified Component)
    ↓
PropertyBubble (Category bubbles) + Config Bubbles (Configuration selection)
```

---

## Bubble Design System

**Status:** `PropertyCanvas.vue`, `PropertyCanvas_Vorlage.vue`, `MediumSelectionBubbles.vue`, `NoMatchState.vue`, `PipelineExecutionView.vue` and `HomeView.vue` were removed on 2026-10-10 as files without a router entry or an importer (code review finding S-095/S-102). `PropertyBubble.vue` remains, consumed by `InterceptionPresetOverlay.vue`. The sections below describe the removed canvas as it was built and are kept as the record of the design pattern.
**Canonical Implementation (historical):** `PropertyCanvas.vue` + `PropertyBubble.vue`
**Scope:** All phases of the application (current + future)

### Overview

The Bubble Design System is the foundational UI pattern for the AI4ArtsEd frontend. It uses circular "bubbles" as the primary interaction metaphor for both category selection (Phase 1) and configuration selection across all phases.

**Design Principles:**
1. **Consistency** - Same bubble metaphor across all phases
2. **Visual Hierarchy** - Size difference indicates importance (configs > categories)
3. **Accessibility** - High contrast, clear labels, touch-friendly sizes
4. **Responsiveness** - Percentage-based sizing scales with viewport
5. **Visual Polish** - Shadows, backdrop filters, smooth animations

---

### Visual Design Elements

#### 1. Category Bubbles (PropertyBubble component)

**Purpose:** Top-level property categories (semantics, aesthetics, arts, heritage, freestyle)

**Visual Specifications:**
- **Shape:** Circular (`border-radius: 50%`)
- **Size:** 12% of container width with `aspect-ratio: 1:1`
- **Background:** `rgba(20, 20, 20, 0.9)` (dark, semi-transparent)
- **Border:** `3px solid` with category-specific color
- **Content:** Emoji symbol + text label (centered)
- **Typography:**
  - Symbol: Large emoji (48px default)
  - Label: 14px, semi-bold, white

**States:**
- **Default:** Dark background, colored border, no glow
- **Hover:** `transform: scale(1.1)` with colored glow shadow
- **Selected:** Background filled with category color, elevated shadow

**Implementation Example:**
```vue
<div class="property-bubble selected"
     :style="{
       left: '50%',
       top: '50%',
       '--bubble-color': '#2196F3',
       '--bubble-shadow': '0 0 20px #2196F3'
     }">
  <span class="property-symbol">💬</span>
</div>
```

```css
.property-bubble {
  width: 12%;  /* Percentage of container */
  aspect-ratio: 1 / 1;
  border-radius: 50%;
  background: rgba(20, 20, 20, 0.9);
  border: 3px solid var(--bubble-color);
  box-shadow: var(--bubble-shadow);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.property-bubble:hover {
  transform: scale(1.1);
  box-shadow: 0 0 25px var(--bubble-color);
}

.property-bubble.selected {
  background: var(--bubble-color);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}
```

---

#### 2. Config Bubbles

**Purpose:** Individual configuration selection (dada, bauhaus, abstract-photo, etc.)

**Visual Specifications:**
- **Shape:** Circular (`border-radius: 50%`)
- **Size:** 18% of container width (larger than categories to show hierarchy)
- **Background:** White with config preview image
- **Image:** `background-size: cover`, `background-position: center`
- **Text Badge Overlay:**
  - Position: `bottom: 8%` of bubble
  - Background: `rgba(0, 0, 0, 0.85)`
  - Border-radius: `10px`
  - Backdrop-filter: `blur(8px)`
  - Max 2 lines with ellipsis overflow
  - Typography: 14px, font-weight 600, white color

**States:**
- **Default:** Preview image + text badge
- **Hover:** `transform: scale(1.1)` with elevated shadow
- **Selected:** (Navigation trigger - no persistent state)

**Implementation Example:**
```vue
<div class="config-bubble"
     :style="{
       left: '72%',
       top: '28%',
       backgroundImage: 'url(/config-previews/dada.png)'
     }"
     @click="selectConfiguration(config)">
  <div class="config-content">
    <div class="preview-image" />
    <div class="text-badge">Dada</div>
  </div>
</div>
```

```css
.config-bubble {
  width: 18%;  /* Larger than category bubbles */
  aspect-ratio: 1 / 1;
  border-radius: 50%;
  background: white;
  cursor: pointer;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  position: absolute;
  overflow: hidden;
}

.config-bubble:hover {
  transform: scale(1.1);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
}

.preview-image {
  width: 100%;
  height: 100%;
  background-size: cover;
  background-position: center;
  border-radius: 50%;
}

.text-badge {
  position: absolute;
  bottom: 8%;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(8px);
  color: white;
  padding: 8px 16px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  max-width: 80%;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
```

---

### Color System

**Category Colors:**
```javascript
const categoryColorMap: Record<string, string> = {
  semantics: '#2196F3',   // Blue 💬
  aesthetics: '#9C27B0',  // Purple 🪄
  arts: '#E91E63',        // Pink 🖌️
  heritage: '#4CAF50',    // Green 🌍
  freestyle: '#FFC107',   // Gold 🫵
}
```

**Usage:**
- Category bubble borders
- Selected state backgrounds
- Hover glow effects
- Color consistency across all UI elements

---

### Layout Pattern

#### X-Formation (Category Bubbles)

Categories are arranged in an X-pattern with Freestyle at the center:

```typescript
// Positions in percentage (0-100) relative to container
const categoryPositions: Record<string, CategoryPosition> = {
  freestyle: { x: 50, y: 50 },      // Center
  semantics: { x: 72, y: 28 },      // Top-right (45°)
  aesthetics: { x: 72, y: 72 },     // Bottom-right (135°)
  arts: { x: 28, y: 72 },           // Bottom-left (225°)
  heritage: { x: 28, y: 28 },       // Top-left (315°)
}
```

**Rationale:**
- Central Freestyle allows quick access to unrestricted configs
- Symmetric layout provides visual balance
- 45° angles maximize space utilization
- Percentage positioning ensures responsiveness

#### Circular Arrangement (Config Bubbles)

Configs appear in a circle around their selected category:

```typescript
const OFFSET_DISTANCE = 25  // Percentage units

const getConfigStyle = (config: ConfigMetadata, index: number) => {
  const categoryX = categoryPositions[selectedCategory.value].x
  const categoryY = categoryPositions[selectedCategory.value].y

  // Calculate angle based on config count
  const angle = (index / visibleConfigs.length) * 2 * Math.PI

  // Calculate position on circle
  const configX = categoryX + Math.cos(angle) * OFFSET_DISTANCE
  const configY = categoryY + Math.sin(angle) * OFFSET_DISTANCE

  return {
    left: `${configX}%`,
    top: `${configY}%`,
  }
}
```

**Rationale:**
- Configs visually connected to their parent category
- Equal spacing prevents overlap
- Dynamic calculation supports any number of configs
- Maintains spatial relationship across viewport sizes

---

### Responsive Container

**Container Sizing:**
```css
.cluster-wrapper {
  width: min(70vw, 70vh);
  height: min(70vw, 70vh);
  position: relative;
  margin: 0 auto;
}
```

**Rationale:**
- Square aspect ratio simplifies percentage calculations
- `min()` ensures container fits both portrait and landscape
- 70% viewport leaves room for header and margins
- All child bubbles use percentage positioning relative to this container

---

### Interaction Design

#### Touch Support

All bubbles support both mouse and touch events:

```typescript
<div
  @click="handleClick"
  @touchstart.prevent="selectConfiguration(config)"
>
```

**Considerations:**
- Touch targets minimum 44x44px (iOS/Android guidelines)
- Prevents default touch behavior to avoid scrolling
- Distinguishes tap from drag events

#### Smooth Transitions

All state changes use consistent timing:

```css
transition: transform 0.3s ease, box-shadow 0.3s ease;
```

**Transition Types:**
- **Transform:** Scale effects on hover/select
- **Box-shadow:** Glow effects for visual feedback
- **Opacity:** Fade-in/out for config bubbles

**Config Bubble Transitions:**
```vue
<transition-group name="config-fade">
  <!-- Config bubbles -->
</transition-group>
```

```css
.config-fade-enter-active,
.config-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.config-fade-enter-from {
  opacity: 0;
  transform: scale(0.8);
}

.config-fade-leave-to {
  opacity: 0;
  transform: scale(0.8);
}
```

#### XOR Selection Logic

Only ONE category can be selected at a time:

```typescript
const handlePropertyToggle = (property: string) => {
  if (selectedCategory.value === property) {
    // Deselect if clicking same category
    selectedCategory.value = null
  } else {
    // Select new category (auto-deselects previous)
    selectedCategory.value = property
  }
}
```

**Rationale:**
- Simplifies user mental model (one choice at a time)
- Reduces UI complexity (no multi-select state management)
- Matches pedagogical flow (progressive refinement)

---

### Implementation Reference

**Canonical Files:**
- `/public/ai4artsed-frontend/src/components/PropertyCanvas.vue` - Complete implementation (removed 2026-10-10)
- `/public/ai4artsed-frontend/src/components/PropertyBubble.vue` - Category bubble component
- `/public/ai4artsed-frontend/src/assets/main.css` - Global bubble styles

**Key Code Sections:**

1. **Category Bubble Component** (`PropertyBubble.vue`)
   - Lines 59-65: Style computation with CSS variables
   - Lines 2-14: Template structure with percentage positioning

2. **Config Bubble Layout** (`PropertyCanvas.vue`)
   - Lines 22-40: Config bubble rendering with preview images
   - Lines 145-165: Circular positioning calculation
   - Lines 92-97: Category color mapping

3. **Container Setup** (`PropertyCanvas.vue`)
   - Lines 2-42: Template with cluster-wrapper container
   - CSS: `.cluster-wrapper` responsive sizing

---

### Future Application

This design system should be applied to:

**Phase 2: Creative Flow**
- Bubble-based workflow step selection
- Same size hierarchy (categories > steps)
- Maintain color consistency

**Phase 3: Pipeline Execution**
- Progress visualization using bubble metaphor
- Stage completion indicators (filled bubbles)
- Error states (red border/glow)

**Phase 4: Output Gallery**
- Generated media as bubbles (circular thumbnails)
- Hover for preview, click for full view
- Maintain text badge overlay pattern

**General Guidelines:**
- Always use circular (`border-radius: 50%`) for bubbles
- Maintain size hierarchy (larger = more important)
- Use percentage positioning for responsiveness
- Apply consistent transition timings (0.3s ease)
- Follow category color system
- Text badges always at 8% from bottom with backdrop-filter

---

### Key Components

#### 1. PropertyCanvas.vue (Unified Component)

**Purpose:** Displays category bubbles and configuration bubbles in a single coordinate system

**Location:** `/public/ai4artsed-frontend/src/components/PropertyCanvas.vue` (removed 2026-10-10)

**Architecture Decision (2025-11-21, Commits e266628 + be3f247):**

Previously split into two separate components (PropertyCanvas + ConfigCanvas), which caused coordinate system mismatches. The two components used different positioning logic, resulting in config bubbles appearing in incorrect locations.

**Solution:** Merged ConfigCanvas functionality into PropertyCanvas, creating a single unified component with one coordinate system.

**Key Features:**
- **Unified Coordinate System:** All bubbles (category + config) use percentage-based positioning within the same container
- **Responsive Sizing:** Container dimensions calculated as `min(70vw, 70vh)` for consistent scaling
- **X-Formation Layout:** 5 category bubbles arranged in X-pattern with Freestyle in center
- **Dynamic Config Display:** Config bubbles appear in circular arrangement around selected category
- **Touch Support:** iPad/mobile-friendly touch events
- **Config Preview Images:** Displays preview images from `/config-previews/{config-id}.png`
- **Text Badge Overlay:** Black semi-transparent badge at 8% from bottom (matching ConfigTile design)

**Coordinate System:**
```typescript
// All positions in percentage (0-100) relative to cluster-wrapper
const categoryPositions: Record<string, CategoryPosition> = {
  freestyle: { x: 50, y: 50 },      // Center
  semantics: { x: 72, y: 28 },       // Top-right (45°)
  aesthetics: { x: 72, y: 72 },      // Bottom-right (135°)
  arts: { x: 28, y: 72 },            // Bottom-left (225°)
  heritage: { x: 28, y: 28 },        // Top-left (315°)
}
```

**Config Bubble Positioning:**
```typescript
// Configs arranged in circle around their parent category
const angle = (index / visibleConfigs.length) * 2 * Math.PI
const configX = categoryX + Math.cos(angle) * OFFSET_DISTANCE
const configY = categoryY + Math.sin(angle) * OFFSET_DISTANCE
```

**Styling:**
- **Category Bubbles:** 100px diameter, glassmorphic effect, category-specific colors
- **Config Bubbles:** 240px diameter, preview image background, text badge overlay
- **Transitions:** Smooth fade-in/out for config bubbles (config-fade transition)
- **Hover Effects:** Scale transforms on hover (category: 1.05, config: 1.08)

**Bug Fixed (Commit e266628):**
```
BEFORE (Two Components):
PropertyCanvas → percentage positioning
ConfigCanvas → pixel positioning + different center calculation
Result: Configs appeared top-right, not around categories

AFTER (Unified):
PropertyCanvas → single percentage-based coordinate system
Result: Configs correctly positioned around categories
```

#### 2. PropertyBubble.vue (Category Bubble Component)

**Purpose:** Individual category bubble with emoji symbol and color

**Location:** `/public/ai4artsed-frontend/src/components/PropertyBubble.vue`

**Features:**
- Percentage-based absolute positioning
- Draggable within container bounds
- Selection state management
- Emoji symbols with category colors
- Glassmorphic styling

**Props:**
- `property: string` - Category identifier (e.g., "semantics")
- `color: string` - Hex color for category
- `is-selected: boolean` - Selection state
- `x: number` - X position in percentage (0-100)
- `y: number` - Y position in percentage (0-100)
- `symbol-data: SymbolData` - Emoji and metadata

#### 3. PropertyQuadrantsView.vue (removed 2026-09-22)

**Purpose:** Container view managing layout and responsive sizing

**Removed:** the view hung on no route; `/select` has not existed for a long time. Perspectives are picked on the flow surface (`views/x2x_flow.vue`).

**Responsibilities:**
- Header with title and "Clear Selection" button
- ResizeObserver for responsive canvas dimensions
- Props passing to PropertyCanvas
- Navigation to pipeline execution

**Layout:**
```vue
<div class="property-view">
  <header>
    <h1>Konfiguration auswählen</h1>
    <button v-if="hasSelection">Auswahl löschen</button>
  </header>
  <div class="canvas-area">
    <PropertyCanvas :selected-properties="selectedProperties" />
  </div>
</div>
```

#### 4. ConfigTile.vue (removed 2026-09-22)

**Purpose:** Alternative grid-based config selection (not used in PropertyCanvas)

**Removed:** commit 733f4250 — the file hung on no routed view; `PerspectiveBubble.vue` carries the preview + name badge design on the flow surface.

**Note:** ConfigTile is used in list/grid views, while PropertyCanvas uses inline config bubbles. Both share the same preview image + text badge design pattern.

### Design Patterns

#### Config Preview Images (Commit be3f247)

All config bubbles display preview images with consistent styling:

```vue
<div class="config-bubble">
  <div class="config-content">
    <!-- Background image -->
    <div class="preview-image"
         :style="{ backgroundImage: `url(/config-previews/${config.id}.png)` }">
    </div>

    <!-- Text badge overlay -->
    <div class="text-badge">
      {{ config.name[currentLanguage] }}
    </div>
  </div>
</div>
```

**Styling:**
```css
.preview-image {
  width: 100%;
  height: 100%;
  background-size: cover;
  background-position: center;
  border-radius: 50%;
}

.text-badge {
  position: absolute;
  bottom: 8%;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(8px);
  color: white;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
}
```

**Removed:** Fallback letter placeholder system (previously used when images were unavailable)

#### XOR Selection Logic

Only ONE category can be selected at a time:

```typescript
const handlePropertyToggle = (property: string) => {
  if (selectedCategory.value === property) {
    // Deselect if clicking same category
    selectedCategory.value = null
  } else {
    // Select new category (auto-deselects previous)
    selectedCategory.value = property
  }
}
```

#### Progressive Disclosure Scrolling Pattern

**Purpose:** Didactic guidance through multi-stage creative workflows

**Pedagogical Principle:**
The interface reveals complexity progressively, guiding users through distinct phases of the creative-technical process. Each scroll marks a **conceptual transition**, preventing cognitive overload while maintaining user agency.

**Implementation:** `text_transformation.vue` (2025-11-29)

**The Three Phases:**

1. **Phase 1 (Scroll1)**: After interception → Reveal media category selection
   ```javascript
   // In runInterception() after success
   await nextTick()
   scrollDownOnly(categorySectionRef.value, 'end')
   ```

2. **Phase 2 (Scroll2)**: After category selection → Reveal model options and generation controls
   ```javascript
   // In selectCategory()
   await nextTick()
   scrollDownOnly(categorySectionRef.value, 'start')
   ```

3. **Phase 3 (Scroll3)**: After generation start → Focus on output/animation
   ```javascript
   // In startGeneration()
   await nextTick()
   setTimeout(() => scrollToBottomOnly(), 150)
   ```

**Key Functions:**

```javascript
// Helper: Only scroll DOWN, never back up (forward progression)
function scrollDownOnly(element: HTMLElement | null, block: ScrollLogicalPosition = 'start') {
  if (!element) return
  const rect = element.getBoundingClientRect()
  const targetTop = block === 'start' ? rect.top : rect.bottom - window.innerHeight
  // Only scroll if target is below current viewport
  if (targetTop > 0) {
    element.scrollIntoView({ behavior: 'smooth', block })
  }
}

// Scroll container to bottom (for output phase)
function scrollToBottomOnly() {
  // Scroll the container (not window, because container is position:fixed)
  if (mainContainerRef.value) {
    mainContainerRef.value.scrollTo({
      top: mainContainerRef.value.scrollHeight,
      behavior: 'smooth'
    })
  }
}
```

**Critical Implementation Detail:**
The `.text-transformation-view` uses `position: fixed; inset: 0;`, making it the viewport. Therefore, scrolling must target the **container** (`.phase-2a` / `mainContainerRef`), NOT `window`.

**Design Rule:**
Scrolling only moves **downward**, never backward → reinforces forward progression through the creative pipeline.

**When to Use This Pattern:**
- Multi-stage pedagogical workflows
- Complex interfaces requiring guided learning
- Processes where users benefit from step-by-step revelation
- Educational tools where cognitive load management is critical

**Educational Outcome:**
Users learn the workflow structure through **spatial navigation** - the physical act of scrolling becomes part of the learning experience.

### State Management

**Store:** `/public/ai4artsed-frontend/src/stores/configSelection.ts`

**Managed State:**
- `categories: string[]` - Available property categories
- `availableConfigs: ConfigMetadata[]` - All configurations
- `selectedProperties: string[]` - Currently selected categories (XOR: max 1)
- `selectedConfigId: string | null` - Currently selected configuration

### Removed Components

**ConfigCanvas.vue** (reference removed - commit e266628; file removed 2026-09-22 - commit 733f4250)
- **Reason:** Coordinate system mismatch with PropertyCanvas
- **Functionality:** Merged into PropertyCanvas
- **Files Affected:**
  - Deleted: `src/components/ConfigCanvas.vue` (only in 733f4250 — e266628 left the file in the tree)
  - Modified: `src/components/PropertyCanvas.vue` (integrated ConfigCanvas logic)
  - Modified: `src/views/PropertyQuadrantsView.vue` (removed ConfigCanvas reference)

### Navigation Flow

```
PropertyQuadrantsView
  ↓ User clicks category bubble
PropertyCanvas updates → configs appear
  ↓ User clicks config bubble
selectConfiguration(config)
  ↓
router.push(`/pipeline-execution/${config.id}`)
  ↓
PipelineExecutionView (config loaded, ready for prompt input)
```

### Known Issues & Solutions

**Issue 1: Config Bubbles Appearing Top-Right (RESOLVED)**
- **Cause:** Separate PropertyCanvas + ConfigCanvas components with different coordinate systems
- **Solution:** Merged into unified PropertyCanvas with single coordinate system (commit e266628)

**Issue 2: Centering Problems (ACTIVE - See `docs/PropertyCanvas_Problem.md`)**
- **Status:** Under investigation
- **Problem:** Category bubbles not perfectly centered in viewport
- **Affected File:** `PropertyCanvas.vue` positioning logic

### File Structure

```
public/ai4artsed-frontend/
├── src/
│   ├── components/
│   │   ├── PropertyCanvas.vue        # Unified canvas (categories + configs) — removed 2026-10-10
│   │   ├── PropertyBubble.vue        # Individual category bubble
│   │   └── PropertyBubble.vue.archive # Backup of previous version — removed 2026-10-10
│   ├── views/
│   │   ├── text_transformation.vue   # Text→Image/Video pipeline (gold standard pattern) — removed 2026-10-10
│   │   ├── music_generation.vue      # Music Gen V1: dual input (lyrics+tags), single refine button
│   │   ├── music_generation_v2.vue   # Music Gen V2: Lyrics Workshop + Sound Explorer (hidden workbench)
│   ├── stores/
│   │   ├── configSelection.ts        # Config selection state
│   │   └── userPreferences.ts        # Language & preferences
│   ├── assets/
│   │   └── main.css                  # Global styles
│   └── router/
│       └── index.ts                  # Vue Router config
└── public/
    └── config-previews/              # Config preview images
        ├── bauhaus.png
        ├── dada.png
        └── ...
```

### Music Generation Views

Two Vue pages for HeartMuLa music generation, serving different purposes:

#### music_generation.vue (V1 — Pedagogical)
**Route:** `/music-generation` (visible in navigation)
**Pattern:** Dual input (lyrics + tags) → single "Refine" button → dual SSE streams → generate

```
[Lyrics Input]  [Tags Input]
       >>> Refine Lyrics & Tags >>>
[Refined Lyrics] [Refined Tags]
       [Model Selection] [Audio Length]
       >>> Generate Music >>>
       [Audio Player]
```

**Interception configs:** none; `lyrics_refinement` and `tags_generation` were struck on 2026-10-10, no code named them
**Generation:** POST to `/api/schema/pipeline/interception` with `schema: 'heartmula'`

(The music views were removed in `faa8df82`. The song runs in the Flow, `x2x_flow.vue`
`runMusic`, on `/api/schema/pipeline/generation` with `secondary_text` since
2026-10-06; see PART 08, HeartMuLa.)

#### music_generation_v2.vue (V2 — Hidden Workbench)
**Route:** `/music-generation-v2` (NOT in navigation, direct URL only)
**Pattern:** Two independent creative processes + parameter controls + batch mode

```
LYRICS WORKSHOP
  [Input] → [Thema→Lyrics] [Lyrics verfeinern] → [Streaming Result]

SOUND EXPLORER
  [Suggest from Lyrics]
  Genre:  [pop][rock][jazz]...     ← MusicTagSelector.vue (8 dimensions)
  Timbre: [warm][bright]...
  ...
  Tags: jazz,warm,saxophone,romantic

PARAMETERS
  [Audio Length] [Temperature] [Top-K] [CFG Scale]
  [-] 3x [+] >>> Generate Music >>>
  [Audio Player]
```

**Key component:** `MusicTagSelector.vue` — 8-dimension chip selector with per-dimension colors, toggle, live tag preview
**Interception configs:** none; `lyrics_from_theme`, `lyrics_refinement` and `tag_suggestion_from_lyrics` were struck on 2026-10-10, no code named them
**Batch mode:** Sequential N runs with same parameters, progress shown as "2/5"

### Testing Checklist (Vue Frontend)

When testing PropertyCanvas changes:

- [ ] All 5 category bubbles display correctly in X-formation
- [ ] Freestyle bubble centered in viewport
- [ ] Category selection works (XOR: only one selected)
- [ ] Config bubbles appear only when category selected
- [ ] Config bubbles positioned correctly around selected category
- [ ] Config preview images load correctly
- [ ] Text badges display config names
- [ ] Config selection navigates to pipeline execution
- [ ] Touch events work on iPad
- [ ] Responsive sizing works across viewport sizes
- [ ] "Clear Selection" button appears/disappears correctly

---

## Frontend API Patterns

### ⚠️ CRITICAL: Pipeline API Usage

#### Rule 1: Always Use Config ID for Schema Parameter

When calling pipeline endpoints (`/pipeline/stage2`, `/pipeline/execute`, `/pipeline/stage3-4`), the `schema` parameter must be the **config ID**, never the pipeline name.

**Correct Pattern:**
```typescript
// Phase 2 Youth Flow - runInterception()
const response = await axios.post('/api/schema/pipeline/stage2', {
  schema: pipelineStore.selectedConfig?.id || 'overdrive',  // ✅ Config ID
  input_text: inputText.value,
  context_prompt: contextPrompt.value || undefined,
  user_language: 'de',
  execution_mode: 'eco',
  safety_level: 'youth',
  output_config: selectedConfig.value
})

// Phase 2 Youth Flow - executePipeline()
const response = await axios.post('/api/schema/pipeline/execute', {
  schema: pipelineStore.selectedConfig?.id || 'overdrive',  // ✅ Config ID
  input_text: inputText.value,
  interception_result: interceptionResult.value,
  context_prompt: contextPrompt.value || undefined,
  user_language: 'de',
  execution_mode: 'eco',
  safety_level: 'youth',
  output_config: selectedConfig.value
})
```

**Wrong Pattern (NEVER DO THIS):**
```typescript
// ❌ WRONG - Using pipeline name instead of config ID
schema: pipelineStore.selectedConfig?.pipeline  // Causes 404 error!
```

**Why This Matters:**

1. **Config Structure:**
   ```json
   {
     "id": "bauhaus",                     // ← Use for 'schema' parameter
     "pipeline": "text_transformation",   // ← NEVER use for 'schema'
     "version": "1.0",
     "category": "artistic"
   }
   ```

2. **Backend File Loading:**
   - Backend uses `schema` to load: `schemas/configs/{schema}.json`
   - Example: `schema: "bauhaus"` → Loads `bauhaus.json` ✅
   - Example: `schema: "text_transformation"` → Looks for `text_transformation.json` (doesn't exist) → 404 ❌

3. **Silent Failure:**
   - Error appears in browser console
   - Backend logs show nothing (request never reaches route handler)
   - FastAPI returns 404 before route execution

**Debugging Clue:** If you see 404 errors in browser console but backend logs are silent, suspect wrong `schema` parameter value.

**Bug History:** 2025-11-23 - Youth Flow sent `config.pipeline` instead of `config.id`, causing production-breaking 404 errors.

**Affected Files:**
- `/public/ai4artsed-frontend/src/views/Phase2YouthFlowView.vue` (lines 403, 460) - FIXED ✅ (removed 2026-10-10)
- `/public/ai4artsed-frontend/src/views/PipelineExecutionView.vue` (line 250) - Already correct ✅ (removed 2026-10-10)
- All future views making pipeline API calls

**Code Review Checklist:**
- [ ] All `schema:` parameters use `pipelineStore.selectedConfig?.id`
- [ ] No `schema:` parameters use `pipelineStore.selectedConfig?.pipeline`
- [ ] Fallback values use valid config IDs (e.g., `'overdrive'`)

---

### Reusable Components

#### MediaOutputBox Component

**Status:** ✅ Implemented (2025-12-15, commit 8e8e3e0)
**Location:** `/public/ai4artsed-frontend/src/components/MediaOutputBox.vue`

**Purpose:** Unified, reusable template for displaying generated media output across all views (text_transformation, image_transformation, future audio/video views).

**Problem Solved:**
- **Before:** ~300 lines of duplicated output box code in each view
- **After:** Single 515-line component, used with 19 lines per view

**Features:**

1. **Complete Action Toolbar**
   - ⭐ Save (stub, disabled)
   - 🖨️ Print (opens print dialog)
   - ➡️ Forward (re-transform/send to I2I)
   - 💾 Download (with timestamped filename)
   - 🔍 Analyze (calls `/api/image/analyze`)

2. **3 States**
   - **Empty:** Inactive toolbar visible, no media
   - **Generating:** Edutainment animation + real-time progress (+ denoising preview for ComfyUI)
   - **Final:** Active toolbar + media display

3. **All Media Types**
   - Image (with click-to-fullscreen)
   - Video (with HTML5 controls)
   - Audio (with HTML5 controls)
   - 3D Model (placeholder icon)
   - Unknown (generic fallback)

4. **Image Analysis**
   - Expandable section below output
   - Analysis text + reflection prompts
   - Close button

5. **Responsive Design**
   - Desktop: Vertical toolbar on right
   - Mobile (<768px): Horizontal toolbar below media

**Props Interface:**

```typescript
interface Props {
  outputImage: string | null       // Media URL
  mediaType: string                // 'image', 'video', 'audio', 'music', '3d'
  isExecuting: boolean             // Generating state
  progress: number                 // 0-100 for progress bar (real backend data)
  estimatedSeconds?: number        // Estimated duration (for edutainment animation pacing)
  previewImage?: string | null     // Denoising preview (base64 data URI, ComfyUI only)
  isAnalyzing?: boolean            // Analyzing state (button shows ⏳)
  showAnalysis?: boolean           // Show/hide analysis section
  analysisData?: AnalysisData | null  // Analysis results
  forwardButtonTitle?: string      // Custom tooltip for ➡️ button
  runId?: string | null            // For favorites support
  isFavorited?: boolean            // Favorite state
}

interface AnalysisData {
  analysis: string
  reflection_prompts: string[]
  insights: string[]
  success: boolean
}
```

**Events:**

```typescript
defineEmits<{
  'save': []                       // Save button clicked
  'print': []                      // Print button clicked
  'forward': []                    // Forward/re-transform clicked
  'download': []                   // Download button clicked
  'analyze': []                    // Analyze button clicked
  'image-click': [imageUrl: string]  // Image clicked (fullscreen)
  'close-analysis': []             // Close analysis section
}>()
```

**Critical Feature: Autoscroll Support**

The component exposes its internal `<section>` element via `defineExpose()` for autoscroll functionality:

```typescript
// MediaOutputBox.vue
const sectionRef = ref<HTMLElement | null>(null)
defineExpose({ sectionRef })
```

Parent views access it:
```typescript
// text_transformation.vue, image_transformation.vue
const pipelineSectionRef = ref()

// Autoscroll usage
scrollDownOnly(pipelineSectionRef.value?.sectionRef, 'start')
```

**Usage Example:**

```vue
<script setup>
import MediaOutputBox from '@/components/MediaOutputBox.vue'

const pipelineSectionRef = ref()
const outputImage = ref(null)
const outputMediaType = ref('image')
const isPipelineExecuting = ref(false)
const generationProgress = ref(0)
const isAnalyzing = ref(false)
const showAnalysis = ref(false)
const imageAnalysis = ref(null)

function saveMedia() {
  alert('Speichern-Funktion kommt bald!')
}

function printImage() {
  if (!outputImage.value) return
  const printWindow = window.open('', '_blank')
  if (printWindow) {
    printWindow.document.write(`
      <html><head><title>Druck: Bild</title></head>
      <body style="margin:0;display:flex;justify-content:center;align-items:center;height:100vh;">
        <img src="${outputImage.value}" style="max-width:100%;max-height:100%;" onload="window.print();window.close()">
      </body></html>
    `)
    printWindow.document.close()
  }
}

function sendToI2I() {
  // Re-transform: use output as new input
  uploadedImage.value = outputImage.value
  outputImage.value = null
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function downloadMedia() {
  const response = await fetch(outputImage.value)
  const blob = await response.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const timestamp = new Date().toISOString().slice(0, 19).replace(/[:]/g, '-')
  a.download = `ai4artsed_${timestamp}.png`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
}

async function analyzeImage() {
  isAnalyzing.value = true
  const response = await fetch('/api/image/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_url: outputImage.value,
      context: contextPrompt.value || ''
    })
  })
  const data = await response.json()
  if (data.success) {
    imageAnalysis.value = data
    showAnalysis.value = true
  }
  isAnalyzing.value = false
}

function showImageFullscreen(imageUrl) {
  // Implementation for fullscreen modal
}
</script>

<template>
  <MediaOutputBox
    ref="pipelineSectionRef"
    :output-image="outputImage"
    :media-type="outputMediaType"
    :is-executing="isPipelineExecuting"
    :progress="generationProgress"
    :is-analyzing="isAnalyzing"
    :show-analysis="showAnalysis"
    :analysis-data="imageAnalysis"
    forward-button-title="Weiterreichen zu Bild-Transformation"
    @save="saveMedia"
    @print="printImage"
    @forward="sendToI2I"
    @download="downloadMedia"
    @analyze="analyzeImage"
    @image-click="showImageFullscreen"
    @close-analysis="showAnalysis = false"
  />
</template>
```

**Implementation Notes:**

1. **Action Handler Customization:** Each view implements its own action handlers (e.g., `sendToI2I()` in text_transformation forwards to image_transformation, while in image_transformation it re-uses the output as new input).

2. **Forward Button Semantics:**
   - `text_transformation.vue`: "Weiterreichen zu Bild-Transformation" (send to I2I)
   - `image_transformation.vue`: "Erneut Transformieren" (re-transform)

3. **Scoped CSS:** All styles are scoped to the component, no global CSS pollution.

4. **TypeScript Typed:** Full type safety with TypeScript interfaces for props and events.

5. **Accessibility:** All buttons have meaningful `title` attributes for tooltips.

**Views Using MediaOutputBox:**
- `/public/ai4artsed-frontend/src/views/text_transformation.vue`
- `/public/ai4artsed-frontend/src/views/image_transformation.vue`

**Code Reduction Impact:**
- **text_transformation.vue:** ~505 lines removed (170 HTML + 300 CSS + 35 redundant methods)
- **image_transformation.vue:** ~293 lines reduced (150 HTML + 200 CSS, added action methods)
- **Total:** ~300 lines of duplicate code eliminated

#### MediaInputBox Component

**Status:** ✅ Implemented; sketch support added later and refactored to component level
**Location:** `/public/ai4artsed-frontend/src/components/MediaInputBox.vue`

**Purpose:** Unified input component for all pipeline inputs — text, image upload, and sketch drawing. Used across all pipeline views for consistent input handling, safety checks, SSE streaming, and translation.

**Input Modes:**

1. **Text** (`inputType="text"`): Textarea with auto-resize, blur/paste safety checks, Union Jack translate button, SSE streaming support
2. **Image** (`inputType="image"`): `ImageUploadWidget` for file upload. When `allowSketch` is `true`, an internal toggle lets users switch between upload and sketch mode.
3. **Sketch** (internal, via `allowSketch`): `SketchCanvas` for freehand drawing — pen/eraser, 3 brush sizes, undo, exports PNG to same upload API. Same `image-uploaded`/`image-removed` event contract as upload.

**Props Interface (key props):**

```typescript
interface Props {
  icon: string                    // Header icon (emoji or SVG keyword)
  label: string                   // Header label (i18n)
  value: string                   // v-model:value for text, preview URL for image
  inputType?: 'text' | 'image'   // Input mode (default: 'text')
  allowSketch?: boolean           // Show upload/sketch toggle for image inputs (default: false)
  initialImage?: string           // Pre-loaded image URL for ImageUploadWidget
  showTranslate?: boolean         // Show Union Jack translate button (default: true)
  showPresetButton?: boolean      // Show interception preset button (default: false)
  enableStreaming?: boolean        // Enable SSE streaming (default: false)
  streamUrl?: string              // SSE endpoint URL
  streamParams?: Record<string, string | boolean>
  // ... plus isEmpty, isRequired, isFilled, isLoading, showCopy, showPaste, showClear, etc.
}
```

**Sketch Toggle Architecture:**

Previously, `'sketch'` was a third value of the external `inputType` prop — pages had to manage the upload/sketch toggle themselves. This was refactored:
- `inputType` union is now `'text' | 'image'` only
- `allowSketch: boolean` prop controls whether the toggle appears
- Internal `sketchMode: ref(false)` manages the state
- Pages just pass `:allow-sketch="true"` — zero toggle logic needed

**Pedagogical rationale:** Sketch is not an alternative input *type* but an alternative input *modality* within image input. Upload = "Was habe ich?" (material-oriented). Sketch = "Was stelle ich mir vor?" (imagination-oriented). Both equally valid for img2img pipelines.

**Views Using MediaInputBox:**
- `image_transformation.vue` — 1 image (with sketch), 1 text context
- `multi_image_transformation.vue` — 3 images (all with sketch), 1 text context
- `crossmodal_lab.vue` — 2 images (both with sketch), multiple text prompts
- `text_transformation.vue` — text input + text context
- `surrealizer.vue`, `music_generation.vue`, and others — text inputs

**Scalability:** Future views (video_transformation, audio_transformation, etc.) can reuse this component without any code duplication.

---


#### FooterGallery Component

**Status:** ✅ Implemented (2026-01-22/23)
**Location:** `/public/ai4artsed-frontend/src/components/FooterGallery.vue`

**Purpose:** Persistent favorites bar at bottom of viewport for quick access to bookmarked generations across all views.

**Kernidee:**

Die Favleiste ist a) eine Ablage. Ein Thema oder ein Gegenstand wird dort abgelegt,
um es oder anderes mit anderen Instrumenten der Plattform auf andere Weise zu
bearbeiten, zum Beispiel verschiedene Versionen einer Bearbeitung zu erstellen, wie
es für künstlerische Prozesse typisch ist, diese zu vergleichen und wieder
aufzugreifen. Sie ist b) der Ort, an dem ausgewählte komplexe digitale Objekte mit
den anderen im Workshop geteilt werden. Geteilt werden Bild- und Medienresultate und
ebenso Prompts, so dass ein kollektiver vernetzter Kreativ- oder Wissensprozess
direkt auf der Plattform stattfinden kann.

Sharing (b) is what the `Meine` / `Alle` switch in the bar's header does: in `global`
view the bar holds every device's kept runs, and the server refuses a foreign delete
(`favorites_routes._may_change`). A favourite is a RUN, so what is shared carries its
prompt, its values and its origin, and a run dropped into an input field hands the
field what fits (`MediaInputBox.vue:741-743`, `:757-783`).

**Features:**

1. **Fixed Footer Position**
   - Always visible at bottom of viewport
   - Expandable thumbnail gallery
   - Persists across page navigation

2. **One gesture on the plate** (since 2026-08-30, commit 0ed41975)
   - Tap opens the whole run in MediaFullscreen: piece, origin, time, prompt,
     values, and the platform's own row of things one can do with a made thing
   - Removing sits on the plate itself (RemoveBadge), on one's own favourites only
   - The three per-plate buttons this section used to list are gone: two of them
     could not say what they would do at 100 px, and the third promised a restore
     most runs cannot give. A way back is offered only where an instrument can
     really take its run back.

3. **Reactive Store-Based Restore**
   - Uses Pinia store (`favorites.ts`) instead of sessionStorage
   - Watcher pattern for cross-component communication
   - No timing issues with page navigation

**Architecture:**

```
┌─────────────────────────────────────────────────────────┐
│                      App.vue                             │
│  ┌─────────────────────────────────────────────────┐    │
│  │                 router-view                      │    │
│  │  (text_transformation, image_transformation)     │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │               FooterGallery.vue                  │    │
│  │  [thumb] [thumb] [thumb]  [↩️] [📋] [❌]          │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

**Store Integration:**

```typescript
// favorites.ts (Pinia Store)
export interface FavoriteItem {
  run_id: string
  media_type: 'image' | 'video' | 'audio' | 'music'
  thumbnail_url: string
  created_at: string
}

export interface RestoreData {
  run_id: string
  input_text?: string
  context_prompt?: string
  transformed_text?: string
  translation_en?: string
  models_used?: ModelsUsed
  media_outputs: MediaOutput[]
  target_view: string
}

// State
const favorites = ref<FavoriteItem[]>([])
const pendingRestoreData = ref<RestoreData | null>(null)

// Actions
function setRestoreData(data: RestoreData | null) {
  pendingRestoreData.value = data
}
```

**Restore Pattern:**

```typescript
// FooterGallery.vue - triggers restore
async function handleRestore(favorite: FavoriteItem) {
  const restoreData = await favoritesStore.getRestoreData(favorite.run_id)
  favoritesStore.setRestoreData(restoreData)
  router.push(`/${restoreData.target_view}`)
}

// text_transformation.vue - consumes restore
watch(() => favoritesStore.pendingRestoreData, (data) => {
  if (!data) return
  inputText.value = data.input_text || ''
  contextPrompt.value = data.context_prompt || ''
  interceptionResult.value = data.transformed_text || ''
  favoritesStore.setRestoreData(null) // Clear after consuming
}, { immediate: true })
```

**CSS Considerations:**

All transformation views add `padding-bottom: 120px` to ensure content isn't hidden behind the fixed footer:

```css
.text-transformation-view,
.image-transformation-view {
  padding-bottom: 120px; /* Space for FooterGallery */
}
```

**Integration:**

```vue
<!-- App.vue -->
<template>
  <div id="app">
    <AppHeader />
    <router-view />
    <FooterGallery />  <!-- Fixed at bottom, always visible -->
  </div>
</template>
```

**Related Files:**
- `src/stores/favorites.ts` - Pinia store for favorites state
- `devserver/my_app/routes/favorites_routes.py` - REST API endpoints
- `src/views/text_transformation.vue` - Restore watcher implementation
- `src/views/image_transformation.vue` - Restore watcher implementation

---

#### ChatOverlay Component (Träshy)

**Status:** ✅ Implemented
**Location:** `/public/ai4artsed-frontend/src/components/ChatOverlay.vue`

**Purpose:** Living, context-aware chat assistant ("Träshy") providing contextual help and guidance for AI4ArtsEd workflows.

**Pädagogisches Konzept:**

Träshy ist nicht nur ein Chat-Button, sondern ein **aktiver Begleiter**:
- **Präsenz**: Immer sichtbar, sanft animiert ("Ich bin da")
- **Aufmerksamkeit**: Folgt dem Fokus des Users ("Ich sehe was du tust")
- **Lebendigkeit**: Atmet und schwebt ("Ich bin kein totes UI-Element")
- **Kontext**: Weiß was auf der Page passiert ("Ich verstehe deinen Workflow")

**Features:**

1. **Living Icon + Expandable Chat Window**
   - Collapsed: Animated Trashy icon (right side, follows focus)
   - Expanded: 380x520px chat window with message history
   - Idle animation: Subtle floating + breathing effect
   - Movement: Organic cubic-bezier with overshoot

2. **Session-Aware Context**
   - Uses `run_id` from `useCurrentSession` composable
   - Loads chat history from backend when session exists

3. **Page-Aware Context**
   - Uses Pinia store (`pageContextStore`) for cross-component communication
   - Knows current view type, form fields, workflow nodes
   - Prepends context to first message if no run_id session exists

4. **Focus Tracking**
   - MediaInputBox emits `@focus` events
   - Views track `focusedField`: 'input' | 'context' | 'interception' | 'optimization'
   - Träshy Y-position follows focused element dynamically

5. **Viewport Clamping**
   - Chat window never extends beyond viewport edges
   - Position calculated and clamped on every update

**Architecture (Pinia Store):**

```
┌─────────────────────────────────────────────────────────────┐
│                         App.vue                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                     router-view                        │  │
│  │                                                        │  │
│  │   text_transformation.vue ───┐                         │  │
│  │   canvas_workflow.vue ───────┤                         │  │
│  │   image_transformation.vue ──┼─── watch() ──► pageContextStore
│  │   direct.vue ────────────────┤                         │  │
│  │   surrealizer.vue ───────────┤     (Pinia)             │  │
│  │   multi_image_transformation ┘                         │  │
│  │                                                        │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                   ChatOverlay.vue                      │  │
│  │            usePageContextStore() ◄─────────────────────│  │
│  │            - formatForLLM() ──► API request            │  │
│  │            - currentFocusHint ──► dynamic positioning  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Why Pinia instead of provide/inject?**
- ChatOverlay is a **sibling** of router-view in App.vue
- Vue's provide/inject only works parent→child, not sibling→sibling
- Pinia store enables cross-component communication

**Context Priority:**

1. **Session Context (run_id)** - Highest priority
   - Backend loads full session files (prompts, metadata)
   - Chat history persisted per run

2. **Draft Page Context (Pinia store)** - If no session
   - Current view type + focused field
   - Form field values (inputText, contextPrompt, etc.)
   - Canvas workflow nodes
   - Selected configs

3. **Route-only Fallback** - Minimal
   - Just `[Kontext: Aktive Seite = /path]`

**Store: pageContextStore (src/stores/pageContext.ts)**

```typescript
export const usePageContextStore = defineStore('pageContext', () => {
  const activeViewType = ref<string>('')
  const pageContent = ref<PageContent>({})
  const focusHint = ref<FocusHint>(DEFAULT_FOCUS_HINT)

  function setPageContext(ctx: PageContext) { ... }
  function formatForLLM(routePath: string): string { ... }

  return { activeViewType, pageContent, focusHint, currentFocusHint, setPageContext, formatForLLM }
})
```

**FocusHint Interface:**

```typescript
export interface FocusHint {
  x: number  // Horizontal position (percentage)
  y: number  // Vertical position (percentage)
  anchor: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'
}
```

**View Implementation Pattern:**

```typescript
// In each view (e.g., text_transformation.vue)
import { watch, onUnmounted } from 'vue'
import { usePageContextStore } from '@/stores/pageContext'

const pageContextStore = usePageContextStore()
const focusedField = ref<'input' | 'context' | 'interception' | 'optimization' | null>(null)

// Helper: Get element Y position as viewport percentage
function getElementY(el: HTMLElement | null): number {
  if (!el) return 50
  const rect = el.getBoundingClientRect()
  return (rect.top + rect.height / 2) / window.innerHeight * 100
}

// Update store when context or focus changes
watch([focusedField, executionPhase, ...], () => {
  nextTick(() => {
    if (focusedField.value === 'input') {
      trashyY.value = getElementY(inputSectionRef.value)
    }
    // ...
  })
})

const pageContext = computed<PageContext>(() => ({
  activeViewType: 'text_transformation',
  pageContent: {
    inputText: inputText.value,
    contextPrompt: contextPrompt.value,
    interceptionResult: interceptionResult.value,
    selectedCategory: selectedCategory.value,
    selectedConfig: selectedConfig.value
  }
}))

provide(PAGE_CONTEXT_KEY, pageContext)
```

**ChatOverlay Message Prepending:**

```typescript
// In ChatOverlay.vue
const pageContext = inject(PAGE_CONTEXT_KEY, null)
const route = useRoute()

const draftContextString = computed(() => {
  return formatPageContextForLLM(pageContext?.value || null, route.path)
})

async function sendMessage() {
  let messageForBackend = userMessage

  // Only prepend context if no run_id session exists
  if (!currentSession.value.runId && draftContextString.value) {
    messageForBackend = `${draftContextString.value}\n\n${userMessage}`
  }

  // UI shows original message, backend receives context-prepended
  messages.value.push({ role: 'user', content: userMessage })
  await axios.post('/api/chat', { message: messageForBackend, ... })
}
```

**Views with Page Context:**

| View | Context Provided |
|------|------------------|
| `text_transformation.vue` | inputText, contextPrompt, interceptionResult, selectedCategory, selectedConfig |
| `canvas_workflow.vue` | workflowName, workflowNodes, selectedNodeId, connectionCount |
| `image_transformation.vue` | inputText, contextPrompt, uploadedImage, selectedConfig |
| `direct.vue` | inputText, selectedConfig |
| `surrealizer.vue` | inputText, contextPrompt, uploadedImage, selectedConfig |
| `multi_image_transformation.vue` | inputText, contextPrompt, uploadedImages, selectedConfig |

**Related Files:**
- `src/composables/usePageContext.ts` - Type definitions and formatting
- `src/composables/useCurrentSession.ts` - Run ID session management
- `devserver/my_app/routes/chat_routes.py` - Backend chat API

---

### UI Features: Badges & Status Indicators

#### Wikipedia Research Badge

**Purpose:** Visual indicator showing when AI system has consulted Wikipedia for cultural/factual context

**Pedagogical Goal:**
- Transparency about AI research process
- Cultural respect through factual grounding
- Build trust by showing Wikipedia sources
- Show ALL search attempts (found + not found) for full transparency

**Implementation:**

**Location:** Next to Start #1 button in `text_transformation.vue`
- **Reason:** Stable UI area that doesn't move during SSE streaming
- Previous location (interception section) caused badge to disappear during multiple lookups

**Visual Design:**
```typescript
// Wikipedia badge uses LoRA badge design pattern
class="lora-stamp wikipedia-lora"

// SVG icon: Wikipedia "W" in puzzle globe style
// Color: Distinct from LoRA green (configurable via CSS)

// Visual distinction for found/not-found
// Found: Blue clickable link
// Not found: Gray italic with "(nicht gefunden)"
```

**Backend: Wikipedia Lookup Strategy**

Uses **Opensearch API** for fuzzy matching instead of direct Page Summary lookup:

```
Step 1: Opensearch API (finds best matching article)
https://{lang}.wikipedia.org/w/api.php?action=opensearch&search={term}&limit=1&format=json

Response: [searchTerm, [titles], [descriptions], [urls]]
Example: ["Igbo New Yam", ["New Yam Festival"], ["..."], ["https://en.wikipedia.org/wiki/New_Yam_Festival"]]

Step 2: Page Summary API (fetches full content)
https://{lang}.wikipedia.org/api/rest_v1/page/summary/{foundTitle}
```

**Why Opensearch?**
- LLM generates search terms that may not match exact Wikipedia titles
- Example: "Igbo New Yam Festival" → actual article is "New Yam Festival"
- Opensearch does fuzzy matching, Page Summary requires exact title
- Combined approach: Opensearch finds, Page Summary fetches content

**Data Flow:**
```typescript
// SSE Event from backend during Stage 2 (Prompt Interception)
@wikipedia-lookup="handleWikipediaLookup"

// Event structure:
{
  status: 'start' | 'complete',
  terms: Array<{
    term: string,        // Original search term from LLM
    lang: string,        // Language used for lookup
    title: string,       // Wikipedia article title (or term if not found)
    url: string,         // Full Wikipedia URL (empty if not found)
    success: boolean     // Whether lookup succeeded
  }>
}

// ALL terms sent (no filter), success=false for not found
```

**State Management:**
```typescript
const wikipediaData = ref<{
  active: boolean,  // Research in progress
  terms: Array<WikipediaTerm>
}>({ active: false, terms: [] })

// Accumulates terms during multiple lookups
// Only resets on new interception run
```

**User Interaction:**
- Click badge → Expand list of Wikipedia articles
- Each article shows language code `[de]`, `[en]`, etc.
- Articles are clickable links to Wikipedia

**Key Implementation Details:**

**Problem Solved:** Badge disappeared after 3 seconds during multiple lookups
- **Root Cause:** SSE "start" events reset `terms: []`, badge was in unstable section
- **Solution:**
  1. Moved badge to stable area (Start #1 button container)
  2. Changed `handleWikipediaLookup()` to **accumulate** terms instead of replacing
  3. Only full reset on new interception run (`runInterception()`)

**Code Pattern:**
```typescript
function handleWikipediaLookup(data) {
  if (data.status === 'start') {
    wikipediaData.value.active = true
    // Accumulate, don't replace
    if (data.terms?.length > 0) {
      wikipediaData.value.terms = [...wikipediaData.value.terms, ...data.terms]
    }
  } else if (data.status === 'complete') {
    wikipediaData.value.active = false
    // Accumulate
    if (data.terms?.length > 0) {
      wikipediaData.value.terms = [...wikipediaData.value.terms, ...data.terms]
    }
  }
}

function runInterception() {
  // Only place where terms reset
  wikipediaData.value = { active: false, terms: [] }
}
```

**Badge Text:**
- During research: "Wikipedia-Recherche läuft..."
- After completion: "3 Begriff(e)" (shows count of ALL searched terms)

**Expandable Details:**
```typescript
wikipediaExpanded = ref(false)  // Toggle state

// Expanded view shows ALL terms with visual distinction:
<div class="lora-details">
  <div v-for="term in wikipediaData.terms" class="lora-item">
    // Found: Blue clickable link
    <template v-if="item.success && item.url">
      <a :href="item.url" target="_blank">{{ item.title }}</a>
    </template>
    // Not found: Gray italic text
    <template v-else>
      <span class="wikipedia-not-found">
        {{ item.term }} <small>(nicht gefunden)</small>
      </span>
    </template>
  </div>
</div>
```

**CSS for Not Found:**
```css
.wikipedia-not-found {
  color: #888;
  font-style: italic;
}
```

**Cultural Context Feature:**
- Wikipedia lookup uses **cultural reference language**, not prompt language
- Example: German prompt about Nigeria → uses Hausa/Yoruba/Igbo/English Wikipedia
- 70+ languages supported for cultural contexts
- Prevents orientalism by grounding in cultural sources

**Related Files:**
- `public/ai4artsed-frontend/src/views/text_transformation.vue` - Badge UI
- `public/ai4artsed-frontend/src/views/text_transformation.css` - Badge styling
- `devserver/schemas/engine/pipeline_executor.py` - Sends Wikipedia events via SSE
- `devserver/my_app/services/wikipedia_service.py` - Opensearch API + 70+ languages

**Evolution:**
1. Initial implementation with cultural language support
2. Badge UI improvements
3. Fixed badge disappearing (moved to stable area)
4. Opensearch API for fuzzy matching + show all terms

---

#### LoRA Badge

**Purpose:** Shows when Low-Rank Adaptation models are being used

**Locations:**
1. **Stage 2 (Interception):** Shows config-defined LoRAs (after Start #1)
2. **Stage 4 (Generation):** Shows active LoRAs from backend response (after Start #2)

**Visual Design:**
- Green color scheme (distinct from Wikipedia badge)
- Caterpillar/nature icon
- Shows count: "2 LoRAs"

**Expandable Details:**
- Click to expand list of LoRA names and strengths
- Format: "LoRA Name" with strength value

**Code Pattern:**
```typescript
// Stage 2: Uses config data
const configLoras = computed(() => {
  return pipelineStore.selectedConfig?.loras || []
})

// Stage 4: Uses backend response
const activeLoras = ref<Array<{name: string, strength: number}>>([])

// Smart computed: uses activeLoras if available, else configLoras
const stage4Loras = computed(() => {
  return activeLoras.value.length > 0
    ? activeLoras.value
    : configLoras.value
})
```

**Related Files:**
- `public/ai4artsed-frontend/src/views/text_transformation.vue` - Badge UI
- `devserver/my_app/routes/schema_pipeline_routes.py` - Returns active LoRAs in response

---

#### Safety Approved Stamp (Stage 1)

**Purpose:** Visual confirmation that user input passed safety validation

**Location:** Next to Start #2 button (Generation)

**Visual Design:**
- Checkmark icon ✓
- Text: "Safety Approved"
- Green color scheme

**Timing:**
- Appears after 300ms delay during `executePipeline()`
- Simulates Stage 1 safety check
- Provides user confidence before generation starts

**Code Pattern:**
```typescript
const showSafetyApprovedStamp = ref(false)

async function executePipeline() {
  showSafetyApprovedStamp.value = false  // Reset

  // Stage 1: Safety check (silent, shows stamp when complete)
  await new Promise(resolve => setTimeout(resolve, 300))
  showSafetyApprovedStamp.value = true

  // Continue with generation...
}
```

---

## Favorites System: Dual-Mode Pedagogical Workspace

**Purpose:** Two-mode favorites system balancing **personal creative iteration** with **collaborative workshop learning**.

### Architecture Overview

**Two Modes:**
1. **"Meine" (Per-User):** Personal workspace - filter by device_id
2. **"Alle" (Global):** Workshop collaboration - show all favorites

**Key Decision:** Device-based identity (not login) for workshop context.

### Component Structure

```
FooterGallery.vue (Fixed footer at bottom)
├── Toggle Bar (Collapse/Expand)
│   ├── Gallery Title: "Favoriten"
│   ├── Badge: Favorite count
│   └── View Mode Switch: [Meine | Alle]  ← 2-field segmented control
│
└── Gallery Content (Expandable)
    ├── Loading State
    ├── Empty State
    └── Favorites Grid
        ├── Thumbnail
        ├── Input Preview (overlay)
        └── Action Buttons
            ├── Continue (copy URL) - images only
            ├── Restore (load session)
            └── Remove (delete favorite)
```

### State Management (Pinia Store)

**File:** `public/ai4artsed-frontend/src/stores/favorites.ts`

```typescript
// State
const favorites = ref<FavoriteItem[]>([])
const viewMode = ref<'per_user' | 'global'>('per_user')  // Default: personal
const mode = ref<'global' | 'per_user'>('global')  // Backend mode
const isGalleryExpanded = ref(false)
const pendingRestoreData = ref<RestoreData | null>(null)

// Types
interface FavoriteItem {
  run_id: string
  device_id?: string  // Device identity for the per_user view
  media_type: 'image' | 'audio' | 'video' | ...
  added_at: string
  thumbnail_url: string
  user_id: string
  user_note: string
  // Enriched by backend
  exists?: boolean
  schema?: string
  timestamp?: string
  input_preview?: string
}
```

### Device ID System (Reuses Export Architecture)

**Same as the research data export system:**

```typescript
function getDeviceId(): string {
  // Browser ID (persistent across sessions)
  let browserId = localStorage.getItem('browser_id')
  if (!browserId) {
    browserId = crypto.randomUUID()
    localStorage.setItem('browser_id', browserId)
  }

  // Combine with date (24h rotation)
  const today = new Date().toISOString().split('T')[0]  // "2026-01-28"
  return `${browserId}_${today}`
}

// Example: "a1b2c3d4-e5f6_2026-01-28"
```

**Privacy:**
- Daily rotation at midnight → GDPR-friendly
- No long-term tracking
- Acceptable for workshop context (device = workstation)

### API Integration

#### Loading Favorites (with filtering)

```typescript
async function loadFavorites(deviceId?: string): Promise<void> {
  // Build query parameters
  const params = new URLSearchParams()
  if (deviceId) {
    params.append('device_id', deviceId)
  }
  params.append('view_mode', viewMode.value)  // 'per_user' or 'global'

  // Fetch with filter
  const response = await axios.get<FavoritesResponse>(
    `/api/favorites?${params.toString()}`
  )

  favorites.value = response.data.favorites
}
```

**Backend Filter (`favorites_routes.py`):**
```python
# GET /api/favorites?device_id=xxx_2026-01-28&view_mode=per_user
device_id = request.args.get('device_id')
view_mode = request.args.get('view_mode', 'per_user')

# Filter if per_user mode
if view_mode == 'per_user' and device_id:
    favorites = [f for f in favorites if f.get('device_id') == device_id]
```

#### Adding Favorites

```typescript
async function addFavorite(
  runId: string,
  mediaType: FavoriteItem['media_type'],
  deviceId: string,  // Required for per-user filtering
  userId: string = 'anonymous'
): Promise<boolean> {
  // Optimistic update
  favorites.value.unshift({
    run_id: runId,
    device_id: deviceId,  // Store device_id
    media_type: mediaType,
    // ...
  })

  // POST to backend
  await axios.post('/api/favorites', {
    run_id: runId,
    media_type: mediaType,
    device_id: deviceId,  // Include in request
    user_id: userId
  })
}
```

### UI: 2-Field Segmented Control

**Why 2-field (not toggle button):**
- User feedback: Single toggle confusing - can't see inactive option
- Both options visible → clear affordance
- Active state highlighted → current mode obvious

**Template (`FooterGallery.vue`):**
```vue
<div class="view-mode-switch" @click.stop>
  <button
    class="switch-option"
    :class="{ active: viewMode === 'per_user' }"
    @click="setViewModePerUser"
    title="Nur meine Favoriten"
  >
    <svg><!-- Person icon --></svg>
    <span>Meine</span>
  </button>

  <button
    class="switch-option"
    :class="{ active: viewMode === 'global' }"
    @click="setViewModeGlobal"
    title="Alle Favoriten"
  >
    <svg><!-- Group icon --></svg>
    <span>Alle</span>
  </button>
</div>
```

**CSS:**
```css
.view-mode-switch {
  display: flex;
  gap: 0;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 6px;
  padding: 2px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.switch-option {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.5rem;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.switch-option.active {
  background: rgba(102, 126, 234, 0.4);  /* Highlighted */
  color: rgba(255, 255, 255, 1);
  font-weight: 600;
}
```

### Session Restore Pattern (Cross-Component Communication)

**Pattern:** Pinia store reactive signal (not sessionStorage)

**FooterGallery (sets data):**
```typescript
async function handleRestore(favorite: FavoriteItem) {
  // Fetch complete session data
  const restoreData = await favoritesStore.getRestoreData(favorite.run_id)

  // Set reactive signal
  favoritesStore.setRestoreData(restoreData)

  // Navigate to target view
  router.push(restoreData.target_view)  // 'text-transformation' or 'image-transformation'
}
```

**View (watches and consumes):**
```typescript
// text_transformation.vue
watch(() => favoritesStore.pendingRestoreData, (data) => {
  if (!data) return

  // Restore fields
  inputText.value = data.input_text
  contextPrompt.value = data.context_prompt
  interceptionResult.value = data.transformed_text

  // Clear signal
  favoritesStore.setRestoreData(null)
}, { immediate: true })
```

**Why this pattern:**
- Reactive: Works even if already on target page
- Timing-safe: `{ immediate: true }` processes on mount
- Clean: Automatic cleanup via watcher

### Pedagogical Workflows

#### Workflow 1: Personal Iteration

1. Student generates image → clicks favorite
2. Generates variation → favorites it
3. Opens FooterGallery in "Meine" mode
4. Compares thumbnails side-by-side
5. Selects best version for continuation
6. Clicks "Restore" → session reloaded
7. Refines prompt, generates final version

**Pedagogical Value:**
- Visual comparison of variations
- Learn from own process (what worked/didn't)
- Iterate without losing intermediate steps
- Build personal portfolio

#### Workflow 2: Collaborative Learning

1. Student A generates interesting result → favorites it
2. Student B switches to "Alle" mode
3. Sees Student A's thumbnail in gallery
4. Clicks "Restore" → loads Student A's complete session
5. Sees original prompt, transformation, and parameters
6. Can remix: modify prompt, try different config
7. Generate own variation, favorite for others to see

**Pedagogical Value:**
- Transparent creative process (prompts visible)
- Peer learning (discover effective strategies)
- Collective refinement (build on others' work)
- Workshop culture (shared visual vocabulary)

### Storage Architecture

**Backend File:** `exports/json/favorites.json`

```json
{
  "version": "1.0",
  "mode": "global",
  "favorites": [
    {
      "run_id": "run_1769619726272_aa0ee5",
      "device_id": "a1b2c3d4_2026-01-28",  // Device identity for the per_user view
      "media_type": "image",
      "added_at": "2026-01-28T18:02:50.294120",
      "thumbnail_url": "/api/media/image/run_1769619726272_aa0ee5/0",
      "user_id": "anonymous",
      "user_note": ""
    }
  ]
}
```

**Metadata Enrichment:**

Backend loads run metadata for each favorite:
- Schema used (`config_name`)
- Timestamp
- Input text preview (first 100 chars)
- Exists check (run folder still available)

**Restore Data:**

```typescript
interface RestoreData {
  run_id: string
  schema: string
  execution_mode: string
  timestamp: string
  input_text?: string
  context_prompt?: string  // Meta-prompt (user-editable!)
  transformed_text?: string
  translation_en?: string
  models_used?: ModelsUsed
  media_outputs: MediaOutput[]
  target_view: string  // 'text-transformation' | 'image-transformation'
}
```

### Edge Cases & Workshop Scenarios

**1. Shared Device (Multiple Students):**
- All share same browser_id → same device_id
- Favorites are per-workstation, not per-person
- Acceptable: Device = Arbeitsplatz in workshop

**2. Daily Rotation (Privacy):**
- device_id changes at midnight
- Old favorites persist in backend
- "Meine" shows only today's device_id
- "Alle" shows all days → can restore old work

**3. localStorage Cleared:**
- New browser_id generated
- Old favorites lost in "Meine" mode
- Still accessible in "Alle" mode
- Trade-off for privacy

**4. Collaborative Remixing:**
- Student sees interesting work in "Alle"
- Restores session → gets complete prompt chain
- Modifies and generates variation
- Favorites own version for others to build upon

### Related Files

**Backend:**
- `devserver/my_app/routes/favorites_routes.py` - REST API + filtering logic

**Frontend:**
- `public/ai4artsed-frontend/src/stores/favorites.ts` - Pinia store
- `public/ai4artsed-frontend/src/components/FooterGallery.vue` - UI component
- `public/ai4artsed-frontend/src/views/text_transformation.vue` - Restore watcher
- `public/ai4artsed-frontend/src/views/image_transformation.vue` - Restore watcher
- `public/ai4artsed-frontend/src/App.vue` - FooterGallery mounting

---
