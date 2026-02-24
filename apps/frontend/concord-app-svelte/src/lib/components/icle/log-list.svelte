<script lang="ts">
  import { Download, FileText, HardDrive, Loader2 } from 'lucide-svelte';
  import type { IcleLogFile } from '$lib/types/icle';

  let {
    logs,
    deviceId,
    loading = false,
    onDownload,
    onRefresh
  }: {
    logs: IcleLogFile[];
    deviceId: string;
    loading?: boolean;
    onDownload?: (filename: string) => void;
    onRefresh?: () => void;
  } = $props();

  function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleString();
  }

  function handleDownload(filename: string) {
    if (onDownload) {
      onDownload(filename);
    } else {
      // Default: open download URL in new tab
      window.open(`/v2/icle/${deviceId}/logs/${encodeURIComponent(filename)}`, '_blank');
    }
  }
</script>

<div class="card p-4">
  <div class="flex items-center justify-between mb-4">
    <div class="flex items-center gap-2">
      <HardDrive size={16} class="text-accent" />
      <h3 class="text-sm font-semibold text-text-primary">Log Files</h3>
      {#if logs.length > 0}
        <span class="rounded-full bg-surface-2 px-1.5 py-0.5 text-2xs font-medium text-text-secondary">
          {logs.length}
        </span>
      {/if}
    </div>
    {#if onRefresh}
      <button
        onclick={onRefresh}
        disabled={loading}
        class="flex items-center gap-1.5 rounded-lg bg-surface-2 px-2.5 py-1.5 text-2xs font-medium text-text-secondary hover:bg-surface-3 disabled:opacity-50"
      >
        {#if loading}
          <Loader2 size={12} class="animate-spin" />
        {:else}
          <Download size={12} />
        {/if}
        Refresh
      </button>
    {/if}
  </div>

  {#if loading && logs.length === 0}
    <div class="flex items-center justify-center py-8">
      <Loader2 size={24} class="text-accent animate-spin" />
    </div>
  {:else if logs.length === 0}
    <div class="flex flex-col items-center justify-center py-8 text-center">
      <FileText size={32} class="text-text-tertiary mb-2" />
      <p class="text-sm text-text-secondary">No log files available</p>
      <p class="text-2xs text-text-tertiary mt-1">Logs will appear here when device starts logging</p>
    </div>
  {:else}
    <div class="divide-y divide-border">
      {#each logs as log (log.filename)}
        <div class="flex items-center justify-between py-2.5 group">
          <div class="flex items-center gap-3 min-w-0 flex-1">
            <FileText size={16} class="text-text-tertiary shrink-0" />
            <div class="min-w-0">
              <p class="text-xs font-medium text-text-primary font-mono truncate">
                {log.filename}
              </p>
              <p class="text-2xs text-text-tertiary">
                {formatBytes(log.size_bytes)} - {formatDate(log.created_at)}
              </p>
            </div>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            {#if log.is_active}
              <span class="inline-flex items-center gap-1 rounded-full bg-accent-muted px-2 py-0.5 text-[10px] font-medium text-accent">
                <span class="h-1.5 w-1.5 rounded-full bg-accent animate-pulse"></span>
                Active
              </span>
            {/if}
            <button
              onclick={() => handleDownload(log.filename)}
              class="rounded p-1.5 text-text-tertiary hover:text-accent hover:bg-surface-2 transition-colors opacity-0 group-hover:opacity-100"
              title="Download log file"
            >
              <Download size={14} />
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
