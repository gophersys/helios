<script lang="ts">
  import type { Snippet } from 'svelte';

  interface InfoItem {
    label: string;
    value: Snippet | string;
    mono?: boolean;
  }

  interface Props {
    items: InfoItem[];
  }

  let { items }: Props = $props();
</script>

<div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
  {#each items as item, i}
    {#if i > 0}
      <span class="text-border">|</span>
    {/if}
    <span class="text-text-secondary">{item.label}:</span>
    {#if typeof item.value === 'string'}
      <span class="text-text-primary {item.mono ? 'font-mono' : ''}">{item.value}</span>
    {:else}
      {@render item.value()}
    {/if}
  {/each}
</div>
