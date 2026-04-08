import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';

/**
 * Sidebar navigation component.
 * Handles primary nav, expandable Admin/System sections, and View As role switching.
 */
export class SidebarComponent {
  constructor(private page: Page) {}

  /** The full sidebar aside element (contains nav + expanded sections). */
  private get sidebar() {
    return this.page.locator('aside');
  }

  /** Assert that the listed items are visible in the sidebar. */
  async expectItems(items: string[]): Promise<void> {
    for (const label of items) {
      await expect(
        this.sidebar.getByRole('link', { name: label }),
      ).toBeVisible();
    }
  }

  /** Assert that the listed items are NOT visible. */
  async expectHidden(items: string[]): Promise<void> {
    for (const label of items) {
      await expect(
        this.sidebar.getByRole('link', { name: label }),
      ).not.toBeVisible();
    }
  }

  /** Click a sidebar nav item to navigate. */
  async navigateTo(item: string): Promise<void> {
    await this.sidebar.getByRole('link', { name: item }).click();
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Expand a collapsible section (Admin or System).
   * D15: These are behind expandable toggle buttons that must be clicked.
   */
  async expandSection(section: 'Admin' | 'System'): Promise<void> {
    const btn = this.sidebar.getByRole('button', { name: section, exact: true });
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
    // Open the view-as dropdown — button text is "View as..." or "Viewing as <Role>"
    const viewAsBtn = this.page.locator('button').filter({ hasText: /view(?:ing)? as/i });
    await viewAsBtn.waitFor({ state: 'visible', timeout: 10_000 });
    await viewAsBtn.click();
    await this.page.waitForTimeout(300);

    if (role === null) {
      // Reset to own view — the label includes the user's role in parens, e.g. "Your View (Admin)"
      // Clicking triggers window.location.reload(), so wait for navigation
      await Promise.all([
        this.page.waitForLoadState('load'),
        this.page.getByText(/Your View/).click(),
      ]);
    } else {
      // Clicking triggers window.location.reload(), so wait for navigation
      await Promise.all([
        this.page.waitForLoadState('load'),
        this.page.getByText(role, { exact: true }).click(),
      ]);
    }
    await this.page.waitForLoadState('networkidle');
  }
}
