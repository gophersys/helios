import type { Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './base.page';

/**
 * Products list page object.
 */
export class ProductsPage extends BasePage {
  protected get path() {
    return '/products';
  }

  /** Assert the product list shows exactly `count` items. */
  async expectProductList(count: number): Promise<void> {
    // Products are displayed as cards or list items
    const items = this.page.locator('[data-testid="product-card"], [data-testid="product-row"]');
    // Fallback: count links/cards within the product list area
    if ((await items.count()) === 0 && count > 0) {
      // Wait for them to appear
      await items.first().waitFor({ timeout: 10_000 });
    }
    await expect(items).toHaveCount(count);
  }

  /** Type into the search/filter input. */
  async searchProduct(name: string): Promise<void> {
    const input = this.page.getByPlaceholder(/search/i).first();
    await input.fill(name);
    await this.page.waitForTimeout(500); // debounce
  }

  /** Click the create product button to open the wizard. */
  async openCreateWizard(): Promise<void> {
    await this.page
      .getByRole('button', { name: /create|new|add/i })
      .first()
      .click();
  }

  /** Delete a product by clicking its delete action. */
  async deleteProduct(name: string): Promise<void> {
    const row = this.page.locator('[data-testid="product-card"], [data-testid="product-row"]').filter({ hasText: name });
    await row.getByRole('button', { name: /delete|remove/i }).click();
    // Confirm the deletion dialog
    await this.page.getByRole('button', { name: /confirm|delete|yes/i }).click();
    await this.page.waitForTimeout(500);
  }

  /** Click a product to navigate to its detail page. */
  async openProduct(name: string): Promise<void> {
    await this.page.getByText(name, { exact: false }).first().click();
    await this.page.waitForLoadState('networkidle');
  }
}
