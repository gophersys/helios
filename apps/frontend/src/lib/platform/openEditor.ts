// openEditor — the ONE place the "Open in VS Code" branch lives, extracted from the workspace page so
// the desktop-vs-web decision is unit-testable in isolation (and reusable: any surface that opens the
// read-only editor for a worktree uses this, not a re-spelled branch). The decision (ADR-0006):
//   • DESKTOP (Tauri) AND a non-empty sshHost  → hand the OS a vscode://…ssh-remote URI so the user's
//     NATIVE VS Code attaches to the read-only ssh sandbox (workstream C). location.href, not a tab.
//   • otherwise (WEB, or desktop without an ssh host) → open the code-server URL in a REUSABLE named
//     window ('eden-vscode'); a second open of a different project re-points the same window.
// It is injected with the platform probe + the window seams so a test drives every branch without a DOM
// (the page passes the real isDesktop / window). SSR-safe: it touches no global directly.

import type { EditorView } from '$lib/gateway/client';

/** The narrow window seam openEditor needs — exactly the two navigations the two branches use. The
 *  page passes the real `window`; a test passes a mock. (Consumer-defined port, ≤5 members.) */
export interface EditorWindow {
  /** Open a URL in a (re-pointable) named window — the WEB code-server tab. */
  open(url: string, target: string): { opener: unknown } | null;
  /** The location whose href the DESKTOP branch assigns the vscode:// URI to. */
  location: { href: string };
}

/** The desktop-runtime probe seam (src/lib/platform/runtime.ts `isDesktop`), injected so the branch is
 *  driven deterministically in a test without faking `window.__TAURI__`. */
export type DesktopProbe = () => boolean;

/** buildSshRemoteUri forms the vscode ssh-remote URI the native VS Code opens. It is the SINGLE home of
 *  the URI shape so the page and the test agree by construction (one concept, one home). */
export function buildSshRemoteUri(sshHost: string, worktreePath: string): string {
  return `vscode://vscode-remote/ssh-remote+${sshHost}${worktreePath}`;
}

/** openEditor applies the desktop/web branch for a resolved EditorView. Returns the kind of navigation
 *  taken ('desktop' | 'web') so a caller/test can assert WITHOUT inspecting the window — the navigation
 *  itself still happens through the injected seam. Desktop requires BOTH the desktop runtime AND a
 *  non-empty sshHost; anything else is the web path (the honest fallback). */
export function openEditor(
  editor: EditorView,
  win: EditorWindow,
  isDesktop: DesktopProbe,
): 'desktop' | 'web' {
  if (isDesktop() && editor.sshHost) {
    win.location.href = buildSshRemoteUri(editor.sshHost, editor.worktreePath);
    return 'desktop';
  }
  const opened = win.open(editor.url, 'eden-vscode');
  if (opened) opened.opener = null;
  return 'web';
}
