<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { ArrowLeft, Trash2, FileCode } from 'lucide-svelte';
  import { api } from '$lib/api';
  import { getAuth } from '$lib/stores/auth.svelte';
  import StatusIndicator from '$lib/components/system/status-indicator.svelte';
  import ResourceAge from '$lib/components/system/resource-age.svelte';
  import LabelList from '$lib/components/system/label-list.svelte';
  import MetricCard from '$lib/components/system/metric-card.svelte';
  import CollapsibleSection from '$lib/components/system/collapsible-section.svelte';
  import ActionButton from '$lib/components/system/action-button.svelte';
  import ResourceYamlDialog from '$lib/components/system/resource-yaml-dialog.svelte';

  interface JobCondition {
    type: string;
    status: string;
    reason: string;
    message: string;
    lastTransitionTime: string;
  }

  interface JobPod {
    name: string;
    namespace: string;
    status: string;
    restarts: number;
  }

  interface JobDetailData {
    name: string;
    namespace: string;
    completions: string;
    status: string;
    active: number;
    succeeded: number;
    failed: number;
    parallelism: number;
    backoffLimit: number;
    duration: string | null;
    createdAt: string;
    conditions: JobCondition[];
    pods: JobPod[];
    labels: Record<string, string>;
  }

  const namespace = $derived($page.params.namespace);
  const jobName = $derived($page.params.name);

  let job = $state<JobDetailData | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let showYaml = $state(false);
  let deleting = $state(false);
  let mutationError = $state<string | null>(null);

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('Concord.Admin.System.Manage'));

  async function fetchJob() {
    loading = true;
    try {
      const res = await api.get<{ data: JobDetailData }>(`/v2/cluster/jobs/${namespace}/${jobName}`);
      if (res?.data) job = res.data;
      error = null;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load job';
    } finally {
      loading = false;
    }
  }

  async function deleteJob() {
    deleting = true;
    mutationError = null;
    try {
      await api.delete(`/v2/cluster/jobs/${namespace}/${jobName}`);
      goto('/kubernetes/jobs');
    } catch (e) {
      mutationError = e instanceof Error ? e.message : 'Failed to delete job';
      throw e;
    } finally {
      deleting = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.System.View')) {
      goto('/');
      return;
    }
    fetchJob();
  });

  function mapStatus(status: string): string {
    if (status === 'Complete') return 'Succeeded';
    return status;
  }
</script>

<div class="space-y-6">
  <!-- Back Button -->
  <button
    onclick={() => goto('/kubernetes/jobs')}
    class="flex items-center gap-1 text-sm text-secondary hover:text-primary"
  >
    <ArrowLeft class="w-4 h-4" />
    Back to Jobs
  </button>

  {#if loading}
    <div class="flex items-center justify-center py-12">
      <span class="text-secondary">Loading job details...</span>
    </div>
  {:else if error}
    <div class="rounded-lg border border-error/20 bg-error/10 p-4 text-error">{error}</div>
  {:else if job}
    <!-- Header -->
    <div class="flex items-start justify-between">
      <div>
        <div class="flex items-center gap-3">
          <h2 class="text-xl font-semibold text-primary">{job.name}</h2>
          <StatusIndicator status={mapStatus(job.status)} />
        </div>
        <div class="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm">
          <span class="text-secondary">Namespace: <span class="text-primary">{job.namespace}</span></span>
          {#if job.duration}
            <span class="text-border">|</span>
            <span class="text-secondary">Duration: <span class="text-primary">{job.duration}</span></span>
          {/if}
          <span class="text-border">|</span>
          <span class="text-secondary">Backoff Limit: <span class="text-primary">{job.backoffLimit}</span></span>
          <span class="text-border">|</span>
          <span class="text-secondary">Age: <ResourceAge timestamp={job.createdAt} /></span>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button
          onclick={() => showYaml = true}
          class="flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded bg-surface-2 text-secondary hover:bg-surface-2/80"
        >
          <FileCode class="w-4 h-4" />
          YAML
        </button>
        {#if canManage}
          <ActionButton
            label="Delete"
            icon={Trash2}
            variant="danger"
            confirmMessage="Delete this job?"
            onConfirm={deleteJob}
            disabled={deleting}
          />
        {/if}
      </div>
    </div>

    {#if mutationError}
      <div class="rounded-lg border border-error/20 bg-error/10 p-3 text-sm text-error">{mutationError}</div>
    {/if}

    <!-- Metrics -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <MetricCard
        label="Active"
        value={job.active}
        status={job.active > 0 ? 'info' : 'neutral'}
      />
      <MetricCard
        label="Succeeded"
        value={job.succeeded}
        status="success"
      />
      <MetricCard
        label="Failed"
        value={job.failed}
        status={job.failed > 0 ? 'error' : 'neutral'}
      />
      <MetricCard
        label="Parallelism"
        value={job.parallelism}
        status="neutral"
      />
    </div>

    <!-- Pods -->
    <div>
      <h3 class="text-lg font-semibold text-text-primary mb-3">Pods ({job.pods.length})</h3>
      <div class="table-wrapper">
        <table class="table">
          <thead>
            <tr class="border-b border-border">
              <th class="table-header">Name</th>
              <th class="table-header">Status</th>
              <th class="table-header">Restarts</th>
            </tr>
          </thead>
          <tbody>
            {#each job.pods as pod}
              <tr
                class="table-row table-row-interactive"
                onclick={() => goto(`/kubernetes/pods/${pod.namespace}/${pod.name}`)}
                role="button"
                tabindex="0"
                onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && goto(`/kubernetes/pods/${pod.namespace}/${pod.name}`)}
              >
                <td class="table-cell font-medium text-text-primary">{pod.name}</td>
                <td class="table-cell">
                  <StatusIndicator status={pod.status} />
                </td>
                <td class="table-cell {pod.restarts > 0 ? 'font-bold text-warning' : 'text-text-secondary'}">
                  {pod.restarts}
                </td>
              </tr>
            {:else}
              <tr>
                <td colspan="3" class="table-empty">No pods</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Conditions -->
    {#if job.conditions.length > 0}
      <CollapsibleSection title="Conditions" count={job.conditions.length} defaultOpen>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-tertiary">
                <th class="px-2 py-1">Type</th>
                <th class="px-2 py-1">Status</th>
                <th class="px-2 py-1">Reason</th>
                <th class="px-2 py-1">Message</th>
                <th class="px-2 py-1">Age</th>
              </tr>
            </thead>
            <tbody>
              {#each job.conditions as condition}
                <tr>
                  <td class="px-2 py-1 font-medium text-primary">{condition.type}</td>
                  <td class="px-2 py-1">
                    <StatusIndicator status={condition.status === 'True' ? 'Ready' : 'NotReady'} />
                  </td>
                  <td class="px-2 py-1 text-secondary">{condition.reason || '-'}</td>
                  <td class="px-2 py-1 text-secondary truncate max-w-xs" title={condition.message}>
                    {condition.message || '-'}
                  </td>
                  <td class="px-2 py-1">
                    <ResourceAge timestamp={condition.lastTransitionTime} />
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </CollapsibleSection>
    {/if}

    <!-- Labels -->
    <CollapsibleSection title="Labels" count={Object.keys(job.labels).length}>
      <LabelList labels={job.labels} />
    </CollapsibleSection>

    <!-- YAML Dialog -->
    <ResourceYamlDialog
      kind="Job"
      {namespace}
      name={jobName}
      open={showYaml}
      onclose={() => showYaml = false}
    />
  {/if}
</div>
