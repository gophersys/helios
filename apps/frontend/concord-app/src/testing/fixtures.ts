import type {
  Product,
  Codebase,
  InventoryComponent,
  BoardRevision,
  FirmwareApp,
} from '../app/types/models';

export function createProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: 'prod-1',
    name: 'Sigma5',
    description: 'Main product line',
    active: true,
    metadata: null,
    chipsets: ['Sigma5 Cx'],
    boardRevisionCount: 2,
    firmwareAppCount: 3,
    firmwareBuildCount: 5,
    createdAt: '2025-01-01T00:00:00.000Z',
    updatedAt: '2025-01-15T00:00:00.000Z',
    ...overrides,
  } as Product;
}

export function createBoardRevision(
  overrides: Partial<BoardRevision> = {}
): BoardRevision {
  return {
    id: 'rev-1',
    productId: 'prod-1',
    version: '1.0',
    chipsets: ['nRF9160'],
    status: 'ACTIVE',
    notes: null,
    createdAt: '2025-01-01T00:00:00.000Z',
    updatedAt: '2025-01-01T00:00:00.000Z',
    ...overrides,
  } as BoardRevision;
}

export function createFirmwareApp(
  overrides: Partial<FirmwareApp> = {}
): FirmwareApp {
  return {
    id: 'app-1',
    productId: 'prod-1',
    applicationId: 1,
    name: 'Main App',
    targetMcu: 'nRF9160',
    chipset: 'Sigma5 Cx',
    coreCloudDeviceType: null,
    coreCloudVariant: null,
    notes: null,
    createdAt: '2025-01-01T00:00:00.000Z',
    updatedAt: '2025-01-01T00:00:00.000Z',
    ...overrides,
  } as FirmwareApp;
}

export function createCodebase(overrides: Partial<Codebase> = {}): Codebase {
  return {
    id: 'cb-1',
    name: 'firmware-main',
    description: 'Main firmware repository',
    repoUrl: 'https://github.com/example/firmware',
    defaultBranch: 'main',
    imageKey: null,
    createdAt: '2025-01-01T00:00:00.000Z',
    updatedAt: '2025-01-15T00:00:00.000Z',
    ...overrides,
  } as Codebase;
}

export function createComponent(
  overrides: Partial<InventoryComponent> = {}
): InventoryComponent {
  return {
    id: 'comp-1',
    name: 'nRF9160 SiP',
    category: 'SOM',
    manufacturer: 'Nordic Semiconductor',
    partNumber: 'NRF9160-SICA',
    description: 'System in Package',
    imageKey: null,
    createdAt: '2025-01-01T00:00:00.000Z',
    updatedAt: '2025-01-01T00:00:00.000Z',
    ...overrides,
  } as InventoryComponent;
}
