// Package bom is the gateway's services Bill-of-Materials surface: the self-describing manifest of
// the libraries, contract version, and substrate a running gateway was assembled from. A generated
// app exposes it (e.g. behind GET /v1/bom or a startup log line) so a fleet operator can read, from
// the running process, exactly which library + contract versions are deployed — the services-BOM
// thesis (OD-15-bom, open fork A/B/C: embedded-at-build vs resolved-at-runtime vs a hybrid).
//
// SKELETON: the BOM is a typed value the composition root populates; HOW it is sourced — an
// embed-at-build of the module graph (fork A), a runtime debug.ReadBuildInfo read (fork B), or a
// hybrid (fork C) — is the OPEN fork recorded in open-decisions. The template ships the runtime-read
// shape (B) as the compiling default because it needs no build step; a real read, not a stub.
package bom

import "runtime/debug"

// BOM is the self-describing manifest of a running gateway. It is a plain value, safe to copy, JSON-
// marshalable for a /v1/bom response or a structured startup Event.
type BOM struct {
	// Service is the service slug ("platformgateway").
	Service string `json:"service"`
	// Version is the build's main-module version (the git-described tag, or "(devel)").
	Version string `json:"version"`
	// Substrate is the detected deployment substrate ("docker" | "kubernetes").
	Substrate string `json:"substrate"`
	// Modules is the resolved dependency set the binary was built from (path@version).
	Modules []Module `json:"modules"`
}

// Module is one resolved dependency in the BOM (the library path and the version it resolved to).
type Module struct {
	Path    string `json:"path"`
	Version string `json:"version"`
}

// Read assembles the BOM from the binary's build info (debug.ReadBuildInfo) plus the caller-supplied
// service slug and detected substrate. It is the runtime-read shape (fork B): no build step, the
// truth comes from the linked module graph. A nil/absent build info (a `go run` without module info)
// yields a BOM with the static fields and an empty module set rather than failing — a manifest is
// best-effort observability, never a load-bearing dependency.
func Read(service, substrate string) BOM {
	out := BOM{Service: service, Substrate: substrate, Version: "(unknown)"}
	info, ok := debug.ReadBuildInfo()
	if !ok {
		return out
	}
	out.Version = info.Main.Version
	out.Modules = make([]Module, 0, len(info.Deps))
	for _, dep := range info.Deps {
		out.Modules = append(out.Modules, Module{Path: dep.Path, Version: dep.Version})
	}
	return out
}
