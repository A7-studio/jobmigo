import { describe, expect, it } from 'vitest'
import {
  PASTE_INSTEAD,
  addedLabel,
  checkAdd,
  initialOf,
  jobsCopy,
  readableLink,
  safeHref,
  sourceHost,
  titleHint,
} from '#/lib/jobs-view'

const good = {
  company: 'Acme',
  title: 'Flutter Engineer',
  location: '',
  text: 'Build apps.',
}

describe('checkAdd', () => {
  it('collapses whitespace and builds the body, leaving out empty optional fields', () => {
    expect(
      checkAdd(
        { ...good, company: '  Acme   Ltd ', location: ' Nairobi ' },
        ' https://x.example/j ',
      ),
    ).toEqual({
      ok: true,
      body: {
        company: 'Acme Ltd',
        title: 'Flutter Engineer',
        text: 'Build apps.',
        location: 'Nairobi',
        url: 'https://x.example/j',
      },
    })
    expect(checkAdd(good, null)).toEqual({
      ok: true,
      body: { company: 'Acme', title: 'Flutter Engineer', text: 'Build apps.' },
    })
  })

  it('says what is wrong beside each field', () => {
    const errs = (over: Partial<typeof good>, url: string | null = null) => {
      const r = checkAdd({ ...good, ...over }, url)
      return r.ok ? {} : r.errors
    }
    expect(errs({ company: '  ' })).toHaveProperty('company')
    expect(errs({ company: 'x'.repeat(121) })).toHaveProperty('company')
    expect(errs({ title: '' })).toHaveProperty('title')
    expect(errs({ title: 'x'.repeat(201) })).toHaveProperty('title')
    expect(errs({ location: 'x'.repeat(121) })).toHaveProperty('location')
    expect(errs({ text: '  ab ' })).toHaveProperty('text')
    expect(errs({ text: 'x'.repeat(100_001) })).toHaveProperty('text')
    expect(errs({}, 'ftp://x.example')).toHaveProperty('url')
    expect(errs({}, 'not a link')).toHaveProperty('url')
    expect(errs({}, 'https://u:p@x.example/')).toHaveProperty('url')
  })

  it('counts the collapsed length like the engine', () => {
    const spaced = Array(60).fill('ab').join('  ') // 238 raw, 179 collapsed
    expect(checkAdd({ ...good, title: spaced }, null)).toMatchObject({
      ok: true,
    })
    expect(
      checkAdd({ ...good, title: Array(120).fill('ab').join('  ') }, null),
    ).toMatchObject({ ok: false })
  })
})

describe('links', () => {
  it('accepts only http and https addresses with a host and no credentials', () => {
    expect(readableLink('https://jobs.example.com/a?b=1')).toBe(true)
    expect(readableLink('http://localhost:3000/x')).toBe(true)
    for (const bad of [
      'javascript:alert(1)',
      'data:text/html,x',
      'ftp://x.example',
      '//x.example',
      'x.example',
      '',
      'https://a:b@x.example',
    ]) {
      expect(readableLink(bad)).toBe(false)
    }
  })

  it('shows a host and links only to safe addresses', () => {
    expect(sourceHost('https://www.jobs.example.com/a')).toBe(
      'jobs.example.com',
    )
    expect(sourceHost('javascript:alert(1)')).toBeNull()
    expect(sourceHost(null)).toBeNull()
    expect(safeHref('https://x.example/a b')).toBe('https://x.example/a%20b')
    expect(safeHref('javascript:alert(1)')).toBeNull()
    expect(safeHref(null)).toBeNull()
  })
})

describe('labels', () => {
  it('takes the first letter or digit for the tile', () => {
    expect(initialOf('acme')).toBe('A')
    expect(initialOf('  (Fieldnote)')).toBe('F')
    expect(initialOf('42 Labs')).toBe('4')
    expect(initialOf('---')).toBe('·')
  })

  it('says when a job was added', () => {
    const now = new Date(2026, 10, 10, 15, 0)
    expect(addedLabel(new Date(2026, 10, 10, 1, 0).toISOString(), now)).toBe(
      'Added today',
    )
    expect(addedLabel(new Date(2026, 10, 9, 23, 0).toISOString(), now)).toBe(
      'Added yesterday',
    )
    expect(addedLabel(new Date(2026, 10, 5, 12, 0).toISOString(), now)).toBe(
      'Added 5 days ago',
    )
    expect(addedLabel(new Date(2026, 8, 1, 12, 0).toISOString(), now)).toMatch(
      /^Added 1 Sept(ember)? 2026$/,
    )
    expect(addedLabel('not a date', now)).toBe('')
  })

  it('trims a page title to a starting point for the job title', () => {
    expect(titleHint('  Flutter   Engineer ')).toBe('Flutter Engineer')
    expect(titleHint(null)).toBe('')
    expect(titleHint('x'.repeat(300))).toHaveLength(200)
  })
})

describe('jobsCopy', () => {
  const codes = [
    'validation_failed',
    'already_exists',
    'limit_reached',
    'fetch_blocked',
    'robots_disallowed',
    'robots_unreadable',
    'not_a_page',
    'too_large',
    'fetch_failed',
    'rate_limited',
    'not_found',
    'network',
    'unexpected',
    'internal_error',
  ]

  it('has calm copy for every code and never shows a code or a status', () => {
    for (const code of codes) {
      const { title, body } = jobsCopy(code)
      expect(title.length).toBeGreaterThan(0)
      expect(`${title} ${body}`).not.toMatch(/_|\b[45]\d\d\b/)
    }
  })

  it('points to pasting the text after each fetch refusal', () => {
    for (const code of PASTE_INSTEAD) {
      expect(jobsCopy(code).body.toLowerCase()).toMatch(/paste|try again/)
    }
    expect(PASTE_INSTEAD.has('already_exists')).toBe(false)
  })
})
