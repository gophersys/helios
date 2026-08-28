<!--
  @eden/primitives — PermissionRequest (ADR-0024 / RD-16). The human-in-the-loop prompt (the 5b
  surface): the agent asks to run a tool, showing the tool, its args, and a reason, with three
  actions — Allow once, Allow for session, Deny. The APPEARANCE is decided entirely by
  derivePermissionRequestTokens (permission-request/tokens.ts) — every colour/size/space is a CSS
  custom property whose value is DERIVED from an @eden/theme token; this template references
  var(--eden-permission-request-*) only and carries NO literal colour and NO literal px.

  The three actions DELEGATE to the Button primitive (one concept, one home): Allow-once = primary,
  Allow-for-session = secondary, Deny = danger. So they inherit the Button's gated contrast, its
  bits-ui behaviour, AND its 44px AAA hit target — this card never re-styles an action button.

  Semantics: the card is role="group" with aria-label naming the decision, the heading is a real
  <h3> (the warning accent is paired with the word "Permission required" — colour is never the only
  signal, WCAG 1.4.1), the args are a <pre><code>, and the action row is grouped so a screen reader
  presents the three choices together.
-->
<script lang="ts">
  import type { Theme } from '@eden/theme';
  import { generateTheme, C21_SEED } from '@eden/theme';
  import { Button } from '../button/index.js';
  import { derivePermissionRequestTokens, permissionRequestStyleVars } from './tokens.js';

  /** The decision the human can return — the three permission outcomes. */
  type PermissionDecision = 'allow-once' | 'allow-session' | 'deny';

  interface PermissionRequestProps {
    /** The tool the agent is asking to run (e.g. `write_file`). */
    tool: string;
    /** The serialised arguments to render in the code block. */
    args?: string;
    /** The agent's reason for the request (prose). */
    reason?: string;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** Invoked with the chosen decision when the human acts. */
    onDecision?: (decision: PermissionDecision) => void;
  }

  let { tool, args = '', reason = '', theme, onDecision }: PermissionRequestProps = $props();

  const resolvedTheme = $derived(theme ?? generateTheme(C21_SEED));
  const tokens = $derived(derivePermissionRequestTokens(resolvedTheme));
  const styleVars = $derived(permissionRequestStyleVars(tokens));

  function decide(decision: PermissionDecision): void {
    onDecision?.(decision);
  }
</script>

<!-- role="group" on a <div> (not a <section>): the explicit group role names the decision without
     adding a region landmark, and avoids the implicit-vs-explicit role conflict a <section role> trips. -->
<div
  class="eden-permission-request"
  data-eden-permission-request=""
  role="group"
  aria-label={`Permission required to run ${tool}`}
  style={styleVars}
>
  <h3 class="eden-permission-request-heading">Permission required</h3>
  <p class="eden-permission-request-tool">
    The agent wants to run <strong>{tool}</strong>.
  </p>
  {#if reason}
    <p class="eden-permission-request-reason">{reason}</p>
  {/if}
  {#if args}
    <pre class="eden-permission-request-args"><code>{args}</code></pre>
  {/if}
  <div class="eden-permission-request-actions" role="group" aria-label="Permission decision">
    <Button
      variant="primary"
      theme={resolvedTheme}
      onclick={() => {
        decide('allow-once');
      }}
    >
      Allow once
    </Button>
    <Button
      variant="secondary"
      theme={resolvedTheme}
      onclick={() => {
        decide('allow-session');
      }}
    >
      Allow for session
    </Button>
    <Button
      variant="danger"
      theme={resolvedTheme}
      onclick={() => {
        decide('deny');
      }}
    >
      Deny
    </Button>
  </div>
</div>

<style>
  .eden-permission-request {
    display: flex;
    flex-direction: column;
    gap: var(--eden-permission-request-gap);
    box-sizing: border-box;
    padding: var(--eden-permission-request-padding);
    border-radius: var(--eden-permission-request-radius);
    color: var(--eden-permission-request-fg);
    background: var(--eden-permission-request-bg);
    /* the ask is raised by a clear outline edge, not a competing tonal fill. */
    border: 1px solid var(--eden-permission-request-border);
  }

  .eden-permission-request-heading {
    margin: 0;
    color: var(--eden-permission-request-heading);
    font-size: var(--eden-permission-request-heading-size);
    line-height: var(--eden-permission-request-heading-line-height);
    font-family: var(--eden-permission-request-heading-family);
    font-weight: 700;
  }

  .eden-permission-request-tool,
  .eden-permission-request-reason {
    margin: 0;
    font-size: var(--eden-permission-request-body-size);
    line-height: var(--eden-permission-request-body-line-height);
    font-family: var(--eden-permission-request-body-family);
  }

  .eden-permission-request-args {
    margin: 0;
    font-size: var(--eden-permission-request-code-size);
    font-family: var(--eden-permission-request-code-family);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .eden-permission-request-args code {
    font-family: inherit;
  }

  .eden-permission-request-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--eden-permission-request-action-gap);
    /* every action is a Button — it carries the 44px floor itself; the row reserves the same min. */
    min-block-size: var(--eden-permission-request-hit-target);
  }
</style>
