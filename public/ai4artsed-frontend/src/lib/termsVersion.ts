/**
 * The version of the conditions of use is the date its wording was last
 * changed, as the server names it ("2026-03-17", TERMS_VERSION in
 * devserver/my_app/lab/terms.py). The sign-in page and "My area" show it as a
 * date in the reader's language (views/LoginView.vue, views/AccountView.vue).
 */

/** The version as a date in `locale`; the version as given where it is no
 *  date. A calendar date has no time zone: it is read and written in UTC, so
 *  that no zone west of Greenwich shows the day before. */
export function formatTermsVersion(version: string, locale: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(version)) return version
  const day = new Date(`${version}T00:00:00Z`)
  if (Number.isNaN(day.getTime())) return version
  try {
    return day.toLocaleDateString(locale, { timeZone: 'UTC' })
  } catch {
    return day.toLocaleDateString(undefined, { timeZone: 'UTC' })
  }
}

/** When an agreement was given (an ISO time from the server), as a date and
 *  a time of day in `locale` and the reader's zone; null where the time is
 *  unreadable. */
export function formatAgreedAt(iso: string | null, locale: string): { date: string; time: string } | null {
  if (iso === null) return null
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) return null
  try {
    return {
      date: at.toLocaleDateString(locale),
      time: at.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' }),
    }
  } catch {
    return {
      date: at.toLocaleDateString(),
      time: at.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }),
    }
  }
}
