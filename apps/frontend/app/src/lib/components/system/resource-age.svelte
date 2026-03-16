<script lang="ts">
  import { formatAge } from './k8s-resources';

  interface Props {
    timestamp: string | null;
  }

  let { timestamp }: Props = $props();

  const age = $derived(formatAge(timestamp));
  const fullDate = $derived(timestamp ? new Date(timestamp).toLocaleString() : '');
</script>

<span class="text-text-secondary" title={fullDate}>{age}</span>
