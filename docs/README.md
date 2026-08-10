# docs

Documentation index for `infrastructure/`.

| Document                  | Purpose                                                 |
|---------------------------|---------------------------------------------------------|
| `architecture.md`         | How machines, clusters, platform and charts fit together |
| `getting-started.md`      | First-time operator setup                               |
| `contracts.md`            | What an application monorepo can rely on from infrastructure |
| `secrets-guide.md`        | The Bitwarden pattern of temporary secrets on tmpfs, end to end |
| `troubleshooting.md`      | Common problems and the first diagnostics to run        |
| `debt-register.md`        | Undocumented and imperative state, plus the engineering agreement |
| `runtime-secrets.md`      | Imperative k8s Secrets and how to recreate them from Vaultwarden |
| `cluster-topology.md`     | What runs in each namespace and why (live reference)    |
| `cloud-cluster.md`        | The OCI cluster that hosts Vaultwarden — the root of trust |
| `machine-inventory.md`    | Every machine, how to reach it, and whether it is declared |
| `where-things-live.md`    | The one rule for the choice between cloud and homelab, and why |
| `ci-runners.md`           | ARC self-hosted runners: how to onboard a repo, and the public-repo policy |
| `ci-substrate.md`         | The pool/image interface: pools carry physical capability, images carry software |
| `testing-standard.md`     | The standard `go test` invocation, the measured cost of each flag, and the trigger table |
| `migration-homelab-to-idp.md` | Historical: the move from homelab to IDP, and the 9 decisions |
| `audit-2026-07.md`        | Point-in-time cluster audit and backlog (2026-07)       |
| `runbooks/`               | Operational runbooks (for example the staged Longhorn upgrade) |

Machine facts are declared in `contracts/access.yaml`, and
`bash ctl.sh verify-access` asserts them. Secrets live only in Vaultwarden. The
contract names the item, never the value.
