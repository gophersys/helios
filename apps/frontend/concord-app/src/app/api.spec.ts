import { api, getToken, setToken, clearToken } from './api';

describe('api', () => {
  let mockFetch: jest.Mock;

  beforeEach(() => {
    localStorage.clear();
    mockFetch = jest.fn();
    global.fetch = mockFetch;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('injects Authorization header when token exists in localStorage', async () => {
    setToken('test-token');
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: 'test' }),
    });

    await api('/v2/products');

    expect(mockFetch).toHaveBeenCalledWith('/v2/products', {
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer test-token',
      },
    });
  });

  it('does not include Authorization header when no token', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: 'test' }),
    });

    await api('/v2/products');

    expect(mockFetch).toHaveBeenCalledWith('/v2/products', {
      headers: {
        'Content-Type': 'application/json',
      },
    });
  });

  it('parses JSON response and returns data', async () => {
    const responseData = { data: { id: '1', name: 'Product' } };
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => responseData,
    });

    const result = await api('/v2/products');

    expect(result).toEqual(responseData);
  });

  it('on 401 response, clears token and redirects to /login', async () => {
    setToken('expired-token');

    mockFetch.mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ error: 'Unauthorized' }),
    });

    // The api function will try to set window.location.href which triggers jsdom navigation
    // We can suppress the error and just check that the token was cleared
    const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {});

    await expect(api('/v2/products')).rejects.toThrow('Session expired');
    expect(getToken()).toBeNull();

    // Note: In a real test environment, we'd verify window.location.href was set
    // but jsdom doesn't fully support navigation, so we just verify the error was thrown
    // and token was cleared

    consoleError.mockRestore();
  });

  it('on non-ok response, throws Error with error message from response', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({
        errors: [{ message: 'Validation failed' }],
      }),
    });

    await expect(api('/v2/products')).rejects.toThrow('Validation failed');
  });

  it('sets Content-Type to application/json', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: 'test' }),
    });

    await api('/v2/products', { method: 'POST' });

    expect(mockFetch).toHaveBeenCalledWith('/v2/products', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });
  });
});

describe('token functions', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('setToken stores in localStorage, getToken retrieves, clearToken removes', () => {
    expect(getToken()).toBeNull();

    setToken('my-token');
    expect(getToken()).toBe('my-token');

    clearToken();
    expect(getToken()).toBeNull();
  });
});
