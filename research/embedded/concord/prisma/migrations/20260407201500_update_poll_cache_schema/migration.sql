-- AlterTable: Update poll_cache to support both branch and PR tracking
-- Old schema: (repoSlug, prId) — only tracked PRs
-- New schema: (repoSlug, type, refId) — tracks branches and PRs

-- Drop the old unique constraint
DROP INDEX IF EXISTS "poll_cache_repoSlug_prId_key";

-- Add new columns
ALTER TABLE "poll_cache" ADD COLUMN "type" TEXT NOT NULL DEFAULT 'pr';
ALTER TABLE "poll_cache" ADD COLUMN "refId" TEXT;
ALTER TABLE "poll_cache" ADD COLUMN "metadata" JSONB;

-- Migrate existing data: prId → refId (as string)
UPDATE "poll_cache" SET "refId" = CAST("prId" AS TEXT) WHERE "refId" IS NULL;

-- Make refId non-nullable now that data is migrated
ALTER TABLE "poll_cache" ALTER COLUMN "refId" SET NOT NULL;

-- Drop old prId column
ALTER TABLE "poll_cache" DROP COLUMN "prId";

-- Create new composite unique constraint
CREATE UNIQUE INDEX "poll_cache_repoSlug_type_refId_key" ON "poll_cache"("repoSlug", "type", "refId");
