<script lang="ts">
  // An array of objects rendered as a table (doc 12 §5: arrays of objects →
  // tables). Columns are the union of keys across rows, ordered so that an `id`
  // comes first and a long prose-ish column (statement/responsibility/summary)
  // comes last. A row that carries an item id (REQ-0001, CMP-0003, …) gets an
  // item anchor (id="item-…") so links elsewhere can jump to it, and — when a
  // backlinks index is supplied — a "realized by …" line of derived reverse edges
  // (doc 11 §3, doc 12 §5 typed backlinks).
  import DataValue from './DataValue.svelte';
  import LinkChip from './LinkChip.svelte';
  import { isItemId } from '$lib/documentModel';
  import type { Backlink } from '../../routes/p/[slug]/+page.server';

  let {
    rows,
    backlinks = {},
  }: { rows: Array<Record<string, unknown>>; backlinks?: Record<string, Backlink[]> } = $props();

  // Columns that read better as the wide trailing column when present.
  const WIDE_KEYS = new Set([
    'statement',
    'responsibility',
    'summary',
    'rationale',
    'description',
    'outcome',
    'definition',
  ]);

  // The union of keys across all rows, ordered: id first, wide columns last,
  // everything else in first-seen order. Stable across rows so the header is fixed.
  const columns = $derived.by(() => {
    const seen: string[] = [];
    for (const row of rows) {
      for (const key of Object.keys(row)) {
        if (!seen.includes(key)) seen.push(key);
      }
    }
    const head = seen.filter((key) => key === 'id');
    const wide = seen.filter((key) => WIDE_KEYS.has(key) && key !== 'id');
    const middle = seen.filter((key) => key !== 'id' && !WIDE_KEYS.has(key));
    return [...head, ...middle, ...wide];
  });

  function rowItemId(row: Record<string, unknown>): string | null {
    const id = row.id;
    return typeof id === 'string' && isItemId(id) ? id : null;
  }

  function label(key: string): string {
    return key.replace(/[_-]/g, ' ');
  }
</script>

<div class="table-wrap">
  <table class="data-table">
    <thead>
      <tr>
        {#each columns as column (column)}
          <th>{label(column)}</th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#each rows as row, index (rowItemId(row) ?? index)}
        {@const itemId = rowItemId(row)}
        <tr id={itemId ? `item-${itemId}` : undefined} class:has-anchor={itemId}>
          {#each columns as column (column)}
            <td data-column={column}>
              {#if column === 'id' && itemId}
                <code class="row-id">{itemId}</code>
              {:else}
                <DataValue value={row[column]} />
              {/if}
            </td>
          {/each}
        </tr>
        {#if itemId && backlinks[itemId]?.length}
          <tr class="backlink-row">
            <td colspan={columns.length}>
              <span class="backlink-label">realized by</span>
              {#each backlinks[itemId] as backlink (backlink.from + backlink.type)}
                <span class="backlink-edge">
                  <LinkChip target={backlink.from} />
                  <span class="backlink-type">{backlink.type}</span>
                </span>
              {/each}
            </td>
          </tr>
        {/if}
      {/each}
    </tbody>
  </table>
</div>

<style>
  .table-wrap {
    overflow-x: auto;
    border: 1px solid var(--line);
    border-radius: var(--radius);
  }
  .data-table {
    border-collapse: collapse;
    width: 100%;
    font-size: 0.88rem;
  }
  th,
  td {
    text-align: left;
    padding: 0.5rem 0.7rem;
    border-bottom: 1px solid var(--line);
    vertical-align: top;
  }
  th {
    background: var(--th);
    font-size: 0.68rem;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 700;
    white-space: nowrap;
    position: sticky;
    top: 0;
  }
  tbody tr:last-child td {
    border-bottom: none;
  }
  td[data-column='id'] {
    white-space: nowrap;
  }
  .row-id {
    background: var(--chipbg);
    color: var(--accent);
    border-radius: 6px;
    padding: 0.1em 0.4em;
    font-size: 0.82em;
  }
  tr.has-anchor {
    scroll-margin-top: 5rem;
  }
  tr.has-anchor:target td {
    background: var(--chip-info-bg);
  }

  .backlink-row td {
    background: var(--quote);
    padding-top: 0.35rem;
    padding-bottom: 0.5rem;
  }
  .backlink-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--muted);
    font-weight: 700;
    margin-right: 0.5rem;
  }
  .backlink-edge {
    display: inline-flex;
    align-items: baseline;
    gap: 0.3rem;
    margin-right: 0.7rem;
  }
  .backlink-type {
    font-size: 0.7rem;
    color: var(--muted);
    font-style: italic;
  }
</style>
