import { expect } from '@playwright/test';
import { BasePage } from './base.page';

/**
 * Builds list page object.
 */
export class BuildsPage extends BasePage {
  protected get path() {
    return '/builds';
  }

  /** Assert the build list shows exactly `count` items. */
  async expectBuildList(count: number): Promise<void> {
    const rows = this.page.locator('[data-testid="build-row"], [data-testid="build-card"]');
    if (count > 0) {
      await rows.first().waitFor({ timeout: 15_000 });
    }
    await expect(rows).toHaveCount(count);
  }

  /** Filter builds by status (e.g. 'RUNNING', 'SUCCESS', 'FAILED'). */
  async filterByStatus(status: string): Promise<void> {
    const filter = this.page.getByRole('button', { name: new RegExp(status, 'i') })
      .or(this.page.getByLabel(/status/i));
    await filter.first().click();
    await this.page.waitForTimeout(500);
  }

  /** Filter builds by stage. */
  async filterByStage(stage: string): Promise<void> {
    const filter = this.page.getByRole('button', { name: new RegExp(stage, 'i') })
      .or(this.page.getByLabel(/stage/i));
    await filter.first().click();
    await this.page.waitForTimeout(500);
  }

  /** Click a build to navigate to its detail page. */
  async openBuild(id: string): Promise<void> {
    await this.page.locator(`[href*="${id}"]`).first().click();
    await this.page.waitForLoadState('networkidle');
  }
}
