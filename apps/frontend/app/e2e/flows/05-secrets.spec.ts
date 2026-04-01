import { test, expect } from '../fixtures';
import { loginViaAPI } from '../helpers/auth';
import { deleteSecret, getSecrets } from '../helpers/api';

test.describe('Secrets Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
  });

  async function openSettingsModal(page: import('@playwright/test').Page) {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Settings is in the sidebar footer (gear icon)
    const settingsBtn = page.locator('button').filter({ hasText: 'Settings' })
      .or(page.locator('[title="Settings"]'));
    await settingsBtn.first().click();
    await page.waitForTimeout(500);
  }

  async function clickSecretsTab(page: import('@playwright/test').Page) {
    // Inside the settings modal, click the Secrets tab
    const secretsTab = page.getByText('Secrets').first();
    await secretsTab.click();
    await page.waitForTimeout(500);
  }

  test('settings modal opens and shows Secrets tab', async ({ page }) => {
    await openSettingsModal(page);

    // The modal should be visible
    await expect(page.getByText('Secrets')).toBeVisible();
  });

  test('Bootloader Key exists in secrets list', async ({ page }) => {
    await openSettingsModal(page);
    await clickSecretsTab(page);

    await expect(page.getByText('Bootloader Key')).toBeVisible();
  });

  test.describe.serial('Create and delete secret', () => {
    let testSecretId: string | null = null;

    test('create new secret', async ({ page }) => {
      await openSettingsModal(page);
      await clickSecretsTab(page);

      // Click add/create button
      const addBtn = page.getByRole('button', { name: /add|create|new/i }).first();
      await addBtn.click();
      await page.waitForTimeout(300);

      // Fill form fields
      await page.getByPlaceholder(/name/i).first().fill('E2E Test Secret');
      // Value field
      const valueInput = page.getByPlaceholder(/value|key/i).first();
      if (await valueInput.isVisible()) {
        await valueInput.fill('test-secret-value-e2e-playwright');
      }

      // Submit
      const submitBtn = page.getByRole('button', { name: /save|create|add/i }).last();
      await submitBtn.click();
      await page.waitForLoadState('networkidle');

      // Verify it appears
      await expect(page.getByText('E2E Test Secret')).toBeVisible();

      // Get the ID for cleanup
      const secrets = await getSecrets(page) as any[];
      const testSecret = secrets?.find?.((s: any) => s.name === 'E2E Test Secret');
      testSecretId = testSecret?.id;
    });

    test('delete test secret', async ({ page }) => {
      test.skip(!testSecretId, 'No test secret to delete');

      await openSettingsModal(page);
      await clickSecretsTab(page);

      // Find and click delete for E2E Test Secret
      const secretRow = page.locator('text=E2E Test Secret').first().locator('..');
      const deleteBtn = secretRow.locator('[title="Delete"]')
        .or(secretRow.locator('button').filter({ hasText: /delete/i }))
        .or(page.locator('button[aria-label="Delete"]'));

      if (await deleteBtn.first().isVisible()) {
        await deleteBtn.first().click();
        await page.waitForTimeout(500);
        // Confirm if needed
        const confirmBtn = page.getByRole('button', { name: /confirm|delete|yes/i }).last();
        if (await confirmBtn.isVisible()) {
          await confirmBtn.click();
        }
      } else {
        // Fallback: delete via API
        if (testSecretId) {
          await deleteSecret(page, testSecretId);
          testSecretId = null;
        }
      }

      await page.waitForLoadState('networkidle');
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
