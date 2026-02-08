// Hook for fetching chipset configuration
import { apiFetch } from '$lib/api';
import type { ApiResponse } from '$lib/types';
import type { ChipsetConfig } from '$lib/types/models';

interface ChipsetConfigState {
  data: ChipsetConfig | null;
  loading: boolean;
  error: string | null;
  fetch: () => Promise<void>;
}

export function useChipsetConfig(): ChipsetConfigState {
  let data = $state<ChipsetConfig | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  async function fetch() {
    loading = true;
    error = null;
    try {
      const res = await apiFetch<ApiResponse<ChipsetConfig>>('/v2/config/chipsets');
      data = res.data;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load chipset config';
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
