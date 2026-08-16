<script lang="ts">
  import { Search, X } from 'lucide-svelte';

  let {
    value = $bindable(''),
    placeholder = 'Search...',
    class: className = '',
  }: {
    value?: string;
    placeholder?: string;
    class?: string;
  } = $props();
</script>

<div class="relative {className}">
  <Search size={14} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-tertiary pointer-events-none" />
  <input
    type="text"
    bind:value
    {placeholder}
    class="w-full rounded-md border border-border bg-surface-0 py-1.5 pl-8 pr-7 text-xs text-text-primary placeholder:text-text-tertiary transition-colors hover:border-text-tertiary focus:border-accent focus:outline-hidden"
  />
  {#if value}
    <button
      type="button"
      onclick={() => value = ''}
      class="absolute right-2 top-1/2 -translate-y-1/2 text-text-tertiary hover:text-text-secondary"
    >
      <X size={12} />
    </button>
  {/if}
</div>
