<script lang="ts">
  import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-svelte';

  let {
    page,
    totalPages,
    onPageChange,
  }: {
    page: number;
    totalPages: number;
    onPageChange: (page: number) => void;
  } = $props();

  const pages = $derived.by(() => {
    const result: (number | '...')[] = [];
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) result.push(i);
      return result;
    }
    result.push(1);
    if (page > 3) result.push('...');
    const start = Math.max(2, page - 1);
    const end = Math.min(totalPages - 1, page + 1);
    for (let i = start; i <= end; i++) result.push(i);
    if (page < totalPages - 2) result.push('...');
    result.push(totalPages);
    return result;
  });

  const isFirst = $derived(page <= 1);
  const isLast = $derived(page >= totalPages);
</script>

{#if totalPages > 1}
  <nav class="flex items-center gap-1" aria-label="Pagination">
    <button
      type="button"
      disabled={isFirst}
      onclick={() => onPageChange(1)}
      class="inline-flex items-center justify-center rounded p-1 text-xs text-text-secondary transition-colors hover:bg-surface-2 disabled:opacity-30 disabled:pointer-events-none"
      aria-label="First page"
    >
      <ChevronsLeft size={14} />
    </button>
    <button
      type="button"
      disabled={isFirst}
      onclick={() => onPageChange(page - 1)}
      class="inline-flex items-center justify-center rounded p-1 text-xs text-text-secondary transition-colors hover:bg-surface-2 disabled:opacity-30 disabled:pointer-events-none"
      aria-label="Previous page"
    >
      <ChevronLeft size={14} />
    </button>

    {#each pages as p}
      {#if p === '...'}
        <span class="px-1 text-xs text-text-tertiary">...</span>
      {:else}
        <button
          type="button"
          onclick={() => onPageChange(p)}
          class="inline-flex min-w-6 items-center justify-center rounded px-1.5 py-0.5 text-xs font-medium transition-colors {p === page ? 'bg-accent text-white' : 'text-text-secondary hover:bg-surface-2'}"
          aria-current={p === page ? 'page' : undefined}
        >
          {p}
        </button>
      {/if}
    {/each}

    <button
      type="button"
      disabled={isLast}
      onclick={() => onPageChange(page + 1)}
      class="inline-flex items-center justify-center rounded p-1 text-xs text-text-secondary transition-colors hover:bg-surface-2 disabled:opacity-30 disabled:pointer-events-none"
      aria-label="Next page"
    >
      <ChevronRight size={14} />
    </button>
    <button
      type="button"
      disabled={isLast}
      onclick={() => onPageChange(totalPages)}
      class="inline-flex items-center justify-center rounded p-1 text-xs text-text-secondary transition-colors hover:bg-surface-2 disabled:opacity-30 disabled:pointer-events-none"
      aria-label="Last page"
    >
      <ChevronsRight size={14} />
    </button>
  </nav>
{/if}
