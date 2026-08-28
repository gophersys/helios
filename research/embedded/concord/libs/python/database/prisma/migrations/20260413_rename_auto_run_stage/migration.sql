-- Rename autoValidate -> autoRunStage on pipeline_runs table (Prisma model: BuildRun)
ALTER TABLE "pipeline_runs" RENAME COLUMN "autoValidate" TO "autoRunStage";

-- Add assetSources column to product_stage_configs (may already exist from prior raw SQL migration)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'product_stage_configs' AND column_name = 'assetSources'
    ) THEN
        ALTER TABLE "product_stage_configs" ADD COLUMN "assetSources" TEXT[] NOT NULL DEFAULT ARRAY['BUILD_SERVICE'];
    END IF;
END $$;

-- Decouple validation_queue_entries from build system: buildRunId -> assetSetId
-- Add assetSetId column
ALTER TABLE "validation_queue_entries" ADD COLUMN "assetSetId" TEXT;

-- Backfill: for existing queue entries, resolve assetSetId from the build run's asset set
UPDATE "validation_queue_entries" vqe
SET "assetSetId" = a."id"
FROM "asset_sets" a
WHERE a."buildRunId" = vqe."buildRunId"
  AND vqe."assetSetId" IS NULL;

-- Make assetSetId NOT NULL (after backfill)
ALTER TABLE "validation_queue_entries" ALTER COLUMN "assetSetId" SET NOT NULL;

-- Drop buildRunId column and its index
DROP INDEX IF EXISTS "validation_queue_entries_buildRunId_idx";
ALTER TABLE "validation_queue_entries" DROP COLUMN "buildRunId";

-- Add index on assetSetId
CREATE INDEX IF NOT EXISTS "validation_queue_entries_assetSetId_idx" ON "validation_queue_entries"("assetSetId");

-- Add FK constraint
ALTER TABLE "validation_queue_entries"
    ADD CONSTRAINT "validation_queue_entries_assetSetId_fkey"
    FOREIGN KEY ("assetSetId") REFERENCES "asset_sets"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
