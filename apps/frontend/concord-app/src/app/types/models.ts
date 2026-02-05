// Shared model interfaces used across the application.

import type React from 'react';
import type { User } from '../auth-provider';

export interface BoardRevision {
  id: string;
  productId: string;
  version: string;
  chipsets: string[];
  status: string;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface FirmwareApp {
  id: string;
  productId: string;
  applicationId: number;
  name: string;
  targetMcu: string | null;
  chipset: string | null;
  coreCloudDeviceType: string | null;
  coreCloudVariant: string | null;
  notes: string | null;
  buildCount?: number;
  createdAt: string;
  updatedAt: string;
}

export interface FirmwareBuild {
  id: string;
  productId: string;
  applicationId: string;
  boardRevisionId: string | null;
  version: string;
  majorVersion: number;
  minorVersion: number;
  buildNumber: number;
  bootloaderId: string | null;
  isManufacturing: boolean;
  storageKey: string;
  filename: string;
  sizeBytes: string | null;
  checksum: string;
  contentType: string | null;
  status: string;
  notes: string | null;
  applicationName?: string;
  boardRevisionVersion?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Product {
  id: string;
  name: string;
  description: string | null;
  active: boolean;
  chipsets?: string[];
  boardRevisionCount?: number;
  firmwareAppCount?: number;
  firmwareBuildCount?: number;
  boardRevisions?: BoardRevision[];
  firmwareApplications?: FirmwareApp[];
  firmwareBuilds?: FirmwareBuild[];
  createdAt: string;
  updatedAt: string;
}

export interface Artifact {
  id: string;
  releaseId: string;
  name: string;
  filename: string | null;
  type: string;
  storageKey: string | null;
  externalUrl: string | null;
  sizeBytes: string | null;
  checksum: string | null;
  contentType: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Release {
  id: string;
  codebaseId: string;
  version: string;
  status: string;
  releaseNotes: string | null;
  tagName: string | null;
  releasedAt: string | null;
  artifactCount: number;
  artifacts?: Artifact[];
  createdAt: string;
  updatedAt: string;
}

export interface LatestRelease {
  id: string;
  version: string;
  status: string;
  releasedAt: string | null;
}

export interface Codebase {
  id: string;
  name: string;
  description: string | null;
  repoUrl: string | null;
  defaultBranch: string;
  imageKey: string | null;
  imageUrl: string | null;
  releaseCount: number;
  latestRelease: LatestRelease | null;
  releases?: Release[];
  createdAt: string;
  updatedAt: string;
}

// ── Inventory types ──────────────────────────────────────────

export interface InventoryRevision {
  id: string;
  componentId: string;
  version: string;
  status: string;
  releaseNotes: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface InventoryComponent {
  id: string;
  name: string;
  description: string | null;
  category: string;
  manufacturer: string;
  partNumber: string;
  imageKey: string | null;
  imageUrl: string | null;
  revisionCount: number;
  revisions?: InventoryRevision[];
  createdAt: string;
  updatedAt: string;
}

export interface BomItem {
  id: string;
  inventoryRevisionId: string;
  quantity: number;
  inventoryRevision?: {
    id: string;
    version: string;
    status: string;
    componentId: string;
    component?: {
      id: string;
      name: string;
      category: string;
      manufacturer: string;
      partNumber: string;
    };
  };
}

export interface AssemblyRevision {
  id: string;
  assemblyId: string;
  version: string;
  status: string;
  releaseNotes: string | null;
  bom?: BomItem[];
  createdAt: string;
  updatedAt: string;
}

export interface Assembly {
  id: string;
  name: string;
  description: string | null;
  imageKey: string | null;
  imageUrl: string | null;
  revisionCount: number;
  revisions?: AssemblyRevision[];
  createdAt: string;
  updatedAt: string;
}

export interface InventoryRevisionOption {
  id: string;
  version: string;
  status: string;
  componentId: string;
  componentName: string;
  category: string;
}

// ── System / Kubernetes types ────────────────────────────────

export interface K8sEvent {
  type: string;
  reason: string;
  message: string;
  object: string;
  namespace: string;
  count: number;
  firstSeen: string | null;
  lastSeen: string | null;
  source: string;
}

export interface NodeSummary {
  name: string;
  status: string;
  roles: string[];
  internalIp: string;
  kubeletVersion: string;
  capacity: Record<string, string>;
  allocatable?: Record<string, string>;
  allocated: { cpuRequests: string; memoryRequests: string; podCount: number };
  labels?: Record<string, string>;
  createdAt: string;
  age?: string;
}

// ── Auth types ───────────────────────────────────────────────

export interface PermissionSet {
  id: string;
  name: string;
  description: string | null;
  permissions: string[];
  userCount?: number;
  users?: PermissionSetUser[];
  createdAt?: string;
  updatedAt?: string;
}

export interface PermissionSetUser {
  id: string;
  name: string;
  email: string;
}

// ── Auth types (extended) ────────────────────────────────────

export interface FullUser extends User {
  active: boolean;
  lastSeenAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface AvailablePermission {
  key: string;
  name: string;
}

// ── History / Audit types ───────────────────────────────────

export interface AuditUser {
  id: string;
  name: string;
  email: string;
}

export interface AuditEntry {
  id: string;
  userId: string | null;
  action: string;
  entityType: string;
  entityId: string | null;
  details: Record<string, unknown> | null;
  ipAddress: string | null;
  createdAt: string;
  user: AuditUser | null;
}

export interface Pagination {
  page: number;
  limit: number;
  total: number;
  pages: number;
}

// ── System / Kubernetes types (extended) ────────────────────

export interface ClusterInfo {
  kubernetesVersion: string;
  platforms: string[];
  nodeCount: number;
  namespaceCount: number;
  resources: {
    pods: { running: number; pending: number; failed: number; succeeded: number; total: number };
    deployments: { available: number; progressing: number; total: number };
    services: { total: number };
    jobs: { active: number; succeeded: number; failed: number; total: number };
  };
}

export interface PodSummary {
  name: string;
  namespace: string;
  status: string;
  ready: string;
  restarts: number;
  nodeName: string;
  createdAt: string;
}

export interface PodDetailData {
  name: string;
  namespace: string;
  status: string;
  ready: string;
  restarts: number;
  nodeName: string;
  podIp: string;
  serviceAccount: string;
  qosClass: string;
  containers: {
    name: string;
    image: string;
    ready: boolean;
    restartCount: number;
    state: string;
  }[];
  conditions: {
    type: string;
    status: string;
    reason: string;
    message: string;
    lastTransition: string;
  }[];
  volumes: { name: string; type: string }[];
  events: {
    type: string;
    reason: string;
    message: string;
    lastSeen: string | null;
    count: number;
  }[];
  labels: Record<string, string>;
  createdAt: string;
  age: string;
}

export interface DeploymentSummary {
  name: string;
  namespace: string;
  replicas: { desired: number; ready: number; available: number; updated: number };
  strategy: string;
  containers: { name: string; image: string }[];
  createdAt: string;
}

export interface DeploymentDetailData {
  name: string;
  namespace: string;
  replicas: { desired: number; ready: number; available: number; updated: number };
  strategy: string;
  containers: { name: string; image: string }[];
  conditions: { type: string; status: string; reason: string; message: string; lastTransition: string }[];
  selector: Record<string, string>;
  labels: Record<string, string>;
  annotations: Record<string, string>;
  pods: { name: string; status: string; ready: boolean; restarts: number; nodeName: string }[];
  createdAt: string;
  age: string;
}

export interface ServiceSummary {
  name: string;
  namespace: string;
  type: string;
  clusterIp: string;
  ports: { name: string; port: number; targetPort: string; protocol: string }[];
  createdAt: string;
}

export interface ServiceDetailData {
  name: string;
  namespace: string;
  type: string;
  clusterIp: string;
  externalIps: string[];
  loadBalancerIp: string | null;
  ports: { name: string; port: number; targetPort: string; protocol: string; nodePort: number | null }[];
  selector: Record<string, string>;
  endpoints: { addresses: string[]; ports: { port: number; protocol: string }[] }[];
  createdAt: string;
  age: string;
}

export interface JobSummary {
  name: string;
  namespace: string;
  completions: string;
  status: string;
  active: number;
  succeeded: number;
  failed: number;
  duration: string;
  createdAt: string;
}

export interface JobDetailData {
  name: string;
  namespace: string;
  completions: string;
  parallelism: number;
  active: number;
  succeeded: number;
  failed: number;
  status: string;
  duration: string;
  backoffLimit: number;
  conditions: { type: string; status: string; reason: string; message: string }[];
  pods: { name: string; status: string; restarts: number }[];
  labels: Record<string, string>;
  createdAt: string;
  age: string;
}

export interface ConfigMapSummary {
  name: string;
  namespace: string;
  dataKeys: string[];
  dataCount: number;
  createdAt: string;
}

export interface SecretSummary {
  name: string;
  namespace: string;
  type: string;
  dataKeys: string[];
  dataCount: number;
  createdAt: string;
}

export interface Role {
  name: string;
  namespace: string;
  rules: { apiGroups: string[]; resources: string[]; verbs: string[]; resourceNames: string[] }[];
  createdAt: string;
}

export interface RoleBinding {
  name: string;
  namespace: string;
  roleRef: { kind: string; name: string };
  subjects: { kind: string; name: string; namespace: string }[];
  createdAt: string;
}

export interface ServiceAccount {
  name: string;
  namespace: string;
  secrets: string[];
  createdAt: string;
}

export interface Namespace {
  name: string;
  status: string;
}

export interface ResourceYamlData {
  kind: string;
  apiVersion: string;
  yaml: string;
}

// ── Guides types ────────────────────────────────────────────

export interface GuideSection {
  id: string;
  title: string;
  icon: React.ComponentType<{ size: number; strokeWidth: number; className?: string }>;
  steps: { title: string; description: string }[];
}

// ── Hooks types ─────────────────────────────────────────────

export interface ChipsetEntry {
  name: string;
  targetMcus: string[];
}

export interface ChipsetConfig {
  chipsets: ChipsetEntry[];
  supportedSocs: string[];
}

// ── UI utility types ─────────────────────────────────────────

export interface TreeNode {
  label: string;
  permKey?: string;
  children: TreeNode[];
}
