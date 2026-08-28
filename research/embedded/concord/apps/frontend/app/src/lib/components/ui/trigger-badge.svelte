<script lang="ts">
  import { GitPullRequest, Hand, Zap, Clock, Play } from 'lucide-svelte';

  let {
    type,
    prNumber,
  }: {
    type: 'pr_push' | 'manual' | 'auto' | 'schedule' | string;
    prNumber?: number;
  } = $props();

  const config = $derived.by(() => {
    switch (type) {
      case 'pr_push':
        return { icon: GitPullRequest, label: prNumber ? `PR #${prNumber}` : 'PR', class: 'bg-accent-muted text-accent' };
      case 'manual':
        return { icon: Hand, label: 'Manual', class: 'bg-surface-2 text-text-secondary' };
      case 'auto':
        return { icon: Zap, label: 'Auto', class: 'bg-warning-muted text-warning' };
      case 'schedule':
        return { icon: Clock, label: 'Scheduled', class: 'bg-info-muted text-info' };
      default:
        return { icon: Play, label: type, class: 'bg-surface-2 text-text-secondary' };
    }
  });
</script>

<span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-2xs font-medium {config.class}">
  <config.icon size={12} strokeWidth={2} />
  {config.label}
</span>
