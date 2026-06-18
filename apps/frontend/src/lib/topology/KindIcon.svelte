<script lang="ts">
  // Minimal, token-friendly service iconography keyed by NodeKind. SVG line icons (24x24,
  // currentColor) so they inherit the node accent. A first set to promote into @eden/icons later.
  import type { NodeKind } from './contract';
  let { kind, size = 18 }: { kind: NodeKind; size?: number } = $props();
</script>

<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
     stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  {#if kind === 'deployment'}
    <rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M9 21V9" />
  {:else if kind === 'statefulset'}
    <rect x="3" y="3" width="14" height="14" rx="2" /><rect x="7" y="7" width="14" height="14" rx="2" />
  {:else if kind === 'daemonset'}
    <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" />
  {:else if kind === 'cronjob'}
    <circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" />
  {:else if kind === 'service'}
    <path d="M12 2l9 5v10l-9 5-9-5V7z" />
  {:else if kind === 'ingress'}
    <circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18" />
  {:else if kind === 'pvc'}
    <ellipse cx="12" cy="6" rx="8" ry="3" /><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6" />
  {:else if kind === 'database'}
    <ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
  {:else if kind === 'cache'}
    <path d="M13 2L4 14h7l-1 8 9-12h-7z" />
  {:else if kind === 'queue'}
    <rect x="3" y="5" width="18" height="3" rx="1" /><rect x="3" y="10.5" width="18" height="3" rx="1" /><rect x="3" y="16" width="18" height="3" rx="1" />
  {:else if kind === 'secretstore'}
    <rect x="4" y="10" width="16" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" />
  {:else if kind === 'namespace'}
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
  {:else}
    <circle cx="12" cy="12" r="9" />
  {/if}
</svg>
