# Workspace components (staging home — promotion-ready)

This directory holds the **project workspace** — the XCode-like 3-pane workspace UI (W4) — built as
REUSABLE Eden components per the agent-UI lib principle (every UI element built reusable; libs →
demos; the demo only consumes).

They live here in `apps/frontend/src/lib/workspace` as the **staging home** pending the library
pipeline (ADR-0020). **Do not run the lib pipeline against them yet.** When they stabilize they
promote into `libs/typescript` (a new `@eden/workspace` lib) through the full four-phase gate, at
which point the few app-local citations (the `$lib/chat` conversation components, the `$lib/markdown`
renderer, the `$lib/gateway` `ProjectView` type) are taken as snippets / generic props so the lib
carries no app coupling.

## Components (all token-driven from `@eden/theme`; one-concept-one-home)

| File | Role |
| --- | --- |
| `WorkspaceShell.svelte` | The pure 3-pane LAYOUT (top bar over left + center). Zero domain coupling — content arrives as snippets. Promotes unchanged. |
| `ProjectTopBar.svelte` | The TOP BAR: git info (branch · last commit · repo link from `project.repoUrl`) + project settings (status · stacks · supervisor agent). Pure presentation over the `ProjectView` read model. |
| `SupervisorConversation.svelte` | The LEFT pane: the live conversation with the supervisor. REUSES the chat SSE rails (`ChatSession` + `$lib/chat` components) — renders the agentsession Event taxonomy. One home for the fold is `session.svelte.ts`; this only renders it. |
| `WorktreePane.svelte` | The CENTER pane: the worktree tree beside the file viewer, both driven by one `WorktreeStore`. |
| `WorktreeTree.svelte` | The nested, file-browser-style file tree (recurses on itself). |
| `FileViewer.svelte` | The viewer: markdown / JSON pretty-render (reuses the `$lib/markdown` pipeline) + plaintext fallback; honest loading/error/empty states. |
| `worktreeFiles.svelte.ts` | The data layer: the `WorktreeFileSource` PORT (real `GatewayWorktreeSource` + fake-able) and `WorktreeStore` (the runes reducer). |
| `worktreeTree.ts` | The pure flat-list → nested-tree fold (`buildTree`). |

## Backend contracts the workspace binds

- **File LIST** — `GET /sessions/{id}/workspace` — **EXISTS** (`workspace_handler.go`): the real files
  the supervisor produced under its workspace root, as `{ files: [{ path, size, modifiedUnix }] }`,
  relative + sorted + capped, dotfiles/`.git` skipped. Reused as-is.
- **File READ** — `GET /sessions/{id}/workspace/file?path=<rel>` — **SERVED** (`router.go:50` →
  `handleWorkspaceFile`): the `GatewayWorktreeSource.read()` adapter binds it; body `{ path, kind, text }`.
  The handler mirrors `handleWorkspace`'s traversal safety (cleans the relative path, rejects
  `..`/absolute, stays within the workspace root, skips dotfiles/`.git`), reads up to a 1 MiB cap, and
  marks `kind` `"text"`/`"binary"`. If a read faults, `read()` surfaces the gateway's typed fault,
  which the viewer shows as an honest "could not read" notice rather than streaming bytes.
- **Supervisor session binding** — `project.supervisorAgentId` (falling back to the legacy
  `project.sessionId`) is the build/supervisor session the conversation attaches to. EXISTS on the
  `projectView` projection (`project.go`).
