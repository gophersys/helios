<script lang="ts">
  // Software-visibility canvas: a read-only, live map of each Kubernetes cluster's architecture,
  // rendered from snapshots introspected off the real clusters. Pick a cluster, switch views
  // (architecture / data-flow), click a node for detail. The data is the topology contract; this
  // page only renders it.
  import { listClusters, getTopology } from '$lib/topology/load';
  import ServiceCanvas from '$lib/topology/ServiceCanvas.svelte';

  const clusters = listClusters();
  let selectedId = $state(clusters[0]?.id ?? '');
  const topology = $derived(getTopology(selectedId));
</script>

<div class="page">
  <header class="head">
    <div class="title">
      <h1>Clusters</h1>
      <p>Live architecture of every connected Kubernetes cluster — read-only.</p>
    </div>
    <div class="pills">
      {#each clusters as c}
        <button class="pill" class:active={selectedId === c.id} onclick={() => (selectedId = c.id)}>
          <span class="cn">{c.name}</span>
          <span class="cm">{c.nodeCount} services · {c.namespaces} namespaces</span>
        </button>
      {/each}
    </div>
  </header>

  {#if topology}
    <div class="canvas">
      {#key topology.clusterId}
        <ServiceCanvas {topology} />
      {/key}
    </div>
  {:else}
    <div class="empty">No cluster snapshots found.</div>
  {/if}
</div>

<style>
  .page { display: flex; flex-direction: column; height: 100%; min-height: 0; }
  .head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; padding: 20px 24px 14px; flex-wrap: wrap; }
  .title h1 { margin: 0; font-size: 20px; font-weight: 700; color: var(--eden-app-fg, #c0caf5); }
  .title p { margin: 4px 0 0; color: var(--eden-app-muted, #7a82a8); font-size: 13px; }
  .pills { display: flex; gap: 8px; }
  .pill { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; background: var(--eden-app-rail-bg, #12141d); border: 1px solid var(--eden-app-line, #2b2f44); border-radius: 10px; padding: 8px 14px; cursor: pointer; min-width: 150px; }
  .pill:hover { border-color: #3a4060; }
  .pill.active { border-color: #7aa2f7; background: #161a28; }
  .cn { font-weight: 600; font-size: 13px; color: var(--eden-app-fg, #c0caf5); }
  .cm { font-size: 11px; color: var(--eden-app-muted, #7a82a8); }
  .canvas { flex: 1; min-height: 0; margin: 0 16px 16px; border: 1px solid var(--eden-app-line, #2b2f44); border-radius: 14px; overflow: hidden; }
  .empty { padding: 40px; color: #7a82a8; }
</style>
