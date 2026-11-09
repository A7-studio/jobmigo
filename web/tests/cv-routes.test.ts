import { describe, expect, it } from 'vitest'
import { Route as Index } from '#/routes/api/cv/index'
import { Route as Item } from '#/routes/api/cv/$id/index'
import { Route as Download } from '#/routes/api/cv/$id/download'
import { Route as Parse } from '#/routes/api/cv/$id/parse'
import { Route as Profile } from '#/routes/api/cv/$id/profile'
import { routeTree } from '#/routeTree.gen'

type Registered = {
  options: { id?: string; server?: { handlers?: Record<string, unknown> } }
}
const methods = (route: unknown) =>
  Object.keys((route as Registered).options.server?.handlers ?? {}).sort()

describe('the CV routes are registered', () => {
  it('has every method and path pair', () => {
    expect([
      [(Index as unknown as Registered).options.id, methods(Index)],
      [(Item as unknown as Registered).options.id, methods(Item)],
      [(Download as unknown as Registered).options.id, methods(Download)],
      [(Parse as unknown as Registered).options.id, methods(Parse)],
      [(Profile as unknown as Registered).options.id, methods(Profile)],
    ]).toEqual([
      ['/api/cv/', ['GET', 'POST']],
      ['/api/cv/$id/', ['DELETE', 'GET']],
      ['/api/cv/$id/download', ['GET']],
      ['/api/cv/$id/parse', ['POST']],
      ['/api/cv/$id/profile', ['GET']],
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
