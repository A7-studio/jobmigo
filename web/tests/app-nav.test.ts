import { describe, expect, it } from 'vitest'
import { LANDING_PATH, NAV_ITEMS, STEPS, nextStep } from '#/lib/app-nav'

describe('the app navigation', () => {
  it('has the four places in order', () => {
    expect(NAV_ITEMS.map((item) => item.label)).toEqual([
      'Today',
      'Jobs',
      'Profile',
      'Settings',
    ])
    expect(NAV_ITEMS.map((item) => item.to)).toEqual([
      '/today',
      '/jobs',
      '/profile',
      '/settings',
    ])
  })

  it('lands people on Today', () => {
    expect(LANDING_PATH).toBe('/today')
    expect(NAV_ITEMS[0].to).toBe(LANDING_PATH)
  })
})

describe('the workspace step keys', () => {
  it('has the four steps in order', () => {
    expect([...STEPS]).toEqual(['Fit', 'CV and letter', 'Outreach', 'Track'])
  })

  it('moves with the arrow keys and wraps around', () => {
    expect(nextStep('Fit', 'ArrowRight')).toBe('CV and letter')
    expect(nextStep('Track', 'ArrowRight')).toBe('Fit')
    expect(nextStep('Fit', 'ArrowLeft')).toBe('Track')
    expect(nextStep('Outreach', 'ArrowLeft')).toBe('CV and letter')
  })

  it('jumps with Home and End', () => {
    expect(nextStep('Outreach', 'Home')).toBe('Fit')
    expect(nextStep('Outreach', 'End')).toBe('Track')
  })

  it('ignores every other key', () => {
    for (const key of ['Enter', ' ', 'Tab', 'ArrowDown', 'a']) {
      expect(nextStep('Fit', key)).toBeNull()
    }
  })
})
