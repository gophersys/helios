<script lang="ts">
  import { Code, Save, CheckCircle, AlertCircle, Download, Upload, RefreshCw } from 'lucide-svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import { apiFetch, api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';

  interface Props {
    productId: string;
    productName: string;
    canManage: boolean;
  }

  let { productId, productName, canManage }: Props = $props();

  let recipe = $state('');
  let originalRecipe = $state('');
  let loading = $state(true);
  let saving = $state(false);
  let validating = $state(false);
  let error = $state<string | null>(null);
  let validationResult = $state<{ valid: boolean; errors: string[]; warnings: string[] } | null>(null);
  let hasChanges = $derived(recipe !== originalRecipe);

  async function loadRecipe() {
    loading = true;
    error = null;
    try {
      const res = await apiFetch<ApiResponse<{ content: string | null; slug: string }>>(`/v2/products/${productId}/recipe`);
      recipe = res.data?.content || '';
      originalRecipe = recipe;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load recipe';
    } finally {
      loading = false;
    }
  }

  async function saveRecipe() {
    saving = true;
    error = null;
    try {
      await api.put(`/v2/products/${productId}/recipe`, { content: recipe });
      originalRecipe = recipe;
      validationResult = null;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to save recipe';
    } finally {
      saving = false;
    }
  }

  async function validateRecipe() {
    validating = true;
    error = null;
    try {
      const res = await api.post<ApiResponse<{ valid: boolean; errors: string[]; warnings: string[] }>>(
        `/v2/products/${productId}/recipe/validate`,
        { content: recipe }
      );
      validationResult = res.data;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to validate recipe';
    } finally {
      validating = false;
    }
  }

  $effect(() => {
    loadRecipe();
  });
</script>

<div class="space-y-6">
  <ErrorAlert message={error} />

  <!-- Header -->
  <div class="flex items-center justify-between">
    <div>
      <h3 class="text-lg font-semibold text-text-primary">Build Recipe</h3>
      <p class="text-sm text-text-secondary mt-1">
        Bash script executed by the build service inside the product's devcontainer image.
        Uses the Concord Build SDK for version handling, CFW generation, and artifact naming.
      </p>
    </div>
    <div class="flex items-center gap-2">
      {#if canManage}
        <button
          onclick={validateRecipe}
          disabled={validating || !recipe}
          class="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary hover:bg-surface-2 disabled:opacity-50"
        >
          {#if validating}
            <RefreshCw class="h-4 w-4 animate-spin" />
          {:else}
            <CheckCircle class="h-4 w-4" />
          {/if}
          Validate
        </button>
        <button
          onclick={saveRecipe}
          disabled={saving || !hasChanges}
          class="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {#if saving}
            <RefreshCw class="h-4 w-4 animate-spin" />
          {:else}
            <Save class="h-4 w-4" />
          {/if}
          Save Recipe
        </button>
      {/if}
    </div>
  </div>

  <!-- Validation Result -->
  {#if validationResult}
    <div class="rounded-lg border p-4 {validationResult.valid ? 'border-success bg-success-muted' : 'border-error bg-error-muted'}">
      <div class="flex items-center gap-2 mb-2">
        {#if validationResult.valid}
          <CheckCircle class="h-5 w-5 text-success" />
          <span class="font-medium text-success">Recipe is valid</span>
        {:else}
          <AlertCircle class="h-5 w-5 text-error" />
          <span class="font-medium text-error">Recipe has errors</span>
        {/if}
      </div>
      {#each validationResult.errors as err}
        <p class="text-sm text-error ml-7">{err}</p>
      {/each}
      {#each validationResult.warnings as warn}
        <p class="text-sm text-warning ml-7">{warn}</p>
      {/each}
    </div>
  {/if}

  <!-- Code Editor -->
  <div class="rounded-lg border border-border bg-surface-0 overflow-hidden">
    <div class="flex items-center justify-between border-b border-border bg-surface-2 px-4 py-2">
      <div class="flex items-center gap-2">
        <Code class="h-4 w-4 text-text-tertiary" />
        <span class="text-sm font-medium text-text-secondary">build.sh</span>
      </div>
      {#if hasChanges}
        <span class="text-2xs text-warning">Unsaved changes</span>
      {/if}
    </div>
    {#if loading}
      <div class="p-8 text-center text-text-tertiary">Loading recipe...</div>
    {:else}
      <textarea
        bind:value={recipe}
        disabled={!canManage}
        spellcheck="false"
        class="w-full min-h-[500px] bg-surface-0 p-4 font-mono text-sm text-text-primary
               placeholder:text-text-tertiary focus:outline-none resize-y
               disabled:opacity-60 disabled:cursor-not-allowed"
        placeholder="#!/bin/bash&#10;source /app/sdk/concord-build.sh&#10;concord_init&#10;&#10;# Your build commands here...&#10;&#10;concord_finalize"
      ></textarea>
    {/if}
  </div>

  <!-- SDK Reference -->
  <div class="rounded-lg border border-border-subtle bg-surface-1 p-4">
    <h4 class="text-sm font-medium text-text-secondary mb-2">Concord Build SDK Reference</h4>
    <div class="grid grid-cols-2 gap-3 text-2xs font-mono text-text-tertiary">
      <div>
        <span class="text-accent">concord_init</span> — setup workspace, extract version, fix paths
      </div>
      <div>
        <span class="text-accent">concord_collect_hex</span> &lt;role&gt; &lt;path&gt; — register hex artifact
      </div>
      <div>
        <span class="text-accent">concord_collect_cfw</span> &lt;role&gt; &lt;path&gt; — generate CFW from signed bin
      </div>
      <div>
        <span class="text-accent">concord_finalize</span> — validate artifacts, generate build.json
      </div>
    </div>
    <div class="mt-3 text-2xs text-text-tertiary">
      Available env vars: <code class="text-accent">$CONCORD_BOARD</code>, <code class="text-accent">$CONCORD_VARIANT</code>,
      <code class="text-accent">$CONCORD_FW_TYPE</code>, <code class="text-accent">$CONCORD_REPO_DIR</code>,
      <code class="text-accent">$CONCORD_COMMS_SOC</code>, <code class="text-accent">$CONCORD_CONFIG_LOG</code>
    </div>
  </div>
</div>
