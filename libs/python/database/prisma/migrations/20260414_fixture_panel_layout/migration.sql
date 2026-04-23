-- Add panel layout columns to fixtures
ALTER TABLE "fixtures" ADD COLUMN "panelRows" INTEGER NOT NULL DEFAULT 1;
ALTER TABLE "fixtures" ADD COLUMN "panelCols" INTEGER NOT NULL DEFAULT 1;
