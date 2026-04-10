-- CreateTable
CREATE TABLE "modem_firmwares" (
    "id" TEXT NOT NULL,
    "boardRevisionId" TEXT NOT NULL,
    "version" TEXT NOT NULL,
    "filename" TEXT NOT NULL,
    "storageKey" TEXT NOT NULL,
    "sizeBytes" INTEGER NOT NULL DEFAULT 0,
    "checksum" TEXT,
    "notes" TEXT,
    "createdById" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "modem_firmwares_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "modem_firmwares_boardRevisionId_idx" ON "modem_firmwares"("boardRevisionId");

-- CreateIndex
CREATE UNIQUE INDEX "modem_firmwares_boardRevisionId_version_key" ON "modem_firmwares"("boardRevisionId", "version");

-- AddColumn
ALTER TABLE "asset_sets" ADD COLUMN "modemFirmwareId" TEXT;

-- AddForeignKey
ALTER TABLE "modem_firmwares" ADD CONSTRAINT "modem_firmwares_boardRevisionId_fkey" FOREIGN KEY ("boardRevisionId") REFERENCES "board_revisions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "modem_firmwares" ADD CONSTRAINT "modem_firmwares_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "asset_sets" ADD CONSTRAINT "asset_sets_modemFirmwareId_fkey" FOREIGN KEY ("modemFirmwareId") REFERENCES "modem_firmwares"("id") ON DELETE SET NULL ON UPDATE CASCADE;
