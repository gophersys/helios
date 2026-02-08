<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import Select from '$lib/components/ui/select.svelte';

  interface Props {
    value: string;
    onchange: (ns: string) => void;
  }

  let { value, onchange }: Props = $props();

  let namespaces = $state<string[]>([]);
  let loading = $state(true);

  onMount(async () => {
    try {
      const res = await api.get<{ data: { name: string }[] }>('/v2/system/namespaces');
      if (res?.data) {
        namespaces = res.data.map((n: { name: string }) => n.name);
      }
    } catch {
      // Silently fail, just show all namespaces option
    } finally {
      loading = false;
    }
  });

  function handleChange(e: Event) {
    // The Select component sets value via bind, read it after change
    onchange(String(value));
  }
</script>

<Select
  bind:value={value}
  onchange={handleChange}
  disabled={loading}
  placeholder="All namespaces"
  options={namespaces.map(ns => ({ value: ns, label: ns }))}
  compact
/>
