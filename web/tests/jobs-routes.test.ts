import { describe, expect, it } from 'vitest'
import { Route as Screen } from '#/routes/api/jobs/$id/screen'
import { Route as Screens } from '#/routes/api/jobs/$id/screens'
import { routeTree } from '#/routeTree.gen'

type Registered = {
  options: { id?: string; server?: { handlers?: Record<string, unknown> } }
}
const methods = (route: unknown) =>
  Object.keys((route as Registered).options.server?.handlers ?? {}).sort()
const id = (route: unknown) => (route as Registered).options.id

describe('the job screen routes are registered', () => {
  it('has every method and path pair', () => {
    expect([
      [id(Screen), methods(Screen)],
      [id(Screens), methods(Screens)],
    ]).toEqual([
      ['/api/jobs/$id/screen', ['POST']],
      ['/api/jobs/$id/screens', ['GET']],
    ])
  })

  it('has them in the generated route tree', () => {
    const tree = JSON.stringify(
      (routeTree as unknown as { children?: unknown }).children,
      (_key, value) => (typeof value === 'function' ? undefined : value),
    )
    // The closing quote keeps `/screen` from matching inside `/screens`.
    expect(tree).toContain('"id":"/api/jobs/$id/screen"')
    expect(tree).toContain('"id":"/api/jobs/$id/screens"')
  })
})
