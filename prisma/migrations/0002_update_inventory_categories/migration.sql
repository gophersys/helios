-- AlterEnum: InventoryCategory
-- Old values: SOM, CARRIER_BOARD, ACCESSORY
-- New values: HARDWARE, MECHANICAL, CABLE, ACCESSORY, OTHER

-- Step 1: Create the new enum type
CREATE TYPE "InventoryCategory_new" AS ENUM ('HARDWARE', 'MECHANICAL', 'CABLE', 'ACCESSORY', 'OTHER');

-- Step 2: Migrate existing data to new values, then swap the column type
ALTER TABLE "inventory_components"
  ALTER COLUMN "category" TYPE "InventoryCategory_new"
  USING (
    CASE "category"::text
      WHEN 'SOM' THEN 'HARDWARE'::"InventoryCategory_new"
      WHEN 'CARRIER_BOARD' THEN 'HARDWARE'::"InventoryCategory_new"
      WHEN 'ACCESSORY' THEN 'ACCESSORY'::"InventoryCategory_new"
      ELSE 'OTHER'::"InventoryCategory_new"
    END
  );

-- Step 3: Drop the old enum and rename the new one
DROP TYPE "InventoryCategory";
ALTER TYPE "InventoryCategory_new" RENAME TO "InventoryCategory";
