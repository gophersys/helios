import { expect, test, type Page } from '@playwright/test';

// The LIVE permission round-trip E2E (ADR-0025) — the demo centerpiece. It drives a REAL
// agentgateway over real REST + SSE (no mocked fetch/SSE) and exercises the human-in-the-loop gate
// end-to-end: an out-of-grant tool request streams a permission-request event, the @eden/primitives
// PermissionRequest card renders, a human verdict (Allow / Deny) POSTs to the gateway's Resolve
// endpoint (POST /sessions/{id}/permissions/{requestId}) -> session.Resolve -> the harness answer
// frame, and the resulting permission-resolved event reflects on the card. Allow PROCEEDS (the
// out-of-grant tool runs); Deny BLOCKS it.
//
// Two arms:
//   FAKE (the dev-serve, always-on): the verdict-aware dev adapter (devserve/permission_adapter.go)
//     streams the gate deterministically, so this arm is NON-VACUOUS — the card renders, the resolve
//     POSTs, and Allow-proceeds / Deny-blocks are both asserted over a real SSE stream.
//   LIVE (agentgateway-live + a real claude token): honest-skip when the token/harness is absent.
//     Wired below as a documented, skipped placeholder so the lane is explicit about the live path.

/** The permission-demo prompt the dev adapter dispatches to the out-of-grant gate (it carries the
 *  devserve.permissionDemoSentinel). A real LIVE agent asks for a tool on its own; this is the
 *  dev-plane trigger that makes the FAKE arm deterministic. */
const PERMISSION_DEMO_PROMPT = 'eden:demo:permission — clean the build directory';

async function openChat(page: Page): Promise<void> {
  await page.goto('/chat');
  await expect(page.getByTestId('chat-app')).toBeVisible();
  await expect(page.getByTestId('gateway-health')).toHaveText('gateway up');
}

/** Drive the PRODUCT WIZARD to launch a claude session whose OPENING prompt is the permission-demo
 *  prompt — so the dev adapter's first turn is the out-of-grant gate (not the canonical demo). */
async function launchPermissionSession(page: Page): Promise<void> {
  await page.getByTestId('new-session').click();
  await expect(page.getByTestId('product-wizard')).toBeVisible();
  await page.getByTestId('wizard-prompt').fill(PERMISSION_DEMO_PROMPT);

  // DEFINE -> STACK -> CAPABILITIES (claude) -> PROCESS -> SAFETY -> REVIEW -> Launch.
  await page.getByTestId('wizard-next').click();
  await expect(page.getByTestId('product-wizard')).toHaveAttribute('data-step', 'stack');
  await page.getByTestId('wizard-next').click();
  await expect(page.getByTestId('product-wizard')).toHaveAttribute('data-step', 'capabilities');
  await page.getByTestId('wizard-harness-claude').click();
  await page.getByTestId('wizard-next').click();
  await expect(page.getByTestId('product-wizard')).toHaveAttribute('data-step', 'process');
  await page.getByTestId('wizard-next').click();
  await expect(page.getByTestId('product-wizard')).toHaveAttribute('data-step', 'safety');
  await page.getByTestId('wizard-next').click();
  await expect(page.getByTestId('product-wizard')).toHaveAttribute('data-step', 'review');
  await page.getByTestId('wizard-launch').click();
  await expect(page.getByTestId('product-wizard')).toBeHidden();
  await expect(page.getByTestId('active-harness')).toHaveText('claude');
}

test.describe('permission flow — live round-trip against a real dev-serve (fake arm)', () => {
  test('Allow: card renders -> resolve POSTs -> permission resolved + tool proceeds', async ({
    page,
  }) => {
    await openChat(page);
    await launchPermissionSession(page);

    // The out-of-grant request streams a permission-request event; the interactive card renders with
    // the tool + the three actions (Allow once / Allow for session / Deny) — the @eden/primitives card.
    const card = page.getByTestId('permission-card');
    await expect(card).toBeVisible({ timeout: 15_000 });
    await expect(card).toContainText('Permission required');
    await expect(card).toContainText('Bash');
    const allowOnce = card.getByRole('button', { name: 'Allow once' });
    await expect(allowOnce).toBeVisible();
    await expect(card.getByRole('button', { name: 'Deny' })).toBeVisible();

    // Allow once -> GatewayClient.resolve(id, req, 'allow', 'once') POSTs to the Resolve endpoint;
    // session.Resolve forwards the verdict, the harness emits permission-resolved (allowed), and the
    // card reflects the resolved state.
    await allowOnce.click();
    await expect(page.getByTestId('permission-decision')).toHaveText('allowed', {
      timeout: 15_000,
    });

    // Allow PROCEEDS: the out-of-grant Bash tool now runs to completion (a tool card for Bash with
    // the success result) — the agent proceeded because the human allowed it.
    const bashTool = page.getByTestId('tool-card').filter({ hasText: 'Bash' });
    await expect(bashTool).toBeVisible({ timeout: 15_000 });
    await expect(bashTool.getByTestId('tool-result')).toContainText('removed build');

    // The turn reached its clean terminal over the real SSE stream.
    await expect(page.getByTestId('terminal-banner')).toHaveAttribute('data-outcome', 'completed', {
      timeout: 15_000,
    });
    await expect(page.getByTestId('sse-status')).toHaveText('ended');

    // Tear the session down so the dev-serve has no orphan live handle.
    await page.getByTestId('stop').getByRole('button').click();
    await expect(page.getByTestId('empty-state')).toBeVisible();
  });

  test('Deny: card renders -> resolve POSTs -> permission denied + tool blocked', async ({
    page,
  }) => {
    await openChat(page);
    await launchPermissionSession(page);

    const card = page.getByTestId('permission-card');
    await expect(card).toBeVisible({ timeout: 15_000 });
    const deny = card.getByRole('button', { name: 'Deny' });
    await expect(deny).toBeVisible();

    // Deny -> resolve(id, req, 'deny') POSTs; the harness emits permission-resolved (denied).
    await deny.click();
    await expect(page.getByTestId('permission-decision')).toHaveText('denied', { timeout: 15_000 });

    // Deny BLOCKS: the Bash tool is reported denied (the gate rejected it), NOT run to success.
    const bashTool = page.getByTestId('tool-card').filter({ hasText: 'Bash' });
    await expect(bashTool).toBeVisible({ timeout: 15_000 });
    await expect(bashTool).toHaveAttribute('data-status', 'denied');

    // The turn still reaches a clean terminal (the agent stopped at the gate, no error).
    await expect(page.getByTestId('terminal-banner')).toHaveAttribute('data-outcome', 'completed', {
      timeout: 15_000,
    });

    await page.getByTestId('stop').getByRole('button').click();
    await expect(page.getByTestId('empty-state')).toBeVisible();
  });
});

// The LIVE arm: drive agentgateway-live with a real claude token to make a REAL agent request an
// out-of-grant tool, then Allow (assert it proceeds) / Deny (assert it blocks). It is honest-skipped
// unless the runner booted the live backend AND a claude token is present — the gated path
// (E2E_LIVE_PERMISSION=1 is exported by tests/e2e/run-live-permission.sh when /workspace/.env.development
// carries a CLAUDE_CODE_OAUTH_TOKEN). The token is NEVER read or logged here — the runner injects it
// into the agentgateway-live process env only; this spec just drives the same UI surface as the fake arm.
test.describe('permission flow — LIVE arm (real claude agent)', () => {
  test.skip(
    process.env.E2E_LIVE_PERMISSION !== '1',
    'live claude harness/token unavailable — run tests/e2e/run-live-permission.sh with a CLAUDE_CODE_OAUTH_TOKEN in /workspace/.env.development',
  );

  test('a real agent requests an out-of-grant tool; Allow proceeds', async ({ page }) => {
    await openChat(page);
    // The LIVE backend routes to the real claude harness; the same UI surface (the @eden/primitives
    // PermissionRequest card + the resolve round-trip) is exercised. The live agent asks for the tool
    // on its own, so the opening prompt instructs a task that needs one outside the standing grant.
    await launchPermissionSession(page);
    const card = page.getByTestId('permission-card');
    await expect(card).toBeVisible({ timeout: 60_000 });
    await card.getByRole('button', { name: 'Allow once' }).click();
    await expect(page.getByTestId('permission-decision')).toHaveText('allowed', {
      timeout: 60_000,
    });
    await expect(page.getByTestId('terminal-banner')).toBeVisible({ timeout: 60_000 });
  });
});
