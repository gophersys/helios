<script lang="ts">
  import { formatTimeAgo, formatDateTime } from '$lib/utils/formatting';

  let {
    datetime,
    prefix = '',
  }: {
    datetime: string | null;
    prefix?: string;
  } = $props();

  const display = $derived(datetime ? formatTimeAgo(datetime) : null);
  const full = $derived(datetime ? formatDateTime(datetime) : null);
</script>

{#if display && full}
  <span title={full} class="whitespace-nowrap">
    {#if prefix}{prefix} {/if}{display}
  </span>
{:else}
  <span class="text-text-tertiary">&mdash;</span>
{/if}
