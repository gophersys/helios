<script lang="ts">
  import { untrack } from 'svelte';
  import type { Snippet } from 'svelte';
  import { ChevronRight } from 'lucide-svelte';

  interface Props {
    title: string;
    count?: number;
    defaultOpen?: boolean;
    children: Snippet;
  }

  let { title, count, defaultOpen = false, children }: Props = $props();

  let isOpen = $state(untrack(() => defaultOpen));
</script>

<div class="border border-border rounded-lg overflow-hidden">
  <button
    onclick={() => isOpen = !isOpen}
    class="w-full flex items-center gap-2 px-3 py-2 bg-surface-2 hover:bg-surface-2/80 text-left"
  >
    <ChevronRight class="w-4 h-4 text-text-tertiary transition-transform {isOpen ? 'rotate-90' : ''}" />
    <span class="text-sm font-medium text-text-primary">{title}</span>
    {#if count !== undefined}
      <span class="px-1.5 py-0.5 rounded text-2xs bg-surface-1 text-text-secondary">{count}</span>
    {/if}
  </button>
  {#if isOpen}
    <div class="p-3 bg-surface-1">
      {@render children()}
    </div>
  {/if}
</div>
