-- Convert assetSource (single string) to assetSources (string array)
-- Safe for both fresh DBs (where assetSources already exists) and upgrades

-- Add column if it doesn't exist (idempotent)
ALTER TABLE "product_stage_configs"
  ADD COLUMN IF NOT EXISTS "assetSources" TEXT[] NOT NULL DEFAULT ARRAY['BUILD_SERVICE'];

-- Migrate existing data if old column exists
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'product_stage_configs' AND column_name = 'assetSource'
  ) THEN
    UPDATE "product_stage_configs" SET "assetSources" = ARRAY["assetSource"];
    ALTER TABLE "product_stage_configs" DROP COLUMN "assetSource";
  END IF;
END $$;
