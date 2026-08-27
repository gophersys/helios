import { expect } from '@playwright/test';
import { BasePage } from './base.page';

/**
 * Validation run detail page object.
 */
export class ValidationRunPage extends BasePage {
  protected get path() {
    return '/validation'; // Dynamic: /validation/[id]
  }

  /** Assert the run has the expected status. */
  async expectStatus(status: string): Promise<void> {
    await expect(
      this.page.getByText(status, { exact: false }).first(),
    ).toBeVisible();
  }

  /** Assert the number of test results displayed. */
  async expectTestCount(count: number): Promise<void> {
    const tests = this.page.locator('[data-testid="test-result"]');
    await expect(tests).toHaveCount(count);
  }

  /**
   * Wait for the run to reach a terminal state.
   * Polls the page until the status changes or timeout is reached.
   */
  async waitForCompletion(timeout = 300_000): Promise<void> {
    const terminalStatuses = /PASSED|FAILED|ERROR|COMPLETE|CANCELLED/i;
    await expect(
      this.page.locator('[data-testid="run-status"], [data-testid="status-badge"]').first(),
    ).toHaveText(terminalStatuses, { timeout });
  }

  /** Get the result of a specific test by name. */
  async getTestResult(name: string): Promise<string> {
    const row = this.page.locator('[data-testid="test-result"]').filter({ hasText: name });
    const badge = row.locator('[data-testid="status-badge"]').first();
    return (await badge.textContent()) ?? '';
  }
}
