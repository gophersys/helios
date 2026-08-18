# The `ui` image — build-ready notes

Status: specification, ready to build. Do not derive again.
Sources: the image-architecture design and the measured image census
(2026-08 image-consolidation program). Decision record: ADR-0003
(`docs/adr/0003-ui-image-consolidation.md`). Sizes come from the census.
`EST` marks an estimate. All other sizes are measured.
Language: ASD-STE100 Simplified Technical English.

---

## 1. What the `ui` image is

`ghcr.io/gophersys/ui` is the one image for all UI work: dev container,
CI container, and the `ui-runner` child.

- **Parent:** `ghcr.io/gophersys/cloud`. This is the reduced base image
  (the rename of `base`, with the drop list and the 1.6 GB Go-cache
  cleanup applied). Target for cloud: 4 GB or less.
- **Construction:** `FROM cloud` + one script, `_delta/ui.sh`. The script
  lives in the eden `.devcontainer/_delta/` directory. The same script
  builds the `ui` layer of the `matrix` image. One edit moves both.
- **Child:** `ui-runner` = `ui` + the single `runner/Dockerfile`
  (`ARG PARENT_IMAGE`). The runner delta is ~1.04 GB: .NET runtime deps,
  Actions runner 2.336.0, cictl, claude CLI.

### What it absorbs

- `ghcr.io/gophersys/research-ui-ci` (this repo, `ci/Dockerfile`,
  `FROM base`). All of its toolchain moves into `_delta/ui.sh`.
- This repo's `.devcontainer/Dockerfile` (`FROM research-ui-ci`). Its
  five comfort packages (zsh, less, jq, gh, ripgrep) are already in
  cloud. Nothing is lost.

### What it retires

When the `ui` image is green (migration step (c), section 5):

- `ci/Dockerfile` — deleted.
- `.devcontainer/Dockerfile` — deleted.
- `.github/workflows/build-ci-image.yml` — deleted.
- The `|| (retry without gh)` fallback in the old devcontainer build —
  it dies with the file. It let `gh` be absent without failing the image
  build. That is acceptable for a comfort package in a devcontainer, but
  the pattern must not migrate to gate tooling.

The census verdict on this repo: **zero toolchain drift** between dev
and CI, because dev built FROM the CI image. The `ui` image keeps that
property. Dev and CI pin the SAME digest (acceptance metric 5).

---

## 2. The exact delta — `_delta/ui.sh`

Order and contents are fixed. Pins live ONCE, at the top of the script,
as guarded defaults (`: "${VAR:=value}"`). A Dockerfile that repeats a
pin without an override reason fails review.

| # | Group | Content | Size |
|---|---|---|---|
| 1 | GTK/webkit/Tauri dev libs (moved out of base) | `libgtk-3-dev`, `libwebkit2gtk-4.1-dev`, `librsvg2-dev`, `libayatana-appindicator3-dev` | ~450 MB EST |
| 2 | clang (moved out of base) | apt `clang` | ~550 MB EST |
| 3 | Rust | `components/rust.sh`: rustup stable, minimal profile + rustfmt + clippy. SHARED with `_delta/embedded.sh`. Must be idempotent: a second caller detects the toolchain, asserts the version, exits 0 | 675 MB |
| 4 | Browser | amd64: `google-chrome-stable` from Google's apt repo. arm64: a pinned non-snap Chromium (see section 3, risk R3). BOTH arches get the `/usr/local/bin/ui-chromium` symlink and `ENV UI_CHROME` | in group total |
| 5 | Fonts | `fonts-dejavu-core`. `ctl.sh` uses the fallback font path `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` for `assemble.py` off-macOS | small |
| 6 | Node 22 root-wide | NodeSource install. Reason: gates run as root; cloud's Node 24 is nvm-homed under the `dev` user and root does not see it | in group total |
| 7 | uv root-wide | Install at `/usr/local/bin`. Same reason: cloud's uv lives in `/home/dev/.local/bin` | small |
| 8 | `ENV PYTHONUNBUFFERED=1` | Set in the Dockerfile, not the script (a script cannot set ENV). Reason: gates must stream output. A silent step read as a stall and got cancelled (run 31761167311) | 0 |
| 9 | Proof block | `ui-chromium --version && uv --version && node --version && python3 --version` — or the build FAILS and names the tool | 0 |

Delta total: **cloud + ~1.7 GB** per arch (EST until first build).

Script rules: `set -euo pipefail`; one tool group per function; apt
lists cleaned in the same RUN; the proof block at the end.

Known coexistence facts (no collision, by design):

- Root-wide Node 22 (ui) and nvm Node 24 (cloud) live in different
  paths.
- Root-wide uv (ui) and dev-homed uv (cloud) live in different paths.

### What was deliberately dropped, and why

- **Nothing from the CI toolchain.** The census found zero drop
  candidates in `ci/Dockerfile`. Every tool serves a gate.
- **The devcontainer comfort layer** (zsh, less, jq, gh, ripgrep) —
  not re-installed. Cloud already carries all five.
- **The gh soft-skip fallback** — deleted, not ported (section 1).
- **The base drop list does not come back through ui.** Cloud drops
  ansible+oci-cli (787 MB), AWS CLI v2 (268 MB), terraform (101 MB),
  k9s (129 MB), DB clients (~25 MB EST), and the convenience set
  (httpie, speedtest-cli, bat, btop, htop, ncat, net-tools, ~100 MB
  EST). No UI gate calls any of them. The `ui` delta must not
  re-install any of them.
- **cmake and the USB/BLE libs** moved to `_delta/embedded.sh`, not
  here. Tauri on Linux does not need them.

What ui gets from cloud and must NOT re-install: build-essential,
Python 3.12 + pip + venv, Go + gate tools, jq/yq/rg/fd, shellcheck,
hadolint, gitleaks, kubeconform, gh, docker-ce-cli + compose +
buildx plugin, kubectl/helm, k3d/kind, nats, bun, tailscale, bw.

---

## 3. Dual-arch notes

Policy for all six images: `linux/amd64,linux/arm64`. No QEMU in CI,
ever. amd64 builds native on the cluster (arc-org pool). arm64 builds
native on the mini's buildkitd (`tcp://10.168.0.92:1234`, mTLS, BUILD
API only, measured 3.44x faster than emulation). If the mini is down,
the build FAILS and names the node.

### The UI-specific arch risk — R3, no Chrome on linux/arm64

- Google ships NO arm64 Linux Chrome. `google-chrome-stable` exists
  for amd64 only.
- Ubuntu's `chromium` package is a snap stub. It does not work in a
  container.
- The Playwright browser CDN timed out from the fleet before. Do not
  depend on it.
- Candidate source: Debian's `chromium`, apt-pinned. **Unproven.**
  Prove it before the first arm64 publish.
- Both arches MUST resolve the same entry point: the
  `/usr/local/bin/ui-chromium` symlink and `ENV UI_CHROME`.
  `tools/ui/src/ui/probe.py` reads `UI_CHROME`. Gates must
  not branch on arch.
- Version skew is structural: amd64 Chrome and arm64 Chromium will not
  have the same version. See open question Q2.

### The narrow-loudly switch

If no arm64 Chromium source proves out, `ui` narrows to amd64. This is
a stated decision, never a silent skip:

1. Set `IMAGE_PLATFORMS="linux/amd64"` explicitly in `ui/ctl.sh`,
   before the `source` of the ctl library.
2. Use the narrow per-image key in `build-and-push.yml` (the
   `PLATFORMS_AMD64_ONLY` pattern), in BOTH the workflow and its
   byte-identical `.ci/providers/github/` copy.
3. `platform-policy.test.sh` clause 2 then asserts "non-empty SUBSET
   of the sanctioned set", not equality.
4. `verify-published` compares the manifest to `IMAGE_PLATFORMS`, so a
   correct amd64-only manifest stays green.
5. Write the reason (R3) next to the narrow declaration. The probe
   battery is then amd64-only — stated in the workflow, not hidden.

### Smoke substrate

- amd64 smoke: in-cluster, against the LOADED image, BEFORE publish.
- arm64 smoke: executed natively on the mini's docker
  (`runs-on: [self-hosted, macos, mini]`), in the `mini-serial`
  concurrency group. An emulated smoke is forbidden — D42 proved an
  emulated pass hides a mislabelled image.

---

## 4. The publish gate — real-world tests, every publish

Correctness first: the gate runs the REAL workload, not only
`--version` checks. Order per arch: build → load → smoke → push arch
tag. Then: manifest merge → verify. A gate that cannot run (mini
unreachable, image not local) is a FAILURE that names the missing
thing. Nothing skips.

### 4.1 Build-time proof (inside `_delta/ui.sh`)

```bash
ui-chromium --version
uv --version
node --version        # must report v22.x
python3 --version
```

Any non-zero exit fails the BUILD, before any tag exists.

### 4.2 The ui probe battery (per arch, executed)

Run the repo's own gates inside the candidate image, as root, against
a pinned research-ui checkout:

```bash
docker run --rm -v "$PWD:/w" -w /w <candidate-ref> \
  bash -lc 'bash ctl.sh test'
docker run --rm -v "$PWD:/w" -w /w <candidate-ref> bash -lc '
  set -euo pipefail
  bash ctl.sh geometry | tee /tmp/geo.txt
  bash ctl.sh score    | tee /tmp/score.txt
  grep -Eq "\"parts\": *[1-9]" /tmp/geo.txt \
    || { echo "geometry report has no non-zero parts count"; exit 1; }
  grep -Eq "\"targets_measured\": *[1-9]" /tmp/score.txt \
    || { echo "score report measured no targets"; exit 1; }'
```

Both commands rely on the image's baked `ENV UI_CHROME` (group 4,
section 2). Do not pass `-e UI_CHROME` without a value: docker then
overrides the baked value with an unset one (host-unset) or an empty
string (`-e UI_CHROME=`), and `probe.py` treats both the same —
`if env:` is false for `""` — so it silently falls through to its
candidate search. The probe may then find the image's Chrome by path
and pass without proving the baked `ENV` (defeating assertion 2), or
fail with `no Chrome/Chromium found` when no candidate exists. The
`UI_CHROME=<path> does not exist` error fires only for a non-empty
path that does not exist.

Assertions:

1. Exit 0 on each command.
2. The probe battery started headless Chrome through `UI_CHROME`
   (the probe output names the browser binary and version).
3. `geometry` and `score` produce real reports for the pinned
   fixture — not empty ones. An empty report is red. The command block
   enforces this by field name, not by the presence of a stray digit:
   the `geometry` capture must carry a non-zero `"parts"` count (the
   demo-build reports) and the `score` capture a non-zero
   `"targets_measured"` count (the scorecard), so a report that is
   empty, malformed, or mere error text fails the gate.
4. `uv run` resolved as root (proves the root-wide uv), and
   `node --check` ran as root (proves the root-wide Node 22).

### 4.3 The Tauri hello build (per arch, executed)

This is the proof for groups 1–3 (GTK/webkit libs, clang, Rust). A
`--version` check cannot prove a linker path; a real build can.

```bash
docker run --rm -v "<hello-fixture>:/hello" -w /hello <candidate-ref> \
  bash -lc 'cargo build --locked --release'
```

Assertions:

1. Exit 0. A missing dev lib fails here with the pkg-config name —
   that failure is the gate working, not noise.
2. The produced binary exists and `file` reports the arch under test
   (amd64: x86-64; arm64: aarch64). This is the D42 class of check:
   content, not label.
3. The fixture is a minimal Tauri app that links `webkit2gtk-4.1` and
   `gtk-3`, with a committed `Cargo.lock`. See open question Q1 for
   where it lives and how its crates stay deterministic.

### 4.4 Per-arch execution map

| Arch | Where the battery runs | When |
|---|---|---|
| amd64 | arc-org pod, against the `--load`-ed image | BEFORE the amd64 push |
| arm64 | the mini's docker, natively, `mini-serial` group | after the arm64 arch-tag push, BEFORE the manifest merge |

### 4.5 Manifest and content verify

```bash
docker buildx imagetools create -t <ref>:<sha> -t <ref>:latest \
  <ref>:<sha>-amd64 <ref>:<sha>-arm64
# verify-published: manifest platforms == IMAGE_PLATFORMS
# [infra] ctl.sh verify-image-arch <ref>   # reads ELF machine bytes
```

If ui is narrowed (section 3), the arm64 rows are absent by policy and
the manifest assertion expects amd64 only.

---

## 5. Migration — step (c) of the program, this repo's part

Preconditions: steps (a) renames and (b) cloud reduction are merged;
`cloud` is published; `_delta/ui.sh` exists and builds.

1. Build and publish `ghcr.io/gophersys/ui` through the section-4
   gate. If R3 is unresolved on that day, publish amd64-only through
   the narrow-loudly switch.
2. Point this repo's CI (`.github/workflows/ci.yml`, `on-pr.yml`) at
   `ghcr.io/gophersys/ui` **by digest**.
3. Point `.devcontainer/devcontainer.json` at the SAME digest. Add the
   tripwire that asserts the two references resolve to one digest
   (acceptance metric 5).
4. Run CI once on the new image. One green run is the bar.
5. In the same PR as the pin change or the next one: DELETE
   `ci/Dockerfile`, `.devcontainer/Dockerfile`, and
   `.github/workflows/build-ci-image.yml`.
6. After a soak period: delete the ghcr package `research-ui-ci`.
   **Mateo authorizes this deletion. Nobody else.**

### Status — steps 1 and 2 have landed (2026-08-18)

Step 1 is done upstream: `ghcr.io/gophersys/ui` is published by
`gophersys/.devcontainer` (`ui/Dockerfile`, `FROM cloud`), **dual-arch**
— amd64 AND arm64. R3 dissolved rather than resolved: Google's stable
component now publishes `google-chrome-stable` for arm64 at the same
version as amd64 (measured upstream 2026-08-18), so section 3's
"Google ships NO arm64 Linux Chrome" is out of date and the pinned
Debian Chromium candidate is not needed. Nothing compares the arm64
browser yet — that gap is recorded upstream, not here.

Step 2 landed **by digest, as this ADR requires**, plus two deviations
that remain deliberate:

- **The pin.** All three container jobs run
  `ghcr.io/gophersys/ui:latest@sha256:26547a1fdc03bacd4bae9845f43fa74b200347d726034e96e04ae8116486117c`
  (resolved 2026-08-18). That digest is the **multi-arch index**, not
  the amd64 manifest (`sha256:11a9e70f8780c37e…`) — this ADR asks dev
  and CI to pin the SAME digest, and only the index resolves for both
  an arm64 devcontainer and the amd64 fleet. The tag is retained ahead
  of the `@` for readability; the digest is what resolves. `ui`
  republishes daily off an unpinned chrome channel, so the tag alone
  would let a green commit go red the next day with no code change —
  which is the property this pin exists to remove during the soak.
  Step 3 pins `.devcontainer/devcontainer.json` to this same string and
  adds the acceptance-metric-5 tripwire over the two references. The
  form matches the sibling lane: research-hardware pins
  `ghcr.io/gophersys/hardware:latest@sha256:ad5851…` the same way.
- **`UI_CHROME` is set by the workflows.** The published image bakes
  `DENSUI_CHROME=/usr/local/bin/densui-chromium`, named before the
  `densui` → `ui` rename landed here, while `tools/ui/src/ui/probe.py`
  reads `UI_CHROME`. Section 2's "both arches resolve `ui-chromium` and
  `ENV UI_CHROME`" is therefore not yet true of the org image. Unset,
  `find_chrome()` falls through to its PATH candidate search and finds
  `/usr/bin/google-chrome-stable` anyway — it passes without proving the
  baked entry point, which is the silent-fallback failure this document
  already warns about. The workflows name the path instead, so a moved
  symlink is a loud `ProbeError`. The bridge is removed when `ui`
  exports `UI_CHROME`.
- **Steps 3 and 5 are NOT in that change.** `.devcontainer/Dockerfile`
  still builds `FROM research-ui-ci:latest`, so dev and CI drift until
  step 3: chrome `151.0.7922.137` vs `151.0.7922.169`, node `22.23.2`
  vs `24.19.0`, uv root-installed vs cloud's. `build-ci-image.yml` is
  left alive on purpose while that dependency exists — deleting it
  would freeze the image the devcontainer still consumes. Steps 3 and 5
  are one PR.

### Rollback

- The deleted files stay in git history. One revert restores them.
- The `research-ui-ci` image stays published until the section-8
  consolidation of the program (after soak, Mateo-authorized). Until
  then, one commit re-pins CI and the devcontainer to it.
- The last `base` tag (e0c6bc5 lineage) stays published as the
  program-wide rollback anchor. It is not deleted.

---

## 6. Open questions — honest

- **Q1 — the Tauri hello fixture.** The design names the test but not
  the fixture's home. Options: vendor it under the eden
  `.devcontainer` test assets, or under this repo. Its crates must be
  deterministic: committed `Cargo.lock` plus either `cargo vendor` or
  a proven registry cache. A gate that fails on crates.io weather is a
  flaky gate. Decide before the first publish.
- **Q2 — Chrome version skew across arches.** amd64 gets rolling
  `google-chrome-stable`; arm64 gets a pinned Chromium. The probe
  battery's tolerance for that skew is not defined. Define it, or pin
  the amd64 Chrome too.
- **Q3 — R3 itself.** The Debian chromium apt-pin candidate is
  unproven. Prove or narrow before the first dual-arch publish.
- **Q4 — Node 22 vs Node 24.** The root-wide pin is 22 because the old
  CI image chose 22; cloud carries 24 for `dev`. Unify on one major,
  or record why the gates stay on 22.
- **Q5 — `ui-runner` day-1 need.** The tree defines it. Confirm which
  research-ui jobs need a runner image rather than a `container:` job
  before building it.
- **Q6 — cloud size (R4 upstream).** Cloud's two estimates disagree
  (3.0 vs 4.4–4.8 GB). If cloud misses its 4 GB gate, the ui totals
  move with it. The budget decision returns to Mateo; the gate does
  not move quietly.
