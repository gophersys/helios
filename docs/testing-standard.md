# Testing standard

How Go tests run on `arc-org`, and why. Every number here was measured in August
2026 by a workflow that ran on the pool. Nothing here is inferred.

Runner sizing and pool policy: `ci-runners.md`. Pool and image interface:
`ci-substrate.md`.

## The standard invocation

```bash
go test -race -shuffle=on -p 4 ./...
```

3 flags. Nothing else. Each one is justified below, and 2 flags that look useful
are deliberately absent.

## What each flag is worth

| Flag | Measured effect | Verdict |
|---|---|---|
| `-p 4` | **2.9x faster** than serial packages | the only parallelism lever that works |
| `-race` | **1.5x to 1.8x** wall time, **1.2x** memory | keep it |
| `-shuffle=on` | green across all 15 modules | adopt it |
| `-parallel` / more `t.Parallel` | **0x** | do not spend time here |
| `-failfast` | near useless with `t.Parallel` | leave it out |

## `-p` is the lever

`-p` sets how many test binaries run at the same time. It is the only flag that
changed the wall time: **2.9x**.

Set it explicitly. Its default is `GOMAXPROCS`, and `GOMAXPROCS` in a runner pod
is a property of the node, not of the job — see the next section. A wall time
that depends on which node the pod landed on is not a wall time you can hold to a
budget.

`4` matches the worker core count today. Raise it when the workers grow, and
measure again.

## `-parallel` and `t.Parallel` give 0x here

**86.8%** of the tests already call `t.Parallel`, and their bodies are
**sub-millisecond**. There is no serial time left inside a package to recover.

The cost is per package, not per test: compile, link, start the process, run
`TestMain`. That fixed cost dominates. Raising `-parallel` divides a number that
is already near zero.

**Therefore: do not write `t.Parallel` into more tests to make CI faster.** It
will not. Write it for correctness, because a test that cannot run beside its
neighbours has hidden shared state.

## `GOMAXPROCS` is the node core count, not the request

The runner pod requests **1000m** across its 2 containers (500m runner, 500m
dind) and sets **no CPU limit** — CFS throttling makes builds slow and flaky, so
the limit is left off on purpose. See `ci-runners.md`.

A CPU **request** is a scheduling weight. It sets no ceiling and the kernel
enforces no quota from it. The Go runtime therefore finds no cgroup CPU limit to
read, and falls back to the machine:

```
GOMAXPROCS = 4      # the NODE has 4 cores, not 1 from the 1000m request
```

The pod is **guaranteed 1 core and can use 4**. Only the 1 core is guaranteed.
The other 3 are available only while no other pod asks for them:

> Measured: the same suite took **114.5 s** idle and **191.4 s** under
> contention. That is **1.67x**, from nothing but a neighbour.

2 consequences:

1. **A test timeout must survive 1.67x.** Size it against the contended number,
   never the idle number.
2. **A wall-time budget is not a promise.** `maxRunners` is 4 and the workers have
   4 cores each, so 2 runners on 1 node is a normal event, not an incident.

## A cold build cache is 64% of a cold run

> Measured: **61.4 s of a 96.0 s** cold run was the Go build cache filling.

The pod is temporary, so every job starts cold unless the cache is already in the
image.

**The fix is to warm the Go build cache in the runner image.** The kubelet pulls
that image and caches it per node. The first job on a node pays the pull; every
later job starts warm.

**Not a PVC.** A shared writable cache across concurrent runners is a corruption
and locking problem, and it makes a job depend on state no commit can reproduce.

**Not `actions/cache`.** It downloads and extracts on every job, so it re-pays
the cost it is meant to remove, and it stores nothing the image cannot hold.

This is the same rule that put the toolchain on the pod image instead of a
workflow `container:` block. See `ci-substrate.md`.

## Keep `-race`

`-race` costs **1.5x to 1.8x** wall time and **1.2x** memory.

**Do not drop `-race` to hit a time target.** The flag is the only thing in the
suite that finds a data race, and a data race does not fail the same way twice.
If the suite is too slow, cut the cold cache (64%) or raise `-p` (2.9x). Both are
larger than what `-race` costs, and neither loses a class of defect.

## Leave `-failfast` out

`-failfast` stops after the first failure. With `t.Parallel` it does not: every
test already started keeps running, so the saving is a fraction of one package
and the report loses the other failures.

This was proven with a fixture, not assumed.

`-failfast` is worth using in 1 place only: a local loop where you fix 1 test.
It is never worth using in CI, where you want the whole list.

## Adopt `-shuffle=on`

`-shuffle=on` randomizes the order of the tests in a package. It catches a test
that passes only because an earlier test left state behind.

It is **green across all 15 modules** today. Adopt it now, while the cost is
zero. A suite that has never been shuffled hides this defect class until the day
a new test changes the order.

The seed is printed on failure. Reproduce with `-shuffle=<seed>`.

## Which tests run at which trigger

The table above is measurement. This table is **decision**.

| Trigger | What runs | Why |
|---|---|---|
| pre-commit hook | format, lint, and the unit tests of the changed module, without `-race` | must stay fast enough that nobody uses `--no-verify` |
| pre-push hook | the standard invocation, changed modules only | find the race before the pool does |
| pull request | the standard invocation, every module | this is the gate |
| push to `main` | the standard invocation, every module | `main` must stay green after a merge |
| schedule (nightly) | load, mutation, coverage floor, vulnerability, SAST and secret scan | these do not change a merge decision quickly enough to sit on the pull request path |

An integration test that needs a real substrate (docker, k3d, kind) runs at the
pull request trigger, not nightly. The pool has a privileged dind sidecar for
exactly this. Never replace a substrate with a mock to save time.

## The rules behind all of the above

1. **Measure, then change.** Every number here came from a run. `-parallel`
   looked like the obvious lever and was worth 0x.
2. **Never buy speed with a class of defect.** `-race` and `-shuffle=on` stay.
   Cut fixed cost instead.
3. **A missing tool is a failure, not a skip.** The runner image carries the
   toolchain, so an absent binary means the image is wrong. Never guard a test
   step with a skip.
