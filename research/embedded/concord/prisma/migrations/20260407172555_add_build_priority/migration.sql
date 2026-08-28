-- AlterTable: Add priority field to build_jobs for queue ordering
ALTER TABLE "build_jobs" ADD COLUMN "priority" INTEGER NOT NULL DEFAULT 50;

-- CreateIndex: Compound index for efficient queue queries (status + priority)
CREATE INDEX "build_jobs_status_priority_idx" ON "build_jobs"("status", "priority");
