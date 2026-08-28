<script lang="ts">
  interface Props {
    label: string;
    used: number;
    total: number;
    unit?: string;
    formatFn?: (val: number) => string;
  }

  let { label, used, total, unit = '', formatFn }: Props = $props();

  const percentage = $derived(total > 0 ? Math.min((used / total) * 100, 100) : 0);

  const colorClass = $derived.by(() => {
    if (percentage >= 90) return 'bg-error';
    if (percentage >= 70) return 'bg-warning';
    return 'bg-success';
  });

  const formatValue = (val: number) => {
    if (formatFn) return formatFn(val);
    return unit ? `${val}${unit}` : val.toString();
  };
</script>

<div class="space-y-1">
  <div class="flex justify-between text-xs">
    <span class="text-text-secondary">{label}</span>
    <span class="text-text-primary font-medium">
      {formatValue(used)} / {formatValue(total)} ({Math.round(percentage)}%)
    </span>
  </div>
  <div class="h-2 bg-surface-2 rounded-full overflow-hidden">
    <div
      class="h-full {colorClass} transition-all duration-500 ease-out rounded-full"
      style="width: {percentage}%"
    ></div>
  </div>
</div>
