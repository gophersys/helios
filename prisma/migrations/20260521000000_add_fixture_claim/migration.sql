-- ============================================================================
-- add_fixture_claim
--
-- Introduces the `FixtureClaim` entity (and its node-mode child
-- `ClaimedNode`) plus the `FixtureClaimStatus` enum. Backs the DEV_HOLD
-- local-dev TDD loop: a developer leases a real fixture (or an ad-hoc
-- set of raw nodes) for the duration of a development session, and the
-- backend honors the lease against concurrent TestRun /
-- ManufacturingSession scheduling.
--
-- Two binding modes share a single lifecycle:
--   * fixture-mode — fixtureId set, all slots held implicitly
--   * node-mode    — claimed_nodes populated, ad-hoc node set held
--
-- TTL is sliding (lastHeartbeatAt + 5min) clamped by hardCeilingAt
-- (acquiredAt + 8h). State transitions ACTIVE → RELEASED (explicit) /
-- EXPIRED (sliding TTL lapse) / ABANDONED (hard ceiling).
--
-- The reservation gate (is_fixture_busy) unions ACTIVE FixtureClaim
-- with active TestRun / ManufacturingSession — see schema-overview.md.
--
-- Additive migration. No existing tables touched.
-- ============================================================================

-- CreateEnum
CREATE TYPE "FixtureClaimStatus" AS ENUM ('ACTIVE', 'RELEASED', 'EXPIRED', 'ABANDONED');

-- CreateTable
CREATE TABLE "fixture_claims" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "fixtureId" TEXT,
    "status" "FixtureClaimStatus" NOT NULL DEFAULT 'ACTIVE',
    "acquiredAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "lastHeartbeatAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "hardCeilingAt" TIMESTAMP(3) NOT NULL,
    "releasedAt" TIMESTAMP(3),
    "description" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "fixture_claims_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "claimed_nodes" (
    "id" TEXT NOT NULL,
    "claimId" TEXT NOT NULL,
    "nodeId" TEXT NOT NULL,
    "label" TEXT,

    CONSTRAINT "claimed_nodes_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "fixture_claims_fixtureId_status_idx" ON "fixture_claims"("fixtureId", "status");

-- CreateIndex
CREATE INDEX "fixture_claims_userId_status_idx" ON "fixture_claims"("userId", "status");

-- CreateIndex
CREATE UNIQUE INDEX "claimed_nodes_claimId_nodeId_key" ON "claimed_nodes"("claimId", "nodeId");

-- CreateIndex
CREATE INDEX "claimed_nodes_nodeId_idx" ON "claimed_nodes"("nodeId");

-- AddForeignKey
ALTER TABLE "fixture_claims" ADD CONSTRAINT "fixture_claims_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "fixture_claims" ADD CONSTRAINT "fixture_claims_fixtureId_fkey" FOREIGN KEY ("fixtureId") REFERENCES "fixtures"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "claimed_nodes" ADD CONSTRAINT "claimed_nodes_claimId_fkey" FOREIGN KEY ("claimId") REFERENCES "fixture_claims"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "claimed_nodes" ADD CONSTRAINT "claimed_nodes_nodeId_fkey" FOREIGN KEY ("nodeId") REFERENCES "nodes"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
