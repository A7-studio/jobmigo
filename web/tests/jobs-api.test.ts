import { describe, expect, it, vi } from 'vitest'
import {
  addJob,
  deleteJob,
  fetchJobPage,
  getJob,
  evaluateJob,
  getJobEvaluations,
  getJobScreens,
  listJobs,
  screenJob,
  setJobKind,
  setJobStatus,
} from '#/lib/jobs-api'

const ID = '9a1c2d3e-4b5f-4a6b-8c7d-0e1f2a3b4c5d'
type Fetch = typeof fetch
const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status })

describe('jobs-api', () => {
  it('calls each route with the right method, path and body', async () => {
    const fetchFn = vi.fn<Fetch>(async () => reply({ ok: 1 }))
    await listJobs(undefined, { fetchFn })
    await listJobs('dismissed', { fetchFn })
    await addJob({ company: 'A', title: 'T', text: 'posting' }, { fetchFn })
    await getJob(ID, { fetchFn })
    await setJobStatus(ID, 'dismissed', { fetchFn })
    await setJobKind(ID, 'gig', { fetchFn })
    await fetchJobPage('https://x.example/j', { fetchFn })
    await screenJob(ID, { fetchFn })
    await getJobScreens(ID, { fetchFn })
    await evaluateJob(ID, ID, { fetchFn })
    await getJobEvaluations(ID, { fetchFn })
    const del = vi.fn<Fetch>(async () => new Response(null, { status: 204 }))
    expect(await deleteJob(ID, { fetchFn: del })).toEqual({
      ok: true,
      data: undefined,
    })
    expect([del.mock.calls[0][1]?.method, del.mock.calls[0][0]]).toEqual([
      'DELETE',
      `/api/jobs/${ID}`,
    ])
    expect(
      fetchFn.mock.calls.map(([url, init]) => [init?.method, url, init?.body]),
    ).toEqual([
      ['GET', '/api/jobs', undefined],
      ['GET', '/api/jobs?status=dismissed', undefined],
      [
        'POST',
        '/api/jobs',
        JSON.stringify({ company: 'A', title: 'T', text: 'posting' }),
      ],
      ['GET', `/api/jobs/${ID}`, undefined],
      ['PATCH', `/api/jobs/${ID}`, JSON.stringify({ status: 'dismissed' })],
      ['PATCH', `/api/jobs/${ID}`, JSON.stringify({ kind: 'gig' })],
      [
        'POST',
        '/api/jobs/fetch',
        JSON.stringify({ url: 'https://x.example/j' }),
      ],
      ['POST', `/api/jobs/${ID}/screen`, undefined],
      ['GET', `/api/jobs/${ID}/screens`, undefined],
      ['POST', `/api/jobs/${ID}/evaluate`, JSON.stringify({ trackId: ID })],
      ['GET', `/api/jobs/${ID}/evaluations`, undefined],
    ])
  })

  it('turns errors into a result with a safe code', async () => {
    const dup = vi.fn<Fetch>(async () => reply({ code: 'already_exists' }, 409))
    expect(
      await addJob({ company: 'A', title: 'T', text: 'x' }, { fetchFn: dup }),
    ).toMatchObject({ ok: false, code: 'already_exists' })
    const blocked = vi.fn<Fetch>(async () =>
      reply({ code: 'robots_disallowed' }, 422),
    )
    expect(
      await fetchJobPage('https://x.example/', { fetchFn: blocked }),
    ).toMatchObject({ ok: false, code: 'robots_disallowed' })
    const odd = vi.fn<Fetch>(async () => reply({ code: '<b>' }, 500))
    expect(await listJobs(undefined, { fetchFn: odd })).toMatchObject({
      code: 'unexpected',
    })
    const down = vi.fn<Fetch>(async () => {
      throw new Error('offline')
    })
    expect(await getJob(ID, { fetchFn: down })).toMatchObject({
      code: 'network',
    })
  })
})
