<script lang="ts">
  type ColorType = 'success' | 'warning' | 'error' | 'accent' | 'info';

  interface Props {
    value: number;
    max: number;
    size?: number;
    strokeWidth?: number;
    color?: ColorType;
    centerText?: string;
    label?: string;
    sublabel?: string;
  }

  let {
    value,
    max,
    size = 80,
    strokeWidth = 6,
    color,
    centerText,
    label,
    sublabel
  }: Props = $props();

  const percentage = $derived(max > 0 ? Math.min((value / max) * 100, 100) : 0);

  const autoColor = $derived.by((): ColorType => {
    if (color) return color;
    if (percentage >= 90) return 'error';
    if (percentage >= 70) return 'warning';
    return 'success';
  });

  const colorClass = $derived.by(() => {
    switch (autoColor) {
      case 'success': return 'stroke-success';
      case 'warning': return 'stroke-warning';
      case 'error': return 'stroke-error';
      case 'accent': return 'stroke-accent';
      case 'info': return 'stroke-info';
      default: return 'stroke-accent';
    }
  });

  const radius = $derived((size - strokeWidth) / 2);
  const circumference = $derived(2 * Math.PI * radius);
  const strokeDashoffset = $derived(circumference - (percentage / 100) * circumference);
  const center = $derived(size / 2);
  const displayText = $derived(centerText ?? `${Math.round(percentage)}%`);
</script>

<div class="flex flex-col items-center gap-1">
  <div class="relative" style="width: {size}px; height: {size}px;">
    <svg class="transform -rotate-90" width={size} height={size}>
      <!-- Background circle -->
      <circle
        cx={center}
        cy={center}
        r={radius}
        fill="none"
        stroke="currentColor"
        stroke-width={strokeWidth}
        class="text-surface-2"
      />
      <!-- Progress circle -->
      <circle
        cx={center}
        cy={center}
        r={radius}
        fill="none"
        stroke-width={strokeWidth}
        stroke-linecap="round"
        stroke-dasharray={circumference}
        stroke-dashoffset={strokeDashoffset}
        class="{colorClass} transition-all duration-700 ease-out"
      />
    </svg>
    <!-- Center text -->
    <div class="absolute inset-0 flex items-center justify-center">
      <span class="text-sm font-semibold text-text-primary">{displayText}</span>
    </div>
  </div>
  {#if label}
    <span class="text-xs font-medium text-text-primary">{label}</span>
  {/if}
  {#if sublabel}
    <span class="text-2xs text-text-tertiary">{sublabel}</span>
  {/if}
</div>
