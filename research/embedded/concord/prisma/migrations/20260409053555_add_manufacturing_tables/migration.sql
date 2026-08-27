-- CreateEnum
CREATE TYPE "ManufacturingSessionStatus" AS ENUM ('ACTIVE', 'COMPLETED', 'CANCELLED');

-- CreateEnum
CREATE TYPE "PanelStatus" AS ENUM ('RUNNING', 'PASSED', 'FAILED', 'CANCELLED');

-- CreateEnum
CREATE TYPE "UnitStatus" AS ENUM ('RUNNING', 'PASSED', 'FAILED', 'ERROR');

-- AlterTable
ALTER TABLE "poll_cache" ALTER COLUMN "type" DROP DEFAULT;

-- CreateTable
CREATE TABLE "manufacturing_configs" (
    "id" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "boardRevisionId" TEXT NOT NULL,
    "enabled" BOOLEAN NOT NULL DEFAULT false,
    "stages" JSONB NOT NULL,
    "firmwareSource" TEXT NOT NULL DEFAULT 'latest_build',
    "firmwareSetId" TEXT,
    "personalizationConfig" JSONB,
    "passCriteria" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "manufacturing_configs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "manufacturing_sessions" (
    "id" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "fixtureId" TEXT NOT NULL,
    "status" "ManufacturingSessionStatus" NOT NULL DEFAULT 'ACTIVE',
    "operatorId" TEXT NOT NULL,
    "panelCount" INTEGER NOT NULL DEFAULT 0,
    "passedCount" INTEGER NOT NULL DEFAULT 0,
    "failedCount" INTEGER NOT NULL DEFAULT 0,
    "config" JSONB,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "endedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "manufacturing_sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "manufacturing_panels" (
    "id" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "panelIndex" INTEGER NOT NULL,
    "qrCode" TEXT NOT NULL,
    "status" "PanelStatus" NOT NULL DEFAULT 'RUNNING',
    "unitCount" INTEGER NOT NULL,
    "passedUnits" INTEGER NOT NULL DEFAULT 0,
    "failedUnits" INTEGER NOT NULL DEFAULT 0,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completedAt" TIMESTAMP(3),
    "durationMs" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "manufacturing_panels_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "manufacturing_units" (
    "id" TEXT NOT NULL,
    "panelId" TEXT NOT NULL,
    "slotIndex" INTEGER NOT NULL,
    "slotId" TEXT NOT NULL,
    "serialNumber" TEXT,
    "status" "UnitStatus" NOT NULL DEFAULT 'RUNNING',
    "stages" JSONB NOT NULL,
    "errorMessage" TEXT,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completedAt" TIMESTAMP(3),
    "durationMs" INTEGER,

    CONSTRAINT "manufacturing_units_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "manufacturing_configs_productId_boardRevisionId_key" ON "manufacturing_configs"("productId", "boardRevisionId");

-- CreateIndex
CREATE INDEX "manufacturing_sessions_productId_status_idx" ON "manufacturing_sessions"("productId", "status");

-- CreateIndex
CREATE INDEX "manufacturing_sessions_fixtureId_idx" ON "manufacturing_sessions"("fixtureId");

-- CreateIndex
CREATE INDEX "manufacturing_sessions_operatorId_idx" ON "manufacturing_sessions"("operatorId");

-- CreateIndex
CREATE UNIQUE INDEX "manufacturing_panels_sessionId_panelIndex_key" ON "manufacturing_panels"("sessionId", "panelIndex");

-- CreateIndex
CREATE UNIQUE INDEX "manufacturing_units_panelId_slotIndex_key" ON "manufacturing_units"("panelId", "slotIndex");

-- AddForeignKey
ALTER TABLE "manufacturing_configs" ADD CONSTRAINT "manufacturing_configs_productId_fkey" FOREIGN KEY ("productId") REFERENCES "products"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "manufacturing_configs" ADD CONSTRAINT "manufacturing_configs_boardRevisionId_fkey" FOREIGN KEY ("boardRevisionId") REFERENCES "board_revisions"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "manufacturing_sessions" ADD CONSTRAINT "manufacturing_sessions_productId_fkey" FOREIGN KEY ("productId") REFERENCES "products"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "manufacturing_sessions" ADD CONSTRAINT "manufacturing_sessions_fixtureId_fkey" FOREIGN KEY ("fixtureId") REFERENCES "fixtures"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "manufacturing_sessions" ADD CONSTRAINT "manufacturing_sessions_operatorId_fkey" FOREIGN KEY ("operatorId") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "manufacturing_panels" ADD CONSTRAINT "manufacturing_panels_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "manufacturing_sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "manufacturing_units" ADD CONSTRAINT "manufacturing_units_panelId_fkey" FOREIGN KEY ("panelId") REFERENCES "manufacturing_panels"("id") ON DELETE CASCADE ON UPDATE CASCADE;
