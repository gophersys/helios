-- ============================================================================
-- collapse_status_lockstate
--
-- Two contradictions on the fixture page traced to overlapping fields that
-- tried to answer the same question. This migration removes the duplication:
--
--   • Node.status (DB column, NodeStatus enum) — was set to ONLINE on first
--     deploy and never updated. Replaced with ``Node.disabled`` (admin
--     override) plus a live computation in the API serializer that reads K8s
--     pod readiness + gRPC probe.
--
--   • Fixture.status (DB column, FixtureStatus enum AVAILABLE/LOCKED/OFFLINE/
--     MAINTENANCE) — conflated lock-state with health. Renamed to
--     ``Fixture.lockState`` (FixtureLockState enum FREE/IN_USE/MAINTENANCE).
--     OFFLINE was a leak from health into lock state and is dropped.
--
-- ``Fixture.assignable`` and ``Fixture.assignableReason`` are computed at
-- serialize time (lockState == FREE && health == READY); they have no DB
-- representation.
-- ============================================================================

-- 1. New enums.
CREATE TYPE "FixtureLockState" AS ENUM ('FREE', 'IN_USE', 'MAINTENANCE');

-- 2. Fixture: rename + retype the column with explicit value mapping.
ALTER TABLE "fixtures" ADD COLUMN "lockState" "FixtureLockState" NOT NULL DEFAULT 'FREE';
UPDATE "fixtures" SET "lockState" = CASE
    WHEN "status" = 'AVAILABLE'   THEN 'FREE'::"FixtureLockState"
    WHEN "status" = 'LOCKED'      THEN 'IN_USE'::"FixtureLockState"
    WHEN "status" = 'OFFLINE'     THEN 'FREE'::"FixtureLockState"  -- health leak — collapse to FREE
    WHEN "status" = 'MAINTENANCE' THEN 'MAINTENANCE'::"FixtureLockState"
    ELSE 'FREE'::"FixtureLockState"
END;

-- 3. Drop legacy index + column on Fixture.
DROP INDEX IF EXISTS "fixtures_productId_status_idx";
DROP INDEX IF EXISTS "fixtures_status_idx";
ALTER TABLE "fixtures" DROP COLUMN "status";
DROP TYPE IF EXISTS "FixtureStatus";

-- 4. New indexes on lockState.
CREATE INDEX "fixtures_productId_lockState_idx" ON "fixtures"("productId", "lockState");
CREATE INDEX "fixtures_lockState_idx" ON "fixtures"("lockState");

-- 5. Node: add admin override flag.
ALTER TABLE "nodes" ADD COLUMN "disabled" BOOLEAN NOT NULL DEFAULT false;
-- Preserve existing admin overrides: any node previously stamped MAINTENANCE
-- was an admin decision; carry that intent across.
UPDATE "nodes" SET "disabled" = true WHERE "status" = 'MAINTENANCE';

-- 6. Drop legacy column + enum on Node.
ALTER TABLE "nodes" DROP COLUMN "status";
DROP TYPE IF EXISTS "NodeStatus";
