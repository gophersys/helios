import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './base.page';

interface DesignConfig {
  name: string;
  description?: string;
  boardRevisionId?: string;
}

interface FixtureConfig {
  name: string;
  designId?: string;
  type?: string;
}

/**
 * Fixtures page object.
 * Supports tabbed view: Fixtures, Designs, Nodes.
 */
export class FixturesPage extends BasePage {
  protected get path() {
    return '/fixtures';
  }

  /** Switch between tabs (e.g. 'Fixtures', 'Designs', 'Nodes'). */
  async switchTab(tab: string): Promise<void> {
    await this.page
      .getByRole('tab', { name: new RegExp(tab, 'i') })
      .or(this.page.getByText(tab, { exact: true }))
      .first()
      .click();
    await this.page.waitForTimeout(300);
  }

  /** Create a TestBed design via the UI. */
  async createDesign(config: DesignConfig): Promise<void> {
    await this.page.getByRole('button', { name: /create|new|add/i }).first().click();
    await this.page.getByLabel(/name/i).first().fill(config.name);
    if (config.description) {
      const desc = this.page.getByLabel(/description/i).first();
      if (await desc.isVisible()) {
        await desc.fill(config.description);
      }
    }
    await this.page
      .getByRole('button', { name: /create|save|confirm/i })
      .first()
      .click();
    await this.page.waitForLoadState('networkidle');
  }

  /** Create a fixture via the UI. */
  async createFixture(config: FixtureConfig): Promise<void> {
    await this.page.getByRole('button', { name: /create|new|add/i }).first().click();
    await this.page.getByLabel(/name/i).first().fill(config.name);
    if (config.type) {
      const typeSelect = this.page.getByLabel(/type/i).first();
      if (await typeSelect.isVisible()) {
        await typeSelect.selectOption({ label: config.type });
      }
    }
    await this.page
      .getByRole('button', { name: /create|save|confirm/i })
      .first()
      .click();
    await this.page.waitForLoadState('networkidle');
  }

  /** Delete a fixture by name. */
  async deleteFixture(name: string): Promise<void> {
    const row = this.page.locator('[data-testid="fixture-row"], [data-testid="fixture-card"]').filter({ hasText: name });
    await row.getByRole('button', { name: /delete|remove/i }).click();
    await this.page.getByRole('button', { name: /confirm|delete|yes/i }).click();
    await this.page.waitForTimeout(500);
  }
}
