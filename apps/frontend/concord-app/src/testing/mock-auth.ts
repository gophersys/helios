import type { User } from '../app/auth-provider';

export function createMockUser(overrides: Partial<User> = {}): User {
  return {
    id: 'test-user-id',
    email: 'test@example.com',
    name: 'Test User',
    permissionSetId: 'test-perm-set-id',
    permissionSetName: 'Test Admin',
    permissions: [
      'Concord.Admin.Products.View',
      'Concord.Admin.Products.Manage',
      'Concord.Admin.Codebases.View',
      'Concord.Admin.Codebases.Manage',
      'Concord.Admin.Inventory.View',
      'Concord.Admin.Inventory.Manage',
      'Concord.Admin.Users.View',
      'Concord.Admin.Users.Manage',
      'Concord.Admin.System.View',
      'Concord.Admin.System.Manage',
    ],
    ...overrides,
  };
}

export function authenticatedAuth(permissions: string[] = []) {
  const user = createMockUser({
    permissions:
      permissions.length > 0 ? permissions : createMockUser().permissions,
  });
  return {
    user,
    isAuthenticated: true,
    isLoading: false,
    login: jest.fn(),
    logout: jest.fn(),
    hasPermission: (...perms: string[]) =>
      perms.every((p) => user.permissions.includes(p)),
  };
}

export function unauthenticatedAuth() {
  return {
    user: null,
    isAuthenticated: false,
    isLoading: false,
    login: jest.fn(),
    logout: jest.fn(),
    hasPermission: () => false,
  };
}
