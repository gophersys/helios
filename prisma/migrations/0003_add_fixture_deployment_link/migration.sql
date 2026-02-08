-- AlterTable
ALTER TABLE "deployments" ADD COLUMN "fixtureId" TEXT;

-- CreateIndex
CREATE INDEX "deployments_fixtureId_idx" ON "deployments"("fixtureId");

-- AddForeignKey
ALTER TABLE "deployments" ADD CONSTRAINT "deployments_fixtureId_fkey"
  FOREIGN KEY ("fixtureId") REFERENCES "fixtures"("id") ON DELETE SET NULL ON UPDATE CASCADE;
