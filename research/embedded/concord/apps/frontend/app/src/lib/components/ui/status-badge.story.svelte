<script lang="ts">
  import StatusBadge from './status-badge.svelte';

  export let Hst: any;

  const statuses = [
    'ACTIVE', 'INACTIVE', 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED',
    'PASSED', 'CANCELLED', 'DRAFT', 'RELEASED', 'ONLINE', 'OFFLINE',
    'BUILDING', 'QUEUED', 'SKIPPED', 'BLOCKED', 'SUCCESS', 'ERROR',
    'AVAILABLE', 'LOCKED', 'HEALTHY', 'DEGRADED', 'PUBLISHED',
    'MANUFACTURING', 'VALIDATION', 'REGISTERED', 'ASSIGNED',
  ];
</script>

<Hst.Story title="UI/StatusBadge" group="ui">
  <Hst.Variant title="All Statuses">
    <div class="flex flex-wrap gap-2 p-4">
      {#each statuses as status}
        <StatusBadge {status} />
      {/each}
    </div>
  </Hst.Variant>

  <Hst.Variant title="Single Status">
    <div class="p-4">
      <StatusBadge status="ACTIVE" />
    </div>
  </Hst.Variant>

  <Hst.Variant title="Unknown Status (fallback)">
    <div class="p-4">
      <StatusBadge status="SOMETHING_ELSE" />
    </div>
  </Hst.Variant>
</Hst.Story>
