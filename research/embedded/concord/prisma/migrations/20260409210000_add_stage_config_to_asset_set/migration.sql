-- Add stageConfigId FK to asset_sets (links assets to a specific stage config)
ALTER TABLE "asset_sets" ADD COLUMN "stageConfigId" TEXT;

-- FK constraint
ALTER TABLE "asset_sets" ADD CONSTRAINT "asset_sets_stageConfigId_fkey"
  FOREIGN KEY ("stageConfigId") REFERENCES "product_stage_configs"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;

-- Index for "latest asset set for stage config" queries
CREATE INDEX "asset_sets_stageConfigId_status_idx" ON "asset_sets"("stageConfigId", "status");
