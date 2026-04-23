<script lang="ts">
  import { onMount } from 'svelte';
  import { Settings, Save, X, AlertCircle, GitBranch } from 'lucide-svelte';
  import { apiFetch } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { Product } from '$lib/types/models';
  import type { ProductStageConfig } from '$lib/types/stages';
  import { listStageConfigs } from '$lib/services/stages';

  interface Props { product: any; canManage: boolean; onRefresh: () => void; }
  let { product, canManage, onRefresh }: Props = $props();

  let editing = $state(false);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let editName = $state('');
  let editDescription = $state('');
  let stageConfigs = $state<ProductStageConfig[]>([]);
  let loadingRepos = $state(true);

  const repoInfo = $derived.by(() => {
    const repos: { label: string; url: string; branch: string | null }[] = [];
    const seen = new Set<string>();
    for (const cfg of stageConfigs) {
      if (cfg.fwRepoUrl && !seen.has(cfg.fwRepoUrl)) { seen.add(cfg.fwRepoUrl); repos.push({ label: 'FW Repo', url: cfg.fwRepoUrl, branch: cfg.fwRepoBranch ?? null }); }
      if (cfg.mfgRepoUrl && !seen.has(cfg.mfgRepoUrl)) { seen.add(cfg.mfgRepoUrl); repos.push({ label: 'Mfg Repo', url: cfg.mfgRepoUrl, branch: cfg.mfgRepoBranch ?? null }); }
    }
    return repos;
  });

  onMount(async () => {
    try { stageConfigs = await listStageConfigs(product.id); } catch { /* non-critical */ } finally { loadingRepos = false; }
  });

  function startEdit() { editName = product.name; editDescription = product.description ?? ''; error = null; editing = true; }
  function cancelEdit() { editing = false; error = null; }

  async function saveChanges() {
    if (!editName.trim()) { error = 'Name is required'; return; }
    saving = true; error = null;
    try {
      await apiFetch<ApiResponse<Product>>(`/v2/products/${product.id}`, {
        method: 'PATCH', body: JSON.stringify({ name: editName.trim(), description: editDescription.trim() || null }),
      });
      editing = false; success = 'Settings saved'; setTimeout(() => (success = null), 3000); onRefresh();
    } catch (e: unknown) { error = e instanceof Error ? e.message : 'Failed to save'; }
    finally { saving = false; }
  }
</script>

<div class="space-y-6">
  {#if success}
    <div class="rounded-lg border border-success bg-surface-1 p-3 text-sm text-success">
      {success}
    </div>
  {/if}
  {#if error}
    <div class="flex items-center gap-2 rounded-lg border border-error bg-surface-1 p-3 text-sm text-error">
      <AlertCircle size={14} /> {error}
    </div>
  {/if}

  <!-- General Settings -->
  <section class="rounded-lg border border-border bg-surface-1 p-5">
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-2 text-(--color-text-primary)">
        <Settings size={16} />
        <h3 class="font-semibold text-sm">General Settings</h3>
      </div>
      {#if canManage && !editing}
        <button onclick={startEdit} class="btn btn-sm btn-ghost">
          Edit
        </button>
      {/if}
    </div>

    {#if editing}
      <div class="space-y-3">
        <label class="block">
          <span class="block text-xs font-medium text-(--color-text-tertiary) mb-1">Name</span>
          <input type="text" bind:value={editName} class="input input-md" />
        </label>
        <label class="block">
          <span class="block text-xs font-medium text-(--color-text-tertiary) mb-1">Description</span>
          <textarea bind:value={editDescription} rows={3} class="input input-md"></textarea>
        </label>
        <div class="flex justify-end gap-2">
          <button onclick={cancelEdit} class="btn btn-sm btn-ghost">
            <X size={14} /> Cancel
          </button>
          <button onclick={saveChanges} disabled={saving} class="btn btn-sm btn-primary">
            <Save size={14} /> {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    {:else}
      <dl class="space-y-2 text-sm">
        {#each [['Name', product.name], ['Description', product.description || 'No description'], ['Status', product.status === 'ACTIVE' ? 'Active' : 'Archived']] as [label, value]}
          <div class="flex items-baseline justify-between py-1 border-b border-border last:border-0">
            <dt class="text-xs text-(--color-text-tertiary)">{label}</dt>
            <dd class="text-(--color-text-primary)">{value}</dd>
          </div>
        {/each}
      </dl>
    {/if}
  </section>

  <!-- Repository Info -->
  <section class="rounded-lg border border-border bg-surface-1 p-5">
    <div class="flex items-center gap-2 text-(--color-text-primary) mb-4">
      <GitBranch size={16} />
      <h3 class="font-semibold text-sm">Repositories</h3>
    </div>
    {#if loadingRepos}
      <div class="h-12 animate-pulse rounded bg-surface-2"></div>
    {:else if repoInfo.length === 0}
      <p class="text-sm text-(--color-text-tertiary) text-center py-4">No repositories configured.</p>
    {:else}
      {#each repoInfo as repo}
        <div class="rounded-lg border border-border bg-surface-0 p-3 mb-2 last:mb-0">
          <div class="flex items-center justify-between">
            <span class="text-xs text-(--color-text-tertiary)">{repo.label}</span>
            {#if repo.branch}<span class="font-mono text-xs text-(--color-text-secondary)">{repo.branch}</span>{/if}
          </div>
          <code class="block truncate text-sm text-(--color-text-primary) mt-1">{repo.url}</code>
        </div>
      {/each}
    {/if}
  </section>
</div>
