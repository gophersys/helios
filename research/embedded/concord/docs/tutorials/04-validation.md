---
min_role: DEVELOPER
---

# Tutorial 4: Validation

**Duration:** ~10 minutes
**Audience:** Developers, Maintainers, System Admins
**Format:** Presentation + browser demo + code walkthrough

---

## Slide Outline

### Slide 1 — Title

**Visual:** Validation queue screenshot

**Content:**

> Validation: Automated Hardware Testing on Every Commit

**Speaker notes:**
Manufacturing tests firmware that's already been blessed. Validation is the process that does the blessing. It's the automated answer to "does this firmware actually work on real hardware?"

---

### Slide 2 — The Core Idea

**Visual:** Single concept diagram

**Content:**

```
Code push → Build triggers → Asset set created → Validation scheduled → Tests run on hardware → Results visible
```

No human intervention between code push and test results.

**The promise:** Push code at 4 PM, have hardware-verified results by 4:05 PM.

**Speaker notes:**
This is the thing that changes everything. Before: you push code, build locally, walk to a test bench, flash manually, run tests, squint at serial output. After: push code, go get coffee, results are waiting. On real hardware. Against every enabled stage.

---

### Slide 3 — Stages Revisited (Developer Perspective)

**Visual:** Stage pipeline with timing

**Content:**

| Stage | Triggers on | Duration | What breaks here |
|-------|-------------|----------|-----------------|
| **Smoke** | Every push to watched branch | ~2 min | Boot failures, init crashes, basic communication |
| **Driver** | Every push to watched branch | ~5 min | Peripheral failures, SPI/I2C/UART issues |
| **Integration** | Scheduled (nightly) or manual | ~15 min | Subsystem interaction bugs, timing issues |
| **Regression** | Manual (pre-release) | ~30 min | Regressions in previously-working features |
| **FUOTA** | Manual (pre-release) | ~10 min | OTA update failures, version migration bugs |

**Key insight:** Fast stages run often. Slow stages run on-demand. You find most bugs in Smoke/Driver within minutes of pushing.

**FUOTA is the OTA gate:** Once firmware passes FUOTA, it's cleared for over-the-air deployment to devices already in customers' hands. This is the final safety check before a field update.

**Speaker notes:**
The stage ordering is intentional. Smoke catches 80% of broken commits instantly. Driver catches hardware-specific issues. Integration catches the subtle bugs that only appear when subsystems talk to each other. Regression is the full suite you run before tagging a release. FUOTA verifies the upgrade path from the previous production version.

---

### Slide 4 — How Scheduling Works

**Visual:** Flow diagram showing trigger → queue → execute

**Content:**

1. **Git poller** watches configured branches (per stage config)
2. New commit detected → build triggered
3. Build completes → asset set created
4. Asset set matches an enabled stage config → **validation run auto-scheduled**
5. Runner pod spins up, pulls test package, connects to fixture
6. Tests execute on real hardware
7. Results reported back to Concord

**What you see:** A new row appears in the validation queue. Status goes PENDING → ACTIVE → COMPLETED/FAILED.

**Speaker notes:**
You don't schedule validation manually for Smoke and Driver — it just happens. The system watches your branch, builds, and validates automatically. Integration and Regression stages can be configured to auto-run on schedule or triggered manually when you're ready for a release check.

---

### Slide 5 — Validation vs Manufacturing Tests

**Visual:** Comparison table

**Content:**

| | Validation | Manufacturing |
|--|-----------|---------------|
| **Purpose** | Verify firmware quality | Verify hardware quality |
| **Triggered by** | Code push (automatic) | Operator scan (manual) |
| **Tests change when** | Firmware features change | Manufacturing process changes |
| **Firmware** | Different build per run | Same asset set all day |
| **Hardware** | Fixed DUTs (validation fixtures) | New DUTs every panel |
| **Result means** | "This firmware is good — safe to manufacture or push via FUOTA" | "This unit is good" |

**Speaker notes:**
Same test framework, same fixtures, same runner infrastructure — but different purpose. Validation tests firmware repeatedly on known-good hardware. Manufacturing tests hardware using known-good firmware. If validation passes, we have confidence the firmware is ready for production. If manufacturing passes, we have confidence the unit is ready to ship.

---

### Slide 6 — Writing Test Packages (Overview)

**Visual:** Directory structure + code snippet

**Content:**

Test packages are Python projects using pytest:

```
apps/validation/alpha/
├── concord.yaml           # Product, type, stages
├── pyproject.toml         # Dependencies
├── tests/
│   ├── smoke/
│   │   ├── test_boot.py
│   │   └── test_basic_comms.py
│   ├── driver/
│   │   ├── test_spi.py
│   │   └── test_uart.py
│   └── regression/
│       └── test_full_suite.py
└── conftest.py            # Shared fixtures
```

A typical test:

```python
@pytest.mark.timeout(15)
def test_chip_ids(slot, report):
    """Verify both processors report correct chip IDs."""
    with report.step("Read app chip ID"):
        chip_id, err = slot.app_shell.chip_info()
        assert err is None
        assert chip_id.startswith("nRF52840")

    with report.step("Read comms chip ID"):
        chip_id, err = slot.comms_shell.chip_info()
        assert err is None
        assert chip_id.startswith("nRF9151")
```

**Speaker notes:**
The test framework gives you `slot` — that's your hardware. It has `app_shell` and `comms_shell` for UART communication, `mtib` for power and GPIO control, and `report` for structured result reporting. You write pytest functions, use the hardware abstractions, and the framework handles parallelism, timeouts, and result collection.

---

### Slide 7 — Uploading Test Packages

**Visual:** Terminal commands

**Content:**

```bash
# Development iteration (not released, tagged as dev)
corectl upload

# Release a version (used by production validation)
corectl upload --release
```

`corectl upload` reads `concord.yaml`, packages the directory, and pushes it to Concord's storage. The test package becomes available for runs immediately.

**Development flow:**
1. Write/edit tests locally
2. `corectl upload` (dev version — only your runs use it)
3. Test against hardware
4. Iterate until satisfied
5. `corectl upload --release` (promoted — auto-validation uses this version)

**Speaker notes:**
Dev uploads let you iterate without affecting production validation. Only released versions get picked up by the automatic scheduler. This means you can break your tests while developing without blocking anyone else's builds from validating.

---

### Slide 8 — Reading Validation Results

**Visual:** Screenshot of validation run detail page

**Content:**

A validation run shows:

- **Overall status** — PASSED, FAILED, or ERROR
- **Per-slot results** — if multiple DUTs are used
- **Per-test breakdown** — which test functions passed/failed
- **Per-step detail** — within a test, which steps succeeded
- **Measurements** — numerical data captured during tests
- **Logs** — full UART output and framework logs
- **Duration** — total and per-test timing

**What to look at first:**
- If FAILED: click the red test → read the assertion error → that's what broke
- If ERROR: the test framework itself crashed → check logs for stack trace

**Speaker notes:**
Validation results are your CI feedback loop. Push code, check the validation page 5 minutes later, see if it's green. If it's red, the test name and assertion tell you exactly what regressed. This replaces "flash a board at your desk and manually poke at it."

---

### Slide 9 — The Developer Workflow

**Visual:** Numbered daily workflow

**Content:**

Your daily workflow as a developer:

1. Write firmware code, push to your branch
2. (If branch is watched) Wait ~5 min for smoke results
3. Check validation page — green means it works on hardware
4. If red: read the failing test, fix the issue, push again
5. When ready for release: trigger regression + FUOTA stages
6. All stages green → firmware is release-ready

For test development:
1. Modify test code in `apps/validation/<product>/`
2. `corectl upload` to push dev version
3. Trigger a manual validation run to verify
4. Once satisfied: `corectl upload --release`

**Speaker notes:**
The key shift: you don't manually verify on hardware. The system does it for you, every time, consistently. Your job is to write good firmware and respond to validation failures. If you need a new test — write it, upload it, and it runs automatically from then on.

---

### Slide 10 — Summary

**Visual:** Three takeaways

**Content:**

1. **Automatic.** Push code → validation runs → results appear. No manual steps.
2. **Layered.** Five stages catch different bug classes. Fast ones run often, slow ones run pre-release.
3. **The gate for everything.** Firmware must pass validation before it's manufactured onto new units OR pushed to the field via FUOTA.

Next: Tutorial 5 covers Builds — how firmware gets from source code to asset sets, whether through the internal build service or external CI.

---

## Live Demo Script (3-4 min)

1. **Validation queue** — "Here are recent runs. This one passed smoke on the last push to main."
2. **Click into a run** — "Per-test results. All green. Took 2 minutes. This firmware is verified."
3. **Show a failed run** — "This one has a red test. Click it — 'Expected IMEI format, got empty string.' The comms processor didn't initialize. Developer sees this, fixes the init sequence, pushes again."
4. **Stage configs** — "Back on the product page — here's where admins configure which branches trigger which stages."

---

## Key Points to Reinforce

- Validation is your CI for hardware. It replaces manual test bench verification.
- The faster you find bugs, the cheaper they are to fix. Smoke catches most within minutes.
- Test packages are code — version them, review them, iterate on them like firmware.
- Automatic scheduling means no one needs to remember to test. It just happens.
