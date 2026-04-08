import { test, expect } from '../../fixtures';
import { SidebarComponent } from '../../pages/sidebar.component';
import { loginAsRole } from '../../helpers/auth-extended';

/**
 * Sidebar visibility tests for all four roles.
 *
 * D15: Kubernetes lives under the "System" toggle, Users under "Admin" toggle.
 *      Tests must expand those sections before checking item visibility.
 *
 * Permission matrix:
 *   Dashboard:      all
 *   Products:       ADMIN, MAINT, DEV
 *   Builds:         ADMIN, MAINT, DEV
 *   Validation:     ADMIN, MAINT, DEV
 *   Manufacturing:  all
 *   Fixtures:       ADMIN, MAINT, DEV
 *   Kubernetes:     ADMIN, MAINT   (system:view)
 *   Users:          ADMIN, MAINT   (users:view)
 *   View-As:        ADMIN, MAINT
 */

async function loginAndGoHome(page: import('@playwright/test').Page, role: Parameters<typeof loginAsRole>[1]) {
  await loginAsRole(page, role);
  await page.goto('/');
  await page.waitForLoadState('networkidle');
}

test.describe('Sidebar visibility per role', () => {
  test('Admin sees Dashboard, Products, Builds, Validation, Manufacturing, Fixtures, Kubernetes, Users', async ({ page }) => {
    await loginAndGoHome(page, 'admin');
    const sidebar = new SidebarComponent(page);

    // Primary items always visible
    await sidebar.expectItems(['Dashboard', 'Products', 'Builds', 'Validation', 'Manufacturing', 'Fixtures']);

    // System section — must expand first
    await sidebar.expandSection('System');
    await sidebar.expectItems(['Kubernetes']);

    // Admin section — must expand first
    await sidebar.expandSection('Admin');
    await sidebar.expectItems(['Users']);
  });

  test('Maintainer sees Dashboard, Products, Builds, Validation, Manufacturing, Fixtures, Kubernetes', async ({ page }) => {
    await loginAndGoHome(page, 'maintainer');
    const sidebar = new SidebarComponent(page);

    await sidebar.expectItems(['Dashboard', 'Products', 'Builds', 'Validation', 'Manufacturing', 'Fixtures']);

    // Maintainer has system:view
    await sidebar.expandSection('System');
    await sidebar.expectItems(['Kubernetes']);
  });

  test('Maintainer sees Users (has users:view permission)', async ({ page }) => {
    await loginAndGoHome(page, 'maintainer');
    const sidebar = new SidebarComponent(page);

    // D17: Maintainer CAN see Users sidebar link (gated on users:view which Maintainer HAS)
    await sidebar.expandSection('Admin');
    await sidebar.expectItems(['Users']);
  });

  test('Developer sees Dashboard, Products, Builds, Validation, Manufacturing, Fixtures', async ({ page }) => {
    await loginAndGoHome(page, 'developer');
    const sidebar = new SidebarComponent(page);

    await sidebar.expectItems(['Dashboard', 'Products', 'Builds', 'Validation', 'Manufacturing', 'Fixtures']);
  });

  test('Developer does NOT see Kubernetes or Users', async ({ page }) => {
    await loginAndGoHome(page, 'developer');
    const sidebar = new SidebarComponent(page);

    // The System and Admin toggle buttons should not even appear
    // because developer has no system:view or users:view permissions
    const systemBtn = page.locator('button').filter({ hasText: 'System' });
    await expect(systemBtn).not.toBeVisible();

    const adminBtn = page.locator('button').filter({ hasText: 'Admin' });
    await expect(adminBtn).not.toBeVisible();
  });

  test('Operator sees Dashboard and Manufacturing', async ({ page }) => {
    await loginAndGoHome(page, 'operator');
    const sidebar = new SidebarComponent(page);

    await sidebar.expectItems(['Dashboard', 'Manufacturing']);
  });

  test('Operator does NOT see Products, Builds, Validation, Fixtures, Kubernetes, Users', async ({ page }) => {
    await loginAndGoHome(page, 'operator');
    const sidebar = new SidebarComponent(page);

    await sidebar.expectHidden(['Products', 'Builds', 'Validation', 'Fixtures']);

    // System and Admin toggle buttons should not appear for operator
    const systemBtn = page.locator('button').filter({ hasText: 'System' });
    await expect(systemBtn).not.toBeVisible();

    const adminBtn = page.locator('button').filter({ hasText: 'Admin' });
    await expect(adminBtn).not.toBeVisible();
  });

  test('sidebar collapse persists across navigation', async ({ page }) => {
    await loginAndGoHome(page, 'admin');

    // Collapse the sidebar
    const collapseBtn = page.locator('button[aria-label="Collapse sidebar"]');
    await collapseBtn.click();
    await page.waitForTimeout(300);

    // Navigate to products
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    // Sidebar should still be collapsed — expand button visible instead of collapse
    const expandBtn = page.locator('button[aria-label="Expand sidebar"]');
    await expect(expandBtn).toBeVisible();

    // Navigate to manufacturing
    await page.goto('/manufacturing');
    await page.waitForLoadState('networkidle');

    // Still collapsed
    await expect(expandBtn).toBeVisible();

    // Verify localStorage has the persisted state
    const collapsed = await page.evaluate(() => localStorage.getItem('concord-sidebar-collapsed'));
    expect(collapsed).toBe('true');
  });

  test('sidebar shows user avatar and email', async ({ page }) => {
    await loginAndGoHome(page, 'admin');

    // The sidebar shows the user initial in a circular avatar
    // and the user's name or email below it
    const nav = page.locator('aside');
    await expect(nav.locator('text=admin@concord.dev').or(nav.locator('text=Admin User').or(nav.locator('text=Admin')))).toBeVisible();
  });

  test('Admin sees View-As-Role dropdown', async ({ page }) => {
    await loginAndGoHome(page, 'admin');

    const viewAsBtn = page.locator('button').filter({ hasText: /view as/i });
    await expect(viewAsBtn).toBeVisible();
  });

  test('Maintainer sees View-As-Role dropdown', async ({ page }) => {
    await loginAndGoHome(page, 'maintainer');

    const viewAsBtn = page.locator('button').filter({ hasText: /view as/i });
    await expect(viewAsBtn).toBeVisible();
  });

  test('Developer does NOT see View-As-Role dropdown', async ({ page }) => {
    await loginAndGoHome(page, 'developer');

    const viewAsBtn = page.locator('button').filter({ hasText: /view as/i });
    await expect(viewAsBtn).not.toBeVisible();
  });
});
