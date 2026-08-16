<script lang="ts">
  interface Props {
    labels: Record<string, string>;
    truncateAt?: number;
  }

  let { labels, truncateAt = 30 }: Props = $props();

  const entries = $derived(Object.entries(labels));

  function truncate(text: string, max: number): string {
    return text.length > max ? text.slice(0, max) + '...' : text;
  }
</script>

{#if entries.length === 0}
  <span class="text-xs text-text-tertiary">No labels</span>
{:else}
  <div class="flex flex-wrap gap-1">
    {#each entries as [key, value]}
      {@const full = `${key}=${value}`}
      <span
        class="inline-flex items-center px-1.5 py-0.5 rounded text-2xs bg-surface-2 text-text-secondary font-mono"
        title={full}
      >
        {truncate(key, truncateAt)}={truncate(value, truncateAt)}
      </span>
    {/each}
  </div>
{/if}
