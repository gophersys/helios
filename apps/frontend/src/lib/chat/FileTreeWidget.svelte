<script lang="ts">
  // The FILES widget — the REAL files the agent produced on disk, fetched from the gateway's
  // GET /sessions/{id}/workspace endpoint. This is the GROUND-TRUTH complement to WorkspaceWidget:
  // that one derives artifacts from the tool-call stream (what the agent SAID it touched); this one
  // lists what is ACTUALLY on disk under the workspace root (relative paths, size, mtime). It
  // re-fetches LIVE as the agent works — keyed on the timeline length — so new files appear as they
  // are written, with a light debounce so a burst of events coalesces into one request. Fully
  // token-driven from @eden/theme; honest empty + error states; no dead controls.
  import type { Theme } from '@eden/theme';
  import type { ChatSession } from '$lib/gateway/session.svelte';
  import { resolveGatewayUrl } from '$lib/gateway/configuration';
  import PanelWidget from './PanelWidget.svelte';

  let { session, theme }: { session: ChatSession; theme?: Theme } = $props();

  /** One real file under the workspace root (the gateway wire DTO: relative path + size + mtime). */
  interface WorkspaceFile {
    path: string;
    size: number;
    modifiedUnix: number;
  }

  let files = $state<WorkspaceFile[]>([]);
  let error = $state<string | null>(null);
  let loaded = $state(false);

  // The timeline length is the live "the agent did something" signal: a new tool call / message
  // grows it, so re-fetching the on-disk listing on each change surfaces freshly-written files
  // without a backend push channel. Debounced so a burst of streamed events is one request.
  const activityCount = $derived(session.entries.length);

  $effect(() => {
    // Touch the reactive signals this effect depends on so it re-runs as the session works.
    void activityCount;
    const id = session.id;

    let cancelled = false;
    const handle = setTimeout(() => {
      void refresh(id, () => cancelled);
    }, REFETCH_DEBOUNCE_MS);

    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  });

  /** REFETCH_DEBOUNCE_MS coalesces a burst of streamed events into a single workspace fetch. */
  const REFETCH_DEBOUNCE_MS = 250;

  async function refresh(sessionId: string, isCancelled: () => boolean): Promise<void> {
    try {
      const response = await fetch(`${resolveGatewayUrl()}/sessions/${sessionId}/workspace`);
      if (isCancelled()) return;
      if (!response.ok) {
        error = `Could not load files (${response.status})`;
        loaded = true;
        return;
      }
      const body = (await response.json()) as { files?: WorkspaceFile[] };
      if (isCancelled()) return;
      files = body.files ?? [];
      error = null;
      loaded = true;
    } catch {
      if (isCancelled()) return;
      error = 'Could not reach the gateway';
      loaded = true;
    }
  }

  function fileName(path: string): string {
    const parts = path.split('/');
    return parts[parts.length - 1] || path;
  }
  function dirName(path: string): string {
    const i = path.lastIndexOf('/');
    return i > 0 ? path.slice(0, i) : '';
  }
  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
</script>

<div class="filetree" data-testid="filetree-widget" data-count={files.length} aria-label="files on disk">
  <PanelWidget title="Files" count={files.length} defaultOpen={false} {theme}>
    {#snippet children()}
      {#if error}
        <p class="filetree__note filetree__note--error" data-testid="filetree-error">{error}</p>
      {:else if !loaded}
        <p class="filetree__note" data-testid="filetree-loading">Loading files…</p>
      {:else if files.length === 0}
        <p class="filetree__note" data-testid="filetree-empty">
          No files on disk yet — they appear as the agent writes.
        </p>
      {:else}
        <ul class="filetree__list" role="list">
          {#each files as file (file.path)}
            <li class="file" data-testid="filetree-file" data-path={file.path}>
              <span class="file__glyph" aria-hidden="true">▪</span>
              <span class="file__name">
                {fileName(file.path)}
                {#if dirName(file.path)}<span class="file__dir">{dirName(file.path)}</span>{/if}
              </span>
              <span class="file__size">{formatSize(file.size)}</span>
            </li>
          {/each}
        </ul>
      {/if}
    {/snippet}
  </PanelWidget>
</div>

<style>
  .filetree {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
    min-block-size: 0;
  }
  .filetree__note {
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    margin: 0;
  }
  .filetree__note--error {
    color: var(--color-error);
  }
  .filetree__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-1, 4px);
    overflow-y: auto;
  }
  .file {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    padding: var(--space-1, 4px) var(--space-2, 8px);
    border-radius: var(--eden-app-radius, 4px);
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    animation: file-in 240ms ease-out;
  }
  .file:hover {
    background: var(--eden-app-panel-bg);
  }
  .file__glyph {
    color: var(--eden-app-accent);
    flex: none;
  }
  .file__name {
    color: var(--eden-app-fg);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-inline-size: 0;
  }
  .file__dir {
    color: var(--eden-app-muted);
    margin-inline-start: var(--space-2, 8px);
    opacity: 0.7;
  }
  .file__size {
    color: var(--eden-app-muted);
    flex: none;
    font-variant-numeric: tabular-nums;
  }
  @keyframes file-in {
    from {
      opacity: 0;
      transform: translateY(-3px);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .file {
      animation: none;
    }
  }
</style>
