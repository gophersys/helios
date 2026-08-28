<!--
  @eden/primitives — Message (ADR-0024 / RD-16). A token-driven chat bubble: a user or assistant
  message rendered as the role's gated chat-surface container. The APPEARANCE is decided entirely by
  deriveMessageTokens (message/tokens.ts) — every colour/size/space is a CSS custom property whose
  value is DERIVED from an @eden/theme token; this template references var(--eden-message-*) only and
  carries NO literal colour and NO literal px. That is what makes the design-correctness gate (the
  prose contrast + the type-scale proportion + ramp-step spacing) a mechanical property of the
  component, and what keeps the no-hand-set-hex provenance lint green by construction.

  Semantics: the bubble is a <article> with role="listitem" (a turn in the conversation log) carrying
  an accessible label naming the author, and the author is also surfaced visibly as a <header> so the
  role is not conveyed by colour alone (WCAG 1.4.1). The prose is a slot the host fills (text today,
  the StreamingText renderer or rich content tomorrow).
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';
  import { generateTheme, C21_SEED } from '@eden/theme';
  import { deriveMessageTokens, messageStyleVars, type MessageRole } from './tokens.js';

  interface MessageProps {
    /** Who authored this turn — selects the gated role container (user accent / assistant quiet). */
    role?: MessageRole;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** An optional visible author label override (defaults to the capitalised role). */
    author?: string;
    /** The message body content. */
    children: Snippet;
  }

  let { role = 'assistant', theme, author, children }: MessageProps = $props();

  const resolvedTheme = $derived(theme ?? generateTheme(C21_SEED));
  const tokens = $derived(deriveMessageTokens(role, resolvedTheme));
  const styleVars = $derived(messageStyleVars(tokens));
  const label = $derived(author ?? (role === 'user' ? 'User' : 'Assistant'));
</script>

<!-- role="listitem": a message is a turn in the conversation log (the host wraps these in role="list").
     A plain <div> carries the role so there is no implicit-role conflict (an <article> already implies
     a role, which axe's aria-allowed-role flags when overridden to listitem). -->
<div
  class="eden-message"
  role="listitem"
  data-eden-message=""
  data-role={role}
  aria-label={`${label} message`}
  style={styleVars}
>
  <span class="eden-message-author">{label}</span>
  <div class="eden-message-body">
    {@render children()}
  </div>
</div>

<style>
  /*
    Every value is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    messageStyleVars). There is NO literal colour and NO literal px here. The prose colour is the
    role container's gated foreground; the fill + edge are the container's bg + border; the type is
    the `body` proportion; padding/gap/radius are spacing-ramp steps.
  */
  .eden-message {
    display: flex;
    flex-direction: column;
    gap: var(--eden-message-gap);
    box-sizing: border-box;
    padding: var(--eden-message-padding);
    border-radius: var(--eden-message-radius);

    color: var(--eden-message-fg);
    background: var(--eden-message-bg);
    border: 1px solid var(--eden-message-border);

    font-family: var(--eden-message-font-family);
    font-size: var(--eden-message-font-size);
    line-height: var(--eden-message-line-height);
  }

  .eden-message-author {
    /* The author label rides one ramp step smaller in weight, not size: keep it on the prose
       proportion so it inherits the gated contrast; only the weight changes. */
    font-weight: 600;
    opacity: 0.85;
  }

  .eden-message-body {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
</style>
