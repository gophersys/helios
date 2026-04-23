-- AlterTable
ALTER TABLE "test_packages" ADD COLUMN "boardRevisionId" TEXT;

-- AlterTable
ALTER TABLE "test_runs" ADD COLUMN "boardRevisionId" TEXT;

-- AddForeignKey
ALTER TABLE "test_packages" ADD CONSTRAINT "test_packages_boardRevisionId_fkey"
  FOREIGN KEY ("boardRevisionId") REFERENCES "board_revisions"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "test_runs" ADD CONSTRAINT "test_runs_boardRevisionId_fkey"
  FOREIGN KEY ("boardRevisionId") REFERENCES "board_revisions"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- CreateIndex
CREATE INDEX "test_packages_boardRevisionId_idx" ON "test_packages"("boardRevisionId");

-- CreateIndex
CREATE INDEX "test_runs_boardRevisionId_idx" ON "test_runs"("boardRevisionId");
