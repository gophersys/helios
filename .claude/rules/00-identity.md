# .devcontainer — identity and conventions

`gophersys/eden` uses this repository (`gophersys/.devcontainer`) as a shared
submodule at `.devcontainer/`. Its role is to supply the container images. Eden
uses the images for local development (the VS Code devcontainer) and as the CI
runtime the ARC pools run.

**The consumer is Eden, and `brain` is a name that no longer resolves.** This
document named a `brain` parent in 7 places, and 2 verbs of `ctl.sh` shelled out
to `$(superproject)/.claude/scripts/`. That directory does not exist in Eden, so
both verbs failed at every invocation. The verbs are deleted and the name is
corrected in the same change, because a dead path and a dead name are 1 defect:
text that describes a layout nobody checked.

## Purpose

- It is the single source of truth for the canonical container images.
- It keeps the local development environment and the CI environment identical,
  byte for byte.
- It gives you 1 place to change a toolchain version. You make the change
  exactly once. Eden takes the change when it moves its submodule pointer.

## Image model

The repository supplies 5 **devcontainer** images. Every one of them sets the
`GOPHERSYS_DEVCONTAINER` environment marker, so a script can detect the image
that it runs inside.

| Image | `GOPHERSYS_DEVCONTAINER` | Intent |
|---|---|---|
| `ghcr.io/gophersys/base`          | `base`          | Everything that most projects need: shells (zsh+oh-my-zsh), git/gh, languages (Node LTS, Python 3.12, Go, Rust), infra CLIs (kubectl/helm/k9s/tailscale/docker-cli/docker-compose/bw/nats), desktop libs (Tauri/GTK/webkit), USB/BLE libs (libusb, libudev, libbluetooth, bluez), data clients (psql, sqlite3, redis-cli), parsing (jq, yq, httpie, rg, fd, bat), QA (shellcheck, hadolint). |
| `ghcr.io/gophersys/flutter`       | `flutter`       | Base + OpenJDK 21 + Android cmdline-tools/platform/build-tools + Flutter stable SDK. |
| `ghcr.io/gophersys/zephyr`        | `zephyr`        | Base + device-tree-compiler/ninja/ccache + west in an isolated venv + Zephyr SDK (arm-zephyr-eabi + riscv64-zephyr-elf by default) + udev rules for common dev boards. |
| `ghcr.io/gophersys/zephyr-devbox` | `zephyr-devbox` | Zephyr + sshd (key-auth only, persistent host keys under /etc/ssh/hostkeys) + openocd/stlink-tools/picocom/gdb-multiarch + esptool in an isolated venv + all Espressif Xtensa SDK toolchains + CP210x/CH340 udev rules + clangd and code-server on `:8443` (browser VS Code, `EXPOSE 8443`, the clangd extension seeded into `/opt/code-server-extensions` at build time). It is an embedded development box for a k8s pod. It has 2 access paths: SSH as `dev`, and the browser at `:8443`. |
| `ghcr.io/gophersys/cloud`         | `cloud`         | The successor image of the consolidation program (ledger #94), ADDITIVE today: the reduced base (no clang/cmake, no desktop/Tauri libs, no USB-BLE libs, no Rust, no ansible + oci-cli, no speedtest-cli/ncat/net-tools, Go caches removed — terraform and the AWS CLI are NOT in this list, because they left `base` itself and are ready components nothing installs; db clients and the comfort TUIs are not in it either, because cloud re-adds them through `_delta/components/`) + delve/buf/grpcurl + the CI fold (Actions runner, cictl, claude/omp/codex at the versions.env pins). ONE image for dev and CI: the default command is zsh, and a CI pod overrides the command to `/home/runner/run.sh`. Every pin lives in `versions.env` at the repository root — the same 1 home `base` reads since the 2 Dockerfile mechanisms collapsed onto it; the build feeds it in as generated `--build-arg`s, and `_delta/components/*.sh` install the folded tool groups. Its smoke gates publish (build → smoke → push) and enforces the ≤ 5.75 GB size budget (raised from 5.5 GB by Mateo, 2026-08-16: the measured floor after the R4 levers with every tool kept is ~5.63–5.67 GB). |

## Structure

```
.devcontainer/
├── README.md
├── project.json                 # repo-level Nx wiring
├── ctl.sh                       # repo-wide control
├── versions.env                 # the ONE pin home of base and cloud
├── _ctl/lib.sh                  # the shared ctl library — every verb body, 1 time
├── _ctl/tests/                  # hermetic *.test.sh + harness + docker stub + fixtures
├── .claude/rules/00-identity.md # (this file)
├── docs/                        # PROPOSALS for images that do not exist yet — see docs/README.md
├── _build/                      # COPYed into base and cloud, above their first download
│   ├── fetch-verified.sh        # the ONE verifier every image download goes through
│   ├── download-exemptions.txt  # the downloads that take a stated class instead of a digest
│   ├── upstreams.txt            # where the next value of every pin comes from
│   └── resolve-upstream.sh      # the weekly resolver: 1 function per datasource
├── _delta/components/           # 1 file per folded tool group; cloud COPYs them and runs them
├── .ci/                         # the CI layer — .ci/README.md lists every file
│   ├── affected.sh              # which images this commit changes — 1 home for the answer
│   ├── buildx-node.sh           # the builder every image build uses; owns the arm64 switch
│   └── mirror-buildkit.sh       # keeps ghcr.io holding the BuildKit index the builder boots from
├── base/          { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── cloud/         { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── runner/        { Dockerfile, project.json, ctl.sh }   # RETIRED — nothing builds it, deletion pending
├── flutter/       { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── zephyr/        { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── zephyr-devbox/ { devcontainer.json, Dockerfile, project.json, ctl.sh, devbox-entrypoint.sh }
└── .github/workflows/
    ├── build-and-push.yml    # publish the images
    ├── security-nightly.yml  # the nightly trivy scan + the base-OS currency probe
    ├── weekly-bumps.yml      # the weekly upstream resolution + the 1 bump pull request
    ├── validate.yml          # the pull request gate: ctl.sh validate + ctl.sh test + BUILD_ORDER
    └── pr-review.yml         # the review agent, shared from gophersys/cictl
```

## Conventions

1. **This repository has no Nx workspace of its own.** You must be able to run
   every operation as plain `bash ./ctl.sh <cmd>` from within this repository.
2. **Per-image file rule.** Each devcontainer image directory at the repository
   root (`base/`, `cloud/`, `flutter/`, `zephyr/`, `zephyr-devbox/`) contains
   `devcontainer.json` + `Dockerfile` + `project.json` + `ctl.sh`. It also
   contains each script that the image COPYs in, for example an entrypoint.
   `validate` runs `shellcheck -x -S style` on every shell script in the
   repository — found by `*.sh` name **or** by a shell shebang on the first
   line, so a script with no extension is linted too. A new script is therefore
   linted wherever you put it. Do not write a README for an image. The output
   of `bash ./ctl.sh help` is the specification.

   **A per-image `ctl.sh` is a thin dispatcher.** The body of each verb is in
   `_ctl/lib.sh`, 1 time only. The per-image script sets its data
   (`IMAGE_NAME`, and any build argument), it sources the library, and it
   sends the verb to `image_main`. Never copy a verb body into an image
   directory. Add the verb to the library, and every image has it.
   `_ctl/` is not an image directory. The leading underscore says so, and it
   follows `gophersys/libs`, which uses `go/_ctl/lib.sh` for the same purpose.
   An image that adds a verb of its own handles that verb first, then sends
   every other verb to `image_main`. `base/ctl.sh` does this for the
   devcontainer lifecycle verbs.

   **`runner/` was the 1 exception, and it is RETIRED.** See "The `+ runner`
   layer is retired" below. The directory is still on disk and nothing builds
   it: it left `BUILD_ORDER`, so no loop of `ctl.sh` — `validate`'s hadolint
   pass included — reaches its Dockerfile any more. `image_dir()` still maps
   `*-runner` to `runner/` in both control scripts, because those 2 functions
   must agree whatever the set holds.

   **"Nothing builds it" is not "nothing reaches it".** `runner/Dockerfile` is
   still 1 of the 5 `PIN_VALUE_HOMES` in `_ctl/lib.sh`, so `bump_pin` writes
   into it every Monday; it is 1 of the 6 `GOVERNED_DOCKERFILES` in
   `_build/resolve-upstream.sh`; `_build/upstreams.txt` carries its
   `RUNNER_VERSION` row and `_build/download-exemptions.txt` carries its
   claude-installer row; and 5 test files hold `runner/Dockerfile`,
   `runner/ctl.sh` or `runner/project.json` as a literal. Deleting the
   directory is scheduled with the consolidation wave and not with this docs
   sweep, and that list is the real cost: the deletion edits every file above
   in 1 change, and it is not a `git rm`.

   **Those 2 lists hold different members, and now different lengths.** Read
   each list, never a count beside it. `PIN_VALUE_HOMES` is 5 since
   `base/Dockerfile` went value-less — `versions.env` plus the 4 Dockerfiles
   that still spell their own pins. `GOVERNED_DOCKERFILES` is still 6 and holds
   `base/Dockerfile` AND `cloud/Dockerfile`, because a governed file is one that
   FETCHES and base still fetches every download it always did. It stopped
   declaring the VALUES, not the URLs.
3. **Do not add a `CLAUDE.md` file.** The conventions of this repository stay
   here, in `.claude/rules/`.
4. **A human writes the text.** Do not put an AI or LLM attribution of any kind
   in a commit, in a comment or in a document.

## Nx caching

**No target of this repository caches, and `"cache": false` is the invariant.**
The `"//"` key on each target carries the same statement where the reader who is
tempted to flip it back will be standing. A `//` line comment is not available:
`ctl.sh validate` runs `jq empty` over the root `project.json`, and `jq` rejects
a comment that Nx's own parser would accept. `"//"` is legal JSON, and Nx's
project schema sets no `additionalProperties: false` at either level, so the key
survives both readers.

**`.ci/project.json` is jq-parsed by nothing.** `validate` reads
`*/project.json` for each name in `BUILD_ORDER` plus the root file, and `.ci/`
is in neither set — so that file is held to the `"//"` convention by hand and
not by the gate. Widening the jq pass to reach it is open work.

The reason is a property of the verbs, not a preference. `validate` and `test`
DISCOVER their file set at runtime: `shell_scripts()` in `ctl.sh` walks the whole
tree with `find` and takes a file by its `*.sh` name **or** by a shell shebang on
its first line, and `cmd_test` globs `_ctl/tests/*.test.sh` and lets each file
read whatever it judges. No static `inputs` list can be TRUE by construction
against a rule of that shape — "every file whose first line is a shebang" is not
a glob.

It was not true in fact either. The list that stood on the root `validate` target
named 8 globs and missed **32 tracked files the verb reads**, measured on
2026-08-17 against the 70 files `validate` shellchecks: all 12
`_delta/components/*.sh`, both `_build/*.sh`, `zephyr-devbox/devbox-entrypoint.sh`,
and the 17 extensionless shebang stubs under `_ctl/tests/stubs/`.
`.ci/project.json` repeated the fault with 9 globs of its own, and that target
only delegates to the root verb, so it inherits the discovery it cannot enumerate.
Every `*/devcontainer.json` joined the missed set the day `validate` started
reading them.

**A cache key that under-counts its inputs replays a green that checked nothing.**
Edit a component script, and Nx would have served the previous result: the gate
reports OK having read no changed file. That is the FAIL-NOT-SKIP failure one
layer up — a check that is believed and did not run.

Restoring `"cache": true` on a target needs the inputs list PROVEN complete
against what the verb reads, and the proof has to survive the next file somebody
adds. For these 2 verbs it cannot, because the verb answers "what is a shell
script" itself. Nothing here is slow enough for the cache to be worth a false
green: the whole gate is a lint pass and a bash suite.

## ARGs-at-top + latest-LTS convention

Every Dockerfile MUST declare all tool versions as `ARG`s at the top of the
file. **In `base/Dockerfile` and `cloud/Dockerfile` those ARGs are VALUE-LESS:
the value lives in `versions.env`, the ONE pin home, and arrives as a generated
`--build-arg`.** Each `versions.env` row carries the
`# latest LTS as of YYYY-MM-DD` comment — the date belongs beside the value it
dates, not beside a declaration that holds none.

**There were 2 mechanisms until this collapse, and now there is 1.**
`base/Dockerfile` carried 55 inline `ARG NAME=value` pins — measured
2026-08-17 — and 54 of them were spelled in `versions.env` as well, at equal
values; `_ctl/tests/pin-mirroring.test.sh` existed only to hold the 2 copies to
1 value. The rule did not die whole: 3 pins are still dual-home
(`versions.env` and the retired `runner/Dockerfile`), and
`_ctl/tests/runner-residue-mirroring.test.sh` keeps the mirror for exactly
those until runner/'s deletion wave removes the second home. The 55th was
`RUST_CHANNEL`, which `cloud` does not install and which
is a `versions.env` row now like the rest. Everything downstream paid for the
split: 6 pin homes, a family branch in `.ci/smoke.sh`, an admitted over-build in
`.ci/affected.sh`. It is 1 mechanism now, and the doubling that dual-arch would
have done to it is a doubling of 1 file.

**The 3 per-image Dockerfiles still carry inline pins, and that is the open
half.** `flutter/`, `zephyr/` and `zephyr-devbox/` declare their own
`ARG NAME=value` blocks and consume no build arg from `versions.env`; `runner/`
does the same and is retired. Read "the pin value is in `versions.env`" as true
of `base` and `cloud`, and of nothing else.

**What closed is the CLASSIFICATION half, and it closed alone.** That sentence
went on to say those pins "are the ones no smoke run compares". They are
compared now: `.ci/smoke.sh` reads a child image's own Dockerfile as a SECOND
pin home beside `versions.env`, with a class table of its own, and the
refuse-to-run rule for an unclassified pin covers both homes equally. The reader
takes every VALUE-FUL `ARG` — 19 of them across the 3 files, `BASE_TAG` and the
3 digest rows included, because an ARG that carries a value and no class is the
silence the rule exists to break — and 6 of them name a tool that reports its
own version: `JAVA_VERSION`, `FLUTTER_VERSION`, `WEST_VERSION`,
`ZEPHYR_SDK_VERSION`, `ESPTOOL_VERSION` and `CODE_SERVER_VERSION`.
The rest are a build id, an API level, a channel or a toolchain list, and each
one says so in its row's neighbourhood. **The VALUE home did not move**: these
files still spell their own pins and `bump_pin` still writes into all 4 of them,
so `PIN_VALUE_HOMES` is still 5 and ledger #102 stays open on that half.

- **To change a version**, edit 1 `versions.env` row and its date comment.
  Change nothing else. The Dockerfile is not a home and takes no edit.
- **A hardcoded version in a RUN line is forbidden.** `ctl.sh validate`
  searches for `=\d+\.\d+\.\d+` in a RUN line and fails the build.
- **A value-less ARG needs a gate, or it fails silently.** An unfed pin expands
  to the empty string, and the failure surfaces much later as a mangled download
  URL. Both root Dockerfiles therefore open with a `RUN : "${PIN:?not in
  versions.env}"` chain that stops the build naming the variable — 54 entries in
  `base`, 55 in `cloud`. `UBUNTU_BASE_REF` is deliberately outside both chains:
  the `FROM` consumes it first and an absent value dies there.
- **A build parameter is not a pin and keeps its value.** `USERNAME`,
  `USER_UID`, `USER_GID` and `OH_MY_ZSH_INSTALL_URL` stay inline in both files:
  no upstream publishes a uid, so no row in `versions.env` and no row in
  `_build/upstreams.txt` could answer for one.
- **`${USERNAME}` in a RUN under a zsh SHELL is not the ARG, and `validate` now
  fails on it.** zsh sets `USERNAME` itself — a special parameter tied to the
  EFFECTIVE user, overwritten at shell startup whatever the environment held —
  and Docker hands a RUN line to the shell rather than expanding it. So under
  `SHELL ["/usr/bin/zsh", ...]` a `chown ${USERNAME}` means the uid of the
  layer, and in a root layer it silently means `chown root`. The failure never
  shows at build time: `flutter/Dockerfile` chowned `/opt/flutter` and
  `/opt/android-sdk` that way, both shipped root-owned, and
  `flutter --version` as `dev` exited 128 with "detected dubious ownership" —
  found by the first smoke run that ever executed it. `zsh_username_run_references`
  in `ctl.sh` reports every RUN line holding `${USERNAME}` or `$USERNAME` AFTER
  the file switches SHELL to zsh, naming the file and the line; a reference
  BEFORE the switch passes, and an `ENV`, a `USER` or a `LABEL` is never
  reported, because the Dockerfile PARSER expands those out of the build args
  and no shell is involved. `base` and `cloud` had 9 and 5 such RUN lines, and
  they are the literal `dev` now — the pattern the 3 child Dockerfiles already
  document in their own headers. Both files still DECLARE `ARG USERNAME=dev`,
  because `ENV`, `USER` and the pre-switch RUN still read it, so the 2 DL3064
  inline ignores stay too. **The detector's trigger is the SHELL line in the
  file it reads.** A child Dockerfile INHERITS zsh through its `FROM` and
  declares no SHELL of its own, so this reader is silent on all 3 of them;
  all 3 hardcode `dev` today, and closing the hole means resolving the `FROM`
  graph in `ctl.sh`.
- To add a new tool, select its **latest LTS or stable** release. Do the
  research with apt-cache, with the upstream GitHub releases, or with pypi.
  Never invent a version.
- **You must get approval to change a version.** A change to a `versions.env`
  row needs Mateo's approval on the pull request. It reaches every image below
  this one in the graph, and the ARC pools run `cloud`.
- **A digest row takes the same shape as a version row, and sits beside it.**
  Every binary download compares its bytes against a `<TOOL>_SHA256_<ARCH>`
  declared in the SAME home as `<TOOL>_VERSION`: a `versions.env` row for `base`
  and `cloud`, an `ARG` at the top of the Dockerfile for the 3 per-image
  Dockerfiles that have not moved yet. The reason is that a bump is then 2
  adjacent lines: 2 homes apart, and the bump misses one. That failure is now
  impossible for `base` and `cloud`, because they have 1 home between them.
- **The vocabulary is `_SHA256_AMD64` and `_SHA256_NOARCH`, and nothing else.**
  It names the PLATFORM and never the upstream asset spelling — compose writes
  `x86_64` and buildx writes `amd64` for the same platform, and following the
  asset gave 2 vocabularies for 1 arch. `_NOARCH` is for an asset that serves
  every platform. There is no `_ARM64` row while `SANCTIONED_PLATFORMS` is
  `linux/amd64` alone: a digest that nothing compares is a check that cannot
  fail. Widening the platform set restores the `linux/arm64)` case arm and the
  `_ARM64` row together — and the row is written ONCE now, in `versions.env`,
  for both root images. Collapsing the mechanism before the arch axis widened is
  why: 2 homes × 2 arches is the multiplication this repository does not pay.
- **Every digest row records where its value came from**, machine-readably:
  `# upstream-published: <checksum file url>` when the release ships a checksum
  file and the 2 agreed, otherwise `# computed-at-pin: <yyyy-mm-dd>` — TLS plus
  an immutable release URL is then the whole evidence, and the row says so. A
  number a reviewer has to take on faith is not a pin.
- **The download itself goes through `_build/fetch-verified.sh`.** It is 1 file
  by the same rule that puts a verb body in `_ctl/lib.sh` once. `base` and
  `cloud` COPY `_build/` to `/usr/local/lib/gophersys/` above their first
  download; `flutter`, `zephyr` and `zephyr-devbox` inherit it
  through their `FROM` and add no COPY. **Because base COPYs it, base's docker
  build context is the repository root and not `base/`** — `base/ctl.sh` sets
  `IMAGE_BUILD_CONTEXT`, and both copies of `build-and-push.yml` say
  `context: .` for the base job. A download that can carry no digest takes 1 row
  in `_build/download-exemptions.txt` naming a stated class and a reason.
  `_ctl/tests/download-coverage.test.sh` reads what the files CONSUME and holds
  both directions: an unanswered download is red, and so is a row for a
  download that no longer exists.
- **`HADOLINT_VERSION` in `versions.env` also governs the gate.**
  hadolint's verdict depends on its version — 2.15.1 raises DL3064 and DL3066 on
  Dockerfiles that 2.14.0 passes — so `validate` lints at that exact pin.
  `hadolint_pin` in `ctl.sh` read it out of the `base/Dockerfile` ARG until that
  ARG went value-less; the read FAILED naming the pin rather than falling back
  to whatever the host held, which is how a gate is supposed to lose its
  input. It uses
  the `hadolint` on PATH when the version matches, otherwise
  `hadolint/hadolint:v<pin>` through docker, and it FAILS naming the version when
  it can reach neither. The devcontainer ships the pinned version, so a developer
  and CI get the same verdict. Raising the pin is a version change like any
  other, and it may turn new findings red.

## The base OS is pinned by digest

`base/Dockerfile` and `cloud/Dockerfile` build `FROM ubuntu:24.04@${UBUNTU_BASE_REF}`.
The other 4 Dockerfiles build from an image of this repository, so they inherit
the pin instead of repeating it.

The reason is the property the whole repository rests on: **the commit decides
the image.** Under the moving tag, 2 builds of 1 commit produce 2 different
operating systems, and `verify-published` cannot say which one it read.

- **`UBUNTU_BASE_REF` has 1 pin home and 1 value**: the `versions.env` row. It
  had 2 — that row and the `ARG` block of `base/Dockerfile` — and a test held
  the 2 to the same `sha256:`. Both Dockerfiles declare
  `ARG UBUNTU_BASE_REF` value-less and take the digest as a generated
  `--build-arg`, so the rule that needed a test is now a property of the tree.
  Hold the row itself to 64 hex characters: a truncated digest reads as correct
  in a diff and dies at `docker build`, after the merge.
- **The ARG is declared ABOVE the `FROM`.** A `FROM` can interpolate only an ARG
  declared before it. Below it the expansion is the empty string, the `FROM`
  becomes `ubuntu:24.04@`, and the build dies in the publish job. That is also
  why this 1 pin is outside the pin gate: the `FROM` consumes it before the gate
  runs, so an absent value fails there and not 50 lines later.
- **Take the INDEX digest, never a per-platform one.** Resolve it with
  `docker buildx imagetools inspect ubuntu:24.04 --format '{{.Manifest.Digest}}'`,
  which reports the digest of the manifest LIST. buildx still has to choose the
  manifest for the platform it builds; a per-platform digest takes that choice
  away and pins the wrong thing. The pin of 2026-08-16 was read that way and its
  `MediaType` was `application/vnd.oci.image.index.v1+json`.
- **The bump path** is a pull request like any other: read the new digest with
  the command above, write it into the 1 pin home with a dated comment, and let
  the build → smoke → push order settle it. Never a nightly republish — that
  would move `:latest` with no commit behind it.
- **A pin that nothing watches is a snapshot that looks current forever**, so the
  currency reader ships with it. `bash ./ctl.sh base-currency` asks the registry
  what the tag holds NOW and fails naming BOTH digests when it differs. The body
  is `require_base_image_current` in `_ctl/lib.sh`, and the nightly runs it every
  night, so a moved ubuntu digest arrives as an issue rather than as silence.

## Scheduled security scan

`.github/workflows/security-nightly.yml` scans the 5 published images at
`:latest` every night at 09:00 UTC — 02:00 MST, and cron is UTC — and runs the
base-OS currency probe above. It builds and publishes nothing.

- **The matrix is BOUNDED.** It runs on `arc-build`, which has 6 slots that
  every repository's builds share, so `max-parallel: 3` keeps a nightly from
  taking the whole pool. Nobody is waiting for it at 02:00 MST.
  `_ctl/tests/scheduled-workflows.test.sh` holds the rule on the TRIGGER: a
  scheduled workflow with a matrix declares `max-parallel`, so tomorrow's is
  covered the day it is added.

- **CRITICAL fails the run, fixed or unfixed.** The scan sets
  `--severity CRITICAL --exit-code 1` and **no `--ignore-unfixed`**. HIGH is not
  gated: its count on these images is unmeasured, and a gate that is red every
  morning teaches the reader to ignore red. The measurement is 1
  `workflow_dispatch` run at `HIGH,CRITICAL`.
- **An unfixed CRITICAL becomes a waiver, never a skip.** Waivers live in
  `.ci/trivyignore.yaml`. Each entry carries 4 fields: trivy's own `id`,
  `statement` (WHY it is accepted) and `expired_at` (`yyyy-mm-dd`), and `paths`.
  Trivy enforces the expiry itself, so a dated waiver reopens on its own.
  `_ctl/tests/scheduled-workflows.test.sh` fails an entry missing 1 of the first
  3. **`paths` is the 4th field and no test holds it**, so it is a rule the
  waiver file states and a reader must obey by hand: a bare id waives the
  finding in every file of every image, and `CVE-2025-68121` alone would have
  covered gitleaks AND yq AND k9s AND any binary added tomorrow. The scan must
  NAME the file with `--ignorefile`: trivy's YAML ignore file is experimental
  and is loaded only when its path is given, so an unnamed waiver file is dead
  text.
- **Read the file, never a count in this document.** An earlier version of this
  sentence said the file "is EMPTY at merge". It has not been empty for some
  time, and a maintainer taking that sentence at its word would believe the scan
  accepts zero CVEs. The file holds 6 `vulnerabilities:` entries and 1
  `secrets:` entry today, every one expiring 2026-11-30 — so all 7 reopen in 1
  night rather than in a stagger, which the November review must plan for. The
  standing rule is the invariant, not the length: an entry is a visible diff
  line, it carries all 4 fields, and its expiry is a date.
- **A scheduled run has no author watching it.** Every workflow that runs
  `on: schedule` therefore calls `.ci/notify-failure.sh` from a step guarded by
  `if: ${{ failure() }}` and declares `issues: write`. That script opens or
  updates ONE issue naming the run URL and the jobs that failed, and a green run
  closes EVERY open issue carrying that label — 2 can exist whenever 2 runs
  raced past the search, and one that a green run cannot reach stays red for the
  life of the repository. The rule in the test file is keyed on the TRIGGER, so
  a scheduled workflow added tomorrow is covered the day it is added.
- **The label is a PARAMETER, and each scheduled run owns one.** `ISSUE_LABEL`
  defaults to `ci-nightly-red`, so the scan keeps its behaviour with no edit;
  the weekly bump passes `ci-weekly-red`. With the label hardcoded, a green
  Monday closed the issue the nightly opened about a CRITICAL CVE and a red
  Monday commented on it, and both read as the SCAN changing state.
- **`failure()` in a step means "a step of THIS job failed".** The notify job
  runs under `if: ${{ !cancelled() }}`, so it first reduces the verdict of the
  jobs it needs to its own status. Without that step the notifier would be
  skipped exactly when it is needed. `always()` is the other accepted spelling
  and the test takes either; `!cancelled()` is the one this repository uses,
  because under `always()` a run a human CANCELLED reduces to a non-success
  verdict and files an issue about itself.

## Weekly upstream bumps

`.github/workflows/weekly-bumps.yml` runs at 10:00 UTC on Monday — 03:00 MST,
1 hour after the nightly's window so the 2 scheduled runs never race — and on
`workflow_dispatch`. It resolves every pin, writes each one that moved into
EVERY home of that pin, and opens ONE pull request. It merges nothing.

**A pin nobody watches is a snapshot that looks maintained.** `ZSH_VERSION=5.9`
carried `# latest LTS as of 2026-04-19` for 4 months, and that comment records
the day somebody looked, not the day the value was current. The nightly scan
reports a CVE in an image; it cannot report that a pin is 3 releases behind,
because until this table no file in this repository knew what the current
release was.

- **`_build/upstreams.txt` says where the next value of every pin comes from.**
  4 fields, the grammar of its neighbour `download-exemptions.txt`:
  `<pin>|<datasource>|<coordinate>|<policy or reason>`. Every pin of the value
  homes carries exactly 1 row, and every row names a pin that exists —
  `_ctl/tests/upstream-coverage.test.sh` holds both directions, reading the pins
  out of the HOMES and never out of the table, because a rule that reads the
  listing goes on reporting coverage after the pin it covers was renamed.
- **12 datasources, and the 12th resolves nothing.** `github-release`, `pypi`,
  `npm`, `apt`, `go-dl`, `node-dist`, `oci-index`, `k8s-dl`, `tailscale-pkgs`,
  `flutter-releases` and `eden-manifest` each read 1 upstream DOCUMENT;
  `no-autobump` states, in a sentence, why a pin is not resolved. 13 pins take
  it today: the 3 `ANDROID_*` rows, `PYTHON_PACKAGE`,
  `JAVA_VERSION`, `RUST_CHANNEL`, `FLUTTER_CHANNEL`, `BENCHSTAT_REF`,
  `TERRAFORM_VERSION`, `AWS_CLI_VERSION`, `CICTL_VERSION`, `HNSLINT_VERSION`
  and `BW_VERSION`. The 3 harness pins left the set on 2026-08-17, when
  `EDEN_MANIFEST_READ` was minted and their rows became `eden-manifest`. A reason under 20 characters or with no space in it is a
  placeholder and the test names it: `n/a` passes every non-empty check, and it
  is a pin nobody decided about wearing the label of a pin somebody did.
- **A reason has to be TRUE, and no static check can tell.** 3 rows were
  corrected after their coordinates were measured against the real upstreams,
  and the suite was green on all 3 before and after — a stub upstream answers
  any coordinate. `cictl` and `hnslint` are ours and publish TAGS and no GitHub
  Releases, so `releases/latest` was a 404 forever while the pin sat 4 releases
  behind; `bitwarden/clients` ships browser, desktop, web and cli under one
  release stream, so the newest release of the repository is not the newest
  release of the CLI and the asset URL 404s; and the android index this file
  claimed did not exist is `repository2-3.xml`, 408907 bytes of it. All 3 are
  `no-autobump` with the true reason. **Measure a coordinate against the real
  API before you write its row.**
- **The digest is of the asset for the version this run resolved.** There are 3
  HTTP reads per digested pin — the index, the digest, the re-proof — so the
  property is not "one fetch". `_build/resolve-upstream.sh <PIN>` prints
  `<version>|<sha256>`, where the URL is read out of the file that performs the
  download and never out of the table (a second URL home lets a correct digest
  be computed of the wrong asset), and the value is then handed back to
  `_build/fetch-verified.sh`, which fetches that same URL again and compares
  before a line is written. A version that moves while its digest stays cannot
  reach the branch.
- **An aggregate run COLLECTS, then fails.** `--dry-run` and `--apply` resolve
  every row, report every mover AND every failing pin, write nothing, and exit
  non-zero if anything failed. Abort-at-the-first-failure would let 1 dead
  coordinate hide the bumps behind it, and a run that reports nothing reads like
  a quiet week. The mechanism is `capture` in the resolver, which reads the
  status of each command substitution itself: bash UNSETS errexit inside `$( )`
  before 4.4, and `set -Eeuo pipefail` alone let a failed fetch return an empty
  string that was then reported as `bump: PIN 2.3.0 -> ` at exit 0.
  `shopt -s inherit_errexit` is also set where the shell has it, but nothing
  depends on it — the mac's bash 3.2 runs the same gate.
- **The version is spelled the way the pin is spelled.** A leading `v` is kept
  when the pin carries one (`cictl` pins `v0.1.0`) and dropped when it does not;
  `go1.26.5` and `bun-v1.3.14` lose their word prefix the same way. An apt
  version drops the epoch and the debian revision, because `5.9` is what the
  tool reports about itself and what the smoke test compares.
- **`bump_pin` in `_ctl/lib.sh` is the only writer**, and it edits every home of
  the pin: the version row, the digest row beside it and that row's evidence
  comment, and no other line. It DISCOVERS the homes through `homes_of` rather
  than assuming any of them, which is why dropping `base/Dockerfile` from
  `PIN_VALUE_HOMES` changed nothing about it: a pin of `versions.env` alone now
  has 1 home, and the writer edits the 1 it finds. The multi-home path is still
  live for the 4 per-image Dockerfiles.
- **The pull request is opened, never merged.** `--dry-run` composes it and
  writes nothing TO THE REPOSITORY — it still writes temporary files and
  downloads every moved asset twice; `--apply` writes and leaves git and gh to
  the workflow. The workflow is 2 jobs, the nightly's shape: a job TIMEOUT
  cancels the job, `if: failure()` steps inside it never run, and the notify job
  under `!cancelled()` is what reports the one failure a download budget makes
  likely.
  **The pull request arrives with NO checks**: GitHub starts no workflow run for
  an event a `GITHUB_TOKEN` caused, so `validate.yml` does not fire on it. Close
  and reopen the pull request, or push to its branch, before merging — the
  workflow says so in its own log. That paragraph is history now: the pull
  request is created with `BUMP_PR_TOKEN`, a fine-grained PAT, so its checks
  fire on their own and the close-reopen step is gone. What stays human is
  the MERGE.
- **The 3 harness pins mirror eden through `eden-manifest`.**
  `CLAUDE_CODE_VERSION`, `OMP_VERSION` and `CODEX_VERSION` MUST match eden
  `harnesses/versions.env`, and eden's `harness-upgrade-check` is the one
  decision point for them — the weekly MIRRORS that file, it never leads it.
  `gophersys/eden` is private and this repository's `GITHUB_TOKEN` is
  repository-scoped, so the read uses `EDEN_MANIFEST_READ`, a fine-grained PAT
  with `contents:read` on that one repository (minted 2026-08-17). With the
  secret absent the resolver FAILS naming the pin and the secret, and never
  reports the current value as current — a missing credential is a red
  Monday, not a quiet one.

## Sanctioned-platform policy

Every image of this repository publishes **1** platform: `linux/amd64`. The
declaration is `SANCTIONED_PLATFORMS` in `_ctl/lib.sh`, and it is the only place
a platform is named. A platform outside that set fails the guard and names
itself.

**An image builds only the arch it deploys to.** Each narrowing was measured, not
assumed:

- `base-runner` ran only as an ARC pod, and every node in that cluster is amd64.
  Its arm64 half compiled Go under QEMU for an architecture that no node runs,
  and it took ~13 minutes on a thin layer. The image is retired; the measurement
  is kept because it is half of why the set narrowed.
- `zephyr-devbox` runs only as a kubernetes pod (commit `c7e8e94`). Its 3 running
  pods sat on `k3s-w-1`, `k3s-w-3` and `k3s-w-4`, and all 3 are amd64. Nobody
  opens it locally; `zephyr` is the image for that.
- `base`, `flutter` and `zephyr` were published for 2 architectures until the
  arm64 half was measured: the published `base` arm64 variant was an amd64 Ubuntu
  userland carrying aarch64 Go binaries, because the `FROM` line pinned the
  userland to the BUILD host while buildx labelled the result with the TARGET.
  So it was mislabelled rather than native, and on the only host that would
  consume it Docker Desktop emulates that userland anyway. It gave none of the
  benefit of a native image and cost the larger half of a 41.7-minute build.

**No arm64 consumer can be verified for any image today**, which is recorded in
gophersys/infrastructure `docs/debt-register.md` D42. Widen
`SANCTIONED_PLATFORMS` on the day a consumer exists, and not before.

**Widening it is not 1 edit.** Each shell path reads the list from that 1
declaration, and `.ci/smoke.sh` selects a platform out of it rather than refusing
a list of more than 1. But 3 other places STATE the same policy, and they must
move with it: `PLATFORMS` in `.github/workflows/build-and-push.yml`, the same key
in its provider copy, and the literal `SANCTIONED` in
`_ctl/tests/platform-policy.test.sh`. That literal is deliberate — a test that
reads the value it checks agrees with any value, a wrong one included. The
`build` verb also refuses a list of more than 1 entry, because `docker build`
makes 1 image, so the local loop must name the 1 platform it wants. Measured on
2026-08-13: 1 edit to `_ctl/lib.sh`, and nothing else, made 8 checks red in 4
test files — `build` 3, `guard` 1, `platform-policy` 2, `verify-published` 2. The
per-file counts are here because the first version of this sentence said 11,
which is the TOTAL check count of `guard.test.sh` read as its failure count.

Verify a published image with `bash ./ctl.sh verify-published <image> [tag]`. A
manifest declares a platform; that verb reads the manifest back out of the
registry and asserts the set is exactly the sanctioned one. An `unknown/unknown`
entry is an attestation manifest, which buildx attaches 1 of per variant, and it
is not a variant. For the deeper check — the manifest declares a platform, but
what is in the layers — `bash ctl.sh verify-image-arch <ref> [platforms]` in
gophersys/infrastructure reads the content.

| Verb | Scope | Platform |
|---|---|---|
| `build` | local dev loop | explicit `--platform`, 1 platform, no push |
| `push` | publish | **GUARDED** buildx build + push |
| `verify-published` | after a publish | reads the manifest the registry holds |

The guard `require_buildx_and_platforms` is in `_ctl/lib.sh`, 1 time only, and it
runs at the start of every per-image `push`. It fails closed in 5 conditions: a
platform outside the sanctioned set, an empty platform list, buildx absent, no
buildx builder active, or the active builder unable to build 1 of the required
platforms. The first condition is `require_sanctioned_platforms`, which `build`
also uses.

The list of platforms an image builds is `IMAGE_PLATFORMS`, which defaults to
`SANCTIONED_PLATFORMS` and stays overridable from the environment. An image may
declare a measured NARROWER list; it may not declare a wider one, because every
entry still has to be sanctioned. `IMAGE_PLATFORMS` was called
`MULTI_ARCH_PLATFORMS` until the arm64 drop, and a tripwire in the library fails
at source time if the old name is still set — both names would hold the same
string, so a missed rename would otherwise be silent.

The repository-root `ctl.sh` does **not** call the guard. It sends `push` to the
per-image `ctl.sh`, which calls the guard with its own list. The root script
cannot call the guard correctly, because the list is not the same for every
image. Do not add a call to the guard there.

The CI workflow enforces the same policy. It sets up buildx, builds with
`--platform ${{ env.PLATFORMS }} --push`, and then runs `verify-published`
against the SHA tag it just pushed. It sets up no QEMU: emulation is what a
cross-platform build needed, and there is no cross-platform build.

**Every** job builds **twice**, and the order is the point. The first build sets
`push: false` + `load: true`, so the image goes into the local image store and
not to ghcr.io. The smoke test then asserts the content of that loaded image.
Only then does the second build push, from the cache the first one wrote. A push
cannot be undone and no job here rolls one back, so a check that runs after the
push reports a broken image but cannot stop one from reaching a consumer.
`_ctl/tests/publish-order.test.sh` holds that order in the pull request gate, and
it fails any job that publishes without a smoke step. `load: true` takes 1
platform, so read the arm64 note at the top of that test file before you widen
`SANCTIONED_PLATFORMS`.

The smoke test compares **versions**, and it does not only run tools. `.ci/smoke.sh`
is the host driver: it classifies every pin of every home the image has as
`asserted`, `not-a-version` or `not-in-this-image`, resolves
each asserted pin, and sends
`.ci/image-checks.sh`, the `.ci/fixtures/` and the assertion table into 1 `docker
run`. The guest compares what each tool reports against its pin, and it then runs
the gate-critical tools on the fixtures — a Go module through
gofumpt/golangci-lint/hnslint/vet, a Dockerfile through hadolint, a compose file
through the compose plugin, and delve/buf/grpcurl each on 1 real operation.
`_ctl/tests/version-coverage.test.sh` fails when a pin of `versions.env` carries
no classification, so a new pin there cannot stay silent.

**2 classification TABLES read `versions.env`**, and the branch that chooses
between them is all that is left of the family split: `cloud` takes the table
that asserts the CI fold, and `base`/`flutter`/`zephyr`/`zephyr-devbox` take the
table that asserts what `base` installs. A pin one image does not carry takes
`not-in-this-image` in that image's table, which is what the class exists for.

**A CHILD image reads a second home: its own Dockerfile.** `flutter`, `zephyr`
and `zephyr-devbox` each carry a class table of their own — `PIN_CLASSES_FLUTTER`,
`PIN_CLASSES_ZEPHYR`, `PIN_CLASSES_DEVBOX` — over the value-ful `ARG`s of their
own file, and every rule of the `versions.env` home applies there unchanged: an
unclassified pin refuses the run before a container starts. `home_pin_names` in
`.ci/smoke.sh` therefore holds 2 readers again, and this pair is not the pair
that went away — the old second reader read `base/Dockerfile`, which declares no
value at all now. `CODE_SERVER_VERSION` is the pin that shows why: read on
2026-08-17, `ghcr.io/gophersys/zephyr-devbox:latest` reports code-server 4.127.0
while `zephyr-devbox/Dockerfile` pins 4.133.0, and until that table existed no
class, no test and no run in this repository could say so.

**2 things are deliberately outside the child home**, and each is named in the
driver: `runner/Dockerfile`, because nothing builds `base-runner` and no run can
name it, so a table for it would be dead text; and the pins a child inherits
from ANOTHER child — `zephyr-devbox` builds `FROM zephyr` and carries west and
the Zephyr SDK, but `WEST_VERSION` lives in `zephyr/Dockerfile`, so the devbox
run asserts esptool and code-server and not those 2. Closing that needs the
`FROM` graph walked in the driver, and it is what is left of ledger #102 beside
the value-home half.

**`not-in-this-image` is a CHECKED claim now, and it was not.** Ledger #103. The
class field of a table row takes an optional absence probe —
`not-in-this-image:<binary>[,<binary>...]` — and the guest asserts
`! command -v <binary>` for every one of them. Without it the class said the
image does not install the tool, no command ran, and a tool that leaked in read
exactly like a tool that stayed out. The leak is measured and not theoretical:
on 2026-08-17 `ghcr.io/gophersys/base:latest` carried `/usr/local/bin/terraform`
and `/usr/local/bin/aws` while `base/Dockerfile` installs neither — the
published image is older than the removal, and nothing here could report it. A
row keeps the BARE class where a probe would prove nothing, and there are
exactly 2 such rows: `RUNNER_VERSION`, because the Actions runner is at
`/home/runner/bin/Runner.Listener` and on no image's PATH, and `ANSIBLE_VERSION`,
because the `ansible` metapackage ships collections and no binary of its own. A
probe that can never fire is a check that cannot fail. The driver refuses to run
an image whose whole table names no probe at all.

## Dev-in-container expectation

Use these images for **development from inside the container**. They are not
only a CI runtime. The default `CMD` is zsh. oh-my-zsh is already installed for
the `dev` user (uid 1000, sudo-nopasswd). The working directory is
`/workspace`. This agrees with Eden's bind-mount convention.

Every image exports `GOPHERSYS_DEVCONTAINER=<image-name>`, so a development
script and a project CI job can detect the image that they run inside.

Each image directory contains a `devcontainer.json` that pins its published
image. A consuming project mounts the file at
`.devcontainer/<image>/devcontainer.json`. The VS Code command "Reopen in
Container" then lists `base`, `cloud`, `flutter`, `zephyr` and `zephyr-devbox`
as configurations that you can select — 5 files, 1 for each image. Each
configuration bind-mounts the project to `/workspace` and runs as the `dev`
user.

**`ctl.sh validate` holds every `*/devcontainer.json` to 4 properties**, and
until that pass was written these 5 files were read by NOTHING in this
repository — no verb, no test, no workflow opened one, so a typo in an image ref
reached a developer's "Reopen in Container" and nowhere earlier. The 4 are
`jq .` parses, `.image` matches `ghcr.io/gophersys/<name>:latest`,
`.remoteUser` is `dev`, `.workspaceFolder` is `/workspace` — the contract this
section states. The pass FAILS naming the file and the property, and it fails
when the glob matches zero files, because a check that opened no file is not a
check that passed. It finds the files by glob and not by `BUILD_ORDER`: `runner/`
is out of `BUILD_ORDER` and would otherwise take an unchecked `devcontainer.json`
the day somebody added one.

**`postCreateCommand` is deliberately NOT the 5th property. 1 of the 5 files
declares it, and the other 4 must not.** The property is not symmetry; it is
whether an image needs an install at create time.

- **`base` declares it**, and it is the only image whose `ctl.sh` answers a
  `post-create` verb. `base` carries no harness, so
  `base/ctl.sh post-create` installs claude, omp and codex at create time,
  pinned from the consuming repository's `harnesses/versions.env` when that file
  is mounted.
- **`cloud` must not.** It bakes the same 3 harnesses into the image through
  `_delta/components/agents.sh` at the `versions.env` pins, so an agent pod does
  zero network installs at start. Adding a post-create step would install over
  the bake on every container create.
- **`flutter`, `zephyr` and `zephyr-devbox` must not either**, and for a
  different reason: each one is a thin dispatcher that sends every verb to
  `image_main`, and `_ctl/lib.sh` has no `post-create`. A `postCreateCommand`
  in one of those 3 files would name a verb that nothing answers — the dead-path
  class this document opens with. Their toolchains are baked, which is what an
  image is for.

Adding a `postCreateCommand` to an image is therefore 2 edits and not 1: the
`devcontainer.json` line, and the verb that answers it.

You can also deploy `zephyr-devbox` as a k8s pod, connect to it over VS Code
Remote-SSH, or open it in a browser at `:8443`. Read
`zephyr-devbox/devbox-entrypoint.sh` for its full contract; sshd is the last
thing it does, and 5 operator-facing steps come first:

1. It execs any argv you supply and does nothing else. Local devcontainer use
   therefore behaves like the other layers.
2. It generates persistent ed25519 and rsa host keys into `/etc/ssh/hostkeys`,
   so the box keeps its SSH identity across pod restarts.
3. It takes `authorized_keys` from `DEVBOX_AUTHORIZED_KEYS` (a pod env, usually
   a Secret), otherwise from a mounted `/etc/devbox/authorized_keys`, otherwise
   it leaves the persistent home's file alone. With none of the 3 it reports a
   DEGRADED error: sshd boots and refuses every login.
4. It chowns and chmods the `/home/dev` and `/workspace` mountpoints, and
   deliberately NOT recursively. It then recreates `/dev/mcu-slot-1..6` from
   `/dev/serial/by-path`, because a symlink at the node's `/dev` root does not
   propagate into the pod. Slot N is guest USB port N is physical hub slot N.
5. It starts code-server as `dev` on `0.0.0.0:8443`, under a supervisor loop
   that logs and restarts every exit. **Auth is required by default.** Set
   `DEVBOX_CODE_SERVER_HASHED_PASSWORD` (code-server's own argon2
   `HASHED_PASSWORD` contract), or state
   `DEVBOX_CODE_SERVER_AUTH=none-behind-proxy` to declare that an
   authenticating proxy owns the port. With neither set, code-server does NOT
   start and the refusal names both knobs. The reason is measured, not
   theoretical: the account code-server runs as holds passwordless sudo, so a
   reachable unauthenticated `:8443` is root on the pod for any peer the network
   admits — and the network boundary is a NetworkPolicy in another repository,
   which this file cannot see and must not trust as the only wall.

**Every refusal above writes `/run/devbox-degraded` and logs ERROR, not
WARNING.** sshd still runs, because code-server is supplementary and a missing
credential must not take the primary service down. But a pod that reports
Running while a declared service is absent is the failure mode this entrypoint
used to have, so the marker file is machine-readable state a probe or an
operator can find.

## Per-image verb catalog

| Verb | Action | Cache |
|---|---|---|
| `build` | `docker build --platform "$IMAGE_PLATFORMS"` | false |
| `push` | `docker buildx build --platform "$IMAGE_PLATFORMS" --push` (guarded) | false |
| `verify-published [tag]` | read the published manifest; it must carry exactly `SANCTIONED_PLATFORMS` | false |
| `pull` | `docker pull ghcr.io/gophersys/<name>:latest` | false |
| `inspect` | `docker image inspect ghcr.io/gophersys/<name>:latest` | false |
| `help` | Print the usage block from `ctl.sh` | n/a |

## Repo-root verb catalog

| Verb | Action |
|---|---|
| `build <image>` | Delegate to per-image `ctl.sh build` |
| `push <image>` | Delegate to per-image `ctl.sh push` (guarded) |
| `verify-published <image> [tag]` | Delegate to per-image `ctl.sh verify-published` |
| `pull <image>` | Delegate to per-image `ctl.sh pull` |
| `inspect <image>` | Delegate to per-image `ctl.sh inspect` |
| `base-currency [reference]` | Assert the registry still holds the digest `UBUNTU_BASE_REF` pins |
| `list` | Print the managed image refs |
| `validate` | shellcheck every shell script, jq, the `devcontainer.json` contract, hadolint at the pinned version, ARG-discipline checks, the zsh-`$USERNAME` trap |
| `test` | Run every `_ctl/tests/*.test.sh`; fail if it finds none |
| `help` | Usage |

`propagate` and `release` were 2 more rows here, and both are deleted. Each one
shelled out to `$(git rev-parse --show-superproject-working-tree)/.claude/scripts/`,
a layout that belonged to the pre-Eden `brain` parent. Eden has no
`.claude/scripts/`, so both verbs took their own error path at every invocation
and told the caller to run them "from within brain". A verb that cannot succeed
is worse than an absent verb: it reads as a capability in the catalog, and the
verb catalog is what a reader trusts.

## Dependency graph

```
        base            cloud
     ┌───┴───┐        (FROM ubuntu)
 flutter   zephyr
              │
        zephyr-devbox
```

`validate.yml` runs `bash ./ctl.sh validate`, then `bash ./ctl.sh test`, then
asserts that BUILD_ORDER agrees between `ctl.sh` and `.ci/ctl.sh`. `.ci/ctl.sh
validate` delegates to the root `ctl.sh`: it used to be a second copy and the 2
diverged, so it reported OK on a Dockerfile that the root script rejected.

The graph is declared in **6** files. All 6 MUST stay the same. Count the list,
never the sentence — this heading said 5 while carrying 6 bullets, and its 4th
bullet called itself "the 5th home" by counting `BUILD_ORDER`'s 2 files as 2:

1. `BUILD_ORDER` in `./ctl.sh`.
2. `BUILD_ORDER` in `.ci/ctl.sh`.
3. `dependsOn` in each image's `project.json`.
4. `needs:` in `.github/workflows/build-and-push.yml`.
5. `image_parent()` in `.ci/affected.sh`. It arrived with affected-only builds.
   It is the graph again because a child's input set has to CONTAIN its
   parent's: that inclusion is what makes "the parent built, so the child
   builds" true by construction, and a missing edge there publishes a layer on a
   parent that moved under it. The workflow's `needs:` and this map answer 2
   different questions — order, and inputs — and both are the same graph.
6. `.ci/providers/github/build-and-push.yml`. This file is the source of truth
   for the provider, and it must match home 4 byte for byte. It is a home in its
   own right, because a reader who edits 1 of the pair has already drifted the
   graph. Once it became an old copy that listed only 3 images, and nobody saw
   the difference. Then it drifted again in commit `d9089b2`, which added 5
   `timeout-minutes: 90` blocks to the workflow and to neither copy of this
   file, while this rule went on calling them identical. A rule that nothing
   checks is a rule that drifts: `_ctl/tests/platform-policy.test.sh` compares
   the 2 files with `cmp` now, and `bash ./ctl.sh test` runs it in the pull
   request gate.

**2 files still say 4**, and they are the files the reader meets on a red gate:
the step comment at `.github/workflows/validate.yml:49`, and the `fail_check`
evidence string in `_ctl/tests/publish-order.test.sh`. That number was correct
before `image_parent()` and before the `cmp`. Both belong to the wave that owns
workflows and tests; this document is the count they must take.

That `cmp` covers **every** file of `.ci/providers/github/`, found by a glob, and
not `build-and-push.yml` alone. The narrow version had the same hole 1 level up:
a second provider file got no check at all on the day it was added, and
`security-nightly.yml` is that second file. A glob that stopped matching would be
a green result that read nothing, so the same test holds a literal list of the
directory — **add or rename a provider file and you edit
`EXPECTED_PROVIDER_FILES` in `_ctl/tests/platform-policy.test.sh` in the same
change.** The direction is provider → workflow: `validate.yml` and `pr-review.yml`
are provider-native and have no source-of-truth copy.

## The `+ runner` layer is retired

CI runs **these images**. There is no second set of CI images, and 2 measured
constraints say the toolchain has to be the image of the POD rather than a
workflow `container:` image:

1. The dind daemon in the runner pod pulls a `container:` image, and the image
   is lost when the pod stops. At this image size the cost is 5m17s per job.
2. To pull a private package with `GITHUB_TOKEN` you need a grant for each
   (package, repository) pair. GitHub gives that grant only in its user
   interface. A kubelet pull has neither problem: 1 in-cluster
   `imagePullSecret` covers every image and every repository.

Both still hold. What changed is WHICH image answers them. `base-runner` —
`base` plus the runner binary, built from `runner/Dockerfile` — was that image
until all 3 ARC pools moved to `cloud`, pinned by digest (gophersys/
infrastructure #184). `cloud` folds the runner in itself, so the extra layer has
no consumer.

So `base-runner` is retired here: out of `BUILD_ORDER` in both control scripts,
out of both copies of the publishing workflow, out of the nightly scan matrix,
and out of `.ci/smoke.sh`. Its `content-runner` check group did NOT go with it —
`cloud` carries the runner layer, and that group runs against `cloud`.

1 thing is deliberately left. The second thing this section listed as left is
already gone, and the entry stays so the next reader does not go looking:

- **`runner/` is still on disk.** Nothing builds it: no loop of either control
  script reaches its Dockerfile, because every loop walks `BUILD_ORDER`. That is
  not the same as inert — it is still a pin home, an exemptions row and a
  literal in 5 test files, all listed under convention 2 above. Its deletion is
  scheduled with the consolidation wave, and it edits every one of those files
  in the same change.
- **`ghcr.io/gophersys/base-runner` is GONE from the registry.** This document
  said the package "is still published" and that it would be archived "after
  this merges". Read on 2026-08-17, the org holds no `base-runner` and no
  `base-runner-cache` package, and
  `/orgs/gophersys/packages/container/base-runner` answers 404. So no tag of it
  is reachable, and a consumer that still pins one gets a pull failure and not
  an old image.

The full interface is in `gophersys/infrastructure` `docs/ci-substrate.md`. It
states which capabilities are pools and which capabilities are images.

## The builds run at home

`build-and-push.yml`, `security-nightly.yml` and `weekly-bumps.yml` run on
`arc-build`. `validate.yml` and `pr-review.yml` keep `arc-org` and `arc-review`.
Nothing in this repository runs on a GitHub-hosted runner: the account had 195
of 2,000 minutes left against a $0 budget, and a warm rebuild of the whole set
spent ~35 of them per push. The measurement was taken when the set held 6
images; it holds 5 now, and the number is kept because the budget argument does
not depend on the count.

- **No job may install a free-disk action.** That action reclaims space by
  deleting the preinstalled SDKs of a throwaway hosted VM. On `arc-build` the
  same deletion strips the NODE, and the blast radius is every pod on it. A
  build pod takes its headroom from the `work` volume the scale set sizes.
  `_ctl/tests/workflow-yaml.test.sh` holds both halves — every `runs-on:` in
  both workflow directories, and the absent action.
- **Only what changed is built.** Each job of `build-and-push.yml` asks
  `.ci/affected.sh <image>` whether the commit touches that image's inputs and
  gates its build, smoke, push and manifest read on the answer. The path table
  lives in that 1 file. Everything builds on `workflow_dispatch`, on a tag, and
  on any change to a workflow or to `.ci/`. **An unbuilt image keeps its
  `:latest` and publishes no `:<sha>` for that commit** — a SHA tag is not a
  promise that every image carries it.
- **The layer cache is in the registry**, `ghcr.io/gophersys/<image>-cache`, one
  package per image, `mode=max` on the write. `type=gha` is 10 GB per repository
  across every scope, which 5 images at `mode=max` do not fit.
- **The builder is `.ci/buildx-node.sh`, not `docker/setup-buildx-action`.** It
  makes the same `docker-container` builder — the default `docker` driver can
  neither read nor write a registry cache — and it owns the switch that appends
  the Mac mini as a native arm64 node when `SANCTIONED_PLATFORMS` names
  `linux/arm64`. That switch READS the library, so widening the platform set
  stays 1 edit in `_ctl/lib.sh`. It is inert today (D42).
- **No bridge exists on the build path.** The builder container and every RUN
  step share the runner pod's own network namespace (`network=host` +
  `--oci-worker-net=host`). The default is a bridge at MTU 1500 nested inside
  a flannel pod interface at MTU 1450, and that mismatch is a silent
  blackhole: whether a fetch survives depends on the PEER's path-MTU
  behaviour. It killed the first arc-build wave 3 times — get.helm.sh reset
  the same fetch at the same offset in every attempt while ghcr.io, docker.io
  and dl.k8s.io tolerated the mismatch — and it was proven by a probe on
  k3s-w-0 that timed out through the bridge and succeeded from the pod
  namespace. The pod namespace needs no number maintained: the CNI sizes it.
  `_ctl/tests/egress-policy.test.sh` pins both tokens.
- **The builder boots from OUR registry.** With no image named, buildx pulls
  `docker.io/moby/buildkit:buildx-stable-1` — an unpinned tag on a registry
  nothing else here uses, fetched before one line of ours runs; a 502 from
  auth.docker.io killed a build attempt in exactly that pull. `BUILDKIT_REF`
  in `_ctl/lib.sh` names the same image mirrored to
  `ghcr.io/gophersys/buildkit`, pinned by index digest.
  `.ci/mirror-buildkit.sh` keeps the mirror populated — the warm path is 1
  authenticated read of ghcr.io — and is the only file that names the
  docker.io source. Every build job orders login → mirror → builder, because
  the mirror package is private. Bumping BuildKit is 1 edit to the 2
  adjacent refs in `_ctl/lib.sh`; the next build copies the new version
  across. The mirror is deliberately OUTSIDE `versions.env` and
  `upstreams.txt`: it is CI substrate, not image content, and nothing scans
  or smoke-tests it — residue recorded on the ledger.
- **Both `_build` fetch helpers retry**: 4 more attempts, 3 seconds apart, on
  ANY failure (`--retry-all-errors` — curl's default retry set skips a
  mid-transfer reset, the failure home egress actually produces). The digest
  comparison in `fetch-verified.sh` judges whichever attempt lands, so a
  retry can change WHETHER bytes arrive and never WHICH bytes install.
- **Every timeout in those 3 workflows is a ceiling measured on the hosted
  runner.** The first run on `arc-build` measures the real numbers. Resize from
  that, never from a guess.

## Shared-change propagation

`gophersys/eden` uses this repository as a submodule at `.devcontainer/`. Eden
does not see a change here until Eden moves that pointer:

```sh
# from the eden checkout
git -C .devcontainer fetch origin && git -C .devcontainer checkout <sha>
git add .devcontainer && git commit
```

**There is no propagate verb, and there is no fan-out.** `bash ./ctl.sh
propagate` used to stand here. It called
`$(superproject)/.claude/scripts/propagate.sh`, a path of the pre-Eden `brain`
parent that Eden does not have, so every invocation took the error branch. The
pointer bump is 1 commit in 1 consumer, which needs no automation and needs
Mateo's approval like any other merge.

## Git hygiene

- Set the git identity for each repository:
  `user.name = Mateo Segura`, `user.email = mateo.segura413@gmail.com`.
- Set `commit.gpgsign = false` for each repository.
- Use Conventional Commits for every commit.
- Do not force-push to `main`.
- Do not put an AI or LLM attribution anywhere.
