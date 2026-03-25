<script lang="ts">
  import { fade } from 'svelte/transition';
  import { loaderIn, loaderOut } from '$lib/utils/transitions';
  import PlanesLoader from './planes-loader.svelte';

  let { message = 'Loading...' }: { message?: string } = $props();
</script>

<div class="flex items-center justify-center py-8" aria-live="polite" role="status" in:fade={loaderIn} out:fade={loaderOut}>
  <PlanesLoader size="sm" planeCount={4} message={message} />
</div>
