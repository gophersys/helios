<script lang="ts">
  // WorkspaceShell — the XCode-like 3-pane workspace SHELL: a full-height top bar over a two-column
  // body (LEFT pane + CENTER pane). It is a pure LAYOUT primitive: it owns the grid, the collapsible
  // left column, and the column hairlines — nothing about WHAT each pane renders. The project
  // workspace composes the conversation into the left pane and the generated-assets tree+viewer into
  // the center pane; any other agent surface can reuse the same shell.
  //
  // REUSABLE + promotion-ready (agent-UI lib principle): content arrives as snippets (topbar / left /
  // center), so the shell carries zero domain coupling. The left pane folds to a 0-width column via
  // `leftOpen` (the top bar toggles it) so the center can take the full width. Token-driven from
  // @eden/theme.
  //
  // PROMOTION NOTE: staged in apps/frontend/src/lib/workspace pending the lib pipeline (ADR-0020) —
  // it has no app imports at all, so it promotes into libs/typescript unchanged.
  import type { Theme } from '@eden/theme';
  import type { Snippet } from 'svelte';

  let {
    leftOpen = true,
    leftLabel = 'Left pane',
    topbar,
    left,
    center,
    theme: _theme,
  }: {
    /** Whether the left pane is shown; when false it folds to a 0-width column (center takes over). */
    leftOpen?: boolean;
    /** The accessible label for the left region. */
    leftLabel?: string;
    /** The top-bar content (e.g. ProjectTopBar). */
    topbar: Snippet;
    /** The left-pane content (e.g. the conversation with the supervisor). */
    left: Snippet;
    /** The center-pane content (e.g. the worktree tree + the file viewer). */
    center: Snippet;
    theme?: Theme;
  } = $props();
</script>

<div class="shell" data-testid="workspace-shell">
  <div class="shell__topbar">
    {@render topbar()}
  </div>
  <div
    class="shell__body"
    style="grid-template-columns: {leftOpen ? 'clamp(320px, 32vw, 460px)' : '0'} minmax(0, 1fr);"
  >
    {#if leftOpen}
      <aside class="shell__left" aria-label={leftLabel} data-testid="workspace-left">
        {@render left()}
      </aside>
    {:else}
      <div class="shell__collapsed" aria-hidden="true"></div>
    {/if}
    <main class="shell__center" data-testid="workspace-center">
      {@render center()}
    </main>
  </div>
</div>

<style>
  .shell {
    display: flex;
    flex-direction: column;
    /* Fill the host's content area (100% of the parent), NOT the raw viewport — so when the
       workspace renders inside the app shell's scrollable main it occupies that region exactly,
       with no double-viewport overflow. The host bounds the height; the panes flex + scroll. */
    block-size: 100%;
    min-block-size: 0;
    overflow: hidden;
    background: var(--eden-app-bg);
    color: var(--eden-app-fg);
  }
  .shell__topbar {
    flex: none;
  }
  .shell__body {
    display: grid;
    flex: 1;
    min-block-size: 0;
    overflow: hidden;
  }
  .shell__left {
    display: flex;
    flex-direction: column;
    min-inline-size: 0;
    min-block-size: 0;
    overflow: hidden;
    border-inline-end: 1px solid var(--eden-app-line);
    background: var(--eden-app-panel-bg);
  }
  .shell__collapsed {
    inline-size: 0;
    overflow: hidden;
  }
  .shell__center {
    display: flex;
    flex-direction: column;
    min-inline-size: 0;
    min-block-size: 0;
    overflow: hidden;
  }
</style>
