# Phase 2 — API Client and Types

## Objective

Port the API client module and all TypeScript type definitions. These are framework-agnostic and require minimal changes.

---

## 1. Create `src/lib/api.ts`

Nearly identical to React version. Only change: use `$app/environment` for detecting browser vs server.

```typescript
import { browser } from '$app/environment';

const TOKEN_KEY = 'concord-token';

export function getToken(): string | null {
  if (!browser) return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (!browser) return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (!browser) return;
  localStorage.removeItem(TOKEN_KEY);
}

export async function api<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>)
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(path, { ...options, headers });

  if (res.status === 401) {
    clearToken();
    if (browser) {
      window.location.href = '/login';
    }
    throw new Error('Session expired');
  }

  const data = await res.json();

  if (!res.ok) {
    throw new Error(
      data.errors?.[0]?.message || data.error || `Request failed (${res.status})`
    );
  }

  return data as T;
}

export async function apiUploadRaw(
  path: string,
  formData: FormData
): Promise<Response> {
  const token = getToken();

  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(path, {
    method: 'POST',
    headers,
    body: formData
  });

  if (res.status === 401) {
    clearToken();
    if (browser) {
      window.location.href = '/login';
    }
    throw new Error('Session expired');
  }

  if (!res.ok) {
    const data = await res.json();
    throw new Error(
      data.error || data.errors?.[0]?.message || `Upload failed (${res.status})`
    );
  }

  return res;
}

export async function apiUpload<T = unknown>(
  path: string,
  formData: FormData
): Promise<T> {
  const token = getToken();

  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  // Do NOT set Content-Type — browser sets it with boundary for multipart

  const res = await fetch(path, {
    method: 'POST',
    headers,
    body: formData
  });

  if (res.status === 401) {
    clearToken();
    if (browser) {
      window.location.href = '/login';
    }
    throw new Error('Session expired');
  }

  const data = await res.json();

  if (!res.ok) {
    throw new Error(
      data.error || data.errors?.[0]?.message || `Request failed (${res.status})`
    );
  }

  return data as T;
}
```

---

## 2. Create `src/lib/types.ts`

Copy from React:

```typescript
export interface ApiResponse<T> {
  data: T;
  errors: Array<{
    code: string;
    message: string;
    field?: string;
  }>;
}
```

---

## 3. Create `src/lib/types/models.ts`

Copy the entire file from React. This is pure TypeScript, no React dependencies. Example subset:

```typescript
// User & Auth
export interface User {
  id: string;
  email: string;
  name: string;
  permissionSetId: string | null;
  permissionSetName: string | null;
  permissions: string[];
  createdAt: string;
  updatedAt: string;
}

export interface PermissionSet {
  id: string;
  name: string;
  description: string | null;
  permissions: string[];
  createdAt: string;
  updatedAt: string;
}

export interface ApiKey {
  id: string;
  name: string;
  keyPrefix: string;
  expiresAt: string | null;
  lastUsedAt: string | null;
  createdAt: string;
}

// Products
export interface Product {
  id: string;
  name: string;
  description: string | null;
  active: boolean;
  boardRevisions: BoardRevision[];
  firmwareApps: FirmwareApp[];
  createdAt: string;
  updatedAt: string;
}

export interface BoardRevision {
  id: string;
  productId: string;
  revision: string;
  description: string | null;
  chipset: string;
  active: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface FirmwareApp {
  id: string;
  productId: string;
  name: string;
  appId: string;
  description: string | null;
  active: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface FirmwareBuild {
  id: string;
  productId: string;
  boardRevisionId: string;
  firmwareAppId: string;
  version: string;
  description: string | null;
  artifactKey: string | null;
  artifactSize: number | null;
  createdAt: string;
  updatedAt: string;
}

// Codebases
export interface Codebase {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  imageKey: string | null;
  releases: Release[];
  createdAt: string;
  updatedAt: string;
}

export interface Release {
  id: string;
  codebaseId: string;
  version: string;
  description: string | null;
  status: 'DRAFT' | 'RELEASED' | 'DEPRECATED';
  artifacts: Artifact[];
  createdAt: string;
  updatedAt: string;
}

export interface Artifact {
  id: string;
  releaseId: string;
  name: string;
  filename: string;
  size: number;
  type: 'UPLOAD' | 'EXTERNAL';
  externalUrl: string | null;
  storageKey: string | null;
  createdAt: string;
}

// Inventory
export interface InventoryComponent {
  id: string;
  name: string;
  partNumber: string;
  description: string | null;
  category: string | null;
  imageKey: string | null;
  currentRevision: string | null;
  revisions: InventoryRevision[];
  createdAt: string;
  updatedAt: string;
}

export interface InventoryRevision {
  id: string;
  componentId: string;
  revision: string;
  description: string | null;
  status: 'ACTIVE' | 'DEPRECATED' | 'EOL';
  createdAt: string;
}

export interface Assembly {
  id: string;
  name: string;
  assemblyNumber: string;
  description: string | null;
  imageKey: string | null;
  currentRevision: string | null;
  revisions: AssemblyRevision[];
  createdAt: string;
  updatedAt: string;
}

export interface AssemblyRevision {
  id: string;
  assemblyId: string;
  revision: string;
  description: string | null;
  status: 'ACTIVE' | 'DEPRECATED' | 'EOL';
  components: AssemblyComponent[];
  createdAt: string;
}

export interface AssemblyComponent {
  id: string;
  componentId: string;
  revisionId: string | null;
  quantity: number;
  referenceDesignator: string | null;
  component?: InventoryComponent;
}

// Audit Log
export interface AuditLogEntry {
  id: string;
  userId: string;
  userEmail: string;
  action: string;
  resourceType: string;
  resourceId: string;
  resourceName: string | null;
  changes: Record<string, unknown> | null;
  createdAt: string;
}

// System Monitor (K8s)
export interface ClusterInfo {
  kubernetesVersion: string;
  platform: string;
  nodeCount: number;
  namespaceCount: number;
  resources: {
    pods: { running: number; pending: number; failed: number; total: number };
    deployments: { available: number; progressing: number; total: number };
    services: { total: number };
    jobs: { active: number; succeeded: number; failed: number; total: number };
  };
}

export interface K8sNamespace {
  name: string;
  status: string;
  createdAt: string;
  age: string;
}

export interface K8sNode {
  name: string;
  status: string;
  roles: string[];
  internalIp: string;
  osImage: string;
  kubeletVersion: string;
  containerRuntime: string;
  architecture: string;
  capacity: Record<string, string>;
  allocatable: Record<string, string>;
  conditions: K8sCondition[];
  labels: Record<string, string>;
  annotations: Record<string, string>;
  taints: K8sTaint[];
  unschedulable: boolean;
  createdAt: string;
  age: string;
}

export interface K8sCondition {
  type: string;
  status: string;
  reason: string;
  message: string;
  lastTransition: string;
}

export interface K8sTaint {
  key: string;
  value: string;
  effect: string;
}

export interface K8sEvent {
  type: string;
  reason: string;
  message: string;
  object: string;
  namespace: string;
  count: number;
  firstSeen: string;
  lastSeen: string;
  source: string;
}

export interface K8sPod {
  name: string;
  namespace: string;
  status: string;
  nodeName: string;
  podIP: string;
  startTime: string;
  age: string;
  containers: K8sContainer[];
  conditions: K8sCondition[];
  labels: Record<string, string>;
  annotations: Record<string, string>;
}

export interface K8sContainer {
  name: string;
  image: string;
  ready: boolean;
  restartCount: number;
  state: string;
  stateReason: string | null;
}

export interface K8sDeployment {
  name: string;
  namespace: string;
  replicas: number;
  availableReplicas: number;
  readyReplicas: number;
  updatedReplicas: number;
  strategy: string;
  selector: Record<string, string>;
  labels: Record<string, string>;
  createdAt: string;
  age: string;
}

export interface K8sService {
  name: string;
  namespace: string;
  type: string;
  clusterIP: string;
  externalIP: string | null;
  ports: K8sServicePort[];
  selector: Record<string, string>;
  labels: Record<string, string>;
  createdAt: string;
  age: string;
}

export interface K8sServicePort {
  name: string;
  port: number;
  targetPort: number | string;
  protocol: string;
  nodePort: number | null;
}

export interface K8sJob {
  name: string;
  namespace: string;
  completions: number;
  succeeded: number;
  failed: number;
  active: number;
  startTime: string | null;
  completionTime: string | null;
  duration: string | null;
  labels: Record<string, string>;
  createdAt: string;
  age: string;
}

export interface K8sConfigMap {
  name: string;
  namespace: string;
  dataKeys: string[];
  labels: Record<string, string>;
  createdAt: string;
  age: string;
}

export interface K8sSecret {
  name: string;
  namespace: string;
  type: string;
  dataKeys: string[];
  labels: Record<string, string>;
  createdAt: string;
  age: string;
}
```

---

## Verification

1. Create a test file `src/lib/api.test.ts` to verify types compile:

```typescript
import { api, getToken, setToken, clearToken } from './api';
import type { ApiResponse } from './types';
import type { Product, User } from './types/models';

// Type checks (these just need to compile, not run)
async function test() {
  const products = await api<ApiResponse<Product[]>>('/v2/products');
  const p: Product = products.data[0];
  console.log(p.name);

  const me = await api<ApiResponse<User>>('/v2/auth/me');
  console.log(me.data.email);
}
```

2. Run `npm run check` — should pass with no type errors
3. Delete the test file after verification

---

## Files Created

| File | Description |
|------|-------------|
| `src/lib/api.ts` | API client with token management |
| `src/lib/types.ts` | Shared API response types |
| `src/lib/types/models.ts` | All model interfaces |

---

## Next Phase

Phase 3 will implement the auth store and login page.
