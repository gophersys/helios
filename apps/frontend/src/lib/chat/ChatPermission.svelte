<script lang="ts">
  // The live permission round-trip surface (ADR-0025). While the request is PENDING it renders the
  // @eden/primitives interactive PermissionRequest card (tool + args/reason + Allow-once /
  // Allow-for-session / Deny — every action a gated, token-driven, 44px-floor Button); a human
  // decision flows GatewayClient.resolve(...) -> session.Resolve -> the native control_response, so
  // the agent proceeds or is blocked. Once resolved (or while the POST is in flight) it shows the
  // outcome chip + the deciding principal + any advisor rationale. The card is token-driven off the
  // SAME generated @eden/theme the rest of the chat uses (math is source of truth) — no hardcoded
  // colour. When the autonomous advisor decides without a human click, `decision` arrives already
  // resolved and the rationale is surfaced.
  import { PermissionRequest } from '@eden/primitives';
  import type { Theme } from '@eden/theme';
  import type { PermissionEntry } from '$lib/gateway/session.svelte';
  import type { PermissionScope, PermissionVerdict } from '$lib/gateway/types';

  let {
    permission,
    theme,
    onresolve,
  }: {
    permission: PermissionEntry;
    theme: Theme;
    onresolve: (
      requestId: string,
      verdict: PermissionVerdict,
      scope: PermissionScope,
    ) => Promise<void> | void;
  } = $props();

  // `pending` means the request has not been answered AND no answer is in flight — the only state
  // in which the interactive card is shown. Once the human clicks (resolving) or the resolution
  // event lands (decision != pending), the read-only resolved view replaces the actions.
  const pending = $derived(permission.decision === 'pending' && !permission.resolving);
  const outcome = $derived(permission.resolving ? 'resolving' : (permission.decision ?? 'pending'));
  const tone = $derived(
    permission.decision === 'allowed' ? 'ok' : permission.decision === 'denied' ? 'denied' : 'info',
  );

  /** Map the primitive's three decisions onto the gateway Resolve verdict + scope (ADR-0025):
   *  Allow-once -> allow/once, Allow-for-session -> allow/session, Deny -> deny/once. */
  function onDecision(decision: 'allow-once' | 'allow-session' | 'deny'): void {
    if (!pending) return;
    const verdict: PermissionVerdict = decision === 'deny' ? 'deny' : 'allow';
    const scope: PermissionScope = decision === 'allow-session' ? 'session' : 'once';
    void onresolve(permission.requestId, verdict, scope);
  }
</script>

<div
  class="chat-permission"
  data-testid="permission-card"
  data-request-id={permission.requestId}
  data-decision={outcome}
>
  {#if pending}
    <PermissionRequest
      tool={permission.tool ?? 'a tool'}
      reason={permission.reason ?? ''}
      {theme}
      {onDecision}
    />
  {:else}
    <!-- The resolved (or in-flight) record: the outcome the human/advisor chose, surfaced with the
         tool, the deciding principal, and the advisor rationale when the policy decided. -->
    <article
      class="resolved"
      data-state={tone}
      role="group"
      aria-label={`Permission ${outcome} for ${permission.tool ?? 'a tool'}`}
    >
      <header class="resolved__head">
        <h3 class="resolved__title">Permission {outcome}</h3>
        {#if permission.tool}
          <code class="resolved__tool">{permission.tool}</code>
        {/if}
        <span class="resolved__chip" data-testid="permission-decision" data-state={tone}>
          {outcome}
        </span>
      </header>
      {#if permission.reason}
        <p class="resolved__reason">{permission.reason}</p>
      {/if}
      {#if permission.rationale}
        <p class="resolved__rationale" data-testid="permission-rationale">
          <span class="resolved__label">advisor</span>
          {permission.rationale}
        </p>
      {/if}
      {#if permission.by}
        <p class="resolved__by">resolved by <code>{permission.by}</code></p>
      {/if}
    </article>
  {/if}
</div>

<style>
  .chat-permission {
    max-width: 78ch;
  }

  /* The resolved record reads off the SAME generated role tokens the primitive card uses (one
     identity, math is source of truth) — never a hardcoded colour. */
  .resolved {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
    padding: var(--space-5, 20px);
    border-radius: var(--radius-lg, 12px);
    color: var(--foreground, var(--color-on-surface));
    background: var(--card, var(--color-surface));
    border: 1px solid var(--border, var(--color-outline));
    box-shadow: var(--shadow-xs);
  }
  .resolved[data-state='ok'] {
    border-color: color-mix(
      in oklab,
      var(--color-success) 45%,
      var(--border, var(--color-outline))
    );
  }
  .resolved[data-state='denied'] {
    border-color: color-mix(in oklab, var(--color-error) 45%, var(--border, var(--color-outline)));
  }
  .resolved__head {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    flex-wrap: wrap;
  }
  .resolved__title {
    margin: 0;
    margin-inline-end: auto;
    font-size: var(--font-size-title, 23px);
    font-family: var(--font-display);
  }
  .resolved__tool {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    background: var(
      --surface-muted,
      color-mix(in oklab, var(--color-on-surface) 8%, var(--color-surface))
    );
    border: 1px solid var(--border);
    border-radius: var(--radius-sm, 4px);
    padding: 0.15em 0.5em;
  }
  /* Shadcn outline status pill — a status-tinted fill, a 1px status border, --radius-sm corners. */
  .resolved__chip {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border-radius: var(--radius-sm, 7px);
    padding: 0.18rem 0.6rem;
    background: var(
      --info-surface,
      color-mix(in oklab, var(--color-info) 18%, var(--color-surface))
    );
    border: 1px solid color-mix(in oklab, var(--color-info) 30%, transparent);
    color: var(--color-info);
  }
  .resolved__chip[data-state='ok'] {
    background: var(
      --success-surface,
      color-mix(in oklab, var(--color-success) 18%, var(--color-surface))
    );
    border-color: color-mix(in oklab, var(--color-success) 30%, transparent);
    color: var(--color-success);
  }
  .resolved__chip[data-state='denied'] {
    background: var(
      --destructive-surface,
      color-mix(in oklab, var(--color-error) 16%, var(--color-surface))
    );
    border-color: color-mix(in oklab, var(--color-error) 30%, transparent);
    color: var(--destructive, var(--color-error));
  }
  .resolved__reason,
  .resolved__rationale,
  .resolved__by {
    margin: 0;
    font-size: var(--font-size-body, 16px);
    line-height: var(--line-height-body, 1.56);
  }
  .resolved__rationale {
    color: color-mix(in oklab, var(--color-on-surface) 75%, var(--color-surface));
    font-style: italic;
  }
  .resolved__label {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    font-style: normal;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-primary);
    margin-inline-end: var(--space-1, 4px);
  }
  .resolved__by {
    font-size: var(--font-size-caption, 12px);
    color: color-mix(in oklab, var(--color-on-surface) 58%, var(--color-surface));
  }
  .resolved__by code,
  .resolved__tool {
    font-family: var(--font-code);
  }
</style>
