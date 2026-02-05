/**
 * Validates that a URL string is safe to render as an href.
 * Only allows http: and https: protocols to prevent javascript: or data: injection.
 */
export function isSafeUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return ['http:', 'https:'].includes(parsed.protocol);
  } catch {
    return false;
  }
}
