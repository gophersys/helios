# Codebase-insight visualization: metrics, behavioral/temporal mining, and the dynamic-dashboard widget taxonomy

> **Class:** research note (docs/README.md §1) · **Research date:** 2026-06-17 · **Status:** DRAFT
> for human review. Point-in-time findings; never canonical — promoted into specs with a citation,
> not edited here. **Promotes into:** the proposed `codeinsight` analyzer library + payload
> contract (`docs/architecture/contracts/codeinsight.md`) and the `@eden/visualization` widget
> asset set — the substrate for the "point Eden at a codebase → generate the insight dashboards"
> feature (Eden self-feeding).
>
> **Provenance.** Two adversarially-verified deep-research passes (fan-out web search → source
> fetch → 2-of-3-vote refutation → cited synthesis). Round 1 (15 findings, 0 refuted, 28 sources)
> covered the metrics catalog, behavioral/temporal mining, visualization theory, and the widget
> taxonomy. Round 2 (3 findings, 3-0, complete) closed the gaps round 1 left: DORA operationalization,
> Martin I/Ca/Ce (A/D theory-only), cognitive-complexity (15/30) + Halstead formulas, and concrete
> Go+TypeScript tooling output shapes — promoted below as `§R2` (§5a) and into the metric table.
> Four narrow items remain open (§7): the latest Google/DORA numeric bands, a Martin A/D tool, an
> authoritative Halstead source, and the bus-factor algorithm default (OD-CI-3).

**Domain:** how to compute, threshold, and *visualize* the load-bearing properties of a codebase —
for two distinct lenses: (1) **active-development triage** (find the risky/complex/hotspot code worth
a review or refactor *right now*) and (2) **long-term health monitoring** (trends over time).
**Audience:** the team building the `codeinsight` analyzer and the `@eden/visualization` lib.

**Epistemic legend:**
✅ primary-sourced, formula-verified · 🔶 sound practitioner-canon / single-study / strong convention
with weaker independent proof · ⚠️ contested or vendor-self-reported — flagged with what the evidence
actually supports · 🧩 synthesis/inference across verified facts (not a single cited authority).

---

## 1. The one-paragraph synthesis

Static metrics are table stakes; the **predictive signal lives in the temporal/git-history
dimension**. A *hotspot* — complicated code that changes frequently (`change_frequency ×
complexity`) — out-predicts any single static property for defects, and effort is brutally
concentrated: **~25% of development work in ~1% of files**, with a bus factor of 2–3 even on
50–60-person teams. So the analyzer's spine is git-history mining (churn, logical coupling,
ownership), not a SonarQube clone. The recurring dashboard reduces to **eight chart primitives**
that cover every screen CodeScene, SonarQube, and Grafana-style tools render — which is exactly the
reusable `@eden/visualization` asset set.

---

## 2. Metrics catalog — formula · threshold · SDLC attention point

For each metric: how it is calculated, the trouble threshold, and *when* in the lifecycle it earns
attention (pre-commit / PR review / release gate / continuous monitoring).

| Metric | Calculation | Trouble threshold | Attention point | Tag |
|---|---|---|---|---|
| **Cyclomatic complexity** | `1 + #conditional branches` (`if`/`for`/`while`/`case`/`&&`/`‖`/`?`/`catch`); per-function min 1; file/repo = sum of function scores. Graph form `C = E − N + 2P`. | >10 review · >15–20 high risk (convention, *not* in the primary source) | pre-commit / PR | ✅ |
| **Cognitive complexity** | SonarSource: structural + **nesting** increments (penalizes deeply nested flow, ignores `switch` fall-through shorthand) — readability proxy vs cyclomatic's path-count | **15** (SonarJS default) · **30** (gocognit default) | pre-commit / PR | ✅ (R2) |
| **Maintainability Index** | VS: `MAX(0, (171 − 5.2·ln(HalsteadVolume) − 0.23·CC − 16.2·ln(LOC)) · 100/171)`. Original (Oman & Hagemeister 1992) un-rescaled: `171 − 5.2·ln(V) − 0.23·CC − 16.2·ln(LOC)`. | VS bands: **0–9 red · 10–19 yellow · 20–100 green** | release gate / monitoring | ✅ (⚠️ validity critiqued — van Deursen, "Think Twice Before Using the MI"; dispute is usefulness, not the formula) |
| **Coverage** | overall `(CT+LC)/(B+EL)` · line `LC/EL` · branch `(CT+CF)/(2B)` (CT/CF = conditions true/false ≥once, B = total conditions, LC = covered lines, EL = executable lines) | gate on **new code**, not flat global % (clean-as-you-code) | PR / release gate | ✅ |
| **Technical-debt ratio (SQALE)** | `debt / (cost_per_line × LOC)`, default **30 min/line**. Worked ex: `122,563 / (30 × 63,987) = 6.4%` | maps to rating ↓ | continuous monitoring | ✅ |
| **Maintainability rating (SQALE)** | debt-ratio → letter | **A ≤5% · B <10% · C <20% · D <50% · E ≥50%** | dashboard badge / gate | ✅ |
| **Hotspot** | `change_frequency × complexity` (the behavioral lens) | rank-ordered; top ~1–5% of files ≈ **23–45% of defects** | **active-dev triage** | ✅ |
| **Logical / temporal coupling** | files co-changing in the same commit; `degree = shared_revs / avg_revs` (0–100) | filter **≥10 revisions** to cut accidental co-change | architecture review | ✅ |
| **Code churn** | lines added+removed per file over a window; prefer **relative** churn (÷ LOC) over absolute | high churn → more post-release defects | continuous monitoring | ✅ |
| **Bus factor / ownership** | author→code map from commit authorship | usually **2–3** even on big teams; flags single points of failure | team-health monitoring | 🔶 (⚠️ method-sensitive; precise 2-3/50-60 figure is an under-specified vendor study) |
| **Martin coupling** (Ca, Ce, I, A, D) | `I = Ce/(Ca+Ce)` (Ca inbound, Ce outbound, 0–1) · `A = abstract/total` · `D = |A + I − 1|` | `D → 0` = on main sequence (good); `D → 1` bad. low-A/low-I = **zone of pain**, high-A/high-I = **zone of uselessness** | architecture review | ✅ I/Ca/Ce (R2) · 🔶 A/D (theory; no tool — compute natively) |
| **Halstead suite** (n, N, V, D, E) | `V = N·log₂(n)` · `D = (n1/2)·(N2/n2)` · `E = D·V` · time `T = E/18` · bugs `B = V/3000` | no hard threshold (a proxy) | release gate / monitoring | 🔶 (R2, low conf — formulas not independently re-verified) |
| **DORA Four Keys** | GitLab op.: deploy-freq = **mean** successful prod deploys/day · lead-time = **median** sec MR-merge→prod · change-fail = incidents/deploys · MTTR = **median** sec incident-open. Needs CI/CD **+ incident** data beyond git. | Elite/High/Med/Low bands **still unverified** (open-Q) | continuous monitoring / post-incident | ✅ formulas (R2) · ⚠️ bands + needs non-git data |

---

## 3. Behavioral / temporal mining is the foundation (lens C)

✅ **Behavioral code analysis** — mining the version-control *temporal* dimension rather than a
single static snapshot — was defined by Adam Tornhill (*Your Code as a Crime Scene*, 2014/2024;
*Software Design X-Rays*, 2018) and productized in **CodeScene**, which states verbatim that "static
analysis works on a snapshot … while CodeScene considers the temporal dimension and evolution of the
whole system." Tornhill: "static analysis was never ever intended to help you prioritize technical
debt." *Nuance:* CodeScene combines static (its Code Health AST metric, 25+ smells) **with** temporal
— temporal is what *defines* the approach, not the whole of it.

✅ **Hotspots out-predict static metrics.** A hotspot "has more predictive value than any properties
of the code itself" (Tornhill, SE-Radio 554). Corroborated by independent peer-reviewed work that
process/change metrics generally beat code metrics for defect prediction — Rahman & Devanbu (ICSE
2013), Hassan (ICSE 2009), Nagappan & Ball (Microsoft). CodeScene data: prioritized hotspots ≈ 1.2%
of code yet ≈ 45% of bugs. *Qualifier:* "any" is slightly absolutist — best modern models **combine**
code + process metrics.

✅ **Effort is heavy-tailed.** ~1–2% of a codebase accounts for the majority of development work;
commonly **~25% of work in ~1% of the code**. *Caveat:* the strict "power law" label is statistically
contested (lognormal often fits better — Clauset/Shalizi/Newman); cite as **heavy-tailed / Pareto-like
concentration**, not a strict power law. The directional concentration is sound and is the entire
rationale for hotspot-first prioritization over a flat static backlog.

✅ **Logical coupling exposes hidden dependencies** static analysis cannot see ("a change to one …
leads to a predictable change in the coupled module"). It is **bidirectional** (same-commit co-change
is symmetric) so it cannot indicate dependency *direction*. *Nuance:* association-rule confidence
(Zimmermann et al., TSE 2005) is asymmetric and **can** extract partial directional signal.

✅ **Churn predicts post-release defects** (Nagappan & Ball, ICSE 2005, Windows Server 2003). *Qualifier:*
**relative** churn (normalized by size) predicts better than absolute.

🔶 **Bus factor is low even on large teams** (usually 2–3). Corroborated by Avelino et al. (SANER/ICPC
2016: 46% of 133 popular GitHub projects have truck-factor 1, 28% have 2). The qualitative claim
survives across definitions; the precise vendor figure does not have public methodology.

### Extraction tooling (commit-hash level)
- ✅ **code-maat** — Tornhill's Clojure CLI; mines git/hg/svn/p4/tfs logs → logical coupling
  (`entity, coupled, degree, average-revs`; `degree` = shared revs / avg revs, 0–100), churn, author
  counts, hotspots. "Evolved into CodeScene."
- ✅ **PyDriller** — Python framework (FSE 2018, Spadini et al.). `Commit{hash, author(name+email),
  committer, authored/committed dates, message, parents}`; `ModifiedFile{change_type, diff,
  added_lines, deleted_lines, complexity, nloc, source_code}`. Built-in **SZZ** API
  (`get_commits_last_modified_lines`) for bug-inducing-commit detection (19 LOC vs 66 in GitPython).
  *Nuance:* AG-SZZ-based — known false positives on tangled commits.

> **Eden implication:** code-maat (JVM) and PyDriller (Python) are *reference implementations*, not
> dependencies. Their algorithms are git-log walks; Eden computes them **natively in Go** on
> `libs/go/gitrepository` (which owns git but does **not yet** expose a history/log-walk surface —
> see the contract). No Clojure/Python in the runtime.

---

## 4. Visualization theory & encoding (lens B)

🔶 **Caserta & Zendra taxonomy** (IEEE TVCG 17(7):913–933, 2011, "Visualization of the Static Aspects
of Software: A Survey") — four categories: **code-line-centered · class-centered · architecture ·
software-evolution**, each organized by whether it depicts **structure / relationships / metrics**.
This is the matching function: pick the encoding by (category × focus). *Caveat:* the PDF returned
403 on fetch; the four-category structure is confirmed via the INRIA/HAL landing page + an
independent review, but exact in-paper wording is unverified.

**Encoding → metric map:**
- **Hotspot map** (churn × complexity scatter) — *the* signature behavioral view; size/color encode
  effort and risk.
- **Enclosure hierarchies** — treemap · sunburst/icicle · circle-packing · "code city"; size + color
  encode LOC · complexity · churn · ownership.
- **Dependency graph + Design Structure Matrix (DSM)** — coupling and cycles; DSM scales past the
  ~50-node node-link legibility wall.
- **Heat map** — file/dir × metric grids.
- **Knowledge / ownership map** — author-colored file hierarchy → bus-factor single points of failure.
- **Letter-grade badges + KPI gauge tiles** — A–E ratings, single-value.
- **Trend sparklines** — churn, debt, coverage, DORA over time (the monitoring lens).

What makes these *insightful vs. misleading*: encode magnitude with a perceptually-ordered scale
(area/position beat hue for quantity), keep one metric per visual channel, and never imply a
direction that the data (e.g. symmetric co-change coupling) cannot support.

---

## 5. The reusable widget primitive set (lens D) 🧩

The recurring chart primitives across CodeScene, SonarQube, and Grafana-style observability — the
`@eden/visualization` asset set, each themeable and backend-payload-driven:

1. **Enclosure/hierarchy** — treemap · sunburst/icicle · circle-pack/code-city
2. **Dependency graph + DSM**
3. **Churn × complexity scatter (hotspot map)** — the behavioral signature
4. **Heat map**
5. **Ownership/knowledge map** (author-colored hierarchy)
6. **Rating badge** (A–E) + **KPI gauge / single-value tile**
7. **Trend line / sparkline**
8. **(supporting) data table** with inline sort/threshold coloring — the drill-down under every view

Eight primitives. A backend payload that tags each block with its primitive type lets the frontend
render *any* repo's dashboard with zero per-repo code — the basis of the "point-it-at-a-codebase"
feature.

---

## 5a. Concrete Go + TypeScript tooling (§R2 — machine-readable output)

The per-language metric providers `codeinsight` dispatches to. Go cyclomatic/cognitive are cheap to
compute **natively from the AST** (resolves OD-CI-4 for the Go provider — no subprocess); the tools
below are the reference algorithms + the path for non-Go languages.

| Metric | Go | TypeScript / Svelte | Output |
|---|---|---|---|
| Cyclomatic | gocyclo / `cyclop` (in golangci-lint) | SonarJS / ESLint `complexity` | golangci-lint **JSON + SARIF 2.1.0**; ESLint JSON |
| Cognitive | gocognit (default **30**) | SonarJS (default **15**) | golangci-lint JSON/SARIF |
| Coverage | `go test -coverprofile` (→ cobertura via gocover-cobertura) | c8/istanbul JSON | coverprofile / cobertura XML / JSON |
| Duplication | (jscpd is polyglot) | **jscpd `--reporters json`** (Svelte/Vue SFC: `.vue` matches `.ts`) | JSON |
| Dependency cycles + **Martin I/Ca/Ce** | (native AST) | **dependency-cruiser `-T json`** (`metrics` per module+folder) | JSON (`dependencies` + `summary`) |
| Dead code | (native) | **knip `--reporter json`** (issues array per file) | JSON |
| Vulnerabilities | **govulncheck `-json`** / `-format sarif` (streaming) | npm-audit / osv | JSON / SARIF |

⚠️ `dependency-cruiser` computes **I/Ca/Ce** but NOT abstractness `A` or distance `D` — no verified
tool emits A/D, so the main-sequence view requires native computation. `ts-complex` and the exact
Halstead-emitting tools were not re-verified.

## 6. Caveats & coverage gaps (honest scope)

- Metric **formulas/thresholds** from SonarQube and Visual Studio are **primary vendor docs** —
  strong. Thresholds are **tool-specific, not universal** (VS MI bands ≠ other tools' scales).
- Behavioral-analysis claims lean heavily on **Tornhill / CodeScene** primary sources — credible
  domain authority but partly self-serving; mitigated by independent peer-reviewed corroboration
  (Nagappan & Ball, Rahman & Devanbu, Hassan, Avelino).
- Time-sensitivity: vendor formulas can change between major releases; PyDriller's API names already
  shifted (`Modification`→`ModifiedFile`).
- The widget taxonomy (§5) is a **synthesis/inference** across the three tool families, not one cited
  authority — hence 🧩.
- **Round-1 gaps closed by round 2 (`§R2`):** cognitive complexity (15/30 thresholds), Halstead
  formulas (🔶 low conf), Martin I/Ca/Ce (✅; A/D theory-only — no tool), DORA operationalization
  (✅ GitLab formulas), and the Go/TS tooling output shapes (§5a). **Still open after round 2:** the
  latest Google/DORA numeric **bands**, a tool for Martin **A/D**, an authoritative Halstead source,
  and the deployment-vs-incident change-fail definition (store both).
- **DORA needs non-git data.** Deploy frequency and change-failure rate require CI/CD pipeline +
  incident records; only lead-time is approximable from git alone (merge→tag/deploy). For an arbitrary
  repo with no pipeline/incident feed, DORA is **partial** — the `Report.Summary.Dora` field stays
  `omitempty` and is populated only when a deploy/incident source is wired.

## 7. Open questions (remaining after round 2)

1. The latest Google/DORA State-of-DevOps **numeric** Elite/High/Medium/Low bands (round 2 verified
   the formulas/operationalization but not current threshold numbers).
2. Any tool that emits Martin **abstractness A** and **distance D** (none found — Eden computes
   natively from the AST per language).
3. An authoritative primary source + emitting tool for the full **Halstead** suite (🔶 low confidence).
4. **Bus-factor algorithm** default (OD-CI-3): >50%-line-ownership vs per-file primary-dev vs
   Minimum-Critical-Set — round 2 did not resolve; default stays >50%-line-ownership.

## 8. Sources (round 1)

Primary: SonarQube metrics-definition docs · Microsoft Learn (MI range/meaning) · adamtornhill.com ·
CodeScene enterprise docs 3.0.2 · code-maat README + `logical_coupling.clj` · PyDriller (ACM FSE 2018,
10.1145/3236024.3264598) · SE-Radio #554 · Tech Lead Journal #241 · Caserta & Zendra TVCG 2011 (INRIA
HAL) · Wettel ICSE (code cities) · DORA.dev · GitLab DORA docs · dependency-cruiser · golangci-lint ·
jscpd · madge · knip. Independent corroboration: Nagappan & Ball (ICSE 2005), Rahman & Devanbu (ICSE
2013), Hassan (ICSE 2009), Avelino et al. (SANER/ICPC 2016), Zimmermann et al. (TSE 2005). Full URL
list with per-claim vote counts retained in the workflow journal.
