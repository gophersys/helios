-- AlterTable: manufacturing_sessions — runner lifecycle + firmware fields
ALTER TABLE "manufacturing_sessions" ADD COLUMN "runnerStatus" TEXT;
ALTER TABLE "manufacturing_sessions" ADD COLUMN "runnerDeploymentName" TEXT;
ALTER TABLE "manufacturing_sessions" ADD COLUMN "runnerLastHeartbeat" TIMESTAMP(3);
ALTER TABLE "manufacturing_sessions" ADD COLUMN "assetSetId" TEXT;

-- AlterTable: test_packages — type enum + release lifecycle fields
CREATE TYPE "TestPackageType" AS ENUM ('VALIDATION', 'MANUFACTURING');
ALTER TABLE "test_packages" ADD COLUMN "type" "TestPackageType" NOT NULL DEFAULT 'VALIDATION';
ALTER TABLE "test_packages" ADD COLUMN "releasedVersion" TEXT;
ALTER TABLE "test_packages" ADD COLUMN "releasedAt" TIMESTAMP(3);
ALTER TABLE "test_packages" ADD COLUMN "releasedById" TEXT;

-- AddForeignKey: manufacturing_sessions.assetSetId -> asset_sets.id
ALTER TABLE "manufacturing_sessions" ADD CONSTRAINT "manufacturing_sessions_assetSetId_fkey" FOREIGN KEY ("assetSetId") REFERENCES "asset_sets"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey: test_packages.releasedById -> users.id
ALTER TABLE "test_packages" ADD CONSTRAINT "test_packages_releasedById_fkey" FOREIGN KEY ("releasedById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- CreateIndex: unique (productId, releasedVersion, type) on test_packages
CREATE UNIQUE INDEX "test_packages_productId_releasedVersion_type_key" ON "test_packages"("productId", "releasedVersion", "type");

-- CreateIndex: assetSetId on manufacturing_sessions
CREATE INDEX "manufacturing_sessions_assetSetId_idx" ON "manufacturing_sessions"("assetSetId");

-- CreateIndex: releasedById on test_packages
CREATE INDEX "test_packages_releasedById_idx" ON "test_packages"("releasedById");
