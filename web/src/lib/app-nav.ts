/** Where a signed-in person lands: after sign-in, sign-up and the old `/dashboard` address. */
export const LANDING_PATH = '/today'

/** The four places of the signed-in app, in the order the sidebar shows them. */
export const NAV_ITEMS = [
  { label: 'Today', to: '/today' },
  { label: 'Jobs', to: '/jobs' },
  { label: 'Profile', to: '/profile' },
  { label: 'Settings', to: '/settings' },
] as const

/** The four steps of a job workspace. Later features fill them in. */
export const STEPS = ['Fit', 'CV and letter', 'Outreach', 'Track'] as const
export type Step = (typeof STEPS)[number]

/** The step a tab key moves to, or null when the key is not a tab key. */
export function nextStep(current: Step, key: string): Step | null {
  const at = STEPS.indexOf(current)
  if (key === 'ArrowRight') return STEPS[(at + 1) % STEPS.length]
  if (key === 'ArrowLeft') return STEPS[(at + STEPS.length - 1) % STEPS.length]
  if (key === 'Home') return STEPS[0]
  if (key === 'End') return STEPS[STEPS.length - 1]
  return null
}
