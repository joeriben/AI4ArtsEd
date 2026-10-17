/**
 * Cursor-Rechts nimmt das Beispiel an.
 *
 * Ein leeres Eingabefeld zeigt sein Beispiel als Platzhalter. Wer die
 * Rechts-Taste drueckt, bekommt genau diesen Text ins Feld geschrieben,
 * statt ihn abzutippen. Steht schon Text im Feld, bleibt die Taste die
 * gewoehnliche Cursor-Bewegung — die beiden Bedeutungen koennen einander
 * nicht in die Quere kommen.
 *
 * Welche Felder mitmachen, entscheidet der Platzhalter selbst: ein Beispiel
 * traegt in jedem Sprachstand eine Marke ("e.g.", "z.B.", "oern.", "ye:",
 * "napr.", "p. ex."), eine Beschriftung wie "Search..." traegt keine. Die
 * Marke wird beim Annehmen abgeschnitten — ins Feld kommt der Prompt, nicht
 * seine Ankuendigung.
 *
 * Ein Feld traegt sein Beispiel bewusst ohne Marke (Ideen-Feld im Fluss); es
 * meldet sich per `data-example` an. Der Quellprompt der Decomposition stand
 * hier bis 2026-09-05 daneben — die Marke sass dort an einem `MediaInputBox`,
 * dessen Textfeld ein contenteditable ist, und der Horcher unten nimmt nur
 * `input`/`textarea`: sie hat nie gewirkt. Das Feld hat seither die
 * Beispiel-Liste (`components/PromptExamples.vue`) ueber sich.
 * Felder, deren "e.g." ein FORMAT beschreibt statt eines Wertes
 * ("e.g. Surname, F. — or several"), melden sich per `data-example="no"` ab.
 */

const MARKER = /^(e\.g\.|z\.B\.|örn?\.|예|напр\.|p\.\s?ex\.|par\s?ex\.)\s*[:.,]?\s*/i

/** Nur Freitext nimmt an — nicht Passwort, Zahl, Datum, Farbe. */
const FREE_TEXT_TYPES = new Set(['text', 'search', ''])

type Field = HTMLInputElement | HTMLTextAreaElement

function ready(el: Field): boolean {
  if (el.disabled || el.readOnly) return false
  if (el.dataset.example === 'no') return false
  if (el.value !== '') return false
  if (el instanceof HTMLInputElement && !FREE_TEXT_TYPES.has(el.type)) return false
  return Boolean(el.placeholder)
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key !== 'ArrowRight') return
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return
  if (event.isComposing) return

  const el = event.target
  if (!(el instanceof HTMLInputElement) && !(el instanceof HTMLTextAreaElement)) return
  if (!ready(el)) return

  const placeholder = el.placeholder
  const example = placeholder.replace(MARKER, '')

  // Ohne Marke nimmt nur an, wer sich ausdruecklich angemeldet hat.
  if (example === placeholder && el.dataset.example === undefined) return
  if (!example) return

  event.preventDefault()
  el.value = example
  // v-model haengt am input-Event, v-model.lazy am change-Event.
  el.dispatchEvent(new Event('input', { bubbles: true }))
  el.dispatchEvent(new Event('change', { bubbles: true }))
}

export function installExampleAccept(): void {
  document.addEventListener('keydown', onKeydown, true)
}
