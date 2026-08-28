-- Add message column to test_packages (developer description at upload time)
ALTER TABLE "test_packages" ADD COLUMN IF NOT EXISTS "message" TEXT;
