# Concord: Continuous Delivery for Embedded Systems

A thesis on applying continuous delivery principles to firmware engineering, grounded in Dave Farley's [*Modern Software Engineering*](https://www.amazon.com/Modern-Software-Engineering-Discipline-Development/dp/0137314914) and Forsgren, Humble & Kim's [*Accelerate*](https://www.amazon.com/Accelerate-Software-Performing-Technology-Organizations/dp/1942788339).

**Why this matters:**

- **Elite performers are 2x more likely to exceed profitability, productivity, and customer satisfaction goals.** DORA's [10+ years of research](https://dora.dev/research/2024/dora-report/) across 39,000+ professionals proves that speed and stability are *correlated*, not competing — teams that deploy more frequently also have lower failure rates. ([Accelerate State of DevOps Report, 2024](https://services.google.com/fh/files/misc/2024_final_dora_report.pdf))
- **The data holds across industries, including regulated and hardware-adjacent domains.** The research covers organizations of all sizes and sectors. Elite teams deploy multiple times per day with change failure rates below 5%, while low performers deploy monthly with failure rates above 46%. The gap is not marginal — it is [an order of magnitude](https://www.atlassian.com/devops/frameworks/dora-metrics).
- **These are engineering practices, not tooling choices.** Farley's core argument is that continuous delivery is the application of [scientific reasoning to software development](https://www.davefarley.net/?p=352) — working in small batches, getting fast feedback, and iterating. The principles are universal; only the implementation changes for embedded.

---

## 1. The Core Problem

Embedded engineering operates under a belief system that makes continuous delivery seem impossible:

- "We can't deploy on every commit — we'd brick devices."
- "Hardware-in-the-loop tests are too slow for CI."
- "OTA is too risky to automate."
- "Our release cadence is dictated by hardware, not software."

These beliefs produce a predictable outcome: long release cycles, manual validation gates, low confidence in firmware quality, and a growing backlog of changes that compound risk with every passing week. The longer you wait to integrate and validate, the harder it becomes to find and fix problems. This is the exact dynamic that *Accelerate* identifies as the hallmark of low-performing organizations.

The Accelerate research is unambiguous: **elite performers deploy more frequently AND have lower failure rates.** Speed and stability are not trade-offs — they are correlated outcomes of the same underlying practices. The question is not whether these principles apply to embedded systems. The question is how to implement them given the real constraints of physical hardware, cross-compilation, over-the-air delivery, and devices that can't be SSH'd into when something goes wrong.

Concord exists to answer that question.

---

## 2. The Thesis

**Concord is a deployment pipeline for embedded systems that treats every firmware commit as a release candidate, validates it through progressive hardware-in-the-loop stages, and delivers it to devices — all without human intervention in the critical path.**

This is not a build system. It is not a test runner. It is not a dashboard. It is the **executable specification of how firmware goes from a developer's commit to a validated, deployed artifact on a physical device.** The pipeline is the product. Everything else — the build service, the validation framework, the FUOTA client, the MTIB infrastructure — exists to serve this pipeline.

Farley's central insight: the deployment pipeline is the backbone. Every change flows through the same pipeline. Every stage provides fast, automated feedback. The pipeline is deterministic — same inputs, same outputs. When it breaks, you stop and fix it before anything else.

Web pipelines end at "deploy to production server." Embedded pipelines must pass through physical reality — real silicon, real sensors, real radio links, real power constraints — before they earn the right to be called "deployable." Harder to build, but more valuable once built. The alternative is a human manually running through a test checklist on a lab bench.

---

## 3. The Embedded Deployment Pipeline

Concord's five-stage model maps directly to Farley's deployment pipeline — each stage provides faster feedback at lower cost before escalating to slower, higher-fidelity validation:

```
Commit → Build → Stage 1 → Stage 2 → Stage 3 → Stage 4 → Stage 5 → Deploy
         (sec)   (min)      (min)      (min)      (hours)   (min)     (min)

         Cross-   Software   Silicon    Harness    Black-box  Gate     FUOTA
         compile  sim        real HW    instrum.   product    PR+OTA   delivery

         Zero     Zero       Dev-kit    MTIB +     MTIB +     MTIB +   CoreCloud
         hardware hardware   fixture    product    product    product  OTA server
                                        board      board      board
```

**The key property:** each stage is a strict quality gate. If Stage 1 fails, you never waste a physical test bench on a build that can't even pass its unit tests. If Stage 5 fails (the fast gate that includes FUOTA), the PR is blocked — the firmware never reaches production devices.

This is the embedded equivalent of Farley's "fail fast" principle. The cheapest stages run first. The most expensive stages (which require physical hardware, real OTA delivery, and minutes of wall-clock time) run last, and only on firmware that has already survived everything cheaper.

### What the Pipeline Must Prove

Each stage answers a specific question:

| Stage | Question | Evidence |
|-------|----------|----------|
| Build | Does it compile for all target boards and configurations? | Clean cross-compilation, no warnings-as-errors |
| 1 - Smoke | Do the software abstractions behave correctly in isolation? | Unit + integration tests pass on native_sim |
| 2 - Silicon | Do the drivers work on real silicon? | Sensor reads, peripheral I/O, power measurements on dev-kit |
| 3 - Integration | Does the instrumented firmware work as a system? | End-to-end flows via concord_harness on product board |
| 4 - Product | Does the production binary work as a black-box product? | 89 product test cases (PRDTST) on production firmware, no harness |
| 5 - Gate | Can we safely deliver this firmware to devices in the field? | FUOTA delivery + post-update verification in < 15 minutes |

**The pipeline doesn't just test the firmware — it tests the delivery mechanism.** Stage 5 includes an actual FUOTA delivery, the same one used to update devices in the field. If FUOTA fails in Stage 5, it would have failed in production. Farley calls this "practice the hard things."

---

## 4. The Four Keys — Adapted for Embedded

*Accelerate* identifies four metrics that predict delivery performance. They were designed for web software. Here's what they mean when your deployment target is a microcontroller in a plastic enclosure.

### 4.1 Lead Time for Changes

In web: commit to production. In embedded: **commit to validated, deployable firmware** — optionally extended through FUOTA delivery.

Lead time is the speed of your feedback loop. When it's short, developers learn about breakage while the code is still fresh in their heads. When it's long, they've context-switched to something else and the fix takes twice as long.

```
Lead Time = PipelineRun.finishedAt - PipelineRun.createdAt
```

That covers build + validation. What it misses: developer wait time before the pipeline triggers, and deployment lag after it succeeds. Breaking it down:

| Segment | Source | Status |
|---------|--------|--------|
| Queue wait | BuildJob.startedAt - BuildJob.queuedAt | **MISSING** — no `queuedAt` field |
| Build time | BuildJob.durationSeconds | Tracked |
| Validation time | Session.finishedAt - Session.startedAt | Tracked |
| FUOTA delivery | — | **MISSING** — no deployment model |
| End-to-end | PipelineRun.finishedAt - PipelineRun.createdAt | Tracked |

Targets: Stage 5 gate under 15 minutes, Stage 4 nightly under 60 minutes, full pipeline under 2 hours. The trend matters more than the absolute number — if lead time is climbing week over week, the pipeline is degrading.

### 4.2 Deployment Frequency

Deployment frequency is really a proxy for batch size. Deploy often, and each release carries one or two changes — easy to diagnose when something breaks. Deploy monthly, and you're shipping 47 commits at once, praying the radio stack still works.

For embedded, frequency splits in two:

- **Internal** — how often firmware passes the full pipeline and becomes deployable. Measurable today: `COUNT(PipelineRun WHERE status = 'SUCCESS') per week`.
- **External** — how often firmware actually reaches devices via FUOTA. Not measurable — Concord has no deployment model. FUOTA happens through CoreCloud with no results captured back.

The goal: every PR triggers a pipeline automatically. No manual "should we test this?" decisions. Multiple successful pipelines per day internally, weekly FUOTA deliveries to staging devices externally.

### 4.3 Change Failure Rate

The counterbalance to speed. In embedded, a failed deployment isn't a 500 error on a web page — it's a boot loop, a bricked device, or a field recall.

There's a critical distinction here. Pipeline and validation failures are *good* — the pipeline caught a problem before it reached a device. The metric that matters is the **post-deployment failure rate**: firmware that passed every stage but still caused problems in the field.

```
Pipeline CFR  = failed pipelines / total pipelines
FUOTA CFR     = failed post-update checks / total deployments  // MISSING MODEL
```

Concord can track build and validation failure rates today. Post-deployment failure rate? Zero visibility — there's no feedback loop from devices back to the platform.

Targets: build failures under 5% (developers should run Stage 1 locally), validation failures under 15% (cheap stages catch most issues), post-deployment failures under 1%. If Stage 4/5 failure rates are high, that means earlier stages have gaps — bugs are escaping upward.

### 4.4 Mean Time to Recovery

The hardest metric, and the one with the highest stakes. In web, recovery means rolling back a deployment. In embedded, it depends on how badly things went wrong:

| Scenario | Recovery | Time |
|----------|----------|------|
| Bad firmware, MCUboot rollback works | Automatic — device reverts to previous slot | Seconds |
| Bad firmware, device boots but degraded | FUOTA fix delivery | Minutes to hours |
| Bad firmware, device can't reach cloud | Physical intervention (J-Link reflash) | Days |
| Bad firmware, bricked bootloader | RMA / physical recovery | Weeks |

The pipeline's job is to make the bottom two rows impossible. MCUboot handles the first. The pipeline handles the second by catching bugs before they ship. Rows three and four are pipeline failures — that firmware should never have been deployed.

Concord currently has **zero** incident tracking, **zero** deployment tracking, and **zero** device health monitoring. MTTR is unmeasurable. To change that, we need:

1. A **Deployment** model — firmware version, target devices, delivery status, post-update health check
2. An **Incident** model or integration with an external system
3. A **device health feedback loop** — the device reports its state back to Concord after an update

---

## 5. Beyond the Four Keys — Metrics the Books Don't Cover

DORA was designed for web. Embedded has a physical dimension that creates failure modes — and metrics — with no web equivalent.

### 5.1 Test Infrastructure Reliability

An MTIB that intermittently drops UART bytes produces test failures that look like firmware bugs. If engineers can't trust the pipeline, they stop investigating failures ("probably just the MTIB acting up") and eventually stop using the pipeline entirely. Death by a thousand paper cuts.

Every test failure needs a classification: **firmware** (the test caught a real bug), **infrastructure** (MTIB, power supply, fixture, or connectivity), or **test** (the assertion or timeout is wrong). Concord's `errorMessage` is free text today — no structured categorization exists. Without it, you can't distinguish a sick pipeline from a sick product.

### 5.2 Test Stability

Flaky tests are the #1 pipeline killer. A test that fails 5% of the time means every 20th run produces a false negative. With 50 tests, that's 2-3 spurious failures per run. Engineers start re-running "one more time to see if it passes." Then they stop investigating. Then they bypass the pipeline.

Measuring flakiness means tracking results per `(test_name, firmware_version, hardware_revision)` tuple over time. Concord captures individual results but doesn't aggregate them.

Embedded flakiness has sources web engineers never deal with: sensor noise, wireless interference, power supply settling time, UART streaming latency, and lab temperature drift. Each demands a different fix — wider tolerances, retry logic, environmental monitoring, hardware changes. You can't fix what you can't categorize.

### 5.3 Stage Escape Rate

When Stage 4 catches a bug that Stage 1 could have caught, that's an hour of bench time wasted on a problem that should have been flagged in seconds. The escape rate measures how often bugs slip past cheaper stages to be caught by expensive ones.

High escape rates from Stage 1 → Stage 4 mean Stage 1 needs more tests. Low escape rates mean the stage model is earning its keep. The [traceability matrix](../reference/traceability-matrix.md) maps test cases across stages to make this measurable.

### 5.4 FUOTA Delivery

FUOTA is the deployment mechanism — embedded's equivalent of `kubectl apply`, except you can't easily roll back a device that stops responding.

| Metric | Status |
|--------|--------|
| Delivery success rate | **Not tracked** |
| Delivery time (plan creation → 100%) | **Not tracked** |
| Post-update boot success rate | **Not tracked** |
| MCUboot rollback rate | **Not tracked** |
| Pages per second (throughput) | Measured in tests, not in DB |

None of these are captured. FUOTA goes through CoreCloud, and Concord has no feedback loop. This is the single largest measurement gap in the platform.

---

## 6. The Self-Measuring Pipeline

A pipeline that's getting slower, flakier, or less reliable is quietly destroying the feedback loop that makes continuous delivery work. Concord needs to measure its own health, not just the firmware's.

| Metric | Question It Answers | How to Track |
|--------|---------------------|--------------|
| Cycle time trend | Is the pipeline getting slower? | Weekly rolling average of PipelineRun duration |
| Build worker utilization | Bottlenecked on compute? | % time workers are building vs. idle |
| Test bench utilization | Bottlenecked on hardware? | % time MTIBs are running tests vs. idle |
| Queue depth | How much work is waiting? | QUEUED BuildJobs and TestExecutions over time |
| Infrastructure failure rate | Is test infra degrading? | Classified failures: infrastructure vs. firmware |
| False positive rate | Wasting developer time? | Tests that fail on pipeline, pass on re-run |
| Feedback latency | How fast do developers learn? | Commit push → first failure notification |

After every pipeline run, the platform should record timing data, classify failures, compute rolling metrics, compare against SLAs, and alert on degradation. Humble and Farley call this the "build monitor" — the pipeline's health dashboard should be as prominent as the product's. If the pipeline is sick, the team is flying blind.

---

## 7. Where Concord Stands Today

### Data Model Coverage

| Concept | Model Exists? | Timestamps? | Status Tracking? | Queryable for Metrics? |
|---------|--------------|-------------|-----------------|----------------------|
| Build | Yes (BuildJob) | Partial (no queuedAt) | Yes (8 states) | Yes |
| Pipeline | Yes (PipelineRun) | Yes | Yes (6 states) | Yes |
| Validation Run | Yes (Session) | Yes | Yes | Yes |
| Test Execution | Yes (TestExecution) | Yes | Yes (7 states) | Yes |
| Test Result | Yes (TestResult) | Partial | Boolean pass/fail | Partial (JSON blob) |
| Deployment (FUOTA) | **No** | — | — | — |
| Incident | **No** | — | — | — |
| Device Health | **No** | — | — | — |
| Metric Aggregate | **No** | — | — | — |
| Failure Category | **No** | — | — | — |

### Derivable Today vs. Needs Work

**Can compute right now:**
- Pipeline cycle time (end-to-end and per-stage)
- Build success/failure rate
- Validation pass/fail rate per session
- Test execution duration distribution
- Build duration by product/board
- Deployment frequency (pipeline completions per period)
- Change failure rate (pipeline failures per period)

**Needs small schema additions:**
- Queue wait time (add `queuedAt` to BuildJob)
- Failure categorization (add `failureCategory` enum to TestExecution)
- SLA compliance (compare durations against stage config thresholds)
- Test flakiness (add historical comparison query or materialized view)

**Needs new models:**
- Deployment tracking (FUOTA plan → device delivery → post-update check)
- Device health feedback (device → cloud → Concord)
- Incident tracking (or integration with external system)
- Metric aggregates (pre-computed daily/weekly summaries)

---

## 8. The Gap That Matters Most

**Concord has no concept of "deployed to production."**

The pipeline ends at "validation passed." No record of which firmware version runs on which devices. No record of when a firmware was delivered, whether devices booted successfully, or whether a deployment was rolled back. Three of the four DORA metrics are either unmeasurable (MTTR) or only partially measurable (deployment frequency, change failure rate).

This is a factory with no shipping dock — you can build and inspect the product, but you have no idea what happens after it leaves the building.

### Closing the Loop

```
Pipeline Success
    → Firmware marked "deployable"
    → FUOTA plan created in CoreCloud (tracked in Concord)
    → Device delivery progress tracked
    → Post-update health check (boot success, basic telemetry)
    → Deployment record closed with outcome
    → Metrics updated
```

This loop is the difference between CI (we build and test) and CD (we build, test, and deliver). Concord is currently a CI system. The thesis is that it should be a CD system.

---

## 9. Principles

Five rules, drawn from Farley and the Accelerate research, that should govern how Concord is built.

**Every commit is a release candidate.** No "development builds" vs. "release builds." Every commit triggers the same pipeline, and the pipeline — not a human — decides if the firmware ships. Concord's `triggerType` already supports webhooks. That needs to be the default, not the exception.

**The pipeline is the authority.** Pass means deployable. Fail means not. No human override, no "let's ship it anyway, we're under pressure." The moment you bypass the pipeline, you've destroyed the feedback loop. `blocksMerge` must be enforced at the Bitbucket level — a failed Stage 5 gate should physically prevent PR merge.

**Fix the pipeline before fixing the product.** A broken pipeline is worse than a broken product, because it means you can't detect or fix anything. A flaky test is a higher priority than the next feature. A rising flake rate should trigger the same urgency as a production outage.

**Measure outcomes, not activity.** Lines of code, commit count, test count — activity metrics. They show people are busy. They don't show whether working firmware is reaching devices. The primary dashboard shows the four DORA keys. Build counts and test counts are diagnostic detail.

**Optimize for fast feedback.** The most important property of the pipeline is speed. A developer who gets feedback in 10 minutes iterates six times in an hour. A developer who waits 2 hours iterates once and context-switches. Stage 5's 15-minute SLA is the constraint everything else must serve.

---

## 10. Open Questions

These need concrete answers before this thesis becomes an implementation plan.

**Product & deployment reality:**

1. **What does "production" mean today?** Devices in customers' hands, or internal staging?
2. **What's the current release cadence?** Weekly? Monthly? "When someone remembers"?
3. **How many firmware variants?** Products × boards × configs × debug/release — 4 is different from 40.

**Organizational:**

4. **How many developers push firmware changes?** One person's throughput looks different from a team of five.
5. **Who consumes pipeline results?** Developers only? QA? Management? Auditors?
6. **Any compliance requirements?** FDA? Industrial safety? Traceability mandates?

**Technical:**

7. **Can devices report back after FUOTA?** Does the device tell CoreCloud its new firmware version? Can Concord query that?
8. **Where's the biggest bottleneck?** Build time? Queue wait? Test execution? Manual steps? Theory of Constraints: optimize the bottleneck, ignore everything else.
9. **How many test benches?** One MTIB means zero parallelism. Ten changes the design entirely.
10. **Can Concord write to CoreCloud?** Create FUOTA plans, assign devices, track delivery — programmatically?

---

## 11. Success Criteria

A developer pushes a firmware change. Without any human intervention, it's built, validated across all stages, and — if every gate passes — delivered to staging devices via FUOTA. The developer sees pass/fail/deployed within a defined time window. The entire journey is tracked, timed, and measurable.

**The four numbers on the wall:**

| Metric | Current (estimate) | 90-day target | North star |
|--------|-------------------|---------------|------------|
| Lead time (commit → validated) | Unknown (manual) | < 2 hours | < 30 min |
| Deployment frequency | Ad-hoc | Weekly | On every merge to main |
| Change failure rate | Unknown | < 20% | < 5% |
| Mean time to recovery | Unknown (days?) | < 4 hours | < 1 hour |

These are estimates. Filling them in with real data is the first milestone — you can't improve what you don't measure.

---

*The pipeline is the product. Everything Concord builds traces back to these principles, these metrics, and these questions.*
