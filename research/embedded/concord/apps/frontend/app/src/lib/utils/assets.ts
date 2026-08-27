/**
 * Build a canonical asset filename from its component parts.
 *
 * Pattern: {product}_{role}_{processor}_{revision}_{variant}.{ext}
 * Example: alpha_app_nrf52840_b0_debug.hex
 */
export function canonicalFilename(
  productSlug: string,
  role: string,
  processor: string | null,
  revision: string,
  variant: string,
  ext: string,
): string {
  const parts = [
    productSlug || 'unknown',
    role || 'unknown',
    processor || 'unknown',
    revision?.toLowerCase() || 'unknown',
    variant || 'unknown',
  ];
  return parts.join('_') + `.${ext}`;
}
