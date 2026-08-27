/**
 * Test data factories for the E2E story suite.
 * Generate consistent, uniquely-named test data with timestamp suffixes.
 */

/** Prefix for all Stage 1 test data — enables cleanup without affecting other stages. */
const PREFIX = 's1';

function uid(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

// ── Product ──────────────────────────────────────────────────

export interface ProductConfig {
  name: string;
  slug: string;
  description: string;
}

export function productConfig(overrides?: Partial<ProductConfig>): ProductConfig {
  const id = uid();
  return {
    name: `${PREFIX}-Product-${id}`,
    slug: `${PREFIX}-product-${id}`,
    description: `Auto-generated product for E2E testing (${id})`,
    ...overrides,
  };
}

// ── TestBed Design ───────────────────────────────────────────

export interface DesignConfig {
  name: string;
  description: string;
  boardRevisionId: string;
  slotCount: number;
}

export function testBedDesignConfig(
  boardRevisionId: string,
  overrides?: Partial<DesignConfig>,
): DesignConfig {
  const id = uid();
  return {
    name: `${PREFIX}-Design-${id}`,
    description: `Auto-generated TestBed design (${id})`,
    boardRevisionId,
    slotCount: 1,
    ...overrides,
  };
}

// ── Fixture ──────────────────────────────────────────────────

export interface FixtureConfig {
  name: string;
  designId: string;
  type: 'MANUFACTURING' | 'VALIDATION';
  productId: string;
}

export function fixtureConfig(
  productId: string,
  type: 'MANUFACTURING' | 'VALIDATION',
  overrides?: Partial<FixtureConfig>,
): FixtureConfig {
  const id = uid();
  return {
    name: `${PREFIX}-Fixture-${id}`,
    designId: '',
    type,
    productId,
    ...overrides,
  };
}

// ── Node ─────────────────────────────────────────────────────

export interface NodeConfig {
  hostname: string;
  type: string;
  address: string;
}

export function nodeConfig(
  type: 'MANUFACTURING' | 'VALIDATION',
  overrides?: Partial<NodeConfig>,
): NodeConfig {
  const id = uid();
  return {
    hostname: `${PREFIX}-node-${id}`,
    type,
    address: `10.0.0.${Math.floor(Math.random() * 254) + 1}`,
    ...overrides,
  };
}

// ── User ─────────────────────────────────────────────────────

export type Role = 'ADMIN' | 'MAINTAINER' | 'DEVELOPER' | 'OPERATOR';

export interface UserConfig {
  email: string;
  name: string;
  role: Role;
  password: string;
}

export function userConfig(role: Role, overrides?: Partial<UserConfig>): UserConfig {
  const id = uid();
  return {
    email: `${PREFIX}-${role.toLowerCase()}-${id}@test.concord.dev`,
    name: `${PREFIX} ${role.charAt(0) + role.slice(1).toLowerCase()} ${id}`,
    role,
    password: `${PREFIX}-pass-${id}`,
    ...overrides,
  };
}
