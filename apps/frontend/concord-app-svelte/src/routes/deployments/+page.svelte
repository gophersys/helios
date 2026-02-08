<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Plus, X, Check } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import PageHeader from '$lib/components/ui/page-header.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import DeploymentCard from '$lib/components/deployments/deployment-card.svelte';
  import type { ConcordDeployment, Fixture } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('Concord.Admin.Deployments.Manage'));

  let deployments = $state<ConcordDeployment[]>([]);
  let fixtures = $state<Fixture[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Form state
  let showForm = $state(false);
  let formName = $state('');
  let formFixtureId = $state('');
  let submitting = $state(false);

  // Delete confirmation
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  // Polling
  let pollInterval = $state<ReturnType<typeof setInterval> | null>(null);

  const hasRunning = $derived(deployments.some(d => d.status === 'RUNNING'));

  async function fetchDeployments() {
    try {
      const res = await apiFetch<ApiResponse<{ data: ConcordDeployment[] }>>('/v2/deployments');
      const payload = res.data;
      deployments = Array.isArray(payload) ? payload : (payload as { data: ConcordDeployment[] }).data || [];
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load deployments';
    } finally {
      loading = false;
    }
  }

  async function fetchFixtures() {
    try {
      const res = await apiFetch<ApiResponse<{ data: Fixture[] }>>('/v2/fixtures');
      const payload = res.data;
      fixtures = Array.isArray(payload) ? payload : (payload as { data: Fixture[] }).data || [];
    } catch {
      // Non-critical
    }
  }

  function startPolling() {
    stopPolling();
    pollInterval = setInterval(() => {
      if (hasRunning) fetchDeployments();
    }, 10000);
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  $effect(() => {
    if (hasRunning) {
      startPolling();
    } else {
      stopPolling();
    }
  });

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.Deployments.View')) {
      goto('/');
      return;
    }
    fetchDeployments();
    fetchFixtures();
    return () => stopPolling();
  });

  function resetForm() {
    formName = '';
    formFixtureId = '';
    showForm = false;
  }

  $effect(() => {
    if (formFixtureId && !formName) {
      const f = fixtures.find(fx => fx.id === formFixtureId);
      if (f) formName = `${f.name}-deploy`;
    }
  });

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = null;
    submitting = true;

    const fixture = fixtures.find(f => f.id === formFixtureId);

    const body = {
      name: formName,
      fixtureId: formFixtureId || null,
      productId: fixture?.productId || null,
    };

    try {
      await api.post('/v2/deployments', body);
      resetForm();
      fetchDeployments();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to create deployment';
    } finally {
      submitting = false;
    }
  }

  async function handleDeploy(id: string) {
    error = null;
    try {
      await api.post(`/v2/deployments/${id}/deploy`);
      fetchDeployments();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to deploy';
    }
  }

  async function handleStop(id: string) {
    error = null;
    try {
      await api.post(`/v2/deployments/${id}/stop`);
      fetchDeployments();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to stop deployment';
    }
  }

  async function handleRestart(id: string) {
    error = null;
    try {
      await api.post(`/v2/deployments/${id}/restart`);
      fetchDeployments();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to restart deployment';
    }
  }

  function promptDelete(id: string) {
    const target = deployments.find((d) => d.id === id);
    deleteTarget = { id, name: target?.name || '' };
  }

  async function handleDelete(id: string) {
    error = null;
    try {
      await api.delete(`/v2/deployments/${id}`);
      fetchDeployments();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete deployment';
    }
  }
</script>

<svelte:head>
  <title>Deployments — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Deployments"
      description="Manage MTIB server deployments for fixtures."
    >
      {#snippet actions()}
        {#if canManage && !showForm}
          <button
            onclick={() => { resetForm(); showForm = true; }}
            class="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover"
          >
            <Plus size={16} />
            Create Deployment
          </button>
        {/if}
      {/snippet}
    </PageHeader>
  </div>

  {#if loading}
    <LoadingState message="Loading deployments..." />
  {:else}
    <ErrorAlert message={error} />

    <!-- Create form -->
    {#if showForm && canManage}
      <div class="mb-6 card card-md">
        <div class="mb-4 flex items-center justify-between">
          <h3 class="text-sm font-semibold text-text-primary">New deployment</h3>
          <button
            onclick={resetForm}
            class="rounded-lg p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
          >
            <X size={16} />
          </button>
        </div>

        <form onsubmit={handleSubmit}>
          <div class="mb-3 grid grid-cols-2 gap-3">
            <Select
              bind:value={formFixtureId}
              label="Fixture"
              placeholder="Select fixture..."
              options={fixtures.map(f => ({ value: f.id, label: `${f.name} (${f.type})` }))}
            />
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Name</span>
              <input
                type="text"
                required
                bind:value={formName}
                placeholder="e.g. mfg-fixture-01-deploy"
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </label>
          </div>
          <div class="flex gap-2">
            <button
              type="submit"
              disabled={submitting}
              class="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              <Check size={16} />
              {submitting ? 'Creating...' : 'Create'}
            </button>
            <button
              type="button"
              onclick={resetForm}
              class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    {/if}

    <!-- Deployments list -->
    {#if deployments.length === 0}
      <EmptyState message="No deployments yet" />
    {:else}
      <div class="space-y-3">
        {#each deployments as d (d.id)}
          <DeploymentCard
            deployment={d}
            {canManage}
            onDeploy={handleDeploy}
            onStop={handleStop}
            onRestart={handleRestart}
            onDelete={promptDelete}
          />
        {/each}
      </div>
    {/if}

    <ConfirmDeleteDialog
      open={!!deleteTarget}
      entityType="deployment"
      entityName={deleteTarget?.name || ''}
      onConfirm={() => { handleDelete(deleteTarget!.id); deleteTarget = null; }}
      onCancel={() => (deleteTarget = null)}
    />
  {/if}
</div>
