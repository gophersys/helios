<script lang="ts">
  import { Code, Save, CheckCircle, AlertCircle, RefreshCw, Maximize2 } from 'lucide-svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import Card from '$lib/components/ui/card.svelte';
  import CodeEditor from '$lib/components/ui/code-editor.svelte';
  import BuildScriptEditor from './build-script-editor.svelte';
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
  let showFullEditor = $state(false);
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

  function handleFullEditorSave(content: string): void {
    recipe = content;
    originalRecipe = content;
    validationResult = null;
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
          onclick={() => (showFullEditor = true)}
          class="btn btn-sm btn-ghost"
          title="Open full editor"
          aria-label="Open full editor"
        >
          <Maximize2 class="h-4 w-4" />
          Full Editor
        </button>
        <button
          onclick={validateRecipe}
          disabled={validating || !recipe}
          class="btn btn-sm btn-secondary"
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
          class="btn btn-sm btn-primary"
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
  <Card size="sm" class="overflow-hidden p-0!">
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
      <CodeEditor
        value={recipe}
        onchange={(v) => (recipe = v)}
        readonly={!canManage}
        maxHeight="500px"
      />
    {/if}
  </Card>

  <!-- SDK Reference -->
  <Card title="Concord Build SDK Reference" size="sm">
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
  </Card>
</div>

<!-- Full-screen build script editor overlay -->
<BuildScriptEditor
  open={showFullEditor}
  {productId}
  {productName}
  initialContent={recipe}
  onClose={() => (showFullEditor = false)}
  onSave={handleFullEditorSave}
/>
