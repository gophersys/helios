// Connectors settings-section screenshot sweep (Brief B) — drives the REAL vite dev-serve (started by
// screenshots-connectors.sh) and captures the Connectors section states to /tmp/ui-audit/connectors/.
// Real-flow over the dev-serve's in-memory ConnectorStore (no page.route stubs): the add flow POSTs a
// real connector so the list/fingerprint shots show a real row. Both themes for the sweep-diff.
//
//   connectors-empty  — the empty product surface (headline + available offer)
//   connectors-add    — the nested add dialog (pick provider · paste · scope)
//   connectors-list   — a connected row with its write-only fingerprint display
//   connectors-dark   — the list in dark mode (retheme proof)
import { chromium } from '@playwright/test';

const BASE = process.env.E2E_BASE_URL;
if (!BASE) throw new Error('E2E_BASE_URL is required');
const OUT = '/tmp/ui-audit/connectors';

/** Seed the theme the REAL way (the app.html bootstrap + themePreference store read this key). */
async function setTheme(page, mode) {
  await page.addInitScript((m) => {
    try {
      localStorage.setItem('eden-theme', m);
    } catch {
      /* private mode — the store falls back to system */
    }
  }, mode);
}

/** Open Settings → Connectors from the projects dashboard (the sidebar user affordance + the rail). */
async function openConnectors(page, base) {
  await page.goto(`${base}/projects`, { waitUntil: 'networkidle' });
  await page.getByTestId('projects-dashboard').waitFor({ state: 'visible', timeout: 15000 });
  await page.getByTestId('user-settings-open').click();
  await page.getByTestId('settings-surface').waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.eden-settings-surface-rail-item[data-section="connectors"]').click();
  await page.getByTestId('settings-connectors').waitFor({ state: 'visible', timeout: 15000 });
}

async function shootMode(browser, mode, base) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await setTheme(page, mode);
  await openConnectors(page, base);

  if (mode === 'light') {
    // 1) EMPTY — the product surface.
    await page
      .getByTestId('settings-connectors-empty')
      .waitFor({ state: 'visible', timeout: 10000 });
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${OUT}/connectors-empty.png` });

    // 2) ADD — the nested dialog (pick · paste · scope).
    await page.getByTestId('settings-connector-add').click();
    await page
      .getByTestId('settings-connector-dialog')
      .waitFor({ state: 'visible', timeout: 10000 });
    await page.getByTestId('settings-connector-kind').selectOption('claude-api');
    await page
      .getByTestId('settings-connector-credential')
      .locator('input[type="password"]')
      .fill('sk-ant-screenshot-demo-value-000');
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${OUT}/connectors-add.png` });

    // Save → a real connector row appears (real dev-serve).
    await page.getByTestId('settings-connector-save').click();
    await page
      .getByTestId('settings-connector-row')
      .first()
      .waitFor({ state: 'visible', timeout: 10000 });
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${OUT}/connectors-list.png` });
  } else {
    // DARK — seed a couple of connectors so the dark list shot shows the write-only rows.
    for (const [kind, value] of [
      ['github', 'ghp_dark_demo_value_11111'],
      ['openrouter', 'or-dark-demo-value-22222'],
    ]) {
      await page.getByTestId('settings-connector-add').click();
      await page
        .getByTestId('settings-connector-dialog')
        .waitFor({ state: 'visible', timeout: 10000 });
      await page.getByTestId('settings-connector-kind').selectOption(kind);
      await page
        .getByTestId('settings-connector-credential')
        .locator('input[type="password"]')
        .fill(value);
      await page.getByTestId('settings-connector-save').click();
      await page.waitForTimeout(400);
    }
    await page
      .getByTestId('settings-connector-row')
      .first()
      .waitFor({ state: 'visible', timeout: 10000 });
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${OUT}/connectors-dark.png` });
  }

  await ctx.close();
}

const browser = await chromium.launch();
try {
  await shootMode(browser, 'light', BASE);
  await shootMode(browser, 'dark', BASE);
  console.log('connectors gallery written to', OUT);
} finally {
  await browser.close();
}
