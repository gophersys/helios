<script lang="ts">
  // The shared Detail drawer — details on demand (the leaf). Opens from any lens over the focused
  // node id (clusters.focusId). Shows the full meta, the public route chain, mounted volumes and the
  // 1-hop relationships (blast radius) derived from the edges. Never replaces the canvas; ESC / X /
  // backdrop closes. The "Open in k9s" affordance is honestly gated.
  import type { ClusterModel } from './model';
  import { classOf, readiness } from './model';
  import { clusters } from './clustersState.svelte';
  import StatusChip from './StatusChip.svelte';
  import StatusGlyph from './StatusGlyph.svelte';
  import KindIcon from './KindIcon.svelte';

  let { model }: { model: ClusterModel } = $props();
  const node = $derived(clusters.focusId ? model.byId.get(clusters.focusId) : undefined);

  const ready = $derived(node ? readiness(node) : null);
  const metaRows = $derived(
    node ? Object.entries(node.meta).filter(([k, v]) => v && k !== 'hosts' && k !== 'kind') : [],
  );
  const hosts = $derived(model.endpoints.filter((e) => e.ingress.id === node?.id || e.service?.id === node?.id || e.workload?.id === node?.id));

  // 1-hop neighbours from the edges (excluding the grouping `contains`).
  const links = $derived(
    node
      ? model.topo.edges
          .filter((e) => e.kind !== 'contains' && (e.source === node.id || e.target === node.id))
          .map((e) => {
            const otherId = e.source === node.id ? e.target : e.source;
            const dir = e.source === node.id ? 'out' : 'in';
            return { kind: e.kind, dir, other: model.byId.get(otherId) };
          })
          .filter((l) => l.other)
      : [],
  );

  function onKey(ev: KeyboardEvent): void {
    if (ev.key === 'Escape') clusters.focus(null);
  }

  // "Open in k9s" → a live, read-only k9s TUI in a new tab, served by ttyd on its OWN port (it is a
  // full-page terminal, not a same-origin API — and vite's ws proxy crashes under bun). ttyd appends
  // the ?arg=… values as k9s flags (--context/-n/-c) so the session lands on THIS resource; the k9s
  // resource view is keyed off the authoritative meta.kind. Port overridable via PUBLIC_EDEN_K9S_PORT.
  const K9S_PORT = '7682';
  const K9S_VIEW: Record<string, string> = {
    deploy: 'deploy', deployment: 'deploy', sts: 'statefulset', statefulset: 'statefulset',
    ds: 'daemonset', daemonset: 'daemonset', svc: 'service', service: 'service',
    ing: 'ingress', ingress: 'ingress', pvc: 'pvc',
  };
  function openK9s(): void {
    if (!node) return;
    const args = ['--context', model.topo.clusterId];
    if (node.namespace) args.push('-n', node.namespace);
    args.push('-c', K9S_VIEW[node.meta.kind ?? ''] ?? K9S_VIEW[node.kind] ?? 'pods');
    const qs = args.map((a) => `arg=${encodeURIComponent(a)}`).join('&');
    window.open(`http://${window.location.hostname}:${K9S_PORT}/?${qs}`, '_blank', 'noopener');
  }
</script>

<svelte:window onkeydown={onKey} />

{#if node}
  <button class="scrim" aria-label="close" onclick={() => clusters.focus(null)}></button>
  <aside class="drawer" aria-label="resource detail">
    <button class="x" onclick={() => clusters.focus(null)} aria-label="close">✕</button>

    <header>
      <span class="ic"><KindIcon kind={node.kind} size={22} /></span>
      <div>
        <div class="nm">{node.name}</div>
        <div class="sub">{node.meta.kind ?? classOf(node)}{node.namespace ? ` · ${node.namespace}` : ''}</div>
      </div>
    </header>

    <div class="statusline">
      <StatusChip status={node.status ?? 'unknown'} size="md" />
      {#if ready}<span class="ready">{ready.ready}/{ready.desired} ready</span>{/if}
      {#if model.publicIds.has(node.id)}<span class="exp">🌐 public</span>{/if}
    </div>

    {#if hosts.length}
      <section>
        <h4>Routes</h4>
        {#each hosts as e}
          <div class="chain">
            <StatusGlyph status={e.status} size={11} />
            <span class="mono">{e.host}{#if e.port}:{e.port}{/if}</span>
            <span class="arr">→</span>
            <span>{e.service?.name ?? '—'}</span>
            <span class="arr">→</span>
            <span>{e.workload?.name ?? '—'}</span>
          </div>
        {/each}
      </section>
    {/if}

    {#if metaRows.length}
      <section>
        <h4>Details</h4>
        <dl>
          {#each metaRows as [k, v]}
            <dt>{k}</dt>
            <dd class="mono" title={v}>{v}</dd>
          {/each}
        </dl>
      </section>
    {/if}

    {#if links.length}
      <section>
        <h4>Connections <span class="hint">blast radius</span></h4>
        <ul class="links">
          {#each links as l (l.kind + l.dir + l.other?.id)}
            <li>
              <button class="link" onclick={() => l.other && clusters.focus(l.other.id)}>
                <StatusGlyph status={l.other?.status ?? 'unknown'} size={9} />
                <span class="rel">{l.dir === 'out' ? l.kind : `${l.kind} ←`}</span>
                <span class="other">{l.other?.name}</span>
                <span class="rns">{l.other?.namespace}</span>
              </button>
            </li>
          {/each}
        </ul>
      </section>
    {/if}

    <button class="k9s" title="Opens a live k9s session for this resource (ttyd) — coming next">
      ⎈ Open in k9s
    </button>
  </aside>
{/if}

<style>
  .scrim {
    position: fixed;
    inset: 0;
    background: color-mix(in oklab, var(--eden-app-fg) 14%, transparent);
    border: 0;
    cursor: default;
    z-index: 40;
  }
  .drawer {
    position: fixed;
    top: 0;
    right: 0;
    height: 100vh;
    width: 360px;
    max-width: 92vw;
    overflow: auto;
    z-index: 41;
    background: var(--eden-app-panel-bg);
    border-inline-start: 1px solid var(--eden-app-line);
    box-shadow: -18px 0 50px -30px rgba(0, 0, 0, 0.4);
    padding: 20px 18px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    color: var(--eden-app-fg);
  }
  .x {
    position: absolute;
    top: 14px;
    right: 14px;
    background: none;
    border: 0;
    color: var(--eden-app-muted);
    cursor: pointer;
    font-size: 14px;
  }
  header {
    display: flex;
    gap: 11px;
    align-items: center;
    padding-inline-end: 24px;
  }
  .ic {
    color: var(--eden-app-accent);
  }
  .nm {
    font-weight: 700;
    font-size: 16px;
  }
  .sub {
    color: var(--eden-app-muted);
    font-size: 12px;
    font-family: var(--font-code);
  }
  .statusline {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }
  .ready,
  .exp {
    font-size: 12px;
    color: var(--eden-app-muted);
    font-family: var(--font-code);
  }
  section h4 {
    margin: 0 0 8px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--eden-app-muted);
    font-family: var(--font-text);
    font-weight: 700;
  }
  .hint {
    text-transform: none;
    letter-spacing: 0;
    font-weight: 400;
    opacity: 0.7;
  }
  .chain {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 12px;
    flex-wrap: wrap;
    margin-bottom: 6px;
  }
  .arr {
    color: var(--eden-app-muted);
  }
  dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 5px 14px;
    margin: 0;
  }
  dt {
    color: var(--eden-app-muted);
    font-size: 12px;
  }
  dd {
    margin: 0;
    text-align: end;
    font-size: 12px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .links {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .link {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 6px 8px;
    background: none;
    border: 0;
    border-radius: 7px;
    font: inherit;
    font-size: 12px;
    color: var(--eden-app-fg);
    cursor: pointer;
    text-align: start;
  }
  .link:hover {
    background: var(--eden-app-rail-bg);
  }
  .rel {
    color: var(--eden-app-muted);
    font-family: var(--font-code);
    font-size: 11px;
  }
  .other {
    font-weight: 500;
  }
  .rns {
    margin-inline-start: auto;
    color: var(--eden-app-muted);
    font-size: 11px;
    font-family: var(--font-code);
  }
  .mono {
    font-family: var(--font-code);
  }
  .k9s {
    margin-top: auto;
    padding: 10px;
    background: var(--eden-app-rail-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: 9px;
    color: var(--eden-app-accent);
    font: inherit;
    font-weight: 600;
    font-size: 13px;
    cursor: pointer;
  }
  .k9s:hover {
    border-color: var(--eden-app-accent);
  }
</style>
