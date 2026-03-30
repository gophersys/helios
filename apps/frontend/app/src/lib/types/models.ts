// Shared model interfaces used across the application.

// ── Auth types ───────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  name: string;
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

export interface Chipset {
  id: string;
  name: string;
  manufacturer: string | null;
  isModem: boolean;
  description: string | null;
  active: boolean;
  productCount?: number;
  createdAt: string;
  updatedAt: string;
}

export interface BoardRevision {
  id: string;
  boardId: string;
  version: string;
  chipsets: { id: string; name: string; isModem: boolean }[];
  selectedBuilds: Record<string, string>;
  status: string;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Board {
  id: string;
  productId: string;
  name: string;
  description: string | null;
  active: boolean;
  revisionCount?: number;
  revisions?: BoardRevision[];
  createdAt: string;
  updatedAt: string;
}

export interface FirmwareBuild {
  id: string;
  productId: string;
  chipsetId: string;
  chipset: { id: string; name: string; isModem: boolean };
  version: string;
  isManufacturing: boolean;
  storageKey: string;
  filename: string;
  sizeBytes: string | null;
  checksum: string;
  contentType: string | null;
  status: string;
  notes: string | null;
  modemFilename?: string | null;
  modemSizeBytes?: string | null;
  modemChecksum?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ProductTarget {
  id: string;
  role: string;
  soc: string;
  appId: number;
}

export interface Product {
  id: string;
  name: string;
  slug: string | null;
  description: string | null;
  active: boolean;
  metadata: Record<string, unknown> | null;
  buildConfig: BuildConfig | null;
  targets: ProductTarget[];
  boardCount?: number;
  firmwareBuildCount?: number;
  boards?: Board[];
  firmwareBuilds?: FirmwareBuild[];
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

export interface DtsPeripheral {
  compatible: string;
  type: string;
  bus: string;
}

export interface BoardRevisionDetail {
  name: string;
  peripherals: DtsPeripheral[];
}

export interface BoardSummary {
  board: string;
  socs: string[];
  revisions: string[];
  variants: string[];
}

export interface BoardDetail {
  board: string;
  socs: string[];
  revisions: BoardRevisionDetail[];
  variants: string[];
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

// ── Validation types ─────────────────────────────────────────

export interface ValidationDevice {
  id: string;
  serialNumber: string;
  sessionId: string;
  status: string;
  metadata: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
}

export interface ValidationTest {
  id: string;
  name: string;
  category: string;
  enabled: boolean;
  sortOrder: number;
}

export interface ValidationResult {
  id: string;
  executionId: string;
  stepIndex: number;
  groupIndex: number;
  passed: boolean;
  result: Record<string, unknown> | null;
  createdAt: string;
}

export interface ValidationExecution {
  id: string;
  testId: string;
  nodeId: string;
  deviceId: string;
  status: 'QUEUED' | 'RUNNING' | 'PASSED' | 'FAILED' | 'CANCELLED' | 'SKIPPED';
  config: Record<string, unknown> | null;
  startedAt: string | null;
  finishedAt: string | null;
  createdAt: string;
  updatedAt: string;
  test?: ValidationTest;
  resultCount?: number;
  resultsPassed?: number;
  results?: ValidationResult[];
}

export type ValidationTrigger = 'manual' | 'bitbucket' | 'nightly' | 'scheduled' | 'ci';
export type ValidationStage = 'smoke' | 'silicon' | 'integration' | 'nightly' | 'fuota';

export interface ValidationRun {
  id: string;
  name: string;
  productId: string;
  fixtureId: string | null;
  status: 'ACTIVE' | 'COMPLETED' | 'CANCELLED' | 'PAUSED';
  config: Record<string, unknown> | null;
  targetCount: number;
  completedCount: number;
  passedCount: number;
  failedCount: number;
  startedAt: string | null;
  finishedAt: string | null;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
  product?: { id: string; name: string };
  createdBy?: { id: string; name: string; email: string };
  devices?: ValidationDevice[];
  executions?: ValidationExecution[];
  executionCount?: number;
  // Extended fields for filtering/display
  trigger?: ValidationTrigger;
  stage?: ValidationStage;
  pipelineRunId?: string;
  commitSha?: string;
  branch?: string;
}

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
  type: string;
  description: string | null;
  active: boolean;
  metadata: Record<string, unknown> | null;
  slotCount?: number;
  productName?: string;
  slots?: FixtureSlot[];
  createdAt: string;
  updatedAt: string;
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
  hasActiveDeployment: boolean;
  activeDeploymentStatus: string | null;
  updatedAt: string;
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
  product: string;
  revision: string;
  capabilities: string[];
  profileTemplate: Record<string, unknown>;
  schematicUrl: string | null;
  bomUrl: string | null;
  assemblyGuide: string | null;
  notes: string | null;
  benchCount?: number;
  createdAt: string;
  updatedAt: string;
}

export interface FixtureDesignSummary {
  id: string;
  name: string;
  product: string;
  revision: string;
  capabilities: string[];
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
