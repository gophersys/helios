<script lang="ts">
  // Render an arbitrary projected-data value (doc 11 §5: data blocks vary by
  // document type). The rules, applied recursively:
  //   · an array of objects   → a DataTable (threaded with backlinks so item rows
  //                             get anchors + derived "realized by …" edges);
  //   · an array of scalars   → a bulleted list, recursing per entry;
  //   · a plain object        → a DefinitionList;
  //   · a string that is an item id → a navigable link chip;
  //   · any other scalar      → text.
  // The backlinks map is passed down so it reaches nested tables; components in
  // the cycle (DataTable, DefinitionList) import this one back — Svelte resolves
  // the mutual import.
  import DataValue from './DataValue.svelte';
  import DataTable from './DataTable.svelte';
  import DefinitionList from './DefinitionList.svelte';
  import LinkChip from './LinkChip.svelte';
  import { isItemId } from '$lib/documentModel';
  import type { Backlink } from '../../routes/p/[slug]/+page.server';

  let { value, backlinks = {} }: { value: unknown; backlinks?: Record<string, Backlink[]> } =
    $props();

  function isPlainObject(candidate: unknown): candidate is Record<string, unknown> {
    return typeof candidate === 'object' && candidate !== null && !Array.isArray(candidate);
  }

  function isArrayOfObjects(candidate: unknown): candidate is Array<Record<string, unknown>> {
    return (
      Array.isArray(candidate) &&
      candidate.length > 0 &&
      candidate.every((entry) => isPlainObject(entry))
    );
  }

  const kind = $derived(
    isArrayOfObjects(value)
      ? 'table'
      : Array.isArray(value)
        ? 'list'
        : isPlainObject(value)
          ? 'object'
          : typeof value === 'string' && isItemId(value)
            ? 'item'
            : 'scalar',
  );
</script>

{#if kind === 'table'}
  <DataTable rows={value as Array<Record<string, unknown>>} {backlinks} />
{:else if kind === 'list'}
  {@const items = value as unknown[]}
  {#if items.length === 0}
    <span class="value-empty">—</span>
  {:else}
    <ul class="value-list">
      {#each items as entry, index (index)}
        <li><DataValue value={entry} {backlinks} /></li>
      {/each}
    </ul>
  {/if}
{:else if kind === 'object'}
  <DefinitionList record={value as Record<string, unknown>} {backlinks} />
{:else if kind === 'item'}
  <LinkChip target={value as string} />
{:else if value === null || value === undefined}
  <span class="value-empty">—</span>
{:else if typeof value === 'boolean'}
  <span class="value-scalar">{value ? 'yes' : 'no'}</span>
{:else}
  <span class="value-scalar">{String(value)}</span>
{/if}

<style>
  .value-list {
    margin: 0;
    padding-left: 1.1rem;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }
  .value-empty {
    color: var(--muted);
  }
  .value-scalar {
    white-space: pre-wrap;
  }
</style>
