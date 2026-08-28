-- Add type, slotDefinitions, testPackageId to fixture_designs
ALTER TABLE "fixture_designs" ADD COLUMN "type" "StageType" NOT NULL DEFAULT 'VALIDATION';
ALTER TABLE "fixture_designs" ADD COLUMN "slotDefinitions" JSONB;
ALTER TABLE "fixture_designs" ADD COLUMN "testPackageId" TEXT;

-- FK to test_packages
ALTER TABLE "fixture_designs" ADD CONSTRAINT "fixture_designs_testPackageId_fkey"
  FOREIGN KEY ("testPackageId") REFERENCES "test_packages"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;

-- Index for type-filtered queries
CREATE INDEX "fixture_designs_boardRevisionId_type_idx" ON "fixture_designs"("boardRevisionId", "type");
