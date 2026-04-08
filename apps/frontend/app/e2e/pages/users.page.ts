import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './base.page';

interface UserConfig {
  email: string;
  name: string;
  role: string;
  permissionSetId?: string;
}

interface UserChanges {
  name?: string;
  role?: string;
  permissionSetId?: string;
}

/**
 * Users management page object.
 * Supports tabs: Users, Permission Sets.
 */
export class UsersPage extends BasePage {
  protected get path() {
    return '/users';
  }

  /** Switch between tabs (e.g. 'Users', 'Permission Sets'). */
  async switchTab(tab: string): Promise<void> {
    // Tab buttons are plain <button> elements in the tab bar (not role="tab")
    const tabBtn = this.page
      .locator('button')
      .filter({ hasText: new RegExp(`^${tab}$`) })
      .first();
    await tabBtn.click();
    await this.page.waitForTimeout(500);
  }

  /** Create a new user via the UI. */
  async createUser(config: UserConfig): Promise<void> {
    await this.page.getByRole('button', { name: /create|add|invite/i }).first().click();
    await this.page.getByLabel(/email/i).first().fill(config.email);
    await this.page.getByLabel(/name/i).first().fill(config.name);

    const roleSelect = this.page.getByLabel(/role/i).first();
    if (await roleSelect.isVisible()) {
      await roleSelect.selectOption({ label: config.role });
    }

    await this.page
      .getByRole('button', { name: /create|save|confirm/i })
      .first()
      .click();
    await this.page.waitForLoadState('networkidle');
  }

  /** Edit an existing user. */
  async editUser(email: string, changes: UserChanges): Promise<void> {
    const row = this.page.locator('tr, [data-testid="user-row"]').filter({ hasText: email });
    await row.getByRole('button', { name: /edit/i }).click();

    if (changes.name) {
      await this.page.getByLabel(/name/i).first().fill(changes.name);
    }
    if (changes.role) {
      await this.page.getByLabel(/role/i).first().selectOption({ label: changes.role });
    }

    await this.page
      .getByRole('button', { name: /save|update/i })
      .first()
      .click();
    await this.page.waitForLoadState('networkidle');
  }

  /** Deactivate a user by email. */
  async deactivateUser(email: string): Promise<void> {
    const row = this.page.locator('tr, [data-testid="user-row"]').filter({ hasText: email });
    await row.getByRole('button', { name: /deactivate|disable/i }).click();
    await this.page.getByRole('button', { name: /confirm|yes/i }).click();
    await this.page.waitForTimeout(500);
  }
}
