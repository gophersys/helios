-- Session-code authorisation for the corectl CLI (RFC 8628 device-code
-- flow) and refresh-token rotation. Replaces the paste-an-API-key
-- onboarding for human users; service accounts continue to use the
-- existing api_keys table.
--
-- AuthSession lifecycle:
--   PENDING (created by /v2/auth/session/code, 10 min expiry)
--     → APPROVED (/v2/auth/session/approve sets userId + issues a
--       RefreshToken)
--     → EXPIRED / DENIED (terminal)
--
-- RefreshToken rotation:
--   Each /v2/auth/session/refresh issues a new token and revokes the
--   presented one. parentId records the chain so a replayed (already-
--   revoked) token is detectable; future PR will revoke the entire
--   chain on detection and audit-log a SUSPECTED_REPLAY event.

-- CreateEnum
CREATE TYPE "AuthSessionStatus" AS ENUM ('PENDING', 'APPROVED', 'EXPIRED', 'DENIED');

-- CreateTable
CREATE TABLE "auth_sessions" (
    "id" TEXT NOT NULL,
    "userCode" TEXT NOT NULL,
    "deviceCode" TEXT NOT NULL,
    "status" "AuthSessionStatus" NOT NULL DEFAULT 'PENDING',
    "userId" TEXT,
    "userAgent" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "approvedAt" TIMESTAMP(3),

    CONSTRAINT "auth_sessions_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "auth_sessions_userCode_key" ON "auth_sessions"("userCode");
CREATE UNIQUE INDEX "auth_sessions_deviceCode_key" ON "auth_sessions"("deviceCode");
CREATE INDEX "auth_sessions_deviceCode_idx" ON "auth_sessions"("deviceCode");
CREATE INDEX "auth_sessions_userId_idx" ON "auth_sessions"("userId");
CREATE INDEX "auth_sessions_expiresAt_idx" ON "auth_sessions"("expiresAt");

-- AddForeignKey
ALTER TABLE "auth_sessions" ADD CONSTRAINT "auth_sessions_userId_fkey"
    FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- CreateTable
CREATE TABLE "refresh_tokens" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "tokenHash" TEXT NOT NULL,
    "parentId" TEXT,
    "revokedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expiresAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "refresh_tokens_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "refresh_tokens_tokenHash_key" ON "refresh_tokens"("tokenHash");
CREATE INDEX "refresh_tokens_userId_idx" ON "refresh_tokens"("userId");
CREATE INDEX "refresh_tokens_sessionId_idx" ON "refresh_tokens"("sessionId");
CREATE INDEX "refresh_tokens_expiresAt_idx" ON "refresh_tokens"("expiresAt");

-- AddForeignKey
ALTER TABLE "refresh_tokens" ADD CONSTRAINT "refresh_tokens_userId_fkey"
    FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "refresh_tokens" ADD CONSTRAINT "refresh_tokens_sessionId_fkey"
    FOREIGN KEY ("sessionId") REFERENCES "auth_sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;
