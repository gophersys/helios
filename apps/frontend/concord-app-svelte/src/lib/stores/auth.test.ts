/**
 * Tests for the auth store.
 * Critical for security - test thoroughly.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  createMockFetch,
  createMockApiResponse,
  setupLocalStorageMock,
  createMockUser,
  type MockStorage
} from '../../tests/helpers';

// We need to test the AuthState class directly since context functions
// require a Svelte component context. We'll extract and test the logic.

// Mock modules before importing
vi.mock('$app/environment', () => ({ browser: true }));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('svelte', () => ({
  getContext: vi.fn(),
  setContext: vi.fn()
}));

// Now import the module under test
import { createAuthContext, getAuth } from './auth.svelte';
import { goto } from '$app/navigation';
import { getContext, setContext } from 'svelte';
import * as api from '$lib/api';

describe('AuthState', () => {
  let storage: MockStorage;
  let originalFetch: typeof global.fetch;

  beforeEach(() => {
    storage = setupLocalStorageMock();
    originalFetch = global.fetch;
    vi.clearAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  describe('createAuthContext', () => {
    it('creates AuthState and sets context', () => {
      const auth = createAuthContext();

      expect(setContext).toHaveBeenCalled();
      expect(auth).toBeDefined();
      expect(auth.isLoading).toBe(true);
      expect(auth.user).toBeNull();
    });
  });

  describe('getAuth', () => {
    it('retrieves auth from context', () => {
      const mockAuth = { user: null };
      vi.mocked(getContext).mockReturnValue(mockAuth);

      const result = getAuth();

      expect(getContext).toHaveBeenCalled();
      expect(result).toBe(mockAuth);
    });
  });

  describe('isAuthenticated', () => {
    it('returns false when user is null', () => {
      const auth = createAuthContext();
      expect(auth.isAuthenticated).toBe(false);
    });

    it('returns true when user exists', async () => {
      const mockUser = createMockUser();
      global.fetch = createMockFetch(createMockApiResponse(mockUser));
      storage._store['concord-token'] = 'valid-token';

      const auth = createAuthContext();
      await auth.init();

      expect(auth.isAuthenticated).toBe(true);
    });
  });

  describe('hasPermission', () => {
    it('returns false when user is null', () => {
      const auth = createAuthContext();
      expect(auth.hasPermission('Concord.Admin.Test')).toBe(false);
    });

    it('returns false when user has no permissions', async () => {
      const mockUser = createMockUser({ permissions: [] });
      global.fetch = createMockFetch(createMockApiResponse(mockUser));
      storage._store['concord-token'] = 'valid-token';

      const auth = createAuthContext();
      await auth.init();

      expect(auth.hasPermission('Concord.Admin.Test')).toBe(false);
    });

    it('returns true when user has the permission', async () => {
      const mockUser = createMockUser({
        permissions: ['Concord.Admin.Catalog.View', 'Concord.Admin.Catalog.Manage']
      });
      global.fetch = createMockFetch(createMockApiResponse(mockUser));
      storage._store['concord-token'] = 'valid-token';

      const auth = createAuthContext();
      await auth.init();

      expect(auth.hasPermission('Concord.Admin.Catalog.View')).toBe(true);
    });

    it('returns false when user is missing any required permission', async () => {
      const mockUser = createMockUser({
        permissions: ['Concord.Admin.Catalog.View']
      });
      global.fetch = createMockFetch(createMockApiResponse(mockUser));
      storage._store['concord-token'] = 'valid-token';

      const auth = createAuthContext();
      await auth.init();

      expect(auth.hasPermission(
        'Concord.Admin.Catalog.View',
        'Concord.Admin.Catalog.Manage'
      )).toBe(false);
    });

    it('returns true when user has all required permissions', async () => {
      const mockUser = createMockUser({
        permissions: ['Concord.Admin.Catalog.View', 'Concord.Admin.Catalog.Manage']
      });
      global.fetch = createMockFetch(createMockApiResponse(mockUser));
      storage._store['concord-token'] = 'valid-token';

      const auth = createAuthContext();
      await auth.init();

      expect(auth.hasPermission(
        'Concord.Admin.Catalog.View',
        'Concord.Admin.Catalog.Manage'
      )).toBe(true);
    });
  });

  describe('init', () => {
    it('sets isLoading to false when no token exists', async () => {
      const auth = createAuthContext();
      await auth.init();

      expect(auth.isLoading).toBe(false);
      expect(auth.user).toBeNull();
    });

    it('fetches user when token exists', async () => {
      const mockUser = createMockUser();
      const mockFetch = createMockFetch(createMockApiResponse(mockUser));
      global.fetch = mockFetch;
      storage._store['concord-token'] = 'valid-token';

      const auth = createAuthContext();
      await auth.init();

      expect(mockFetch).toHaveBeenCalled();
      expect(auth.user).toEqual(mockUser);
      expect(auth.isLoading).toBe(false);
    });

    it('clears token and sets user null on API error', async () => {
      global.fetch = vi.fn().mockRejectedValue(new Error('Unauthorized'));
      storage._store['concord-token'] = 'invalid-token';

      const auth = createAuthContext();
      await auth.init();

      expect(storage._store['concord-token']).toBeUndefined();
      expect(auth.user).toBeNull();
      expect(auth.isLoading).toBe(false);
    });

    it('sets isLoading to false even on error', async () => {
      global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));
      storage._store['concord-token'] = 'some-token';

      const auth = createAuthContext();
      await auth.init();

      expect(auth.isLoading).toBe(false);
    });
  });

  describe('login', () => {
    it('calls login API with email and password', async () => {
      const mockLoginResponse = {
        data: {
          token: 'new-jwt-token',
          user: { id: '1', email: 'test@test.com', name: 'Test', permissionSetId: null, permissionSetName: null }
        }
      };
      const mockUser = createMockUser();

      let callCount = 0;
      global.fetch = vi.fn().mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve(mockLoginResponse)
          });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(createMockApiResponse(mockUser))
        });
      });

      const auth = createAuthContext();
      await auth.login('test@test.com', 'password123');

      // Should have called login endpoint with email/password
      expect(global.fetch).toHaveBeenCalledWith(
        '/v2/auth/login',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ email: 'test@test.com', password: 'password123' })
        })
      );

      // Should have stored the token
      expect(storage._store['concord-token']).toBe('new-jwt-token');
    });

    it('fetches user profile after login', async () => {
      const mockLoginResponse = {
        data: { token: 'jwt', user: { id: '1', email: 'a@b.c', name: 'A', permissionSetId: null, permissionSetName: null } }
      };
      const mockUser = createMockUser({ id: 'user-after-login' });

      let callCount = 0;
      global.fetch = vi.fn().mockImplementation(() => {
        callCount++;
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(
            callCount === 1 ? mockLoginResponse : createMockApiResponse(mockUser)
          )
        });
      });

      const auth = createAuthContext();
      await auth.login('user@test.com', 'secret');

      // Should have fetched /v2/auth/me
      expect(global.fetch).toHaveBeenCalledWith(
        '/v2/auth/me',
        expect.anything()
      );
      expect(auth.user?.id).toBe('user-after-login');
    });

    it('throws on login failure', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ error: 'Invalid email or password' })
      });

      // Mock clearToken to not redirect
      vi.spyOn(api, 'clearToken').mockImplementation(() => {});

      const auth = createAuthContext();

      await expect(auth.login('bad@test.com', 'wrong')).rejects.toThrow();
    });
  });

  describe('logout', () => {
    it('clears token', async () => {
      const mockUser = createMockUser();
      global.fetch = createMockFetch(createMockApiResponse(mockUser));
      storage._store['concord-token'] = 'logged-in-token';

      const auth = createAuthContext();
      await auth.init();
      auth.logout();

      expect(storage._store['concord-token']).toBeUndefined();
    });

    it('sets user to null', async () => {
      const mockUser = createMockUser();
      global.fetch = createMockFetch(createMockApiResponse(mockUser));
      storage._store['concord-token'] = 'token';

      const auth = createAuthContext();
      await auth.init();
      expect(auth.user).not.toBeNull();

      auth.logout();
      expect(auth.user).toBeNull();
    });

    it('redirects to login page', async () => {
      const mockUser = createMockUser();
      global.fetch = createMockFetch(createMockApiResponse(mockUser));
      storage._store['concord-token'] = 'token';

      const auth = createAuthContext();
      await auth.init();
      auth.logout();

      expect(goto).toHaveBeenCalledWith('/login');
    });
  });
});
