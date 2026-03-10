-- Add Stage 4 build matrix fields to BuildJob
ALTER TABLE "build_jobs" ADD COLUMN IF NOT EXISTS "matrixLabel" TEXT;
ALTER TABLE "build_jobs" ADD COLUMN IF NOT EXISTS "matrixIndex" INTEGER;
ALTER TABLE "build_jobs" ADD COLUMN IF NOT EXISTS "versionBump" BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE "build_jobs" ADD COLUMN IF NOT EXISTS "baseJobId" TEXT;

-- Add build matrix configuration to PipelineRun
ALTER TABLE "pipeline_runs" ADD COLUMN IF NOT EXISTS "buildMatrix" JSONB;
ALTER TABLE "pipeline_runs" ADD COLUMN IF NOT EXISTS "matrixMode" TEXT;

-- Add index for matrixLabel lookups
CREATE INDEX IF NOT EXISTS "build_jobs_matrixLabel_idx" ON "build_jobs"("matrixLabel");
