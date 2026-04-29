-- ============================================================================
-- restore_test_package_stage_hardware
--
-- v0.5.0's `drop_capabilities` migration removed `hardware[]` from
-- `test_package_stages` because the legacy capability-matching system was
-- being deleted. v0.9.0 reintroduced the field for a different purpose: the
-- test app's `concord.yaml` declares per-stage hardware requirements
-- (`hardware: [mtib, fixture, jlink]`) that the platform persists so the
-- UI can render which resources each stage will consume *before* a run is
-- scheduled. The schema was updated but the migration was missed, so prod
-- inserts fail with: column "hardware" does not exist.
--
-- Add the column back with a safe default so existing rows aren't broken.
-- New uploads will populate it from `concord.yaml`.
-- ============================================================================

ALTER TABLE "test_package_stages"
    ADD COLUMN IF NOT EXISTS "hardware" TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[];
