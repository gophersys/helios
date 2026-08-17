# mobile — the build-ready image spec

> **STATUS: PROPOSAL. The `mobile` image does not exist.** Last judged against
> the tree on 2026-08-17. Read `.claude/rules/00-identity.md` for what the
> repository builds today, and `docs/README.md` for the class of file this is.
>
> **Names this document PROPOSES, which are not in the tree:**
> `ghcr.io/gophersys/mobile`, `mobile/`, `_delta/mobile.sh`, `mobile-runner`,
> `matrix`, and `ARG PARENT_IMAGE`. `_delta/` holds `components/*.sh` and no
> `mobile.sh`; `runner/Dockerfile` declares `ARG BASE_IMAGE` and no
> `PARENT_IMAGE`.
>
> **Every pin below is the value that was current when this was written.** The
> live pins are in `flutter/Dockerfile` and they have moved since —
> `FLUTTER_VERSION` is 3.47.0 there today, against the 3.41.7 this document
> repeats. Re-resolve every pin before you build from these notes.

Status: build-ready notes. Develop later without new derivation.
Grounding: the image-architecture design (draft, 2026-08) and the measured
image census. Sizes marked EST are estimates. All other sizes are measured.
Language: ASD-STE100 Simplified Technical English.

---

## 1. What the mobile image is

`ghcr.io/gophersys/mobile` is the category image for Flutter and Android
work. It is a rename of today's `flutter` image.

- **Parent:** `ghcr.io/gophersys/cloud`. The parent supplies git, Go, Python,
  Node (nvm, `dev`-homed), gh, docker CLI + buildx, and the gate toolchain.
  This document called `cloud` "a rename of `base`". It is not: `cloud`
  builds `FROM ubuntu` directly, so it is a reduction and not a layer, and
  `base` is still built and still published.
- **Recipe:** `mobile = cloud + _delta/mobile.sh`. One script holds the
  delta. The `matrix` image consumes the same script. One edit moves both.
- **Home:** this repo. The directory `flutter/` becomes `mobile/`.
- **Absorbs:** the full content of `flutter/Dockerfile`, unchanged.
- **Retires:** the `flutter` image name and directory. The old ghcr
  `flutter` package stays until Mateo authorizes its deletion (see §5).
- **Child: SUPERSEDED.** This document proposed `mobile-runner` = mobile +
  the single `runner/Dockerfile` (`ARG PARENT_IMAGE`), with the runner delta
  measured at ~1.04 GB. The category-image program supersedes it. The
  `+ runner` layer is retired: all 3 ARC pools run `cloud`, which folds the
  runner in itself, the `base-runner` package is gone from ghcr, and
  `runner/` is on disk only until the consolidation wave deletes it. A
  `<category>-runner` child image is therefore not the shape any more — a CI
  consumer takes a pool whose image already carries the runner. The size
  measurement is kept because it is half of why the layer was dropped.
  `ARG PARENT_IMAGE` never existed; `runner/Dockerfile` declares
  `ARG BASE_IMAGE`.
- **Out of scope for the image:** iOS. Xcode cannot run in a Linux
  container. The iOS lane runs on the mini's native macOS runner (§3.2).

Why the image shrinks although its delta does not change: today `flutter`
sits on the 9.26 GB `base`. Tomorrow it sits on `cloud` (3.0–4.8 GB EST).
The parent drops ansible + oci-cli (787 MB), AWS CLI (268 MB), terraform
(101 MB), k9s (129 MB), DB clients, and the convenience tools, and it
cleans 1.6 GB of Go cache. Rust, clang, GTK, and cmake move to the ui and
embedded deltas. The mobile image loses all of that weight for free.

---

## 2. The exact delta — `_delta/mobile.sh`

The delta is the `flutter/Dockerfile` content, as-is. Nothing in the delta
itself is dropped. The census proves each group serves the lane.

| # | Group | Exact content | Size |
|---|---|---|---|
| 1 | apt | `openjdk-${JAVA_VERSION}-jdk-headless` (resolves to 21 from the guarded default below), `libglu1-mesa`, `ninja-build`, `file` (`--no-install-recommends`, lists cleaned in the same RUN) | ~300 MB EST |
| 2 | Android SDK | cmdline-tools `14742923`; `platform-tools`; `platforms;android-36`; `build-tools;36.1.0`; licenses accepted at build time via `sdkmanager --licenses` | ~1.3 GB EST |
| 3 | Flutter SDK | `3.41.7` `stable` tarball from `storage.googleapis.com/flutter_infra_release`, with the bundled Dart | ~1.8 GB EST |

Delta total ≈ **3.4 GB EST**. Image total ≈ cloud + 3.4 GB per arch.

Row 1 shows the package in its parameterized form because that is what
`flutter/Dockerfile` writes: `openjdk-${JAVA_VERSION}-jdk-headless` with
`ARG JAVA_VERSION=21`. This paragraph used to instruct a future change to
correct an "OpenJDK 17" row in `00-identity.md`. That correction landed:
the identity's flutter row reads OpenJDK 21 now. Do not go looking for it.

**Pins (one home, top of `mobile.sh`, guarded defaults):**

```bash
: "${JAVA_VERSION:=21}"
: "${ANDROID_CMDLINE_TOOLS_VERSION:=14742923}"
: "${ANDROID_PLATFORM_VERSION:=36}"
: "${ANDROID_BUILDTOOLS_VERSION:=36.1.0}"
: "${FLUTTER_VERSION:=3.41.7}"
: "${FLUTTER_CHANNEL:=stable}"
```

The `mobile/Dockerfile` declares its ARGs at the top and passes overrides
on the RUN line. The default case passes nothing. A Dockerfile that
repeats a pin without an override reason fails review.

**ENV (set in the Dockerfile — a script cannot set ENV):**

```
ANDROID_SDK_ROOT=/opt/android-sdk
ANDROID_HOME=/opt/android-sdk
FLUTTER_HOME=/opt/flutter
FLUTTER_ROOT=/opt/flutter
PUB_CACHE=/home/dev/.pub-cache
PATH += /opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/opt/flutter/bin:/opt/flutter/bin/cache/dart-sdk/bin
GOPHERSYS_DEVCONTAINER=mobile        # was: flutter
```

**Proof block (end of `mobile.sh`; the build FAILS if a line fails):**

```bash
java -version
sdkmanager --version
test -d "${ANDROID_SDK_ROOT}/build-tools/${ANDROID_BUILDTOOLS_VERSION}"
test -d "${ANDROID_SDK_ROOT}/platforms/android-${ANDROID_PLATFORM_VERSION}"
flutter --version | grep -F "${FLUTTER_VERSION}"
dart --version
```

The old Dockerfile skips the Flutter proof with a QEMU note ("bundled dart
fails under QEMU cross-arch build"). That caveat retires: the new pipeline
bans QEMU, and both arches build on native silicon, so the RUN steps
execute the native Dart runtime. Keep the platform sanity `case` that
rejects platforms outside `linux/amd64|linux/arm64`.

**Deliberately dropped, and why:**

- Nothing from the flutter delta itself. All three groups serve the gate.
- From the parent (drops decided at the cloud level, listed here so the
  mobile lane knows what it no longer carries): ansible/oci-cli, AWS CLI,
  terraform, k9s, psql/redis-cli/sqlite3, httpie/bat/btop/htop/ncat/
  net-tools. No mobile gate calls them.
- The emulator and Android system images are NOT baked. They are ~1.5+ GB
  EST and only the weekly emulator gate uses them (§4.4, open Q3).

---

## 3. Dual-arch notes

Target policy — it lands at M3 (§5): `linux/amd64,linux/arm64` for mobile
and mobile-runner. Today `SANCTIONED_PLATFORMS` in `_ctl/lib.sh` holds
`linux/amd64` only, so a `mobile/ctl.sh` that declares arm64 before M3
fails `require_sanctioned_platforms`. No QEMU, ever. amd64 builds native
on the cluster (arc-org). arm64 builds native on the mini's buildkitd
(`tcp://10.168.0.92:1234`, mTLS, BUILD API only). If the mini is down,
the build FAILS and names the node.

### 3.1 Arch risk specific to mobile (design risk R2)

- Android **cmdline-tools** are JAR-based. They run on both arches through
  the JVM. Low risk.
- Android **build-tools 36.1.0 host binaries** (aapt2 and friends) for
  linux-arm64 are **unproven**. Google's linux-arm64 host support is the
  single biggest arch risk in this category. The first native arm64 build
  decides. The in-build proof block turns a missing binary into a red
  build, not a silent gap.
- **openjdk-21** and **Flutter linux-arm64** both ship for arm64. Low risk.
- If build-tools (or the APK gate, §4.2) fail on arm64: narrow mobile to
  amd64 with an explicit `IMAGE_PLATFORMS="linux/amd64"` in
  `mobile/ctl.sh` — the documented switch from the widening checklist.
  State the narrow in the README. Never hide it.

### 3.2 The iOS lane (the one exception to devcontainer-everywhere)

| Item | State |
|---|---|
| Substrate | Native macOS runner on the mini. No container. |
| Xcode | 16.4 — present on the mini. |
| Flutter on macOS | To install. Pin the SAME `3.41.7`. |
| Signing | No Apple cert exists. Gate with `--no-codesign` now. Real signing lands when the cert exists. |
| Scope | Exactly: `flutter build ios`, `xcodebuild`, iOS simulator tests, App Store signing. Every other gate for the same repo runs in the `mobile` image. A job that claims the exception outside this scope fails review. |

### 3.3 Mini concurrency and the 8 GB constraint

- The mini has 8 GB RAM. ALL mini runner work joins ONE GitHub concurrency
  group: `mini-serial`, `cancel-in-progress: false`. Members: iOS builds,
  the arm64 image build + smoke job (§4.3).
- buildkitd work from other clients arrives over the BUILD API and does
  NOT respect the group. Such a build can land during an iOS build (design
  risk R1). The mobile publish gate is not that client: its arm64 build
  runs from a `mini-serial` job (§4.3). Until measured, treat parallel
  mini load as unknown.
- Mini health workflow (scheduled; red = FAIL and name the node): disk
  floor ≥ 20 GB free after pruning (docker prune, buildkitd GC, Xcode
  DerivedData, Flutter cache); buildkitd liveness (`buildctl debug
  workers` over mTLS); runner liveness (canary job starts within a bound).

---

## 4. The publish gate — real-world test spec

Correctness first: a version print does not prove the toolchain. The gate
that proves mobile is **a real APK built from a real Flutter project**.
Every gate FAILS loudly. A gate that cannot run (mini unreachable, image
not local) is a failure that names the missing thing.

Every command in this section assumes M1 is complete. `.ci/smoke.sh`
accepts `mobile` only after M1 step 3 renames the `flutter)` case arm and
the valid-images list. Run these commands before M1 and the script fails
with `unknown image: 'mobile'`.

### 4.1 Job 1 — amd64 build + smoke BEFORE publish (arc-org pod)

Build context is `.devcontainer/` (the repo root), because `_delta/` sits
one level above `mobile/`.

```bash
docker buildx build --platform linux/amd64 --load \
  --file mobile/Dockerfile \
  --tag "ghcr.io/gophersys/mobile:${SHA}-amd64" .
bash .ci/smoke.sh mobile "ghcr.io/gophersys/mobile:${SHA}-amd64"   # LOADED image, pre-push
docker push "ghcr.io/gophersys/mobile:${SHA}-amd64"
```

### 4.2 The mobile smoke (extends the base smoke in `.ci/smoke.sh`)

Today's flutter smoke is `flutter --version && adb --version &&
java -version`. Keep it, and add the assertions and the real-world gate:

```bash
# Toolchain identity — exact pins, not just presence.
flutter --version | grep -F "3.41.7"
dart --version
java -version 2>&1 | grep -F '"21'
adb --version
sdkmanager --version
test -d "${ANDROID_SDK_ROOT}/build-tools/36.1.0"
test -d "${ANDROID_SDK_ROOT}/platforms/android-36"

# The REAL gate: a debug APK from a fresh project.
flutter create /tmp/smokeapp
cd /tmp/smokeapp
flutter build apk --debug
test -f build/app/outputs/flutter-apk/app-debug.apk
```

The APK gate exercises Gradle, the JDK, aapt2, the Android platform, and
the Dart compiler end to end. It is the assertion that catches a broken
link between pinned parts. Network note: the first build downloads Gradle,
pub packages, and engine artifacts — see open Q2 (bake caches vs allow
network in this gate).

### 4.3 Jobs 2–3 — arm64 and the manifest

The arm64 half obeys the same law as §4.1 and as every publish job in
00-identity.md: build → smoke the LOADED image → only then push. A push
cannot be undone, so no tag — the per-arch `-arm64` tag included — may
reach ghcr before the native smoke is green.

```bash
# Job 2 — arm64 build + smoke + push, ON the mini (joins mini-serial).
# runs-on: [self-hosted, macos, mini]. The buildx client runs where the
# buildkitd and the arm64-native docker both live, so --load stays local.
docker buildx create --name mini --driver remote tcp://10.168.0.92:1234 \
  <mTLS flags; certs from secret buildkit-client-certs>
docker buildx build --builder mini --platform linux/arm64 --load \
  --file mobile/Dockerfile \
  --tag "ghcr.io/gophersys/mobile:${SHA}-arm64" .
bash .ci/smoke.sh mobile "ghcr.io/gophersys/mobile:${SHA}-arm64"   # LOADED image, pre-push; SAME script, APK gate included
docker buildx build --builder mini --platform linux/arm64 --push \
  --file mobile/Dockerfile \
  --tag "ghcr.io/gophersys/mobile:${SHA}-arm64" .                  # second build: cache hit, push only

# Job 3 — manifest merge + verify.
docker buildx imagetools create \
  -t "ghcr.io/gophersys/mobile:${SHA}" -t ghcr.io/gophersys/mobile:latest \
  "ghcr.io/gophersys/mobile:${SHA}-amd64" "ghcr.io/gophersys/mobile:${SHA}-arm64"
# verify-published: manifest lists BOTH platforms; compare to IMAGE_PLATFORMS.
# [infra] ctl.sh verify-image-arch <ref>: read the ELF machine bytes per arch.
```

The two-build shape is the publish pattern from 00-identity.md: the
first build loads and does not push, the smoke asserts the loaded image,
and the second build pushes from the cache the first one wrote.

An emulated smoke is forbidden. The D42 defect passed an emulated smoke
and shipped mislabelled. Job 2 on the mini is the only sanctioned arm64
execution. Because the whole arm64 lane runs inside `mini-serial`, the
publish gate's own build also respects the group (§3.3, risk R1).

### 4.4 The iOS gate and the weekly emulator gate

**iOS (per PR that touches the mobile lane; mini, `mini-serial`):**

```bash
flutter --version | grep -F "3.41.7"   # mini pin MUST equal the mobile.sh pin; drift = red
flutter build ios --no-codesign
```

When the Apple cert exists: replace `--no-codesign` with the signed build
and a `codesign --verify` assertion. That change is its own PR.

**Emulator (weekly scheduled workflow; amd64 node WITH /dev/kvm):**

```bash
test -e /dev/kvm || { echo "FAIL: /dev/kvm absent on ${NODE_NAME}"; exit 1; }
sdkmanager "emulator" "system-images;android-36;google_apis;x86_64"
avdmanager create avd -n smoke --force -k "system-images;android-36;google_apis;x86_64"
emulator -avd smoke -no-window -no-audio -gpu swiftshader_indirect &
adb wait-for-device
adb shell 'while [ "$(getprop sys.boot_completed)" != "1" ]; do sleep 2; done'
cd /tmp/smokeapp && flutter test integration_test
```

A missing /dev/kvm is a FAILURE that names the node — never a skip.

---

## 5. Migration and rollback

Each step is one /dev feature. Order matters. Old ghcr tags never move
until Mateo authorizes deletion.

**M1 — rename flutter → mobile (design step a).**
1. `git mv flutter mobile`; image name → `ghcr.io/gophersys/mobile`;
   `ENV GOPHERSYS_DEVCONTAINER=mobile`; Dockerfile contents unchanged.
2. Sync the graph in the 6 files 00-identity.md names: `BUILD_ORDER` in
   `./ctl.sh` (1) and in `.ci/ctl.sh` (2); `dependsOn` in the image's own
   `project.json` (3); job `needs` in `.github/workflows/build-and-push.yml`
   (4); `image_parent()` in `.ci/affected.sh` (5); the byte-identical
   provider copy `.ci/providers/github/build-and-push.yml` (6). This step
   said 4 and omitted `image_parent()`, which arrived with affected-only
   builds — a missing edge there publishes a child on a parent that moved
   under it.
3. `.ci/smoke.sh`: the `flutter)` case arm and the valid-images list →
   `mobile`.
4. Update the warmer image list and any devcontainer.json that names
   `flutter`.
*Rollback:* revert the commit. The old `flutter` tags never moved.
Consumers re-pin in one commit.

**M2 — ride the parent change (design step b).**
1. Create `_delta/mobile.sh` from the Dockerfile RUN bodies; pins become
   the guarded defaults of §2; add the proof block.
2. `mobile/Dockerfile` becomes: `FROM ghcr.io/gophersys/cloud:${BASE_TAG}`
   + `COPY _delta/ /opt/delta/` + `RUN bash /opt/delta/mobile.sh && rm -rf
   /opt/delta`. Build context = `.devcontainer/`.
3. `matrix` consumes the same script (fixed order: hardware → ui → mobile
   → embedded). An edit to `mobile.sh` must rebuild `mobile`,
   `mobile-runner` (when it exists), AND `matrix` — assert this in the
   graph-sync test.
*Rollback:* the last `base`-parented `flutter`/`mobile` tag stays
published and pinned in the rollback note. One revert restores the old
Dockerfile.

**M3 — dual-arch (design step d).** Mobile widens with the fleet policy.
If arm64 fails (§3.1): set `IMAGE_PLATFORMS="linux/amd64"` in
`mobile/ctl.sh`, state it in the README, keep the amd64 half green.
*Rollback:* revert `SANCTIONED_PLATFORMS`; the amd64 half of every
published manifest keeps working.

**M4 — the iOS lane on the mini.** Install Flutter 3.41.7 for macOS on
the mini; add the pin-equality assert to the iOS job; add the §3.2
carve-out text to governance; join `mini-serial`. Can land any time after
M1.
*Rollback:* remove the workflow; the mini keeps only a dormant Flutter
install.

**Deletions (after proof, Mateo authorizes):** the ghcr `flutter` package
deletes after M1 + the fleet re-pin soak. `mobile-runner` publishes only
when a consumer exists.

---

## 6. Open questions — honest

1. **Android build-tools 36.1.0 on linux-arm64 host: unproven.** The first
   native arm64 build gives the verdict. Fallback: the documented narrow
   (§3.1). Probability unknown; do not plan around a green.
2. **APK-gate network.** `flutter build apk` downloads Gradle, pub, and
   engine artifacts on first run. Options: (a) bake caches in the delta
   (`flutter precache --android` + a warm Gradle cache; adds ~1+ GB EST,
   unmeasured), or (b) allow network in the publish gate only. The
   zero-install acceptance covers devcontainer postCreate, not this gate —
   but decide explicitly and write it down.
3. **Emulator home.** System image + emulator ≈ 1.5+ GB EST. Bake into the
   image, or install in the weekly job? Current spec: install in the job.
   Cost: weekly download; benefit: 1.5 GB off every pull.
4. **The Flutter pin has a second home on the mini.** The macOS install
   sits outside the image, so the one-home rule bends. Mitigation in spec:
   the iOS job asserts mini-Flutter == the `mobile.sh` pin, so drift is
   red. The install/upgrade step on the mini stays manual until automated.
5. **No Apple signing cert.** `--no-codesign` proves compilation and
   linking, not signing or App Store upload. That half of the lane stays
   unproven until the cert exists.
6. **/dev/kvm on the cluster's amd64 nodes: unverified.** The weekly gate
   fails loudly if absent; verify a node and label it before scheduling.
7. **Mini under concurrent load (design R1).** 8 GB covers neither an iOS
   build nor an image build comfortably, and buildkitd ignores
   `mini-serial` for every client outside the mobile gate (§3.3). Measure
   before trusting parallel load; a RAM upgrade or a build window is the
   real fix.
8. **Delta sizes are EST.** The flutter image was never local; ~3.4 GB is
   an estimate. The first M2 build measures it; the size-budget test
   records the real number.
