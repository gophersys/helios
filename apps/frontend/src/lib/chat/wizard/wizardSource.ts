// wizardSource — the SEAM the SetupWizard drives, so the component stays a pure view with no network
// of its own (the same callback-injection pattern CreateProjectFlow uses for propose/onlaunch). It
// has exactly two responsibilities, mirroring the two inputs the wizard reads:
//
//   • the supervisor's COMMITTED ARTIFACTS — list + read the init/product/* files from the project's
//     workspace worktree. One concept, one home: the worktree file PORT already lives in
//     $lib/workspace/worktreeFiles (WorktreeFileSource + the gateway-backed GatewayWorktreeSource,
//     which binds GET /sessions/{id}/workspace[/file]). The wizard REUSES that port — it does not
//     re-spell the file I/O — and only adds the prefix-filtered convenience read it needs.
//   • the supervisor SESSION — send the user's brief / each answer to the live supervisor session
//     (sendToSupervisor), which is what makes the supervisor commit the questionnaire (after the
//     brief) and record each answer. This is the existing session control channel
//     (GatewayClient.prompt → POST /sessions/{id}/control verb=prompt) — no new send route is needed.
//
// Keeping this an interface (not a concrete gateway call inside the component) is what lets the
// Playwright E2E drive the WHOLE wizard over a FAKE supervisor file source + session, while the live
// wizard binds the same shape to the real gateway.
//
// ── WIZARD BACKEND CONTRACT (what the live supervisor + the backend file API must provide) ──────────
// The supervisor session's workspace root IS the project's worktree (the create-saga launches the
// supervisor with the project worktree as its CWD), so the wizard reads the interview through the
// SESSION-scoped workspace surface the workspace shell already specifies:
//
//   GET /sessions/{id}/workspace            → { files: [{ path, size, modifiedUnix }, …] }   EXISTS
//       (workspace_handler.go — relative, traversal-safe, sorted, dotfiles/.git skipped).
//   GET /sessions/{id}/workspace/file?path= → { path, kind, text }                           SPECIFIED
//       (the file-READ contract $lib/workspace/worktreeFiles specifies — NOT YET SERVED. Until the
//       gateway serves it, readFile surfaces the gateway's typed fault, which the wizard shows as an
//       honest inline error rather than a blank screen. The handler must mirror handleWorkspace's
//       traversal safety and refuse a non-text/oversize file with a typed error.)
//
// And the supervisor side must COMMIT the interview artifacts to that worktree as the session runs:
//   - after the DESCRIBE brief is sent, commit init/product/questionnaire/<NN>-<slug>.md per question
//     (one file = one question; the file body IS the question text),
//   - after each answer is sent, commit init/product/answers/<slug>.md (the recorded answer body),
//   - leave a question's answers file ABSENT (or blank) until it is answered — the advance guard reads
//     "no open questions" from exactly that.

import type { GatewayClient } from '$lib/gateway/client';
import {
  GatewayWorktreeSource,
  type WorktreeFileSource,
} from '$lib/workspace/worktreeFiles.svelte';
import type { WizardFile } from './setupWizard';

/** WizardSource is the SetupWizard's full I/O contract. Every method is async and may reject; the
 *  component surfaces a rejection as an inline, non-crashing error (never a swallowed failure). */
export interface WizardSource {
  /** List the committed files under the supervisor's workspace worktree whose worktree-relative path
   *  starts with `prefix` (e.g. "init/product/"). The wizard reads only the small init/product/* tree. */
  listFiles(prefix: string): Promise<string[]>;
  /** Read ONE committed file's UTF-8 text by its worktree-relative path. */
  readFile(path: string): Promise<string>;
  /** Send a turn (the DESCRIBE brief, or one Q&A answer) to the live supervisor session, which is
   *  what drives it to commit the questionnaire / record the answer. */
  sendToSupervisor(text: string): Promise<void>;
}

/** loadFiles is the shared "list a prefix, then read every file" helper the wizard uses to pull the
 *  committed init/product/* sub-trees into WizardFile records (path + text). It reads the listed
 *  files in parallel; a single unreadable file (a mid-commit race) is dropped rather than failing the
 *  whole load, so a partially-committed questionnaire still renders what landed. */
export async function loadFiles(source: WizardSource, prefix: string): Promise<WizardFile[]> {
  const paths = await source.listFiles(prefix);
  const settled = await Promise.allSettled(
    paths.map(async (path) => ({ path, text: await source.readFile(path) }) satisfies WizardFile),
  );
  const files: WizardFile[] = [];
  for (const result of settled) {
    if (result.status === 'fulfilled') files.push(result.value);
  }
  return files;
}

/** fromWorktreeSource adapts the workspace's WorktreeFileSource port (list-all + read-content) into
 *  the wizard's prefix-filtered list + text read. This is the one place the wizard's "I only want the
 *  init/product/* tree" filter sits on top of the shared worktree port — no file I/O is re-spelled. */
export function fromWorktreeSource(
  worktree: WorktreeFileSource,
  sendToSupervisor: (text: string) => Promise<void>,
): WizardSource {
  return {
    listFiles: async (prefix) => {
      const files = await worktree.list();
      return files.map((file) => file.path).filter((path) => path.startsWith(prefix));
    },
    readFile: async (path) => (await worktree.read(path)).text,
    sendToSupervisor,
  };
}

/** createGatewayWizardSource binds the WizardSource to the LIVE gateway: the supervisor session's
 *  workspace surface (via the shared GatewayWorktreeSource) for the committed-artifact reads, and the
 *  supervisor session's control channel (GatewayClient.prompt) for sendToSupervisor.
 *  `supervisorSessionId` is the live build session the create-saga launched
 *  (projectView.supervisorAgentId, falling back to the legacy sessionId). */
export function createGatewayWizardSource(
  client: GatewayClient,
  supervisorSessionId: string,
): WizardSource {
  const worktree = new GatewayWorktreeSource(supervisorSessionId, client.baseUrl);
  return fromWorktreeSource(worktree, async (text) => {
    await client.prompt(supervisorSessionId, text);
  });
}
