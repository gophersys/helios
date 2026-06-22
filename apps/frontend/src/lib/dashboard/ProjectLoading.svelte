<script lang="ts" module>
  // ProjectLoading — the REUSABLE, status-driven loading surface a project shows while Eden's
  // create-saga provisions it. It renders a three-step STEPPER (repo → template → supervisor) whose
  // active/done/pending tone is DERIVED entirely from the project's lifecycle `status`, so a reload
  // resumes at exactly the right step (the parent re-reads status on mount + polls). On `failed` it
  // surfaces the human `lastError` + a Retry affordance the host wires.
  //
  // Pure presentation: clean props in (`status`, `name`, `lastError`, callbacks out) — no network, no
  // stores, no $lib/gateway value imports. Token-driven from @eden/theme: every colour/size/space is a
  // var() over the allowed app token vocabulary (--eden-app-*, --space-*, --font-size-*, --font-code,
  // --color-*, --duration-*, --ease-*). The only literals are var() fallbacks + hairline widths.
  // Reduced-motion is honored (the pulse + spinner still away their animation under the media query).
  import type { ProjectStatus } from '$lib/gateway/types';

  /** One stepper step: a stable id (the data-testid suffix), a human label, and the set of statuses
   *  during which it is the ACTIVE step. The order of STEPS is the saga's provisioning walk. */
  interface LoadingStep {
    id: 'repo' | 'template' | 'supervisor';
    label: string;
    detail: string;
    /** The lifecycle statuses at which THIS step is the one in progress. */
    activeAt: ReadonlySet<ProjectStatus>;
  }

  /** The provisioning walk as the user sees it. `creating` (the saga has claimed the project but not
   *  yet begun a named effect) folds into the first step so the stepper is never blank. */
  export const LOADING_STEPS: readonly LoadingStep[] = [
    {
      id: 'repo',
      label: 'Provisioning repository',
      detail: 'Creating the project repository',
      activeAt: new Set<ProjectStatus>(['creating', 'provisioning_repo']),
    },
    {
      id: 'template',
      label: 'Seeding template',
      detail: 'Laying down the starter scaffold',
      activeAt: new Set<ProjectStatus>(['seeding_template']),
    },
    {
      id: 'supervisor',
      label: 'Launching supervisor',
      detail: 'Bringing the build agent online',
      activeAt: new Set<ProjectStatus>(['launching_supervisor']),
    },
  ];
</script>

<script lang="ts">
  import type { Theme } from '@eden/theme';
  import { PROJECT_READY_STATUSES } from '$lib/gateway/types';

  let {
    status,
    name,
    lastError = null,
    retrying = false,
    onRetry,
    onCancel,
    // `theme` is accepted so a host hands the active generated theme uniformly with every other Eden
    // component; the visual tokens resolve from the @eden/theme cascade on the page, so the prop is a
    // forward-compatible seam (referenced to satisfy noUnusedLocals) rather than read per-property.
    theme: _theme,
  }: {
    /** The project's current lifecycle status — drives the whole surface. */
    status: ProjectStatus;
    /** The project name shown in the heading (falls back to a generic phrase when empty). */
    name?: string;
    /** The human fault reason shown on `failed` (the gateway's redaction-safe lastError). */
    lastError?: string | null;
    /** True while a Retry re-POST is in flight (disables the button + shows progress copy). */
    retrying?: boolean;
    /** Invoked when the user clicks Retry on a `failed` project (the host re-POSTs the create). */
    onRetry?: () => void;
    /** Invoked when the user backs out (e.g. to the dashboard). Optional — the link is hidden when absent. */
    onCancel?: () => void;
    theme?: Theme;
  } = $props();

  const failed = $derived(status === 'failed');
  const ready = $derived(PROJECT_READY_STATUSES.has(status));

  // The active step INDEX: the first step whose activeAt set contains the status. A status past the
  // walk (ready/failed) yields -1 here; the per-step tone derivation handles those terminal cases.
  const activeIndex = $derived(LOADING_STEPS.findIndex((step) => step.activeAt.has(status)));

  /** The tone for one step at the current status: a step before the active one is `done`, the active
   *  one is `active`, a later one is `pending`. When the project is READY every step reads `done`;
   *  when it FAILED the active step reads `error` and the rest hold their done/pending tone (so the
   *  stepper shows WHERE it stalled). */
  function toneFor(index: number): 'done' | 'active' | 'pending' | 'error' {
    if (ready) return 'done';
    if (failed) {
      // On failure the saga step the project carries is the one that stalled; everything before it
      // committed (done), everything after never ran (pending). activeIndex is the stalled step.
      if (activeIndex < 0) return index === 0 ? 'error' : 'pending';
      if (index < activeIndex) return 'done';
      if (index === activeIndex) return 'error';
      return 'pending';
    }
    if (activeIndex < 0) return 'pending';
    if (index < activeIndex) return 'done';
    if (index === activeIndex) return 'active';
    return 'pending';
  }

  const heading = $derived(
    failed
      ? `Couldn't build ${name?.trim() || 'your project'}`
      : `Building ${name?.trim() || 'your project'}`,
  );
</script>

<section
  class="loading"
  data-testid="project-loading"
  data-status={status}
  data-phase={failed ? 'failed' : ready ? 'ready' : 'provisioning'}
  aria-busy={!failed && !ready}
>
  <div class="loading__inner">
    <h1 class="loading__title" data-testid="project-loading-title">{heading}</h1>
    <p class="loading__subtitle">
      {#if failed}
        Eden hit a snag while setting things up. You can retry from where it stopped.
      {:else}
        Eden is setting up everything your project needs. This takes a moment.
      {/if}
    </p>

    <ol class="stepper" role="list" data-testid="project-loading-stepper">
      {#each LOADING_STEPS as step, index (step.id)}
        {@const tone = toneFor(index)}
        <li
          class="step"
          data-testid="project-loading-step"
          data-step={step.id}
          data-tone={tone}
          aria-current={tone === 'active' ? 'step' : undefined}
        >
          <span class="step__marker" data-tone={tone} aria-hidden="true">
            {#if tone === 'done'}
              <span class="step__check">✓</span>
            {:else if tone === 'error'}
              <span class="step__cross">✕</span>
            {:else if tone === 'active'}
              <span class="step__spinner"></span>
            {:else}
              <span class="step__dot"></span>
            {/if}
          </span>
          <span class="step__body">
            <span class="step__label">{step.label}</span>
            <span class="step__detail">{step.detail}</span>
          </span>
          <span class="step__status" data-tone={tone}>
            {#if tone === 'done'}Done{:else if tone === 'active'}In progress{:else if tone === 'error'}Failed{:else}Waiting{/if}
          </span>
        </li>
      {/each}
    </ol>

    {#if failed && lastError}
      <p class="loading__error" data-testid="project-loading-error" role="alert">{lastError}</p>
    {/if}

    {#if failed}
      <div class="loading__actions">
        <button
          type="button"
          class="action action--primary"
          data-testid="project-loading-retry"
          disabled={retrying}
          onclick={() => onRetry?.()}
        >
          {retrying ? 'Retrying…' : 'Retry'}
        </button>
        {#if onCancel}
          <button
            type="button"
            class="action action--ghost"
            data-testid="project-loading-cancel"
            onclick={() => onCancel?.()}
          >
            Back to projects
          </button>
        {/if}
      </div>
    {/if}
  </div>
</section>

<style>
  .loading {
    display: flex;
    align-items: center;
    justify-content: center;
    min-block-size: 100%;
    padding: var(--space-6, 24px);
    background: var(--eden-app-bg);
    color: var(--eden-app-fg);
  }
  .loading__inner {
    inline-size: 100%;
    max-inline-size: 34rem;
    display: flex;
    flex-direction: column;
    gap: var(--space-5, 20px);
  }
  .loading__title {
    margin: 0;
    font-size: var(--font-size-title, 23px);
    line-height: 1.2;
    color: var(--eden-app-fg);
    overflow-wrap: anywhere;
  }
  .loading__subtitle {
    margin: 0;
    color: var(--eden-app-muted);
    font-size: var(--font-size-body, 15px);
    line-height: 1.4;
  }

  /* ── the stepper ─────────────────────────────────────────────────────────────── */
  .stepper {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-1, 4px);
  }
  .step {
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: center;
    gap: var(--space-3, 12px);
    padding: var(--space-3, 12px) var(--space-4, 16px);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 8px);
    background: var(--eden-app-panel-bg);
    /* The connector spine between markers: a thin line through the marker column, dimmed by default. */
    position: relative;
    transition:
      border-color var(--duration-2, 160ms) var(--ease-out, ease),
      background var(--duration-2, 160ms) var(--ease-out, ease);
  }
  .step[data-tone='active'] {
    border-color: color-mix(in oklab, var(--eden-app-accent) 55%, var(--eden-app-line));
    background: color-mix(in oklab, var(--eden-app-accent) 6%, var(--eden-app-panel-bg));
  }
  .step[data-tone='error'] {
    border-color: color-mix(in oklab, var(--color-error) 55%, var(--eden-app-line));
    background: color-mix(in oklab, var(--color-error) 6%, var(--eden-app-panel-bg));
  }

  .step__marker {
    inline-size: 28px;
    block-size: 28px;
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    border: 1.5px solid var(--eden-app-line);
    background: var(--eden-app-bg);
    color: var(--eden-app-muted);
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
  }
  /* Done: an OUTLINED success marker — the check + ring are `--color-success` ON the panel surface,
     so the contrast pairing is success-on-surface (a generator-gated role against the surface the
     whole app reads text on), not the non-existent on-success role. A filled success swatch would
     need a `--color-on-success` the generator does not emit; the outline keeps it provably legible. */
  .step__marker[data-tone='done'] {
    border-color: var(--color-success, var(--color-info));
    background: color-mix(
      in oklab,
      var(--color-success, var(--color-info)) 12%,
      var(--eden-app-bg)
    );
    color: var(--color-success, var(--color-info));
  }
  .step__marker[data-tone='active'] {
    border-color: var(--eden-app-accent);
    color: var(--eden-app-accent);
    background: var(--eden-app-bg);
  }
  .step__marker[data-tone='error'] {
    border-color: var(--color-error);
    background: var(--color-error);
    color: var(--color-on-error, var(--color-on-primary, #fff));
  }
  .step__check,
  .step__cross {
    line-height: 1;
  }

  /* The active-step spinner — a token-driven ring that rotates. */
  .step__spinner {
    inline-size: 14px;
    block-size: 14px;
    border-radius: 50%;
    border: 2px solid color-mix(in oklab, var(--eden-app-accent) 28%, transparent);
    border-block-start-color: var(--eden-app-accent);
    animation: project-loading-spin 0.7s linear infinite;
  }
  .step__dot {
    inline-size: 7px;
    block-size: 7px;
    border-radius: 50%;
    background: var(--eden-app-muted);
    opacity: 0.55;
  }

  .step__body {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-inline-size: 0;
  }
  .step__label {
    font-size: var(--font-size-body, 15px);
    font-weight: 600;
    color: var(--eden-app-fg);
  }
  .step[data-tone='pending'] .step__label {
    color: var(--eden-app-muted);
    font-weight: 500;
  }
  .step__detail {
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    overflow-wrap: anywhere;
  }

  .step__status {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--eden-app-muted);
    white-space: nowrap;
  }
  .step__status[data-tone='active'] {
    color: var(--eden-app-accent);
  }
  .step__status[data-tone='done'] {
    color: var(--color-success, var(--color-info));
  }
  .step__status[data-tone='error'] {
    color: var(--color-error);
  }

  /* ── failure state ───────────────────────────────────────────────────────────── */
  .loading__error {
    margin: 0;
    padding: var(--space-3, 12px) var(--space-4, 16px);
    border-radius: var(--eden-app-radius, 8px);
    border: 1px solid color-mix(in oklab, var(--color-error) 45%, var(--eden-app-line));
    background: color-mix(in oklab, var(--color-error) 8%, var(--eden-app-panel-bg));
    color: var(--color-error);
    font-size: var(--font-size-label, 13px);
    line-height: 1.4;
    overflow-wrap: anywhere;
  }
  .loading__actions {
    display: flex;
    gap: var(--space-3, 12px);
    align-items: center;
  }
  .action {
    appearance: none;
    font-family: inherit;
    font-size: var(--font-size-body, 15px);
    font-weight: 600;
    padding: var(--space-2, 8px) var(--space-5, 20px);
    min-block-size: 44px;
    border-radius: var(--eden-app-radius, 8px);
    cursor: pointer;
    transition:
      filter var(--duration-2, 160ms) var(--ease-out, ease),
      border-color var(--duration-2, 160ms) var(--ease-out, ease);
  }
  .action--primary {
    border: 1px solid transparent;
    background: var(--eden-app-accent);
    color: var(--color-on-primary, #fff);
  }
  .action--primary:hover:not(:disabled) {
    filter: brightness(1.05);
  }
  .action--primary:disabled {
    cursor: default;
    opacity: 0.6;
  }
  .action--ghost {
    border: 1px solid var(--eden-app-line);
    background: none;
    color: var(--eden-app-fg);
  }
  .action--ghost:hover {
    border-color: var(--eden-app-accent);
  }
  .action:focus-visible {
    outline: 2px solid var(--eden-app-accent);
    outline-offset: 2px;
  }

  @keyframes project-loading-spin {
    to {
      transform: rotate(360deg);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .step {
      transition: none;
    }
    .step__spinner {
      animation: none;
      border-block-start-color: var(--eden-app-accent);
    }
    .action {
      transition: none;
    }
  }
</style>
