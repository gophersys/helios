<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    ArrowLeft,
    BookOpen,
    ChevronRight,
    Clock,
    Cpu,
    FileCode,
    Layers,
    Package,
    Play,
    Timer,
    Zap,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { TestCatalogSummary, TestCatalog, TestStage, TestDefinition } from '$lib/types/models';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';

  const auth = getAuth();

  let catalogs = $state<TestCatalogSummary[]>([]);
  let selectedProduct = $state<string | null>(null);
  let catalog = $state<TestCatalog | null>(null);
  let selectedStage = $state<string | null>(null);
  let loading = $state(true);
  let catalogLoading = $state(false);
  let error = $state<string | null>(null);

  // Filter tests by selected stage
  const filteredTests = $derived(
    catalog?.tests.filter(t => !selectedStage || t.stage === selectedStage) ?? []
  );

  // Stage list with counts
  const stageList = $derived.by(() => {
    if (!catalog) return [];
    const stages = Object.entries(catalog.stages).map(([id, stage]) => ({
      id,
      ...stage,
      testCount: catalog.tests.filter(t => t.stage === id).length,
    }));
    return stages.sort((a, b) => a.name.localeCompare(b.name));
  });

  function getTriggerIcon(trigger: string) {
    switch (trigger) {
      case 'pr': return Zap;
      case 'cron': return Timer;
      case 'manual': return Play;
      default: return Play;
    }
  }

  function formatDuration(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
  }

  async function fetchCatalogs(): Promise<void> {
    try {
      const res = await apiFetch<ApiResponse<TestCatalogSummary[]>>('/v2/validation/catalog');
      catalogs = res.data;
      error = null;

      // Auto-select first catalog if only one
      if (catalogs.length === 1) {
        selectProduct(catalogs[0].product);
      }
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load catalogs';
    } finally {
      loading = false;
    }
  }

  async function selectProduct(product: string): Promise<void> {
    selectedProduct = product;
    selectedStage = null;
    catalogLoading = true;

    try {
      const res = await apiFetch<ApiResponse<TestCatalog>>(`/v2/validation/catalog/${product}`);
      catalog = res.data;
      error = null;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load catalog';
    } finally {
      catalogLoading = false;
    }
  }

  function selectStage(stageId: string | null): void {
    selectedStage = selectedStage === stageId ? null : stageId;
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.Validation.View')) {
      goto('/');
      return;
    }
    fetchCatalogs();
  });
</script>

<svelte:head>
  <title>Test Catalog — Validation — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <!-- Back link -->
  <button
    onclick={() => goto('/validation')}
    class="flex items-center gap-1 text-xs text-text-tertiary hover:text-text-primary transition-colors mb-3"
  >
    <ArrowLeft size={14} />
    Validation
  </button>

  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-lg font-semibold text-text-primary flex items-center gap-2">
        <BookOpen size={20} class="text-accent" />
        Test Catalog
      </h1>
      <p class="text-xs text-text-tertiary mt-1">
        Browse test definitions by product and stage
      </p>
    </div>
  </div>

  {#if loading}
    <LoadingState message="Loading catalogs..." />
  {:else if error && !catalog}
    <ErrorAlert message={error} />
  {:else}
    <ErrorAlert message={error} />

    <div class="flex gap-6">
      <!-- Left sidebar: Product + Stage selection -->
      <div class="w-64 flex-shrink-0 space-y-4">
        <!-- Product selector -->
        <div class="card">
          <h3 class="text-xs font-medium text-text-tertiary uppercase tracking-wider mb-3">Products</h3>
          <div class="space-y-1">
            {#each catalogs as cat (cat.product)}
              <button
                onclick={() => selectProduct(cat.product)}
                class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-left transition-colors
                  {selectedProduct === cat.product
                    ? 'bg-accent-muted border border-accent/30 text-text-primary'
                    : 'hover:bg-surface-1 text-text-secondary'
                  }"
              >
                <div class="flex items-center gap-2">
                  <Package size={14} class="text-text-tertiary" />
                  <span class="text-sm font-medium">{cat.product}</span>
                </div>
                <span class="text-2xs text-text-tertiary">{cat.testCount}</span>
              </button>
            {/each}
          </div>
        </div>

        <!-- Stage selector (when product selected) -->
        {#if catalog}
          <div class="card">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-xs font-medium text-text-tertiary uppercase tracking-wider">Stages</h3>
              <span class="text-2xs text-text-tertiary">v{catalog.version}</span>
            </div>
            <div class="space-y-1">
              <button
                onclick={() => selectStage(null)}
                class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-left transition-colors
                  {selectedStage === null
                    ? 'bg-accent-muted border border-accent/30 text-text-primary'
                    : 'hover:bg-surface-1 text-text-secondary'
                  }"
              >
                <span class="text-sm">All Tests</span>
                <span class="text-2xs text-text-tertiary">{catalog.testCount}</span>
              </button>

              {#each stageList as stage (stage.id)}
                {@const TriggerIcon = getTriggerIcon(stage.trigger)}
                <button
                  onclick={() => selectStage(stage.id)}
                  class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-left transition-colors
                    {selectedStage === stage.id
                      ? 'bg-accent-muted border border-accent/30 text-text-primary'
                      : 'hover:bg-surface-1 text-text-secondary'
                    }"
                >
                  <div class="flex items-center gap-2">
                    <TriggerIcon size={12} class="text-text-tertiary" />
                    <span class="text-sm">{stage.name}</span>
                  </div>
                  <div class="flex items-center gap-2">
                    {#if stage.blocksMerge}
                      <span class="text-2xs px-1.5 py-0.5 rounded bg-warning-muted text-warning font-medium">gate</span>
                    {/if}
                    <span class="text-2xs text-text-tertiary">{stage.testCount}</span>
                  </div>
                </button>
              {/each}
            </div>
          </div>
        {/if}
      </div>

      <!-- Right panel: Test list -->
      <div class="flex-1 min-w-0">
        {#if catalogLoading}
          <LoadingState message="Loading catalog..." />
        {:else if catalog}
          <!-- Stage info header (when stage selected) -->
          {#if selectedStage}
            {@const stage = catalog.stages[selectedStage]}
            {#if stage}
              <div class="card mb-4 bg-surface-1">
                <div class="flex items-start justify-between">
                  <div>
                    <h2 class="text-base font-medium text-text-primary flex items-center gap-2">
                      <Layers size={16} class="text-accent" />
                      {stage.name}
                    </h2>
                    <p class="text-xs text-text-secondary mt-1">{stage.description}</p>
                  </div>
                  <div class="flex items-center gap-4 text-xs text-text-tertiary">
                    <span class="flex items-center gap-1">
                      <Clock size={12} />
                      {formatDuration(stage.timingBudgetS)}
                    </span>
                    <span class="flex items-center gap-1">
                      <FileCode size={12} />
                      {filteredTests.length} tests
                    </span>
                  </div>
                </div>
              </div>
            {/if}
          {/if}

          <!-- Test list -->
          <div class="card overflow-hidden">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-border text-left">
                  <th class="px-4 py-2 text-xs font-medium text-text-tertiary uppercase tracking-wider">Test ID</th>
                  <th class="px-4 py-2 text-xs font-medium text-text-tertiary uppercase tracking-wider">Name</th>
                  <th class="px-4 py-2 text-xs font-medium text-text-tertiary uppercase tracking-wider">Stage</th>
                  <th class="px-4 py-2 text-xs font-medium text-text-tertiary uppercase tracking-wider text-right">Timeout</th>
                  <th class="px-4 py-2 text-xs font-medium text-text-tertiary uppercase tracking-wider">Hardware</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-border">
                {#each filteredTests as test (test.id)}
                  <tr class="hover:bg-surface-1 transition-colors">
                    <td class="px-4 py-3">
                      <span class="font-mono text-xs text-accent">{test.id}</span>
                    </td>
                    <td class="px-4 py-3">
                      <div>
                        <span class="font-mono text-text-primary">{test.name}</span>
                        <p class="text-2xs text-text-tertiary mt-0.5 line-clamp-1">{test.description}</p>
                      </div>
                    </td>
                    <td class="px-4 py-3">
                      <span class="inline-flex items-center gap-1 rounded bg-surface-2 px-2 py-0.5 text-2xs font-medium text-text-secondary">
                        {test.stage}
                      </span>
                    </td>
                    <td class="px-4 py-3 text-right">
                      <span class="text-xs text-text-secondary tabular-nums">{test.timeoutS}s</span>
                    </td>
                    <td class="px-4 py-3">
                      {#if test.hardware.length > 0}
                        <div class="flex flex-wrap gap-1">
                          {#each test.hardware as hw}
                            <span class="inline-flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-tertiary">
                              <Cpu size={10} />
                              {hw}
                            </span>
                          {/each}
                        </div>
                      {:else}
                        <span class="text-2xs text-text-tertiary">—</span>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>

            {#if filteredTests.length === 0}
              <div class="px-4 py-8 text-center text-text-tertiary text-sm">
                No tests found for this stage.
              </div>
            {/if}
          </div>
        {:else}
          <div class="card text-center py-12">
            <BookOpen size={48} class="mx-auto text-text-tertiary opacity-50 mb-4" />
            <p class="text-sm text-text-tertiary">
              Select a product to view its test catalog.
            </p>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>
