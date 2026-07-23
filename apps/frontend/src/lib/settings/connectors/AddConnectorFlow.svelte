<script lang="ts">
  // AddConnectorFlow — the nested-Dialog add/connect flow (design §3.3 wireframe): pick a WORKING
  // provider (P-D6 — only kinds whose connect path works render), paste the credential (write-only,
  // via SecretField ENTRY mode), choose the scope (org DEFAULT — LOCKED call), Save. On Save the
  // plaintext crosses the injected `onSave` seam ONCE; on success the row appears showing only the
  // fingerprint — the credential is cleared here and NEVER echoed again (no reveal affordance at all).
  //
  // Composed from @eden/primitives Dialog (nested LIFO over the Settings sheet's own portal —
  // OD-1-proven) + Button + the app-local SecretField. Defines no atom of its own (P-D7). The
  // provider/scope pickers are native <select>s bridged to the app tokens (there is no primitive
  // select yet; the same honest-chrome native control the Agents posture uses).
  //
  // P-D7 PROMOTION CANDIDATE (do NOT touch libs/typescript this wave): §3.5 #4 — if the wizard
  // outgrows one Dialog, promote to a WizardShell-backed organism.
  import { Dialog, Button } from '@eden/primitives';
  import type { Theme } from '@eden/theme';
  import SecretField from './SecretField.svelte';
  import {
    CONNECTOR_KIND_DESCRIPTORS,
    type ConnectorKind,
    type ScopeLevel,
    type ScopeInput,
    type ConnectorView,
  } from './connectors';

  let {
    open = $bindable(false),
    theme,
    // The connect seam: the plaintext crosses HERE, exactly once. Returns the stored ConnectorView
    // (fingerprint only, never the value). Absent ⇒ the flow is read-only (graceful degrade, P-D6).
    onSave,
    // Preselect a kind (the Connect button on an offered-but-unconnected row deep-links its kind).
    initialKind,
  }: {
    open?: boolean;
    theme?: Theme;
    onSave?: (kind: ConnectorKind, credential: string, scope: ScopeInput) => Promise<ConnectorView>;
    initialKind?: ConnectorKind;
  } = $props();

  const SCOPE_LEVELS: readonly { value: ScopeLevel; label: string }[] = [
    { value: 'org', label: 'Organization (shared)' },
    { value: 'user', label: 'Only me' },
  ];

  // Seeded to the first working kind; the open-effect below re-seats it to `initialKind` when the
  // dialog opens (so an unconnected row's Connect deep-links its provider). Reading `initialKind` here
  // would only capture its initial value — the effect is the reactive re-seat.
  let kind = $state<ConnectorKind>(CONNECTOR_KIND_DESCRIPTORS[0].kind);
  let scopeLevel = $state<ScopeLevel>('org'); // org-scope DEFAULT (LOCKED call).
  let credential = $state('');
  let saving = $state(false);
  let error = $state('');

  const descriptor = $derived(
    CONNECTOR_KIND_DESCRIPTORS.find((d) => d.kind === kind) ?? CONNECTOR_KIND_DESCRIPTORS[0],
  );
  const canSave = $derived(!saving && credential.trim().length > 0 && Boolean(onSave));

  // Re-seat the preselected kind + reset the draft each time the dialog opens (a re-open re-reads
  // fresh; the credential never survives a close — no lingering plaintext).
  $effect(() => {
    if (open) {
      if (initialKind) kind = initialKind;
      scopeLevel = 'org';
      credential = '';
      error = '';
      saving = false;
    }
  });

  function onOpenChange(next: boolean): void {
    open = next;
    if (!next) credential = ''; // belt-and-braces: clear the plaintext on any close.
  }

  async function save(): Promise<void> {
    if (!onSave || !canSave) return;
    saving = true;
    error = '';
    const scope: ScopeInput = { level: scopeLevel };
    try {
      await onSave(kind, credential.trim(), scope);
      credential = ''; // NEVER retain the plaintext after the seam accepts it.
      open = false;
    } catch (cause) {
      error = cause instanceof Error ? cause.message : String(cause);
    } finally {
      saving = false;
    }
  }
</script>

<Dialog bind:open {onOpenChange} title="Add connector" {theme}>
  {#snippet trigger()}
    <span class="add-trigger" data-testid="settings-connector-add">+ Add connector</span>
  {/snippet}

  <div class="add-flow" data-testid="settings-connector-dialog">
    <!-- 1 · pick a WORKING provider (P-D6 — only working kinds render). -->
    <label class="add-flow__field">
      <span class="add-flow__label">Provider</span>
      <select
        class="add-flow__select"
        bind:value={kind}
        data-testid="settings-connector-kind"
        disabled={saving}
      >
        {#each CONNECTOR_KIND_DESCRIPTORS as option (option.kind)}
          <option value={option.kind} data-testid={`settings-connector-kind-${option.kind}`}>
            {option.label}
          </option>
        {/each}
      </select>
    </label>

    <!-- 2 · paste the credential (write-only; the value crosses onSave once). -->
    <SecretField
      bind:value={credential}
      label={descriptor.credentialLabel}
      hint={descriptor.credentialHint}
      {error}
      {theme}
    />

    <!-- 3 · choose the scope (org DEFAULT). -->
    <label class="add-flow__field">
      <span class="add-flow__label">Scope</span>
      <select
        class="add-flow__select"
        bind:value={scopeLevel}
        data-testid="settings-connector-scope"
        disabled={saving}
      >
        {#each SCOPE_LEVELS as option (option.value)}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>
    </label>

    <div class="add-flow__actions">
      <Button variant="ghost" {theme} disabled={saving} onclick={() => onOpenChange(false)}>
        <span>Cancel</span>
      </Button>
      <Button variant="primary" {theme} disabled={!canSave} onclick={save}>
        <span data-testid="settings-connector-save">{saving ? 'Validating…' : 'Save'}</span>
      </Button>
    </div>
  </div>
</Dialog>

<style>
  /* Token-bridge only — zero px/hex on a painted role (P-D3). The dialog body is a focus moment
     (generous, P-D5): one field per step, the SecretField owns the write-only entry. */
  /* The add trigger reads as the shadcn solid button — a solid --primary fill, --radius-md, the
     --shadow-sm lift. */
  .add-trigger {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
    padding: var(--space-2, 8px) var(--space-4, 16px);
    min-block-size: 44px;
    border: 1px solid var(--primary, var(--color-primary));
    border-radius: var(--radius-md, 6px);
    background: var(--primary, var(--color-primary));
    color: var(--primary-foreground, var(--color-on-primary));
    font-family: var(--font-code, monospace);
    font-size: var(--font-size-label, 13px);
    font-weight: 600;
    cursor: pointer;
    box-shadow: var(--shadow-sm);
    transition:
      filter var(--duration-short-2, 120ms) var(--ease-standard, ease),
      box-shadow var(--duration-short-2, 120ms) var(--ease-standard, ease);
  }
  .add-trigger:hover {
    filter: brightness(1.08);
    box-shadow: var(--shadow-md);
  }
  .add-flow {
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 16px);
    min-inline-size: min(24rem, 70vw);
  }
  .add-flow__field {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
  }
  .add-flow__label {
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted-foreground, var(--color-outline));
  }
  /* Shadcn select geometry — a 1px --input edge, --radius-sm corners, a --ring focus halo. */
  .add-flow__select {
    padding: var(--space-2, 8px) var(--space-3, 12px);
    min-block-size: 44px;
    background: var(--background, var(--color-surface));
    color: var(--foreground, var(--color-on-surface));
    border: 1px solid var(--input, var(--color-outline));
    border-radius: var(--radius-sm, 4px);
    font-family: var(--font-code, monospace);
    font-size: var(--font-size-label, 13px);
    cursor: pointer;
    transition:
      border-color var(--duration-short-2, 120ms) var(--ease-standard, ease),
      box-shadow var(--duration-short-2, 120ms) var(--ease-standard, ease);
  }
  .add-flow__select:focus-visible {
    outline: none;
    border-color: var(--ring, var(--color-primary));
    box-shadow: 0 0 0 3px color-mix(in oklab, var(--ring, var(--color-primary)) 30%, transparent);
  }
  .add-flow__actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--space-2, 8px);
    padding-block-start: var(--space-2, 8px);
  }
</style>
