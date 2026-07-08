#!/usr/bin/env bash
#
# apps/frontend/deploy/build-libs.sh — emit the @eden/* workspace libraries the frontend production
# image consumes (their dist/), IN DEPENDENCY ORDER. Run this in the devcontainer (the ADR-0022 dev/CI
# substrate with the full yarn-4-installed Svelte toolchain) BEFORE `docker build`ing the frontend
# image: the libs' build tools (@sveltejs/package + @sveltejs/vite-plugin-svelte + vitest) resolve only
# through the workspace install, which is not reproducible in the lean bun-alpine build stage — so the
# frontend Dockerfile ships the dist in rather than rebuilding the libs. See deploy/Dockerfile.
#
# The frontend's own build (svelte-kit sync + vite build) STILL runs inside the image; only the four
# @eden/* libraries are prebuilt here.
#
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$REPO_ROOT" ] || REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
LIBS_DIR="$REPO_ROOT/libs/typescript"

log() { printf '\033[0;36m[build-libs]\033[0m %s\n' "$*" >&2; }
die() { printf '\033[0;31m[build-libs:error]\033[0m %s\n' "$*" >&2; exit 1; }

# Dependency order: scale + theme are pure-tsc foundations; primitives depends on theme (+ scale via
# theme); visualization is a leaf. Building in this order guarantees each lib's deps' dist exist first.
LIBS=(scale theme primitives visualization)

for lib in "${LIBS[@]}"; do
  lib_dir="$LIBS_DIR/$lib"
  [ -d "$lib_dir" ] || die "library not found: $lib_dir"
  log "building @eden/$lib …"
  bash "$lib_dir/ctl.sh" build || die "@eden/$lib build failed (is the devcontainer toolchain installed? run 'yarn install' at the workspace root)"
  [ -f "$lib_dir/dist/index.js" ] || die "@eden/$lib build produced no dist/index.js"
done

log "DONE — the four @eden/* libraries are built; the frontend image build can now consume their dist."
