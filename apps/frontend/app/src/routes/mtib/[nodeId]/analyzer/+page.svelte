<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';

  const nodeId = $derived($page.params.nodeId);

  onMount(() => {
    // Redirect to new capture page
    goto(`/mtib/${nodeId}/analyzer/new`, { replaceState: true });
  });
</script>

<div class="flex items-center justify-center py-12">
  <span class="text-text-secondary">Redirecting to analyzer...</span>
</div>
