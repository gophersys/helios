-- AlterTable: Add createdById to products
ALTER TABLE "products" ADD COLUMN "createdById" TEXT;

-- AlterTable: Add createdById to boards
ALTER TABLE "boards" ADD COLUMN "createdById" TEXT;

-- AlterTable: Add createdById to board_revisions
ALTER TABLE "board_revisions" ADD COLUMN "createdById" TEXT;

-- AlterTable: Add createdById to product_stage_configs
ALTER TABLE "product_stage_configs" ADD COLUMN "createdById" TEXT;

-- AlterTable: Add createdById to fixture_designs
ALTER TABLE "fixture_designs" ADD COLUMN "createdById" TEXT;

-- AlterTable: Add createdById to fixtures
ALTER TABLE "fixtures" ADD COLUMN "createdById" TEXT;

-- AlterTable: Add createdById to build_runs (BuildRun)
ALTER TABLE "build_runs" ADD COLUMN "createdById" TEXT;

-- AlterTable: Add updatedAt to modem_firmwares
ALTER TABLE "modem_firmwares" ADD COLUMN "updatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP;

-- AddForeignKey
ALTER TABLE "products" ADD CONSTRAINT "products_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "boards" ADD CONSTRAINT "boards_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "board_revisions" ADD CONSTRAINT "board_revisions_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "product_stage_configs" ADD CONSTRAINT "product_stage_configs_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "fixture_designs" ADD CONSTRAINT "fixture_designs_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "fixtures" ADD CONSTRAINT "fixtures_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "build_runs" ADD CONSTRAINT "build_runs_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
