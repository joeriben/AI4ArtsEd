import { afterEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { isSignInRequired, onSignInLapse, suspectSignIn, watchAxios, watchFetch } from '../signInLapse'

afterEach(() => onSignInLapse(null))

describe('the refusal of the sign-in gate', () => {
  it('is a 401 that names sign_in_required, and nothing else', () => {
    expect(isSignInRequired(401, { error: 'sign_in_required' })).toBe(true)
    expect(isSignInRequired(401, { error: 'Invalid credentials' })).toBe(false)
    expect(isSignInRequired(401, { error: 'Authentication required' })).toBe(false)
    expect(isSignInRequired(403, { error: 'sign_in_required' })).toBe(false)
    expect(isSignInRequired(401, 'sign_in_required')).toBe(false)
    expect(isSignInRequired(undefined, null)).toBe(false)
  })

  it('is reported by a watched axios instance and still reaches the caller', async () => {
    const told = vi.fn()
    onSignInLapse(told)
    const client = axios.create({
      adapter: async (config) => {
        const error: any = new Error('Request failed with status code 401')
        error.config = config
        error.response = { status: 401, data: { error: 'sign_in_required' }, headers: {}, config }
        throw error
      },
    })
    watchAxios(client)
    await expect(client.get('/api/anything')).rejects.toMatchObject({ response: { status: 401 } })
    expect(told).toHaveBeenCalledTimes(1)
  })

  it('is not reported for another refusal', async () => {
    const told = vi.fn()
    onSignInLapse(told)
    const client = axios.create({
      adapter: async (config) => {
        const error: any = new Error('Request failed with status code 403')
        error.config = config
        error.response = { status: 403, data: { error: 'forbidden' }, headers: {}, config }
        throw error
      },
    })
    watchAxios(client)
    await expect(client.get('/api/anything')).rejects.toBeTruthy()
    expect(told).not.toHaveBeenCalled()
  })

  it('is reported from fetch, and the caller still reads the answer', async () => {
    const told = vi.fn()
    onSignInLapse(told)
    const answer = () => new Response(JSON.stringify({ error: 'sign_in_required' }), { status: 401 })
    const target = { fetch: vi.fn(async () => answer()) as unknown as typeof fetch }
    watchFetch(target)
    const response = await target.fetch('/api/anything')
    expect(response.status).toBe(401)
    expect(await response.json()).toEqual({ error: 'sign_in_required' })
    await vi.waitFor(() => expect(told).toHaveBeenCalledTimes(1))
  })

  it('is not reported from fetch for another 401 or an answer', async () => {
    const told = vi.fn()
    onSignInLapse(told)
    const answers = [
      new Response(JSON.stringify({ error: 'Authentication required' }), { status: 401 }),
      new Response('not json', { status: 401 }),
      new Response(JSON.stringify({ error: 'sign_in_required' }), { status: 200 }),
    ]
    const target = { fetch: vi.fn(async () => answers.shift()!) as unknown as typeof fetch }
    watchFetch(target)
    for (let i = 0; i < 3; i++) await (await target.fetch('/api/anything')).text()
    await new Promise((resolve) => setTimeout(resolve, 10))
    expect(told).not.toHaveBeenCalled()
  })

  it('is suspected by a stream without a listener, harmlessly', () => {
    expect(() => suspectSignIn()).not.toThrow()
  })
})
