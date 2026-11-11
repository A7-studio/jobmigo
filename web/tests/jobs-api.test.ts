import { describe, expect, it, vi } from 'vitest'
import {
  addJob,
  deleteJob,
  fetchJobPage,
  getJob,
  evaluateJob,
  getJobEvaluations,
  getJobScreens,
  editKit,
  exportKit,
  fileNameFrom,
  getKits,
  listJobs,
  screenJob,
  setJobKind,
  setJobStatus,
  writeKit,
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
    await writeKit(ID, ID, [], { fetchFn })
    await writeKit(ID, ID, ['Why us?'], { fetchFn })
    await getKits(ID, undefined, { fetchFn })
    await getKits(ID, ID, { fetchFn })
    await editKit(
      ID,
      ID,
      { path: 'summary', action: 'edit', text: 'x' },
      { fetchFn },
    )
    await editKit(
      ID,
      ID,
      { path: 'paragraphs.2', action: 'remove' },
      { fetchFn },
    )
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
      ['POST', `/api/jobs/${ID}/kit`, JSON.stringify({ trackId: ID })],
      [
        'POST',
        `/api/jobs/${ID}/kit`,
        JSON.stringify({ trackId: ID, questions: ['Why us?'] }),
      ],
      ['GET', `/api/jobs/${ID}/kits`, undefined],
      ['GET', `/api/jobs/${ID}/kits?trackId=${ID}`, undefined],
      [
        'PATCH',
        `/api/jobs/${ID}/kits/${ID}`,
        JSON.stringify({ path: 'summary', action: 'edit', text: 'x' }),
      ],
      [
        'PATCH',
        `/api/jobs/${ID}/kits/${ID}`,
        JSON.stringify({ path: 'paragraphs.2', action: 'remove' }),
      ],
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

  it('exports a file and reads its name, or turns a refusal into a safe code', async () => {
    const file = vi.fn<Fetch>(
      async () =>
        new Response(new Uint8Array([37, 80, 68, 70]), {
          status: 200,
          headers: {
            'content-disposition': `attachment; filename="Jose_Mueller - CV - Acme.pdf"; filename*=UTF-8''Jos%C3%A9%20M%C3%BCller%20-%20CV.pdf`,
          },
        }),
    )
    const ok = await exportKit(
      ID,
      ID,
      { format: 'pdf', name: 'José' },
      { fetchFn: file },
    )
    expect(ok.ok && ok.data.filename).toBe('José Müller - CV.pdf')
    expect(ok.ok && ok.data.blob.size).toBe(4)
    expect(file.mock.calls[0][0]).toBe(`/api/jobs/${ID}/kits/${ID}/export`)
    expect(file.mock.calls[0][1]?.method).toBe('POST')
    expect(file.mock.calls[0][1]?.body).toBe(
      JSON.stringify({ format: 'pdf', name: 'José' }),
    )
    const refused = vi.fn<Fetch>(async () =>
      reply({ code: 'needs_fixing' }, 409),
    )
    expect(
      await exportKit(
        ID,
        ID,
        { format: 'docx', name: 'S' },
        { fetchFn: refused },
      ),
    ).toMatchObject({ ok: false, code: 'needs_fixing' })
    const odd = vi.fn<Fetch>(async () => reply({ code: 'Not Safe' }, 500))
    expect(
      await exportKit(ID, ID, { format: 'pdf', name: 'S' }, { fetchFn: odd }),
    ).toMatchObject({ code: 'unexpected' })
    const down = vi.fn<Fetch>(async () => {
      throw new Error('x')
    })
    expect(
      await exportKit(ID, ID, { format: 'pdf', name: 'S' }, { fetchFn: down }),
    ).toMatchObject({ code: 'network' })
  })

  it('reads a download name from either form of the header', () => {
    expect(fileNameFrom(null)).toBeNull()
    expect(fileNameFrom('attachment; filename="a b.pdf"')).toBe('a b.pdf')
    expect(fileNameFrom("attachment; filename*=UTF-8''a%20b.pdf")).toBe(
      'a b.pdf',
    )
    expect(fileNameFrom("attachment; filename*=UTF-8''%E0%A4%A")).toBeNull()
    expect(fileNameFrom('inline')).toBeNull()
  })
})
