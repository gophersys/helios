-- Expand NotificationType enum with grouped types
ALTER TYPE "NotificationType" ADD VALUE IF NOT EXISTS 'PLATFORM_RELEASE_PUBLISHED';
ALTER TYPE "NotificationType" ADD VALUE IF NOT EXISTS 'PLATFORM_DEPLOYMENT_COMPLETE';
ALTER TYPE "NotificationType" ADD VALUE IF NOT EXISTS 'PLATFORM_DEPLOYMENT_FAILED';
ALTER TYPE "NotificationType" ADD VALUE IF NOT EXISTS 'VALIDATION_RUN_COMPLETE';
ALTER TYPE "NotificationType" ADD VALUE IF NOT EXISTS 'VALIDATION_RUN_FAILED';
ALTER TYPE "NotificationType" ADD VALUE IF NOT EXISTS 'MANUFACTURING_SESSION_COMPLETE';
ALTER TYPE "NotificationType" ADD VALUE IF NOT EXISTS 'MANUFACTURING_SESSION_FAILED';
ALTER TYPE "NotificationType" ADD VALUE IF NOT EXISTS 'BUILD_COMPLETE';
ALTER TYPE "NotificationType" ADD VALUE IF NOT EXISTS 'BUILD_FAILED';
ALTER TYPE "NotificationType" ADD VALUE IF NOT EXISTS 'SYSTEM_MAINTENANCE';

-- NotificationPreference table
CREATE TABLE "notification_preferences" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "type" "NotificationType" NOT NULL,
    "enabled" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "notification_preferences_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "notification_preferences_userId_type_key" ON "notification_preferences"("userId", "type");
CREATE INDEX "notification_preferences_userId_idx" ON "notification_preferences"("userId");

ALTER TABLE "notification_preferences"
    ADD CONSTRAINT "notification_preferences_userId_fkey"
    FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
