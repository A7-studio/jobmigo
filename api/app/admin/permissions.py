OVERVIEW_READ = "overview.read"
USERS_READ = "users.read"
USERS_WRITE = "users.write"
BILLING_READ = "billing.read"
BILLING_REFUND = "billing.refund"
PRICING_WRITE = "pricing.write"
TICKETS_READ = "tickets.read"
TICKETS_REPLY = "tickets.reply"
JOBS_WRITE = "jobs.write"
AI_WRITE = "ai.write"
FLAGS_WRITE = "flags.write"
OPS_WRITE = "ops.write"
AUDIT_READ = "audit.read"

ALL_PERMISSIONS = (
    OVERVIEW_READ,
    USERS_READ,
    USERS_WRITE,
    BILLING_READ,
    BILLING_REFUND,
    PRICING_WRITE,
    TICKETS_READ,
    TICKETS_REPLY,
    JOBS_WRITE,
    AI_WRITE,
    FLAGS_WRITE,
    OPS_WRITE,
    AUDIT_READ,
)

# Staff matrix confirmed at review; changing it needs a new migration.
ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "support": (OVERVIEW_READ, USERS_READ, TICKETS_READ, TICKETS_REPLY),
    "finance": (OVERVIEW_READ, USERS_READ, BILLING_READ, BILLING_REFUND, PRICING_WRITE),
    "admin": tuple(p for p in ALL_PERMISSIONS if p not in (BILLING_REFUND, PRICING_WRITE)),
    "owner": ALL_PERMISSIONS,
}
