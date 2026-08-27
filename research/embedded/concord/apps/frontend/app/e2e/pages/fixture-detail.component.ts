import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';

/**
 * Fixture detail component.
 * Shows slots, node assignments, and fixture status.
 */
export class FixtureDetailComponent {
  constructor(private page: Page) {}

  /** Assert the fixture has exactly `count` slots. */
  async expectSlots(count: number): Promise<void> {
    const slots = this.page.locator('[data-testid="fixture-slot"]');
    await expect(slots).toHaveCount(count);
  }

  /** Assign a node to a slot by index. */
  async assignNode(slotIdx: number, nodeId: string): Promise<void> {
    const slots = this.page.locator('[data-testid="fixture-slot"]');
    const slot = slots.nth(slotIdx);
    const assignBtn = slot.getByRole('button', { name: /assign|select/i });
    await assignBtn.click();
    // Select the node from the dropdown/dialog
    await this.page.getByText(nodeId, { exact: false }).click();
    await this.page.waitForTimeout(500);
  }

  /** Assert the fixture has the expected status. */
  async expectStatus(status: string): Promise<void> {
    await expect(
      this.page.getByText(status, { exact: false }).first(),
    ).toBeVisible();
  }
}
