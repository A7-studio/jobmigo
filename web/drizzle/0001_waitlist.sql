CREATE TABLE "waitlist_signup" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"email" text NOT NULL,
	"status" text DEFAULT 'pending' NOT NULL,
	"consent_text_version" text NOT NULL,
	"consented_at" timestamp with time zone NOT NULL,
	"source" text,
	"token_hash" text NOT NULL,
	"token_sent_at" timestamp with time zone NOT NULL,
	"emails_sent" integer DEFAULT 1 NOT NULL,
	"confirmed_at" timestamp with time zone,
	"unsubscribed_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "waitlist_signup_email_unique" UNIQUE("email"),
	CONSTRAINT "ck_waitlist_signup_status" CHECK ("waitlist_signup"."status" in ('pending', 'confirmed', 'unsubscribed'))
);
--> statement-breakpoint
CREATE INDEX "waitlist_signup_token_hash_idx" ON "waitlist_signup" USING btree ("token_hash");