<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { X, Download, Trash2, Pause, Play } from 'lucide-svelte';
  import Select from '$lib/components/ui/select.svelte';
  import { subscribeLogs } from '$lib/services/websocket';
  import { apiFetch } from '$lib/api';
  import type { ApiResponse } from '$lib/types';

  interface Props {
    namespace: string;
    pod: string;
    container: string;
    onclose: () => void;
  }

  let { namespace, pod, container, onclose }: Props = $props();

  interface PodStatus {
    status: string;
    containers: Array<{
      name: string;
      state: string;
      ready: boolean;
    }>;
  }

  let lines = $state<string[]>([]);
  let error = $state<string | null>(null);
  let podStatus = $state<PodStatus | null>(null);
  let statusCheckInterval = $state<number | null>(null);
  let paused = $state(false);
  let tailLines = $state(100);
  let autoScroll = $state(true);
  let logsContainer: HTMLDivElement;
  let unsubscribe: (() => void) | null = null;

  let pausedBuffer = $state<string[]>([]);

  function handleLine(line: string) {
    if (paused) {
      pausedBuffer.push(line);
    } else {
      lines = [...lines, line];
      if (lines.length > 10000) {
        lines = lines.slice(-5000);
      }
    }
  }

  async function fetchPodStatus() {
    try {
      const res = await apiFetch<ApiResponse<PodStatus>>(
        `/v2/cluster/pods/${namespace}/${pod}`
      );
      if (res.data) {
        podStatus = res.data;
      }
    } catch (err) {
      console.error('Failed to fetch pod status:', err);
    }
  }

  function handleError(message: string) {
    // When we get an error, fetch pod status to provide better UX
    error = message;
    fetchPodStatus();

    // If this is a connection error, start checking pod status periodically
    if (message.includes('transport error') || message.includes('Disconnected')) {
      if (!statusCheckInterval) {
        statusCheckInterval = window.setInterval(() => {
          fetchPodStatus();
          // If pod is running, try to reconnect
          if (podStatus?.status === 'Running') {
            const containerReady = podStatus.containers.find(c => c.name === container)?.ready;
            if (containerReady) {
              clearInterval(statusCheckInterval!);
              statusCheckInterval = null;
              reconnect();
            }
          }
        }, 3000);
      }
    }
  }

  function togglePause() {
    if (paused) {
      // Resume: add buffered lines
      lines = [...lines, ...pausedBuffer];
      pausedBuffer = [];
      paused = false;
    } else {
      paused = true;
    }
  }

  function clearLogs() {
    lines = [];
    pausedBuffer = [];
  }

  function downloadLogs() {
    const content = lines.join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${pod}-${container}.log`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function reconnect() {
    if (unsubscribe) {
      unsubscribe();
    }
    error = null;
    lines = [];
    unsubscribe = subscribeLogs(
      { namespace, pod, container, tailLines },
      handleLine,
      handleError
    );
  }

  onMount(() => {
    reconnect();
  });

  onDestroy(() => {
    if (unsubscribe) {
      unsubscribe();
    }
    if (statusCheckInterval) {
      clearInterval(statusCheckInterval);
      statusCheckInterval = null;
    }
  });

  $effect(() => {
    if (autoScroll && logsContainer && !paused) {
      logsContainer.scrollTop = logsContainer.scrollHeight;
    }
  });
</script>

<div class="fixed inset-0 z-modal flex items-center justify-center bg-overlay">
  <div class="w-[90vw] h-[80vh] max-w-6xl bg-surface-1 rounded-lg border border-border flex flex-col shadow-xl">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <div class="flex items-center gap-3">
        <h3 class="text-lg font-semibold text-text-primary">Logs</h3>
        <span class="text-sm text-text-secondary font-mono">{container}</span>
        <span class="text-xs text-text-tertiary">({lines.length} lines)</span>
      </div>
      <div class="flex items-center gap-2">
        <button
          onclick={togglePause}
          class="btn btn-sm btn-ghost"
          title={paused ? 'Resume' : 'Pause'}
        >
          {#if paused}
            <Play size={16} />
            <span class="text-xs">Resume ({pausedBuffer.length})</span>
          {:else}
            <Pause size={16} />
          {/if}
        </button>
        <button
          onclick={clearLogs}
          class="btn btn-sm btn-ghost"
          title="Clear"
        >
          <Trash2 size={16} />
        </button>
        <button
          onclick={downloadLogs}
          class="btn btn-sm btn-ghost"
          title="Download"
        >
          <Download size={16} />
        </button>
        <button
          onclick={onclose}
          class="btn btn-sm btn-ghost"
          title="Close"
        >
          <X size={16} />
        </button>
      </div>
    </div>

    <!-- Options bar -->
    <div class="flex items-center gap-4 px-4 py-2 border-b border-border bg-surface-0">
      <label class="flex items-center gap-2 text-sm">
        <span class="text-text-secondary">Tail lines:</span>
        <Select
          bind:value={tailLines}
          onchange={reconnect}
          options={[
            { value: '50', label: '50' },
            { value: '100', label: '100' },
            { value: '500', label: '500' },
            { value: '1000', label: '1000' },
            { value: '5000', label: '5000' },
          ]}
          compact
        />
      </label>
      <label class="flex items-center gap-2 text-sm">
        <input type="checkbox" bind:checked={autoScroll} class="rounded" />
        <span class="text-text-secondary">Auto-scroll</span>
      </label>
    </div>

    <!-- Log content -->
    <div
      bind:this={logsContainer}
      class="flex-1 overflow-auto font-mono text-xs leading-relaxed bg-surface-0 text-text-secondary"
    >
      {#if error}
        {#if podStatus}
          {#if podStatus.status === 'Pending'}
            <div class="p-4 text-text-secondary">
              <div class="flex items-center gap-2 mb-2">
                <span class="w-2 h-2 rounded-full bg-warning animate-pulse"></span>
                <span class="font-semibold text-warning">Pod Starting</span>
              </div>
              <div class="text-text-tertiary">Waiting for pod to be scheduled...</div>
            </div>
          {:else if podStatus.status === 'Running'}
            {@const containerState = podStatus.containers.find(c => c.name === container)}
            {#if containerState?.state === 'waiting'}
              <div class="p-4 text-text-secondary">
                <div class="flex items-center gap-2 mb-2">
                  <span class="w-2 h-2 rounded-full bg-accent animate-pulse"></span>
                  <span class="font-semibold text-accent">Container Starting</span>
                </div>
                <div class="text-text-tertiary">Pulling container image and initializing...</div>
              </div>
            {:else}
              <div class="p-4 text-error">{error}</div>
            {/if}
          {:else if podStatus.status === 'Failed' || podStatus.status === 'CrashLoopBackOff' || podStatus.status === 'Error'}
            <div class="p-4 text-error">
              <div class="font-semibold mb-2">Pod Failed</div>
              <div>{error}</div>
            </div>
          {:else if podStatus.status === 'Succeeded'}
            <div class="p-4 text-text-secondary">
              <div class="flex items-center gap-2 mb-2">
                <span class="w-2 h-2 rounded-full bg-success"></span>
                <span class="font-semibold text-success">Pod Completed</span>
              </div>
              <div class="text-text-tertiary">This pod has finished running.</div>
            </div>
          {:else}
            <div class="p-4 text-warning">
              <div class="font-semibold mb-2">Pod Status: {podStatus.status}</div>
              <div class="text-text-secondary">{error}</div>
            </div>
          {/if}
        {:else}
          <div class="p-4 text-text-secondary">
            <div class="flex items-center gap-2 mb-2">
              <span class="w-2 h-2 rounded-full bg-accent animate-pulse"></span>
              <span class="font-semibold text-accent">Connecting</span>
            </div>
            <div class="text-text-tertiary">Checking pod status...</div>
          </div>
        {/if}
      {:else if lines.length === 0}
        <div class="p-4 text-text-tertiary">Waiting for logs...</div>
      {:else}
        <pre class="p-4 whitespace-pre-wrap break-all">{lines.join('\n')}</pre>
      {/if}
    </div>

    <!-- Status bar -->
    <div class="flex items-center justify-between px-4 py-2 border-t border-border bg-surface-0 text-xs text-text-tertiary">
      <span>{namespace}/{pod}/{container}</span>
      <span class="flex items-center gap-2">
        {#if paused}
          <span class="flex items-center gap-1 text-warning">
            <span class="w-2 h-2 rounded-full bg-warning"></span>
            Paused
          </span>
        {:else}
          <span class="flex items-center gap-1 text-success">
            <span class="w-2 h-2 rounded-full bg-success animate-pulse"></span>
            Streaming
          </span>
        {/if}
      </span>
    </div>
  </div>
</div>
