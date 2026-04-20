# platform

Cluster-level shared services. Each subdirectory is one logical service,
packaged as a Helm release with values overrides per cluster.

| Service                         | Provides                               |
|---------------------------------|----------------------------------------|
| `ingress-tls/`                  | Ingress controller + cert-manager      |
| `secrets-external-operator/`    | External Secrets Operator + BW backend |
| `observability/`                | Loki, Prometheus, Tempo, Grafana       |
| `database-postgresql/`          | Shared Postgres with per-tenant DBs    |
| `messaging/`                    | NATS (leader) + optional Kafka         |

These are NOT consumed by applications directly — applications talk to the
public-facing interfaces (ingress hostnames, Postgres connection strings,
NATS cluster URLs). Platform services are a cluster-install concern.

See each subdirectory's README for status and intended configuration.
