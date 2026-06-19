# hooks — lifecycle hook placeholder

> Directory README (ADR-0023). Placeholder for the http-gateway template's Claude Code lifecycle
> hooks. The bodies are wired when the template is promoted to a registered plugin, mirroring
> `libs/plugins/project-go/hooks/`.

Intended hooks (parity with the library pipeline's instrumentation):

| Hook | Event | Job |
|---|---|---|
| `session-start.sh` | SessionStart | Inject `../rules/*.md` (the CRUD authoring loop), phase-aware. |
| `post-edit-lint.sh` | PostToolUse (Edit/Write on `*.go`) | gofumpt + golangci-lint the edited file; warn on a route that breaks the five-file shape. |
| `pre-git-gate.sh` | PreToolUse (`git commit`/`push`) | Gate on `bash ./ctl.sh phase-gate qa` for the touched app. |
| `stop-phase-check.sh` | Stop | Block turn-end while a touched app's `phase-gate qa` is red. |

This is intentionally a placeholder, not a stub of logic: the hook bodies belong to the plugin
promotion step, not the skeleton. Keeping the directory + this contract here marks the intent so the
promotion is a fill-in, not a redesign.
