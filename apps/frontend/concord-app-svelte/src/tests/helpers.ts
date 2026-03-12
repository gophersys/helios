/**
 * Test helpers and utilities.
 * Import these in your test files for consistent testing patterns.
 */
import { vi, type Mock } from 'vitest';

// ============================================================================
// MOCK FACTORIES
// ============================================================================

/**
 * Creates a mock fetch function with configurable responses.
 * Use this to test API calls without hitting real endpoints.
 *
 * @example
 * const mockFetch = createMockFetch({ data: { id: '1' } });
 * global.fetch = mockFetch;
 * // ... run test
 * expect(mockFetch).toHaveBeenCalledWith('/api/test', expect.any(Object));
 */
export function createMockFetch(
  response: unknown = {},
  options: { status?: number; ok?: boolean; headers?: Record<string, string> } = {}
): Mock {
  const { status = 200, ok = true, headers = {} } = options;

  return vi.fn().mockResolvedValue({
    ok,
    status,
    headers: new Headers(headers),
    json: vi.fn().mockResolvedValue(response),
    text: vi.fn().mockResolvedValue(JSON.stringify(response)),
    clone: function() { return this; }
  });
}

/**
 * Creates a mock fetch that rejects with an error.
 */
export function createMockFetchError(message = 'Network error'): Mock {
  return vi.fn().mockRejectedValue(new Error(message));
}

/**
 * Creates a mock fetch that returns non-JSON (for error scenarios).
 */
export function createMockFetchInvalidJson(): Mock {
  return vi.fn().mockResolvedValue({
    ok: false,
    status: 500,
    headers: new Headers(),
    json: vi.fn().mockRejectedValue(new SyntaxError('Unexpected token')),
    text: vi.fn().mockResolvedValue('Internal Server Error'),
    clone: function() { return this; }
  });
}

// ============================================================================
// MOCK DATA FACTORIES
// ============================================================================

/**
 * Creates a mock user object.
 */
export function createMockUser(overrides: Partial<MockUser> = {}): MockUser {
  return {
    id: 'user-123',
    email: 'test@example.com',
    name: 'Test User',
    picture: 'https://example.com/avatar.jpg',
    permissions: ['products:view'],
    ...overrides
  };
}

export interface MockUser {
  id: string;
  email: string;
  name: string;
  picture?: string;
  permissions: string[];
}

/**
 * Creates a mock API response envelope.
 */
export function createMockApiResponse<T>(data: T, errors: string[] = []): { data: T; errors: string[] } {
  return { data, errors };
}

/**
 * Creates a mock product.
 */
export function createMockProduct(overrides: Partial<MockProduct> = {}): MockProduct {
  return {
    id: 'prod-123',
    name: 'Test Product',
    description: 'A test product',
    active: true,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    ...overrides
  };
}

export interface MockProduct {
  id: string;
  name: string;
  description: string;
  active: boolean;
  createdAt: string;
  updatedAt: string;
}

/**
 * Creates a mock codebase.
 */
export function createMockCodebase(overrides: Partial<MockCodebase> = {}): MockCodebase {
  return {
    id: 'cb-123',
    name: 'Test Codebase',
    description: 'A test codebase',
    repoUrl: 'https://github.com/test/repo',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    ...overrides
  };
}

export interface MockCodebase {
  id: string;
  name: string;
  description: string;
  repoUrl: string;
  createdAt: string;
  updatedAt: string;
}

// ============================================================================
// STORAGE MOCKS
// ============================================================================

/**
 * Creates a mock localStorage.
 */
export function createMockLocalStorage(): MockStorage {
  const store: Record<string, string> = {};

  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: vi.fn((key: string) => { delete store[key]; }),
    clear: vi.fn(() => { Object.keys(store).forEach(k => delete store[k]); }),
    get length() { return Object.keys(store).length; },
    key: vi.fn((index: number) => Object.keys(store)[index] ?? null),
    _store: store // For test assertions
  };
}

export interface MockStorage extends Storage {
  _store: Record<string, string>;
}

/**
 * Sets up localStorage mock on global/window.
 */
export function setupLocalStorageMock(): MockStorage {
  const mock = createMockLocalStorage();
  Object.defineProperty(global, 'localStorage', { value: mock, writable: true });
  return mock;
}

// ============================================================================
// TIMER UTILITIES
// ============================================================================

/**
 * Advances timers and flushes promises.
 * Use this when testing code with setTimeout/setInterval.
 */
export async function advanceTimersAndFlush(ms: number): Promise<void> {
  vi.advanceTimersByTime(ms);
  await flushPromises();
}

/**
 * Flushes all pending promises.
 */
export function flushPromises(): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, 0));
}

// ============================================================================
// VISIBILITY API MOCK
// ============================================================================

/**
 * Mocks the Page Visibility API.
 */
export function mockPageVisibility(hidden = false): {
  setHidden: (hidden: boolean) => void;
  triggerVisibilityChange: () => void;
} {
  let isHidden = hidden;

  Object.defineProperty(document, 'hidden', {
    configurable: true,
    get: () => isHidden
  });

  return {
    setHidden: (h: boolean) => { isHidden = h; },
    triggerVisibilityChange: () => {
      document.dispatchEvent(new Event('visibilitychange'));
    }
  };
}

// ============================================================================
// ASSERTION HELPERS
// ============================================================================

/**
 * Asserts that a mock was called with a specific URL path.
 */
export function expectFetchCalledWith(
  mockFetch: Mock,
  path: string,
  options?: Partial<RequestInit>
): void {
  expect(mockFetch).toHaveBeenCalled();
  const calls = mockFetch.mock.calls;
  const matchingCall = calls.find((call: any[]) =>
    (call[0] as string).includes(path) || call[0] === path
  );
  expect(matchingCall).toBeDefined();

  if (options && matchingCall) {
    expect(matchingCall[1]).toMatchObject(options);
  }
}

/**
 * Waits for a condition to be true with timeout.
 */
export async function waitFor(
  condition: () => boolean | Promise<boolean>,
  timeout = 1000,
  interval = 50
): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    if (await condition()) return;
    await new Promise(r => setTimeout(r, interval));
  }
  throw new Error(`Condition not met within ${timeout}ms`);
}
