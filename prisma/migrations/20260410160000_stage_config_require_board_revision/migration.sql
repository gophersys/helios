-- Make boardRevisionId required on ProductStageConfig.
-- Every stage config must be explicitly scoped to a hardware revision.
-- No more product-wide (NULL revision) stages.

-- Delete any existing stage configs with NULL boardRevisionId
-- (there should be none since we wiped Alpha's data, but be safe)
DELETE FROM "product_stage_configs" WHERE "boardRevisionId" IS NULL;

-- Make the column NOT NULL
ALTER TABLE "product_stage_configs" ALTER COLUMN "boardRevisionId" SET NOT NULL;
