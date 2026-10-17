/**
 * A file out of the browser and onto the disk, under a name that leads back to
 * the run it came from.
 *
 * Rule 13. The same three lines stood in eleven places, in two families that
 * behave differently: one hangs the address itself on an `<a download>`, the
 * other fetches the bytes first and hands the anchor a blob. This is the second,
 * because the two part exactly where it matters — `download` is honoured only
 * for a same-origin href, and a browser handed a foreign one NAVIGATES to the
 * picture instead of saving it. On a surface inside a workshop that means the
 * raster the reader was working on is gone from the screen.
 */

/**
 * Fetch and hand over.
 *
 * @returns what went wrong, or an empty string where the file reached the disk.
 *   The CAUSE and not a flag: a surface with a line to say it in says what
 *   happened, and a download that does nothing otherwise looks exactly like a
 *   button that was never wired to anything. It is written to the console as
 *   well, with the address, for the surfaces that have nowhere to put it.
 */
export async function downloadMedia(url: string, filename: string): Promise<string> {
  if (!url) return 'no address'
  try {
    const answer = await fetch(url)
    if (!answer.ok) throw new Error(`${answer.status} ${answer.statusText}`)
    const blob = await answer.blob()
    return downloadBlob(blob, withExtensionOf(filename, blob.type))
  } catch (err) {
    console.error(`[download] ${filename} from ${url}:`, err)
    return (err as Error)?.message || String(err)
  }
}

/**
 * Hand bytes the page already holds to the disk: a file the page writes itself
 * (a Canvas workflow) rather than one it fetches. The second half of
 * `downloadMedia`, and the same contract: the cause, or an empty string.
 */
export function downloadBlob(blob: Blob, filename: string): string {
  let blobUrl = ''
  try {
    blobUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = filename
    link.click()
    return ''
  } catch (err) {
    console.error(`[download] ${filename}:`, err)
    return (err as Error)?.message || String(err)
  } finally {
    // After the click has been handed on, rather than in the same breath: the
    // browser reads the blob asynchronously, and an address given back at once
    // is a save that fails on the slower of two machines and works on the other.
    if (blobUrl) {
      const held = blobUrl
      setTimeout(() => URL.revokeObjectURL(held), 60_000)
    }
  }
}

/**
 * The extension a medium's file gets before anything is fetched, by media
 * type. ONE table: five surfaces carried their own until 2026-10-10, and two
 * of them gave audio another extension than the other three (finding S-043 of the code review of 2026-10-10). What
 * the server actually serves wins once the bytes are here (`withExtensionOf`
 * in `downloadMedia`); this table is the name the request starts with.
 */
const EXTENSION_BY_MEDIA_TYPE: Record<string, string> = {
  image: 'png', audio: 'wav', video: 'mp4', music: 'mp3', '3d': 'glb',
  code: 'js', composition: 'mp4', p5: 'js', tonejs: 'js',
}

export function mediaExtension(mediaType: string | null | undefined): string {
  return EXTENSION_BY_MEDIA_TYPE[mediaType || ''] || 'bin'
}

/** The extension the served type says, where it says one. */
const EXTENSION_BY_MIME: Record<string, string> = {
  'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/gif': 'gif',
  'image/svg+xml': 'svg',
  'audio/wav': 'wav', 'audio/x-wav': 'wav', 'audio/wave': 'wav', 'audio/mpeg': 'mp3',
  'audio/mp3': 'mp3', 'audio/flac': 'flac', 'audio/ogg': 'ogg', 'audio/mp4': 'm4a',
  'video/mp4': 'mp4', 'video/webm': 'webm',
  'model/gltf-binary': 'glb', 'model/gltf+json': 'gltf',
  'application/javascript': 'js', 'text/javascript': 'js',
}

/**
 * The file name with the extension the served type says. A name whose
 * extension already agrees, and a type the table does not know (an empty
 * one, `application/octet-stream`), leave the name as it was: the recorder
 * sniffs an audio file for WAV or MP3 before it names it, and the media
 * routes serve the type of the file they hold, so the download carries the
 * extension that opens it.
 */
export function withExtensionOf(filename: string, mime: string | null | undefined): string {
  const [type = ''] = (mime || '').split(';')
  const ext = EXTENSION_BY_MIME[type.trim().toLowerCase()]
  if (!ext) return filename
  const dot = filename.lastIndexOf('.')
  const stem = dot > 0 ? filename.slice(0, dot) : filename
  const had = dot > 0 ? filename.slice(dot + 1).toLowerCase() : ''
  if (had === ext || (had === 'jpeg' && ext === 'jpg')) return filename
  return `${stem}.${ext}`
}

/**
 * The name that file gets: a word for the surface, then what identifies the
 * picture on it, then the extension. Parts are joined by `_`, the words inside a
 * part by `-`, and empty parts fall away rather than leaving `__` behind.
 */
export function mediaFileName(
  stem: string,
  parts: Array<string | number | null | undefined>,
  ext = 'png',
): string {
  const words = [stem, ...parts].map(part => fileNamePart(part)).filter(Boolean)
  return `${withinBytes(words.join('_'), NAME_BYTES) || 'download'}.${ext}`
}

/**
 * Letters the German convention writes out rather than strips (ä → ae, as in
 * DIN 5007-2 and every German address that cannot carry an umlaut), and the
 * Latin letters that carry no separable mark and so would otherwise vanish.
 */
const SPELLED_OUT: Record<string, string> = {
  ä: 'ae', ö: 'oe', ü: 'ue', Ä: 'Ae', Ö: 'Oe', Ü: 'Ue', ß: 'ss', ẞ: 'SS',
  æ: 'ae', Æ: 'Ae', œ: 'oe', Œ: 'Oe', ø: 'o', Ø: 'O', ł: 'l', Ł: 'L',
  đ: 'd', Đ: 'D', ð: 'd', Ð: 'D', þ: 'th', Þ: 'Th', ı: 'i',
}

/** Where a part is cut, in characters. */
const PART_CHARS = 32
/**
 * Where a whole name is cut, in BYTES: file systems count bytes (255 on APFS,
 * ext4 and NTFS alike), and a Korean or Arabic character is three or two of
 * them. Kept well below the limit, because a browser that finds the name taken
 * adds ` (1)` to it.
 */
const NAME_BYTES = 200

/**
 * One part of a file name, as it travels between machines.
 *
 * Latin script is written in the POSIX portable file name characters (letters,
 * digits, `-`): the German letters are spelled out, every other letter loses
 * its mark (é → e, ğ → g). Those names survive a zip archive, an e-mail
 * attachment and a USB stick formatted elsewhere, which an umlaut does not
 * reliably do. Letters of the platform's other scripts (Cyrillic, Hangul,
 * Hebrew, Arabic) stay as they are written — there is no transliteration that
 * keeps them readable, and stripping them turned every such word into nothing.
 * Everything that is not a letter or a digit becomes one `-`.
 */
export function fileNamePart(raw: unknown, max = PART_CHARS): string {
  let out = ''
  // Whether the last letter written was of another script: a combining mark
  // belongs to that letter there, and to nothing a Latin name can carry here.
  let foreign = false
  for (const ch of String(raw ?? '').normalize('NFC')) {
    const spelled = SPELLED_OUT[ch]
    if (spelled) {
      out += spelled
      foreign = false
    } else if (/[A-Za-z0-9]/.test(ch)) {
      out += ch
      foreign = false
    } else if (/\p{Script=Latin}/u.test(ch)) {
      const bare = ch.normalize('NFD').replace(/\p{M}+/gu, '')
      out += /^[A-Za-z]+$/.test(bare) ? bare : '-'
      foreign = false
    } else if (/\p{M}/u.test(ch)) {
      if (foreign) out += ch
    } else if (/[\p{L}\p{N}]/u.test(ch)) {
      out += ch
      foreign = true
    } else {
      out += '-'
      foreign = false
    }
  }
  const whole = Array.from(out.replace(/-+/g, '-').replace(/^-|-$/g, ''))
  if (whole.length <= max) return whole.join('')
  // Cut at a word where there is one in the second half, so a prompt ends on a
  // word rather than on half of one.
  const cut = whole.slice(0, max).join('')
  // A cut that falls just before a dash already ends on a whole word.
  if (whole[max] === '-') return cut.replace(/-+$/, '')
  const lastDash = cut.lastIndexOf('-')
  return (lastDash > max / 2 ? cut.slice(0, lastDash) : cut).replace(/-+$/, '')
}

function withinBytes(name: string, bytes: number): string {
  const encoder = new TextEncoder()
  if (encoder.encode(name).length <= bytes) return name
  const chars = Array.from(name)
  while (chars.length && encoder.encode(chars.join('')).length > bytes) chars.pop()
  return chars.join('').replace(/[-_]+$/, '')
}

/**
 * The day and the minute a file is named by, in the order a folder sorts:
 * `2026-10-01` and `1432`, local time — the clock the person saving it reads.
 */
export function fileDateParts(when: Date | number = new Date()): [string, string] {
  const d = typeof when === 'number' ? new Date(when) : when
  const two = (n: number) => String(n).padStart(2, '0')
  return [
    `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())}`,
    `${two(d.getHours())}${two(d.getMinutes())}`,
  ]
}

/**
 * A run id as it goes into a file name: without the prefix every id on this
 * platform carries, which would otherwise be the same six characters in front of
 * every file in the folder.
 */
export function runStem(id: string | null | undefined): string {
  return (id || '').replace(/^(run|lab)_/, '')
}
