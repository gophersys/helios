# The `embedded` image — build-ready spec

Status: build-ready notes. No build starts before Mateo approves the program.
Sources: `image-architecture.md` (design, status DRAFT for review, read
2026-08-16) and `image-census.md` (measured census). Sizes come from the
census. `EST` marks an estimate. All other sizes are measured.
One divergence from the design draft exists. See section 1.2 and Q1.

---

## 1. What this image is

### 1.1 Identity and parent

- Name: `ghcr.io/gophersys/embedded`.
- Parent: `ghcr.io/gophersys/cloud` (the reduced base, rename of `base`,
  budget ≤ 4 GB).
- Build shape: `FROM cloud` + one script, `.devcontainer/_delta/embedded.sh`.
- The same script builds the `matrix` image. `matrix` applies the four delta
  scripts in the fixed order hardware → ui → mobile → embedded. Embedded is
  last. A pin lives once, at the top of `embedded.sh`, as a guarded default
  (`: "${WEST_VERSION:=1.5.0}"`). One edit moves `embedded` and `matrix`
  together.
- Children: `embedded-runner` (the single `runner/Dockerfile` with
  `ARG PARENT_IMAGE=embedded`; delta ≈ 1.04 GB measured).

### 1.2 What it absorbs and what retires

- It absorbs the `zephyr` image. This is a rename plus a move into the
  delta-script mechanism. Contents do not change.
- It absorbs the full `zephyr-devbox` delta. This is the FOLD: sshd,
  code-server, the bench tools, and the Xtensa toolchains move INTO
  `embedded.sh`. They are inert files in CI and in local devcontainers.
  The devbox pod manifest selects sshd with an explicit pod `command`.
  The image default command stays neutral.
- Retired: the `zephyr` image name and the `zephyr-devbox` image name.
  No `embedded-devbox` image exists after the fold.
- NOTE: the design draft I read still lists `embedded-devbox` as a separate
  child image. The fold supersedes that. Sync the design document before
  the build. See Q1.

### 1.3 What the parent already carries (do not install again)

Go 1.26.5 + the gate tools, Python 3.12 + uv, Node 24 (nvm, `dev`-homed),
build-essential/make/pkg-config, docker-ce-cli + buildx + compose, gh, jq,
yq, ripgrep, fd, shellcheck, hadolint, gitleaks, kubeconform, kubectl,
helm, k3d, kind, nats, bun, tailscale, bw. A delta that repeats one of
these fails review.

---

## 2. The exact delta contents

### 2.1 The `zephyr` groups (contents as-is from the old Dockerfile)

| Group | Pins | Size |
|---|---|---|
| apt: ccache, device-tree-compiler, dfu-util, gperf, libmagic1, libsdl2-dev, ninja-build | apt, unpinned | ~200 MB EST |
| west venv | west 1.5.0 + pyelftools, pyyaml, cryptography, intelhex, pykwalify, canopen | ~120 MB EST |
| Zephyr SDK | 1.0.1 minimal + `arm-zephyr-eabi` + `riscv64-zephyr-elf` | ~1.6 GB EST |
| udev rules + `plugdev`/`dialout` groups | — | < 1 MB |

### 2.2 The groups that move OUT of the old base, INTO this delta

| Group | Size | Why here |
|---|---|---|
| cmake | ~110 MB EST | Zephyr builds need it. No other lane does. |
| USB/BLE: bluez, libbluetooth-dev, libusb-1.0-0-dev, libudev-dev, usbutils | ~20 MB EST | Flash and BLE work is this lane only. |
| Rust via `_delta/components/rust.sh`: rustup stable, minimal profile + rustfmt + clippy | 675 MB | Locked decision: embedded keeps Rust. The script is shared with `ui.sh` and is idempotent. |

### 2.3 The devbox FOLD (contents as-is from the old zephyr-devbox Dockerfile)

| Group | Pins | Size |
|---|---|---|
| apt bench tools: clangd, gdb-multiarch, openocd, openssh-server, picocom, stlink-tools | apt, unpinned | ~280 MB EST |
| esptool venv | esptool 5.3.1 | ~30 MB EST |
| west venv runtime deps: requests, jsonschema, esptool, pyserial | — | ~50 MB EST |
| Xtensa Espressif SDK toolchains: esp32, esp32s2, esp32s3 | 3 toolchains | ~1.5 GB EST |
| udev USB-UART rules + sshd drop-in + zshenv | — | < 1 MB |
| code-server | 4.127.0 (.deb) | ~350 MB EST |
| clangd extension seed | — | ~40 MB EST |

Fold rule: sshd does not start by default. code-server does not start by
default. The pod manifest starts sshd through its `command`. CI never
starts either.

### 2.4 Size projection

- Delta total ≈ 4.9 GB EST (2.05 zephyr + 0.13 moved + 0.68 Rust + 2.2 fold).
- Image total ≈ cloud (3.0–4.8 GB EST, the ≤ 4 GB gate decides) + 4.9 GB.
- `embedded-runner` adds ≈ 1.04 GB (measured runner delta).

### 2.5 Deliberately dropped — and why

Nothing from the old `zephyr` or `zephyr-devbox` images drops. The drops
happen in the parent and apply here through inheritance:

| Dropped in cloud | Size | Reason |
|---|---|---|
| ansible + ansible-core + oci-cli | 787 MB | Infra-ops tools. No embedded gate calls them. |
| AWS CLI v2 | 268 MB | Only arm-builder EC2 ops touched AWS. |
| terraform | 101 MB | Infra CLI. Not in the baseline. |
| k9s | 129 MB | Interactive TUI. kubectl covers CI. |
| DB clients (psql, redis-cli, sqlite3) | ~25 MB EST | No embedded gate calls them. |
| httpie, speedtest-cli, bat, btop, htop, ncat, net-tools | ~100 MB EST | Comfort only. |
| Go module/build caches in the gate-tools layer | ~1.6 GB | Cache, not tools. The cleanup is mandatory in cloud. |

Not in this image, by design: GTK/webkit/clang (ui only), JDK/Android
SDK/Flutter (mobile only), KiCad (hardware only), Chrome (ui only).

### 2.6 Script mechanics

`embedded.sh` follows the delta-script contract: `set -euo pipefail`, one
tool group per function, apt lists cleaned in the same RUN, pins at the
top as guarded defaults, and a proof block at the end. A missing tool
FAILS the build and names the tool. `ENV` lines (none known for this
delta today) go in the Dockerfile, not the script.

---

## 3. Dual-arch notes

### 3.1 The policy

- Platforms: `linux/amd64,linux/arm64` for `embedded` and `embedded-runner`.
- amd64 builds native on the cluster (arc-org pool).
- arm64 builds native on the mini's buildkitd (`tcp://10.168.0.92:1234`,
  mTLS, BUILD API only). Never QEMU. If the mini is down, the build FAILS
  and names the node.
- Both arches get an executed smoke on native silicon: amd64 in-cluster,
  arm64 on the mini's own docker.

### 3.2 Arch risks specific to this category

- Zephyr SDK 1.0.1 ships aarch64 host toolchains. The arm/riscv cross
  compilers are safe on arm64. Size ≈ amd64.
- The Xtensa Espressif SDK aarch64 host toolchains are UNPROVEN (design
  risk R2). The fold moves this risk from the old devbox image into
  `embedded` itself. If no aarch64 host build exists, the WHOLE embedded
  image narrows to amd64.
- code-server arm64 is UNPROVEN (same risk, same consequence).
- The narrow switch exists and is documented: set
  `IMAGE_PLATFORMS="linux/amd64"` in `embedded/ctl.sh` before the library
  `source`. A narrow image is stated, never silent. The devbox pods sit on
  amd64 nodes today, so a narrow embedded still serves the k3s-w-4 lab.

---

## 4. The publish-gate test spec — real-world, correctness-first

The gate runs BEFORE publish. A gate that cannot run is a failure that
names the missing thing. No step skips.

### 4.1 Job 1 — amd64 build + category smoke (arc-org pod, pre-publish)

```
docker buildx build --platform linux/amd64 --load \
  -f embedded/Dockerfile -t "$REF" .devcontainer/
bash .ci/smoke.sh "$REF"          # smoke takes the ref; never :latest
```

Tool proof block (inside `$REF`; every line must exit 0):

```
west --version                       # 1.5.0 venv on PATH
cmake --version && ninja --version && ccache --version && dtc --version
cargo --version && cargo clippy --version && rustfmt --version
arm-zephyr-eabi-gcc --version
riscv64-zephyr-elf-gcc --version
xtensa-esp32-elf-gcc --version       # fold proof
xtensa-esp32s3-elf-gcc --version
esptool version && openocd --version && st-flash --version
sshd -t                              # config parses; daemon NOT started
code-server --version
```

Real-world build proof (inside `$REF`; this is the correctness gate):

```
west init -m <pinned manifest> ws && cd ws && west update
west blobs fetch hal_espressif
west build -p -b nucleo_h743zi \
  research-embedded/zephyr-cipher/samples/rpc_uplink
west build -p -b esp32_devkitc_wroom/esp32/procpu \
  research-embedded/zephyr-cipher/samples/matrix_node
west build -p -b esp32s3_devkitc/esp32s3/procpu \
  research-embedded/zephyr-cipher/samples/rpc_uplink
west twister --integration -T research-embedded/concord/libs/zephyr
```

Assertions:

- Each `west build` exits 0 AND produces `build/zephyr/zephyr.elf`
  (`test -f`). An exit 0 with no ELF is red.
- `west twister` exits 0 AND executes MORE THAN zero cases. A zero-case
  run is red (FAIL-NOT-SKIP: an empty test scope is a silent pass).
- Any nonzero exit stops the pipeline before any push.

After a green smoke, push the arch tag `:<sha>-amd64`.

### 4.2 Job 2 — arm64 build (same pod, remote driver to the mini)

Mount the `buildkit-client-certs` secret. `docker buildx create --driver
remote tcp://10.168.0.92:1234` with the mTLS flags. Build
`--platform linux/arm64`. Push `:<sha>-arm64`. If embedded narrows to
amd64 (section 3.2), this job does not exist and the manifest declares
amd64 only.

### 4.3 Job 3 — arm64 smoke ON the mini (native execution)

A job on the mini's macOS runner pulls `:<sha>-arm64` and runs the SAME
smoke blocks (4.1) through the mini's docker. Apple silicon executes
linux/arm64 natively. An emulated smoke is forbidden — an emulated pass
hid a mislabelled image before (D42). The job joins the `mini-serial`
concurrency group.

### 4.4 Job 4 — manifest merge + verify

```
docker buildx imagetools create -t :<sha> -t :latest :<sha>-amd64 :<sha>-arm64
```

Then `verify-published` asserts the manifest lists exactly
`IMAGE_PLATFORMS`, and `[infra] ctl.sh verify-image-arch <ref>` reads the
ELF machine bytes per arch.

### 4.5 WEEKLY hardware-in-the-loop — flash + run on the k3s-w-4 USB lab

A scheduled workflow, weekly, post-publish. Substrate: the devbox pod on
k3s-w-4 (privileged; `/dev/bus/usb` and `/dev/serial` host mounts).

1. Restart the pod. `:latest` + `imagePullPolicy: Always` pulls the new
   digest. Record the digest in the run log.
2. Flash every mapped lab slot from inside the pod: `west flash` — esptool
   over USB-UART for the ESP32 and ESP32-S3 slots, openocd/stlink for the
   Nucleo slots.
3. Run on target:
   `west twister --device-testing --hardware-map <map.yml>` for the mapped
   slots, plus the cipher on-hardware smoke at the proven evidence bar:
   RPC 100/100 on ESP32 WiFi; RPC 200/200 and stream checksum-OK on
   Nucleo-H743ZI Ethernet.
4. Assertions: every mapped slot flashes AND passes. A red names the slot
   and the board. Nucleo slot 4 stays OUT of the map — its PHY is
   hardware-dead (confirmed by MDIO scan). That exclusion is written in
   the map with its reason.
5. An unreachable pod or node is red and names `k3s-w-4`. Never a skip.
6. A red weekly run blocks every devbox re-pin and triggers the rollback
   re-pin (section 5.3) to the last-good digest.

---

## 5. Migration and rollback

### 5.1 When

This category rides design steps (a) rename and (b) delta extraction, as
one `/dev` feature per step. Dual-arch rides step (d). Package deletion
waits for §8 of the design and needs Mateo's authorization.

### 5.2 Steps

1. Create `.devcontainer/_delta/embedded.sh` and
   `.devcontainer/_delta/components/rust.sh` (idempotent: a second caller
   asserts the version and exits 0). Move the section-2 contents in,
   verbatim, pins at the top.
2. Create `embedded/Dockerfile`: `FROM cloud`, `COPY _delta/`, `RUN` the
   script, then `rm -rf /opt/delta`. Build context is `.devcontainer/`
   with `--file embedded/Dockerfile`.
3. Do NOT create an `embedded-devbox/` directory. Delete the `zephyr/`
   and `zephyr-devbox/` directories in the same change.
4. Sync the dependency graph in all 4 places: BUILD_ORDER in the
   `.devcontainer` ctl AND its byte-identical provider copy; eden
   `project.json` `dependsOn`; `build-and-push.yml` job `needs` in BOTH
   workflow copies. New invariant for the graph-sync test: an edit to
   `_delta/embedded.sh` rebuilds `embedded`, `embedded-runner`, AND
   `matrix`.
5. Re-point the infra consumers (repo `gophersys/infrastructure`):
   - `apps/embedded/zephyr-devbox/base/deployment.yaml:50` — image →
     `ghcr.io/gophersys/embedded:latest`; ADD the pod `command` that runs
     the sshd entrypoint (the fold makes the image default neutral).
   - `apps/embedded/zephyr-devbox/base/` service, configmap,
     kustomization, storage — rename the app path and names.
   - `apps/embedded/envs/zephyr-libs/kustomization.yaml` and
     `apps/embedded/envs/nucleo-bringup/kustomization.yaml` — resource
     path and name references.
   - `platform/services/gitops/registry/app-zephyr-envs.yaml`.
   - `apps/workspaces/workspaces-api/20-deployment.yaml` — its
     zephyr-devbox reference.
   - `.github/workflows/validate.yml`, `scripts/verify-image-arch.sh`,
     `scripts/lint-manifests.sh` — name references.
   - `platform/services/ci/arc-runners/41-image-warmer-config.yaml` (and
     the daemonset) — the warmer list gains `embedded`, loses `zephyr`
     and `zephyr-devbox`. The warmer-coverage test asserts the new set.
   - Docs: `docs/cluster-topology.md`, `docs/ci-substrate.md`,
     `docs/debt-register.md`, `apps/embedded/README.md` — inside the
     step, never as a drive-by.
6. Point this repository's CI and devcontainer at
   `ghcr.io/gophersys/embedded` BY DIGEST. Dev and CI pin the same digest;
   the tripwire test asserts the two references resolve to one digest.
7. Wire `embedded-runner` only when an embedded CI pool exists (Q7).

### 5.3 Rollback

- The old `ghcr.io/gophersys/zephyr` and `ghcr.io/gophersys/zephyr-devbox`
  tags never move. They stay published until Mateo authorizes deletion,
  after soak.
- Pods: one infra commit re-pins `deployment.yaml` to
  `ghcr.io/gophersys/zephyr-devbox:<last-good digest>` and removes the
  `command` override. The pod restarts. Nothing else changes.
- Eden: one revert restores the `zephyr/` and `zephyr-devbox/`
  directories and the old graph.
- CI consumers pin by digest, so a bad `embedded` digest rolls back with
  one pin edit in each consumer.
- Dual-arch rollback: revert `SANCTIONED_PLATFORMS` to `linux/amd64`.
  Published manifests keep their amd64 half.

---

## 6. Open questions — honest

- **Q1 — design divergence.** The design draft (status DRAFT, read
  2026-08-16) lists `embedded-devbox` as a separate child image. This spec
  folds the devbox into `embedded` and retires the separate image, per the
  program brief. The design document must be updated to match before the
  build, or this spec must be corrected. One of the two documents is wrong
  today.
- **Q2 — the fold widens the arm64 risk.** Xtensa aarch64 host toolchains
  and code-server arm64 are unproven. Before the fold, a failure narrowed
  only the devbox. After the fold, it narrows ALL of `embedded`. Decide:
  accept a possible amd64-only embedded, or reconsider the fold if arm64
  embedded CI matters.
- **Q3 — the fold's size cost.** Every embedded CI pull carries ~2.2 GB of
  bench, sshd, and code-server files it never runs. Delta ≈ 4.9 GB EST
  total. Accepted, or not?
- **Q4 — the west manifest pin.** The publish gate needs a pinned Zephyr
  revision for `west init && west update`. No west manifest exists in this
  repository today. Decide its home and its pin owner.
- **Q5 — the sample-per-board matrix.** `nucleo_h743zi` and
  `esp32_devkitc_wroom/esp32/procpu` have sample overlays in
  `zephyr-cipher` today. No sample carries an `esp32s3_devkitc` overlay
  yet; the target id is referenced but unproven here. Also, `zephyr-cipher`
  has no `testcase.yaml`, so the twister scope today is
  `concord/libs/zephyr` only. Author the s3 overlay and the zephyr-cipher
  twister manifests, or trim the gate to what exists — decide which.
- **Q6 — the hardware map.** `west twister --device-testing` needs a
  `hardware-map` file. None exists. Author it from the k3s-w-4 slot map,
  with slot 4 excluded and the PHY reason written in.
- **Q7 — embedded-runner day 1.** No embedded CI pool exists yet. Build
  `embedded-runner` with the category, or defer until a pool needs it.
