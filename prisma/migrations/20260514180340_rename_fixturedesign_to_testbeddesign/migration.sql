-- Rename the FixtureDesign Prisma model + table to TestBedDesign.
--
-- Concord's `Fixture` model (the physical rig) stays unchanged. Only the
-- design-spec row produced by the AST extractor from the user's `TestBed`
-- class is renamed, so the platform vocabulary lines up: a TestBed
-- (user-Python class) populates a TestBedDesign (Concord storage).

-- 1. Rename the table.
ALTER TABLE "fixture_designs" RENAME TO "test_bed_designs";

-- 2. Rename the table's indexes (Prisma's table-prefixed convention).
ALTER INDEX "fixture_designs_pkey"                       RENAME TO "test_bed_designs_pkey";
ALTER INDEX "fixture_designs_testPackageId_key"          RENAME TO "test_bed_designs_testPackageId_key";
ALTER INDEX "fixture_designs_boardRevisionId_idx"        RENAME TO "test_bed_designs_boardRevisionId_idx";
ALTER INDEX "fixture_designs_status_idx"                 RENAME TO "test_bed_designs_status_idx";
ALTER INDEX "fixture_designs_boardRevisionId_type_idx"   RENAME TO "test_bed_designs_boardRevisionId_type_idx";

-- 3. Rename the renamed table's own foreign-key constraints.
ALTER TABLE "test_bed_designs" RENAME CONSTRAINT "fixture_designs_boardRevisionId_fkey" TO "test_bed_designs_boardRevisionId_fkey";
ALTER TABLE "test_bed_designs" RENAME CONSTRAINT "fixture_designs_createdById_fkey"     TO "test_bed_designs_createdById_fkey";
ALTER TABLE "test_bed_designs" RENAME CONSTRAINT "fixture_designs_testPackageId_fkey"   TO "test_bed_designs_testPackageId_fkey";

-- 4. Foreign keys pointing TO this table from `fixtures` and other tables
--    track by OID, not by name. Their constraint names live on the source
--    table and stay as-is. No rename needed there.
