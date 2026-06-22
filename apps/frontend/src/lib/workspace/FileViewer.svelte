<script lang="ts">
  // FileViewer — the workspace center pane's VIEWER: it pretty-renders one selected worktree file by
  // content kind. Markdown renders through Eden's existing markdown pipeline (lexMarkdown → BlockList
  // block components — one home, the same renderer the docs + chat answers use); JSON renders
  // re-indented in a CodeBlock; everything else renders as monospaced plaintext. A path header names
  // the file. Honest states: a loading note while a read is in flight, an error notice on a read
  // fault (never a blank pane), an empty prompt before any selection.
  //
  // REUSABLE + promotion-ready (agent-UI lib principle): clean props in (the content payload + the
  // loading/error flags), no network, no stores. Token-driven from @eden/theme.
  //
  // PROMOTION NOTE: staged in apps/frontend/src/lib/workspace pending the lib pipeline (ADR-0020).
  // The markdown pipeline (lexMarkdown/BlockList) lives in the app today; when this promotes into
  // libs/typescript it takes the rendered markdown as a snippet/slot so the lib carries no app
  // markdown dependency. Do NOT run the lib pipeline now — this is the staging home.
  import type { Theme } from '@eden/theme';
  import { lexMarkdown } from '$lib/markdown/tokens';
  import BlockList from '$lib/components/blocks/BlockList.svelte';
  import CodeBlock from '$lib/components/blocks/CodeBlock.svelte';
  import { prettyJson, type WorktreeFileContent } from './worktreeFiles.svelte';

  let {
    content = null,
    selectedPath = null,
    loading = false,
    error = null,
    theme: _theme,
  }: {
    /** The loaded file content, or null when nothing is selected / it failed to read. */
    content?: WorktreeFileContent | null;
    /** The path that is selected (shown in the header + the error context), even mid-read. */
    selectedPath?: string | null;
    /** True while the read is in flight (shows the loading note). */
    loading?: boolean;
    /** A read fault to surface as an honest notice, or null. */
    error?: string | null;
    theme?: Theme;
  } = $props();

  // Markdown lexing is reactive on the content text — only computed when the content IS markdown, so
  // a large non-markdown file is never needlessly lexed.
  const markdownTokens = $derived(
    content && content.kind === 'markdown' ? lexMarkdown(content.text) : [],
  );
  const prettyJsonText = $derived(
    content && content.kind === 'json' ? prettyJson(content.text) : '',
  );
</script>

<section class="viewer" data-testid="file-viewer" data-kind={content?.kind ?? 'none'}>
  <header class="viewer__head">
    {#if selectedPath}
      <code class="viewer__path" data-testid="viewer-path">{selectedPath}</code>
      {#if content}
        <span class="viewer__kind" data-testid="viewer-kind">{content.kind}</span>
      {/if}
    {:else}
      <span class="viewer__path viewer__path--muted">No file selected</span>
    {/if}
  </header>

  <div class="viewer__body" data-testid="viewer-body">
    {#if error}
      <p class="viewer__note viewer__note--error" data-testid="viewer-error">{error}</p>
    {:else if loading}
      <p class="viewer__note" data-testid="viewer-loading">Loading {selectedPath}…</p>
    {:else if !content}
      <p class="viewer__note" data-testid="viewer-empty">
        Select a generated file to view it — Eden's committed assets appear in the tree as the build
        commits them.
      </p>
    {:else if content.kind === 'markdown'}
      <div class="viewer__markdown" data-testid="viewer-markdown">
        <BlockList tokens={markdownTokens} />
      </div>
    {:else if content.kind === 'json'}
      <div class="viewer__code" data-testid="viewer-json">
        <CodeBlock code={prettyJsonText} lang="json" />
      </div>
    {:else}
      <pre class="viewer__plaintext" data-testid="viewer-text">{content.text}</pre>
    {/if}
  </div>
</section>

<style>
  .viewer {
    display: flex;
    flex-direction: column;
    min-block-size: 0;
    block-size: 100%;
    overflow: hidden;
  }
  .viewer__head {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    padding: var(--space-2, 8px) var(--space-4, 16px);
    border-block-end: 1px solid var(--eden-app-line);
    background: var(--eden-app-panel-bg);
    flex: none;
  }
  .viewer__path {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-fg);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .viewer__path--muted {
    color: var(--eden-app-muted);
    font-family: inherit;
  }
  .viewer__kind {
    font-family: var(--font-code);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--eden-app-muted);
    border: 1px solid var(--eden-app-line);
    border-radius: 3px;
    padding: 0 var(--space-1, 4px);
    flex: none;
  }
  .viewer__body {
    flex: 1;
    min-block-size: 0;
    overflow: auto;
    padding: var(--space-5, 20px) var(--space-6, 24px);
  }
  .viewer__note {
    color: var(--eden-app-muted);
    font-size: var(--font-size-label, 13px);
    max-inline-size: 60ch;
    margin: 0;
  }
  .viewer__note--error {
    color: var(--color-error);
    font-family: var(--font-code);
    overflow-wrap: anywhere;
  }
  .viewer__markdown {
    max-inline-size: 68rem;
  }
  .viewer__code {
    max-inline-size: 80rem;
  }
  .viewer__plaintext {
    margin: 0;
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    line-height: 1.6;
    color: var(--eden-app-fg);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
</style>
