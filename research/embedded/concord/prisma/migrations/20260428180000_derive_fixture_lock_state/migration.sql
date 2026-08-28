-- ============================================================================
-- derive_fixture_lock_state
--
-- Same architectural lesson as v0.7.0 (collapse_status_lockstate): a stored
-- column that mirrors live state from another table drifts when any unlock
-- path fails. v0.7.0 already collapsed Node.status. This migration finishes
-- the job for Fixture.
--
-- Drops:
--   • Fixture.lockState (FixtureLockState enum FREE/IN_USE/MAINTENANCE)
--   • Fixture.lockedBy  (the session/run id holding the lock)
--   • Fixture.lockedAt
--   • indexes on lockState
--   • the FixtureLockState enum itself
--
-- Adds:
--   • Fixture.disabled (Boolean) — admin override, the *only* persisted
--     fixture state. When true, the API serializes the fixture as
--     lockState=MAINTENANCE.
--
-- The API's lockState/lockedBy/lockedAt fields are computed live at
-- serialize time:
--   - disabled=true                                  → MAINTENANCE
--   - any ManufacturingSession.status='ACTIVE' on it → IN_USE
--   - any TestRun.status='ACTIVE' on it              → IN_USE
--   - otherwise                                      → FREE
-- ============================================================================

-- 1. Add the new admin-override flag.
ALTER TABLE "fixtures" ADD COLUMN "disabled" BOOLEAN NOT NULL DEFAULT false;

-- 2. Preserve admin intent: any fixture currently MAINTENANCE was an admin
--    decision to take it out of rotation. Carry that across.
UPDATE "fixtures" SET "disabled" = true WHERE "lockState" = 'MAINTENANCE';

-- 3. Drop legacy indexes on lockState.
DROP INDEX IF EXISTS "fixtures_productId_lockState_idx";
DROP INDEX IF EXISTS "fixtures_lockState_idx";

-- 4. Drop the legacy columns.
ALTER TABLE "fixtures" DROP COLUMN "lockState";
ALTER TABLE "fixtures" DROP COLUMN "lockedBy";
ALTER TABLE "fixtures" DROP COLUMN "lockedAt";

-- 5. Drop the now-unused enum type.
DROP TYPE IF EXISTS "FixtureLockState";
