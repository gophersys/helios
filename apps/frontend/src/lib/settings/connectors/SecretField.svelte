<script lang="ts">
  // SecretField (the WriteOnlyField) — the SECURITY SPINE of the connectors section (design §3.5 #2:
  // "most-worth-a-single-audited-home; carries the no-echo invariant"). It has exactly two display
  // modes:
  //
  //   • ENTRY  — before a credential is saved: a `type="password"` Input the user pastes into. The
  //              value is BOUND locally and handed to the caller's connect seam ONCE (on Save). It is
  //              never persisted here, never logged, and is cleared the instant the caller confirms.
  //   • SAVED  — after a credential is stored: renders ONLY the fingerprint/last-4 (the mono chip)
  //              plus the account hint. There is NO reveal affordance AT ALL (honest chrome — the
  //              value does not exist client-side to reveal). "Replace" re-opens the ENTRY mode so a
  //              rotation re-pastes a fresh secret; it never echoes the old one.
  //
  // The value NEVER rides a ConnectorView (design §2: no `value` field, ever). Composed from
  // @eden/primitives (Field + Input) — defines no atom of its own (P-D7).
  //
  // P-D7 PROMOTION CANDIDATE (do NOT touch libs/typescript this wave): promote to
  // libs/typescript/primitives when a second surface needs a write-only credential field. The no-echo
  // rule lives in one audited home (fingerprintDisplay in ./connectors) so the promoted molecule cites
  // it rather than re-spelling it.
  import { Field, Input } from '@eden/primitives';
  import type { Theme } from '@eden/theme';
  import { fingerprintDisplay } from './connectors';

  let {
    // The stored fingerprint when SAVED (empty ⇒ ENTRY mode). NEVER the value — a one-way digest.
    fingerprint = '',
    // The account hint shown beside the fingerprint (e.g. "ecs-bot@acme"), mono. Never a secret.
    accountHint = '',
    // The credential-entry label + hint (per-provider copy).
    label = 'Credential',
    hint = '',
    // The bound plaintext, lifted to the parent (the add flow) so Save can hand it to the seam ONCE.
    // Bindable so the parent reads it on Save and clears it after.
    value = $bindable(''),
    // Force ENTRY mode even when a fingerprint exists (the "Replace" re-paste path).
    replacing = false,
    // The validation error (a bad credential the connect seam rejected), shown inline.
    error = '',
    theme,
  }: {
    fingerprint?: string;
    accountHint?: string;
    label?: string;
    hint?: string;
    value?: string;
    replacing?: boolean;
    error?: string;
    theme?: Theme;
  } = $props();

  // ENTRY when there is no stored fingerprint, or the caller is explicitly replacing. Otherwise SAVED
  // — the write-only display (fingerprint + hint only).
  const entering = $derived(replacing || fingerprint.trim().length === 0);
  const shown = $derived(fingerprintDisplay(fingerprint));
</script>

{#if entering}
  <!-- ENTRY — paste the credential (write-only: type=password; the value crosses the seam once). -->
  <div class="secret-field secret-field--entry" data-testid="settings-connector-credential">
    <Field {label} {error} {theme}>
      {#snippet control({ id, describedby, invalid })}
        <Input
          {id}
          type="password"
          bind:value
          placeholder="Paste the credential"
          aria-describedby={describedby}
          {invalid}
          {theme}
        />
      {/snippet}
    </Field>
    {#if hint}
      <p class="secret-field__hint">{hint}</p>
    {/if}
  </div>
{:else}
  <!-- SAVED — the write-only display: fingerprint/last-4 + account hint. NO reveal affordance. -->
  <div class="secret-field secret-field--saved">
    <span class="secret-field__label">Stored credential</span>
    <span class="secret-field__digest" data-testid="settings-connector-fingerprint">{shown}</span>
    {#if accountHint}
      <span class="secret-field__hint-mono" data-testid="settings-connector-account-hint">
        {accountHint}
      </span>
    {/if}
  </div>
{/if}

<style>
  /* Token-bridge only — zero px/hex on a painted role (P-D3). The digest + account hint are the MONO
     data voice (P-D4: mono for data). */
  .secret-field {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
    min-inline-size: 0;
  }
  .secret-field--saved {
    flex-direction: row;
    align-items: baseline;
    flex-wrap: wrap;
    gap: var(--space-3, 12px);
  }
  .secret-field__label {
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted-foreground, var(--color-outline));
  }
  .secret-field__digest {
    font-family: var(--font-code, monospace);
    font-size: var(--font-size-label, 13px);
    letter-spacing: 0.08em;
    color: var(--foreground, var(--color-on-surface));
  }
  .secret-field__hint-mono {
    font-family: var(--font-code, monospace);
    font-size: var(--font-size-label, 13px);
    color: var(--muted-foreground, var(--color-outline));
  }
  .secret-field__hint {
    margin: 0;
    font-size: var(--font-size-caption, 12px);
    color: var(--muted-foreground, var(--color-outline));
  }
</style>
