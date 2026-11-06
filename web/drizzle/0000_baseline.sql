CREATE TABLE "audit_log" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"staff_id" uuid NOT NULL,
	"action" text NOT NULL,
	"target_type" text NOT NULL,
	"target_id" uuid,
	"before" jsonb,
	"after" jsonb,
	"reason" text NOT NULL,
	"ip" text,
	"at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "ck_audit_log_reason_not_empty" CHECK (length(trim("audit_log"."reason")) > 0)
);
--> statement-breakpoint
CREATE TABLE "auth_account" (
	"id" text PRIMARY KEY NOT NULL,
	"account_id" text NOT NULL,
	"provider_id" text NOT NULL,
	"user_id" text NOT NULL,
	"access_token" text,
	"refresh_token" text,
	"id_token" text,
	"access_token_expires_at" timestamp with time zone,
	"refresh_token_expires_at" timestamp with time zone,
	"scope" text,
	"password" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone NOT NULL
);
--> statement-breakpoint
CREATE TABLE "auth_session" (
	"id" text PRIMARY KEY NOT NULL,
	"expires_at" timestamp with time zone NOT NULL,
	"token" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone NOT NULL,
	"ip_address" text,
	"user_agent" text,
	"user_id" text NOT NULL,
	CONSTRAINT "auth_session_token_unique" UNIQUE("token")
);
--> statement-breakpoint
CREATE TABLE "auth_user" (
	"id" text PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"email" text NOT NULL,
	"email_verified" boolean DEFAULT false NOT NULL,
	"image" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "auth_user_email_unique" UNIQUE("email")
);
--> statement-breakpoint
CREATE TABLE "auth_verification" (
	"id" text PRIMARY KEY NOT NULL,
	"identifier" text NOT NULL,
	"value" text NOT NULL,
	"expires_at" timestamp with time zone NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "role" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"name" text NOT NULL,
	CONSTRAINT "role_name_unique" UNIQUE("name")
);
--> statement-breakpoint
CREATE TABLE "role_permission" (
	"role_id" uuid NOT NULL,
	"permission" text NOT NULL,
	CONSTRAINT "role_permission_role_id_permission_pk" PRIMARY KEY("role_id","permission")
);
--> statement-breakpoint
CREATE TABLE "staff_member" (
	"user_id" uuid PRIMARY KEY NOT NULL,
	"role_id" uuid NOT NULL,
	"mfa_enforced" boolean DEFAULT true NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "user" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"auth_subject" text NOT NULL,
	"email" text NOT NULL,
	"display_name" text,
	"locale" text DEFAULT 'en' NOT NULL,
	"timezone" text DEFAULT 'Africa/Nairobi' NOT NULL,
	"status" text DEFAULT 'active' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "user_auth_subject_unique" UNIQUE("auth_subject"),
	CONSTRAINT "user_email_unique" UNIQUE("email"),
	CONSTRAINT "ck_user_status" CHECK ("user"."status" in ('active', 'suspended', 'deleted'))
);
--> statement-breakpoint
ALTER TABLE "audit_log" ADD CONSTRAINT "audit_log_staff_id_staff_member_user_id_fk" FOREIGN KEY ("staff_id") REFERENCES "public"."staff_member"("user_id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "auth_account" ADD CONSTRAINT "auth_account_user_id_auth_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."auth_user"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "auth_session" ADD CONSTRAINT "auth_session_user_id_auth_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."auth_user"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "role_permission" ADD CONSTRAINT "role_permission_role_id_role_id_fk" FOREIGN KEY ("role_id") REFERENCES "public"."role"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "staff_member" ADD CONSTRAINT "staff_member_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "staff_member" ADD CONSTRAINT "staff_member_role_id_role_id_fk" FOREIGN KEY ("role_id") REFERENCES "public"."role"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "auth_account_user_id_idx" ON "auth_account" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "auth_session_user_id_idx" ON "auth_session" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "auth_verification_identifier_idx" ON "auth_verification" USING btree ("identifier");

--> statement-breakpoint
-- Seed: roles and the frozen permission matrix
INSERT INTO "role" ("name") VALUES ('support');
--> statement-breakpoint
INSERT INTO "role_permission" ("role_id", "permission") SELECT r."id", p.perm FROM "role" r, (VALUES ('overview.read'),('users.read'),('tickets.read'),('tickets.reply')) AS p(perm) WHERE r."name" = 'support';
--> statement-breakpoint
INSERT INTO "role" ("name") VALUES ('finance');
--> statement-breakpoint
INSERT INTO "role_permission" ("role_id", "permission") SELECT r."id", p.perm FROM "role" r, (VALUES ('overview.read'),('users.read'),('billing.read'),('billing.refund'),('pricing.write')) AS p(perm) WHERE r."name" = 'finance';
--> statement-breakpoint
INSERT INTO "role" ("name") VALUES ('admin');
--> statement-breakpoint
INSERT INTO "role_permission" ("role_id", "permission") SELECT r."id", p.perm FROM "role" r, (VALUES ('overview.read'),('users.read'),('users.write'),('billing.read'),('tickets.read'),('tickets.reply'),('jobs.write'),('ai.write'),('flags.write'),('ops.write'),('audit.read')) AS p(perm) WHERE r."name" = 'admin';
--> statement-breakpoint
INSERT INTO "role" ("name") VALUES ('owner');
--> statement-breakpoint
INSERT INTO "role_permission" ("role_id", "permission") SELECT r."id", p.perm FROM "role" r, (VALUES ('overview.read'),('users.read'),('users.write'),('billing.read'),('billing.refund'),('pricing.write'),('tickets.read'),('tickets.reply'),('jobs.write'),('ai.write'),('flags.write'),('ops.write'),('audit.read')) AS p(perm) WHERE r."name" = 'owner';
--> statement-breakpoint
-- audit_log is append-only
CREATE FUNCTION audit_log_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only';
END;
$$ LANGUAGE plpgsql;
--> statement-breakpoint
CREATE TRIGGER audit_log_no_change
BEFORE UPDATE OR DELETE ON "audit_log"
FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
