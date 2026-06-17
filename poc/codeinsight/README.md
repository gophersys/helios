# poc/codeinsight — codebase-insight analyzer (proof of concept)

> **Class:** PoC / donor material (CLAUDE.md: `poc/` is reference; code enters `main` only
> through the ADR-0020 gates). **Validates:** the `codeinsight` payload contract
> (`docs/architecture/contracts/codeinsight.md`) and the verified metric formulas
> (`docs/research/06-codebase-insight-visualization.md`) against the real Eden repository,
> ahead of the gated `libs/go/codeinsight` build.

The producer side of the **"point Eden at a codebase → generate the insight dashboards"**
feature. It walks an arbitrary git repository and emits one self-describing `Report` — the
contract's exact schema — so the frontend (`@eden/visualization`) renders any repo's
dashboard from the payload alone, with zero per-repo code. This is Eden self-feeding:
Eden computing insights about its own code.

## Run it

```sh
# Human-readable digest (top hotspots, couplings, rating):
GOWORK=off go run ./cmd/codeinsight --summary /path/to/repo

# Full Report JSON (the contract payload the dashboard consumes):
GOWORK=off go run ./cmd/codeinsight /path/to/repo > report.json

# Self-feeding: analyze Eden's own Go libraries:
GOWORK=off go run ./cmd/codeinsight --summary /Users/mateo/helios/libs
```

Flags: `--since "6 months ago"` / `--until` (window), `--coupling-min-shared N`
(co-change floor; research recommends ≥10 on mature repos, defaults to 3 for young history),
`--max-entities` / `--max-couplings` (cap by rank), `--identifier`.

## What it computes (the verified spine)

| Metric | Source | How |
|---|---|---|
| Churn (absolute + relative) | `git log --numstat` | added+deleted lines per file, ÷ LOC for relative |
| Change frequency | git history | commits touching each file in the window |
| Cyclomatic complexity | native `go/ast` | `1 + branches`, summed per function (OD-CI-4 Go provider, no subprocess) |
| Cognitive complexity | native `go/ast` | nesting-aware increments (SonarSource approximation) |
| Maintainability index | `go/scanner` Halstead volume + CC + LOC | Visual Studio rescaled formula, 0–100 |
| **Hotspot score** | derived | `changeFrequency × complexity`, normalized — the triage lens |
| Logical coupling | git co-change | `degree = shared / avg revisions × 100` (code-maat definition) |
| Ownership / bus factor | commit authorship | fewest authors past 50% (OD-CI-3 default) |
| Churn trend | git history | monthly buckets, each commit-hash stamped |

Each metric maps to a `View` in the payload's render-plan (the 8 `@eden/visualization`
primitives: hotspot-map, enclosure, dependency-matrix, ownership-map, rating-badge, trend,
data-table).

## Self-feeding result (Eden `libs/` @ 2333b4f, 49 commits)

717 files / 40.5k LOC. Top hotspot: `workspaceprovider/workspaceprovidertest/cases.go`
(cyclomatic 216, 5 changes). Strongest couplings are test↔implementation pairs (e.g.
`secrets_test.go ↔ testing/runner.go`). Repository bus factor: 1 (solo repo — correct).

## Honest limitations (findings that shape the gated library)

1. **File-level cyclomatic *summation* saturates the maintainability index.** A 1192-line
   file with summed CC 216 drives MI to 0 → everything rates **E**, so the rating does not
   discriminate at file granularity. **The gated lib must compute MI per function/method and
   aggregate** (max or distribution), not sum-then-MI. (Research §2 F2 already flags MI's
   contested validity.)
2. **Young-history coupling saturates at 100%** because `shared == averageRevisions` when two
   files have only ever changed together. The `≥10` revision floor (research §3) needs a
   mature history to be meaningful; the default floor of 3 is a young-repo concession.
3. **Go-only static metrics.** Non-Go files contribute churn/coupling/ownership but no
   complexity (the TS/Svelte `MetricProvider` — dependency-cruiser/jscpd/knip — is future work
   per contract §4).
4. **Ownership ≈ commit authorship**, not line-level `git blame` attribution; the real bus
   factor (OD-CI-3) should weigh surviving lines, not commit counts.
5. **History via `os/exec git`**, not the `gitrepository` library — which has no history-walk
   surface yet (OD-CI-1). Promotion replaces this with `gitrepository`'s read surface.

## Promotion path → `libs/go/codeinsight`

This PoC proves the contract and de-risks the design. The gated build (ADR-0020, TDD-order,
8-dimension taxonomy on a real seeded-history fixture):
1. `gitrepository` grows a read-only history-walk surface (contract §2 / OD-CI-1).
2. `codeinsight` reimplements this logic behind `New(configuration, dependencies)` with the
   `MetricProvider` port, per-function MI aggregation (limitation 1), and `codeinsighttest`
   fakes + conformance.
3. An `edenhttp` endpoint serves the `Report`; `@eden/visualization` renders the `Views`.
