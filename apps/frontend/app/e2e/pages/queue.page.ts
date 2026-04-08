import { expect } from '@playwright/test';
import { BasePage } from './base.page';

/**
 * Queue page object.
 * Shows queued builds/validation waiting for fixture assignment.
 */
export class QueuePage extends BasePage {
  protected get path() {
    return '/validation/queue';
  }

  /** Assert the queue shows exactly `count` entries. */
  async expectEntries(count: number): Promise<void> {
    const entries = this.page.locator('[data-testid="queue-entry"]');
    if (count > 0) {
      await entries.first().waitFor({ timeout: 10_000 });
    }
    await expect(entries).toHaveCount(count);
  }

  /** Assert a queue entry has the expected status. */
  async expectStatus(id: string, status: string): Promise<void> {
    const entry = this.page.locator('[data-testid="queue-entry"]').filter({ hasText: id });
    await expect(entry.getByText(status, { exact: false })).toBeVisible();
  }

  /** Cancel a queue entry. */
  async cancelEntry(id: string): Promise<void> {
    const entry = this.page.locator('[data-testid="queue-entry"]').filter({ hasText: id });
    await entry.getByRole('button', { name: /cancel/i }).click();
    await this.page.waitForTimeout(500);
  }

  /** Promote a queue entry (move it up in priority). */
  async promoteEntry(id: string): Promise<void> {
    const entry = this.page.locator('[data-testid="queue-entry"]').filter({ hasText: id });
    await entry.getByRole('button', { name: /promote|priority/i }).click();
    await this.page.waitForTimeout(500);
  }
}
