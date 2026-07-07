<!--
  @eden/primitives — EmptyState (ADR-0024 / doc 17 §4 molecules).

  A product surface for the empty case — NEVER a bare void (doc 17 §1.2). A serif-display HEADLINE
  (the identity-moment voice, P-D4), a sans BODY line, an optional primary ACTION, and an optional
  content SLOT (templates / recents — so the empty state OFFERS something, not just apologizes).
  Renders a `<section>` labelled by its own headline (`aria-labelledby`), so the region is announced.

  The APPEARANCE is decided entirely by `deriveEmptyStateTokens` (empty-state/tokens.ts): every
  colour/size/space is a CSS custom property whose value is DERIVED from an @eden/theme token. This
  template carries NO literal colour and NO literal px — it references `var(--eden-empty-state-*)`
  only. The action is passed as a snippet (a host renders an Eden Button into it), so the EmptyState
  owns the LAYOUT + VOICE and the host owns the action wiring.
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';
  import { defaultButtonTheme } from '../button/tokens.js';
  import { deriveEmptyStateTokens, emptyStateStyleVars } from './tokens.js';

  interface EmptyStateProps {
    /** The headline — the serif-display identity line (e.g. "No projects yet"). */
    headline: string;
    /** The body — one sentence of orientation (the sans interface voice). */
    body?: string;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** A stable id base for the headline↔region link; defaults to a generated unique id. */
    id?: string;
    /** The primary action — a host renders an Eden Button here (optional). */
    action?: Snippet;
    /** The content slot — templates / recents / a preview (optional; the anti-void product surface). */
    content?: Snippet;
  }

  let { headline, body, theme, id, action, content }: EmptyStateProps = $props();

  // A stable, unique id base per instance — the Svelte 5 `$props.id()` rune (SSR-consistent). The
  // headline gets `${base}-headline`, and the region's aria-labelledby points at it.
  const uid = $props.id();
  const baseId = $derived(id ?? `eden-empty-state-${uid}`);
  const headlineId = $derived(`${baseId}-headline`);

  const resolvedTheme = $derived(theme ?? defaultButtonTheme());
  const styleVars = $derived(emptyStateStyleVars(deriveEmptyStateTokens(resolvedTheme)));
</script>

<section
  class="eden-empty-state"
  data-eden-empty-state=""
  aria-labelledby={headlineId}
  style={styleVars}
>
  <h2 class="eden-empty-state-headline" id={headlineId}>{headline}</h2>
  {#if body}
    <p class="eden-empty-state-body">{body}</p>
  {/if}
  {#if action}
    <div class="eden-empty-state-action">{@render action()}</div>
  {/if}
  {#if content}
    <div class="eden-empty-state-content">{@render content()}</div>
  {/if}
</section>

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    emptyStateStyleVars). There is NO literal colour and NO literal px here. The headline is the SERIF
    display voice; the body is the sans interface voice — the two voices governed, never mixed (P-D4).
  */
  .eden-empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--eden-empty-state-gap);

    box-sizing: border-box;
    padding: var(--eden-empty-state-padding);
    /* the reading measure caps the sprawl — a void is never generous, just empty (doc 17 §1.2/§5) */
    max-inline-size: var(--eden-empty-state-max-width);
    margin-inline: auto;
    text-align: center;

    color: var(--eden-empty-state-body);
    background: var(--eden-empty-state-surface);
  }

  .eden-empty-state-headline {
    margin: 0;
    color: var(--eden-empty-state-headline);
    font-family: var(--eden-empty-state-headline-font-family);
    font-size: var(--eden-empty-state-headline-font-size);
    line-height: var(--eden-empty-state-headline-line-height);
    font-weight: 600;
  }

  .eden-empty-state-body {
    margin: 0;
    color: var(--eden-empty-state-body);
    font-family: var(--eden-empty-state-body-font-family);
    font-size: var(--eden-empty-state-body-font-size);
    line-height: var(--eden-empty-state-body-line-height);
  }

  .eden-empty-state-content {
    /* the slot spans the reading measure so templates/recents fill the space a void would waste */
    inline-size: 100%;
  }
</style>
