import { expect } from '@playwright/test';
import { BasePage } from './base.page';

/**
 * Validation runs list page object.
 */
export class ValidationPage extends BasePage {
  protected get path() {
    return '/validation';
  }

  /** Assert the validation run list shows exactly `count` items. */
  async expectRunList(count: number): Promise<void> {
    const rows = this.page.locator('[data-testid="validation-row"], [data-testid="validation-card"]');
    if (count > 0) {
      await rows.first().waitFor({ timeout: 15_000 });
    }
    await expect(rows).toHaveCount(count);
  }

  /** Filter runs by status. */
  async filterByStatus(status: string): Promise<void> {
    const filter = this.page.getByRole('button', { name: new RegExp(status, 'i') })
      .or(this.page.getByLabel(/status/i));
    await filter.first().click();
    await this.page.waitForTimeout(500);
  }

  /** Filter runs by stage. */
  async filterByStage(stage: string): Promise<void> {
    const filter = this.page.getByRole('button', { name: new RegExp(stage, 'i') })
      .or(this.page.getByLabel(/stage/i));
    await filter.first().click();
    await this.page.waitForTimeout(500);
  }

  /** Click a validation run to navigate to its detail page. */
  async openRun(id: string): Promise<void> {
    await this.page.locator(`[href*="${id}"]`).first().click();
    await this.page.waitForLoadState('networkidle');
  }
}
