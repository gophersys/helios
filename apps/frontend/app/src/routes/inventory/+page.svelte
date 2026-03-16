<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { PageHeader, Tabs } from '$lib/components/ui';
  import ComponentsTab from '$lib/components/inventory/components-tab.svelte';
  import AssembliesTab from '$lib/components/inventory/assemblies-tab.svelte';

  const auth = getAuth();
  let activeTab = $state('components');

  const tabs = [
    { id: 'components', label: 'Components' },
    { id: 'assemblies', label: 'Assemblies' },
  ];

  onMount(() => {
    if (!auth.hasPermission('products:view')) {
      goto('/');
    }
  });
</script>

<svelte:head>
  <title>Inventory — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Inventory"
      description="Manage inventory components, assemblies, and their revisions."
    />
  </div>

  <div class="mb-6">
    <Tabs {tabs} bind:activeTab fullWidth />
  </div>

  {#if activeTab === 'components'}
    <ComponentsTab />
  {:else}
    <AssembliesTab />
  {/if}
</div>
