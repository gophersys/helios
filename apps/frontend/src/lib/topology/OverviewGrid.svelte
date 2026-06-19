<script lang="ts">
  // The default lens — the cluster as a ranked grid of namespace cards (worst-first). The overview
  // is NAMESPACES, not pods (Shneiderman A1): ~8 cards, zero edges. Unhealthy namespaces (or any
  // matched by an active filter) auto-expand so the problem is visible without a click.
  import type { ClusterModel } from './model';
  import type { TopoNode } from './contract';
  import { clusters } from './clustersState.svelte';
  import NamespaceCard from './NamespaceCard.svelte';

  let { model }: { model: ClusterModel } = $props();

  // local expand state, keyed by namespace name; a value here overrides the auto rule.
  let manual = $state<Record<string, boolean>>({});

  const filtering = $derived(clusters.statuses.size > 0 || clusters.query.trim().length > 0);

  // which namespaces to show: namespace scope filter + (status/query) "has a matching member"
  const shown = $derived(
    model.namespaces.filter((ns) => {
      if (clusters.namespaces.size && !clusters.namespaces.has(ns.name)) return false;
      if (!filtering) return true;
      return ns.members.some((m) => clusters.matches(m)) || ns.name.toLowerCase().includes(clusters.query.trim().toLowerCase());
    }),
  );

  function membersFor(nsName: string): TopoNode[] {
    const ns = model.namespaces.find((n) => n.name === nsName);
    if (!ns) return [];
    return filtering ? ns.members.filter((m) => clusters.matches(m)) : ns.members;
  }

  function isExpanded(nsName: string, rollup: string): boolean {
    if (nsName in manual) return manual[nsName];
    return rollup !== 'ok' || filtering; // auto-expand problems + active filters
  }
</script>

<div class="grid">
  {#each shown as ns (ns.id)}
    <NamespaceCard
      {ns}
      expanded={isExpanded(ns.name, ns.rollup)}
      members={membersFor(ns.name)}
      publicIds={model.publicIds}
      onToggle={() => (manual = { ...manual, [ns.name]: !isExpanded(ns.name, ns.rollup) })}
      onMember={(id) => clusters.focus(id)}
      onScope={() => clusters.scopeToMap(ns.name)}
    />
  {:else}
    <p class="empty">No namespaces match the current filters.</p>
  {/each}
</div>

<style>
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 14px;
    align-content: start;
    padding: 18px 20px;
  }
  .empty {
    grid-column: 1 / -1;
    color: var(--eden-app-muted);
    padding: 24px;
  }
</style>
