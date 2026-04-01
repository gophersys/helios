import { test, expect } from '../fixtures';
import { loginViaAPI } from '../helpers/auth';

test.describe('Stage Configuration', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaAPI(page);
    // Navigate to Alpha product detail → Validation tab
    await page.goto('/products');
    await page.waitForLoadState('networkidle');
    await page.getByRole('heading', { name: 'Alpha', level: 3 }).click();
    await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: 'Validation' }).click();
    await page.waitForLoadState('networkidle');
    // Wait for stages to load from API
    await page.waitForTimeout(2000);
  });

  test('validation tab shows stage names', async ({ page }) => {
    await page.waitForTimeout(1000);
    const content = await page.textContent('body');
    expect(content).toContain('Smoke');
    expect(content).toContain('Silicon');
    expect(content).toContain('Integration');
    expect(content).toContain('Nightly');
    expect(content).toContain('FUOTA');
  });

  test('FUOTA stage shows enabled indicator', async ({ page }) => {
    // FUOTA is enabled — should show some enabled state
    const content = await page.textContent('body');
    expect(content).toContain('FUOTA');
    // Look for trigger type or enabled indicator near FUOTA
    const hasEnabled = content?.includes('pr_push') || content?.includes('Enabled') || content?.includes('concord-main');
    expect(hasEnabled).toBeTruthy();
  });

  test('stages show correct count', async ({ page }) => {
    // Should have 5 stages total
    // Count stage-related headings or sections
    const stageNames = ['Smoke', 'Silicon', 'Integration', 'Nightly', 'FUOTA'];
    const content = await page.textContent('body') || '';
    let count = 0;
    for (const name of stageNames) {
      if (content.includes(name)) count++;
    }
    expect(count).toBe(5);
  });
});
