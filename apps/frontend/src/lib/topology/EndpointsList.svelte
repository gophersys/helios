<script lang="ts">
  // The Endpoints lens — the public edge. One row per ingress host: host → service:port → workload,
  // the row inheriting the chain's worst health (a broken backend floats to the top). A directional
  // list, not a graph (a graph is overkill for <=10 entrypoints). Derived from the routes/selects
  // edges already in the snapshot.
  import type { ClusterModel } from './model';
  import { clusters } from './clustersState.svelte';
  import StatusGlyph from './StatusGlyph.svelte';

  let { model }: { model: ClusterModel } = $props();
  let onlyBroken = $state(false);

  const rows = $derived(
    model.endpoints.filter((e) => {
      if (onlyBroken && e.status === 'ok') return false;
      if (clusters.namespaces.size && !clusters.namespaces.has(e.namespace)) return false;
      const q = clusters.query.trim().toLowerCase();
      if (
        q &&
        !`${e.host} ${e.namespace} ${e.service?.name ?? ''} ${e.workload?.name ?? ''}`
          .toLowerCase()
          .includes(q)
      )
        return false;
      return true;
    }),
  );

  function copy(host: string): void {
    void navigator.clipboard?.writeText(host).catch(() => {});
  }
</script>

<div class="wrap">
  <div class="head">
    <span class="count">{rows.length} public {rows.length === 1 ? 'endpoint' : 'endpoints'}</span>
    <label class="tog"><input type="checkbox" bind:checked={onlyBroken} /> only broken</label>
  </div>

  {#if rows.length === 0}
    <p class="empty">No public ingress endpoints{onlyBroken ? ' are broken' : ''}.</p>
  {/if}

  <ul class="rows">
    {#each rows as e (e.id)}
      <li class="row" class:bad={e.status !== 'ok'}>
        <StatusGlyph status={e.status} size={13} />
        <a
          class="host"
          href={`https://${e.host}`}
          target="_blank"
          rel="noreferrer"
          title="open {e.host}">{e.host}</a
        >
        <button class="cp" title="copy host" onclick={() => copy(e.host)}>⧉</button>
        <span class="arr">→</span>
        <button class="seg svc" onclick={() => e.service && clusters.focus(e.service.id)}>
          {e.service?.name ?? '—'}{#if e.port}<span class="port">:{e.port}</span>{/if}
        </button>
        <span class="arr">→</span>
        <button
          class="seg wl"
          onclick={() => clusters.focus((e.workload ?? e.service ?? e.ingress).id)}
        >
          {e.workload?.name ?? e.service?.name ?? e.ingress.name}
        </button>
        <span class="ns">{e.namespace}</span>
      </li>
    {/each}
  </ul>
</div>

<style>
  .wrap {
    padding: 18px 20px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .count {
    font-weight: 600;
    color: var(--eden-app-fg);
  }
  .tog {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: var(--font-size-caption);
    color: var(--eden-app-muted);
    cursor: pointer;
  }
  .empty {
    color: var(--eden-app-muted);
  }
  .rows {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 10px 14px;
    background: var(--eden-app-panel-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: 10px;
    flex-wrap: wrap;
  }
  .row.bad {
    border-color: color-mix(in oklab, var(--color-error) 45%, var(--eden-app-line));
  }
  .host {
    font-family: var(--font-code);
    font-size: var(--font-size-label);
    font-weight: 600;
    color: var(--eden-app-fg);
    text-decoration: none;
  }
  .host:hover {
    color: var(--eden-app-accent);
    text-decoration: underline;
  }
  .cp {
    background: none;
    border: 0;
    color: var(--eden-app-muted);
    cursor: pointer;
    font-size: var(--font-size-caption);
  }
  .arr {
    color: var(--eden-app-muted);
  }
  .seg {
    display: inline-flex;
    align-items: center;
    background: var(--eden-app-rail-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: 7px;
    padding: 3px 9px;
    font: inherit;
    font-size: var(--font-size-label);
    color: var(--eden-app-fg);
    cursor: pointer;
  }
  .seg:hover {
    border-color: var(--eden-app-accent);
  }
  .port {
    color: var(--eden-app-muted);
    font-family: var(--font-code);
  }
  .ns {
    margin-inline-start: auto;
    font-size: var(--font-size-caption);
    color: var(--eden-app-muted);
    font-family: var(--font-code);
  }
</style>
