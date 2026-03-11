<script lang="ts">
  let {
    x1,
    y1,
    x2,
    y2,
    animated = false,
  }: {
    x1: number;
    y1: number;
    x2: number;
    y2: number;
    animated?: boolean;
  } = $props();

  // Calculate control points for a smooth bezier curve
  let midX = $derived((x1 + x2) / 2);
</script>

<path
  d="M {x1} {y1} C {midX} {y1}, {midX} {y2}, {x2} {y2}"
  fill="none"
  stroke="var(--color-text-tertiary)"
  stroke-width="2"
  class={animated ? 'animate-dash' : ''}
/>

<!-- Arrow head -->
<polygon
  points="{x2 - 8},{y2 - 4} {x2},{y2} {x2 - 8},{y2 + 4}"
  fill="var(--color-text-tertiary)"
/>

<style>
  @keyframes dash {
    to {
      stroke-dashoffset: -20;
    }
  }

  .animate-dash {
    stroke-dasharray: 5 5;
    animation: dash 0.5s linear infinite;
  }
</style>
