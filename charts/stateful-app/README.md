# charts/stateful-app

StatefulSet + headless Service + PVC + optional Ingress. Target:
single-instance (or small-cluster) services that own their storage
directly, for cases where `platform/database-postgresql` is not a fit.

Status: stub.

TODO: implement. Required knobs: storage class per cluster,
volumeClaimTemplates sizing, pod anti-affinity, update strategy.
