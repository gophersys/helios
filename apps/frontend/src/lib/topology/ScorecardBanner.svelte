<script lang="ts">
  // The Scorecard — the 5-second read. One dominant worst-of word, clickable count chips (each a
  // status filter), the size totals, and a provenance chip that ambers when the snapshot is stale.
  // Pure projection of model.rollup; zero graph.
  import type { ClusterModel } from './model';
  import { STATUS } from './status';
  import { clusters } from './clustersState.svelte';
  import StatusGlyph from './StatusGlyph.svelte';

  let { model }: { model: ClusterModel } = $props();
  const r = $derived(model.rollup);

  // count chips in severity order, only those with a non-zero count (plus always ok)
  const order = ['down', 'warn', 'progressing', 'ok', 'unknown'] as const;
  const chips = $derived(order.filter((s) => r.byStatus[s] > 0));

  const totals = $derived([
    { label: 'namespaces', value: r.totals.namespaces },
    { label: 'workloads', value: r.totals.workloads },
    { label: 'services', value: r.totals.services },
    { label: 'exposed', value: r.totals.hosts },
    { label: 'volumes', value: r.totals.volumes },
  ]);

  const age = $derived(relTime(model.topo.generatedAt));
  function relTime(iso: string): { text: string; stale: boolean } {
    const ms = Date.now() - new Date(iso).getTime();
    if (!Number.isFinite(ms) || ms < 0) return { text: 'just now', stale: false };
    const m = Math.floor(ms / 60000);
    const stale = m > 15;
    if (m < 1) return { text: 'just now', stale };
    if (m < 60) return { text: `${m}m ago`, stale };
    const h = Math.floor(m / 60);
    if (h < 24) return { text: `${h}h ago`, stale };
    return { text: `${Math.floor(h / 24)}d ago`, stale: true };
  }
</script>

<div class="bar" style="--tint: var({STATUS[r.status].token})">
  <div class="verdict">
    <StatusGlyph status={r.status} size={20} />
    <div class="vtext">
      <span class="word">{r.status === 'ok' ? 'All healthy' : STATUS[r.status].label}</span>
      <span class="sub">{r.totals.workloads + r.totals.services} components live</span>
    </div>
  </div>

  <div class="chips">
    {#each chips as s}
      <button
        class="chip"
        class:active={clusters.statuses.size === 1 && clusters.statuses.has(s)}
        style="--c: var({STATUS[s].token})"
        onclick={() => clusters.filterStatus(s)}
        title="Filter to {STATUS[s].label.toLowerCase()}"
      >
        <StatusGlyph status={s} size={11} />
        <b>{r.byStatus[s]}</b>
        <span>{STATUS[s].label.toLowerCase()}</span>
      </button>
    {/each}
    {#if clusters.statuses.size}
      <button class="clear" onclick={() => (clusters.statuses = new Set())}>clear</button>
    {/if}
  </div>

  <div class="totals">
    {#each totals as t}
      <div class="tot"><b>{t.value}</b><span>{t.label}</span></div>
    {/each}
  </div>

  <div class="prov" class:stale={age.stale} title="Snapshot freshness">
    <span class="dot"></span>
    {age.stale ? 'stale · ' : 'live · '}{age.text}
  </div>
</div>

<style>
  .bar {
    display: flex;
    align-items: center;
    gap: 22px;
    padding: 12px 20px;
    background: var(--eden-app-panel-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 12px);
    border-inline-start: 4px solid var(--tint);
    flex-wrap: wrap;
  }
  .verdict {
    display: flex;
    align-items: center;
    gap: 11px;
  }
  .vtext {
    display: flex;
    flex-direction: column;
    line-height: 1.15;
  }
  .word {
    font-weight: 700;
    font-size: var(--font-size-body);
    color: var(--eden-app-fg);
  }
  .sub {
    font-size: var(--font-size-caption);
    color: var(--eden-app-muted);
  }
  .chips {
    display: flex;
    align-items: center;
    gap: 7px;
    flex-wrap: wrap;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 11px 4px 8px;
    border-radius: 999px;
    border: 1px solid color-mix(in oklab, var(--c) 32%, transparent);
    background: color-mix(in oklab, var(--c) 9%, var(--eden-app-panel-bg));
    color: var(--eden-app-fg);
    font: inherit;
    font-size: var(--font-size-caption);
    cursor: pointer;
  }
  .chip b {
    font-variant-numeric: tabular-nums;
  }
  .chip span {
    color: var(--eden-app-muted);
  }
  .chip:hover {
    border-color: color-mix(in oklab, var(--c) 55%, transparent);
  }
  .chip.active {
    background: color-mix(in oklab, var(--c) 18%, var(--eden-app-panel-bg));
    border-color: var(--c);
  }
  .clear {
    background: none;
    border: 0;
    color: var(--eden-app-muted);
    font: inherit;
    font-size: var(--font-size-caption);
    text-decoration: underline;
    cursor: pointer;
  }
  .totals {
    display: flex;
    gap: 18px;
    margin-inline-start: auto;
  }
  .tot {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    line-height: 1.1;
  }
  .tot b {
    font-size: var(--font-size-body);
    color: var(--eden-app-fg);
    font-variant-numeric: tabular-nums;
  }
  .tot span {
    font-size: var(--font-size-caption);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--eden-app-muted);
  }
  .prov {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: var(--font-size-caption);
    color: var(--eden-app-muted);
    font-family: var(--font-code);
  }
  .prov .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--color-success);
  }
  .prov.stale .dot {
    background: var(--color-warning);
  }
</style>
