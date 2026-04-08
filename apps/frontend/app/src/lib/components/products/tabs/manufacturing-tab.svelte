<script lang="ts">
  import { onMount } from 'svelte';
  import {
    Factory, Settings, Zap, Cpu, ShieldCheck, Package,
    CheckCircle2, XCircle, AlertTriangle, Loader2,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import ManufacturingConfigWizard from '../manufacturing-config-wizard.svelte';
  import type { Product, BoardRevision, ManufacturingConfig } from '$lib/types/models';
  import { api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';

  interface Props {
    product: Product;
    canManage: boolean;
    onRefresh: () => void;
  }

  let { product, canManage, onRefresh }: Props = $props();

  const auth = getAuth();
  const canConfigureMfg = $derived(auth.hasPermission('manufacturing:manage'));

  let config = $state<ManufacturingConfig | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let wizardOpen = $state(false);

  const revisions = $derived(
    (product.boards || []).flatMap((b) => b.revisions || [])
  );

  const enabledStages = $derived(
    config?.stages?.filter((s) => s.enabled) ?? []
  );

  const firmwareSourceLabel = $derived.by(() => {
    if (!config) return '';
    switch (config.firmwareSource) {
      case 'latest_build': return 'Latest Build';
      case 'specific_version': return 'Specific Version';
      case 'manual_upload': return 'Manual Upload';
      default: return config.firmwareSource;
    }
  });

  async function loadConfig() {
    loading = true;
    error = null;
    try {
      const res = await api.get<ApiResponse<ManufacturingConfig>>(`/v2/products/${product.id}/manufacturing`);
      config = res.data;
    } catch (err: unknown) {
      // 404 means no config exists — that's fine
      if (err instanceof Error && err.message.includes('404')) {
        config = null;
      } else {
        error = err instanceof Error ? err.message : 'Failed to load manufacturing config';
      }
    } finally {
      loading = false;
    }
  }

  function openWizard() {
    wizardOpen = true;
  }

  function onWizardSaved() {
    wizardOpen = false;
    loadConfig();
    onRefresh();
  }

  onMount(() => {
    loadConfig();
  });
</script>

{#if loading}
  <div class="flex items-center justify-center py-12">
    <Loader2 size={20} class="animate-spin text-text-tertiary" />
    <span class="ml-2 text-sm text-text-tertiary">Loading manufacturing config...</span>
  </div>
{:else if error}
  <ErrorAlert message={error} />
{:else if !config}
  <!-- Not configured state -->
  <div class="py-8 text-center">
    <Factory size={32} class="mx-auto mb-3 text-text-tertiary opacity-40" />
    <p class="text-sm font-medium text-text-secondary">Manufacturing not configured</p>
    <p class="mt-1 text-2xs text-text-tertiary">
      Set up manufacturing stages, firmware source, and pass criteria for this product.
    </p>
    {#if canConfigureMfg}
      <button
        onclick={openWizard}
        class="mt-4 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
      >
        Configure Manufacturing
      </button>
    {/if}
  </div>
{:else}
  <!-- Config summary -->
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="inline-flex items-center rounded-full px-2 py-0.5 text-2xs font-medium {config.enabled ? 'bg-success-muted text-success' : 'bg-surface-2 text-text-tertiary'}">
          {config.enabled ? 'Enabled' : 'Disabled'}
        </span>
        <span class="text-2xs text-text-tertiary">Board revision: {revisions.find((r) => r.id === config?.boardRevisionId)?.version ?? 'Unknown'}</span>
      </div>
      {#if canConfigureMfg}
        <button
          onclick={openWizard}
          class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-surface-2"
        >
          <Settings size={14} />
          Edit Configuration
        </button>
      {/if}
    </div>

    <!-- Stages -->
    <div class="rounded-xl border border-border bg-surface-1 p-4">
      <h4 class="mb-3 text-xs font-semibold uppercase tracking-wide text-text-tertiary">Manufacturing Stages</h4>
      <div class="grid gap-3 sm:grid-cols-3">
        {#each config.stages as stage}
          <div class="rounded-lg border border-border bg-surface-0 p-3">
            <div class="flex items-center gap-2">
              {#if stage.name === 'electrical'}
                <Zap size={14} class="text-warning" />
              {:else if stage.name === 'flash'}
                <Cpu size={14} class="text-accent" />
              {:else}
                <ShieldCheck size={14} class="text-success" />
              {/if}
              <span class="text-sm font-medium text-text-primary capitalize">{stage.name}</span>
              {#if stage.enabled}
                <CheckCircle2 size={12} class="ml-auto text-success" />
              {:else}
                <XCircle size={12} class="ml-auto text-text-tertiary" />
              {/if}
            </div>
          </div>
        {/each}
      </div>
    </div>

    <!-- Firmware Source -->
    <div class="rounded-xl border border-border bg-surface-1 p-4">
      <h4 class="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">Firmware Source</h4>
      <div class="flex items-center gap-2">
        <Package size={14} class="text-text-secondary" />
        <span class="text-sm text-text-primary">{firmwareSourceLabel}</span>
      </div>
    </div>

    <!-- Pass Criteria -->
    {#if config.passCriteria}
      <div class="rounded-xl border border-border bg-surface-1 p-4">
        <h4 class="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">Pass Criteria</h4>
        <div class="grid gap-2 text-sm">
          <div class="flex items-center justify-between">
            <span class="text-text-secondary">All stages must pass</span>
            <span class="text-text-primary">{config.passCriteria.allStagesMustPass ? 'Yes' : 'No'}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-text-secondary">Max retries per unit</span>
            <span class="text-text-primary">{config.passCriteria.maxRetriesPerUnit}</span>
          </div>
        </div>
      </div>
    {/if}

    <!-- Personalization -->
    {#if config.personalizationConfig}
      <div class="rounded-xl border border-border bg-surface-1 p-4">
        <h4 class="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">Personalization</h4>
        <div class="grid gap-2 text-sm">
          <div class="flex items-center justify-between">
            <span class="text-text-secondary">CoreOps URL</span>
            <span class="text-text-primary font-mono text-2xs">{config.personalizationConfig.coreOpsUrl}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-text-secondary">Device type / variant</span>
            <span class="text-text-primary">{config.personalizationConfig.deviceType} / {config.personalizationConfig.deviceVariant}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-text-secondary">Default carrier</span>
            <span class="text-text-primary">{config.personalizationConfig.defaultCarrier}</span>
          </div>
        </div>
      </div>
    {/if}
  </div>
{/if}

<!-- Wizard modal -->
<ManufacturingConfigWizard
  open={wizardOpen}
  productId={product.id}
  {revisions}
  existingConfig={config}
  onClose={() => (wizardOpen = false)}
  onSaved={onWizardSaved}
/>
