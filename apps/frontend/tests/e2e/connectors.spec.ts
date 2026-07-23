import { expect, test, type Page } from '@playwright/test';

// The CONNECTORS settings-section E2E (connectors design §3, Brief B) — a REAL, full-stack Playwright
// journey against the agentgateway dev-serve over real REST (no mocked fetch for the happy path). The
// dev-serve's in-memory ConnectorStore (internal/devserve/connector_store.go) backs the section, so
// this drives the REAL create → save → list → delete flow — the same real-vs-fake mirror the Settings
// → Agents E2E uses. NOTHING is page.route-stubbed on the happy path; the fault arm (the value-never-
// echoed grep) inspects the REAL wire traffic.
//
// The write-only invariant is the load-bearing assertion (§2, §3.5 #2): after a credential is saved,
// the plaintext appears NOWHERE in the DOM — only the fingerprint/last-4 + account hint. There is no
// reveal affordance at all (honest chrome).
//
// Coverage (Brief B4): empty state → add flow (pick → paste → save) → row-appears → fingerprint-not-
// value → delete → back to empty.

// The known-needle plaintext. It must NEVER appear in the DOM or any read-side wire body after save.
const SECRET = 'sk-ant-DO-NOT-ECHO-abcdef0123456789';

/** Open the ONE Settings surface from the projects dashboard, deep-linked to the Connectors section
 *  (the sidebar user affordance opens the surface; the rail item selects the section — the SAME
 *  selectors the Settings → Agents E2E and the screenshot sweep use). */
async function openConnectorsSection(page: Page): Promise<void> {
  await page.goto('/projects');
  await expect(page.getByTestId('projects-dashboard')).toBeVisible();
  await page.getByTestId('user-settings-open').click();
  await expect(page.getByTestId('settings-surface')).toBeVisible();
  // Select the Connectors rail section (the primitive renders each section as a rail item).
  await page.locator('.eden-settings-surface-rail-item[data-section="connectors"]').click();
  await expect(page.getByTestId('settings-panel-connectors')).toBeVisible();
  await expect(page.getByTestId('settings-connectors')).toBeVisible();
}

test.describe('Settings → Connectors — the write-only user-secrets manager (real dev-serve)', () => {
  test('empty state → add a connector → fingerprint (never the value) → disconnect → empty again', async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));

    await openConnectorsSection(page);

    // ── 1 · EMPTY STATE — a product surface (P-D2): headline + the available-providers offer. ──
    await expect(page.getByTestId('settings-connectors-empty')).toBeVisible();
    await expect(page.getByText('No connectors yet')).toBeVisible();
    // The empty state OFFERS the working providers (never a void).
    await expect(page.getByText('Claude API')).toBeVisible();
    // No connector rows yet.
    await expect(page.getByTestId('settings-connector-row')).toHaveCount(0);

    // ── 2 · ADD FLOW — open the nested dialog, pick a provider, paste the credential, save. ──
    await page.getByTestId('settings-connector-add').click();
    await expect(page.getByTestId('settings-connector-dialog')).toBeVisible();

    // Pick the Claude API provider (only WORKING kinds render — P-D6).
    await page.getByTestId('settings-connector-kind').selectOption('claude-api');

    // The credential entry is a write-only password field (the value is masked in the DOM).
    const credential = page
      .getByTestId('settings-connector-credential')
      .locator('input[type="password"]');
    await expect(credential).toBeVisible();
    await credential.fill(SECRET);

    // Capture the REAL create POST — assert its body carries the value ONCE (the only path it travels),
    // and that the RESPONSE never echoes it back (fingerprint only).
    const createRequest = page.waitForRequest(
      (r) => r.url().includes('/connectors') && r.method() === 'POST',
    );
    const createResponse = page.waitForResponse(
      (r) => r.url().includes('/connectors') && r.request().method() === 'POST',
    );
    await page.getByTestId('settings-connector-save').click();

    const postBody = (await createRequest).postDataJSON() as {
      kind: string;
      value: string;
      scope: { level: string };
    };
    expect(postBody.kind).toBe('claude-api');
    expect(postBody.value).toBe(SECRET); // the plaintext crosses HERE, exactly once.
    expect(postBody.scope.level).toBe('org'); // org-scope DEFAULT (LOCKED call).

    // The create RESPONSE must NOT carry the value (only the §2 view: fingerprint + hint).
    const responseBody = await (await createResponse).text();
    expect(responseBody).not.toContain(SECRET);
    expect(responseBody).toContain('fingerprint');

    // ── 3 · ROW APPEARS — the connector renders with its write-only display. ──
    const row = page.getByTestId('settings-connector-row').filter({
      has: page.locator('[data-connector-kind="claude-api"]'),
    });
    await expect(row).toBeVisible();
    await expect(row).toHaveAttribute('data-connector-state', 'healthy');
    // The real-status Badge shows the WORD (survives grayscale, doc 17 §1).
    await expect(row.getByTestId('settings-connector-state')).toContainText('healthy');

    // ── 4 · FINGERPRINT, NEVER THE VALUE — the load-bearing write-only assertion. ──
    const fingerprint = row.getByTestId('settings-connector-fingerprint');
    await expect(fingerprint).toBeVisible();
    // The fingerprint is a masked short digest — it is NOT the plaintext.
    await expect(fingerprint).not.toContainText(SECRET);
    await expect(fingerprint).not.toContainText('sk-ant');
    // There is NO reveal affordance at all (honest chrome — the value cannot be shown).
    await expect(row.getByText('Reveal')).toHaveCount(0);
    await expect(row.getByText('Show')).toHaveCount(0);
    // The password value must not survive in ANY DOM node on the whole page after save.
    const domContainsSecret = await page.evaluate(
      (needle) => document.documentElement.innerHTML.includes(needle),
      SECRET,
    );
    expect(
      domContainsSecret,
      'the plaintext credential must never live in the DOM after save',
    ).toBe(false);

    // ── 5 · DISCONNECT — revoke the connector; the list returns to the empty product surface. ──
    await row.getByTestId('settings-connector-disconnect').click();
    await expect(page.getByTestId('settings-connector-row')).toHaveCount(0);
    await expect(page.getByTestId('settings-connectors-empty')).toBeVisible();

    expect(pageErrors, `uncaught exceptions: ${pageErrors.join(' | ')}`).toEqual([]);
  });

  test('a second connector kind (github) validates and lists alongside the first', async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));

    await openConnectorsSection(page);

    // Add a GitHub connector (org scope by default).
    await page.getByTestId('settings-connector-add').click();
    await expect(page.getByTestId('settings-connector-dialog')).toBeVisible();
    await page.getByTestId('settings-connector-kind').selectOption('github');
    await page
      .getByTestId('settings-connector-credential')
      .locator('input[type="password"]')
      .fill('ghp_a_github_token_value_9876543210');
    await page.getByTestId('settings-connector-save').click();

    const ghRow = page.getByTestId('settings-connector-row').filter({
      has: page.locator('[data-connector-kind="github"]'),
    });
    await expect(ghRow).toBeVisible();
    // Its write-only display shows a fingerprint (never the token).
    await expect(ghRow.getByTestId('settings-connector-fingerprint')).toBeVisible();
    await expect(ghRow.getByTestId('settings-connector-fingerprint')).not.toContainText('ghp_');
    // Manage + Disconnect are offered on a connected row (never Connect).
    await expect(ghRow.getByTestId('settings-connector-manage')).toBeVisible();
    await expect(ghRow.getByTestId('settings-connector-disconnect')).toBeVisible();

    // Clean up so this test leaves the dev-serve store as it found it (state is process-wide).
    await ghRow.getByTestId('settings-connector-disconnect').click();
    await expect(ghRow).toHaveCount(0);

    expect(pageErrors, `uncaught exceptions: ${pageErrors.join(' | ')}`).toEqual([]);
  });
});
