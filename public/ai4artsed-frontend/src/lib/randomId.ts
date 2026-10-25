/**
 * One place where this browser draws an id.
 *
 * The device identity (composables/useDeviceId.ts) draws one here, with a
 * fallback for a browser without `crypto.randomUUID` — which is not an exotic
 * case here: that function
 * is only there on a trustworthy origin, so a classroom iPad that reaches this
 * machine over plain http on the network takes the fallback every time.
 *
 * Randomness only. What a caller wants around it — a date, a moment, a length —
 * it adds itself, because those differ and only the drawing is the same.
 */
export function randomId(): string {
  // `globalThis.` rather than a bare `crypto`: the optional chain guards the
  // property, not the name, and a run without that global at all — a test, a
  // render on the server — would otherwise raise instead of falling back.
  // `||` rather than `??` for the same kind of reason: a polyfill that answers
  // with an empty string has answered with nothing.
  return globalThis.crypto?.randomUUID?.() || Math.random().toString(36).slice(2)
}
