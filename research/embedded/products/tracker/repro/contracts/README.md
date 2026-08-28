# Contract-state snapshots for the reproduction runs

The determinism loop demands every run be re-runnable. Runs 2 and 3 were
measured against contract states that were, at the time, UNCOMMITTED
working-tree states — a violation of the loop's own step 6, caught by the
PR #6 refutation. These snapshots RECONSTRUCT those states by reversing
the recorded edit sequence from the committed 7c52eead docs; each reversal
asserted byte-unique anchors. They are labeled reconstructions, not
contemporaneous commits — the one run whose contracts are a real commit
is run 1 (main @ 03109cc7, v1) and run 4 (this branch's HEAD, v3).

- run2-state/ — v1 + post-run-1 fix pack (the state runs 2 measured)
- run3-state/ — run2-state + fix-pack v2 incl. the loosened declared-none
  line that split run 3's verdict
