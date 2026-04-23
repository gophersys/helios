<script lang="ts">
  import { fade } from 'svelte/transition';
  import { loaderIn, loaderOut, contentIn } from '$lib/utils/transitions';
  import PlanesLoader from './planes-loader.svelte';

  interface Props {
    /** Whether content is loading */
    loading: boolean;
    /** Optional loading message */
    message?: string;
    /** Content to render (children) */
    children: any;
  }

  let { loading, message = 'Loading...', children }: Props = $props();
</script>

{#if loading}
  <div class="page-loader" in:fade={loaderIn} out:fade={loaderOut}>
    <PlanesLoader size="md" planeCount={5} message={message} />
  </div>
{:else}
  <div in:fade={contentIn}>
    {@render children()}
  </div>
{/if}

<style>
  .page-loader {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 300px;
    width: 100%;
  }
</style>
