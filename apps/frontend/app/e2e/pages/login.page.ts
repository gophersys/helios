import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './base.page';

type Role = 'admin' | 'maintainer' | 'developer' | 'operator';

const ROLE_EMAILS: Record<Role, string> = {
  admin: 'admin@concord.dev',
  maintainer: 'maintainer@concord.dev',
  developer: 'developer@concord.dev',
  operator: 'operator@concord.dev',
};

/**
 * Login page object.
 * In dev mode, the login page shows role-based buttons instead of email/password.
 */
export class LoginPage extends BasePage {
  protected get path() {
    return '/login';
  }

  /** Click the dev-mode role button for the given role. */
  async loginAsRole(role: Role): Promise<void> {
    await this.goto();
    const roleLabel = role.charAt(0).toUpperCase() + role.slice(1);
    const btn = this.page
      .locator('button')
      .filter({ hasText: new RegExp(`^${roleLabel}$`, 'i') });
    await btn.click();
    await this.page.waitForURL((url) => !url.pathname.includes('/login'), {
      timeout: 10_000,
    });
  }

  /** Login with email/password form (production mode). */
  async loginWithCredentials(email: string, password: string): Promise<void> {
    await this.goto();
    await this.page.getByPlaceholder('you@company.com').fill(email);
    await this.page.getByPlaceholder('Enter your password').fill(password);
    await this.page.getByRole('button', { name: /sign in/i }).click();
    await this.page.waitForURL((url) => !url.pathname.includes('/login'), {
      timeout: 10_000,
    });
  }

  /** Assert that all four role buttons are visible (dev mode). */
  async expectRoleButtons(): Promise<void> {
    for (const role of ['Admin', 'Maintainer', 'Developer', 'Operator']) {
      await expect(
        this.page.locator('button').filter({ hasText: new RegExp(`^${role}$`, 'i') }),
      ).toBeVisible();
    }
  }

  /** Assert the Concord branding is visible. */
  async expectBranding(): Promise<void> {
    await expect(this.page.getByText('Concord')).toBeVisible();
  }
}
