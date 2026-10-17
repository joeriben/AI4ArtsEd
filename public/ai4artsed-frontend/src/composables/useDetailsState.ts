import { ref } from 'vue'

/**
 * Composable that persists <details> open/closed state in localStorage.
 *
 * Usage:
 *   const { isOpen, onToggle } = useDetailsState('my_key', false)
 *   <details :open="isOpen" @toggle="onToggle">
 */
export function useDetailsState(key: string, defaultOpen = false) {
  const stored = localStorage.getItem(key)
  const isOpen = ref(stored === 'true' || (stored === null && defaultOpen))

  function onToggle(event: Event) {
    const details = event.target as HTMLDetailsElement
    isOpen.value = details.open
    localStorage.setItem(key, String(details.open))
  }

  return { isOpen, onToggle }
}
