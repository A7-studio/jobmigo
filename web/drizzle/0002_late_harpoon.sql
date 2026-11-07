CREATE TABLE "ai_cache" (
	"user_id" uuid NOT NULL,
	"cache_key" text NOT NULL,
	"task" text NOT NULL,
	"prompt_version" text NOT NULL,
	"output" jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "ai_cache_user_id_cache_key_pk" PRIMARY KEY("user_id","cache_key")
);
--> statement-breakpoint
CREATE TABLE "usage_event" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_id" uuid NOT NULL,
	"workflow" text NOT NULL,
	"provider" text NOT NULL,
	"model" text NOT NULL,
	"prompt_version" text NOT NULL,
	"tokens_in" integer NOT NULL,
	"tokens_out" integer NOT NULL,
	"cost_usd" numeric(12, 6),
	"cache_hit" boolean NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "ck_usage_event_workflow" CHECK ("usage_event"."workflow" in ('parse', 'screen', 'evaluate', 'tailor', 'reach_check', 'outreach')),
	CONSTRAINT "ck_usage_event_tokens" CHECK ("usage_event"."tokens_in" >= 0 and "usage_event"."tokens_out" >= 0)
);
--> statement-breakpoint
ALTER TABLE "ai_cache" ADD CONSTRAINT "ai_cache_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "usage_event" ADD CONSTRAINT "usage_event_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "usage_event_user_created_idx" ON "usage_event" USING btree ("user_id","created_at");