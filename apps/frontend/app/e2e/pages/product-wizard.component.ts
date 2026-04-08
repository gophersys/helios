import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';

interface RevisionConfig {
  name: string;
  description?: string;
}

/**
 * Product creation wizard component.
 * Walks through the multi-step product creation flow.
 */
export class ProductWizardComponent {
  constructor(private page: Page) {}

  /** Fill in the product name field. */
  async setName(name: string): Promise<void> {
    await this.page.getByLabel(/name/i).first().fill(name);
  }

  /** Fill in the product description. */
  async setDescription(description: string): Promise<void> {
    const desc = this.page.getByLabel(/description/i).first();
    if (await desc.isVisible()) {
      await desc.fill(description);
    }
  }

  /** Select a Bitbucket branch from the dropdown. */
  async selectBranch(name: string): Promise<void> {
    const select = this.page.getByLabel(/branch/i).first();
    if (await select.isVisible()) {
      await select.selectOption({ label: name });
    }
  }

  /** Select a board family. */
  async selectBoard(family: string): Promise<void> {
    const select = this.page.getByLabel(/board|family/i).first();
    if (await select.isVisible()) {
      await select.selectOption({ label: family });
    }
  }

  /** Configure a hardware revision. */
  async configureRevision(config: RevisionConfig): Promise<void> {
    const revInput = this.page.getByLabel(/revision/i).first();
    if (await revInput.isVisible()) {
      await revInput.fill(config.name);
    }
  }

  /** Click the next/continue button. */
  async next(): Promise<void> {
    await this.page
      .getByRole('button', { name: /next|continue/i })
      .first()
      .click();
    await this.page.waitForTimeout(300);
  }

  /** Click the confirm/create button to finalize. */
  async confirm(): Promise<void> {
    await this.page
      .getByRole('button', { name: /create|confirm|save/i })
      .first()
      .click();
    await this.page.waitForLoadState('networkidle');
  }
}
