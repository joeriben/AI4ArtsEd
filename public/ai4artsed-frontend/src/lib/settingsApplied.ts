/**
 * The settings were saved and applied. They are an overlay (App.vue): the page
 * under them stands while they change what it may offer -- which provider a
 * language model is reached through, and so which models there are -- and a
 * list a surface read when it was entered would go on offering what was
 * chosen before, and sending to it. A list that depends on the settings asks
 * again when this is called: useChatModels, and the Canvas's own lists
 * (views/canvas_workflow.vue).
 */
const listeners = new Set<() => void>()

/** Runs `cb` whenever the settings have been applied; returns what stops it. */
export function onSettingsApplied(cb: () => void): () => void {
  listeners.add(cb)
  return () => { listeners.delete(cb) }
}

/** Called by the settings once the backend has applied what was saved. */
export function settingsApplied(): void {
  for (const cb of [...listeners]) cb()
}
