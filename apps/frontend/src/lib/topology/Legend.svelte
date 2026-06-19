<script lang="ts">
  // The legend — a status encoding is only "consistent" if decodable without tribal knowledge.
  // Shows the shape+colour+word for each status; in the Service Map it also keys the edge kinds.
  import type { Status } from './contract';
  import { STATUS } from './status';
  import StatusGlyph from './StatusGlyph.svelte';

  let { showEdges = false }: { showEdges?: boolean } = $props();
  const order: Status[] = ['ok', 'progressing', 'warn', 'down', 'unknown'];
</script>

<div class="legend">
  <div class="grp">
    <span class="cap">Health</span>
    {#each order as s}
      <span class="row"><StatusGlyph status={s} size={11} /> {STATUS[s].label}</span>
    {/each}
  </div>
  {#if showEdges}
    <div class="grp">
      <span class="cap">Links</span>
      <span class="row"><i class="ln routes"></i> routes (ingress→service)</span>
      <span class="row"><i class="ln depends"></i> depends</span>
      <span class="row"><i class="ln selects"></i> selects</span>
      <span class="row"><i class="ln mounts"></i> mounts</span>
    </div>
  {/if}
</div>

<style>
  .legend {
    display: flex;
    flex-direction: column;
    gap: 12px;
    font-size: 11.5px;
    color: var(--eden-app-muted);
  }
  .grp {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .cap {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--eden-app-muted);
    opacity: 0.8;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 7px;
    color: var(--eden-app-fg);
  }
  .ln {
    width: 16px;
    height: 0;
    flex: none;
    border-top: 2px solid var(--eden-app-line);
  }
  .ln.routes {
    border-top-color: var(--color-primary);
  }
  .ln.depends {
    border-top-color: var(--color-on-surface);
    opacity: 0.5;
  }
  .ln.selects {
    border-top-style: dashed;
    border-top-color: var(--color-outline);
  }
  .ln.mounts {
    border-top-style: dotted;
    border-top-color: var(--color-warning);
  }
</style>
