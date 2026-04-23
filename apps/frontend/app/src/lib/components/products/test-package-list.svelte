<script lang="ts">
  import { ChevronDown, ChevronRight, Rocket, Package, Wrench } from 'lucide-svelte';
  import { api } from '$lib/api';
  import { getAuth } from '$lib/stores/auth.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import { formatTimeAgo } from '$lib/utils/formatting';
  import type { TestPackage } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  interface Props {
    productId: string;
    packageType: 'VALIDATION' | 'MANUFACTURING';
    boardRevisionId?: string;
    onRefresh?: () => void;
  }

  let { productId, packageType, boardRevisionId = undefined, onRefresh }: Props = $props();

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('products:manage'));

  let packages = $state<TestPackage[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let expanded = $state(false);
  let releasing = $state<string | null>(null);
  let confirmId = $state<string | null>(null);
  let deletingId = $state<string | null>(null);
  let successMessage = $state<string | null>(null);

  async function fetchPackages(): Promise<void> {
    loading = true;
    error = null;
    try {
      let url = `/v2/products/${productId}/test-packages?type=${packageType}&limit=20`;
      if (boardRevisionId) {
        url += `&boardRevisionId=${boardRevisionId}`;
      }
      const res = await api.get<ApiResponse<{ data: TestPackage[]; pagination: unknown }>>(url);
      packages = res.data?.data ?? (Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load test packages';
    } finally {
      loading = false;
    }
  }

  async function handleRelease(id: string): Promise<void> {
    releasing = id;
    confirmId = null;
    error = null;
    successMessage = null;
    try {
      const res = await api.post<ApiResponse<TestPackage>>(
        `/v2/products/${productId}/test-packages/${id}/release`
      );
      successMessage = `Released as v${res.data.releasedVersion}`;
      await fetchPackages();
      onRefresh?.();
      setTimeout(() => { successMessage = null; }, 4000);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to release package';
    } finally {
      releasing = null;
    }
  }

  async function handleDelete(id: string): Promise<void> {
    error = null;
    try {
      await api.delete(`/v2/products/${productId}/test-packages/${id}`);
      deletingId = null;
      await fetchPackages();
      onRefresh?.();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete package';
      deletingId = null;
    }
  }

  function displayVersion(pkg: TestPackage): string {
    if (pkg.status === 'RELEASED' && pkg.releasedVersion) return pkg.releasedVersion;
    return pkg.version;
  }

  function truncateSha(sha: string | null): string {
    if (!sha) return '';
    return sha.slice(0, 7);
  }

  $effect(() => {
    // Re-fetch when productId, packageType, or boardRevisionId changes
    productId;
    packageType;
    boardRevisionId;
    fetchPackages();
  });
</script>

<div class="mt-2">
  <!-- Collapsible header -->
  <button
    onclick={() => (expanded = !expanded)}
    class="flex w-full items-center gap-2 rounded-lg px-1 py-1.5 text-left hover:bg-surface-2 transition-colors"
  >
    {#if expanded}
      <ChevronDown size={14} class="shrink-0 text-text-tertiary" />
    {:else}
      <ChevronRight size={14} class="shrink-0 text-text-tertiary" />
    {/if}
    <Package size={14} class="shrink-0 text-text-tertiary" />
    <span class="text-xs font-medium text-text-secondary">Version History</span>
    {#if !loading}
      <span class="text-2xs text-text-tertiary">({packages.length})</span>
    {/if}
  </button>

  {#if expanded}
    <div class="mt-1 rounded-lg border border-border bg-surface-0 overflow-hidden">
      <ErrorAlert message={error} />

      {#if successMessage}
        <div class="flex items-center gap-2 bg-success-muted px-4 py-2">
          <Rocket size={14} class="text-success" />
          <span class="text-xs font-medium text-success">{successMessage}</span>
        </div>
      {/if}

      {#if loading}
        <div class="py-6 text-center text-sm text-text-tertiary">Loading...</div>
      {:else if packages.length === 0}
        <div class="py-6 text-center text-sm text-text-tertiary">No packages uploaded yet.</div>
      {:else}
        <div class="table-wrapper">
          <table class="table">
            <thead>
              <tr class="border-b border-border">
                <th class="table-header">Version</th>
                <th class="table-header">Status</th>
                <th class="table-header">Tests</th>
                <th class="table-header">Commit</th>
                <th class="table-header">Message</th>
                <th class="table-header">Time</th>
                {#if canManage}
                  <th class="table-header text-right">Actions</th>
                {/if}
              </tr>
            </thead>
            <tbody>
              {#each packages as pkg (pkg.id)}
                <tr class="table-row">
                  <td class="table-cell">
                    <code class="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-2xs text-text-primary">
                      {displayVersion(pkg)}
                    </code>
                  </td>
                  <td class="table-cell">
                    <StatusBadge status={pkg.status} />
                  </td>
                  <td class="table-cell text-text-secondary text-2xs">
                    {pkg.testCount}
                  </td>
                  <td class="table-cell">
                    {#if pkg.gitSha}
                      <code class="font-mono text-2xs text-text-secondary">
                        {truncateSha(pkg.gitSha)}{pkg.gitDirty ? '*' : ''}
                      </code>
                    {:else}
                      <span class="text-text-tertiary text-2xs">-</span>
                    {/if}
                  </td>
                  <td class="table-cell text-2xs text-text-secondary max-w-[200px] truncate" title={pkg.message ?? ''}>
                    {pkg.message ?? '-'}
                  </td>
                  <td class="table-cell text-2xs text-text-tertiary whitespace-nowrap">
                    {#if pkg.status === 'RELEASED' && pkg.releasedAt}
                      {formatTimeAgo(pkg.releasedAt)}
                    {:else}
                      {formatTimeAgo(pkg.createdAt)}
                    {/if}
                  </td>
                  {#if canManage}
                    <td class="table-cell text-right">
                      {#if pkg.status === 'DEVELOPMENT'}
                        {#if confirmId === pkg.id}
                          <div class="flex items-center justify-end gap-1">
                            <button
                              onclick={() => handleRelease(pkg.id)}
                              disabled={releasing === pkg.id}
                              class="rounded bg-success px-2 py-1 text-2xs font-medium text-white hover:bg-success/80 disabled:opacity-50"
                            >
                              {releasing === pkg.id ? 'Releasing...' : 'Confirm'}
                            </button>
                            <button
                              onclick={() => (confirmId = null)}
                              class="rounded px-2 py-1 text-2xs font-medium text-text-secondary hover:bg-surface-2"
                            >
                              Cancel
                            </button>
                          </div>
                        {:else if deletingId === pkg.id}
                          <div class="flex items-center justify-end gap-1">
                            <span class="text-2xs text-error">Delete?</span>
                            <button
                              onclick={() => handleDelete(pkg.id)}
                              class="rounded bg-error px-2 py-1 text-2xs font-medium text-white hover:bg-error/80"
                            >
                              Yes
                            </button>
                            <button
                              onclick={() => (deletingId = null)}
                              class="rounded px-2 py-1 text-2xs font-medium text-text-secondary hover:bg-surface-2"
                            >
                              Cancel
                            </button>
                          </div>
                        {:else}
                          <div class="flex items-center justify-end gap-2">
                            <button
                              onclick={() => (confirmId = pkg.id)}
                              class="flex items-center gap-1 rounded bg-accent px-2 py-1 text-2xs font-medium text-white hover:bg-accent-hover"
                            >
                              <Rocket size={12} />
                              Release
                            </button>
                            <button
                              onclick={() => (deletingId = pkg.id)}
                              class="text-2xs text-text-tertiary hover:text-error transition-colors"
                              title="Delete this development package"
                            >
                              Delete
                            </button>
                          </div>
                        {/if}
                      {:else if pkg.releasedAt}
                        <span class="text-2xs text-text-tertiary">{formatTimeAgo(pkg.releasedAt)}</span>
                      {/if}
                    </td>
                  {/if}
                </tr>
                {#if pkg.fixtureDesign}
                  <tr class="border-none">
                    <td colspan={canManage ? 7 : 6} class="px-4 pb-2 pt-0">
                      <a
                        href="/fixtures?designId={pkg.fixtureDesign.id}"
                        class="inline-flex items-center gap-1 text-2xs text-text-tertiary hover:text-accent transition-colors"
                      >
                        <Wrench size={10} />
                        Fixture: {pkg.fixtureDesign.name} v{pkg.fixtureDesign.revision}
                      </a>
                    </td>
                  </tr>
                {/if}
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}
</div>
