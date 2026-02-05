import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../api';
import { type ApiResponse } from '../types';

interface UseFetchDataOptions {
  pollInterval?: number;
  enabled?: boolean;
}

interface UseFetchDataResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useFetchData<T>(
  url: string | null,
  options: UseFetchDataOptions = {}
): UseFetchDataResult<T> {
  const { pollInterval, enabled = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    if (!url) return;
    try {
      const res = await api<ApiResponse<T>>(url);
      if (mountedRef.current) {
        setData(res.data);
        setError(null);
      }
    } catch (err: unknown) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Request failed');
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [url]);

  useEffect(() => {
    mountedRef.current = true;
    if (!enabled || !url) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchData();

    let intervalId: ReturnType<typeof setInterval> | undefined;
    if (pollInterval && pollInterval > 0) {
      intervalId = setInterval(fetchData, pollInterval);
    }

    return () => {
      mountedRef.current = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, [fetchData, pollInterval, enabled, url]);

  return { data, loading, error, refetch: fetchData };
}
