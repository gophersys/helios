<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';

  const buildId = $derived($page.params.id);

  onMount(() => {
    goto(`/builds/${buildId}`, { replaceState: true });
  });
</script>

<div class="flex items-center justify-center h-64 text-text-tertiary text-sm">
  Redirecting...
</div>
