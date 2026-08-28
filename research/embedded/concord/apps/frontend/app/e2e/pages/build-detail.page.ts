import { expect } from '@playwright/test';
import { BasePage } from './base.page';

/**
 * Build detail page object.
 */
export class BuildDetailPage extends BasePage {
  protected get path() {
    return '/builds'; // Dynamic: /builds/[id]
  }

  /** Assert the build has the expected status. */
  async expectStatus(status: string): Promise<void> {
    await expect(
      this.page.getByText(status, { exact: false }).first(),
    ).toBeVisible();
  }

  /** Assert the number of jobs in the build. */
  async expectJobs(count: number): Promise<void> {
    const jobs = this.page.locator('[data-testid="build-job"]');
    await expect(jobs).toHaveCount(count);
  }

  /** Click the download artifacts button. */
  async downloadArtifacts(): Promise<void> {
    await this.page
      .getByRole('button', { name: /download|artifact/i })
      .first()
      .click();
  }

  /** Get the status of a specific job by label. */
  async getJobStatus(label: string): Promise<string> {
    const job = this.page.locator('[data-testid="build-job"]').filter({ hasText: label });
    const badge = job.locator('[data-testid="status-badge"]').first();
    return (await badge.textContent()) ?? '';
  }
}
