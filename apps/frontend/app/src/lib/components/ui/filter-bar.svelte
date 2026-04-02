<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    filters,
    children,
    class: className = '',
  }: {
    filters?: Snippet;
    children?: Snippet;
    class?: string;
  } = $props();
</script>

<div class="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface-1 p-3 {className}">
  {#if filters}{@render filters()}{/if}
  {#if children}{@render children()}{/if}
</div>
