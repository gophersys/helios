// Validation Flow Types

export type ValidationCategory = 'SIM' | 'DRV' | 'INT' | 'PRD';
export type ValidationNodeType = 'BUILD' | 'FLASH' | 'FUOTA' | 'TEST' | 'MANUAL' | 'GATE';
export type ValidationStepStatus = 'PENDING' | 'BLOCKED' | 'RUNNING' | 'PASSED' | 'FAILED' | 'SKIPPED';

export interface FlowNodeData {
  id: string;
  type: ValidationNodeType;
  label: string;
  category: ValidationCategory;
  status: ValidationStepStatus;
  progress?: number; // 0-100 for running steps
  summary?: string; // "12/12 passed" or "45% (234/512)"
  config?: Record<string, unknown>;
}

export interface FlowEdgeData {
  id: string;
  source: string;
  target: string;
  condition?: 'success' | 'failure' | 'always';
}

export interface ValidationDesign {
  id: string;
  name: string;
  slug: string;
  product: string;
  board: string;
  description?: string;
  nodes: FlowNodeData[];
  edges: FlowEdgeData[];
}

export interface ValidationRun {
  id: string;
  designId: string;
  design?: ValidationDesign;
  pipelineId?: string;
  status: 'PENDING' | 'RUNNING' | 'PASSED' | 'FAILED' | 'CANCELLED';
  deviceId?: string;
  nodeId?: string;
  currentStep?: string;
  stepsTotal: number;
  stepsPassed: number;
  stepsFailed: number;
  startedAt?: string;
  finishedAt?: string;
  durationMs?: number;
  steps?: ValidationStep[];
}

export interface ValidationStep {
  id: string;
  runId: string;
  nodeId: string;
  nodeType: ValidationNodeType;
  nodeLabel: string;
  category: ValidationCategory;
  status: ValidationStepStatus;
  startedAt?: string;
  finishedAt?: string;
  durationMs?: number;
  summary?: string;

  // Test results
  testsTotal?: number;
  testsPassed?: number;
  testsFailed?: number;
  testsSkipped?: number;
  testResults?: TestResult[];

  // FUOTA progress
  fuotaPlanId?: number;
  fuotaTargets?: string;
  fuotaPages?: number;
  fuotaPagesTotal?: number;
  fuotaPercent?: number;

  // Details
  errorMessage?: string;
  logs?: string;
  artifacts?: ArtifactLink[];
  metrics?: PowerMetrics;
}

export interface TestResult {
  name: string;
  status: 'PASSED' | 'FAILED' | 'SKIPPED' | 'ERROR';
  durationMs: number;
  message?: string;
}

export interface ArtifactLink {
  name: string;
  url: string;
  type: 'log' | 'power' | 'uart' | 'other';
  sizeBytes?: number;
}

export interface PowerMetrics {
  ch0?: { avg: number; min: number; max: number };
  ch1?: { avg: number; min: number; max: number };
  samples?: number;
  durationMs?: number;
}

// Category display info
export const CATEGORY_INFO: Record<ValidationCategory, { label: string; color: string }> = {
  SIM: { label: 'Simulation', color: 'blue' },
  DRV: { label: 'Driver', color: 'yellow' },
  INT: { label: 'Integration', color: 'orange' },
  PRD: { label: 'Product', color: 'red' },
};

// Node type icons (using text for now, could be Lucide icons)
export const NODE_TYPE_ICONS: Record<ValidationNodeType, string> = {
  BUILD: '🔨',
  FLASH: '⚡',
  FUOTA: '📡',
  TEST: '🧪',
  MANUAL: '👤',
  GATE: '🚪',
};
