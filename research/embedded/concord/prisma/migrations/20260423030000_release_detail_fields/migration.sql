-- AlterTable
ALTER TABLE "releases" ADD COLUMN "testDurationMs" INTEGER;
ALTER TABLE "releases" ADD COLUMN "testDetails" JSONB;
ALTER TABLE "releases" ADD COLUMN "linesAdded" INTEGER;
ALTER TABLE "releases" ADD COLUMN "linesRemoved" INTEGER;
ALTER TABLE "releases" ADD COLUMN "prUrl" TEXT;
ALTER TABLE "releases" ADD COLUMN "releaseOrigin" TEXT;
ALTER TABLE "releases" ADD COLUMN "releaseDurationMs" INTEGER;
