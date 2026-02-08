<script lang="ts" generics="T">
  import type { Snippet } from 'svelte';

  interface Column<T> {
    key: string;
    header: string;
    render: Snippet<[T]>;
    className?: string;
  }

  interface Props {
    columns: Column<T>[];
    data: T[];
    keyFn: (item: T) => string;
    onRowClick?: (item: T) => void;
    emptyMessage?: string;
  }

  let { columns, data, keyFn, onRowClick, emptyMessage = 'No items found' }: Props = $props();

  function handleKeyDown(e: KeyboardEvent, item: T) {
    if (onRowClick && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onRowClick(item);
    }
  }
</script>

<div class="table-wrapper">
  <table class="table">
    <thead>
      <tr class="border-b border-border">
        {#each columns as col}
          <th class="table-header {col.className ?? ''}">
            {col.header}
          </th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#if data.length === 0}
        <tr>
          <td colspan={columns.length} class="table-empty">
            {emptyMessage}
          </td>
        </tr>
      {:else}
        {#each data as item (keyFn(item))}
          <tr
            class="table-row {onRowClick ? 'table-row-interactive' : ''}"
            onclick={() => onRowClick?.(item)}
            onkeydown={(e) => handleKeyDown(e, item)}
            tabindex={onRowClick ? 0 : undefined}
            role={onRowClick ? 'button' : undefined}
          >
            {#each columns as col}
              <td class="table-cell {col.className ?? ''}">
                {@render col.render(item)}
              </td>
            {/each}
          </tr>
        {/each}
      {/if}
    </tbody>
  </table>
</div>
