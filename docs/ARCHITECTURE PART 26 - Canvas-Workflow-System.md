# ARCHITECTURE PART 26 - Canvas Workflow System

**Status:** AUTHORITATIVE
**Created:** 2026-01-29
**Related:** ARCHITECTURE_CANVAS_EVALUATION_NODES.md

---

## Table of Contents

1. [Overview](#overview)
2. [Pedagogical Framework](#pedagogical-framework)
3. [Node Types](#node-types)
4. [Connection Rules](#connection-rules)
5. [Workflow Execution](#workflow-execution)
6. [Presets & Configurations](#presets--configurations)
7. [Frontend Components](#frontend-components)
8. [Backend API](#backend-api)
9. [Data Structures](#data-structures)

---

## Overview

The Canvas Workflow System is a visual node-based workflow builder for creating custom AI pipelines. Users connect nodes to define data flow from input through transformations to media generation.

### Core Principles

1. **Visual Programming**: Drag-and-drop nodes, connect with lines
2. **DAG Execution**: Directed Acyclic Graph traversal (no cycles currently)
3. **Fan-out Support**: One source can connect to multiple targets (parallel execution)
4. **Safety Transparent**: Stage 1/3 safety handled automatically by DevServer
5. **Streaming Progress**: Real-time SSE updates during execution

### Default Workflow Structure

```
Input → [User-defined nodes] → Collector
```

Every workflow starts with an **Input** node and ends with a **Collector** node.

---

## Pedagogical Framework

### Paradigm: Exploratory Research (Lehrforschung)

Canvas is designed for **collaborative exploration** in workshops, classrooms, or professional development settings. It enables systematic investigation of generative AI behavior through hands-on experimentation.

### Distinction from Technical Systems

Canvas deliberately differs from other modular systems like Max/MSP or ComfyUI:

| Aspect | ComfyUI / Max | Canvas |
|--------|---------------|--------|
| **Primary Focus** | Product optimization | Process exploration |
| **Parameters** | Deep technical control | Minimal technical exposure |
| **Complexity** | Technical complexity | Structural complexity |
| **User Model** | Expert operator | Researcher/Learner |

**Design Decision**: Canvas reduces technical complexity to make **structural complexity** visible and explorable. Users who need fine-grained parameter control can use ComfyUI directly.

### Deconstructing the Control Paradigm

The **Prompt Interception** concept challenges conventional human-AI interaction models at a fundamental level.

**Conventional Model (rejected)**:
```
User → Directive Command → AI → Optimized Output
         ↑
    "User as operator commanding the machine"
```

This design pattern performatively produces **user-subjects** who "operate the machine" - seemingly commanding, yet simultaneously subjected to its logic. Users become commanders who are themselves subordinated: the interface positions them as directive-givers whose agency is reduced to optimizing technical parameters for better outputs. The machine does not serve their creative becoming; rather, they serve the machine's operational requirements.

**Interception Model (Canvas approach)**:
```
User → Input → [LLM Interception] → Transformed Prompt → Generation
                     ↓
         Introduces novelty, unpredictability
         Machine serves creative becoming
```

Prompt Interception breaks this pattern:
- User inputs are **not** understood as technical directives to be optimized
- The LLM introduces **novelty and unpredictability** into the process
- Users and LLM create **new feedback loops** together
- The machine serves the user's creative becoming, not vice versa
- Working "backwards" (from output criteria to input refinement) becomes possible throughout the interface

**Pragmatic Dimension**: Interception also enables creation of appropriately complex prompts - essential for meaningful AI exploration. Simple prompts necessarily produce simplistic, clichéd outputs. Only with complex prompts can one systematically and justifiably experience:
- Biases inherent in the models
- Normative tendencies vs. genuine "creativity"
- **Distinctive characteristics of the system that may be worth exploring** - not only problems to expose, but also productive peculiarities, unexpected capabilities, and generative potentials

### Recursive-Reflexive Workflows: A Novel Approach

Canvas introduces **recursive-reflexive workflows** - a capability not found in other genAI platforms:

```
Input → Interception → Generation → Evaluation ─┬→ Collector (if passed)
              ↑                                  │
              └────── Feedback (if failed) ─────┘
```

**How it works**:
- Evaluation nodes assess outputs against user-defined criteria
- Failed evaluations feed back to upstream nodes (e.g., Interception)
- Workflow iterates until criteria are met (or max iterations reached)
- Users define the criteria - not the system

**Research Applications**:
- **Bias exploration**: How do models respond to different cultural contexts?
- **Normativity vs. "Creativity"**: What produces novel vs. stereotypical outputs?
- **Ethical assessment**: Evaluating LLM (and soon: image) outputs against ethical criteria
- **Comparative analysis**: Mass generation for systematic comparison (hundreds of variations)

**Planned**: Loop functionality for N workflow runs, enabling bulk generation for research datasets.

### Target Groups

| Group | Use Case |
|-------|----------|
| **Older children (12+)** | Structured exploration of AI behavior in educational settings |
| **Educators** | Professional development - understanding genAI for pedagogical integration |
| **Researchers** | Systematic investigation of model behavior, bias, creativity |
| **Cultural education** | Workshop settings for critical AI literacy |

### Relationship to Other Views

Canvas exists alongside other AI4ArtsEd interfaces, each serving different pedagogical needs:

| View | Complexity | Focus | Setting |
|------|------------|-------|---------|
| Text Transformation | Low | Creative doing, collective process | Workshops, classrooms |
| Image Transformation | Low | Visual exploration, immediate results | Art education, media pedagogy |
| Multi-Image | Medium | Comparative visual exploration | Group work, analysis |
| **Canvas** | Higher | Systematic research, mass generation | Research, professional development |

**Origin Story**: The simpler views emerged from research findings that ComfyUI's complexity failed to motivate professional art educators to explore. For non-formal cultural education contexts, such technical complexity would be rejected entirely. The simpler views prioritize **doing** in collective creative settings where genAI is one element among many.

Canvas serves those ready for deeper, systematic exploration - including generating large output sets for comparative analysis.

---

## Node Types

### Overview Table

| Node | Type | Color | Purpose | Multiple? | Mandatory? |
|------|------|-------|---------|-----------|------------|
| **Input Prompt** | `input` | Blue (#3b82f6) | Text input source | No | Yes |
| **Random Prompt** | `random_prompt` | Pink (#ec4899) | LLM-generated creative content | Yes | No |
| **Interception** | `interception` | Purple (#8b5cf6) | Pedagogical transformation | Yes | No |
| **Translation** | `translation` | Amber (#f59e0b) | Language translation | Yes | No |
| **Model Adaption** | `model_adaption` | Teal (#14b8a6) | Prompt optimization for specific models | Yes | No |
| **Generation** | `generation` | Emerald (#10b981) | Media generation (image/audio/video) | Yes | Yes |
| **Evaluation** | `evaluation` | Amber (#f59e0b) | LLM-based judgment with branching | Yes | No |
| **Preview** | `display` | Green (#10b981) | Inline text/media preview | Yes | No |
| **Media Output** | `collector` | Cyan (#06b6d4) | Collects and displays all outputs | No | Yes |
| **Seed** | `seed` | Teal (#14b8a6) | Random seed control for reproducibility | Yes | No |
| **Resolution** | `resolution` | Teal (#14b8a6) | Image dimensions (width/height) | Yes | No |
| **Quality** | `quality` | Teal (#14b8a6) | Generation quality (steps/cfg) | Yes | No |

---

### Node Details

#### 1. Input Prompt (`input`)

**Purpose**: Entry point for user text.

**Configuration**:
- `promptText`: The user's input text

**Connectors**:
- Input: None (source node)
- Output: 1 (text)

**Notes**:
- Only one Input node per workflow
- Required in every workflow

---

#### 2. Random Prompt (`random_prompt`)

**Purpose**: Generate creative content via LLM using presets.

**Configuration**:
- `randomPromptPreset`: Preset type (see [Random Prompt Presets](#random-prompt-presets))
- `randomPromptModel`: LLM model ID
- `randomPromptFilmType`: Film type (only for `photo` preset)

**Presets**:
| Preset | Label (EN/DE) | Description |
|--------|---------------|-------------|
| `clean_image` | Scenic Description / Szenische Beschreibung | Media-neutral image prompt |
| `photo` | Photo Prompt / Foto-Prompt | Realistic photographic prompt with film type |
| `artform` | Artform Transformation / Kunstform-Transformation | Artistic practice instructions |
| `instruction` | Creative Instruction / Kreative Anweisung | Unusual transformation instructions |
| `language` | Language Suggestion / Sprach-Vorschlag | Random world language |

**Connectors**:
- Input: 1 (optional context)
- Output: 1 (generated text)

---

#### 3. Interception (`interception`)

**Purpose**: Pedagogical transformation of text using LLM.

**Configuration**:
- `llmModel`: Selected LLM model
- `interceptionPreset`: Predefined transformation style (see [Interception Presets](#interception-presets))
- `contextPrompt`: Custom transformation instructions (when preset is `user_defined`)

**Connectors**:
- Input: 1 (text)
- Output: 1 (transformed text)

**Notes**:
- Core pedagogical feature - transforms prompts before generation
- 22+ built-in presets available

---

#### 4. Translation (`translation`)

**Purpose**: Language translation with custom prompt.

**Configuration**:
- `llmModel`: Selected LLM model
- `translationPrompt`: Translation instructions (e.g., "Translate to French")

**Connectors**:
- Input: 1 (text)
- Output: 1 (translated text)

---

#### 5. Model Adaption (`model_adaption`)

**Purpose**: Optimize prompts for specific media model architectures.

**Configuration**:
- `modelAdaptionPreset`: Target model type

**Presets**:
| Preset | Description |
|--------|-------------|
| `none` | Pass-through (no adaption) |
| `sd35` | Stable Diffusion 3.5 (CLIP-style keywords) |
| `flux` | Flux (T5-style natural language) |
| `video` | Video models (scenic descriptions) |
| `audio` | Audio/Music models (auditive descriptions) |

**Connectors**:
- Input: 1 (text)
- Output: 1 (adapted text)

---

#### 6. Seed (`seed`)

**Purpose**: Control random seed for reproducible generation.

**Configuration**:
- `seedMode`: `fixed` | `random` | `increment`
- `seedValue`: Fixed seed value (default: 123456789)
- `seedBase`: Base value for increment mode

**Modes**:
| Mode | Behavior |
|------|----------|
| `fixed` | Use specified seed value |
| `random` | Generate random seed per execution |
| `increment` | Base seed + batch index |

**Connectors**:
- Input: None (parameter source node)
- Output: 1 (connects to Generation node)

**Notes**:
- Parameter nodes don't propagate through workflow
- Only affects connected Generation nodes
- Ignored by API-based backends (GPT-Image, Gemini)

---

#### 7. Resolution (`resolution`)

**Purpose**: Set image dimensions for generation.

**Configuration**:
- `resolutionPreset`: `square_1024` | `portrait_768x1344` | `landscape_1344x768` | `custom`
- `resolutionWidth`: Custom width (64-4096)
- `resolutionHeight`: Custom height (64-4096)

**Presets**:
| Preset | Dimensions |
|--------|------------|
| `square_1024` | 1024 × 1024 |
| `portrait_768x1344` | 768 × 1344 |
| `landscape_1344x768` | 1344 × 768 |
| `custom` | User-defined |

**Connectors**:
- Input: None (parameter source node)
- Output: 1 (connects to Generation node)

---

#### 8. Quality (`quality`)

**Purpose**: Control generation quality parameters.

**Configuration**:
- `qualitySteps`: Number of diffusion steps (1-150, default: 25)
- `qualityCfg`: CFG scale (0-30, default: 5.5)

**Connectors**:
- Input: None (parameter source node)
- Output: 1 (connects to Generation node)

**Notes**:
- Higher steps = more detail, slower generation
- CFG controls prompt adherence (too high = artifacts)

---

#### 9. Generation (`generation`)

**Purpose**: Create media (image, audio, video) from text prompt.

**Configuration**:
- `configId`: Output config ID (e.g., `sd35_large`, `flux2_schnell`, `qwen_vl_max`)

**Connectors**:
- Input: 1 (text prompt)
- Output: 1 (media URL/path)

**Notes**:
- Requires config selection via modal
- Multiple generation nodes enable parallel media creation

---

#### 7. Evaluation (`evaluation`)

**Purpose**: LLM-based judgment with optional conditional branching.

**Configuration**:
- `evaluationType`: `fairness` | `creativity` | `bias` | `quality` | `custom`
- `evaluationPrompt`: Evaluation criteria
- `llmModel`: Selected LLM
- `outputType`: `commentary` | `score` | `all`
- `enableBranching`: Enable 3-output branching
- `branchCondition`: `binary` | `threshold`
- `thresholdValue`: Score threshold (0-10)
- `trueLabel` / `falseLabel`: Branch labels

**Connectors (without branching)**:
- Input: 1 (text)
- Output: 1 (evaluation result)

**Connectors (with branching enabled)**:
- Input: 1 (text)
- Outputs: 3
  - **P (Passthrough)**: Original text if passed (green)
  - **C (Commented)**: Text + feedback if failed (orange)
  - **→ (Commentary)**: Feedback only, always active (cyan)

**See**: [ARCHITECTURE_CANVAS_EVALUATION_NODES.md](ARCHITECTURE_CANVAS_EVALUATION_NODES.md) for detailed documentation.

---

#### 8. Preview (`display`)

**Purpose**: Inline visualization of intermediate results.

**Configuration**:
- `title`: Display title
- `displayMode`: `popup` | `inline` | `toast`

**Connectors**:
- Input: 1 (text or media)
- Output: None (terminal node)

**Notes**:
- Acts as a "tap" to observe data flow
- Does not modify or pass data

---

#### 9. Media Output (`collector`)

**Purpose**: Collects and displays all workflow outputs.

**Configuration**: None (automatic collection)

**Connectors**:
- Input: Multiple (fan-in from any node)
- Output: None (terminal node)

**Notes**:
- Only one Collector per workflow
- Required in every workflow
- Aggregates all connected outputs with source attribution

---

## Connection Rules

### Structural Constraints

```typescript
// Terminal nodes (no output connector)
const terminalNodes = ['collector', 'display']

// Source nodes (no input connector)
const sourceNodes = ['input', 'seed', 'resolution', 'quality']
```

### Valid Connections Matrix

| Source ↓ / Target → | input | random_prompt | interception | translation | model_adaption | generation | evaluation | display | collector |
|---------------------|-------|---------------|--------------|-------------|----------------|------------|------------|---------|-----------|
| **input** | - | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **random_prompt** | - | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **interception** | - | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **translation** | - | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **model_adaption** | - | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **generation** | - | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **evaluation** | - | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **display** | - | - | - | - | - | - | - | - | - |
| **collector** | - | - | - | - | - | - | - | - | - |

**Legend**: ✓ = Valid, - = Invalid

### Connection Data Types

Data type compatibility is checked at runtime:
- **Text nodes**: input, random_prompt, interception, translation, model_adaption, evaluation
- **Media nodes**: generation (output is media URL)
- **Any type**: collector, display (accept both)

---

## Workflow Execution

### Execution Model

1. **Trigger**: User clicks "Execute" button
2. **Validation**: Check workflow validity (required nodes, no orphans)
3. **Traversal**: DAG traversal starting from Input node
4. **Streaming**: SSE events for real-time progress
5. **Collection**: Collector aggregates all outputs

### Execution Flow

```
┌─────────────────────────────────────────────────────────┐
│  Frontend: executeWorkflow()                            │
│  ├─ POST /api/canvas/execute-stream                     │
│  ├─ SSE EventSource connection                          │
│  └─ Process events: progress → node_complete → complete │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│  Backend: execute_workflow_stream()                     │
│  ├─ Parse workflow JSON                                 │
│  ├─ Build node map & connection graph                   │
│  ├─ Find input node, start traversal                    │
│  ├─ For each node:                                      │
│  │   ├─ Yield "progress" event                          │
│  │   ├─ Execute node (LLM call, generation, etc.)       │
│  │   ├─ Yield "node_complete" event                     │
│  │   └─ Queue downstream nodes                          │
│  └─ Yield "complete" event with all results             │
└─────────────────────────────────────────────────────────┘
```

### SSE Event Types

| Event | Payload | Description |
|-------|---------|-------------|
| `progress` | `{node_id, node_type, status, message}` | Node starts executing |
| `node_complete` | `{node_id, node_type, output_preview}` | Node finished |
| `complete` | `{results, collectorOutput, cardMeta, executionOrder}` | Workflow complete |

`cardMeta` (since 2026-08-19) holds, per generation node, what its card shows on the BACK: the prompt, the model's
provenance sheet (`services/model_meta.py`), the time, and the sub-run id the media URL carries. It has its own key
because `results` and `collectorOutput` are both in the event, and `results` also holds the collector node — whose
output IS the item list. A sheet placed in a node result or in a collected item was therefore serialised three times
(8.2 kB per sheet for `sd35_large`). Keyed by node id, it is also in the run record for a graph that has no collector
at all — which is every graph the workshop companion authors (`services/canvas_graph_authoring.py`).
| `error` | `{message}` | Execution failed |

### Node Execution Details

```python
def execute_node(node, input_data, data_type):
    node_type = node.get('type')

    if node_type == 'input':
        return node.get('promptText'), 'text', None

    elif node_type == 'random_prompt':
        # Call LLM with preset system prompt
        return generated_text, 'text', None

    elif node_type == 'interception':
        # Load preset context or use custom
        # Call LLM for transformation
        return transformed_text, 'text', None

    elif node_type == 'translation':
        # Call LLM with translation prompt
        return translated_text, 'text', None

    elif node_type == 'model_adaption':
        # Apply CLIP/T5 style adaption
        return adapted_text, 'text', None

    elif node_type == 'generation':
        # Call SwarmUI/ComfyUI backend
        return media_url, 'media', None

    elif node_type == 'evaluation':
        # Call LLM for evaluation
        # Parse COMMENTARY/SCORE/BINARY from response
        return output, 'text', metadata

    elif node_type == 'display':
        # Store for visualization, no output
        return None, None, None

    elif node_type == 'collector':
        # Aggregate input to collection
        return None, None, None
```

---

## Presets & Configurations

### Random Prompt Presets

| ID | Label | System Prompt Focus |
|----|-------|---------------------|
| `clean_image` | Scenic Description | Media-neutral, no camera/photo references |
| `photo` | Photo Prompt | Realistic, film type prefix, everyday motives |
| `artform` | Artform Transformation | Artistic practice perspective, global cultures |
| `instruction` | Creative Instruction | Unusual transformations, wildly creative |
| `language` | Language Suggestion | Random world language selection |

### Photo Film Types

For `photo` preset only:

**Color Negative**: Portra 400, Portra 800, Ektar 100, Fuji Pro 400H, Fuji Superia, CineStill 800T

**Color Slide**: Kodachrome, Ektachrome

**Black & White**: Ilford HP5, Ilford Delta 400, Ilford FP4, Ilford Pan F, Ilford XP2, Tri-X 400

### Interception Presets

| ID | Label (EN) | Label (DE) |
|----|------------|------------|
| `user_defined` | Your Call! | Du bestimmst! |
| `analog_photography_1870s` | Daguerreotype | Daguerreotypie |
| `analog_photography_1970s` | Analog Photography | Analogfotografie |
| `analogue_copy` | Analogue Copy | Analoge Kopie |
| `bauhaus` | Bauhaus | Bauhaus |
| `clichéfilter_v2` | De-Kitsch | Entkitscher |
| `confucianliterati` | Literati | Literati |
| `cooked_negatives` | Cooked Negatives | Gekochte Filmnegative |
| `digital_photography` | Digital Photography | Digitalfotografie |
| `forceful` | Forceful | kraftvoll |
| `hunkydoryharmonizer` | Sweetener | Verniedlicher |
| `jugendsprache` | Slang | Jugendslang |
| `mad_world` | mad world | verrückt |
| `one_world` | One World | Eine Welt |
| `overdrive` | Amplifier | Übertreiber! |
| `p5js_simplifier` | Listifier | Auflister |
| `piglatin` | Word Game | Sprachspiel |
| `planetarizer` | Planetarizer | Planetarisierer |
| `renaissance` | Renaissance | Renaissance |
| `sensitive` | Sensitive | sensibel |
| `stillepost` | Telephone | Stille Post |
| `technicaldrawing` | Technical | Technisch |
| `tellastory` | Your Story | Deine Geschichte |
| `theopposite` | On the Contrary! | Im Gegenteil! |

### Model Adaption Presets

| ID | Target Model | Prompt Style |
|----|--------------|--------------|
| `none` | Pass-through | No modification |
| `sd35` | Stable Diffusion 3.5 | CLIP-style keywords |
| `flux` | Flux | T5-style natural language |
| `video` | Video models | Scenic descriptions |
| `audio` | Audio/Music | Auditive descriptions |

---

## Frontend Components

### Component Structure

```
public/ai4artsed-frontend/src/
├── views/
│   └── canvas_workflow.vue       # Main canvas view
├── components/canvas/
│   ├── CanvasWorkspace.vue       # Canvas area with grid
│   ├── StageModule.vue           # Individual node component
│   ├── ConnectionLine.vue        # SVG connection lines
│   ├── ModulePalette.vue         # Node type palette
│   └── ConfigSelectorModal.vue   # Generation config modal
├── stores/
│   └── canvas.ts                 # Pinia state management
└── types/
    └── canvas.ts                 # TypeScript definitions
```

### Pinia Store (`canvas.ts`)

**State**:
- `workflow`: Current workflow definition
- `selectedNodeId`: Currently selected node
- `connectingFromId`: Node being connected from
- `llmModels`: Available LLM models
- `outputConfigs`: Available generation configs
- `isExecuting`: Execution in progress
- `executionResults`: Node results map
- `collectorOutput`: Aggregated collector items
- `cardMeta`: per generation node, the card's back side (prompt, model sheet, time, sub-run id)
- `activeNodeId`: Currently animating node
- `currentProgress`: SSE progress state

**Actions**:
- `addNode(type, x, y)`: Create new node
- `updateNode(id, config)`: Update node configuration
- `deleteNode(id)`: Remove node and connections
- `addConnection(sourceId, targetId)`: Create connection
- `deleteConnection(sourceId, targetId)`: Remove connection
- `executeWorkflow()`: Start SSE execution
- `loadAllConfigs()`: Fetch LLM models and output configs

---

## Backend API

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/canvas/llm-models` | LLM models: the local ones live from the GPU service, the cloud ones from the platform's chat-model list (since 2026-09-12) |
| GET | `/api/canvas/output-configs` | List available generation configs |
| GET | `/api/canvas/interception-configs` | List interception presets |
| GET | `/api/canvas/interception-context/:id` | Get preset context prompt |
| POST | `/api/canvas/execute-stream` | Execute workflow (SSE streaming) |

### LLM Model Selection

Curated models per provider:

| Provider | Small | Medium | Top | DSGVO |
|----------|-------|--------|-----|-------|
| **Anthropic** | Claude 3.5 Haiku | Claude 3.5 Sonnet | Claude Sonnet 4 | No |
| **Mistral** | Ministral 8B | Mistral Small 3.1 | Mistral Large | Yes |
| **Google** | Gemma 3 4B | Gemini 2.0 Flash | Gemini 2.5 Pro | No |
| **Meta** | Llama 3.2 3B | Llama 3.3 70B | Llama 4 Maverick | No |
| **Local** | GPT-OSS 8B | GPT-OSS 20B | GPT-OSS 120B | Yes |

Plus: Dynamic Ollama models from local instance.

---

## Data Structures

### CanvasNode

```typescript
interface CanvasNode {
  id: string
  type: StageType
  x: number
  y: number
  config: Record<string, unknown>

  // Generation
  configId?: string

  // Interception
  interceptionPreset?: InterceptionPreset
  llmModel?: string
  contextPrompt?: string

  // Translation
  translationPrompt?: string

  // Input
  promptText?: string

  // Display
  width?: number
  height?: number
  title?: string
  displayMode?: 'popup' | 'inline' | 'toast'

  // Evaluation
  evaluationType?: 'fairness' | 'creativity' | 'bias' | 'quality' | 'custom'
  evaluationPrompt?: string
  outputType?: 'commentary' | 'score' | 'all'
  enableBranching?: boolean
  branchCondition?: 'binary' | 'threshold'
  thresholdValue?: number
  trueLabel?: string
  falseLabel?: string

  // Random Prompt
  randomPromptPreset?: RandomPromptPreset
  randomPromptModel?: string
  randomPromptFilmType?: PhotoFilmType

  // Model Adaption
  modelAdaptionPreset?: ModelAdaptionPreset

  // Seed
  seedMode?: 'fixed' | 'random' | 'increment'
  seedValue?: number
  seedBase?: number

  // Resolution
  resolutionPreset?: 'square_1024' | 'portrait_768x1344' | 'landscape_1344x768' | 'custom'
  resolutionWidth?: number
  resolutionHeight?: number

  // Quality
  qualitySteps?: number
  qualityCfg?: number
}
```

### CanvasConnection

```typescript
interface CanvasConnection {
  sourceId: string
  targetId: string
  label?: string    // For evaluation branches: 'passthrough' | 'commented' | 'commentary'
  active?: boolean  // Set during execution for conditional paths
}
```

### CanvasWorkflow

```typescript
interface CanvasWorkflow {
  id: string
  name: string
  description?: string
  type: 'canvas_workflow'
  nodes: CanvasNode[]
  connections: CanvasConnection[]
  loops?: LoopConfig
  automation?: AutomationConfig
  createdAt?: string
  updatedAt?: string
}
```

---

## Parameter Injection System

### Overview

Parameter nodes (Seed, Resolution, Quality) allow users to control generation parameters without exposing technical complexity. Parameters are injected into the pipeline at execution time.

### Architecture

```
Parameter Nodes (source)     Workflow Nodes           Generation
┌──────────────────┐        ┌─────────────────┐      ┌──────────────┐
│ Seed Node        │───┐    │                 │      │              │
│ seedValue: 999   │   │    │ Input → Interc. │──────│  Generation  │
└──────────────────┘   │    │                 │      │              │
┌──────────────────┐   ├───▶│                 │      │ Collects:    │
│ Resolution Node  │───┘    └─────────────────┘      │ - seed       │
│ 1920 × 1080      │                                 │ - width      │
└──────────────────┘                                 │ - height     │
                                                     │ - steps      │
                                                     │ - cfg        │
                                                     └──────────────┘
                                                            │
                                                            ▼
                                                     Pipeline Executor
                                                     custom_placeholders
```

### Execution Model

1. **Parameter nodes are source nodes** - They are executed first, like Input nodes
2. **No downstream propagation** - Parameter nodes return `[]` from `_get_next_nodes()`
3. **Collection at Generation** - Generation node queries connected parameter nodes
4. **Graceful ignore** - Params not in config's `input_mappings` are silently ignored

### Parameter Support by Backend

| Parameter | SD3.5 | Flux2 | GPT-Image | Gemini | ACEnet | Wan22 |
|-----------|:-----:|:-----:|:---------:|:------:|:------:|:-----:|
| `seed` | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| `width` | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| `height` | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| `steps` | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| `cfg` | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| `negative_prompt` | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |

**Note**: API-based backends (GPT-Image, Gemini) use different parameter systems and ignore ComfyUI-style parameters.

### useGenerationStream Integration

Other Vue views can inject parameters via the composable:

```typescript
import { useGenerationStream } from '@/composables/useGenerationStream'

const { startGeneration } = useGenerationStream()

await startGeneration({
  prompt: 'A sunset',
  outputConfig: 'sd35_large',
  safetyLevel: 'youth',
  // Parameter injection (all optional):
  seed: 123456789,
  width: 1920,
  height: 1080,
  steps: 30,
  cfg: 7.0,
  negative_prompt: 'blurry, low quality'
})
```

### Backend Implementation

Parameters flow through:
1. **SSE Endpoint** (`/api/schema/pipeline/generation`) - Parses query params
2. **`execute_stage4_generation_only()`** - Accepts optional params
3. **`custom_placeholders`** - Injected into PipelineContext
4. **Pipeline Executor** - Applies params via `input_mappings`

---

## Example Workflows

### Simple Text-to-Image

```
Input → Interception → Generation → Collector
```

### Parallel Generation

```
Input → Interception ─┬→ Generation (SD3.5) ─┬→ Collector
                      └→ Generation (Flux)  ─┘
```

### With Evaluation Feedback Loop

```
Input → Interception → Generation → Evaluation ─┬→ (P) Collector
                 ↑                              └→ (C) Interception
                 └────────────────────────────────┘
```

### Full Pipeline

```
Input → Random Prompt → Interception → Model Adaption → Generation → Collector
                              ↓
                           Preview
```

### With Parameter Nodes

```
Seed (fixed: 999) ──────────────────────────┐
Resolution (1920×1080) ─────────────────────┼──→ Generation → Collector
Quality (steps: 30, cfg: 7) ────────────────┘         ↑
                                                      │
Input → Interception ─────────────────────────────────┘
```

---

## Related Documentation

- [ARCHITECTURE_CANVAS_EVALUATION_NODES.md](ARCHITECTURE_CANVAS_EVALUATION_NODES.md) - Detailed evaluation node architecture
- [ARCHITECTURE PART 01](ARCHITECTURE%20PART%2001%20-%204-Stage%20Orchestration%20Flow.md) - Core pipeline system
- [ARCHITECTURE PART 12](ARCHITECTURE%20PART%2012%20-%20Frontend-Architecture.md) - Frontend architecture

---

**Document Status:** Complete
**Last Updated:** 2026-02-01 (Parameter Injection)
