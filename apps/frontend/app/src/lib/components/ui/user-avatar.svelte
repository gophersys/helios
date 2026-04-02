<script lang="ts">
  let {
    name,
    email,
    size = 'md',
  }: {
    name?: string;
    email?: string;
    size?: 'sm' | 'md';
  } = $props();

  const COLORS = [
    'bg-accent text-white',
    'bg-success text-white',
    'bg-warning text-white',
    'bg-error text-white',
    'bg-info text-white',
  ];

  const initials = $derived.by(() => {
    if (!name) return '?';
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    return parts[0][0].toUpperCase();
  });

  const colorClass = $derived.by(() => {
    const str = name || email || '';
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0;
    }
    return COLORS[Math.abs(hash) % COLORS.length];
  });

  const sizeClass = $derived(size === 'sm' ? 'h-6 w-6 text-2xs' : 'h-8 w-8 text-xs');

  const tooltip = $derived.by(() => {
    const parts: string[] = [];
    if (name) parts.push(name);
    if (email) parts.push(email);
    return parts.join('\n') || undefined;
  });
</script>

<span
  class="inline-flex shrink-0 items-center justify-center rounded-full font-medium {sizeClass} {colorClass}"
  title={tooltip}
  aria-label={name || email || 'User'}
>
  {initials}
</span>
