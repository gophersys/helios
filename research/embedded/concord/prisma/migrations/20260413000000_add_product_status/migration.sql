-- Add status column to products table
CREATE TYPE "ProductStatus" AS ENUM ('ACTIVE', 'ARCHIVED');
ALTER TABLE "products" ADD COLUMN "status" "ProductStatus" NOT NULL DEFAULT 'ACTIVE';
