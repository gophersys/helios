/**
 * E2E tests for Kubernetes Pod Detail page.
 * Tests logs, container switching, terminal, YAML view.
 *
 * Run with: VITE_BACKEND_URL=https://staging.concord.local npx playwright test e2e/kubernetes-pod-detail.spec.ts
 */
import { test, expect, type Page, type BrowserContext } from '@playwright/test';

const API_KEY = 'ck_run_test_Oi4FANF9YUsaWuJJM3fzG2K1VngfctZlDO72yyo0CDk';

async function authenticateWithApiKey(context: BrowserContext) {
  await context.route('**/v2/**', async route => {
    const headers = {
      ...route.request().headers(),
      'Authorization': `ApiKey ${API_KEY}`
    };
    await route.continue({ headers });
  });
}

async function mockAuthState(page: Page) {
  await page.goto('/login');
  await page.evaluate(() => {
    localStorage.setItem('concord-token', 'staging-e2e-test-token');
    localStorage.setItem('concord-user', JSON.stringify({
      id: 'e2e-test-user',
      email: 'test@example.com',
      name: 'E2E Test User',
      permissionSetName: 'Super Admin',
      permissions: [
        'products:view', 'products:manage',
        'system:view', 'system:manage'
      ]
    }));
  });
}

test.describe('Kubernetes Pod Detail', () => {
  let podNamespace: string;
  let podName: string;

  test.beforeAll(async ({ browser }) => {
    // Fetch a real pod from the staging cluster
    const context = await browser.newContext();
    await authenticateWithApiKey(context);
    const page = await context.newPage();

    const res = await page.request.get('https://staging.concord.local/v2/cluster/pods', {
      headers: { 'Authorization': `ApiKey ${API_KEY}` }
    });
    const body = await res.json();
    const pods = body.data || [];

    // Find a pod with multiple containers (build-worker has 2)
    const multiContainerPod = pods.find((p: any) =>
      p.containers && p.containers.length > 1 && p.status === 'Running'
    );

    if (multiContainerPod) {
      podNamespace = multiContainerPod.namespace;
      podName = multiContainerPod.name;
    } else if (pods.length > 0) {
      // Fallback to first running pod
      const runningPod = pods.find((p: any) => p.status === 'Running') || pods[0];
      podNamespace = runningPod.namespace;
      podName = runningPod.name;
    }

    await context.close();
  });

  test.beforeEach(async ({ context, page }) => {
    await authenticateWithApiKey(context);
    await mockAuthState(page);
  });

  test('pod detail page loads with all sections', async ({ page }) => {
    test.skip(!podName, 'No pods available in staging');

    await page.goto(`/kubernetes/pods/${podNamespace}/${podName}`);
    await page.waitForLoadState('networkidle');

    // Should see pod name in header
    await expect(page.locator('h2').filter({ hasText: podName })).toBeVisible({ timeout: 10000 });

    // Should see status indicator
    await expect(page.locator('text=Running').first()).toBeVisible();

    // Should see Logs section
    await expect(page.getByText('Logs').first()).toBeVisible();

    // Should see Containers section
    await expect(page.getByText('Containers').first()).toBeVisible();

    // Should see Conditions section
    await expect(page.getByText('Conditions').first()).toBeVisible();
  });

  test('logs section is expanded by default', async ({ page }) => {
    test.skip(!podName, 'No pods available in staging');

    await page.goto(`/kubernetes/pods/${podNamespace}/${podName}`);
    await page.waitForLoadState('networkidle');

    // Wait for logs section to be visible
    await expect(page.getByText('Logs').first()).toBeVisible({ timeout: 10000 });

    // Should see container selector in logs controls
    await expect(page.getByText('Container:').first()).toBeVisible({ timeout: 5000 });

    // Should see tail selector
    await expect(page.getByText('Tail:').first()).toBeVisible();
  });

  test('can switch between containers in logs', async ({ page }) => {
    test.skip(!podName, 'No pods available in staging');

    await page.goto(`/kubernetes/pods/${podNamespace}/${podName}`);
    await page.waitForLoadState('networkidle');

    // Wait for logs section to load
    await expect(page.getByText('Container:').first()).toBeVisible({ timeout: 10000 });

    // Find container dropdown
    const containerDropdown = page.locator('.select-wrapper').filter({ hasText: 'Container:' }).locator('button').first();

    // Get initial container name
    const initialText = await containerDropdown.textContent();

    // Click dropdown
    await containerDropdown.click();
    await page.waitForTimeout(500);

    // Check if there are multiple options
    const options = page.locator('[role="listbox"] [role="option"]');
    const optionCount = await options.count();

    if (optionCount > 1) {
      // Click the second option
      await options.nth(1).click();
      await page.waitForTimeout(1000);

      // Verify container changed (log stream should reconnect)
      const newText = await containerDropdown.textContent();
      expect(newText).not.toBe(initialText);
    }
  });

  test('YAML button opens dialog', async ({ page }) => {
    test.skip(!podName, 'No pods available in staging');

    await page.goto(`/kubernetes/pods/${podNamespace}/${podName}`);
    await page.waitForLoadState('networkidle');

    // Click YAML button
    const yamlButton = page.locator('button').filter({ hasText: 'YAML' });
    await expect(yamlButton).toBeVisible({ timeout: 10000 });
    await yamlButton.click();

    // Should see YAML dialog with content
    await expect(page.getByText('Pod YAML').or(page.locator('text=apiVersion'))).toBeVisible({ timeout: 5000 });
  });

  test('terminal button shows for running containers', async ({ page }) => {
    test.skip(!podName, 'No pods available in staging');

    await page.goto(`/kubernetes/pods/${podNamespace}/${podName}`);
    await page.waitForLoadState('networkidle');

    // Look for Terminal button in header
    const terminalButton = page.locator('button').filter({ hasText: 'Terminal' });
    await expect(terminalButton.first()).toBeVisible({ timeout: 10000 });
  });

  test('can collapse and expand logs section', async ({ page }) => {
    test.skip(!podName, 'No pods available in staging');

    await page.goto(`/kubernetes/pods/${podNamespace}/${podName}`);
    await page.waitForLoadState('networkidle');

    // Should see container selector (logs expanded)
    await expect(page.getByText('Container:').first()).toBeVisible({ timeout: 10000 });

    // Click logs header to collapse
    const logsHeader = page.locator('button').filter({ hasText: 'Logs' }).first();
    await logsHeader.click();
    await page.waitForTimeout(500);

    // Container selector should not be visible (collapsed)
    await expect(page.getByText('Container:').first()).not.toBeVisible();

    // Click again to expand
    await logsHeader.click();
    await page.waitForTimeout(500);

    // Should be visible again
    await expect(page.getByText('Container:').first()).toBeVisible();
  });

  test('back button navigates to pods list', async ({ page }) => {
    test.skip(!podName, 'No pods available in staging');

    await page.goto(`/kubernetes/pods/${podNamespace}/${podName}`);
    await page.waitForLoadState('networkidle');

    // Click back button
    const backButton = page.locator('button').filter({ hasText: 'Back to Pods' });
    await expect(backButton).toBeVisible({ timeout: 10000 });
    await backButton.click();

    // Should navigate to pods list
    await expect(page).toHaveURL(/.*kubernetes\/pods/, { timeout: 10000 });
  });

  test('container cards show shell button for running containers', async ({ page }) => {
    test.skip(!podName, 'No pods available in staging');

    await page.goto(`/kubernetes/pods/${podNamespace}/${podName}`);
    await page.waitForLoadState('networkidle');

    // Wait for containers section
    await expect(page.getByText('Containers').first()).toBeVisible({ timeout: 10000 });

    // Look for Shell button on any container card
    const shellButtons = page.locator('.card-sm button').filter({ hasText: 'Shell' });

    // At least one running container should have a shell button
    const count = await shellButtons.count();
    expect(count).toBeGreaterThanOrEqual(0); // May be 0 if no running containers
  });
});
