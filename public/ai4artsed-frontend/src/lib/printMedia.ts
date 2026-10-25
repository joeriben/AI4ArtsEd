/**
 * A picture onto paper: a document of its own with the picture in it, which
 * prints itself once the picture has loaded. Rule 13 — this stood in six
 * places character for character until 2026-10-10 (three comparison views,
 * the favourites bar, the Canvas drawer, the direct view), and the Flow wrote
 * a document of its own for the same thing. The document is written here
 * rather than the address opened as a page: a browser refuses to OPEN a
 * `data:` address (a sketch's picture, a captured frame) in a window of its
 * own, and shows it inside a page it was given. The button itself is `print`
 * of MediaActionBar; a surface that answers it calls this.
 */
export function printMedia(url: string | null | undefined): void {
  if (!url) return
  const printWindow = window.open('', '_blank')
  if (!printWindow) return
  const doc = printWindow.document
  doc.title = 'ai4artsed'
  const picture = doc.createElement('img')
  picture.style.maxWidth = '100%'
  picture.onload = () => printWindow.print()
  picture.src = url
  doc.body.appendChild(picture)
}
