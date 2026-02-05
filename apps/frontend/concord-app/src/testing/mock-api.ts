/**
 * Mock fetch utility for tests.
 */

interface MockFetchOptions {
  status?: number;
  ok?: boolean;
  headers?: Record<string, string>;
}

/**
 * Mock global.fetch to return a single response for any URL.
 */
export function mockFetch(
  data: unknown,
  options: MockFetchOptions = {}
): jest.Mock {
  const { status = 200, ok = true } = options;
  const mockFn = jest.fn().mockResolvedValue({
    ok,
    status,
    json: () => Promise.resolve(data),
    headers: new Headers(options.headers),
  });
  global.fetch = mockFn;
  return mockFn;
}

/**
 * Mock global.fetch to return different responses based on URL patterns.
 */
export function mockFetchRoutes(
  routes: Record<string, { data: unknown; status?: number; ok?: boolean }>
): jest.Mock {
  const mockFn = jest.fn().mockImplementation((url: string) => {
    for (const [pattern, response] of Object.entries(routes)) {
      if (url.includes(pattern)) {
        return Promise.resolve({
          ok: response.ok ?? true,
          status: response.status ?? 200,
          json: () => Promise.resolve(response.data),
          headers: new Headers(),
        });
      }
    }
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ data: null, errors: [] }),
      headers: new Headers(),
    });
  });
  global.fetch = mockFn;
  return mockFn;
}

/**
 * Mock global.fetch to return an error response.
 */
export function mockFetchError(
  message: string,
  status = 400
): jest.Mock {
  return mockFetch(
    { data: null, errors: [{ message }] },
    { status, ok: false }
  );
}
