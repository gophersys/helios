<script lang="ts" generics="T">
  import type { Snippet } from 'svelte';
  import Skeleton from './skeleton.svelte';
  import EmptyState from './empty-state.svelte';

  let {
    items,
    loading = false,
    emptyMessage = 'No items found',
    children,
  }: {
    items: T[];
    loading?: boolean;
    emptyMessage?: string;
    children: Snippet<[T, number]>;
  } = $props();
</script>

{#if loading}
  <div class="divide-y divide-border-subtle">
    {#each Array(5) as _}
      <div class="px-4 py-3">
        <Skeleton width="60%" height="0.875rem" />
        <div class="mt-2">
          <Skeleton width="40%" height="0.75rem" />
        </div>
      </div>
    {/each}
  </div>
{:else if items.length === 0}
  <EmptyState message={emptyMessage} />
{:else}
  <div>
    {#each items as item, index}
      <div class="border-b border-border-subtle last:border-0 hover:bg-surface-2/50 transition-colors">
        {@render children(item, index)}
      </div>
    {/each}
  </div>
{/if}
