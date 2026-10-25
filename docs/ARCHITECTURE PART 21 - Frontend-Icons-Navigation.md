# DevServer Architecture

**Part 21: Frontend Icons & Navigation Patterns**

---

## Overview

**Status:** ✅ Active
**Architecture:** Emoji-first icon strategy with Vue Router navigation
**Last Updated:** 2025-12-08

This document analyzes the icon and navigation implementation patterns across the AI4ArtsEd Vue frontend, focusing on Phase1 button, Text2I/Img2I mode icons, and universal action toolbar patterns.

---

## 0. Current Mode-Selector & Hub Grouping (Update 2026-07-13)

> **Sections 1-17 below are STALE (state of 2025-12-08).** The header now uses inline **SVG** icons (not emoji), there is no "Phase 1" return button, and `/` maps to LandingView. This section reflects the current header `mode-selector` in `App.vue`.

**Header order (8 icon-only buttons, left to right, verified against `App.vue` on 2026-08-18):** Home `/`, Workshop `/workshop`, Contesting `/contesting`, x2x flow `/x2x-flow`, Compare `/compare`, Latent Lab `/latent-lab`, Canvas `/canvas`, LoRA `/training`. Re-enactment lost its own button on 2026-08-18 and became the fourth entry of the Crossmodal group in the Latent Lab's left column; the route `/cover-band` still works and the Latent Lab button is marked when it is open. (Before 2026-08-12 the list said nine and named `/persona`, which is `/contesting`, while omitting `/cover-band` entirely.) Inline `<svg viewBox="0 -960 960 960">`; `guardGenerating` blocks navigation while a generation runs.

**The "A-with-arrow" button is gone (2026-08-12).** It opened the x2x (legacy)
hub — four tabs over `text_transformation.vue`, `image_transformation.vue`,
`multi_image_transformation.vue` and the music page. The mode is completely
replaced by Flow. The hub, the three pages, the pilot
`t2i_flow.vue` and the loader `PipelineRouter.vue` were removed; `/x2x-flow` is
the one place this work happens now. The old paths redirect there, because they
are written down in workshop handouts. What moved rather than died: the p5.js /
Tone.js code surface, which only the text page could run — it is
`components/CodeSandbox.vue` and opens from the flow's output node; and the
"send onward" controls on eight pages, which handed an image to the
image-to-image page and now drop it into the flow's ring.

**Rationale + the inconsistency this partially heals:** see `docs/DEVELOPMENT_DECISIONS.md` (2026-07-13). The hub-tab pattern is registered (`to-consolidate`) in `docs/ELEMENT_STRUCTURE_REGISTRY.md`.

---

## 1. Phase1 Return Button (entfallen)

Der Knopf ist fort, und das, worauf er zeigte, auch. Er stand in `.header-left`
von `App.vue` und schob auf `/`, was damals auf `/select` (PropertyQuadrantsView)
umleitete. `/select` gibt es seit langem nicht mehr, `PropertyQuadrantsView.vue`
ist am 2026-09-22 geloescht. `/` ist `views/LandingView.vue`, und `.header-left`
traegt das Logo des UNESCO Chair, verlinkt auf ucdcae.fau.de.

---

## 2. Mode Icons

### Location
**File**: `public/ai4artsed-frontend/src/App.vue`, Abschnitt `.header-center`

### Current Implementation
Sechs `router-link`, jeder mit einem Material-Symbols-SVG (24 px,
`fill="currentColor"`):

| Ziel | Titel |
|---|---|
| `/` | — |
| `/together` | `$t('resona.title')` |
| `/contesting` | `$t('persona.title')` |
| `/x2x-flow` | `$t('x2xFlow.modeTitle')` |
| `/latent-lab` | — |
| `/canvas` | "Canvas Workflow" |

### Key Details
- **Position**: Center header (`.header-center`)
- **Type**: eingebettetes SVG, kein Emoji
- **Active State**: gruene Hervorhebung bei passender Route; `/latent-lab` passt
  auch auf seine Instrumenten-Pfade
- **Haengt an keinem Laufzustand**: vom 2026-03-22 bis zum 2026-08-15 stand jeder
  Knopf hier auf `pointer-events: none`, solange eine Erzeugung lief. Der
  Kommentar ueber dem Selektor in `App.vue` haelt fest, warum das nicht
  wiederkommen darf.
- Das fruehere Paar — 📝 `/text-transformation` und 🖼️ `/image-transformation` —
  ging am 2026-08-12 mit dem Transform-Modus; beide Pfade leiten auf `/x2x-flow`.

### Styling Characteristics
```css
.mode-selector {
  display: flex;
  gap: 0.25rem;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 0.25rem;
}

.mode-button {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  background: transparent;
  border: 2px solid transparent;
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.6);
  transition: all 0.3s ease;
  min-width: 60px;
}

.mode-button.active {
  background: rgba(76, 175, 80, 0.15);  /* Green background */
  border-color: rgba(76, 175, 80, 0.5);  /* Green border */
  color: #4CAF50;  /* Green text */
}

.mode-icon {
  font-size: 1.5rem;
}
```

**Educational Design Rationale**:
- **Icon-only design** reduces cognitive load (no competing text labels)
- **Green active state** provides clear visual feedback of current mode
- **Grouped in single container** establishes relationship between modes
- **Equal visual weight** prevents hierarchy (both modes equally valid)

---

## 3. Overall Icon Strategy

### Emoji-First Approach

**Principle** (Stand 2025, ueberholt): App uses Unicode emojis exclusively for UI icons, NOT SVG components. Die Kopfzeile traegt seit 2026 Material-Symbols-SVG (Abschnitt 2). Wo im uebrigen Interface noch Emoji stehen, ist nicht erhoben; die folgenden Abschnitte sind an der Oberflaeche nicht nachgeprueft.

**Advantages**:
1. **Simplicity**: No icon libraries or SVG asset management
2. **Consistency**: Emojis render consistently across modern browsers
3. **Accessibility**: Screen readers provide built-in emoji descriptions
4. **Rapid Development**: No need to design/import/maintain SVG files
5. **Zero Overhead**: No additional network requests or bundle size
6. **Cultural Universal**: Icons transcend language barriers (important for educational app)

**Disadvantages** (acknowledged but accepted):
- Platform-dependent rendering (emoji appearance varies by OS)
- Limited customization (can't change emoji colors/paths)
- Size constraints (emoji fonts control sizing)

**Decision Rationale**: For educational applications targeting K-12, emoji familiarity outweighs customization needs.

---

## 4. Icon Component Infrastructure

### Icon Component Pattern
```vue
<template>
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor">
    <path d="..." />
  </svg>
</template>
```

**Status**: Default Vue3 template icons, NOT actively used in main application.

**Rationale for Non-Use**: Emoji approach chosen instead (see Section 3).

---

## 5. Universal Action Toolbar Pattern

### Overview
**Status**: Implemented (Universal Image Analysis Helper)
**Location**: All Phase 2 views (text_transformation.vue, image_transformation.vue)
**Purpose**: Consistent post-generation actions across all media types

### Implementation Pattern
```vue
<div class="action-toolbar">
  <button class="action-btn" @click="saveMedia" disabled title="Merken (Coming Soon)">
    <span class="action-icon">⭐</span>
  </button>
  <button class="action-btn" @click="printImage" title="Drucken">
    <span class="action-icon">🖨️</span>
  </button>
  <button class="action-btn" @click="sendToI2I" title="Weiterreichen zu Bild-Transformation">
    <span class="action-icon">➡️</span>
  </button>
  <button class="action-btn" @click="downloadMedia" title="Herunterladen">
    <span class="action-icon">💾</span>
  </button>
  <button class="action-btn" @click="analyzeImage" title="Bildanalyse">
    <span class="action-icon">🔍</span>
  </button>
</div>
```

### Action Icons Reference
| Icon | Action | German Label | Status | Notes |
|------|--------|--------------|--------|-------|
| ⭐ | Save/Bookmark | Merken | Disabled | Coming Soon |
| 🖨️ | Print | Drucken | Active | Opens print dialog |
| ➡️ | Transfer to Img2I | Weiterreichen | Active (images only) | localStorage transfer |
| 💾 | Download | Herunterladen | Active | Direct file download |
| 🔍 | Image Analysis | Bildanalyse | Active (images only) | Universal helper |

### Styling Characteristics
```css
.action-btn {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(30, 30, 30, 0.9);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.action-btn:hover:not(:disabled) {
  border-color: rgba(102, 126, 234, 0.8);
  background: rgba(102, 126, 234, 0.2);
  transform: scale(1.1);
}

.action-icon {
  font-size: 1.5rem;
  line-height: 1;
}
```

**Responsive Behavior** (Mobile < 768px):
```css
@media (max-width: 768px) {
  .action-toolbar {
    flex-direction: row;  /* Horizontal on mobile */
    gap: 0.5rem;
  }

  .action-btn {
    width: 40px;
    height: 40px;
  }

  .action-icon {
    font-size: 1.25rem;
  }
}
```

### Educational Design Rationale
- **Consistent Position**: Always next to output (right side on desktop, below on mobile)
- **Icon-Only Design**: Reduces visual clutter, tooltips provide labels
- **Disabled State Visible**: Shows future capabilities (e.g., Save feature)
- **Scale Hover Effect**: Provides tactile feedback (important for touch devices)

---

## 6. Category & Config Selection Patterns

### Category Bubbles (Media Type Selection)

**Used In**: text_transformation.vue, image_transformation.vue

```vue
<div class="category-bubble"
     :class="{ selected: selectedCategory === category.id }"
     :style="{ '--bubble-color': category.color }">
  <div class="bubble-emoji-small">{{ category.emoji }}</div>
</div>
```

**Available Categories**:
- 🖼️ **Image** (Bild) - `#4CAF50` (green)
- 🎬 **Video** - `#9C27B0` (purple) - disabled
- 🔊 **Sound** - `#FF9800` (orange) - disabled

**Design Pattern**:
- Circular bubbles (50% border-radius)
- Dynamic color via CSS custom property
- Scale transform on selection (1.15x)
- Glow effect using box-shadow with category color

### Config Bubbles (Model Selection)

**Mixed Icon Approach**: Logos for branded models, emojis for generic

```vue
<img v-if="config.logo" :src="config.logo" :alt="config.label" class="bubble-logo" />
<div v-else class="bubble-emoji-medium">{{ config.emoji }}</div>
```

**Example Configs**:
- **Flux.1-schnell**: Custom logo (PNG)
- **DALL-E 3**: OpenAI logo
- **SD 3.5 Large**: Stability AI logo
- **Generic**: Emoji fallback

**Educational Design Rationale**:
- **Brand Recognition**: Logos help students recognize AI models
- **Emoji Fallback**: Ensures visual consistency when logos unavailable
- **Light Background Option**: `light-bg` class for dark logos

---

## 7. Input/Context Bubble Icons

### Semantic Icon Pattern

**Used In**: text_transformation.vue, image_transformation.vue

| Icon | Context | Meaning |
|------|---------|---------|
| 💡 | Input | "Deine Idee" (Your Idea) - represents creativity |
| 📋 | Context | "Bestimme Regeln" (Set Rules) - represents constraints |
| → | Interception | Arrow indicates transformation |
| ✨ | Optimization | Sparkles represent model enhancement |
| 🖼️ | Image Upload | Frame represents image container |

**Design Pattern**:
```vue
<div class="bubble-header">
  <span class="bubble-icon">💡</span>
  <span class="bubble-label">Deine Idee: Worum soll es gehen?</span>
</div>
```

**Educational Design Rationale**:
- **Semantic Consistency**: Each icon has fixed meaning across views
- **Visual Hierarchy**: Icon + label establishes bubble purpose
- **Cognitive Anchors**: Students learn to associate icons with workflow stages

---

## 8. Router Structure & Navigation Flow

### Route Hierarchy
```
/ → LandingView.vue
/about → AboutView.vue
/direct → direct.vue
/x2x-flow → x2x_flow.vue
/surrealizer-flow → surrealizer_flow.vue
/latent-lab/:instrument? → latent_lab.vue
/together → resona.vue
/contesting → ai_persona.vue
/canvas → canvas_workflow.vue
/kickin, /kickin-perblock → KickinView.vue, KickinPerBlockView.vue
/settings → LandingView.vue
/impressum, /datenschutz, /dokumentation → die gleichnamigen Views
/login, /account, /usage-agreement → die gleichnamigen Views
/educator, /educator/courses/:id, /admin/users → Kurs- und Admin-Views
/dev/pixel-editor, /animation-test → Entwicklerflaechen

Umleitungen:
/execute/:configId, /text-transformation, /t2i-flow, /image-transformation,
/multi-image-transformation, /x2x-legacy → /x2x-flow
/surrealizer → /latent-lab/encoder-fusion
/decomposition → /latent-lab
/training → /latent-lab/lora-sd35
/cover-band → /latent-lab/re-enactment
/silly-parrot → /cover-band
/compare → /latent-lab/model-comparison
/workshop → /together
```

### Navigation Patterns

#### 1. Eine Perspektive waehlen
Eine eigene Auswahlseite gibt es nicht mehr. Eine Perspektive (Config) wird auf
der Flussflaeche selbst genommen, von den Scheiben auf dem Brett
(`views/x2x_flow.vue`). `/execute/:configId`, das eine Pipeline-Seite nach
Config lud, leitet auf `/x2x-flow`.

#### 2. Zwischen den Modi wechseln
Die sechs Zeichen in `.header-center` sind `router-link`s: Routenwechsel ohne
erhaltenen Zustand.

#### 3. Ein Bild weiterreichen
Die „send onward"-Knoepfe schreiben `i2i_transfer_data` nach `localStorage`
(`views/direct.vue`, `views/ai_persona.vue`, die beiden Vergleichsflaechen,
`components/canvas/OutputDrawer.vue`). `views/x2x_flow.vue` liest den Schluessel
einmal und entfernt ihn sofort; ist der Zeitstempel juenger als fuenf Minuten,
faellt das Bild in den Ring des Flusses. Alles Aeltere ist ein Ueberbleibsel und
wird verworfen — `localStorage` ueberlebt den Browser.

---

## 9. Design System Patterns

### Color Palette

**Background Colors**:
- Primary Background: `#0a0a0a` (near black)
- Card Background: `rgba(20-30, 20-30, 20-30, 0.9)`
- Overlay Background: `rgba(0, 0, 0, 0.95)` (fullscreen modals)

**Accent Colors**:
- **Green** (Active/Success): `#4CAF50` / `rgba(76, 175, 80, ...)`
- **Purple/Blue** (Hover/Focus): `rgba(102, 126, 234, ...)`
- **Yellow** (Warning/Required): `rgba(255, 193, 7, ...)`
- **Orange** (Media Types): `#FFB300` (Start button accent)

**Border Colors**:
- Default: `rgba(255, 255, 255, 0.2)`
- Hover: `rgba(255, 255, 255, 0.3)`
- Active: Accent color with 0.5-0.8 opacity

### Border Radius Standards
- **Small elements** (buttons, inputs): `6-8px`
- **Medium elements** (cards, bubbles): `12-16px`
- **Large elements** (modals, frames): `16-20px`
- **Circles** (category bubbles): `50%`
- **Responsive**: Use `clamp(12px, 2vw, 20px)` for fluid scaling

### Hover & Active State Patterns

**Consistent Hover Effect**:
```css
element:hover {
  border-color: rgba(102, 126, 234, 0.8);
  background: rgba(102, 126, 234, 0.2);
  transform: scale(1.05) | translateX(-4px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}
```

**Active State (Selected)**:
```css
element.active | element.selected {
  border-color: rgba(76, 175, 80, 0.6);
  background: rgba(76, 175, 80, 0.15);
  transform: scale(1.15);
  box-shadow: 0 0 30px var(--bubble-color);
}
```

**Disabled State**:
```css
element:disabled | element.disabled {
  opacity: 0.3;
  cursor: not-allowed;
  pointer-events: none;
  filter: grayscale(0.8);
}
```

---

## 10. Responsive Design Strategy

### Breakpoints
- **Desktop**: Default (> 768px)
- **Mobile**: `@media (max-width: 768px)`
- **iPad Landscape**: `@media (min-width: 1024px) and (max-height: 768px)`

### Fluid Typography & Spacing
```css
/* Font Sizes */
font-size: clamp(0.9rem, 2vw, 1rem);     /* Body text */
font-size: clamp(1rem, 2.5vw, 1.2rem);   /* Buttons */
font-size: clamp(1.5rem, 3vw, 2rem);     /* Icons */

/* Padding */
padding: clamp(0.5rem, 1.5vw, 0.75rem);  /* Inputs */
padding: clamp(1rem, 3vw, 2rem);         /* Sections */

/* Gap */
gap: clamp(1rem, 2.5vw, 1.5rem);         /* Flex containers */
```

**Educational Design Rationale**: Fluid scaling ensures readability across devices commonly used in classrooms (tablets, Chromebooks, projectors).

### Mobile Adaptations
```css
@media (max-width: 768px) {
  .header-content {
    grid-template-columns: auto 1fr auto;  /* Compress header */
  }

  .action-toolbar {
    flex-direction: row;  /* Horizontal on mobile */
    gap: 0.5rem;
  }

  .category-bubbles-row {
    gap: 1rem;  /* Tighter spacing */
  }
}
```

---

## 11. Accessibility Implementation

### Keyboard Navigation
```vue
<div
  role="button"
  :tabindex="category.disabled ? -1 : 0"
  @keydown.enter="selectCategory(category.id)"
  @keydown.space.prevent="selectCategory(category.id)"
>
```

**Patterns**:
- `role="button"` on clickable divs
- `tabindex="0"` for keyboard focus (or `-1` when disabled)
- `@keydown.enter` and `@keydown.space` for keyboard activation
- `:focus-visible` styles for focus indication

### ARIA Attributes
```vue
<button
  :aria-pressed="selectedCategory === category.id"
  :aria-disabled="category.disabled"
  :title="category.label"
>
```

**Patterns**:
- `aria-pressed` for toggle states
- `aria-disabled` for disabled elements (in addition to `:disabled`)
- `title` attributes provide tooltips (read by screen readers)

### Focus Styles
```css
.category-bubble:focus-visible {
  outline: 3px solid rgba(102, 126, 234, 0.8);
  outline-offset: 4px;
}
```

**Educational Design Rationale**:
- **Visible Focus Indicators**: Essential for keyboard-only users (motor disabilities)
- **Skip to Content**: Header navigation allows quick access to Phase1/modes
- **Semantic HTML**: Proper button elements instead of clickable divs where possible

---

## 12. Asset Strategy

### Assets Directory
**Location**: `<repo>/public/ai4artsed-frontend/src/assets/`

**Contents**:
- `base.css` (2KB) - CSS reset/base styles
- `main.css` (359 bytes) - Main styles
- `logo.svg` (276 bytes) - App logo
- `trashy-icon.png` (319KB) - Pixel art mascot

### External Assets (Model Logos)
**Pattern**: Model logos stored externally or in public directory

```vue
<img :src="config.logo" :alt="config.label" class="bubble-logo" />
```

**Examples**:
- Flux logos: `/public/flux_schnell_logo.png`
- OpenAI logo: `/public/openai_logo.png`
- Stability AI logo: `/public/stability_logo.png`

**Rationale**: Separates UI icons (emoji) from brand assets (logos).

---

## 13. Future Considerations

### Potential Icon System Enhancements

#### 1. SVG Icon System (if needed)
```vue
<!-- /src/components/icons/IconPhase1.vue -->
<template>
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor">
    <path d="M10 0 L0 10 L10 20 L20 10 Z" />
  </svg>
</template>
```

**Usage**:
```vue
<script setup>
import IconPhase1 from '@/components/icons/IconPhase1.vue'
</script>

<template>
  <button>
    <IconPhase1 />
    <span>Phase 1</span>
  </button>
</template>
```

**When to Use**:
- Need precise color control
- Platform-independent rendering critical
- Complex icon shapes beyond emoji capabilities

#### 2. Icon Library Integration
**Options**:
- [Lucide Icons](https://lucide.dev/) (Vue 3 support, tree-shakeable)
- [Heroicons](https://heroicons.com/) (Tailwind ecosystem)
- [Material Design Icons](https://fonts.google.com/icons) (widely recognized)

**Trade-offs**:
- **Pro**: Consistent cross-platform rendering, customizable
- **Con**: Bundle size increase, learning curve, maintenance overhead

**Recommendation**: Only consider if emoji limitations become pedagogically problematic.

#### 3. Dynamic Icon Theming
```css
.icon {
  color: var(--icon-color, currentColor);
  filter: var(--icon-filter, none);
}

/* Dark mode example */
@media (prefers-color-scheme: dark) {
  .icon {
    --icon-filter: brightness(0.9);
  }
}
```

**Use Case**: Support for dark/light theme switching (currently app is dark-only).

---

## 14. Educational Design Principles Applied

### 1. Progressive Disclosure
**Pattern**: Icons appear/activate as user progresses through workflow

```vue
<!-- Initially disabled, activates after interception -->
<button :disabled="!areModelBubblesEnabled">
  <img :src="config.logo" />
</button>
```

**Pedagogical Rationale**: Prevents cognitive overload by revealing options only when contextually appropriate.

### 2. Visual Consistency
**Pattern**: Same icon always means same thing across entire app

| Icon | Global Meaning |
|------|----------------|
| 💡 | Creative input/ideation |
| 📋 | Constraints/rules |
| ✨ | AI enhancement |
| 🖼️ | Image content |
| 🎬 | Video content |
| 🔊 | Audio content |

**Pedagogical Rationale**: Builds mental models, reduces cognitive load on repeated use.

### 3. Scaffolding via Visual Hierarchy
**Pattern**: Icon size indicates importance/stage

```css
.bubble-icon { font-size: 1.5rem; }           /* Section headers */
.bubble-emoji-small { font-size: 2rem; }      /* Category selection */
.bubble-emoji-medium { font-size: 2.5rem; }   /* Model selection */
.mode-icon { font-size: 1.5rem; }             /* Mode toggle */
.action-icon { font-size: 1.5rem; }           /* Post-generation actions */
```

**Pedagogical Rationale**: Larger icons draw attention to primary decision points.

### 4. Feedback Loops
**Pattern**: Every interaction has visual acknowledgment

- **Hover**: Border color + transform
- **Active**: Background color + scale
- **Loading**: Spinner animation
- **Success**: Green glow + safety stamp
- **Error**: Red border (not heavily used - app minimizes errors)

**Pedagogical Rationale**: Immediate feedback reinforces cause-effect understanding.

---

## 15. Performance Considerations

### Icon Rendering Performance

**Emoji Rendering**: No network requests, rendered by OS font system
**Logo Images**: Minimal (< 50KB each), cached by browser
**SVG Icons**: Would be inlined in bundle, zero network overhead

### Bundle Size Impact
```
Current approach (emoji):  0 KB icon overhead
SVG icon library:          ~50-100 KB (Lucide)
Icon font (Material):      ~40-80 KB
Full library (FontAwesome): ~900 KB (unacceptable)
```

**Recommendation**: Current emoji strategy optimal for performance.

### Lazy Loading (Assets)
```javascript
// Model logos loaded on-demand
<img :src="config.logo" loading="lazy" />
```

**Pattern**: Browser-native lazy loading for model logos that appear below fold.

---

## 16. Related Documentation

### Frontend Architecture
- **Part 12**: Frontend Architecture (Vue components, stores, routing)
- **Part 21**: This document (Icons & Navigation)

### Backend Integration
- **Part 11**: API Routes (endpoints called by navigation actions)
- **Part 08**: Backend Routing (server-side routing)

### Stage-Specific Views
- **Part 20**: Stage2 Pipeline Capabilities (text_transformation details)
- **Part 01**: 4-Stage Orchestration Flow (backend pipeline stages)

### Design Decisions
- **Part 15**: Key Design Decisions (rationale for emoji-first approach)

---

## 17. Key Takeaways

### Icon Strategy Summary
1. **Emoji-first approach** chosen for educational clarity
2. **Hybrid strategy** for brand logos (model selection)
3. **Consistent patterns** across all views (action toolbar, category bubbles)
4. **Accessibility built-in** (ARIA, keyboard nav, focus styles)

### Navigation Patterns Summary
1. **Eine Perspektive waehlen**: auf der Flussflaeche (`/x2x-flow`), nicht auf einer eigenen Auswahlseite
2. **Modi**: sechs Zeichen in der Kopfzeile (`/`, `/together`, `/contesting`, `/x2x-flow`, `/latent-lab`, `/canvas`)
3. **Bild weiterreichen**: `i2i_transfer_data` in `localStorage`, gelesen vom Fluss (5 Minuten)
4. **Settings**: Global settings button (DSGVO mode)

### Design System Summary
1. **Purple/Blue hover** + **Green active** = consistent interaction language
2. **Fluid typography** via clamp() = responsive by default
3. **Border radius hierarchy**: 6px → 12px → 20px → 50% (circles)
4. **Disabled states visible**: Shows future capabilities

---

**Last Updated**: 2025-12-08
**Contributors**: Analysis based on codebase exploration
