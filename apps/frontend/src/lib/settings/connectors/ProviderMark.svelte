<script lang="ts">
  // ProviderMark — the placeholder provider glyph for a connector row (§3.2 gap: no Avatar/Icon-slot
  // atom exists in @eden/primitives yet; doc 17 §4 anticipates it). A plain inline element for now,
  // token-driven (no hardcoded hex/px on a painted role, P-D3). Rendered decorative (aria-hidden) —
  // the accessible name is the connector NAME beside it, never the glyph alone.
  //
  // P-D7 PROMOTION CANDIDATE (do NOT touch libs/typescript this wave): this is the missing
  // ProviderMark atom (§3.5 #3 — "promote on second use"). When the Avatar/Icon-slot atom lands in
  // @eden/primitives, this app-local placeholder is replaced by it; keep the tokened surface so the
  // promotion is a swap, not a re-derivation.
  import { kindGlyph } from './connectors';

  let { kind }: { kind: string } = $props();
  const glyph = $derived(kindGlyph(kind));
</script>

<span
  class="provider-mark"
  data-testid="settings-connector-mark"
  data-connector-kind={kind}
  aria-hidden="true"
>
  {glyph}
</span>

<style>
  /* Token-bridge only (the same math-sourced bridge the settings content uses): the mark is a small
     square carrying the provider glyph in the accent voice, its surface + edge from the app rail
     tokens. Zero px/hex literals on a painted role (P-D3). */
  .provider-mark {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: var(--space-7, 28px);
    block-size: var(--space-7, 28px);
    flex: none;
    border: 1px solid var(--border, var(--color-outline));
    border-radius: var(--radius-sm, 4px);
    background: var(
      --surface-muted,
      color-mix(in oklab, var(--color-on-surface) 4%, var(--color-surface))
    );
    color: var(--color-primary);
    font-size: var(--font-size-body-large, 15px);
    line-height: 1;
  }
</style>
