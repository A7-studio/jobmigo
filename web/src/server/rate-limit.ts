export type RateLimiter = {
  /** Returns true when the call is allowed, false when the key is over its limit. */
  take: (key: string) => boolean
  /** Number of keys currently tracked (for tests and monitoring). */
  size: () => number
}

const MAX_KEYS = 10_000

/** In-memory fixed-window limiter. Resets on restart, which is fine for one server. */
export function createRateLimiter(options: {
  max: number
  windowMs: number
  maxKeys?: number
  now?: () => number
}): RateLimiter {
  const now = options.now ?? Date.now
  const maxKeys = options.maxKeys ?? MAX_KEYS
  const windows = new Map<string, { count: number; resetAt: number }>()

  function makeRoom(time: number) {
    if (windows.size < maxKeys) return
    for (const [key, window] of windows) {
      if (window.resetAt <= time) windows.delete(key)
    }
    // Still full: drop the oldest keys (Map keeps insertion order).
    for (const key of windows.keys()) {
      if (windows.size < maxKeys) break
      windows.delete(key)
    }
  }

  return {
    take(key) {
      const time = now()
      const current = windows.get(key)
      if (!current || current.resetAt <= time) {
        if (!current) makeRoom(time)
        windows.set(key, { count: 1, resetAt: time + options.windowMs })
        return true
      }
      if (current.count >= options.max) return false
      current.count += 1
      return true
    },
    size: () => windows.size,
  }
}
