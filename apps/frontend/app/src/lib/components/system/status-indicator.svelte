<script lang="ts">
  type StatusType = 'Ready' | 'Running' | 'Active' | 'Succeeded' | 'Complete' |
                    'Pending' | 'ContainerCreating' | 'Terminating' |
                    'NotReady' | 'Failed' | 'Error' | 'CrashLoopBackOff' |
                    'Warning' | 'Normal' | 'Unknown' | string;

  interface Props {
    status: StatusType;
  }

  let { status }: Props = $props();

  const statusColors = $derived.by(() => {
    switch (status) {
      case 'Ready':
      case 'Running':
      case 'Active':
      case 'Succeeded':
      case 'Complete':
      case 'Normal':
        return { dot: 'bg-success', bg: 'bg-success/10', text: 'text-success' };
      case 'Pending':
      case 'ContainerCreating':
      case 'Terminating':
      case 'Warning':
        return { dot: 'bg-warning', bg: 'bg-warning/10', text: 'text-warning' };
      case 'NotReady':
      case 'Failed':
      case 'Error':
      case 'CrashLoopBackOff':
        return { dot: 'bg-error', bg: 'bg-error/10', text: 'text-error' };
      default:
        return { dot: 'bg-text-tertiary', bg: 'bg-surface-2', text: 'text-text-tertiary' };
    }
  });
</script>

<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium {statusColors.bg} {statusColors.text}">
  <span class="w-1.5 h-1.5 rounded-full {statusColors.dot}"></span>
  {status}
</span>
