import { checkId, checkKind, forward } from '../profile/http'
import type { ProfileHttpDeps } from '../profile/http'

/** Proxies to the engine's track routes. Sign-in, size cap and errors are the profile layer's. */
export type TracksHttpDeps = ProfileHttpDeps

export const handleTracks = (request: Request, deps: TracksHttpDeps = {}) =>
  forward(request, deps, { method: 'GET', path: '/internal/tracks' })

export const handleTrackCreate = (
  request: Request,
  deps: TracksHttpDeps = {},
) =>
  forward(request, deps, {
    method: 'POST',
    path: '/internal/tracks',
    withBody: true,
    status: 201,
  })

export const handleTrackRename = (
  request: Request,
  id: string,
  deps: TracksHttpDeps = {},
) =>
  forward(
    request,
    deps,
    { method: 'PATCH', path: `/internal/tracks/${id}`, withBody: true },
    () => checkId(id),
  )

export const handleTrackDelete = (
  request: Request,
  id: string,
  deps: TracksHttpDeps = {},
) =>
  forward(
    request,
    deps,
    { method: 'DELETE', path: `/internal/tracks/${id}` },
    () => checkId(id),
  )

export const handleEmphasis = (
  request: Request,
  id: string,
  kind: string,
  itemId: string,
  on: boolean,
  deps: TracksHttpDeps = {},
) =>
  forward(
    request,
    deps,
    {
      method: on ? 'PUT' : 'DELETE',
      path: `/internal/tracks/${id}/items/${kind}/${itemId}`,
    },
    () => {
      checkId(id)
      checkKind(kind)
      checkId(itemId)
    },
  )

export const handlePreferences = (
  request: Request,
  id: string,
  deps: TracksHttpDeps = {},
) =>
  forward(
    request,
    deps,
    {
      method: 'PATCH',
      path: `/internal/tracks/${id}/preferences`,
      withBody: true,
    },
    () => checkId(id),
  )
