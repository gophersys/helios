#!/usr/bin/env bash
#
# .ci/pin-eden-digests.sh — pin the freshly-built Eden image DIGESTS into the infrastructure repo's
# apps/eden/*.yaml Deployment manifests (the release.yml promote job runs this against a checkout of
# gophersys/infrastructure at ./infrastructure). Digest-pinning (never :latest) is the deploy
# contract: Argo reconciles the exact image the release built.
#
# ROBUST TO FILE LAYOUT: the rewrite is keyed on the image REFERENCE stem
# `ghcr.io/gophersys/eden/<service>` on any `image:` line — it replaces whatever tag/digest follows
# (`:<tag>` or `@sha256:<old>`) with `@<new-digest>`. So it does not care which numbered file
# (30-agentgateway.yaml-style) a Deployment lives in, nor whether the ref was previously a tag or a
# digest. agentgateway AND orchestrator both run the agentgateway image, so BOTH lines pin to the
# agentgateway digest (one image, two Deployments).
#
# Inputs (env, set by the promote job from the per-service build outputs):
#   AGENTGATEWAY_DIGEST / AGENT_RUNTIME_DIGEST / PLATFORMGATEWAY_DIGEST / FRONTEND_DIGEST — each a
#   bare `sha256:...` digest (docker/build-push-action's `digest` output).
#   VERSION — the release version string (e.g. `v0.1.5`), from release-meta.sh. Each `image:` line is
#   preceded by a human-readable `# <version>` marker comment; when set, that comment is refreshed to
#   the new VERSION alongside the digest so the manifest never reads a stale version. Optional: if
#   VERSION is unset/empty the comment is left untouched (digest pinning is unaffected).
#
set -Eeuo pipefail

INFRA_DIR="${INFRA_DIR:-infrastructure}"
APPS_DIR="${INFRA_DIR}/apps/eden"

REGISTRY_PREFIX="ghcr.io/gophersys/eden"

# VERSION marks the human-readable `# <version>` comment above each image line; empty = leave alone.
VERSION="${VERSION:-}"

log() { printf '[pin-eden-digests] %s\n' "$*" >&2; }
die() { printf '[pin-eden-digests] ERROR: %s\n' "$*" >&2; exit 1; }

[ -d "$APPS_DIR" ] || die "infra apps dir not found: $APPS_DIR (is the infrastructure checkout at $INFRA_DIR ?)"

# pin_service <service-image-name> <digest>: rewrite every `image:` line whose ref is
# <registry>/<service>[:@...] to <registry>/<service>@<digest>. The service image name is the stem
# after the eden prefix (agentgateway, agent-runtime, platformgateway, frontend). The `orchestrator`
# Deployment uses the `agentgateway` IMAGE, so it is covered by the agentgateway pass (same stem).
pin_service() {
  local image="$1" digest="$2"
  [ -n "$digest" ] || die "empty digest for $image (the build job did not export one)"
  case "$digest" in
    sha256:*) : ;;
    *) die "digest for $image must be a bare sha256:… value (got: $digest)" ;;
  esac

  local ref="${REGISTRY_PREFIX}/${image}"
  # Escape the ref for the sed pattern (only '/' and '.' matter here; use '|' as the sed delimiter).
  local escaped="${ref//./\\.}"
  local hits=0

  # Match an `image:` line referencing this exact stem, with an OPTIONAL quote, followed by either
  # `:<tag>` or `@sha256:<old>` — replace the whole ref+tag/digest with ref@<new-digest>, preserving
  # the surrounding quote style. The stem boundary ([:@"]) prevents `agentgateway` from also matching
  # a hypothetical `agentgateway-foo`.
  while IFS= read -r file; do
    if grep -Eq "image:[[:space:]]*[\"']?${escaped}[:@]" "$file"; then
      sed -i -E "s|(image:[[:space:]]*[\"']?)${escaped}(@sha256:[a-f0-9]+\|:[A-Za-z0-9._-]+)|\\1${ref}@${digest}|g" "$file"
      hits=$((hits + 1))
      log "pinned ${image} in ${file##*/} -> @${digest}"

      # Refresh the `# <version>` marker comment that sits on the line ABOVE each pinned image line,
      # preserving its indentation. Scoped to THIS service's image line via the two-line window, so
      # only the comment belonging to the pin we just wrote is touched. Skipped when VERSION is empty.
      if [ -n "$VERSION" ]; then
        sed -i -E "/^([[:space:]]*)#[[:space:]].*\$/{N;s|^([[:space:]]*)#[[:space:]].*(\n[[:space:]]*image:[[:space:]]*[\"']?${escaped}@)|\\1# ${VERSION}\\2|}" "$file"
        log "  version comment -> # ${VERSION}"
      fi
    fi
  done < <(find "$APPS_DIR" -type f \( -name '*.yaml' -o -name '*.yml' \))

  [ "$hits" -gt 0 ] || die "no image line for ${ref} found under ${APPS_DIR} (is the manifest present?)"
}

pin_service "agentgateway"    "${AGENTGATEWAY_DIGEST:?AGENTGATEWAY_DIGEST is required}"
pin_service "agent-runtime"   "${AGENT_RUNTIME_DIGEST:?AGENT_RUNTIME_DIGEST is required}"
pin_service "platformgateway" "${PLATFORMGATEWAY_DIGEST:?PLATFORMGATEWAY_DIGEST is required}"
pin_service "frontend"        "${FRONTEND_DIGEST:?FRONTEND_DIGEST is required}"

log "DONE — apps/eden/*.yaml pinned to the release digests."
