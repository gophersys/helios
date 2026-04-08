<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { PageHeader, EmptyState } from '$lib/components/ui';

  const auth = getAuth();

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
  <div class="mb-6">
    <PageHeader
      title="Manufacturing"
      description="Track and manage manufacturing runs across your products."
    />
  </div>

  <EmptyState message="Manufacturing runs will appear here once configured for your products." />
</div>
