<script lang="ts">
  // The Inventory lens — the exact, sortable fallback when the question is "what exists, precisely".
  // Trades spatial structure for sort + scan. Honest kind column (the authoritative meta.kind, not
  // the producer's semantic guess). Shared filters apply; row click opens the drawer.
  import type { ClusterModel } from './model';
  import type { Status, TopoNode } from './contract';
  import { classOf } from './model';
  import { STATUS } from './status';
  import { clusters } from './clustersState.svelte';
  import StatusGlyph from './StatusGlyph.svelte';

  let { model }: { model: ClusterModel } = $props();

  type Col = 'status' | 'kind' | 'name' | 'namespace' | 'replicas' | 'ports' | 'image';
  let sortKey = $state<Col>('status');
  let asc = $state(false);

  const kindOf = (n: TopoNode) => n.meta.kind ?? classOf(n);

  function val(n: TopoNode, c: Col): string | number {
    switch (c) {
      case 'status':
        return STATUS[n.status ?? 'unknown'].severity;
      case 'kind':
        return kindOf(n);
      case 'name':
        return n.name;
      case 'namespace':
        return n.namespace ?? '';
      case 'replicas':
        return n.meta.replicas ?? '';
      case 'ports':
        return n.meta.ports ?? '';
      case 'image':
        return n.meta.image ?? '';
    }
  }

  const rows = $derived(
    model.members
      .filter((n) => clusters.matches(n))
      .slice()
      .sort((a, b) => {
        const va = val(a, sortKey);
        const vb = val(b, sortKey);
        let c = typeof va === 'number' && typeof vb === 'number' ? va - vb : String(va).localeCompare(String(vb));
        if (c === 0) c = a.name.localeCompare(b.name);
        return asc ? c : -c;
      }),
  );

  function sortBy(c: Col): void {
    if (sortKey === c) asc = !asc;
    else {
      sortKey = c;
      asc = c !== 'status'; // status defaults worst-first (desc)
    }
  }
  const cols: { key: Col; label: string }[] = [
    { key: 'status', label: 'Status' },
    { key: 'kind', label: 'Kind' },
    { key: 'name', label: 'Name' },
    { key: 'namespace', label: 'Namespace' },
    { key: 'replicas', label: 'Ready' },
    { key: 'ports', label: 'Ports' },
    { key: 'image', label: 'Image' },
  ];
</script>

<div class="wrap">
  <div class="count">{rows.length} {rows.length === 1 ? 'resource' : 'resources'}</div>
  <table>
    <thead>
      <tr>
        {#each cols as c}
          <th class:active={sortKey === c.key} onclick={() => sortBy(c.key)}>
            {c.label}{#if sortKey === c.key}<span class="caret">{asc ? '▲' : '▼'}</span>{/if}
          </th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#each rows as n (n.id)}
        <tr onclick={() => clusters.focus(n.id)}>
          <td class="st"><StatusGlyph status={(n.status ?? 'unknown') as Status} size={11} /> {STATUS[n.status ?? 'unknown'].label}</td>
          <td class="mono">{kindOf(n)}</td>
          <td class="nm">{n.name}{#if model.publicIds.has(n.id)}<span class="pub" title="public">🌐</span>{/if}</td>
          <td>{n.namespace ?? '—'}</td>
          <td class="mono">{n.meta.replicas ?? '—'}</td>
          <td class="mono pts">{n.meta.ports ?? '—'}</td>
          <td class="mono img" title={n.meta.image ?? ''}>{n.meta.image ?? '—'}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .wrap {
    padding: 12px 20px 24px;
    overflow: auto;
  }
  .count {
    font-size: 12px;
    color: var(--eden-app-muted);
    padding: 6px 2px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12.5px;
  }
  th {
    text-align: start;
    padding: 8px 10px;
    color: var(--eden-app-muted);
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 1px solid var(--eden-app-line);
    cursor: pointer;
    white-space: nowrap;
    position: sticky;
    top: 0;
    background: var(--eden-app-bg);
  }
  th.active {
    color: var(--eden-app-fg);
  }
  .caret {
    font-size: 8px;
    margin-inline-start: 4px;
  }
  td {
    padding: 8px 10px;
    border-bottom: 1px solid color-mix(in oklab, var(--eden-app-line) 55%, transparent);
    color: var(--eden-app-fg);
    white-space: nowrap;
  }
  tr {
    cursor: pointer;
  }
  tbody tr:hover td {
    background: var(--eden-app-rail-bg);
  }
  .st {
    display: flex;
    align-items: center;
    gap: 7px;
  }
  .mono {
    font-family: var(--font-code);
    font-size: 11.5px;
    color: var(--eden-app-muted);
  }
  .nm {
    font-weight: 600;
  }
  .pub {
    margin-inline-start: 6px;
    font-size: 10px;
  }
  .img {
    max-width: 280px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .pts {
    max-width: 130px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
