-- AlterTable: Change unique constraint on tests from (productId, name) to (productId, name, category)
-- This allows tests with the same name in different modules (categories) to be distinct records.
-- e.g., test_01_download_artifacts in test_01_mfg_to_mfg_fuota vs test_02_mfg_to_prod_fuota

-- Drop the old constraint
DROP INDEX IF EXISTS "tests_productId_name_key";

-- Make category NOT NULL with a default for existing rows
UPDATE "tests" SET "category" = 'uncategorized' WHERE "category" IS NULL;

-- Add the new unique constraint
CREATE UNIQUE INDEX "tests_productId_name_category_key" ON "tests"("productId", "name", "category");
