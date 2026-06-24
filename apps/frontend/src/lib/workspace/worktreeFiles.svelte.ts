// The project WORKTREE data layer — the reactive store behind the workspace CENTER pane (the
// generated-assets file tree + viewer). One concept, one home: this module owns (1) the
// WorktreeFileSource PORT — the consumer-defined seam the workspace lists + reads files through, so
// a real gateway adapter backs it in the app and an in-memory fake backs it in a render test (the
// same real-vs-fake mirror the gateway client uses) — and (2) WorktreeStore, the Svelte 5 runes
// reducer that folds a list + a per-file read into renderable tree + viewer state, refreshing LIVE
// as commits land (the host re-polls and the store reconciles).
//
// No field here can carry a credential: a worktree entry is a relative path + size + mtime, and a
// file payload is its text content + a content-kind tag — the redaction-safe projection the gateway
// already guarantees on its workspace surface (workspace_handler.go: every emitted path stays within
// the root, dotfiles/.git are skipped). The gateway adapter binds the EXISTING list contract
// (GET /sessions/{id}/workspace) and the file-read contract this layer specifies
// (GET /sessions/{id}/workspace/file?path=<rel> — see GatewayWorktreeSource).

import { resolveGatewayUrl } from '$lib/gateway/configuration';

/** One file under the project worktree root — the wire DTO the gateway's workspace list emits
 *  (workspaceFileView, wire.go): a slash-separated path RELATIVE to the root (never absolute, never
 *  escaping), its size in bytes, and its mtime as a Unix second. No field is a credential. */
export interface WorktreeFile {
  path: string;
  size: number;
  modifiedUnix: number;
}

/** The content kind the viewer renders a file as — derived from its extension, so the viewer
 *  pretty-renders markdown + JSON and falls back to monospaced plaintext for everything else. */
export type FileContentKind = 'markdown' | 'json' | 'text';

/** One file's content payload: its relative path, the decoded text, and the kind the viewer
 *  dispatches on. The gateway adapter reads this from the file-read contract; the fake supplies it
 *  inline. Text only — a binary file is surfaced as a notice by the viewer, never decoded blindly. */
export interface WorktreeFileContent {
  path: string;
  text: string;
  kind: FileContentKind;
}

/** WorktreeFileSource is the workspace's file PORT: the consumer-defined seam the center pane lists
 *  and reads the project worktree through. Two methods (well under the 5-method ceiling):
 *
 *    • list() returns the worktree's files (relative paths + size + mtime), newest-walk order;
 *    • read(path) returns one file's text content + content kind, or throws when the path is absent
 *      or not a decodable text file.
 *
 *  The real adapter (GatewayWorktreeSource) binds the gateway's workspace surface; a fake backs the
 *  render test, so the whole center pane is provable without a live gateway. */
export interface WorktreeFileSource {
  list(): Promise<WorktreeFile[]>;
  read(path: string): Promise<WorktreeFileContent>;
}

/** classifyContentKind maps a path's extension onto the viewer's content kind. Markdown + JSON
 *  pretty-render; everything else is plaintext (the safe, lossless default). Pure + cheap. */
export function classifyContentKind(path: string): FileContentKind {
  const lower = path.toLowerCase();
  if (lower.endsWith('.md') || lower.endsWith('.markdown')) return 'markdown';
  if (lower.endsWith('.json')) return 'json';
  return 'text';
}

/** prettyJson re-indents a JSON string to two spaces for the viewer, returning the input UNCHANGED
 *  when it does not parse (a partial or malformed file still renders as-is rather than vanishing).
 *  Pure — no throw escapes. */
export function prettyJson(text: string): string {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

/** The gateway-backed WorktreeFileSource: it binds the live agentgateway workspace surface.
 *
 *  • list()  → GET /sessions/{id}/workspace            (the EXISTING root-scoped list contract,
 *              workspace_handler.go: { files: [{path,size,modifiedUnix}] }).
 *  • read()  → GET /sessions/{id}/workspace/file?path=<rel>   (SERVED by router.go:50 →
 *              handleWorkspaceFile; the body is { path, kind, text }, traversal-safe with a 1 MiB
 *              cap. If a read faults, read() surfaces the gateway's typed fault, which the viewer
 *              shows as an honest "could not read" notice rather than a blank pane).
 *
 *  The session id is the supervisor/build session bound to the project (project.supervisorAgentId,
 *  falling back to the legacy sessionId). No credential rides either request. */
export class GatewayWorktreeSource implements WorktreeFileSource {
  private readonly baseUrl: string;
  private readonly sessionId: string;

  constructor(sessionId: string, baseUrl: string = resolveGatewayUrl()) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.sessionId = sessionId;
  }

  async list(): Promise<WorktreeFile[]> {
    const response = await fetch(this.fileUrl('/workspace'));
    if (!response.ok) {
      throw new Error(`could not list worktree files (${response.status})`);
    }
    const body = (await response.json()) as { files?: WorktreeFile[] };
    return body.files ?? [];
  }

  async read(path: string): Promise<WorktreeFileContent> {
    const query = new URLSearchParams({ path });
    const response = await fetch(this.fileUrl(`/workspace/file?${query.toString()}`));
    if (!response.ok) {
      throw new Error(`could not read ${path} (${response.status})`);
    }
    const body = (await response.json()) as Partial<WorktreeFileContent>;
    // The gateway stamps the kind; if a forward-compatible gateway omits it, classify locally so
    // the viewer still pretty-renders (one home for the extension rule).
    return {
      path,
      text: body.text ?? '',
      kind: body.kind ?? classifyContentKind(path),
    };
  }

  private fileUrl(suffix: string): string {
    return `${this.baseUrl}/sessions/${encodeURIComponent(this.sessionId)}${suffix}`;
  }
}

/** WorktreeStore owns the reactive worktree state the center pane renders: the file list, the
 *  selected path, the loaded content of the selection, and honest loading/error flags. The host
 *  calls refresh() on mount + whenever a commit lands (the build session's activity is the live
 *  "files changed" signal); select(path) loads one file's content. Construct it with a
 *  WorktreeFileSource (real or fake), so the whole pane is testable without a gateway. */
export class WorktreeStore {
  private readonly source: WorktreeFileSource;

  // Reactive surface ($state) — the center pane reads these directly.
  files = $state<WorktreeFile[]>([]);
  selectedPath = $state<string | null>(null);
  content = $state<WorktreeFileContent | null>(null);
  listError = $state<string | null>(null);
  contentError = $state<string | null>(null);
  loadedList = $state(false);
  loadingContent = $state(false);

  constructor(source: WorktreeFileSource) {
    this.source = source;
  }

  /** refresh re-lists the worktree (called on mount + on every commit-landed signal). It preserves
   *  the current selection across refreshes when the file still exists, and auto-selects a sensible
   *  default on the FIRST successful list (the first generated product asset) so the viewer is never
   *  blank when assets exist. A list fault is surfaced (not swallowed) and does not clear a prior
   *  good listing — a transient gateway blip should not blank the tree. */
  async refresh(): Promise<void> {
    try {
      const next = await this.source.list();
      this.files = next;
      this.listError = null;
      this.loadedList = true;
      // First good list with assets and no selection → open the most salient generated file.
      if (this.selectedPath === null && next.length > 0) {
        void this.select(defaultSelection(next));
      } else if (this.selectedPath !== null && !next.some((f) => f.path === this.selectedPath)) {
        // The selected file vanished (a rewrite/rename across commits): fall back to the default.
        void this.select(next.length > 0 ? defaultSelection(next) : null);
      }
    } catch (cause) {
      this.listError = cause instanceof Error ? cause.message : String(cause);
      this.loadedList = true;
    }
  }

  /** select loads one file's content into the viewer. A null path clears the selection (the empty
   *  viewer). A read fault is surfaced on the viewer as an honest notice; the selection still moves
   *  so the user sees WHICH file failed rather than a silent no-op. */
  async select(path: string | null): Promise<void> {
    this.selectedPath = path;
    this.contentError = null;
    if (path === null) {
      this.content = null;
      return;
    }
    this.loadingContent = true;
    try {
      const loaded = await this.source.read(path);
      // Guard a stale read landing after the selection moved on.
      if (this.selectedPath !== path) return;
      this.content = loaded;
      this.contentError = null;
    } catch (cause) {
      if (this.selectedPath !== path) return;
      this.content = null;
      this.contentError = cause instanceof Error ? cause.message : String(cause);
    } finally {
      if (this.selectedPath === path) this.loadingContent = false;
    }
  }
}

/** defaultSelection picks the most salient generated asset to open first: the project's PRODUCT.md
 *  (or any markdown under init/product/), else the first markdown, else the first file. Pure. */
export function defaultSelection(files: readonly WorktreeFile[]): string {
  const productMd = files.find(
    (f) => /(^|\/)product\//i.test(f.path) && /\.md$/i.test(f.path),
  );
  if (productMd) return productMd.path;
  const anyMd = files.find((f) => /\.md$/i.test(f.path));
  if (anyMd) return anyMd.path;
  return files[0].path;
}
