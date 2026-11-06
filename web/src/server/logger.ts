import { AsyncLocalStorage } from 'node:async_hooks'

type Level = 'info' | 'warn' | 'error'

const requestContext = new AsyncLocalStorage<{ requestId: string }>()

export function runWithRequestId<T>(requestId: string, fn: () => T): T {
  return requestContext.run({ requestId }, fn)
}

export function currentRequestId(): string | undefined {
  return requestContext.getStore()?.requestId
}

function write(
  level: Level,
  message: string,
  fields?: Record<string, unknown>,
) {
  const line = JSON.stringify({
    level,
    time: new Date().toISOString(),
    message,
    requestId: currentRequestId(),
    ...fields,
  })
  if (level === 'error') console.error(line)
  else console.log(line)
}

/** One JSON line per event. Callers pass ids and codes, never emails, tokens or CV text. */
export const logger = {
  info: (message: string, fields?: Record<string, unknown>) =>
    write('info', message, fields),
  warn: (message: string, fields?: Record<string, unknown>) =>
    write('warn', message, fields),
  error: (message: string, fields?: Record<string, unknown>) =>
    write('error', message, fields),
}
