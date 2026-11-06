import { logger } from './logger'

export type ErrorResult = { status: number; code: string; message: string }

export class DomainError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'DomainError'
    this.status = status
    this.code = code
  }
}

export class UnauthorizedError extends DomainError {
  constructor(message = 'Sign in to continue.') {
    super(401, 'unauthorized', message)
  }
}

export class PermissionDeniedError extends DomainError {
  constructor(message = 'You do not have access to this.') {
    super(403, 'forbidden', message)
  }
}

export class NotFoundError extends DomainError {
  constructor(message = 'Not found.') {
    super(404, 'not_found', message)
  }
}

export class ConflictError extends DomainError {
  constructor(message: string) {
    super(409, 'conflict', message)
  }
}

/** Map any thrown value to the stable `{ code, message }` shape. */
export function toResult(error: unknown): ErrorResult {
  if (error instanceof DomainError) {
    return { status: error.status, code: error.code, message: error.message }
  }
  logger.error('unhandled error', {
    error: error instanceof Error ? error.name : typeof error,
  })
  return {
    status: 500,
    code: 'internal_error',
    message: 'Something went wrong.',
  }
}
