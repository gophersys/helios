<script lang="ts">
  // Clusters — "Atlas": an overview-first software-visibility surface. One catalog (the topology
  // contract, derived once in model.ts), many lenses (Overview · Endpoints · Service Map · Inventory)
  // sharing ONE filter/scope/focus state mirrored to the URL. Default entry answers "is it healthy /
  // what's exposed / what's broken" before showing any graph. Read-only; Eden light theme.
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { listClusters, getModel } from '$lib/topology/load';
  import { clusters, LENSES } from '$lib/topology/clustersState.svelte';
  import ScorecardBanner from '$lib/topology/ScorecardBanner.svelte';
  import OverviewGrid from '$lib/topology/OverviewGrid.svelte';
  import EndpointsList from '$lib/topology/EndpointsList.svelte';
  import InventoryTable from '$lib/topology/InventoryTable.svelte';
  import ServiceCanvas from '$lib/topology/ServiceCanvas.svelte';
  import DetailDrawer from '$lib/topology/DetailDrawer.svelte';
  import Legend from '$lib/topology/Legend.svelte';
  import StatusGlyph from '$lib/topology/StatusGlyph.svelte';

  const clusterList = listClusters();
  if (!clusters.clusterId) clusters.clusterId = clusterList[0]?.id ?? '';

  const model = $derived(getModel(clusters.clusterId));

  // URL ⇄ state: hydrate on mount (deep-link / reload), then mirror every change back.
  onMount(() => {
    const params = new URLSearchParams(location.search);
    if ([...params.keys()].length) clusters.applyQuery(params, clusterList[0]?.id ?? '');
  });
  $effect(() => {
    if (!browser) return;
    const qs = clusters.toQuery().toString();
    history.replaceState(history.state, '', qs ? `?${qs}` : location.pathname);
  });
</script>

<svelte:head><title>Eden — Clusters</title></svelte:head>

<div class="atlas">
  <header class="top">
    <div class="titles">
      <h1>Clusters</h1>
      <p>Live architecture of every connected Kubernetes cluster — read-only.</p>
    </div>
    <div class="switch" role="tablist" aria-label="cluster">
      {#each clusterList as c}
        <button
          class="seg"
          class:active={clusters.clusterId === c.id}
          onclick={() => clusters.setCluster(c.id)}
        >
          <StatusGlyph status={c.status} size={10} />
          <span>{c.name}</span>
        </button>
      {/each}
    </div>
  </header>

  {#if model}
    <ScorecardBanner {model} />

    <nav class="tabs">
      <div class="lenses">
        {#each LENSES as l}
          <button
            class="tab"
            class:active={clusters.lens === l.id}
            onclick={() => clusters.setLens(l.id)}
          >
            {l.title}
          </button>
        {/each}
      </div>
      <div class="search">
        <input
          type="search"
          placeholder="Search name · namespace · image · host…"
          value={clusters.query}
          oninput={(e) => (clusters.query = e.currentTarget.value)}
        />
        {#if clusters.hasFilters}
          <button class="clearall" onclick={() => clusters.clearFilters()}>clear filters</button>
        {/if}
      </div>
    </nav>

    <div class="body">
      <aside class="rail">
        <div class="rsec">
          <span class="cap">Namespaces</span>
          <div class="nss">
            {#each model.namespaces as ns}
              <button
                class="nsf"
                class:on={clusters.namespaces.has(ns.name)}
                onclick={() => clusters.toggleNamespace(ns.name)}
              >
                <StatusGlyph status={ns.rollup} size={9} />
                <span class="nsn">{ns.name}</span>
                <span class="nsc">{ns.total}</span>
              </button>
            {/each}
          </div>
        </div>
        <div class="rsec"><Legend showEdges={clusters.lens === 'map'} /></div>
      </aside>

      <section class="surface">
        {#if clusters.lens === 'map'}
          <ServiceCanvas {model} />
        {:else}
          <div class="scroll">
            {#if clusters.lens === 'overview'}
              <OverviewGrid {model} />
            {:else if clusters.lens === 'endpoints'}
              <EndpointsList {model} />
            {:else}
              <InventoryTable {model} />
            {/if}
          </div>
        {/if}
      </section>
    </div>

    <DetailDrawer {model} />
  {:else}
    <div class="empty">No cluster snapshots found.</div>
  {/if}
</div>

<style>
  .atlas {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    padding: 18px 20px 0;
    gap: 14px;
    background: var(--eden-app-bg);
    color: var(--eden-app-fg);
  }
  .top {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
  }
  .titles h1 {
    margin: 0;
    font-size: var(--font-size-body-large);
    font-weight: 700;
  }
  .titles p {
    margin: 3px 0 0;
    color: var(--eden-app-muted);
    font-size: var(--font-size-label);
  }
  .switch {
    display: inline-flex;
    background: var(--eden-app-rail-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: 10px;
    padding: 3px;
    gap: 2px;
  }
  .seg {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 6px 13px;
    border: 0;
    border-radius: 8px;
    background: none;
    color: var(--eden-app-muted);
    font: inherit;
    font-size: var(--font-size-label);
    font-weight: 600;
    cursor: pointer;
  }
  .seg.active {
    background: var(--eden-app-panel-bg);
    color: var(--eden-app-fg);
    box-shadow: 0 1px 2px color-mix(in oklab, var(--eden-app-fg) 8%, transparent);
  }
  .tabs {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    border-bottom: 1px solid var(--eden-app-line);
    flex-wrap: wrap;
  }
  .lenses {
    display: flex;
    gap: 2px;
  }
  .tab {
    background: none;
    border: 0;
    border-bottom: 2px solid transparent;
    padding: 9px 14px;
    font: inherit;
    font-size: var(--font-size-label);
    font-weight: 600;
    color: var(--eden-app-muted);
    cursor: pointer;
    margin-bottom: -1px;
  }
  .tab:hover {
    color: var(--eden-app-fg);
  }
  .tab.active {
    color: var(--eden-app-fg);
    border-bottom-color: var(--eden-app-accent);
  }
  .search {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding-bottom: 6px;
  }
  .search input {
    width: 280px;
    max-width: 42vw;
    padding: 7px 11px;
    border: 1px solid var(--eden-app-line);
    border-radius: 8px;
    background: var(--eden-app-panel-bg);
    color: var(--eden-app-fg);
    font: inherit;
    font-size: var(--font-size-label);
  }
  .search input:focus {
    outline: 2px solid color-mix(in oklab, var(--eden-app-accent) 55%, transparent);
    border-color: var(--eden-app-accent);
  }
  .clearall {
    background: none;
    border: 0;
    color: var(--eden-app-muted);
    font: inherit;
    font-size: var(--font-size-caption);
    text-decoration: underline;
    cursor: pointer;
  }
  .body {
    display: grid;
    grid-template-columns: 196px 1fr;
    gap: 0;
    flex: 1;
    min-height: 0;
  }
  .rail {
    border-inline-end: 1px solid var(--eden-app-line);
    overflow: auto;
    padding: 14px 14px 14px 0;
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  .rsec {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .cap {
    font-size: var(--font-size-caption);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--eden-app-muted);
    opacity: 0.8;
  }
  .nss {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }
  .nsf {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 8px;
    background: none;
    border: 0;
    border-radius: 7px;
    font: inherit;
    font-size: var(--font-size-caption);
    color: var(--eden-app-fg);
    cursor: pointer;
    text-align: start;
  }
  .nsf:hover {
    background: var(--eden-app-rail-bg);
  }
  .nsf.on {
    background: color-mix(in oklab, var(--eden-app-accent) 14%, var(--eden-app-panel-bg));
  }
  .nsn {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .nsc {
    color: var(--eden-app-muted);
    font-family: var(--font-code);
    font-size: var(--font-size-caption);
  }
  .surface {
    display: flex;
    flex-direction: column;
    min-height: 0;
    min-width: 0;
  }
  .scroll {
    flex: 1;
    min-height: 0;
    overflow: auto;
  }
  .empty {
    padding: 40px;
    color: var(--eden-app-muted);
  }
</style>
