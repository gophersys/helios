import { test, expect } from '../../fixtures';
import { SidebarComponent } from '../../pages/sidebar.component';
import { loginAsRole } from '../../helpers/auth-extended';

/**
 * View-As-Role tests.
 *
 * The View-As feature lets Admin/Maintainer preview the sidebar as another role.
 * It stores the selection in localStorage as `concord-view-as-role` and triggers
 * window.location.reload(). The API sends the value via X-View-As-Role header,
 * which changes the effective permission set returned by /v2/auth/me.
 *
 * After reload, the sidebar reflects the impersonated role's permissions.
 */

async function loginAdminAndGoHome(page: import('@playwright/test').Page) {
  await loginAsRole(page, 'admin');
  await page.goto('/');
  await page.waitForLoadState('networkidle');
}

test.describe('View-As-Role', () => {
  test('Admin can select Maintainer from View-As dropdown and page reloads', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const sidebar = new SidebarComponent(page);

    // Open View-As dropdown and select Maintainer
    await sidebar.viewAsRole('Maintainer');

    // The view-as triggers a reload. Wait for it to settle.
    await page.waitForLoadState('networkidle');

    // Verify the sidebar now shows "Viewing as Maintainer"
    await expect(page.locator('text=Viewing as Maintainer')).toBeVisible();
  });

  test('View-As Maintainer: sidebar still shows Users (maintainer has users:view)', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const sidebar = new SidebarComponent(page);

    await sidebar.viewAsRole('Maintainer');
    await page.waitForLoadState('networkidle');

    // Maintainer has users:view, so Admin section toggle should still appear
    await sidebar.expandSection('Admin');
    await sidebar.expectItems(['Users']);

    // System section should also still appear (maintainer has system:view)
    await sidebar.expandSection('System');
    await sidebar.expectItems(['Kubernetes']);
  });

  test('Admin can select Developer from View-As dropdown and page reloads', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const sidebar = new SidebarComponent(page);

    await sidebar.viewAsRole('Developer');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('text=Viewing as Developer')).toBeVisible();
  });

  test('View-As Developer hides Kubernetes and Users sidebar items', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const sidebar = new SidebarComponent(page);

    await sidebar.viewAsRole('Developer');
    await page.waitForLoadState('networkidle');

    // Primary items should still be visible
    await sidebar.expectItems(['Dashboard', 'Products', 'Builds', 'Validation', 'Manufacturing', 'Fixtures']);

    // System and Admin toggle buttons should NOT appear for developer view
    const systemBtn = page.locator('button').filter({ hasText: 'System' });
    await expect(systemBtn).not.toBeVisible();

    const adminBtn = page.locator('button').filter({ hasText: 'Admin' });
    await expect(adminBtn).not.toBeVisible();
  });

  test('Admin can select Operator from View-As dropdown and page reloads', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const sidebar = new SidebarComponent(page);

    await sidebar.viewAsRole('Operator');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('text=Viewing as Operator')).toBeVisible();
  });

  test('View-As Operator shows only Dashboard and Manufacturing', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const sidebar = new SidebarComponent(page);

    await sidebar.viewAsRole('Operator');
    await page.waitForLoadState('networkidle');

    await sidebar.expectItems(['Dashboard', 'Manufacturing']);
    await sidebar.expectHidden(['Products', 'Builds', 'Validation', 'Fixtures']);

    // System/Admin toggles should not appear
    const systemBtn = page.locator('button').filter({ hasText: 'System' });
    await expect(systemBtn).not.toBeVisible();

    const adminBtn = page.locator('button').filter({ hasText: 'Admin' });
    await expect(adminBtn).not.toBeVisible();
  });

  test('View-As value persists in localStorage as concord-view-as-role', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const sidebar = new SidebarComponent(page);

    await sidebar.viewAsRole('Developer');
    await page.waitForLoadState('networkidle');

    const viewAsValue = await page.evaluate(() =>
      localStorage.getItem('concord-view-as-role')
    );
    expect(viewAsValue).toBe('DEVELOPER');
  });

  test('Reset View-As restores full Admin sidebar', async ({ page }) => {
    await loginAdminAndGoHome(page);
    const sidebar = new SidebarComponent(page);

    // First set View-As to Operator (most restricted)
    await sidebar.viewAsRole('Operator');
    await page.waitForLoadState('networkidle');

    // Verify restricted view
    await sidebar.expectHidden(['Products', 'Builds', 'Validation', 'Fixtures']);

    // Reset to own view (null)
    await sidebar.viewAsRole(null);
    await page.waitForLoadState('networkidle');

    // Full Admin sidebar should be restored
    await sidebar.expectItems(['Dashboard', 'Products', 'Builds', 'Validation', 'Manufacturing', 'Fixtures']);

    // System and Admin sections should be available again
    await sidebar.expandSection('System');
    await sidebar.expectItems(['Kubernetes']);

    await sidebar.expandSection('Admin');
    await sidebar.expectItems(['Users']);

    // localStorage should be cleared
    const viewAsValue = await page.evaluate(() =>
      localStorage.getItem('concord-view-as-role')
    );
    expect(viewAsValue).toBeNull();
  });
});
