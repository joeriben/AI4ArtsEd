import { ref } from 'vue'

/**
 * Composable that persists <details> open/closed state in localStorage.
 *
 * Usage:
 *   const { isOpen, onToggle } = useDetailsState('my_key', false)
 *   <details :open="isOpen" @toggle="onToggle">
 *
 * `setOpen` opens or closes the section from code and stores that: a section
 * that is not rendered (yet) fires no `toggle`, so `onToggle` would never store
 * the change.
 */
export function useDetailsState(key: string, defaultOpen = false) {
  const stored = localStorage.getItem(key)
  const isOpen = ref(stored === 'true' || (stored === null && defaultOpen))

  function onToggle(event: Event) {
    const details = event.target as HTMLDetailsElement
    isOpen.value = details.open
    localStorage.setItem(key, String(details.open))
  }

  function setOpen(open: boolean) {
    isOpen.value = open
    localStorage.setItem(key, String(open))
  }

  return { isOpen, onToggle, setOpen }
}
