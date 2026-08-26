# The determinism loop — how any judgment step becomes repeatable

Whenever the research process needs a step to be DETERMINISTIC — same
inputs, same outputs, every run — it earns that property through this
loop, never through assertion. The goal is correctness and determinism;
for hardware, a non-repeatable step upstream poisons everything money is
spent on downstream. (Mateo, 2026-08-26.)

## The loop

1. **FREEZE the inputs.** Verbatim, typos and all, in a dated file. The
   frozen input is the experiment's constant; later answers go in a dated
   addendum, never edited in.
2. **RUN N ≥ 3 blind instances in parallel.** Same written contracts, same
   frozen input, zero contact with each other or with any prior output.
   Each instance also returns its own list of places the contracts
   underdetermined it — that list is data, not commentary.
3. **MEASURE mechanically.** A comparison tool computes per-field
   unanimity, per-class agreement rates, and the verdict split. The tool
   compares canonical content (sorted sets), never string renderings —
   the instrument must be more deterministic than the process it measures.
4. **CLASSIFY every divergence.** (a) contract ambiguity → tighten the
   written contract; (b) input ambiguity → the interrogation/extraction
   should have asked; (c) operator drift → the runner deviated from the
   contracts (measured separately from blind agreement); (d) instrument
   bug → fix the tool first, then re-measure BOTH runs.
5. **RATCHET.** Every fix becomes contract text or a lint rule, never a
   verbal agreement. Judgment migrates to derived rules each time a
   divergence closes. Re-run the loop; the agreement delta is the result.
6. **STOP at unanimity or at an accepted, named residual.** Land the
   contracts, the frozen inputs, the raw instance outputs, the tool, and
   the numbers together — the experiment must be re-runnable by anyone.

## Standing findings from run 1 → run 2 (tracker, 2026-08-26)

- Blind-3 agreement 94.4% → 97.2%; scores 16/16 unanimous both runs;
  verdict unanimous both runs.
- The largest noise source was the OPERATOR, not the readers: the runner
  deviated from his own contracts 5 times; blind instances outvoted him.
- A check's oracle must be machine-readable; a prose oracle diverges.
- The measuring tool itself produced one false disagreement before it was
  canonicalized. Trust order: frozen input > contracts > tool > operator.
