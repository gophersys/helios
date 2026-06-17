<script lang="ts">
  // UserProfileCard — the user-identity card pinned at the BOTTOM of the dashboard. It reads like a
  // pressable button (a clickable surface with a hover state) carrying the signed-in user's avatar
  // (their initials, token-tinted), name, an optional muted email line, and — on the trailing edge —
  // a dedicated SETTINGS affordance (⚙) whose own click is isolated from the card's.
  //
  // Reusable + self-contained: clean props in, callbacks out. No stores, no network, no $lib/gateway
  // VALUE imports — only the `Theme` type seam every chat/dashboard component accepts. Fully
  // token-driven from @eden/theme: every color/size/space is a var() over the allowed app token
  // vocabulary (--eden-app-*, --space-*, --font-size-*, --color-*). The only literals are token
  // fallbacks + hairline border widths. Reduced-motion is honored.
  import type { Theme } from '@eden/theme';

  let {
    name = 'You',
    email,
    onSettings,
    // `theme` is accepted so a host can hand the active generated theme to this card uniformly with
    // every other chat/dashboard component; the visual tokens resolve from the @eden/theme cascade on
    // the page, so the prop is a forward-compatible seam (referenced to satisfy noUnusedLocals).
    theme: _theme,
  }: {
    name?: string;
    email?: string;
    onSettings?: () => void;
    theme?: Theme;
  } = $props();

  // The avatar shows up to two initials derived from `name`: the first letter of the first and last
  // whitespace-separated words (so "Ada Lovelace" → "AL", "Mateo" → "M"). Falls back to "?" when the
  // name carries no letters at all, so the avatar is never an empty circle.
  const initials = $derived(initialsOf(name));

  /** initialsOf extracts up to two uppercased leading letters from a display name. */
  function initialsOf(value: string): string {
    const words = value.trim().split(/\s+/).filter(Boolean);
    if (words.length === 0) return '?';
    const first = words[0]?.[0] ?? '';
    const last = words.length > 1 ? (words[words.length - 1]?.[0] ?? '') : '';
    const result = (first + last).toUpperCase();
    return result || '?';
  }

  /** onCardKeydown makes the role=button card keyboard-activatable (Enter / Space → open settings),
   *  matching the pointer affordance so the card is a real, accessible button — not a div that merely
   *  looks clickable. */
  function onCardKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onSettings?.();
    }
  }
</script>

<!-- The whole card IS the (single) interactive control: a role=button surface that opens settings on
     pointer or keyboard. The trailing ⚙ is a decorative cue, not a nested button — a click on it
     bubbles to the card, so there is exactly one accessible control and no nested-interactive a11y trap. -->
<div
  class="card"
  data-testid="user-profile-card"
  role="button"
  tabindex="0"
  aria-label="Open settings"
  title="Settings"
  onclick={() => onSettings?.()}
  onkeydown={onCardKeydown}
>
  <span class="card__avatar" data-testid="user-avatar" aria-hidden="true">{initials}</span>

  <span class="card__identity">
    <span class="card__name" data-testid="user-name">{name}</span>
    {#if email}
      <span class="card__email" data-testid="user-email">{email}</span>
    {/if}
  </span>

  <span class="card__settings" data-testid="user-settings-open" aria-hidden="true">⚙</span>
</div>

<style>
  /* The card IS one pressable button: a horizontal surface that opens settings on click/keyboard,
     with a hover lift and a real focus ring. The trailing ⚙ is a decorative cue. */
  .card {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    inline-size: 100%;
    padding: var(--space-2, 8px) var(--space-3, 12px);
    background: var(--eden-app-panel-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 8px);
    color: var(--eden-app-fg);
    cursor: pointer;
    text-align: start;
    transition:
      background-color 120ms ease,
      border-color 120ms ease;
  }
  .card:hover {
    background: var(--eden-app-rail-bg);
    border-color: var(--eden-app-accent);
  }
  .card:focus-visible {
    outline: 2px solid var(--eden-app-accent);
    outline-offset: 2px;
    border-color: var(--eden-app-accent);
  }

  /* round, token-tinted initials avatar */
  .card__avatar {
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: var(--space-8, 32px);
    block-size: var(--space-8, 32px);
    border-radius: 50%;
    background: color-mix(in oklab, var(--eden-app-accent) 22%, transparent);
    color: var(--eden-app-accent);
    border: 1px solid color-mix(in oklab, var(--eden-app-accent) 40%, transparent);
    font-size: var(--font-size-caption, 12px);
    font-weight: 700;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    user-select: none;
  }

  /* name + optional muted email, stacked, ellipsised so a long value never overflows the card */
  .card__identity {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-inline-size: 0;
    flex: 1 1 auto;
  }
  .card__name {
    font-size: var(--font-size-label, 14px);
    font-weight: 600;
    color: var(--eden-app-fg);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .card__email {
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* trailing settings cue — a decorative ⚙ glyph (the whole card is the control); it tints with the
     card's hover so the affordance reads as one surface. */
  .card__settings {
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: var(--space-7, 28px);
    block-size: var(--space-7, 28px);
    border-radius: var(--eden-app-radius, 6px);
    color: var(--eden-app-muted);
    font-size: var(--font-size-body-large, 15px);
    transition: color 120ms ease;
  }
  .card:hover .card__settings {
    color: var(--eden-app-fg);
  }

  @media (prefers-reduced-motion: reduce) {
    .card,
    .card__settings {
      transition: none;
    }
  }
</style>
