<script lang="ts">
  import { onMount, onDestroy, tick, untrack } from 'svelte';
  import { Download, Trash2, Pause, Play, ChevronRight, RefreshCw } from 'lucide-svelte';
  import Select from '$lib/components/ui/select.svelte';
  import { subscribeLogs } from '$lib/services/websocket';

  interface Props {
    namespace: string;
    pod: string;
    containers: string[];
    defaultOpen?: boolean;
  }

  let { namespace, pod, containers, defaultOpen = true }: Props = $props();

  let selectedContainer = $state(untrack(() => containers[0] || ''));
  let prevContainer = $state(untrack(() => containers[0] || ''));
  let lines = $state<string[]>([]);
  let error = $state<string | null>(null);
  let connected = $state(false);
  let paused = $state(false);
  let tailLines = $state(100);
  let prevTailLines = $state(100);
  let autoScroll = $state(true);
  let isOpen = $state(untrack(() => defaultOpen));
  let logsContainer = $state<HTMLDivElement | undefined>(undefined);
  let unsubscribe: (() => void) | null = null;

  let pausedBuffer = $state<string[]>([]);

  // Watch for container or tail lines changes and reconnect
  $effect(() => {
    if (selectedContainer !== prevContainer) {
      prevContainer = selectedContainer;
      if (isOpen) connect();
    }
  });

  $effect(() => {
    if (tailLines !== prevTailLines) {
      prevTailLines = tailLines;
      if (isOpen) connect();
    }
  });

  async function scrollToBottom() {
    if (autoScroll && logsContainer && !paused) {
      await tick();
      logsContainer.scrollTop = logsContainer.scrollHeight;
    }
  }

  function handleLine(line: string) {
    if (paused) {
      pausedBuffer.push(line);
    } else {
      lines.push(line);
      if (lines.length > 2000) {
        lines = lines.slice(-1000);
      }
      scrollToBottom();
    }
  }

  function handleError(message: string) {
    error = message;
  }

  function togglePause() {
    if (paused) {
      lines = [...lines, ...pausedBuffer];
      pausedBuffer = [];
      paused = false;
      scrollToBottom();
    } else {
      paused = true;
    }
  }

  function clearLogs() {
    lines = [];
    pausedBuffer = [];
    error = null;
  }

  function downloadLogs() {
    const content = lines.join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${pod}-${selectedContainer}.log`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function connect() {
    if (unsubscribe) {
      unsubscribe();
      unsubscribe = null;
    }
    if (!selectedContainer || !isOpen) return;

    error = null;
    lines = [];
    pausedBuffer = [];
    paused = false;
    connected = false;

    unsubscribe = subscribeLogs(
      { namespace, pod, container: selectedContainer, tailLines },
      handleLine,
      handleError,
      () => { connected = true; }
    );
  }


  function toggleOpen() {
    isOpen = !isOpen;
    if (isOpen) {
      connect();
    } else if (unsubscribe) {
      unsubscribe();
      unsubscribe = null;
    }
  }

  onMount(() => {
    if (isOpen && selectedContainer) {
      connect();
    }
  });

  onDestroy(() => {
    if (unsubscribe) {
      unsubscribe();
    }
  });
</script>

<div class="border border-border rounded-lg overflow-hidden">
  <!-- Header - matches CollapsibleSection style -->
  <button
    onclick={toggleOpen}
    class="w-full flex items-center gap-2 px-3 py-2 bg-surface-2 hover:bg-surface-2/80 text-left"
  >
    <ChevronRight class="w-4 h-4 text-text-tertiary transition-transform {isOpen ? 'rotate-90' : ''}" />
    <span class="text-sm font-medium text-text-primary">Logs</span>
    <span class="px-1.5 py-0.5 rounded text-2xs bg-surface-1 text-text-secondary">{lines.length}</span>
    {#if isOpen}
      <span class="flex items-center gap-1.5 ml-2">
        {#if error}
          <span class="w-1.5 h-1.5 rounded-full bg-error"></span>
          <span class="text-2xs text-error">Error</span>
        {:else if paused}
          <span class="w-1.5 h-1.5 rounded-full bg-warning"></span>
          <span class="text-2xs text-warning">Paused</span>
        {:else}
          <span class="w-1.5 h-1.5 rounded-full bg-success animate-pulse"></span>
          <span class="text-2xs text-success">Live</span>
        {/if}
      </span>
    {/if}
  </button>

  {#if isOpen}
    <div class="bg-surface-1">
      <!-- Controls bar -->
      <div class="flex items-center gap-4 px-3 py-2 border-b border-border">
        <div class="flex items-center gap-2">
          <span class="text-xs text-text-secondary">Container:</span>
          <Select
            bind:value={selectedContainer}
            options={containers.map(c => ({ value: c, label: c }))}
            compact
          />
        </div>

        <div class="flex items-center gap-2">
          <span class="text-xs text-text-secondary">Tail:</span>
          <Select
            bind:value={tailLines}
            options={[
              { value: '50', label: '50' },
              { value: '100', label: '100' },
              { value: '500', label: '500' },
              { value: '1000', label: '1000' },
            ]}
            compact
          />
        </div>

        <label class="flex items-center gap-1.5 text-xs">
          <input type="checkbox" bind:checked={autoScroll} class="rounded" />
          <span class="text-text-secondary">Auto-scroll</span>
        </label>

        <div class="flex-1"></div>

        <div class="flex items-center gap-1">
          <button
            onclick={connect}
            class="p-1.5 rounded hover:bg-surface-2 text-text-secondary hover:text-text-primary transition-colors"
            title="Reconnect"
          >
            <RefreshCw size={14} />
          </button>
          <button
            onclick={togglePause}
            class="p-1.5 rounded hover:bg-surface-2 text-text-secondary hover:text-text-primary transition-colors"
            title={paused ? 'Resume' : 'Pause'}
          >
            {#if paused}
              <Play size={14} />
            {:else}
              <Pause size={14} />
            {/if}
          </button>
          <button
            onclick={clearLogs}
            class="p-1.5 rounded hover:bg-surface-2 text-text-secondary hover:text-text-primary transition-colors"
            title="Clear"
          >
            <Trash2 size={14} />
          </button>
          <button
            onclick={downloadLogs}
            class="p-1.5 rounded hover:bg-surface-2 text-text-secondary hover:text-text-primary transition-colors"
            title="Download"
          >
            <Download size={14} />
          </button>
        </div>
      </div>

      <!-- Log content -->
      <div
        bind:this={logsContainer}
        class="h-64 overflow-auto font-mono text-xs leading-relaxed bg-surface-0 text-text-secondary"
      >
        {#if error}
          <div class="p-3 flex flex-col items-center justify-center h-full gap-2">
            <span class="text-error">{error}</span>
            <button
              onclick={connect}
              class="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded bg-surface-2 text-text-secondary hover:bg-surface-3 hover:text-text-primary transition-colors"
            >
              <RefreshCw size={12} />
              Reconnect
            </button>
          </div>
        {:else if lines.length === 0}
          <div class="p-3 text-text-tertiary">
            {connected ? 'Connected — waiting for log output...' : 'Connecting to log stream...'}
          </div>
        {:else}
          <pre class="p-3 whitespace-pre-wrap break-all">{lines.join('\n')}</pre>
        {/if}
      </div>
    </div>
  {/if}
</div>
