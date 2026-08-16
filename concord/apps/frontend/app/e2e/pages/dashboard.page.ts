import type { Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './base.page';

/**
 * Dashboard / home page object.
 */
export class DashboardPage extends BasePage {
  protected get path() {
    return '/';
  }

  /** Assert that exactly `count` fixture cards are visible. */
  async expectFixtureCards(count: number): Promise<void> {
    const cards = this.page.locator('[data-testid="fixture-card"]');
    await expect(cards).toHaveCount(count);
  }

  /** Toggle between dashboard display modes if available. */
  async toggleMode(mode: string): Promise<void> {
    const btn = this.page.getByRole('button', { name: new RegExp(mode, 'i') });
    if (await btn.isVisible()) {
      await btn.click();
      await this.page.waitForTimeout(300);
    }
  }

  /** Get a fixture card by name. */
  getFixtureCard(name: string): Locator {
    return this.page
      .locator('[data-testid="fixture-card"]')
      .filter({ hasText: name });
  }
}
