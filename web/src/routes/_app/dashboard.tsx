import { createFileRoute, redirect } from '@tanstack/react-router'
import { LANDING_PATH } from '#/lib/app-nav'

/** The old home address. It only sends people to Today. */
export const Route = createFileRoute('/_app/dashboard')({
  beforeLoad: () => {
    throw redirect({ to: LANDING_PATH, replace: true })
  },
})
