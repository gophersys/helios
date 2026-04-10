// Shared model interfaces used across the application.

// ── Auth types ───────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  permissionSetId: string | null;
  permissionSetName: string | null;
  permissions: string[];
}

export interface FullUser extends User {
  active: boolean;
  lastSeenAt: string | null;
  createdAt: string;
  updatedAt: string;
}

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

export interface AvailablePermission {
  key: string;
  name: string;
}

// ── Catalog types ────────────────────────────────────────────

export interface ModemFirmware {
  id: string;
  boardRevisionId: string;
  version: string;
  filename: string;
  storageKey: string;
  sizeBytes: number;
  checksum: string | null;
  notes: string | null;
  createdById: string | null;
  createdAt: string;
}

export interface BoardRevision {
  id: string;
  boardId: string;
  version: string;
  ckBoardsName: string | null;
  socs: string[];
  deviceType: number | null;
  deviceVariant: number | null;
  modemVersion: string | null;
  hasModemFirmware: boolean;
  status: string;
  notes: string | null;
  targets?: ProductTarget[];
  modemFirmwares?: ModemFirmware[];
  createdAt: string;
  updatedAt: string;
}

export interface Board {
  id: string;
  productId: string;
  name: string;
  ckBoardsFamily: string | null;
  vendor: string;
  description: string | null;
  active: boolean;
  revisionCount?: number;
  revisions?: BoardRevision[];
  createdAt: string;
  updatedAt: string;
}

export interface FirmwareSet {
  id: string;
  productId: string;
  boardRevisionId: string | null;
  version: string;
  variant?: string;
  releaseTrack: string;
  isManufacturing: boolean;
  isDebug: boolean;
  source: string;
  modemVersion: string | null;
  status: string;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
  boardRevision?: { id: string; version: string; ckBoardsName: string } | null;
  builds?: FirmwareBuild[];
}

export interface FirmwareBuild {
  id: string;
  firmwareSetId: string;
  targetId: string | null;
  target: { id: string; role: string; soc: string; appId: number } | null;
  versionString: string | null;
  hexStorageKey: string | null;
  cfwStorageKey: string | null;
  filename: string;
  sizeBytes: string | null;
  checksum: string;
  contentType: string | null;
  notes: string | null;
  createdAt: string;
  // Display fields used by firmware-app-list
  version?: string | null;
  modemFilename?: string | null;
  status?: string | null;
  isManufacturing?: boolean;
}

export interface ProductTarget {
  id: string;
  role: string;
  soc: string;
  appId: number;
}

export interface TestPackageSummary {
  version: string;
  status: 'DEVELOPMENT' | 'RELEASED';
  testCount: number;
  message: string | null;
  gitSha: string | null;
  gitDirty: boolean | null;
  updatedAt: string | null;
}

export interface TestAppStatus {
  validation: TestPackageSummary | null;
  manufacturing: TestPackageSummary | null;
}

export interface TestPackage {
  id: string;
  productId: string;
  version: string;
  releasedVersion: string | null;
  type: 'VALIDATION' | 'MANUFACTURING';
  status: 'DEVELOPMENT' | 'RELEASED';
  frameworkVersion: string;
  testCount: number;
  schemaVersion: string | null;
  message: string | null;
  gitSha: string | null;
  gitDirty: boolean | null;
  notes: string | null;
  releasedAt: string | null;
  releasedById: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Product {
  id: string;
  name: string;
  slug: string | null;
  description: string | null;
  active: boolean;
  fwRepoSlug: string | null;
  mfgFwRepoSlug: string | null;
  builderImage: string | null;
  metadata: Record<string, unknown> | null;
  buildConfig: BuildConfig | null;
  targets: ProductTarget[];
  boardCount?: number;
  assetSetCount?: number;
  sessionCount?: number;
  testCount?: number;
  testAppStatus?: TestAppStatus;
  boards?: Board[];
  manufacturingStats?: {
    activeSessions: number;
    totalDevices: number;
    passedDevices: number;
    failedDevices: number;
  };
  createdAt: string;
  updatedAt: string;
}

// ── Build Config types ──────────────────────────────────────

export interface BuildConfigTarget {
  soc: string;
  appId: number;
  role: string;
}

export interface BuildConfigCfw {
  deviceType: number;
  deviceVariant: number;
}

export interface BuildConfig {
  board: string;
  ncsVersion: string;
  boardRoot: string;
  hasVsmMerge: boolean;
  hasFips: boolean;
  confFiles: Record<string, string[]>;
  overlays: Record<string, string[]>;
  postBuild: string[];
  cfw: BuildConfigCfw;
}

// ── Board Discovery types ───────────────────────────────────

export interface BoardFamilyRevision {
  version: string;
  ckBoardsName: string;
  socs: string[];
}

export interface BoardSummary {
  family: string;
  vendor: string;
  revisions: BoardFamilyRevision[];
}

export interface BoardDetail {
  family: string;
  vendor: string;
  revisions: BoardFamilyRevision[];
}

export interface BoardBranchesResponse {
  branches: string[];
  tags: string[];
}

// ── Codebases types ──────────────────────────────────────────

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

// ── History / Audit types ────────────────────────────────────

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

// ── Test Run types (unified validation + manufacturing) ──────

export interface TestRun {
  id: string;
  type: 'VALIDATION' | 'MANUFACTURING';
  name?: string;
  productId: string;
  fixtureId: string;
  testPackageId?: string;
  buildRunId?: string;
  manufacturingSessionId?: string;
  panelIdentifier?: string;
  assetSetId?: string;
  status: 'PENDING' | 'ACTIVE' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  operatorId: string;
  targetCount: number;
  completedCount: number;
  passedCount: number;
  failedCount: number;
  config?: Record<string, any>;
  notes?: string;
  errorMessage?: string;
  startedAt?: string;
  completedAt?: string;
  durationMs?: number;
  createdAt: string;
  updatedAt: string;
  // Relations (when included)
  product?: { id: string; name: string; slug?: string };
  fixture?: { id: string; name: string; stationId?: string };
  operator?: { id: string; name: string; email: string };
  testPackage?: { id: string; version: string; type: string };
  buildRun?: { id: string; name?: string; commitSha?: string; branch: string };
  targets?: RunTarget[];
}

/** Backward-compat aliases */
export type ValidationRun = TestRun;
export type ValidationDevice = RunTarget;
export type ValidationExecution = TestExecution;
export type ValidationResult = TestStep;

export interface RunTarget {
  id: string;
  runId: string;
  slotIndex: number;
  slotId?: string;
  serialNumber?: string;
  deviceId?: string;
  status: 'PENDING' | 'RUNNING' | 'PASSED' | 'FAILED' | 'ERROR';
  metadata?: Record<string, any>;
  errorMessage?: string;
  startedAt?: string;
  completedAt?: string;
  durationMs?: number;
  createdAt: string;
  executions?: TestExecution[];
}

export interface TestExecution {
  id: string;
  targetId: string;
  executionIndex: number;
  name: string;
  module?: string;
  status: 'PENDING' | 'RUNNING' | 'PASSED' | 'FAILED' | 'SKIPPED' | 'ERROR';
  durationMs?: number;
  errorMessage?: string;
  measurements?: Record<string, any>;
  logOutput?: string;
  logStorageKey?: string;
  startedAt?: string;
  completedAt?: string;
  createdAt: string;
  steps?: TestStep[];
}

export interface TestStep {
  id: string;
  executionId: string;
  stepIndex: number;
  name: string;
  status: 'PENDING' | 'RUNNING' | 'PASSED' | 'FAILED' | 'SKIPPED' | 'ERROR';
  passed?: boolean;
  durationMs?: number;
  errorMessage?: string;
  measurements?: Record<string, any>;
  logOutput?: string;
  logStorageKey?: string;
  startedAt?: string;
  completedAt?: string;
}

export type ValidationTrigger = 'manual' | 'bitbucket' | 'regression' | 'scheduled' | 'ci';
export type ValidationStage = 'smoke' | 'driver' | 'integration' | 'regression' | 'fuota';

// ── Test Catalog types ────────────────────────────────────────

export interface TestCatalogSummary {
  product: string;
  version: string;
  board: string | null;
  testCount: number;
  stageCount: number;
}

export interface TestStage {
  id: string;
  name: string;
  description: string | null;
  timingBudgetS: number;
  trigger: 'pr' | 'cron' | 'manual';
  blocksMerge: boolean;
  cron?: string;
  requiresHarness?: boolean;
  directory?: string;
  testCount: number;
  totalTimeoutS: number;
}

export interface TestDefinition {
  id: string;
  name: string;
  stage: string;
  timeoutS: number;
  description: string;
  hardware: string[];
  category?: string;
  stageInfo?: {
    id: string;
    name: string;
    timingBudgetS: number;
  };
}

export interface TestCatalog {
  version: string;
  product: string;
  board: string | null;
  stages: Record<string, TestStage>;
  hardware: Record<string, { description: string; required: boolean }>;
  tests: TestDefinition[];
  testCount: number;
  stageCount: number;
}

// ── Build Matrix types ───────────────────────────────────────

export interface StageBuildMatrixEntry {
  id: string;
  label: string;
  fwType: string;
  variant: string;
  processor: string | null;
  filenamePattern: string | null;
  configLog: boolean;
  producesHex: boolean;
  producesCfw: boolean;
  gitRef: string;
  isVersionBump: boolean;
  baseLabel: string | null;
  description: string | null;
  sortOrder: number;
}

// ── Asset Set types ──────────────────────────────────────────

export interface AssetSet {
  id: string;
  productId: string;
  version: string;
  variant: string;
  stage: number | null;
  source: 'BUILD_SERVICE' | 'MANUAL_UPLOAD' | 'EXTERNAL_CI';
  status: 'PENDING' | 'COMPLETE' | 'VALIDATED' | 'FAILED';
  buildRunId: string | null;
  externalBuildId: string | null;
  recipeVersionId: string | null;
  modemFirmwareId: string | null;
  modemFirmware: { id: string; version: string; filename: string; storageKey: string; sizeBytes: number } | null;
  commitSha: string | null;
  branch: string | null;
  notes: string | null;
  boardRevision?: { id: string; version: string; ckBoardsName: string } | null;
  createdBy?: { id: string; name: string } | null;
  assets: AssetFile[];
  createdAt: string;
  updatedAt: string;
}

export interface AssetFile {
  id: string;
  label: string;
  role: string;
  processor: string | null;
  artifactType: string;
  storageKey: string | null;
  filename: string;
  sizeBytes: number;
  checksum: string;
}

// ── UI utility types ─────────────────────────────────────────

export interface TreeNode {
  label: string;
  permKey?: string;
  children: TreeNode[];
}

// ── Guides types ─────────────────────────────────────────────

export interface GuideStep {
  title: string;
  description: string;
}

export interface GuideSection {
  id: string;
  title: string;
  icon: unknown;
  steps: GuideStep[];
}

// ── Node types ─────────────────────────────────────────────

export interface ConcordNode {
  id: string;
  name: string;
  hostname: string;
  type: string;
  status: string;
  ipAddress: string | null;
  hardwareRevision: string | null;
  metadata: Record<string, unknown> | null;
  lastSeenAt?: string | null;
  deploymentStatus?: {
    name: string;
    replicas: number;
    readyReplicas: number;
    availableReplicas: number;
    pods: { name: string; nodeName: string | null; status: string; ready: boolean; restarts: number }[];
  } | null;
  fixtureSlot?: {
    id: string;
    fixtureId: string;
    slotIndex: number;
    label: string | null;
    fixtureName?: string;
  } | null;
  createdAt: string;
  updatedAt: string;
}

export interface DiscoveredNode {
  hostname: string;
  ip: string;
  arch: string;
  status: string;
  labels: Record<string, string>;
}

export interface NodeSyncResult {
  registered: ConcordNode[];
  discovered: DiscoveredNode[];
  offline: ConcordNode[];
}

// ── Fixture types ──────────────────────────────────────────

export interface FixtureSlot {
  id: string;
  fixtureId: string;
  slotIndex: number;
  label: string | null;
  nodeId: string | null;
  active: boolean;
  node?: {
    id: string;
    name: string;
    hostname: string;
    type: string;
    status: string;
  } | null;
  createdAt: string;
  updatedAt: string;
}

export interface Fixture {
  id: string;
  name: string;
  productId: string;
  boardRevisionId: string | null;
  designId: string | null;
  type: string;
  description: string | null;
  active: boolean;
  metadata: Record<string, unknown> | null;
  slotCount?: number;
  productName?: string;
  boardRevision?: { id: string; version: string; ckBoardsName: string } | null;
  design?: FixtureDesignSummary | null;
  slots?: FixtureSlot[];
  createdAt: string;
  updatedAt: string;
}

// ── Manufacturing config types ─────────────────────────────

export interface ManufacturingStageConfig {
  name: string;
  enabled: boolean;
}

export interface ManufacturingPersonalizationConfig {
  coreOpsUrl: string;
  deviceType: number;
  deviceVariant: number;
  defaultCarrier: string;
}

export interface ManufacturingPassCriteria {
  allStagesMustPass: boolean;
  maxRetriesPerUnit: number;
}

export interface ManufacturingConfig {
  id: string;
  productId: string;
  boardRevisionId: string | null;
  enabled: boolean;
  stages: ManufacturingStageConfig[];
  firmwareSource: string;
  firmwareSetId: string | null;
  personalizationConfig: ManufacturingPersonalizationConfig | null;
  passCriteria: ManufacturingPassCriteria | null;
  boardRevision?: { id: string; version: string } | null;
  createdAt: string | null;
  updatedAt: string | null;
}

// ── Manufacturing session types ───────────────────────────

export interface ManufacturingSession {
  id: string;
  productId: string;
  fixtureId: string;
  status: 'ACTIVE' | 'COMPLETED' | 'CANCELLED';
  operatorId: string;
  assetSetId?: string;
  assetSet?: { id: string; version: string; variant: string; status: string };
  runnerStatus?: string; // DEPLOYING | READY | RUNNING | ERROR
  runnerLastHeartbeat?: string;
  config?: Record<string, any>;
  notes?: string;
  startedAt: string;
  endedAt?: string;
  createdAt: string;
  // Relations
  product?: { id: string; name: string; slug?: string };
  fixture?: { id: string; name: string };
  operator?: { id: string; name: string; email: string };
  runs?: TestRun[];
}

/**
 * @deprecated Use ManufacturingSession with `runs` relation instead.
 * Kept for backward compatibility with components that still reference panels.
 */
export interface ManufacturingSessionDetail extends ManufacturingSession {
  panels: ManufacturingPanel[];
}

/**
 * @deprecated Use TestRun (type=MANUFACTURING) instead.
 * Panels map to individual TestRun entries within a ManufacturingSession.
 */
export interface ManufacturingPanel {
  id: string;
  sessionId: string;
  panelIndex: number;
  qrCode: string;
  status: string;
  unitCount: number;
  passedUnits: number;
  failedUnits: number;
  startedAt: string | null;
  completedAt: string | null;
  durationMs: number | null;
  units: ManufacturingUnit[];
}

/**
 * @deprecated Use RunTarget instead.
 */
export interface ManufacturingUnit {
  id: string;
  panelId: string;
  slotIndex: number;
  slotId: string;
  serialNumber: string | null;
  status: string;
  stages: ManufacturingStage[];
  errorMessage: string | null;
  startedAt: string | null;
  completedAt: string | null;
  durationMs: number | null;
}

/**
 * @deprecated Use TestExecution / TestStep instead.
 */
export interface ManufacturingStage {
  name: string;
  status: string;
  durationMs?: number | null;
  measurements?: Record<string, unknown> | null;
  errorMessage?: string | null;
}

/**
 * @deprecated Use Fixture instead.
 */
export interface ManufacturingFixture {
  id: string;
  name: string;
  productId: string;
  productName?: string;
  type: string;
  status: string;
  slotCount: number;
  description?: string;
  activeSessionId?: string | null;
}

// ── Dashboard types ────────────────────────────────────────

export interface DashboardFixture {
  id: string;
  name: string;
  type: string;
  active: boolean;
  productName: string | null;
  productId: string;
  slotCount: number;
  assignedCount: number;
  nodesOnline: number;
  nodesOffline: number;
  nodesError: number;
  health: 'HEALTHY' | 'DEGRADED' | 'ERROR' | 'UNASSIGNED' | 'EMPTY' | 'UNKNOWN';
  updatedAt: string;
}

export interface DashboardStats {
  products?: { total: number; active: number };
  builds?: { total: number; active: number; failed: number };
  validation?: { total: number; active: number; passed: number; passRate: number | null; queueDepth: number };
  manufacturing?: { total: number; active: number };
  fixtures?: { total: number; online: number; degraded: number };
}

export interface DashboardData {
  stats: DashboardStats;
  fixtures: DashboardFixture[];
}

// ── MTIB Observability types ────────────────────────────────

export interface PowerReading {
  channel: number;
  voltage_v: number;
  current_ma: number;
  power_mw: number;
  enabled: boolean;
  timestamp: string;
}

export interface GpioState {
  pin: number;
  direction: number;
  value: boolean;
  configured: boolean;
  last_changed: string;
}

export interface UartPortStatus {
  port_name: string;
  is_open: boolean;
  baud_rate: number;
  bytes_received: number;
  bytes_sent: number;
  client_count: number;
  recent_lines: string[];
}

export interface SystemMetrics {
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  uptime_seconds: number;
  hostname: string;
  os_info: string;
  hardware_revision: string;
  server_version: string;
  grpc_active_connections: number;
  grpc_total_requests: number;
}

export interface ClientInfo {
  client_id: string;
  remote_addr: string;
  connected_since: string;
  active_rpcs: string[];
}

export interface AdcReading {
  channel: number;
  voltage_v: number;
  raw_value: number;
}

export interface ObservabilitySnapshot {
  timestamp: string;
  power_readings: PowerReading[];
  gpio_states: GpioState[];
  uart_ports: UartPortStatus[];
  system_metrics: SystemMetrics;
  connected_clients: ClientInfo[];
  adc_readings: AdcReading[];
}

export interface MtibDeploymentStatus {
  status: 'running' | 'pending' | 'failed' | 'not_deployed';
  replicas: number;
  ready: number;
  pod_name: string;
  restart_count: number;
}

export interface ObservabilityNode {
  id: string;
  name: string;
  hostname: string;
  type: string;
  status: string;
  ip_address: string | null;
  hardware_revision: string | null;
  deployment_status: MtibDeploymentStatus | null;
  snapshot: ObservabilitySnapshot | null;
  last_seen: string | null;
  online: boolean;
}

export interface ObservabilitySummary {
  total: number;
  online: number;
  offline: number;
  total_power_mw: number;
}

export interface FleetObservabilityResponse {
  nodes: ObservabilityNode[];
  summary: ObservabilitySummary;
}

// ── Deployment types ───────────────────────────────────────

export interface ConcordDeployment {
  id: string;
  name: string;
  productId: string | null;
  fixtureId: string | null;
  status: string;
  config: Record<string, unknown> | null;
  version: string | null;
  fixtureName?: string;
  productName?: string;
  createdBy?: { id: string; name: string } | null;
  k8sStatus?: DeploymentK8sStatus | null;
  createdAt: string;
  updatedAt: string;
}

export interface DeploymentK8sStatus {
  deployments: {
    name: string;
    replicas: number;
    readyReplicas: number;
    availableReplicas: number;
    pods: {
      name: string;
      nodeName: string;
      status: string;
      ready: boolean;
      restarts: number;
    }[];
  }[];
}

// ── Validation Infrastructure ─────────────────────────────────

export interface FixtureDesign {
  id: string;
  name: string;
  boardRevisionId: string;
  revision: string;
  capabilities: string[];
  profileTemplate: Record<string, unknown>;
  schematicUrl: string | null;
  bomUrl: string | null;
  assemblyGuide: string | null;
  notes: string | null;
  boardRevision?: { id: string; version: string; ckBoardsName: string } | null;
  benchCount?: number;
  createdAt: string;
  updatedAt: string;
}

export interface FixtureDesignSummary {
  id: string;
  name: string;
  boardRevisionId: string;
  revision: string;
  capabilities: string[];
  boardRevision?: { id: string; version: string; ckBoardsName: string } | null;
  benchCount?: number;
  createdAt: string;
}

export interface TestBench {
  id: string;
  stationId: string;
  name: string;
  mtibAddress: string;
  mtibRevision: string | null;
  capabilities: string[];
  fixtureDesignId: string | null;
  fixtureDesign?: FixtureDesignSummary;
  profileOverrides: Record<string, unknown> | null;
  dutProduct: string;
  dutRevision: string;
  dutDeviceId: string | null;
  dutSnr: string | null;
  dutImei: string | null;
  dutIccids: string[];
  jlinkAppSerial: string | null;
  jlinkCommsSerial: string | null;
  uartAppPath: string | null;
  uartCommsPath: string | null;
  status: 'AVAILABLE' | 'LOCKED' | 'OFFLINE' | 'MAINTENANCE';
  lockedBy: string | null;
  lockedAt: string | null;
  lastHealthCheck: string | null;
  metadata: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
}

export interface UnregisteredMtib {
  hostname: string;
  ip: string;
  mtibAddress: string;
  hardwareRevision: string | null;
  labels: Record<string, string>;
  ready: boolean;
}

// ── Build Script Editor types ───────────────────────────────

export interface RecipeVersion {
  id: string;
  version: number;
  status: 'draft' | 'published';
  changeNote: string | null;
  createdBy: { id: string; name: string } | null;
  createdAt: string;
  content?: string;
}

export interface RecipeTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  content: string;
}
