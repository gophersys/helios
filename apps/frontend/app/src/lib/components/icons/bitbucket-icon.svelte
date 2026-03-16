<script lang="ts">
  let { size = 24, class: className = '' }: { size?: number; class?: string } = $props();
</script>

<svg
  xmlns="http://www.w3.org/2000/svg"
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="currentColor"
  class={className}
>
  <path d="M2.65 3C2.3 3 2 3.3 2 3.65v.12c0 .03 0 .06.01.09l2.76 16.78c.11.7.72 1.21 1.43 1.21h11.73a1.08 1.08 0 001.07-.9l2.76-16.92v-.02c.03-.36-.23-.68-.6-.68H2.65zm11.21 12.57H9.94l-.89-5.19h5.7l-.89 5.19z"/>
</svg>
