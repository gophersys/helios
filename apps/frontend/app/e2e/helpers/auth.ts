import type { Page } from '@playwright/test';

const API_URL = 'http://localhost:9001';
const TOKEN_KEY = 'concord-token';
const DEV_EMAIL = 'admin@concord.local';
const DEV_PASSWORD = 'admin';

let cachedToken: string | null = null;

/**
 * Login via the API (fast, ~50ms). Sets the JWT in localStorage.
 * Caches the token across calls within the same test worker.
 */
export async function loginViaAPI(page: Page): Promise<string> {
  if (!cachedToken) {
    const res = await page.request.post(`${API_URL}/v2/auth/login`, {
      data: { email: DEV_EMAIL, password: DEV_PASSWORD },
    });
    const body = await res.json();
    if (!body?.data?.token) {
      throw new Error(`Login failed: ${JSON.stringify(body)}`);
    }
    cachedToken = body.data.token;
  }

  // Navigate to a page first so localStorage is available for the domain
  await page.goto('/login', { waitUntil: 'commit' });
  await page.evaluate((token: string) => {
    localStorage.setItem('concord-token', token);
  }, cachedToken);

  return cachedToken;
}

/**
 * Login via the UI form (slower, tests the actual login flow).
 */
export async function loginViaUI(page: Page): Promise<void> {
  await page.goto('/login');
  await page.getByPlaceholder('you@company.com').fill(DEV_EMAIL);
  await page.getByPlaceholder('Enter your password').fill(DEV_PASSWORD);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10000 });
}

/**
 * Ensure the page is authenticated. Call in beforeEach.
 */
export async function ensureAuth(page: Page): Promise<void> {
  await loginViaAPI(page);
}
