import { expect, test } from '@playwright/test';

// k9s launch behaviour for the Clusters visibility canvas. "Open in k9s" must open a ttyd-served
// k9s session (:7682) scoped to the focused resource via k9s flags passed as ttyd ?arg= params:
// --context <clusterId>, -n <namespace>, -c <resource view>. Runs against the dev server; window.open
// is stubbed so the URL is asserted deterministically without needing the ttyd backend up for the
// unit-of-behaviour (the backend is verified separately, end-to-end).
const BASE = process.env.E2E_BASE_URL ?? 'http://localhost:5173';

test('Open in k9s launches a session scoped to the focused resource', async ({ page }) => {
  await page.addInitScript(() => {
    (window as unknown as { __opened: string[] }).__opened = [];
    window.open = ((u?: string | URL) => {
      (window as unknown as { __opened: string[] }).__opened.push(String(u));
      return null;
    }) as typeof window.open;
  });

  await page.goto(`${BASE}/clusters`);
  // Focus a node via the Inventory lens (a table — occlusion-free, unlike the Service Map canvas
  // whose toolbar overlays the top nodes). The Detail drawer + its k9s button are lens-agnostic
  // (they render off the shared focus state), so this exercises the same behaviour.
  await page.locator('.tab', { hasText: 'Inventory' }).click();
  await page.locator('td.nm').first().waitFor({ timeout: 15_000 });
  await page.locator('td.nm').first().click();
  await expect(page.locator('.drawer')).toBeVisible();

  await page.locator('button.k9s').click();

  const opened: string[] = await page.evaluate(
    () => (window as unknown as { __opened: string[] }).__opened,
  );
  expect(opened.length).toBe(1);
  const url = opened[0];
  expect(url).toContain(':7682/');
  expect(url).toContain('arg=--context');
  expect(url).toContain('arg=-n'); // namespace-scoped
  expect(url).toContain('arg=-c'); // resource view
});
