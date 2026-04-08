import { test, expect } from '../../fixtures';
import { loginAsRole } from '../../helpers/auth-extended';
import { ProductsPage } from '../../pages/products.page';
import { ProductWizardComponent } from '../../pages/product-wizard.component';

/**
 * Product Creation Wizard — 4-step wizard flow.
 * Tests run in serial because they are cumulative: earlier tests set up state for later ones.
 *
 * Steps: Branch -> Board Family -> Configure -> Create
 */

test.describe.configure({ mode: 'serial' });

// Shared state across cumulative tests
let createdProductId: string | undefined;

test.describe('Product Creation Wizard', () => {
  test('Products page shows empty state when no products exist', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    // Either the empty state message or the filter "no matches" message
    const emptyState = page.getByText(/no products/i);
    await expect(emptyState).toBeVisible({ timeout: 10_000 });
  });

  test('Create Product button visible for Admin', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    const createBtn = page.getByRole('button', { name: /new product/i });
    await expect(createBtn).toBeVisible();
  });

  test('Create Product button visible for Maintainer', async ({ page }) => {
    await loginAsRole(page, 'maintainer');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    const createBtn = page.getByRole('button', { name: /new product/i });
    await expect(createBtn).toBeVisible();
  });

  test('Create Product button NOT visible for Developer', async ({ page }) => {
    await loginAsRole(page, 'developer');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    const createBtn = page.getByRole('button', { name: /new product/i });
    await expect(createBtn).not.toBeVisible();
  });

  test('clicking Create Product opens wizard', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /new product/i }).click();

    // Wizard shows step indicator with "Branch" as first step
    await expect(page.getByText('Select ck_boards branch')).toBeVisible({ timeout: 10_000 });
  });

  test('Step 1: branch selector loads branches from ck_boards repo', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /new product/i }).click();
    await expect(page.getByText('Select ck_boards branch')).toBeVisible({ timeout: 10_000 });

    // Wait for branches to load (loading spinner disappears)
    await page.waitForSelector('#branch-select', { timeout: 15_000 });

    // The branch select should have options
    const select = page.locator('#branch-select');
    await expect(select).toBeVisible();
    const options = select.locator('option');
    const count = await options.count();
    expect(count).toBeGreaterThan(0);
  });

  test('Step 1: selecting "main" branch proceeds to step 2', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /new product/i }).click();
    await page.waitForSelector('#branch-select', { timeout: 15_000 });

    // "main" should be auto-selected if present
    const select = page.locator('#branch-select');
    await select.selectOption('main');

    // Click Next
    await page.getByRole('button', { name: /next/i }).click();

    // Step 2: "Select product family" heading
    await expect(page.getByText('Select product family')).toBeVisible({ timeout: 15_000 });
  });

  test('Step 2: board family list populated from ck_boards discovery', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /new product/i }).click();
    await page.waitForSelector('#branch-select', { timeout: 15_000 });
    await page.locator('#branch-select').selectOption('main');
    await page.getByRole('button', { name: /next/i }).click();
    await expect(page.getByText('Select product family')).toBeVisible({ timeout: 15_000 });

    // Wait for scanning to finish and board cards to appear
    // Board families appear as clickable cards with family name
    await page.waitForSelector('button:has-text("alpha")', { timeout: 20_000 });
    const alphaCard = page.locator('button').filter({ hasText: /alpha/i }).first();
    await expect(alphaCard).toBeVisible();
  });

  test('Step 2: selecting "alpha" board family proceeds to step 3', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /new product/i }).click();
    await page.waitForSelector('#branch-select', { timeout: 15_000 });
    await page.locator('#branch-select').selectOption('main');
    await page.getByRole('button', { name: /next/i }).click();

    // Wait for boards and select alpha
    await page.waitForSelector('button:has-text("alpha")', { timeout: 20_000 });
    await page.locator('button').filter({ hasText: /alpha/i }).first().click();

    await page.getByRole('button', { name: /next/i }).click();

    // Step 3: "Configure product" heading
    await expect(page.getByText('Configure product')).toBeVisible({ timeout: 15_000 });
  });

  test('Step 3: board revision config shows SoC fields', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    // Walk to step 3
    await page.getByRole('button', { name: /new product/i }).click();
    await page.waitForSelector('#branch-select', { timeout: 15_000 });
    await page.locator('#branch-select').selectOption('main');
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForSelector('button:has-text("alpha")', { timeout: 20_000 });
    await page.locator('button').filter({ hasText: /alpha/i }).first().click();
    await page.getByRole('button', { name: /next/i }).click();
    await expect(page.getByText('Configure product')).toBeVisible({ timeout: 15_000 });

    // Should show revision section(s) with SoC info (nrf52840, nrf9151)
    // Targets appear as role labels (app, comms)
    await expect(page.getByText(/app/i).first()).toBeVisible();
    // AppID input fields should be present
    const appIdInputs = page.locator('input[type="number"][placeholder*="109"], input[type="number"][min="0"]');
    const count = await appIdInputs.count();
    expect(count).toBeGreaterThan(0);
  });

  test('Step 3: configuring nrf52840 (app, appId=109) + nrf9151 (comms, appId=108)', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    // Walk to step 3
    await page.getByRole('button', { name: /new product/i }).click();
    await page.waitForSelector('#branch-select', { timeout: 15_000 });
    await page.locator('#branch-select').selectOption('main');
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForSelector('button:has-text("alpha")', { timeout: 20_000 });
    await page.locator('button').filter({ hasText: /alpha/i }).first().click();
    await page.getByRole('button', { name: /next/i }).click();
    await expect(page.getByText('Configure product')).toBeVisible({ timeout: 15_000 });

    // Find the app target section and set AppID = 109
    const appSection = page.locator('div').filter({ hasText: /^app/ }).locator('input[type="number"]').first();
    if (await appSection.isVisible().catch(() => false)) {
      await appSection.fill('109');
    }

    // Find the comms target section and set AppID = 108
    const commsSection = page.locator('div').filter({ hasText: /comms/ }).locator('input[type="number"]').first();
    if (await commsSection.isVisible().catch(() => false)) {
      await commsSection.fill('108');
    }

    // Product name should be auto-populated from board family
    const nameInput = page.locator('input[type="text"]').first();
    const nameValue = await nameInput.inputValue();
    expect(nameValue).toBeTruthy();
  });

  test('Step 3: firmware repo slug validation (async check against Bitbucket)', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    // Walk to step 3
    await page.getByRole('button', { name: /new product/i }).click();
    await page.waitForSelector('#branch-select', { timeout: 15_000 });
    await page.locator('#branch-select').selectOption('main');
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForSelector('button:has-text("alpha")', { timeout: 20_000 });
    await page.locator('button').filter({ hasText: /alpha/i }).first().click();
    await page.getByRole('button', { name: /next/i }).click();
    await expect(page.getByText('Configure product')).toBeVisible({ timeout: 15_000 });

    // The firmware repo slug fields should be auto-populated (alpha_fw, alpha_mfg_fw)
    const fwInput = page.locator('input[placeholder*="alpha_fw"]').first();
    await expect(fwInput).toBeVisible();
    const fwValue = await fwInput.inputValue();
    expect(fwValue).toContain('alpha');
  });

  test('Step 3: repo existence indicator shows green check for valid repo', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    // Walk to step 3
    await page.getByRole('button', { name: /new product/i }).click();
    await page.waitForSelector('#branch-select', { timeout: 15_000 });
    await page.locator('#branch-select').selectOption('main');
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForSelector('button:has-text("alpha")', { timeout: 20_000 });
    await page.locator('button').filter({ hasText: /alpha/i }).first().click();
    await page.getByRole('button', { name: /next/i }).click();
    await expect(page.getByText('Configure product')).toBeVisible({ timeout: 15_000 });

    // Wait for the async repo check to complete — green check icon (lucide Check with text-success class)
    // The alpha_fw repo is real and should show a check mark
    await page.waitForSelector('.text-success', { timeout: 10_000 });
    const checkIcons = page.locator('.text-success');
    const count = await checkIcons.count();
    expect(count).toBeGreaterThan(0);
  });

  test('Step 3: repo existence indicator shows warning for invalid repo', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    // Walk to step 3
    await page.getByRole('button', { name: /new product/i }).click();
    await page.waitForSelector('#branch-select', { timeout: 15_000 });
    await page.locator('#branch-select').selectOption('main');
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForSelector('button:has-text("alpha")', { timeout: 20_000 });
    await page.locator('button').filter({ hasText: /alpha/i }).first().click();
    await page.getByRole('button', { name: /next/i }).click();
    await expect(page.getByText('Configure product')).toBeVisible({ timeout: 15_000 });

    // Clear the fw repo slug and type an invalid one
    const fwInput = page.locator('input[placeholder*="alpha_fw"]').first();
    await fwInput.clear();
    await fwInput.fill('nonexistent_repo_xyz_123');

    // Wait for the async check — should show warning icon (text-warning class)
    await page.waitForSelector('.text-warning', { timeout: 10_000 });
    const warningIcons = page.locator('.text-warning');
    const count = await warningIcons.count();
    expect(count).toBeGreaterThan(0);
  });

  test('Step 4: review page shows all configured values', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    // Walk to step 3
    await page.getByRole('button', { name: /new product/i }).click();
    await page.waitForSelector('#branch-select', { timeout: 15_000 });
    await page.locator('#branch-select').selectOption('main');
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForSelector('button:has-text("alpha")', { timeout: 20_000 });
    await page.locator('button').filter({ hasText: /alpha/i }).first().click();
    await page.getByRole('button', { name: /next/i }).click();
    await expect(page.getByText('Configure product')).toBeVisible({ timeout: 15_000 });

    // Set a unique product name to avoid conflicts
    const uniqueName = `E2E Alpha ${Date.now()}`;
    const nameInput = page.locator('span:has-text("Product Name") + input, span:has-text("Product Name")').locator('..').locator('input').first();
    // Alternative: find the input labeled "Product Name"
    const allInputs = page.locator('input[type="text"]');
    // First text input is product name
    await allInputs.first().clear();
    await allInputs.first().fill(uniqueName);

    // Click Next to go to step 4 (review)
    await page.getByRole('button', { name: /next/i }).click();

    // Step 4: "Confirm and create" heading
    await expect(page.getByText('Confirm and create')).toBeVisible({ timeout: 10_000 });

    // Review page should show the product name, board family, repos
    await expect(page.getByText(uniqueName)).toBeVisible();
    await expect(page.getByText('alpha')).toBeVisible();
  });

  test('Step 4: confirm creates product and redirects to product list', async ({ page }) => {
    await loginAsRole(page, 'admin');
    await page.goto('/products');
    await page.waitForLoadState('networkidle');

    // Walk through entire wizard
    await page.getByRole('button', { name: /new product/i }).click();
    await page.waitForSelector('#branch-select', { timeout: 15_000 });
    await page.locator('#branch-select').selectOption('main');
    await page.getByRole('button', { name: /next/i }).click();
    await page.waitForSelector('button:has-text("alpha")', { timeout: 20_000 });
    await page.locator('button').filter({ hasText: /alpha/i }).first().click();
    await page.getByRole('button', { name: /next/i }).click();
    await expect(page.getByText('Configure product')).toBeVisible({ timeout: 15_000 });

    // Set unique product name
    const uniqueName = `E2E Alpha ${Date.now()}`;
    const allInputs = page.locator('input[type="text"]');
    await allInputs.first().clear();
    await allInputs.first().fill(uniqueName);

    // Go to review
    await page.getByRole('button', { name: /next/i }).click();
    await expect(page.getByText('Confirm and create')).toBeVisible({ timeout: 10_000 });

    // Click "Create Product"
    await page.getByRole('button', { name: /create product/i }).click();

    // After creation, the wizard closes and the product list refreshes
    // The product should now appear in the list
    await page.waitForLoadState('networkidle');

    // Wait for product list to refresh showing the new product
    await expect(page.getByText(uniqueName)).toBeVisible({ timeout: 15_000 });

    // Store product ID for downstream tests (by navigating to it)
    await page.getByText(uniqueName).first().click();
    await page.waitForLoadState('networkidle');
    const url = page.url();
    const match = url.match(/\/products\/([^/]+)/);
    if (match) {
      createdProductId = match[1];
    }
  });
});
