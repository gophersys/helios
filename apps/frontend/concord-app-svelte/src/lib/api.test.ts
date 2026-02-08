/**
 * Comprehensive tests for the API layer.
 * This is critical infrastructure - test thoroughly.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getToken,
  setToken,
  clearToken,
  apiFetch,
  apiUpload,
  apiUploadRaw,
  api
} from './api';
import {
  createMockFetch,
  createMockFetchError,
  createMockFetchInvalidJson,
  setupLocalStorageMock,
  createMockApiResponse,
  type MockStorage
} from '../tests/helpers';

// Mock $app/environment
vi.mock('$app/environment', () => ({
  browser: true
}));

describe('Token Management', () => {
  let storage: MockStorage;

  beforeEach(() => {
    storage = setupLocalStorageMock();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('getToken', () => {
    it('returns null when no token exists', () => {
      expect(getToken()).toBeNull();
    });

    it('returns token when it exists', () => {
      storage._store['concord-token'] = 'my-jwt-token';
      expect(getToken()).toBe('my-jwt-token');
    });

    it('calls localStorage.getItem with correct key', () => {
      getToken();
      expect(storage.getItem).toHaveBeenCalledWith('concord-token');
    });
  });

  describe('setToken', () => {
    it('stores token in localStorage', () => {
      setToken('new-token');
      expect(storage.setItem).toHaveBeenCalledWith('concord-token', 'new-token');
    });

    it('token is retrievable after setting', () => {
      setToken('stored-token');
      expect(storage._store['concord-token']).toBe('stored-token');
    });
  });

  describe('clearToken', () => {
    it('removes token from localStorage', () => {
      storage._store['concord-token'] = 'existing-token';
      clearToken();
      expect(storage.removeItem).toHaveBeenCalledWith('concord-token');
    });

    it('token is null after clearing', () => {
      setToken('temp-token');
      clearToken();
      expect(storage._store['concord-token']).toBeUndefined();
    });
  });
});

describe('apiFetch', () => {
  let storage: MockStorage;
  let originalFetch: typeof global.fetch;
  let originalLocation: Location;

  beforeEach(() => {
    storage = setupLocalStorageMock();
    originalFetch = global.fetch;
    originalLocation = window.location;

    // Mock window.location
    delete (window as any).location;
    (window as any).location = { href: '' };
  });

  afterEach(() => {
    global.fetch = originalFetch;
    (window as any).location = originalLocation;
    vi.restoreAllMocks();
  });

  describe('Request Configuration', () => {
    it('sets Content-Type header to application/json', async () => {
      const mockFetch = createMockFetch({ data: {} });
      global.fetch = mockFetch;

      await apiFetch('/api/test');

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/test',
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          })
        })
      );
    });

    it('includes Authorization header when token exists', async () => {
      storage._store['concord-token'] = 'my-jwt';
      const mockFetch = createMockFetch({ data: {} });
      global.fetch = mockFetch;

      await apiFetch('/api/test');

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/test',
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer my-jwt'
          })
        })
      );
    });

    it('does not include Authorization header when no token', async () => {
      const mockFetch = createMockFetch({ data: {} });
      global.fetch = mockFetch;

      await apiFetch('/api/test');

      const callArgs = mockFetch.mock.calls[0][1];
      expect(callArgs.headers.Authorization).toBeUndefined();
    });

    it('merges custom headers with defaults', async () => {
      const mockFetch = createMockFetch({ data: {} });
      global.fetch = mockFetch;

      await apiFetch('/api/test', {
        headers: { 'X-Custom': 'value' }
      });

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/test',
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            'X-Custom': 'value'
          })
        })
      );
    });

    it('passes through request options', async () => {
      const mockFetch = createMockFetch({ data: {} });
      global.fetch = mockFetch;

      await apiFetch('/api/test', { method: 'POST', body: '{"key":"value"}' });

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/test',
        expect.objectContaining({
          method: 'POST',
          body: '{"key":"value"}'
        })
      );
    });
  });

  describe('Response Handling', () => {
    it('returns parsed JSON data on success', async () => {
      const responseData = { data: { id: '123', name: 'Test' } };
      global.fetch = createMockFetch(responseData);

      const result = await apiFetch('/api/test');

      expect(result).toEqual(responseData);
    });

    it('handles 401 by clearing token and redirecting', async () => {
      storage._store['concord-token'] = 'expired-token';
      global.fetch = createMockFetch({}, { status: 401, ok: false });

      await expect(apiFetch('/api/test')).rejects.toThrow('Session expired');
      expect(storage._store['concord-token']).toBeUndefined();
      expect(window.location.href).toBe('/login');
    });

    it('throws error with message from API errors array', async () => {
      global.fetch = createMockFetch(
        { errors: [{ message: 'Validation failed' }] },
        { status: 400, ok: false }
      );

      await expect(apiFetch('/api/test')).rejects.toThrow('Validation failed');
    });

    it('throws error with message from API error field', async () => {
      global.fetch = createMockFetch(
        { error: 'Not found' },
        { status: 404, ok: false }
      );

      await expect(apiFetch('/api/test')).rejects.toThrow('Not found');
    });

    it('throws generic error when no message available', async () => {
      global.fetch = createMockFetch({}, { status: 500, ok: false });

      await expect(apiFetch('/api/test')).rejects.toThrow('Request failed (500)');
    });

    it('handles invalid JSON on error response', async () => {
      global.fetch = createMockFetchInvalidJson();

      await expect(apiFetch('/api/test')).rejects.toThrow('Request failed (500)');
    });

    it('handles invalid JSON on success response', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: vi.fn().mockRejectedValue(new SyntaxError('Unexpected token'))
      });

      await expect(apiFetch('/api/test')).rejects.toThrow('Invalid JSON response');
    });

    it('handles network errors', async () => {
      global.fetch = createMockFetchError('Network unavailable');

      await expect(apiFetch('/api/test')).rejects.toThrow('Network unavailable');
    });
  });
});

describe('api helper object', () => {
  let originalFetch: typeof global.fetch;

  beforeEach(() => {
    setupLocalStorageMock();
    originalFetch = global.fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  describe('api.get', () => {
    it('makes GET request', async () => {
      const mockFetch = createMockFetch({ data: { items: [] } });
      global.fetch = mockFetch;

      await api.get('/api/items');

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/items',
        expect.objectContaining({ method: 'GET' })
      );
    });

    it('returns response data', async () => {
      global.fetch = createMockFetch({ data: { id: '1' } });

      const result = await api.get<{ data: { id: string } }>('/api/item/1');

      expect(result.data.id).toBe('1');
    });
  });

  describe('api.post', () => {
    it('makes POST request with JSON body', async () => {
      const mockFetch = createMockFetch({ data: { created: true } });
      global.fetch = mockFetch;

      await api.post('/api/items', { name: 'New Item' });

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/items',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ name: 'New Item' })
        })
      );
    });

    it('makes POST request without body', async () => {
      const mockFetch = createMockFetch({ data: {} });
      global.fetch = mockFetch;

      await api.post('/api/action');

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/action',
        expect.objectContaining({
          method: 'POST',
          body: undefined
        })
      );
    });
  });

  describe('api.put', () => {
    it('makes PUT request with JSON body', async () => {
      const mockFetch = createMockFetch({ data: { updated: true } });
      global.fetch = mockFetch;

      await api.put('/api/items/1', { name: 'Updated' });

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/items/1',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ name: 'Updated' })
        })
      );
    });
  });

  describe('api.delete', () => {
    it('makes DELETE request', async () => {
      const mockFetch = createMockFetch({ data: { deleted: true } });
      global.fetch = mockFetch;

      await api.delete('/api/items/1');

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/items/1',
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });
});

describe('apiUpload', () => {
  let storage: MockStorage;
  let originalFetch: typeof global.fetch;
  let originalLocation: Location;

  beforeEach(() => {
    storage = setupLocalStorageMock();
    originalFetch = global.fetch;
    originalLocation = window.location;
    delete (window as any).location;
    (window as any).location = { href: '' };
  });

  afterEach(() => {
    global.fetch = originalFetch;
    (window as any).location = originalLocation;
    vi.restoreAllMocks();
  });

  it('does not set Content-Type header (browser handles multipart)', async () => {
    const mockFetch = createMockFetch({ data: { uploaded: true } });
    global.fetch = mockFetch;

    const formData = new FormData();
    formData.append('file', new Blob(['test']), 'test.txt');

    await apiUpload('/api/upload', formData);

    const callArgs = mockFetch.mock.calls[0][1];
    expect(callArgs.headers['Content-Type']).toBeUndefined();
  });

  it('includes Authorization header when token exists', async () => {
    storage._store['concord-token'] = 'upload-token';
    const mockFetch = createMockFetch({ data: {} });
    global.fetch = mockFetch;

    await apiUpload('/api/upload', new FormData());

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/upload',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer upload-token'
        })
      })
    );
  });

  it('uses POST method', async () => {
    const mockFetch = createMockFetch({ data: {} });
    global.fetch = mockFetch;

    await apiUpload('/api/upload', new FormData());

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/upload',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('handles 401 by clearing token and redirecting', async () => {
    storage._store['concord-token'] = 'old-token';
    global.fetch = createMockFetch({}, { status: 401, ok: false });

    await expect(apiUpload('/api/upload', new FormData()))
      .rejects.toThrow('Session expired');

    expect(storage._store['concord-token']).toBeUndefined();
    expect(window.location.href).toBe('/login');
  });

  it('returns parsed response on success', async () => {
    global.fetch = createMockFetch({ data: { fileId: 'f123' } });

    const result = await apiUpload<{ data: { fileId: string } }>('/api/upload', new FormData());

    expect(result.data.fileId).toBe('f123');
  });

  it('throws error with API error message', async () => {
    global.fetch = createMockFetch(
      { error: 'File too large' },
      { status: 413, ok: false }
    );

    await expect(apiUpload('/api/upload', new FormData()))
      .rejects.toThrow('File too large');
  });
});

describe('apiUploadRaw', () => {
  let originalFetch: typeof global.fetch;

  beforeEach(() => {
    setupLocalStorageMock();
    originalFetch = global.fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('returns raw Response object on success', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      json: vi.fn()
    };
    global.fetch = vi.fn().mockResolvedValue(mockResponse);

    const result = await apiUploadRaw('/api/upload', new FormData());

    expect(result).toBe(mockResponse);
  });
});
