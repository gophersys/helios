# knowledge — POC: does a curated knowledge library make an agent write better Go?

An empirical harness that tests whether (and **how**) a knowledge base of Go
rules changes what a coding agent produces. Agent under test: **DeepSeek V4
Flash** driven headlessly through the **omp** (Oh My Pi) harness. Everything
else — rules, tasks, oracles, scoring — is deterministic Go.

## The theses under test

| # | Thesis | Where verified |
|---|---|---|
| H1 | **Post-cutoff rules have massive prior-delta**: the bare model violates Go 1.24–1.26 idioms (`errors.AsType`, `slog.NewMultiHandler`, `B.Loop`, `WaitGroup.Go`) at high rates because it cannot know them. | `results/report.md` hypothesis table, `post-cutoff` rows |
| H2 | **Prior-known idioms have low prior-delta**: rules the model already follows (ctx-first, small interfaces) add little — the *prior-delta filter* should cut them from guides. | hypothesis table, `idiom` rows |
| H3 | **Knowledge arms reduce violations vs baseline**, most strongly on post-cutoff rules. | rule × arm table |
| H4 | **Checker-only feedback works without prose** — knowledge delivered purely as deterministic checker findings (with fix hints) closes violations, at the cost of extra iterations. | `checker` arm column + tokens/turns |
| H5 | **Hybrid (compact core + checkers) is the best compliance-per-token.** | arms table |

## Anti-slop invariants (enforced at load time, `internal/rule`)

1. a rule without an **oracle** is an opinion → rejected;
2. an opinion without a **citation** (provenance) is slop → rejected;
3. no **falsifiability** (good + bad example) → rejected;
4. no documented **exception** → unconditional platitude → rejected;
5. every rule carries a **pre-registered hypothesis** (`hypothesis_baseline_violation`) that the experiment confirms or refutes — the knowledge base is itself under test.

## Layout

```
rules/        the rule DB: 10 rules — 2 architecture, 4 idiom, 4 post-cutoff (Go 1.24–1.26)
tasks/        6 temptation tasks; each pins an exact contract and tempts specific rules
  <id>/workspace/    agent-facing scaffold (spec.md + go.mod)
  <id>/_verify/      held-out clean-room tests (agent never sees them)
  <id>/_reference/   gold implementation (validates the verify suite; rule-clean by construction)
arms/         rendered knowledge artifacts (pure function of rules/)
internal/check    the C1 oracles: 10 deterministic AST+types checkers
internal/runner   matrix executor (omp -p, isolated workspaces, full provenance)
internal/score    clean-room grading (held-out tests + oracles)
internal/report   aggregate.json + report.md (byte-deterministic)
cmd/rulecheck     standalone checker binary (used by check.sh in checker arms)
cmd/harness       render | selftest | run | score | report
results/      run artifacts: per-run workspace, session transcript, run.json, score.json
```

## The four arms

| arm | knowledge delivery |
|---|---|
| `baseline` | none — spec only (the control) |
| `monolithic` | full GUIDE.md (~3k tokens of prose rules) appended to the system prompt |
| `checker` | **no prose** — `check.sh` in the workspace (build+vet+rulecheck with fix hints) + iterate-until-green instruction |
| `hybrid` | compact CORE.md (~800 tokens: one-liners + post-cutoff API snippets) + `check.sh` |

## Determinism & replicability

- **Pinned**: model id, thinking level, omp version, go version — all recorded per run in `run.json` together with sha256 of the exact prompt and system-prompt artifact.
- **Isolated**: `--no-extensions --no-skills --no-rules --no-lsp --no-title`, fresh workspace and session dir per run; no ambient omp config can leak in.
- **Budgeted**: hard wall-clock timeout per run (process-group kill); token budget flagged in `run.json`; full token/cost accounting parsed from the session transcript.
- **Idempotent**: a cell with `run.json` is never re-run; `score` and `report` are pure functions of the artifacts (re-running them is byte-identical).
- **Hermetic scoring**: `GOPROXY=off`, `-count=1`, held-out tests injected only into the clean-room copy; oracles exclude `zz_verify*` files.
- LLM sampling itself is **not** deterministic (no seed control through the OpenAI-compat surface); the protocol compensates with N seeds per cell and reports mean ± sd. This is recorded as a known limitation, not hidden.

## Clean-room scoring (the information barrier)

The verifier never sees the arm, the prompt, or the transcript — only the
produced module. Functional truth = held-out `TestVerify*` suite; rule truth =
the 10 oracles. The agent's own tests run nowhere near the score (its test
files must merely compile). This is the helios `evidence` model: the gate
reads the envelope, never the implementer's claims.

## Reproduce

```bash
go build -o bin/rulecheck ./cmd/rulecheck
go build -o bin/harness  ./cmd/harness
./bin/harness selftest        # verify suites pass on references; references rule-clean
./bin/harness run -seeds 3 -parallel 4    # needs omp + OpenRouter auth
./bin/harness score
./bin/harness report          # → results/report.md
go test ./...                 # oracle unit tests incl. determinism test
```

## Known limitations (deliberate POC scope)

- C1 checkers analyze **direct calls** in constructors (no transitive purity);
  documented per rule. C3 (judgment) rules are excluded — they would import
  judge nondeterminism this POC is designed to avoid.
- One model, one harness; the design is arm/task/rule-extensible by adding
  YAML + a checker function.
- Second-task velocity (architecture quality as next-task cost) is specced in
  the parent research doc but not run in this POC.
