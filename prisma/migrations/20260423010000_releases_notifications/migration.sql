-- CreateEnum
CREATE TYPE "ReleaseStatus" AS ENUM ('DRAFT', 'STAGED', 'RELEASED', 'ROLLED_BACK');

-- CreateEnum
CREATE TYPE "NotificationType" AS ENUM ('RELEASE_PUBLISHED', 'BUG_ACKNOWLEDGED', 'BUG_RESOLVED', 'BUG_DISMISSED', 'SYSTEM_ANNOUNCEMENT');

-- CreateTable
CREATE TABLE "releases" (
    "id" TEXT NOT NULL,
    "version" TEXT NOT NULL,
    "status" "ReleaseStatus" NOT NULL DEFAULT 'DRAFT',
    "commitSha" TEXT NOT NULL,
    "branch" TEXT NOT NULL DEFAULT 'main',
    "previousVersion" TEXT,
    "corekinectVersion" TEXT,
    "corectlMinVersion" TEXT,
    "protoVersion" TEXT,
    "migrationHash" TEXT,
    "changelog" TEXT,
    "summary" TEXT,
    "breakingChanges" TEXT,
    "testsPassed" INTEGER,
    "testsFailed" INTEGER,
    "testCoverage" DOUBLE PRECISION,
    "gateStatus" TEXT,
    "gateOverrideBy" TEXT,
    "gateOverrideReason" TEXT,
    "stagedAt" TIMESTAMP(3),
    "releasedAt" TIMESTAMP(3),
    "rolledBackAt" TIMESTAMP(3),
    "createdById" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "releases_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "notifications" (
    "id" TEXT NOT NULL,
    "type" "NotificationType" NOT NULL,
    "title" TEXT NOT NULL,
    "message" TEXT NOT NULL,
    "userId" TEXT,
    "releaseId" TEXT,
    "errorReportId" TEXT,
    "readAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "notifications_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "releases_version_key" ON "releases"("version");

-- CreateIndex
CREATE INDEX "releases_status_idx" ON "releases"("status");

-- CreateIndex
CREATE INDEX "releases_createdAt_idx" ON "releases"("createdAt");

-- CreateIndex
CREATE INDEX "releases_version_idx" ON "releases"("version");

-- CreateIndex
CREATE INDEX "notifications_userId_readAt_idx" ON "notifications"("userId", "readAt");

-- CreateIndex
CREATE INDEX "notifications_createdAt_idx" ON "notifications"("createdAt");

-- CreateIndex
CREATE INDEX "notifications_type_idx" ON "notifications"("type");

-- AlterTable
ALTER TABLE "error_reports" ADD COLUMN "resolvedInReleaseId" TEXT;

-- CreateIndex
CREATE INDEX "error_reports_resolvedInReleaseId_idx" ON "error_reports"("resolvedInReleaseId");

-- AddForeignKey
ALTER TABLE "error_reports" ADD CONSTRAINT "error_reports_resolvedInReleaseId_fkey" FOREIGN KEY ("resolvedInReleaseId") REFERENCES "releases"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "releases" ADD CONSTRAINT "releases_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "notifications" ADD CONSTRAINT "notifications_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "notifications" ADD CONSTRAINT "notifications_releaseId_fkey" FOREIGN KEY ("releaseId") REFERENCES "releases"("id") ON DELETE SET NULL ON UPDATE CASCADE;
