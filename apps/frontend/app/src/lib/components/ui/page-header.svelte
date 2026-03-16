<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    title,
    description,
    actions
  }: {
    title: string;
    description?: string;
    actions?: Snippet;
  } = $props();
</script>

<div class="flex items-center justify-between">
  <div>
    <h1 class="text-xl font-semibold text-text-primary">{title}</h1>
    {#if description}
      <p class="mt-1 text-sm text-text-secondary">{description}</p>
    {/if}
  </div>
  {#if actions}
    <div>
      {@render actions()}
    </div>
  {/if}
</div>
