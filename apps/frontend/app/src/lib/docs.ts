import { PUBLIC_APP_ENVIRONMENT } from '$env/static/public';
import { browser } from '$app/environment';

/**
 * Build the docs base URL from the current hostname.
 *
 * Development: http://localhost:4000 (mkdocs serve standalone)
 * Staging:     https://docs.staging.concord.local
 * Production:  https://docs.concord.local
 */
function getDocsBase(): string {
  const env = PUBLIC_APP_ENVIRONMENT || 'development';
  if (env === 'development' || env === 'local') {
    return 'http://localhost:4000';
  }
  if (!browser) return '/';
  // Derive docs subdomain from current host: staging.concord.local → docs.staging.concord.local
  const host = window.location.hostname;
  const protocol = window.location.protocol;
  return `${protocol}//docs.${host}`;
}

/**
 * Maps app routes to their corresponding docs sections.
 */
const DOCS_MAP: Record<string, string> = {
  '/products': '/products/',
  '/builds': '/builds/',
  '/validation': '/validation/',
  '/manufacturing': '/manufacturing/',
  '/fixtures': '/fixtures/',
  '/users': '/administration/users-and-roles/',
  '/kubernetes': '/platform/',
  '/history': '/platform/',
  '/ci': '/builds/ci-integration/'
};

/**
 * Get the docs URL for a given app route path.
 * Returns the most specific match, or the docs root.
 */
export function getDocsUrl(appPath: string): string {
  const base = getDocsBase();
  const match = Object.entries(DOCS_MAP).find(([key]) => appPath.startsWith(key));
  return match ? `${base}${match[1]}` : `${base}/`;
}

/**
 * Build a docs URL for a specific docs path.
 */
export function docsUrl(path: string): string {
  return `${getDocsBase()}${path}`;
}
