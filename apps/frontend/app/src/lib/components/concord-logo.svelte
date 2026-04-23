<script lang="ts">
  interface Props {
    size?: number;
    class?: string;
  }

  let { size = 24, class: className = '' }: Props = $props();
</script>

<!--
  Concord Logo - Minimalistic Concorde jet outline
  Clean line-art style for better visibility
-->
<svg
  width={size}
  height={size}
  viewBox="0 0 32 32"
  fill="none"
  xmlns="http://www.w3.org/2000/svg"
  class="shrink-0 {className}"
>
  <!-- Concorde outline - sleek supersonic silhouette -->
  <path
    d="M3 16L7 13L12 12L26 14.5L30 16L26 17.5L12 20L7 19L3 16Z"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linejoin="round"
    fill="none"
  />
  <!-- Top delta wing -->
  <path
    d="M14 12L22 6L24 14"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    fill="none"
  />
  <!-- Bottom delta wing -->
  <path
    d="M14 20L22 26L24 18"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    fill="none"
  />
  <!-- Tail fin -->
  <path
    d="M7 13L11 8"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="round"
    fill="none"
  />
</svg>
