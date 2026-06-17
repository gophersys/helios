<!--
  The hotspot-map a11y-evidence harness view (ADR-0024 / codeinsight contract §6 — Eden analyzing
  Eden). Mounts the HotspotMap over a real Eden-libs Report slice, with sibling focusable anchors
  before/after so a Tab-order assertion can prove the scatter points participate in the natural tab
  sequence. The surrounding Eden token context is injected at the document level by theme.ts (so axe
  reads the real reading background), and the component derives its OWN --eden-hotspot-map-* vars from
  the same theme.
-->
<script lang="ts">
  import { HotspotMap, type Entity } from '@eden/visualization';

  // A small Eden-libs Report slice (the self-feeding target, contract §6). The top hotspot cases.go
  // mirrors the contract worked example (churnRelative ≈ 1.07 / cyclomatic 216 / score 1.0).
  const entities: Entity[] = [
    {
      path: 'libs/go/agentsession/cases.go',
      kind: 'file',
      language: 'go',
      lines: 1840,
      cyclomatic: 216,
      churnAbsolute: 1969,
      churnRelative: 1.07,
      changeFrequency: 58,
      hotspotScore: 1.0,
      ageDays: 3,
    },
    {
      path: 'libs/go/orchestrator/configuration.go',
      kind: 'file',
      language: 'go',
      lines: 320,
      cyclomatic: 28,
      churnAbsolute: 240,
      churnRelative: 0.75,
      changeFrequency: 22,
      hotspotScore: 0.42,
      ageDays: 11,
    },
    {
      path: 'libs/go/observability/clock.go',
      kind: 'file',
      language: 'go',
      lines: 90,
      cyclomatic: 8,
      churnAbsolute: 9,
      churnRelative: 0.1,
      changeFrequency: 2,
      hotspotScore: 0.05,
      ageDays: 120,
    },
  ];
</script>

<div class="hotspot-harness-stack">
  <!-- A page-level heading so the evidence page satisfies page-has-heading-one; visually hidden so it
       does not alter the demo (the component under test is what the spec audits). -->
  <h1 class="hotspot-harness-visually-hidden">Hotspot map a11y evidence</h1>

  <a href="#before" data-testid="before">before</a>

  <HotspotMap {entities} title="Hotspot map — Eden libs" />

  <a href="#after" data-testid="after">after</a>
</div>

<style>
  .hotspot-harness-stack {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: var(--space-4, 16px);
    padding: var(--space-8, 32px);
    max-inline-size: 48rem;
  }

  .hotspot-harness-visually-hidden {
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
