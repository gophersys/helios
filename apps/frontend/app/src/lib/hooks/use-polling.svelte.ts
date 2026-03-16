/**
 * Polling hook with visibility awareness.
 * Automatically pauses polling when the tab is hidden to save resources.
 */

import { onMount, onDestroy } from 'svelte';
import { browser } from '$app/environment';

export interface UsePollingOptions<T> {
  /** Function to fetch data */
  fetchFn: () => Promise<T>;
  /** Polling interval in milliseconds (default: 15000) */
  interval?: number;
  /** Whether to respect page visibility (pause when hidden) */
  respectVisibility?: boolean;
  /** Whether to fetch immediately on mount */
  fetchOnMount?: boolean;
  /** Callback when fetch succeeds */
  onSuccess?: (data: T) => void;
  /** Callback when fetch fails */
  onError?: (error: Error) => void;
}

export interface UsePollingReturn<T> {
  /** Manually trigger a fetch */
  refetch: () => Promise<void>;
  /** Start polling */
  start: () => void;
  /** Stop polling */
  stop: () => void;
  /** Whether polling is currently active */
  isPolling: boolean;
}

/**
 * Creates a polling mechanism with automatic visibility handling.
 *
 * @example
 * ```ts
 * let data = $state<T | null>(null);
 * let loading = $state(true);
 * let error = $state<string | null>(null);
 *
 * const { refetch } = usePolling({
 *   fetchFn: async () => {
 *     const res = await api.get<{ data: T }>('/api/data');
 *     return res.data;
 *   },
 *   interval: 15000,
 *   onSuccess: (result) => {
 *     data = result;
 *     error = null;
 *     loading = false;
 *   },
 *   onError: (err) => {
 *     error = err.message;
 *     loading = false;
 *   }
 * });
 * ```
 */
export function usePolling<T>(options: UsePollingOptions<T>): UsePollingReturn<T> {
  const {
    fetchFn,
    interval = 15000,
    respectVisibility = true,
    fetchOnMount = true,
    onSuccess,
    onError
  } = options;

  let pollInterval: ReturnType<typeof setInterval> | null = null;
  let isPolling = false;

  async function refetch(): Promise<void> {
    try {
      const data = await fetchFn();
      onSuccess?.(data);
    } catch (e) {
      const error = e instanceof Error ? e : new Error(String(e));
      onError?.(error);
    }
  }

  function start(): void {
    if (pollInterval) return; // Already polling
    isPolling = true;
    pollInterval = setInterval(refetch, interval);
  }

  function stop(): void {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    isPolling = false;
  }

  function handleVisibilityChange(): void {
    if (document.hidden) {
      stop();
    } else {
      refetch(); // Refresh immediately when tab becomes visible
      start();
    }
  }

  onMount(() => {
    if (fetchOnMount) {
      refetch();
    }
    start();

    if (browser && respectVisibility) {
      document.addEventListener('visibilitychange', handleVisibilityChange);
    }
  });

  onDestroy(() => {
    stop();
    if (browser && respectVisibility) {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    }
  });

  return {
    refetch,
    start,
    stop,
    get isPolling() {
      return isPolling;
    }
  };
}

/**
 * Simple interval-based polling without the full hook machinery.
 * Use this when you need manual control or in non-component contexts.
 */
export function createPollingInterval(
  fn: () => void | Promise<void>,
  intervalMs: number,
  options: { respectVisibility?: boolean } = {}
): { start: () => void; stop: () => void } {
  const { respectVisibility = true } = options;
  let interval: ReturnType<typeof setInterval> | null = null;

  function handleVisibility() {
    if (document.hidden) {
      stop();
    } else {
      fn();
      start();
    }
  }

  function start() {
    if (interval) return;
    interval = setInterval(fn, intervalMs);
    if (browser && respectVisibility) {
      document.addEventListener('visibilitychange', handleVisibility);
    }
  }

  function stop() {
    if (interval) {
      clearInterval(interval);
      interval = null;
    }
    if (browser && respectVisibility) {
      document.removeEventListener('visibilitychange', handleVisibility);
    }
  }

  return { start, stop };
}
