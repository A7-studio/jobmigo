import { describe, expect, it } from 'vitest'
import { callEngine } from '#/server/engine/client'

/**
 * Calls the running local engine (docker compose `engine`). Skipped unless
 * ENGINE_LIVE_TEST=1:  ENGINE_LIVE_TEST=1 npm test -- tests/engine-live.test.ts
 */
const live = process.env.ENGINE_LIVE_TEST === '1'
const USER = '3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44'

describe.skipIf(!live)('live engine check', () => {
  it('reaches the engine and gets the user id back', async () => {
    expect(await callEngine('/internal/whoami', { userId: USER })).toEqual({
      userId: USER,
    })
  })
})
