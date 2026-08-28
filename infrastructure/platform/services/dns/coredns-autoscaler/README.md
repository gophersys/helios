# coredns-autoscaler

Purpose: k3s ships CoreDNS at 1 replica and re-applies that manifest on every
server start, so a hand edit does not hold. One DNS pod serves the whole
cluster, and a build wave plus image pulls on its node produced a UDP read
timeout that failed a 40-minute CI build (.devcontainer run 32062015200,
2026-08-17; the pods' resolver posture was fixed the same day in #187 — this
component fixes the CAPACITY half, ledger #114).

Default implementation: cluster-proportional-autoscaler (registry.k8s.io,
pinned by digest) in linear mode. It rewrites kube-system/coredns's replica
count continuously, which is exactly why it survives the k3s re-apply: the
re-apply sets 1, the autoscaler sets it back within its poll interval.

Sizing: nodesPerReplica 4, min 2, max 4 — 8 nodes today = 2 replicas, and a
node added or drained moves the count without a human. The floor of 2 is the
point: DNS survives the loss of the one node that used to hold it all.

Dependencies: none. Contracts: none (kube-system is upstream's).
