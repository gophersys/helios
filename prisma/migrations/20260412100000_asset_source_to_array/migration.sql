-- Convert assetSource (single string) to assetSources (string array)
-- Wraps existing value into a single-element array for backward compatibility

ALTER TABLE "product_stage_configs"
  ADD COLUMN "assetSources" TEXT[] NOT NULL DEFAULT ARRAY['BUILD_SERVICE'];

-- Migrate existing data: wrap the old value into an array
UPDATE "product_stage_configs"
  SET "assetSources" = ARRAY["assetSource"];

-- Drop the old column
ALTER TABLE "product_stage_configs"
  DROP COLUMN "assetSource";
