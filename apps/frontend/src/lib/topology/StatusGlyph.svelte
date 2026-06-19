<script lang="ts">
  // The status glyph — a SHAPE (circle/triangle/octagon/diamond/ring) filled with the generated
  // status role colour. Shape + colour is redundant by design (R3 E1): the health reads under
  // grayscale / colour-blindness, and the shared Legend decodes the shapes. Where there is room a
  // word is added alongside (StatusChip) for the third channel. One home: src/lib/topology/status.ts.
  import type { Status } from './contract';
  import { STATUS, statusColor } from './status';

  let { status = 'unknown', size = 12 }: { status?: Status; size?: number } = $props();
  const spec = $derived(STATUS[status]);
  const fill = $derived(statusColor(status));
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 16 16"
  role="img"
  aria-label={spec.label}
  style="display:block;flex:none"
>
  {#if spec.shape === 'circle'}
    <circle cx="8" cy="8" r="6" fill={fill} />
  {:else if spec.shape === 'triangle'}
    <path d="M8 1.5 L14.5 13.5 L1.5 13.5 Z" fill={fill} />
  {:else if spec.shape === 'octagon'}
    <path d="M5 1.5 H11 L14.5 5 V11 L11 14.5 H5 L1.5 11 V5 Z" fill={fill} />
  {:else if spec.shape === 'diamond'}
    <path d="M8 1 L15 8 L8 15 L1 8 Z" fill={fill} />
  {:else}
    <circle cx="8" cy="8" r="5.5" fill="none" stroke={fill} stroke-width="2" />
  {/if}
</svg>
