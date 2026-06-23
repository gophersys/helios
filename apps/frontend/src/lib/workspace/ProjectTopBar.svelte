<script lang="ts">
  // ProjectTopBar — the workspace TOP BAR: the project's git identity (branch · last commit · the
  // repo link from project.repoUrl) on the left, and the project settings (lifecycle status · the
  // stacks · the bound supervisor agent) on the right. The XCode-like title bar of the project
  // workspace.
  //
  // REUSABLE + promotion-ready (agent-UI lib principle): pure presentation — clean props in
  // (the projectView fields + the optional last-commit summary), callbacks out (onBack), no network,
  // no $lib/gateway VALUE imports (only the ProjectView TYPE, a redaction-safe read model). Every
  // colour/size/space is a var() over the allowed app token vocabulary (--eden-app-*, --space-*,
  // --font-size-*, --font-code, --color-*), so it themes from the @eden/theme cascade on the page.
  //
  // PROMOTION NOTE: this lives in apps/frontend/src/lib/workspace pending the lib pipeline
  // (ADR-0020). When promoted into libs/typescript it takes the ProjectView shape as a generic
  // `project` prop type so it does not depend on the app's gateway types module. Do NOT run the lib
  // pipeline now — this is the staging home.
  import type { Theme } from '@eden/theme';
  import type { ProjectView } from '$lib/gateway/types';

  /** A git commit summary the top bar shows ("last commit"). Optional — the host supplies it from a
   *  commit feed when present; absent, the bar shows the branch + repo without a commit line (honest:
   *  no fabricated hash). No field is a credential. */
  export interface CommitSummary {
    /** The short commit hash (e.g. `a1b2c3d`). */
    shortHash: string;
    /** The commit subject (first line of the message). */
    subject: string;
    /** A human relative time ("2m ago") the host pre-formats, or omitted. */
    relativeTime?: string;
  }

  let {
    project,
    commit = null,
    onBack,
    onOpenEditor,
    editorBusy = false,
    theme: _theme,
  }: {
    /** The project's redaction-safe read model (repoUrl/defaultBranch/status/stacks/supervisorAgentId). */
    project: ProjectView;
    /** The last commit on the branch, when the host has it; null shows branch + repo only. */
    commit?: CommitSummary | null;
    /** Invoked when the user clicks the brand/back affordance (e.g. to the projects dashboard). */
    onBack?: () => void;
    /** Invoked to open the project in a read-only VS Code. Absent == the editor affordance is hidden
     *  (kept network-free: the host resolves the editor URL + opens the tab / vscode:// URI). */
    onOpenEditor?: () => void;
    /** True while an editor open is in flight — disables the button so a double-click can't double-open. */
    editorBusy?: boolean;
    theme?: Theme;
  } = $props();

  /** The branch label — the project's default branch, or a neutral placeholder when the saga has not
   *  recorded one yet (a pre-provision draft). */
  const branch = $derived(project.defaultBranch || 'main');

  /** Whether a public clone URL exists to link to (repoUrl is the public clone URL, never a secret). */
  const hasRepo = $derived(Boolean(project.repoUrl));

  /** The status chip tone — green for a healthy terminal (building), warn for failed, info for the
   *  provisioning walk, muted for a draft. DERIVED from the closed status set, never hand-guessed. */
  const statusTone = $derived(statusToneFor(project.status));

  function statusToneFor(status: string): 'ok' | 'warn' | 'info' | 'muted' {
    if (status === 'building') return 'ok';
    if (status === 'failed') return 'warn';
    if (status === 'draft') return 'muted';
    return 'info';
  }
</script>

<header class="ptbar" data-testid="project-top-bar">
  <!-- left: brand + project name -->
  <div class="ptbar__group ptbar__group--lead">
    <button
      class="ptbar__brand"
      data-testid="project-back"
      title="Back to projects"
      disabled={!onBack}
      onclick={onBack}
    >
      <span class="ptbar__mark" aria-hidden="true">◆</span>
      <span class="ptbar__brand-name">Eden</span>
    </button>
    <span class="ptbar__sep" aria-hidden="true">/</span>
    <span class="ptbar__project" data-testid="project-name" title={project.name}>{project.name}</span>
  </div>

  <!-- center: git info — branch · last commit · repo -->
  <div class="ptbar__group ptbar__group--git" data-testid="project-git">
    <span class="ptbar__branch" data-testid="project-branch" title="branch">
      <span class="ptbar__glyph" aria-hidden="true">⎇</span>
      <code>{branch}</code>
    </span>
    {#if commit}
      <span class="ptbar__sep" aria-hidden="true">·</span>
      <span class="ptbar__commit" data-testid="project-commit" title={commit.subject}>
        <code class="ptbar__hash">{commit.shortHash}</code>
        <span class="ptbar__commit-subject">{commit.subject}</span>
        {#if commit.relativeTime}
          <span class="ptbar__commit-time">{commit.relativeTime}</span>
        {/if}
      </span>
    {/if}
    {#if hasRepo}
      <span class="ptbar__sep" aria-hidden="true">·</span>
      <a
        class="ptbar__repo"
        data-testid="project-repo-link"
        href={project.repoUrl}
        target="_blank"
        rel="noreferrer noopener"
        title={project.repoUrl}
      >
        <span class="ptbar__glyph" aria-hidden="true">↗</span>
        repository
      </a>
    {/if}
    {#if onOpenEditor}
      <span class="ptbar__sep" aria-hidden="true">·</span>
      <button
        class="ptbar__repo ptbar__editor"
        data-testid="project-open-editor"
        type="button"
        disabled={editorBusy}
        onclick={onOpenEditor}
        title="Open this project in a read-only VS Code"
      >
        <span class="ptbar__glyph" aria-hidden="true">⧉</span>
        {editorBusy ? 'opening…' : 'open in VS Code'}
      </button>
    {/if}
  </div>

  <!-- right: project settings — status · stacks · supervisor -->
  <div class="ptbar__group ptbar__group--settings" data-testid="project-settings">
    <span class="ptbar__chip ptbar__chip--{statusTone}" data-testid="project-status">
      {project.status}
    </span>
    {#each project.stacks.slice(0, 4) as stack (stack)}
      <span class="ptbar__chip ptbar__chip--muted" data-testid="project-stack">{stack}</span>
    {/each}
    {#if project.supervisorAgentId}
      <span
        class="ptbar__supervisor"
        data-testid="project-supervisor"
        title="supervisor agent {project.supervisorAgentId}"
      >
        <span class="ptbar__glyph" aria-hidden="true">⌖</span>
        <code class="ptbar__supervisor-id">{project.supervisorAgentId}</code>
      </span>
    {/if}
  </div>
</header>

<style>
  .ptbar {
    display: flex;
    align-items: center;
    gap: var(--space-4, 16px);
    padding: var(--space-2, 8px) var(--space-4, 16px);
    background: var(--eden-app-panel-bg);
    border-block-end: 1px solid var(--eden-app-line);
    min-block-size: calc(var(--space-8, 32px) + var(--space-1, 4px));
  }
  .ptbar__group {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
    min-inline-size: 0;
  }
  .ptbar__group--git {
    flex: 1;
    overflow: hidden;
    color: var(--eden-app-muted);
    font-size: var(--font-size-caption, 12px);
  }
  .ptbar__group--settings {
    margin-inline-start: auto;
    flex: none;
    flex-wrap: wrap;
    justify-content: flex-end;
  }
  .ptbar__brand {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
    background: none;
    border: 1px solid transparent;
    border-radius: var(--eden-app-radius, 4px);
    padding: var(--space-1, 4px) var(--space-2, 8px);
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  .ptbar__brand:hover:not(:disabled) {
    border-color: var(--eden-app-line);
    background: var(--eden-app-rail-bg);
  }
  .ptbar__brand:disabled {
    cursor: default;
  }
  .ptbar__brand:focus-visible {
    outline: 2px solid var(--eden-app-accent);
    outline-offset: 2px;
  }
  .ptbar__mark {
    color: var(--eden-app-accent);
    font-size: var(--font-size-body-large, 16px);
  }
  .ptbar__brand-name {
    font-weight: 700;
    letter-spacing: 0.02em;
    color: var(--eden-app-fg);
  }
  .ptbar__project {
    font-weight: 650;
    color: var(--eden-app-fg);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-inline-size: 28ch;
  }
  .ptbar__sep {
    opacity: 0.4;
    flex: none;
  }
  .ptbar__glyph {
    color: var(--eden-app-accent);
    flex: none;
  }
  .ptbar__branch,
  .ptbar__commit,
  .ptbar__repo,
  .ptbar__supervisor {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1, 4px);
    min-inline-size: 0;
  }
  .ptbar__branch code,
  .ptbar__hash,
  .ptbar__supervisor-id {
    font-family: var(--font-code);
    color: var(--eden-app-fg);
  }
  .ptbar__commit {
    overflow: hidden;
  }
  .ptbar__commit-subject {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-inline-size: 40ch;
    color: var(--eden-app-muted);
  }
  .ptbar__commit-time {
    flex: none;
    opacity: 0.7;
  }
  .ptbar__repo {
    color: var(--eden-app-accent);
    text-decoration: none;
    font-weight: 600;
    flex: none;
  }
  .ptbar__repo:hover {
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .ptbar__repo:focus-visible {
    outline: 2px solid var(--eden-app-accent);
    outline-offset: 2px;
    border-radius: 2px;
  }
  /* the editor action reuses the repo-link look but is a real <button> (it triggers a host callback,
     not a navigation) — reset the button chrome so it reads as an inline accent action. */
  .ptbar__editor {
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
  }
  .ptbar__editor:disabled {
    cursor: progress;
    opacity: 0.65;
  }
  .ptbar__supervisor-id {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-inline-size: 20ch;
  }
  /* chips — app-chrome micro-labels, token-driven off the generated roles (contrast-correct pairs) */
  .ptbar__chip {
    display: inline-flex;
    align-items: center;
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    border-radius: 999px;
    padding: 0.16rem 0.55rem;
    line-height: 1.4;
    white-space: nowrap;
  }
  .ptbar__chip--ok {
    background: var(--color-primary);
    color: var(--color-on-primary);
  }
  .ptbar__chip--info {
    background: color-mix(in oklab, var(--color-info) 16%, var(--color-surface));
    color: var(--color-info);
  }
  .ptbar__chip--warn {
    background: color-mix(in oklab, var(--color-warning) 22%, var(--color-surface));
    color: var(--color-warning);
  }
  .ptbar__chip--muted {
    background: color-mix(in oklab, var(--color-on-surface) 8%, var(--color-surface));
    color: var(--eden-app-muted);
  }
  @media (max-width: 900px) {
    .ptbar__commit-subject {
      display: none;
    }
  }
  @media (max-width: 720px) {
    .ptbar__group--git {
      display: none;
    }
  }
</style>
