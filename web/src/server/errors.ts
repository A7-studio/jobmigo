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

export class AiNotConfiguredError extends DomainError {
  constructor(message: string) {
    super(503, 'ai_not_configured', message)
  }
}

export class AiUnavailableError extends DomainError {
  constructor(message = 'The AI service is unavailable. Try again shortly.') {
    super(502, 'ai_unavailable', message)
  }
}

export class AiOutputInvalidError extends DomainError {
  constructor(message = 'The AI returned an answer we could not use.') {
    super(502, 'ai_output_invalid', message)
  }
}

export class AiInputInvalidError extends DomainError {
  constructor(message = 'The input for this AI task is not valid.') {
    super(400, 'ai_input_invalid', message)
  }
}

export class EngineNotConfiguredError extends DomainError {
  constructor(message: string) {
    super(503, 'engine_not_configured', message)
  }
}

export class EngineUnavailableError extends DomainError {
  constructor(message = 'The AI service is unavailable. Try again shortly.') {
    super(502, 'engine_unavailable', message)
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
