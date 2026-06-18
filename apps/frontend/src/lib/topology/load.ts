// Loads the committed cluster snapshots (produced by scripts/introspect-topology.py) and exposes
// them as the topology contract. Today the source is static snapshots of the live clusters; the
// same surface can later be swapped for a live BFF call without touching the canvas.
import type { Topology, ClusterSummary } from './contract';

const modules = import.meta.glob<Topology>('./snapshots/*.json', { eager: true, import: 'default' });

const topologies: Topology[] = Object.values(modules).sort((a, b) => a.clusterName.localeCompare(b.clusterName));

export function listClusters(): ClusterSummary[] {
  return topologies.map((t) => ({
    id: t.clusterId,
    name: t.clusterName,
    generatedAt: t.generatedAt,
    nodeCount: t.nodes.filter((n) => n.kind !== 'namespace').length,
    namespaces: t.nodes.filter((n) => n.kind === 'namespace').length,
  }));
}

export function getTopology(id: string): Topology | undefined {
  return topologies.find((t) => t.clusterId === id);
}
