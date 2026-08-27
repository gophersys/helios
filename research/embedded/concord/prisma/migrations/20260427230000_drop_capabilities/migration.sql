-- Drop the legacy ``capabilities`` / ``hardware`` lists from
-- ``fixture_designs`` and ``test_package_stages``.
--
-- Per-package fixture-design ownership (v0.5.0) made the test app's
-- ``concord.yaml`` + extracted ``fixture.yaml`` the single source of
-- truth for what hardware a fixture provides and a stage needs. The
-- parallel ``capabilities[]`` / ``hardware[]`` arrays were a pre-v0.5.0
-- matching mechanism that has nothing to gate against anymore — every
-- fixture instance derives from a design that already encodes its
-- behaviour, and the test app declares its own requirements.
--
-- Dropped here so the runtime stops reading + storing them; backend
-- and frontend code that referenced them is removed in the same
-- commit. ``IF EXISTS`` so the migration tolerates partial state on
-- hosts that received earlier hotfix patches.

ALTER TABLE "fixture_designs" DROP COLUMN IF EXISTS "capabilities";
ALTER TABLE "test_package_stages" DROP COLUMN IF EXISTS "hardware";
