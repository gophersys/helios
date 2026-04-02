<script lang="ts">
  import FirmwareTab from '../firmware-tab.svelte';

  interface Props {
    productId: string;
    canManage: boolean;
  }

  let { productId, canManage }: Props = $props();
</script>

<FirmwareTab {productId} {canManage} />
