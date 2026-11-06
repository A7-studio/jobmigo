import type { Db } from './db/client'
import { auditLog } from './db/schema'
import { DomainError } from './errors'

export class AuditReasonRequiredError extends DomainError {
  constructor() {
    super(400, 'reason_required', 'Give a reason for this action.')
  }
}

export type AuditInput = {
  action: string
  targetType: string
  targetId?: string | null
  reason: string
  before?: unknown
  after?: unknown
  ip?: string | null
}

/**
 * Append an audit row. Pass the caller's transaction so the row commits or rolls
 * back with the change it records. A reason is always required.
 */
export async function recordAudit(
  tx: Pick<Db, 'insert'>,
  staff: { userId: string },
  input: AuditInput,
) {
  const reason = input.reason.trim()
  if (!reason) throw new AuditReasonRequiredError()
  const rows = await tx
    .insert(auditLog)
    .values({
      staffId: staff.userId,
      action: input.action,
      targetType: input.targetType,
      targetId: input.targetId ?? null,
      reason,
      before: input.before ?? null,
      after: input.after ?? null,
      ip: input.ip ?? null,
    })
    .returning()
  return rows[0]
}
