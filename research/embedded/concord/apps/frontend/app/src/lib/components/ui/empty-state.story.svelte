<script lang="ts">
  import EmptyState from './empty-state.svelte';
  import { Search, Package, AlertTriangle } from 'lucide-svelte';

  export let Hst: any;
</script>

<Hst.Story title="UI/EmptyState" group="ui">
  <Hst.Variant title="Default">
    <EmptyState />
  </Hst.Variant>

  <Hst.Variant title="Custom Message">
    <EmptyState message="No products match your filters." />
  </Hst.Variant>

  <Hst.Variant title="Custom Icon">
    <EmptyState message="No search results." icon={Search} />
  </Hst.Variant>

  <Hst.Variant title="Package Icon">
    <EmptyState message="No packages available." icon={Package} />
  </Hst.Variant>

  <Hst.Variant title="Warning Icon">
    <EmptyState message="Something went wrong." icon={AlertTriangle} />
  </Hst.Variant>
</Hst.Story>
