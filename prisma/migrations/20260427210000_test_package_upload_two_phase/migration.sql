-- Two-phase commit on test-package upload.
--
-- Until now the upload handler did "MinIO put → DB create" with a
-- duplicate-version check between them. Two failure modes leaked into
-- prod:
--
-- 1. MinIO succeeded, DB create failed → orphan blob nobody owns.
-- 2. Duplicate check fired AFTER upload → wasted bandwidth + a race
--    where two concurrent uploads of the same version both succeed
--    against MinIO but only one wins the DB write.
--
-- The fix is a placeholder DB row up front: status=UPLOADING,
-- storageKey=null. MinIO upload runs second; on success the row is
-- flipped to DEVELOPMENT (or RELEASED) with the real key. Failure paths
-- leave UPLOADING rows that the retention sweep reaps.
--
-- This migration adds the UPLOADING enum value and relaxes
-- ``storageKey`` to NULL during the placeholder phase. Both changes are
-- additive and idempotent.

DO $$ BEGIN
    ALTER TYPE "TestPackageStatus" ADD VALUE IF NOT EXISTS 'UPLOADING';
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE "test_packages" ALTER COLUMN "storageKey" DROP NOT NULL;
