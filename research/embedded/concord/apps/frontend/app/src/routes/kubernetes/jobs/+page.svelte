<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import { getAuth } from '$lib/stores/auth.svelte';
  import StatusIndicator from '$lib/components/system/status-indicator.svelte';
  import ResourceAge from '$lib/components/system/resource-age.svelte';
  import NamespaceSelector from '$lib/components/system/namespace-selector.svelte';
  import PlanesLoader from '$lib/components/ui/planes-loader.svelte';

  interface JobSummary {
    name: string;
    namespace: string;
    completions: string;
    status: string;
    active: number;
    succeeded: number;
    failed: number;
    duration: string | null;
    createdAt: string;
  }

  let jobs = $state<JobSummary[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let namespace = $state('');
  const auth = getAuth();
  let pollInterval: ReturnType<typeof setInterval>;

  async function fetchJobs() {
    try {
      const url = namespace ? `/v2/kubernetes/jobs?namespace=${namespace}` : '/v2/kubernetes/jobs';
      const res = await api.get<{ data: JobSummary[] }>(url);
      if (res?.data) jobs = res.data;
      error = null;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load jobs';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('system:view')) {
      goto('/');
      return;
    }
    fetchJobs();
    pollInterval = setInterval(fetchJobs, 5000);
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
  });

  $effect(() => {
    namespace;
    fetchJobs();
  });

  function mapStatus(status: string): string {
    if (status === 'Complete') return 'Succeeded';
    return status;
  }
</script>

<div class="space-y-4">
  <!-- Filters -->
  <div class="flex items-center gap-3">
    <NamespaceSelector value={namespace} onchange={(ns) => namespace = ns} />
    <span class="text-sm text-secondary ml-auto">{jobs.length} jobs</span>
  </div>

  {#if loading}
    <PlanesLoader message="Loading jobs..." />
  {:else if error}
    <div class="rounded-lg border border-error/20 bg-error/10 p-4 text-error">{error}</div>
  {:else}
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr class="border-b border-border">
            <th class="table-header">Name</th>
            <th class="table-header">Namespace</th>
            <th class="table-header">Completions</th>
            <th class="table-header">Status</th>
            <th class="table-header">Duration</th>
            <th class="table-header">Age</th>
          </tr>
        </thead>
        <tbody>
          {#each jobs as job}
            <tr
              class="table-row table-row-interactive"
              onclick={() => goto(`/kubernetes/jobs/${job.namespace}/${job.name}`)}
              role="button"
              tabindex="0"
              onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && goto(`/kubernetes/jobs/${job.namespace}/${job.name}`)}
            >
              <td class="table-cell font-medium text-text-primary">{job.name}</td>
              <td class="table-cell text-text-secondary">{job.namespace}</td>
              <td class="table-cell font-mono text-text-secondary">{job.completions}</td>
              <td class="table-cell">
                <StatusIndicator status={mapStatus(job.status)} />
              </td>
              <td class="table-cell text-text-secondary">{job.duration || '-'}</td>
              <td class="table-cell">
                <ResourceAge timestamp={job.createdAt} />
              </td>
            </tr>
          {:else}
            <tr>
              <td colspan="6" class="table-empty">No jobs found</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
