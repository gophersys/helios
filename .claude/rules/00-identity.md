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

The repository supplies 6 **devcontainer** images. Every one of them sets the
`GOPHERSYS_DEVCONTAINER` environment marker, so a script can detect the image
that it runs inside.

| Image | `GOPHERSYS_DEVCONTAINER` | Intent |
|---|---|---|
| `ghcr.io/gophersys/base`          | `base`          | Everything that most projects need: shells (zsh+oh-my-zsh), git/gh, languages (Node LTS, Python 3.12, Go, Rust), infra CLIs (kubectl/helm/k9s/tailscale/docker-cli/docker-compose/bw/nats), desktop libs (Tauri/GTK/webkit), USB/BLE libs (libusb, libudev, libbluetooth, bluez), data clients (psql, sqlite3, redis-cli), parsing (jq, yq, httpie, rg, fd, bat), QA (shellcheck, hadolint). |
| `ghcr.io/gophersys/mobile`       | `mobile`       | Base + OpenJDK 21 + Android cmdline-tools/platform/build-tools + Flutter stable SDK. |
| `ghcr.io/gophersys/embedded`      | `embedded`      | Base + device-tree-compiler/ninja/ccache + west in an isolated venv + Zephyr SDK (arm-zephyr-eabi + riscv64-zephyr-elf by default) + all Espressif Xtensa SDK toolchains + esptool in an isolated venv + the flash/debug bench (openocd/stlink-tools/picocom/gdb-multiarch/clangd) + udev rules for common dev boards and for the CP210x/CH340 USB-UART bridges. **It was 2 images**, `zephyr` and `zephyr-devbox` — see "The embedded fold" below — and **the pod half of that fold is DELETED**: no sshd, no code-server, no `EXPOSE`, no `GOPHERSYS_EMBEDDED_MODE`. See "The devbox mode is deleted" below. Its `size_budget_gb` is 8.15 and no longer provisional: the 8.98 ceiling — set against the image BEFORE the deletion — was reset on 2026-08-19 to the first post-deletion publish measured by the gate, 7,760,642,048 unpacked bytes + 5% (run 32231070482); the measurement record is beside the key in `images.yaml`. |
| `ghcr.io/gophersys/cloud`         | `cloud`         | The successor image of the consolidation program (ledger #94), ADDITIVE today: the reduced base (no clang/cmake, no desktop/Tauri libs, no USB-BLE libs, no Rust, no ansible + oci-cli, no speedtest-cli/ncat/net-tools, Go caches removed — terraform and the AWS CLI are NOT in this list, because they left `base` itself and are ready components nothing installs; db clients and the comfort TUIs are not in it either, because cloud re-adds them through `_delta/components/`) + delve/buf/grpcurl + the CI fold (Actions runner, cictl, claude/omp/codex at the versions.env pins). ONE image for dev and CI: the default command is zsh, and a CI pod overrides the command to `/home/runner/run.sh`. Every pin lives in `versions.env` at the repository root — the same 1 home `base` reads since the 2 Dockerfile mechanisms collapsed onto it; the build feeds it in as generated `--build-arg`s, and `_delta/components/*.sh` install the folded tool groups. Its smoke gates publish (build → smoke → push) and enforces the ≤ 5.75 GB size budget (raised from 5.5 GB by Mateo, 2026-08-16: the measured floor after the R4 levers with every tool kept is ~5.63–5.67 GB). That budget is DATA now — `size_budget_gb` on its `images.yaml` entry, with the R4 measurement beside the key — and `.ci/smoke.sh` runs 1 shared gate for every image that declares one. |
| `ghcr.io/gophersys/hardware`      | `hardware`      | Cloud + the KiCad 10 ECAD toolchain, for `gophersys/research-hardware`. It installs `kicad`, `kicad-symbols`, `kicad-footprints` and `kicad-packages3d` from `ppa:kicad/kicad-10.0-releases`, and the python stack that repository's suite imports and runs (`kiutils`, `sexpdata`, `pytest`, `ruff`) into the SYSTEM interpreter, because `python3 -m pytest` cannot import from a `uv tool` venv. The library packages are named explicitly: `kicad` does not pull them in under `--no-install-recommends`, and without them `/usr/share/kicad` exists and is EMPTY, so the consumer's resolver suite fails on `assert 0 > 10000` — which reads like a code bug. `checks_content_hardware` holds the 3 floors that keep it true. **It is 1 of the 2 CHILD images whose pins live in `versions.env`** (`ui` is the other): its ARGs are value-less like cloud's, and `pins: versions.env` on its manifest entry is what generates the build args, so no extra `PIN_VALUE_HOME` is minted. Its `size_budget_gb` is 10.52 and no longer provisional: the 11.0 estimate computed from 2 measured images was reset on 2026-08-19 to the first green build measured on the repaired gate, 10,013,827,072 unpacked bytes + 5%. |
| `ghcr.io/gophersys/ui`            | `ui`            | Cloud + headless Chrome and the DejaVu fallback font, for `gophersys/research-ui`. Its ARGs are value-less and it takes `pins: versions.env` the way `hardware` does. It exposes cloud's own Node and uv at `/usr/local/bin` rather than carrying a second copy of each, so the content group asserts `node`/`npm`/`uv` resolving as BOTH root and dev. Its `size_budget_gb` is 6.33 and no longer provisional: the 6.5 estimate from 2 independent derivations (6.32 and 6.47) was reset on 2026-08-19 to the first build measured on the repaired gate, 6,027,251,712 unpacked bytes + 5%, and the a-priori 6.32 landed 0.005 GB from the truth. **This row arrived late.** The image landed in `images.yaml` on 2026-08-18 and reached no sentence of this document, so every count here read 6 while the set was 7 — measure the manifest, never a count in this file. |

## Structure

```
.devcontainer/
├── README.md
├── project.json                 # repo-level Nx wiring
├── ctl.sh                       # repo-wide control
├── images.yaml                  # the ONE declaration of the image SET
├── versions.env                 # the ONE pin home of base, cloud and hardware
├── _ctl/lib.sh                  # the shared ctl library — every verb body, 1 time,
│                                #   and the images.yaml reader every home derives from
├── _ctl/generate.sh             # images.yaml -> the publish jobs + the nightly matrix
├── _ctl/tests/                  # hermetic *.test.sh + harness + docker stub + fixtures
├── .claude/rules/00-identity.md # (this file)
├── docs/                        # PROPOSALS — part of one has LANDED; see docs/README.md
├── _build/                      # COPYed into base and cloud, above their first download
│   ├── fetch-verified.sh        # the ONE verifier every image download goes through
│   ├── download-exemptions.txt  # the downloads that take a stated class instead of a digest
│   ├── upstreams.txt            # where the next value of every pin comes from
│   └── resolve-upstream.sh      # the weekly resolver: 1 function per datasource
├── _delta/components/           # 1 file per folded tool group; cloud COPYs them and runs them
├── .ci/                         # the CI layer — .ci/README.md lists every file
│   ├── affected.sh              # which images this commit changes — 1 home for the answer
│   ├── buildx-node.sh           # the builder every image build uses; owns the arm64 switch
│   ├── mirror-buildkit.sh       # keeps ghcr.io holding the BuildKit index the builder boots from
│   └── ghcr-retention.sh        # what may be deleted from ghcr.io, and what may never be
├── base/          { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── cloud/         { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── mobile/       { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── embedded/      { devcontainer.json, Dockerfile, project.json, ctl.sh, embedded-entrypoint.sh }
├── hardware/      { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── ui/            { devcontainer.json, Dockerfile, project.json, ctl.sh }
└── .github/workflows/
    ├── build-and-push.yml    # publish the images
    ├── security-nightly.yml  # the nightly trivy scan + the base-OS currency probe
    ├── weekly-bumps.yml      # the weekly upstream resolution + the 1 bump pull request
    ├── validate.yml          # the pull request gate: ctl.sh validate + ctl.sh test + BUILD_ORDER
    ├── pr-review.yml         # the review agent, shared from gophersys/cictl
    └── ghcr-retention.yml    # the weekly prune; DRY RUN until its mode is changed
```

## Conventions

1. **This repository has no Nx workspace of its own.** You must be able to run
   every operation as plain `bash ./ctl.sh <cmd>` from within this repository.
2. **Per-image file rule.** Each devcontainer image directory at the repository
   root (`base/`, `cloud/`, `mobile/`, `embedded/`, `hardware/`, `ui/`)
   contains
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

   **A dispatcher is EXECUTABLE, and `validate` is what holds it there.**
   `image_ctl` in the root `ctl.sh` refuses a per-image `ctl.sh` that is not
   `-x`, so a file committed 100644 makes every per-image verb of that image
   fail. Nothing caught it before this gate: `validate` shellchecks the file by
   READING it, and a reader is blind to the mode. `hardware/ctl.sh` shipped that
   way (run `32133161779`) — the publish job pushed `:latest` and `:8af73ec`,
   and then `verify-published` died on the mode, which is the ordering the whole
   build → smoke → push rule exists to avoid: the check that could have stopped
   it ran after the irreversible action. The check derives its list from
   `images.yaml` like every other loop in `cmd_validate`, so a directory that is
   not an image of the manifest is not held to it —
   `_ctl/tests/fixtures/no-platform-list/ctl.sh` is a dispatcher-shaped fixture
   and not an image. The rule's holder is `_ctl/tests/dispatcher-mode.test.sh`,
   which proves in a staged tree that the check fires, names the file, and does
   not hold a dispatcher outside the manifest.

   **`runner/` was the 1 exception, and it is DELETED.** See "The `+ runner`
   layer is retired" below. There is no exception to this rule any more: every
   directory the rule names is an image of `images.yaml`, and `image_dir()` in
   `ctl.sh` is `<root>/<name>` for all of them. The `.ci/ctl.sh` copy of that
   function went with the arm it mirrored — it had no caller of its own.

   **"Nothing builds it" was not "nothing reaches it", and that is what the
   deletion cost.** While the directory sat retired, `runner/Dockerfile` was 1
   of the 5 `PIN_VALUE_HOMES` in `_ctl/lib.sh` and `bump_pin` wrote into it
   every Monday; it was 1 of the 6 `GOVERNED_DOCKERFILES` in
   `_build/resolve-upstream.sh`; `_build/download-exemptions.txt` carried its
   claude-installer row; and 5 test files held `runner/Dockerfile`,
   `runner/ctl.sh` or `runner/project.json` as a literal. So the deletion edited
   every one of those files in 1 change and was not a `git rm` — which is the
   general lesson, not a fact about runner: measure what READS a directory
   before you call it inert.

   **Those 2 lists hold different members, and different lengths.** Read
   each list, never a count beside it. `PIN_VALUE_HOMES` is 3: `base/Dockerfile`
   left it when it went value-less, `runner/Dockerfile` left it by deletion, and
   `zephyr/Dockerfile` + `zephyr-devbox/Dockerfile` left it as a PAIR when the 2
   images became `embedded/Dockerfile` — so it is `versions.env` plus the 2
   Dockerfiles that still spell their own pins.
   `GOVERNED_DOCKERFILES` is 5 and holds `base/Dockerfile` AND
   `cloud/Dockerfile`, because a governed file is one that FETCHES and base
   still fetches every download it always did. It stopped declaring the VALUES,
   not the URLs.
3. **Do not add a `CLAUDE.md` file.** The conventions of this repository stay
   here, in `.claude/rules/`.
4. **Attribution is identity.** The record must say who did the work. This
   REVERSES the no-attribution rule this line used to carry — see "Attribution"
   under Git hygiene below. `gophersys/eden` `.claude/rules/git-process.md` §13
   is the single home of the rule (ADR-0032); what follows is this repository
   obeying it, never a second copy to be maintained.

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
file. **In `base/Dockerfile`, `cloud/Dockerfile` and `hardware/Dockerfile` those
ARGs are VALUE-LESS: the value lives in `versions.env`, the ONE pin home, and
arrives as a generated `--build-arg`.** Each `versions.env` row carries the
`# latest LTS as of YYYY-MM-DD` comment — the date belongs beside the value it
dates, not beside a declaration that holds none.

**There were 2 mechanisms until this collapse, and now there is 1.**
`base/Dockerfile` carried 55 inline `ARG NAME=value` pins — measured
2026-08-17 — and 54 of them were spelled in `versions.env` as well, at equal
values; `_ctl/tests/pin-mirroring.test.sh` existed only to hold the 2 copies to
1 value. The rule did not die whole at that collapse: 3 pins stayed dual-home in
`versions.env` and the retired `runner/Dockerfile`, and
`_ctl/tests/runner-residue-mirroring.test.sh` held that pair to 1 value. **No
pin has 2 homes now.** `runner/` is deleted, so `RUNNER_VERSION`,
`CICTL_VERSION` and `CLAUDE_CODE_VERSION` hold their `versions.env` row alone,
and that test file went with its subject. The 55th was
`RUST_CHANNEL`, which `cloud` does not install and which
is a `versions.env` row now like the rest. Everything downstream paid for the
split: 6 pin homes, a family branch in `.ci/smoke.sh`, an admitted over-build in
`.ci/affected.sh`. It is 1 mechanism now, and the doubling that dual-arch would
have done to it is a doubling of 1 file.

**The 2 per-image Dockerfiles still carry inline pins, and that is the open
half.** `mobile/` and `embedded/` declare their own
`ARG NAME=value` blocks and consume no build arg from `versions.env`. `runner/`
was a 4th and is deleted, which closed its share of the debt by removing the
file rather than by moving it; `zephyr/` and `zephyr-devbox/` were 2 of the 3
that remained and are 1 now, which closed a home the same way — by removing a
file, not by moving a pin into `versions.env`. Read "the pin value is in `versions.env`" as true
of `base`, `cloud`, `hardware` and `ui`, and of nothing else. `hardware` and
`ui` are CHILDREN that read the one home, which is what the `pins` key of
`images.yaml` exists for: without it a child has to spell its own pins, and a 4th `PIN_VALUE_HOME`
would be minted for the sake of a `parent:` field.

**What closed is the CLASSIFICATION half, and it closed alone.** That sentence
went on to say those pins "are the ones no smoke run compares". They are
compared now: `.ci/smoke.sh` reads a child image's own Dockerfile as a SECOND
pin home beside `versions.env`, with a class table of its own, and the
refuse-to-run rule for an unclassified pin covers both homes equally. The reader
takes every VALUE-FUL `ARG` — measured on 2026-08-19, 17 of them across the 2
files (mobile 9, embedded 8), each file's own `BASE_TAG` and all 4 digest rows
included, because an ARG that carries a value and no class is the
silence the rule exists to break — and 5 of them name a tool that reports its
own version: `JAVA_VERSION`, `FLUTTER_VERSION`, `WEST_VERSION`,
`ZEPHYR_SDK_VERSION` and `ESPTOOL_VERSION`. It read 20 and 6 the day before,
and the devbox deletion took `CODE_SERVER_VERSION` and its 2 digest rows out of
`embedded/Dockerfile` — count the blocks, never this sentence.
The rest are a build id, an API level, a channel or a toolchain list, and each
one says so in its row's neighbourhood. **The VALUE home did not move**: these
files still spell their own pins and `bump_pin` still writes into both of them,
so `PIN_VALUE_HOMES` is 3 and ledger #102 stays open on that half. It was 5 with
`runner/Dockerfile` in it, and that home left by deletion and not by moving; the
zephyr pair left the same way, by becoming 1 file rather than by moving a value —
the 2 open ones are the 2 child images that spell their own pins.

- **To change a version**, edit 1 `versions.env` row and its date comment.
  Change nothing else. The Dockerfile is not a home and takes no edit.
- **A hardcoded version in a RUN line is forbidden.** `ctl.sh validate`
  searches for `=\d+\.\d+\.\d+` in a RUN line and fails the build.
- **A value-less ARG needs a gate, or it fails silently.** An unfed pin expands
  to the empty string, and the failure surfaces much later as a mangled download
  URL. Both root Dockerfiles therefore open with a `RUN : "${PIN:?not in
  versions.env}"` chain that stops the build naming the variable — 71 entries in
  `base`, 81 in `cloud`. Each grew by its digest count when the platform set
  widened: a `_SHA256_ARM64` row is a pin like any other, and an unfed one would
  reach the arm64 leg of the build as an empty digest.
  `UBUNTU_BASE_REF` is deliberately outside both chains:
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
  shows at build time: `mobile/Dockerfile` chowned `/opt/flutter` and
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
- **The vocabulary is `_SHA256_AMD64`, `_SHA256_ARM64` and `_SHA256_NOARCH`, and
  nothing else.**
  It names the PLATFORM and never the upstream asset spelling — compose writes
  `x86_64`/`aarch64` and buildx writes `amd64`/`arm64` for the same 2 platforms,
  and following the asset gave 2 vocabularies per arch. `_NOARCH` is for an
  asset that serves every platform. **The rule that said "no `_ARM64` row while
  the set is `linux/amd64` alone" is INVERTED, not deleted**: a row exists for
  every sanctioned platform, and a platform in the set with no row is the
  failure the rule now names — the arm64 leg would reach its download with an
  empty digest. Each row is written ONCE, in `versions.env`, for both root
  images, which is why collapsing the pin mechanism before widening the arch
  axis was worth doing: 2 homes × 2 arches is the multiplication this repository
  did not pay.
- **The arm chooses the digest, and the pin NAME travels with it.** With 2
  platforms the `case` has something to choose again, so each arm sets
  `SHA256` and `SHA256_PIN` beside its `ARCH`, and the fetch reads both. The
  second local is not decoration: `fetch-verified.sh` names that pin in every
  refusal, and `YQ_SHA256_ARM64` tells a reader the row to fix where "exit 1"
  tells them nothing. **Do not spell that local `<TOOL>_SHA256_PIN`.**
  `<PREFIX>_SHA256_<SUFFIX>` is the shape every reader of the vocabulary
  matches, so the local reads as a digest row that no home declares —
  `_delta/components/protocols.sh` did it and `download-coverage` reported a
  digest living in "nowhere" while every real row was correct. It is `BUF_PIN`
  there.
- **A case arm stays on ONE line.** `fetch_urls` in `_ctl/lib.sh` reads an arm
  as the text between `linux/amd64)` and the `;;` that follows it on the same
  logical line. An arm broken across lines reads as an arm that assigns nothing,
  and every download below it becomes a download nobody can answer for.
- **Every digest row records where its value came from**, machine-readably:
  `# upstream-published: <checksum file url>` when the release ships a checksum
  file and the 2 agreed, otherwise `# computed-at-pin: <yyyy-mm-dd>` — TLS plus
  an immutable release URL is then the whole evidence, and the row says so. A
  number a reviewer has to take on faith is not a pin.
- **The download itself goes through `_build/fetch-verified.sh`.** It is 1 file
  by the same rule that puts a verb body in `_ctl/lib.sh` once. `base` and
  `cloud` COPY `_build/` to `/usr/local/lib/gophersys/` above their first
  download; `mobile`, `embedded`, `hardware` and `ui` inherit it
  through their `FROM` and add no COPY. `hardware` fetches nothing of its own —
  apt over the PPA and pip are its 2 installers, and each is answered by its own
  ecosystem — so it is deliberately NOT a governed download file. **Because base COPYs it, base's docker
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
The other 5 Dockerfiles build from an image of this repository, so they inherit
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

`.github/workflows/security-nightly.yml` scans the 6 published images at
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
  gated, by measurement and decision (Mateo, 2026-08-18): the count is
  267-333 per image (base 267, cloud 333, zephyr 267, zephyr-devbox 268,
  measured in-cluster at trivy 0.65.0), and a ~270-finding red every morning
  teaches the reader to ignore red. Re-measure before ever gating it.
- **An unfixed CRITICAL becomes a waiver, never a skip — with ONE named
  exception.** `linux-libc-dev` takes the class rule in
  `.ci/trivy-ignore-policy.rego` (Mateo, 2026-08-24): the kernel-headers
  package accrues unfixed kernel CVEs faster than dated waivers can follow —
  5 in the 5 days to 2026-08-24 — and no kernel code from it executes in a
  container. That suppression is deliberately NOT dated the way a yaml waiver
  is: it un-suppresses itself through `FixedVersion` instead of an expiry —
  the rule ignores a finding only while ubuntu publishes no fix, so the
  moment one ships the finding resurfaces and the rebuild picks it up. The
  scan names the policy with `--ignore-policy`, and
  `_ctl/tests/scheduled-workflows.test.sh` holds the file's existence and
  both predicates of its rule. Every OTHER package: waivers live in
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
- **13 datasources, and the 13th resolves nothing.** `github-release`, `pypi`,
  `npm`, `go-proxy`, `apt`, `go-dl`, `node-dist`, `oci-index`, `k8s-dl`,
  `tailscale-pkgs`,
  `flutter-releases` and `eden-manifest` each read 1 upstream DOCUMENT;
  `no-autobump` states, in a sentence, why a pin is not resolved. 15 pins take
  it today: the 3 `ANDROID_*` rows, `PYTHON_PACKAGE`,
  `JAVA_VERSION`, `KICAD_PPA_VERSION`, `CHROME_MAJOR_VERSION`, `RUST_CHANNEL`,
  `FLUTTER_CHANNEL`,
  `BENCHSTAT_REF`,
  `TERRAFORM_VERSION`, `AWS_CLI_VERSION`, `CICTL_VERSION`, `HNSLINT_VERSION`
  and `BW_VERSION`. **The count and the names must be re-derived together.**
  This sentence read "14" over 14 names while the table held 15 rows, because
  `CHROME_MAJOR_VERSION` was never enumerated; correcting the count alone left
  a list that claimed to be exhaustive and was not. `KICAD_PPA_VERSION` joined with the hardware image and takes
  the class `PYTHON_PACKAGE` and `JAVA_VERSION` take: it is a MAJOR LINE inside
  a name — `ppa:kicad/kicad-10.0-releases` — so the version that archive
  publishes (`10.0.5~ubuntu24.04.1` on noble) is not what the row holds, and a
  new major is a different PPA that a human chooses. **Only the exceptions are
  named here.** A pin of a resolving datasource takes no line in this document,
  which is why the 4 pypi pins the hardware image added
  (`KIUTILS_VERSION`, `SEXPDATA_VERSION`, `PYTEST_VERSION`, `RUFF_VERSION`) are
  absent from it: their rows are the whole record. The 3 harness pins left the
  set on 2026-08-17, when
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
- **A row that RESOLVES can still be dead, and that is the harder defect.** The
  3 corrections above were coordinates that FAILED — a 404 a run reports. The
  4th was silent: `GOVULNCHECK_VERSION|github-release|golang/vuln` resolved
  every Monday to 1.1.4, because golang/vuln cut its last GitHub Release there
  and went on TAGGING to v1.7.0. Nothing went red for 7 months, the pin sat 6
  releases behind, and it surfaced only when go1.27 arrived and 1.1.4's vendored
  x/tools panicked on the AST in every consumer's `validate`. **A resolver that
  always answers the same thing is indistinguishable from a pin that is
  current.**
- **The upstream of a `go install` pin is the MODULE PROXY**, which is what
  `go-proxy` reads — `.Version` of `proxy.golang.org/<module>/@latest`, the
  coordinate being the module path and never the package path under it. A
  GitHub Release is a document a human writes about a tag and `go install` never
  reads one, so the proxy is the upstream that decides the bytes. 5 pins take it:
  `DELVE_VERSION`, `GOFUMPT_VERSION`, `GOLANGCI_LINT_VERSION`, `GOSEC_VERSION`
  and `GOVULNCHECK_VERSION`.
  **The class is not the rule, and 2 `go install` pins are deliberately outside
  it.** `GREMLINS_VERSION` stays on `github-release` because the proxy answers
  v0.5.1 against a v0.6.0 tag and would DOWNGRADE it — the mirror image of the
  govulncheck defect, measured 2026-08-25 and undiagnosed. `BENCHSTAT_REF` stays
  on `no-autobump` because x/perf carries no tag at all, so the proxy answers a
  PSEUDO-VERSION naming a commit; `resolve_go_proxy` refuses one outright rather
  than moving a pin on every push to somebody's default branch. Choose the
  datasource per pin against a measurement, never per language.
- **The digest is of the asset for the version this run resolved.** The HTTP
  reads are 1 index plus 2 per ASSET — the digest and the re-proof — so the
  property is not "one fetch", and a dual-arch pin costs 2 assets rather than 1.
  `_build/resolve-upstream.sh <PIN>` prints `<version>|<row>=<sha256> ...`, one
  pair per digest row, where each URL is read out of the file that performs the
  download and never out of the table (a second URL home lets a correct digest
  be computed of the wrong asset), and each value is then handed back to
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
  when the pin carries one (`cictl` pins `v0.6.0`) and dropped when it does not;
  `go1.26.5` and `bun-v1.3.14` lose their word prefix the same way. An apt
  version drops the epoch and the debian revision, because `5.9` is what the
  tool reports about itself and what the smoke test compares.
- **`bump_pin` in `_ctl/lib.sh` is the only writer**, and it edits every home of
  the pin: the version row, EVERY digest row beside it and each of those rows'
  evidence comments, and no other line. It DISCOVERS the homes through
  `homes_of` rather than assuming any of them, which is why dropping
  `base/Dockerfile` from `PIN_VALUE_HOMES` changed nothing about it: a pin of
  `versions.env` alone now has 1 home, and the writer edits the 1 it finds. The
  multi-home path is still live for the 2 per-image Dockerfiles that spell their
  own pins — `mobile` and `embedded`, which is what
  `PIN_VALUE_HOMES` holds beside `versions.env`.
- **A pin's digest rows are a SET, and the writer REFUSES a partial one.** It
  takes `<row>=<digest>` pairs and fails naming the row that got no value, so a
  caller cannot move a version and leave a sibling behind. It could until
  2026-08-18: `digest_row_of` stopped at the FIRST `<TOOL>_SHA256_<ARCH>` it
  found — the `_AMD64` one — so every weekly bump left the `_ARM64` row on the
  digest of the release it was bumping away from, and the arm64 leg died at that
  download in the bump pull request. The reader is `digest_rows_of` and reports
  all of them; the refusal is what makes a third platform safe, because the day a
  `_SHA256_RISCV64` row is written every caller that does not compute one fails
  here naming it.
- **The resolver reads the arms THAT EXIST, never `SANCTIONED_PLATFORMS`.**
  `fetch_urls` emits one record per `linux/<arch>)` arm in scope at a fetch —
  `<platform>|<digest pin>|<url>|<case arm>` — and `_build/resolve-upstream.sh`
  fetches one asset per record, so each row's digest is of the asset for the arm
  that row answers for. That is also the whole handling of the 2 shapes that are
  not 2-armed, and `mobile/Dockerfile` holds one of each. **Read that file
  before repeating the pairing: it is the opposite of the intuitive one.** The
  Android cmdline-tools download sits under a `linux/amd64) : ;;` guard that
  assigns nothing, so its record carries platform `linux/amd64` and its row is
  `ANDROID_CMDLINE_TOOLS_SHA256_NOARCH`; flutter's OWN SDK download sits in a
  later RUN with no case at all, so its record carries platform `-` while its
  row is `FLUTTER_SHA256_AMD64`. Nothing in that second RUN names a platform —
  the `exit 1` in the guard RUN above is what makes the image amd64-only. A
  reader that consulted the sanctioned set would demand an arm64 asset from both.
- **A digest row that answers for 2 different assets is REFUSED**, naming the row
  and both URLs. 2 records may share a row: same asset means a duplicate READING
  of it — `base/Dockerfile` and a component under `_delta/` both fetch `k9s` and
  `docker buildx` at one URL — and is deduplicated, while 2 assets under 1 row
  can be correct for at most one arch. The identity compared is the URL with the
  ARM resolved into it, because 2 arms of one RUN usually share the URL template
  and differ only in what they assign `ARCH`.
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

## GHCR retention

`.github/workflows/ghcr-retention.yml` runs at 11:00 UTC on Monday — 04:00 MST,
1 hour after the weekly bump and 2 after the nightly, so the 3 scheduled runs
never race. The policy is `.ci/ghcr-retention.sh`, and nothing about what is safe
to delete is decided in the workflow.

**It is DRY RUN as it lands, and flipping it is a 1-word edit.** The schedule
supplies no inputs, so the `RETENTION_MODE: ${{ inputs.mode || 'dry-run' }}`
fallback IS the scheduled run's policy. A delete is irreversible and no job here
rolls one back, which is the same ordering rule that puts the smoke before the
push: read one real log first. `workflow_dispatch` with `mode=enforce` runs a
single enforcing pass without changing the file.

**An untagged version is almost always a LIVE CHILD, not an orphan.** A tagged
image here is an OCI index and its per-platform and attestation manifests appear
in the packages API as separate untagged versions. Measured on `base`
2026-08-26: 91 tagged, 225 untagged, and **all 225 are children of a live tag** —
zero orphans. The prune every retention example performs, "delete all untagged",
would have destroyed the content of all 91 tags. A child also has more than 1
parent — 300 references over 225 distinct digests — so the delete set is
`all versions - protected closure` and never a walk down from the doomed.

**A tag is not safe to delete because it is old.** 6 protection classes, each
with its measurement in the script's header: `latest`; every `v<semver>`; every
short-SHA tag a live submodule pointer names, reading eden's default branch AND
its open pull requests; every tag or digest a consumer pins; the transitive
children of all of those; and a margin of the `RETENTION_KEEP` most recent left
over. **The classes are not decoration, and that is measured rather than
argued**: `ghcr.io/gophersys/cloud@sha256:ffdcf504…` is the ARC image-warmer
DaemonSet's pin and ranks 3rd by recency, `cloud:997bb6b` ranks 35th of 43 and
`base:e0c6bc5` 56th of 91. A keep-the-10-most-recent rule with no pin sweep
deletes the last 2 outright and the first after 8 more publishes, and every ARC
pool in the homelab runs the image that DaemonSet warms.

**THE PROTECTED SET IS BUILT FROM RESOLVED DIGESTS, NEVER FROM TAG NAMES.** A
pin can name both — `ghcr.io/gophersys/hardware:latest@sha256:ad5851…` in
research-hardware, `ghcr.io/gophersys/ui:latest@sha256:26547a…` in research-ui —
and the digest is what is served while the tag beside it drifts. Read
2026-08-26, both of those digests carried only the tag `efe48e1` and `:latest`
had already moved to `449d5f4`. A reader that believed the tag half would call
both pins covered by class 1 and delete the digests anyway. The sweep therefore
takes every `sha256:<64 hex>` token of every swept tree, whatever syntax
surrounds it.

**The consumer list is MAINTAINED, and a missing row is the failure mode.** No
API answers "who pins me", so `RETENTION_PIN_REPOS` is a default in the script:
infrastructure, eden, research-hardware and research-ui. The first dry run
planned to delete `ad5851…` and `26547a…` because the 2 research repositories
were not in it — the mechanism was right and its input set was short by 2. **A
new consumer of these images is a new row there, in the same change that adds
the consumer.**

**A digest referenced only by a test fixture is protected and SAID SO.**
`cloud@sha256:9a150cbf…` appears only in
`infrastructure/scripts/test-verify-warmer-pins.sh`, whose own header says the
suite never reads a real manifest. The run reports it as fixture-only and keeps
it: a path heuristic that dropped it would trade a bounded cost — 1 index and
its children kept — for the unbounded one, a real pin in a file whose name
happens to say `test`. The fix belongs in the fixture, which should spell a
digest that cannot be mistaken for a live one.

**`Accept: */*` reads a live index as absent.** ghcr.io answers 404
MANIFEST_UNKNOWN for a manifest it serves when the Accept header does not name
its media type, and curl sends `*/*` by default. The closure walk therefore
sends the explicit OCI and docker media types, and a non-200 during the walk is
FATAL rather than an empty child list — an under-protection of this shape looks
exactly like a clean read.

**The sweep reads the CONSUMERS and deliberately not this repository.** A sweep
is a grep over a tree, so it reads prose as readily as configuration: the
script's own header names `ghcr.io/gophersys/base:e0c6bc5` while explaining that
infrastructure pins it, and that sentence alone protected the tag until the
counter-stimulus refused to fire. This document carries the same hazard
independently — it names `ghcr.io/gophersys/base:69b4f11` in a sentence about an
old incident. Nothing is lost: every reference this repository makes to its own
images is `:latest`, which is class 1.

**A read that fails is fatal, and "deleted nothing" is not asserted against.**
Every class is a read of something outside this repository, and a quiet failure
does not weaken a class — it EMPTIES it, and the run then deletes exactly what
the class existed to keep. So an unreadable consumer, an unreadable manifest, an
absent `GHCR_RETENTION_TOKEN` and a tag of an unrecognised shape each stop the
run before anything is deleted. What is NOT asserted is a non-empty delete plan:
once the backlog is gone an empty plan is the policy working, and a red every
Monday that nobody can act on is how a reader is taught to ignore red — the same
reasoning that keeps HIGH CVEs outside the nightly's gate. The guards assert
that each mechanism RAN, and every stage prints its count.

**What catches a wrong answer is 2 different tools, never 2 spellings of one.**
The first version of that safety net compared `kept + planned == versions`, and
those were 2 jq selections partitioning 1 array by 1 predicate — so the sum was
that array's length for every input, and the check passed on the exact DELETE-0
regression it was named for. The real catch for a jq that ERRORS is reading jq's
own exit status; for a jq that exits 0 and answers wrongly it is recomputing the
delete set with `comm` and refusing to act when the 2 disagree. A check that
cannot fail is worse here than no check, because this one was cited in 3 places
as the reason an empty plan could be trusted.

**The credential is `GHCR_RETENTION_TOKEN` and the workflow token cannot stand
in.** `GITHUB_TOKEN` carries no `delete:packages`, and it is scoped to this
repository, so it can read none of the 4 consumers. The secret needs
`read:packages` + `delete:packages` on the organization and `contents:read` on
each repository of `RETENTION_PIN_REPOS` and `RETENTION_SUBMODULE_REPOS`.
gophersys/infrastructure solves the same problem with a GitHub App
(`ARC_APP_ID` / `ARC_APP_PRIVATE_KEY`), and that route is NOT open here:
measured 2026-08-26, this repository is exposed to 0 organization secrets and
holds exactly 2 of its own, `BUMP_PR_TOKEN` and `EDEN_MANIFEST_READ`.

**This policy EXTENDS gophersys/infrastructure's, and does not replace it.**
`infrastructure/.github/workflows/ghcr-retention.yml` plus
`.github/scripts/prune-ghcr.py` already prune `workspaces-api` — keep `:latest`
and the 8 most recent — and that workflow says in its own header that it is
"Scoped to OUR package". So the rule is the one this organization already
applies to builds: **a repository prunes the packages it publishes.** The 2
systems share a registry and no package. Worth knowing about the other one: its
keep-newest-N rule is safe because `workspaces-api` is single-arch, and it
acquires the untagged-child footgun documented above on the day that image
becomes multi-arch.

## Sanctioned-platform policy

The sanctioned set is **2** platforms: `linux/amd64` and `linux/arm64`. The
declaration is `SANCTIONED_PLATFORMS` in `_ctl/lib.sh`, and it is the only place
a platform is named. A platform outside that set fails the guard and names
itself. 5 of the 6 images publish both; **`mobile` alone narrows**, to
`linux/amd64`, declared in `images.yaml` and measured — see the mobile
subsection below.

**An image builds only the arch it deploys to**, and that rule is what widened
the set as surely as it narrowed it. The narrowing measurements stay, because
they are why the arm64 half has to be NATIVE rather than merely present:

- `base-runner` ran only as an ARC pod, and every node in that cluster is amd64.
  Its arm64 half compiled Go under QEMU for an architecture that no node runs,
  and it took ~13 minutes on a thin layer. The image is retired; the measurement
  is kept because it is half of why the set narrowed.
- `zephyr-devbox` ran only as a kubernetes pod (commit `c7e8e94`). Its 3 running
  pods sat on `k3s-w-1`, `k3s-w-3` and `k3s-w-4`, and all 3 are amd64. That
  image is `embedded` now, and the measurement no longer narrows anything: the
  same image is what a developer opens locally, in its default mode, so it
  publishes both platforms like every other non-mobile image.
- `base`, `flutter` and `zephyr` were published for 2 architectures until the
  arm64 half was measured: the published `base` arm64 variant was an amd64 Ubuntu
  userland carrying aarch64 Go binaries, because the `FROM` line pinned the
  userland to the BUILD host while buildx labelled the result with the TARGET.
  So it was mislabelled rather than native, and on the only host that would
  consume it Docker Desktop emulates that userland anyway. It gave none of the
  benefit of a native image and cost the larger half of a 41.7-minute build.

**D42 is ANSWERED, and the answer is 2 consumers.** Local development on Apple
Silicon through the devcontainer CLI consumes `linux/arm64`, and the Mac mini
builds it natively — a standalone buildkitd over mTLS, 3.44x faster than the
same build emulated on an amd64 node, wired in `.ci/buildx-node.sh` and inert
until this line named the platform. Neither defect that retired the old arm64
half is reachable: no Dockerfile writes `FROM --platform=`, and
`platform-policy.test.sh` fails one that does.

**Widening it is not 1 edit, and the blast radius was measured, not predicted.**
Each shell path reads the list from that 1 declaration, and `.ci/smoke.sh`
selects a platform out of it rather than refusing a list of more than 1. **1
other place STATES the same policy**, and it must move with it: the literal
`SANCTIONED` in `_ctl/tests/platform-policy.test.sh`. That literal is deliberate
— a test that reads the value it checks agrees with any value, a wrong one
included. There were 3. The other 2 were `PLATFORMS` in
`.github/workflows/build-and-push.yml` and the same key in its provider copy,
and `_ctl/generate.sh` writes `SANCTIONED_PLATFORMS` into that key now, so
widening the list reaches both copies through a regeneration rather than through
2 hand edits. The
`build` verb also refuses a list of more than 1 entry, because `docker build`
makes 1 image, so the local loop must name the 1 platform it wants —
`IMAGE_PLATFORMS=linux/arm64 bash ./ctl.sh build base`, and a bare `build` now
fails naming the list.

Measured on 2026-08-13, narrowing: 1 edit to `_ctl/lib.sh` and nothing else made
8 checks red in 4 test files — `build` 3, `guard` 1, `platform-policy` 2,
`verify-published` 2. The per-file counts are here because the first version of
that sentence said 11, which is the TOTAL check count of `guard.test.sh` read as
its failure count. Measured on 2026-08-17, widening: **11 checks red in 5 test
files** — `build` 3, `guard` 1, `platform-policy` 3, `verify-published` 2,
`download-coverage` 2. The 2 that the narrowing measurement did not predict are
the reason the number is re-measured rather than reused: `platform-policy` grew
1 because `linux/arm64` is a FORBIDDEN token on the build path and the library
now writes it, and `download-coverage` is 2 new rules rather than 2 flipped
literals — the 1-arch digest vocabulary, and the rule that a fetch names its pin
literally instead of through the arm.

**A digest row per platform is the other half of the cost.** 20 `_SHA256_ARM64`
rows in `versions.env` and 2 more in the child Dockerfiles, each carrying its own
evidence, each verified against the asset the SAME pinned version publishes.
Widening again means doing that fact-finding again, per pin, before an edit —
and a pin whose new platform has no asset at the pinned version is a BLOCKER to
report, never a bump to improvise.

**Count the rows, never quote a count.** Every number in the paragraph above is a
measurement of a tree that changes, and the arch suffixes do not divide evenly —
read on 2026-08-19 the 3 value homes hold **46** declaration rows, 22 `_AMD64`
+ 21 `_ARM64` + 3 `_NOARCH`, because 3 downloads are `_NOARCH` and `mobile`'s
own SDK row has no `_ARM64` sibling to pair with. A count that assumes the rows
come in pairs is wrong by exactly those 4. It read 48 / 23 / 22 / 3 the day
before, and the devbox deletion removed the `CODE_SERVER_SHA256_AMD64` /
`_ARM64` pair — which is the point of the paragraph rather than an exception to
it. Re-derive it rather than trusting this sentence:

```sh
grep -hcE '^[[:space:]]*(ARG[[:space:]]+)?[A-Z0-9_]+_SHA256_[A-Z0-9_]+=' \
  versions.env mobile/Dockerfile embedded/Dockerfile
```

### mobile is amd64-only, and the manifest says so

**`mobile` publishes `linux/amd64` alone.** It is the 1 image of the 6 that
declares a `platforms` key in `images.yaml`, and the reason is upstream rather
than ours: **Flutter publishes no linux-arm64 SDK, at any version.** Read on
2026-08-17, `releases_linux.json` (264191 bytes) lists every Linux release ever
published — 730 of them — and `[.releases[].dart_sdk_arch] | unique` returns
`[null,"x64"]`: 431 predate the key and carry none, 299 say `x64`, and
`[.releases[] | select(.dart_sdk_arch != null and .dart_sdk_arch != "x64")]
| length` is **0**. The pinned 3.47.0 stable carries 1 archive whose filename
holds no architecture, so an HTTP probe of it succeeds and proves nothing —
read the JSON, never the 200.

No bump reaches an asset upstream does not publish, so this is not a stale pin
and it does not expire. Whether Android platform-tools ships a linux-arm64 build
is a question that only opens on the day Flutter itself does.
`mobile/Dockerfile` keeps amd64-only case arms, and they are CORRECT rather
than incomplete for as long as that key stands. Delete the key on the day the
SDK exists, and the arm64 arms and their `_SHA256_ARM64` rows go in with it.

**The mechanism is `platforms` in `images.yaml`, read by `image_platforms` in
`_ctl/lib.sh`.** An absent key means the sanctioned set, which is what the other
5 images take, so the manifest names a platform only where an image is an
exception. NARROWER is the only exception there is: a declared entry outside
`SANCTIONED_PLATFORMS` FAILS naming the image and the platform, because a
manifest that could widen the policy would BE the policy, and 1 place answers
"what may we publish". `resolve_image_platforms` puts that answer into
`IMAGE_PLATFORMS` at the head of `build`, `push` and `verify-published`, and
`.ci/smoke.sh` calls it with the image from its own argv. The ENVIRONMENT still
outranks both — `IMAGE_PLATFORMS_SOURCE` is what tells a caller's choice from
the default, since after the default runs the variable holds a value either way.

Two consequences a reader will meet:

- **`verify-published` asserts the image's OWN set**, not the sanctioned set.
  Against the sanctioned set, mobile's correct amd64-only manifest would read
  as a broken publish forever.
- **The generated publish job carries a job-level `PLATFORMS` key** where the
  image is narrower, which overrides the workflow-level one for that job. It is
  emitted only where the 2 differ: a key repeating the value above it is a
  second declaration waiting to drift.

Verify a published image with `bash ./ctl.sh verify-published <image> [tag]`. A
manifest declares a platform; that verb reads the manifest back out of the
registry and asserts the set is exactly the sanctioned one, and then asserts
that every blob those manifests reference SERVES — see "A manifest that parses
is not an image that pulls" below, which is the half a green manifest cannot
answer for. An `unknown/unknown`
entry is an attestation manifest, which buildx attaches 1 of per variant, and it
is not a variant. For the deeper check — the manifest declares a platform, but
what is in the layers — `bash ctl.sh verify-image-arch <ref> [platforms]` in
gophersys/infrastructure reads the content.

| Verb | Scope | Platform |
|---|---|---|
| `build` | local dev loop | explicit `--platform`, 1 platform, no push |
| `push` | publish | **GUARDED** buildx build + push |
| `verify-published` | after a publish | reads the manifest the registry holds, then asks the registry for 1 byte of every blob it references |

### A manifest that parses is not an image that pulls

Ledger #118. ghcr.io answered **404** for layer `d14f6240…` while 4 manifests
still referenced it. Every document parsed, every platform was declared,
`verify-published` was GREEN — and `docker pull` failed for every consumer until
an unrelated rebuild re-uploaded the blob. Manifest-level verification proves
STRUCTURE, and the structure was never what broke.

**A HEAD per blob does not close it, and that is MEASURED rather than argued.**
Read 2026-08-18 against a real layer of `ghcr.io/gophersys/base`:

```
HEAD /v2/gophersys/base/blobs/sha256:966c39…  ->  HTTP/2 200, content-length
                                                  29751109, answered by ghcr.io
                                                  ITSELF, with NO redirect
GET  /v2/gophersys/base/blobs/sha256:966c39…  ->  HTTP 307 to
                                                  pkg-containers.githubusercontent.com,
                                                  where the bytes actually are
```

The 2 methods are answered by 2 tiers. A HEAD asks the metadata tier whether a
blob is registered and never contacts the store that holds it, so **HEAD 200 is
not evidence**. A registry that has lost an object while keeping its metadata
answers exactly HEAD 200 / GET 404, which is the incident. The probe is
therefore a **ranged GET**, `Range: bytes=0-0`: it follows the 307, reaches the
object store, and costs 1 byte.

- **The cost is bounded and measured**, `:latest` on 2026-08-18, config + layers
  per platform: base 33, mobile 37, embedded 48, cloud 39, hardware 43, ui 43.
  The verb runs once per image, so the worst invocation is `embedded` at
  48 × 2 = 96 ranged GETs. The whole set is 449 probes over 11 variants — 449
  bytes of payload. Wall time from a home connection, measured the same day:
  base 34s, mobile 20s, embedded 120s, cloud 56s, hardware 48s, ui 49s. Batching
  the probes of one manifest into a single `curl` invocation, so the connection
  is reused, is the obvious speed-up and is NOT in this change.
- **The blob half speaks the registry API directly, and that is a 2-client
  seam.** No docker subcommand fetches a blob, so `registry_get_status` in
  `_ctl/lib.sh` uses `curl` while the index read stays on
  `docker buildx imagetools`. Moving the index read onto the same API would
  leave this verb needing no docker at all; that is recorded residue, not done.
- **The credential is resolved in 1 place and never falls back to anonymous.**
  `registry_credential` reads `GHCR_TOKEN`, `GITHUB_TOKEN` or `GH_TOKEN` first,
  then the credential docker itself holds (`credsStore`/`credHelpers`, then the
  plain `auths` entry). Every package here is private, so an anonymous read
  answers 403: a probe that fell through to one would report every blob of every
  image as unreachable — a red about the credential wearing the clothes of a red
  about the image. With no credential the verb REFUSES and names the variables,
  because a skip would be a green that checked nothing. Each publish job passes
  `GITHUB_TOKEN` to the step, the same secret it pushed with.
- **The attestation manifests are deliberately NOT walked.** buildx attaches 1
  per variant, and `docker pull` never fetches one, so a dangling attestation
  blob does not make an image unpullable. Widening the walk is a decision about
  what "published" means here, not an oversight.
- **A walk that probes nothing FAILS.** An index with no image variant, a
  manifest with an empty layer list, and a variant that yielded fewer digests
  than its own manifest declares are each a refusal — 0 failures out of 0 probes
  is a verdict about nothing.

The guard `require_buildx_and_platforms` is in `_ctl/lib.sh`, 1 time only, and it
runs at the start of every per-image `push`. It fails closed in 5 conditions: a
platform outside the sanctioned set, an empty platform list, buildx absent, no
buildx builder active, or the active builder unable to build 1 of the required
platforms. The first condition is `require_sanctioned_platforms`, which `build`
also uses.

The list of platforms an image builds is `IMAGE_PLATFORMS`, and it has 3 sources
in falling precedence: the ENVIRONMENT, the image's own `platforms` key in
`images.yaml`, and `SANCTIONED_PLATFORMS`. An image may declare a measured
NARROWER list; it may not declare a wider one, because every entry still has to
be sanctioned — `mobile` is the 1 image that declares one today, and the
section above carries its measurement. `IMAGE_PLATFORMS` was called
`MULTI_ARCH_PLATFORMS` until the arm64 drop, and a tripwire in the library fails
at source time if the old name is still set — both names would hold the same
string, so a missed rename would otherwise be silent.

The repository-root `ctl.sh` does **not** call the guard. It sends `push` to the
per-image `ctl.sh`, which calls the guard with its own list. The root script
cannot call the guard correctly, because the list is not the same for every
image. Do not add a call to the guard there.

The CI workflow enforces the same policy. It sets up buildx, builds with
`--platform ${{ env.PLATFORMS }} --push`, and then runs `verify-published`
against the SHA tag it just pushed. It sets up no QEMU, and that is still true
with 2 platforms: each one is built on a node of its own architecture — amd64 on
the pool, arm64 on the mini `.ci/buildx-node.sh` appends — so nothing is
emulated and nothing needs to be.

**Every** job builds **twice**, and the order is the point. The first build sets
`push: false` + `load: true`, so the image goes into the local image store and
not to ghcr.io. The smoke test then asserts the content of that loaded image.
Only then does the second build push, from the cache the first one wrote. A push
cannot be undone and no job here rolls one back, so a check that runs after the
push reports a broken image but cannot stop one from reaching a consumer.
`_ctl/tests/publish-order.test.sh` holds that order in the pull request gate, and
it fails any job that publishes without a smoke step.

**The 2 builds no longer name the same platform list, and that is the shape of
this phase.** `load: true` takes 1 platform — buildx writes a manifest LIST for
2 and the docker image store holds a single image — so the gate build names
`SMOKE_PLATFORM`, `linux/amd64`, the architecture the pool runs natively and the
only one whose version checks can execute without emulation. The publish build
names the full `PLATFORMS`, takes its amd64 layers from the cache the gate wrote
and builds every other leg on the node for it.

**So the arm64 content of every image is NOT smoke-gated at publish time.** The
amd64 smoke gates the publish for both variants; the arm64 variant ships on the
same build definition, the same pins and the per-download digest comparison, and
`verify-published` asserts afterwards that the manifest carries both. That is a
stated gap and the recorded follow-up: smoking arm64 out of the registry after
the push. It is not a line to add — the arm64 note at the top of
`publish-order.test.sh` explains why a throwaway-tag push would make that test
report a FALSE RED, and taking that route is a decision about what "publish"
means to this repository.

**REHEARSAL MODE is what makes that gap testable before a merge.**
`workflow_dispatch` on `build-and-push.yml` takes a `mode` input, `publish` or
`rehearsal`, and `publish` is the default. In rehearsal every job runs its gate
build and its amd64 smoke unchanged, then runs the publish-shaped build with the
same context, the same build-args and the same per-image `PLATFORMS` on the same
builders — the mini included — with `push: false`, and the manifest read-back is
skipped because nothing was pushed. So the arm64 build that only happens at
publish time can be exercised on a branch, with no tag moved.

- **`inputs.mode` is empty on a `push` event**, and empty is not `rehearsal`, so
  a push to main behaves exactly as it did before the input existed. The gates
  are written `!= 'rehearsal'` for that reason: `== 'publish'` would make every
  push to main take the rehearsal branch and ship nothing, green.
- **It is 2 STEPS and not a `push: ${{ ... }}` expression.**
  `_ctl/tests/publish-order.test.sh` finds a publishing step by the LITERAL line
  `push: true`, and the whole smoke-gates-publish rule rests on that detector. An
  expression there would make every job read as a job that publishes nothing, and
  the rule guarding the irreversible action would pass while checking nothing.
- **Both gates OPEN with `steps.filter.outputs.build`.** That test reads the
  FIRST `steps.<id>.outputs.<key>` on an `if:` line as the gate a step carries,
  so the mode condition is appended and never prepended.
- Both steps sit AFTER the smoke, so the ordering rule holds in either mode.

**A rehearsal proves each image's own content. It does NOT prove the
child-at-NEW-parent seam, and that limitation is structural.** A child job FROMs
`ghcr.io/gophersys/<parent>:<sha>`, and a mode that publishes nothing never
creates that tag — so in rehearsal `BASE_TAG` resolves to `latest`, the parent
that is currently published, and every other event keeps the expression it always
had (`built == 'true'` → the short sha, otherwise `latest`).

Rehearsal #2 (run `32114973844`) is the measurement, and it is why the input
needed a second hunk rather than a note: `base` and `cloud` went GREEN on both
platforms with the mini in the builder — the shape works — while `zephyr` and
`flutter` died resolving `ghcr.io/gophersys/base:69b4f11`, a tag no rehearsal had
pushed.

So the 2 modes prove different things, and neither is redundant:

- **rehearsal** — every image's own layers build on every platform it publishes,
  against the parent that is live today. Cheap, branch-safe, nothing ships.
- **publish** — the same, PLUS the child-at-new-parent seam, and that seam is
  smoke-gated because the child's gate build and its smoke run before its push.

Closing the seam in rehearsal would mean pushing the parent to a quarantined tag
for the children to FROM, and this repository deliberately does not do that: a
throwaway push is a `push: true` step that runs before the smoke, which the arm64
note at the top of `_ctl/tests/publish-order.test.sh` measured as a FALSE RED
against the rule that guards the irreversible action.

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

**3 classification TABLES read `versions.env`**, and the branch that chooses
between them is all that is left of the family split: `cloud` takes the table
that asserts the CI fold, `base`/`mobile`/`embedded` take the
table that asserts what `base` installs, and `hardware` takes
`PIN_CLASSES_HARDWARE` — the cloud table with the 5 KiCad rows flipped to
`asserted`, because it inherits every tool of cloud through its `FROM`. A pin one image does not carry takes
`not-in-this-image` in that image's table, which is what the class exists for.

**A CHILD image reads a second home: its own Dockerfile — except `hardware`,
which has no second home to read.** Its Dockerfile declares every pin
value-less, so there is no value in it for any reader to find, and 1 home is the
whole of it. `mobile` and `embedded`
each carry a class table of their own — `PIN_CLASSES_MOBILE` and
`PIN_CLASSES_EMBEDDED` — over the value-ful `ARG`s of their
own file, and every rule of the `versions.env` home applies there unchanged: an
unclassified pin refuses the run before a container starts. `home_pin_names` in
`.ci/smoke.sh` therefore holds 2 readers again, and this pair is not the pair
that went away — the old second reader read `base/Dockerfile`, which declares no
value at all now. `CODE_SERVER_VERSION` is the pin that showed why: read on
2026-08-17, `ghcr.io/gophersys/zephyr-devbox:latest` reported code-server 4.127.0
while `zephyr-devbox/Dockerfile` pinned 4.133.0, and until that table existed no
class, no test and no run in this repository could say so. **That pin is deleted
now** — the devbox deletion of 2026-08-19 took the binary with it — and the
lesson it bought is why the table it created stays.

**1 thing is deliberately outside the child home**, and it is named in the
driver. `runner/Dockerfile` was the other, and it is deleted rather than
excluded: a table for an image no run can name would have been dead text, and so
was the file. What is left is the pins a child inherits
from ANOTHER child. `zephyr-devbox` built `FROM zephyr` and carried west and
the Zephyr SDK while `WEST_VERSION` lived in `zephyr/Dockerfile`, so the devbox
run asserted esptool and code-server and NOT those 2 — and that instance is gone
by CONSTRUCTION rather than by a fix: the 2 images are `embedded`, so 1 home and
1 table cover every pin either of them declared. **The hole itself is open**, and a child of a
child would meet it again. Closing it needs the
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
probe that can never fire is a check that cannot fail. `KIUTILS_VERSION` and
`SEXPDATA_VERSION` joined that set with the hardware image, for the same kind of
reason: both are import-only python libraries and neither ships a console
script, so the hardware run asserts them through `importlib.metadata` and the 2
parent tables carry them bare. The driver refuses to run
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
Container" then lists `base`, `cloud`, `mobile`, `embedded`, `hardware` and
`ui` as configurations that you can select — 6 files, 1 for each image. Each
configuration bind-mounts the project to `/workspace` and runs as the `dev`
user.

**`ctl.sh validate` holds every `*/devcontainer.json` to 6 properties**, and
until that pass was written these 6 files were read by NOTHING in this
repository — no verb, no test, no workflow opened one, so a typo in an image ref
reached a developer's "Reopen in Container" and nowhere earlier. The 6 are
`jq .` parses, `.image` matches `ghcr.io/gophersys/<name>:latest`,
`.remoteUser` is `dev`, `.workspaceFolder` is `/workspace`, the image set of
`images.yaml` and the devcontainer set are ONE set in BOTH directions, and
`.image` is the ref of the directory the file sits in — the contract this
section states. The pass FAILS naming the file and the property, and it fails
when the glob matches zero files, because a check that opened no file is not a
check that passed. It finds the files by glob and not by `BUILD_ORDER`: a
directory outside `BUILD_ORDER` would otherwise take an unchecked
`devcontainer.json` the day somebody added one, which is what `runner/` would
have done for as long as it sat on disk retired.

**The last 2 are the local/CI 1:1 workflow, and they are SET rules that no
single file can answer.** The workflow is 1 sentence: a developer opens the SAME
published `:latest` a CI job runs, the amd64 leg on the pool and the arm64 leg on
the Mac, out of 1 manifest list that 1 publish wrote. Property 5 is why the
first 4 are not enough — an image of `images.yaml` with no `devcontainer.json` is
an image nobody can open locally, and a `devcontainer.json` in a directory no
image declares points at a ref nothing here builds or pushes, which is what
`runner/` would have carried. Property 6 is the half the SHAPE rule cannot see:
`ghcr.io/gophersys/second:latest` inside `first/` matches
`^ghcr\.io/gophersys/[a-z-]+:latest$` exactly, and it hands the developer a
container that no CI job of `first/` has ever run. Both refusals name the
directory and the remedy, and property 6 names both refs, because 2 refs of this
repository leave a reader no way to tell which direction the mistake goes in.

**`mobile` is the 1 exception to the workflow, and it is STATED rather than
fixed.** It publishes `linux/amd64` alone, so an arm64 host emulates that variant
or does not open the image locally, and the developer's architecture then
disagrees with every CI job of it. The reason is upstream's and not ours — see
the mobile subsection of the platform policy above — so the rule is that the
exception is named where a developer reads the workflow. `README.md`
"### The local/CI 1:1 workflow" is that place, and
`_ctl/tests/platform-policy.test.sh` holds its `ARM64_LOCAL_EXCEPTIONS` literal
to SET EQUALITY with the rows of its platform table that carry no `linux/arm64`.
So an image that loses its arm64 variant with no name in that section is red, and
a name there that describes no narrowed image is red too.

**`postCreateCommand` is deliberately NOT the 7th property. 1 of the 6 files
declares it, and the other 5 must not.** The property is not symmetry; it is
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
- **`mobile`, `embedded`, `hardware` and `ui` must not either**, and
  for a different reason: each one is a thin dispatcher that sends every verb to
  `image_main`, and `_ctl/lib.sh` has no `post-create`. A `postCreateCommand`
  in one of those 4 files would name a verb that nothing answers — the dead-path
  class this document opens with. Their toolchains are baked, which is what an
  image is for.

Adding a `postCreateCommand` to an image is therefore 2 edits and not 1: the
`devcontainer.json` line, and the verb that answers it.

`embedded/embedded-entrypoint.sh` is PID 1 of that image, and reading it takes
under a minute now: it execs the argv docker hands it — the image `CMD` when the
caller named none — as `dev`, and it does nothing else.

1. **At euid 0 it drops through `runuser -u dev --`.** The image ships
   `USER root`, so this is the arm every plain `docker run embedded` takes, and
   it is what reproduces the `USER dev` line the pre-fold Dockerfile carried:
   `docker run embedded id` answers `dev`. Plain `runuser`, deliberately NOT
   `--preserve-environment`, which would keep `HOME=/root` while the toolchain's
   caches and oh-my-zsh live in `/home/dev`.
2. **At any other euid it execs plainly.** `runuser` REFUSES below root — "may
   not be used by non-root users" — so an arm that always ran it would turn
   `docker run --user dev`, which `.ci/smoke.sh` itself uses, into an error.
3. **An EMPTY argv EXITS 2**, naming the cause. The image declares `CMD`, so
   reaching that needs a caller who replaced `CMD` with nothing, and `exec` with
   no argument is a NO-OP in bash: the script would simply end and hand the
   caller a container that started nothing and reported success.

That list had **7 steps**, and the other 4 were the pod: host keys into
`/etc/ssh/hostkeys`, mountpoint ownership, `authorized_keys` from
`DEVBOX_AUTHORIZED_KEYS`, the `/dev/mcu-slot-N` links, code-server on `:8443`
behind an auth knob, and `exec sshd`. **They are deleted** — see the section
below. So is the `/run/devbox-degraded` marker: its only reader was a probe
against a pod that reported Running, and a file written into a container that is
exiting is state nothing can read.

## The devbox mode is deleted

**The decision.** Mateo, 2026-08-19, verbatim: *"yes strip and delete and clean
up anything devbox we don't need any of it anymore."* That order is the
authority for this section, and it REOPENS 2 recorded decisions — the
`content-devbox` check group the embedded fold deliberately kept ("`DEVBOX_*`
keeps its spelling", below), and the `size_budget_gb` row set the day before
against an image that included the devbox layers.

**The premise, verified rather than assumed.** `GOPHERSYS_EMBEDDED_MODE`
appeared in 9 places org-wide and every one was inside this repository. Read on
2026-08-19: GitHub code search over `org:gophersys` returns 0 for
`GOPHERSYS_EMBEDDED_MODE`, 0 for `DEVBOX_` and 0 for `code-server`, and a
`git grep` of `origin/main` in `gophersys/infrastructure` finds no
`DEVBOX_AUTHORIZED_KEYS`, no `DEVBOX_CODE_SERVER_*` and no `devbox-degraded`.
The last consumer was the `zephyr-devbox` Deployment, deleted in infrastructure
#192. **No manifest, no workflow and no pod set the mode**, so both arms of the
dispatch were reachable only from this repository's own tests.

**What went, by surface.** The mode dispatch and every statement below it in
`embedded/embedded-entrypoint.sh` (~150 lines of 240); the `DEVBOX_*` env
contract; `/run/devbox-degraded`; `openssh-server`, the
`/etc/ssh/sshd_config.d/10-gophersys-devbox.conf` drop-in, `/etc/ssh/hostkeys`
and `/etc/devbox`; the code-server `.deb` and its baked clangd extension seed;
`EXPOSE 22` and `EXPOSE 8443`; `CODE_SERVER_VERSION` with its 2 digest rows and
its `_build/upstreams.txt` row; the `content-devbox` check group in both
`images.yaml` and `.ci/image-checks.sh`; the `CODE_SERVER_VERSION` row of
`PIN_CLASSES_EMBEDDED`; and the 5 tripwire stubs under
`_ctl/tests/stubs/entrypoint/` that existed to catch a fall-through into a pod
path that no longer exists.

**What STAYED, and why it is not devbox.** `openocd`, `stlink-tools`,
`picocom`, `gdb-multiarch`, `clangd`, the esptool venv, the Espressif Xtensa
toolchains and both udev rule files. Every one is a tool a developer runs INSIDE
the container and CI runs in the same image — none of them was reached only over
SSH. `clangd` is the one that looks like a devbox tool and is not: the VS Code
clangd extension in a "Reopen in Container" session drives that same binary, and
only the code-server-side extension SEED was pod-specific. The
`99-gophersys-devbox.rules` file is renamed `99-gophersys-usb-uart.rules` —
udev reads the directory and nothing reads the name, so a rules file named after
a deleted mode is a stale reference and not a contract.

**2 check groups became 1.** `content-zephyr` and `content-devbox` existed
because there were 2 IMAGES. The deletion removed only the pod's own checks —
code-server, its seeded extension, and the 3 `sshd -t` steps — and every
surviving check is toolchain content, so they are 1 group under the name whose
content stayed. `_ctl/tests/images-manifest.test.sh` holds the manifest's group
set and `run_functional_groups`' arms to SET EQUALITY, so dropping the group
from one of the 2 files and not the other is red.

**The size budget is NOT lowered here, and that is deliberate.** `8.98` was set
on 2026-08-19 from a measurement of the image WITH the devbox layers. The
pre-fold devbox delta measured 1.504 GB, but that delta also held esptool, the
Xtensa toolchains and the flash/debug stack — all of which stay — so the saving
is a fraction of it that no measurement in this repository answers for. Writing
a new row from arithmetic on a number that measured something else is exactly
the stale row ledger #119 was about. The row stood for exactly one publish, as
instructed: run 32231070482 (2026-08-19) measured the stripped image at
7,760,642,048 unpacked bytes, and the row is 8.15 now — that measurement + 5%,
reset in a change of its own. The deletion returned 0.78 GB of the 1.504 GB
pre-fold delta, which is why the arithmetic was refused and the measurement
waited for.

**The entrypoint SURVIVED the deletion, and its test was rewritten rather than
deleted.** `USER root` + a dev-drop is still what makes `docker run embedded id`
answer `dev`, and `_ctl/tests/embedded-entrypoint.test.sh` is the only thing in
this repository that exercises the euid-0 arm — `.ci/smoke.sh` runs the image
with `--user dev` and reaches the other one. The file went from 39 checks to 29:
every check about the pod arm went with the code it read, and 3 new ones took
their place — the deleted mode variable proved INERT at both euids, no devbox
surface back in the entrypoint's code, and none back in the Dockerfile's
instructions. Those are guards against a revert, and they are the reason the
literals `GOPHERSYS_EMBEDDED_MODE` and `devbox` are still spelled in that file.

**What is left as OPEN WORK, stated so nobody reads it as done.** With sshd gone
nothing in this image needs root at runtime, so `USER root` + the entrypoint
could collapse into a plain `USER dev` with no entrypoint at all. That is a
SECOND decision: it also removes `.ci/smoke.sh`'s embedded-only `--user dev`
arm and the identity sentences 2 other files state. It is recorded at the top of
`embedded/embedded-entrypoint.sh` and it is not part of this change.

## Per-image verb catalog

| Verb | Action | Cache |
|---|---|---|
| `build` | `docker build --platform "$IMAGE_PLATFORMS"` | false |
| `push` | `docker buildx build --platform "$IMAGE_PLATFORMS" --push` (guarded) | false |
| `verify-published [tag]` | read the published manifest; it must carry exactly `$IMAGE_PLATFORMS` — the image's OWN set, which is the sanctioned set unless `images.yaml` narrows it. Held against `SANCTIONED_PLATFORMS`, mobile's correct amd64-only manifest reads as a broken publish forever. A platform the image does not publish is refused too, so the rule is equality and not "at least". THEN walk each published manifest and prove every blob it references SERVES, with a ranged GET of 1 byte; a non-2xx names the image, the platform, the digest and the status. | false |
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
| `validate` | shellcheck every shell script, assert every per-image `ctl.sh` the manifest names is executable, jq, the `devcontainer.json` contract, hadolint at the pinned version, ARG-discipline checks, the zsh-`$USERNAME` trap |
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
        base                cloud
     ┌───┴────┐         (FROM ubuntu)
 mobile   embedded     ┌────┴────┐
                     hardware    ui
```

That drawing is prose. `images.yaml` is the graph, and this is what the machine
reads:

```yaml
images:
  base:          { parent: "",       paths: [...], groups: [...] }
  mobile:       { parent: base,     platforms: [linux/amd64], ... }
  embedded:      { parent: base,     size_budget_gb: 8.15, ... }
  cloud:         { parent: "",       size_budget_gb: 5.75, ... }
  hardware:      { parent: cloud,    pins: versions.env, size_budget_gb: 10.52, ... }
  ui:            { parent: cloud,    pins: versions.env, size_budget_gb: 6.33, ... }
```

**3 keys are OPTIONAL, and for each one ABSENT IS A DECISION.** `platforms`
narrows the sanctioned set and may never widen it; `pins` names the pin home a
build feeds in as generated `--build-arg`s, and an absent key keeps the older
rule (a root image reads `versions.env`, a child reads its `BASE_TAG` alone);
`size_budget_gb` declares an acceptance size budget, and an absent key means no
size gate. `_ctl/lib.sh` reads all 3 by POSITION — fields 8, 9 and 10 of the flat
record — so read the record shape at `image_records` before you add a fourth.

**The BASIS of every `size_budget_gb` is UNPACKED bytes**, and this document
carried no sentence saying so until now (ledger #119). The gate reads the sum of
`docker history --human=false --format '{{.Size}}'`, in
`image_unpacked_size_bytes` in `.ci/smoke.sh`. It was
`docker image inspect --format '{{.Size}}'`, and that template answers the
COMPRESSED content size on a containerd-store daemon — the store the arc-build
dind switched to with no commit here — so for 2 days 3 budgets were compared
against a number 3.4x to 4.2x under them and none of the 3 could fail. Read the
BASIS of a log line before comparing it to a budget: a line that does not say
`unpacked bytes` predates 2026-08-18 and is in the other unit. The measurement
that set each budget is beside its own key in `images.yaml`, never here — a
number in this file is a number that goes stale, which is exactly what 11.0 and
6.5 did in the 2 rows above.

`validate.yml` runs `bash ./ctl.sh validate`, then `bash ./ctl.sh test`, then
asserts that BUILD_ORDER agrees between `ctl.sh` and `.ci/ctl.sh` — a step that
can no longer fail, for the reason stated below. `.ci/ctl.sh validate` delegates
to the root `ctl.sh`: it used to be a second copy and the 2 diverged, so it
reported OK on a Dockerfile that the root script rejected.

**The graph is declared ONCE, in `images.yaml` at the repository root.** That
sentence used to read "the graph is declared in 6 files. All 6 MUST stay the
same", and the 6 were held to each other by tests. The declaration is 1 file
now, and the homes below are DERIVED from it rather than kept beside it:

1. `BUILD_ORDER` in `./ctl.sh` and in `.ci/ctl.sh`. Both arrays are filled at
   source time from `image_names` in `_ctl/lib.sh`, which reads the manifest.
   Document order in `images.yaml` IS build order, and `image_names` refuses a
   manifest that writes a child above its parent — so the order is a checked
   property and not a convention.
2. `image_parent()` and the input path table, both in `_ctl/lib.sh` and read by
   `.ci/affected.sh`. That file carried a copy of each. A child's input set has
   to CONTAIN its parent's: that inclusion is what makes "the parent built, so
   the child builds" true by construction, and `image_input_paths` walks the
   manifest's `parent` edge to produce it.
3. The check groups, `image_check_groups` in `_ctl/lib.sh`, read by
   `.ci/smoke.sh`. That file carried a case table of its own.
4. `needs:` in `.ci/providers/github/build-and-push.yml`, which
   `_ctl/generate.sh` emits from the manifest — 1 job template applied to each
   entry, so the 6 jobs cannot drift apart. The file carries a GENERATED header
   naming the generator and the manifest.
5. The `image:` line of the nightly scan matrix, rewritten in place by the same
   generator. The rest of `security-nightly.yml` is hand-written, because the
   trivy pin and the waiver rules are not image facts.
6. `.github/workflows/` holds a hand-made COPY of each provider file, and
   `_ctl/tests/platform-policy.test.sh` compares the pair with `cmp`. That copy
   is not a home in its own right any more — it is the output of a copy — but
   the `cmp` stays, because a reader who edits one of the pair still drifts the
   pair. It caught nothing twice before it existed: once the provider file was
   an old copy that listed only 3 images, and once commit `d9089b2` added 5
   `timeout-minutes: 90` blocks to the workflow and to neither copy.
7. `dependsOn` in each image's `project.json`, and the image's
   `devcontainer.json`. These are still HAND-WRITTEN. Generating them is the
   next slice of this work and is not done.

**The policy tests keep their hand-kept literals, and that is deliberate.**
`SANCTIONED` in `platform-policy.test.sh`, `EXPECTED_PROVIDER_FILES` beside its
glob, the governed-file lists in `dockerfile-args.test.sh` and
`download-coverage.test.sh`: a test that reads the value it checks agrees with
any value, a wrong one included, so none of them may read `images.yaml`. What
they owe the manifest is set EQUALITY — a literal list that no longer matches
the manifest is a red test — and that check is what replaces the hand-copying.

**The BUILD_ORDER agreement step in `validate.yml` is now VACUOUS.** It greps
`^BUILD_ORDER=(...)` out of both control scripts and compares the 2 strings;
both read `BUILD_ORDER=()` today, so it compares 2 equal literals and can no
longer fail. It is left in place with this change and its replacement is open
work: the check worth having is "the manifest parses, its order is a valid
topological order, and every policy-test literal equals its set". A step that
cannot fail is exactly the believed-and-empty check this repository refuses
elsewhere, so it does not get to stay unnamed.

**1 file still says 4**: the `fail_check` evidence string in
`_ctl/tests/publish-order.test.sh`. That number was correct before
`image_parent()` and before the `cmp`. It belongs to the wave that owns the
tests; this document is the count it must take.

That `cmp` covers **every** file of `.ci/providers/github/`, found by a glob, and
not `build-and-push.yml` alone. The narrow version had the same hole 1 level up:
a second provider file got no check at all on the day it was added, and
`security-nightly.yml` is that second file. A glob that stopped matching would be
a green result that read nothing, so the same test holds a literal list of the
directory — **add or rename a provider file and you edit
`EXPECTED_PROVIDER_FILES` in `_ctl/tests/platform-policy.test.sh` in the same
change.** The direction is provider → workflow: `validate.yml` and `pr-review.yml`
are provider-native and have no source-of-truth copy.

## The embedded fold

**READ "The devbox mode is deleted" ABOVE FIRST.** This section is the record of
how `embedded` came to hold both halves, and the pod half is gone since
2026-08-19. Everything below is history, kept because the fold's measurements and
its ledger-#102 finding are still what a reader needs. The fold is also what made
the deletion 1 file to edit instead of a second image to retire.

`zephyr` and `zephyr-devbox` are 1 image, `embedded`. The devbox was the
toolchain plus 9 layers, so the split carried ~1.5 GB of delta at the cost of a
second publish job, a second pin home, a second class table and a second nightly
scan — measured on 2026-08-18 through the ghcr.io registry API, amd64, summing
the per-layer gzip ISIZE trailers: `zephyr` 6,741,148,672 bytes and
`zephyr-devbox` 8,244,974,080.

**It also cost a CHECK, and that is the reason the fold happened rather than the
saving.** `.ci/smoke.sh` reads a child image's OWN Dockerfile as its second pin
home, and `zephyr-devbox` declared esptool and code-server there while west and
the Zephyr SDK lived in the PARENT's file. So the devbox run compared 2 of the 4
pins its image carried, and nothing in this repository could say so — the
inherited-pin half of ledger #102. 1 home and 1 table carried all 7 rows after
the fold, and the 4 `asserted` ones were compared in a single run. It is 6 rows
and 3 asserted since the devbox deletion took `CODE_SERVER_VERSION`. **This
closes #102 for this family and for no other**: `mobile` inherits base's pins
the same way, and the general fix is a `FROM`-graph walker in the driver, which
is still open.

**1 image cannot carry 2 users, so the identity moved out of the Dockerfile.**
`embedded` ships `USER root` — at the fold, because the pod half bound sshd and
managed host keys — and `embedded/embedded-entrypoint.sh` drops to `dev` before
it execs the command. That is a CONTRACT CHANGE with a stated shape:
`docker run embedded id` prints `dev` as it always did, `docker run --user dev
embedded` must NOT reach `runuser` (it is unprivileged there and would refuse),
and `.ci/smoke.sh` takes the second of those 2 paths. The euid test in the
entrypoint is what makes both callers work, and
`_ctl/tests/embedded-entrypoint.test.sh` is where both arms are proven — on the
host, because the smoke's own argv reaches only the non-root one. **The REASON
for `USER root` left with the pod half and the LINE did not**; collapsing it
onto `USER dev` is the open work the deletion section names.

**`DEVBOX_*` kept its spelling at the fold**, and so did the `content-zephyr`
and `content-devbox` check groups: those names described the pod's env contract
and the CONTENT a group exercises, neither moved, and renaming them would have
reached into running pods for nothing. **That paragraph is history.** `DEVBOX_*`
and `content-devbox` are DELETED, not renamed — see "The devbox mode is
deleted" above — and `content-zephyr` is the 1 content group of this image.

**`ghcr.io/gophersys/zephyr` and `ghcr.io/gophersys/zephyr-devbox` are the
rollback anchors.** Their `:latest` freezes at the last publish before this
merge, and the nightly stops scanning them the moment the matrix regenerates —
so an unscanned image stays pullable, on purpose, until a green `embedded` has
run in the cluster. Deleting either package is Mateo's decision alone.

## The mobile rename

`flutter` is `mobile`. One name per category — the last naming step of the
consolidation program (ledger #94), and a rename of the IMAGE and nothing else:
the Dockerfile's layers, its pins and its amd64-only `platforms` key are byte
for byte what they were.

**The SDK is named flutter, and the SDK did not move.** That is the whole rule
for reading a `flutter` that survives in the tree. `FLUTTER_VERSION`,
`FLUTTER_CHANNEL` and `FLUTTER_SHA256_AMD64` are pins of the Flutter SDK;
`/opt/flutter` is where it installs; `flutter --version` is its binary;
`flutter-releases` is the datasource that reads its release index; and
`content-flutter` is the group that runs that binary. None of them is an image
name, so none of them changed. `content-flutter` keeping its spelling is the
rule the embedded fold states above, applied again: a group names the CONTENT
it exercises.

**A rename here is a set-equality problem, not a search-and-replace.** The
policy tests keep hand-kept literals on purpose, so the manifest key alone made
26 checks red across 11 test files — `dockerfile-args` 2, `download-coverage` 3,
`images-manifest` 2, `platform-policy` 4, `publish-order` 5, `resolve-upstream`
1, `scheduled-workflows` 2, `upstream-coverage` 2, `verify-published` 2,
`version-coverage` 2, `zsh-username` 1. That red run is the proof the suite
guards the set; a rename that produced no red would mean nothing enumerated the
images. Read the list, never this count — the next rename measures its own.

**`ghcr.io/gophersys/flutter` is the rollback anchor.** Its `:latest` freezes at
the last publish before this merge and no run moves it again. The `mobile`
package does not exist until the first publish after the merge, so a consumer
that has not re-pinned still pulls a working image. Deleting the `flutter`
package is Mateo's decision alone.

**2 sentences in this file still name the IMAGE `flutter`, and both are
CORRECT**: the 2-arch publish measurement and the rehearsal-#2 record name the
image as it was called on the day it was measured, beside `zephyr`, which no
longer exists either. A measurement whose subject is renamed under it stops
being a measurement. Every OTHER surviving `flutter` in this file is the SDK —
its pins, its path, its binary, its datasource — by the rule above.

## The `+ runner` layer is retired and deleted

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

**This section is a historical record now, and nothing is left.** The 3 facts a
reader needs:

- **`runner/` is DELETED**, on 2026-08-18, under Mateo's D2 decision: the CI
  fold lives in the shared parent, so the parent-plus-runner-layer image
  directory has no future role. It sat on disk retired between the two dates,
  which is the state convention 2 above describes and warns about — nothing
  built it, and 4 mechanisms plus 5 test files still read it.
- **Its content is not lost.** `_delta/components/runner.sh` installs the
  Actions runner and cictl into `cloud`, and `_delta/components/agents.sh`
  installs claude — the same 2 downloads `runner/Dockerfile` performed, at the
  same URLs, from the same `versions.env` pins. The audit that preceded D2
  compared them line by line.
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
images — a different 6, with `base-runner` in it and `cloud` and `hardware` out
— and the number is kept because the budget argument does not depend on the
count.

- **No job may install a free-disk action.** That action reclaims space by
  deleting the preinstalled SDKs of a throwaway hosted VM. On `arc-build` the
  same deletion strips the NODE, and the blast radius is every pod on it. A
  build pod takes its headroom from the `work` volume the scale set sizes.
  `_ctl/tests/workflow-yaml.test.sh` holds both halves — every `runs-on:` in
  both workflow directories, and the absent action.
- **Only what changed is built.** Each job of `build-and-push.yml` asks
  `.ci/affected.sh <image>` whether the commit touches that image's inputs and
  gates its build, smoke, push and manifest read on the answer. The path table
  lives in `images.yaml`, and that script derives its answer from it through
  `image_input_paths`. Everything builds on `workflow_dispatch`, on a tag, and
  on any change to a workflow or to `.ci/`. **An unbuilt image keeps its
  `:latest` and publishes no `:<sha>` for that commit** — a SHA tag is not a
  promise that every image carries it.
- **A publish QUEUES behind the run in flight. It does not cancel it.**
  `build-and-push.yml` declares `cancel-in-progress: false` on the group
  `build-and-push-${{ github.ref }}`. Cancelling cost the image rename on
  2026-08-19: the publish run was killed part way through, the run that
  superseded it asked `.ci/affected.sh` about a range starting at the killed
  push's own head, every image read as unaffected, and
  `ghcr.io/gophersys/mobile` was never created while 6 badges went green.
  **It is a MITIGATION and the hole is narrower rather than closed** — GitHub
  keeps at most 1 PENDING run per group, so a third push replaces the queued
  second and that push's changes are skipped the same way. The durable fix is
  the `org.opencontainers.image.revision` read-back the workflow header defers.
  `_ctl/tests/workflow-yaml.test.sh` holds this value, and holds every other
  workflow at the concurrency it declares today: `pr-review.yml` CANCELS on
  purpose, because a review of a diff that has already changed is spend with no
  reader, and the other 3 declare no group at all.
- **The layer cache is in the registry**, `ghcr.io/gophersys/<image>-cache`, one
  package per image, `mode=max` on the write. `type=gha` is 10 GB per repository
  across every scope, which 6 images at `mode=max` do not fit.
- **The builder is `.ci/buildx-node.sh`, not `docker/setup-buildx-action`.** It
  owns the switch that appends the Mac mini as a native arm64 node when
  `SANCTIONED_PLATFORMS` names `linux/arm64`. That switch READS the library, so
  it took no edit of its own when the set widened. **It is live now**, and the
  first dual-arch build is the mini's first real work: an unreachable mini, an
  expired client PEM or a stopped buildkitd surface at the `--bootstrap` that
  step ends with, naming the node and the endpoint.
- **The builder has ONE driver, `remote`, and that was learned the hard way.**
  The file made a `docker-container` builder and appended the mini with
  `--driver remote`; buildx refuses a builder whose nodes disagree —
  `ERROR: existing instance for "gophersys" but has mismatched driver
  "docker-container"` — and rehearsal run `32111891941` died there. The bug was
  invisible until arm64 was sanctioned, because the append sits inside the
  switch that only fires when it is. So the LOCAL node is a remote node too: a
  buildkitd container the script starts itself from `BUILDKIT_REF`, in the pod's
  network namespace, listening on `tcp://127.0.0.1:18234` with
  `--oci-worker-net=host` — the same flag the old driver got through
  `--buildkitd-flags`. It is pinned to `linux/amd64`, because buildkitd
  advertises every platform it can EMULATE and an unpinned local node would
  volunteer for the arm64 half and build it under QEMU.
- **That local endpoint is plaintext TCP, and the threat model is stated.**
  `--network host` is the POD's namespace: the runner, dind and this buildkitd
  share it and nothing outside the pod has a route to that loopback address, so
  the peers that can reach the BUILD API are exactly the peers that can already
  run commands in the build. The `docker-container` driver it replaces was
  reachable through the docker socket the job already holds — the boundary did
  not move. The MINI is the opposite case and keeps its mTLS, because that
  endpoint is on the tailnet.
- **Re-running the builder step REMOVES and recreates.** `docker buildx create
  --name <existing>` fails even when the driver matches (measured, rc=1), and
  reusing whatever is there is the other trap: a builder left by a run that died
  between the create and the append carries the wrong node set, and the next
  build would silently target one architecture.
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

### Attribution — identity in the record

**Mateo's ruling, 2026-08-25 (D5): ATTRIBUTION IS IDENTITY.** It REVERSES the
rule this section used to carry, which forbade every AI trailer. An unattributed
agent commit reads as a human's, and that is a false record.

- **Solo agent work** is authored `Claude <claude-agent@gophersys.noreply>`,
  with no trailer.
- **Joint interactive work** is authored Mateo, with a `Co-Authored-By: Claude`
  trailer.
- **An agent NEVER commits, approves or comments as "Mateo".** An agent's pull
  request comment identifies itself and NAMES THE AUTHORITY it acts under.
- These govern the git AUTHOR field and only that field. The COMMITTER stays the
  human account whose credential does the push, because an agent has no GitHub
  identity of its own yet. A commit today therefore reads `author=Claude`,
  `committer=Mateo Segura`. That is the honest current state and not an
  oversight; actor-level separation is eden task #138.

**The single home is `gophersys/eden` `.claude/rules/git-process.md` §13
(ADR-0032).** Read it there. The lines above are this repository obeying that
rule, not a second home for it — if the two ever disagree, §13 wins and this
section is the stale one.

**Why this file needed the edit at all.** §13's own closing lesson is "when a
rule changes, sweep EVERY subject across EVERY ring — root files first, because
the root is what loads". The D5 sweep closed four files inside eden and stopped
at that repository's edge. This file is the next ring: Convention 3 forbids a
`CLAUDE.md` here, so `.claude/rules/00-identity.md` IS this repository's
always-loaded root, and it carried the reversed rule after the reversal. An
agent reading only what is loaded for it would have obeyed the dead rule.
