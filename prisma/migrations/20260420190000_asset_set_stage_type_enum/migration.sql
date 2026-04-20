-- Align asset_sets."stageType" column type with the Prisma schema.
--
-- Migration 20260415000000_add_asset_set_stage_type added the column as
-- ``TEXT`` even though the Prisma schema declares it ``StageType?``.
-- That drift silently worked for inserts (Prisma serializes enums to
-- text), but any WHERE clause comparing ``stageType`` to the enum
-- value raised ``operator does not exist: text = "StageType"`` in
-- Postgres — which is what broke the asset-zip upload flow
-- (``db.assetset.find_first(where={"stageType": stage_config.type})``).
--
-- Existing prod rows contain only valid enum literals (verified:
-- MANUFACTURING ×2, NULLs ×0). A plain cast is safe. Staging has zero
-- rows so the cast is trivially a no-op there.

ALTER TABLE "asset_sets"
  ALTER COLUMN "stageType" TYPE "StageType"
  USING "stageType"::"StageType";
