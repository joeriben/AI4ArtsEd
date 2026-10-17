import { describe, it, expect } from 'vitest'
import { planComposition } from '../useCompositionRouting'

const AUDIO = 'run_audio_1'
const VIDEO = 'run_video_1'
const IMAGE = 'run_image_1'

describe('planComposition', () => {
  it('is null without a sound — there is nothing to compose', () => {
    expect(planComposition({ hasText: true, medium: 'image' })).toBeNull()
    expect(planComposition({ hasText: true, medium: 'video', videoRef: VIDEO })).toBeNull()
  })

  it('lays a sound under an existing video, generating nothing', () => {
    expect(planComposition({ hasText: false, medium: 'sound', audioRef: AUDIO, videoRef: VIDEO })).toEqual({
      op: 'video_plus_audio',
      ready: { video: VIDEO, audio: AUDIO },
      generate: null,
    })
  })

  it('lays a sound under a picture that already lies there, generating nothing', () => {
    expect(
      planComposition({ hasText: false, medium: 'image', audioRef: AUDIO, imageRef: IMAGE }),
    ).toEqual({
      op: 'still_plus_audio',
      ready: { image: IMAGE, audio: AUDIO },
      generate: null,
    })
  })

  it('an existing video wins over a picture that already lies there', () => {
    const plan = planComposition({
      hasText: false,
      medium: 'image',
      audioRef: AUDIO,
      imageRef: IMAGE,
      videoRef: VIDEO,
    })
    expect(plan!.op).toBe('video_plus_audio')
    expect(plan!.ready).toEqual({ video: VIDEO, audio: AUDIO })
  })

  it('words outrank a lying picture — text + sound still makes a new one', () => {
    const plan = planComposition({ hasText: true, medium: 'image', audioRef: AUDIO, imageRef: IMAGE })
    expect(plan!.generate).toBe('image')
    expect(plan!.ready).toEqual({ audio: AUDIO })
  })

  it('turns text + sound into a still with sound', () => {
    expect(planComposition({ hasText: true, medium: 'image', audioRef: AUDIO })).toEqual({
      op: 'still_plus_audio',
      ready: { audio: AUDIO },
      generate: 'image',
    })
  })

  it('turns text + sound into a video with sound when the medium is video', () => {
    expect(planComposition({ hasText: true, medium: 'video', audioRef: AUDIO })).toEqual({
      op: 'video_plus_audio',
      ready: { audio: AUDIO },
      generate: 'video',
    })
  })

  it('an existing video wins over generating one', () => {
    const plan = planComposition({ hasText: true, medium: 'video', audioRef: AUDIO, videoRef: VIDEO })
    expect(plan!.generate).toBeNull()
    expect(plan!.ready).toEqual({ video: VIDEO, audio: AUDIO })
  })

  // No operation exists for these. The sound must be marked surplus, not consumed.
  it('is null for a lone sound, and for sound/3d media', () => {
    expect(planComposition({ hasText: false, medium: 'image', audioRef: AUDIO })).toBeNull()
    expect(planComposition({ hasText: true, medium: 'sound', audioRef: AUDIO })).toBeNull()
    expect(planComposition({ hasText: true, medium: '3d', audioRef: AUDIO })).toBeNull()
  })
})
