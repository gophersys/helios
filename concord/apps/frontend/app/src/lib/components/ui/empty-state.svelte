<script lang="ts">
  import { Inbox, type Icon } from 'lucide-svelte';
  import type { ComponentType, Snippet } from 'svelte';

  let {
    message = 'No items found',
    icon: IconComponent = Inbox,
    children
  }: {
    message?: string;
    icon?: ComponentType<Icon>;
    children?: Snippet;
  } = $props();
</script>

<div class="card flex flex-col items-center justify-center py-12">
  <IconComponent size={32} class="text-text-tertiary" strokeWidth={1.5} />
  <p class="mt-3 text-sm text-text-tertiary">{message}</p>
  {#if children}
    {@render children()}
  {/if}
</div>
