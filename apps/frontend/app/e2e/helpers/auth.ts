import type { Page } from '@playwright/test';

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';
const TOKEN_KEY = 'concord-token';
const DEV_EMAIL = 'admin@concord.dev';

let cachedToken: string | null = null;

/**
 * Login via the dev-login API (fast, ~50ms). Sets the JWT in localStorage.
 * Caches the token across calls within the same test worker.
 */
export async function loginViaAPI(page: Page): Promise<string> {
  if (!cachedToken) {
    const res = await page.request.post(`${API_URL}/v2/auth/dev-login`, {
      data: { email: DEV_EMAIL },
    });
    const body = await res.json();
    if (!body?.data?.token) {
      throw new Error(`Login failed: ${JSON.stringify(body)}`);
    }
    cachedToken = body.data.token;
  }

  // Set token before ANY navigation via addInitScript (runs on every page load)
  await page.addInitScript((token: string) => {
    window.localStorage.setItem('concord-token', token);
  }, cachedToken);

  return cachedToken;
}

/**
 * Login via the UI role buttons (dev mode — uses dev-login buttons on /login).
 */
export async function loginViaUI(page: Page): Promise<void> {
  await page.goto('/login');
  await page.waitForLoadState('networkidle');
  const btn = page.getByRole('button', { name: /admin/i });
  await btn.waitFor({ timeout: 5_000 });
  await btn.click();
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10000 });
}

/**
 * Ensure the page is authenticated. Call in beforeEach.
 */
export async function ensureAuth(page: Page): Promise<void> {
  await loginViaAPI(page);
}
