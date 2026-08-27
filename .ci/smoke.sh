#!/usr/bin/env bash
#
# .ci/smoke.sh — post-build smoke test for a single image.
#
# Dockerfiles in this repo deliberately do NOT run `bw --version`,
# `gh --version`, etc inside RUN steps: those binaries are built for the target,
# and they could not run while an image was cross-built under QEMU. This script
# re-introduces those checks as a post-build step that runs the already-built
# image. Nothing is cross-built any more.
#
# It prefers to run the image NATIVELY, for that same reason, and the platform
# resolver below is what makes that the default. On a developer host of another
# architecture it runs the sanctioned image under emulation instead — which is
# the only way to check the published image from that host at all, and it is
# slower rather than impossible.
#
# ============================================================================
# WHAT THIS FILE IS, AND WHAT .ci/image-checks.sh IS
# ============================================================================
#
# This file is the HOST driver. It knows where a pin LIVES, it classifies every
# one of them, and it resolves the ones it says it asserts. The
# checks themselves are .ci/image-checks.sh, which this file sends to the
# container on stdin together with the fixtures the functional checks read.
#
# The split is the point. `<tool> --version` inside a container proves that the
# binary RUNS; it says nothing about WHICH version runs, so `gh --version` is
# green on gh 2.40 while versions.env pins 2.90. Only a COMPARISON sees that, and
# the comparison needs the pin, which exists on the host and not in the image.
#
# 10 things fail this script before it reaches the docker daemon at all, because
# each one would otherwise report an image as smoked while checking nothing.
# Read the list, never the number beside it — this block said "3 things" once
# while listing 7:
#
#   - a pin of a home of this image that carries no classification;
#   - a pin classified `asserted` with no command to read a version with;
#   - a pin classified `asserted` that resolves to the empty string;
#   - a pin classified `asserted` whose value holds no version to compare;
#   - a home where NO pin is asserted, so the guest would compare nothing;
#   - a class outside the taxonomy, which classifies a pin into nothing while
#     looking like an answer;
#   - an absence probe on a class other than `not-in-this-image`, which is a
#     binary nothing would ever assert about;
#   - an image for which NO row names an absence probe, so `not-in-this-image`
#     would be an unchecked assertion again;
#   - no fixture under .ci/fixtures/, so the functional checks read nothing;
#   - an embedded file carrying the heredoc delimiter, which would truncate the
#     payload without an error.
#
# 6 more fail after the daemon is reached and still BEFORE the smoke container
# starts: the 3 platform-resolver refusals, the unobtainable-ref refusal, and
# the 2 size-gate refusals — an unreadable budget, and an image whose size the
# daemon will not report. This block said "3 things" and listed the first 3 of
# them — a count written in prose that the file then grew past.
#
# Usage: bash .ci/smoke.sh <image> [ref]
# where <image> ∈ {base, mobile, embedded, cloud, hardware, ui}
# and [ref] is the exact image reference to test. The default is the :latest tag
# that build-and-push.yml has just built, which is what CI runs. Naming a ref is
# how an operator audits the SHA tag a cluster is actually running — and how a
# developer proves a check against an image that is not the local :latest.
#
#   SMOKE_LIST_PINS=1 bash .ci/smoke.sh <image>
#
# prints `<PIN>|<class>` for every pin of every home of that image and exits 0,
# with no docker command at all: a classification is a property of the FILES, so
# it is readable in the pull request gate, where a container is not. The class it
# prints is the BARE class — the absence probe a `not-in-this-image` row may
# carry is a property of the table, and the seam's contract is the taxonomy.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Set before the source line, the way .ci/ctl.sh sets it: the git fallback in
# _ctl/lib.sh reads the wrong root when this repository is a submodule worktree.
REPO_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"

# The logging, the tool gate and the platform policy live in _ctl/lib.sh, 1 time
# only.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../_ctl/lib.sh
source "$PROJECT_ROOT/../_ctl/lib.sh"

IMAGE="${1:-}"
REF_ARG="${2:-}"

if [[ -z "$IMAGE" ]]; then
  log_error "usage: bash .ci/smoke.sh <image> [ref]"
  exit 2
fi

# ---------------------------------------------------------------------------
# The pin homes. versions.env for every image, plus its OWN Dockerfile when the
# image is a child.
#
# versions.env was 2 homes once: the cloud family read it and the base family
# read the ARGs at the top of base/Dockerfile, so this driver had to know which
# family an image belonged to before it could read a version at all.
# base/Dockerfile declares no value now — every pin of it arrives as a
# --build-arg generated from this same file — so the question does not arise and
# the branch below selects a CLASSIFICATION and nothing else.
#
# mobile and embedded read versions.env too, and always did read base's home:
# what they assert there is the toolchain they INHERIT from base. What they did
# NOT assert was their own `ARG NAME=value` block — 13 pins at the time this
# was measured, of which FLUTTER_VERSION, WEST_VERSION, ZEPHYR_SDK_VERSION,
# ESPTOOL_VERSION and CODE_SERVER_VERSION named a tool that reports its own
# version and no run compared one. (CODE_SERVER_VERSION is deleted since — the
# devbox deletion of 2026-08-19 took the binary with it. Read the ARG blocks,
# never this count.) That is ledger #102, and CHILD_PIN_HOME below is its home half:
# a child image reads its own Dockerfile as a SECOND home, with its own
# classification table, and every rule of the versions.env home applies to it
# unchanged — an unclassified pin refuses the run just the same.
#
# 1 thing is deliberately outside it. runner/Dockerfile was the other, and it is
# DELETED (D2, 2026-08-18) rather than excluded — a class table for an image no
# run could name would have been dead text, and so was the file:
#
#   - the pins a child INHERITS from ANOTHER CHILD. zephyr-devbox built FROM
#     zephyr and carried west and the Zephyr SDK while WEST_VERSION lived in
#     zephyr/Dockerfile, so the devbox run asserted esptool and code-server and
#     not those 2. That instance is gone by CONSTRUCTION and not by a fix: the
#     2 images are `embedded`, so both pairs are 1 home and 1 table. The general
#     hole is open — a child of a child would meet it again — and closing it
#     needs the FROM graph walked here, which is the remaining half of #102.
# ---------------------------------------------------------------------------
PIN_HOME="versions.env"

# image_child_pin_home <image> — the Dockerfile an image declares its own pins
# in, empty for the 2 root images. base and cloud declare every ARG value-less.
function image_child_pin_home() {
  case "$1" in
    mobile)  printf 'mobile/Dockerfile' ;;
    embedded) printf 'embedded/Dockerfile' ;;
    *)        printf '' ;;
  esac
}

# ---------------------------------------------------------------------------
# The classification, 1 row per pin:
#
#   <PIN>|<class>|<command that prints a version>|<extractor>
#
# The 3 classes are the whole taxonomy, and every pin of a home carries exactly
# 1 of them (_ctl/tests/version-coverage.test.sh holds that):
#
#   asserted           the smoke runs the command and compares what it reports
#   not-a-version      the pin is a digest, a channel or an untagged ref
#   not-in-this-image  the image does not install the tool
#
# THE CLASS FIELD CARRIES AN OPTIONAL ABSENCE PROBE, and only that 1 class may:
#
#   not-in-this-image:<binary>[,<binary>...]
#
# where each binary is asserted ABSENT in the guest — `! command -v <binary>`.
# Without it `not-in-this-image` is an assertion nobody checks: the row says the
# image does not install the tool, no command runs, and a tool that leaked in
# reads exactly like a tool that stayed out. It is not a theoretical leak.
# Measured on 2026-08-17, `ghcr.io/gophersys/base:latest` carries
# /usr/local/bin/terraform and /usr/local/bin/aws while base/Dockerfile installs
# neither and both rows below say `not-in-this-image` — the published image is
# older than the removal, and no check in this repository could say so.
#
# A row keeps the BARE class where a probe would prove nothing, and each such
# row says why beside it: a tool that is on no PATH in any image (the Actions
# runner lives at /home/runner/bin/Runner.Listener), or a package that ships no
# binary of its own. A probe that can never fire is a check that cannot fail.
#
# The extractor is empty for the ~30 tools whose first `<digits>.<digits>` token
# IS the version. The 2 other readers are named in .ci/image-checks.sh, and each
# use below says why it is there.
#
# A `*_SHA256_*` pin carries NO row in any table below. It is classified by
# SHAPE in class_row, because the 42 digest rows of versions.env would be copied
# once per table that reads that home, and the 6 digest ARGs of the child
# Dockerfiles once more — the day a digest is added without its row the smoke
# refuses to run at all. The shape is safe to trust HERE and only here:
# _ctl/tests/download-coverage.test.sh owns those names end to end, in
# versions.env AND in each child Dockerfile — it holds each one to the 1 arch
# vocabulary, to 64 lowercase hex, to the home its version lives in, and to an
# evidence comment. A digest is never a version, so no reading of a shell
# command could compare it against an image.
# ---------------------------------------------------------------------------

read -r -d '' PIN_CLASSES_CLOUD <<'PIN_CLASS_TABLE' || true
UBUNTU_BASE_REF|not-a-version||
ZSH_VERSION|asserted|zsh --version|prefix
NVM_VERSION|asserted|zsh -c "nvm --version"|
NODE_VERSION|asserted|node --version|
NPM_VERSION|asserted|npm --version|
PNPM_VERSION|asserted|COREPACK_HOME=/home/dev/.cache/node/corepack pnpm --version|
BUN_VERSION|asserted|bun --version|
PYTHON_PACKAGE|asserted|python3 --version|prefix
UV_VERSION|asserted|uv --version|
GO_VERSION|asserted|go version|
GOFUMPT_VERSION|asserted|gofumpt --version|
GOLANGCI_LINT_VERSION|asserted|golangci-lint --version|
GOVULNCHECK_VERSION|asserted|govulncheck -version|line:govulncheck
GOSEC_VERSION|asserted|go version -m ${GOPATH}/bin/gosec|line:mod
HNSLINT_VERSION|asserted|go version -m ${GOPATH}/bin/hnslint|line:mod
GREMLINS_VERSION|asserted|go version -m ${GOPATH}/bin/gremlins|line:mod
BENCHSTAT_REF|not-a-version||
RUST_CHANNEL|not-in-this-image:rustc,cargo||
DELVE_VERSION|asserted|dlv version|
SHELLCHECK_VERSION|asserted|shellcheck --version|
YQ_VERSION|asserted|yq --version|
HADOLINT_VERSION|asserted|hadolint --version|
KUBECONFORM_VERSION|asserted|kubeconform -v|
GITLEAKS_VERSION|asserted|gitleaks version|
KUBECTL_VERSION|asserted|kubectl version --client|
HELM_VERSION|asserted|helm version --short|
K9S_VERSION|asserted|k9s version --short|
K3D_VERSION|asserted|k3d version|
KIND_VERSION|asserted|kind version|
TAILSCALE_VERSION|asserted|tailscale version|
BW_VERSION|asserted|bw --version|
GH_VERSION|asserted|gh --version|
NATS_VERSION|asserted|nats --version|
DOCKER_COMPOSE_VERSION|asserted|docker compose version|
DOCKER_BUILDX_VERSION|asserted|docker buildx version|
BUF_VERSION|asserted|buf --version|
GRPCURL_VERSION|asserted|grpcurl -version|
RUNNER_VERSION|asserted|/home/runner/bin/Runner.Listener --version|line:Version:
CICTL_VERSION|asserted|go version -m /usr/local/bin/cictl|line:mod
CLAUDE_CODE_VERSION|asserted|claude --version|
OMP_VERSION|asserted|omp --version|
CODEX_VERSION|asserted|codex --version|
TERRAFORM_VERSION|not-in-this-image:terraform||
AWS_CLI_VERSION|not-in-this-image:aws||
OCI_CLI_VERSION|not-in-this-image:oci||
ANSIBLE_VERSION|not-in-this-image||
ANSIBLE_CORE_VERSION|not-in-this-image:ansible,ansible-playbook||
KICAD_PPA_VERSION|not-in-this-image:kicad-cli||
KIUTILS_VERSION|not-in-this-image||
SEXPDATA_VERSION|not-in-this-image||
PYTEST_VERSION|not-in-this-image:pytest||
RUFF_VERSION|not-in-this-image:ruff||
CHROME_MAJOR_VERSION|not-in-this-image:google-chrome-stable,densui-chromium||
PIN_CLASS_TABLE

# The 5 hardware rows keep cloud honest in the direction that matters: hardware
# builds FROM cloud, so a KiCad layer that drifted UP into the parent would make
# every ARC pool pull a 4.7 GB ECAD toolchain it never asked for, and the parent
# would still smoke green. kicad-cli is the probe that says so.
#
# KIUTILS_VERSION and SEXPDATA_VERSION keep the BARE class. Both are import-only
# python libraries and neither ships a console script, so there is no binary for
# `command -v` to look for — a probe that can never fire is a check that cannot
# fail. They are the 3rd and 4th bare rows of this table, beside RUNNER_VERSION
# (the Actions runner is on no image's PATH) and ANSIBLE_VERSION (the
# metapackage ships collections and no binary).
#
# CHROME_MAJOR_VERSION probes 2 binaries and not 1. google-chrome-stable is the
# package's own name and densui-chromium is the symlink the ui layer adds, so a
# browser that drifted UP into the parent would be caught whichever half arrived:
# every ARC pool runs cloud, and a 0.46 GB browser nobody asked for would ship to
# all of them.

read -r -d '' PIN_CLASSES_BASE <<'PIN_CLASS_TABLE' || true
UBUNTU_BASE_REF|not-a-version||
ZSH_VERSION|asserted|zsh --version|prefix
NVM_VERSION|asserted|zsh -c "nvm --version"|
NODE_VERSION|asserted|node --version|
NPM_VERSION|asserted|npm --version|
PNPM_VERSION|asserted|COREPACK_HOME=/home/dev/.cache/node/corepack pnpm --version|
BUN_VERSION|asserted|bun --version|
PYTHON_PACKAGE|asserted|python3 --version|prefix
UV_VERSION|asserted|uv --version|
GO_VERSION|asserted|go version|
RUST_CHANNEL|not-a-version||
GOFUMPT_VERSION|asserted|gofumpt --version|
GOLANGCI_LINT_VERSION|asserted|golangci-lint --version|
GOVULNCHECK_VERSION|asserted|govulncheck -version|line:govulncheck
GOSEC_VERSION|asserted|go version -m ${GOPATH}/bin/gosec|line:mod
HNSLINT_VERSION|asserted|go version -m ${GOPATH}/bin/hnslint|line:mod
GREMLINS_VERSION|asserted|go version -m ${GOPATH}/bin/gremlins|line:mod
BENCHSTAT_REF|not-a-version||
SHELLCHECK_VERSION|asserted|shellcheck --version|
YQ_VERSION|asserted|yq --version|
HADOLINT_VERSION|asserted|hadolint --version|
KUBECONFORM_VERSION|asserted|kubeconform -v|
GITLEAKS_VERSION|asserted|gitleaks version|
KUBECTL_VERSION|asserted|kubectl version --client|
HELM_VERSION|asserted|helm version --short|
K9S_VERSION|asserted|k9s version --short|
K3D_VERSION|asserted|k3d version|
KIND_VERSION|asserted|kind version|
TAILSCALE_VERSION|asserted|tailscale version|
BW_VERSION|asserted|bw --version|
GH_VERSION|asserted|gh --version|
NATS_VERSION|asserted|nats --version|
DOCKER_COMPOSE_VERSION|asserted|docker compose version|
DOCKER_BUILDX_VERSION|asserted|docker buildx version|
OCI_CLI_VERSION|asserted|oci --version|
ANSIBLE_CORE_VERSION|asserted|ansible --version|
ANSIBLE_VERSION|asserted|/home/dev/.local/share/uv/tools/ansible-core/bin/python -c "import importlib.metadata as m; print(m.version('ansible'))"|
DELVE_VERSION|not-in-this-image:dlv||
BUF_VERSION|not-in-this-image:buf||
GRPCURL_VERSION|not-in-this-image:grpcurl||
RUNNER_VERSION|not-in-this-image||
CICTL_VERSION|not-in-this-image:cictl||
CLAUDE_CODE_VERSION|asserted|claude --version|
OMP_VERSION|asserted|omp --version|
CODEX_VERSION|asserted|codex --version|
TERRAFORM_VERSION|not-in-this-image:terraform||
AWS_CLI_VERSION|not-in-this-image:aws||
KICAD_PPA_VERSION|not-in-this-image:kicad-cli||
KIUTILS_VERSION|not-in-this-image||
SEXPDATA_VERSION|not-in-this-image||
PYTEST_VERSION|not-in-this-image:pytest||
RUFF_VERSION|not-in-this-image:ruff||
CHROME_MAJOR_VERSION|not-in-this-image:google-chrome-stable,densui-chromium||
PIN_CLASS_TABLE

# The same 5 rows the cloud table carries, and for the same reason read from the
# other side of the graph: the KiCad toolchain is a leaf and nothing above it
# installs it. The 2 bare classes are the import-only libraries — see the note
# under the cloud table. CHROME_MAJOR_VERSION is a 6th row of that kind: base is
# the OTHER root, so nothing in its graph installs a browser either.

# The hardware table. A CHILD that reads versions.env, so this is a 3rd table
# over the SAME home rather than a table over a Dockerfile: hardware/Dockerfile
# declares every pin value-less and takes it as a generated --build-arg, exactly
# as cloud does, so there is no second home for it to have a table about.
#
# It is the cloud table with the 5 KiCad rows flipped to `asserted`. Everything
# else is inherited through the FROM, which is what makes copying the rows the
# TRUE answer rather than a shortcut — a row that said not-in-this-image here
# would be asserting the absence of a tool the parent installs.
read -r -d '' PIN_CLASSES_HARDWARE <<'PIN_CLASS_TABLE' || true
UBUNTU_BASE_REF|not-a-version||
ZSH_VERSION|asserted|zsh --version|prefix
NVM_VERSION|asserted|zsh -c "nvm --version"|
NODE_VERSION|asserted|node --version|
NPM_VERSION|asserted|npm --version|
PNPM_VERSION|asserted|COREPACK_HOME=/home/dev/.cache/node/corepack pnpm --version|
BUN_VERSION|asserted|bun --version|
PYTHON_PACKAGE|asserted|python3 --version|prefix
UV_VERSION|asserted|uv --version|
GO_VERSION|asserted|go version|
GOFUMPT_VERSION|asserted|gofumpt --version|
GOLANGCI_LINT_VERSION|asserted|golangci-lint --version|
GOVULNCHECK_VERSION|asserted|govulncheck -version|line:govulncheck
GOSEC_VERSION|asserted|go version -m ${GOPATH}/bin/gosec|line:mod
HNSLINT_VERSION|asserted|go version -m ${GOPATH}/bin/hnslint|line:mod
GREMLINS_VERSION|asserted|go version -m ${GOPATH}/bin/gremlins|line:mod
BENCHSTAT_REF|not-a-version||
RUST_CHANNEL|not-in-this-image:rustc,cargo||
DELVE_VERSION|asserted|dlv version|
SHELLCHECK_VERSION|asserted|shellcheck --version|
YQ_VERSION|asserted|yq --version|
HADOLINT_VERSION|asserted|hadolint --version|
KUBECONFORM_VERSION|asserted|kubeconform -v|
GITLEAKS_VERSION|asserted|gitleaks version|
KUBECTL_VERSION|asserted|kubectl version --client|
HELM_VERSION|asserted|helm version --short|
K9S_VERSION|asserted|k9s version --short|
K3D_VERSION|asserted|k3d version|
KIND_VERSION|asserted|kind version|
TAILSCALE_VERSION|asserted|tailscale version|
BW_VERSION|asserted|bw --version|
GH_VERSION|asserted|gh --version|
NATS_VERSION|asserted|nats --version|
DOCKER_COMPOSE_VERSION|asserted|docker compose version|
DOCKER_BUILDX_VERSION|asserted|docker buildx version|
BUF_VERSION|asserted|buf --version|
GRPCURL_VERSION|asserted|grpcurl -version|
RUNNER_VERSION|asserted|/home/runner/bin/Runner.Listener --version|line:Version:
CICTL_VERSION|asserted|go version -m /usr/local/bin/cictl|line:mod
CLAUDE_CODE_VERSION|asserted|claude --version|
OMP_VERSION|asserted|omp --version|
CODEX_VERSION|asserted|codex --version|
TERRAFORM_VERSION|not-in-this-image:terraform||
AWS_CLI_VERSION|not-in-this-image:aws||
OCI_CLI_VERSION|not-in-this-image:oci||
ANSIBLE_VERSION|not-in-this-image||
ANSIBLE_CORE_VERSION|not-in-this-image:ansible,ansible-playbook||
KICAD_PPA_VERSION|asserted|kicad-cli version|prefix
KIUTILS_VERSION|asserted|python3 -c "import importlib.metadata as m; print(m.version('kiutils'))"|
SEXPDATA_VERSION|asserted|python3 -c "import importlib.metadata as m; print(m.version('sexpdata'))"|
PYTEST_VERSION|asserted|pytest --version|
RUFF_VERSION|asserted|ruff --version|
CHROME_MAJOR_VERSION|not-in-this-image:google-chrome-stable,densui-chromium||
PIN_CLASS_TABLE

# KICAD_PPA_VERSION takes `prefix` because the pin is a MAJOR inside a PPA name,
# the way JAVA_VERSION is a major inside an apt package name: the archive serves
# 10.0.5~ubuntu24.04.1 on noble and `kicad-cli version` reports 10.0.5, so an
# exact comparison would demand a pin that moves with every PPA point release
# and the row would stop meaning "KiCad 10".
#
# kiutils and sexpdata are asserted through importlib.metadata and not through a
# command, because neither ships one — the shape PIN_CLASSES_BASE already uses
# for ANSIBLE_VERSION. Asking the INTERPRETER is also the stronger question
# here: the pip install is only useful if `python3 -m pytest` can import it, and
# this asks exactly that.

# The ui table. The 2nd CHILD that reads versions.env, so it is a 4th table over
# the SAME home and not a table over a Dockerfile — ui/Dockerfile declares its 1
# ARG value-less and takes the value as a generated --build-arg, exactly as cloud
# and hardware do.
#
# It is the cloud table with 1 row flipped: CHROME_MAJOR_VERSION. Everything else
# is inherited through the FROM, and the 5 KiCad rows stay not-in-this-image
# because ui is cloud's other leaf and installs none of them.
read -r -d '' PIN_CLASSES_UI <<'PIN_CLASS_TABLE' || true
UBUNTU_BASE_REF|not-a-version||
ZSH_VERSION|asserted|zsh --version|prefix
NVM_VERSION|asserted|zsh -c "nvm --version"|
NODE_VERSION|asserted|node --version|
NPM_VERSION|asserted|npm --version|
PNPM_VERSION|asserted|COREPACK_HOME=/home/dev/.cache/node/corepack pnpm --version|
BUN_VERSION|asserted|bun --version|
PYTHON_PACKAGE|asserted|python3 --version|prefix
UV_VERSION|asserted|uv --version|
GO_VERSION|asserted|go version|
GOFUMPT_VERSION|asserted|gofumpt --version|
GOLANGCI_LINT_VERSION|asserted|golangci-lint --version|
GOVULNCHECK_VERSION|asserted|govulncheck -version|line:govulncheck
GOSEC_VERSION|asserted|go version -m ${GOPATH}/bin/gosec|line:mod
HNSLINT_VERSION|asserted|go version -m ${GOPATH}/bin/hnslint|line:mod
GREMLINS_VERSION|asserted|go version -m ${GOPATH}/bin/gremlins|line:mod
BENCHSTAT_REF|not-a-version||
RUST_CHANNEL|not-in-this-image:rustc,cargo||
DELVE_VERSION|asserted|dlv version|
SHELLCHECK_VERSION|asserted|shellcheck --version|
YQ_VERSION|asserted|yq --version|
HADOLINT_VERSION|asserted|hadolint --version|
KUBECONFORM_VERSION|asserted|kubeconform -v|
GITLEAKS_VERSION|asserted|gitleaks version|
KUBECTL_VERSION|asserted|kubectl version --client|
HELM_VERSION|asserted|helm version --short|
K9S_VERSION|asserted|k9s version --short|
K3D_VERSION|asserted|k3d version|
KIND_VERSION|asserted|kind version|
TAILSCALE_VERSION|asserted|tailscale version|
BW_VERSION|asserted|bw --version|
GH_VERSION|asserted|gh --version|
NATS_VERSION|asserted|nats --version|
DOCKER_COMPOSE_VERSION|asserted|docker compose version|
DOCKER_BUILDX_VERSION|asserted|docker buildx version|
BUF_VERSION|asserted|buf --version|
GRPCURL_VERSION|asserted|grpcurl -version|
RUNNER_VERSION|asserted|/home/runner/bin/Runner.Listener --version|line:Version:
CICTL_VERSION|asserted|go version -m /usr/local/bin/cictl|line:mod
CLAUDE_CODE_VERSION|asserted|claude --version|
OMP_VERSION|asserted|omp --version|
CODEX_VERSION|asserted|codex --version|
TERRAFORM_VERSION|not-in-this-image:terraform||
AWS_CLI_VERSION|not-in-this-image:aws||
OCI_CLI_VERSION|not-in-this-image:oci||
ANSIBLE_VERSION|not-in-this-image||
ANSIBLE_CORE_VERSION|not-in-this-image:ansible,ansible-playbook||
KICAD_PPA_VERSION|not-in-this-image:kicad-cli||
KIUTILS_VERSION|not-in-this-image||
SEXPDATA_VERSION|not-in-this-image||
PYTEST_VERSION|not-in-this-image:pytest||
RUFF_VERSION|not-in-this-image:ruff||
CHROME_MAJOR_VERSION|asserted|sh -c "${DENSUI_CHROME} --version"|prefix
PIN_CLASS_TABLE

# CHROME_MAJOR_VERSION takes `prefix` because the pin is a MAJOR line, the way
# KICAD_PPA_VERSION and JAVA_VERSION are: `google-chrome-stable --version`
# reports 152.0.7977.64 and the row holds 152, so an exact comparison would
# demand a pin that moves with every point release Google ships.
#
# It reads the browser through ${DENSUI_CHROME} ON PURPOSE, and that is why the
# command is wrapped in `sh -c` rather than written bare: probe_tool takes the
# FIRST word of a row as the binary to look for, and an unexpanded
# `${DENSUI_CHROME}` is on no PATH — the shape `zsh -c "nvm --version"` already
# uses here. Reading the ENV is the stronger question: the consumer's probe.py
# reads exactly that variable, and an empty value there makes it fall through to
# its own candidate search, which passes while proving nothing about the image.
# So this 1 row compares the version AND proves the entry point the gates use.
#
# WHAT IT DOES NOT COVER: the arm64 variant. This driver runs ONE container, on
# the platform `resolve_smoke_platform` chose — `SMOKE_PLATFORM`, linux/amd64, in
# every CI run — so every `asserted` row of every table here is a statement about
# that variant alone. For the other images that is a small claim: both legs
# install the same pinned tarball at the same digest. For `ui` it is not, because
# `google-chrome-stable` is an UNPINNED apt install that the publish step
# re-resolves for arm64 at build time. Reading the arm64 browser needs the
# recorded follow-up in the sanctioned-platform section of
# .claude/rules/00-identity.md — smoking arm64 out of the registry after the
# push — and no row of this file can stand in for it.

# ---------------------------------------------------------------------------
# The child tables, 1 per child image, over that image's OWN Dockerfile.
#
# Same 4 fields and same taxonomy as the 2 above. They are separate tables and
# not extra rows in PIN_CLASSES_BASE because they read a DIFFERENT home: a row
# here names an `ARG NAME=value` of one Dockerfile, and the same reader that
# refuses an unclassified versions.env pin refuses an unclassified one here.
#
# BASE_TAG is in each of them. It is a build parameter and not a pin — it
# selects which tag of the parent image the FROM resolves — and it is a
# value-ful ARG, so the reader finds it and it needs an answer. `not-a-version`
# is that answer, and leaving it out would refuse every child run.
#
# There is no `not-in-this-image` row in any of the 3, so no absence probe
# either: a child image installs every pin its own Dockerfile declares. The
# absence probes for these runs come from PIN_CLASSES_BASE, which is the other
# home each child reads.
# ---------------------------------------------------------------------------

read -r -d '' PIN_CLASSES_MOBILE <<'PIN_CLASS_TABLE' || true
BASE_TAG|not-a-version||
JAVA_VERSION|asserted|java -version|prefix
ANDROID_CMDLINE_TOOLS_VERSION|not-a-version||
ANDROID_PLATFORM_VERSION|not-a-version||
ANDROID_BUILDTOOLS_VERSION|not-a-version||
FLUTTER_VERSION|asserted|flutter --version|
FLUTTER_CHANNEL|not-a-version||
PIN_CLASS_TABLE

# JAVA_VERSION takes `prefix` because the pin is a MAJOR — openjdk-21 reports
# `openjdk version "21.0.11"`, and an exact comparison would demand a pin that
# moves with every ubuntu security update.
#
# The 3 ANDROID_* rows are `not-a-version` for the reason the header gives, and
# the reason was measured rather than assumed: `sdkmanager --version` in
# ghcr.io/gophersys/flutter:latest prints `20.0`, which is the cmdline-tools
# release and not ANDROID_CMDLINE_TOOLS_VERSION=14742923 — that pin is the
# google download build id. ANDROID_PLATFORM_VERSION is an API level and
# ANDROID_BUILDTOOLS_VERSION is a directory name under the SDK root; no tool in
# the SDK reports either as its own version, so any command written here would
# compare a number against a different number and go red forever.
#
# FLUTTER_CHANNEL is `stable`, which is a channel and never a version — the same
# answer RUST_CHANNEL takes in base.

# PIN_CLASSES_ZEPHYR and PIN_CLASSES_DEVBOX were 2 tables over 2 files, and
# THE SPLIT COST A CHECK. `zephyr-devbox` built FROM `zephyr` and carried west
# and the Zephyr SDK, but WEST_VERSION and ZEPHYR_SDK_VERSION were declared in
# the PARENT's Dockerfile, and CHILD_PIN_HOME reads 1 file: the image's own. So
# the devbox run asserted esptool and code-server against the image and left the
# 2 pins it inherited compared by nothing — the inherited-pin half of ledger
# #102. The 2 images are 1 image now, so the 2 tables are 1 table over 1 home.
# That closes #102 FOR THIS FAMILY
# and for no other: `mobile` still inherits base's pins the same way, and the
# general fix is a FROM-graph walker in this driver, which is still open.
#
# THE TABLE IS 6 ROWS AND IT WAS 7. `CODE_SERVER_VERSION|asserted` left with
# the devbox deletion (Mateo, 2026-08-19), because the binary it compared
# against is not in the image any more — an `asserted` row over an absent tool
# is a row that goes red forever, and a `not-in-this-image` row for a pin no
# home declares is a row `version-coverage.test.sh` refuses in the other
# direction. A pin with no declaration takes no row at all.
read -r -d '' PIN_CLASSES_EMBEDDED <<'PIN_CLASS_TABLE' || true
BASE_TAG|not-a-version||
WEST_VERSION|asserted|west --version|
ZEPHYR_SDK_VERSION|asserted|cat ${ZEPHYR_SDK_INSTALL_DIR}/sdk_version|
ZSDK_TOOLCHAINS|not-a-version||
ESPTOOL_VERSION|asserted|esptool version|
ZSDK_EXTRA_TOOLCHAINS|not-a-version||
PIN_CLASS_TABLE

# ZEPHYR_SDK_VERSION has no CLI to ask: the SDK ships toolchains, and each
# toolchain's gcc reports the GCC version. What it does ship is `sdk_version` at
# the root of ZEPHYR_SDK_INSTALL_DIR — the file the SDK's own
# Zephyr-sdkConfigVersion.cmake reads — so the command is a `cat` of it. Read on
# 2026-08-17 in ghcr.io/gophersys/zephyr-devbox:latest: `1.0.1`.
#
# ZSDK_TOOLCHAINS and ZSDK_EXTRA_TOOLCHAINS are comma-separated LISTS of
# toolchain names and pin no version at all. What they select is asserted by the
# content-zephyr group, which finds the gcc of each toolchain under the SDK root.
#
# CODE_SERVER_VERSION IS WHY THIS TABLE EXISTS, and the row is gone while the
# table stays. It was pinned in a cycle where no class, no test and no run
# compared it against the image: read on 2026-08-17,
# ghcr.io/gophersys/zephyr-devbox:latest reported 4.127.0 while
# zephyr-devbox/Dockerfile pinned 4.133.0 — the published image was older than
# its own pin, and nothing here could say so. Its scoping clause is worth
# keeping as the lesson even though the row is deleted: it read `line:with
# Code`, because unscoped the reader took the FIRST number in the whole output
# and in the built image that was '12.329' — the seconds of a timestamped
# warning line printed above the version, so the observed 'version' equalled the
# wall clock of the check itself (02:04:12.329, failed at .338), measured in run
# 32088060119. A comparator needs to be told WHICH line answers.

# The functional groups .ci/image-checks.sh runs for each image, beyond the
# version comparison, are the `groups` field of images.yaml — image_check_groups
# in _ctl/lib.sh reads it. This file carried a case table of its own, which was
# 1 of the ~15 homes an image name had to be written into.
#
# `base-runner` had a row here and is RETIRED — the ARC pools run `cloud` now,
# so nothing builds it. The `content-runner` group did NOT go with it: `cloud`
# carries the runner layer, so the checks that read /home/runner, its ownership
# and the docker group still run, on the image that ships them today.

# The homes of THIS image, and the classification table each one is read
# against. 2 parallel arrays and not 1 map: the mac's bash is 3.2 and has no
# associative array, and every reader below walks the pair by index.
PIN_HOMES=()
PIN_TABLES=()
CHILD_CLASSES=""

case "$IMAGE" in
  cloud)
    PIN_CLASSES="$PIN_CLASSES_CLOUD"
    ;;
  hardware)
    # No CHILD_CLASSES: this child's pins are in versions.env, not in its own
    # Dockerfile, so it has 1 home like the 2 root images and not 2 like the
    # other 3 children.
    PIN_CLASSES="$PIN_CLASSES_HARDWARE"
    ;;
  ui)
    # No CHILD_CLASSES, for the reason the hardware arm gives.
    PIN_CLASSES="$PIN_CLASSES_UI"
    ;;
  base)
    PIN_CLASSES="$PIN_CLASSES_BASE"
    ;;
  mobile)
    PIN_CLASSES="$PIN_CLASSES_BASE"
    CHILD_CLASSES="$PIN_CLASSES_MOBILE"
    ;;
  embedded)
    PIN_CLASSES="$PIN_CLASSES_BASE"
    CHILD_CLASSES="$PIN_CLASSES_EMBEDDED"
    ;;
  *)
    log_error "unknown image: '$IMAGE'"
    log_error "valid images: base, mobile, embedded, cloud, hardware, ui"
    exit 2
    ;;
esac

PIN_HOMES+=("$PIN_HOME")
PIN_TABLES+=("$PIN_CLASSES")

CHILD_PIN_HOME="$(image_child_pin_home "$IMAGE")"
# The 2 halves have to arrive together. A home with no table classifies nothing
# and every pin of it would refuse the run; a table with no home is rows about a
# file this run never opens.
if [[ -n "$CHILD_PIN_HOME" || -n "$CHILD_CLASSES" ]]; then
  if [[ -z "$CHILD_PIN_HOME" || -z "$CHILD_CLASSES" ]]; then
    log_error "${IMAGE} declares a child pin home of '${CHILD_PIN_HOME:-<none>}' and a child class table that is ${CHILD_CLASSES:+non-}empty"
    log_error "the home and its table are set in the same case arm of .ci/smoke.sh; set both or neither"
    exit 1
  fi
  PIN_HOMES+=("$CHILD_PIN_HOME")
  PIN_TABLES+=("$CHILD_CLASSES")
fi

CHECK_GROUPS="$(image_check_groups "$IMAGE")" || exit 2
if [[ -z "$CHECK_GROUPS" ]]; then
  log_error "no functional check group is declared for '${IMAGE}' in images.yaml"
  log_error "a smoke that compares versions and exercises nothing is not a smoke"
  exit 2
fi

# ---------------------------------------------------------------------------
# The readers.
# ---------------------------------------------------------------------------

# home_pin_names <home> — every pin the home declares, 1 per line, in file order.
#
# versions.env declares `NAME=value`, and every row of it is a pin — including
# PYTHON_PACKAGE, which is an apt package name and not a semver.
#
# A child Dockerfile declares `ARG NAME=value`. Only the VALUE-FUL ones are pins:
# `ARG TARGETPLATFORM` is injected by buildx and declares nothing to compare, and
# base/Dockerfile is value-less from end to end because its values arrive as
# generated --build-args. The reader takes the whole file and not a "top block":
# the ARGs-at-top convention is a rule of this repository and not a property this
# reader can measure, so an ARG somebody adds further down is CLASSIFIED rather
# than silently skipped.
function home_pin_names() {
  local home="$1"
  case "$home" in
    "$PIN_HOME")
      awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/ { print $1 }' "$REPO_ROOT/$home" | awk '!seen[$0]++'
      ;;
    */Dockerfile)
      awk '
        match($0, /^[[:space:]]*ARG[[:space:]]+[A-Za-z_][A-Za-z0-9_]*=/) {
          name = substr($0, RSTART, RLENGTH)
          sub(/^[[:space:]]*ARG[[:space:]]+/, "", name)
          sub(/=$/, "", name)
          print name
        }
      ' "$REPO_ROOT/$home" | awk '!seen[$0]++'
      ;;
    *)
      log_error "no reader for pin home '${home}'"
      exit 1
      ;;
  esac
}

# resolve_pin <NAME> <home> — the value that home declares for that pin.
#
# 2 globals come out, never a printed value: PIN_VALUE, and PIN_PROBLEM when
# there is nothing to use. Every unreadable case ends with an EMPTY PIN_VALUE,
# and an empty value for an asserted pin stops this script before it starts a
# container — an image compared against an empty string is an image nobody
# checked, which is the result this repository has already published once.
#
# This 1 function replaced 2 that could each read only the buildx pin. They
# answered "declares no ARG" whenever their single regex missed, which is a lie
# when the file plainly declares one, so the shapes a human writes are read here:
# leading whitespace, a trailing `# comment`, and a `v` on the value.
PIN_VALUE=""
PIN_PROBLEM=""
function resolve_pin() {
  local name="$1" home="$2"
  local file="$REPO_ROOT/$home"
  local line="" status=0
  PIN_VALUE=""
  PIN_PROBLEM=""

  if [[ ! -f "$file" ]]; then
    PIN_PROBLEM="the pin home ${home} is not a file: ${file}"
    return 0
  fi

  case "$home" in
    "$PIN_HOME")
      line="$(grep -E "^${name}=" "$file")" || status=$?
      if [[ "$status" -ne 0 || -z "$line" ]]; then
        PIN_PROBLEM="${home} declares no ${name}"
        return 0
      fi
      line="${line%%#*}"
      line="${line%"${line##*[![:space:]]}"}"
      local assignment="${name}="
      PIN_VALUE="${line#*"$assignment"}"
      ;;
    */Dockerfile)
      # declaration_line and declaration_value are in _ctl/lib.sh, which this
      # file already sources. They are the readers `bump_pin` WRITES through, so
      # the value this run compares against the image is the value the weekly
      # bump would edit — a second parser here is how the 2 come to disagree.
      line="$(declaration_line "$file" "$name")"
      if [[ -z "$line" ]]; then
        PIN_PROBLEM="${home} declares no ${name} with a value"
        return 0
      fi
      PIN_VALUE="$(declaration_value "$line")"
      ;;
    *)
      PIN_PROBLEM="no reader for pin home '${home}'"
      return 0
      ;;
  esac

  if [[ -z "$PIN_VALUE" ]]; then
    PIN_PROBLEM="${home} declares ${name} with an empty value"
  fi
}

# expected_version <raw pin value> — the version INSIDE the pin. Everything
# before the first digit goes: CICTL_VERSION is written `v0.6.0`, and
# PYTHON_PACKAGE is written `python3.12` because apt names a package rather than
# a version. Empty when the value holds no digit at all, which the caller reports.
function expected_version() {
  local raw="$1"
  printf '%s' "${raw#"${raw%%[0-9]*}"}"
}

# class_row <PIN> <table> — the classification row for a pin in that table, empty
# when it has none. The table is passed in and not read from a global, because a
# child image reads 2 homes and each one is judged against its own table.
#
# A digest is classified by its NAME and carries no table row. See the note
# above the tables: the rule that keeps this honest is that
# download-coverage.test.sh governs every `*_SHA256_*` name in every home.
function class_row() {
  local name="$1" table="$2" row
  if [[ "$name" == *_SHA256_* ]]; then
    printf '%s|not-a-version||' "$name"
    return 0
  fi
  while IFS= read -r row; do
    [[ "${row%%|*}" == "$name" ]] || continue
    printf '%s' "$row"
    return 0
  done <<< "$table"
  printf ''
}

# bare_class <class field> — the class without its absence probe. The taxonomy is
# 3 words, and `not-in-this-image:terraform` is 1 of them carrying a probe.
function bare_class() {
  printf '%s' "${1%%:*}"
}

# class_probes <class field> — the absence probes a class field names, 1 binary
# per line, empty when it names none.
function class_probes() {
  local field="$1"
  [[ "$field" == *:* ]] || return 0
  # The trailing newline is load-bearing twice over: without it, `read` drops
  # the LAST binary of every field (it returns nonzero on an unterminated
  # line and the loop body never runs), and a trailing comma's empty final
  # field vanishes with it — so the empty-probe refusal below could not fire.
  printf '%s\n' "${field#*:}" | tr ',' '\n'
}

# ---------------------------------------------------------------------------
# The listing. A classification is a property of the files, so this runs with no
# daemon at all and it is the seam the pull request gate reads.
# ---------------------------------------------------------------------------
if [[ "${SMOKE_LIST_PINS:-}" == "1" ]]; then
  for home_index in "${!PIN_HOMES[@]}"; do
    home="${PIN_HOMES[$home_index]}"
    table="${PIN_TABLES[$home_index]}"
    while IFS= read -r pin; do
      [[ -z "$pin" ]] && continue
      row="$(class_row "$pin" "$table")"
      [[ -z "$row" ]] && continue
      row="${row#*|}"
      printf '%s|%s\n' "$pin" "$(bare_class "${row%%|*}")"
    done <<< "$(home_pin_names "$home")"
  done
  exit 0
fi

# Contract tests exercise the payload tables for retained, disabled image
# definitions without starting Docker. Production callers never set this seam;
# every normal smoke invocation must target the active base/cloud surface.
if [[ "${SMOKE_STATIC_CONTRACT:-}" != "1" ]]; then
  require_active_image "$IMAGE" || exit 2
fi

# ---------------------------------------------------------------------------
# The assertion table, built BEFORE anything touches docker.
#
# ABSENT_TABLE is built in the same pass. It is the other half of a
# classification: PIN_TABLE says what the guest must FIND at the pinned version,
# and ABSENT_TABLE says what it must not find at all.
# ---------------------------------------------------------------------------
PIN_TABLE=""
ABSENT_TABLE=""
UNCLASSIFIED=""
for home_index in "${!PIN_HOMES[@]}"; do
  home="${PIN_HOMES[$home_index]}"
  table="${PIN_TABLES[$home_index]}"
  while IFS= read -r pin; do
    [[ -z "$pin" ]] && continue
    if [[ -z "$(class_row "$pin" "$table")" ]]; then
      UNCLASSIFIED="${UNCLASSIFIED:+${UNCLASSIFIED} }${home}:${pin}"
    fi
  done <<< "$(home_pin_names "$home")"
done
if [[ -n "$UNCLASSIFIED" ]]; then
  log_error "these pins carry no classification: ${UNCLASSIFIED}"
  log_error "assert each one in .ci/smoke.sh, or classify it not-a-version or not-in-this-image"
  log_error "a pin nothing compares against the image is a number in a file"
  exit 1
fi

for home_index in "${!PIN_HOMES[@]}"; do
  home="${PIN_HOMES[$home_index]}"
  table="${PIN_TABLES[$home_index]}"
  while IFS='|' read -r pin class probe extractor; do
    [[ -z "$pin" ]] && continue
    class_name="$(bare_class "$class")"
    case "$class_name" in
      asserted|not-a-version|not-in-this-image) ;;
      *)
        log_error "${pin} carries the class '${class_name}' in the ${home} table of .ci/smoke.sh"
        log_error "the 3 classes are: asserted, not-a-version, not-in-this-image"
        log_error "a class outside the taxonomy classifies a pin into nothing while it looks like an answer"
        exit 1
        ;;
    esac

    if [[ "$class" == *:* ]]; then
      if [[ "$class_name" != "not-in-this-image" ]]; then
        log_error "${pin} carries an absence probe on class '${class_name}', and only not-in-this-image may"
        log_error "an image that INSTALLS a tool cannot also be asserted not to have it"
        exit 1
      fi
      while IFS= read -r binary; do
        if [[ -z "$binary" ]]; then
          log_error "${pin} is classified '${class}' and names an empty absence probe"
          log_error "write not-in-this-image:<binary>[,<binary>...], or drop the colon"
          exit 1
        fi
        ABSENT_TABLE="${ABSENT_TABLE:+${ABSENT_TABLE}
}${pin}|${binary}"
      done < <(class_probes "$class")
      # < <(...) and not <<< "$(...)": command substitution STRIPS the trailing
      # newline, so 'not-in-this-image:aws,' lost its empty last field and the
      # refusal above could never fire on a trailing comma — measured 2026-08-18.
    fi

    [[ "$class_name" == "asserted" ]] || continue
    if [[ -z "$probe" ]]; then
      log_error "${pin} is classified asserted and names no command to read a version with"
      log_error "give it a command in the ${home} table of .ci/smoke.sh, or classify it not-a-version"
      exit 1
    fi
    resolve_pin "$pin" "$home"
    if [[ -z "$PIN_VALUE" ]]; then
      log_error "${pin} is classified asserted and resolves to the empty string: ${PIN_PROBLEM}"
      log_error "an empty expected version compares against nothing, so NOTHING was asserted about ${IMAGE}"
      exit 1
    fi
    expected="$(expected_version "$PIN_VALUE")"
    if [[ -z "$expected" ]]; then
      log_error "${pin} is classified asserted and its value '${PIN_VALUE}' holds no version to compare"
      exit 1
    fi
    PIN_TABLE="${PIN_TABLE:+${PIN_TABLE}
}${pin}|${expected}|${probe}|${extractor:-}"
  done <<< "$table"
done

# `${array[*]}` joins on the FIRST character of IFS, and this script runs with
# IFS=$'\n\t', so the plain form puts each home on a line of its own and splits
# the message it is part of. Both readings below join on a space deliberately.
PIN_HOMES_TEXT="$(IFS=' '; printf '%s' "${PIN_HOMES[*]}")"

if [[ -z "$PIN_TABLE" ]]; then
  log_error "no pin of ${PIN_HOMES_TEXT} is classified asserted, so the guest would compare nothing"
  exit 1
fi

# A `not-in-this-image` row that names no binary is the unchecked assertion this
# class used to be end to end. terraform and the AWS CLI are ready components
# that NO image installs, so every table carries at least those 2 — an image
# whose whole table probes nothing means somebody emptied the probe field, not
# that the image grew every tool.
if [[ -z "$ABSENT_TABLE" ]]; then
  log_error "no pin of ${IMAGE} is classified not-in-this-image with an absence probe"
  log_error "the class would be an assertion nobody checks, which is what it was before ledger #103"
  exit 1
fi

# ---------------------------------------------------------------------------
# The payload: the fixtures, the table, and .ci/image-checks.sh, in 1 stream.
#
# It travels on stdin and not in the argv because the guest also receives FILES,
# and an argv is not a place to put a file. The guest script is written out and
# exec'd rather than piped into bash, so a check that reads stdin cannot eat the
# rest of the script.
# ---------------------------------------------------------------------------
FIXTURES_DIR="$PROJECT_ROOT/fixtures"
PAYLOAD_EOF="GOPHERSYS_SMOKE_PAYLOAD_EOF"

FIXTURE_FILES=()
while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  FIXTURE_FILES+=("${file#"$FIXTURES_DIR/"}")
done < <(find "$FIXTURES_DIR" -type f | sort)

if [[ "${#FIXTURE_FILES[@]}" -eq 0 ]]; then
  log_error "no fixture found under ${FIXTURES_DIR} — the functional checks would have nothing to run on"
  exit 1
fi

# A file that carried the delimiter would end its own heredoc, and the rest of it
# would be read as shell. The check names the file, because that is the edit
# somebody has to make.
EMBEDDED_FILES=("$PROJECT_ROOT/image-checks.sh")
for relative in "${FIXTURE_FILES[@]}"; do
  EMBEDDED_FILES+=("$FIXTURES_DIR/$relative")
done
for file in "${EMBEDDED_FILES[@]}"; do
  if grep -qF -- "$PAYLOAD_EOF" "$file"; then
    log_error "the embedded file ${file} carries the heredoc delimiter ${PAYLOAD_EOF}"
    log_error "the payload would end there and the rest of the file would run as shell"
    exit 1
  fi
done

# payload_text — the stream the container reads on stdin.
#
# Every `$` below belongs to the GUEST shell and must reach it unexpanded, so
# the single quotes are the point rather than an oversight.
# shellcheck disable=SC2016
function payload_text() {
  local relative
  printf 'SMOKE_FIXTURE_DIR="$(mktemp -d)"\n'
  printf 'export SMOKE_FIXTURE_DIR\n'
  for relative in "${FIXTURE_FILES[@]}"; do
    printf 'mkdir -p "${SMOKE_FIXTURE_DIR}/%s"\n' "$(dirname "$relative")"
    printf 'cat > "${SMOKE_FIXTURE_DIR}/%s" <<'\''%s'\''\n' "$relative" "$PAYLOAD_EOF"
    cat "$FIXTURES_DIR/$relative"
    printf '%s\n' "$PAYLOAD_EOF"
  done
  # The table travels IN the payload and is exported from there, so no pin name
  # ever becomes an environment variable of the container: zsh sets ZSH_VERSION
  # itself, and a pin that collided with it would be compared against the shell.
  printf 'PIN_TABLE="$(cat <<'\''%s'\''\n' "$PAYLOAD_EOF"
  printf '%s\n' "$PIN_TABLE"
  printf '%s\n)"\n' "$PAYLOAD_EOF"
  printf 'export PIN_TABLE\n'
  printf 'ABSENT_TABLE="$(cat <<'\''%s'\''\n' "$PAYLOAD_EOF"
  printf '%s\n' "$ABSENT_TABLE"
  printf '%s\n)"\n' "$PAYLOAD_EOF"
  printf 'export ABSENT_TABLE\n'
  printf 'SMOKE_CHECKS=%q\n' "$CHECK_GROUPS"
  printf 'export SMOKE_CHECKS\n'
  # The name this run was asked about, which is what GOPHERSYS_DEVCONTAINER has
  # to equal. It comes from argv and is non-empty by the check at the top, so the
  # guest's "empty means no marker check" branch is for the pull request gate and
  # never for a real run.
  printf 'SMOKE_IMAGE=%q\n' "$IMAGE"
  printf 'export SMOKE_IMAGE\n'
  printf 'SMOKE_GUEST="$(mktemp)"\n'
  printf 'cat > "$SMOKE_GUEST" <<'\''%s'\''\n' "$PAYLOAD_EOF"
  cat "$PROJECT_ROOT/image-checks.sh"
  printf '%s\n' "$PAYLOAD_EOF"
  printf 'exec bash "$SMOKE_GUEST" < /dev/null\n'
}

REF="${REF_ARG:-ghcr.io/gophersys/${IMAGE}:latest}"

# A missing tool is a failure, never a skip.
require_cmd docker

# The list this IMAGE publishes, which is the sanctioned set unless images.yaml
# narrows it. Selecting out of the sanctioned set instead would let a smoke run
# choose a platform the image does not build.
resolve_image_platforms "$IMAGE"

# Every entry of the list must be sanctioned before 1 of them is chosen.
require_sanctioned_platforms

# A smoke test runs 1 image, so it names exactly 1 platform. When the sanctioned
# set holds several, the answer is to SELECT one — never to refuse to run.
#
# Refusing is what this block did first: it exited 1 whenever the list held more
# than 1 entry. Widening SANCTIONED_PLATFORMS to a second architecture — the 1
# edit this whole feature exists to make possible — would then have exited 1 at
# build-and-push.yml BEFORE asserting anything, turning the publish job red while
# checking nothing. .claude/rules/00-identity.md says "Widening it is 1 edit, and
# every path reads it". This path reads it now.
#
# The token for the second architecture is deliberately not written anywhere in
# this file: _ctl/tests/platform-policy.test.sh forbids it on the named build
# path, and a comment is not an exemption.
#
# The order, and why:
#   1. SMOKE_PLATFORM, when an operator names one deliberately. It must still be
#      in the list, so this is a choice WITHIN the guard and not a way around it.
#   2. the platform of the docker DAEMON, when the list holds it. This is the
#      premise of the whole script: the version checks the Dockerfiles dropped
#      could not run under emulation, so the native variant is the one to smoke.
#      It is the live path now that the set holds 2: the amd64 pool smokes amd64
#      natively, and it took no edit here.
#   3. the only entry, when the list holds exactly 1. On a developer host of
#      another architecture it runs emulated.
#   4. otherwise FAIL, naming the list and the daemon. An unspecified platform is
#      how a smoke test silently asserts against the wrong architecture, which is
#      worse than not running.
#
# The daemon is read rather than `uname -m` because the daemon is what runs the
# container: on Docker Desktop the host is darwin and the daemon is linux.
SMOKE_PLATFORM_RESOLVED=""
function platform_is_listed() {
  [[ ",${IMAGE_PLATFORMS}," == *",${1},"* ]]
}
function resolve_smoke_platform() {
  local requested="${SMOKE_PLATFORM:-}"
  if [[ -n "$requested" ]]; then
    if ! platform_is_listed "$requested"; then
      log_error "SMOKE_PLATFORM=${requested} is not in IMAGE_PLATFORMS (${IMAGE_PLATFORMS})"
      log_error "a smoke test may choose among the sanctioned platforms; it may not add one"
      exit 1
    fi
    SMOKE_PLATFORM_RESOLVED="$requested"
    return 0
  fi

  local daemon="" status=0
  daemon="$(docker version --format '{{.Server.Os}}/{{.Server.Arch}}')" || status=$?
  if [[ "$status" -ne 0 || -z "$daemon" ]]; then
    log_error "cannot read the platform of the docker daemon (docker version exited ${status})"
    log_error "the daemon has to answer before this script can choose which image to run"
    exit 1
  fi

  if platform_is_listed "$daemon"; then
    SMOKE_PLATFORM_RESOLVED="$daemon"
    return 0
  fi
  if [[ "$IMAGE_PLATFORMS" != *,* ]]; then
    SMOKE_PLATFORM_RESOLVED="$IMAGE_PLATFORMS"
    log_info "the daemon is ${daemon} and the only sanctioned platform is ${SMOKE_PLATFORM_RESOLVED}; this run is emulated"
    return 0
  fi

  log_error "cannot choose a platform to smoke: the daemon is ${daemon}, which is not in IMAGE_PLATFORMS (${IMAGE_PLATFORMS})"
  log_error "name one with SMOKE_PLATFORM=<platform>; running an unnamed one would assert against an architecture nobody chose"
  exit 1
}
resolve_smoke_platform

# The image has to be here before anything is asserted about it, and here FOR THE
# PLATFORM that was chosen. A pull that failed and a tool that is absent both come
# back as a non-zero status, and they are not the same defect — so the one that
# happened is named.
#
# The architecture is read rather than assumed. `docker image inspect` answers
# about whichever variant the local store holds, so an image of one architecture
# satisfies a bare presence check, and `docker run --platform <the other one>`
# then fails with "pull access denied ... may require 'docker login'" — a
# message about credentials, for a defect that is an architecture. Measured.
#
# The inspect is quiet on purpose: its "No such image" is the expected answer on
# a cold host, and the branch below acts on it.
STORED_PLATFORM=""
if ! STORED_PLATFORM="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$REF" 2>/dev/null)"; then
  STORED_PLATFORM=""
fi
if [[ "$STORED_PLATFORM" != "$SMOKE_PLATFORM_RESOLVED" ]]; then
  if [[ -n "$STORED_PLATFORM" ]]; then
    log_info "${REF} is in the local store as ${STORED_PLATFORM}, and this run needs ${SMOKE_PLATFORM_RESOLVED}"
  else
    log_info "${REF} is not in the local image store"
  fi
  log_info "pulling ${REF} for ${SMOKE_PLATFORM_RESOLVED}"
  if ! docker pull --platform "$SMOKE_PLATFORM_RESOLVED" "$REF"; then
    log_error "cannot obtain ${REF} for ${SMOKE_PLATFORM_RESOLVED}${STORED_PLATFORM:+ — the local store holds ${STORED_PLATFORM} instead}"
    log_error "NOTHING was asserted about this image"
    exit 1
  fi
fi

# image_unpacked_size_bytes <ref> — the UNPACKED size of a stored image, in
# bytes: the sum of the per-layer sizes `docker history` reports.
#
# ============================================================================
# READ THIS BEFORE CHANGING THE READ. IT IS LEDGER #119.
# ============================================================================
#
# This was `docker image inspect --format '{{.Size}}'`, and that template does
# NOT answer the same question on every daemon:
#
#   - under the CLASSIC (graphdriver) image store it answers the UNPACKED size,
#     which is the basis every size_budget_gb in images.yaml was set on;
#   - under the CONTAINERD image store it answers the CONTENT size instead: the
#     sum of the COMPRESSED layer blobs.
#
# WHICH STORE A DAEMON RUNS IS NOT THIS REPOSITORY'S TO CHOOSE. The dind the
# arc-build pods talk to answers the second way, and the numbers below are how
# that was found rather than a claim about a docker version.
#
# The daemon under this smoke changed basis without a commit here. cloud read
# 5,627,002,516 bytes in run 32039450157 (2026-08-17T14:33Z) and 2,059,410,281
# in run 32055368934 (2026-08-17T18:32Z), and by 2026-08-18 all 3 budgets were
# being compared against a number 3.4x to 4.2x under them. Nothing went red,
# because a smaller number is still under a budget — so 3 acceptance metrics
# stopped being able to fail and every run went on printing that they passed.
#
# `docker history --human=false` is the store-invariant answer. Measured on a
# mac at docker 29.5.3 with the containerd store, against an image holding
# 400,000,000 bytes of zeros: `image inspect --format '{{.Size}}'` said
# 4,483,568 and the history lines summed to 409,493,504.
#
# 3 readings are refusals here rather than a number:
#
#   - a history that cannot be READ. There is no size, so there is no gate.
#   - a history with NO LAYER in it. It sums to 0, and 0 is under every budget
#     anybody will ever write — the believed-and-empty check again.
#   - a line that is NOT A COUNT OF BYTES. This is the defect's own class one
#     flag away: without `--human=false` docker prints `4GB`. Measured —
#     `t=$((t + 4GB))` under `set -Eeuo pipefail` aborts with
#     `value too great for base (error token is "4GB")`, which names neither
#     this gate nor the image, and it would abort the smoke of an image nobody
#     had measured. The refusal below names both.
function image_unpacked_size_bytes() {
  local reference="$1"
  local lines
  if ! lines="$(docker history --human=false --format '{{.Size}}' "$reference")"; then
    return 1
  fi
  if [[ -z "$lines" ]]; then
    log_error "docker history reported no layer for ${reference}"
    log_error "a sum over no layer is 0 bytes, which is under every budget — so this is a FAILURE and not a size"
    return 1
  fi
  local total=0 line
  while IFS= read -r line; do
    if [[ -z "$line" ]]; then
      continue
    fi
    if [[ ! "$line" =~ ^[0-9]+$ ]]; then
      log_error "docker history reported '${line}' as a layer size of ${reference}, which is not a count of bytes"
      log_error "the gate compares BYTES; a human-readable size would compare a number nobody measured"
      return 1
    fi
    total=$((total + line))
  done <<< "$lines"
  printf '%s\n' "$total"
}

# The size gate: the acceptance budget images.yaml declares for THIS image, in
# decimal GB — the unit every census figure of this repository uses. It runs on
# the HOST against the loaded or pulled image, BEFORE the container smoke, and
# in CI this whole script runs before the push, so an oversize image never
# reaches a consumer.
#
# It was `if [[ "$IMAGE" == "cloud" ]]` with 5750000000 spelled inside it, and
# the branch is what changed rather than the rule. The budget is DATA now, so
# the budget of the next image is a manifest row and not a second branch here —
# and the MEASUREMENT that set each budget lives beside the key it justifies,
# which is where a reader tempted to raise one will be standing. cloud's R4
# history moved there whole.
#
# THE BASIS IS UNPACKED BYTES, and the reader above is where that is enforced.
# A log line from before 2026-08-18 carries the other basis for the same image,
# so the lines below name the basis rather than only the number.
#
# An image that declares no budget takes no gate. Read images.yaml for which
# ones: a count written here is a count that goes stale, and this file has done
# that twice already. The refusals are all FAILURES and never skips: a budget
# that cannot be READ, and — inside the reader — a size the daemon will not
# report, a size with no layer behind it, and a size that is not in bytes.
SIZE_BUDGET_BYTES="$(image_size_budget_bytes "$IMAGE")" || exit 1
if [[ -n "$SIZE_BUDGET_BYTES" ]]; then
  SIZE_BUDGET_GB="$(image_size_budget_gb "$IMAGE")"
  IMAGE_SIZE_BYTES=""
  if ! IMAGE_SIZE_BYTES="$(image_unpacked_size_bytes "$REF")"; then
    log_error "cannot read the unpacked size of ${REF} for the ${IMAGE} ${SIZE_BUDGET_GB} GB size gate"
    log_error "the gate cannot run, which is a FAILURE and not a skip"
    exit 1
  fi
  if [[ "$IMAGE_SIZE_BYTES" -gt "$SIZE_BUDGET_BYTES" ]]; then
    log_error "${IMAGE} size gate: ${REF} is ${IMAGE_SIZE_BYTES} unpacked bytes, over the ${SIZE_BUDGET_BYTES}-byte (${SIZE_BUDGET_GB} GB) budget"
    log_error "the budget is an acceptance metric declared in ${IMAGES_MANIFEST}, with the measurement that set it beside the key"
    log_error "it does not move quietly: read that comment before you raise the number"
    exit 1
  fi
  log_info "${IMAGE} size gate: ${IMAGE_SIZE_BYTES} unpacked bytes <= ${SIZE_BUDGET_BYTES} (${SIZE_BUDGET_GB} GB budget)"
fi

RUN_ARGS=(
  --rm
  --interactive
  --platform "$SMOKE_PLATFORM_RESOLVED"
)
if [[ "$IMAGE" == "embedded" ]]; then
  # The embedded image ships USER root and its entrypoint drops to dev. Force
  # the dev user so the base checks run in the same identity as the other
  # images.
  #
  # This is ALSO the non-root arm of the entrypoint's euid test, and it is
  # reached by accident rather than by design: at euid != 0 the entrypoint execs
  # the argv below plainly instead of through runuser. Nothing here exercises
  # the euid-0 arm — _ctl/tests/embedded-entrypoint.test.sh is that coverage.
  #
  # THIS ARM IS THE COST OF `USER root`, and root is what the deleted pod half
  # needed. Collapsing the image onto `USER dev` would delete this branch with
  # it; that is stated as open work at the top of embedded-entrypoint.sh.
  RUN_ARGS+=(--user dev)
fi

log_info "running smoke test in ${REF} (${SMOKE_PLATFORM_RESOLVED})"
log_info "asserting $(printf '%s\n' "$PIN_TABLE" | wc -l | tr -d ' ') pins of ${PIN_HOMES_TEXT}; check groups: ${CHECK_GROUPS}"
log_info "probing $(printf '%s\n' "$ABSENT_TABLE" | wc -l | tr -d ' ') binaries for absence"
docker run "${RUN_ARGS[@]}" "${REF}" bash -s <<< "$(payload_text)"
log_info "smoke test passed for ${IMAGE}"
