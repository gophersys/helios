// Loads the committed cluster snapshots (produced by scripts/introspect-topology.py) and exposes
// them as the topology contract + the derived ClusterModel. Today the source is static snapshots of
// the live clusters; the same surface can later be swapped for a live BFF call without touching the
// canvas or any lens (they consume the model, never the loader).
import type { ClusterSummary, Topology } from './contract';
import { deriveCluster, type ClusterModel } from './model';
import { worstOf } from './status';

const modules = import.meta.glob<Topology>('./snapshots/*.json', { eager: true, import: 'default' });

const topologies: Topology[] = Object.values(modules).sort((a, b) =>
  a.clusterName.localeCompare(b.clusterName),
);

const models = new Map<string, ClusterModel>(
  topologies.map((t) => [t.clusterId, deriveCluster(t)]),
);

/** The cluster switcher index — name + a worst-of health dot + namespace count. */
export function listClusters(): ClusterSummary[] {
  return topologies.map((t) => ({
    id: t.clusterId,
    name: t.clusterName,
    generatedAt: t.generatedAt,
    status: worstOf(t.nodes.filter((n) => n.kind !== 'namespace').map((n) => n.status)),
    namespaces: t.nodes.filter((n) => n.kind === 'namespace').length,
  }));
}

/** The derived catalog for one cluster (memoized) — what every lens projects. */
export function getModel(id: string): ClusterModel | undefined {
  return models.get(id);
}
