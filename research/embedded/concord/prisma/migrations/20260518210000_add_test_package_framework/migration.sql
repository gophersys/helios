-- ============================================================================
-- add_test_package_framework
--
-- Adds the `TestFramework` enum and the `framework` column on
-- `test_packages`. Selects which entrypoint the validation runner Job
-- dispatches:
--   * PYTEST — the existing path (corekinect.test.runner via pytest)
--   * ZTEST  — Zephyr ztest captured over UART via corekinect.test.ztest_runner
--
-- The column defaults to PYTEST so every pre-existing row preserves
-- its original behaviour. NOT NULL — the runner dispatch is not
-- allowed to be ambiguous, and "no framework declared" already maps
-- to PYTEST in the upload handler.
-- ============================================================================

CREATE TYPE "TestFramework" AS ENUM ('PYTEST', 'ZTEST');

ALTER TABLE "test_packages"
    ADD COLUMN "framework" "TestFramework" NOT NULL DEFAULT 'PYTEST';
