<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { ChevronRight, ChevronDown } from 'lucide-svelte';
  import { api } from '$lib/api';
  import { getAuth } from '$lib/stores/auth.svelte';
  import ResourceAge from '$lib/components/system/resource-age.svelte';
  import NamespaceSelector from '$lib/components/system/namespace-selector.svelte';

  type TabType = 'roles' | 'clusterroles' | 'rolebindings' | 'clusterrolebindings' | 'serviceaccounts';

  interface RbacRule {
    apiGroups: string[];
    resources: string[];
    verbs: string[];
    resourceNames: string[];
  }

  interface Role {
    name: string;
    namespace?: string;
    rules: RbacRule[];
    createdAt: string;
  }

  interface RoleBinding {
    name: string;
    namespace?: string;
    roleRef: { kind: string; name: string };
    subjects: { kind: string; name: string; namespace?: string }[];
    createdAt: string;
  }

  interface ServiceAccount {
    name: string;
    namespace: string;
    secrets: string[];
    createdAt: string;
  }

  type RbacItem = Role | RoleBinding | ServiceAccount;

  let tab = $state<TabType>('roles');
  let namespace = $state('');
  let data = $state<RbacItem[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  const auth = getAuth();
  let expandedRule = $state<string | null>(null);

  const isNamespaced = $derived(
    tab === 'roles' || tab === 'rolebindings' || tab === 'serviceaccounts'
  );

  async function fetchData() {
    loading = true;
    error = null;
    try {
      let url = `/v2/kubernetes/rbac/${tab}`;
      if (isNamespaced && namespace) {
        url += `?namespace=${namespace}`;
      }
      const res = await api.get<{ data: RbacItem[] }>(url);
      if (res?.data) data = res.data;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load RBAC data';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.System.View')) {
      goto('/');
      return;
    }
    fetchData();
  });

  $effect(() => {
    tab;
    namespace;
    fetchData();
  });

  function isRole(item: RbacItem): item is Role {
    return 'rules' in item;
  }

  function isRoleBinding(item: RbacItem): item is RoleBinding {
    return 'roleRef' in item;
  }

  function isServiceAccount(item: RbacItem): item is ServiceAccount {
    return 'secrets' in item;
  }

  function getVerbColor(verb: string): string {
    const writeVerbs = ['create', 'update', 'patch', 'delete', 'deletecollection'];
    if (verb === '*') return 'text-warning';
    if (writeVerbs.includes(verb)) return 'text-error';
    return 'text-success';
  }

  function toggleRule(name: string) {
    expandedRule = expandedRule === name ? null : name;
  }

  const tabs: { id: TabType; label: string }[] = [
    { id: 'roles', label: 'Roles' },
    { id: 'clusterroles', label: 'ClusterRoles' },
    { id: 'rolebindings', label: 'RoleBindings' },
    { id: 'clusterrolebindings', label: 'ClusterRoleBindings' },
    { id: 'serviceaccounts', label: 'ServiceAccounts' },
  ];
</script>

<div class="space-y-4">
  <!-- Tab Selector -->
  <div class="flex items-center gap-3 overflow-x-auto">
    <div class="flex rounded-lg bg-surface-2 p-1">
      {#each tabs as t}
        <button
          onclick={() => tab = t.id}
          class="px-3 py-1 text-sm font-medium rounded whitespace-nowrap {tab === t.id ? 'bg-surface-1 text-primary' : 'text-secondary hover:text-primary'}"
        >
          {t.label}
        </button>
      {/each}
    </div>
    {#if isNamespaced}
      <NamespaceSelector value={namespace} onchange={(ns) => namespace = ns} />
    {/if}
    <span class="text-sm text-secondary ml-auto">{data.length} items</span>
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-12">
      <span class="text-secondary">Loading RBAC data...</span>
    </div>
  {:else if error}
    <div class="rounded-lg border border-error/20 bg-error/10 p-4 text-error">{error}</div>
  {:else}
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr class="border-b border-border">
            {#if tab === 'roles' || tab === 'clusterroles'}
              <th class="table-header w-8 px-2"></th>
              <th class="table-header">Name</th>
              {#if tab === 'roles'}
                <th class="table-header">Namespace</th>
              {/if}
              <th class="table-header">Rules</th>
              <th class="table-header">Age</th>
            {:else if tab === 'rolebindings' || tab === 'clusterrolebindings'}
              <th class="table-header">Name</th>
              {#if tab === 'rolebindings'}
                <th class="table-header">Namespace</th>
              {/if}
              <th class="table-header">Role Ref</th>
              <th class="table-header">Subjects</th>
              <th class="table-header">Age</th>
            {:else}
              <th class="table-header">Name</th>
              <th class="table-header">Namespace</th>
              <th class="table-header">Secrets</th>
              <th class="table-header">Age</th>
            {/if}
          </tr>
        </thead>
        <tbody>
          {#each data as item}
            {#if isRole(item)}
              <tr
                class="table-row table-row-interactive"
                onclick={() => toggleRule(item.name)}
              >
                <td class="table-cell px-2">
                  {#if expandedRule === item.name}
                    <ChevronDown class="w-4 h-4 text-text-tertiary" />
                  {:else}
                    <ChevronRight class="w-4 h-4 text-text-tertiary" />
                  {/if}
                </td>
                <td class="table-cell font-medium text-text-primary">{item.name}</td>
                {#if tab === 'roles'}
                  <td class="table-cell text-text-secondary">{item.namespace}</td>
                {/if}
                <td class="table-cell text-text-secondary">{item.rules.length}</td>
                <td class="table-cell">
                  <ResourceAge timestamp={item.createdAt} />
                </td>
              </tr>
              {#if expandedRule === item.name}
                <tr class="bg-surface-0">
                  <td colspan={tab === 'roles' ? 5 : 4} class="px-6 py-3">
                    <table class="w-full text-xs">
                      <thead>
                        <tr class="text-text-tertiary">
                          <th class="px-2 py-1 text-left">API Groups</th>
                          <th class="px-2 py-1 text-left">Resources</th>
                          <th class="px-2 py-1 text-left">Verbs</th>
                          <th class="px-2 py-1 text-left">Resource Names</th>
                        </tr>
                      </thead>
                      <tbody>
                        {#each item.rules as rule}
                          <tr>
                            <td class="px-2 py-1 font-mono text-text-secondary">{rule.apiGroups.join(', ') || '*'}</td>
                            <td class="px-2 py-1 font-mono text-text-secondary">{rule.resources.join(', ')}</td>
                            <td class="px-2 py-1">
                              {#each rule.verbs as verb}
                                <span class="inline-block mr-1 {getVerbColor(verb)}">{verb}</span>
                              {/each}
                            </td>
                            <td class="px-2 py-1 font-mono text-text-secondary">{rule.resourceNames.join(', ') || '-'}</td>
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                  </td>
                </tr>
              {/if}
            {:else if isRoleBinding(item)}
              <tr class="table-row">
                <td class="table-cell font-medium text-text-primary">{item.name}</td>
                {#if tab === 'rolebindings'}
                  <td class="table-cell text-text-secondary">{item.namespace}</td>
                {/if}
                <td class="table-cell font-mono text-text-secondary">
                  {item.roleRef.kind}/{item.roleRef.name}
                </td>
                <td class="table-cell">
                  <div class="flex flex-wrap gap-1">
                    {#each item.subjects as subject}
                      <span class="px-1.5 py-0.5 rounded text-2xs bg-surface-2 text-text-secondary">
                        {subject.kind}/{subject.name}
                      </span>
                    {/each}
                  </div>
                </td>
                <td class="table-cell">
                  <ResourceAge timestamp={item.createdAt} />
                </td>
              </tr>
            {:else if isServiceAccount(item)}
              <tr class="table-row">
                <td class="table-cell font-medium text-text-primary">{item.name}</td>
                <td class="table-cell text-text-secondary">{item.namespace}</td>
                <td class="table-cell text-text-secondary">{item.secrets.length}</td>
                <td class="table-cell">
                  <ResourceAge timestamp={item.createdAt} />
                </td>
              </tr>
            {/if}
          {:else}
            <tr>
              <td colspan="5" class="table-empty">No items found</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
