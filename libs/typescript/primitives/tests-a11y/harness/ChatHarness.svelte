<!--
  The chat-group a11y-evidence harness view (ADR-0024 / RD-16). Mounts every chat surface in a
  focusable sequence (sibling anchors before/after the interactive ones) so a Tab-order assertion can
  prove each interactive surface participates in the natural tab sequence. The surfaces carry
  data-testid so the spec can target them across the Chromium AND WebKit engines.

  These are the agent-event taxonomy as components: a Message log (user + assistant bubbles), a live
  StreamingText, a ToolCall card (every status), the PermissionRequest human prompt (with its three
  Allow/Deny actions), a UsageMeter (every tier), and a collapsible ThinkingBlock. The surrounding
  Eden token context is injected at the document level by theme.ts (so axe reads the real reading
  background), and each component derives its OWN --eden-* vars from the same theme.
-->
<script lang="ts">
  import {
    Message,
    StreamingText,
    ToolCall,
    PermissionRequest,
    UsageMeter,
    ThinkingBlock,
  } from '@eden/primitives';
</script>

<div class="chat-harness-stack">
  <!-- A page-level heading so the evidence page satisfies page-has-heading-one; visually hidden so it
       does not alter the demo layout (the components under test are what the spec audits). -->
  <h1 class="chat-harness-visually-hidden">Chat surfaces a11y evidence</h1>

  <a href="#before" data-testid="before">before</a>

  <!-- The conversation log: a list of message turns (listitem roles inside a list). -->
  <div role="list" aria-label="Conversation" class="chat-harness-log">
    <Message role="user">What files changed in the last commit?</Message>
    <Message role="assistant">Let me check the repository for you.</Message>
  </div>

  <StreamingText text="Reading the git log" streaming={true} />

  <ToolCall tool="read_file" args={'{"path":"CHANGELOG.md"}'} status="running" />
  <ToolCall tool="grep" args={'pattern=changed'} status="success" />
  <ToolCall tool="write_file" args={'{"path":"/etc/hosts"}'} status="error" />

  <PermissionRequest
    tool="write_file"
    args={'{"path":"src/app.ts"}'}
    reason="to apply the edit you approved"
    onDecision={() => undefined}
  />

  <UsageMeter used={45} budget={100} cost="$0.12" />
  <UsageMeter used={88} budget={100} cost="$0.41" />
  <UsageMeter used={100} budget={100} cost="$0.55" />

  <ThinkingBlock summary="Thinking" open={false}>
    The user asked which files changed; I should inspect the latest commit and summarise the diff.
  </ThinkingBlock>

  <a href="#after" data-testid="after">after</a>
</div>

<style>
  .chat-harness-stack {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: var(--space-4, 16px);
    padding: var(--space-8, 32px);
    max-inline-size: 40rem;
  }

  .chat-harness-log {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
  }

  .chat-harness-visually-hidden {
    position: absolute;
    inline-size: 1px;
    block-size: 1px;
    margin: -1px;
    padding: 0;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    border: 0;
  }
</style>
