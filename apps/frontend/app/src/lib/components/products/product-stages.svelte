<script lang="ts">
  import { onMount } from 'svelte';
  import type { ProductStageConfig } from '$lib/types/stages';
  import type { BoardRevision } from '$lib/types/models';
  import { listStageConfigs, initializeStages } from '$lib/services/stages';
  import StageCard from './stage-card.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import { Loader2 } from 'lucide-svelte';

  interface Props {
    productId: string;
    productName?: string;
    revisions?: BoardRevision[];
  }

  let { productId, productName = '', revisions = [] }: Props = $props();

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
    <div class="flex items-center gap-2 py-8 text-sm text-text-tertiary justify-center">
      <Loader2 size={16} class="animate-spin" /> Loading stages...
    </div>
  {:else if configs.length === 0}
    <div class="text-center py-8">
      <p class="text-sm text-text-secondary mb-2">No validation stages configured for {productName}.</p>
      <p class="text-2xs text-text-tertiary mb-4">Initialize the 5 standard stages, then enable the ones you need.</p>
      <button
        class="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        disabled={initializing}
        onclick={handleInitialize}
      >
        {initializing ? 'Initializing...' : 'Initialize Stages'}
      </button>
    </div>
  {:else}
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-semibold text-text-primary">Validation Stages</h3>
      <span class="text-2xs text-text-tertiary">
        {enabledCount} of {configs.length} enabled
      </span>
    </div>

    <div class="space-y-2">
      {#each [1, 2, 3, 4, 5] as stage}
        <StageCard
          {stage}
          config={getConfig(stage)}
          {productId}
          {revisions}
          onUpdated={loadConfigs}
        />
      {/each}
    </div>
  {/if}
</div>
