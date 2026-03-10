<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '$lib/api';
  import {
    AlertCircle,
    Loader2,
    RefreshCw,
    Filter,
    ArrowDownToLine,
    Pause,
    Clock,
  } from 'lucide-svelte';

  // Props
  interface Props {
    runId: string;
    testName: string;
    maxHeight?: string;
  }

  let { runId, testName, maxHeight = '500px' }: Props = $props();

  // UART log entry structure
  interface UartEntry {
    timestamp: number; // ms since start
    source: 'app' | 'comms';
    level: 'I' | 'D' | 'W' | 'E' | 'U'; // Info, Debug, Warning, Error, Unknown
    message: string;
    rawLine: string;
  }

  // State
  let appEntries = $state<UartEntry[]>([]);
  let commsEntries = $state<UartEntry[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let logContainer: HTMLElement | null = null;

  // View options
  let showApp = $state(true);
  let showComms = $state(true);
  let showMerged = $state(true);
  let showRelativeTime = $state(true);
  let autoScroll = $state(true);
  let filterLevel = $state<'all' | 'I' | 'D' | 'W' | 'E'>('all');

  // Log level colors
  const LEVEL_COLORS: Record<string, string> = {
    'E': 'text-error',
    'W': 'text-warning',
    'I': 'text-info',
    'D': 'text-text-tertiary',
    'U': 'text-text-secondary',
  };

  const LEVEL_BG: Record<string, string> = {
    'E': 'bg-error-muted',
    'W': 'bg-warning-muted',
    'I': '',
    'D': '',
    'U': '',
  };

  const SOURCE_COLORS: Record<string, string> = {
    'app': 'text-accent',
    'comms': 'text-success',
  };

  // Parse UART log line: [timestamp] LEVEL: message
  function parseUartLine(line: string, source: 'app' | 'comms'): UartEntry | null {
    if (!line.trim()) return null;

    // Match pattern: [123456] I: some message
    // or: [2025-03-07 12:34:56.789] I: some message
    // or just: I: some message
    let timestamp = 0;
    let level: UartEntry['level'] = 'U';
    let message = line;

    // Try to extract timestamp
    const timestampMatch = line.match(/^\[(\d+)\]\s*/);
    if (timestampMatch) {
      timestamp = parseInt(timestampMatch[1], 10);
      message = line.slice(timestampMatch[0].length);
    } else {
      const isoMatch = line.match(/^\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]\s*/);
      if (isoMatch) {
        timestamp = new Date(isoMatch[1]).getTime();
        message = line.slice(isoMatch[0].length);
      }
    }

    // Try to extract level prefix
    const levelMatch = message.match(/^([IDWE]):\s*/);
    if (levelMatch) {
      level = levelMatch[1] as UartEntry['level'];
      message = message.slice(levelMatch[0].length);
    } else {
      // Check for verbose level names
      const verboseMatch = message.match(/^<(inf|dbg|wrn|err)>\s*/i);
      if (verboseMatch) {
        const levelMap: Record<string, UartEntry['level']> = {
          'inf': 'I', 'dbg': 'D', 'wrn': 'W', 'err': 'E'
        };
        level = levelMap[verboseMatch[1].toLowerCase()] || 'U';
        message = message.slice(verboseMatch[0].length);
      }
    }

    return {
      timestamp,
      source,
      level,
      message: message.trim(),
      rawLine: line,
    };
  }

  // Parse UART file content
  function parseUartFile(content: string, source: 'app' | 'comms'): UartEntry[] {
    const lines = content.split('\n');
    const entries: UartEntry[] = [];

    for (const line of lines) {
      const entry = parseUartLine(line, source);
      if (entry) {
        entries.push(entry);
      }
    }

    return entries;
  }

  // Fetch UART logs
  async function fetchUartLogs(): Promise<void> {
    loading = true;
    error = null;

    try {
      // Fetch both app and comms UART logs
      const [appRes, commsRes] = await Promise.allSettled([
        apiFetch<{ data: { content: string } }>(
          `/v2/validation/runs/${runId}/logs/tests/${encodeURIComponent(testName)}/uart_app.log`
        ),
        apiFetch<{ data: { content: string } }>(
          `/v2/validation/runs/${runId}/logs/tests/${encodeURIComponent(testName)}/uart_comms.log`
        ),
      ]);

      if (appRes.status === 'fulfilled') {
        appEntries = parseUartFile(appRes.value.data.content, 'app');
      } else {
        appEntries = [];
      }

      if (commsRes.status === 'fulfilled') {
        commsEntries = parseUartFile(commsRes.value.data.content, 'comms');
      } else {
        commsEntries = [];
      }

      if (appEntries.length === 0 && commsEntries.length === 0) {
        error = 'No UART logs available';
      }
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load UART logs';
    } finally {
      loading = false;
    }
  }

  // Merged and filtered entries
  const displayEntries = $derived.by(() => {
    let entries: UartEntry[] = [];

    if (showMerged) {
      if (showApp) entries = entries.concat(appEntries);
      if (showComms) entries = entries.concat(commsEntries);
      // Sort by timestamp
      entries.sort((a, b) => a.timestamp - b.timestamp);
    } else {
      if (showApp) entries = appEntries;
      else if (showComms) entries = commsEntries;
    }

    // Filter by level
    if (filterLevel !== 'all') {
      entries = entries.filter(e => e.level === filterLevel);
    }

    return entries;
  });

  // Format timestamp
  function formatTimestamp(entry: UartEntry): string {
    if (showRelativeTime) {
      // Relative ms since first entry
      const firstTs = displayEntries.length > 0 ? displayEntries[0].timestamp : 0;
      const relMs = entry.timestamp - firstTs;
      if (relMs < 1000) {
        return `+${relMs}ms`;
      } else if (relMs < 60000) {
        return `+${(relMs / 1000).toFixed(2)}s`;
      } else {
        const mins = Math.floor(relMs / 60000);
        const secs = ((relMs % 60000) / 1000).toFixed(1);
        return `+${mins}m${secs}s`;
      }
    } else {
      // Absolute timestamp
      if (entry.timestamp > 1e12) {
        // Unix timestamp in ms
        return new Date(entry.timestamp).toISOString().slice(11, 23);
      } else {
        // Relative ms
        return `${entry.timestamp}ms`;
      }
    }
  }

  // Scroll to bottom
  function scrollToBottom(): void {
    if (logContainer && autoScroll) {
      logContainer.scrollTop = logContainer.scrollHeight;
    }
  }

  // Handle scroll
  function handleScroll(): void {
    if (!logContainer) return;
    const threshold = 50;
    const isAtBottom = logContainer.scrollHeight - logContainer.scrollTop - logContainer.clientHeight < threshold;
    if (!isAtBottom && autoScroll) {
      autoScroll = false;
    }
  }

  function toggleAutoScroll(): void {
    autoScroll = !autoScroll;
    if (autoScroll) {
      scrollToBottom();
    }
  }

  // Level filter options
  const levelOptions = [
    { value: 'all', label: 'All' },
    { value: 'E', label: 'Error' },
    { value: 'W', label: 'Warn' },
    { value: 'I', label: 'Info' },
    { value: 'D', label: 'Debug' },
  ];

  // Stats
  const stats = $derived.by(() => {
    return {
      appCount: appEntries.length,
      commsCount: commsEntries.length,
      errorCount: displayEntries.filter(e => e.level === 'E').length,
      warnCount: displayEntries.filter(e => e.level === 'W').length,
    };
  });

  onMount(() => {
    fetchUartLogs();
  });

  $effect(() => {
    // Scroll to bottom when entries change
    if (displayEntries.length > 0) {
      requestAnimationFrame(() => scrollToBottom());
    }
  });
</script>

<div class="rounded-lg border border-border bg-surface-0 overflow-hidden">
  <!-- Header -->
  <div class="flex items-center justify-between px-3 py-2 border-b border-border bg-surface-1">
    <div class="flex items-center gap-2">
      <span class="text-xs font-medium text-text-primary">UART Logs</span>
      {#if displayEntries.length > 0}
        <span class="text-2xs text-text-tertiary">({displayEntries.length} entries)</span>
      {/if}
    </div>

    <div class="flex items-center gap-2">
      <!-- Source toggles -->
      <div class="flex items-center gap-1 mr-2">
        <button
          onclick={() => (showApp = !showApp)}
          class="px-2 py-1 text-2xs font-medium rounded transition-colors {showApp ? 'bg-accent-muted text-accent' : 'bg-surface-2 text-text-tertiary hover:text-text-primary'}"
        >
          APP
        </button>
        <button
          onclick={() => (showComms = !showComms)}
          class="px-2 py-1 text-2xs font-medium rounded transition-colors {showComms ? 'bg-success-muted text-success' : 'bg-surface-2 text-text-tertiary hover:text-text-primary'}"
        >
          COMMS
        </button>
      </div>

      <!-- Merge toggle -->
      <button
        onclick={() => (showMerged = !showMerged)}
        class="p-1.5 rounded hover:bg-surface-2 transition-colors {showMerged ? 'text-accent' : 'text-text-tertiary hover:text-text-primary'}"
        title={showMerged ? 'Merged view' : 'Separate view'}
      >
        <Filter size={14} />
      </button>

      <!-- Time format toggle -->
      <button
        onclick={() => (showRelativeTime = !showRelativeTime)}
        class="p-1.5 rounded hover:bg-surface-2 transition-colors {showRelativeTime ? 'text-accent' : 'text-text-tertiary hover:text-text-primary'}"
        title={showRelativeTime ? 'Relative time' : 'Absolute time'}
      >
        <Clock size={14} />
      </button>

      <!-- Level filter -->
      <select
        bind:value={filterLevel}
        class="text-2xs bg-surface-2 border-0 rounded px-2 py-1 text-text-primary focus:ring-1 focus:ring-accent"
      >
        {#each levelOptions as opt}
          <option value={opt.value}>{opt.label}</option>
        {/each}
      </select>

      <!-- Auto-scroll toggle -->
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

      <!-- Refresh -->
      <button
        onclick={fetchUartLogs}
        disabled={loading}
        class="p-1.5 rounded hover:bg-surface-2 text-text-tertiary hover:text-text-primary transition-colors disabled:opacity-50"
        title="Refresh"
      >
        <RefreshCw size={14} class={loading ? 'animate-spin' : ''} />
      </button>
    </div>
  </div>

  <!-- Log content -->
  <div
    bind:this={logContainer}
    onscroll={handleScroll}
    class="overflow-auto font-mono text-xs"
    style:max-height={maxHeight}
  >
    {#if loading}
      <div class="flex items-center justify-center py-8 text-text-tertiary">
        <Loader2 size={16} class="animate-spin mr-2" />
        Loading UART logs...
      </div>
    {:else if error && displayEntries.length === 0}
      <div class="flex items-center gap-2 px-3 py-4 text-error">
        <AlertCircle size={14} />
        <span>{error}</span>
      </div>
    {:else if displayEntries.length === 0}
      <div class="px-3 py-4 text-text-tertiary text-center">
        No UART entries to display
      </div>
    {:else}
      <table class="w-full">
        <tbody>
          {#each displayEntries as entry, i (i)}
            <tr class="hover:bg-surface-1 border-b border-border/30 {LEVEL_BG[entry.level]}">
              <!-- Timestamp -->
              <td class="px-2 py-1 text-2xs text-text-tertiary whitespace-nowrap w-20 align-top">
                {formatTimestamp(entry)}
              </td>

              <!-- Source badge -->
              {#if showMerged && showApp && showComms}
                <td class="px-1 py-1 w-12 align-top">
                  <span class="text-2xs font-medium {SOURCE_COLORS[entry.source]}">
                    {entry.source.toUpperCase()}
                  </span>
                </td>
              {/if}

              <!-- Level -->
              <td class="px-1 py-1 w-6 align-top">
                <span class="text-2xs font-bold {LEVEL_COLORS[entry.level]}">
                  {entry.level}
                </span>
              </td>

              <!-- Message -->
              <td class="px-2 py-1 text-text-secondary whitespace-pre-wrap break-all">
                {entry.message}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>

  <!-- Stats footer -->
  {#if stats.appCount > 0 || stats.commsCount > 0}
    <div class="flex items-center gap-4 px-3 py-1.5 border-t border-border bg-surface-1 text-2xs text-text-tertiary">
      {#if stats.appCount > 0}
        <span>APP: <span class="text-accent font-medium">{stats.appCount}</span></span>
      {/if}
      {#if stats.commsCount > 0}
        <span>COMMS: <span class="text-success font-medium">{stats.commsCount}</span></span>
      {/if}
      {#if stats.errorCount > 0}
        <span class="text-error">Errors: <span class="font-medium">{stats.errorCount}</span></span>
      {/if}
      {#if stats.warnCount > 0}
        <span class="text-warning">Warnings: <span class="font-medium">{stats.warnCount}</span></span>
      {/if}
    </div>
  {/if}
</div>
