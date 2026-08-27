-- CreateEnum
CREATE TYPE "ErrorReportStatus" AS ENUM ('OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'DISMISSED');

-- CreateTable
CREATE TABLE "error_reports" (
    "id" TEXT NOT NULL,
    "status" "ErrorReportStatus" NOT NULL DEFAULT 'OPEN',
    "type" TEXT NOT NULL,
    "severity" TEXT NOT NULL,
    "message" TEXT NOT NULL,
    "context" JSONB,
    "currentPath" TEXT,
    "userEmail" TEXT,
    "userId" TEXT,
    "appVersion" TEXT,
    "resolvedById" TEXT,
    "resolvedAt" TIMESTAMP(3),
    "adminNotes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "error_reports_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "error_reports_createdAt_idx" ON "error_reports"("createdAt");
CREATE INDEX "error_reports_status_idx" ON "error_reports"("status");
CREATE INDEX "error_reports_type_idx" ON "error_reports"("type");
CREATE INDEX "error_reports_severity_idx" ON "error_reports"("severity");
CREATE INDEX "error_reports_userId_idx" ON "error_reports"("userId");

-- AddForeignKey
ALTER TABLE "error_reports" ADD CONSTRAINT "error_reports_resolvedById_fkey" FOREIGN KEY ("resolvedById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
