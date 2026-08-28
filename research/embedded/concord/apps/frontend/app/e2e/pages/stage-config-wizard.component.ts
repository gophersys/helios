import type { Page } from '@playwright/test';

/**
 * Stage configuration wizard component.
 * Used to configure validation/build stages for a product.
 */
export class StageConfigWizard {
  constructor(private page: Page) {}

  /** Select a hardware revision for the stage. */
  async selectRevision(rev: string): Promise<void> {
    const select = this.page.getByLabel(/revision/i).first();
    await select.selectOption({ label: rev });
  }

  /** Set the branch to watch for triggers. */
  async setWatchBranch(branch: string): Promise<void> {
    const input = this.page.getByLabel(/branch|watch/i).first();
    await input.fill(branch);
  }

  /**
   * Set the trigger types for the stage.
   * D19: Trigger type is "schedule" not "cron".
   */
  async setTriggerTypes(types: string[]): Promise<void> {
    for (const type of types) {
      const checkbox = this.page.getByLabel(new RegExp(type, 'i'));
      if (await checkbox.isVisible()) {
        await checkbox.check();
      }
    }
  }

  /** Edit the recipe/build script YAML. */
  async editRecipe(yaml: string): Promise<void> {
    const editor = this.page.locator('[data-testid="recipe-editor"], .cm-editor, textarea').first();
    await editor.click();
    await editor.fill(yaml);
  }

  /** Save the stage configuration. */
  async save(): Promise<void> {
    await this.page
      .getByRole('button', { name: /save|apply/i })
      .first()
      .click();
    await this.page.waitForLoadState('networkidle');
  }
}
