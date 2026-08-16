<script lang="ts">
  import { ChevronDown, ChevronRight, CheckCircle2, XCircle } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import UnitCard from './unit-card.svelte';
  import { formatDuration } from '$lib/utils/formatting';
  import type { TestRun } from '$lib/types/models';

  let { panels, onSelectUnit }: { panels: TestRun[]; onSelectUnit?: (panel: TestRun, target: import('$lib/types/models').RunTarget) => void } = $props();

  let expandedPanels = $state<Set<string>>(new Set());

  function togglePanel(panelId: string) {
    const next = new Set(expandedPanels);
    if (next.has(panelId)) {
      next.delete(panelId);
    } else {
      next.add(panelId);
    }
    expandedPanels = next;
  }

  function getPanelDuration(panel: TestRun): string | null {
    if (!panel.startedAt) return null;
    const start = new Date(panel.startedAt).getTime();
    const end = panel.completedAt ? new Date(panel.completedAt).getTime() : Date.now();
    return formatDuration(end - start);
  }
</script>

{#if panels.length === 0}
  <p class="text-sm text-text-tertiary py-4 text-center">No completed panels yet.</p>
{:else}
  <div class="space-y-2">
    {#each panels as panel, idx (panel.id)}
      {@const expanded = expandedPanels.has(panel.id)}
      {@const panelDuration = getPanelDuration(panel)}
      {@const targets = panel.targets || []}
      <div class="rounded-lg border border-border bg-surface-0 overflow-hidden">
        <!-- Panel header (accordion trigger) -->
        <button
          onclick={() => togglePanel(panel.id)}
          class="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-2/50"
        >
          <div class="shrink-0 text-text-tertiary">
            {#if expanded}
              <ChevronDown size={14} />
            {:else}
              <ChevronRight size={14} />
            {/if}
          </div>

          <span class="text-xs font-medium text-text-primary">
            Panel {idx + 1}
          </span>
          <span class="text-2xs font-mono text-text-secondary">{panel.panelIdentifier || panel.id.slice(0, 8)}</span>

          <div class="flex items-center gap-2 ml-auto">
            <span class="flex items-center gap-1 text-2xs">
              <CheckCircle2 size={11} class="text-success" />
              <span class="font-medium text-text-primary">{panel.passedCount}</span>
            </span>
            {#if panel.failedCount > 0}
              <span class="flex items-center gap-1 text-2xs text-error">
                <XCircle size={11} />
                <span class="font-medium">{panel.failedCount}</span>
              </span>
            {/if}
            {#if panelDuration}
              <span class="text-2xs text-text-tertiary tabular-nums">{panelDuration}</span>
            {/if}
            <StatusBadge status={panel.status} />
          </div>
        </button>

        <!-- Expanded content -->
        {#if expanded}
          <div class="border-t border-border-subtle px-4 py-3">
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {#each targets as target (target.id)}
                <UnitCard unit={target} onclick={onSelectUnit ? () => onSelectUnit(panel, target) : undefined} />
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/each}
  </div>
{/if}
