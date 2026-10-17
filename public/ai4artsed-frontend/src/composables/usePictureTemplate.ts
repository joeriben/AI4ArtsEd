/**
 * A TEMPLATE that can be READ FROM A PICTURE.
 *
 * Two instruments of the Prompt Interception group let a picture into the field
 * their template stands in: Perspectives on a Template and Aesthetic Poles. A
 * picture dragged onto that field is read as a DESCRIPTION,
 * and the reading then stands in the field, where it can be worked on further.
 * The route is the platform's own — the flow board reads its pictures with it —
 * and the only thing new is where the answer lands.
 *
 * What the surface gets back is the state of that reading and the two handlers
 * the picture field emits into. What it keeps for itself is the field, the row
 * that draws the picture, and the record of its run.
 *
 * Lifted out of `views/latent_lab/perspectives_template.vue` on 2026-09-04, when
 * the second instrument needed the same thing (Rule 13).
 */
import { computed, ref, watch, onBeforeUnmount, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { failureKey } from '@/composables/useGenerationStream'
import { postStreamedRun } from '@/services/directRun'
import { type ReadingFrame } from '@/data/readingFrames'
import { apiBase } from '@/services/labApi'

/**
 * WHERE the line came from, where it was read: the picture, the frame it was
 * read through, and the text that came back.
 */
export interface TemplateOrigin {
  imagePath: string
  frame: string
  text: string
}

export function usePictureTemplate(text: Ref<string>) {
  const { locale } = useI18n()
  const baseUrl = apiBase()

  /** The surface is gone; nothing that comes back late touches it. */
  let alive = true
  onBeforeUnmount(() => { alive = false })

  /** Where the uploaded picture lies on the server, and what it looks like. */
  const picturePath = ref<string>('')
  const picturePreview = ref<string>('')
  const reading = ref(false)
  /** Why the last reading did not come back, as one of the platform's sentences. */
  const readingFailedKey = ref('')

  const templateOrigin = ref<TemplateOrigin | null>(null)

  /** Whether the line standing in the field IS the reading of a picture. */
  const templateFromPicture = computed(
    () => !!templateOrigin.value && text.value === templateOrigin.value.text,
  )

  /**
   * Whether the head of the reference row draws a picture. Two things have to
   * hold at once, and the field alone is neither of them: the line has to BE the
   * reading, and the picture in the field has to be the one it was read from.
   * A picture laid there whose reading is still out — or never came back — is
   * beside a line that came from somewhere else, and drawing it there would say
   * that line was read from it.
   */
  const showsOriginPicture = computed(
    () =>
      !!picturePreview.value &&
      templateFromPicture.value &&
      picturePath.value === templateOrigin.value?.imagePath,
  )

  /**
   * The newest event is the one the surface says. A sentence about a reading that
   * failed is about the picture that was read; a line written since and a run
   * pressed since are newer facts, and the old sentence would stand over them.
   */
  watch(text, () => { readingFailedKey.value = '' })

  /**
   * The frame a picture is read through: the DESCRIPTION, and no choice about it.
   * A template that other pictures are to be made from is what a description
   * gives; the four other frames of the platform (`data/readingFrames.ts`) read a
   * picture rather than restate it, and reading it is what the rows of this
   * surface do afterwards. The id is the backend's own key.
   */
  const FRAME: ReadingFrame = 'descriptive'

  function handlePicture(data: { image_path?: string; preview_url?: string }): void {
    picturePath.value = String(data?.image_path || '')
    picturePreview.value = String(data?.preview_url || '')
    if (picturePath.value) void readPicture()
  }

  /** The picture goes; what was read of it stays, because it is written now. */
  function dropPicture(): void {
    picturePath.value = ''
    picturePreview.value = ''
    readingFailedKey.value = ''
  }

  /**
   * Which reading is the current one. The field is closed while one is out, so a
   * second cannot be asked for from the surface; this holds where a caller goes
   * round the field. A newer reading supersedes an older one: what an older one
   * answers belongs to a state that is gone, and the waiting ends when the NEWEST
   * has ended and not before.
   */
  let readingToken = 0

  /**
   * One picture, read as a description, straight into the template line. The
   * route is the platform's own — the flow board reads its pictures with it — and
   * the only thing new is where the answer lands.
   */
  async function readPicture(): Promise<void> {
    const path = picturePath.value
    if (!path) return
    const usedFrame = FRAME
    const token = ++readingToken
    reading.value = true
    readingFailedKey.value = ''
    try {
      // Streamed, not awaited in one silent POST: a vision model has to be
      // loaded before it can look and may stand in the card's queue first, and
      // the edge in front of the server cuts a request whose origin has sent
      // nothing for about 100 seconds — the reading was then made and thrown
      // away. Every status resolves, so the two readings of it below stay this
      // function's own.
      const res = await postStreamedRun<
        { success?: boolean; analysis?: string; error?: string } | null
      >(
        '/api/media/analyze/image',
        { image_path: path, lang: locale.value, frame: usedFrame },
        { baseUrl, validateStatus: () => true },
      )
      const data = res.data
      // The picture was taken away while this one was still out. What came back
      // belongs to a state that is gone.
      if (!alive || token !== readingToken || picturePath.value !== path) return
      const read = typeof data?.analysis === 'string' ? data.analysis.trim() : ''
      if (res.status >= 200 && res.status < 300 && data?.success && read) {
        templateOrigin.value = { imagePath: path, frame: usedFrame, text: read }
        text.value = read
        return
      }
      // A reader that answered without a reading is the one case that has no
      // cause of its own; everything else the route can end on — a queue that is
      // full, a station that is silent, a model that is not installed — is said
      // the way a failed generation says it, so the cause travels.
      readingFailedKey.value =
        res.status === 502
          ? 'latentLab.interception.models.readingFailed'
          : failureKey('error', typeof data?.error === 'string' ? data.error : '')
    } catch (err: unknown) {
      const e = err as { message?: string }
      if (!alive || token !== readingToken) return
      readingFailedKey.value = failureKey('error', e?.message || '')
    } finally {
      // Only the newest reading ends the waiting. An older one coming back late
      // would open the field while the newer one is still out.
      if (alive && token === readingToken) reading.value = false
    }
  }

  return {
    picturePath,
    picturePreview,
    reading,
    readingFailedKey,
    templateOrigin,
    templateFromPicture,
    showsOriginPicture,
    handlePicture,
    dropPicture,
    FRAME,
  }
}
