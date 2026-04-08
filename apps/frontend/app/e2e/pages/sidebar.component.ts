import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';

/**
 * Sidebar navigation component.
 * Handles primary nav, expandable Admin/System sections, and View As role switching.
 */
export class SidebarComponent {
  constructor(private page: Page) {}

  private get nav() {
    return this.page.locator('nav');
  }

  /** Assert that the listed items are visible in the sidebar. */
  async expectItems(items: string[]): Promise<void> {
    for (const label of items) {
      await expect(this.nav.getByText(label, { exact: true })).toBeVisible();
    }
  }

  /** Assert that the listed items are NOT visible. */
  async expectHidden(items: string[]): Promise<void> {
    for (const label of items) {
      await expect(this.nav.getByText(label, { exact: true })).not.toBeVisible();
    }
  }

  /** Click a sidebar nav item to navigate. */
  async navigateTo(item: string): Promise<void> {
    await this.nav.getByText(item, { exact: true }).click();
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Expand a collapsible section (Admin or System).
   * D15: These are behind expandable toggle buttons that must be clicked.
   */
  async expandSection(section: 'Admin' | 'System'): Promise<void> {
    const btn = this.page.locator('button').filter({ hasText: section });
    await btn.click();
    // Wait for the expand animation
    await this.page.waitForTimeout(300);
  }

  /** Collapse a section if it is currently expanded. */
  async collapseSection(section: 'Admin' | 'System'): Promise<void> {
    await this.expandSection(section); // toggle
  }

  /**
   * Use the "View As" role switcher (Admin/Maintainer only).
   * Sets the sidebar to show navigation as the specified role would see it.
   */
  async viewAsRole(role: 'Maintainer' | 'Developer' | 'Operator' | null): Promise<void> {
    // Open the view-as dropdown
    const viewAsBtn = this.page.locator('button').filter({ hasText: /view as/i });
    if (await viewAsBtn.isVisible()) {
      await viewAsBtn.click();
      await this.page.waitForTimeout(200);
    }

    if (role === null) {
      // Reset to own view
      await this.page.getByText('Your View', { exact: true }).click();
    } else {
      await this.page.getByText(role, { exact: true }).click();
    }
    await this.page.waitForTimeout(300);
  }
}
