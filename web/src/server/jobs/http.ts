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

export const handleJobFetch = (request: Request, deps: JobsHttpDeps = {}) =>
  forward(request, deps, {
    method: 'POST',
    path: '/internal/jobs/fetch',
    withBody: true,
  })
