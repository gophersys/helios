-- Fix schema drift: fixture_designs.type was created as "StageType" NOT NULL
-- DEFAULT 'VALIDATION' but the Prisma schema declares it "NodeType?". Prisma's
-- runtime query uses NodeType values, and Postgres rejects the comparison:
--
--   operator does not exist: "StageType" = "NodeType"
--
-- NodeType and StageType have identical variants (MANUFACTURING, VALIDATION),
-- so the cast via text is safe for every existing row. Drop NOT NULL + the
-- StageType default so the column matches the nullable schema, then retype.

ALTER TABLE "fixture_designs" ALTER COLUMN "type" DROP NOT NULL;
ALTER TABLE "fixture_designs" ALTER COLUMN "type" DROP DEFAULT;
ALTER TABLE "fixture_designs"
  ALTER COLUMN "type" TYPE "NodeType"
  USING "type"::text::"NodeType";
