#!/usr/bin/env bash
#
# apps/platformgateway/ctl.sh — control script for platformgateway, Eden's platform HTTP API
# (an OpenAPI-first, sqlc/pgx HTTP service that assembles the Eden Go libraries). Scaffolded from
# the libs/templates/go/http-gateway template (ADR-0023): Eden builds Eden.
#
# Thin dispatcher (ADR-0023, mirroring ADR-0020): the verb BODIES live once in
# libs/templates/_ctl/template.sh ("one concept, one home", 10 §9). This file sets the
# per-app metadata and sources that shared library. project.json targets delegate here.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT

# -------- per-template metadata (ADR-0023) --------
EDEN_TEMPLATE_NAME="platformgateway"
EDEN_COVERAGE_FLOOR="80"
# The integration lane stands up a REAL postgres (sqlc/pgx) on docker; the deploy lane reaches for
# k3d/kind when the rendered manifests are exercised end-to-end.
EDEN_INTEGRATION_CMDS="docker"
# The two codegen axes (ADR-0023): persistence/ (sqlc) and clients/go/ (OpenAPI test client). Each
# is its own Nx sub-project with its own ctl.sh; `generate` delegates to both.
EDEN_CODEGEN_PROJECTS="persistence clients/go"
# OD-16-openapi = GO-FIRST-EMIT (ADR-0023): contract/openapi.yaml is EMITTED from the five-file route
# packages' Go types by tools/openapi, not hand-authored. `openapi` emits it, `verify-openapi` gates
# drift, `gen-client` runs oapi-codegen over it, and `generate` chains emit → sqlc → client.
EDEN_OPENAPI_EMITTER="./tools/openapi"
EDEN_OPENAPI_CONTRACT="contract/openapi.yaml"
EDEN_CLIENT_PROJECT="clients/go"
export EDEN_TEMPLATE_NAME EDEN_COVERAGE_FLOOR EDEN_INTEGRATION_CMDS EDEN_CODEGEN_PROJECTS
export EDEN_OPENAPI_EMITTER EDEN_OPENAPI_CONTRACT EDEN_CLIENT_PROJECT

# The verb bodies live ONCE in the libs/templates subtree's shared ctl library (one home,
# 10 §9). platformgateway sits at apps/ in the eden superproject, so reach across to the submodule.
# shellcheck source=../../libs/templates/_ctl/template.sh
# shellcheck disable=SC1091
source "$PROJECT_ROOT/../../libs/templates/_ctl/template.sh"

case "${1:-help}" in
  help|"") template_usage ;;
  *)       template_main "$@" ;;
esac
