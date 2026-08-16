-- AlterTable: Add lastHeartbeat for stale build detection
ALTER TABLE "build_jobs" ADD COLUMN "lastHeartbeat" TIMESTAMP(3);
