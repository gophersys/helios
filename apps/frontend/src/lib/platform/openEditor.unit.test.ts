// openEditor.unit.test.ts — the desktop/web branch-selection contract for "Open in VS Code" (workstream
// C). It drives the SAME helper the workspace page calls, with a mocked window seam (open + location)
// and a mocked desktop probe, and asserts:
//   • DESKTOP (isDesktop()===true) + a non-empty sshHost → window.location.href is the EXACT
//     vscode://vscode-remote/ssh-remote+<host><worktreePath> URI, and NO web tab is opened.
//   • sshHost==='' (or web runtime) → falls back to window.open(url, 'eden-vscode') and DOES NOT touch
//     location.href.
// No real DOM navigation, no real Tauri — the seams are mocked, the decision is pure.

import { describe, it, expect, vi } from 'vitest';
import type { EditorView } from '$lib/gateway/client';
import { openEditor, buildSshRemoteUri, type EditorWindow } from '$lib/platform/openEditor';

/** A fresh mocked window seam: a spied open() returning a re-pointable window stub, and a location whose
 *  href the desktop branch assigns. Mirrors the two navigations the page's real `window` exposes. */
function makeWindow(): EditorWindow & {
  open: ReturnType<typeof vi.fn>;
  location: { href: string };
} {
  const openedWindow = { opener: {} as unknown };
  const open = vi.fn((_url: string, _target: string) => openedWindow);
  return { open, location: { href: '' } };
}

const DESKTOP_EDITOR: EditorView = {
  url: 'http://localhost:8500/?folder=/workspace/.eden-runtime/supervisors/x',
  worktreePath: '/workspace/.eden-runtime/supervisors/x',
  sshHost: 'eden-editor',
};

describe('openEditor branch selection', () => {
  it('DESKTOP + sshHost → navigates the native VS Code ssh-remote URI (no web tab)', () => {
    const win = makeWindow();
    const isDesktop = vi.fn(() => true);

    const taken = openEditor(DESKTOP_EDITOR, win, isDesktop);

    expect(taken).toBe('desktop');
    // The EXACT URI the prompt specifies.
    expect(win.location.href).toBe(
      'vscode://vscode-remote/ssh-remote+eden-editor/workspace/.eden-runtime/supervisors/x',
    );
    // The desktop path NEVER opens a browser tab.
    expect(win.open).not.toHaveBeenCalled();
  });

  it('empty sshHost → falls back to the reusable web code-server window (location untouched)', () => {
    const win = makeWindow();
    const isDesktop = vi.fn(() => true); // desktop runtime, but no ssh host → still the web path
    const webEditor: EditorView = { ...DESKTOP_EDITOR, sshHost: '' };

    const taken = openEditor(webEditor, win, isDesktop);

    expect(taken).toBe('web');
    expect(win.open).toHaveBeenCalledTimes(1);
    expect(win.open).toHaveBeenCalledWith(webEditor.url, 'eden-vscode');
    // The web fallback must not drive an ssh-remote navigation.
    expect(win.location.href).toBe('');
  });

  it('WEB runtime (isDesktop()===false) → web window even when an sshHost is present', () => {
    const win = makeWindow();
    const isDesktop = vi.fn(() => false);

    const taken = openEditor(DESKTOP_EDITOR, win, isDesktop);

    expect(taken).toBe('web');
    expect(win.open).toHaveBeenCalledWith(DESKTOP_EDITOR.url, 'eden-vscode');
    expect(win.location.href).toBe('');
  });

  it('the web window has its opener nulled (no reverse-tabnabbing handle)', () => {
    const win = makeWindow();
    const opened = win.open('x', 'eden-vscode');
    win.open.mockClear();

    openEditor({ ...DESKTOP_EDITOR, sshHost: '' }, win, () => false);

    // openEditor nulls opener on the returned window.
    expect(opened?.opener).toBeNull();
  });

  it('buildSshRemoteUri is the single home of the URI shape', () => {
    expect(buildSshRemoteUri('eden-editor', '/workspace/p')).toBe(
      'vscode://vscode-remote/ssh-remote+eden-editor/workspace/p',
    );
  });
});
