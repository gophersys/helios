import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './base.page';

interface SessionConfig {
  productId?: string;
  fixtureId?: string;
}

/**
 * Manufacturing page object.
 */
export class ManufacturingPage extends BasePage {
  protected get path() {
    return '/manufacturing';
  }

  /** Assert the manufacturing run list shows exactly `count` items. */
  async expectRunList(count: number): Promise<void> {
    const rows = this.page.locator('[data-testid="mfg-row"], [data-testid="mfg-card"]');
    if (count > 0) {
      await rows.first().waitFor({ timeout: 10_000 });
    }
    await expect(rows).toHaveCount(count);
  }

  /** Trigger a new manufacturing session via the UI. */
  async triggerSession(config: SessionConfig): Promise<void> {
    await this.page
      .getByRole('button', { name: /start|trigger|new/i })
      .first()
      .click();
    await this.page.waitForLoadState('networkidle');
  }
}
