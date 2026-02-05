import { renderHook, waitFor, act } from '@testing-library/react';
import { useFetchData } from './use-fetch-data';
import { api } from '../api';

jest.mock('../api', () => ({ api: jest.fn() }));

const mockApi = api as jest.MockedFunction<typeof api>;

describe('useFetchData', () => {
  beforeEach(() => {
    mockApi.mockClear();
  });

  it('fetches data and returns it', async () => {
    const testData = { id: '1', name: 'Test' };
    mockApi.mockResolvedValue({ data: testData });

    const { result } = renderHook(() => useFetchData('/v2/products'));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toEqual(testData);
    expect(result.current.error).toBeNull();
    expect(mockApi).toHaveBeenCalledWith('/v2/products');
  });

  it('sets loading to true initially, then false after fetch', async () => {
    mockApi.mockResolvedValue({ data: { id: '1' } });

    const { result } = renderHook(() => useFetchData('/v2/products'));

    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.loading).toBe(false));
  });

  it('sets error on fetch failure', async () => {
    mockApi.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useFetchData('/v2/products'));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe('Network error');
  });

  it('does not fetch when url is null', async () => {
    const { result } = renderHook(() => useFetchData(null));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(mockApi).not.toHaveBeenCalled();
    expect(result.current.data).toBeNull();
  });

  it('does not fetch when enabled is false', async () => {
    const { result } = renderHook(() =>
      useFetchData('/v2/products', { enabled: false })
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(mockApi).not.toHaveBeenCalled();
    expect(result.current.data).toBeNull();
  });

  it('refetch triggers a new fetch', async () => {
    const initialData = { data: { id: '1', name: 'Initial' } };
    const refetchData = { data: { id: '2', name: 'Refetched' } };

    mockApi.mockResolvedValueOnce(initialData).mockResolvedValueOnce(refetchData);

    const { result } = renderHook(() => useFetchData('/v2/products'));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual(initialData.data);

    await act(async () => {
      await result.current.refetch();
    });

    await waitFor(() => expect(result.current.data).toEqual(refetchData.data));
    expect(mockApi).toHaveBeenCalledTimes(2);
  });
});
