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

/** Drive the CREATE-PROJECT FLOW to launch a claude session whose OPENING prompt is the
 *  permission-demo prompt — so the dev adapter's first turn is the out-of-grant gate (not the
 *  canonical demo). Spark (the prompt) → Scope → Stack → Build it. */
async function launchPermissionSession(page: Page): Promise<void> {
  await page.getByTestId('new-session').first().click();
  await expect(page.getByTestId('create-flow')).toBeVisible();
  await page.getByTestId('create-spark').fill(PERMISSION_DEMO_PROMPT);
  await page.getByTestId('create-start').click();
  await expect(page.getByTestId('create-flow')).toHaveAttribute('data-step', 'scope', {
    timeout: 10_000,
  });
  await page.getByTestId('create-next').click();
  await expect(page.getByTestId('create-flow')).toHaveAttribute('data-step', 'stack');
  await page.getByTestId('create-launch').click();
  await expect(page.getByTestId('create-flow')).toBeHidden();
  await expect(page.getByTestId('active-harness')).toHaveText('claude');
}

/** assertAwaitingPermissionControls is the regression guard for the (state × action) bug: while the
 *  session is AWAITING-PERMISSION, the turn-taking controls the state machine forbids (Steer needs
 *  Running; Prompt needs Ready/AwaitingInput) MUST be disabled — the UI derives them from the
 *  projected allowed-set, so an illegal control is unclickable. Abort (legal, non-terminal) and the
 *  permission Allow/Deny stay enabled. This is the assertion whose absence let the live bug ship. */
async function assertAwaitingPermissionControls(page: Page): Promise<void> {
  await expect(page.getByTestId('session-state')).toHaveText('awaiting-permission');
  await expect(page.getByTestId('steer').getByRole('button')).toBeDisabled();
  await expect(page.getByTestId('composer-send').getByRole('button')).toBeDisabled();
  await expect(page.getByTestId('request-tool').getByRole('button')).toBeDisabled();
  // Abort is legal in any non-terminal state, so it stays enabled; the permission card's Allow/Deny too.
  await expect(page.getByTestId('abort').getByRole('button')).toBeEnabled();
  // And the gateway drives the single opening turn, so NO illegal-prompt conflict notice renders —
  // this is the exact "prompt is illegal in state awaiting-permission" artifact the double-send used
  // to surface here; its absence is now asserted.
  await expect(page.getByTestId('notice').filter({ hasText: /illegal|conflict/i })).toHaveCount(0);
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

    // While awaiting the decision, the illegal turn-taking controls are disabled (the matrix fix);
    // Allow/Deny/Abort stay live. This is the cell the live "Steer is illegal in awaiting-permission"
    // bug lived in — the UI now cannot fire it.
    await assertAwaitingPermissionControls(page);
    await expect(allowOnce).toBeEnabled();

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
