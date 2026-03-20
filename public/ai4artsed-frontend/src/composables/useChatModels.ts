/**
 * Shared chat model list for Compare Hub tabs.
 * Single source of truth — no duplicate model lists in views.
 * All cloud models route via Mammouth (DSGVO-compliant EU proxy).
 */

export interface ChatModelOption {
  id: string
  label: string
}

export const chatModels: ChatModelOption[] = [
  { id: '', label: 'Default (Settings)' },
  // Cloud via Mammouth (DSGVO-compliant)
  { id: 'mammouth/claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
  { id: 'mammouth/claude-opus-4-6', label: 'Claude Opus 4.6' },
  { id: 'mammouth/claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5' },
  // Local (Ollama)
  { id: 'local/qwen3:32b', label: 'Qwen 3 32B (local)' },
  { id: 'local/qwen3:4b', label: 'Qwen 3 4B (local, fast)' },
  { id: 'local/deepseek-r1:32b', label: 'DeepSeek R1 32B (local)' },
  { id: 'local/mistral-small:24b', label: 'Mistral Small 24B (local)' },
]
