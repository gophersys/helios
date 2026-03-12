<script lang="ts">
  import { onMount } from 'svelte';
  import { Layers, Zap, AlertCircle } from 'lucide-svelte';
  import type { ProductStageConfig } from '$lib/types/stages';
  import { STAGE_NAMES, STAGE_DESCRIPTIONS } from '$lib/types/stages';
  import { listStageConfigs, initializeStages } from '$lib/services/stages';
  import StageCard from '$lib/components/catalog/stage-card.svelte';

  interface Props {
    productId: string;
  }

  let { productId }: Props = $props();

  let stages = $state<ProductStageConfig[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let initializing = $state(false);

  const stageMap = $derived.by(() => {
    const map = new Map<number, ProductStageConfig>();
    for (const s of stages) map.set(s.stage, s);
    return map;
  });

  const allStageNumbers = [1, 2, 3, 4, 5];
  const configuredCount = $derived(stages.length);
  const needsInit = $derived(configuredCount < 5);

  async function loadStages(): Promise<void> {
    loading = true;
    error = null;
    try {
      stages = await listStageConfigs(productId);
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : 'Failed to load stage configs';
    } finally {
      loading = false;
    }
  }

  async function handleInitialize(): Promise<void> {
    initializing = true;
    error = null;
    try {
      stages = await initializeStages(productId);
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : 'Failed to initialize stages';
    } finally {
      initializing = false;
    }
  }

  onMount(() => { loadStages(); });

  $effect(() => {
    const _pid = productId;
    loadStages();
  });
</script>

<div class="space-y-4">
  <!-- Header -->
  <div class="flex items-center justify-between">
    <div class="flex items-center gap-2">
      <Layers size={18} class="text-[var(--color-text-secondary)]" />
      <h3 class="text-sm font-semibold text-[var(--color-text-primary)]">Validation Stages</h3>
      <span class="text-xs text-[var(--color-text-tertiary)]">{configuredCount}/5 configured</span>
    </div>
    {#if needsInit && !loading}
      <button onclick={handleInitialize} disabled={initializing}
        class="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50">
        <Zap size={14} />
        {initializing ? 'Initializing...' : 'Initialize All Stages'}
      </button>
    {/if}
  </div>

  {#if error}
    <div class="flex items-center gap-2 rounded-lg border border-[var(--color-error)] bg-[var(--color-surface-1)] p-3 text-sm text-[var(--color-error)]">
      <AlertCircle size={14} /> {error}
    </div>
  {/if}

  <!-- Loading skeleton -->
  {#if loading}
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {#each allStageNumbers as _}
        <div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-1)] p-4 space-y-3">
          <div class="flex items-center justify-between">
            <div class="h-5 w-20 animate-pulse rounded bg-[var(--color-surface-2)]"></div>
            <div class="h-4 w-14 animate-pulse rounded bg-[var(--color-surface-2)]"></div>
          </div>
          <div class="h-4 w-3/4 animate-pulse rounded bg-[var(--color-surface-2)]"></div>
          <div class="h-3 w-full animate-pulse rounded bg-[var(--color-surface-2)]"></div>
          <div class="h-3 w-2/3 animate-pulse rounded bg-[var(--color-surface-2)]"></div>
        </div>
      {/each}
    </div>
  {:else}
    <!-- Stage cards grid -->
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {#each allStageNumbers as stageNum (stageNum)}
        <StageCard
          stage={stageNum}
          config={stageMap.get(stageNum)}
          {productId}
          onUpdated={loadStages}
        />
      {/each}
    </div>
  {/if}
</div>
