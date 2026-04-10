-- Unified Test Execution Model
--
-- Replaces the old dual-model approach (Session + ManufacturingSession) with:
--   TestRun → RunTarget → TestExecution → TestStep
--
-- Manufacturing sessions become thin wrappers around TestRun[].
-- No production data exists — all old tables are dropped.

-- ─── Drop old tables (order matters: children before parents) ───

DROP TABLE IF EXISTS "test_steps" CASCADE;
DROP TABLE IF EXISTS "test_executions" CASCADE;
DROP TABLE IF EXISTS "devices" CASCADE;
DROP TABLE IF EXISTS "sessions" CASCADE;
DROP TABLE IF EXISTS "tests" CASCADE;
DROP TABLE IF EXISTS "manufacturing_units" CASCADE;
DROP TABLE IF EXISTS "manufacturing_panels" CASCADE;

-- Drop V2 tables (if they were created by the previous migration)
DROP TABLE IF EXISTS "test_steps_v2" CASCADE;
DROP TABLE IF EXISTS "test_executions_v2" CASCADE;
DROP TABLE IF EXISTS "session_targets" CASCADE;
DROP TABLE IF EXISTS "session_batches" CASCADE;
DROP TABLE IF EXISTS "sessions_v2" CASCADE;

-- ─── Drop old enums ───

DROP TYPE IF EXISTS "SessionType" CASCADE;
DROP TYPE IF EXISTS "SessionStatus" CASCADE;
DROP TYPE IF EXISTS "DeviceStatus" CASCADE;
DROP TYPE IF EXISTS "TestExecutionStatus" CASCADE;
DROP TYPE IF EXISTS "PanelStatus" CASCADE;
DROP TYPE IF EXISTS "UnitStatus" CASCADE;
DROP TYPE IF EXISTS "SessionStatusV2" CASCADE;
DROP TYPE IF EXISTS "BatchStatus" CASCADE;

-- ─── Create new enums ───

CREATE TYPE "TestRunType" AS ENUM ('VALIDATION', 'MANUFACTURING');
CREATE TYPE "TestRunStatus" AS ENUM ('PENDING', 'ACTIVE', 'COMPLETED', 'FAILED', 'CANCELLED');
CREATE TYPE "TargetStatus" AS ENUM ('PENDING', 'RUNNING', 'PASSED', 'FAILED', 'ERROR');
CREATE TYPE "ExecutionStatus" AS ENUM ('PENDING', 'RUNNING', 'PASSED', 'FAILED', 'SKIPPED', 'ERROR');

-- ─── Redefine ManufacturingSession (drop old columns, add new) ───

ALTER TABLE "manufacturing_sessions" DROP COLUMN IF EXISTS "testPackageId";
ALTER TABLE "manufacturing_sessions" DROP COLUMN IF EXISTS "panelCount";
ALTER TABLE "manufacturing_sessions" DROP COLUMN IF EXISTS "passedCount";
ALTER TABLE "manufacturing_sessions" DROP COLUMN IF EXISTS "failedCount";
ALTER TABLE "manufacturing_sessions" ADD COLUMN IF NOT EXISTS "notes" TEXT;

DROP INDEX IF EXISTS "manufacturing_sessions_testPackageId_idx";

-- ─── Add schemaVersion to test_packages ───

ALTER TABLE "test_packages" ADD COLUMN IF NOT EXISTS "schemaVersion" TEXT;

-- ─── Rename sessionId to testRunId on validation_queue_entries ───

ALTER TABLE "validation_queue_entries" RENAME COLUMN "sessionId" TO "testRunId";

-- ─── Create TestRun ───

CREATE TABLE "test_runs" (
    "id" TEXT NOT NULL,
    "type" "TestRunType" NOT NULL,
    "name" TEXT,
    "productId" TEXT NOT NULL,
    "fixtureId" TEXT NOT NULL,
    "testPackageId" TEXT,
    "buildRunId" TEXT,
    "manufacturingSessionId" TEXT,
    "panelIdentifier" TEXT,
    "assetSetId" TEXT,
    "status" "TestRunStatus" NOT NULL DEFAULT 'PENDING',
    "operatorId" TEXT NOT NULL,
    "targetCount" INTEGER NOT NULL DEFAULT 0,
    "completedCount" INTEGER NOT NULL DEFAULT 0,
    "passedCount" INTEGER NOT NULL DEFAULT 0,
    "failedCount" INTEGER NOT NULL DEFAULT 0,
    "config" JSONB,
    "notes" TEXT,
    "errorMessage" TEXT,
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    "durationMs" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "test_runs_pkey" PRIMARY KEY ("id")
);

-- ─── Create RunTarget ───

CREATE TABLE "run_targets" (
    "id" TEXT NOT NULL,
    "runId" TEXT NOT NULL,
    "slotIndex" INTEGER NOT NULL,
    "slotId" TEXT,
    "serialNumber" TEXT,
    "deviceId" TEXT,
    "status" "TargetStatus" NOT NULL DEFAULT 'PENDING',
    "metadata" JSONB,
    "errorMessage" TEXT,
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    "durationMs" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "run_targets_pkey" PRIMARY KEY ("id")
);

-- ─── Create TestExecution (new) ───

CREATE TABLE "test_executions" (
    "id" TEXT NOT NULL,
    "targetId" TEXT NOT NULL,
    "executionIndex" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "module" TEXT,
    "status" "ExecutionStatus" NOT NULL DEFAULT 'PENDING',
    "durationMs" INTEGER,
    "errorMessage" TEXT,
    "measurements" JSONB,
    "logOutput" TEXT,
    "logStorageKey" TEXT,
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "test_executions_pkey" PRIMARY KEY ("id")
);

-- ─── Create TestStep (new) ───

CREATE TABLE "test_steps" (
    "id" TEXT NOT NULL,
    "executionId" TEXT NOT NULL,
    "stepIndex" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "status" "ExecutionStatus" NOT NULL DEFAULT 'PENDING',
    "passed" BOOLEAN,
    "durationMs" INTEGER,
    "errorMessage" TEXT,
    "measurements" JSONB,
    "logOutput" TEXT,
    "logStorageKey" TEXT,
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "test_steps_pkey" PRIMARY KEY ("id")
);

-- ─── Create TestPackageStage ───

CREATE TABLE "test_package_stages" (
    "id" TEXT NOT NULL,
    "testPackageId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "stageIndex" INTEGER NOT NULL,
    "directory" TEXT,
    "module" TEXT,
    "timeoutS" INTEGER,
    "hardware" TEXT[],
    "markers" TEXT[],
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "test_package_stages_pkey" PRIMARY KEY ("id")
);

-- ─── Unique Constraints ───

CREATE UNIQUE INDEX "run_targets_runId_slotIndex_key" ON "run_targets"("runId", "slotIndex");
CREATE UNIQUE INDEX "test_executions_targetId_executionIndex_key" ON "test_executions"("targetId", "executionIndex");
CREATE UNIQUE INDEX "test_steps_executionId_stepIndex_key" ON "test_steps"("executionId", "stepIndex");
CREATE UNIQUE INDEX "test_package_stages_testPackageId_name_key" ON "test_package_stages"("testPackageId", "name");

-- ─── Indexes ───

CREATE INDEX "test_runs_productId_type_status_idx" ON "test_runs"("productId", "type", "status");
CREATE INDEX "test_runs_fixtureId_idx" ON "test_runs"("fixtureId");
CREATE INDEX "test_runs_testPackageId_idx" ON "test_runs"("testPackageId");
CREATE INDEX "test_runs_buildRunId_idx" ON "test_runs"("buildRunId");
CREATE INDEX "test_runs_manufacturingSessionId_idx" ON "test_runs"("manufacturingSessionId");
CREATE INDEX "test_runs_operatorId_idx" ON "test_runs"("operatorId");
CREATE INDEX "test_runs_assetSetId_idx" ON "test_runs"("assetSetId");
CREATE INDEX "run_targets_runId_idx" ON "run_targets"("runId");
CREATE INDEX "test_executions_targetId_idx" ON "test_executions"("targetId");
CREATE INDEX "test_steps_executionId_idx" ON "test_steps"("executionId");
CREATE INDEX "test_package_stages_testPackageId_idx" ON "test_package_stages"("testPackageId");

-- ─── Foreign Keys ───

-- TestRun
ALTER TABLE "test_runs" ADD CONSTRAINT "test_runs_productId_fkey"
  FOREIGN KEY ("productId") REFERENCES "products"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "test_runs" ADD CONSTRAINT "test_runs_fixtureId_fkey"
  FOREIGN KEY ("fixtureId") REFERENCES "fixtures"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "test_runs" ADD CONSTRAINT "test_runs_testPackageId_fkey"
  FOREIGN KEY ("testPackageId") REFERENCES "test_packages"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "test_runs" ADD CONSTRAINT "test_runs_buildRunId_fkey"
  FOREIGN KEY ("buildRunId") REFERENCES "pipeline_runs"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "test_runs" ADD CONSTRAINT "test_runs_manufacturingSessionId_fkey"
  FOREIGN KEY ("manufacturingSessionId") REFERENCES "manufacturing_sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "test_runs" ADD CONSTRAINT "test_runs_assetSetId_fkey"
  FOREIGN KEY ("assetSetId") REFERENCES "asset_sets"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "test_runs" ADD CONSTRAINT "test_runs_operatorId_fkey"
  FOREIGN KEY ("operatorId") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- ValidationQueueEntry → TestRun (renamed from sessionId)
ALTER TABLE "validation_queue_entries" DROP CONSTRAINT IF EXISTS "validation_queue_entries_sessionId_fkey";
ALTER TABLE "validation_queue_entries" ADD CONSTRAINT "validation_queue_entries_testRunId_fkey"
  FOREIGN KEY ("testRunId") REFERENCES "test_runs"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- RunTarget
ALTER TABLE "run_targets" ADD CONSTRAINT "run_targets_runId_fkey"
  FOREIGN KEY ("runId") REFERENCES "test_runs"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "run_targets" ADD CONSTRAINT "run_targets_slotId_fkey"
  FOREIGN KEY ("slotId") REFERENCES "fixture_slots"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- TestExecution
ALTER TABLE "test_executions" ADD CONSTRAINT "test_executions_targetId_fkey"
  FOREIGN KEY ("targetId") REFERENCES "run_targets"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- TestStep
ALTER TABLE "test_steps" ADD CONSTRAINT "test_steps_executionId_fkey"
  FOREIGN KEY ("executionId") REFERENCES "test_executions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- TestPackageStage
ALTER TABLE "test_package_stages" ADD CONSTRAINT "test_package_stages_testPackageId_fkey"
  FOREIGN KEY ("testPackageId") REFERENCES "test_packages"("id") ON DELETE CASCADE ON UPDATE CASCADE;
