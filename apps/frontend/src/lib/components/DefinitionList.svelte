<script lang="ts">
  // A nested object rendered as a definition list (doc 12 §5: nested objects →
  // definition lists). Each key is a term; its value is rendered recursively via
  // DataValue, so an object-of-arrays-of-objects renders as a list of tables, and
  // so on. A `links` sub-object (the typed-edge block on data items) is rendered
  // the same way — its item-id values become navigable chips through DataValue.
  import DataValue from './DataValue.svelte';
  import type { Backlink } from '../../routes/p/[slug]/+page.server';

  let {
    record,
    backlinks = {},
  }: { record: Record<string, unknown>; backlinks?: Record<string, Backlink[]> } = $props();

  // Humanize a key for display (snake/kebab → spaced), keeping it lowercase so it
  // reads as a label, not a heading.
  function label(key: string): string {
    return key.replace(/[_-]/g, ' ');
  }

  const entries = $derived(Object.entries(record));
</script>

{#if entries.length === 0}
  <span class="definition-empty">—</span>
{:else}
  <dl class="definition-list">
    {#each entries as [key, value] (key)}
      <dt>{label(key)}</dt>
      <dd><DataValue {value} {backlinks} /></dd>
    {/each}
  </dl>
{/if}

<style>
  .definition-list {
    margin: 0;
    display: grid;
    grid-template-columns: minmax(6rem, max-content) 1fr;
    gap: 0.25rem 1rem;
    align-items: baseline;
  }
  dt {
    font-size: 0.74rem;
    font-weight: 650;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    color: var(--muted);
    white-space: nowrap;
  }
  dd {
    margin: 0;
    min-width: 0;
  }
  .definition-empty {
    color: var(--muted);
  }

  @media (max-width: 560px) {
    .definition-list {
      grid-template-columns: 1fr;
      gap: 0.1rem;
    }
    dd {
      margin-bottom: 0.5rem;
    }
  }
</style>
