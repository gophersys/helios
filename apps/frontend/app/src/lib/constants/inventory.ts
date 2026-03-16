/**
 * Inventory category constants and utilities.
 * Used across inventory components for consistent category display.
 */

// NOTE: These categories must match the Prisma InventoryCategory enum
// To add new categories, update prisma/schema.prisma and run migration
export const COMPONENT_CATEGORIES = {
  HARDWARE: 'Hardware',
  MECHANICAL: 'Mechanical Part',
  CABLE: 'Cable / Connector',
  ACCESSORY: 'Accessory',
  OTHER: 'Other',
} as const;

export type ComponentCategory = keyof typeof COMPONENT_CATEGORIES;

/**
 * Get display name for a component category.
 * Returns the category key if not found (graceful degradation).
 */
export function getCategoryDisplayName(category: string): string {
  return COMPONENT_CATEGORIES[category as ComponentCategory] ?? category;
}

/**
 * Get all available category options for select dropdowns.
 */
export function getCategoryOptions(): { value: ComponentCategory; label: string }[] {
  return Object.entries(COMPONENT_CATEGORIES).map(([value, label]) => ({
    value: value as ComponentCategory,
    label,
  }));
}

export const REVISION_STATUSES = {
  ACTIVE: 'Active',
  DEPRECATED: 'Deprecated',
  EOL: 'End of Life',
} as const;

export type RevisionStatus = keyof typeof REVISION_STATUSES;

/**
 * Get display name for a revision status.
 */
export function getStatusDisplayName(status: string): string {
  return REVISION_STATUSES[status as RevisionStatus] ?? status;
}
