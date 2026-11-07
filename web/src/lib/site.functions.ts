import { createServerFn } from '@tanstack/react-start'

export const getSiteConfig = createServerFn({ method: 'GET' }).handler(() => ({
  publicUrl: (
    process.env.PUBLIC_URL ??
    process.env.BETTER_AUTH_URL ??
    ''
  ).replace(/\/$/, ''),
  contactEmail: process.env.CONTACT_EMAIL ?? '',
}))
