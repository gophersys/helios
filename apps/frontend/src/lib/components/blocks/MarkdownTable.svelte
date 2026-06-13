<script lang="ts">
  // A GFM markdown table (doc 12 §5: "tables (reuse/extend DataTable.svelte styling
  // — bordered, zebra-light, readable)"). The chrome below mirrors
  // DataTable.svelte's bordered wrapper, uppercase muted header, and row borders,
  // and adds light zebra striping for long tables. Cell content carries inline
  // markdown (links, code, emphasis), rendered through RichText. Column alignment
  // from the GFM `:---:` syntax is honored.
  import type { Tokens } from 'marked';
  import RichText from './RichText.svelte';

  let { token }: { token: Tokens.Table } = $props();

  function alignOf(index: number): 'left' | 'center' | 'right' {
    return token.align[index] ?? 'left';
  }
</script>

<div class="md-table-wrap">
  <table class="md-table">
    <thead>
      <tr>
        {#each token.header as cell, index (index)}
          <th style:text-align={alignOf(index)}><RichText text={cell.text} /></th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#each token.rows as row, rowIndex (rowIndex)}
        <tr>
          {#each row as cell, cellIndex (cellIndex)}
            <td style:text-align={alignOf(cellIndex)}><RichText text={cell.text} /></td>
          {/each}
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  /* Mirrors DataTable.svelte: a bordered, rounded, horizontally-scrollable wrapper
     so a wide table never breaks the reading column. */
  .md-table-wrap {
    overflow-x: auto;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    margin: 1.4rem 0;
  }
  .md-table {
    border-collapse: collapse;
    width: 100%;
    font-size: 0.92rem;
  }
  th,
  td {
    text-align: left;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid var(--line);
    vertical-align: top;
    line-height: 1.55;
  }
  /* Header: uppercase, letterspaced, muted — the DataTable header treatment. */
  th {
    background: var(--th);
    font-size: 0.68rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 700;
    white-space: nowrap;
  }
  /* Zebra-light: a faint Sage wash on alternate rows for scannability. */
  tbody tr:nth-child(even) td {
    background: color-mix(in srgb, var(--color-sage) 8%, transparent);
  }
  tbody tr:last-child td {
    border-bottom: none;
  }
  /* Inline code in a cell reads as a chip (inherits the global code styling but
     stays compact). */
  td :global(code),
  th :global(code) {
    font-size: 0.82em;
  }
</style>
