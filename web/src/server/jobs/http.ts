import { checkId, forward } from '../profile/http'
import type { ProfileHttpDeps } from '../profile/http'

/** A pasted posting is long text; a body past this is refused before the engine sees it. */
export const MAX_JOB_BODY_BYTES = 256 * 1024

export type JobsHttpDeps = ProfileHttpDeps

export const handleJobs = (request: Request, deps: JobsHttpDeps = {}) => {
  const status = new URL(request.url).searchParams.get('status')
  const query = status === null ? '' : `?status=${encodeURIComponent(status)}`
  return forward(request, deps, {
    method: 'GET',
    path: `/internal/jobs${query}`,
  })
}

export const handleJobCreate = (request: Request, deps: JobsHttpDeps = {}) =>
  forward(request, deps, {
    method: 'POST',
    path: '/internal/jobs',
    withBody: true,
    maxBytes: MAX_JOB_BODY_BYTES,
    status: 201,
  })

export const handleJob = (
  request: Request,
  id: string,
  deps: JobsHttpDeps = {},
) =>
  forward(request, deps, { method: 'GET', path: `/internal/jobs/${id}` }, () =>
    checkId(id),
  )

export const handleJobStatus = (
  request: Request,
  id: string,
  deps: JobsHttpDeps = {},
) =>
  forward(
    request,
    deps,
    { method: 'PATCH', path: `/internal/jobs/${id}`, withBody: true },
    () => checkId(id),
  )

export const handleJobDelete = (
  request: Request,
  id: string,
  deps: JobsHttpDeps = {},
) =>
  forward(
    request,
    deps,
    { method: 'DELETE', path: `/internal/jobs/${id}` },
    () => checkId(id),
  )

/** Run the gates and the cheap screen for this job against every track. */
export const handleJobScreen = (
  request: Request,
  id: string,
  deps: JobsHttpDeps = {},
) =>
  forward(
    request,
    deps,
    { method: 'POST', path: `/internal/jobs/${id}/screen` },
    () => checkId(id),
  )

/** The saved screen results for this job. */
export const handleJobScreens = (
  request: Request,
  id: string,
  deps: JobsHttpDeps = {},
) =>
  forward(
    request,
    deps,
    { method: 'GET', path: `/internal/jobs/${id}/screens` },
    () => checkId(id),
  )

/** Evaluate this job for the track named in the body. The body is short: `{ trackId }`. */
export const handleJobEvaluate = (
  request: Request,
  id: string,
  deps: JobsHttpDeps = {},
) =>
  forward(
    request,
    deps,
    { method: 'POST', path: `/internal/jobs/${id}/evaluate`, withBody: true },
    () => checkId(id),
  )

/** The kept evaluations of this job, one per track. */
export const handleJobEvaluations = (
  request: Request,
  id: string,
  deps: JobsHttpDeps = {},
) =>
  forward(
    request,
    deps,
    { method: 'GET', path: `/internal/jobs/${id}/evaluations` },
    () => checkId(id),
  )

/** Write the kit (CV, letter or proposal, answers) for this job and the track in the body. */
export const handleJobKit = (
  request: Request,
  id: string,
  deps: JobsHttpDeps = {},
) =>
  forward(
    request,
    deps,
    { method: 'POST', path: `/internal/jobs/${id}/kit`, withBody: true },
    () => checkId(id),
  )

/** The kept kit versions: the latest of each document, or every version of one track. */
export const handleJobKits = (
  request: Request,
  id: string,
  deps: JobsHttpDeps = {},
) => {
  const track = new URL(request.url).searchParams.get('trackId')
  return forward(
    request,
    deps,
    {
      method: 'GET',
      path: `/internal/jobs/${id}/kits${track === null ? '' : `?trackId=${encodeURIComponent(track)}`}`,
    },
    () => {
      checkId(id)
      if (track !== null) checkId(track)
    },
  )
}

/** Edit or remove one statement of this kit version; the engine saves a new version. */
export const handleJobKitEdit = (
  request: Request,
  id: string,
  kitId: string,
  deps: JobsHttpDeps = {},
) =>
  forward(
    request,
    deps,
    {
      method: 'PATCH',
      path: `/internal/jobs/${id}/kits/${kitId}`,
      withBody: true,
    },
    () => {
      checkId(id)
      checkId(kitId)
    },
  )

const EXPORT_TYPES = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
])
const MAX_EXPORT_BYTES = 5 * 1024 * 1024
const BASE64 = /^[A-Za-z0-9+/]*={0,2}$/

/** A header-safe name: no control characters, no path separators, no quotes. */
function safeName(raw: string): string {
  const cleaned = Array.from(raw)
    .filter((ch) => ch >= ' ' && ch !== '\u007f' && !'/\\"%;'.includes(ch))
    .join('')
    .trim()
    .slice(0, 150)
  return cleaned || 'document'
}

/**
 * Make a PDF or DOCX of one kit version and send it as a download. The engine builds the
 * file on demand and returns it as base64 JSON; nothing is stored. A refusal (for example
 * `needs_fixing`) is passed through unchanged.
 */
export async function handleJobKitExport(
  request: Request,
  id: string,
  kitId: string,
  deps: JobsHttpDeps = {},
): Promise<Response> {
  const reply = await forward(
    request,
    deps,
    {
      method: 'POST',
      path: `/internal/jobs/${id}/kits/${kitId}/export`,
      withBody: true,
    },
    () => {
      checkId(id)
      checkId(kitId)
    },
  )
  if (!reply.ok) return reply
  const refuse = () =>
    new Response(
      JSON.stringify({ code: 'unexpected', message: 'Something went wrong.' }),
      {
        status: 502,
        headers: {
          'content-type': 'application/json',
          'cache-control': 'no-store',
        },
      },
    )
  try {
    const file = (await reply.json()) as {
      filename?: unknown
      contentType?: unknown
      data?: unknown
    }
    if (
      typeof file.filename !== 'string' ||
      typeof file.contentType !== 'string' ||
      !EXPORT_TYPES.has(file.contentType) ||
      typeof file.data !== 'string' ||
      file.data.length > Math.ceil((MAX_EXPORT_BYTES * 4) / 3) + 4 ||
      !BASE64.test(file.data)
    ) {
      return refuse()
    }
    const bytes = Uint8Array.from(Buffer.from(file.data, 'base64'))
    const name = safeName(file.filename)
    const ascii = name.replace(/[^\x20-\x7e]/g, '_')
    return new Response(bytes, {
      status: 200,
      headers: {
        'content-type': file.contentType,
        'content-length': String(bytes.byteLength),
        'content-disposition': `attachment; filename="${ascii}"; filename*=UTF-8''${encodeURIComponent(name)}`,
        'cache-control': 'no-store',
        'x-content-type-options': 'nosniff',
      },
    })
  } catch {
    return refuse()
  }
}

export const handleJobFetch = (request: Request, deps: JobsHttpDeps = {}) =>
  forward(request, deps, {
    method: 'POST',
    path: '/internal/jobs/fetch',
    withBody: true,
  })
