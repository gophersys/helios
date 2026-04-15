-- AlterTable
ALTER TABLE "asset_sets" ADD COLUMN IF NOT EXISTS "stageType" TEXT;

-- CreateIndex
CREATE INDEX IF NOT EXISTS "asset_sets_stageType_idx" ON "asset_sets"("productId", "stage", "stageType", "status");
