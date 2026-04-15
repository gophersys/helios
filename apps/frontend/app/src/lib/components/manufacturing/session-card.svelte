<script lang="ts">
  import { goto } from '$app/navigation';
  import { CheckCircle2, XCircle, Cpu, Package, FlaskConical } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import { formatTimeAgo, formatDuration, formatDateTime } from '$lib/utils/formatting';
  import type { ManufacturingSession } from '$lib/types/models';

  let { session }: { session: ManufacturingSession } = $props();

  // Unit counts from server-provided aggregates (or compute from runs as fallback)
  const runs = $derived(session.runs || []);
  const totalUnits = $derived((session as any).totalUnits ?? runs.reduce((sum: number, r: any) => sum + (r.targetCount || 0), 0));
  const passedUnits = $derived((session as any).passedUnits ?? runs.reduce((sum: number, r: any) => sum + (r.passedCount || 0), 0));
  const failedUnits = $derived((session as any).failedUnits ?? runs.reduce((sum: number, r: any) => sum + (r.failedCount || 0), 0));

  const duration = $derived.by(() => {
    if (!session.startedAt) return null;
    const start = new Date(session.startedAt).getTime();
    const end = session.endedAt ? new Date(session.endedAt).getTime() : Date.now();
    return formatDuration(end - start);
  });

  // Firmware version from assetSet
  const fwVersion = $derived(
    session.assetSet ? `v${session.assetSet.version}` : null
  );
  const fwVariant = $derived(session.assetSet?.variant || null);

  // Test package version from session config
  const testVersion = $derived(
    (session.config as Record<string, any>)?.testPackageVersion || null
  );
</script>

<button
  onclick={() => goto(`/manufacturing/session/${session.id}`)}
  class="flex w-full items-center gap-4 px-4 py-3 text-left transition-colors hover:bg-surface-2/50"
  class:opacity-60={session.status === 'ARCHIVED'}
>
  <!-- Left: Session info -->
  <div class="min-w-0 flex-1">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-sm font-medium text-text-primary">
        {session.product?.name || 'Unknown'}
      </span>
      <StatusBadge status={session.status} />
      {#if session.status === 'ACTIVE' && session.runnerStatus}
        <span class="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-2xs font-medium
          {session.runnerStatus === 'READY' ? 'bg-success-muted text-success' :
           session.runnerStatus === 'ERROR' ? 'bg-error-muted text-error' :
           'bg-warning-muted text-warning'}">
          <span class="h-1.5 w-1.5 rounded-full {session.runnerStatus === 'READY' ? 'bg-success' : session.runnerStatus === 'ERROR' ? 'bg-error' : 'bg-warning animate-pulse'}"></span>
          {session.runnerStatus}
        </span>
      {/if}
    </div>

    <!-- Details row -->
    <div class="flex items-center gap-3 mt-1.5 text-2xs flex-wrap">
      {#if session.fixture?.name}
        <span class="text-text-secondary">{session.fixture.name}</span>
      {/if}
      {#if session.operator?.name}
        <span class="text-text-tertiary">{session.operator.name}</span>
      {/if}
      {#if fwVersion}
        <span class="inline-flex items-center gap-1 text-text-secondary">
          <Package size={10} class="text-text-tertiary" />
          {fwVersion}{#if fwVariant} <span class="text-text-tertiary">({fwVariant})</span>{/if}
        </span>
      {/if}
      {#if testVersion}
        <span class="inline-flex items-center gap-1 text-text-tertiary font-mono">
          <FlaskConical size={10} />
          {testVersion}
        </span>
      {/if}
    </div>
  </div>

  <!-- Center: Unit pass/fail counts -->
  <div class="flex items-center gap-3 shrink-0">
    {#if totalUnits > 0}
      <span class="flex items-center gap-1">
        <CheckCircle2 size={12} class="text-success" />
        <span class="text-sm font-semibold text-success tabular-nums">{passedUnits}</span>
      </span>
      {#if failedUnits > 0}
        <span class="flex items-center gap-1">
          <XCircle size={12} class="text-error" />
          <span class="text-sm font-semibold text-error tabular-nums">{failedUnits}</span>
        </span>
      {/if}
      <span class="text-2xs text-text-tertiary">
        {totalUnits} unit{totalUnits !== 1 ? 's' : ''}
      </span>
    {:else}
      <span class="text-2xs text-text-tertiary">No units tested</span>
    {/if}
  </div>

  <!-- Right: Duration + time -->
  <div class="flex flex-col items-end gap-1 text-2xs text-text-tertiary shrink-0">
    {#if duration}
      <span class="tabular-nums font-medium text-text-secondary">{duration}</span>
    {/if}
    {#if session.startedAt}
      <span title={formatDateTime(session.startedAt)}>
        {formatTimeAgo(session.startedAt)}
      </span>
    {/if}
  </div>
</button>
