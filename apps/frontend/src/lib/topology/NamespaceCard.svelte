<script lang="ts">
  // One namespace as a summary card (semantic-zoom tier 0): worst-of health rollup + fraction, a
  // kind breakdown, exposure/storage badges, ZERO edges. Expands in place to a member list (tier 1).
  import type { NamespaceSummary, TopoNode } from './contract';
  import { classOf } from './model';
  import StatusChip from './StatusChip.svelte';
  import StatusGlyph from './StatusGlyph.svelte';
  import KindIcon from './KindIcon.svelte';

  let {
    ns,
    expanded = false,
    members,
    publicIds,
    onToggle,
    onMember,
    onScope,
  }: {
    ns: NamespaceSummary;
    expanded?: boolean;
    members: TopoNode[]; // already filtered (what to show when expanded)
    publicIds: Set<string>;
    onToggle: () => void;
    onMember: (id: string) => void;
    onScope: () => void;
  } = $props();

  const fraction = $derived(
    ns.rollup === 'ok' ? `${ns.total}` : `${ns.byStatus[ns.rollup] ?? 0}/${ns.total}`,
  );
  const breakdown = $derived(
    (
      [
        ['workload', 'workloads'],
        ['service', 'svc'],
        ['ingress', 'ingress'],
        ['volume', 'vol'],
        ['config', 'config'],
      ] as const
    )
      .filter(([k]) => ns.byClass[k] > 0)
      .map(([k, label]) => `${ns.byClass[k]} ${label}`),
  );
</script>

<div class="card" class:bad={ns.rollup !== 'ok'} class:open={expanded}>
  <button class="head" onclick={onToggle} aria-expanded={expanded}>
    <span class="chev" class:open={expanded}>▸</span>
    <span class="nm">{ns.name}</span>
    <span class="spacer"></span>
    <StatusChip status={ns.rollup} fraction={fraction} />
  </button>

  <div class="meta">
    <span class="bd">{breakdown.join(' · ')}</span>
    <span class="badges">
      {#if ns.hosts.length}
        <span class="badge" title={ns.hosts.join(', ')}>🌐 {ns.hosts.length}</span>
      {/if}
      {#if ns.storage}
        <span class="badge" title="persistent volumes">💾 {ns.storage.count}</span>
      {/if}
    </span>
  </div>

  {#if expanded}
    <ul class="members">
      {#each members as m (m.id)}
        <li>
          <button class="member" onclick={() => onMember(m.id)} title={m.meta.image ?? m.name}>
            <StatusGlyph status={m.status ?? 'unknown'} size={10} />
            <span class="mi"><KindIcon kind={m.kind} size={14} /></span>
            <span class="mn">{m.name}</span>
            <span class="mk">{m.meta.kind ?? classOf(m)}</span>
            {#if publicIds.has(m.id)}<span class="pub" title="reachable from the internet">🌐</span>{/if}
            {#if m.meta.replicas}<span class="rep">{m.meta.replicas}</span>{/if}
          </button>
        </li>
      {:else}
        <li class="none">no matching resources</li>
      {/each}
    </ul>
    <button class="ingraph" onclick={onScope}>Open in Service Map →</button>
  {/if}
</div>

<style>
  .card {
    display: flex;
    flex-direction: column;
    background: var(--eden-app-panel-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: 12px;
    overflow: hidden;
  }
  .card.bad {
    border-color: color-mix(in oklab, var(--color-error) 45%, var(--eden-app-line));
  }
  .head {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 14px;
    background: none;
    border: 0;
    font: inherit;
    color: var(--eden-app-fg);
    cursor: pointer;
    text-align: start;
  }
  .chev {
    color: var(--eden-app-muted);
    transition: transform 120ms ease;
    font-size: var(--font-size-caption);
  }
  .chev.open {
    transform: rotate(90deg);
  }
  .nm {
    font-weight: 600;
    font-size: var(--font-size-label);
  }
  .spacer {
    flex: 1;
  }
  .meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 0 14px 12px 34px;
  }
  .bd {
    font-size: var(--font-size-caption);
    color: var(--eden-app-muted);
    font-family: var(--font-code);
  }
  .badges {
    display: flex;
    gap: 6px;
  }
  .badge {
    font-size: var(--font-size-caption);
    color: var(--eden-app-muted);
    border: 1px solid var(--eden-app-line);
    border-radius: 999px;
    padding: 1px 7px;
  }
  .members {
    list-style: none;
    margin: 0;
    padding: 4px 8px 8px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    border-top: 1px solid var(--eden-app-line);
    max-height: 260px;
    overflow: auto;
  }
  .member {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 6px 8px;
    background: none;
    border: 0;
    border-radius: 7px;
    font: inherit;
    font-size: var(--font-size-label);
    color: var(--eden-app-fg);
    cursor: pointer;
    text-align: start;
  }
  .member:hover {
    background: var(--eden-app-rail-bg);
  }
  .mi {
    color: var(--eden-app-muted);
    display: grid;
    place-items: center;
    flex: none;
  }
  .mn {
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .mk {
    color: var(--eden-app-muted);
    font-family: var(--font-code);
    font-size: var(--font-size-caption);
  }
  .pub {
    font-size: var(--font-size-caption);
  }
  .rep {
    margin-inline-start: auto;
    font-family: var(--font-code);
    font-size: var(--font-size-caption);
    color: var(--eden-app-muted);
  }
  .none {
    list-style: none;
    color: var(--eden-app-muted);
    font-size: var(--font-size-caption);
    padding: 6px 8px;
  }
  .ingraph {
    margin: 0 8px 8px;
    padding: 7px;
    background: var(--eden-app-rail-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: 8px;
    color: var(--eden-app-accent);
    font: inherit;
    font-size: var(--font-size-caption);
    font-weight: 600;
    cursor: pointer;
  }
  .ingraph:hover {
    border-color: var(--eden-app-accent);
  }
</style>
