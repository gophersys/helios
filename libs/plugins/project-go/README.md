# project-go — Eden Go authoring guardrails (ADR-0018 Layer 2)

A Claude Code plugin that constrains Go authoring in the Eden libraries at **edit time**,
so the standard shapes generation instead of only being caught at the gate. It is the
"AI-instrumented authoring" half of ADR-0018; the deterministic teeth are the same
`golangci-lint` / `hnslint` checks, run here at three trigger points.

## What fires, when

| Hook | Event | What it does |
|---|---|---|
| `hooks/session-start.sh` | **SessionStart** | Injects `libs/.claude/rules/*.md` (interface design, HNS-1 naming, error handling) plus any active frozen contract (`$EDEN_ACTIVE_CONTRACT`, else lists `docs/architecture/contracts/`) into the agent's context, with the standing instruction that the rules are enforced, not optional. |
| `hooks/post-edit-lint.sh` | **PostToolUse** on `Edit`/`Write`/`MultiEdit` | On any `*.go` edit, runs `gofumpt -l` + `golangci-lint` (fast path) on the file's module and `hnslint` on its `libs/go/<lib>`, and returns the findings to the agent (`hookSpecificOutput.additionalContext`) so it self-corrects **before** proceeding. This is the inner-loop check that would have caught `cfgtest`. |
| `hooks/pre-git-gate.sh` | **PreToolUse** on `Bash` | When the command is `git commit` / `git push`, runs the full gate over the staged tree (commit) or the commits ahead of upstream (push) and **denies** the tool call on any violation, feeding the findings back. Honours `--no-verify`. |

Hooks degrade gracefully: a tool not yet installed becomes a skip, never a crash — the
non-bypassable enforcement is CI, which re-runs the identical gate.

## Enabling it

The plugin is registered in the marketplace at `libs/.claude-plugin/marketplace.json`
(marketplace `eden-libs`, plugin source `./plugins/project-go`). From the monorepo root:

```bash
claude plugin marketplace add ./libs          # register the eden-libs marketplace
claude plugin install project-go@eden-libs     # install the plugin
# restart Claude Code (hooks load at session start)
```

Validate the manifests at any time:

```bash
claude plugin validate libs/plugins/project-go
claude plugin validate libs
```

## Relationship to the git hooks

The tracked `.githooks/` (eden repo) catch a human or agent running `git` directly; this
plugin's PreToolUse gate catches the agent inside the Claude Code harness and gives it the
findings inline. Same checks, two trigger points — defense in depth (ADR-0018, 10 §8).

## Layout

```
plugins/project-go/
├── .claude-plugin/plugin.json   # manifest (validated by `claude plugin validate`)
├── hooks/
│   ├── hooks.json               # SessionStart + PostToolUse + PreToolUse wiring
│   ├── _lib.sh                  # shared helpers (bash 3.2 safe, jq-optional)
│   ├── session-start.sh
│   ├── post-edit-lint.sh
│   └── pre-git-gate.sh
└── skills/api-design/SKILL.md   # layer (B): the Go rendering of the rules (10 §9)
```
