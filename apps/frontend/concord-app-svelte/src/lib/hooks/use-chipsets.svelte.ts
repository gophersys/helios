// Hook for fetching chipsets from the catalog
import { apiFetch } from '$lib/api';
import type { ApiResponse } from '$lib/types';
import type { Chipset } from '$lib/types/models';

interface ChipsetsState {
  data: Chipset[];
  loading: boolean;
  error: string | null;
  fetch: () => Promise<void>;
}

export function useChipsets(): ChipsetsState {
  let data = $state<Chipset[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  async function fetch() {
    loading = true;
    error = null;
    try {
      const res = await apiFetch<ApiResponse<Chipset[]>>('/v2/catalog/chipsets');
      data = Array.isArray(res.data) ? res.data : [];
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load chipsets';
    } finally {
      loading = false;
    }
  }

  // Auto-fetch on creation
  fetch();

  return {
    get data() { return data; },
    get loading() { return loading; },
    get error() { return error; },
    fetch
  };
}
