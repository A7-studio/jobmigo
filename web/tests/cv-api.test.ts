import { describe, expect, it, vi } from 'vitest'
import {
  deleteCv,
  getCv,
  getDraft,
  listCvs,
  startParse,
  uploadCv,
} from '#/lib/cv-api'

const ID = '9a1c2d3e-4b5f-4a6b-8c7d-0e1f2a3b4c5d'
type Fetch = typeof fetch
const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status })

describe('cv-api', () => {
  it('uploads the file as the raw body with an encoded name', async () => {
    const fetchFn = vi.fn<Fetch>(async () => reply({ id: ID }, 201))
    const file = new File([new Uint8Array([1, 2, 3])], 'Zoë "CV" 100%.pdf', {
      type: 'application/pdf',
    })
    const result = await uploadCv(file, { fetchFn })
    expect(result).toEqual({ ok: true, data: { id: ID } })
    const [url, init] = fetchFn.mock.calls[0]
    expect(url).toBe('/api/cv')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBe(file)
    const name = (init?.headers as Record<string, string>)['x-filename']
    expect(decodeURIComponent(name)).toBe('Zoë "CV" 100%.pdf')
    expect(name).toMatch(/^[\x20-\x7e]+$/)
  })

  it('calls each route with the right method and path', async () => {
    const fetchFn = vi.fn<Fetch>(async () => reply({ ok: 1 }))
    await listCvs({ fetchFn })
    await getCv(ID, { fetchFn })
    await startParse(ID, { fetchFn })
    await getDraft(ID, { fetchFn })
    await deleteCv(ID, {
      fetchFn: async () => new Response(null, { status: 204 }),
    })
    expect(
      fetchFn.mock.calls.map(([url, init]) => [init?.method, url]),
    ).toEqual([
      ['GET', '/api/cv'],
      ['GET', `/api/cv/${ID}`],
      ['POST', `/api/cv/${ID}/parse`],
      ['GET', `/api/cv/${ID}/profile`],
    ])
  })

  it('returns undefined data for a 204 delete', async () => {
    const result = await deleteCv(ID, {
      fetchFn: async () => new Response(null, { status: 204 }),
    })
    expect(result).toEqual({ ok: true, data: undefined })
  })

  it('turns an HTTP error into its stable code and never throws', async () => {
    const fetchFn = vi.fn<Fetch>(async () =>
      reply({ code: 'cv_too_large', message: 'raw server words' }, 413),
    )
    const result = await getCv(ID, { fetchFn })
    expect(result).toEqual({
      ok: false,
      code: 'cv_too_large',
      message: 'Request failed.',
    })
  })

  it('ignores a code that is not in the safe shape', async () => {
    const result = await getCv(ID, {
      fetchFn: async () => reply({ code: '<script>alert(1)</script>' }, 400),
    })
    expect(result).toMatchObject({ ok: false, code: 'unexpected' })
  })

  it('reports a network failure and a non-JSON body as stable errors', async () => {
    expect(
      await getCv(ID, {
        fetchFn: async () => {
          throw new TypeError('failed to fetch')
        },
      }),
    ).toMatchObject({ ok: false, code: 'network' })
    expect(
      await getCv(ID, {
        fetchFn: async () => new Response('<html>', { status: 502 }),
      }),
    ).toMatchObject({ ok: false, code: 'unexpected' })
  })
})
