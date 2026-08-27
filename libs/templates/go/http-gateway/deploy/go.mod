// Module github.com/gophersys/libs/templates/go/http-gateway/deploy — the http-gateway
// template's deploy surface. It is its OWN module (a build-time renderer, like eden's
// deploy/servicespec) so it never enters the gateway's runtime dependency graph, and it is NOT in
// the workspace go.work.
//
// It REUSES eden's deploy/servicespec renderer (ADR-0023: reuse, never reinvent) rather than
// re-implementing compose/Helm rendering. servicespec is a deliberately-unpublished build-time tool
// module kept OUT of go.work, so it is resolved here by a relative `replace` into the superproject
// working tree (the monorepo), where libs/templates always sits as a submodule. This is the
// sanctioned exception to the no-module-replace rule, which targets the go.work SIBLING libraries —
// servicespec is neither a sibling lib nor a go.work member.
module github.com/gophersys/libs/templates/go/http-gateway/deploy

go 1.26

require github.com/gophersys/eden/deploy/servicespec v0.0.0

replace github.com/gophersys/eden/deploy/servicespec => ../../../../../deploy/servicespec
