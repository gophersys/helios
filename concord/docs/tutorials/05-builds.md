---
min_role: DEVELOPER
---

# Tutorial 5: Builds

**Duration:** ~10 minutes
**Audience:** Developers, Maintainers, System Admins
**Format:** Presentation + browser demo

---

## Slide Outline

### Slide 1 — Title

**Visual:** Build run page screenshot

**Content:**

> Builds: From Source Code to Asset Sets

**Speaker notes:**
Builds are the entry point. Every validation run, every manufacturing session, every OTA deployment starts with compiled firmware. This tutorial covers how firmware gets into Concord.

---

### Slide 2 — Three Ways In

**Visual:** Three parallel paths converging to "Asset Set"

**Content:**

```
Internal Build Service ─┐
                        ├──→ Asset Set ──→ Validate ──→ Manufacture / Deploy
External CI (Temacity) ─┤
                        │
Manual Upload ──────────┘
```

| Method | When to use | Who does it |
|--------|-------------|-------------|
| **Internal build service** | Primary workflow. Push code, builds automatically. | Automatic (configured by admin) |
| **External CI upload** | Existing CI pipeline you don't want to migrate yet. | CI system via API |
| **Manual upload** | One-off testing, legacy firmware, hotfixes. | System Admin |

**Speaker notes:**
You don't have to pick one. Some products use the internal build service. Others upload from Temacity. You can even mix — internal builds for main development, manual upload for a hotfix that bypasses CI. All three produce the same output: an asset set that flows through validation.

---

### Slide 3 — Internal Build Service

**Visual:** Automatic pipeline flow

**Content:**

How it works:
1. **Git poller** watches configured branches on Bitbucket
2. New commit detected → **build run** created
3. Build service compiles firmware for all product targets
4. Artifacts (hex, cfw, manifest) stored in MinIO
5. **Asset set** created from successful build
6. Validation auto-scheduled for matching stage configs

**Speed advantage:** Optimized for our firmware. Parallel target builds. Cached toolchains. Typical build: 30-90 seconds. Compare to Temacity's 5+ minutes.

**Speaker notes:**
The internal build service isn't just "another CI." It's purpose-built for our firmware targets. It knows about nRF toolchains, it knows about our multi-target builds, and it integrates directly with validation — no manual steps between "build done" and "tests running."

---

### Slide 4 — External CI Integration

**Visual:** API upload flow

**Content:**

For teams using existing CI (Temacity, GitHub Actions, etc.):

```bash
# Your CI pipeline does:
# 1. Compile firmware (existing workflow)
# 2. Upload artifacts to Concord

curl -X POST https://concord.ad.corekinect.com/v2/builds/upload \
  -H "Authorization: ApiKey $CONCORD_API_KEY" \
  -F "app_hex=@build/alpha_app.hex" \
  -F "comms_hex=@build/alpha_comms.hex" \
  -F "version=1.2.3" \
  -F "variant=release"
```

Concord creates the asset set and triggers validation — same as if the internal service built it.

**Speaker notes:**
This is the migration path. Keep your existing build system, add one API call at the end. You get validation, manufacturing, and traceability without changing how you compile. When you're ready to move builds internal — do it then. No rush.

---

### Slide 5 — Manual Uploads

**Visual:** UI upload form screenshot

**Content:**

System admins can upload pre-built firmware through the browser:

1. Navigate to product → Asset Sets
2. Click "Upload Asset Set"
3. Select files (one per target)
4. Set version and variant
5. Submit

**Use cases:**
- Testing firmware from a branch that isn't watched
- Uploading a vendor-provided binary
- Hotfixing production with a known-good build
- Initial product setup before CI is configured

**Speaker notes:**
Manual upload is the escape hatch. It's not the daily workflow — it's for exceptions. If you find yourself uploading manually every day, that's a sign we should configure a watched branch instead.

---

### Slide 6 — Asset Sets in Detail

**Visual:** Asset set structure diagram

**Content:**

An asset set is the complete firmware package:

```
Asset Set: "v0.5.14"
├── Variant: debug
├── Status: COMPLETE
├── Builds:
│   ├── App (nRF52840): alpha_app_debug.hex (248 KB)
│   └── Comms (nRF9151): alpha_comms_debug.hex (184 KB)
├── Source: internal-build-service
├── Git commit: a4c7f2e
└── Created: 2026-04-20 14:32:07
```

**Variants:** An asset set has a variant (debug, release, manufacturing). Different variants may have different compiler flags, logging levels, or feature toggles. Validation and manufacturing can target specific variants.

**Speaker notes:**
The asset set is the unit of truth. When we say "v0.5.14 is validated" — we mean this specific set of binaries was tested on hardware. Not "the code at that tag compiles" — the actual compiled output was verified. That's the traceability guarantee.

---

### Slide 7 — Build Configs

**Visual:** Build config JSON example

**Content:**

Products can define build configuration:

```json
{
  "targets": {
    "app": {
      "board": "alpha_b0",
      "overlays": ["debug.overlay"],
      "extra_args": "-DCONFIG_LOG_DEFAULT_LEVEL=4"
    },
    "comms": {
      "board": "alpha_comms_b0",
      "overlays": []
    }
  },
  "variants": ["debug", "release", "manufacturing"],
  "post_build": ["generate_dfu_package"]
}
```

This tells the build service exactly how to compile each target for each variant.

**Speaker notes:**
Build configs are set up once by admins or maintainers. They define the build matrix — which boards, which overlays, which variants to produce. Once configured, builds are fully automatic. If you need a new variant or a new overlay, ask a maintainer to update the config.

---

### Slide 8 — The Speed Argument

**Visual:** Timeline comparison

**Content:**

**Before (Temacity):**
```
Push → Wait 5-8 min → Build done → Manual flash → Manual test → 15+ min total
```

**After (Concord internal):**
```
Push → Build (60s) → Validation auto-starts (120s) → Results in ~3 min total
```

**Why it's faster:**
- Parallel multi-target compilation
- Cached toolchains (no download on every build)
- No queue contention (dedicated build workers)
- Zero handoff time between build → validate (automatic)

**Speaker notes:**
Three minutes from push to hardware-verified results. That changes how you develop. You can push small changes frequently and get fast feedback, instead of batching up changes and doing one big "let's see if this works" flash at the end of the day.

---

### Slide 9 — Build → Validate → Ship

**Visual:** Full pipeline with OTA deployment

**Content:**

The complete firmware lifecycle:

```
Code push
  → Build (60s)
    → Smoke validation (2 min) — basic sanity on hardware
      → Driver validation (5 min) — peripheral verification
        → Integration (15 min) — subsystem interaction
          → Regression (30 min) — full pre-release suite
            → FUOTA (10 min) — OTA upgrade verification
              → RELEASE: firmware available for:
                  • Manufacturing (flash onto new units)
                  • OTA deployment (push to devices in the field)
```

Each stage is a gate. Firmware progresses only when it passes.

**Speaker notes:**
This is the full vision. Code goes in one end. A validated, production-ready firmware comes out the other. Every stage adds confidence. By the time firmware reaches manufacturing or OTA deployment, it's been tested on real hardware at every level. No surprises.

---

### Slide 10 — Summary

**Visual:** Three takeaways

**Content:**

1. **Multiple entry points.** Internal builds, external CI, or manual upload — all produce asset sets that flow through the same pipeline.
2. **Speed matters.** Faster builds mean faster feedback means more iterations means better firmware.
3. **Traceability end-to-end.** Every asset set links back to a Git commit. Every validation run links to an asset set. Every manufactured unit links to a validation-approved firmware.

---

## Live Demo Script (2-3 min)

1. **Build runs page** — "Recent builds. This one triggered on a push to main. Built both targets in 47 seconds."
2. **Click into a build** — "Here's the asset set it produced. Two firmware files. Version derived from Git."
3. **Show linked validation** — "And here — validation was auto-scheduled. Already passed smoke. Running driver now."
4. **Asset sets list** — "All versions for this product. You can see which are validated, which are in manufacturing."

---

## Key Points to Reinforce

- Builds are not the goal — validated firmware is the goal. Builds are just the first step.
- The internal build service is faster and more integrated, but external CI is supported and fine to use.
- The Git commit → build → validate → deploy chain is fully traceable. Nothing is "trust me, I built it."
- Speed enables quality. Fast feedback loops catch bugs before they compound.
