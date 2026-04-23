-- CreateEnum
CREATE TYPE "NodeStatus" AS ENUM ('ONLINE', 'OFFLINE', 'MAINTENANCE', 'ERROR');

-- CreateEnum
CREATE TYPE "NodeType" AS ENUM ('MANUFACTURING', 'VALIDATION');

-- CreateEnum
CREATE TYPE "SessionType" AS ENUM ('MANUFACTURING', 'VALIDATION');

-- CreateEnum
CREATE TYPE "SessionStatus" AS ENUM ('PENDING', 'ACTIVE', 'PASSED', 'FAILED', 'CANCELLED');

-- CreateEnum
CREATE TYPE "DeviceStatus" AS ENUM ('PENDING', 'IN_PROGRESS', 'PASSED', 'FAILED');

-- CreateEnum
CREATE TYPE "TestExecutionStatus" AS ENUM ('QUEUED', 'RUNNING', 'PASSED', 'FAILED', 'SKIPPED', 'CANCELLED', 'ERROR');

-- CreateEnum
CREATE TYPE "LifecycleStatus" AS ENUM ('DRAFT', 'ACTIVE', 'DEPRECATED', 'EOL');

-- CreateEnum
CREATE TYPE "FixtureStatus" AS ENUM ('AVAILABLE', 'LOCKED', 'OFFLINE', 'MAINTENANCE');

-- CreateEnum
CREATE TYPE "IcleDeviceStatus" AS ENUM ('ONLINE', 'OFFLINE', 'LOGGING', 'CONFIG', 'BOOT', 'OTA');

-- CreateEnum
CREATE TYPE "BuildJobStatus" AS ENUM ('QUEUED', 'BLOCKED', 'CLONING', 'BUILDING', 'SUCCESS', 'FAILED', 'CANCELLED', 'CACHED');

-- CreateEnum
CREATE TYPE "AssetSetSource" AS ENUM ('BUILD_SERVICE', 'MANUAL_UPLOAD', 'EXTERNAL_CI');

-- CreateEnum
CREATE TYPE "AssetSetStatus" AS ENUM ('PENDING', 'COMPLETE', 'VALIDATED', 'FAILED');

-- CreateEnum
CREATE TYPE "QueueEntryStatus" AS ENUM ('QUEUED', 'ASSIGNED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED');

-- CreateEnum
CREATE TYPE "TestPackageStatus" AS ENUM ('DEVELOPMENT', 'RELEASED');

-- CreateEnum
CREATE TYPE "BuildRunStatus" AS ENUM ('PENDING', 'BUILDING', 'BUILD_FAILED', 'VALIDATING', 'SUCCESS', 'FAILED', 'CANCELLED');

-- CreateEnum
CREATE TYPE "Role" AS ENUM ('ADMIN', 'MAINTAINER', 'DEVELOPER', 'OPERATOR');

-- CreateEnum
CREATE TYPE "FirmwareVariant" AS ENUM ('smoke', 'debug', 'release', 'mfg');

-- CreateEnum
CREATE TYPE "ReleaseTrack" AS ENUM ('bench', 'engineering', 'production');

-- CreateEnum
CREATE TYPE "FirmwareSetStatus" AS ENUM ('active', 'deprecated', 'recalled');

-- CreateEnum
CREATE TYPE "RecipeStatus" AS ENUM ('draft', 'published');

-- CreateEnum
CREATE TYPE "AccessLevel" AS ENUM ('view', 'operate', 'develop', 'admin');

-- CreateTable
CREATE TABLE "products" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "slug" TEXT,
    "description" TEXT,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "fwRepoSlug" TEXT,
    "mfgFwRepoSlug" TEXT,
    "builderImage" TEXT,
    "buildConfig" JSONB,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "products_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "test_packages" (
    "id" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "version" TEXT NOT NULL,
    "status" "TestPackageStatus" NOT NULL DEFAULT 'DEVELOPMENT',
    "storageKey" TEXT NOT NULL,
    "frameworkVersion" TEXT NOT NULL,
    "manifestHash" TEXT,
    "testCount" INTEGER NOT NULL DEFAULT 0,
    "stagesEnabled" JSONB,
    "notes" TEXT,
    "createdById" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "test_packages_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "product_targets" (
    "id" TEXT NOT NULL,
    "boardRevisionId" TEXT NOT NULL,
    "role" TEXT NOT NULL,
    "soc" TEXT NOT NULL,
    "appId" INTEGER NOT NULL,

    CONSTRAINT "product_targets_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "boards" (
    "id" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "ckBoardsFamily" TEXT NOT NULL,
    "vendor" TEXT NOT NULL DEFAULT 'corekinect',
    "description" TEXT,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "boards_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "board_revisions" (
    "id" TEXT NOT NULL,
    "boardId" TEXT NOT NULL,
    "version" TEXT NOT NULL,
    "ckBoardsName" TEXT NOT NULL,
    "socs" TEXT[],
    "deviceType" INTEGER,
    "deviceVariant" INTEGER,
    "modemVersion" TEXT,
    "modemStorageKey" TEXT,
    "status" "LifecycleStatus" NOT NULL DEFAULT 'ACTIVE',
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "board_revisions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "firmware_sets" (
    "id" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "boardRevisionId" TEXT,
    "version" TEXT NOT NULL,
    "variant" "FirmwareVariant" NOT NULL DEFAULT 'debug',
    "releaseTrack" "ReleaseTrack" NOT NULL DEFAULT 'bench',
    "isManufacturing" BOOLEAN NOT NULL DEFAULT false,
    "isDebug" BOOLEAN NOT NULL DEFAULT false,
    "source" TEXT NOT NULL DEFAULT 'upload',
    "buildJobId" TEXT,
    "externalBuildId" TEXT,
    "buildFingerprint" TEXT,
    "status" "FirmwareSetStatus" NOT NULL DEFAULT 'active',
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "firmware_sets_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "firmware_builds" (
    "id" TEXT NOT NULL,
    "firmwareSetId" TEXT NOT NULL,
    "targetId" TEXT,
    "versionString" TEXT,
    "hexStorageKey" TEXT,
    "hexEncStorageKey" TEXT,
    "cfwStorageKey" TEXT,
    "manifestKey" TEXT,
    "filename" TEXT NOT NULL,
    "sizeBytes" BIGINT NOT NULL,
    "checksum" TEXT NOT NULL,
    "contentType" TEXT,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "firmware_builds_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "product_stage_configs" (
    "id" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "stage" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "enabled" BOOLEAN NOT NULL DEFAULT false,
    "boardRevisionId" TEXT,
    "watchBranch" TEXT,
    "triggerTypes" TEXT[],
    "signingKeyId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "recipeVersionId" TEXT,

    CONSTRAINT "product_stage_configs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "validation_queue_entries" (
    "id" TEXT NOT NULL,
    "buildRunId" TEXT NOT NULL,
    "stageConfigId" TEXT,
    "stage" INTEGER NOT NULL,
    "priority" INTEGER NOT NULL DEFAULT 50,
    "status" "QueueEntryStatus" NOT NULL DEFAULT 'QUEUED',
    "fixtureId" TEXT,
    "sessionId" TEXT,
    "reason" TEXT,
    "errorMessage" TEXT,
    "jobName" TEXT,
    "requestedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "assignedAt" TIMESTAMP(3),
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "validation_queue_entries_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "pipeline_runs" (
    "id" TEXT NOT NULL,
    "name" TEXT,
    "productId" TEXT NOT NULL,
    "board" TEXT NOT NULL,
    "branch" TEXT NOT NULL,
    "commitSha" TEXT,
    "status" "BuildRunStatus" NOT NULL DEFAULT 'PENDING',
    "triggerType" TEXT NOT NULL DEFAULT 'manual',
    "triggerData" JSONB,
    "stage" INTEGER,
    "stageConfigId" TEXT,
    "expectedBuilds" INTEGER NOT NULL DEFAULT 2,
    "completedBuilds" INTEGER NOT NULL DEFAULT 0,
    "buildMatrix" JSONB,
    "matrixMode" TEXT,
    "prNumber" INTEGER,
    "prTitle" TEXT,
    "prAuthor" TEXT,
    "sourceBranch" TEXT,
    "targetBranch" TEXT,
    "prUrl" TEXT,
    "autoValidate" BOOLEAN NOT NULL DEFAULT false,
    "validationRunId" TEXT,
    "startedAt" TIMESTAMP(3),
    "finishedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "recipeVersionId" TEXT,

    CONSTRAINT "pipeline_runs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "build_jobs" (
    "id" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "board" TEXT NOT NULL,
    "target" TEXT NOT NULL,
    "variant" TEXT NOT NULL DEFAULT 'release',
    "mtibRev" TEXT NOT NULL DEFAULT '1.2',
    "branch" TEXT NOT NULL,
    "commitSha" TEXT,
    "status" "BuildJobStatus" NOT NULL DEFAULT 'QUEUED',
    "versionMajor" INTEGER,
    "versionMinor" INTEGER,
    "buildNum" SERIAL NOT NULL,
    "versionString" TEXT,
    "errorMessage" TEXT,
    "buildLog" TEXT,
    "webhookData" JSONB,
    "matrixLabel" TEXT,
    "matrixIndex" INTEGER,
    "versionBump" BOOLEAN NOT NULL DEFAULT false,
    "baseJobId" TEXT,
    "buildFingerprint" TEXT,
    "configFlags" JSONB,
    "reusedFromId" TEXT,
    "buildRunId" TEXT,
    "workerId" TEXT,
    "startedAt" TIMESTAMP(3),
    "finishedAt" TIMESTAMP(3),
    "durationSeconds" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "recipeVersionId" TEXT,

    CONSTRAINT "build_jobs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "build_job_artifacts" (
    "id" TEXT NOT NULL,
    "buildJobId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "storageKey" TEXT NOT NULL,
    "sizeBytes" BIGINT NOT NULL,
    "checksum" TEXT NOT NULL,
    "role" TEXT,
    "processor" TEXT,
    "artifactType" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "build_job_artifacts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sessions" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "type" "SessionType" NOT NULL,
    "productId" TEXT NOT NULL,
    "status" "SessionStatus" NOT NULL DEFAULT 'PENDING',
    "fixtureId" TEXT,
    "buildRunId" TEXT,
    "testPackageId" TEXT,
    "targetCount" INTEGER,
    "completedCount" INTEGER NOT NULL DEFAULT 0,
    "passedCount" INTEGER NOT NULL DEFAULT 0,
    "failedCount" INTEGER NOT NULL DEFAULT 0,
    "config" JSONB,
    "notes" TEXT,
    "errorMessage" TEXT,
    "createdById" TEXT,
    "startedAt" TIMESTAMP(3),
    "finishedAt" TIMESTAMP(3),
    "durationMs" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "assetSetId" TEXT,

    CONSTRAINT "sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "devices" (
    "id" TEXT NOT NULL,
    "serialNumber" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "status" "DeviceStatus" NOT NULL DEFAULT 'PENDING',
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "devices_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "fixture_designs" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "boardRevisionId" TEXT NOT NULL,
    "revision" TEXT NOT NULL,
    "capabilities" TEXT[],
    "profileTemplate" JSONB NOT NULL,
    "schematicUrl" TEXT,
    "bomUrl" TEXT,
    "assemblyGuide" TEXT,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "fixture_designs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "fixtures" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "stationId" TEXT,
    "productId" TEXT NOT NULL,
    "boardRevisionId" TEXT,
    "type" "NodeType" NOT NULL,
    "designId" TEXT,
    "status" "FixtureStatus" NOT NULL DEFAULT 'AVAILABLE',
    "lockedBy" TEXT,
    "lockedAt" TIMESTAMP(3),
    "profileOverrides" JSONB,
    "description" TEXT,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "metadata" JSONB,
    "lastHealthCheck" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "fixtures_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "fixture_slots" (
    "id" TEXT NOT NULL,
    "fixtureId" TEXT NOT NULL,
    "slotIndex" INTEGER NOT NULL,
    "label" TEXT,
    "nodeId" TEXT,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "jlinkAppSerial" TEXT,
    "jlinkCommsSerial" TEXT,
    "uartAppPath" TEXT,
    "uartCommsPath" TEXT,
    "dutDeviceId" TEXT,
    "dutSnr" TEXT,
    "dutImei" TEXT,
    "dutIccids" TEXT[],
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "fixture_slots_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "nodes" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "hostname" TEXT NOT NULL,
    "type" "NodeType" NOT NULL,
    "status" "NodeStatus" NOT NULL DEFAULT 'OFFLINE',
    "ipAddress" TEXT,
    "hardwareRevision" TEXT,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "nodes_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "icle_devices" (
    "id" TEXT NOT NULL,
    "deviceId" TEXT NOT NULL,
    "name" TEXT,
    "ipAddress" TEXT,
    "macAddress" TEXT,
    "firmwareVersion" TEXT,
    "status" "IcleDeviceStatus" NOT NULL DEFAULT 'OFFLINE',
    "registered" BOOLEAN NOT NULL DEFAULT false,
    "lastHeartbeat" TIMESTAMP(3),
    "lastStatusData" JSONB,
    "pendingConfig" JSONB,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "icle_devices_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "icle_pending_commands" (
    "id" TEXT NOT NULL,
    "deviceId" TEXT NOT NULL,
    "commandType" TEXT NOT NULL,
    "payload" JSONB NOT NULL,
    "priority" INTEGER NOT NULL DEFAULT 0,
    "expiresAt" TIMESTAMP(3),
    "acknowledged" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "icle_pending_commands_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "icle_logs" (
    "id" TEXT NOT NULL,
    "deviceId" TEXT NOT NULL,
    "filename" TEXT NOT NULL,
    "storageKey" TEXT NOT NULL,
    "sizeBytes" BIGINT NOT NULL,
    "format" TEXT NOT NULL,
    "uploadedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "icle_logs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "tests" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "description" TEXT,
    "category" TEXT,
    "sortOrder" INTEGER NOT NULL DEFAULT 0,
    "config" JSONB,
    "enabled" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "tests_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "test_executions" (
    "id" TEXT NOT NULL,
    "testId" TEXT NOT NULL,
    "nodeId" TEXT NOT NULL,
    "deviceId" TEXT,
    "slotId" TEXT,
    "status" "TestExecutionStatus" NOT NULL DEFAULT 'QUEUED',
    "config" JSONB,
    "triggeredById" TEXT,
    "startedAt" TIMESTAMP(3),
    "finishedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "test_executions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "test_steps" (
    "id" TEXT NOT NULL,
    "executionId" TEXT NOT NULL,
    "stepIndex" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "status" "TestExecutionStatus" NOT NULL DEFAULT 'QUEUED',
    "passed" BOOLEAN,
    "errorMessage" TEXT,
    "measurements" JSONB,
    "logOutput" TEXT,
    "logStorageKey" TEXT,
    "startedAt" TIMESTAMP(3),
    "finishedAt" TIMESTAMP(3),
    "durationMs" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "test_steps_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "users" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "externalId" TEXT,
    "role" "Role" NOT NULL DEFAULT 'DEVELOPER',
    "permissionSetId" TEXT,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "lastSeenAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "product_access" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "level" "AccessLevel" NOT NULL DEFAULT 'view',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "product_access_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "permission_sets" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "permissions" TEXT[],
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "permission_sets_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "api_keys" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "keyHash" TEXT NOT NULL,
    "keyPrefix" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "expiresAt" TIMESTAMP(3),
    "lastUsedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "api_keys_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "audit_logs" (
    "id" TEXT NOT NULL,
    "userId" TEXT,
    "action" TEXT NOT NULL,
    "entityType" TEXT NOT NULL,
    "entityId" TEXT,
    "details" JSONB,
    "ipAddress" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "audit_logs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "secrets" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "value" TEXT NOT NULL,
    "description" TEXT,
    "createdById" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "secrets_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "poll_cache" (
    "id" TEXT NOT NULL,
    "repoSlug" TEXT NOT NULL,
    "prId" INTEGER NOT NULL,
    "commitSha" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "poll_cache_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "recipe_versions" (
    "id" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "version" INTEGER NOT NULL,
    "content" TEXT NOT NULL,
    "status" "RecipeStatus" NOT NULL DEFAULT 'draft',
    "changeNote" TEXT,
    "createdById" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "recipe_versions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "recipe_templates" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "content" TEXT NOT NULL,
    "category" TEXT NOT NULL DEFAULT 'general',
    "sortOrder" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "recipe_templates_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "stage_build_matrix" (
    "id" TEXT NOT NULL,
    "stageConfigId" TEXT NOT NULL,
    "sortOrder" INTEGER NOT NULL DEFAULT 0,
    "label" TEXT NOT NULL,
    "fwType" TEXT NOT NULL,
    "variant" TEXT NOT NULL,
    "configLog" BOOLEAN NOT NULL DEFAULT true,
    "producesHex" BOOLEAN NOT NULL DEFAULT true,
    "producesCfw" BOOLEAN NOT NULL DEFAULT false,
    "gitRef" TEXT NOT NULL DEFAULT 'pr',
    "isVersionBump" BOOLEAN NOT NULL DEFAULT false,
    "baseLabel" TEXT,
    "description" TEXT,

    CONSTRAINT "stage_build_matrix_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "asset_sets" (
    "id" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "boardRevisionId" TEXT,
    "version" TEXT NOT NULL,
    "variant" TEXT NOT NULL DEFAULT 'debug',
    "stage" INTEGER,
    "source" "AssetSetSource" NOT NULL,
    "buildRunId" TEXT,
    "externalBuildId" TEXT,
    "commitSha" TEXT,
    "branch" TEXT,
    "recipeVersionId" TEXT,
    "status" "AssetSetStatus" NOT NULL DEFAULT 'PENDING',
    "notes" TEXT,
    "createdById" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "asset_sets_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "assets" (
    "id" TEXT NOT NULL,
    "assetSetId" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "role" TEXT NOT NULL,
    "processor" TEXT,
    "artifactType" TEXT NOT NULL,
    "storageKey" TEXT NOT NULL,
    "filename" TEXT NOT NULL,
    "sizeBytes" BIGINT NOT NULL,
    "checksum" TEXT NOT NULL,
    "contentType" TEXT,
    "appId" INTEGER,
    "versionString" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "assets_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "products_name_key" ON "products"("name");

-- CreateIndex
CREATE UNIQUE INDEX "products_slug_key" ON "products"("slug");

-- CreateIndex
CREATE INDEX "test_packages_productId_status_idx" ON "test_packages"("productId", "status");

-- CreateIndex
CREATE INDEX "test_packages_createdById_idx" ON "test_packages"("createdById");

-- CreateIndex
CREATE UNIQUE INDEX "test_packages_productId_version_key" ON "test_packages"("productId", "version");

-- CreateIndex
CREATE INDEX "product_targets_appId_idx" ON "product_targets"("appId");

-- CreateIndex
CREATE UNIQUE INDEX "product_targets_boardRevisionId_role_key" ON "product_targets"("boardRevisionId", "role");

-- CreateIndex
CREATE UNIQUE INDEX "product_targets_boardRevisionId_appId_key" ON "product_targets"("boardRevisionId", "appId");

-- CreateIndex
CREATE UNIQUE INDEX "boards_productId_key" ON "boards"("productId");

-- CreateIndex
CREATE UNIQUE INDEX "boards_ckBoardsFamily_key" ON "boards"("ckBoardsFamily");

-- CreateIndex
CREATE UNIQUE INDEX "board_revisions_boardId_version_key" ON "board_revisions"("boardId", "version");

-- CreateIndex
CREATE UNIQUE INDEX "board_revisions_ckBoardsName_key" ON "board_revisions"("ckBoardsName");

-- CreateIndex
CREATE INDEX "firmware_sets_productId_idx" ON "firmware_sets"("productId");

-- CreateIndex
CREATE INDEX "firmware_sets_boardRevisionId_idx" ON "firmware_sets"("boardRevisionId");

-- CreateIndex
CREATE INDEX "firmware_sets_productId_version_idx" ON "firmware_sets"("productId", "version");

-- CreateIndex
CREATE INDEX "firmware_builds_firmwareSetId_idx" ON "firmware_builds"("firmwareSetId");

-- CreateIndex
CREATE INDEX "product_stage_configs_productId_idx" ON "product_stage_configs"("productId");

-- CreateIndex
CREATE UNIQUE INDEX "product_stage_configs_productId_stage_boardRevisionId_key" ON "product_stage_configs"("productId", "stage", "boardRevisionId");

-- CreateIndex
CREATE UNIQUE INDEX "validation_queue_entries_sessionId_key" ON "validation_queue_entries"("sessionId");

-- CreateIndex
CREATE INDEX "validation_queue_entries_status_priority_idx" ON "validation_queue_entries"("status", "priority");

-- CreateIndex
CREATE INDEX "validation_queue_entries_buildRunId_idx" ON "validation_queue_entries"("buildRunId");

-- CreateIndex
CREATE INDEX "validation_queue_entries_fixtureId_idx" ON "validation_queue_entries"("fixtureId");

-- CreateIndex
CREATE INDEX "pipeline_runs_productId_branch_idx" ON "pipeline_runs"("productId", "branch");

-- CreateIndex
CREATE INDEX "pipeline_runs_productId_prNumber_idx" ON "pipeline_runs"("productId", "prNumber");

-- CreateIndex
CREATE INDEX "pipeline_runs_productId_stage_status_idx" ON "pipeline_runs"("productId", "stage", "status");

-- CreateIndex
CREATE INDEX "pipeline_runs_productId_prNumber_stage_idx" ON "pipeline_runs"("productId", "prNumber", "stage");

-- CreateIndex
CREATE INDEX "pipeline_runs_status_idx" ON "pipeline_runs"("status");

-- CreateIndex
CREATE INDEX "pipeline_runs_commitSha_idx" ON "pipeline_runs"("commitSha");

-- CreateIndex
CREATE INDEX "pipeline_runs_stage_idx" ON "pipeline_runs"("stage");

-- CreateIndex
CREATE INDEX "build_jobs_productId_branch_idx" ON "build_jobs"("productId", "branch");

-- CreateIndex
CREATE INDEX "build_jobs_matrixLabel_idx" ON "build_jobs"("matrixLabel");

-- CreateIndex
CREATE INDEX "build_jobs_productId_idx" ON "build_jobs"("productId");

-- CreateIndex
CREATE INDEX "build_jobs_status_idx" ON "build_jobs"("status");

-- CreateIndex
CREATE INDEX "build_jobs_buildRunId_idx" ON "build_jobs"("buildRunId");

-- CreateIndex
CREATE INDEX "build_jobs_buildFingerprint_idx" ON "build_jobs"("buildFingerprint");

-- CreateIndex
CREATE INDEX "build_job_artifacts_buildJobId_idx" ON "build_job_artifacts"("buildJobId");

-- CreateIndex
CREATE INDEX "sessions_productId_idx" ON "sessions"("productId");

-- CreateIndex
CREATE INDEX "sessions_type_status_idx" ON "sessions"("type", "status");

-- CreateIndex
CREATE INDEX "sessions_buildRunId_idx" ON "sessions"("buildRunId");

-- CreateIndex
CREATE INDEX "sessions_testPackageId_idx" ON "sessions"("testPackageId");

-- CreateIndex
CREATE INDEX "sessions_fixtureId_idx" ON "sessions"("fixtureId");

-- CreateIndex
CREATE INDEX "sessions_assetSetId_idx" ON "sessions"("assetSetId");

-- CreateIndex
CREATE INDEX "sessions_createdById_idx" ON "sessions"("createdById");

-- CreateIndex
CREATE INDEX "devices_serialNumber_idx" ON "devices"("serialNumber");

-- CreateIndex
CREATE UNIQUE INDEX "devices_serialNumber_sessionId_key" ON "devices"("serialNumber", "sessionId");

-- CreateIndex
CREATE UNIQUE INDEX "fixture_designs_name_key" ON "fixture_designs"("name");

-- CreateIndex
CREATE INDEX "fixture_designs_boardRevisionId_idx" ON "fixture_designs"("boardRevisionId");

-- CreateIndex
CREATE UNIQUE INDEX "fixtures_stationId_key" ON "fixtures"("stationId");

-- CreateIndex
CREATE INDEX "fixtures_productId_status_idx" ON "fixtures"("productId", "status");

-- CreateIndex
CREATE INDEX "fixtures_boardRevisionId_idx" ON "fixtures"("boardRevisionId");

-- CreateIndex
CREATE INDEX "fixtures_status_idx" ON "fixtures"("status");

-- CreateIndex
CREATE UNIQUE INDEX "fixture_slots_nodeId_key" ON "fixture_slots"("nodeId");

-- CreateIndex
CREATE UNIQUE INDEX "fixture_slots_fixtureId_slotIndex_key" ON "fixture_slots"("fixtureId", "slotIndex");

-- CreateIndex
CREATE UNIQUE INDEX "nodes_hostname_key" ON "nodes"("hostname");

-- CreateIndex
CREATE UNIQUE INDEX "icle_devices_deviceId_key" ON "icle_devices"("deviceId");

-- CreateIndex
CREATE INDEX "icle_devices_status_idx" ON "icle_devices"("status");

-- CreateIndex
CREATE INDEX "icle_pending_commands_deviceId_acknowledged_idx" ON "icle_pending_commands"("deviceId", "acknowledged");

-- CreateIndex
CREATE UNIQUE INDEX "icle_logs_deviceId_filename_key" ON "icle_logs"("deviceId", "filename");

-- CreateIndex
CREATE UNIQUE INDEX "tests_productId_name_category_key" ON "tests"("productId", "name", "category");

-- CreateIndex
CREATE INDEX "test_executions_status_idx" ON "test_executions"("status");

-- CreateIndex
CREATE INDEX "test_executions_testId_idx" ON "test_executions"("testId");

-- CreateIndex
CREATE INDEX "test_executions_nodeId_idx" ON "test_executions"("nodeId");

-- CreateIndex
CREATE INDEX "test_executions_deviceId_idx" ON "test_executions"("deviceId");

-- CreateIndex
CREATE INDEX "test_steps_executionId_idx" ON "test_steps"("executionId");

-- CreateIndex
CREATE UNIQUE INDEX "users_email_key" ON "users"("email");

-- CreateIndex
CREATE UNIQUE INDEX "users_externalId_key" ON "users"("externalId");

-- CreateIndex
CREATE INDEX "product_access_userId_idx" ON "product_access"("userId");

-- CreateIndex
CREATE INDEX "product_access_productId_idx" ON "product_access"("productId");

-- CreateIndex
CREATE UNIQUE INDEX "product_access_userId_productId_key" ON "product_access"("userId", "productId");

-- CreateIndex
CREATE UNIQUE INDEX "permission_sets_name_key" ON "permission_sets"("name");

-- CreateIndex
CREATE UNIQUE INDEX "api_keys_keyHash_key" ON "api_keys"("keyHash");

-- CreateIndex
CREATE INDEX "audit_logs_createdAt_idx" ON "audit_logs"("createdAt");

-- CreateIndex
CREATE INDEX "audit_logs_entityType_entityId_idx" ON "audit_logs"("entityType", "entityId");

-- CreateIndex
CREATE INDEX "audit_logs_userId_idx" ON "audit_logs"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "secrets_name_key" ON "secrets"("name");

-- CreateIndex
CREATE UNIQUE INDEX "poll_cache_repoSlug_prId_key" ON "poll_cache"("repoSlug", "prId");

-- CreateIndex
CREATE INDEX "recipe_versions_productId_version_idx" ON "recipe_versions"("productId", "version");

-- CreateIndex
CREATE INDEX "recipe_versions_productId_status_idx" ON "recipe_versions"("productId", "status");

-- CreateIndex
CREATE UNIQUE INDEX "recipe_templates_name_key" ON "recipe_templates"("name");

-- CreateIndex
CREATE INDEX "stage_build_matrix_stageConfigId_idx" ON "stage_build_matrix"("stageConfigId");

-- CreateIndex
CREATE UNIQUE INDEX "stage_build_matrix_stageConfigId_label_key" ON "stage_build_matrix"("stageConfigId", "label");

-- CreateIndex
CREATE UNIQUE INDEX "asset_sets_buildRunId_key" ON "asset_sets"("buildRunId");

-- CreateIndex
CREATE INDEX "asset_sets_productId_stage_status_idx" ON "asset_sets"("productId", "stage", "status");

-- CreateIndex
CREATE INDEX "asset_sets_productId_version_idx" ON "asset_sets"("productId", "version");

-- CreateIndex
CREATE INDEX "assets_assetSetId_idx" ON "assets"("assetSetId");

-- CreateIndex
CREATE INDEX "assets_assetSetId_label_artifactType_idx" ON "assets"("assetSetId", "label", "artifactType");

-- CreateIndex
CREATE INDEX "assets_appId_artifactType_idx" ON "assets"("appId", "artifactType");

-- AddForeignKey
ALTER TABLE "test_packages" ADD CONSTRAINT "test_packages_productId_fkey" FOREIGN KEY ("productId") REFERENCES "products"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "test_packages" ADD CONSTRAINT "test_packages_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "product_targets" ADD CONSTRAINT "product_targets_boardRevisionId_fkey" FOREIGN KEY ("boardRevisionId") REFERENCES "board_revisions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "boards" ADD CONSTRAINT "boards_productId_fkey" FOREIGN KEY ("productId") REFERENCES "products"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "board_revisions" ADD CONSTRAINT "board_revisions_boardId_fkey" FOREIGN KEY ("boardId") REFERENCES "boards"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "firmware_sets" ADD CONSTRAINT "firmware_sets_productId_fkey" FOREIGN KEY ("productId") REFERENCES "products"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "firmware_sets" ADD CONSTRAINT "firmware_sets_boardRevisionId_fkey" FOREIGN KEY ("boardRevisionId") REFERENCES "board_revisions"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "firmware_builds" ADD CONSTRAINT "firmware_builds_firmwareSetId_fkey" FOREIGN KEY ("firmwareSetId") REFERENCES "firmware_sets"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "firmware_builds" ADD CONSTRAINT "firmware_builds_targetId_fkey" FOREIGN KEY ("targetId") REFERENCES "product_targets"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "product_stage_configs" ADD CONSTRAINT "product_stage_configs_productId_fkey" FOREIGN KEY ("productId") REFERENCES "products"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "product_stage_configs" ADD CONSTRAINT "product_stage_configs_boardRevisionId_fkey" FOREIGN KEY ("boardRevisionId") REFERENCES "board_revisions"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "product_stage_configs" ADD CONSTRAINT "product_stage_configs_signingKeyId_fkey" FOREIGN KEY ("signingKeyId") REFERENCES "secrets"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "product_stage_configs" ADD CONSTRAINT "product_stage_configs_recipeVersionId_fkey" FOREIGN KEY ("recipeVersionId") REFERENCES "recipe_versions"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "validation_queue_entries" ADD CONSTRAINT "validation_queue_entries_buildRunId_fkey" FOREIGN KEY ("buildRunId") REFERENCES "pipeline_runs"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "validation_queue_entries" ADD CONSTRAINT "validation_queue_entries_stageConfigId_fkey" FOREIGN KEY ("stageConfigId") REFERENCES "product_stage_configs"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "validation_queue_entries" ADD CONSTRAINT "validation_queue_entries_fixtureId_fkey" FOREIGN KEY ("fixtureId") REFERENCES "fixtures"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "validation_queue_entries" ADD CONSTRAINT "validation_queue_entries_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "sessions"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "pipeline_runs" ADD CONSTRAINT "pipeline_runs_productId_fkey" FOREIGN KEY ("productId") REFERENCES "products"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "pipeline_runs" ADD CONSTRAINT "pipeline_runs_stageConfigId_fkey" FOREIGN KEY ("stageConfigId") REFERENCES "product_stage_configs"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "pipeline_runs" ADD CONSTRAINT "pipeline_runs_recipeVersionId_fkey" FOREIGN KEY ("recipeVersionId") REFERENCES "recipe_versions"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "build_jobs" ADD CONSTRAINT "build_jobs_buildRunId_fkey" FOREIGN KEY ("buildRunId") REFERENCES "pipeline_runs"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "build_jobs" ADD CONSTRAINT "build_jobs_productId_fkey" FOREIGN KEY ("productId") REFERENCES "products"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "build_jobs" ADD CONSTRAINT "build_jobs_recipeVersionId_fkey" FOREIGN KEY ("recipeVersionId") REFERENCES "recipe_versions"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "build_jobs" ADD CONSTRAINT "build_jobs_reusedFromId_fkey" FOREIGN KEY ("reusedFromId") REFERENCES "build_jobs"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "build_job_artifacts" ADD CONSTRAINT "build_job_artifacts_buildJobId_fkey" FOREIGN KEY ("buildJobId") REFERENCES "build_jobs"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_productId_fkey" FOREIGN KEY ("productId") REFERENCES "products"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_fixtureId_fkey" FOREIGN KEY ("fixtureId") REFERENCES "fixtures"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_buildRunId_fkey" FOREIGN KEY ("buildRunId") REFERENCES "pipeline_runs"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_testPackageId_fkey" FOREIGN KEY ("testPackageId") REFERENCES "test_packages"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_assetSetId_fkey" FOREIGN KEY ("assetSetId") REFERENCES "asset_sets"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "devices" ADD CONSTRAINT "devices_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "fixture_designs" ADD CONSTRAINT "fixture_designs_boardRevisionId_fkey" FOREIGN KEY ("boardRevisionId") REFERENCES "board_revisions"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "fixtures" ADD CONSTRAINT "fixtures_productId_fkey" FOREIGN KEY ("productId") REFERENCES "products"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "fixtures" ADD CONSTRAINT "fixtures_boardRevisionId_fkey" FOREIGN KEY ("boardRevisionId") REFERENCES "board_revisions"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "fixtures" ADD CONSTRAINT "fixtures_designId_fkey" FOREIGN KEY ("designId") REFERENCES "fixture_designs"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "fixture_slots" ADD CONSTRAINT "fixture_slots_fixtureId_fkey" FOREIGN KEY ("fixtureId") REFERENCES "fixtures"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "fixture_slots" ADD CONSTRAINT "fixture_slots_nodeId_fkey" FOREIGN KEY ("nodeId") REFERENCES "nodes"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "icle_pending_commands" ADD CONSTRAINT "icle_pending_commands_deviceId_fkey" FOREIGN KEY ("deviceId") REFERENCES "icle_devices"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "icle_logs" ADD CONSTRAINT "icle_logs_deviceId_fkey" FOREIGN KEY ("deviceId") REFERENCES "icle_devices"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "tests" ADD CONSTRAINT "tests_productId_fkey" FOREIGN KEY ("productId") REFERENCES "products"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "test_executions" ADD CONSTRAINT "test_executions_testId_fkey" FOREIGN KEY ("testId") REFERENCES "tests"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "test_executions" ADD CONSTRAINT "test_executions_nodeId_fkey" FOREIGN KEY ("nodeId") REFERENCES "nodes"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "test_executions" ADD CONSTRAINT "test_executions_deviceId_fkey" FOREIGN KEY ("deviceId") REFERENCES "devices"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "test_executions" ADD CONSTRAINT "test_executions_slotId_fkey" FOREIGN KEY ("slotId") REFERENCES "fixture_slots"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "test_executions" ADD CONSTRAINT "test_executions_triggeredById_fkey" FOREIGN KEY ("triggeredById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "test_steps" ADD CONSTRAINT "test_steps_executionId_fkey" FOREIGN KEY ("executionId") REFERENCES "test_executions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "users" ADD CONSTRAINT "users_permissionSetId_fkey" FOREIGN KEY ("permissionSetId") REFERENCES "permission_sets"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "product_access" ADD CONSTRAINT "product_access_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "product_access" ADD CONSTRAINT "product_access_productId_fkey" FOREIGN KEY ("productId") REFERENCES "products"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "api_keys" ADD CONSTRAINT "api_keys_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "audit_logs" ADD CONSTRAINT "audit_logs_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "secrets" ADD CONSTRAINT "secrets_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "recipe_versions" ADD CONSTRAINT "recipe_versions_productId_fkey" FOREIGN KEY ("productId") REFERENCES "products"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "recipe_versions" ADD CONSTRAINT "recipe_versions_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "stage_build_matrix" ADD CONSTRAINT "stage_build_matrix_stageConfigId_fkey" FOREIGN KEY ("stageConfigId") REFERENCES "product_stage_configs"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "asset_sets" ADD CONSTRAINT "asset_sets_productId_fkey" FOREIGN KEY ("productId") REFERENCES "products"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "asset_sets" ADD CONSTRAINT "asset_sets_boardRevisionId_fkey" FOREIGN KEY ("boardRevisionId") REFERENCES "board_revisions"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "asset_sets" ADD CONSTRAINT "asset_sets_buildRunId_fkey" FOREIGN KEY ("buildRunId") REFERENCES "pipeline_runs"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "asset_sets" ADD CONSTRAINT "asset_sets_recipeVersionId_fkey" FOREIGN KEY ("recipeVersionId") REFERENCES "recipe_versions"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "asset_sets" ADD CONSTRAINT "asset_sets_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "assets" ADD CONSTRAINT "assets_assetSetId_fkey" FOREIGN KEY ("assetSetId") REFERENCES "asset_sets"("id") ON DELETE CASCADE ON UPDATE CASCADE;

