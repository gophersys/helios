<script lang="ts">
  import { onDestroy } from 'svelte';
  import { ArrowLeft, Factory, User, Clock, Cpu, Wifi, Archive, Trash2, StopCircle, Server } from 'lucide-svelte';
  import { goto } from '$app/navigation';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import { formatDateTime, formatDuration } from '$lib/utils/formatting';
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

  let elapsed = $state('');
  let timer: ReturnType<typeof setInterval> | null = null;

  const runs = $derived(session.runs || []);
  const panelCount = $derived(runs.length);
  const passCount = $derived(runs.reduce((sum, r) => sum + (r.passedCount || 0), 0));
  const failCount = $derived(runs.reduce((sum, r) => sum + (r.failedCount || 0), 0));

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
  class="mb-3 flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
>
  <ArrowLeft size={14} />
  Manufacturing
</button>

<!-- Session info card -->
<div class="card card-sm mb-6">
  <!-- Top row: title + status + stats -->
  <div class="flex items-start justify-between gap-4 mb-4">
    <div>
      <div class="flex items-center gap-3">
        <h1 class="text-lg font-semibold text-text-primary">
          {session.product?.name || 'Session'}
        </h1>
        <StatusBadge status={session.status} />
        {#if runnerDisplay}
          <span class="flex items-center gap-1.5 text-xs">
            <span class="inline-block h-2 w-2 rounded-full {runnerDisplay.dotClass}"></span>
            <span class="text-text-secondary">{runnerDisplay.label}</span>
          </span>
        {/if}
      </div>
    </div>

    <!-- Stat counters -->
    <div class="flex items-center gap-4 shrink-0">
      <div class="text-center">
        <div class="text-xl font-semibold text-text-primary tabular-nums">{panelCount}</div>
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Panels</div>
      </div>
      <div class="text-center">
        <div class="text-xl font-semibold text-success tabular-nums">{passCount}</div>
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Pass</div>
      </div>
      <div class="text-center">
        <div class="text-xl font-semibold tabular-nums {failCount > 0 ? 'text-error' : 'text-text-primary'}">{failCount}</div>
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Fail</div>
      </div>
    </div>
  </div>

  <!-- Detail grid -->
  <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 border-t border-border pt-4">
    <div class="flex items-start gap-2">
      <Factory size={14} class="text-text-tertiary mt-0.5 shrink-0" />
      <div>
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Fixture</div>
        <div class="text-sm text-text-primary">{session.fixture?.name || '—'}</div>
      </div>
    </div>
    <div class="flex items-start gap-2">
      <User size={14} class="text-text-tertiary mt-0.5 shrink-0" />
      <div>
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Operator</div>
        <div class="text-sm text-text-primary">{session.operator?.name || '—'}</div>
      </div>
    </div>
    <div class="flex items-start gap-2">
      <Clock size={14} class="text-text-tertiary mt-0.5 shrink-0" />
      <div>
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">{session.status === 'ACTIVE' ? 'Elapsed' : 'Duration'}</div>
        <div class="text-sm text-text-primary tabular-nums">{elapsed || '—'}</div>
        {#if session.startedAt}
          <div class="text-2xs text-text-tertiary">{formatDateTime(session.startedAt)}</div>
        {/if}
      </div>
    </div>
    <div class="flex items-start gap-2">
      <Cpu size={14} class="text-text-tertiary mt-0.5 shrink-0" />
      <div>
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Firmware</div>
        {#if session.assetSet}
          <div class="text-sm text-text-primary">v{session.assetSet.version}</div>
          <div class="text-2xs text-text-tertiary">{session.assetSet.variant}</div>
        {:else}
          <div class="text-sm text-text-tertiary">—</div>
        {/if}
      </div>
    </div>
    {#if ((session.config as Record<string, any>)?.fixtureSnapshot?.slots?.filter((s: any) => s.mtibDeploymentName) || []).length > 0}
      {@const mtibSlots = ((session.config as Record<string, any>)?.fixtureSnapshot?.slots?.filter((s: any) => s.mtibDeploymentName) || [])}
      <div class="flex items-start gap-2">
        <Server size={14} class="text-text-tertiary mt-0.5 shrink-0" />
        <div>
          <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">MTIBs</div>
          <div class="text-sm text-text-primary">{mtibSlots.length} node{mtibSlots.length !== 1 ? 's' : ''}</div>
          {#if mtibSlots[0]?.mtibImageSha}
            <div class="text-2xs text-text-tertiary font-mono">{mtibSlots[0].mtibImageSha.split(':').pop()?.substring(0, 12) || ''}</div>
          {/if}
        </div>
      </div>
    {/if}
  </div>

  <!-- Action buttons -->
  {#if canManage}
    <div class="flex items-center gap-2 border-t border-border pt-4 mt-4">
      {#if activeRunExists}
        <div class="flex items-center gap-2 text-accent text-sm font-medium">
          <span class="relative flex h-2 w-2">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2 w-2 bg-accent"></span>
          </span>
          Run in progress — scanning locked
        </div>
      {/if}
      {#if session.status === 'ACTIVE'}
        <button
          onclick={onEndSession}
          disabled={activeRunExists}
          class="btn btn-sm btn-secondary {activeRunExists ? 'ml-auto' : ''}"
          title={activeRunExists ? 'A test run is actively executing — wait for it to finish' : 'End this session'}
        >
          <StopCircle size={14} />
          End Session
        </button>
      {/if}
      {#if session.status === 'COMPLETED' || session.status === 'CANCELLED'}
        <button onclick={onArchive} class="btn btn-sm bg-warning-muted text-warning hover:bg-warning/20">
          <Archive size={14} />
          Archive
        </button>
      {/if}
      {#if session.status === 'ARCHIVED'}
        <button onclick={onDelete} class="btn btn-sm btn-danger">
          <Trash2 size={14} />
          Delete
        </button>
      {/if}
    </div>
  {/if}
</div>
