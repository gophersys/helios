import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';

interface PermissionSetConfig {
  name: string;
  description?: string;
  permissions?: string[];
}

interface PermissionSetChanges {
  name?: string;
  description?: string;
  permissions?: string[];
}

/**
 * Permission Sets tab component (within UsersPage).
 */
export class PermissionSetsTab {
  constructor(private page: Page) {}

  /** Create a new permission set. */
  async createSet(config: PermissionSetConfig): Promise<void> {
    await this.page.getByRole('button', { name: /create|add|new/i }).first().click();
    await this.page.getByLabel(/name/i).first().fill(config.name);

    if (config.description) {
      const desc = this.page.getByLabel(/description/i).first();
      if (await desc.isVisible()) {
        await desc.fill(config.description);
      }
    }

    if (config.permissions) {
      for (const perm of config.permissions) {
        const checkbox = this.page.getByLabel(new RegExp(perm, 'i'));
        if (await checkbox.isVisible()) {
          await checkbox.check();
        }
      }
    }

    await this.page
      .getByRole('button', { name: /create|save|confirm/i })
      .first()
      .click();
    await this.page.waitForLoadState('networkidle');
  }

  /** Edit an existing permission set. */
  async editSet(name: string, changes: PermissionSetChanges): Promise<void> {
    const row = this.page.locator('tr, [data-testid="permset-row"]').filter({ hasText: name });
    await row.getByRole('button', { name: /edit/i }).click();

    if (changes.name) {
      await this.page.getByLabel(/name/i).first().fill(changes.name);
    }
    if (changes.description) {
      await this.page.getByLabel(/description/i).first().fill(changes.description);
    }

    await this.page
      .getByRole('button', { name: /save|update/i })
      .first()
      .click();
    await this.page.waitForLoadState('networkidle');
  }

  /** Delete a permission set by name. */
  async deleteSet(name: string): Promise<void> {
    const row = this.page.locator('tr, [data-testid="permset-row"]').filter({ hasText: name });
    await row.getByRole('button', { name: /delete|remove/i }).click();
    await this.page.getByRole('button', { name: /confirm|delete|yes/i }).click();
    await this.page.waitForTimeout(500);
  }
}
