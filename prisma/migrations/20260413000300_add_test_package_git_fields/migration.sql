-- Add missing columns to test_packages
ALTER TABLE "test_packages" ADD COLUMN IF NOT EXISTS "gitSha" TEXT;
ALTER TABLE "test_packages" ADD COLUMN IF NOT EXISTS "gitDirty" BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE "test_packages" ADD COLUMN IF NOT EXISTS "fixtureDesignId" TEXT;

-- FK for fixtureDesignId
ALTER TABLE "test_packages" ADD CONSTRAINT "test_packages_fixtureDesignId_fkey"
  FOREIGN KEY ("fixtureDesignId") REFERENCES "fixture_designs"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- Index
CREATE INDEX IF NOT EXISTS "test_packages_fixtureDesignId_idx" ON "test_packages"("fixtureDesignId");
