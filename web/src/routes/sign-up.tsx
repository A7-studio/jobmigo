import { createFileRoute } from '@tanstack/react-router'
import { AuthForm } from '#/components/AuthForm'
import { getAuthConfig } from '#/lib/auth.functions'

export const Route = createFileRoute('/sign-up')({
  loader: () => getAuthConfig(),
  component: Page,
})

function Page() {
  const { google } = Route.useLoaderData()
  return <AuthForm mode="sign-up" google={google} />
}
