import { describe, expect, it } from 'vitest'
import { Route as Index } from '#/routes/api/cv/index'
import { Route as Item } from '#/routes/api/cv/$id/index'
import { Route as Download } from '#/routes/api/cv/$id/download'
import { routeTree } from '#/routeTree.gen'

type Registered = {
  options: { id?: string; server?: { handlers?: Record<string, unknown> } }
}
const methods = (route: unknown) =>
  Object.keys((route as Registered).options.server?.handlers ?? {}).sort()

describe('the CV routes are registered', () => {
  it('has the four method and path pairs', () => {
    expect([
      [(Index as unknown as Registered).options.id, methods(Index)],
      [(Item as unknown as Registered).options.id, methods(Item)],
      [(Download as unknown as Registered).options.id, methods(Download)],
    ]).toEqual([
      ['/api/cv/', ['GET', 'POST']],
      ['/api/cv/$id/', ['DELETE']],
      ['/api/cv/$id/download', ['GET']],
    ])
  })

  it('has them in the generated route tree', () => {
    const tree = JSON.stringify(
      (routeTree as unknown as { children?: unknown }).children,
      (_key, value) => (typeof value === 'function' ? undefined : value),
    )
    expect(tree).toContain('/api/cv')
  })
})
