<script lang="ts">
  // A permission round-trip card (REQ-0024 the human/policy gate): renders a permission-request
  // and its permission-resolved decision, correlated by requestId. The decision drives the chip
  // tone — pending (awaiting a human/policy Resolve), allowed, or denied.
  import type { PermissionEntry } from '$lib/gateway/session.svelte';

  let { permission }: { permission: PermissionEntry } = $props();

  const tone = $derived(
    permission.decision === 'allowed' ? 'ok' : permission.decision === 'denied' ? 'warn' : 'info',
  );
</script>

<article class="permission" data-testid="permission-card">
  <header class="permission__head">
    <span aria-hidden="true">🔐</span>
    <span class="permission__title">permission</span>
    {#if permission.tool}
      <span class="chip chip--muted">{permission.tool}</span>
    {/if}
    <span class="chip chip--{tone}" data-testid="permission-decision">{permission.decision}</span>
  </header>
  {#if permission.reason}
    <p class="permission__reason">{permission.reason}</p>
  {/if}
  {#if permission.by}
    <p class="permission__by">resolved by <code>{permission.by}</code></p>
  {/if}
</article>

<style>
  .permission {
    border: 1px solid var(--line);
    border-left: 3px solid var(--chip-warn-fg);
    border-radius: var(--radius);
    background: var(--quote);
    padding: 0.7rem 0.9rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    max-width: 78ch;
  }
  .permission__head {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .permission__title {
    font-family: var(--font-code);
    font-weight: 650;
    font-size: 0.9rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .permission__reason {
    margin: 0;
    font-size: 0.92rem;
  }
  .permission__by {
    margin: 0;
    font-size: var(--type-micro);
    color: var(--muted);
  }
</style>
