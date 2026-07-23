<script lang="ts">
  // ConnectorRow — the repeated working-list unit of the Connectors section (design §3.5 #1). A dense,
  // scannable row (Clusters-grade, not a card-in-a-void, P-D5): the provider mark · the connector name
  // (sans) · the scope chip (mono) · the real-status Badge + account hint · the action cluster
  // (Connect / Manage / Disconnect). Composed ENTIRELY from @eden/primitives + the app-local
  // ProviderMark/SecretField (P-D7 — defines no atom of its own).
  //
  // The write-only display is delegated to SecretField: a connected row shows ONLY the fingerprint
  // (never the value, never a reveal affordance). An unconnected ("not set") row offers Connect.
  //
  // P-D7 PROMOTION CANDIDATE (do NOT touch libs/typescript this wave): §3.5 #1 — promote this row
  // molecule to libs/typescript/primitives when a second surface renders a connector list.
  import { Badge, Button, Chip } from '@eden/primitives';
  import type { Theme } from '@eden/theme';
  import ProviderMark from './ProviderMark.svelte';
  import SecretField from './SecretField.svelte';
  import {
    kindLabel,
    isConnected,
    scopeChipText,
    stateBadgeVariant,
    stateLabel,
    type ConnectorView,
  } from './connectors';

  let {
    view,
    theme,
    onConnect,
    onManage,
    onDisconnect,
    busy = false,
  }: {
    view: ConnectorView;
    theme?: Theme;
    onConnect?: (view: ConnectorView) => void;
    onManage?: (view: ConnectorView) => void;
    onDisconnect?: (view: ConnectorView) => void;
    busy?: boolean;
  } = $props();

  const connected = $derived(isConnected(view));
  const badgeVariant = $derived(stateBadgeVariant(view.state));
</script>

<div
  class="connector-row"
  data-testid="settings-connector-row"
  data-connector-id={view.id}
  data-connector-kind={view.kind}
  data-connector-state={view.state}
>
  <div class="connector-row__lead">
    <ProviderMark kind={view.kind} />
    <div class="connector-row__ident">
      <span class="connector-row__name">{kindLabel(view.kind)}</span>
      <div class="connector-row__meta">
        <Chip {theme}>{`scope:${scopeChipText(view.scope)}`}</Chip>
        <span class="connector-row__status" data-testid="settings-connector-state">
          <Badge variant={badgeVariant} status {theme}>{stateLabel(view.state)}</Badge>
        </span>
      </div>
    </div>
  </div>

  <div class="connector-row__body">
    {#if connected}
      <SecretField fingerprint={view.fingerprint} accountHint={view.accountHint} {theme} />
    {:else}
      <span class="connector-row__unset" data-testid="settings-connector-unset">—</span>
    {/if}
  </div>

  <div class="connector-row__actions">
    {#if connected}
      <Button variant="ghost" {theme} disabled={busy} onclick={() => onManage?.(view)}>
        <span data-testid="settings-connector-manage">Manage</span>
      </Button>
      <Button variant="danger" {theme} disabled={busy} onclick={() => onDisconnect?.(view)}>
        <span data-testid="settings-connector-disconnect">Disconnect</span>
      </Button>
    {:else}
      <Button variant="primary" {theme} disabled={busy} onclick={() => onConnect?.(view)}>
        <span data-testid="settings-connector-connect">Connect</span>
      </Button>
    {/if}
  </div>
</div>

<style>
  /* Token-bridge only — zero px/hex on a painted role (P-D3). Dense row: lead (mark+ident) · body
     (write-only display) · actions, wrapping gracefully at narrow widths. The name is the SANS
     interface voice; scope/fingerprint the MONO data voice (P-D4). */
  .connector-row {
    display: grid;
    grid-template-columns: minmax(12rem, 1.4fr) minmax(8rem, 1fr) auto;
    align-items: center;
    gap: var(--space-3, 12px) var(--space-4, 16px);
    padding: var(--space-3, 12px) var(--space-4, 16px);
  }
  .connector-row__lead {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    min-inline-size: 0;
  }
  .connector-row__ident {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
    min-inline-size: 0;
  }
  .connector-row__name {
    font-size: var(--font-size-body-large, 15px);
    font-weight: 600;
    color: var(--eden-app-fg, var(--color-on-surface));
  }
  .connector-row__meta {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2, 8px);
  }
  .connector-row__status {
    display: inline-flex;
  }
  .connector-row__body {
    display: flex;
    min-inline-size: 0;
  }
  .connector-row__unset {
    font-family: var(--font-code, monospace);
    color: var(--eden-app-muted, var(--color-outline));
    font-size: var(--font-size-label, 13px);
  }
  .connector-row__actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--space-2, 8px);
    flex-wrap: wrap;
  }

  /* Narrow: collapse to a single column, actions left-aligned. */
  @media (max-width: 640px) {
    .connector-row {
      grid-template-columns: 1fr;
    }
    .connector-row__actions {
      justify-content: flex-start;
    }
  }
</style>
