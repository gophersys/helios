<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { FlaskConical, Cpu, Wrench, ArrowRight, Activity } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('Concord.Admin.Validation.Manage'));

  interface NavCard {
    title: string;
    description: string;
    href: string;
    icon: typeof FlaskConical;
    count?: number;
  }

  const navCards: NavCard[] = [
    {
      title: 'Validation Runs',
      description: 'View and manage validation test sessions, results, and power measurements.',
      href: '/validation/runs',
      icon: Activity,
    },
    {
      title: 'Test Benches',
      description: 'Registered MTIBs with DUT configuration and hardware settings.',
      href: '/validation/benches',
      icon: Cpu,
    },
    {
      title: 'Fixture Designs',
      description: 'Versioned hardware designs with profile templates and capabilities.',
      href: '/validation/designs',
      icon: Wrench,
    },
  ];

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.Validation.View')) {
      goto('/');
    }
  });
</script>

<svelte:head>
  <title>Validation - Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-8">
    <PageHeader
      title="Validation"
      description="Product validation infrastructure - test runs, benches, and fixture designs."
    />
  </div>

  <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
    {#each navCards as card}
      <a
        href={card.href}
        class="group rounded-lg border border-border bg-surface-1 p-6 transition-all hover:border-accent hover:shadow-lg"
      >
        <div class="mb-4 flex items-center justify-between">
          <div class="rounded-lg bg-accent-muted p-2.5">
            <card.icon size={20} class="text-accent" />
          </div>
          <ArrowRight
            size={16}
            class="text-text-tertiary transition-transform group-hover:translate-x-1 group-hover:text-accent"
          />
        </div>
        <h3 class="mb-1 text-lg font-semibold text-text-primary">{card.title}</h3>
        <p class="text-sm text-text-secondary">{card.description}</p>
      </a>
    {/each}
  </div>

  {#if canManage}
    <div class="mt-8 rounded-lg border border-border bg-surface-1 p-6">
      <h2 class="mb-4 text-lg font-semibold text-text-primary">Quick Actions</h2>
      <div class="flex flex-wrap gap-3">
        <a href="/validation/runs" class="btn btn-sm btn-primary">
          <FlaskConical size={14} class="mr-1.5" />
          View Runs
        </a>
        <a href="/validation/benches/register" class="btn btn-sm">
          <Cpu size={14} class="mr-1.5" />
          Register MTIB
        </a>
        <a href="/validation/designs" class="btn btn-sm">
          <Wrench size={14} class="mr-1.5" />
          Manage Designs
        </a>
      </div>
    </div>
  {/if}
</div>
