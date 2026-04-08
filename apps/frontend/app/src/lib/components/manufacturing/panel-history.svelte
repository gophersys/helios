<script lang="ts">
  import { ChevronDown, ChevronRight, CheckCircle2, XCircle } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import UnitCard from './unit-card.svelte';
  import { formatDuration } from '$lib/utils/formatting';
  import type { ManufacturingPanel } from '$lib/types/models';

  let { panels }: { panels: ManufacturingPanel[] } = $props();

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

  function getPanelDuration(panel: ManufacturingPanel): string | null {
    if (!panel.startedAt) return null;
    const start = new Date(panel.startedAt).getTime();
    const end = panel.finishedAt ? new Date(panel.finishedAt).getTime() : Date.now();
    return formatDuration(end - start);
  }
</script>

{#if panels.length === 0}
  <p class="text-sm text-text-tertiary py-4 text-center">No completed panels yet.</p>
{:else}
  <div class="space-y-2">
    {#each panels as panel (panel.id)}
      {@const expanded = expandedPanels.has(panel.id)}
      {@const panelDuration = getPanelDuration(panel)}
      <div class="rounded-lg border border-border bg-surface-0 overflow-hidden">
        <!-- Panel header (accordion trigger) -->
        <button
          onclick={() => togglePanel(panel.id)}
          class="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-2/50"
        >
          <div class="flex-shrink-0 text-text-tertiary">
            {#if expanded}
              <ChevronDown size={14} />
            {:else}
              <ChevronRight size={14} />
            {/if}
          </div>

          <span class="text-xs font-medium text-text-primary">
            Panel {panel.panelIndex + 1}
          </span>
          <span class="text-2xs font-mono text-text-secondary">{panel.qrCode}</span>

          <div class="flex items-center gap-2 ml-auto">
            <span class="flex items-center gap-1 text-2xs">
              <CheckCircle2 size={11} class="text-success" />
              <span class="font-medium text-text-primary">{panel.passCount}</span>
            </span>
            {#if panel.failCount > 0}
              <span class="flex items-center gap-1 text-2xs text-error">
                <XCircle size={11} />
                <span class="font-medium">{panel.failCount}</span>
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
              {#each panel.units as unit (unit.id)}
                <UnitCard {unit} />
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/each}
  </div>
{/if}
