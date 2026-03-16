<script lang="ts">
  let {
    class: className = '',
    width = '100%',
    height = '1rem',
  }: {
    class?: string;
    width?: string;
    height?: string;
  } = $props();
</script>

<div
  class="animate-pulse rounded bg-surface-2 {className}"
  style="width: {width}; height: {height};"
  aria-hidden="true"
></div>
