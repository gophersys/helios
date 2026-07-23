<script lang="ts">
  // ConnectorsSection — the CONNECTORS section content of the ONE Settings surface (design §3). It
  // renders inside SettingsSurface's `{:else if active === 'connectors'}` arm, above the read-only
  // Connections catch-all (§3.1). Claude-app-quality organization: a dense working list of connector
  // rows (provider mark · name · scope chip · real-status Badge + account hint · Connect/Manage/
  // Disconnect), or — when empty — the EmptyState as a PRODUCT surface (serif headline + action +
  // a content slot listing the available providers, never a void, P-D2).
  //
  // Data seam (callback-injection, mirroring the Agents section's loadConfigs/saveConfig — §3.1):
  //   • loadConnectors      — GET the caller-org connectors (never a value; the §2 view shape).
  //   • connectProvider     — POST a new connector; the credential crosses HERE, once (§2).
  //   • disconnectConnector — DELETE (revoke) a connector.
  //   Absent seam ⇒ the section degrades to read-only (graceful, P-D6 — same pattern as Agents).
  //
  // Composed from @eden/primitives (Card·flat, EmptyState, Divider) + the app-local ConnectorRow /
  // AddConnectorFlow (P-D7 — the app defines no atom of its own; those are the promotion units).
  import { Card, EmptyState, Divider } from '@eden/primitives';
  import type { Theme } from '@eden/theme';
  import ConnectorRow from './ConnectorRow.svelte';
  import AddConnectorFlow from './AddConnectorFlow.svelte';
  import {
    CONNECTOR_KIND_DESCRIPTORS,
    type ConnectorKind,
    type ScopeInput,
    type ConnectorView,
  } from './connectors';

  let {
    open = false,
    theme,
    loadConnectors,
    connectProvider,
    disconnectConnector,
  }: {
    open?: boolean;
    theme?: Theme;
    loadConnectors?: () => Promise<ConnectorView[]>;
    connectProvider?: (
      kind: ConnectorKind,
      credential: string,
      scope: ScopeInput,
    ) => Promise<ConnectorView>;
    disconnectConnector?: (id: string) => Promise<void>;
  } = $props();

  let connectors = $state<ConnectorView[]>([]);
  let loaded = $state(false);
  let loadError = $state<string | null>(null);
  let busyId = $state<string | null>(null);
  let addOpen = $state(false);
  let addKind = $state<ConnectorKind | undefined>(undefined);

  const readOnly = $derived(!connectProvider);
  const available = CONNECTOR_KIND_DESCRIPTORS.map((d) => d.label).join(' · ');

  /** Load the caller-org connectors into the list (an absent seam ⇒ read-only empty). */
  async function loadAll(): Promise<void> {
    if (!loadConnectors) {
      loaded = true;
      return;
    }
    try {
      connectors = await loadConnectors();
      loadError = null;
    } catch (cause) {
      loadError = cause instanceof Error ? cause.message : String(cause);
    } finally {
      loaded = true;
    }
  }

  // Load once per surface-open; reset on close so a re-open re-reads fresh (the Agents pattern).
  $effect(() => {
    if (open && !loaded) void loadAll();
    if (!open) {
      loaded = false;
      addOpen = false;
    }
  });

  /** The add/connect seam: the plaintext crosses connectProvider ONCE; on success we reload so the
   *  new row renders its fingerprint (never the value). The add flow already cleared the plaintext. */
  async function onSave(
    kind: ConnectorKind,
    credential: string,
    scope: ScopeInput,
  ): Promise<ConnectorView> {
    if (!connectProvider) throw new Error('connect is not available');
    const stored = await connectProvider(kind, credential, scope);
    await loadAll();
    return stored;
  }

  /** Open the add flow, optionally deep-linked to a kind (an unconnected row's Connect). */
  function openAdd(kind?: ConnectorKind): void {
    addKind = kind;
    addOpen = true;
  }

  /** Manage re-opens the add flow deep-linked to the connector's kind (a rotation re-pastes a fresh
   *  secret — SecretField's Replace path; the old value is never echoed). */
  function onManage(view: ConnectorView): void {
    const kind = CONNECTOR_KIND_DESCRIPTORS.find((d) => d.kind === view.kind)?.kind;
    openAdd(kind);
  }

  /** Disconnect (revoke) a connector, then reload the list. */
  async function onDisconnect(view: ConnectorView): Promise<void> {
    if (!disconnectConnector) return;
    busyId = view.id;
    try {
      await disconnectConnector(view.id);
      await loadAll();
    } catch (cause) {
      loadError = cause instanceof Error ? cause.message : String(cause);
    } finally {
      busyId = null;
    }
  }
</script>

<section class="connectors" data-testid="settings-connectors">
  {#if loadError}
    <p class="connectors__error" data-testid="settings-connector-error" role="alert">{loadError}</p>
  {/if}

  {#if connectors.length === 0}
    <!-- EMPTY — a product surface (P-D2): serif headline + action + the available-providers offer. -->
    <div data-testid="settings-connectors-empty">
      <EmptyState
        headline="No connectors yet"
        body="Connect a provider to give your agents access to the tools they use."
        {theme}
      >
        {#snippet action()}
          {#if !readOnly}
            <AddConnectorFlow bind:open={addOpen} initialKind={addKind} {onSave} {theme} />
          {/if}
        {/snippet}
        {#snippet content()}
          <p class="connectors__available">
            <span class="connectors__available-label">Available</span>
            <span class="connectors__available-list">{available}</span>
          </p>
        {/snippet}
      </EmptyState>
    </div>
  {:else}
    <!-- LIST — the dense working list of connector rows (Clusters-grade density, P-D5). -->
    <Card variant="flat" aria-label="Connectors" {theme}>
      {#snippet body()}
        <div class="connectors__list" role="list">
          {#each connectors as view, index (view.id)}
            <div role="listitem">
              <ConnectorRow
                {view}
                {theme}
                busy={busyId === view.id}
                onConnect={(v) =>
                  openAdd(CONNECTOR_KIND_DESCRIPTORS.find((d) => d.kind === v.kind)?.kind)}
                {onManage}
                {onDisconnect}
              />
              {#if index < connectors.length - 1}
                <Divider {theme} />
              {/if}
            </div>
          {/each}
        </div>
      {/snippet}
    </Card>

    {#if !readOnly}
      <div class="connectors__add">
        <AddConnectorFlow bind:open={addOpen} initialKind={addKind} {onSave} {theme} />
      </div>
    {/if}
  {/if}
</section>

<style>
  /* Token-bridge only — zero px/hex on a painted role (P-D3). */
  .connectors {
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 16px);
  }
  .connectors__list {
    display: flex;
    flex-direction: column;
  }
  .connectors__add {
    display: flex;
    justify-content: flex-start;
  }
  .connectors__error {
    margin: 0;
    padding: var(--space-2, 8px) var(--space-3, 12px);
    border: 1px solid color-mix(in oklab, var(--color-error) 30%, transparent);
    border-radius: var(--radius-md, 6px);
    background: var(--destructive-surface);
    color: var(--destructive, var(--color-error));
    font-size: var(--font-size-label, 13px);
  }
  /* The available-providers offer in the empty state — mono data voice (P-D4). */
  .connectors__available {
    margin: 0;
    display: inline-flex;
    align-items: baseline;
    gap: var(--space-3, 12px);
    flex-wrap: wrap;
  }
  .connectors__available-label {
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted-foreground, var(--color-outline));
  }
  .connectors__available-list {
    font-family: var(--font-code, monospace);
    font-size: var(--font-size-label, 13px);
    color: var(--foreground, var(--color-on-surface));
  }
</style>
