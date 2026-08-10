# docs

Documentation index for `infrastructure/`.

| Document                  | Purpose                                                 |
|---------------------------|---------------------------------------------------------|
| `architecture.md`         | How machines, clusters, platform, charts fit together   |
| `getting-started.md`      | First-time operator setup                               |
| `contracts.md`            | What an application monorepo can rely on from infra     |
| `secrets-guide.md`        | Bitwarden ephemeral-on-tmpfs pattern, end-to-end        |
| `troubleshooting.md`      | Common issues and first-stop diagnostics                |
| `debt-register.md`        | Undocumented/imperative state + the engineering agreement |
| `runtime-secrets.md`      | Imperative k8s Secrets + their Vaultwarden recreation   |
| `cluster-topology.md`     | What runs in each namespace and why (live reference) |
| `cloud-cluster.md`        | The OCI cluster that hosts Vaultwarden — the root of trust |
| `machine-inventory.md`    | Every machine, how to reach it, and whether it is declared |
| `where-things-live.md`    | The one rule for choosing cloud vs homelab, and why |

Machine facts are declared in `contracts/access.yaml` and asserted by
`bash ctl.sh verify-access`. Secrets live only in Vaultwarden; the contract
names the item, never the value.
| `ci-runners.md`           | ARC self-hosted runners: onboarding a repo, public-repo policy |
| `migration-homelab-to-idp.md` | Historical: the homelab→IDP relocation + 9 decisions |
| `audit-2026-07.md`        | Point-in-time cluster audit + backlog (2026-07)         |
| `runbooks/`               | Operational runbooks (e.g. Longhorn staged upgrade)     |
