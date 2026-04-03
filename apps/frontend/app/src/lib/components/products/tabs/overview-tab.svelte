<script lang="ts">
  import { onMount } from 'svelte';
  import { CircuitBoard, Cpu, Hammer, FlaskConical, Clock, Activity } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TimeDisplay from '$lib/components/ui/time-display.svelte';
  import type { Product } from '$lib/types/models';

  interface Props {
    product: Product;
    canManage: boolean;
  }

  let { product, canManage }: Props = $props();

  const revisions = $derived(
    (product.boards || []).flatMap((b) => b.revisions || [])
  );
  const activeRevisions = $derived(revisions.filter((r) => r.status === 'ACTIVE'));
  const stageConfigs = $derived((product as any).stageConfigs || []);
  const enabledStages = $derived(stageConfigs.filter((s: any) => s.enabled));
</script>

<!-- Stats row -->
<div class="grid grid-cols-2 gap-3 sm:grid-cols-4 mb-6">
  <div class="rounded-lg border border-border bg-surface-0 p-3">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <CircuitBoard size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Revisions</span>
    </div>
    <div class="text-xl font-semibold text-text-primary">{revisions.length}</div>
    <div class="text-2xs text-text-tertiary">{activeRevisions.length} active</div>
  </div>
  <div class="rounded-lg border border-border bg-surface-0 p-3">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <FlaskConical size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Stages</span>
    </div>
    <div class="text-xl font-semibold text-text-primary">{enabledStages.length}<span class="text-sm text-text-tertiary">/{stageConfigs.length}</span></div>
    <div class="text-2xs text-text-tertiary">enabled</div>
  </div>
  <div class="rounded-lg border border-border bg-surface-0 p-3">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <Cpu size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Targets</span>
    </div>
    <div class="text-xl font-semibold text-text-primary">{product.targets?.length ?? 0}</div>
    <div class="text-2xs text-text-tertiary">SoC targets</div>
  </div>
  <div class="rounded-lg border border-border bg-surface-0 p-3">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <Hammer size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Firmware</span>
    </div>
    <div class="text-xl font-semibold text-text-primary">{product.firmwareSetCount ?? 0}</div>
    <div class="text-2xs text-text-tertiary">sets</div>
  </div>
</div>

<!-- Hardware revisions summary -->
<div class="mb-6">
  <h3 class="text-sm font-semibold text-text-primary mb-3">Hardware Revisions</h3>
  {#if revisions.length === 0}
    <p class="text-sm text-text-tertiary">No hardware revisions configured. Go to the Hardware tab to add one.</p>
  {:else}
    <div class="rounded-lg border border-border overflow-hidden">
      {#each revisions as rev}
        <div class="flex items-center gap-4 px-4 py-2.5 border-b border-border-subtle last:border-b-0">
          <div class="flex items-center gap-2 min-w-0">
            <CircuitBoard size={14} class="text-accent shrink-0" />
            <span class="text-sm font-semibold text-text-primary">{rev.version}</span>
            <StatusBadge status={rev.status} />
          </div>
          <span class="font-mono text-2xs text-text-tertiary">{rev.ckBoardsName}</span>
          <div class="flex-1"></div>
          {#if rev.targets && rev.targets.length > 0}
            <div class="flex gap-2">
              {#each rev.targets as target}
                <span class="font-mono text-2xs text-text-secondary">{target.role}: {target.soc}</span>
              {/each}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<!-- Stage overview -->
<div>
  <h3 class="text-sm font-semibold text-text-primary mb-3">Validation Stages</h3>
  {#if stageConfigs.length === 0}
    <p class="text-sm text-text-tertiary">No stages configured. Go to the Stages tab to set up validation.</p>
  {:else}
    <div class="rounded-lg border border-border overflow-hidden">
      {#each stageConfigs as cfg}
        <div class="flex items-center gap-4 px-4 py-2.5 border-b border-border-subtle last:border-b-0">
          <div class="flex items-center gap-2">
            <div class="w-6 h-6 flex items-center justify-center rounded text-[10px] font-bold {cfg.enabled ? 'bg-accent text-white' : 'bg-surface-2 text-text-tertiary'}">
              {cfg.stage}
            </div>
            <span class="text-sm font-medium text-text-primary">{cfg.name}</span>
          </div>
          <StatusBadge status={cfg.enabled ? 'ACTIVE' : 'DISABLED'} />
          <div class="flex-1"></div>
          {#if cfg.watchBranch}
            <span class="font-mono text-2xs text-text-tertiary">{cfg.watchBranch}</span>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>
