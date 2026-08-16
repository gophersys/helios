import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { SidebarComponent } from './sidebar.component';

/**
 * Base class for all page objects in the E2E story suite.
 * Provides common navigation, waiting, and assertion utilities.
 */
export abstract class BasePage {
  constructor(protected page: Page) {}

  /** The route path this page lives at (e.g. '/products'). Override in subclasses. */
  protected abstract get path(): string;

  /** Navigate to the page and wait for it to settle. */
  async goto(): Promise<void> {
    await this.page.goto(this.path);
    await this.waitForLoad();
  }

  /** Wait for the page to finish loading (network idle + any loading indicators gone). */
  async waitForLoad(): Promise<void> {
    await this.page.waitForLoadState('networkidle');
    // Wait for any skeleton/loader to disappear
    const loader = this.page.locator('[data-testid="page-loader"], .animate-pulse').first();
    await loader.waitFor({ state: 'hidden', timeout: 15_000 }).catch(() => {
      // Loader might not exist at all, which is fine
    });
  }

  /** Assert the page is visible (navigated to the correct URL). */
  async expectVisible(): Promise<void> {
    await expect(this.page).toHaveURL(new RegExp(this.path));
  }

  /** Assert the page title heading contains the given text. */
  async expectPageTitle(title: string): Promise<void> {
    await expect(
      this.page.getByRole('heading', { name: title }).first(),
    ).toBeVisible();
  }

  /** Get the sidebar component for interaction. */
  sidebar(): SidebarComponent {
    return new SidebarComponent(this.page);
  }

  /** Get a generic locator scoped to the main content area. */
  protected content(): Locator {
    return this.page.locator('main, [role="main"], #main-content').first();
  }
}
