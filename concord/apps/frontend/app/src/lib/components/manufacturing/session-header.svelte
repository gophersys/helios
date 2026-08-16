<script lang="ts">
  import { onDestroy } from 'svelte';
  import { ArrowLeft, Factory, Clock, Cpu, Archive, Trash2, StopCircle, Download } from 'lucide-svelte';
  import { goto } from '$app/navigation';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import { formatDuration } from '$lib/utils/formatting';
  import { getToken } from '$lib/api';
  import type { ManufacturingSession } from '$lib/types/models';

  let {
    session,
    canManage = false,
    onEndSession,
    onArchive,
    onDelete,
    activeRunExists = false,
  }: {
    session: ManufacturingSession;
    canManage?: boolean;
    onEndSession?: () => void;
    onArchive?: () => void;
    onDelete?: () => void;
    activeRunExists?: boolean;
  } = $props();

  let downloadingReport = $state(false);
  let downloadError = $state<string | null>(null);

  const reportAvailable = $derived(
    session.status === 'COMPLETED' || session.status === 'ARCHIVED'
  );

  async function downloadReport(): Promise<void> {
    if (downloadingReport) return;
    downloadingReport = true;
    downloadError = null;
    try {
      const token = getToken();
      const res = await fetch(`/v2/manufacturing/sessions/${session.id}/report`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        let msg = `Report failed (${res.status})`;
        try {
          const body = await res.json();
          msg = body.errors?.[0]?.message || msg;
        } catch { /* non-json body */ }
        throw new Error(msg);
      }
      const blob = await res.blob();
      const dispo = res.headers.get('content-disposition') || '';
      const match = dispo.match(/filename="?([^";]+)"?/);
      const filename = match ? match[1] : `session-${session.id}-report.zip`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      downloadError = err instanceof Error ? err.message : 'Failed to download report';
      setTimeout(() => { downloadError = null; }, 4000);
    } finally {
      downloadingReport = false;
    }
  }

  let elapsed = $state('');
  let timer: ReturnType<typeof setInterval> | null = null;

  const runs = $derived(session.runs || []);

  // Deduplicate boards by SNR — keep latest result per unique board
  const boardResults = $derived.by(() => {
    const map = new Map<string, { snr: string; status: string; runCreatedAt: string }>();
    // Process runs newest-first so the first seen SNR is the latest result
    const sorted = [...runs].sort((a, b) =>
      new Date(b.createdAt || 0).getTime() - new Date(a.createdAt || 0).getTime()
    );
    for (const r of sorted) {
      for (const t of (r.targets || [])) {
        const snr = t.serialNumber || t.id;
        if (!map.has(snr)) {
          map.set(snr, { snr, status: t.status, runCreatedAt: r.createdAt || '' });
        }
      }
    }
    return Array.from(map.values());
  });

  const uniquePanels = $derived(new Set(runs.map(r => r.panelIdentifier || r.id)).size);
  const totalBoards = $derived(boardResults.length);
  const boardPassCount = $derived(boardResults.filter(b => b.status === 'PASSED').length);
  const boardFailCount = $derived(boardResults.filter(b => b.status === 'FAILED' || b.status === 'ERROR').length);

  const RUNNER_STATUS_CONFIG: Record<string, { dotClass: string; label: string }> = {
    CHECKING_MTIBS: { dotClass: 'bg-text-tertiary animate-pulse', label: 'Checking MTIBs...' },
    DEPLOYING: { dotClass: 'bg-text-tertiary animate-pulse', label: 'Deploying...' },
    READY: { dotClass: 'bg-success', label: 'Ready' },
    RUNNING: { dotClass: 'bg-warning animate-pulse', label: 'Running' },
    ERROR: { dotClass: 'bg-error', label: 'Error' },
  };

  const runnerDisplay = $derived(
    session.runnerStatus ? RUNNER_STATUS_CONFIG[session.runnerStatus] : null
  );

  function updateElapsed() {
    if (!session.startedAt) { elapsed = ''; return; }
    const start = new Date(session.startedAt).getTime();
    const end = session.endedAt ? new Date(session.endedAt).getTime() : Date.now();
    elapsed = formatDuration(end - start);
  }

  $effect(() => {
    updateElapsed();
    if (session.status === 'ACTIVE' && !timer) {
      timer = setInterval(updateElapsed, 1000);
    } else if (session.status !== 'ACTIVE' && timer) {
      clearInterval(timer);
      timer = null;
    }
  });

  onDestroy(() => { if (timer) clearInterval(timer); });
</script>

<!-- Back link -->
<button
  onclick={() => goto('/manufacturing')}
  class="mb-2 flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
>
  <ArrowLeft size={14} />
  Manufacturing
</button>

<!-- Compact single-row session header -->
<div class="flex items-center gap-2 mb-4 px-3 py-1.5 rounded-lg bg-surface-1 border border-border">
  <!-- Title + status -->
  <h1 class="text-sm font-semibold text-text-primary truncate">
    {session.product?.name || 'Session'}
  </h1>
  <StatusBadge status={session.status} />

  {#if runnerDisplay}
    <span class="flex items-center gap-1.5 text-xs shrink-0">
      <span class="inline-block h-1.5 w-1.5 rounded-full {runnerDisplay.dotClass}"></span>
      <span class="text-text-secondary">{runnerDisplay.label}</span>
    </span>
  {/if}

  <div class="w-px h-4 bg-border"></div>

  <!-- Metadata -->
  <div class="flex items-center gap-3 text-xs text-text-tertiary">
    <span class="flex items-center gap-1">
      <Factory size={12} />
      {session.fixture?.name || '—'}
    </span>
    {#if session.assetSet}
      <span class="flex items-center gap-1">
        <Cpu size={12} />
        <span class="font-mono text-2xs">v{session.assetSet.version}</span>
      </span>
    {/if}
    {#if (session.config as Record<string, any>)?.testPackageVersion}
      <span class="font-mono text-2xs bg-surface-2 px-1.5 py-0.5 rounded">
        app {(session.config as Record<string, any>).testPackageVersion}
      </span>
    {/if}
    <span class="flex items-center gap-1 tabular-nums">
      <Clock size={12} />
      {elapsed || '—'}
    </span>
  </div>

  <!-- Counters: unique boards pass/fail (latest result per SNR) -->
  <div class="flex items-center gap-3 text-xs shrink-0 ml-auto">
    <span class="text-text-secondary">{runs.length} run{runs.length !== 1 ? 's' : ''}</span>
    <span class="text-text-tertiary">&middot;</span>
    <span class="text-success font-medium">{boardPassCount}/{totalBoards} boards</span>
    {#if boardFailCount > 0}
      <span class="text-error font-medium">{boardFailCount} fail</span>
    {/if}
  </div>

  <div class="w-px h-4 bg-border"></div>

  <!-- Active run indicator -->
  {#if activeRunExists}
    <span class="flex items-center gap-1.5 text-xs text-accent font-medium shrink-0">
      <span class="relative flex h-1.5 w-1.5">
        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
        <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-accent"></span>
      </span>
      Running
    </span>
  {/if}

  <!-- Action buttons -->
  {#if canManage && session.status === 'ACTIVE'}
    <button
      onclick={onEndSession}
      disabled={activeRunExists}
      class="shrink-0 flex items-center gap-1.5 rounded-lg border border-error/30 bg-error/10 px-3 py-1 text-xs font-medium text-error hover:bg-error/20 transition-colors disabled:opacity-50"
      title={activeRunExists ? 'Wait for run to finish' : 'End session'}
    >
      <StopCircle size={12} />
      End
    </button>
  {/if}
  {#if reportAvailable}
    <button
      onclick={downloadReport}
      disabled={downloadingReport}
      class="shrink-0 flex items-center gap-1.5 rounded-lg border border-border bg-surface-0 px-3 py-1 text-xs font-medium text-text-secondary hover:bg-surface-2 hover:text-text-primary transition-colors disabled:opacity-60"
      title={downloadError || 'Download session report (.zip)'}
    >
      <Download size={12} />
      {downloadingReport ? 'Preparing…' : 'Download report'}
    </button>
  {/if}
  {#if canManage && (session.status === 'COMPLETED' || session.status === 'CANCELLED')}
    <button onclick={onArchive} class="btn btn-sm bg-warning-muted text-warning hover:bg-warning/20 shrink-0">
      <Archive size={12} />
      Archive
    </button>
  {/if}
  {#if canManage && session.status === 'ARCHIVED'}
    <button onclick={onDelete} class="btn btn-sm btn-danger shrink-0">
      <Trash2 size={12} />
      Delete
    </button>
  {/if}
</div>
