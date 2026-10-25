/**
 * BOARD MEMORY — what the Together surface keeps across a reload.
 *
 * WHY IT IS HERE AND NOT IN THE JOURNAL
 *   The journal is the workshop's record and lives on the server: the dialogue,
 *   the media intents, what came of them. What this keeps is a different and
 *   smaller thing, and it belongs to the browser — WHERE the cards lie on the
 *   board, which of them are open, what somebody wrote on a note. Losing it
 *   must never mean losing the record, and it never does: the two are written
 *   separately and read separately.
 *
 * IT ROTATES WITH THE DEVICE ID
 *   One board is kept, stamped with the device id it was written under. That id
 *   carries the date (`composables/useDeviceId.ts`), so a shared iPad opens the
 *   next day on an empty surface — the protection every other store on this
 *   platform has, and not a rule invented here.
 *
 * IT IS ALLOWED TO FAIL
 *   A private window refuses `localStorage` and a full quota throws. Nothing
 *   here raises: a board that could not be written is a board that comes back
 *   empty, which is exactly what happened before any of this existed.
 *
 * THE PAYLOAD IS THE VIEW'S BUSINESS
 *   This module knows the envelope — the key, the version, the device stamp —
 *   and nothing about what a card is. `views/resona.vue` decides what survives
 *   a reload and writes that decision down in one place, where the shapes are
 *   in scope.
 */

const KEY = 'resona_board'

/** Raised when the shape the view writes changes; an older board is dropped
 *  rather than read wrong. */
const VERSION = 1

export type BoardPayload = Record<string, unknown>

interface Envelope {
  version: number
  deviceId: string
  savedAt: number
  board: BoardPayload
}

export function readBoard(deviceId: string): BoardPayload | null {
  let raw: string | null = null
  try {
    raw = localStorage.getItem(KEY)
  } catch {
    return null
  }
  if (!raw) return null
  try {
    const env = JSON.parse(raw) as Envelope | null
    if (!env || env.version !== VERSION) return null
    // Another browser identity, or the day has turned.
    if (env.deviceId !== deviceId) return null
    return env.board ?? null
  } catch {
    return null
  }
}

export function writeBoard(deviceId: string, board: BoardPayload): void {
  const env: Envelope = { version: VERSION, deviceId, savedAt: Date.now(), board }
  try {
    localStorage.setItem(KEY, JSON.stringify(env))
  } catch {
    // Out of room, or storage refused. What stands there now is a board from
    // some earlier moment of this same session, and a surface that comes back
    // half as it was left is worse than one that comes back empty.
    forgetBoard()
  }
}

export function forgetBoard(): void {
  try {
    localStorage.removeItem(KEY)
  } catch {
    // Nothing further to do: the board was never kept in the first place.
  }
}
