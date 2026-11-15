import { describe, expect, it } from 'vitest'
import { imageInputRoute, resolveRoute } from '../useMaterialRouting'

const base = { medium: 'image' as const, t2xConfigId: 'sd35_large' }

describe('the two multi-image routes', () => {
  it('names the one route whose adaption reads the pictures', () => {
    expect(imageInputRoute('flux3_multi')?.adaptionReadsPictures).toBe(true)
    expect(imageInputRoute('qwen_2511_multi')?.adaptionReadsPictures).toBeUndefined()
  })

  it('sends a hand-picked Flux 3 Multi every image up to ten', () => {
    expect(resolveRoute({ ...base, imageCount: 5, pinnedConfigId: 'flux3_multi' })).toEqual({
      outputConfigId: 'flux3_multi',
      medium: 'image',
      maxImages: 5,
      imageParam: 'multi',
    })
    expect(resolveRoute({ ...base, imageCount: 12, pinnedConfigId: 'flux3_multi' }).maxImages).toBe(10)
  })

  it('holds a hand-picked Flux 3 Multi with one image', () => {
    expect(resolveRoute({ ...base, imageCount: 1, pinnedConfigId: 'flux3_multi' })).toEqual({
      outputConfigId: 'flux3_multi',
      medium: 'image',
      maxImages: 1,
      imageParam: 'multi',
    })
  })

  it('gives a hand-picked Qwen Multi up with one image', () => {
    const route = resolveRoute({ ...base, imageCount: 1, pinnedConfigId: 'qwen_2511_multi' })
    expect(route.outputConfigId).toBe('flux3_multi')
  })

  it('holds the Qwen models where they are picked by hand', () => {
    expect(resolveRoute({ ...base, imageCount: 3, pinnedConfigId: 'qwen_2511_multi' }).outputConfigId).toBe('qwen_2511_multi')
    expect(resolveRoute({ ...base, imageCount: 1, pinnedConfigId: 'qwen_img2img' })).toEqual({
      outputConfigId: 'qwen_img2img',
      medium: 'image',
      maxImages: 1,
      imageParam: 'single',
    })
  })

  it('takes Flux 3 Multi on its own for one image and for several', () => {
    expect(resolveRoute({ ...base, imageCount: 1 })).toEqual({
      outputConfigId: 'flux3_multi',
      medium: 'image',
      maxImages: 1,
      imageParam: 'multi',
    })
    expect(resolveRoute({ ...base, imageCount: 5 })).toEqual({
      outputConfigId: 'flux3_multi',
      medium: 'image',
      maxImages: 5,
      imageParam: 'multi',
    })
    expect(resolveRoute({ ...base, imageCount: 12 }).maxImages).toBe(10)
  })

  it('clamps an inferred medium to the image route with two images', () => {
    expect(resolveRoute({ ...base, medium: 'video', imageCount: 2 }).outputConfigId).toBe('flux3_multi')
  })

  it('leaves video and 3d on their own routes with one image', () => {
    expect(resolveRoute({ ...base, medium: 'video', imageCount: 1 }).outputConfigId).toBe('wan22_i2v_video')
    expect(resolveRoute({ ...base, medium: '3d', imageCount: 1 }).outputConfigId).toBe('hunyuan3d_text_to_3d')
  })

  it('names the route for the model picker', () => {
    expect(imageInputRoute('flux3_multi')).toMatchObject({ label: 'Flux 3 Multi', minImages: 1, maxImages: 10 })
  })
})
