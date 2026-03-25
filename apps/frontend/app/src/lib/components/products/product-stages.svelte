<script lang="ts">
  import { onMount } from 'svelte';
  import type { ProductStageConfig } from '$lib/types/stages';
  import { listStageConfigs, initializeStages } from '$lib/services/stages';
  import StageCard from './stage-card.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';

  interface Props {
    productId: string;
    productName?: string;
  }

  let { productId, productName = '' }: Props = $props();

  let configs = $state<ProductStageConfig[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let initializing = $state(false);

  const enabledCount = $derived(configs.filter(c => c.enabled).length);

  onMount(async () => {
    await loadConfigs();
  });

  async function loadConfigs() {
    loading = true;
    error = null;
    try {
      configs = await listStageConfigs(productId);
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : 'Failed to load stage configs';
    } finally {
      loading = false;
    }
  }

  async function handleInitialize() {
    initializing = true;
    error = null;
    try {
      configs = await initializeStages(productId);
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : 'Failed to initialize stages';
    } finally {
      initializing = false;
    }
  }

  function getConfig(stage: number): ProductStageConfig | undefined {
    return configs.find(c => c.stage === stage);
  }
</script>

<div class="space-y-4">
  <ErrorAlert message={error} />

  {#if loading}
    <div class="flex items-center justify-center py-12">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-accent"></div>
    </div>
  {:else if configs.length === 0}
    <div class="text-center py-12">
      <p class="text-text-secondary mb-4">No stage configurations found for {productName}.</p>
      <button
        class="px-4 py-2 bg-accent text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
        disabled={initializing}
        onclick={handleInitialize}
      >
        {initializing ? 'Initializing...' : 'Initialize All 5 Stages'}
      </button>
    </div>
  {:else}
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-medium text-text-primary">Validation Stages</h3>
      <div class="text-sm text-text-tertiary">
        {enabledCount} of {configs.length} enabled
      </div>
    </div>

    <div class="space-y-3">
      {#each [1, 2, 3, 4, 5] as stage}
        <StageCard
          {stage}
          config={getConfig(stage)}
          {productId}
          onUpdated={loadConfigs}
        />
      {/each}
    </div>
  {/if}
</div>
