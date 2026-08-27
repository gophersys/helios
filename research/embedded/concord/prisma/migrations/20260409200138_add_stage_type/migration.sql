-- CreateEnum
CREATE TYPE "StageType" AS ENUM ('VALIDATION', 'MANUFACTURING');

-- Add type column with default VALIDATION (backfills existing rows)
ALTER TABLE "product_stage_configs" ADD COLUMN "type" "StageType" NOT NULL DEFAULT 'VALIDATION';

-- Drop old unique constraint
ALTER TABLE "product_stage_configs" DROP CONSTRAINT IF EXISTS "product_stage_configs_productId_stage_boardRevisionId_key";

-- Create new unique constraint including type
CREATE UNIQUE INDEX "product_stage_configs_productId_type_stage_boardRevisionId_key" ON "product_stage_configs"("productId", "type", "stage", "boardRevisionId");

-- Add index for type-filtered queries
CREATE INDEX "product_stage_configs_productId_type_idx" ON "product_stage_configs"("productId", "type");

-- Backfill: any stage with stage=0 is manufacturing (from our earlier work)
UPDATE "product_stage_configs" SET "type" = 'MANUFACTURING', "stage" = 1 WHERE "stage" = 0;
