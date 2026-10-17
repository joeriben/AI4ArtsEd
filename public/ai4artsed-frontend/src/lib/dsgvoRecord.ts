/**
 * What is RECORDED about the data path of ONE service, read from the register
 * (`hardware_matrix.json`) under the one rule: a status about somebody else's
 * service without a reason is not a status. Both halves live in the register --
 * the flag and the line saying on what grounds it was set -- and a flag standing
 * on its own reads as "nothing recorded", here and in the backend, where
 * `settings_routes._recorded_conformity` applies the same rule.
 *
 * `requireNote` is false only for the local entry: that nothing leaves this
 * machine is a property of the installation, not a claim about a vendor.
 *
 * The rule stood in `ModelMatrixTab` alone while the API tab of the settings
 * wrote its own verdict per provider into i18n strings; both read it here since
 * 2026-09-10.
 */
export interface DsgvoRecordSource {
  DSGVO_CONFORMITY?: boolean | null
  DSGVO_NOTE?: string
}

export interface DsgvoRecord {
  recorded: boolean | null
  note: string
}

/**
 * The word for one of the three states, for a place that can hold a word and
 * not the badge -- the option text of a native select. The badge
 * (`components/DsgvoBadge.vue`) reads the same three here, so the two never
 * say different things about the same state.
 */
export function dsgvoWord(
  recorded: boolean | null | undefined,
  t: (key: string) => string
): string {
  if (recorded === true) return t('settings.backendStatus.dsgvoCompliant')
  if (recorded === false) return t('settings.backendStatus.dsgvoNotCompliant')
  return t('settings.backendStatus.dsgvoNoRecord')
}

export function readDsgvoRecord(
  preset?: DsgvoRecordSource | null,
  requireNote = true
): DsgvoRecord {
  const note = (preset?.DSGVO_NOTE || '').trim()
  const flag = preset?.DSGVO_CONFORMITY
  if (flag === null || flag === undefined) return { recorded: null, note }
  if (requireNote && !note) return { recorded: null, note }
  return { recorded: Boolean(flag), note }
}
