-- Rename buildRunId → assetSetId on validation_queue_entries
-- The queue entry now references an AssetSet (decoupled from BuildRun)
ALTER TABLE "validation_queue_entries" RENAME COLUMN "buildRunId" TO "assetSetId";

-- Update FK to point to asset_sets instead of build_runs
ALTER TABLE "validation_queue_entries" DROP CONSTRAINT IF EXISTS "validation_queue_entries_buildRunId_fkey";
ALTER TABLE "validation_queue_entries" ADD CONSTRAINT "validation_queue_entries_assetSetId_fkey"
  FOREIGN KEY ("assetSetId") REFERENCES "asset_sets"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Update index
DROP INDEX IF EXISTS "validation_queue_entries_buildRunId_idx";
CREATE INDEX "validation_queue_entries_assetSetId_idx" ON "validation_queue_entries"("assetSetId");
