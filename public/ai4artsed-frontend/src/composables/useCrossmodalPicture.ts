/**
 * The ONE picture the Crossmodal Lab's two image instruments work on.
 *
 * MMAudio and ImageBind Guidance ask the same thing of a photograph — the first
 * makes sound out of it, the second steers sound towards it — and until
 * 2026-09-05 they were two tabs of one file sharing one pair of refs, on
 * purpose: a visitor uploads a picture on the one, switches to the other and
 * the picture is still there, so the two readings are of the SAME picture and
 * can be compared. Splitting the file into two gave each a private copy and the
 * field emptied on every switch — with it went ImageBind Guidance's trigger,
 * which is dark without a picture.
 *
 * Module-level refs, so the two files share one holder rather than one each
 * (Rule 13). Two things are kept and they belong together: the path the server
 * knows the uploaded picture by, which is what a run sends, and the URL the
 * field shows. The synth takes no picture and does not read this.
 *
 * It lives as long as the tab does, which is what "still there when I come
 * back" means — with ONE end to it besides a reload: the picture is a
 * PARTICIPANT's, and it goes when they do. `stores/labAuth.ts` puts it away on
 * sign-out and on a change of course. A workshop machine is handed on, and
 * without that the next participant found the last one's photograph standing in
 * the field, with ImageBind Guidance's trigger live on it.
 */
import { ref } from 'vue'

/** What a run sends: the path the server filed the uploaded picture under. */
const imagePath = ref('')
/** What the field shows. */
const imagePreview = ref('')

/** The payload both the picture widget and a dropped run hand over. */
export interface UploadedPicture {
  image_path: string
  preview_url: string
}

/**
 * Put the shared picture away. Exported on its own, beside the composable,
 * because the caller that has to reach it is not a component: the auth store
 * calls it on sign-out and on a change of course.
 */
export function clearCrossmodalPicture(): void {
  imagePath.value = ''
  imagePreview.value = ''
}

export function useCrossmodalPicture() {
  function setPicture(data: UploadedPicture): void {
    imagePath.value = data.image_path
    imagePreview.value = data.preview_url
  }

  return { imagePath, imagePreview, setPicture, clearPicture: clearCrossmodalPicture }
}
