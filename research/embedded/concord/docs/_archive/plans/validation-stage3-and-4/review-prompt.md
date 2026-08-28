# Plan Review Prompt

Give this entire prompt to a review agent. It will read all plan documents
and produce a structured review.

---

## Prompt

```
You are reviewing a comprehensive firmware validation execution plan. Your job
is to find gaps, inconsistencies, missing dependencies, unrealistic assumptions,
and interface mismatches. Be thorough and critical.

Read ALL of the following documents in order:

1. /home/mateo/work/docs/concord/validation/plans/stage3-and-4/overview.md
2. /home/mateo/work/docs/concord/validation/plans/stage3-and-4/status.md
3. /home/mateo/work/docs/concord/validation/plans/stage3-and-4/phases/phase-0-prerequisites.md
4. /home/mateo/work/docs/concord/validation/plans/stage3-and-4/phases/phase-1-parallel-foundation.md
5. /home/mateo/work/docs/concord/validation/plans/stage3-and-4/phases/phase-2-harness-integration.md
6. /home/mateo/work/docs/concord/validation/plans/stage3-and-4/phases/phase-3-stage3-proof.md
7. /home/mateo/work/docs/concord/validation/plans/stage3-and-4/phases/phase-4-5-stage4-proof.md
8. /home/mateo/work/docs/concord/validation/plans/stage3-and-4/phases/phase-6-comparison.md
9. /home/mateo/work/docs/concord/validation/plans/mtib-server-redesign.md

Then read these architecture reference documents for cross-checking:

10. /home/mateo/work/docs/concord/validation/architecture/stage3-integration-tests.md
11. /home/mateo/work/docs/concord/validation/architecture/stage4-product-tests.md
12. /home/mateo/work/docs/concord/validation/project/bom-validation-pipeline.md
13. /home/mateo/work/concord/concord/libs/protocols/mtib_v2/DESIGN.md
14. /home/mateo/work/concord/concord/libs/protocols/mtib/mtib.proto

After reading everything, produce a structured review covering:

## 1. Interface Consistency
- Do the Python test framework interfaces (HarnessTransport, MtibClient,
  FixtureController, CloudClient) match what the MTIB server proto actually
  provides?
- Does the concord_harness shell protocol in the plan match what the
  architecture doc specifies?
- Do the fixture profile pin assignments match the MTIB hardware capabilities
  documented in DESIGN.md?
- Are there any RPCs referenced in the plan that don't exist in the proto
  definition, or vice versa?

## 2. Dependency Gaps
- Are there any streams that claim "no dependency" but actually need something
  from another stream?
- Is the dependency ordering correct? Can Phase 2 actually start when Phase 1
  finishes?
- Are there circular dependencies?
- Does the MTIB server need to be deployed before any firmware flashing can
  happen? If so, is this reflected in the phasing?

## 3. Missing Work
- Are there tasks that aren't captured in any stream? For example:
  - Who generates the proto Python bindings?
  - Who writes the west manifest entry for concord_harness in alpha_fw?
  - Who builds the nRF9151 comms MCU firmware (Stage 4 needs LTE)?
  - Who writes conftest.py for Stage 3 and Stage 4?
  - Who handles the Nx project.json update for the redesigned MTIB server?
- Are there integration gaps between components?

## 4. Hardware Assumptions
- Does the plan account for the single-unit constraint correctly?
  (Dev parallelizes, testing serializes)
- Is the charging limitation correctly reflected in test counts?
- Are the GPIO/ADC pin assignments realistic given the 7 DUT GPIO + 8 ADC
  channel limits?
- Does the motion scaffold integration match what FluidNC actually supports?

## 5. Effort Estimates
- Are any estimates obviously too low or too high?
- Is the MTIB server rewrite at 40h realistic given it's a complete rewrite
  of 7 handlers + observability + deployment?
- Is 52h for the Python test framework realistic?
- Are the "debug + iterate" steps (H2, J9, J10) realistically estimated?

## 6. Risk Assessment
- Are there risks not captured in the risk register?
- What's the actual critical path? (Longest sequential chain)
- What happens if the MTIB server redesign runs late?
- What's the fallback if concord_harness doesn't work on real hardware
  despite working on native_sim?

## 7. Cohesion Check
- Do all documents use consistent terminology?
- Are BOM component IDs consistent across overview and phase documents?
- Do branch names match across documents?
- Are claude-kit kit assignments consistent?
- Do effort totals add up correctly?

## 8. Missing Specifications
- Are there interfaces that are described at too high a level to be
  implementable?
- Are there message types referenced but not defined?
- Are test pass criteria specific enough?

Format your review as a numbered list of findings, each with:
- **Severity**: Critical / High / Medium / Low
- **Location**: Which document(s) and section(s)
- **Finding**: What's wrong or missing
- **Recommendation**: How to fix it

End with a summary: overall plan quality (1-10), top 3 things to fix
before starting execution, and top 3 strengths of the plan.
```
