<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import { apiFetch } from '$lib/api';
  import { subscribeValidationLogs } from '$lib/services/websocket';
  import {
    ArrowDownToLine,
    Pause,
    RefreshCw,
    AlertCircle,
    Loader2,
  } from 'lucide-svelte';

  // Props
  interface Props {
    runId: string;
    testName: string;
    file?: string;
    maxHeight?: string;
  }

  let { runId, testName, file = 'output.log', maxHeight = '500px' }: Props = $props();

  // State
  let content = $state('');
  let lastOffset = $state(0);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let autoScroll = $state(true);
  let connected = $state(false);
  let reconnecting = $state(false);
  let logContainer: HTMLElement | null = null;
  let unsubscribe: (() => void) | null = null;

  // Log level colors for syntax highlighting
  const LOG_LEVEL_COLORS: Record<string, string> = {
    'ERROR': 'text-error',
    'WARN': 'text-warning',
    'WARNING': 'text-warning',
    'INFO': 'text-info',
    'DEBUG': 'text-text-tertiary',
    'TRACE': 'text-text-tertiary',
  };

  // Parse and highlight log lines
  function highlightLine(line: string): string {
    // Match patterns like [ERROR], [WARN], [INFO], etc.
    const levelMatch = line.match(/\[(ERROR|WARN|WARNING|INFO|DEBUG|TRACE)\]/i);
    if (levelMatch) {
      const level = levelMatch[1].toUpperCase();
      const color = LOG_LEVEL_COLORS[level] || '';
      if (color) {
        return `<span class="${color}">${escapeHtml(line)}</span>`;
      }
    }

    // Match prefix patterns like E:, W:, I:, D:
    const prefixMatch = line.match(/^(E:|W:|I:|D:)/);
    if (prefixMatch) {
      const prefix = prefixMatch[1];
      const colorMap: Record<string, string> = {
        'E:': 'text-error',
        'W:': 'text-warning',
        'I:': 'text-info',
        'D:': 'text-text-tertiary',
      };
      const color = colorMap[prefix] || '';
      if (color) {
        return `<span class="${color}">${escapeHtml(line)}</span>`;
      }
    }

    return escapeHtml(line);
  }

  function escapeHtml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Scroll to bottom
  function scrollToBottom(): void {
    if (logContainer && autoScroll) {
      logContainer.scrollTop = logContainer.scrollHeight;
    }
  }

  // Detect if user scrolled up (disable auto-scroll)
  function handleScroll(): void {
    if (!logContainer) return;
    const threshold = 50;
    const isAtBottom = logContainer.scrollHeight - logContainer.scrollTop - logContainer.clientHeight < threshold;
    if (!isAtBottom && autoScroll) {
      autoScroll = false;
    }
  }

  // Fetch initial log content
  async function fetchLogs(): Promise<void> {
    loading = true;
    error = null;

    try {
      const res = await apiFetch<{ data: { content: string; size: number } }>(
        `/v2/validation/runs/${runId}/logs/tests/${encodeURIComponent(testName)}/${encodeURIComponent(file)}`
      );
      content = res.data.content;
      lastOffset = content.length;
      error = null;

      // Scroll to bottom after content loads
      requestAnimationFrame(() => scrollToBottom());
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load logs';
      content = '';
    } finally {
      loading = false;
    }
  }

  // Fetch missing data from a specific offset
  async function fetchFromOffset(offset: number): Promise<string> {
    try {
      const res = await apiFetch<{ data: { content: string; size: number } }>(
        `/v2/validation/runs/${runId}/logs/tests/${encodeURIComponent(testName)}/${encodeURIComponent(file)}?offset=${offset}`
      );
      return res.data.content;
    } catch {
      return '';
    }
  }

  // Setup WebSocket subscription
  function setupWebSocket(): void {
    if (!browser) return;

    connected = true;

    unsubscribe = subscribeValidationLogs(
      { runId, testName, file },
      async (data) => {
        if (data.offset === lastOffset) {
          // Sequential chunk - append directly
          content += data.chunk;
          lastOffset = content.length;
          requestAnimationFrame(() => scrollToBottom());
        } else if (data.offset > lastOffset) {
          // Gap detected - fetch missing data
          reconnecting = true;
          const missing = await fetchFromOffset(lastOffset);
          content += missing + data.chunk;
          lastOffset = content.length;
          reconnecting = false;
          requestAnimationFrame(() => scrollToBottom());
        }
        // If offset < lastOffset, it's a duplicate - ignore
      },
      (errMsg) => {
        error = errMsg;
        connected = false;
      }
    );
  }

  // Refresh logs
  function refresh(): void {
    content = '';
    lastOffset = 0;
    fetchLogs();
  }

  // Toggle auto-scroll
  function toggleAutoScroll(): void {
    autoScroll = !autoScroll;
    if (autoScroll) {
      scrollToBottom();
    }
  }

  // Generate highlighted HTML content
  const highlightedContent = $derived(
    content.split('\n').map(highlightLine).join('\n')
  );

  onMount(() => {
    fetchLogs();
    setupWebSocket();
  });

  onDestroy(() => {
    if (unsubscribe) {
      unsubscribe();
    }
  });
</script>

<div class="rounded-lg border border-border bg-surface-0 overflow-hidden">
  <!-- Header -->
  <div class="flex items-center justify-between px-3 py-2 border-b border-border bg-surface-1">
    <div class="flex items-center gap-2">
      <span class="text-xs font-medium text-text-primary">{file}</span>
      {#if connected}
        <span class="inline-flex items-center gap-1 text-2xs text-success">
          <span class="relative flex h-1.5 w-1.5">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
            <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-success"></span>
          </span>
          Live
        </span>
      {/if}
      {#if reconnecting}
        <span class="inline-flex items-center gap-1 text-2xs text-warning">
          <Loader2 size={10} class="animate-spin" />
          Reconnecting
        </span>
      {/if}
    </div>

    <div class="flex items-center gap-1">
      <button
        onclick={refresh}
        disabled={loading}
        class="p-1.5 rounded hover:bg-surface-2 text-text-tertiary hover:text-text-primary transition-colors disabled:opacity-50"
        title="Refresh"
      >
        <RefreshCw size={14} class={loading ? 'animate-spin' : ''} />
      </button>
      <button
        onclick={toggleAutoScroll}
        class="p-1.5 rounded hover:bg-surface-2 transition-colors {autoScroll ? 'text-accent' : 'text-text-tertiary hover:text-text-primary'}"
        title={autoScroll ? 'Auto-scroll enabled' : 'Auto-scroll disabled'}
      >
        {#if autoScroll}
          <ArrowDownToLine size={14} />
        {:else}
          <Pause size={14} />
        {/if}
      </button>
    </div>
  </div>

  <!-- Log content -->
  <div
    bind:this={logContainer}
    onscroll={handleScroll}
    class="overflow-auto font-mono text-xs leading-relaxed"
    style:max-height={maxHeight}
  >
    {#if loading && !content}
      <div class="flex items-center justify-center py-8 text-text-tertiary">
        <Loader2 size={16} class="animate-spin mr-2" />
        Loading logs...
      </div>
    {:else if error && !content}
      <div class="flex items-center gap-2 px-3 py-4 text-error">
        <AlertCircle size={14} />
        <span>{error}</span>
      </div>
    {:else if !content}
      <div class="px-3 py-4 text-text-tertiary text-center">
        No log output yet
      </div>
    {:else}
      <pre class="px-3 py-2 text-text-secondary whitespace-pre-wrap">{@html highlightedContent}</pre>
    {/if}
  </div>

  <!-- Footer with stats -->
  {#if content}
    <div class="flex items-center justify-between px-3 py-1.5 border-t border-border bg-surface-1 text-2xs text-text-tertiary">
      <span>{content.split('\n').length} lines</span>
      <span>{(content.length / 1024).toFixed(1)} KB</span>
    </div>
  {/if}
</div>
