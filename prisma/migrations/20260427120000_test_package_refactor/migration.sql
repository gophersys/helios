-- Test-package refactor: schema reshape for the new validation/manufacturing
-- model. The end state:
--
--   • FixtureDesign is owned 1:1 by a TestPackage. The old "(name, revision)"
--     dedup key let designs drift independently of the test code that
--     declares them; flipping ownership makes a package's manifest the sole
--     authority for fixture configuration.
--
--   • Fixture instances carry a `purpose` (DEV vs RELEASE) so dev packages
--     can only run on dev rigs and released packages can only run on the
--     production floor. Existing fixtures default to RELEASE — that matches
--     pre-refactor behavior.
--
--   • ProductStageConfig.releasedTestPackageId is the explicit "blessed"
--     package for a stage. Validation auto-runs gate on it; manufacturing
--     sessions can override per-session.
--
--   • ManufacturingSession.testPackageId records the wizard's package choice
--     (released or dev). Null = resolve at runner-deploy time.
--
--   • TestPackage drops two dead v1 fields (stagesEnabled, gitDirty) and
--     renames schemaVersion → manifestVersion with NOT NULL "1.0" default.
--     The dev-{sha}-... prefix on already-released versions is normalized
--     into releasedVersion so the misleading "dev-" stops appearing in
--     consumer UIs.
--
-- Production state (queried 2026-04-27): 21 packages, all schemaVersion=2.0,
-- all RELEASED, all MANUFACTURING. 1 staging dev package. No v1 rows. The
-- backfill steps below are written for that state but tolerate any mix.

-- 1. New enum
CREATE TYPE "FixturePurpose" AS ENUM ('DEV', 'RELEASE');

-- 2. New columns (all nullable / defaulted so adding them is safe)
ALTER TABLE "fixtures" ADD COLUMN "purpose" "FixturePurpose" NOT NULL DEFAULT 'RELEASE';
ALTER TABLE "manufacturing_sessions" ADD COLUMN "testPackageId" TEXT;
ALTER TABLE "product_stage_configs" ADD COLUMN "releasedTestPackageId" TEXT;
ALTER TABLE "fixture_designs" ADD COLUMN "testPackageId" TEXT;
ALTER TABLE "fixture_designs" ADD COLUMN "status" "TestPackageStatus";

-- 3. Backfill: every existing FixtureDesign that's referenced by a TestPackage
--    becomes owned by that package. Today the relation runs in the opposite
--    direction (TestPackage.fixtureDesignId), so we copy it across before
--    dropping the old column.
UPDATE "fixture_designs" fd
SET "testPackageId" = tp.id,
    "status" = tp.status
FROM "test_packages" tp
WHERE tp."fixtureDesignId" = fd.id;

-- 4. Designs that no test package points at are orphans under the new model.
--    Investigation confirmed every existing fixture design originated from
--    a test-package upload, so dropping unreferenced rows is safe; nothing
--    else creates fixture_designs records.
DELETE FROM "fixture_designs" WHERE "testPackageId" IS NULL;

-- 5. Tighten the new fixture_designs columns + flip the unique constraint.
ALTER TABLE "fixture_designs" ALTER COLUMN "testPackageId" SET NOT NULL;
ALTER TABLE "fixture_designs" ALTER COLUMN "status" SET NOT NULL;
ALTER TABLE "fixture_designs" DROP CONSTRAINT "fixture_designs_name_revision_key";
CREATE UNIQUE INDEX "fixture_designs_testPackageId_key" ON "fixture_designs"("testPackageId");
CREATE INDEX "fixture_designs_status_idx" ON "fixture_designs"("status");
ALTER TABLE "fixture_designs"
    ADD CONSTRAINT "fixture_designs_testPackageId_fkey"
    FOREIGN KEY ("testPackageId") REFERENCES "test_packages"("id") ON DELETE CASCADE;

-- 6. Drop the now-redundant TestPackage.fixtureDesignId — relation moved to
--    FixtureDesign.testPackageId above.
DROP INDEX IF EXISTS "test_packages_fixtureDesignId_idx";
ALTER TABLE "test_packages" DROP COLUMN "fixtureDesignId";

-- 7. Drop dead v1 fields.
ALTER TABLE "test_packages" DROP COLUMN "stagesEnabled";
ALTER TABLE "test_packages" DROP COLUMN "gitDirty";

-- 8. schemaVersion → manifestVersion, NOT NULL with "1.0" default.
ALTER TABLE "test_packages" RENAME COLUMN "schemaVersion" TO "manifestVersion";
UPDATE "test_packages" SET "manifestVersion" = '1.0' WHERE "manifestVersion" IS NULL OR "manifestVersion" = '2.0';
ALTER TABLE "test_packages" ALTER COLUMN "manifestVersion" SET NOT NULL;
ALTER TABLE "test_packages" ALTER COLUMN "manifestVersion" SET DEFAULT '1.0';

-- 9. Strip the misleading "dev-" prefix from already-released versions. A
--    "dev-{sha}-{epoch}" version that's been promoted to RELEASED reads
--    confusingly in the UI; copying the bare suffix into releasedVersion
--    is what the new release endpoint will do for new releases too.
UPDATE "test_packages"
SET "releasedVersion" = regexp_replace("version", '^dev-', '')
WHERE "status" = 'RELEASED' AND "releasedVersion" IS NULL;

-- 10. FK constraints + indexes for the two new columns on existing tables.
ALTER TABLE "manufacturing_sessions"
    ADD CONSTRAINT "manufacturing_sessions_testPackageId_fkey"
    FOREIGN KEY ("testPackageId") REFERENCES "test_packages"("id") ON DELETE SET NULL;
CREATE INDEX "manufacturing_sessions_testPackageId_idx" ON "manufacturing_sessions"("testPackageId");

ALTER TABLE "product_stage_configs"
    ADD CONSTRAINT "product_stage_configs_releasedTestPackageId_fkey"
    FOREIGN KEY ("releasedTestPackageId") REFERENCES "test_packages"("id") ON DELETE SET NULL;
CREATE INDEX "product_stage_configs_releasedTestPackageId_idx" ON "product_stage_configs"("releasedTestPackageId");
