<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { ArrowLeft, Trash2, FileCode, Terminal, ChevronDown } from 'lucide-svelte';
  import { api } from '$lib/api';
  import { getAuth } from '$lib/stores/auth.svelte';
  import StatusIndicator from '$lib/components/system/status-indicator.svelte';
  import ResourceAge from '$lib/components/system/resource-age.svelte';
  import LabelList from '$lib/components/system/label-list.svelte';
  import CollapsibleSection from '$lib/components/system/collapsible-section.svelte';
  import ActionButton from '$lib/components/system/action-button.svelte';
  import ResourceYamlDialog from '$lib/components/system/resource-yaml-dialog.svelte';
  import PodLogsInline from '$lib/components/system/pod-logs-inline.svelte';
  import PodTerminal from '$lib/components/system/pod-terminal.svelte';
  import PlanesLoader from '$lib/components/ui/planes-loader.svelte';

  interface Container {
    name: string;
    image: string;
    ready: boolean;
    restartCount: number;
    state: string;
  }

  interface PodCondition {
    type: string;
    status: string;
    reason: string;
    lastTransitionTime: string;
  }

  interface PodEvent {
    type: string;
    reason: string;
    message: string;
    count: number;
    lastSeen: string;
  }

  interface PodDetailData {
    name: string;
    namespace: string;
    status: string;
    podIp: string;
    nodeName: string;
    serviceAccount: string;
    qosClass: string;
    createdAt: string;
    containers: Container[];
    conditions: PodCondition[];
    events: PodEvent[];
    labels: Record<string, string>;
  }

  const namespace = $derived($page.params.namespace ?? '');
  const podName = $derived($page.params.name ?? '');

  let pod = $state<PodDetailData | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let showYaml = $state(false);
  let deleting = $state(false);
  let mutationError = $state<string | null>(null);
  let terminalContainer = $state<string | null>(null);
  let showTerminalMenu = $state(false);

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('system:manage'));

  // Get running containers for terminal
  const runningContainers = $derived(
    pod?.containers.filter(c => c.state === 'running') ?? []
  );

  async function fetchPod() {
    loading = true;
    try {
      const res = await api.get<{ data: PodDetailData }>(`/v2/kubernetes/pods/${namespace}/${podName}`);
      if (res?.data) pod = res.data;
      error = null;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load pod';
    } finally {
      loading = false;
    }
  }

  async function deletePod() {
    deleting = true;
    mutationError = null;
    try {
      await api.delete(`/v2/kubernetes/pods/${namespace}/${podName}`);
      goto('/kubernetes/pods');
    } catch (e) {
      mutationError = e instanceof Error ? e.message : 'Failed to delete pod';
      throw e;
    } finally {
      deleting = false;
    }
  }

  function openTerminal(containerName: string) {
    terminalContainer = containerName;
    showTerminalMenu = false;
  }

  onMount(() => {
    if (!auth.hasPermission('system:view')) {
      goto('/');
      return;
    }
    fetchPod();
  });
</script>

<div class="space-y-6">
  <!-- Back Button -->
  <button
    onclick={() => goto('/kubernetes/pods')}
    class="flex items-center gap-1 text-sm text-secondary hover:text-primary"
  >
    <ArrowLeft class="w-4 h-4" />
    Back to Pods
  </button>

  {#if loading}
    <PlanesLoader message="Loading pod details..." />
  {:else if error}
    <div class="rounded-lg border border-error/20 bg-error/10 p-4 text-error">{error}</div>
  {:else if pod}
    <!-- Header -->
    <div class="flex items-start justify-between">
      <div>
        <div class="flex items-center gap-3">
          <h2 class="text-xl font-semibold text-primary">{pod.name}</h2>
          <StatusIndicator status={pod.status} />
        </div>
        <div class="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm">
          <span class="text-secondary">Namespace: <span class="text-primary">{pod.namespace}</span></span>
          <span class="text-border">|</span>
          <span class="text-secondary">Node: <span class="text-primary">{pod.nodeName}</span></span>
          <span class="text-border">|</span>
          <span class="text-secondary">IP: <span class="text-primary font-mono">{pod.podIp || '-'}</span></span>
          <span class="text-border">|</span>
          <span class="text-secondary">SA: <span class="text-primary">{pod.serviceAccount}</span></span>
          <span class="text-border">|</span>
          <span class="text-secondary">QoS: <span class="text-primary">{pod.qosClass}</span></span>
          <span class="text-border">|</span>
          <span class="text-secondary">Age: <ResourceAge timestamp={pod.createdAt} /></span>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <!-- Terminal Button with dropdown -->
        {#if runningContainers.length > 0}
          <div class="relative">
            <button
              onclick={() => {
                if (runningContainers.length === 1) {
                  openTerminal(runningContainers[0].name);
                } else {
                  showTerminalMenu = !showTerminalMenu;
                }
              }}
              class="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded bg-accent text-white hover:bg-accent-hover transition-colors"
            >
              <Terminal size={16} />
              Terminal
              {#if runningContainers.length > 1}
                <ChevronDown size={14} />
              {/if}
            </button>
            {#if showTerminalMenu && runningContainers.length > 1}
              <div class="absolute right-0 mt-1 w-48 rounded-lg border border-border bg-surface-1 shadow-lg z-10">
                {#each runningContainers as container}
                  <button
                    onclick={() => openTerminal(container.name)}
                    class="w-full px-3 py-2 text-left text-sm hover:bg-surface-2 first:rounded-t-lg last:rounded-b-lg"
                  >
                    <span class="font-mono">{container.name}</span>
                  </button>
                {/each}
              </div>
            {/if}
          </div>
        {:else}
          <button
            disabled
            class="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded bg-surface-2 text-tertiary cursor-not-allowed"
            title="No running containers"
          >
            <Terminal size={16} />
            Terminal
          </button>
        {/if}
        <button
          onclick={() => showYaml = true}
          class="flex items-center gap-1.5 px-2 py-1.5 text-sm font-medium rounded bg-surface-2 text-secondary hover:bg-surface-3 transition-colors"
        >
          <FileCode size={16} />
          YAML
        </button>
        {#if canManage}
          <ActionButton
            label="Delete"
            icon={Trash2}
            variant="danger"
            confirmMessage="Delete this pod?"
            onConfirm={deletePod}
            disabled={deleting}
          />
        {/if}
      </div>
    </div>

    {#if mutationError}
      <div class="rounded-lg border border-error/20 bg-error/10 p-3 text-sm text-error">{mutationError}</div>
    {/if}

    <!-- LOGS SECTION - Prominent, auto-open -->
    <PodLogsInline
      {namespace}
      pod={podName}
      containers={pod.containers.map(c => c.name)}
      defaultOpen={true}
    />

    <!-- Containers -->
    <div>
      <h3 class="text-lg font-semibold text-primary mb-3">Containers ({pod.containers.length})</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {#each pod.containers as container}
          <div class="card card-sm">
            <div class="flex items-center justify-between mb-2">
              <span class="font-medium text-primary">{container.name}</span>
              <StatusIndicator status={container.state} />
            </div>
            <div class="text-xs font-mono text-secondary truncate mb-2" title={container.image}>
              {container.image}
            </div>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-4 text-xs">
                <span class="text-secondary">
                  Ready: <span class="{container.ready ? 'text-success' : 'text-error'}">{container.ready ? 'Yes' : 'No'}</span>
                </span>
                <span class="text-secondary">
                  Restarts: <span class="{container.restartCount > 0 ? 'text-warning font-bold' : ''}">{container.restartCount}</span>
                </span>
              </div>
              {#if container.state === 'running'}
                <button
                  onclick={() => terminalContainer = container.name}
                  class="flex items-center gap-1 px-2 py-1 text-xs rounded bg-surface-2 text-secondary hover:bg-surface-3 hover:text-primary transition-colors"
                >
                  <Terminal size={14} />
                  Shell
                </button>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    </div>

    <!-- Conditions -->
    <CollapsibleSection title="Conditions" count={pod.conditions.length} defaultOpen>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-tertiary">
              <th class="px-2 py-1">Type</th>
              <th class="px-2 py-1">Status</th>
              <th class="px-2 py-1">Reason</th>
              <th class="px-2 py-1">Age</th>
            </tr>
          </thead>
          <tbody>
            {#each pod.conditions as condition}
              <tr>
                <td class="px-2 py-1 font-medium text-primary">{condition.type}</td>
                <td class="px-2 py-1">
                  <StatusIndicator status={condition.status === 'True' ? 'Ready' : 'NotReady'} />
                </td>
                <td class="px-2 py-1 text-secondary">{condition.reason || '-'}</td>
                <td class="px-2 py-1">
                  <ResourceAge timestamp={condition.lastTransitionTime} />
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </CollapsibleSection>

    <!-- Events -->
    <CollapsibleSection title="Events" count={pod.events.length} defaultOpen>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-tertiary">
              <th class="px-2 py-1">Type</th>
              <th class="px-2 py-1">Reason</th>
              <th class="px-2 py-1">Message</th>
              <th class="px-2 py-1">Count</th>
              <th class="px-2 py-1">Age</th>
            </tr>
          </thead>
          <tbody>
            {#each pod.events as event}
              <tr>
                <td class="px-2 py-1">
                  <StatusIndicator status={event.type} />
                </td>
                <td class="px-2 py-1 font-medium text-primary">{event.reason}</td>
                <td class="px-2 py-1 text-secondary truncate max-w-xs" title={event.message}>
                  {event.message}
                </td>
                <td class="px-2 py-1 text-secondary">{event.count}</td>
                <td class="px-2 py-1">
                  <ResourceAge timestamp={event.lastSeen} />
                </td>
              </tr>
            {:else}
              <tr>
                <td colspan="5" class="px-2 py-4 text-center text-tertiary">No events</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </CollapsibleSection>

    <!-- Labels -->
    <CollapsibleSection title="Labels" count={Object.keys(pod.labels).length} defaultOpen>
      <LabelList labels={pod.labels} />
    </CollapsibleSection>

    <!-- YAML Dialog -->
    <ResourceYamlDialog
      kind="Pod"
      {namespace}
      name={podName}
      open={showYaml}
      onclose={() => showYaml = false}
    />

    <!-- Terminal Modal -->
    {#if terminalContainer !== null}
      {@const container = terminalContainer}
      <PodTerminal
        {namespace}
        pod={podName}
        {container}
        onclose={() => terminalContainer = null}
      />
    {/if}
  {/if}
</div>

<!-- Click outside to close terminal menu -->
{#if showTerminalMenu}
  <button
    class="fixed inset-0 z-0"
    onclick={() => showTerminalMenu = false}
    aria-label="Close menu"
  ></button>
{/if}
