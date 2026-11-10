import { describe, expect, it, vi } from 'vitest'
import {
  addItem,
  confirmAll,
  confirmItem,
  deleteItem,
  getProfile,
  patchItem,
  patchProfile,
} from '#/lib/profile-api'

const ID = '9a1c2d3e-4b5f-4a6b-8c7d-0e1f2a3b4c5d'
type Fetch = typeof fetch
const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status })

describe('profile-api', () => {
  it('calls each route with the right method, path and JSON body', async () => {
    const fetchFn = vi.fn<Fetch>(async () => reply({ ok: 1 }))
    await getProfile({ fetchFn })
    await patchProfile({ headline: 'h' }, { fetchFn })
    await addItem('skill', { name: 'Go' }, { fetchFn })
    await patchItem('experience', ID, { role: 'R' }, { fetchFn })
    await confirmItem('project', ID, { fetchFn })
    await confirmAll({ fetchFn })
    const del = vi.fn<Fetch>(async () => new Response(null, { status: 204 }))
    await deleteItem('education', ID, { fetchFn: del })
    expect([del.mock.calls[0][1]?.method, del.mock.calls[0][0]]).toEqual([
      'DELETE',
      `/api/profile/items/education/${ID}`,
    ])
    expect(
      fetchFn.mock.calls.map(([url, init]) => [init?.method, url, init?.body]),
    ).toEqual([
      ['GET', '/api/profile', undefined],
      ['PATCH', '/api/profile', JSON.stringify({ headline: 'h' })],
      ['POST', '/api/profile/items/skill', JSON.stringify({ name: 'Go' })],
      [
        'PATCH',
        `/api/profile/items/experience/${ID}`,
        JSON.stringify({ role: 'R' }),
      ],
      ['POST', `/api/profile/items/project/${ID}/confirm`, undefined],
      ['POST', '/api/profile/confirm-all', undefined],
    ])
  })

  it('returns undefined data for a 204 delete', async () => {
    expect(
      await deleteItem('skill', ID, {
        fetchFn: async () => new Response(null, { status: 204 }),
      }),
    ).toEqual({ ok: true, data: undefined })
  })

  it('turns an HTTP error into its stable code and never throws', async () => {
    const result = await addItem(
      'skill',
      { name: 'x' },
      {
        fetchFn: async () =>
          reply({ code: 'already_exists', message: 'raw words' }, 409),
      },
    )
    expect(result).toEqual({
      ok: false,
      code: 'already_exists',
      message: 'Request failed.',
    })
  })

  it('ignores an unsafe code, and reports network and non-JSON failures', async () => {
    expect(
      await getProfile({
        fetchFn: async () => reply({ code: '<b>x</b>' }, 400),
      }),
    ).toMatchObject({ ok: false, code: 'unexpected' })
    expect(
      await getProfile({
        fetchFn: async () => {
          throw new TypeError('failed')
        },
      }),
    ).toMatchObject({ ok: false, code: 'network' })
    expect(
      await getProfile({
        fetchFn: async () => new Response('<html>', { status: 502 }),
      }),
    ).toMatchObject({ ok: false, code: 'unexpected' })
  })
})
