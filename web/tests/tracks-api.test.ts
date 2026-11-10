import { describe, expect, it, vi } from 'vitest'
import {
  createTrack,
  deleteTrack,
  listTracks,
  renameTrack,
  setEmphasis,
} from '#/lib/tracks-api'

const ID = '9a1c2d3e-4b5f-4a6b-8c7d-0e1f2a3b4c5d'
const ITEM = '1b2c3d4e-5f60-4718-8293-a4b5c6d7e8f9'
type Fetch = typeof fetch
const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status })

describe('tracks-api', () => {
  it('calls each route with the right method, path and body', async () => {
    const fetchFn = vi.fn<Fetch>(async () => reply({ ok: 1 }))
    await listTracks({ fetchFn })
    await createTrack('Mobile', { fetchFn })
    await renameTrack(ID, 'New', { fetchFn })
    await setEmphasis(ID, 'skill', ITEM, true, { fetchFn })
    await setEmphasis(ID, 'skill', ITEM, false, { fetchFn })
    const del = vi.fn<Fetch>(async () => new Response(null, { status: 204 }))
    expect(await deleteTrack(ID, { fetchFn: del })).toEqual({
      ok: true,
      data: undefined,
    })
    expect([del.mock.calls[0][1]?.method, del.mock.calls[0][0]]).toEqual([
      'DELETE',
      `/api/tracks/${ID}`,
    ])
    expect(
      fetchFn.mock.calls.map(([url, init]) => [init?.method, url, init?.body]),
    ).toEqual([
      ['GET', '/api/tracks', undefined],
      ['POST', '/api/tracks', JSON.stringify({ name: 'Mobile' })],
      ['PATCH', `/api/tracks/${ID}`, JSON.stringify({ name: 'New' })],
      ['PUT', `/api/tracks/${ID}/items/skill/${ITEM}`, undefined],
      ['DELETE', `/api/tracks/${ID}/items/skill/${ITEM}`, undefined],
    ])
  })

  it('turns errors into a result and keeps only a safe code', async () => {
    const bad = vi.fn<Fetch>(async () => reply({ code: 'already_exists' }, 409))
    expect(await createTrack('x', { fetchFn: bad })).toMatchObject({
      ok: false,
      code: 'already_exists',
    })
    const odd = vi.fn<Fetch>(async () => reply({ code: '<script>' }, 500))
    expect(await listTracks({ fetchFn: odd })).toMatchObject({
      ok: false,
      code: 'unexpected',
    })
    const down = vi.fn<Fetch>(async () => {
      throw new Error('offline')
    })
    expect(await listTracks({ fetchFn: down })).toMatchObject({
      ok: false,
      code: 'network',
    })
  })
})
