# .claude — the template's AI authoring instrumentation

> Directory README (ADR-0023). This is the http-gateway template's own AI-instrumentation surface:
> the CRUD-authoring rules an agent extending a GENERATED app follows, so the app stays on the same
> five-file, OpenAPI-first, no-shortcuts discipline the template was built on.

## rules/

Injected at SessionStart (the ordered CRUD authoring loop):

| Rule | Scope |
|---|---|
| `00-add-resource.md` | The ordered loop for adding/extending a resource (drives the other four). |
| `10-five-files-per-route.md` | The cardinal structural rule: route = five files; authz = the `Required` field. |
| `20-schema-and-migrations.md` | sqlc-over-pgx: the schema/migration lockstep; typed queries. |
| `30-openapi-and-clients.md` | OpenAPI-first; emit the clients; never hand-edit generated. |
| `40-test-loop.md` | The phase-gate sequence + the no-shortcuts / real-substrate bar. |

These EXTEND (never replace) the shared `libs/.claude/rules/` (naming, interface-design,
error-handling, the library pipeline, the test taxonomy) — those still apply; these add the app
shape on top.

## hooks/

A placeholder for the template's lifecycle hooks (a SessionStart that injects the rules above, a
PostToolUse that lints an edited `*.go`, a PreToolUse that gates `git commit`/`push` on
`phase-gate qa`). The bodies are wired when the template is promoted to a registered Claude Code
plugin (mirroring `libs/plugins/project-go/`); see `hooks/README.md`.
