import { expect, test } from '@playwright/test';

// The LOGIN E2E against a REAL Vault + Postgres + platformgateway-live stack (run-login.sh) — ZERO
// mocks. It proves the whole login path end to end: real Vault resolves platformgateway's JWT +
// Postgres DSN → platformgateway migrates the users table + seeds the default user at startup (the
// IOTEA-style seed) → the PUBLIC login bootstrap returns that user → the /login screen loads it →
// "Continue" lands on the Projects dashboard signed in AS that user (the profile card names them).
//
// The default identity is the seed default (environment.go: "Mateo Segura" / mateo@eden.local) — the
// E2E does not override it, so it asserts those exact values, proving the seed planted the real row.

const DEFAULT_NAME = 'Mateo Segura';
const DEFAULT_EMAIL = 'mateo@eden.local';

test.describe('login — real Vault + Postgres + platformgateway (no mocks)', () => {
  test('login loads the seeded default user and continues into the dashboard as them', async ({
    page,
  }) => {
    await page.goto('/login');
    await expect(page.getByTestId('login-screen')).toBeVisible();

    // The login screen loads the seeded default user from platformgateway's public bootstrap (real
    // Vault → real Postgres). The default-user card names them and shows their email.
    const who = page.getByTestId('login-default-user');
    await expect(who).toContainText(DEFAULT_NAME, { timeout: 20_000 });
    await expect(who).toContainText(DEFAULT_EMAIL);
    await expect(page.getByTestId('login-continue').getByRole('button')).toContainText(
      DEFAULT_NAME,
    );

    // Continue → land on the Projects dashboard signed in as that user (NOT the unauthenticated
    // "You" fallback — a real identity loaded from the platform).
    await page.getByTestId('login-continue').getByRole('button').click();
    await expect(page).toHaveURL(/\/projects$/, { timeout: 20_000 });
    await expect(page.getByTestId('user-name')).toHaveText(DEFAULT_NAME, { timeout: 20_000 });
  });

  test('the public bootstrap returns the seeded default user (the API the login reads)', async ({
    request,
    baseURL,
  }) => {
    // Hit the SAME public endpoint the login screen reads, through the UI's same-origin /platform
    // proxy — proving platformgateway served the seeded user over real Vault + Postgres.
    const response = await request.get(`${baseURL}/platform/bootstrap/default-user`);
    expect(response.ok()).toBeTruthy();
    const body = (await response.json()) as {
      data: {
        email: string;
        name: string;
        isDefault: boolean;
        organization: { name: string };
        role: string;
        permissions: string[];
      };
    };
    expect(body.data.email).toBe(DEFAULT_EMAIL);
    expect(body.data.name).toBe(DEFAULT_NAME);
    expect(body.data.isDefault).toBe(true);
    // The IOTEA-style RBAC seed: the default user is an ADMIN of the default org with the "*" grant —
    // proving the org + permission-set + membership were migrated + seeded on the real stack.
    expect(body.data.organization.name).toBe('Eden');
    expect(body.data.role).toBe('admin');
    expect(body.data.permissions).toContain('*');
  });
});
