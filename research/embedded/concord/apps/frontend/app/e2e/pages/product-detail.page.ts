import { expect } from '@playwright/test';
import { BasePage } from './base.page';

/**
 * Product detail page object.
 * Supports tabbed navigation (Overview, Stages, Builds, etc.).
 */
export class ProductDetailPage extends BasePage {
  protected get path() {
    return '/products'; // Dynamic — actual URL is /products/[id]
  }

  /** Switch to a named tab (e.g. 'Overview', 'Stages', 'Builds'). */
  async switchTab(tab: string): Promise<void> {
    await this.page
      .getByRole('tab', { name: new RegExp(tab, 'i') })
      .or(this.page.getByText(tab, { exact: true }))
      .first()
      .click();
    await this.page.waitForTimeout(300);
  }

  /** Assert a specific tab is currently active/visible. */
  async expectTab(tab: string): Promise<void> {
    const tabEl = this.page
      .getByRole('tab', { name: new RegExp(tab, 'i') })
      .or(this.page.getByText(tab, { exact: true }))
      .first();
    await expect(tabEl).toBeVisible();
  }

  /** Edit an inline field by label. */
  async editField(field: string, value: string): Promise<void> {
    const label = this.page.getByText(field);
    const container = label.locator('..');
    const input = container.locator('input, textarea').first();

    // If there is an edit button, click it first
    const editBtn = container.getByRole('button', { name: /edit/i });
    if (await editBtn.isVisible({ timeout: 1_000 }).catch(() => false)) {
      await editBtn.click();
    }

    await input.fill(value);
  }

  /** Save edits (click Save button). */
  async saveEdits(): Promise<void> {
    await this.page
      .getByRole('button', { name: /save/i })
      .first()
      .click();
    await this.page.waitForTimeout(500);
  }
}
