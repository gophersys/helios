/**
 * Extended auth helpers for the E2E story suite.
 * Re-exports existing auth helpers and adds role-based login via dev-login endpoint.
 */
import type { Page } from '@playwright/test';

// Re-export existing helpers
export { loginViaAPI, loginViaUI, ensureAuth } from './auth';

const API_URL = process.env.E2E_API_URL || 'http://localhost:9001';

type Role = 'admin' | 'maintainer' | 'developer' | 'operator';

const ROLE_EMAILS: Record<Role, string> = {
  admin: 'admin@concord.dev',
  maintainer: 'maintainer@concord.dev',
  developer: 'developer@concord.dev',
  operator: 'operator@concord.dev',
};

/**
 * Fast API-based login as a specific role.
 * Uses POST /v2/auth/dev-login with the role's email.
 * Sets the JWT token in localStorage via addInitScript.
 */
export async function loginAsRole(page: Page, role: Role): Promise<void> {
  const email = ROLE_EMAILS[role];
  const res = await page.request.post(`${API_URL}/v2/auth/dev-login`, {
    data: { email },
  });
  const body = await res.json();
  const token = body?.data?.token;
  if (!token) {
    throw new Error(`Dev login as ${role} (${email}) failed: ${JSON.stringify(body)}`);
  }

  await page.addInitScript((t: string) => {
    window.localStorage.setItem('concord-token', t);
  }, token);
}

/**
 * Login via the UI role buttons (dev mode).
 * Navigates to /login, waits for role buttons, and clicks the correct one.
 */
export async function loginAsRoleViaUI(page: Page, role: Role): Promise<void> {
  await page.goto('/login');
  await page.waitForLoadState('networkidle');

  const roleLabel = role.charAt(0).toUpperCase() + role.slice(1);
  const btn = page.locator('button').filter({ hasText: new RegExp(`^${roleLabel}$`, 'i') });
  await btn.waitFor({ timeout: 5_000 });
  await btn.click();

  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10_000 });
}
