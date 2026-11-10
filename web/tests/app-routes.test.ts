import { describe, expect, it } from 'vitest'
import { isRedirect } from '@tanstack/react-router'
import { Route as Dashboard } from '#/routes/_app/dashboard'
import { Route as Workspace } from '#/routes/_app/jobs_.$jobId'
import { Route as Settings } from '#/routes/_app/settings'
import { Route as Today } from '#/routes/_app/today'
import { routeTree } from '#/routeTree.gen'

type Registered = { options: { id: string; path: string } }
const ids = (route: unknown) => (route as Registered).options.id
const paths = (route: unknown) => (route as Registered).options.path

describe('the signed-in routes', () => {
  it('has Today, Settings and the job workspace', () => {
    expect([Today, Settings, Workspace].map(ids)).toEqual([
      '/today',
      '/settings',
      '/jobs_/$jobId',
    ])
    expect([Today, Settings, Workspace].map(paths)).toEqual([
      '/today',
      '/settings',
      '/jobs/$jobId',
    ])
  })

  it('has them in the generated route tree', () => {
    const tree = JSON.stringify(
      (routeTree as unknown as { children?: unknown }).children,
      (_key, value) => (typeof value === 'function' ? undefined : value),
    )
    for (const path of ['/today', '/settings', '/jobs/$jobId']) {
      expect(tree).toContain(`"path":"${path}"`)
    }
  })

  it('sends the old dashboard address to Today, replacing the history entry', () => {
    const beforeLoad = (
      Dashboard as unknown as { options: { beforeLoad: () => never } }
    ).options.beforeLoad
    let thrown: unknown
    try {
      beforeLoad()
    } catch (error) {
      thrown = error
    }
    expect(isRedirect(thrown)).toBe(true)
    expect((thrown as { options: unknown }).options).toMatchObject({
      to: '/today',
      replace: true,
    })
  })
})
