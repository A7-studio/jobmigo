import { describe, expect, it, vi } from 'vitest'
import { getAiUsage } from '#/lib/admin-api'

describe('getAiUsage', () => {
  it('asks for the window and returns the report', async () => {
    const fetchFn = vi.fn(
      async () => new Response(JSON.stringify({ days: 7 }), { status: 200 }),
    )
    const result = await getAiUsage(7, { fetchFn })
    expect(result).toEqual({ ok: true, data: { days: 7 } })
    expect((fetchFn.mock.calls[0] as unknown as [string])[0]).toBe(
      '/api/admin/ai-usage?days=7',
    )
  })

  it('turns a refusal into a safe code and a network error into network', async () => {
    const forbidden = vi.fn(
      async () =>
        new Response(JSON.stringify({ code: 'forbidden' }), { status: 403 }),
    )
    expect(await getAiUsage(30, { fetchFn: forbidden })).toMatchObject({
      ok: false,
      code: 'forbidden',
    })
    const odd = vi.fn(
      async () =>
        new Response(JSON.stringify({ code: 'Not A Safe Code' }), {
          status: 500,
        }),
    )
    expect(await getAiUsage(30, { fetchFn: odd })).toMatchObject({
      code: 'unexpected',
    })
    const down = vi.fn(async () => {
      throw new Error('boom')
    })
    expect(await getAiUsage(30, { fetchFn: down })).toMatchObject({
      code: 'network',
    })
  })
})
