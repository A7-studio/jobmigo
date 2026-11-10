import { describe, expect, it } from 'vitest'
import { Route as Index } from '#/routes/api/profile/index'
import { Route as ConfirmAll } from '#/routes/api/profile/confirm-all'
import { Route as Add } from '#/routes/api/profile/items/$kind/index'
import { Route as Item } from '#/routes/api/profile/items/$kind/$id/index'
import { Route as Confirm } from '#/routes/api/profile/items/$kind/$id/confirm'
import { routeTree } from '#/routeTree.gen'

type Registered = {
  options: { id?: string; server?: { handlers?: Record<string, unknown> } }
}
const methods = (route: unknown) =>
  Object.keys((route as Registered).options.server?.handlers ?? {}).sort()
const id = (route: unknown) => (route as Registered).options.id

describe('the profile routes are registered', () => {
  it('has every method and path pair', () => {
    expect([
      [id(Index), methods(Index)],
      [id(ConfirmAll), methods(ConfirmAll)],
      [id(Add), methods(Add)],
      [id(Item), methods(Item)],
      [id(Confirm), methods(Confirm)],
    ]).toEqual([
      ['/api/profile/', ['GET', 'PATCH']],
      ['/api/profile/confirm-all', ['POST']],
      ['/api/profile/items/$kind/', ['POST']],
      ['/api/profile/items/$kind/$id/', ['DELETE', 'PATCH']],
      ['/api/profile/items/$kind/$id/confirm', ['POST']],
    ])
  })

  it('has them in the generated route tree', () => {
    const tree = JSON.stringify(
      (routeTree as unknown as { children?: unknown }).children,
      (_key, value) => (typeof value === 'function' ? undefined : value),
    )
    expect(tree).toContain('/api/profile')
  })
})
