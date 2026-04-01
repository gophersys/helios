import { test, expect } from '../fixtures';
import { loginViaAPI } from '../helpers/auth';
import { deleteSecret, getSecrets } from '../helpers/api';

test.describe('Secrets Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('settings button exists in sidebar', async ({ page }) => {
    // Settings is a button in the sidebar footer with gear icon
    const settingsBtn = page.getByRole('button', { name: 'Settings' });
    await expect(settingsBtn).toBeVisible();
  });

  test('settings modal opens on click', async ({ page }) => {
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.waitForTimeout(500);
    // Modal should appear with settings content (uses role="dialog")
    await expect(page.getByRole('dialog')).toBeVisible();
  });

  test('secrets tab shows Bootloader Key', async ({ page }) => {
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.waitForTimeout(500);
    // Click Secrets tab
    await page.getByRole('button', { name: 'Secrets' }).or(page.getByText('Secrets')).first().click();
    await page.waitForTimeout(500);
    await expect(page.getByText('Bootloader Key')).toBeVisible();
  });

  test.describe.serial('Create and delete secret', () => {
    let testSecretId: string | null = null;

    test('create test secret via API and verify in settings', async ({ page }) => {
      // Create via API (reliable)
      const secret = await (await page.request.post('http://localhost:9001/v2/system/secrets', {
        data: { name: 'E2E Test Secret', type: 'signing_key', value: 'dGVzdC1zZWNyZXQ=' },
        headers: { Authorization: 'ApiKey ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG', 'Content-Type': 'application/json' },
      })).json();
      testSecretId = secret?.data?.id;

      // Verify in settings modal
      await page.getByRole('button', { name: 'Settings' }).click();
      await page.waitForTimeout(500);
      await page.getByRole('button', { name: 'Secrets' }).or(page.getByText('Secrets')).first().click();
      await page.waitForTimeout(500);
      await expect(page.getByText('E2E Test Secret')).toBeVisible();
    });

    test('delete test secret via API and verify gone', async ({ page }) => {
      test.skip(!testSecretId, 'No test secret');
      await deleteSecret(page, testSecretId!);
      testSecretId = null;

      // Verify in settings modal
      await page.getByRole('button', { name: 'Settings' }).click();
      await page.waitForTimeout(500);
      await page.getByRole('button', { name: 'Secrets' }).or(page.getByText('Secrets')).first().click();
      await page.waitForTimeout(500);
      await expect(page.getByText('E2E Test Secret')).not.toBeVisible();
    });

    test.afterAll(async ({ request }) => {
      if (testSecretId) {
        try {
          await request.delete(`http://localhost:9001/v2/system/secrets/${testSecretId}`, {
            headers: { Authorization: 'ApiKey ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG' },
          });
        } catch { /* ignore */ }
      }
    });
  });
});
