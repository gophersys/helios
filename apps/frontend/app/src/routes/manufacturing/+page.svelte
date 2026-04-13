<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Plus } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { PageHeader, EmptyState } from '$lib/components/ui';
  import SessionCreateWizard from '$lib/components/manufacturing/session-create-wizard.svelte';

  const auth = getAuth();
  const canRun = $derived(auth.hasPermission('manufacturing:run'));
  let showCreateWizard = $state(false);

  onMount(() => {
    if (!auth.hasPermission('manufacturing:view')) {
      goto('/');
    }
  });
</script>

<svelte:head>
  <title>Manufacturing — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6 flex items-start justify-between">
    <PageHeader
      title="Manufacturing"
      description="Track and manage manufacturing runs across your products."
    />
    {#if canRun}
      <button onclick={() => showCreateWizard = true} class="btn btn-sm btn-primary">
        <Plus size={16} /> New Session
      </button>
    {/if}
  </div>

  <EmptyState message="Manufacturing sessions will appear here. Start a new session to begin." />
</div>

<SessionCreateWizard
  open={showCreateWizard}
  onClose={() => showCreateWizard = false}
  onStarted={(id) => {
    showCreateWizard = false;
    goto(`/manufacturing/session/${id}`);
  }}
/>
