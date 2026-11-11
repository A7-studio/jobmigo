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

export const handleJobFetch = (request: Request, deps: JobsHttpDeps = {}) =>
  forward(request, deps, {
    method: 'POST',
    path: '/internal/jobs/fetch',
    withBody: true,
  })
